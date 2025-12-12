from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import Category, Product
from app.utils import permission_required

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")


@categories_bp.route("/", methods=["GET"])
@login_required
@permission_required('categories_manage')
def index():
    # Get main categories (no parent) and subcategories
    main_categories = Category.query.filter_by(parent_id=None).order_by(Category.name).all()
    subcategories = Category.query.filter(Category.parent_id.isnot(None)).order_by(Category.name).all()
    all_categories = Category.query.order_by(Category.name).all()
    return render_template(
        "categories/index.html",
        categories=all_categories,
        main_categories=main_categories
    )


@categories_bp.route("/add", methods=["POST"])
@login_required
@permission_required('categories_manage')
def add():
    name = request.form.get("name", "").strip()
    parent_id = request.form.get("parent_id", "").strip()
    
    if not name:
        flash("Category name is required.", "warning")
        return redirect(url_for("categories.index"))
    
    # Check if category already exists (same name, same parent)
    existing = Category.query.filter_by(name=name, parent_id=int(parent_id) if parent_id else None).first()
    if existing:
        flash("Category already exists.", "danger")
        return redirect(url_for("categories.index"))
    
    category = Category(
        name=name,
        parent_id=int(parent_id) if parent_id else None
    )
    db.session.add(category)
    db.session.commit()
    flash("Category added successfully.", "success")
    return redirect(url_for("categories.index"))


@categories_bp.route("/edit/<int:category_id>", methods=["POST"])
@login_required
@permission_required('categories_manage')
def edit(category_id: int):
    category = db.session.get(Category, category_id)
    if not category:
        flash("Category not found.", "danger")
        return redirect(url_for("categories.index"))
    
    name = request.form.get("name", "").strip()
    parent_id = request.form.get("parent_id", "").strip()
    
    if not name:
        flash("Category name is required.", "warning")
        return redirect(url_for("categories.index"))
    
    # Check if another category with the same name and parent exists
    new_parent_id = int(parent_id) if parent_id else None
    existing = Category.query.filter_by(name=name, parent_id=new_parent_id).first()
    if existing and existing.id != category_id:
        flash("Category name already exists in this parent.", "danger")
        return redirect(url_for("categories.index"))
    
    # Prevent setting parent to itself or its own subcategory
    if new_parent_id == category_id:
        flash("Category cannot be its own parent.", "danger")
        return redirect(url_for("categories.index"))
    
    category.name = name
    category.parent_id = new_parent_id
    db.session.commit()
    flash("Category updated successfully.", "success")
    return redirect(url_for("categories.index"))


@categories_bp.route("/delete/<int:category_id>", methods=["POST"])
@login_required
@permission_required('categories_manage')
def delete(category_id: int):
    category = db.session.get(Category, category_id)
    if not category:
        flash("Category not found.", "danger")
        return redirect(url_for("categories.index"))
    
    # Check if products are using this category
    products_count = Product.query.filter_by(category_id=category_id).count()
    
    if products_count > 0:
        # Option: Set products to null instead of preventing delete
        Product.query.filter_by(category_id=category_id).update({"category_id": None})
        db.session.commit()
        flash(f"Category deleted. {products_count} product(s) were set to 'No Category'.", "info")
    else:
        flash("Category deleted successfully.", "success")
    
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for("categories.index"))
