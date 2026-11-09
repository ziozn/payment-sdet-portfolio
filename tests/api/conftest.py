"""普通 pytest fixture：真实服务生命周期与测试数据隔离。"""
import os
import sys
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import time
from uuid import uuid4

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
TIMEOUT = (2, 3)


@pytest.fixture(scope="session")
def api_service(request):
    run_dir = ROOT / "artifacts/api-service" / f"service-{uuid4().hex}"
    run_dir.mkdir(parents=True)
    database_path = run_dir / "test.db"
    if getattr(request, 'param', None) == 'legacy':
        # 独立旧结构快照：带虚构记录，再通过显式命令迁移后启动 HTTP 服务。
        with sqlite3.connect(database_path) as legacy:
            legacy.execute("""CREATE TABLE users (
                user_id TEXT PRIMARY KEY, test_run_id TEXT NOT NULL,
                display_name TEXT NOT NULL, status TEXT NOT NULL CHECK (status = 'NEW'))""")
            legacy.execute("INSERT INTO users VALUES ('legacy-http', 'legacy-space', 'DEMO_LEGACY', 'NEW')")
        legacy.close()
        result = subprocess.run([sys.executable, '-m', 'service.migrate_database',
                                 '--database', str(database_path)], cwd=ROOT, capture_output=True, text=True)
        (run_dir / 'migration.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PAYMENT_DB_PATH"] = str(database_path)
    command = [sys.executable, "-m", "uvicorn", "service.main:app",
               "--host", "127.0.0.1", "--port", str(port)]
    (run_dir / "command.txt").write_text(" ".join(command) + "\nPAYMENT_DB_PATH=" + str(database_path))
    with (run_dir / "uvicorn.log").open("w") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    pytest.fail(f"Uvicorn exited {process.returncode}: {(run_dir / 'uvicorn.log').read_text()}")
                try:
                    response = requests.get(f"{base_url}/health", timeout=TIMEOUT)
                    if response.status_code == 200 and response.json() == {"status": "ok"}:
                        break
                except requests.ConnectionError:
                    pass  # 仅启动就绪轮询；实际测试不捕获连接错误
                if time.monotonic() >= deadline:
                    pytest.fail(f"Service not ready: {(run_dir / 'uvicorn.log').read_text()}")
                time.sleep(0.1)
            yield {"base_url": base_url, "database_path": database_path}
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            (run_dir / "exit-code.txt").write_text(str(process.returncode))
            assert process.returncode == 0, (run_dir / "uvicorn.log").read_text()


@pytest.fixture(scope="session")
def api_base_url(api_service):
    return api_service["base_url"]


@pytest.fixture
def user_namespace(api_service):
    test_run_id = uuid4().hex
    try:
        yield {"X-Test-Run-ID": test_run_id}
    finally:
        connection = sqlite3.connect(api_service["database_path"])
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                connection.execute("DELETE FROM users WHERE test_run_id = ?", (test_run_id,))
            remaining = connection.execute(
                "SELECT COUNT(*) FROM users WHERE test_run_id = ?", (test_run_id,)
            ).fetchone()[0]
            assert remaining == 0
            cards = connection.execute("SELECT COUNT(*) FROM cards WHERE test_run_id = ?", (test_run_id,)).fetchone()[0]
            assert cards == 0
            payments = connection.execute("SELECT COUNT(*) FROM payments WHERE test_run_id = ?", (test_run_id,)).fetchone()[0]
            assert payments == 0
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            connection.close()


@pytest.fixture
def new_user(api_base_url, user_namespace):
    response = requests.post(f"{api_base_url}/users", json={"display_name": "DEMO_PERSON_01"},
                             headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def verified_user(api_base_url, user_namespace, new_user):
    response = requests.post(f"{api_base_url}/users/{new_user['user_id']}/verification",
                             json={"verification_name": "DEMO_PERSON_01", "identity_token": "DEMO_ID_01"},
                             headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def bound_card_user(api_base_url, user_namespace, verified_user):
    response = requests.post(f"{api_base_url}/users/{verified_user['user_id']}/cards",
                             json={"card_token":"DEMO_CARD_001"}, headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 201, response.text
    return {"user": verified_user, "card": response.json()}
