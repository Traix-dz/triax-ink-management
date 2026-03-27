from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    # Configuration
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-fallback-key")
    database_url = os.environ.get("DATABASE_URL", "sqlite:///triax_dev.db")
    # Render fournit parfois postgres:// — SQLAlchemy 1.4+ exige postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 Mo max pour les PDF
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "../uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "warning"

    # Import des modèles (nécessaire pour Migrate)
    from app import models  # noqa: F401

    # Blueprints
    from app.auth.routes import auth_bp
    from app.of.routes import of_bp
    from app.referentiels.routes import ref_bp
    from app.admin.routes import admin_bp
    from app.export.routes import export_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(of_bp)
    app.register_blueprint(ref_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(export_bp)

    # Route racine
    from flask import redirect, url_for
    from flask_login import current_user

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("of.dashboard"))
        return redirect(url_for("auth.login"))

    return app
