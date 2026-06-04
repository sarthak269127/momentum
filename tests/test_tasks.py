"""
tests/test_tasks.py — Tests for task creation, editing, toggling, and deletion.
"""

import json
from datetime import date, timedelta

import pytest

from models import Task


def _post_json(client, url, data):
    """Helper: POST JSON with content-type header."""
    return client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
    )


class TestTasksPage:
    def test_tasks_page_requires_login(self, client):
        res = client.get("/tasks/", follow_redirects=True)
        assert b"Sign in" in res.data

    def test_tasks_page_renders_for_logged_in_user(self, auth_client):
        res = auth_client.get("/tasks/")
        assert res.status_code == 200
        assert b"Tasks" in res.data


class TestAddTask:
    def test_add_task_returns_201(self, auth_client):
        res = _post_json(auth_client, "/tasks/add", {
            "title": "Test task",
            "task_date": date.today().isoformat(),
        })
        assert res.status_code == 201
        body = res.get_json()
        assert body["title"] == "Test task"
        assert body["completed"] is False

    def test_add_task_defaults_to_medium_priority(self, auth_client):
        res = _post_json(auth_client, "/tasks/add", {
            "title": "Priority test",
            "task_date": date.today().isoformat(),
        })
        assert res.get_json()["priority"] == "medium"

    def test_add_task_respects_priority(self, auth_client):
        res = _post_json(auth_client, "/tasks/add", {
            "title": "High prio",
            "task_date": date.today().isoformat(),
            "priority": "high",
        })
        assert res.get_json()["priority"] == "high"

    def test_add_task_invalid_priority_falls_back_to_medium(self, auth_client):
        res = _post_json(auth_client, "/tasks/add", {
            "title": "Bad prio",
            "task_date": date.today().isoformat(),
            "priority": "extreme",
        })
        assert res.get_json()["priority"] == "medium"

    def test_add_task_empty_title_rejected(self, auth_client):
        res = _post_json(auth_client, "/tasks/add", {"title": ""})
        assert res.status_code == 400

    def test_add_task_long_title_rejected(self, auth_client):
        res = _post_json(auth_client, "/tasks/add", {
            "title": "x" * 201,
            "task_date": date.today().isoformat(),
        })
        assert res.status_code == 400

    def test_add_task_requires_login(self, client):
        res = _post_json(client, "/tasks/add", {"title": "Sneaky"})
        assert res.status_code in (302, 401)


class TestToggleTask:
    def test_toggle_task_flips_completed(self, auth_client, test_user, db):
        task = Task(
            title="Toggle me",
            task_date=date.today(),
            priority="medium",
            user_id=test_user.id,
        )
        db.session.add(task)
        db.session.commit()

        res = _post_json(auth_client, f"/tasks/toggle/{task.id}", {})
        assert res.status_code == 200
        assert res.get_json()["completed"] is True

        # Toggle back
        res2 = _post_json(auth_client, f"/tasks/toggle/{task.id}", {})
        assert res2.get_json()["completed"] is False

    def test_toggle_other_users_task_forbidden(self, auth_client, db):
        from models import User
        from werkzeug.security import generate_password_hash

        other = User(
            username="other", email="other@example.com",
            password=generate_password_hash("pw123"),
        )
        db.session.add(other)
        db.session.commit()

        task = Task(
            title="Not yours",
            task_date=date.today(),
            priority="low",
            user_id=other.id,
        )
        db.session.add(task)
        db.session.commit()

        res = _post_json(auth_client, f"/tasks/toggle/{task.id}", {})
        assert res.status_code == 403


class TestDeleteTask:
    def test_delete_task_removes_row(self, auth_client, test_user, db):
        task = Task(
            title="Delete me",
            task_date=date.today(),
            priority="low",
            user_id=test_user.id,
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id

        res = _post_json(auth_client, f"/tasks/delete/{task_id}", {})
        assert res.status_code == 200
        assert res.get_json()["ok"] is True
        assert Task.query.get(task_id) is None

    def test_delete_nonexistent_task_returns_404(self, auth_client):
        res = _post_json(auth_client, "/tasks/delete/99999", {})
        assert res.status_code == 404
