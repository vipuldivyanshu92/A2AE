"""FastAPI dependencies."""

from collections.abc import Generator

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_engine, get_session_factory
from .repository import IdempotencyRepository, JobRepository

_Session = get_session_factory()


def get_db() -> Generator[Session, None, None]:
    """Database session dependency."""
    session = _Session()
    try:
        yield session
    finally:
        session.close()


def get_job_repo(db: Session = None) -> JobRepository:
    """Job repository dependency - inject via request state in routers."""
    raise NotImplementedError("Use db: Session and JobRepository(db)")


def require_idempotency_key(
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> str:
    """Require Idempotency-Key header for state-mutating operations."""
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required for this operation",
        )
    return idempotency_key
