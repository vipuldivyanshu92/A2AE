"""Verification service - Tasks 6.3, 6.4, 6.5."""

from typing import Any

from .schemas.completion_packet import CompletionPacket
from .schemas.job_spec import JobSpec


def verify_deterministic(
    completion: CompletionPacket,
    job_spec: JobSpec,
) -> tuple[bool, str | None]:
    """
    Task 6.3: Deterministic verification - schema validation, constraint checks.
    Returns (passed, error_message).
    """
    if job_spec.output_schema:
        # Simple schema check: if output_schema has "type", validate deliverable structure
        definition = job_spec.output_schema.definition
        if definition:
            content = completion.deliverable.content
            if isinstance(content, dict):
                # Check required keys if specified
                required = definition.get("required", [])
                for key in required:
                    if key not in content:
                        return False, f"Missing required field: {key}"
            elif isinstance(content, str):
                pass  # No structural validation for string
        # Add more schema validation as needed
    for constraint in job_spec.constraints or []:
        # Placeholder: actual constraint evaluation would be task-specific
        pass
    return True, None


def verify_rubric(
    completion: CompletionPacket,
    rubric: dict,
) -> tuple[bool, float]:
    """
    Task 6.4: Rubric evaluator for open-ended tasks.
    Returns (passed, score). v0: placeholder that accepts if evidence exists.
    """
    required_score = rubric.get("required_score")
    if required_score is None:
        return True, 1.0
    # v0: simple pass if we have deliverable + some evidence
    has_evidence = len(completion.evidence) > 0 or completion.deliverable.content
    score = 1.0 if has_evidence else 0.0
    passed = score >= required_score
    return passed, score


def apply_contract_policy(
    policy: str,
) -> str:
    """
    Task 6.5: Contract policy on verification failure.
    Returns next action: retry | dispute | refund | partial_payout
    """
    return policy if policy in ("retry", "arbitration", "refund") else "refund"
