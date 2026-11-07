"""failure_memory_engine

Revision ID: 0003_failure_memory
Revises: 0002_github_ingestion
Create Date: 2026-11-07 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0003_failure_memory'
down_revision = '0002_github_ingestion'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Extend incidents table
    with op.batch_alter_table('incidents') as batch_op:
        batch_op.add_column(sa.Column('incident_key', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('incident_type', sa.String(100), server_default='UNKNOWN_FAILURE', nullable=False))
        batch_op.add_column(sa.Column('environment', sa.String(100), server_default='production', nullable=False))
        batch_op.add_column(sa.Column('primary_service_id', sa.CHAR(36), sa.ForeignKey('services.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('repository_id', sa.CHAR(36), sa.ForeignKey('repositories.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('first_observed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('last_observed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.alter_column('service_id', existing_type=sa.CHAR(36), nullable=True)
        batch_op.create_index('ix_incidents_incident_key', ['incident_key'])
        batch_op.create_index('ix_incidents_incident_type', ['incident_type'])
        batch_op.create_index('ix_incidents_environment', ['environment'])
        batch_op.create_index('ix_incidents_primary_service_id', ['primary_service_id'])
        batch_op.create_index('ix_incidents_repository_id', ['repository_id'])
        batch_op.create_index('ix_incidents_first_observed_at', ['first_observed_at'])
        batch_op.create_index('ix_incidents_last_observed_at', ['last_observed_at'])

    # 2. Create incident_events table
    op.create_table(
        'incident_events',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('incident_id', sa.CHAR(36), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_id', sa.CHAR(36), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_type', sa.String(50), server_default='correlated', nullable=False),
        sa.Column('relevance', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('incident_id', 'event_id', name='uq_incident_event'),
    )
    op.create_index('ix_incident_events_incident_id', 'incident_events', ['incident_id'])
    op.create_index('ix_incident_events_event_id', 'incident_events', ['event_id'])
    op.create_index('ix_incident_events_tenant_id', 'incident_events', ['tenant_id'])

    # 3. Create failure_classifications table
    op.create_table(
        'failure_classifications',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('incident_id', sa.CHAR(36), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('subcategory', sa.String(100), nullable=False),
        sa.Column('classification_method', sa.String(50), server_default='DETERMINISTIC_RULE', nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('classifier_version', sa.String(50), server_default='1.0.0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_failure_classifications_incident_id', 'failure_classifications', ['incident_id'])
    op.create_index('ix_failure_classifications_category', 'failure_classifications', ['category'])
    op.create_index('ix_failure_classifications_tenant_id', 'failure_classifications', ['tenant_id'])

    # 4. Extend root_cause_hypotheses
    with op.batch_alter_table('root_cause_hypotheses') as batch_op:
        batch_op.add_column(sa.Column('hypothesis', sa.Text(), server_default='', nullable=False))
        batch_op.add_column(sa.Column('explanation', sa.Text(), server_default='', nullable=False))
        batch_op.add_column(sa.Column('evidence_event_ids', sa.JSON(), server_default='[]', nullable=False))
        batch_op.add_column(sa.Column('confidence_level', sa.String(50), server_default='MEDIUM', nullable=False))
        batch_op.add_column(sa.Column('generated_by', sa.String(100), server_default='DETERMINISTIC_RULE_V1', nullable=False))

    # 5. Extend confirmed_root_causes
    with op.batch_alter_table('confirmed_root_causes') as batch_op:
        batch_op.add_column(sa.Column('hypothesis_id', sa.CHAR(36), sa.ForeignKey('root_cause_hypotheses.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('confirmed_by', sa.String(255), server_default='authorized_engineer', nullable=False))
        batch_op.add_column(sa.Column('confirmation_notes', sa.Text(), server_default='', nullable=False))
        batch_op.create_index('ix_confirmed_root_causes_hypothesis_id', ['hypothesis_id'])

    # 6. Extend remediation_actions
    with op.batch_alter_table('remediation_actions') as batch_op:
        batch_op.add_column(sa.Column('proposed_by', sa.String(255), server_default='SYSTEM', nullable=False))
        batch_op.add_column(sa.Column('approved_by', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('outcome', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('effectiveness', sa.String(50), nullable=True))

    # 7. Create operational_lessons table
    op.create_table(
        'operational_lessons',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('incident_id', sa.CHAR(36), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('lesson', sa.Text(), nullable=False),
        sa.Column('verified_root_cause_id', sa.CHAR(36), sa.ForeignKey('confirmed_root_causes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('remediation_action_id', sa.CHAR(36), sa.ForeignKey('remediation_actions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('applicability_conditions', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('verification_status', sa.String(50), server_default='VERIFIED', nullable=False),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_operational_lessons_incident_id', 'operational_lessons', ['incident_id'])
    op.create_index('ix_operational_lessons_verified_root_cause_id', 'operational_lessons', ['verified_root_cause_id'])
    op.create_index('ix_operational_lessons_tenant_id', 'operational_lessons', ['tenant_id'])


def downgrade() -> None:
    op.drop_table('operational_lessons')

    with op.batch_alter_table('remediation_actions') as batch_op:
        batch_op.drop_column('effectiveness')
        batch_op.drop_column('outcome')
        batch_op.drop_column('approved_by')
        batch_op.drop_column('proposed_by')

    with op.batch_alter_table('confirmed_root_causes') as batch_op:
        batch_op.drop_index('ix_confirmed_root_causes_hypothesis_id')
        batch_op.drop_column('confirmation_notes')
        batch_op.drop_column('confirmed_by')
        batch_op.drop_column('hypothesis_id')

    with op.batch_alter_table('root_cause_hypotheses') as batch_op:
        batch_op.drop_column('generated_by')
        batch_op.drop_column('confidence_level')
        batch_op.drop_column('evidence_event_ids')
        batch_op.drop_column('explanation')
        batch_op.drop_column('hypothesis')

    op.drop_table('failure_classifications')
    op.drop_table('incident_events')

    with op.batch_alter_table('incidents') as batch_op:
        batch_op.drop_index('ix_incidents_last_observed_at')
        batch_op.drop_index('ix_incidents_first_observed_at')
        batch_op.drop_index('ix_incidents_repository_id')
        batch_op.drop_index('ix_incidents_primary_service_id')
        batch_op.drop_index('ix_incidents_environment')
        batch_op.drop_index('ix_incidents_incident_type')
        batch_op.drop_index('ix_incidents_incident_key')
        batch_op.drop_column('last_observed_at')
        batch_op.drop_column('first_observed_at')
        batch_op.drop_column('repository_id')
        batch_op.drop_column('primary_service_id')
        batch_op.drop_column('environment')
        batch_op.drop_column('incident_type')
        batch_op.drop_column('description')
        batch_op.drop_column('incident_key')
