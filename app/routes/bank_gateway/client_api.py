from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app.models.bank_gateway import (
    BankGatewayProvider, BankGatewayAccount, BankGatewayClientSite, 
    BankGatewayAPIKey, BankGatewayTransaction, BankGatewayDepositRequest
)
from app.utils.timezone import now_eest
from app.extensions import db
from datetime import datetime, timedelta
import uuid
import hashlib
import hmac

# Create blueprint for client API
client_api_bp = Blueprint('bank_client_api', __name__, url_prefix='/bank-api')

def verify_api_key(api_key):
    """Verify API key and return client site"""
    api_key_obj = BankGatewayAPIKey.query.filter_by(key=api_key).first()
    if api_key_obj and api_key_obj.client_site.is_active:
        return api_key_obj.client_site
    return None

def verify_signature(data, signature, api_key):
    """Verify request signature for security"""
    # Create signature using HMAC-SHA256
    computed_signature = hmac.new(
        api_key.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, computed_signature)

@client_api_bp.route('/deposit/request', methods=['POST'])
def request_deposit():
    """API endpoint for requesting a deposit"""
    try:
        # Verify API key
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        client_site = verify_api_key(api_key)
        if not client_site:
            return jsonify({'error': 'Invalid API key'}), 401
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['amount', 'currency', 'user_name', 'user_email']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Find available bank account with sufficient capacity
        amount = float(data['amount'])
        available_account = None
        
        for provider in BankGatewayProvider.query.filter_by(is_blocked=False).all():
            for account in provider.bank_accounts.filter_by(is_active=True).all():
                if account.available_balance >= amount:
                    available_account = account
                    break
            if available_account:
                break
        
        if not available_account:
            return jsonify({'error': 'No available account for this amount'}), 503
        
        # Create transaction
        reference_code = f"DEP_{uuid.uuid4().hex[:12].upper()}"
        
        transaction = BankGatewayTransaction(
            client_site_id=client_site.id,
            bank_account_id=available_account.id,
            provider_id=available_account.provider_id,
            transaction_type='deposit',
            amount=amount,
            currency=data['currency'],
            reference_code=reference_code,
            user_name=data['user_name'],
            user_email=data['user_email'],
            user_phone=data.get('user_phone'),
            expires_at=now_eest() + timedelta(hours=24),
            callback_data=data.get('callback_data', {})
        )
        
        # Calculate commissions
        commission_rate = client_site.client.deposit_commission / 100
        provider_commission_rate = available_account.provider.deposit_commission / 100
        
        transaction.commission_amount = amount * commission_rate
        transaction.provider_commission = amount * provider_commission_rate
        
        db.session.add(transaction)
        db.session.commit()
        
        # Create deposit request
        deposit_request = BankGatewayDepositRequest(
            transaction_id=transaction.id,
            bank_account_id=available_account.id
        )
        
        db.session.add(deposit_request)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'transaction_id': transaction.id,
            'reference_code': reference_code,
            'bank_details': {
                'bank_name': available_account.bank_name,
                'account_holder': available_account.account_holder,
                'iban': available_account.iban
            },
            'amount': amount,
            'currency': data['currency'],
            'expires_at': transaction.expires_at.isoformat(),
            'deposit_url': url_for('bank_client_api.deposit_form', 
                                 reference_code=reference_code, _external=True)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@client_api_bp.route('/deposit/<reference_code>')
def deposit_form(reference_code):
    """Public deposit form for users"""
    transaction = BankGatewayTransaction.query.filter_by(
        reference_code=reference_code
    ).first()
    
    if not transaction:
        return render_template('bank_gateway/client/error.html', 
                             error='Transaction not found'), 404
    
    if transaction.status != 'pending':
        return render_template('bank_gateway/client/error.html',
                             error='Transaction already processed'), 400
    
    if transaction.expires_at and transaction.expires_at < now_eest():
        transaction.status = 'expired'
        db.session.commit()
        return render_template('bank_gateway/client/error.html',
                             error='Transaction expired'), 400
    
    return render_template('bank_gateway/client/deposit_form.html', 
                         transaction=transaction)

@client_api_bp.route('/deposit/<reference_code>/upload', methods=['POST'])
def upload_receipt(reference_code):
    """Upload payment receipt"""
    transaction = BankGatewayTransaction.query.filter_by(
        reference_code=reference_code
    ).first()
    
    if not transaction or transaction.status != 'pending':
        return jsonify({'error': 'Invalid transaction'}), 400
    
    # Handle file upload (simplified - you'd want proper file handling)
    if 'receipt' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['receipt']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save file and update deposit request
    # (In production, you'd save to cloud storage)
    deposit_request = transaction.deposit_request
    deposit_request.sender_name = request.form.get('sender_name')
    deposit_request.sender_iban = request.form.get('sender_iban')
    deposit_request.receipt_image = f"receipt_{reference_code}_{file.filename}"
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Receipt uploaded successfully'})

@client_api_bp.route('/transaction/status/<reference_code>')
def transaction_status(reference_code):
    """Check transaction status"""
    api_key = request.headers.get('X-API-Key')
    if api_key:
        client_site = verify_api_key(api_key)
        if not client_site:
            return jsonify({'error': 'Invalid API key'}), 401
    
    transaction = BankGatewayTransaction.query.filter_by(
        reference_code=reference_code
    ).first()
    
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    # If API key provided, verify it belongs to the transaction's client
    if api_key and transaction.client_site_id != client_site.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    response_data = {
        'reference_code': reference_code,
        'status': transaction.status,
        'amount': float(transaction.amount),
        'currency': transaction.currency,
        'created_at': transaction.created_at.isoformat()
    }
    
    if transaction.confirmed_at:
        response_data['confirmed_at'] = transaction.confirmed_at.isoformat()
    
    return jsonify(response_data)

@client_api_bp.route('/withdraw/request', methods=['POST'])
def request_withdrawal():
    """API endpoint for requesting a withdrawal"""
    try:
        # Verify API key
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        client_site = verify_api_key(api_key)
        if not client_site:
            return jsonify({'error': 'Invalid API key'}), 401
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['amount', 'currency', 'user_name', 'user_iban']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create withdrawal transaction
        reference_code = f"WTH_{uuid.uuid4().hex[:12].upper()}"
        amount = float(data['amount'])
        
        transaction = BankGatewayTransaction(
            client_site_id=client_site.id,
            transaction_type='withdraw',
            amount=amount,
            currency=data['currency'],
            reference_code=reference_code,
            user_name=data['user_name'],
            user_email=data.get('user_email'),
            user_phone=data.get('user_phone'),
            callback_data=data.get('callback_data', {}),
            notes=f"Withdraw to IBAN: {data['user_iban']}"
        )
        
        # Calculate commissions
        commission_rate = client_site.client.withdraw_commission / 100
        transaction.commission_amount = amount * commission_rate
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'transaction_id': transaction.id,
            'reference_code': reference_code,
            'amount': amount,
            'currency': data['currency'],
            'status': 'pending'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500
