import asyncio
import os
import sys

from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import BOT_TOKEN, PORT, logger
from app.database import db
from app.domain.interfaces import ISystemSettingsRepository, IUserRepository
from app.handlers import setup_handlers
from app.keyboards import get_main_keyboard
from app.services import reminder_worker
from app.web import start_health_server


async def setup_bot_commands(bot: Bot):
    """Регистрирует команды бота в меню Telegram (синяя кнопка [Меню])."""
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="🔄 Главное меню / обновить"),
                BotCommand(command="new", description="➕ Создать напоминание"),
                BotCommand(command="list", description="📋 Мои напоминания"),
                BotCommand(command="timezone", description="⚙️ Настройка часового пояса"),
                BotCommand(command="help", description="ℹ️ Помощь и справка"),
            ]
        )
        logger.info("Команды бота в меню Telegram успешно зарегистрированы.")
    except Exception as cmd_err:
        logger.warning(f"Не удалось установить команды бота: {cmd_err}")


async def notify_on_deploy(
    bot: Bot,
    system_repo: Optional[ISystemSettingsRepository] = None,
    user_repo: Optional[IUserRepository] = None,
):
    """Уведомляет пользователей о деплое новой версии для обновления меню."""
    sys_repo = system_repo or db.system
    u_repo = user_repo or db.users

    current_build = os.getenv("RENDER_GIT_COMMIT") or str(int(os.path.getmtime(__file__)))
    last_build = sys_repo.get_setting("last_deployed_build")

    if last_build != current_build:
        sys_repo.set_setting("last_deployed_build", current_build)
        if last_build is not None:
            user_ids = u_repo.get_all_user_ids()
            for uid in user_ids:
                try:
                    await bot.send_message(
                        chat_id=uid,
                        text=(
                            "🚀 <b>Бот успешно обновлён!</b>\n\n"
                            "Все свежие изменения и кнопки меню обновлены 👇"
                        ),
                        reply_markup=get_main_keyboard(),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as notify_err:
                    logger.warning(f"Не удалось отправить уведомление пользователю {uid}: {notify_err}")


async def main():
    """Основная точка входа приложения."""
    if not BOT_TOKEN:
        print("=" * 60)
        print("ОШИБКА: Токен Telegram-бота не задан!")
        print("Укажите его в переменной окружения BOT_TOKEN или в файле .env")
        print("=" * 60)
        sys.exit(1)

    # Веб-сервер для прохождения проверок Render.com
    web_runner = await start_health_server(PORT)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключение всех роутеров и обработчиков
    setup_handlers(dp)

    # Регистрация меню команд и оповещение об обновлении
    await setup_bot_commands(bot)
    await notify_on_deploy(bot)

    # Фоновый воркер напоминаний
    worker_task = asyncio.create_task(reminder_worker(bot))

    logger.info("Бот запускается... Нажмите Ctrl+C для остановки.")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        worker_task.cancel()
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()
        logger.info("Бот остановлен.")
