from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.bank_gateway import (
    BankGatewayProvider, BankGatewayAccount, BankGatewayClientSite, 
    BankGatewayAPIKey, BankGatewayTransaction, BankGatewayDepositRequest
)
from app.models.client import Client
from app.utils.timezone import now_eest
from app.extensions import db
from datetime import datetime, timedelta
import uuid
import secrets

# Create blueprint for admin panel
admin_panel_bp = Blueprint('bank_admin_panel', __name__, url_prefix='/yonetim')

@admin_panel_bp.route('/')
@login_required
def dashboard():
    """Admin dashboard for bank gateway management"""
    # Statistics
    total_providers = BankGatewayProvider.query.count()
    total_accounts = BankGatewayAccount.query.count()
    total_clients = BankGatewayClientSite.query.count()
    
    # Recent transactions
    recent_transactions = BankGatewayTransaction.query.order_by(
        BankGatewayTransaction.created_at.desc()
    ).limit(20).all()
    
    # Pending transactions requiring admin attention
    pending_transactions = BankGatewayTransaction.query.filter_by(
        status='pending'
    ).count()
    
    # Revenue statistics (last 30 days)
    last_month = now_eest() - timedelta(days=30)
    monthly_revenue = db.session.query(
        db.func.sum(BankGatewayTransaction.commission_amount)
    ).filter(
        BankGatewayTransaction.created_at >= last_month,
        BankGatewayTransaction.status == 'confirmed'
    ).scalar() or 0
    
    return render_template('bank_gateway/admin/dashboard.html',
                         total_providers=total_providers,
                         total_accounts=total_accounts,
                         total_clients=total_clients,
                         recent_transactions=recent_transactions,
                         pending_transactions=pending_transactions,
                         monthly_revenue=monthly_revenue)

@admin_panel_bp.route('/providers')
@login_required
def providers():
    """Manage bank gateway providers"""
    providers = BankGatewayProvider.query.all()
    return render_template('bank_gateway/admin/providers.html', providers=providers)

@admin_panel_bp.route('/providers/add', methods=['GET', 'POST'])
@login_required
def add_provider():
    """Add new provider"""
    if request.method == 'POST':
        # Create provider
        provider = BankGatewayProvider(
            user_id=request.form['user_id'],
            name=request.form['name'],
            phone=request.form.get('phone'),
            deposit_commission=float(request.form.get('deposit_commission', 0)),
            withdraw_commission=float(request.form.get('withdraw_commission', 0))
        )
        
        db.session.add(provider)
        db.session.commit()
        
        flash('Provider added successfully!', 'success')
        return redirect(url_for('bank_admin_panel.providers'))
    
    # Get available users who can be providers
    from app.models.user import User
    available_users = User.query.filter(~User.id.in_(
        db.session.query(BankGatewayProvider.user_id)
    )).all()
    
    return render_template('bank_gateway/admin/add_provider.html', users=available_users)

@admin_panel_bp.route('/providers/<int:provider_id>/toggle_block', methods=['POST'])
@login_required
def toggle_provider_block(provider_id):
    """Block/unblock a provider"""
    provider = BankGatewayProvider.query.get_or_404(provider_id)
    provider.is_blocked = not provider.is_blocked
    db.session.commit()
    
    status = 'blocked' if provider.is_blocked else 'unblocked'
    flash(f'Provider {provider.name} has been {status}.', 'success')
    return redirect(url_for('bank_admin_panel.providers'))

@admin_panel_bp.route('/clients')
@login_required
def clients():
    """Manage bank gateway client sites"""
    client_sites = BankGatewayClientSite.query.all()
    return render_template('bank_gateway/admin/clients.html', client_sites=client_sites)

@admin_panel_bp.route('/clients/add', methods=['GET', 'POST'])
@login_required
def add_client():
    """Add new client site"""
    if request.method == 'POST':
        # Create client site
        client_site = BankGatewayClientSite(
            client_id=request.form['client_id'],
            site_name=request.form['site_name'],
            site_url=request.form['site_url'],
            callback_url=request.form.get('callback_url'),
            success_url=request.form.get('success_url'),
            fail_url=request.form.get('fail_url')
        )
        
        db.session.add(client_site)
        db.session.commit()
        
        # Generate API key
        api_key = BankGatewayAPIKey(
            client_site_id=client_site.id,
            key=secrets.token_urlsafe(32)
        )
        
        db.session.add(api_key)
        db.session.commit()
        
        flash('Client site added successfully!', 'success')
        return redirect(url_for('bank_admin_panel.clients'))
    
    # Get available clients
    clients = Client.query.all()
    return render_template('bank_gateway/admin/add_client.html', clients=clients)

@admin_panel_bp.route('/transactions')
@login_required
def transactions():
    """View all transactions"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    query = BankGatewayTransaction.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    transactions = query.order_by(
        BankGatewayTransaction.created_at.desc()
    ).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('bank_gateway/admin/transactions.html', 
                         transactions=transactions, 
                         status_filter=status_filter)

@admin_panel_bp.route('/transaction/<int:transaction_id>')
@login_required
def transaction_detail(transaction_id):
    """View transaction details"""
    transaction = BankGatewayTransaction.query.get_or_404(transaction_id)
    return render_template('bank_gateway/admin/transaction_detail.html', 
                         transaction=transaction)

@admin_panel_bp.route('/reports')
@login_required
def reports():
    """Financial reports for bank gateway"""
    # Daily statistics for last 30 days
    last_month = now_eest() - timedelta(days=30)
    
    daily_stats = db.session.query(
        db.func.date(BankGatewayTransaction.created_at).label('date'),
        db.func.count(BankGatewayTransaction.id).label('transaction_count'),
        db.func.sum(BankGatewayTransaction.amount).label('total_amount'),
        db.func.sum(BankGatewayTransaction.commission_amount).label('total_commission')
    ).filter(
        BankGatewayTransaction.created_at >= last_month,
        BankGatewayTransaction.status == 'confirmed'
    ).group_by(
        db.func.date(BankGatewayTransaction.created_at)
    ).all()
    
    # Provider performance
    provider_stats = db.session.query(
        BankGatewayProvider.name,
        db.func.count(BankGatewayTransaction.id).label('transaction_count'),
        db.func.sum(BankGatewayTransaction.amount).label('total_amount')
    ).join(BankGatewayAccount).join(BankGatewayTransaction).filter(
        BankGatewayTransaction.created_at >= last_month,
        BankGatewayTransaction.status == 'confirmed'
    ).group_by(BankGatewayProvider.id).all()
    
    return render_template('bank_gateway/admin/reports.html',
                         daily_stats=daily_stats,
                         provider_stats=provider_stats)
