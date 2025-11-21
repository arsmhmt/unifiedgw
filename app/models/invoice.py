from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from decimal import Decimal
from app.extensions import db
from .base import BaseModel

class InvoiceStatus(db.Enum('draft','pending','paid','confirmed','underpaid','overpaid','expired','cancelled', name='invoice_status')):
    pass

class Invoice(BaseModel):
    __tablename__ = 'invoices'

    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    payment_session_id = db.Column(db.Integer, db.ForeignKey('payment_sessions.id'), nullable=True, index=True)

    # Merchant order info
    external_order_id = db.Column(db.String(64), nullable=True, index=True)
    customer_email = db.Column(db.String(255), nullable=True)
    metadata = db.Column(db.JSON, default=dict)

    # Amounts & pricing
    fiat_amount = db.Column(db.Numeric(18, 2), nullable=False)
    fiat_currency = db.Column(db.String(5), nullable=False, default='USD')
    crypto_currency = db.Column(db.String(10), nullable=False, default='USDT')
    crypto_amount = db.Column(db.Numeric(18, 8), nullable=True)

    exchange_rate = db.Column(db.Numeric(18, 8), nullable=True)   # fiat -> crypto at creation
    rate_locked_at = db.Column(db.DateTime, nullable=True)
    rate_expires_at = db.Column(db.DateTime, nullable=True)

    # Fees & settlement
    fee_amount = db.Column(db.Numeric(18, 2), nullable=True)
    net_amount = db.Column(db.Numeric(18, 2), nullable=True)

    # Checkout & lifecycle
    status = db.Column(db.String(20), nullable=False, default='pending')
    deposit_address = db.Column(db.String(128), nullable=True)
    network = db.Column(db.String(20), nullable=True)

    success_url = db.Column(db.Text, nullable=True)
    cancel_url = db.Column(db.Text, nullable=True)
    webhook_url = db.Column(db.Text, nullable=True)

    # Relationships
    client = db.relationship('Client', backref=db.backref('invoices', lazy=True))
    payment_session = db.relationship('PaymentSession', backref=db.backref('invoice', uselist=False))

    def lock_rate(self, rate: Decimal, ttl_minutes: int = 15):
        self.exchange_rate = rate
        self.rate_locked_at = now_eest()
        self.rate_expires_at = self.rate_locked_at + timedelta(minutes=ttl_minutes)

    def is_rate_expired(self) -> bool:
        if not self.rate_expires_at:
            return True
        return now_eest() > self.rate_expires_at