def test_api_list_cars_empty(client):
    response = client.get("/api/v1/cars")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["items"] == []
    assert payload["total"] == 0


def test_api_list_cars_returns_listings(client, user_factory, car_factory):
    seller = user_factory(email="api-seller@example.com")
    car_factory(owner=seller, make="Suzuki", model="Swift")

    response = client.get("/api/v1/cars")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 1
    assert payload["items"][0]["make"] == "Suzuki"


def test_api_get_car_includes_seller(client, user_factory, car_factory, url_for_with_app):
    seller = user_factory(email="seller-detail@example.com")
    car = car_factory(owner=seller)

    response = client.get(url_for_with_app("api.get_car", car_id=car.id))
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["seller"]["email"] == "seller-detail@example.com"


def test_api_favorites_requires_auth(client):
    response = client.get("/api/v1/favorites")
    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication required"}


def test_api_favorite_lifecycle(logged_in_client, user_factory, car_factory, url_for_with_app):
    client, _user = logged_in_client
    seller = user_factory(email="api-fav-seller@example.com")
    car = car_factory(owner=seller)

    response = client.post(url_for_with_app("api.add_favorite", car_id=car.id))
    assert response.status_code == 201

    response = client.get("/api/v1/favorites")
    items = response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["car"]["id"] == car.id

    response = client.delete(url_for_with_app("api.remove_favorite", car_id=car.id))
    assert response.status_code == 200
    assert response.get_json()["favorited"] is False
