from datetime import datetime
from ..utils.timezone import now_eest
from sqlalchemy.orm import relationship, validates
from sqlalchemy import ForeignKey, func, CheckConstraint
from ..extensions import db
from .base import BaseModel
from app.utils.crypto import validate_crypto_address
from app.models.enums import WithdrawalMethodType, WithdrawalStatus, WithdrawalType

class WithdrawalRequest(BaseModel):
    __tablename__ = 'withdrawal_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False)
    crypto_address = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    withdrawal_type = db.Column(db.Enum(WithdrawalType), default=WithdrawalType.USER_REQUEST)
    
    # Administrative fields
    approved_by = db.Column(db.Integer, db.ForeignKey('admin_users.id'))
    approved_at = db.Column(db.DateTime)
    rejected_by = db.Column(db.Integer, db.ForeignKey('admin_users.id'))
    rejected_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    
    # Fee information
    fee = db.Column(db.Float, default=0.0)
    net_amount = db.Column(db.Float)  # Amount after fees
    
    # User information (for user withdrawals)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # For B2C withdrawals
    user_wallet_address = db.Column(db.String(100))  # User's destination wallet
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = db.relationship('Client', back_populates='withdrawal_requests')
    user = db.relationship('User', backref='withdrawal_requests')
    approved_by_admin = db.relationship('AdminUser', foreign_keys=[approved_by], backref='approved_withdrawals')
    rejected_by_admin = db.relationship('AdminUser', foreign_keys=[rejected_by], backref='rejected_withdrawals')
    
    # Relationship with Withdrawal
    withdrawal = db.relationship('Withdrawal', back_populates='request', uselist=False)
    
    def validate(self):
        if not validate_crypto_address(self.crypto_address, self.currency):
            raise ValueError(f"Invalid {self.currency} address")
        if self.amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        return True

class WithdrawalMethod(BaseModel):
    """
    Represents a withdrawal method that clients can use to withdraw funds.
    Supports multiple types of withdrawal methods including bank transfers and cryptocurrencies.
    """
    __tablename__ = 'withdrawal_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # User-defined name for the method
    method_type = db.Column(db.Enum(WithdrawalMethodType), nullable=False)
    
    # Bank transfer fields
    bank_name = db.Column(db.String(100))
    account_holder_name = db.Column(db.String(100))
    account_number = db.Column(db.String(50))
    iban = db.Column(db.String(50))
    swift_code = db.Column(db.String(50))
    
    # Crypto fields
    crypto_currency = db.Column(db.String(10))  # BTC, ETH, etc.
    wallet_address = db.Column(db.String(100))
    
    # Status
    is_verified = db.Column(db.Boolean, default=False)
    is_default = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = db.relationship('Client', back_populates='withdrawal_methods')
    
    __table_args__ = (
        # Simple unique constraint on client_id and name to prevent duplicates
        db.UniqueConstraint('client_id', 'name', name='uq_client_method_name'),
    )
    
    def __init__(self, **kwargs):
        super(WithdrawalMethod, self).__init__(**kwargs)
        self.validate()
        
    def validate(self):
        """Validate the withdrawal method based on its type."""
        if self.method_type == WithdrawalMethodType.BANK:
            if not all([self.bank_name, self.account_holder_name]):
                raise ValueError("Bank name and account holder name are required for bank transfers")
            if not (self.account_number or self.iban):
                raise ValueError("Either account number or IBAN is required for bank transfers")
        elif self.method_type == WithdrawalMethodType.CRYPTO:
            if not all([self.crypto_currency, self.wallet_address]):
                raise ValueError("Crypto currency and wallet address are required for crypto withdrawals")
        elif self.method_type == WithdrawalMethodType.OTHER:
            if not self.name:
                raise ValueError("Name is required for other withdrawal methods")
        else:
            raise ValueError(f"Invalid withdrawal method type: {self.method_type}")
    
    @classmethod
    def set_default_method(cls, client_id, method_id, session=None):
        """Set a withdrawal method as the default for a client."""
        from ..extensions import db
        
        session = session or db.session
        
        # First, unset any existing default method for this client
        session.query(cls).filter(
            cls.client_id == client_id,
            cls.is_default == True
        ).update({'is_default': False})
        
        # Set the new default method
        method = session.query(cls).filter(
            cls.id == method_id,
            cls.client_id == client_id
        ).first()
        
        if method:
            method.is_default = True
            session.add(method)
            
        return method
    
    @validates('wallet_address')
    def validate_wallet_address(self, key, address):
        """Validate cryptocurrency wallet address if method type is crypto."""
        if self.method_type == WithdrawalMethodType.CRYPTO and address:
            if not validate_crypto_address(address, self.crypto_currency):
                raise ValueError(f'Invalid {self.crypto_currency} wallet address')
        return address
    
    def to_dict(self):
        """Convert withdrawal method to dictionary for API responses."""
        return {
            'id': self.id,
            'name': self.name,
            'method_type': self.method_type.value,
            'bank_name': self.bank_name,
            'account_holder_name': self.account_holder_name,
            'account_number': self.account_number,
            'iban': self.iban,
            'swift_code': self.swift_code,
            'crypto_currency': self.crypto_currency,
            'wallet_address': self.wallet_address,
            'is_verified': self.is_verified,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Withdrawal(BaseModel):
    __tablename__ = 'withdrawals'
    
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('withdrawal_requests.id'), nullable=False)
    transaction_hash = db.Column(db.String(100))
    status = db.Column(db.Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    request = db.relationship('WithdrawalRequest', back_populates='withdrawal')
    
    # Relationship with Client
    client = db.relationship('Client', back_populates='withdrawals')

    def process(self):
        """Process withdrawal request"""
        if self.status != WithdrawalStatus.APPROVED:
            raise ValueError("Withdrawal must be approved first")
            
        # TODO: Implement actual crypto transfer
        # This would typically use a crypto wallet API (e.g., Binance)
        
        self.status = WithdrawalStatus.PROCESSING
        self.processed_at = now_eest()
        db.session.commit()
    
    def complete(self, tx_hash):
        """Mark withdrawal as completed"""
        self.status = WithdrawalStatus.COMPLETED
        self.tx_hash = tx_hash
        self.processed_at = now_eest()
        db.session.commit()
    
    def reject(self, reason):
        """Reject withdrawal request"""
        self.status = WithdrawalStatus.REJECTED
        self.rejection_reason = reason
        self.processed_at = now_eest()
        db.session.commit()

def get_client_balance(client_id):
    """Calculate client's available balance"""
    from .payment import Payment  # Import here to avoid circular imports
    
    # Get total deposits
    total_in = db.session.query(func.sum(Payment.amount)).filter_by(
        client_id=client_id,
        status='completed'
    ).scalar() or 0
    
    # Get total withdrawals
    total_out = db.session.query(func.sum(WithdrawalRequest.amount)).filter_by(
        client_id=client_id,
        status='completed'
    ).scalar() or 0
    
    # Get total commissions
    commission = db.session.query(func.sum(Payment.commission)).filter_by(
        client_id=client_id,
        status='completed'
    ).scalar() or 0
    
    return total_in - total_out - commission
