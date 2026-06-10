"""Add search_url_template to scraper_sites

Revision ID: 662ed7000db1
Revises: d2e3f4a5b6c7
Create Date: 2026-06-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '662ed7000db1'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('scraper_sites', schema=None) as batch_op:
        batch_op.add_column(sa.Column('search_url_template', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('scraper_sites', schema=None) as batch_op:
        batch_op.drop_column('search_url_template')
