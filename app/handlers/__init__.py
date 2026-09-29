from typing import Optional

from aiogram import Dispatcher, Router

from app.handlers.common import fallback_expired_callback, router as common_router
from app.handlers.reminders import router as reminders_router
from app.handlers.timezone import router as timezone_router
from app.handlers.wizard import router as wizard_router
from app.middlewares import DependencyInjectionMiddleware


def setup_handlers(
    dp: Dispatcher,
    di_middleware: Optional[DependencyInjectionMiddleware] = None,
):
    """Подключает middleware и роутеры к диспетчеру в строгом порядке приоритета."""
    # 0. Внедрение зависимостей (DIP)
    di = di_middleware or DependencyInjectionMiddleware()
    dp.message.outer_middleware(di)
    dp.callback_query.outer_middleware(di)

    # 1. Подключение роутеров в строгом порядке приоритета
    routers = [wizard_router, timezone_router, reminders_router, common_router]
    for r in routers:
        r._parent_router = None
        dp.include_router(r)

    # 2. Роутер перехвата устаревших кнопок от предыдущих версий (СТРОГО ПОСЛЕДНИЙ)
    fallback_router = Router(name="fallback")
    fallback_router.callback_query.register(fallback_expired_callback)
    dp.include_router(fallback_router)

