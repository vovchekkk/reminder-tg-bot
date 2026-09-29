from contextlib import contextmanager
from datetime import datetime
import threading
from typing import Any, Dict, Generator, List, Optional
import urllib.parse

import psycopg
from psycopg.rows import dict_row

from app.config import DEFAULT_TIMEZONE, logger
from app.domain.interfaces import (
    IReminderRepository,
    ISystemSettingsRepository,
    IUserRepository,
)


class PostgresConnectionManager:
    """Менеджер подключений к PostgreSQL (Supabase / Neon / Render Postgres)."""

    def __init__(self, database_url: str):
        self.database_url = self._normalize_database_url(database_url)
        self._lock = threading.Lock()
        self._conn: Optional[psycopg.Connection] = None
        self.init_db()

    @staticmethod
    def _normalize_database_url(url: str) -> str:
        """Нормализует URL базы данных для psycopg."""
        url = url.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]

        # Добавляем sslmode=require для удаленных баз данных, если не указано
        if "localhost" not in url and "127.0.0.1" not in url and "sslmode" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"

        return url

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    def _get_active_conn(self) -> psycopg.Connection:
        """Возвращает живое подключение к базе данных, переподключаясь при разрыве."""
        if self._conn is not None:
            if not self._conn.closed:
                try:
                    # Быстрая проверка живости подключения
                    self._conn.execute("SELECT 1")
                    return self._conn
                except Exception:
                    try:
                        self._conn.close()
                    except Exception:
                        pass
                    self._conn = None

        logger.info("Opening new PostgreSQL connection...")
        self._conn = psycopg.connect(self.database_url, autocommit=True, row_factory=dict_row)
        return self._conn

    @contextmanager
    def get_connection(self) -> Generator[psycopg.Connection, None, None]:
        with self._lock:
            conn = self._get_active_conn()
            yield conn

    def init_db(self) -> None:
        """Создает необходимые таблицы и индексы в PostgreSQL."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Таблица пользователей
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
                        updated_at TEXT NOT NULL
                    );
                    """
                )

                # Таблица напоминаний
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reminders (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        text TEXT NOT NULL,
                        reminder_type TEXT NOT NULL,
                        days_of_week TEXT,
                        interval_minutes INTEGER NOT NULL DEFAULT 60,
                        start_time TEXT,
                        end_time TEXT,
                        start_datetime TEXT,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        last_reminded_at TEXT,
                        last_completed_date TEXT,
                        is_completed INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL
                    );
                    """
                )

                # Таблица системных настроек
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS system_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    );
                    """
                )

                # Индексы для ускорения поиска
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
                    CREATE INDEX IF NOT EXISTS idx_reminders_active ON reminders(is_active, is_completed);
                    """
                )
        logger.info("PostgreSQL database initialized successfully.")

    def close(self) -> None:
        """Закрывает активное подключение к PostgreSQL."""
        with self._lock:
            if self._conn and not self._conn.closed:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None


class PostgresUserRepository(IUserRepository):
    """PostgreSQL реализация репозитория пользователей."""

    def __init__(self, connection_manager: PostgresConnectionManager):
        self._cm = connection_manager

    def get_user_timezone(self, user_id: int) -> str:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT timezone FROM users WHERE user_id = %s;", (user_id,))
                row = cur.fetchone()
                if row and row.get("timezone"):
                    return row["timezone"]
                return DEFAULT_TIMEZONE

    def has_user_timezone(self, user_id: int) -> bool:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE user_id = %s;", (user_id,))
                return cur.fetchone() is not None

    def set_user_timezone(self, user_id: int, timezone_name: str) -> None:
        now_iso = datetime.now().isoformat()
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (user_id, timezone, updated_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET timezone = EXCLUDED.timezone, updated_at = EXCLUDED.updated_at;
                    """,
                    (user_id, timezone_name, now_iso),
                )

    def get_all_user_ids(self) -> List[int]:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT user_id FROM users
                    UNION
                    SELECT DISTINCT user_id FROM reminders;
                    """
                )
                rows = cur.fetchall()
                return [row["user_id"] for row in rows if row.get("user_id")]


class PostgresReminderRepository(IReminderRepository):
    """PostgreSQL реализация репозитория напоминаний."""

    def __init__(self, connection_manager: PostgresConnectionManager):
        self._cm = connection_manager

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
        now_iso = datetime.now().isoformat()
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reminders (
                        user_id, text, reminder_type, days_of_week,
                        interval_minutes, start_time, end_time, start_datetime,
                        is_active, last_completed_date, is_completed, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, NULL, 0, %s)
                    RETURNING id;
                    """,
                    (
                        user_id,
                        text,
                        reminder_type,
                        days_of_week,
                        interval_minutes,
                        start_time,
                        end_time,
                        start_datetime,
                        now_iso,
                    ),
                )
                row = cur.fetchone()
                return row["id"]

    def get_reminder(self, reminder_id: int) -> Optional[Dict[str, Any]]:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM reminders WHERE id = %s;", (reminder_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def get_user_reminders(self, user_id: int) -> List[Dict[str, Any]]:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM reminders WHERE user_id = %s ORDER BY id DESC;",
                    (user_id,),
                )
                return [dict(r) for r in cur.fetchall()]

    def get_active_reminders(self) -> List[Dict[str, Any]]:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM reminders
                    WHERE is_active = 1 AND is_completed = 0;
                    """
                )
                return [dict(r) for r in cur.fetchall()]

    def toggle_active(self, reminder_id: int, user_id: int) -> Optional[bool]:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT is_active FROM reminders WHERE id = %s AND user_id = %s;",
                    (reminder_id, user_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                new_status = 0 if row["is_active"] else 1
                cur.execute(
                    "UPDATE reminders SET is_active = %s WHERE id = %s;",
                    (new_status, reminder_id),
                )
                return bool(new_status)

    def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM reminders WHERE id = %s AND user_id = %s;",
                    (reminder_id, user_id),
                )
                return cur.rowcount > 0

    def mark_completed_today(self, reminder_id: int, today_str: str) -> None:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE reminders SET last_completed_date = %s WHERE id = %s;",
                    (today_str, reminder_id),
                )

    def mark_completed_permanently(self, reminder_id: int) -> None:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE reminders
                    SET is_completed = 1, is_active = 0
                    WHERE id = %s;
                    """,
                    (reminder_id,),
                )

    def update_last_reminded(self, reminder_id: int, reminded_iso: str) -> None:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE reminders SET last_reminded_at = %s WHERE id = %s;",
                    (reminded_iso, reminder_id),
                )


