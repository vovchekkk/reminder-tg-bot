from app.database.database import Database, db
from app.database.postgres import (
    PostgresConnectionManager,
    PostgresReminderRepository,
    PostgresSystemSettingsRepository,
    PostgresUserRepository,
    migrate_from_sqlite_if_needed,
)
from app.database.sqlite import (
    DatabaseConnectionManager,
    SqliteConnectionManager,
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
    "SqliteConnectionManager",
    "SqliteReminderRepository",
    "SqliteSystemSettingsRepository",
    "SqliteUserRepository",
    "db",
    "migrate_from_sqlite_if_needed",
]
