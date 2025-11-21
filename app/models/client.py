from ..utils.timezone import now_eest
from ..extensions import db  # Changed from 'from app import db'
from datetime import datetime
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from .base import BaseModel
from flask_login import UserMixin
from .enums import PaymentStatus
from sqlalchemy import event, func, distinct
from sqlalchemy.orm import relationship, backref

# Import the feature access configuration
from ..config.packages import FeatureAccessMixin, sync_client_status_with_package, client_has_feature
from ..config import config

class Client(BaseModel, FeatureAccessMixin, UserMixin):
    __tablename__ = 'clients'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platforms.id'), nullable=True)
    name = db.Column(db.String(255), nullable=True)  # Individual/contact person name
    username = db.Column(db.String(50), unique=True, nullable=True)  # Login username
    company_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    tax_id = db.Column(db.String(50))
    vat_number = db.Column(db.String(50))
    registration_number = db.Column(db.String(50))
    website = db.Column(db.String(255))
    logo_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100))
    verification_sent_at = db.Column(db.DateTime)
    verified_at = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    password_hash = db.Column(db.String(255))
    reset_password_token = db.Column(db.String(100))
    reset_password_sent_at = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, default=0)
    locked_at = db.Column(db.DateTime)
    contact_person = db.Column(db.String(255))
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(20))
    notes = db.Column(db.Text)
    settings = db.Column(db.JSON)
    
    # API and integration fields
    api_key = db.Column(db.String(64), unique=True, nullable=True)
    rate_limit = db.Column(db.Integer, default=100)  # requests per minute
    theme_color = db.Column(db.String(7), default='#6c63ff')  # hex color code
    
    # Commission fields (keeping only one set)
    deposit_commission_rate = db.Column(db.Float, default=0.035)  # 3.5%
    withdrawal_commission_rate = db.Column(db.Float, default=0.015)  # 1.5%
    balance = db.Column(db.Numeric(precision=18, scale=8), default=Decimal('0.0'))
    
    # Usage tracking for flat-rate plans (NEW - critical for margin protection)
    current_month_volume = db.Column(db.Numeric(20, 2), default=Decimal('0.00'))  # Current month volume in USD
    current_month_transactions = db.Column(db.Integer, default=0)  # Current month transaction count
    last_usage_reset = db.Column(db.DateTime, nullable=True)  # Last time usage was reset (audit trail)
    
    # Package relationship
    package_id = db.Column(db.Integer, db.ForeignKey('client_packages.id'), nullable=True)
    package = db.relationship('ClientPackage', back_populates='clients', lazy=True)
    
    # Branch relationship - each client belongs to a branch (superadmin)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    branch = db.relationship('Branch', back_populates='clients', lazy=True)
    
    # Feature overrides for manual admin control
    features_override = db.Column(db.PickleType, default=list)  # Optional custom features
    
    # Relationships
    user = db.relationship('User', back_populates='client', lazy=True)
    platform = db.relationship('Platform', back_populates='clients', lazy=True)
    
    payments = db.relationship('Payment', 
                            back_populates='client',
                            lazy='dynamic',
                            cascade='all, delete-orphan')
    
    # Commission snapshots
    commission_snapshot_records = db.relationship('CommissionSnapshot', 
                                               back_populates='client',
                                               lazy=True,
                                               cascade='all, delete-orphan')
    
    invoices = db.relationship('Invoice', 
                          back_populates='client',
                          lazy=True,
                          cascade='all, delete-orphan')
                             
    recurring_payments = db.relationship('RecurringPayment', 
                                   back_populates='client',
                                   lazy=True,
                                   cascade='all, delete-orphan')
                                        
    documents = db.relationship('ClientDocument', 
                             back_populates='client',
                             lazy=True,
                             cascade='all, delete-orphan')
                               
    notification_preferences = db.relationship('ClientNotificationPreference', 
                                             back_populates='client',
                                             lazy=True,
                                             cascade='all, delete-orphan')
                                             
    withdrawal_requests = db.relationship('WithdrawalRequest', 
                                       back_populates='client',
                                       lazy=True,
                                       cascade='all, delete-orphan')
                                       
    withdrawals = db.relationship('Withdrawal', 
                               back_populates='client',
                               lazy=True,
                               cascade='all, delete-orphan')
                               
    withdrawal_methods = db.relationship('WithdrawalMethod', 
                                     back_populates='client',
                                     lazy=True,
                                     cascade='all, delete-orphan')
    
    # Multi-wallet support relationships
    wallets = db.relationship('ClientWallet', 
                           back_populates='client',
                           lazy=True,
                           cascade='all, delete-orphan')
                           
    pricing_plan = db.relationship('ClientPricingPlan', 
                                back_populates='client',
                                uselist=False,  # One-to-one relationship
                                cascade='all, delete-orphan')
    
    def get_primary_wallet(self):
        """Get the client's primary wallet"""
        from .client_wallet import WalletStatus
        return self.wallets.filter_by(status=WalletStatus.ACTIVE.value).first()
    
    def get_current_package(self):
        """Get the client's current package"""
        return self.package if self.package_id else None
    
    # Note: has_feature method is inherited from FeatureAccessMixin
    # which uses the new centralized package-to-feature mapping
    
    def get_client_type(self):
        """Get client type from package (commission/flat_rate)"""
        package = self.get_current_package()
        return package.client_type if package else None
    
    def is_commission_based(self):
        """Check if client uses commission-based pricing (Type 1)"""
        from .client_package import ClientType
        return self.get_client_type() == ClientType.COMMISSION
    
    def is_flat_rate(self):
        """Check if client uses flat-rate pricing (Type 2)"""
        from .client_package import ClientType
        return self.get_client_type() == ClientType.FLAT_RATE
    
    def has_custom_wallet(self):
        """Check if client has their own wallet configuration"""
        # For flat-rate clients, they typically use their own wallets
        return self.is_flat_rate()
    
    def get_commission_rate(self, transaction_type='deposit'):
        """Get commission rate based on package"""
        package = self.get_current_package()
        if package and package.commission_rate:
            return float(package.commission_rate)
        # Fallback to old commission fields
        if transaction_type == 'deposit':
            return self.deposit_commission_rate or 0.035
        else:
            return self.withdrawal_commission_rate or 0.015
    
    def get_balance(self):
        from .payment import Payment  # Local import to avoid circular imports
        
        total_deposits = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).\
            filter(Payment.client_id == self.id, 
                  Payment.status == PaymentStatus.APPROVED).scalar() or 0
            
        # Note: Withdrawal calculations would need proper withdrawal model
        total_withdrawals = 0  # Placeholder until proper withdrawal model is available
            
        return float(total_deposits - total_withdrawals)
    
    def get_payment_history(self):
        from .payment import Payment  # Local import to avoid circular imports
        return self.payments.order_by(Payment.created_at.desc()).all()
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password with proper None handling"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        """Return prefixed ID for Flask-Login"""
        return f'client_{self.id}'

    @property
    def is_locked(self):
        """Check if the client account is locked due to too many failed login attempts."""
        if not self.locked_at:
            return False
        lock_duration = now_eest() - self.locked_at
        return lock_duration.total_seconds() < 3600  # Lock for 1 hour
        
    @property
    def allowed_coins(self):
        """Get the list of coin symbols allowed for this client's package."""
        if not hasattr(self, 'package') or not self.package:
            return []
            
        from .coin import Coin
        coins = Coin.get_allowed_coins(self.package.slug)
        return [coin.symbol for coin in coins]
        
    def is_coin_allowed(self, coin_symbol):
        """Check if a coin is allowed for this client's package."""
        if not coin_symbol:
            return False
        return coin_symbol.upper() in self.allowed_coins
        
    def get_coin_limit(self):
        """Get the maximum number of coins allowed for this client's package."""
        if not hasattr(self, 'package') or not self.package:
            return 0
        return config.PACKAGE_COIN_LIMITS.get(self.package.slug, 0)
        
    def get_coin_usage(self):
        """Get the number of unique coins used by this client."""
        from .transaction import Transaction  # Import here to avoid circular imports
        
        # Get count of unique coins used in transactions
        unique_coins_count = db.session.query(
            func.count(distinct(Transaction.coin))
        ).filter(
            Transaction.client_id == self.id
        ).scalar() or 0
        
        return unique_coins_count
    
    def to_dict(self):
        return {
            'id': self.id,
            'company_name': self.company_name,
            'email': self.email,
            'is_active': self.is_active,
            'is_verified': self.is_verified
        }

    def get_documents(self):
        return self.documents.all()
        
    def get_30d_volume(self):
        """Calculate total payment volume for the last 30 days"""
        from .payment import Payment
        from datetime import datetime, timedelta
        
        thirty_days_ago = now_eest() - timedelta(days=30)
        
        total = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).\
            filter(Payment.client_id == self.id,
                  Payment.status == PaymentStatus.APPROVED,
                  Payment.created_at >= thirty_days_ago).scalar() or 0
                  
        return float(total)
    
    def get_30d_commission(self):
        """Calculate total commission for the last 30 days"""
        from .payment import Payment
        from datetime import datetime, timedelta
        
        thirty_days_ago = now_eest() - timedelta(days=30)
        
        # Get all approved payments in the last 30 days
        payments = Payment.query.filter(
            Payment.client_id == self.id,
            Payment.status == PaymentStatus.APPROVED,
            Payment.created_at >= thirty_days_ago
        ).all()
        
        # Calculate commission for each payment and sum them up
        total_commission = 0
        for payment in payments:
            if payment.type == 'deposit':
                commission_rate = self.deposit_commission_rate or 0
            else:
                commission_rate = self.withdrawal_commission_rate or 0
                
            total_commission += float(payment.amount) * (commission_rate / 100)
            
        return total_commission
    
    def get_lifetime_commission(self):
        """Calculate total lifetime commission"""
        from .payment import Payment
        
        # Get all approved payments
        payments = Payment.query.filter(
            Payment.client_id == self.id,
            Payment.status == PaymentStatus.APPROVED
        ).all()
        
        # Calculate commission for each payment and sum them up
        total_commission = 0
        for payment in payments:
            if payment.type == 'deposit':
                commission_rate = self.deposit_commission_rate or 0
            else:
                commission_rate = self.withdrawal_commission_rate or 0
                
            total_commission += float(payment.amount) * (commission_rate / 100)
            
        return total_commission
    
    def get_all_features(self):
        """Return all available features in the system (for dashboard display)"""
        from app.models.client_package import Feature
        return Feature.query.order_by(Feature.name).all()

    def get_dashboard_features(self):
        """
        Return the correct dashboard features for this client based on their package/type.
        Commission-based: minimal, standard features only.
        Flat-rate: features based on their package/status.
        """
        # Commission-based clients: minimal, standard features
        if self.is_commission_based():
            return [
                {
                    'key': 'basic_payment',
                    'name': 'Basic Payment Processing',
                    'icon': 'bi-credit-card',
                    'description': 'Accept crypto payments with simple integration.'
                },
                {
                    'key': 'platform_wallet',
                    'name': 'Platform Wallet',
                    'icon': 'bi-wallet2',
                    'description': 'Funds are held in a secure platform wallet.'
                },
                {
                    'key': 'basic_analytics',
                    'name': 'Basic Analytics',
                    'icon': 'bi-bar-chart',
                    'description': 'View basic payment and withdrawal stats.'
                },
                {
                    'key': 'email_support',
                    'name': 'Email Support',
                    'icon': 'bi-envelope',
                    'description': 'Get help via email for any issues.'
                },
                {
                    'key': 'withdraw_request',
                    'name': 'Withdrawal Request',
                    'icon': 'bi-arrow-down-circle',
                    'description': 'Request payout of your net balance.'
                }
            ]
        # Flat-rate clients: features based on their package
        package = self.get_current_package()
        if not package:
            return []
        # Example: You may want to fetch features from the package relationship
        # If package.features is a relationship/list of Feature objects:
        features = []
        for feature in getattr(package, 'features', []) or []:
            features.append({
                'key': feature.key,
                'name': feature.name,
                'icon': feature.icon or 'bi-star',
                'description': feature.description
            })
        return features
    
    def get_pending_withdrawal_requests_count(self):
        """Get count of pending withdrawal requests for this client"""
        try:
            from app.models.withdrawal import WithdrawalRequest, WithdrawalStatus
            return WithdrawalRequest.query.filter_by(
                client_id=self.id,
                status=WithdrawalStatus.PENDING
            ).count()
        except:
            return 0
    
    def is_admin(self):
        """Return False for Client users (not admin)."""
        return False
    
