import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-env")
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_ENABLED = True
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

