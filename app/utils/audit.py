"""
Audit logging utilities for the CPGateway application.
"""

from flask import request
from flask_login import current_user
from app.models.audit import AuditTrail
from ..utils.timezone import now_eest
from app.extensions import db
from app.models.user import User
from app.models.admin import AdminUser
import logging
import json
from datetime import datetime
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)


def log_audit(action, model, model_id, description, old_values=None, new_values=None):
    """
    Helper function to log audit trail for admin actions.
    
    Args:
        action (str): The action performed (e.g., 'create', 'update', 'delete')
        model (str): The model name being operated on
        model_id (int): The ID of the model instance
        description (str): Description of the action
        old_values (dict, optional): Previous values before change
        new_values (dict, optional): New values after change
        
    Returns:
        bool: True if audit log was created successfully, False otherwise
    """
    from flask import current_app
    
    try:
        user_id = None
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            user_id = current_user.id
            
        # Log the action
        audit = AuditTrail.log_action(
            user_id=user_id,
            action_type=action,
            entity_type=model,
            entity_id=model_id,
            old_value=old_values,
            new_value=new_values,
            request=request
        )
        
        if audit:
            logger.info(f"Audit log created: {action} on {model}({model_id}) by user {user_id}")
        else:
            logger.warning(f"Failed to create audit log for {action} on {model}({model_id})")
            
        return audit is not None
        
    except Exception as e:
        logger.error(f"Error creating audit log: {str(e)}", exc_info=True)
        # Don't raise the exception, just log it and continue
        return False


def log_security_event(event_type: str, details: Dict[str, Any], user_id: Optional[int] = None, 
                      severity: str = 'medium', ip_address: Optional[str] = None):
    """
    Log security-related events for monitoring and analysis
    
    Args:
        event_type: Type of security event
        details: Event details dictionary
        user_id: User ID if applicable
        severity: Event severity (low, medium, high, critical)
        ip_address: IP address if different from request
    """
    try:
        # Get current user if not provided
        if user_id is None and hasattr(current_user, 'id'):
            user_id = current_user.id
        
        # Get IP address
        if ip_address is None and request:
            ip_address = request.remote_addr
        
        # Enhanced details
        enhanced_details = {
            'event_type': event_type,
            'severity': severity,
            'timestamp': now_eest().isoformat(),
            'ip_address': ip_address,
            'user_agent': request.headers.get('User-Agent') if request else None,
            'endpoint': request.endpoint if request else None,
            'method': request.method if request else None,
            **details
        }
        
        # Log to AuditTrail with security event type
        audit = AuditTrail.log_action(
            user_id=user_id,
            action_type=f'security_{event_type}',
            entity_type='security_event',
            entity_id=0,  # No specific entity
            old_value=None,
            new_value=enhanced_details,
            request=request
        )
        
        db.session.commit()
        
        # Also log to application logger based on severity
        log_level = {
            'low': logging.INFO,
            'medium': logging.WARNING,
            'high': logging.ERROR,
            'critical': logging.CRITICAL
        }.get(severity, logging.WARNING)
        
        logger.log(log_level, f"Security event [{severity.upper()}]: {event_type} - {details}")
        
    except Exception as e:
        logger.error(f"Failed to log security event: {e}")
        db.session.rollback()


def log_admin_action(action: str, target_type: str, target_id: int, description: str, 
                    old_values: Optional[Dict] = None, new_values: Optional[Dict] = None,
                    admin_user: Optional[AdminUser] = None):
    """
    Log administrative actions with enhanced context
    
    Args:
        action: Action performed (approve, reject, create, update, delete)
        target_type: Type of target (withdrawal, client, user, etc.)
        target_id: ID of the target
        description: Human-readable description
        old_values: Previous values
        new_values: New values
        admin_user: Admin user performing action
    """
    try:
        admin_id = admin_user.id if admin_user else (current_user.id if hasattr(current_user, 'id') else None)
        
        # Enhanced action details
        action_details = {
            'admin_id': admin_id,
            'admin_username': admin_user.username if admin_user else (current_user.username if hasattr(current_user, 'username') else None),
            'action': action,
            'target_type': target_type,
            'target_id': target_id,
            'description': description,
            'timestamp': now_eest().isoformat(),
            'ip_address': request.remote_addr if request else None,
            'user_agent': request.headers.get('User-Agent') if request else None
        }
        
        if old_values:
            action_details['old_values'] = old_values
        if new_values:
            action_details['new_values'] = new_values
        
        # Log to audit trail
        audit = AuditTrail.log_action(
            user_id=admin_id,
            action_type=f'admin_{action}',
            entity_type=target_type,
            entity_id=target_id,
            old_value=old_values,
            new_value=new_values,
            request=request
        )
        
        db.session.commit()
        
        logger.info(f"Admin action logged: {action} on {target_type}({target_id}) by admin {admin_id}")
        
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")
        db.session.rollback()


