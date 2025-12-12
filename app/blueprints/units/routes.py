from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import Product, Unit
from app.utils import permission_required

units_bp = Blueprint("units", __name__, url_prefix="/units")


@units_bp.route("/", methods=["GET"])
@login_required
@permission_required('units_manage')
def index():
    units = Unit.query.order_by(Unit.name).all()
    return render_template("units/index.html", units=units)


@units_bp.route("/add", methods=["POST"])
@login_required
@permission_required('units_manage')
def add():
    name = request.form.get("name", "").strip()
    short_name = request.form.get("short_name", "").strip()
    
    if not name or not short_name:
        flash("Name and Short Name are required.", "warning")
        return redirect(url_for("units.index"))
    
    # Check if unit already exists
    if Unit.query.filter_by(name=name).first():
        flash("Unit name already exists.", "danger")
        return redirect(url_for("units.index"))
    
    if Unit.query.filter_by(short_name=short_name).first():
        flash("Short name already exists.", "danger")
        return redirect(url_for("units.index"))
    
    unit = Unit(name=name, short_name=short_name)
    db.session.add(unit)
    db.session.commit()
    flash("Unit added successfully.", "success")
    return redirect(url_for("units.index"))


@units_bp.route("/edit/<int:unit_id>", methods=["POST"])
@login_required
@permission_required('units_manage')
def edit(unit_id: int):
    unit = db.session.get(Unit, unit_id)
    if not unit:
        flash("Unit not found.", "danger")
        return redirect(url_for("units.index"))
    
    name = request.form.get("name", "").strip()
    short_name = request.form.get("short_name", "").strip()
    
    if not name or not short_name:
        flash("Name and Short Name are required.", "warning")
        return redirect(url_for("units.index"))
    
    # Check if another unit with the same name/short_name exists
    existing_name = Unit.query.filter_by(name=name).first()
    if existing_name and existing_name.id != unit_id:
        flash("Unit name already exists.", "danger")
        return redirect(url_for("units.index"))
    
    existing_short = Unit.query.filter_by(short_name=short_name).first()
    if existing_short and existing_short.id != unit_id:
        flash("Short name already exists.", "danger")
        return redirect(url_for("units.index"))
    
    unit.name = name
    unit.short_name = short_name
    db.session.commit()
    flash("Unit updated successfully.", "success")
    return redirect(url_for("units.index"))


@units_bp.route("/delete/<int:unit_id>", methods=["POST"])
@login_required
@permission_required('units_manage')
def delete(unit_id: int):
    unit = db.session.get(Unit, unit_id)
    if not unit:
        flash("Unit not found.", "danger")
        return redirect(url_for("units.index"))
    
    # Check if products are using this unit
    products_count = Product.query.filter_by(unit_id=unit_id).count()
    
    if products_count > 0:
        # Set products to null instead of preventing delete
        Product.query.filter_by(unit_id=unit_id).update({"unit_id": None})
        db.session.commit()
        flash(f"Unit deleted. {products_count} product(s) were set to 'No Unit'.", "info")
    else:
        flash("Unit deleted successfully.", "success")
    
    db.session.delete(unit)
    db.session.commit()
    return redirect(url_for("units.index"))
