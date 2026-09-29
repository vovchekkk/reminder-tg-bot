import asyncio
from datetime import datetime, timezone
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.database.connection import DatabaseConnectionManager
from app.database.repositories import (
    SqliteReminderRepository,
    SqliteSystemSettingsRepository,
    SqliteUserRepository,
)
from app.domain.interfaces import INotifier
from app.handlers import setup_handlers
from app.services.evaluator import ReminderEvaluator


@pytest.fixture
def temp_db():
    """Создаёт чистую временную SQLite базу данных для каждого теста."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn_mgr = DatabaseConnectionManager(db_path=path)
    user_repo = SqliteUserRepository(conn_mgr)
    reminder_repo = SqliteReminderRepository(conn_mgr)
    system_repo = SqliteSystemSettingsRepository(conn_mgr)

    yield {
        "path": path,
        "conn_mgr": conn_mgr,
        "user_repo": user_repo,
        "reminder_repo": reminder_repo,
        "system_repo": system_repo,
    }

    try:
        os.remove(path)
    except Exception:
        pass


@pytest.fixture
def evaluator():
    return ReminderEvaluator()


@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=True)
    bot.edit_message_text = AsyncMock(return_value=True)
    bot.delete_message = AsyncMock(return_value=True)
    bot.__call__ = AsyncMock(return_value=True)
    return bot


@pytest.fixture
def mock_notifier():
    notifier = MagicMock(spec=INotifier)
    notifier.send_reminder = AsyncMock(return_value=True)
    return notifier


@pytest.fixture
def test_dp(temp_db):
    """Dispatcher с подключенными роутерами и DI репозиториями из temp_db."""
    from app.middlewares.di import DependencyInjectionMiddleware

    dp = Dispatcher(storage=MemoryStorage())
    di = DependencyInjectionMiddleware(
        user_repo=temp_db["user_repo"],
        reminder_repo=temp_db["reminder_repo"],
        system_repo=temp_db["system_repo"],
    )
    setup_handlers(dp, di_middleware=di)
    return dp
