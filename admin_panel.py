"""Flask-Admin power tools.

Mounts a Flask-Admin instance at ``/admin/db`` providing low-level CRUD on every
model. The curated moderation dashboard at ``/admin`` (admin blueprint) is the
primary surface; this is for power-admins who need raw access.

Access is restricted to authenticated users with ``is_admin = True``.
"""

from __future__ import annotations

from flask import Flask, abort, redirect, request, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user

from extensions import db
from models import (
    Car, CarImage, CarView, Conversation, Favorite, Message, Notification,
    Offer, Report, SavedSearch, TestDrive, User,
)


class _SecureMixin:
    """Restrict access to authenticated admins."""

    def is_accessible(self):
        return current_user.is_authenticated and getattr(current_user, "is_admin", False)

    def inaccessible_callback(self, name, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("main.login", next=request.url))
        abort(403)


class SecureModelView(_SecureMixin, ModelView):
    page_size = 50
    can_export = True
    column_display_pk = True


class SecureIndexView(_SecureMixin, AdminIndexView):
    @expose("/")
    def index(self):
        if not self.is_accessible():
            return self.inaccessible_callback("index")
        return self.render("admin/db_index.html")


class UserAdminView(SecureModelView):
    column_list = ("id", "full_name", "email", "phone", "location", "is_admin", "date_created")
    column_searchable_list = ("full_name", "email", "phone", "location")
    column_filters = ("is_admin", "location")
    form_excluded_columns = ("password_hash", "cars", "favorites", "saved_searches", "notifications")


class CarAdminView(SecureModelView):
    column_list = (
        "id", "make", "model", "year", "price", "location", "owner",
        "is_sold", "is_taken_down", "view_count", "date_posted",
    )
    column_searchable_list = ("make", "model", "location", "seller_name", "seller_email")
    column_filters = ("is_sold", "is_taken_down", "fuel_type", "transmission", "make")
    column_default_sort = ("date_posted", True)
    form_excluded_columns = (
        "images", "favorited_by", "conversations", "offers", "test_drives",
        "reports", "views",
    )


class ReportAdminView(SecureModelView):
    column_list = ("id", "car", "reason", "status", "reporter", "reviewer", "created_at")
    column_filters = ("status", "reason")
    column_default_sort = ("created_at", True)


class OfferAdminView(SecureModelView):
    column_list = ("id", "car", "buyer", "seller", "amount", "status", "proposed_by", "created_at")
    column_filters = ("status", "proposed_by")
    column_default_sort = ("created_at", True)


class TestDriveAdminView(SecureModelView):
    column_list = ("id", "car", "buyer", "seller", "requested_at", "status", "created_at")
    column_filters = ("status",)
    column_default_sort = ("requested_at", True)


class CarViewAdminView(SecureModelView):
    column_list = ("id", "car", "user", "session_key", "viewed_date", "viewed_at")
    column_filters = ("viewed_date",)
    column_default_sort = ("viewed_at", True)
    can_create = False
    can_edit = False


def init_admin_panel(app: Flask) -> Admin:
    """Mount Flask-Admin at ``/admin/db`` and register model views."""

    admin = Admin(
        app,
        name="Napak Wheels DB",
        url="/admin/db",
        endpoint="admin_db",
        index_view=SecureIndexView(url="/admin/db", endpoint="admin_db"),
    )

    admin.add_view(UserAdminView(User, db.session, name="Users", category="People"))
    admin.add_view(CarAdminView(Car, db.session, name="Cars", category="Listings"))
    admin.add_view(SecureModelView(CarImage, db.session, name="Car images", category="Listings"))
    admin.add_view(SecureModelView(Favorite, db.session, name="Favorites", category="Engagement"))
    admin.add_view(CarViewAdminView(CarView, db.session, name="Car views", category="Engagement"))
    admin.add_view(SecureModelView(Conversation, db.session, name="Conversations", category="Messaging"))
    admin.add_view(SecureModelView(Message, db.session, name="Messages", category="Messaging"))
    admin.add_view(OfferAdminView(Offer, db.session, name="Offers", category="Negotiation"))
    admin.add_view(TestDriveAdminView(TestDrive, db.session, name="Test drives", category="Negotiation"))
    admin.add_view(SecureModelView(SavedSearch, db.session, name="Saved searches", category="Engagement"))
    admin.add_view(ReportAdminView(Report, db.session, name="Reports", category="Moderation"))
    admin.add_view(SecureModelView(Notification, db.session, name="Notifications", category="Messaging"))

    return admin
