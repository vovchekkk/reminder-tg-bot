import html
from typing import Any, Dict

from aiogram import Bot
from aiogram.enums import ParseMode

from app.config import logger
from app.domain.interfaces import INotifier
from app.keyboards import get_done_keyboard
from app.services.time_utils import format_interval


class TelegramNotifier(INotifier):
    """Сервис отправки напоминаний через Telegram Bot API."""

    def __init__(self, bot: Bot):
        self._bot = bot

    async def send_reminder(self, reminder: Dict[str, Any]) -> bool:
        """Форматирует и отправляет сообщение с напоминанием пользователю."""
        try:
            user_id = reminder["user_id"]
            rem_id = reminder["id"]
            text = reminder["text"]
            interval = reminder["interval_minutes"]

            message_text = (
                f"🔔 <b>НАПОМИНАНИЕ!</b>\n\n"
                f"📌 <b>{html.escape(text)}</b>\n\n"
                f"<i>Повторяю каждые {format_interval(interval)}, "
                f"пока не подтвердите выполнение кнопкой ниже:</i>"
            )

            await self._bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=get_done_keyboard(rem_id),
                parse_mode=ParseMode.HTML,
            )
            return True
        except Exception as e:
            logger.error(
                f"Не удалось отправить напоминание #{reminder.get('id')} "
                f"пользователю {reminder.get('user_id')}: {e}"
            )
            return False
