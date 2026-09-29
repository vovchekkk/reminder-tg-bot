import pytest

from app.database.postgres import PostgresReminderRepository, PostgresUserRepository
from app.database.sqlite import SqliteReminderRepository, SqliteUserRepository
from app.domain.interfaces import (
    IReminderExecutionRepository,
    IReminderReader,
    IReminderRepository,
    IReminderWriter,
    IUserRepository,
)


class TestISPInterfaces:
    def test_sqlite_repositories_satisfy_segregated_interfaces(self, temp_db):
        sqlite_rem_repo = temp_db["reminder_repo"]
        sqlite_user_repo = temp_db["user_repo"]

        # Проверка соответствия протоколам ISP
        assert isinstance(sqlite_rem_repo, IReminderReader)
        assert isinstance(sqlite_rem_repo, IReminderWriter)
        assert isinstance(sqlite_rem_repo, IReminderExecutionRepository)
        assert isinstance(sqlite_rem_repo, IReminderRepository)
        assert isinstance(sqlite_user_repo, IUserRepository)

    def test_postgres_repositories_satisfy_segregated_interfaces(self):
        from unittest.mock import MagicMock
        mock_cm = MagicMock()
        pg_rem_repo = PostgresReminderRepository(mock_cm)
        pg_user_repo = PostgresUserRepository(mock_cm)

        assert isinstance(pg_rem_repo, IReminderReader)
        assert isinstance(pg_rem_repo, IReminderWriter)
        assert isinstance(pg_rem_repo, IReminderExecutionRepository)
        assert isinstance(pg_rem_repo, IReminderRepository)
        assert isinstance(pg_user_repo, IUserRepository)
