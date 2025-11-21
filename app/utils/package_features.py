"""
Package Features Mapping for Commission-Based vs Flat-Rate Clients
Centralized feature management with REVISED pricing structure respecting ≥1.2% margins

💼 REVISED FLAT-RATE PRICING (Margin Protection):
   - Starter: $499/month, $35K volume = 1.43% margin ✅
   - Business: $999/month, $70K volume = 1.42% margin ✅  
   - Enterprise: $2000/month, Unlimited volume (scales down with usage) ✅

🔐 All plans maintain minimum 1.2% margin to ensure profitability
"""

from datetime import datetime
from ..utils.timezone import now_eest
from decimal import Decimal

# REVISED: Package Configuration with proper margin protection
PACKAGE_CONFIGURATIONS = {
    # Commission-based packages (Type 1: Platform wallet, commission model)
    'starter_commission': {
        'name': 'Starter Commission',
        'client_type': 'commission',
        'commission_rate': Decimal('0.035'),  # 3.5%
        'setup_fee': Decimal('1000.00'),
        'monthly_price': None,
        'max_volume_per_month': None,  # Unlimited
        'min_margin_percent': None,
        'features': ['api_basic', 'platform_wallet', 'basic_analytics', 'email_support']
    },
    
    # Flat-rate packages (Type 2: Own wallet, flat monthly fee)
    'starter_flat_rate': {
        'name': 'Starter Flat Rate',
        'client_type': 'flat_rate',
        'commission_rate': None,
        'setup_fee': Decimal('0.00'),
        'monthly_price': Decimal('499.00'),       # $499/month
        'max_volume_per_month': Decimal('35000.00'),  # $35K volume = 1.43% margin
        'min_margin_percent': Decimal('1.20'),
        'features': ['api_basic', 'wallet_management', 'basic_analytics']
    },
    
    'business_flat_rate': {
        'name': 'Business Flat Rate',
        'client_type': 'flat_rate',
        'commission_rate': None,
        'setup_fee': Decimal('0.00'),
        'monthly_price': Decimal('999.00'),       # $999/month
        'max_volume_per_month': Decimal('70000.00'),  # $70K volume = 1.42% margin
        'min_margin_percent': Decimal('1.20'),
        'features': ['api_basic', 'api_webhooks', 'wallet_management', 'dashboard_analytics', 'basic_analytics']
    },
    
    'enterprise_flat_rate': {
        'name': 'Enterprise Flat Rate',
        'client_type': 'flat_rate',
        'commission_rate': None,
        'setup_fee': Decimal('0.00'),
        'monthly_price': Decimal('2000.00'),      # $2000/month
        'max_volume_per_month': None,             # Unlimited (scales with usage)
        'min_margin_percent': Decimal('1.20'),
        'features': [
            'api_basic', 'api_advanced', 'api_webhooks', 
            'wallet_management', 'dashboard_realtime', 'dashboard_analytics',
            'basic_analytics', 'support_priority', 'support_dedicated'
        ]
    }
}

# LEGACY: Keep existing PACKAGE_FEATURES for backward compatibility
PACKAGE_FEATURES = {
    # Commission-Based Clients (Type 1: Platform wallet, commission-based)
    'starter_commission': [
        'api_basic',
        'platform_wallet',
        'basic_analytics',
        'commission_based',
        'withdrawal_request',  # Can request platform payouts
    ],
    'basic_commission': [
        'api_basic', 
        'platform_wallet',
        'basic_analytics',
        'commission_based',
        'support_email',
        'withdrawal_request',
    ],
    
    # REVISED Flat-Rate Clients (Type 2: Own wallet, monthly fees with margin protection)
    
    # Starter: $499/month, $35K volume = 1.43% margin ✅
    'starter_flat_rate': [
        'api_basic',
        'own_wallet',
        'flat_rate_billing',
        # RESTRICTIONS: No real-time, No analytics, No webhooks, No multi-wallet
    ],
    
    # Business: $999/month, $70K volume = 1.42% margin ✅
    'business_flat_rate': [
        'api_basic',
        'api_webhooks',  # 1 webhook allowed
        'own_wallet',
        'wallet_management',
        'dashboard_analytics',
        'flat_rate_billing',
        'support_email',
        # RESTRICTIONS: Basic analytics only, No priority support
    ],
    
    # Enterprise: $2000/month, Unlimited volume with scaling ✅
    'enterprise_flat_rate': [
        'api_basic',
        'api_advanced',
        'api_webhooks',  # Unlimited webhooks
        'own_wallet',
        'wallet_management', 
        'wallet_multi',
        'dashboard_analytics',
        'dashboard_realtime',
        'flat_rate_billing',
        'support_priority',
        'support_dedicated',
        'audit_logs',
        'custom_branding',
    ],
    
    # Legacy/Backward compatibility
    'basic': [
        'api_basic',
        'platform_wallet',
    ],
    'premium': [
        'api_basic',
        'api_webhooks',
        'dashboard_analytics',
        'own_wallet',
    ],
    'professional': [
        'api_basic',
        'api_advanced',
        'api_webhooks',
        'dashboard_analytics',
        'dashboard_realtime',
        'wallet_management',
        'support_priority',
    ],
}

