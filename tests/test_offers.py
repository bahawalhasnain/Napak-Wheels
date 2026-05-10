def test_buyer_can_make_offer(logged_in_client, user_factory, car_factory, url_for_with_app):
    client, _buyer = logged_in_client
    seller = user_factory(email="seller-off@example.com")
    car = car_factory(owner=seller)

    response = client.post(
        url_for_with_app("offers.new", car_id=car.id),
        data={"amount": "3000000", "note": "best I can do"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    from models import Offer
    assert Offer.query.count() == 1
    offer = Offer.query.first()
    assert offer.amount == 3000000.0
    assert offer.status == Offer.STATUS_PENDING


def test_seller_can_accept_offer_and_listing_becomes_sold(
    client, user_factory, car_factory, url_for_with_app,
):
    seller = user_factory(email="acc-seller@example.com")
    buyer = user_factory(email="acc-buyer@example.com")
    car = car_factory(owner=seller)

    client.post("/login", data={"email": buyer.email, "password": "testpass123"}, follow_redirects=True)
    client.post(url_for_with_app("offers.new", car_id=car.id), data={"amount": "3100000"}, follow_redirects=True)

    from models import Offer
    offer = Offer.query.first()

    client.get("/logout")
    client.post("/login", data={"email": seller.email, "password": "testpass123"}, follow_redirects=True)

    response = client.post(url_for_with_app("offers.accept", offer_id=offer.id), follow_redirects=True)
    assert response.status_code == 200

    from extensions import db
    from models import Car
    refreshed = db.session.get(Car, car.id)
    db.session.refresh(offer)
    assert offer.status == Offer.STATUS_ACCEPTED
    assert refreshed.is_sold is True


def test_counter_offer_creates_chain(client, user_factory, car_factory, url_for_with_app):
    seller = user_factory(email="cnt-seller@example.com")
    buyer = user_factory(email="cnt-buyer@example.com")
    car = car_factory(owner=seller)

    client.post("/login", data={"email": buyer.email, "password": "testpass123"}, follow_redirects=True)
    client.post(url_for_with_app("offers.new", car_id=car.id), data={"amount": "2900000"}, follow_redirects=True)

    from models import Offer
    parent = Offer.query.first()

    client.get("/logout")
    client.post("/login", data={"email": seller.email, "password": "testpass123"}, follow_redirects=True)

    client.post(
        url_for_with_app("offers.counter", offer_id=parent.id),
        data={"amount": "3300000", "note": "meeting in middle"},
        follow_redirects=True,
    )

    from extensions import db
    db.session.expire_all()
    parent = Offer.query.get(parent.id)
    assert parent.status == Offer.STATUS_COUNTERED
    assert Offer.query.count() == 2
    counter = Offer.query.filter(Offer.parent_offer_id == parent.id).first()
    assert counter is not None
    assert counter.amount == 3300000.0
    assert counter.proposed_by == Offer.PROPOSED_SELLER
