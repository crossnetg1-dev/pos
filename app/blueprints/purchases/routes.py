from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Product, Purchase, PurchaseItem, StockMovement, Supplier
from app.utils import log_stock_movement, permission_required

purchases_bp = Blueprint("purchases", __name__, url_prefix="/purchases")


@purchases_bp.route("/suppliers", methods=["GET", "POST"])
@login_required
@permission_required('purchases_manage')
def suppliers():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name:
            flash("Name is required.", "warning")
            return redirect(url_for("purchases.suppliers"))

        supplier = Supplier(
            name=name,
            phone=phone,
            address=address,
        )
        db.session.add(supplier)
        db.session.commit()
        flash("Supplier added.", "success")
        return redirect(url_for("purchases.suppliers"))

    suppliers_list = Supplier.query.order_by(Supplier.name).all()
    return render_template("purchases/suppliers.html", suppliers=suppliers_list)


@purchases_bp.route("/suppliers/<int:supplier_id>/delete", methods=["POST"])
@login_required
def delete_supplier(supplier_id: int):
    supplier = db.session.get(Supplier, supplier_id)
    if not supplier:
        flash("Supplier not found.", "danger")
        return redirect(url_for("purchases.suppliers"))
    db.session.delete(supplier)
    db.session.commit()
    flash("Supplier deleted.", "info")
    return redirect(url_for("purchases.suppliers"))


@purchases_bp.route("/new", methods=["GET"])
@login_required
@permission_required('purchases_manage')
def new_purchase():
    from datetime import date
    suppliers = Supplier.query.order_by(Supplier.name).all()
    products = Product.query.order_by(Product.name).all()
    today = date.today().strftime("%Y-%m-%d")
    return render_template(
        "purchases/new_purchase.html", suppliers=suppliers, products=products, today=today
    )


@purchases_bp.route("/products/search", methods=["GET"])
@login_required
@permission_required('purchases_manage')
def search_products():
    """API endpoint for product search."""
    query = request.args.get("q", "").lower()
    if not query:
        return jsonify({"products": []})
    
    # SQLite compatible search
    products = (
        Product.query.filter(
            (Product.name.like(f"%{query}%")) | (Product.barcode.like(f"%{query}%"))
        )
        .limit(20)
        .all()
    )

    results = [
        {
            "id": p.id,
            "name": p.name,
            "barcode": p.barcode,
            "current_cost": float(p.cost or 0),
            "current_stock": p.stock or 0,
        }
        for p in products
    ]
    return jsonify({"products": results})


@purchases_bp.route("/create", methods=["POST"])
@login_required
@permission_required('purchases_manage')
def create_purchase():
    if not request.is_json:
        return jsonify({"error": "JSON body required"}), 400

    data = request.get_json(silent=True) or {}
    supplier_id = data.get("supplier_id")
    items = data.get("items", [])
    purchase_date = data.get("date")

    if not supplier_id:
        return jsonify({"error": "Supplier is required"}), 400

    if not items:
        return jsonify({"error": "No items provided"}), 400

    supplier = db.session.get(Supplier, supplier_id)
    if not supplier:
        return jsonify({"error": "Supplier not found"}), 404

    # Create purchase
    purchase = Purchase(supplier_id=supplier_id, total_amount=0)
    if purchase_date:
        try:
            purchase.date = datetime.strptime(purchase_date, "%Y-%m-%d")
        except ValueError:
            pass

    db.session.add(purchase)
    db.session.flush()

    # Process items
    for item_data in items:
        product_id = item_data.get("product_id")
        quantity = int(item_data.get("quantity", 0))
        cost_price = float(item_data.get("cost_price", 0))

        if not product_id or quantity <= 0:
            continue

        product = db.session.get(Product, product_id)
        if not product:
            continue

        # Create purchase item
        purchase_item = PurchaseItem(
            purchase_id=purchase.id,
            product_id=product.id,
            quantity=quantity,
            cost_price=cost_price,
            subtotal=cost_price * quantity,
        )
        db.session.add(purchase_item)

        # Update product stock and cost (weighted average)
        old_stock = product.stock or 0
        old_cost = float(product.cost or 0)
        new_stock = old_stock + quantity

        # Weighted average cost calculation
        if old_stock > 0:
            total_old_value = old_stock * old_cost
            total_new_value = quantity * cost_price
            new_cost = (total_old_value + total_new_value) / new_stock
        else:
            new_cost = cost_price

        product.stock = new_stock
        product.cost = new_cost

        # Log stock movement
        log_stock_movement(
            product_id=product.id,
            quantity=quantity,
            change_type='in',
            reason=f'Purchase #{purchase.id}',
            user_id=current_user.id if current_user.is_authenticated else None
        )

    purchase.recompute_total()
    db.session.commit()

    return jsonify(
        {
            "status": "success",
            "purchase_id": purchase.id,
            "total": float(purchase.total_amount),
        }
    )


