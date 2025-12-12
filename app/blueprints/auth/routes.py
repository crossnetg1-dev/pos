from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from app import db
from app.models import User
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
    return render_template("auth/login.html")


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
    if request.method == "POST":
        email = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "warning")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("User already exists.", "danger")
            return render_template("auth/register.html")

        username = email.split("@")[0] if "@" in email else email
        user = User(email=email, username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html")
