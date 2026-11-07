"""github_ingestion_and_correlations

Revision ID: 0002_github_ingestion
Revises: 0001_initial_schema
Create Date: 2026-11-07 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0002_github_ingestion'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create webhook_deliveries
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('delivery_id', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('signature', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), default='RECEIVED', nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_webhook_delivery_tenant_delivery', 'webhook_deliveries', ['tenant_id', 'delivery_id'], unique=True)
    op.create_index('ix_webhook_delivery_status_time', 'webhook_deliveries', ['status', 'received_at'])

    # 2. Add columns to repositories
    op.add_column('repositories', sa.Column('github_repo_id', sa.String(100), nullable=True))
    op.add_column('repositories', sa.Column('owner_login', sa.String(255), nullable=True))
    op.add_column('repositories', sa.Column('is_private', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('repositories', sa.Column('html_url', sa.String(512), nullable=True))
    op.create_index('ix_repositories_github_repo_id', 'repositories', ['github_repo_id'])

    # 3. Add columns to commits
    op.add_column('commits', sa.Column('github_commit_id', sa.String(100), nullable=True))
    op.add_column('commits', sa.Column('author_login', sa.String(255), nullable=True))
    op.add_column('commits', sa.Column('html_url', sa.String(512), nullable=True))
    op.add_column('commits', sa.Column('stats_additions', sa.Integer(), server_default='0', nullable=False))
    op.add_column('commits', sa.Column('stats_deletions', sa.Integer(), server_default='0', nullable=False))

    # 4. Create pull_requests
    op.create_table(
        'pull_requests',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repository_id', sa.CHAR(36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('github_pr_id', sa.String(100), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(512), nullable=False),
        sa.Column('state', sa.String(50), default='open', nullable=False),
        sa.Column('is_merged', sa.Boolean(), default=False, nullable=False),
        sa.Column('merged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('head_sha', sa.String(64), nullable=False),
        sa.Column('base_branch', sa.String(255), default='main', nullable=False),
        sa.Column('head_branch', sa.String(255), nullable=False),
        sa.Column('author_login', sa.String(255), nullable=True),
        sa.Column('html_url', sa.String(512), nullable=True),
        sa.Column('changed_files_count', sa.Integer(), default=0, nullable=False),
        sa.Column('additions', sa.Integer(), default=0, nullable=False),
        sa.Column('deletions', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_pr_tenant_repo_number', 'pull_requests', ['tenant_id', 'repository_id', 'number'], unique=True)
    op.create_index('ix_pr_head_sha', 'pull_requests', ['tenant_id', 'head_sha'])

    # 5. Create workflow_runs
    op.create_table(
        'workflow_runs',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repository_id', sa.CHAR(36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('commit_id', sa.CHAR(36), sa.ForeignKey('commits.id', ondelete='SET NULL'), nullable=True),
        sa.Column('github_run_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('head_sha', sa.String(64), nullable=False),
        sa.Column('head_branch', sa.String(255), default='main', nullable=False),
        sa.Column('event', sa.String(100), default='push', nullable=False),
        sa.Column('status', sa.String(50), default='queued', nullable=False),
        sa.Column('conclusion', sa.String(50), nullable=True),
        sa.Column('run_number', sa.Integer(), default=1, nullable=False),
        sa.Column('run_attempt', sa.Integer(), default=1, nullable=False),
        sa.Column('actor_login', sa.String(255), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('html_url', sa.String(512), nullable=True),
        sa.Column('logs_url', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_run_tenant_github_id', 'workflow_runs', ['tenant_id', 'github_run_id'], unique=True)
    op.create_index('ix_run_repo_head_sha', 'workflow_runs', ['repository_id', 'head_sha'])

    # 6. Create workflow_jobs
    op.create_table(
        'workflow_jobs',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workflow_run_id', sa.CHAR(36), sa.ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('github_job_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), default='queued', nullable=False),
        sa.Column('conclusion', sa.String(50), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('runner_name', sa.String(255), nullable=True),
        sa.Column('steps_summary', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_job_tenant_github_id', 'workflow_jobs', ['tenant_id', 'github_job_id'], unique=True)

    # 7. Add workflow_run_id to builds
    op.add_column('builds', sa.Column('workflow_run_id', sa.CHAR(36), sa.ForeignKey('workflow_runs.id', ondelete='SET NULL'), nullable=True))

    # 8. Add columns to deployments
    op.add_column('deployments', sa.Column('github_deployment_id', sa.String(100), nullable=True))
    op.add_column('deployments', sa.Column('creator_login', sa.String(255), nullable=True))
    op.add_column('deployments', sa.Column('workflow_run_id', sa.CHAR(36), sa.ForeignKey('workflow_runs.id', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_deployments_github_deployment_id', 'deployments', ['github_deployment_id'])

    # 9. Create deployment_events
    op.create_table(
        'deployment_events',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('deployment_id', sa.CHAR(36), sa.ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('github_deployment_id', sa.String(100), nullable=True),
        sa.Column('github_deployment_status_id', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('environment', sa.String(100), default='production', nullable=False),
        sa.Column('creator_login', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_dep_event_time', 'deployment_events', ['deployment_id', 'occurred_at'])


def downgrade() -> None:
    op.drop_table('deployment_events')
    op.drop_column('deployments', 'workflow_run_id')
    op.drop_column('deployments', 'creator_login')
    op.drop_column('deployments', 'github_deployment_id')
    op.drop_column('builds', 'workflow_run_id')
    op.drop_table('workflow_jobs')
    op.drop_table('workflow_runs')
    op.drop_table('pull_requests')
    op.drop_column('commits', 'stats_deletions')
    op.drop_column('commits', 'stats_additions')
    op.drop_column('commits', 'html_url')
    op.drop_column('commits', 'author_login')
    op.drop_column('commits', 'github_commit_id')
    op.drop_column('repositories', 'html_url')
    op.drop_column('repositories', 'is_private')
    op.drop_column('repositories', 'owner_login')
    op.drop_column('repositories', 'github_repo_id')
    op.drop_table('webhook_deliveries')
