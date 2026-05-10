"""Tests for view tracking, analytics page, CSV export, and Flask-Admin gating."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# View tracking
# ---------------------------------------------------------------------------


def test_anonymous_view_records_one_view_per_session_per_day(
    client, user_factory, car_factory, url_for_with_app,
):
    seller = user_factory(email="vt-seller@example.com")
    car = car_factory(owner=seller)
    car_url = url_for_with_app("main.car_detail", id=car.id)

    for _ in range(3):
        resp = client.get(car_url)
        assert resp.status_code == 200

    from extensions import db
    from models import Car, CarView

    refreshed = db.session.get(Car, car.id)
    assert refreshed.view_count == 1
    assert CarView.query.filter_by(car_id=car.id).count() == 1
    assert b"1 person viewed today" in resp.data


def test_distinct_anonymous_visitors_each_count(
    app, user_factory, car_factory, url_for_with_app,
):
    seller = user_factory(email="vt-seller2@example.com")
    car = car_factory(owner=seller)
    car_url = url_for_with_app("main.car_detail", id=car.id)

    client_a = app.test_client()
    client_b = app.test_client()

    client_a.get(car_url)
    client_b.get(car_url)

    from extensions import db
    from models import Car

    refreshed = db.session.get(Car, car.id)
    assert refreshed.view_count == 2


def test_owner_view_does_not_count(logged_in_client, car_factory, url_for_with_app):
    client, user = logged_in_client
    car = car_factory(owner=user)
    car_url = url_for_with_app("main.car_detail", id=car.id)

    client.get(car_url)
    client.get(car_url)

    from extensions import db
    from models import Car, CarView

    refreshed = db.session.get(Car, car.id)
    assert refreshed.view_count == 0
    assert CarView.query.filter_by(car_id=car.id).count() == 0


def test_admin_view_does_not_count(
    logged_in_admin, user_factory, car_factory, url_for_with_app,
):
    client, _admin = logged_in_admin
    seller = user_factory(email="vt-seller3@example.com")
    car = car_factory(owner=seller)

    client.get(url_for_with_app("main.car_detail", id=car.id))

    from extensions import db
    from models import Car

    refreshed = db.session.get(Car, car.id)
    assert refreshed.view_count == 0


def test_authenticated_buyer_view_dedupes_per_day(
    client, user_factory, car_factory, url_for_with_app,
):
    seller = user_factory(email="vt-seller4@example.com")
    buyer = user_factory(email="vt-buyer@example.com")
    car = car_factory(owner=seller)
    car_url = url_for_with_app("main.car_detail", id=car.id)

    client.post("/login", data={"email": buyer.email, "password": "testpass123"}, follow_redirects=True)

    client.get(car_url)
    client.get(car_url)

    from extensions import db
    from models import Car, CarView

    refreshed = db.session.get(Car, car.id)
    assert refreshed.view_count == 1
    assert CarView.query.filter_by(car_id=car.id, user_id=buyer.id).count() == 1


# ---------------------------------------------------------------------------
# Analytics page
# ---------------------------------------------------------------------------


def test_analytics_page_renders_for_admin(logged_in_admin, user_factory, car_factory):
    client, _admin = logged_in_admin
    seller = user_factory(email="anly-seller@example.com")
    car_factory(owner=seller, make="Honda", model="City")
    car_factory(owner=seller, make="Toyota", model="Corolla", is_sold=True)

    resp = client.get("/admin/analytics")
    assert resp.status_code == 200
    assert b"Analytics" in resp.data
    assert b"listingsChart" in resp.data
    assert b"makesChart" in resp.data
    assert b"conversionChart" in resp.data
    assert b"Honda" in resp.data


def test_analytics_blocked_for_non_admin(logged_in_client):
    client, _user = logged_in_client
    resp = client.get("/admin/analytics")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def test_csv_export_cars(logged_in_admin, user_factory, car_factory):
    client, _admin = logged_in_admin
    seller = user_factory(email="csv-seller@example.com")
    car_factory(owner=seller, make="Suzuki", model="Alto")

    resp = client.get("/admin/export/cars.csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "attachment" in resp.headers.get("Content-Disposition", "")
    body = resp.data.decode("utf-8")
    lines = body.strip().splitlines()
    assert lines[0].startswith("id,make,model,year,price")
    assert any("Suzuki,Alto" in line for line in lines[1:])


def test_csv_export_users(logged_in_admin, user_factory):
    client, admin = logged_in_admin
    user_factory(email="csv-user@example.com")

    resp = client.get("/admin/export/users.csv")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "csv-user@example.com" in body
    assert admin.email in body


def test_csv_export_blocked_for_non_admin(logged_in_client):
    client, _user = logged_in_client
    resp = client.get("/admin/export/cars.csv")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Flask-Admin DB panel
# ---------------------------------------------------------------------------


def test_flask_admin_panel_accessible_for_admin(logged_in_admin):
    client, _admin = logged_in_admin
    resp = client.get("/admin/db/", follow_redirects=False)
    assert resp.status_code == 200
    assert b"Database Admin" in resp.data


def test_flask_admin_panel_blocked_for_non_admin(logged_in_client):
    client, _user = logged_in_client
    resp = client.get("/admin/db/", follow_redirects=False)
    assert resp.status_code == 403


def test_flask_admin_panel_blocked_for_anonymous(client):
    resp = client.get("/admin/db/", follow_redirects=False)
    assert resp.status_code in (302, 401)
