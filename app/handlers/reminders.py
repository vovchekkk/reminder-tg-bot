import html
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import logger
from app.database import db
from app.domain.interfaces import IReminderRepository, IUserRepository
from app.keyboards import get_done_keyboard, get_reminder_control_keyboard
from app.services.presentation import ReminderPresenter
from app.services.reminder_service import ReminderService
from app.services.time_utils import (
    format_days_list,
    get_now_for_user,
)

router = Router(name="reminders")


def render_reminders_list(
    user_id: int,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Формирует текст и инлайн-клавиатуру со списком напоминаний пользователя."""
    r_repo = reminder_repo or db.reminders
    u_repo = user_repo or db.users

    service = ReminderService(reminder_repo=r_repo, user_repo=u_repo)
    presenter = ReminderPresenter()

    reminders = service.get_user_reminders(user_id)
    user_now = get_now_for_user(user_id, u_repo)
    return presenter.render_list(reminders, user_now)


@router.message(Command("list"))
@router.message(F.text == "📋 Мои напоминания")
async def show_reminders_list(
    message: Message,
    state: FSMContext,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Показывает список напоминаний по команде или кнопке."""
    await state.clear()
    text, kb = render_reminders_list(message.from_user.id, reminder_repo, user_repo)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "refresh_list")
