from flask import Blueprint, render_template, redirect, request, url_for, flash, current_app, jsonify
from sqlalchemy import func
from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from app.forms_withdrawal import WithdrawalRequestForm
from app.models.withdrawal import WithdrawalRequest, WithdrawalStatus
from flask_login import login_user, logout_user, login_required, current_user
from app.models import Client
from app.models.user import User
from app import db
from app.utils.admin_notifications import create_withdrawal_request_notification
from werkzeug.security import check_password_hash
from app.decorators import client_required
from app.models.api_key import ClientApiKey, ApiKeyScope

client_bp = Blueprint("client", __name__, url_prefix="/client")

@client_bp.context_processor
def inject_client_context():
    """Make client data available to all client templates"""
    if current_user.is_authenticated:
        if isinstance(current_user, User) and current_user.client:
            # User with linked client
            return {'client': current_user.client}
        elif isinstance(current_user, Client):
            # Direct client login
            return {'client': current_user}
    return {}

# --- Payments Page (unified crypto + bank) ---
@client_bp.route('/payments')
@login_required
def payments():
    from app.models.bank_gateway import BankGatewayClientSite, BankGatewayTransaction
    from app.models.payment_session import PaymentSession
    
    # Get client data
    client_data = None
    if isinstance(current_user, User) and current_user.client:
        client_data = current_user.client
    elif isinstance(current_user, Client):
        client_data = current_user
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))
    
    # Get crypto payments (PaymentSession)
    crypto_payments = []
    try:
        crypto_payments = PaymentSession.query.filter_by(client_id=client_data.id).order_by(
            PaymentSession.created_at.desc()
        ).limit(20).all()
    except Exception:
        crypto_payments = []
    
    # Get bank payments
    bank_sites = BankGatewayClientSite.query.filter_by(client_id=client_data.id).all()
    bank_payments = []
    if bank_sites:
        site_ids = [site.id for site in bank_sites]
        bank_payments = BankGatewayTransaction.query.filter(
            BankGatewayTransaction.client_site_id.in_(site_ids)
        ).order_by(BankGatewayTransaction.created_at.desc()).limit(20).all()
    
    # Combine and sort by date
    all_payments = []
    
    # Add crypto payments with type indicator
    for payment in crypto_payments:
        all_payments.append({
            'type': 'crypto',
            'id': payment.id,
            'amount': getattr(payment, 'total_amount', 0),
            'currency': getattr(payment, 'currency', 'BTC'),
            'status': getattr(payment, 'status', 'unknown'),
            'created_at': payment.created_at,
            'description': f"Crypto Payment #{payment.id}",
            'reference': getattr(payment, 'session_id', str(payment.id))
        })
    
    # Add bank payments with type indicator
    for payment in bank_payments:
        all_payments.append({
            'type': 'bank',
            'id': payment.id,
            'amount': float(payment.amount),
            'currency': payment.currency,
            'status': payment.status,
            'created_at': payment.created_at,
            'description': f"Bank {payment.transaction_type.title()} #{payment.reference_code}",
            'reference': payment.reference_code
        })
    
    # Sort by date (newest first)
    all_payments.sort(key=lambda x: x['created_at'], reverse=True)
    
    # Take top 50 for display
    all_payments = all_payments[:50]
    
    # Create pagination stub for template compatibility
    class PaymentPagination:
        def __init__(self, items):
            self.items = items
            self.pages = 1
            self.page = 1
        def iter_pages(self):
            return [1]
    
    payments = PaymentPagination(all_payments)
    
    return render_template('client/payments.html', 
                         client=current_user, 
                         payments=payments,
                         crypto_count=len(crypto_payments),
                         bank_count=len(bank_payments))

# --- Bank Gateway Management ---
@client_bp.route('/bank-gateway')
@login_required
@client_required
def bank_gateway():
    """Bank gateway management for clients"""
    from app.models.bank_gateway import BankGatewayClientSite, BankGatewayAPIKey, BankGatewayTransaction
    
    # Get client data
    client_data = None
    if isinstance(current_user, User) and current_user.client:
        client_data = current_user.client
    elif isinstance(current_user, Client):
        client_data = current_user
    
    # Get client's bank gateway sites
    bank_sites = BankGatewayClientSite.query.filter_by(client_id=client_data.id).all()
    
    # Get statistics for each site
    site_stats = {}
    for site in bank_sites:
        transactions = BankGatewayTransaction.query.filter_by(client_site_id=site.id).all()
        site_stats[site.id] = {
            'total_transactions': len(transactions),
            'total_volume': sum(float(tx.amount or 0) for tx in transactions),
            'pending_count': len([tx for tx in transactions if tx.status == 'pending']),
            'success_count': len([tx for tx in transactions if tx.status == 'confirmed']),
        }
    
    return render_template('client/bank_gateway.html', 
                         bank_sites=bank_sites,
                         site_stats=site_stats)

