"""Add ExtractedTable for table extraction (PRP 19)

Revision ID: c9a3d4e5f678
Revises: b8f2c5a1d234
Create Date: 2025-08-22 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c9a3d4e5f678'
down_revision: Union[str, None] = 'b8f2c5a1d234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create extracted_tables table
    op.create_table('extracted_tables',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('table_index', sa.Integer(), nullable=False),
        sa.Column('table_type', sa.String(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('headers', sa.JSON(), nullable=False),
        sa.Column('rows', sa.JSON(), nullable=False),
        sa.Column('units', sa.JSON(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('content_vector', Vector(384), nullable=True),
        sa.Column('bbox', sa.JSON(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_table_document', 'extracted_tables', 
                    ['document_id', 'page_number'])
    op.create_index('idx_table_type', 'extracted_tables', ['table_type'])
    
    # Create vector index for similarity search
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_table_content_vector "
        "ON extracted_tables USING ivfflat (content_vector vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_table_content_vector', table_name='extracted_tables')
    op.drop_index('idx_table_type', table_name='extracted_tables')
    op.drop_index('idx_table_document', table_name='extracted_tables')
    
    # Drop table
    op.drop_table('extracted_tables')