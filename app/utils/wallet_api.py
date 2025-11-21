"""
Wallet API Integration Services
Handles integration with different crypto wallet providers
"""

import hmac
import hashlib
import json
import time
from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from decimal import Decimal
import requests
from flask import current_app
from app.extensions import db, cache
from app.models import WalletProvider, WalletProviderTransaction, WalletBalance
from app.utils.crypto import encrypt_data, decrypt_data


class WalletAPIError(Exception):
    """Base exception for wallet API errors"""
    pass


class WalletAPIConnectionError(WalletAPIError):
    """Connection error with wallet provider"""
    pass


class WalletAPIAuthenticationError(WalletAPIError):
    """Authentication error with wallet provider"""
    pass


class BaseWalletAPI:
    """Base class for wallet API integrations"""

    def __init__(self, provider):
        self.provider = provider
        self.api_key = decrypt_data(provider.api_key) if provider.api_key else None
        self.api_secret = decrypt_data(provider.api_secret) if provider.api_secret else None
        self.api_passphrase = decrypt_data(provider.api_passphrase) if provider.api_passphrase else None
        self.sandbox_mode = provider.sandbox_mode
        self.base_url = self._get_base_url()

    def _get_base_url(self):
        """Get base URL for API calls"""
        raise NotImplementedError

    def _make_request(self, method, endpoint, data=None, params=None):
        """Make authenticated API request"""
        raise NotImplementedError

    def get_balance(self, currency=None):
        """Get wallet balance"""
        raise NotImplementedError

    def create_withdrawal(self, currency, amount, address, network=None):
        """Create withdrawal request"""
        raise NotImplementedError

    def get_transaction_status(self, tx_id):
        """Get transaction status"""
        raise NotImplementedError

    def validate_address(self, currency, address):
        """Validate wallet address"""
        raise NotImplementedError


class BinanceWalletAPI(BaseWalletAPI):
    """Binance wallet API integration"""

    def _get_base_url(self):
        return "https://api.binance.com" if not self.sandbox_mode else "https://testnet.binance.vision"

    def _generate_signature(self, query_string):
        """Generate HMAC SHA256 signature"""
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _make_request(self, method, endpoint, data=None, params=None):
        """Make authenticated request to Binance API"""
        url = f"{self.base_url}{endpoint}"

        # Add timestamp
        params = params or {}
        params['timestamp'] = int(time.time() * 1000)

        # Create query string
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])

        # Add signature
        signature = self._generate_signature(query_string)
        params['signature'] = signature

        headers = {
            'X-MBX-APIKEY': self.api_key
        }

        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, headers=headers)
            elif method.upper() == 'POST':
                response = requests.post(url, params=params, headers=headers, json=data)
            else:
                raise WalletAPIError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise WalletAPIConnectionError(f"Binance API request failed: {str(e)}")

    def get_balance(self, currency=None):
        """Get account balance from Binance"""
        try:
            data = self._make_request('GET', '/api/v3/account')

            balances = {}
            for balance in data.get('balances', []):
                asset = balance['asset']
                free = Decimal(balance['free'])
                locked = Decimal(balance['locked'])
                total = free + locked

                if total > 0:  # Only include assets with balance
                    balances[asset] = {
                        'free': free,
                        'locked': locked,
                        'total': total
                    }

            return balances if currency is None else balances.get(currency, {})

        except Exception as e:
            raise WalletAPIError(f"Failed to get Binance balance: {str(e)}")

    def create_withdrawal(self, currency, amount, address, network=None):
        """Create withdrawal on Binance"""
        params = {
            'coin': currency,
            'address': address,
            'amount': str(amount)
        }

        if network:
            params['network'] = network

        try:
            result = self._make_request('POST', '/sapi/v1/capital/withdraw/apply', params=params)
            return result
        except Exception as e:
            raise WalletAPIError(f"Failed to create Binance withdrawal: {str(e)}")

    def get_transaction_status(self, tx_id):
        """Get withdrawal status"""
        try:
            params = {'id': tx_id}
            result = self._make_request('GET', '/sapi/v1/capital/withdraw/history', params=params)
            return result
        except Exception as e:
            raise WalletAPIError(f"Failed to get transaction status: {str(e)}")

    def validate_address(self, currency, address):
        """Validate withdrawal address"""
        # Binance doesn't have a direct address validation endpoint
        # We'll do basic validation based on currency
        return len(address) > 10  # Basic check


