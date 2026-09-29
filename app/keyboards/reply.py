from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная постоянная клавиатура бота."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Создать напоминание"),
                KeyboardButton(text="📋 Мои напоминания"),
            ],
            [
                KeyboardButton(text="⚙️ Часовой пояс"),
                KeyboardButton(text="ℹ️ Помощь"),
            ],
        ],
        resize_keyboard=True,
    )
