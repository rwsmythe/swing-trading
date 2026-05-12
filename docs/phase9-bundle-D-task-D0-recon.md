# Phase 9 Sub-bundle D — Task D.0: chart_pattern hardening recon

**Purpose:** Summarize the existing chart_pattern hardening at `swing/web/routes/trades.py` (commits `117dc97` + `2b9d6f3`) so the T-D.1 sector/industry extension mirrors the shape verbatim. Recon-only — no code changes in this commit. Per plan §G T-D.0.

## §1 Scope of existing chart_pattern hardening

Two-commit chain on the entry POST handler `entry_post` in `swing/web/routes/trades.py`:

- **`117dc97` (Codex R1):** enum/FK validation gates — `chart_pattern_algo IN ('flag', 'none')`; `chart_pattern_classification_pipeline_run_id` references an existing `pipeline_runs.id`.
- **`2b9d6f3` (Codex R2):** snapshot-vs-cache match check — the hidden `pipeline_run_id` + form `ticker` MUST correspond to an actual cached `pattern_classifications` row via `get_classification(conn, pipeline_run_id, ticker)`.

## §2 Pattern shape (binding template for T-D.1)

1. **Hidden form-render fields** (`chart_pattern_algo`, `chart_pattern_algo_confidence`, `chart_pattern_classification_pipeline_run_id`, `chart_pattern_operator`, `chart_pattern_operator_other`) carry the form-render-time snapshot.
2. **Coerce empty strings to None** at the route boundary (`cp_algo_value = chart_pattern_algo or None`) — backward compat for CLI / bare cURL callers.
3. **Cached-only consumption gate:** if the operator submitted an override (`cp_operator_value is not None`) but no cached snapshot rode along (`not cache_evaluated`) → reject with `_rerender_entry_form_with_error`. Symmetric with CLI's refusal gate.
4. **Enum validation:** if `cp_algo_value not in ("flag", "none")` → reject with descriptive error.
5. **FK existence check:** if `cp_anchor_value` references no `pipeline_runs` row → reject.
6. **Snapshot-vs-cache match check (Codex R2):** if `(pipeline_run_id, ticker)` is not in `pattern_classifications` → reject ("snapshot rejected: no cached classification exists for {TICKER} under pipeline_runs.id={ID}").
7. **All rejection paths return** `_rerender_entry_form_with_error(...)` with HTTP 400 + the form re-rendered preserving operator inputs.

Key signature of the rejection helper:

```python
def _rerender_entry_form_with_error(
    *, request, templates, cfg, cache, executor,
    ticker, entry_date, entry_price, shares, initial_stop,
    rationale, notes, error_message, origin="watchlist",
) -> HTMLResponse:
    """Re-render trade_entry_form preserving operator inputs +
    banner at HTTP 400. Origin threads through so colspan + Cancel
    target match the originating surface."""
```

## §3 What sector/industry tamper hardening (T-D.1 + T-D.2) inherits

| chart_pattern | sector/industry tamper (T-D.1 + T-D.2) |
|---|---|
| Hidden inputs `chart_pattern_algo`, `..._confidence`, `..._pipeline_run_id`, `..._operator`, `..._operator_other` | Hidden inputs already present: `sector` + `industry` (per `swing/web/view_models/trades.py:340-396` form-render path) — populated from `candidates` table at form-render via the `latest_evaluation_run_id` (watchlist) or `pipeline_eval_id` (hyp-recs) anchor |
| Cached-only consumption gate keyed on `(pipeline_run_id, ticker)` hidden anchor | Cached lookup keyed on `(ticker, action_session_for_run(now()))` per spec §7 step 2 — no hidden run_id anchor; session is the natural anchor at POST-time |
| Reject via `_rerender_entry_form_with_error` (HTTP 400) | Same helper, HTTP 400, HTMX swap-enabled per `base.html.j2` `responseHandling` override (CLAUDE.md gotcha) |
| Form-render values flow AS-IS into `EntryRequest` on match | Same: form sector/industry flow into `EntryRequest.sector` + `.industry` on match |
| No audit-trail emission (advisory-only at the route layer) | **T-D.2 adds:** ad-hoc `reconciliation_runs` row with `source='system_audit'`, `state='completed'`, `period_start=period_end=action_session_iso` + `sector_tamper` discrepancy with `material_to_review=MATERIAL_BY_TYPE['sector_tamper'] = 0`. Committed in a SEPARATE TRANSACTION before the rejection response renders, so the audit persists even though the entry POST is rejected. |
| `pattern_classifications`-keyed lookup repo: `get_classification(conn, pipeline_run_id, ticker)` | `candidates`-keyed lookup via direct SELECT (no dedicated repo function needed) — joined on `evaluation_runs.action_session_date` |

