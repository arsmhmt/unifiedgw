from werkzeug.security import check_password_hash

def check_password(password_hash, password):
    """Verify a password against its hash."""
    return check_password_hash(password_hash, password)
"""
Security utilities for CPGateway - Rate limiting, fraud detection, and protection
"""

import time
try:
    import redis  # optional dependency; migrations/tests can run without it
except Exception:  # pragma: no cover
    redis = None
import hmac
import hashlib
import json
from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from flask import request, current_app, g, jsonify
from functools import wraps
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Redis connection for rate limiting (fallback to in-memory if Redis unavailable)
try:
    if redis is not None:
        redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        # Only ping if we successfully created the client
        redis_client.ping()
        REDIS_AVAILABLE = True
    else:
        raise RuntimeError("redis not installed")
except Exception as e:
    REDIS_AVAILABLE = False
    # Fallback to in-memory storage
    _memory_store = {}

class RateLimiter:
    """Rate limiting implementation with Redis backend and memory fallback"""
    
    def __init__(self):
        self.redis = redis_client if REDIS_AVAILABLE else None
    
    def _get_key(self, identifier: str, endpoint: str) -> str:
        """Generate rate limiting key"""
        return f"rate_limit:{identifier}:{endpoint}"
    
    def _get_client_identifier(self) -> str:
        """Get client identifier for rate limiting"""
        # Try to get client ID from session/auth
        if hasattr(g, 'current_user') and g.current_user:
            return f"user:{g.current_user.id}"
        
        # Fall back to IP address
        return f"ip:{request.remote_addr}"
    
    def is_allowed(self, endpoint: str, limit: int, window: int = 3600) -> Tuple[bool, Dict]:
        """
        Check if request is allowed under rate limit
        
        Args:
            endpoint: API endpoint name
            limit: Max requests allowed
            window: Time window in seconds (default 1 hour)
            
        Returns:
            (allowed, info_dict)
        """
        identifier = self._get_client_identifier()
        key = self._get_key(identifier, endpoint)
        current_time = int(time.time())
        window_start = current_time - window
        
        if self.redis:
            # Redis implementation
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)  # Remove old entries
            pipe.zcard(key)  # Count current requests
            pipe.zadd(key, {current_time: current_time})  # Add current request
            pipe.expire(key, window)  # Set expiry
            results = pipe.execute()
            
            current_count = results[1] + 1  # +1 for current request
        else:
            # Memory fallback
            if key not in _memory_store:
                _memory_store[key] = []
            
            # Clean old entries
            _memory_store[key] = [t for t in _memory_store[key] if t > window_start]
            _memory_store[key].append(current_time)
            current_count = len(_memory_store[key])
        
        allowed = current_count <= limit
        
        info = {
            'allowed': allowed,
            'current_count': current_count,
            'limit': limit,
            'window': window,
            'reset_time': current_time + window if not allowed else None,
            'identifier': identifier
        }
        
        # Log rate limit violations
        if not allowed:
            logger.warning(f"Rate limit exceeded for {identifier} on {endpoint}: {current_count}/{limit}")
        
        return allowed, info

