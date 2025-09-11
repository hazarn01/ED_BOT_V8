"""Add highlighting fields for source attribution (PRP 17-18)

Revision ID: b8f2c5a1d234
Revises: 086828fa1d96
Create Date: 2025-08-22 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8f2c5a1d234'
down_revision: Union[str, None] = '086828fa1d96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add highlighting fields to document_chunks table
    op.add_column('document_chunks', 
        sa.Column('page_span_start', sa.Integer(), nullable=True))
    op.add_column('document_chunks',
        sa.Column('page_span_end', sa.Integer(), nullable=True))
    op.add_column('document_chunks',
        sa.Column('document_span_start', sa.Integer(), nullable=True))
    op.add_column('document_chunks',
        sa.Column('document_span_end', sa.Integer(), nullable=True))
    op.add_column('document_chunks',
        sa.Column('bbox', sa.JSON(), nullable=True))
    
    # Add page-based retrieval index
    op.create_index('idx_chunk_page', 'document_chunks', 
                    ['document_id', 'page_number'])
    
    # Create query response cache table for PDF viewer
    op.create_table('query_response_cache',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('response', sa.JSON(), nullable=False),
        sa.Column('highlights', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_response_expires', 'query_response_cache', 
                    ['expires_at'])


def downgrade() -> None:
    # Drop query response cache table
    op.drop_index('idx_response_expires', table_name='query_response_cache')
    op.drop_table('query_response_cache')
    
    # Drop page index
    op.drop_index('idx_chunk_page', table_name='document_chunks')
    
    # Remove highlighting fields from document_chunks
    op.drop_column('document_chunks', 'bbox')
    op.drop_column('document_chunks', 'document_span_end')
    op.drop_column('document_chunks', 'document_span_start')
    op.drop_column('document_chunks', 'page_span_end')
    op.drop_column('document_chunks', 'page_span_start')