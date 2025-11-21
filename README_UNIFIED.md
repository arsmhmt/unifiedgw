# PayCrypt Unified Application

This is the unified PayCrypt application that combines the functionality of both the original PayCrypt CCA (Flask) application and the PayCrypt Bank Gateway (Django) application into a single, comprehensive Flask-based platform.

## Architecture Overview

The unified application is built on Flask and includes:

### Core Features (from PayCrypt CCA)
- **Payment Processing**: Comprehensive cryptocurrency and traditional payment processing
- **Client Management**: Multi-client system with individual balances and settings
- **Wallet Management**: Integration with multiple wallet providers
- **Subscription System**: Package-based client subscriptions
- **Admin Dashboard**: Full administrative interface
- **API System**: RESTful APIs for payment processing
- **Withdrawal Management**: Automated and manual withdrawal processing
- **Support System**: Ticket-based customer support

### Bank Gateway Features (from PayCrypt Bank Gateway)
- **Provider Management**: Bank account providers with commission structures
- **Bank Account Management**: Multiple bank accounts per provider
- **Deposit Processing**: Manual bank transfer processing with receipt verification
- **Transaction Tracking**: Real-time transaction status and management
- **Client API**: RESTful API for deposit/withdrawal requests
- **Commission System**: Automated commission calculations

## Directory Structure

```
paycrypt-unified/
├── app/
│   ├── models/
│   │   ├── bank_gateway/          # Bank gateway models
│   │   │   └── __init__.py        # All bank gateway models
│   │   ├── client.py              # Original client models
│   │   ├── payment.py             # Payment models
│   │   └── ...                    # Other original models
│   ├── routes/
│   │   ├── bank_gateway/          # Bank gateway routes
│   │   │   ├── provider_panel.py  # Provider dashboard (/teminci)
│   │   │   ├── admin_panel.py     # Admin interface (/yonetim)
│   │   │   └── client_api.py      # Client API (/bank-api)
│   │   └── ...                    # Other route modules
│   ├── templates/
│   │   ├── bank_gateway/          # Bank gateway templates
│   │   │   ├── provider/          # Provider panel templates
│   │   │   ├── admin/             # Admin panel templates
│   │   │   └── client/            # Public client templates
│   │   └── ...                    # Other templates
│   └── ...
├── migrations/                    # Database migrations
└── ...
```

## New Models (Bank Gateway)

### BankGatewayProvider
- Represents bank account providers
- Links to User model
- Contains commission rates and blocking status

### BankGatewayAccount
- Bank accounts belonging to providers
- IBAN, account holder, and limits
- Tracks available balance

### BankGatewayClientSite
- Client integration sites
- URLs for callbacks, success/failure pages
- Links to existing Client model

### BankGatewayAPIKey
- API authentication for client sites
- One-to-one relationship with client sites

### BankGatewayTransaction
- All bank gateway transactions (deposits/withdrawals)
- Status tracking and commission calculations
- Reference codes and user information

### BankGatewayDepositRequest
- Specific to deposit transactions
- Receipt upload and verification tracking

## API Endpoints

### Bank Gateway Client API (`/bank-api`)

#### POST `/bank-api/deposit/request`
Create a deposit request
```json
{
    "amount": 100.00,
    "currency": "TRY",
    "user_name": "John Doe",
    "user_email": "john@example.com",
    "user_phone": "+905551234567",
    "callback_data": {}
}
```

#### GET `/bank-api/transaction/status/{reference_code}`
Check transaction status

#### POST `/bank-api/withdraw/request`
Create a withdrawal request

### Provider Panel (`/teminci`)
- Dashboard with statistics and recent transactions
- Bank account management
- Transaction confirmation/rejection

### Admin Panel (`/yonetim`)
- Provider management
- Client site configuration
- Transaction oversight
- Financial reports

## Database Migration

To apply the bank gateway tables:

```bash
# Generate migration (if not using the provided one)
flask db migrate -m "Add bank gateway tables"

# Apply migration
flask db upgrade
```

## Configuration

The bank gateway functionality uses the existing Flask configuration. No additional environment variables are required beyond the standard PayCrypt CCA setup.

## Integration Points

### User Management
Bank gateway providers are linked to the existing User model with role-based permissions.

### Client System
Bank gateway client sites are linked to the existing Client model, maintaining the same commission and balance systems.

### Commission System
Bank gateway commissions integrate with the existing commission tracking and can be viewed in the standard admin reports.

## Testing

The bank gateway functionality can be tested by:

1. Creating a provider user with 'provider' role
2. Adding bank accounts through the provider panel
3. Creating a client site through admin panel
4. Using the generated API key to make deposit requests
5. Processing transactions through the provider panel

## Migration from Separate Apps

If migrating from the separate Django and Flask applications:

1. **Database**: Run the migration script to create bank gateway tables
2. **Data Migration**: Create scripts to migrate existing Django data to the new Flask models
3. **Users**: Map Django User model to Flask User model
4. **Templates**: Update any custom templates to use the new unified structure
5. **Configuration**: Merge environment variables and configuration files

## Security Considerations

- API keys are automatically generated and should be kept secure
- HMAC signature verification can be implemented for webhook security
- File uploads (receipts) should be validated and stored securely
- All monetary transactions include audit trails

## Future Enhancements

- Automated bank statement parsing
- Real-time bank API integrations
- Advanced fraud detection
- Multi-currency support expansion
- Mobile app integration APIs
