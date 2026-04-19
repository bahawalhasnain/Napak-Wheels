from datetime import datetime
from extensions import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    cars = db.relationship('Car', back_populates='owner', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'


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
    # Stored as JSON array string of feature tags.
    features = db.Column(db.Text)
    seller_name = db.Column(db.String(100), nullable=False)
    seller_phone = db.Column(db.String(20), nullable=False)
    seller_email = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    photo_filename = db.Column(db.String(255))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    is_sold = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    owner = db.relationship('User', back_populates='cars')
    images = db.relationship(
        'CarImage',
        back_populates='car',
        cascade='all, delete-orphan',
        order_by='CarImage.id',
        lazy=True,
    )
    
    def __repr__(self):
        return f'<Car {self.year} {self.make} {self.model}>'
    
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
        """Return features as list of strings (new listings store JSON array)."""
        import json

        if not self.features:
            return []
        try:
            parsed = json.loads(self.features)
            if isinstance(parsed, list):
                return [str(x) for x in parsed if str(x).strip()]
        except Exception:
            pass

        # Backward compatibility if stored as comma-separated text.
        return [x.strip() for x in str(self.features).split(",") if x.strip()]


class CarImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('car.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    car = db.relationship('Car', back_populates='images')

    def __repr__(self):
        return f'<CarImage {self.filename}>'
