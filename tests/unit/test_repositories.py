import pytest

from app.config import DEFAULT_TIMEZONE


class TestSqliteUserRepository:
    def test_default_timezone(self, temp_db):
        user_repo = temp_db["user_repo"]
        user_id = 99999
        assert user_repo.has_user_timezone(user_id) is False
        assert user_repo.get_user_timezone(user_id) == DEFAULT_TIMEZONE

    def test_set_and_get_timezone(self, temp_db):
        user_repo = temp_db["user_repo"]
        user_id = 12345
        user_repo.set_user_timezone(user_id, "Asia/Yekaterinburg")
        assert user_repo.has_user_timezone(user_id) is True
        assert user_repo.get_user_timezone(user_id) == "Asia/Yekaterinburg"

    def test_get_all_user_ids(self, temp_db):
        user_repo = temp_db["user_repo"]
        reminder_repo = temp_db["reminder_repo"]

        user_repo.set_user_timezone(101, "Europe/Moscow")
        user_repo.set_user_timezone(102, "+5")
        reminder_repo.add_reminder(user_id=103, text="Test", reminder_type="recurring")

        uids = user_repo.get_all_user_ids()
        assert set(uids) == {101, 102, 103}


class TestSqliteReminderRepository:
    def test_add_and_get_reminder(self, temp_db):
        repo = temp_db["reminder_repo"]
        rem_id = repo.add_reminder(
            user_id=555,
            text="Купить молока",
            reminder_type="recurring",
            interval_minutes=30,
            days_of_week="0,4",
            start_time="09:00",
            end_time="21:00",
        )
        assert rem_id > 0

        rem = repo.get_reminder(rem_id)
        assert rem is not None
        assert rem["id"] == rem_id
        assert rem["user_id"] == 555
        assert rem["text"] == "Купить молока"
        assert rem["reminder_type"] == "recurring"
        assert rem["interval_minutes"] == 30
        assert rem["is_active"] == 1
        assert rem["is_completed"] == 0

    def test_user_reminders_and_active_list(self, temp_db):
        repo = temp_db["reminder_repo"]
        r1 = repo.add_reminder(user_id=1, text="R1", reminder_type="recurring")
        r2 = repo.add_reminder(user_id=1, text="R2", reminder_type="one_time")
        r3 = repo.add_reminder(user_id=2, text="R3", reminder_type="one_time")

        user1_rems = repo.get_user_reminders(1)
        assert len(user1_rems) == 2
        assert {r["id"] for r in user1_rems} == {r1, r2}

        active = repo.get_active_reminders()
        assert len(active) == 3

    def test_toggle_active(self, temp_db):
        repo = temp_db["reminder_repo"]
        r_id = repo.add_reminder(user_id=1, text="Test", reminder_type="recurring")

        # 1 -> 0 (pause)
        status1 = repo.toggle_active(r_id, user_id=1)
        assert status1 is False
        assert repo.get_reminder(r_id)["is_active"] == 0

        # 0 -> 1 (resume)
        status2 = repo.toggle_active(r_id, user_id=1)
        assert status2 is True
        assert repo.get_reminder(r_id)["is_active"] == 1

        # Non-existent or wrong user
        assert repo.toggle_active(9999, user_id=1) is None
        assert repo.toggle_active(r_id, user_id=9999) is None

    def test_completion_methods(self, temp_db):
        repo = temp_db["reminder_repo"]
        r_id = repo.add_reminder(user_id=1, text="Test", reminder_type="recurring")

        # Mark completed today
        repo.mark_completed_today(r_id, "2026-09-29")
        assert repo.get_reminder(r_id)["last_completed_date"] == "2026-09-29"

        # Mark completed permanently
        repo.mark_completed_permanently(r_id)
        rem = repo.get_reminder(r_id)
        assert rem["is_completed"] == 1
        assert rem["is_active"] == 0

    def test_update_last_reminded(self, temp_db):
        repo = temp_db["reminder_repo"]
        r_id = repo.add_reminder(user_id=1, text="Test", reminder_type="recurring")
        repo.update_last_reminded(r_id, "2026-09-29T12:00:00")
        assert repo.get_reminder(r_id)["last_reminded_at"] == "2026-09-29T12:00:00"

    def test_delete_reminder(self, temp_db):
        repo = temp_db["reminder_repo"]
        r_id = repo.add_reminder(user_id=1, text="To delete", reminder_type="recurring")
        # Wrong user cannot delete
        assert repo.delete_reminder(r_id, user_id=2) is False
        assert repo.get_reminder(r_id) is not None

        # Owner can delete
        assert repo.delete_reminder(r_id, user_id=1) is True
        assert repo.get_reminder(r_id) is None


class TestSqliteSystemSettingsRepository:
    def test_get_and_set_setting(self, temp_db):
        repo = temp_db["system_repo"]
        assert repo.get_setting("non_existent") is None

        repo.set_setting("version", "2.0.0")
        assert repo.get_setting("version") == "2.0.0"

        # Overwrite
        repo.set_setting("version", "2.1.0")
        assert repo.get_setting("version") == "2.1.0"
