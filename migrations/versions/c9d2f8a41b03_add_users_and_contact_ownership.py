"""add users and contact ownership

Revision ID: c9d2f8a41b03
Revises: 6f2eb617807f
Create Date: 2026-08-02 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d2f8a41b03'
down_revision: Union[str, Sequence[str], None] = '6f2eb617807f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.Column('avatar', sa.String(length=255), nullable=True),
        sa.Column('confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Contacts created before authentication existed have no owner and cannot
    # be attributed to anyone, so they are removed before user_id becomes
    # NOT NULL.
    op.execute('DELETE FROM contacts')

    op.add_column('contacts', sa.Column('user_id', sa.Integer(), nullable=False))
    op.create_index(op.f('ix_contacts_user_id'), 'contacts', ['user_id'], unique=False)
    op.create_foreign_key(
        'fk_contacts_user_id_users',
        'contacts',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE',
    )

    # The email is now unique per user instead of globally.
    op.drop_index(op.f('ix_contacts_email'), table_name='contacts')
    op.create_index(op.f('ix_contacts_email'), 'contacts', ['email'], unique=False)
    op.create_unique_constraint('uq_contacts_user_email', 'contacts', ['user_id', 'email'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_contacts_user_email', 'contacts', type_='unique')
    op.drop_index(op.f('ix_contacts_email'), table_name='contacts')
    op.create_index(op.f('ix_contacts_email'), 'contacts', ['email'], unique=True)
    op.drop_constraint('fk_contacts_user_id_users', 'contacts', type_='foreignkey')
    op.drop_index(op.f('ix_contacts_user_id'), table_name='contacts')
    op.drop_column('contacts', 'user_id')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
