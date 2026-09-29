from unittest.mock import MagicMock
import pytest

from app.domain.interfaces import IReminderRepository, IUserRepository
from app.services.reminder_service import ReminderService


class TestReminderService:
    def test_create_reminder_delegation(self):
        repo = MagicMock(spec=IReminderRepository)
        repo.add_reminder.return_value = 101

        service = ReminderService(reminder_repo=repo)
        wizard_data = {
            "text": "Позвонить врачу",
            "reminder_type": "recurring",
            "days_of_week": "0,1,2",
            "start_time": "10:00",
            "end_time": "18:00",
            "start_datetime": None,
        }
        res = service.create_reminder_from_wizard(user_id=123, data=wizard_data, interval_minutes=60)
        assert res == 101
        repo.add_reminder.assert_called_once_with(
            user_id=123,
            text="Позвонить врачу",
            reminder_type="recurring",
            interval_minutes=60,
            days_of_week="0,1,2",
            start_time="10:00",
            end_time="18:00",
            start_datetime=None,
        )

    def test_mark_done_recurring_vs_permanent(self):
        repo = MagicMock(spec=IReminderRepository)
        service = ReminderService(reminder_repo=repo)

        # Recurring
        rem_rec = {"id": 1, "reminder_type": "recurring"}
        status_rec = service.mark_done(rem_rec, "2026-09-29")
        assert status_rec == "today"
        repo.mark_completed_today.assert_called_once_with(1, "2026-09-29")

        # One-time
        rem_one = {"id": 2, "reminder_type": "one_time"}
        status_one = service.mark_done(rem_one, "2026-09-29")
        assert status_one == "permanent"
        repo.mark_completed_permanently.assert_called_once_with(2)
