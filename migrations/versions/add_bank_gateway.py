"""Add bank gateway tables

Revision ID: add_bank_gateway
Revises: 
Create Date: 2025-01-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_bank_gateway'
down_revision = None  # Replace with actual previous revision
branch_labels = None
depends_on = None

def upgrade():
    # Create bank_gateway_providers table
    op.create_table('bank_gateway_providers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('deposit_commission', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('withdraw_commission', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('is_blocked', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create bank_gateway_accounts table
    op.create_table('bank_gateway_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('bank_name', sa.String(length=100), nullable=False),
        sa.Column('account_holder', sa.String(length=100), nullable=False),
        sa.Column('iban', sa.String(length=34), nullable=False),
        sa.Column('account_limit', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['bank_gateway_providers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create bank_gateway_client_sites table
    op.create_table('bank_gateway_client_sites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('site_name', sa.String(length=100), nullable=False),
        sa.Column('site_url', sa.String(length=255), nullable=False),
        sa.Column('callback_url', sa.String(length=255), nullable=True),
        sa.Column('success_url', sa.String(length=255), nullable=True),
        sa.Column('fail_url', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create bank_gateway_api_keys table
    op.create_table('bank_gateway_api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('client_site_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['client_site_id'], ['bank_gateway_client_sites.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_site_id'),
        sa.UniqueConstraint('key')
    )

    # Create bank_gateway_transactions table
    op.create_table('bank_gateway_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('client_site_id', sa.Integer(), nullable=False),
        sa.Column('bank_account_id', sa.Integer(), nullable=True),
        sa.Column('provider_id', sa.Integer(), nullable=True),
        sa.Column('transaction_type', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('external_transaction_id', sa.String(length=100), nullable=True),
        sa.Column('reference_code', sa.String(length=50), nullable=False),
        sa.Column('user_name', sa.String(length=100), nullable=True),
        sa.Column('user_email', sa.String(length=100), nullable=True),
        sa.Column('user_phone', sa.String(length=20), nullable=True),
        sa.Column('commission_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('provider_commission', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('callback_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['bank_account_id'], ['bank_gateway_accounts.id'], ),
        sa.ForeignKeyConstraint(['client_site_id'], ['bank_gateway_client_sites.id'], ),
        sa.ForeignKeyConstraint(['provider_id'], ['bank_gateway_providers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference_code')
    )

    # Create bank_gateway_commissions table
    op.create_table('bank_gateway_commissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('commission_type', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('percentage', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.ForeignKeyConstraint(['transaction_id'], ['bank_gateway_transactions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create bank_gateway_deposit_requests table
    op.create_table('bank_gateway_deposit_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('bank_account_id', sa.Integer(), nullable=False),
        sa.Column('sender_name', sa.String(length=100), nullable=True),
        sa.Column('sender_iban', sa.String(length=34), nullable=True),
        sa.Column('receipt_image', sa.String(length=255), nullable=True),
        sa.Column('processing_notes', sa.Text(), nullable=True),
        sa.Column('verification_status', sa.String(length=20), nullable=True),
        sa.Column('verified_by', sa.Integer(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['bank_account_id'], ['bank_gateway_accounts.id'], ),
        sa.ForeignKeyConstraint(['transaction_id'], ['bank_gateway_transactions.id'], ),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('bank_gateway_deposit_requests')
    op.drop_table('bank_gateway_commissions')
    op.drop_table('bank_gateway_transactions')
    op.drop_table('bank_gateway_api_keys')
    op.drop_table('bank_gateway_client_sites')
    op.drop_table('bank_gateway_accounts')
    op.drop_table('bank_gateway_providers')
