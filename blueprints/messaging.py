"""In-app messaging between buyer and seller."""

from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from forms import MessageForm
from models import Car, Conversation, Message, Notification


messaging_bp = Blueprint("messaging", __name__, url_prefix="/messages")


@messaging_bp.route("/")
@login_required
def inbox():
    threads = (
        Conversation.query.filter(
            db.or_(
                Conversation.buyer_id == current_user.id,
                Conversation.seller_id == current_user.id,
            )
        )
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return render_template("messaging/inbox.html", threads=threads)


@messaging_bp.route("/start/<car_pid:car_id>", methods=["GET", "POST"])
@login_required
def start(car_id):
    car = Car.query.get_or_404(car_id)
    if car.user_id is None:
        flash("This listing has no owner to message.", "warning")
        return redirect(url_for("main.car_detail", id=car_id))
    if car.user_id == current_user.id:
        flash("You cannot message yourself.", "warning")
        return redirect(url_for("main.car_detail", id=car_id))

    convo = Conversation.query.filter_by(car_id=car.id, buyer_id=current_user.id).first()
    if convo is None:
        convo = Conversation(
            car_id=car.id,
            buyer_id=current_user.id,
            seller_id=car.user_id,
        )
        db.session.add(convo)
        db.session.commit()
    return redirect(url_for("messaging.thread", conversation_id=convo.id))


@messaging_bp.route("/<convo_pid:conversation_id>", methods=["GET", "POST"])
@login_required
def thread(conversation_id):
    convo = Conversation.query.get_or_404(conversation_id)
    if current_user.id not in (convo.buyer_id, convo.seller_id):
        abort(403)

    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(
            conversation_id=convo.id,
            sender_id=current_user.id,
            body=form.body.data.strip(),
        )
        db.session.add(msg)
        convo.updated_at = datetime.utcnow()

        recipient = convo.other_party(current_user)
        Notification.push(
            user_id=recipient.id,
            title=f"New message about {convo.car.year} {convo.car.make} {convo.car.model}",
            body=msg.body[:140],
            link=url_for("messaging.thread", conversation_id=convo.id),
        )
        db.session.commit()
        return redirect(url_for("messaging.thread", conversation_id=convo.id))

    unread = (
        Message.query.filter_by(conversation_id=convo.id, read_at=None)
        .filter(Message.sender_id != current_user.id)
        .all()
    )
    if unread:
        now = datetime.utcnow()
        for m in unread:
            m.read_at = now
        db.session.commit()

    today = date.today()
    return render_template(
        "messaging/thread.html",
        convo=convo,
        form=form,
        other=convo.other_party(current_user),
        today=today,
        yesterday=today - timedelta(days=1),
    )
