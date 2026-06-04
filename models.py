"""
models.py — SQLAlchemy ORM models for Momentum.

Model hierarchy
───────────────
  User
    ├── Task            (one-to-many, cascade delete)
    ├── Note            (one-to-many, cascade delete)
    │     └── Task      (optional reminder task linked via FK)
    ├── Habit           (one-to-many, cascade delete)
    │     └── HabitCompletion  (one-to-many, cascade delete)
    ├── FocusSession    (one-to-many, cascade delete)
    └── Countdown       (one-to-many, cascade delete)

Design decisions
────────────────
- All user-owned models carry a non-nullable user_id FK with an index
  so per-user queries never do full-table scans.
- Composite indexes are added where queries filter on two columns together
  (e.g. tasks by user + date, habit completions by habit + date).
- Cascade rules are set to "all, delete-orphan" so deleting a User (or
  Habit) automatically removes all child rows without extra queries.
- to_dict() methods are intentionally thin — they return only what the
  frontend needs.  Business-logic calculations belong in services/.
"""

from datetime import datetime, date, timedelta

from extensions import db
from flask_login import UserMixin


# ─────────────────────────────────────────────────────────────────────────────
# User
# ─────────────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    """
    Core account model.

    flask-login requires UserMixin which provides default implementations
    of is_authenticated, is_active, is_anonymous, and get_id().
    The password field stores a Werkzeug-generated bcrypt hash — never
    the plaintext password.
    """

    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email      = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password   = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships — lazy="dynamic" returns a query object so callers can
    # add filters without loading all rows.  cascade ensures children are
    # removed when the user is deleted.
    tasks          = db.relationship("Task",         backref="user", lazy="dynamic", cascade="all, delete-orphan")
    notes          = db.relationship("Note",         backref="user", lazy="dynamic", cascade="all, delete-orphan")
    habits         = db.relationship("Habit",        backref="user", lazy="dynamic", cascade="all, delete-orphan")
    focus_sessions = db.relationship("FocusSession", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    countdowns     = db.relationship("Countdown",    backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Task
# ─────────────────────────────────────────────────────────────────────────────

class Task(db.Model):
    """
    A single to-do item belonging to a user.

    Tasks have a task_date (the day they are due), a priority level,
    and an optional link back to a Note when they were created as a
    reminder from the note editor.

    The composite index ix_tasks_user_date makes the common dashboard
    query "tasks for user X on date Y" efficient.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        # Covers queries that filter by user_id AND task_date together —
        # the most common query pattern in dashboard and calendar views.
        db.Index("ix_tasks_user_date", "user_id", "task_date"),
    )

    id               = db.Column(db.Integer, primary_key=True)
    title            = db.Column(db.String(200), nullable=False)
    description      = db.Column(db.Text)
    completed        = db.Column(db.Boolean, default=False, index=True)
    # Priority levels: low | medium | high
    priority         = db.Column(db.String(20), default="medium", nullable=False)
    task_date        = db.Column(db.Date, nullable=False, index=True)
    # True when the task was auto-created from a note's reminder
    is_note_reminder = db.Column(db.Boolean, default=False)
    # FK back to the source note (nullable — only set for reminder tasks)
    source_note_id   = db.Column(db.Integer, db.ForeignKey("notes.id"), nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict for API responses."""
        return {
            "id":          self.id,
            "title":       self.title,
            "description": self.description or "",
            "completed":   self.completed,
            "priority":    self.priority,
            "task_date":   self.task_date.isoformat() if self.task_date else None,
            "created_at":  self.created_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title!r} date={self.task_date}>"


# ─────────────────────────────────────────────────────────────────────────────
# Note
# ─────────────────────────────────────────────────────────────────────────────

class Note(db.Model):
    """
    A free-form text note with optional browser-notification reminder.

    When has_reminder is True the user has set a reminder_datetime.
    The backend creates a linked Task (reminder_task_id) on the same
    date so the reminder also appears in the tasks list.  The task is
    NOT deleted when the reminder is toggled off — the user manages it
    in the Tasks view.
    """

    __tablename__ = "notes"

    id                = db.Column(db.Integer, primary_key=True)
    title             = db.Column(db.String(200))
    content           = db.Column(db.Text, nullable=False, default="")
    has_reminder      = db.Column(db.Boolean, default=False, index=True)
    reminder_datetime = db.Column(db.DateTime, nullable=True)
    # FK to the auto-created Task that mirrors this reminder
    reminder_task_id  = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    user_id           = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict for API responses."""
        return {
            "id":                self.id,
            "title":             self.title or "",
            "content":           self.content or "",
            "has_reminder":      self.has_reminder,
            "reminder_datetime": self.reminder_datetime.isoformat() if self.reminder_datetime else None,
            "updated_at":        self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Note id={self.id} title={self.title!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Habit + HabitCompletion
# ─────────────────────────────────────────────────────────────────────────────

class Habit(db.Model):
    """
    A recurring behaviour the user wants to track.

    Frequency types
    ───────────────
    - daily:    due every calendar day.
    - weekdays: due on specific days of the week stored as a comma-
                separated list of integers (0=Mon … 6=Sun).
    - interval: due every N days counting from created_at.

    Streak and completion-rate calculations live here as model methods
    because they are simple date arithmetic that depends only on the
    habit's own completion records — no cross-model joins needed.
    For more complex aggregates (e.g. multi-habit dashboard stats) see
    services/habit_service.py.
    """

    __tablename__ = "habits"

    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(100), nullable=False)
    # 'daily' | 'interval' | 'weekdays'
    frequency_type = db.Column(db.String(50), nullable=False)
    # Only used when frequency_type == 'interval'
    interval_days  = db.Column(db.Integer, nullable=True)
    # Comma-separated weekday ints, e.g. '0,1,4' — only when frequency_type == 'weekdays'
    weekdays       = db.Column(db.String(50), nullable=True)
    color          = db.Column(db.String(20), default="#5b6ef5", nullable=False)
    icon           = db.Column(db.String(60), default="fa-solid fa-star", nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # HabitCompletion rows are loaded eagerly via lazy=True (joined load).
    # For a user with many habits this is fine — completion sets per habit
    # are small (max 30 rows for streak/rate calculations).
    completions = db.relationship(
        "HabitCompletion",
        backref="habit",
        lazy=True,
        cascade="all, delete-orphan",
    )

    # ── Business logic ────────────────────────────────────────────────────────

    def is_due_today(self) -> bool:
        """Return True if this habit is scheduled for today."""
        today = date.today()

        if self.frequency_type == "daily":
            return True

        if self.frequency_type == "weekdays":
            if not self.weekdays:
                return False
            # Parse comma-separated weekday integers
            active_days = [
                int(d) for d in self.weekdays.split(",") if d.strip().isdigit()
            ]
            return today.weekday() in active_days

        if self.frequency_type == "interval":
            if not self.interval_days:
                return False
            # Count days from creation; habit is due every interval_days days
            delta = (today - self.created_at.date()).days
            return delta % self.interval_days == 0

        return False

    def streak(self) -> int:
        """
        Return the current consecutive-day streak.

        Walk backwards from today through completion dates; stop as soon
        as a day is missed.  Only considers calendar days, not frequency.
        """
        # Deduplicate completion dates and sort newest-first
        done_dates = sorted({c.date for c in self.completions}, reverse=True)
        if not done_dates:
            return 0

        streak = 0
        check = date.today()
        for d in done_dates:
            if d == check:
                streak += 1
                check = check - timedelta(days=1)
            elif d < check:
                # Gap found — streak is broken
                break
        return streak

    def completion_rate(self) -> int:
        """
        Return the percentage of due days completed over the last 30 days.

        Returns an integer 0–100.  Returns 0 if the habit was never due
        in the window (avoids division by zero).
        """
        today = date.today()
        done_set = {c.date for c in self.completions}
        due_count = 0
        done_count = 0

        for i in range(30):
            d = today - timedelta(days=i)
            is_due = self._is_due_on(d)
            if is_due:
                due_count += 1
                if d in done_set:
                    done_count += 1

        return round((done_count / due_count) * 100) if due_count else 0

    def _is_due_on(self, d: date) -> bool:
        """
        Check whether the habit was due on a specific past date.

        Extracted from completion_rate() to avoid repeated conditional
        logic in the 30-day loop.
        """
        if self.frequency_type == "daily":
            return True
        if self.frequency_type == "weekdays" and self.weekdays:
            active_days = [int(x) for x in self.weekdays.split(",") if x.strip().isdigit()]
            return d.weekday() in active_days
        if self.frequency_type == "interval" and self.interval_days:
            delta = (d - self.created_at.date()).days
            return delta >= 0 and delta % self.interval_days == 0
        return False

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict including computed stats."""
        today = date.today()
        done_today = any(c.date == today for c in self.completions)
        return {
            "id":               self.id,
            "name":             self.name,
            "frequency_type":   self.frequency_type,
            "interval_days":    self.interval_days,
            "weekdays":         self.weekdays or "",
            "color":            self.color,
            "icon":             self.icon,
            "is_due_today":     self.is_due_today(),
            "done_today":       done_today,
            "streak":           self.streak(),
            "rate":             self.completion_rate(),
            "completion_dates": [c.date.isoformat() for c in self.completions],
        }

    def __repr__(self) -> str:
        return f"<Habit id={self.id} name={self.name!r} freq={self.frequency_type}>"


class HabitCompletion(db.Model):
    """
    One record per day a habit was completed.

    The composite index makes "was this habit done on this date?" lookups
    very fast, which is called on every habit card render.
    """

    __tablename__ = "habit_completions"
    __table_args__ = (
        db.Index("ix_habit_completions_habit_date", "habit_id", "date"),
    )

    id       = db.Column(db.Integer, primary_key=True)
    date     = db.Column(db.Date, nullable=False)
    habit_id = db.Column(db.Integer, db.ForeignKey("habits.id"), nullable=False)

    def __repr__(self) -> str:
        return f"<HabitCompletion habit_id={self.habit_id} date={self.date}>"


# ─────────────────────────────────────────────────────────────────────────────
# FocusSession
# ─────────────────────────────────────────────────────────────────────────────

class FocusSession(db.Model):
    """
    A completed (or manually ended) focus session.

    Sessions are written to the database only when they end — either
    when a countdown timer reaches zero (completed=True) or when a
    stopwatch is manually reset (completed=False).  They are never
    written on pause.

    duration is stored in seconds because it is always summed for
    totals, and integer arithmetic is exact.
    """

    __tablename__ = "focus_sessions"

    id         = db.Column(db.Integer, primary_key=True)
    # Session length in seconds (minimum 10, maximum 86400 / 24 h)
    duration   = db.Column(db.Integer, nullable=False)
    # 'timer' (countdown) or 'stopwatch' (count-up)
    mode       = db.Column(db.String(30), default="timer", nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, index=True, nullable=False)
    # True when the timer ran to completion; False for stopwatch/manual end
    completed  = db.Column(db.Boolean, default=True, nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict for API responses."""
        return {
            "id":         self.id,
            "duration":   self.duration,
            "mode":       self.mode,
            "started_at": self.started_at.isoformat(),
            "completed":  self.completed,
        }

    def __repr__(self) -> str:
        return f"<FocusSession id={self.id} duration={self.duration}s mode={self.mode}>"


# ─────────────────────────────────────────────────────────────────────────────
# Countdown
# ─────────────────────────────────────────────────────────────────────────────

class Countdown(db.Model):
    """
    An upcoming event the user wants to count down to.

    target_date stores the full datetime so users can count down to a
    specific time (e.g. a flight at 14:30), not just a day.  The
    frontend displays days/hours/minutes/seconds remaining.
    """

    __tablename__ = "countdowns"

    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    target_date = db.Column(db.DateTime, nullable=False, index=True)
    emoji       = db.Column(db.String(10), default="🎯", nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict for API responses."""
        return {
            "id":          self.id,
            "title":       self.title,
            "target_date": self.target_date.isoformat(),
            "emoji":       self.emoji or "🎯",
        }

    def __repr__(self) -> str:
        return f"<Countdown id={self.id} title={self.title!r} target={self.target_date}>"
