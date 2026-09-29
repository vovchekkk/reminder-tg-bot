from datetime import datetime, timedelta
import html
import re
from typing import Optional

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.database import db
from app.domain.interfaces import IReminderRepository, IUserRepository
from app.keyboards import (
    get_days_keyboard,
    get_end_time_keyboard,
    get_interval_keyboard,
    get_onetime_end_time_keyboard,
    get_onetime_quick_keyboard,
    get_start_time_keyboard,
    get_type_keyboard,
    get_wizard_cancel_keyboard,
)
from app.services.time_utils import (
    format_days_list,
    format_interval,
    get_now_for_user,
    parse_time_or_delay,
    safe_fromisoformat,
)
from app.states import CreateReminderFSM

router = Router(name="wizard")


@router.message(Command("new"))
@router.message(F.text == "➕ Создать напоминание")
@router.callback_query(F.data == "start_wizard")
async def start_wizard(event: Message | CallbackQuery, state: FSMContext):
    """Старт мастера создания напоминания."""
    await state.clear()
    prompt_text = (
        "📝 <b>Шаг 1: Текст напоминания</b>\n\n"
        "Напишите сообщение, о чём вам напомнить.\n"
        "<i>Например: «Сделать тест по физре», «Выпить витамины», «Сдать отчёт»</i>"
    )
    cancel_kb = get_wizard_cancel_keyboard()

    if isinstance(event, CallbackQuery):
        msg = await event.message.edit_text(
            prompt_text, reply_markup=cancel_kb, parse_mode=ParseMode.HTML
        )
        await event.answer()
    else:
        msg = await event.answer(
            prompt_text, reply_markup=cancel_kb, parse_mode=ParseMode.HTML
        )

    await state.set_state(CreateReminderFSM.waiting_for_text)
    await state.update_data(wizard_msg_id=msg.message_id)


@router.callback_query(F.data == "cancel_wizard")
async def cancel_wizard(callback: CallbackQuery, state: FSMContext):
    """Отмена мастера создания."""
    await state.clear()
    await callback.answer("Создание отменено.")
    await callback.message.edit_text(
        "❌ <b>Создание напоминания отменено.</b>",
        reply_markup=None,
        parse_mode=ParseMode.HTML,
    )


async def cleanup_previous_wizard_message(message: Message, state: FSMContext):
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


