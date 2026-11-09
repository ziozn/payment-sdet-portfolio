from contextlib import closing, contextmanager
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from threading import Barrier
from uuid import uuid4

import pytest
import requests
import allure
from conftest import user_namespace as namespace_fixture

TIMEOUT = (2, 3)


def pay_body(bound_card_user, amount_cent=100):
    return {"user_id": bound_card_user["user"]["user_id"],
            "card_id": bound_card_user["card"]["card_id"], "amount_cent": amount_cent}


def payment_rows(api_service, namespace):
    with closing(sqlite3.connect(api_service["database_path"])) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(
            "SELECT * FROM payments WHERE test_run_id=? ORDER BY payment_id",
            (namespace["X-Test-Run-ID"],))]


def payment_headers(namespace, key="DEMO_PAYMENT_001"):
    return {**namespace, "Idempotency-Key": key}


@allure.step("POST simulated payment")
def send_payment(url, *, json, headers, timeout):
    allure.attach(str(headers), "Demo request headers", allure.attachment_type.TEXT)
    allure.attach(str(json), "Demo request body", allure.attachment_type.TEXT)
    response = requests.post(url, json=json, headers=headers, timeout=timeout)
    allure.attach(f"HTTP {response.status_code}\n{response.text}", "Actual response", allure.attachment_type.TEXT)
    return response


