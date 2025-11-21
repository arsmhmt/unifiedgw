"""add payment_session_id to payments

Revision ID: 20250820_add_payment_session_fk
Revises: 
Create Date: 2025-08-20 00:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250820_add_payment_session_fk'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('payments') as batch_op:
        batch_op.add_column(sa.Column('payment_session_id', sa.Integer(), nullable=True))
        try:
            batch_op.create_foreign_key('fk_payments_payment_session', 'payment_sessions', ['payment_session_id'], ['id'])
        except Exception:
            pass

def downgrade():
    with op.batch_alter_table('payments') as batch_op:
        try:
            batch_op.drop_constraint('fk_payments_payment_session', type_='foreignkey')
        except Exception:
            pass
        batch_op.drop_column('payment_session_id')