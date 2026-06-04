"""
blueprints/habits.py — Habit tracking routes.

Habits support three frequency types (daily, weekdays, interval) and
track completions per calendar day.  The toggle endpoint adds or removes
a HabitCompletion for the given date, making the UI instantly reflective
of the user's action.

_get_habit_or_403 enforces ownership on every write endpoint.
"""

import logging
from datetime import date, timedelta

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from csrf_utils import csrf_protect
from extensions import db
from models import Habit, HabitCompletion

logger = logging.getLogger(__name__)

habits_bp = Blueprint("habits", __name__, url_prefix="/habits")

VALID_FREQUENCY_TYPES = frozenset({"daily", "interval", "weekdays"})


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_habit_or_403(habit_id: int) -> Habit:
    """Return the Habit if it belongs to current_user, else raise 404/403."""
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        abort(403)
    return habit


def _build_heatmap(habit: Habit, today: date) -> list[dict]:
    """
    Build a 30-day heatmap array for a single habit.

    Returns a list of dicts [{ date: ISO str, done: bool }, ...] ordered
    oldest-first so the frontend renders left-to-right in time order.
    """
    done_set = {c.date for c in habit.completions}
    return [
        {
            "date": (today - timedelta(days=i)).isoformat(),
            "done": (today - timedelta(days=i)) in done_set,
        }
        for i in range(29, -1, -1)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@habits_bp.route("/")
@login_required
def habits():
    """
    Habits list page.

    Passes habit_data — a list of dicts that extend each habit's to_dict()
    with a 30-day heatmap array.  Ordering: creation date ascending.
    """
    today = date.today()
    all_habits = (
        Habit.query.filter_by(user_id=current_user.id)
        .order_by(Habit.created_at)
        .all()
    )

    habit_data = []
    for habit in all_habits:
        entry = habit.to_dict()
        entry["heatmap"] = _build_heatmap(habit, today)
        habit_data.append(entry)

    return render_template(
        "main/habits.html",
        active="habits",
        habit_data=habit_data,
        today=today.isoformat(),
    )


@habits_bp.route("/add", methods=["POST"])
@login_required
@csrf_protect
def add_habit():
    """
    Create a new habit.

    Expects JSON: { name, frequency_type, weekdays?, interval_days?,
                    color?, icon? }
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return jsonify({"error": "Habit name is required."}), 400
    if len(name) > 100:
        return jsonify({"error": "Name must be 100 characters or fewer."}), 400

    frequency_type = data.get("frequency_type", "daily")
    if frequency_type not in VALID_FREQUENCY_TYPES:
        frequency_type = "daily"

    # interval_days is only meaningful for 'interval' frequency
    interval_raw = data.get("interval_days")
    interval_days = None
    if interval_raw is not None:
        try:
            interval_days = int(interval_raw)
        except (TypeError, ValueError):
            interval_days = None

    habit = Habit(
        name=name,
        frequency_type=frequency_type,
        interval_days=interval_days,
        weekdays=data.get("weekdays", ""),
        color=data.get("color", "#5b6ef5"),
        icon=data.get("icon", "fa-solid fa-star"),
        user_id=current_user.id,
    )
    db.session.add(habit)
    db.session.commit()
    logger.info("Habit created: id=%d user=%d name=%r", habit.id, current_user.id, habit.name)
    return jsonify(habit.to_dict()), 201


@habits_bp.route("/<int:habit_id>/edit", methods=["POST"])
@login_required
@csrf_protect
def edit_habit(habit_id: int):
    """
    Update an existing habit's settings.

    Only fields present in the JSON body are updated (partial update).
    """
    habit = _get_habit_or_403(habit_id)
    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = data["name"].strip()
        if name:
            habit.name = name[:100]

    if "frequency_type" in data and data["frequency_type"] in VALID_FREQUENCY_TYPES:
        habit.frequency_type = data["frequency_type"]

    if "interval_days" in data:
        habit.interval_days = data["interval_days"]

    if "weekdays" in data:
        habit.weekdays = data["weekdays"]

    if "color" in data:
        habit.color = data["color"]

    if "icon" in data:
        habit.icon = data["icon"]

    db.session.commit()
    logger.debug("Habit updated: id=%d user=%d", habit_id, current_user.id)
    return jsonify(habit.to_dict())


@habits_bp.route("/<int:habit_id>/toggle", methods=["POST"])
@login_required
@csrf_protect
def toggle_habit(habit_id: int):
    """
    Toggle completion of a habit for a specific date.

    Expects optional JSON: { date: "YYYY-MM-DD" } (defaults to today).
    If a HabitCompletion already exists for (habit_id, date) it is removed;
    otherwise one is created.

    Returns updated streak and rate so the card can update without reload.
    """
    habit = _get_habit_or_403(habit_id)
    data = request.get_json(silent=True) or {}

    raw_date = data.get("date", date.today().isoformat())
    try:
        target_date = date.fromisoformat(raw_date)
    except ValueError:
        target_date = date.today()

    existing = HabitCompletion.query.filter_by(
        habit_id=habit.id, date=target_date
    ).first()

    if existing:
        db.session.delete(existing)
        done = False
    else:
        db.session.add(HabitCompletion(habit_id=habit.id, date=target_date))
        done = True

    db.session.commit()
    logger.debug(
        "Habit toggled: id=%d date=%s done=%s user=%d",
        habit_id, target_date, done, current_user.id
    )
    return jsonify({
        "id": habit.id,
        "done": done,
        "streak": habit.streak(),
        "rate": habit.completion_rate(),
    })


@habits_bp.route("/<int:habit_id>/delete", methods=["POST"])
@login_required
@csrf_protect
def delete_habit(habit_id: int):
    """
    Delete a habit and all its completion history (cascade).

    Returns { ok: true } on success.
    """
    habit = _get_habit_or_403(habit_id)
    db.session.delete(habit)
    db.session.commit()
    logger.info("Habit deleted: id=%d user=%d", habit_id, current_user.id)
    return jsonify({"ok": True})


@habits_bp.route("/api/today")
@login_required
def api_today():
    """Return all habits due today as a JSON array (for the dashboard widget)."""
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    return jsonify([h.to_dict() for h in habits if h.is_due_today()])
