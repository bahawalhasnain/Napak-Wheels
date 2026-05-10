"""Profile + Settings (account, security, notifications, danger zone)."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from forms import (
    ChangePasswordForm,
    DeleteAccountForm,
    NotificationPrefsForm,
    ProfileForm,
)
from models import (
    Car,
    Conversation,
    Favorite,
    Notification,
    Offer,
    SavedSearch,
    User,
)


account_bp = Blueprint("account", __name__, url_prefix="/account")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def _profile_stats(user):
    return {
        "listings": Car.query.filter_by(user_id=user.id).count(),
        "active_listings": Car.query.filter_by(
            user_id=user.id, is_sold=False, is_taken_down=False
        ).count(),
        "sold_listings": Car.query.filter_by(user_id=user.id, is_sold=True).count(),
        "favorites": Favorite.query.filter_by(user_id=user.id).count(),
        "saved_searches": SavedSearch.query.filter_by(user_id=user.id).count(),
        "offers_made": Offer.query.filter_by(buyer_id=user.id).count(),
        "offers_received": Offer.query.filter_by(seller_id=user.id).count(),
        "conversations": Conversation.query.filter(
            (Conversation.buyer_id == user.id) | (Conversation.seller_id == user.id)
        ).count(),
    }


@account_bp.route("/profile")
@login_required
def profile():
    stats = _profile_stats(current_user)
    recent_listings = (
        Car.query.filter_by(user_id=current_user.id)
        .order_by(Car.date_posted.desc())
        .limit(3)
        .all()
    )
    recent_favorites = (
        Favorite.query.filter_by(user_id=current_user.id)
        .order_by(Favorite.date_added.desc())
        .limit(3)
        .all()
    )
    return render_template(
        "account/profile.html",
        stats=stats,
        recent_listings=recent_listings,
        recent_favorites=[f.car for f in recent_favorites if f.car],
    )


# ---------------------------------------------------------------------------
# Settings (tabbed)
# ---------------------------------------------------------------------------


@account_bp.route("/settings")
@login_required
def settings():
    return redirect(url_for("account.settings_account"))


@account_bp.route("/settings/account", methods=["GET", "POST"])
@login_required
def settings_account():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        new_email = form.email.data.strip().lower()
        if new_email != current_user.email:
            existing = User.query.filter_by(email=new_email).first()
            if existing and existing.id != current_user.id:
                flash("That email is already in use.", "danger")
                return render_template(
                    "account/settings_account.html", form=form, active_tab="account"
                )
            current_user.email = new_email
        current_user.full_name = form.full_name.data.strip()
        current_user.phone = (form.phone.data or "").strip() or None
        current_user.location = (form.location.data or "").strip() or None
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("account.settings_account"))

    return render_template(
        "account/settings_account.html", form=form, active_tab="account"
    )


@account_bp.route("/settings/security", methods=["GET", "POST"])
@login_required
def settings_security():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not check_password_hash(
            current_user.password_hash, form.current_password.data
        ):
            flash("Your current password is incorrect.", "danger")
        elif form.new_password.data == form.current_password.data:
            flash("New password must differ from current password.", "warning")
        else:
            current_user.password_hash = generate_password_hash(form.new_password.data)
            db.session.commit()
            flash("Password updated. Please use it next time you sign in.", "success")
            return redirect(url_for("account.settings_security"))

    return render_template(
        "account/settings_security.html", form=form, active_tab="security"
    )


@account_bp.route("/settings/notifications", methods=["GET", "POST"])
@login_required
def settings_notifications():
    # Pass formdata explicitly on POST so Flask-WTF doesn't bail out when the
    # request body is "empty" except for the csrf_token (an unchecked checkbox
    # submits as a missing field, which is the whole point of the toggle).
    form = NotificationPrefsForm(
        formdata=request.form if request.method == "POST" else None,
        obj=current_user,
    )

    unread_count = current_user.unread_notification_count()
    saved_search_count = SavedSearch.query.filter_by(user_id=current_user.id).count()
    saved_with_alerts = (
        SavedSearch.query.filter_by(user_id=current_user.id, alerts_enabled=True).count()
    )

    if form.validate_on_submit():
        current_user.email_alerts_enabled = bool(form.email_alerts_enabled.data)
        db.session.commit()
        flash("Notification preferences saved.", "success")
        return redirect(url_for("account.settings_notifications"))

    return render_template(
        "account/settings_notifications.html",
        form=form,
        active_tab="notifications",
        unread_count=unread_count,
        saved_search_count=saved_search_count,
        saved_with_alerts=saved_with_alerts,
    )


@account_bp.route("/settings/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_notifications_read():
    from datetime import datetime

    Notification.query.filter_by(user_id=current_user.id, read_at=None).update(
        {Notification.read_at: datetime.utcnow()}, synchronize_session=False
    )
    db.session.commit()
    flash("All notifications marked as read.", "info")
    return redirect(url_for("account.settings_notifications"))


@account_bp.route("/settings/danger", methods=["GET", "POST"])
@login_required
def settings_danger():
    """Deactivate account: take down all user's listings, clear personal data
    that can be cleared without breaking FK constraints, and log out.

    A hard delete is intentionally avoided — conversations, offers, test drives,
    and reports reference the user via foreign keys. Production apps almost
    always do this kind of soft-delete + grace period.
    """

    form = DeleteAccountForm()
    if form.validate_on_submit():
        if (form.confirm_text.data or "").strip() != "DELETE":
            flash('You must type "DELETE" exactly (in capital letters) to confirm.', "danger")
        elif not check_password_hash(
            current_user.password_hash, form.confirm_password.data
        ):
            flash("Password is incorrect.", "danger")
        else:
            Car.query.filter_by(user_id=current_user.id).update(
                {"is_taken_down": True}, synchronize_session=False
            )
            SavedSearch.query.filter_by(user_id=current_user.id).update(
                {"alerts_enabled": False}, synchronize_session=False
            )
            current_user.email_alerts_enabled = False
            db.session.commit()
            logout_user()
            flash(
                "Your account has been deactivated. All listings are hidden and "
                "alerts are off. Contact support to fully delete your data.",
                "info",
            )
            return redirect(url_for("main.index"))

    return render_template(
        "account/settings_danger.html", form=form, active_tab="danger"
    )
