"""Add is_removed to manga_source_entries

Revision ID: f5g6h7i8j9k0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5g6h7i8j9k0'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('manga_source_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_removed', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('manga_source_entries', schema=None) as batch_op:
        batch_op.drop_column('is_removed')
