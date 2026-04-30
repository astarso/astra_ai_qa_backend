"""initial_tables

Revision ID: 001
Revises:
Create Date: 2026-04-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Index
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import VECTOR

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("ldap_dn", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )

    op.create_table(
        "test_suites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), default={}, nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uq_test_suites_project_name"),
    )

    op.create_table(
        "test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_suites.id"), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("code_path", sa.String(length=512), nullable=True),
        sa.Column("avg_duration_ms", sa.Float(), nullable=True),
    )

    op.create_table(
        "test_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_suites.id"), nullable=False),
        sa.Column("commit_sha", sa.CHAR(length=40), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("priority", sa.SmallInteger(), default=0, nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        Index("ix_test_runs_suite_started", "suite_id", "started_at"),
        Index("ix_test_runs_commit", "commit_sha"),
    )

    op.create_table(
        "test_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_runs.id"), nullable=False),
        sa.Column("test_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_cases.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        Index("ix_test_results_run_status", "run_id", "status"),
        Index("ix_test_results_finished", "finished_at", postgresql_using="brin"),
    )

    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_results.id"), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
    )

    op.create_table(
        "ai_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_results.id"), nullable=False, unique=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("short_cause", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("llm_model", sa.String(length=128), nullable=False),
        sa.Column("prompt_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("error_embedding", VECTOR(768), nullable=True),
        Index("ix_ai_analyses_result", "result_id"),
        Index(
            "ix_ai_analyses_vec",
            "error_embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"error_embedding": "vector_cosine_ops"},
        ),
    )

    op.create_table(
        "defects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), default="open", nullable=False),
        sa.Column("jira_key", sa.String(length=64), nullable=True, unique=True),
    )

    op.create_table(
        "defect_results",
        sa.Column("defect_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("defects.id"), primary_key=True),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_results.id"), primary_key=True),
        Index("ix_defect_results_defect", "defect_id"),
        Index("ix_defect_results_result", "result_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("defect_results")
    op.drop_table("defects")
    op.drop_table("ai_analyses")
    op.drop_table("attachments")
    op.drop_table("test_results")
    op.drop_table("test_runs")
    op.drop_table("test_cases")
    op.drop_table("test_suites")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("roles")
    op.execute("DROP EXTENSION IF EXISTS vector;")
