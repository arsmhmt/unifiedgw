from app.extensions import db
from app.models.base import BaseModel
from app.models.user import User
from app.models.client import Client
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from decimal import Decimal

class BankGatewayProvider(BaseModel):
    """Provider model for bank gateway functionality"""
    __tablename__ = 'bank_gateway_providers'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    deposit_commission = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    withdraw_commission = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    is_blocked = db.Column(db.Boolean, default=False)
    
    # Relationships
    user = db.relationship('User', backref='bank_gateway_provider')
    bank_accounts = db.relationship('BankGatewayAccount', backref='provider', lazy='dynamic')
    
    def __repr__(self):
        return f'<BankGatewayProvider {self.name}>'

class BankGatewayAccount(BaseModel):
    """Bank account model for gateway providers"""
    __tablename__ = 'bank_gateway_accounts'
    
    provider_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_providers.id'), nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    account_holder = db.Column(db.String(100), nullable=False)
    iban = db.Column(db.String(34), nullable=False)
    account_limit = db.Column(db.Numeric(12, 2), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    transactions = db.relationship('BankGatewayTransaction', backref='bank_account', lazy='dynamic')
    
    def __repr__(self):
        return f'<BankGatewayAccount {self.bank_name} - {self.iban}>'
    
    @property
    def available_balance(self):
        """Calculate available balance based on account limit and pending transactions"""
        pending_amount = self.transactions.filter_by(status='pending').with_entities(
            func.sum(BankGatewayTransaction.amount)).scalar() or Decimal('0.00')
        return self.account_limit - pending_amount

class BankGatewayClientSite(BaseModel):
    """Client site configuration for bank gateway"""
    __tablename__ = 'bank_gateway_client_sites'
    
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    site_name = db.Column(db.String(100), nullable=False)
    site_url = db.Column(db.String(255), nullable=False)
    callback_url = db.Column(db.String(255), nullable=True)
    success_url = db.Column(db.String(255), nullable=True)
    fail_url = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    client = db.relationship('Client', backref='bank_gateway_sites')
    api_key = db.relationship('BankGatewayAPIKey', backref='client_site', uselist=False)
    transactions = db.relationship('BankGatewayTransaction', backref='client_site', lazy='dynamic')
    
    def __repr__(self):
        return f'<BankGatewayClientSite {self.site_name}>'

class BankGatewayAPIKey(BaseModel):
    """API key for bank gateway client authentication"""
    __tablename__ = 'bank_gateway_api_keys'
    
    client_site_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_client_sites.id'), unique=True, nullable=False)
    key = db.Column(db.String(64), unique=True, nullable=False)
    
    def __repr__(self):
        return f'<BankGatewayAPIKey {self.key[:8]}...>'

class BankGatewayTransaction(BaseModel):
    """Transaction model for bank gateway operations"""
    __tablename__ = 'bank_gateway_transactions'
    
    # Foreign keys
    client_site_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_client_sites.id'), nullable=False)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_accounts.id'), nullable=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_providers.id'), nullable=True)
    
    # Transaction details
    transaction_type = db.Column(db.String(20), nullable=False)  # 'deposit', 'withdraw'
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default='TRY')
    
    # Status and processing
    status = db.Column(db.String(20), default='pending')  # 'pending', 'confirmed', 'rejected', 'expired'
    external_transaction_id = db.Column(db.String(100), nullable=True)
    reference_code = db.Column(db.String(50), unique=True, nullable=False)
    
    # User information
    user_name = db.Column(db.String(100), nullable=True)
    user_email = db.Column(db.String(100), nullable=True)
    user_phone = db.Column(db.String(20), nullable=True)
    
    # Commission and fees
    commission_amount = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    provider_commission = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    
    # Timestamps
    expires_at = db.Column(db.DateTime, nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    
    # Additional data
    notes = db.Column(db.Text, nullable=True)
    callback_data = db.Column(db.JSON, nullable=True)
    
    def __repr__(self):
        return f'<BankGatewayTransaction {self.reference_code} - {self.amount} {self.currency}>'
    
    @property
    def net_amount(self):
        """Calculate net amount after commissions"""
        return self.amount - self.commission_amount - self.provider_commission

class BankGatewayCommission(BaseModel):
    """Commission tracking for bank gateway operations"""
    __tablename__ = 'bank_gateway_commissions'
    
    transaction_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_transactions.id'), nullable=False)
    commission_type = db.Column(db.String(20), nullable=False)  # 'client', 'provider', 'platform'
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    percentage = db.Column(db.Numeric(5, 2), nullable=True)
    is_paid = db.Column(db.Boolean, default=False)  # Track if commission has been paid
    paid_at = db.Column(db.DateTime, nullable=True)
    paid_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    payment_notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    transaction = db.relationship('BankGatewayTransaction', backref='commissions')
    payer = db.relationship('User', backref='paid_commissions', foreign_keys=[paid_by])
    
    def __repr__(self):
        return f'<BankGatewayCommission {self.commission_type} - {self.amount}>'

class BankGatewayDepositRequest(BaseModel):
    """Deposit request model for bank gateway"""
    __tablename__ = 'bank_gateway_deposit_requests'
    
    transaction_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_transactions.id'), nullable=False)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_accounts.id'), nullable=False)
    
    # Deposit specific information
    sender_name = db.Column(db.String(100), nullable=True)
    sender_iban = db.Column(db.String(34), nullable=True)
    receipt_image = db.Column(db.String(255), nullable=True)
    processing_notes = db.Column(db.Text, nullable=True)
    
    # Status tracking
    verification_status = db.Column(db.String(20), default='pending')  # 'pending', 'verified', 'rejected'
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    transaction = db.relationship('BankGatewayTransaction', backref='deposit_request', uselist=False)
    verifier = db.relationship('User', backref='verified_deposits')
    
    def __repr__(self):
        return f'<BankGatewayDepositRequest {self.transaction.reference_code}>'