@purchases_bp.route("/", methods=["GET"])
@login_required
@permission_required('purchases_manage')
def index():
    purchases = Purchase.query.order_by(Purchase.date.desc()).all()
    suppliers = Supplier.query.order_by(Supplier.name).all()
    return render_template("purchases/index.html", purchases=purchases, suppliers=suppliers)


@purchases_bp.route("/<int:purchase_id>/delete", methods=["POST"])
@login_required
@permission_required('purchases_manage')
def delete_purchase(purchase_id: int):
    purchase = db.session.get(Purchase, purchase_id)
    if not purchase:
        flash("Purchase not found.", "danger")
        return redirect(url_for("purchases.index"))

    # Rollback stock for each item
    for item in purchase.items:
        product = db.session.get(Product, item.product_id)
        if product:
            # Subtract the quantity from stock
            product.stock = max(0, (product.stock or 0) - item.quantity)

            # Log stock movement
            log_stock_movement(
                product_id=product.id,
                quantity=item.quantity,
                change_type='out',
                reason=f'Purchase Voided #{purchase.id}',
                user_id=current_user.id if current_user.is_authenticated else None
            )

    # Delete the purchase (cascade will delete items)
    db.session.delete(purchase)
    db.session.commit()

    flash(f"Purchase #{purchase.id} has been voided and stock rolled back.", "info")
    return redirect(url_for("purchases.index"))


@purchases_bp.route("/<int:purchase_id>/details", methods=["GET"])
@login_required
@permission_required('purchases_manage')
def get_purchase_details(purchase_id: int):
    """API endpoint to get purchase details."""
    purchase = db.session.get(Purchase, purchase_id)
    if not purchase:
        return jsonify({"error": "Purchase not found"}), 404

    items = [
        {
            "product_name": item.product.name if item.product else "Unknown",
            "quantity": item.quantity,
            "cost_price": float(item.cost_price or 0),
            "subtotal": float(item.subtotal or 0),
        }
        for item in purchase.items
    ]

    return jsonify(
        {
            "id": purchase.id,
            "date": purchase.date.strftime("%Y-%m-%d %H:%M"),
            "supplier": purchase.supplier.name if purchase.supplier else "Unknown",
            "total": float(purchase.total_amount or 0),
            "items": items,
        }
    )


@purchases_bp.route("/<int:purchase_id>/edit", methods=["GET"])
@login_required
@permission_required('purchases_edit')
def edit_purchase(purchase_id: int):
    purchase = db.session.get(Purchase, purchase_id)
    if not purchase:
        flash("Purchase not found.", "danger")
        return redirect(url_for("purchases.index"))

    suppliers = Supplier.query.order_by(Supplier.name).all()
    products = Product.query.order_by(Product.name).all()
    
    # Get purchase items for pre-filling
    purchase_items = [
        {
            "product_id": item.product_id,
            "product_name": item.product.name if item.product else "Unknown",
            "barcode": item.product.barcode if item.product else "",
            "quantity": item.quantity,
            "cost_price": float(item.cost_price or 0),
            "subtotal": float(item.subtotal or 0),
        }
        for item in purchase.items
    ]

    return render_template(
        "purchases/edit_purchase.html",
        purchase=purchase,
        suppliers=suppliers,
        products=products,
        purchase_items=purchase_items,
    )