def test_payment_success_and_query(api_base_url, user_namespace, bound_card_user, api_service):
    body = pay_body(bound_card_user)
    with allure.step("Submit simulated payment with a scoped idempotency key"):
        response = send_payment(f"{api_base_url}/payments", json=body,
                                 headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert response.status_code == 201, response.text
    payment = response.json()
    assert payment == {**body, "payment_id": payment["payment_id"], "status": "SUCCEEDED"}
    with allure.step("Read the payment through the business API"):
        read = requests.get(f"{api_base_url}/payments/{payment['payment_id']}",
                            headers=user_namespace, timeout=TIMEOUT)
    assert read.status_code == 200, read.text
    assert read.json() == payment
    rows = payment_rows(api_service, user_namespace)
    assert len(rows) == 1
    assert rows[0] == {**payment, "test_run_id": user_namespace["X-Test-Run-ID"],
                       "idempotency_key": "DEMO_PAYMENT_001"}
    (api_service["database_path"].parent / "payment-example.json").write_text(
        json.dumps({"request_headers": payment_headers(user_namespace), "request_json": body,
                    "response_status": response.status_code, "response_json": payment}, indent=2))


def test_same_key_same_request_creates_one_payment(api_base_url, user_namespace, bound_card_user, api_service):
    body = pay_body(bound_card_user)
    with allure.step("Create the first payment"):
        first = send_payment(f"{api_base_url}/payments", json=body,
                              headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert first.status_code == 201, first.text
    before = payment_rows(api_service, user_namespace)
    with allure.step("Retry the exact request and compare the same payment resource"):
        second = send_payment(f"{api_base_url}/payments", json=body,
                               headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert second.status_code == 201, second.text
    assert second.json() == first.json()
    assert payment_rows(api_service, user_namespace) == before
    assert len(before) == 1


@pytest.mark.parametrize("field,value", [("amount_cent", 101), ("user_id", "DEMO_OTHER_USER"),
                                         ("card_id", "DEMO_OTHER_CARD")])
def test_same_key_changed_parameters_conflict(api_base_url, user_namespace, bound_card_user, api_service, field, value):
    body = pay_body(bound_card_user)
    first = send_payment(f"{api_base_url}/payments", json=body,
                          headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert first.status_code == 201, first.text
    before = payment_rows(api_service, user_namespace)
    with allure.step(f"Retry with changed {field} and require conflict without another row"):
        response = send_payment(f"{api_base_url}/payments", json={**body, field: value},
                                 headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert response.status_code == 409, response.text
    assert payment_rows(api_service, user_namespace) == before


def test_two_concurrent_same_key_requests_create_one_payment(api_base_url, user_namespace, bound_card_user, api_service):
    barrier = Barrier(2)
    def send():
        barrier.wait(timeout=5)
        return send_payment(f"{api_base_url}/payments", json=pay_body(bound_card_user),
                             headers=payment_headers(user_namespace), timeout=TIMEOUT)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: send(), range(2)))
    assert all(response.status_code == 201 for response in responses), [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    assert len(payment_rows(api_service, user_namespace)) == 1


@pytest.mark.parametrize("amount", [0, -1, 1000001, 1.5, True, "100", None])
def test_invalid_amount_does_not_create_payment(api_base_url, user_namespace, bound_card_user, api_service, amount):
    response = send_payment(f"{api_base_url}/payments", json=pay_body(bound_card_user, amount),
                             headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert response.status_code == 422, response.text
    assert payment_rows(api_service, user_namespace) == []


@pytest.mark.parametrize("missing", ["user_id", "card_id", "amount_cent"])
def test_missing_payment_field(api_base_url, user_namespace, bound_card_user, api_service, missing):
    body = pay_body(bound_card_user)
    del body[missing]
    response = send_payment(f"{api_base_url}/payments", json=body,
                             headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert response.status_code == 422, response.text
    assert payment_rows(api_service, user_namespace) == []


@pytest.mark.parametrize("amount", [1, 1000000])
def test_payment_amount_boundaries(api_base_url, user_namespace, bound_card_user, api_service, amount):
    response = send_payment(f"{api_base_url}/payments", json=pay_body(bound_card_user, amount),
                             headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert response.status_code == 201, response.text
    assert response.json()["amount_cent"] == amount
    assert payment_rows(api_service, user_namespace)[0]["amount_cent"] == amount


@pytest.mark.parametrize("case", ["missing-namespace", "missing-key", "invalid-key"])
def test_payment_requires_valid_headers(api_base_url, user_namespace, bound_card_user, api_service, case):
    headers = payment_headers(user_namespace)
    if case == "missing-namespace":
        del headers["X-Test-Run-ID"]
    elif case == "missing-key":
        del headers["Idempotency-Key"]
    else:
        headers["Idempotency-Key"] = "not-demo"
    response = send_payment(f"{api_base_url}/payments", json=pay_body(bound_card_user),
                             headers=headers, timeout=TIMEOUT)
    assert response.status_code == 422, response.text
    assert payment_rows(api_service, user_namespace) == []


@pytest.mark.parametrize("state", ["new", "verified-no-card", "unknown-user"])
def test_payment_user_preconditions(api_base_url, user_namespace, new_user, api_service, state):
    user_id = new_user["user_id"]
    if state == "verified-no-card":
        verified = requests.post(f"{api_base_url}/users/{user_id}/verification",
            json={"verification_name": "DEMO_PERSON_01", "identity_token": "DEMO_ID_01"},
            headers=user_namespace, timeout=TIMEOUT)
        assert verified.status_code == 200, verified.text
    if state == "unknown-user":
        user_id = "DEMO_UNKNOWN_USER"
    response = send_payment(f"{api_base_url}/payments",
        json={"user_id": user_id, "card_id": "DEMO_NO_CARD", "amount_cent": 100},
        headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert response.status_code == (404 if state == "unknown-user" else 409), response.text
    assert payment_rows(api_service, user_namespace) == []


def test_foreign_users_card_is_rejected(api_base_url, user_namespace, bound_card_user, api_service):
    other = requests.post(f"{api_base_url}/users", json={"display_name": "DEMO_OTHER"},
                          headers=user_namespace, timeout=TIMEOUT)
    assert other.status_code == 201, other.text
    user_id = other.json()["user_id"]
    verified = requests.post(f"{api_base_url}/users/{user_id}/verification",
        json={"verification_name": "DEMO_PERSON_01", "identity_token": "DEMO_ID_01"},
        headers=user_namespace, timeout=TIMEOUT)
    assert verified.status_code == 200, verified.text
    response = send_payment(f"{api_base_url}/payments",
        json={**pay_body(bound_card_user), "user_id": user_id},
        headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert response.status_code == 409, response.text
    assert payment_rows(api_service, user_namespace) == []


def test_declined_card_failure_does_not_consume_key_or_pollute_payments(api_base_url, user_namespace, bound_card_user, api_service):
    first = send_payment(f"{api_base_url}/payments", json=pay_body(bound_card_user),
                          headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert first.status_code == 201, first.text
    before = payment_rows(api_service, user_namespace)
    card = requests.post(f"{api_base_url}/users/{bound_card_user['user']['user_id']}/cards",
                         json={"card_token": "DEMO_CARD_DECLINED"}, headers=user_namespace, timeout=TIMEOUT)
    assert card.status_code == 201, card.text
    denied = send_payment(f"{api_base_url}/payments",
        json={**pay_body(bound_card_user), "card_id": card.json()["card_id"]},
        headers=payment_headers(user_namespace, "DEMO_DECLINED"), timeout=TIMEOUT)
    assert denied.status_code == 409, denied.text
    assert payment_rows(api_service, user_namespace) == before
    retry = send_payment(f"{api_base_url}/payments", json=pay_body(bound_card_user),
                          headers=payment_headers(user_namespace, "DEMO_DECLINED"), timeout=TIMEOUT)
    assert retry.status_code == 201, retry.text
    assert len(payment_rows(api_service, user_namespace)) == 2


def test_unknown_payment_returns_404(api_base_url, user_namespace):
    response = requests.get(f"{api_base_url}/payments/{uuid4()}", headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Payment not found"}


def test_other_namespace_same_key_and_failure_cleanup(api_base_url, user_namespace, bound_card_user, api_service):
    own = send_payment(f"{api_base_url}/payments", json=pay_body(bound_card_user),
                        headers=payment_headers(user_namespace), timeout=TIMEOUT)
    assert own.status_code == 201, own.text
    own_rows = payment_rows(api_service, user_namespace)
    with pytest.raises(RuntimeError, match="DEMO cleanup failure"):
        with contextmanager(namespace_fixture.__wrapped__)(api_service) as other_namespace:
            user = requests.post(f"{api_base_url}/users", json={"display_name": "DEMO_OTHER_SPACE"},
                                 headers=other_namespace, timeout=TIMEOUT)
            assert user.status_code == 201, user.text
            user_id = user.json()["user_id"]
            verified = requests.post(f"{api_base_url}/users/{user_id}/verification",
                json={"verification_name": "DEMO_PERSON_01", "identity_token": "DEMO_ID_01"},
                headers=other_namespace, timeout=TIMEOUT)
            assert verified.status_code == 200, verified.text
            card = requests.post(f"{api_base_url}/users/{user_id}/cards", json={"card_token": "DEMO_CARD_001"},
                                 headers=other_namespace, timeout=TIMEOUT)
            assert card.status_code == 201, card.text
            paid = send_payment(f"{api_base_url}/payments",
                json={"user_id": user_id, "card_id": card.json()["card_id"], "amount_cent": 100},
                headers=payment_headers(other_namespace), timeout=TIMEOUT)
            assert paid.status_code == 201, paid.text
            assert paid.json()["payment_id"] != own.json()["payment_id"]
            cross_read = requests.get(f"{api_base_url}/payments/{own.json()['payment_id']}",
                                      headers=other_namespace, timeout=TIMEOUT)
            assert cross_read.status_code == 404, cross_read.text
            cross_pay = send_payment(f"{api_base_url}/payments", json=pay_body(bound_card_user),
                headers=payment_headers(other_namespace, "DEMO_CROSS"), timeout=TIMEOUT)
            assert cross_pay.status_code == 404, cross_pay.text
            raise RuntimeError("DEMO cleanup failure")
    assert payment_rows(api_service, other_namespace) == []
    assert payment_rows(api_service, user_namespace) == own_rows
