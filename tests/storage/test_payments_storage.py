import sqlite3

import pytest

from service.database import USERS_SQL, connect, initialize_database


def test_payment_unique_foreign_keys_and_cascade(tmp_path):
    path = tmp_path / 'payment.db'
    initialize_database(path)
    with connect(path) as connection:
        connection.execute("INSERT INTO users (user_id,test_run_id,display_name,status) VALUES ('DEMO_U','DEMO_SPACE','DEMO_A','VERIFIED')")
        connection.execute("INSERT INTO cards VALUES ('DEMO_C','DEMO_U','DEMO_SPACE','DEMO_CARD_001','BOUND')")
        connection.execute("INSERT INTO payments VALUES ('DEMO_P','DEMO_SPACE','DEMO_KEY','DEMO_U','DEMO_C',100,'SUCCEEDED')")
    invalid = [
        ('DEMO_P2','DEMO_SPACE','DEMO_KEY','DEMO_U','DEMO_C',100,'SUCCEEDED'),
        ('DEMO_P2','DEMO_SPACE','DEMO_OTHER','DEMO_U','DEMO_MISSING',100,'SUCCEEDED'),
        ('DEMO_P2','DEMO_OTHER_SPACE','DEMO_KEY','DEMO_U','DEMO_C',100,'SUCCEEDED'),
        ('DEMO_P2','DEMO_SPACE','DEMO_OTHER','DEMO_U','DEMO_C',0,'SUCCEEDED'),
    ]
    for row in invalid:
        with pytest.raises(sqlite3.IntegrityError):
            with connect(path) as connection:
                connection.execute('INSERT INTO payments VALUES (?,?,?,?,?,?,?)', row)
    with connect(path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM payments').fetchone()[0] == 1
        connection.execute("DELETE FROM users WHERE user_id='DEMO_U'")
    with connect(path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM payments').fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM cards').fetchone()[0] == 0
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []


def test_day4_populated_database_upgrade_preserves_users_and_cards(tmp_path):
    path = tmp_path / 'day4.db'
    with connect(path) as connection:
        connection.execute(USERS_SQL)
        connection.execute("""CREATE TABLE cards (
            card_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, test_run_id TEXT NOT NULL,
            card_token TEXT NOT NULL, status TEXT NOT NULL CHECK (status='BOUND'),
            UNIQUE(user_id,card_token),
            FOREIGN KEY(user_id,test_run_id) REFERENCES users(user_id,test_run_id) ON DELETE CASCADE)""")
        connection.execute("INSERT INTO users (user_id,test_run_id,display_name,status) VALUES ('DEMO_U','DEMO_SPACE','DEMO_A','VERIFIED')")
        connection.execute("INSERT INTO cards VALUES ('DEMO_C','DEMO_U','DEMO_SPACE','DEMO_CARD_001','BOUND')")
        users_before = [tuple(row) for row in connection.execute('SELECT * FROM users')]
        cards_before = [tuple(row) for row in connection.execute('SELECT * FROM cards')]
    initialize_database(path)
    initialize_database(path)
    with connect(path) as connection:
        assert [tuple(row) for row in connection.execute('SELECT * FROM users')] == users_before
        assert [tuple(row) for row in connection.execute('SELECT * FROM cards')] == cards_before
        connection.execute("INSERT INTO payments VALUES ('DEMO_P','DEMO_SPACE','DEMO_KEY','DEMO_U','DEMO_C',100,'SUCCEEDED')")
    with connect(path) as connection:
        assert connection.execute("SELECT idempotency_key FROM payments WHERE payment_id='DEMO_P'").fetchone()[0] == 'DEMO_KEY'
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
