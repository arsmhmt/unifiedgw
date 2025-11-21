from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    BooleanField,
    SelectField,
    DecimalField,
    IntegerField,
    TextAreaField,
    DateField,
    HiddenField,
)
from wtforms.validators import DataRequired, Length, Optional, Email, NumberRange, EqualTo

from app.models.enums import PaymentStatus

class ClientLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class ClientForm(FlaskForm):
    # Basic Information
    company_name = StringField('Company Name', validators=[DataRequired(), Length(max=128)])
    client_type = SelectField('Client Type', choices=[('COMPANY', 'Company'), ('INDIVIDUAL', 'Individual')], validators=[DataRequired()])
    name = StringField('Contact Name', validators=[Optional(), Length(max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=128)])
    phone = StringField('Phone', validators=[Optional(), Length(max=32)])
    website = StringField('Website', validators=[Optional(), Length(max=128)])

    # Login Credentials
    username = StringField('Username', validators=[Optional(), Length(max=64)])
    password = PasswordField('Password', validators=[Optional(), Length(max=128)])
    new_password = PasswordField('New Password', validators=[Optional(), Length(max=128)])
    auto_generate_password = BooleanField('Auto-generate password')

    # Address Information
    address = StringField('Address', validators=[Optional(), Length(max=256)])
    city = StringField('City', validators=[Optional(), Length(max=64)])
    country = StringField('Country', validators=[Optional(), Length(max=64)])
    postal_code = StringField('Postal Code', validators=[Optional(), Length(max=32)])

    # Business Information
    tax_id = StringField('Tax ID', validators=[Optional(), Length(max=64)])
    vat_number = StringField('VAT Number', validators=[Optional(), Length(max=64)])
    registration_number = StringField('Registration Number', validators=[Optional(), Length(max=64)])

    # Package and Status Management
    package_id = SelectField('Package', coerce=int, validators=[Optional()])
    client_status = SelectField('Client Status', choices=[('ACTIVE', 'Active'), ('INACTIVE', 'Inactive')], validators=[Optional()])
    is_active = BooleanField('Is Active')
    is_verified = BooleanField('Is Verified')

    # Account Balance Management
    balance = DecimalField('Balance', validators=[Optional(), NumberRange(min=0)], places=8, default=0)
    commission_balance = DecimalField('Commission Balance', validators=[Optional(), NumberRange(min=0)], places=8, default=0)

    # Additional Contact Information
    contact_person = StringField('Contact Person', validators=[Optional(), Length(max=64)])
    contact_email = StringField('Contact Email', validators=[Optional(), Email(), Length(max=128)])
    contact_phone = StringField('Contact Phone', validators=[Optional(), Length(max=32)])

    # Technical Settings
    rate_limit = IntegerField('API Rate Limit', validators=[Optional(), NumberRange(min=0)], default=0)
    theme_color = StringField('Theme Color', validators=[Optional(), Length(max=16)])

    # API Management
    api_key_enabled = BooleanField('API Key Enabled')
    auto_generate_api_key = BooleanField('Auto-generate API Key')
    webhook_url = StringField('Webhook URL', validators=[Optional(), Length(max=256)])

    # Commission Settings
    deposit_commission_rate = DecimalField('Deposit Commission Rate', validators=[Optional(), NumberRange(min=0, max=100)], places=2, default=0)
    withdrawal_commission_rate = DecimalField('Withdrawal Commission Rate', validators=[Optional(), NumberRange(min=0, max=100)], places=2, default=0)

    # Notes
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=1024)])

    submit = SubmitField('Save')

