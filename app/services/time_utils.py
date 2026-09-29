from datetime import datetime, time, timedelta, timezone
import re
from typing import Optional

from app.config import DAYS_NAMES, DEFAULT_TIMEZONE, logger
from app.database.database import Database


def get_user_tz_obj(tz_name: str) -> timezone:
    """Пытается получить объект часового пояса (через zoneinfo или UTC смещение)."""
    tz_clean = tz_name.strip()
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(tz_clean)
    except Exception:
        pass

    m = re.match(r"^(?:UTC|GMT)?([+-])?(\d{1,2})(?::?(\d{2}))?$", tz_clean, re.IGNORECASE)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        hours = int(m.group(2))
        minutes = int(m.group(3) or 0)
        offset = timedelta(hours=hours * sign, minutes=minutes * sign)
        return timezone(offset, name=tz_clean)

    m_city = re.match(r"^([+-])?(\d{1,2})$", tz_clean)
    if m_city:
        sign = -1 if m_city.group(1) == "-" else 1
        hours = int(m_city.group(2))
        return timezone(timedelta(hours=hours * sign))

    logger.warning(f"Неизвестный формат часового пояса '{tz_name}', fallback to UTC")
    return timezone.utc


def get_now_for_user(user_id: int, db: Database) -> datetime:
    """Возвращает текущую дату и время для конкретного пользователя с учетом его часового пояса."""
    tz_str = db.get_user_timezone(user_id) if db else DEFAULT_TIMEZONE
    tz_obj = get_user_tz_obj(tz_str)
    return datetime.now(tz_obj)


def safe_fromisoformat(dt_str: str, tz_obj: Optional[timezone] = None) -> datetime:
    """Парсит ISO строку и приводит её к часовому поясу tz_obj."""
    try:
        dt = datetime.fromisoformat(dt_str)
    except Exception:
        dt = datetime.strptime(dt_str.split(".")[0], "%Y-%m-%dT%H:%M:%S")

    if dt.tzinfo is None and tz_obj is not None:
        dt = dt.replace(tzinfo=tz_obj)
    elif dt.tzinfo is not None and tz_obj is not None:
        dt = dt.astimezone(tz_obj)
    return dt


def parse_time_or_delay(text: str, base_time: datetime) -> Optional[datetime]:
    """Распознает задержку ('+30m', '+2h') или точное время/дату."""
    text = text.strip().lower()

    delay_match = re.match(r"^\+(\d+)\s*([mhмчdд])?$", text)
    if delay_match:
        val = int(delay_match.group(1))
        unit = delay_match.group(2) or "m"
        if unit in ("m", "м"):
            return base_time + timedelta(minutes=val)
        elif unit in ("h", "ч"):
            return base_time + timedelta(hours=val)
        elif unit in ("d", "д"):
            return base_time + timedelta(days=val)

    time_match = re.match(r"^(\d{1,2})[:.-](\d{2})$", text)
    if time_match:
        try:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return None
            target = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= base_time:
                target += timedelta(days=1)
            return target
        except ValueError:
            return None

    dt_match = re.match(r"^(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\s+(\d{1,2})[:.-](\d{2})$", text)
    if dt_match:
        try:
            day = int(dt_match.group(1))
            month = int(dt_match.group(2))
            year = int(dt_match.group(3)) if dt_match.group(3) else base_time.year
            if year < 100:
                year += 2000
            hour = int(dt_match.group(4))
            minute = int(dt_match.group(5))
            target = base_time.replace(
                year=year, month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0
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


def is_time_in_range(
    start_str: Optional[str], end_str: Optional[str], current_time: time
) -> bool:
    """Проверяет, входит ли current_time в интервал со start_str до end_str (включая полночь)."""
    if not start_str and not end_str:
        return True
    try:
        sh, sm = map(int, start_str.split(":")) if start_str else (0, 0)
        eh, em = map(int, end_str.split(":")) if end_str else (23, 59)
        start_t = time(sh, sm, 0, 0)
        end_t = time(eh, em, 59, 999999)
        if start_t <= end_t:
            return start_t <= current_time <= end_t
        else:
            return current_time >= start_t or current_time <= end_t
    except Exception:
        return True


def format_days_list(days_str: Optional[str]) -> str:
    """Форматирует строку индексов дней '0,1,4' в читаемый список 'Пн, Вт, Пт'."""
    if not days_str:
        return "Каждый день"
    try:
        indices = [int(x.strip()) for x in days_str.split(",") if x.strip().isdigit()]
        indices.sort()
        names = [DAYS_NAMES[i][0] for i in indices if 0 <= i < len(DAYS_NAMES)]
        return ", ".join(names) if names else "Не задано"
    except Exception:
        return days_str


def format_interval(minutes: int) -> str:
    """Форматирует число минут в понятную строку."""
    if minutes < 60:
        return f"{minutes} мин"
    elif minutes % 60 == 0:
        hours = minutes // 60
        if hours == 1:
            return "1 час"
        elif 2 <= hours <= 4:
            return f"{hours} часа"
        else:
            return f"{hours} часов"
    else:
        hours = minutes // 60
        rem_min = minutes % 60
        return f"{hours} ч {rem_min} мин"
