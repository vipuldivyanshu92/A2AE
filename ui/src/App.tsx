import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createJob,
  fetchMetrics,
  fundJob,
  getJob,
  handshakeAccept,
  handshakeCounter,
  refundJob,
  settleJob,
  startJob,
  submitCompletion,
  verifyJob,
  type JobSnapshot,
  type Metrics,
} from "./api";

const STEPS = [
  { id: "create", label: "Create job" },
  { id: "handshake", label: "Doer handshake" },
  { id: "fund", label: "Fund escrow" },
  { id: "start", label: "Start & token" },
  { id: "submit", label: "Submit work" },
  { id: "verify", label: "Verify" },
  { id: "settle", label: "Settle / refund" },
] as const;

type StepId = (typeof STEPS)[number]["id"];

const STATUS_ORDER = [
  "created",
  "negotiated",
  "funded",
  "in_progress",
  "submitted",
  "verified",
  "settled",
  "refunded",
];

function stepFromStatus(status: string): number {
  const i = STATUS_ORDER.indexOf(status);
  if (i < 0) return 0;
  if (status === "refunded") return 6;
  if (status === "settled") return 6;
  if (status === "verified") return 5;
  if (status === "submitted") return 4;
  if (status === "in_progress") return 3;
  if (status === "funded") return 2;
  if (status === "negotiated") return 1;
  return 0;
}

