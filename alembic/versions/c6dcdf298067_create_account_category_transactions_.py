"""create account, category, transactions table

Revision ID: c6dcdf298067
Revises: 3e03d8a7da83
Create Date: 2025-03-05 21:44:44.670359

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
import psycopg2


# revision identifiers, used by Alembic.
revision: str = 'c6dcdf298067'
down_revision: Union[str, None] = '3e03d8a7da83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ENUM types
    account_type = ENUM('bank_account', 'credit_card', 'other', name='account_type', create_type=False)
    category_type = ENUM('income', 'expense', name='category_type', create_type=False)
    transaction_type = ENUM('income', 'expense', 'transfer', name='transaction_type', create_type=False)
    
    # Create types if they don't exist
    for enum in [account_type, category_type, transaction_type]:
        try:
            enum.create(op.get_bind(), checkfirst=False)
        except psycopg2.errors.DuplicateObject:
            pass
    
    # Create accounts table
    op.create_table(
        'accounts',
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', account_type, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('limit', sa.Float(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('account_id'),
        sa.UniqueConstraint('uuid')
    )
    
    # Create indexes for accounts table
    op.create_index('idx_accounts_user_id', 'accounts', ['user_id'])
    op.create_index('idx_accounts_type', 'accounts', ['type'])
    op.create_index('idx_accounts_created_at', 'accounts', ['created_at'])
    
    # Create categories table
    op.create_table(
        'categories',
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', category_type, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('category_id'),
        sa.UniqueConstraint('uuid')
    )
    
    # Create indexes for categories table
    op.create_index('idx_categories_user_id', 'categories', ['user_id'])
    op.create_index('idx_categories_type', 'categories', ['type'])
    op.create_index('idx_categories_created_at', 'categories', ['created_at'])
    
    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(), nullable=False),
        sa.Column('transaction_date', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('transaction_type', transaction_type, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('destination_account_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.account_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.category_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['destination_account_id'], ['accounts.account_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('transaction_id'),
        sa.UniqueConstraint('uuid')
    )
    
    # Create indexes for transactions table
    op.create_index('idx_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('idx_transactions_account_id', 'transactions', ['account_id'])
    op.create_index('idx_transactions_category_id', 'transactions', ['category_id'])
    op.create_index('idx_transactions_destination_account_id', 'transactions', ['destination_account_id'])
    op.create_index('idx_transactions_transaction_type', 'transactions', ['transaction_type'])
    op.create_index('idx_transactions_transaction_date', 'transactions', ['transaction_date'])
    op.create_index('idx_transactions_created_at', 'transactions', ['created_at'])
    # Composite index for common query patterns
    op.create_index('idx_transactions_user_account_date', 'transactions', ['user_id', 'account_id', 'transaction_date'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_transactions_user_account_date', table_name='transactions')
    op.drop_index('idx_transactions_created_at', table_name='transactions')
    op.drop_index('idx_transactions_transaction_date', table_name='transactions')
    op.drop_index('idx_transactions_transaction_type', table_name='transactions')
    op.drop_index('idx_transactions_destination_account_id', table_name='transactions')
    op.drop_index('idx_transactions_category_id', table_name='transactions')
    op.drop_index('idx_transactions_account_id', table_name='transactions')
    op.drop_index('idx_transactions_user_id', table_name='transactions')
    
    op.drop_index('idx_categories_created_at', table_name='categories')
    op.drop_index('idx_categories_type', table_name='categories')
    op.drop_index('idx_categories_user_id', table_name='categories')
    
    op.drop_index('idx_accounts_created_at', table_name='accounts')
    op.drop_index('idx_accounts_type', table_name='accounts')
    op.drop_index('idx_accounts_user_id', table_name='accounts')
    
    # Drop tables
    op.drop_table('transactions')
    op.drop_table('categories')
    op.drop_table('accounts')
    
    # Drop ENUM types if they exist
    for enum_name in ['transaction_type', 'category_type', 'account_type']:
        op.execute(f'DROP TYPE IF EXISTS {enum_name}')
