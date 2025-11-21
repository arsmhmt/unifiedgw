from ..utils.timezone import now_eest
from ..extensions import db  # Changed from 'from app import db'
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.orm import relationship # Ensure relationship is imported if not already

class RecurringFrequency(Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    BIWEEKLY = 'biweekly'
    MONTHLY = 'monthly'
    QUARTERLY = 'quarterly'
    YEARLY = 'yearly'

class RecurringPayment(db.Model):
    __tablename__ = 'recurring_payments'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    frequency = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)
    next_payment_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, paused, cancelled
    description = db.Column(db.String(255))
    payment_method = db.Column(db.String(50))
    payment_provider = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = db.relationship('Client', back_populates='recurring_payments') # This one is fine



    def __init__(self, client_id, amount, currency, frequency, start_date, end_date=None, 
                 description=None, payment_method=None, payment_provider=None):
        self.client_id = client_id
        self.amount = amount
        self.currency = currency
        self.frequency = frequency
        self.start_date = start_date
        self.end_date = end_date
        self.description = description
        self.payment_method = payment_method
        self.payment_provider = payment_provider
        self.next_payment_date = self.calculate_next_payment_date(start_date)

    def calculate_next_payment_date(self, current_date=None):
        """Calculate the next payment date based on frequency"""
        if not current_date:
            current_date = now_eest()
            
        if self.frequency == RecurringFrequency.DAILY.value:
            return current_date + timedelta(days=1)
        elif self.frequency == RecurringFrequency.WEEKLY.value:
            return current_date + timedelta(weeks=1)
        elif self.frequency == RecurringFrequency.BIWEEKLY.value:
            return current_date + timedelta(weeks=2)
        elif self.frequency == RecurringFrequency.MONTHLY.value:
            return current_date + timedelta(days=30)
        elif self.frequency == RecurringFrequency.QUARTERLY.value:
            return current_date + timedelta(days=90)
        elif self.frequency == RecurringFrequency.YEARLY.value:
            return current_date + timedelta(days=365)
        return None

    def create_next_payment(self):
        """Create a new payment instance based on the recurring schedule"""
        from .payment import Payment  # <-- Local import to prevent circular dependency

        if self.status != 'active':
            return None
            
        if self.end_date and self.next_payment_date > self.end_date:
            return None
            
        payment = Payment(
            client_id=self.client_id,
            amount=self.amount,
            currency=self.currency,
            payment_method=self.payment_method,
            payment_provider=self.payment_provider,
            description=f"Recurring payment: {self.description or 'Regular payment'}"
        )
        
        db.session.add(payment)
        db.session.commit()
        
        # Update next payment date
        self.next_payment_date = self.calculate_next_payment_date(self.next_payment_date)
        db.session.commit()
        
        return payment

    def pause(self):
        """Pause the recurring payment"""
        self.status = 'paused'
        db.session.commit()

    def resume(self):
        """Resume the recurring payment"""
        self.status = 'active'
        db.session.commit()

    def cancel(self):
        """Cancel the recurring payment"""
        self.status = 'cancelled'
        db.session.commit()

