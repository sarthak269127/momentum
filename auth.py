"""
auth.py — Authentication blueprint (register, login, logout, password reset).

Security considerations
───────────────────────
- Passwords are hashed with Werkzeug's generate_password_hash (pbkdf2:sha256).
- Password-reset tokens are signed+timestamped with itsdangerous; they
  expire after PASSWORD_RESET_TOKEN_MAX_AGE seconds (default 10 min).
- The forgot-password route always returns the same flash message
  whether or not the email exists, preventing user enumeration.
- CSRF tokens protect all POST routes via hidden form fields.
- After login, the 'next' redirect parameter is validated to prevent
  open redirect attacks (Flask's url_for ensures same-origin only when
  we use it, but raw 'next' values from query strings are not trusted
  automatically — we use url_parse to guard it).
"""

import logging

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash
from urllib.parse import urlparse

from extensions import db, login_manager
from models import User
from services.email_service import send_password_reset_email

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Login manager hook
# ─────────────────────────────────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """
    Reload the user object from the database given its ID stored in the session.

    Called by flask-login on every request that requires authentication.
    Returns None if the user no longer exists (e.g. account deleted).
    """
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_serializer() -> URLSafeTimedSerializer:
    """Return a token serializer bound to the app's SECRET_KEY."""
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _safe_next_url(next_url: str | None) -> str:
    """
    Return the 'next' redirect target only if it is a relative (same-origin) URL.

    An attacker could craft a link like /login?next=https://evil.com to
    redirect users off-site after login.  url_parse().netloc being empty
    ensures the URL has no host component, making it safe.
    """
    if not next_url:
        return url_for("routes.dashboard")
    # Block absolute URLs to prevent open redirects
    if urlparse(next_page).netloc:
        return url_for("routes.dashboard")
    return next_url


def _validate_registration(username: str, email: str, password: str) -> str | None:
    """
    Validate registration inputs.

    Returns an error message string on failure, or None if all inputs are valid.
    Checks length constraints and uniqueness in the database.
    """
    min_username = current_app.config["MIN_USERNAME_LEN"]
    min_password = current_app.config["MIN_PASSWORD_LEN"]

    if len(username) < min_username:
        return f"Username must be at least {min_username} characters."
    if len(password) < min_password:
        return f"Password must be at least {min_password} characters."
    if User.query.filter_by(email=email).first():
        return "Email already registered."
    if User.query.filter_by(username=username).first():
        return "Username already taken."
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Registration page.

    On GET: render the empty form.
    On POST: validate inputs, create the account, log the user in, and
             redirect to the dashboard.  On validation failure re-render
             the form with the entered values preserved and an error flash.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        error = _validate_registration(username, email, password)
        if error:
            flash(error, "error")
            return render_template("auth/register.html", username=username, email=email)

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        logger.info("New user registered: id=%d username=%r", user.id, user.username)
        flash("Welcome to Momentum!", "success")
        return redirect(url_for("routes.dashboard"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Login page.

    Accepts an optional 'next' query parameter to redirect to after a
    successful login.  The next URL is validated to prevent open redirects.
    """
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            logger.info("User logged in: id=%d", user.id)
            return redirect(_safe_next_url(request.args.get("next")))

        # Intentionally vague message — don't reveal whether the email exists
        flash("Invalid email or password.", "error")
        return render_template("auth/login.html")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """Log the current user out and redirect to the login page."""
    logger.info("User logged out: id=%d", getattr(login_user, "id", "?"))
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """
    Forgot-password page.

    Always shows the same response regardless of whether the email exists
    to prevent user-enumeration attacks.  A reset link is generated and
    emailed only when the account is found; SMTP errors are suppressed.
    """
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            token = _get_serializer().dumps(email, salt=current_app.config["SECURITY_PASSWORD_SALT"])
            reset_link = url_for("auth.reset_password", token=token, _external=True)
            # Swallow email errors — never reveal the result to the user
            send_password_reset_email(email, reset_link)

        # Always the same flash, whether user was found or not
        flash("If that email is registered, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """
    Password-reset page, guarded by a time-limited signed token.

    Token is verified with itsdangerous; an expired or tampered token
    is rejected with an error flash.  Valid token → allow the user to
    set a new password and log them in immediately.
    """
    max_age = current_app.config["PASSWORD_RESET_TOKEN_MAX_AGE"]
    salt = current_app.config["SECURITY_PASSWORD_SALT"]

    try:
        email = _get_serializer().loads(token, salt=salt, max_age=max_age)
    except SignatureExpired:
        flash("Reset link has expired. Please request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))
    except BadSignature:
        flash("Invalid or tampered reset link.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        new_password = request.form.get("password", "")
        min_len = current_app.config["MIN_PASSWORD_LEN"]

        if len(new_password) < min_len:
            flash(f"Password must be at least {min_len} characters.", "error")
            return render_template("auth/reset_password.html")

        user.password = generate_password_hash(new_password)
        db.session.commit()
        login_user(user, remember=True)
        logger.info("Password reset successful for user id=%d", user.id)
        flash("Password updated successfully.", "success")
        return redirect(url_for("routes.dashboard"))

    return render_template("auth/reset_password.html")
