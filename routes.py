import json
import os
import uuid
from datetime import date

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, send_from_directory, session, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from extensions import db
from forms import CarForm, EditCarForm, LoginForm, SearchForm, SignUpForm
from models import Car, CarImage, CarView, Favorite, User
from tasks import match_saved_searches_for_car, process_uploaded_image


bp = Blueprint("main", __name__)


COMMON_FEATURES = [
    "Adaptive Cruise Control", "Lane Keep Assist", "Lane Departure Warning",
    "Blind Spot Monitoring", "Rear Cross-Traffic Alert", "Automatic Emergency Braking",
    "Forward Collision Warning", "Pedestrian Detection", "Automatic Headlights",
    "Keyless Entry", "Push Button Start", "Heated Seats", "Ventilated Seats",
    "Power Seats", "Sunroof", "Panoramic Roof", "Electronic Stability Control",
    "Traction Control", "Anti-lock Braking System (ABS)", "Electronic Parking Brake",
    "Hill Descent Control", "Hill Start Assist", "Parking Sensors",
    "Rear Parking Camera", "360-Degree Camera", "Auto-Dimming Rearview Mirror",
    "Wireless Charging", "USB-C Ports", "Apple CarPlay", "Android Auto",
    "Navigation System", "Wireless Android Auto/Apple CarPlay",
    "Automatic Climate Control", "Dual-Zone Climate Control", "Remote Start",
    "Power Tailgate", "Cruise Control", "Automatic Wipers", "Rain Sensing Wipers",
    "Smart Key System", "Electronic Brake Assist", "Driver Attention Alert",
    "Traffic Sign Recognition", "Lane Centering Assist", "Lane Tracing Assist",
    "Apple CarPlay + Android Auto", "Heated Steering Wheel",
]


def _parse_features(raw_value):
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
        return [x.strip() for x in raw_value.split(",") if x.strip()]
    return [str(raw_value).strip()] if str(raw_value).strip() else []


def _allowed_file(filename):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_IMAGE_EXTENSIONS", set())


def _save_photo(upload):
    if not upload or not _allowed_file(upload.filename):
        return None

    filename = secure_filename(upload.filename)
    unique_filename = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_filename)
    upload.save(file_path)
    try:
        process_uploaded_image.delay(file_path)
    except Exception:
        current_app.logger.exception("Image processing dispatch failed for %s", file_path)
    return unique_filename


def _extract_valid_uploads(files):
    return [file for file in (files or []) if file and file.filename]


def _save_photos(files):
    filenames = []
    for file in _extract_valid_uploads(files):
        saved = _save_photo(file)
        if saved:
            filenames.append(saved)
    return filenames


def _record_car_view(car):
    """Record a unique-per-day view of a car listing.

    Skipped for the owner and admins so the counter reflects genuine buyer interest.
    Anonymous visitors are deduped by a per-session UUID stored in the Flask session.
    """

    if car.is_taken_down:
        return

    if current_user.is_authenticated and (
        current_user.id == car.user_id or current_user.is_admin
    ):
        return

    today = date.today()

    if current_user.is_authenticated:
        already = CarView.query.filter_by(
            car_id=car.id, user_id=current_user.id, viewed_date=today
        ).first()
        if already:
            return
        view = CarView(car_id=car.id, user_id=current_user.id, viewed_date=today)
    else:
        token = session.get("anon_view_token")
        if not token:
            token = uuid.uuid4().hex
            session["anon_view_token"] = token
        already = CarView.query.filter_by(
            car_id=car.id, session_key=token, viewed_date=today
        ).first()
        if already:
            return
        view = CarView(car_id=car.id, session_key=token, viewed_date=today)

    db.session.add(view)
    car.view_count = (car.view_count or 0) + 1
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to record car view for car_id=%s", car.id)


def _favorited_ids_for_current_user(car_ids):
    if not current_user.is_authenticated or not car_ids:
        return set()
    rows = (
        db.session.query(Favorite.car_id)
        .filter(Favorite.user_id == current_user.id, Favorite.car_id.in_(car_ids))
        .all()
    )
    return {row[0] for row in rows}


@bp.app_context_processor
def inject_user():
    return {"current_user": current_user}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = SignUpForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if existing:
            flash("This email is already registered. Please log in.", "warning")
            return redirect(url_for("main.login"))

        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=form.phone.data.strip(),
            location=form.location.data.strip(),
            password_hash=generate_password_hash(form.password.data),
        )
        db.session.add(user)
        db.session.commit()
        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("main.login"))

    return render_template("signup.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=bool(form.remember.data))
            flash(f"Welcome back, {user.full_name}.", "success")
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("main.index"))
        flash("Invalid email or password.", "danger")

    return render_template("login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.login"))


