"""init

Revision ID: 8bc63af6c535
Revises: 
Create Date: 2025-03-18 04:51:17.409403

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.models.cuan import EnumAsString, TrxAccountType, TransactionType, TrxCategoryType


# revision identifiers, used by Alembic.
revision: str = '8bc63af6c535'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('users',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.UUID(), nullable=False),
    sa.Column('username', sa.String(), nullable=True),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('password', sa.String(), nullable=True),
    sa.Column('is_superuser', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('user_id'),
    sa.UniqueConstraint('uuid')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_user_id'), 'users', ['user_id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('posts',
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('excerpt', sa.String(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('slug', sa.String(), nullable=False),
    sa.Column('published', sa.Boolean(), nullable=True),
    sa.Column('reading_time', sa.Integer(), nullable=False),
    sa.Column('tags', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('embedding', sa.ARRAY(sa.Float()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('post_id'),
    sa.UniqueConstraint('slug'),
    sa.UniqueConstraint('uuid')
    )
    op.create_index(op.f('ix_posts_post_id'), 'posts', ['post_id'], unique=False)
    op.create_table('trx_accounts',
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', EnumAsString(TrxAccountType), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('limit', sa.DECIMAL(precision=10, scale=2), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('account_id'),
    sa.UniqueConstraint('uuid')
    )
    op.create_table('trx_categories',
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', EnumAsString(TrxCategoryType), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('category_id'),
    sa.UniqueConstraint('uuid')
    )
    op.create_table('transactions',
    sa.Column('transaction_id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.UUID(), nullable=False),
    sa.Column('transaction_date', sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=10, scale=2), nullable=False),
    sa.Column('transaction_type', EnumAsString(TransactionType), nullable=False),
    sa.Column('transfer_fee', sa.DECIMAL(precision=10, scale=2), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('destination_account_id', sa.Integer(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['trx_accounts.account_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['category_id'], ['trx_categories.category_id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['destination_account_id'], ['trx_accounts.account_id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('transaction_id'),
    sa.UniqueConstraint('uuid')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('transactions')
    op.drop_table('trx_categories')
    op.drop_table('trx_accounts')
    op.drop_index(op.f('ix_posts_post_id'), table_name='posts')
    op.drop_table('posts')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_user_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    # ### end Alembic commands ###
