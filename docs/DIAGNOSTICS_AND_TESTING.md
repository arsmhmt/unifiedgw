# Diagnostics and Testing Guide

## Overview

This guide covers the 3-day diagnostics, flow hardening, and testing implementation for PayCrypt Unified Gateway.

---

## Day 1 – Wire Diagnostics

### DIAGNOSTICS-PASS Command

**Implemented Features:**
- ✅ X-Request-ID header on all responses
- ✅ Structured error responses with request_id
- ✅ Request/response logging with duration tracking
- ✅ 500 error handler with detailed logging
- ✅ Exception handler for all unhandled errors

### Manual Testing

#### 1. Check API Error Response Format

**Using curl:**
```bash
curl -X POST http://localhost:5000/api/v1/payments \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"invalid": "data"}' \
  -v
```

**Expected Response:**
```json
{
  "error": {
    "code": "invalid_request",
    "message": "Missing required fields",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "details": {
      "missing_fields": ["amount", "currency", "method", "type"]
    }
  }
}
```

**Check Headers:**
```
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

#### 2. Trigger 500 Error and Check Logs

**Create a test route that raises an exception:**
```python
# Add to app/__init__.py temporarily
@app.route('/test-500')
def test_500():
    raise Exception("Test 500 error")
```

**Trigger it:**
```bash
curl http://localhost:5000/test-500
```

**Check logs for:**
```
[550e8400-...] 500 Internal Server Error: GET /test-500
[550e8400-...] request_id=550e8400-... method=GET path=/test-500 error_type=Exception
```

---

## Day 2 – Bank & Crypto Flow Hardening

### FLOW-HARDENING Command

**Implemented Features:**
- ✅ Bank deposit event logging (`bank_deposit.*`)
- ✅ Status transition logging (`status.transition`)
- ✅ Crypto confirmation logging with double-confirmation protection
- ✅ `double_confirmation_rejected` event logging
- ✅ Balance change audit logging

### Manual Testing

#### 1. Trigger Bank Deposit and Check Logs

**Simulate bank deposit:**
```python
from app import create_app, db
from app.models.bank_gateway import BankGatewayTransaction
from app.utils.flow_logging import log_bank_deposit_event

app = create_app()
with app.app_context():
    # Create transaction
    txn = BankGatewayTransaction(
        client_site_id=1,
        amount=100.00,
        currency='USD',
        transaction_type='deposit',
        status='pending',
        reference_code='TEST123'
    )
    db.session.add(txn)
    db.session.commit()
    
    # Log event
    log_bank_deposit_event('bank_deposit.initiated', txn)
    
    # Update status
    txn.status = 'confirmed'
    db.session.commit()
    log_bank_deposit_event('bank_deposit.confirmed', txn)
```

**Check logs for:**
```
[...] bank_deposit.initiated: ref=TEST123 amount=100.0 USD status=pending
[...] status.transition: bank_transaction#1 pending -> confirmed
[...] bank_deposit.confirmed: ref=TEST123 amount=100.0 USD status=confirmed
```

#### 2. Test Double Confirmation Protection

**Simulate crypto confirmation twice:**
```python
from app import create_app, db
from app.models.payment import Payment
from app.models.enums import PaymentStatus

app = create_app()
with app.app_context():
    # Get a pending payment
    payment = Payment.query.filter_by(status=PaymentStatus.PENDING).first()
    
    # First confirmation
    result1 = payment.confirm_payment(tx_hash='0xabc123', confirmations=6)
    print(f"First confirmation: {result1}")  # Should be True
    db.session.commit()
    
    # Second confirmation (should be rejected)
    result2 = payment.confirm_payment(tx_hash='0xabc123', confirmations=12)
    print(f"Second confirmation: {result2}")  # Should be False
```

**Check logs for:**
```
[...] crypto.confirmation: payment#123 confirmations=6 tx=0xabc123
[...] status.transition: payment#123 pending -> completed
[...] double_confirmation_rejected: payment#123 reason=Payment already in completed status
```

**Verify balance NOT double-credited:**
- Check client balance before and after
- Should only increase once

---

## Day 3 – Tests & Smoke

### TESTS-AND-SMOKE Command

**Implemented Features:**
- ✅ pytest configuration with markers
- ✅ Test fixtures for app, db, client, payments
- ✅ API v1 endpoint tests
- ✅ Webhook system tests
- ✅ Flow hardening tests
- ✅ Smoke test script for production readiness

### Running Tests

#### 1. Run pytest

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/test_api_v1.py -v

# Run tests by marker
pytest -m api -v
pytest -m webhook -v
pytest -m integration -v

# Run with coverage
pytest --cov=app --cov-report=html

# Quick run (quiet mode)
pytest -q
```

