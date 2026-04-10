const BASE = import.meta.env.VITE_API_BASE ?? "";

function idemKey(): string {
  return crypto.randomUUID();
}

async function apiFetch(
  path: string,
  init: RequestInit & { idempotency?: boolean } = {}
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.idempotency !== false && init.method && init.method !== "GET") {
    headers.set("Idempotency-Key", idemKey());
  }
  if (
    init.body &&
    typeof init.body === "string" &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${BASE}${path}`, { ...init, headers });
}

export type JobSnapshot = {
  job_id: string;
  status: string;
  requester_id: string;
  doer_id: string | null;
  callback_url: string | null;
  hold_id: string | null;
  job_spec: Record<string, unknown>;
  contract: Record<string, unknown> | null;
};

export type Metrics = {
  completion_rate: number;
  dispute_rate: number;
  settlement_latency_avg_ms: number;
  jobs_settled: number;
  jobs_refunded: number;
  jobs_disputed: number;
  verification_failures: number;
};

export async function getJob(jobId: string): Promise<JobSnapshot> {
  const r = await apiFetch(`/jobs/${jobId}`, { method: "GET" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function createJob(body: Record<string, unknown>) {
  const r = await apiFetch("/jobs", {
    method: "POST",
    body: JSON.stringify(body),
    idempotency: true,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ job_id: string }>;
}

export async function handshakeAccept(jobId: string, doerId: string) {
  const r = await apiFetch(`/jobs/${jobId}/handshake/accept`, {
    method: "POST",
    body: JSON.stringify({ doer_id: doerId }),
    idempotency: true,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function handshakeCounter(
  jobId: string,
  body: {
    doer_id: string;
    counter_amount?: string;
    counter_deadline?: string;
    notes?: string;
  }
) {
  const r = await apiFetch(`/jobs/${jobId}/handshake/counteroffer`, {
    method: "POST",
    body: JSON.stringify(body),
    idempotency: true,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fundJob(jobId: string) {
  const r = await apiFetch(`/jobs/${jobId}/fund`, {
    method: "POST",
    idempotency: true,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function startJob(jobId: string) {
  const r = await apiFetch(`/jobs/${jobId}/start`, {
    method: "POST",
    idempotency: false,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{
    start_token: string;
    job_id: string;
    expires_at: number;
  }>;
}

export async function submitCompletion(jobId: string, packet: unknown) {
  const r = await apiFetch(`/jobs/${jobId}/submit`, {
    method: "POST",
    body: JSON.stringify(packet),
    idempotency: true,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function verifyJob(jobId: string) {
  const r = await apiFetch(`/jobs/${jobId}/verify`, {
    method: "POST",
    idempotency: false,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function settleJob(jobId: string) {
  const r = await apiFetch(`/jobs/${jobId}/settle`, {
    method: "POST",
    idempotency: true,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function refundJob(jobId: string) {
  const r = await apiFetch(`/jobs/${jobId}/refund`, {
    method: "POST",
    idempotency: true,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchMetrics(): Promise<Metrics> {
  const r = await apiFetch("/metrics", { method: "GET" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type ExperimentPlanArm = {
  name?: string;
  agents?: number;
  expected_verify?: boolean;
  expected_action?: string;
  note?: string;
};

export type ExperimentPlanEntry = {
  id: string;
  title: string;
  summary: string;
  arms: ExperimentPlanArm[];
  pipeline: string[];
  metrics?: string[];
};

export type ExperimentPlan = {
  version: number;
  agent_count_per_wave: number;
  doer_id_slotting?: Record<string, string>;
  experiments: ExperimentPlanEntry[];
};

export async function fetchExperimentPlan(): Promise<ExperimentPlan> {
  const r = await apiFetch("/experiments/plan", { method: "GET" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type ExperimentsRunBody = {
  target_base_url?: string | null;
  only: "1" | "2" | "3" | "4" | "5" | "all";
  instance_label: string;
  dry_run: boolean;
  /** Exactly six `doer_id` strings for external agents (optional). */
  doer_ids?: string[];
  trials?: number;
  include_llm?: boolean;
  llm_trials_per_arm?: number;
};

export type FlowResultRow = {
  experiment: string;
  arm: string;
  agent_id: string;
  job_id: string | null;
  ok: boolean;
  verify_passed: boolean | null;
  verify_action: string | null;
  settled: boolean;
  error: string | null;
  elapsed_s: number;
};

export type Exp3Summary = {
  sequential_wall_s: number;
  parallel_wall_s: number;
  sequential_success_rate: number;
  parallel_success_rate: number;
  speedup: number | null;
  sequential_results: FlowResultRow[];
  parallel_results: FlowResultRow[];
};

export type TrialResultEntry = {
  trial_index: number;
  wall_s: number;
  experiments: Record<string, unknown>;
};

export type ExperimentsAggregate = Record<string, number | string | null | undefined>;

export type ExperimentsRunResponse = {
  api_base: string;
  instance_label: string;
  simulated: boolean;
  doer_ids?: string[] | null;
  trials?: number;
  include_llm?: boolean;
  llm_trials_per_arm?: number;
  trial_results?: TrialResultEntry[];
  aggregate?: ExperimentsAggregate | null;
  experiments: Record<string, unknown>;
};

export async function runExperiments(
  body: ExperimentsRunBody
): Promise<ExperimentsRunResponse> {
  const payload: Record<string, unknown> = {
    only: body.only,
    instance_label: body.instance_label,
    dry_run: body.dry_run,
    trials: body.trials ?? 1,
    include_llm: body.include_llm ?? false,
    llm_trials_per_arm: body.llm_trials_per_arm ?? 3,
  };
  if (body.target_base_url?.trim()) {
    payload.target_base_url = body.target_base_url.trim().replace(/\/$/, "");
  }
  if (body.doer_ids && body.doer_ids.length === 6) {
    payload.doer_ids = body.doer_ids;
  }
  const r = await apiFetch("/experiments/run", {
    method: "POST",
    body: JSON.stringify(payload),
    idempotency: true,
  });
  if (!r.ok) {
    const t = await r.text();
    let msg = t;
    try {
      const j = JSON.parse(t) as { detail?: unknown };
      const d = j.detail;
      if (typeof d === "string") msg = d;
      else if (Array.isArray(d)) msg = d.map((x) => JSON.stringify(x)).join("; ");
    } catch {
      /* use raw body */
    }
    throw new Error(msg);
  }
  return r.json();
}
