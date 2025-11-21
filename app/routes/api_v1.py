from flask import Blueprint, request, jsonify, current_app, g
from flask_login import current_user
from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from functools import wraps
import hashlib
import hmac
import json
from decimal import Decimal, InvalidOperation

import requests

from app.models.api_key import ClientApiKey
from app.models.client import Client
from app.models import Payment, WithdrawalRequest, ClientWallet, WalletStatus, WalletType
from app.utils.admin_notifications import create_payment_request_notification
from app.models.enums import PaymentStatus, WithdrawalStatus
from app import db
from sqlalchemy import func
import uuid
from app.middleware.rate_limiter import require_api_key, check_endpoint_permissions
from app.utils.crypto_utils import generate_address
from app.utils import create_qr
from app.utils.exchange import convert_fiat_to_crypto

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

def api_key_required(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'error': 'Missing or invalid Authorization header',
                'message': 'Include API key as Bearer token'
            }), 401
        
        api_key = auth_header.replace('Bearer ', '')
        
        # Find the API key
        key_record = ClientApiKey.query.filter_by(key=api_key, is_active=True).first()
        if not key_record:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'API key not found or inactive'
            }), 401
        
        # Check if key is expired
        if key_record.expires_at and key_record.expires_at < now_eest():
            return jsonify({
                'error': 'API key expired',
                'message': 'Please regenerate your API key'
            }), 401
        
        # Update usage stats
        key_record.last_used_at = now_eest()
        key_record.usage_count = (key_record.usage_count or 0) + 1
        db.session.commit()
        
        # Add client to request context
        request.api_client = key_record.client
        request.api_key_record = key_record
        
        return f(*args, **kwargs)
    return decorated_function

def check_permission(permission):
    """Decorator to check if API key has specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if permission not in (request.api_key_record.permissions or []):
                return jsonify({
                    'error': 'Insufficient permissions',
                    'message': f'API key requires {permission} permission'
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# === HEALTH CHECK (no auth required) ===
@api_v1.route('/health', methods=['GET', 'OPTIONS'])
def health():
    """Public health check endpoint for CORS preflight and connectivity testing"""
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200
    
    return jsonify({
        'status': 'ok',
        'message': 'PayCrypt API is running',
        'version': 'v1',
        'timestamp': now_eest().isoformat()
    }), 200

# === AUTHENTICATION & STATUS ===
@api_v1.route('/status', methods=['GET'])
@require_api_key
def api_status():
    """Get API status and client information"""
    client = g.client
    
    return jsonify({
        'status': 'active',
        'timestamp': now_eest().isoformat(),
        'client': {
            'id': client.id,
            'company_name': client.company_name,
            'client_type': 'flat_rate' if client.is_flat_rate() else 'commission',
            'package': client.package.name if client.package else None
        },
        'api_key': {
            'name': g.api_key.name,
            'rate_limit': g.api_key.rate_limit,
            'usage_count': g.api_key.usage_count,
            'permissions': g.api_key.permissions
        }
    })

# === BETSLIP SPECIFIC ENDPOINTS ===
@api_v1.route('/betslip/generate', methods=['POST'])
@require_api_key
@check_endpoint_permissions(['flat_rate:payment:create'])
def generate_betslip():
    """Generate a new payment request for betslip"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['amount', 'currency', 'user_id']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'error': 'Missing required field',
                    'message': f'Field {field} is required'
                }), 400
        
        # Generate unique transaction ID
        transaction_id = f"bet_{uuid.uuid4().hex[:12]}"
        
        # Create payment record
        payment = Payment(
            client_id=g.client.id,
            amount=float(data['amount']),
            fiat_amount=float(data['amount']),
            crypto_currency=data['currency'],
            transaction_id=transaction_id,
            status=PaymentStatus.PENDING,
            payment_method='crypto',
            description=data.get('description', f'Betslip payment for user {data["user_id"]}')
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'payment_id': payment.id,
            'transaction_id': transaction_id,
            'amount': payment.amount,
            'currency': payment.crypto_currency,
            'status': payment.status.value,
            'payment_url': f"{request.host_url}payment/{payment.id}",
            'created_at': payment.created_at.isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Betslip generation error: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to generate betslip'
        }), 500

