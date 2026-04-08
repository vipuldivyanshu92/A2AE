"""Job Spec schema - defines task intake structure per spec requirement."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OutputSchema(BaseModel):
    """Output schema definition for expected deliverable structure."""

    type: str = Field(..., description="Schema type, e.g. json-schema")
    definition: dict[str, Any] = Field(default_factory=dict)


class Constraint(BaseModel):
    """Constraint on the task execution or deliverable."""

    type: str = Field(..., description="Constraint type identifier")
    value: Any = Field(..., description="Constraint value")


class EvaluationRubric(BaseModel):
    """Evaluation rubric for open-ended task verification."""

    criteria: list[dict[str, Any]] = Field(default_factory=list)
    required_score: float | None = Field(None, ge=0, le=1)
    dispute_policy: str | None = Field(None, description="retry | arbitration | refund")


class JobSpec(BaseModel):
    """
    Job Spec - structure created from incoming task request.
    Task 1.1: output schema, constraints, SLA/deadline, max budget, evaluation rubric.
    """

    output_schema: OutputSchema | None = Field(None)
    constraints: list[Constraint] = Field(default_factory=list)
    sla_deadline: datetime | None = Field(None)
    max_budget: str | None = Field(None, description="Max payment amount in smallest unit")
    evaluation_rubric: EvaluationRubric | None = Field(None)
    task_description: str | None = Field(None)


class TaskRequest(BaseModel):
    """Incoming task request from requesting agent."""

    output_schema: OutputSchema | None = None
    constraints: list[Constraint] = Field(default_factory=list)
    sla_deadline: datetime | None = None
    max_budget: str | None = None
    evaluation_rubric: EvaluationRubric | None = None
    task_description: str | None = None
    callback_url: str | None = Field(None)
