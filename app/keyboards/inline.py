"""
Фасад инлайн-клавиатур (для обратной совместимости).
Реализации вынесены в специализированные модули:
- app.keyboards.wizard
- app.keyboards.reminder
- app.keyboards.timezone
"""

from app.keyboards.reminder import (
    get_done_keyboard,
    get_reminder_control_keyboard,
)
from app.keyboards.timezone import get_timezone_inline_keyboard
from app.keyboards.wizard import (
    get_days_keyboard,
    get_end_time_keyboard,
    get_exact_time_keyboard,
    get_interval_keyboard,
    get_onetime_date_keyboard,
    get_onetime_end_time_keyboard,
    get_onetime_mode_keyboard,
    get_onetime_quick_keyboard,
    get_recurring_mode_keyboard,
    get_start_time_keyboard,
    get_type_keyboard,
    get_wizard_cancel_keyboard,
)

__all__ = [
    "get_days_keyboard",
    "get_done_keyboard",
    "get_end_time_keyboard",
    "get_exact_time_keyboard",
    "get_interval_keyboard",
    "get_onetime_date_keyboard",
    "get_onetime_end_time_keyboard",
    "get_onetime_mode_keyboard",
    "get_onetime_quick_keyboard",
    "get_recurring_mode_keyboard",
    "get_reminder_control_keyboard",
    "get_start_time_keyboard",
    "get_timezone_inline_keyboard",
    "get_type_keyboard",
    "get_wizard_cancel_keyboard",
]
