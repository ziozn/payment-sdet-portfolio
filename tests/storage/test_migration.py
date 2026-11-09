from contextlib import closing
import sqlite3

import pytest

from service.database import connect, initialize_database
import service.migrate_database as migration

# 冻结的 Day 3 原始结构，独立于新建表定义。
LEGACY_USERS_SQL = """CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status = 'NEW')
)"""
from service.migrate_database import migrate_database


@pytest.fixture
def legacy_database(tmp_path):
    path = tmp_path / 'legacy.db'
    with closing(sqlite3.connect(path)) as connection:
        with connection:
            connection.execute(LEGACY_USERS_SQL)
            connection.executemany("INSERT INTO users VALUES (?, ?, ?, ?)", [
                ('legacy-a', 'space-a', 'DEMO_A', 'NEW'), ('legacy-b', 'space-b', 'DEMO_B', 'NEW')])
    return path


def rows(path):
    with connect(path) as connection:
        return [tuple(row) for row in connection.execute(
            'SELECT user_id, test_run_id, display_name, status FROM users ORDER BY user_id')]


def test_legacy_migration_preserves_users_and_backup(legacy_database):
    before = rows(legacy_database)
    with pytest.raises(RuntimeError, match='Unsupported users schema'):
        initialize_database(legacy_database)
    assert rows(legacy_database) == before
    backup = migrate_database(legacy_database)
    assert rows(backup) == before
    assert rows(legacy_database) == before
    initialize_database(legacy_database)
    with connect(legacy_database) as connection:
        connection.execute("UPDATE users SET status='VERIFIED' WHERE user_id='legacy-a'")
    assert rows(legacy_database)[0][-1] == 'VERIFIED'
    # 备份仍保留迁移前原貌，可离线恢复到新路径检查。
    restored = legacy_database.with_name('restored.db')
    with connect(backup) as source, connect(restored) as target:
        source.backup(target)
    assert rows(restored) == before


def test_migration_rejects_unknown_schema(legacy_database):
    with connect(legacy_database) as connection:
        connection.execute('CREATE TABLE unexpected (id TEXT)')
    before = legacy_database.read_bytes()
    with pytest.raises(ValueError, match='exact Day 3'):
        migrate_database(legacy_database)
    assert legacy_database.read_bytes() == before


def test_migration_rolls_back_on_copy_failure(legacy_database, monkeypatch):
    before = rows(legacy_database)
    # 只在该测试注入目标表约束错误，验证复制异常时事务回滚，生产代码不关闭约束。
    monkeypatch.setattr(migration, 'USERS_SQL', migration.USERS_SQL.replace(
        'display_name TEXT NOT NULL', "display_name TEXT NOT NULL CHECK (display_name != 'DEMO_A')"))
    with pytest.raises(sqlite3.IntegrityError):
        migrate_database(legacy_database)
    assert rows(legacy_database) == before
    with connect(legacy_database) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='users_v2'").fetchone() is None
    backups = list(legacy_database.parent.glob('legacy.db.backup-*.db'))
    assert len(backups) == 1
    assert rows(backups[0]) == before
