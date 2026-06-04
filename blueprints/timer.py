"""
blueprints/timer.py — Focus timer routes.

The timer page hosts both the countdown timer and stopwatch modes.  The
actual timing logic runs entirely in the browser (timer.js) using
localStorage for cross-tab persistence.  The backend is only contacted
when a session ends:
  - Natural completion of a countdown timer
  - Manual reset of a stopwatch

The /timer/save endpoint validates and persists a FocusSession row.
Stats (sessions today, total hours, weekly chart) are queried from the
database on page load and updated client-side after each save.

Heavy lifting (validation, formatting, weekly data) is in
services/focus_service.py which is also used by the dashboard.
"""

import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from csrf_utils import csrf_protect
from services.focus_service import (
    create_focus_session,
    format_focus_duration,
    get_today_stats,
    get_total_focus_hours,
    get_weekly_focus,
)
from config import config_by_name
import os

logger = logging.getLogger(__name__)

timer_bp = Blueprint("timer", __name__, url_prefix="/timer")


@timer_bp.route("/")
@login_required
def timer():
    """
    Focus timer page.

    Passes server-side stats (today's sessions, focus time, weekly data)
    to the template as embedded JSON so timer.js can initialise its UI
    without a separate API call.
    """
    uid = current_user.id
    today_stats = get_today_stats(uid)
    weekly = get_weekly_focus(uid)
    total_hours = get_total_focus_hours(uid)

    return render_template(
        "main/timer.html",
        active="timer",
        sessions_today=today_stats["session_count"],
        focus_secs_today=today_stats["total_seconds"],
        weekly=weekly,
        total_hours=total_hours,
    )


@timer_bp.route("/save", methods=["POST"])
@login_required
@csrf_protect
def save_session():
    """
    Persist a completed focus session.

    Expects JSON: { duration: int (seconds), mode: str, completed: bool }
    Returns the created session as JSON with HTTP 201.

    Validation is delegated to focus_service.create_focus_session which
    raises ValueError on invalid duration.
    """
    # Read config limits (avoids hardcoding magic numbers in route handlers)
    env = os.environ.get("FLASK_ENV", "development")
    cfg = config_by_name.get(env, config_by_name["default"])

    data = request.get_json(silent=True) or {}

    try:
        session = create_focus_session(
            user_id=current_user.id,
            duration=data.get("duration", 0),
            mode=data.get("mode", "timer"),
            completed=data.get("completed", True),
            min_secs=cfg.MIN_SESSION_DURATION_SECS,
            max_secs=cfg.MAX_SESSION_DURATION_SECS,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(session.to_dict()), 201


@timer_bp.route("/api/stats")
@login_required
def api_stats():
    """
    Return today's focus stats as JSON.

    Used by the floating timer widget and any page that needs live stats.
    Response: { today_seconds, today_minutes, sessions_today }
    """
    uid = current_user.id
    stats = get_today_stats(uid)
    secs = stats["total_seconds"]
    return jsonify({
        "today_seconds": secs,
        "today_minutes": secs // 60,
        "sessions_today": stats["session_count"],
    })
