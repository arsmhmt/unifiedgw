"""API v1 blueprint."""
from flask import Blueprint

api_v1_bp = Blueprint('api_v1_clean', __name__, url_prefix='/api/v1')

# Import routes to register them
from . import payments, errors

__all__ = ['api_v1_bp']
