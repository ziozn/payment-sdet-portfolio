from contextlib import closing
import sqlite3
from uuid import uuid4

import pytest
import requests

TIMEOUT = (2, 3)
IDENTITY = {"verification_name": "DEMO_PERSON_01", "identity_token": "DEMO_ID_01"}


def stored_user(api_service, user_id):
    with closing(sqlite3.connect(api_service['database_path'])) as connection:
        connection.row_factory = sqlite3.Row
        return dict(connection.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone())


def test_verification_success(api_base_url, user_namespace, new_user, api_service):
    response = requests.post(f"{api_base_url}/users/{new_user['user_id']}/verification",
                             json=IDENTITY, headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 200, response.text
    assert response.json() == {**new_user, 'status': 'VERIFIED'}
    read = requests.get(f"{api_base_url}/users/{new_user['user_id']}", headers=user_namespace, timeout=TIMEOUT)
    assert read.status_code == 200, read.text
    assert read.json() == response.json()
    stored = stored_user(api_service, new_user['user_id'])
    assert stored['status'] == 'VERIFIED'
    assert stored['verification_name'] == IDENTITY['verification_name']
    assert stored['identity_token'] == IDENTITY['identity_token']


def test_repeat_verification_is_idempotent(api_base_url, user_namespace, new_user, api_service):
    url = f"{api_base_url}/users/{new_user['user_id']}/verification"
    first = requests.post(url, json=IDENTITY, headers=user_namespace, timeout=TIMEOUT)
    assert first.status_code == 200, first.text
    before = stored_user(api_service, new_user['user_id'])
    second = requests.post(url, json=IDENTITY, headers=user_namespace, timeout=TIMEOUT)
    assert second.status_code == 200, second.text
    assert second.json() == first.json()
    assert stored_user(api_service, new_user['user_id']) == before


@pytest.mark.parametrize('initial_verified', [False, True])
def test_rejected_identity_does_not_change_user(api_base_url, user_namespace, new_user, api_service, initial_verified):
    url = f"{api_base_url}/users/{new_user['user_id']}/verification"
    if initial_verified:
        response = requests.post(url, json=IDENTITY, headers=user_namespace, timeout=TIMEOUT)
        assert response.status_code == 200, response.text
    before = stored_user(api_service, new_user['user_id'])
    response = requests.post(url, json={**IDENTITY, 'identity_token': 'DEMO_ID_02'}, headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 409, response.text
    assert stored_user(api_service, new_user['user_id']) == before


@pytest.mark.parametrize('payload', [{}, {**IDENTITY, 'identity_token': 123},
    {**IDENTITY, 'identity_token': 'not-an-id'}, {**IDENTITY, 'verification_name': ''},
    {**IDENTITY, 'extra': True}])
def test_invalid_verification(api_base_url, user_namespace, new_user, api_service, payload):
    before = stored_user(api_service, new_user['user_id'])
    response = requests.post(f"{api_base_url}/users/{new_user['user_id']}/verification",
                             json=payload, headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 422, response.text
    assert stored_user(api_service, new_user['user_id']) == before


@pytest.mark.parametrize('kind', ['missing-header', 'other-namespace', 'unknown-user'])
def test_verification_scope(api_base_url, user_namespace, new_user, api_service, kind):
    user_id = str(uuid4()) if kind == 'unknown-user' else new_user['user_id']
    headers = {} if kind == 'missing-header' else ({'X-Test-Run-ID': uuid4().hex} if kind == 'other-namespace' else user_namespace)
    before = stored_user(api_service, new_user['user_id'])
    response = requests.post(f"{api_base_url}/users/{user_id}/verification", json=IDENTITY, headers=headers, timeout=TIMEOUT)
    assert response.status_code == (422 if kind == 'missing-header' else 404), response.text
    assert stored_user(api_service, new_user['user_id']) == before


def test_verification_updates_only_target(api_base_url, user_namespace, new_user, api_service):
    second = requests.post(f"{api_base_url}/users", json={'display_name':'DEMO_SECOND'},
                           headers=user_namespace, timeout=TIMEOUT)
    assert second.status_code == 201, second.text
    before = stored_user(api_service, second.json()['user_id'])
    response = requests.post(f"{api_base_url}/users/{new_user['user_id']}/verification",
                             json=IDENTITY, headers=user_namespace, timeout=TIMEOUT)
    assert response.status_code == 200, response.text
    assert stored_user(api_service, new_user['user_id'])['status'] == 'VERIFIED'
    assert stored_user(api_service, second.json()['user_id']) == before
    assert before['status'] == 'NEW'
