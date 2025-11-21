"""
Branch Superadmin Routes
Routes for branch superadmins to manage their clients, transactions, and audit logs
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, desc, and_, or_
from datetime import datetime, timedelta
from ..utils.timezone import now_eest

from app.extensions import db
from app.decorators import branch_superadmin_required
from app.models import (
    Branch, Client, User, Payment, Withdrawal, AuditLog
)
from app.models.bank_gateway import (
    BankGatewayProvider, BankGatewayAccount, BankGatewayClientSite,
    BankGatewayTransaction, BankGatewayDepositRequest, BankGatewayWithdrawalRequest,
    BankGatewayProviderCommission
)
from app.models.enums import PaymentStatus, WithdrawalStatus
from app.models.audit import AuditLog

branch_bp = Blueprint('branch', __name__, url_prefix='/branch')

@branch_bp.route('/dashboard')
@login_required
@branch_superadmin_required
def dashboard():
    """Branch superadmin dashboard with statistics"""
    branch = current_user.managed_branch

    # Get statistics
    total_clients = branch.clients.filter_by(is_active=True).count()

    # Transaction stats for last 30 days
    thirty_days_ago = now_eest() - timedelta(days=30)

    # Deposits
    deposit_query = db.session.query(func.sum(Payment.amount)).join(Client).filter(
        Client.branch_id == branch.id,
        Payment.status == PaymentStatus.APPROVED,
        Payment.created_at >= thirty_days_ago
    )
    total_deposits = deposit_query.scalar() or 0

    # Withdrawals
    withdrawal_query = db.session.query(func.sum(Withdrawal.amount)).join(Client).filter(
        Client.branch_id == branch.id,
        Withdrawal.status == WithdrawalStatus.APPROVED,
        Withdrawal.created_at >= thirty_days_ago
    )
    total_withdrawals = withdrawal_query.scalar() or 0

    # Commission earned
    commission_earned = total_deposits * 0.035  # Assuming 3.5% commission rate

    # Recent transactions
    recent_payments = Payment.query.join(Client).filter(
        Client.branch_id == branch.id
    ).order_by(Payment.created_at.desc()).limit(10).all()

    recent_withdrawals = Withdrawal.query.join(Client).filter(
        Client.branch_id == branch.id
    ).order_by(Withdrawal.created_at.desc()).limit(10).all()

    # Combine and sort recent transactions
    recent_transactions = []
    for payment in recent_payments:
        recent_transactions.append({
            'type': 'deposit',
            'id': payment.id,
            'client': payment.client.company_name,
            'amount': payment.amount,
            'currency': payment.currency,
            'status': payment.status.value,
            'date': payment.created_at
        })

    for withdrawal in recent_withdrawals:
        recent_transactions.append({
            'type': 'withdrawal',
            'id': withdrawal.id,
            'client': withdrawal.client.company_name,
            'amount': withdrawal.amount,
            'currency': withdrawal.currency,
            'status': withdrawal.status.value,
            'date': withdrawal.created_at
        })

    recent_transactions.sort(key=lambda x: x['date'], reverse=True)
    recent_transactions = recent_transactions[:10]

    # Client activity stats
    client_stats = []
    for client in branch.clients.filter_by(is_active=True).all():
        client_deposits = db.session.query(func.sum(Payment.amount)).filter(
            Payment.client_id == client.id,
            Payment.status == PaymentStatus.APPROVED,
            Payment.created_at >= thirty_days_ago
        ).scalar() or 0

        client_stats.append({
            'name': client.company_name,
            'deposits': client_deposits,
            'transactions': Payment.query.filter(
                Payment.client_id == client.id,
                Payment.created_at >= thirty_days_ago
            ).count()
        })

    client_stats.sort(key=lambda x: x['deposits'], reverse=True)

    return render_template('branch/dashboard.html',
                         branch=branch,
                         total_clients=total_clients,
                         total_deposits=total_deposits,
                         total_withdrawals=total_withdrawals,
                         commission_earned=commission_earned,
                         recent_transactions=recent_transactions,
                         client_stats=client_stats)

@branch_bp.route('/transactions')
@login_required
@branch_superadmin_required
def transactions():
    """View all transactions for branch clients"""
    branch = current_user.managed_branch

    # Get filter parameters
    client_filter = request.args.get('client', type=int)
    type_filter = request.args.get('type')  # deposit, withdrawal
    status_filter = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    page = request.args.get('page', 1, type=int)

    # Base queries
    payments_query = Payment.query.join(Client).filter(Client.branch_id == branch.id)
    withdrawals_query = Withdrawal.query.join(Client).filter(Client.branch_id == branch.id)

    # Apply filters
    if client_filter:
        payments_query = payments_query.filter(Payment.client_id == client_filter)
        withdrawals_query = withdrawals_query.filter(Withdrawal.client_id == client_filter)

    if status_filter:
        if status_filter in [s.value for s in PaymentStatus]:
            payments_query = payments_query.filter(Payment.status == PaymentStatus(status_filter))
        if status_filter in [s.value for s in WithdrawalStatus]:
            withdrawals_query = withdrawals_query.filter(Withdrawal.status == WithdrawalStatus(status_filter))

    if date_from:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
        payments_query = payments_query.filter(Payment.created_at >= date_from_obj)
        withdrawals_query = withdrawals_query.filter(Withdrawal.created_at >= date_from_obj)

    if date_to:
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
        payments_query = payments_query.filter(Payment.created_at <= date_to_obj)
        withdrawals_query = withdrawals_query.filter(Withdrawal.created_at <= date_to_obj)

    # Get paginated results
    payments = payments_query.order_by(Payment.created_at.desc()).paginate(page=page, per_page=20)
    withdrawals = withdrawals_query.order_by(Withdrawal.created_at.desc()).paginate(page=page, per_page=20)

    # Combine transactions for display
    transactions = []

    for payment in payments.items:
        transactions.append({
            'id': payment.id,
            'type': 'deposit',
            'client': payment.client.company_name,
            'amount': payment.amount,
            'currency': payment.currency,
            'status': payment.status.value,
            'date': payment.created_at,
            'reference': payment.reference_number,
            'can_approve': payment.status == PaymentStatus.PENDING
        })

    for withdrawal in withdrawals.items:
        transactions.append({
            'id': withdrawal.id,
            'type': 'withdrawal',
            'client': withdrawal.client.company_name,
            'amount': withdrawal.amount,
            'currency': withdrawal.currency,
            'status': withdrawal.status.value,
            'date': withdrawal.created_at,
            'reference': withdrawal.reference_number,
            'can_approve': withdrawal.status == WithdrawalStatus.PENDING
        })

    # Sort combined transactions
    transactions.sort(key=lambda x: x['date'], reverse=True)

    # Get clients for filter dropdown
    clients = branch.clients.filter_by(is_active=True).all()

    return render_template('branch/transactions.html',
                         transactions=transactions,
                         clients=clients,
                         client_filter=client_filter,
                         type_filter=type_filter,
                         status_filter=status_filter,
                         date_from=date_from,
                         date_to=date_to,
                         payments=payments,
                         withdrawals=withdrawals)

@branch_bp.route('/approve-deposit/<int:payment_id>', methods=['POST'])
@login_required
@branch_superadmin_required
def approve_deposit(payment_id):
    """Approve a pending deposit"""
    branch = current_user.managed_branch

    payment = Payment.query.join(Client).filter(
        Payment.id == payment_id,
        Client.branch_id == branch.id
    ).first_or_404()

    if payment.status != PaymentStatus.PENDING:
        flash('Payment is not in pending status', 'warning')
        return redirect(url_for('branch.transactions'))

    # Update payment status
    old_status = payment.status
    payment.status = PaymentStatus.APPROVED
    payment.approved_at = now_eest()
    payment.approved_by = current_user.id

    db.session.commit()

    # Log audit action
    AuditLog.log_action(
        branch_id=branch.id,
        action='approve_deposit',
        details=f'Approved deposit #{payment.id} for {payment.amount} {payment.currency}',
        admin_id=current_user.id,
        client_id=payment.client_id,
        request=request
    )

    flash(f'Deposit #{payment.id} approved successfully', 'success')
    return redirect(url_for('branch.transactions'))

@branch_bp.route('/reject-deposit/<int:payment_id>', methods=['POST'])
@login_required
@branch_superadmin_required
def reject_deposit(payment_id):
    """Reject a pending deposit"""
    branch = current_user.managed_branch

    payment = Payment.query.join(Client).filter(
        Payment.id == payment_id,
        Client.branch_id == branch.id
    ).first_or_404()

    if payment.status != PaymentStatus.PENDING:
        flash('Payment is not in pending status', 'warning')
        return redirect(url_for('branch.transactions'))

    # Update payment status
    old_status = payment.status
    payment.status = PaymentStatus.REJECTED
    payment.rejected_at = now_eest()
    payment.rejected_by = current_user.id

    db.session.commit()

    # Log audit action
    AuditLog.log_action(
        branch_id=branch.id,
        action='reject_deposit',
        details=f'Rejected deposit #{payment.id} for {payment.amount} {payment.currency}',
        admin_id=current_user.id,
        client_id=payment.client_id,
        request=request
    )

    flash(f'Deposit #{payment.id} rejected', 'info')
    return redirect(url_for('branch.transactions'))

@branch_bp.route('/approve-withdrawal/<int:withdrawal_id>', methods=['POST'])
@login_required
@branch_superadmin_required
def approve_withdrawal(withdrawal_id):
    """Approve a pending withdrawal"""
    branch = current_user.managed_branch

    withdrawal = Withdrawal.query.join(Client).filter(
        Withdrawal.id == withdrawal_id,
        Client.branch_id == branch.id
    ).first_or_404()

    if withdrawal.status != WithdrawalStatus.PENDING:
        flash('Withdrawal is not in pending status', 'warning')
        return redirect(url_for('branch.transactions'))

    # Update withdrawal status
    old_status = withdrawal.status
    withdrawal.status = WithdrawalStatus.APPROVED
    withdrawal.approved_at = now_eest()
    withdrawal.approved_by = current_user.id

    db.session.commit()

    # Log audit action
    AuditLog.log_action(
        branch_id=branch.id,
        action='approve_withdrawal',
        details=f'Approved withdrawal #{withdrawal.id} for {withdrawal.amount} {withdrawal.currency}',
        admin_id=current_user.id,
        client_id=withdrawal.client_id,
        request=request
    )

    flash(f'Withdrawal #{withdrawal.id} approved successfully', 'success')
    return redirect(url_for('branch.transactions'))

@branch_bp.route('/reject-withdrawal/<int:withdrawal_id>', methods=['POST'])
@login_required
@branch_superadmin_required
def reject_withdrawal(withdrawal_id):
    """Reject a pending withdrawal"""
    branch = current_user.managed_branch

    withdrawal = Withdrawal.query.join(Client).filter(
        Withdrawal.id == withdrawal_id,
        Client.branch_id == branch.id
    ).first_or_404()

    if withdrawal.status != WithdrawalStatus.PENDING:
        flash('Withdrawal is not in pending status', 'warning')
        return redirect(url_for('branch.transactions'))

    # Update withdrawal status
    old_status = withdrawal.status
    withdrawal.status = WithdrawalStatus.REJECTED
    withdrawal.rejected_at = now_eest()
    withdrawal.rejected_by = current_user.id

    db.session.commit()

    # Log audit action
    AuditLog.log_action(
        branch_id=branch.id,
        action='reject_withdrawal',
        details=f'Rejected withdrawal #{withdrawal.id} for {withdrawal.amount} {withdrawal.currency}',
        admin_id=current_user.id,
        client_id=withdrawal.client_id,
        request=request
    )

    flash(f'Withdrawal #{withdrawal.id} rejected', 'info')
    return redirect(url_for('branch.transactions'))

@branch_bp.route('/audit-logs')
@login_required
@branch_superadmin_required
def audit_logs():
    """View audit logs for the branch"""
    branch = current_user.managed_branch

    # Get filter parameters
    admin_filter = request.args.get('admin', type=int)
    client_filter = request.args.get('client', type=int)
    action_filter = request.args.get('action')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    page = request.args.get('page', 1, type=int)

    # Base query
    logs_query = AuditLog.query.filter(AuditLog.branch_id == branch.id)

    # Apply filters
    if admin_filter:
        logs_query = logs_query.filter(AuditLog.admin_id == admin_filter)
    if client_filter:
        logs_query = logs_query.filter(AuditLog.client_id == client_filter)
    if action_filter:
        logs_query = logs_query.filter(AuditLog.action == action_filter)
    if date_from:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
        logs_query = logs_query.filter(AuditLog.timestamp >= date_from_obj)
    if date_to:
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
        logs_query = logs_query.filter(AuditLog.timestamp <= date_to_obj)

    # Get paginated results
    logs = logs_query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=50)

    # Get filter options
    admins = branch.admins.filter_by(is_active=True).all()
    clients = branch.clients.filter_by(is_active=True).all()
    actions = db.session.query(AuditLog.action).filter(AuditLog.branch_id == branch.id).distinct().all()
    actions = [action[0] for action in actions]

    return render_template('branch/audit_logs.html',
                         logs=logs,
                         admins=admins,
                         clients=clients,
                         actions=actions,
                         admin_filter=admin_filter,
                         client_filter=client_filter,
                         action_filter=action_filter,
                         date_from=date_from,
                         date_to=date_to)

@branch_bp.route('/clients')
@login_required
@branch_superadmin_required
def clients():
    """View all clients under this branch"""
    branch = current_user.managed_branch
    clients = branch.clients.order_by(Client.created_at.desc()).all()

    return render_template('branch/clients.html', clients=clients)

@branch_bp.route('/create-client', methods=['GET', 'POST'])
@login_required
@branch_superadmin_required
def create_client_wizard():
    """Multi-step wizard for creating clients with API keys and wallet setup"""
    from app.forms import ClientWizardForm
    from app.models import ApiKey, ClientWallet
    import secrets

    branch = current_user.managed_branch
    form = ClientWizardForm()

    if form.validate_on_submit():
        try:
            # Create the client
            client = Client(
                company_name=form.company_name.data,
                contact_email=form.contact_email.data,
                contact_phone=form.contact_phone.data,
                website=form.website.data,
                address=form.address.data,
                city=form.city.data,
                country=form.country.data,
                branch=branch,
                is_active=True
            )

            # Set password for client login
            client.set_password(form.password.data)

            db.session.add(client)
            db.session.flush()  # Get client ID

            # Create API keys
            api_key = ApiKey(
                client_id=client.id,
                name='Primary API Key',
                key=secrets.token_urlsafe(32),
                secret=secrets.token_urlsafe(32),
                is_active=True,
                permissions=['deposit', 'withdraw', 'status']
            )
            db.session.add(api_key)

            # Create wallet configurations for selected coins
            selected_coins = form.coins.data or []
            for coin_symbol in selected_coins:
                wallet = ClientWallet(
                    client_id=client.id,
                    coin_symbol=coin_symbol.upper(),
                    wallet_address=form.wallet_addresses.get(coin_symbol, ''),
                    is_active=True
                )
                db.session.add(wallet)

            db.session.commit()

            # Log audit action
            AuditLog.log_action(
                branch_id=branch.id,
                action='create_client',
                details=f'Created client {client.company_name} with API key and {len(selected_coins)} wallet configurations',
                admin_id=current_user.id,
                client_id=client.id,
                request=request
            )

            flash(f'Client {client.company_name} created successfully with API access and wallet configurations!', 'success')
            return redirect(url_for('branch.clients'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating client: {str(e)}', 'danger')

    return render_template('branch/create_client_wizard.html', form=form)


# --- Bank Gateway Routes ---

@branch_bp.route('/bank-gateway')
@login_required
@branch_superadmin_required
def bank_gateway_dashboard():
    """Bank gateway dashboard for branch - shows data for branch's clients only"""
    branch = current_user.managed_branch
    
    # Get all client IDs under this branch
    client_ids = [client.id for client in branch.clients.all()]
    
    # Get all client sites for these clients
    client_sites = BankGatewayClientSite.query.filter(
        BankGatewayClientSite.client_id.in_(client_ids)
    ).all() if client_ids else []
    
    site_ids = [site.id for site in client_sites]
    
    # Statistics
    total_sites = len(client_sites)
    
    # Transactions
    total_transactions = BankGatewayTransaction.query.filter(
        BankGatewayTransaction.client_site_id.in_(site_ids)
    ).count() if site_ids else 0
    
    pending_transactions = BankGatewayTransaction.query.filter(
        BankGatewayTransaction.client_site_id.in_(site_ids),
        BankGatewayTransaction.status == 'pending'
    ).count() if site_ids else 0
    
    # Deposit requests
    pending_deposits = BankGatewayDepositRequest.query.filter(
        BankGatewayDepositRequest.client_site_id.in_(site_ids),
        BankGatewayDepositRequest.status == 'pending'
    ).count() if site_ids else 0
    
    # Withdrawal requests
    pending_withdrawals = BankGatewayWithdrawalRequest.query.filter(
        BankGatewayWithdrawalRequest.client_site_id.in_(site_ids),
        BankGatewayWithdrawalRequest.status == 'pending'
    ).count() if site_ids else 0
    
    # Monthly revenue (last 30 days)
    thirty_days_ago = now_eest() - timedelta(days=30)
    monthly_revenue = db.session.query(
        func.sum(BankGatewayTransaction.amount)
    ).filter(
        BankGatewayTransaction.client_site_id.in_(site_ids),
        BankGatewayTransaction.status == 'confirmed',
        BankGatewayTransaction.created_at >= thirty_days_ago
    ).scalar() or 0 if site_ids else 0
    
    # Recent transactions
    recent_transactions = BankGatewayTransaction.query.filter(
        BankGatewayTransaction.client_site_id.in_(site_ids)
    ).order_by(BankGatewayTransaction.created_at.desc()).limit(10).all() if site_ids else []
    
    return render_template('branch/bank_gateway/dashboard.html',
                         branch=branch,
                         total_sites=total_sites,
                         total_transactions=total_transactions,
                         pending_transactions=pending_transactions,
                         pending_deposits=pending_deposits,
                         pending_withdrawals=pending_withdrawals,
                         monthly_revenue=monthly_revenue,
                         recent_transactions=recent_transactions)


