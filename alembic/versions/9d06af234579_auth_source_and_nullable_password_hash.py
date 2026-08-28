"""auth_source and nullable password_hash

Revision ID: 9d06af234579
Revises: c4e8138aa39f
Create Date: 2026-08-28 14:01:09.114338

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d06af234579'
down_revision: Union[str, Sequence[str], None] = 'c4e8138aa39f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite can't ALTER a column's nullability (or, safely, add a NOT NULL
    # column with no default) without table recreation — batch mode handles
    # that automatically instead of a plain ALTER TABLE.
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('auth_source', sa.String(length=10), nullable=False, server_default='local')
        )
        batch_op.alter_column('password_hash', existing_type=sa.VARCHAR(length=255), nullable=True)

    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('auth_source', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('password_hash', existing_type=sa.VARCHAR(length=255), nullable=False)
        batch_op.drop_column('auth_source')