class CoinbaseWalletAPI(BaseWalletAPI):
    """Coinbase wallet API integration"""

    def _get_base_url(self):
        return "https://api.coinbase.com"

    def _make_request(self, method, endpoint, data=None, params=None):
        """Make authenticated request to Coinbase API"""
        url = f"{self.base_url}{endpoint}"

        # Coinbase uses API key and secret for authentication
        timestamp = str(int(time.time()))
        message = timestamp + method.upper() + endpoint + (json.dumps(data) if data else "")

        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        headers = {
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-SIGN': signature,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-PASSPHRASE': self.api_passphrase or '',
            'Content-Type': 'application/json'
        }

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            else:
                raise WalletAPIError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise WalletAPIConnectionError(f"Coinbase API request failed: {str(e)}")

    def get_balance(self, currency=None):
        """Get account balance from Coinbase"""
        try:
            data = self._make_request('GET', '/api/v3/brokerage/accounts')

            balances = {}
            for account in data.get('accounts', []):
                currency_code = account['currency']
                balance = Decimal(account['available_balance']['value'])

                if balance > 0:
                    balances[currency_code] = {
                        'free': balance,
                        'locked': Decimal('0'),
                        'total': balance
                    }

            return balances if currency is None else balances.get(currency, {})

        except Exception as e:
            raise WalletAPIError(f"Failed to get Coinbase balance: {str(e)}")

    def create_withdrawal(self, currency, amount, address, network=None):
        """Create withdrawal on Coinbase"""
        data = {
            'amount': str(amount),
            'currency': currency,
            'to': address
        }

        if network:
            data['network'] = network

        try:
            result = self._make_request('POST', '/api/v3/brokerage/withdrawals', data=data)
            return result
        except Exception as e:
            raise WalletAPIError(f"Failed to create Coinbase withdrawal: {str(e)}")

    def get_transaction_status(self, tx_id):
        """Get withdrawal status"""
        try:
            result = self._make_request('GET', f'/api/v3/brokerage/withdrawals/{tx_id}')
            return result
        except Exception as e:
            raise WalletAPIError(f"Failed to get transaction status: {str(e)}")

    def validate_address(self, currency, address):
        """Validate withdrawal address"""
        # Basic validation - Coinbase has its own validation
        return len(address) > 10


class WalletAPIProvider:
    """Factory for wallet API providers"""

    @staticmethod
    def get_api(provider):
        """Get appropriate API instance for provider"""
        if provider.provider_type.value == 'binance':
            return BinanceWalletAPI(provider)
        elif provider.provider_type.value == 'coinbase':
            return CoinbaseWalletAPI(provider)
        else:
            raise WalletAPIError(f"Unsupported provider type: {provider.provider_type.value}")


class WalletService:
    """High-level wallet service for managing wallet operations"""

    @staticmethod
    def get_provider_balance(provider_id, currency=None):
        """Get balance for a specific provider"""
        provider = WalletProvider.query.get(provider_id)
        if not provider or not provider.is_active:
            raise WalletAPIError("Provider not found or inactive")

        try:
            api = WalletAPIProvider.get_api(provider)
            balance = api.get_balance(currency)

            # Update cached balance
            WalletService._update_balance_cache(provider.id, balance)

            return balance

        except Exception as e:
            # Update provider health status
            provider.health_status = 'error'
            provider.last_error_message = str(e)
            provider.last_health_check = now_eest()
            db.session.commit()
            raise

    @staticmethod
    def create_provider_withdrawal(provider_id, currency, amount, address, network=None):
        """Create withdrawal through provider"""
        provider = WalletProvider.query.get(provider_id)
        if not provider or not provider.supports_withdrawals:
            raise WalletAPIError("Provider not found or doesn't support withdrawals")

        try:
            api = WalletAPIProvider.get_api(provider)

            # Validate address
            if not api.validate_address(currency, address):
                raise WalletAPIError("Invalid withdrawal address")

            result = api.create_withdrawal(currency, amount, address, network)

            # Record transaction
            transaction = WalletProviderTransaction(
                provider_id=provider.id,
                transaction_type='withdrawal',
                currency=currency,
                amount=amount,
                transaction_hash=result.get('id') or result.get('txId'),
                status='pending',
                details=json.dumps(result)
            )
            db.session.add(transaction)
            db.session.commit()

            return result

        except Exception as e:
            raise WalletAPIError(f"Withdrawal failed: {str(e)}")

    @staticmethod
    def _update_balance_cache(provider_id, balances):
        """Update balance cache in database"""
        for currency, balance_data in balances.items():
            balance = WalletBalance.query.filter_by(
                provider_id=provider_id,
                currency=currency
            ).first()

            if balance:
                balance.free_balance = balance_data['free']
                balance.locked_balance = balance_data['locked']
                balance.total_balance = balance_data['total']
                balance.last_updated = now_eest()
            else:
                balance = WalletBalance(
                    provider_id=provider_id,
                    currency=currency,
                    free_balance=balance_data['free'],
                    locked_balance=balance_data['locked'],
                    total_balance=balance_data['total']
                )
                db.session.add(balance)

        db.session.commit()

    @staticmethod
    def get_all_provider_balances():
        """Get balances for all active providers"""
        providers = WalletProvider.get_active_providers()
        all_balances = {}

        for provider in providers:
            try:
                balances = WalletService.get_provider_balance(provider.id)
                all_balances[provider.name] = {
                    'provider': provider,
                    'balances': balances,
                    'status': 'success'
                }
            except Exception as e:
                all_balances[provider.name] = {
                    'provider': provider,
                    'balances': {},
                    'status': 'error',
                    'error': str(e)
                }

        return all_balances

    @staticmethod
    def test_provider_connection(provider_id):
        """Test connection to wallet provider"""
        provider = WalletProvider.query.get(provider_id)
        if not provider:
            return False, "Provider not found"

        try:
            api = WalletAPIProvider.get_api(provider)
            # Try to get balance as a connection test
            api.get_balance()

            # Update health status
            provider.health_status = 'healthy'
            provider.last_health_check = now_eest()
            provider.last_error_message = None
            db.session.commit()

            return True, "Connection successful"

        except Exception as e:
            # Update health status
            provider.health_status = 'error'
            provider.last_health_check = now_eest()
            provider.last_error_message = str(e)
            db.session.commit()

            return False, str(e)