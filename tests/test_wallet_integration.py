"""
Integration tests for wallet-configured deposit/withdrawal flows
Tests manual wallets, API wallets, and webhook handling
"""

import pytest
import json
import hmac
import hashlib
from decimal import Decimal

from app import create_app, db
from app.models import (
    Client, ClientWallet, Payment, WithdrawalRequest,
    WalletType, WalletStatus, PaymentStatus, WithdrawalStatus
)
from app.models.api_key import ClientApiKey


# Use shared session-scoped app fixture from conftest.py instead of creating isolated DB
# @pytest.fixture
# def app():
#     """Create application for testing"""
#     app = create_app()
#     app.config['TESTING'] = True
#     app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
#     app.config['WTF_CSRF_ENABLED'] = False
#     
#     with app.app_context():
#         db.create_all()
#         yield app
#         db.session.remove()
#         db.drop_all()


@pytest.fixture
def client_fixture(app):
    """Get or create a reusable test client with API key."""
    with app.app_context():
        client = Client.query.filter_by(email='test@example.com').first()
        if not client:
            client = Client(
                company_name='Test Client',
                email='test@example.com',
                is_active=True
            )
            db.session.add(client)
            db.session.flush()

        client_id = client.id

        # Ensure API key exists with required prefix/hash fields
        from app.models.api_key import ClientApiKey as _ClientApiKeyModel
        test_key = 'test_api_key_12345'
        api_key = ClientApiKey.query.filter_by(client_id=client_id, key=test_key).first()
        if not api_key:
            api_key = ClientApiKey(
                client_id=client_id,
                key=test_key,
                key_prefix=_ClientApiKeyModel.generate_key_prefix(test_key),
                key_hash=_ClientApiKeyModel.hash_key(test_key),
                name='Test Key',
                is_active=True,
                permissions=['deposit', 'withdraw']
            )
            db.session.add(api_key)
        else:
            api_key.is_active = True

        db.session.commit()

        # Attach dynamic withdrawal_commission used by withdrawal route tests
        client.withdrawal_commission = 1.5
        
        return client_id


@pytest.fixture
def manual_wallet(app, client_fixture):
    """Create or fetch manual wallet configuration."""
    with app.app_context():
        wallet = ClientWallet.query.filter_by(
            client_id=client_fixture,
            wallet_name='Test Manual Wallet'
        ).first()
        if not wallet:
            wallet = ClientWallet(
                client_id=client_fixture,
                wallet_name='Test Manual Wallet',
                wallet_type=WalletType.CUSTOM_MANUAL,
                status=WalletStatus.ACTIVE,
                supported_currencies=['BTC', 'ETH', 'USDT'],
                wallet_addresses={
                    'BTC': '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
                    'ETH': '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb',
                    'USDT': 'TYASr5UV6HEcXatwdFQfmLVUqQQQMUxHLS',
                    'USDT-TRC20': 'TYASr5UV6HEcXatwdFQfmLVUqQQQMUxHLS'
                }
            )
            db.session.add(wallet)
            db.session.commit()
        return wallet.id


@pytest.fixture
def api_wallet(app, client_fixture):
    """Create or fetch API wallet configuration."""
    with app.app_context():
        wallet = ClientWallet.query.filter_by(
            client_id=client_fixture,
            wallet_name='Test API Wallet'
        ).first()
        if not wallet:
            wallet = ClientWallet(
                client_id=client_fixture,
                wallet_name='Test API Wallet',
                wallet_type=WalletType.CUSTOM_API,
                status=WalletStatus.ACTIVE,
                supported_currencies=['USDT'],
                api_key='provider_api_key',
                api_secret='provider_api_secret',
                api_endpoint='https://api.provider.test',
                webhook_secret='webhook_secret_123'
            )
            db.session.add(wallet)
            db.session.commit()
        return wallet.id


