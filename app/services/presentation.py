from datetime import datetime
import html
from typing import Any, Dict, List, Optional, Tuple

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.domain.interfaces import IReminderFormatterStrategy
from app.services.time_utils import (
    format_days_list,
    format_interval,
    safe_fromisoformat,
)


class RecurringReminderFormatter(IReminderFormatterStrategy):
    """Форматирование повторяющихся напоминаний по дням недели (Open/Closed Principle)."""

    def format_schedule(self, reminder: Dict[str, Any], user_now: datetime) -> str:
        interval = reminder.get("interval_minutes", 60)
        if interval == 0:
            return f"   • Режим: 1 раз в день в {reminder.get('start_time', '00:00')}\n"
        else:
            interval_str = format_interval(interval)
            start_s = reminder.get("start_time") or "00:00"
            end_s = f" до {reminder['end_time']}" if reminder.get("end_time") else ""
            return (
                f"   • Повтор: каждые {interval_str}\n"
                f"   • Время: с {start_s}{end_s}\n"
            )

    def format_card_details(self, reminder: Dict[str, Any], user_now: datetime) -> str:
        interval = reminder.get("interval_minutes", 60)
        if interval == 0:
            return (
                f"⏰ <b>Режим:</b> 1 раз в день\n"
                f"🕐 <b>Время напоминания:</b> в {reminder.get('start_time', '00:00')}\n"
            )
        else:
            start_s = reminder.get("start_time") or "00:00"
            end_s = f" до {reminder['end_time']}" if reminder.get("end_time") else ""
            return (
                f"⏰ <b>Интервал повтора:</b> каждые {format_interval(interval)}\n"
                f"🕐 <b>Время показа:</b> с {start_s}{end_s}\n"
            )

    def format_summary(self, reminder: Dict[str, Any], user_now: datetime) -> str:
        interval = reminder.get("interval_minutes", 60)
        days = reminder.get("days_of_week")
        if interval == 0:
            return (
                f"📅 <b>Дни недели:</b> {format_days_list(days)}\n"
                f"🕐 <b>Время напоминания:</b> в {reminder.get('start_time', '00:00')}\n"
                f"⏰ <b>Режим:</b> 1 раз в день в точное время\n\n"
                f"Бот пришлёт сообщение в назначенный час в выбранные дни."
            )
        else:
            start_s = reminder.get("start_time") or "00:00"
            end_time = reminder.get("end_time")
            end_s = f"до {end_time}" if end_time else "до 23:59"
            return (
                f"📅 <b>Дни недели:</b> {format_days_list(days)}\n"
                f"🕐 <b>Время показа:</b> с {start_s} {end_s}\n"
                f"⏰ <b>Частота повтора:</b> каждые {format_interval(interval)} (пока не нажмёте ✅)\n\n"
                f"Когда придёт напоминание, нажмите под ним <b>«✅ Сделано!»</b>, чтобы отключить повторы на сегодня."
            )

    def format_test_desc(self, reminder: Dict[str, Any]) -> str:
        interval = reminder.get("interval_minutes", 60)
        if interval == 0:
            return f"В назначенные дни приходит 1 раз в {reminder.get('start_time', 'указанное время')}."
        return f"Интервал повтора: каждые {format_interval(interval)}, пока не нажмёте галочку."


