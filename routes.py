import os
import uuid
import json
from functools import wraps

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
    current_app,
)
from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from extensions import db
from forms import CarForm, EditCarForm, LoginForm, SearchForm, SignUpForm
from models import Car, CarImage, User

bp = Blueprint("main", __name__)

# Predefined feature suggestions for the tag input.
COMMON_FEATURES = [
    "Adaptive Cruise Control",
    "Lane Keep Assist",
    "Lane Departure Warning",
    "Blind Spot Monitoring",
    "Rear Cross-Traffic Alert",
    "Automatic Emergency Braking",
    "Forward Collision Warning",
    "Pedestrian Detection",
    "Automatic Headlights",
    "Keyless Entry",
    "Push Button Start",
    "Heated Seats",
    "Ventilated Seats",
    "Power Seats",
    "Sunroof",
    "Panoramic Roof",
    "Electronic Stability Control",
    "Traction Control",
    "Anti-lock Braking System (ABS)",
    "Electronic Parking Brake",
    "Hill Descent Control",
    "Hill Start Assist",
    "Parking Sensors",
    "Rear Parking Camera",
    "360-Degree Camera",
    "Auto-Dimming Rearview Mirror",
    "Wireless Charging",
    "USB-C Ports",
    "Apple CarPlay",
    "Android Auto",
    "Navigation System",
    "Wireless Android Auto/Apple CarPlay",
    "Automatic Climate Control",
    "Dual-Zone Climate Control",
    "Remote Start",
    "Power Tailgate",
    "Cruise Control",
    "Automatic Wipers",
    "Rain Sensing Wipers",
    "Smart Key System",
    "Electronic Brake Assist",
    "Driver Attention Alert",
    "Traffic Sign Recognition",
    "Lane Centering Assist",
    "Lane Tracing Assist",
    "Apple CarPlay + Android Auto",
    "Heated Steering Wheel",
]


def _parse_features(raw_value):
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if not raw_value:
            return []
        # Expected: JSON array string from the tag widget.
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

        # Fallback: comma-separated string.
        return [x.strip() for x in raw_value.split(",") if x.strip()]

    # Last resort: string conversion
    return [str(raw_value).strip()] if str(raw_value).strip() else []


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = User.query.get(user_id) if user_id else None


@bp.app_context_processor
def inject_user():
    return {"current_user": g.get("user")}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"png", "jpg", "jpeg", "gif", "jfif"}


def process_image(file_path, max_size=(800, 600)):
    try:
        with Image.open(file_path) as img:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            img.save(file_path, optimize=True, quality=85)
    except Exception as exc:
        current_app.logger.error(f"Error processing image: {exc}")


def _save_photo(upload):
    if not upload or not allowed_file(upload.filename):
        return None

    filename = secure_filename(upload.filename)
    unique_filename = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_filename)
    upload.save(file_path)
    process_image(file_path)
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


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("main.index"))

    form = SignUpForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if existing_user:
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
    if g.user:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            session.clear()
            session["user_id"] = user.id
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
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.login"))


@bp.route("/")
def index():
    search_form = SearchForm(request.args)

    makes = db.session.query(Car.make.distinct()).filter(Car.is_sold == False).all()
    search_form.make.choices = [("", "Any Make")] + [(make[0], make[0]) for make in makes]

    query = Car.query.filter(Car.is_sold == False)

    if request.args.get("search"):
        search_term = f"%{request.args.get('search')}%"
        query = query.filter(
            db.or_(
                Car.make.ilike(search_term),
                Car.model.ilike(search_term),
                Car.description.ilike(search_term),
            )
        )

    if request.args.get("make"):
        query = query.filter(Car.make == request.args.get("make"))

    min_price = request.args.get("min_price")
    if min_price and min_price.strip():
        try:
            query = query.filter(Car.price >= float(min_price))
        except (ValueError, TypeError):
            pass

    max_price = request.args.get("max_price")
    if max_price and max_price.strip():
        try:
            query = query.filter(Car.price <= float(max_price))
        except (ValueError, TypeError):
            pass

    min_year = request.args.get("min_year")
    if min_year and min_year.strip():
        try:
            query = query.filter(Car.year >= int(min_year))
        except (ValueError, TypeError):
            pass

    max_year = request.args.get("max_year")
    if max_year and max_year.strip():
        try:
            query = query.filter(Car.year <= int(max_year))
        except (ValueError, TypeError):
            pass

    if request.args.get("fuel_type"):
        query = query.filter(Car.fuel_type == request.args.get("fuel_type"))

    cars = query.order_by(Car.date_posted.desc()).all()
    return render_template("index.html", cars=cars, search_form=search_form)


