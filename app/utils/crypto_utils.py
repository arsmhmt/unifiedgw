import os
import hashlib
import pyqrcode
import base64
from io import BytesIO
from datetime import datetime
from ..utils.timezone import now_eest

def generate_address(client_id, coin='BTC'):
    """
    Generate a unique payment address for a client.
    In a real application, this would interface with a cryptocurrency wallet.
    For development, we'll generate a deterministic address based on client ID and timestamp.
    """
    timestamp = int(now_eest().timestamp())
    unique_str = f"{client_id}_{timestamp}_{os.urandom(8).hex()}"
    address_hash = hashlib.sha256(unique_str.encode()).hexdigest()
    
    # For development, return a mock address with a prefix based on the coin
    prefix = {
        'BTC': '1',
        'ETH': '0x',
        'LTC': 'L'
    }.get(coin.upper(), 'addr_')
    
    return f"{prefix}{address_hash[:34]}"  # Return first 34 chars for consistency

def generate_order_id(client_id, length=12):
    """
    Generate a unique order ID for a payment.
    """
    timestamp = int(now_eest().timestamp())
    unique_str = f"{client_id}_{timestamp}_{os.urandom(4).hex()}"
    return hashlib.sha256(unique_str.encode()).hexdigest()[:length].upper()

def create_qr(data, scale=6):
    """
    Generate a QR code from the given data and return it as a base64 encoded string.
    
    Args:
        data (str): The data to encode in the QR code
        scale (int): The scale factor for the QR code
        
    Returns:
        str: Base64 encoded PNG image data
    """
    try:
        # Generate QR code
        qr = pyqrcode.create(data)
        
        # Create a buffer to save the QR code
        buffer = BytesIO()
        qr.png(buffer, scale=scale, quiet_zone=2)
        
        # Reset buffer position to the beginning
        buffer.seek(0)
        
        # Encode the image as base64
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return ""