# Feature descriptions for UI display
FEATURE_DESCRIPTIONS = {
    # API Features
    'api_basic': {
        'name': 'Basic API Access',
        'description': 'Create payments, check status, basic endpoints',
        'category': 'api',
        'commission_only': ['payment_create', 'payment_status'],
        'flat_rate_only': ['payment_create', 'payment_status', 'balance_read', 'profile_read'],
    },
    'api_advanced': {
        'name': 'Advanced API Access', 
        'description': 'Full API suite including wallet management, user management',
        'category': 'api',
        'flat_rate_only': ['wallet_manage', 'user_manage', 'invoice_create', 'withdrawal_create'],
    },
    'api_webhooks': {
        'name': 'Webhook Support',
        'description': 'Real-time notifications via webhooks with HMAC security',
        'category': 'api',
        'flat_rate_only': True,  # Only for flat-rate clients
    },
    
    # Wallet Features  
    'platform_wallet': {
        'name': 'Platform-Managed Wallet',
        'description': 'Paycrypt manages your funds and wallets',
        'category': 'wallet',
        'commission_only': True,
    },
    'own_wallet': {
        'name': 'Client-Owned Wallet',
        'description': 'You control your own crypto wallets',
        'category': 'wallet',
        'flat_rate_only': True,
    },
    'wallet_management': {
        'name': 'Advanced Wallet Management',
        'description': 'Configure multiple wallets, set withdrawal rules',
        'category': 'wallet',
        'flat_rate_only': True,
    },
    'wallet_multi': {
        'name': 'Multi-Wallet Support',
        'description': 'Manage multiple wallets for different purposes',
        'category': 'wallet',
        'enterprise_only': True,
    },
    
    # Analytics & Dashboard
    'basic_analytics': {
        'name': 'Basic Analytics',
        'description': 'Transaction history, basic reports',
        'category': 'analytics',
    },
    'dashboard_analytics': {
        'name': 'Advanced Analytics',
        'description': 'Detailed transaction analytics, custom reports',
        'category': 'analytics',
    },
    'dashboard_realtime': {
        'name': 'Real-time Dashboard',
        'description': 'Live transaction monitoring and alerts',
        'category': 'analytics',
        'enterprise_only': True,
    },
    
    # Support
    'support_email': {
        'name': 'Email Support',
        'description': 'Standard email support during business hours',
        'category': 'support',
    },
    'support_priority': {
        'name': 'Priority Support',
        'description': 'Faster response times, phone support',
        'category': 'support',
    },
    'support_dedicated': {
        'name': 'Dedicated Account Manager',
        'description': 'Personal account manager and dedicated support',
        'category': 'support',
        'enterprise_only': True,
    },
    
    # Billing & Security
    'commission_based': {
        'name': 'Commission-Based Billing',
        'description': 'Pay per transaction with commission rates',
        'category': 'billing',
    },
    'flat_rate_billing': {
        'name': 'Flat-Rate Billing',
        'description': 'Fixed monthly fee with volume limits',
        'category': 'billing',
    },
    'audit_logs': {
        'name': 'Full Audit Logs',
        'description': 'Complete audit trail of all activities',
        'category': 'security',
        'enterprise_only': True,
    },
    'custom_branding': {
        'name': 'Custom Branding',
        'description': 'White-label dashboard and email templates',
        'category': 'branding',
        'enterprise_only': True,
    },
}

# Package pricing information (matching your new structure)
PACKAGE_PRICING = {
    'starter_flat_rate': {
        'monthly_price': 499,
        'max_volume_per_month': 35000,
        'margin_percent': 1.43,
        'description': 'Perfect for small businesses starting with crypto payments',
        'limits': {
            'webhooks': 0,
            'api_calls_per_minute': 30,
            'realtime_dashboard': False,
        }
    },
    'business_flat_rate': {
        'monthly_price': 999, 
        'max_volume_per_month': 70000,
        'margin_percent': 1.42,
        'description': 'Growing businesses with moderate transaction volumes',
        'limits': {
            'webhooks': 1,
            'api_calls_per_minute': 60,
            'realtime_dashboard': False,
        }
    },
    'enterprise_flat_rate': {
        'monthly_price': 2000,
        'max_volume_per_month': None,  # Unlimited
        'margin_percent': None,  # Scales with volume
        'description': 'Large enterprises with high transaction volumes',
        'limits': {
            'webhooks': None,  # Unlimited
            'api_calls_per_minute': 200,
            'realtime_dashboard': True,
        }
    }
}

