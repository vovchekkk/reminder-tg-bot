from contextlib import contextmanager
import sqlite3
import threading
from typing import Generator

from app.config import DB_PATH, logger


class DatabaseConnectionManager:
    """Отвечает исключительно за подключение к SQLite и инициализацию схемы."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    def init_db(self) -> None:
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
