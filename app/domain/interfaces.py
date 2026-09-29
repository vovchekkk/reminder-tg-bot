from datetime import datetime
from typing import Any, Awaitable, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class IUserRepository(Protocol):
    """Интерфейс для работы с пользователями и их настройками часового пояса."""

    def get_user_timezone(self, user_id: int) -> str:
        ...

    def has_user_timezone(self, user_id: int) -> bool:
        ...

    def set_user_timezone(self, user_id: int, timezone_name: str) -> None:
        ...

    def get_all_user_ids(self) -> List[int]:
        ...


@runtime_checkable
class IReminderReader(Protocol):
    """Интерфейс чтения напоминаний (Interface Segregation Principle)."""

    def get_reminder(self, reminder_id: int) -> Optional[Dict[str, Any]]:
        ...

    def get_user_reminders(self, user_id: int) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class IReminderWriter(Protocol):
    """Интерфейс создания и модификации напоминаний (Interface Segregation Principle)."""

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
        ...

    def toggle_active(self, reminder_id: int, user_id: int) -> Optional[bool]:
        ...

    def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        ...


@runtime_checkable
class IReminderExecutionRepository(Protocol):
    """Интерфейс планировщика и отслеживания выполнения (Interface Segregation Principle)."""

    def get_active_reminders(self) -> List[Dict[str, Any]]:
        ...

    def mark_completed_today(self, reminder_id: int, today_str: str) -> None:
        ...

    def mark_completed_permanently(self, reminder_id: int) -> None:
        ...

    def update_last_reminded(self, reminder_id: int, reminded_iso: str) -> None:
        ...


@runtime_checkable
class IReminderRepository(
    IReminderReader, IReminderWriter, IReminderExecutionRepository, Protocol
):
    """Полный интерфейс хранилища напоминаний, объединяющий сегрегированные протоколы."""
    ...


@runtime_checkable
class IReminderFormatterStrategy(Protocol):
    """Стратегия форматирования отображения напоминания (Open/Closed Principle)."""

    def format_schedule(self, reminder: Dict[str, Any], user_now: datetime) -> str:
        ...

    def format_summary(self, reminder: Dict[str, Any], user_now: datetime) -> str:
        ...



@runtime_checkable
class ISystemSettingsRepository(Protocol):
    """Интерфейс для системных параметров (например, отслеживание деплоев)."""

    def get_setting(self, key: str) -> Optional[str]:
        ...

    def set_setting(self, key: str, value: str) -> None:
        ...


@runtime_checkable
class IReminderStrategy(Protocol):
    """Стратегия оценки необходимости отправки напоминания (Open/Closed Principle)."""

    def should_remind(self, reminder: Dict[str, Any], now: datetime) -> bool:
        ...


@runtime_checkable
class INotifier(Protocol):
    """Интерфейс отправки напоминаний пользователям (Dependency Inversion)."""

    def send_reminder(self, reminder: Dict[str, Any]) -> Awaitable[bool]:
        ...