@api_v1.route('/betslip/<int:payment_id>/status', methods=['GET'])
@require_api_key
@check_endpoint_permissions(['flat_rate:payment:read'])
def betslip_status(payment_id):
    """Get betslip payment status"""
    payment = Payment.query.filter_by(
        id=payment_id, 
        client_id=g.client.id
    ).first()
    
    if not payment:
        return jsonify({
            'error': 'Payment not found',
            'message': 'Payment ID not found or unauthorized'
        }), 404
    
    return jsonify({
        'payment_id': payment.id,
        'transaction_id': payment.transaction_id,
        'status': payment.status.value,
        'amount': payment.amount,
        'currency': payment.crypto_currency,
        'description': payment.description,
        'created_at': payment.created_at.isoformat(),
        'completed_at': payment.updated_at.isoformat() if payment.status.value == 'completed' else None
    })

# === PAYMENT ENDPOINTS ===
@api_v1.route('/payments', methods=['GET'])
@require_api_key
@check_endpoint_permissions(['flat_rate:payment:read'])
def list_payments():
    """List payments for the client"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status = request.args.get('status')
    
    query = Payment.query.filter_by(client_id=g.client.id)
    
    if status:
        try:
            status_enum = PaymentStatus(status)
            query = query.filter_by(status=status_enum)
        except ValueError:
            return jsonify({
                'error': 'Invalid status',
                'message': f'Status must be one of: {[s.value for s in PaymentStatus]}'
            }), 400
    
    payments = query.order_by(Payment.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'payments': [{
            'id': p.id,
            'transaction_id': p.transaction_id,
            'amount': p.amount,
            'currency': p.crypto_currency,
            'status': p.status.value,
            'description': p.description,
            'created_at': p.created_at.isoformat()
        } for p in payments.items],
        'pagination': {
            'page': payments.page,
            'pages': payments.pages,
            'per_page': payments.per_page,
            'total': payments.total
        }
    })

@api_v1.route('/payments', methods=['POST'])
@require_api_key
@check_endpoint_permissions(['flat_rate:payment:create'])
def create_payment():
    """Create a new payment"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['amount', 'currency']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'error': 'Missing required field',
                    'message': f'Field {field} is required'
                }), 400
        
        # Generate unique transaction ID
        transaction_id = f"pay_{uuid.uuid4().hex[:12]}"
        
        # Create payment record
        payment = Payment(
            client_id=g.client.id,
            amount=float(data['amount']),
            fiat_amount=float(data['amount']),
            crypto_currency=data['currency'],
            transaction_id=transaction_id,
            status=PaymentStatus.PENDING,
            payment_method=data.get('payment_method', 'crypto'),
            description=data.get('description', 'API Payment')
        )
        
        db.session.add(payment)
        db.session.commit()
        
        # TODO: Create admin notification (disabled due to schema mismatch)
        # create_payment_request_notification(payment)
        
        return jsonify({
            'success': True,
            'payment_id': payment.id,
            'transaction_id': transaction_id,
            'amount': payment.amount,
            'currency': payment.crypto_currency,
            'status': payment.status.value,
            'created_at': payment.created_at.isoformat()
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Payment creation error: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to create payment'
        }), 500

# === BALANCE ENDPOINTS ===
@api_v1.route('/balance', methods=['GET'])
@require_api_key
@check_endpoint_permissions(['flat_rate:balance:read'])
def get_balance():
    """Get client balance information"""
    client = g.client
    
    # Calculate current balance
    total_payments = db.session.query(func.sum(Payment.fiat_amount)).filter(
        Payment.client_id == client.id,
        Payment.status == PaymentStatus.COMPLETED
    ).scalar() or 0
    
    total_withdrawals = db.session.query(func.sum(WithdrawalRequest.net_amount)).filter(
        WithdrawalRequest.client_id == client.id,
        WithdrawalRequest.status == WithdrawalStatus.COMPLETED
    ).scalar() or 0
    
    current_balance = float(total_payments) - float(total_withdrawals)
    
    return jsonify({
        'balance': current_balance,
        'total_payments': float(total_payments),
        'total_withdrawals': float(total_withdrawals),
        'currency': 'USD',
        'last_updated': now_eest().isoformat()
    })

