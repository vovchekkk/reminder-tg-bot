import re
from typing import Optional

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.domain.interfaces import IReminderRepository, IUserRepository
from app.keyboards.wizard import (
    get_days_keyboard,
    get_end_time_keyboard,
    get_exact_time_keyboard,
    get_recurring_mode_keyboard,
    get_start_time_keyboard,
)
from app.services.time_utils import format_days_list
from app.states import CreateReminderFSM
from app.handlers.wizard.helpers import cleanup_previous_wizard_message, finalize_wizard

router = Router(name="wizard_recurring")


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
    await state.set_state(CreateReminderFSM.choosing_recurring_mode)

    await callback.message.edit_text(
        f"📅 Выбранные дни: <b>{format_days_list(days_str)}</b>\n\n"
        f"⚙️ <b>Как напоминать в эти дни?</b>\n\n"
        f"• 🔔 <b>1 раз в день в точное время</b> — пришлёт ровно одно напоминание в назначенный час.\n"
        f"• 🔁 <b>Повторяющиеся напоминания</b> — будет напоминать каждые X минут в заданном диапазоне времени, пока вы не нажмёте «Сделано».",
        reply_markup=get_recurring_mode_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.choosing_recurring_mode, F.data == "recmode:once"
)
async def process_recmode_once(callback: CallbackQuery, state: FSMContext):
    """Выбор режима: 1 раз в день в точное время."""
    await state.set_state(CreateReminderFSM.waiting_for_exact_time)
    await callback.message.edit_text(
        "🕐 <b>Во сколько прислать напоминание в эти дни?</b>\n\n"
        "Выберите время кнопкой или напишите своё в формате <b>ЧЧ:ММ</b> (например, <code>10:00</code> или <code>14:30</code>):",
        reply_markup=get_exact_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.choosing_recurring_mode, F.data == "recmode:repeating"
)
async def process_recmode_repeating(callback: CallbackQuery, state: FSMContext):
    """Выбор режима: повторяющиеся напоминания в течение дня."""
    data = await state.get_data()
    days_str = data.get("days_of_week")
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
    CreateReminderFSM.waiting_for_exact_time, F.data.startswith("exacttime:")
)
async def process_exact_time_choice(
    callback: CallbackQuery,
    state: FSMContext,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Выбор готового точного времени для 1-разового ежедневного напоминания."""
    val = callback.data.split(":", 1)[1]
    if val == "custom":
        await callback.message.edit_text(
            "✏️ Напишите точное время напоминания в формате <b>ЧЧ:ММ</b> (например, <code>09:30</code> или <code>14:00</code>):",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    await state.update_data(start_time=val, end_time=val)
    await finalize_wizard(
        callback.message,
        state,
        interval_minutes=0,
        is_callback=True,
        reminder_repo=reminder_repo,
        user_repo=user_repo,
    )
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_exact_time)
async def process_custom_exact_time_text(
    message: Message,
    state: FSMContext,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Ручной ввод точного времени для 1-разового ежедневного напоминания."""
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

    exact_time_str = f"{h:02d}:{m_val:02d}"
    await state.update_data(start_time=exact_time_str, end_time=exact_time_str)
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

    start_time_str = "00:00" if val in ("00:00", "day_start") else val

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

    from app.handlers.wizard.interval import prompt_interval_selection
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

    from app.handlers.wizard.interval import prompt_interval_selection
    sent = await prompt_interval_selection(message, state, is_edit=False)
    if sent:
        await state.update_data(wizard_msg_id=sent.message_id)
