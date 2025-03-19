"""add_vector_index

Revision ID: 1494e1cfce48
Revises: 3f49ac202510
Create Date: 2024-03-18 03:20:45.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1494e1cfce48'
down_revision: Union[str, None] = '3f49ac202510'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create an IVFFlat index on the embedding column
    # This index type is good for approximate nearest neighbor search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS posts_embedding_idx
        ON posts USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade() -> None:
    # Drop the index if it exists
    op.execute("DROP INDEX IF EXISTS posts_embedding_idx")
