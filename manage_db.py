#!/usr/bin/env python3
"""
Database Health Check and Migration Script
Checks for missing columns and automatically adds them to match SQLAlchemy models.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import app
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app, db
from app.models import (
    Product, Sale, SaleItem, Customer, User, StoreSetting,
    Category, Supplier, Purchase, PurchaseItem, StockMovement,
    Role, Unit, AuditLog
)


def get_db_path():
    """Get the database file path from Flask config."""
    app = create_app()
    with app.app_context():
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            if Path(db_path).is_absolute():
                return db_path
            return str(Path(__file__).parent / db_path)
    return None


def get_table_columns(conn, table_name):
    """Get list of columns for a table."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def check_and_fix_table(conn, model_class, table_name):
    """Check if table exists and has all required columns, add missing ones."""
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    if not cursor.fetchone():
        print(f"  ⚠️  Table '{table_name}' does not exist. Run 'db.create_all()' first.")
        return False
    
    # Get existing columns
    existing_columns = get_table_columns(conn, table_name)
    
    # Get expected columns from model
    expected_columns = {}
    for column_name, column in model_class.__table__.columns.items():
        expected_columns[column_name] = column
    
    # Check for missing columns
    missing_columns = []
    for col_name, col_def in expected_columns.items():
        if col_name not in existing_columns:
            missing_columns.append((col_name, col_def))
    
    if not missing_columns:
        return True
    
    # Add missing columns
    print(f"  🔧 Adding {len(missing_columns)} missing column(s) to '{table_name}':")
    for col_name, col_def in missing_columns:
        sql_type = get_sqlite_type(col_def)
        nullable = "NULL" if col_def.nullable else "NOT NULL"
        default = ""
        
        if col_def.default is not None:
            if hasattr(col_def.default, 'arg'):
                default_val = col_def.default.arg
                if isinstance(default_val, (int, float)):
                    default = f"DEFAULT {default_val}"
                elif isinstance(default_val, str):
                    default = f"DEFAULT '{default_val}'"
                elif default_val == "CURRENT_TIMESTAMP" or str(default_val) == "datetime.utcnow":
                    default = "DEFAULT CURRENT_TIMESTAMP"
            elif col_def.default == 0:
                default = "DEFAULT 0"
        
        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type} {nullable} {default}"
        
        try:
            conn.execute(alter_sql)
            print(f"    ✅ Added column: {col_name} ({sql_type})")
        except sqlite3.OperationalError as e:
            print(f"    ❌ Failed to add {col_name}: {e}")
            return False
    
    conn.commit()
    return True


def get_sqlite_type(column):
    """Convert SQLAlchemy column type to SQLite type."""
    col_type = str(column.type)
    
    if 'Integer' in col_type:
        return 'INTEGER'
    elif 'String' in col_type or 'Text' in col_type:
        # Extract length if present
        if 'String' in col_type:
            length_match = __import__('re').search(r'\((\d+)\)', col_type)
            if length_match:
                length = length_match.group(1)
                return f'VARCHAR({length})'
        return 'TEXT'
    elif 'Numeric' in col_type or 'Float' in col_type or 'Decimal' in col_type:
        return 'REAL'
    elif 'Boolean' in col_type:
        return 'INTEGER'
    elif 'DateTime' in col_type:
        return 'DATETIME'
    else:
        return 'TEXT'


def main():
    """Main function to check and fix database schema."""
    print("=" * 60)
    print("Database Health Check & Migration Tool")
    print("=" * 60)
    print()
    
    db_path = get_db_path()
    if not db_path:
        print("❌ Could not determine database path.")
        sys.exit(1)
    
    if not Path(db_path).exists():
        print(f"❌ Database file not found: {db_path}")
        print("   Run 'python setup.py' to create the database first.")
        sys.exit(1)
    
    print(f"📁 Database: {db_path}")
    print()
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Tables to check (in order of dependencies)
    tables_to_check = [
        ('roles', Role),
        ('users', User),
        ('categories', Category),
        ('units', Unit),
        ('products', Product),
        ('customers', Customer),
        ('suppliers', Supplier),
        ('store_settings', StoreSetting),
        ('sales', Sale),
        ('sale_items', SaleItem),
        ('purchases', Purchase),
        ('purchase_items', PurchaseItem),
        ('stock_movements', StockMovement),
        ('audit_logs', AuditLog),
    ]
    
    all_ok = True
    fixed_count = 0
    
    for table_name, model_class in tables_to_check:
        print(f"🔍 Checking table: {table_name}")
        if check_and_fix_table(conn, model_class, table_name):
            print(f"  ✅ Table '{table_name}' is healthy")
        else:
            fixed_count += 1
            all_ok = False
        print()
    
    conn.close()
    
    print("=" * 60)
    if all_ok:
        print("✅ All tables are healthy! No missing columns found.")
    else:
        print(f"⚠️  Fixed {fixed_count} table(s). Please review the changes.")
    print("=" * 60)
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
