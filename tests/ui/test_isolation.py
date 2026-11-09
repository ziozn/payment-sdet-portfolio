from .pages.home_page import HomePage
from .pages.payment_page import PaymentPage


def test_session_starts_clean_and_leaves_payment(android_driver, ui_snapshot, ui_case):
    with ui_case:
        home = HomePage(android_driver)
        payment = PaymentPage(android_driver)
        assert home.is_displayed()
        home.open_payment()
        payment.wait_until_loaded()
        assert payment.input_text() == ""
        assert payment.status_text() == "尚未发起操作"
        assert payment.amount_text() == "金额：—"
        assert payment.transaction_id_text() == "交易 ID：未生成（后台未执行）"
        ui_snapshot("clean-start")

        # Verify replacement, then intentionally leave this Activity dirty.
        # The next test must get a new session/home page, not depend on back().
        payment.enter_amount("33.00")
        assert payment.input_text() == "33.00"
        payment.enter_amount("88.88")
        assert payment.input_text() == "88.88"
        payment.submit()
        expected_status = "UI 演示模式：已校验金额 88.88 元；未调用后台 API，未产生支付。"
        payment.wait_for_status(expected_status)
        assert payment.status_text() == expected_status
        assert payment.amount_text() == "金额：88.88 元"
        assert payment.transaction_id_text() == "交易 ID：未生成（后台未执行）"
        ui_snapshot("dirty-end")
