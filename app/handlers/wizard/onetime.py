from datetime import date, datetime, time, timedelta
import re
from typing import Optional

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database import db
from app.domain.interfaces import IReminderRepository, IUserRepository
from app.keyboards.wizard import (
    get_exact_time_keyboard,
    get_onetime_date_keyboard,
    get_onetime_end_time_keyboard,
    get_onetime_mode_keyboard,
    get_start_time_keyboard,
    get_wizard_cancel_keyboard,
)
from app.services.time_utils import (
    get_now_for_user,
    parse_date_string,
    parse_time_or_delay,
)
from app.states import CreateReminderFSM
from app.handlers.wizard.helpers import cleanup_previous_wizard_message, finalize_wizard

router = Router(name="wizard_onetime")


@router.callback_query(
    CreateReminderFSM.choosing_type, F.data == "type:one_time"
)
async def choose_onetime_type(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: Optional[IUserRepository] = None,
):
    """Выбор одноразового напоминания: переход к выбору даты."""
    u_repo = user_repo or db.users
    now = get_now_for_user(callback.from_user.id, u_repo)

    await state.update_data(reminder_type="one_time")
    await state.set_state(CreateReminderFSM.waiting_for_onetime_date)
    await callback.message.edit_text(
        "📅 <b>Шаг 3: Выберите дату напоминания:</b>\n\n"
        "Выберите дату кнопкой или напишите вручную сообщением.\n\n"
        "<i>Поддерживаемые форматы ввода:\n"
        "• Число месяца: <code>30</code>\n"
        "• День и месяц: <code>30.09</code>\n"
        "• С указанием года: <code>15.10.2026</code> или <code>01.01.2027</code>\n"
        "• Словами: <code>сегодня</code>, <code>завтра</code></i>",
        reply_markup=get_onetime_date_keyboard(now),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.waiting_for_onetime_date, F.data.startswith("setdate:")
)
async def process_onetime_date_callback(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: Optional[IUserRepository] = None,
):
    """Выбор даты для одноразового напоминания по инлайн-кнопке."""
    val = callback.data.split(":", 1)[1]
    if val == "custom":
        await callback.message.edit_text(
            "✏️ <b>Введите дату напоминания сообщением:</b>\n\n"
            "Примеры:\n"
            "• Число месяца: <code>30</code>\n"
            "• Дата: <code>30.09</code>\n"
            "• С указанием года: <code>15.10.2026</code> или <code>01.01.2027</code>\n"
            "• Словами: <code>сегодня</code>, <code>завтра</code>, <code>послезавтра</code>",
            reply_markup=get_wizard_cancel_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    u_repo = user_repo or db.users
    now = get_now_for_user(callback.from_user.id, u_repo)

    try:
        target_date = date.fromisoformat(val)
    except ValueError:
        await callback.answer("Некорректная дата.", show_alert=True)
        return

    if target_date < now.date():
        await callback.answer("⚠️ Дата не может быть в прошлом!", show_alert=True)
        return

    await state.update_data(onetime_date=target_date.isoformat())
    await state.set_state(CreateReminderFSM.choosing_onetime_mode)
    await callback.message.edit_text(
        f"📅 Выбранная дата: <b>{target_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"⚙️ <b>Как напомнить в этот день?</b>\n\n"
        f"• 🔔 <b>1 раз в определенное время</b> — пришлёт ровно одно напоминание в назначенный час.\n"
        f"• 🔁 <b>Повторяющиеся напоминания</b> — будет напоминать каждые X минут в заданном диапазоне времени, пока вы не нажмёте «✅ Сделано!» (или до конца дня).",
        reply_markup=get_onetime_mode_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_onetime_date)
async def process_onetime_date_text(
    message: Message,
    state: FSMContext,
    user_repo: Optional[IUserRepository] = None,
):
    """Ручной ввод даты для одноразового напоминания."""
    text = message.text.strip()
    u_repo = user_repo or db.users
    now = get_now_for_user(message.from_user.id, u_repo)

    target_date, err = parse_date_string(text, now)
    if err == "past_date":
        await message.answer(
            f"⚠️ <b>Дата не может быть в прошлом!</b>\n\n"
            f"Укажите сегодняшнюю дату ({now.strftime('%d.%m')}) или дату в будущем.\n"
            f"<i>Например: <code>{now.strftime('%d.%m')}</code>, <code>30.09</code> или <code>15.10.2026</code></i>",
            parse_mode=ParseMode.HTML,
        )
        return
    elif err == "invalid_date":
        await message.answer(
            "⚠️ <b>Некорректная дата!</b> Такого дня нет в календаре.\n"
            "Попробуйте еще раз (например, <code>30.09</code> или <code>15.10.2026</code>):",
            parse_mode=ParseMode.HTML,
        )
        return
    elif err == "invalid_format" or target_date is None:
        await message.answer(
            "⚠️ <b>Не удалось распознать дату.</b>\n\n"
            "Пожалуйста, введите дату в формате <b>ДД.ММ</b> или <b>ДД.ММ.ГГГГ</b> (например: <code>30.09</code> или <code>15.10.2026</code>):",
            parse_mode=ParseMode.HTML,
        )
        return

    await state.update_data(onetime_date=target_date.isoformat())
    await state.set_state(CreateReminderFSM.choosing_onetime_mode)
    await cleanup_previous_wizard_message(message, state)

    sent = await message.answer(
        f"📅 Выбранная дата: <b>{target_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"⚙️ <b>Как напомнить в этот день?</b>\n\n"
        f"• 🔔 <b>1 раз в определенное время</b> — пришлёт ровно одно напоминание в назначенный час.\n"
        f"• 🔁 <b>Повторяющиеся напоминания</b> — будет напоминать каждые X минут в заданном диапазоне времени, пока вы не нажмёте «✅ Сделано!» (или до конца дня).",
        reply_markup=get_onetime_mode_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await state.update_data(wizard_msg_id=sent.message_id)


@router.callback_query(
    CreateReminderFSM.choosing_onetime_mode, F.data == "onetime_mode:once"
)
async def process_onetime_mode_once(callback: CallbackQuery, state: FSMContext):
    """Выбор режима: 1 раз в точное время."""
    data = await state.get_data()
    target_date = date.fromisoformat(data["onetime_date"])
    await state.set_state(CreateReminderFSM.waiting_for_onetime_exact_time)
    await callback.message.edit_text(
        f"📅 Дата: <b>{target_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"🕐 <b>Во сколько отправить напоминание?</b>\n\n"
        f"Выберите время кнопкой или напишите своё в формате <b>ЧЧ:ММ</b> (например, <code>14:30</code>):",
        reply_markup=get_exact_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.choosing_onetime_mode, F.data == "onetime_mode:repeating"
)
async def process_onetime_mode_repeating(callback: CallbackQuery, state: FSMContext):
    """Выбор режима: повторяющиеся напоминания в течение дня."""
    data = await state.get_data()
    target_date = date.fromisoformat(data["onetime_date"])
    await state.set_state(CreateReminderFSM.waiting_for_onetime_start_time)
    await callback.message.edit_text(
        f"📅 Дата: <b>{target_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"🕐 <b>С какого времени начинать напоминать?</b>\n"
        f"<i>(Например, если выбрать «С 09:00», бот в этот день начнёт присылать напоминания с 9 утра по вашему поясу и повторять их, пока вы не нажмёте ✅)</i>",
        reply_markup=get_start_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.waiting_for_onetime_exact_time, F.data.startswith("exacttime:")
)
async def process_onetime_exact_time_choice(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Выбор готового точного времени для одноразового напоминания."""
    val = callback.data.split(":", 1)[1]
    if val == "custom":
        await callback.message.edit_text(
            "✏️ Напишите точное время напоминания в формате <b>ЧЧ:ММ</b> (например, <code>14:30</code>):",
            reply_markup=get_wizard_cancel_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    u_repo = user_repo or db.users
    now = get_now_for_user(callback.from_user.id, u_repo)
    data = await state.get_data()
    target_date = date.fromisoformat(data["onetime_date"])

    sh, sm = map(int, val.split(":"))
    chosen_time = time(sh, sm)

    if target_date == now.date() and chosen_time <= now.time():
        await callback.answer(
            f"⚠️ Время {val} на сегодня уже прошло! Сейчас {now.strftime('%H:%M')}.",
            show_alert=True,
        )
        return

    start_dt = datetime.combine(target_date, chosen_time).replace(tzinfo=now.tzinfo)
    await state.update_data(
        start_datetime=start_dt.isoformat(),
        start_time=val,
        end_time=val,
    )
    await finalize_wizard(
        callback.message,
        state,
        interval_minutes=0,
        is_callback=True,
        reminder_repo=reminder_repo,
        user_repo=user_repo,
    )
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_onetime_exact_time)
async def process_onetime_custom_exact_time_text(
    message: Message,
    state: FSMContext,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Ручной ввод точного времени для одноразового напоминания."""
    text = message.text.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not m:
        await message.answer(
            "Некорректный формат! Введите время в виде <b>ЧЧ:ММ</b> (например, <code>14:30</code>):",
            parse_mode=ParseMode.HTML,
        )
        return

    h, m_val = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= m_val <= 59):
        await message.answer(
            "Неверные часы или минуты. Введите время от 00:00 до 23:59."
        )
        return

    u_repo = user_repo or db.users
    now = get_now_for_user(message.from_user.id, u_repo)
    data = await state.get_data()
    target_date = date.fromisoformat(data["onetime_date"])
    chosen_time = time(h, m_val)

    if target_date == now.date() and chosen_time <= now.time():
        await message.answer(
            f"⚠️ Время <b>{h:02d}:{m_val:02d}</b> на сегодня уже прошло! "
            f"Сейчас <b>{now.strftime('%H:%M')}</b>. Пожалуйста, введите время в будущем:",
            parse_mode=ParseMode.HTML,
        )
        return

    exact_time_str = f"{h:02d}:{m_val:02d}"
    start_dt = datetime.combine(target_date, chosen_time).replace(tzinfo=now.tzinfo)
    await state.update_data(
        start_datetime=start_dt.isoformat(),
        start_time=exact_time_str,
        end_time=exact_time_str,
    )
    await cleanup_previous_wizard_message(message, state)
    await finalize_wizard(
        message,
        state,
        interval_minutes=0,
        is_callback=False,
        reminder_repo=reminder_repo,
        user_repo=user_repo,
    )


@router.callback_query(
    CreateReminderFSM.waiting_for_onetime_start_time, F.data.startswith("starttime:")
)
async def process_onetime_start_time_choice(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: Optional[IUserRepository] = None,
):
    """Выбор готового времени начала для повторяющегося одноразового напоминания."""
    val = callback.data.split(":", 1)[1]
    if val == "custom":
        await callback.message.edit_text(
            "✏️ Напишите время начала в формате <b>ЧЧ:ММ</b> (например, <code>09:30</code> или <code>14:00</code>):",
            reply_markup=get_wizard_cancel_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    start_time_str = "00:00" if val in ("00:00", "day_start") else val
    sh, sm = map(int, start_time_str.split(":"))

    u_repo = user_repo or db.users
    now = get_now_for_user(callback.from_user.id, u_repo)
    data = await state.get_data()
    target_date = date.fromisoformat(data["onetime_date"])

    start_dt = datetime.combine(target_date, time(sh, sm)).replace(tzinfo=now.tzinfo)
    await state.update_data(
        start_datetime=start_dt.isoformat(),
        start_time=start_time_str,
    )
    await state.set_state(CreateReminderFSM.waiting_for_onetime_end_time)
    await callback.message.edit_text(
        f"📅 Дата: <b>{target_date.strftime('%d.%m.%Y')}</b>\n"
        f"🕐 Начало: <b>с {start_time_str}</b>\n\n"
        f"🛑 <b>До скольки напоминать?</b>\n"
        f"<i>(После этого времени бот перестанет присылать повторные сообщения)</i>",
        reply_markup=get_onetime_end_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_onetime_start_time)
async def process_onetime_custom_start_time_text(
    message: Message,
    state: FSMContext,
    user_repo: Optional[IUserRepository] = None,
):
    """Ручной ввод времени начала для повторяющегося одноразового напоминания."""
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
    u_repo = user_repo or db.users
    now = get_now_for_user(message.from_user.id, u_repo)
    data = await state.get_data()
    target_date = date.fromisoformat(data["onetime_date"])

    start_dt = datetime.combine(target_date, time(h, m_val)).replace(tzinfo=now.tzinfo)
    await state.update_data(
        start_datetime=start_dt.isoformat(),
        start_time=start_time_str,
    )
    await state.set_state(CreateReminderFSM.waiting_for_onetime_end_time)
    await cleanup_previous_wizard_message(message, state)

    sent = await message.answer(
        f"📅 Дата: <b>{target_date.strftime('%d.%m.%Y')}</b>\n"
        f"🕐 Начало: <b>с {start_time_str}</b>\n\n"
        f"🛑 <b>До скольки напоминать?</b>\n"
        f"<i>(После этого времени бот перестанет присылать повторные сообщения)</i>",
        reply_markup=get_onetime_end_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await state.update_data(wizard_msg_id=sent.message_id)


# --- СОВМЕСТИМОСТЬ СО СТАРЫМИ СОСТОЯНИЯМИ ОДНОРАЗОВЫХ НАПОМИНАНИЙ ---


@router.callback_query(
    CreateReminderFSM.waiting_for_onetime_dt, F.data.startswith("quicktime:")
)
async def process_quick_onetime_legacy(
    callback: CallbackQuery,
    state: FSMContext,
    user_repo: Optional[IUserRepository] = None,
):
    """Fallback обработчик для quicktime при миграции."""
    u_repo = user_repo or db.users
    now = get_now_for_user(callback.from_user.id, u_repo)
    target_dt = now + timedelta(minutes=10)
    await state.update_data(start_datetime=target_dt.isoformat())
    await state.set_state(CreateReminderFSM.waiting_for_onetime_end_time)
    await callback.message.edit_text(
        f"🕐 Напоминание: <b>{target_dt.strftime('%d.%m.%Y %H:%M')}</b>",
        reply_markup=get_onetime_end_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_onetime_dt)
async def process_manual_onetime_dt_legacy(
    message: Message,
    state: FSMContext,
    user_repo: Optional[IUserRepository] = None,
):
    """Fallback ввод для устаревшего waiting_for_onetime_dt."""
    u_repo = user_repo or db.users
    now = get_now_for_user(message.from_user.id, u_repo)
    parsed_dt = parse_time_or_delay(message.text, now) or (now + timedelta(minutes=10))
    await cleanup_previous_wizard_message(message, state)
    sent = await message.answer(
        f"🕐 Напоминание: <b>{parsed_dt.strftime('%d.%m.%Y %H:%M')}</b>",
        reply_markup=get_onetime_end_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await state.update_data(
        start_datetime=parsed_dt.isoformat(), wizard_msg_id=sent.message_id
    )
    await state.set_state(CreateReminderFSM.waiting_for_onetime_end_time)
