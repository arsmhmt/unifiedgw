from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from enum import Enum
from app.extensions.extensions import db

class SubscriptionStatus(str, Enum):
    """Subscription status options."""
    ACTIVE = 'active'
    CANCELED = 'canceled'
    EXPIRED = 'expired'
    TRIAL = 'trial'
    PAUSED = 'paused'

class Subscription(db.Model):
    """User subscription to a pricing plan."""
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pricing_plan_id = db.Column(db.Integer, db.ForeignKey('pricing_plans.id'), nullable=False)
    status = db.Column(db.Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    end_date = db.Column(db.DateTime, nullable=True)
    is_recurring = db.Column(db.Boolean, default=True, nullable=False)
    auto_renew = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='subscriptions')
    pricing_plan = db.relationship('PricingPlan', back_populates='subscriptions')
    
    def __repr__(self):
        return f'<Subscription {self.id} - User {self.user_id} - Plan {self.pricing_plan_id}>'
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'pricing_plan_id': self.pricing_plan_id,
            'status': self.status.value,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_recurring': self.is_recurring,
            'auto_renew': self.auto_renew,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_active(self):
        """Check if the subscription is currently active."""
        now = now_eest()
        return (
            self.status == SubscriptionStatus.ACTIVE and 
            (self.end_date is None or self.end_date > now)
        )
    
    def renew(self, period_days=30):
        """Renew the subscription for the given period."""
        now = now_eest()
        if self.end_date and self.end_date > now:
            self.end_date += timedelta(days=period_days)
        else:
            self.start_date = now
            self.end_date = now + timedelta(days=period_days)
        self.status = SubscriptionStatus.ACTIVE
        return self
