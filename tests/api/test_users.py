from contextlib import closing
import sqlite3
from uuid import UUID, uuid4

import pytest
import requests

TIMEOUT = (2, 3)
PAYLOAD = {"display_name": "DEMO_PERSON_01"}


def test_create_user(api_base_url, user_namespace):
    response = requests.post(f"{api_base_url}/users", json=PAYLOAD, headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 201, response.text
    user = response.json()
    assert str(UUID(user["user_id"])) == user["user_id"]
    assert user["status"] == "NEW"
    assert user["display_name"] == PAYLOAD["display_name"]


def test_read_created_user(api_base_url, user_namespace):
    created = requests.post(f"{api_base_url}/users", json=PAYLOAD, headers=user_namespace, timeout=TIMEOUT)
    assert created.status_code == 201, created.text
    response = requests.get(f"{api_base_url}/users/{created.json()['user_id']}", headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 200, response.text
    assert response.json() == created.json()


def test_user_ids_are_unique(api_base_url, user_namespace):
    ids = []
    for _ in range(5):
        response = requests.post(f"{api_base_url}/users", json=PAYLOAD, headers=user_namespace, timeout=TIMEOUT)
        assert response.status_code == 201, response.text
        ids.append(response.json()["user_id"])
    assert len(set(ids)) == 5  # 同名允许创建不同用户；POST 暂无幂等语义


@pytest.mark.parametrize("payload", [
    {}, {"display_name": ""}, {"display_name": "REAL_PERSON"},
    {"display_name": 123}, {"display_name": True}, {"display_name": None},
    {"display_name": "DEMO_" + "x" * 41},
    {"display_name": "DEMO_A", "status": "VERIFIED"}, [],
])
def test_invalid_body_returns_422(api_base_url, user_namespace, api_service, payload):
    response = requests.post(f"{api_base_url}/users", json=payload, headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 422, response.text
    assert response.json()["detail"]
    # 确认校验失败没有写入记录，不靠下一条用例检查。
    with closing(sqlite3.connect(api_service["database_path"])) as connection:
        count = connection.execute("SELECT COUNT(*) FROM users WHERE test_run_id = ?",
                                   (user_namespace["X-Test-Run-ID"],)).fetchone()[0]
    assert count == 0


def test_malformed_json_returns_422(api_base_url, user_namespace):
    response = requests.post(f"{api_base_url}/users", data='{',
                            headers={**user_namespace, "Content-Type": "application/json"}, timeout=TIMEOUT)
    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["type"] == "json_invalid"


@pytest.mark.parametrize("headers", [{}, {"X-Test-Run-ID": "bad space"}, {"X-Test-Run-ID": "x" * 65}])
def test_invalid_namespace_returns_422(api_base_url, headers):
    response = requests.post(f"{api_base_url}/users", json=PAYLOAD, headers=headers, timeout=TIMEOUT)
    assert response.status_code == 422, response.text


def test_unknown_user_returns_404(api_base_url, user_namespace):
    response = requests.get(f"{api_base_url}/users/{uuid4()}", headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "User not found"}


def test_other_namespace_cannot_read_user(api_base_url, user_namespace):
    created = requests.post(f"{api_base_url}/users", json=PAYLOAD, headers=user_namespace, timeout=TIMEOUT)
    assert created.status_code == 201, created.text
    response = requests.get(f"{api_base_url}/users/{created.json()['user_id']}",
                            headers={"X-Test-Run-ID": uuid4().hex}, timeout=TIMEOUT)
    assert response.status_code == 404, response.text
    own = requests.get(f"{api_base_url}/users/{created.json()['user_id']}", headers=user_namespace, timeout=TIMEOUT)
    assert own.status_code == 200, own.text
    assert own.json() == created.json()
