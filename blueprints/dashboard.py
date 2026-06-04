"""
blueprints/dashboard.py — Dashboard and settings routes.

The dashboard is the application's home page.  It aggregates data from
multiple models (tasks, habits, focus sessions, countdowns) to give the
user a quick overview of their day.

Data assembly is done here in the route handler rather than a service
layer because it is a simple fan-out of independent per-model queries —
there is no reusable business logic to extract.  The weekly focus chart
data is the exception: it is reused by the timer page, so it lives in
services/focus_service.py.
"""

import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from extensions import db
from models import Countdown, FocusSession, Habit, Task
from services.focus_service import format_focus_duration, get_today_stats, get_weekly_focus

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("routes", __name__)


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
@dashboard_bp.route("/home")
@login_required
def dashboard():
    """
    Main dashboard view.

    Gathers today's task counts, focus session totals, best habit streak,
    upcoming tasks (next 7 days), and the nearest 3 countdowns.
    Also passes the 7-day weekly focus chart data for Chart.js.
    """
    today = date.today()
    now = datetime.now()
    uid = current_user.id

    # ── Tasks ──────────────────────────────────────────────────────────────
    # Load all tasks once, then partition in Python to avoid multiple queries
    all_tasks = Task.query.filter_by(user_id=uid).all()
    todays_tasks = [t for t in all_tasks if t.task_date == today]
    completed_tasks = [t for t in todays_tasks if t.completed]
    pending_tasks = [t for t in todays_tasks if not t.completed]
    overdue_tasks = [t for t in all_tasks if t.task_date < today and not t.completed]

    # ── Focus time ─────────────────────────────────────────────────────────
    focus_stats = get_today_stats(uid)
    focus_label = format_focus_duration(focus_stats["total_seconds"])

    # ── Habits ─────────────────────────────────────────────────────────────
    habits = Habit.query.filter_by(user_id=uid).all()
    best_streak = max((h.streak() for h in habits), default=0)

    # ── Upcoming countdowns (future only, limited to 3) ────────────────────
    countdowns = (
        Countdown.query.filter(
            Countdown.user_id == uid,
            Countdown.target_date > now,
        )
        .order_by(Countdown.target_date)
        .limit(3)
        .all()
    )

    # ── Upcoming tasks (next 7 days, pending, max 5) ───────────────────────
    upcoming_limit = 7
    upcoming_tasks = (
        Task.query.filter(
            Task.user_id == uid,
            Task.task_date > today,
            Task.task_date <= today + timedelta(days=upcoming_limit),
            Task.completed == False,
        )
        .order_by(Task.task_date)
        .limit(5)
        .all()
    )

    # ── Weekly focus chart data ────────────────────────────────────────────
    weekly_focus = get_weekly_focus(uid)

    return render_template(
        "main/dashboard.html",
        active="dashboard",
        now=now,
        date=now.strftime("%A, %B %d"),
        today=today,
        todays_tasks=todays_tasks,
        tasks_today=len(todays_tasks),
        completed_count=len(completed_tasks),
        pending_count=len(pending_tasks),
        overdue_count=len(overdue_tasks),
        focus_time=focus_label,
        streak=best_streak,
        countdowns=countdowns,
        upcoming_tasks=upcoming_tasks,
        weekly_focus=weekly_focus,
        habits=habits,
    )


@dashboard_bp.route("/settings")
@login_required
def settings():
    """Simple settings page — currently display-only."""
    return render_template("main/settings.html", active="settings")
