# Production Deployment Checklist

## Pre-Deployment Steps

### 1. Database Health Check
```bash
python3 manage_db.py
```
This script will:
- Check all tables for missing columns
- Automatically add missing columns (image_url, discount, logo_filename, role_id, etc.)
- Verify database schema matches SQLAlchemy models

### 2. Environment Variables
Set these environment variables in production:

```bash
export FLASK_ENV=production
export FLASK_DEBUG=False
export SECRET_KEY="your-strong-secret-key-here"
export SECURITY_PASSWORD_SALT="your-salt-here"
export DATABASE_URL="sqlite:///path/to/your/production.db"
```

**⚠️ CRITICAL:** Never commit SECRET_KEY to version control!

### 3. Logging
Logs are automatically saved to `logs/app.log`:
- Rotating file handler (10MB max, 10 backups)
- Errors are logged automatically
- Check logs for debugging production issues

## Production Features Implemented

### ✅ Database Resilience
- **Script:** `manage_db.py`
- Automatically detects and fixes missing columns
- Safe to run multiple times
- Handles all recent feature additions

### ✅ Error Handling
- **404 Page:** Clean, modern error page with "Go Home" button
- **500 Page:** Server error page with logging
- All errors logged to `logs/app.log`
- Database rollback on 500 errors

### ✅ Input Validation
- **Inventory:** Price, cost, stock cannot be negative
- **POS Checkout:** 
  - Cart cannot be empty
  - Discount cannot exceed subtotal
  - Tax and discount validated
- **Customers:** 
  - Duplicate phone numbers prevented
  - Credit balance validated
- **All numeric inputs:** Type checking and validation

### ✅ Security
- **SECRET_KEY:** Loaded from environment or secure fallback
- **DEBUG:** Disabled by default in production
- **Session Security:** HTTPOnly cookies enabled
- **Production Config:** Secure cookie settings

## Deployment Commands

### Initial Setup
```bash
# 1. Check database health
python3 manage_db.py

# 2. Run setup (if needed)
python3 setup.py

# 3. Set environment variables
export FLASK_ENV=production
export SECRET_KEY="your-secret-key"

# 4. Run the application
python3 run.py
# Or use gunicorn for production:
# gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

### Monitoring
- Check `logs/app.log` for errors
- Monitor database size and performance
- Review audit logs in the admin panel

## Post-Deployment

1. **Test Error Pages:** Visit a non-existent URL to test 404
2. **Test Logging:** Check that `logs/app.log` is being created
3. **Verify Database:** Run `manage_db.py` to ensure schema is correct
4. **Check Permissions:** Verify file permissions for database and logs

## Troubleshooting

### Database Errors
```bash
# Run database health check
python3 manage_db.py

# If issues persist, backup and recreate:
cp app/pos.db app/pos.db.backup
python3 setup.py
```

### Logging Issues
- Ensure `logs/` directory is writable
- Check disk space
- Verify file permissions

### Missing Columns
- Run `manage_db.py` to auto-fix
- Check error logs for specific column names
- Manually add columns if needed using SQLite

## Security Notes

- ✅ SECRET_KEY is never hardcoded
- ✅ DEBUG is disabled in production
- ✅ All user inputs are validated
- ✅ SQL injection protection via SQLAlchemy
- ✅ XSS protection via Flask's template engine
- ✅ CSRF protection recommended (add Flask-WTF if needed)

## Performance Tips

- Use a production WSGI server (gunicorn, uWSGI)
- Consider PostgreSQL for production (update DATABASE_URL)
- Enable database connection pooling
- Use a reverse proxy (nginx) for static files
- Enable gzip compression
