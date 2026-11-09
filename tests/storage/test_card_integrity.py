import sqlite3
import pytest
from service.database import connect, initialize_database


def test_foreign_key_rejects_orphan_and_wrong_namespace(tmp_path):
    path = tmp_path / 'integrity.db'
    initialize_database(path)
    with connect(path) as connection:
        connection.execute("INSERT INTO users (user_id,test_run_id,display_name,status) VALUES ('u','owner','DEMO_A','NEW')")
    for user_id, space in [('missing','owner'), ('u','other')]:
        with pytest.raises(sqlite3.IntegrityError, match='FOREIGN KEY'):
            with connect(path) as connection:
                connection.execute("INSERT INTO cards VALUES ('c',?,?, 'DEMO_CARD_001','BOUND')", (user_id, space))
    with connect(path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM cards').fetchone()[0] == 0
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
