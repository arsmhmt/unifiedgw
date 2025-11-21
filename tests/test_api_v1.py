"""
Tests for v1 Payments API.
Day 3: API testing.
"""
import pytest
import json


@pytest.mark.api
class TestPaymentsAPI:
    """Test v1 Payments API endpoints."""
    
    def test_create_payment_success(self, client, test_client_model, auth_headers):
        """Test successful payment creation."""
        payload = {
            'amount': 100.00,
            'currency': 'USD',
            'method': 'crypto',
            'type': 'deposit',
            'crypto_currency': 'USDT',
            'description': 'Test payment'
        }
        
        response = client.post(
            '/api/v1/payments',
            data=json.dumps(payload),
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert 'id' in data
        assert 'transaction_id' in data
        assert data['status'] == 'pending'
        assert data['amount'] == 100.00
        assert data['currency'] == 'USD'
        
        # Day 1: Check X-Request-ID header
        assert 'X-Request-ID' in response.headers
    
    def test_create_payment_missing_fields(self, client, auth_headers):
        """Test payment creation with missing required fields."""
        payload = {
            'amount': 100.00
            # Missing currency, method, type
        }
        
        response = client.post(
            '/api/v1/payments',
            data=json.dumps(payload),
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert data['error']['code'] == 'invalid_request'
        assert 'missing_fields' in data['error'].get('details', {})
        
        # Day 1: Check X-Request-ID in error response
        assert 'request_id' in data['error']
    
    def test_create_payment_invalid_auth(self, client):
        """Test payment creation with invalid API key."""
        payload = {
            'amount': 100.00,
            'currency': 'USD',
            'method': 'crypto',
            'type': 'deposit'
        }
        
        response = client.post(
            '/api/v1/payments',
            data=json.dumps(payload),
            headers={
                'Authorization': 'Bearer invalid_key',
                'Content-Type': 'application/json'
            }
        )
        
        assert response.status_code == 401
        data = response.get_json()
        assert data['error']['code'] == 'authentication_failed'
    
    def test_get_payment_success(self, client, test_payment, auth_headers):
        """Test retrieving a payment."""
        response = client.get(
            f'/api/v1/payments/{test_payment.id}',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == test_payment.id
        assert data['status'] == 'pending'
    
    def test_get_payment_not_found(self, client, auth_headers):
        """Test retrieving non-existent payment."""
        response = client.get(
            '/api/v1/payments/99999',
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['error']['code'] == 'resource_not_found'
    
    def test_list_payments(self, client, test_payment, auth_headers):
        """Test listing payments."""
        response = client.get(
            '/api/v1/payments',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'data' in data
        assert 'pagination' in data
        assert len(data['data']) > 0
    
    def test_list_payments_with_filters(self, client, test_payment, auth_headers):
        """Test listing payments with status filter."""
        response = client.get(
            '/api/v1/payments?status=pending&per_page=10',
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert all(p['status'] == 'pending' for p in data['data'])
