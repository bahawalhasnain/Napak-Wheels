"""Tests for the profile + settings (account / security / notifications / danger)."""

from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def test_profile_page_requires_login(client):
    resp = client.get("/account/profile", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_page_renders_for_logged_in_user(logged_in_client, car_factory):
    client, user = logged_in_client
    car_factory(owner=user)

    resp = client.get("/account/profile")
    assert resp.status_code == 200
    assert user.full_name.encode() in resp.data
    assert b"Listings" in resp.data
    assert b"Favorites" in resp.data


# ---------------------------------------------------------------------------
# Settings - account
# ---------------------------------------------------------------------------


def test_settings_redirects_to_account(logged_in_client):
    client, _user = logged_in_client
    resp = client.get("/account/settings", follow_redirects=False)
    assert resp.status_code == 302
    assert "/account/settings/account" in resp.headers["Location"]


def test_update_profile_fields(logged_in_client):
    client, user = logged_in_client

    resp = client.post(
        "/account/settings/account",
        data={
            "full_name": "Updated Name",
            "email": user.email,
            "phone": "0301-9999999",
            "location": "Karachi",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    from extensions import db
    from models import User

    refreshed = db.session.get(User, user.id)
    assert refreshed.full_name == "Updated Name"
    assert refreshed.phone == "0301-9999999"
    assert refreshed.location == "Karachi"


def test_cannot_change_email_to_one_already_taken(logged_in_client, user_factory):
    client, user = logged_in_client
    other = user_factory(email="taken@example.com")

    resp = client.post(
        "/account/settings/account",
        data={
            "full_name": user.full_name,
            "email": other.email,
            "phone": user.phone or "",
            "location": user.location or "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"already in use" in resp.data

    from extensions import db
    from models import User
    refreshed = db.session.get(User, user.id)
    assert refreshed.email == "user@example.com"


# ---------------------------------------------------------------------------
# Settings - security (change password)
# ---------------------------------------------------------------------------


def test_change_password_happy_path(logged_in_client):
    client, user = logged_in_client

    resp = client.post(
        "/account/settings/security",
        data={
            "current_password": "testpass123",
            "new_password": "newpass4567",
            "confirm_password": "newpass4567",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    from extensions import db
    from models import User

    refreshed = db.session.get(User, user.id)
    assert check_password_hash(refreshed.password_hash, "newpass4567")
    assert not check_password_hash(refreshed.password_hash, "testpass123")


def test_change_password_rejects_wrong_current(logged_in_client):
    client, user = logged_in_client
    resp = client.post(
        "/account/settings/security",
        data={
            "current_password": "wrong-password",
            "new_password": "newpass4567",
            "confirm_password": "newpass4567",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"current password is incorrect" in resp.data

    from extensions import db
    from models import User
    refreshed = db.session.get(User, user.id)
    assert check_password_hash(refreshed.password_hash, "testpass123")


def test_change_password_rejects_mismatched_confirm(logged_in_client):
    client, _user = logged_in_client
    resp = client.post(
        "/account/settings/security",
        data={
            "current_password": "testpass123",
            "new_password": "newpass4567",
            "confirm_password": "different-pass",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Passwords must match" in resp.data


# ---------------------------------------------------------------------------
# Settings - notifications
# ---------------------------------------------------------------------------


def test_toggle_email_alerts_off(logged_in_client):
    client, user = logged_in_client
    assert user.email_alerts_enabled is True

    resp = client.post(
        "/account/settings/notifications",
        data={},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    from extensions import db
    from models import User
    refreshed = db.session.get(User, user.id)
    assert refreshed.email_alerts_enabled is False


def test_toggle_email_alerts_on(logged_in_client):
    client, user = logged_in_client

    from extensions import db
    user.email_alerts_enabled = False
    db.session.commit()

    resp = client.post(
        "/account/settings/notifications",
        data={"email_alerts_enabled": "y"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    from models import User
    refreshed = db.session.get(User, user.id)
    assert refreshed.email_alerts_enabled is True


def test_mark_all_notifications_read(logged_in_client):
    client, user = logged_in_client

    from extensions import db
    from models import Notification
    Notification.push(user_id=user.id, title="Test 1")
    Notification.push(user_id=user.id, title="Test 2")
    db.session.commit()

    assert user.unread_notification_count() == 2

    resp = client.post(
        "/account/settings/notifications/mark-all-read",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert user.unread_notification_count() == 0


# ---------------------------------------------------------------------------
# Settings - danger zone (deactivate)
# ---------------------------------------------------------------------------


def test_deactivate_account_takes_down_listings_and_logs_out(logged_in_client, car_factory):
    client, user = logged_in_client
    car_factory(owner=user)
    car_factory(owner=user)

    resp = client.post(
        "/account/settings/danger",
        data={
            "confirm_password": "testpass123",
            "confirm_text": "DELETE",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    from extensions import db
    from models import Car, User

    refreshed_user = db.session.get(User, user.id)
    assert refreshed_user is not None
    assert refreshed_user.email_alerts_enabled is False

    cars = Car.query.filter_by(user_id=user.id).all()
    assert len(cars) == 2
    assert all(c.is_taken_down for c in cars)

    # Logged out -> hitting a protected route bounces to /login
    resp_after = client.get("/account/profile", follow_redirects=False)
    assert resp_after.status_code == 302
    assert "/login" in resp_after.headers["Location"]


def test_deactivate_requires_correct_password(logged_in_client):
    client, _user = logged_in_client
    resp = client.post(
        "/account/settings/danger",
        data={
            "confirm_password": "wrong-password",
            "confirm_text": "DELETE",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Password is incorrect" in resp.data


def test_deactivate_requires_typed_confirmation(logged_in_client):
    client, _user = logged_in_client
    resp = client.post(
        "/account/settings/danger",
        data={
            "confirm_password": "testpass123",
            "confirm_text": "delete",  # lowercase, should be rejected
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"DELETE" in resp.data


# ---------------------------------------------------------------------------
# Navbar avatar smoke check
# ---------------------------------------------------------------------------


def test_navbar_renders_user_menu_when_logged_in(logged_in_client):
    client, user = logged_in_client
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"user-menu-btn" in resp.data
    assert b"user-avatar" in resp.data


def test_navbar_renders_login_signup_when_anonymous(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Sign up" in resp.data
    assert b"Login" in resp.data
