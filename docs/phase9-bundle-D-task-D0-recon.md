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

**Note (Codex R2 amendment 2026-05-12):** the table row that originally read "Cached lookup keyed on `(ticker, action_session_for_run(now()))` — no hidden run_id anchor" has been superseded. Sector/industry now ALSO uses a hidden anchor (`sector_industry_evaluation_run_id`) mirroring chart_pattern's `pipeline_run_id` anchor. §4 below carries the binding description.

| chart_pattern | sector/industry tamper (T-D.1 + T-D.2 + R2 anchor) |
|---|---|
| Hidden inputs `chart_pattern_algo`, `..._confidence`, `..._pipeline_run_id`, `..._operator`, `..._operator_other` | Hidden inputs: `sector`, `industry`, and (R2) `sector_industry_evaluation_run_id` (per `swing/web/view_models/trades.py:340-409` form-render path) — populated from `candidates` table at form-render via the `latest_evaluation_run_id` (watchlist) or `pipeline_eval_id` (hyp-recs) anchor; the anchor field carries the eval_run_id used to derive those values |
| Cached-only consumption gate keyed on `(pipeline_run_id, ticker)` hidden anchor | **POST-time lookup keyed on `(sector_industry_evaluation_run_id, ticker)` hidden anchor** (Codex R2 Major #1 fix). Form-render + POST agree on the exact cached row being compared against; no TOCTOU window. |
| Reject via `_rerender_entry_form_with_error` (HTTP 400) | Same helper, HTTP 400, HTMX swap-enabled per `base.html.j2` `responseHandling` override (CLAUDE.md gotcha) |
| Form-render values flow AS-IS into `EntryRequest` on match | Same: form sector/industry flow into `EntryRequest.sector` + `.industry` on match |
| No audit-trail emission (advisory-only at the route layer) | **T-D.2 adds:** ad-hoc `reconciliation_runs` row with `source='system_audit'`, `state='completed'`, `period_start=period_end=action_session_for_run(now())` + `sector_tamper` discrepancy with `material_to_review=MATERIAL_BY_TYPE['sector_tamper'] = 0`. Committed in a SEPARATE TRANSACTION before the rejection response renders, so the audit persists even though the entry POST is rejected. |
| `pattern_classifications`-keyed lookup repo: `get_classification(conn, pipeline_run_id, ticker)` | `candidates`-keyed lookup via direct SELECT — joined to `evaluation_runs` to also surface the cached candidate's `action_session_date` for the audit JSON's `expected.session` field |

## §4 Cached candidate lookup query at POST time

**(Codex R2 Major #1 + #2 amendment 2026-05-12; supersedes original recon wording.)**

Original recon wording (preserved for context): a today-anchored lookup keyed on `(ticker, action_session_for_run(now()))` joined to `evaluation_runs.action_session_date`.

**Codex R2 found two problems with the today-anchored design:**

1. **Anchor drift between form-render and POST.** The form-render at `swing/web/view_models/trades.py:392-409` populates the hidden `sector`/`industry` inputs from `latest_evaluation_run_id` (watchlist origin) or `latest_completed_pipeline_run.evaluation_run_id` (hyp-recs origin) — NOT today's action_session. A stale-pipeline scenario (today's `action_session_for_run(now())` has no eval_run yet) would render the form with stale-eval values and then POST-validation would find no today-anchored row → silently accept any tampered POST.

2. **TOCTOU race between GET and POST.** Even if today's eval_run exists at form-render time, a fresh pipeline landing between GET and POST changes the authoritative "latest" candidate. A POST-time recompute would compare against the NEW row, not the one the operator saw.

**Resolution (BINDING; mirrors chart_pattern's `pipeline_run_id` hidden anchor):**

- The form template emits a new hidden input `sector_industry_evaluation_run_id` carrying the EXACT evaluation_run_id the form-render used to populate sector/industry (`swing/web/view_models/trades.py` populates `TradeEntryFormVM.sector_industry_evaluation_run_id`; `swing/web/templates/partials/trade_entry_form.html.j2` renders it).
- The POST handler accepts `sector_industry_evaluation_run_id: int | None = Form(None)` and uses it as the authoritative anchor for the cached-candidate lookup:

```sql
SELECT c.sector, c.industry, e.action_session_date
FROM candidates c
JOIN evaluation_runs e ON c.evaluation_run_id = e.id
WHERE c.evaluation_run_id = ? AND c.ticker = ?
LIMIT 1
```

- The audit JSON's `expected.session` field carries the cached `eval_run.action_session_date` (matches what the operator saw at form-render time). The `reconciliation_runs` row's `period_start = period_end = action_session_for_run(now())` per plan §A.4.1 (describes WHEN the audit happened, distinct from the cached data's anchor).

**Backward-compat:**

- **Anchor absent (`None`)** — bare cURL / CLI / any caller not going through the form template: skip the check entirely. The hidden input is the form-flow signal; absence of anchor is the bare-cURL backward-compat path.
- **Anchor present but references no candidate row for `(eval_id, ticker)`** — tampered or stale anchor: reject with 400 + descriptive error message. No audit row is emitted (no cached values to attribute the discrepancy against). The error guidance instructs the operator to re-render the form to bind a current anchor.

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
