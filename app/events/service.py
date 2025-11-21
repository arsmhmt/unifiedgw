"""
Event service layer for creating and managing webhook events.
"""
from datetime import datetime
from app.extensions.extensions import db
from app.models.webhook_event import WebhookEvent
from app.payment.constants import WebhookEventType, WebhookEventStatus


def create_event(payment, event_type):
    """
    Create a new webhook event for a payment status change.
    
    Args:
        payment: Payment model instance
        event_type (str or WebhookEventType): Type of event (e.g., 'payment.created')
        
    Returns:
        WebhookEvent: Created event instance, or None if client has no webhook configured
    """
    if not payment or not payment.client:
        return None
    
    client = payment.client
    
    # Check if client has webhooks enabled and configured
    if not getattr(client, 'webhook_enabled', False):
        return None
    if not getattr(client, 'webhook_url', None):
        return None
    
    # Convert enum to string if needed
    if isinstance(event_type, WebhookEventType):
        event_type = event_type.value
    
    # Build payload
    payload = {
        'event_type': event_type,
        'payment': {
            'id': payment.id,
            'client_id': payment.client_id,
            'amount': float(payment.amount) if payment.amount else None,
            'currency': payment.currency,
            'fiat_amount': float(payment.fiat_amount) if payment.fiat_amount else None,
            'fiat_currency': payment.fiat_currency,
            'crypto_amount': float(payment.crypto_amount) if payment.crypto_amount else None,
            'crypto_currency': payment.crypto_currency,
            'status': payment.status.value if hasattr(payment.status, 'value') else str(payment.status),
            'payment_method': payment.payment_method,
            'transaction_id': payment.transaction_id,
            'description': payment.description,
            'created_at': payment.created_at.isoformat() if payment.created_at else None,
            'updated_at': payment.updated_at.isoformat() if payment.updated_at else None
        },
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Create event
    event = WebhookEvent(
        client_id=payment.client_id,
        payment_id=payment.id,
        event_type=event_type,
        status=WebhookEventStatus.PENDING.value,
        attempts=0,
        payload=payload,
        next_attempt_at=datetime.utcnow()  # Ready to send immediately
    )
    
    db.session.add(event)
    db.session.commit()
    
    return event


def mark_event_delivered(event, response_code=200):
    """
    Mark an event as successfully delivered.
    
    Args:
        event (WebhookEvent): Event instance
        response_code (int): HTTP response code from client
    """
    event.status = WebhookEventStatus.DELIVERED.value
    event.delivered_at = datetime.utcnow()
    event.last_response_code = response_code
    event.last_error = None
    event.updated_at = datetime.utcnow()
    
    db.session.commit()


def mark_event_failed(event, error_message, response_code=None):
    """
    Mark an event delivery attempt as failed and schedule retry.
    
    Args:
        event (WebhookEvent): Event instance
        error_message (str): Error description
        response_code (int, optional): HTTP response code if available
    """
    event.attempts += 1
    event.last_error = error_message[:500]  # Truncate long errors
    event.last_response_code = response_code
    event.updated_at = datetime.utcnow()
    
    # Check if we've exhausted retries
    if event.attempts >= event.max_attempts:
        event.status = WebhookEventStatus.FAILED.value
        event.next_attempt_at = None
    else:
        # Calculate next retry time using exponential backoff
        event.next_attempt_at = event.calculate_next_attempt()
    
    db.session.commit()
