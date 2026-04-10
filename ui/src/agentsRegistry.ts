/** External agent profiles for escrow protocol integration (browser localStorage). */

export type AgentRole = "doer" | "requester" | "both";

export type ExternalAgent = {
  id: string;
  displayName: string;
  /** Value sent as `doer_id` in handshake — must match what the remote agent uses. */
  escrowDoerId: string;
  role: AgentRole;
  /** Optional: where the agent’s control plane / docs live (informational). */
  baseUrl: string;
  /** Optional: where the requester expects escrow callbacks (informational). */
  webhookUrl: string;
  notes: string;
};

export const AGENTS_STORAGE_KEY = "agentescrow-external-agents-v1";

export const ESCROW_PROTOCOL_REFERENCE = {
  title: "Escrow HTTP protocol (for external agents)",
  description:
    "Your process (OpenClaw, LangGraph, cron, etc.) calls the same REST API as this UI. There is no separate API key; use Idempotency-Key on mutating requests.",
  steps: [
    { method: "POST", path: "/jobs", note: "Create job; save job_id from response." },
    {
      method: "POST",
      path: "/jobs/{job_id}/handshake/accept",
      note: "Body: { doer_id: \"<your escrowDoerId>\", dispute_policy?: \"refund\"|\"arbitration\" }",
    },
    { method: "POST", path: "/jobs/{job_id}/fund", note: "Requester funds (mock adapter in v0)." },
    { method: "POST", path: "/jobs/{job_id}/start", note: "Returns start_token; job → in_progress." },
    {
      method: "POST",
      path: "/jobs/{job_id}/submit",
      note: "Completion packet: deliverable + evidence; Idempotency-Key required.",
    },
    { method: "POST", path: "/jobs/{job_id}/verify", note: "Deterministic / rubric checks." },
    { method: "POST", path: "/jobs/{job_id}/settle", note: "After verified." },
  ],
} as const;

function safeParse(raw: string | null): ExternalAgent[] {
  if (!raw) return [];
  try {
    const v = JSON.parse(raw) as unknown;
    if (!Array.isArray(v)) return [];
    return v.filter(isAgent);
  } catch {
    return [];
  }
}

function isAgent(x: unknown): x is ExternalAgent {
  if (typeof x !== "object" || x === null) return false;
  const o = x as Record<string, unknown>;
  return (
    typeof o.id === "string" &&
    typeof o.displayName === "string" &&
    typeof o.escrowDoerId === "string" &&
    typeof o.role === "string" &&
    ["doer", "requester", "both"].includes(o.role)
  );
}

export function loadAgents(): ExternalAgent[] {
  return safeParse(localStorage.getItem(AGENTS_STORAGE_KEY));
}

export function saveAgents(agents: ExternalAgent[]): void {
  localStorage.setItem(AGENTS_STORAGE_KEY, JSON.stringify(agents));
}

export function newAgentId(): string {
  return crypto.randomUUID();
}

export function agentsWithDoerRole(agents: ExternalAgent[]): ExternalAgent[] {
  return agents.filter((a) => a.role === "doer" || a.role === "both");
}

export function defaultAgent(): ExternalAgent {
  return {
    id: newAgentId(),
    displayName: "",
    escrowDoerId: "",
    role: "doer",
    baseUrl: "",
    webhookUrl: "",
    notes: "",
  };
}
