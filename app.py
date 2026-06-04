"""
app.py — Application factory for Momentum.

Using an application factory (create_app) allows:
  - Multiple app instances with different configurations (e.g. tests)
  - Deferred extension initialisation (extensions created without an app,
    then bound to it here)
  - Clean circular-import avoidance (blueprints import from extensions,
    not from app)

Usage:
    # Development / gunicorn
    from app import create_app
    app = create_app()

    # Tests
    from app import create_app
    from config import TestingConfig
    app = create_app("testing")
"""

import logging
import logging.handlers
import os
from pathlib import Path

from flask import Flask

from config import config_by_name
from csrf_utils import generate_csrf
from extensions import db, login_manager, mail


def create_app(config_name: str | None = None) -> Flask:
    """
    Create and configure a Flask application instance.

    Args:
        config_name: One of 'development', 'production', 'testing', or None
                     (defaults to FLASK_ENV env-var, falling back to 'development').

    Returns:
        A fully initialised Flask app.
    """
    app = Flask(__name__, instance_relative_config=True)

    # ── Select config ──────────────────────────────────────────────────────
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    config_class = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_class)

    # ── Logging ────────────────────────────────────────────────────────────
    _configure_logging(app)
    app.logger.info("Starting Momentum in %r mode", config_name)

    # ── Initialise extensions ──────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    # Redirect unauthenticated users to login; show an informational message
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "info"

    # ── Context processors ─────────────────────────────────────────────────
    @app.context_processor
    def inject_csrf():
        """Expose csrf_token() as a callable in every Jinja2 template."""
        return {"csrf_token": generate_csrf}

    # ── Register blueprints ────────────────────────────────────────────────
    _register_blueprints(app)

    # ── Register error handlers ────────────────────────────────────────────
    _register_error_handlers(app)

    # ── Create database tables ─────────────────────────────────────────────
    with app.app_context():
        db.create_all()

    return app


def _register_blueprints(app: Flask) -> None:
    """
    Import and register all application blueprints.

    Blueprints are imported inside this function (not at the module level)
    to avoid circular imports — blueprints import from extensions and models,
    which must be imported after db/login_manager are created.
    """
    from auth import auth_bp
    from blueprints.tasks import tasks_bp
    from blueprints.notes import notes_bp
    from blueprints.habits import habits_bp
    from blueprints.timer import timer_bp
    from blueprints.countdowns import countdowns_bp
    from blueprints.calendar import calendar_bp
    from blueprints.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(habits_bp)
    app.register_blueprint(timer_bp)
    app.register_blueprint(countdowns_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(dashboard_bp)


def _register_error_handlers(app: Flask) -> None:
    """
    Register centralised HTTP error handlers.

    These render plain JSON responses for API-style requests and simple
    flash-message redirects for browser requests, giving a consistent
    experience regardless of where an error originates.
    """
    from flask import jsonify, render_template, request

    @app.errorhandler(400)
    def bad_request(e):
        app.logger.warning("400 Bad Request: %s", request.url)
        if request.is_json:
            return jsonify({"error": "Bad request", "detail": str(e)}), 400
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(e):
        app.logger.warning("403 Forbidden: %s %s", request.method, request.url)
        if request.is_json:
            return jsonify({"error": "Forbidden"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if request.is_json:
            return jsonify({"error": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(e):
        # Roll back the database session so the next request gets a clean slate
        db.session.rollback()
        app.logger.exception("500 Internal Server Error: %s", request.url)
        if request.is_json:
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500


def _configure_logging(app: Flask) -> None:
    """
    Set up application-level logging with rotating file output.

    In development the default Flask logger (stderr) is sufficient.
    In production logs rotate daily, keeping 14 days of history.
    """
    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO

    # Ensure log directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Rotating file handler — 5 MB per file, keep 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "momentum.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Attach to root logger so all modules (services, blueprints) benefit
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers in production
    if not app.config.get("DEBUG"):
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("werkzeug").setLevel(logging.WARNING)


# ── Entry point ────────────────────────────────────────────────────────────────
# Allows: python app.py
# In production use: gunicorn "app:create_app()"
app = create_app()

if __name__ == "__main__":
    app.run()
