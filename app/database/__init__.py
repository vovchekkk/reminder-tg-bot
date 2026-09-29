from app.database.connection import DatabaseConnectionManager
from app.database.database import Database, db
from app.database.postgres import (
    PostgresConnectionManager,
    PostgresReminderRepository,
    PostgresSystemSettingsRepository,
    PostgresUserRepository,
    migrate_from_sqlite_if_needed,
)
from app.database.repositories import (
    SqliteReminderRepository,
    SqliteSystemSettingsRepository,
    SqliteUserRepository,
)

__all__ = [
    "Database",
    "DatabaseConnectionManager",
    "PostgresConnectionManager",
    "PostgresReminderRepository",
    "PostgresSystemSettingsRepository",
    "PostgresUserRepository",
    "SqliteReminderRepository",
    "SqliteSystemSettingsRepository",
    "SqliteUserRepository",
    "db",
    "migrate_from_sqlite_if_needed",
]