class OneTimeReminderFormatter(IReminderFormatterStrategy):
    """Форматирование одноразовых напоминаний (Open/Closed Principle)."""

    def format_schedule(self, reminder: Dict[str, Any], user_now: datetime) -> str:
        start_datetime = reminder.get("start_datetime")
        if not start_datetime:
            return ""
        try:
            dt_obj = safe_fromisoformat(start_datetime, tz_obj=user_now.tzinfo)
            interval = reminder.get("interval_minutes", 60)
            if interval == 0:
                return f"   • Режим: 1 раз ({dt_obj.strftime('%d.%m.%Y в %H:%M')})\n"
            else:
                end_s = f" до {reminder['end_time']}" if reminder.get("end_time") else ""
                interval_str = format_interval(interval)
                return (
                    f"   • Дата: {dt_obj.strftime('%d.%m.%Y')} (с {dt_obj.strftime('%H:%M')}{end_s})\n"
                    f"   • Повтор: каждые {interval_str}\n"
                )
        except Exception:
            return ""

    def format_card_details(self, reminder: Dict[str, Any], user_now: datetime) -> str:
        start_datetime = reminder.get("start_datetime")
        if not start_datetime:
            return ""
        try:
            dt_obj = safe_fromisoformat(start_datetime, tz_obj=user_now.tzinfo)
            interval = reminder.get("interval_minutes", 60)
            if interval == 0:
                return (
                    f"⏰ <b>Режим:</b> 1 раз в определенное время\n"
                    f"🕐 <b>Дата и время:</b> {dt_obj.strftime('%d.%m.%Y в %H:%M')}\n"
                )
            else:
                end_s = f" до {reminder['end_time']}" if reminder.get("end_time") else ""
                start_s = dt_obj.strftime("%H:%M")
                return (
                    f"📅 <b>Дата:</b> {dt_obj.strftime('%d.%m.%Y')}\n"
                    f"⏰ <b>Интервал повтора:</b> каждые {format_interval(interval)}\n"
                    f"🕐 <b>Время показа:</b> с {start_s}{end_s}\n"
                )
        except Exception:
            return ""

    def format_summary(self, reminder: Dict[str, Any], user_now: datetime) -> str:
        start_datetime = reminder.get("start_datetime")
        interval = reminder.get("interval_minutes", 60)
        end_time = reminder.get("end_time")
        dt_obj = safe_fromisoformat(start_datetime, tz_obj=user_now.tzinfo)

        if interval == 0:
            return (
                f"📅 <b>Дата:</b> {dt_obj.strftime('%d.%m.%Y')}\n"
                f"🕐 <b>Время напоминания:</b> в {dt_obj.strftime('%H:%M')}\n"
                f"⏰ <b>Режим:</b> 1 раз в определенное время\n\n"
                f"Бот пришлёт сообщение в назначенное время."
            )
        else:
            start_s = dt_obj.strftime("%H:%M")
            end_s = f"до {end_time}" if end_time else "до конца дня"
            return (
                f"📅 <b>Дата:</b> {dt_obj.strftime('%d.%m.%Y')}\n"
                f"🕐 <b>Время показа:</b> с {start_s} {end_s}\n"
                f"⏰ <b>Частота повтора:</b> каждые {format_interval(interval)} (пока не нажмёте ✅)\n\n"
                f"Когда придёт напоминание, нажмите под ним <b>«✅ Сделано!»</b>, чтобы отключить повторы."
            )

    def format_test_desc(self, reminder: Dict[str, Any]) -> str:
        interval = reminder.get("interval_minutes", 60)
        if interval == 0:
            dt_str = reminder.get("start_time", "")
            if reminder.get("start_datetime"):
                try:
                    dt = safe_fromisoformat(reminder["start_datetime"])
                    dt_str = dt.strftime("%d.%m.%Y в %H:%M")
                except Exception:
                    pass
            return f"Одноразовое напоминание на {dt_str}."
        return f"Интервал повтора: каждые {format_interval(interval)}, пока не нажмёте галочку."


