"""add login history table

Revision ID: 20251004_add_login_history
Revises: 
Create Date: 2025-10-04 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251004_add_login_history'
down_revision = 'd013b60aeca4'  # Point to existing head
branch_labels = None
depends_on = None


def upgrade():
    # Create login_history table
    op.create_table('login_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('username', sa.String(length=100), nullable=False),
    sa.Column('user_type', sa.String(length=20), nullable=False),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('failure_reason', sa.String(length=255), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=False),
    sa.Column('user_agent', sa.String(length=500), nullable=True),
    sa.Column('country', sa.String(length=100), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('session_id', sa.String(length=100), nullable=True),
    sa.Column('login_at', sa.DateTime(), nullable=False),
    sa.Column('logout_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_login_history_login_at'), 'login_history', ['login_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_login_history_login_at'), table_name='login_history')
    op.drop_table('login_history')
