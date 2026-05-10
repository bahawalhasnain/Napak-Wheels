"""Application factory for Napak Wheels."""

from __future__ import annotations

import logging
import os
from time import perf_counter

import click
from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix


load_dotenv(override=True)


def create_app(config_object: str | type | None = None) -> Flask:
    """Construct and configure the Flask application."""

    from config import Config
    from extensions import csrf, db, login_manager, migrate
    from tasks import init_celery

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    app = Flask(__name__)
    app.config.from_object(config_object or Config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.logger.setLevel(getattr(logging, app.config.get("LOG_LEVEL", "INFO"), logging.INFO))
    logging.getLogger("werkzeug").setLevel(app.logger.level)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    init_celery(app)

    @login_manager.unauthorized_handler
    def _on_unauthorized():
        if request.path.startswith("/api/"):
            return jsonify({"error": "authentication required"}), 401
        return redirect(url_for("main.login", next=request.path))

    app.logger.info(
        "Database URL loaded. Driver: %s",
        app.config["SQLALCHEMY_DATABASE_URI"].split(":")[0],
    )

    with app.app_context():
        import models  # noqa: F401  - register tables for migrations

        from url_ids import init_url_id_codec, register_url_id_converters

        init_url_id_codec(app)
        register_url_id_converters(app)

        from routes import bp as main_bp
        from api import api_bp
        from blueprints.messaging import messaging_bp
        from blueprints.offers import offers_bp
        from blueprints.test_drives import test_drives_bp
        from blueprints.saved_searches import saved_searches_bp
        from blueprints.reports import reports_bp
        from blueprints.notifications import notifications_bp
        from blueprints.admin import admin_bp
        from blueprints.account import account_bp

        for blueprint in (
            main_bp, api_bp, messaging_bp, offers_bp, test_drives_bp,
            saved_searches_bp, reports_bp, notifications_bp, admin_bp, account_bp,
        ):
            app.register_blueprint(blueprint)

        csrf.exempt(api_bp)

        _register_jinja_helpers(app)

        from admin_panel import init_admin_panel
        init_admin_panel(app)

        if app.config.get("TESTING"):
            db.create_all()

    _register_request_logging(app)
    _register_error_handlers(app)
    _register_cli(app)
    return app


_AVATAR_PALETTE = (
    "#1f6feb", "#7c3aed", "#db2777", "#0ea5e9", "#22c55e",
    "#f97316", "#ef4444", "#14b8a6", "#a855f7", "#eab308",
)


def _register_jinja_helpers(app: Flask) -> None:
    def avatar_color(seed: str) -> str:
        seed = (seed or "?").strip().lower()
        bucket = sum(ord(ch) for ch in seed) if seed else 0
        return _AVATAR_PALETTE[bucket % len(_AVATAR_PALETTE)]

    app.jinja_env.globals["avatar_color"] = avatar_color


def _register_request_logging(app: Flask) -> None:
    @app.before_request
    def _log_start():
        g.request_start_time = perf_counter()
        app.logger.info("Request started: %s %s", request.method, request.path)

    @app.after_request
    def _log_end(response):
        duration_ms = (perf_counter() - g.get("request_start_time", perf_counter())) * 1000
        app.logger.info(
            "Request completed: %s %s -> %s (%.2f ms)",
            request.method, request.path, response.status_code, duration_ms,
        )
        return response


def _register_error_handlers(app: Flask) -> None:
    from extensions import db

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal(_error):
        db.session.rollback()
        return render_template("500.html"), 500


def _register_cli(app: Flask) -> None:
    from extensions import db
    from models import User

    @app.cli.command("make-admin")
    @click.argument("email")
    def make_admin(email):
        """Grant admin privileges to a user by email."""

        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            click.echo(f"User not found: {email}")
            return
        user.is_admin = True
        db.session.commit()
        click.echo(f"{email} is now an admin.")

    @app.cli.command("revoke-admin")
    @click.argument("email")
    def revoke_admin(email):
        """Revoke admin privileges from a user by email."""

        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            click.echo(f"User not found: {email}")
            return
        user.is_admin = False
        db.session.commit()
        click.echo(f"{email} is no longer an admin.")


# Note: do not auto-instantiate at module import time. The Flask CLI auto-detects
# the ``create_app`` factory, ``main.py`` calls it explicitly, and tests inject
# their own config. Auto-creating here would boot a production-config app every
# time this module is imported (e.g. by pytest), which causes Celery to bind to
# the wrong Flask app and breaks ``db.session`` lookups in background tasks.
