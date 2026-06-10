"""Add chapter_image_selector to scraper_sites

Revision ID: d2e3f4a5b6c7
Revises: c81a67917f65
Create Date: 2026-03-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2e3f4a5b6c7'
down_revision = 'c81a67917f65'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('scraper_sites', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chapter_image_selector', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('scraper_sites', schema=None) as batch_op:
        batch_op.drop_column('chapter_image_selector')
