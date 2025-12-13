#!/usr/bin/env python3
"""
Clean Setup Script - System Preparation Only
No user seeding - client will create their own Admin account

This script:
1. Deletes existing database (if any) for fresh start
2. Creates all required directories
3. Initializes database schema
4. Seeds Roles only (Admin and Cashier) - NO USERS
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def print_step(step_num, message):
    """Print a formatted step message."""
    print(f"\n{'='*60}")
    print(f"Step {step_num}: {message}")
    print('='*60)

def delete_existing_database():
    """Delete existing database if it exists."""
    print_step(1, "Removing Existing Database")
    
    # Check common database locations
    db_paths = [
        project_root / 'instance' / 'site.db',
        project_root / 'instance' / 'pos.db',
        project_root / 'app' / 'pos.db',
        project_root / 'pos.db',
    ]
    
    deleted = False
    for db_path in db_paths:
        if db_path.exists():
            try:
                db_path.unlink()
                print(f"✅ Deleted existing database: {db_path}")
                deleted = True
            except Exception as e:
                print(f"⚠️  Warning: Could not delete {db_path}: {e}")
    
    if not deleted:
        print("✅ No existing database found (fresh start)")
    
    # Also delete any .db-journal files
    for db_path in db_paths:
        journal_path = Path(str(db_path) + '-journal')
        if journal_path.exists():
            try:
                journal_path.unlink()
                print(f"✅ Deleted journal file: {journal_path}")
            except Exception as e:
                print(f"⚠️  Warning: Could not delete {journal_path}: {e}")

def create_required_directories():
    """Create all required directories."""
    print_step(2, "Creating Required Directories")
    
    directories = [
        project_root / 'instance',
        project_root / 'app' / 'static' / 'uploads',
        project_root / 'app' / 'static' / 'uploads' / 'product_images',
        project_root / 'app' / 'static' / 'uploads' / 'logos',
    ]
    
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created/Verified: {directory}")
        except Exception as e:
            print(f"❌ Error creating {directory}: {e}")
            sys.exit(1)

def initialize_database():
    """Initialize database schema."""
    print_step(3, "Database Initialization")
    
    try:
        from app import create_app, db
        
        app = create_app()
        
        with app.app_context():
            # Create all tables
            db.create_all()
            print("✅ Database schema created successfully")
            
            return app, db
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def seed_roles_only(app, db):
    """Seed Roles only - NO USERS."""
    print_step(4, "Seeding Roles (No Users)")
    
    try:
        from app.models import Role
        from app.utils import ALL_PERMISSIONS
        
        with app.app_context():
            # 1. Create Admin Role
            print("\n📋 Creating Admin Role...")
            admin_role = Role.query.filter_by(name='Admin').first()
            if not admin_role:
                admin_role = Role(
                    name='Admin',
                    permissions=','.join(ALL_PERMISSIONS)
                )
                db.session.add(admin_role)
                db.session.commit()
                print("✅ Admin role created with ALL permissions")
            else:
                admin_role.permissions = ','.join(ALL_PERMISSIONS)
                db.session.commit()
                print("✅ Admin role updated with ALL permissions")
            
            # 2. Create Cashier Role
            print("\n📋 Creating Cashier Role...")
            cashier_role = Role.query.filter_by(name='Cashier').first()
            if not cashier_role:
                basic_permissions = [
                    'pos_access',
                    'sales_view',
                    'dashboard_view'
                ]
                cashier_role = Role(
                    name='Cashier',
                    permissions=','.join(basic_permissions)
                )
                db.session.add(cashier_role)
                db.session.commit()
                print("✅ Cashier role created with basic permissions")
            else:
                print("✅ Cashier role already exists")
            
            print("\n✅ Roles seeded successfully!")
            print("⚠️  No users created - client will create Admin account on first run")
            
    except Exception as e:
        print(f"❌ Error seeding roles: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def print_success_message():
    """Print final success message."""
    print("\n" + "="*60)
    print(" " * 10 + "✅ SYSTEM INITIALIZED!")
    print("="*60)
    print("\n" + " " * 5 + "🎉 Setup Complete! System is ready for first run.")
    print("\n" + " " * 5 + "📝 Next Steps:")
    print(" " * 10 + "   1. Run: python run.py (or python3 run.py)")
    print(" " * 10 + "   2. Open: http://localhost:5000")
    print(" " * 10 + "   3. Click 'Create Admin Account' on login page")
    print(" " * 10 + "   4. First user will automatically become Admin")
    print("\n" + "="*60 + "\n")

def main():
    """Main setup function."""
    print("\n" + "="*60)
    print(" " * 10 + "Cid-POS Clean Setup")
    print(" " * 5 + "System Preparation (No Users)")
    print("="*60)
    
    try:
        # Step 1: Delete existing database
        delete_existing_database()
        
        # Step 2: Create directories
        create_required_directories()
        
        # Step 3: Initialize database
        app, db = initialize_database()
        
        # Step 4: Seed roles only (no users)
        seed_roles_only(app, db)
        
        # Step 5: Success message
        print_success_message()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
