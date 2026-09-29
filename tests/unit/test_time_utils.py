from datetime import datetime, time, timezone, timedelta
import pytest

from app.services.time_utils import (
    format_days_list,
    format_interval,
    get_user_tz_obj,
    is_time_in_range,
    parse_date_string,
    parse_time_or_delay,
    safe_fromisoformat,
)


class TestTimeUtils:
    def test_format_interval(self):
        assert format_interval(15) == "15 мин"
        assert format_interval(60) == "1 час"
        assert format_interval(90) == "1 ч 30 мин"
        assert format_interval(120) == "2 часа"
        assert format_interval(150) == "2 ч 30 мин"

    def test_format_days_list(self):
        assert format_days_list("0,4") == "Пн, Пт"
        assert format_days_list("0,1,2,3,4") == "Пн, Вт, Ср, Чт, Пт"
        assert format_days_list("5,6") == "Сб, Вс"
        assert format_days_list(None) == "Каждый день"
        assert format_days_list("") == "Каждый день"

    def test_is_time_in_range_normal(self):
        # Обычный диапазон: с 09:00 до 18:00
        start = "09:00"
        end = "18:00"
        assert is_time_in_range(start, end, time(8, 59)) is False
        assert is_time_in_range(start, end, time(9, 0)) is True
        assert is_time_in_range(start, end, time(12, 30)) is True
        assert is_time_in_range(start, end, time(18, 0)) is True
        assert is_time_in_range(start, end, time(18, 1)) is False

    def test_is_time_in_range_overnight(self):
        # Ночной диапазон: с 22:00 до 06:00
        start = "22:00"
        end = "06:00"
        assert is_time_in_range(start, end, time(21, 59)) is False
        assert is_time_in_range(start, end, time(22, 0)) is True
        assert is_time_in_range(start, end, time(23, 59)) is True
        assert is_time_in_range(start, end, time(2, 0)) is True
        assert is_time_in_range(start, end, time(6, 0)) is True
        assert is_time_in_range(start, end, time(6, 1)) is False

    def test_is_time_in_range_open_boundaries(self):
        # Только start
        assert is_time_in_range("09:00", None, time(10, 0)) is True
        assert is_time_in_range("09:00", None, time(8, 0)) is False
        # Только end
        assert is_time_in_range(None, "18:00", time(10, 0)) is True
        assert is_time_in_range(None, "18:00", time(19, 0)) is False
        # Без ограничений
        assert is_time_in_range(None, None, time(12, 0)) is True

    def test_parse_time_or_delay_relative(self):
        base = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        # +30m
        res1 = parse_time_or_delay("+30m", base)
        assert res1 == base + timedelta(minutes=30)

        # +2h
        res2 = parse_time_or_delay("+2h", base)
        assert res2 == base + timedelta(hours=2)

    def test_parse_time_or_delay_exact_hh_mm(self):
        base = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        # Время позже текущего (сегодня)
        res1 = parse_time_or_delay("14:30", base)
        assert res1 == datetime(2026, 9, 29, 14, 30, tzinfo=timezone.utc)

        # Время раньше текущего (переносится на завтра)
        res2 = parse_time_or_delay("10:00", base)
        assert res2 == datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)

    def test_parse_time_or_delay_full_date(self):
        base = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
        res = parse_time_or_delay("05.10 15:45", base)
        assert res == datetime(2026, 10, 5, 15, 45, tzinfo=timezone.utc)

    def test_get_user_tz_obj(self):
        tz5 = get_user_tz_obj("+5")
        assert tz5.utcoffset(None) == timedelta(hours=5)

        tz_minus = get_user_tz_obj("-3")
        assert tz_minus.utcoffset(None) == timedelta(hours=-3)

        tz_utc = get_user_tz_obj("UTC+4")
        assert tz_utc.utcoffset(None) == timedelta(hours=4)

    def test_safe_fromisoformat(self):
        iso_str = "2026-09-29T14:30:00"
        tz = timezone(timedelta(hours=3))
        dt = safe_fromisoformat(iso_str, tz_obj=tz)
        assert dt.year == 2026
        assert dt.month == 9
        assert dt.day == 29
        assert dt.hour == 14
        assert dt.minute == 30
        assert dt.tzinfo == tz

    def test_parse_date_string(self):
        from datetime import date
        base = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)

        # Относительные слова
        d, err = parse_date_string("сегодня", base)
        assert d == date(2026, 9, 29) and err is None

        d, err = parse_date_string("завтра", base)
        assert d == date(2026, 9, 30) and err is None

        d, err = parse_date_string("послезавтра", base)
        assert d == date(2026, 10, 1) and err is None

        # Число месяца
        d, err = parse_date_string("30", base)
        assert d == date(2026, 9, 30) and err is None

        d, err = parse_date_string("5", base)
        assert d == date(2026, 10, 5) and err is None

        # ДД.ММ
        d, err = parse_date_string("30.09", base)
        assert d == date(2026, 9, 30) and err is None

        d, err = parse_date_string("29.09", base)
        assert d == date(2026, 9, 29) and err is None

        d, err = parse_date_string("28.09", base)
        assert d is None and err == "past_date"

        # ДД.ММ.ГГГГ и с годом
        d, err = parse_date_string("15.10.2026", base)
        assert d == date(2026, 10, 15) and err is None

        d, err = parse_date_string("15.10.26", base)
        assert d == date(2026, 10, 15) and err is None

        d, err = parse_date_string("01.01.2027", base)
        assert d == date(2027, 1, 1) and err is None

        # Прошлый год
        d, err = parse_date_string("01.01.2025", base)
        assert d is None and err == "past_date"

        # Некорректные календарные даты
        d, err = parse_date_string("31.02.2026", base)
        assert d is None and err == "invalid_date"

        d, err = parse_date_string("31.04.2026", base)
        assert d is None and err == "invalid_date"

        # Некорректный формат
        d, err = parse_date_string("привет", base)
        assert d is None and err == "invalid_format"

