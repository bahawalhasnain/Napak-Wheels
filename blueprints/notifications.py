"""In-app notification list + read tracking."""

from datetime import datetime

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import Notification


notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
def list_notifications():
    items = (
        current_user.notifications.order_by(Notification.created_at.desc()).limit(100).all()
    )
    now = datetime.utcnow()
    changed = False
    for n in items:
        if n.read_at is None:
            n.read_at = now
            changed = True
    if changed:
        db.session.commit()
    return render_template("notifications/list.html", notifications=items)


@notifications_bp.route("/<notif_pid:notif_id>/open")
@login_required
def open_notification(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        return redirect(url_for("notifications.list_notifications"))
    if notif.read_at is None:
        notif.read_at = datetime.utcnow()
        db.session.commit()
    return redirect(notif.link or url_for("notifications.list_notifications"))


@notifications_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    now = datetime.utcnow()
    current_user.notifications.filter(Notification.read_at.is_(None)).update(
        {"read_at": now}, synchronize_session=False
    )
    db.session.commit()
    return redirect(request.referrer or url_for("notifications.list_notifications"))
