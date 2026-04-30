"""SQLAlchemy models for job persistence - Task 2.2."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base for all models."""

    pass


class JobModel(Base):
    """Job persistence model."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False)
    doer_id: Mapped[str] = mapped_column(String(128), nullable=True)
    job_spec_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    job_contract_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    hold_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    callback_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class IdempotencyRecord(Base):
    """Idempotency key tracking - Task 2.3."""

    __tablename__ = "idempotency_records"

    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompletionPacketModel(Base):
    """Completion packet storage - Task 6.1."""

    __tablename__ = "completion_packets"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    deliverable_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLogModel(Base):
    """Audit log for settlement and state transitions - Task 8.1."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentModel(Base):
    """
    Public agent registry — any agent (Alice, Bob, OpenClaw worker, …) can
    list itself here so peers can discover it and see its track record.
    """

    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="both")
    endpoint_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class LedgerEntryModel(Base):
    """Ledger entry persistence - Task 4.2."""

    __tablename__ = "ledger_entries"

    entry_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), default="default")
    debit_account: Mapped[str] = mapped_column(String(128), nullable=False)
    credit_account: Mapped[str] = mapped_column(String(128), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