@branch_bp.route('/bank-gateway/transactions')
@login_required
@branch_superadmin_required
def bank_gateway_transactions():
    """View all bank gateway transactions for branch's clients"""
    branch = current_user.managed_branch
    
    # Get all client IDs under this branch
    client_ids = [client.id for client in branch.clients.all()]
    
    # Get all client sites for these clients
    client_sites = BankGatewayClientSite.query.filter(
        BankGatewayClientSite.client_id.in_(client_ids)
    ).all() if client_ids else []
    
    site_ids = [site.id for site in client_sites]
    
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    client_filter = request.args.get('client_id', type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query
    query = BankGatewayTransaction.query.filter(
        BankGatewayTransaction.client_site_id.in_(site_ids)
    ) if site_ids else BankGatewayTransaction.query.filter(False)
    
    # Apply filters
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if client_filter and client_filter in client_ids:
        client_site_ids = [site.id for site in client_sites if site.client_id == client_filter]
        query = query.filter(BankGatewayTransaction.client_site_id.in_(client_site_ids))
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(BankGatewayTransaction.created_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(BankGatewayTransaction.created_at < date_to_obj)
        except ValueError:
            pass
    
    # Order and paginate
    query = query.order_by(BankGatewayTransaction.created_at.desc())
    transactions = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Statistics
    total_amount = db.session.query(func.sum(BankGatewayTransaction.amount)).filter(
        BankGatewayTransaction.client_site_id.in_(site_ids),
        BankGatewayTransaction.status == 'confirmed'
    ).scalar() or 0 if site_ids else 0
    
    return render_template('branch/bank_gateway/transactions.html',
                         branch=branch,
                         transactions=transactions,
                         clients=branch.clients.all(),
                         status_filter=status_filter,
                         client_filter=client_filter,
                         date_from=date_from,
                         date_to=date_to,
                         total_amount=total_amount)


@branch_bp.route('/bank-gateway/deposit-requests')
@login_required
@branch_superadmin_required
def bank_gateway_deposits():
    """View deposit requests for branch's clients"""
    branch = current_user.managed_branch
    
    # Get all client IDs under this branch
    client_ids = [client.id for client in branch.clients.all()]
    
    # Get all client sites for these clients
    client_sites = BankGatewayClientSite.query.filter(
        BankGatewayClientSite.client_id.in_(client_ids)
    ).all() if client_ids else []
    
    site_ids = [site.id for site in client_sites]
    
    # Get filter parameters
    status_filter = request.args.get('status', 'pending')
    client_filter = request.args.get('client_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query
    query = BankGatewayDepositRequest.query.filter(
        BankGatewayDepositRequest.client_site_id.in_(site_ids)
    ) if site_ids else BankGatewayDepositRequest.query.filter(False)
    
    # Apply filters
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if client_filter and client_filter in client_ids:
        client_site_ids = [site.id for site in client_sites if site.client_id == client_filter]
        query = query.filter(BankGatewayDepositRequest.client_site_id.in_(client_site_ids))
    
    # Order and paginate
    query = query.order_by(BankGatewayDepositRequest.created_at.desc())
    deposits = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Statistics
    pending_count = BankGatewayDepositRequest.query.filter(
        BankGatewayDepositRequest.client_site_id.in_(site_ids),
        BankGatewayDepositRequest.status == 'pending'
    ).count() if site_ids else 0
    
    approved_count = BankGatewayDepositRequest.query.filter(
        BankGatewayDepositRequest.client_site_id.in_(site_ids),
        BankGatewayDepositRequest.status == 'approved'
    ).count() if site_ids else 0
    
    return render_template('branch/bank_gateway/deposits.html',
                         branch=branch,
                         deposits=deposits,
                         clients=branch.clients.all(),
                         status_filter=status_filter,
                         client_filter=client_filter,
                         pending_count=pending_count,
                         approved_count=approved_count)


@branch_bp.route('/bank-gateway/withdrawal-requests')
@login_required
@branch_superadmin_required
def bank_gateway_withdrawals():
    """View withdrawal requests for branch's clients"""
    branch = current_user.managed_branch
    
    # Get all client IDs under this branch
    client_ids = [client.id for client in branch.clients.all()]
    
    # Get all client sites for these clients
    client_sites = BankGatewayClientSite.query.filter(
        BankGatewayClientSite.client_id.in_(client_ids)
    ).all() if client_ids else []
    
    site_ids = [site.id for site in client_sites]
    
    # Get filter parameters
    status_filter = request.args.get('status', 'pending')
    client_filter = request.args.get('client_id', type=int)
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query
    query = BankGatewayWithdrawalRequest.query.filter(
        BankGatewayWithdrawalRequest.client_site_id.in_(site_ids)
    ) if site_ids else BankGatewayWithdrawalRequest.query.filter(False)
    
    # Apply filters
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if client_filter and client_filter in client_ids:
        client_site_ids = [site.id for site in client_sites if site.client_id == client_filter]
        query = query.filter(BankGatewayWithdrawalRequest.client_site_id.in_(client_site_ids))
    
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            or_(
                BankGatewayWithdrawalRequest.user_name.ilike(search_term),
                BankGatewayWithdrawalRequest.user_surname.ilike(search_term),
                BankGatewayWithdrawalRequest.iban.ilike(search_term),
                BankGatewayWithdrawalRequest.reference_code.ilike(search_term)
            )
        )
    
    # Order and paginate
    query = query.order_by(BankGatewayWithdrawalRequest.created_at.desc())
    withdrawals = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Statistics
    pending_count = BankGatewayWithdrawalRequest.query.filter(
        BankGatewayWithdrawalRequest.client_site_id.in_(site_ids),
        BankGatewayWithdrawalRequest.status == 'pending'
    ).count() if site_ids else 0
    
    approved_count = BankGatewayWithdrawalRequest.query.filter(
        BankGatewayWithdrawalRequest.client_site_id.in_(site_ids),
        BankGatewayWithdrawalRequest.status == 'approved'
    ).count() if site_ids else 0
    
    pending_amount = db.session.query(func.sum(BankGatewayWithdrawalRequest.amount)).filter(
        BankGatewayWithdrawalRequest.client_site_id.in_(site_ids),
        BankGatewayWithdrawalRequest.status == 'pending'
    ).scalar() or 0 if site_ids else 0
    
    return render_template('branch/bank_gateway/withdrawals.html',
                         branch=branch,
                         withdrawals=withdrawals,
                         clients=branch.clients.all(),
                         status_filter=status_filter,
                         client_filter=client_filter,
                         search=search,
                         pending_count=pending_count,
                         approved_count=approved_count,
                         pending_amount=pending_amount)


@branch_bp.route('/bank-gateway/withdrawal-request/<int:request_id>')
@login_required
@branch_superadmin_required
def bank_gateway_withdrawal_detail(request_id):
    """View withdrawal request detail - read only for branch"""
    branch = current_user.managed_branch
    
    # Get all client IDs under this branch
    client_ids = [client.id for client in branch.clients.all()]
    
    # Get all client sites for these clients
    client_sites = BankGatewayClientSite.query.filter(
        BankGatewayClientSite.client_id.in_(client_ids)
    ).all() if client_ids else []
    
    site_ids = [site.id for site in client_sites]
    
    # Get withdrawal request - ensure it belongs to this branch
    withdrawal = BankGatewayWithdrawalRequest.query.filter(
        BankGatewayWithdrawalRequest.id == request_id,
        BankGatewayWithdrawalRequest.client_site_id.in_(site_ids)
    ).first_or_404() if site_ids else None
    
    if not withdrawal:
        flash('Withdrawal request not found or access denied', 'danger')
        return redirect(url_for('branch.bank_gateway_withdrawals'))
    
    return render_template('branch/bank_gateway/withdrawal_detail.html',
                         branch=branch,
                         withdrawal=withdrawal)


@branch_bp.route('/bank-gateway/reports')
@login_required
@branch_superadmin_required
def bank_gateway_reports():
    """Financial reports for branch's bank gateway activity"""
    branch = current_user.managed_branch
    
    # Get all client IDs under this branch
    client_ids = [client.id for client in branch.clients.all()]
    
    # Get all client sites for these clients
    client_sites = BankGatewayClientSite.query.filter(
        BankGatewayClientSite.client_id.in_(client_ids)
    ).all() if client_ids else []
    
    site_ids = [site.id for site in client_sites]
    
    # Date range (default last 30 days)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    if not date_from:
        date_from_obj = now_eest() - timedelta(days=30)
    else:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
        except ValueError:
            date_from_obj = now_eest() - timedelta(days=30)
    
    if not date_to:
        date_to_obj = now_eest()
    else:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        except ValueError:
            date_to_obj = now_eest()
    
    # Daily statistics
    daily_stats = []
    if site_ids:
        daily_data = db.session.query(
            func.date(BankGatewayTransaction.created_at).label('date'),
            func.count(BankGatewayTransaction.id).label('count'),
            func.sum(BankGatewayTransaction.amount).label('total_amount'),
            func.sum(BankGatewayTransaction.commission_amount).label('total_commission')
        ).filter(
            BankGatewayTransaction.client_site_id.in_(site_ids),
            BankGatewayTransaction.created_at >= date_from_obj,
            BankGatewayTransaction.created_at < date_to_obj
        ).group_by(func.date(BankGatewayTransaction.created_at)).all()
        
        daily_stats = [{
            'date': row.date.strftime('%Y-%m-%d'),
            'count': row.count,
            'total_amount': float(row.total_amount) if row.total_amount else 0,
            'total_commission': float(row.total_commission) if row.total_commission else 0
        } for row in daily_data]
    
    # Summary statistics
    total_transactions = BankGatewayTransaction.query.filter(
        BankGatewayTransaction.client_site_id.in_(site_ids),
        BankGatewayTransaction.created_at >= date_from_obj,
        BankGatewayTransaction.created_at < date_to_obj
    ).count() if site_ids else 0
    
    total_volume = db.session.query(func.sum(BankGatewayTransaction.amount)).filter(
        BankGatewayTransaction.client_site_id.in_(site_ids),
        BankGatewayTransaction.status == 'confirmed',
        BankGatewayTransaction.created_at >= date_from_obj,
        BankGatewayTransaction.created_at < date_to_obj
    ).scalar() or 0 if site_ids else 0
    
    total_commission = db.session.query(func.sum(BankGatewayTransaction.commission_amount)).filter(
        BankGatewayTransaction.client_site_id.in_(site_ids),
        BankGatewayTransaction.status == 'confirmed',
        BankGatewayTransaction.created_at >= date_from_obj,
        BankGatewayTransaction.created_at < date_to_obj
    ).scalar() or 0 if site_ids else 0
    
    # Withdrawal statistics
    total_withdrawals = BankGatewayWithdrawalRequest.query.filter(
        BankGatewayWithdrawalRequest.client_site_id.in_(site_ids),
        BankGatewayWithdrawalRequest.created_at >= date_from_obj,
        BankGatewayWithdrawalRequest.created_at < date_to_obj
    ).count() if site_ids else 0
    
    withdrawal_volume = db.session.query(func.sum(BankGatewayWithdrawalRequest.amount)).filter(
        BankGatewayWithdrawalRequest.client_site_id.in_(site_ids),
        BankGatewayWithdrawalRequest.status.in_(['approved', 'completed']),
        BankGatewayWithdrawalRequest.created_at >= date_from_obj,
        BankGatewayWithdrawalRequest.created_at < date_to_obj
    ).scalar() or 0 if site_ids else 0
    
    stats = {
        'total_transactions': total_transactions,
        'total_volume': total_volume,
        'total_commission': total_commission,
        'total_withdrawals': total_withdrawals,
        'withdrawal_volume': withdrawal_volume
    }
    
    return render_template('branch/bank_gateway/reports.html',
                         branch=branch,
                         daily_stats=daily_stats,
                         stats=stats,
                         date_from=date_from_obj.strftime('%Y-%m-%d'),
                         date_to=date_to_obj.strftime('%Y-%m-%d'))