# ---------------------------------------------------------------------------
# Browse + detail
# ---------------------------------------------------------------------------


@bp.route("/")
def index():
    search_form = SearchForm(request.args)

    base_filter = db.and_(Car.is_sold == False, Car.is_taken_down == False)
    makes = db.session.query(Car.make.distinct()).filter(base_filter).all()
    search_form.make.choices = [("", "Any Make")] + [(m[0], m[0]) for m in makes]

    query = Car.query.filter(base_filter)

    if request.args.get("search"):
        like = f"%{request.args.get('search')}%"
        query = query.filter(
            db.or_(
                Car.make.ilike(like),
                Car.model.ilike(like),
                Car.description.ilike(like),
            )
        )

    if request.args.get("make"):
        query = query.filter(Car.make == request.args.get("make"))

    for arg, column, cast in (
        ("min_price", Car.price, float),
        ("max_price", Car.price, float),
        ("min_year", Car.year, int),
        ("max_year", Car.year, int),
    ):
        raw = request.args.get(arg)
        if not raw or not raw.strip():
            continue
        try:
            value = cast(raw)
        except (ValueError, TypeError):
            continue
        query = query.filter(column >= value if arg.startswith("min_") else column <= value)

    if request.args.get("fuel_type"):
        query = query.filter(Car.fuel_type == request.args.get("fuel_type"))

    cars = query.order_by(Car.date_posted.desc()).all()
    favorited_ids = _favorited_ids_for_current_user([c.id for c in cars])
    return render_template(
        "index.html",
        cars=cars,
        search_form=search_form,
        favorited_ids=favorited_ids,
    )


@bp.route("/car/<int:id>")
def car_detail(id):
    car = Car.query.get_or_404(id)
    if car.is_taken_down and not (current_user.is_authenticated and (
        current_user.is_admin or current_user.id == car.user_id
    )):
        abort(404)

    _record_car_view(car)

    is_favorited = (
        current_user.is_authenticated and current_user.has_favorited(car.id)
    )
    views_today = car.views_today()
    return render_template(
        "car_detail.html",
        car=car,
        is_favorited=is_favorited,
        views_today=views_today,
        total_views=car.view_count or 0,
    )


# ---------------------------------------------------------------------------
# Listings (CRUD)
# ---------------------------------------------------------------------------


@bp.route("/add_car", methods=["GET", "POST"])
@login_required
def add_car():
    form = CarForm()
    if request.method == "GET":
        form.features.data = json.dumps([])
        form.seller_phone.data = current_user.phone or ""
        form.location.data = current_user.location or ""

    if form.validate_on_submit():
        uploads = _extract_valid_uploads(form.photos.data)
        if len(uploads) > 6:
            flash("You can upload a maximum of 6 photos.", "danger")
            return render_template(
                "add_car.html", form=form, feature_suggestions=COMMON_FEATURES,
            )

        photo_filenames = _save_photos(uploads)
        raw = request.form.get("features_json", form.features.data)
        features_list = _parse_features(raw)

        car = Car(
            make=form.make.data, model=form.model.data, year=form.year.data,
            price=form.price.data, mileage=form.mileage.data, color=form.color.data,
            fuel_type=form.fuel_type.data, transmission=form.transmission.data,
            engine_size=form.engine_size.data, description=form.description.data,
            seller_name=current_user.full_name, seller_phone=form.seller_phone.data,
            seller_email=current_user.email, location=form.location.data,
            photo_filename=photo_filenames[0] if photo_filenames else None,
            user_id=current_user.id, features=json.dumps(features_list),
        )
        db.session.add(car)
        db.session.flush()

        for filename in photo_filenames:
            db.session.add(CarImage(car_id=car.id, filename=filename))

        db.session.commit()

        try:
            match_saved_searches_for_car.delay(car.id)
        except Exception:
            current_app.logger.exception("Saved-search matching dispatch failed for car %s", car.id)

        flash("Your car listing has been posted successfully!", "success")
        return redirect(url_for("main.my_listings"))

    return render_template(
        "add_car.html", form=form, feature_suggestions=COMMON_FEATURES,
    )