@client_bp.route('/bank-gateway/site/<int:site_id>')
@login_required
@client_required
def bank_gateway_site_detail(site_id):
    """View details of a specific bank gateway site"""
    from app.models.bank_gateway import BankGatewayClientSite, BankGatewayTransaction
    
    # Get client data
    client_data = None
    if isinstance(current_user, User) and current_user.client:
        client_data = current_user.client
    elif isinstance(current_user, Client):
        client_data = current_user
    
    # Get the site (ensure it belongs to current client)
    site = BankGatewayClientSite.query.filter_by(
        id=site_id, 
        client_id=client_data.id
    ).first_or_404()
    
    # Get transactions for this site
    transactions = BankGatewayTransaction.query.filter_by(
        client_site_id=site.id
    ).order_by(BankGatewayTransaction.created_at.desc()).limit(50).all()
    
    # Calculate statistics
    stats = {
        'total_transactions': len(transactions),
        'total_volume': sum(float(tx.amount or 0) for tx in transactions),
        'pending_count': len([tx for tx in transactions if tx.status == 'pending']),
        'success_count': len([tx for tx in transactions if tx.status == 'confirmed']),
        'failed_count': len([tx for tx in transactions if tx.status == 'rejected']),
    }
    
    return render_template('client/bank_gateway_site.html',
                         site=site,
                         transactions=transactions,
                         stats=stats)

@client_bp.route('/bank-transactions')
@login_required
@client_required
def bank_transactions():
    """View all bank gateway transactions for the client"""
    from app.models.bank_gateway import BankGatewayClientSite, BankGatewayTransaction
    
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    period_filter = request.args.get('period')
    
    # Get client data
    client_data = None
    if isinstance(current_user, User) and current_user.client:
        client_data = current_user.client
    elif isinstance(current_user, Client):
        client_data = current_user
    
    # Base query for user's bank transactions
    query = BankGatewayTransaction.query.join(BankGatewayClientSite).filter(
        BankGatewayClientSite.client_id == client_data.id
    )
    
    # Apply status filter
    if status_filter:
        query = query.filter(BankGatewayTransaction.status == status_filter)
    
    # Apply period filter
    if period_filter:
        from datetime import datetime, timedelta
        now = now_eest()
        if period_filter == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(BankGatewayTransaction.created_at >= start_date)
        elif period_filter == 'week':
            start_date = now - timedelta(days=7)
            query = query.filter(BankGatewayTransaction.created_at >= start_date)
        elif period_filter == 'month':
            start_date = now - timedelta(days=30)
            query = query.filter(BankGatewayTransaction.created_at >= start_date)
    
    # Get paginated transactions
    transactions = query.order_by(BankGatewayTransaction.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Calculate statistics for display
    pending_count = BankGatewayTransaction.query.join(BankGatewayClientSite).filter(
        BankGatewayClientSite.client_id == client_data.id,
        BankGatewayTransaction.status == 'pending'
    ).count()
    
    completed_count = BankGatewayTransaction.query.join(BankGatewayClientSite).filter(
        BankGatewayClientSite.client_id == client_data.id,
        BankGatewayTransaction.status == 'completed'
    ).count()
    
    failed_count = BankGatewayTransaction.query.join(BankGatewayClientSite).filter(
        BankGatewayClientSite.client_id == client_data.id,
        BankGatewayTransaction.status == 'failed'
    ).count()
    
    total_volume = db.session.query(func.sum(BankGatewayTransaction.amount)).join(BankGatewayClientSite).filter(
        BankGatewayClientSite.client_id == client_data.id
    ).scalar() or 0
    
    return render_template('client/bank_transactions.html',
                         transactions=transactions,
                         pending_count=pending_count,
                         completed_count=completed_count,
                         failed_count=failed_count,
                         total_volume=total_volume)

# --- Payment History Page (stub) ---
@client_bp.route('/payment-history')
@login_required
@client_required
def payment_history():
    # TODO: Implement payment history logic
    return render_template('client/payment_history.html')

# --- Support Page (stub) ---
@client_bp.route('/support')
@login_required
@client_required
def support():
    # TODO: Implement support logic
    return render_template('client/support.html')

# --- Profile Page (stub) ---
@client_bp.route('/profile')
@login_required
@client_required
def profile():
    # TODO: Implement profile logic
    return render_template('client/profile.html', client=current_user)

# --- API Management (Client) ---
@client_bp.route('/api', methods=['GET'], endpoint='api_management')
@login_required
@client_required
def api_management():
    # Resolve client record for current user
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))

    keys = ClientApiKey.query.filter_by(client_id=client_data.id).order_by(ClientApiKey.created_at.desc()).all()
    # Expose scopes grouped by type for UI help
    flat_scopes = [s.value for s in ApiKeyScope if s.value.startswith('flat_rate:')]
    commission_scopes = [s.value for s in ApiKeyScope if s.value.startswith('commission:')]
    return render_template('client/api_management.html', client=client_data, api_keys=keys,
                           flat_scopes=flat_scopes, commission_scopes=commission_scopes)


@client_bp.route('/api/docs', methods=['GET'])
@login_required
@client_required
def api_documentation():
    """Client API documentation page"""
    return render_template('client/api_docs.html')


@client_bp.route('/api/sdk/<filename>')
@login_required
@client_required
def download_sdk(filename):
    """Download SDK files"""
    from flask import send_from_directory
    import os
    
    # Security: only allow specific SDK files
    allowed_files = ['paycrypt_sdk.py', 'paycrypt_sdk.js', 'paycrypt_sdk.php']
    
    if filename not in allowed_files:
        flash('SDK file not found', 'error')
        return redirect(url_for('client.api_documentation'))
    
    sdk_dir = os.path.join(current_app.root_path, 'static', 'sdk')
    return send_from_directory(sdk_dir, filename, as_attachment=True)


