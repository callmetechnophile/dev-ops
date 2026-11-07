"""predictive_deployment_intelligence

Revision ID: 0004_predictive_intelligence
Revises: 0003_failure_memory
Create Date: 2026-11-07 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0004_predictive_intelligence'
down_revision = '0003_failure_memory'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Extend risk_assessments
    with op.batch_alter_table('risk_assessments') as batch_op:
        batch_op.add_column(sa.Column('repository_id', sa.CHAR(36), sa.ForeignKey('repositories.id', ondelete='SET NULL'), nullable=True))
        batch_op.add_column(sa.Column('environment', sa.String(100), server_default='production', nullable=False))
        batch_op.add_column(sa.Column('risk_category', sa.String(50), server_default='LOW', nullable=False))
        batch_op.add_column(sa.Column('impact_category', sa.String(50), server_default='LOW', nullable=False))
        batch_op.add_column(sa.Column('affected_services', sa.JSON(), server_default='[]', nullable=False))
        batch_op.add_column(sa.Column('feature_snapshot', sa.JSON(), server_default='{}', nullable=False))
        batch_op.add_column(sa.Column('supporting_incident_ids', sa.JSON(), server_default='[]', nullable=False))
        batch_op.add_column(sa.Column('model_version', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('calibration_version', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('explanation', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('assessment_status', sa.String(50), server_default='COMPLETED', nullable=False))
        batch_op.add_column(sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index('ix_risk_assessments_repository_id', ['repository_id'])
        batch_op.create_index('ix_risk_assessments_environment', ['environment'])
        batch_op.create_index('ix_risk_assessments_risk_category', ['risk_category'])

    # 2. Create deployment_outcome_labels
    op.create_table(
        'deployment_outcome_labels',
        sa.Column('id', sa.CHAR(36), primary_key=True),
        sa.Column('tenant_id', sa.CHAR(36), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('deployment_id', sa.CHAR(36), sa.ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('observation_window_minutes', sa.Integer(), server_default='60', nullable=False),
        sa.Column('outcome_label', sa.String(50), nullable=False),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('evidence_references', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('verification_status', sa.String(50), server_default='VERIFIED', nullable=False),
        sa.Column('dataset_version', sa.String(50), server_default='v1.0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('tenant_id', 'deployment_id', name='uq_tenant_deployment_outcome'),
    )
    op.create_index('ix_deployment_outcome_labels_outcome', 'deployment_outcome_labels', ['outcome_label'])
    op.create_index('ix_deployment_outcome_labels_dataset_ver', 'deployment_outcome_labels', ['dataset_version'])
    op.create_index('ix_deployment_outcome_labels_tenant_id', 'deployment_outcome_labels', ['tenant_id'])


def downgrade() -> None:
    op.drop_table('deployment_outcome_labels')

    with op.batch_alter_table('risk_assessments') as batch_op:
        batch_op.drop_index('ix_risk_assessments_risk_category')
        batch_op.drop_index('ix_risk_assessments_environment')
        batch_op.drop_index('ix_risk_assessments_repository_id')
        batch_op.drop_column('assessed_at')
        batch_op.drop_column('assessment_status')
        batch_op.drop_column('explanation')
        batch_op.drop_column('calibration_version')
        batch_op.drop_column('model_version')
        batch_op.drop_column('supporting_incident_ids')
        batch_op.drop_column('feature_snapshot')
        batch_op.drop_column('affected_services')
        batch_op.drop_column('impact_category')
        batch_op.drop_column('risk_category')
        batch_op.drop_column('environment')
        batch_op.drop_column('repository_id')
