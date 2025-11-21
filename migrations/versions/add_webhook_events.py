"""Add webhook_events table

Revision ID: add_webhook_events
Revises: 
Create Date: 2025-11-21 12:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_webhook_events'
down_revision = 'add_bank_gateway_enhancements'
branch_labels = None
depends_on = None


def upgrade():
    # Create webhook_events table
    op.create_table('webhook_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_response_code', sa.Integer(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index(op.f('ix_webhook_events_client_id'), 'webhook_events', ['client_id'], unique=False)
    op.create_index(op.f('ix_webhook_events_payment_id'), 'webhook_events', ['payment_id'], unique=False)
    op.create_index(op.f('ix_webhook_events_event_type'), 'webhook_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_webhook_events_status'), 'webhook_events', ['status'], unique=False)
    op.create_index(op.f('ix_webhook_events_next_attempt_at'), 'webhook_events', ['next_attempt_at'], unique=False)
    
    # Add webhook configuration columns to clients table
    op.add_column('clients', sa.Column('webhook_url', sa.String(length=500), nullable=True))
    op.add_column('clients', sa.Column('webhook_secret', sa.String(length=64), nullable=True))
    op.add_column('clients', sa.Column('webhook_enabled', sa.Boolean(), nullable=False, server_default='1'))


def downgrade():
    # Remove webhook configuration columns from clients
    op.drop_column('clients', 'webhook_enabled')
    op.drop_column('clients', 'webhook_secret')
    op.drop_column('clients', 'webhook_url')
    
    # Drop indexes
    op.drop_index(op.f('ix_webhook_events_next_attempt_at'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_status'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_event_type'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_payment_id'), table_name='webhook_events')
    op.drop_index(op.f('ix_webhook_events_client_id'), table_name='webhook_events')
    
    # Drop table
    op.drop_table('webhook_events')
