# Placeholder for decorators.py
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_admin = False
        try:
            is_admin = current_user.is_authenticated and (
                (hasattr(current_user, 'is_admin') and (
                    current_user.is_admin() if callable(current_user.is_admin) else bool(current_user.is_admin)
                ))
            )
        except Exception:
            is_admin = False
        if not is_admin:
            flash("Admin access only.", "danger")
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def client_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "danger")
            return redirect(url_for('auth.login'))
        
        # Check if user has client role or is a Client instance (for backward compatibility)
        is_client = False
        if hasattr(current_user, 'role') and current_user.role and current_user.role.name == 'client':
            is_client = True
        elif hasattr(current_user, 'is_client') and callable(current_user.is_client) and current_user.is_client():
            is_client = True
        elif current_user.__class__.__name__ == 'Client':
            is_client = True
            
        if not is_client:
            flash("Client access only.", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def commission_client_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'commission':
            flash("Commission-based client access only.", "danger")
            return redirect(url_for('auth.client_login'))
        return f(*args, **kwargs)
    return decorated_function

def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_owner = False
        try:
            is_owner = current_user.is_authenticated and (
                (hasattr(current_user, 'role') and current_user.role and 
                 current_user.role.name.lower() == 'owner')
            )
        except Exception:
            is_owner = False
        if not is_owner:
            flash("Owner access only.", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_superadmin = False
        try:
            is_superadmin = current_user.is_authenticated and (
                (hasattr(current_user, 'is_superuser') and current_user.is_superuser) or
                (hasattr(current_user, 'role') and current_user.role and 
                 current_user.role.name.lower() == 'superadmin')
            )
        except Exception:
            is_superadmin = False
        if not is_superadmin:
            flash("Superadmin access only.", "danger")
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def branch_superadmin_required(f):
    """Decorator for branch superadmins - can only access their own branch's data"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in.", "danger")
            return redirect(url_for('auth.admin_login'))
        
        # Check if user is a superadmin with a managed branch
        is_branch_superadmin = (
            hasattr(current_user, 'role') and current_user.role and 
            current_user.role.name.lower() == 'superadmin' and
            hasattr(current_user, 'managed_branch') and current_user.managed_branch
        )
        
        if not is_branch_superadmin:
            flash("Branch superadmin access only.", "danger")
            return redirect(url_for('auth.admin_login'))
        
        return f(*args, **kwargs)
    return decorated_function

def branch_admin_required(f):
    """Decorator for branch admins - can access branch data with permissions"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in.", "danger")
            return redirect(url_for('auth.admin_login'))
        
        # Check if user is admin under a branch
        is_branch_admin = (
            hasattr(current_user, 'role') and current_user.role and 
            current_user.role.name.lower() == 'admin' and
            hasattr(current_user, 'branch') and current_user.branch
        )
        
        if not is_branch_admin:
            flash("Branch admin access only.", "danger")
            return redirect(url_for('auth.admin_login'))
        
        return f(*args, **kwargs)
    return decorated_function

def flat_rate_client_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'flat':
            flash("Flat-rate client access only.", "danger")
            return redirect(url_for('auth.client_login'))
        return f(*args, **kwargs)
    return decorated_function

def is_payment_exempt_client(client):
    """
    Check if a client is exempt from payment enforcement.
    Returns True for flat-rate clients that should skip payment checks.
    """
    if not client or not hasattr(client, 'package'):
        return False
    
    # Skip payment enforcement for flat-rate SmartBetslip client
    if (client.company_name in ['SBS', 'SmartBetslip'] and 
        client.package and 
        hasattr(client.package, 'client_type')):
        from app.models.client_package import ClientType
        if client.package.client_type == ClientType.FLAT_RATE:
            return True
    
    # Skip payment enforcement for ALL flat-rate packages (package_type == 'flat_rate')
    if (client.package and 
        hasattr(client.package, 'client_type')):
        from app.models.client_package import ClientType
        if client.package.client_type == ClientType.FLAT_RATE:
            return True
    
    # Add more exemption rules here if needed
    return False

def ensure_smartbetslip_active():
    """
    Ensure SmartBetslip client is always marked as active.
    This function can be called from various parts of the application.
    """
    from app.models import Client
    from app.extensions import db
    
    try:
        # Find SmartBetslip client
        smartbetslip_client = Client.query.filter(
            Client.company_name.in_(['SBS', 'SmartBetslip'])
        ).first()
        
        if smartbetslip_client and not smartbetslip_client.is_active:
            smartbetslip_client.is_active = True
            db.session.commit()
            return True
    except Exception as e:
        print(f"Error ensuring SmartBetslip active status: {e}")
        
    return False
