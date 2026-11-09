"""Real Android UI demo; no backend payment is executed."""
from .pages.home_page import HomePage
from .pages.payment_page import PaymentPage


def test_payment_ui_demo(android_driver, ui_snapshot, ui_case):
    with ui_case:
        home = HomePage(android_driver)
        payment = PaymentPage(android_driver)

        assert home.is_displayed()
        assert home.title_text() == "模拟支付测试"
        assert home.user_name_text() == "用户：DEMO_PERSON_01"
        assert "DEMO_CARD_001" in home.user_status_text()
        ui_snapshot("home")

        home.open_payment()
        payment.wait_until_loaded()
        payment.enter_amount("12.50")
        assert payment.input_text() == "12.50"
        payment.submit()

        expected_status = "UI 演示模式：已校验金额 12.50 元；未调用后台 API，未产生支付。"
        payment.wait_for_status(expected_status)
        assert payment.amount_text() == "金额：12.50 元"
        assert payment.status_text() == expected_status
        assert payment.transaction_id_text() == "交易 ID：未生成（后台未执行）"
        ui_snapshot("result")

        payment.back_home()
        assert home.is_displayed()
        assert home.title_text() == "模拟支付测试"
        assert android_driver.current_activity == ".MainActivity"
        ui_snapshot("home-return")