@client_bp.route('/api/keys/create', methods=['POST'], endpoint='create_api_key_management')
@login_required
@client_required
def create_api_key_management():
    # Resolve client
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))

    # Parse form data
    name = request.form.get('name', 'Default API Key')
    rate_limit = int(request.form.get('rate_limit', 60))
    requested_perms = request.form.getlist('permissions') or []

    # Create an API key tailored to client type
    api_key = ClientApiKey.create_for_client_by_type(
        client=client_data,
        name=name,
        permissions=requested_perms or None,
        rate_limit=rate_limit,
        expires_at=None,
    )

    # Persist (create_for_client_by_type does not commit)
    db.session.add(api_key)
    db.session.commit()

    # We return the key and secret one time via flash message and redirect to management page
    from flask_babel import _
    flash(_(f"API key '{name}' created successfully! Copy these credentials now - they won't be shown again:\n\nAPI Key: {api_key.key}\nSecret Key: {api_key.secret_key}\nWebhook Secret: {api_key.webhook_secret or 'Not generated'}"), 'success')
    return redirect(url_for('client.api_management'))


@client_bp.route('/api/keys/<int:key_id>/deactivate', methods=['POST'])
@login_required
@client_required
def deactivate_api_key(key_id: int):
    # Ensure ownership
    client_id = getattr(current_user, 'id', None) if current_user.__class__.__name__ == 'Client' else getattr(getattr(current_user, 'client', None), 'id', None)
    key = ClientApiKey.query.filter_by(id=key_id, client_id=client_id).first()
    if not key:
        from flask_babel import _
        flash(_("API key not found"), 'danger')
        return redirect(url_for('client.api_management'))
    key.is_active = False
    db.session.commit()
    from flask_babel import _
    flash(_("API key deactivated"), 'info')
    return redirect(url_for('client.api_management'))


@client_bp.route('/api/keys/<int:key_id>/regenerate', methods=['POST'])
@login_required
@client_required
def regenerate_api_key(key_id: int):
    """Regenerate API key and secret"""
    # Ensure ownership
    client_id = getattr(current_user, 'id', None) if current_user.__class__.__name__ == 'Client' else getattr(getattr(current_user, 'client', None), 'id', None)
    key = ClientApiKey.query.filter_by(id=key_id, client_id=client_id).first()
    
    if not key:
        return jsonify({'success': False, 'error': 'API key not found'}), 404
    
    if not key.is_active:
        return jsonify({'success': False, 'error': 'Cannot regenerate inactive key'}), 400
    
    try:
        # Generate new key and secret
        new_key = ClientApiKey.generate_key()
        new_secret = ClientApiKey.generate_key()
        
        # Update the key
        key.key = new_key
        key.key_prefix = ClientApiKey.generate_key_prefix(new_key)
        key.key_hash = ClientApiKey.hash_key(new_key)
        key.secret_key = new_secret
        key.last_used_at = None  # Reset usage
        key.usage_count = 0
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'key': new_key,
            'secret': new_secret,
            'message': 'API key regenerated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@client_bp.route('/api/bank-keys/<int:site_id>/regenerate', methods=['POST'])
@login_required
@client_required
def regenerate_bank_api_key(site_id: int):
    """Regenerate bank gateway API key"""
    from app.models.bank_gateway import BankGatewayClientSite, BankGatewayAPIKey
    import secrets
    
    # Ensure ownership
    client_id = getattr(current_user, 'id', None) if current_user.__class__.__name__ == 'Client' else getattr(getattr(current_user, 'client', None), 'id', None)
    site = BankGatewayClientSite.query.filter_by(id=site_id, client_id=client_id).first()
    
    if not site:
        return jsonify({'success': False, 'error': 'Bank site not found'}), 404
    
    if not site.is_active:
        return jsonify({'success': False, 'error': 'Cannot regenerate key for inactive site'}), 400
    
    try:
        # Generate new bank API key
        new_key = secrets.token_urlsafe(32)
        
        if site.api_key:
            # Update existing key
            site.api_key.key = new_key
        else:
            # Create new API key
            bank_api_key = BankGatewayAPIKey(
                client_site_id=site.id,
                key=new_key
            )
            db.session.add(bank_api_key)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'key': new_key,
            'message': 'Bank API key regenerated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Withdrawal Analytics (stub) ---
