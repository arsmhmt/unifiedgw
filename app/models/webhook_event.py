"""
WebhookEvent model for tracking webhook deliveries to clients.
"""
from datetime import datetime, timedelta
import uuid
from app.extensions.extensions import db
from .base import BaseModel
from app.payment.constants import WebhookEventType, WebhookEventStatus


class WebhookEvent(BaseModel):
    """
    Tracks webhook events sent to clients when payment status changes.
    Supports retry logic and delivery confirmation.
    """
    __tablename__ = 'webhook_events'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False, index=True)
    
    event_type = db.Column(db.String(50), nullable=False, index=True)  # e.g., 'payment.created'
    status = db.Column(db.String(20), nullable=False, default=WebhookEventStatus.PENDING.value, index=True)
    
    attempts = db.Column(db.Integer, default=0, nullable=False)
    max_attempts = db.Column(db.Integer, default=5, nullable=False)
    
    next_attempt_at = db.Column(db.DateTime, nullable=True, index=True)
    
    payload = db.Column(db.JSON, nullable=False)  # The webhook payload sent to client
    
    last_error = db.Column(db.Text, nullable=True)  # Last error message if delivery failed
    last_response_code = db.Column(db.Integer, nullable=True)  # HTTP response code from client
    
    delivered_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    client = db.relationship('Client', backref=db.backref('webhook_events', lazy='dynamic'))
    payment = db.relationship('Payment', backref=db.backref('webhook_events', lazy='dynamic'))
    
    def __repr__(self):
        return f"<WebhookEvent {self.id} | {self.event_type} | {self.status} | attempts={self.attempts}>"
    
    def is_deliverable(self):
        """Check if this event is ready to be delivered."""
        if self.status != WebhookEventStatus.PENDING.value:
            return False
        if self.attempts >= self.max_attempts:
            return False
        if self.next_attempt_at and self.next_attempt_at > datetime.utcnow():
            return False
        return True
    
    def calculate_next_attempt(self):
        """Calculate next attempt time using exponential backoff."""
        if self.attempts == 0:
            # First retry after 1 minute
            delay_minutes = 1
        elif self.attempts == 1:
            # Second retry after 5 minutes
            delay_minutes = 5
        elif self.attempts == 2:
            # Third retry after 15 minutes
            delay_minutes = 15
        elif self.attempts == 3:
            # Fourth retry after 1 hour
            delay_minutes = 60
        else:
            # Final retry after 4 hours
            delay_minutes = 240
        
        return datetime.utcnow() + timedelta(minutes=delay_minutes)
    
    def to_dict(self):
        """Convert event to dictionary for API responses."""
        return {
            'id': self.id,
            'client_id': self.client_id,
            'payment_id': self.payment_id,
            'event_type': self.event_type,
            'status': self.status,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'next_attempt_at': self.next_attempt_at.isoformat() if self.next_attempt_at else None,
            'last_error': self.last_error,
            'last_response_code': self.last_response_code,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
