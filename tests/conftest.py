"""Pytest fixtures for the Napak Wheels test suite."""

from __future__ import annotations

import os
import shutil

import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture(scope="session")
def app():
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "1"

    from app import create_app
    from config import TestConfig

    test_app = create_app(TestConfig)

    upload_dir = test_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)

    yield test_app

    if os.path.isdir(upload_dir):
        shutil.rmtree(upload_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_database(app):
    from extensions import db

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user_factory(app):
    def _make(email="user@example.com", password="testpass123", full_name="Test User", is_admin=False):
        from extensions import db
        from models import User

        user = User(
            full_name=full_name,
            email=email.lower(),
            phone="0300-0000000",
            location="Lahore",
            password_hash=generate_password_hash(password),
            is_admin=is_admin,
        )
        db.session.add(user)
        db.session.commit()
        return user

    return _make


@pytest.fixture
def car_factory(app):
    def _make(owner=None, **overrides):
        from extensions import db
        from models import Car

        defaults = {
            "make": "Honda", "model": "Civic", "year": 2018,
            "price": 3500000.0, "mileage": 50000, "color": "White",
            "fuel_type": "Gasoline", "transmission": "Automatic",
            "engine_size": "1.8", "description": "Well maintained.",
            "seller_name": owner.full_name if owner else "Seller",
            "seller_phone": "0300-1111111",
            "seller_email": owner.email if owner else "seller@example.com",
            "location": "Lahore",
            "user_id": owner.id if owner else None,
        }
        defaults.update(overrides)
        car = Car(**defaults)
        db.session.add(car)
        db.session.commit()
        return car

    return _make


def _login(client, email, password="testpass123"):
    resp = client.post("/login", data={"email": email, "password": password}, follow_redirects=True)
    assert resp.status_code == 200
    return resp


@pytest.fixture
def logged_in_client(client, user_factory):
    user = user_factory()
    _login(client, user.email)
    return client, user


@pytest.fixture
def logged_in_admin(client, user_factory):
    admin = user_factory(email="admin@example.com", is_admin=True)
    _login(client, admin.email)
    return client, admin
