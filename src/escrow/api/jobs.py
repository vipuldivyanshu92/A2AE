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
        requester_id=(req.requester_id or "requester").strip() or "requester",
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
    dp = body.dispute_policy if body.dispute_policy in ("retry", "arbitration", "refund") else "refund"
    contract = {
        "job_id": job_id,
        "job_spec": spec.model_dump(),
        "requester_id": job.requester_id,
        "doer_id": body.doer_id,
        "agreed_amount": spec.max_budget or "0",
        "agreed_deadline": spec.sla_deadline.isoformat() if spec.sla_deadline else None,
        "callback_url": job.callback_url,
        "dispute_policy": dp,
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
    dp = body.dispute_policy if body.dispute_policy in ("retry", "arbitration", "refund") else "refund"

    contract = {
        "job_id": job_id,
        "job_spec": spec.model_dump(),
        "requester_id": job.requester_id,
        "doer_id": body.doer_id,
        "agreed_amount": agreed_amount,
        "agreed_deadline": agreed_deadline.isoformat() if agreed_deadline else None,
        "callback_url": job.callback_url,
        "dispute_policy": dp,
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


@router.get("")
def list_jobs(
    status: str | None = None,
    requester_id: str | None = None,
    doer_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    """List recent jobs for the live dashboard. Filterable by status / agent.

    Each row returns just enough to render a feed row; clients fetch
    `/jobs/{id}` or `/jobs/{id}/trace` for full detail.
    """
    from sqlalchemy import select
    from ..models import JobModel

    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    q = select(JobModel)
    if status:
        q = q.where(JobModel.status == status)
    if requester_id:
        q = q.where(JobModel.requester_id == requester_id)
    if doer_id:
        q = q.where(JobModel.doer_id == doer_id)
    q = q.order_by(JobModel.updated_at.desc()).offset(offset).limit(limit)

    rows = db.execute(q).scalars().all()
    return {
        "limit": limit,
        "offset": offset,
        "count": len(rows),
        "jobs": [
            {
                "job_id": r.job_id,
                "status": r.status,
                "requester_id": r.requester_id,
                "doer_id": r.doer_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "task_description": (r.job_spec_json or {}).get("task_description"),
                "max_budget": (r.job_spec_json or {}).get("max_budget"),
                "dispute_policy": (r.job_contract_json or {}).get("dispute_policy")
                if r.job_contract_json
                else None,
            }
            for r in rows
        ],
    }


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
