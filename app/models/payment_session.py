from datetime import datetime, timedelta, timezone
from ..utils.timezone import now_eest, utc_to_eest
from app.extensions import db
from .base import BaseModel

class PaymentSession(BaseModel):
    __tablename__ = 'payment_sessions'

    # Inherit integer primary key `id` from BaseModel; expose `public_id` for external use
    public_id = db.Column(db.String(32), unique=True, index=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    order_id = db.Column(db.String(64), nullable=False, index=True)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    currency = db.Column(db.String(5), nullable=False, default='USD')
    customer_email = db.Column(db.String(255), nullable=True)
    meta = db.Column(db.JSON, default=dict)

    status = db.Column(db.String(20), nullable=False, default='created')
    expires_at = db.Column(db.DateTime, nullable=False)

    success_url = db.Column(db.Text, nullable=False)
    cancel_url = db.Column(db.Text, nullable=False)
    webhook_url = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = db.relationship('Client', backref=db.backref('payment_sessions', lazy=True))
    events = db.relationship(
        'PaymentSessionEvent',
        backref='session',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='PaymentSessionEvent.created_at.desc()'
    )

    @classmethod
    def create_from_request(cls, data: dict, client_id: int):
        import uuid
        ps_id = 'ps_' + uuid.uuid4().hex[:12]
        expires = now_eest() + timedelta(minutes=30)
        obj = cls(
            public_id=ps_id,
            client_id=client_id,
            order_id=data['order_id'],
            amount=data['amount'],
            currency=(data.get('currency') or 'USD').upper(),
            customer_email=(data.get('customer') or {}).get('email'),
            meta=data.get('metadata') or {},
            status='created',
            expires_at=expires,
            success_url=data['success_url'],
            cancel_url=data['cancel_url'],
            webhook_url=data.get('webhook_url')
        )
        db.session.add(obj)
        db.session.commit()
        return obj

    def is_expired(self) -> bool:
        """Check if payment session has expired, handling both naive and aware datetimes"""
        now = now_eest()
        expires = self.expires_at
        
        # If expires_at is timezone-naive, assume it's UTC and convert to EEST
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc).astimezone(now.tzinfo)
        
        # If expires_at is None, consider it expired
        if expires is None:
            return True
            
        return now > expires


class PaymentSessionEvent(BaseModel):
    __tablename__ = 'payment_session_events'

    payment_session_id = db.Column(db.Integer, db.ForeignKey('payment_sessions.id'), nullable=False, index=True)
    event_type = db.Column(db.String(40), nullable=False)
    payload = db.Column(db.JSON, default=dict)
    response_status = db.Column(db.Integer, nullable=True)
    response_body = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def mark_delivered(self, status_code: int, body: str | None = None):
        self.response_status = status_code
        self.response_body = body
        self.error = None

    def mark_failed(self, status_code: int | None, error_message: str):
        self.response_status = status_code
        self.error = error_message
