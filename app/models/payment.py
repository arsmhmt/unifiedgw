from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from decimal import Decimal
from app.extensions.extensions import db 
from .base import BaseModel
from .enums import PaymentStatus
from sqlalchemy.orm import relationship
from sqlalchemy import event
from app.utils.exchange import get_exchange_rate as fetch_exchange_rate

class Payment(BaseModel):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    platform_id = db.Column(db.Integer, db.ForeignKey('platforms.id'), nullable=True, index=True)
    
    # Legacy fields (kept for backward compatibility)
    amount = db.Column(db.Numeric(18, 8), nullable=True)  # Now represents crypto amount
    currency = db.Column(db.String(10), nullable=True)     # Now represents crypto currency
    
    # New fiat fields
    fiat_amount = db.Column(db.Numeric(18, 2), nullable=True)      # Amount in fiat (e.g., 500.00)
    fiat_currency = db.Column(db.String(5), nullable=True)         # Fiat currency code (e.g., 'TRY', 'USD')
    
    # New crypto fields
    crypto_amount = db.Column(db.Numeric(18, 8), nullable=True)    # Calculated crypto amount
    crypto_currency = db.Column(db.String(5), default='BTC')       # Default to BTC
    
    # Exchange information
    exchange_rate = db.Column(db.Numeric(18, 8), nullable=True)    # Rate at time of creation
    rate_expiry = db.Column(db.DateTime, nullable=True)            # When the rate expires
    
    # Payment details
    _status = db.Column('status', db.Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    
    @property
    def status(self):
        return self._status
        
    @status.setter
    def status(self, value):
        if isinstance(value, str):
            # Handle string input by converting to enum, case-insensitive
            self._status = PaymentStatus(value.lower())
        else:
            self._status = value
            
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.String(255), unique=True)
    description = db.Column(db.String(255))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # When the payment expires

    # Foreign Key for the relationship to RecurringPayment
    recurring_payment_id = db.Column(db.Integer, db.ForeignKey('recurring_payments.id'), nullable=True)

    # Relationships
    client = db.relationship('Client', back_populates='payments')
    platform = db.relationship('Platform', back_populates='payments')
    documents = db.relationship('Document', back_populates='payment', lazy=True) 
    
    # For backward compatibility
    @property
    def display_amount(self):
        """Return the amount in the appropriate currency for display"""
        if self.fiat_amount is not None and self.fiat_currency:
            return f"{self.fiat_amount:.2f} {self.fiat_currency}"
        return f"{self.amount or 0} {self.currency or 'BTC'}"
    
    @property
    def display_crypto_amount(self):
        """Return the crypto amount for display"""
        amount = self.crypto_amount or self.amount
        currency = self.crypto_currency or self.currency or 'BTC'
        return f"{amount:.8f} {currency}"
    
    def update_exchange_rate(self, force_refresh=False):
        """Update the exchange rate for this payment"""
        if not self.fiat_currency or not self.fiat_amount:
            return None
            
        # Check if we have a valid rate that hasn't expired
        if not force_refresh and self.exchange_rate and self.rate_expiry and self.rate_expiry > now_eest():
            return self.exchange_rate
            
        # Get new rate
        rate = fetch_exchange_rate(self.fiat_currency, self.crypto_currency or 'BTC')
        if not rate:
            return None
            
        # Update rate and expiry (15 minutes from now)
        self.exchange_rate = rate
        self.rate_expiry = now_eest() + timedelta(minutes=15)
        
        # Calculate crypto amount if we have fiat amount
        if self.fiat_amount:
            self.crypto_amount = Decimal(str(self.fiat_amount)) / Decimal(str(rate))
            
        return rate
    
    def calculate_crypto_amount(self, fiat_amount=None, currency=None):
        """Calculate the crypto amount for a given fiat amount"""
        if fiat_amount is not None:
            self.fiat_amount = Decimal(str(fiat_amount))
        if currency:
            self.fiat_currency = currency.upper()
            
        if not self.fiat_amount or not self.fiat_currency:
            return None
            
        rate = self.update_exchange_rate()
        if not rate:
            return None
            
        self.crypto_amount = Decimal(str(self.fiat_amount)) / Decimal(str(rate))
        return self.crypto_amount
    
    def is_rate_expired(self):
        """Check if the exchange rate has expired"""
        if not self.rate_expiry:
            return True
        return now_eest() > self.rate_expiry
    
    def time_until_expiry(self):
        """Return seconds until rate expiry"""
        if not self.rate_expiry:
            return 0
        return max(0, (self.rate_expiry - now_eest()).total_seconds())

    def __repr__(self):
        if self.fiat_amount and self.fiat_currency:
            return f"<Payment {self.id} | {self.fiat_amount} {self.fiat_currency} → {self.crypto_amount:.8f} {self.crypto_currency} | {self.status.value}>"
        return f"<Payment {self.id} | {self.amount} {self.currency} | {self.status.value}>"


@event.listens_for(Payment, 'after_update')
def payment_status_changed(mapper, connection, target):
    """
    SQLAlchemy event listener to emit webhook events when payment status changes.
    """
    from sqlalchemy import inspect
    from app.payment.constants import WebhookEventType
    
    # Check if status was changed
    state = inspect(target)
    history = state.get_history('_status', passive=True)
    
    if not history.has_changes():
        return
    
    # Map status to webhook event type
    status_to_event = {
        PaymentStatus.PENDING: WebhookEventType.PAYMENT_PENDING,
        PaymentStatus.APPROVED: WebhookEventType.PAYMENT_APPROVED,
        PaymentStatus.COMPLETED: WebhookEventType.PAYMENT_COMPLETED,
        PaymentStatus.FAILED: WebhookEventType.PAYMENT_FAILED,
        PaymentStatus.REJECTED: WebhookEventType.PAYMENT_REJECTED,
        PaymentStatus.CANCELLED: WebhookEventType.PAYMENT_CANCELLED,
    }
    
    new_status = target._status
    event_type = status_to_event.get(new_status)
    
    if event_type:
        # Import here to avoid circular imports
        from app.events.service import create_event
        try:
            # Use db.session.flush() to ensure the payment is persisted before creating event
            db.session.flush()
            create_event(target, event_type)
        except Exception as e:
            # Log error but don't fail the payment update
            import logging
            logging.error(f"Failed to create webhook event for payment {target.id}: {e}")