class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    platform_id = db.Column(db.Integer, db.ForeignKey('platforms.id'), nullable=True, index=True)
    invoice_number = db.Column(db.String(20), unique=True, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = db.relationship('Client', back_populates='invoices')
    platform = db.relationship('Platform', back_populates='invoices')
    
    def generate_pdf(self):
        # Implementation for generating PDF invoice
        pass

class ClientDocument(db.Model):
    __tablename__ = 'client_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    
    # Relationship with Client
    client = db.relationship('Client', back_populates='documents')

class ClientNotificationPreference(db.Model):
    __tablename__ = 'client_notification_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    channel = db.Column(db.String(20), nullable=False)  # email, sms, etc.
    enabled = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with Client
    client = db.relationship('Client', back_populates='notification_preferences')

# Event listeners for audit trail and package sync
@event.listens_for(Client, 'after_insert')
def log_client_insert(mapper, connection, target):
    from .audit import AuditTrail, AuditActionType
    AuditTrail.log_action(
        user_id=target.id,
        action_type=AuditActionType.CREATE.value,
        entity_type='client',
        entity_id=target.id,
        old_value=None,
        new_value=target.to_dict()
    )

@event.listens_for(Client, 'after_update')
def log_client_update(mapper, connection, target):
    from .audit import AuditTrail, AuditActionType
    AuditTrail.log_action(
        user_id=target.id,
        action_type=AuditActionType.UPDATE.value,
        entity_type='client',
        entity_id=target.id,
        old_value=None,
        new_value=target.to_dict()
    )

    # Usage tracking methods for flat-rate plans (NEW)
    def is_exceeding_volume_limits(self):
        """Check if client is exceeding their monthly volume limits"""
        if not self.package or not self.package.max_volume_per_month:
            return False  # Unlimited volume
        return self.current_month_volume > self.package.max_volume_per_month
    
    def is_exceeding_transaction_limits(self):
        """Check if client is exceeding their monthly transaction limits"""
        if not self.package or not self.package.max_transactions_per_month:
            return False  # Unlimited transactions
        return self.current_month_transactions > self.package.max_transactions_per_month
    
    def get_volume_utilization_percent(self):
        """Get percentage of monthly volume limit used"""
        if not self.package or not self.package.max_volume_per_month:
            return 0  # Unlimited
        return (float(self.current_month_volume) / float(self.package.max_volume_per_month)) * 100
    
    def get_transaction_utilization_percent(self):
        """Get percentage of monthly transaction limit used"""
        if not self.package or not self.package.max_transactions_per_month:
            return 0  # Unlimited
        return (self.current_month_transactions / self.package.max_transactions_per_month) * 100
    
    def add_volume_usage(self, amount):
        """Add to current month's volume usage"""
        if self.current_month_volume is None:
            self.current_month_volume = Decimal('0.00')
        self.current_month_volume += Decimal(str(amount))
        db.session.commit()
    
    def add_transaction_usage(self, count=1):
        """Add to current month's transaction usage"""
        if self.current_month_transactions is None:
            self.current_month_transactions = 0
        self.current_month_transactions += count
        db.session.commit()
    
    def reset_monthly_usage(self):
        """Reset monthly usage counters (called at start of each month)"""
        from datetime import datetime
        self.current_month_volume = Decimal('0.00')
        self.current_month_transactions = 0
        self.last_usage_reset = now_eest()
        db.session.commit()
    
    def get_margin_status(self):
        """Get current margin status for flat-rate clients"""
        if not self.package or self.package.client_type.value != 'flat_rate':
            return None
        
        if not self.package.monthly_price or not self.package.max_volume_per_month:
            return None
            
        current_margin = (float(self.package.monthly_price) / float(self.current_month_volume or 1)) * 100
        min_margin = float(self.package.min_margin_percent or 1.20)
        
        return {
            'current_margin': current_margin,
            'min_margin': min_margin,
            'is_acceptable': current_margin >= min_margin,
            'volume_used': float(self.current_month_volume or 0),
            'volume_limit': float(self.package.max_volume_per_month or 0)
        }

# Package synchronization event listener
@event.listens_for(Client.package_id, 'set')
def sync_status_on_package_change(target, value, oldvalue, initiator):
    """Automatically sync client status when package changes"""
    if value != oldvalue and hasattr(target, 'sync_status'):
        # Use the mixin method to sync status
        target.sync_status()
