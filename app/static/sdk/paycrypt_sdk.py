"""
PayCrypt Python SDK
Simple Python client for PayCrypt API integration

Installation:
    pip install requests

Usage:
    from paycrypt_sdk import PayCryptClient
    
    client = PayCryptClient(
        api_key='your_crypto_api_key',
        secret_key='your_crypto_secret',
        bank_api_key='your_bank_api_key'
    )
    
    # Create crypto payment
    payment = client.create_payment_session(
        order_id='ORD-123',
        amount='99.99',
        currency='USD',
        customer_email='customer@example.com'
    )
    
    # Create bank deposit
    deposit = client.create_bank_deposit(
        amount='500.00',
        currency='TRY',
        user_name='John Doe',
        user_email='john@example.com'
    )
"""

import requests
import json
import time
import hmac
import hashlib
from typing import Dict, Any, Optional


class PayCryptError(Exception):
    """Base exception for PayCrypt SDK"""
    pass


class PayCryptClient:
    """PayCrypt API Client"""
    
    def __init__(self, 
                 api_key: str,
                 secret_key: str,
                 bank_api_key: Optional[str] = None,
                 base_url: str = "https://paycrypt.online"):
        """
        Initialize PayCrypt client
        
        Args:
            api_key: Crypto payment API key
            secret_key: Crypto payment secret key for HMAC
            bank_api_key: Bank gateway API key (optional)
            base_url: Base URL for PayCrypt API
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.bank_api_key = bank_api_key
        self.base_url = base_url.rstrip('/')
        
    def _create_hmac_signature(self, timestamp: str, body: str) -> str:
        """Create HMAC signature for crypto API"""
        message = f"{timestamp}.{body}"
        return hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _make_crypto_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make authenticated request to crypto API"""
        url = f"{self.base_url}/api/v1{endpoint}"
        timestamp = str(int(time.time()))
        body = json.dumps(data) if data else ""
        
        headers = {
            'Content-Type': 'application/json',
            'X-Paycrypt-Key': self.api_key,
            'X-Paycrypt-Timestamp': timestamp,
            'X-Paycrypt-Signature': self._create_hmac_signature(timestamp, body)
        }
        
        response = requests.request(method, url, headers=headers, data=body)
        
        if not response.ok:
            raise PayCryptError(f"API request failed: {response.status_code} - {response.text}")
            
        return response.json()
    
    def _make_bank_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make authenticated request to bank API"""
        if not self.bank_api_key:
            raise PayCryptError("Bank API key not configured")
            
        url = f"{self.base_url}/bank-api{endpoint}"
        
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.bank_api_key
        }
        
        response = requests.request(method, url, headers=headers, json=data)
        
        if not response.ok:
            raise PayCryptError(f"Bank API request failed: {response.status_code} - {response.text}")
            
        return response.json()
    
    # Crypto Payment Methods
    
    def create_payment_session(self,
                             order_id: str,
                             amount: str,
                             currency: str = "USD",
                             customer_email: str = None,
                             success_url: str = None,
                             cancel_url: str = None,
                             webhook_url: str = None,
                             metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a new crypto payment session
        
        Args:
            order_id: Unique order identifier
            amount: Payment amount as string (e.g., "99.99")
            currency: Payment currency (default: USD)
            customer_email: Customer email address
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
            webhook_url: URL to receive webhook notifications
            metadata: Additional metadata dictionary
            
        Returns:
            Payment session data including checkout_url
        """
        data = {
            'order_id': order_id,
            'amount': amount,
            'currency': currency
        }
        
        if customer_email:
            data['customer'] = {'email': customer_email}
        
        if success_url:
            data['success_url'] = success_url
            
        if cancel_url:
            data['cancel_url'] = cancel_url
            
        if webhook_url:
            data['webhook_url'] = webhook_url
            
        if metadata:
            data['metadata'] = metadata
            
        return self._make_crypto_request('POST', '/payment_sessions', data)
    
    def get_payment_session(self, session_id: str) -> Dict[str, Any]:
        """Get payment session status"""
        return self._make_crypto_request('GET', f'/payment_sessions/{session_id}')
    
    def generate_betslip(self,
                        betslip_id: str,
                        user_id: str,
                        bets: list,
                        total_stake: str,
                        potential_payout: str,
                        webhook_url: str = None) -> Dict[str, Any]:
        """
        Generate a betslip for gaming platforms
        
        Args:
            betslip_id: Unique betslip identifier
            user_id: User identifier
            bets: List of bet objects
            total_stake: Total stake amount
            potential_payout: Potential payout amount
            webhook_url: URL to receive betslip notifications
            
        Returns:
            Betslip data
        """
        data = {
            'betslip_id': betslip_id,
            'user_id': user_id,
            'bets': bets,
            'total_stake': total_stake,
            'potential_payout': potential_payout
        }
        
        if webhook_url:
            data['webhook_url'] = webhook_url
            
        return self._make_crypto_request('POST', '/betslip/generate', data)
    
    def get_betslip_status(self, betslip_id: str) -> Dict[str, Any]:
        """Get betslip status"""
        return self._make_crypto_request('GET', f'/betslip/status/{betslip_id}')
    
    # Bank Gateway Methods
    
    def create_bank_deposit(self,
                           amount: str,
                           currency: str = "TRY",
                           user_name: str = None,
                           user_email: str = None,
                           user_phone: str = None,
                           callback_url: str = None,
                           external_transaction_id: str = None) -> Dict[str, Any]:
        """
        Create a bank deposit request
        
        Args:
            amount: Deposit amount as string
            currency: Currency code (default: TRY)
            user_name: Customer name
            user_email: Customer email
            user_phone: Customer phone
            callback_url: URL to receive status updates
            external_transaction_id: Your transaction ID
            
        Returns:
            Deposit request data with bank details
        """
        data = {
            'amount': amount,
            'currency': currency
        }
        
        if user_name:
            data['user_name'] = user_name
            
        if user_email:
            data['user_email'] = user_email
            
        if user_phone:
            data['user_phone'] = user_phone
            
        if callback_url:
            data['callback_url'] = callback_url
            
        if external_transaction_id:
            data['external_transaction_id'] = external_transaction_id
            
        return self._make_bank_request('POST', '/deposit/request', data)
    
    def create_bank_withdrawal(self,
                              amount: str,
                              currency: str = "TRY",
                              user_name: str = None,
                              user_email: str = None,
                              user_iban: str = None,
                              callback_url: str = None,
                              external_transaction_id: str = None) -> Dict[str, Any]:
        """
        Create a bank withdrawal request
        
        Args:
            amount: Withdrawal amount as string
            currency: Currency code (default: TRY)
            user_name: Customer name
            user_email: Customer email
            user_iban: Customer IBAN
            callback_url: URL to receive status updates
            external_transaction_id: Your transaction ID
            
        Returns:
            Withdrawal request data
        """
        data = {
            'amount': amount,
            'currency': currency
        }
        
        if user_name:
            data['user_name'] = user_name
            
        if user_email:
            data['user_email'] = user_email
            
        if user_iban:
            data['user_iban'] = user_iban
            
        if callback_url:
            data['callback_url'] = callback_url
            
        if external_transaction_id:
            data['external_transaction_id'] = external_transaction_id
            
        return self._make_bank_request('POST', '/withdraw/request', data)
    
    def get_bank_transaction_status(self, reference_code: str) -> Dict[str, Any]:
        """Get bank transaction status"""
        return self._make_bank_request('GET', f'/transaction/{reference_code}')
    
    def get_bank_balance(self) -> Dict[str, Any]:
        """Get bank account balance"""
        return self._make_bank_request('GET', '/balance')
    
    # Webhook Verification
    
    def verify_webhook(self, signature: str, timestamp: str, body: str) -> bool:
        """
        Verify webhook signature
        
        Args:
            signature: X-Paycrypt-Signature header value
            timestamp: X-Paycrypt-Timestamp header value
            body: Raw request body
            
        Returns:
            True if signature is valid
        """
        expected_signature = self._create_hmac_signature(timestamp, body)
        return hmac.compare_digest(signature, expected_signature)


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = PayCryptClient(
        api_key="your_crypto_api_key_here",
        secret_key="your_crypto_secret_here",
        bank_api_key="your_bank_api_key_here"
    )
    
    try:
        # Create crypto payment
        payment = client.create_payment_session(
            order_id="TEST-001",
            amount="99.99",
            currency="USD",
            customer_email="test@example.com",
            success_url="https://yoursite.com/success",
            cancel_url="https://yoursite.com/cancel",
            webhook_url="https://yoursite.com/webhook"
        )
        print(f"Payment created: {payment['id']}")
        print(f"Checkout URL: {payment['checkout_url']}")
        
        # Create bank deposit
        deposit = client.create_bank_deposit(
            amount="500.00",
            currency="TRY",
            user_name="Test User",
            user_email="test@example.com",
            callback_url="https://yoursite.com/callback"
        )
        print(f"Deposit created: {deposit['reference_code']}")
        
    except PayCryptError as e:
        print(f"Error: {e}")
