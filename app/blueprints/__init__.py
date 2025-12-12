from app.blueprints.auth import auth_bp
from app.blueprints.inventory import inventory_bp
from app.blueprints.main import main_bp
from app.blueprints.pos import pos_bp
from app.blueprints.reports import reports_bp
from app.blueprints.customers import customers_bp
from app.blueprints.settings import settings_bp
from app.blueprints.purchases import purchases_bp
from app.blueprints.categories import categories_bp
from app.blueprints.units import units_bp
from app.blueprints.roles import roles_bp
from app.blueprints.users import users_bp

__all__ = [
    "auth_bp",
    "inventory_bp",
    "main_bp",
    "pos_bp",
    "reports_bp",
    "customers_bp",
    "settings_bp",
    "purchases_bp",
    "categories_bp",
    "units_bp",
    "roles_bp",
    "users_bp",
]
