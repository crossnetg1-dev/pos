"""
Seeding script to create Admin role with ALL permissions.
Run this script to ensure you don't get locked out.
"""
from app import create_app, db
from app.models import Role, User
from app.utils import ALL_PERMISSIONS
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Create roles table if it doesn't exist
    db.create_all()
    
    # Create Admin role with ALL permissions
    admin_role = Role.query.filter_by(name='Admin').first()
    if not admin_role:
        admin_role = Role(
            name='Admin',
            permissions=','.join(ALL_PERMISSIONS)  # All permissions
        )
        db.session.add(admin_role)
        db.session.commit()
        print("✅ Admin role created with ALL permissions")
    else:
        # Update existing Admin role to have all permissions
        admin_role.permissions = ','.join(ALL_PERMISSIONS)
        db.session.commit()
        print("✅ Admin role updated with ALL permissions")
    
    # Create Cashier role with basic permissions
    cashier_role = Role.query.filter_by(name='Cashier').first()
    if not cashier_role:
        cashier_permissions = ['dashboard_view', 'pos_access', 'sales_view', 'customers_manage']
        cashier_role = Role(
            name='Cashier',
            permissions=','.join(cashier_permissions)
        )
        db.session.add(cashier_role)
        db.session.commit()
        print("✅ Cashier role created")
    else:
        # Update existing Cashier role to include dashboard_view
        current_perms = cashier_role.permissions.split(',') if cashier_role.permissions else []
        if 'dashboard_view' not in current_perms:
            current_perms.append('dashboard_view')
            cashier_role.permissions = ','.join(current_perms)
            db.session.commit()
            print("✅ Cashier role updated with dashboard_view")
    
    # Update existing users to use Admin role if they were 'owner'
    admin_role = Role.query.filter_by(name='Admin').first()
    if admin_role:
        # Update users with old 'owner' role to Admin
        users_to_update = User.query.filter(User.role_id.is_(None)).all()
        for user in users_to_update:
            # Check if user was created with old role system
            # Assign Admin role by default for existing users
            user.role_id = admin_role.id
        db.session.commit()
        print(f"✅ Updated {len(users_to_update)} existing users to Admin role")
    
    print("🎉 Role seeding complete!")
    print(f"   - Admin role: {len(ALL_PERMISSIONS)} permissions")
    print(f"   - Cashier role: Basic POS access")
