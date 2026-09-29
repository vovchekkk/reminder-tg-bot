from datetime import datetime, timezone, timedelta
import pytest

from app.services.evaluator import (
    OneTimeReminderStrategy,
    RecurringReminderStrategy,
    ReminderEvaluator,
)


class TestRecurringReminderStrategy:
    def setup_method(self):
        self.strategy = RecurringReminderStrategy()

    def test_days_of_week_filter(self):
        # Понедельник (weekday=0)
        monday_dt = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        assert monday_dt.weekday() == 0

        # Напоминание по Пн и Пт ("0,4")
        rem = {
            "days_of_week": "0,4",
            "interval_minutes": 60,
            "last_reminded_at": None,
            "last_completed_date": None,
        }
        assert self.strategy.should_remind(rem, monday_dt) is True

        # Вторник (weekday=1)
        tuesday_dt = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        assert self.strategy.should_remind(rem, tuesday_dt) is False

    def test_already_completed_today(self):
        now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        rem = {
            "days_of_week": "0",
            "interval_minutes": 60,
            "last_reminded_at": None,
            "last_completed_date": "2026-09-28",  # уже выполнено сегодня
        }
        assert self.strategy.should_remind(rem, now) is False

    def test_time_range_window(self):
        # Окно с 09:00 до 18:00
        rem = {
            "days_of_week": "0",
            "start_time": "09:00",
            "end_time": "18:00",
            "interval_minutes": 60,
            "last_reminded_at": None,
            "last_completed_date": None,
        }
        # В 08:30 (до начала) - False
        assert self.strategy.should_remind(rem, datetime(2026, 9, 28, 8, 30, tzinfo=timezone.utc)) is False
        # В 12:00 (внутри окна) - True
        assert self.strategy.should_remind(rem, datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)) is True
        # В 18:30 (после окончания) - False
        assert self.strategy.should_remind(rem, datetime(2026, 9, 28, 18, 30, tzinfo=timezone.utc)) is False

    def test_interval_minutes_elapsed(self):
        now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
        # Напоминание каждые 30 минут, последнее было 20 минут назад -> False
        rem_too_early = {
            "days_of_week": "0",
            "interval_minutes": 30,
            "last_reminded_at": (now - timedelta(minutes=20)).isoformat(),
            "last_completed_date": None,
        }
        assert self.strategy.should_remind(rem_too_early, now) is False

        # Последнее было 35 минут назад -> True
        rem_due = {
            "days_of_week": "0",
            "interval_minutes": 30,
            "last_reminded_at": (now - timedelta(minutes=35)).isoformat(),
            "last_completed_date": None,
        }
        assert self.strategy.should_remind(rem_due, now) is True

    def test_last_reminded_yesterday(self):
        now = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)
        # Напоминали вчера -> сегодня должно сразу сработать
        rem = {
            "days_of_week": "0",
            "interval_minutes": 60,
            "last_reminded_at": "2026-09-27T22:00:00+00:00",
            "last_completed_date": None,
        }
        assert self.strategy.should_remind(rem, now) is True


class TestOneTimeReminderStrategy:
    def setup_method(self):
        self.strategy = OneTimeReminderStrategy()

    def test_completed_onetime(self):
        now = datetime(2026, 9, 29, 15, 0, tzinfo=timezone.utc)
        rem = {
            "start_datetime": "2026-09-29T14:00:00+00:00",
            "is_completed": 1,
            "interval_minutes": 60,
        }
        assert self.strategy.should_remind(rem, now) is False

    def test_before_start_time(self):
        now = datetime(2026, 9, 29, 13, 0, tzinfo=timezone.utc)
        rem = {
            "start_datetime": "2026-09-29T14:00:00+00:00",
            "is_completed": 0,
            "interval_minutes": 60,
        }
        assert self.strategy.should_remind(rem, now) is False

    def test_after_start_time_first_trigger(self):
        now = datetime(2026, 9, 29, 14, 5, tzinfo=timezone.utc)
        rem = {
            "start_datetime": "2026-09-29T14:00:00+00:00",
            "is_completed": 0,
            "interval_minutes": 60,
            "last_reminded_at": None,
        }
        assert self.strategy.should_remind(rem, now) is True

    def test_end_time_boundary(self):
        now = datetime(2026, 9, 29, 22, 30, tzinfo=timezone.utc)
        rem = {
            "start_datetime": "2026-09-29T14:00:00+00:00",
            "end_time": "21:00",
            "is_completed": 0,
            "interval_minutes": 60,
            "last_reminded_at": None,
        }
        assert self.strategy.should_remind(rem, now) is False


class TestReminderEvaluator:
    def test_evaluator_dispatches_correctly(self):
        evaluator = ReminderEvaluator()
        now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)

        recurring_rem = {
            "reminder_type": "recurring",
            "days_of_week": "0",
            "interval_minutes": 60,
            "last_reminded_at": None,
            "last_completed_date": None,
        }
        assert evaluator.is_due(recurring_rem, now) is True

        unknown_rem = {
            "reminder_type": "custom_unknown",
        }
        assert evaluator.is_due(unknown_rem, now) is False
