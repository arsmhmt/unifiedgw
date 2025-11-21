"""
API Key Management Models for Client API Access
Enhanced for Commission-Based vs Flat-Rate Client Models
"""
from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from app.extensions import db
from .base import BaseModel
import secrets
import string
from enum import Enum

class ApiKeyScope(Enum):
    """API Key scopes based on client type"""
    # Commission-Based Client permissions (limited)
    COMMISSION_PAYMENT_CREATE = 'commission:payment:create'
    COMMISSION_PAYMENT_READ = 'commission:payment:read'
    COMMISSION_BALANCE_READ = 'commission:balance:read'
    COMMISSION_STATUS_CHECK = 'commission:status:check'
    
    # Flat-Rate Client permissions (full suite)
    FLAT_RATE_PAYMENT_CREATE = 'flat_rate:payment:create'
    FLAT_RATE_PAYMENT_READ = 'flat_rate:payment:read'
    FLAT_RATE_PAYMENT_UPDATE = 'flat_rate:payment:update'
    FLAT_RATE_WITHDRAWAL_CREATE = 'flat_rate:withdrawal:create'
    FLAT_RATE_WITHDRAWAL_READ = 'flat_rate:withdrawal:read'
    FLAT_RATE_WITHDRAWAL_APPROVE = 'flat_rate:withdrawal:approve'
    FLAT_RATE_BALANCE_READ = 'flat_rate:balance:read'
    FLAT_RATE_BALANCE_UPDATE = 'flat_rate:balance:update'
    FLAT_RATE_WALLET_MANAGE = 'flat_rate:wallet:manage'
    FLAT_RATE_WEBHOOK_MANAGE = 'flat_rate:webhook:manage'
    FLAT_RATE_USER_MANAGE = 'flat_rate:user:manage'
    FLAT_RATE_INVOICE_CREATE = 'flat_rate:invoice:create'
    FLAT_RATE_INVOICE_READ = 'flat_rate:invoice:read'
    FLAT_RATE_PROFILE_READ = 'flat_rate:profile:read'
    FLAT_RATE_PROFILE_UPDATE = 'flat_rate:profile:update'


class ApiKeyPermission(BaseModel):
    """
    API Key Permissions model for fine-grained access control.
    Maps API keys to specific permissions.
    """
    __tablename__ = 'api_key_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    api_key_id = db.Column(db.Integer, db.ForeignKey('client_api_keys.id'), nullable=False)
    permission = db.Column(db.String(100), nullable=False)  # Permission string (e.g., 'payment:create')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    api_key = db.relationship('ClientApiKey', backref=db.backref('key_permissions', lazy=True, cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<ApiKeyPermission {self.permission} for key {self.api_key_id}>'
    
    @classmethod
    def get_available_permissions(cls):
        """
        Returns a list of all available permission strings that can be assigned to an API key.
        These should match the scopes defined in the ApiKeyScope enum.
        """
        return [str(scope.value) for scope in ApiKeyScope]


