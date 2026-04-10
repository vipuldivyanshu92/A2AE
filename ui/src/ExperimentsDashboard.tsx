import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchExperimentPlan,
  runExperiments,
  type ExperimentPlan,
  type ExperimentsRunResponse,
  type FlowResultRow,
  type Exp3Summary,
} from "./api";
import { agentsWithDoerRole } from "./agentsRegistry";
import { useAgents } from "./AgentsContext";

const SLOT_HINTS = [
  "Slots 1–3: exp1 strict · exp2 refund · exp3 jobs 1–3",
  "Slots 4–6: exp1 loose · exp2 arbitration · exp3 jobs 4–6",
];

function isFlowRow(x: unknown): x is FlowResultRow {
  return (
    typeof x === "object" &&
    x !== null &&
    "agent_id" in x &&
    "arm" in x &&
    "ok" in x
  );
}

function isExp3(x: unknown): x is Exp3Summary {
  return (
    typeof x === "object" &&
    x !== null &&
    "sequential_wall_s" in x &&
    "parallel_wall_s" in x
  );
}

export function ExperimentsDashboard({
  onOpenAgents,
}: {
  onOpenAgents?: () => void;
} = {}) {
  const { agents } = useAgents();
  const doerPool = useMemo(() => agentsWithDoerRole(agents), [agents]);

  const [plan, setPlan] = useState<ExperimentPlan | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);

  const [targetBase, setTargetBase] = useState("");
  const [instanceLabel, setInstanceLabel] = useState("dashboard-ui");
  const [only, setOnly] = useState<"all" | "1" | "2" | "3" | "4" | "5">("all");
  const [trials, setTrials] = useState(1);
  const [includeLlm, setIncludeLlm] = useState(false);
  const [llmTrialsPerArm, setLlmTrialsPerArm] = useState(3);
  const [dryRun, setDryRun] = useState(false);
  const [useRegisteredDoers, setUseRegisteredDoers] = useState(false);
  const [slotDoerIds, setSlotDoerIds] = useState<string[]>(["", "", "", "", "", ""]);

  const [loading, setLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<ExperimentsRunResponse | null>(null);

  const loadPlan = useCallback(async () => {
    setPlanError(null);
    try {
      setPlan(await fetchExperimentPlan());
    } catch (e) {
      setPlan(null);
      setPlanError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  function autofillSlotsFromPool() {
    if (doerPool.length === 0) return;
    const next = slotDoerIds.slice();
    for (let i = 0; i < 6; i++) {
      next[i] = doerPool[i % doerPool.length]!.escrowDoerId;
    }
    setSlotDoerIds(next);
  }

  async function onRun() {
    setRunError(null);
    setResult(null);
    if (useRegisteredDoers) {
      const missing = slotDoerIds.some((s) => !s.trim());
      if (missing) {
        setRunError("Select a doer_id for all six slots, or turn off “Use registered doers”.");
        return;
      }
    }
    setLoading(true);
    try {
      const out = await runExperiments({
        target_base_url: targetBase.trim() || null,
        only,
        instance_label: instanceLabel.trim() || "dashboard-ui",
        dry_run: dryRun,
        doer_ids: useRegisteredDoers ? slotDoerIds.map((s) => s.trim()) : undefined,
        trials,
        include_llm: includeLlm,
        llm_trials_per_arm: llmTrialsPerArm,
      });
      setResult(out);
    } catch (e) {
      setRunError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const exp1 = result?.experiments?.exp1_verification_strictness;
  const exp2 = result?.experiments?.exp2_dispute_policy;
  const exp3 = result?.experiments?.exp3_coordination_latency;
  const exp4 = result?.experiments?.exp4_failure_recovery;
  const exp5 = result?.experiments?.exp5_llm_memory_ab;

  const rows1 = Array.isArray(exp1) ? exp1.filter(isFlowRow) : [];
  const rows2 = Array.isArray(exp2) ? exp2.filter(isFlowRow) : [];
  const sum3 = isExp3(exp3) ? exp3 : null;
  const e4 =
    exp4 && typeof exp4 === "object" ? (exp4 as Record<string, unknown>) : null;
  const e5 =
    exp5 && typeof exp5 === "object" ? (exp5 as Record<string, unknown>) : null;

  const passCount = (rows: FlowResultRow[]) =>
    rows.filter((r) => r.ok).length;

  return (
    <div className="exp-page">
      <div className="exp-hero panel">
        <h2>Experiment lab</h2>
        <p className="exp-lead">
          Run protocol suites <strong>1–3</strong>, <strong>4</strong> (verify fail → refund), and optional{" "}
          <strong>5</strong> (real OpenAI memory A/B). Use <strong>Trials</strong> for repeated runs and
          aggregate stats. <strong>Simulate</strong> = dry run. Default API target is this server.
        </p>
        <div className="exp-controls">
          <label>
            Target API base (optional)
            <input
              placeholder="Leave empty to use this server"
              value={targetBase}
              onChange={(e) => setTargetBase(e.target.value)}
            />
          </label>
          <label>
            Instance label (doer_id prefix)
            <input value={instanceLabel} onChange={(e) => setInstanceLabel(e.target.value)} />
          </label>
          <label>
            Suite
            <select value={only} onChange={(e) => setOnly(e.target.value as typeof only)}>
              <option value="all">All (1 + 2 + 3 + 4 + 5*)</option>
              <option value="1">1 — Verification strictness</option>
              <option value="2">2 — Dispute policy</option>
              <option value="3">3 — Sequential vs parallel</option>
              <option value="4">4 — Failure recovery (refund)</option>
              <option value="5">5 — LLM memory A vs B</option>
            </select>
          </label>
          <label>
            Trials (repeat suite)
            <input
              type="number"
              min={1}
              max={50}
              value={trials}
              onChange={(e) => setTrials(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
            />
          </label>
          <label>
            LLM trials / arm (exp5)
            <input
              type="number"
              min={1}
              max={20}
              value={llmTrialsPerArm}
              onChange={(e) =>
                setLlmTrialsPerArm(Math.max(1, Math.min(20, Number(e.target.value) || 3)))
              }
            />
          </label>
          <label className="exp-check">
            <input
              type="checkbox"
              checked={includeLlm}
              onChange={(e) => setIncludeLlm(e.target.checked)}
            />
            Include LLM exp5 (needs <code>OPENAI_API_KEY</code> on server)
          </label>
          <label className="exp-check">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
            />
            Simulate only (dry run, no jobs created)
          </label>
          <label className="exp-check">
            <input
              type="checkbox"
              checked={useRegisteredDoers}
              onChange={(e) => {
                const on = e.target.checked;
                setUseRegisteredDoers(on);
                if (on && doerPool.length > 0) {
                  setSlotDoerIds(
                    Array.from(
                      { length: 6 },
                      (_, i) => doerPool[i % doerPool.length]!.escrowDoerId
                    )
                  );
                }
              }}
            />
            Use registered external <code>doer_id</code>s (six slots)
          </label>
          {useRegisteredDoers && (
            <div className="exp-slots panel-inner">
              <p className="exp-slots-hint">{SLOT_HINTS.join(" · ")}</p>
              {doerPool.length === 0 && (
                <p className="alert error" style={{ marginTop: 0 }}>
                  No doer-capable agents yet.{" "}
                  {onOpenAgents ? (
                    <button type="button" className="ghost" onClick={onOpenAgents}>
                      Open Agents
                    </button>
                  ) : (
                    "Add agents in the Agents tab."
                  )}
                </p>
              )}
              <div className="exp-slots-grid">
                {slotDoerIds.map((val, idx) => (
                  <label key={idx}>
                    Slot {idx + 1}
                    <select
                      value={val}
                      onChange={(e) => {
                        const next = [...slotDoerIds];
                        next[idx] = e.target.value;
                        setSlotDoerIds(next);
                      }}
                    >
                      <option value="">— choose —</option>
                      {doerPool.map((a) => (
                        <option key={a.id} value={a.escrowDoerId}>
                          {a.displayName} ({a.escrowDoerId})
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <button type="button" className="ghost" onClick={autofillSlotsFromPool}>
                Cycle-fill from pool (repeat if &lt; 6 agents)
              </button>
            </div>
          )}
          <div className="exp-actions">
            <button type="button" className="primary" disabled={loading} onClick={onRun}>
              {loading ? "Running…" : dryRun ? "Simulate" : "Run experiments"}
            </button>
            <button type="button" className="ghost" disabled={loading} onClick={loadPlan}>
              Reload plan
            </button>
          </div>
        </div>
        {runError && <div className="alert error">{runError}</div>}
        {result && (
          <p className="exp-meta">
            <span className={`exp-pill ${result.simulated ? "sim" : "live"}`}>
              {result.simulated ? "Simulated" : "Live"}
            </span>
            <span className="exp-meta-text">
              Target <code>{result.api_base}</code> · instance <code>{result.instance_label}</code>
              {(result.trials ?? 1) > 1 && <> · trials {result.trials}</>}
              {result.doer_ids && result.doer_ids.length === 6 && (
                <>
                  {" "}
                  · custom <code>doer_ids</code>
                </>
              )}
            </span>
          </p>
        )}
      </div>

      <div className="exp-grid">
        <section className="panel exp-plan">
          <h3>Plan</h3>
          {planError && <div className="alert error">{planError}</div>}
          {!plan && !planError && (
            <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>Loading…</p>
          )}
          {plan && (
            <>
              <p className="exp-plan-meta">
                {plan.agent_count_per_wave} agents per full wave · {plan.experiments.length}{" "}
                experiments
              </p>
              {plan.doer_id_slotting && (
                <div className="exp-slotting">
                  <strong>External doer slotting</strong>
                  <ul>
                    {Object.entries(plan.doer_id_slotting).map(([k, v]) => (
                      <li key={k}>
                        <code>{k}</code>: {v}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <ul className="exp-plan-list">
                {plan.experiments.map((ex) => (
                  <li key={ex.id}>
                    <strong>{ex.title}</strong>
                    <span className="exp-id">{ex.id}</span>
                    <p>{ex.summary}</p>
                    <ul>
                      {ex.arms.map((a) => (
                        <li key={String(a.name)}>
                          <code>{a.name}</code>
                          {a.agents != null && ` · ${a.agents} agents`}
                          {a.note && ` — ${a.note}`}
                          {a.expected_action && ` → action ${a.expected_action}`}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section className="panel exp-results">
          <h3>Results</h3>
          {!result && (
            <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
              Run or simulate to see outcome tables and timing.
            </p>
          )}

          {result && (result.trials ?? 1) > 1 && result.aggregate && (
            <div className="exp-block">
              <h4>Aggregate ({result.trials} trials)</h4>
              <pre className="json">{JSON.stringify(result.aggregate, null, 2)}</pre>
            </div>
          )}

          {result && e4 && (
            <div className="exp-block">
              <h4>
                Exp 4 — Failure recovery
                <span className="exp-badge">
                  {e4.ok ? "refund path OK" : "check steps"}
                </span>
              </h4>
              <p className="mono sm">
                final_status: <code>{String(e4.final_status ?? "—")}</code> · job_id:{" "}
                <code>{String(e4.job_id ?? "—")}</code>
              </p>
              {Array.isArray(e4.steps) && (
                <ol className="agents-protocol-steps">
                  {(e4.steps as string[]).map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              )}
              {typeof e4.error === "string" && e4.error ? (
                <div className="alert error">{e4.error}</div>
              ) : null}
            </div>
          )}

          {result && e5 && (
            <div className="exp-block">
              <h4>Exp 5 — LLM memory A vs B</h4>
              {e5.skipped ? (
                <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                  Skipped: {String(e5.reason)}
                </p>
              ) : (
                <>
                  <p className="mono sm">model: {String(e5.model ?? "—")}</p>
                  {e5.total_usage && typeof e5.total_usage === "object" && (
                    <pre className="json">
                      {JSON.stringify(e5.total_usage as object, null, 2)}
                    </pre>
                  )}
                  {e5.arms && typeof e5.arms === "object" && (
                    <div className="exp-latency" style={{ marginTop: "0.75rem" }}>
                      {Object.entries(e5.arms as Record<string, { settled_rate?: number }>).map(
                        ([name, arm]) => (
                          <div key={name} className="exp-lat-card">
                            <span className="lbl">{name}</span>
                            <span className="val">
                              {((arm.settled_rate ?? 0) * 100).toFixed(0)}% settled
                            </span>
                          </div>
                        )
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {result && rows1.length > 0 && (
            <div className="exp-block">
              <h4>
                Exp 1 — Verification strictness
                <span className="exp-badge">
                  {passCount(rows1)}/{rows1.length} expected match
                </span>
              </h4>
              <div className="table-wrap">
                <table className="exp-table">
                  <thead>
                    <tr>
                      <th>Arm</th>
                      <th>Agent</th>
                      <th>Verify</th>
                      <th>Settled</th>
                      <th>OK</th>
                      <th>ms</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows1.map((r, idx) => (
                      <tr key={`${r.agent_id}-${idx}`}>
                        <td>
                          <code>{r.arm}</code>
                        </td>
                        <td className="mono sm">{r.agent_id}</td>
                        <td>
                          {r.verify_passed === null ? "—" : r.verify_passed ? "pass" : "fail"}
                        </td>
                        <td>{r.settled ? "yes" : "no"}</td>
                        <td>
                          <span className={r.ok ? "ok-yes" : "ok-no"}>{r.ok ? "✓" : "✗"}</span>
                        </td>
                        <td className="mono sm">{(r.elapsed_s * 1000).toFixed(0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result && rows2.length > 0 && (
            <div className="exp-block">
              <h4>
                Exp 2 — Dispute policy
                <span className="exp-badge">
                  {passCount(rows2)}/{rows2.length} policy match
                </span>
              </h4>
              <div className="table-wrap">
                <table className="exp-table">
                  <thead>
                    <tr>
                      <th>Policy</th>
                      <th>Action</th>
                      <th>Agent</th>
                      <th>OK</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows2.map((r, idx) => (
                      <tr key={`${r.agent_id}-${idx}`}>
                        <td>
                          <code>{r.arm}</code>
                        </td>
                        <td>
                          <code>{r.verify_action ?? "—"}</code>
                        </td>
                        <td className="mono sm">{r.agent_id}</td>
                        <td>
                          <span className={r.ok ? "ok-yes" : "ok-no"}>{r.ok ? "✓" : "✗"}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result && sum3 && (
            <div className="exp-block">
              <h4>Exp 3 — Coordination / latency</h4>
              <div className="exp-latency">
                <div className="exp-lat-card">
                  <span className="lbl">Sequential wall</span>
                  <span className="val">{sum3.sequential_wall_s}s</span>
                  <span className="sub">
                    success {(sum3.sequential_success_rate * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="exp-lat-card">
                  <span className="lbl">Parallel wall</span>
                  <span className="val">{sum3.parallel_wall_s}s</span>
                  <span className="sub">
                    success {(sum3.parallel_success_rate * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="exp-lat-card accent">
                  <span className="lbl">Speedup</span>
                  <span className="val">{sum3.speedup ?? "—"}×</span>
                  <span className="sub">seq / par</span>
                </div>
              </div>
            </div>
          )}

          {result && (
            <details className="exp-raw">
              <summary>Raw JSON</summary>
              <pre className="json">{JSON.stringify(result, null, 2)}</pre>
            </details>
          )}
        </section>
      </div>
    </div>
  );
}
