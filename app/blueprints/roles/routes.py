from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import Role, User
from app.utils import ALL_PERMISSIONS, permission_required

roles_bp = Blueprint("roles", __name__, url_prefix="/roles")


@roles_bp.route("/", methods=["GET"])
@login_required
@permission_required('users_manage')
def index():
    roles = Role.query.order_by(Role.name).all()
    return render_template("roles/index.html", roles=roles, all_permissions=ALL_PERMISSIONS)


@roles_bp.route("/add", methods=["GET", "POST"])
@login_required
@permission_required('users_manage')
def add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        selected_permissions = request.form.getlist("permissions")
        
        if not name:
            flash("Role name is required.", "warning")
            return redirect(url_for("roles.add"))
        
        # Check if role already exists
        if Role.query.filter_by(name=name).first():
            flash("Role name already exists.", "danger")
            return redirect(url_for("roles.add"))
        
        # Store permissions as comma-separated string
        permissions_str = ','.join(selected_permissions) if selected_permissions else ''
        
        role = Role(name=name, permissions=permissions_str)
        db.session.add(role)
        db.session.commit()
        flash("Role added successfully.", "success")
        return redirect(url_for("roles.index"))
    
    return render_template("roles/add.html", all_permissions=ALL_PERMISSIONS)


@roles_bp.route("/edit/<int:role_id>", methods=["GET", "POST"])
@login_required
@permission_required('users_manage')
def edit(role_id: int):
    role = db.session.get(Role, role_id)
    if not role:
        flash("Role not found.", "danger")
        return redirect(url_for("roles.index"))
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        selected_permissions = request.form.getlist("permissions")
        
        if not name:
            flash("Role name is required.", "warning")
            return redirect(url_for("roles.edit", role_id=role_id))
        
        # Check if another role with the same name exists
        existing = Role.query.filter_by(name=name).first()
        if existing and existing.id != role_id:
            flash("Role name already exists.", "danger")
            return redirect(url_for("roles.edit", role_id=role_id))
        
        role.name = name
        role.permissions = ','.join(selected_permissions) if selected_permissions else ''
        db.session.commit()
        flash("Role updated successfully.", "success")
        return redirect(url_for("roles.index"))
    
    # Parse current permissions
    current_permissions = []
    if role.permissions:
        current_permissions = [p.strip() for p in role.permissions.split(',')]
    
    return render_template(
        "roles/edit.html",
        role=role,
        all_permissions=ALL_PERMISSIONS,
        current_permissions=current_permissions
    )


@roles_bp.route("/delete/<int:role_id>", methods=["POST"])
@login_required
@permission_required('users_manage')
def delete(role_id: int):
    role = db.session.get(Role, role_id)
    if not role:
        flash("Role not found.", "danger")
        return redirect(url_for("roles.index"))
    
    # Check if users are using this role
    users_count = User.query.filter_by(role_id=role_id).count()
    
    if users_count > 0:
        flash(f"Cannot delete role. {users_count} user(s) are using this role.", "danger")
        return redirect(url_for("roles.index"))
    
    db.session.delete(role)
    db.session.commit()
    flash("Role deleted successfully.", "success")
    return redirect(url_for("roles.index"))
