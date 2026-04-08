"""Audit logging - Task 8.1."""

from sqlalchemy.orm import Session

from .models import AuditLogModel


class AuditLogger:
    """Log settlement actions and state transitions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def log(
        self,
        job_id: str,
        action: str,
        from_status: str | None = None,
        to_status: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Record audit entry."""
        entry = AuditLogModel(
            job_id=job_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            details=details or {},
        )
        self._session.add(entry)
        self._session.commit()
