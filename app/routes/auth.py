from flask import Blueprint, render_template, redirect, request, url_for, flash, session
auth_bp = Blueprint("auth", __name__)
from datetime import datetime
from ..utils.timezone import now_eest
from flask_login import login_user, logout_user, current_user
from app.models import User, Client
from app.models.login_history import LoginHistory, LoginAttemptLimiter
from app.utils import check_password
from app import db
from app.forms import ClientLoginForm, ClientRegistrationForm
import secrets

auth_bp = Blueprint("auth", __name__)

# --- Client Login (Flask-Login expects endpoint 'auth.login') ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Route /login should show appropriate login page based on user type
    # If user is authenticated, redirect to appropriate dashboard
    if current_user.is_authenticated:
        if hasattr(current_user, 'role') and current_user.role:
            role_name = current_user.role.name.lower()
            if role_name == 'owner':
                return redirect(url_for("owner.owner_dashboard"))
            elif role_name == 'client':
                return redirect(url_for("client.client_dashboard"))
        if hasattr(current_user, 'is_admin') and current_user.is_admin:
            return redirect(url_for("admin.admin_dashboard"))
        return redirect(url_for("client.client_dashboard"))
    
    # Check if this is an owner login attempt (from URL or referrer)
    if request.path.startswith('/owner') or request.referrer and '/owner' in request.referrer:
        return owner_login()
    else:
        return client_login()

# --- Register ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = ClientRegistrationForm()
    # TODO: Implement registration logic (form validation, user creation, etc.)
    return render_template('auth/register.html', form=form, now=now_eest())

# --- Reset Password ---
@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    # TODO: Implement password reset logic (token validation, new password form, etc.)
    return render_template('auth/reset_password.html', now=now_eest())

# --- Forgot Password ---
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # TODO: Implement password reset logic (send email, etc.)
        from flask_babel import _
        flash(_('If your email exists in our system, you will receive a password reset link.'), 'info')
    return render_template('auth/forgot_password.html', now=now_eest())

# --- Client Login ---
@auth_bp.route("/client/login", methods=["GET", "POST"])
def client_login():
    form = ClientLoginForm()
    # Only redirect if the current user is a Client (prevents redirect loop for other user types)
    if current_user.is_authenticated and isinstance(current_user, Client):
        return redirect(url_for("client.client_dashboard"))

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')
        
        # Check if account is locked due to failed attempts
        is_blocked, block_message = LoginAttemptLimiter.is_blocked(username, ip_address)
        if is_blocked:
            from flask_babel import _
            flash(_(block_message), "danger")
            return render_template("auth/client_login.html", form=form, now=now_eest())
        
        # First check for owner users
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if hasattr(user, 'role') and user.role and user.role.name.lower() == 'owner':
                # Log successful login
                session_id = secrets.token_urlsafe(32)
                session['login_session_id'] = session_id
                LoginHistory.log_login_attempt(
                    username=username,
                    user_type='owner',
                    success=True,
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    session_id=session_id
                )
                login_user(user, remember=form.remember.data)
                return redirect(url_for("owner.owner_dashboard"))
        
        # Then try to find the User record (for admin-created clients)
        if user and user.check_password(password) and user.client:
            # Check if the linked client is active
            client = user.client
            if client.is_active and not client.is_locked:
                # Log successful login
                session_id = secrets.token_urlsafe(32)
                session['login_session_id'] = session_id
                LoginHistory.log_login_attempt(
                    username=username,
                    user_type='client',
                    success=True,
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    session_id=session_id
                )
                login_user(user, remember=form.remember.data)
                return redirect(url_for("client.client_dashboard"))
        
        # Fallback: try direct Client authentication (for legacy clients)
        client = Client.query.filter_by(username=username).first()
        if client and client.check_password(password) and client.is_active and not client.is_locked:
            # Log successful login
            session_id = secrets.token_urlsafe(32)
            session['login_session_id'] = session_id
            LoginHistory.log_login_attempt(
                username=username,
                user_type='client',
                success=True,
                user_id=client.id,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id
            )
            login_user(client, remember=form.remember.data)
            return redirect(url_for("client.client_dashboard"))
        
        # Log failed attempt
        LoginHistory.log_login_attempt(
            username=username,
            user_type='client',
            success=False,
            failure_reason='invalid_credentials',
            ip_address=ip_address,
            user_agent=user_agent
        )
            
        from flask_babel import _
        flash(_("Invalid credentials"), "danger")

    return render_template("auth/client_login.html", form=form, now=now_eest())