def get_features_for_client(client):
    """
    Get features for a client based on their package/status
    Respects both package-based features and manual overrides
    """
    features = set()
    
    # Get base features from package
    if client.package and client.package.slug:
        package_features = PACKAGE_FEATURES.get(client.package.slug, [])
        features.update(package_features)
    elif hasattr(client, 'status') and client.status:
        # Fallback to status-based features
        package_features = PACKAGE_FEATURES.get(client.status, [])
        features.update(package_features)
    
    # Apply manual feature overrides from admin
    if client.features_override:
        try:
            if isinstance(client.features_override, str):
                import json
                override = json.loads(client.features_override)
            else:
                override = client.features_override
                
            if isinstance(override, dict):
                if override.get("add"):
                    features.update(override["add"])
                if override.get("remove"):
                    features.difference_update(override["remove"])
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass  # Ignore invalid override data
    
    return list(features)

def get_client_pricing_info(client):
    """Get pricing and limit information for a client"""
    if not client.package or not client.package.slug:
        return None
        
    return PACKAGE_PRICING.get(client.package.slug, {})

def is_feature_allowed_for_client_type(feature_key, client_type):
    """Check if a feature is allowed for a specific client type"""
    feature_info = FEATURE_DESCRIPTIONS.get(feature_key, {})
    
    if client_type == 'commission':
        return not feature_info.get('flat_rate_only', False)
    elif client_type == 'flat_rate':
        return not feature_info.get('commission_only', False)
    
    return True

def get_package_upgrade_recommendations(current_package_slug):
    """Get upgrade recommendations based on current package"""
    upgrade_paths = {
        'starter_commission': ['business_flat_rate', 'enterprise_flat_rate'],
        'starter_flat_rate': ['business_flat_rate', 'enterprise_flat_rate'], 
        'business_flat_rate': ['enterprise_flat_rate'],
        'enterprise_flat_rate': [],  # No upgrades available
    }
    
    return upgrade_paths.get(current_package_slug, [])

def validate_package_margin_simple(monthly_price, max_volume, min_margin_percent=1.20):
    """Simple validation that a package maintains minimum margin requirements"""
    if not monthly_price or not max_volume:
        return True  # Can't validate without both values
        
    actual_margin = (monthly_price / max_volume) * 100
    return actual_margin >= min_margin_percent


def validate_package_margin(package_slug, monthly_price, max_volume_per_month):
    """
    Validate that a package configuration meets minimum margin requirements.
    
    Args:
        package_slug (str): Package identifier
        monthly_price (float): Monthly fee in USD
        max_volume_per_month (float): Maximum monthly volume in USD (None = unlimited)
    
    Returns:
        dict: Validation result with margin info
    """
    
    MIN_ACCEPTABLE_MARGIN = 1.20  # Global minimum 1.2%
    
    if not max_volume_per_month:  # Unlimited volume
        return {
            'is_valid': True,
            'margin_percent': None,
            'volume_limit': None,
            'note': 'Unlimited volume package - margin scales with usage'
        }
    
    # Calculate margin percentage
    margin_percent = (monthly_price / max_volume_per_month) * 100
    
    return {
        'is_valid': margin_percent >= MIN_ACCEPTABLE_MARGIN,
        'margin_percent': round(margin_percent, 2),
        'min_required': MIN_ACCEPTABLE_MARGIN,
        'volume_limit': max_volume_per_month,
        'monthly_fee': monthly_price,
        'status': (
            'acceptable' if margin_percent >= MIN_ACCEPTABLE_MARGIN 
            else 'below_minimum'
        ),
        'note': f"Margin: {margin_percent:.2f}% ({'✅' if margin_percent >= MIN_ACCEPTABLE_MARGIN else '❌'})"
    }


