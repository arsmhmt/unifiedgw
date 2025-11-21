"""
Login History Model
Tracks user login attempts, successes, and failures for security auditing
"""

from datetime import datetime
from app.extensions import db
from app.models.base import BaseModel
from ..utils.timezone import now_eest

class LoginHistory(BaseModel):
    """Track all login attempts"""
    __tablename__ = 'login_history'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # User information
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username = db.Column(db.String(100), nullable=False)  # Store even if user not found
    user_type = db.Column(db.String(20), nullable=False)  # 'admin', 'client', 'owner'
    
    # Login details
    success = db.Column(db.Boolean, default=False, nullable=False)
    failure_reason = db.Column(db.String(255), nullable=True)  # 'invalid_password', 'user_not_found', 'account_locked'
    
    # Request details
    ip_address = db.Column(db.String(45), nullable=False)  # IPv6 support
    user_agent = db.Column(db.String(500), nullable=True)
    
    # Location data (optional, from IP geolocation)
    country = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    
    # Session info
    session_id = db.Column(db.String(100), nullable=True)
    
    # Timestamps
    login_at = db.Column(db.DateTime, default=now_eest, nullable=False, index=True)
    logout_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='login_history', lazy=True)
    
    def __repr__(self):
        return f'<LoginHistory {self.username} - {"Success" if self.success else "Failed"} at {self.login_at}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'user_type': self.user_type,
            'success': self.success,
            'failure_reason': self.failure_reason,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'country': self.country,
            'city': self.city,
            'session_id': self.session_id,
            'login_at': self.login_at.isoformat() if self.login_at else None,
            'logout_at': self.logout_at.isoformat() if self.logout_at else None,
            'duration': self.get_session_duration()
        }
    
    def get_session_duration(self):
        """Get session duration in minutes"""
        if not self.logout_at or not self.login_at:
            return None
        
        delta = self.logout_at - self.login_at
        return round(delta.total_seconds() / 60, 2)
    
    @classmethod
    def log_login_attempt(cls, username, user_type, success, user_id=None, 
                         failure_reason=None, ip_address=None, user_agent=None,
                         session_id=None):
        """Log a login attempt"""
        login_record = cls(
            user_id=user_id,
            username=username,
            user_type=user_type,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address or 'unknown',
            user_agent=user_agent,
            session_id=session_id,
            login_at=now_eest()
        )
        
        db.session.add(login_record)
        db.session.commit()
        
        return login_record
    
    @classmethod
    def log_logout(cls, user_id, session_id=None):
        """Log a logout event"""
        # Find the most recent login for this user
        login_record = cls.query.filter_by(
            user_id=user_id,
            success=True
        ).order_by(cls.login_at.desc()).first()
        
        if login_record and not login_record.logout_at:
            login_record.logout_at = now_eest()
            db.session.commit()
        
        return login_record
    
    @classmethod
    def get_failed_attempts(cls, username, minutes=30):
        """Get failed login attempts for a username in the last X minutes"""
        from datetime import timedelta
        
        cutoff_time = now_eest() - timedelta(minutes=minutes)
        
        return cls.query.filter(
            cls.username == username,
            cls.success == False,
            cls.login_at >= cutoff_time
        ).count()
    
    @classmethod
    def get_user_history(cls, user_id, limit=50):
        """Get login history for a specific user"""
        return cls.query.filter_by(user_id=user_id).order_by(
            cls.login_at.desc()
        ).limit(limit).all()
    
    @classmethod
    def get_recent_logins(cls, hours=24, limit=100):
        """Get recent login attempts"""
        from datetime import timedelta
        
        cutoff_time = now_eest() - timedelta(hours=hours)
        
        return cls.query.filter(
            cls.login_at >= cutoff_time
        ).order_by(cls.login_at.desc()).limit(limit).all()
    
    @classmethod
    def get_suspicious_activity(cls):
        """Get suspicious login activity (multiple failed attempts from same IP)"""
        from sqlalchemy import func
        
        # Find IPs with 5+ failed attempts in last hour
        from datetime import timedelta
        cutoff_time = now_eest() - timedelta(hours=1)
        
        suspicious = db.session.query(
            cls.ip_address,
            func.count(cls.id).label('attempts'),
            func.max(cls.login_at).label('last_attempt')
        ).filter(
            cls.success == False,
            cls.login_at >= cutoff_time
        ).group_by(cls.ip_address).having(
            func.count(cls.id) >= 5
        ).all()
        
        return suspicious

class LoginAttemptLimiter:
    """Rate limiter for login attempts"""
    
    @staticmethod
    def is_blocked(username, ip_address=None):
        """Check if username or IP is blocked due to too many failed attempts"""
        
        # Check username-based blocking (5 failures in 30 minutes)
        username_failures = LoginHistory.get_failed_attempts(username, minutes=30)
        if username_failures >= 5:
            return True, 'Too many failed login attempts. Please try again later.'
        
        # Check IP-based blocking (10 failures in 30 minutes)
        if ip_address:
            from datetime import timedelta
            cutoff_time = now_eest() - timedelta(minutes=30)
            
            ip_failures = LoginHistory.query.filter(
                LoginHistory.ip_address == ip_address,
                LoginHistory.success == False,
                LoginHistory.login_at >= cutoff_time
            ).count()
            
            if ip_failures >= 10:
                return True, 'Too many failed login attempts from this IP address.'
        
        return False, None
    
    @staticmethod
    def reset_attempts(username):
        """Reset failed attempts counter after successful login"""
        # This is handled automatically by the time-based filtering
        # But you could implement a manual reset if needed
        pass
