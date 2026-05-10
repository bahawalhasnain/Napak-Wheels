"""Celery configuration and background tasks.

Tasks default to ``task_always_eager=True`` when no broker URL is configured,
so the app works out of the box without Redis. Set ``CELERY_BROKER_URL`` (and
optionally ``CELERY_RESULT_BACKEND``) in ``.env`` to enable real async
processing, then run a worker with::

    celery -A tasks.celery worker --loglevel=info
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Iterable

from celery import Celery


logger = logging.getLogger(__name__)


def _make_celery() -> Celery:
    broker = os.environ.get("CELERY_BROKER_URL") or "memory://"
    backend = os.environ.get("CELERY_RESULT_BACKEND") or "cache+memory://"
    eager = (
        os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() in {"1", "true", "yes"}
        or not os.environ.get("CELERY_BROKER_URL")
    )

    app = Celery("napak_wheels", broker=broker, backend=backend)
    app.conf.update(
        task_always_eager=eager,
        task_eager_propagates=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )
    return app


celery = _make_celery()


def init_celery(flask_app):
    celery.conf.update(
        broker_url=flask_app.config.get("CELERY_BROKER_URL") or celery.conf.broker_url,
        result_backend=flask_app.config.get("CELERY_RESULT_BACKEND") or celery.conf.result_backend,
        task_always_eager=flask_app.config.get("CELERY_TASK_ALWAYS_EAGER", celery.conf.task_always_eager),
    )

    class FlaskTask(celery.Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return super().__call__(*args, **kwargs)

    celery.Task = FlaskTask
    return celery


@celery.task(name="tasks.process_uploaded_image")
def process_uploaded_image(file_path: str, max_width: int = 800, max_height: int = 600) -> str:
    from PIL import Image

    try:
        with Image.open(file_path) as img:
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            img.save(file_path, optimize=True, quality=85)
    except Exception:
        logger.exception("Failed to process image at %s", file_path)
        raise
    return file_path


@celery.task(name="tasks.send_email_async")
def send_email_async(subject: str, body: str, recipients: Iterable[str], html: str | None = None):
    from email_utils import send_email

    send_email(subject=subject, body=body, recipients=list(recipients), html=html)


@celery.task(name="tasks.match_saved_searches_for_car")
def match_saved_searches_for_car(car_id: int) -> int:
    """Notify users with saved searches matching this newly posted car."""

    from extensions import db
    from flask import url_for
    from models import Car, Notification, SavedSearch
    from email_utils import send_email

    car = db.session.get(Car, car_id)
    if not car or car.is_sold or car.is_taken_down:
        return 0

    matched = 0
    saved = SavedSearch.query.filter_by(alerts_enabled=True).all()
    for ss in saved:
        if ss.user_id == car.user_id:
            continue
        if not ss.matches_car(car):
            continue
        if not ss.user:
            continue

        try:
            link = url_for("main.car_detail", id=car.id, _external=False)
        except Exception:
            from url_ids import encode_url_id

            link = "/car/" + encode_url_id("car", car.id)

        Notification.push(
            user_id=ss.user_id,
            title=f"New match for '{ss.name}'",
            body=f"{car.year} {car.make} {car.model} - {car.formatted_price} in {car.location}",
            link=link,
        )
        ss.last_notified_at = datetime.utcnow()

        send_email(
            subject=f"New car matches your saved search '{ss.name}'",
            body=(
                f"Hi {ss.user.full_name},\n\n"
                f"A new listing matches your saved search:\n"
                f"  {car.year} {car.make} {car.model}\n"
                f"  Price: {car.formatted_price}\n"
                f"  Location: {car.location}\n\n"
                f"View it here: {link}\n\n"
                f"You can manage alerts in your account."
            ),
            recipients=[ss.user.email],
        )
        matched += 1

    db.session.commit()
    return matched
