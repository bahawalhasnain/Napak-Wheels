def test_buyer_can_start_conversation(logged_in_client, user_factory, car_factory):
    client, _user = logged_in_client
    seller = user_factory(email="seller-msg@example.com")
    car = car_factory(owner=seller)

    response = client.get(f"/messages/start/{car.id}", follow_redirects=True)
    assert response.status_code == 200

    from models import Conversation
    assert Conversation.query.count() == 1


def test_send_message_creates_record_and_notification(logged_in_client, user_factory, car_factory):
    client, buyer = logged_in_client
    seller = user_factory(email="seller-msg2@example.com")
    car = car_factory(owner=seller)

    client.get(f"/messages/start/{car.id}", follow_redirects=True)

    from models import Conversation, Message, Notification
    convo = Conversation.query.first()
    response = client.post(
        f"/messages/{convo.id}",
        data={"body": "Hello, is this still available?"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert Message.query.count() == 1
    assert Notification.query.filter_by(user_id=seller.id).count() == 1


def test_outsider_cannot_view_thread(client, user_factory, car_factory):
    seller = user_factory(email="seller-msg3@example.com")
    buyer = user_factory(email="buyer-msg3@example.com")
    outsider = user_factory(email="outsider@example.com")
    car = car_factory(owner=seller)

    # Buyer creates a conversation
    client.post("/login", data={"email": buyer.email, "password": "testpass123"}, follow_redirects=True)
    client.get(f"/messages/start/{car.id}", follow_redirects=True)

    from models import Conversation
    convo = Conversation.query.first()

    # Outsider logs in and tries to view it
    client.get("/logout")
    client.post("/login", data={"email": outsider.email, "password": "testpass123"}, follow_redirects=True)
    response = client.get(f"/messages/{convo.id}")
    assert response.status_code == 403
