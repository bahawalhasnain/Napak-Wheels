"""Test-drive booking flow."""

from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from extensions import db
from forms import TestDriveRequestForm, TestDriveResponseForm
from models import Car, Notification, TestDrive


test_drives_bp = Blueprint("test_drives", __name__, url_prefix="/test-drives")


def _notify(user_id, title, body, drive_id):
    Notification.push(
        user_id=user_id,
        title=title,
        body=body,
        link=url_for("test_drives.detail", drive_id=drive_id),
    )


@test_drives_bp.route("/sent")
@login_required
def sent():
    items = (
        TestDrive.query.filter_by(buyer_id=current_user.id)
        .order_by(TestDrive.requested_at.desc())
        .all()
    )
    return render_template("test_drives/list.html", drives=items, mode="sent")


@test_drives_bp.route("/received")
@login_required
def received():
    items = (
        TestDrive.query.filter_by(seller_id=current_user.id)
        .order_by(TestDrive.requested_at.desc())
        .all()
    )
    return render_template("test_drives/list.html", drives=items, mode="received")


@test_drives_bp.route("/new/<int:car_id>", methods=["GET", "POST"])
@login_required
def new(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id is None or car.user_id == current_user.id:
        abort(403)
    if car.is_sold or car.is_taken_down:
        flash("This listing is no longer available.", "warning")
        return redirect(url_for("main.car_detail", id=car_id))

    form = TestDriveRequestForm()
    if form.validate_on_submit():
        if form.requested_at.data <= datetime.utcnow():
            flash("Please pick a future date and time.", "danger")
            return render_template("test_drives/new.html", form=form, car=car)

        drive = TestDrive(
            car_id=car.id,
            buyer_id=current_user.id,
            seller_id=car.user_id,
            requested_at=form.requested_at.data,
            duration_minutes=form.duration_minutes.data,
            location=(form.location.data or car.location),
            message=(form.message.data or None),
            status=TestDrive.STATUS_REQUESTED,
        )
        db.session.add(drive)
        db.session.flush()
        _notify(
            user_id=car.user_id,
            title=f"Test drive request: {car.year} {car.make} {car.model}",
            body=f"Requested for {drive.requested_at.strftime('%Y-%m-%d %H:%M')}",
            drive_id=drive.id,
        )
        db.session.commit()
        flash("Test drive requested.", "success")
        return redirect(url_for("test_drives.detail", drive_id=drive.id))

    return render_template("test_drives/new.html", form=form, car=car)


@test_drives_bp.route("/<int:drive_id>", methods=["GET"])
@login_required
def detail(drive_id):
    drive = TestDrive.query.get_or_404(drive_id)
    if current_user.id not in (drive.buyer_id, drive.seller_id):
        abort(403)
    return render_template(
        "test_drives/detail.html",
        drive=drive,
        is_seller=current_user.id == drive.seller_id,
        response_form=TestDriveResponseForm(),
    )


def _seller_action(drive_id, status, message):
    drive = TestDrive.query.get_or_404(drive_id)
    if current_user.id != drive.seller_id:
        abort(403)

    form = TestDriveResponseForm()
    if form.validate_on_submit():
        drive.seller_response = form.seller_response.data or None
    drive.status = status
    _notify(
        user_id=drive.buyer_id,
        title=f"Test drive {status}: {drive.car.year} {drive.car.make} {drive.car.model}",
        body=message,
        drive_id=drive.id,
    )
    db.session.commit()
    flash(message, "info")
    return redirect(url_for("test_drives.detail", drive_id=drive.id))


@test_drives_bp.route("/<int:drive_id>/confirm", methods=["POST"])
@login_required
def confirm(drive_id):
    return _seller_action(drive_id, TestDrive.STATUS_CONFIRMED, "Test drive confirmed.")


@test_drives_bp.route("/<int:drive_id>/decline", methods=["POST"])
@login_required
def decline(drive_id):
    return _seller_action(drive_id, TestDrive.STATUS_DECLINED, "Test drive declined.")


@test_drives_bp.route("/<int:drive_id>/complete", methods=["POST"])
@login_required
def complete(drive_id):
    return _seller_action(drive_id, TestDrive.STATUS_COMPLETED, "Test drive marked completed.")


@test_drives_bp.route("/<int:drive_id>/cancel", methods=["POST"])
@login_required
def cancel(drive_id):
    drive = TestDrive.query.get_or_404(drive_id)
    if current_user.id != drive.buyer_id:
        abort(403)
    drive.status = TestDrive.STATUS_CANCELLED
    _notify(
        user_id=drive.seller_id,
        title=f"Test drive cancelled: {drive.car.year} {drive.car.make} {drive.car.model}",
        body="The buyer cancelled the request.",
        drive_id=drive.id,
    )
    db.session.commit()
    flash("Test drive cancelled.", "info")
    return redirect(url_for("test_drives.detail", drive_id=drive.id))
