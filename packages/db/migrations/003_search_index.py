"""
Search index migration - Postgres FTS for artifacts

Per spec §6.5, §9:
- Postgres full-text search on parsed artifacts
- Indexes PDF text, repo file text, and logs
- Support GET /search?workspace_id=...&query=...
"""

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    """Create search_index table with Postgres FTS support."""
    
    # Create search_index table
    op.create_table(
        'search_index',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('artifact_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('artifact_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('artifact_type', sa.Text(), nullable=False),  # pdf, repo, log, etc.
        sa.Column('content', sa.Text(), nullable=False),  # Searchable text content
        sa.Column('metadata', postgresql.JSONB(), nullable=True),  # Optional metadata (file path, page number, etc.)
        sa.Column('indexed_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_search_index_workspace', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], name='fk_search_index_artifact', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name='fk_search_index_version', ondelete='CASCADE'),
    )
    
    # Indexes for efficient querying
    op.create_index('idx_search_index_workspace', 'search_index', ['workspace_id'])
    op.create_index('idx_search_index_artifact', 'search_index', ['artifact_id'])
    op.create_index('idx_search_index_version', 'search_index', ['artifact_version_id'])
    op.create_index('idx_search_index_type', 'search_index', ['artifact_type'])
    
    # Create FTS index using tsvector
    # Add tsvector column for efficient full-text search
    op.execute("""
        ALTER TABLE search_index 
        ADD COLUMN content_tsv tsvector 
        GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
    """)
    
    # Create GIN index on tsvector for fast search
    op.create_index(
        'idx_search_index_content_tsv',
        'search_index',
        ['content_tsv'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    """Drop search_index table and indexes."""
    op.drop_index('idx_search_index_content_tsv', table_name='search_index')
    op.drop_index('idx_search_index_type', table_name='search_index')
    op.drop_index('idx_search_index_version', table_name='search_index')
    op.drop_index('idx_search_index_artifact', table_name='search_index')
    op.drop_index('idx_search_index_workspace', table_name='search_index')
    op.drop_table('search_index')
