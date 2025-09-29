"""
Planner: create plans and plan_steps tables

Revision ID: 0011_planner
Revises: 0010_device_events_stats
Create Date: 2025-09-18 18:55:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0011_planner'
down_revision = '0010_device_events_stats'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='queued', index=True),
        sa.Column('meta', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('finished_at', sa.Integer(), nullable=False, server_default='0'),
    )
    # Some SQLite backends ignore index=True inside Column; add explicit indexes
    op.create_index('ix_plans_title', 'plans', ['title'], unique=False)
    op.create_index('ix_plans_user_id', 'plans', ['user_id'], unique=False)
    op.create_index('ix_plans_status', 'plans', ['status'], unique=False)

    op.create_table(
        'plan_steps',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plan_id', sa.Integer(), nullable=False, index=True),
        sa.Column('idx', sa.Integer(), nullable=False, server_default='0', index=True),
        sa.Column('type', sa.String(length=64), nullable=False, server_default='task', index=True),
        sa.Column('payload', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='queued', index=True),
        sa.Column('result', sa.Text(), nullable=False, server_default=''),
        sa.Column('error', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('finished_at', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_plan_steps_plan_id', 'plan_steps', ['plan_id'], unique=False)
    op.create_index('ix_plan_steps_idx', 'plan_steps', ['idx'], unique=False)
    op.create_index('ix_plan_steps_type', 'plan_steps', ['type'], unique=False)
    op.create_index('ix_plan_steps_status', 'plan_steps', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_plan_steps_status', table_name='plan_steps')
    op.drop_index('ix_plan_steps_type', table_name='plan_steps')
    op.drop_index('ix_plan_steps_idx', table_name='plan_steps')
    op.drop_index('ix_plan_steps_plan_id', table_name='plan_steps')
    op.drop_table('plan_steps')

    op.drop_index('ix_plans_status', table_name='plans')
    op.drop_index('ix_plans_user_id', table_name='plans')
    op.drop_index('ix_plans_title', table_name='plans')
    op.drop_table('plans')
