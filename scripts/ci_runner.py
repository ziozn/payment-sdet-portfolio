"""Small local Jenkins runner; subprocess exit codes remain authoritative."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
SERVER_URL = "http://127.0.0.1:4723"
UDID = os.environ.get("ANDROID_UDID", "emulator-5554")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stop_process(process):
    """Only handle the child returned by our own Popen, never process-name kills."""
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def command(directory, name, args, env=None):
    directory.mkdir(parents=True, exist_ok=True)
    args = [str(arg) for arg in args]
    record = {"argv": args, "cwd": str(ROOT)}  # Do not dump environment/secrets.
    write_json(directory / f"{name}-command.json", record)
    start = time.monotonic()
    with (directory / f"{name}.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(args, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait()
        except BaseException:
            stop_process(process)
            raise
        finally:
            write_json(directory / f"{name}-result.json", {
                "exit_code": process.returncode, "elapsed_seconds": time.monotonic() - start,
            })
    print(f"{name}: exit={code}; log={directory / (name + '.log')}", flush=True)
    return code


def checked(directory, name, args, env=None):
    code = command(directory, name, args, env)
    if code:
        raise RuntimeError(f"{name} exited {code}; see {directory / (name + '.log')}")
    return (directory / f"{name}.log").read_text(encoding="utf-8")


def prepare(output):
    if not PYTHON.is_file():
        raise RuntimeError(f"Missing existing project interpreter: {PYTHON}")
    code = command(output, "python", [PYTHON, "-c", (
        "import sys, importlib.metadata as m; "
        "print('executable:', sys.executable); print('version:', sys.version); "
        "print('prefix:', sys.prefix); "
        "print({p: m.version(p) for p in ['pytest','requests','fastapi','uvicorn','allure-pytest']})"
    )])
    if code:
        return code
    if (ROOT / ".git").exists():
        checked(output, "git-head", ["git", "rev-parse", "HEAD"])
        checked(output, "git-status", ["git", "status", "--short"])
    return 0


def pytest_command(directory, paths):
    if (directory / "pytest-command.json").exists():
        raise RuntimeError(f"Refusing to mix or overwrite test executions in {directory}; use a new build output")
    traceback_style = "--tb=short" if directory.name == "api" else "--tb=long"
    return [PYTHON, "-m", "pytest", *paths, "-v", "-s", traceback_style,
            f"--junitxml={directory / 'junit.xml'}", f"--alluredir={directory / 'allure-results'}"]


def api(output):
    directory = output / "api"
    before = set((ROOT / "artifacts/api-service").glob("service-*"))
    try:
        return command(directory, "pytest", pytest_command(directory, ["tests/api", "tests/storage"]))
    finally:
        # Existing fixture paths stay unchanged. Copy only this run's text logs, not databases.
        for service in set((ROOT / "artifacts/api-service").glob("service-*")) - before:
            for source in service.iterdir():
                if source.is_file() and source.suffix in {".log", ".txt"}:
                    destination = directory / "service-logs" / service.name
                    destination.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination / source.name)


def ui(output, probe=False):
    directory = output / ("probe" if probe else "ui")
    directory.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["APPIUM_HOME"] = os.environ.get("APPIUM_HOME", str(ROOT / ".appium-home"))
    env["APPIUM_SERVER_URL"] = SERVER_URL
    env["UI_ARTIFACT_ROOT"] = str(directory / "evidence")
    if not Path(env["APPIUM_HOME"]).is_dir():
        raise RuntimeError("Project .appium-home is missing; do not change global Appium permissions")
    state = checked(directory, "device-state", ["adb", "-s", UDID, "get-state"], env)
    boot = checked(directory, "device-boot", ["adb", "-s", UDID, "shell", "getprop", "sys.boot_completed"], env)
    package = checked(directory, "device-app", ["adb", "-s", UDID, "shell", "pm", "path", "com.example.paymentsim"], env)
    if state.strip() != "device" or boot.strip() != "1" or "package:" not in package:
        raise RuntimeError("Required emulator is not fully booted or demo APK is not installed")
    checked(directory, "node-version", ["node", "--version"], env)
    drivers = checked(directory, "drivers", ["appium", "driver", "list", "--installed"], env)
    if "uiautomator2" not in drivers.lower():
        raise RuntimeError("UiAutomator2 is missing from project APPIUM_HOME")
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 4723))
        except OSError as error:
            raise RuntimeError("Port 4723 is occupied; existing server will not be stopped or reused") from error
    log_path = directory / "appium.log"
    args = ["appium", "--address", "127.0.0.1", "--port", "4723", "--log", str(log_path),
            "--log-no-colors", "--log-timestamp"]
    write_json(directory / "appium-command.json", {"argv": args, "cwd": str(ROOT)})
    marker = directory / "appium-process.json"
    with (directory / "appium-console.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(args, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            write_json(marker, {"pid": process.pid, "log_path": str(log_path), "stopped": False})
            deadline = time.monotonic() + 60
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Our Appium process exited {process.returncode}; see {log_path}")
                try:
                    with urlopen(SERVER_URL + "/status", timeout=2) as response:
                        status = json.load(response)
                    if status.get("value", {}).get("ready") is True:
                        write_json(directory / "appium-status.json", status)
                        break
                except (OSError, ValueError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Our Appium was not ready within 60 seconds; see {log_path}")
                time.sleep(0.25)  # Bounded server health poll, not a UI timing workaround.
            paths = ["tests/ui/failure_probe.py"] if probe else ["tests/ui"]
            return command(directory, "pytest", pytest_command(directory, paths), env)
        finally:
            stop_process(process)
            write_json(marker, {"pid": process.pid, "log_path": str(log_path), "stopped": True,
                                "exit_code": process.returncode})


def cleanup(output):
    for marker in output.glob("*/appium-process.json"):
        resource = json.loads(marker.read_text(encoding="utf-8"))
        if resource.get("stopped"):
            continue
        pid = int(resource["pid"])
        log_path = str(marker.parent / "appium.log")
        if resource.get("log_path") != log_path:
            raise RuntimeError(f"Invalid process marker: {marker}")
        result = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
        if result.returncode == 0:
            if log_path not in result.stdout or "appium" not in result.stdout.lower():
                raise RuntimeError(f"PID {pid} ownership cannot be confirmed; refusing to stop it")
            os.kill(pid, signal.SIGINT)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode:
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError(f"Owned Appium PID {pid} did not exit after SIGINT")
        resource["stopped"] = True
        write_json(marker, resource)
    return 0


def report(output):
    results = [path for name in ("api", "ui", "probe")
               if (path := output / name / "allure-results").is_dir()]
    if not results:
        (output / "report-status.txt").write_text("No Allure result directories were produced.\n")
        return 0
    allure = shutil.which("allure")
    if not allure:
        (output / "report-status.txt").write_text("Allure CLI unavailable; raw results and JUnit retained.\n")
        return 1
    env = os.environ.copy()
    temporary = ROOT / ".local/java-tmp" / output.name
    temporary.mkdir(parents=True, exist_ok=True)
    env["JAVA_TOOL_OPTIONS"] = f"-Djava.io.tmpdir={temporary}"
    return command(output, "allure-generate", [allure, "generate", *results,
                   "-o", output / "html-report", "--clean"], env)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "api", "ui", "probe", "report", "cleanup"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "artifacts/ci") or output == ROOT / "artifacts/ci":
        parser.error("--output must be a build directory underneath this project's artifacts/ci/")
    output.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, lambda number, frame: sys.exit(128 + number))
    try:
        code = ui(output, probe=True) if args.stage == "probe" else globals()[args.stage](output)
    except Exception:
        (output / f"{args.stage}-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        traceback.print_exc()
        code = 1
    (output / f"{args.stage}-exit-code.txt").write_text(str(code) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
