from contextlib import contextmanager
from datetime import datetime
import sqlite3
import threading
from typing import List, Optional

from app.config import DB_PATH, DEFAULT_TIMEZONE, logger


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            # Таблица напоминаний
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    reminder_type TEXT NOT NULL,      -- 'recurring' или 'one_time'
                    days_of_week TEXT,                -- '0,4' (0=Пн, 4=Пт)
                    interval_minutes INTEGER NOT NULL DEFAULT 60,
                    start_time TEXT,                  -- '09:00'
                    end_time TEXT,                    -- '22:00'
                    start_datetime TEXT,              -- для one_time: ISO формат
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_reminded_at TEXT,            -- ISO формат времени последнего сообщения
                    last_completed_date TEXT,         -- 'YYYY-MM-DD' дата выполнения
                    is_completed INTEGER NOT NULL DEFAULT 0, -- 1 если выполнено
                    created_at TEXT NOT NULL
                )
                """
            )
            # Миграция для существующей базы (добавление end_time)
            try:
                cursor.execute("ALTER TABLE reminders ADD COLUMN end_time TEXT")
            except sqlite3.OperationalError:
                pass

            # Таблица пользователей (часовые пояса)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Таблица системных настроек (версия деплоя и т.д.)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.commit()

    def get_system_setting(self, key: str) -> Optional[str]:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    def set_system_setting(self, key: str, value: str):
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO system_settings (key, value)
                VALUES (?, ?)
                """,
                (key, value),
            )
            conn.commit()

    def get_all_user_ids(self) -> List[int]:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT user_id FROM users
                UNION
                SELECT DISTINCT user_id FROM reminders
                """
            )
            return [row[0] for row in cursor.fetchall() if row[0]]

    def get_user_timezone(self, user_id: int) -> str:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timezone FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row and row["timezone"]:
                return row["timezone"]
            return DEFAULT_TIMEZONE

    def has_user_timezone(self, user_id: int) -> bool:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None

    def set_user_timezone(self, user_id: int, timezone_name: str):
        now_iso = datetime.now().isoformat()
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO users (user_id, timezone, updated_at)
                VALUES (?, ?, ?)
                """,
                (user_id, timezone_name, now_iso),
            )
            conn.commit()

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
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO reminders (
                    user_id, text, reminder_type, days_of_week,
                    interval_minutes, start_time, end_time, start_datetime,
                    is_active, last_completed_date, is_completed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, NULL, 0, ?)
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
            conn.commit()
            return cursor.lastrowid

    def get_reminder(self, reminder_id: int) -> Optional[dict]:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_reminders(self, user_id: int) -> List[dict]:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM reminders WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def get_active_reminders(self) -> List[dict]:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM reminders
                WHERE is_active = 1 AND is_completed = 0
                """
            )
            return [dict(r) for r in cursor.fetchall()]

    def toggle_active(self, reminder_id: int, user_id: int) -> Optional[bool]:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT is_active FROM reminders WHERE id = ? AND user_id = ?",
                (reminder_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            new_status = 0 if row["is_active"] else 1
            cursor.execute(
                "UPDATE reminders SET is_active = ? WHERE id = ?",
                (new_status, reminder_id),
            )
            conn.commit()
            return bool(new_status)

    def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM reminders WHERE id = ? AND user_id = ?",
                (reminder_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_completed_today(self, reminder_id: int, today_str: str):
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE reminders SET last_completed_date = ? WHERE id = ?",
                (today_str, reminder_id),
            )
            conn.commit()

    def mark_completed_permanently(self, reminder_id: int):
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE reminders
                SET is_completed = 1, is_active = 0
                WHERE id = ?
                """,
                (reminder_id,),
            )
            conn.commit()

    def update_last_reminded(self, reminder_id: int, reminded_iso: str):
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE reminders SET last_reminded_at = ? WHERE id = ?",
                (reminded_iso, reminder_id),
            )
            conn.commit()
