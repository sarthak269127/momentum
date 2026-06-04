"""
tests/test_notes.py — Tests for note creation, autosave, reminder sync, and deletion.
"""

import json

import pytest

from models import Note, Task


def _post_json(client, url, data):
    return client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
    )


class TestNotesList:
    def test_notes_page_requires_login(self, client):
        res = client.get("/notes/", follow_redirects=True)
        assert b"Sign in" in res.data

    def test_notes_page_renders(self, auth_client):
        res = auth_client.get("/notes/")
        assert res.status_code == 200


class TestCreateNote:
    def test_create_note_returns_201(self, auth_client):
        res = _post_json(auth_client, "/notes/create", {})
        assert res.status_code == 201
        body = res.get_json()
        assert "id" in body

    def test_created_note_is_in_database(self, auth_client, test_user, db):
        res = _post_json(auth_client, "/notes/create", {"title": "My note"})
        note_id = res.get_json()["id"]
        note = Note.query.get(note_id)
        assert note is not None
        assert note.user_id == test_user.id


class TestSaveNote:
    def test_save_updates_title_and_content(self, auth_client, test_user, db):
        note = Note(title="Old", content="Old content", user_id=test_user.id)
        db.session.add(note)
        db.session.commit()

        res = _post_json(auth_client, f"/notes/{note.id}/save", {
            "title": "New Title",
            "content": "New content",
        })
        assert res.status_code == 200
        updated = Note.query.get(note.id)
        assert updated.title == "New Title"
        assert updated.content == "New content"

    def test_save_with_reminder_creates_task(self, auth_client, test_user, db):
        note = Note(title="Remind me", content="", user_id=test_user.id)
        db.session.add(note)
        db.session.commit()

        res = _post_json(auth_client, f"/notes/{note.id}/save", {
            "title": "Remind me",
            "content": "details",
            "has_reminder": True,
            "reminder_datetime": "2030-01-01T09:00",
        })
        assert res.status_code == 200

        updated = Note.query.get(note.id)
        assert updated.has_reminder is True
        assert updated.reminder_task_id is not None
        linked_task = Task.query.get(updated.reminder_task_id)
        assert linked_task is not None
        assert linked_task.is_note_reminder is True

    def test_save_turning_off_reminder_clears_flag(self, auth_client, test_user, db):
        note = Note(
            title="Has reminder",
            content="",
            has_reminder=True,
            user_id=test_user.id,
        )
        db.session.add(note)
        db.session.commit()

        res = _post_json(auth_client, f"/notes/{note.id}/save", {
            "title": "Has reminder",
            "content": "",
            "has_reminder": False,
        })
        assert res.status_code == 200
        updated = Note.query.get(note.id)
        assert updated.has_reminder is False

    def test_save_other_users_note_forbidden(self, auth_client, db):
        from models import User
        from werkzeug.security import generate_password_hash

        other = User(
            username="oth2", email="oth2@example.com",
            password=generate_password_hash("pw123"),
        )
        db.session.add(other)
        db.session.commit()

        note = Note(title="Not yours", content="", user_id=other.id)
        db.session.add(note)
        db.session.commit()

        res = _post_json(auth_client, f"/notes/{note.id}/save", {"title": "Hack"})
        assert res.status_code == 403


class TestDeleteNote:
    def test_delete_note_removes_row(self, auth_client, test_user, db):
        note = Note(title="Bye", content="", user_id=test_user.id)
        db.session.add(note)
        db.session.commit()
        note_id = note.id

        res = _post_json(auth_client, f"/notes/{note_id}/delete", {})
        assert res.status_code == 200
        assert Note.query.get(note_id) is None

    def test_delete_note_with_task_removes_both(self, auth_client, test_user, db):
        from datetime import date
        note = Note(title="With task", content="", user_id=test_user.id)
        db.session.add(note)
        db.session.flush()

        task = Task(
            title="Linked task",
            task_date=date.today(),
            priority="medium",
            is_note_reminder=True,
            source_note_id=note.id,
            user_id=test_user.id,
        )
        db.session.add(task)
        db.session.flush()
        note.reminder_task_id = task.id
        db.session.commit()

        note_id = note.id
        task_id = task.id

        res = _post_json(auth_client, f"/notes/{note_id}/delete", {"delete_task": True})
        assert res.status_code == 200
        assert Note.query.get(note_id) is None
        assert Task.query.get(task_id) is None
