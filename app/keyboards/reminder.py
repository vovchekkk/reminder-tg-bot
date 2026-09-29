from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_done_keyboard(reminder_id: int, is_test: bool = False) -> InlineKeyboardMarkup:
    """Кнопка подтверждения выполнения напоминания."""
    cb_data = f"done_test:{reminder_id}" if is_test else f"done:{reminder_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Сделано!",
                    callback_data=cb_data,
                )
            ]
        ]
    )


def get_reminder_control_keyboard(reminder: dict) -> InlineKeyboardMarkup:
    """Кнопки управления карточкой напоминания."""
    rem_id = reminder["id"]
    is_active = reminder["is_active"]
    toggle_text = "⏸️ Приостановить" if is_active else "▶️ Включить"

    buttons = [
        [
            InlineKeyboardButton(
                text=toggle_text, callback_data=f"toggle_active:{rem_id}"
            ),
            InlineKeyboardButton(
                text="🔔 Проверить сейчас",
                callback_data=f"test_trigger:{rem_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ Удалить", callback_data=f"delete_rem:{rem_id}"
            ),
            InlineKeyboardButton(
                text="🔙 К списку", callback_data="refresh_list"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
