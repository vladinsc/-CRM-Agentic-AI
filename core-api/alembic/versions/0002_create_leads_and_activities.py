"""create leads and agent_activities tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'leads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('company', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('deal_value', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('currency', sa.String(10), nullable=False, server_default='EUR'),
        sa.Column('last_activity_description', sa.Text(), nullable=True),
        sa.Column('intent_score', sa.Integer(), nullable=True),
        sa.Column('last_researched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('signals', JSONB(), nullable=False, server_default='[]'),
        sa.Column('assigned_to', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='new'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_leads_id', 'leads', ['id'])
    op.create_index('ix_leads_assigned_to', 'leads', ['assigned_to'])

    op.create_table(
        'agent_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('leads.id'), nullable=False),
        sa.Column('lead_name', sa.String(), nullable=False),
        sa.Column('agent_name', sa.String(), nullable=False),
        sa.Column('action_type', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('payload', JSONB(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(), nullable=False, server_default='completed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_activities_id', 'agent_activities', ['id'])
    op.create_index('ix_agent_activities_lead_id', 'agent_activities', ['lead_id'])


def downgrade():
    op.drop_index('ix_agent_activities_lead_id', table_name='agent_activities')
    op.drop_index('ix_agent_activities_id', table_name='agent_activities')
    op.drop_table('agent_activities')

    op.drop_index('ix_leads_assigned_to', table_name='leads')
    op.drop_index('ix_leads_id', table_name='leads')
    op.drop_table('leads')
