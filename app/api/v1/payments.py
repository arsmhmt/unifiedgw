"""
Clean v1 Payments API endpoints.
"""
from flask import request, jsonify, current_app
from datetime import datetime
from decimal import Decimal, InvalidOperation
import uuid

from . import api_v1_bp
from .errors import (
    invalid_request_error,
    authentication_error,
    not_found_error,
    internal_error
)
from .auth import api_key_required
from app.models.payment import Payment
from app.models.enums import PaymentStatus
from app.payment.constants import PaymentMethod, PaymentType
from app.extensions.extensions import db
from app.events.service import create_event
from app.payment.constants import WebhookEventType


@api_v1_bp.route('/payments', methods=['POST'])
@api_key_required
def create_payment():
    """
    Create a new payment (deposit or withdrawal).
    
    Request body:
        {
            "amount": 100.00,
            "currency": "USD",
            "method": "crypto",  // or "bank"
            "type": "deposit",   // or "withdraw"
            "crypto_currency": "USDT",  // optional, for crypto payments
            "crypto_network": "TRC20",  // optional
            "client_reference": "order_123",  // optional
            "description": "Payment for order 123"  // optional
        }
    
    Returns:
        {
            "id": 123,
            "transaction_id": "pay_abc123",
            "status": "pending",
            "method": "crypto",
            "type": "deposit",
            "amount": 100.00,
            "currency": "USD",
            "crypto_amount": 99.5,
            "crypto_currency": "USDT",
            "crypto_network": "TRC20",
            "deposit_address": "TYASr5...",  // for crypto deposits
            "qr_code": "data:image/png;base64,...",  // for crypto deposits
            "created_at": "2025-11-21T12:00:00Z"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return invalid_request_error('Request body must be JSON')
        
        # Validate required fields
        required_fields = ['amount', 'currency', 'method', 'type']
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return invalid_request_error(
                'Missing required fields',
                {'missing_fields': missing_fields}
            )
        
        # Validate amount
        try:
            amount = Decimal(str(data['amount']))
            if amount <= 0:
                return invalid_request_error('Amount must be greater than zero')
        except (InvalidOperation, ValueError):
            return invalid_request_error('Invalid amount format')
        
        # Validate method
        try:
            method = PaymentMethod(data['method'].lower())
        except ValueError:
            return invalid_request_error(
                'Invalid payment method',
                {'valid_methods': [m.value for m in PaymentMethod]}
            )
        
        # Validate type
        try:
            payment_type = PaymentType(data['type'].lower())
        except ValueError:
            return invalid_request_error(
                'Invalid payment type',
                {'valid_types': [t.value for t in PaymentType]}
            )
        
        # Generate transaction ID
        transaction_id = f"pay_{uuid.uuid4().hex[:16]}"
        
        # Create payment record
        payment = Payment(
            client_id=request.api_client.id,
            fiat_amount=float(amount),
            fiat_currency=data['currency'].upper(),
            crypto_currency=data.get('crypto_currency', 'BTC').upper(),
            payment_method=method.value,
            transaction_id=transaction_id,
            status=PaymentStatus.PENDING,
            description=data.get('description', f'{payment_type.value.title()} payment')
        )
        
        # Calculate crypto amount if crypto payment
        if method == PaymentMethod.CRYPTO:
            try:
                payment.calculate_crypto_amount()
            except Exception as e:
                current_app.logger.error(f"Failed to calculate crypto amount: {e}")
                # Continue anyway, can be calculated later
        
        db.session.add(payment)
        db.session.commit()
        
        # Emit webhook event
        try:
            create_event(payment, WebhookEventType.PAYMENT_CREATED)
        except Exception as e:
            current_app.logger.error(f"Failed to create webhook event: {e}")
            # Don't fail the payment creation
        
        # Build response
        response = {
            'id': payment.id,
            'transaction_id': payment.transaction_id,
            'status': payment.status.value,
            'method': method.value,
            'type': payment_type.value,
            'amount': float(payment.fiat_amount) if payment.fiat_amount else None,
            'currency': payment.fiat_currency,
            'description': payment.description,
            'created_at': payment.created_at.isoformat() if payment.created_at else None
        }
        
        # Add crypto-specific fields
        if method == PaymentMethod.CRYPTO:
            response.update({
                'crypto_amount': float(payment.crypto_amount) if payment.crypto_amount else None,
                'crypto_currency': payment.crypto_currency,
                'crypto_network': data.get('crypto_network', 'TRC20'),
                # TODO: Add deposit_address and qr_code generation
            })
        
        return jsonify(response), 201
        
    except Exception as e:
        current_app.logger.error(f"Payment creation error: {str(e)}")
        db.session.rollback()
        return internal_error('Failed to create payment')


@api_v1_bp.route('/payments/<int:payment_id>', methods=['GET'])
@api_key_required
def get_payment(payment_id):
    """
    Get a single payment by ID.
    
    Returns:
        {
            "id": 123,
            "transaction_id": "pay_abc123",
            "status": "completed",
            "method": "crypto",
            "amount": 100.00,
            "currency": "USD",
            "crypto_amount": 99.5,
            "crypto_currency": "USDT",
            "description": "Payment for order 123",
            "created_at": "2025-11-21T12:00:00Z",
            "updated_at": "2025-11-21T12:05:00Z"
        }
    """
    payment = Payment.query.filter_by(
        id=payment_id,
        client_id=request.api_client.id
    ).first()
    
    if not payment:
        return not_found_error('Payment')
    
    response = {
        'id': payment.id,
        'transaction_id': payment.transaction_id,
        'status': payment.status.value,
        'method': payment.payment_method,
        'amount': float(payment.fiat_amount) if payment.fiat_amount else float(payment.amount) if payment.amount else None,
        'currency': payment.fiat_currency or payment.currency,
        'crypto_amount': float(payment.crypto_amount) if payment.crypto_amount else None,
        'crypto_currency': payment.crypto_currency,
        'description': payment.description,
        'created_at': payment.created_at.isoformat() if payment.created_at else None,
        'updated_at': payment.updated_at.isoformat() if payment.updated_at else None
    }
    
    return jsonify(response), 200


@api_v1_bp.route('/payments', methods=['GET'])
@api_key_required
def list_payments():
    """
    List payments for the authenticated client.
    
    Query parameters:
        - status: Filter by status (pending, approved, completed, etc.)
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20, max: 100)
        - from_date: Filter payments from this date (ISO format)
        - to_date: Filter payments to this date (ISO format)
    
    Returns:
        {
            "data": [
                {
                    "id": 123,
                    "transaction_id": "pay_abc123",
                    "status": "completed",
                    "amount": 100.00,
                    "currency": "USD",
                    "created_at": "2025-11-21T12:00:00Z"
                },
                ...
            ],
            "pagination": {
                "page": 1,
                "per_page": 20,
                "total": 150,
                "pages": 8
            }
        }
    """
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Build query
    query = Payment.query.filter_by(client_id=request.api_client.id)
    
    # Filter by status
    status = request.args.get('status')
    if status:
        try:
            status_enum = PaymentStatus(status.lower())
            query = query.filter_by(status=status_enum)
        except ValueError:
            return invalid_request_error(
                'Invalid status',
                {'valid_statuses': [s.value for s in PaymentStatus]}
            )
    
    # Filter by date range
    from_date = request.args.get('from_date')
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            query = query.filter(Payment.created_at >= from_dt)
        except ValueError:
            return invalid_request_error('Invalid from_date format (use ISO 8601)')
    
    to_date = request.args.get('to_date')
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            query = query.filter(Payment.created_at <= to_dt)
        except ValueError:
            return invalid_request_error('Invalid to_date format (use ISO 8601)')
    
    # Execute query with pagination
    payments = query.order_by(Payment.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    # Build response
    response = {
        'data': [{
            'id': p.id,
            'transaction_id': p.transaction_id,
            'status': p.status.value,
            'method': p.payment_method,
            'amount': float(p.fiat_amount) if p.fiat_amount else float(p.amount) if p.amount else None,
            'currency': p.fiat_currency or p.currency,
            'crypto_amount': float(p.crypto_amount) if p.crypto_amount else None,
            'crypto_currency': p.crypto_currency,
            'description': p.description,
            'created_at': p.created_at.isoformat() if p.created_at else None
        } for p in payments.items],
        'pagination': {
            'page': payments.page,
            'per_page': payments.per_page,
            'total': payments.total,
            'pages': payments.pages
        }
    }
    
    return jsonify(response), 200
