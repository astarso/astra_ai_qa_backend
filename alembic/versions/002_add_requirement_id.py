"""add_requirement_id

Revision ID: 002
Revises: 001
Create Date: 2026-04-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
    )

    op.add_column(
        "test_cases",
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("requirements.id"), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("test_cases", "requirement_id")
    op.drop_table("requirements")