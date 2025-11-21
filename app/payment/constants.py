"""
Payment API constants and enums for v1 API.
"""
from enum import Enum


class PaymentMethod(Enum):
    """Payment methods supported by the API."""
    CRYPTO = 'crypto'
    BANK = 'bank'


class PaymentType(Enum):
    """Payment types (direction)."""
    DEPOSIT = 'deposit'
    WITHDRAW = 'withdraw'


class WebhookEventType(Enum):
    """Webhook event types emitted by the system."""
    PAYMENT_CREATED = 'payment.created'
    PAYMENT_PENDING = 'payment.pending'
    PAYMENT_APPROVED = 'payment.approved'
    PAYMENT_COMPLETED = 'payment.completed'
    PAYMENT_FAILED = 'payment.failed'
    PAYMENT_REJECTED = 'payment.rejected'
    PAYMENT_CANCELLED = 'payment.cancelled'


class WebhookEventStatus(Enum):
    """Status of a webhook event delivery."""
    PENDING = 'pending'
    DELIVERED = 'delivered'
    FAILED = 'failed'


# API error codes
class APIErrorCode:
    """Standardized API error codes."""
    INVALID_REQUEST = 'invalid_request'
    AUTHENTICATION_FAILED = 'authentication_failed'
    RESOURCE_NOT_FOUND = 'resource_not_found'
    INSUFFICIENT_BALANCE = 'insufficient_balance'
    RATE_LIMIT_EXCEEDED = 'rate_limit_exceeded'
    INTERNAL_ERROR = 'internal_error'
    INVALID_API_KEY = 'invalid_api_key'
    DISABLED_API_KEY = 'disabled_api_key'
    MISSING_PARAMETER = 'missing_parameter'
    INVALID_PARAMETER = 'invalid_parameter'
