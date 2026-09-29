from aiogram import Dispatcher, Router

from app.handlers.common import fallback_expired_callback, router as common_router
from app.handlers.reminders import router as reminders_router
from app.handlers.timezone import router as timezone_router
from app.handlers.wizard import router as wizard_router


def setup_handlers(dp: Dispatcher):
    """Подключает все роутеры к диспетчеру в правильном порядке приоритета."""
    root_router = Router(name="root")

    # Специфичные обработчики мастера и функций
    root_router.include_router(wizard_router)
    root_router.include_router(timezone_router)
    root_router.include_router(reminders_router)
    root_router.include_router(common_router)

    # В самом конце регистрируем fallback для устаревших кнопок после деплоя
    root_router.callback_query.register(fallback_expired_callback)

    dp.include_router(root_router)