class BankGatewayWithdrawalRequest(BaseModel):
    """Withdrawal request model for bank gateway"""
    __tablename__ = 'bank_gateway_withdrawal_requests'
    
    # Foreign keys
    client_site_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_client_sites.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_providers.id'), nullable=True)
    
    # Withdrawal details
    user_name = db.Column(db.String(100), nullable=False)
    user_surname = db.Column(db.String(100), nullable=True)
    iban = db.Column(db.String(34), nullable=False)
    bank_name = db.Column(db.String(100), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default='TRY')
    
    # Status tracking
    status = db.Column(db.String(20), default='pending')  # 'pending', 'approved', 'rejected', 'processing', 'completed'
    reference_code = db.Column(db.String(50), unique=True, nullable=False)
    
    # Processing information
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    processing_notes = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    
    # Commission
    commission_amount = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    provider_commission = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    
    # Additional data
    user_email = db.Column(db.String(100), nullable=True)
    user_phone = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    client_site = db.relationship('BankGatewayClientSite', backref='withdrawal_requests')
    provider = db.relationship('BankGatewayProvider', backref='withdrawal_requests')
    processor = db.relationship('User', backref='processed_withdrawals', foreign_keys=[processed_by])
    
    def __repr__(self):
        return f'<BankGatewayWithdrawalRequest {self.reference_code} - {self.amount} {self.currency}>'
    
    @property
    def net_amount(self):
        """Calculate net amount after commissions"""
        return self.amount - self.commission_amount - self.provider_commission

class BankGatewayProviderCommission(BaseModel):
    """Provider commission tracking for payment processing"""
    __tablename__ = 'bank_gateway_provider_commissions'
    
    # Foreign keys
    provider_id = db.Column(db.Integer, db.ForeignKey('bank_gateway_providers.id'), nullable=False)
    transaction_id = db.Column(db.Integer, nullable=True)  # Can be transaction or withdrawal request
    
    # Commission details
    transaction_type = db.Column(db.String(20), nullable=False)  # 'deposit', 'withdraw'
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default='TRY')
    
    # Payment tracking
    is_paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    paid_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)  # 'bank_transfer', 'cash', 'crypto', etc.
    payment_reference = db.Column(db.String(100), nullable=True)
    payment_notes = db.Column(db.Text, nullable=True)
    
    # Additional tracking
    related_transaction_ref = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    provider = db.relationship('BankGatewayProvider', backref='commissions')
    payer = db.relationship('User', backref='paid_provider_commissions', foreign_keys=[paid_by])
    
    def __repr__(self):
        return f'<BankGatewayProviderCommission {self.provider.name} - {self.amount} - {"Paid" if self.is_paid else "Unpaid"}>'
    
    @property
    def status_display(self):
        """Human-readable status"""
        return 'Paid' if self.is_paid else 'Unpaid'
