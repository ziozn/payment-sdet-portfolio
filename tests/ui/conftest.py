"""Real Appium sessions, independent evidence, and explicit failure capture."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import traceback
from uuid import uuid4
import warnings

from appium import webdriver
from appium.options.android import UiAutomator2Options
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def ui_run_dir(request):
    # Each execution can choose its own round directory; each test gets a UUID.
    root = Path(os.environ.get("UI_ARTIFACT_ROOT", ROOT / "artifacts/ui"))
    directory = root / f"ui-{uuid4().hex}"
    directory.mkdir(parents=True)
    (directory / "test-id.txt").write_text(request.node.nodeid + "\n", encoding="utf-8")
    print(f"UI evidence: {directory.resolve()}")
    return directory


@pytest.fixture
def android_driver(ui_run_dir):
    server_url = os.environ.get("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    options = UiAutomator2Options().load_capabilities({
        "platformName": "Android",
        "appium:automationName": "UiAutomator2",
        "appium:udid": os.environ.get("ANDROID_UDID", "emulator-5554"),
        "appium:appPackage": "com.example.paymentsim",
        "appium:appActivity": "com.example.paymentsim.MainActivity",
        "appium:noReset": True,
        "appium:forceAppLaunch": True,
        "appium:newCommandTimeout": 60,
    })
    try:
        driver = webdriver.Remote(server_url, options=options)
    except Exception:
        (ui_run_dir / "setup-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise  # No returned driver: do not claim a successful session/quit.
    try:
        (ui_run_dir / "session.json").write_text(json.dumps({
            "server_url": server_url,
            "session_id": driver.session_id,
            "requested_capabilities": options.to_capabilities(),
            "actual_capabilities": driver.capabilities,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Appium session: {driver.session_id}")
        yield driver
    finally:
        try:
            errors = save_ui_snapshot(driver, ui_run_dir, "last-screen")
            if errors:
                warnings.warn(f"Final UI evidence incomplete: {ui_run_dir}: {errors}")
        except Exception as error:
            warnings.warn(f"Could not save final UI evidence to {ui_run_dir}: {error}")
        finally:
            # Evidence collection must never prevent the DELETE session request.
            try:
                driver.quit()
            except Exception:
                (ui_run_dir / "quit.txt").write_text(traceback.format_exc(), encoding="utf-8")
                raise
            else:
                (ui_run_dir / "quit.txt").write_text("driver.quit() completed\n", encoding="utf-8")


def save_ui_snapshot(driver, directory, name):
    """Try both evidence channels; record real errors without inventing content."""
    errors = {}
    try:
        (directory / f"{name}.xml").write_text(driver.page_source, encoding="utf-8")
    except Exception:
        errors["xml"] = traceback.format_exc()
    try:
        if not driver.save_screenshot(str(directory / f"{name}.png")):
            raise RuntimeError("Appium returned false while saving screenshot")
    except Exception:
        errors["screenshot"] = traceback.format_exc()
    (directory / f"{name}-capture.json").write_text(json.dumps({
        "xml_saved": "xml" not in errors,
        "screenshot_saved": "screenshot" not in errors,
        "errors": errors,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return errors


@pytest.fixture
def ui_snapshot(android_driver, ui_run_dir):
    def capture(name):
        errors = save_ui_snapshot(android_driver, ui_run_dir, name)
        if errors:
            raise RuntimeError(f"UI snapshot incomplete: {ui_run_dir}: {errors}")
    return capture


@pytest.fixture
def ui_case(android_driver, ui_run_dir):
    # A yield fixture does not receive exceptions from the test body.
    # The explicit with block catches the real exception before driver teardown.
    @contextmanager
    def record_failure():
        try:
            yield
        except Exception:
            original_traceback = traceback.format_exc()
            try:
                (ui_run_dir / "failure.txt").write_text(original_traceback, encoding="utf-8")
                errors = save_ui_snapshot(android_driver, ui_run_dir, "failure")
                if errors:
                    warnings.warn(f"Failure evidence incomplete: {ui_run_dir}: {errors}")
            except Exception as error:
                warnings.warn(f"Could not save failure evidence to {ui_run_dir}: {error}")
            raise  # Keep the original assertion/timeout and its pytest exit code.
    return record_failure()