@purchases_bp.route("/<int:purchase_id>/edit", methods=["POST"])
@login_required
@permission_required('purchases_edit')
def update_purchase(purchase_id: int):
    """Full edit: Revert & Re-apply logic for accurate stock updates."""
    # Get Record: Fetch Purchase by ID
    purchase = db.session.get(Purchase, purchase_id)
    if not purchase:
        return jsonify({"error": "Purchase not found"}), 404

    if not request.is_json:
        return jsonify({"error": "JSON body required"}), 400

    data = request.get_json(silent=True) or {}
    supplier_id = data.get("supplier_id")
    new_items = data.get("items", [])
    purchase_date = data.get("date")

    if not supplier_id:
        return jsonify({"error": "Supplier is required"}), 400

    # ============================================
    # STEP 1: REVERT - Subtract old items from stock
    # ============================================
    # Loop through existing purchase.items
    for old_item in purchase.items:
        product = db.session.get(Product, old_item.product_id)
        if product:
            # Subtract item.quantity from Product.stock (Send back to supplier)
            current_stock = product.stock or 0
            product.stock = max(0, current_stock - old_item.quantity)
            # Log stock movement (Rollback Phase)
            log_stock_movement(
                product_id=product.id,
                quantity=old_item.quantity,
                change_type='out',
                reason=f'Purchase Edit Rollback #{purchase.id}',
                user_id=current_user.id if current_user.is_authenticated else None
            )

    # ============================================
    # STEP 2: DELETE - Remove old PurchaseItem records
    # ============================================
    for old_item in purchase.items:
        db.session.delete(old_item)

    db.session.flush()  # Ensure deletions are processed

    # ============================================
    # STEP 3: APPLY NEW - Add new items to stock
    # ============================================
    # Loop through NEW items
    for item_data in new_items:
        product_id = item_data.get("product_id")
        quantity = int(item_data.get("quantity", 0))
        cost_price = float(item_data.get("cost_price", 0))

        if not product_id or quantity <= 0:
            continue

        product = db.session.get(Product, product_id)
        if not product:
            continue

        # Add new quantity to Product.stock (Receive new stock)
        current_stock = product.stock or 0
        new_stock = current_stock + quantity

        # Update product cost using weighted average
        old_cost = float(product.cost or 0)
        if current_stock > 0:
            total_old_value = current_stock * old_cost
            total_new_value = quantity * cost_price
            new_cost = (total_old_value + total_new_value) / new_stock
        else:
            new_cost = cost_price

        product.stock = new_stock
        product.cost = new_cost

        # Log stock movement (Apply Phase)
        log_stock_movement(
            product_id=product.id,
            quantity=quantity,
            change_type='in',
            reason=f'Purchase Edit Apply #{purchase.id}',
            user_id=current_user.id if current_user.is_authenticated else None
        )

        # Create new PurchaseItem
        purchase_item = PurchaseItem(
            purchase_id=purchase.id,
            product_id=product.id,
            quantity=quantity,
            cost_price=cost_price,
            subtotal=cost_price * quantity,
        )
        db.session.add(purchase_item)

    # ============================================
    # STEP 4: UPDATE HEADER - Update purchase fields and total
    # ============================================
    # Update purchase.supplier_id, purchase.date
    purchase.supplier_id = supplier_id
    if purchase_date:
        try:
            purchase.date = datetime.strptime(purchase_date, "%Y-%m-%d")
        except ValueError:
            pass  # Keep existing date if parsing fails

    # Recalculate purchase total
    purchase.recompute_total()

    # ============================================
    # STEP 5: COMMIT - Save everything
    # ============================================
    db.session.commit()

    return jsonify(
        {
            "status": "success",
            "purchase_id": purchase.id,
            "total": float(purchase.total_amount),
        }
    )
