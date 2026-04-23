"""drop unused auth/usage tables for personal mode

Revision ID: 003
Revises: 002
Create Date: 2026-04-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These tables were used for multi-user/auth + usage tracking.
    # Personal-local mode does not need them.
    op.drop_table("refresh_tokens")
    op.drop_table("api_keys")
    op.drop_table("usage_logs")


def downgrade() -> None:
    raise RuntimeError("Downgrade is not supported for personal-local mode migration 003.")

