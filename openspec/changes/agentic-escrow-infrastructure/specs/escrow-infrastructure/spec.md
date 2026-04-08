# Escrow Infrastructure Specification

## ADDED Requirements

### Requirement: Structured task intake
The system SHALL convert incoming task requests into a Job Spec and return a unique job identifier.

#### Scenario: Convert incoming task request into a Job Spec
- **WHEN** a requesting agent submits a task request
- **THEN** the system MUST create a Job Spec with: output schema, constraints, SLA/deadline, max budget, and evaluation rubric (if provided)
- **AND** the system MUST return a unique `job_id`

### Requirement: Doer handshake
The system SHALL require explicit acceptance or counteroffer from the doer before allowing funding.

#### Scenario: Doer must explicitly accept terms before funding
- **WHEN** a job is created
- **THEN** the system MUST request acceptance (or counteroffer) from the doer agent
- **AND** the job MUST NOT transition to FUNDED until terms are finalized

### Requirement: Funds must be held before execution begins
The system SHALL NOT issue a start token until the job is funded.

#### Scenario: Doer cannot start without FUNDED status
- **WHEN** the job is not in FUNDED status
- **THEN** the system MUST NOT issue a start token

### Requirement: Start token is scoped and non-reusable
The system SHALL issue capability tokens scoped to a single job and invalidate them on completion or cancellation.

#### Scenario: Capability token only authorizes one job
- **WHEN** the system issues a start token
- **THEN** the token MUST be scoped to a single `job_id`
- **AND** the token MUST expire or be invalidated upon completion/cancellation

### Requirement: Async execution
The system SHALL support long-running tasks with progress tracking.

#### Scenario: Escrow supports long-running tasks
- **WHEN** a doer begins executing
- **THEN** the job MUST transition to IN_PROGRESS
- **AND** the system SHOULD accept progress events/heartbeats

### Requirement: Completion submission must include evidence
The system SHALL store deliverable and evidence as a Completion Packet upon submission.

#### Scenario: Doer submits deliverable + evidence
- **WHEN** the doer submits results
- **THEN** the system MUST store deliverable + evidence as a Completion Packet
- **AND** the system MUST mark the job SUBMITTED

### Requirement: Verification gates settlement
The system SHALL NOT release funds to the doer unless verification passes.

#### Scenario: Only verified jobs are settled
- **WHEN** verification fails
- **THEN** the system MUST NOT release funds to the doer
- **AND** the system MUST apply contract policy (retry, dispute, partial payout, or refund)

### Requirement: Settlement is atomic and auditable
The system SHALL create ledger entries for settlement and ensure idempotent release.

#### Scenario: Release payment exactly once
- **WHEN** a job transitions to SETTLED
- **THEN** the system MUST create ledger entries for release and fees
- **AND** settlement MUST be idempotent (repeated calls do not double-pay)

### Requirement: Requester receives a completion callback
The system SHALL notify the requesting agent on job completion or refund with retry on transient failures.

#### Scenario: Callback is retried on transient failures
- **WHEN** a job is VERIFIED (or REFUNDED)
- **THEN** the system MUST notify the requesting agent via callback/webhook
- **AND** the system SHOULD retry delivery with backoff on transient errors
