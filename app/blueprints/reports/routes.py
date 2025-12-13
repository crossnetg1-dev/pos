from decimal import Decimal
from datetime import datetime

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models import Customer, Product, Sale, SaleItem
from app.utils import log_activity, log_stock_movement, permission_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/", methods=["GET"])
@login_required
@permission_required('sales_view')
def overview():
    # Date filtering
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    search_query = request.args.get("q", "").strip()

    query = Sale.query.join(Customer, Sale.customer_id == Customer.id, isouter=True)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Sale.date >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            # Include the entire end date
            from datetime import timedelta
            end_dt = end_dt + timedelta(days=1)
            query = query.filter(Sale.date < end_dt)
        except ValueError:
            pass

    # Search by invoice number or customer name
    if search_query:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                Sale.invoice_no.like(f'%{search_query}%'),
                Customer.name.like(f'%{search_query}%')
            )
        )

    sales = query.order_by(Sale.date.desc()).all()

    # Calculate totals
    sales_count = len(sales)
    revenue = sum(float(sale.total_amount or 0) for sale in sales)
    customers = Customer.query.order_by(Customer.name).all()

    return render_template(
        "reports/overview.html",
        sales=sales,
        sales_count=sales_count,
        revenue=revenue,
        start_date=start_date or "",
        end_date=end_date or "",
        search_query=search_query,
        customers=customers,
    )


@reports_bp.route("/sale/<int:sale_id>", methods=["GET"])
@login_required
@permission_required('sales_view')
def get_sale_details(sale_id: int):
    sale = db.session.get(Sale, sale_id)
    if not sale:
        return jsonify({"error": "Sale not found"}), 404

    items = [
        {
            "sale_item_id": item.id,
            "product_name": item.product.name if item.product else "Unknown",
            "quantity": item.quantity,
            "returned_quantity": item.returned_quantity or 0,
            "available_to_return": item.quantity - (item.returned_quantity or 0),
            "price": float(item.price or 0),
            "subtotal": float(item.subtotal or 0),
        }
        for item in sale.items
    ]

    return jsonify(
        {
            "id": sale.id,
            "invoice_no": sale.invoice_no,
            "date": sale.date.strftime("%Y-%m-%d %H:%M"),
            "customer": sale.customer.name if sale.customer else "Walk-in Customer",
            "customer_id": sale.customer_id,
            "payment_method": sale.payment_method,
            "status": sale.status,
            "returned_amount": float(sale.returned_amount or 0),
            "subtotal": float(sum(item.subtotal or 0 for item in sale.items)),
            "tax": float(sale.tax or 0),
            "discount": float(sale.discount or 0),
            "total": float(sale.total_amount or 0),
            "items": items,
        }
    )


@reports_bp.route("/sale/<int:sale_id>/return", methods=["POST"])
@login_required
@permission_required('sales_edit')
def return_sale(sale_id: int):
    """Handle sales return/refund."""
    if not request.is_json:
        return jsonify({"error": "JSON body required"}), 400
    
    data = request.get_json()
    return_items = data.get("return_items", [])  # [{sale_item_id, quantity}]
    
    if not return_items:
        return jsonify({"error": "No items to return"}), 400
    
    sale = db.session.get(Sale, sale_id)
    if not sale:
        return jsonify({"error": "Sale not found"}), 404
    
    try:
        total_returned = Decimal('0')
        
        for return_item in return_items:
            sale_item_id = return_item.get("sale_item_id")
            return_qty = int(return_item.get("quantity", 0))
            
            if return_qty <= 0:
                continue
            
            sale_item = db.session.get(SaleItem, sale_item_id)
            if not sale_item or sale_item.sale_id != sale_id:
                continue
            
            # Check if already returned more than available
            available_to_return = sale_item.quantity - (sale_item.returned_quantity or 0)
            if return_qty > available_to_return:
                return jsonify({"error": f"Cannot return more than available for item {sale_item.product.name}"}), 400
            
            # Update returned quantity
            sale_item.returned_quantity = (sale_item.returned_quantity or 0) + return_qty
            
            # Increase stock
            product = sale_item.product
            product.stock = (product.stock or 0) + return_qty
            
            # Log stock movement
            log_stock_movement(
                product_id=product.id,
                quantity=return_qty,
                change_type='in',
                reason=f'Customer Return - Sale #{sale.invoice_no}',
                user_id=current_user.id
            )
            
            # Calculate returned amount
            returned_subtotal = Decimal(str(sale_item.price or 0)) * return_qty
            total_returned += returned_subtotal
        
        # Update sale status
        sale.returned_amount = Decimal(str(sale.returned_amount or 0)) + total_returned
        
        if sale.returned_amount >= sale.total_amount:
            sale.status = "returned"
        elif sale.returned_amount > 0:
            sale.status = "partially_returned"
        
        # Handle financial refund
        if sale.payment_method == "cash":
            # For cash, we could create a negative sale or just track the loss
            # For now, we'll just track it in returned_amount
            pass
        elif sale.payment_method == "credit" and sale.customer:
            # Decrease customer's credit balance
            customer = sale.customer
            current_balance = Decimal(str(customer.credit_balance or 0))
            customer.credit_balance = current_balance - total_returned
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": f"Return processed. {total_returned} Ks refunded.",
            "returned_amount": float(total_returned),
            "sale_status": sale.status
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Return failed: {str(e)}"}), 500


