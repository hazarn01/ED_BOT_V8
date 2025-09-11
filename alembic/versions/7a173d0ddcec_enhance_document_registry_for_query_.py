"""Enhance document registry for query type classification

Revision ID: 7a173d0ddcec
Revises: c9a3d4e5f678
Create Date: 2025-08-27 10:31:55.816730

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7a173d0ddcec'
down_revision: Union[str, None] = 'c9a3d4e5f678'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add enhanced categorization fields to document_registry table
    op.add_column('document_registry', 
        sa.Column('query_type', sa.String(), nullable=True))
    op.add_column('document_registry',
        sa.Column('confidence', sa.Float(), nullable=True, default=0.0))
    op.add_column('document_registry',
        sa.Column('classification_method', sa.String(), nullable=True))
    op.add_column('document_registry',
        sa.Column('medical_specialty', sa.String(), nullable=True))
    op.add_column('document_registry',
        sa.Column('urgency_level', sa.String(), nullable=True))
    op.add_column('document_registry',
        sa.Column('primary_keywords', sa.JSON(), nullable=True, default=[]))
    op.add_column('document_registry',
        sa.Column('medical_terms', sa.JSON(), nullable=True, default=[]))
    op.add_column('document_registry',
        sa.Column('abbreviations', sa.JSON(), nullable=True, default=[]))
    
    # Add indexes for enhanced search capabilities
    op.create_index('idx_registry_query_type', 'document_registry', ['query_type'])
    op.create_index('idx_registry_medical_specialty', 'document_registry', ['medical_specialty'])
    op.create_index('idx_registry_urgency', 'document_registry', ['urgency_level'])
    op.create_index('idx_registry_confidence', 'document_registry', ['confidence'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_registry_confidence', table_name='document_registry')
    op.drop_index('idx_registry_urgency', table_name='document_registry')
    op.drop_index('idx_registry_medical_specialty', table_name='document_registry')
    op.drop_index('idx_registry_query_type', table_name='document_registry')
    
    # Remove enhanced categorization fields
    op.drop_column('document_registry', 'abbreviations')
    op.drop_column('document_registry', 'medical_terms')
    op.drop_column('document_registry', 'primary_keywords')
    op.drop_column('document_registry', 'urgency_level')
    op.drop_column('document_registry', 'medical_specialty')
    op.drop_column('document_registry', 'classification_method')
    op.drop_column('document_registry', 'confidence')
    op.drop_column('document_registry', 'query_type')