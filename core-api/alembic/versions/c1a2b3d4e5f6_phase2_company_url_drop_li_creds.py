"""phase2: add leads.company_url, drop linkedin_credentials

Revision ID: c1a2b3d4e5f6
Revises: bb812b415554
Create Date: 2026-06-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c1a2b3d4e5f6'
down_revision = 'bb812b415554'
branch_labels = None
depends_on = None


def upgrade():
    # Phase 2: company website URL captured by the extension, fetched during research.
    op.add_column('leads', sa.Column('company_url', sa.String(), nullable=True))

    # Obsolete: server-side LinkedIn cookie storage replaced by the browser extension.
    op.drop_table('linkedin_credentials')


def downgrade():
    op.create_table(
        'linkedin_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('cookies_json', sa.Text(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.drop_column('leads', 'company_url')