## §4 Cached candidate lookup query at POST time

Per spec §7 + plan §A.4 wording (`(ticker, action_session)`), the POST-time lookup queries `candidates` joined to `evaluation_runs` on the action-session anchor:

```sql
SELECT c.sector, c.industry
FROM candidates c
JOIN evaluation_runs e ON c.evaluation_run_id = e.id
WHERE c.ticker = ? AND e.action_session_date = ?
ORDER BY e.run_ts DESC, e.id DESC
LIMIT 1
```

`action_session_date` is the session the evaluation TARGETED (forward-looking session-anchor at pipeline-run time). At POST time, the same anchor is `action_session_for_run(now()).isoformat()`. Tiebreaker `(run_ts DESC, id DESC)` for the rare same-day-multi-eval case.

**Backward-compat:** if the query returns no row (off-pipeline ticker, fresh install, mid-walk DB before any eval has run for today's session), the tamper check is SKIPPED — same shape as chart_pattern's `cp_anchor_value is None` early-out. The entry proceeds with operator-supplied sector/industry; no rejection, no audit row.

## §5 Field selection: sector vs industry mismatch — TWO discrete code paths

Per plan §G T-D.1: "TWO discrete tests: sector mismatch + industry mismatch (separate code paths)."

Sector-first short-circuit, industry-fallthrough:

1. If `cached.sector != form.sector` → reject with `field_name='sector'`.
2. ELIF `cached.industry != form.industry` → reject with `field_name='industry'`.
3. Else proceed.

The `expected_value_json` shape per spec §3.3.1 carries BOTH fields regardless of which triggered (`{"sector": cached_sector, "industry": cached_industry, "session": session_iso}`); `field_name` distinguishes the triggering column. Both-mismatch case falls under sector-first by convention (the test pair pins each path; both-mismatch is not separately spec'd — sector wins).

## §6 Why no `INSERT OR REPLACE` (binding §A.8 + watch item §I.3)

The audit emit is a pure INSERT chain inside one `with conn:` block:

1. `insert_run(..., state='running')` — INSERT
2. `insert_discrepancy(...)` — INSERT
3. `update_run_completed(...)` — UPDATE (not REPLACE; CLAUDE.md gotcha discipline preserved per Bundle B's pattern)

No table has an upsert on a unique key in Bundle D's emit path; no `INSERT OR REPLACE` risk. Bundle D inherits Bundle B's `insert_run` + `insert_discrepancy` repo entry points (composition-surface enumeration: `^def` grep in `swing/data/repos/reconciliation.py` returns single definitions).

## §7 Transaction-discipline contract for the audit emit

- **Caller-held transaction at entry:** rejected — Bundle D's audit emitter is a NEW transaction (per plan §A.4.1 SEPARATE TRANSACTION semantic). The route handler is NOT inside an open transaction at the audit-emit point (no `with conn:` wrapping the validation chain).
- **Connection scope:** Bundle D opens its own `connect(cfg.paths.db_path)` for the cached-candidate lookup AND the audit emit, then closes. The route's later `record_entry` path opens a fresh connection if/when the entry proceeds — and on rejection it never runs. Audit row commits via Python's `with conn:` deferred-transaction-on-write semantic.
- **No `conn.commit()`** inside any new repo helper (Bundle B's repo functions are pure no-commit per plan §I.5; Bundle D consumes them directly).

## §8 Composition surfaces for T-D.2's audit emit

Bundle D adds one private helper in `swing/web/routes/trades.py`:

```python
def _emit_sector_tamper_audit(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    cached_sector: str,
    cached_industry: str,
    form_sector: str,
    form_industry: str,
    session_iso: str,
    field_name: str,
) -> int:
    """Emit ad-hoc system_audit reconciliation_run + sector_tamper
    discrepancy on tamper rejection. Returns the discrepancy_id for
    test assertions / log-line plumbing. Owns its own transaction
    via `with conn:` — caller must NOT hold one."""
```

`^def _emit_sector_tamper_audit` → 1 match in `swing/web/routes/trades.py`. No cross-module duplication.

---

*End of recon. T-D.1 implements the rejection extension; T-D.2 adds the audit emit; T-D.3 wires the E2E test.*
