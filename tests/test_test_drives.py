from datetime import datetime, timedelta


def test_buyer_can_request_test_drive(logged_in_client, user_factory, car_factory):
    client, _buyer = logged_in_client
    seller = user_factory(email="seller-td@example.com")
    car = car_factory(owner=seller)

    when = (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    response = client.post(
        f"/test-drives/new/{car.id}",
        data={
            "requested_at": when,
            "duration_minutes": "30",
            "location": "DHA Phase 5",
            "message": "Looking forward to it.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    from models import TestDrive
    assert TestDrive.query.count() == 1
    drive = TestDrive.query.first()
    assert drive.status == TestDrive.STATUS_REQUESTED


def test_seller_can_confirm_test_drive(client, user_factory, car_factory):
    seller = user_factory(email="seller-td2@example.com")
    buyer = user_factory(email="buyer-td2@example.com")
    car = car_factory(owner=seller)

    when = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
    client.post("/login", data={"email": buyer.email, "password": "testpass123"}, follow_redirects=True)
    client.post(f"/test-drives/new/{car.id}", data={
        "requested_at": when, "duration_minutes": "30",
    }, follow_redirects=True)

    from models import TestDrive
    drive = TestDrive.query.first()

    client.get("/logout")
    client.post("/login", data={"email": seller.email, "password": "testpass123"}, follow_redirects=True)
    response = client.post(
        f"/test-drives/{drive.id}/confirm",
        data={"seller_response": "See you then"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    from extensions import db
    db.session.refresh(drive)
    assert drive.status == TestDrive.STATUS_CONFIRMED


def test_past_date_is_rejected(logged_in_client, user_factory, car_factory):
    client, _buyer = logged_in_client
    seller = user_factory(email="seller-td3@example.com")
    car = car_factory(owner=seller)

    when = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    response = client.post(
        f"/test-drives/new/{car.id}",
        data={"requested_at": when, "duration_minutes": "30"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    from models import TestDrive
    assert TestDrive.query.count() == 0
