"""
Webhook dispatcher for sending pending events to clients.
"""
import requests
from datetime import datetime
from app.extensions.extensions import db
from app.models.webhook_event import WebhookEvent
from app.payment.constants import WebhookEventStatus
from .signing import sign_payload
from .service import mark_event_delivered, mark_event_failed


def dispatch_pending_events(limit=100, timeout=10):
    """
    Fetch and dispatch pending webhook events.
    
    Args:
        limit (int): Maximum number of events to process in one run
        timeout (int): HTTP request timeout in seconds
        
    Returns:
        dict: Summary of dispatch results
    """
    results = {
        'processed': 0,
        'delivered': 0,
        'failed': 0,
        'skipped': 0
    }
    
    # Fetch pending events that are due for delivery
    events = WebhookEvent.query.filter(
        WebhookEvent.status == WebhookEventStatus.PENDING.value,
        WebhookEvent.attempts < WebhookEvent.max_attempts,
        db.or_(
            WebhookEvent.next_attempt_at == None,
            WebhookEvent.next_attempt_at <= datetime.utcnow()
        )
    ).limit(limit).all()
    
    for event in events:
        results['processed'] += 1
        
        try:
            success = dispatch_event(event, timeout=timeout)
            if success:
                results['delivered'] += 1
            else:
                results['failed'] += 1
        except Exception as e:
            # Catch any unexpected errors
            mark_event_failed(event, f"Unexpected error: {str(e)}")
            results['failed'] += 1
    
    return results


def dispatch_event(event, timeout=10):
    """
    Dispatch a single webhook event to the client.
    
    Args:
        event (WebhookEvent): Event to dispatch
        timeout (int): HTTP request timeout in seconds
        
    Returns:
        bool: True if delivered successfully
    """
    # Validate event is deliverable
    if not event.is_deliverable():
        return False
    
    # Get client webhook configuration
    client = event.client
    if not client or not getattr(client, 'webhook_url', None):
        mark_event_failed(event, "Client webhook URL not configured")
        return False
    
    webhook_url = client.webhook_url
    webhook_secret = getattr(client, 'webhook_secret', None)
    
    # Prepare payload and headers
    payload = event.payload
    timestamp = datetime.utcnow().isoformat()
    
    headers = {
        'Content-Type': 'application/json',
        'X-Paycrypt-Event': event.event_type,
        'X-Paycrypt-Timestamp': timestamp,
        'X-Paycrypt-Event-Id': event.id
    }
    
    # Add signature if client has a webhook secret
    if webhook_secret:
        try:
            signature = sign_payload(webhook_secret, timestamp, payload)
            headers['X-Paycrypt-Signature'] = signature
        except Exception as e:
            mark_event_failed(event, f"Failed to sign payload: {str(e)}")
            return False
    
    # Send HTTP POST request
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=timeout
        )
        
        # Consider 2xx responses as successful
        if 200 <= response.status_code < 300:
            mark_event_delivered(event, response.status_code)
            return True
        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            mark_event_failed(event, error_msg, response.status_code)
            return False
            
    except requests.exceptions.Timeout:
        mark_event_failed(event, f"Request timeout after {timeout}s")
        return False
    except requests.exceptions.ConnectionError as e:
        mark_event_failed(event, f"Connection error: {str(e)[:200]}")
        return False
    except requests.exceptions.RequestException as e:
        mark_event_failed(event, f"Request error: {str(e)[:200]}")
        return False
    except Exception as e:
        mark_event_failed(event, f"Unexpected error: {str(e)[:200]}")
        return False
