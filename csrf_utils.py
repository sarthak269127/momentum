"""
csrf_utils.py — Lightweight, dependency-free CSRF protection.

Why not flask-wtf?
  flask-wtf is excellent for form-based flows, but Momentum's frontend
  makes JSON POST requests from JavaScript.  This module provides the
  same protection (session-bound token, HMAC comparison) without
  requiring WTForms on every route.

How it works:
  1. A random 48-character hex token is generated once per session and
     stored in the server-side session under the key '_csrf_token'.
  2. Every HTML page includes the token in a <meta> tag and hidden form
     fields via the csrf_token() template helper.
  3. On every state-mutating request (POST/PUT/DELETE/PATCH) the
     csrf_protect decorator reads the token the client sent back
     (from the X-CSRFToken header for AJAX, or a form field) and
     compares it with the session token using hmac.compare_digest()
     to prevent timing-based attacks.
  4. A mismatch returns HTTP 403 Forbidden.
"""

import hmac
import os
from functools import wraps

from flask import abort, request, session


# ─────────────────────────────────────────────────────────────────────────────
# Token generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_csrf() -> str:
    """
    Return the CSRF token for the current session, creating it if absent.

    Called as a Jinja2 context function: {{ csrf_token() }}.
    The token is stored in Flask's signed session cookie, so it cannot
    be read or forged by a third-party site.
    """
    if "_csrf_token" not in session:
        session["_csrf_token"] = os.urandom(24).hex()
    return session["_csrf_token"]


# ─────────────────────────────────────────────────────────────────────────────
# Token extraction
# ─────────────────────────────────────────────────────────────────────────────

def _get_request_token() -> str:
    """
    Extract the CSRF token from wherever the client may have sent it.

    Priority order:
      1. X-CSRFToken header  — used by JavaScript fetch() calls
      2. csrf_token form field — used by plain HTML forms
      3. JSON body field       — used when Content-Type is application/json
    """
    # 1. Custom header (preferred for AJAX)
    token = request.headers.get("X-CSRFToken", "")
    if token:
        return token

    # 2. Form field (HTML form submissions)
    token = request.form.get("csrf_token", "")
    if token:
        return token

    # 3. JSON body (API requests that include it explicitly)
    if request.is_json:
        body = request.get_json(silent=True) or {}
        token = body.get("csrf_token", "")
        if token:
            return token

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Decorator
# ─────────────────────────────────────────────────────────────────────────────

def csrf_protect(f):
    """
    Route decorator that rejects state-mutating requests with an invalid CSRF token.

    Applies only to POST, PUT, DELETE, and PATCH.  GET and HEAD are
    safe methods and do not require protection.

    Usage:
        @app.route('/thing/delete', methods=['POST'])
        @login_required
        @csrf_protect
        def delete_thing():
            ...
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            token_sent = _get_request_token()
            token_expected = session.get("_csrf_token", "")

            # All three conditions must hold: both tokens present AND equal.
            # compare_digest prevents timing attacks.
            if (
                not token_expected
                or not token_sent
                or not hmac.compare_digest(token_expected, token_sent)
            ):
                abort(403)

        return f(*args, **kwargs)

    return decorated
