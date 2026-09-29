from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import POPULAR_TIMEZONES


def get_timezone_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-кнопки с популярными часовыми поясами (Single Responsibility)."""
    buttons = []
    row = []
    for label, tz_name in POPULAR_TIMEZONES:
        row.append(
            InlineKeyboardButton(text=label, callback_data=f"settz:{tz_name}")
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(
                text="✏️ Ввести свой пояс или UTC вручную",
                callback_data="settz:manual",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)
