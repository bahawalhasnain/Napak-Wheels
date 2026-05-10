"""Report a listing for moderation."""

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from extensions import db
from forms import ReportForm
from models import Car, Report


reports_bp = Blueprint("reports", __name__, url_prefix="/report")


@reports_bp.route("/<int:car_id>", methods=["GET", "POST"])
@login_required
def new(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id == current_user.id:
        abort(403)

    form = ReportForm()
    if form.validate_on_submit():
        report = Report(
            car_id=car.id,
            reporter_id=current_user.id,
            reason=form.reason.data,
            details=(form.details.data or None),
            status=Report.STATUS_OPEN,
        )
        db.session.add(report)
        db.session.commit()
        flash("Thanks. The listing has been reported and will be reviewed.", "success")
        return redirect(url_for("main.car_detail", id=car.id))

    return render_template("reports/new.html", form=form, car=car)
