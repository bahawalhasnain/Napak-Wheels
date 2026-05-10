def test_signup_creates_user(client):
    response = client.post(
        "/signup",
        data={
            "full_name": "Alice",
            "email": "alice@example.com",
            "phone": "0300-0000000",
            "location": "Lahore",
            "password": "supersecret123",
            "confirm_password": "supersecret123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    from models import User
    assert User.query.filter_by(email="alice@example.com").first() is not None


def test_login_valid_credentials(client, user_factory):
    user_factory(email="bob@example.com", password="bobspassword")
    response = client.post(
        "/login",
        data={"email": "bob@example.com", "password": "bobspassword"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Welcome back" in response.data


def test_login_invalid_credentials(client, user_factory):
    user_factory(email="carol@example.com", password="rightpassword")
    response = client.post(
        "/login",
        data={"email": "carol@example.com", "password": "wrongpassword"},
        follow_redirects=True,
    )
    assert b"Invalid email or password" in response.data


def test_protected_route_redirects_when_anonymous(client):
    response = client.get("/my_listings")
    assert response.status_code in (301, 302)
    assert "/login" in response.headers["Location"]
