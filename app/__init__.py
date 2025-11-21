from flask import Flask, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS
from dotenv import load_dotenv
from pathlib import Path
import os


from app.extensions import db, login_manager, cache
csrf = CSRFProtect()

def get_route_names():
    from flask import current_app
    return [rule.endpoint.split('.')[-1] for rule in current_app.url_map.iter_rules()]

def create_app():
    # Load environment variables from .env file
    load_dotenv()
    
    app = Flask(__name__)

    # Ensure instance directory exists for SQLite and other runtime files
    try:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[WARN] Could not create instance directory: {exc}")
    
    # Enable CORS for demo client and API access
    # Use simple configuration for maximum compatibility
    CORS(app, 
         resources={r"/api/*": {"origins": "*"}},
         allow_headers=["Content-Type", "Authorization", "X-API-Key"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         supports_credentials=False)
    
    # Add manual CORS headers as fallback
    @app.after_request
    def after_request(response):
        origin = request.headers.get('Origin')
        if origin and '/api/' in request.path:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-API-Key'
            response.headers['Access-Control-Max-Age'] = '3600'
        return response
    
    # configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-default-secret')
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        # Use main SQLite database for development with absolute path to avoid Windows path issues
        instance_db_path = Path(app.instance_path) / "paycrypt.db"
        db_url = f"sqlite:///{instance_db_path.as_posix()}"
        print(f"[DEBUG] Using main database: {db_url}")
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Improve DB connection resilience in production
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        # recycle slightly below common 300s idle timeouts on some hosts
        'pool_recycle': int(os.getenv('SQLALCHEMY_POOL_RECYCLE', '280')),
        'pool_size': int(os.getenv('SQLALCHEMY_POOL_SIZE', '5')),
        'max_overflow': int(os.getenv('SQLALCHEMY_MAX_OVERFLOW', '10')),
    }

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # For development - disable CSRF for API testing
    app.config['WTF_CSRF_ENABLED'] = False
    csrf.init_app(app)
    
    # Initialize Babel
    from app.extensions import babel
    babel.init_app(app)
    app.config['BABEL_DEFAULT_LOCALE'] = 'en'

    # Migrate setup
    from flask_migrate import Migrate
    migrate = Migrate(app, db)


    # Flask-Login user loader for AdminUser, Client and User
    from app.models import Client, User
    from app.models.admin import AdminUser
    @login_manager.user_loader
    def load_user(user_id):
        # Check if user_id contains type prefix
        if isinstance(user_id, str):
            if user_id.startswith('admin_'):
                # Load as AdminUser
                actual_id = int(user_id.replace('admin_', ''))
                return AdminUser.query.get(actual_id)
            elif user_id.startswith('user_'):
                # Load as User
                actual_id = int(user_id.replace('user_', ''))
                return User.query.get(actual_id)
            elif user_id.startswith('client_'):
                # Load as Client
                actual_id = int(user_id.replace('client_', ''))
                return Client.query.get(actual_id)
        
        # Fallback: try to load as AdminUser first (for admin)
        admin_user = AdminUser.query.get(int(user_id))
        if admin_user:
            return admin_user
        # If not found as AdminUser, try as User
        user = User.query.get(int(user_id))
        if user:
            return user
        # If not found as User, try as Client
        return Client.query.get(int(user_id))

    # Custom unauthorized handler for Flask-Login
    from flask import redirect, request, url_for
    @login_manager.unauthorized_handler
    def custom_unauthorized():
        next_url = request.url
        # If accessing admin route, redirect to admin login
        if request.path.startswith('/admin120724'):
            return redirect(url_for('auth.admin_login', next=next_url))
        # If accessing provider panel, redirect to provider login
        elif request.path.startswith('/teminci'):
            return redirect(url_for('provider_panel.provider_login', next=next_url))
        # Otherwise, redirect to client login
        return redirect(url_for('auth.login', next=next_url))
    login_manager.login_message_category = 'info'

    # Register custom filters
    from app.utils.filters import escapejs, format_datetime, datetime_eest
    app.jinja_env.filters['escapejs'] = escapejs
    app.jinja_env.filters['format_datetime'] = format_datetime
    app.jinja_env.filters['datetime_eest'] = datetime_eest
    
    # Context processor for admin sidebar stats
    @app.context_processor
    def inject_sidebar_stats():
        if request.path.startswith('/admin120724'):
            from app.models import Client, WithdrawalRequest
            from app.models.enums import WithdrawalType, WithdrawalStatus
            
            try:
                total_clients = Client.query.count()
                pending_client_withdrawals = WithdrawalRequest.query.filter_by(
                    withdrawal_type=WithdrawalType.CLIENT_BALANCE,
                    status=WithdrawalStatus.PENDING
                ).count()
                
                return {
                    'sidebar_stats': {
                        'total_clients': total_clients,
                        'pending_withdrawals': 0,  # Legacy
                        'pending_user_withdrawals': 0,  # TODO
                        'pending_client_withdrawals': pending_client_withdrawals,
                        'pending_tickets': 0,  # TODO
                    }
                }
            except:
                return {
                    'sidebar_stats': {
                        'total_clients': 0,
                        'pending_withdrawals': 0,
                        'pending_user_withdrawals': 0,
                        'pending_client_withdrawals': 0,
                        'pending_tickets': 0,
                    }
                }
        return {}
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.client import client_bp
    from app.routes.admin import admin_bp
    from app.routes.owner import owner_bp
    from app.routes.main import main_bp, api_bp
    from app.routes.withdrawal_admin import withdrawal_admin
    from app.routes.api_v1 import api_v1
    from app.webhooks import webhooks
    from app.utils.wallet_webhooks import wallet_webhooks
    from app.routes.webhooks import webhooks_bp  # wallet provider webhooks
    from app.routes.tools import tools_bp
    from app.routes.api_payment_sessions import payment_sessions_api  # new
    from app.routes.checkout import checkout_bp  # new
    from app.routes.bank_gateway import provider_panel_bp, client_api_bp  # bank gateway (admin integrated into main admin)
    from app.routes.branch import branch_bp  # branch superadmin routes
    from app.routes.demo_gateway import demo_gateway_bp  # public demo gateway experience

    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(owner_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(withdrawal_admin)
    app.register_blueprint(api_bp)
    app.register_blueprint(api_v1)
    app.register_blueprint(webhooks)
    app.register_blueprint(wallet_webhooks)
    app.register_blueprint(webhooks_bp)  # wallet provider webhooks
    app.register_blueprint(tools_bp)
    app.register_blueprint(payment_sessions_api)
    app.register_blueprint(checkout_bp)
    app.register_blueprint(branch_bp)  # branch superadmin routes
    # Register bank gateway blueprints (admin functionality integrated into main admin)
    app.register_blueprint(provider_panel_bp)
    app.register_blueprint(client_api_bp)
    app.register_blueprint(demo_gateway_bp)

    # Debug: Print admin routes
    admin_routes = [rule.endpoint for rule in app.url_map.iter_rules() if rule.endpoint.startswith('admin.')]
    print(f"[DEBUG] Registered admin routes: {len(admin_routes)} routes")
    payment_routes = [rule.endpoint for rule in app.url_map.iter_rules() if 'payment' in rule.endpoint]
    print(f"[DEBUG] Payment routes: {payment_routes}")

    # Exempt JSON APIs from CSRF (they use Bearer auth, not cookies/forms)
    try:
        csrf.exempt(api_v1)
        csrf.exempt(api_bp)
        csrf.exempt(webhooks)
        csrf.exempt(wallet_webhooks)
        csrf.exempt(webhooks_bp)  # wallet provider webhooks
        csrf.exempt(payment_sessions_api)
    except Exception:
        pass

    # Inject get_locale into Jinja2 context
    from app.extensions.extensions import get_locale
    app.jinja_env.globals['get_locale'] = get_locale

    # Inject get_upgrade_package_name into Jinja2 context (if it exists)
    try:
        from app.utils.package_features import get_package_upgrade_recommendations as get_upgrade_package_name
        app.jinja_env.globals['get_upgrade_package_name'] = get_upgrade_package_name
    except ImportError:
        pass
    # Inject get_route_names into Jinja2 context
    app.jinja_env.globals['get_route_names'] = get_route_names
    
    # Inject hasattr into Jinja2 context for template permission checks
    app.jinja_env.globals['hasattr'] = hasattr
    
    # Initialize middleware
    from app.middleware import init_branch_isolation, init_rate_limiting
    init_branch_isolation(app)
    init_rate_limiting(app)
    
    # Context processor for admin notifications
    @app.context_processor
    def inject_admin_notifications():
        from flask_login import current_user
        from app.models.notification import AdminNotification
        
        notification_count = 0
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            # Check if current user is an AdminUser
            if hasattr(current_user, 'is_superuser'):
                notification_count = AdminNotification.get_unread_count(current_user.id)
        
        return {'notification_count': notification_count}
    
    # --- Disabled during migration: SmartBetslip client maintenance ---
    # @app.before_request
    # def ensure_flat_rate_clients_active():
    #     """Ensure flat-rate clients, especially SmartBetslip, remain active"""
    #     try:
    #         from app.decorators import ensure_smartbetslip_active
    #         ensure_smartbetslip_active()
    #     except Exception:
    #         pass  # Silently fail to avoid breaking requests
    
    app.config.setdefault('CHECKOUT_HOST', os.getenv('CHECKOUT_HOST', '').rstrip('/') or None)

    # Serve demo_client static files
    @app.route('/demo_client/')
    @app.route('/demo_client/<path:filename>')
    def serve_demo_client(filename='index.html'):
        demo_client_path = os.path.join(app.root_path, '..', 'demo_client')
        return send_from_directory(demo_client_path, filename)

    return app
# Placeholder for __init__.py
