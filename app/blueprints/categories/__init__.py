from flask import Blueprint

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")

from app.blueprints.categories import routes
