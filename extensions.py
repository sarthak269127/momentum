"""
extensions.py — Flask extension singletons.

Extensions are created here without an app object so they can be
imported anywhere before create_app() runs.  Each extension is
initialised with the real app inside create_app() via its init_app()
method (the application factory pattern).

Importing from this module:
    from extensions import db, login_manager, mail
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail

# Relational database ORM — used by all models.
db = SQLAlchemy()

# Manages user session state (login / logout / current_user).
login_manager = LoginManager()

# Email delivery — used only by the password-reset flow.
mail = Mail()
