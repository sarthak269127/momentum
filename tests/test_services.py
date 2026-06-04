"""
tests/test_services.py — Unit tests for service-layer functions.

These tests exercise business logic directly without going through HTTP,
making them fast and easy to reason about.
"""

import pytest
from datetime import date, datetime, timedelta

from models import FocusSession, Habit, HabitCompletion


class TestFocusService:
    def test_validate_duration_valid(self, app):
        from services.focus_service import validate_session_duration
        with app.app_context():
            assert validate_session_duration(300, 10, 86400) == 300

    def test_validate_duration_too_short_raises(self, app):
        from services.focus_service import validate_session_duration
        with app.app_context():
            with pytest.raises(ValueError, match="too short"):
                validate_session_duration(5, 10, 86400)

    def test_validate_duration_capped_at_max(self, app):
        from services.focus_service import validate_session_duration
        with app.app_context():
            result = validate_session_duration(999_999, 10, 86400)
            assert result == 86400

    def test_validate_duration_non_numeric_raises(self, app):
        from services.focus_service import validate_session_duration
        with app.app_context():
            with pytest.raises(ValueError, match="must be a number"):
                validate_session_duration("abc", 10, 86400)

    def test_format_focus_duration_minutes(self, app):
        from services.focus_service import format_focus_duration
        with app.app_context():
            assert format_focus_duration(900) == "15m"
            assert format_focus_duration(0) == "0m"

    def test_format_focus_duration_hours(self, app):
        from services.focus_service import format_focus_duration
        with app.app_context():
            assert format_focus_duration(3661) == "1h 1m"
            assert format_focus_duration(7200) == "2h 0m"

    def test_get_weekly_focus_returns_7_days(self, app, test_user, db):
        from services.focus_service import get_weekly_focus
        with app.app_context():
            result = get_weekly_focus(test_user.id)
            assert len(result) == 7
            for entry in result:
                assert "day" in entry
                assert "minutes" in entry

    def test_get_today_stats_empty(self, app, test_user, db):
        from services.focus_service import get_today_stats
        with app.app_context():
            stats = get_today_stats(test_user.id)
            assert stats["total_seconds"] == 0
            assert stats["session_count"] == 0


class TestHabitModel:
    """Tests for Habit model business logic methods."""

    def test_daily_habit_is_due_today(self, app, test_user, db):
        with app.app_context():
            habit = Habit(
                name="Daily",
                frequency_type="daily",
                color="#5b6ef5",
                icon="fa-solid fa-star",
                user_id=test_user.id,
            )
            assert habit.is_due_today() is True

    def test_weekday_habit_due_on_correct_day(self, app, test_user, db):
        with app.app_context():
            today_weekday = date.today().weekday()  # 0=Mon … 6=Sun
            habit = Habit(
                name="Weekday",
                frequency_type="weekdays",
                weekdays=str(today_weekday),
                color="#5b6ef5",
                icon="fa-solid fa-star",
                user_id=test_user.id,
            )
            assert habit.is_due_today() is True

    def test_weekday_habit_not_due_on_other_day(self, app, test_user, db):
        with app.app_context():
            # Set a weekday that is NOT today
            other_day = (date.today().weekday() + 1) % 7
            habit = Habit(
                name="Not today",
                frequency_type="weekdays",
                weekdays=str(other_day),
                color="#5b6ef5",
                icon="fa-solid fa-star",
                user_id=test_user.id,
            )
            assert habit.is_due_today() is False

    def test_streak_zero_with_no_completions(self, app, test_user, db):
        with app.app_context():
            habit = Habit(
                name="New habit",
                frequency_type="daily",
                color="#5b6ef5",
                icon="fa-solid fa-star",
                user_id=test_user.id,
            )
            db.session.add(habit)
            db.session.commit()
            assert habit.streak() == 0

    def test_streak_counts_consecutive_days(self, app, test_user, db):
        with app.app_context():
            habit = Habit(
                name="Streak test",
                frequency_type="daily",
                color="#5b6ef5",
                icon="fa-solid fa-star",
                user_id=test_user.id,
            )
            db.session.add(habit)
            db.session.commit()

            today = date.today()
            for i in range(3):
                db.session.add(HabitCompletion(
                    habit_id=habit.id,
                    date=today - timedelta(days=i),
                ))
            db.session.commit()

            assert habit.streak() == 3

    def test_completion_rate_perfect_daily(self, app, test_user, db):
        with app.app_context():
            habit = Habit(
                name="Perfect",
                frequency_type="daily",
                color="#5b6ef5",
                icon="fa-solid fa-star",
                user_id=test_user.id,
            )
            db.session.add(habit)
            db.session.commit()

            today = date.today()
            for i in range(30):
                db.session.add(HabitCompletion(
                    habit_id=habit.id,
                    date=today - timedelta(days=i),
                ))
            db.session.commit()

            assert habit.completion_rate() == 100


class TestNoteService:
    def test_parse_reminder_datetime_valid(self, app):
        from services.note_service import parse_reminder_datetime
        with app.app_context():
            result = parse_reminder_datetime("2030-06-15T10:30")
            assert result is not None
            assert result.year == 2030
            assert result.month == 6

    def test_parse_reminder_datetime_empty_returns_none(self, app):
        from services.note_service import parse_reminder_datetime
        with app.app_context():
            assert parse_reminder_datetime("") is None
            assert parse_reminder_datetime(None) is None

    def test_parse_reminder_datetime_invalid_returns_none(self, app):
        from services.note_service import parse_reminder_datetime
        with app.app_context():
            assert parse_reminder_datetime("not-a-date") is None
