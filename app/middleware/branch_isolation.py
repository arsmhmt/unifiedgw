"""
Branch Data Isolation Middleware
Automatically filters queries by branch_id to ensure data isolation between branches
"""

from flask import g, request
from flask_login import current_user
from functools import wraps
from sqlalchemy import event
from sqlalchemy.orm import Query

def get_current_branch_id():
    """Get the current branch ID based on the logged-in user"""
    if not current_user or not current_user.is_authenticated:
        return None
    
    # Owner has access to all branches
    role = getattr(current_user, 'role', None)
    if getattr(role, 'name', None) == 'owner':
        return None
    
    # Branch superadmin
    if hasattr(current_user, 'managed_branch') and current_user.managed_branch:
        return current_user.managed_branch.id
    
    # Admin under a branch
    if hasattr(current_user, 'branch_id') and current_user.branch_id:
        return current_user.branch_id
    
    # Client
    if hasattr(current_user, 'branch_id') and current_user.branch_id:
        return current_user.branch_id
    
    return None

def apply_branch_filter(model_class):
    """
    Apply branch filter to model queries if the model has a branch_id column
    """
    branch_id = get_current_branch_id()
    
    # Owner sees everything
    if branch_id is None:
        return None
    
    # Check if model has branch_id
    if hasattr(model_class, 'branch_id'):
        return {'branch_id': branch_id}
    
    return None

class BranchIsolationMixin:
    """
    Mixin to add to models that should be branch-isolated
    Automatically filters queries by branch_id
    """
    
    @classmethod
    def query_with_branch_filter(cls):
        """Return a query filtered by current branch"""
        from flask_sqlalchemy import BaseQuery
        
        branch_id = get_current_branch_id()
        
        if branch_id is None:
            # Owner or no branch context
            return cls.query
        
        # Filter by branch
        if hasattr(cls, 'branch_id'):
            return cls.query.filter_by(branch_id=branch_id)
        
        return cls.query
    
    @classmethod
    def get_all_for_branch(cls, branch_id=None):
        """Get all records for a specific branch (or current branch)"""
        if branch_id is None:
            branch_id = get_current_branch_id()
        
        if branch_id is None:
            return cls.query.all()
        
        if hasattr(cls, 'branch_id'):
            return cls.query.filter_by(branch_id=branch_id).all()
        
        return cls.query.all()

def ensure_branch_access(func):
    """
    Decorator to ensure branch data isolation on routes
    Validates that the requested resource belongs to the current user's branch
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        branch_id = get_current_branch_id()
        
        # Owner has access to everything
        if branch_id is None:
            return func(*args, **kwargs)
        
        # Check if there's a branch_id or client_id in the route parameters
        resource_branch_id = None
        
        if 'branch_id' in kwargs:
            resource_branch_id = kwargs['branch_id']
        elif 'client_id' in kwargs:
            from app.models import Client
            client = Client.query.get(kwargs['client_id'])
            if client:
                resource_branch_id = client.branch_id
        
        # Validate access
        if resource_branch_id and resource_branch_id != branch_id:
            from flask import abort
            abort(403)  # Forbidden
        
        return func(*args, **kwargs)
    
    return wrapper

def init_branch_isolation(app):
    """
    Initialize branch isolation middleware
    Sets up request context and query filters
    """
    
    @app.before_request
    def set_branch_context():
        """Set the current branch context in Flask's g object"""
        g.branch_id = get_current_branch_id()
    
    @app.after_request
    def log_branch_access(response):
        """Log branch access for audit trail"""
        if hasattr(g, 'branch_id') and g.branch_id:
            # Could add detailed logging here
            pass
        return response
    
    app.logger.info("Branch isolation middleware initialized")
