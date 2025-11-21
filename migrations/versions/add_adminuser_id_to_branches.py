"""add adminuser_id to branches

Revision ID: add_adminuser_id
Revises: 2afdcf68d2ed
Create Date: 2025-09-24 21:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_adminuser_id'
down_revision = '2afdcf68d2ed'
branch_labels = None
depends_on = None


def upgrade():
    # Use batch mode for SQLite
    with op.batch_alter_table('branches') as batch_op:
        # Add adminuser_id column
        batch_op.add_column(sa.Column('adminuser_id', sa.Integer(), nullable=True))
        # Add foreign key
        batch_op.create_foreign_key('fk_branches_adminuser_id', 'admin_users', ['adminuser_id'], ['id'])
        # Make client_id nullable
        batch_op.alter_column('client_id', nullable=True)


def downgrade():
    # Use batch mode for SQLite
    with op.batch_alter_table('branches') as batch_op:
        # Remove the foreign key and column
        batch_op.drop_constraint('fk_branches_adminuser_id', type_='foreignkey')
        batch_op.drop_column('adminuser_id')
        # Make client_id not nullable again
        batch_op.alter_column('client_id', nullable=False)