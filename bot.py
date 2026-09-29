"""
Универсальный Telegram-бот для напоминаний с подтверждением выполнения (галочка).
Всё в одном файле.

Основные возможности:
1. Автоматическое определение и выбор часового пояса:
   - По кнопке «📍 Отправить геопозицию» (бот сам определяет город и часовой пояс).
   - Выбор из удобного списка (Москва, Екатеринбург, Владивосток и т.д.) или ввод любого UTC.
   - Напоминания приходят строго по местному времени конкретного пользователя.
2. Быстрый шаблон: Напоминание о тесте по физре каждый час по Пн и Пт.
3. Кнопка галочки под напоминанием:
   - При нажатии: бот хвалит («🎉 Ура, вы молодец!») и останавливает напоминания
     (для повторяющихся — до следующего назначенного дня, для одноразовых — навсегда).
   - Если НЕ нажали — бот настойчиво повторяет напоминание через заданный интервал (по умолчанию каждый час).
4. Универсальность:
   - Любой свой текст напоминания.
   - Выбор любых дней недели (мультивыбор кнопками: Пн, Вт, Ср, Чт, Пт, Сб, Вс).
   - Настройка частоты повтора (15 мин, 30 мин, 1 час, 2 часа или свой интервал).
   - Одноразовые напоминания (на конкретное время или через X минут/часов).
   - Управление: просмотр списка, ручная проверка, пауза, удаление.
5. Готовность к развертыванию на Render.com (встроенный порт-сервер) / VPS / ПК.
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, time, timezone
import html
import logging
import os
import re
import sqlite3
import sys
import threading
from typing import Dict, List, Optional, Set, Tuple

# Настройка UTF-8 для консоли Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Aiogram 3
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# ---------------------------------------------------------
# КОНФИГУРАЦИЯ
# ---------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DEFAULT_TIMEZONE = os.getenv("BOT_TIMEZONE", "Europe/Moscow")
DB_PATH = os.getenv("DB_PATH", "reminders.db")
CHECK_INTERVAL_SECONDS = 20  # Частота проверки базы данных фоновым воркером

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ReminderBot")


# ---------------------------------------------------------
# РАБОТА С ЧАСОВЫМИ ПОЯСАМИ
# ---------------------------------------------------------
def get_user_tz_obj(tz_str: str):
    """Преобразует строку часового пояса ('Europe/Moscow', '+5', 'UTC+3') в объект tzinfo."""
    tz_str = tz_str.strip()
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(tz_str)
    except Exception:
        pass

    # Проверка на смещение вида +5, -3, UTC+5, GMT-4
    m = re.match(
        r"^(?:UTC|GMT)?([+-]?\d{1,2})(?::?(\d{2}))?$", tz_str, re.IGNORECASE
    )
    if m:
        hours = int(m.group(1))
        mins = int(m.group(2) or 0)
        if hours < 0:
            mins = -mins
        return timezone(timedelta(hours=hours, minutes=mins))

    # Резервный вариант: Europe/Moscow
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo("Europe/Moscow")
    except Exception:
        return timezone(timedelta(hours=3))


def safe_fromisoformat(val: str, tz_obj=None) -> datetime:
    """Безопасно преобразует ISO строку в datetime, согласованный с нужным часовым поясом."""
    dt = datetime.fromisoformat(val)
    if tz_obj:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz_obj)
        else:
            dt = dt.astimezone(tz_obj)
    return dt


# Популярные часовые пояса для быстрого выбора
POPULAR_TIMEZONES = [
    ("Калининград (UTC+2)", "Europe/Kaliningrad"),
    ("Москва, СПб (UTC+3)", "Europe/Moscow"),
    ("Самара, Саратов (UTC+4)", "Europe/Samara"),
    ("Екатеринбург, Уфа (UTC+5)", "Asia/Yekaterinburg"),
    ("Омск (UTC+6)", "Asia/Omsk"),
    ("Новосибирск, Красноярск (UTC+7)", "Asia/Krasnoyarsk"),
    ("Иркутск (UTC+8)", "Asia/Irkutsk"),
    ("Якутск, Чита (UTC+9)", "Asia/Yakutsk"),
    ("Владивосток, Хабаровск (UTC+10)", "Asia/Vladivostok"),
    ("Магадан, Сахалин (UTC+11)", "Asia/Magadan"),
    ("Камчатка (UTC+12)", "Asia/Kamchatka"),
]


# ---------------------------------------------------------
# БАЗА ДАННЫХ (SQLite)
# ---------------------------------------------------------
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
                    start_datetime TEXT,              -- для one_time: ISO формат
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_reminded_at TEXT,            -- ISO формат времени последнего сообщения
                    last_completed_date TEXT,         -- 'YYYY-MM-DD' дата выполнения
                    is_completed INTEGER NOT NULL DEFAULT 0, -- 1 если выполнено
                    created_at TEXT NOT NULL
                )
                """
            )
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
            conn.commit()

    def get_user_timezone(self, user_id: int) -> str:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timezone FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row and row["timezone"]:
                return row["timezone"]
            return DEFAULT_TIMEZONE

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
        start_datetime: Optional[str] = None,
    ) -> int:
        now_iso = datetime.now().isoformat()
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO reminders (
                    user_id, text, reminder_type, days_of_week,
                    interval_minutes, start_time, start_datetime,
                    is_active, last_completed_date, is_completed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL, 0, ?)
                """,
                (
                    user_id,
                    text,
                    reminder_type,
                    days_of_week,
                    interval_minutes,
                    start_time,
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
            return [dict(row) for row in cursor.fetchall()]

    def get_active_reminders(self) -> List[dict]:
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM reminders WHERE is_active = 1 AND is_completed = 0"
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_last_reminded(self, reminder_id: int, timestamp_iso: str):
        with self._lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE reminders SET last_reminded_at = ? WHERE id = ?",
                (timestamp_iso, reminder_id),
            )
            conn.commit()

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
                "UPDATE reminders SET is_completed = 1, is_active = 0 WHERE id = ?",
                (reminder_id,),
            )
            conn.commit()

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
            new_status = 0 if row["is_active"] == 1 else 1
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


db = Database()


def get_now_for_user(user_id: int) -> datetime:
    """Возвращает текущее время конкретного пользователя с учетом его часового пояса."""
    tz_str = db.get_user_timezone(user_id)
    tz_obj = get_user_tz_obj(tz_str)
    return datetime.now(tz_obj)


# ---------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И КОНСТАНТЫ
# ---------------------------------------------------------
DAYS_NAMES = [
    ("Пн", "Понедельник"),
    ("Вт", "Вторник"),
    ("Ср", "Среда"),
    ("Чт", "Четверг"),
    ("Пт", "Пятница"),
    ("Сб", "Суббота"),
    ("Вс", "Воскресенье"),
]


def format_days_list(days_str: Optional[str]) -> str:
    if not days_str:
        return "Каждый день"
    try:
        day_indices = sorted(map(int, days_str.split(",")))
        short_names = [DAYS_NAMES[i][0] for i in day_indices if 0 <= i <= 6]
        return ", ".join(short_names)
    except Exception:
        return days_str


def format_interval(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} мин."
    hours = minutes // 60
    rem_min = minutes % 60
    if rem_min == 0:
        if hours == 1:
            return "1 час"
        elif 2 <= hours <= 4:
            return f"{hours} часа"
        else:
            return f"{hours} часов"
    return f"{hours} ч. {rem_min} мин."


def parse_time_or_delay(text: str, base_time: datetime) -> Optional[datetime]:
    text = text.strip().lower()

    # Относительное время: +15m, +2h, +45
    m_rel = re.match(r"^\+(\d+)\s*(м|m|мин|ч|h|час|часа|часов)?$", text)
    if m_rel:
        val = int(m_rel.group(1))
        unit = m_rel.group(2) or "m"
        if unit in ("ч", "h", "час", "часа", "часов"):
            return base_time + timedelta(hours=val)
        return base_time + timedelta(minutes=val)

    # Время дня: ЧЧ:ММ
    m_time = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if m_time:
        hour, minute = int(m_time.group(1)), int(m_time.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            target = base_time.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if target <= base_time:
                target += timedelta(days=1)
            return target

    # Дата и время: ДД.ММ ЧЧ:ММ
    m_dt = re.match(r"^(\d{1,2})\.(\d{1,2})\s+(\d{1,2}):(\d{2})$", text)
    if m_dt:
        day, month = int(m_dt.group(1)), int(m_dt.group(2))
        hour, minute = int(m_dt.group(3)), int(m_dt.group(4))
        try:
            year = base_time.year
            target = base_time.replace(
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
            if target < base_time:
                target = target.replace(year=year + 1)
            return target
        except ValueError:
            return None

    try:
        dt = safe_fromisoformat(text.replace(" ", "T"), tz_obj=base_time.tzinfo)
        return dt
    except Exception:
        pass

    return None


# ---------------------------------------------------------
# FSM (СОСТОЯНИЯ)
# ---------------------------------------------------------
class CreateReminderFSM(StatesGroup):
    waiting_for_text = State()
    choosing_type = State()
    choosing_days = State()
    waiting_for_start_time = State()
    waiting_for_onetime_dt = State()
    choosing_interval = State()
    waiting_for_custom_interval = State()


class TimezoneSettingsFSM(StatesGroup):
    waiting_for_manual_tz = State()


# ---------------------------------------------------------
# КЛАВИАТУРЫ
# ---------------------------------------------------------
def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Создать напоминание"),
                KeyboardButton(text="📋 Мои напоминания"),
            ],
            [
                KeyboardButton(text="⚙️ Часовой пояс"),
                KeyboardButton(text="ℹ️ Помощь"),
            ],
        ],
        resize_keyboard=True,
    )


def get_timezone_inline_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-кнопки с популярными часовыми поясами."""
    buttons = []
    # По 2 кнопки в ряд
    row = []
    for label, tz_name in POPULAR_TIMEZONES:
        row.append(
            InlineKeyboardButton(text=label, callback_data=f"settz:{tz_name}")
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(
                text="✏️ Ввести свой пояс или UTC вручную",
                callback_data="settz:manual",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_done_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Сделано!",
                    callback_data=f"done:{reminder_id}",
                )
            ]
        ]
    )


