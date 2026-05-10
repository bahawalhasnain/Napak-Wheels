from datetime import date, datetime

from flask_login import UserMixin

from extensions import db, login_manager


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False, index=True)
    email_alerts_enabled = db.Column(db.Boolean, default=True, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    cars = db.relationship("Car", back_populates="owner", lazy=True)
    favorites = db.relationship(
        "Favorite", back_populates="user", cascade="all, delete-orphan", lazy="dynamic"
    )
    saved_searches = db.relationship(
        "SavedSearch", back_populates="user", cascade="all, delete-orphan", lazy="dynamic"
    )
    notifications = db.relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan", lazy="dynamic"
    )

    def __repr__(self):
        return f"<User {self.email}>"

    def has_favorited(self, car_id):
        return self.favorites.filter_by(car_id=car_id).first() is not None

    def unread_message_count(self):
        return (
            Message.query.join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Message.read_at.is_(None),
                Message.sender_id != self.id,
                db.or_(
                    Conversation.buyer_id == self.id,
                    Conversation.seller_id == self.id,
                ),
            )
            .count()
        )

    def unread_notification_count(self):
        return self.notifications.filter(Notification.read_at.is_(None)).count()


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Cars
# ---------------------------------------------------------------------------


class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    make = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    mileage = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(30), nullable=False)
    fuel_type = db.Column(db.String(20), nullable=False)
    transmission = db.Column(db.String(20), nullable=False)
    engine_size = db.Column(db.String(10))
    description = db.Column(db.Text)
    features = db.Column(db.Text)
    seller_name = db.Column(db.String(100), nullable=False)
    seller_phone = db.Column(db.String(20), nullable=False)
    seller_email = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    photo_filename = db.Column(db.String(255))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    is_sold = db.Column(db.Boolean, default=False)
    is_taken_down = db.Column(db.Boolean, default=False, nullable=False, index=True)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    owner = db.relationship("User", back_populates="cars")
    images = db.relationship(
        "CarImage", back_populates="car", cascade="all, delete-orphan",
        order_by="CarImage.id", lazy=True,
    )
    favorited_by = db.relationship(
        "Favorite", back_populates="car", cascade="all, delete-orphan", lazy="dynamic"
    )
    conversations = db.relationship(
        "Conversation", back_populates="car", cascade="all, delete-orphan", lazy="dynamic"
    )
    offers = db.relationship(
        "Offer", back_populates="car", cascade="all, delete-orphan", lazy="dynamic"
    )
    test_drives = db.relationship(
        "TestDrive", back_populates="car", cascade="all, delete-orphan", lazy="dynamic"
    )
    reports = db.relationship(
        "Report", back_populates="car", cascade="all, delete-orphan", lazy="dynamic"
    )
    views = db.relationship(
        "CarView", back_populates="car", cascade="all, delete-orphan", lazy="dynamic"
    )

    def __repr__(self):
        return f"<Car {self.year} {self.make} {self.model}>"

    def views_today(self):
        return self.views.filter(CarView.viewed_date == date.today()).count()

    @property
    def formatted_price(self):
        return f"RS {self.price:,.0f}"

    @property
    def formatted_mileage(self):
        return f"{self.mileage:,} miles"

    @property
    def display_photos(self):
        image_files = [image.filename for image in self.images if image.filename]
        if image_files:
            return image_files
        return [self.photo_filename] if self.photo_filename else []

    @property
    def primary_photo(self):
        photos = self.display_photos
        return photos[0] if photos else None

    @property
    def features_list(self):
        import json

        if not self.features:
            return []
        try:
            parsed = json.loads(self.features)
            if isinstance(parsed, list):
                return [str(x) for x in parsed if str(x).strip()]
        except Exception:
            pass

        return [x.strip() for x in str(self.features).split(",") if x.strip()]

    @property
    def favorite_count(self):
        return self.favorited_by.count()

    @property
    def is_visible(self):
        return not self.is_taken_down

    def to_dict(self, include_seller=False):
        data = {
            "id": self.id,
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "price": self.price,
            "formatted_price": self.formatted_price,
            "mileage": self.mileage,
            "color": self.color,
            "fuel_type": self.fuel_type,
            "transmission": self.transmission,
            "engine_size": self.engine_size,
            "description": self.description,
            "features": self.features_list,
            "location": self.location,
            "is_sold": bool(self.is_sold),
            "is_taken_down": bool(self.is_taken_down),
            "date_posted": self.date_posted.isoformat() if self.date_posted else None,
            "primary_photo": self.primary_photo,
            "photos": self.display_photos,
            "favorite_count": self.favorite_count,
        }
        if include_seller:
            data["seller"] = {
                "name": self.seller_name,
                "phone": self.seller_phone,
                "email": self.seller_email,
            }
        return data


class CarImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey("car.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    car = db.relationship("Car", back_populates="images")

    def __repr__(self):
        return f"<CarImage {self.filename}>"


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------


class Favorite(db.Model):
    __tablename__ = "favorite"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    car_id = db.Column(db.Integer, db.ForeignKey("car.id"), nullable=False, index=True)
    date_added = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="favorites")
    car = db.relationship("Car", back_populates="favorited_by")

    __table_args__ = (db.UniqueConstraint("user_id", "car_id", name="uq_favorite_user_car"),)


# ---------------------------------------------------------------------------
# Car views (analytics)
# ---------------------------------------------------------------------------


class CarView(db.Model):
    """A single (deduped) view event of a car listing.

    We dedupe per (car, viewer_user_id OR session_key, viewed_date) so refreshing
    the page in the same day doesn't inflate the counter.
    """

    __tablename__ = "car_view"

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey("car.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    session_key = db.Column(db.String(64), nullable=True, index=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    viewed_date = db.Column(db.Date, default=date.today, nullable=False, index=True)

    car = db.relationship("Car", back_populates="views")
    user = db.relationship("User")

    __table_args__ = (
        db.Index("ix_car_view_car_date", "car_id", "viewed_date"),
        db.Index("ix_car_view_dedupe_user", "car_id", "user_id", "viewed_date"),
        db.Index("ix_car_view_dedupe_session", "car_id", "session_key", "viewed_date"),
    )


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------


class Conversation(db.Model):
    """A single thread between a buyer and seller about a specific car."""

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey("car.id"), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True
    )

    car = db.relationship("Car", back_populates="conversations")
    buyer = db.relationship("User", foreign_keys=[buyer_id])
    seller = db.relationship("User", foreign_keys=[seller_id])
    messages = db.relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    __table_args__ = (
        db.UniqueConstraint("car_id", "buyer_id", name="uq_conversation_car_buyer"),
    )

    def other_party(self, user):
        return self.seller if user.id == self.buyer_id else self.buyer

    def latest_message(self):
        return (
            Message.query.filter_by(conversation_id=self.id)
            .order_by(Message.created_at.desc())
            .first()
        )

    def unread_for(self, user):
        return (
            Message.query.filter_by(conversation_id=self.id, read_at=None)
            .filter(Message.sender_id != user.id)
            .count()
        )


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversation.id"), nullable=False, index=True
    )
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)

    conversation = db.relationship("Conversation", back_populates="messages")
    sender = db.relationship("User")


# ---------------------------------------------------------------------------
# Offers
# ---------------------------------------------------------------------------


