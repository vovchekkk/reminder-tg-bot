from datetime import datetime
from typing import Any, Dict

from app.domain.interfaces import IReminderStrategy
from app.services.time_utils import is_time_in_range, safe_fromisoformat


class RecurringReminderStrategy(IReminderStrategy):
    """Стратегия для повторяющихся напоминаний (по дням недели)."""

    def should_remind(self, reminder: Dict[str, Any], now: datetime) -> bool:
        today_str = now.strftime("%Y-%m-%d")

        # 1. Проверка дня недели
        if reminder.get("days_of_week"):
            days = [
                int(d)
                for d in reminder["days_of_week"].split(",")
                if d.strip().isdigit()
            ]
            if now.weekday() not in days:
                return False

        # 2. Проверка, было ли сегодня уже отмечено как сделанное
        if reminder.get("last_completed_date") == today_str:
            return False

        interval = reminder.get("interval_minutes", 60)

        # 3. Режим: 1 раз в день в точное время (interval_minutes == 0)
        if interval == 0:
            last_reminded = reminder.get("last_reminded_at")
            if last_reminded:
                last_reminded_dt = safe_fromisoformat(last_reminded, tz_obj=now.tzinfo)
                if last_reminded_dt.date() == now.date():
                    return False  # Сегодня уже было отправлено

            # Проверяем, наступило ли запланированное время
            start_time_str = reminder.get("start_time")
            if start_time_str:
                try:
                    sh, sm = map(int, start_time_str.split(":"))
                    from datetime import time

                    if now.time() < time(sh, sm, 0):
                        return False
                except Exception:
                    pass
            return True

        # 4. Режим: повторяющиеся напоминания в течение дня
        # Проверка диапазона времени [start_time, end_time]
        if not is_time_in_range(
            reminder.get("start_time"), reminder.get("end_time"), now.time()
        ):
            return False

        # Проверка интервала с момента последнего напоминания
        last_reminded = reminder.get("last_reminded_at")
        if not last_reminded:
            return True

        last_reminded_dt = safe_fromisoformat(last_reminded, tz_obj=now.tzinfo)
        if last_reminded_dt.date() < now.date():
            return True

        elapsed_minutes = (now - last_reminded_dt).total_seconds() / 60
        return elapsed_minutes >= interval



class OneTimeReminderStrategy(IReminderStrategy):
    """Стратегия для одноразовых напоминаний."""

    def should_remind(self, reminder: Dict[str, Any], now: datetime) -> bool:
        if reminder.get("is_completed"):
            return False

        start_dt_str = reminder.get("start_datetime")
        if not start_dt_str:
            return False

        start_dt = safe_fromisoformat(start_dt_str, tz_obj=now.tzinfo)
        if now < start_dt:
            return False

        # Ограничение по времени дня (если задано)
        if reminder.get("end_time"):
            if not is_time_in_range(None, reminder.get("end_time"), now.time()):
                return False

        last_reminded = reminder.get("last_reminded_at")
        if not last_reminded:
            return True

        last_reminded_dt = safe_fromisoformat(last_reminded, tz_obj=now.tzinfo)
        elapsed_minutes = (now - last_reminded_dt).total_seconds() / 60
        return elapsed_minutes >= reminder.get("interval_minutes", 60)


class ReminderEvaluator:
    """
    Фабрика/реестр стратегий (Open/Closed Principle).
    Позволяет добавлять новые типы напоминаний без изменения существующего кода.
    """

    def __init__(self):
        self._strategies: Dict[str, IReminderStrategy] = {
            "recurring": RecurringReminderStrategy(),
            "one_time": OneTimeReminderStrategy(),
        }

    def register_strategy(self, reminder_type: str, strategy: IReminderStrategy) -> None:
        """Регистрация новой стратегии для расширения функционала."""
        self._strategies[reminder_type] = strategy

    def is_due(self, reminder: Dict[str, Any], now: datetime) -> bool:
        """Определяет, наступило ли время отправки напоминания."""
        reminder_type = reminder.get("reminder_type")
        strategy = self._strategies.get(reminder_type)
        if not strategy:
            return False
        return strategy.should_remind(reminder, now)