def get_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔁 По дням недели", callback_data="type:recurring"
                ),
                InlineKeyboardButton(
                    text="⏱️ Одноразовое", callback_data="type:one_time"
                ),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_days_keyboard(selected_days: Set[int]) -> InlineKeyboardMarkup:
    row1 = []
    for day_idx in range(4):
        mark = "✅ " if day_idx in selected_days else "⬜ "
        name = DAYS_NAMES[day_idx][0]
        row1.append(
            InlineKeyboardButton(
                text=f"{mark}{name}", callback_data=f"toggle_day:{day_idx}"
            )
        )

    row2 = []
    for day_idx in range(4, 7):
        mark = "✅ " if day_idx in selected_days else "⬜ "
        name = DAYS_NAMES[day_idx][0]
        row2.append(
            InlineKeyboardButton(
                text=f"{mark}{name}", callback_data=f"toggle_day:{day_idx}"
            )
        )

    sel_text = (
        ", ".join(DAYS_NAMES[d][0] for d in sorted(selected_days))
        if selected_days
        else "не выбрано"
    )

    action_row1 = [
        InlineKeyboardButton(
            text="Выбрать все", callback_data="preset_days:all"
        ),
        InlineKeyboardButton(
            text="Выбрать будни", callback_data="preset_days:weekdays"
        ),
    ]

    action_row2 = [
        InlineKeyboardButton(
            text="Выбрать выходные", callback_data="preset_days:weekends"
        ),
        InlineKeyboardButton(
            text="Сброс", callback_data="preset_days:clear"
        ),
    ]

    confirm_row = [
        InlineKeyboardButton(
            text=f"➡️ Далее ({sel_text})", callback_data="days_confirmed"
        )
    ]

    cancel_row = [
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")
    ]

    return InlineKeyboardMarkup(
        inline_keyboard=[row1, row2, action_row1, action_row2, confirm_row, cancel_row]
    )


