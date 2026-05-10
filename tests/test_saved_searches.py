def test_create_saved_search(logged_in_client):
    client, _user = logged_in_client
    response = client.post(
        "/saved-searches/new",
        data={
            "name": "Civic in Lahore",
            "alerts_enabled": "y",
            "params": '{"make": "Honda", "max_price": "3500000"}',
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    from models import SavedSearch
    assert SavedSearch.query.count() == 1
    ss = SavedSearch.query.first()
    assert ss.alerts_enabled is True
    assert ss.params_dict.get("make") == "Honda"


def test_saved_search_matches_new_car(logged_in_client, user_factory, car_factory):
    client, user = logged_in_client
    client.post(
        "/saved-searches/new",
        data={
            "name": "Civic",
            "alerts_enabled": "y",
            "params": '{"make": "Honda", "max_price": "4000000"}',
        },
        follow_redirects=True,
    )

    seller = user_factory(email="ss-seller@example.com")
    from tasks import match_saved_searches_for_car
    car = car_factory(owner=seller, make="Honda", price=3000000.0)

    matched = match_saved_searches_for_car(car.id)
    assert matched == 1

    from models import Notification
    assert Notification.query.filter_by(user_id=user.id).count() == 1


def test_saved_search_does_not_match_when_filters_differ(logged_in_client, user_factory, car_factory):
    client, _user = logged_in_client
    client.post(
        "/saved-searches/new",
        data={
            "name": "Toyota only",
            "alerts_enabled": "y",
            "params": '{"make": "Toyota"}',
        },
        follow_redirects=True,
    )

    seller = user_factory(email="ss-seller2@example.com")
    from tasks import match_saved_searches_for_car
    car = car_factory(owner=seller, make="Honda")

    matched = match_saved_searches_for_car(car.id)
    assert matched == 0