# Global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(endpoint: str, limit: int, window: int = 3600):
    """
    Decorator for rate limiting endpoints
    
    Usage:
        @rate_limit('withdrawal_create', limit=10, window=3600)  # 10 per hour
        def create_withdrawal():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            allowed, info = rate_limiter.is_allowed(endpoint, limit, window)
            
            if not allowed:
                from flask import jsonify
                
                # Log the violation
                from app.utils.audit import log_security_event
                log_security_event(
                    event_type='rate_limit_exceeded',
                    details={
                        'endpoint': endpoint,
                        'identifier': info['identifier'],
                        'count': info['current_count'],
                        'limit': limit,
                        'window': window
                    },
                    severity='warning'
                )
                
                response = jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests. Limit: {limit} per {window} seconds',
                    'retry_after': info['reset_time'] - int(time.time()) if info['reset_time'] else window
                })
                response.status_code = 429
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(max(0, limit - info['current_count']))
                response.headers['X-RateLimit-Reset'] = str(info['reset_time'] or int(time.time()) + window)
                return response
            
            # Add rate limit headers to successful responses
            response = f(*args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(max(0, limit - info['current_count']))
                response.headers['X-RateLimit-Reset'] = str(int(time.time()) + window)
            
            return response
        return decorated_function
    return decorator

def abuse_protection(endpoint: str, threshold: int, window: int = 3600):
    """
    Decorator for abuse protection with IP blocking
    
    Usage:
        @abuse_protection('login_attempts', threshold=10, window=3600)
        def login():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            identifier = f"ip:{request.remote_addr}"
            key = f"abuse:{identifier}:{endpoint}"
            current_time = int(time.time())
            window_start = current_time - window
            
            # Check current abuse count
            if REDIS_AVAILABLE:
                pipe = redis_client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zcard(key)
                pipe.zadd(key, {current_time: current_time})
                pipe.expire(key, window)
                results = pipe.execute()
                count = results[1] + 1
            else:
                # Memory fallback
                if key not in _memory_store:
                    _memory_store[key] = []
                _memory_store[key] = [t for t in _memory_store[key] if t > window_start]
                _memory_store[key].append(current_time)
                count = len(_memory_store[key])
            
            # Check if threshold exceeded
            if count > threshold:
                # Log security event
                from app.utils.audit import log_security_event
                log_security_event(
                    event_type='abuse_protection_triggered',
                    details={
                        'endpoint': endpoint,
                        'ip_address': request.remote_addr,
                        'count': count,
                        'threshold': threshold,
                        'window': window
                    },
                    severity='high'
                )
                
                logger.warning(f"Abuse protection triggered for {request.remote_addr} on {endpoint}: {count}/{threshold}")
                
                # Add to blocklist with appropriate expiration
                block_key = f"blocklist:ip:{request.remote_addr}"
                block_expiry = window * 2  # Block for twice the window period
                
                if REDIS_AVAILABLE:
                    redis_client.setex(block_key, block_expiry, 1)
                else:
                    _memory_store[block_key] = current_time + block_expiry
                
                response = jsonify({
                    'error': 'Too many requests',
                    'message': f'IP temporarily blocked due to excessive requests. Try again later.',
                    'blocked_until': current_time + block_expiry
                })
                response.status_code = 429
                return response
            
            # Check if IP is in blocklist
            block_key = f"blocklist:ip:{request.remote_addr}"
            is_blocked = False
            
            if REDIS_AVAILABLE:
                is_blocked = redis_client.exists(block_key)
            else:
                is_blocked = block_key in _memory_store and _memory_store[block_key] > current_time
            
            if is_blocked:
                # Return blocked response
                block_expiry = 0
                if REDIS_AVAILABLE:
                    block_expiry = redis_client.ttl(block_key)
                else:
                    block_expiry = _memory_store[block_key] - current_time
                
                response = jsonify({
                    'error': 'Access denied',
                    'message': 'Your IP address is temporarily blocked due to suspicious activity',
                    'retry_after': max(1, block_expiry)
                })
                response.status_code = 403
                return response
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

