# Design: Agent-to-Agent Escrow Infrastructure

## System overview
The escrow service is a middleware layer between a **requesting agent** and a **doer agent**. It enforces an explicit lifecycle:

`CREATED → NEGOTIATED → FUNDED → IN_PROGRESS → SUBMITTED → VERIFIED → SETTLED` (or `REFUNDED`)

## Components
1. **Escrow API / Gateway**
   - Accepts task requests and exposes job status APIs.
   - Issues idempotency keys and job IDs.

2. **Contract & Handshake Service**
   - Sends Job Spec to doer agent.
   - Records acceptance/counteroffer and final Job Contract.

3. **Payments Adapter**
   - Collects funds (authorize or prefund).
   - Creates escrow holds and releases/refunds.
   - Abstracts rail-specific semantics.

4. **Ledger Service (Double-entry)**
   - Records holds, releases, refunds, and fees.
   - Guarantees no double-spend / no double-pay via atomic state transitions.

5. **Verification Service**
   - Deterministic checks: schema validation, tests, constraint checks.
   - Rubric evaluation: evaluator agent / LLM judge with guardrails.
   - Produces a Verification Report.

6. **Eventing & Callbacks**
   - Webhooks/callbacks to the requesting agent (and optionally the doer).
   - Supports retries and at-least-once delivery semantics.

## Trust boundary
- Escrow is a **trusted coordinator** with authority to release funds.
- Doer and requester are untrusted by default.
- Every job produces an immutable audit trail (contract + ledger + evidence + decision).

## Key APIs (illustrative)
- `POST /jobs` → create job from task request
- `POST /jobs/{job_id}/handshake` → accept/counteroffer (doer)
- `POST /jobs/{job_id}/fund` → fund escrow (requester)
- `POST /jobs/{job_id}/start` → issue start token to doer (escrow)
- `POST /jobs/{job_id}/submit` → completion packet upload (doer)
- `POST /jobs/{job_id}/verify` → run verification (escrow)
- `POST /jobs/{job_id}/settle` → release payment (escrow)

## Verification strategy
- Prefer deterministic checks whenever possible.
- For open-ended tasks, require:
  - explicit rubric
  - required evidence artifacts
  - dispute policy (retry/arbitration)

## Failure modes & handling
- **Timeouts**: if `IN_PROGRESS` exceeds SLA → auto-fail → refund or dispute.
- **Partial completion**: support partial payout if contract defines milestones.
- **Disputes**: escrow can route to arbitration (human or automated).

## Security notes
- Use capability tokens for “start” authorization.
- Require idempotency keys for all state-mutating endpoints.
- Log all admin and settlement actions.
