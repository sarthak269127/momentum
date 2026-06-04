"""
blueprints/tasks.py — Task CRUD routes.

All routes follow the pattern:
  - GET  → render a template with server-side data
  - POST → JSON API endpoint protected by CSRF, returns JSON

Ownership is enforced on every write operation: a user can only modify
or delete tasks they own.  _get_task_or_403 centralises this check.
"""

import logging
from datetime import date

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from csrf_utils import csrf_protect
from extensions import db
from models import Task

logger = logging.getLogger(__name__)

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")

# Allowed priority values — used for input sanitisation
VALID_PRIORITIES = frozenset({"low", "medium", "high"})


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_task_or_403(task_id: int) -> Task:
    """
    Return the Task with the given ID if it belongs to the current user.

    Raises 404 if the task does not exist, 403 if it belongs to another user.
    """
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        abort(403)
    return task


def _parse_task_date(raw: str | None, fallback: date | None = None) -> date:
    """
    Parse an ISO date string (YYYY-MM-DD) from a request payload.

    Falls back to today if the value is absent or malformed.
    Only the first 10 characters are parsed to tolerate datetime strings.
    """
    if not raw:
        return fallback or date.today()
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return fallback or date.today()


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@tasks_bp.route("/")
@login_required
def tasks():
    """
    Tasks list page.

    Returns all tasks for the current user ordered by date then creation
    time.  Filtering (today/overdue/upcoming) happens client-side in tasks.js.
    """
    today = date.today()
    all_tasks = (
        Task.query.filter_by(user_id=current_user.id)
        .order_by(Task.task_date, Task.created_at)
        .all()
    )
    return render_template("main/tasks.html", active="tasks", tasks=all_tasks, today=today)


@tasks_bp.route("/add", methods=["POST"])
@login_required
@csrf_protect
def add_task():
    """
    Create a new task.

    Expects JSON: { title, task_date?, priority?, description? }
    Returns the created task as JSON with HTTP 201.
    """
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()

    if not title:
        return jsonify({"error": "Title is required."}), 400
    if len(title) > 200:
        return jsonify({"error": "Title must be 200 characters or fewer."}), 400

    priority = data.get("priority", "medium")
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    description = (data.get("description") or "").strip()[:1000]

    task = Task(
        title=title,
        description=description,
        priority=priority,
        task_date=_parse_task_date(data.get("task_date") or data.get("due_date")),
        user_id=current_user.id,
    )
    db.session.add(task)
    db.session.commit()
    logger.info("Task created: id=%d user=%d title=%r", task.id, current_user.id, task.title)
    return jsonify(task.to_dict()), 201


@tasks_bp.route("/edit/<int:task_id>", methods=["POST"])
@login_required
@csrf_protect
def edit_task(task_id: int):
    """
    Update an existing task's fields.

    Only the fields present in the JSON body are updated (partial update).
    Returns the updated task as JSON.
    """
    task = _get_task_or_403(task_id)
    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = data["title"].strip()
        if title and len(title) <= 200:
            task.title = title

    if "description" in data:
        task.description = (data["description"] or "").strip()[:1000]

    if "priority" in data and data["priority"] in VALID_PRIORITIES:
        task.priority = data["priority"]

    if "task_date" in data:
        task.task_date = _parse_task_date(data["task_date"], fallback=task.task_date)

    db.session.commit()
    logger.debug("Task updated: id=%d user=%d", task_id, current_user.id)
    return jsonify(task.to_dict())


@tasks_bp.route("/toggle/<int:task_id>", methods=["POST"])
@login_required
@csrf_protect
def toggle_task(task_id: int):
    """
    Toggle a task's completed status.

    Returns { id, completed } — the minimal payload the frontend needs
    to update the UI without a page reload.
    """
    task = _get_task_or_403(task_id)
    task.completed = not task.completed
    db.session.commit()
    logger.debug("Task toggled: id=%d completed=%s", task_id, task.completed)
    return jsonify({"id": task.id, "completed": task.completed})


@tasks_bp.route("/delete/<int:task_id>", methods=["POST"])
@login_required
@csrf_protect
def delete_task(task_id: int):
    """
    Permanently delete a task.

    Returns { ok: true } on success.
    """
    task = _get_task_or_403(task_id)
    db.session.delete(task)
    db.session.commit()
    logger.info("Task deleted: id=%d user=%d", task_id, current_user.id)
    return jsonify({"ok": True})


@tasks_bp.route("/api/list")
@login_required
def api_list():
    """
    Return all tasks for the current user as a JSON array.

    Used when the frontend needs a fresh task list without a full page reload.
    """
    all_tasks = (
        Task.query.filter_by(user_id=current_user.id)
        .order_by(Task.task_date, Task.created_at)
        .all()
    )
    return jsonify([t.to_dict() for t in all_tasks])