**Expected Output:**
```
tests/test_api_v1.py::TestPaymentsAPI::test_create_payment_success PASSED
tests/test_api_v1.py::TestPaymentsAPI::test_create_payment_missing_fields PASSED
tests/test_api_v1.py::TestPaymentsAPI::test_get_payment_success PASSED
tests/test_webhooks.py::TestWebhookSystem::test_create_webhook_event PASSED
tests/test_flow_hardening.py::TestFlowHardening::test_double_confirmation_rejected PASSED

======================== 15 passed in 2.34s ========================
```

#### 2. Run Smoke Tests

**Set environment variables:**
```bash
# Windows PowerShell
$env:UNIFIEDGW_BASE_URL = "http://localhost:5000"
$env:UNIFIEDGW_API_KEY = "your_test_api_key"

# Linux/Mac
export UNIFIEDGW_BASE_URL="http://localhost:5000"
export UNIFIEDGW_API_KEY="your_test_api_key"
```

**Run smoke tests:**
```bash
python scripts/smoke_test.py
```

**Expected Output:**
```
============================================================
PayCrypt Unified Gateway - Smoke Tests
============================================================

Timestamp: 2025-11-21T13:30:00
Base URL: http://localhost:5000
API Key: ********************

============================================================
Day 1: Wire Diagnostics
============================================================

✓ PASS Health endpoint responds
    200
✓ PASS X-Request-ID header present
    550e8400-e29b-41d4-a716-446655440000
✓ PASS Standardized error format
    request_id present: True

============================================================
API Functionality
============================================================

✓ PASS API authentication
    Auth working correctly
✓ PASS Payment creation
    Created payment #123

============================================================
Infrastructure
============================================================

✓ PASS Webhook dispatcher script exists
    scripts/dispatch_webhooks.py

============================================================
Summary
============================================================

Total tests: 6
Passed: 6
Success rate: 100.0%

All tests passed! System is ready.
```

---

## Test Markers

Use pytest markers to run specific test categories:

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (database required)
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.webhook` - Webhook system tests
- `@pytest.mark.slow` - Slow-running tests

**Examples:**
```bash
# Run only fast unit tests
pytest -m unit

# Run API and webhook tests
pytest -m "api or webhook"

# Skip slow tests
pytest -m "not slow"
```

---

## Logging Configuration

### Log Levels

- **INFO**: Normal operations, status transitions, confirmations
- **WARNING**: Double confirmation attempts, rate limits
- **ERROR**: Failed operations, exceptions
- **DEBUG**: Detailed request/response data (development only)

### Log Format

All logs include structured data:
```python
{
    'request_id': '550e8400-...',
    'event': 'status.transition',
    'entity_type': 'payment',
    'entity_id': 123,
    'old_status': 'pending',
    'new_status': 'completed',
    'method': 'POST',
    'path': '/api/v1/payments'
}
```

### Viewing Logs

**Development:**
```bash
# Flask default logging
flask run

# With debug logging
FLASK_DEBUG=1 flask run
```

**Production:**
```bash
# Output to file
flask run > logs/app.log 2>&1

# With log rotation (recommended)
# Configure in your deployment (systemd, supervisor, etc.)
```

---

## Troubleshooting

### Tests Failing

**Issue:** `ModuleNotFoundError: No module named 'app'`
**Solution:** Run tests from project root: `cd f:\projects\unified-advanced && pytest`

**Issue:** Database errors in tests
**Solution:** Tests use in-memory SQLite. Check `conftest.py` fixtures.

**Issue:** API tests return 401
**Solution:** Ensure `test_api_key_12345` exists in test fixtures.

### Smoke Tests Failing

**Issue:** Connection refused
**Solution:** Ensure Flask app is running: `flask run`

**Issue:** 401 Unauthorized
**Solution:** Set valid `UNIFIEDGW_API_KEY` environment variable.

**Issue:** Missing X-Request-ID header
**Solution:** Ensure request tracking middleware is initialized in `app/__init__.py`.

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest -v --cov=app
      - name: Run smoke tests
        env:
          UNIFIEDGW_BASE_URL: http://localhost:5000
          UNIFIEDGW_API_KEY: ${{ secrets.TEST_API_KEY }}
        run: |
          flask run &
          sleep 5
          python scripts/smoke_test.py
```

---

## Next Steps

1. **Add more test coverage:**
   - Bank gateway flows
   - Withdrawal processing
   - Commission calculations

2. **Performance testing:**
   - Load test API endpoints
   - Webhook delivery under load

3. **Security testing:**
   - API key rotation
   - SQL injection tests
   - XSS prevention

4. **Monitoring:**
   - Set up error tracking (Sentry)
   - Add metrics (Prometheus)
   - Create dashboards (Grafana)

---

## Support

For issues or questions:
- Check logs first: Look for request_id and error messages
- Run smoke tests: `python scripts/smoke_test.py`
- Review test output: `pytest -v`
- Contact: support@paycrypt.com
