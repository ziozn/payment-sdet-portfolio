"""仅显式运行的报告排障练习：故意把支付成功状态码写错，不加入常规回归。"""
import allure
import requests


@allure.title("Diagnostic only: intentionally expect 200 instead of payment creation 201")
def test_intentionally_wrong_payment_status(api_base_url, user_namespace, bound_card_user):
    with allure.step("Send a real valid payment request"):
        response = requests.post(f"{api_base_url}/payments",
            json={"user_id":bound_card_user['user']['user_id'],
                  "card_id":bound_card_user['card']['card_id'], "amount_cent":100},
            headers={**user_namespace,"Idempotency-Key":"DEMO_FAILURE_DEMO"}, timeout=(2,3))
        allure.attach(f"HTTP {response.status_code}\n{response.text}", "Actual payment response", allure.attachment_type.TEXT)
    with allure.step("Intentionally wrong assertion, to inspect failure and traceback"):
        assert response.status_code == 200, f"Intentional demo: expected 200, actual {response.status_code}; {response.text}"
