import logging
import os
import sys

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

# Конфигурация окружения
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
DEFAULT_TIMEZONE: str = os.getenv("BOT_TIMEZONE", "Europe/Moscow")
DB_PATH: str = os.getenv("DB_PATH", "reminders.db")
PORT: str = os.getenv("PORT", "")
CHECK_INTERVAL_SECONDS: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "20"))

# Supabase / PostgreSQL конфигурация
DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip()
SUPABASE_DB_PASSWORD: str = os.getenv("SUPABASE_DB_PASSWORD", os.getenv("DB_PASSWORD", "")).strip()

if not DATABASE_URL and SUPABASE_URL and SUPABASE_DB_PASSWORD:
    import re
    match = re.search(r"https://([a-z0-9]+)\.supabase\.co", SUPABASE_URL)
    if match:
        ref = match.group(1)
        pooler_host = os.getenv("SUPABASE_POOLER_HOST", "aws-1-eu-west-1.pooler.supabase.com")
        DATABASE_URL = (
            f"postgresql://postgres.{ref}:{SUPABASE_DB_PASSWORD}@{pooler_host}:5432/postgres?sslmode=require"
        )


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("reminder_bot")

# Популярные часовые пояса для быстрого выбора
POPULAR_TIMEZONES = [
    ("🇷🇺 Калининград (UTC+2)", "Europe/Kaliningrad"),
    ("🇷🇺 Москва / СПб (UTC+3)", "Europe/Moscow"),
    ("🇷🇺 Самара (UTC+4)", "Europe/Samara"),
    ("🇷🇺 Екатеринбург (UTC+5)", "Asia/Yekaterinburg"),
    ("🇷🇺 Омск (UTC+6)", "Asia/Omsk"),
    ("🇷🇺 Новосибирск / Красноярск (UTC+7)", "Asia/Krasnoyarsk"),
    ("🇷🇺 Иркутск (UTC+8)", "Asia/Irkutsk"),
    ("🇷🇺 Владивосток (UTC+10)", "Asia/Vladivostok"),
    ("🇰🇿 Алматы / Астана (UTC+5)", "Asia/Almaty"),
    ("🇧🇾 Минск (UTC+3)", "Europe/Minsk"),
]

# Дни недели (0 = Пн, 6 = Вс)
DAYS_NAMES = [
    ("Пн", "Понедельник"),
    ("Вт", "Вторник"),
    ("Ср", "Среда"),
    ("Чт", "Четверг"),
    ("Пт", "Пятница"),
    ("Сб", "Суббота"),
    ("Вс", "Воскресенье"),
]
