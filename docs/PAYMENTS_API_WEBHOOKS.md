# Payments API v1 & Webhooks Implementation Guide

## Overview

This document describes the implementation of the clean v1 Payments API and Webhook/Event system for the PayCrypt Unified Gateway.

## What Was Implemented

### Part A: Payments API v1

✅ **Canonical Payment Model**
- Uses existing unified `Payment` model from `app/models/payment.py`
- Fields: `id`, `client_id`, `amount`, `currency`, `method`, `type`, `status`, `created_at`, `updated_at`
- Added payment constants in `app/payment/constants.py`:
  - `PaymentMethod` (crypto, bank)
  - `PaymentType` (deposit, withdraw)
  - `APIErrorCode` (standardized error codes)

✅ **API Blueprint** (`app/api/v1/`)
- **POST** `/api/v1/payments` - Create payment
- **GET** `/api/v1/payments/<payment_id>` - Get single payment
- **GET** `/api/v1/payments` - List/filter payments (with pagination, status, date range filters)
- JSON-only responses
- Standardized error format: `{"error": {"code": "...", "message": "...", "details": {...}}}`
- Bearer token authentication via API keys (from `clients.api_key`)

✅ **Request/Response Schemas**
- Documented in `docs/API.md`
- Input validation for amount, currency, method, type
- Comprehensive response fields including crypto amounts, transaction IDs, timestamps

### Part B: Webhook/Event System

✅ **Data Model** (`app/models/webhook_event.py`)
- `WebhookEvent` model with fields:
  - `id` (UUID string)
  - `client_id`, `payment_id` (FKs)
  - `event_type` (payment.created, payment.pending, etc.)
  - `status` (pending, delivered, failed)
  - `attempts`, `max_attempts` (retry tracking)
  - `next_attempt_at` (exponential backoff)
  - `payload` (JSON)
  - `last_error`, `last_response_code`
  - `delivered_at`, `created_at`, `updated_at`

✅ **Service Layer** (`app/events/service.py`)
- `create_event(payment, event_type)` - Create webhook event
- `mark_event_delivered(event, response_code)` - Mark successful delivery
- `mark_event_failed(event, error, response_code)` - Mark failed with retry scheduling

✅ **HMAC Signing** (`app/events/signing.py`)
- `sign_payload(secret, timestamp, payload)` - Generate HMAC-SHA256 signature
- `verify_signature(...)` - Verify incoming webhook signatures
- Signing format: `HMAC-SHA256(secret, timestamp + "." + json_payload)`

✅ **Webhook Dispatcher** (`app/events/dispatcher.py`)
- `dispatch_pending_events(limit, timeout)` - Fetch and send pending events
- `dispatch_event(event, timeout)` - Send single event with retry logic
- Includes headers: `X-Paycrypt-Event`, `X-Paycrypt-Timestamp`, `X-Paycrypt-Signature`, `X-Paycrypt-Event-Id`
- Exponential backoff: 1min → 5min → 15min → 1hr → 4hr (6 attempts max)

✅ **CLI Script** (`scripts/dispatch_webhooks.py`)
- Run manually: `python scripts/dispatch_webhooks.py --limit 100 --timeout 10`
- Can be scheduled via cron or supervisor for continuous delivery

✅ **Client Configuration UI**
- Template: `app/templates/client/webhook_settings.html`
- Routes in `app/routes/client.py`:
  - `GET /client/webhook-settings` - Display settings page
  - `POST /client/webhook-settings/update` - Update webhook config
- Fields: `webhook_enabled`, `webhook_url`, `webhook_secret`
- Auto-generates secret if not provided

### Part C: Wiring & Lifecycle

✅ **Payment Status Change Hooks**
- SQLAlchemy `after_update` event listener in `app/models/payment.py`
- Automatically emits webhook events on status transitions:
  - `payment.created`
  - `payment.pending`
  - `payment.approved`
  - `payment.completed`
  - `payment.failed`
  - `payment.rejected`
  - `payment.cancelled`

