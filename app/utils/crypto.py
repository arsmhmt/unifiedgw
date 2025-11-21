import re
import os
from cryptography.fernet import Fernet
from flask import current_app

def validate_crypto_address(address, crypto_type):
    """
    Validate a cryptocurrency address based on its type.
    
    Args:
        address (str): The cryptocurrency address to validate
        crypto_type (str): The type of cryptocurrency (e.g., 'bitcoin', 'ethereum', 'litecoin')
        
    Returns:
        bool: True if the address is valid, False otherwise
    """
    # Bitcoin/Bitcoin Cash (BTC/BCH)
    if crypto_type.lower() in ['bitcoin', 'btc', 'bitcoin cash', 'bch']:
        # Bitcoin addresses start with 1, 3, or bc1
        if re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$', address) or \
           re.match(r'^bc1[a-zA-HJ-NP-Z0-9]{25,39}$', address):
            return True
        # Bitcoin Cash addresses start with q, p, or 1
        elif re.match(r'^(?:bitcoincash:)?[qp1][a-z0-9]{39}$', address):
            return True
    
    # Ethereum (ETH)
    elif crypto_type.lower() in ['ethereum', 'eth']:
        # Ethereum addresses start with 0x and are 42 characters long
        if re.match(r'^0x[a-fA-F0-9]{40}$', address):
            return True
    
    # Litecoin (LTC)
    elif crypto_type.lower() in ['litecoin', 'ltc']:
        # Litecoin addresses start with L or M
        if re.match(r'^[LM][a-km-zA-HJ-NP-Z1-9]{26,33}$', address):
            return True
    
    # Ripple (XRP)
    elif crypto_type.lower() in ['ripple', 'xrp']:
        # Ripple addresses are 34 characters long
        if re.match(r'^r[1-9A-HJ-NP-Za-km-z]{25,34}$', address):
            return True
    
    # Dogecoin (DOGE)
    elif crypto_type.lower() in ['dogecoin', 'doge']:
        # Dogecoin addresses start with D
        if re.match(r'^D{1}[5-9A-HJ-NP-U]{1}[1-9A-HJ-NP-Za-km-z]{32}$', address):
            return True
    
    # Bitcoin SV (BSV)
    elif crypto_type.lower() in ['bitcoin sv', 'bsv']:
        # Bitcoin SV addresses start with 1, 3, or bc1
        if re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$', address) or \
           re.match(r'^bc1[a-zA-HJ-NP-Z0-9]{25,39}$', address):
            return True
    
    # TRON (TRX)
    elif crypto_type.lower() in ['tron', 'trx']:
        # TRON addresses start with T
        if re.match(r'^T[a-km-zA-HJ-NP-Z1-9]{33}$', address):
            return True
    
    # EOS
    elif crypto_type.lower() in ['eos']:
        # EOS addresses are 12 characters long and use a-z, 1-5
        if re.match(r'^[a-z1-5\.]{12}$', address):
            return True
    
    # Binance Coin (BNB)
    elif crypto_type.lower() in ['binance coin', 'bnb']:
        # Binance addresses start with bnb
        if re.match(r'^bnb1[a-z0-9]{38}$', address):
            return True
    
    # Stellar (XLM)
    elif crypto_type.lower() in ['stellar', 'xlm']:
        # Stellar addresses start with G
        if re.match(r'^G[a-zA-Z0-9]{55}$', address):
            return True
    
    # Cardano (ADA)
    elif crypto_type.lower() in ['cardano', 'ada']:
        # Cardano addresses start with addr1
        if re.match(r'^addr1[a-z0-9]{56}$', address):
            return True
    
    # Solana (SOL)
    elif crypto_type.lower() in ['solana', 'sol']:
        # Solana addresses are 32 characters long
        if re.match(r'^[1-9A-HJ-NP-Za-km-z]{32}$', address):
            return True
    
    # Polygon (MATIC)
    elif crypto_type.lower() in ['polygon', 'matic']:
        # Polygon addresses are the same as Ethereum
        if re.match(r'^0x[a-fA-F0-9]{40}$', address):
            return True
    
    # Avalanche (AVAX)
    elif crypto_type.lower() in ['avalanche', 'avax']:
        # Avalanche addresses start with 0x
        if re.match(r'^0x[a-fA-F0-9]{40}$', address):
            return True
    
    return False

# Get encryption key from environment or generate one
def _get_encryption_key():
    """Get or generate encryption key"""
    key = current_app.config.get('ENCRYPTION_KEY')
    if not key:
        # Generate a new key if not set
        key = Fernet.generate_key()
        current_app.config['ENCRYPTION_KEY'] = key
    return key

def encrypt_data(data):
    """
    Encrypt sensitive data using Fernet encryption
    
    Args:
        data (str): Data to encrypt
        
    Returns:
        str: Encrypted data as base64 string
    """
    if not data:
        return data
    
    key = _get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(data.encode())
    return encrypted.decode()

def decrypt_data(encrypted_data):
    """
    Decrypt data encrypted with encrypt_data
    
    Args:
        encrypted_data (str): Encrypted data to decrypt
        
    Returns:
        str: Decrypted data
    """
    if not encrypted_data:
        return encrypted_data
    
    key = _get_encryption_key()
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_data.encode())
    return decrypted.decode()
