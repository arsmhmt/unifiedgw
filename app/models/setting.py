from datetime import datetime
from ..utils.timezone import now_eest
from enum import Enum
from app.extensions import db

class SettingType(Enum):
    """Types of settings"""
    SYSTEM = 'system'
    PAYMENT = 'payment'
    NOTIFICATION = 'notification'
    SECURITY = 'security'
    EMAIL = 'email'
    INTEGRATION = 'integration'

class SettingKey(Enum):
    """Specific setting keys"""
    # System Settings
    SYSTEM_NAME = 'system_name'
    SYSTEM_TIMEZONE = 'system_timezone'
    SYSTEM_CURRENCY = 'system_currency'
    
    # Payment Settings
    PAYMENT_CURRENCIES = 'payment_currencies'
    PAYMENT_METHODS = 'payment_methods'
    MIN_PAYMENT_AMOUNT = 'min_payment_amount'
    MAX_PAYMENT_AMOUNT = 'max_payment_amount'
    
    # Notification Settings
    EMAIL_PROVIDER = 'email_provider'
    SMS_PROVIDER = 'sms_provider'
    DEFAULT_NOTIFICATION_METHOD = 'default_notification_method'
    
    # Security Settings
    PASSWORD_MIN_LENGTH = 'password_min_length'
    PASSWORD_EXPIRY_DAYS = 'password_expiry_days'
    LOGIN_ATTEMPT_LIMIT = 'login_attempt_limit'
    
    # Email Settings
    SMTP_SERVER = 'smtp_server'
    SMTP_PORT = 'smtp_port'
    SMTP_USERNAME = 'smtp_username'
    SMTP_PASSWORD = 'smtp_password'
    
    # Integration Settings - Paycrypt's Own Payment System
    PAYCRYPT_WALLET_ADDRESS = 'paycrypt_wallet_address'
    PAYCRYPT_API_KEY = 'paycrypt_api_key'

class Setting(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), nullable=False, unique=True)
    value = db.Column(db.JSON)
    setting_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, key, value, setting_type, description=None):
        self.key = key
        self.value = value
        self.setting_type = setting_type
        self.description = description

    @classmethod
    def get_setting(cls, key):
        """Get a setting by key"""
        return cls.query.filter_by(key=key).first()

    @classmethod
    def get_all_settings(cls):
        """Get all settings grouped by type"""
        settings = cls.query.all()
        grouped = {}
        for setting in settings:
            if setting.setting_type not in grouped:
                grouped[setting.setting_type] = []
            grouped[setting.setting_type].append(setting)
        return grouped

    @classmethod
    def update_setting(cls, key, value):
        """Update a setting value"""
        setting = cls.get_setting(key)
        if setting:
            setting.value = value
            setting.updated_at = now_eest()
            db.session.commit()
            return setting
        return None

    @classmethod
    def create_default_settings(cls):
        """Create default settings"""
        default_settings = [
            # System Settings
            {
                'key': SettingKey.SYSTEM_NAME.value,
                'value': 'Paycrypt Payment Gateway',
                'type': SettingType.SYSTEM.value,
                'description': 'Name of the payment gateway system'
            },
            {
                'key': SettingKey.SYSTEM_TIMEZONE.value,
                'value': 'UTC',
                'type': SettingType.SYSTEM.value,
                'description': 'System timezone'
            },
            {
                'key': SettingKey.SYSTEM_CURRENCY.value,
                'value': 'USD',
                'type': SettingType.SYSTEM.value,
                'description': 'Default system currency'
            },
            
            # Payment Settings
            {
                'key': SettingKey.PAYMENT_CURRENCIES.value,
                'value': ['USD', 'EUR', 'GBP', 'BTC', 'ETH'],
                'type': SettingType.PAYMENT.value,
                'description': 'Supported payment currencies'
            },
            {
                'key': SettingKey.PAYMENT_METHODS.value,
                'value': ['crypto', 'bitcoin', 'ethereum'],
                'type': SettingType.PAYMENT.value,
                'description': 'Supported payment methods'
            },
            {
                'key': SettingKey.MIN_PAYMENT_AMOUNT.value,
                'value': 0.01,
                'type': SettingType.PAYMENT.value,
                'description': 'Minimum payment amount'
            },
            {
                'key': SettingKey.MAX_PAYMENT_AMOUNT.value,
                'value': 100000.00,
                'type': SettingType.PAYMENT.value,
                'description': 'Maximum payment amount'
            },
            
            # Notification Settings
            {
                'key': SettingKey.EMAIL_PROVIDER.value,
                'value': 'smtp',
                'type': SettingType.NOTIFICATION.value,
                'description': 'Email provider to use'
            },
            {
                'key': SettingKey.SMS_PROVIDER.value,
                'value': 'twilio',
                'type': SettingType.NOTIFICATION.value,
                'description': 'SMS provider to use'
            },
            {
                'key': SettingKey.DEFAULT_NOTIFICATION_METHOD.value,
                'value': 'email',
                'type': SettingType.NOTIFICATION.value,
                'description': 'Default notification method'
            },
            
            # Security Settings
            {
                'key': SettingKey.PASSWORD_MIN_LENGTH.value,
                'value': 8,
                'type': SettingType.SECURITY.value,
                'description': 'Minimum password length'
            },
            {
                'key': SettingKey.PASSWORD_EXPIRY_DAYS.value,
                'value': 90,
                'type': SettingType.SECURITY.value,
                'description': 'Password expiry days'
            },
            {
                'key': SettingKey.LOGIN_ATTEMPT_LIMIT.value,
                'value': 5,
                'type': SettingType.SECURITY.value,
                'description': 'Maximum login attempts before lockout'
            },
            
            # Email Settings
            {
                'key': SettingKey.SMTP_SERVER.value,
                'value': '',
                'type': SettingType.EMAIL.value,
                'description': 'SMTP server address'
            },
            {
                'key': SettingKey.SMTP_PORT.value,
                'value': 587,
                'type': SettingType.EMAIL.value,
                'description': 'SMTP server port'
            },
            {
                'key': SettingKey.SMTP_USERNAME.value,
                'value': '',
                'type': SettingType.EMAIL.value,
                'description': 'SMTP username'
            },
            {
                'key': SettingKey.SMTP_PASSWORD.value,
                'value': '',
                'type': SettingType.EMAIL.value,
                'description': 'SMTP password'
            },
            
            # Integration Settings - Paycrypt's Own Payment System
            {
                'key': SettingKey.PAYCRYPT_WALLET_ADDRESS.value,
                'value': '1PayCryptMainWallet123ABC',
                'type': SettingType.INTEGRATION.value,
                'description': 'Paycrypt main wallet address'
            },
            {
                'key': SettingKey.PAYCRYPT_API_KEY.value,
                'value': '',
                'type': SettingType.INTEGRATION.value,
                'description': 'Paycrypt internal API key'
            }
        ]
        
        # Create settings if they don't exist
        for setting_data in default_settings:
            if not cls.get_setting(setting_data['key']):
                setting = cls(
                    key=setting_data['key'],
                    value=setting_data['value'],
                    setting_type=setting_data['type'],
                    description=setting_data['description']
                )
                db.session.add(setting)
                
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error creating default settings: {e}")

    def __repr__(self):
        return f'<Setting {self.key}: {self.value}>'
