"""initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-07 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0. Enable pgvector if postgresql
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 1. Tenants
    op.create_table(
        'tenants',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'])

    # 2. Organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_org_tenant_slug', 'organizations', ['tenant_id', 'slug'], unique=True)

    # 3. Users
    op.create_table(
        'users',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), default='developer', nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_user_tenant_email', 'users', ['tenant_id', 'email'], unique=True)

    # 4. Repositories
    op.create_table(
        'repositories',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.CHAR(36), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('provider', sa.String(50), default='github', nullable=False),
        sa.Column('default_branch', sa.String(100), default='main', nullable=False),
        sa.Column('clone_url', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_repositories_full_name', 'repositories', ['full_name'])

    # 5. Services
    op.create_table(
        'services',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repository_id', sa.CHAR(36), sa.ForeignKey('repositories.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tier', sa.String(50), default='tier-2', nullable=False),
        sa.Column('health_status', sa.String(50), default='healthy', nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_service_tenant_slug', 'services', ['tenant_id', 'slug'], unique=True)

    # 6. Environments
    op.create_table(
        'environments',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('is_production', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_env_tenant_slug', 'environments', ['tenant_id', 'slug'], unique=True)

    # 7. Service Dependencies
    op.create_table(
        'service_dependencies',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_service_id', sa.CHAR(36), sa.ForeignKey('services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_service_id', sa.CHAR(36), sa.ForeignKey('services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dependency_type', sa.String(50), default='sync_http', nullable=False),
        sa.Column('criticality', sa.String(50), default='high', nullable=False),
        sa.Column('weight', sa.Float(), default=1.0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_svc_dep_unique', 'service_dependencies', ['tenant_id', 'source_service_id', 'target_service_id'], unique=True)

    # 8. Commits
    op.create_table(
        'commits',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repository_id', sa.CHAR(36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('commit_sha', sa.String(64), nullable=False),
        sa.Column('branch', sa.String(255), default='main', nullable=False),
        sa.Column('author_name', sa.String(255), nullable=True),
        sa.Column('author_email', sa.String(255), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('committed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_commit_tenant_repo_sha', 'commits', ['tenant_id', 'repository_id', 'commit_sha'], unique=True)

    # 9. Changes
    op.create_table(
        'changes',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('commit_id', sa.CHAR(36), sa.ForeignKey('commits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('change_type', sa.String(50), default='modified', nullable=False),
        sa.Column('additions', sa.Integer(), default=0, nullable=False),
        sa.Column('deletions', sa.Integer(), default=0, nullable=False),
        sa.Column('patch_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 10. Builds
    op.create_table(
        'builds',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repository_id', sa.CHAR(36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('commit_sha', sa.String(64), nullable=False),
        sa.Column('build_number', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(50), default='pending', nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('docker_image_tag', sa.String(255), nullable=True),
        sa.Column('tests_passed', sa.Integer(), default=0, nullable=False),
        sa.Column('tests_failed', sa.Integer(), default=0, nullable=False),
        sa.Column('logs_summary', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 11. Deployments
    op.create_table(
        'deployments',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_id', sa.CHAR(36), sa.ForeignKey('services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('build_id', sa.CHAR(36), sa.ForeignKey('builds.id', ondelete='SET NULL'), nullable=True),
        sa.Column('environment', sa.String(100), default='production', nullable=False),
        sa.Column('commit_sha', sa.String(64), nullable=False),
        sa.Column('status', sa.String(50), default='PENDING', nullable=False),
        sa.Column('triggered_by', sa.String(255), default='github_action', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('rollback_from_id', sa.CHAR(36), sa.ForeignKey('deployments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 12. Infrastructure Changes
    op.create_table(
        'infrastructure_changes',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('deployment_id', sa.CHAR(36), sa.ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_id', sa.CHAR(36), sa.ForeignKey('services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('change_category', sa.String(50), nullable=False),
        sa.Column('file_path', sa.String(512), nullable=False),
        sa.Column('diff_content', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(50), default='low', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 13. Events
    op.create_table(
        'events',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_id', sa.String(255), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('schema_version', sa.String(20), default='1.0.0', nullable=False),
        sa.Column('repository_id', sa.CHAR(36), nullable=True),
        sa.Column('service_id', sa.CHAR(36), nullable=True),
        sa.Column('deployment_id', sa.CHAR(36), nullable=True),
        sa.Column('commit_sha', sa.String(64), nullable=True),
        sa.Column('environment', sa.String(100), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('correlation_id', sa.String(255), nullable=False),
        sa.Column('idempotency_key', sa.String(255), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_event_tenant_idempotency', 'events', ['tenant_id', 'idempotency_key'], unique=True)
    op.create_index('ix_event_tenant_type_occurred', 'events', ['tenant_id', 'event_type', 'occurred_at'])

    # 14. Incidents
    op.create_table(
        'incidents',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_id', sa.CHAR(36), sa.ForeignKey('services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('deployment_id', sa.CHAR(36), sa.ForeignKey('deployments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(20), default='P2', nullable=False),
        sa.Column('status', sa.String(50), default='OPEN', nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('blast_radius_score', sa.Float(), default=1.0, nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 15. Failures
    op.create_table(
        'failures',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('incident_id', sa.CHAR(36), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_id', sa.CHAR(36), sa.ForeignKey('services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('failure_type', sa.String(100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('container_name', sa.String(255), nullable=True),
        sa.Column('pod_name', sa.String(255), nullable=True),
        sa.Column('exit_code', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 16. Root Cause Hypotheses
    op.create_table(
        'root_cause_hypotheses',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('incident_id', sa.CHAR(36), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('change_id', sa.CHAR(36), sa.ForeignKey('changes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('infrastructure_change_id', sa.CHAR(36), sa.ForeignKey('infrastructure_changes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('hypothesis_statement', sa.Text(), nullable=False),
        sa.Column('confidence_score', sa.Float(), default=0.5, nullable=False),
        sa.Column('status', sa.String(50), default='SUSPECTED_CAUSE', nullable=False),
        sa.Column('evidence_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 17. Confirmed Root Causes
    op.create_table(
        'confirmed_root_causes',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('incident_id', sa.CHAR(36), sa.ForeignKey('incidents.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('confirmed_by_user_id', sa.CHAR(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('root_cause_summary', sa.Text(), nullable=False),
        sa.Column('verified_engineering_lesson', sa.Text(), nullable=False),
        sa.Column('prevention_strategy', sa.Text(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 18. Remediation Actions
    op.create_table(
        'remediation_actions',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('incident_id', sa.CHAR(36), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('failure_id', sa.CHAR(36), sa.ForeignKey('failures.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('runbook_url', sa.String(512), nullable=True),
        sa.Column('estimated_recovery_time_sec', sa.Float(), nullable=True),
        sa.Column('is_automated_executable', sa.String(10), default='false', nullable=False),
        sa.Column('execution_status', sa.String(50), default='PROPOSED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 19. Risk Assessments
    op.create_table(
        'risk_assessments',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('deployment_id', sa.CHAR(36), sa.ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_id', sa.CHAR(36), sa.ForeignKey('services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('overall_risk_score', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.String(20), nullable=False),
        sa.Column('failure_probability', sa.Float(), nullable=True),
        sa.Column('operational_impact_score', sa.Float(), nullable=False),
        sa.Column('rule_score', sa.Float(), default=0.0, nullable=False),
        sa.Column('ml_score', sa.Float(), nullable=True),
        sa.Column('triggered_rules', sa.JSON(), nullable=False),
        sa.Column('supporting_records', sa.JSON(), nullable=False),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 20. Recommendations
    op.create_table(
        'recommendations',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('risk_assessment_id', sa.CHAR(36), sa.ForeignKey('risk_assessments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('deployment_id', sa.CHAR(36), sa.ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recommendation_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('mitigation_steps', sa.JSON(), nullable=False),
        sa.Column('confidence_score', sa.Float(), default=0.8, nullable=False),
        sa.Column('requires_approval', sa.String(10), default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 21. Approval Requests
    op.create_table(
        'approval_requests',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('deployment_id', sa.CHAR(36), sa.ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recommendation_id', sa.CHAR(36), sa.ForeignKey('recommendations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('requested_action', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), default='WAITING_FOR_APPROVAL', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('context_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 22. Approval Decisions
    op.create_table(
        'approval_decisions',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('approval_request_id', sa.CHAR(36), sa.ForeignKey('approval_requests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('decided_by_user_id', sa.CHAR(36), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('decision', sa.String(20), nullable=False),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('audit_signature', sa.String(255), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 23. Model Versions
    op.create_table(
        'model_versions',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('model_name', sa.String(100), default='deployment_risk_xgboost', nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('algorithm', sa.String(100), default='XGBoostClassifier', nullable=False),
        sa.Column('status', sa.String(50), default='CANDIDATE', nullable=False),
        sa.Column('training_dataset_size', sa.Integer(), default=0, nullable=False),
        sa.Column('features_list', sa.JSON(), nullable=False),
        sa.Column('hyperparameters', sa.JSON(), nullable=False),
        sa.Column('evaluation_metrics', sa.JSON(), nullable=False),
        sa.Column('is_calibrated', sa.String(10), default='false', nullable=False),
        sa.Column('artifact_path', sa.String(512), nullable=True),
        sa.Column('trained_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_model_version_tenant_name', 'model_versions', ['tenant_id', 'model_name', 'version'], unique=True)


def downgrade() -> None:
    op.drop_table('model_versions')
    op.drop_table('approval_decisions')
    op.drop_table('approval_requests')
    op.drop_table('recommendations')
    op.drop_table('risk_assessments')
    op.drop_table('remediation_actions')
    op.drop_table('confirmed_root_causes')
    op.drop_table('root_cause_hypotheses')
    op.drop_table('failures')
    op.drop_table('incidents')
    op.drop_table('events')
    op.drop_table('infrastructure_changes')
    op.drop_table('deployments')
    op.drop_table('builds')
    op.drop_table('changes')
    op.drop_table('commits')
    op.drop_table('service_dependencies')
    op.drop_table('environments')
    op.drop_table('services')
    op.drop_table('repositories')
    op.drop_table('users')
    op.drop_table('organizations')
    op.drop_table('tenants')
