# Agentic Escrow Infrastructure (OpenSpec / OPSX Document)

> This file is a single-file version of the OpenSpec change artifacts (proposal + specs + design + tasks).

---

## Proposal

### Summary
Build an escrow middleware layer that enables **safe, programmable, agent-to-agent transactions** for long-running tasks. The escrow service coordinates task intake, doer handshake, payment hold, execution authorization, completion verification, and settlement.

### Problem
Autonomous agents increasingly **delegate work to other agents** (research, browsing, code generation, data processing). For long-running tasks (>1s) and uncertain outcomes:
- The **requesting agent** risks paying without receiving a correct result.
- The **doer agent** risks doing work without getting paid.

Without an escrow primitive, agent marketplaces and delegation networks are fragile and hard to automate.

### Goals
- Make agent work safe to buy/sell using **funded escrow + verifiable completion**.
- Support **async/long-running tasks** with progress events, timeouts, and retries.
- Provide an explicit **contract + audit trail** (terms, ledger, evidence, verification report).
- Callback-first integration so agents can operate without humans.

### Non-goals (v0)
- Not a full global payments stack; v0 can run on mocked rails or a single integration.
- Not solving generalized truth for every open-ended task.
- Not providing underwriting/credit.

### Success metrics
- No double-pay / missed refund events (state + ledger correctness).
- Improved completion rate vs direct peer-to-peer.
- Low dispute rate and fast dispute resolution.

---

## Design

### Lifecycle
`CREATED → NEGOTIATED → FUNDED → IN_PROGRESS → SUBMITTED → VERIFIED → SETTLED` (or `REFUNDED`)

### Components
1. Escrow API / Gateway
2. Contract & Handshake Service
3. Payments Adapter
4. Double-entry Ledger
5. Verification Service
6. Eventing & Callbacks

### Verification strategy
- Prefer deterministic checks (schema validation, tests).
- For open-ended tasks: explicit rubric + required evidence + dispute policy.

### Failure handling
- Timeouts: `IN_PROGRESS` beyond SLA → refund or dispute.
- Partial completion: milestone-based payouts if defined in contract.
- Disputes: arbitration (human or automated).

### Security
- Capability “start token” scoped to `job_id`.
- Idempotency keys for all state-mutating endpoints.
- Audit logs for all settlement actions.

---

## Specs

### Requirement: Structured task intake
**Scenario: Convert incoming task request into a Job Spec**
- **WHEN** a requesting agent submits a task request
- **THEN** the system MUST create a Job Spec with: output schema, constraints, SLA/deadline, max budget, evaluation rubric (if provided)
- **AND** the system MUST return a unique `job_id`

### Requirement: Doer handshake
**Scenario: Doer must explicitly accept terms before funding**
- **WHEN** a job is created
- **THEN** the system MUST request acceptance (or counteroffer) from the doer agent
- **AND** the job MUST NOT transition to FUNDED until terms are finalized

### Requirement: Funds must be held before execution begins
**Scenario: Doer cannot start without FUNDED status**
- **WHEN** the job is not in FUNDED status
- **THEN** the system MUST NOT issue a start token

### Requirement: Start token is scoped and non-reusable
**Scenario: Capability token only authorizes one job**
- **WHEN** the system issues a start token
- **THEN** the token MUST be scoped to a single `job_id`
- **AND** the token MUST expire or be invalidated upon completion/cancellation

### Requirement: Async execution
**Scenario: Escrow supports long-running tasks**
- **WHEN** a doer begins executing
- **THEN** the job MUST transition to IN_PROGRESS
- **AND** the system SHOULD accept progress events/heartbeats

### Requirement: Completion submission must include evidence
**Scenario: Doer submits deliverable + evidence**
- **WHEN** the doer submits results
- **THEN** the system MUST store deliverable + evidence as a Completion Packet
- **AND** the system MUST mark the job SUBMITTED

### Requirement: Verification gates settlement
**Scenario: Only verified jobs are settled**
- **WHEN** verification fails
- **THEN** the system MUST NOT release funds to the doer
- **AND** the system MUST apply contract policy (retry, dispute, partial payout, or refund)

### Requirement: Settlement is atomic and auditable
**Scenario: Release payment exactly once**
- **WHEN** a job transitions to SETTLED
- **THEN** the system MUST create ledger entries for release and fees
- **AND** settlement MUST be idempotent (repeated calls do not double-pay)

### Requirement: Requester receives a completion callback
**Scenario: Callback is retried on transient failures**
- **WHEN** a job is VERIFIED (or REFUNDED)
- **THEN** the system MUST notify the requesting agent via callback/webhook
- **AND** the system SHOULD retry delivery with backoff on transient errors

---

## Tasks

- Define Job Spec + Job Contract schemas
- Implement job lifecycle state machine + persistence
- Implement handshake endpoints (accept/counteroffer)
- Implement payments adapter (hold/release/refund) + double-entry ledger
- Implement completion packet submission + artifact storage
- Implement verification hooks (deterministic + rubric evaluator)
- Implement callbacks/webhooks + retries
- Add audit logs + metrics
