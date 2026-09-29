from typing import Any, Dict, List, Optional

from app.domain.interfaces import IReminderRepository, IUserRepository


class ReminderService:
    """
    Application Service для координации бизнес-логики напоминаний (SRP & DIP).
    Изолирует хэндлеры от деталей хранилища данных.
    """

    def __init__(
        self,
        reminder_repo: IReminderRepository,
        user_repo: Optional[IUserRepository] = None,
    ):
        self._reminder_repo = reminder_repo
        self._user_repo = user_repo

    def create_reminder_from_wizard(
        self, user_id: int, data: Dict[str, Any], interval_minutes: int
    ) -> int:
        """Создает и сохраняет напоминание на основе данных из FSM мастера."""
        return self._reminder_repo.add_reminder(
            user_id=user_id,
            text=data["text"],
            reminder_type=data["reminder_type"],
            interval_minutes=interval_minutes,
            days_of_week=data.get("days_of_week"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            start_datetime=data.get("start_datetime"),
        )

    def get_reminder(self, reminder_id: int) -> Optional[Dict[str, Any]]:
        return self._reminder_repo.get_reminder(reminder_id)

    def get_user_reminders(self, user_id: int) -> List[Dict[str, Any]]:
        return self._reminder_repo.get_user_reminders(user_id)

    def toggle_active(self, reminder_id: int, user_id: int) -> Optional[bool]:
        return self._reminder_repo.toggle_active(reminder_id, user_id)

    def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        return self._reminder_repo.delete_reminder(reminder_id, user_id)

    def mark_done(
        self, reminder: Dict[str, Any], today_str: str
    ) -> str:
        """Отмечает напоминание выполненным и возвращает тип завершения (today или permanent)."""
        rem_id = reminder["id"]
        if reminder["reminder_type"] == "recurring":
            self._reminder_repo.mark_completed_today(rem_id, today_str)
            return "today"
        else:
            self._reminder_repo.mark_completed_permanently(rem_id)
            return "permanent"
