"""add database optimizations for transactions

Revision ID: e8d1a6f84952
Revises: c6dcdf298067
Create Date: 2023-07-18 15:30:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e8d1a6f84952'
down_revision: Union[str, None] = 'c6dcdf298067'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def create_index_if_not_exists(index_name, table_name, columns, unique=False):
    """Helper function to create an index only if it doesn't already exist"""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Get existing indexes
    indexes = inspector.get_indexes(table_name)
    existing_index_names = [idx['name'] for idx in indexes if 'name' in idx]
    
    # Create index only if it doesn't exist
    if index_name not in existing_index_names:
        op.create_index(index_name, table_name, columns, unique=unique)
        print(f"Created index {index_name} on {table_name}")
    else:
        print(f"Index {index_name} already exists on {table_name}, skipping")


def upgrade() -> None:
    # Add indexes for common query patterns in transactions table
    
    # Index on transaction_date for date range queries and sorting
    create_index_if_not_exists('idx_transactions_transaction_date', 'transactions', ['transaction_date'], unique=False)
    
    # Index on created_at for default ordering
    create_index_if_not_exists('idx_transactions_created_at', 'transactions', ['created_at'], unique=False)
    
    # Composite index for user_id and transaction_date for filtered queries
    create_index_if_not_exists('idx_transactions_user_id_transaction_date', 'transactions', ['user_id', 'transaction_date'], unique=False)
    
    # Composite index for user_id and transaction_type for filtered queries
    create_index_if_not_exists('idx_transactions_user_id_transaction_type', 'transactions', ['user_id', 'transaction_type'], unique=False)
    
    # Index for category_id for category filtering
    create_index_if_not_exists('idx_transactions_category_id', 'transactions', ['category_id'], unique=False)
    
    # Index for description for potential text searching
    create_index_if_not_exists('idx_transactions_description', 'transactions', ['description'], unique=False)
    
    # Index for account filtering
    create_index_if_not_exists('idx_transactions_account_id', 'transactions', ['account_id'], unique=False)
    
    # Index for destination account filtering
    create_index_if_not_exists('idx_transactions_destination_account_id', 'transactions', ['destination_account_id'], unique=False)
    
    # Add indexes for common query patterns in accounts table
    
    # Index for account name searching
    create_index_if_not_exists('idx_accounts_name', 'accounts', ['name'], unique=False)
    
    # Add indexes for common query patterns in categories table
    
    # Index for category name searching
    create_index_if_not_exists('idx_categories_name', 'categories', ['name'], unique=False)
    
    # Composite index for category type and user_id
    create_index_if_not_exists('idx_categories_type_user_id', 'categories', ['type', 'user_id'], unique=False)


def downgrade() -> None:
    # We'll try to drop indexes, but ignore errors if they don't exist
    try:
        op.drop_index('idx_transactions_transaction_date', table_name='transactions')
    except:
        pass
        
    try:
        op.drop_index('idx_transactions_created_at', table_name='transactions')
    except:
        pass
        
    try:
        op.drop_index('idx_transactions_user_id_transaction_date', table_name='transactions')
    except:
        pass
        
    try:
        op.drop_index('idx_transactions_user_id_transaction_type', table_name='transactions')
    except:
        pass
        
    try:
        op.drop_index('idx_transactions_category_id', table_name='transactions')
    except:
        pass
        
    try:
        op.drop_index('idx_transactions_description', table_name='transactions')
    except:
        pass
        
    try:
        op.drop_index('idx_transactions_account_id', table_name='transactions')
    except:
        pass
        
    try:
        op.drop_index('idx_transactions_destination_account_id', table_name='transactions')
    except:
        pass
        
    try:
        op.drop_index('idx_accounts_name', table_name='accounts')
    except:
        pass
        
    try:
        op.drop_index('idx_categories_name', table_name='categories')
    except:
        pass
        
    try:
        op.drop_index('idx_categories_type_user_id', table_name='categories')
    except:
        pass 