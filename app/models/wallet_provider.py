"""
Wallet Provider Models
Handles different wallet/exchange providers for the payment gateway
"""

from datetime import datetime
from ..utils.timezone import now_eest
from enum import Enum
from app.extensions import db
from sqlalchemy import func, event
import json


class WalletProviderType(str, Enum):
    """Enum for wallet provider types"""
    BINANCE = 'binance'
    COINBASE = 'coinbase'
    KRAKEN = 'kraken'
    MANUAL = 'manual_wallet'
    OTHER = 'other'


class WalletProvider(db.Model):
    """Model for wallet/exchange providers"""
    __tablename__ = 'wallet_providers'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # e.g., "Binance Main", "Coinbase Backup"
    provider_type = db.Column(db.Enum(WalletProviderType), nullable=False)
    
    # API configuration
    api_key = db.Column(db.Text)  # Encrypted API key
    api_secret = db.Column(db.Text)  # Encrypted API secret
    api_passphrase = db.Column(db.Text)  # For some exchanges like Coinbase Pro
    sandbox_mode = db.Column(db.Boolean, default=False)
    
    # Manual Wallet configuration (for non-exchange wallets)
    wallet_addresses = db.Column(db.Text)  # JSON: {"BTC": "address", "ETH": "address"}
    
    # Provider Settings
    is_active = db.Column(db.Boolean, default=True)
    is_primary = db.Column(db.Boolean, default=False)  # Only one can be primary
    priority = db.Column(db.Integer, default=100)  # Lower number = higher priority
    
    # Supported Features
    supports_deposits = db.Column(db.Boolean, default=True)
    supports_withdrawals = db.Column(db.Boolean, default=True)
    supports_balance_check = db.Column(db.Boolean, default=True)
    
    # Rate Limiting
    max_requests_per_minute = db.Column(db.Integer, default=600)  # API rate limit
    
    # Status Monitoring
    last_health_check = db.Column(db.DateTime)
    health_status = db.Column(db.String(20), default='unknown')  # healthy, warning, error, unknown
    last_error_message = db.Column(db.Text)
    
    # Metadata
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    supported_currencies = db.relationship('WalletProviderCurrency', back_populates='provider', lazy='dynamic', cascade='all, delete-orphan')
    provider_transactions = db.relationship('WalletProviderTransaction', back_populates='provider', cascade='all, delete-orphan')
    balances = db.relationship('WalletBalance', back_populates='provider', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<WalletProvider {self.name}>'
    
    @property
    def wallet_addresses_dict(self):
        """Return wallet addresses as dictionary"""
        if self.wallet_addresses:
            try:
                return json.loads(self.wallet_addresses)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    @wallet_addresses_dict.setter
    def wallet_addresses_dict(self, value):
        """Set wallet addresses from dictionary"""
        if isinstance(value, dict):
            self.wallet_addresses = json.dumps(value)
        else:
            self.wallet_addresses = None
    
    @classmethod
    def get_primary(cls):
        """Get the primary wallet provider"""
        return cls.query.filter_by(is_primary=True, is_active=True).first()
    
    @classmethod
    def get_active_providers(cls):
        """Get all active providers ordered by priority"""
        return cls.query.filter_by(is_active=True).order_by(cls.priority.asc()).all()
    
    def set_as_primary(self):
        """Set this provider as primary (removes primary from others)"""
        # Remove primary status from all other providers
        db.session.query(WalletProvider).filter(WalletProvider.id != self.id).update(
            {'is_primary': False}
        )
        self.is_primary = True
        db.session.commit()
    
    def update_health_status(self, status, error_message=None):
        """Update health check status"""
        self.health_status = status
        self.last_health_check = now_eest()
        if error_message:
            self.last_error_message = error_message
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'provider_type': self.provider_type.value,
            'is_active': self.is_active,
            'is_primary': self.is_primary,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class WalletProviderCurrency(db.Model):
    """Supported currencies for each wallet provider"""
    __tablename__ = 'wallet_provider_currencies'
    __table_args__ = (
        db.UniqueConstraint('provider_id', 'currency_code', name='unique_provider_currency'),
        {'extend_existing': True}
    )
    
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('wallet_providers.id'), nullable=False)
    currency_code = db.Column(db.String(10), nullable=False)  # BTC, ETH, USDT, etc.
    
    # Currency-specific settings
    is_enabled = db.Column(db.Boolean, default=True)
    minimum_deposit = db.Column(db.Numeric(20, 8), default=0)
    minimum_withdrawal = db.Column(db.Numeric(20, 8), default=0)
    withdrawal_fee = db.Column(db.Numeric(20, 8), default=0)
    
    # For manual wallets
    wallet_address = db.Column(db.String(255))  # Specific address for this currency
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    provider = db.relationship('WalletProvider', back_populates='supported_currencies')
    
    def __repr__(self):
        return f'<WalletProviderCurrency {self.provider.name}-{self.currency_code}>'


class WalletProviderTransaction(db.Model):
    """Track all wallet provider transactions for monitoring and reconciliation"""
    __tablename__ = 'wallet_provider_transactions'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('wallet_providers.id'), nullable=False)
    
    # Transaction Details
    external_id = db.Column(db.String(255))  # Transaction ID from the exchange/wallet
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal, internal_transfer
    currency_code = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Numeric(20, 8), nullable=False)
    fee = db.Column(db.Numeric(20, 8), default=0)
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, cancelled
    
    # Addresses
    from_address = db.Column(db.String(255))
    to_address = db.Column(db.String(255))
    
    # Blockchain Info
    txid = db.Column(db.String(255))  # Blockchain transaction ID
    block_height = db.Column(db.Integer)
    confirmations = db.Column(db.Integer, default=0)
    
    # Metadata
    notes = db.Column(db.Text)
    raw_response = db.Column(db.Text)  # Store original API response for debugging
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    provider = db.relationship('WalletProvider', back_populates='provider_transactions')
    
    def __repr__(self):
        return f'<WalletProviderTransaction {self.transaction_type}-{self.currency_code}-{self.amount}>'


class WalletBalance(db.Model):
    """Current wallet balances across all providers"""
    __tablename__ = 'wallet_balances'
    __table_args__ = (
        db.UniqueConstraint('provider_id', 'currency', name='unique_provider_balance'),
        {'extend_existing': True}
    )
    
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('wallet_providers.id'), nullable=False)
    currency = db.Column(db.String(10), nullable=False)
    
    # Balance Information
    available_balance = db.Column(db.Numeric(20, 8), default=0)
    locked_balance = db.Column(db.Numeric(20, 8), default=0)  # Funds in pending orders
    total_balance = db.Column(db.Numeric(20, 8), default=0)
    
    # Metadata
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    update_source = db.Column(db.String(50), default='api')  # api, manual, webhook
    
    # Relationships
    provider = db.relationship('WalletProvider', back_populates='balances')
    
    def __repr__(self):
        return f'<WalletBalance {self.provider.name}-{self.currency}: {self.available_balance}>'
    
    @classmethod
    def get_total_balance(cls, currency):
        """Get total balance across all active providers for a currency"""
        from app.models.wallet_provider import WalletProvider as WP
        return db.session.query(func.sum(cls.available_balance)).join(WP).filter(
            cls.currency == currency,
            WP.is_active == True
        ).scalar() or 0
