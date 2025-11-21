"""merge_all_migrations

Revision ID: 21ca69483103
Revises: 20250814_add_payment_sessions, add_bank_gateway, 20250820_add_payment_session_fk
Create Date: 2025-09-13 20:51:05.523456

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '21ca69483103'
down_revision = ('20250814_add_payment_sessions', 'add_bank_gateway', '20250820_add_payment_session_fk')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
