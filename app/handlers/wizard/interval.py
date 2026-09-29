import re
from typing import Optional

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.domain.interfaces import IReminderRepository, IUserRepository
from app.keyboards.wizard import get_interval_keyboard
from app.states import CreateReminderFSM
from app.handlers.wizard.helpers import cleanup_previous_wizard_message, finalize_wizard

router = Router(name="wizard_interval")


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
    await finalize_wizard(
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
    await finalize_wizard(
        message,
        state,
        minutes,
        is_callback=False,
        reminder_repo=reminder_repo,
        user_repo=user_repo,
    )
