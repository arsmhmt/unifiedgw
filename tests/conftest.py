"""
Pytest configuration and fixtures.
Day 3: Test infrastructure.
"""
import os
import uuid

import pytest

from app import create_app, db as _db
from app.models.client import Client
from app.models.payment import Payment
from app.models.enums import PaymentStatus


@pytest.fixture(scope='session')
def app():
    """Create application for testing (shared DB)."""
    os.environ.setdefault('FLASK_ENV', 'testing')
    app = create_app()
    app.config['TESTING'] = True
    # Use shared in-memory DB so test client requests see the same data
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///file:testdb?mode=memory&cache=shared&uri=true'
    app.config['WTF_CSRF_ENABLED'] = False
    
    ctx = app.app_context()
    ctx.push()
    # Ensure tables for all models touched in tests are registered
    from app.models.client import Client  # noqa
    from app.models.api_key import ClientApiKey  # noqa
    from app.models.payment import Payment  # noqa
    from app.models.withdrawal import WithdrawalRequest  # noqa
    from app.models.history import PaymentHistoryLog  # noqa
    from app.models.client_wallet import ClientWallet  # noqa
    _db.create_all()
    yield app
    _db.session.remove()
    _db.drop_all()
    ctx.pop()


@pytest.fixture(scope='function')
def db(app):
    """Provide database session for a test (tables already created)."""
    yield _db
    _db.session.rollback()
    _db.session.remove()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def test_client_model(db):
    """Return a reusable test client with seeded API key."""
    from app.models.api_key import ClientApiKey

    client = Client.query.filter_by(email='test@example.com').first()
    test_key = 'test_api_key_12345'
    if not client:
        client = Client(
            company_name='Test Company',
            email='test@example.com',
            is_active=True,
            api_key=test_key
        )
        db.session.add(client)
        db.session.flush()
    else:
        client.api_key = test_key

    # Ensure API key exists (re-use to avoid unique constraint violations)
    api_key = ClientApiKey.query.filter_by(client_id=client.id, key=test_key).first()
    if not api_key:
        api_key = ClientApiKey(
            client_id=client.id,
            name='Test API Key',
            key=test_key,
            key_prefix=test_key[:8] + '...',
            key_hash=ClientApiKey.hash_key(test_key),
            is_active=True,
            permissions=[
                'deposit', 'withdraw', 'status',
                'flat_rate:payment:create',
                'flat_rate:payment:read',
                'flat_rate:payment:list',
                'commission:payment:create',
                'commission:payment:read',
                'commission:payment:list'
            ]
        )
        db.session.add(api_key)
    else:
        api_key.is_active = True
        api_key.permissions = api_key.permissions or []
        required_perms = [
            'flat_rate:payment:create',
            'flat_rate:payment:read',
            'flat_rate:payment:list'
        ]
        for perm in required_perms:
            if perm not in api_key.permissions:
                api_key.permissions.append(perm)

    db.session.commit()

    client.webhook_enabled = True
    client.webhook_url = 'https://client.example.com/webhook'
    client.webhook_secret = 'test_webhook_secret'
    client.test_api_key = api_key
    return client


@pytest.fixture
def test_payment(db, test_client_model):
    """Create a test payment."""
    payment = Payment(
        client_id=test_client_model.id,
        fiat_amount=100.00,
        fiat_currency='USD',
        crypto_amount=99.5,
        crypto_currency='USDT',
        payment_method='crypto',
        transaction_id=f'test_tx_{uuid.uuid4().hex[:8]}',
        status=PaymentStatus.PENDING
    )
    db.session.add(payment)
    db.session.commit()
    return payment


@pytest.fixture
def auth_headers(test_client_model):
    """Return authentication headers for API tests (ensures client + key)."""
    return {
        'Authorization': 'Bearer test_api_key_12345',
        'Content-Type': 'application/json'
    }
