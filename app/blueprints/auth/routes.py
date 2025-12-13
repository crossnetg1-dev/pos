from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app import db
from app.models import User, Role
from app.utils import log_activity

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            log_activity('LOGIN_SUCCESS', f'User {user.username} ({user.email}) logged in')
            flash("Logged in successfully.", "success")
            return redirect(url_for("main.dashboard"))
        log_activity('LOGIN_FAIL', f'Failed login attempt for email: {email}')
        flash("Invalid credentials.", "danger")
    
    # Check if this is the first run (no users exist)
    is_first_run = User.query.first() is None
    return render_template("auth/login.html", is_first_run=is_first_run)


@auth_bp.route("/logout")
@login_required
def logout():
    from flask_login import current_user
    username = current_user.username if current_user.is_authenticated else "Unknown"
    logout_user()
    log_activity('LOGOUT', f'User {username} logged out')
    flash("Logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # Check if users already exist (public registration disabled after first user)
    existing_users = User.query.first()
    if existing_users:
        flash("Public registration is disabled. Please ask the Admin to create an account.", "warning")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "warning")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("User already exists.", "danger")
            return render_template("auth/register.html")

        # First Run Logic: Check if this is the first user
        is_first_user = User.query.count() == 0
        
        if is_first_user:
            # First user automatically becomes Admin
            admin_role = Role.query.filter_by(name='Admin').first()
            if not admin_role:
                # If Admin role doesn't exist, create it with all permissions
                from app.utils import ALL_PERMISSIONS
                admin_role = Role(
                    name='Admin',
                    permissions=','.join(ALL_PERMISSIONS)
                )
                db.session.add(admin_role)
                db.session.flush()  # Flush to get the ID
            
            username = email.split("@")[0] if "@" in email else email
            user = User(email=email, username=username, role_id=admin_role.id)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            log_activity('USER_CREATE', f'First user (Admin) created: {user.username} ({user.email})')
            flash("Admin account created successfully. Please log in.", "success")
        else:
            # Subsequent users get Cashier role (if registration is allowed)
            cashier_role = Role.query.filter_by(name='Cashier').first()
            if not cashier_role:
                # Create Cashier role with basic permissions
                from app.utils import ALL_PERMISSIONS
                basic_permissions = ['pos_access', 'sales_view', 'dashboard_view']
                cashier_role = Role(
                    name='Cashier',
                    permissions=','.join(basic_permissions)
                )
                db.session.add(cashier_role)
                db.session.flush()
            
            username = email.split("@")[0] if "@" in email else email
            user = User(email=email, username=username, role_id=cashier_role.id)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            log_activity('USER_CREATE', f'User (Cashier) created: {user.username} ({user.email})')
            flash("Account created successfully. Please log in.", "success")
        
        return redirect(url_for("auth.login"))
    
    return render_template("auth/register.html")
