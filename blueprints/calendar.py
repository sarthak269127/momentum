"""
blueprints/calendar.py — Monthly calendar and day-planner routes.

The calendar page renders a server-side monthly grid with task dots
for each day.  Clicking a day opens a modal that fetches that day's
tasks via /calendar/day/<date>.

Month navigation uses query params (?year=&month=) and is clamped to
valid ranges.
"""

import calendar as cal
import logging
from datetime import date, datetime

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from models import Task

logger = logging.getLogger(__name__)

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")

# Full month names indexed by month number (1-based, position 0 unused)
MONTH_NAMES = [
    "",  # placeholder so index 1 = January
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _clamp_month(year: int, month: int) -> tuple[int, int]:
    """
    Wrap month values that overflow a calendar year boundary.

    e.g. month=13 → next January; month=0 → previous December.
    """
    if month < 1:
        return year - 1, 12
    if month > 12:
        return year + 1, 1
    return year, month


def _prev_next(year: int, month: int) -> tuple[int, int, int, int]:
    """Return (prev_month, prev_year, next_month, next_year) for navigation."""
    prev_year, prev_month = _clamp_month(year, month - 1)
    next_year, next_month = _clamp_month(year, month + 1)
    return prev_month, prev_year, next_month, next_year


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@calendar_bp.route("/")
@login_required
def calendar():
    """
    Monthly calendar view.

    Query params:
      year  — int, defaults to current year
      month — int, defaults to current month

    Renders a grid of day cells, each carrying a list of tasks (title,
    priority, completed).  First-weekday offset uses Sunday=0 convention
    to match the front-end header row.
    """
    today = date.today()

    # Parse year/month from query string; fall back to current date on error
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month

    year, month = _clamp_month(year, month)

    # Python's calendar module gives first_weekday as 0=Mon; convert to 0=Sun
    first_weekday_mon, num_days = cal.monthrange(year, month)
    first_weekday_sun = (first_weekday_mon + 1) % 7

    month_start = date(year, month, 1)
    month_end = date(year, month, num_days)

    # Single query for the full month, then group by day in Python
    tasks = (
        Task.query.filter(
            Task.user_id == current_user.id,
            Task.task_date >= month_start,
            Task.task_date <= month_end,
        )
        .order_by(Task.task_date, Task.created_at)
        .all()
    )

    task_by_day: dict[int, list] = {}
    for task in tasks:
        task_by_day.setdefault(task.task_date.day, []).append(task)

    # Build the list of day objects that the template iterates over
    days = [
        {
            "number": day_num,
            "today": date(year, month, day_num) == today,
            "date_str": date(year, month, day_num).isoformat(),
            "tasks": [
                {
                    "title": t.title,
                    "completed": t.completed,
                    "priority": t.priority,
                }
                for t in task_by_day.get(day_num, [])
            ],
        }
        for day_num in range(1, num_days + 1)
    ]

    prev_month, prev_year, next_month, next_year = _prev_next(year, month)

    return render_template(
        "main/calendar.html",
        active="calendar",
        days=days,
        first_weekday=first_weekday_sun,
        month=month,
        year=year,
        month_label=f"{MONTH_NAMES[month]} {year}",
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        today=today,
    )


@calendar_bp.route("/day/<date_str>")
@login_required
def day_planner(date_str: str):
    """
    Return the task list for a single day as JSON.

    Called by the day-planner modal when the user clicks a calendar cell.
    Response: { date: str, tasks: [task.to_dict(), ...] }
    """
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        target_date = date.today()

    tasks = (
        Task.query.filter_by(user_id=current_user.id, task_date=target_date)
        .order_by(Task.created_at)
        .all()
    )

    return jsonify({"date": date_str, "tasks": [t.to_dict() for t in tasks]})
