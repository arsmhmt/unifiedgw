"""Add wallet_addresses column to client_wallets

Revision ID: 20251004_add_wallet_addresses
Revises: 20251004_add_login_history
Create Date: 2025-10-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '20251004_add_wallet_addresses'
down_revision = '20251004_add_login_history'
branch_labels = None
depends_on = None


def upgrade():
    """Add wallet_addresses JSON column to client_wallets table"""
    # Check if table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'client_wallets' in inspector.get_table_names():
        # Check if column already exists
        columns = [col['name'] for col in inspector.get_columns('client_wallets')]
        
        if 'wallet_addresses' not in columns:
            # Add wallet_addresses column
            with op.batch_alter_table('client_wallets', schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column('wallet_addresses', sa.JSON(), nullable=True)
                )
            
            # Update existing records to have empty dict
            op.execute(
                """
                UPDATE client_wallets 
                SET wallet_addresses = '{}' 
                WHERE wallet_addresses IS NULL
                """
            )
            
            print("✓ Added wallet_addresses column to client_wallets table")
        else:
            print("✓ wallet_addresses column already exists in client_wallets table")
    else:
        print("! client_wallets table does not exist - skipping")


def downgrade():
    """Remove wallet_addresses column from client_wallets table"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'client_wallets' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('client_wallets')]
        
        if 'wallet_addresses' in columns:
            with op.batch_alter_table('client_wallets', schema=None) as batch_op:
                batch_op.drop_column('wallet_addresses')
            
            print("✓ Removed wallet_addresses column from client_wallets table")
