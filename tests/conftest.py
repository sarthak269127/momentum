"""
tests/conftest.py — Shared pytest fixtures.

Provides:
  app      — a Flask test application using an in-memory SQLite database
  client   — a test HTTP client attached to the app
  auth_client — a test client already logged in as a test user
  test_user   — a User row in the test database
"""

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db as _db
from models import User


@pytest.fixture(scope="session")
def app():
    """
    Create a Flask app configured for testing.

    Uses an in-memory SQLite database so tests never touch disk and always
    start with a clean slate.  CSRF protection is disabled in TestingConfig.
    """
    flask_app = create_app("testing")

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    """
    Provide a database session that is rolled back after each test.

    Using a transaction-level rollback means tests never commit to the
    database, keeping the state clean without recreating tables.
    """
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()

        # Override the session to use this connection so rollback works
        _db.session.bind = connection

        yield _db

        transaction.rollback()
        connection.close()
        _db.session.remove()


@pytest.fixture(scope="function")
def client(app):
    """Return a Flask test client."""
    return app.test_client()


@pytest.fixture(scope="function")
def test_user(db):
    """
    Create and return a User row for use in authenticated tests.

    The password is 'password123' — use this in login requests.
    """
    user = User(
        username="testuser",
        email="test@example.com",
        password=generate_password_hash("password123"),
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture(scope="function")
def auth_client(client, test_user):
    """
    Return a test client that is already logged in as test_user.

    Uses the login endpoint so flask-login's session is properly set.
    """
    client.post(
        "/login",
        data={"email": "test@example.com", "password": "password123"},
        follow_redirects=True,
    )
    return client
