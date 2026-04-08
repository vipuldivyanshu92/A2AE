"""Job and handshake API - Tasks 3.1, 3.2, 3.3."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session_factory
from ..metrics import get_metrics
from ..repository import IdempotencyRepository, JobRepository
from ..schemas.job_contract import HandshakeAccept, HandshakeCounteroffer
from ..schemas.job_spec import TaskRequest
from ..state import JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])
SessionLocal = get_session_factory()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_idempotency_key(
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> str:
    if not idempotency_key:
        raise HTTPException(400, "Idempotency-Key header required")
    return idempotency_key


@router.post("")
def create_job(
    req: TaskRequest,
    db: Session = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> dict:
    """
    Task 3.1: POST /jobs - create job from task request and return job_id.
    """
    idem_repo = IdempotencyRepository(db)
    existing = idem_repo.get(idempotency_key)
    if existing and existing.operation == "create_job":
        return existing.response_json

    job_repo = JobRepository(db)
    job_id = str(uuid.uuid4())

    job_spec_json = req.model_dump()
    job_repo.create(
        job_id=job_id,
        requester_id="requester",  # TODO: from auth
        job_spec_json=job_spec_json,
        callback_url=req.callback_url,
    )
    get_metrics().jobs_created += 1

    try:
        idem_repo.set(
            idempotency_key,
            "create_job",
            job_id,
            {"job_id": job_id},
        )
    except Exception:
        db.rollback()
        raise

    return {"job_id": job_id}


@router.post("/{job_id}/handshake/accept")
def handshake_accept(
    job_id: str,
    body: HandshakeAccept,
    db: Session = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> dict:
    """
    Task 3.2: Doer accepts terms. Transitions CREATED -> NEGOTIATED.
    """
    idem_repo = IdempotencyRepository(db)
    op_key = f"{idempotency_key}:accept:{job_id}"
    existing = idem_repo.get(op_key)
    if existing:
        return existing.response_json or {}

    job_repo = JobRepository(db)
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if JobStatus(job.status) != JobStatus.CREATED:
        raise HTTPException(400, f"Job cannot accept in status {job.status}")

    from datetime import datetime
    from ..schemas.job_spec import JobSpec

    spec = JobSpec(**job.job_spec_json)
    contract = {
        "job_id": job_id,
        "job_spec": spec.model_dump(),
        "requester_id": job.requester_id,
        "doer_id": body.doer_id,
        "agreed_amount": spec.max_budget or "0",
        "agreed_deadline": spec.sla_deadline.isoformat() if spec.sla_deadline else None,
        "callback_url": job.callback_url,
        "dispute_policy": "refund",
        "finalized_at": datetime.utcnow().isoformat(),
    }

    job_repo.update_doer(job_id, body.doer_id)
    job_repo.update_contract(job_id, contract)
    job_repo.transition_status(job_id, JobStatus.NEGOTIATED)

    try:
        idem_repo.set(
            op_key, "handshake_accept", job_id, {"status": "negotiated", "job_id": job_id}
        )
    except Exception:
        db.rollback()
        raise

    return {"status": "negotiated", "job_id": job_id}


@router.post("/{job_id}/handshake/counteroffer")
def handshake_counteroffer(
    job_id: str,
    body: HandshakeCounteroffer,
    db: Session = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> dict:
    """
    Task 3.2: Doer proposes counter terms. Transitions CREATED -> NEGOTIATED
    with updated terms. Task 3.3: Job cannot transition to FUNDED until
    terms are finalized (handshake completed).
    """
    idem_repo = IdempotencyRepository(db)
    op_key = f"{idempotency_key}:counter:{job_id}"
    existing = idem_repo.get(op_key)
    if existing:
        return existing.response_json or {}

    job_repo = JobRepository(db)
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if JobStatus(job.status) != JobStatus.CREATED:
        raise HTTPException(400, f"Job cannot counteroffer in status {job.status}")

    from datetime import datetime
    from ..schemas.job_spec import JobSpec

    spec = JobSpec(**job.job_spec_json)
    agreed_amount = body.counter_amount or spec.max_budget or "0"
    agreed_deadline = body.counter_deadline or spec.sla_deadline

    contract = {
        "job_id": job_id,
        "job_spec": spec.model_dump(),
        "requester_id": job.requester_id,
        "doer_id": body.doer_id,
        "agreed_amount": agreed_amount,
        "agreed_deadline": agreed_deadline.isoformat() if agreed_deadline else None,
        "callback_url": job.callback_url,
        "dispute_policy": "refund",
        "finalized_at": datetime.utcnow().isoformat(),
    }

    job_repo.update_doer(job_id, body.doer_id)
    job_repo.update_contract(job_id, contract)
    job_repo.transition_status(job_id, JobStatus.NEGOTIATED)

    try:
        idem_repo.set(
            op_key, "handshake_counter", job_id, {"status": "negotiated", "job_id": job_id}
        )
    except Exception:
        db.rollback()
        raise

    return {"status": "negotiated", "job_id": job_id}


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    """Return job snapshot for dashboards and UI refresh."""
    job_repo = JobRepository(db)
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "requester_id": job.requester_id,
        "doer_id": job.doer_id,
        "callback_url": job.callback_url,
        "hold_id": job.hold_id,
        "job_spec": job.job_spec_json,
        "contract": job.job_contract_json,
    }
