import os
import shutil
from datetime import datetime
from pathlib import Path
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import db
from app.models import (
    Category,
    Customer,
    Product,
    Purchase,
    PurchaseItem,
    Sale,
    SaleItem,
    StockMovement,
    StoreSetting,
    Supplier,
)
from app.utils import log_activity, permission_required

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
@permission_required('settings_access')
def index():
    try:
        settings = StoreSetting.get_settings()
    except Exception:
        # Table doesn't exist yet, create it
        db.create_all()
        settings = StoreSetting.get_settings()

    if request.method == "POST":
        settings.shop_name = request.form.get("shop_name", settings.shop_name).strip()
        settings.address = request.form.get("address", "").strip()
        settings.phone = request.form.get("phone", "").strip()
        settings.receipt_header = request.form.get("receipt_header", "").strip()
        settings.receipt_footer = request.form.get("receipt_footer", settings.receipt_footer).strip()
        settings.currency_symbol = request.form.get("currency_symbol", settings.currency_symbol).strip()
        
        # Printer settings
        settings.printer_paper_size = request.form.get("printer_paper_size", "58mm")
        settings.auto_print = request.form.get("auto_print") == "on"
        settings.show_logo_on_receipt = request.form.get("show_logo_on_receipt") == "on"
        try:
            settings.print_padding = int(request.form.get("print_padding", 0) or 0)
        except ValueError:
            settings.print_padding = 0

        # Handle logo upload
        logo_upload_dir = Path(current_app.static_folder) / "uploads" / "logo"
        logo_upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if remove_logo checkbox is checked
        if request.form.get("remove_logo") == "on":
            # Delete existing logo file
            if settings.logo_filename:
                old_logo_path = logo_upload_dir / settings.logo_filename
                if old_logo_path.exists():
                    try:
                        old_logo_path.unlink()
                    except Exception as e:
                        flash(f"Warning: Could not delete old logo file: {str(e)}", "warning")
            settings.logo_filename = None
        
        # Handle new logo upload
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename:
                # Validate file type
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
                filename = secure_filename(logo_file.filename)
                file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                
                if file_ext in allowed_extensions:
                    # Delete old logo if exists
                    if settings.logo_filename:
                        old_logo_path = logo_upload_dir / settings.logo_filename
                        if old_logo_path.exists():
                            try:
                                old_logo_path.unlink()
                            except Exception:
                                pass
                    
                    # Generate unique filename with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    new_filename = f"logo_{timestamp}.{file_ext}"
                    logo_path = logo_upload_dir / new_filename
                    
                    try:
                        logo_file.save(str(logo_path))
                        settings.logo_filename = new_filename
                        flash("Logo uploaded successfully.", "success")
                    except Exception as e:
                        flash(f"Error saving logo: {str(e)}", "danger")
                else:
                    flash("Invalid file type. Please upload an image file (PNG, JPG, GIF, etc.).", "danger")

        db.session.commit()
        log_activity('SETTINGS_UPDATE', 'Store settings updated')
        flash("Settings saved successfully.", "success")
        return redirect(url_for("settings.index"))

    return render_template("settings/index.html", settings=settings)


