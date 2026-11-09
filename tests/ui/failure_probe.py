"""Explicit diagnostic only: intentionally fails; excluded from normal discovery."""
from .pages.home_page import HomePage
from .pages.payment_page import PaymentPage


def test_failure_capture_probe(android_driver, ui_snapshot, ui_case):
    with ui_case:
        home = HomePage(android_driver)
        payment = PaymentPage(android_driver)
        assert home.is_displayed()
        home.open_payment()
        payment.wait_until_loaded()
        payment.enter_amount("23.45")
        assert payment.input_text() == "23.45"
        payment.submit()
        expected_status = "UI 演示模式：已校验金额 23.45 元；未调用后台 API，未产生支付。"
        payment.wait_for_status(expected_status)
        assert payment.status_text() == expected_status
        ui_snapshot("before-deliberate-failure")
        raise AssertionError("Intentional Day 9 probe: verify automatic failure evidence and quit")
