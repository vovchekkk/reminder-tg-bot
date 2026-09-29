import pytest
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import TelegramObject

from app.middlewares.di import DependencyInjectionMiddleware


@pytest.mark.asyncio
async def test_di_middleware_injects_dependencies(temp_db):
    user_repo = temp_db["user_repo"]
    reminder_repo = temp_db["reminder_repo"]
    system_repo = temp_db["system_repo"]

    middleware = DependencyInjectionMiddleware(
        user_repo=user_repo,
        reminder_repo=reminder_repo,
        system_repo=system_repo,
    )

    dummy_event = MagicMock(spec=TelegramObject)
    data = {}

    called = False
    async def dummy_handler(event, event_data):
        nonlocal called
        called = True
        assert event_data["user_repo"] is user_repo
        assert event_data["reminder_repo"] is reminder_repo
        assert event_data["system_repo"] is system_repo
        assert "evaluator" in event_data
        return "result_ok"

    res = await middleware(dummy_handler, dummy_event, data)
    assert called is True
    assert res == "result_ok"
