import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    # SECRET_KEY: Hardcoded for production stability (prevents Gunicorn session dropouts)
    SECRET_KEY = os.environ.get("SECRET_KEY", "cid-pos-secure-key-2024")
    
    # Timezone Configuration
    TIMEZONE = 'Asia/Yangon'
    
    # Upload Configuration
    UPLOAD_FOLDER = BASE_DIR / 'app' / 'static' / 'uploads'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'app' / 'pos.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    # SECURITY_PASSWORD_SALT: Use environment variable or hardcoded default
    # CRITICAL: Must be constant, not random, to maintain password verification consistency
    SECURITY_PASSWORD_SALT = os.environ.get(
        "SECURITY_PASSWORD_SALT", "cid-pos-password-salt-2024-default"
    )


class DevelopmentConfig(Config):
    DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() == "true"


class ProductionConfig(Config):
    DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
