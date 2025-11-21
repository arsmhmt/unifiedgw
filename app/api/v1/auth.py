"""
API authentication and authorization.
"""
from functools import wraps
from flask import request
from datetime import datetime

from .errors import authentication_error
from app.models.client import Client
from app.payment.constants import APIErrorCode


def api_key_required(f):
    """
    Decorator to require API key authentication.
    
    Expects Authorization header with format: Bearer <api_key>
    Sets request.api_client to the authenticated client.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get Authorization header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return authentication_error('Missing Authorization header')
        
        if not auth_header.startswith('Bearer '):
            return authentication_error('Invalid Authorization header format (use Bearer <api_key>)')
        
        # Extract API key
        api_key = auth_header.replace('Bearer ', '').strip()
        
        if not api_key:
            return authentication_error('Empty API key')
        
        # Find client by API key
        client = Client.query.filter_by(api_key=api_key).first()
        
        if not client:
            return authentication_error('Invalid API key')
        
        # Check if client is active
        if not client.is_active:
            return authentication_error('API key is disabled')
        
        # TODO: Add rate limiting check here if needed
        # if client.rate_limit and check_rate_limit(client):
        #     return error_response(APIErrorCode.RATE_LIMIT_EXCEEDED, 'Rate limit exceeded', None, 429)
        
        # Attach client to request context
        request.api_client = client
        
        return f(*args, **kwargs)
    
    return decorated_function
