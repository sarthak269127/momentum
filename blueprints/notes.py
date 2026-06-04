"""
blueprints/notes.py — Notes CRUD routes.

Notes have two special behaviours beyond simple CRUD:
  1. Autosave — the frontend sends a POST /notes/<id>/save on every
     keystroke (debounced).  The save endpoint handles the full note
     payload including the optional reminder datetime.
  2. Reminder-task sync — when a reminder is set/updated, a linked
     Task is created or updated via note_service.sync_reminder_task.
     The task is NOT deleted when the reminder is turned off.

Ownership check: _get_note_or_403 is used on all write endpoints.
"""

import logging
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from csrf_utils import csrf_protect
from extensions import db
from models import Note, Task
from services.note_service import parse_reminder_datetime, sync_reminder_task

logger = logging.getLogger(__name__)

notes_bp = Blueprint("notes", __name__, url_prefix="/notes")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_note_or_403(note_id: int) -> Note:
    """Return the Note if it belongs to current_user, else raise 404/403."""
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        abort(403)
    return note


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@notes_bp.route("/")
@login_required
def notes():
    """Notes list page — most recently updated first."""
    all_notes = (
        Note.query.filter_by(user_id=current_user.id)
        .order_by(Note.updated_at.desc())
        .all()
    )
    return render_template("main/notes.html", active="notes", notes=all_notes)


@notes_bp.route("/create", methods=["POST"])
@login_required
@csrf_protect
def create_note():
    """
    Create a new blank note and return its ID so the frontend can redirect.

    The frontend immediately navigates to /notes/<id> where the user
    starts typing.  The title and content are empty at creation.
    """
    data = request.get_json(silent=True) or {}
    note = Note(
        title=(data.get("title") or "").strip()[:200],
        content=data.get("content", ""),
        user_id=current_user.id,
    )
    db.session.add(note)
    db.session.commit()
    logger.info("Note created: id=%d user=%d", note.id, current_user.id)
    return jsonify(note.to_dict()), 201


@notes_bp.route("/<int:note_id>")
@login_required
def view_note(note_id: int):
    """Note editor page for a single note."""
    note = _get_note_or_403(note_id)
    return render_template("main/note_detail.html", active="notes", note=note)


@notes_bp.route("/<int:note_id>/save", methods=["POST"])
@login_required
@csrf_protect
def save_note(note_id: int):
    """
    Autosave endpoint — updates title, content, and reminder settings.

    Called frequently by the frontend's debounced autosave.  Must be fast.

    Reminder logic:
    - has_reminder=True + valid reminder_datetime → set/update reminder
      and sync the linked reminder task.
    - has_reminder=False → clear reminder flag and datetime, but do NOT
      delete the linked task (user manages it in Tasks).
    - has_reminder=True + invalid/missing datetime → leave existing
      reminder state unchanged (don't nuke a valid reminder on bad input).
    """
    note = _get_note_or_403(note_id)
    data = request.get_json(silent=True) or {}

    note.title = (data.get("title", note.title or "")).strip()[:200]
    note.content = data.get("content", note.content or "")
    note.updated_at = datetime.utcnow()

    has_reminder = bool(data.get("has_reminder", False))
    reminder_str = data.get("reminder_datetime", "")
    reminder_dt = parse_reminder_datetime(reminder_str)

    if has_reminder and reminder_dt:
        note.has_reminder = True
        note.reminder_datetime = reminder_dt
        sync_reminder_task(note, reminder_dt)

    elif not has_reminder:
        # User turned off the reminder — clear flag but preserve the task
        note.has_reminder = False
        note.reminder_datetime = None
        # Intentionally NOT clearing reminder_task_id

    # If has_reminder=True but reminder_dt is None (bad input) → no change

    db.session.commit()
    return jsonify(note.to_dict())


@notes_bp.route("/<int:note_id>/delete", methods=["POST"])
@login_required
@csrf_protect
def delete_note(note_id: int):
    """
    Delete a note.

    Optional JSON body: { delete_task: bool }
    If delete_task is True and the note has a linked reminder task, that
    task is also deleted.  This gives the user a choice in the delete modal.
    """
    note = _get_note_or_403(note_id)
    data = request.get_json(silent=True) or {}

    if data.get("delete_task") and note.reminder_task_id:
        linked_task = Task.query.filter_by(
            id=note.reminder_task_id,
            user_id=current_user.id,
        ).first()
        if linked_task:
            db.session.delete(linked_task)
            logger.info(
                "Reminder task deleted with note: task_id=%d note_id=%d",
                linked_task.id,
                note_id,
            )

    db.session.delete(note)
    db.session.commit()
    logger.info("Note deleted: id=%d user=%d", note_id, current_user.id)
    return jsonify({"ok": True})