# === WITHDRAWAL ENDPOINTS ===
@api_v1.route('/withdrawals', methods=['GET'])
@require_api_key
@check_endpoint_permissions(['flat_rate:withdrawal:read'])
def list_withdrawals():
    """List withdrawal requests"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    withdrawals = WithdrawalRequest.query.filter_by(
        client_id=g.client.id
    ).order_by(WithdrawalRequest.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'withdrawals': [{
            'id': w.id,
            'amount': float(w.amount),
            'net_amount': float(w.net_amount) if w.net_amount else None,
            'currency': w.currency,
            'status': w.status.value,
            'wallet_address': w.user_wallet_address,
            'created_at': w.created_at.isoformat(),
            'processed_at': w.processed_at.isoformat() if w.processed_at else None
        } for w in withdrawals.items],
        'pagination': {
            'page': withdrawals.page,
            'pages': withdrawals.pages,
            'per_page': withdrawals.per_page,
            'total': withdrawals.total
        }
    })

@api_v1.route('/withdrawals', methods=['POST'])
@require_api_key
@check_endpoint_permissions(['flat_rate:withdrawal:create'])
def create_withdrawal():
    """Create a new withdrawal request"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['amount', 'currency', 'wallet_address']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'error': 'Missing required field',
                    'message': f'Field {field} is required'
                }), 400
        
        # Create withdrawal request
        withdrawal = WithdrawalRequest(
            client_id=g.client.id,
            amount=float(data['amount']),
            currency=data['currency'],
            user_wallet_address=data['wallet_address'],
            memo=data.get('memo'),
            note=data.get('note', 'API Withdrawal Request'),
            status=WithdrawalStatus.PENDING
        )
        
        db.session.add(withdrawal)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal.id,
            'amount': float(withdrawal.amount),
            'currency': withdrawal.currency,
            'status': withdrawal.status.value,
            'created_at': withdrawal.created_at.isoformat()
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Withdrawal creation error: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to create withdrawal'
        }), 500

# === BANK GATEWAY ENDPOINTS ===
@api_v1.route('/bank-gateway/deposits', methods=['POST', 'OPTIONS'])
def create_bank_deposit():
    """Create a bank gateway deposit request (wrapper for payments)"""
    current_app.logger.info(f"Bank deposit endpoint called: {request.method} from {request.headers.get('Origin')}")
    
    # Handle preflight BEFORE authentication
    if request.method == 'OPTIONS':
        current_app.logger.info("Returning OPTIONS response")
        response = jsonify({'status': 'ok'})
        return response, 200
    
    current_app.logger.info("Processing POST request")
    
    # Apply authentication only for actual POST request
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 401
    
    key_record = ClientApiKey.query.filter_by(key=api_key, is_active=True).first()
    if not key_record:
        return jsonify({'error': 'Invalid API key'}), 401
    
    client = key_record.client
    
    # Check permissions
    if not client.is_active:
        return jsonify({'error': 'Client account is not active'}), 403
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['amount', 'sender_name', 'sender_iban']
    for field in required_fields:
        if field not in data:
            return jsonify({
                'error': 'Missing required field',
                'field': field
            }), 400
    
    try:
        # Create payment record (existing system)
        payment = Payment(
            client_id=client.id,
            fiat_amount=float(data['amount']),
            fiat_currency='TRY',
            payment_method='bank_transfer',
            status=PaymentStatus.PENDING,
            description=f"Bank deposit from {data['sender_name']}",
            metadata={
                'sender_name': data['sender_name'],
                'sender_iban': data['sender_iban'],
                'reference': data.get('reference', ''),
                'provider_id': data.get('provider_id'),
                'user_id': data.get('user_id'),
                'client_id': data.get('client_id'),
                'source': 'demo_client'
            }
        )
        
        db.session.add(payment)
        db.session.commit()
        
        # TODO: Create notification for admin (disabled due to admin_notifications table schema mismatch)
        # The table is missing the admin_id column that the code expects
        # create_payment_request_notification(payment)
        
        return jsonify({
            'success': True,
            'deposit_id': payment.id,
            'amount': float(payment.fiat_amount),
            'currency': payment.fiat_currency,
            'status': payment.status.value,
            'sender_name': data['sender_name'],
            'sender_iban': data['sender_iban'],
            'reference': data.get('reference', ''),
            'created_at': payment.created_at.isoformat(),
            'message': 'Deposit request created. Awaiting admin approval.'
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Bank deposit creation error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to create deposit request'
        }), 500

