"""
Webhook handlers for external wallet providers
Validates incoming webhooks and updates payment/withdrawal status
"""

from flask import Blueprint, request, jsonify, current_app
from functools import wraps
import hmac
import hashlib
import json

from app import db
from app.models import Payment, WithdrawalRequest, ClientWallet, WalletStatus
from app.models.enums import PaymentStatus, WithdrawalStatus
from ..utils.timezone import now_eest

webhooks_bp = Blueprint('wallet_provider_webhooks', __name__, url_prefix='/webhooks')


def validate_webhook_signature(wallet_id):
    """Decorator to validate webhook signature against wallet's webhook_secret"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get wallet configuration
            wallet = ClientWallet.query.get(wallet_id)
            if not wallet or wallet.status != WalletStatus.ACTIVE:
                return jsonify({'error': 'Wallet not found or inactive'}), 404
            
            if not wallet.webhook_secret:
                current_app.logger.warning(f"Wallet {wallet_id} has no webhook secret configured")
                return jsonify({'error': 'Webhook not configured'}), 400
            
            # Get signature from headers (common patterns)
            signature = (
                request.headers.get('X-Signature') or
                request.headers.get('X-Webhook-Signature') or
                request.headers.get('Signature')
            )
            
            if not signature:
                return jsonify({'error': 'Missing signature'}), 401
            
            # Compute expected signature
            payload = request.get_data()
            expected_signature = hmac.new(
                wallet.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures (constant-time comparison)
            if not hmac.compare_digest(signature, expected_signature):
                current_app.logger.warning(f"Invalid webhook signature for wallet {wallet_id}")
                return jsonify({'error': 'Invalid signature'}), 401
            
            # Add wallet to request context
            request.wallet = wallet
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


@webhooks_bp.route('/crypto/deposit/<int:wallet_id>', methods=['POST'])
def crypto_deposit_webhook(wallet_id):
    """
    Handle deposit confirmation webhooks from external wallet providers
    Expected payload format (flexible):
    {
        "transaction_id": "...",
        "address": "...",
        "amount": 123.45,
        "currency": "USDT",
        "network": "TRC20",
        "confirmations": 6,
        "status": "confirmed" | "pending" | "failed",
        "txid": "blockchain_tx_hash"
    }
    """
    wallet = ClientWallet.query.get(wallet_id)
    if not wallet or wallet.status != WalletStatus.ACTIVE:
        return jsonify({'error': 'Wallet not found or inactive'}), 404
    
    # Validate webhook secret if configured
    if wallet.webhook_secret:
        signature = (
            request.headers.get('X-Signature') or
            request.headers.get('X-Webhook-Signature') or
            request.headers.get('Signature')
        )
        
        if signature:
            payload = request.get_data()
            expected_signature = hmac.new(
                wallet.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                current_app.logger.warning(f"Invalid webhook signature for wallet {wallet_id}")
                return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json() or {}
    
    # Extract transaction details (support multiple formats)
    transaction_id = data.get('transaction_id') or data.get('txId') or data.get('id')
    address = data.get('address') or data.get('deposit_address')
    amount = data.get('amount')
    currency = (data.get('currency') or data.get('coin') or '').upper()
    network = (data.get('network') or '').upper()
    confirmations = data.get('confirmations', 0)
    status = (data.get('status') or 'pending').lower()
    txid = data.get('txid') or data.get('tx_hash') or data.get('hash')
    
    if not transaction_id or not amount:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Find matching payment by transaction_id or address
        payment = Payment.query.filter(
            Payment.client_id == wallet.client_id,
            db.or_(
                Payment.transaction_id == transaction_id,
                Payment.transaction_id.like(f'%{address}%')
            )
        ).order_by(Payment.created_at.desc()).first()
        
        if not payment:
            current_app.logger.warning(f"No payment found for transaction {transaction_id}")
            return jsonify({'error': 'Payment not found'}), 404
        
        # Update payment status based on webhook status
        old_status = payment.status
        
        if status in ['confirmed', 'completed', 'success']:
            if confirmations >= 1:  # Configurable threshold
                payment.status = PaymentStatus.APPROVED
                current_app.logger.info(f"Payment {payment.id} auto-approved via webhook (confirmations: {confirmations})")
        elif status in ['pending', 'processing']:
            payment.status = PaymentStatus.PENDING
        elif status in ['failed', 'rejected', 'cancelled']:
            payment.status = PaymentStatus.REJECTED
        
        # Store blockchain transaction hash if provided
        if txid and not payment.description:
            payment.description = f"Blockchain TX: {txid}"
        
        payment.updated_at = now_eest()
        db.session.commit()
        
        current_app.logger.info(
            f"Webhook processed: Payment {payment.id} status {old_status.value} → {payment.status.value}"
        )
        
        return jsonify({
            'success': True,
            'payment_id': payment.id,
            'status': payment.status.value,
            'message': 'Webhook processed successfully'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Webhook processing error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@webhooks_bp.route('/crypto/withdrawal/<int:wallet_id>', methods=['POST'])
def crypto_withdrawal_webhook(wallet_id):
    """
    Handle withdrawal status webhooks from external wallet providers
    Expected payload format:
    {
        "withdrawal_id": "...",
        "amount": 123.45,
        "currency": "USDT",
        "address": "...",
        "status": "completed" | "pending" | "failed",
        "txid": "blockchain_tx_hash",
        "fee": 1.5
    }
    """
    wallet = ClientWallet.query.get(wallet_id)
    if not wallet or wallet.status != WalletStatus.ACTIVE:
        return jsonify({'error': 'Wallet not found or inactive'}), 404
    
    # Validate webhook secret if configured
    if wallet.webhook_secret:
        signature = (
            request.headers.get('X-Signature') or
            request.headers.get('X-Webhook-Signature') or
            request.headers.get('Signature')
        )
        
        if signature:
            payload = request.get_data()
            expected_signature = hmac.new(
                wallet.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                current_app.logger.warning(f"Invalid webhook signature for wallet {wallet_id}")
                return jsonify({'error': 'Invalid signature'}), 401
    
    data = request.get_json() or {}
    
    withdrawal_id = data.get('withdrawal_id') or data.get('id')
    status = (data.get('status') or 'pending').lower()
    txid = data.get('txid') or data.get('tx_hash')
    
    if not withdrawal_id:
        return jsonify({'error': 'Missing withdrawal_id'}), 400
    
    try:
        # Find matching withdrawal request
        withdrawal = WithdrawalRequest.query.filter_by(
            id=withdrawal_id,
            client_id=wallet.client_id
        ).first()
        
        if not withdrawal:
            current_app.logger.warning(f"No withdrawal found for ID {withdrawal_id}")
            return jsonify({'error': 'Withdrawal not found'}), 404
        
        # Update withdrawal status
        old_status = withdrawal.status
        
        if status in ['completed', 'success']:
            withdrawal.status = WithdrawalStatus.COMPLETED
        elif status in ['pending', 'processing']:
            withdrawal.status = WithdrawalStatus.PROCESSING
        elif status in ['failed', 'rejected']:
            withdrawal.status = WithdrawalStatus.FAILED
        
        # Store transaction hash if provided
        if txid:
            if not withdrawal.metadata:
                withdrawal.metadata = {}
            withdrawal.metadata['txid'] = txid
        
        db.session.commit()
        
        current_app.logger.info(
            f"Withdrawal webhook processed: {withdrawal.id} status {old_status.value} → {withdrawal.status.value}"
        )
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal.id,
            'status': withdrawal.status.value,
            'message': 'Webhook processed successfully'
        }), 200
    
    except Exception as e:
        current_app.logger.error(f"Withdrawal webhook error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@webhooks_bp.route('/test/<int:wallet_id>', methods=['POST'])
def test_webhook(wallet_id):
    """Test endpoint for webhook configuration validation"""
    wallet = ClientWallet.query.get(wallet_id)
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    
    # Validate signature if secret is configured
    if wallet.webhook_secret:
        signature = request.headers.get('X-Signature')
        if signature:
            payload = request.get_data()
            expected_signature = hmac.new(
                wallet.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            if hmac.compare_digest(signature, expected_signature):
                return jsonify({
                    'success': True,
                    'message': 'Webhook configuration valid',
                    'wallet_id': wallet_id,
                    'wallet_name': wallet.wallet_name
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'Invalid signature'
                }), 401
    
    return jsonify({
        'success': True,
        'message': 'Webhook endpoint reachable (no signature validation)',
        'wallet_id': wallet_id,
        'wallet_name': wallet.wallet_name
    }), 200
