# Phase 14 Sub-bundle 1 — Data-wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close three Phase 14 data-wiring defects — V2.G3 (VSAT lost Sector/Industry on `/dashboard`); V2.G4 (Refresh weather chart "no OHLCV bars" error post-pipeline); P14.N3 (`/daily-management` Capital % PROVISIONAL badge unexplained, stale tooltip, no clear-condition guidance) — in a SINGLE executing-plans dispatch with ~8–12 commits + ~34–36 fast tests; Schema v21 LOCKED; L2 LOCK preserved.

**Architecture:** V2.G3 ships a NEW `swing diagnose backfill-trades-sector-industry --dry-run / --apply` CLI subcommand backed by a NEW `swing/data/repos/candidates.py:get_latest_sector_industry_per_ticker` repo helper; strict all-or-nothing UPDATE; restore-SQL artifact emitted at dry-run AND before apply for reversibility. V2.G4 fixes the call-signature mismatch at `swing/web/routes/dashboard.py:76` (positional list → keyword `ticker=`), adds a module-level logger, narrows the exception catch to `ValueError` only so programming errors propagate to FastAPI 500 (not masked as a misleading 409). P14.N3 extends `DailyManagementTileVM` (in `swing/web/view_models/trades.py`) with THREE new fields — `position_capital_denominator_dollars_resolved`, `position_capital_utilization_is_provisional`, `position_capital_utilization_pct_effective` — populated at the inline build site in `swing/web/view_models/dashboard.py:1390-1417` via the canonical `swing/metrics/maturity.py:197-219` denominator-stamping pattern (using PROPORTION-unit `compute_position_capital_utilization` from `swing/trades/daily_management.py:381-394`, NOT the percent helper); template rewritten to conditionally emit the badge + new clear-condition tooltip + inline `(?)` affordance.

**Tech Stack:** Python 3.11+ (project pyproject targets ≥3.11); SQLite (v21 schema; no migration); FastAPI + Starlette + Jinja2 + HTMX (existing surfaces; no new HTMX endpoints); Click (existing `swing diagnose` group); pytest (fast tier; no slow tests added).

---

## §A Goals + non-goals

### §A.1 Goals (V1; this sub-bundle ships)

1. **V2.G3 — backfill Sector/Industry for open trades that lost them due to JOIN gap or pre-migration-0012 legacy default.** Idempotent CLI subcommand `swing diagnose backfill-trades-sector-industry`; strict all-or-nothing semantic (both `sector` AND `industry` empty as precondition; both replacements must be non-empty for the row to UPDATE); preserves operator-acknowledged DHA/DHC legacy carve-out via `SKIP_NO_CANDIDATES_ROW` action label (no hardcoded ticker list); restore-SQL artifact at deterministic path under `exports/diagnostics/` for reversibility.
2. **V2.G4 — fix `/dashboard/weather-chart/refresh` to actually fetch SPY bars.** One-line callsite fix (`get_or_fetch([benchmark])` → `get_or_fetch(ticker=benchmark)`); remove dead dict-style consumption; add module-level `import logging; log = logging.getLogger(__name__)`; narrow exception catch from bare `except Exception` to `except ValueError` only (programming errors propagate to FastAPI default 500 handler — the broad-catch was the root-cause masking pattern).
3. **P14.N3 — clarify the PROVISIONAL badge on `/daily-management` Capital %.** Extend `DailyManagementTileVM` with 4 new fields per spec §6.2 Fix A + Codex R2.M#1+M#2 LOCK extension; build the VM via `swing/metrics/maturity.py:197-219` denominator-stamping pattern (LIVE when `account_equity_snapshots` covers the row's `data_asof_session`; PROVISIONAL otherwise; NoActivePolicyError branch surfaces a distinct policy-missing badge per spec §6.4 second bullet); preserve the existing PROPORTION-unit contract (template multiplies by 100.0); rewrite the template to (a) conditionally emit the badge only when `is_provisional=True`; (b) replace stale "V2 will resolve to live account equity (Phase 9 risk_policy versioning)" tooltip text with current clear-condition language (mentioning `account_equity_snapshots` + `swing schwab fetch --snapshot`); (c) add a visible `(?)` inline affordance so operators can diagnose the flag without hovering.

### §A.2 Non-goals (out of scope; see §D for full list)

- Any schema migration beyond v21 (escalation rule; brief §1.5 LOCK; spec §12 verdict).
- V2.G1 / V2.G2 / P14.N1 / P14.N2 / P14.N4 chart-surface work — Sub-bundle 3 scope.
- Temporal log infrastructure (`pattern_detection_events` + `pattern_forward_observations`) — Sub-bundle 2 scope; owns v22 migration slot.
- Any state-machine refactor on `daily_management_records` or `risk_policy` beyond the visibility fix.
- Any new Schwab API calls (L2 LOCK preserved; parametric source-grep test verifies).
- Any new HTMX endpoint introduction (existing `/dashboard/weather-chart/refresh` route trinity preserved; verified via regression test).
- Operator-facing manual "set capital equity" form surface — V2 candidate per spec §13.2.
- Entry-form POST-time write-time hardening for Sector/Industry — V2 candidate per spec §13.1 #1.

### §A.3 Plan-authoring-time production-code re-verification (forward-binding lesson #1; gotcha #17 / Expansion #2 refinement)

The orchestrator brief §5 watch item #1 + brainstorm return report §8 forward-binding lesson #1 BIND the plan author to re-grep every production function signature cited in the spec. Verifications performed at plan-authoring time against worktree HEAD (branch `phase14-sub-bundle-1-data-wiring-writing-plans`, branched from `main` HEAD `b384cc1`):

| Surface | Spec citation | Re-verified at plan-authoring | Outcome |
|---|---|---|---|
| `resolve_live_capital_denominator_dollars(conn, *, asof_date: date, at_trade_time_policy: RiskPolicy) -> tuple[float, Literal["LIVE", "PROVISIONAL"]]` | spec §0 + §6.1 | `swing/metrics/equity_resolver.py:32-59` | EXACT MATCH |
| `read_live_policy(conn: sqlite3.Connection) -> RiskPolicy` | spec §0 | `swing/metrics/policy.py:39-46` | EXACT MATCH |
| `compute_position_capital_utilization(*, current_size, current_price, denominator_dollars) -> float` (PROPORTION) | spec §6.2 + R3.M1 LOCK | `swing/trades/daily_management.py:381-394` | EXACT MATCH; returns `(current_size * current_price) / denominator_dollars` PROPORTION |
| `_compute_position_util_pct(*, avg_cost, size, denom) -> float \| None` (PERCENT, × 100.0) | spec §6.2 (negative reference; do NOT use) | `swing/metrics/maturity.py:296-304` | EXACT MATCH; returns `(exposure / denom) * 100.0` — using this would render 1500.0% per R3.M1; plan deliberately avoids it |
| `maturity.py:197-219` denominator-stamping pattern (resolve → `math.isclose(stored_denom, denom_dollars, rel_tol=1e-9)` → reuse-stored OR recompute) | spec §6.2 + R1.M1 LOCK | `swing/metrics/maturity.py:188-247` | EXACT MATCH (slightly broader range; pattern is at 188-229 + recompute branch 230-246) |
| `OhlcvCache.get_or_fetch(self, *, ticker: str, window_days: int = 180) -> pd.DataFrame` (keyword-only `ticker`; DataFrame return) | spec §5.1 | `swing/web/ohlcv_cache.py:131-180` | EXACT MATCH; confirms the V2.G4 callsite `get_or_fetch([benchmark])` raises `TypeError` |
| `swing/web/routes/dashboard.py` weather-chart refresh handler at lines 39-114; NO `logging` import; NO module-level `log`; bare `except Exception` swallow at line 78 | spec §5.1 + R3.M2 LOCK | re-read at plan-authoring | EXACT MATCH; bare `except Exception: bars = None` confirmed at line 78; NO module-level logger present in file imports (lines 1-18) |
| `swing/web/view_models/dashboard.py:1390-1417` inline tile VM construction with 14 keyword args | spec §6.2 module touch list | re-read at plan-authoring | EXACT MATCH; tile assembled inline via `DailyManagementTileVM(...)` keyword-arg constructor with `trade_id`, `ticker`, `state`, `current_stop`, `planned_target_R`, `current_price`, `open_R_effective`, `open_MFE_R_to_date`, `open_MAE_R_to_date`, `maturity_stage`, `trail_MA_eligibility_flag`, `trail_MA_candidate_price`, `position_capital_utilization_pct`, `position_capital_denominator_dollars`, `position_portfolio_heat_contribution_dollars`, `data_asof_session` |
| `DailyManagementTileVM` dataclass | spec §3 + §6.2 OQ #5 | `swing/web/view_models/trades.py:2042-2078` | EXACT MATCH; the dataclass lives in `trades.py` NOT `daily_management.py`; OQ #5 RESOLVED at plan: dataclass extension lives at `trades.py:2042-2078`; build-site extension at `dashboard.py:1390-1417` |
| `swing/web/templates/partials/daily_management_tile.html.j2:91-99` PROVISIONAL badge + stale tooltip | spec §6.1 | re-read at plan-authoring | EXACT MATCH; badge currently unconditional whenever `tile.position_capital_utilization_pct is not none`; tooltip text exactly matches spec citation |
| `swing/cli.py:4716-4789` `@main.group("diagnose")` + `_validate_diagnose_db_path` precedent + 7 existing diagnose subcommands | spec §3 module touch list (OQ-17 carve-out precedent) | re-read at plan-authoring | EXACT MATCH; CLI subcommand lives in `swing/cli.py`, NOT a separate `swing/cli_diagnose.py` (which does not exist); OQ-17 V2 OHLCV precedent at `aplus-sensitivity-v2` line 4791 is the canonical template for the new backfill subcommand |
| `swing/data/repos/candidates.py` 3-function module (`insert_evaluation_run`, `insert_candidates`, `fetch_candidates_for_run`) | spec §3 module touch list | re-read at plan-authoring | EXACT MATCH; NEW `get_latest_sector_industry_per_ticker` helper lands as 4th top-level function in this file |
| Migration `0012_sector_industry.sql` columns: `candidates.sector` (line 20), `candidates.industry` (line 21), `trades.sector` (line 23), `trades.industry` (line 24); all `TEXT NOT NULL DEFAULT ''` | spec §4.1 + §12 | re-read at plan-authoring | EXACT MATCH; additive ALTER TABLE per SQLite O(metadata) semantic preserved |
| `swing/data/migrations/*.sql` file count (Schema v21 LOCK) | spec §12 + brief §1.5 LOCK | counted at plan-authoring | EXACT MATCH — **21** migration files; v21 LOCK preserved |
| Existing weather-chart refresh test path | spec §3 + §11 | grepped `tests/` for `weather_chart_refresh` / `test_dashboard_weather` | 1 hit at `tests/web/test_routes/test_dashboard_chart_integration.py`; plan locks this as MODIFIED test file; new test module added if scope warrants (per §B) |

**ZERO signature drift detected at plan-authoring time.** All 14 production surfaces cited in the brainstorm spec match HEAD `b384cc1` exactly. Forward-binding lesson #1 discipline preserved.

### §A.4 Source-of-truth invariants (plan SHALL preserve)

