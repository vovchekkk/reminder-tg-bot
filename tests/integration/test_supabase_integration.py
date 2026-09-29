import os
import pytest

from app.database.postgres import (
    PostgresConnectionManager,
    PostgresReminderRepository,
    PostgresSystemSettingsRepository,
    PostgresUserRepository,
)

SUPABASE_URL = "postgresql://postgres.nmpgkyjzytzwzaoixxde:*yud9u6-C-+KW2h@aws-1-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require"


@pytest.mark.integration
def test_supabase_live_lifecycle():
    """Интеграционный тест жизненного цикла данных в живой базе данных Supabase."""
    conn_str = os.getenv("TEST_DATABASE_URL", SUPABASE_URL)
    try:
        cm = PostgresConnectionManager(conn_str)
    except Exception as e:
        pytest.skip(f"Supabase network unreachable or credentials failed: {e}")

    user_repo = PostgresUserRepository(cm)
    rem_repo = PostgresReminderRepository(cm)
    sys_repo = PostgresSystemSettingsRepository(cm)

    test_user_id = 9876543210

    try:
        # 1. Проверяем пользователей
        user_repo.set_user_timezone(test_user_id, "Asia/Yekaterinburg")
        assert user_repo.has_user_timezone(test_user_id) is True
        assert user_repo.get_user_timezone(test_user_id) == "Asia/Yekaterinburg"

        # 2. Создаем напоминание
        r_id = rem_repo.add_reminder(
            user_id=test_user_id,
            text="Интеграционный тест Supabase",
            reminder_type="recurring",
            interval_minutes=45,
            days_of_week="0,1,2",
            start_time="10:00",
            end_time="20:00",
        )
        assert r_id > 0

        # 3. Читаем напоминание
        rem = rem_repo.get_reminder(r_id)
        assert rem is not None
        assert rem["text"] == "Интеграционный тест Supabase"
        assert rem["interval_minutes"] == 45
        assert rem["is_active"] == 1

        # 4. Переключаем статус
        new_active = rem_repo.toggle_active(r_id, test_user_id)
        assert new_active is False
        rem_updated = rem_repo.get_reminder(r_id)
        assert rem_updated["is_active"] == 0

        # 5. Системные настройки
        sys_repo.set_setting("integration_test_key", "active")
        assert sys_repo.get_setting("integration_test_key") == "active"

    finally:
        # 6. Очистка после теста
        try:
            rem_repo.delete_reminder(r_id, test_user_id)
            with cm.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM users WHERE user_id = %s;", (test_user_id,))
                    cur.execute("DELETE FROM system_settings WHERE key = %s;", ("integration_test_key",))
            cm.close()
        except Exception:
            pass
