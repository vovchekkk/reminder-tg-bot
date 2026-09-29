from aiogram.fsm.state import State, StatesGroup


class CreateReminderFSM(StatesGroup):
    waiting_for_text = State()
    choosing_type = State()
    choosing_days = State()
    choosing_recurring_mode = State()
    waiting_for_exact_time = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_onetime_date = State()
    choosing_onetime_mode = State()
    waiting_for_onetime_exact_time = State()
    waiting_for_onetime_start_time = State()
    waiting_for_onetime_dt = State()
    waiting_for_onetime_end_time = State()
    choosing_interval = State()
    waiting_for_custom_interval = State()


class TimezoneSettingsFSM(StatesGroup):
    waiting_for_manual_tz = State()
