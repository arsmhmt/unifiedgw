"""
Client Package/Pricing Plan Models
Defines available packages, features, and pricing for different client types
"""

from datetime import datetime
from ..utils.timezone import now_eest
from app.extensions import db
from enum import Enum
from sqlalchemy import Numeric


class ClientType(Enum):
    """Client business model types"""
    COMMISSION = "commission"  # Type 1: Uses platform wallet, pays commission
    FLAT_RATE = "flat_rate"   # Type 2: Uses own wallet, pays flat rate


class PackageStatus(Enum):
    """Package availability status"""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEPRECATED = "DEPRECATED"


from .feature import Feature


class ClientPackage(db.Model):
    """Client packages/pricing plans"""
    __tablename__ = 'client_packages'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(64), nullable=True, info={'description': 'URL-friendly identifier'})
    description = db.Column(db.Text)
    client_type = db.Column(db.Enum(ClientType), nullable=False)
    
    # Pricing
    monthly_price = db.Column(db.Numeric(10, 2))  # For flat-rate packages
    annual_price = db.Column(db.Numeric(10, 2))  # Annual price with discount
    commission_rate = db.Column(db.Numeric(5, 4))  # For commission-based packages (e.g., 0.025 = 2.5%)
    setup_fee = db.Column(db.Numeric(10, 2), default=1000.00)  # One-time setup fee for commission plans
    
    # Billing options
    supports_monthly = db.Column(db.Boolean, default=True)
    supports_annual = db.Column(db.Boolean, default=True)
    annual_discount_percent = db.Column(db.Numeric(5, 2), default=10.0)  # 10% discount for annual
    
    # Limits and quotas
    max_transactions_per_month = db.Column(db.Integer)  # None = unlimited
    max_api_calls_per_month = db.Column(db.Integer)
    max_wallets = db.Column(db.Integer, default=1)
    
    # NEW: Volume limits for flat-rate plans (critical for margin protection)
    max_volume_per_month = db.Column(db.Numeric(20, 2))  # Monthly volume limit in USD
    min_margin_percent = db.Column(db.Numeric(5, 2), default=1.20)  # Minimum acceptable margin (1.2%)
    
    # Package settings
    status = db.Column(db.Enum(PackageStatus), default=PackageStatus.ACTIVE)
    is_popular = db.Column(db.Boolean, default=False)  # Highlight on pricing page
    sort_order = db.Column(db.Integer, default=0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    clients = db.relationship('Client', back_populates='package', lazy='dynamic')
    package_features = db.relationship('PackageFeature', backref='package', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def features(self):
        """Get list of features included in this package"""
        return [pf.feature for pf in self.package_features if pf.is_included]
    
    @property
    def slug(self):
        """Generate a slug from the package name, enforcing unique commission and correct flat-rate slugs."""
        if not self.name:
            return 'unknown'
        import re
        slug = re.sub(r'[^a-zA-Z0-9\s]', '', self.name.lower())
        slug = re.sub(r'\s+', '_', slug.strip())
        # Only allow flat-rate packages to use starter/professional/enterprise slugs
        if self.client_type == ClientType.FLAT_RATE:
            allowed = {
                'starter_flat_rate': 'starter',
                'business_flat_rate': 'business',  # changed from 'professional' to 'business'
                'enterprise_flat_rate': 'enterprise',
                'basic_flat_rate': 'basic',
                'premium_flat_rate': 'premium',
                'professional_flat_rate': 'professional',
            }
            # Map actual DB slugs to simplified slugs for frontend use
            return allowed.get(slug, slug)
        # Only one commission package, always use 'commission' as slug
        if self.client_type == ClientType.COMMISSION:
            return 'commission'
        return slug

# MIGRATION/CLEANUP: After this change, ensure only one commission package exists (keep the most appropriate one), and only flat-rate packages use the starter/professional/enterprise slugs. Remove or reassign any others.
    
    @property
    def price_display(self):
        """Get human-readable price"""
        if self.client_type == ClientType.COMMISSION:
            return f"{float(self.commission_rate * 100):.1f}% commission + ${float(self.setup_fee)} setup"
        else:
            monthly = f"${float(self.monthly_price)}/month"
            if self.annual_price:
                annual = f"${float(self.annual_price)}/year"
                return f"{monthly} or {annual}"
            return monthly
    
    @property
    def annual_price_calculated(self):
        """Calculate annual price with discount if not explicitly set"""
        if self.annual_price:
            return self.annual_price
        if self.monthly_price and self.annual_discount_percent:
            annual_full = self.monthly_price * 12
            discount = annual_full * (self.annual_discount_percent / 100)
            return annual_full - discount
        return None
    
    @property
    def annual_savings(self):
        """Calculate annual savings amount"""
        if self.monthly_price and self.annual_price_calculated:
            full_annual = self.monthly_price * 12
            return full_annual - self.annual_price_calculated
        return 0
    
    def has_feature(self, feature_key):
        """Check if package includes a specific feature"""
        return any(pf.feature.feature_key == feature_key and pf.is_included 
                  for pf in self.package_features)
    
    def calculate_margin_percent(self):
        """Calculate the margin percentage for flat-rate packages"""
        if self.client_type != ClientType.FLAT_RATE or not self.monthly_price or not self.max_volume_per_month:
            return None
        return (float(self.monthly_price) / float(self.max_volume_per_month)) * 100
    
    def is_margin_acceptable(self):
        """Check if the package margin meets minimum requirements"""
        margin = self.calculate_margin_percent()
        if margin is None:
            return True  # Commission-based or no limits set
        return margin >= float(self.min_margin_percent)
    
    def validate_pricing_structure(self):
        """
        Validate that this package meets minimum margin requirements.
        Returns dict with validation results.
        """
        if self.client_type != ClientType.FLAT_RATE:
            return {
                'is_valid': True,
                'message': 'Commission-based package - no margin validation needed',
                'margin_percent': None
            }
        
        if not self.monthly_price or not self.max_volume_per_month:
            return {
                'is_valid': False,
                'message': 'Missing required pricing fields for flat-rate package',
                'margin_percent': None
            }
        
        margin = self.calculate_margin_percent()
        min_margin = float(self.min_margin_percent or 1.20)
        
        if margin is None:
            return {
                'is_valid': False,
                'message': 'Could not calculate margin percentage',
                'margin_percent': None
            }
        
        return {
            'is_valid': margin >= min_margin,
            'margin_percent': margin,
            'min_margin_percent': min_margin,
            'message': f'Margin {margin:.2f}% {"meets" if margin >= min_margin else "below"} minimum {min_margin:.2f}%'
        }
    
    def get_volume_utilization_percent(self, current_volume):
        """Calculate what percentage of monthly volume limit is being used"""
        if not self.max_volume_per_month or self.max_volume_per_month <= 0:
            return 0  # Unlimited
        return (float(current_volume) / float(self.max_volume_per_month)) * 100
    
    def is_volume_exceeded(self, current_volume):
        """Check if current volume exceeds package limits"""
        if not self.max_volume_per_month:
            return False  # Unlimited volume
        return current_volume > self.max_volume_per_month
    
    def __repr__(self):
        return f'<ClientPackage {self.name}>'


class PackageFeature(db.Model):
    """Many-to-many relationship between packages and features"""
    __tablename__ = 'package_features'
    
    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.Integer, db.ForeignKey('client_packages.id'), nullable=False)
    feature_id = db.Column(db.Integer, db.ForeignKey('features.id'), nullable=False)
    is_included = db.Column(db.Boolean, default=True)
    limit_value = db.Column(db.Integer)  # For features with limits (e.g., API calls)
    
    # Relationships
    feature = db.relationship('Feature', backref='package_features')
    
    __table_args__ = (db.UniqueConstraint('package_id', 'feature_id'),)


class ClientSubscription(db.Model):
    """Track client subscription history and billing"""
    __tablename__ = 'client_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('client_packages.id'), nullable=False)
    
    # Subscription period
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)  # None for active subscription
    
    # Billing
    monthly_fee = db.Column(db.Numeric(10, 2))  # Locked-in price
    commission_rate = db.Column(db.Numeric(5, 4))  # Locked-in commission
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    client = db.relationship('Client', backref='subscriptions')
    package = db.relationship('ClientPackage', backref='subscriptions')
    
    @property
    def is_current(self):
        """Check if this is the current active subscription"""
        return self.is_active and (self.end_date is None or self.end_date > now_eest())


