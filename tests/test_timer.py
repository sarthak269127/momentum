"""
tests/test_timer.py — Tests for focus session save and stats endpoints.
"""

import json
from datetime import date, datetime

import pytest

from models import FocusSession


def _post_json(client, url, data):
    return client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
    )


class TestTimerPage:
    def test_timer_page_requires_login(self, client):
        res = client.get("/timer/", follow_redirects=True)
        assert b"Sign in" in res.data

    def test_timer_page_renders(self, auth_client):
        res = auth_client.get("/timer/")
        assert res.status_code == 200
        assert b"Focus Timer" in res.data


class TestSaveSession:
    def test_save_valid_timer_session(self, auth_client, test_user, db):
        res = _post_json(auth_client, "/timer/save", {
            "duration": 1500,  # 25 minutes
            "mode": "timer",
            "completed": True,
        })
        assert res.status_code == 201
        body = res.get_json()
        assert body["duration"] == 1500
        assert body["mode"] == "timer"
        assert body["completed"] is True

    def test_save_stopwatch_session(self, auth_client, test_user, db):
        res = _post_json(auth_client, "/timer/save", {
            "duration": 600,
            "mode": "stopwatch",
            "completed": False,
        })
        assert res.status_code == 201
        assert res.get_json()["mode"] == "stopwatch"

    def test_save_duration_too_short_rejected(self, auth_client):
        res = _post_json(auth_client, "/timer/save", {
            "duration": 5,
            "mode": "timer",
            "completed": True,
        })
        assert res.status_code == 400

    def test_save_invalid_duration_rejected(self, auth_client):
        res = _post_json(auth_client, "/timer/save", {
            "duration": "not-a-number",
            "mode": "timer",
            "completed": True,
        })
        assert res.status_code == 400

    def test_save_duration_capped_at_24h(self, auth_client, test_user, db):
        res = _post_json(auth_client, "/timer/save", {
            "duration": 999_999,  # Way over 24 h
            "mode": "timer",
            "completed": True,
        })
        assert res.status_code == 201
        assert res.get_json()["duration"] == 86_400  # Capped at 24 h

    def test_save_invalid_mode_defaults_to_timer(self, auth_client, test_user, db):
        res = _post_json(auth_client, "/timer/save", {
            "duration": 300,
            "mode": "invalid_mode",
            "completed": True,
        })
        assert res.status_code == 201
        assert res.get_json()["mode"] == "timer"

    def test_save_requires_login(self, client):
        res = _post_json(client, "/timer/save", {"duration": 300})
        assert res.status_code in (302, 401)


class TestApiStats:
    def test_stats_returns_expected_shape(self, auth_client):
        res = auth_client.get("/timer/api/stats")
        assert res.status_code == 200
        body = res.get_json()
        assert "today_seconds" in body
        assert "today_minutes" in body
        assert "sessions_today" in body

    def test_stats_counts_todays_sessions(self, auth_client, test_user, db):
        session = FocusSession(
            duration=900,
            mode="timer",
            completed=True,
            user_id=test_user.id,
            started_at=datetime.combine(date.today(), datetime.min.time()),
        )
        db.session.add(session)
        db.session.commit()

        res = auth_client.get("/timer/api/stats")
        body = res.get_json()
        assert body["today_seconds"] >= 900
        assert body["sessions_today"] >= 1
