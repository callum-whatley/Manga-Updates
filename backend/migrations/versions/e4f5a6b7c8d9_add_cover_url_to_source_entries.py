"""Add cover_url to manga_source_entries

Revision ID: e4f5a6b7c8d9
Revises: 662ed7000db1
Create Date: 2026-06-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4f5a6b7c8d9'
down_revision = '662ed7000db1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('manga_source_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cover_url', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('manga_source_entries', schema=None) as batch_op:
        batch_op.drop_column('cover_url')