@client_bp.route('/withdrawal-analytics')
@login_required
@client_required
def withdrawal_analytics():
    from app.models import Payment, WithdrawalRequest, Transaction
    from app.models.enums import PaymentStatus, WithdrawalStatus
    from sqlalchemy import func, extract
    from datetime import datetime, timedelta
    import calendar
    
    # Get client data properly
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
        client_id = current_user.client.id
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
        client_id = current_user.id
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))
    
    # Date filters
    end_date = now_eest()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    year_start = datetime(end_date.year, 1, 1)
    
    # === PAYMENT ANALYTICS ===
    # Total payments received
    total_payments = db.session.query(func.sum(Payment.fiat_amount)).filter(
        Payment.client_id == client_id,
        Payment.status == PaymentStatus.COMPLETED
    ).scalar() or 0
    
    # Payments in the last 30 days
    recent_payments = db.session.query(func.sum(Payment.fiat_amount)).filter(
        Payment.client_id == client_id,
        Payment.status == PaymentStatus.COMPLETED,
        Payment.created_at >= start_date
    ).scalar() or 0
    
    # Payment count
    payment_count = Payment.query.filter(
        Payment.client_id == client_id,
        Payment.status == PaymentStatus.COMPLETED
    ).count()
    
    # === WITHDRAWAL ANALYTICS ===
    # Total withdrawals processed
    total_withdrawals = db.session.query(func.sum(WithdrawalRequest.net_amount)).filter(
        WithdrawalRequest.client_id == client_id,
        WithdrawalRequest.status == WithdrawalStatus.COMPLETED
    ).scalar() or 0
    
    # Pending withdrawals
    pending_withdrawals = db.session.query(func.sum(WithdrawalRequest.amount)).filter(
        WithdrawalRequest.client_id == client_id,
        WithdrawalRequest.status == WithdrawalStatus.PENDING
    ).scalar() or 0
    
    # Withdrawal count
    withdrawal_count = WithdrawalRequest.query.filter(
        WithdrawalRequest.client_id == client_id
    ).count()
    
    # === MONTHLY BREAKDOWN ===
    # Monthly payment data (last 12 months)
    monthly_payments = db.session.query(
        extract('year', Payment.created_at).label('year'),
        extract('month', Payment.created_at).label('month'),
        func.sum(Payment.fiat_amount).label('total'),
        func.count(Payment.id).label('count')
    ).filter(
        Payment.client_id == client_id,
        Payment.status == PaymentStatus.COMPLETED,
        Payment.created_at >= datetime(end_date.year - 1, end_date.month, 1)
    ).group_by(
        extract('year', Payment.created_at),
        extract('month', Payment.created_at)
    ).order_by(
        extract('year', Payment.created_at),
        extract('month', Payment.created_at)
    ).all()
    
    # Monthly withdrawal data
    monthly_withdrawals = db.session.query(
        extract('year', WithdrawalRequest.created_at).label('year'),
        extract('month', WithdrawalRequest.created_at).label('month'),
        func.sum(WithdrawalRequest.net_amount).label('total'),
        func.count(WithdrawalRequest.id).label('count')
    ).filter(
        WithdrawalRequest.client_id == client_id,
        WithdrawalRequest.status == WithdrawalStatus.COMPLETED,
        WithdrawalRequest.created_at >= datetime(end_date.year - 1, end_date.month, 1)
    ).group_by(
        extract('year', WithdrawalRequest.created_at),
        extract('month', WithdrawalRequest.created_at)
    ).order_by(
        extract('year', WithdrawalRequest.created_at),
        extract('month', WithdrawalRequest.created_at)
    ).all()
    
    # === CURRENCY BREAKDOWN ===
    # Payment by currency
    payment_by_currency = db.session.query(
        Payment.crypto_currency.label('currency'),
        func.sum(Payment.fiat_amount).label('fiat_total'),
        func.sum(Payment.crypto_amount).label('crypto_total'),
        func.count(Payment.id).label('count')
    ).filter(
        Payment.client_id == client_id,
        Payment.status == PaymentStatus.COMPLETED
    ).group_by(Payment.crypto_currency).all()
    
    # Withdrawal by currency
    withdrawal_by_currency = db.session.query(
        WithdrawalRequest.currency.label('currency'),
        func.sum(WithdrawalRequest.net_amount).label('total'),
        func.count(WithdrawalRequest.id).label('count')
    ).filter(
        WithdrawalRequest.client_id == client_id,
        WithdrawalRequest.status == WithdrawalStatus.COMPLETED
    ).group_by(WithdrawalRequest.currency).all()
    
    # === RECENT TRANSACTIONS ===
    # Recent payments (last 10)
    recent_payments_list = Payment.query.filter(
        Payment.client_id == client_id
    ).order_by(Payment.created_at.desc()).limit(10).all()
    
    # Recent withdrawals (last 10)
    recent_withdrawals_list = WithdrawalRequest.query.filter(
        WithdrawalRequest.client_id == client_id
    ).order_by(WithdrawalRequest.created_at.desc()).limit(10).all()
    
    # === BALANCE INFO ===
    current_balance = client_data.balance or 0
    
    # Net profit (payments - withdrawals)
    net_profit = float(total_payments or 0) - float(total_withdrawals or 0)
    
    # Package the data for the template
    analytics_data = {
        'summary': {
            'total_payments': float(total_payments or 0),
            'recent_payments': float(recent_payments or 0),
            'payment_count': payment_count,
            'total_withdrawals': float(total_withdrawals or 0),
            'pending_withdrawals': float(pending_withdrawals or 0),
            'withdrawal_count': withdrawal_count,
            'current_balance': float(current_balance),
            'net_profit': net_profit
        },
        'monthly_payments': monthly_payments,
        'monthly_withdrawals': monthly_withdrawals,
        'payment_by_currency': payment_by_currency,
        'withdrawal_by_currency': withdrawal_by_currency,
        'recent_payments': recent_payments_list,
        'recent_withdrawals': recent_withdrawals_list
    }
    
    return render_template('client/withdrawal_analytics.html', 
                         client=client_data,
                         analytics=analytics_data)

# --- Invoices Page ---
@client_bp.route("/invoices")
@login_required
@client_required
def invoices():
    return render_template("client/invoices.html")


# --- Documents Page ---
@client_bp.route("/documents")
@login_required
@client_required
def documents():
    return render_template("client/documents.html")


# --- Logout ---
@client_bp.route("/logout", endpoint="logout")
@login_required
def client_logout():
    logout_user()
    return redirect(url_for("client.client_login"))


