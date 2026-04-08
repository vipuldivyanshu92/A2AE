## Context

Autonomous agents delegate work to other agents for research, browsing, code generation, and data processing. For long-running tasks (>1s) and uncertain outcomes, both parties face risk: the requester may pay without receiving a correct result; the doer may work without getting paid. No escrow primitive exists for agent-to-agent transactions.

**Current state**: No middleware; agents either transact peer-to-peer (risky) or require human-in-loop approval (not scalable).

**Constraints**: Callback-first integration so agents operate without humans. v0 can run on mocked payment rails or a single integration.

**Stakeholders**: Agent marketplace operators, delegation network builders, requesting agents, doer agents.

## Goals / Non-Goals

**Goals:**
- Make agent work safe to buy/sell using funded escrow + verifiable completion
- Support async/long-running tasks with progress events, timeouts, and retries
- Provide an explicit contract + audit trail (terms, ledger, evidence, verification report)
- Ensure no double-pay / missed refund events (state + ledger correctness)

**Non-Goals (v0):**
- Full global payments stack; v0 uses mocked rails or a single integration
- Generalized truth for every open-ended task
- Underwriting/credit

## Decisions

### 1. Lifecycle state machine
**Decision**: `CREATED → NEGOTIATED → FUNDED → IN_PROGRESS → SUBMITTED → VERIFIED → SETTLED` (or `REFUNDED`).

**Rationale**: Explicit states prevent ambiguous transitions. No execution until FUNDED; no settlement until VERIFIED.

**Alternatives considered**: Fewer states (e.g., merging NEGOTIATED and FUNDED) were rejected—handshake and funding are distinct operations with different parties.

### 2. Capability tokens for start authorization
**Decision**: Issue a scoped "start token" per `job_id` that authorizes exactly one execution. Token expires or invalidates on completion/cancellation.

**Rationale**: Prevents replay and cross-job misuse.

**Alternatives considered**: API keys or role-based auth—less fine-grained and harder to revoke per job.

### 3. Idempotency keys for all state-mutating endpoints
**Decision**: Require idempotency key on POST/PUT endpoints (create, fund, submit, settle).

**Rationale**: Safe retries; prevents double-fund, double-submit, double-settle.

**Alternatives considered**: Request deduplication by content—less reliable under network failures.

### 4. Verification strategy: deterministic first, rubric for open-ended
**Decision**: Prefer schema validation, tests, constraint checks. For open-ended tasks: require explicit rubric, required evidence, and dispute policy.

**Rationale**: Deterministic checks are unambiguous; rubric + evidence provide auditability for subjective tasks.

**Alternatives considered**: LLM-only verification—too expensive and non-deterministic for v0.

### 5. Double-entry ledger for settlement
**Decision**: Record holds, releases, refunds, and fees in a double-entry ledger. Settlement is atomic with ledger write.

**Rationale**: Guarantees no double-spend; audit trail for reconciliation and disputes.

**Alternatives considered**: Single-entry—harder to reconcile and verify correctness.

### 6. Callback retries with backoff
**Decision**: Notify requester via webhook on VERIFIED/REFUNDED. Retry with exponential backoff on transient errors.

**Rationale**: At-least-once delivery for async agents; transient failures should not block settlement.

**Alternatives considered**: Fire-and-forget—would fail silently too often.

## Risks / Trade-offs

- **[Risk] Verification ambiguity for open-ended tasks** → Mitigation: Require rubric, evidence, dispute policy; arbitration path for unresolved cases
- **[Risk] Payment rail failures during hold/release** → Mitigation: Adapter abstraction; idempotent settlement; audit logs for manual reconciliation
- **[Risk] Timeout/SLA abuse** → Mitigation: Contract-defined SLA; auto-refund or dispute on breach
- **[Risk] Partial completion disputes** → Mitigation: Support milestone-based payouts in contract; dispute resolution policy

## Migration Plan

1. Deploy escrow services behind feature flag
2. Integrate with mocked payment adapter for testing
3. Onboard pilot agents (requesters + doers)
4. Enable production payment rail when ready
5. Rollback: Disable new job creation; drain in-flight jobs to completion or refund

## Open Questions

- Exact rubric evaluator interface (agent vs. LLM vs. hybrid)
- Dispute arbitration flow (human-only vs. automated escalation)