@api_v1.route('/bank-gateway/withdrawals', methods=['POST', 'OPTIONS'])
def create_bank_withdrawal():
    """Create a bank gateway withdrawal request (wrapper for withdrawals)"""
    # Handle preflight BEFORE authentication
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        return response, 200
    
    # Apply authentication only for actual POST request
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 401
    
    key_record = ClientApiKey.query.filter_by(key=api_key, is_active=True).first()
    if not key_record:
        return jsonify({'error': 'Invalid API key'}), 401
    
    client = key_record.client
    
    # Check permissions
    if not client.is_active:
        return jsonify({'error': 'Client account is not active'}), 403
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['amount', 'recipient_name', 'recipient_iban']
    for field in required_fields:
        if field not in data:
            return jsonify({
                'error': 'Missing required field',
                'field': field
            }), 400
    
    try:
        amount = float(data['amount'])
        
        # Calculate commission
        commission_rate = client.withdrawal_commission / 100
        commission = amount * commission_rate
        net_amount = amount - commission
        
        # Create withdrawal record
        withdrawal = WithdrawalRequest(
            client_id=client.id,
            amount=amount,
            currency='TRY',
            withdrawal_method='bank_transfer',
            recipient_name=data['recipient_name'],
            recipient_iban=data['recipient_iban'],
            bank_name=data.get('bank_name'),
            commission=commission,
            net_amount=net_amount,
            status=WithdrawalStatus.PENDING,
            metadata={
                'provider_id': data.get('provider_id'),
                'user_id': data.get('user_id'),
                'client_id': data.get('client_id'),
                'source': 'demo_client'
            }
        )
        
        db.session.add(withdrawal)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal.id,
            'amount': float(withdrawal.amount),
            'commission': float(withdrawal.commission),
            'net_amount': float(withdrawal.net_amount),
            'currency': withdrawal.currency,
            'status': withdrawal.status.value,
            'recipient_name': withdrawal.recipient_name,
            'recipient_iban': withdrawal.recipient_iban,
            'created_at': withdrawal.created_at.isoformat(),
            'message': 'Withdrawal request created. Awaiting admin processing.'
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Bank withdrawal creation error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to create withdrawal request'
        }), 500

