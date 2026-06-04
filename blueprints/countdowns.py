"""
blueprints/countdowns.py — Countdown event routes.

Countdowns display live time remaining to a future event.  The browser
does all the tick rendering — the backend just stores and serves records.

_parse_target handles multiple date/datetime string formats to be
tolerant of browser datetime-local input variations.
"""

import logging
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from csrf_utils import csrf_protect
from extensions import db
from models import Countdown

logger = logging.getLogger(__name__)

countdowns_bp = Blueprint("countdown", __name__, url_prefix="/countdown")

# Hard cap on emoji field length to prevent unexpected unicode sequences
MAX_EMOJI_LEN = 8


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_countdown_or_403(cd_id: int) -> Countdown:
    """Return Countdown if owned by current_user, else raise 404/403."""
    cd = Countdown.query.get_or_404(cd_id)
    if cd.user_id != current_user.id:
        abort(403)
    return cd


def _parse_target_date(raw) -> datetime | None:
    """
    Parse a target date/datetime from a request payload.

    Accepts both date-only ('YYYY-MM-DD') and datetime ('YYYY-MM-DDTHH:MM')
    strings to tolerate different browser input types.
    Returns a datetime or None if parsing fails.
    """
    if not raw:
        return None

    raw = str(raw).strip()

    # Try formats from most to least specific
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:19], fmt)
        except ValueError:
            continue

    # Final fallback: fromisoformat (handles timezone-aware strings)
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@countdowns_bp.route("/")
@login_required
def countdown():
    """Countdown list page — ordered by target date ascending."""
    countdowns = (
        Countdown.query.filter_by(user_id=current_user.id)
        .order_by(Countdown.target_date)
        .all()
    )
    return render_template(
        "main/countdown.html", active="countdown", countdowns=countdowns
    )


@countdowns_bp.route("/add", methods=["POST"])
@login_required
@csrf_protect
def add_countdown():
    """
    Create a new countdown event.

    Expects JSON: { title, target_date, emoji? }
    Returns the created countdown as JSON with HTTP 201.
    """
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()

    if not title:
        return jsonify({"error": "Title is required."}), 400
    if len(title) > 200:
        return jsonify({"error": "Title must be 200 characters or fewer."}), 400

    target = _parse_target_date(data.get("target_date"))
    if not target:
        return jsonify({"error": "A valid target date is required."}), 400

    emoji = (data.get("emoji") or "🎯").strip()[:MAX_EMOJI_LEN]

    cd = Countdown(
        title=title,
        target_date=target,
        emoji=emoji,
        user_id=current_user.id,
    )
    db.session.add(cd)
    db.session.commit()
    logger.info("Countdown created: id=%d user=%d title=%r", cd.id, current_user.id, cd.title)
    return jsonify(cd.to_dict()), 201


@countdowns_bp.route("/<int:cd_id>/edit", methods=["POST"])
@login_required
@csrf_protect
def edit_countdown(cd_id: int):
    """
    Update a countdown's title, emoji, and/or target date.

    Only fields present in the JSON body are updated (partial update).
    """
    cd = _get_countdown_or_403(cd_id)
    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = data["title"].strip()
        if title and len(title) <= 200:
            cd.title = title

    if "emoji" in data:
        cd.emoji = (data["emoji"] or "🎯").strip()[:MAX_EMOJI_LEN]

    if "target_date" in data:
        target = _parse_target_date(data["target_date"])
        if target:
            cd.target_date = target

    db.session.commit()
    logger.debug("Countdown updated: id=%d user=%d", cd_id, current_user.id)
    return jsonify(cd.to_dict())


@countdowns_bp.route("/<int:cd_id>/delete", methods=["POST"])
@login_required
@csrf_protect
def delete_countdown(cd_id: int):
    """Delete a countdown event. Returns { ok: true }."""
    cd = _get_countdown_or_403(cd_id)
    db.session.delete(cd)
    db.session.commit()
    logger.info("Countdown deleted: id=%d user=%d", cd_id, current_user.id)
    return jsonify({"ok": True})
