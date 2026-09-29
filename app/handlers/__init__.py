from aiogram import Dispatcher, Router

from app.handlers.common import fallback_expired_callback, router as common_router
from app.handlers.reminders import router as reminders_router
from app.handlers.timezone import router as timezone_router
from app.handlers.wizard import router as wizard_router


def setup_handlers(dp: Dispatcher):
    """Подключает роутеры к диспетчеру в строгом порядке приоритета."""
    # 1. Пошаговый конструктор напоминаний
    dp.include_router(wizard_router)
    # 2. Настройки часового пояса
    dp.include_router(timezone_router)
    # 3. Список и управление напоминаниями
    dp.include_router(reminders_router)
    # 4. Общие команды (/start, /help, /menu)
    dp.include_router(common_router)

    # 5. Роутер перехвата устаревших кнопок от предыдущих версий (СТРОГО ПОСЛЕДНИЙ)
    fallback_router = Router(name="fallback")
    fallback_router.callback_query.register(fallback_expired_callback)
    dp.include_router(fallback_router)

