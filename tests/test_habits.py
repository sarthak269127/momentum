"""
tests/test_habits.py — Tests for habit creation, toggling, and deletion.
"""

import json
from datetime import date

import pytest

from models import Habit, HabitCompletion


def _post_json(client, url, data):
    return client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
    )


class TestHabitsPage:
    def test_habits_page_requires_login(self, client):
        res = client.get("/habits/", follow_redirects=True)
        assert b"Sign in" in res.data

    def test_habits_page_renders(self, auth_client):
        res = auth_client.get("/habits/")
        assert res.status_code == 200


class TestAddHabit:
    def test_add_daily_habit(self, auth_client, test_user, db):
        res = _post_json(auth_client, "/habits/add", {
            "name": "Morning run",
            "frequency_type": "daily",
        })
        assert res.status_code == 201
        body = res.get_json()
        assert body["name"] == "Morning run"
        assert body["frequency_type"] == "daily"

    def test_add_weekday_habit(self, auth_client, test_user, db):
        res = _post_json(auth_client, "/habits/add", {
            "name": "Gym",
            "frequency_type": "weekdays",
            "weekdays": "0,2,4",  # Mon, Wed, Fri
        })
        assert res.status_code == 201
        assert res.get_json()["weekdays"] == "0,2,4"

    def test_add_interval_habit(self, auth_client, test_user, db):
        res = _post_json(auth_client, "/habits/add", {
            "name": "Deep clean",
            "frequency_type": "interval",
            "interval_days": 7,
        })
        assert res.status_code == 201
        assert res.get_json()["interval_days"] == 7

    def test_add_habit_empty_name_rejected(self, auth_client):
        res = _post_json(auth_client, "/habits/add", {"name": ""})
        assert res.status_code == 400

    def test_add_habit_invalid_frequency_defaults_to_daily(self, auth_client, test_user, db):
        res = _post_json(auth_client, "/habits/add", {
            "name": "Invalid freq",
            "frequency_type": "whenever",
        })
        assert res.status_code == 201
        assert res.get_json()["frequency_type"] == "daily"


class TestToggleHabit:
    def test_toggle_creates_completion(self, auth_client, test_user, db):
        habit = Habit(
            name="Meditate",
            frequency_type="daily",
            color="#5b6ef5",
            icon="fa-solid fa-star",
            user_id=test_user.id,
        )
        db.session.add(habit)
        db.session.commit()

        today = date.today().isoformat()
        res = _post_json(auth_client, f"/habits/{habit.id}/toggle", {"date": today})
        assert res.status_code == 200
        assert res.get_json()["done"] is True

        completion = HabitCompletion.query.filter_by(
            habit_id=habit.id, date=date.today()
        ).first()
        assert completion is not None

    def test_toggle_twice_removes_completion(self, auth_client, test_user, db):
        habit = Habit(
            name="Read",
            frequency_type="daily",
            color="#22c55e",
            icon="fa-solid fa-book",
            user_id=test_user.id,
        )
        db.session.add(habit)
        db.session.commit()

        today = date.today().isoformat()
        _post_json(auth_client, f"/habits/{habit.id}/toggle", {"date": today})
        res = _post_json(auth_client, f"/habits/{habit.id}/toggle", {"date": today})

        assert res.get_json()["done"] is False
        assert HabitCompletion.query.filter_by(
            habit_id=habit.id, date=date.today()
        ).count() == 0


class TestDeleteHabit:
    def test_delete_habit_removes_row(self, auth_client, test_user, db):
        habit = Habit(
            name="Delete me",
            frequency_type="daily",
            color="#ef4444",
            icon="fa-solid fa-trash",
            user_id=test_user.id,
        )
        db.session.add(habit)
        db.session.commit()
        habit_id = habit.id

        res = _post_json(auth_client, f"/habits/{habit_id}/delete", {})
        assert res.status_code == 200
        assert Habit.query.get(habit_id) is None

    def test_delete_other_users_habit_forbidden(self, auth_client, db):
        from models import User
        from werkzeug.security import generate_password_hash

        other = User(
            username="habother", email="habother@example.com",
            password=generate_password_hash("pw123"),
        )
        db.session.add(other)
        db.session.commit()

        habit = Habit(
            name="Not mine",
            frequency_type="daily",
            color="#5b6ef5",
            icon="fa-solid fa-star",
            user_id=other.id,
        )
        db.session.add(habit)
        db.session.commit()

        res = _post_json(auth_client, f"/habits/{habit.id}/delete", {})
        assert res.status_code == 403
