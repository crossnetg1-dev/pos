import os
import base64
from io import BytesIO
from flask import Blueprint, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
import pandas as pd
from datetime import datetime
import pytz
import barcode
from barcode.writer import ImageWriter

from app import db
from app.models import Category, Product, StockMovement, Unit
from app.utils import log_stock_movement, permission_required

# Timezone configuration
MYANMAR_TZ = pytz.timezone('Asia/Yangon')

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")

# Image upload configuration
# Get the app root directory (3 levels up from this file: app/blueprints/inventory/routes.py)
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
UPLOAD_FOLDER = os.path.join(APP_ROOT, "app", "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@inventory_bp.route("/", methods=["GET"])
@login_required
@permission_required('inventory_view')
def products():
    products_list = Product.query.order_by(Product.name).all()
    
    # Convert to JSON-serializable format for frontend
    products_json = [
        {
            "id": p.id,
            "name": p.name,
            "barcode": p.barcode or "",
            "stock": int(p.stock or 0)
        }
        for p in products_list
    ]
    
    # Fetch categories organized by parent > child
    main_categories = Category.query.filter_by(parent_id=None).order_by(Category.name).all()
    subcategories = Category.query.filter(Category.parent_id.isnot(None)).order_by(Category.name).all()
    
    # Organize categories for template (parent with children)
    categories_organized = []
    for main_cat in main_categories:
        categories_organized.append(main_cat)
        # Add subcategories under this parent
        for sub_cat in subcategories:
            if sub_cat.parent_id == main_cat.id:
                categories_organized.append(sub_cat)
    
    # Also include subcategories that might not have a parent in the list
    for sub_cat in subcategories:
        if sub_cat not in categories_organized:
            categories_organized.append(sub_cat)
    
    units = Unit.query.order_by(Unit.name).all()
    
    return render_template(
        "inventory/products.html",
        products=products_list,
        products_json=products_json,
        categories=categories_organized,
        main_categories=main_categories,
        units=units
    )


@inventory_bp.route("/product", methods=["POST"])
@login_required
@permission_required('inventory_edit')
def add_product():
    name = request.form.get("name", "").strip()
    barcode = request.form.get("barcode", "").strip()
    try:
        price = float(request.form.get("price", 0) or 0)
        cost = float(request.form.get("cost", 0) or 0)
        stock = int(request.form.get("stock", 0) or 0)
        min_stock = int(request.form.get("min_stock", 0) or 0)
    except (ValueError, TypeError):
        flash("Invalid numeric values for price, cost, stock, or min_stock.", "danger")
        return redirect(url_for("inventory.products"))
    
    # Validation: Ensure price, cost, and stock are not negative
    if price < 0:
        flash("Price cannot be negative.", "danger")
        return redirect(url_for("inventory.products"))
    if cost < 0:
        flash("Cost cannot be negative.", "danger")
        return redirect(url_for("inventory.products"))
    if stock < 0:
        flash("Stock cannot be negative.", "danger")
        return redirect(url_for("inventory.products"))
    if min_stock < 0:
        flash("Minimum stock cannot be negative.", "danger")
        return redirect(url_for("inventory.products"))
    
    if not name or not barcode:
        flash("Name and barcode are required.", "warning")
        return redirect(url_for("inventory.products"))

    if Product.query.filter_by(barcode=barcode).first():
        flash("Barcode already exists.", "danger")
        return redirect(url_for("inventory.products"))

    category_id = request.form.get("category_id")
    category_id = int(category_id) if category_id else None
    
    unit_id = request.form.get("unit_id")
    unit_id = int(unit_id) if unit_id else None

    # Handle image: Priority: image_url > image_file > default.jpg
    image_url = request.form.get("image_url", "").strip()
    image_file = None
    
    if image_url:
        # Use image URL if provided
        image_file = None  # Clear file if URL is provided
    elif "image" in request.files:
        # Handle file upload
        file = request.files["image"]
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_")
            filename = timestamp + filename
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            image_file = filename
            image_url = None  # Clear URL if file is uploaded
    else:
        # Default image for new products
        image_file = "default.jpg"

    product = Product(
        name=name,
        barcode=barcode,
        price=price,
        cost=cost,
        stock=stock or 0,
        min_stock=min_stock or 0,
        category_id=category_id,
        unit_id=unit_id,
        image_url=image_url if image_url else None,
        image_file=image_file,
    )
    db.session.add(product)
    db.session.commit()

    flash("Product created.", "success")
    return redirect(url_for("inventory.products"))


@inventory_bp.route("/product/<int:product_id>/update", methods=["POST"])
@login_required
@permission_required('inventory_edit')
def update_product(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("inventory.products"))

    # Store old values for logging
    old_name = product.name
    old_price = product.price
    old_cost = product.cost
    old_stock = product.stock

    # Validate and convert numeric inputs
    try:
        new_price = float(request.form.get("price", product.price) or product.price)
        new_cost = float(request.form.get("cost", product.cost) or product.cost)
        new_stock = int(request.form.get("stock", product.stock) or product.stock)
        new_min_stock = int(request.form.get("min_stock", product.min_stock) or product.min_stock)
    except (ValueError, TypeError):
        flash("Invalid numeric values for price, cost, stock, or min_stock.", "danger")
        return redirect(url_for("inventory.products"))
    
    # Validation: Ensure price, cost, and stock are not negative
    if new_price < 0:
        flash("Price cannot be negative.", "danger")
        return redirect(url_for("inventory.products"))
    if new_cost < 0:
        flash("Cost cannot be negative.", "danger")
        return redirect(url_for("inventory.products"))
    if new_stock < 0:
        flash("Stock cannot be negative.", "danger")
        return redirect(url_for("inventory.products"))
    if new_min_stock < 0:
        flash("Minimum stock cannot be negative.", "danger")
        return redirect(url_for("inventory.products"))

    product.name = request.form.get("name", product.name).strip()
    product.barcode = request.form.get("barcode", product.barcode).strip()
    product.price = new_price
    product.cost = new_cost
    product.stock = new_stock
    product.min_stock = new_min_stock
    category_id = request.form.get("category_id")
    product.category_id = int(category_id) if category_id else None
    unit_id = request.form.get("unit_id")
    product.unit_id = int(unit_id) if unit_id else None

    # Handle image: Priority: image_url > image_file
    image_url = request.form.get("image_url", "").strip()
    
    if image_url:
        # Use image URL if provided
        product.image_url = image_url
        # Delete old uploaded file if switching to URL
        if product.image_file and product.image_file != "default.jpg":
            old_filepath = os.path.join(UPLOAD_FOLDER, product.image_file)
            if os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except OSError:
                    pass
            product.image_file = None
    elif "image" in request.files:
        # Handle file upload
        file = request.files["image"]
        if file and file.filename and allowed_file(file.filename):
            # Delete old image if exists (and not default)
            if product.image_file and product.image_file != "default.jpg":
                old_filepath = os.path.join(UPLOAD_FOLDER, product.image_file)
                if os.path.exists(old_filepath):
                    try:
                        os.remove(old_filepath)
                    except OSError:
                        pass
            
            # Save new image
            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_")
            filename = timestamp + filename
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            product.image_file = filename
            product.image_url = None  # Clear URL if file is uploaded
    # If neither is provided, keep existing image

    db.session.commit()
    
    # Log changes
    changes = []
    if old_name != product.name:
        changes.append(f"Name: {old_name} → {product.name}")
    if old_price != product.price:
        changes.append(f"Price: {old_price} → {product.price}")
    if old_cost != product.cost:
        changes.append(f"Cost: {old_cost} → {product.cost}")
    if old_stock != product.stock:
        changes.append(f"Stock: {old_stock} → {product.stock}")
    
    if changes:
        log_activity('PRODUCT_EDIT', f'Updated product {product.name} (ID: {product_id}): {", ".join(changes)}')
    else:
        log_activity('PRODUCT_EDIT', f'Updated product {product.name} (ID: {product_id})')
    
    flash("Product updated.", "success")
    return redirect(url_for("inventory.products"))


@inventory_bp.route("/product/<int:product_id>/delete", methods=["POST"])
@login_required
@permission_required('inventory_edit')
def delete_product(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("inventory.products"))
    
    product_name = product.name
    product_barcode = product.barcode
    db.session.delete(product)
    db.session.commit()
    log_activity('PRODUCT_DELETE', f'Deleted product: {product_name} (Barcode: {product_barcode}, ID: {product_id})')
    flash("Product deleted.", "info")
    return redirect(url_for("inventory.products"))


@inventory_bp.route("/product/<int:product_id>/restock", methods=["POST"])
@login_required
def restock_product(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("inventory.products"))

    quantity = request.form.get("quantity", 0)
    cost_price = request.form.get("cost_price")
    reason = request.form.get("reason", "Restock").strip()

    try:
        quantity = int(quantity)
        if quantity <= 0:
            flash("Quantity must be greater than 0.", "warning")
            return redirect(url_for("inventory.products"))

        # Update stock
        product.stock = (product.stock or 0) + quantity

        # Update cost if provided (using latest cost)
        if cost_price:
            try:
                product.cost = float(cost_price)
            except ValueError:
                pass

        # Log stock movement
        log_stock_movement(
            product_id=product.id,
            quantity=quantity,
            change_type='in',
            reason=reason,
            user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.commit()

        flash(f"Restocked {quantity} units of {product.name}.", "success")
    except ValueError:
        flash("Invalid quantity.", "danger")

    return redirect(url_for("inventory.products"))


@inventory_bp.route("/export/data", methods=["GET"])
@login_required
@permission_required('inventory_view')
def export_data():
    """Export all products to Excel file."""
    products = Product.query.order_by(Product.name).all()
    
    # Prepare data
    data = []
    for product in products:
        category_name = ""
        if product.category:
            # Handle hierarchical categories
            if product.category.parent:
                category_name = f"{product.category.parent.name} > {product.category.name}"
            else:
                category_name = product.category.name
        
        unit_name = product.unit.short_name if product.unit else ""
        
        data.append({
            "Name": product.name or "",
            "Barcode": product.barcode or "",
            "Category": category_name,
            "Price": float(product.price or 0),
            "Cost": float(product.cost or 0),
            "Stock": int(product.stock or 0),
            "Unit": unit_name,
            "Min Stock": int(product.min_stock or 0)
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Products')
    
    output.seek(0)
    
    # Generate filename with timestamp
    filename = f"products_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


@inventory_bp.route("/export/template", methods=["GET"])
@login_required
@permission_required('inventory_view')
def export_template():
    """Export empty Excel template with headers."""
    # Create DataFrame with headers only
    df = pd.DataFrame(columns=[
        "Name *",
        "Barcode *",
        "Category",
        "Price *",
        "Cost",
        "Stock",
        "Unit",
        "Min Stock"
    ])
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Products')
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name="products_import_template.xlsx"
    )


@inventory_bp.route("/import", methods=["POST"])
@login_required
@permission_required('inventory_edit')
def import_data():
    """Import products from Excel file."""
    if 'file' not in request.files:
        flash("No file uploaded.", "danger")
        return redirect(url_for("inventory.products"))
    
    file = request.files['file']
    if file.filename == '':
        flash("No file selected.", "danger")
        return redirect(url_for("inventory.products"))
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash("Invalid file format. Please upload an Excel file (.xlsx or .xls).", "danger")
        return redirect(url_for("inventory.products"))
    
    try:
        # Read Excel file
        df = pd.read_excel(file, engine='openpyxl')
        
        # Check mandatory columns
        required_columns = ['Name *', 'Barcode *', 'Price *']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            flash(f"Missing required columns: {', '.join(missing_columns)}", "danger")
            return redirect(url_for("inventory.products"))
        
        # Map column names (handle both with and without *)
        # Create a mapping dictionary for columns that exist in the DataFrame
        column_mapping = {}
        for col in df.columns:
            col_str = str(col).strip()
            if col_str in ['Name *', 'Name']:
                column_mapping[col] = 'name'
            elif col_str in ['Barcode *', 'Barcode']:
                column_mapping[col] = 'barcode'
            elif col_str == 'Category':
                column_mapping[col] = 'category'
            elif col_str in ['Price *', 'Price']:
                column_mapping[col] = 'price'
            elif col_str == 'Cost':
                column_mapping[col] = 'cost'
            elif col_str == 'Stock':
                column_mapping[col] = 'stock'
            elif col_str == 'Unit':
                column_mapping[col] = 'unit'
            elif col_str in ['Min Stock', 'Min Stock *']:
                column_mapping[col] = 'min_stock'
        
        # Rename columns
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        # Ensure required columns exist
        if 'name' not in df.columns or 'barcode' not in df.columns or 'price' not in df.columns:
            flash("Required columns (Name, Barcode, Price) must be present.", "danger")
            return redirect(url_for("inventory.products"))
        
        imported_count = 0
        updated_count = 0
        errors = []
        
        # Process each row
        for index, row in df.iterrows():
            try:
                name = str(row.get('name', '')).strip()
                barcode = str(row.get('barcode', '')).strip()
                price = row.get('price', 0)
                
                # Skip empty rows
                if not name or not barcode or pd.isna(price):
                    continue
                
                # Convert price to float
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    errors.append(f"Row {index + 2}: Invalid price value")
                    continue
                
                # Check if product exists by barcode
                existing_product = Product.query.filter_by(barcode=barcode).first()
                
                # Handle Category (smart creation)
                category_id = None
                category_name = str(row.get('category', '')).strip()
                if category_name:
                    # Check if category exists
                    category = Category.query.filter_by(name=category_name).first()
                    if not category:
                        # Create new category
                        category = Category(name=category_name)
                        db.session.add(category)
                        db.session.flush()
                    category_id = category.id
                
                # Handle Unit
                unit_id = None
                unit_name = str(row.get('unit', '')).strip()
                if unit_name:
                    # Try to find by short_name first, then by name
                    unit = Unit.query.filter(
                        (Unit.short_name == unit_name) | (Unit.name == unit_name)
                    ).first()
                    if not unit:
                        # Create new unit
                        unit = Unit(name=unit_name, short_name=unit_name)
                        db.session.add(unit)
                        db.session.flush()
                    unit_id = unit.id
                
                # Get other fields
                cost = float(row.get('cost', 0)) if pd.notna(row.get('cost')) else 0
                stock = int(row.get('stock', 0)) if pd.notna(row.get('stock')) else 0
                min_stock = int(row.get('min_stock', 0)) if pd.notna(row.get('min_stock')) else 0
                
                if existing_product:
                    # Update existing product
                    existing_product.name = name
                    existing_product.price = price
                    existing_product.cost = cost
                    existing_product.stock = stock
                    existing_product.min_stock = min_stock
                    existing_product.category_id = category_id
                    existing_product.unit_id = unit_id
                    updated_count += 1
                else:
                    # Create new product
                    new_product = Product(
                        name=name,
                        barcode=barcode,
                        price=price,
                        cost=cost,
                        stock=stock,
                        min_stock=min_stock,
                        category_id=category_id,
                        unit_id=unit_id
                    )
                    db.session.add(new_product)
                    imported_count += 1
                
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
                continue
        
        # Commit all changes
        db.session.commit()
        
        # Flash success message
        message = f"Import completed! {imported_count} new products imported, {updated_count} products updated."
        if errors:
            message += f" {len(errors)} errors occurred."
        flash(message, "success" if not errors else "warning")
        
        if errors and len(errors) <= 10:
            for error in errors:
                flash(error, "warning")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Import failed: {str(e)}", "danger")
    
    return redirect(url_for("inventory.products"))


@inventory_bp.route("/adjust", methods=["POST"])
@login_required
@permission_required('inventory_edit')
def adjust_stock():
    """Handle stock adjustment for damage, loss, etc."""
    if not request.is_json:
        return jsonify({"error": "JSON body required"}), 400
    
    data = request.get_json()
    product_id = data.get("product_id")
    quantity = int(data.get("quantity", 0))
    adjustment_type = data.get("type", "Damage")  # Damage, Expired, Lost, Theft
    
    if not product_id or quantity <= 0:
        return jsonify({"error": "Invalid product ID or quantity"}), 400
    
    if adjustment_type not in ["Damage", "Expired", "Lost", "Theft"]:
        return jsonify({"error": "Invalid adjustment type"}), 400
    
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    
    if quantity > (product.stock or 0):
        return jsonify({"error": "Cannot adjust more than available stock"}), 400
    
    try:
        # Decrease stock
        product.stock = (product.stock or 0) - quantity
        
        # Log stock movement
        log_stock_movement(
            product_id=product.id,
            quantity=quantity,
            change_type='out',
            reason=f'{adjustment_type} - Manual Adjustment',
            user_id=current_user.id
        )
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": f"Stock adjusted. {quantity} units removed due to {adjustment_type}.",
            "new_stock": product.stock
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Adjustment failed: {str(e)}"}), 500


def generate_barcode_base64(barcode_number: str) -> str:
    """Generate a Code128 barcode and return as Base64 encoded PNG string."""
    try:
        # Create Code128 barcode
        code128 = barcode.get_barcode_class('code128')
        barcode_instance = code128(barcode_number, writer=ImageWriter())
        
        # Generate image to BytesIO
        buffer = BytesIO()
        barcode_instance.write(buffer, options={
            'module_width': 0.5,
            'module_height': 15,
            'quiet_zone': 2,
            'font_size': 10,
            'text_distance': 5,
            'background': 'white',
            'foreground': 'black',
        })
        buffer.seek(0)
        
        # Convert to Base64
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
    except Exception as e:
        # Return placeholder if barcode generation fails
        return None


@inventory_bp.route("/labels", methods=["GET"])
@login_required
@permission_required('inventory_view')
def labels():
    """Barcode Label Generator Dashboard."""
    products = Product.query.order_by(Product.name).all()
    
    # Convert to JSON-serializable format for frontend
    products_json = [
        {
            "id": p.id,
            "name": p.name,
            "barcode": p.barcode or "",
            "price": float(p.price or 0)
        }
        for p in products
    ]
    
    return render_template("inventory/labels.html", products=products, products_json=products_json)


@inventory_bp.route("/labels/print", methods=["POST"])
@login_required
@permission_required('inventory_view')
def print_labels():
    """Generate and render print layout for barcode labels."""
    # Accept JSON request
    if not request.is_json:
        return jsonify({"error": "JSON body required"}), 400
    
    data = request.get_json()
    label_items = data.get("items", [])  # [{product_id, quantity}]
    paper_size = data.get("paper_size", "thermal_50x30")  # thermal_50x30, continuous, a4_grid
    
    if not label_items:
        return jsonify({"error": "No items to print"}), 400
    
    # Fetch products and generate barcodes
    labels_data = []
    for item in label_items:
        product_id = item.get("product_id")
        quantity = int(item.get("quantity", 1))
        
        product = db.session.get(Product, product_id)
        if not product:
            continue
        
        # Generate barcode for this product
        barcode_img = generate_barcode_base64(product.barcode)
        
        # Add to labels (repeat based on quantity)
        for _ in range(quantity):
            labels_data.append({
                "product": product,
                "barcode_image": barcode_img,
                "barcode_number": product.barcode
            })
    
    if not labels_data:
        return jsonify({"error": "No valid products found"}), 400
    
    # Get store settings for label header
    from app.models import StoreSetting
    store_settings = StoreSetting.get_settings()
    
    # Return HTML directly (frontend will render in new window)
    return render_template(
        "inventory/print_labels.html",
        labels=labels_data,
        paper_size=paper_size,
        store=store_settings
    )


@inventory_bp.route("/history/<int:product_id>", methods=["GET"])
@login_required
def get_stock_history(product_id: int):
    """API endpoint to get stock history for a product."""
    product = db.session.get(Product, product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    movements = (
        StockMovement.query.filter_by(product_id=product_id)
        .order_by(StockMovement.date.desc())
        .all()
    )

    history = [
        {
            "date": movement.date.strftime("%Y-%m-%d %H:%M"),
            "type": movement.change_type,
            "quantity": movement.quantity,
            "reason": movement.reason or "",
        }
        for movement in movements
    ]

    return jsonify({"history": history})