# --- Dashboard ---
@client_bp.route("/dashboard")
def client_dashboard():
    from app.models.bank_gateway import (
        BankGatewayClientSite, BankGatewayTransaction, BankGatewayAPIKey
    )
    from app.models.payment_session import PaymentSession
    from app.models.payment import Payment

    # Check if user has client role or is a Client instance
    is_client = False
    client_data = None

    if isinstance(current_user, User) and current_user.client:
        # User with linked client
        is_client = True
        client_data = current_user.client
    elif isinstance(current_user, Client):
        # Direct Client instance
        is_client = True
        client_data = current_user

    if not is_client or not client_data:
        from flask_babel import _
        flash(_("Unauthorized access - Client access required"), "danger")
        return redirect(url_for("auth.login"))

    # Get crypto payment stats (existing logic)
    crypto_stats = {
        'balance': getattr(client_data, 'balance', 0),
        'monthly_transactions': getattr(client_data, 'monthly_transactions', 0),
        'monthly_volume': getattr(client_data, 'monthly_volume', 0),
        'monthly_transaction_limit': getattr(client_data, 'monthly_transaction_limit', 1000),
        'monthly_volume_limit': getattr(client_data, 'monthly_volume_limit', 10000),
    }

    # Get bank gateway stats
    bank_sites = BankGatewayClientSite.query.filter_by(client_id=client_data.id).all()
    bank_stats = {
        'total_sites': len(bank_sites),
        'active_sites': len([site for site in bank_sites if site.is_active]),
        'total_transactions': 0,
        'total_volume': 0,
        'pending_deposits': 0,
        'recent_transactions': []
    }

    if bank_sites:
        # Get transactions for all client sites
        site_ids = [site.id for site in bank_sites]
        transactions = BankGatewayTransaction.query.filter(
            BankGatewayTransaction.client_site_id.in_(site_ids)
        ).all()

        bank_stats['total_transactions'] = len(transactions)
        bank_stats['total_volume'] = sum(float(tx.amount or 0) for tx in transactions)
        bank_stats['pending_deposits'] = len([tx for tx in transactions if tx.status == 'pending' and tx.transaction_type == 'deposit'])
        bank_stats['recent_transactions'] = BankGatewayTransaction.query.filter(
            BankGatewayTransaction.client_site_id.in_(site_ids)
        ).order_by(BankGatewayTransaction.created_at.desc()).limit(5).all()

    # Payment history (crypto payment sessions)
    payments_query = PaymentSession.query.filter_by(client_id=client_data.id).order_by(PaymentSession.created_at.desc())
    recent_payment_sessions = payments_query.limit(5).all()

    # Fallback to ensure template loop works with .items access pattern
    class _RecentPayments:
        def __init__(self, items):
            self.items = items

    payments = _RecentPayments(recent_payment_sessions)

    # Derive dashboard-level metrics
    monthly_window_start = now_eest() - timedelta(days=30)

    # Cryptocurrency metrics from payment sessions
    monthly_crypto_sessions = PaymentSession.query.filter(
        PaymentSession.client_id == client_data.id,
        PaymentSession.created_at >= monthly_window_start
    ).all()

    monthly_crypto_volume = sum(float(session.amount or 0) for session in monthly_crypto_sessions)
    monthly_crypto_transactions = len(monthly_crypto_sessions)

    # Historical fiat payments (legacy model) if available
    legacy_payments = Payment.query.filter(
        Payment.client_id == client_data.id,
        Payment.created_at >= monthly_window_start
    ).all()

    legacy_volume = sum(float(payment.fiat_amount or payment.amount or 0) for payment in legacy_payments)
    legacy_transactions = len(legacy_payments)

    monthly_transactions = monthly_crypto_transactions + legacy_transactions
    monthly_volume = monthly_crypto_volume + legacy_volume

    # Reasonable defaults; ideally pulled from package settings
    monthly_transaction_limit = getattr(client_data, 'monthly_transaction_limit', 1000) or 1000
    monthly_volume_limit = getattr(client_data, 'monthly_volume_limit', 10000) or 10000

    # Combined stats for unified view
    unified_stats = {
        'total_transactions': crypto_stats['monthly_transactions'] + bank_stats['total_transactions'],
        'total_volume': crypto_stats['monthly_volume'] + bank_stats['total_volume'],
        'crypto_balance': crypto_stats['balance'],
        'bank_sites': bank_stats['total_sites'],
        'pending_operations': bank_stats['pending_deposits'],
    }

    # The template will get proper client data from context processor
    return render_template("client/dashboard.html",
                         crypto_stats=crypto_stats,
                         bank_stats=bank_stats,
                         unified_stats=unified_stats,
                         bank_sites=bank_sites,
                         payments=payments,
                         monthly_transactions=monthly_transactions,
                         monthly_transaction_limit=monthly_transaction_limit,
                         monthly_volume=monthly_volume,
                         monthly_volume_limit=monthly_volume_limit)
@client_required
@client_bp.route("/settings", methods=["GET", "POST"], endpoint="settings")
def client_settings():
    # Get client data properly for both User and Client objects
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        current_user.wallet_address = request.form["wallet_address"]
        current_user.api_key = request.form["api_key"]
        current_user.api_secret = request.form["api_secret"]
        db.session.commit()
        from flask_babel import _
        flash(_("Settings updated"), "success")
        return redirect(url_for("client.client_settings"))

    return render_template("client/settings.html")

# --- Notification Preferences ---
@client_bp.route("/notification-preferences", methods=["GET", "POST"])
@login_required
@client_required
def notification_preferences():
    # Add logic to fetch and update notification preferences
    return render_template("client/notification_preferences.html")

# --- Wallet Configure Page ---
@client_bp.route("/wallet-configure")
@login_required
@client_required
def wallet_configure():
    # Get client data properly
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))
    
    # Get client wallets from database
    from app.models import ClientWallet
    wallets = ClientWallet.query.filter_by(client_id=client_data.id).all()
    
    # Get client type for wallet features
    client_type = 'flat_rate' if client_data.package and 'flat' in client_data.package.name.lower() else 'commission'
    
    return render_template("client/wallet_configure.html", 
                         client=client_data,
                         wallets=wallets,
                         client_type=client_type)

