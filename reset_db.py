#!/usr/bin/env python3
"""
Database Reset Utility Script

This script completely wipes the database and recreates empty tables.
Use this to test the 'First Run' registration logic.

⚠️  WARNING: This will delete ALL data including users, products, sales, etc.
"""

import os
import sys

from app import create_app, db

def main():
    """Reset the database by dropping and recreating all tables."""
    
    # Safety confirmation
    print("\n" + "="*60)
    print("⚠️  DATABASE RESET UTILITY")
    print("="*60)
    print("\nThis will DELETE ALL DATA from the database:")
    print("  - All users (including Admin accounts)")
    print("  - All products and inventory")
    print("  - All sales and purchase records")
    print("  - All customers and suppliers")
    print("  - All settings and configurations")
    print("  - Everything else in the database")
    print("\n" + "-"*60)
    
    confirmation = input("⚠️  This will delete ALL data. Are you sure? (y/n): ").strip().lower()
    
    if confirmation != 'y':
        print("\n❌ Reset cancelled. Database unchanged.")
        sys.exit(0)
    
    # Create app instance
    config_name = os.environ.get("FLASK_CONFIG", "development")
    app = create_app(config_name)
    
    # Perform reset within app context
    with app.app_context():
        print("\n🔄 Resetting database...")
        
        try:
            # Drop all tables
            print("   Dropping all tables...")
            db.drop_all()
            
            # Recreate empty tables
            print("   Creating empty tables...")
            db.create_all()
            
            # Commit changes
            db.session.commit()
            
            print("\n" + "="*60)
            print("✅ Database has been wiped successfully!")
            print("="*60)
            print("\n📝 Next Steps:")
            print("   1. Go to http://localhost:5000/auth/register")
            print("   2. Create the first Admin account")
            print("   3. The first user will automatically become Admin")
            print("\n✅ You can now test the 'First Run' registration logic.")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"\n❌ Error during database reset: {e}")
            print("   Please check the error message above.")
            sys.exit(1)


if __name__ == "__main__":
    main()