✅ **Documentation**
- Comprehensive API docs in `docs/API.md` with:
  - Authentication guide
  - All endpoint specs with request/response examples
  - Webhook configuration and verification
  - Code examples in Python, Node.js, PHP
  - Error handling reference

---

## Database Migration

### Step 1: Update Migration File

The migration file is located at:
```
migrations/versions/add_webhook_events.py
```

**Important:** Update the `down_revision` field to match your latest migration ID:

```python
# Open the migration file and find this line:
down_revision = None  # Update this to the latest migration ID in your project
```

To find your latest migration ID:
```bash
# List all migrations
ls migrations/versions/

# Or check the database
flask db current
```

### Step 2: Run Migration

```bash
# Generate migration (if needed)
flask db migrate -m "Add webhook events and client webhook config"

# Review the generated migration
# Then apply it:
flask db upgrade
```

The migration will:
1. Create `webhook_events` table with indexes
2. Add `webhook_url`, `webhook_secret`, `webhook_enabled` columns to `clients` table

### Step 3: Verify Migration

```bash
# Check current migration status
flask db current

# Verify tables exist
flask shell
>>> from app.models.webhook_event import WebhookEvent
>>> from app.models.client import Client
>>> WebhookEvent.query.count()
>>> Client.query.first().webhook_url  # Should not error
```

---

## Testing the System

### 1. Test API Authentication

```bash
# Get a client's API key from the database or client dashboard
# Then test authentication:

curl -X GET http://localhost:5000/api/v1/payments \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Expected: 200 OK with payment list or empty array.

### 2. Test Payment Creation

```bash
curl -X POST http://localhost:5000/api/v1/payments \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.00,
    "currency": "USD",
    "method": "crypto",
    "type": "deposit",
    "crypto_currency": "USDT",
    "description": "Test payment"
  }'
```

Expected: 201 Created with payment details.

### 3. Test Payment Retrieval

```bash
# Use the payment ID from the creation response
curl -X GET http://localhost:5000/api/v1/payments/123 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Expected: 200 OK with payment details.

### 4. Configure Webhooks

1. Log in to client dashboard
2. Navigate to `/client/webhook-settings`
3. Enable webhooks
4. Enter webhook URL (e.g., `https://webhook.site/unique-id` for testing)
5. Generate or enter webhook secret
6. Save settings

### 5. Test Webhook Event Creation

```python
# In Flask shell
flask shell

from app.models.payment import Payment
from app.models.enums import PaymentStatus
from app import db

# Get a test payment
payment = Payment.query.first()

# Change its status to trigger webhook
payment.status = PaymentStatus.COMPLETED
db.session.commit()

# Check if webhook event was created
from app.models.webhook_event import WebhookEvent
events = WebhookEvent.query.filter_by(payment_id=payment.id).all()
print(f"Created {len(events)} webhook events")
for event in events:
    print(f"  - {event.event_type}: {event.status}")
```

### 6. Test Webhook Dispatcher

```bash
# Run the dispatcher manually
python scripts/dispatch_webhooks.py --verbose

# Expected output:
# Dispatching up to 100 pending webhook events...
# Webhook dispatch complete:
#   Processed: 1
#   Delivered: 1
#   Failed: 0
#   Skipped: 0
```

### 7. Verify Webhook Delivery

Check your webhook endpoint (e.g., webhook.site) to see:
- POST request received
- Headers: `X-Paycrypt-Event`, `X-Paycrypt-Timestamp`, `X-Paycrypt-Signature`
- Payload with payment data

### 8. Test Webhook Signature Verification

```python
# Example Python verification
import hmac
import hashlib
import json

webhook_secret = "your_webhook_secret"
timestamp = "2025-11-21T12:00:00Z"
payload = {"event_type": "payment.completed", "payment": {...}}

# Create signing string
signing_string = f"{timestamp}.{json.dumps(payload, sort_keys=True, separators=(',', ':'))}"

# Calculate signature
signature = hmac.new(
    webhook_secret.encode('utf-8'),
    signing_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()

print(f"Expected signature: {signature}")
```