export default function App() {
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<JobSnapshot | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeStep, setActiveStep] = useState<StepId>("create");

  const [taskDescription, setTaskDescription] = useState(
    "Summarize the attached research notes into bullet points."
  );
  const [maxBudget, setMaxBudget] = useState("100");
  const [slaDeadline, setSlaDeadline] = useState("");
  const [callbackUrl, setCallbackUrl] = useState("");

  const [doerId, setDoerId] = useState("doer-agent-1");
  const [handshakeMode, setHandshakeMode] = useState<"accept" | "counter">(
    "accept"
  );
  const [counterAmount, setCounterAmount] = useState("");
  const [counterNotes, setCounterNotes] = useState("");

  const [deliverableJson, setDeliverableJson] = useState(
    '{\n  "result": "Task completed successfully.",\n  "items": ["a", "b"]\n}'
  );
  const [startToken, setStartToken] = useState<string | null>(null);

  const refreshJob = useCallback(async () => {
    if (!jobId.trim()) return;
    setError(null);
    try {
      const j = await getJob(jobId.trim());
      setJob(j);
      setActiveStep(STEPS[Math.min(stepFromStatus(j.status), STEPS.length - 1)].id);
    } catch (e) {
      setJob(null);
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [jobId]);

  const refreshMetrics = useCallback(async () => {
    try {
      setMetrics(await fetchMetrics());
    } catch {
      setMetrics(null);
    }
  }, []);

  useEffect(() => {
    refreshMetrics();
    const t = setInterval(refreshMetrics, 8000);
    return () => clearInterval(t);
  }, [refreshMetrics]);

  useEffect(() => {
    if (!jobId.trim()) {
      setJob(null);
      return;
    }
    refreshJob();
  }, [jobId, refreshJob]);

  const stepIndex = useMemo(
    () => STEPS.findIndex((s) => s.id === activeStep),
    [activeStep]
  );

  async function run<T>(fn: () => Promise<T>, okMsg: string): Promise<T | void> {
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      const out = await fn();
      setSuccess(okMsg);
      await refreshJob();
      await refreshMetrics();
      return out;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <h1>Agentic Escrow</h1>
            <p>Walk through the full agent-to-agent escrow lifecycle</p>
          </div>
          {metrics && (
            <div className="metrics-row">
              <span className="metric">
                Completion <strong>{(metrics.completion_rate * 100).toFixed(0)}%</strong>
              </span>
              <span className="metric">
                Settled <strong>{metrics.jobs_settled}</strong>
              </span>
              <span className="metric">
                Refunded <strong>{metrics.jobs_refunded}</strong>
              </span>
              <span className="metric">
                Verify fails <strong>{metrics.verification_failures}</strong>
              </span>
            </div>
          )}
        </div>
      </header>

      <main className="app-main">
        <nav className="steps-nav" aria-label="Workflow steps">
          <h2>Steps</h2>
          {STEPS.map((s, i) => (
            <button
              key={s.id}
              type="button"
              className={`step-item ${activeStep === s.id ? "active" : ""} ${
                i < stepIndex ? "done" : ""
              }`}
              onClick={() => setActiveStep(s.id)}
            >
              <span className="step-dot" />
              {s.label}
            </button>
          ))}
        </nav>

        <section className="panel">
          <div className="refresh-bar">
            <button type="button" className="ghost" onClick={refreshMetrics}>
              Refresh metrics
            </button>
            {jobId && (
              <button type="button" className="ghost" onClick={refreshJob}>
                Refresh job
              </button>
            )}
          </div>

          {activeStep === "create" && (
            <>
              <h3>Create job</h3>
              <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "-0.5rem" }}>
                POST /jobs — defines the Job Spec (task, budget, optional SLA and callback).
              </p>
              <div className="form-grid">
                <label>
                  Task description
                  <textarea
                    value={taskDescription}
                    onChange={(e) => setTaskDescription(e.target.value)}
                    rows={3}
                  />
                </label>
                <label>
                  Max budget (smallest unit)
                  <input
                    value={maxBudget}
                    onChange={(e) => setMaxBudget(e.target.value)}
                  />
                </label>
                <label>
                  SLA deadline (optional, ISO 8601)
                  <input
                    placeholder="2026-04-01T12:00:00"
                    value={slaDeadline}
                    onChange={(e) => setSlaDeadline(e.target.value)}
                  />
                </label>
                <label>
                  Callback URL (optional)
                  <input
                    placeholder="https://requester.example/hooks/escrow"
                    value={callbackUrl}
                    onChange={(e) => setCallbackUrl(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  className="primary"
                  disabled={loading}
                  onClick={() =>
                    run(async () => {
                      const body: Record<string, unknown> = {
                        task_description: taskDescription,
                        max_budget: maxBudget,
                      };
                      if (slaDeadline.trim()) body.sla_deadline = slaDeadline.trim();
                      if (callbackUrl.trim()) body.callback_url = callbackUrl.trim();
                      const { job_id } = await createJob(body);
                      setJobId(job_id);
                      setHandshakeMode("accept");
                      setStartToken(null);
                      return job_id;
                    }, "Job created")
                  }
                >
                  Create job
                </button>
              </div>
            </>
          )}

          {activeStep === "handshake" && (
            <>
              <h3>Doer handshake</h3>
              <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "-0.5rem" }}>
                Doer accepts terms or sends a counteroffer before funding.
              </p>
              <div className="form-grid">
                <label>
                  Doer ID
                  <input value={doerId} onChange={(e) => setDoerId(e.target.value)} />
                </label>
                <div className="radio-row">
                  <label>
                    <input
                      type="radio"
                      name="hs"
                      checked={handshakeMode === "accept"}
                      onChange={() => setHandshakeMode("accept")}
                    />
                    Accept
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="hs"
                      checked={handshakeMode === "counter"}
                      onChange={() => setHandshakeMode("counter")}
                    />
                    Counteroffer
                  </label>
                </div>
                {handshakeMode === "counter" && (
                  <>
                    <label>
                      Counter amount (optional)
                      <input
                        value={counterAmount}
                        onChange={(e) => setCounterAmount(e.target.value)}
                      />
                    </label>
                    <label>
                      Notes
                      <input value={counterNotes} onChange={(e) => setCounterNotes(e.target.value)} />
                    </label>
                  </>
                )}
                <button
                  type="button"
                  className="primary"
                  disabled={loading || !jobId}
                  onClick={() =>
                    run(async () => {
                      if (handshakeMode === "accept") {
                        await handshakeAccept(jobId, doerId);
                      } else {
                        await handshakeCounter(jobId, {
                          doer_id: doerId,
                          counter_amount: counterAmount || undefined,
                          notes: counterNotes || undefined,
                        });
                      }
                    }, "Handshake complete — status: negotiated")
                  }
                >
                  Submit handshake
                </button>
              </div>
            </>
          )}

          {activeStep === "fund" && (
            <>
              <h3>Fund escrow</h3>
              <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "-0.5rem" }}>
                Holds funds via the payments adapter and moves the job to funded.
              </p>
              <button
                type="button"
                className="primary"
                disabled={loading || !jobId}
                onClick={() => run(() => fundJob(jobId), "Escrow funded")}
              >
                Fund job
              </button>
            </>
          )}

          {activeStep === "start" && (
            <>
              <h3>Start execution</h3>
              <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "-0.5rem" }}>
                Issues a scoped start token and transitions to in progress.
              </p>
              <button
                type="button"
                className="primary"
                disabled={loading || !jobId}
                onClick={() =>
                  run(async () => {
                    const r = await startJob(jobId);
                    setStartToken(r.start_token);
                  }, "Started — token issued")
                }
              >
                Start job
              </button>
              {startToken && (
                <div>
                  <p style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: 0 }}>
                    Start token
                  </p>
                  <div className="token-box">{startToken}</div>
                </div>
              )}
            </>
          )}

          {activeStep === "submit" && (
            <>
              <h3>Submit completion</h3>
              <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "-0.5rem" }}>
                Deliverable as JSON object (maps to API deliverable.content).
              </p>
              <div className="form-grid">
                <label>
                  Deliverable JSON
                  <textarea
                    className="code"
                    value={deliverableJson}
                    onChange={(e) => setDeliverableJson(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  className="primary"
                  disabled={loading || !jobId}
                  onClick={() =>
                    run(async () => {
                      let content: unknown;
                      try {
                        content = JSON.parse(deliverableJson);
                      } catch {
                        throw new Error("Invalid JSON in deliverable");
                      }
                      await submitCompletion(jobId, {
                        deliverable: {
                          content,
                          mime_type: "application/json",
                        },
                        evidence: [],
                      });
                    }, "Completion submitted")
                  }
                >
                  Submit completion
                </button>
              </div>
            </>
          )}

          {activeStep === "verify" && (
            <>
              <h3>Verify</h3>
              <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "-0.5rem" }}>
                Runs deterministic checks (and rubric if configured on the job).
              </p>
              <button
                type="button"
                className="primary"
                disabled={loading || !jobId}
                onClick={() => run(() => verifyJob(jobId), "Verification finished")}
              >
                Run verification
              </button>
            </>
          )}

          {activeStep === "settle" && (
            <>
              <h3>Settle or refund</h3>
              <p style={{ color: "var(--muted)", fontSize: "0.85rem", marginTop: "-0.5rem" }}>
                Settle releases payment to the doer (after verified). Refund returns escrow to the requester path.
              </p>
              <div className="btn-row">
                <button
                  type="button"
                  className="primary"
                  disabled={loading || !jobId}
                  onClick={() => run(() => settleJob(jobId), "Settlement complete")}
                >
                  Settle
                </button>
                <button
                  type="button"
                  className="danger"
                  disabled={loading || !jobId}
                  onClick={() => run(() => refundJob(jobId), "Refund processed")}
                >
                  Refund
                </button>
              </div>
            </>
          )}

          {error && <div className="alert error">{error}</div>}
          {success && <div className="alert success">{success}</div>}
        </section>

        <aside className="side-panel panel">
          <h3>Current job</h3>
          <div className="job-id-row">
            <input
              placeholder="job_id UUID"
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
            />
          </div>
          {job && (
            <>
              <p>
                Status{" "}
                <span className={`status-pill ${job.status}`}>{job.status}</span>
              </p>
              <h3 style={{ marginTop: "1rem" }}>Snapshot</h3>
              <pre className="json">{JSON.stringify(job, null, 2)}</pre>
            </>
          )}
          {!job && jobId && !error && (
            <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>Loading or not found…</p>
          )}
        </aside>
      </main>
    </div>
  );
}
