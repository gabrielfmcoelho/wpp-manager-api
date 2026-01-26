"""add users tables

Revision ID: a1b2c3d4e5f6
Revises: 702841108473
Create Date: 2026-01-25 02:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '702841108473'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Define the enum type (will be created if not exists)
devicerole_enum = postgresql.ENUM('OWNER', 'ADMIN', 'VIEWER', name='devicerole', create_type=False)


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('logto_sub', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('picture', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('logto_sub')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=False)

    # Create device role enum with IF NOT EXISTS (PostgreSQL specific)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'devicerole') THEN
                CREATE TYPE devicerole AS ENUM ('OWNER', 'ADMIN', 'VIEWER');
            END IF;
        END $$;
    """)

    # Create user_devices table using raw SQL to avoid SQLAlchemy trying to create the enum
    op.execute("""
        CREATE TABLE user_devices (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            role devicerole NOT NULL DEFAULT 'VIEWER',
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
    """)
    op.create_index('ix_user_devices_user_device', 'user_devices', ['user_id', 'device_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_user_devices_user_device', table_name='user_devices')
    op.drop_table('user_devices')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS devicerole;")
