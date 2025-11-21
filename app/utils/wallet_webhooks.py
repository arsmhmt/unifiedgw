"""
Wallet Webhook Handlers
Handle incoming webhooks from wallet providers
"""

import hmac
import hashlib
import json
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models import WalletProvider, WalletProviderTransaction, Payment
from app.utils.audit import log_api_usage, log_security_event
from app.utils.webhook_security import WebhookHandler


wallet_webhooks = Blueprint('wallet_webhooks', __name__)


@wallet_webhooks.route('/webhook/binance', methods=['POST'])
def binance_webhook():
    """Handle Binance webhook notifications"""
    try:
        # Get raw data
        raw_data = request.get_data()
        data = request.get_json() if request.is_json else {}

        # Verify Binance signature
        if not _verify_binance_signature(raw_data, request.headers):
            log_security_event(
                event_type='invalid_binance_webhook_signature',
                user_id=None,
                details={'endpoint': '/webhook/binance'},
                ip_address=request.remote_addr
            )
            return jsonify({'error': 'Invalid signature'}), 401

        # Process webhook data
        event_type = data.get('eventType')
        event_data = data.get('data', {})

        if event_type == 'ACCOUNT_UPDATE':
            _process_binance_balance_update(event_data)
        elif event_type == 'ORDER_TRADE_UPDATE':
            _process_binance_trade_update(event_data)

        log_api_usage(
            user_id=None,
            endpoint='/webhook/binance',
            method='POST',
            request_data=data,
            ip_address=request.remote_addr
        )

        return jsonify({'status': 'processed'}), 200

    except Exception as e:
        current_app.logger.error(f"Binance webhook error: {str(e)}")
        return jsonify({'error': 'Processing failed'}), 500


@wallet_webhooks.route('/webhook/coinbase', methods=['POST'])
def coinbase_webhook():
    """Handle Coinbase webhook notifications"""
    try:
        # Get raw data
        raw_data = request.get_data()
        data = request.get_json() if request.is_json else {}

        # Verify Coinbase signature
        if not _verify_coinbase_signature(raw_data, request.headers):
            log_security_event(
                event_type='invalid_coinbase_webhook_signature',
                user_id=None,
                details={'endpoint': '/webhook/coinbase'},
                ip_address=request.remote_addr
            )
            return jsonify({'error': 'Invalid signature'}), 401

        # Process webhook data
        event_type = data.get('type')
        event_data = data.get('data', {})

        if event_type == 'wallet:addresses:new-payment':
            _process_coinbase_payment(event_data)
        elif event_type == 'wallet:transactions:new':
            _process_coinbase_transaction(event_data)

        log_api_usage(
            user_id=None,
            endpoint='/webhook/coinbase',
            method='POST',
            request_data=data,
            ip_address=request.remote_addr
        )

        return jsonify({'status': 'processed'}), 200

    except Exception as e:
        current_app.logger.error(f"Coinbase webhook error: {str(e)}")
        return jsonify({'error': 'Processing failed'}), 500


def _verify_binance_signature(raw_data, headers):
    """Verify Binance webhook signature"""
    # Binance uses HMAC SHA256 with API secret
    # This is a simplified verification - in production you'd need the provider's secret
    return True  # Placeholder - implement proper verification


def _verify_coinbase_signature(raw_data, headers):
    """Verify Coinbase webhook signature"""
    # Coinbase uses HMAC SHA256 with webhook secret
    # This is a simplified verification - in production you'd need the provider's secret
    return True  # Placeholder - implement proper verification


def _process_binance_balance_update(data):
    """Process Binance balance update"""
    balances = data.get('B', [])
    for balance in balances:
        asset = balance.get('a')
        free = balance.get('f')
        locked = balance.get('l')

        # Update balance in database
        # This would update WalletBalance records
        current_app.logger.info(f"Binance balance update: {asset} - Free: {free}, Locked: {locked}")


def _process_binance_trade_update(data):
    """Process Binance trade update"""
    order = data.get('o', {})
    symbol = order.get('s')
    order_id = order.get('i')
    status = order.get('X')

    # Update transaction status
    transaction = WalletProviderTransaction.query.filter_by(
        transaction_hash=str(order_id)
    ).first()

    if transaction:
        if status == 'FILLED':
            transaction.status = 'completed'
        elif status in ['CANCELED', 'EXPIRED']:
            transaction.status = 'failed'
        else:
            transaction.status = 'pending'

        db.session.commit()

    current_app.logger.info(f"Binance trade update: {symbol} order {order_id} - {status}")


def _process_coinbase_payment(data):
    """Process Coinbase payment notification"""
    address = data.get('address')
    amount = data.get('amount', {})
    transaction_hash = data.get('transaction', {}).get('hash')

    # Find related payment and update status
    payment = Payment.query.filter_by(
        transaction_hash=transaction_hash
    ).first()

    if payment:
        payment.status = 'completed'
        payment.completed_at = db.func.now()
        db.session.commit()

    current_app.logger.info(f"Coinbase payment received: {amount} to {address}")


def _process_coinbase_transaction(data):
    """Process Coinbase transaction notification"""
    transaction_id = data.get('id')
    status = data.get('status')
    amount = data.get('amount', {})

    # Update transaction status
    transaction = WalletProviderTransaction.query.filter_by(
        transaction_hash=transaction_id
    ).first()

    if transaction:
        if status == 'completed':
            transaction.status = 'completed'
        elif status == 'failed':
            transaction.status = 'failed'
        else:
            transaction.status = 'pending'

        db.session.commit()

    current_app.logger.info(f"Coinbase transaction update: {transaction_id} - {status}")


# Register webhook blueprint
def init_wallet_webhooks(app):
    """Initialize wallet webhooks"""
    app.register_blueprint(wallet_webhooks, url_prefix='/wallet')
    # Exempt from CSRF protection
    if hasattr(app, 'extensions') and 'csrf' in app.extensions:
        csrf = app.extensions['csrf']
        csrf.exempt(wallet_webhooks)