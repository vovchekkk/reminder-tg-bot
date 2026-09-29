"""
Entry point for Reminder Telegram Bot.
Run: python bot.py
"""

import asyncio
from app.database import Database, db
from app.keyboards import (
    get_end_time_keyboard,
    get_onetime_end_time_keyboard,
    get_start_time_keyboard,
)
from app.main import main
from app.services.time_utils import is_time_in_range

__all__ = [
    "Database",
    "db",
    "get_end_time_keyboard",
    "get_onetime_end_time_keyboard",
    "get_start_time_keyboard",
    "is_time_in_range",
    "main",
]

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