# --- Create Wallet Configuration ---
@client_bp.route("/wallet-configure/create", methods=["POST"])
@login_required
@client_required
def create_wallet():
    # Get client data properly
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))
    
    from app.models import ClientWallet, WalletType, WalletStatus
    from flask import jsonify
    
    try:
        wallet_name = request.form.get('wallet_name', 'Default Wallet')
        wallet_type = request.form.get('wallet_type', 'custom_manual')
        
        # Get supported currencies
        supported_currencies = request.form.getlist('supported_currencies')
        if not supported_currencies:
            supported_currencies = ['USDT', 'BTC', 'ETH']
        
        # Convert string to enum
        try:
            wallet_type_enum = WalletType(wallet_type)
        except ValueError:
            wallet_type_enum = WalletType.CUSTOM_MANUAL
        
        # Create wallet object
        new_wallet = ClientWallet(
            client_id=client_data.id,
            wallet_name=wallet_name,
            wallet_type=wallet_type_enum,
            status=WalletStatus.PENDING_VERIFICATION,
            supported_currencies=supported_currencies,
            wallet_addresses={},
            settings={}
        )
        
        # Handle wallet configuration based on type
        if wallet_type_enum == WalletType.CUSTOM_API:
            # API configuration
            new_wallet.api_key = request.form.get('api_key', '')
            new_wallet.api_secret = request.form.get('api_secret', '')
            new_wallet.api_endpoint = request.form.get('api_endpoint', '')
            new_wallet.webhook_url = request.form.get('webhook_url', '')
        
        elif wallet_type_enum == WalletType.CUSTOM_MANUAL:
            # Manual wallet addresses
            wallet_addresses = {}
            
            # Parse addresses from form data
            for key in request.form.keys():
                if key.startswith('address_'):
                    currency = key.replace('address_', '').upper()
                    address = request.form.get(key, '').strip()
                    if address and len(address) > 10:  # Basic validation
                        wallet_addresses[currency] = address
            
            new_wallet.wallet_addresses = wallet_addresses
        
        db.session.add(new_wallet)
        db.session.commit()
        
        from flask_babel import _
        flash(_(f"Wallet '{wallet_name}' created successfully!"), "success")
        
        # Return JSON if AJAX request
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': f"Wallet '{wallet_name}' created successfully!",
                'wallet': new_wallet.to_dict()
            }), 200
        
        return redirect(url_for("client.wallet_configure"))
    
    except Exception as e:
        db.session.rollback()
        from flask_babel import _
        error_msg = str(e)
        flash(_(f"Error creating wallet: {error_msg}"), "danger")
        
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': error_msg}), 400
        
        return redirect(url_for("client.wallet_configure"))

# Update Wallet (AJAX)
@client_bp.route("/wallet-configure/<int:wallet_id>/update", methods=["PUT", "POST"])
@login_required
@client_required
def update_wallet(wallet_id):
    """Update wallet configuration and addresses"""
    from app.models import ClientWallet, WalletStatus
    from flask import jsonify
    
    # Get client data
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        return jsonify({'success': False, 'error': 'Client not found'}), 404
    
    # Get wallet
    wallet = ClientWallet.query.filter_by(id=wallet_id, client_id=client_data.id).first()
    if not wallet:
        return jsonify({'success': False, 'error': 'Wallet not found'}), 404
    
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        # Update wallet addresses
        if 'addresses' in data:
            wallet.wallet_addresses = data['addresses']
        
        # Update single address
        if 'currency' in data and 'address' in data:
            wallet.set_address(data['currency'], data['address'])
        
        # Update wallet name
        if 'wallet_name' in data:
            wallet.wallet_name = data['wallet_name']
        
        # Update API configuration
        if 'api_key' in data:
            wallet.api_key = data['api_key']
        if 'api_secret' in data:
            wallet.api_secret = data['api_secret']
        if 'api_endpoint' in data:
            wallet.api_endpoint = data['api_endpoint']
        
        # Update status
        if 'status' in data:
            try:
                wallet.status = WalletStatus(data['status'])
            except ValueError:
                pass
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Wallet updated successfully',
            'wallet': wallet.to_dict()
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

# Delete Wallet (AJAX)
@client_bp.route("/wallet-configure/<int:wallet_id>/delete", methods=["DELETE", "POST"])
@login_required
@client_required
def delete_wallet(wallet_id):
    """Delete a wallet configuration"""
    from app.models import ClientWallet
    from flask import jsonify
    
    # Get client data
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        return jsonify({'success': False, 'error': 'Client not found'}), 404
    
    # Get wallet
    wallet = ClientWallet.query.filter_by(id=wallet_id, client_id=client_data.id).first()
    if not wallet:
        return jsonify({'success': False, 'error': 'Wallet not found'}), 404
    
    try:
        wallet_name = wallet.wallet_name
        db.session.delete(wallet)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f"Wallet '{wallet_name}' deleted successfully"
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

