from app import create_app, db
from app.models import User, Product, Category, Sale, SaleItem, Role, AuditLog
from app.utils import ALL_PERMISSIONS
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # ၁။ ဇယားများ အသစ်ပြန်ဆောက်ခြင်း
    db.create_all()
    print("✅ Database tables created (including audit_logs)!")

    # ၂။ Create Admin Role with ALL permissions
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

    # ၃။ Admin User အသစ်ထည့်ခြင်း (Email ပါဝင်သည်)
    admin_user = User.query.filter_by(email='admin@gmail.com').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            email='admin@gmail.com',
            password_hash=generate_password_hash('123456'),
            role_id=admin_role.id
        )
        db.session.add(admin_user)
        print("✅ Admin user created (Email: admin@gmail.com, Pass: 123456)")
    else:
        # Update existing admin to use Admin role
        admin_user.role_id = admin_role.id
        db.session.commit()
        print("✅ Admin user updated with Admin role")

    # ၃။ Categories ထည့်ခြင်း
    if not Category.query.first():
        cat_food = Category(name='Food')
        cat_drink = Category(name='Drinks')
        cat_snack = Category(name='Snacks')
        db.session.add_all([cat_food, cat_drink, cat_snack])
        db.session.commit() # Save categories first to get IDs

        # ၄။ Products ထည့်ခြင်း (ပုံထဲကအတိုင်း)
        products = [
            Product(name='Mama Noodles', barcode='8850987123', price=500, cost=400, stock=100, min_stock=10, category_id=cat_food.id),
            Product(name='Coca Cola (330ml)', barcode='8851952333', price=800, cost=600, stock=48, min_stock=5, category_id=cat_drink.id),
            Product(name='Coffee Mix', barcode='8859998887', price=200, cost=150, stock=195, min_stock=20, category_id=cat_drink.id),
            Product(name='Potato Chips', barcode='8851112223', price=1200, cost=900, stock=20, min_stock=5, category_id=cat_snack.id)
        ]
        db.session.add_all(products)
        print("✅ Dummy products added!")

    db.session.commit()
    print("🎉 Setup Complete! You can run the app now.")
    