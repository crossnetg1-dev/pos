from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

from config import config_by_name, DevelopmentConfig

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app(config_name: str | None = None) -> Flask:
    """Application factory."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    config_obj = config_by_name.get(config_name or "development", DevelopmentConfig)
    app.config.from_object(config_obj)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    migrate.init_app(app, db)

    register_blueprints(app)
    register_shellcontext(app)
    register_context_processors(app)
    return app


def register_blueprints(app: Flask) -> None:
    """Attach blueprint modules."""
    from app.blueprints.auth.routes import auth_bp
    from app.blueprints.pos.routes import pos_bp
    from app.blueprints.inventory.routes import inventory_bp
    from app.blueprints.reports.routes import reports_bp
    from app.blueprints.main.routes import main_bp
    from app.blueprints.customers.routes import customers_bp
    from app.blueprints.settings.routes import settings_bp
    from app.blueprints.purchases.routes import purchases_bp
    from app.blueprints.categories.routes import categories_bp
    from app.blueprints.units.routes import units_bp
    from app.blueprints.roles.routes import roles_bp
    from app.blueprints.users.routes import users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(purchases_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(units_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(users_bp)


def register_shellcontext(app: Flask) -> None:
    """Add objects to `flask shell` context for convenience."""
    from app import models

    @app.shell_context_processor
    def shell_context():
        return {
            "db": db,
            "models": models,
        }


def register_context_processors(app: Flask) -> None:
    """Register context processors for global template variables."""
    @app.context_processor
    def inject_store_settings():
        from app.models import StoreSetting
        try:
            store = StoreSetting.get_settings()
            return {"store": store}
        except Exception:
            # If table doesn't exist yet, return defaults
            return {
                "store": type(
                    "Store",
                    (),
                    {
                        "shop_name": "Smart POS",
                        "address": "",
                        "phone": "",
                        "receipt_header": "",
                        "receipt_footer": "Thank You!",
                        "currency_symbol": "Ks",
                        "printer_paper_size": "58mm",
                        "auto_print": False,
                        "show_logo_on_receipt": True,
                        "print_padding": 0,
                    },
                )()
            }


@login_manager.user_loader
def load_user(user_id: str):
    from app.models import User

    return db.session.get(User, int(user_id))