@bp.route("/edit_car/<int:id>", methods=["GET", "POST"])
@login_required
def edit_car(id):
    car = Car.query.get_or_404(id)
    if car.user_id != current_user.id:
        abort(403)

    form = EditCarForm(obj=car)
    if request.method == "GET":
        form.seller_name.data = current_user.full_name
        form.seller_email.data = current_user.email
        form.features.data = json.dumps(car.features_list)

    if form.validate_on_submit():
        uploads = _extract_valid_uploads(form.photos.data)
        if uploads and len(uploads) > 6:
            flash("You can upload a maximum of 6 photos.", "danger")
            return render_template(
                "edit_car.html", form=form, car=car, feature_suggestions=COMMON_FEATURES,
            )

        if uploads:
            for existing in car.images:
                old_image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], existing.filename)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
                db.session.delete(existing)

            if car.photo_filename:
                old_path = os.path.join(current_app.config["UPLOAD_FOLDER"], car.photo_filename)
                if os.path.exists(old_path):
                    os.remove(old_path)

            photo_filenames = _save_photos(uploads)
            car.photo_filename = photo_filenames[0] if photo_filenames else None
            for filename in photo_filenames:
                db.session.add(CarImage(car=car, filename=filename))

        car.make = form.make.data
        car.model = form.model.data
        car.year = form.year.data
        car.price = form.price.data
        car.mileage = form.mileage.data
        car.color = form.color.data
        car.fuel_type = form.fuel_type.data
        car.transmission = form.transmission.data
        car.engine_size = form.engine_size.data
        car.description = form.description.data
        car.seller_phone = form.seller_phone.data
        car.location = form.location.data
        car.is_sold = bool(form.is_sold.data)
        car.seller_name = current_user.full_name
        car.seller_email = current_user.email
        car.user_id = current_user.id
        raw = request.form.get("features_json", form.features.data)
        car.features = json.dumps(_parse_features(raw))
        db.session.commit()
        flash("Your car listing has been updated successfully!", "success")
        return redirect(url_for("main.car_detail", id=car.id))

    return render_template(
        "edit_car.html", form=form, car=car, feature_suggestions=COMMON_FEATURES,
    )


@bp.route("/my_listings")
@login_required
def my_listings():
    cars = (
        Car.query.filter_by(user_id=current_user.id)
        .order_by(Car.date_posted.desc())
        .all()
    )
    return render_template("my_listings.html", cars=cars)


@bp.route("/delete_car/<int:id>", methods=["POST"])
@login_required
def delete_car(id):
    car = Car.query.get_or_404(id)
    if car.user_id != current_user.id:
        abort(403)

    for image in car.images:
        file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], image.filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    if car.photo_filename:
        legacy_path = os.path.join(current_app.config["UPLOAD_FOLDER"], car.photo_filename)
        if os.path.exists(legacy_path):
            os.remove(legacy_path)

    db.session.delete(car)
    db.session.commit()
    flash("Car listing has been deleted successfully!", "success")
    return redirect(url_for("main.my_listings"))


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------


@bp.route("/favorite/<int:car_id>", methods=["POST"])
@login_required
def add_favorite(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id == current_user.id:
        flash("You cannot favorite your own listing.", "warning")
        return redirect(request.referrer or url_for("main.car_detail", id=car_id))

    existing = Favorite.query.filter_by(user_id=current_user.id, car_id=car_id).first()
    if not existing:
        db.session.add(Favorite(user_id=current_user.id, car_id=car_id))
        db.session.commit()
        flash("Saved to your favorites.", "success")
    return redirect(request.referrer or url_for("main.car_detail", id=car_id))


@bp.route("/unfavorite/<int:car_id>", methods=["POST"])
@login_required
def remove_favorite(car_id):
    favorite = Favorite.query.filter_by(user_id=current_user.id, car_id=car_id).first()
    if favorite:
        db.session.delete(favorite)
        db.session.commit()
        flash("Removed from your favorites.", "info")
    return redirect(request.referrer or url_for("main.my_favorites"))


@bp.route("/my_favorites")
@login_required
def my_favorites():
    favorites = (
        Favorite.query.filter_by(user_id=current_user.id)
        .order_by(Favorite.date_added.desc())
        .all()
    )
    cars = [fav.car for fav in favorites if fav.car is not None]
    return render_template(
        "my_favorites.html", cars=cars, favorited_ids={c.id for c in cars}
    )


@bp.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
