"""
services/email_service.py — Outbound email helpers.

Currently the only email sent is a password-reset link.  The service
layer is kept thin: rendering the HTML email body lives here, and the
actual SMTP delivery is delegated to flask-mail.

Callers should always wrap send_* functions in a try/except and never
surface SMTP errors to the end user — doing so would expose whether an
email address is registered (user enumeration).
"""

import logging

from flask import current_app, render_template_string
from flask_mail import Message

from extensions import mail

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Email body templates
# ─────────────────────────────────────────────────────────────────────────────

# Inline HTML string so no extra template file is needed.
_RESET_EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 20px;">
  <div style="max-width: 480px; margin: 0 auto; background: #ffffff;
              border-radius: 8px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">

    <div style="text-align: center; margin-bottom: 24px;">
      <div style="display: inline-block; background: #5b5cff; color: #fff;
                  width: 40px; height: 40px; border-radius: 8px; line-height: 40px;
                  font-weight: 700; font-size: 18px;">M</div>
      <h1 style="font-size: 20px; color: #1a1a2e; margin: 8px 0 0;">Momentum</h1>
    </div>

    <h2 style="font-size: 18px; color: #1a1a2e; margin: 0 0 12px;">Password Reset Request</h2>
    <p style="color: #555; margin: 0 0 24px; line-height: 1.6;">
      We received a request to reset the password for your Momentum account.
      Click the button below to set a new password.  This link expires in
      <strong>10 minutes</strong>.
    </p>

    <div style="text-align: center; margin: 24px 0;">
      <a href="{{ reset_link }}"
         style="display: inline-block; padding: 12px 28px;
                background: #5b5cff; color: #ffffff;
                text-decoration: none; border-radius: 6px;
                font-weight: 600; font-size: 15px;">
        Reset Password
      </a>
    </div>

    <p style="font-size: 12px; color: #999; margin: 24px 0 0; line-height: 1.5;">
      If you did not request a password reset, you can safely ignore this email.
      Your password will not change.
    </p>
  </div>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def send_password_reset_email(recipient_email: str, reset_link: str) -> bool:
    """
    Send a password-reset email containing a time-limited link.

    Args:
        recipient_email: The user's email address.
        reset_link:      The full HTTPS URL containing the signed token.

    Returns:
        True if the email was accepted by the SMTP server, False on any error.

    Callers must not reveal the return value to the end user — always
    show the same "check your inbox" message regardless of success.
    """
    try:
        html_body = render_template_string(_RESET_EMAIL_HTML, reset_link=reset_link)

        msg = Message(
            subject="Reset Your Momentum Password",
            sender=current_app.config["MAIL_USERNAME"],
            recipients=[recipient_email],
            html=html_body,
        )
        mail.send(msg)
        logger.info("Password reset email sent to %s", recipient_email)
        return True

    except Exception:
        # Log the full traceback for ops visibility but don't re-raise —
        # callers are expected to handle False silently.
        logger.exception("Failed to send password-reset email to %s", recipient_email)
        return False