@router.message(CreateReminderFSM.waiting_for_text)
async def process_reminder_text(message: Message, state: FSMContext):
    """Обработка текста напоминания."""
    text = message.text.strip()
    if not text:
        await message.answer("Пожалуйста, введите непустой текст напоминания:")
        return

    await cleanup_previous_wizard_message(message, state)

    sent = await message.answer(
        f"📌 Текст: <b>{html.escape(text)}</b>\n\n"
        f"<b>Шаг 2: Выберите тип напоминания:</b>\n"
        f"• <b>🔁 По дням недели</b> — повторяется в выбранные дни (например, каждый Пн и Пт)\n"
        f"• <b>⏱️ Одноразовое</b> — напомнить один раз (в конкретную дату/время)",
        reply_markup=get_type_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await state.update_data(text=text, wizard_msg_id=sent.message_id)
    await state.set_state(CreateReminderFSM.choosing_type)


# --- ПОВТОРЯЮЩИЕСЯ НАПОМИНАНИЯ (ПО ДНЯМ НЕДЕЛИ) ---


@router.callback_query(
    CreateReminderFSM.choosing_type, F.data == "type:recurring"
)
async def choose_recurring_type(callback: CallbackQuery, state: FSMContext):
    """Выбор повторяющегося типа напоминания."""
    await state.update_data(reminder_type="recurring", selected_days=[])
    await state.set_state(CreateReminderFSM.choosing_days)
    await callback.message.edit_text(
        "📅 <b>Шаг 3: Выберите дни недели:</b>\n\n"
        "Нажимайте на кнопки, чтобы отметить нужные дни.\n"
        "Когда закончите выбор, нажмите <b>«➡️ Далее»</b>:",
        reply_markup=get_days_keyboard(set()),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.choosing_days, F.data.startswith("toggle_day:")
)
async def toggle_day_selection(callback: CallbackQuery, state: FSMContext):
    """Переключение выбора дня недели."""
    day_idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_days = set(data.get("selected_days", []))

    if day_idx in selected_days:
        selected_days.remove(day_idx)
    else:
        selected_days.add(day_idx)

    await state.update_data(selected_days=list(selected_days))
    await callback.message.edit_reply_markup(
        reply_markup=get_days_keyboard(selected_days)
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.choosing_days, F.data.startswith("preset_days:")
)
async def preset_days_action(callback: CallbackQuery, state: FSMContext):
    """Быстрый выбор пресетов дней недели (все, будни, выходные, сброс)."""
    action = callback.data.split(":")[1]
    if action == "all":
        selected = {0, 1, 2, 3, 4, 5, 6}
    elif action == "weekdays":
        selected = {0, 1, 2, 3, 4}
    elif action == "weekends":
        selected = {5, 6}
    else:
        selected = set()

    await state.update_data(selected_days=list(selected))
    await callback.message.edit_reply_markup(
        reply_markup=get_days_keyboard(selected)
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.choosing_days, F.data == "days_confirmed"
)
async def days_confirmed(callback: CallbackQuery, state: FSMContext):
    """Подтверждение выбранных дней недели."""
    data = await state.get_data()
    selected_days = data.get("selected_days", [])
    if not selected_days:
        await callback.answer(
            "Пожалуйста, выберите хотя бы один день недели!", show_alert=True
        )
        return

    days_str = ",".join(map(str, sorted(selected_days)))
    await state.update_data(days_of_week=days_str)
    await state.set_state(CreateReminderFSM.waiting_for_start_time)

    await callback.message.edit_text(
        f"📅 Выбранные дни: <b>{format_days_list(days_str)}</b>\n\n"
        f"🕐 <b>С какого времени начинать напоминать в эти дни?</b>\n"
        f"<i>(Например, если выбрать «С 09:00», бот в этот день начнёт присылать напоминания в 9 утра по вашему поясу и повторять их, пока вы не нажмёте ✅)</i>",
        reply_markup=get_start_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.waiting_for_start_time, F.data.startswith("starttime:")
)
async def process_start_time_choice(
    callback: CallbackQuery, state: FSMContext
):
    """Обработка кнопки времени старта."""
    val = callback.data.split(":", 1)[1]
    if val == "custom":
        await callback.message.edit_text(
            "✏️ Напишите время начала в формате <b>ЧЧ:ММ</b> (например, <code>09:30</code> или <code>14:00</code>):",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    if val in ("now", "00:00", "day_start"):
        start_time_str = "00:00"
    else:
        start_time_str = val

    await state.update_data(start_time=start_time_str)
    await state.set_state(CreateReminderFSM.waiting_for_end_time)
    await callback.message.edit_text(
        f"🕐 Начало: <b>с {start_time_str}</b>\n\n"
        f"🛑 <b>До скольки напоминать в эти дни?</b>\n"
        f"<i>(После этого времени бот перестанет присылать повторы до следующего назначенного дня, чтобы не беспокоить ночью)</i>",
        reply_markup=get_end_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_start_time)
async def process_custom_start_time_text(message: Message, state: FSMContext):
    """Ручной ввод времени начала."""
    text = message.text.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not m:
        await message.answer(
            "Некорректный формат! Введите время в виде <b>ЧЧ:ММ</b> (например, <code>09:15</code>):",
            parse_mode=ParseMode.HTML,
        )
        return

    h, m_val = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= m_val <= 59):
        await message.answer(
            "Неверные часы или минуты. Введите время от 00:00 до 23:59."
        )
        return

    start_time_str = f"{h:02d}:{m_val:02d}"
    await cleanup_previous_wizard_message(message, state)

    sent = await message.answer(
        f"🕐 Начало: <b>с {start_time_str}</b>\n\n"
        f"🛑 <b>До скольки напоминать в эти дни?</b>\n"
        f"<i>(После этого времени бот перестанет присылать повторы до следующего назначенного дня, чтобы не беспокоить ночью)</i>",
        reply_markup=get_end_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await state.update_data(start_time=start_time_str, wizard_msg_id=sent.message_id)
    await state.set_state(CreateReminderFSM.waiting_for_end_time)


@router.callback_query(
    CreateReminderFSM.waiting_for_end_time, F.data.startswith("endtime:")
)
async def process_end_time_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки времени окончания."""
    val = callback.data.split(":", 1)[1]
    if val == "custom":
        await callback.message.edit_text(
            "✏️ Напишите время окончания в формате <b>ЧЧ:ММ</b> (например, <code>22:00</code> или <code>23:30</code>):",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    end_time_str = "23:59" if val in ("day_end", "23:59") else val
    await state.update_data(end_time=end_time_str)
    await prompt_interval_selection(callback.message, state, is_edit=True)
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_end_time)
async def process_custom_end_time_text(message: Message, state: FSMContext):
    """Ручной ввод времени окончания."""
    text = message.text.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not m:
        await message.answer(
            "Некорректный формат! Введите время в виде <b>ЧЧ:ММ</b> (например, <code>22:00</code>):",
            parse_mode=ParseMode.HTML,
        )
        return

    h, m_val = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= m_val <= 59):
        await message.answer(
            "Неверные часы или минуты. Введите время от 00:00 до 23:59."
        )
        return

    end_time_str = f"{h:02d}:{m_val:02d}"
    await state.update_data(end_time=end_time_str)
    await cleanup_previous_wizard_message(message, state)
    sent = await prompt_interval_selection(message, state, is_edit=False)
    if sent:
        await state.update_data(wizard_msg_id=sent.message_id)


# --- ОДНОРАЗОВЫЕ НАПОМИНАНИЯ ---


@router.callback_query(
    CreateReminderFSM.choosing_type, F.data == "type:one_time"
)
async def choose_onetime_type(callback: CallbackQuery, state: FSMContext):
    """Выбор одноразового напоминания."""
    await state.update_data(reminder_type="one_time")
    await state.set_state(CreateReminderFSM.waiting_for_onetime_dt)
    await callback.message.edit_text(
        "⏱️ <b>Когда отправить первое напоминание?</b>\n\n"
        "Выберите быстрый вариант или напишите текстом\n"
        "(например: <code>18:30</code>, <code>+45m</code>, <code>+2h</code> или <code>30.09 14:00</code>):",
        reply_markup=get_onetime_quick_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.waiting_for_onetime_dt, F.data.startswith("quicktime:")
)
async def process_quick_onetime(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: Optional[IUserRepository] = None,
):
    """Быстрый выбор времени для одноразового напоминания."""
    val = callback.data.split(":", 1)[1]
    u_repo = user_repo or db.users
    now = get_now_for_user(callback.from_user.id, u_repo)

    if val == "manual":
        await callback.message.edit_text(
            "✏️ Напишите дату и время для напоминания:\n\n"
            "Примеры:\n"
            "• <code>18:30</code> (сегодня/завтра)\n"
            "• <code>+30m</code> (через 30 минут)\n"
            "• <code>+2h</code> (через 2 часа)\n"
            "• <code>30.09 15:00</code>",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    target_dt: Optional[datetime] = None
    if val == "+10m":
        target_dt = now + timedelta(minutes=10)
    elif val == "+30m":
        target_dt = now + timedelta(minutes=30)
    elif val == "+1h":
        target_dt = now + timedelta(hours=1)
    elif val == "+2h":
        target_dt = now + timedelta(hours=2)
    elif val == "18:00":
        target_dt = now.replace(
            hour=18, minute=0, second=0, microsecond=0
        )
        if target_dt <= now:
            target_dt += timedelta(days=1)
    elif val == "tomorrow_09":
        target_dt = (now + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )

    if target_dt:
        await state.update_data(start_datetime=target_dt.isoformat())
        await state.set_state(CreateReminderFSM.waiting_for_onetime_end_time)
        await callback.message.edit_text(
            f"🕐 Первое напоминание: <b>{target_dt.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"🛑 <b>До скольки напоминать (если вы не нажмёте ✅)?</b>\n"
            f"<i>(После этого времени бот перестанет присылать повторные сообщения)</i>",
            reply_markup=get_onetime_end_time_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_onetime_dt)
async def process_manual_onetime_dt(
    message: Message,
    state: FSMContext,
    user_repo: Optional[IUserRepository] = None,
):
    """Ручной ввод даты и времени для одноразового напоминания."""
    u_repo = user_repo or db.users
    now = get_now_for_user(message.from_user.id, u_repo)
    parsed_dt = parse_time_or_delay(message.text, now)
    if not parsed_dt:
        await message.answer(
            "⚠️ Не удалось распознать время. Попробуйте еще раз:\n"
            "Примеры: <code>18:30</code>, <code>+45m</code>, <code>+2h</code>, <code>30.09 15:00</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    await cleanup_previous_wizard_message(message, state)

    sent = await message.answer(
        f"🕐 Первое напоминание: <b>{parsed_dt.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
        f"🛑 <b>До скольки напоминать (если вы не нажмёте ✅)?</b>\n"
        f"<i>(После этого времени бот перестанет присылать повторные сообщения)</i>",
        reply_markup=get_onetime_end_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await state.update_data(
        start_datetime=parsed_dt.isoformat(), wizard_msg_id=sent.message_id
    )
    await state.set_state(CreateReminderFSM.waiting_for_onetime_end_time)


@router.callback_query(
    CreateReminderFSM.waiting_for_onetime_end_time, F.data.startswith("onetime_end:")
)
async def process_onetime_end_choice(callback: CallbackQuery, state: FSMContext):
    """Выбор ограничения времени для одноразового напоминания."""
    val = callback.data.split(":", 1)[1]
    if val == "custom":
        await callback.message.edit_text(
            "✏️ Напишите время окончания в формате <b>ЧЧ:ММ</b> (например, <code>22:00</code> или <code>23:30</code>):",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    if val == "none":
        end_time_str = None
    elif val in ("day_end", "23:59"):
        end_time_str = "23:59"
    else:
        end_time_str = val

    await state.update_data(end_time=end_time_str)
    await prompt_interval_selection(callback.message, state, is_edit=True)
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_onetime_end_time)
async def process_custom_onetime_end_text(message: Message, state: FSMContext):
    """Ручной ввод ограничения времени для одноразового напоминания."""
    text = message.text.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not m:
        await message.answer(
            "Некорректный формат! Введите время в виде <b>ЧЧ:ММ</b> (например, <code>22:00</code>):",
            parse_mode=ParseMode.HTML,
        )
        return

    h, m_val = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= m_val <= 59):
        await message.answer(
            "Неверные часы или минуты. Введите время от 00:00 до 23:59."
        )
        return

    end_time_str = f"{h:02d}:{m_val:02d}"
    await state.update_data(end_time=end_time_str)
    await cleanup_previous_wizard_message(message, state)
    sent = await prompt_interval_selection(message, state, is_edit=False)
    if sent:
        await state.update_data(wizard_msg_id=sent.message_id)


# --- ВЫБОР ИНТЕРВАЛА И ЗАВЕРШЕНИЕ ---


async def prompt_interval_selection(
    message: Message, state: FSMContext, is_edit: bool
):
    """Показывает выбор частоты повторов напоминания."""
    await state.set_state(CreateReminderFSM.choosing_interval)
    prompt = (
        "⏰ <b>Как часто напоминать, если вы не нажали ✅?</b>\n\n"
        "Бот будет присылать повторные сообщения с этим интервалом (в пределах заданного диапазона времени), "
        "пока вы не нажмёте кнопку «✅ Сделано!»:"
    )
    if is_edit:
        return await message.edit_text(
            prompt,
            reply_markup=get_interval_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    else:
        return await message.answer(
            prompt,
            reply_markup=get_interval_keyboard(),
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(
    CreateReminderFSM.choosing_interval, F.data.startswith("interval:")
)
async def process_interval_choice(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Выбор готового интервала."""
    val = callback.data.split(":", 1)[1]
    if val == "custom":
        await state.set_state(CreateReminderFSM.waiting_for_custom_interval)
        await callback.message.edit_text(
            "✏️ Введите свой интервал повтора <b>в минутах</b> (число от 5 до 1440):\n"
            "<i>Например: 45 (каждые 45 мин) или 90 (каждые 1.5 часа)</i>",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    interval_minutes = int(val)
    await finalize_reminder_creation(
        callback.message,
        state,
        interval_minutes,
        is_callback=True,
        reminder_repo=reminder_repo,
        user_repo=user_repo,
    )
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_custom_interval)
async def process_custom_interval_text(
    message: Message,
    state: FSMContext,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Ручной ввод интервала в минутах."""
    text = message.text.strip()
    if not text.isdigit():
        await message.answer(
            "Пожалуйста, введите целое число минут (например: <code>45</code>):",
            parse_mode=ParseMode.HTML,
        )
        return

    minutes = int(text)
    if minutes < 1 or minutes > 10080:
        await message.answer(
            "Интервал должен быть от 1 до 10080 минут. Попробуйте еще раз:"
        )
        return

    await cleanup_previous_wizard_message(message, state)
    await finalize_reminder_creation(
        message,
        state,
        minutes,
        is_callback=False,
        reminder_repo=reminder_repo,
        user_repo=user_repo,
    )


async def finalize_reminder_creation(
    message: Message,
    state: FSMContext,
    interval_minutes: int,
    is_callback: bool,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Завершение создания напоминания и сохранение в базу."""
    r_repo = reminder_repo or db.reminders
    u_repo = user_repo or db.users

    data = await state.get_data()
    user_id = message.chat.id
    text = data["text"]
    reminder_type = data["reminder_type"]
    days_of_week = data.get("days_of_week")
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    start_datetime = data.get("start_datetime")

    rem_id = r_repo.add_reminder(
        user_id=user_id,
        text=text,
        reminder_type=reminder_type,
        interval_minutes=interval_minutes,
        days_of_week=days_of_week,
        start_time=start_time,
        end_time=end_time,
        start_datetime=start_datetime,
    )

    await state.clear()
    user_now = get_now_for_user(user_id, u_repo)

    summary = (
        f"🎉 <b>Напоминание успешно создано!</b>\n\n"
        f"📌 <b>Текст:</b> {html.escape(text)}\n"
        f"🔁 <b>Тип:</b> {'По дням недели' if reminder_type == 'recurring' else 'Одноразовое'}\n"
    )

    if reminder_type == "recurring":
        start_s = start_time or "00:00"
        end_s = f" до {end_time}" if end_time else "до 23:59"
        summary += (
            f"📅 <b>Дни недели:</b> {format_days_list(days_of_week)}\n"
            f"🕐 <b>Время показа:</b> с {start_s} {end_s}\n"
        )
    else:
        dt_obj = safe_fromisoformat(start_datetime, tz_obj=user_now.tzinfo)
        summary += f"🕐 <b>Первое напоминание:</b> {dt_obj.strftime('%d.%m.%Y %H:%M')}\n"
        if end_time:
            summary += f"🛑 <b>Напоминать до:</b> {end_time}\n"

    summary += (
        f"⏰ <b>Частота повтора:</b> каждые {format_interval(interval_minutes)} "
        f"(пока не нажмёте ✅)\n\n"
        f"Когда придёт напоминание, нажмите под ним <b>«✅ Сделано!»</b>, чтобы отключить повторы."
    )

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