# --- Admin Login ---
@auth_bp.route("/owner/login", methods=["GET", "POST"])
def owner_login():
    form = ClientLoginForm()  # Reuse the same form

    # Redirect if already authenticated as owner
    if current_user.is_authenticated:
        if hasattr(current_user, 'role') and current_user.role and current_user.role.name.lower() == 'owner':
            return redirect(url_for("owner.owner_dashboard"))
        # If authenticated but not owner, redirect to appropriate dashboard
        elif hasattr(current_user, 'is_admin') and current_user.is_admin:
            return redirect(url_for("admin.admin_dashboard"))
        elif hasattr(current_user, 'is_client') and current_user.is_client():
            return redirect(url_for("client.client_dashboard"))

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        # Find User with owner role
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if hasattr(user, 'role') and user.role and user.role.name.lower() == 'owner':
                login_user(user, remember=form.remember.data)
                return redirect(url_for("owner.owner_dashboard"))

        from flask_babel import _
        flash(_("Invalid credentials"), "danger")

    return render_template("auth/owner_login.html", form=form, now=now_eest())

# --- Admin Login ---
@auth_bp.route("/admin120724/login", methods=["GET", "POST"])
def admin_login():
    # Debug: Print session info
    print(f"[DEBUG] Admin login - Current user: {current_user}, is_authenticated: {current_user.is_authenticated}")
    
    if current_user.is_authenticated:
        # Debug: Print user attributes
        print(f"[DEBUG] User attributes: {dir(current_user)}")
        
        # Check if user is AdminUser or has admin privileges
        is_admin = False
        if hasattr(current_user, '__class__') and current_user.__class__.__name__ == 'AdminUser':
            is_admin = True
            print(f"[DEBUG] User is AdminUser, is_admin: {is_admin}")
        elif hasattr(current_user, 'is_admin') and callable(current_user.is_admin):
            is_admin = current_user.is_admin()
            print(f"[DEBUG] is_admin() result: {is_admin}")
        
        # Only redirect if user is actually an admin
        if is_admin:
            print("[DEBUG] User is admin, redirecting to admin dashboard")
            return redirect(url_for("admin.admin_dashboard"))
        # If not admin, log out and show login form
        print("[DEBUG] User is not an admin, logging out")
        logout_user()
        flash("You must be an admin to access this page.", "danger")

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        print(f"[DEBUG] Login attempt - Username: {username}")

        # Check AdminUser table first
        from app.models.admin import AdminUser
        admin_user = AdminUser.query.filter_by(username=username).first()
        print(f"[DEBUG] AdminUser found: {admin_user}")
        
        if admin_user and hasattr(admin_user, 'check_password') and callable(admin_user.check_password):
            print("[DEBUG] Checking AdminUser password...")
            if admin_user.check_password(password):
                print("[DEBUG] AdminUser password correct, logging in...")
                login_user(admin_user)
                print(f"[DEBUG] Logged in as AdminUser {admin_user.username}, is_authenticated: {current_user.is_authenticated}")
                return redirect(url_for("admin.admin_dashboard"))
            else:
                print("[DEBUG] Invalid AdminUser password")
        else:
            # Fallback to User table with roles for backward compatibility
            from app.models import Role
            user = User.query.filter_by(username=username).filter(User.role.has(Role.name.in_(["superadmin", "admin"]))).first()
            print(f"[DEBUG] Fallback User found: {user}")
            
            if user and hasattr(user, 'check_password') and callable(user.check_password):
                print("[DEBUG] Checking User password...")
                if user.check_password(password):
                    print("[DEBUG] User password correct, logging in...")
                    login_user(user)
                    print(f"[DEBUG] Logged in as User {user.username}, is_authenticated: {current_user.is_authenticated}")
                    return redirect(url_for("admin.admin_dashboard"))
                else:
                    print("[DEBUG] Invalid User password")
            else:
                print("[DEBUG] User not found or invalid user type")
            
        flash("Invalid credentials", "danger")

    return render_template("auth/admin_login.html", now=now_eest())

# --- Logout for both ---
@auth_bp.route("/logout")
def logout():
    # Store user role before logout for proper redirect
    was_owner = False
    if current_user.is_authenticated:
        if hasattr(current_user, 'role') and current_user.role and current_user.role.name.lower() == 'owner':
            was_owner = True
        
        # Log logout event
        if hasattr(current_user, 'id'):
            session_id = session.get('login_session_id')
            LoginHistory.log_logout(current_user.id, session_id)

    logout_user()

    # After logout, redirect to correct login page
    if was_owner:
        return redirect(url_for("auth.owner_login"))
    elif request.args.get('next') and request.args.get('next').startswith('/admin120724'):
        return redirect(url_for("auth.admin_login"))
    return redirect(url_for("auth.client_login"))
