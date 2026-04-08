"""Start endpoint - Tasks 5.3, 5.4."""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session_factory
from ..repository import JobRepository
from ..state import JobStatus
from ..tokens import generate_start_token

router = APIRouter(prefix="/jobs", tags=["jobs"])
SessionLocal = get_session_factory()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{job_id}/start")
def start_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Task 5.3: Issue start token only when FUNDED.
    Task 5.4: Transition to IN_PROGRESS when doer begins execution.
    """
    job_repo = JobRepository(db)
    job = job_repo.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if JobStatus(job.status) != JobStatus.FUNDED:
        raise HTTPException(
            400,
            f"Cannot start: job must be FUNDED (current: {job.status})",
        )

    token, expires_at = generate_start_token(job_id)

    job_repo.transition_status(job_id, JobStatus.IN_PROGRESS)

    return {
        "start_token": token,
        "job_id": job_id,
        "expires_at": expires_at,
    }
