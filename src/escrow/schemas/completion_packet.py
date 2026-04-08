"""Completion Packet schema - deliverable + evidence submitted by doer."""

from typing import Any

from pydantic import BaseModel, Field


class EvidenceArtifact(BaseModel):
    """Evidence artifact supporting the deliverable."""

    artifact_id: str = Field(...)
    type: str = Field(..., description="e.g. log, screenshot, test_output")
    content: str | bytes | dict[str, Any] = Field(...)
    mime_type: str | None = Field(None)


class Deliverable(BaseModel):
    """Primary deliverable from the doer."""

    content: str | dict[str, Any] | bytes = Field(...)
    mime_type: str = Field("application/json")


class CompletionPacket(BaseModel):
    """
    Completion Packet - deliverable + evidence stored when doer submits results.
    Task 1.3: Must be stored and job marked SUBMITTED.
    """

    deliverable: Deliverable = Field(...)
    evidence: list[EvidenceArtifact] = Field(default_factory=list)
