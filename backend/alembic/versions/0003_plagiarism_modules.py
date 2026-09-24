"""plagiarism check modules

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('analyses') as b:
        b.add_column(sa.Column('check_modules', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        # "awaiting_confirmation" (21 chars) did not fit the old String(12) on PostgreSQL
        b.alter_column('status', existing_type=sa.String(length=12), type_=sa.String(length=24), existing_nullable=False)
    with op.batch_alter_table('web_page_cache') as b:
        b.add_column(sa.Column('module', sa.String(length=20), nullable=False, server_default='web'))
        b.add_column(sa.Column('language', sa.String(length=10), nullable=True))
        b.add_column(sa.Column('vectors', sa.LargeBinary(), nullable=True))
        b.add_column(sa.Column('vector_backend', sa.String(length=80), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('web_page_cache') as b:
        b.drop_column('vector_backend')
        b.drop_column('vectors')
        b.drop_column('language')
        b.drop_column('module')
    with op.batch_alter_table('analyses') as b:
        b.alter_column('status', existing_type=sa.String(length=24), type_=sa.String(length=12), existing_nullable=False)
        b.drop_column('check_modules')