# Test Wallet Connection (AJAX)
@client_bp.route("/wallet-configure/<int:wallet_id>/test", methods=["POST"])
@login_required
@client_required
def test_wallet(wallet_id):
    """Test wallet configuration and connectivity"""
    from app.models import ClientWallet, WalletType
    from flask import jsonify
    
    # Get client data
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        return jsonify({'success': False, 'error': 'Client not found'}), 404
    
    # Get wallet
    wallet = ClientWallet.query.filter_by(id=wallet_id, client_id=client_data.id).first()
    if not wallet:
        return jsonify({'success': False, 'error': 'Wallet not found'}), 404
    
    try:
        # Test based on wallet type
        if wallet.wallet_type == WalletType.CUSTOM_MANUAL:
            # Validate addresses
            validation = wallet.validate_addresses()
            if not validation['valid']:
                return jsonify({
                    'success': False,
                    'error': 'Address validation failed',
                    'details': validation['errors']
                }), 400
            
            return jsonify({
                'success': True,
                'message': f"Wallet validated successfully! {validation['addresses_count']} addresses configured.",
                'details': {
                    'addresses': list(wallet.wallet_addresses.keys()) if wallet.wallet_addresses else []
                }
            }), 200
        
        elif wallet.wallet_type == WalletType.CUSTOM_API:
            # Test API connection
            if not wallet.api_key or not wallet.api_endpoint:
                return jsonify({
                    'success': False,
                    'error': 'API configuration incomplete'
                }), 400
            
            # Here you would test the actual API connection
            # For now, just validate that fields are present
            return jsonify({
                'success': True,
                'message': 'API configuration validated',
                'details': {
                    'endpoint': wallet.api_endpoint,
                    'has_api_key': bool(wallet.api_key)
                }
            }), 200
        
        else:
            return jsonify({
                'success': False,
                'error': 'Unsupported wallet type'
            }), 400
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Get Wallet Details (AJAX)
@client_bp.route("/wallet-configure/<int:wallet_id>", methods=["GET"])
@login_required
@client_required
def get_wallet(wallet_id):
    """Get wallet details including addresses"""
    from app.models import ClientWallet
    from flask import jsonify
    
    # Get client data
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        return jsonify({'success': False, 'error': 'Client not found'}), 404
    
    # Get wallet
    wallet = ClientWallet.query.filter_by(id=wallet_id, client_id=client_data.id).first()
    if not wallet:
        return jsonify({'success': False, 'error': 'Wallet not found'}), 404
    
    wallet_data = wallet.to_dict()
    wallet_data['wallet_addresses'] = wallet.wallet_addresses or {}
    
    return jsonify({
        'success': True,
        'wallet': wallet_data
    }), 200

# Alias for backward compatibility with templates
@client_bp.route("/wallets")
@login_required
@client_required  
def wallets():
    # Redirect to wallet_configure for now
    return redirect(url_for('client.wallet_configure'))


# --- Withdrawal Requests Page ---
@client_bp.route("/withdrawal-requests")
@login_required
@client_required
def withdrawal_requests():
    # Get client data properly
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))

    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    query = WithdrawalRequest.query.filter_by(client_id=client_data.id)
    if status and status != 'all':
        query = query.filter(WithdrawalRequest.status == WithdrawalStatus[status.upper()])
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(WithdrawalRequest.created_at >= start)
        except Exception:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(WithdrawalRequest.created_at < end)
        except Exception:
            pass
    query = query.order_by(WithdrawalRequest.created_at.desc())
    withdrawal_requests = query.paginate(page=page, per_page=20)

    # Status counts for stat boxes
    status_counts = {
        'ALL': WithdrawalRequest.query.filter_by(client_id=current_user.id).count(),
        'PENDING': WithdrawalRequest.query.filter_by(client_id=current_user.id, status=WithdrawalStatus.PENDING).count(),
        'APPROVED': WithdrawalRequest.query.filter_by(client_id=current_user.id, status=WithdrawalStatus.APPROVED).count(),
        'COMPLETED': WithdrawalRequest.query.filter_by(client_id=current_user.id, status=WithdrawalStatus.COMPLETED).count(),
        'REJECTED': WithdrawalRequest.query.filter_by(client_id=current_user.id, status=WithdrawalStatus.REJECTED).count(),
    }

    return render_template(
        "client/withdrawal_requests.html",
        client=current_user,
        withdrawal_requests=withdrawal_requests,
        status=status,
        status_counts=status_counts
    )

# --- Create Withdrawal Request ---
@client_bp.route("/withdrawal-requests/create", methods=["GET", "POST"])
@login_required
@client_required
def create_withdrawal_request():
    # Get client data properly
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))

    form = WithdrawalRequestForm()
    # Populate currency choices dynamically (example: USDT, BTC, ETH)
    form.currency.choices = [(c, c) for c in ["USDT", "BTC", "ETH"]]

    if form.validate_on_submit():
        req = WithdrawalRequest(
            client_id=client_data.id,
            currency=form.currency.data,
            amount=form.amount.data,
            user_wallet_address=form.user_wallet_address.data,
            memo=form.memo.data,
            note=form.note.data,
            status=WithdrawalStatus.PENDING,
            created_at=now_eest()
        )
        from app import db
        db.session.add(req)
        db.session.commit()
        
        # Create admin notification for new withdrawal request
        create_withdrawal_request_notification(req)
        
        from flask_babel import _
        flash(_("Withdrawal request submitted and pending admin approval."), "success")
        return redirect(url_for("client.withdrawal_requests"))

    return render_template(
        "client/create_withdrawal_request.html",
        form=form
    )

