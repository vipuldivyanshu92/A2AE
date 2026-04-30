/* Shared client helpers used by every UI page.
 *
 * NOTE: This file is wrapped in an IIFE on purpose. Without it, every
 * `const`/`let` here lives in the global script scope, which means the
 * per-page inline `<script>` blocks that destructure `window.AE`
 * (e.g. `const { API, fmtDate } = window.AE;`) would throw
 * `Uncaught SyntaxError: Identifier 'API' has already been declared`,
 * which in turn aborts the inline script before its
 * `event.preventDefault()` handlers are wired up — so forms then
 * submit themselves via the default GET. Keep the IIFE.
 */
(function () {
  "use strict";

  const API = {
    get base() {
      // Same-origin by default. Override via ?api=... query for cross-origin testing.
      const q = new URLSearchParams(location.search).get("api");
      return (q || location.origin).replace(/\/$/, "");
    },
    async get(path) {
      const r = await fetch(`${this.base}${path}`, { headers: { Accept: "application/json" } });
      if (!r.ok) throw new Error(`GET ${path} ${r.status}: ${await r.text()}`);
      return r.json();
    },
    async post(path, body, opts = {}) {
      const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
      if (opts.idempotency) headers["Idempotency-Key"] = opts.idempotency;
      const r = await fetch(`${this.base}${path}`, {
        method: "POST",
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`POST ${path} ${r.status}: ${await r.text()}`);
      return r.json();
    },
    async del(path) {
      const r = await fetch(`${this.base}${path}`, { method: "DELETE" });
      if (!r.ok) throw new Error(`DELETE ${path} ${r.status}: ${await r.text()}`);
      return r.json();
    },
  };

  const uuid = () =>
    (crypto.randomUUID && crypto.randomUUID()) ||
    "uuid-" + Math.random().toString(16).slice(2) + Date.now().toString(16);

  const fmtDate = (s) => {
    if (!s) return "—";
    const d = typeof s === "string" ? new Date(s) : s;
    if (isNaN(d.getTime())) return "—";
    const now = Date.now();
    const diff = (now - d.getTime()) / 1000;
    if (diff < 60) return `${Math.round(diff)}s ago`;
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    return d.toISOString().slice(0, 19).replace("T", " ");
  };

  const fmtPct = (v) => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(0)}%`);
  const fmtNum = (v) => (v === null || v === undefined ? "—" : v.toString());
  const fmtSec = (v) => (v === null || v === undefined ? "—" : `${v.toFixed(2)}s`);

  const escapeHtml = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const statusBadge = (status) => `<span class="badge ${status || ""}">${escapeHtml(status || "?")}</span>`;
  const roleBadge = (role) => `<span class="badge role-${role || ""}">${escapeHtml(role || "?")}</span>`;
  const verdictBadge = (v) => `<span class="badge verdict-${v || ""}">${escapeHtml(v || "?")}</span>`;

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function setActiveNav(id) {
    document.querySelectorAll("header .links a[data-nav]").forEach((a) => {
      a.classList.toggle("active", a.dataset.nav === id);
    });
  }

  async function showError(host, e) {
    console.error(e);
    host.innerHTML = `<div class="empty" style="color:var(--bad)">Error: ${escapeHtml(e.message || e)}</div>`;
  }

  // The ONLY thing this script leaks to the global scope.
  window.AE = {
    API, uuid, fmtDate, fmtPct, fmtNum, fmtSec, escapeHtml,
    statusBadge, roleBadge, verdictBadge, $, $$, setActiveNav, showError,
  };
})();
