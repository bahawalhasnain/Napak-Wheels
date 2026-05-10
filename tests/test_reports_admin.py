def test_user_can_report_listing(logged_in_client, user_factory, car_factory):
    client, _user = logged_in_client
    seller = user_factory(email="seller-rep@example.com")
    car = car_factory(owner=seller)

    response = client.post(
        f"/report/{car.id}",
        data={"reason": "spam", "details": "Looks suspicious."},
        follow_redirects=True,
    )
    assert response.status_code == 200

    from models import Report
    assert Report.query.count() == 1
    r = Report.query.first()
    assert r.reason == "spam"
    assert r.status == Report.STATUS_OPEN


def test_user_cannot_report_own_listing(logged_in_client, car_factory):
    client, user = logged_in_client
    car = car_factory(owner=user)
    response = client.post(f"/report/{car.id}", data={"reason": "spam"})
    assert response.status_code == 403


def test_admin_can_take_down_listing(client, user_factory, car_factory):
    seller = user_factory(email="rep-seller@example.com")
    reporter = user_factory(email="rep-reporter@example.com")
    admin = user_factory(email="rep-admin@example.com", is_admin=True)
    car = car_factory(owner=seller)

    client.post("/login", data={"email": reporter.email, "password": "testpass123"}, follow_redirects=True)
    client.post(f"/report/{car.id}", data={"reason": "fraud"}, follow_redirects=True)

    from models import Report
    report = Report.query.first()

    client.get("/logout")
    client.post("/login", data={"email": admin.email, "password": "testpass123"}, follow_redirects=True)

    response = client.post(
        f"/admin/reports/{report.id}/takedown",
        data={"review_note": "removed"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    from extensions import db
    from models import Car
    refreshed = db.session.get(Car, car.id)
    assert refreshed.is_taken_down is True


def test_non_admin_cannot_access_admin(logged_in_client):
    client, _user = logged_in_client
    response = client.get("/admin/")
    assert response.status_code == 403


def test_admin_dashboard_accessible(logged_in_admin):
    client, _admin = logged_in_admin
    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"Admin Dashboard" in response.data
