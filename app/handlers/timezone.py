from datetime import datetime

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database import db
from app.keyboards import get_main_keyboard, get_timezone_inline_keyboard
from app.services.time_utils import get_now_for_user, get_user_tz_obj
from app.states import TimezoneSettingsFSM

router = Router(name="timezone")


@router.message(Command("timezone"))
@router.message(F.text == "⚙️ Часовой пояс")
async def show_timezone_settings(message: Message, state: FSMContext):
    """Показывает меню выбора часового пояса."""
    await state.clear()
    user_now = get_now_for_user(message.from_user.id, db)
    user_tz = db.get_user_timezone(message.from_user.id)
    now_str = user_now.strftime("%d.%m.%Y %H:%M")

    prompt = (
        f"⚙️ <b>Настройка часового пояса</b>\n\n"
        f"🌍 Текущий пояс: <code>{user_tz}</code>\n"
        f"🕒 Ваше время сейчас: <b>{now_str}</b>\n\n"
        f"Выберите ваш регион из списка ниже или введите смещение вручную:"
    )
    await message.answer(
        prompt,
        reply_markup=get_timezone_inline_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith("settz:"))
async def process_timezone_button(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор города или запрос на ручной ввод пояса."""
    val = callback.data.split(":")[1]

    if val == "manual":
        await state.set_state(TimezoneSettingsFSM.waiting_for_manual_tz)
        text = (
            "✏️ Введите ваш часовой пояс текстом:\n\n"
            "Примеры:\n"
            "• Смещение: <code>+5</code>, <code>+3</code>, <code>-4</code>\n"
            "• Формат UTC: <code>UTC+5</code>, <code>UTC+03:00</code>\n"
            "• Название: <code>Europe/Moscow</code>, <code>Asia/Yekaterinburg</code>"
        )
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML)
        await callback.answer()
        return

    # Сохраняем выбранный из списка часовой пояс
    db.set_user_timezone(callback.from_user.id, val)
    user_now = get_now_for_user(callback.from_user.id, db)
    now_str = user_now.strftime("%d.%m.%Y %H:%M")

    await callback.answer("✅ Часовой пояс сохранён!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        f"✅ <b>Часовой пояс установлен:</b> <code>{val}</code>\n"
        f"🕒 Ваше местное время: <b>{now_str}</b>\n\n"
        f"🎉 Теперь все напоминания будут приходить строго по вашему времени!\n"
        f"Нажмите кнопку <b>«➕ Создать напоминание»</b> ниже, чтобы добавить первую задачу 👇",
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.message(TimezoneSettingsFSM.waiting_for_manual_tz)
async def process_manual_tz_input(message: Message, state: FSMContext):
    """Обрабатывает введённый вручную часовой пояс."""
    tz_text = message.text.strip()
    try:
        tz_obj = get_user_tz_obj(tz_text)
        now_test = datetime.now(tz_obj)
        db.set_user_timezone(message.from_user.id, tz_text)
        await state.clear()

        await message.answer(
            f"✅ <b>Часовой пояс успешно установлен:</b> <code>{tz_text}</code>\n"
            f"🕒 Ваше местное время: <b>{now_test.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"Все напоминания будут приходить строго по этому времени!",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await message.answer(
            "⚠️ Не удалось распознать часовой пояс. Попробуйте еще раз (например, <code>+5</code> или <code>Europe/Moscow</code>):",
            parse_mode=ParseMode.HTML,
        )
