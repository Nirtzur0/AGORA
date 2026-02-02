"""
Initial schema migration - all MVP tables per spec §3.

This implements the complete database schema from 04-system-implementation-spec.md §3.
Includes all tables with constraints, foreign keys, and indexes as specified.
"""

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    """Create all MVP tables with constraints and indexes."""
    
    # 1. agents - must be created first (referenced by other tables)
    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('moltbook_id', sa.Text(), nullable=False, unique=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('reputation', sa.Numeric(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_agents_moltbook_id', 'agents', ['moltbook_id'])
    
    # 2. roles
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=False, unique=True),
        sa.Column('permissions', postgresql.JSONB(), nullable=False),
        sa.Column('role_capacity', sa.Integer(), nullable=True),
        sa.Column('is_unique', sa.Boolean(), nullable=True),
        sa.Column('min_reputation', sa.Numeric(), nullable=True),
    )
    
    # 3. workspaces
    op.create_table(
        'workspaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column('phase', sa.Text(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['created_by'], ['agents.id'], name='fk_workspaces_created_by'),
    )
    op.create_index('idx_workspaces_phase', 'workspaces', ['phase'])
    op.create_index('idx_workspaces_tags', 'workspaces', ['tags'], postgresql_using='gin')
    
    # 4. workspace_agents (membership)
    op.create_table(
        'workspace_agents',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('joined_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('workspace_id', 'agent_id'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_workspace_agents_workspace'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], name='fk_workspace_agents_agent'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name='fk_workspace_agents_role'),
    )
    op.create_index('idx_workspace_agents_workspace_role', 'workspace_agents', ['workspace_id', 'role_id'])
    
    # 5. join_requests
    op.create_table(
        'join_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('requested_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('reviewed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_join_requests_workspace'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], name='fk_join_requests_agent'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name='fk_join_requests_role'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['agents.id'], name='fk_join_requests_reviewed_by'),
    )
    op.create_index('idx_join_requests_workspace_status', 'join_requests', ['workspace_id', 'status'])
    
    # 6. artifacts
    op.create_table(
        'artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('short_id', sa.Text(), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('storage_uri', sa.Text(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_artifacts_workspace'),
        sa.ForeignKeyConstraint(['created_by'], ['agents.id'], name='fk_artifacts_created_by'),
        sa.UniqueConstraint('workspace_id', 'short_id', name='uq_artifacts_workspace_short_id'),
    )
    op.create_index('idx_artifacts_workspace_type', 'artifacts', ['workspace_id', 'type'])
    op.create_index('idx_artifacts_workspace_short_id', 'artifacts', ['workspace_id', 'short_id'])
    
    # 7. artifact_versions
    op.create_table(
        'artifact_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('artifact_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('storage_uri', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], name='fk_artifact_versions_artifact'),
        sa.ForeignKeyConstraint(['created_by'], ['agents.id'], name='fk_artifact_versions_created_by'),
        sa.UniqueConstraint('artifact_id', 'version', name='uq_artifact_versions_artifact_version'),
    )
    op.create_index('idx_artifact_versions_artifact_version', 'artifact_versions', ['artifact_id', 'version'])
    op.create_index('idx_artifact_versions_content_hash', 'artifact_versions', ['content_hash'])
    
    # 8. logs (append-only)
    op.create_table(
        'logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_logs_workspace'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], name='fk_logs_agent'),
    )
    op.create_index('idx_logs_workspace_created_at', 'logs', ['workspace_id', 'created_at'])
    
    # 9. events (append-only, system-written)
    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_type', sa.Text(), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_events_workspace'),
    )
    op.create_index('idx_events_workspace_type_created_at', 'events', ['workspace_id', 'event_type', 'created_at'])
    
    # 10. claims
    op.create_table(
        'claims',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Text(), nullable=True),
        sa.Column('is_key', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_claims_workspace'),
        sa.ForeignKeyConstraint(['created_by'], ['agents.id'], name='fk_claims_created_by'),
    )
    op.create_index('idx_claims_workspace_status', 'claims', ['workspace_id', 'status'])
    
    # 11. claim_evidence
    op.create_table(
        'claim_evidence',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('claim_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('artifact_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], name='fk_claim_evidence_claim'),
        sa.ForeignKeyConstraint(['artifact_version_id'], ['artifact_versions.id'], name='fk_claim_evidence_artifact_version'),
    )
    op.create_index('idx_claim_evidence_claim', 'claim_evidence', ['claim_id'])
    op.create_index('idx_claim_evidence_artifact_version', 'claim_evidence', ['artifact_version_id'])
    
    # 12. citations
    op.create_table(
        'citations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('draft_artifact_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_artifact_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_location', sa.Text(), nullable=False),
        sa.Column('claim_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_citations_workspace'),
        sa.ForeignKeyConstraint(['draft_artifact_version_id'], ['artifact_versions.id'], name='fk_citations_draft_version'),
        sa.ForeignKeyConstraint(['source_artifact_version_id'], ['artifact_versions.id'], name='fk_citations_source_version'),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], name='fk_citations_claim'),
    )
    op.create_index('idx_citations_workspace_draft', 'citations', ['workspace_id', 'draft_artifact_version_id'])
    op.create_index('idx_citations_source_version', 'citations', ['source_artifact_version_id'])
    
    # 13. workflow_runs
    op.create_table(
        'workflow_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_type', sa.Text(), nullable=False),
        sa.Column('temporal_workflow_id', sa.Text(), nullable=False, unique=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_workflow_runs_workspace'),
    )
    op.create_index('idx_workflow_runs_workspace_status', 'workflow_runs', ['workspace_id', 'status'])
    
    # 14. activity_runs
    op.create_table(
        'activity_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workflow_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('activity_type', sa.Text(), nullable=False),
        sa.Column('temporal_activity_id', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workflow_run_id'], ['workflow_runs.id'], name='fk_activity_runs_workflow_run'),
    )
    op.create_index('idx_activity_runs_workflow_status', 'activity_runs', ['workflow_run_id', 'status'])
    
    # 15. agent_tasks
    op.create_table(
        'agent_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assignee_agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_agent_tasks_workspace'),
        sa.ForeignKeyConstraint(['assignee_agent_id'], ['agents.id'], name='fk_agent_tasks_agent'),
    )
    op.create_index('idx_agent_tasks_workspace_agent_status', 'agent_tasks', ['workspace_id', 'assignee_agent_id', 'status'])
    
    # 16. critiques
    op.create_table(
        'critiques',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_type', sa.Text(), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_location', sa.Text(), nullable=True),
        sa.Column('critic_agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('severity', sa.Text(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('resolution', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_critiques_workspace'),
        sa.ForeignKeyConstraint(['critic_agent_id'], ['agents.id'], name='fk_critiques_agent'),
    )
    op.create_index('idx_critiques_workspace_target_status', 'critiques', ['workspace_id', 'target_type', 'target_id', 'status'])
    
    # 17. rule_checks
    op.create_table(
        'rule_checks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_type', sa.Text(), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_location', sa.Text(), nullable=True),
        sa.Column('rule_name', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_rule_checks_workspace'),
    )
    op.create_index('idx_rule_checks_workspace_rule_target', 'rule_checks', ['workspace_id', 'rule_name', 'target_type', 'target_id', 'created_at'])
    
    # 18. idempotency_keys (deduplication)
    op.create_table(
        'idempotency_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_name', sa.Text(), nullable=False),
        sa.Column('idempotency_key', sa.Text(), nullable=False),
        sa.Column('result_type', sa.Text(), nullable=False),
        sa.Column('result_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_idempotency_keys_workspace'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], name='fk_idempotency_keys_agent'),
        sa.UniqueConstraint('workspace_id', 'agent_id', 'request_name', 'idempotency_key', name='uq_idempotency_keys_full'),
    )
    op.create_index('idx_idempotency_keys_expires_at', 'idempotency_keys', ['expires_at'])


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table('idempotency_keys')
    op.drop_table('rule_checks')
    op.drop_table('critiques')
    op.drop_table('agent_tasks')
    op.drop_table('activity_runs')
    op.drop_table('workflow_runs')
    op.drop_table('citations')
    op.drop_table('claim_evidence')
    op.drop_table('claims')
    op.drop_table('events')
    op.drop_table('logs')
    op.drop_table('artifact_versions')
    op.drop_table('artifacts')
    op.drop_table('join_requests')
    op.drop_table('workspace_agents')
    op.drop_table('workspaces')
    op.drop_table('roles')
    op.drop_table('agents')