def get_revised_pricing_summary():
    """
    Get summary of revised flat-rate pricing with margin protection.
    """
    
    pricing_plans = {
        'starter_flat_rate': {
            'name': 'Starter Flat Rate',
            'monthly_price': 499.00,
            'max_volume': 35000.00,
            'features': len(PACKAGE_FEATURES.get('starter_flat_rate', [])),
            'target_market': 'Small businesses getting started'
        },
        'business_flat_rate': {
            'name': 'Business Flat Rate', 
            'monthly_price': 999.00,
            'max_volume': 70000.00,
            'features': len(PACKAGE_FEATURES.get('business_flat_rate', [])),
            'target_market': 'Growing businesses with moderate volumes'
        },
        'enterprise_flat_rate': {
            'name': 'Enterprise Flat Rate',
            'monthly_price': 2000.00,
            'max_volume': None,  # Unlimited
            'features': len(PACKAGE_FEATURES.get('enterprise_flat_rate', [])),
            'target_market': 'High-volume enterprises and platforms'
        }
    }
    
    summary = {}
    for package_slug, config in pricing_plans.items():
        validation = validate_package_margin(
            package_slug,
            config['monthly_price'],
            config['max_volume']
        )
        
        summary[package_slug] = {
            **config,
            'margin_validation': validation,
            'pricing_display': (
                f"${config['monthly_price']}/month"
                f" for ${config['max_volume']:,.0f} volume" if config['max_volume']
                else f"${config['monthly_price']}/month (unlimited volume)"
            ),
            'margin_display': (
                f"{validation['margin_percent']:.2f}%" if validation['margin_percent']
                else "Scales with usage"
            )
        }
    
    return summary


def get_betconstruct_integration_guidance():
    """
    Provide specific guidance for BetConstruct and similar sportsbook/casino integrations.
    """
    
    return {
        'recommended_package': 'business_flat_rate',  # Most cost-effective for sportsbooks
        'reasoning': 'Business plan provides webhooks and analytics needed for real-time betting',
        'integration_requirements': {
            'webhooks': 'Essential for real-time bet settlement notifications',
            'api_access': 'Basic API sufficient for most sportsbook integrations',
            'wallet_management': 'Critical for managing player deposits/withdrawals',
            'analytics': 'Important for tracking betting volumes and patterns'
        },
        'volume_considerations': {
            'typical_monthly_volume': '$50,000 - $150,000',
            'business_plan_covers': '$70,000 at 1.42% margin',
            'upgrade_threshold': 'Consider Enterprise if consistently exceeding $70K/month',
            'enterprise_benefits': 'Unlimited volume, real-time dashboard, priority support'
        },
        'onboarding_steps': [
            '1. Start with Business Flat Rate plan',
            '2. Configure webhook endpoints for bet settlement',
            '3. Set up multi-wallet configuration for different game types',
            '4. Implement API endpoints for deposits/withdrawals',
            '5. Test in sandbox environment',
            '6. Go live with real player transactions',
            '7. Monitor volume and upgrade to Enterprise if needed'
        ],
        'security_requirements': {
            'webhook_hmac': 'HMAC-SHA256 signature verification required',
            'ip_restrictions': 'Whitelist BetConstruct server IPs',
            'api_rate_limits': 'Standard rate limits apply (50,000 calls/month)',
            'ssl_required': 'All webhook endpoints must use HTTPS'
        },
        'margin_protection': {
            'business_plan_margin': '1.42%',
            'volume_limit': '$70,000/month',
            'overage_handling': 'Soft limit with margin monitoring',
            'upgrade_recommendation': 'Automatic notification when approaching limits'
        }
    }


def validate_all_packages():
    """
    Validate margin requirements for all defined packages.
    Returns validation report for admin review.
    """
    
    # Package configurations for validation
    package_configs = {
        'starter_flat_rate': {'monthly_price': 499.00, 'max_volume': 35000.00},
        'business_flat_rate': {'monthly_price': 999.00, 'max_volume': 70000.00},
        'enterprise_flat_rate': {'monthly_price': 2000.00, 'max_volume': None},
    }
    
    validation_report = {
        'timestamp': now_eest().isoformat(),
        'global_minimum_margin': 1.20,
        'packages': {},
        'summary': {
            'total_packages': len(package_configs),
            'valid_packages': 0,
            'invalid_packages': 0,
            'unlimited_packages': 0
        }
    }
    
    for package_slug, config in package_configs.items():
        validation = validate_package_margin(
            package_slug,
            config['monthly_price'],
            config['max_volume']
        )
        
        validation_report['packages'][package_slug] = {
            'name': package_slug.replace('_', ' ').title(),
            'config': config,
            'validation': validation,
            'features_count': len(PACKAGE_FEATURES.get(package_slug, [])),
            'is_recommended': package_slug == 'business_flat_rate'  # Most popular
        }
        
        # Update summary counters
        if validation['is_valid']:
            validation_report['summary']['valid_packages'] += 1
        else:
            validation_report['summary']['invalid_packages'] += 1
            
        if not config['max_volume']:
            validation_report['summary']['unlimited_packages'] += 1
    
    return validation_report
