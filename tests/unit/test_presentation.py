from datetime import datetime, timezone
import pytest

from app.services.presentation import (
    OneTimeReminderFormatter,
    RecurringReminderFormatter,
    ReminderPresenter,
)


class TestPresentationService:
    def setup_method(self):
        self.presenter = ReminderPresenter()
        self.now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)

    def test_recurring_formatter_schedule(self):
        formatter = RecurringReminderFormatter()
        # 1 раз в день
        rem_once = {
            "reminder_type": "recurring",
            "interval_minutes": 0,
            "start_time": "10:00",
        }
        res_once = formatter.format_schedule(rem_once, self.now)
        assert "1 раз в день в 10:00" in res_once

        # С интервалом
        rem_repeat = {
            "reminder_type": "recurring",
            "interval_minutes": 30,
            "start_time": "09:00",
            "end_time": "18:00",
        }
        res_repeat = formatter.format_schedule(rem_repeat, self.now)
        assert "каждые 30 мин" in res_repeat
        assert "с 09:00 до 18:00" in res_repeat

    def test_onetime_formatter_schedule(self):
        formatter = OneTimeReminderFormatter()
        # 1 раз в точное время
        rem_once = {
            "reminder_type": "one_time",
            "interval_minutes": 0,
            "start_datetime": "2026-10-15T14:30:00+00:00",
        }
        res_once = formatter.format_schedule(rem_once, self.now)
        assert "1 раз (15.10.2026 в 14:30)" in res_once

        # С повторами
        rem_repeat = {
            "reminder_type": "one_time",
            "interval_minutes": 60,
            "start_datetime": "2026-10-15T09:00:00+00:00",
            "end_time": "21:00",
        }
        res_repeat = formatter.format_schedule(rem_repeat, self.now)
        assert "15.10.2026 (с 09:00 до 21:00)" in res_repeat
        assert "каждые 1 час" in res_repeat

    def test_presenter_render_empty_list(self):
        text, kb = self.presenter.render_list([], self.now)
        assert "У вас пока нет созданных напоминаний" in text
        assert kb is None

    def test_presenter_render_list_with_items(self):
        items = [
            {
                "id": 1,
                "text": "Тестовая задача 1",
                "reminder_type": "recurring",
                "days_of_week": "0,4",
                "interval_minutes": 0,
                "start_time": "10:00",
                "is_active": 1,
                "is_completed": 0,
                "last_completed_date": None,
            }
        ]
        text, kb = self.presenter.render_list(items, self.now)
        assert "Тестовая задача 1" in text
        assert "Пн, Пт" in text
        assert "1 раз в день в 10:00" in text
        assert kb is not None

    def test_presenter_render_card(self):
        rem = {
            "id": 10,
            "text": "Купить билеты",
            "reminder_type": "one_time",
            "start_datetime": "2026-10-15T15:00:00+00:00",
            "interval_minutes": 0,
            "is_active": 1,
            "is_completed": 0,
            "last_completed_date": None,
        }
        card_text = self.presenter.render_card(rem, self.now)
        assert "Купить билеты" in card_text
        assert "15.10.2026 в 15:00" in card_text
        assert "1 раз в определенное время" in card_text
