"""
Wallet provider execution utilities
Handles actual withdrawal execution through configured wallet providers
"""

import requests
from decimal import Decimal
from flask import current_app

from app import db
from app.models import WithdrawalRequest, ClientWallet, WalletStatus, WalletType
from app.models.enums import WithdrawalStatus
from ..utils.timezone import now_eest


class WalletExecutionError(Exception):
    """Base exception for wallet execution errors"""
    pass


def execute_withdrawal_via_provider(withdrawal_id):
    """
    Execute a withdrawal through the client's configured wallet provider
    
    Args:
        withdrawal_id: ID of the WithdrawalRequest to execute
        
    Returns:
        dict: Execution result with status and transaction details
        
    Raises:
        WalletExecutionError: If execution fails
    """
    withdrawal = WithdrawalRequest.query.get(withdrawal_id)
    if not withdrawal:
        raise WalletExecutionError(f"Withdrawal {withdrawal_id} not found")
    
    if withdrawal.status != WithdrawalStatus.APPROVED:
        raise WalletExecutionError(f"Withdrawal {withdrawal_id} is not approved (status: {withdrawal.status.value})")
    
    # Get wallet configuration from metadata
    metadata = withdrawal.metadata or {}
    wallet_id = metadata.get('wallet_id')
    
    if not wallet_id:
        raise WalletExecutionError("No wallet configuration found in withdrawal metadata")
    
    wallet = ClientWallet.query.get(wallet_id)
    if not wallet or wallet.status != WalletStatus.ACTIVE:
        raise WalletExecutionError(f"Wallet {wallet_id} not found or inactive")
    
    if wallet.wallet_type != WalletType.CUSTOM_API:
        raise WalletExecutionError(f"Wallet {wallet_id} does not support API execution (type: {wallet.wallet_type.value})")
    
    if not wallet.api_endpoint or not wallet.api_key:
        raise WalletExecutionError(f"Wallet {wallet_id} API configuration incomplete")
    
    # Prepare withdrawal request payload
    payload = {
        'withdrawal_id': withdrawal.id,
        'amount': float(withdrawal.net_amount),  # Send net amount after commission
        'currency': withdrawal.currency,
        'network': metadata.get('crypto_network'),
        'address': metadata.get('wallet_address'),
        'client_reference': withdrawal.id
    }
    
    try:
        current_app.logger.info(f"Executing withdrawal {withdrawal_id} via wallet provider {wallet_id}")
        
        # Call wallet provider API
        response = requests.post(
            f"{wallet.api_endpoint}/withdraw",
            json=payload,
            headers={
                'Authorization': f'Bearer {wallet.api_key}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract transaction details
            provider_tx_id = data.get('transaction_id') or data.get('txId') or data.get('id')
            blockchain_tx_hash = data.get('txid') or data.get('tx_hash') or data.get('hash')
            status = (data.get('status') or 'processing').lower()
            
            # Update withdrawal metadata
            if not withdrawal.metadata:
                withdrawal.metadata = {}
            
            withdrawal.metadata['provider_tx_id'] = provider_tx_id
            withdrawal.metadata['blockchain_tx_hash'] = blockchain_tx_hash
            withdrawal.metadata['provider_response'] = data
            withdrawal.metadata['executed_at'] = now_eest().isoformat()
            
            # Update withdrawal status
            if status in ['completed', 'success']:
                withdrawal.status = WithdrawalStatus.COMPLETED
            elif status in ['processing', 'pending']:
                withdrawal.status = WithdrawalStatus.PROCESSING
            else:
                withdrawal.status = WithdrawalStatus.PROCESSING  # Default to processing
            
            db.session.commit()
            
            current_app.logger.info(
                f"Withdrawal {withdrawal_id} executed successfully. Provider TX: {provider_tx_id}, Status: {withdrawal.status.value}"
            )
            
            return {
                'success': True,
                'withdrawal_id': withdrawal.id,
                'provider_tx_id': provider_tx_id,
                'blockchain_tx_hash': blockchain_tx_hash,
                'status': withdrawal.status.value,
                'message': 'Withdrawal executed via provider'
            }
        
        else:
            error_msg = f"Provider API returned status {response.status_code}"
            try:
                error_data = response.json()
                error_msg = error_data.get('error') or error_data.get('message') or error_msg
            except:
                pass
            
            raise WalletExecutionError(error_msg)
    
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Wallet provider API call failed: {str(e)}")
        raise WalletExecutionError(f"Provider API unavailable: {str(e)}")
    
    except Exception as e:
        current_app.logger.error(f"Withdrawal execution error: {str(e)}")
        raise WalletExecutionError(f"Execution failed: {str(e)}")


def get_withdrawal_status_from_provider(withdrawal_id):
    """
    Query withdrawal status from the provider
    
    Args:
        withdrawal_id: ID of the WithdrawalRequest
        
    Returns:
        dict: Status information from provider
    """
    withdrawal = WithdrawalRequest.query.get(withdrawal_id)
    if not withdrawal:
        raise WalletExecutionError(f"Withdrawal {withdrawal_id} not found")
    
    metadata = withdrawal.metadata or {}
    wallet_id = metadata.get('wallet_id')
    provider_tx_id = metadata.get('provider_tx_id')
    
    if not wallet_id or not provider_tx_id:
        raise WalletExecutionError("Withdrawal not executed via provider")
    
    wallet = ClientWallet.query.get(wallet_id)
    if not wallet or wallet.wallet_type != WalletType.CUSTOM_API:
        raise WalletExecutionError("Wallet not configured for API queries")
    
    try:
        response = requests.get(
            f"{wallet.api_endpoint}/withdrawal/{provider_tx_id}",
            headers={
                'Authorization': f'Bearer {wallet.api_key}',
                'Content-Type': 'application/json'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            status = (data.get('status') or 'unknown').lower()
            
            # Update local status if changed
            if status == 'completed' and withdrawal.status != WithdrawalStatus.COMPLETED:
                withdrawal.status = WithdrawalStatus.COMPLETED
                withdrawal.metadata['status_updated_at'] = now_eest().isoformat()
                db.session.commit()
                current_app.logger.info(f"Withdrawal {withdrawal_id} status updated to COMPLETED")
            
            return {
                'success': True,
                'withdrawal_id': withdrawal.id,
                'provider_status': status,
                'local_status': withdrawal.status.value,
                'details': data
            }
        else:
            raise WalletExecutionError(f"Provider returned status {response.status_code}")
    
    except requests.exceptions.RequestException as e:
        raise WalletExecutionError(f"Provider query failed: {str(e)}")
