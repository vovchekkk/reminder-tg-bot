from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from app.domain.interfaces import IReminderRepository, IUserRepository
from app.handlers import setup_handlers
from app.middlewares.di import DependencyInjectionMiddleware


@pytest.fixture
def e2e_setup(temp_db):
    user_repo = temp_db["user_repo"]
    reminder_repo = temp_db["reminder_repo"]
    system_repo = temp_db["system_repo"]

    bot = Bot(token="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")
    calls = []

    async def mock_call(b, method, *args, **kwargs):
        calls.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=len(calls) + 100,
                date=datetime.now(timezone.utc),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        elif isinstance(method, EditMessageText):
            return Message(
                message_id=method.message_id or 100,
                date=datetime.now(timezone.utc),
                chat=Chat(id=method.chat_id or 12345, type="private"),
                text=method.text,
            )
        return True

    bot.session = AsyncMock(side_effect=mock_call)

    dp = Dispatcher(storage=MemoryStorage())
    # Внедряем middleware с нашими тестовыми репозиториями
    di = DependencyInjectionMiddleware(
        user_repo=user_repo,
        reminder_repo=reminder_repo,
        system_repo=system_repo,
    )
    setup_handlers(dp, di_middleware=di)

    return {
        "bot": bot,
        "dp": dp,
        "user_repo": user_repo,
        "reminder_repo": reminder_repo,
        "calls": calls,
    }


def make_message_update(user_id: int, text: str, update_id: int) -> Update:
    user = User(id=user_id, is_bot=False, first_name="Tester")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=update_id,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
        text=text,
    )
    return Update(update_id=update_id, message=msg)


def make_callback_update(user_id: int, data: str, update_id: int, message_id: int = 100) -> Update:
    user = User(id=user_id, is_bot=False, first_name="Tester")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=message_id,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=user,
        text="previous text",
    )
    cb = CallbackQuery(
        id=str(update_id),
        from_user=user,
        chat_instance="ci",
        message=msg,
        data=data,
    )
    return Update(update_id=update_id, callback_query=cb)


@pytest.mark.asyncio
async def test_full_user_onboarding_and_start(e2e_setup):
    bot = e2e_setup["bot"]
    dp = e2e_setup["dp"]
    user_repo = e2e_setup["user_repo"]
    calls = e2e_setup["calls"]
    user_id = 1111

    # 1. Пользователь впервые пишет /start
    up1 = make_message_update(user_id, "/start", 1)
    await dp.feed_update(bot, up1)

    assert any(isinstance(c, SendMessage) and "выберите ваш часовой пояс" in c.text for c in calls)
    calls.clear()

    # 2. Выбор пояса Самара (+4)
    up2 = make_callback_update(user_id, "settz:Europe/Samara", 2)
    await dp.feed_update(bot, up2)

    assert user_repo.has_user_timezone(user_id) is True
    assert user_repo.get_user_timezone(user_id) == "Europe/Samara"
    assert any(isinstance(c, SendMessage) and "Часовой пояс установлен" in c.text for c in calls)
    calls.clear()

    # 3. Пользователь снова вызывает /start -> теперь показывается главное меню
    up3 = make_message_update(user_id, "/start", 3)
    await dp.feed_update(bot, up3)
    assert any(isinstance(c, SendMessage) and "Главное меню обновлено" in c.text for c in calls)


