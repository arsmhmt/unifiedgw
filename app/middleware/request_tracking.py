"""
Request tracking middleware for diagnostics.
Adds X-Request-ID to all responses and logs request details.
"""
import uuid
import time
import logging
from flask import request, g

logger = logging.getLogger(__name__)


def init_request_tracking(app):
    """Initialize request tracking middleware."""
    
    @app.before_request
    def before_request():
        """Generate request ID and track start time."""
        # Generate or use existing request ID
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        g.request_id = request_id
        g.start_time = time.time()
        
        # Log incoming request
        logger.info(
            f"[{request_id}] {request.method} {request.path}",
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', 'unknown')
            }
        )
    
    @app.after_request
    def after_request(response):
        """Add request ID to response headers and log completion."""
        if hasattr(g, 'request_id'):
            response.headers['X-Request-ID'] = g.request_id
            
            # Calculate request duration
            duration = time.time() - g.start_time if hasattr(g, 'start_time') else 0
            
            # Log response
            logger.info(
                f"[{g.request_id}] {request.method} {request.path} -> {response.status_code} ({duration:.3f}s)",
                extra={
                    'request_id': g.request_id,
                    'method': request.method,
                    'path': request.path,
                    'status_code': response.status_code,
                    'duration_seconds': duration
                }
            )
        
        return response
    
    @app.errorhandler(500)
    def handle_500(error):
        """Handle 500 errors with detailed logging."""
        request_id = getattr(g, 'request_id', 'unknown')
        
        # Log the error with full context
        logger.error(
            f"[{request_id}] 500 Internal Server Error: {request.method} {request.path}",
            exc_info=True,
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
                'error_type': type(error).__name__,
                'error_message': str(error)
            }
        )
        
        # Return JSON error response
        from flask import jsonify
        return jsonify({
            'error': {
                'code': 'internal_error',
                'message': 'An internal server error occurred',
                'request_id': request_id
            }
        }), 500
    
    @app.errorhandler(404)
    def handle_404(error):
        """Handle 404 errors."""
        request_id = getattr(g, 'request_id', 'unknown')
        
        logger.warning(
            f"[{request_id}] 404 Not Found: {request.method} {request.path}",
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.path
            }
        )
        
        from flask import jsonify
        return jsonify({
            'error': {
                'code': 'not_found',
                'message': 'The requested resource was not found',
                'request_id': request_id
            }
        }), 404
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Catch-all exception handler."""
        request_id = getattr(g, 'request_id', 'unknown')
        
        # Log the exception
        logger.exception(
            f"[{request_id}] Unhandled exception: {request.method} {request.path}",
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.path,
                'error_type': type(error).__name__,
                'error_message': str(error)
            }
        )
        
        # Return appropriate error response
        from flask import jsonify
        from werkzeug.exceptions import HTTPException
        
        if isinstance(error, HTTPException):
            return jsonify({
                'error': {
                    'code': error.name.lower().replace(' ', '_'),
                    'message': error.description,
                    'request_id': request_id
                }
            }), error.code
        
        # Generic 500 for unexpected errors
        return jsonify({
            'error': {
                'code': 'internal_error',
                'message': 'An unexpected error occurred',
                'request_id': request_id
            }
        }), 500
    
    logger.info("Request tracking middleware initialized")
