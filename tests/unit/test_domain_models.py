from app.domain.interfaces import (
    INotifier,
    IReminderRepository,
    IReminderStrategy,
    ISystemSettingsRepository,
    IUserRepository,
)
from app.domain.models import ReminderEntity, UserEntity


def test_user_entity():
    user = UserEntity(user_id=1, timezone="Europe/Moscow", updated_at="2026-09-29T12:00:00")
    assert user.user_id == 1
    assert user.timezone == "Europe/Moscow"


def test_reminder_entity():
    rem = ReminderEntity(
        id=10,
        user_id=1,
        text="Сделать тест",
        reminder_type="recurring",
        interval_minutes=60,
    )
    assert rem.id == 10
    assert rem.text == "Сделать тест"
    assert rem.is_active is True
    assert rem.is_completed is False


def test_protocol_runtime_checks(temp_db):
    assert isinstance(temp_db["user_repo"], IUserRepository)
    assert isinstance(temp_db["reminder_repo"], IReminderRepository)
    assert isinstance(temp_db["system_repo"], ISystemSettingsRepository)
