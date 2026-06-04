"""
config.py — Application configuration hierarchy.

Three config classes are provided:
  - DevelopmentConfig  (FLASK_ENV=development)
  - ProductionConfig   (FLASK_ENV=production)
  - TestingConfig      (FLASK_ENV=testing)

All sensitive or deployment-specific values are read from environment
variables via python-dotenv.  No secrets should ever be hardcoded here.

Usage in create_app():
    from config import config_by_name
    app.config.from_object(config_by_name[env_name])
"""

import os
from dotenv import load_dotenv

# Load .env file into os.environ before anything reads from it.
load_dotenv()


class Config:
    """
    Base configuration shared across all environments.

    Every setting that is identical in dev, prod, and test lives here.
    Subclasses only override what differs.
    """

    # ── Core ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "fallback-dev-secret-CHANGE-ME")

    # ── Database ──────────────────────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "sqlite:///users.db")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    # Enable query recording in debug mode (overridden per-env)
    SQLALCHEMY_ECHO: bool = False

    # ── Mail ──────────────────────────────────────────────────────────────────
    MAIL_SERVER: str = os.environ.get("MAIL_SERVER", "smtp.zoho.in")
    MAIL_PORT: int = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS: bool = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME: str = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD: str = os.environ.get("MAIL_PASSWORD", "")

    # ── Security ──────────────────────────────────────────────────────────────
    # Separate salt for password-reset tokens; avoids cross-purpose token reuse.
    SECURITY_PASSWORD_SALT: str = os.environ.get(
        "SECURITY_PASSWORD_SALT", "fallback-salt-CHANGE-ME"
    )

    # Password-reset token expiry in seconds (10 minutes).
    PASSWORD_RESET_TOKEN_MAX_AGE: int = 600

    # Session cookie hardening
    SESSION_COOKIE_HTTPONLY: bool = (
        os.environ.get("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
    )
    SESSION_COOKIE_SAMESITE: str = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")

    # ── Validation constants ──────────────────────────────────────────────────
    # Centralise business-rule limits so route handlers never use magic numbers.
    MAX_TITLE_LEN: int = 200
    MAX_DESCRIPTION_LEN: int = 1000
    MAX_HABIT_NAME_LEN: int = 100
    MAX_EMOJI_LEN: int = 8
    MIN_PASSWORD_LEN: int = 6
    MIN_USERNAME_LEN: int = 2
    MIN_SESSION_DURATION_SECS: int = 10
    MAX_SESSION_DURATION_SECS: int = 86_400  # 24 h cap
    HEATMAP_DAYS: int = 30
    WEEKLY_CHART_DAYS: int = 7
    DASHBOARD_UPCOMING_DAYS: int = 7
    DASHBOARD_UPCOMING_LIMIT: int = 5
    DASHBOARD_COUNTDOWN_LIMIT: int = 3


class DevelopmentConfig(Config):
    """
    Development overrides.

    - DEBUG on so Flask auto-reloads and shows detailed errors.
    - SQLAlchemy echo off by default (flip to True for SQL debugging).
    - Session cookie *not* Secure so localhost HTTP works.
    """

    DEBUG: bool = True
    TESTING: bool = False
    SESSION_COOKIE_SECURE: bool = False


class ProductionConfig(Config):
    """
    Production overrides.

    - DEBUG and TESTING are explicitly off.
    - Session cookie marked Secure (requires HTTPS).
    - SQLAlchemy echo stays off to avoid leaking query data in logs.
    """

    DEBUG: bool = False
    TESTING: bool = False
    SESSION_COOKIE_SECURE: bool = (
        os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    )


class TestingConfig(Config):
    """
    Testing overrides.

    - Uses an in-memory SQLite database so tests never touch disk.
    - TESTING=True makes Flask propagate exceptions rather than returning 500 pages.
    - WTF_CSRF_ENABLED=False disables CSRF validation in test requests.
    """

    TESTING: bool = True
    DEBUG: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    WTF_CSRF_ENABLED: bool = False
    SESSION_COOKIE_SECURE: bool = False
    # Disable mail sending in tests
    MAIL_SUPPRESS_SEND: bool = True


# Map string names to config classes so create_app() can select by name.
config_by_name: dict = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
