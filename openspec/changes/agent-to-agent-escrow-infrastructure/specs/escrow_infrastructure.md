# Escrow Infrastructure Specification

## Requirements

### Requirement: Structured task intake
#### Scenario: Convert incoming task request into a Job Spec
- **WHEN** a requesting agent submits a task request
- **THEN** the system MUST create a Job Spec with: output schema, constraints, SLA/deadline, max budget, and evaluation rubric (if provided)
- **AND** the system MUST return a unique `job_id`

### Requirement: Doer handshake
#### Scenario: Doer must explicitly accept terms before funding
- **WHEN** a job is created
- **THEN** the system MUST request acceptance (or counteroffer) from the doer agent
- **AND** the job MUST NOT transition to FUNDED until terms are finalized

### Requirement: Funds must be held before execution begins
#### Scenario: Doer cannot start without FUNDED status
- **WHEN** the job is not in FUNDED status
- **THEN** the system MUST NOT issue a start token

### Requirement: Start token is scoped and non-reusable
#### Scenario: Capability token only authorizes one job
- **WHEN** the system issues a start token
- **THEN** the token MUST be scoped to a single `job_id`
- **AND** the token MUST expire (time-based) or be invalidated upon job completion/cancellation

### Requirement: Async execution
#### Scenario: Escrow supports long-running tasks
- **WHEN** a doer begins executing
- **THEN** the job MUST transition to IN_PROGRESS
- **AND** the system SHOULD accept progress events/heartbeats

### Requirement: Completion submission must include evidence
#### Scenario: Doer submits deliverable + evidence
- **WHEN** the doer submits results
- **THEN** the system MUST store the deliverable and associated evidence artifacts as a Completion Packet
- **AND** the system MUST mark the job SUBMITTED

### Requirement: Verification gates settlement
#### Scenario: Only verified jobs are settled
- **WHEN** verification fails
- **THEN** the system MUST NOT release funds to the doer
- **AND** the system MUST apply contract policy (retry, dispute, partial payout, or refund)

### Requirement: Settlement is atomic and auditable
#### Scenario: Release payment exactly once
- **WHEN** a job transitions to SETTLED
- **THEN** the system MUST create ledger entries for release and fees
- **AND** settlement MUST be idempotent (repeated calls do not double-pay)

### Requirement: Requester receives a completion callback
#### Scenario: Callback is retried on transient failures
- **WHEN** a job is VERIFIED (or REFUNDED)
- **THEN** the system MUST notify the requesting agent via callback/webhook
- **AND** the system SHOULD retry delivery with backoff on transient errors
