import html

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.wizard import get_type_keyboard, get_wizard_cancel_keyboard
from app.states import CreateReminderFSM
from app.handlers.wizard.helpers import cleanup_previous_wizard_message

router = Router(name="wizard_common")


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
