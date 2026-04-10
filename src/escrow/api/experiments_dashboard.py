"""Dashboard API: run or simulate agent experiment suites against an escrow base URL."""

from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

router = APIRouter(tags=["experiments"])

OnlyChoice = Literal["1", "2", "3", "4", "5", "all"]


class ExperimentsRunBody(BaseModel):
    """Body for POST /experiments/run."""

    target_base_url: str | None = Field(
        None,
        description="Escrow API origin (e.g. http://127.0.0.1:8000). Omit to use this server's public base URL.",
    )
    only: OnlyChoice = "all"
    instance_label: str = Field("dashboard", max_length=128)
    dry_run: bool = Field(
        False,
        description="If true, return a simulated result payload without calling the target API.",
    )
    doer_ids: list[str] | None = Field(
        None,
        description=(
            "Exactly six escrow doer_id strings when integrating external agents. "
            "Slots 0-2: exp1 strict + exp2 refund + exp3 workers 0-2; "
            "slots 3-5: exp1 loose + exp2 arbitration + exp3 jobs 3-5. "
            "Exp4 uses slot 0 for doer_id when provided."
        ),
    )
    trials: int = Field(
        1,
        ge=1,
        le=50,
        description="Repeat the selected suite; aggregate success/latency across trials.",
    )
    include_llm: bool = Field(
        False,
        description="When true and only is all or 5, run exp5 (OpenAI) if OPENAI_API_KEY is set.",
    )
    llm_trials_per_arm: int = Field(3, ge=1, le=20, description="Trials per arm for exp5.")

    @field_validator("doer_ids")
    @classmethod
    def validate_doer_ids(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if len(v) != 6:
            raise ValueError("doer_ids must contain exactly 6 strings when provided")
        for s in v:
            if not s or len(s) > 256:
                raise ValueError("each doer_id must be 1-256 characters")
        return v


@router.get("/experiments/plan")
def experiments_plan() -> dict[str, Any]:
    """Structured description of experiments (for UI / docs)."""
    from experiments.run_agent_experiments import get_experiment_plan

    return get_experiment_plan()


@router.post("/experiments/run")
def experiments_run(body: ExperimentsRunBody, request: Request) -> dict[str, Any]:
    from experiments.run_agent_experiments import run_experiments, run_experiments_dry_run

    default_base = str(request.base_url).rstrip("/")
    base = (body.target_base_url or default_base).rstrip("/")

    if body.dry_run:
        return run_experiments_dry_run(
            base_url=base,
            instance_label=body.instance_label,
            only=body.only,
            doer_ids=body.doer_ids,
            trials=body.trials,
            include_llm=body.include_llm,
            llm_trials_per_arm=body.llm_trials_per_arm,
        )

    try:
        return run_experiments(
            base=base,
            instance_label=body.instance_label,
            only=body.only,
            doer_ids=body.doer_ids,
            trials=body.trials,
            include_llm=body.include_llm,
            llm_trials_per_arm=body.llm_trials_per_arm,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Target API HTTP error: {e.response.status_code} {e.response.text[:500]}",
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Target API unreachable: {e}") from e