@api_v1.route('/crypto/deposits', methods=['POST', 'OPTIONS'])
def create_crypto_deposit():
    """Create a crypto deposit request with client wallet integration"""
    # Handle preflight BEFORE authentication
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        return response, 200

    # Apply authentication only for actual POST request
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 401

    key_record = ClientApiKey.query.filter_by(key=api_key, is_active=True).first()
    if not key_record:
        return jsonify({'error': 'Invalid API key'}), 401

    client = key_record.client

    if not client.is_active:
        return jsonify({'error': 'Client account is not active'}), 403

    data = request.get_json() or {}

    # Required inputs from the wallet flow
    required_fields = ['fiat_amount', 'fiat_currency', 'crypto_currency', 'crypto_network']
    for field in required_fields:
        if field not in data:
            return jsonify({
                'error': 'Missing required field',
                'field': field
            }), 400

    try:
        fiat_amount = Decimal(str(data['fiat_amount']))
        if fiat_amount <= 0:
            return jsonify({'error': 'Amount must be greater than zero'}), 400
    except (ValueError, InvalidOperation):
        return jsonify({'error': 'Invalid fiat amount'}), 400

    fiat_currency = data['fiat_currency'].upper()
    crypto_currency = data['crypto_currency'].upper()
    crypto_network = data['crypto_network'].upper()

    # Convert fiat to crypto
    crypto_amount, exchange_rate = convert_fiat_to_crypto(fiat_amount, fiat_currency, crypto_currency)
    if not crypto_amount or not exchange_rate:
        return jsonify({'error': 'Unable to calculate exchange rate at this time'}), 422

    try:
        # Step 1: Check if client has an active wallet configuration
        active_wallet = ClientWallet.query.filter_by(
            client_id=client.id,
            status=WalletStatus.ACTIVE
        ).first()

        deposit_address = None
        qr_code = None
        wallet_metadata = {}

        if active_wallet:
            # Client has a configured wallet - use it
            current_app.logger.info(f"Using client wallet {active_wallet.id} ({active_wallet.wallet_type.value}) for deposit")
            
            if active_wallet.wallet_type == WalletType.CUSTOM_MANUAL:
                # Manual wallet: use preconfigured address
                deposit_address = active_wallet.get_address(crypto_currency)
                if not deposit_address:
                    # Try with network suffix (e.g., USDT-TRC20)
                    deposit_address = active_wallet.get_address(f"{crypto_currency}-{crypto_network}")
                
                if not deposit_address:
                    return jsonify({
                        'error': 'Wallet configuration incomplete',
                        'message': f'No {crypto_currency} address configured for this wallet'
                    }), 400
                
                qr_code = create_qr(deposit_address)
                wallet_metadata = {
                    'wallet_id': active_wallet.id,
                    'wallet_type': 'custom_manual',
                    'wallet_name': active_wallet.wallet_name
                }
            
            elif active_wallet.wallet_type == WalletType.CUSTOM_API:
                # API wallet: call the provider's API to generate deposit address
                if not active_wallet.api_endpoint or not active_wallet.api_key:
                    return jsonify({
                        'error': 'Wallet API configuration incomplete',
                        'message': 'API endpoint or key not configured'
                    }), 400
                
                try:
                    # Call custom wallet API to get deposit address
                    api_response = requests.post(
                        f"{active_wallet.api_endpoint}/deposit-address",
                        json={
                            'currency': crypto_currency,
                            'network': crypto_network,
                            'amount': float(crypto_amount)
                        },
                        headers={
                            'Authorization': f'Bearer {active_wallet.api_key}',
                            'Content-Type': 'application/json'
                        },
                        timeout=10
                    )
                    
                    if api_response.status_code == 200:
                        api_data = api_response.json()
                        deposit_address = api_data.get('address') or api_data.get('deposit_address')
                        if not deposit_address:
                            raise ValueError('API did not return deposit address')
                        
                        qr_code = create_qr(deposit_address)
                        wallet_metadata = {
                            'wallet_id': active_wallet.id,
                            'wallet_type': 'custom_api',
                            'wallet_name': active_wallet.wallet_name,
                            'api_response': api_data
                        }
                    else:
                        raise ValueError(f'API returned status {api_response.status_code}')
                
                except requests.exceptions.RequestException as e:
                    current_app.logger.error(f"Wallet API call failed: {str(e)}")
                    return jsonify({
                        'error': 'Wallet API unavailable',
                        'message': 'Unable to generate deposit address from wallet provider'
                    }), 503
            
            else:
                # Platform wallet or unsupported type - fall back to internal generation
                deposit_address = generate_address(client.id, coin=crypto_currency)
                qr_code = create_qr(deposit_address)
                wallet_metadata = {
                    'wallet_id': active_wallet.id,
                    'wallet_type': active_wallet.wallet_type.value,
                    'fallback': True
                }
        else:
            # No wallet configured - use platform default (backward compatibility)
            current_app.logger.info(f"No wallet configured for client {client.id}, using platform default")
            deposit_address = generate_address(client.id, coin=crypto_currency)
            qr_code = create_qr(deposit_address)
            wallet_metadata = {
                'wallet_type': 'platform_default',
                'note': 'Client has no wallet configured'
            }

        transaction_id = uuid.uuid4().hex

        # Create payment record with wallet metadata
        payment = Payment(
            client_id=client.id,
            fiat_amount=fiat_amount,
            fiat_currency=fiat_currency,
            crypto_amount=crypto_amount,
            crypto_currency=crypto_currency,
            exchange_rate=exchange_rate,
            payment_method=f"{crypto_currency}-{crypto_network}",
            transaction_id=transaction_id,
            status=PaymentStatus.PENDING,
        )

        db.session.add(payment)
        db.session.commit()

        return jsonify({
            'success': True,
            'payment_id': payment.id,
            'transaction_id': transaction_id,
            'fiat_amount': float(fiat_amount),
            'fiat_currency': fiat_currency,
            'crypto_amount': float(crypto_amount),
            'crypto_currency': crypto_currency,
            'exchange_rate': float(exchange_rate),
            'network': crypto_network,
            'status': payment.status.value,
            'deposit_address': deposit_address,
            'qr_code': qr_code,
            'wallet_info': wallet_metadata,
            'created_at': payment.created_at.isoformat(),
            'message': 'Deposit request created. Awaiting confirmation.'
        }), 201

    except Exception as e:
        current_app.logger.error(f"Crypto deposit creation error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to create deposit request'
        }), 500

