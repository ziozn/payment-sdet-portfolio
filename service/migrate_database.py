"""显式离线迁移：仅支持已知 Day 3 users 表；先备份，事务内保留全部用户。"""
import argparse
from pathlib import Path
from uuid import uuid4

from service.database import LEGACY_USERS_SQL, USERS_SQL, connect, normalized_sql


def migrate_database(database_path: Path) -> Path:
    if not database_path.is_file():
        raise ValueError("Database must already exist; migration never creates a source database")
    with connect(database_path) as connection:
        tables = connection.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'").fetchall()
        if len(tables) != 1 or tables[0]['name'] != 'users' or normalized_sql(tables[0]['sql']) != normalized_sql(LEGACY_USERS_SQL):
            raise ValueError("Only the exact Day 3 users-only schema is supported; source unchanged")
        extras = connection.execute("SELECT name FROM sqlite_master WHERE type IN ('trigger','view') "
                                    "OR (type='index' AND sql IS NOT NULL)").fetchall()
        if extras:
            raise ValueError("Unexpected indexes/triggers/views; source unchanged")
        backup_path = database_path.with_name(database_path.name + f".backup-{uuid4().hex}.db")
        with connect(backup_path) as backup:
            connection.backup(backup)
        connection.execute("BEGIN IMMEDIATE")
        before = [tuple(row) for row in connection.execute("SELECT * FROM users ORDER BY user_id")]
        connection.execute(USERS_SQL.replace("CREATE TABLE users", "CREATE TABLE users_v2", 1))
        connection.execute("INSERT INTO users_v2 (user_id, test_run_id, display_name, status) "
                           "SELECT user_id, test_run_id, display_name, status FROM users")
        after = [tuple(row) for row in connection.execute(
            "SELECT user_id, test_run_id, display_name, status FROM users_v2 ORDER BY user_id")]
        if after != before:
            raise RuntimeError("Migration data mismatch; transaction rolled back")
        connection.execute("DROP TABLE users")  # 全量复制并核对后，事务内替换旧表
        connection.execute("ALTER TABLE users_v2 RENAME TO users")
    return backup_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    print("Backup:", migrate_database(args.database.resolve()))
