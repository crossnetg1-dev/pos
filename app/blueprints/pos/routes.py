from decimal import Decimal
from datetime import datetime
import re

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.models import Customer, Product, Sale, SaleItem
from app.utils import log_activity, log_stock_movement, permission_required

pos_bp = Blueprint("pos", __name__, url_prefix="/pos")


def generate_invoice_number():
    """
    Generate sequential invoice number in format INV-00001, INV-00002, etc.
    """
    # Query the last sale record ordered by ID (most reliable)
    last_sale = Sale.query.order_by(Sale.id.desc()).first()
    
    if not last_sale:
        # No sales exist, start with INV-00001
        return "INV-00001"
    
    # Extract number from invoice_no (e.g., "INV-00050" -> 50, "INV-1765449110" -> 1765449110)
    match = re.search(r'INV-(\d+)', last_sale.invoice_no)
    if match:
        last_number = int(match.group(1))
        # If the number is very large (timestamp format), use the sale ID instead
        if last_number > 1000000:  # Likely a timestamp
            next_number = last_sale.id + 1
        else:
            next_number = last_number + 1
    else:
        # If format doesn't match, use sale ID + 1
        next_number = last_sale.id + 1
    
    # Format with zero padding (5 digits)
    return f"INV-{next_number:05d}"


@pos_bp.route("/", methods=["GET"])
@login_required
@permission_required('pos_access')
def cart():
    from app.models import StoreSetting
    products = Product.query.order_by(Product.name.asc()).all()
    customers = Customer.query.order_by(Customer.name.asc()).all()
    store_settings = StoreSetting.get_settings()
    return render_template("pos/index.html", products=products, customers=customers, store=store_settings)


@pos_bp.route("/checkout", methods=["POST"])
@login_required
@permission_required('pos_access')
def checkout():
    if not request.is_json:
        return jsonify({"error": "invalid_request", "message": "JSON body required"}), 400

    data = request.get_json(silent=True) or {}
    cart_items = data.get("cart_items") or []
    tax = data.get("tax", 0) or 0
    discount = data.get("discount", 0) or 0
    payment_method = data.get("payment_method", "cash")
    customer_id = data.get("customer_id")

    if not cart_items:
        return jsonify({"error": "empty_cart", "message": "No items provided"}), 400

    invoice_no = generate_invoice_number()
    sale = Sale(
        invoice_no=invoice_no,
        total_amount=0,
        tax=tax,
        discount=discount,
        payment_method=payment_method,
        user_id=current_user.id,
        customer_id=customer_id,
    )
    db.session.add(sale)
    db.session.flush()  # ensure sale.id

    for item in cart_items:
        product_id = item.get("product_id")
        quantity = int(item.get("quantity", 0) or 0)
        price = item.get("price")

        if not product_id or quantity <= 0:
            continue

        product = db.session.get(Product, product_id)
        if not product:
            continue

        unit_price = price if price is not None else product.price
        subtotal = (unit_price or 0) * quantity

        # Deduct stock
        product.stock = (product.stock or 0) - quantity

        # Log stock movement
        log_stock_movement(
            product_id=product.id,
            quantity=quantity,
            change_type='out',
            reason=f'Sale #{sale.invoice_no}',
            user_id=current_user.id
        )

        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity=quantity,
            price=unit_price,
            subtotal=subtotal,
        )
        db.session.add(sale_item)

    sale.recompute_totals()

    # If credit payment, update customer's credit balance
    customer_balance = None
    if payment_method == "credit" and customer_id:
        customer = db.session.get(Customer, customer_id)
        if customer:
            # Use Decimal-safe addition
            current_balance = Decimal(str(customer.credit_balance or 0))
            sale_total = Decimal(str(sale.total_amount or 0))
            customer.credit_balance = current_balance + sale_total
            customer_balance = float(customer.credit_balance)

    db.session.commit()
    
    # Log sale creation
    customer_name = ""
    if customer_id:
        customer = db.session.get(Customer, customer_id)
        if customer:
            customer_name = f" (Customer: {customer.name})"
    log_activity('SALE_CREATE', f'Created sale {sale.invoice_no} - Total: {sale.total_amount}, Payment: {payment_method}{customer_name}')

    return jsonify(
        {
            "status": "success",
            "sale_id": sale.id,
            "invoice_no": sale.invoice_no,
            "total": float(sale.total_amount),
            "payment_method": payment_method,
            "customer_id": customer_id,
            "customer_balance": customer_balance,
        }
    )
