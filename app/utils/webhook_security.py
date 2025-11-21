"""
Webhook Security and Verification for CPGateway
Handles webhook authentication, signature verification, and replay attack prevention
"""

import hmac
import hashlib
import time
import json
import logging
from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from typing import Dict, Optional, Tuple, Any
from flask import Blueprint, request, jsonify, current_app
from functools import wraps

from app.utils.security import WebhookSecurity, rate_limit
from app.utils.audit import log_security_event, log_api_usage
from app.models.client import Client
from app.extensions import db

logger = logging.getLogger(__name__)

# Webhook blueprint
webhook_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')

class WebhookHandler:
    """Advanced webhook handling with security features"""
    
    def __init__(self):
        self.replay_window = 300  # 5 minutes
        self.max_payload_size = 1024 * 1024  # 1MB
        
    def verify_webhook_request(self, client_id: int, payload: bytes, 
                             signature: str, timestamp: str) -> Tuple[bool, str]:
        """
        Comprehensive webhook verification
        
        Args:
            client_id: Client ID for webhook
            payload: Raw request body
            signature: X-Signature header
            timestamp: X-Timestamp header
            
        Returns:
            (is_valid, error_message)
        """
        try:
            # 1. Check payload size
            if len(payload) > self.max_payload_size:
                return False, "Payload too large"
            
            # 2. Verify timestamp
            if not WebhookSecurity.verify_timestamp(timestamp, self.replay_window):
                return False, "Invalid or expired timestamp"
            
            # 3. Get client and webhook secret
            client = Client.query.get(client_id)
            if not client:
                return False, "Client not found"
            
            if not client.is_active:
                return False, "Client account disabled"
            
            # Get webhook secret from client settings or configuration
            webhook_secret = self._get_webhook_secret(client)
            if not webhook_secret:
                return False, "Webhook not configured"
            
            # 4. Verify signature
            if not WebhookSecurity.verify_signature(payload, signature, webhook_secret):
                return False, "Invalid signature"
            
            return True, "Valid"
            
        except Exception as e:
            logger.error(f"Webhook verification error: {e}")
            return False, "Verification error"
    
    def _get_webhook_secret(self, client: Client) -> Optional[str]:
        """Get webhook secret for client"""
        # This could be stored in client settings or a separate webhook config table
        # For now, we'll use a simple approach
        settings = client.settings or {}
        return settings.get('webhook_secret')
    
    def process_webhook_payload(self, client: Client, payload_data: Dict) -> Dict:
        """
        Process and validate webhook payload
        
        Args:
            client: Client instance
            payload_data: Parsed webhook data
            
        Returns:
            Processing result
        """
        try:
            # Basic payload validation
            if not isinstance(payload_data, dict):
                return {'success': False, 'error': 'Invalid payload format'}
            
            # Check for required fields
            required_fields = ['event_type', 'data']
            missing_fields = [field for field in required_fields if field not in payload_data]
            if missing_fields:
                return {'success': False, 'error': f'Missing fields: {missing_fields}'}
            
            event_type = payload_data.get('event_type')
            event_data = payload_data.get('data', {})
            
            # Process based on event type
            result = self._handle_webhook_event(client, event_type, event_data)
            
            # Log successful processing
            log_security_event(
                event_type='webhook_processed',
                details={
                    'client_id': client.id,
                    'event_type': event_type,
                    'data_keys': list(event_data.keys()) if isinstance(event_data, dict) else 'non-dict'
                },
                severity='low'
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Webhook processing error for client {client.id}: {e}")
            return {'success': False, 'error': 'Processing error'}
    
    def _handle_webhook_event(self, client: Client, event_type: str, event_data: Dict) -> Dict:
        """Handle specific webhook event types"""
        
        handlers = {
            'payment_completed': self._handle_payment_completed,
            'payment_failed': self._handle_payment_failed,
            'user_registered': self._handle_user_registered,
            'deposit_confirmed': self._handle_deposit_confirmed,
            'withdrawal_requested': self._handle_withdrawal_requested
        }
        
        handler = handlers.get(event_type)
        if not handler:
            return {'success': False, 'error': f'Unknown event type: {event_type}'}
        
        return handler(client, event_data)
    
    def _handle_payment_completed(self, client: Client, data: Dict) -> Dict:
        """Handle payment completion webhook"""
        # Implementation for payment completion
        # This would integrate with your payment processing system
        return {'success': True, 'message': 'Payment completed webhook processed'}
    
    def _handle_payment_failed(self, client: Client, data: Dict) -> Dict:
        """Handle payment failure webhook"""
        # Implementation for payment failure
        return {'success': True, 'message': 'Payment failed webhook processed'}
    
    def _handle_user_registered(self, client: Client, data: Dict) -> Dict:
        """Handle user registration webhook"""
        # Implementation for user registration
        return {'success': True, 'message': 'User registration webhook processed'}
    
    def _handle_deposit_confirmed(self, client: Client, data: Dict) -> Dict:
        """Handle deposit confirmation webhook"""
        # Implementation for deposit confirmation
        return {'success': True, 'message': 'Deposit confirmed webhook processed'}
    
    def _handle_withdrawal_requested(self, client: Client, data: Dict) -> Dict:
        """Handle withdrawal request webhook"""
        # Implementation for withdrawal request
        # This might create a new WithdrawalRequest record
        return {'success': True, 'message': 'Withdrawal request webhook processed'}

# Global webhook handler
webhook_handler = WebhookHandler()

@webhook_bp.route('/client/<int:client_id>', methods=['POST'])
@rate_limit('webhook_endpoint', limit=1000, window=3600)  # 1000 webhooks per hour per client
def handle_client_webhook(client_id):
    """
    Handle incoming webhooks for a specific client
    """
    start_time = time.time()
    
    try:
        # Get headers
        signature = request.headers.get('X-Signature', '')
        timestamp = request.headers.get('X-Timestamp', '')
        content_type = request.headers.get('Content-Type', '')
        
        # Get raw payload
        payload = request.get_data()
        
        # Basic validation
        if not signature:
            log_security_event(
                event_type='webhook_missing_signature',
                details={'client_id': client_id, 'ip': request.remote_addr},
                severity='medium'
            )
            return jsonify({'error': 'Missing signature'}), 400
        
        if not timestamp:
            log_security_event(
                event_type='webhook_missing_timestamp',
                details={'client_id': client_id, 'ip': request.remote_addr},
                severity='medium'
            )
            return jsonify({'error': 'Missing timestamp'}), 400
        
        # Verify webhook
        is_valid, error_msg = webhook_handler.verify_webhook_request(
            client_id, payload, signature, timestamp
        )
        
        if not is_valid:
            log_security_event(
                event_type='webhook_verification_failed',
                details={
                    'client_id': client_id,
                    'error': error_msg,
                    'signature': signature[:16] + '...',  # Partial signature for logging
                    'ip': request.remote_addr
                },
                severity='high'
            )
            return jsonify({'error': error_msg}), 401
        
        # Parse payload
        try:
            if content_type.startswith('application/json'):
                payload_data = json.loads(payload.decode('utf-8'))
            else:
                return jsonify({'error': 'Unsupported content type'}), 400
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON payload'}), 400
        
        # Get client
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Process webhook
        result = webhook_handler.process_webhook_payload(client, payload_data)
        
        # Log API usage
        response_time = (time.time() - start_time) * 1000
        log_api_usage(
            api_key=f'webhook_{client_id}',
            endpoint=f'/webhooks/client/{client_id}',
            method='POST',
            response_code=200 if result.get('success') else 400,
            response_time=response_time
        )
        
        if result.get('success'):
            return jsonify({'status': 'success', 'message': result.get('message', 'Processed')})
        else:
            return jsonify({'error': result.get('error', 'Processing failed')}), 400
            
    except Exception as e:
        logger.error(f"Webhook error for client {client_id}: {e}")
        
        # Log API usage for error
        response_time = (time.time() - start_time) * 1000
        log_api_usage(
            api_key=f'webhook_{client_id}',
            endpoint=f'/webhooks/client/{client_id}',
            method='POST',
            response_code=500,
            response_time=response_time,
            error_message=str(e)
        )
        
        return jsonify({'error': 'Internal server error'}), 500

@webhook_bp.route('/client/<int:client_id>/test', methods=['POST'])
@rate_limit('webhook_test', limit=10, window=3600)  # 10 test webhooks per hour
def test_client_webhook(client_id):
    """
    Test webhook endpoint for clients to verify their integration
    """
    try:
        client = Client.query.get_or_404(client_id)
        
        # Create test payload
        test_payload = {
            'event_type': 'test',
            'data': {
                'timestamp': now_eest().isoformat(),
                'message': 'This is a test webhook'
            }
        }
        
        payload_bytes = json.dumps(test_payload).encode('utf-8')
        timestamp = str(int(time.time()))
        
        # Get webhook secret
        webhook_secret = webhook_handler._get_webhook_secret(client)
        if not webhook_secret:
            return jsonify({'error': 'Webhook secret not configured'}), 400
        
        # Generate signature
        signature = WebhookSecurity.create_signature(payload_bytes, webhook_secret)
        
        return jsonify({
            'success': True,
            'test_data': {
                'payload': test_payload,
                'headers': {
                    'X-Signature': signature,
                    'X-Timestamp': timestamp,
                    'Content-Type': 'application/json'
                }
            },
            'message': 'Use this data to test your webhook endpoint'
        })
        
    except Exception as e:
        logger.error(f"Webhook test error for client {client_id}: {e}")
        return jsonify({'error': 'Test generation failed'}), 500

def setup_webhook_security(client: Client, webhook_url: str, events: list) -> Dict:
    """
    Setup webhook configuration for a client
    
    Args:
        client: Client instance
        webhook_url: Client's webhook endpoint URL
        events: List of events to subscribe to
        
    Returns:
        Configuration result with webhook secret
    """
    try:
        import secrets
        
        # Generate webhook secret
        webhook_secret = secrets.token_urlsafe(32)
        
        # Update client settings
        settings = client.settings or {}
        settings.update({
            'webhook_url': webhook_url,
            'webhook_secret': webhook_secret,
            'webhook_events': events,
            'webhook_enabled': True,
            'webhook_created_at': now_eest().isoformat()
        })
        
        client.settings = settings
        db.session.commit()
        
        log_security_event(
            event_type='webhook_configured',
            details={
                'client_id': client.id,
                'webhook_url': webhook_url,
                'events': events
            },
            severity='low'
        )
        
        return {
            'success': True,
            'webhook_secret': webhook_secret,
            'webhook_url': webhook_url,
            'events': events,
            'message': 'Webhook configured successfully'
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Webhook setup error for client {client.id}: {e}")
        return {'success': False, 'error': 'Configuration failed'}

def send_webhook(client: Client, event_type: str, data: Dict) -> bool:
    """
    Send webhook to client endpoint
    
    Args:
        client: Client to send webhook to
        event_type: Type of event
        data: Event data
        
    Returns:
        Success status
    """
    try:
        import requests
        
        settings = client.settings or {}
        webhook_url = settings.get('webhook_url')
        webhook_secret = settings.get('webhook_secret')
        
        if not webhook_url or not webhook_secret:
            logger.warning(f"Webhook not configured for client {client.id}")
            return False
        
        # Prepare payload
        payload = {
            'event_type': event_type,
            'data': data,
            'timestamp': now_eest().isoformat(),
            'client_id': client.id
        }
        
        payload_bytes = json.dumps(payload).encode('utf-8')
        timestamp = str(int(time.time()))
        signature = WebhookSecurity.create_signature(payload_bytes, webhook_secret)
        
        # Send webhook
        headers = {
            'Content-Type': 'application/json',
            'X-Signature': signature,
            'X-Timestamp': timestamp,
            'User-Agent': 'CPGateway-Webhook/1.0'
        }
        
        response = requests.post(
            webhook_url,
            data=payload_bytes,
            headers=headers,
            timeout=30
        )
        
        success = response.status_code == 200
        
        log_security_event(
            event_type='webhook_sent',
            details={
                'client_id': client.id,
                'event_type': event_type,
                'webhook_url': webhook_url,
                'response_code': response.status_code,
                'success': success
            },
            severity='low'
        )
        
        return success
        
    except Exception as e:
        logger.error(f"Failed to send webhook to client {client.id}: {e}")
        return False
