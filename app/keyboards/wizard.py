from datetime import datetime, timedelta
from typing import Set

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import DAYS_NAMES


def get_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа напоминания (по дням или одноразовое)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔁 По дням недели", callback_data="type:recurring"
                ),
                InlineKeyboardButton(
                    text="⏱️ Одноразовое", callback_data="type:one_time"
                ),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_days_keyboard(selected_days: Set[int]) -> InlineKeyboardMarkup:
    """Сетка кнопок выбора дней недели с пресетами."""
    row1 = []
    for day_idx in range(4):
        mark = "✅ " if day_idx in selected_days else "⬜ "
        name = DAYS_NAMES[day_idx][0]
        row1.append(
            InlineKeyboardButton(
                text=f"{mark}{name}", callback_data=f"toggle_day:{day_idx}"
            )
        )

    row2 = []
    for day_idx in range(4, 7):
        mark = "✅ " if day_idx in selected_days else "⬜ "
        name = DAYS_NAMES[day_idx][0]
        row2.append(
            InlineKeyboardButton(
                text=f"{mark}{name}", callback_data=f"toggle_day:{day_idx}"
            )
        )

    sel_text = (
        ", ".join(DAYS_NAMES[d][0] for d in sorted(selected_days))
        if selected_days
        else "не выбрано"
    )

    action_row1 = [
        InlineKeyboardButton(
            text="Выбрать все", callback_data="preset_days:all"
        ),
        InlineKeyboardButton(
            text="Выбрать будни", callback_data="preset_days:weekdays"
        ),
    ]

    action_row2 = [
        InlineKeyboardButton(
            text="Выбрать выходные", callback_data="preset_days:weekends"
        ),
        InlineKeyboardButton(
            text="Сброс", callback_data="preset_days:clear"
        ),
    ]

    confirm_row = [
        InlineKeyboardButton(
            text=f"➡️ Далее ({sel_text})", callback_data="days_confirmed"
        )
    ]

    cancel_row = [
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")
    ]

    return InlineKeyboardMarkup(
        inline_keyboard=[row1, row2, action_row1, action_row2, confirm_row, cancel_row]
    )


