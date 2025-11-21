"""
API Rate Limiting Middleware
Enforces rate limits on API keys and endpoints
"""

from flask import request, jsonify, g
from functools import wraps
from datetime import datetime, timedelta
from app.extensions import db
from app.models.api_key import ClientApiKey, ApiKeyUsageLog
from ..utils.timezone import now_eest
import time

class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""
    pass

class RateLimiter:
    """Rate limiter for API requests"""
    
    def __init__(self):
        self.cache = {}  # In-memory cache for rate limit tracking
        # Format: {api_key: {'count': 0, 'reset_at': datetime}}
    
    def check_rate_limit(self, api_key_obj):
        """
        Check if API key has exceeded rate limit
        Returns: (allowed: bool, remaining: int, reset_at: datetime)
        """
        api_key = api_key_obj.key
        rate_limit = api_key_obj.rate_limit or 60  # Default 60 req/min
        
        now = now_eest()
        
        # Get or create cache entry
        if api_key not in self.cache:
            self.cache[api_key] = {
                'count': 0,
                'reset_at': now + timedelta(minutes=1)
            }
        
        cache_entry = self.cache[api_key]
        
        # Reset if time window has passed
        if now >= cache_entry['reset_at']:
            cache_entry['count'] = 0
            cache_entry['reset_at'] = now + timedelta(minutes=1)
        
        # Check limit
        if cache_entry['count'] >= rate_limit:
            remaining = 0
            allowed = False
        else:
            cache_entry['count'] += 1
            remaining = rate_limit - cache_entry['count']
            allowed = True
        
        return allowed, remaining, cache_entry['reset_at']
    
    def cleanup_cache(self):
        """Remove expired entries from cache"""
        now = now_eest()
        expired_keys = [
            key for key, value in self.cache.items()
            if now >= value['reset_at'] + timedelta(minutes=5)
        ]
        for key in expired_keys:
            del self.cache[key]

# Global rate limiter instance
rate_limiter = RateLimiter()

def require_api_key(f):
    """
    Decorator to require and validate API key
    Also enforces rate limiting and IP whitelisting
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from header
        api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization')
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key required',
                'message': 'Please provide API key in X-API-Key header'
            }), 401
        
        # Remove "Bearer " prefix if present
        if api_key.startswith('Bearer '):
            api_key = api_key[7:]
        
        # Find API key in database
        api_key_obj = ClientApiKey.query.filter_by(key=api_key).first()
        
        if not api_key_obj:
            return jsonify({
                'success': False,
                'error': 'Invalid API key',
                'message': 'The provided API key is not valid'
            }), 401
        
        # Check if API key is active
        if not api_key_obj.is_active:
            return jsonify({
                'success': False,
                'error': 'API key disabled',
                'message': 'This API key has been disabled'
            }), 403
        
        # Check if API key is expired
        if api_key_obj.expires_at:
            # Handle both timezone-aware and naive datetimes
            current_time = now_eest()
            expires_at = api_key_obj.expires_at
            
            # Make both timezone-aware for comparison
            if expires_at.tzinfo is None:
                # expires_at is naive, convert now_eest to naive
                current_time = current_time.replace(tzinfo=None)
            
            if current_time > expires_at:
                return jsonify({
                    'success': False,
                    'error': 'API key expired',
                    'message': 'This API key has expired'
                }), 403
        
        # Check IP whitelist
        client_ip = request.remote_addr
        if api_key_obj.allowed_ips:
            # Handle both string (comma-separated) and list formats
            if isinstance(api_key_obj.allowed_ips, str):
                allowed_ips = [ip.strip() for ip in api_key_obj.allowed_ips.split(',')]
            else:
                allowed_ips = api_key_obj.allowed_ips if api_key_obj.allowed_ips else []
            
            if allowed_ips and client_ip not in allowed_ips and '*' not in allowed_ips:
                return jsonify({
                    'success': False,
                    'error': 'IP not whitelisted',
                    'message': f'Your IP address ({client_ip}) is not authorized to use this API key'
                }), 403
        
        # Check rate limit
        allowed, remaining, reset_at = rate_limiter.check_rate_limit(api_key_obj)
        
        if not allowed:
            reset_seconds = int((reset_at - now_eest()).total_seconds())
            return jsonify({
                'success': False,
                'error': 'Rate limit exceeded',
                'message': f'Rate limit exceeded. Try again in {reset_seconds} seconds',
                'retry_after': reset_seconds
            }), 429
        
        # Store scalar rate-limit values to avoid DetachedInstanceError later
        g.rate_limit_remaining = remaining
        g.rate_limit_reset = reset_at
        g.api_rate_limit = api_key_obj.rate_limit or 60
        
        # Log API usage
        try:
            log_entry = ApiKeyUsageLog(
                api_key_id=api_key_obj.id,
                endpoint=request.endpoint or request.path,
                method=request.method,
                ip_address=client_ip,
                user_agent=request.headers.get('User-Agent'),
                status_code=None,  # Will be updated in after_request
                response_time_ms=None,  # Will be updated in after_request
                requests_in_window=remaining
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            # Don't fail the request if logging fails
            print(f"Failed to log API usage: {e}")
        
        # Store API key in g for use in the route
        g.api_key = api_key_obj
        g.client = api_key_obj.client
        
        return f(*args, **kwargs)
    
    return decorated_function

def add_rate_limit_headers(response):
    """Add rate limit headers to API responses"""
    if hasattr(g, 'rate_limit_remaining'):
        response.headers['X-RateLimit-Remaining'] = str(g.rate_limit_remaining)
    
    if hasattr(g, 'rate_limit_reset'):
        response.headers['X-RateLimit-Reset'] = g.rate_limit_reset.isoformat()
    
    # Use scalar copy instead of touching ORM object to avoid DetachedInstanceError
    if hasattr(g, 'api_rate_limit'):
        response.headers['X-RateLimit-Limit'] = str(g.api_rate_limit)
    
    return response

def check_endpoint_permissions(required_permissions):
    """
    Decorator to check if API key has required permissions for endpoint
    Usage: @check_endpoint_permissions(['deposit', 'withdraw'])
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'api_key'):
                return jsonify({
                    'success': False,
                    'error': 'Authentication required'
                }), 401
            
            api_key = g.api_key
            
            # Check permissions
            if api_key.permissions:
                api_permissions = api_key.permissions if isinstance(api_key.permissions, list) else []
                
                missing_permissions = [
                    perm for perm in required_permissions
                    if perm not in api_permissions
                ]
                
                if missing_permissions:
                    return jsonify({
                        'success': False,
                        'error': 'Insufficient permissions',
                        'message': f'This API key does not have permission for: {", ".join(missing_permissions)}',
                        'required_permissions': required_permissions,
                        'api_key_permissions': api_permissions
                    }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def init_rate_limiting(app):
    """Initialize rate limiting middleware"""
    
    @app.after_request
    def add_rate_limit_headers_to_response(response):
        """Add rate limit headers to all API responses"""
        if request.path.startswith('/api/'):
            return add_rate_limit_headers(response)
        return response
    
    # Periodic cache cleanup
    import atexit
    atexit.register(lambda: rate_limiter.cleanup_cache())
    
    app.logger.info("Rate limiting middleware initialized")
