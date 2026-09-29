import html
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import logger
from app.database import db
from app.domain.interfaces import IReminderRepository, IUserRepository
from app.keyboards import get_done_keyboard, get_reminder_control_keyboard
from app.services.time_utils import (
    format_days_list,
    format_interval,
    get_now_for_user,
    safe_fromisoformat,
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

    reminders = r_repo.get_user_reminders(user_id)
    user_now = get_now_for_user(user_id, u_repo)
    user_today_str = user_now.strftime("%Y-%m-%d")

    if not reminders:
        return (
            "📭 У вас пока нет созданных напоминаний.\n\n"
            "Нажмите <b>«➕ Создать напоминание»</b>, чтобы запланировать первую задачу!",
            None,
        )

    text = f"📋 <b>Ваши напоминания ({len(reminders)}):</b>\n\n"
    buttons = []

    for r in reminders:
        status_icon = "🟢" if r["is_active"] else "⏸️"
        if r["is_completed"]:
            status_icon = "✅"

        type_str = (
            f"📅 {format_days_list(r['days_of_week'])}"
            if r["reminder_type"] == "recurring"
            else "⏱️ Одноразовое"
        )
        interval_str = format_interval(r["interval_minutes"])

        short_title = r["text"][:30] + ("..." if len(r["text"]) > 30 else "")
        text += (
            f"{status_icon} <b>ID {r['id']}: {html.escape(short_title)}</b>\n"
            f"   • Тип: {type_str}\n"
            f"   • Повтор: каждые {interval_str}\n"
        )
        if r["reminder_type"] == "recurring":
            start_s = r["start_time"] or "00:00"
            end_s = f" до {r['end_time']}" if r.get("end_time") else ""
            text += f"   • Время: с {start_s}{end_s}\n"
        elif r["reminder_type"] == "one_time" and r["start_datetime"]:
            try:
                dt_obj = safe_fromisoformat(
                    r["start_datetime"], tz_obj=user_now.tzinfo
                )
                end_s = f" (до {r['end_time']})" if r.get("end_time") else ""
                text += f"   • Старт: {dt_obj.strftime('%d.%m.%Y %H:%M')}{end_s}\n"
            except Exception:
                pass

        if r["last_completed_date"] == user_today_str:
            text += "   • <i>Сегодня уже выполнено 🎉</i>\n"

        text += "\n"

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{status_icon} ID {r['id']}: {short_title}",
                    callback_data=f"manage_rem:{r['id']}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="➕ Создать новое", callback_data="start_wizard"
            )
        ]
    )
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


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

    rem_id = int(callback.data.split(":")[1])
    rem = r_repo.get_reminder(rem_id)
    if not rem or rem["user_id"] != callback.from_user.id:
        await callback.answer("Напоминание не найдено.", show_alert=True)
        return

    user_now = get_now_for_user(callback.from_user.id, u_repo)
    status = (
        "🟢 Активно"
        if rem["is_active"]
        else ("✅ Завершено" if rem["is_completed"] else "⏸️ На паузе")
    )
    type_str = (
        f"По дням недели ({format_days_list(rem['days_of_week'])})"
        if rem["reminder_type"] == "recurring"
        else "Одноразовое"
    )

    info = (
        f"⚙️ <b>Управление напоминанием #{rem['id']}</b>\n\n"
        f"📌 <b>Текст:</b> {html.escape(rem['text'])}\n"
        f"📊 <b>Статус:</b> {status}\n"
        f"🔁 <b>Тип:</b> {type_str}\n"
        f"⏰ <b>Интервал повтора:</b> каждые {format_interval(rem['interval_minutes'])}\n"
    )
    if rem["reminder_type"] == "recurring":
        start_s = rem["start_time"] or "00:00"
        end_s = f" до {rem['end_time']}" if rem.get("end_time") else ""
        info += f"🕐 <b>Время показа:</b> с {start_s}{end_s}\n"
    elif rem["reminder_type"] == "one_time" and rem["start_datetime"]:
        try:
            dt_obj = safe_fromisoformat(
                rem["start_datetime"], tz_obj=user_now.tzinfo
            )
            end_s = f" (до {rem['end_time']})" if rem.get("end_time") else ""
            info += f"🕐 <b>Начало:</b> {dt_obj.strftime('%d.%m.%Y %H:%M')}{end_s}\n"
        except Exception:
            pass

    if rem["last_completed_date"] == user_now.strftime("%Y-%m-%d"):
        info += "\n<i>✨ Сегодня задание уже отмечено как сделанное!</i>"

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
    rem_id = int(callback.data.split(":")[1])
    res = r_repo.toggle_active(rem_id, callback.from_user.id)
    if res is None:
        await callback.answer("Ошибка: напоминание не найдено.")
        return
    msg = (
        "▶️ Напоминание включено!"
        if res
        else "⏸️ Напоминание приостановлено на паузу."
    )
    await callback.answer(msg)
    rem = r_repo.get_reminder(rem_id)
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
    rem_id = int(callback.data.split(":")[1])
    r_repo.delete_reminder(rem_id, callback.from_user.id)
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
    rem_id = int(callback.data.split(":")[1])
    rem = r_repo.get_reminder(rem_id)
    if not rem:
        await callback.answer("Напоминание не найдено.")
        return

    await callback.answer("Отправляю тестовое напоминание...")
    await bot.send_message(
        chat_id=callback.from_user.id,
        text=(
            f"🔔 <b>НАПОМИНАНИЕ (тестовая проверка)!</b>\n\n"
            f"📌 <b>{html.escape(rem['text'])}</b>\n\n"
            f"<i>Интервал повтора: каждые {format_interval(rem['interval_minutes'])}, пока не нажмёте галочку.</i>"
        ),
        reply_markup=get_done_keyboard(rem["id"]),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith("done:"))
async def callback_done_button(
    callback: CallbackQuery,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Обработка нажатия на кнопку «✅ Сделано!»."""
    r_repo = reminder_repo or db.reminders
    u_repo = user_repo or db.users

    rem_id = int(callback.data.split(":")[1])
    rem = r_repo.get_reminder(rem_id)

    if not rem:
        await callback.answer(
            "Напоминание уже не существует или удалено.", show_alert=True
        )
        return

    user_now = get_now_for_user(callback.from_user.id, u_repo)
    today_str = user_now.strftime("%Y-%m-%d")

    await callback.answer("🎉 Ура, вы молодец!", show_alert=True)

    if rem["reminder_type"] == "recurring":
        r_repo.mark_completed_today(rem_id, today_str)
        congrats_text = (
            f"✅ <b>Ура, вы молодец! Задача выполнена!</b> 🎉\n\n"
            f"📌 «{html.escape(rem['text'])}»\n\n"
            f"На сегодня напоминания <b>остановлены</b>.\n"
            f"Следующее напоминание придёт в следующий запланированный день ({format_days_list(rem['days_of_week'])})."
        )
    else:
        r_repo.mark_completed_permanently(rem_id)
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