# Revised Flat-Rate Pricing configurations (≥1.2% Margin Protection)
REVISED_FLAT_RATE_PACKAGES = {
    'starter_flat_rate': {
        'name': 'Starter Flat Rate',
        'monthly_price': 499.00,
        'max_volume_per_month': 35000.00,  # $35K = 1.43% margin
        'min_margin_percent': 1.43,
        'max_transactions_per_month': 500,
        'max_api_calls_per_month': 10000,
        'max_wallets': 1,
        'description': 'Perfect for small businesses getting started with crypto payments',
        'features': ['api_basic', 'wallet_basic'],
        'restrictions': {
            'no_real_time': True,
            'no_analytics': True, 
            'no_webhooks': True,
            'no_multi_wallet': True,
            'basic_support_only': True
        }
    },
    'business_flat_rate': {
        'name': 'Business Flat Rate', 
        'monthly_price': 999.00,
        'max_volume_per_month': 70000.00,  # $70K = 1.42% margin
        'min_margin_percent': 1.42,
        'max_transactions_per_month': 2000,
        'max_api_calls_per_month': 50000,
        'max_wallets': 3,
        'description': 'Ideal for growing businesses with moderate transaction volumes',
        'features': ['api_basic', 'api_webhooks', 'dashboard_analytics', 'wallet_management'],
        'restrictions': {
            'webhook_limit': 1,
            'basic_analytics_only': True,
            'no_priority_support': True
        }
    },
    'enterprise_flat_rate': {
        'name': 'Enterprise Flat Rate',
        'monthly_price': 2000.00,
        'max_volume_per_month': None,  # Unlimited volume
        'min_margin_percent': 1.20,  # Scales down with volume
        'max_transactions_per_month': None,  # Unlimited
        'max_api_calls_per_month': None,  # Unlimited
        'max_wallets': None,  # Unlimited
        'description': 'Full-featured enterprise solution with unlimited scaling',
        'features': [
            'api_basic', 'api_advanced', 'api_webhooks', 
            'dashboard_analytics', 'dashboard_realtime',
            'wallet_management', 'support_priority', 'support_dedicated'
        ],
        'restrictions': {}  # No restrictions
    }
}

