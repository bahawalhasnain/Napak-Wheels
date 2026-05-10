"""Make-an-offer / negotiation flow."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from forms import CounterOfferForm, OfferForm
from models import Car, Notification, Offer


offers_bp = Blueprint("offers", __name__, url_prefix="/offers")


def _notify(user_id, title, body, offer_id):
    Notification.push(
        user_id=user_id,
        title=title,
        body=body,
        link=url_for("offers.detail", offer_id=offer_id),
    )


@offers_bp.route("/new/<car_pid:car_id>", methods=["GET", "POST"])
@login_required
def new(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id is None or car.user_id == current_user.id:
        abort(403)
    if car.is_sold or car.is_taken_down:
        flash("This listing is no longer available.", "warning")
        return redirect(url_for("main.car_detail", id=car_id))

    form = OfferForm()
    if form.validate_on_submit():
        offer = Offer(
            car_id=car.id,
            buyer_id=current_user.id,
            seller_id=car.user_id,
            amount=form.amount.data,
            note=(form.note.data or None),
            proposed_by=Offer.PROPOSED_BUYER,
            status=Offer.STATUS_PENDING,
        )
        db.session.add(offer)
        db.session.flush()
        _notify(
            user_id=car.user_id,
            title=f"New offer on {car.year} {car.make} {car.model}",
            body=f"{offer.formatted_amount} from {current_user.full_name}",
            offer_id=offer.id,
        )
        db.session.commit()
        flash("Offer submitted.", "success")
        return redirect(url_for("offers.detail", offer_id=offer.id))

    return render_template("offers/new.html", form=form, car=car)


@offers_bp.route("/sent")
@login_required
def sent():
    items = (
        Offer.query.filter_by(buyer_id=current_user.id)
        .order_by(Offer.created_at.desc())
        .all()
    )
    return render_template("offers/list.html", offers=items, mode="sent")


@offers_bp.route("/received")
@login_required
def received():
    items = (
        Offer.query.filter_by(seller_id=current_user.id)
        .order_by(Offer.created_at.desc())
        .all()
    )
    return render_template("offers/list.html", offers=items, mode="received")


@offers_bp.route("/<offer_pid:offer_id>", methods=["GET", "POST"])
@login_required
def detail(offer_id):
    offer = Offer.query.get_or_404(offer_id)
    if current_user.id not in (offer.buyer_id, offer.seller_id):
        abort(403)

    history = _build_history(offer)
    counter_form = CounterOfferForm()
    return render_template(
        "offers/detail.html",
        offer=offer,
        history=history,
        counter_form=counter_form,
        is_seller=current_user.id == offer.seller_id,
    )


def _build_history(offer):
    chain = []
    seen = set()
    cursor = offer
    while cursor and cursor.id not in seen:
        seen.add(cursor.id)
        chain.append(cursor)
        cursor = cursor.parent
    chain.reverse()

    head = offer
    while head.children:
        head = max(head.children, key=lambda c: c.created_at)
        if head.id in seen:
            break
        seen.add(head.id)
        chain.append(head)
    return chain


def _ensure_open(offer):
    if not offer.is_open:
        flash("This offer has already been resolved.", "warning")
        return False
    return True


@offers_bp.route("/<offer_pid:offer_id>/accept", methods=["POST"])
@login_required
def accept(offer_id):
    offer = Offer.query.get_or_404(offer_id)
    if current_user.id != offer.seller_id:
        abort(403)
    if not _ensure_open(offer):
        return redirect(url_for("offers.detail", offer_id=offer.id))

    offer.status = Offer.STATUS_ACCEPTED
    offer.car.is_sold = True
    _notify(
        user_id=offer.buyer_id,
        title=f"Offer accepted: {offer.car.year} {offer.car.make} {offer.car.model}",
        body=f"Your offer of {offer.formatted_amount} was accepted.",
        offer_id=offer.id,
    )
    db.session.commit()
    flash("Offer accepted. Listing marked as sold.", "success")
    return redirect(url_for("offers.detail", offer_id=offer.id))


@offers_bp.route("/<offer_pid:offer_id>/reject", methods=["POST"])
@login_required
def reject(offer_id):
    offer = Offer.query.get_or_404(offer_id)
    if current_user.id != offer.seller_id:
        abort(403)
    if not _ensure_open(offer):
        return redirect(url_for("offers.detail", offer_id=offer.id))

    offer.status = Offer.STATUS_REJECTED
    _notify(
        user_id=offer.buyer_id,
        title=f"Offer rejected: {offer.car.year} {offer.car.make} {offer.car.model}",
        body=f"Your offer of {offer.formatted_amount} was rejected.",
        offer_id=offer.id,
    )
    db.session.commit()
    flash("Offer rejected.", "info")
    return redirect(url_for("offers.detail", offer_id=offer.id))


@offers_bp.route("/<offer_pid:offer_id>/withdraw", methods=["POST"])
@login_required
def withdraw(offer_id):
    offer = Offer.query.get_or_404(offer_id)
    if current_user.id != offer.buyer_id:
        abort(403)
    if not _ensure_open(offer):
        return redirect(url_for("offers.detail", offer_id=offer.id))

    offer.status = Offer.STATUS_WITHDRAWN
    _notify(
        user_id=offer.seller_id,
        title=f"Offer withdrawn: {offer.car.year} {offer.car.make} {offer.car.model}",
        body="The buyer withdrew their offer.",
        offer_id=offer.id,
    )
    db.session.commit()
    flash("Offer withdrawn.", "info")
    return redirect(url_for("offers.detail", offer_id=offer.id))


@offers_bp.route("/<offer_pid:offer_id>/counter", methods=["POST"])
@login_required
def counter(offer_id):
    parent = Offer.query.get_or_404(offer_id)
    if current_user.id not in (parent.buyer_id, parent.seller_id):
        abort(403)
    if not _ensure_open(parent):
        return redirect(url_for("offers.detail", offer_id=parent.id))

    form = CounterOfferForm()
    if not form.validate_on_submit():
        flash("Please enter a valid counter-offer amount.", "danger")
        return redirect(url_for("offers.detail", offer_id=parent.id))

    proposer_is_seller = current_user.id == parent.seller_id
    new_offer = Offer(
        car_id=parent.car_id,
        buyer_id=parent.buyer_id,
        seller_id=parent.seller_id,
        amount=form.amount.data,
        note=(form.note.data or None),
        proposed_by=(Offer.PROPOSED_SELLER if proposer_is_seller else Offer.PROPOSED_BUYER),
        parent_offer_id=parent.id,
        status=Offer.STATUS_PENDING,
    )
    parent.status = Offer.STATUS_COUNTERED
    db.session.add(new_offer)
    db.session.flush()

    recipient_id = parent.buyer_id if proposer_is_seller else parent.seller_id
    _notify(
        user_id=recipient_id,
        title=f"Counter-offer on {parent.car.year} {parent.car.make} {parent.car.model}",
        body=f"New counter: {new_offer.formatted_amount}",
        offer_id=new_offer.id,
    )
    db.session.commit()
    flash("Counter-offer sent.", "success")
    return redirect(url_for("offers.detail", offer_id=new_offer.id))
