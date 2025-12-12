from datetime import date, datetime, time, timedelta

import pytz

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.models import AuditLog, Category, Customer, Product, Sale, SaleItem
from app.utils import permission_required

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
@permission_required('dashboard_view')
def dashboard():
    # Use Myanmar timezone (Asia/Yangon)
    myanmar_tz = pytz.timezone('Asia/Yangon')
    now_myanmar = datetime.now(myanmar_tz)
    today = now_myanmar.date()
    month_start = date(today.year, today.month, 1)
    
    # Calculate start and end of today in Myanmar timezone (convert to UTC for DB comparison)
    today_start_myanmar = myanmar_tz.localize(datetime.combine(today, time.min))
    today_end_myanmar = myanmar_tz.localize(datetime.combine(today, time.max))
    today_start_utc = today_start_myanmar.astimezone(pytz.UTC).replace(tzinfo=None)
    today_end_utc = today_end_myanmar.astimezone(pytz.UTC).replace(tzinfo=None)
    
    # Calculate start of month in Myanmar timezone
    month_start_myanmar = myanmar_tz.localize(datetime.combine(month_start, time.min))
    month_start_utc = month_start_myanmar.astimezone(pytz.UTC).replace(tzinfo=None)

    # Today's Sales (Total revenue for current day in Myanmar timezone)
    today_sales_revenue = (
        db.session.query(func.sum(Sale.total_amount))
        .filter(Sale.date >= today_start_utc)
        .filter(Sale.date < today_end_utc)
        .scalar()
        or 0
    )
    # Convert Decimal to float for arithmetic operations
    today_sales_revenue = float(today_sales_revenue or 0)

    # Monthly Sales (Total revenue for current month, 1st to now)
    monthly_sales_revenue = (
        db.session.query(func.sum(Sale.total_amount))
        .filter(Sale.date >= month_start_utc)
        .filter(Sale.date < today_end_utc)
        .scalar()
        or 0
    )
    # Convert Decimal to float
    monthly_sales_revenue = float(monthly_sales_revenue or 0)

    # Today's Profit: (selling price - cost price) * quantity for items sold today
    today_sales = (
        Sale.query.filter(Sale.date >= today_start_utc)
        .filter(Sale.date < today_end_utc)
        .all()
    )
    today_profit = 0.0
    for sale in today_sales:
        for item in sale.items:
            if item.product:
                selling_price = float(item.price or 0)
                cost_price = float(item.product.cost or 0)
                quantity = item.quantity or 0
                profit_per_item = (selling_price - cost_price) * quantity
                today_profit += profit_per_item

    # Monthly Profit: (selling price - cost price) * quantity for items sold this month
    monthly_sales = (
        Sale.query.filter(Sale.date >= month_start_utc)
        .filter(Sale.date < today_end_utc)
        .all()
    )
    monthly_profit = 0.0
    for sale in monthly_sales:
        for item in sale.items:
            if item.product:
                selling_price = float(item.price or 0)
                cost_price = float(item.product.cost or 0)
                quantity = item.quantity or 0
                profit_per_item = (selling_price - cost_price) * quantity
                monthly_profit += profit_per_item

    # Top 5 Best Selling Products (based on quantity sold this month)
    # Use timezone-aware UTC ranges for consistency with other dashboard queries
    top_products_query = (
        db.session.query(
            Product.id,
            Product.name,
            func.sum(SaleItem.quantity).label('total_quantity')
        )
        .join(SaleItem, Product.id == SaleItem.product_id)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .filter(Sale.date >= month_start_utc)
        .filter(Sale.date < today_end_utc)
        .group_by(Product.id, Product.name)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(5)
        .all()
    )
    top_products = [
        {"name": name, "quantity": int(total_qty)}
        for _, name, total_qty in top_products_query
    ]

    # Legacy metrics (keeping for compatibility)
    today_orders = (
        db.session.query(func.count(Sale.id))
        .filter(Sale.date >= today_start_utc)
        .filter(Sale.date < today_end_utc)
        .scalar()
        or 0
    )
    low_stock_count = (
        db.session.query(func.count(Product.id))
        .filter(Product.stock <= Product.min_stock)
        .scalar()
        or 0
    )
    total_customers = db.session.query(func.count(Customer.id)).scalar() or 0

    recent_sales = (
        Sale.query.order_by(Sale.date.desc())
        .limit(5)
        .all()
    )

    # Calculate sales for last 7 days (for chart)
    dates = []
    sales_data = []
    for i in range(6, -1, -1):  # Last 7 days (6 days ago to today)
        day = today - timedelta(days=i)
        day_start_myanmar = myanmar_tz.localize(datetime.combine(day, datetime.min.time()))
        day_end_myanmar = myanmar_tz.localize(datetime.combine(day, datetime.max.time()))
        day_start_utc = day_start_myanmar.astimezone(pytz.UTC).replace(tzinfo=None)
        day_end_utc = day_end_myanmar.astimezone(pytz.UTC).replace(tzinfo=None)
        
        day_sales = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(Sale.date >= day_start_utc)
            .filter(Sale.date < day_end_utc)
            .scalar()
            or 0
        )
        # Format day name (Mon, Tue, Wed, etc.)
        day_name = day.strftime('%a')
        dates.append(day_name)
        sales_data.append(float(day_sales) if day_sales else 0)

    # Sales Growth: Compare Today vs Yesterday
    yesterday = today - timedelta(days=1)
    yesterday_start_myanmar = myanmar_tz.localize(datetime.combine(yesterday, time.min))
    yesterday_end_myanmar = myanmar_tz.localize(datetime.combine(yesterday, time.max))
    yesterday_start_utc = yesterday_start_myanmar.astimezone(pytz.UTC).replace(tzinfo=None)
    yesterday_end_utc = yesterday_end_myanmar.astimezone(pytz.UTC).replace(tzinfo=None)
    
    yesterday_sales_revenue = (
        db.session.query(func.sum(Sale.total_amount))
        .filter(Sale.date >= yesterday_start_utc)
        .filter(Sale.date < yesterday_end_utc)
        .scalar()
        or 0
    )
    # Convert Decimal to float
    yesterday_sales_revenue = float(yesterday_sales_revenue or 0)
    
    # Calculate sales growth (both values are now float)
    sales_growth_percent = 0.0
    if yesterday_sales_revenue > 0:
        sales_growth_percent = ((today_sales_revenue - yesterday_sales_revenue) / yesterday_sales_revenue) * 100
    elif today_sales_revenue > 0:
        sales_growth_percent = 100.0  # Infinite growth (from 0 to something)

    # Category Sales: Total quantity sold per category
    category_sales_query = (
        db.session.query(
            Category.name,
            func.sum(SaleItem.quantity).label('total_qty')
        )
        .join(Product, Category.id == Product.category_id)
        .join(SaleItem, Product.id == SaleItem.product_id)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .filter(Sale.date >= today_start_utc)
        .filter(Sale.date < today_end_utc)
        .group_by(Category.id, Category.name)
        .all()
    )
    category_sales = [
        {"name": name, "quantity": int(qty or 0)}
        for name, qty in category_sales_query
    ]
    category_labels = [c["name"] for c in category_sales]
    category_quantities = [c["quantity"] for c in category_sales]

    # Payment Methods Breakdown
    payment_methods_query = (
        db.session.query(
            Sale.payment_method,
            func.count(Sale.id).label('count')
        )
        .filter(Sale.date >= today_start_utc)
        .filter(Sale.date < today_end_utc)
        .group_by(Sale.payment_method)
        .all()
    )
    payment_methods = {method: count for method, count in payment_methods_query}
    payment_labels = list(payment_methods.keys())
    payment_counts = list(payment_methods.values())

    # Top 5 Customers by Total Spending (all time)
    top_customers_query = (
        db.session.query(
            Customer.id,
            Customer.name,
            Customer.phone,
            func.sum(Sale.total_amount).label('total_spent'),
            func.max(Sale.date).label('last_visit')
        )
        .join(Sale, Customer.id == Sale.customer_id)
        .group_by(Customer.id, Customer.name, Customer.phone)
        .order_by(func.sum(Sale.total_amount).desc())
        .limit(5)
        .all()
    )
    top_customers = [
        {
            "id": cid,
            "name": name,
            "phone": phone or "N/A",
            "total_spent": float(total_spent or 0),
            "last_visit": last_visit.strftime('%Y-%m-%d') if last_visit else "Never"
        }
        for cid, name, phone, total_spent, last_visit in top_customers_query
    ]

    # Critical Stock: Products where stock <= min_stock
    critical_stock_products = (
        Product.query.filter(Product.stock <= Product.min_stock)
        .order_by(Product.stock.asc())
        .limit(10)
        .all()
    )
    critical_stock = [
        {
            "id": p.id,
            "name": p.name,
            "stock": int(p.stock or 0),
            "min_stock": int(p.min_stock or 0),
            "status": "Critical" if p.stock == 0 else "Low"
        }
        for p in critical_stock_products
    ]

    # Returns and Damaged Goods Analytics
    from app.models import StockMovement
    
    # Total Returns (from sales)
    total_returns = (
        db.session.query(func.sum(Sale.returned_amount))
        .filter(Sale.returned_amount > 0)
        .scalar()
        or 0
    )
    # Convert Decimal to float
    total_returns = float(total_returns or 0)
    
    # Total Damaged/Lost (from stock movements)
    damaged_losses = (
        db.session.query(func.sum(StockMovement.quantity))
        .join(Product, StockMovement.product_id == Product.id)
        .filter(
            StockMovement.change_type == 'out',
            StockMovement.reason.like('%Damage%')
            | StockMovement.reason.like('%Expired%')
            | StockMovement.reason.like('%Lost%')
            | StockMovement.reason.like('%Theft%')
        )
        .scalar()
        or 0
    )
    
    # Calculate value of damaged goods (using product cost)
    damaged_value = 0.0
    damaged_movements = (
        StockMovement.query.filter(
            StockMovement.change_type == 'out',
            (
                StockMovement.reason.like('%Damage%')
                | StockMovement.reason.like('%Expired%')
                | StockMovement.reason.like('%Lost%')
                | StockMovement.reason.like('%Theft%')
            )
        )
        .all()
    )
    for movement in damaged_movements:
        if movement.product:
            damaged_value += float(movement.product.cost or 0) * movement.quantity

    # Total Inventory Value: Sum(Product.stock * Product.cost)
    total_inventory_value = (
        db.session.query(func.sum(Product.stock * Product.cost))
        .scalar()
        or 0
    )
    # Convert Decimal to float
    total_inventory_value = float(total_inventory_value or 0)

    # Calculate Net Profit (Gross Profit - Expenses)
    # Note: Currently no Expense model, so showing Gross Profit
    # Structure is ready for expenses when added
    today_expenses = 0.0  # Placeholder for future Expense model
    monthly_expenses = 0.0  # Placeholder for future Expense model
    
    net_profit_today = today_profit - today_expenses
    net_profit_monthly = monthly_profit - monthly_expenses

    # Recent Activity Feed: Last 5 AuditLog entries
    recent_activities = (
        AuditLog.query.order_by(AuditLog.timestamp.desc())
        .limit(5)
        .all()
    )
    
    # Format activities for display
    activity_list = []
    for activity in recent_activities:
        # Calculate time ago
        # activity.timestamp is naive UTC from database, so localize as UTC first, then convert to Myanmar timezone
        activity_timestamp_utc = pytz.UTC.localize(activity.timestamp) if activity.timestamp.tzinfo is None else activity.timestamp
        activity_timestamp_myanmar = activity_timestamp_utc.astimezone(myanmar_tz)
        time_diff = datetime.now(myanmar_tz) - activity_timestamp_myanmar
        if time_diff.total_seconds() < 60:
            time_ago = f"{int(time_diff.total_seconds())} secs ago"
        elif time_diff.total_seconds() < 3600:
            time_ago = f"{int(time_diff.total_seconds() / 60)} mins ago"
        elif time_diff.total_seconds() < 86400:
            time_ago = f"{int(time_diff.total_seconds() / 3600)} hrs ago"
        else:
            time_ago = f"{int(time_diff.total_seconds() / 86400)} days ago"
        
        user_name = activity.user.username if activity.user else "System"
        activity_list.append({
            "user": user_name,
            "action": activity.action,
            "details": activity.details or "",
            "time_ago": time_ago,
            "timestamp": activity.timestamp
        })

    # All values are already converted to float
    return render_template(
        "main/dashboard.html",
        today_sales_revenue=today_sales_revenue,
        monthly_sales_revenue=monthly_sales_revenue,
        today_profit=float(today_profit or 0),
        monthly_profit=float(monthly_profit or 0),
        top_products=top_products,
        dates=dates,
        sales_data=sales_data,
        recent_sales=recent_sales,
        # Legacy metrics
        today_orders=today_orders,
        low_stock_count=low_stock_count,
        total_customers=total_customers,
        # New metrics
        sales_growth_percent=sales_growth_percent,
        category_labels=category_labels,
        category_quantities=category_quantities,
        payment_labels=payment_labels,
        payment_counts=payment_counts,
        top_customers=top_customers,
        critical_stock=critical_stock,
        total_returns=total_returns,
        damaged_losses=int(damaged_losses or 0),
        damaged_value=float(damaged_value or 0),
        total_inventory_value=total_inventory_value,
        net_profit_today=float(net_profit_today or 0),
        net_profit_monthly=float(net_profit_monthly or 0),
        gross_profit_today=float(today_profit or 0),
        gross_profit_monthly=float(monthly_profit or 0),
        today_expenses=float(today_expenses or 0),
        monthly_expenses=float(monthly_expenses or 0),
        recent_activities=activity_list,
    )
