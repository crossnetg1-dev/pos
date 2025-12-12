#!/usr/bin/env python3
"""
Database Integrity Fix Script

This script inspects the SQLite database and compares it with app/models.py.
It automatically adds missing columns and creates missing tables to prevent
'Internal Server Error' caused by schema mismatches.
"""

import os
import sqlite3
import sys
from pathlib import Path

from app import create_app, db
from app.models import (
    AuditLog,
    Category,
    Customer,
    Product,
    Purchase,
    PurchaseItem,
    Role,
    Sale,
    SaleItem,
    StockMovement,
    StoreSetting,
    Supplier,
    Unit,
    User,
)


def get_table_columns(cursor, table_name):
    """Get all column names for a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1]: row[2] for row in cursor.fetchall()}  # {column_name: type}


def add_column_if_missing(cursor, table_name, column_name, column_type, nullable=True, default=None):
    """Add a column to a table if it doesn't exist."""
    columns = get_table_columns(cursor, table_name)
    if column_name not in columns:
        nullable_str = "" if nullable else " NOT NULL"
        default_str = f" DEFAULT {default}" if default is not None else ""
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}{nullable_str}{default_str}"
        try:
            cursor.execute(sql)
            print(f"   ✅ Added column '{column_name}' to '{table_name}'")
            return True
        except sqlite3.OperationalError as e:
            print(f"   ❌ Failed to add column '{column_name}' to '{table_name}': {e}")
            return False
    return False


def main():
    """Fix database schema by adding missing columns and creating missing tables."""
    print("\n" + "="*60)
    print("🔧 DATABASE INTEGRITY FIX SCRIPT")
    print("="*60)
    
    # Create app instance
    config_name = os.environ.get("FLASK_CONFIG", "development")
    app = create_app(config_name)
    
    with app.app_context():
        # Get database path
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
            if not os.path.isabs(db_path):
                db_path = str(Path(__file__).parent / db_path)
        else:
            print("❌ This script only works with SQLite databases.")
            sys.exit(1)
        
        if not os.path.exists(db_path):
            print(f"⚠️  Database file not found: {db_path}")
            print("   Creating database with all tables...")
            db.create_all()
            print("✅ Database created successfully!")
            sys.exit(0)
        
        print(f"\n📁 Database: {db_path}")
        print("\n🔍 Checking database schema...\n")
        
        # Connect to SQLite directly
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        changes_made = False
        
        # Ensure all tables exist
        print("📋 Creating missing tables...")
        db.create_all()
        print("   ✅ All tables verified\n")
        
        # Define expected columns for each table
        expected_columns = {
            'users': [
                ('role_id', 'INTEGER', True, None),
                ('is_active', 'BOOLEAN', False, '1'),
                ('created_at', 'DATETIME', False, None),
            ],
            'products': [
                ('image_url', 'VARCHAR(500)', True, None),
                ('image_file', 'VARCHAR(255)', True, None),
                ('unit_id', 'INTEGER', True, None),
                ('created_at', 'DATETIME', False, None),
            ],
            'categories': [
                ('parent_id', 'INTEGER', True, None),
            ],
            'sales': [
                ('discount', 'NUMERIC(10,2)', False, '0'),
                ('status', 'VARCHAR(20)', False, "'completed'"),
                ('returned_amount', 'NUMERIC(10,2)', False, '0'),
            ],
            'sale_items': [
                ('returned_quantity', 'INTEGER', False, '0'),
            ],
            'store_settings': [
                ('printer_paper_size', 'VARCHAR(20)', False, "'58mm'"),
                ('auto_print', 'BOOLEAN', False, '0'),
                ('show_logo_on_receipt', 'BOOLEAN', False, '1'),
                ('print_padding', 'INTEGER', False, '0'),
                ('logo_filename', 'VARCHAR(255)', True, None),
            ],
            'audit_logs': [
                ('ip_address', 'VARCHAR(45)', True, None),
            ],
        }
        
        # Check and add missing columns
        print("🔧 Checking and adding missing columns...")
        for table_name, columns in expected_columns.items():
            # Check if table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            if not cursor.fetchone():
                print(f"   ⚠️  Table '{table_name}' does not exist (will be created by db.create_all())")
                continue
            
            for column_name, column_type, nullable, default in columns:
                if add_column_if_missing(cursor, table_name, column_name, column_type, nullable, default):
                    changes_made = True
        
        # Commit changes
        if changes_made:
            conn.commit()
            print("\n✅ Database schema updated successfully!")
        else:
            print("\n✅ Database schema is up to date. No changes needed.")
        
        conn.close()
        
        print("\n" + "="*60)
        print("✅ Database integrity check complete!")
        print("="*60 + "\n")


if __name__ == "__main__":
    main()
