import os


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Base configuration loaded from environment variables."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-env")
    DEBUG = _bool(os.environ.get("FLASK_DEBUG"), False)

    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_ENABLED = True

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///napak_wheels.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "16")) * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "jfif"}

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool(os.environ.get("SESSION_COOKIE_SECURE"), False)

    # Email (SMTP). Leave MAIL_SERVER blank to log emails instead of sending.
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = _bool(os.environ.get("MAIL_USE_TLS"), True)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@napak-wheels.local")
    MAIL_SUPPRESS_SEND = _bool(os.environ.get("MAIL_SUPPRESS_SEND"), False)

    # Celery / background jobs
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "")
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "")
    CELERY_TASK_ALWAYS_EAGER = _bool(
        os.environ.get("CELERY_TASK_ALWAYS_EAGER"),
        default=not bool(os.environ.get("CELERY_BROKER_URL")),
    )


class TestConfig(Config):
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SECRET_KEY = "test-secret"
    UPLOAD_FOLDER = "test_uploads"
    CELERY_TASK_ALWAYS_EAGER = True
    MAIL_SUPPRESS_SEND = True
