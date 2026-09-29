from aiogram.fsm.state import State, StatesGroup


class CreateReminderFSM(StatesGroup):
    waiting_for_text = State()
    choosing_type = State()
    choosing_days = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_onetime_dt = State()
    waiting_for_onetime_end_time = State()
    choosing_interval = State()
    waiting_for_custom_interval = State()


class TimezoneSettingsFSM(StatesGroup):
    waiting_for_manual_tz = State()
