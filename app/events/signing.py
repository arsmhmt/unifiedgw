"""
HMAC signing utilities for webhook payloads.
"""
import hmac
import hashlib
import json


def sign_payload(secret, timestamp, payload):
    """
    Generate HMAC signature for webhook payload.
    
    Args:
        secret (str): Client's webhook secret
        timestamp (str): ISO timestamp string
        payload (dict): Webhook payload dictionary
        
    Returns:
        str: Hex-encoded HMAC signature
    """
    if not secret:
        raise ValueError("Webhook secret is required for signing")
    
    # Create signing string: timestamp + payload JSON
    payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    signing_string = f"{timestamp}.{payload_json}"
    
    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode('utf-8'),
        signing_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_signature(secret, timestamp, payload, provided_signature):
    """
    Verify HMAC signature from incoming webhook.
    
    Args:
        secret (str): Client's webhook secret
        timestamp (str): ISO timestamp from headers
        payload (dict): Webhook payload
        provided_signature (str): Signature from X-Paycrypt-Signature header
        
    Returns:
        bool: True if signature is valid
    """
    if not secret or not provided_signature:
        return False
    
    try:
        expected_signature = sign_payload(secret, timestamp, payload)
        return hmac.compare_digest(expected_signature, provided_signature)
    except Exception:
        return False
