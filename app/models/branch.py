from app.extensions import db
from app.models.base import BaseModel

class Branch(BaseModel):
    """Branch model for managing client branches/locations - Superadmin level"""
    __tablename__ = 'branches'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, default=True)

    # Superadmin user who manages this branch
    superadmin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    superadmin = db.relationship('User', back_populates='managed_branch', uselist=False, foreign_keys=[superadmin_id])

    # Relationships - this branch manages multiple clients and admins
    clients = db.relationship('Client', back_populates='branch', lazy='dynamic', cascade='all, delete-orphan')
    admins = db.relationship('User', back_populates='branch', lazy='dynamic', foreign_keys='User.branch_id')

    # Financial stats (aggregated from clients)
    total_clients = db.Column(db.Integer, default=0)
    total_transactions = db.Column(db.Integer, default=0)
    total_volume = db.Column(db.Numeric(20, 8), default=0)
    monthly_commission = db.Column(db.Numeric(20, 8), default=0)

    def __init__(self, **kwargs):
        super(Branch, self).__init__(**kwargs)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'postal_code': self.postal_code,
            'phone': self.phone,
            'email': self.email,
            'is_active': self.is_active,
            'superadmin_id': self.superadmin_id,
            'total_clients': self.total_clients,
            'total_transactions': self.total_transactions,
            'total_volume': float(self.total_volume) if self.total_volume else 0,
            'monthly_commission': float(self.monthly_commission) if self.monthly_commission else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def get_active_clients(self):
        """Get all active clients under this branch"""
        return self.clients.filter_by(is_active=True).all()

    def get_total_deposit_volume(self):
        """Calculate total deposit volume for all clients in this branch"""
        from app.models.payment import Payment
        from app.models.enums import PaymentStatus
        from sqlalchemy import func
        from app.models.client import Client

        result = db.session.query(func.sum(Payment.amount)).join(Client).filter(
            Client.branch_id == self.id,
            Payment.status == PaymentStatus.APPROVED
        ).scalar()

        return result or 0

    def get_total_withdrawal_volume(self):
        """Calculate total withdrawal volume for all clients in this branch"""
        from app.models.withdrawal import Withdrawal
        from app.models.enums import WithdrawalStatus
        from sqlalchemy import func
        from app.models.client import Client

        result = db.session.query(func.sum(Withdrawal.amount)).join(Client).filter(
            Client.branch_id == self.id,
            Withdrawal.status == WithdrawalStatus.APPROVED
        ).scalar()

        return result or 0

    def update_stats(self, commit: bool = True):
        """Update branch statistics using latest payment data."""
        from sqlalchemy import func

        from app.models.payment import Payment
        from app.models.enums import PaymentStatus
        from app.models.client import Client

        self.total_clients = self.clients.filter_by(is_active=True).count()

        payment_query = (
            Payment.query.join(Client, Payment.client_id == Client.id)
            .filter(
                Client.branch_id == self.id,
                Payment.status == PaymentStatus.APPROVED,
            )
        )

        self.total_transactions = payment_query.count()

        # Prefer fiat_amount when available, fallback to crypto amount
        total_fiat = (
            payment_query.with_entities(func.coalesce(func.sum(Payment.fiat_amount), 0)).scalar() or 0
        )
        if total_fiat:
            self.total_volume = total_fiat
        else:
            self.total_volume = (
                payment_query.with_entities(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0
            )

        if commit:
            db.session.commit()

    @classmethod
    def update_all_stats(cls, commit: bool = True):
        """Recalculate statistics for all branches."""
        for branch in cls.query.all():
            branch.update_stats(commit=False)

        if commit:
            db.session.commit()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'postal_code': self.postal_code,
            'phone': self.phone,
            'email': self.email,
            'is_active': self.is_active,
            'superadmin_id': self.superadmin_id,
            'total_clients': self.total_clients,
            'total_transactions': self.total_transactions,
            'total_volume': float(self.total_volume) if self.total_volume else 0,
            'monthly_commission': float(self.monthly_commission) if self.monthly_commission else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }