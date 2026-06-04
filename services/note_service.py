"""
services/note_service.py — Business logic for notes and reminder tasks.

The most complex piece here is reminder-task synchronisation: when a
user sets a reminder on a note, the system auto-creates a corresponding
Task so the reminder appears in the task list.  If the reminder is
edited the task is updated; if the reminder is turned off the task
remains (the user manages it manually).

This logic was previously embedded inline in the notes blueprint —
extracting it here makes it independently testable.
"""

import logging
from datetime import date, datetime

from flask_login import current_user

from extensions import db
from models import Note, Task

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Reminder-task synchronisation
# ─────────────────────────────────────────────────────────────────────────────

def sync_reminder_task(note: Note, reminder_dt: datetime) -> Task:
    """
    Create or update the Task that mirrors a note's reminder.

    Rules:
    - If the note already has a linked reminder_task_id and that task
      still exists, update it in-place (title, description, date).
    - Otherwise create a new Task and link it to the note.

    The new/updated Task is added to the database session but NOT
    committed — callers are responsible for committing.

    Args:
        note:        The Note that has_reminder=True.
        reminder_dt: The datetime at which the reminder should fire.

    Returns:
        The Task that was created or updated.
    """
    task_title = f"Reminder: {note.title or 'Untitled'}"[:200]
    task_description = (note.content or "")[:200]
    task_date = reminder_dt.date() if reminder_dt else date.today()

    if note.reminder_task_id:
        # Try to find the existing linked task owned by this user
        existing_task = Task.query.filter_by(
            id=note.reminder_task_id,
            user_id=current_user.id,
        ).first()

        if existing_task:
            existing_task.title = task_title
            existing_task.description = task_description
            existing_task.task_date = task_date
            logger.debug("Updated reminder task id=%d for note id=%d", existing_task.id, note.id)
            return existing_task

    # No existing task — create a fresh one
    new_task = Task(
        title=task_title,
        description=task_description,
        task_date=task_date,
        priority="medium",
        is_note_reminder=True,
        source_note_id=note.id,
        user_id=current_user.id,
    )
    db.session.add(new_task)
    # Flush assigns an ID without committing so we can link it immediately
    db.session.flush()
    note.reminder_task_id = new_task.id
    logger.debug("Created reminder task id=%d for note id=%d", new_task.id, note.id)
    return new_task


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def parse_reminder_datetime(raw: str) -> datetime | None:
    """
    Parse an ISO-8601 datetime string from a form/JSON payload.

    Returns a datetime on success or None if the string is empty/invalid.
    Logs a warning for non-empty strings that fail to parse.
    """
    if not raw or not raw.strip():
        return None

    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError:
        logger.warning("Could not parse reminder datetime: %r", raw)
        return None