def log_api_usage(api_key: str, endpoint: str, method: str, response_code: int, 
                 response_time: float, error_message: Optional[str] = None):
    """
    Log API usage for monitoring and rate limiting
    
    Args:
        api_key: API key used (will be hashed for privacy)
        endpoint: API endpoint accessed
        method: HTTP method
        response_code: HTTP response code
        response_time: Response time in milliseconds
        error_message: Error message if applicable
    """
    try:
        import hashlib
        
        # Hash API key for privacy
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        
        usage_details = {
            'api_key_hash': api_key_hash,
            'endpoint': endpoint,
            'method': method,
            'response_code': response_code,
            'response_time_ms': response_time,
            'timestamp': now_eest().isoformat(),
            'ip_address': request.remote_addr if request else None,
            'user_agent': request.headers.get('User-Agent') if request else None
        }
        
        if error_message:
            usage_details['error_message'] = error_message
        
        # Log to audit trail
        audit = AuditTrail.log_action(
            user_id=None,  # API usage is not tied to a specific user
            action_type='api_usage',
            entity_type='api_endpoint',
            entity_id=0,
            old_value=None,
            new_value=usage_details,
            request=request
        )
        
        db.session.commit()
        
        # Log anomalies
        if response_code >= 400:
            logger.warning(f"API error: {response_code} for {endpoint} with key {api_key_hash}")
        elif response_time > 5000:  # > 5 seconds
            logger.warning(f"Slow API response: {response_time}ms for {endpoint}")
        
    except Exception as e:
        logger.error(f"Failed to log API usage: {e}")
        db.session.rollback()


def log_client_setting_change(client_id: int, setting: str, old_value: Any, new_value: Any, 
                             admin_user: Optional[AdminUser] = None):
    """
    Log changes to client settings
    
    Args:
        client_id: Client ID
        setting: Setting name that changed
        old_value: Previous value
        new_value: New value
        admin_user: Admin user making the change
    """
    log_admin_action(
        action='setting_change',
        target_type='client',
        target_id=client_id,
        description=f"Changed {setting} from '{old_value}' to '{new_value}'",
        old_values={setting: old_value},
        new_values={setting: new_value},
        admin_user=admin_user
    )


def log_transaction_decision(transaction_id: int, decision: str, reason: str, 
                           admin_user: Optional[AdminUser] = None):
    """
    Log admin decisions on transactions (approve/deny)
    
    Args:
        transaction_id: Transaction ID
        decision: 'approve' or 'deny'
        reason: Reason for the decision
        admin_user: Admin user making the decision
    """
    log_admin_action(
        action=f'transaction_{decision}',
        target_type='withdrawal',
        target_id=transaction_id,
        description=f"Transaction {decision}d: {reason}",
        new_values={'decision': decision, 'reason': reason},
        admin_user=admin_user
    )


def get_security_events(hours: int = 24, severity: Optional[str] = None, 
                       event_type: Optional[str] = None) -> List[AuditTrail]:
    """
    Retrieve security events from audit log
    
    Args:
        hours: Number of hours to look back
        severity: Filter by severity level
        event_type: Filter by event type
        
    Returns:
        List of AuditTrail records
    """
    try:
        from datetime import timedelta
        
        since = now_eest() - timedelta(hours=hours)
        
        query = AuditTrail.query.filter(
            AuditTrail.action_type.like('security_%'),
            AuditTrail.created_at >= since
        )
        
        if severity:
            # Filter by severity in new_value JSON
            query = query.filter(AuditTrail.new_value.contains(f'"severity": "{severity}"'))
        
        if event_type:
            query = query.filter(AuditTrail.action_type == f'security_{event_type}')
        
        return query.order_by(AuditTrail.created_at.desc()).all()
        
    except Exception as e:
        logger.error(f"Failed to retrieve security events: {e}")
        return []


def get_admin_activity(admin_id: Optional[int] = None, hours: int = 24) -> List[AuditTrail]:
    """
    Retrieve admin activity from audit log
    
    Args:
        admin_id: Specific admin ID (None for all admins)
        hours: Number of hours to look back
        
    Returns:
        List of AuditTrail records
    """
    try:
        from datetime import timedelta
        
        since = now_eest() - timedelta(hours=hours)
        
        query = AuditTrail.query.filter(
            AuditTrail.action_type.like('admin_%'),
            AuditTrail.created_at >= since
        )
        
        if admin_id:
            query = query.filter(AuditTrail.user_id == admin_id)
        
        return query.order_by(AuditTrail.created_at.desc()).all()
        
    except Exception as e:
        logger.error(f"Failed to retrieve admin activity: {e}")
        return []
