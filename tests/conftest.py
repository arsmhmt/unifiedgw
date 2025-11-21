"""
Pytest configuration and fixtures.
Day 3: Test infrastructure.
"""
import pytest
import os
from app import create_app, db as _db
from app.models.client import Client
from app.models.payment import Payment
from app.models.enums import PaymentStatus


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    return app


@pytest.fixture(scope='function')
def db(app):
    """Create database for testing."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def test_client_model(db):
    """Create a test client in the database."""
    client = Client(
        company_name='Test Company',
        email='test@example.com',
        api_key='test_api_key_12345',
        is_active=True,
        webhook_enabled=True,
        webhook_url='https://example.com/webhook',
        webhook_secret='test_secret_key'
    )
    db.session.add(client)
    db.session.commit()
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
        transaction_id='test_tx_123',
        status=PaymentStatus.PENDING
    )
    db.session.add(payment)
    db.session.commit()
    return payment


@pytest.fixture
def auth_headers():
    """Return authentication headers for API tests."""
    return {
        'Authorization': 'Bearer test_api_key_12345',
        'Content-Type': 'application/json'
    }
