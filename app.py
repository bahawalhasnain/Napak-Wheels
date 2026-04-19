import os
import logging
from time import perf_counter
from flask import Flask, g, request
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import inspect, text
from dotenv import load_dotenv
from extensions import db

# Set up console logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
# Ensure values in local .env replace any stale system env variables.
load_dotenv(override=True)
from config import Config

# Create the app
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config["SECRET_KEY"]
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
logging.getLogger("werkzeug").setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
logger = app.logger


@app.before_request
def log_request_start():
    g.request_start_time = perf_counter()
    logger.info("Request started: %s %s", request.method, request.path)


@app.after_request
def log_request_end(response):
    duration_ms = (perf_counter() - g.get("request_start_time", perf_counter())) * 1000
    logger.info(
        "Request completed: %s %s -> %s (%.2f ms)",
        request.method,
        request.path,
        response.status_code,
        duration_ms,
    )
    return response

# Configure file uploads
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize the app with the extension
db.init_app(app)
logger.info("Database URL loaded. Driver: %s", app.config["SQLALCHEMY_DATABASE_URI"].split(":")[0])

with app.app_context():
    # Import models to ensure tables are created
    import models
    logger.info("Creating database tables if missing...")
    db.create_all()
    logger.info("Database initialization completed.")

    # Lightweight schema migration for existing SQLite databases only.
    inspector = inspect(db.engine)
    if db.engine.dialect.name == "sqlite":
        if inspector.has_table("car"):
            car_columns = {col["name"] for col in inspector.get_columns("car")}
            if "user_id" not in car_columns:
                db.session.execute(text("ALTER TABLE car ADD COLUMN user_id INTEGER"))
                db.session.commit()
            if "features" not in car_columns:
                db.session.execute(text("ALTER TABLE car ADD COLUMN features TEXT"))
                db.session.commit()

        if inspector.has_table("user"):
            user_columns = {col["name"] for col in inspector.get_columns("user")}
            if "phone" not in user_columns:
                db.session.execute(text("ALTER TABLE user ADD COLUMN phone VARCHAR(20)"))
                db.session.commit()
            if "location" not in user_columns:
                db.session.execute(text("ALTER TABLE user ADD COLUMN location VARCHAR(100)"))
                db.session.commit()

    # Import routes after app is configured
    from routes import bp
    app.register_blueprint(bp)
    logger.info("Blueprints registered successfully.")
