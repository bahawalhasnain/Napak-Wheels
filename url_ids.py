"""Opaque, signed integer IDs in URLs (per-namespace salts prevent cross-resource swapping).

Uses itsdangerous.URLSafeSerializer so tokens are tamper-evident and reversible
with the app SECRET_KEY. Not encryption of sensitive data — IDs remain guessable
in principle if someone obtains a valid token for another resource type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from itsdangerous import BadSignature, URLSafeSerializer
from werkzeug.exceptions import NotFound
from werkzeug.routing import BaseConverter

if TYPE_CHECKING:
    from flask import Flask

_SERIALIZERS: dict[str, URLSafeSerializer] = {}

_NAMESPACES = (
    "car",
    "conversation",
    "offer",
    "test_drive",
    "report",
    "user",
    "saved_search",
    "notification",
)


def init_url_id_codec(app: Flask) -> None:
    global _SERIALIZERS
    secret = app.config["SECRET_KEY"]
    _SERIALIZERS = {ns: URLSafeSerializer(secret, salt=f"nw-url-{ns}") for ns in _NAMESPACES}


def _ensure_codec(app: Flask | None = None) -> None:
    if _SERIALIZERS:
        return
    if app is not None:
        init_url_id_codec(app)
        return
    from flask import current_app, has_app_context

    if has_app_context():
        init_url_id_codec(current_app._get_current_object())


def encode_url_id(namespace: str, id_: int, app: Flask | None = None) -> str:
    _ensure_codec(app)
    try:
        return _SERIALIZERS[namespace].dumps(id_)
    except KeyError as exc:
        raise ValueError(f"unknown url id namespace: {namespace}") from exc


def decode_url_id(namespace: str, token: str, app: Flask | None = None) -> int:
    _ensure_codec(app)
    try:
        ser = _SERIALIZERS[namespace]
    except KeyError as exc:
        raise ValueError(f"unknown url id namespace: {namespace}") from exc
    try:
        val = ser.loads(token)
    except BadSignature:
        raise NotFound() from None
    if not isinstance(val, int) or val < 1:
        raise NotFound()
    return val


def _make_pid_converter(namespace: str):
    class PidConverter(BaseConverter):
        # itsdangerous URLSafeSerializer uses "." between payload and signature
        regex = r"[^/]+"

        def to_python(self, value: str) -> int:
            return decode_url_id(namespace, value)

        def to_url(self, value):
            if value is None:
                raise ValueError("missing id for URL")
            return encode_url_id(namespace, int(value))

    PidConverter.__name__ = f"PidConverter_{namespace.replace('-', '_')}"
    return PidConverter


def register_url_id_converters(app: Flask) -> None:
    m = app.url_map.converters
    m["car_pid"] = _make_pid_converter("car")
    m["convo_pid"] = _make_pid_converter("conversation")
    m["offer_pid"] = _make_pid_converter("offer")
    m["drive_pid"] = _make_pid_converter("test_drive")
    m["report_pid"] = _make_pid_converter("report")
    m["user_pid"] = _make_pid_converter("user")
    m["search_pid"] = _make_pid_converter("saved_search")
    m["notif_pid"] = _make_pid_converter("notification")