def get_interval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="15 минут", callback_data="interval:15"
                ),
                InlineKeyboardButton(
                    text="30 минут", callback_data="interval:30"
                ),
            ],
            [
                InlineKeyboardButton(text="1 час", callback_data="interval:60"),
                InlineKeyboardButton(
                    text="2 часа", callback_data="interval:120"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="3 часа", callback_data="interval:180"
                ),
                InlineKeyboardButton(
                    text="✏️ Свой интервал", callback_data="interval:custom"
                ),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_start_time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="С 08:00", callback_data="starttime:08:00"
                ),
                InlineKeyboardButton(
                    text="С 09:00", callback_data="starttime:09:00"
                ),
                InlineKeyboardButton(
                    text="С 10:00", callback_data="starttime:10:00"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="С 12:00", callback_data="starttime:12:00"
                ),
                InlineKeyboardButton(
                    text="Прямо сейчас", callback_data="starttime:now"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Ввести другое время",
                    callback_data="starttime:custom",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_onetime_quick_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Через 10 мин", callback_data="quicktime:+10m"
                ),
                InlineKeyboardButton(
                    text="Через 30 мин", callback_data="quicktime:+30m"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Через 1 час", callback_data="quicktime:+1h"
                ),
                InlineKeyboardButton(
                    text="Через 2 часа", callback_data="quicktime:+2h"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Сегодня в 18:00", callback_data="quicktime:18:00"
                ),
                InlineKeyboardButton(
                    text="Завтра в 09:00", callback_data="quicktime:tomorrow_09"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Ввести время текстом", callback_data="quicktime:manual"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")],
        ]
    )


