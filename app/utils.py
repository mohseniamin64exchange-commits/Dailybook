"""Presentation and validation helpers for daily entries."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import jdatetime

TEHRAN_TIMEZONE = timezone(timedelta(hours=3, minutes=30))


PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def to_persian_digits(value) -> str:
    return str(value).translate(PERSIAN_DIGITS)


def normalize_digits(value: str) -> str:
    return str(value).translate(ARABIC_DIGITS).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


def format_amount(value) -> str:
    """Format a non-negative amount using Persian digits and grouping."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    if amount == amount.to_integral_value():
        text = f"{int(amount):,}".replace(",", "٬")
    else:
        text = f"{amount:,.2f}".rstrip("0").rstrip(".").replace(",", "٬")
    return to_persian_digits(text)


def jalali_to_gregorian_iso(value: str) -> str:
    """Convert YYYY/MM/DD or YYYY-MM-DD Jalali input to Gregorian ISO date."""
    normalized = normalize_digits(value).strip().replace("-", "/")
    parts = normalized.split("/")
    if len(parts) != 3:
        raise ValueError("تاریخ جلالی باید به شکل ۱۴۰۳/۰۱/۱۵ باشد.")
    try:
        year, month, day = (int(part) for part in parts)
        date = jdatetime.date(year, month, day).togregorian()
        return date.isoformat()
    except (TypeError, ValueError):
        raise ValueError("تاریخ جلالی واردشده معتبر نیست.") from None


def gregorian_to_jalali(value) -> str:
    if not value:
        return ""
    date = value
    if isinstance(value, str):
        from datetime import date as date_type
        date = date_type.fromisoformat(value[:10])
    return to_persian_digits(jdatetime.date.fromgregorian(date=date).strftime("%Y/%m/%d"))


def gregorian_datetime_to_jalali(value, include_time=True) -> str:
    """Format a stored Gregorian datetime as Jalali for every UI surface."""
    if not value:
        return ""
    dt = value
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    # Stored timestamps are UTC. Normalize naive SQLite values as UTC,
    # then display every timestamp consistently in Tehran local time.
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(TEHRAN_TIMEZONE)
    jdate = jdatetime.date.fromgregorian(date=dt.date()).strftime("%Y/%m/%d")
    result = jdate
    if include_time:
        result += " — " + dt.strftime("%H:%M")
    return to_persian_digits(result)


def parse_amount(value: str) -> int:
    normalized = normalize_digits(value).replace(",", "").replace("٬", "").strip()
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError):
        raise ValueError("مبلغ واردشده معتبر نیست.") from None
    if amount <= 0:
        raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد.")
    if amount != amount.to_integral_value():
        raise ValueError("مبلغ باید عدد صحیح باشد.")
    return int(amount)