class ClientApiKey(BaseModel):
    """Client API Keys for secure API access"""
    __tablename__ = 'client_api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    # Key details
    name = db.Column(db.String(100), nullable=False)  # User-friendly name
    key = db.Column(db.String(64), unique=True, nullable=False)  # The actual API key
    key_prefix = db.Column(db.String(12), nullable=False)  # First 8 chars for display
    key_hash = db.Column(db.String(128), nullable=False)  # Hashed version for security
    
    # Enhanced permissions with client type awareness
    permissions = db.Column(db.JSON, default=list)
    
    # Rate limiting - different defaults for client types
    rate_limit = db.Column(db.Integer, default=60)  # requests per minute
    
    # Security enhancements for flat-rate clients
    allowed_ips = db.Column(db.JSON, default=list)  # IP whitelist for enterprise clients
    webhook_secret = db.Column(db.String(64), nullable=True)  # For webhook HMAC verification
    secret_key = db.Column(db.String(64), nullable=True)  # For request signing and authentication
    
    # Client type specific settings
    client_type = db.Column(db.String(20), nullable=True)  # 'commission' or 'flat_rate'
    
    # Status and lifecycle
    is_active = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime)
    usage_count = db.Column(db.Integer, default=0)
    
    # Expiry
    expires_at = db.Column(db.DateTime)  # Optional expiry date
    
    # Audit trail
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)
    
    # Relationships - using string-based references to avoid circular imports
    # Use string-based relationships to avoid circular imports
    client = db.relationship('Client', backref=db.backref('api_keys', lazy=True, cascade='all, delete-orphan'), lazy=True)
    created_by_admin = db.relationship('AdminUser', backref=db.backref('created_api_keys', lazy=True, cascade='all, delete-orphan'), lazy=True)
    
    @staticmethod
    def generate_key():
        """Generate a secure API key"""
        # Generate 32 random bytes, encode as hex = 64 character string
        return secrets.token_hex(32)
    
    @staticmethod
    def generate_key_prefix(key):
        """Generate display prefix from key"""
        return key[:8] + '...'
    
    @staticmethod
    def hash_key(key):
        """Hash the API key for secure storage"""
        from werkzeug.security import generate_password_hash
        return generate_password_hash(key)
    
    @staticmethod
    def verify_key(key, key_hash):
        """Verify an API key against stored hash"""
        from werkzeug.security import check_password_hash
        return check_password_hash(key_hash, key)
    
    @classmethod
    def create_key(cls, client_id, name, permissions=None, rate_limit=60, expires_days=None, created_by_admin_id=None):
        """Create a new API key for a client"""
        key = cls.generate_key()
        key_prefix = cls.generate_key_prefix(key)
        key_hash = cls.hash_key(key)
        
        expires_at = None
        if expires_days:
            expires_at = now_eest() + timedelta(days=expires_days)
        
        api_key = cls(
            client_id=client_id,
            name=name,
            key=key,  # We store the key temporarily for returning to admin
            key_prefix=key_prefix,
            key_hash=key_hash,
            permissions=permissions or [],
            rate_limit=rate_limit,
            expires_at=expires_at,
            created_by_admin_id=created_by_admin_id
        )
        
        db.session.add(api_key)
        db.session.commit()
        
        # Return the key one time only
        return api_key, key
    
    @classmethod
    def create_for_admin(cls, client_id, name, permissions=None, rate_limit=60, 
                         expires_days=None, created_by_admin_id=None):
        """Create a new API key for a client by admin"""
        key = cls.generate_key()
        key_prefix = key[:8] + '...'
        key_hash = cls.hash_key(key)
        
        # Generate secret key and webhook secret
        secret_key = secrets.token_hex(32)
        webhook_secret = secrets.token_hex(24)
        
        expires_at = None
        if expires_days:
            expires_at = now_eest() + timedelta(days=expires_days)
        
        api_key = cls(
            client_id=client_id,
            name=name,
            key=key,  # We store the key temporarily for returning to admin
            key_prefix=key_prefix,
            key_hash=key_hash,
            secret_key=secret_key,
            webhook_secret=webhook_secret,
            permissions=permissions or [],
            rate_limit=rate_limit,
            expires_at=expires_at,
            created_by_admin_id=created_by_admin_id
        )
        
        db.session.add(api_key)
        db.session.commit()
        
        # Return the API key object (contains key, secret_key, webhook_secret)
        return api_key
    
    @classmethod
    def create_for_client(cls, client, name, permissions=None, rate_limit=60, expires_at=None):
        """Create a new API key for a client (self-service)"""
        key = cls.generate_key()
        key_prefix = key[:8] + '...'
        key_hash = cls.hash_key(key)
        
        # Generate secret key and webhook secret for all clients
        secret_key = secrets.token_hex(32)
        webhook_secret = secrets.token_hex(24)
        
        api_key = cls(
            client_id=client.id,
            name=name,
            key=key,  # Store the full key temporarily for returning to user
            key_prefix=key_prefix,
            key_hash=key_hash,
            permissions=permissions or [],
            rate_limit=rate_limit,
            expires_at=expires_at,
            secret_key=secret_key,
            webhook_secret=webhook_secret
        )
        
        return api_key
    
    @classmethod
    def create_for_client_by_type(cls, client, name, permissions=None, rate_limit=None, expires_at=None):
        """Create a new API key for a client with type-specific settings"""
        key = cls.generate_key()
        key_prefix = key[:8] + '...'
        key_hash = cls.hash_key(key)
        
        # Determine client type and set appropriate defaults
        client_type = 'commission' if client.is_commission_based() else 'flat_rate'
        
        # Set default rate limits based on client type
        if rate_limit is None:
            rate_limit = 30 if client.is_commission_based() else 100  # Commission clients get lower limits
        
        # Filter permissions based on client type
        filtered_permissions = cls._filter_permissions_by_client_type(permissions or [], client_type)
        
        # Generate webhook secret for flat-rate clients
        webhook_secret = None
        secret_key = None
        if client.is_flat_rate():
            webhook_secret = secrets.token_hex(24)
            secret_key = secrets.token_hex(32)
        else:
            # Commission clients also get secret keys but simpler webhook secrets
            secret_key = secrets.token_hex(32)
            webhook_secret = secrets.token_hex(16)
        
        api_key = cls(
            client_id=client.id,
            name=name,
            key=key,  # Store the full key temporarily for returning to user
            key_prefix=key_prefix,
            key_hash=key_hash,
            permissions=filtered_permissions,
            rate_limit=rate_limit,
            expires_at=expires_at,
            client_type=client_type,
            webhook_secret=webhook_secret,
            secret_key=secret_key
        )
        
        return api_key
    
    @staticmethod
    def _filter_permissions_by_client_type(permissions, client_type):
        """Filter permissions based on client type"""
        if client_type == 'commission':
            # Commission clients get limited permissions
            allowed_scopes = [
                'commission:payment:create',
                'commission:payment:read', 
                'commission:balance:read',
                'commission:status:check'
            ]
        else:  # flat_rate
            # Flat-rate clients get full access
            allowed_scopes = [scope.value for scope in ApiKeyScope if scope.value.startswith('flat_rate:')]
        
        return [perm for perm in permissions if perm in allowed_scopes]
    
    @classmethod
    def get_permissions_for_client_type(cls, client_type):
        """Get available permissions for a client type"""
        if client_type == 'commission':
            return [
                {'value': 'commission:payment:create', 'label': 'Create Payments', 'description': 'Create new payment requests'},
                {'value': 'commission:payment:read', 'label': 'Read Payments', 'description': 'View payment history and status'},
                {'value': 'commission:balance:read', 'label': 'Read Balance', 'description': 'View account balance'},
                {'value': 'commission:status:check', 'label': 'Check Status', 'description': 'Check transaction status'}
            ]
        else:  # flat_rate
            return [
                {'value': 'flat_rate:payment:create', 'label': 'Create Payments', 'description': 'Create new payment requests'},
                {'value': 'flat_rate:payment:read', 'label': 'Read Payments', 'description': 'View payment history and status'},
                {'value': 'flat_rate:payment:update', 'label': 'Update Payments', 'description': 'Update payment details'},
                {'value': 'flat_rate:withdrawal:create', 'label': 'Create Withdrawals', 'description': 'Request new withdrawals'},
                {'value': 'flat_rate:withdrawal:read', 'label': 'Read Withdrawals', 'description': 'View withdrawal history'},
                {'value': 'flat_rate:withdrawal:approve', 'label': 'Approve Withdrawals', 'description': 'Approve withdrawal requests'},
                {'value': 'flat_rate:balance:read', 'label': 'Read Balance', 'description': 'View account balance'},
                {'value': 'flat_rate:balance:update', 'label': 'Update Balance', 'description': 'Update user balances'},
                {'value': 'flat_rate:wallet:manage', 'label': 'Manage Wallets', 'description': 'Manage user wallets'},
                {'value': 'flat_rate:webhook:manage', 'label': 'Manage Webhooks', 'description': 'configure webhook endpoints'},
                {'value': 'flat_rate:user:manage', 'label': 'Manage Users', 'description': 'Manage user accounts'},
                {'value': 'flat_rate:invoice:create', 'label': 'Create Invoices', 'description': 'Generate invoices'},
                {'value': 'flat_rate:invoice:read', 'label': 'Read Invoices', 'description': 'View invoice history'},
                {'value': 'flat_rate:profile:read', 'label': 'Read Profile', 'description': 'View account profile'},
                {'value': 'flat_rate:profile:update', 'label': 'Update Profile', 'description': 'Update account settings'}
            ]
    
    def get_max_rate_limit(self):
        """Get maximum allowed rate limit for this client type"""
        if self.client_type == 'commission':
            return 60  # Commission clients: max 60 req/min
        else:  # flat_rate
            return 1000  # Flat-rate clients: max 1000 req/min
    
    def is_ip_allowed(self, ip_address):
        """Check if IP address is allowed (for flat-rate clients with IP restrictions)"""
        if not self.allowed_ips:
            return True  # No restrictions
        return ip_address in self.allowed_ips
    
    def generate_webhook_signature(self, payload):
        """Generate HMAC signature for webhook verification (flat-rate clients)"""
        if not self.webhook_secret:
            return None
        
        import hmac
        import hashlib
        
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    def verify_webhook_signature(self, payload, signature):
        """Verify webhook HMAC signature (flat-rate clients)"""
        if not self.webhook_secret or not signature:
            return False
        
        import hmac
        expected_signature = self.generate_webhook_signature(payload)
        return hmac.compare_digest(expected_signature, signature)
    
    def __repr__(self):
        return f'<ClientApiKey {self.name} for {self.client_id}>'

