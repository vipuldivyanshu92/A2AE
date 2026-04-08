"""Job repository with state transition validation - Task 2.2, 2.3."""

from sqlalchemy.orm import Session

from .models import IdempotencyRecord, JobModel
from .state import JobStatus, transition


class JobRepository:
    """Job persistence with state validation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, job_id: str) -> JobModel | None:
        """Get job by id."""
        return self._session.get(JobModel, job_id)

    def create(
        self,
        job_id: str,
        requester_id: str,
        job_spec_json: dict,
        callback_url: str | None = None,
    ) -> JobModel:
        """Create job in CREATED status."""
        job = JobModel(
            job_id=job_id,
            status=JobStatus.CREATED.value,
            requester_id=requester_id,
            job_spec_json=job_spec_json,
            callback_url=callback_url,
        )
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def transition_status(self, job_id: str, to_status: JobStatus) -> JobModel:
        """Transition job to new status with validation and audit log."""
        job = self.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        current = JobStatus(job.status)
        new_status = transition(current, to_status)
        from .models import AuditLogModel
        audit = AuditLogModel(
            job_id=job_id,
            action="state_transition",
            from_status=current.value,
            to_status=new_status.value,
        )
        self._session.add(audit)
        job.status = new_status.value
        self._session.commit()
        self._session.refresh(job)
        return job

    def update_contract(self, job_id: str, contract_json: dict) -> JobModel:
        """Store finalized contract."""
        job = self.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        job.job_contract_json = contract_json
        self._session.commit()
        self._session.refresh(job)
        return job

    def update_doer(self, job_id: str, doer_id: str) -> JobModel:
        """Set doer_id."""
        job = self.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        job.doer_id = doer_id
        self._session.commit()
        self._session.refresh(job)
        return job

    def update_hold_id(self, job_id: str, hold_id: str) -> JobModel:
        """Set hold_id after funding."""
        job = self.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        job.hold_id = hold_id
        self._session.commit()
        self._session.refresh(job)
        return job


class IdempotencyRepository:
    """Idempotency key handling - Task 2.3."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> IdempotencyRecord | None:
        """Get existing idempotency record."""
        return self._session.get(IdempotencyRecord, key)

    def set(
        self,
        key: str,
        operation: str,
        resource_id: str,
        response_json: dict | None = None,
    ) -> IdempotencyRecord:
        """Store idempotency record."""
        rec = IdempotencyRecord(
            idempotency_key=key,
            operation=operation,
            resource_id=resource_id,
            response_json=response_json,
        )
        self._session.add(rec)
        self._session.commit()
        return rec
