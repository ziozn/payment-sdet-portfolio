import pytest

from .pages.home_page import HomePage
from .pages.payment_page import PaymentPage


@pytest.mark.parametrize("value", ["", "0", "12.501"], ids=["empty", "zero", "three-decimals"])
def test_invalid_amount(android_driver, ui_snapshot, ui_case, value):
    with ui_case:
        home = HomePage(android_driver)
        payment = PaymentPage(android_driver)
        assert home.is_displayed()
        home.open_payment()
        payment.wait_until_loaded()

        payment.enter_amount(value)
        # Check the actual field, so keyboard filtering cannot create a false pass.
        assert payment.input_text() == value
        ui_snapshot("input")
        payment.submit()

        expected_status = "金额无效，请输入 0.01–10000.00 元且最多两位小数。"
        payment.wait_for_status(expected_status)
        assert payment.status_text() == expected_status
        assert payment.amount_text() == "金额：—"
        assert payment.transaction_id_text() == "交易 ID：未生成（后台未执行）"
        ui_snapshot("invalid-result")

        payment.back_home()
        assert home.is_displayed()
