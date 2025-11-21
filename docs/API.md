# PayCrypt API v1 Documentation

This guide covers the PayCrypt v1 Payments API and Webhook system.

## Table of Contents

1. [Authentication](#authentication)
2. [Payments API](#payments-api)
3. [Webhooks](#webhooks)
4. [Error Handling](#error-handling)
5. [Code Examples](#code-examples)

---

## Authentication

All API requests require authentication via API key using the `Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

### Getting Your API Key

1. Log in to your PayCrypt client dashboard
2. Navigate to **API Management**
3. Create a new API key with appropriate permissions
4. Copy and securely store your API key

### Security Best Practices

- Never expose API keys in client-side code
- Use environment variables to store keys
- Rotate keys periodically
- Use different keys for development and production

---

## Payments API

### Base URL

```
https://your-paycrypt-domain.com/api/v1
```

### Endpoints

#### 1. Create Payment

**POST** `/api/v1/payments`

Create a new payment (deposit or withdrawal).

**Request Headers:**
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

**Request Body:**
```json
{
  "amount": 100.00,
  "currency": "USD",
  "method": "crypto",
  "type": "deposit",
  "crypto_currency": "USDT",
  "crypto_network": "TRC20",
  "client_reference": "order_123",
  "description": "Payment for order 123"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `amount` | number | Yes | Payment amount (fiat) |
| `currency` | string | Yes | Fiat currency code (USD, EUR, TRY, etc.) |
| `method` | string | Yes | Payment method: `crypto` or `bank` |
| `type` | string | Yes | Payment type: `deposit` or `withdraw` |
| `crypto_currency` | string | No | Crypto currency (BTC, USDT, ETH, etc.) |
| `crypto_network` | string | No | Network for crypto (TRC20, ERC20, etc.) |
| `client_reference` | string | No | Your internal reference ID |
| `description` | string | No | Payment description |

**Response (201 Created):**
```json
{
  "id": 123,
  "transaction_id": "pay_abc123def456",
  "status": "pending",
  "method": "crypto",
  "type": "deposit",
  "amount": 100.00,
  "currency": "USD",
  "crypto_amount": 99.5,
  "crypto_currency": "USDT",
  "crypto_network": "TRC20",
  "description": "Payment for order 123",
  "created_at": "2025-11-21T12:00:00Z"
}
```

---

#### 2. Get Payment

**GET** `/api/v1/payments/{payment_id}`

Retrieve details of a specific payment.

**Request Headers:**
```
Authorization: Bearer YOUR_API_KEY
```

**Response (200 OK):**
```json
{
  "id": 123,
  "transaction_id": "pay_abc123def456",
  "status": "completed",
  "method": "crypto",
  "amount": 100.00,
  "currency": "USD",
  "crypto_amount": 99.5,
  "crypto_currency": "USDT",
  "description": "Payment for order 123",
  "created_at": "2025-11-21T12:00:00Z",
  "updated_at": "2025-11-21T12:05:00Z"
}
```

---

#### 3. List Payments

**GET** `/api/v1/payments`

List all payments for your account with optional filters.

**Request Headers:**
```
Authorization: Bearer YOUR_API_KEY
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `pending`, `approved`, `completed`, `failed`, `rejected`, `cancelled` |
| `page` | integer | Page number (default: 1) |
| `per_page` | integer | Items per page (default: 20, max: 100) |
| `from_date` | string | Filter from date (ISO 8601 format) |
| `to_date` | string | Filter to date (ISO 8601 format) |

**Example Request:**
```
GET /api/v1/payments?status=completed&page=1&per_page=20
```

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": 123,
      "transaction_id": "pay_abc123def456",
      "status": "completed",
      "method": "crypto",
      "amount": 100.00,
      "currency": "USD",
      "crypto_amount": 99.5,
      "crypto_currency": "USDT",
      "description": "Payment for order 123",
      "created_at": "2025-11-21T12:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "pages": 8
  }
}
```

---

## Webhooks

Webhooks allow you to receive real-time notifications when payment status changes.

### Configuration

1. Log in to your PayCrypt client dashboard
2. Navigate to **Webhook Settings**
3. Enable webhooks
4. Enter your webhook URL
5. Generate or provide a webhook secret
6. Save settings

### Webhook Events

PayCrypt sends the following webhook events:

| Event Type | Description |
|------------|-------------|
| `payment.created` | New payment created |
| `payment.pending` | Payment is pending |
| `payment.approved` | Payment approved |
| `payment.completed` | Payment completed successfully |
| `payment.failed` | Payment failed |
| `payment.rejected` | Payment rejected |
| `payment.cancelled` | Payment cancelled |

### Webhook Payload

Webhooks are sent as HTTP POST requests to your configured URL.

**Headers:**
```
Content-Type: application/json
X-Paycrypt-Event: payment.completed
X-Paycrypt-Timestamp: 2025-11-21T12:05:00Z
X-Paycrypt-Signature: abc123def456...
X-Paycrypt-Event-Id: evt_abc123
```

**Payload:**
```json
{
  "event_type": "payment.completed",
  "payment": {
    "id": 123,
    "client_id": 456,
    "amount": 100.00,
    "currency": "USD",
    "fiat_amount": 100.00,
    "fiat_currency": "USD",
    "crypto_amount": 99.5,
    "crypto_currency": "USDT",
    "status": "completed",
    "payment_method": "crypto",
    "transaction_id": "pay_abc123def456",
    "description": "Payment for order 123",
    "created_at": "2025-11-21T12:00:00Z",
    "updated_at": "2025-11-21T12:05:00Z"
  },
  "timestamp": "2025-11-21T12:05:00Z"
}
```

### Verifying Webhook Signatures

To ensure webhooks are from PayCrypt, verify the HMAC signature:

**Signature Calculation:**
```
HMAC-SHA256(webhook_secret, timestamp + "." + json_payload)
```

**Python Example:**
```python
import hmac
import hashlib
import json

def verify_webhook(request, webhook_secret):
    timestamp = request.headers.get('X-Paycrypt-Timestamp')
    signature = request.headers.get('X-Paycrypt-Signature')
    payload = request.body.decode('utf-8')
    
    # Create signing string
    signing_string = f"{timestamp}.{payload}"
    
    # Calculate expected signature
    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        signing_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Compare signatures
    return hmac.compare_digest(expected_signature, signature)
```

**Node.js Example:**
```javascript
const crypto = require('crypto');

function verifyWebhook(req, webhookSecret) {
  const timestamp = req.headers['x-paycrypt-timestamp'];
  const signature = req.headers['x-paycrypt-signature'];
  const payload = JSON.stringify(req.body);
  
  // Create signing string
  const signingString = `${timestamp}.${payload}`;
  
  // Calculate expected signature
  const expectedSignature = crypto
    .createHmac('sha256', webhookSecret)
    .update(signingString)
    .digest('hex');
  
  // Compare signatures
  return crypto.timingSafeEqual(
    Buffer.from(expectedSignature),
    Buffer.from(signature)
  );
}
```

**PHP Example:**
```php
function verifyWebhook($request, $webhookSecret) {
    $timestamp = $request->header('X-Paycrypt-Timestamp');
    $signature = $request->header('X-Paycrypt-Signature');
    $payload = $request->getContent();
    
    // Create signing string
    $signingString = $timestamp . '.' . $payload;
    
    // Calculate expected signature
    $expectedSignature = hash_hmac('sha256', $signingString, $webhookSecret);
    
    // Compare signatures
    return hash_equals($expectedSignature, $signature);
}
```

### Retry Logic

PayCrypt automatically retries failed webhook deliveries:

- **Attempt 1:** Immediate
- **Attempt 2:** After 1 minute
- **Attempt 3:** After 5 minutes
- **Attempt 4:** After 15 minutes
- **Attempt 5:** After 1 hour
- **Attempt 6:** After 4 hours (final)

Webhooks are considered successful if your endpoint returns a 2xx HTTP status code.

---

## Error Handling

All API errors follow a standardized format:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Missing required field: amount",
    "details": {
      "missing_fields": ["amount"]
    }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `invalid_request` | 400 | Request validation failed |
| `authentication_failed` | 401 | Invalid or missing API key |
| `resource_not_found` | 404 | Payment or resource not found |
| `rate_limit_exceeded` | 429 | Too many requests |
| `internal_error` | 500 | Server error |

---

## Code Examples

### Python (requests)

```python
import requests

API_KEY = 'your_api_key_here'
BASE_URL = 'https://your-paycrypt-domain.com/api/v1'

headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

# Create payment
payment_data = {
    'amount': 100.00,
    'currency': 'USD',
    'method': 'crypto',
    'type': 'deposit',
    'crypto_currency': 'USDT',
    'description': 'Test payment'
}

response = requests.post(
    f'{BASE_URL}/payments',
    headers=headers,
    json=payment_data
)

if response.status_code == 201:
    payment = response.json()
    print(f"Payment created: {payment['transaction_id']}")
else:
    print(f"Error: {response.json()}")

# Get payment
payment_id = 123
response = requests.get(
    f'{BASE_URL}/payments/{payment_id}',
    headers=headers
)

if response.status_code == 200:
    payment = response.json()
    print(f"Payment status: {payment['status']}")
```

### Node.js (fetch)

```javascript
const API_KEY = 'your_api_key_here';
const BASE_URL = 'https://your-paycrypt-domain.com/api/v1';

const headers = {
  'Authorization': `Bearer ${API_KEY}`,
  'Content-Type': 'application/json'
};

// Create payment
async function createPayment() {
  const response = await fetch(`${BASE_URL}/payments`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      amount: 100.00,
      currency: 'USD',
      method: 'crypto',
      type: 'deposit',
      crypto_currency: 'USDT',
      description: 'Test payment'
    })
  });
  
  if (response.ok) {
    const payment = await response.json();
    console.log(`Payment created: ${payment.transaction_id}`);
  } else {
    const error = await response.json();
    console.error('Error:', error);
  }
}

// Get payment
async function getPayment(paymentId) {
  const response = await fetch(`${BASE_URL}/payments/${paymentId}`, {
    method: 'GET',
    headers
  });
  
  if (response.ok) {
    const payment = await response.json();
    console.log(`Payment status: ${payment.status}`);
  }
}
```

### PHP (cURL)

```php
<?php
$apiKey = 'your_api_key_here';
$baseUrl = 'https://your-paycrypt-domain.com/api/v1';

// Create payment
$paymentData = [
    'amount' => 100.00,
    'currency' => 'USD',
    'method' => 'crypto',
    'type' => 'deposit',
    'crypto_currency' => 'USDT',
    'description' => 'Test payment'
];

$ch = curl_init($baseUrl . '/payments');
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($paymentData));
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Authorization: Bearer ' . $apiKey,
    'Content-Type: application/json'
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($httpCode === 201) {
    $payment = json_decode($response, true);
    echo "Payment created: " . $payment['transaction_id'];
} else {
    echo "Error: " . $response;
}

// Get payment
$paymentId = 123;
$ch = curl_init($baseUrl . '/payments/' . $paymentId);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Authorization: Bearer ' . $apiKey
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($httpCode === 200) {
    $payment = json_decode($response, true);
    echo "Payment status: " . $payment['status'];
}
?>
```

---

## Support

For API support, contact:
- **Email:** support@paycrypt.com
- **Telegram:** @PayCryptSupport
- **Documentation:** https://docs.paycrypt.com
