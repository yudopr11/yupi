"""add_embedding_column

Revision ID: 3e03d8a7da83
Revises: e13f19145873
Create Date: 2025-03-02 17:39:23.675768

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, FLOAT


# revision identifiers, used by Alembic.
revision: str = '3e03d8a7da83'
down_revision: Union[str, None] = 'e13f19145873'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add embedding column to posts table (using ARRAY of FLOAT)
    op.add_column('posts', sa.Column('embedding', ARRAY(FLOAT), nullable=True))
    
    # Create function for cosine similarity calculation in PostgreSQL
    op.execute("""
    CREATE OR REPLACE FUNCTION cosine_similarity(a FLOAT[], b FLOAT[])
    RETURNS FLOAT AS $$
    DECLARE
        dot_product FLOAT := 0;
        norm_a FLOAT := 0;
        norm_b FLOAT := 0;
    BEGIN
        -- Calculate dot product and vector magnitudes
        FOR i IN 1..array_length(a, 1) LOOP
            dot_product := dot_product + (a[i] * b[i]);
            norm_a := norm_a + (a[i] * a[i]);
            norm_b := norm_b + (b[i] * b[i]);
        END LOOP;
        
        -- Handle zero vectors
        IF norm_a = 0 OR norm_b = 0 THEN
            RETURN 0;
        END IF;
        
        -- Return cosine similarity
        RETURN dot_product / (SQRT(norm_a) * SQRT(norm_b));
    END;
    $$ LANGUAGE plpgsql IMMUTABLE;
    """)
    
    # Create an index on the embedding column to speed up similarity search
    op.execute("""
    CREATE INDEX IF NOT EXISTS posts_embedding_idx ON posts USING gin (embedding);
    """)


def downgrade() -> None:
    # Drop the index
    op.execute("DROP INDEX IF EXISTS posts_embedding_idx;")
    
    # Drop the function
    op.execute("DROP FUNCTION IF EXISTS cosine_similarity;")
    
    # Drop the embedding column
    op.drop_column('posts', 'embedding')
