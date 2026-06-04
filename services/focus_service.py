"""
services/focus_service.py — Business logic for focus sessions.

Extracted from blueprints/timer.py and blueprints/dashboard.py to
remove duplicated weekly-chart query logic and centralise validation.

Functions here are pure data operations: they accept a user_id and
query parameters, return plain Python values (dicts, ints), and never
touch Flask request/response objects.
"""

import logging
from datetime import date, datetime, timedelta

from extensions import db
from models import FocusSession

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

VALID_MODES = frozenset({"timer", "stopwatch"})


def validate_session_duration(duration: int, min_secs: int, max_secs: int) -> int:
    """
    Clamp duration to the allowed [min_secs, max_secs] range.

    Raises ValueError with a human-readable message if duration cannot
    be parsed as an integer.
    """
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        raise ValueError("Duration must be a number.")

    if duration < min_secs:
        raise ValueError(f"Duration too short (minimum {min_secs}s).")

    # Cap silently — don't fail on oversized values, just clamp.
    return min(duration, max_secs)


# ─────────────────────────────────────────────────────────────────────────────
# Queries
# ─────────────────────────────────────────────────────────────────────────────

def get_today_stats(user_id: int) -> dict:
    """
    Return today's focus stats for the given user.

    Returns a dict with keys:
      - total_seconds: int   sum of all session durations today
      - session_count: int   number of sessions started today
    """
    today_start = datetime.combine(date.today(), datetime.min.time())

    total_seconds = (
        db.session.query(db.func.sum(FocusSession.duration))
        .filter(
            FocusSession.user_id == user_id,
            FocusSession.started_at >= today_start,
        )
        .scalar()
        or 0
    )

    session_count = (
        FocusSession.query.filter(
            FocusSession.user_id == user_id,
            FocusSession.started_at >= today_start,
        ).count()
    )

    return {"total_seconds": total_seconds, "session_count": session_count}


def get_weekly_focus(user_id: int) -> list[dict]:
    """
    Return focus minutes per day for the last 7 calendar days.

    Returns a list of 7 dicts (oldest first) each with keys:
      - day: str      abbreviated weekday name, e.g. "Mon"
      - minutes: int  total focus minutes for that day

    Used by both the timer page and the dashboard weekly chart.
    Previously this query was duplicated in both blueprints.
    """
    today = date.today()
    result = []

    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        d_start = datetime.combine(d, datetime.min.time())
        d_end = datetime.combine(d, datetime.max.time())

        secs = (
            db.session.query(db.func.sum(FocusSession.duration))
            .filter(
                FocusSession.user_id == user_id,
                FocusSession.started_at >= d_start,
                FocusSession.started_at <= d_end,
            )
            .scalar()
            or 0
        )
        result.append({"day": d.strftime("%a"), "minutes": secs // 60})

    return result


def get_total_focus_hours(user_id: int) -> float:
    """Return the all-time total focus hours rounded to one decimal place."""
    total_secs = (
        db.session.query(db.func.sum(FocusSession.duration))
        .filter(FocusSession.user_id == user_id)
        .scalar()
        or 0
    )
    return round(total_secs / 3600, 1)


def format_focus_duration(seconds: int) -> str:
    """
    Convert a raw second count into a human-readable string.

    Examples:
        3661 → "1h 1m"
        900  → "15m"
        45   → "0m"
    """
    minutes = seconds // 60
    if minutes >= 60:
        return f"{minutes // 60}h {minutes % 60}m"
    return f"{minutes}m"


# ─────────────────────────────────────────────────────────────────────────────
# Write operations
# ─────────────────────────────────────────────────────────────────────────────

def create_focus_session(
    user_id: int,
    duration: int,
    mode: str,
    completed: bool,
    min_secs: int,
    max_secs: int,
) -> FocusSession:
    """
    Validate, create, and persist a FocusSession.

    Raises ValueError if the duration is invalid.
    The session is added to the database session and committed.
    """
    duration = validate_session_duration(duration, min_secs, max_secs)

    if mode not in VALID_MODES:
        mode = "timer"

    session = FocusSession(
        duration=duration,
        mode=mode,
        completed=bool(completed),
        user_id=user_id,
    )
    db.session.add(session)
    db.session.commit()
    logger.info(
        "FocusSession created: user=%d duration=%ds mode=%s completed=%s",
        user_id,
        duration,
        mode,
        completed,
    )
    return session
