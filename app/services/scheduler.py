import asyncio
from typing import Optional

from aiogram import Bot

from app.config import CHECK_INTERVAL_SECONDS, logger
from app.database import db
from app.domain.interfaces import INotifier, IReminderRepository, IUserRepository
from app.services.evaluator import ReminderEvaluator
from app.services.notifier import TelegramNotifier
from app.services.time_utils import get_now_for_user


class ReminderSchedulerService:
    """
    Оркестратор планировщика напоминаний.
    Соблюдает SRP: отвечает только за координацию цикла проверки и доставки,
    делегируя оценку ReminderEvaluator, а отправку - INotifier.
    """

    def __init__(
        self,
        reminder_repo: IReminderRepository,
        user_repo: IUserRepository,
        evaluator: ReminderEvaluator,
        notifier: INotifier,
        check_interval_seconds: int = CHECK_INTERVAL_SECONDS,
    ):
        self._reminder_repo = reminder_repo
        self._user_repo = user_repo
        self._evaluator = evaluator
        self._notifier = notifier
        self._check_interval = check_interval_seconds

    async def check_and_deliver(self) -> int:
        """Разовый проход: проверяет базу и отправляет наступившие напоминания. Возвращает число отправленных."""
        delivered_count = 0
        try:
            active_reminders = self._reminder_repo.get_active_reminders()

            for rem in active_reminders:
                try:
                    user_id = rem["user_id"]
                    user_now = get_now_for_user(user_id, self._user_repo)

                    if self._evaluator.is_due(rem, user_now):
                        logger.info(
                            f"Отправка напоминания #{rem['id']} пользователю {user_id}: {rem['text']}"
                        )
                        sent = await self._notifier.send_reminder(rem)
                        if sent:
                            self._reminder_repo.update_last_reminded(
                                rem["id"], user_now.isoformat()
                            )
                            delivered_count += 1
                except Exception as rem_err:
                    logger.error(
                        f"Ошибка обработки напоминания #{rem.get('id')}: {rem_err}"
                    )
        except Exception as loop_err:
            logger.error(f"Ошибка проверки списка активных напоминаний: {loop_err}")

        return delivered_count

    async def run_forever(self) -> None:
        """Бесконечный фоновый цикл проверки напоминаний."""
        logger.info("Фоновый воркер напоминаний запущен.")
        while True:
            await self.check_and_deliver()
            await asyncio.sleep(self._check_interval)


async def reminder_worker(
    bot: Bot,
    reminder_repo: Optional[IReminderRepository] = None,
    user_repo: Optional[IUserRepository] = None,
    evaluator: Optional[ReminderEvaluator] = None,
    notifier: Optional[INotifier] = None,
):
    """Точка входа для запуска воркера с поддержкой внедрения зависимостей (DIP)."""
    r_repo = reminder_repo or db.reminders
    u_repo = user_repo or db.users
    ev = evaluator or ReminderEvaluator()
    notif = notifier or TelegramNotifier(bot)

    service = ReminderSchedulerService(
        reminder_repo=r_repo,
        user_repo=u_repo,
        evaluator=ev,
        notifier=notif,
        check_interval_seconds=CHECK_INTERVAL_SECONDS,
    )
    await service.run_forever()
