from ..extensions import db
from datetime import datetime
from ..utils.timezone import now_eest
from enum import Enum

class AuditActionType(Enum):
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    STATUS_CHANGE = 'status_change'
    DOCUMENT_UPLOAD = 'document_upload'
    DOCUMENT_DELETE = 'document_delete'
    RECURRING_PAYMENT = 'recurring_payment'
    NOTIFICATION = 'notification'
    LOGIN = 'login'
    LOGOUT = 'logout'
    API_KEY_CREATED = 'api_key_created'
    API_KEY_UPDATED = 'api_key_updated'
    API_KEY_REVOKED = 'api_key_revoked'
    API_KEY_REGENERATED = 'api_key_regenerated'

class AuditTrail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action_type = db.Column(db.String(20), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    old_value = db.Column(db.JSON)
    new_value = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=now_eest)
    
    # Relationships
    user = db.relationship('User', back_populates='audit_trail')

    def __init__(self, user_id, action_type, entity_type, entity_id, 
                 old_value=None, new_value=None, ip_address=None, user_agent=None):
        self.user_id = user_id
        self.action_type = action_type
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.old_value = old_value
        self.new_value = new_value
        self.ip_address = ip_address
        self.user_agent = user_agent

    @classmethod
    def log_action(cls, user_id, action_type, entity_type, entity_id, 
                  old_value=None, new_value=None, request=None):
        """Log an audit action"""
        from flask import current_app
        
        try:
            # Ensure user_id is an integer and not None
            if user_id is None:
                current_app.logger.warning(f"Missing user_id in audit log: {action_type} {entity_type} {entity_id}")
                return None
                
            ip_address = request.remote_addr if request else None
            user_agent = request.headers.get('User-Agent') if request else None
            
            audit = cls(
                user_id=user_id,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=entity_id,
                old_value=old_value,
                new_value=new_value,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.session.add(audit)
            # Note: We don't commit here - the caller should commit the session
            return audit
        except Exception as e:
            current_app.logger.error(f"Error logging audit action: {str(e)}")
            return None

    @classmethod
    def get_audit_trail(cls, entity_type=None, entity_id=None, 
                       action_type=None, user_id=None, limit=100):
        """Get audit trail entries with filtering"""
        query = cls.query
        
        if entity_type:
            query = query.filter_by(entity_type=entity_type)
        if entity_id:
            query = query.filter_by(entity_id=entity_id)
        if action_type:
            query = query.filter_by(action_type=action_type)
        if user_id:
            query = query.filter_by(user_id=user_id)
            
        return query.order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def get_user_audit_trail(cls, user_id, limit=100):
        """Get audit trail for a specific user"""
        return cls.get_audit_trail(user_id=user_id, limit=limit)

    @classmethod
    def get_entity_audit_trail(cls, entity_type, entity_id, limit=100):
        """Get audit trail for a specific entity"""
        return cls.get_audit_trail(entity_type=entity_type, entity_id=entity_id, limit=limit)

    def format_action(self):
        """Format the action for display"""
        action = self.action_type.replace('_', ' ').title()
        entity = self.entity_type.replace('_', ' ').title()
        return f"{action} {entity}"

    def format_changes(self):
        """Format changes for display"""
        changes = []
        if self.old_value and self.new_value:
            for key in self.old_value.keys():
                if self.old_value[key] != self.new_value.get(key):
                    changes.append({
                        'field': key,
                        'old': self.old_value[key],
                        'new': self.new_value.get(key)
                    })
        return changes


class AuditLog(db.Model):
    """Branch-level audit log for tracking admin actions, client activity, and API calls"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Admin who performed action
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)  # Client affected (if applicable)
    action = db.Column(db.String(255), nullable=False)  # e.g., 'approve_deposit', 'create_client', 'api_call'
    details = db.Column(db.Text)  # JSON string with action details
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=now_eest, index=True)

    # Relationships
    branch = db.relationship('Branch', backref='audit_logs', lazy=True)
    admin = db.relationship('User', foreign_keys=[admin_id], backref='admin_audit_logs', lazy=True)
    client = db.relationship('Client', backref='audit_logs', lazy=True)

    def __init__(self, branch_id, action, details=None, admin_id=None, client_id=None,
                 ip_address=None, user_agent=None):
        self.branch_id = branch_id
        self.admin_id = admin_id
        self.client_id = client_id
        self.action = action
        self.details = details
        self.ip_address = ip_address
        self.user_agent = user_agent

    @classmethod
    def log_action(cls, branch_id, action, details=None, admin_id=None, client_id=None,
                  request=None):
        """Log a branch-level audit action"""
        ip_address = None
        user_agent = None

        if request:
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent')

        audit_log = cls(
            branch_id=branch_id,
            action=action,
            details=details,
            admin_id=admin_id,
            client_id=client_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        db.session.add(audit_log)
        db.session.commit()

        return audit_log

    def to_dict(self):
        """Convert audit log to dictionary"""
        return {
            'id': self.id,
            'branch_id': self.branch_id,
            'admin_id': self.admin_id,
            'client_id': self.client_id,
            'action': self.action,
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