class Offer(db.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_COUNTERED = "countered"
    STATUS_WITHDRAWN = "withdrawn"

    PROPOSED_BUYER = "buyer"
    PROPOSED_SELLER = "seller"

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey("car.id"), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)
    proposed_by = db.Column(db.String(10), nullable=False, default=PROPOSED_BUYER)
    parent_offer_id = db.Column(db.Integer, db.ForeignKey("offer.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    car = db.relationship("Car", back_populates="offers")
    buyer = db.relationship("User", foreign_keys=[buyer_id])
    seller = db.relationship("User", foreign_keys=[seller_id])
    parent = db.relationship("Offer", remote_side=[id], backref="children")

    @property
    def is_open(self):
        return self.status in {self.STATUS_PENDING, self.STATUS_COUNTERED}

    @property
    def formatted_amount(self):
        return f"RS {self.amount:,.0f}"


# ---------------------------------------------------------------------------
# Test drives
# ---------------------------------------------------------------------------


class TestDrive(db.Model):
    STATUS_REQUESTED = "requested"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DECLINED = "declined"
    STATUS_CANCELLED = "cancelled"
    STATUS_COMPLETED = "completed"

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey("car.id"), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    requested_at = db.Column(db.DateTime, nullable=False, index=True)
    duration_minutes = db.Column(db.Integer, nullable=False, default=30)
    location = db.Column(db.String(200), nullable=True)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_REQUESTED, index=True)
    seller_response = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    car = db.relationship("Car", back_populates="test_drives")
    buyer = db.relationship("User", foreign_keys=[buyer_id])
    seller = db.relationship("User", foreign_keys=[seller_id])


# ---------------------------------------------------------------------------
# Saved searches
# ---------------------------------------------------------------------------


class SavedSearch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    params = db.Column(db.Text, nullable=False)
    alerts_enabled = db.Column(db.Boolean, default=True, nullable=False)
    last_notified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="saved_searches")

    @property
    def params_dict(self):
        import json

        if not self.params:
            return {}
        try:
            value = json.loads(self.params)
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def matches_car(self, car):
        params = self.params_dict
        if not params:
            return False

        if car.is_sold or car.is_taken_down:
            return False

        text = params.get("search")
        if text:
            text_l = text.lower()
            haystack = " ".join(
                str(x or "") for x in (car.make, car.model, car.description)
            ).lower()
            if text_l not in haystack:
                return False

        if params.get("make") and car.make != params["make"]:
            return False
        if params.get("fuel_type") and car.fuel_type != params["fuel_type"]:
            return False
        if params.get("location"):
            if params["location"].lower() not in (car.location or "").lower():
                return False

        for key, op in (("min_price", "ge"), ("max_price", "le")):
            value = params.get(key)
            if value in (None, ""):
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if op == "ge" and car.price < value:
                return False
            if op == "le" and car.price > value:
                return False

        for key, op in (("min_year", "ge"), ("max_year", "le")):
            value = params.get(key)
            if value in (None, ""):
                continue
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            if op == "ge" and car.year < value:
                return False
            if op == "le" and car.year > value:
                return False

        return True


# ---------------------------------------------------------------------------
# Reports / moderation
# ---------------------------------------------------------------------------


class Report(db.Model):
    REASONS = [
        ("spam", "Spam / duplicate listing"),
        ("fraud", "Suspected fraud / scam"),
        ("sold", "Already sold"),
        ("inappropriate", "Inappropriate content"),
        ("wrong_info", "Incorrect information"),
        ("other", "Other"),
    ]

    STATUS_OPEN = "open"
    STATUS_REVIEWED = "reviewed"
    STATUS_DISMISSED = "dismissed"
    STATUS_ACTIONED = "actioned"

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey("car.id"), nullable=False, index=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(30), nullable=False)
    details = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_OPEN, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    review_note = db.Column(db.Text, nullable=True)

    car = db.relationship("Car", back_populates="reports")
    reporter = db.relationship("User", foreign_keys=[reporter_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])

    @property
    def reason_label(self):
        return dict(self.REASONS).get(self.reason, self.reason)


# ---------------------------------------------------------------------------
# In-app notifications
# ---------------------------------------------------------------------------


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=True)
    link = db.Column(db.String(500), nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", back_populates="notifications")

    @classmethod
    def push(cls, user_id, title, body=None, link=None):
        notif = cls(user_id=user_id, title=title, body=body, link=link)
        db.session.add(notif)
        return notif
