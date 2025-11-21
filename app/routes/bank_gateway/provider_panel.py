from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user, login_user
from app.models.bank_gateway import (
    BankGatewayProvider, BankGatewayAccount, BankGatewayClientSite, 
    BankGatewayAPIKey, BankGatewayTransaction, BankGatewayDepositRequest
)
from app.models import User
from app.utils.timezone import now_eest
from app.extensions import db
from datetime import datetime, timedelta
import uuid

# Create blueprint for provider panel
provider_panel_bp = Blueprint('provider_panel', __name__, url_prefix='/teminci')

@provider_panel_bp.route('/login', methods=['GET', 'POST'])
def provider_login():
    """Provider login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return render_template('bank_gateway/provider/login.html')
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            # Check if user has a provider profile
            provider = BankGatewayProvider.query.filter_by(user_id=user.id).first()
            
            if provider:
                if provider.is_blocked:
                    flash('Your provider account is blocked. Please contact administrator.', 'error')
                    return render_template('bank_gateway/provider/login.html')
                
                # Login the user
                login_user(user, remember=False)
                
                # Redirect to provider dashboard
                next_url = request.args.get('next')
                if next_url and next_url.startswith('/teminci'):
                    return redirect(next_url)
                else:
                    return redirect(url_for('provider_panel.dashboard'))
            else:
                flash('You do not have provider access. Please contact administrator.', 'error')
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('bank_gateway/provider/login.html')

@provider_panel_bp.route('/')
@login_required
def dashboard():
    """Provider dashboard showing overview of bank accounts and transactions"""
    provider = BankGatewayProvider.query.filter_by(user_id=current_user.id).first()
    
    if not provider:
        flash('Provider profile not found. Please contact administrator.', 'error')
        return redirect(url_for('main.index'))
    
    # Get provider's bank accounts
    accounts = provider.bank_accounts.filter_by(is_active=True).all()
    
    # Get recent transactions
    recent_transactions = BankGatewayTransaction.query.join(BankGatewayAccount).filter(
        BankGatewayAccount.provider_id == provider.id
    ).order_by(BankGatewayTransaction.created_at.desc()).limit(10).all()
    
    # Calculate statistics
    total_accounts = len(accounts)
    total_balance = sum(account.available_balance for account in accounts)
    pending_transactions = BankGatewayTransaction.query.join(BankGatewayAccount).filter(
        BankGatewayAccount.provider_id == provider.id,
        BankGatewayTransaction.status == 'pending'
    ).count()
    
    return render_template('bank_gateway/provider/dashboard.html',
                         provider=provider,
                         accounts=accounts,
                         recent_transactions=recent_transactions,
                         total_accounts=total_accounts,
                         total_balance=total_balance,
                         pending_transactions=pending_transactions)

@provider_panel_bp.route('/accounts')
@login_required
def accounts():
    """Manage bank accounts"""
    provider = BankGatewayProvider.query.filter_by(user_id=current_user.id).first()
    
    if not provider:
        flash('Provider profile not found.', 'error')
        return redirect(url_for('main.index'))
    
    accounts = provider.bank_accounts.all()
    return render_template('bank_gateway/provider/accounts.html', 
                         provider=provider, accounts=accounts)

@provider_panel_bp.route('/accounts/add', methods=['GET', 'POST'])
@login_required
def add_account():
    """Add new bank account"""
    provider = BankGatewayProvider.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        account = BankGatewayAccount(
            provider_id=provider.id,
            bank_name=request.form['bank_name'],
            account_holder=request.form['account_holder'],
            iban=request.form['iban'],
            account_limit=float(request.form['account_limit'])
        )
        
        db.session.add(account)
        db.session.commit()
        
        flash('Bank account added successfully!', 'success')
        return redirect(url_for('provider_panel.accounts'))
    
    return render_template('bank_gateway/provider/add_account.html', provider=provider)

@provider_panel_bp.route('/transactions')
@login_required
def transactions():
    """View and manage transactions"""
    provider = BankGatewayProvider.query.filter_by(user_id=current_user.id).first()
    
    # Get transactions for provider's accounts
    transactions = BankGatewayTransaction.query.join(BankGatewayAccount).filter(
        BankGatewayAccount.provider_id == provider.id
    ).order_by(BankGatewayTransaction.created_at.desc()).all()
    
    return render_template('bank_gateway/provider/transactions.html',
                         provider=provider,
                         transactions=transactions)

@provider_panel_bp.route('/transaction/<int:transaction_id>/confirm', methods=['POST'])
@login_required
def confirm_transaction(transaction_id):
    """Confirm a transaction"""
    provider = BankGatewayProvider.query.filter_by(user_id=current_user.id).first()
    
    transaction = BankGatewayTransaction.query.join(BankGatewayAccount).filter(
        BankGatewayTransaction.id == transaction_id,
        BankGatewayAccount.provider_id == provider.id
    ).first()
    
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    if transaction.status != 'pending':
        return jsonify({'error': 'Transaction already processed'}), 400
    
    transaction.status = 'confirmed'
    transaction.confirmed_at = now_eest()
    db.session.commit()
    
    flash('Transaction confirmed successfully!', 'success')
    return jsonify({'success': True})

@provider_panel_bp.route('/transaction/<int:transaction_id>/reject', methods=['POST'])
@login_required
def reject_transaction(transaction_id):
    """Reject a transaction"""
    provider = BankGatewayProvider.query.filter_by(user_id=current_user.id).first()
    
    transaction = BankGatewayTransaction.query.join(BankGatewayAccount).filter(
        BankGatewayTransaction.id == transaction_id,
        BankGatewayAccount.provider_id == provider.id
    ).first()
    
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    if transaction.status != 'pending':
        return jsonify({'error': 'Transaction already processed'}), 400
    
    transaction.status = 'rejected'
    transaction.notes = request.json.get('reason', 'Rejected by provider')
    db.session.commit()
    
    flash('Transaction rejected.', 'info')
    return jsonify({'success': True})
