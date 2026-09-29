import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.services.evaluator import ReminderEvaluator
from app.services.scheduler import ReminderSchedulerService


@pytest.mark.asyncio
async def test_scheduler_delivers_due_reminders(temp_db, mock_notifier):
    user_repo = temp_db["user_repo"]
    reminder_repo = temp_db["reminder_repo"]
    evaluator = ReminderEvaluator()

    user_id = 777
    user_repo.set_user_timezone(user_id, "UTC")

    # Создаём напоминание: одноразовое, время старта уже наступило
    rem_id = reminder_repo.add_reminder(
        user_id=user_id,
        text="Принять витамины",
        reminder_type="one_time",
        interval_minutes=60,
        start_datetime="2020-01-01T10:00:00+00:00",
    )

    scheduler = ReminderSchedulerService(
        reminder_repo=reminder_repo,
        user_repo=user_repo,
        evaluator=evaluator,
        notifier=mock_notifier,
    )

    # 1. Запуск доставки
    delivered = await scheduler.check_and_deliver()
    assert delivered == 1
    assert mock_notifier.send_reminder.called
    sent_arg = mock_notifier.send_reminder.call_args[0][0]
    assert sent_arg["id"] == rem_id
    assert sent_arg["text"] == "Принять витамины"

    # Проверяем, что в БД обновилось last_reminded_at
    updated_rem = reminder_repo.get_reminder(rem_id)
    assert updated_rem["last_reminded_at"] is not None

    # 2. Повторный запуск сразу же - должно быть 0, т.к. интервал 60 минут еще не прошел
    delivered_again = await scheduler.check_and_deliver()
    assert delivered_again == 0


@pytest.mark.asyncio
async def test_scheduler_ignores_inactive_or_completed(temp_db, mock_notifier):
    user_repo = temp_db["user_repo"]
    reminder_repo = temp_db["reminder_repo"]
    evaluator = ReminderEvaluator()

    user_id = 888
    user_repo.set_user_timezone(user_id, "UTC")

    rem_id = reminder_repo.add_reminder(
        user_id=user_id,
        text="Сдать отчет",
        reminder_type="one_time",
        start_datetime="2020-01-01T10:00:00+00:00",
    )
    # Помечаем выполненным
    reminder_repo.mark_completed_permanently(rem_id)

    scheduler = ReminderSchedulerService(
        reminder_repo=reminder_repo,
        user_repo=user_repo,
        evaluator=evaluator,
        notifier=mock_notifier,
    )

    delivered = await scheduler.check_and_deliver()
    assert delivered == 0
    assert not mock_notifier.send_reminder.called


@pytest.mark.asyncio
async def test_scheduler_resilience_on_notifier_error(temp_db, mock_notifier):
    user_repo = temp_db["user_repo"]
    reminder_repo = temp_db["reminder_repo"]
    evaluator = ReminderEvaluator()

    user_id = 999
    user_repo.set_user_timezone(user_id, "UTC")

    rem_id = reminder_repo.add_reminder(
        user_id=user_id,
        text="Ошибка отправки",
        reminder_type="one_time",
        start_datetime="2020-01-01T10:00:00+00:00",
    )

    # Имитируем сбой отправки
    mock_notifier.send_reminder = AsyncMock(return_value=False)

    scheduler = ReminderSchedulerService(
        reminder_repo=reminder_repo,
        user_repo=user_repo,
        evaluator=evaluator,
        notifier=mock_notifier,
    )

    delivered = await scheduler.check_and_deliver()
    assert delivered == 0
    # В БД не должно быть обновлено время напоминания, чтобы попробовать снова
    rem = reminder_repo.get_reminder(rem_id)
    assert rem["last_reminded_at"] is None
