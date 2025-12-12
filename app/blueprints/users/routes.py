from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import AuditLog, Role, User
from app.utils import log_activity, permission_required

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("/", methods=["GET"])
@login_required
@permission_required('users_manage')
def index():
    users = User.query.order_by(User.username).all()
    roles = Role.query.order_by(Role.name).all()
    return render_template("users/index.html", users=users, roles=roles)


@users_bp.route("/logs", methods=["GET"])
@login_required
@permission_required('users_manage')
def logs():
    """View audit logs (Admin only)."""
    from flask import request
    from sqlalchemy import or_
    
    # Search functionality
    search_query = request.args.get("q", "").strip()
    query = AuditLog.query
    
    if search_query:
        query = query.join(User, AuditLog.user_id == User.id, isouter=True).filter(
            or_(
                AuditLog.action.ilike(f'%{search_query}%'),
                AuditLog.details.ilike(f'%{search_query}%'),
                AuditLog.ip_address.ilike(f'%{search_query}%'),
                User.username.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%')
            )
        )
    
    # Sort by date descending (newest first)
    logs = query.order_by(AuditLog.timestamp.desc()).limit(500).all()  # Limit to last 500 logs
    
    return render_template("users/logs.html", logs=logs, search_query=search_query)


@users_bp.route("/add", methods=["POST"])
@login_required
@permission_required('users_manage')
def add():
    email = request.form.get("email", "").lower().strip()
    password = request.form.get("password", "")
    role_id = request.form.get("role_id", "").strip()
    
    if not email or not password:
        flash("Email and password are required.", "warning")
        return redirect(url_for("users.index"))
    
    if User.query.filter_by(email=email).first():
        flash("User already exists.", "danger")
        return redirect(url_for("users.index"))
    
    username = email.split("@")[0] if "@" in email else email
    user = User(
        email=email,
        username=username,
        role_id=int(role_id) if role_id else None
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    log_activity('USER_CREATE', f'Created user: {user.username} ({user.email}), Role ID: {role_id}')
    flash("User created successfully.", "success")
    return redirect(url_for("users.index"))


@users_bp.route("/edit/<int:user_id>", methods=["POST"])
@login_required
@permission_required('users_manage')
def edit(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("users.index"))
    
    email = request.form.get("email", "").lower().strip()
    password = request.form.get("password", "").strip()
    role_id = request.form.get("role_id", "").strip()
    
    if not email:
        flash("Email is required.", "warning")
        return redirect(url_for("users.index"))
    
    # Check if another user has this email
    existing = User.query.filter_by(email=email).first()
    if existing and existing.id != user_id:
        flash("Email already exists.", "danger")
        return redirect(url_for("users.index"))
    
    user.email = email
    user.username = email.split("@")[0] if "@" in email else email
    user.role_id = int(role_id) if role_id else None
    
    if password:
        user.set_password(password)
    
    db.session.commit()
    flash("User updated successfully.", "success")
    return redirect(url_for("users.index"))


@users_bp.route("/delete/<int:user_id>", methods=["POST"])
@login_required
@permission_required('users_manage')
def delete(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("users.index"))
    
    # Prevent deleting yourself
    from flask_login import current_user
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("users.index"))
    
    username = user.username
    user_email = user.email
    db.session.delete(user)
    db.session.commit()
    log_activity('USER_DELETE', f'Deleted user: {username} ({user_email}), ID: {user_id}')
    flash("User deleted successfully.", "success")
    return redirect(url_for("users.index"))