class PostgresSystemSettingsRepository(ISystemSettingsRepository):
    """PostgreSQL реализация репозитория системных настроек."""

    def __init__(self, connection_manager: PostgresConnectionManager):
        self._cm = connection_manager

    def get_setting(self, key: str) -> Optional[str]:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM system_settings WHERE key = %s;", (key,))
                row = cur.fetchone()
                return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self._cm.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO system_settings (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value;
                    """,
                    (key, value),
                )


def migrate_from_sqlite_if_needed(sqlite_path: str, connection_manager: PostgresConnectionManager) -> int:
    """
    Автоматически переносит существующие данные из SQLite в PostgreSQL,
    если в SQLite есть записи, а в PostgreSQL таблица напоминаний пуста.
    """
    import os
    import sqlite3

    if not os.path.exists(sqlite_path):
        return 0

    try:
        with connection_manager.get_connection() as pg_conn:
            with pg_conn.cursor() as pg_cur:
                pg_cur.execute("SELECT COUNT(*) FROM reminders;")
                pg_count = pg_cur.fetchone()["count"]
                if pg_count > 0:
                    # В Postgres уже есть данные, миграция не требуется
                    return 0

        # Читаем из SQLite
        sq_conn = sqlite3.connect(sqlite_path)
        sq_conn.row_factory = sqlite3.Row
        sq_cur = sq_conn.cursor()

        # Проверяем таблицы
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reminders'")
        if not sq_cur.fetchone():
            sq_conn.close()
            return 0

        sq_cur.execute("SELECT * FROM users")
        users = [dict(r) for r in sq_cur.fetchall()]

        sq_cur.execute("SELECT * FROM reminders")
        reminders = [dict(r) for r in sq_cur.fetchall()]

        sq_cur.execute("SELECT * FROM system_settings")
        settings = [dict(r) for r in sq_cur.fetchall()]
        sq_conn.close()

        if not users and not reminders:
            return 0

        logger.info(
            f"Migrating {len(users)} users and {len(reminders)} reminders from {sqlite_path} to PostgreSQL..."
        )

        with connection_manager.get_connection() as pg_conn:
            with pg_conn.cursor() as pg_cur:
                for u in users:
                    pg_cur.execute(
                        """
                        INSERT INTO users (user_id, timezone, updated_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id) DO NOTHING;
                        """,
                        (u["user_id"], u["timezone"], u["updated_at"]),
                    )

                for r in reminders:
                    pg_cur.execute(
                        """
                        INSERT INTO reminders (
                            user_id, text, reminder_type, days_of_week,
                            interval_minutes, start_time, end_time, start_datetime,
                            is_active, last_completed_date, is_completed, created_at,
                            last_reminded_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        (
                            r["user_id"],
                            r["text"],
                            r["reminder_type"],
                            r.get("days_of_week"),
                            r.get("interval_minutes", 60),
                            r.get("start_time"),
                            r.get("end_time"),
                            r.get("start_datetime"),
                            r.get("is_active", 1),
                            r.get("last_completed_date"),
                            r.get("is_completed", 0),
                            r["created_at"],
                            r.get("last_reminded_at"),
                        ),
                    )

                for s in settings:
                    pg_cur.execute(
                        """
                        INSERT INTO system_settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key) DO NOTHING;
                        """,
                        (s["key"], s["value"]),
                    )

        logger.info(f"Successfully migrated {len(reminders)} reminders to PostgreSQL!")
        return len(reminders)
    except Exception as e:
        logger.warning(f"SQLite to Postgres migration skipped or failed: {e}")
        return 0

