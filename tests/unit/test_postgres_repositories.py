from unittest.mock import MagicMock
import pytest

from app.config import DEFAULT_TIMEZONE
from app.database.database import Database
from app.database.postgres import (
    PostgresConnectionManager,
    PostgresReminderRepository,
    PostgresSystemSettingsRepository,
    PostgresUserRepository,
)


@pytest.fixture
def mock_pg_cm():
    """Фикстура мока PostgresConnectionManager."""
    cm = MagicMock(spec=PostgresConnectionManager)
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    cm.get_connection.return_value.__enter__.return_value = mock_conn
    return cm, mock_cursor


class TestPostgresUserRepository:
    def test_get_user_timezone_default(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        cur.fetchone.return_value = None
        repo = PostgresUserRepository(cm)

        tz = repo.get_user_timezone(123)
        assert tz == DEFAULT_TIMEZONE
        cur.execute.assert_called_once()

    def test_get_user_timezone_custom(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        cur.fetchone.return_value = {"timezone": "Asia/Almaty"}
        repo = PostgresUserRepository(cm)

        tz = repo.get_user_timezone(123)
        assert tz == "Asia/Almaty"

    def test_has_user_timezone(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        cur.fetchone.return_value = {"?column?": 1}
        repo = PostgresUserRepository(cm)

        assert repo.has_user_timezone(123) is True

    def test_set_user_timezone(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        repo = PostgresUserRepository(cm)

        repo.set_user_timezone(123, "Europe/Samara")
        cur.execute.assert_called_once()
        query = cur.execute.call_args[0][0]
        assert "ON CONFLICT (user_id) DO UPDATE" in query

    def test_get_all_user_ids(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        cur.fetchall.return_value = [{"user_id": 10}, {"user_id": 20}]
        repo = PostgresUserRepository(cm)

        uids = repo.get_all_user_ids()
        assert uids == [10, 20]


class TestPostgresReminderRepository:
    def test_add_reminder(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        cur.fetchone.return_value = {"id": 42}
        repo = PostgresReminderRepository(cm)

        r_id = repo.add_reminder(
            user_id=100,
            text="Выпить воды",
            reminder_type="recurring",
            interval_minutes=30,
        )
        assert r_id == 42
        query = cur.execute.call_args[0][0]
        assert "RETURNING id" in query

    def test_get_reminder(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        cur.fetchone.return_value = {"id": 1, "text": "Test", "user_id": 10}
        repo = PostgresReminderRepository(cm)

        rem = repo.get_reminder(1)
        assert rem["id"] == 1
        assert rem["text"] == "Test"

    def test_toggle_active(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        cur.fetchone.return_value = {"is_active": 1}
        repo = PostgresReminderRepository(cm)

        res = repo.toggle_active(1, 10)
        assert res is False
        assert cur.execute.call_count == 2

    def test_delete_reminder(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        cur.rowcount = 1
        repo = PostgresReminderRepository(cm)

        assert repo.delete_reminder(1, 10) is True

    def test_mark_completed_today(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        repo = PostgresReminderRepository(cm)

        repo.mark_completed_today(1, "2026-09-29")
        cur.execute.assert_called_once()
        assert "last_completed_date = %s" in cur.execute.call_args[0][0]

    def test_mark_completed_permanently(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        repo = PostgresReminderRepository(cm)

        repo.mark_completed_permanently(1)
        cur.execute.assert_called_once()
        assert "is_completed = 1" in cur.execute.call_args[0][0]

    def test_update_last_reminded(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        repo = PostgresReminderRepository(cm)

        repo.update_last_reminded(1, "2026-09-29T18:00:00")
        cur.execute.assert_called_once()
        assert "last_reminded_at = %s" in cur.execute.call_args[0][0]


class TestPostgresSystemSettingsRepository:
    def test_get_and_set_setting(self, mock_pg_cm):
        cm, cur = mock_pg_cm
        cur.fetchone.return_value = {"value": "v1.2.3"}
        repo = PostgresSystemSettingsRepository(cm)

        val = repo.get_setting("deploy_version")
        assert val == "v1.2.3"

        repo.set_setting("deploy_version", "v1.2.4")
        assert "ON CONFLICT (key) DO UPDATE" in cur.execute.call_args[0][0]


class TestDatabaseFacadeSelection:
    def test_database_sqlite_fallback(self, tmp_path):
        db_file = str(tmp_path / "test_fallback.db")
        db = Database(db_path=db_file, database_url="")
        assert db.users.__class__.__name__ == "SqliteUserRepository"
        assert db.reminders.__class__.__name__ == "SqliteReminderRepository"
        assert db.system.__class__.__name__ == "SqliteSystemSettingsRepository"
