"""
tests/test_auth.py — Tests for registration, login, logout, and password reset.
"""

import pytest
from werkzeug.security import check_password_hash

from extensions import db
from models import User


class TestRegister:
    def test_register_get_renders_form(self, client):
        res = client.get("/register")
        assert res.status_code == 200
        assert b"Create account" in res.data

    def test_register_success_creates_user(self, client, db):
        res = client.post(
            "/register",
            data={"username": "newuser", "email": "new@example.com", "password": "secure123"},
            follow_redirects=True,
        )
        assert res.status_code == 200
        user = User.query.filter_by(email="new@example.com").first()
        assert user is not None
        assert user.username == "newuser"

    def test_register_hashes_password(self, client, db):
        client.post(
            "/register",
            data={"username": "hashtest", "email": "hash@example.com", "password": "mypassword"},
            follow_redirects=True,
        )
        user = User.query.filter_by(email="hash@example.com").first()
        # Password must never be stored in plaintext
        assert user.password != "mypassword"
        assert check_password_hash(user.password, "mypassword")

    def test_register_duplicate_email_rejected(self, client, test_user):
        res = client.post(
            "/register",
            data={"username": "other", "email": "test@example.com", "password": "abc123"},
            follow_redirects=True,
        )
        assert b"Email already registered" in res.data

    def test_register_duplicate_username_rejected(self, client, test_user):
        res = client.post(
            "/register",
            data={"username": "testuser", "email": "unique@example.com", "password": "abc123"},
            follow_redirects=True,
        )
        assert b"Username already taken" in res.data

    def test_register_short_password_rejected(self, client):
        res = client.post(
            "/register",
            data={"username": "shortpw", "email": "short@example.com", "password": "ab"},
            follow_redirects=True,
        )
        assert b"6 characters" in res.data

    def test_register_short_username_rejected(self, client):
        res = client.post(
            "/register",
            data={"username": "x", "email": "xuser@example.com", "password": "abc123"},
            follow_redirects=True,
        )
        assert b"2 characters" in res.data


class TestLogin:
    def test_login_get_renders_form(self, client):
        res = client.get("/login")
        assert res.status_code == 200
        assert b"Sign in" in res.data

    def test_login_valid_credentials_redirects_to_dashboard(self, client, test_user):
        res = client.post(
            "/login",
            data={"email": "test@example.com", "password": "password123"},
            follow_redirects=True,
        )
        assert res.status_code == 200
        # Dashboard should be reachable after login
        assert b"Dashboard" in res.data or b"Momentum" in res.data

    def test_login_wrong_password_shows_error(self, client, test_user):
        res = client.post(
            "/login",
            data={"email": "test@example.com", "password": "wrongpassword"},
            follow_redirects=True,
        )
        assert b"Invalid email or password" in res.data

    def test_login_unknown_email_shows_error(self, client):
        res = client.post(
            "/login",
            data={"email": "nobody@example.com", "password": "password123"},
            follow_redirects=True,
        )
        assert b"Invalid email or password" in res.data

    def test_login_does_not_reveal_email_existence(self, client, test_user):
        """Both wrong-email and wrong-password return the same message."""
        res_bad_email = client.post(
            "/login",
            data={"email": "nobody@example.com", "password": "x"},
            follow_redirects=True,
        )
        res_bad_pw = client.post(
            "/login",
            data={"email": "test@example.com", "password": "wrong"},
            follow_redirects=True,
        )
        assert res_bad_email.data == res_bad_pw.data


class TestLogout:
    def test_logout_redirects_to_login(self, auth_client):
        res = auth_client.get("/logout", follow_redirects=True)
        assert res.status_code == 200
        assert b"Sign in" in res.data

    def test_logout_unauthenticated_redirects_to_login(self, client):
        res = client.get("/logout", follow_redirects=True)
        assert res.status_code == 200


class TestForgotPassword:
    def test_forgot_password_get_renders_form(self, client):
        res = client.get("/forgot-password")
        assert res.status_code == 200

    def test_forgot_password_always_shows_same_message(self, client, test_user):
        """Prevents user enumeration — same response whether email exists or not."""
        res_known = client.post(
            "/forgot-password",
            data={"email": "test@example.com"},
            follow_redirects=True,
        )
        res_unknown = client.post(
            "/forgot-password",
            data={"email": "nobody@example.com"},
            follow_redirects=True,
        )
        assert b"If that email is registered" in res_known.data
        assert b"If that email is registered" in res_unknown.data
