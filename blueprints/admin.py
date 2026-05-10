"""Admin moderation dashboard."""

import csv
import io
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta

from flask import (
    Blueprint, Response, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from decorators import admin_required
from extensions import db
from forms import ReportReviewForm
from models import Car, CarView, Notification, Offer, Report, TestDrive, User


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
@login_required
def _require_admin_for_all():
    if not current_user.is_admin:
        abort(403)


@admin_bp.route("/")
def dashboard():
    today = date.today()
    sold_count = Car.query.filter_by(is_sold=True).count()
    total_cars = Car.query.count()
    sold_pct = (sold_count / total_cars * 100.0) if total_cars else 0.0

    stats = {
        "users": User.query.count(),
        "cars": total_cars,
        "active_cars": Car.query.filter_by(is_sold=False, is_taken_down=False).count(),
        "sold_cars": sold_count,
        "sold_pct": sold_pct,
        "open_reports": Report.query.filter_by(status=Report.STATUS_OPEN).count(),
        "offers": Offer.query.count(),
        "test_drives": TestDrive.query.count(),
        "views_today": CarView.query.filter_by(viewed_date=today).count(),
        "total_views": CarView.query.count(),
    }
    recent_reports = (
        Report.query.order_by(Report.created_at.desc()).limit(5).all()
    )
    return render_template("admin/dashboard.html", stats=stats, recent_reports=recent_reports)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


def _listings_per_day(days=30):
    """Return an ordered dict {date: count} for the last N days, including zeros."""

    start = date.today() - timedelta(days=days - 1)
    start_dt = datetime.combine(start, datetime.min.time())
    rows = (
        db.session.query(Car.date_posted)
        .filter(Car.date_posted >= start_dt)
        .all()
    )
    bucket = OrderedDict()
    for offset in range(days):
        bucket[(start + timedelta(days=offset)).isoformat()] = 0
    for (posted,) in rows:
        if not posted:
            continue
        key = posted.date().isoformat()
        if key in bucket:
            bucket[key] += 1
    return bucket


def _top_makes(limit=10):
    rows = (
        db.session.query(Car.make, func.count(Car.id))
        .group_by(Car.make)
        .order_by(func.count(Car.id).desc())
        .limit(limit)
        .all()
    )
    return [{"make": r[0] or "Unknown", "count": r[1]} for r in rows]


def _conversion_to_sold():
    total = Car.query.count()
    sold = Car.query.filter_by(is_sold=True).count()
    active = Car.query.filter_by(is_sold=False, is_taken_down=False).count()
    taken_down = Car.query.filter_by(is_taken_down=True).count()
    pct = (sold / total * 100.0) if total else 0.0
    return {
        "total": total,
        "sold": sold,
        "active": active,
        "taken_down": taken_down,
        "sold_pct": round(pct, 2),
    }


def _views_per_day(days=30):
    start = date.today() - timedelta(days=days - 1)
    rows = (
        db.session.query(CarView.viewed_date)
        .filter(CarView.viewed_date >= start)
        .all()
    )
    counts = Counter(r[0].isoformat() for r in rows if r[0])
    bucket = OrderedDict()
    for offset in range(days):
        key = (start + timedelta(days=offset)).isoformat()
        bucket[key] = counts.get(key, 0)
    return bucket


def _most_viewed_cars(limit=5):
    return (
        Car.query.filter_by(is_taken_down=False)
        .order_by(Car.view_count.desc())
        .limit(limit)
        .all()
    )


@admin_bp.route("/analytics")
def analytics():
    listings = _listings_per_day(30)
    views = _views_per_day(30)
    return render_template(
        "admin/analytics.html",
        listings_per_day=listings,
        views_per_day=views,
        top_makes=_top_makes(10),
        conversion=_conversion_to_sold(),
        most_viewed=_most_viewed_cars(5),
    )


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------


def _csv_response(filename, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    response = Response(buf.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@admin_bp.route("/export/cars.csv")
def export_cars():
    cars = Car.query.order_by(Car.date_posted.desc()).all()
    header = [
        "id", "make", "model", "year", "price", "mileage", "color", "fuel_type",
        "transmission", "location", "is_sold", "is_taken_down", "view_count",
        "owner_email", "date_posted",
    ]
    rows = [
        [
            c.id, c.make, c.model, c.year, c.price, c.mileage, c.color, c.fuel_type,
            c.transmission, c.location, int(bool(c.is_sold)), int(bool(c.is_taken_down)),
            c.view_count or 0,
            c.owner.email if c.owner else c.seller_email,
            c.date_posted.isoformat() if c.date_posted else "",
        ]
        for c in cars
    ]
    return _csv_response("cars.csv", header, rows)


@admin_bp.route("/export/users.csv")
def export_users():
    users = User.query.order_by(User.date_created.desc()).all()
    header = ["id", "full_name", "email", "phone", "location", "is_admin", "listings", "date_created"]
    rows = [
        [
            u.id, u.full_name, u.email, u.phone or "", u.location or "",
            int(bool(u.is_admin)), len(u.cars) if u.cars else 0,
            u.date_created.isoformat() if u.date_created else "",
        ]
        for u in users
    ]
    return _csv_response("users.csv", header, rows)


@admin_bp.route("/export/reports.csv")
def export_reports():
    reports = Report.query.order_by(Report.created_at.desc()).all()
    header = [
        "id", "car_id", "car", "reason", "status", "reporter_email",
        "reviewer_email", "reviewed_at", "details", "created_at",
    ]
    rows = [
        [
            r.id,
            r.car_id,
            f"{r.car.year} {r.car.make} {r.car.model}" if r.car else "",
            r.reason,
            r.status,
            r.reporter.email if r.reporter else "",
            r.reviewer.email if r.reviewer else "",
            r.reviewed_at.isoformat() if r.reviewed_at else "",
            (r.details or "").replace("\n", " "),
            r.created_at.isoformat() if r.created_at else "",
        ]
        for r in reports
    ]
    return _csv_response("reports.csv", header, rows)


@admin_bp.route("/reports")
def reports():
    status = request.args.get("status", Report.STATUS_OPEN)
    query = Report.query
    if status and status != "all":
        query = query.filter_by(status=status)
    items = query.order_by(Report.created_at.desc()).all()
    return render_template("admin/reports.html", reports=items, current_status=status)


@admin_bp.route("/reports/<report_pid:report_id>", methods=["GET", "POST"])
def report_detail(report_id):
    report = Report.query.get_or_404(report_id)
    form = ReportReviewForm(obj=report)
    return render_template("admin/report_detail.html", report=report, form=form)


@admin_bp.route("/reports/<report_pid:report_id>/<string:action>", methods=["POST"])
def report_action(report_id, action):
    report = Report.query.get_or_404(report_id)
    form = ReportReviewForm()

    if action == "dismiss":
        report.status = Report.STATUS_DISMISSED
    elif action == "review":
        report.status = Report.STATUS_REVIEWED
    elif action == "takedown":
        report.status = Report.STATUS_ACTIONED
        if report.car:
            report.car.is_taken_down = True
            if report.car.user_id:
                Notification.push(
                    user_id=report.car.user_id,
                    title=f"Listing taken down: {report.car.year} {report.car.make} {report.car.model}",
                    body=f"Reason: {report.reason_label}",
                    link=url_for("main.my_listings"),
                )
    elif action == "restore":
        report.status = Report.STATUS_REVIEWED
        if report.car:
            report.car.is_taken_down = False
    else:
        abort(400)

    if form.validate_on_submit():
        report.review_note = form.review_note.data or None

    report.reviewed_at = datetime.utcnow()
    report.reviewed_by_id = current_user.id
    db.session.commit()
    flash(f"Report marked as {report.status}.", "info")
    return redirect(url_for("admin.reports"))


@admin_bp.route("/users")
def users():
    items = User.query.order_by(User.date_created.desc()).all()
    return render_template("admin/users.html", users=items)


@admin_bp.route("/users/<user_pid:user_id>/toggle-admin", methods=["POST"])
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot change your own admin status.", "warning")
        return redirect(url_for("admin.users"))
    user.is_admin = not user.is_admin
    db.session.commit()
    flash(
        f"{user.email} {'is now an admin' if user.is_admin else 'is no longer an admin'}.",
        "info",
    )
    return redirect(url_for("admin.users"))


@admin_bp.route("/cars")
def cars():
    show = request.args.get("show", "all")
    query = Car.query
    if show == "taken_down":
        query = query.filter_by(is_taken_down=True)
    elif show == "active":
        query = query.filter_by(is_taken_down=False, is_sold=False)
    items = query.order_by(Car.date_posted.desc()).limit(200).all()
    return render_template("admin/cars.html", cars=items, show=show)


@admin_bp.route("/cars/<car_pid:car_id>/toggle-takedown", methods=["POST"])
def toggle_takedown(car_id):
    car = Car.query.get_or_404(car_id)
    car.is_taken_down = not car.is_taken_down
    if car.is_taken_down and car.user_id:
        Notification.push(
            user_id=car.user_id,
            title=f"Listing taken down: {car.year} {car.make} {car.model}",
            body="An admin removed your listing from public view.",
            link=url_for("main.my_listings"),
        )
    db.session.commit()
    flash(
        f"Listing {'hidden' if car.is_taken_down else 'restored'}.",
        "info",
    )
    return redirect(url_for("admin.cars", show=request.args.get("show", "all")))
