"""
Standardized error responses for API v1.
"""
from flask import jsonify
from app.payment.constants import APIErrorCode


def error_response(code, message, details=None, status_code=400):
    """
    Generate standardized error response.
    
    Args:
        code (str): Error code from APIErrorCode
        message (str): Human-readable error message
        details (dict, optional): Additional error details
        status_code (int): HTTP status code
        
    Returns:
        tuple: (response, status_code)
    """
    response = {
        'error': {
            'code': code,
            'message': message
        }
    }
    
    if details:
        response['error']['details'] = details
    
    return jsonify(response), status_code


def invalid_request_error(message, details=None):
    """Invalid request error (400)."""
    return error_response(
        APIErrorCode.INVALID_REQUEST,
        message,
        details,
        400
    )


def authentication_error(message='Authentication failed'):
    """Authentication error (401)."""
    return error_response(
        APIErrorCode.AUTHENTICATION_FAILED,
        message,
        None,
        401
    )


def not_found_error(resource='Resource'):
    """Resource not found error (404)."""
    return error_response(
        APIErrorCode.RESOURCE_NOT_FOUND,
        f'{resource} not found',
        None,
        404
    )


def internal_error(message='Internal server error'):
    """Internal server error (500)."""
    return error_response(
        APIErrorCode.INTERNAL_ERROR,
        message,
        None,
        500
    )