# Commission-Based Package configurations
COMMISSION_BASED_PACKAGES = {
    "commission_basic": {
        "name": "Commission Basic",
        "description": "Pay as you go, only a small commission per transaction.",
        "commission_rate": 3.5,  # percent (updated from 1.5 to 3.5)
        "setup_fee": 1000.00,  # one-time setup fee
        # Add other fields as needed for display
    }
}

def validate_flat_rate_margins():
    """
    Validate that all flat-rate packages maintain minimum acceptable margins.
    Returns dict with validation results.
    """
    results = {}
    
    for package_key, config in REVISED_FLAT_RATE_PACKAGES.items():
        monthly_price = config['monthly_price']
        max_volume = config['max_volume_per_month']
        min_margin = config['min_margin_percent']
        
        if max_volume:  # If there's a volume limit
            calculated_margin = (monthly_price / max_volume) * 100
            is_acceptable = calculated_margin >= 1.20  # Global minimum 1.2%
            
            results[package_key] = {
                'package_name': config['name'],
                'monthly_price': monthly_price,
                'max_volume': max_volume,
                'calculated_margin': round(calculated_margin, 2),
                'target_margin': min_margin,
                'is_acceptable': is_acceptable,
                'meets_minimum': calculated_margin >= 1.20
            }
        else:  # Unlimited volume
            results[package_key] = {
                'package_name': config['name'],
                'monthly_price': monthly_price,
                'max_volume': 'Unlimited',
                'calculated_margin': 'Scales with usage',
                'target_margin': min_margin,
                'is_acceptable': True,
                'meets_minimum': True
            }
    
    return results

def create_default_flat_rate_packages():
    """
    Create default flat-rate packages with proper margin protection.
    Used during database initialization or package updates.
    """
    packages_created = []
    
    for package_key, config in REVISED_FLAT_RATE_PACKAGES.items():
        # Check if package already exists
        existing = ClientPackage.query.filter_by(
            name=config['name'],
            client_type=ClientType.FLAT_RATE
        ).first()
        
        if existing:
            # Update existing package with new values
            existing.monthly_price = config['monthly_price']
            existing.max_volume_per_month = config['max_volume_per_month']
            existing.min_margin_percent = config['min_margin_percent']
            existing.max_transactions_per_month = config['max_transactions_per_month']
            existing.max_api_calls_per_month = config['max_api_calls_per_month']
            existing.max_wallets = config['max_wallets']
            existing.description = config['description']
            existing.updated_at = now_eest()
            packages_created.append(f"Updated: {existing.name}")
        else:
            # Create new package
            package = ClientPackage(
                name=config['name'],
                description=config['description'],
                client_type=ClientType.FLAT_RATE,
                monthly_price=config['monthly_price'],
                max_volume_per_month=config['max_volume_per_month'],
                min_margin_percent=config['min_margin_percent'],
                max_transactions_per_month=config['max_transactions_per_month'],
                max_api_calls_per_month=config['max_api_calls_per_month'],
                max_wallets=config['max_wallets'],
                status=PackageStatus.ACTIVE,
                is_popular=package_key == 'business_flat_rate'  # Mark Business as popular
            )
            
            db.session.add(package)
            packages_created.append(f"Created: {package.name}")
    
    try:
        db.session.commit()
        return {
            'success': True,
            'packages': packages_created,
            'validation': validate_flat_rate_margins()
        }
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'error': str(e),
            'packages': []
        }

def get_margin_protection_info():
    """
    Get comprehensive margin protection information for admin dashboard.
    """
    return {
        'minimum_global_margin': 1.20,
        'package_margins': validate_flat_rate_margins(),
        'protection_rules': {
            'starter': 'Fixed at 1.43% margin with $35K volume limit',
            'business': 'Fixed at 1.42% margin with $70K volume limit', 
            'enterprise': 'Scales down with volume, minimum 1.20% enforced'
        },
        'risk_thresholds': {
            'safe': 1.50,      # Above 1.5% = safe
            'warning': 1.30,   # 1.3-1.5% = warning
            'critical': 1.20   # Below 1.2% = critical
        }
    }