---

## Scheduling Webhook Dispatcher

### Option 1: Cron (Linux/Mac)

```bash
# Edit crontab
crontab -e

# Add line to run every minute
* * * * * cd /path/to/unified-advanced && /path/to/venv/bin/python scripts/dispatch_webhooks.py >> /var/log/paycrypt_webhooks.log 2>&1
```

### Option 2: Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily, repeat every 1 minute
4. Action: Start a program
   - Program: `C:\path\to\venv\Scripts\python.exe`
   - Arguments: `scripts\dispatch_webhooks.py`
   - Start in: `F:\projects\unified-advanced`

### Option 3: Supervisor (Production)

```ini
# /etc/supervisor/conf.d/paycrypt_webhooks.conf
[program:paycrypt_webhooks]
command=/path/to/venv/bin/python scripts/dispatch_webhooks.py
directory=/path/to/unified-advanced
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/paycrypt_webhooks.err.log
stdout_logfile=/var/log/paycrypt_webhooks.out.log
```

Then:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start paycrypt_webhooks
```

---

## Troubleshooting

### Webhooks Not Being Created

**Check:**
1. Client has `webhook_enabled = True`
2. Client has `webhook_url` configured
3. Payment status is actually changing (check SQLAlchemy event listener)

**Debug:**
```python
flask shell
from app.models.client import Client
client = Client.query.first()
print(f"Webhook enabled: {client.webhook_enabled}")
print(f"Webhook URL: {client.webhook_url}")
print(f"Webhook secret: {client.webhook_secret}")
```

### Webhooks Not Being Delivered

**Check:**
1. Run dispatcher manually: `python scripts/dispatch_webhooks.py --verbose`
2. Check webhook event status: `WebhookEvent.query.filter_by(status='pending').all()`
3. Check `last_error` field for failure reasons

**Debug:**
```python
flask shell
from app.models.webhook_event import WebhookEvent
pending = WebhookEvent.query.filter_by(status='pending').all()
for event in pending:
    print(f"Event {event.id}: attempts={event.attempts}, next_attempt={event.next_attempt_at}")
    if event.last_error:
        print(f"  Last error: {event.last_error}")
```

### API Authentication Failing

**Check:**
1. API key exists in `clients.api_key` column
2. Client is active: `client.is_active = True`
3. Authorization header format: `Bearer <api_key>`

**Debug:**
```python
flask shell
from app.models.client import Client
client = Client.query.filter_by(api_key='YOUR_KEY').first()
print(f"Client found: {client}")
print(f"Is active: {client.is_active if client else 'N/A'}")
```

---

## Architecture Notes

### Why SQLAlchemy Event Listener?

The `@event.listens_for(Payment, 'after_update')` decorator ensures webhook events are created automatically whenever payment status changes, regardless of where the change happens (admin panel, API, background job, etc.). This is more reliable than manual calls.

### Why Separate Dispatcher Script?

Decoupling webhook delivery from the main app allows:
- Independent scaling (run multiple dispatcher workers)
- Retry logic without blocking requests
- Easy monitoring and logging
- Graceful failure handling

### Why HMAC Signatures?

HMAC-SHA256 signatures ensure:
- Webhook authenticity (only PayCrypt can generate valid signatures)
- Payload integrity (tampering detection)
- Replay attack prevention (via timestamp validation)

---

## Next Steps

1. **Add Rate Limiting:** Implement per-client rate limits on API endpoints
2. **Add Webhook Logs:** Create `WebhookLog` model for detailed delivery history
3. **Add Webhook Testing UI:** Allow clients to test webhooks from dashboard
4. **Add Webhook Retry UI:** Allow clients to manually retry failed webhooks
5. **Add API Usage Analytics:** Track API calls per client for billing/monitoring
6. **Add More Event Types:** Extend to withdrawal events, balance updates, etc.

---

## Support

For questions or issues:
- Check `docs/API.md` for API reference
- Review code comments in `app/api/v1/` and `app/events/`
- Contact: support@paycrypt.com