class ApiKeyUsageLog(BaseModel):
    """Log API key usage for monitoring and security"""
    __tablename__ = 'api_key_usage_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    api_key_id = db.Column(db.Integer, db.ForeignKey('client_api_keys.id'), nullable=False)
    
    # Request details
    endpoint = db.Column(db.String(255), nullable=False)
    method = db.Column(db.String(10), nullable=False)  # GET, POST, etc.
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    user_agent = db.Column(db.Text, nullable=True)
    
    # Response details
    status_code = db.Column(db.Integer, nullable=True)
    response_time_ms = db.Column(db.Integer, nullable=True)
    
    # Rate limiting info
    requests_in_window = db.Column(db.Integer, nullable=True)
    
    # Relationships
    api_key = db.relationship('ClientApiKey', backref='usage_logs', lazy=True)

    @classmethod
    def log_request(cls, api_key_id, endpoint, method, ip_address, user_agent, 
                    status_code, response_time_ms, requests_in_window):
        """Log an API request"""
        log_entry = cls(
            api_key_id=api_key_id,
            endpoint=endpoint,
            method=method,
            ip_address=ip_address,
            user_agent=user_agent,
            status_code=status_code,
            response_time_ms=response_time_ms,
            requests_in_window=requests_in_window
        )
        db.session.add(log_entry)
        db.session.commit()
        return log_entry
    
    def __repr__(self):
        return f'<ApiKeyUsageLog {self.method} {self.endpoint} at {self.created_at}>'