class AbuseProtection:
    """Advanced abuse protection and anomaly detection"""
    
    @staticmethod
    def detect_suspicious_activity(user_id: int, activity_type: str, threshold: int = 5, window: int = 300) -> bool:
        """
        Detect suspicious activity patterns
        
        Args:
            user_id: User ID
            activity_type: Type of activity (login_failed, withdrawal_attempt, etc.)
            threshold: Max allowed activities
            window: Time window in seconds
        """
        key = f"abuse:{user_id}:{activity_type}"
        current_time = int(time.time())
        window_start = current_time - window
        
        if REDIS_AVAILABLE:
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {current_time: current_time})
            pipe.expire(key, window)
            results = pipe.execute()
            count = results[1] + 1
        else:
            # Memory fallback
            if key not in _memory_store:
                _memory_store[key] = []
            _memory_store[key] = [t for t in _memory_store[key] if t > window_start]
            _memory_store[key].append(current_time)
            count = len(_memory_store[key])
        
        is_suspicious = count > threshold
        
        if is_suspicious:
            logger.warning(f"Suspicious activity detected: {activity_type} for user {user_id}, count: {count}")
            
            # Log security event
            from app.utils.audit import log_security_event
            log_security_event(
                event_type='suspicious_activity',
                user_id=user_id,
                details={
                    'activity_type': activity_type,
                    'count': count,
                    'threshold': threshold,
                    'window': window
                },
                severity='high'
            )
        
        return is_suspicious
    
    @staticmethod
    def check_withdrawal_patterns(client_id: int, amount: float) -> Dict:
        """
        Analyze withdrawal patterns for fraud detection
        
        Returns fraud risk assessment
        """
        from app.models.withdrawal import WithdrawalRequest
        from app.models.client import Client
        from sqlalchemy import func
        
        # Get recent withdrawal history
        recent_withdrawals = WithdrawalRequest.query.filter(
            WithdrawalRequest.client_id == client_id,
            WithdrawalRequest.created_at >= now_eest() - timedelta(days=7)
        ).all()
        
        # Get client info
        client = Client.query.get(client_id)
        
        risk_factors = []
        risk_score = 0
        
        # Check for unusual amount
        if recent_withdrawals:
            avg_amount = sum(w.amount for w in recent_withdrawals) / len(recent_withdrawals)
            if amount > avg_amount * 3:
                risk_factors.append("amount_significantly_higher_than_average")
                risk_score += 30
        
        # Check for high frequency
        today_withdrawals = [w for w in recent_withdrawals 
                           if w.created_at.date() == now_eest().date()]
        if len(today_withdrawals) > 5:
            risk_factors.append("high_frequency_withdrawals")
            risk_score += 40
        
        # Check for no recent deposits (would need deposit tracking)
        # This is a placeholder for future implementation
        # if not has_recent_deposits(client_id):
        #     risk_factors.append("no_recent_deposits")
        #     risk_score += 25
        
        # Check client verification status
        if not client or not client.is_verified:
            risk_factors.append("unverified_client")
            risk_score += 50
        
        # Check for round numbers (often suspicious)
        if amount % 100 == 0 and amount >= 1000:
            risk_factors.append("round_number_large_amount")
            risk_score += 15
        
        risk_level = "low"
        if risk_score >= 70:
            risk_level = "high"
        elif risk_score >= 40:
            risk_level = "medium"
        
        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'requires_manual_review': risk_score >= 40
        }
    
    def track_failed_attempt(self, ip_address: str, attempt_type: str = 'login') -> None:
        """Track a failed attempt for rate limiting and abuse detection"""
        try:
            key = f"failed_attempts:{ip_address}:{attempt_type}"
            current_time = int(time.time())
            
            if REDIS_AVAILABLE:
                pipe = redis_client.pipeline()
                pipe.zadd(key, {current_time: current_time})
                pipe.expire(key, 3600)  # Expire after 1 hour
                pipe.execute()
            else:
                # Memory fallback
                if key not in _memory_store:
                    _memory_store[key] = []
                _memory_store[key].append(current_time)
                # Clean old entries
                cutoff = current_time - 3600
                _memory_store[key] = [t for t in _memory_store[key] if t > cutoff]
        except Exception as e:
            logger.error(f"Error tracking failed attempt: {e}")
    
    def is_blocked(self, ip_address: str, attempt_type: str = 'login', max_attempts: int = 5, window: int = 300) -> bool:
        """Check if an IP is blocked due to too many failed attempts"""
        try:
            key = f"failed_attempts:{ip_address}:{attempt_type}"
            current_time = int(time.time())
            window_start = current_time - window
            
            if REDIS_AVAILABLE:
                count = redis_client.zcount(key, window_start, current_time)
            else:
                # Memory fallback
                if key not in _memory_store:
                    return False
                # Count recent attempts
                count = sum(1 for t in _memory_store[key] if t > window_start)
            
            return count >= max_attempts
        except Exception as e:
            logger.error(f"Error checking if blocked: {e}")
            return False
    
    def clear_attempts(self, ip_address: str, attempt_type: str = 'login') -> None:
        """Clear failed attempts for successful login"""
        try:
            key = f"failed_attempts:{ip_address}:{attempt_type}"
            
            if REDIS_AVAILABLE:
                redis_client.delete(key)
            else:
                # Memory fallback
                if key in _memory_store:
                    del _memory_store[key]
        except Exception as e:
            logger.error(f"Error clearing attempts: {e}")

