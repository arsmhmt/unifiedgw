"""Add bank gateway enhancements: withdrawal requests, provider commissions, payment tracking

Revision ID: add_bank_gateway_enhancements
Revises: 
Create Date: 2025-10-05

This migration adds:
1. BankGatewayWithdrawalRequest table
2. BankGatewayProviderCommission table
3. is_paid, paid_at, paid_by fields to BankGatewayCommission
4. Enhanced tracking fields for commission payments
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'add_bank_gateway_enhancements'
down_revision = '20251004_add_wallet_addresses'  # Depends on latest migration
branch_labels = None
depends_on = None


def upgrade():
    # Add new fields to bank_gateway_commissions table
    with op.batch_alter_table('bank_gateway_commissions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_paid', sa.Boolean(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('paid_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('paid_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('payment_notes', sa.Text(), nullable=True))
        batch_op.create_foreign_key('fk_commission_paid_by', 'users', ['paid_by'], ['id'])

    # Create bank_gateway_withdrawal_requests table
    op.create_table('bank_gateway_withdrawal_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('client_site_id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=True),
        sa.Column('user_name', sa.String(length=100), nullable=False),
        sa.Column('user_surname', sa.String(length=100), nullable=True),
        sa.Column('iban', sa.String(length=34), nullable=False),
        sa.Column('bank_name', sa.String(length=100), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('reference_code', sa.String(length=50), nullable=False),
        sa.Column('processed_by', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_notes', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('commission_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('provider_commission', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('user_email', sa.String(length=100), nullable=True),
        sa.Column('user_phone', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['client_site_id'], ['bank_gateway_client_sites.id'], ),
        sa.ForeignKeyConstraint(['processed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['provider_id'], ['bank_gateway_providers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference_code')
    )
    with op.batch_alter_table('bank_gateway_withdrawal_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_bank_gateway_withdrawal_requests_client_site_id'), ['client_site_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_bank_gateway_withdrawal_requests_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_bank_gateway_withdrawal_requests_reference_code'), ['reference_code'], unique=True)

    # Create bank_gateway_provider_commissions table
    op.create_table('bank_gateway_provider_commissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.Column('transaction_type', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('is_paid', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('paid_by', sa.Integer(), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('payment_reference', sa.String(length=100), nullable=True),
        sa.Column('payment_notes', sa.Text(), nullable=True),
        sa.Column('related_transaction_ref', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['paid_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['provider_id'], ['bank_gateway_providers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('bank_gateway_provider_commissions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_bank_gateway_provider_commissions_provider_id'), ['provider_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_bank_gateway_provider_commissions_is_paid'), ['is_paid'], unique=False)
        batch_op.create_index(batch_op.f('ix_bank_gateway_provider_commissions_transaction_type'), ['transaction_type'], unique=False)


def downgrade():
    # Drop indices and table for provider_commissions
    with op.batch_alter_table('bank_gateway_provider_commissions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bank_gateway_provider_commissions_transaction_type'))
        batch_op.drop_index(batch_op.f('ix_bank_gateway_provider_commissions_is_paid'))
        batch_op.drop_index(batch_op.f('ix_bank_gateway_provider_commissions_provider_id'))
    
    op.drop_table('bank_gateway_provider_commissions')
    
    # Drop indices and table for withdrawal_requests
    with op.batch_alter_table('bank_gateway_withdrawal_requests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bank_gateway_withdrawal_requests_reference_code'))
        batch_op.drop_index(batch_op.f('ix_bank_gateway_withdrawal_requests_status'))
        batch_op.drop_index(batch_op.f('ix_bank_gateway_withdrawal_requests_client_site_id'))
    
    op.drop_table('bank_gateway_withdrawal_requests')
    
    # Remove new fields from bank_gateway_commissions
    with op.batch_alter_table('bank_gateway_commissions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_commission_paid_by', type_='foreignkey')
        batch_op.drop_column('payment_notes')
        batch_op.drop_column('paid_by')
        batch_op.drop_column('paid_at')
        batch_op.drop_column('is_paid')