@reports_bp.route("/sale/<int:sale_id>/update", methods=["POST"])
@login_required
def update_sale(sale_id: int):
    """Update sale customer and payment method."""
    sale = db.session.get(Sale, sale_id)
    if not sale:
        flash("Sale not found.", "danger")
        return redirect(url_for("reports.overview"))

    old_payment_method = sale.payment_method
    old_customer_id = sale.customer_id
    old_total = Decimal(str(sale.total_amount or 0))

    # Update customer
    customer_id = request.form.get("customer_id")
    if customer_id:
        customer_id = int(customer_id) if customer_id else None
        sale.customer_id = customer_id
    else:
        sale.customer_id = None

    # Update payment method
    new_payment_method = request.form.get("payment_method", sale.payment_method)
    sale.payment_method = new_payment_method

    # Handle credit balance changes
    if old_payment_method != new_payment_method:
        # If was credit, reverse it
        if old_payment_method == "credit" and old_customer_id:
            old_customer = db.session.get(Customer, old_customer_id)
            if old_customer:
                current_balance = Decimal(str(old_customer.credit_balance or 0))
                old_total_decimal = Decimal(str(old_total))
                old_customer.credit_balance = max(Decimal('0'), current_balance - old_total_decimal)

        # If now credit, add it
        if new_payment_method == "credit" and sale.customer_id:
            new_customer = db.session.get(Customer, sale.customer_id)
            if new_customer:
                current_balance = Decimal(str(new_customer.credit_balance or 0))
                old_total_decimal = Decimal(str(old_total))
                new_customer.credit_balance = current_balance + old_total_decimal

    db.session.commit()
    flash("Sale updated successfully.", "success")
    return redirect(url_for("reports.overview"))


@reports_bp.route("/sale/<int:sale_id>/edit", methods=["GET"])
@login_required
@permission_required('sales_edit')
def edit_sale(sale_id: int):
    """Show edit sale form."""
    sale = db.session.get(Sale, sale_id)
    if not sale:
        flash("Sale not found.", "danger")
        return redirect(url_for("reports.overview"))

    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.order_by(Product.name).all()

    # Get sale items for pre-filling
    sale_items = [
        {
            "product_id": item.product_id,
            "product_name": item.product.name if item.product else "Unknown",
            "barcode": item.product.barcode if item.product else "",
            "quantity": item.quantity,
            "price": float(item.price or 0),
            "subtotal": float(item.subtotal or 0),
        }
        for item in sale.items
    ]

    return render_template(
        "reports/edit_sale.html",
        sale=sale,
        customers=customers,
        products=products,
        sale_items=sale_items,
    )


