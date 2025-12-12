from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models import Customer
from app.utils import log_activity, permission_required

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


@customers_bp.route("/", methods=["GET"])
@login_required
@permission_required('customers_manage')
def index():
    customers = Customer.query.order_by(Customer.name.asc()).all()
    return render_template("customers/index.html", customers=customers)


@customers_bp.route("/", methods=["POST"])
@login_required
@permission_required('customers_manage')
def create():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    credit_balance = request.form.get("credit_balance", 0) or 0

    if not name:
        flash("Name is required.", "warning")
        return redirect(url_for("customers.index"))

    customer = Customer(
        name=name,
        phone=phone,
        address=address,
        credit_balance=credit_balance,
    )
    db.session.add(customer)
    db.session.commit()
    flash("Customer added.", "success")
    return redirect(url_for("customers.index"))


@customers_bp.route("/<int:customer_id>/update", methods=["POST"])
@login_required
@permission_required('customers_manage')
def update(customer_id: int):
    customer = db.session.get(Customer, customer_id)
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for("customers.index"))

    customer.name = request.form.get("name", customer.name).strip()
    customer.phone = request.form.get("phone", customer.phone).strip()
    customer.address = request.form.get("address", customer.address).strip()
    customer.credit_balance = request.form.get("credit_balance", customer.credit_balance) or customer.credit_balance
    db.session.commit()
    flash("Customer updated.", "success")
    return redirect(url_for("customers.index"))


@customers_bp.route("/<int:customer_id>/delete", methods=["POST"])
@login_required
@permission_required('customers_manage')
def delete(customer_id: int):
    customer = db.session.get(Customer, customer_id)
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for("customers.index"))
    db.session.delete(customer)
    db.session.commit()
    flash("Customer deleted.", "info")
    return redirect(url_for("customers.index"))


@customers_bp.route("/pay_debt/<int:customer_id>", methods=["POST"])
@login_required
@permission_required('customers_manage')
def pay_debt(customer_id: int):
    """Process a debt repayment from a customer."""
    customer = db.session.get(Customer, customer_id)
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for("customers.index"))
    
    # Get form data
    try:
        amount = Decimal(str(request.form.get("amount", 0) or 0))
        payment_method = request.form.get("payment_method", "cash").strip().lower()
        note = request.form.get("note", "").strip()
    except (ValueError, TypeError):
        flash("Invalid payment amount.", "danger")
        return redirect(url_for("customers.index"))
    
    # Validation: Ensure amount is positive
    if amount <= 0:
        flash("Payment amount must be greater than zero.", "warning")
        return redirect(url_for("customers.index"))
    
    # Validation: Ensure amount does not exceed credit_balance
    current_balance = Decimal(str(customer.credit_balance or 0))
    if amount > current_balance:
        flash(f"Payment amount ({amount:,.0f} Ks) cannot exceed current debt ({current_balance:,.0f} Ks).", "warning")
        return redirect(url_for("customers.index"))
    
    # Subtract the amount from customer.credit_balance
    customer.credit_balance = max(Decimal('0'), current_balance - amount)
    
    # Log the activity
    payment_method_display = payment_method.upper() if payment_method in ['kpay', 'wavepay'] else payment_method.title()
    log_details = f"Received {amount:,.0f} Ks debt payment from {customer.name} via {payment_method_display}"
    if note:
        log_details += f" (Note: {note})"
    log_activity('DEBT_PAYMENT', log_details)
    
    # Commit changes
    db.session.commit()
    
    # Success message
    remaining_balance = customer.credit_balance
    if remaining_balance > 0:
        flash(f"Payment of {amount:,.0f} Ks received. Remaining debt: {remaining_balance:,.0f} Ks", "success")
    else:
        flash(f"Payment of {amount:,.0f} Ks received. Debt fully paid!", "success")
    
    return redirect(url_for("customers.index"))