class ReminderPresenter:
    """
    Отвечает исключительно за визуальное представление и форматирование напоминаний (Single Responsibility).
    Расширяется регистрацией новых стратегий форматирования без изменения кода (Open/Closed).
    """

    def __init__(self):
        self._formatters: Dict[str, IReminderFormatterStrategy] = {
            "recurring": RecurringReminderFormatter(),
            "one_time": OneTimeReminderFormatter(),
        }

    def register_formatter(
        self, reminder_type: str, formatter: IReminderFormatterStrategy
    ) -> None:
        self._formatters[reminder_type] = formatter

    def get_formatter(self, reminder_type: str) -> Optional[IReminderFormatterStrategy]:
        return self._formatters.get(reminder_type)

    def render_list(
        self, reminders: List[Dict[str, Any]], user_now: datetime
    ) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        """Формирует текст и клавиатуру со списком напоминаний."""
        if not reminders:
            return (
                "📭 У вас пока нет созданных напоминаний.\n\n"
                "Нажмите <b>«➕ Создать напоминание»</b>, чтобы запланировать первую задачу!",
                None,
            )

        user_today_str = user_now.strftime("%Y-%m-%d")
        text = f"📋 <b>Ваши напоминания ({len(reminders)}):</b>\n\n"
        buttons = []

        for r in reminders:
            status_icon = "🟢" if r["is_active"] else "⏸️"
            if r.get("is_completed"):
                status_icon = "✅"

            type_str = (
                f"📅 {format_days_list(r.get('days_of_week'))}"
                if r["reminder_type"] == "recurring"
                else "⏱️ Одноразовое"
            )

            short_title = r["text"][:30] + ("..." if len(r["text"]) > 30 else "")
            text += (
                f"{status_icon} <b>{html.escape(short_title)}</b>\n"
                f"   • Тип: {type_str}\n"
            )

            formatter = self._formatters.get(r["reminder_type"])
            if formatter:
                text += formatter.format_schedule(r, user_now)

            if r.get("last_completed_date") == user_today_str:
                text += "   • <i>Сегодня уже выполнено 🎉</i>\n"

            text += "\n"

            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{status_icon} {short_title}",
                        callback_data=f"manage_rem:{r['id']}",
                    )
                ]
            )

        buttons.append(
            [InlineKeyboardButton(text="➕ Создать новое", callback_data="start_wizard")]
        )
        return text, InlineKeyboardMarkup(inline_keyboard=buttons)

    def render_card(self, reminder: Dict[str, Any], user_now: datetime) -> str:
        """Формирует текст карточки конкретного напоминания."""
        status = (
            "🟢 Активно"
            if reminder["is_active"]
            else ("✅ Завершено" if reminder.get("is_completed") else "⏸️ На паузе")
        )
        type_str = (
            f"По дням недели ({format_days_list(reminder.get('days_of_week'))})"
            if reminder["reminder_type"] == "recurring"
            else "Одноразовое"
        )

        info = (
            f"⚙️ <b>Управление напоминанием</b>\n\n"
            f"📌 <b>Текст:</b> {html.escape(reminder['text'])}\n"
            f"📊 <b>Статус:</b> {status}\n"
            f"🔁 <b>Тип:</b> {type_str}\n"
        )

        formatter = self._formatters.get(reminder["reminder_type"])
        if formatter and hasattr(formatter, "format_card_details"):
            info += formatter.format_card_details(reminder, user_now)

        if reminder.get("last_completed_date") == user_now.strftime("%Y-%m-%d"):
            info += "\n<i>✨ Сегодня задание уже отмечено как сделанное!</i>"

        return info

    def render_summary(self, reminder: Dict[str, Any], user_now: datetime) -> str:
        """Формирует поздравительное сообщение после создания напоминания."""
        reminder_type = reminder["reminder_type"]
        summary = (
            f"🎉 <b>Напоминание успешно создано!</b>\n\n"
            f"📌 <b>Текст:</b> {html.escape(reminder['text'])}\n"
            f"🔁 <b>Тип:</b> {'По дням недели' if reminder_type == 'recurring' else 'Одноразовое'}\n"
        )
        formatter = self._formatters.get(reminder_type)
        if formatter:
            summary += formatter.format_summary(reminder, user_now)
        return summary

    def render_test_desc(self, reminder: Dict[str, Any]) -> str:
        """Формирует описание напоминания для тестовой отправки."""
        formatter = self._formatters.get(reminder["reminder_type"])
        if formatter and hasattr(formatter, "format_test_desc"):
            return formatter.format_test_desc(reminder)
        return f"Интервал: каждые {format_interval(reminder.get('interval_minutes', 60))}."
