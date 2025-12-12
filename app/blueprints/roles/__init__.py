from flask import Blueprint

roles_bp = Blueprint("roles", __name__, url_prefix="/roles")

from app.blueprints.roles import routes
