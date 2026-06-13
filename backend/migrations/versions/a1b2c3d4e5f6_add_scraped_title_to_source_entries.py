"""Add scraped_title to manga_source_entries

Revision ID: a1b2c3d4e5f6
Revises: f5g6h7i8j9k0
Create Date: 2026-06-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f5g6h7i8j9k0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('manga_source_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scraped_title', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('manga_source_entries', schema=None) as batch_op:
        batch_op.drop_column('scraped_title')