@reports_bp.route("/sale/<int:sale_id>/edit", methods=["POST"])
@login_required
@permission_required('sales_edit')
def update_sale_full(sale_id: int):
    """Update sale with smart stock adjustment based on quantity differences."""
    try:
        sale = db.session.get(Sale, sale_id)
        if not sale:
            return jsonify({"success": False, "message": "Sale not found"}), 404

        if not request.is_json:
            return jsonify({"success": False, "message": "JSON body required"}), 400

        data = request.get_json(silent=True) or {}
        new_items = data.get("cart_items") or data.get("items", [])
        customer_id = data.get("customer_id")
        payment_method = data.get("payment_method", "cash")
        sale_date = data.get("date")

        if not new_items:
            return jsonify({"success": False, "message": "No items provided"}), 400

        # Store old values for comparison
        old_payment_method = sale.payment_method
        old_customer_id = sale.customer_id
        old_total = Decimal(str(sale.total_amount or 0))

        # Create a map of old items by product_id for quick lookup
        old_items_map = {}
        for old_item in sale.items:
            product_id = old_item.product_id
            if product_id not in old_items_map:
                old_items_map[product_id] = []
            old_items_map[product_id].append({
                'sale_item': old_item,
                'quantity': old_item.quantity,
                'price': float(old_item.price or 0)
            })

        # Create a map of new items by product_id
        new_items_map = {}
        for item_data in new_items:
            product_id = item_data.get("product_id")
            if product_id and product_id > 0:
                if product_id not in new_items_map:
                    new_items_map[product_id] = []
                new_items_map[product_id].append({
                    'quantity': int(item_data.get("quantity", 0)),
                    'price': float(item_data.get("price", 0))
                })

        # ============================================
        # STEP 1: Validate Stock Availability (Before Making Changes)
        # ============================================
        all_product_ids = set(old_items_map.keys()) | set(new_items_map.keys())
        
        for product_id in all_product_ids:
            product = db.session.get(Product, product_id)
            if not product:
                continue
            
            # Calculate total old quantity for this product
            old_total_qty = sum(item['quantity'] for item in old_items_map.get(product_id, []))
            
            # Calculate total new quantity for this product
            new_total_qty = sum(item['quantity'] for item in new_items_map.get(product_id, []))
            
            # Calculate difference (positive = need more stock, negative = returning stock)
            quantity_diff = new_total_qty - old_total_qty
            
            # If increasing quantity, check if enough stock is available
            if quantity_diff > 0:
                current_stock = product.stock or 0
                if current_stock < quantity_diff:
                    return jsonify({
                        "success": False,
                        "message": f"Not enough stock for {product.name}. Available: {current_stock}, Required: {quantity_diff}"
                    }), 400

        # ============================================
        # STEP 2: Calculate Stock Adjustments (Diff-Based)
        # ============================================
        for product_id in all_product_ids:
            product = db.session.get(Product, product_id)
            if not product:
                continue
            
            old_total_qty = sum(item['quantity'] for item in old_items_map.get(product_id, []))
            new_total_qty = sum(item['quantity'] for item in new_items_map.get(product_id, []))
            diff = new_total_qty - old_total_qty
            
            if diff != 0:
                # Adjust stock: if diff is negative (quantity decreased), stock increases
                # if diff is positive (quantity increased), stock decreases
                current_stock = product.stock or 0
                new_stock = max(0, current_stock - diff)
                product.stock = new_stock
                
                # Log stock movement
                change_type = 'in' if diff < 0 else 'out'
                log_stock_movement(
                    product_id=product.id,
                    quantity=abs(diff),
                    change_type=change_type,
                    reason=f'Sale Edit #{sale.invoice_no} - Quantity changed from {old_total_qty} to {new_total_qty}',
                    user_id=current_user.id if current_user.is_authenticated else None
                )

        # ============================================
        # STEP 3: Handle Credit Balance Changes
        # ============================================
        # Revert old credit if payment was credit
        if old_payment_method == "credit" and old_customer_id:
            old_customer = db.session.get(Customer, old_customer_id)
            if old_customer:
                current_balance = Decimal(str(old_customer.credit_balance or 0))
                old_customer.credit_balance = max(Decimal('0'), current_balance - old_total)

        # ============================================
        # STEP 4: Delete Old SaleItems and Create New Ones
        # ============================================
        for old_item in sale.items:
            db.session.delete(old_item)
        
        db.session.flush()

        # ============================================
        # STEP 5: Create New SaleItems
        # ============================================
        new_subtotal = Decimal('0')
        for item_data in new_items:
            product_id = item_data.get("product_id")
            quantity = int(item_data.get("quantity", 0))
            price = float(item_data.get("price", 0))

            if not product_id or quantity <= 0:
                continue

            product = db.session.get(Product, product_id)
            if not product:
                continue

            item_subtotal = Decimal(str(price)) * quantity
            new_subtotal += item_subtotal

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                quantity=quantity,
                price=price,
                subtotal=float(item_subtotal),
            )
            db.session.add(sale_item)

        # Flush to ensure items are available for recompute_totals
        db.session.flush()

        # ============================================
        # STEP 6: Update Sale Header
        # ============================================
        sale.customer_id = int(customer_id) if customer_id else None
        sale.payment_method = payment_method
        if sale_date:
            try:
                sale.date = datetime.strptime(sale_date, "%Y-%m-%dT%H:%M")
            except ValueError:
                try:
                    sale.date = datetime.strptime(sale_date, "%Y-%m-%d %H:%M")
                except ValueError:
                    try:
                        sale.date = datetime.strptime(sale_date, "%Y-%m-%d")
                    except ValueError:
                        pass

        # Calculate New Total - Use recompute_totals or manual calculation
        try:
            sale.recompute_totals()
            new_total = Decimal(str(sale.total_amount or 0))
        except Exception:
            # Fallback: Manual calculation if recompute_totals fails
            tax = Decimal(str(sale.tax or 0))
            discount = Decimal(str(sale.discount or 0))
            new_total = new_subtotal + tax - discount
            sale.total_amount = float(new_total)

        # Apply new credit if payment is credit
        if payment_method == "credit" and sale.customer_id:
            new_customer = db.session.get(Customer, sale.customer_id)
            if new_customer:
                current_balance = Decimal(str(new_customer.credit_balance or 0))
                new_customer.credit_balance = current_balance + new_total

        # Commit all changes
        db.session.commit()
        
        # Log sale edit
        changes = []
        if old_payment_method != payment_method:
            changes.append(f"Payment: {old_payment_method} → {payment_method}")
        if old_total != new_total:
            changes.append(f"Total: {old_total} → {new_total}")
        if old_customer_id != customer_id:
            changes.append(f"Customer changed")
        
        change_details = ", ".join(changes) if changes else "Items updated"
        log_activity('SALE_EDIT', f'Edited sale {sale.invoice_no} (ID: {sale_id}): {change_details}')

        return jsonify({
            "success": True,
            "message": "Sale updated successfully!",
            "sale_id": sale.id,
            "total": float(new_total),
        }), 200

    except Exception as e:
        # Rollback on error
        db.session.rollback()
        
        # Print error to terminal for debugging
        import traceback
        print(f"\n{'='*60}")
        print(f"ERROR in update_sale_full (Sale ID: {sale_id}):")
        print(f"{'='*60}")
        traceback.print_exc()
        print(f"{'='*60}\n")
        
        # Return error response
        return jsonify({
            "success": False,
            "message": f"Error updating sale: {str(e)}"
        }), 500


