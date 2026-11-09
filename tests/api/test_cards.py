from contextlib import closing, contextmanager
import sqlite3
from uuid import uuid4

import pytest
import requests
from conftest import user_namespace as namespace_fixture

TIMEOUT = (2, 3)
CARD = {"card_token": "DEMO_CARD_001"}


def card_rows(api_service, user_id):
    with closing(sqlite3.connect(api_service['database_path'])) as connection:
        return connection.execute('SELECT card_id, user_id, test_run_id, card_token, status FROM cards WHERE user_id = ?',
                                  (user_id,)).fetchall()


def test_bind_and_read_card(api_base_url, user_namespace, verified_user, api_service):
    user_id = verified_user['user_id']
    url = f"{api_base_url}/users/{user_id}/cards"
    response = requests.post(url, json=CARD, headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 201, response.text
    card = response.json()
    assert card['user_id'] == user_id
    assert card['card_token'] == CARD['card_token']
    assert card['status'] == 'BOUND'
    read = requests.get(url, headers=user_namespace, timeout=TIMEOUT)
    assert read.status_code == 200, read.text
    assert read.json() == [card]
    assert card_rows(api_service, user_id) == [(card['card_id'], user_id, user_namespace['X-Test-Run-ID'], CARD['card_token'], 'BOUND')]


def test_unverified_user_cannot_bind(api_base_url, user_namespace, new_user, api_service):
    url = f"{api_base_url}/users/{new_user['user_id']}/cards"
    response = requests.post(url, json=CARD, headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 409, response.text
    assert response.json()['detail'] == 'User must be verified'
    assert card_rows(api_service, new_user['user_id']) == []
    read = requests.get(f"{api_base_url}/users/{new_user['user_id']}", headers=user_namespace, timeout=TIMEOUT)
    assert read.status_code == 200, read.text
    assert read.json() == new_user


def test_duplicate_card_returns_409(api_base_url, user_namespace, verified_user, api_service):
    url = f"{api_base_url}/users/{verified_user['user_id']}/cards"
    first = requests.post(url, json=CARD, headers=user_namespace, timeout=TIMEOUT)
    assert first.status_code == 201, first.text
    before = card_rows(api_service, verified_user['user_id'])
    second = requests.post(url, json=CARD, headers=user_namespace, timeout=TIMEOUT)
    assert second.status_code == 409, second.text
    assert card_rows(api_service, verified_user['user_id']) == before


@pytest.mark.parametrize('payload', [{}, {'card_token': 'not-a-demo-card'}, {'card_token': 123},
                                    {'card_token': None}, {**CARD, 'cvv': 'DEMO_ONLY'}])
def test_invalid_card(api_base_url, user_namespace, verified_user, api_service, payload):
    response = requests.post(f"{api_base_url}/users/{verified_user['user_id']}/cards", json=payload,
                             headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 422, response.text
    assert card_rows(api_service, verified_user['user_id']) == []


@pytest.mark.parametrize('kind', ['unknown-user', 'other-namespace', 'missing-header'])
def test_card_scope(api_base_url, user_namespace, verified_user, api_service, kind):
    user_id = str(uuid4()) if kind == 'unknown-user' else verified_user['user_id']
    headers = {} if kind == 'missing-header' else ({'X-Test-Run-ID':uuid4().hex} if kind == 'other-namespace' else user_namespace)
    response = requests.post(f"{api_base_url}/users/{user_id}/cards", json=CARD, headers=headers, timeout=TIMEOUT)
    assert response.status_code == (422 if kind == 'missing-header' else 404), response.text
    assert card_rows(api_service, verified_user['user_id']) == []


def test_other_namespace_cannot_read_bound_card(api_base_url, user_namespace, verified_user):
    url = f"{api_base_url}/users/{verified_user['user_id']}/cards"
    created = requests.post(url, json=CARD, headers=user_namespace, timeout=TIMEOUT)
    assert created.status_code == 201, created.text
    other = requests.get(url, headers={'X-Test-Run-ID':uuid4().hex}, timeout=TIMEOUT)
    assert other.status_code == 404, other.text
    own = requests.get(url, headers=user_namespace, timeout=TIMEOUT)
    assert own.status_code == 200, own.text
    assert own.json() == [created.json()]


def test_cleanup_on_failure_preserves_other_namespace(api_service, api_base_url, user_namespace, verified_user):
    other_id = verified_user['user_id']
    created = requests.post(f"{api_base_url}/users/{other_id}/cards", json=CARD, headers=user_namespace, timeout=TIMEOUT)
    assert created.status_code == 201, created.text
    # 调用同一 fixture 的底层生成器，模拟测试体异常；验证实际 finally 清理和级联删除。
    with pytest.raises(RuntimeError, match='simulated test failure'):
        with contextmanager(namespace_fixture.__wrapped__)(api_service) as headers:
            response = requests.post(f"{api_base_url}/users", json={'display_name':'DEMO_CLEANUP'}, headers=headers, timeout=TIMEOUT)
            assert response.status_code == 201, response.text
            user_id = response.json()['user_id']
            response = requests.post(f"{api_base_url}/users/{user_id}/verification",
                                     json={'verification_name':'DEMO_PERSON_01','identity_token':'DEMO_ID_01'}, headers=headers, timeout=TIMEOUT)
            assert response.status_code == 200, response.text
            response = requests.post(f"{api_base_url}/users/{user_id}/cards", json=CARD, headers=headers, timeout=TIMEOUT)
            assert response.status_code == 201, response.text
            raise RuntimeError('simulated test failure')
    assert card_rows(api_service, user_id) == []
    with closing(sqlite3.connect(api_service['database_path'])) as connection:
        assert connection.execute('SELECT * FROM users WHERE user_id=?', (user_id,)).fetchone() is None
    assert len(card_rows(api_service, other_id)) == 1


@pytest.mark.parametrize('api_service', ['legacy'], indirect=True)
def test_migrated_legacy_user_via_http(api_service, api_base_url, legacy_namespace):
    headers = legacy_namespace
    url = f"{api_base_url}/users/legacy-http"
    before = requests.get(url, headers=headers, timeout=TIMEOUT)
    assert before.status_code == 200, before.text
    assert before.json() == {'user_id':'legacy-http','display_name':'DEMO_LEGACY','status':'NEW'}
    verified = requests.post(url + '/verification', json={'verification_name':'DEMO_PERSON_01','identity_token':'DEMO_ID_01'}, headers=headers, timeout=TIMEOUT)
    assert verified.status_code == 200, verified.text
    card = requests.post(url + '/cards', json=CARD, headers=headers, timeout=TIMEOUT)
    assert card.status_code == 201, card.text
    read = requests.get(url + '/cards', headers=headers, timeout=TIMEOUT)
    assert read.status_code == 200, read.text
    assert read.json() == [card.json()]


@pytest.fixture
def legacy_namespace(api_service):
    try:
        yield {'X-Test-Run-ID':'legacy-space'}
    finally:
        # 迁移验证断言失败时也清理，仅操作预置的旧用户；不删除数据库/备份。
        with closing(sqlite3.connect(api_service['database_path'])) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            with connection:
                connection.execute("DELETE FROM users WHERE user_id='legacy-http' AND test_run_id='legacy-space'")
            assert connection.execute("SELECT COUNT(*) FROM cards WHERE test_run_id='legacy-space'").fetchone()[0] == 0
