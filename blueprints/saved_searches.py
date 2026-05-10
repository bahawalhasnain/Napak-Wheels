"""Saved searches and email alerts."""

import json

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from forms import SavedSearchForm
from models import SavedSearch


saved_searches_bp = Blueprint("saved_searches", __name__, url_prefix="/saved-searches")


SEARCH_FILTER_KEYS = [
    "search", "make", "min_price", "max_price",
    "min_year", "max_year", "fuel_type", "location",
]


def _params_from_query(args):
    cleaned = {}
    for key in SEARCH_FILTER_KEYS:
        value = (args.get(key) or "").strip()
        if value:
            cleaned[key] = value
    return cleaned


@saved_searches_bp.route("/")
@login_required
def list_searches():
    items = (
        SavedSearch.query.filter_by(user_id=current_user.id)
        .order_by(SavedSearch.created_at.desc())
        .all()
    )
    return render_template("saved_searches/list.html", items=items)


@saved_searches_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        form = SavedSearchForm()
        params_raw = request.form.get("params") or "{}"
        try:
            params_dict = json.loads(params_raw)
            if not isinstance(params_dict, dict):
                params_dict = {}
        except Exception:
            params_dict = {}

        if form.validate_on_submit():
            ss = SavedSearch(
                user_id=current_user.id,
                name=form.name.data.strip(),
                params=json.dumps(params_dict),
                alerts_enabled=bool(form.alerts_enabled.data),
            )
            db.session.add(ss)
            db.session.commit()
            flash("Saved search created.", "success")
            return redirect(url_for("saved_searches.list_searches"))
    else:
        form = SavedSearchForm()
        params_dict = _params_from_query(request.args)

    return render_template(
        "saved_searches/new.html",
        form=form,
        params_dict=params_dict,
        params_json=json.dumps(params_dict),
    )


@saved_searches_bp.route("/<int:search_id>/delete", methods=["POST"])
@login_required
def delete(search_id):
    ss = SavedSearch.query.get_or_404(search_id)
    if ss.user_id != current_user.id:
        abort(403)
    db.session.delete(ss)
    db.session.commit()
    flash("Saved search deleted.", "info")
    return redirect(url_for("saved_searches.list_searches"))


@saved_searches_bp.route("/<int:search_id>/toggle", methods=["POST"])
@login_required
def toggle(search_id):
    ss = SavedSearch.query.get_or_404(search_id)
    if ss.user_id != current_user.id:
        abort(403)
    ss.alerts_enabled = not ss.alerts_enabled
    db.session.commit()
    flash(
        "Email alerts enabled." if ss.alerts_enabled else "Email alerts paused.",
        "info",
    )
    return redirect(url_for("saved_searches.list_searches"))