@reports_bp.route("/sale/<int:sale_id>/delete", methods=["POST"])
@login_required
@permission_required('sales_delete')
def delete_sale(sale_id: int):
    """Delete a sale record and restore stock. Admin only."""
    sale = db.session.get(Sale, sale_id)
    if not sale:
        flash("Sale not found.", "danger")
        return redirect(url_for("reports.overview"))
    
    invoice_no = sale.invoice_no
    payment_method = sale.payment_method
    customer_id = sale.customer_id
    total_amount = Decimal(str(sale.total_amount or 0))
    
    # Stock Return: Loop through sale.items and add quantity back to Product.stock
    for item in sale.items:
        product = db.session.get(Product, item.product_id)
        if product:
            current_stock = product.stock or 0
            product.stock = current_stock + item.quantity
            
            # Log stock movement (Return to inventory)
            log_stock_movement(
                product_id=product.id,
                quantity=item.quantity,
                change_type='in',
                reason=f'Sale Deletion #{invoice_no} - Stock Returned',
                user_id=current_user.id if current_user.is_authenticated else None
            )
    
    # Credit Revert: If payment was 'Credit', subtract sale.total_amount from Customer.credit_balance
    if payment_method == "credit" and customer_id:
        customer = db.session.get(Customer, customer_id)
        if customer:
            current_balance = Decimal(str(customer.credit_balance or 0))
            customer.credit_balance = max(Decimal('0'), current_balance - total_amount)
    
    # Delete the sale record (SaleItems will be deleted via cascade)
    db.session.delete(sale)
    db.session.commit()
    
    # Audit Log
    log_activity('SALE_DELETE', f'Deleted sale {invoice_no} (ID: {sale_id}) - Stock returned, Credit reverted if applicable')
    
    flash(f"Sale {invoice_no} deleted successfully. Stock has been returned to inventory.", "success")
    return redirect(url_for("reports.overview"))
