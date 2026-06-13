"""
utils/financial_year.py
------------------------
Indian financial year utilities.
FY 2025-26 = April 1, 2025 to March 31, 2026.
"""

from datetime import datetime


def fy_to_dates(financial_year: str) -> tuple[datetime, datetime]:
    """
    Convert "2025-26" → (datetime(2025,4,1), datetime(2026,3,31,23,59,59))
    """
    try:
        start_year = int(financial_year.split("-")[0])
    except (ValueError, IndexError):
        raise ValueError(
            f"Invalid financial year format: '{financial_year}'. "
            f"Expected format: '2025-26'"
        )
    end_year = start_year + 1
    period_start = datetime(start_year, 4, 1, 0, 0, 0)
    period_end   = datetime(end_year,   3, 31, 23, 59, 59)
    return period_start, period_end


def date_to_fy(dt: datetime) -> str:
    """
    Convert a datetime → Indian financial year string.
    datetime(2025, 11, 15) → "2025-26"
    datetime(2026, 2, 10)  → "2025-26"
    datetime(2026, 4, 1)   → "2026-27"
    """
    if dt.month >= 4:
        return f"{dt.year}-{str(dt.year + 1)[2:]}"
    else:
        return f"{dt.year - 1}-{str(dt.year)[2:]}"


def current_fy() -> str:
    """Returns the current Indian financial year."""
    return date_to_fy(datetime.now())


def fy_label(financial_year: str) -> str:
    """
    Returns a human-readable label.
    "2025-26" → "FY 2025-26 (Apr 2025 – Mar 2026)"
    """
    start_year = int(financial_year.split("-")[0])
    end_year   = start_year + 1
    return f"FY {financial_year} (Apr {start_year} – Mar {end_year})"