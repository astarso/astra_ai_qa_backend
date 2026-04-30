"""All SQLAlchemy entity models (11 tables)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

import sqlalchemy
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    JSON,
    Boolean,
    CHAR,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, registry

from app.models.base import Base


_extra_registry = registry()


_defect_results_table = sqlalchemy.Table(
    "defect_results",
    _extra_registry.metadata,
    sqlalchemy.Column("defect_id", sqlalchemy.Uuid, ForeignKey("defects.id"), primary_key=True),
    sqlalchemy.Column("result_id", sqlalchemy.Uuid, ForeignKey("test_results.id"), primary_key=True),
    Index("ix_defect_results_defect", "defect_id"),
    Index("ix_defect_results_result", "result_id"),
)


class DefectResult:
    __table__ = _defect_results_table
    __mapper_args__ = {"primary_key": (_defect_results_table.c.defect_id, _defect_results_table.c.result_id)}

    defect_id: Mapped[UUID]
    result_id: Mapped[UUID]


_extra_registry.map_declaratively(DefectResult)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    ldap_dn: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    role: Mapped["Role"] = relationship(back_populates="users")
    owned_projects: Mapped[list["Project"]] = relationship(
        back_populates="owner", foreign_keys="Project.owner_id"
    )


class Project(Base):
    __tablename__ = "projects"

    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    owner: Mapped["User"] = relationship(back_populates="owned_projects", foreign_keys=[owner_id])
    test_suites: Mapped[list["TestSuite"]] = relationship(back_populates="project")


class TestSuite(Base):
    __tablename__ = "test_suites"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped["Project"] = relationship(back_populates="test_suites")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="suite")
    test_runs: Mapped[list["TestRun"]] = relationship(back_populates="suite")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="suite")


class Schedule(Base):
    __tablename__ = "schedules"

    suite_id: Mapped[UUID] = mapped_column(ForeignKey("test_suites.id"))
    name: Mapped[str] = mapped_column(String(255))
    cron_expression: Mapped[str] = mapped_column(String(128))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    triggered_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    suite: Mapped["TestSuite"] = relationship(back_populates="schedules")


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[UUID] = mapped_column(sqlalchemy.Uuid, primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(128))
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="requirement")


class TestCase(Base):
    __tablename__ = "test_cases"

    suite_id: Mapped[UUID] = mapped_column(ForeignKey("test_suites.id"))
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64))
    code_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    avg_duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    requirement_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("requirements.id"), nullable=True)

    suite: Mapped["TestSuite"] = relationship(back_populates="test_cases")
    results: Mapped[list["TestResult"]] = relationship(back_populates="test_case")
    requirement: Mapped[Optional["Requirement"]] = relationship(back_populates="test_cases")


class TestRun(Base):
    __tablename__ = "test_runs"
    __table_args__ = (
        Index("ix_test_runs_suite_started", "suite_id", "started_at"),
        Index("ix_test_runs_commit", "commit_sha"),
    )

    suite_id: Mapped[UUID] = mapped_column(ForeignKey("test_suites.id"))
    commit_sha: Mapped[str] = mapped_column(CHAR(40))
    branch: Mapped[str] = mapped_column(String(255))
    triggered_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    priority: Mapped[int] = mapped_column(SmallInteger, default=0)
    environment: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    suite: Mapped["TestSuite"] = relationship(back_populates="test_runs")
    results: Mapped[list["TestResult"]] = relationship(back_populates="run")
    triggerer: Mapped["User"] = relationship(foreign_keys=[triggered_by])


class TestResult(Base):
    __tablename__ = "test_results"
    __table_args__ = (
        Index("ix_test_results_run_status", "run_id", "status"),
        Index("ix_test_results_finished", "finished_at", postgresql_using="brin"),
    )

    run_id: Mapped[UUID] = mapped_column(ForeignKey("test_runs.id"))
    test_case_id: Mapped[UUID] = mapped_column(ForeignKey("test_cases.id"))
    status: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    run: Mapped["TestRun"] = relationship(back_populates="results")
    test_case: Mapped["TestCase"] = relationship(back_populates="results")
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="result")
    ai_analysis: Mapped[Optional["AIAnalysis"]] = relationship(back_populates="result")


class Attachment(Base):
    __tablename__ = "attachments"

    result_id: Mapped[UUID] = mapped_column(ForeignKey("test_results.id"))
    file_path: Mapped[str] = mapped_column(String(1024))
    mime_type: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(Integer)

    result: Mapped["TestResult"] = relationship(back_populates="attachments")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    __table_args__ = (
        Index("ix_ai_analyses_result", "result_id"),
        Index(
            "ix_ai_analyses_vec",
            "error_embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"error_embedding": "vector_cosine_ops"},
        ),
    )

    result_id: Mapped[UUID] = mapped_column(ForeignKey("test_results.id"), unique=True)
    category: Mapped[str] = mapped_column(String(64))
    probability: Mapped[float] = mapped_column(Float)
    short_cause: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str] = mapped_column(Text)
    llm_model: Mapped[str] = mapped_column(String(128))
    prompt_hash: Mapped[str] = mapped_column(CHAR(64))
    error_embedding: Mapped[Optional[list[float]]] = mapped_column(VECTOR(768), nullable=True)

    result: Mapped["TestResult"] = relationship(back_populates="ai_analysis")


class Defect(Base):
    __tablename__ = "defects"

    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(32), default="open")
    jira_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
