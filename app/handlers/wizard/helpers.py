from typing import Optional

from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.database import db
from app.domain.interfaces import IReminderRepository, IUserRepository
from app.services.presentation import ReminderPresenter
from app.services.reminder_service import ReminderService
from app.services.time_utils import get_now_for_user


async def cleanup_previous_wizard_message(message: Message, state: FSMContext) -> None:
    """Удаляет предыдущее сообщение мастера и сообщение пользователя для чистоты чата."""
    data = await state.get_data()
    prev_msg_id = data.get("wizard_msg_id")
    if prev_msg_id:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id, message_id=prev_msg_id
            )
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass


async def finalize_wizard(
    message: Message,
    state: FSMContext,
    interval_minutes: int,
    is_callback: bool,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
) -> None:
    """Финализация мастера через ReminderService и ReminderPresenter (DIP, SRP, OCP)."""
    r_repo = reminder_repo or db.reminders
    u_repo = user_repo or db.users

    service = ReminderService(reminder_repo=r_repo, user_repo=u_repo)
    presenter = ReminderPresenter()

    data = await state.get_data()
    user_id = message.chat.id
    rem_id = service.create_reminder_from_wizard(user_id, data, interval_minutes)

    await state.clear()
    user_now = get_now_for_user(user_id, u_repo)

    created_rem = service.get_reminder(rem_id) or {
        "text": data["text"],
        "reminder_type": data["reminder_type"],
        "days_of_week": data.get("days_of_week"),
        "start_time": data.get("start_time"),
        "end_time": data.get("end_time"),
        "start_datetime": data.get("start_datetime"),
        "interval_minutes": interval_minutes,
    }

    summary = presenter.render_summary(created_rem, user_now)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 Протестировать сейчас",
                    callback_data=f"test_trigger:{rem_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Мои напоминания", callback_data="refresh_list"
                )
            ],
        ]
    )

    if is_callback:
        await message.edit_text(summary, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await message.answer(summary, reply_markup=kb, parse_mode=ParseMode.HTML)
