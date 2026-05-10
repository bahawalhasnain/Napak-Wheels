def test_add_and_remove_favorite_via_html(
    logged_in_client, user_factory, car_factory, url_for_with_app,
):
    client, _user = logged_in_client
    seller = user_factory(email="seller@example.com")
    car = car_factory(owner=seller)

    response = client.post(url_for_with_app("main.add_favorite", car_id=car.id), follow_redirects=True)
    assert response.status_code == 200

    from models import Favorite
    assert Favorite.query.count() == 1

    response = client.post(url_for_with_app("main.remove_favorite", car_id=car.id), follow_redirects=True)
    assert response.status_code == 200
    assert Favorite.query.count() == 0


def test_cannot_favorite_own_listing(logged_in_client, car_factory, url_for_with_app):
    client, user = logged_in_client
    car = car_factory(owner=user)

    response = client.post(url_for_with_app("main.add_favorite", car_id=car.id), follow_redirects=True)
    assert response.status_code == 200

    from models import Favorite
    assert Favorite.query.count() == 0