def get_recurring_mode_keyboard() -> InlineKeyboardMarkup:
    """Выбор режима повторяющегося напоминания: 1 раз в день или с интервалом."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 1 раз в день в точное время",
                    callback_data="recmode:once",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔁 С повторами в течение дня",
                    callback_data="recmode:repeating",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_exact_time_keyboard() -> InlineKeyboardMarkup:
    """Выбор точного времени для напоминания 1 раз в день."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="08:00", callback_data="exacttime:08:00"),
                InlineKeyboardButton(text="09:00", callback_data="exacttime:09:00"),
                InlineKeyboardButton(text="10:00", callback_data="exacttime:10:00"),
            ],
            [
                InlineKeyboardButton(text="12:00", callback_data="exacttime:12:00"),
                InlineKeyboardButton(text="14:00", callback_data="exacttime:14:00"),
                InlineKeyboardButton(text="16:00", callback_data="exacttime:16:00"),
            ],
            [
                InlineKeyboardButton(text="18:00", callback_data="exacttime:18:00"),
                InlineKeyboardButton(text="20:00", callback_data="exacttime:20:00"),
                InlineKeyboardButton(text="21:00", callback_data="exacttime:21:00"),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Ввести другое время",
                    callback_data="exacttime:custom",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_start_time_keyboard() -> InlineKeyboardMarkup:
    """Выбор времени начала показа напоминания."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="С начала дня", callback_data="starttime:00:00"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="С 08:00", callback_data="starttime:08:00"
                ),
                InlineKeyboardButton(
                    text="С 09:00", callback_data="starttime:09:00"
                ),
                InlineKeyboardButton(
                    text="С 10:00", callback_data="starttime:10:00"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="С 12:00", callback_data="starttime:12:00"
                ),
                InlineKeyboardButton(
                    text="С 14:00", callback_data="starttime:14:00"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Ввести другое время",
                    callback_data="starttime:custom",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_end_time_keyboard() -> InlineKeyboardMarkup:
    """Выбор времени окончания показа напоминания."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="До 18:00", callback_data="endtime:18:00"
                ),
                InlineKeyboardButton(
                    text="До 20:00", callback_data="endtime:20:00"
                ),
                InlineKeyboardButton(
                    text="До 21:00", callback_data="endtime:21:00"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="До 22:00", callback_data="endtime:22:00"
                ),
                InlineKeyboardButton(
                    text="До 23:00", callback_data="endtime:23:00"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="До конца дня", callback_data="endtime:23:59"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Ввести другое время",
                    callback_data="endtime:custom",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_onetime_date_keyboard(now: datetime) -> InlineKeyboardMarkup:
    """Выбор даты для одноразового напоминания."""
    d_today = now.date()
    d_tomorrow = d_today + timedelta(days=1)
    d_after = d_today + timedelta(days=2)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📅 Сегодня ({d_today.strftime('%d.%m')})",
                    callback_data=f"setdate:{d_today.isoformat()}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📅 Завтра ({d_tomorrow.strftime('%d.%m')})",
                    callback_data=f"setdate:{d_tomorrow.isoformat()}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📅 Послезавтра ({d_after.strftime('%d.%m')})",
                    callback_data=f"setdate:{d_after.isoformat()}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Ввести другую дату или год вручную",
                    callback_data="setdate:custom",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_onetime_mode_keyboard() -> InlineKeyboardMarkup:
    """Выбор режима для одноразового напоминания: 1 раз в точное время или повторяющееся."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 1 раз в определенное время",
                    callback_data="onetime_mode:once",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔁 Повторяющиеся напоминания",
                    callback_data="onetime_mode:repeating",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_onetime_end_time_keyboard() -> InlineKeyboardMarkup:
    """Выбор времени окончания для одноразового напоминания."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="До 20:00", callback_data="onetime_end:20:00"
                ),
                InlineKeyboardButton(
                    text="До 21:00", callback_data="onetime_end:21:00"
                ),
                InlineKeyboardButton(
                    text="До 22:00", callback_data="onetime_end:22:00"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="До 23:00", callback_data="onetime_end:23:00"
                ),
                InlineKeyboardButton(
                    text="До конца дня", callback_data="onetime_end:23:59"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Без ограничений", callback_data="onetime_end:none"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Ввести другое время",
                    callback_data="onetime_end:custom",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_onetime_quick_keyboard() -> InlineKeyboardMarkup:
    """Быстрый выбор времени старта для одноразового напоминания."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Через 10 мин", callback_data="quicktime:+10m"
                ),
                InlineKeyboardButton(
                    text="Через 30 мин", callback_data="quicktime:+30m"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Через 1 час", callback_data="quicktime:+1h"
                ),
                InlineKeyboardButton(
                    text="Через 2 часа", callback_data="quicktime:+2h"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Сегодня в 18:00", callback_data="quicktime:18:00"
                ),
                InlineKeyboardButton(
                    text="Завтра в 09:00", callback_data="quicktime:tomorrow_09"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Ввести время текстом", callback_data="quicktime:manual"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_interval_keyboard() -> InlineKeyboardMarkup:
    """Выбор частоты повтора напоминания."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="15 минут", callback_data="interval:15"
                ),
                InlineKeyboardButton(
                    text="30 минут", callback_data="interval:30"
                ),
            ],
            [
                InlineKeyboardButton(text="1 час", callback_data="interval:60"),
                InlineKeyboardButton(
                    text="2 часа", callback_data="interval:120"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="3 часа", callback_data="interval:180"
                ),
                InlineKeyboardButton(
                    text="✏️ Свой интервал", callback_data="interval:custom"
                ),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_wizard_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены мастера создания."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")]
        ]
    )
