"""Format-inference layer: parse dates, times, numbers, currencies without
hardcoding formats. The LLM produces RawInvoice (strings as printed); this
module converts that into a typed Invoice."""
from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Optional

import dateparser
from dateutil import parser as dateutil_parser

from config import (
    ARABIC_DECIMAL,
    ARABIC_INDIC_DIGITS,
    ARABIC_THOUSANDS,
    PERSIAN_DIGITS,
)
from schema import Invoice, LineItem, RawInvoice, RawLineItem


# ──────────────────────────── Digits ────────────────────────────

def asciify_digits(s: str) -> str:
    """Translate Arabic-Indic / Persian digits and Arabic separators to ASCII."""
    if not s:
        return s
    return (
        s.translate(ARABIC_INDIC_DIGITS)
         .translate(PERSIAN_DIGITS)
         .translate(ARABIC_DECIMAL)
         .translate(ARABIC_THOUSANDS)
    )


# ──────────────────────────── Date / time ────────────────────────────

_DATE_SETTINGS = {
    "DATE_ORDER": "DMY",          # Egypt/Saudi convention; dateparser still tries others
    "PREFER_DAY_OF_MONTH": "first",
    "RETURN_AS_TIMEZONE_AWARE": False,
}


_YEAR_FIRST_RE = re.compile(r"^\s*\d{4}[-/.]")


def normalize_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    cleaned = asciify_digits(s).strip()
    # If the string starts with a 4-digit year, override the DMY hint.
    settings = dict(_DATE_SETTINGS)
    if _YEAR_FIRST_RE.match(cleaned):
        settings["DATE_ORDER"] = "YMD"
    parsed = dateparser.parse(cleaned, languages=["ar", "en"], settings=settings)
    if parsed is None:
        try:
            parsed = dateutil_parser.parse(
                cleaned,
                dayfirst=not _YEAR_FIRST_RE.match(cleaned),
                yearfirst=bool(_YEAR_FIRST_RE.match(cleaned)),
                fuzzy=True,
            )
        except (ValueError, OverflowError):
            return None
    return parsed.date()


def normalize_time(s: Optional[str]) -> Optional[time]:
    if not s:
        return None
    cleaned = asciify_digits(s).strip()
    # Arabic AM/PM markers — dateparser handles these but help it along.
    cleaned = re.sub(r"\s*ص\b", " AM", cleaned)
    cleaned = re.sub(r"\s*م\b", " PM", cleaned)
    parsed = dateparser.parse(cleaned, languages=["ar", "en"], settings=_DATE_SETTINGS)
    if parsed is None:
        try:
            parsed = dateutil_parser.parse(cleaned, fuzzy=True)
        except (ValueError, OverflowError):
            return None
    return parsed.time()


def format_time_12h(t: Optional[time]) -> Optional[str]:
    """Render a datetime.time as '3:50:58 PM' (no leading zero on the hour).

    Returns None if t is None. Drops the seconds component when it is zero
    so trivially clean times read as '3:50 PM' rather than '3:50:00 PM'."""
    if t is None:
        return None
    suffix = "AM" if t.hour < 12 else "PM"
    hour = t.hour % 12 or 12
    if t.second:
        return f"{hour}:{t.minute:02d}:{t.second:02d} {suffix}"
    return f"{hour}:{t.minute:02d} {suffix}"


# ──────────────────────────── Numbers ────────────────────────────


def _infer_decimal(num_str: str) -> Optional[float]:
    """Convert a digit string with possible separators into a float.

    Rules (no hardcoded locale):
    - If both `.` and `,` present, the LAST occurrence is the decimal separator,
      everything else is a thousands separator.
    - If only `,` is present and exactly 2 digits follow it, it's a decimal.
    - If only `.` is present, it's a decimal.
    - Otherwise, treat all separators as thousands and return an integer-valued float.
    """
    s = num_str.strip()
    if not s:
        return None

    # Strip leading sign if any
    sign = -1 if s.startswith("-") else 1
    s = s.lstrip("+-").strip()

    has_dot = "." in s
    has_comma = "," in s

    if has_dot and has_comma:
        # Last separator wins as the decimal point.
        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        if last_dot > last_comma:
            decimal_pos = last_dot
            thousands_char = ","
        else:
            decimal_pos = last_comma
            thousands_char = "."
        int_part = s[:decimal_pos].replace(thousands_char, "").replace(".", "").replace(",", "")
        frac_part = s[decimal_pos + 1:]
        try:
            return sign * float(f"{int_part}.{frac_part}")
        except ValueError:
            return None

    if has_comma and not has_dot:
        # Could be decimal (1,50) or thousands (1,500). Heuristic: last group length.
        parts = s.split(",")
        last_group = parts[-1]
        if len(parts) == 2 and 1 <= len(last_group) <= 2:
            try:
                return sign * float(f"{parts[0]}.{last_group}")
            except ValueError:
                return None
        # Thousands separators: drop them all.
        try:
            return sign * float(s.replace(",", ""))
        except ValueError:
            return None

    if has_dot and not has_comma:
        parts = s.split(".")
        # Multiple dots → all thousands except last (e.g. "1.234.567")
        if len(parts) > 2:
            try:
                return sign * float("".join(parts[:-1]) + "." + parts[-1])
            except ValueError:
                try:
                    return sign * float("".join(parts))
                except ValueError:
                    return None
        try:
            return sign * float(s)
        except ValueError:
            return None

    try:
        return sign * float(s)
    except ValueError:
        return None


_NUMBER_PATTERN = re.compile(r"[-+]?[\d.,]+")


def normalize_number(s: Optional[str]) -> Optional[float]:
    """Parse a printed number string → float (or None if no digits found).

    Currency tokens, letters, and other non-numeric noise are ignored —
    we just locate the first numeric chunk and infer decimal/thousands
    separators from its shape.

    Examples (after asciify_digits):
        "123.45 ج.م"  → 123.45
        "1.234,50"    → 1234.5
        "$12.99"      → 12.99
        "x2"          → 2.0
    """
    if s is None:
        return None
    cleaned = asciify_digits(str(s)).strip()
    if not cleaned:
        return None

    # Strip leading qty-marker like 'x2' or 'X 3'.
    cleaned = re.sub(r"(?i)^x\s*", "", cleaned).strip()

    match = _NUMBER_PATTERN.search(cleaned)
    if not match:
        return None

    return _infer_decimal(match.group(0))


# ──────────────────────────── Validation ────────────────────────────

def _normalize_item(raw: RawLineItem) -> LineItem:
    return LineItem(
        name=raw.name.strip(),
        quantity=normalize_number(raw.quantity_raw),
        unit_price=normalize_number(raw.unit_price_raw),
        total_price=normalize_number(raw.total_price_raw),
        raw_line=raw.raw_line,
    )


def validate(raw_dict: dict) -> Invoice:
    """Validate the LLM's RawInvoice dict and produce a typed Invoice."""
    raw = RawInvoice.model_validate(raw_dict)

    return Invoice(
        date=normalize_date(raw.date_raw),
        time=format_time_12h(normalize_time(raw.time_raw)),
        total=normalize_number(raw.total_raw),
        category=raw.category,  # LLM's pick; category.py may override via rules
        items=[_normalize_item(it) for it in raw.items],
    )


__all__ = [
    "asciify_digits",
    "normalize_date",
    "normalize_time",
    "format_time_12h",
    "normalize_number",
    "validate",
]
