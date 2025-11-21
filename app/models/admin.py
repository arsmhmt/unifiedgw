from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from ..extensions import db
from .base import BaseModel


class AdminUser(UserMixin, BaseModel):
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    _active = db.Column('is_active', db.Boolean, default=True)
    is_superuser = db.Column(db.Boolean, default=False)

    def __init__(self, username, email, password, first_name=None, last_name=None, is_active=True, is_superuser=False):
        self.username = username
        self.email = email
        self.set_password(password)  # Hash the password
        self.first_name = first_name
        self.last_name = last_name
        self._active = is_active
        self.is_superuser = is_superuser
        super().__init__()

    def __repr__(self):
        return f'<AdminUser {self.email}>'

    def set_password(self, password):
        """Create hashed password."""
        self.password_hash = generate_password_hash(
            password,
            method='pbkdf2:sha256',
            salt_length=8
        )

    def check_password(self, password):
        """Check hashed password."""
        from flask import current_app
        try:
            current_app.logger.debug("\n=== PASSWORD CHECK START ===")
            current_app.logger.debug(f"[PASSWORD CHECK] Checking password for user: {self.username}")
            current_app.logger.debug(f"[PASSWORD CHECK] Stored hash: {self.password_hash}")
            current_app.logger.debug(f"[PASSWORD CHECK] Provided password: {'*' * len(password) if password else 'None'}")
            current_app.logger.debug(f"[PASSWORD CHECK] Provided password length: {len(password) if password else 0}")
            
            result = check_password_hash(self.password_hash, password)
            
            current_app.logger.debug(f"[PASSWORD CHECK] Result: {result}")
            current_app.logger.debug(f"[PASSWORD CHECK] Hash method: {self.password_hash.split('$')[0] if self.password_hash and '$' in self.password_hash else 'Unknown'}")
            current_app.logger.debug("=== PASSWORD CHECK END ===\n")
            
            return result
        except Exception as e:
            current_app.logger.error(f"[PASSWORD CHECK] Error checking password: {str(e)}", exc_info=True)
            return False
    
    def get_full_name(self):
        """Return the full name of the admin user."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    @property
    def is_admin(self):
        # Always return True for AdminUser instances
        return True
        
    @property
    def is_active(self):
        # Return True if the user is active
        return self._active

    def get_id(self):
        return f"admin_{self.id}"
        
    def has_permission(self, permission_name):
        """
        Check if the admin user has a specific permission.
        Superusers have all permissions by default.
        
        Args:
            permission_name (str): The name of the permission to check
            
        Returns:
            bool: True if the user has the permission, False otherwise
        """
        if self.is_superuser:
            return True
            
        # For now, return True for all permissions if not a superuser
        # In a real application, you would check against a permission system
        return True
