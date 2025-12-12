from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    permissions = db.Column(db.Text, nullable=True)  # Comma-separated list of permissions

    users = db.relationship("User", back_populates="role")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Role {self.name}>"
    
    def has_permission(self, permission: str) -> bool:
        """Check if this role has a specific permission."""
        if self.name.lower() == 'admin':
            return True
        if not self.permissions:
            return False
        permissions_list = [p.strip() for p in self.permissions.split(',')]
        return permission in permissions_list


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    role = db.relationship("Role", back_populates="users")
    sales = db.relationship("Sale", back_populates="cashier", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        if not self.role:
            return False
        return self.role.has_permission(permission)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username}>"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)

    parent = db.relationship("Category", remote_side=[id], backref="subcategories")
    products = db.relationship("Product", back_populates="category")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category {self.name}>"


class Unit(db.Model):
    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    short_name = db.Column(db.String(10), nullable=False)

    products = db.relationship("Product", back_populates="unit")

    __table_args__ = (
        db.UniqueConstraint("name", name="uq_units_name"),
        db.UniqueConstraint("short_name", name="uq_units_short_name"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Unit {self.name} ({self.short_name})>"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    barcode = db.Column(db.String(50), unique=True, nullable=False, index=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    cost = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    min_stock = db.Column(db.Integer, nullable=False, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=True)
    image_file = db.Column(db.String(255), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)  # Support external image URLs
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    category = db.relationship("Category", back_populates="products")
    unit = db.relationship("Unit", back_populates="products")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.barcode}>"


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30))
    address = db.Column(db.String(255))

    purchases = db.relationship(
        "Purchase", back_populates="supplier", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Supplier {self.name}>"


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30))
    address = db.Column(db.String(255))
    credit_balance = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    sales = db.relationship("Sale", back_populates="customer")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Customer {self.name}>"


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    tax = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    discount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    payment_method = db.Column(db.String(30), nullable=False, default="cash")
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="completed")  # completed, returned, partially_returned
    returned_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)  # Total amount returned

    cashier = db.relationship("User", back_populates="sales")
    customer = db.relationship("Customer", back_populates="sales")
    items = db.relationship(
        "SaleItem", back_populates="sale", cascade="all, delete-orphan"
    )

    def recompute_totals(self) -> None:
        """Recalculate totals based on items."""
        subtotal = sum(item.subtotal or 0 for item in self.items)
        self.total_amount = subtotal + (self.tax or 0) - (self.discount or 0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Sale invoice={self.invoice_no}>"


class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    returned_quantity = db.Column(db.Integer, nullable=False, default=0)  # Track returned qty

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SaleItem sale={self.sale_id} product={self.product_id}>"


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    change_type = db.Column(db.String(10), nullable=False)  # 'in' or 'out'
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255))
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    product = db.relationship("Product")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StockMovement product={self.product_id} {self.change_type} {self.quantity}>"


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    supplier = db.relationship("Supplier", back_populates="purchases")
    items = db.relationship(
        "PurchaseItem", back_populates="purchase", cascade="all, delete-orphan"
    )

    def recompute_total(self) -> None:
        """Recalculate total_amount based on items."""
        self.total_amount = sum(item.subtotal or 0 for item in self.items)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Purchase supplier={self.supplier_id} total={self.total_amount}>"


class PurchaseItem(db.Model):
    __tablename__ = "purchase_items"

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchases.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    purchase = db.relationship("Purchase", back_populates="items")
    product = db.relationship("Product")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PurchaseItem purchase={self.purchase_id} product={self.product_id}>"


class StoreSetting(db.Model):
    __tablename__ = "store_settings"

    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(150), nullable=False, default="My Shop")
    address = db.Column(db.String(255))
    phone = db.Column(db.String(30))
    receipt_header = db.Column(db.Text)
    receipt_footer = db.Column(db.String(255), default="Thank You!")
    currency_symbol = db.Column(db.String(10), nullable=False, default="Ks")
    # Printer settings
    printer_paper_size = db.Column(db.String(20), nullable=False, default="58mm")
    auto_print = db.Column(db.Boolean, nullable=False, default=False)
    show_logo_on_receipt = db.Column(db.Boolean, nullable=False, default=True)
    print_padding = db.Column(db.Integer, nullable=False, default=0)
    logo_filename = db.Column(db.String(255), nullable=True)

    @classmethod
    def get_settings(cls):
        """Get or create singleton store settings."""
        try:
            settings = cls.query.first()
            if not settings:
                settings = cls()
                db.session.add(settings)
                db.session.commit()
            return settings
        except Exception:
            # Table doesn't exist, return a default object
            return cls(
                shop_name="My Shop",
                address="",
                phone="",
                receipt_header="",
                receipt_footer="Thank You!",
                currency_symbol="Ks",
                printer_paper_size="58mm",
                auto_print=False,
                show_logo_on_receipt=True,
                print_padding=0,
            )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StoreSetting {self.shop_name}>"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 max length is 45
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="audit_logs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} by {self.user_id} at {self.timestamp}>"