@pytest.mark.asyncio
async def test_wizard_recurring_reminder_e2e(e2e_setup):
    bot = e2e_setup["bot"]
    dp = e2e_setup["dp"]
    reminder_repo = e2e_setup["reminder_repo"]
    user_repo = e2e_setup["user_repo"]
    calls = e2e_setup["calls"]
    user_id = 2222
    user_repo.set_user_timezone(user_id, "Europe/Moscow")

    # 1. Запуск мастера через кнопку "➕ Создать напоминание"
    await dp.feed_update(bot, make_message_update(user_id, "➕ Создать напоминание", 10))
    assert any(isinstance(c, SendMessage) and "Шаг 1: Текст напоминания" in c.text for c in calls)
    calls.clear()

    # 2. Ввод текста напоминания
    await dp.feed_update(bot, make_message_update(user_id, "Сдать тест по физре", 11))
    assert any(isinstance(c, SendMessage) and "Шаг 2: Выберите тип напоминания" in c.text for c in calls)
    calls.clear()

    # 3. Выбор типа: по дням недели
    await dp.feed_update(bot, make_callback_update(user_id, "type:recurring", 12))
    assert any(isinstance(c, EditMessageText) and "Шаг 3: Выберите дни недели" in c.text for c in calls)
    calls.clear()

    # 4. Пресет: выбрать будни
    await dp.feed_update(bot, make_callback_update(user_id, "preset_days:weekdays", 13))
    calls.clear()

    # 5. Подтверждение дней
    await dp.feed_update(bot, make_callback_update(user_id, "days_confirmed", 14))
    assert any(isinstance(c, EditMessageText) and "С какого времени начинать" in c.text for c in calls)
    calls.clear()

    # 6. Выбор времени старта: С начала дня (00:00)
    await dp.feed_update(bot, make_callback_update(user_id, "starttime:00:00", 15))
    assert any(isinstance(c, EditMessageText) and "До скольки напоминать" in c.text for c in calls)
    calls.clear()

    # 7. Выбор времени окончания: До конца дня (23:59)
    await dp.feed_update(bot, make_callback_update(user_id, "endtime:23:59", 16))
    assert any(isinstance(c, EditMessageText) and "Как часто напоминать" in c.text for c in calls)
    calls.clear()

    # 8. Выбор интервала: 30 минут
    await dp.feed_update(bot, make_callback_update(user_id, "interval:30", 17))
    assert any(isinstance(c, EditMessageText) and "Напоминание успешно создано" in c.text for c in calls)

    # Проверяем, что в репозитории реально сохранилось напоминание
    user_rems = reminder_repo.get_user_reminders(user_id)
    assert len(user_rems) == 1
    rem = user_rems[0]
    assert rem["text"] == "Сдать тест по физре"
    assert rem["reminder_type"] == "recurring"
    assert rem["interval_minutes"] == 30
    assert rem["days_of_week"] == "0,1,2,3,4"
    assert rem["start_time"] == "00:00"
    assert rem["end_time"] == "23:59"
    assert rem["is_active"] == 1


@pytest.mark.asyncio
async def test_reminder_actions_lifecycle_e2e(e2e_setup):
    bot = e2e_setup["bot"]
    dp = e2e_setup["dp"]
    reminder_repo = e2e_setup["reminder_repo"]
    calls = e2e_setup["calls"]
    user_id = 3333

    rem_id = reminder_repo.add_reminder(
        user_id=user_id,
        text="Выпить лекарство",
        reminder_type="recurring",
        days_of_week="0,1,2,3,4,5,6",
        interval_minutes=60,
    )

    # 1. Тестовая отправка прямо сейчас
    await dp.feed_update(bot, make_callback_update(user_id, f"test_trigger:{rem_id}", 30))
    assert any(isinstance(c, SendMessage) and "Выпить лекарство" in c.text for c in calls)
    calls.clear()

    # 2. Нажатие на "✅ Сделано!"
    await dp.feed_update(bot, make_callback_update(user_id, f"done:{rem_id}", 31))
    assert any(isinstance(c, EditMessageText) and "Ура, вы молодец" in c.text for c in calls)
    rem = reminder_repo.get_reminder(rem_id)
    assert rem["last_completed_date"] is not None
    calls.clear()

    # 3. Пауза / Включение
    await dp.feed_update(bot, make_callback_update(user_id, f"toggle_active:{rem_id}", 32))
    assert reminder_repo.get_reminder(rem_id)["is_active"] == 0

    await dp.feed_update(bot, make_callback_update(user_id, f"toggle_active:{rem_id}", 33))
    assert reminder_repo.get_reminder(rem_id)["is_active"] == 1

    # 4. Удаление напоминания
    await dp.feed_update(bot, make_callback_update(user_id, f"delete_rem:{rem_id}", 34))
    assert reminder_repo.get_reminder(rem_id) is None


@pytest.mark.asyncio
async def test_expired_button_fallback_e2e(e2e_setup):
    bot = e2e_setup["bot"]
    dp = e2e_setup["dp"]
    calls = e2e_setup["calls"]
    user_id = 4444

    # Нажатие на неизвестную/устаревшую кнопку от старой версии
    await dp.feed_update(bot, make_callback_update(user_id, "expired_legacy_action:999", 50))

    # Должен сработать fallback alert с текстом об устаревшей версии
    answer_calls = [c for c in calls if isinstance(c, AnswerCallbackQuery)]
    assert len(answer_calls) > 0
    assert "Эта версия бота устарела" in answer_calls[0].text

    # Клавиатура устаревшего сообщения должна быть очищена (reply_markup=None)
    edit_markup_calls = [c for c in calls if isinstance(c, EditMessageReplyMarkup)]
    assert len(edit_markup_calls) > 0
    assert edit_markup_calls[0].reply_markup is None
