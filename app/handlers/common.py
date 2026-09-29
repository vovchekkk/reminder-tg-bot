from typing import Optional

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.database import db
from app.domain.interfaces import IUserRepository
from app.keyboards import get_main_keyboard, get_timezone_inline_keyboard
from app.services.time_utils import get_now_for_user

router = Router(name="common")


@router.message(CommandStart())
@router.message(Command("menu"))
@router.message(Command("refresh"))
@router.message(Command("reset"))
@router.message(F.text.lower().in_(["меню", "старт", "start", "обновить", "перезапуск"]))
async def cmd_start(
    message: Message,
    state: FSMContext,
    user_repo: Optional[IUserRepository] = None,
):
    """Стартовая команда или обновление главного меню."""
    await state.clear()
    u_repo = user_repo or db.users
    user_id = message.from_user.id
    user_now = get_now_for_user(user_id, u_repo)
    user_tz = u_repo.get_user_timezone(user_id)
    now_str = user_now.strftime("%d.%m.%Y %H:%M")

    if not u_repo.has_user_timezone(user_id):
        text = (
            f"👋 <b>Привет! Я бот-напоминалка с контролем выполнения!</b>\n\n"
            f"Чтобы напоминания приходили строго вовремя, пожалуйста, <b>выберите ваш часовой пояс</b> из списка ниже:\n\n"
            f"<i>(По умолчанию: <code>{user_tz}</code>, местное время: {now_str})</i>"
        )
        await message.answer(
            text,
            reply_markup=get_timezone_inline_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    else:
        text = (
            f"👋 <b>Главное меню обновлено!</b>\n\n"
            f"🌍 Ваш часовой пояс: <code>{user_tz}</code>\n"
            f"🕒 Местное время: <b>{now_str}</b>\n\n"
            f"Используйте кнопки меню внизу для создания и управления напоминаниями 👇"
        )
        await message.answer(
            text,
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    """Справка по боту."""
    text = (
        "📖 <b>Справка по использованию бота:</b>\n\n"
        "• <b>➕ Создать напоминание</b> — пошаговый конструктор любого напоминания:\n"
        "   - Свой текст сообщения\n"
        "   - Выбор дней недели или одноразовое напоминание\n"
        "   - Своя частота повторов (если не нажали ✅)\n"
        "   - Диапазон времени (со скольки и до скольки напоминать, чтобы не беспокоить ночью)\n\n"
        "• <b>⚙️ Часовой пояс</b> — настройка местного времени:\n"
        "   - Выбор из списка городов\n"
        "   - Ввод любого UTC смещения вручную\n\n"
        "• <b>📋 Мои напоминания</b> — список всех задач:\n"
        "   - Тестовая отправка прямо сейчас (кнопка «🔔 Проверить сейчас»)\n"
        "   - Пауза / возобновление\n"
        "   - Удаление\n\n"
        "• <b>Кнопка галочки «✅ Сделано!»</b>:\n"
        "   - Для повторяющихся: отключает напоминания до следующего назначенного дня.\n"
        "   - Для одноразовых: завершает задачу навсегда."
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


# Обработчик устаревших инлайн-кнопок после деплоя или сброса
async def fallback_expired_callback(callback: CallbackQuery, state: FSMContext):
    """Показывает предупреждение, если нажата старая кнопка с потерянным FSM состоянием."""
    await state.clear()
    await callback.answer(
        "⏳ Эта версия бота устарела.\nНажмите /start для обновления.",
        show_alert=True,
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