# --- API Keys Page ---
@client_bp.route("/api-keys", endpoint="api_keys")
@login_required
@client_required
def api_keys():
    # Get client data properly
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))
    
    # Get client API keys from database
    from app.models import ClientApiKey
    api_keys = ClientApiKey.query.filter_by(client_id=client_data.id).all()
    
    # Check if client has main API key in client table
    main_api_key = client_data.api_key if hasattr(client_data, 'api_key') else None
    
    # Get client type for permissions display
    client_type = 'flat_rate' if client_data.package and 'flat' in client_data.package.name.lower() else 'commission'
    
    # Create key stats (placeholder for now - can be enhanced with actual usage stats)
    key_stats = {}
    for key in api_keys:
        key_stats[key.id] = {
            'requests_count': 0,  # TODO: Implement actual API request tracking
            'last_used': None,    # TODO: Implement last used tracking
            'rate_limit_hits': 0  # TODO: Implement rate limit tracking
        }
    
    return render_template("client/api_keys.html", 
                         client=client_data,
                         api_keys=api_keys,
                         main_api_key=main_api_key,
                         client_type=client_type,
                         key_stats=key_stats)

# --- Create API Key ---
@client_bp.route("/api-keys/create", methods=["POST"])
@login_required
@client_required
def create_api_key():
    # Get client data properly
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))
    
    # Generate API key and secrets
    import secrets
    import hashlib
    from app.models import ClientApiKey
    
    key_name = request.form.get('name', 'Default API Key')
    api_key = f"pk_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    key_prefix = api_key[:8]
    
    # Generate secret key for signing requests
    secret_key = secrets.token_hex(32)
    
    # Generate webhook secret for webhook verification
    webhook_secret = secrets.token_hex(24)
    
    # Get client type for appropriate permissions
    client_type = 'flat_rate' if client_data.package and 'flat' in client_data.package.name.lower() else 'commission'
    
    # Default permissions based on client type
    default_permissions = []
    if client_type == 'flat_rate':
        default_permissions = [
            'flat_rate:payment:create',
            'flat_rate:payment:read', 
            'flat_rate:balance:read',
            'flat_rate:withdrawal:create',
            'flat_rate:webhook:manage'
        ]
    else:
        default_permissions = [
            'commission:payment:create',
            'commission:payment:read',
            'commission:balance:read'
        ]
    
    new_api_key = ClientApiKey(
        client_id=client_data.id,
        name=key_name,
        key=api_key,
        key_prefix=key_prefix,
        key_hash=key_hash,
        client_type=client_type,
        permissions=default_permissions,
        rate_limit=1000 if client_type == 'flat_rate' else 100,
        secret_key=secret_key,
        webhook_secret=webhook_secret
    )
    
    db.session.add(new_api_key)
    db.session.commit()
    
    # Store credentials in session for one-time display
    from flask import session
    session['new_api_key'] = api_key
    session['new_secret_key'] = secret_key
    session['new_webhook_secret'] = webhook_secret
    session['new_api_key_id'] = new_api_key.id
    
    from flask_babel import _
    flash(_(f"API Key '{key_name}' created successfully! Save your credentials now."), "success")
    
    return redirect(url_for("client.api_key_credentials", key_id=new_api_key.id))

# --- API Key Credentials (shown once after creation) ---
@client_bp.route("/api-keys/<int:key_id>/credentials", methods=["GET"])
@login_required
@client_required
def api_key_credentials(key_id):
    """Display API key credentials (shown only once after creation)"""
    from flask import session
    
    # Get client data properly
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))
    
    # Get the specific API key
    from app.models import ClientApiKey
    api_key = ClientApiKey.query.filter_by(
        id=key_id, 
        client_id=client_data.id
    ).first()
    
    if not api_key:
        from flask_babel import _
        flash(_("API Key not found"), "danger")
        return redirect(url_for("client.api_keys"))
    
    # Get credentials from session (only available right after creation)
    credentials = {
        'api_key': session.pop('new_api_key', None) if session.get('new_api_key_id') == key_id else None,
        'secret_key': session.pop('new_secret_key', None) if session.get('new_api_key_id') == key_id else None,
        'webhook_secret': session.pop('new_webhook_secret', None) if session.get('new_api_key_id') == key_id else None
    }
    
    # Clear the key ID from session
    session.pop('new_api_key_id', None)
    
    # Get base URL from config or default
    base_url = request.url_root
    
    return render_template("client/api_key_credentials.html", 
                         client=client_data,
                         api_key=api_key,
                         credentials=credentials,
                         base_url=base_url)

# --- API Key Details with all credentials ---
@client_bp.route("/api-keys/<int:key_id>/details", methods=["GET"])
@login_required
@client_required
def api_key_details(key_id):
    # Get client data properly
    client_data = None
    if hasattr(current_user, 'client') and current_user.client:
        client_data = current_user.client
    elif current_user.__class__.__name__ == 'Client':
        client_data = current_user
    
    if not client_data:
        from flask_babel import _
        flash(_("Client data not found"), "danger")
        return redirect(url_for("auth.login"))
    
    # Get the specific API key
    from app.models import ClientApiKey
    api_key = ClientApiKey.query.filter_by(
        id=key_id, 
        client_id=client_data.id
    ).first()
    
    if not api_key:
        from flask_babel import _
        flash(_("API Key not found"), "danger")
        return redirect(url_for("client.api_keys"))
    
    # Get base URL from config or default
    base_url = current_app.config.get('PAYCRYPT_BASE_URL', 'https://api.paycrypt.online/v1')
    
    # No credentials in details view (security measure)
    return render_template("client/api_key_details.html", 
                         client=client_data,
                         api_key=api_key,
                         base_url=base_url)

# --- API Documentation Page ---
@client_bp.route("/api-docs", endpoint="api_docs")
@login_required
@client_required
def api_docs():
    return render_template("client/api_docs.html")

# --- Pricing Page (stub) ---
@client_bp.route('/pricing')
def pricing():
    return render_template('pricing.html', client=current_user)
