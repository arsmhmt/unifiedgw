# Import order is important to avoid circular imports
from app.extensions import db

# Create base classes
Base = db.Model
BaseModel = db.Model

# Import enums after db is defined
from app.models.enums import PaymentStatus, AuditActionType, CommissionSnapshottingType, ClientEntityType, SettingType, SettingKey

# Import models that don't have foreign key dependencies first
from app.models.api_usage import ApiUsage
from app.models.document import Document
from app.models.notification import NotificationPreference, NotificationType, NotificationEvent, AdminNotification, AdminNotificationType
from app.models.report import Report, ReportType, ReportStatus
from app.models.audit import AuditTrail
from app.models.login_history import LoginHistory, LoginAttemptLimiter

# For backward compatibility
AuditLog = AuditTrail

# Re-export enums for easier access
__all__ = [
    'Base', 'BaseModel', 'db',
    'PaymentStatus', 'AuditActionType', 'CommissionSnapshottingType', 
    'ClientEntityType', 'SettingType', 'SettingKey',
    'PlanType', 'BillingCycle', 'SubscriptionStatus',
    'WalletProvider', 'WalletProviderCurrency', 'WalletProviderTransaction', 'WalletBalance', 'WalletProviderType',
    'WithdrawalMethod', 'ClientApiKey', 'ApiKeyUsageLog',
    'LoginHistory', 'LoginAttemptLimiter',
    'ClientWallet', 'ClientPricingPlan', 'WalletType', 'WalletStatus', 'PricingPlan',
    # Add other models as needed
]

# Import base models first (no foreign key dependencies)
from app.models.client import Client, Invoice, ClientDocument, ClientNotificationPreference

# Import Branch after Client
from app.models.branch import Branch

# Then import models that depend on Client but don't have other complex dependencies
from app.models.client_wallet import ClientWallet, ClientPricingPlan, WalletType, WalletStatus, PricingPlan

# Then import models that have foreign key dependencies
from app.models.transaction import Transaction
from app.models.platform import Platform, PlatformType, PlatformSetting, PlatformIntegration, PlatformWebhook
from app.models.commission_snapshot import CommissionSnapshot, CommissionSnapshottingType
from app.models.client_setting import ClientSetting, ClientSettingKey
from app.models.currency import Currency, ClientBalance, ClientCommission, CurrencyRate

# Import api_key after Client is defined to avoid circular imports
from app.models.api_key import ClientApiKey, ApiKeyUsageLog

# Backward compatibility alias for legacy imports
ApiKey = ClientApiKey

# Then import RecurringPayment before Payment since Payment references it
from app.models.recurring_payment import RecurringPayment

# Then import Withdrawal before Payment since Payment references it
from app.models.withdrawal import Withdrawal, WithdrawalRequest, WithdrawalStatus, WithdrawalMethod

# Finally import Payment which has the relationship to RecurringPayment
from app.models.payment import Payment
# PaymentSession is intentionally not imported here to avoid circular imports and
# to prevent mapping issues during CLI/migration; import directly where needed.

# Import wallet provider models
from app.models.wallet_provider import WalletProvider, WalletProviderCurrency, WalletProviderTransaction, WalletBalance, WalletProviderType

# Import subscription models
from app.models.pricing_plan import PricingPlan, PlanType, BillingCycle
from app.models.subscription import Subscription, SubscriptionStatus

# Import models with dependencies
from app.models.user import User
from app.models.admin import AdminUser
from app.models.role import Role
from app.models.support_ticket import SupportTicket

# Import package-related models
from app.models.feature import Feature
from app.models.client_package import ClientPackage, PackageFeature, ClientSubscription, ClientType
from app.models.package_payment import PackageActivationPayment, FlatRateSubscriptionPayment, SubscriptionBillingCycle, SubscriptionStatus
from app.models.setting import Setting

# Import wallet provider models
from app.models.wallet_provider import WalletProvider, WalletProviderCurrency, WalletBalance, WalletProviderTransaction

# Import bank gateway models (at the end to avoid circular imports)
try:
    # Bank Gateway Models
    from app.models.bank_gateway import (
        BankGatewayProvider, BankGatewayAccount, BankGatewayClientSite, 
        BankGatewayAPIKey, BankGatewayTransaction, BankGatewayCommission, 
        BankGatewayDepositRequest, BankGatewayWithdrawalRequest, 
        BankGatewayProviderCommission
    )
except ImportError:
    # Bank gateway models may not be available during initial setup
    pass

# Export enums directly
PaymentStatus = PaymentStatus
AuditActionType = AuditActionType
CommissionSnapshottingType = CommissionSnapshottingType
ClientType = ClientType
SettingType = SettingType
SettingKey = SettingKey

# Export models
__all__ = [
    # Base models
    'Base', 'BaseModel',
    
    # Main models
    'User', 'AdminUser', 'Role',
    'Client', 'Branch', 'ClientWallet', 'ClientPricingPlan', 'ClientSetting', 'ClientDocument', 'ClientNotificationPreference', 'Invoice',
    'Platform', 'PlatformType', 'PlatformSetting', 'PlatformIntegration', 'PlatformWebhook',
    'Payment', 'PaymentSession', 'RecurringPayment', 
    'Withdrawal', 'WithdrawalRequest', 'WithdrawalStatus',
    'Document', 
    'NotificationPreference', 'NotificationType', 'NotificationEvent',
    'Report', 'ReportType', 'ReportStatus',
    'AuditTrail', 'AuditLog', 
    'Transaction',
    'ApiUsage', 
    'CommissionSnapshot', 'CommissionSnapshottingType',
    'Setting',
    'Currency', 'ClientBalance', 'ClientCommission', 'CurrencyRate',
    
    # Enums
    'PaymentStatus',
    'AuditActionType',
    'ClientType',
    'SettingType',
    'SettingKey',
    'ClientSettingKey',

    # Support Ticket
    'SupportTicket',

    # Package and Subscription
    'ClientPackage', 'Feature', 'PackageFeature', 'ClientSubscription', 'PackageActivationPayment', 'FlatRateSubscriptionPayment', 'SubscriptionBillingCycle', 'SubscriptionStatus',
    
    # Wallet Provider
    'WalletProvider', 'WalletProviderCurrency', 'WalletBalance', 'WalletProviderTransaction',
    
    # Client Wallet
    'ClientWallet', 'ClientPricingPlan', 'WalletType', 'WalletStatus', 'PricingPlan',
    
    # Bank Gateway
    'BankGatewayProvider', 'BankGatewayAccount', 'BankGatewayClientSite', 
    'BankGatewayAPIKey', 'BankGatewayTransaction', 'BankGatewayCommission', 
    'BankGatewayDepositRequest', 'BankGatewayWithdrawalRequest', 
    'BankGatewayProviderCommission',

    # Legacy aliases
    'ApiKey'
]
