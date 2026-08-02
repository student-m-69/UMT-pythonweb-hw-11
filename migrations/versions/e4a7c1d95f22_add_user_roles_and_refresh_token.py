"""add user roles and refresh token

Revision ID: e4a7c1d95f22
Revises: c9d2f8a41b03
Create Date: 2026-08-02 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4a7c1d95f22'
down_revision: Union[str, Sequence[str], None] = 'c9d2f8a41b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

role_enum = sa.Enum('user', 'admin', name='role')


def upgrade() -> None:
    """Upgrade schema."""
    role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'users',
        sa.Column('role', role_enum, nullable=False, server_default='user'),
    )
    op.add_column('users', sa.Column('refresh_token', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'refresh_token')
    op.drop_column('users', 'role')
    role_enum.drop(op.get_bind(), checkfirst=True)
