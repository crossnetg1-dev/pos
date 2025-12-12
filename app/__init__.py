import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, render_template
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

    # Create required directories
    create_required_directories(app)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    migrate.init_app(app, db)

    register_blueprints(app)
    register_shellcontext(app)
    register_context_processors(app)
    register_error_handlers(app)
    configure_logging(app)
    return app


def create_required_directories(app: Flask) -> None:
    """Create required directories if they don't exist."""
    base_dir = Path(__file__).parent.parent
    
    # Upload directories
    upload_dirs = [
        base_dir / 'app' / 'static' / 'uploads' / 'product_images',
        base_dir / 'app' / 'static' / 'uploads' / 'logos',
    ]
    
    # Instance directory (for database)
    instance_dir = base_dir / 'instance'
    
    # Create all directories
    for directory in upload_dirs + [instance_dir]:
        directory.mkdir(parents=True, exist_ok=True)


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
                        "shop_name": "Cid-POS",
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


def register_error_handlers(app: Flask) -> None:
    """Register error handlers for 404 and 500 errors."""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        # Log the error
        app.logger.error(f'Server Error: {error}', exc_info=True)
        db.session.rollback()
        return render_template('errors/500.html'), 500


def configure_logging(app: Flask) -> None:
    """Configure logging for production and development."""
    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # Configure file handler (works in both dev and production)
    file_handler = RotatingFileHandler(
        log_dir / 'app.log',
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
    
    # Set log level based on environment
    if app.debug:
        file_handler.setLevel(logging.DEBUG)
        app.logger.setLevel(logging.DEBUG)
    else:
        file_handler.setLevel(logging.INFO)
        app.logger.setLevel(logging.INFO)
    
    app.logger.addHandler(file_handler)
    app.logger.info('POS System startup')
