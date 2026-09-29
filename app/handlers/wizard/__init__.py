"""
Пакет мастера создания напоминания (Wizard).
Декомпозирован на независимые модули по принципу единственной ответственности (SRP):
- common: входные точки, отмена, обработка текста
- recurring: выбор дней недели, режимов и времени
- onetime: выбор даты (числа), года, режимов и времени одноразового напоминания
- interval: выбор интервалов и времени окончания
- helpers: вспомогательные функции очистки и финализации
"""

from aiogram import Router

from app.handlers.wizard.common import (
    cancel_wizard,
    process_reminder_text,
    router as common_router,
    start_wizard,
)
from app.handlers.wizard.helpers import cleanup_previous_wizard_message, finalize_wizard
from app.handlers.wizard.interval import (
    process_custom_interval_text,
    process_custom_onetime_end_text,
    process_interval_choice,
    process_onetime_end_choice,
    prompt_interval_selection,
    router as interval_router,
)
from app.handlers.wizard.onetime import (
    choose_onetime_type,
    process_manual_onetime_dt_legacy,
    process_onetime_custom_exact_time_text,
    process_onetime_custom_start_time_text,
    process_onetime_date_callback,
    process_onetime_date_text,
    process_onetime_exact_time_choice,
    process_onetime_mode_once,
    process_onetime_mode_repeating,
    process_onetime_start_time_choice,
    process_quick_onetime_legacy,
    router as onetime_router,
)
from app.handlers.wizard.recurring import (
    choose_recurring_type,
    days_confirmed,
    preset_days_action,
    process_custom_end_time_text,
    process_custom_exact_time_text,
    process_custom_start_time_text,
    process_end_time_choice,
    process_exact_time_choice,
    process_recmode_once,
    process_recmode_repeating,
    process_start_time_choice,
    router as recurring_router,
    toggle_day_selection,
)

router = Router(name="wizard")
router.include_router(common_router)
router.include_router(recurring_router)
router.include_router(onetime_router)
router.include_router(interval_router)

__all__ = [
    "cancel_wizard",
    "choose_onetime_type",
    "choose_recurring_type",
    "cleanup_previous_wizard_message",
    "days_confirmed",
    "finalize_wizard",
    "preset_days_action",
    "process_custom_end_time_text",
    "process_custom_exact_time_text",
    "process_custom_interval_text",
    "process_custom_onetime_end_text",
    "process_custom_start_time_text",
    "process_end_time_choice",
    "process_exact_time_choice",
    "process_interval_choice",
    "process_manual_onetime_dt_legacy",
    "process_onetime_custom_exact_time_text",
    "process_onetime_custom_start_time_text",
    "process_onetime_date_callback",
    "process_onetime_date_text",
    "process_onetime_end_choice",
    "process_onetime_exact_time_choice",
    "process_onetime_mode_once",
    "process_onetime_mode_repeating",
    "process_onetime_start_time_choice",
    "process_quick_onetime_legacy",
    "process_recmode_once",
    "process_recmode_repeating",
    "process_reminder_text",
    "process_start_time_choice",
    "prompt_interval_selection",
    "router",
    "start_wizard",
    "toggle_day_selection",
]