class AdminForm(FlaskForm):
    # Basic Information
    username = StringField('Username', validators=[DataRequired(), Length(max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=128)])
    first_name = StringField('First Name', validators=[Optional(), Length(max=64)])
    last_name = StringField('Last Name', validators=[Optional(), Length(max=64)])
    password = PasswordField('Password', validators=[DataRequired(), Length(max=128)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])

    # Admin Type
    admin_type = SelectField('Admin Type', choices=[('admin', 'Limited Admin'), ('superadmin', 'Super Admin')],
                           validators=[DataRequired()], default='admin')

    # Management Permissions (Checkboxes)
    perm_view_clients = BooleanField('View Clients', default=True)
    perm_create_clients = BooleanField('Create Clients', default=False)
    perm_edit_clients = BooleanField('Edit Clients', default=True)
    perm_delete_clients = BooleanField('Delete Clients', default=False)

    perm_approve_payments = BooleanField('Approve Payments', default=True)
    perm_approve_withdrawals = BooleanField('Approve Withdrawals', default=True)
    perm_view_transactions = BooleanField('View All Transactions', default=True)

    perm_view_stats = BooleanField('View Statistics', default=True)
    perm_view_reports = BooleanField('View Reports', default=True)

    perm_manage_wallet_providers = BooleanField('Manage Wallet Providers', default=False)
    perm_manage_bank_providers = BooleanField('Manage Bank Providers', default=False)

    perm_manage_admins = BooleanField('Create/Manage Other Admins', default=False)
    perm_manage_api_keys = BooleanField('Manage API Keys', default=True)

    perm_access_audit_logs = BooleanField('Access Audit Logs', default=True)
    perm_manage_settings = BooleanField('Manage System Settings', default=False)

    # Status
    is_active = BooleanField('Is Active', default=True)

    # Notes
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=512)])

    submit = SubmitField('Create Admin')

class BranchForm(FlaskForm):
    # Branch Information
    name = StringField('Branch Name', validators=[DataRequired(), Length(max=255)])
    address = TextAreaField('Address', validators=[Optional(), Length(max=500)])
    city = StringField('City', validators=[Optional(), Length(max=100)])
    country = StringField('Country', validators=[Optional(), Length(max=100)])
    postal_code = StringField('Postal Code', validators=[Optional(), Length(max=20)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])

    # Superadmin Account Creation
    superadmin_username = StringField('Superadmin Username', validators=[DataRequired(), Length(max=80)])
    superadmin_email = StringField('Superadmin Email', validators=[DataRequired(), Email(), Length(max=120)])
    superadmin_password = PasswordField('Superadmin Password', validators=[DataRequired(), Length(min=8, max=128)])
    superadmin_first_name = StringField('First Name', validators=[Optional(), Length(max=100)])
    superadmin_last_name = StringField('Last Name', validators=[Optional(), Length(max=100)])

    # Branch Settings
    webhook_url = StringField('Webhook URL', validators=[Optional(), Length(max=255)])
    is_active = BooleanField('Is Active', default=True)
    submit = SubmitField('Create Branch & Superadmin')

class SettingsForm(FlaskForm):
    """Base settings form; dynamic fields are attached at runtime."""
    setting_type = HiddenField('Setting Type', validators=[DataRequired()])
    submit = SubmitField('Save Settings')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields = {}


def build_settings_form(settings_data, formdata=None, **kwargs):
    """Create a SettingsForm instance with dynamic fields for the given settings."""
    dynamic_attrs = {}

    if settings_data:
        for setting in settings_data:
            field_name = setting.key
            label = setting.key.replace('_', ' ').title()
            description = getattr(setting, 'description', '')
            field_value = setting.value

            if isinstance(field_value, bool):
                field = BooleanField(label, description=description, default=bool(field_value))
            else:
                field = StringField(label, description=description, default=str(field_value or ''))

            dynamic_attrs[field_name] = field

    DynamicSettingsForm = type('DynamicSettingsForm', (SettingsForm,), dynamic_attrs)
    form = DynamicSettingsForm(formdata=formdata, **kwargs)

    if settings_data:
        form.fields = {}
        for setting in settings_data:
            field = getattr(form, setting.key, None)
            if not field:
                continue

            if isinstance(field, BooleanField):
                field.data = bool(setting.value)
            else:
                field.data = setting.value or ''

            form.fields[setting.key] = field

    return form

