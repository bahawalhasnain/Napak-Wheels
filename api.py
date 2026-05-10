"""JSON REST API at /api/v1/*."""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from extensions import db
from models import Car, Favorite


api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


def _abs_url(name):
    return request.host_url.rstrip("/") + url_for("main.uploaded_file", filename=name)


def _serialize_car(car: Car) -> dict:
    payload = car.to_dict(include_seller=False)
    payload["url"] = request.host_url.rstrip("/") + url_for("main.car_detail", id=car.id)
    payload["photos"] = [_abs_url(name) for name in payload.get("photos", [])]
    if payload.get("primary_photo"):
        payload["primary_photo"] = _abs_url(payload["primary_photo"])
    return payload


@api_bp.route("/cars", methods=["GET"])
def list_cars():
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 20) or 20), 1), 100)

    query = Car.query.filter(Car.is_sold == False, Car.is_taken_down == False)

    search = request.args.get("search")
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Car.make.ilike(like), Car.model.ilike(like), Car.description.ilike(like))
        )
    if request.args.get("make"):
        query = query.filter(Car.make == request.args.get("make"))
    if request.args.get("fuel_type"):
        query = query.filter(Car.fuel_type == request.args.get("fuel_type"))

    for arg, column, cast in (
        ("min_price", Car.price, float),
        ("max_price", Car.price, float),
        ("min_year", Car.year, int),
        ("max_year", Car.year, int),
    ):
        raw = request.args.get(arg)
        if raw is None or raw == "":
            continue
        try:
            value = cast(raw)
        except (ValueError, TypeError):
            continue
        query = query.filter(column >= value if arg.startswith("min_") else column <= value)

    paginated = query.order_by(Car.date_posted.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "items": [_serialize_car(c) for c in paginated.items],
        "page": paginated.page,
        "per_page": paginated.per_page,
        "total": paginated.total,
        "pages": paginated.pages,
    })


@api_bp.route("/cars/<car_pid:car_id>", methods=["GET"])
def get_car(car_id):
    car = Car.query.get_or_404(car_id)
    if car.is_taken_down:
        abort(404)
    payload = car.to_dict(include_seller=True)
    payload["photos"] = [_abs_url(n) for n in payload.get("photos", [])]
    if payload.get("primary_photo"):
        payload["primary_photo"] = _abs_url(payload["primary_photo"])
    return jsonify(payload)


@api_bp.route("/favorites", methods=["GET"])
@login_required
def list_favorites():
    favorites = (
        Favorite.query.filter_by(user_id=current_user.id)
        .order_by(Favorite.date_added.desc())
        .all()
    )
    return jsonify({
        "items": [
            {
                "favorite_id": fav.id,
                "date_added": fav.date_added.isoformat(),
                "car": _serialize_car(fav.car) if fav.car else None,
            }
            for fav in favorites if fav.car is not None
        ]
    })


@api_bp.route("/favorites/<car_pid:car_id>", methods=["POST"])
@login_required
def add_favorite(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id == current_user.id:
        abort(400, description="Cannot favorite your own listing.")

    existing = Favorite.query.filter_by(user_id=current_user.id, car_id=car_id).first()
    if existing:
        return jsonify({"status": "ok", "favorited": True, "already": True})

    db.session.add(Favorite(user_id=current_user.id, car_id=car_id))
    db.session.commit()
    return jsonify({"status": "ok", "favorited": True}), 201


@api_bp.route("/favorites/<car_pid:car_id>", methods=["DELETE"])
@login_required
def remove_favorite(car_id):
    favorite = Favorite.query.filter_by(user_id=current_user.id, car_id=car_id).first()
    if not favorite:
        return jsonify({"status": "ok", "favorited": False, "already": True})

    db.session.delete(favorite)
    db.session.commit()
    return jsonify({"status": "ok", "favorited": False})


@api_bp.errorhandler(404)
def _api_not_found(_error):
    return jsonify({"error": "not found"}), 404


@api_bp.errorhandler(400)
def _api_bad_request(error):
    description = getattr(error, "description", "bad request")
    return jsonify({"error": description}), 400


@api_bp.errorhandler(401)
def _api_unauthorized(_error):
    return jsonify({"error": "authentication required"}), 401
