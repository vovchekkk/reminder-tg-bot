import asyncio
import html

from aiogram import Bot
from aiogram.enums import ParseMode

from app.config import CHECK_INTERVAL_SECONDS, logger
from app.database import db
from app.keyboards import get_done_keyboard
from app.services.time_utils import (
    format_interval,
    get_now_for_user,
    is_time_in_range,
    safe_fromisoformat,
)


async def reminder_worker(bot: Bot):
    """Фоновый планировщик, проверяющий базу и рассылающий напоминания."""
    logger.info("Фоновый воркер напоминаний запущен.")
    while True:
        try:
            active_reminders = db.get_active_reminders()

            for rem in active_reminders:
                try:
                    user_id = rem["user_id"]
                    # Текущее время пользователя с учетом его личного часового пояса
                    now = get_now_for_user(user_id, db)
                    today_str = now.strftime("%Y-%m-%d")
                    should_remind = False

                    if rem["reminder_type"] == "recurring":
                        if rem.get("days_of_week"):
                            days = [
                                int(d)
                                for d in rem["days_of_week"].split(",")
                                if d.strip().isdigit()
                            ]
                            if now.weekday() not in days:
                                continue

                        if rem["last_completed_date"] == today_str:
                            continue

                        # Проверяем диапазон времени со start_time до end_time
                        if not is_time_in_range(
                            rem.get("start_time"), rem.get("end_time"), now.time()
                        ):
                            continue

                        if not rem["last_reminded_at"]:
                            should_remind = True
                        else:
                            last_reminded_dt = safe_fromisoformat(
                                rem["last_reminded_at"], tz_obj=now.tzinfo
                            )
                            if last_reminded_dt.date() < now.date():
                                should_remind = True
                            else:
                                elapsed_minutes = (
                                    now - last_reminded_dt
                                ).total_seconds() / 60
                                if elapsed_minutes >= rem["interval_minutes"]:
                                    should_remind = True

                    elif rem["reminder_type"] == "one_time":
                        if rem["is_completed"]:
                            continue

                        start_dt = safe_fromisoformat(
                            rem["start_datetime"], tz_obj=now.tzinfo
                        )
                        if now < start_dt:
                            continue

                        # Проверяем ограничение end_time (если задано)
                        if rem.get("end_time"):
                            if not is_time_in_range(
                                None, rem.get("end_time"), now.time()
                            ):
                                continue

                        if not rem["last_reminded_at"]:
                            should_remind = True
                        else:
                            last_reminded_dt = safe_fromisoformat(
                                rem["last_reminded_at"], tz_obj=now.tzinfo
                            )
                            elapsed_minutes = (
                                now - last_reminded_dt
                            ).total_seconds() / 60
                            if elapsed_minutes >= rem["interval_minutes"]:
                                should_remind = True

                    if should_remind:
                        logger.info(
                            f"Отправка напоминания #{rem['id']} пользователю {rem['user_id']}: {rem['text']}"
                        )
                        message_text = (
                            f"🔔 <b>НАПОМИНАНИЕ!</b>\n\n"
                            f"📌 <b>{html.escape(rem['text'])}</b>\n\n"
                            f"<i>Повторяю каждые {format_interval(rem['interval_minutes'])}, "
                            f"пока не подтвердите выполнение кнопкой ниже:</i>"
                        )

                        await bot.send_message(
                            chat_id=rem["user_id"],
                            text=message_text,
                            reply_markup=get_done_keyboard(rem["id"]),
                            parse_mode=ParseMode.HTML,
                        )

                        db.update_last_reminded(rem["id"], now.isoformat())

                except Exception as rem_err:
                    logger.error(
                        f"Ошибка обработки напоминания #{rem.get('id')}: {rem_err}"
                    )

        except Exception as loop_err:
            logger.error(f"Ошибка в фоновом цикле воркера: {loop_err}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
