## 1. Schemas & Data Model

- [x] 1.1 Define Job Spec schema (output schema, constraints, SLA/deadline, max budget, evaluation rubric)
- [x] 1.2 Define Job Contract schema (finalized terms from handshake)
- [x] 1.3 Define Completion Packet schema (deliverable + evidence artifacts)
- [x] 1.4 Define ledger entry schema for holds, releases, refunds, fees

## 2. Job Lifecycle & State Machine

- [x] 2.1 Implement job lifecycle state machine (CREATED → NEGOTIATED → FUNDED → IN_PROGRESS → SUBMITTED → VERIFIED → SETTLED/REFUNDED)
- [x] 2.2 Implement job persistence layer with state transition validation
- [x] 2.3 Add idempotency key handling for state-mutating operations

## 3. Task Intake & Handshake

- [x] 3.1 Implement POST /jobs endpoint to create job from task request and return job_id
- [x] 3.2 Implement handshake endpoints (accept/counteroffer) for doer agent
- [x] 3.3 Enforce no transition to FUNDED until terms are finalized

## 4. Payments & Ledger

- [x] 4.1 Implement payments adapter interface (hold/release/refund) with mocked implementation for v0
- [x] 4.2 Implement double-entry ledger for holds, releases, refunds, and fees
- [x] 4.3 Implement POST /jobs/{job_id}/fund endpoint with hold creation
- [x] 4.4 Ensure settlement is atomic with ledger write and idempotent

## 5. Execution Authorization

- [x] 5.1 Implement start token generation scoped to job_id
- [x] 5.2 Implement token expiration and invalidation on completion/cancellation
- [x] 5.3 Implement POST /jobs/{job_id}/start to issue start token only when FUNDED
- [x] 5.4 Transition job to IN_PROGRESS when doer begins execution

## 6. Completion & Verification

- [x] 6.1 Implement artifact storage for Completion Packet (deliverable + evidence)
- [x] 6.2 Implement POST /jobs/{job_id}/submit for completion packet submission
- [x] 6.3 Implement verification hooks (deterministic: schema validation, constraint checks)
- [x] 6.4 Implement rubric evaluator for open-ended tasks
- [x] 6.5 Implement contract policy application on verification failure (retry, dispute, partial payout, refund)

## 7. Settlement & Callbacks

- [x] 7.1 Implement POST /jobs/{job_id}/settle with atomic release and ledger entries
- [x] 7.2 Implement callback/webhook delivery to requesting agent on VERIFIED/REFUNDED
- [x] 7.3 Add retry with exponential backoff for transient callback failures

## 8. Observability

- [x] 8.1 Add audit logs for all settlement actions and state transitions
- [x] 8.2 Add metrics for completion rate, dispute rate, settlement latency