async def callback_refresh_list(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Обновляет сообщение со списком напоминаний."""
    await state.clear()
    text, kb = render_reminders_list(callback.from_user.id, reminder_repo, user_repo)
    try:
        await callback.message.edit_text(
            text, reply_markup=kb, parse_mode=ParseMode.HTML
        )
    except Exception:
        await callback.message.answer(
            text, reply_markup=kb, parse_mode=ParseMode.HTML
        )
    await callback.answer()


@router.callback_query(F.data.startswith("manage_rem:"))
async def callback_manage_reminder(
    callback: CallbackQuery,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Карточка управления конкретным напоминанием."""
    r_repo = reminder_repo or db.reminders
    u_repo = user_repo or db.users

    service = ReminderService(reminder_repo=r_repo, user_repo=u_repo)
    presenter = ReminderPresenter()

    rem_id = int(callback.data.split(":")[1])
    rem = service.get_reminder(rem_id)
    if not rem or rem["user_id"] != callback.from_user.id:
        await callback.answer("Напоминание не найдено.", show_alert=True)
        return

    user_now = get_now_for_user(callback.from_user.id, u_repo)
    info = presenter.render_card(rem, user_now)

    await callback.message.edit_text(
        info,
        reply_markup=get_reminder_control_keyboard(rem),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_active:"))
async def callback_toggle_active(
    callback: CallbackQuery,
    reminder_repo: Optional[IReminderRepository] = None,
):
    """Включение / пауза напоминания."""
    r_repo = reminder_repo or db.reminders
    service = ReminderService(reminder_repo=r_repo)

    rem_id = int(callback.data.split(":")[1])
    res = service.toggle_active(rem_id, callback.from_user.id)
    if res is None:
        await callback.answer("Ошибка: напоминание не найдено.")
        return
    msg = (
        "▶️ Напоминание включено!"
        if res
        else "⏸️ Напоминание приостановлено на паузу."
    )
    await callback.answer(msg)
    rem = service.get_reminder(rem_id)
    await callback.message.edit_reply_markup(
        reply_markup=get_reminder_control_keyboard(rem)
    )


@router.callback_query(F.data.startswith("delete_rem:"))
async def callback_delete_reminder(
    callback: CallbackQuery,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Удаление напоминания."""
    r_repo = reminder_repo or db.reminders
    service = ReminderService(reminder_repo=r_repo, user_repo=user_repo)

    rem_id = int(callback.data.split(":")[1])
    service.delete_reminder(rem_id, callback.from_user.id)
    await callback.answer("🗑️ Напоминание удалено!")
    text, kb = render_reminders_list(callback.from_user.id, r_repo, user_repo)
    await callback.message.edit_text(
        text, reply_markup=kb, parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("test_trigger:"))
async def callback_test_trigger(
    callback: CallbackQuery,
    bot: Bot,
    reminder_repo: Optional[IReminderRepository] = None,
):
    """Тестовая отправка напоминания прямо сейчас."""
    r_repo = reminder_repo or db.reminders
    service = ReminderService(reminder_repo=r_repo)
    presenter = ReminderPresenter()

    rem_id = int(callback.data.split(":")[1])
    rem = service.get_reminder(rem_id)
    if not rem:
        await callback.answer("Напоминание не найдено.")
        return

    await callback.answer("Отправляю тестовое напоминание...")
    desc = presenter.render_test_desc(rem)

    await bot.send_message(
        chat_id=callback.from_user.id,
        text=(
            f"🔔 <b>НАПОМИНАНИЕ (тестовая проверка)!</b>\n\n"
            f"📌 <b>{html.escape(rem['text'])}</b>\n\n"
            f"<i>{desc}</i>"
        ),
        reply_markup=get_done_keyboard(rem["id"], is_test=True),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith("done_test:"))
async def callback_done_test_button(
    callback: CallbackQuery,
    reminder_repo: Optional[IReminderRepository] = None,
):
    """Обработка кнопки «✅ Сделано!» для тестового напоминания."""
    r_repo = reminder_repo or db.reminders
    service = ReminderService(reminder_repo=r_repo)
    rem_id = int(callback.data.split(":")[1])
    rem = service.get_reminder(rem_id)

    # Всплывающее модальное окно (alert)
    await callback.answer(
        "ℹ️ Это тестовое напоминание!\n\n"
        "Нажатие кнопки «Сделано» на тестовом напоминании НЕ отключает его на текущий день. "
        "Основное напоминание сработает строго по расписанию!",
        show_alert=True,
    )

    rem_title = rem["text"] if rem else "Напоминание"
    congrats_text = (
        f"✅ <b>Тестовая проверка завершена!</b> 🎉\n\n"
        f"📌 «{html.escape(rem_title)}»\n\n"
        f"<i>💡 Напоминание по-прежнему активно на сегодня и сработает по расписанию.</i>"
    )

    try:
        await callback.message.edit_text(
            congrats_text, reply_markup=None, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Не удалось обновить сообщение с тестовым напоминанием: {e}")


@router.callback_query(F.data.startswith("done:"))
async def callback_done_button(
    callback: CallbackQuery,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Обработка нажатия на кнопку «✅ Сделано!»."""
    r_repo = reminder_repo or db.reminders
    u_repo = user_repo or db.users
    service = ReminderService(reminder_repo=r_repo, user_repo=u_repo)

    rem_id = int(callback.data.split(":")[1])
    rem = service.get_reminder(rem_id)

    if not rem:
        await callback.answer(
            "Напоминание уже не существует или удалено.", show_alert=True
        )
        return

    user_now = get_now_for_user(callback.from_user.id, u_repo)
    today_str = user_now.strftime("%Y-%m-%d")

    await callback.answer("🎉 Ура, вы молодец!", show_alert=True)
    completion_type = service.mark_done(rem, today_str)

    if completion_type == "today":
        congrats_text = (
            f"✅ <b>Ура, вы молодец! Задача выполнена!</b> 🎉\n\n"
            f"📌 «{html.escape(rem['text'])}»\n\n"
            f"На сегодня напоминания <b>остановлены</b>.\n"
            f"Следующее напоминание придёт в следующий запланированный день ({format_days_list(rem['days_of_week'])})."
        )
    else:
        congrats_text = (
            f"✅ <b>Ура, вы молодец! Задача выполнена!</b> 🎉\n\n"
            f"📌 «{html.escape(rem['text'])}»\n\n"
            f"Одноразовое напоминание успешно <b>завершено</b>."
        )

    try:
        await callback.message.edit_text(
            congrats_text, reply_markup=None, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Не удалось обновить сообщение с напоминанием: {e}")
        await callback.message.answer(
            congrats_text, parse_mode=ParseMode.HTML
        )
