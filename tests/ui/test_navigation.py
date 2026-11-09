from .pages.home_page import HomePage
from .pages.payment_page import PaymentPage


def test_reenter_payment_page(android_driver, ui_snapshot, ui_case):
    with ui_case:
        home = HomePage(android_driver)
        payment = PaymentPage(android_driver)

        for visit, value in enumerate(("1.00", "2.00"), start=1):
            assert home.is_displayed()
            home.open_payment()
            payment.wait_until_loaded()
            # A new Activity should not retain the previous visit's result.
            assert payment.input_text() == ""
            assert payment.status_text() == "尚未发起操作"
            assert payment.amount_text() == "金额：—"
            assert payment.transaction_id_text() == "交易 ID：未生成（后台未执行）"

            payment.enter_amount(value)
            assert payment.input_text() == value
            payment.submit()
            expected_status = f"UI 演示模式：已校验金额 {value} 元；未调用后台 API，未产生支付。"
            payment.wait_for_status(expected_status)
            assert payment.status_text() == expected_status
            assert payment.amount_text() == f"金额：{value} 元"
            assert payment.transaction_id_text() == "交易 ID：未生成（后台未执行）"
            ui_snapshot(f"visit-{visit}-result")

            payment.back_home()
            assert home.is_displayed()
            assert home.title_text() == "模拟支付测试"
