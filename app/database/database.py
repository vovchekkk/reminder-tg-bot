from typing import Any, Dict, List, Optional

from app.config import DB_PATH
from app.database.connection import DatabaseConnectionManager
from app.database.repositories import (
    SqliteReminderRepository,
    SqliteSystemSettingsRepository,
    SqliteUserRepository,
)
from app.domain.interfaces import (
    IReminderRepository,
    ISystemSettingsRepository,
    IUserRepository,
)


class Database:
    """
    Фасад базы данных для сохранения обратной совместимости.
    Объединяет специализированные репозитории: users, reminders, system.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.connection = DatabaseConnectionManager(db_path)
        self.users: IUserRepository = SqliteUserRepository(self.connection)
        self.reminders: IReminderRepository = SqliteReminderRepository(self.connection)
        self.system: ISystemSettingsRepository = SqliteSystemSettingsRepository(self.connection)

    # Делегирование для обратной совместимости
    def get_system_setting(self, key: str) -> Optional[str]:
        return self.system.get_setting(key)

    def set_system_setting(self, key: str, value: str) -> None:
        self.system.set_setting(key, value)

    def get_all_user_ids(self) -> List[int]:
        return self.users.get_all_user_ids()

    def get_user_timezone(self, user_id: int) -> str:
        return self.users.get_user_timezone(user_id)

    def has_user_timezone(self, user_id: int) -> bool:
        return self.users.has_user_timezone(user_id)

    def set_user_timezone(self, user_id: int, timezone_name: str) -> None:
        self.users.set_user_timezone(user_id, timezone_name)

    def add_reminder(
        self,
        user_id: int,
        text: str,
        reminder_type: str,
        interval_minutes: int = 60,
        days_of_week: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        start_datetime: Optional[str] = None,
    ) -> int:
        return self.reminders.add_reminder(
            user_id=user_id,
            text=text,
            reminder_type=reminder_type,
            interval_minutes=interval_minutes,
            days_of_week=days_of_week,
            start_time=start_time,
            end_time=end_time,
            start_datetime=start_datetime,
        )

    def get_reminder(self, reminder_id: int) -> Optional[Dict[str, Any]]:
        return self.reminders.get_reminder(reminder_id)

    def get_user_reminders(self, user_id: int) -> List[Dict[str, Any]]:
        return self.reminders.get_user_reminders(user_id)

    def get_active_reminders(self) -> List[Dict[str, Any]]:
        return self.reminders.get_active_reminders()

    def toggle_active(self, reminder_id: int, user_id: int) -> Optional[bool]:
        return self.reminders.toggle_active(reminder_id, user_id)

    def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        return self.reminders.delete_reminder(reminder_id, user_id)

    def mark_completed_today(self, reminder_id: int, today_str: str) -> None:
        self.reminders.mark_completed_today(reminder_id, today_str)

    def mark_completed_permanently(self, reminder_id: int) -> None:
        self.reminders.mark_completed_permanently(reminder_id)

    def update_last_reminded(self, reminder_id: int, reminded_iso: str) -> None:
        self.reminders.update_last_reminded(reminder_id, reminded_iso)


# Глобальный экземпляр по умолчанию
db = Database()
