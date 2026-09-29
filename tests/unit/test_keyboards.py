from app.keyboards import (
    get_days_keyboard,
    get_done_keyboard,
    get_end_time_keyboard,
    get_interval_keyboard,
    get_main_keyboard,
    get_onetime_date_keyboard,
    get_onetime_end_time_keyboard,
    get_onetime_mode_keyboard,
    get_onetime_quick_keyboard,
    get_reminder_control_keyboard,
    get_start_time_keyboard,
    get_timezone_inline_keyboard,
    get_type_keyboard,
    get_wizard_cancel_keyboard,
)


class TestKeyboards:
    def test_main_keyboard(self):
        kb = get_main_keyboard()
        buttons = [b.text for row in kb.keyboard for b in row]
        assert "➕ Создать напоминание" in buttons
        assert "📋 Мои напоминания" in buttons
        assert "⚙️ Часовой пояс" in buttons
        assert "ℹ️ Помощь" in buttons

    def test_timezone_keyboard(self):
        kb = get_timezone_inline_keyboard()
        callbacks = [b.callback_data for row in kb.inline_keyboard for b in row]
        assert any(c.startswith("settz:Europe/Moscow") for c in callbacks)
        assert any(c == "settz:manual" for c in callbacks)

    def test_days_keyboard(self):
        # Пустой выбор
        kb_empty = get_days_keyboard(set())
        texts_empty = [b.text for row in kb_empty.inline_keyboard for b in row]
        assert any("⬜ Пн" in t for t in texts_empty)

        # Выбран Пн (0) и Пт (4)
        kb_selected = get_days_keyboard({0, 4})
        texts_sel = [b.text for row in kb_selected.inline_keyboard for b in row]
        assert any("✅ Пн" in t for t in texts_sel)
        assert any("✅ Пт" in t for t in texts_sel)
        assert any("⬜ Вт" in t for t in texts_sel)

        # Проверка кнопок пресетов
        callbacks = [b.callback_data for row in kb_selected.inline_keyboard for b in row]
        assert "preset_days:all" in callbacks
        assert "preset_days:weekdays" in callbacks
        assert "preset_days:weekends" in callbacks
        assert "preset_days:clear" in callbacks
        assert "days_confirmed" in callbacks

    def test_start_and_end_time_keyboards(self):
        start_kb = get_start_time_keyboard()
        start_cbs = [b.callback_data for row in start_kb.inline_keyboard for b in row]
        assert "starttime:00:00" in start_cbs  # "С начала дня"
        assert "starttime:custom" in start_cbs
        assert "starttime:now" not in start_cbs  # "Прямо сейчас" удалено!

        end_kb = get_end_time_keyboard()
        end_cbs = [b.callback_data for row in end_kb.inline_keyboard for b in row]
        assert "endtime:23:59" in end_cbs  # "До конца дня"
        assert "endtime:custom" in end_cbs

    def test_done_keyboard_test_mode(self):
        kb_normal = get_done_keyboard(42, is_test=False)
        assert kb_normal.inline_keyboard[0][0].callback_data == "done:42"

        kb_test = get_done_keyboard(42, is_test=True)
        assert kb_test.inline_keyboard[0][0].callback_data == "done_test:42"


    def test_reminder_control_keyboard(self):
        rem_active = {"id": 42, "is_active": 1}
        kb_active = get_reminder_control_keyboard(rem_active)
        cbs_active = [b.callback_data for row in kb_active.inline_keyboard for b in row]
        texts_active = [b.text for row in kb_active.inline_keyboard for b in row]
        assert "toggle_active:42" in cbs_active
        assert any("Приостановить" in t for t in texts_active)

        rem_paused = {"id": 42, "is_active": 0}
        kb_paused = get_reminder_control_keyboard(rem_paused)
        texts_paused = [b.text for row in kb_paused.inline_keyboard for b in row]
        assert any("Включить" in t for t in texts_paused)

    def test_onetime_date_and_mode_keyboards(self):
        from datetime import datetime, timezone
        now = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        kb_date = get_onetime_date_keyboard(now)
        cbs_date = [b.callback_data for row in kb_date.inline_keyboard for b in row]
        assert "setdate:2026-09-29" in cbs_date
        assert "setdate:2026-09-30" in cbs_date
        assert "setdate:2026-10-01" in cbs_date
        assert "setdate:custom" in cbs_date
        assert "cancel_wizard" in cbs_date

        kb_mode = get_onetime_mode_keyboard()
        cbs_mode = [b.callback_data for row in kb_mode.inline_keyboard for b in row]
        assert "onetime_mode:once" in cbs_mode
        assert "onetime_mode:repeating" in cbs_mode
        assert "cancel_wizard" in cbs_mode