class ClientWizardForm(FlaskForm):
    """Multi-step form for creating clients with API keys and wallet configurations"""

    # Step 1: Basic Client Information
    company_name = StringField('Company Name', validators=[DataRequired(), Length(max=128)])
    contact_email = StringField('Contact Email', validators=[DataRequired(), Email(), Length(max=128)])
    contact_phone = StringField('Contact Phone', validators=[Optional(), Length(max=32)])
    website = StringField('Website', validators=[Optional(), Length(max=128)])
    password = PasswordField('Client Password', validators=[DataRequired(), Length(min=8, max=128)])

    # Step 2: Address Information
    address = StringField('Address', validators=[Optional(), Length(max=256)])
    city = StringField('City', validators=[Optional(), Length(max=64)])
    country = StringField('Country', validators=[Optional(), Length(max=64)])

    # Step 3: Coin and Wallet Configuration
    coins = SelectField('Supported Coins',
                       choices=[('btc', 'Bitcoin (BTC)'),
                               ('eth', 'Ethereum (ETH)'),
                               ('usdt', 'Tether (USDT)'),
                               ('bnb', 'Binance Coin (BNB)'),
                               ('ada', 'Cardano (ADA)'),
                               ('sol', 'Solana (SOL)'),
                               ('matic', 'Polygon (MATIC)'),
                               ('avax', 'Avalanche (AVAX)')],
                       validators=[Optional()])

    # Dynamic wallet address fields will be added via JavaScript
    submit = SubmitField('Create Client')

class ClientRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=128)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), Length(min=8, max=128)])
    first_name = StringField('First Name', validators=[Optional(), Length(max=64)])
    last_name = StringField('Last Name', validators=[Optional(), Length(max=64)])
    phone = StringField('Phone', validators=[Optional(), Length(max=32)])
    company_name = StringField('Company Name', validators=[DataRequired(), Length(max=128)])
    company_website = StringField('Company Website', validators=[Optional(), Length(max=128)])
    contact_person = StringField('Contact Person', validators=[Optional(), Length(max=64)])
    contact_email = StringField('Contact Email', validators=[Optional(), Email(), Length(max=128)])
    contact_phone = StringField('Contact Phone', validators=[Optional(), Length(max=32)])
    street_address = StringField('Street Address', validators=[Optional(), Length(max=256)])
    city = StringField('City', validators=[Optional(), Length(max=64)])
    state_province = StringField('State/Province', validators=[Optional(), Length(max=64)])
    country = StringField('Country', validators=[Optional(), Length(max=64)])
    postal_code = StringField('Postal Code', validators=[Optional(), Length(max=32)])
    terms_accepted = BooleanField('I accept the Terms and Conditions', validators=[DataRequired()])
    privacy_accepted = BooleanField('I accept the Privacy Policy', validators=[DataRequired()])
    submit = SubmitField('Register')
class PaymentForm(FlaskForm):
    client_id = SelectField('Client', coerce=int, validators=[DataRequired()])
    fiat_amount = DecimalField('Amount (Fiat)', validators=[DataRequired(), NumberRange(min=0.01)], places=2)
    fiat_currency = SelectField(
        'Fiat Currency',
        choices=[('TRY', 'TL (Turkish Lira)'), ('USD', 'USD'), ('EUR', 'EUR')],
        validators=[DataRequired()],
        default='TRY'
    )
    status = SelectField(
        'Status',
        choices=[(status.value, status.value.title()) for status in PaymentStatus],
        validators=[DataRequired()],
        default=PaymentStatus.PENDING.value
    )
    payment_method = SelectField(
        'Payment Method',
        choices=[('crypto', 'Cryptocurrency'), ('bank_transfer', 'Bank Transfer'), ('card', 'Credit Card')],
        validators=[DataRequired()],
        default='crypto'
    )
    transaction_id = StringField('Transaction ID', validators=[Optional(), Length(max=128)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Create Payment')


class RecurringPaymentForm(FlaskForm):
    client_id = SelectField('Client', coerce=int, validators=[DataRequired()])
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.01)], places=2)
    currency = SelectField('Currency', validators=[DataRequired()])
    frequency = SelectField('Frequency', validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[Optional()])
    payment_method = SelectField('Payment Method', validators=[Optional()])
    payment_provider = SelectField('Payment Provider', coerce=int, validators=[Optional()])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    status = SelectField('Status', validators=[Optional()])
    submit = SubmitField('Save Recurring Payment')
