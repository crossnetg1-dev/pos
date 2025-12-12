"""Utility functions for the POS application."""
from datetime import datetime
from functools import wraps

from flask import abort, request
from flask_login import current_user

from app import db
from app.models import AuditLog, StockMovement

# Standardized list of permissions
ALL_PERMISSIONS = [
    'dashboard_view',
    'pos_access',
    'inventory_view',
    'inventory_edit',
    'sales_view',
    'sales_edit',
    'sales_delete',  # Permission for deleting sales
    'profit_view',
    'settings_access',
    'users_manage',
    'categories_manage',
    'units_manage',
    'customers_manage',
    'purchases_manage',
    'purchases_edit',
]


def log_stock_movement(product_id: int, quantity: int, change_type: str, reason: str, user_id: int = None) -> None:
    """
    Create a StockMovement record to track stock changes.
    
    Args:
        product_id: ID of the product
        quantity: Quantity changed (positive number)
        change_type: 'in' (addition) or 'out' (subtraction)
        reason: Reason for the stock change (e.g., 'Sale #INV-123', 'Purchase #5')
        user_id: Optional user ID who made the change
    """
    if change_type not in ('in', 'out'):
        raise ValueError("change_type must be 'in' or 'out'")
    
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    
    movement = StockMovement(
        product_id=product_id,
        change_type=change_type,
        quantity=quantity,
        reason=reason,
        date=datetime.utcnow(),
    )
    db.session.add(movement)


def log_activity(action: str, details: str = None):
    """
    Log an activity to the audit log.
    
    Args:
        action: The action performed (e.g., 'LOGIN_SUCCESS', 'PRODUCT_DELETE')
        details: Additional details about the action (e.g., 'Deleted Invoice #INV-001')
    
    Usage:
        log_activity('PRODUCT_EDIT', 'Changed Coke Price from 500 to 600')
    """
    try:
        user_id = current_user.id if current_user.is_authenticated else None
        ip_address = request.remote_addr if request else None
        
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address,
            timestamp=datetime.utcnow()
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        # Don't break the application if logging fails
        db.session.rollback()
        print(f"Failed to log activity: {e}")


def permission_required(permission: str):
    """
    Decorator to check if the current user has a specific permission.
    
    Args:
        permission: The permission name to check (e.g., 'inventory_view')
    
    Usage:
        @permission_required('inventory_edit')
        def edit_product():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            
            # Use the User model's has_permission method
            if not current_user.has_permission(permission):
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
