from ..extensions import db
from datetime import datetime
from enum import Enum
from ..utils.timezone import now_eest

class NotificationType(Enum):
    EMAIL = 'email'
    SMS = 'sms'
    PUSH = 'push'
    WEBHOOK = 'webhook'


class NotificationChannel(Enum):
    """Channels through which notifications can be sent."""
    EMAIL = 'email'  # Email notifications
    SMS = 'sms'  # Text message notifications
    IN_APP = 'in_app'  # In-app notifications
    PUSH = 'push'  # Push notifications (mobile/desktop)
    WEBHOOK = 'webhook'  # Webhook notifications for external services
    SLACK = 'slack'  # Slack notifications
    DISCORD = 'discord'  # Discord notifications
    TELEGRAM = 'telegram'  # Telegram notifications

class NotificationEvent(Enum):
    PAYMENT_RECEIVED = 'payment_received'
    PAYMENT_FAILED = 'payment_failed'
    PAYMENT_REFUNDED = 'payment_refunded'
    PAYMENT_OVERDUE = 'payment_overdue'
    RECURRING_PAYMENT = 'recurring_payment'
    SYSTEM_ALERT = 'system_alert'

class NotificationPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    notification_type = db.Column(db.String(20), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('notification_preferences', lazy=True))

    def __init__(self, user_id, notification_type, event_type, enabled=True):
        self.user_id = user_id
        self.notification_type = notification_type
        self.event_type = event_type
        self.enabled = enabled

    @classmethod
    def get_user_preferences(cls, user_id):
        """Get all notification preferences for a user"""
        return cls.query.filter_by(user_id=user_id).all()

    @classmethod
    def get_enabled_preferences(cls, user_id, event_type):
        """Get enabled notification preferences for a user and event type"""
        return cls.query.filter_by(
            user_id=user_id,
            event_type=event_type,
            enabled=True
        ).all()

    @classmethod
    def toggle_preference(cls, user_id, notification_type, event_type):
        """Toggle a notification preference"""
        preference = cls.query.filter_by(
            user_id=user_id,
            notification_type=notification_type,
            event_type=event_type
        ).first()
        
        if not preference:
            preference = cls(
                user_id=user_id,
                notification_type=notification_type,
                event_type=event_type,
                enabled=True
            )
            db.session.add(preference)
        else:
            preference.enabled = not preference.enabled
        
        db.session.commit()
        return preference

    @classmethod
    def bulk_update_preferences(cls, user_id, preferences):
        """Update multiple notification preferences at once"""
        # Delete existing preferences for this user
        cls.query.filter_by(user_id=user_id).delete()
        
        # Create new preferences
        new_preferences = []
        for pref in preferences:
            new_preferences.append(cls(
                user_id=user_id,
                notification_type=pref['type'],
                event_type=pref['event'],
                enabled=pref.get('enabled', True)
            ))
        
        db.session.add_all(new_preferences)
        db.session.commit()
        return new_preferences

    @classmethod
    def get_default_preferences(cls):
        """Get default notification preferences"""
        return [
            {'type': nt.value, 'event': et.value, 'enabled': True}
            for nt in NotificationType
            for et in NotificationEvent
        ]

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    message = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    client = db.relationship('Client', backref=db.backref('notifications', lazy=True))

    def __repr__(self):
        return f'<Notification {self.id} for client {self.client_id}>'


class AdminNotificationType(Enum):
    PAYMENT_REQUEST = 'payment_request'
    WITHDRAWAL_REQUEST = 'withdrawal_request'
    SYSTEM_ALERT = 'system_alert'
    CLIENT_REGISTRATION = 'client_registration'
    SECURITY_ALERT = 'security_alert'


class AdminNotification(db.Model):
    __tablename__ = 'admin_notifications'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'), nullable=True)  # None = all admins
    notification_type = db.Column(db.Enum(AdminNotificationType), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    related_id = db.Column(db.Integer, nullable=True)  # ID of related object (payment, withdrawal, etc.)
    related_model = db.Column(db.String(50), nullable=True)  # Model name (Payment, WithdrawalRequest, etc.)
    is_read = db.Column(db.Boolean, default=False)
    is_urgent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now_eest)
    read_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    admin = db.relationship('AdminUser', backref=db.backref('notifications', lazy=True))

    def __repr__(self):
        return f'<AdminNotification {self.id}: {self.notification_type.value} - {self.title}>'

    @classmethod
    def create_notification(cls, notification_type, title, message, admin_id=None,
                          related_id=None, related_model=None, is_urgent=False):
        """Create a new admin notification"""
        notification = cls(
            admin_id=admin_id,
            notification_type=notification_type,
            title=title,
            message=message,
            related_id=related_id,
            related_model=related_model,
            is_urgent=is_urgent
        )
        db.session.add(notification)
        db.session.commit()
        return notification

    @classmethod
    def get_unread_count(cls, admin_id=None):
        """Get count of unread notifications for an admin (or all if admin_id is None)"""
        query = cls.query.filter_by(is_read=False)
        if admin_id is not None:
            query = query.filter((cls.admin_id == admin_id) | (cls.admin_id.is_(None)))
        return query.count()

    @classmethod
    def get_recent_notifications(cls, admin_id=None, limit=10):
        """Get recent notifications for an admin"""
        query = cls.query
        if admin_id is not None:
            query = query.filter((cls.admin_id == admin_id) | (cls.admin_id.is_(None)))
        return query.order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def mark_as_read(cls, notification_id, admin_id=None):
        """Mark a notification as read"""
        notification = cls.query.get(notification_id)
        if notification and (admin_id is None or notification.admin_id == admin_id or notification.admin_id is None):
            notification.is_read = True
            notification.read_at = now_eest()
            db.session.commit()
            return True
        return False

    @classmethod
    def mark_all_as_read(cls, admin_id=None):
        """Mark all notifications as read for an admin"""
        query = cls.query.filter_by(is_read=False)
        if admin_id is not None:
            query = query.filter((cls.admin_id == admin_id) | (cls.admin_id.is_(None)))
        count = query.update({'is_read': True, 'read_at': now_eest()})
        db.session.commit()
        return count
