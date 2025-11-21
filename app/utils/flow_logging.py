"""
Flow logging utilities for bank deposits, crypto confirmations, and status transitions.
Day 2: Flow hardening with structured event logging.
"""
import logging
from flask import g

logger = logging.getLogger(__name__)


def log_bank_deposit_event(event_type, transaction, **kwargs):
    """
    Log bank deposit events with structured data.
    
    Args:
        event_type (str): Event type (e.g., 'bank_deposit.initiated', 'bank_deposit.confirmed')
        transaction: BankGatewayTransaction instance
        **kwargs: Additional context
    """
    request_id = getattr(g, 'request_id', 'background')
    
    log_data = {
        'request_id': request_id,
        'event': event_type,
        'transaction_id': transaction.id if transaction else None,
        'reference_code': transaction.reference_code if transaction else None,
        'amount': float(transaction.amount) if transaction and transaction.amount else None,
        'currency': transaction.currency if transaction else None,
        'status': transaction.status if transaction else None,
        'client_site_id': transaction.client_site_id if transaction else None,
    }
    log_data.update(kwargs)
    
    logger.info(
        f"[{request_id}] {event_type}: ref={log_data.get('reference_code')} "
        f"amount={log_data.get('amount')} {log_data.get('currency')} status={log_data.get('status')}",
        extra=log_data
    )


def log_status_transition(entity_type, entity_id, old_status, new_status, **kwargs):
    """
    Log status transitions for payments, withdrawals, transactions.
    
    Args:
        entity_type (str): Type of entity ('payment', 'withdrawal', 'bank_transaction')
        entity_id: ID of the entity
        old_status: Previous status
        new_status: New status
        **kwargs: Additional context
    """
    request_id = getattr(g, 'request_id', 'background')
    
    log_data = {
        'request_id': request_id,
        'event': 'status.transition',
        'entity_type': entity_type,
        'entity_id': entity_id,
        'old_status': str(old_status) if old_status else None,
        'new_status': str(new_status) if new_status else None,
    }
    log_data.update(kwargs)
    
    logger.info(
        f"[{request_id}] status.transition: {entity_type}#{entity_id} "
        f"{log_data.get('old_status')} -> {log_data.get('new_status')}",
        extra=log_data
    )


def log_crypto_confirmation(payment_id, confirmation_count, tx_hash=None, **kwargs):
    """
    Log crypto confirmation events.
    
    Args:
        payment_id: Payment ID
        confirmation_count (int): Number of confirmations
        tx_hash (str, optional): Transaction hash
        **kwargs: Additional context
    """
    request_id = getattr(g, 'request_id', 'background')
    
    log_data = {
        'request_id': request_id,
        'event': 'crypto.confirmation',
        'payment_id': payment_id,
        'confirmation_count': confirmation_count,
        'tx_hash': tx_hash,
    }
    log_data.update(kwargs)
    
    logger.info(
        f"[{request_id}] crypto.confirmation: payment#{payment_id} "
        f"confirmations={confirmation_count} tx={tx_hash}",
        extra=log_data
    )


def log_double_confirmation_rejected(payment_id, reason, **kwargs):
    """
    Log when a double confirmation attempt is rejected.
    
    Args:
        payment_id: Payment ID
        reason (str): Reason for rejection
        **kwargs: Additional context
    """
    request_id = getattr(g, 'request_id', 'background')
    
    log_data = {
        'request_id': request_id,
        'event': 'double_confirmation_rejected',
        'payment_id': payment_id,
        'reason': reason,
    }
    log_data.update(kwargs)
    
    logger.warning(
        f"[{request_id}] double_confirmation_rejected: payment#{payment_id} reason={reason}",
        extra=log_data
    )


def log_balance_change(entity_type, entity_id, old_balance, new_balance, reason, **kwargs):
    """
    Log balance changes for audit trail.
    
    Args:
        entity_type (str): Type of entity ('client', 'wallet')
        entity_id: ID of the entity
        old_balance: Previous balance
        new_balance: New balance
        reason (str): Reason for change
        **kwargs: Additional context
    """
    request_id = getattr(g, 'request_id', 'background')
    
    delta = float(new_balance) - float(old_balance) if old_balance and new_balance else 0
    
    log_data = {
        'request_id': request_id,
        'event': 'balance.change',
        'entity_type': entity_type,
        'entity_id': entity_id,
        'old_balance': float(old_balance) if old_balance else None,
        'new_balance': float(new_balance) if new_balance else None,
        'delta': delta,
        'reason': reason,
    }
    log_data.update(kwargs)
    
    logger.info(
        f"[{request_id}] balance.change: {entity_type}#{entity_id} "
        f"{old_balance} -> {new_balance} (delta={delta:+.2f}) reason={reason}",
        extra=log_data
    )
