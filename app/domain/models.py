from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class UserEntity:
    user_id: int
    timezone: str
    updated_at: str


@dataclass(frozen=True)
class ReminderEntity:
    id: int
    user_id: int
    text: str
    reminder_type: str  # 'recurring' | 'one_time'
    interval_minutes: int
    days_of_week: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_datetime: Optional[str] = None
    is_active: bool = True
    last_reminded_at: Optional[str] = None
    last_completed_date: Optional[str] = None
    is_completed: bool = False
    created_at: Optional[str] = None
