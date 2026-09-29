from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.database.database import db
from app.domain.interfaces import (
    IReminderRepository,
    ISystemSettingsRepository,
    IUserRepository,
)
from app.services.evaluator import ReminderEvaluator


class DependencyInjectionMiddleware(BaseMiddleware):
    """
    Внедрение зависимостей в обработчики aiogram (Dependency Inversion Principle).
    Позволяет хендлерам запрашивать интерфейсы репозиториев напрямую в аргументах.
    """

    def __init__(
        self,
        user_repo: IUserRepository = db.users,
        reminder_repo: IReminderRepository = db.reminders,
        system_repo: ISystemSettingsRepository = db.system,
        evaluator: ReminderEvaluator = None,
    ):
        self._user_repo = user_repo
        self._reminder_repo = reminder_repo
        self._system_repo = system_repo
        self._evaluator = evaluator or ReminderEvaluator()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["user_repo"] = self._user_repo
        data["reminder_repo"] = self._reminder_repo
        data["system_repo"] = self._system_repo
        data["evaluator"] = self._evaluator
        data["db"] = db
        return await handler(event, data)