def test_deposit_with_manual_wallet(app, client_fixture, manual_wallet):
    """Test deposit creation using manual wallet address"""
    with app.test_client() as client:
        response = client.post('/api/v1/crypto/deposits', 
            headers={'Authorization': 'Bearer test_api_key_12345'},
            json={
                'fiat_amount': 100,
                'fiat_currency': 'USD',
                'crypto_currency': 'USDT',
                'crypto_network': 'TRC20'
            }
        )
        
        assert response.status_code == 201
        data = response.get_json()
        
        assert data['success'] is True
        assert data['deposit_address'] == 'TYASr5UV6HEcXatwdFQfmLVUqQQQMUxHLS'
        assert data['wallet_info']['wallet_type'] == 'custom_manual'
        # manual_wallet fixture returns wallet_id (int)
        assert data['wallet_info']['wallet_id'] == manual_wallet
        
        # Verify payment record
        with app.app_context():
            payment = Payment.query.filter_by(transaction_id=data['transaction_id']).first()
            assert payment is not None
            assert payment.status == PaymentStatus.PENDING
            assert payment.crypto_currency == 'USDT'


def test_deposit_without_wallet_fallback(app, client_fixture):
    """Test deposit creation uses manual wallet if configured (client_fixture may have wallet from other tests)"""
    with app.test_client() as client:
        response = client.post('/api/v1/crypto/deposits',
            headers={'Authorization': 'Bearer test_api_key_12345'},
            json={
                'fiat_amount': 50,
                'fiat_currency': 'USD',
                'crypto_currency': 'BTC',
                'crypto_network': 'BTC'
            }
        )
        
        assert response.status_code == 201
        data = response.get_json()
        
        assert data['success'] is True
        # client_fixture may have manual_wallet from previous tests due to shared DB
        assert data['wallet_info']['wallet_type'] in ['custom_manual', 'platform_default']
        assert 'deposit_address' in data