class WebhookSecurity:
    """Webhook signature validation and security"""
    
    @staticmethod
    def verify_signature(payload: bytes, signature: str, secret: str, algorithm: str = 'sha256') -> bool:
        """
        Verify webhook signature using HMAC
        
        Args:
            payload: Raw request body
            signature: Signature from header (e.g., 'sha256=abcd1234...')
            secret: Webhook secret
            algorithm: Hash algorithm
        """
        if not signature or not secret:
            return False
        
        # Parse signature format: 'sha256=abcd1234...'
        try:
            method, signature_hash = signature.split('=', 1)
            if method != algorithm:
                return False
        except ValueError:
            return False
        
        # Calculate expected signature
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            getattr(hashlib, algorithm)
        ).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature_hash, expected_signature)
    
    @staticmethod
    def verify_timestamp(timestamp_header: str, tolerance: int = 300) -> bool:
        """
        Verify webhook timestamp to prevent replay attacks
        
        Args:
            timestamp_header: Unix timestamp from header
            tolerance: Max age in seconds (default 5 minutes)
        """
        try:
            webhook_time = int(timestamp_header)
            current_time = int(time.time())
            
            # Check if timestamp is within tolerance
            if abs(current_time - webhook_time) > tolerance:
                logger.warning(f"Webhook timestamp outside tolerance: {webhook_time} vs {current_time}")
                return False
            
            return True
        except (ValueError, TypeError):
            logger.warning(f"Invalid webhook timestamp format: {timestamp_header}")
            return False
    
    @staticmethod
    def create_signature(payload: bytes, secret: str, algorithm: str = 'sha256') -> str:
        """
        Create webhook signature for outgoing webhooks
        
        Args:
            payload: Request body
            secret: Webhook secret
            algorithm: Hash algorithm
            
        Returns:
            Signature in format 'sha256=abcd1234...'
        """
        signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            getattr(hashlib, algorithm)
        ).hexdigest()
        
        return f"{algorithm}={signature}"

def webhook_verified(secret_key_func=None):
    """
    Decorator to verify webhook signatures
    
    Usage:
        @webhook_verified(lambda: current_app.config['WEBHOOK_SECRET'])
        def handle_webhook():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not secret_key_func:
                logger.error("Webhook verification requires secret_key_func")
                return jsonify({'error': 'Configuration error'}), 500
            
            # Get signature and timestamp from headers
            signature = request.headers.get('X-Signature', '')
            timestamp = request.headers.get('X-Timestamp', '')
            
            # Get webhook secret
            try:
                secret = secret_key_func()
                if not secret:
                    logger.error("Webhook secret not configured")
                    return jsonify({'error': 'Webhook verification failed'}), 401
            except Exception as e:
                logger.error(f"Error getting webhook secret: {e}")
                return jsonify({'error': 'Configuration error'}), 500
            
            # Verify timestamp first
            if not WebhookSecurity.verify_timestamp(timestamp):
                from app.utils.audit import log_security_event
                log_security_event(
                    event_type='webhook_replay_attack',
                    details={
                        'timestamp': timestamp,
                        'endpoint': request.endpoint,
                        'ip': request.remote_addr
                    },
                    severity='high'
                )
                return jsonify({'error': 'Invalid timestamp'}), 401
            
            # Verify signature
            payload = request.get_data()
            if not WebhookSecurity.verify_signature(payload, signature, secret):
                from app.utils.audit import log_security_event
                log_security_event(
                    event_type='webhook_signature_invalid',
                    details={
                        'signature': signature,
                        'endpoint': request.endpoint,
                        'ip': request.remote_addr,
                        'payload_size': len(payload)
                    },
                    severity='high'
                )
                return jsonify({'error': 'Invalid signature'}), 401
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Security event types
SECURITY_EVENTS = {
    'rate_limit_exceeded': 'Rate limit exceeded',
    'suspicious_activity': 'Suspicious activity detected',
    'webhook_signature_invalid': 'Invalid webhook signature',
    'webhook_replay_attack': 'Potential webhook replay attack',
    'multiple_failed_logins': 'Multiple failed login attempts',
    'unusual_withdrawal_pattern': 'Unusual withdrawal pattern detected',
    'api_key_misuse': 'API key misuse detected'
}