def get_reminder_control_keyboard(reminder: dict) -> InlineKeyboardMarkup:
    rem_id = reminder["id"]
    is_active = reminder["is_active"]
    toggle_text = "⏸️ Приостановить" if is_active else "▶️ Включить"

    buttons = [
        [
            InlineKeyboardButton(
                text=toggle_text, callback_data=f"toggle_active:{rem_id}"
            ),
            InlineKeyboardButton(
                text="🔔 Проверить сейчас",
                callback_data=f"test_trigger:{rem_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ Удалить", callback_data=f"delete_rem:{rem_id}"
            ),
            InlineKeyboardButton(
                text="🔙 К списку", callback_data="refresh_list"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------
# ОБРАБОТЧИКИ СООБЩЕНИЙ
# ---------------------------------------------------------
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_now = get_now_for_user(message.from_user.id)
    user_tz = db.get_user_timezone(message.from_user.id)
    now_str = user_now.strftime("%d.%m.%Y %H:%M")

    text = (
        f"👋 <b>Привет! Я бот-напоминалка с контролем выполнения!</b>\n\n"
        f"Чтобы напоминания приходили строго вовремя, пожалуйста, <b>выберите ваш часовой пояс</b> из списка ниже:\n\n"
        f"<i>(Сейчас установлен: <code>{user_tz}</code>, местное время: {now_str})</i>"
    )
    await message.answer(
        text,
        reply_markup=get_timezone_inline_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    text = (
        "📖 <b>Справка по использованию бота:</b>\n\n"
        "• <b>➕ Создать напоминание</b> — пошаговый конструктор любого напоминания:\n"
        "   - Свой текст сообщения\n"
        "   - Выбор дней недели или одноразовое напоминание\n"
        "   - Своя частота повторов (если не нажали ✅)\n"
        "   - Время старта\n\n"
        "• <b>⚙️ Часовой пояс</b> — настройка местного времени:\n"
        "   - Выбор из списка городов\n"
        "   - Ввод любого UTC смещения вручную\n\n"
        "• <b>📋 Мои напоминания</b> — список всех задач:\n"
        "   - Тестовая отправка прямо сейчас (кнопка «🔔 Проверить сейчас»)\n"
        "   - Пауза / возобновление\n"
        "   - Удаление\n\n"
        "• <b>Кнопка галочки «✅ Сделано!»</b>:\n"
        "   - Для повторяющихся: отключает напоминания до следующего назначенного дня.\n"
        "   - Для одноразовых: завершает задачу навсегда."
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------
# НАСТРОЙКА ЧАСОВОГО ПОЯСА
# ---------------------------------------------------------
@router.message(Command("timezone"))
@router.message(F.text == "⚙️ Часовой пояс")
async def show_timezone_settings(message: Message, state: FSMContext):
    await state.clear()
    user_now = get_now_for_user(message.from_user.id)
    user_tz = db.get_user_timezone(message.from_user.id)
    now_str = user_now.strftime("%d.%m.%Y %H:%M")

    prompt = (
        f"⚙️ <b>Настройка часового пояса</b>\n\n"
        f"🌍 Текущий пояс: <code>{user_tz}</code>\n"
        f"🕒 Ваше время сейчас: <b>{now_str}</b>\n\n"
        f"Выберите ваш регион из списка ниже или введите смещение вручную:"
    )
    await message.answer(
        prompt,
        reply_markup=get_timezone_inline_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith("settz:"))
async def process_timezone_button(callback: CallbackQuery, state: FSMContext):
    val = callback.data.split(":")[1]

    if val == "manual":
        await state.set_state(TimezoneSettingsFSM.waiting_for_manual_tz)
        text = (
            "✏️ Введите ваш часовой пояс текстом:\n\n"
            "Примеры:\n"
            "• Смещение: <code>+5</code>, <code>+3</code>, <code>-4</code>\n"
            "• Формат UTC: <code>UTC+5</code>, <code>UTC+03:00</code>\n"
            "• Название: <code>Europe/Moscow</code>, <code>Asia/Yekaterinburg</code>"
        )
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML)
        await callback.answer()
        return

    # Сохраняем выбранный из списка часовой пояс
    db.set_user_timezone(callback.from_user.id, val)
    user_now = get_now_for_user(callback.from_user.id)
    now_str = user_now.strftime("%d.%m.%Y %H:%M")

    await callback.answer("✅ Часовой пояс сохранён!", show_alert=True)
    await callback.message.edit_text(
        f"✅ <b>Часовой пояс установлен:</b> <code>{val}</code>\n"
        f"🕒 Ваше местное время: <b>{now_str}</b>\n\n"
        f"🎉 Теперь все напоминания будут приходить строго по вашему времени!\n"
        f"Нажмите <b>«➕ Создать напоминание»</b>, чтобы запланировать первую задачу.",
        parse_mode=ParseMode.HTML,
    )
    await callback.message.answer(
        "Главное меню:", reply_markup=get_main_keyboard()
    )


@router.message(TimezoneSettingsFSM.waiting_for_manual_tz)
async def process_manual_tz_input(message: Message, state: FSMContext):
    tz_text = message.text.strip()
    try:
        tz_obj = get_user_tz_obj(tz_text)
        now_test = datetime.now(tz_obj)
        db.set_user_timezone(message.from_user.id, tz_text)
        await state.clear()

        await message.answer(
            f"✅ <b>Часовой пояс успешно установлен:</b> <code>{tz_text}</code>\n"
            f"🕒 Ваше местное время: <b>{now_test.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"Все напоминания будут приходить строго по этому времени!",
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await message.answer(
            f"⚠️ Не удалось распознать часовой пояс. Попробуйте еще раз (например, <code>+5</code> или <code>Europe/Moscow</code>):",
            parse_mode=ParseMode.HTML,
        )


@router.message(F.text == "🔙 Назад в меню")
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=get_main_keyboard())


# ---------------------------------------------------------
# БЫСТРЫЙ ШАБЛОН: ФИЗРА (ПН И ПТ КАЖДЫЙ ЧАС)
# ---------------------------------------------------------
@router.message(F.text == "⚡ Физра (Пн, Пт каждый час)")
async def create_preset_pe(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user_tz = db.get_user_timezone(user_id)

    rem_id = db.add_reminder(
        user_id=user_id,
        text="Сделать тест по физре 🏃‍♂️",
        reminder_type="recurring",
        days_of_week="0,4",  # 0=Пн, 4=Пт
        interval_minutes=60,  # каждый час
        start_time="09:00",
    )

    text = (
        f"🎉 <b>Напоминание успешно создано!</b>\n\n"
        f"📌 <b>Текст:</b> Сделать тест по физре 🏃‍♂️\n"
        f"📅 <b>Дни недели:</b> Понедельник, Пятница (Пн, Пт)\n"
        f"⏰ <b>Частота повтора:</b> Каждый 1 час (пока не нажмёте ✅)\n"
        f"🕐 <b>Время начала:</b> с 09:00 (по вашему поясу <code>{user_tz}</code>)\n\n"
        f"Каждый час по Пн и Пт бот будет присылать напоминание с кнопкой ✅.\n"
        f"Как только нажмёте — бот поздравит вас и остановится до следующего назначенного дня!"
    )

    quick_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 Протестировать сейчас",
                    callback_data=f"test_trigger:{rem_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Мои напоминания", callback_data="refresh_list"
                )
            ],
        ]
    )

    await message.answer(
        text, reply_markup=quick_kb, parse_mode=ParseMode.HTML
    )


# ---------------------------------------------------------
# СПИСОК И УПРАВЛЕНИЕ НАПОМИНАНИЯМИ
# ---------------------------------------------------------
def render_reminders_list(user_id: int):
    reminders = db.get_user_reminders(user_id)
    user_now = get_now_for_user(user_id)
    user_today_str = user_now.strftime("%Y-%m-%d")

    if not reminders:
        return (
            "📭 У вас пока нет созданных напоминаний.\n\n"
            "Нажмите <b>«➕ Создать напоминание»</b> или воспользуйтесь шаблоном физры!",
            None,
        )

    text = f"📋 <b>Ваши напоминания ({len(reminders)}):</b>\n\n"
    buttons = []

    for r in reminders:
        status_icon = "🟢" if r["is_active"] else "⏸️"
        if r["is_completed"]:
            status_icon = "✅"

        type_str = (
            f"📅 {format_days_list(r['days_of_week'])}"
            if r["reminder_type"] == "recurring"
            else "⏱️ Одноразовое"
        )
        interval_str = format_interval(r["interval_minutes"])

        short_title = r["text"][:30] + ("..." if len(r["text"]) > 30 else "")
        text += (
            f"{status_icon} <b>ID {r['id']}: {html.escape(short_title)}</b>\n"
            f"   • Тип: {type_str}\n"
            f"   • Повтор: каждые {interval_str}\n"
        )
        if r["reminder_type"] == "recurring" and r["start_time"]:
            text += f"   • Старт: с {r['start_time']}\n"
        elif r["reminder_type"] == "one_time" and r["start_datetime"]:
            try:
                dt_obj = safe_fromisoformat(
                    r["start_datetime"], tz_obj=user_now.tzinfo
                )
                text += f"   • Старт: {dt_obj.strftime('%d.%m.%Y %H:%M')}\n"
            except Exception:
                pass

        if r["last_completed_date"] == user_today_str:
            text += "   • <i>Сегодня уже выполнено 🎉</i>\n"

        text += "\n"

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{status_icon} ID {r['id']}: {short_title}",
                    callback_data=f"manage_rem:{r['id']}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="➕ Создать новое", callback_data="start_wizard"
            )
        ]
    )
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("list"))
@router.message(F.text == "📋 Мои напоминания")
async def show_reminders_list(message: Message, state: FSMContext):
    await state.clear()
    text, kb = render_reminders_list(message.from_user.id)
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "refresh_list")
async def callback_refresh_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = render_reminders_list(callback.from_user.id)
    try:
        await callback.message.edit_text(
            text, reply_markup=kb, parse_mode=ParseMode.HTML
        )
    except Exception:
        await callback.message.answer(
            text, reply_markup=kb, parse_mode=ParseMode.HTML
        )
    await callback.answer()