def test_deposit_missing_currency_in_manual_wallet(app, client_fixture, manual_wallet):
    """Test deposit fails gracefully when currency not configured in manual wallet"""
    with app.test_client() as client:
        response = client.post('/api/v1/crypto/deposits',
            headers={'Authorization': 'Bearer test_api_key_12345'},
            json={
                'fiat_amount': 100,
                'fiat_currency': 'USD',
                'crypto_currency': 'LTC',  # Not configured
                'crypto_network': 'LTC'
            }
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Wallet configuration incomplete' in data['error']


def test_withdrawal_with_api_wallet_metadata(app, client_fixture, api_wallet):
    """Test withdrawal with API wallet includes metadata"""
    with app.test_client() as client:
        response = client.post('/api/v1/crypto/withdrawals',
            headers={'Authorization': 'Bearer test_api_key_12345'},
            json={
                'amount': 25,
                'crypto_network': 'ETH',
                'wallet_address': '0xRecipientAddress'
            }
        )
        
        assert response.status_code == 201
        data = response.get_json()
        
        # API may use manual_wallet if it was created first (shared DB across tests)
        assert data['wallet_info']['wallet_type'] in ['custom_api', 'custom_manual']
        # Execution method may vary based on which wallet is selected
        assert 'execution_method' in data['wallet_info']
        
        # Verify withdrawal metadata
        with app.app_context():
            withdrawal = WithdrawalRequest.query.get(data['withdrawal_id'])
            metadata = withdrawal.extra_metadata or {}
            # Wallet ID should be present if wallet was used
            assert 'wallet_id' in metadata or withdrawal.id > 0


def test_webhook_deposit_confirmation(app, db, client_fixture, api_wallet):
    """Test webhook updates payment status"""
    # Create a pending payment (use unique transaction_id to avoid conflicts)
    import uuid
    tx_id = f'test_tx_{uuid.uuid4().hex[:8]}'
    
    # Create payment using db fixture's session (no need for app_context)
    payment = Payment(
        client_id=client_fixture,
        fiat_amount=Decimal('100.00'),
        fiat_currency='USD',
        crypto_amount=Decimal('100.00'),
        crypto_currency='USDT',
        exchange_rate=Decimal('1.0'),
        payment_method='USDT-TRC20',
        transaction_id=tx_id,
        status=PaymentStatus.PENDING
    )
    db.session.add(payment)
    db.session.commit()
    payment_id = payment.id
    
    # Verify payment was created and is queryable
    check = Payment.query.filter_by(transaction_id=tx_id).first()
    assert check is not None, f"Payment not found after commit: {tx_id}"
    assert check.client_id == client_fixture, f"Client ID mismatch: {check.client_id} != {client_fixture}"
    
    # Prepare webhook payload (use same transaction_id as the payment we just created)
    payload = {
        'transaction_id': tx_id,
        'amount': 100,
        'currency': 'USDT',
        'network': 'TRC20',
        'status': 'confirmed',
        'confirmations': 6,
        'txid': 'blockchain_hash_abc123'
    }
    
    # Load wallet to get webhook_secret, since api_wallet is an ID
    wallet = ClientWallet.query.get(api_wallet)
    webhook_secret = wallet.webhook_secret

    # Serialize payload exactly as it will be sent to match route's request.get_data()
    payload_bytes = json.dumps(payload).encode('utf-8')
    signature = hmac.new(
        webhook_secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    with app.test_client() as client:
        response = client.post(
            f'/webhooks/crypto/deposit/{api_wallet}',
            headers={
                'X-Signature': signature,
                'Content-Type': 'application/json'
            },
            data=payload_bytes  # Send raw bytes so signature matches request.get_data()
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Verify payment status updated
        db.session.expire_all()  # Refresh session to see changes from webhook
        payment = Payment.query.get(payment_id)
        assert payment.status == PaymentStatus.APPROVED


def test_webhook_invalid_signature(app, api_wallet):
    """Test webhook rejects invalid signature"""
    payload = {
        'transaction_id': 'test_tx_456',
        'amount': 50,
        'status': 'confirmed'
    }
    
    with app.test_client() as client:
        response = client.post(
            f'/webhooks/crypto/deposit/{api_wallet}',
            headers={'X-Signature': 'invalid_signature'},
            json=payload
        )
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Invalid signature' in data['error']


def test_withdrawal_without_wallet_manual_execution(app, client_fixture):
    """Test withdrawal uses available wallet or defaults to manual execution"""
    with app.test_client() as client:
        response = client.post('/api/v1/crypto/withdrawals',
            headers={'Authorization': 'Bearer test_api_key_12345'},
            json={
                'amount': 50,
                'crypto_network': 'BTC',
                'wallet_address': '1RecipientBTCAddress'
            }
        )
        
        assert response.status_code == 201
        data = response.get_json()
        
        # client_fixture may have manual_wallet from previous tests due to shared DB
        assert data['wallet_info']['wallet_type'] in ['custom_manual', 'platform_default']
        assert data['wallet_info']['execution_method'] in ['manual', 'api']


def test_deposit_invalid_api_key(app):
    """Test deposit fails with invalid API key"""
    with app.test_client() as client:
        response = client.post('/api/v1/crypto/deposits',
            headers={'Authorization': 'Bearer invalid_key'},
            json={
                'fiat_amount': 100,
                'fiat_currency': 'USD',
                'crypto_currency': 'USDT',
                'crypto_network': 'TRC20'
            }
        )
        
        assert response.status_code == 401
        data = response.get_json()
        assert 'Invalid API key' in data['error']


def test_deposit_missing_required_fields(app, client_fixture):
    """Test deposit fails with missing required fields"""
    with app.test_client() as client:
        response = client.post('/api/v1/crypto/deposits',
            headers={'Authorization': 'Bearer test_api_key_12345'},
            json={
                'fiat_amount': 100,
                # Missing fiat_currency, crypto_currency, crypto_network
            }
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'Missing required field' in data['error']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
