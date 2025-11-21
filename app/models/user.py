from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from ..extensions.extensions import db, login_manager
from .base import BaseModel
from sqlalchemy.orm import relationship
from .subscription import Subscription


class User(BaseModel, UserMixin):
    """Base user model"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    password_hash = db.Column(db.String(128))
    
    # Relationships
    client = db.relationship('Client', back_populates='user', uselist=False)
    audit_trail = db.relationship('AuditTrail', back_populates='user')
    
    # Role relationship
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    role = db.relationship('Role', back_populates='users')
    
    # Branch relationships
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)  # For admins under a branch
    branch = db.relationship('Branch', back_populates='admins', foreign_keys=[branch_id], lazy=True)
    managed_branch = db.relationship('Branch', back_populates='superadmin', uselist=False, foreign_keys='Branch.superadmin_id')  # For superadmins who manage a branch
    
    # Package selection
    selected_package_id = db.Column(db.Integer, db.ForeignKey('client_packages.id'), nullable=True)
    selected_package = db.relationship('ClientPackage', foreign_keys=[selected_package_id])
    
    # Subscription relationship
    subscriptions = db.relationship('Subscription', back_populates='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        # Be defensive if legacy rows have NULL password_hash
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def is_client(self):
        """Check if this user is associated with a client"""
        # Direct relationship check
        if hasattr(self, 'client') and self.client is not None:
            return True
            
        # Double-check through database query
        from ..models.client import Client
        from flask import current_app
        
        try:
            client = Client.query.filter_by(user_id=self.id).first()
            if client:
                # Cache the client on the user instance to avoid repeated queries
                self.client = client
                return True
            return False
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error in is_client check for user {self.id}: {str(e)}")
            return False
    
    def is_admin(self):
        """Check if this user is an admin by role name."""
        return self.role is not None and self.role.name in ("superadmin", "admin")
        
    def has_permission(self, permission_name):
        """Check if the user has a specific permission.
        Regular users don't have any admin permissions.
        """
        return False
    
    def get_id(self):
        """Return prefixed ID for Flask-Login"""
        return f'user_{self.id}'
    
    # ---- Delegations to linked Client for template compatibility ----
    def has_feature(self, feature_key: str) -> bool:
        """Delegate feature checks to linked client if present."""
        try:
            if hasattr(self, 'client') and self.client:
                # Client implements FeatureAccessMixin.has_feature
                return bool(self.client.has_feature(feature_key))
            return False
        except Exception:
            return False

    def is_flat_rate(self) -> bool:
        try:
            return bool(self.client.is_flat_rate()) if getattr(self, 'client', None) else False
        except Exception:
            return False

    def is_commission_based(self) -> bool:
        try:
            return bool(self.client.is_commission_based()) if getattr(self, 'client', None) else False
        except Exception:
            return False

    @property
    def package(self):
        """Expose client's package to templates expecting current_user.package."""
        try:
            return self.client.package if getattr(self, 'client', None) else None
        except Exception:
            return None

    # Proxy some commonly used client methods used in templates
    def get_pending_withdrawal_requests_count(self) -> int:
        try:
            if getattr(self, 'client', None):
                return int(self.client.get_pending_withdrawal_requests_count())
            return 0
        except Exception:
            return 0

    @property
    def balance(self):
        """Expose client's balance for templates expecting current_user.balance."""
        try:
            if getattr(self, 'client', None) and getattr(self.client, 'balance', None) is not None:
                val = self.client.balance
                try:
                    # Convert Decimal to float for safe comparisons in Jinja
                    from decimal import Decimal
                    if isinstance(val, Decimal):
                        return float(val)
                except Exception:
                    pass
                return float(val)
            return 0.0
        except Exception:
            return 0.0

    def __repr__(self):
        return f'<User {self.id}:{self.username} role={getattr(self.role, "name", None)}>'

# NOTE: user_loader is now defined in app/__init__.py to handle both User and AdminUser properly
# This prevents security issues with cross-authentication between client and admin systems
