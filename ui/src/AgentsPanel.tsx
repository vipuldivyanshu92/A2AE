import { useMemo, useState } from "react";
import {
  ESCROW_PROTOCOL_REFERENCE,
  agentsWithDoerRole,
  defaultAgent,
  type AgentRole,
  type ExternalAgent,
} from "./agentsRegistry";
import { useAgents } from "./AgentsContext";

const API_BASE_HINT =
  import.meta.env.VITE_API_BASE && String(import.meta.env.VITE_API_BASE).length > 0
    ? String(import.meta.env.VITE_API_BASE).replace(/\/$/, "")
    : "(same origin — e.g. http://127.0.0.1:8000 or your deployed API)";

export function AgentsPanel({ onOpenExperiments }: { onOpenExperiments?: () => void }) {
  const { agents, upsertAgent, removeAgent } = useAgents();
  const [draft, setDraft] = useState<ExternalAgent>(() => defaultAgent());
  const [editingId, setEditingId] = useState<string | null>(null);

  const doerPool = useMemo(() => agentsWithDoerRole(agents), [agents]);

  function startEdit(a: ExternalAgent) {
    setDraft({ ...a });
    setEditingId(a.id);
  }

  function cancelEdit() {
    setDraft(defaultAgent());
    setEditingId(null);
  }

  function submitDraft(e: React.FormEvent) {
    e.preventDefault();
    const id = draft.escrowDoerId.trim();
    if (!draft.displayName.trim() || !id) return;
    upsertAgent({
      ...draft,
      displayName: draft.displayName.trim(),
      escrowDoerId: id,
      baseUrl: draft.baseUrl.trim(),
      webhookUrl: draft.webhookUrl.trim(),
      notes: draft.notes.trim(),
    });
    cancelEdit();
  }

  return (
    <div className="agents-page">
      <section className="panel agents-intro">
        <h2>External agents</h2>
        <p className="exp-lead">
          Register <strong>doer</strong> or <strong>requester</strong> identities that live outside this
          browser (OpenClaw, cloud workers, teammate scripts). The escrow API identifies a doer by the
          string you send as <code>doer_id</code> at handshake — use the same value in your agent code.
        </p>
        <ul className="agents-bullets">
          <li>
            <strong>Workflow</strong> tab: pick a registered doer for handshake or type a custom ID.
          </li>
          <li>
            <strong>Experiments</strong>: enable &quot;Use registered doers&quot; and select six agents
            (slots map to strict / loose / policy arms — see Experiments tab).
          </li>
        </ul>
        {onOpenExperiments && (
          <button type="button" className="ghost" onClick={onOpenExperiments}>
            Go to Experiments
          </button>
        )}
      </section>

      <div className="agents-grid">
        <section className="panel">
          <h3>{editingId ? "Edit agent" : "Add agent"}</h3>
          <form className="form-grid" onSubmit={submitDraft}>
            <label>
              Display name
              <input
                required
                value={draft.displayName}
                onChange={(e) => setDraft((d) => ({ ...d, displayName: e.target.value }))}
                placeholder="e.g. OpenClaw worker eu-1"
              />
            </label>
            <label>
              Escrow <code>doer_id</code>
              <input
                required
                value={draft.escrowDoerId}
                onChange={(e) => setDraft((d) => ({ ...d, escrowDoerId: e.target.value }))}
                placeholder="e.g. openclaw-eu-1"
              />
            </label>
            <label>
              Role
              <select
                value={draft.role}
                onChange={(e) => setDraft((d) => ({ ...d, role: e.target.value as AgentRole }))}
              >
                <option value="doer">Doer (handshake + work)</option>
                <option value="requester">Requester (creates jobs / callbacks)</option>
                <option value="both">Both</option>
              </select>
            </label>
            <label>
              Agent base URL (optional)
              <input
                value={draft.baseUrl}
                onChange={(e) => setDraft((d) => ({ ...d, baseUrl: e.target.value }))}
                placeholder="https://runner.example.com"
              />
            </label>
            <label>
              Callback / webhook URL (optional)
              <input
                value={draft.webhookUrl}
                onChange={(e) => setDraft((d) => ({ ...d, webhookUrl: e.target.value }))}
                placeholder="Paste into Create job → Callback URL"
              />
            </label>
            <label>
              Notes
              <textarea
                rows={2}
                value={draft.notes}
                onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))}
              />
            </label>
            <div className="btn-row">
              <button type="submit" className="primary">
                {editingId ? "Save changes" : "Add agent"}
              </button>
              {editingId && (
                <button type="button" className="ghost" onClick={cancelEdit}>
                  Cancel
                </button>
              )}
            </div>
          </form>
        </section>

        <section className="panel">
          <h3>Registered ({agents.length})</h3>
          {agents.length === 0 && (
            <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>No agents yet.</p>
          )}
          <ul className="agents-list">
            {agents.map((a) => (
              <li key={a.id} className="agents-card">
                <div className="agents-card-head">
                  <strong>{a.displayName}</strong>
                  <span className="agents-role">{a.role}</span>
                </div>
                <div className="mono sm">
                  doer_id: <code>{a.escrowDoerId}</code>
                </div>
                {a.baseUrl && (
                  <div className="mono sm">
                    base: {a.baseUrl}
                  </div>
                )}
                {a.webhookUrl && (
                  <div className="mono sm">
                    webhook: {a.webhookUrl}
                  </div>
                )}
                {a.notes && <p className="agents-notes">{a.notes}</p>}
                <div className="btn-row">
                  <button type="button" className="ghost" onClick={() => startEdit(a)}>
                    Edit
                  </button>
                  <button type="button" className="danger" onClick={() => removeAgent(a.id)}>
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <p className="agents-pool-meta">
            Doer-capable agents for experiments: <strong>{doerPool.length}</strong> (need 6 to run with
            registered IDs).
          </p>
        </section>
      </div>

      <section className="panel agents-protocol">
        <h3>{ESCROW_PROTOCOL_REFERENCE.title}</h3>
        <p className="exp-lead">{ESCROW_PROTOCOL_REFERENCE.description}</p>
        <p className="mono sm" style={{ marginBottom: "0.75rem" }}>
          Base URL hint: {API_BASE_HINT}
        </p>
        <ol className="agents-protocol-steps">
          {ESCROW_PROTOCOL_REFERENCE.steps.map((s) => (
            <li key={s.path}>
              <code>
                {s.method} {s.path}
              </code>
              <span>{s.note}</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