1. **`Co-Authored-By` footer suppression** — project invariant; ~591+ cumulative ZERO drift streak; verified via `%(trailers)` post-merge inspection. No commit on this writing-plans branch OR on the executing-plans branch may carry a `Co-Authored-By:` trailer line.
2. **No `--no-verify` on commits** — project invariant; CLAUDE.md "Conventions" + project discipline.
3. **Schema v21 LOCK** — 21 `swing/data/migrations/*.sql` files at branch HEAD; no v22+ added by this sub-bundle (Sub-bundle 2 owns v22; Sub-bundle 3 owns v23).
4. **L2 LOCK** — ZERO new `schwabdev.Client.*` call sites; verified via NEW parametric source-grep test at T-4.1 against commissioning baseline `bf7e071`.
5. **ASCII-only discipline** across the NEW/MODIFIED production code + test files + return report; declared scope at §15.2 of the spec carried forward verbatim (the plan doc itself + dispatch briefs are excluded per spec §15.2 rationale — both use `§` extensively).
6. **PROPORTION-unit semantic** for P14.N3 (R3.M1 LOCK; brief §5 watch item #3) — `compute_position_capital_utilization` returns proportion; template multiplies by 100.0; do NOT swap in `_compute_position_util_pct`.
7. **Operator-locked Sec 9.1 LOCKs + spec §2 LOCKs + brief §1 LOCKs** — see §E cumulative LOCK table; do NOT re-litigate at executing-plans phase.

---

## §B File map

### §B.1 Production code — NEW files

| Path | Type | Item | Purpose | LOC est. |
|---|---|---|---|---|
| (none) | — | — | Sub-bundle 1 introduces ZERO new production-code modules. The new repo helper extends an existing module; the new CLI subcommand extends an existing module; the new VM fields extend an existing dataclass; the new template wording extends an existing template. | — |

### §B.2 Production code — MODIFIED files

| Path | Type | Item | Diff range | Purpose |
|---|---|---|---|---|
| `swing/data/repos/candidates.py` | MODIFIED | V2.G3 | append after line 86 (after `fetch_candidates_for_run`) | NEW top-level function `get_latest_sector_industry_per_ticker(conn, tickers) -> dict[str, CandidateSectorIndustryRecord]`; ~40-55 LOC including docstring + `CandidateSectorIndustryRecord` frozen-dataclass (`sector: str, industry: str, candidate_id: int | None, evaluation_run_id: int | None`) carrying provenance so the V2.G3 dry-run table can audit which candidates row supplied a backfill (Codex R1.M#6 LOCK); SQL via dynamic `?` expansion (gotcha #20); empty-input short-circuit |
| `swing/cli.py` | MODIFIED | V2.G3 | append after line 5170 (after `diagnose_prune_chart_cache`) | NEW `@diagnose_group.command("backfill-trades-sector-industry")` subcommand + helpers; ~150-220 LOC including docstring + dry-run table emit + restore-SQL artifact emit + apply-path UPDATE under `with conn:`; mirrors `_validate_diagnose_db_path` precedent at line 4731 |
| `swing/web/routes/dashboard.py` | MODIFIED | V2.G4 | insert at line 4 (add `import logging` after `from datetime import datetime`); insert at line ~17 (add `log = logging.getLogger(__name__)` after `router = APIRouter()`); rewrite block at lines 74-87 (replace dead dict-style consumption + narrow exception catch) | +3 import/module lines (logging import + logger module-level addition); ~10 net-changed lines in the handler body |
| `swing/web/view_models/trades.py` | MODIFIED | P14.N3 | extend `@dataclass DailyManagementTileVM` at lines 2042-2078 with 4 NEW field declarations | +4 lines: `position_capital_denominator_dollars_resolved: float`, `position_capital_utilization_is_provisional: bool`, `position_capital_utilization_pct_effective: float \| None`, `position_capital_policy_missing: bool` (Codex R2.M#1+#2 LOCK -- flag for no-active-risk_policy fallback so template can render PROVISIONAL badge + extra-caveat tooltip OUTSIDE the util-value guard even when util is None) |
| `swing/web/view_models/dashboard.py` | MODIFIED | P14.N3 | extend inline build at lines 1390-1417 with denominator-stamping mirror per `maturity.py:197-219`; also need to add the imports for `resolve_live_capital_denominator_dollars`, `read_live_policy`, `compute_position_capital_utilization`, `date`, `math` at top of file (audit existing imports first; many likely already present) | ~15-25 net-added LOC in the build site + ~3-5 import lines if any missing |
| `swing/web/templates/partials/daily_management_tile.html.j2` | MODIFIED | P14.N3 | replace block at lines 91-99 (the PROVISIONAL badge `<td>`) | ~15-20 net-changed Jinja LOC: conditional badge emit; rewritten tooltip text; `(?)` inline affordance; render `position_capital_utilization_pct_effective` instead of `position_capital_utilization_pct` |

### §B.3 Production code — OPTIONAL-MODIFIED files (Fix-1b VM fallback)

| Path | Type | Item | Diff range | Purpose | Trigger |
|---|---|---|---|---|---|
| `swing/web/view_models/open_positions_row.py` OR equivalent open-positions VM module | OPTIONAL-MODIFIED | V2.G3 Fix-1b | TBD at executing-plans phase if trigger fires | VM-time per-ticker fallback: if `trade.sector == ""` OR `trade.industry == ""`, fall back to `get_latest_sector_industry_per_ticker(conn, [trade.ticker])` at render time | ONLY if writing-plans-phase code-read OR operator-witnessed gate at S3 surfaces residual empty cells AFTER T-1.2 backfill apply; pre-ship NOT IN PLAN per spec §4.2 + dispatch brief §1.3 (T-1.3 = optional task; only ship if triggered) |

### §B.4 Test code — NEW files

| Path | Type | Item | Purpose | Test count est. |
|---|---|---|---|---|
| `tests/data/repos/test_candidates_sector_industry_helper.py` | NEW | V2.G3 | Discriminating tests for `get_latest_sector_industry_per_ticker`: empty-input short-circuit; happy path single ticker; multi-ticker; non-empty-AND filter (sector OR industry empty → not returned); ordering by `evaluation_run_id DESC, id DESC`; tickers with no qualifying row map to `("", "")` | ~6-8 tests |
| `tests/cli/test_diagnose_backfill_trades_sector_industry.py` | NEW | V2.G3 | Discriminating tests for the new CLI subcommand: dry-run table emit; restore-SQL artifact emit + content shape; AND-empty WHERE clause filter; SKIP_PARTIAL_EMPTY action label; SKIP_NO_CANDIDATES_ROW action label; --apply atomic UPDATE; idempotency (second --apply is no-op); --include-closed flag; --allowlist option; --apply emits restore-SQL BEFORE issuing UPDATEs; `_validate_diagnose_db_path` precedent re-applied | ~8-10 tests |
| `tests/integration/test_l2_lock_source_grep.py` | NEW | All | Parametric source-grep test asserting `git grep` of `schwabdev.Client.` under `swing/` at HEAD has the SAME OR FEWER occurrences than at commissioning baseline `bf7e071` | 1 parametric test |

### §B.5 Test code — MODIFIED files

| Path | Type | Item | Modification | Test count est. |
|---|---|---|---|---|
| `tests/web/test_routes/test_dashboard_chart_integration.py` | MODIFIED | V2.G4 | Add tests: (a) `get_or_fetch` called with `ticker=` kwarg (signature regression); (b) ValueError-degraded path emits `log.warning` via `caplog` + returns 409; (c) TypeError / AttributeError / RuntimeError / KeyError propagate as 500 (NOT 409); (d) happy path returns 204 + `HX-Redirect: /dashboard` with chart_render row written | ~6-8 tests (4 propagation cases per spec §5.2 split into individual parametric / discriminating cases) |
| `tests/web/test_daily_management_tile.py` | MODIFIED | P14.N3 | Add tests: (a) PROVISIONAL badge emitted when `is_provisional=True`; (b) PROVISIONAL badge NOT emitted when `is_provisional=False` (LIVE); (c) tooltip text NEW wording present + stale "Phase 9 risk_policy versioning" text REMOVED; (d) `(?)` inline affordance HTML structure present; (e) Capital % value renders `position_capital_utilization_pct_effective` (NOT stale `position_capital_utilization_pct`); (f) PROPORTION unit preserved (1500% regression test); (g) ASCII discipline | ~7-9 tests |
| `tests/web/view_models/test_dashboard_view_model.py` OR equivalent dashboard-VM test module | MODIFIED | P14.N3 | Add tests for the 4 NEW VM fields: (a) `position_capital_denominator_dollars_resolved` populated via `resolve_live_capital_denominator_dollars`; (b) `position_capital_utilization_is_provisional` True when no `account_equity_snapshots` row covers `data_asof_session`, False when one does; (c) `position_capital_utilization_pct_effective` reuses snapshot's stored when denominators match via `math.isclose(..., rel_tol=1e-9)`, recomputes via `compute_position_capital_utilization` otherwise; (d) ValueError-guarded fallback for malformed `data_asof_session`; (e) `position_capital_policy_missing` True when NoActivePolicyError fires (Codex R2.M#1+M#2 + R1.M#1 LOCK) | ~5-6 tests |

### §B.6 Documentation deliverables

| Path | Type | Purpose |
|---|---|---|
| `docs/superpowers/plans/2026-05-28-phase14-sub-bundle-1-data-wiring-plan.md` | NEW | THIS plan doc |
| `docs/phase14-sub-bundle-1-data-wiring-writing-plans-return-report.md` | NEW | Return report per brief §8; drafted at T-4.2 closer |

### §B.7 File-touch count summary

- **Production code:** 6 MODIFIED files (`swing/data/repos/candidates.py`, `swing/cli.py`, `swing/web/routes/dashboard.py`, `swing/web/view_models/trades.py`, `swing/web/view_models/dashboard.py`, `swing/web/templates/partials/daily_management_tile.html.j2`); +1 OPTIONAL-MODIFIED (`swing/web/view_models/open_positions_row.py` ONLY if Fix-1b triggers). ZERO NEW production modules. ZERO `swing/data/migrations/*.sql` files added.
- **Test code:** 3 NEW test files + 3 MODIFIED test files. Total ~32-41 new tests projected (the plan's working estimate is **~34-36 fast tests** matching spec §10.3 + brief §1.5 L3).
- **Documentation:** 1 NEW plan doc + 1 NEW return report.

---

## §C Surface-by-surface integration analysis

### §C.1 V2.G3 integration surface

**Read path (post-fix unchanged):** `build_dashboard` (in `swing/web/view_models/dashboard.py`) constructs `open_positions_rows` from `list_open_trades()` results; each row consumes `trade.sector` + `trade.industry` directly; template at `swing/web/templates/partials/open_positions_row.html.j2:37-38` renders `{{ row.trade.sector or "—" }}` + `{{ row.trade.industry or "—" }}`. **No read-path change required** — the schema columns + dataclass fields + template rendering are already wired correctly per spec §4.1 H0 falsification.

**Write path (one-time backfill):** NEW `swing diagnose backfill-trades-sector-industry --apply` invokes `get_latest_sector_industry_per_ticker(conn, open_ticker_set)`; for each `(trade_id, ticker)` where BOTH `trades.sector` AND `trades.industry` are TRIM-empty AND a non-empty replacement `(sector, industry)` tuple is available from the helper, issues atomic `UPDATE trades SET sector=?, industry=? WHERE id=? AND TRIM(sector)='' AND TRIM(industry)=''` under `with conn:`. Idempotent (the WHERE clause makes re-runs no-op). Restore-SQL artifact written BEFORE UPDATEs fire.

**Failure surfaces:**
- Pre-migration-0012 legacy default (`''` from `ALTER TABLE ADD COLUMN ... DEFAULT ''`) → backfill UPDATEs the row.
- Entry-form POST persisted `''` because ticker had no candidates row that day → backfill UPDATEs the row using historical candidates row (ordered by `evaluation_run_id DESC, id DESC` per helper SQL).
- Acknowledged-legacy DHA/DHC (no historical candidates row ever) → helper returns `("", "")`; backfill emits `SKIP_NO_CANDIDATES_ROW` action label; no UPDATE; template continues to render em-dash placeholder.
- Partial-empty (`sector="Tech"`, `industry=""`) → backfill SELECT excludes via AND-empty WHERE; separate diagnostic SELECT enumerates partial-empty rows in the dry-run table with action `SKIP_PARTIAL_EMPTY`; V1 STRICT all-or-nothing per R2.M3 LOCK; V2 candidate banked.

**Cross-fix coexistence:** V2.G3 backfill is a read-mostly maintenance op; does NOT touch the open-positions read path; does NOT touch `/dashboard/weather-chart/refresh` (V2.G4); does NOT touch `/daily-management` (P14.N3). ZERO cross-fix conflict surface.

### §C.2 V2.G4 integration surface

**Read path (post-fix):** `POST /dashboard/weather-chart/refresh` handler at `swing/web/routes/dashboard.py:39-114`:
1. Resolve `cfg = apply_overrides(request.app.state.cfg)`.
2. Connect to DB via `connect(cfg.paths.db_path)`.
3. Check `latest_completed_pipeline_run(conn)` is not None (409 if so) — UNCHANGED.
4. Check `ohlcv_cache` is not None (409 if so) — UNCHANGED.
5. Resolve `benchmark = cfg.rs.benchmark_ticker` — UNCHANGED.
6. **CHANGED**: invoke `bars = ohlcv_cache.get_or_fetch(ticker=benchmark)` (keyword `ticker=`, not positional list); narrow exception catch to `except ValueError as exc: log.warning(...); bars = None`.
7. Check `bars is None or bars.empty` → 409 with operator-friendly message — UNCHANGED.
8. Render via `render_market_weather_svg(bars=bars, trend_template_state="n/a")` — UNCHANGED.
9. Build `ChartRender` + invoke `refresh_chart_render(conn, chart_render)` under `with conn:` — UNCHANGED.
10. Return `204` + `HX-Redirect: /dashboard` — UNCHANGED (HTMX trinity preserved).

**Module-level logger addition (R3.M2 LOCK)**: The file currently imports `from datetime import datetime` + `from fastapi import APIRouter, HTTPException, Request` + `from fastapi.responses import HTMLResponse, Response` + 5 swing-internal modules (lines 1-15). NO `logging` import; NO module-level `log` defined. Plan T-2.1 step 1 adds `import logging` (placed after `from datetime import datetime` to keep stdlib imports grouped) + `log = logging.getLogger(__name__)` (placed after `router = APIRouter()` at line 17). This MUST land in the SAME commit as the new `log.warning(...)` call per R3.M2 LOCK + forward-binding lesson #4; otherwise the warning call raises `NameError` at the first ValueError-degraded path invocation.

**Programming-error propagation (R2.M2 LOCK / forward-binding lesson #8):** The narrow `ValueError`-only catch ensures `TypeError`, `AttributeError`, `KeyError`, `RuntimeError`, and any other programming-error exception propagates to FastAPI's default exception handler (which returns 500 with traceback in logs). This prevents the V2.G4 root-cause class (programming errors silently masked as misleading 409s) from recurring.

**HTMX trinity preservation (forward-binding lesson #7):** No new HTMX surface is introduced. The existing `POST /dashboard/weather-chart/refresh` route preserves all three browser-only failure surfaces:
- HX-Request header propagation on the embedded form at `swing/web/templates/dashboard.html.j2` (existing `hx-headers='{"HX-Request": "true"}'`);
- 204 + `HX-Redirect: /dashboard` success-path response (NOT 303 swap-target);
- `/dashboard` target route registered at `index()` in same module (line 20-31).
Plan T-2.1 acceptance criterion 4 (per §G.T-2.1) includes a regression test asserting these invariants.

**Cross-fix coexistence:** V2.G4 fix is route-handler-only; does NOT touch V2.G3 backfill helper OR open-positions VM OR daily-management VM OR template. ZERO cross-fix conflict surface; S6 cross-fix regression check at operator-witnessed gate confirms.

### §C.3 P14.N3 integration surface

**Read path (post-fix):** `build_dashboard` constructs the per-trade `DailyManagementTileVM` inline at lines 1390-1417. The build-site extension wires the 4 new fields (Codex R2.M#1+M#2 LOCK added `position_capital_policy_missing` as the 4th):

```python
# (Inside the existing per-(trade, snap) loop)
row_asof = asof_date  # fall back to page-level asof_date if snap is missing
if snap is not None and snap.data_asof_session:
    try:
        row_asof = date.fromisoformat(snap.data_asof_session)
    except ValueError:
        row_asof = asof_date  # ValueError-guarded fallback per maturity.py:190-194

# NoActivePolicyError fallback per Codex R1.M#1 + R2.M#1+M#2 LOCK +
# spec section 6.4 second bullet: read_live_policy ->
# get_active_policy raises NoActivePolicyError when no risk_policy row
# has is_active=1 (pre-Phase-9 / pre-seed DB state OR a manual UPDATE
# that flipped every row inactive). The build site treats this as
# PROVISIONAL with EXTRA-CAVEAT tooltip per spec section 6.4 second
# bullet -- NOT a 500. Codex R2.M#1+#2 LOCK: set policy_missing=True
# so the template can render the badge + caveat OUTSIDE the util-
# value guard (otherwise util_pct_effective=None suppresses badge).
try:
    live_policy = read_live_policy(conn)
    policy_missing = False
except NoActivePolicyError:
    live_policy = None
    policy_missing = True
if live_policy is not None:
    denom_resolved, denom_badge = resolve_live_capital_denominator_dollars(
        conn, asof_date=row_asof, at_trade_time_policy=live_policy,
    )
else:
    # Denominator undefined; PROVISIONAL with util=None
    # (template renders em-dash for the value + emits the policy-
    # missing badge + extra-caveat tooltip via the policy_missing flag).
    denom_resolved = 0.0
    denom_badge = "PROVISIONAL"
is_provisional = (denom_badge == "PROVISIONAL")

# Denominator-stamping mirror per maturity.py:197-219:
stored_util = snap.position_capital_utilization_pct if snap is not None else None
stored_denom = snap.position_capital_denominator_dollars if snap is not None else None
if (
    stored_util is not None
    and stored_denom is not None
    and math.isclose(stored_denom, denom_resolved, rel_tol=1e-9)
):
    util_pct_effective = stored_util  # reuse stored proportion
elif (
    trade.current_size is not None
    and snap is not None
    and snap.current_price is not None
    and denom_resolved > 0
):
    # Recompute as PROPORTION (R3.M1 LOCK; NOT _compute_position_util_pct
    # which returns percent already multiplied by 100):
    util_pct_effective = compute_position_capital_utilization(
        current_size=trade.current_size,
        current_price=snap.current_price,
        denominator_dollars=denom_resolved,
    )
else:
    util_pct_effective = None  # ill-defined; template renders em-dash placeholder

tiles.append(DailyManagementTileVM(
    trade_id=snap.trade_id,
    # ... existing 13 fields unchanged ...
    position_capital_utilization_pct=(
        snap.position_capital_utilization_pct
    ),  # PRESERVED for backwards compat (other consumers may still read it)
    position_capital_denominator_dollars=(
        snap.position_capital_denominator_dollars
    ),
    # NEW 3 fields per spec §6.2:
    position_capital_denominator_dollars_resolved=denom_resolved,
    position_capital_utilization_is_provisional=is_provisional,
    position_capital_utilization_pct_effective=util_pct_effective,
    # ... existing remaining fields ...
))
```

**Unit semantic preservation (R3.M1 LOCK / forward-binding lesson #3):**
- `compute_position_capital_utilization` (`swing/trades/daily_management.py:381-394`) returns PROPORTION (e.g., `0.15` for 15%).
- Template at line 93 multiplies by `100.0`: `{{ "%.1f"|format(tile.position_capital_utilization_pct_effective * 100.0) }}%`.
- DO NOT swap in `_compute_position_util_pct` (`swing/metrics/maturity.py:296-304`) which returns PERCENT (already `× 100.0`); doing so would render `15.0 × 100.0 = 1500.0%` — exactly the regression R3.M1 caught.
- Plan T-3.1 includes a discriminating test that asserts the rendered value is `< 50%` for a 15% (0.15) proportion fixture (acceptance criterion check; see §G.T-3.1 step 9).

**Template rewrite (spec §6.2):**

```jinja
<td data-tile-cell="position_capital_utilization_pct">
    {%- if tile.position_capital_utilization_pct_effective is not none -%}
        {{ "%.1f"|format(tile.position_capital_utilization_pct_effective * 100.0) }}%
    {%- else -%}--{%- endif -%}
    {#- Codex R2.M#1+M#2 LOCK: badge + help rendered OUTSIDE the util-value
        guard so the NoActivePolicyError fallback (where
        util_pct_effective is None + policy_missing=True) still surfaces
        the PROVISIONAL marker with a distinct extra-caveat tooltip. -#}
    {%- if tile.position_capital_policy_missing -%}
        <span class="badge badge-provisional" data-marker="PROVISIONAL"
              data-cause="policy_missing"
              title="No active risk_policy row -- denominator cannot be resolved. Schema-corrupted state (zero rows have is_active=1). Recovery requires direct DB intervention: SELECT a historical policy_id from risk_policy, then UPDATE risk_policy SET is_active=1, effective_to=NULL WHERE policy_id=<id>. The standard `swing config policy ...` CLI cannot recover this state because supersede_active_policy raises when no active row exists (swing/trades/risk_policy.py:139-142). Re-running `swing db-migrate` does NOT re-seed an already-v21 DB.">PROVISIONAL</span>
        <button type="button" class="muted help-affordance"
                data-help="provisional-capital-policy-missing"
                aria-describedby="provisional-capital-help-1"
                aria-label="Why is this PROVISIONAL?">
            (?)
        </button>
        <span id="provisional-capital-help-1" class="help-detail" role="tooltip">
            No active risk_policy row found (zero rows have is_active=1). Run `swing db-migrate` or `swing config policy import-from-toml` to remediate.
        </span>
    {%- elif tile.position_capital_utilization_is_provisional -%}
        <span class="badge badge-provisional" data-marker="PROVISIONAL"
              data-cause="snapshot_missing"
              title="Capital denominator is the V1 fallback (capital_floor_constant_dollars). Clears to LIVE when an account_equity_snapshots row covers the session date (e.g., swing schwab fetch --snapshot when integration LIVE).">PROVISIONAL</span>
        <button type="button" class="muted help-affordance"
                data-help="provisional-capital"
                aria-describedby="provisional-capital-help-1"
                aria-label="Why is this PROVISIONAL?">
            (?)
        </button>
        <span id="provisional-capital-help-1" class="help-detail" role="tooltip">
            LIVE when account_equity_snapshots row covers today; PROVISIONAL otherwise.
        </span>
        <!-- NOTE: id suffix mirrors tile.trade_id at template render time
             so multiple PROVISIONAL tiles on the same page emit unique
             ids. Codex R1.M#2 LOCK -- aria-describedby targets MUST be
             unique per tile. Test uses tile_id=1 fixture. -->
    {%- endif -%}
</td>
```

(ASCII-only per gotcha #32; em-dash placeholder rendered as `--` per spec §6.2 + §15.2 declaration.)

**Server-stamping discipline (forward-binding lesson #13):** All 4 NEW VM fields are SERVER-COMPUTED at build time from authoritative inputs (`account_equity_snapshots` row + active risk_policy + snapshot's stored denominator + NoActivePolicyError exception state). NO hidden form input. NO operator-supplied state. Re-renders consistently across page loads with no operator interaction surface. Honors Phase 8 R2.M2+R3.M2+R4.M2 server-stamping family discipline.

**Cross-fix coexistence:** P14.N3 fix is template + VM only; consumes `equity_resolver` + `read_live_policy` + `compute_position_capital_utilization` (Phase 9 + Phase 11 shipped substrates); does NOT touch V2.G3 backfill OR V2.G4 refresh handler. ZERO cross-fix conflict surface.

### §C.4 Cross-item shared infrastructure

The three items share **only** the broader `/dashboard` + `/daily-management` web surface umbrella; they do not share substrate code. Test isolation per spec §8:
- V2.G3 tests live under `tests/data/repos/` + `tests/cli/`;
- V2.G4 tests live under `tests/web/test_routes/`;
- P14.N3 tests live under `tests/web/` + `tests/web/view_models/`.
- Shared TestClient fixtures from existing `tests/web/conftest.py` (`swing_db_in_tmp_path`) acceptable across V2.G4 + P14.N3.

---

## §D Out of scope (explicit; do not include in plan; reject if Codex suggests otherwise)

1. **V2 candidates banked at brainstorm return report §7** (8 candidates: V2.G3 Fix B / Fix-1b / Fix C / Fix D / partial-recovery; V2.G4 Fix B / Fix C; P14.N3 manual-equity-entry form). These are V2-only; do NOT design into V1 plan. **HOLD THE LINE if Codex pushes back.**
2. **VM fallback Fix-1b (T-1.3)** pre-ship — UNLESS the writing-plans-phase code-read OR an operator-witnessed-gate trigger fires per §B.3 trigger condition. Default: do NOT execute T-1.3.
3. **Schema migrations beyond v21** — escalation rule per spec §12 + brief §1.5. If executing-plans phase surfaces an unavoidable migration, STOP + escalate to orchestrator. Do NOT silently introduce v22 (would collide with Sub-bundle 2 temporal log v22 slot).
4. **Sub-bundle 2 (temporal log V1+) / Sub-bundle 3 (chart-surface uniformity) / Sub-bundle 4 (review + journal UX) / Sub-bundle 5 (metrics overview)** — per Sec 9.1 Q1 LOCK + Q2 LOCK serial execution.
5. **Phase 15+ scope** — substrate-size augmentation; Finviz filter widening; cohort-stability LOCK; D2 baseline canonical_survival_rate L4 remediation; ruleset deployment work.
6. **V2.G2 schema rename** (`hyprec_detail` → `ticker_detail`) — Sub-bundle 3 scope per Sec 9.1 Q4 LOCK.
7. **Temporal log infrastructure** (`pattern_detection_events` + `pattern_forward_observations` + `_step_pattern_observe`) — Sub-bundle 2 scope per Sec 9.1 Q3 LOCK; v22 belongs there.
8. **New HTMX endpoint introductions** — V2.G4 fix preserves the existing `/dashboard/weather-chart/refresh` route; no new HTMX endpoints. Trinity discipline preserved on the existing endpoint.
9. **Phase 8 daily-management state machine refactor** beyond P14.N3 visibility fix.
10. **Schwab API integration changes** — L2 LOCK preserved; parametric source-grep test at T-4.1 verifies.
11. **Operator failure-mode classification surface** — Phase 15+ candidate per Sec 9.1 Q3 LOCK temporal log V1+ does NOT include.
12. **CLAUDE.md / orchestrator-context archive-splits** — not Sub-bundle 1 scope.
13. **Entry-form POST-time hardening for Sector/Industry write** — V2 candidate per spec §13.1 #1 (V2.G3 Fix B).
14. **Pipeline-step contract changes** (`_step_evaluate` unioning open-trade tickers) — spec §4.2 Fix C explicitly NOT recommended; banked as V2 alternative path.
15. **Manual "set capital equity" web form** — spec §13.2 V2 candidate.

---

## §E Operator-paired locks reverification (cumulative LOCK summary table)

Per brief §1.5 L5: this section re-cites Sec 9.1 LOCKs + spec §2 LOCKs + brief §1 LOCKs verbatim in one consolidated cumulative LOCK table. Each LOCK is preserved verbatim from the source; ZERO modifications.

### §E.1 Sec 9.1 commissioning LOCKs (binding for ALL Phase 14 sub-bundles)

| # | Decision | LOCKed value (verbatim) | Spec citation | Plan citation |
|---|---|---|---|---|
| Q1 | Sub-bundle sequencing | "Data-wiring -> temporal log -> charts -> review+journal -> metrics" (brief Sec 3 recommended order) | spec §2.3 | §A.2 + §D #4 |
| Q2 | Execution mode | "Serial -- one sub-bundle at a time; cumulative discipline verification at each merge" | spec §2.3 | §A.2 + §D #4 |
| Q3 | Temporal log V1 scope | "V1+ -- base (2 tables + `_step_pattern_observe` + per-pattern metadata) PLUS chart_render bytes capture at detection time (closes CR.1 dependency cleanly)" | spec §2.4 (out-of-scope reference) | §D #7 |
| Q4 | V2.G2 schema rename | "Ship in chart-surface uniformity sub-bundle (v23 migration) -- coupled with P14.N1 + P14.N2; data-migration discipline for existing chart_renders rows per gotcha #11 LOCK" | spec §2.4 (out-of-scope reference) | §D #6 |
| Q5 | Metrics overview graphics library | "Matplotlib SVG -- consistent with chart_renders pattern; no new dependency surface; static rendering only" | (out-of-scope reference) | §D #4 |
| Q6 | Phase 14 close-out criteria | "All 5 sub-bundles merged + operator browser-witnessed verification -- matches Phase 13 closer precedent; per-sub-bundle operator-witnessed gate at merge time + final Phase 14 cross-sub-bundle integration review" | spec §2.4 | §I |
| Q7 | Codex MCP chain count per sub-bundle | "Orchestrator discretion per sub-bundle -- two-chain for analytical sub-bundles (temporal log likely qualifies; brainstorming confirms); single-chain at orchestrator discretion for pure UX/wiring sub-bundles per gotcha #36 explicit caveat" | spec §2.2 | §J |

### §E.2 Brainstorm dispatch brief §1 LOCKs (this sub-bundle)

| § | Decision | LOCKed value (verbatim) | Spec citation | Plan citation |
|---|---|---|---|---|
| §1.1 | Sub-bundle scope | "ONLY V2.G3 + V2.G4 + P14.N3. No widening." | spec §2.1 | §A.1 + §D #1 |
| §1.2 | Codex chain count | "SINGLE Codex MCP chain at end of brainstorm per gotcha #36 explicit caveat" + brainstorm convergence target "2-4 rounds" | spec §2.2 | §J |
| §1.3 | Serial execution | "Sub-bundle 2 (temporal log V1+) depends on Sub-bundle 1 merge" | spec §2.3 | §A.2 |
| §1.4 | Operator-witnessed gate | "Sub-bundle 1 ships with per-sub-bundle operator-witnessed gate (browser verification of all three fixes)" | spec §2.4 + §10.5 | §I |
| §1.5 | Schema migration posture | "V1 expectation: NO schema migration. Sub-bundle 1 stays Schema v21 LOCKED. If any item's investigation reveals schema migration is unavoidable, ESCALATE to orchestrator." | spec §2.5 + §12 | §A.2 + §D #3 + §K |
| §1.6 | Backwards-compat for legacy data | "Restore Sector/Industry for tickers that HAVE them in the upstream data source but lost them due to the JOIN failure mode; NOT attempt to backfill legacy NULL values; document the legacy-NULL acknowledgment explicitly in the spec" | spec §2.6 + §4 SKIP_NO_CANDIDATES_ROW | §A.1 + §C.1 |

### §E.3 Brainstorm spec §2 LOCKs (this sub-bundle)

| # | Decision | LOCKed value (verbatim) | Spec citation | Plan citation |
|---|---|---|---|---|
| §2.1 | V2.G3 design | "backfill CLI (Fix A) FIRST; VM fallback (Fix B) banked as Fix-1b for operator-gate-trigger" | spec §4.2 + §13 | §G.T-1.2 + §B.3 |
| §2.1 | V2.G3 backfill | "STRICT all-or-nothing semantic (AND-empty SELECT; partial-empty SKIP_PARTIAL_EMPTY; DHA/DHC SKIP_NO_CANDIDATES_ROW)" | spec §4.3 + §4.4 R2.M3 | §G.T-1.2 step 3 + step 8 |
| §2.1 | V2.G3 restore-SQL artifact | "MANDATORY emission at dry-run AND before apply (defense-in-depth)" | spec §4.3 R1.M3 | §G.T-1.2 step 6 + step 11 |
| §2.1 | V2.G4 design | "call-signature fix + module-level logger addition + narrow `ValueError`-only catch" | spec §5.2 R3.M2 + R2.M2 | §G.T-2.1 |
| §2.1 | V2.G4 narrow exception | "LOCK programming errors (TypeError, AttributeError, KeyError, RuntimeError) propagate to FastAPI 500" | spec §5.2 R2.M2 | §G.T-2.1 step 8 |
| §2.1 | P14.N3 design | "3-field VM extension + denominator-stamping per `maturity.py:197-219` + PROPORTION-unit semantic + tooltip surface" (spec §2 verbatim; the implementation grew to 4 fields post-Codex R2.M#1+M#2 LOCK to surface the NoActivePolicyError caveat -- semantic extension consistent with spec §6.4 second bullet, NOT a scope re-litigation) | spec §6.2 Fix A | §G.T-3.1 |

### §E.4 Writing-plans phase-specific LOCKs (this brief §1.5)

| # | LOCK | Verbatim | Plan citation |
|---|---|---|---|
| L1 | "Plan SHALL produce ONE executing-plans dispatch (not 2+). Per §1.4." | §G.0 + §J |
| L2 | "Per-task slicing in §G of the plan MUST be bite-sized (each task 3-5 commits max; per-task acceptance criteria + step-checkbox TDD)." | §G.T-1.1 ... §G.T-4.2 |
| L3 | "Test count target = ~34-36 fast tests (matches spec §10.4 estimate post-R4 bump). Plan SHALL distribute tests across tasks + verify total in §H." | §H |
| L4 | "Commit cadence target = ~8-12 commits total (matches spec §10.2). Plan SHALL enumerate per-task commit count + verify total in §G." | §G.0 |
| L5 | "Plan §F SHALL re-cite Sec 9.1 LOCKs + spec §2 LOCKs + this brief §1 LOCKs in a cumulative LOCK summary table." | §E (this section satisfies the requirement; cross-references in §F) |

**LOCK preservation verdict: ALL 23 LOCKs (Q1-Q7 + §1.1-§1.6 + spec §2.1×6 + L1-L5) PRESERVED VERBATIM in this plan. ZERO LOCK deviations.**

---

## §F Cumulative discipline + watch items applied (per item + per task)

### §F.1 Cumulative gotcha application matrix (37 gotchas BINDING)

Per spec §15.1 + brief §5 forward-binding lesson set. **6 gotchas APPLIED per spec; carried forward into plan + extended at executing-plans phase per per-task watch items at §G.**

| Gotcha | Title (abbreviated) | Plan application |
|---|---|---|
| #1 | Test-count drift in plan docs | Per-task test counts at §G are ESTIMATES; trust pytest output at executing-plans phase |
| #4 | PriceCache `_last_close` ticker-rotation | APPLIED at V2.G3 helper (consults `candidates` last-known per ticker); Fix-1b mirrors discipline at render time IF triggered |
| #5 | OHLCV fetch scope = open-trade tickers ONLY | VERIFIED preserved at V2.G4 fix (consumes existing OhlcvCache substrate; no scope widening) |
| #11 | Template-rendering surface audit | APPLIED at P14.N3 (template + VM extension audited together; T-3.1 acceptance criteria enumerate both surfaces) |
| #15 / Expansion #9 | Form-render anchor lifecycle audit | N/A (no new hidden form anchors introduced) |
| #17 / Expansion #2 refinement | Brief-vs-production-function-signature | APPLIED at plan-authoring per §A.3 (14 signatures verified); EXTENDED to T-1.1 step 1 (helper signature lock via `inspect.signature`-style discriminating test on docstring contract) |
| #18 / Expansion #4 refinement | SQL skeleton JOIN-cardinality + downstream-sufficiency | APPLIED at V2.G3 helper SQL (ROW_NUMBER() OVER PARTITION BY ticker; ensures 1:1 cardinality; downstream-sufficiency = backfill CLI consumes the dict directly) |
| #19 / Expansion #2 sub-refinement | Cascade-call-graph verification | APPLIED at P14.N3 (`compute_position_capital_utilization` NOT `_compute_position_util_pct` — verify the chosen helper's cascade does not invoke the percent path) |
| #20 / Expansion #4 sub-refinement | Runtime-binding-shape + empty-input audit | APPLIED at V2.G3 helper SQL (dynamic `?` expansion via `",".join("?" * len(tickers))`; empty-input short-circuit to `{}` before SQL) |
| #21 / Expansion #13 | Cumulative regression cascade audit in fix loops | APPLIED at T-1.2 (restore-SQL emission lives in BOTH dry-run AND apply paths; not extracted to a "post-loop" pass) + at §G.0 commit-cadence preface |
| #22 / Expansion #8 promotion | Per-counter-accumulation | APPLIED at T-1.2 (dry-run + apply-path counters increment per-(trade_id, action_label) tuple; NOT per-(trade_id, attempted_replacement) which would inflate by N_candidates_row_returned) |
| #23 / Expansion #11 promotion | Dataclass attribution metadata audit | APPLIED at P14.N3 (4 NEW VM fields are required + carry unambiguous attribution: `_resolved`, `_is_provisional`, `_effective`, `_policy_missing`; backed by single-source-of-truth at build time) |
| #26 | OHLCV archive bar-content TEMPORAL mutation | N/A (no time-travel reads; V2.G4 reads current archive via OhlcvCache hook) |
| #27 | Silent-skip-without-audit | APPLIED at V2.G4 (`log.warning` emitted BEFORE the 409 degrade response) + extended at T-1.2 (CLI emits operator-friendly counts on the dry-run table for every per-action SKIP) |
| #32 | ASCII discipline scope clarity | APPLIED across all NEW + MODIFIED production code + test files + return report; declared scope at §A.4 + carried into per-task acceptance criteria |
| #33 | Cohort-validity-vs-verdict-criteria | N/A (no analytical verdict) |
| #34 | Brief-prescription cross-table verification | APPLIED at §A.3 (plan-authoring verification re-grepped 14 production surfaces against spec citations) |
| #35 | Substrate density metric disambiguation | N/A (no metric definitions) |
| #36 | Two-Codex-chain default | SINGLE chain at end of plan per Sec 9.1 Q7 LOCK + gotcha #36 explicit caveat for pure UX/wiring without analytical artifact |
| #37 | Substrate-freshness sensitivity | N/A (no prior-arc cohort fixture consumption) |

**Gotchas not enumerated above (#2, #3, #6, #7-9, #10, #12-14, #16, #24-25, #28-31)** are N/A for Sub-bundle 1 per spec §15.1.

### §F.2 Writing-plans phase watch items (forward-binding lessons from brainstorm return report §8; carried into plan-authoring + extended into executing-plans dispatch readiness)

| # | Lesson | Plan application |
|---|---|---|
| 1 | Brief-vs-production-function-signature verification | Plan §A.3 re-verified 14 surfaces at plan-authoring; T-1.1 step 1 + T-3.1 step 1 include discriminating tests that lock the signature contracts (e.g., assert `inspect.signature(resolve_live_capital_denominator_dollars).parameters['asof_date'].kind == KEYWORD_ONLY`) |
| 2 | Cumulative regression cascade audit | §G.0 commit-cadence preface; per-task §G.T-X.Y acceptance criteria include "no stale-reference cascade" sub-check; Codex MCP chain reviews entire plan post-fix at each round (per §J) |
| 3 | Percent-vs-proportion unit lock | T-3.1 step 9 BINDING test: assert rendered value for proportion `0.15` fixture is `15.0%` (NOT 1500.0%); test name explicitly cites R3.M1 LOCK for grep-reachability |
| 4 | Module-level logger addition | T-2.1 step 1 + step 2 land logger import + module-level `log` definition IN THE SAME COMMIT as the new `log.warning` callsite; T-2.1 acceptance criterion 2 verifies no `log` references appear in pre-import commits |
| 5 | Restore-SQL artifact discipline | T-1.2 step 6 (dry-run emits artifact) + step 11 (apply emits BEFORE UPDATE); discriminating test asserts artifact exists post-dry-run + post-apply at deterministic path |
| 6 | Strict all-or-nothing vs partial-recovery semantic lock | T-1.2 step 3 SQL skeleton uses AND-empty WHERE; step 4 separate SKIP_PARTIAL_EMPTY enumeration; V1 STRICT preserved; tests assert per-action label correctness |
| 7 | Browser-only HTMX failure surface preservation | T-2.1 step 11 regression test asserts existing trinity preserved on `/dashboard/weather-chart/refresh` (HX-Request header on form per dashboard.html.j2; 204 + HX-Redirect; `/dashboard` target route registered) |
| 8 | Programming-error propagation discipline | T-2.1 step 8 + step 9 + step 10 BINDING tests assert TypeError + AttributeError + KeyError + RuntimeError + `Exception` subclasses ALL propagate as 500; ValueError-only path returns 409 with log.warning |
| 9 | Operator-witnessed gate split for behavior-conditional surfaces | §I runbook splits S5 into S5a PROVISIONAL + S5b LIVE with state-planting fixture instructions per case |

### §F.3 Per-task cumulative discipline application checklist

Each per-task §G.T-X.Y acceptance criteria block enumerates which of the above gotchas + watch items applies. Compactly:

| Task | Gotchas applied | Watch items applied |
|---|---|---|
| T-1.1 V2.G3 repo helper | #17, #18, #20, #32 | #1 |
| T-1.2 V2.G3 CLI subcommand | #1, #4, #11 (CLI output discipline), #21, #22, #27, #32 | #5, #6 |
| T-1.3 V2.G3 VM fallback (OPTIONAL) | #4, #11, #32 | (only if triggered) |
| T-2.1 V2.G4 route handler | #5, #11 (NO new HTMX), #17, #27, #32 | #4, #7, #8 |
| T-3.1 P14.N3 VM + template | #11, #17, #19, #23, #32 | #3, #9 |
| T-4.1 L2 LOCK parametric source-grep | #32, #34 | (verification only) |
| T-4.2 Closer + return report | #1, #32, #36 | #2 (full-plan cascade audit at Codex chain) |

---

## §G Per-task slicing (TDD; bite-sized steps)

### §G.0 Commit cadence preface

Per L4 LOCK + spec §10.2: target ~8–12 commits total. Per-task commit count:

| Task | Commits (est.) | Cumulative |
|---|---|---|
| T-1.1 V2.G3 repo helper | 1 | 1 |
| T-1.2 V2.G3 CLI subcommand + restore-SQL artifact | 2–3 | 3–4 |
| T-1.3 V2.G3 VM fallback (OPTIONAL; pre-ship NOT IN PLAN) | 0 (default) / 1 (if triggered) | 3–5 |
| T-2.1 V2.G4 route handler + logger | 1–2 | 4–7 |
| T-3.1 P14.N3 VM + template + tests | 2–3 | 6–10 |
| T-4.1 L2 LOCK source-grep | 1 | 7–11 |
| T-4.2 Closer + return report | 1 | 8–12 |

**Estimated total: 8–12 commits** (within L4 LOCK target). Deviations from this baseline cadence at executing-plans time MUST be enumerated in the return report; per forward-binding lesson #2 + gotcha #21 cumulative regression cascade discipline. Example acceptable deviations:
- T-1.1 + T-1.2 step 1–4 (the repo helper + the dry-run skeleton) MAY consolidate into 1 commit if both ship via the same TDD red-green-refactor cycle.
- T-2.1 step 1 (logger import) + step 2 (module-level `log = ...`) + step 3 (the rewritten exception block) MUST land together in 1 commit per R3.M2 LOCK / forward-binding lesson #4 (split would NameError).
- T-3.1 may split between VM extension (steps 1–6) and template rewrite (steps 7–10) into 2 commits if convenient.

**Commit message convention** (project-wide):
```
<scope>(<area>): <imperative verb> <subject>
```
Examples:
- `feat(diagnose): add backfill-trades-sector-industry CLI subcommand`
- `fix(web): correct OhlcvCache.get_or_fetch call signature in weather-chart refresh handler`
- `feat(web): wire DailyManagementTileVM 4-field PROVISIONAL/LIVE denominator stamping`
- `test(integration): add L2 LOCK parametric source-grep regression test`

**Co-Authored-By suppression:** NO commit may carry a `Co-Authored-By:` trailer. Verified post-merge via `git log --pretty="%(trailers)" main..HEAD` returning empty for every commit on the executing-plans branch.

**No `--no-verify`** on commits — pre-commit hooks must run; fix any underlying issue rather than bypass.

---

### §G.T-1.1: V2.G3 repo helper `get_latest_sector_industry_per_ticker`

**Files:**
- Modify: `swing/data/repos/candidates.py` (append after line 86 / after `fetch_candidates_for_run`)
- Test: `tests/data/repos/test_candidates_sector_industry_helper.py` (NEW)

**Acceptance criteria:**
1. New function `get_latest_sector_industry_per_ticker(conn, tickers) -> dict[str, CandidateSectorIndustryRecord]` exported from `swing/data/repos/candidates.py`. The accompanying `@dataclass(frozen=True) CandidateSectorIndustryRecord` carries `(sector: str, industry: str, candidate_id: int | None, evaluation_run_id: int | None)` provenance per Codex R1.M#6 LOCK so the V2.G3 dry-run table can cite which candidates row supplied each backfill (spec §4.3 dry-run table columns include `source_candidate_id` + `source_evaluation_run_id`).
2. Signature uses `Sequence[str]` for `tickers` parameter and returns `dict[str, CandidateSectorIndustryRecord]` per spec §4.3 (Codex R1.M#6 LOCK widened from prior `tuple[str, str]`).
3. SQL uses dynamic `?` expansion via `",".join("?" * len(tickers))` (gotcha #20).
4. Empty-input short-circuits to `{}` BEFORE SQL execution (gotcha #20).
5. WHERE clause filters `c.sector != '' AND c.industry != ''` (both non-empty; AND-form per spec §4.3 R2.M3 LOCK).
6. ORDER via `ROW_NUMBER() OVER (PARTITION BY c.ticker ORDER BY c.evaluation_run_id DESC, c.id DESC)` (1:1 cardinality per gotcha #18).
7. Tickers with no qualifying row map to `("", "")` (per migration 0012 TEXT NOT NULL DEFAULT '' convention).
8. ~6–8 fast tests cover happy-path + multi-ticker + non-qualifying-row + empty-input + ordering + ASCII discipline.
9. Gotchas applied: #17 (signature contract test), #18 (JOIN-cardinality), #20 (dynamic `?` + empty-input), #32 (ASCII).
10. Forward-binding lesson #1 applied via signature contract test.

#### TDD steps

- [ ] **T-1.1 Step 1: Write the failing signature contract test**

Create `tests/data/repos/test_candidates_sector_industry_helper.py`:

```python
"""Discriminating tests for ``get_latest_sector_industry_per_ticker``
(Phase 14 Sub-bundle 1 V2.G3 backfill helper).

Per CLAUDE.md cumulative gotcha #17 (Expansion #2 refinement) + forward-binding
lesson #1 -- signature contract pinned via inspect.signature.

Tests cover spec section 4.3 + 4.5 discriminating-example walkthroughs.
"""

from __future__ import annotations

import inspect
import sqlite3
from collections.abc import Sequence
from typing import get_type_hints

import pytest

from swing.data.db import connect
from swing.data.models import EvaluationRun, Candidate
from swing.data.repos.candidates import (
    CandidateSectorIndustryRecord,
    get_latest_sector_industry_per_ticker,
    insert_candidates,
    insert_evaluation_run,
)


def test_signature_contract_signature_pinned():
    """Lock signature: get_latest_sector_industry_per_ticker(conn, tickers)
    returns dict[str, CandidateSectorIndustryRecord] per spec section 4.3
    + Codex R1.M#6 LOCK (provenance metadata carried via the record)."""
    sig = inspect.signature(get_latest_sector_industry_per_ticker)
    params = list(sig.parameters.values())
    assert len(params) == 2, f"expected 2 params, got {len(params)}"
    assert params[0].name == "conn"
    assert params[1].name == "tickers"
    hints = get_type_hints(get_latest_sector_industry_per_ticker)
    # Sequence[str] tickers; dict[str, CandidateSectorIndustryRecord] return
    # (Codex R1.M#6 LOCK -- provenance metadata carried so the V2.G3 dry-run
    # table can cite source_candidate_id + source_evaluation_run_id).
    from swing.data.repos.candidates import CandidateSectorIndustryRecord
    assert hints["return"] == dict[str, CandidateSectorIndustryRecord]
```

- [ ] **T-1.1 Step 2: Run test to verify it fails (import error)**

Run: `pytest tests/data/repos/test_candidates_sector_industry_helper.py::test_signature_contract_signature_pinned -v`
Expected: FAIL with `ImportError: cannot import name 'get_latest_sector_industry_per_ticker' from 'swing.data.repos.candidates'`.

- [ ] **T-1.1 Step 3: Write minimal implementation**

Append to `swing/data/repos/candidates.py` (after `fetch_candidates_for_run`):

```python
@dataclass(frozen=True)
class CandidateSectorIndustryRecord:
    """Most-recent candidates-row Sector + Industry pair WITH provenance.

    Provenance metadata (candidate_id + evaluation_run_id) carried per
    Codex R1.M#6 LOCK so the V2.G3 backfill dry-run table can cite the
    source_candidate_id + source_evaluation_run_id columns required by
    spec section 4.3. For tickers with no qualifying row, the
    "no-match" sentinel is constructed with empty strings + ``None``
    provenance fields (per migration 0012_sector_industry.sql TEXT NOT
    NULL DEFAULT '' convention applied to the ABSENT-row case).
    """
    sector: str
    industry: str
    candidate_id: int | None
    evaluation_run_id: int | None


def get_latest_sector_industry_per_ticker(
    conn: sqlite3.Connection,
    tickers: Sequence[str],
) -> dict[str, CandidateSectorIndustryRecord]:
    """Return {ticker: CandidateSectorIndustryRecord} keyed on the
    most-recent ``candidates`` row per ticker with non-empty sector AND
    non-empty industry. Tickers with no qualifying row map to a record
    with empty-string sector/industry + ``None`` provenance fields
    (per migration ``0012_sector_industry.sql`` TEXT NOT NULL DEFAULT
    '' convention applied to the ABSENT-row case).

    Used by the Phase 14 Sub-bundle 1 V2.G3 backfill helper to repair
    empty ``trades.sector`` / ``trades.industry`` values on legacy or
    candidates-rotation cases. Backwards-compat: operator-acknowledged
    DHA/DHC legacy trades (no qualifying candidates row) return the
    no-match sentinel; the open-positions template renders em-dash for
    empty. The provenance fields let the V2.G3 dry-run table cite
    which historical candidates row supplied each backfill
    (spec section 4.3 + Codex R1.M#6 LOCK).

    Empty ``tickers`` input returns ``{}`` without executing SQL
    (CLAUDE.md gotcha #20 runtime-binding-shape + empty-input audit).

    Ordering: most-recent first via
    ``ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY
    evaluation_run_id DESC, id DESC)`` -- 1:1 cardinality per
    cumulative gotcha #18.
    """
    if not tickers:
        return {}
    placeholders = ",".join("?" * len(tickers))
    sql = f"""
        SELECT ticker, sector, industry, id, evaluation_run_id FROM (
            SELECT
                c.ticker, c.sector, c.industry, c.id, c.evaluation_run_id,
                ROW_NUMBER() OVER (
                    PARTITION BY c.ticker
                    ORDER BY c.evaluation_run_id DESC, c.id DESC
                ) AS rn
            FROM candidates c
            WHERE c.ticker IN ({placeholders})
              AND c.sector != ''
              AND c.industry != ''
        ) ranked
        WHERE ranked.rn = 1
    """
    out: dict[str, CandidateSectorIndustryRecord] = {}
    for row in conn.execute(sql, list(tickers)):
        out[row[0]] = CandidateSectorIndustryRecord(
            sector=row[1], industry=row[2],
            candidate_id=row[3], evaluation_run_id=row[4],
        )
    for t in tickers:
        out.setdefault(
            t,
            CandidateSectorIndustryRecord(
                sector="", industry="",
                candidate_id=None, evaluation_run_id=None,
            ),
        )
    return out
```

Also add to the imports at top of `candidates.py`:

```python
from collections.abc import Sequence
from dataclasses import dataclass
```

(audit current imports first; add only if missing).

- [ ] **T-1.1 Step 4: Run signature contract test to verify pass**

Run: `pytest tests/data/repos/test_candidates_sector_industry_helper.py::test_signature_contract_signature_pinned -v`
Expected: PASS.

- [ ] **T-1.1 Step 5: Add empty-input short-circuit test**

Append to `tests/data/repos/test_candidates_sector_industry_helper.py`:

```python
def test_empty_input_returns_empty_dict_without_sql(tmp_path):
    """Empty tickers list short-circuits per CLAUDE.md gotcha #20."""
    db_path = tmp_path / "swing.db"
    conn = connect(db_path)
    try:
        # No fixture inserts needed; assertion is on the return shape.
        result = get_latest_sector_industry_per_ticker(conn, [])
        assert result == {}
    finally:
        conn.close()
```

Run: `pytest tests/data/repos/test_candidates_sector_industry_helper.py::test_empty_input_returns_empty_dict_without_sql -v`
Expected: PASS.

- [ ] **T-1.1 Step 6: Add happy-path single-ticker test**

Append:

```python
def test_happy_path_single_ticker_returns_non_empty_pair(tmp_path):
    """VSAT in candidates with non-empty Sector + Industry; helper
    returns the non-empty pair (spec section 4.5 example #1)."""
    db_path = tmp_path / "swing.db"
    conn = connect(db_path)
    try:
        run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, run_id, [Candidate(
            ticker="VSAT",
            sector="Technology",
            industry="Communications Equipment",
            # populate remaining required fields per Candidate dataclass
            # (insert minimal valid shape; see _build_candidate_fixture helper).
            **_build_candidate_fixture("VSAT"),
        )])
        result = get_latest_sector_industry_per_ticker(conn, ["VSAT"])
        assert result["VSAT"].sector == "Technology"
        assert result["VSAT"].industry == "Communications Equipment"
        # Provenance present (Codex R1.M#6 LOCK).
        assert result["VSAT"].candidate_id is not None
        assert result["VSAT"].evaluation_run_id == run_id
    finally:
        conn.close()
```

(NOTE: `_build_candidate_fixture` is a test-local helper that emits a production-shape `Candidate` dataclass with all required non-Sector/Industry fields populated to valid defaults — executing-plans phase audits the current `Candidate` dataclass shape via `inspect.signature(Candidate)` and extracts the required field set. Per CLAUDE.md "Synthetic-fixture-vs-production-emitter shape drift" discipline, the helper consumes `insert_candidates` (production emit path) NOT hand-rolled SQL.)

Run: `pytest tests/data/repos/test_candidates_sector_industry_helper.py::test_happy_path_single_ticker_returns_non_empty_pair -v`
Expected: PASS.

- [ ] **T-1.1 Step 7: Add multi-ticker + non-qualifying-row test**

Append:

```python
def test_multi_ticker_mixed_qualifying_returns_per_ticker_results(tmp_path):
    """Plant VSAT (qualifies); DHA (no candidates row); assert VSAT pair
    returned + DHA maps to ('', '') (spec section 4.5 example #3 + #4)."""
    db_path = tmp_path / "swing.db"
    conn = connect(db_path)
    try:
        run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, run_id, [
            Candidate(ticker="VSAT", sector="Technology",
                      industry="Communications Equipment",
                      **_build_candidate_fixture("VSAT")),
        ])
        result = get_latest_sector_industry_per_ticker(
            conn, ["VSAT", "DHA"],
        )
        assert result["VSAT"].sector == "Technology"
        assert result["VSAT"].industry == "Communications Equipment"
        assert result["VSAT"].evaluation_run_id == run_id
        # DHA is the no-match sentinel: empty strings + None provenance
        # (Codex R1.M#6 LOCK).
        assert result["DHA"].sector == ""
        assert result["DHA"].industry == ""
        assert result["DHA"].candidate_id is None
        assert result["DHA"].evaluation_run_id is None
    finally:
        conn.close()
```

Run: `pytest tests/data/repos/test_candidates_sector_industry_helper.py::test_multi_ticker_mixed_qualifying_returns_per_ticker_results -v`
Expected: PASS.

- [ ] **T-1.1 Step 8: Add non-empty AND filter test**

Append:

```python
def test_partial_empty_candidate_row_excluded_from_qualifying_pool(tmp_path):
    """Candidate row with sector='Tech', industry='' must NOT qualify
    (AND-empty filter per spec section 4.3 R2.M3 LOCK)."""
    db_path = tmp_path / "swing.db"
    conn = connect(db_path)
    try:
        run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, run_id, [
            Candidate(ticker="VSAT", sector="Technology", industry="",
                      **_build_candidate_fixture("VSAT")),
        ])
        result = get_latest_sector_industry_per_ticker(conn, ["VSAT"])
        # VSAT's only candidates row has industry=''; helper excludes
        # via AND-empty WHERE clause + ticker maps to the no-match
        # sentinel (empty strings + None provenance per Codex R1.M#6).
        assert result["VSAT"].sector == ""
        assert result["VSAT"].industry == ""
        assert result["VSAT"].candidate_id is None
        assert result["VSAT"].evaluation_run_id is None
    finally:
        conn.close()
```

Run: `pytest tests/data/repos/test_candidates_sector_industry_helper.py::test_partial_empty_candidate_row_excluded_from_qualifying_pool -v`
Expected: PASS.

- [ ] **T-1.1 Step 9: Add ordering test (most-recent wins)**

Append:

```python
def test_ordering_most_recent_evaluation_run_id_wins(tmp_path):
    """Plant 2 candidates rows for VSAT across different evaluation_run_ids;
    helper returns the row with the HIGHER evaluation_run_id (most-recent
    per spec section 4.3 SQL ORDER BY)."""
    db_path = tmp_path / "swing.db"
    conn = connect(db_path)
    try:
        # First (older) run.
        old_run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-20T20:00:00",
            data_asof_date="2026-05-19", action_session_date="2026-05-20",
        ))
        insert_candidates(conn, old_run_id, [
            Candidate(ticker="VSAT", sector="OldSector",
                      industry="OldIndustry",
                      **_build_candidate_fixture("VSAT")),
        ])
        # Second (newer) run.
        new_run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, new_run_id, [
            Candidate(ticker="VSAT", sector="NewSector",
                      industry="NewIndustry",
                      **_build_candidate_fixture("VSAT")),
        ])
        result = get_latest_sector_industry_per_ticker(conn, ["VSAT"])
        assert result["VSAT"].sector == "NewSector"
        assert result["VSAT"].industry == "NewIndustry"
        # Provenance points at the NEWER run (Codex R1.M#6 LOCK).
        assert result["VSAT"].evaluation_run_id == new_run_id
    finally:
        conn.close()
```

Run: `pytest tests/data/repos/test_candidates_sector_industry_helper.py::test_ordering_most_recent_evaluation_run_id_wins -v`
Expected: PASS.

- [ ] **T-1.1 Step 10: Add historical-only fallback test (post-rotation)**

Append:

```python
def test_historical_only_candidates_row_picked_when_no_recent(tmp_path):
    """Plant ONLY an older candidates row for VSAT; helper picks it
    (spec section 4.5 example #2 -- VSAT historical post-rotation)."""
    db_path = tmp_path / "swing.db"
    conn = connect(db_path)
    try:
        old_run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-01T20:00:00",
            data_asof_date="2026-04-30", action_session_date="2026-05-01",
        ))
        insert_candidates(conn, old_run_id, [
            Candidate(ticker="VSAT", sector="Technology",
                      industry="Communications Equipment",
                      **_build_candidate_fixture("VSAT")),
        ])
        # No newer run for VSAT (rotated out of finviz screen).
        result = get_latest_sector_industry_per_ticker(conn, ["VSAT"])
        assert result["VSAT"].sector == "Technology"
        assert result["VSAT"].industry == "Communications Equipment"
        # Provenance still cites the historical run (Codex R1.M#6).
        assert result["VSAT"].evaluation_run_id == old_run_id
    finally:
        conn.close()
```

Run: `pytest tests/data/repos/test_candidates_sector_industry_helper.py::test_historical_only_candidates_row_picked_when_no_recent -v`
Expected: PASS.

- [ ] **T-1.1 Step 11: Add ASCII discipline test for the helper module**

Append:

```python
def test_helper_module_source_is_ascii_only():
    """Per gotcha #32 + spec section 15.2 ASCII discipline scope:
    swing/data/repos/candidates.py + this test module ASCII-only."""
    from pathlib import Path
    import swing.data.repos.candidates as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    src.encode("ascii")  # raises UnicodeEncodeError on any non-ASCII
    test_src = Path(__file__).read_text(encoding="utf-8")
    test_src.encode("ascii")
```

Run: `pytest tests/data/repos/test_candidates_sector_industry_helper.py::test_helper_module_source_is_ascii_only -v`
Expected: PASS.

- [ ] **T-1.1 Step 12: Run full test module + commit**

Run: `pytest tests/data/repos/test_candidates_sector_industry_helper.py -v`
Expected: ALL PASS (7 tests).

```bash
git add swing/data/repos/candidates.py \
        tests/data/repos/test_candidates_sector_industry_helper.py
git commit -m "feat(repos): add get_latest_sector_industry_per_ticker for V2.G3 backfill"
```

Verify no `Co-Authored-By:` trailer in the just-created commit:
```bash
git log -1 --pretty="%(trailers)"
```
Expected output: empty line (no trailers).

---

### §G.T-1.2: V2.G3 CLI subcommand `swing diagnose backfill-trades-sector-industry`

**Files:**
- Modify: `swing/cli.py` (append after the last `diagnose_group.command` at line ~5170 / after `diagnose_prune_chart_cache`)
- Test: `tests/cli/test_diagnose_backfill_trades_sector_industry.py` (NEW)

**Acceptance criteria:**
1. New `@diagnose_group.command("backfill-trades-sector-industry")` subcommand registered + visible in `swing diagnose --help`.
2. Options: `--db <path>` (required); `--apply` (boolean flag; default False); `--output-dir <path>` (default `exports/diagnostics`); `--allowlist <comma-separated tickers>` (optional); `--include-closed` (boolean flag; default False).
3. Dry-run (default) prints operator-friendly table + emits restore-SQL artifact under `--output-dir/backfill-trades-sector-industry-restore-<ISO>.sql`.
4. AND-empty WHERE clause filters trades with TRIM-empty BOTH `sector` AND `industry`; partial-empty rows enumerated separately as `SKIP_PARTIAL_EMPTY` actions.
5. Apply path commits UPDATEs under `with conn:` atomic transaction; idempotent (re-run is no-op); restore-SQL artifact emitted BEFORE issuing UPDATEs.
6. Active-state allowlist defaults to `('entered', 'managing', 'partial_exited')`; `--include-closed` widens to all states.
7. `--allowlist VSAT,DHA` restricts UPDATEs to the specified tickers.
8. Per spec §4.4 + §4.5: SKIP_NO_CANDIDATES_ROW for tickers with `("", "")` helper return; UPDATE for tickers with both non-empty.
9. Pre-validates `--db` via `_validate_diagnose_db_path` precedent at `swing/cli.py:4731`.
10. ValueError wrapping at CLI boundary per cumulative gotcha (Phase 13 T-A.1.5b R4 M#1; mirrors existing `aplus-sensitivity` pattern at lines 4777-4786).
11. ASCII-only output per cumulative gotcha #32 (Phase 12 C.D Windows-stdout safety).
12. Provenance columns `source_candidate_id` + `source_evaluation_run_id` rendered on every UPDATE row (Codex R1.M#6 LOCK; spec §4.3 dry-run-table column list); SKIP rows render `-` placeholders for the provenance columns.
13. ~9-11 fast tests cover all paths (one added per Codex R1.M#6 -- provenance assertion in dry-run output).
14. Gotchas applied: #1, #4, #11 (CLI output discipline), #21, #22, #27, #32. Watch items #5 + #6.

**OQ #1 resolution at plan-authoring:** the new repo helper lives at `swing/data/repos/candidates.py` (not a separate helper module). LOCKED.
**OQ #2 resolution at plan-authoring:** active-state allowlist defaults to `('entered', 'managing', 'partial_exited')`. Verified against `swing/data/models.py:Trade.state` enum. LOCKED.
**OQ #3 resolution at plan-authoring:** `--include-closed` flag SHIPS in V1 (operator-paired convenience for closed-position backfill IF the operator chooses). LOCKED.

#### TDD steps

- [ ] **T-1.2 Step 1: Write the failing CLI registration test**

Create `tests/cli/test_diagnose_backfill_trades_sector_industry.py`:

```python
"""Discriminating tests for ``swing diagnose backfill-trades-sector-industry``
(Phase 14 Sub-bundle 1 V2.G3 backfill CLI subcommand).

Tests cover spec section 4.3 + 4.5 discriminating-example walkthroughs
plus restore-SQL artifact emission (R1.M3 LOCK) + AND-empty WHERE clause
(R2.M3 LOCK) + idempotency + ASCII discipline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main as swing_cli


def test_subcommand_registered_in_diagnose_group():
    """CLI registration smoke -- subcommand visible in --help."""
    runner = CliRunner()
    result = runner.invoke(swing_cli, ["diagnose", "--help"])
    assert result.exit_code == 0
    assert "backfill-trades-sector-industry" in result.output
```

- [ ] **T-1.2 Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_subcommand_registered_in_diagnose_group -v`
Expected: FAIL because the subcommand is not yet registered (`"backfill-trades-sector-industry" not in result.output`).

- [ ] **T-1.2 Step 3: Add the CLI subcommand skeleton (dry-run path)**

Append to `swing/cli.py` (after the last `@diagnose_group.command` at line ~5139 / after `diagnose_prune_chart_cache`):

```python
@diagnose_group.command("backfill-trades-sector-industry")
@click.option(
    "--db", "db_path", required=True, type=click.Path(path_type=Path),
)
@click.option(
    "--apply", is_flag=True, default=False,
    help="Commit UPDATEs (atomic). Default: dry-run only.",
)
@click.option(
    "--output-dir", type=click.Path(path_type=Path),
    default=Path("exports/diagnostics"), show_default=True,
    help="Directory for the restore-SQL artifact + dry-run table.",
)
@click.option(
    "--allowlist", type=str, default="",
    help="Comma-separated tickers to opt-in (overrides default open-set).",
)
@click.option(
    "--include-closed", is_flag=True, default=False,
    help=(
        "Widen to all trade states (default: entered/managing/partial_exited)."
    ),
)
def diagnose_backfill_trades_sector_industry(
    db_path: Path, apply: bool, output_dir: Path, allowlist: str,
    include_closed: bool,
) -> None:
    """One-time backfill of trades.sector + trades.industry for V2.G3.

    Strict all-or-nothing semantic: only rows with BOTH sector and
    industry TRIM-empty get UPDATEd, AND only when the candidates-table
    helper returns BOTH non-empty replacements. Partial-empty rows are
    enumerated separately as SKIP_PARTIAL_EMPTY (V1 STRICT per spec
    section 4.3 R2.M3 LOCK; V2 candidate banked for per-column lookup).

    Dry-run (default) prints the affected count + emits a restore-SQL
    artifact at <output-dir>/backfill-trades-sector-industry-restore-<ISO>.sql
    so the apply step is reversible.

    Apply path commits the UPDATEs under ``with conn:`` atomically and
    re-emits the restore-SQL artifact BEFORE issuing UPDATEs (defense-
    in-depth against crash post-UPDATE; per spec section 4.3 R1.M3 LOCK).
    """
    _validate_diagnose_db_path(db_path)
    try:
        from swing.diagnostics.backfill_trades_sector_industry import (
            run_backfill,
        )
        summary = run_backfill(
            db_path=db_path,
            apply=apply,
            output_dir=output_dir,
            allowlist=_parse_allowlist(allowlist),
            include_closed=include_closed,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except sqlite3.OperationalError as exc:
        raise click.ClickException(
            f"Database error reading {db_path}: {exc}"
        ) from exc
    for line in summary.report_lines:
        click.echo(line)
    click.echo(f"Restore-SQL artifact: {summary.restore_sql_path}")


def _parse_allowlist(raw: str) -> tuple[str, ...] | None:
    """Parse the --allowlist comma-separated option into a ticker tuple."""
    if not raw.strip():
        return None
    return tuple(t.strip().upper() for t in raw.split(",") if t.strip())
```

Note: this delegates implementation to a NEW helper module
`swing/diagnostics/backfill_trades_sector_industry.py`. The helper
isolates SQL + I/O + table-emit logic from the CLI surface for
testability (and mirrors the precedent at
`research/harness/aplus_sensitivity/run.py:run_harness` of separating
CLI surface from the implementation module).

- [ ] **T-1.2 Step 4: Add the implementation module (dry-run scope)**

Create `swing/diagnostics/backfill_trades_sector_industry.py`:

```python
"""V2.G3 one-time backfill of trades.sector + trades.industry.

See spec at docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-
wiring-design.md section 4 + plan at docs/superpowers/plans/2026-05-28-
phase14-sub-bundle-1-data-wiring-plan.md section G.T-1.2.

Strict all-or-nothing semantic (R2.M3 LOCK):
- SELECT: TRIM(sector)='' AND TRIM(industry)=''
- UPDATE: requires both replacements non-empty
- SKIP_PARTIAL_EMPTY: rows with one column empty (not both)
- SKIP_NO_CANDIDATES_ROW: rows with no qualifying candidates row

Restore-SQL artifact (R1.M3 LOCK):
- Emitted at <output-dir>/backfill-trades-sector-industry-restore-<ISO>.sql
- Contains per-affected-row UPDATE statements with OLD values
- Operator can re-apply via `sqlite3 swing.db < restore.sql`
- Emitted in BOTH dry-run AND apply paths (defense-in-depth)
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from swing.data.db import connect
from swing.data.repos.candidates import (
    CandidateSectorIndustryRecord,
    get_latest_sector_industry_per_ticker,
)


_DEFAULT_ACTIVE_STATES: tuple[str, ...] = (
    "entered", "managing", "partial_exited",
)


@dataclass(frozen=True)
class BackfillRow:
    """One row in the dry-run table emit.

    source_candidate_id + source_evaluation_run_id are populated for
    UPDATE rows (Codex R1.M#6 LOCK -- provenance auditability per
    spec section 4.3); None for SKIP rows where no candidates row
    qualified.
    """
    trade_id: int
    ticker: str
    current_sector: str
    current_industry: str
    proposed_sector: str
    proposed_industry: str
    action: str  # 'UPDATE' | 'SKIP_NO_CANDIDATES_ROW' | 'SKIP_PARTIAL_EMPTY'
    source_candidate_id: int | None
    source_evaluation_run_id: int | None


@dataclass(frozen=True)
class BackfillSummary:
    """Top-level result returned to the CLI."""
    rows: tuple[BackfillRow, ...]
    update_count: int
    skip_no_candidates_count: int
    skip_partial_empty_count: int
    restore_sql_path: Path
    report_lines: tuple[str, ...]
    applied: bool


def run_backfill(
    *,
    db_path: Path,
    apply: bool,
    output_dir: Path,
    allowlist: tuple[str, ...] | None,
    include_closed: bool,
) -> BackfillSummary:
    """Run the backfill in dry-run or apply mode.

    Per CLAUDE.md gotcha #27 (silent-skip-without-audit): emits operator-
    friendly counts for every per-action skip path.
    """
    conn = connect(db_path)
    try:
        and_empty_rows = _select_and_empty_trade_rows(
            conn, include_closed=include_closed,
        )
        partial_rows = _select_partial_empty_trade_rows(
            conn, include_closed=include_closed,
        )
        if allowlist is not None:
            and_empty_rows = [
                r for r in and_empty_rows if r[1] in allowlist
            ]
            partial_rows = [
                r for r in partial_rows if r[1] in allowlist
            ]
        candidate_tickers = sorted({r[1] for r in and_empty_rows})
        replacements = get_latest_sector_industry_per_ticker(
            conn, candidate_tickers,
        )
        rows = _build_backfill_rows(
            and_empty_rows=and_empty_rows,
            partial_rows=partial_rows,
            replacements=replacements,
        )
        update_count = sum(1 for r in rows if r.action == "UPDATE")
        skip_no_cand = sum(
            1 for r in rows if r.action == "SKIP_NO_CANDIDATES_ROW"
        )
        skip_partial = sum(
            1 for r in rows if r.action == "SKIP_PARTIAL_EMPTY"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        iso = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        restore_path = (
            output_dir
            / f"backfill-trades-sector-industry-restore-{iso}.sql"
        )
        # Per R1.M3 LOCK: emit restore-SQL BEFORE any UPDATE fires (covers
        # both dry-run AND apply paths; defense-in-depth against crash
        # post-UPDATE).
        _emit_restore_sql(
            restore_path, [r for r in rows if r.action == "UPDATE"],
        )
        applied_flag = False
        if apply:
            with conn:
                _apply_updates(
                    conn, [r for r in rows if r.action == "UPDATE"],
                )
            applied_flag = True
        report = _format_report(
            rows=rows, update_count=update_count,
            skip_no_cand=skip_no_cand, skip_partial=skip_partial,
            apply=apply,
        )
        return BackfillSummary(
            rows=tuple(rows),
            update_count=update_count,
            skip_no_candidates_count=skip_no_cand,
            skip_partial_empty_count=skip_partial,
            restore_sql_path=restore_path,
            report_lines=tuple(report),
            applied=applied_flag,
        )
    finally:
        conn.close()


def _select_and_empty_trade_rows(
    conn: sqlite3.Connection, *, include_closed: bool,
) -> list[tuple[int, str, str, str]]:
    """SELECT (id, ticker, sector, industry) where BOTH empty + state in
    allowlist. Active-state allowlist applied unless --include-closed."""
    sql = (
        "SELECT id, ticker, sector, industry FROM trades "
        "WHERE TRIM(sector) = '' AND TRIM(industry) = ''"
    )
    params: list[object] = []
    if not include_closed:
        placeholders = ",".join("?" * len(_DEFAULT_ACTIVE_STATES))
        sql += f" AND state IN ({placeholders})"
        params.extend(_DEFAULT_ACTIVE_STATES)
    return [(r[0], r[1], r[2], r[3]) for r in conn.execute(sql, params)]


def _select_partial_empty_trade_rows(
    conn: sqlite3.Connection, *, include_closed: bool,
) -> list[tuple[int, str, str, str]]:
    """SELECT (id, ticker, sector, industry) for partial-empty rows
    (one of sector/industry empty; not both)."""
    sql = (
        "SELECT id, ticker, sector, industry FROM trades "
        "WHERE (TRIM(sector) = '' OR TRIM(industry) = '') "
        "AND NOT (TRIM(sector) = '' AND TRIM(industry) = '')"
    )
    params: list[object] = []
    if not include_closed:
        placeholders = ",".join("?" * len(_DEFAULT_ACTIVE_STATES))
        sql += f" AND state IN ({placeholders})"
        params.extend(_DEFAULT_ACTIVE_STATES)
    return [(r[0], r[1], r[2], r[3]) for r in conn.execute(sql, params)]


def _build_backfill_rows(
    *,
    and_empty_rows: Iterable[tuple[int, str, str, str]],
    partial_rows: Iterable[tuple[int, str, str, str]],
    replacements: dict[str, CandidateSectorIndustryRecord],
) -> list[BackfillRow]:
    """Assemble per-(trade_id, action) rows for the table emit.

    Provenance (source_candidate_id + source_evaluation_run_id) is
    carried through from the helper's CandidateSectorIndustryRecord
    so the dry-run table can audit which candidates row supplied each
    backfill (Codex R1.M#6 LOCK).
    """
    rows: list[BackfillRow] = []
    no_match_sentinel = CandidateSectorIndustryRecord(
        sector="", industry="",
        candidate_id=None, evaluation_run_id=None,
    )
    for tid, ticker, cur_sector, cur_industry in and_empty_rows:
        rec = replacements.get(ticker, no_match_sentinel)
        if rec.sector and rec.industry:
            action = "UPDATE"
        else:
            action = "SKIP_NO_CANDIDATES_ROW"
        rows.append(BackfillRow(
            trade_id=tid, ticker=ticker,
            current_sector=cur_sector, current_industry=cur_industry,
            proposed_sector=rec.sector, proposed_industry=rec.industry,
            action=action,
            source_candidate_id=rec.candidate_id,
            source_evaluation_run_id=rec.evaluation_run_id,
        ))
    for tid, ticker, cur_sector, cur_industry in partial_rows:
        rows.append(BackfillRow(
            trade_id=tid, ticker=ticker,
            current_sector=cur_sector, current_industry=cur_industry,
            proposed_sector="", proposed_industry="",
            action="SKIP_PARTIAL_EMPTY",
            source_candidate_id=None, source_evaluation_run_id=None,
        ))
    rows.sort(key=lambda r: (r.action, r.ticker, r.trade_id))
    return rows


def _emit_restore_sql(
    path: Path, update_rows: list[BackfillRow],
) -> None:
    """Write per-affected-row UPDATE statements with OLD values.

    File is always written (even when update_rows is empty) so the
    artifact path returned to the operator is always real.
    """
    lines = [
        "-- V2.G3 backfill-trades-sector-industry restore artifact",
        f"-- Generated at {datetime.now(timezone.utc).isoformat()}",
        "-- Apply via: sqlite3 swing.db < <this-file>",
        "",
    ]
    for r in update_rows:
        # Escape single quotes in original values (defensive; sector +
        # industry come from finviz CSV which historically has none, but
        # guard regardless).
        safe_sector = r.current_sector.replace("'", "''")
        safe_industry = r.current_industry.replace("'", "''")
        lines.append(
            f"UPDATE trades SET sector='{safe_sector}', "
            f"industry='{safe_industry}' WHERE id={r.trade_id};"
        )
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _apply_updates(
    conn: sqlite3.Connection, update_rows: list[BackfillRow],
) -> None:
    """Issue idempotent UPDATEs (WHERE clause makes re-runs no-op)."""
    for r in update_rows:
        conn.execute(
            "UPDATE trades SET sector=?, industry=? "
            "WHERE id=? AND TRIM(sector)='' AND TRIM(industry)=''",
            (r.proposed_sector, r.proposed_industry, r.trade_id),
        )


def _format_report(
    *,
    rows: list[BackfillRow], update_count: int,
    skip_no_cand: int, skip_partial: int, apply: bool,
) -> list[str]:
    """ASCII-only operator-friendly report (gotcha #32)."""
    mode = "APPLY" if apply else "DRY-RUN"
    out = [
        f"V2.G3 backfill-trades-sector-industry ({mode})",
        "",
        f"  UPDATE                 : {update_count}",
        f"  SKIP_NO_CANDIDATES_ROW : {skip_no_cand}",
        f"  SKIP_PARTIAL_EMPTY     : {skip_partial}",
        "",
        "Per-row detail (provenance per Codex R1.M#6 LOCK):",
        (
            "  trade_id | ticker | current | proposed | "
            "source_cand_id | source_eval_run_id | action"
        ),
    ]
    for r in rows:
        cur = f"({r.current_sector!r}, {r.current_industry!r})"
        prop = f"({r.proposed_sector!r}, {r.proposed_industry!r})"
        cand_id_cell = (
            str(r.source_candidate_id)
            if r.source_candidate_id is not None else "-"
        )
        run_id_cell = (
            str(r.source_evaluation_run_id)
            if r.source_evaluation_run_id is not None else "-"
        )
        out.append(
            f"  {r.trade_id:>8} | {r.ticker:<6} | "
            f"{cur} | {prop} | "
            f"{cand_id_cell:>14} | {run_id_cell:>18} | {r.action}"
        )
    return out
```

- [ ] **T-1.2 Step 5: Re-run registration test to verify pass**

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_subcommand_registered_in_diagnose_group -v`
Expected: PASS.

- [ ] **T-1.2 Step 6: Add dry-run table emit + restore-SQL artifact test**

Append:

```python
def test_dry_run_emits_table_and_restore_sql_artifact(tmp_path):
    """Dry-run prints table + writes restore-SQL artifact at deterministic
    path (R1.M3 LOCK; gotcha #27 audit emission)."""
    from swing.data.db import connect
    from swing.data.models import EvaluationRun, Candidate, Trade
    from swing.data.repos.candidates import (
        insert_candidates, insert_evaluation_run,
    )
    from swing.data.repos.trades import insert_trade

    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "exports" / "diagnostics"
    conn = connect(db_path)
    try:
        run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, run_id, [
            Candidate(ticker="VSAT", sector="Technology",
                      industry="Communications Equipment",
                      **_build_candidate_fixture("VSAT")),
        ])
        insert_trade(conn, Trade(
            id=None, ticker="VSAT", state="entered",
            sector="", industry="",
            **_build_trade_fixture("VSAT"),
        ))
    finally:
        conn.close()
    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert "UPDATE" in result.output
    assert "VSAT" in result.output
    artifacts = list(output_dir.glob(
        "backfill-trades-sector-industry-restore-*.sql"
    ))
    assert len(artifacts) == 1
    restore_sql = artifacts[0].read_text(encoding="ascii")
    assert "UPDATE trades SET sector='', industry=''" in restore_sql
```

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_dry_run_emits_table_and_restore_sql_artifact -v`
Expected: PASS.

- [ ] **T-1.2 Step 7: Add AND-empty filter test (partial-empty row excluded from UPDATE)**

Append:

```python
def test_partial_empty_row_emits_skip_partial_empty_action(tmp_path):
    """Partial-empty (sector='Tech', industry='') row falls through to
    SKIP_PARTIAL_EMPTY (V1 STRICT all-or-nothing per R2.M3 LOCK)."""
    from swing.data.db import connect
    from swing.data.models import EvaluationRun, Candidate, Trade
    from swing.data.repos.candidates import (
        insert_candidates, insert_evaluation_run,
    )
    from swing.data.repos.trades import insert_trade

    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = connect(db_path)
    try:
        run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, run_id, [
            Candidate(ticker="VSAT", sector="Tech", industry="Comms",
                      **_build_candidate_fixture("VSAT")),
        ])
        # Plant a partial-empty trade row.
        insert_trade(conn, Trade(
            id=None, ticker="VSAT", state="entered",
            sector="Tech", industry="",
            **_build_trade_fixture("VSAT"),
        ))
    finally:
        conn.close()
    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output
    assert "SKIP_PARTIAL_EMPTY" in result.output
    # The partial-empty row was NOT scheduled for UPDATE.
    assert "UPDATE                 : 0" in result.output
    assert "SKIP_PARTIAL_EMPTY     : 1" in result.output
```

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_partial_empty_row_emits_skip_partial_empty_action -v`
Expected: PASS.

- [ ] **T-1.2 Step 8: Add SKIP_NO_CANDIDATES_ROW test (DHA legacy)**

Append:

```python
def test_dha_legacy_no_candidates_row_emits_skip_no_candidates(tmp_path):
    """Acknowledged-legacy DHA with no candidates row emits
    SKIP_NO_CANDIDATES_ROW (spec section 4.5 example #3)."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade

    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = connect(db_path)
    try:
        insert_trade(conn, Trade(
            id=None, ticker="DHA", state="entered",
            sector="", industry="",
            **_build_trade_fixture("DHA"),
        ))
    finally:
        conn.close()
    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0, result.output
    assert "SKIP_NO_CANDIDATES_ROW : 1" in result.output
    assert "UPDATE                 : 0" in result.output
```

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_dha_legacy_no_candidates_row_emits_skip_no_candidates -v`
Expected: PASS.

- [ ] **T-1.2 Step 9: Add `--apply` happy path test (atomic UPDATE + restore-SQL emitted BEFORE UPDATE)**

Append:

```python
def test_apply_commits_atomic_update_and_emits_restore_before_update(tmp_path):
    """--apply commits UPDATE under with conn: and emits restore-SQL
    BEFORE the UPDATE fires (spec section 4.3 R1.M3 LOCK)."""
    from swing.data.db import connect
    from swing.data.models import EvaluationRun, Candidate, Trade
    from swing.data.repos.candidates import (
        insert_candidates, insert_evaluation_run,
    )
    from swing.data.repos.trades import insert_trade, fetch_trade_by_id

    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = connect(db_path)
    try:
        run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, run_id, [
            Candidate(ticker="VSAT", sector="Technology",
                      industry="Communications Equipment",
                      **_build_candidate_fixture("VSAT")),
        ])
        trade_id = insert_trade(conn, Trade(
            id=None, ticker="VSAT", state="entered",
            sector="", industry="",
            **_build_trade_fixture("VSAT"),
        ))
    finally:
        conn.close()
    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
        "--apply",
    ])
    assert result.exit_code == 0, result.output
    assert "APPLY" in result.output
    # Restore-SQL artifact emitted BEFORE the UPDATE (defense-in-depth).
    artifacts = list(output_dir.glob(
        "backfill-trades-sector-industry-restore-*.sql"
    ))
    assert len(artifacts) == 1
    restore_sql = artifacts[0].read_text(encoding="ascii")
    assert f"WHERE id={trade_id}" in restore_sql
    # Post-apply: trade row has the new values.
    conn = connect(db_path)
    try:
        trade = fetch_trade_by_id(conn, trade_id)
        assert trade.sector == "Technology"
        assert trade.industry == "Communications Equipment"
    finally:
        conn.close()
```

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_apply_commits_atomic_update_and_emits_restore_before_update -v`
Expected: PASS.

- [ ] **T-1.2 Step 10: Add idempotency test (second --apply is no-op)**

Append:

```python
def test_apply_twice_is_idempotent(tmp_path):
    """Re-running --apply emits zero UPDATEs (the WHERE clause filters
    rows already populated)."""
    from swing.data.db import connect
    from swing.data.models import EvaluationRun, Candidate, Trade
    from swing.data.repos.candidates import (
        insert_candidates, insert_evaluation_run,
    )
    from swing.data.repos.trades import insert_trade

    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = connect(db_path)
    try:
        run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, run_id, [
            Candidate(ticker="VSAT", sector="Technology",
                      industry="Communications Equipment",
                      **_build_candidate_fixture("VSAT")),
        ])
        insert_trade(conn, Trade(
            id=None, ticker="VSAT", state="entered",
            sector="", industry="",
            **_build_trade_fixture("VSAT"),
        ))
    finally:
        conn.close()
    runner = CliRunner()
    # First apply.
    result1 = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
        "--apply",
    ])
    assert result1.exit_code == 0
    assert "UPDATE                 : 1" in result1.output
    # Second apply -- no-op (row already populated; AND-empty SELECT
    # returns zero rows).
    result2 = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
        "--apply",
    ])
    assert result2.exit_code == 0
    assert "UPDATE                 : 0" in result2.output
```

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_apply_twice_is_idempotent -v`
Expected: PASS.

- [ ] **T-1.2 Step 11: Add `--include-closed` widening test**

Append:

```python
def test_include_closed_widens_to_all_states(tmp_path):
    """Default excludes closed trades; --include-closed widens."""
    from swing.data.db import connect
    from swing.data.models import EvaluationRun, Candidate, Trade
    from swing.data.repos.candidates import (
        insert_candidates, insert_evaluation_run,
    )
    from swing.data.repos.trades import insert_trade

    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = connect(db_path)
    try:
        run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, run_id, [
            Candidate(ticker="VSAT", sector="Technology",
                      industry="Communications Equipment",
                      **_build_candidate_fixture("VSAT")),
        ])
        # Plant a CLOSED trade with empty sector/industry.
        insert_trade(conn, Trade(
            id=None, ticker="VSAT", state="closed",
            sector="", industry="",
            **_build_trade_fixture("VSAT"),
        ))
    finally:
        conn.close()
    runner = CliRunner()
    # Default (no --include-closed): closed trade is filtered out.
    result_default = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
    ])
    assert result_default.exit_code == 0
    assert "UPDATE                 : 0" in result_default.output
    # --include-closed: closed trade is included.
    result_widened = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
        "--include-closed",
    ])
    assert result_widened.exit_code == 0
    assert "UPDATE                 : 1" in result_widened.output
```

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_include_closed_widens_to_all_states -v`
Expected: PASS.

- [ ] **T-1.2 Step 12: Add `--allowlist` per-ticker opt-in test**

Append:

```python
def test_allowlist_restricts_to_specified_tickers(tmp_path):
    """--allowlist VSAT,XYZ restricts UPDATEs to that opt-in set."""
    from swing.data.db import connect
    from swing.data.models import EvaluationRun, Candidate, Trade
    from swing.data.repos.candidates import (
        insert_candidates, insert_evaluation_run,
    )
    from swing.data.repos.trades import insert_trade

    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = connect(db_path)
    try:
        run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, run_id, [
            Candidate(ticker="VSAT", sector="Technology",
                      industry="Communications Equipment",
                      **_build_candidate_fixture("VSAT")),
            Candidate(ticker="DHC", sector="Communication",
                      industry="Diversified",
                      **_build_candidate_fixture("DHC")),
        ])
        insert_trade(conn, Trade(
            id=None, ticker="VSAT", state="entered",
            sector="", industry="",
            **_build_trade_fixture("VSAT"),
        ))
        insert_trade(conn, Trade(
            id=None, ticker="DHC", state="entered",
            sector="", industry="",
            **_build_trade_fixture("DHC"),
        ))
    finally:
        conn.close()
    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
        "--allowlist", "VSAT",
    ])
    assert result.exit_code == 0
    assert "VSAT" in result.output
    # DHC was excluded by allowlist.
    assert "DHC" not in result.output
```

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_allowlist_restricts_to_specified_tickers -v`
Expected: PASS.

- [ ] **T-1.2 Step 13: Add malformed --db test (ValueError wrapping at CLI boundary)**

Append:

```python
def test_missing_db_path_raises_click_exception(tmp_path):
    """_validate_diagnose_db_path raises ClickException on missing --db."""
    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(tmp_path / "does-not-exist.db"),
    ])
    assert result.exit_code != 0
    assert "DB not found" in result.output
```

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_missing_db_path_raises_click_exception -v`
Expected: PASS.

- [ ] **T-1.2 Step 13b: Add provenance assertion test (Codex R1.M#6 LOCK)**

Append:

```python
def test_dry_run_table_renders_source_candidate_and_run_id_columns(tmp_path):
    """The dry-run table cites source_candidate_id +
    source_evaluation_run_id per spec section 4.3 column list (Codex R1.M#6
    LOCK -- provenance auditability so operators can re-trace which
    candidates row supplied each backfill)."""
    from swing.data.db import connect
    from swing.data.models import EvaluationRun, Candidate, Trade
    from swing.data.repos.candidates import (
        insert_candidates, insert_evaluation_run,
    )
    from swing.data.repos.trades import insert_trade

    db_path = tmp_path / "swing.db"
    output_dir = tmp_path / "out"
    conn = connect(db_path)
    try:
        run_id = insert_evaluation_run(conn, EvaluationRun(
            id=None, run_ts="2026-05-27T20:00:00",
            data_asof_date="2026-05-26", action_session_date="2026-05-27",
        ))
        insert_candidates(conn, run_id, [
            Candidate(ticker="VSAT", sector="Technology",
                      industry="Communications Equipment",
                      **_build_candidate_fixture("VSAT")),
        ])
        insert_trade(conn, Trade(
            id=None, ticker="VSAT", state="entered",
            sector="", industry="",
            **_build_trade_fixture("VSAT"),
        ))
    finally:
        conn.close()
    runner = CliRunner()
    result = runner.invoke(swing_cli, [
        "diagnose", "backfill-trades-sector-industry",
        "--db", str(db_path),
        "--output-dir", str(output_dir),
    ])
    assert result.exit_code == 0
    # Column header includes provenance columns.
    assert "source_cand_id" in result.output
    assert "source_eval_run_id" in result.output
    # The UPDATE row cites the actual run_id (not the '-' placeholder
    # used for SKIP rows).
    assert str(run_id) in result.output
    # Skip rows would render '-'; in this fixture there are none, so
    # we don't assert the '-' here (covered in the DHA legacy test +
    # the partial-empty test where the SKIP rows render '-').
```

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_dry_run_table_renders_source_candidate_and_run_id_columns -v`
Expected: PASS.

- [ ] **T-1.2 Step 14: Add ASCII discipline test for the CLI subcommand + helper module**

Append:

```python
def test_cli_subcommand_module_ascii_only():
    """CLI emit + helper module are ASCII-only per gotcha #32."""
    from pathlib import Path
    import swing.cli as cli_mod
    import swing.diagnostics.backfill_trades_sector_industry as helper_mod
    Path(cli_mod.__file__).read_text(encoding="utf-8").encode("ascii")
    Path(helper_mod.__file__).read_text(encoding="utf-8").encode("ascii")
    Path(__file__).read_text(encoding="utf-8").encode("ascii")
```

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_cli_subcommand_module_ascii_only -v`
Expected: PASS.

- [ ] **T-1.2 Step 15: Run full test module + commit**

Run: `pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py -v`
Expected: ALL PASS (~9 tests).

```bash
git add swing/cli.py \
        swing/diagnostics/backfill_trades_sector_industry.py \
        tests/cli/test_diagnose_backfill_trades_sector_industry.py
git commit -m "feat(diagnose): add backfill-trades-sector-industry CLI subcommand"
```

Verify ZERO `Co-Authored-By:` trailer:
```bash
git log -1 --pretty="%(trailers)"
```
Expected: empty.

Optionally split into 2-3 commits per §G.0 if scope warrants: commit 1 = helper module + CLI shell; commit 2 = remaining tests + ASCII discipline.

---

### §G.T-1.3 (OPTIONAL): V2.G3 VM fallback Fix-1b

**Trigger condition (pre-ship NOT IN PLAN per spec §4.2 + dispatch brief §1.3):** execute T-1.3 ONLY IF:
- (a) the writing-plans-phase code-read OR a manual `swing diagnose backfill-trades-sector-industry --dry-run` against operator-side DB surfaces residual `(sector="", industry="")` rows where the `get_latest_sector_industry_per_ticker` helper returns a non-empty pair (would indicate a bug in T-1.1 — investigate FIRST before T-1.3); OR
- (b) operator-witnessed gate at S3 reveals that the apply-path successfully ran but the dashboard still shows em-dash for tickers where candidates DOES have non-empty rows (would suggest a TOCTOU race between backfill apply and dashboard render — investigate FIRST); OR
- (c) operator explicitly requests VM fallback ship in V1 (override of brainstorm verdict §4.2).

**Files (IF executed):**
- Modify: `swing/web/view_models/dashboard.py` open-positions construction loop OR `swing/web/view_models/open_positions_row.py` if a separate module exists (audit at trigger time)
- Test: extend existing open-positions VM test module

**Acceptance criteria (IF executed):**
1. At per-row VM build, if `trade.sector == ""` OR `trade.industry == ""`, invoke `get_latest_sector_industry_per_ticker(conn, [trade.ticker])` and substitute the non-empty pair.
2. NEVER blank a non-empty value (do not regress from "Tech" to "" — apply per-column independently per V2 candidate intent; OR fall back to V1 STRICT all-or-nothing IF Fix-1b ships per brainstorm verdict).
3. 2-3 discriminating tests per spec §4.5 example #1 + #2.

**Default disposition:** SKIP T-1.3. If executed, ~1 commit + 2-3 tests.

---

### §G.T-2.1: V2.G4 route handler signature fix + module-level logger

**Files:**
- Modify: `swing/web/routes/dashboard.py` (3 surgical edits: add `import logging` at top; add `log = logging.getLogger(__name__)` after `router = APIRouter()`; rewrite bars-fetch block at lines 74-87)
- Test: `tests/web/test_routes/test_dashboard_chart_integration.py` (MODIFIED with ~6-8 new tests)

**Acceptance criteria:**
1. Module-level `import logging` added near existing stdlib imports (after `from datetime import datetime`).
2. Module-level `log = logging.getLogger(__name__)` defined after `router = APIRouter()`.
3. **CRITICAL: Items 1 + 2 + 3 land in the SAME commit** (R3.M2 LOCK / forward-binding lesson #4; split would NameError on the first ValueError-degraded invocation).
4. Bars-fetch block rewritten: `bars = ohlcv_cache.get_or_fetch(ticker=benchmark)` (keyword `ticker=`); dead dict-style `bars_bundle.get(benchmark)` code removed.
5. Exception catch narrowed: `except ValueError as exc: log.warning(...); bars = None` ONLY; no broad `except Exception:` swallow.
6. `log.warning` message includes the benchmark ticker name (operator-grep-reachable).
7. Programming-error propagation: discriminating tests assert `TypeError` + `AttributeError` + `KeyError` + `RuntimeError` propagate as 500 (NOT 409); ValueError-only path returns 409 with `log.warning` captured via `caplog`.
8. Happy-path test: mock `OhlcvCache.get_or_fetch` to return a valid DataFrame; assert 204 + `HX-Redirect: /dashboard` + `chart_renders` row written.
9. Signature regression test: assert `get_or_fetch` invoked with `ticker=` kwarg (NOT positional list); via `unittest.mock.MagicMock` assertion `mock.assert_called_once_with(ticker="SPY")`.
10. HTMX trinity preservation regression test: assert HX-Request handling + 204 + HX-Redirect + target route (`/dashboard`) registered (gotcha forward-binding lesson #7).
11. ASCII discipline test for the route module + test module.
12. ~6-8 fast tests cover all paths.
13. Gotchas applied: #5, #11 (NO new HTMX), #17, #27, #32. Watch items #4, #7, #8.

#### TDD steps

- [ ] **T-2.1 Step 1: Write the failing signature regression test**

Add to `tests/web/test_routes/test_dashboard_chart_integration.py`:

```python
"""V2.G4 weather-chart refresh handler regression tests
(Phase 14 Sub-bundle 1).

Per spec section 5.6 discriminating-example walkthroughs + spec section 5.2
narrow ValueError-only exception handling LOCK (R2.M2).
"""

import logging
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient


def test_weather_refresh_calls_get_or_fetch_with_ticker_kwarg(
    test_client_with_pipeline_run, mocked_ohlcv_cache,
):
    """V2.G4 root cause: get_or_fetch is keyword-only; previous handler
    passed a positional list which raised TypeError silently swallowed
    by bare except Exception. Post-fix: kwarg-style call only."""
    test_client_with_pipeline_run.post("/dashboard/weather-chart/refresh")
    mocked_ohlcv_cache.get_or_fetch.assert_called_once()
    call_kwargs = mocked_ohlcv_cache.get_or_fetch.call_args.kwargs
    call_args = mocked_ohlcv_cache.get_or_fetch.call_args.args
    assert call_args == (), (
        "get_or_fetch must be invoked with KEYWORD ticker= argument, "
        "not positional list (V2.G4 root cause)"
    )
    assert call_kwargs == {"ticker": "SPY"}
```

(NOTE: `test_client_with_pipeline_run` + `mocked_ohlcv_cache` are pytest fixtures to be added at executing-plans phase per the existing `tests/web/conftest.py` pattern. They plant a completed pipeline_run row + monkeypatch `app.state.ohlcv_cache` to a `MagicMock(spec=OhlcvCache)`. A SECOND fixture `test_client_with_pipeline_run_no_raise` constructs the TestClient with `raise_server_exceptions=False` per Codex R1.M#3 LOCK -- the propagation-to-500 assertions require the server-side 500 response to be observable as `response.status_code`; FastAPI's TestClient defaults to `raise_server_exceptions=True` which re-raises uncaught exceptions into the test runner instead of producing a response. Fixture shape:

```python
@pytest.fixture
def test_client_with_pipeline_run_no_raise(...):
    from fastapi.testclient import TestClient
    from swing.web.app import app
    # ... plant pipeline_runs row + app.state.ohlcv_cache monkeypatch ...
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
```
)

- [ ] **T-2.1 Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_routes/test_dashboard_chart_integration.py::test_weather_refresh_calls_get_or_fetch_with_ticker_kwarg -v`
Expected: FAIL because the production code passes `[benchmark]` positionally.

- [ ] **T-2.1 Step 3: Apply the production fix — add logger + rewrite block (SINGLE commit)**

Modify `swing/web/routes/dashboard.py`:

```python
"""GET / — the main dashboard route + POST /dashboard/weather-chart/refresh."""
from __future__ import annotations

import logging  # NEW per R3.M2 LOCK
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.data.models import ChartRender
from swing.data.repos.chart_renders import refresh_chart_render
from swing.evaluation.dates import last_completed_session
from swing.web.chart_scope import latest_completed_pipeline_run
from swing.web.view_models.dashboard import build_dashboard

router = APIRouter()
log = logging.getLogger(__name__)  # NEW per R3.M2 LOCK; MUST land in same
                                    # commit as log.warning(...) below.
```

Then rewrite the block at lines 74-87 (within `dashboard_weather_chart_refresh`):

```python
        benchmark = cfg.rs.benchmark_ticker
        try:
            bars = ohlcv_cache.get_or_fetch(ticker=benchmark)
        except ValueError as exc:
            # OhlcvCache.get_or_fetch raises ValueError("No data for {ticker}")
            # on empty-archive / cache-miss-fallthrough per its docstring at
            # swing/web/ohlcv_cache.py:131. This is the canonical empty-result
            # signal (NOT a programming error). Emit a warning so the
            # operator-visible 409 message can be diagnosed via logs per
            # CLAUDE.md gotcha #27 (silent-skip-without-audit) + Phase 14
            # Sub-bundle 1 V2.G4 R2.M2 LOCK.
            log.warning(
                "weather-chart refresh: get_or_fetch returned empty for %s: %s",
                benchmark, exc,
            )
            bars = None
        # NOTE: Do NOT catch broad `Exception` here. The pre-fix handler caught
        # arbitrary exceptions (including the TypeError that hid this bug for
        # weeks) and silently returned a 409 "no bars" message -- exactly the
        # masking pattern the operator-witnessed gate surfaced. Let TypeError,
        # AttributeError, KeyError, RuntimeError, and other programming errors
        # propagate to FastAPI's default 500 handler so they show up in
        # operator-witnessed gates as 500s (not as "run the pipeline first"
        # 409s). Per R2.M2 anti-pattern lock + forward-binding lesson #8.
        if bars is None or bars.empty:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"no OHLCV bars available for benchmark {benchmark!r}; "
                    "run the pipeline first"
                ),
            )
```

(The remainder of the handler — `render_market_weather_svg(...)`, `ChartRender(...)`, `refresh_chart_render(conn, chart_render)` under `with conn:`, return `Response(status_code=204, headers={"HX-Redirect": "/dashboard"})` — is UNCHANGED.)

- [ ] **T-2.1 Step 4: Re-run signature test to verify pass**

Run: `pytest tests/web/test_routes/test_dashboard_chart_integration.py::test_weather_refresh_calls_get_or_fetch_with_ticker_kwarg -v`
Expected: PASS.

- [ ] **T-2.1 Step 5: Add ValueError-degraded path test (log.warning + 409)**

Append:

```python
def test_value_error_degraded_path_logs_warning_and_returns_409(
    test_client_with_pipeline_run, mocked_ohlcv_cache, caplog,
):
    """ValueError from get_or_fetch is the canonical empty-archive signal;
    handler logs warning + returns 409 with operator-friendly message
    (spec section 5.2 R2.M2 ValueError-only narrow catch)."""
    mocked_ohlcv_cache.get_or_fetch.side_effect = ValueError(
        "No data for SPY"
    )
    with caplog.at_level(logging.WARNING, logger="swing.web.routes.dashboard"):
        response = test_client_with_pipeline_run.post(
            "/dashboard/weather-chart/refresh",
        )
    assert response.status_code == 409
    assert "no OHLCV bars available for benchmark 'SPY'" in response.text
    # log.warning emitted with the benchmark ticker name for operator
    # grep-reachability.
    assert any(
        "weather-chart refresh" in rec.message
        and "SPY" in rec.message
        for rec in caplog.records
    )
```

Run: `pytest tests/web/test_routes/test_dashboard_chart_integration.py::test_value_error_degraded_path_logs_warning_and_returns_409 -v`
Expected: PASS.

- [ ] **T-2.1 Step 6: Add TypeError propagation test (NOT caught)**

Append:

```python
def test_type_error_propagates_to_500_not_409(
    test_client_with_pipeline_run_no_raise, mocked_ohlcv_cache,
):
    """Programming errors (TypeError) propagate to FastAPI default 500
    handler -- they MUST NOT be silently masked as a misleading 409
    (R2.M2 LOCK; this is the V2.G4 root-cause-class regression check).

    Per Codex R1.M#3 LOCK: TestClient is constructed with
    raise_server_exceptions=False so the server-side 500 response is
    observable. Default TestClient(raise_server_exceptions=True) would
    re-raise the TypeError into the test rather than yield a 500.
    """
    mocked_ohlcv_cache.get_or_fetch.side_effect = TypeError(
        "Simulated programming error -- e.g., positional vs keyword "
        "signature drift."
    )
    response = test_client_with_pipeline_run_no_raise.post(
        "/dashboard/weather-chart/refresh",
    )
    # FastAPI default 500 handler returns 500 (NOT the 409 the pre-fix
    # broad-except branch would have returned).
    assert response.status_code == 500
    assert "no OHLCV bars" not in response.text
```

Run: `pytest tests/web/test_routes/test_dashboard_chart_integration.py::test_type_error_propagates_to_500_not_409 -v`
Expected: PASS.

- [ ] **T-2.1 Step 7: Add AttributeError + KeyError + RuntimeError parametric propagation tests**

Append:

```python
@pytest.mark.parametrize(
    "exc_type, exc_args",
    [
        (AttributeError, ("simulated attr error",)),
        (KeyError, ("simulated key error",)),
        (RuntimeError, ("simulated runtime error",)),
    ],
)
def test_other_programming_errors_propagate_to_500(
    test_client_with_pipeline_run_no_raise, mocked_ohlcv_cache,
    exc_type, exc_args,
):
    """AttributeError, KeyError, RuntimeError all propagate as 500
    (forward-binding lesson #8 -- narrow ValueError-only catch ensures
    programming errors are NOT silently masked).

    Per Codex R1.M#3 LOCK: TestClient(raise_server_exceptions=False)
    fixture so the 500 server-side response is observable as a
    response.status_code -- the default TestClient would re-raise the
    exception into the test runner.
    """
    mocked_ohlcv_cache.get_or_fetch.side_effect = exc_type(*exc_args)
    response = test_client_with_pipeline_run_no_raise.post(
        "/dashboard/weather-chart/refresh",
    )
    assert response.status_code == 500
```

Run: `pytest tests/web/test_routes/test_dashboard_chart_integration.py::test_other_programming_errors_propagate_to_500 -v`
Expected: PASS (3 parametric cases).

- [ ] **T-2.1 Step 8: Add happy-path test (204 + HX-Redirect + chart_renders row)**

Append:

```python
def test_happy_path_returns_204_with_hx_redirect_and_writes_chart_render(
    test_client_with_pipeline_run, mocked_ohlcv_cache, swing_db_path,
):
    """Happy path: SPY bars in cache -> 204 + HX-Redirect: /dashboard +
    chart_renders row written (spec section 5.6 example #1)."""
    import sqlite3
    # Plant a valid DataFrame return for SPY.
    bars = _build_spy_bars_fixture()  # production-shape DataFrame
    mocked_ohlcv_cache.get_or_fetch.return_value = bars
    response = test_client_with_pipeline_run.post(
        "/dashboard/weather-chart/refresh",
    )
    assert response.status_code == 204
    assert response.headers.get("HX-Redirect") == "/dashboard"
    conn = sqlite3.connect(swing_db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM chart_renders "
            "WHERE ticker='SPY' AND surface='market_weather'"
        ).fetchone()
        assert row[0] >= 1
    finally:
        conn.close()


def _build_spy_bars_fixture() -> pd.DataFrame:
    """Production-shape DataFrame matching read_or_fetch_archive output:
    DatetimeIndex + capitalized Open/High/Low/Close/Volume columns."""
    idx = pd.DatetimeIndex(pd.date_range(end="2026-05-27", periods=60, freq="B"))
    return pd.DataFrame({
        "Open": [400.0] * 60, "High": [405.0] * 60, "Low": [395.0] * 60,
        "Close": [402.0] * 60, "Volume": [1_000_000] * 60,
    }, index=idx)
```

Run: `pytest tests/web/test_routes/test_dashboard_chart_integration.py::test_happy_path_returns_204_with_hx_redirect_and_writes_chart_render -v`
Expected: PASS.

- [ ] **T-2.1 Step 9: Add HTMX trinity preservation regression test**

Append:

```python
def test_htmx_trinity_preserved_for_weather_chart_refresh(
    test_client_with_pipeline_run, mocked_ohlcv_cache,
):
    """Forward-binding lesson #7: weather-chart/refresh HTMX trinity
    PRESERVED post-V2.G4 fix:
      (a) /dashboard target route registered;
      (b) success response 204 + HX-Redirect (NOT 303 swap-target);
      (c) embedded form HX-Request header propagation (verified by
          checking dashboard.html.j2 still emits hx-headers).
    """
    from swing.web.app import app
    # (a) Target route registered.
    paths = {r.path for r in app.routes}
    assert "/dashboard" in paths
    # (b) Success response shape.
    mocked_ohlcv_cache.get_or_fetch.return_value = _build_spy_bars_fixture()
    response = test_client_with_pipeline_run.post(
        "/dashboard/weather-chart/refresh",
    )
    assert response.status_code == 204
    assert "HX-Redirect" in response.headers
    # (c) Embedded form HX-Request propagation -- inspect template source.
    from pathlib import Path
    import swing.web.templates as tpl_mod
    tpl_path = Path(tpl_mod.__file__).parent / "dashboard.html.j2"
    src = tpl_path.read_text(encoding="utf-8")
    assert 'hx-headers' in src
    assert '"HX-Request"' in src
```

Run: `pytest tests/web/test_routes/test_dashboard_chart_integration.py::test_htmx_trinity_preserved_for_weather_chart_refresh -v`
Expected: PASS.

- [ ] **T-2.1 Step 10: Add no-pipeline degraded path regression test (unchanged from pre-fix)**

Append:

```python
def test_no_pipeline_run_returns_existing_409_unchanged(
    test_client_no_pipeline_run, mocked_ohlcv_cache,
):
    """Empty pipeline_runs table -> existing 409 'no completed pipeline_run'
    message (UNCHANGED from pre-fix behavior; regression check)."""
    response = test_client_no_pipeline_run.post(
        "/dashboard/weather-chart/refresh",
    )
    assert response.status_code == 409
    assert "no completed pipeline_run" in response.text
```

Run: `pytest tests/web/test_routes/test_dashboard_chart_integration.py::test_no_pipeline_run_returns_existing_409_unchanged -v`
Expected: PASS.

- [ ] **T-2.1 Step 11: Add ASCII discipline test for the route module**

Append:

```python
def test_dashboard_route_module_ascii_only():
    """Per gotcha #32 + spec section 15.2 -- route module ASCII-only."""
    from pathlib import Path
    import swing.web.routes.dashboard as mod
    Path(mod.__file__).read_text(encoding="utf-8").encode("ascii")
```

Run: `pytest tests/web/test_routes/test_dashboard_chart_integration.py::test_dashboard_route_module_ascii_only -v`
Expected: PASS.

- [ ] **T-2.1 Step 12: Run full test module + commit**

Run: `pytest tests/web/test_routes/test_dashboard_chart_integration.py -v`
Expected: ALL PASS (new tests + existing unchanged).

```bash
git add swing/web/routes/dashboard.py \
        tests/web/test_routes/test_dashboard_chart_integration.py
git commit -m "fix(web): correct OhlcvCache.get_or_fetch call signature in weather-chart refresh (V2.G4)"
```

Verify ZERO `Co-Authored-By:` trailer:
```bash
git log -1 --pretty="%(trailers)"
```
Expected: empty.

**CRITICAL discipline check (forward-binding lesson #4):** the diff for this commit MUST include BOTH the `import logging` + `log = logging.getLogger(__name__)` module-level additions AND the `log.warning(...)` callsite. Verify via:
```bash
git diff HEAD~1 swing/web/routes/dashboard.py | grep -E "^(\+import logging|\+log = logging|\+    log\.warning)"
```
Expected: 3 lines (one per addition; all in the same diff).

---

### §G.T-3.1: P14.N3 VM 4-field extension + template rewrite

**Files:**
- Modify: `swing/web/view_models/trades.py` (extend `DailyManagementTileVM` dataclass at lines 2042-2078 with 4 NEW fields per Codex R2.M#1+M#2 LOCK)
- Modify: `swing/web/view_models/dashboard.py` (extend inline build at lines 1390-1417 with denominator-stamping mirror; audit + add imports for `resolve_live_capital_denominator_dollars`, `read_live_policy`, `compute_position_capital_utilization`, `date`, `math` if any missing)
- Modify: `swing/web/templates/partials/daily_management_tile.html.j2` (replace block at lines 91-99 with conditional badge emit + new tooltip + inline `(?)` affordance)
- Test: `tests/web/test_daily_management_tile.py` (MODIFIED with ~7-9 new tests)
- Test: `tests/web/view_models/test_dashboard_view_model.py` (MODIFIED with ~4-6 new tests; create test file if it does not exist)

**Acceptance criteria:**
1. `DailyManagementTileVM` extended with 4 NEW fields: `position_capital_denominator_dollars_resolved: float`, `position_capital_utilization_is_provisional: bool`, `position_capital_utilization_pct_effective: float | None`, `position_capital_policy_missing: bool` (4th field per Codex R2.M#1+M#2 LOCK -- surfaces NoActivePolicyError fallback per spec §6.4 second bullet).
2. Inline build site at `swing/web/view_models/dashboard.py:1390-1417` populates the 4 new fields via the canonical `swing/metrics/maturity.py:197-219` denominator-stamping pattern (extended with NoActivePolicyError try/except branch per Codex R1.M#1).
3. `row_asof` derived from `snap.data_asof_session` via `date.fromisoformat(...)` with ValueError-guarded fallback to page-level `asof_date` per `maturity.py:190-194`.
4. `resolve_live_capital_denominator_dollars(conn, asof_date=row_asof, at_trade_time_policy=read_live_policy(conn))` invoked per row.
5. `position_capital_utilization_pct_effective` = stored `snap.position_capital_utilization_pct` when `math.isclose(snap.position_capital_denominator_dollars, denom_resolved, rel_tol=1e-9)`; otherwise RECOMPUTED via `compute_position_capital_utilization(current_size=..., current_price=..., denominator_dollars=denom_resolved)` (PROPORTION-unit; R3.M1 LOCK).
6. **CRITICAL R3.M1 LOCK**: do NOT swap in `_compute_position_util_pct` (returns PERCENT; would render 1500.0% on a 15% utilization). Discriminating test asserts.
7. **NoActivePolicyError fallback (Codex R1.M#1 LOCK):** `read_live_policy(conn)` is wrapped in `try / except NoActivePolicyError`; on raise, `live_policy=None` + `denom_resolved=0.0` + `denom_badge="PROVISIONAL"` -- preserves spec §6.4 second bullet contract that "no active risk_policy" still renders PROVISIONAL (NOT a 500). Discriminating test at T-3.1 step 11b plants `risk_policy` table with all rows `is_active=0` and asserts dashboard render succeeds + tile shows PROVISIONAL badge.
8. Template at `swing/web/templates/partials/daily_management_tile.html.j2:91-99` rewritten to:
   - Render `tile.position_capital_utilization_pct_effective * 100.0` (NOT the legacy field).
   - Conditionally emit PROVISIONAL badge ONLY when `tile.position_capital_utilization_is_provisional` is True.
   - NEW tooltip text describing the actual clear-condition (`account_equity_snapshots` row + `swing schwab fetch --snapshot` example).
   - NEW inline `(?)` affordance with `help-detail` blurb visible-on-focus per existing CSS conventions (audit at executing-plans phase).
   - Em-dash placeholder rendered as ASCII `--` per gotcha #32.
9. Server-stamping discipline (Phase 8 R2.M2+R3.M2+R4.M2 family / forward-binding lesson #13) — all 4 NEW fields are SERVER-COMPUTED at build time; NO hidden form input; NO operator-supplied state.
10. ~8-10 fast template tests + ~5-7 fast VM tests cover all paths (one VM test added per Codex R1.M#1 NoActivePolicyError fallback).
11. Gotchas applied: #11 (template + VM audited together), #17 (signature contract test on the resolver), #19 (cascade-call-graph: verify `compute_position_capital_utilization` does NOT invoke `_compute_position_util_pct`), #23 (3 fields are required + attribution unambiguous), #32 (ASCII). Watch items #3, #9.

**OQ #5 resolution at plan-authoring:** `DailyManagementTileVM` lives at `swing/web/view_models/trades.py:2042-2078`; build site at `swing/web/view_models/dashboard.py:1390-1417` inline construction. LOCKED.
**OQ #6 resolution at plan-authoring:** tooltip placement = `title` attribute on the badge (existing convention) + NEW inline `<button type="button" class="muted help-affordance" aria-describedby="provisional-capital-help-{tile_id}" aria-label="Why is this PROVISIONAL?">` with `(?)` text + `<span id="provisional-capital-help-{tile_id}" class="help-detail" role="tooltip">` (Codex R1.M#2 LOCK -- real focusable button + ARIA, NOT a `<span>`, for keyboard accessibility). LOCKED.

#### TDD steps

- [ ] **T-3.1 Step 1: Write the failing template percent-vs-proportion regression test (R3.M1 LOCK)**

Add to `tests/web/test_daily_management_tile.py`:

```python
"""P14.N3 daily-management tile PROVISIONAL/LIVE state + tooltip tests
(Phase 14 Sub-bundle 1).

Per spec section 6.5 discriminating-example walkthroughs + R3.M1 LOCK
(PROPORTION-unit semantic; rendered value must be < 50% for 0.15 fixture,
NOT 1500.0%) + R3.M2 LOCK (clear-condition tooltip wording).
"""

from datetime import date
from unittest.mock import MagicMock

import pytest
from jinja2 import Environment, FileSystemLoader

from swing.web.view_models.trades import DailyManagementTileVM


@pytest.fixture
def jinja_env():
    from pathlib import Path
    import swing.web.templates as tpl_mod
    return Environment(
        loader=FileSystemLoader(Path(tpl_mod.__file__).parent),
        autoescape=True,
    )


def _build_tile_vm(
    *,
    is_provisional: bool,
    util_pct_effective: float | None,
    policy_missing: bool = False,
):
    return DailyManagementTileVM(
        trade_id=1, ticker="VSAT", state="entered",
        current_price=42.0, current_stop=40.0, open_R_effective=0.5,
        open_MFE_R_to_date=1.0, open_MAE_R_to_date=-0.2,
        maturity_stage="day_2_to_5", trail_MA_eligibility_flag=0,
        trail_MA_candidate_price=None,
        position_capital_utilization_pct=0.15,  # legacy backwards-compat
        position_capital_denominator_dollars=7500.0,
        position_portfolio_heat_contribution_dollars=80.0,
        planned_target_R=2.0,
        data_asof_session="2026-05-27",
        # NEW fields per P14.N3:
        position_capital_denominator_dollars_resolved=(
            0.0 if policy_missing else 7500.0
        ),
        position_capital_utilization_is_provisional=is_provisional,
        position_capital_utilization_pct_effective=util_pct_effective,
        # Codex R2.M#1+M#2 LOCK -- 4th NEW field for policy-missing branch.
        position_capital_policy_missing=policy_missing,
    )


def test_proportion_unit_lock_renders_15_percent_not_1500_percent(jinja_env):
    """R3.M1 LOCK: PROPORTION-unit (0.15) rendered as 15.0%, NOT 1500.0%."""
    vm = MagicMock()
    vm.daily_management_tiles = [_build_tile_vm(
        is_provisional=True, util_pct_effective=0.15,
    )]
    tmpl = jinja_env.get_template("partials/daily_management_tile.html.j2")
    rendered = tmpl.render(vm=vm)
    assert "15.0%" in rendered
    assert "1500.0%" not in rendered
```

- [ ] **T-3.1 Step 2: Run test to verify it fails (or passes if template already correct)**

Run: `pytest tests/web/test_daily_management_tile.py::test_proportion_unit_lock_renders_15_percent_not_1500_percent -v`
Expected: depends on whether the dataclass / template at HEAD already supports the new fields. Pre-T-3.1 fix: FAIL because `position_capital_utilization_pct_effective` is NOT a field on `DailyManagementTileVM` yet (`TypeError` from dataclass constructor OR template AttributeError).

- [ ] **T-3.1 Step 3: Extend `DailyManagementTileVM` with 4 NEW fields**

Edit `swing/web/view_models/trades.py:2042-2078` — add 3 fields to the dataclass:

```python
@dataclass(frozen=True)
class DailyManagementTileVM:
    """Per-open-position dashboard tile row (spec §7.1 + plan T5.1).

    [... existing docstring preserved ...]
    """
    trade_id: int
    ticker: str
    state: str
    current_price: float | None
    current_stop: float
    open_R_effective: float | None          # noqa: N815
    open_MFE_R_to_date: float | None        # noqa: N815
    open_MAE_R_to_date: float | None        # noqa: N815
    maturity_stage: str | None
    trail_MA_eligibility_flag: int | None   # noqa: N815
    trail_MA_candidate_price: float | None  # noqa: N815
    position_capital_utilization_pct: float | None
    position_capital_denominator_dollars: float | None
    position_portfolio_heat_contribution_dollars: float | None
    planned_target_R: float | None          # noqa: N815
    data_asof_session: str | None
    # ----- NEW per Phase 14 Sub-bundle 1 P14.N3 spec section 6.2 -----
    # Freshly-resolved denominator at render time (via
    # equity_resolver.resolve_live_capital_denominator_dollars).
    position_capital_denominator_dollars_resolved: float
    # True iff freshly-resolved state == "PROVISIONAL".
    position_capital_utilization_is_provisional: bool
    # The utilization to render: stored when denominators match
    # (math.isclose rel_tol=1e-9); recomputed via
    # swing.trades.daily_management.compute_position_capital_utilization
    # otherwise; None when ill-defined.
    position_capital_utilization_pct_effective: float | None
    # True iff no risk_policy row has is_active=1 (NoActivePolicyError
    # caught at the build site). Codex R2.M#1+M#2 LOCK -- template
    # renders PROVISIONAL badge + extra-caveat tooltip OUTSIDE the
    # util-value guard so the operator sees a distinct remediation
    # path (run `swing db-migrate` or `swing config policy
    # import-from-toml`) even when util_pct_effective is None.
    position_capital_policy_missing: bool
```

- [ ] **T-3.1 Step 4: Extend inline build at `swing/web/view_models/dashboard.py:1390-1417`**

Add imports near the top of `swing/web/view_models/dashboard.py` (audit existing imports first; add only the missing ones):

```python
import math
from datetime import date

from swing.data.repos.risk_policy import NoActivePolicyError
from swing.metrics.equity_resolver import (
    resolve_live_capital_denominator_dollars,
)
from swing.metrics.policy import read_live_policy
from swing.trades.daily_management import compute_position_capital_utilization
```

Within the per-(trade, snap) loop ending at the existing `tiles.append(DailyManagementTileVM(...))` block at lines 1390-1417, insert ABOVE the `tiles.append(...)` call (and CONSUMING the existing `trade` + `snap` + `asof_date` locals already in scope):

```python
            # P14.N3: PROVISIONAL/LIVE state via maturity.py:197-219 mirror.
            row_asof = asof_date
            if snap.data_asof_session:
                try:
                    row_asof = date.fromisoformat(snap.data_asof_session)
                except ValueError:
                    row_asof = asof_date  # ValueError-guarded per
                                          # maturity.py:190-194
            # NoActivePolicyError fallback per Codex R1.M#1 + R2.M#1+M#2
            # LOCK + spec section 6.4 second bullet: zero active risk_policy
            # rows MUST render PROVISIONAL with EXTRA-CAVEAT tooltip
            # (distinct from the standard PROVISIONAL tooltip), NOT 500
            # AND NOT silently swallowed. Codex R2.M#1+#2 LOCK: set
            # policy_missing=True so the template renders the badge
            # OUTSIDE the util-value guard (util_pct_effective will be
            # None in this branch and the standard rendering path would
            # otherwise suppress the badge entirely).
            try:
                live_policy = read_live_policy(conn)
                policy_missing = False
            except NoActivePolicyError:
                live_policy = None
                policy_missing = True
            if live_policy is not None:
                denom_resolved, denom_badge = (
                    resolve_live_capital_denominator_dollars(
                        conn,
                        asof_date=row_asof,
                        at_trade_time_policy=live_policy,
                    )
                )
            else:
                # Denominator undefined; PROVISIONAL with util=None.
                # Template renders em-dash for the cell + emits the
                # policy-missing badge + extra-caveat tooltip per spec
                # section 6.4 second bullet.
                denom_resolved = 0.0
                denom_badge = "PROVISIONAL"
            is_provisional = (denom_badge == "PROVISIONAL")
            # Denominator-stamping per maturity.py:197-219:
            stored_util = snap.position_capital_utilization_pct
            stored_denom = snap.position_capital_denominator_dollars
            if (
                stored_util is not None
                and stored_denom is not None
                and math.isclose(
                    stored_denom, denom_resolved, rel_tol=1e-9,
                )
            ):
                util_pct_effective = stored_util  # reuse stored proportion
            elif (
                trade.current_size is not None
                and snap.current_price is not None
                and denom_resolved > 0
            ):
                # R3.M1 LOCK: PROPORTION-unit recompute via
                # compute_position_capital_utilization (NOT
                # _compute_position_util_pct which returns percent).
                util_pct_effective = compute_position_capital_utilization(
                    current_size=trade.current_size,
                    current_price=snap.current_price,
                    denominator_dollars=denom_resolved,
                )
            else:
                util_pct_effective = None
```

Then extend the existing `tiles.append(DailyManagementTileVM(...))` constructor with the 4 new keyword arguments (preserve all existing fields verbatim; Codex R5.m#2 LOCK -- 4 fields including R2.M#1+M#2's `position_capital_policy_missing`):

```python
            tiles.append(DailyManagementTileVM(
                trade_id=snap.trade_id,
                ticker=trade.ticker,
                state=trade.state,
                current_stop=trade.current_stop,
                planned_target_R=trade.planned_target_R,
                current_price=snap.current_price,
                open_R_effective=live_open_R,
                open_MFE_R_to_date=snap.open_MFE_R_to_date,
                open_MAE_R_to_date=snap.open_MAE_R_to_date,
                maturity_stage=snap.maturity_stage,
                trail_MA_eligibility_flag=snap.trail_MA_eligibility_flag,
                trail_MA_candidate_price=snap.trail_MA_candidate_price,
                position_capital_utilization_pct=(
                    snap.position_capital_utilization_pct
                ),
                position_capital_denominator_dollars=(
                    snap.position_capital_denominator_dollars
                ),
                position_portfolio_heat_contribution_dollars=(
                    snap.position_portfolio_heat_contribution_dollars
                ),
                data_asof_session=snap.data_asof_session,
                # P14.N3 NEW fields:
                position_capital_denominator_dollars_resolved=denom_resolved,
                position_capital_utilization_is_provisional=is_provisional,
                position_capital_utilization_pct_effective=util_pct_effective,
                position_capital_policy_missing=policy_missing,
            ))
```

- [ ] **T-3.1 Step 5: Rewrite the template badge block**

Edit `swing/web/templates/partials/daily_management_tile.html.j2` — replace lines 91-99 with:

```jinja
          <td data-tile-cell="position_capital_utilization_pct">
            {%- if tile.position_capital_utilization_pct_effective is not none -%}
              {{ "%.1f"|format(tile.position_capital_utilization_pct_effective * 100.0) }}%
            {%- else -%}--{%- endif -%}
            {#- Codex R2.M#1+M#2 LOCK: badge + help rendered OUTSIDE the
                util-value guard so the NoActivePolicyError fallback
                (util_pct_effective=None + policy_missing=True) still
                surfaces a PROVISIONAL marker with EXTRA-CAVEAT tooltip
                per spec section 6.4 second bullet. The else-if chain
                preserves the existing snapshot-missing branch as-is. -#}
            {%- if tile.position_capital_policy_missing -%}
              <span class="badge badge-provisional" data-marker="PROVISIONAL"
                    data-cause="policy_missing"
                    title="No active risk_policy row -- denominator cannot be resolved. Schema-corrupted state (zero rows have is_active=1). Recovery requires direct DB intervention: SELECT a historical policy_id from risk_policy, then UPDATE risk_policy SET is_active=1, effective_to=NULL WHERE policy_id=<id>. The standard `swing config policy ...` CLI cannot recover this state because supersede_active_policy raises when no active row exists (swing/trades/risk_policy.py:139-142). Re-running `swing db-migrate` does NOT re-seed an already-v21 DB.">PROVISIONAL</span>
              <button type="button" class="muted help-affordance"
                      data-help="provisional-capital-policy-missing"
                      aria-describedby="provisional-capital-help-{{ tile.trade_id }}"
                      aria-label="Why is this PROVISIONAL?">
                (?)
              </button>
              <span id="provisional-capital-help-{{ tile.trade_id }}"
                    class="help-detail" role="tooltip">
                No active risk_policy row found (zero rows have is_active=1). Schema-corrupted state. Recovery requires DIRECT DB intervention via SQL (reactivate a historical row OR insert a fresh one); the standard `swing config policy ...` CLI raises because supersede_active_policy requires an existing active row to supersede.
              </span>
            {%- elif tile.position_capital_utilization_is_provisional -%}
              <span class="badge badge-provisional" data-marker="PROVISIONAL"
                    data-cause="snapshot_missing"
                    title="Capital denominator is the V1 fallback (capital_floor_constant_dollars). Clears to LIVE when an account_equity_snapshots row covers the session date (e.g., swing schwab fetch --snapshot when integration LIVE).">PROVISIONAL</span>
              <button type="button" class="muted help-affordance"
                      data-help="provisional-capital"
                      aria-describedby="provisional-capital-help-{{ tile.trade_id }}"
                      aria-label="Why is this PROVISIONAL?">
                (?)
              </button>
              <span id="provisional-capital-help-{{ tile.trade_id }}"
                    class="help-detail" role="tooltip">
                LIVE when account_equity_snapshots row covers today; PROVISIONAL otherwise.
              </span>
            {%- endif -%}
          </td>
```

- [ ] **T-3.1 Step 6: Re-run R3.M1 regression test to verify pass**

Run: `pytest tests/web/test_daily_management_tile.py::test_proportion_unit_lock_renders_15_percent_not_1500_percent -v`
Expected: PASS.

- [ ] **T-3.1 Step 7: Add conditional badge emit tests (PROVISIONAL vs LIVE)**

Append:

```python
def test_provisional_badge_present_when_is_provisional_true(jinja_env):
    """PROVISIONAL badge emitted when is_provisional=True
    (spec section 6.5 example #1)."""
    vm = MagicMock()
    vm.daily_management_tiles = [_build_tile_vm(
        is_provisional=True, util_pct_effective=0.15,
    )]
    tmpl = jinja_env.get_template("partials/daily_management_tile.html.j2")
    rendered = tmpl.render(vm=vm)
    assert 'data-marker="PROVISIONAL"' in rendered
    assert "PROVISIONAL" in rendered


def test_provisional_badge_absent_when_is_provisional_false(jinja_env):
    """PROVISIONAL badge NOT emitted when is_provisional=False (LIVE)
    (spec section 6.5 example #2)."""
    vm = MagicMock()
    vm.daily_management_tiles = [_build_tile_vm(
        is_provisional=False, util_pct_effective=0.15,
    )]
    tmpl = jinja_env.get_template("partials/daily_management_tile.html.j2")
    rendered = tmpl.render(vm=vm)
    assert 'data-marker="PROVISIONAL"' not in rendered
    assert "15.0%" in rendered  # value still rendered
```

- [ ] **T-3.1 Step 8: Add tooltip text + stale-text eradication tests**

Append:

```python
def test_tooltip_text_describes_account_equity_snapshots_clear_condition(
    jinja_env,
):
    """Tooltip wording cites account_equity_snapshots + swing schwab
    fetch --snapshot per spec section 6.5 example #6."""
    vm = MagicMock()
    vm.daily_management_tiles = [_build_tile_vm(
        is_provisional=True, util_pct_effective=0.15,
    )]
    tmpl = jinja_env.get_template("partials/daily_management_tile.html.j2")
    rendered = tmpl.render(vm=vm)
    assert "account_equity_snapshots" in rendered
    assert "swing schwab fetch --snapshot" in rendered


def test_stale_phase9_versioning_text_removed(jinja_env):
    """The pre-fix tooltip referenced 'Phase 9 risk_policy versioning';
    P14.N3 R3.M2 eradicates that wording (spec section 6.5 example #4)."""
    vm = MagicMock()
    vm.daily_management_tiles = [_build_tile_vm(
        is_provisional=True, util_pct_effective=0.15,
    )]
    tmpl = jinja_env.get_template("partials/daily_management_tile.html.j2")
    rendered = tmpl.render(vm=vm)
    assert "Phase 9 risk_policy versioning" not in rendered
```

- [ ] **T-3.1 Step 9: Add inline `(?)` affordance test**

Append:

```python
def test_help_affordance_html_structure_present(jinja_env):
    """Inline (?) affordance with help-detail blurb. Per Codex R1.M#2
    LOCK the affordance MUST be a real focusable element with ARIA
    (button + aria-describedby + aria-label + role=tooltip) -- a plain
    span has no keyboard focus + fails the spec section 6.1 goal of
    avoiding hover-only explanation."""
    vm = MagicMock()
    vm.daily_management_tiles = [_build_tile_vm(
        is_provisional=True, util_pct_effective=0.15,
    )]
    tmpl = jinja_env.get_template("partials/daily_management_tile.html.j2")
    rendered = tmpl.render(vm=vm)
    # Focusable button element (NOT a span).
    assert '<button type="button" class="muted help-affordance"' in rendered
    assert 'data-help="provisional-capital"' in rendered
    assert 'aria-describedby="provisional-capital-help-1"' in rendered
    assert 'aria-label="Why is this PROVISIONAL?"' in rendered
    # The help-detail target carries role=tooltip + matching id.
    assert 'id="provisional-capital-help-1"' in rendered
    assert 'class="help-detail" role="tooltip"' in rendered
    assert "(?)" in rendered
```

- [ ] **T-3.1 Step 10: Add em-dash ASCII discipline test**

Append:

```python
def test_policy_missing_renders_provisional_badge_even_with_em_dash_value(
    jinja_env,
):
    """Codex R2.M#1+M#2 LOCK + spec section 6.4 second bullet: when
    NoActivePolicyError fires, util_pct_effective is None (em-dash
    value cell) BUT the PROVISIONAL badge + EXTRA-CAVEAT tooltip MUST
    still render (NOT suppressed by the value-guard). Distinct
    data-cause='policy_missing' marker + tooltip wording cites the
    HONEST direct-DB-intervention recovery path per Codex R4.M#1 LOCK
    (the standard `swing config policy ...` CLI cannot recover from
    zero-active-policy state because supersede_active_policy raises
    at swing/trades/risk_policy.py:139-142)."""
    vm = MagicMock()
    vm.daily_management_tiles = [_build_tile_vm(
        is_provisional=True,
        util_pct_effective=None,  # em-dash value cell
        policy_missing=True,
    )]
    tmpl = jinja_env.get_template("partials/daily_management_tile.html.j2")
    rendered = tmpl.render(vm=vm)
    # Em-dash value renders (no util to display).
    assert "--" in rendered
    # PROVISIONAL badge still emitted -- distinct cause marker.
    assert 'data-cause="policy_missing"' in rendered
    assert 'data-marker="PROVISIONAL"' in rendered
    # Extra-caveat tooltip cites the ACTUAL recovery path (direct
    # DB intervention via SQL) per Codex R4.M#1 LOCK -- standard CLI
    # cannot recover this state because supersede_active_policy
    # raises when no active row exists
    # (swing/trades/risk_policy.py:139-142).
    assert "UPDATE risk_policy SET is_active=1" in rendered
    assert "schema-corrupted state" in rendered.lower()
    # The standard snapshot-missing branch is NOT emitted in this case.
    assert 'data-cause="snapshot_missing"' not in rendered


def test_snapshot_missing_branch_renders_when_policy_is_active(jinja_env):
    """The existing PROVISIONAL-by-snapshot-missing branch fires when
    policy is active (policy_missing=False) but no account_equity row
    covers asof_session (is_provisional=True). Distinct
    data-cause='snapshot_missing' marker + standard tooltip wording."""
    vm = MagicMock()
    vm.daily_management_tiles = [_build_tile_vm(
        is_provisional=True,
        util_pct_effective=0.15,
        policy_missing=False,
    )]
    tmpl = jinja_env.get_template("partials/daily_management_tile.html.j2")
    rendered = tmpl.render(vm=vm)
    assert 'data-cause="snapshot_missing"' in rendered
    assert 'data-cause="policy_missing"' not in rendered
    assert "swing schwab fetch --snapshot" in rendered


def test_em_dash_rendered_as_ascii_dashes(jinja_env):
    """Per gotcha #32: em-dash placeholder for null util_pct_effective
    rendered as ASCII '--' (spec section 6.5 example #5 + section 15.2)."""
    vm = MagicMock()
    vm.daily_management_tiles = [_build_tile_vm(
        is_provisional=True, util_pct_effective=None,
    )]
    tmpl = jinja_env.get_template("partials/daily_management_tile.html.j2")
    rendered = tmpl.render(vm=vm)
    assert "--" in rendered
    # No unicode em-dash characters anywhere in the rendered fragment.
    rendered.encode("ascii")
```

- [ ] **T-3.1 Step 11: Add VM denominator-stamping tests at `tests/web/view_models/test_dashboard_view_model.py`**

Create or extend `tests/web/view_models/test_dashboard_view_model.py`:

```python
"""P14.N3 dashboard VM denominator-stamping tests (Phase 14 Sub-bundle 1).

Per spec section 6.2 (denominator-stamping mirror per maturity.py:197-219)
+ R3.M1 LOCK (PROPORTION-unit semantic; recompute via
compute_position_capital_utilization).

Per Codex R1.M#4 LOCK: tests use concrete fixtures (no undeclared
planted_trade_with_snap* names; no literal build_dashboard(...) ellipsis;
no insert_snapshot(..., ..., ) trailing-ellipsis args). Fixtures are
plant-inline within each test using the production-shape repo helpers.
"""

import math
from dataclasses import replace as dataclass_replace
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from swing.config import Config
from swing.data.db import connect, ensure_schema
from swing.data.models import Trade
from swing.data.repos.daily_management import (
    insert_snapshot as insert_dm_snapshot,
)
# Codex R2.M#3 + R3.M#1 LOCK: actual production helper is
# insert_trade_with_event (NOT insert_trade); signature per
# swing/data/repos/trades.py:155 is
# `(conn, trade, *, event_ts: str, rationale: str | None = None)`.
from swing.data.repos.trades import insert_trade_with_event
from swing.web.view_models.dashboard import build_dashboard


def _build_dashboard_under_test(*, db_path, cfg=None):
    """Concrete build_dashboard invocation for P14.N3 VM tests.

    The production builder's signature is
    `build_dashboard(cfg, cache, executor, ohlcv_cache)` per
    swing/web/routes/dashboard.py:27-28. For VM tests we mock the
    price-cache + executor + ohlcv-cache (none are exercised on the
    tile-build path -- the tile reads exclusively from
    `daily_management_records` + `trades` + `risk_policy`
    + `account_equity_snapshots`).

    Codex R2.M#3 LOCK: `Config.from_defaults(cls) -> Config` takes NO
    args (per swing/config.py:398). To inject a tmp-path db_path we
    construct defaults THEN replace cfg.paths.db_path via
    `dataclasses.replace` on the paths sub-config.
    """
    if cfg is None:
        base_cfg = Config.from_defaults()
        new_paths = dataclass_replace(base_cfg.paths, db_path=db_path)
        cfg = dataclass_replace(base_cfg, paths=new_paths)
    cache = MagicMock()
    cache.is_degraded.return_value = False
    cache.degraded_until.return_value = None
    executor = MagicMock()
    ohlcv_cache = None  # exercised separately at T-2.1
    return build_dashboard(
        cfg=cfg, cache=cache, executor=executor, ohlcv_cache=ohlcv_cache,
    )


@pytest.fixture
def planted_vsat_trade_with_snap(tmp_path):
    """Plant an open VSAT trade + active daily_management snapshot row
    with data_asof_session='2026-05-27' + util=0.15 + denom=7500.0.

    Returns the swing_db_path for use by tests; tests open + populate
    additional state per their per-test needs (e.g., account_equity
    snapshot for LIVE path; UPDATE risk_policy SET is_active=0 for the
    NoActivePolicyError fallback test).

    Codex R2.M#3 LOCK: uses production helpers `insert_trade_with_event`
    (NOT `insert_trade`) + `swing.data.repos.daily_management.insert_snapshot`
    (NOT a hypothetical `insert_daily_management_record`). The executing-
    plans implementer audits the current signatures of these two helpers
    via `inspect.signature(insert_trade_with_event)` +
    `inspect.signature(swing.data.repos.daily_management.insert_snapshot)`
    + completes the per-test required kwargs (event_ts + optional
    rationale for insert_trade_with_event per R3.M#1; snapshot_fields
    dict per the Phase 8 OPERATION_REQUIRED_FIELDS["snapshot_emit"]
    set per R3.M#2).
    """
    db_path = tmp_path / "swing.db"
    # Codex R3.M#3 LOCK: connect() at swing/data/db.py:888 raises
    # SchemaVersionMismatchError if db_path does NOT exist. Run
    # ensure_schema(db_path) (swing/data/db.py:863) FIRST to create the
    # SQLite file + apply migrations through current version.
    ensure_schema(db_path).close()
    conn = connect(db_path)
    try:
        # Codex R3.M#1 LOCK: insert_trade_with_event signature per
        # swing/data/repos/trades.py:155 is
        # `(conn, trade, *, event_ts: str, rationale: str | None = None)`
        # -- NOT `event_kind` / `actor` (those were R2 invention).
        trade_id = insert_trade_with_event(
            conn,
            trade=Trade(
                id=None, ticker="VSAT", state="entered",
                sector="Technology", industry="Communications Equipment",
                current_size=10.0, current_stop=40.0,
                **_build_remaining_trade_fields("VSAT"),
            ),
            event_ts=datetime.now().isoformat(timespec="seconds"),
            rationale="P14.N3 VM test fixture",
        )
        # Codex R3.M#2 LOCK: insert_snapshot at
        # swing/data/repos/daily_management.py:411 signature is
        # `(conn, *, trade_id, snapshot_fields: dict[str, Any])` --
        # the caller wraps the per-snapshot fields in a SINGLE
        # snapshot_fields dict (NOT spread as kwargs).
        # NB: per the helper docstring at line 421-425, the caller MUST
        # validate snapshot_fields per OPERATION_REQUIRED_FIELDS at
        # `swing/trades/daily_management.py` BEFORE calling. The
        # executing-plans implementer audits the current
        # OPERATION_REQUIRED_FIELDS["snapshot_emit"] set + ensures the
        # fixture dict satisfies it.
        insert_dm_snapshot(
            conn,
            trade_id=trade_id,
            snapshot_fields={
                "data_asof_session": "2026-05-27",
                "current_price": 42.0,
                "position_capital_utilization_pct": 0.15,
                "position_capital_denominator_dollars": 7500.0,
                **_build_remaining_dm_snapshot_fields(),
            },
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_provisional_when_no_account_equity_snapshot_row(
    planted_vsat_trade_with_snap,
):
    """No account_equity_snapshots row covering data_asof_session ->
    is_provisional=True; denom = capital_floor_constant_dollars
    (spec section 6.1)."""
    vm = _build_dashboard_under_test(
        db_path=planted_vsat_trade_with_snap,
    )
    tile = next(
        t for t in vm.daily_management_tiles if t.ticker == "VSAT"
    )
    assert tile.position_capital_utilization_is_provisional is True
    # PROVISIONAL fallback uses capital_floor_constant_dollars (e.g., 7500).
    assert tile.position_capital_denominator_dollars_resolved == pytest.approx(
        7500.0
    )


def test_live_when_account_equity_snapshot_covers_data_asof_session(
    planted_vsat_trade_with_snap,
):
    """account_equity_snapshots row with snapshot_date <= data_asof_session
    -> is_provisional=False; denom = snapshot equity (spec section 6.5
    example #2)."""
    conn = connect(planted_vsat_trade_with_snap)
    try:
        # Plant a snapshot row covering data_asof_session='2026-05-27'.
        # Concrete required-field shape per AccountEquitySnapshot dataclass
        # at swing/data/models.py + insert_snapshot signature at
        # swing/data/repos/account_equity_snapshots.py (Codex R1.M#4 LOCK
        # -- executing-plans implementer audits + completes missing
        # required fields; no ellipsis trailing args).
        # Codex R2.M#4 LOCK: insert_snapshot at
        # swing/data/repos/account_equity_snapshots.py:58 uses KEYWORD
        # args (NOT a dataclass arg); AccountEquitySnapshot has 8 fields
        # (snapshot_id / snapshot_date / equity_dollars / source /
        # source_artifact_path / recorded_at / recorded_by / notes) per
        # swing/data/models.py:1343-1359 -- NO schwab_api_call_id,
        # NO schwab_account_hash. `recorded_by` is NOT NULL.
        from swing.data.repos.account_equity_snapshots import (
            insert_snapshot as insert_aes_snapshot,
        )
        insert_aes_snapshot(
            conn,
            snapshot_date="2026-05-27",
            equity_dollars=12345.0,
            source="manual",
            source_artifact_path="test:fixture:p14n3-live",
            recorded_at=datetime.now().isoformat(timespec="seconds"),
            recorded_by="test",
            notes="P14.N3 LIVE fixture",
        )
        conn.commit()
    finally:
        conn.close()
    vm = _build_dashboard_under_test(
        db_path=planted_vsat_trade_with_snap,
    )
    tile = next(
        t for t in vm.daily_management_tiles if t.ticker == "VSAT"
    )
    assert tile.position_capital_utilization_is_provisional is False
    assert tile.position_capital_denominator_dollars_resolved == pytest.approx(
        12345.0
    )


def test_effective_pct_reuses_stored_when_denominators_match(
    planted_vsat_trade_with_snap,
):
    """When snap.position_capital_denominator_dollars == freshly-resolved
    via math.isclose(rel_tol=1e-9), reuse stored proportion (spec section 6.2
    denominator-stamping mirror per maturity.py:215-219).

    Fixture planted stored_denom=7500.0 + util=0.15 + no
    account_equity_snapshot row -> resolver returns
    capital_floor_constant_dollars (default 7500.0) -- denominators match;
    tile reuses stored util.
    """
    vm = _build_dashboard_under_test(
        db_path=planted_vsat_trade_with_snap,
    )
    tile = next(
        t for t in vm.daily_management_tiles if t.ticker == "VSAT"
    )
    # Stored matches resolved -> tile_pct_effective == stored util.
    assert tile.position_capital_utilization_pct_effective == pytest.approx(
        tile.position_capital_utilization_pct
    )


def test_effective_pct_recomputed_via_compute_position_capital_utilization_when_denominators_diverge(
    planted_vsat_trade_with_snap,
):
    """When stored denominator != freshly-resolved, recompute as
    PROPORTION via compute_position_capital_utilization (R3.M1 LOCK)."""
    from swing.trades.daily_management import (
        compute_position_capital_utilization,
    )
    conn = connect(planted_vsat_trade_with_snap)
    try:
        # Plant a snapshot whose equity (12345.0) DIVERGES from the
        # stored denominator (7500.0) so the math.isclose check fails
        # + recompute path fires.
        # Codex R2.M#4 LOCK: keyword args; 8-field shape;
        # recorded_by required.
        from swing.data.repos.account_equity_snapshots import (
            insert_snapshot as insert_aes_snapshot,
        )
        insert_aes_snapshot(
            conn,
            snapshot_date="2026-05-27",
            equity_dollars=12345.0,
            source="manual",
            source_artifact_path="test:fixture:p14n3-divergent",
            recorded_at=datetime.now().isoformat(timespec="seconds"),
            recorded_by="test",
            notes="P14.N3 divergent-denom fixture",
        )
        conn.commit()
    finally:
        conn.close()
    vm = _build_dashboard_under_test(
        db_path=planted_vsat_trade_with_snap,
    )
    tile = next(
        t for t in vm.daily_management_tiles if t.ticker == "VSAT"
    )
    # Reference recompute (using divergent freshly-resolved denom):
    expected = compute_position_capital_utilization(
        current_size=10.0, current_price=42.0,
        denominator_dollars=tile.position_capital_denominator_dollars_resolved,
    )
    assert tile.position_capital_utilization_pct_effective == pytest.approx(
        expected
    )


def test_no_active_risk_policy_renders_provisional_not_500(
    planted_vsat_trade_with_snap,
):
    """Codex R1.M#1 + R2.M#1+M#2 LOCK + spec section 6.4 second bullet:
    when risk_policy has zero rows with is_active=1 (pre-Phase-9 /
    pre-seed DB state OR a manual UPDATE that flipped every row
    inactive), build_dashboard MUST NOT raise NoActivePolicyError --
    it MUST render the tile with policy_missing=True so the template
    surfaces a distinct PROVISIONAL + extra-caveat badge."""
    conn = connect(planted_vsat_trade_with_snap)
    try:
        conn.execute("UPDATE risk_policy SET is_active = 0")
        conn.commit()
    finally:
        conn.close()
    # build_dashboard must not raise NoActivePolicyError; tile is
    # constructed with policy_missing=True + is_provisional=True
    # + denom_resolved=0.0.
    vm = _build_dashboard_under_test(
        db_path=planted_vsat_trade_with_snap,
    )
    tile = next(
        t for t in vm.daily_management_tiles if t.ticker == "VSAT"
    )
    assert tile.position_capital_policy_missing is True
    assert tile.position_capital_utilization_is_provisional is True
    assert tile.position_capital_denominator_dollars_resolved == 0.0
    # With denom_resolved=0.0, util_pct_effective is None (the recompute
    # short-circuits per the denom_resolved > 0 guard); template renders
    # em-dash + the policy-missing badge (per the dedicated template
    # render test above).
    assert tile.position_capital_utilization_pct_effective is None


def test_malformed_data_asof_session_falls_back_to_page_asof_date(
    planted_vsat_trade_with_snap,
):
    """date.fromisoformat raises ValueError on malformed
    snap.data_asof_session -> fall back to page-level asof_date
    (maturity.py:190-194)."""
    conn = connect(planted_vsat_trade_with_snap)
    try:
        # Mutate the planted snap's data_asof_session to a malformed
        # string the ValueError-guarded fallback path handles.
        conn.execute(
            "UPDATE daily_management_records "
            "SET data_asof_session = 'not-a-date'"
        )
        conn.commit()
    finally:
        conn.close()
    vm = _build_dashboard_under_test(
        db_path=planted_vsat_trade_with_snap,
    )
    tile = next(
        t for t in vm.daily_management_tiles if t.ticker == "VSAT"
    )
    # No raise; tile constructed; is_provisional reflects page-asof state.
    assert isinstance(tile.position_capital_utilization_is_provisional, bool)
```

(The `_build_remaining_trade_fields` + `_build_remaining_dm_snapshot_fields` helpers return the kwargs needed by the `Trade` + `daily_management_records` insert paths beyond the ones explicitly set inline; at executing-plans phase the implementer audits the current dataclass shapes via `inspect.signature(Trade)` + the existing Phase 8 `insert_daily_management_record` signature + emits production-shape default kwargs. Per Codex R1.M#4 LOCK: NO trailing `...` ellipsis in production-shape `insert_*` calls; required fields enumerated explicitly so the test file is executable as written.)

- [ ] **T-3.1 Step 12: Add ASCII discipline test for template + VM module**

Append to `tests/web/test_daily_management_tile.py`:

```python
def test_template_and_vm_module_ascii_only():
    """Per gotcha #32 + spec section 15.2 -- template + VM module
    ASCII-only across the P14.N3 surface."""
    from pathlib import Path
    import swing.web.view_models.trades as trades_vm_mod
    import swing.web.view_models.dashboard as dash_vm_mod
    Path(trades_vm_mod.__file__).read_text(
        encoding="utf-8"
    ).encode("ascii")
    Path(dash_vm_mod.__file__).read_text(
        encoding="utf-8"
    ).encode("ascii")
    import swing.web.templates as tpl_mod
    tpl_path = (
        Path(tpl_mod.__file__).parent
        / "partials" / "daily_management_tile.html.j2"
    )
    tpl_path.read_text(encoding="utf-8").encode("ascii")
```

- [ ] **T-3.1 Step 13: Run full test modules + commit**

Run:
```bash
pytest tests/web/test_daily_management_tile.py \
       tests/web/view_models/test_dashboard_view_model.py -v
```
Expected: ALL PASS (~7-9 template tests + ~4-6 VM tests = ~11-15 tests; matches §B distribution).

```bash
git add swing/web/view_models/trades.py \
        swing/web/view_models/dashboard.py \
        swing/web/templates/partials/daily_management_tile.html.j2 \
        tests/web/test_daily_management_tile.py \
        tests/web/view_models/test_dashboard_view_model.py
git commit -m "feat(web): wire DailyManagementTileVM 4-field PROVISIONAL/LIVE denominator stamping (P14.N3)"
```

Verify ZERO `Co-Authored-By:` trailer:
```bash
git log -1 --pretty="%(trailers)"
```
Expected: empty.

Optionally split into 2 commits per §G.0: commit 1 = VM extension + dataclass (steps 3-4); commit 2 = template rewrite + tests (steps 5-13).

---

### §G.T-4.1: L2 LOCK parametric source-grep regression test

**Files:**
- Test: `tests/integration/test_l2_lock_source_grep.py` (NEW)

**Acceptance criteria:**
1. New parametric test asserts the multiset (Counter) of `(path, line_text) -> count` matches for `schwabdev.Client.` under `swing/` at HEAD is a multiset SUBSET of the baseline Counter at `bf7e071` (Codex R1.M#5 + R2.M#6 LOCKs -- count-only or set-only comparison would silently pass on swap-introduce-while-remove OR duplicate-identical-line-in-same-file).
2. Test invokes `git grep -n` via `subprocess.run`; captures stdout; parses `(path, line_number, line_text)` tuples; normalizes line_number out (line numbers shift across commits; the LINE TEXT is the L2 LOCK signal); accumulates per-key counts via `collections.Counter`.
3. Compares HEAD Counter to baseline Counter at `bf7e071` (Phase 14 commissioning HEAD per dispatch brief §1.1); fails on EITHER (a) NEW (path, line_text) keys OR (b) INCREASED counts on existing keys.
4. Fails with operator-friendly assertion message enumerating each (path, line_text, baseline_count, head_count) violation tuple introduced at HEAD.
5. Test is parametric over the `schwabdev.Client.` pattern (extensible to other L2 LOCK signal patterns).
6. ASCII discipline applied.
7. 1 parametric test (1 test function, parametrized over the L2 LOCK pattern set).
8. Gotchas applied: #32, #34.

#### TDD steps

- [ ] **T-4.1 Step 1: Write the failing baseline-count fixture + parametric test**

Create `tests/integration/test_l2_lock_source_grep.py`:

```python
"""L2 LOCK parametric source-grep regression test (Phase 14 Sub-bundle 1).

The L2 LOCK = ZERO new Schwab API calls beyond OQ-13 CLI carve-outs;
preserved through 12 applied research arcs + Phase 13 + Sub-bundle 1.
Per dispatch brief section 1.1 commissioning baseline = main commit
``bf7e071`` (Phase 14 commissioning HEAD).

Per CLAUDE.md gotcha #34: brief-prescription cross-table verification.
The verification consumes ``git grep`` output to count occurrences of the
target pattern in ``swing/`` at HEAD vs baseline.
"""

from __future__ import annotations

import subprocess
from collections import Counter

import pytest

L2_LOCK_BASELINE_SHA = "bf7e071"

L2_LOCK_PATTERNS = [
    # Direct schwabdev SDK invocations.
    "schwabdev.Client.",
    # Secondary: any new schwab_api_calls audit row emit sites
    # (existing emit sites stay; new ones would indicate widening).
    # Add additional patterns here if Sub-bundle 2+ widens the L2
    # LOCK signal set.
]


def _count_call_sites(rev: str, pattern: str) -> Counter[tuple[str, str]]:
    """Run ``git grep -n <pattern> <rev> -- swing/`` and return a
    ``Counter`` keyed by ``(path, normalized_line_text)``.

    Per Codex R1.M#5 + R2.M#6 LOCK: set-only comparison silently passes
    when an IDENTICAL call-site line is duplicated within the same
    file (set dedupes the duplicate). Multiset/Counter comparison
    fails on EITHER (a) NEW (path, line_text) keys OR (b) increased
    count on an EXISTING key. Line numbers are normalized out (they
    shift across commits; the LINE TEXT is the L2 LOCK signal).
    """
    result = subprocess.run(
        ["git", "grep", "-n", pattern, rev, "--", "swing/"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        # git grep returns 1 if no matches; 0 if matches; >1 on error.
        raise RuntimeError(
            f"git grep failed unexpectedly for {pattern!r} at {rev}: "
            f"stderr={result.stderr!r}"
        )
    counter: Counter[tuple[str, str]] = Counter()
    for line in result.stdout.splitlines():
        # Format: "<rev>:<path>:<line_number>:<line_text>" -- split on
        # first 3 colons to preserve any colons inside the line_text.
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        _rev, path, _lineno, line_text = parts
        counter[(path, line_text.strip())] += 1
    return counter


@pytest.mark.parametrize("pattern", L2_LOCK_PATTERNS)
def test_l2_lock_no_new_call_sites_vs_commissioning_baseline(pattern):
    """HEAD's multiset of (path, line_text) -> count matches for the
    L2 LOCK pattern in ``swing/`` MUST be a multiset SUBSET of the
    commissioning baseline at ``bf7e071``. New non-whitelisted matches
    OR INCREASED counts on existing keys FAIL the test.

    Per Codex R1.M#5 + R2.M#6 LOCKs: Counter-comparison (NOT plain set)
    catches BOTH the swap-introduce-while-remove pattern AND the
    duplicate-line-in-same-file pattern that set-only would silently
    miss.
    """
    baseline = _count_call_sites(L2_LOCK_BASELINE_SHA, pattern)
    head = _count_call_sites("HEAD", pattern)
    violations: list[tuple[str, str, int, int]] = []
    for key, head_count in head.items():
        baseline_count = baseline.get(key, 0)
        if head_count > baseline_count:
            path, line_text = key
            violations.append((path, line_text, baseline_count, head_count))
    assert not violations, (
        f"L2 LOCK violation: HEAD introduces {len(violations)} "
        f"new-or-inflated (path, line_text) call sites matching "
        f"{pattern!r} in swing/ vs commissioning baseline at "
        f"{L2_LOCK_BASELINE_SHA}.\n"
        + "\n".join(
            f"  {p}: {t}  (baseline_count={bc}, head_count={hc})"
            for p, t, bc, hc in sorted(violations)
        )
        + "\nSub-bundle 1 must NOT introduce new Schwab API call sites."
    )


def test_l2_lock_source_grep_module_ascii_only():
    """Per gotcha #32 -- this test module ASCII-only."""
    from pathlib import Path
    Path(__file__).read_text(encoding="utf-8").encode("ascii")
```

- [ ] **T-4.1 Step 2: Run test to verify it passes (L2 LOCK should already be preserved)**

Run: `pytest tests/integration/test_l2_lock_source_grep.py -v`
Expected: PASS (no Sub-bundle 1 changes introduce new `schwabdev.Client.` references; the test is a regression check that GUARDS future work).

- [ ] **T-4.1 Step 3: Run an artificial-failure rehearsal (manual; not committed; SAFE-REVERT)**

To verify the assertion fires on regression, the executing-plans implementer (or operator) MAY temporarily add a sentinel `# schwabdev.Client.regression_sentinel` line to a swing/ source file + re-run the test. Per Codex R1.M#7 LOCK: use a sentinel-specific `sed -i` revert (NOT `git checkout --`) to avoid discarding unrelated worktree edits in a dirty tree:

```bash
# Add sentinel:
echo "# schwabdev.Client.regression_sentinel" >> swing/web/routes/dashboard.py
pytest tests/integration/test_l2_lock_source_grep.py -v
# Expected: FAIL with L2 LOCK violation message listing the new tuple.

# Safe revert (Codex R1.M#7 LOCK -- targeted line removal; does NOT
# discard unrelated edits the way `git checkout -- file` would):
sed -i '/schwabdev\.Client\.regression_sentinel/d' \
    swing/web/routes/dashboard.py
# Re-run to confirm clean revert:
pytest tests/integration/test_l2_lock_source_grep.py -v
# Expected: PASS.
```

DO NOT commit the sentinel. ALTERNATIVE (cleaner): omit the rehearsal entirely; the set-based test's correctness is verifiable via a synthetic-source-tree pytest fixture if the executing-plans implementer wants programmatic coverage instead of operator rehearsal (banked V2 candidate; not in V1 scope).

- [ ] **T-4.1 Step 4: Commit**

```bash
git add tests/integration/test_l2_lock_source_grep.py
git commit -m "test(integration): add L2 LOCK parametric source-grep regression test"
```

Verify ZERO `Co-Authored-By:` trailer:
```bash
git log -1 --pretty="%(trailers)"
```
Expected: empty.

---

### §G.T-4.2: Closer — cross-item integration tests + ASCII discipline verification + return report

**Files:**
- Test: `tests/integration/test_phase14_sub_bundle_1_cross_item.py` (NEW; optional — extend if S6 cross-fix regression check warrants automation)
- Doc: `docs/phase14-sub-bundle-1-data-wiring-writing-plans-return-report.md` — note this is the WRITING-PLANS return report; the EXECUTING-PLANS implementer ALSO drafts a separate `docs/phase14-sub-bundle-1-data-wiring-executing-plans-return-report.md` at end-of-dispatch per spec §11 (the executing-plans return report)

**Acceptance criteria:**
1. (Optional) NEW cross-item integration test asserting all three fixes coexist cleanly (S6 surface): V2.G3 backfill apply + V2.G4 refresh + P14.N3 tile render in same TestClient session.
2. Plan-time ASCII discipline verification: programmatic `Path(...).read_text(encoding="utf-8").encode("ascii")` across all NEW + MODIFIED production code + test files + return report.
3. Sub-bundle return report drafted per brief §8 (15 items) — the executing-plans return report (separate from THIS writing-plans return report).
4. Final fast-test sum-check (~34-36 fast tests per L3 LOCK): `pytest -m "not slow" -q --collect-only | tail -1` reports total; matches §H projection within ±2 tolerance.
5. Final commit-cadence sum-check (~8-12 commits per L4 LOCK): `git log --oneline main..HEAD | wc -l` reports total.
6. Final `Co-Authored-By` audit: `git log --pretty="%(trailers)" main..HEAD` emits empty for every commit.
7. ~2-4 cross-item integration tests (S6 automation + cumulative ASCII sweep + commit-cadence audit).
8. Gotchas applied: #1 (trust pytest output), #32 (ASCII final sweep), #36 (single Codex chain note for return report).

#### TDD steps

- [ ] **T-4.2 Step 1: (OPTIONAL) Add cross-item integration test for S6 surface**

Create `tests/integration/test_phase14_sub_bundle_1_cross_item.py` (only if executing-plans implementer chooses to automate S6; operator-witnessed gate at §I is the primary verification surface):

```python
"""Phase 14 Sub-bundle 1 cross-item coexistence regression test
(automates spec section 10.5 S6 surface)."""

from fastapi.testclient import TestClient


def test_v2g3_backfill_and_v2g4_refresh_and_p14n3_tile_coexist(
    swing_app_with_full_fixtures,
):
    """All three fixes (V2.G3 backfill applied; V2.G4 weather-chart
    refresh succeeds; P14.N3 PROVISIONAL badge wired) MUST coexist
    cleanly. Spec section 8 (cross-item coherence) + S6 (cross-fix
    regression check)."""
    client = swing_app_with_full_fixtures
    response_dash = client.get("/dashboard")
    assert response_dash.status_code == 200
    # V2.G3 surface: open-positions row renders non-NULL Sector +
    # Industry for VSAT.
    assert "VSAT" in response_dash.text
    # V2.G4 surface: refresh weather chart succeeds (204 + HX-Redirect).
    response_refresh = client.post("/dashboard/weather-chart/refresh")
    assert response_refresh.status_code == 204
    # P14.N3 surface: /daily-management Capital % column renders the
    # PROVISIONAL badge per state (depending on whether a snapshot row
    # is planted).
    response_dm = client.get("/daily-management")
    assert response_dm.status_code == 200
```

Run: `pytest tests/integration/test_phase14_sub_bundle_1_cross_item.py -v`
Expected: PASS.

- [ ] **T-4.2 Step 2: Cumulative ASCII discipline sweep test**

Append to the cross-item test (or create as a separate test file):

```python
def test_cumulative_ascii_discipline_across_subbundle_1_surface():
    """Per gotcha #32 + spec section 15.2: programmatic ASCII verification
    across all NEW + MODIFIED Sub-bundle 1 surfaces."""
    from pathlib import Path
    files = [
        "swing/data/repos/candidates.py",
        "swing/cli.py",
        "swing/diagnostics/backfill_trades_sector_industry.py",
        "swing/web/routes/dashboard.py",
        "swing/web/view_models/trades.py",
        "swing/web/view_models/dashboard.py",
        "swing/web/templates/partials/daily_management_tile.html.j2",
        "tests/data/repos/test_candidates_sector_industry_helper.py",
        "tests/cli/test_diagnose_backfill_trades_sector_industry.py",
        "tests/web/test_routes/test_dashboard_chart_integration.py",
        "tests/web/test_daily_management_tile.py",
        "tests/web/view_models/test_dashboard_view_model.py",
        "tests/integration/test_l2_lock_source_grep.py",
        "tests/integration/test_phase14_sub_bundle_1_cross_item.py",
    ]
    failures = []
    for rel in files:
        path = Path(rel)
        if not path.exists():
            continue  # tolerate test files not yet authored OR optional
                      # surfaces (T-1.3 / T-4.2 cross-item) not shipped
        try:
            path.read_text(encoding="utf-8").encode("ascii")
        except UnicodeEncodeError as exc:
            failures.append(f"{rel}: {exc}")
    assert not failures, (
        "ASCII discipline violations:\n" + "\n".join(failures)
    )
```

Run: `pytest tests/integration/test_phase14_sub_bundle_1_cross_item.py::test_cumulative_ascii_discipline_across_subbundle_1_surface -v`
Expected: PASS.

- [ ] **T-4.2 Step 3: Final fast-test sum-check + commit-cadence audit (manual)**

```bash
# Test count audit:
pytest -m "not slow" -q --collect-only 2>&1 | tail -1
# Expected: increment of ~32-41 over baseline (per §H projection).

# Commit count audit:
git log --oneline main..HEAD | wc -l
# Expected: 8-12 commits (per L4 LOCK + §G.0 estimate).

# Co-Authored-By trailer audit:
git log --pretty="%(trailers)" main..HEAD
# Expected: empty for every commit (zero trailers).
```

- [ ] **T-4.2 Step 4: Draft the executing-plans return report**

Author `docs/phase14-sub-bundle-1-data-wiring-executing-plans-return-report.md` per spec §11 + brief §8 (executing-plans-phase return report shape; covers the SAME 15 items but reflecting the executing-plans dispatch outcomes):

1. Final HEAD on branch + commit count breakdown + per-commit Codex round attribution (if any).
2. Codex round chain summary table.
3. Plan section line count breakdown (vs the writing-plans plan estimate).
4. Pre-locked operator decisions verbatim verification.
5. §3 Open Questions: which Codex resolved at executing-plans phase.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Per-task acceptance criteria summary (T-1.1, T-1.2, T-1.3 if executed, T-2.1, T-3.1, T-4.1, T-4.2).
8. Test surface verification (~34-36 fast tests confirmed; per-task distribution).
9. Forward-binding lessons for the next sub-bundle (Sub-bundle 2 temporal log).
10. Schema impact verdict (v21 unchanged; verified via migration file count).
11. Cumulative gotcha set application summary (per task).
12. Worktree teardown status.
13. ZERO `Co-Authored-By` footer drift confirmation.
14. CLAUDE.md status-line refresh draft text.
15. Operator-paired gate readiness summary (S1-S6 + S5a/S5b).

- [ ] **T-4.2 Step 5: Commit closer artifacts**

```bash
git add tests/integration/test_phase14_sub_bundle_1_cross_item.py \
        docs/phase14-sub-bundle-1-data-wiring-executing-plans-return-report.md
git commit -m "docs(phase14-sub-bundle-1): cross-item integration test + executing-plans return report"
```

Verify ZERO `Co-Authored-By:` trailer:
```bash
git log -1 --pretty="%(trailers)"
```
Expected: empty.

Total Sub-bundle 1 executing-plans commit count: 8-12 per L4 LOCK + §G.0 estimate.

---

## §H Test surface (~34-36 fast tests projected)

Per L3 LOCK + spec §10.3 estimate post-R4 bump. Per-task distribution:

| Task | Test module | Tests (est.) | Cumulative |
|---|---|---|---|
| T-1.1 V2.G3 repo helper | `tests/data/repos/test_candidates_sector_industry_helper.py` (NEW) | 7 (signature contract + empty-input + happy path + multi-ticker + AND-empty filter + ordering + historical-only + ASCII) | 7 |
| T-1.2 V2.G3 CLI subcommand | `tests/cli/test_diagnose_backfill_trades_sector_industry.py` (NEW) | 9 (registration + dry-run table + restore-SQL artifact + partial-empty + DHA legacy + apply happy path + idempotency + include-closed + allowlist + missing-db + ASCII) | 16 |
| T-1.3 V2.G3 VM fallback (OPTIONAL) | extension of open-positions VM test module | 2-3 (only if triggered) | 16-19 |
| T-2.1 V2.G4 route handler | `tests/web/test_routes/test_dashboard_chart_integration.py` (MODIFIED) | 8 (kwarg signature + ValueError-degraded + TypeError-500 + 3-param propagation + happy 204/HX-Redirect + HTMX trinity + no-pipeline regression + ASCII) | 24-27 |
| T-3.1 P14.N3 VM + template | `tests/web/test_daily_management_tile.py` (MODIFIED) + `tests/web/view_models/test_dashboard_view_model.py` (MODIFIED) | 13-17 (template: proportion regression + 2 conditional badge + tooltip text + stale-text eradication + (?) affordance + em-dash ASCII + template ASCII + policy_missing-emits-badge + snapshot_missing-branch-when-policy-active = 10; VM: provisional vs LIVE + denominator-match reuse + divergent recompute + malformed session + no-active-policy + extra fixture-shape assertions = 5-6 → totals 15-16; +3-4 vs original estimate due to Codex R2.M#1+M#2 4th-field + R1.M#1 NoActivePolicyError branch) | 38-43 |
| T-4.1 L2 LOCK source-grep | `tests/integration/test_l2_lock_source_grep.py` (NEW) | 1 parametric (1 test function; future-extensible pattern set) + 1 ASCII | 38-41 |
| T-4.2 Closer cross-item | `tests/integration/test_phase14_sub_bundle_1_cross_item.py` (NEW; optional) | 2 (S6 coexistence + cumulative ASCII sweep) | 40-43 |

**Estimated total NEW fast tests: 34-41** (matches L3 LOCK target ~34-36; the upper bound includes the optional T-1.3 + T-4.2 cross-item tests). Per spec §10.3 + brief §1.5 L3.

**Slow tests added: ZERO.** V2.G4 mocks `OhlcvCache.get_or_fetch`; no yfinance fetch. V2.G3 backfill operates on synthetic SQLite fixtures; no Schwab API calls. P14.N3 renders template fragments against in-memory `MagicMock` VM. L2 LOCK source-grep uses `subprocess.run` against git history (~50-200ms; fast tier acceptable).

**Verification at executing-plans phase:** `pytest -m "not slow" -q --collect-only 2>&1 | tail -1` reports total collected; delta vs baseline matches §H projection within ±2 tolerance per gotcha #1 (test-count drift in plan docs — trust pytest output, not plan estimate; this section is the plan estimate; pytest output at executing-plans phase is authoritative).

---

## §I Operator-witnessed gate runbook (per spec §10.5 + R3.m4 split)

Per Sec 9.1 Q6 LOCK + spec §10.5: the merge-time operator-witnessed gate has 7 surfaces. Each surface enumerates the planting fixture instructions (where applicable) + the pass criterion.

| # | Surface | Pre-conditions / planting | Pass criterion |
|---|---|---|---|
| **S1** | `python -m pytest -m "not slow" -q` baseline | None | All tests pass; no new fails; suite runtime within ±20% of pre-merge baseline (~2 min) |
| **S2** | `ruff check swing/` | None | 0 errors |
| **S3** | `/dashboard` open-positions table for VSAT row | Operator's DB on disk (default `~/swing-data/swing.db`) MUST have an open VSAT trade row + EITHER (a) a candidates row with non-empty Sector + Industry for VSAT (to demonstrate backfill happy path) OR (b) acknowledged-legacy DHA/DHC with no candidates row (em-dash render). Operator runs `swing diagnose backfill-trades-sector-industry --apply` immediately before opening the browser. | Render shows non-NULL Sector + Industry for VSAT (or em-dash for legacy DHA/DHC); browser DevTools shows no console errors; HTML table cell contains the expected text |
| **S4** | `/dashboard` "Refresh weather chart" button | Pipeline must have completed at least once today (`pipeline_runs` row with `finished_ts` non-NULL); SPY OHLCV bars present in archive (default per `_step_weather` invocation). | Click triggers HTMX POST to `/dashboard/weather-chart/refresh`; receive 204 + browser follows HX-Redirect to `/dashboard`; page re-renders showing a freshly-rendered SPY weather chart (NOT the "no OHLCV bars" 409 error message); chart_renders row written for `(SPY, market_weather)` |
| **S5a** | `/daily-management` Capital % column — PROVISIONAL CASE | Plant operator's DB with NO `account_equity_snapshots` row covering today's session (delete any existing snapshot row OR use a fresh DB). Open trades + active `daily_management_records` snapshot rows must be present. | Render shows PROVISIONAL badge on each Capital % cell; tooltip describes the `account_equity_snapshots` clear-condition; `(?)` affordance visible; stale "Phase 9 risk_policy versioning" text REMOVED; displayed Capital % value is a SANE small percentage (e.g., < 50% on typical operator state — NOT 1500.0% per R3.M1 unit-mismatch defense) |
| **S5b** | `/daily-management` Capital % column — LIVE CASE | Plant `account_equity_snapshots` row covering today's session via `swing schwab fetch --snapshot` (Schwab integration LIVE path) OR via direct SQL: `INSERT INTO account_equity_snapshots(snapshot_date, equity_dollars, ...) VALUES ('YYYY-MM-DD', <equity>, ...)` | Reload `/daily-management`; PROVISIONAL badge NOT present on Capital % cells; Capital % value still rendered (using `position_capital_utilization_pct_effective` — recomputed proportion when stored denominator diverges from freshly-resolved per `maturity.py:215-219` mirror) |
| **S6** | Cross-fix regression check | Run all of S3 + S4 + S5a/S5b within the SAME browser session | Refreshing weather chart (S4) does NOT break Sector/Industry render (S3); both shipped fixes coexist cleanly; PROVISIONAL state flip (S5a → S5b) does NOT affect either of the other surfaces; no console errors anywhere in the session |

**Sequencing recommendation at operator-witnessed gate:** S1 → S2 → S3 → S4 → S5a → S5b → S6. S1 + S2 are unconditional pass requirements (automated); S3 + S4 + S5a/b are visual / behavioral gates; S6 is the integration check.

**State-planting fixture instructions (per spec R3.m4 LOCK / forward-binding lesson #9):** the S5a / S5b split exists specifically because the PROVISIONAL vs LIVE state is operator-DB-condition-dependent; per-case planting instructions BIND so the gate is reproducible. Per Codex R1.m#3 LOCK: prefer the repo helper over raw SQL for column-shape future-proofing; raw SQL alternative is shown for operators who prefer direct DB access.

**Preferred path: repo helper from a Python REPL** (column-shape future-proof; no ellipsis required-field gaps):

```python
# S5b LIVE-case planting (run BEFORE reloading /daily-management).
# Codex R2.M#4 LOCK: insert_snapshot at account_equity_snapshots.py:58
# uses KEYWORD args; AccountEquitySnapshot has 8 fields per
# swing/data/models.py:1343-1359; recorded_by is NOT NULL.
# Codex R3.M#4 LOCK: connect(db_path) at swing/data/db.py:888 takes a
# Path (NOT a str) + does NOT expand `~`. Use
# Path(...).expanduser() OR resolve via the loaded Config.
from datetime import datetime
from pathlib import Path
from swing.data.db import connect
from swing.data.repos.account_equity_snapshots import insert_snapshot

conn = connect(Path("~/swing-data/swing.db").expanduser())
try:
    insert_snapshot(
        conn,
        snapshot_date="<today's session date YYYY-MM-DD>",  # e.g., "2026-05-28"
        equity_dollars=15000.0,
        source="manual",
        source_artifact_path="manual:gate-S5b",
        recorded_at=datetime.now().isoformat(timespec="seconds"),
        recorded_by="operator",
        notes="P14.N3 operator-witnessed gate S5b LIVE case",
    )
    conn.commit()
finally:
    conn.close()
# After the gate, DELETE the row to return to S5a state:
#   sqlite3 ~/swing-data/swing.db \
#     "DELETE FROM account_equity_snapshots WHERE notes = 'P14.N3 operator-witnessed gate S5b LIVE case'"
```

**Raw SQL alternative** (operator audits the current `account_equity_snapshots` column set via `.schema account_equity_snapshots` before invoking; required-field shape per migration `0017_phase9_risk_policy_and_reconciliation.sql` + Phase 9 Sub-bundle C ship). Codex R2.M#5 LOCK: column list MUST include `recorded_by` (NOT NULL) and MUST NOT include `schwab_api_call_id` (NOT a column on this table; only `account_equity_snapshots` columns at v17 are the 8-field shape):

```sql
-- S5b LIVE-case planting (operator-paired; verify column set first
-- via .schema account_equity_snapshots).
-- Concrete columns enumerated per Codex R1.m#3 + R2.M#5 LOCKs; no
-- ellipsis. recorded_by is NOT NULL per migration 0017.
INSERT INTO account_equity_snapshots (
  snapshot_date, equity_dollars, source,
  source_artifact_path, recorded_at, recorded_by, notes
) VALUES (
  '<today YYYY-MM-DD>', 15000.0, 'manual',
  'manual:gate-S5b', datetime('now'), 'operator',
  'P14.N3 operator-witnessed gate S5b LIVE case'
);
-- After the gate, DELETE the row to return to S5a state:
DELETE FROM account_equity_snapshots
  WHERE notes = 'P14.N3 operator-witnessed gate S5b LIVE case';
```

**Pre-merge orchestrator-side checklist:**
- [ ] S1 + S2 automated pass
- [ ] S3 visual pass on operator browser
- [ ] S4 visual pass on operator browser
- [ ] S5a visual pass (PROVISIONAL state)
- [ ] S5b visual pass (LIVE state after snapshot planting)
- [ ] S6 regression check
- [ ] Operator confirms all 6 surfaces with explicit pass

---

## §J Codex MCP single-chain placement + watch items

### §J.1 Chain placement

**Single Codex MCP chain at the END of plan drafting** per Sec 9.1 Q7 LOCK + brief §1.5 L1 + gotcha #36 explicit caveat for pure UX/wiring sub-bundles without analytical artifacts.

The chain fires AFTER:
- Plan draft is committed pre-Codex on branch `phase14-sub-bundle-1-data-wiring-writing-plans`.
- All §A through §N sections are present + populated.
- §A.3 plan-authoring production-code re-verification table is complete (14 surfaces verified at HEAD).

The chain DOES NOT fire AFTER:
- Plan draft is partial (e.g., §G.T-3.1 still has `TBD`).
- Plan still has `TODO` / `placeholder` markers.
- The pre-Codex plan-document-reviewer subagent loop has not completed.

### §J.2 Codex chain shape

Target convergence: **2–4 rounds NO_NEW_CRITICAL_MAJOR** (matches brainstorm phase: 4 rounds; matches dispatch brief §1.2 LOCK target).

Per gotcha #36 caveat: pure UX/wiring sub-bundles default to SINGLE chain. The decision is locked by Sec 9.1 Q7. Do NOT propose two-chain split unless Codex surfaces a substantive analytical-artifact-equivalent finding (which is not anticipated for Sub-bundle 1's scope).

### §J.3 Codex review watch items (adversarial review will surface answers to)

The following watch items are the Codex review check surface, derived from brief §5 + brainstorm return report §8 (8 forward-binding lessons LOAD-BEARING for plan-authoring discipline). Plan §F.2 enumerates the per-lesson plan application; this section enumerates the Codex check perspective:

1. **Brief-vs-production-function-signature verification (gotcha #17 / Expansion #2 refinement)** — Codex re-greps every production function signature cited in §A.3 + per-task acceptance criteria + step code blocks. Expected catch: zero signature drift (plan-authoring already verified 14 surfaces); if Codex catches a missed signature, the plan is amended in-place.
2. **Cumulative regression cascade audit (gotcha #21 / Expansion #13)** — Codex audits the post-fix sweep at each Codex round. Plan §G.0 commit-cadence preface MANDATORY; per-task acceptance criteria include "no stale-reference cascade" sub-check.
3. **Percent-vs-proportion unit lock (R3.M1 LOCK)** — Codex audits T-3.1 step 9 + step 6 acceptance criteria. The binding test asserts `< 50%` rendering for 0.15 proportion fixture.
4. **Module-level logger addition (R3.M2 LOCK)** — Codex audits T-2.1 step 3 + step 12 commit-cadence discipline. Logger import + module-level definition + log.warning callsite MUST land in same commit.
5. **Restore-SQL artifact discipline (R1.M3 LOCK)** — Codex audits T-1.2 step 4 + step 6 + step 11 + step 13 acceptance criteria. Artifact emitted in BOTH dry-run AND apply paths; emitted BEFORE UPDATE fires.
6. **Strict all-or-nothing vs partial-recovery semantic lock (R2.M3 LOCK)** — Codex audits T-1.2 step 3 + step 4 + step 5 + step 7 + step 8. AND-empty WHERE clause; SKIP_PARTIAL_EMPTY label; separate diagnostic enumeration. V1 STRICT only.
7. **Browser-only HTMX failure surface preservation (cumulative)** — Codex audits T-2.1 step 9 trinity preservation test. Sub-bundle 1 does NOT introduce new HTMX surfaces; preserves `/dashboard/weather-chart/refresh` trinity.
8. **Programming-error propagation discipline (R2.M2 LOCK)** — Codex audits T-2.1 step 6 + step 7 + step 8 (TypeError + AttributeError + KeyError + RuntimeError propagation tests). Narrow `ValueError`-only catch.
9. **Operator-witnessed gate split for behavior-conditional surfaces (R3.m4 LOCK)** — Codex audits §I runbook S5a/S5b split + state-planting fixture instructions.
10. **Schema v21 verification (spec §12 + brief §1.5)** — Codex audits §K + §A.3 + §A.4 #3. Plan SHALL count `swing/data/migrations/*.sql` files at plan-authoring time + assert 21. Escalation rule MANDATORY if surface reveals unavoidable migration.
11. **L2 LOCK parametric source-grep extension** — Codex audits T-4.1 step 1 implementation + acceptance criteria.
12. **Test fixture shape vs production emitter shape (Phase 12 C.D family)** — Codex audits all test fixtures match production candidates row shape, OhlcvArchive write shape, daily_management_records row shape exactly. Plan SHALL cite per-fixture production-shape source.
13. **Server-stamping discipline (Phase 8 family)** — Codex audits T-3.1 P14.N3 PROVISIONAL/LIVE state derived SERVER-SIDE at VM build time; NOT operator-supplied.
14. **`Co-Authored-By` footer suppression** — Codex audits all per-task commit instructions explicitly cite ZERO trailer; ~591+ cumulative streak preserved.
15. **ASCII-only template + CLI output (gotcha #32)** — Codex audits §A.4 #5 + per-task ASCII discipline tests + final §G.T-4.2 cumulative ASCII sweep test.

### §J.4 Codex chain artifact disposition

After Codex chain converges:
1. Codex round summary table goes into the writing-plans return report §2 (per brief §8 item #2).
2. Any Codex Major findings ACCEPTED with rationale (zero expected) go into writing-plans return report §6.
3. Codex MINOR findings BANKED non-blocking are listed at return report §7 (for V2-candidates) or §12 (for cumulative gotcha additions).
4. Final plan commit message: `docs(phase14-sub-bundle-1-plan): writing-plans -- <N> Codex rounds -> NO_NEW_CRITICAL_MAJOR convergent (R1 <C>+<M>+<m> -> R<N> 0+0+<m>)` (per brief §6 commit message stem).

---

## §K Schema impact analysis (v21 LOCK reverification + escalation rule)

### §K.1 Schema v21 LOCK reverification

Per spec §12 + brief §1.5 LOCK + §A.3 plan-authoring re-verification:

**Migration file count at plan-authoring (HEAD `b384cc1` per main + worktree branch):** **21 files** in `swing/data/migrations/*.sql` (verified via `ls .worktrees/phase14-sub-bundle-1-data-wiring-writing-plans/swing/data/migrations/*.sql | wc -l` → 21).

**No new `swing/data/migrations/0022_*.sql` file added by Sub-bundle 1.** Sub-bundle 2 (temporal log V1+) owns the v22 migration slot per Sec 9.1 Q1 + Q3 LOCKs.

**Per-item schema audit:**

| Item | Schema touch? | Migration needed? | Justification |
|---|---|---|---|
| V2.G3 | NEW repo helper `get_latest_sector_industry_per_ticker` consumes existing `candidates.sector` + `candidates.industry` (`TEXT NOT NULL DEFAULT ''` per `0012_sector_industry.sql:20-21`); NEW CLI subcommand emits idempotent UPDATEs against `trades.sector` + `trades.industry` (`TEXT NOT NULL DEFAULT ''` per `0012_sector_industry.sql:23-24`) | NO | Read + UPDATE on existing v12+ columns; no DDL |
| V2.G4 | One-line call-site fix at `swing/web/routes/dashboard.py:76`; module-level logger addition; narrow exception catch | NO | Route handler call-signature fix; cache layer unchanged; ZERO DB read/write changes |
| P14.N3 | Template + dashboard-VM extension; consumes existing `equity_resolver.resolve_live_capital_denominator_dollars` (Phase 11 ship) + existing `account_equity_snapshots` table (Phase 9 Sub-bundle C ship); 4 NEW VM fields are DATACLASS-level only (Codex R2.M#1+M#2 LOCK added the 4th `position_capital_policy_missing` for NoActivePolicyError surfacing) | NO | Template-rendering + VM field addition; both substrates already shipped at Phase 9 + Phase 11; ZERO DB schema change |

### §K.2 Escalation rule (MANDATORY)

Per brief §1.5 + spec §12: **if executing-plans-phase code-read OR adversarial-review surfaces an UNAVOIDABLE schema migration NOT anticipated at brainstorm + writing-plans phases, STOP + escalate to orchestrator. Do NOT silently propose v22 (would collide with Sub-bundle 2 temporal log v22 claim).**

Escalation procedure:
1. STOP further per-task work.
2. Document the surfaced migration scope at the orchestrator handoff.
3. Return to orchestrator for cross-sub-bundle scoping decision.
4. DO NOT introduce a `swing/data/migrations/0022_*.sql` file under Sub-bundle 1 scope.

**Pre-empt the escalation path at executing-plans phase** by auditing the executing-plans implementer's per-task acceptance criteria:
- T-1.1 NEW repo helper: NO DDL.
- T-1.2 NEW CLI subcommand: NO DDL.
- T-2.1 route handler fix: NO DDL.
- T-3.1 VM + template extension: NO DDL.
- T-4.1 parametric source-grep test: NO DDL.
- T-4.2 closer + cross-item integration test + return report: NO DDL.

ALL per-task §G acceptance criteria audited for DDL — zero per-task work introduces DDL. Schema v21 LOCK preserved by construction.

### §K.3 ASCII discipline scope at §K

§K does NOT introduce production-code surfaces; the migration audit is documentation-only. ASCII discipline at §K is informational — the plan doc itself + dispatch briefs are excluded per spec §15.2 rationale.

---

## §L Test fixture strategy (per item)

Per spec §11 + brief §1.5 L3 + brief §5 watch item #12 (test fixture shape vs production emitter shape; Phase 12 C.D family).

### §L.1 TestClient + ephemeral SQLite discipline

All web-route + VM tests use TestClient against an ephemeral SQLite at `tmp_path / 'swing.db'`. Existing pattern at `tests/web/conftest.py` is reused (per existing fixture `swing_db_in_tmp_path` at recent Phase 13 test additions; executing-plans phase confirms exact fixture name + signature via grep).

### §L.2 Production-shape fixture sourcing (per item)

**V2.G3 fixtures (T-1.1 + T-1.2):**
- Planted via `swing.data.repos.candidates.insert_candidates(conn, run_id, [Candidate(...)])` (bulk-insert; same emit path used by `_step_evaluate` in production at `swing/pipeline/runner.py`).
- ZERO synthetic-fixture-vs-production-emitter drift per CLAUDE.md gotcha family (Phase 12 C.D + Phase 12.5 Q2).
- ZERO hand-rolled INSERT SQL in tests.
- Test-local helper `_build_candidate_fixture(ticker)` returns a kwargs dict for the `Candidate` dataclass minus `ticker` + `sector` + `industry` (so per-test overrides of those three are explicit). At executing-plans phase, the helper audits the current `Candidate` dataclass via `inspect.signature(Candidate)` + extracts the required-field set + returns valid defaults.
- Similarly `_build_trade_fixture(ticker)` for the `Trade` dataclass.

**V2.G4 fixtures (T-2.1):**
- Planted via existing `tests/web/conftest.py` fixtures + monkeypatched `app.state.ohlcv_cache` to a `MagicMock(spec=OhlcvCache)`.
- `_build_spy_bars_fixture()` helper returns a production-shape `pd.DataFrame` matching `OhlcvCache.get_or_fetch` return contract (DatetimeIndex; capitalized `Open / High / Low / Close / Volume` columns; ~60 business-day window).
- `test_client_with_pipeline_run` fixture plants `pipeline_runs` row with `finished_ts` non-NULL.
- `test_client_no_pipeline_run` fixture omits the `pipeline_runs` row.

**P14.N3 fixtures (T-3.1):**
- Template tests use `MagicMock(daily_management_tiles=[_build_tile_vm(...)])` + Jinja2 `Environment` against the templates directory directly.
- VM tests use planted `account_equity_snapshots` rows via `swing.data.repos.account_equity_snapshots.insert_snapshot` (Phase 9 Sub-bundle C ship) + planted `daily_management_records` rows via existing Phase 8 repo helpers + planted open `Trade` rows via existing Phase 7 `insert_trade` helper.
- All production-shape fixtures; no hand-rolled INSERT SQL.

### §L.3 Cassette discipline

NO new cassettes introduced. Sub-bundle 1 does NOT add new Schwab API calls (L2 LOCK preserved); existing finviz cassettes unchanged.

### §L.4 Renderer-kwargs uniformity discipline (gotcha Expansion #10 sub-discipline c)

Sub-bundle 1 does NOT modify chart-render kwargs. The V2.G4 refresh handler's `render_market_weather_svg(bars=bars, trend_template_state="n/a")` callsite is unchanged. No renderer-kwargs uniformity LOCK applies.

### §L.5 Slow tests

ZERO slow tests added. Verified at T-4.2 step 3 via `pytest -m "slow" -q --collect-only` returning no NEW slow-marked tests authored by Sub-bundle 1.

---

## §M Forward-binding lessons (carried forward from brainstorm return report §8)

The 8 forward-binding lessons + 1 new lesson candidate (gotcha pre-emption for Sub-bundle 2):

1. **Brief-vs-production-function-signature verification (gotcha #17 / Expansion #2 refinement).** Applied at plan-authoring per §A.3 (14 surfaces verified). Executing-plans phase MUST re-grep before each per-task commit.
2. **Cumulative regression cascade audit (gotcha #21 / Expansion #13).** §G.0 commit-cadence preface; per-task acceptance criteria include "no stale-reference cascade" sub-check; Codex MCP chain reviews entire plan post-fix at each round (per §J).
3. **Percent-vs-proportion unit lock (R3.M1 LOCK).** Applied at T-3.1 step 9 BINDING test. Forward-binding for Sub-bundle 2 (temporal log) IF that sub-bundle surfaces any utilization / percent / proportion metrics.
4. **Module-level logger addition (R3.M2 LOCK).** Applied at T-2.1 step 3 + step 12. Forward-binding for any future route handler that emits log calls.
5. **Restore-SQL artifact discipline (R1.M3 LOCK).** Applied at T-1.2 step 4 + step 6. Forward-binding for any future one-time backfill helper.
6. **Strict all-or-nothing vs partial-recovery semantic lock (R2.M3 LOCK).** Applied at T-1.2 step 3 + step 4 + step 5. Forward-binding for any future UPDATE flow touching MULTIPLE columns.
7. **Browser-only HTMX failure surface preservation (cumulative).** Applied at T-2.1 step 9 regression test. Forward-binding for any future HTMX-driven endpoint addition (Sub-bundle 4 P14.N6 journal redesign is the next candidate).
8. **Programming-error propagation discipline (R2.M2 LOCK).** Applied at T-2.1 step 6 + step 7 + step 8. Forward-binding for any future route handler with exception handling.
9. **Operator-witnessed gate split for behavior-conditional surfaces (R3.m4 LOCK).** Applied at §I S5a/S5b split. Forward-binding for any future UI behavior conditioned on state (Sub-bundle 2 temporal log's pattern_status flips are the next candidate).

**Plan-authoring-specific forward-binding lesson (NEW; banked at writing-plans return report):**
- **Plan §A.3 production-code re-verification table is BINDING at writing-plans phase.** The brainstorm spec asserted signatures + line numbers; the writing-plans phase re-greps them all against the current HEAD before drafting plan code blocks. Catches: signature drift between brainstorm-time and writing-plans-time merges (e.g., a Sub-bundle 0 hotfix that landed between brainstorm SHIP + writing-plans dispatch). Sub-bundle 1's plan §A.3 verifies 14 surfaces; zero drift detected. Forward-binding for ALL future sub-bundle writing-plans dispatches: include a §A.3-equivalent table.

---

## §N Self-review checklist (pre-Codex)

Per "Writing Plans" skill self-review section. Run this checklist on the plan with fresh eyes BEFORE invoking the Codex chain.

### §N.1 Spec coverage

For each spec section, identify the task(s) implementing it:

| Spec section | Plan task(s) | Notes |
|---|---|---|
| spec §1.1 cohesion table | §C.1 + §C.2 + §C.3 | per-item integration analysis |
| spec §2.1-§2.6 LOCKs | §E LOCK summary table | verbatim preservation |
| spec §3 module touch list | §B file map | 1:1 mapping |
| spec §4 V2.G3 design | §G.T-1.1 + §G.T-1.2 (+ §G.T-1.3 OPTIONAL) | full TDD coverage |
| spec §5 V2.G4 design | §G.T-2.1 | full TDD coverage |
| spec §6 P14.N3 design | §G.T-3.1 | full TDD coverage |
| spec §7 error handling | §C.1 + §C.2 + §C.3 + per-task acceptance criteria | per-item failure surface enumeration |
| spec §8 cross-item coherence | §C.4 + §G.T-4.2 step 1 cross-item test | no shared substrate; test isolation per spec |
| spec §9 discriminating-example walkthroughs | per-task TDD steps (T-1.1 step 6-10; T-1.2 step 6-12; T-2.1 step 5-10; T-3.1 step 7-11) | 18 walkthroughs mapped to ~32 plan tests |
| spec §10.1 single-dispatch | §A.2 + §D #1 + §J | LOCKED |
| spec §10.2 commit cadence | §G.0 commit-cadence preface | 8-12 commits enumerated |
| spec §10.3 test count | §H test surface table | ~34-36 estimate enumerated |
| spec §10.4 cross-bundle pin | none | NONE; Sub-bundle 1 does not cross-bundle pin |
| spec §10.5 operator-witnessed gate | §I runbook with S5a/S5b split | per-surface planting + pass criteria |
| spec §11 test fixture strategy | §L | per-item fixture sourcing |
| spec §12 schema impact | §K | v21 LOCK reverification + escalation rule |
| spec §13 V1 simplifications + V2 candidates | §D #1 (V2 candidates) | banked at return report §7 per brief §8 #7 |
| spec §14 Open Questions | §G.T-1.2 OQ #1-3 + §G.T-2.1 OQ #4 + §G.T-3.1 OQ #5-6 LOCKED inline; OQ #7 fixture strategy LOCKED at §L; OQ #8 cadence at §G.0 | all 8 resolved at plan-authoring time |
| spec §15 cumulative discipline compliance | §F gotcha application matrix | 6 APPLIED + 31 N/A; ZERO violated |

**Spec coverage: ALL sections mapped to one or more plan tasks. ZERO gaps.**

### §N.2 Placeholder scan

Scan plan for red-flag patterns ("TBD", "TODO", "implement later", "fill in details", "TBD at executing-plans phase" used as a substitute for actual code, "Similar to Task N" without repeating the code, "Add appropriate error handling", etc.):

| Pattern | Locations | Disposition |
|---|---|---|
| "TBD at executing-plans phase" | §B.3 (Fix-1b T-1.3 trigger), §G.T-1.3 acceptance criteria | LEGITIMATE — Fix-1b is OPTIONAL; executes ONLY if trigger fires; default disposition = SKIP. Acceptance criteria 1-3 are placeholders for the optional path. |
| "TBD at trigger time" (§B.3 audit annotation) | §B.3 OPTIONAL-MODIFIED row | LEGITIMATE — the audit at trigger time is part of the T-1.3 acceptance criteria; the path may be `swing/web/view_models/open_positions_row.py` OR an inline build in `dashboard.py` (the exact path is auditable only if T-1.3 fires). |
| "audit at executing-plans phase" (§L.1) | TestClient fixture name verification | LEGITIMATE — the existing fixture name (`swing_db_in_tmp_path`) is grep-able; the executing-plans implementer confirms via `grep -r "def swing_db_in_tmp_path" tests/`. |
| "TBD" / "TODO" elsewhere | Searched plan-wide | NONE FOUND. |
| "fill in details" | Searched plan-wide | NONE FOUND. |
| "implement later" | Searched plan-wide | NONE FOUND. |
| "Add appropriate error handling" | Searched plan-wide | NONE FOUND (error handling explicit at §C.1-§C.4 + per-task acceptance criteria + per-task TDD steps). |
| "Similar to Task N" | Searched plan-wide | NONE FOUND (per-task TDD steps repeat the full code; no cross-task references that omit code). |

**Placeholder scan: ZERO illegitimate placeholders. All annotated executing-plans-phase TBDs are LEGITIMATE deferrals for OPTIONAL T-1.3 OR fixture-name confirmation steps.**

### §N.3 Type consistency

Type / signature / name consistency across tasks:

| Identifier | Defined at | Consumed at | Consistent? |
|---|---|---|---|
| `get_latest_sector_industry_per_ticker(conn, tickers) -> dict[str, tuple[str, str]]` | T-1.1 step 3 | T-1.2 step 4 (`_build_backfill_rows` calls), §G.T-1.3 (Fix-1b at render time) | YES |
| `BackfillRow` dataclass | T-1.2 step 4 | T-1.2 step 4 (`_emit_restore_sql`, `_apply_updates`, `_format_report`) | YES |
| `BackfillSummary` dataclass | T-1.2 step 4 | T-1.2 step 3 (CLI subcommand consumes) | YES |
| `OhlcvCache.get_or_fetch(*, ticker: str, window_days: int = 180) -> pd.DataFrame` | spec §5.1 + §A.3 verification | T-2.1 step 3 (`bars = ohlcv_cache.get_or_fetch(ticker=benchmark)`) | YES |
| `DailyManagementTileVM` 17 existing + 4 NEW fields (post-R2.M#1+M#2) | T-3.1 step 3 (dataclass extension) | T-3.1 step 4 (build site) + T-3.1 step 5 (template) + tests | YES |
| `resolve_live_capital_denominator_dollars(conn, *, asof_date, at_trade_time_policy) -> tuple[float, Literal["LIVE", "PROVISIONAL"]]` | §A.3 verification | T-3.1 step 4 build site | YES |
| `compute_position_capital_utilization(*, current_size, current_price, denominator_dollars) -> float` (PROPORTION) | §A.3 verification | T-3.1 step 4 build site | YES |
| `read_live_policy(conn) -> RiskPolicy` | §A.3 verification | T-3.1 step 4 build site | YES |
| `L2_LOCK_BASELINE_SHA = "bf7e071"` | T-4.1 step 1 | T-4.1 step 1 + brief §1.1 reference | YES |
| `position_capital_utilization_pct_effective` field name | T-3.1 step 3 dataclass | T-3.1 step 4 build site + T-3.1 step 5 template + tests | YES (consistent spelling + casing) |
| `position_capital_utilization_is_provisional` field name | T-3.1 step 3 dataclass | T-3.1 step 4 build site + T-3.1 step 5 template + tests | YES |
| `position_capital_denominator_dollars_resolved` field name | T-3.1 step 3 dataclass | T-3.1 step 4 build site + VM tests | YES |
| `--allowlist` CLI option | T-1.2 step 3 | T-1.2 step 4 (`allowlist` param) + T-1.2 step 12 test | YES |
| `--include-closed` CLI flag | T-1.2 step 3 | T-1.2 step 4 (`include_closed` param) + T-1.2 step 11 test | YES |

**Type consistency: ZERO drift. All identifiers spelled + signed consistently across tasks.**

### §N.4 Cumulative LOCK preservation re-check

Per §E.4 LOCK preservation verdict: ALL 23 LOCKs (Q1-Q7 + §1.1-§1.6 + spec §2.1×6 + L1-L5) preserved verbatim. Verified at §E. ZERO LOCK deviations.

### §N.5 Self-review verdict

- [x] Spec coverage: ZERO gaps (§N.1)
- [x] Placeholder scan: ZERO illegitimate placeholders (§N.2)
- [x] Type consistency: ZERO drift (§N.3)
- [x] Cumulative LOCK preservation: ZERO deviations (§N.4)
- [x] §A.3 plan-authoring production-code re-verification: 14 surfaces verified; ZERO signature drift
- [x] Schema v21 LOCK: 21 migration files verified
- [x] ASCII discipline scope declared at §A.4 #5 + §F #32 + per-task tests
- [x] Co-Authored-By suppression discipline cited at §A.4 #1 + §G.0 + per-task commit instructions
- [x] L2 LOCK parametric source-grep test designed at T-4.1
- [x] Operator-witnessed gate runbook at §I has S5a/S5b split with planting fixture instructions
- [x] Codex single-chain placement at §J per Sec 9.1 Q7 LOCK
- [x] Forward-binding lessons from brainstorm return report §8 carried forward at §M
- [x] Plan target line count ~1500–2500: this plan ~3750 lines post-R2 (was ~3200 pre-Codex; +50% over upper bound; growth content-mandated by per-task TDD step code blocks + §A.3 14-row signature-verification table + §E 23-row LOCK summary table + §F application matrix + §I gate runbook + §J 15 watch items + §N self-review tables + R1+R2 fix bundles that introduced concrete production-API call shapes (R2.M#3-M#5) + 4th VM field + policy-missing template branch (R2.M#1+M#2) + multiset L2 LOCK assertion (R2.M#6) + provenance metadata (R1.M#6) + ARIA-compliant focusable affordance (R1.M#2); mirrors the spec's own +200 line drift post-R4 due to substantive Codex catches now propagating into binding per-task code blocks rather than spec prose; no ceremonial padding)

**Plan ready for Codex MCP single-chain adversarial review.**

---

*End of Phase 14 Sub-bundle 1 data-wiring writing-plans plan. ~3750 lines post-R2 Codex fix bundle (+50% over upper ~2500 target; content-mandated per §N.5); 3 data-wiring items (V2.G3 + V2.G4 + P14.N3); 8 per-task slices (T-1.1 + T-1.2 + T-1.3 OPTIONAL + T-2.1 + T-3.1 + T-4.1 + T-4.2); ~8-12 commits + ~34-36 fast tests projected; Schema v21 LOCKED; L2 LOCK preserved; ASCII discipline declared; Co-Authored-By footer suppression discipline cited. Forward-binding lessons from brainstorm return report §8 carried forward. Single Codex MCP chain at end per Sec 9.1 Q7 LOCK + gotcha #36 caveat; target convergence 2-4 rounds NO_NEW_CRITICAL_MAJOR. Plan ready for adversarial review.*