@router.callback_query(F.data.startswith("manage_rem:"))
async def callback_manage_reminder(callback: CallbackQuery):
    rem_id = int(callback.data.split(":")[1])
    rem = db.get_reminder(rem_id)
    if not rem or rem["user_id"] != callback.from_user.id:
        await callback.answer("Напоминание не найдено.", show_alert=True)
        return

    user_now = get_now_for_user(callback.from_user.id)
    status = (
        "🟢 Активно"
        if rem["is_active"]
        else ("✅ Завершено" if rem["is_completed"] else "⏸️ На паузе")
    )
    type_str = (
        f"По дням недели ({format_days_list(rem['days_of_week'])})"
        if rem["reminder_type"] == "recurring"
        else "Одноразовое"
    )

    info = (
        f"⚙️ <b>Управление напоминанием #{rem['id']}</b>\n\n"
        f"📌 <b>Текст:</b> {html.escape(rem['text'])}\n"
        f"📊 <b>Статус:</b> {status}\n"
        f"🔁 <b>Тип:</b> {type_str}\n"
        f"⏰ <b>Интервал повтора:</b> каждые {format_interval(rem['interval_minutes'])}\n"
    )
    if rem["reminder_type"] == "recurring" and rem["start_time"]:
        info += f"🕐 <b>Время начала:</b> {rem['start_time']}\n"
    elif rem["reminder_type"] == "one_time" and rem["start_datetime"]:
        try:
            dt_obj = safe_fromisoformat(
                rem["start_datetime"], tz_obj=user_now.tzinfo
            )
            info += f"🕐 <b>Начало:</b> {dt_obj.strftime('%d.%m.%Y %H:%M')}\n"
        except Exception:
            pass

    if rem["last_completed_date"] == user_now.strftime("%Y-%m-%d"):
        info += "\n<i>✨ Сегодня задание уже отмечено как сделанное!</i>"

    await callback.message.edit_text(
        info,
        reply_markup=get_reminder_control_keyboard(rem),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_active:"))
async def callback_toggle_active(callback: CallbackQuery):
    rem_id = int(callback.data.split(":")[1])
    res = db.toggle_active(rem_id, callback.from_user.id)
    if res is None:
        await callback.answer("Ошибка: напоминание не найдено.")
        return
    msg = (
        "▶️ Напоминание включено!"
        if res
        else "⏸️ Напоминание приостановлено на паузу."
    )
    await callback.answer(msg)
    rem = db.get_reminder(rem_id)
    await callback.message.edit_reply_markup(
        reply_markup=get_reminder_control_keyboard(rem)
    )


@router.callback_query(F.data.startswith("delete_rem:"))
async def callback_delete_reminder(callback: CallbackQuery):
    rem_id = int(callback.data.split(":")[1])
    db.delete_reminder(rem_id, callback.from_user.id)
    await callback.answer("🗑️ Напоминание удалено!")
    text, kb = render_reminders_list(callback.from_user.id)
    await callback.message.edit_text(
        text, reply_markup=kb, parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("test_trigger:"))
async def callback_test_trigger(callback: CallbackQuery, bot: Bot):
    rem_id = int(callback.data.split(":")[1])
    rem = db.get_reminder(rem_id)
    if not rem:
        await callback.answer("Напоминание не найдено.")
        return

    await callback.answer("Отправляю тестовое напоминание...")
    await bot.send_message(
        chat_id=callback.from_user.id,
        text=(
            f"🔔 <b>НАПОМИНАНИЕ (тестовая проверка)!</b>\n\n"
            f"📌 <b>{html.escape(rem['text'])}</b>\n\n"
            f"<i>Интервал повтора: каждые {format_interval(rem['interval_minutes'])}, пока не нажмёте галочку.</i>"
        ),
        reply_markup=get_done_keyboard(rem["id"]),
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------
# ОБРАБОТКА НАЖАТИЯ НА ГАЛОЧКУ «✅ Сделано!»
# ---------------------------------------------------------
@router.callback_query(F.data.startswith("done:"))
async def callback_done_button(callback: CallbackQuery):
    rem_id = int(callback.data.split(":")[1])
    rem = db.get_reminder(rem_id)

    if not rem:
        await callback.answer(
            "Напоминание уже не существует или удалено.", show_alert=True
        )
        return

    user_now = get_now_for_user(callback.from_user.id)
    today_str = user_now.strftime("%Y-%m-%d")

    await callback.answer("🎉 Ура, вы молодец!", show_alert=True)

    if rem["reminder_type"] == "recurring":
        db.mark_completed_today(rem_id, today_str)
        congrats_text = (
            f"✅ <b>Ура, вы молодец! Задача выполнена!</b> 🎉\n\n"
            f"📌 «{html.escape(rem['text'])}»\n\n"
            f"На сегодня напоминания <b>остановлены</b>.\n"
            f"Следующее напоминание придёт в следующий запланированный день ({format_days_list(rem['days_of_week'])})."
        )
    else:
        db.mark_completed_permanently(rem_id)
        congrats_text = (
            f"✅ <b>Ура, вы молодец! Задача выполнена!</b> 🎉\n\n"
            f"📌 «{html.escape(rem['text'])}»\n\n"
            f"Одноразовое напоминание успешно <b>завершено</b>."
        )

    try:
        await callback.message.edit_text(
            congrats_text, reply_markup=None, parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.warning(f"Не удалось обновить сообщение с напоминанием: {e}")
        await callback.message.answer(
            congrats_text, parse_mode=ParseMode.HTML
        )


# ---------------------------------------------------------
# МАСТЕР СОЗДАНИЯ НАПОМИНАНИЯ (FSM WIZARD)
# ---------------------------------------------------------
@router.message(Command("new"))
@router.message(F.text == "➕ Создать напоминание")
@router.callback_query(F.data == "start_wizard")
async def start_wizard(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    prompt_text = (
        "📝 <b>Шаг 1 из 4: Текст напоминания</b>\n\n"
        "Напишите сообщение, о чём вам напомнить.\n"
        "<i>Например: «Сделать тест по физре», «Выпить витамины», «Сдать отчёт»</i>"
    )
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wizard")]
        ]
    )

    if isinstance(event, CallbackQuery):
        await event.message.answer(
            prompt_text, reply_markup=cancel_kb, parse_mode=ParseMode.HTML
        )
        await event.answer()
    else:
        await event.answer(
            prompt_text, reply_markup=cancel_kb, parse_mode=ParseMode.HTML
        )

    await state.set_state(CreateReminderFSM.waiting_for_text)


@router.callback_query(F.data == "cancel_wizard")
async def cancel_wizard(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Создание отменено.")
    await callback.message.edit_text("❌ Создание напоминания отменено.")


@router.message(CreateReminderFSM.waiting_for_text)
async def process_reminder_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("Пожалуйста, введите непустой текст напоминания:")
        return

    await state.update_data(text=text)
    await state.set_state(CreateReminderFSM.choosing_type)

    await message.answer(
        f"📌 Текст: <b>{html.escape(text)}</b>\n\n"
        f"<b>Шаг 2 из 4: Выберите тип напоминания:</b>\n"
        f"• <b>🔁 По дням недели</b> — повторяется в выбранные дни (например, каждый Пн и Пт)\n"
        f"• <b>⏱️ Одноразовое</b> — напомнить один раз (в конкретную дату/время)",
        reply_markup=get_type_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(
    CreateReminderFSM.choosing_type, F.data == "type:recurring"
)
async def choose_recurring_type(callback: CallbackQuery, state: FSMContext):
    await state.update_data(reminder_type="recurring", selected_days=[])
    await state.set_state(CreateReminderFSM.choosing_days)
    await callback.message.edit_text(
        "📅 <b>Шаг 3 из 4: Выберите дни недели</b>\n\n"
        "Нажимайте на кнопки, чтобы отметить нужные дни.\n"
        "Когда закончите выбор, нажмите <b>«➡️ Далее»</b>:",
        reply_markup=get_days_keyboard(set()),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.choosing_days, F.data.startswith("toggle_day:")
)
async def toggle_day_selection(callback: CallbackQuery, state: FSMContext):
    day_idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_days = set(data.get("selected_days", []))

    if day_idx in selected_days:
        selected_days.remove(day_idx)
    else:
        selected_days.add(day_idx)

    await state.update_data(selected_days=list(selected_days))
    await callback.message.edit_reply_markup(
        reply_markup=get_days_keyboard(selected_days)
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.choosing_days, F.data.startswith("preset_days:")
)
async def preset_days_action(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    if action == "all":
        selected = {0, 1, 2, 3, 4, 5, 6}
    elif action == "weekdays":
        selected = {0, 1, 2, 3, 4}
    elif action == "weekends":
        selected = {5, 6}
    else:
        selected = set()

    await state.update_data(selected_days=list(selected))
    await callback.message.edit_reply_markup(
        reply_markup=get_days_keyboard(selected)
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.choosing_days, F.data == "days_confirmed"
)
async def days_confirmed(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_days = data.get("selected_days", [])
    if not selected_days:
        await callback.answer(
            "Пожалуйста, выберите хотя бы один день недели!", show_alert=True
        )
        return

    days_str = ",".join(map(str, sorted(selected_days)))
    await state.update_data(days_of_week=days_str)
    await state.set_state(CreateReminderFSM.waiting_for_start_time)

    await callback.message.edit_text(
        f"📅 Выбранные дни: <b>{format_days_list(days_str)}</b>\n\n"
        f"🕐 <b>С какого времени начинать напоминать в эти дни?</b>\n"
        f"<i>(Например, если выбрать «С 09:00», бот в этот день начнёт присылать напоминания в 9 утра по вашему поясу и повторять их, пока вы не нажмёте ✅)</i>",
        reply_markup=get_start_time_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.waiting_for_start_time, F.data.startswith("starttime:")
)
async def process_start_time_choice(
    callback: CallbackQuery, state: FSMContext
):
    val = callback.data.split(":")[1]
    if val == "custom":
        await callback.message.edit_text(
            "✏️ Напишите время начала в формате <b>ЧЧ:ММ</b> (например, <code>09:30</code> или <code>14:00</code>):",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    if val == "now":
        start_time_str = "00:00"
    else:
        start_time_str = val

    await state.update_data(start_time=start_time_str)
    await prompt_interval_selection(callback.message, state, is_edit=True)
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_start_time)
async def process_custom_start_time_text(message: Message, state: FSMContext):
    text = message.text.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not m:
        await message.answer(
            "Некорректный формат! Введите время в виде <b>ЧЧ:ММ</b> (например, <code>09:15</code>):",
            parse_mode=ParseMode.HTML,
        )
        return

    h, m_val = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= m_val <= 59):
        await message.answer(
            "Неверные часы или минуты. Введите время от 00:00 до 23:59."
        )
        return

    start_time_str = f"{h:02d}:{m_val:02d}"
    await state.update_data(start_time=start_time_str)
    await prompt_interval_selection(message, state, is_edit=False)


@router.callback_query(
    CreateReminderFSM.choosing_type, F.data == "type:one_time"
)
async def choose_onetime_type(callback: CallbackQuery, state: FSMContext):
    await state.update_data(reminder_type="one_time")
    await state.set_state(CreateReminderFSM.waiting_for_onetime_dt)
    await callback.message.edit_text(
        "⏱️ <b>Шаг 3 из 4: Когда отправить первое напоминание?</b>\n\n"
        "Выберите быстрый вариант или напишите текстом\n"
        "(например: <code>18:30</code>, <code>+45m</code>, <code>+2h</code> или <code>30.09 14:00</code>):",
        reply_markup=get_onetime_quick_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(
    CreateReminderFSM.waiting_for_onetime_dt, F.data.startswith("quicktime:")
)
async def process_quick_onetime(callback: CallbackQuery, state: FSMContext):
    val = callback.data.split(":")[1]
    now = get_now_for_user(callback.from_user.id)

    if val == "manual":
        await callback.message.edit_text(
            "✏️ Напишите дату и время для напоминания:\n\n"
            "Примеры:\n"
            "• <code>18:30</code> (сегодня/завтра)\n"
            "• <code>+30m</code> (через 30 минут)\n"
            "• <code>+2h</code> (через 2 часа)\n"
            "• <code>30.09 15:00</code>",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    target_dt: Optional[datetime] = None
    if val == "+10m":
        target_dt = now + timedelta(minutes=10)
    elif val == "+30m":
        target_dt = now + timedelta(minutes=30)
    elif val == "+1h":
        target_dt = now + timedelta(hours=1)
    elif val == "+2h":
        target_dt = now + timedelta(hours=2)
    elif val == "18:00":
        target_dt = now.replace(
            hour=18, minute=0, second=0, microsecond=0
        )
        if target_dt <= now:
            target_dt += timedelta(days=1)
    elif val == "tomorrow_09":
        target_dt = (now + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )

    if target_dt:
        await state.update_data(start_datetime=target_dt.isoformat())
        await prompt_interval_selection(callback.message, state, is_edit=True)
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_onetime_dt)
async def process_manual_onetime_dt(message: Message, state: FSMContext):
    now = get_now_for_user(message.from_user.id)
    parsed_dt = parse_time_or_delay(message.text, now)
    if not parsed_dt:
        await message.answer(
            "⚠️ Не удалось распознать время. Попробуйте еще раз:\n"
            "Примеры: <code>18:30</code>, <code>+45m</code>, <code>+2h</code>, <code>30.09 15:00</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    await state.update_data(start_datetime=parsed_dt.isoformat())
    await prompt_interval_selection(message, state, is_edit=False)


async def prompt_interval_selection(
    message: Message, state: FSMContext, is_edit: bool
):
    await state.set_state(CreateReminderFSM.choosing_interval)
    prompt = (
        "⏰ <b>Шаг 4 из 4: Как часто напоминать, если вы не нажали ✅?</b>\n\n"
        "Бот будет присылать повторные сообщения с этим интервалом до тех пор, пока вы не нажмёте кнопку «✅ Сделано!»:"
    )
    if is_edit:
        await message.edit_text(
            prompt,
            reply_markup=get_interval_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.answer(
            prompt,
            reply_markup=get_interval_keyboard(),
            parse_mode=ParseMode.HTML,
        )


@router.callback_query(
    CreateReminderFSM.choosing_interval, F.data.startswith("interval:")
)
async def process_interval_choice(callback: CallbackQuery, state: FSMContext):
    val = callback.data.split(":")[1]
    if val == "custom":
        await state.set_state(CreateReminderFSM.waiting_for_custom_interval)
        await callback.message.edit_text(
            "✏️ Введите свой интервал повтора <b>в минутах</b> (число от 5 до 1440):\n"
            "<i>Например: 45 (каждые 45 мин) или 90 (каждые 1.5 часа)</i>",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    interval_minutes = int(val)
    await finalize_reminder_creation(
        callback.message, state, interval_minutes, is_callback=True
    )
    await callback.answer()


@router.message(CreateReminderFSM.waiting_for_custom_interval)
async def process_custom_interval_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer(
            "Пожалуйста, введите целое число минут (например: <code>45</code>):",
            parse_mode=ParseMode.HTML,
        )
        return

    minutes = int(text)
    if minutes < 1 or minutes > 10080:
        await message.answer(
            "Интервал должен быть от 1 до 10080 минут. Попробуйте еще раз:"
        )
        return

    await finalize_reminder_creation(
        message, state, minutes, is_callback=False
    )


async def finalize_reminder_creation(
    message: Message, state: FSMContext, interval_minutes: int, is_callback: bool
):
    data = await state.get_data()
    user_id = message.chat.id
    text = data["text"]
    reminder_type = data["reminder_type"]
    days_of_week = data.get("days_of_week")
    start_time = data.get("start_time")
    start_datetime = data.get("start_datetime")

    rem_id = db.add_reminder(
        user_id=user_id,
        text=text,
        reminder_type=reminder_type,
        interval_minutes=interval_minutes,
        days_of_week=days_of_week,
        start_time=start_time,
        start_datetime=start_datetime,
    )

    await state.clear()
    user_now = get_now_for_user(user_id)

    summary = (
        f"🎉 <b>Напоминание успешно создано!</b>\n\n"
        f"📌 <b>Текст:</b> {html.escape(text)}\n"
        f"🔁 <b>Тип:</b> {'По дням недели' if reminder_type == 'recurring' else 'Одноразовое'}\n"
    )

    if reminder_type == "recurring":
        summary += (
            f"📅 <b>Дни недели:</b> {format_days_list(days_of_week)}\n"
            f"🕐 <b>Время старта в эти дни:</b> {start_time}\n"
        )
    else:
        dt_obj = safe_fromisoformat(start_datetime, tz_obj=user_now.tzinfo)
        summary += f"🕐 <b>Первое напоминание:</b> {dt_obj.strftime('%d.%m.%Y %H:%M')}\n"

    summary += (
        f"⏰ <b>Частота повтора:</b> каждые {format_interval(interval_minutes)} "
        f"(пока не нажмёте ✅)\n\n"
        f"Когда придёт напоминание, нажмите под ним <b>«✅ Сделано!»</b>, чтобы отключить повторы."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔔 Протестировать сейчас",
                    callback_data=f"test_trigger:{rem_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Мои напоминания", callback_data="refresh_list"
                )
            ],
        ]
    )

    if is_callback:
        await message.edit_text(summary, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await message.answer(summary, reply_markup=kb, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------
# ФОНОВЫЙ ПЛАНИРОВЩИК (BACKGROUND WORKER)
# ---------------------------------------------------------
async def reminder_worker(bot: Bot):
    logger.info("Фоновый воркер напоминаний запущен.")
    while True:
        try:
            active_reminders = db.get_active_reminders()

            for rem in active_reminders:
                try:
                    user_id = rem["user_id"]
                    # Текущее время пользователя с учетом его личного часового пояса
                    now = get_now_for_user(user_id)
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

                        if rem["start_time"]:
                            try:
                                sh, sm = map(int, rem["start_time"].split(":"))
                                if now.time() < time(sh, sm):
                                    continue
                            except Exception:
                                pass

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


# ---------------------------------------------------------
# ОСНОВНОЙ ВХОД В ПРОГРАММУ
# ---------------------------------------------------------
async def main():
    if not BOT_TOKEN:
        print("=" * 60)
        print("ОШИБКА: Токен Telegram-бота не задан!")
        print("Укажите его в переменной окружения BOT_TOKEN или в файле .env")
        print("Пример .env файла:")
        print("BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")
        print("BOT_TIMEZONE=Europe/Moscow")
        print("=" * 60)
        sys.exit(1)

    # Веб-сервер для совместимости с бесплатным тарифом Render.com
    web_port = os.getenv("PORT")
    web_runner = None
    if web_port:
        try:
            from aiohttp import web
            app = web.Application()
            app.router.add_get("/", lambda r: web.Response(text="Reminder Bot is running!"))
            app.router.add_get("/health", lambda r: web.Response(text="OK"))
            web_runner = web.AppRunner(app)
            await web_runner.setup()
            site = web.TCPSite(web_runner, "0.0.0.0", int(web_port))
            await site.start()
            logger.info(f"Веб-сервер запущен на порту {web_port}")
        except Exception as web_err:
            logger.warning(f"Не удалось запустить веб-сервер на порту {web_port}: {web_err}")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Программа завершена.")
