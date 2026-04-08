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
