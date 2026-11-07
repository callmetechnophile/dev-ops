"""agent_orchestration_and_approvals

Revision ID: 0005_agent_approvals
Revises: 0004_predictive_intelligence
Create Date: 2026-11-07 21:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0005_agent_approvals'
down_revision = '0004_predictive_intelligence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create agent_executions
    op.create_table(
        'agent_executions',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('trigger_type', sa.String(100), nullable=False),
        sa.Column('trigger_reference', sa.String(255), nullable=False),
        sa.Column('deployment_id', sa.CHAR(36), sa.ForeignKey('deployments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('service_id', sa.CHAR(36), sa.ForeignKey('services.id', ondelete='SET NULL'), nullable=True),
        sa.Column('environment', sa.String(100), server_default='production', nullable=False),
        sa.Column('current_state', sa.String(50), server_default='DEPLOYMENT_DETECTED', nullable=False),
        sa.Column('execution_status', sa.String(50), server_default='RUNNING', nullable=False),
        sa.Column('context_snapshot', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('missing_context', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_agent_exec_tenant_status', 'agent_executions', ['tenant_id', 'execution_status'])
    op.create_index('ix_agent_exec_tenant_state', 'agent_executions', ['tenant_id', 'current_state'])
    op.create_index('ix_agent_exec_trigger', 'agent_executions', ['tenant_id', 'trigger_type', 'trigger_reference'])

    # 2. Create agent_state_transitions
    op.create_table(
        'agent_state_transitions',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('execution_id', sa.CHAR(36), sa.ForeignKey('agent_executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('previous_state', sa.String(50), nullable=False),
        sa.Column('next_state', sa.String(50), nullable=False),
        sa.Column('transition_reason', sa.Text(), nullable=False),
        sa.Column('triggered_by', sa.String(100), server_default='SYSTEM_ORCHESTRATOR', nullable=False),
        sa.Column('payload', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_agent_trans_exec_order', 'agent_state_transitions', ['execution_id', 'created_at'])

    # 3. Create deployment_policies
    op.create_table(
        'deployment_policies',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('policy_version', sa.String(50), server_default='v1.0.0', nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('policy_definition', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_tenant_policy_name'),
    )

    # 4. Create policy_evaluations
    op.create_table(
        'policy_evaluations',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('execution_id', sa.CHAR(36), sa.ForeignKey('agent_executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('policy_id', sa.CHAR(36), sa.ForeignKey('deployment_policies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('policy_version', sa.String(50), server_default='v1.0.0', nullable=False),
        sa.Column('outcome', sa.String(50), nullable=False),
        sa.Column('evidence', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 5. Create outcome_observations
    op.create_table(
        'outcome_observations',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('execution_id', sa.CHAR(36), sa.ForeignKey('agent_executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('deployment_id', sa.CHAR(36), sa.ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('observation_type', sa.String(100), nullable=False),
        sa.Column('observation_value', sa.String(100), nullable=False),
        sa.Column('evidence_reference', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 6. Alter approval_requests
    with op.batch_alter_table('approval_requests') as batch_op:
        batch_op.add_column(sa.Column('execution_id', sa.CHAR(36), sa.ForeignKey('agent_executions.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('assigned_reviewer_id', sa.CHAR(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('policy_version', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('risk_assessment_version', sa.String(50), nullable=True))
        batch_op.create_index('ix_approval_requests_execution_id', ['execution_id'])

    # 7. Alter approval_decisions
    with op.batch_alter_table('approval_decisions') as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))

    # 8. Alter recommendations
    with op.batch_alter_table('recommendations') as batch_op:
        batch_op.add_column(sa.Column('execution_id', sa.CHAR(36), sa.ForeignKey('agent_executions.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('explanation', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('evidence_references', sa.JSON(), server_default='{}', nullable=False))
        batch_op.add_column(sa.Column('confidence_level', sa.String(20), server_default='MEDIUM', nullable=False))
        batch_op.add_column(sa.Column('status', sa.String(50), server_default='PROPOSED', nullable=False))
        batch_op.create_index('ix_recommendations_execution_id', ['execution_id'])


def downgrade() -> None:
    with op.batch_alter_table('recommendations') as batch_op:
        batch_op.drop_index('ix_recommendations_execution_id')
        batch_op.drop_column('status')
        batch_op.drop_column('confidence_level')
        batch_op.drop_column('evidence_references')
        batch_op.drop_column('explanation')
        batch_op.drop_column('execution_id')

    with op.batch_alter_table('approval_decisions') as batch_op:
        batch_op.drop_column('notes')

    with op.batch_alter_table('approval_requests') as batch_op:
        batch_op.drop_index('ix_approval_requests_execution_id')
        batch_op.drop_column('risk_assessment_version')
        batch_op.drop_column('policy_version')
        batch_op.drop_column('assigned_reviewer_id')
        batch_op.drop_column('execution_id')

    op.drop_table('outcome_observations')
    op.drop_table('policy_evaluations')
    op.drop_table('deployment_policies')
    op.drop_table('agent_state_transitions')
    op.drop_table('agent_executions')