@settings_bp.route("/reset_data", methods=["POST"])
@login_required
@permission_required('settings_access')
def reset_data():
    """Secure data reset endpoint. Requires admin password confirmation."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400
    
    password = data.get("password", "")
    reset_type = data.get("reset_type", "")
    
    if not password or not reset_type:
        return jsonify({"error": "Password and reset type are required"}), 400
    
    if reset_type not in ["transactions_only", "full_reset"]:
        return jsonify({"error": "Invalid reset type"}), 400
    
    # CRITICAL: Verify password
    if not current_user.check_password(password):
        return jsonify({"error": "Incorrect password"}), 401
    
    try:
        if reset_type == "transactions_only":
            # Delete transaction records
            db.session.query(SaleItem).delete()
            db.session.query(Sale).delete()
            db.session.query(PurchaseItem).delete()
            db.session.query(Purchase).delete()
            db.session.query(StockMovement).delete()
            
            # Reset stock and credit balances
            db.session.query(Product).update({Product.stock: 0})
            db.session.query(Customer).update({Customer.credit_balance: 0})
            
            db.session.commit()
            log_activity('DATA_RESET', f'Data reset: Transactions only (cleared sales, purchases, stock movements)')
            return jsonify({"message": "Sales and transaction history cleared successfully"}), 200
        
        elif reset_type == "full_reset":
            # Delete transaction records first (to avoid foreign key issues)
            db.session.query(SaleItem).delete()
            db.session.query(Sale).delete()
            db.session.query(PurchaseItem).delete()
            db.session.query(Purchase).delete()
            db.session.query(StockMovement).delete()
            
            # Delete master data (but NOT users)
            db.session.query(Product).delete()
            db.session.query(Category).delete()
            db.session.query(Supplier).delete()
            db.session.query(Customer).delete()
            
            db.session.commit()
            log_activity('DATA_RESET', f'Data reset: Full reset (deleted all products, categories, suppliers, customers, and transactions)')
            return jsonify({"message": "All data reset successfully. Users and settings preserved."}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Reset failed: {str(e)}"}), 500


def get_database_path():
    """Extract the database file path from SQLALCHEMY_DATABASE_URI."""
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    # Remove sqlite:/// prefix
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
        # Handle absolute paths
        if os.path.isabs(db_path):
            return db_path
        # Handle relative paths
        return os.path.join(current_app.root_path, '..', db_path)
    return None


@settings_bp.route("/backup/download", methods=["GET"])
@login_required
@permission_required('settings_access')
def download_backup():
    """Download a backup copy of the database."""
    try:
        db_path = get_database_path()
        if not db_path or not os.path.exists(db_path):
            flash("Database file not found", "danger")
            return redirect(url_for("settings.index"))
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        filename = f"pos_backup_{timestamp}.db"
        
        return send_file(
            db_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/x-sqlite3'
        )
    except Exception as e:
        flash(f"Backup failed: {str(e)}", "danger")
        return redirect(url_for("settings.index"))


@settings_bp.route("/backup/restore", methods=["POST"])
@login_required
@permission_required('settings_access')
def restore_backup():
    """Restore database from uploaded backup file. Requires password confirmation."""
    # Get password from form data
    password = request.form.get("password", "")
    
    if not password:
        return jsonify({"error": "Password is required"}), 400
    
    # CRITICAL: Verify password
    if not current_user.check_password(password):
        return jsonify({"error": "Incorrect password"}), 401
    
    # Check if file was uploaded (via form data)
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Validate file extension
    if not (file.filename.endswith('.db') or file.filename.endswith('.sqlite') or file.filename.endswith('.sqlite3')):
        return jsonify({"error": "Invalid file type. Please upload a .db, .sqlite, or .sqlite3 file"}), 400
    
    backup_path = None
    try:
        db_path = get_database_path()
        if not db_path:
            return jsonify({"error": "Database path not found"}), 500
        
        # Safety Step: Create backup of current database
        backup_path = f"{db_path}.bak"
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
        
        # Close any existing database connections first
        db.session.close()
        
        # Save the uploaded file to the database location
        file.save(db_path)
        
        # Verify the new database file is valid
        if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
            # Restore from backup if new file is invalid
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, db_path)
            return jsonify({"error": "Restored file is invalid or empty"}), 500
        
        return jsonify({
            "message": "Database restored successfully. The page will reload.",
            "backup_created": os.path.exists(backup_path) if backup_path else False
        }), 200
    
    except Exception as e:
        # Try to restore from backup if restore failed
        if backup_path and os.path.exists(backup_path):
            try:
                db_path = get_database_path()
                if db_path:
                    shutil.copy2(backup_path, db_path)
            except:
                pass
        return jsonify({"error": f"Restore failed: {str(e)}"}), 500