@api_v1.route('/crypto/withdrawals', methods=['POST', 'OPTIONS'])
def create_crypto_withdrawal():
    """Create a crypto withdrawal request with wallet provider integration"""
    # Handle preflight BEFORE authentication
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        return response, 200
    
    # Apply authentication only for actual POST request
    api_key = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 401
    
    key_record = ClientApiKey.query.filter_by(key=api_key, is_active=True).first()
    if not key_record:
        return jsonify({'error': 'Invalid API key'}), 401
    
    client = key_record.client
    
    # Check permissions
    if not client.is_active:
        return jsonify({'error': 'Client account is not active'}), 403
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['amount', 'crypto_network', 'wallet_address']
    for field in required_fields:
        if field not in data:
            return jsonify({
                'error': 'Missing required field',
                'field': field
            }), 400
    
    try:
        amount = float(data['amount'])
        crypto_network = data['crypto_network'].upper()
        wallet_address = data['wallet_address']
        currency = data.get('currency', 'USDT').upper()
        
        # Calculate commission
        commission_rate = client.withdrawal_commission / 100
        commission = amount * commission_rate
        net_amount = amount - commission
        
        # Check if client has an active wallet configuration
        active_wallet = ClientWallet.query.filter_by(
            client_id=client.id,
            status=WalletStatus.ACTIVE
        ).first()
        
        wallet_metadata = {
            'crypto_network': crypto_network,
            'wallet_address': wallet_address,
            'user_id': data.get('user_id'),
            'client_id': data.get('client_id'),
            'source': 'api_request'
        }
        
        # If wallet is configured and supports API, prepare for provider execution
        if active_wallet and active_wallet.wallet_type == WalletType.CUSTOM_API:
            wallet_metadata['wallet_id'] = active_wallet.id
            wallet_metadata['wallet_type'] = 'custom_api'
            wallet_metadata['wallet_name'] = active_wallet.wallet_name
            wallet_metadata['requires_provider_execution'] = True
            current_app.logger.info(f"Withdrawal will be executed via wallet provider {active_wallet.id}")
        elif active_wallet:
            wallet_metadata['wallet_id'] = active_wallet.id
            wallet_metadata['wallet_type'] = active_wallet.wallet_type.value
            wallet_metadata['requires_manual_execution'] = True
        else:
            wallet_metadata['wallet_type'] = 'platform_default'
            wallet_metadata['requires_manual_execution'] = True
        
        # Create withdrawal record (always requires admin approval first)
        withdrawal = WithdrawalRequest(
            client_id=client.id,
            amount=amount,
            currency=currency,
            withdrawal_method='crypto',
            commission=commission,
            net_amount=net_amount,
            status=WithdrawalStatus.PENDING,
            metadata=wallet_metadata
        )
        
        db.session.add(withdrawal)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal.id,
            'amount': float(withdrawal.amount),
            'commission': float(withdrawal.commission),
            'net_amount': float(withdrawal.net_amount),
            'currency': withdrawal.currency,
            'crypto_network': crypto_network,
            'wallet_address': wallet_address,
            'status': withdrawal.status.value,
            'wallet_info': {
                'wallet_type': wallet_metadata.get('wallet_type'),
                'execution_method': 'provider_api' if wallet_metadata.get('requires_provider_execution') else 'manual'
            },
            'created_at': withdrawal.created_at.isoformat(),
            'message': 'Crypto withdrawal request created. Awaiting admin approval.'
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Crypto withdrawal creation error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': 'Failed to create withdrawal request'
        }), 500

# === ERROR HANDLERS ===
@api_v1.errorhandler(404)
def api_not_found(error):
    return jsonify({
        'error': 'Not found',
        'message': 'The requested endpoint does not exist'
    }), 404

@api_v1.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'error': 'Method not allowed',
        'message': 'The requested method is not allowed for this endpoint'
    }), 405

@api_v1.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please slow down.'
    }), 429

@api_v1.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500