@bp.route("/car/<int:id>")
def car_detail(id):
    car = Car.query.get_or_404(id)
    return render_template("car_detail.html", car=car)


@bp.route("/add_car", methods=["GET", "POST"])
@login_required
def add_car():
    form = CarForm()
    if request.method == "GET":
        # Tag widget stores the selected features in this hidden field.
        form.features.data = json.dumps([])
        if g.user:
            form.seller_phone.data = g.user.phone or ""
            form.location.data = g.user.location or ""

    if form.validate_on_submit():
        uploads = _extract_valid_uploads(form.photos.data)
        if len(uploads) > 6:
            flash("You can upload a maximum of 6 photos.", "danger")
            return render_template(
                "add_car.html",
                form=form,
                feature_suggestions=COMMON_FEATURES,
            )

        photo_filenames = _save_photos(uploads)
        raw_features_payload = request.form.get("features_json", form.features.data)
        features_list = _parse_features(raw_features_payload)

        car = Car(
            make=form.make.data,
            model=form.model.data,
            year=form.year.data,
            price=form.price.data,
            mileage=form.mileage.data,
            color=form.color.data,
            fuel_type=form.fuel_type.data,
            transmission=form.transmission.data,
            engine_size=form.engine_size.data,
            description=form.description.data,
            seller_name=g.user.full_name,
            seller_phone=form.seller_phone.data,
            seller_email=g.user.email,
            location=form.location.data,
            photo_filename=photo_filenames[0] if photo_filenames else None,
            user_id=g.user.id,
            features=json.dumps(features_list),
        )
        db.session.add(car)
        db.session.flush()

        for filename in photo_filenames:
            db.session.add(CarImage(car_id=car.id, filename=filename))

        db.session.commit()
        flash("Your car listing has been posted successfully!", "success")
        return redirect(url_for("main.my_listings"))

    return render_template(
        "add_car.html",
        form=form,
        feature_suggestions=COMMON_FEATURES,
    )


@bp.route("/edit_car/<int:id>", methods=["GET", "POST"])
@login_required
def edit_car(id):
    car = Car.query.get_or_404(id)
    if car.user_id != g.user.id:
        abort(403)

    form = EditCarForm(obj=car)
    if request.method == "GET":
        form.seller_name.data = g.user.full_name
        form.seller_email.data = g.user.email
        form.features.data = json.dumps(car.features_list)

    if form.validate_on_submit():
        uploads = _extract_valid_uploads(form.photos.data)
        if uploads and len(uploads) > 6:
            flash("You can upload a maximum of 6 photos.", "danger")
            return render_template(
                "edit_car.html",
                form=form,
                car=car,
                feature_suggestions=COMMON_FEATURES,
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
        car.seller_name = g.user.full_name
        car.seller_email = g.user.email
        car.user_id = g.user.id
        raw_features_payload = request.form.get("features_json", form.features.data)
        car.features = json.dumps(_parse_features(raw_features_payload))
        db.session.commit()
        flash("Your car listing has been updated successfully!", "success")
        return redirect(url_for("main.car_detail", id=car.id))

    return render_template(
        "edit_car.html",
        form=form,
        car=car,
        feature_suggestions=COMMON_FEATURES,
    )


@bp.route("/my_listings")
@login_required
def my_listings():
    cars = Car.query.filter_by(user_id=g.user.id).order_by(Car.date_posted.desc()).all()
    return render_template("my_listings.html", cars=cars)


@bp.route("/delete_car/<int:id>", methods=["POST"])
@login_required
def delete_car(id):
    car = Car.query.get_or_404(id)
    if car.user_id != g.user.id:
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


@bp.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@bp.app_errorhandler(403)
def forbidden_error(error):
    return render_template("403.html"), 403


@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404


@bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("500.html"), 500
