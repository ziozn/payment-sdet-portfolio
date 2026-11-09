"""SQLite 连接与建表；旧版 CHECK 约束需显式离线迁移。"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

LEGACY_USERS_SQL = """CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status = 'NEW')
)"""
USERS_SQL = """CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('NEW', 'VERIFIED')),
    verification_name TEXT,
    identity_token TEXT,
    UNIQUE (user_id, test_run_id)
)"""


def normalized_sql(sql: str) -> str:
    return ''.join(sql.split()).replace('"', '').lower()


@contextmanager
def connect(database_path: Path):
    connection = sqlite3.connect(database_path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(database_path) as connection:
        row = connection.execute("SELECT sql FROM sqlite_master WHERE name = 'users'").fetchone()
        if row is None:
            connection.execute(USERS_SQL)
        elif normalized_sql(row['sql']) != normalized_sql(USERS_SQL):
            raise RuntimeError("Unsupported users schema. Stop service, back up and run: "
                               "python -m service.migrate_database --database PATH")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                card_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                test_run_id TEXT NOT NULL,
                card_token TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status = 'BOUND'),
                UNIQUE (user_id, card_token),
                FOREIGN KEY (user_id, test_run_id) REFERENCES users (user_id, test_run_id) ON DELETE CASCADE
            )
        """)

        # 只增索引和新表，Day 4 users/cards 数据不重建、不清空。
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS cards_payment_owner ON cards (card_id, user_id, test_run_id)")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                test_run_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                user_id TEXT NOT NULL,
                card_id TEXT NOT NULL,
                amount_cent INTEGER NOT NULL CHECK (typeof(amount_cent) = 'integer' AND amount_cent BETWEEN 1 AND 1000000),
                status TEXT NOT NULL CHECK (status = 'SUCCEEDED'),
                UNIQUE (test_run_id, idempotency_key),
                FOREIGN KEY (user_id, test_run_id) REFERENCES users (user_id, test_run_id) ON DELETE CASCADE,
                FOREIGN KEY (card_id, user_id, test_run_id) REFERENCES cards (card_id, user_id, test_run_id) ON DELETE CASCADE
            )
        """)
