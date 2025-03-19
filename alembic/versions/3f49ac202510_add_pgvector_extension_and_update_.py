"""add_pgvector_extension_and_update_embedding_column

Revision ID: 3f49ac202510
Revises: 8bc63af6c535
Create Date: 2024-03-18 02:42:45.123456

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '3f49ac202510'
down_revision = '8bc63af6c535'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Drop the existing embedding column
    op.drop_column('posts', 'embedding')
    
    # Add the new vector column
    op.add_column('posts', sa.Column('embedding', Vector(1536), nullable=True))


def downgrade() -> None:
    # Drop the vector column
    op.drop_column('posts', 'embedding')
    
    # Add back the original ARRAY(Float) column
    op.add_column('posts', sa.Column('embedding', sa.ARRAY(sa.Float()), nullable=True))
    
    # Drop the pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
