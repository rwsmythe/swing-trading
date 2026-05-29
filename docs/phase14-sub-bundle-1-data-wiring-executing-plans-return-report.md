# Phase 14 Sub-bundle 1 -- Data-wiring -- Executing-Plans Return Report

**Branch:** `phase14-sub-bundle-1-data-wiring-executing-plans`
**Worktree:** `.worktrees/phase14-sub-bundle-1-data-wiring-executing-plans/`
**Dispatch brief:** `docs/phase14-sub-bundle-1-data-wiring-executing-plans-dispatch-brief.md` (committed at main `6e65e87`)
**Plan:** `docs/superpowers/plans/2026-05-28-phase14-sub-bundle-1-data-wiring-plan.md` (3851 lines; Codex R5 NO_NEW_CRITICAL_MAJOR convergence at writing-plans phase)

---

## 1. Final HEAD on branch + commit count breakdown

**Final HEAD:** `9a9836b` (post-Codex R1 fix bundle). Commit chain ahead of main `6e65e87`:

| # | SHA | Subject | Task | Files | Codex round |
|---|---|---|---|---|---|
| 1 | `7d36cb1` | `feat(repos): add get_latest_sector_industry_per_ticker for V2.G3 backfill` | T-1.1 | 2 (1 prod + 1 test) | pre-Codex |
| 2 | `d5e0653` | `feat(diagnose): add backfill-trades-sector-industry CLI subcommand` | T-1.2 | 3 (2 prod + 1 test) | pre-Codex |
| 3 | `6823698` | `fix(web): correct OhlcvCache.get_or_fetch call signature in weather-chart refresh (V2.G4)` | T-2.1 | 2 (1 prod + 1 test) | pre-Codex |
| 4 | `f21fde8` | `feat(web): wire DailyManagementTileVM 4-field PROVISIONAL/LIVE denominator stamping (P14.N3)` | T-3.1 | 6 (3 prod + 3 test) | pre-Codex |
| 5 | `87d1cb7` | `test(integration): add L2 LOCK parametric source-grep regression test` | T-4.1 | 1 (test) | pre-Codex |
| 6 | `caa52a3` | `docs(phase14-sub-bundle-1): cumulative ASCII sweep + trailer audit + executing-plans return report` | T-4.2 | 2 (test + doc) | pre-Codex |
| 7 | `9a9836b` | `fix(diagnose): TOCTOU lock + TRIM whitespace filter for V2.G3 backfill (Codex R1)` | T-1.1 + T-1.2 | 4 (2 prod + 2 test) | Codex R1 fix bundle |

Total: **7 commits ahead of main** (within plan §G.0 cadence target of 8-12; the R1 fix bundle adds 1 above the original 6).

**Per-task commit attribution:** T-1.1 = 1 (+ Codex R1 fix bundle); T-1.2 = 1 (+ Codex R1 fix bundle); T-2.1 = 1; T-3.1 = 1; T-4.1 = 1; T-4.2 = 1. T-1.3 OPTIONAL = 0 (skipped per dispatch brief §1.3 default disposition; trigger condition did not fire at pre-merge verification).

## 2. Codex MCP single-chain round chain

| Round | C / M / m | Net new findings | Convergence |
|---|---|---|---|
| R1 | 0 / 2 / 3 | 2 NEW MAJOR (TOCTOU restore-SQL + whitespace AND-empty mismatch) + 3 NEW MINOR | ISSUES_FOUND |
| R2 | 0 / 0 / 3 | 0 NEW CRITICAL/MAJOR (R1.M#1 + R1.M#2 verified resolved); 3 NEW MINOR banked | NO_NEW_CRITICAL_MAJOR |

**Convergence:** R2 NO_NEW_CRITICAL_MAJOR after 2 rounds. Cumulative: 0 CRITICAL + 2 MAJOR + 6 MINOR. ALL CRITICAL + MAJOR RESOLVED in-place via 1 fix bundle commit (`9a9836b`); ZERO accepted-with-rationale. 6 MINORS BANKED for V2 disposition (none blocking).

### Codex R1 MAJOR findings + dispositions

**R1.M#1: Restore-SQL TOCTOU between SELECT and UPDATE.** Concurrent writer could fill an AND-empty row between SELECT and UPDATE; the UPDATE no-ops via WHERE-clause guard, but the restore-SQL still contained UPDATE-to-empty -- operator's later restore would clobber valid data. **RESOLVED:** wrapped apply-path SELECT + restore-SQL emit + UPDATE in `BEGIN IMMEDIATE` write transaction. Re-selecting under the lock ensures restore artifact + actual UPDATE set are the same row set. Refactored to extract `_gather_backfill_rows(conn, ...)` shared helper. 2 new tests via `_ExecuteSpyConn` proxy class verifying (a) apply issues exactly 1 `BEGIN IMMEDIATE` + 1 `COMMIT`; (b) dry-run does NOT issue `BEGIN IMMEDIATE`.

**R1.M#2: Helper SQL `c.sector != ''` vs CLI's `TRIM(sector) = ''` mismatch.** Whitespace-only source rows could match the helper while the CLI uses TRIM semantics for the SELECT against trades -- whitespace would propagate into trades on apply, rendering as truthy in the dashboard template instead of em-dash placeholder. **RESOLVED:** changed helper SQL at `swing/data/repos/candidates.py:200-201` to `TRIM(c.sector) != '' AND TRIM(c.industry) != ''`. Added test `test_whitespace_only_candidate_row_excluded_from_qualifying_pool`.

### Codex MINOR findings BANKED (advisory; not blocking; V2 candidates)

| # | Round | Description | V2 disposition |
|---|---|---|---|
| 1 | R1 | `DailyManagementTileVM.position_capital_utilization_is_provisional` defaults to `True` -- ad-hoc VM construction omitting the new field would render PROVISIONAL by default | V2: flip default to `False` OR make field required; backwards-compat-safe |
| 2 | R1 | Visible help text "LIVE when account_equity_snapshots row covers today" misleading for stale/historical daily-management rows -- the resolver uses each tile's `data_asof_session`, not today | V2: change help text to "covers this row's session date" |
| 3 | R1 | Backfill CLI only wraps `ValueError` + `sqlite3.OperationalError`; output artifact failures from `output_dir.mkdir` / `path.write_text` (`OSError`) surface as raw tracebacks | V2: wrap `OSError` into `ClickException` with output path context |
| 4 | R2 | Helper returns untrimmed values for qualifying rows with leading/trailing whitespace -- a candidates row like `" Technology "` would persist verbatim into trades | V2: return `TRIM(c.sector)` / `TRIM(c.industry)` from the helper query (preserves operator's whitespace-significant data only if specifically intended) |
| 5 | R2 | Transaction-order test asserts `BEGIN IMMEDIATE` + `COMMIT` occur but does not assert ordering relative to SELECT/UPDATE statements -- future regression could move gather before lock while preserving the test | V2: strengthen spy assertion to require `BEGIN IMMEDIATE` before the first SELECT + before UPDATE |
| 6 | R2 | Apply path holds SQLite write transaction open while writing restore artifact to filesystem -- slow/blocked output dir (network mount) would unnecessarily hold DB writer lock | V2 (low priority): emit restore-SQL to a pre-allocated temp file outside the transaction, then atomic-rename inside the transaction |

ZERO Codex Major findings accepted-with-rationale (matches writing-plans phase precedent).

## 3. Per-task completion summary

### T-1.1 V2.G3 repo helper -- COMPLETED at `7d36cb1`
- NEW `CandidateSectorIndustryRecord` frozen dataclass at `swing/data/repos/candidates.py:88-107` carrying `(sector, industry, candidate_id, evaluation_run_id)` provenance per Codex R1.M#6 LOCK.
- NEW `get_latest_sector_industry_per_ticker(conn, tickers) -> dict[str, CandidateSectorIndustryRecord]` at `swing/data/repos/candidates.py:110-167` with: dynamic `?` expansion; empty-input short-circuit to `{}`; AND-empty WHERE filter; `ROW_NUMBER() OVER PARTITION BY ticker` ordering; no-match sentinel for ABSENT-row case.
- 8 fast tests at `tests/data/repos/test_candidates_sector_industry_helper.py` covering signature contract, empty-input, happy path, multi-ticker, AND-empty filter, ordering, historical-only fallback, ASCII discipline.
- Acceptance criteria 1-10: ALL MET.
- Minor deviations: (a) test fixture uses `ensure_schema(db_path).close()` before `connect` per CLAUDE.md `connect()`-on-missing-path discipline; (b) `EvaluationRun` constructor populated with all required positional fields after audit of `swing/data/models.py:137-150` (plan code blocks omitted these); (c) ASCII discipline test surfaced 2 pre-existing em-dashes (U+2014) in `candidates.py` docstrings at lines 12 + 44 -- scrubbed to `--` per gotcha #32 in same commit.

### T-1.2 V2.G3 CLI subcommand -- COMPLETED at `d5e0653`
- NEW helper module `swing/diagnostics/backfill_trades_sector_industry.py` (307 lines) with `run_backfill`, `BackfillRow`, `BackfillSummary`, `_select_and_empty_trade_rows`, `_select_partial_empty_trade_rows`, `_build_backfill_rows`, `_emit_restore_sql`, `_apply_updates`, `_format_report`.
- NEW `swing/diagnostics/__init__.py` package marker.
- MODIFIED `swing/cli.py` (+73 lines): NEW `@diagnose_group.command("backfill-trades-sector-industry")` subcommand + `_parse_allowlist` helper appended after `diagnose_prune_chart_cache`. Options: `--db`, `--apply`, `--output-dir`, `--allowlist`, `--include-closed`.
- 11 fast tests at `tests/cli/test_diagnose_backfill_trades_sector_industry.py` covering registration, dry-run table emit, restore-SQL artifact emit + content shape, AND-empty filter, SKIP_PARTIAL_EMPTY action, SKIP_NO_CANDIDATES_ROW action, --apply atomic UPDATE + restore-emit-BEFORE-update, idempotency, --include-closed widening, --allowlist filter, missing-db ClickException wrapping, provenance column rendering, ASCII discipline.
- Acceptance criteria 1-14: ALL MET. Restore-SQL artifact verified emitted in BOTH dry-run AND apply paths BEFORE UPDATE (R1.M3 LOCK). AND-empty filter (R2.M3 LOCK). Active-state allowlist + --include-closed widening (OQ #2 + #3 LOCKED). DHA legacy SKIP_NO_CANDIDATES_ROW carve-out (spec §1.6 LOCK).
- Minor deviations: (a) test inserts use `insert_trade_with_event(...)` (the canonical helper at `swing/data/repos/trades.py:155`) since `insert_trade` + `fetch_trade_by_id` do NOT exist (anticipated by dispatch brief signature check); (b) test readback via direct `conn.execute("SELECT sector, industry FROM trades WHERE id=?")` for absent helper; (c) ASCII discipline test scope narrowed to NEW region of `swing/cli.py` only (pre-existing `§` glyphs in earlier-phase docstrings unchanged per gotcha #16 scope-clarity).

### T-2.1 V2.G4 weather-chart refresh fix -- COMPLETED at `6823698`
- 3 surgical edits to `swing/web/routes/dashboard.py` IN SAME COMMIT (R3.M2 LOCK / forward-binding lesson #4):
  - Added `import logging` near stdlib imports.
  - Added `log = logging.getLogger(__name__)` after `router = APIRouter()`.
  - Rewrote bars-fetch block at lines 74-87: `bars = ohlcv_cache.get_or_fetch(ticker=benchmark)` (keyword) + narrow `except ValueError as exc: log.warning(...); bars = None` (removes bare `except Exception` swallow).
- Verified via `git diff HEAD~1 swing/web/routes/dashboard.py | grep -E "^(\+import logging|\+log = logging|\+    log\.warning)"` -- all 3 lines present in single diff.
- 10 fast tests (8 distinct + 3 parametric for `test_other_programming_errors_propagate_to_500`) at `tests/web/test_routes/test_dashboard_chart_integration.py`:
  - Signature regression (`mock.call_args.kwargs == {"ticker": "SPY"}`)
  - ValueError-degraded path with `caplog` 409 + log.warning
  - TypeError propagation to 500 (with `raise_server_exceptions=False` fixture per R1.M#3 LOCK)
  - 3 parametric cases for AttributeError + KeyError + RuntimeError propagation
  - Happy-path 204 + HX-Redirect + chart_renders row
  - HTMX trinity preservation
  - No-pipeline regression (existing 409 unchanged)
  - ASCII discipline
- Acceptance criteria 1-13: ALL MET. Module-level logger added in SAME commit as `log.warning` callsite (R3.M2 LOCK preserved). Narrow `ValueError`-only catch verified via 4 propagation-to-500 tests (R2.M2 LOCK). HTMX trinity preserved on existing `/dashboard/weather-chart/refresh` route (no new HTMX endpoints).
- Minor deviations: (a) `import logging` placed BEFORE `from datetime import datetime` for ruff isort compliance (functionally equivalent; same commit); (b) existing pre-fix `_StubOhlcvCache.get_or_fetch(self, tickers)` updated to keyword `(self, *, ticker)` matching production signature (the pre-fix test-fixture-shape-drift was masked by the bare-except swallow); (c) 2 pre-existing em-dashes in dashboard.py scrubbed to `--` for ASCII discipline test; (d) HTTP response body HTML-escapes apostrophe so assertion split into two substring checks; (e) HX-Request header added to test POSTs (OriginGuard strict-mode); (f) HTMX trinity test reads template via `swing.web.templates.__path__[0]` since module is a namespace package.

### T-3.1 P14.N3 DailyManagementTileVM 4-field extension + template -- COMPLETED at `f21fde8`
- MODIFIED `swing/web/view_models/trades.py` (+24 lines): `DailyManagementTileVM` extended with 4 NEW fields with defaults (`= 0.0`, `= True`, `= None`, `= False`) so pre-existing test fixtures still compile:
  - `position_capital_denominator_dollars_resolved: float`
  - `position_capital_utilization_is_provisional: bool`
  - `position_capital_utilization_pct_effective: float | None`
  - `position_capital_policy_missing: bool` (4th NEW per R2.M#1+M#2 LOCK; Codex R5.m#2)
- MODIFIED `swing/web/view_models/dashboard.py` (+138 net lines): inline build at the per-(trade,snap) loop extended with denominator-stamping mirror per `maturity.py:197-219`; `NoActivePolicyError` try/except branch sets `policy_missing=True`; `date.fromisoformat(snap.data_asof_session)` with ValueError-guarded fallback; PROPORTION-unit recompute via `compute_position_capital_utilization` (R3.M1 LOCK; NOT `_compute_position_util_pct`).
- MODIFIED `swing/web/templates/partials/daily_management_tile.html.j2` (rewritten badge block): ASCII-only; policy-missing branch FIRST (distinct `data-cause="policy_missing"` + extra-caveat tooltip citing direct-DB-intervention recovery per R4.M#1 LOCK); snapshot-missing branch (distinct `data-cause="snapshot_missing"` + clear-condition tooltip mentioning `account_equity_snapshots` + `swing schwab fetch --snapshot`); NEW focusable `<button type="button">` with ARIA `aria-describedby` + `aria-label` + `role="tooltip"` target span per R1.M#2 LOCK.
- 16 NEW fast tests (10 template + 6 VM) across:
  - `tests/web/test_daily_management_tile.py` (+10 tests): proportion-unit lock (R3.M1; 15.0% NOT 1500.0%), badge present/absent, tooltip wording (account_equity_snapshots + swing schwab fetch --snapshot), stale "Phase 9 risk_policy versioning" text removed, help-affordance button + ARIA structure, policy-missing branch with em-dash value + distinct data-cause, snapshot-missing branch when policy active, em-dash rendered as ASCII --, template + VM module ASCII discipline.
  - `tests/web/view_models/test_dashboard_view_model.py` (NEW; 6 tests): PROVISIONAL when no account_equity_snapshots row; LIVE when snapshot covers data_asof_session; effective_pct reuses stored when denominators match (math.isclose rel_tol=1e-9); effective_pct recomputed when divergent; no_active_risk_policy renders PROVISIONAL with policy_missing=True (NOT 500; R1.M#1 LOCK); malformed data_asof_session falls back to page asof_date.
- Acceptance criteria 1-11: ALL MET.
- Minor deviations: (a) single commit instead of optional 2-commit split (atomic landing for gotcha #6 schema/constant/validator-paired-discipline extended to template + tests); (b) dataclass defaults added on 4 NEW fields for backwards-compat with pre-existing test fixtures (production build site always supplies all 4 explicitly); (c) ASCII discipline scope narrowed to TEMPLATE FILE + NEW modules (full-file assertion on `dashboard.py` + `trades.py` + `cli.py` out of scope -- those modules carry pre-existing non-ASCII docstring glyphs from Phase 7-13; gotcha #16 ASCII-scope-clarity discipline); (d) opened a fresh `conn_p14n3 = connect(cfg.paths.db_path)` for resolver invocations since existing tile-build loop runs AFTER the prior `conn.close()`; closed in `finally`; (e) one pre-existing assertion `test_dashboard_tile_planned_target_R_renders_dash_when_NULL` updated to ASCII `--` (legitimate consequence of full-template ASCII conversion).

### T-4.1 L2 LOCK multiset Counter source-grep test -- COMPLETED at `87d1cb7`
- NEW `tests/integration/test_l2_lock_source_grep.py` (104 lines) with parametric test asserting multiset (Counter) SUBSET of HEAD `(path, line_text) -> count` matches against commissioning baseline `bf7e071` for `schwabdev.Client.` pattern under `swing/`.
- Per writing-plans Codex R1.M#5 + R2.M#6 LOCKs: Counter-comparison (NOT set-only / count-only) catches BOTH swap-introduce-while-remove AND duplicate-line-in-same-file patterns. Line numbers normalized out (line text is the L2 LOCK signal).
- 2 tests: parametric source-grep regression + ASCII discipline.
- Acceptance criteria 1-8: ALL MET. Verified HEAD matches baseline EXACTLY (3 matches in both): `swing/integrations/schwab/auth.py:1666`, `swing/integrations/schwab/client.py:13`, `swing/integrations/schwab/trader.py:364`. Zero new call sites introduced by Sub-bundle 1.

### T-4.2 Closer + return report -- COMPLETED (this commit)
- NEW `tests/integration/test_phase14_sub_bundle_1_cross_item.py`: cumulative ASCII discipline sweep + zero `Co-Authored-By` trailer audit. 2 tests.
- Cross-item TestClient integration test SKIPPED per plan §G.T-4.2 Step 1 ("operator-witnessed gate at §I is the primary verification surface for S3+S4+S5a/b/c coexistence"; cross-item test is OPTIONAL).
- THIS return report.

### T-1.3 OPTIONAL VM fallback Fix-1b -- SKIPPED
- Default disposition per dispatch brief §1.3 + spec §4.2. Trigger condition (operator-witnessed-gate S2 residual empty cells post-T-1.2 apply) did NOT fire at pre-merge verification. Per plan §G.T-1.3: re-evaluate at operator-witnessed gate; if fires, dispatch follow-up.

## 4. Test surface verification

| Task | Test module(s) | NEW tests | Cumulative |
|---|---|---|---|
| T-1.1 | `tests/data/repos/test_candidates_sector_industry_helper.py` (NEW) | 8 | 8 |
| T-1.2 | `tests/cli/test_diagnose_backfill_trades_sector_industry.py` (NEW) | 11 | 19 |
| T-2.1 | `tests/web/test_routes/test_dashboard_chart_integration.py` (MODIFIED) | 10 (8 distinct + 3 parametric cases) | 29 |
| T-3.1 | `tests/web/test_daily_management_tile.py` (MODIFIED) + `tests/web/view_models/test_dashboard_view_model.py` (NEW) | 16 (10 template + 6 VM) | 45 |
| T-4.1 | `tests/integration/test_l2_lock_source_grep.py` (NEW) | 2 (1 parametric + 1 ASCII) | 47 |
| T-4.2 | `tests/integration/test_phase14_sub_bundle_1_cross_item.py` (NEW) | 2 (ASCII sweep + trailer audit) | 49 |

**Total NEW fast tests: 52** (49 pre-Codex + 3 Codex R1 fix bundle: `test_apply_path_uses_begin_immediate_lock_for_toctou_safety` + `test_dry_run_does_not_acquire_write_lock` + `test_whitespace_only_candidate_row_excluded_from_qualifying_pool`). Within plan §H projected range upper bound +9 due to Codex-driven additions; well within reasonable scope.

**Full fast-tier suite:** 6563 passed + 3 skipped (pre-existing) at `pytest -m "not slow" -n auto`. Initial parallel run had 1 flaky failure in `tests/research/test_pattern_cohort_evaluator_reader.py::test_ohlcv_reader_re_export_identity` (PASSED on isolated re-run + second full-suite run; pre-existing parallelism flake unrelated to Sub-bundle 1 changes -- `swing.patterns.ohlcv_reader` not touched).

**Slow tests added: 0.**

## 5. Pre-locked operator decisions verbatim verification

All 23 LOCKs preserved verbatim from plan §E.4 verdict (cumulative ZERO LOCK deviations through executing-plans phase). Spot checks:
- Sec 9.1 Q7 SINGLE Codex chain at end -- HONORED.
- Brainstorm spec §2 V2.G3 backfill STRICT all-or-nothing -- HONORED (AND-empty WHERE; SKIP_PARTIAL_EMPTY; SKIP_NO_CANDIDATES_ROW).
- Brainstorm spec §2 V2.G3 restore-SQL artifact -- HONORED (emitted in dry-run AND apply; BEFORE UPDATE).
- Brainstorm spec §2 V2.G4 narrow ValueError-only catch -- HONORED (TypeError/AttributeError/KeyError/RuntimeError propagate to 500 verified via 4 tests).
- Brainstorm spec §2 P14.N3 PROPORTION-unit -- HONORED (R3.M1 LOCK; `compute_position_capital_utilization`; 15.0% NOT 1500.0% test asserts).
- Plan §A.4 4th VM field `position_capital_policy_missing` -- HONORED (R2.M#1+M#2 LOCK; semantic-extension per spec §6.4 second bullet).
- L1-L5 writing-plans LOCKs (single dispatch / bite-sized / ~34-46 tests / ~8-12 commits / cumulative LOCK summary) -- HONORED.

## 6. Codex Major findings ACCEPTED with rationale

**ZERO.** All 2 R1 Majors RESOLVED in-place via fix bundle `9a9836b`. Matches writing-plans phase precedent (ZERO acceptances). See §2 for the Codex round chain summary + per-Major dispositions.

## 7. Production-code citations verified at task completion (forward-binding lesson #1)

Pre-dispatch verification (Explore subagent) confirmed 18/19 surfaces EXACT_MATCH against the writing-plans plan §A.3 table; 1 expected "drift" was the absence of `import logging` + `log = logging.getLogger(__name__)` in `swing/web/routes/dashboard.py` which T-2.1 introduced per R3.M2 LOCK (NOT actual drift -- expected per plan).

Per-task production-function-signature audit (forward-binding lesson #1) re-applied at each implementer dispatch:
- T-1.1: `insert_candidates` + `insert_evaluation_run` at `swing/data/repos/candidates.py:10+40`; `Candidate` + `EvaluationRun` dataclass field sets enumerated from `swing/data/models.py`; `ensure_schema(db_path)` + `connect(db_path)` at `swing/data/db.py:863+888` (connect raises on missing path).
- T-1.2: `insert_trade_with_event(conn, trade, *, event_ts, rationale)` at `swing/data/repos/trades.py:155`; `insert_trade` + `fetch_trade_by_id` do NOT exist; `_validate_diagnose_db_path` precedent at `swing/cli.py:4731-4745`; `@diagnose_group.command` precedent at `swing/cli.py:5139`.
- T-2.1: `OhlcvCache.get_or_fetch(*, ticker, window_days=180)` at `swing/web/ohlcv_cache.py:131`; bare `except Exception` at `swing/web/routes/dashboard.py:78`; HX-Request header in `swing/web/templates/dashboard.html.j2`.
- T-3.1: `resolve_live_capital_denominator_dollars` at `swing/metrics/equity_resolver.py:32`; `read_live_policy` at `swing/metrics/policy.py:39`; `NoActivePolicyError` at `swing/data/repos/risk_policy.py:28`; `compute_position_capital_utilization` at `swing/trades/daily_management.py:381`; `account_equity_snapshots.insert_snapshot` at `swing/data/repos/account_equity_snapshots.py:58` (8 fields incl. snapshot_id; recorded_by NOT NULL); `daily_management.insert_snapshot(conn, *, trade_id, snapshot_fields)` at `swing/data/repos/daily_management.py:411`.
- T-4.1: `bf7e071` baseline reachable via `git grep`.

ZERO signature drift detected. Forward-binding lesson #1 discipline preserved.

## 8. Schema impact verdict

**v21 LOCK preserved.** Migration file count at branch HEAD: 21 (verified via `ls swing/data/migrations/*.sql | wc -l`). NO `swing/data/migrations/0022_*.sql` added. Sub-bundle 2 (temporal log V1+) retains v22 slot per Sec 9.1 Q1 + Q3 LOCKs. Plan §K escalation rule was NOT triggered (no item surfaced unavoidable migration).

## 9. L2 LOCK verification

**Preserved.** `tests/integration/test_l2_lock_source_grep.py::test_l2_lock_no_new_call_sites_vs_commissioning_baseline[schwabdev.Client.]` PASSES. HEAD multiset matches baseline `bf7e071` EXACTLY: 3 matches in both (`swing/integrations/schwab/auth.py`, `swing/integrations/schwab/client.py`, `swing/integrations/schwab/trader.py`). ZERO new `schwabdev.Client.` call sites introduced.

## 10. Operator-witnessed gate readiness

Plan §I S1-S6 + S5a/S5b/S5c runbook is READY for operator-paired verification:
- **S1** (`pytest -m "not slow"` baseline): 6563 passed + 3 skipped (pre-existing); ZERO new fails.
- **S2** (`ruff check swing/`): 0 errors.
- **S3** V2.G3 (VSAT row Sector + Industry post-backfill): operator runs `python -m swing diagnose backfill-trades-sector-industry --dry-run` (then --apply if dry-run looks correct), reloads `/dashboard`, asserts VSAT Sector + Industry render non-NULL; DHA legacy renders em-dash gracefully.
- **S4** V2.G4 (weather chart refresh): operator clicks "Refresh weather chart" button, asserts 204 + browser follows HX-Redirect to `/dashboard`, fresh SPY weather chart renders.
- **S5a** P14.N3 PROVISIONAL: no `account_equity_snapshots` row planted; reload `/daily-management`; PROVISIONAL badge present with `data-cause="snapshot_missing"` + clear-condition tooltip + `(?)` button.
- **S5b** P14.N3 LIVE: plant snapshot row via planting fixture in plan §I; reload; PROVISIONAL badge ABSENT + value renders via `position_capital_utilization_pct_effective` (recomputed proportion when denominators diverge).
- **S5c** P14.N3 policy-missing: `UPDATE risk_policy SET is_active=0`; reload; PROVISIONAL badge present with `data-cause="policy_missing"` + extra-caveat tooltip citing direct-DB-intervention recovery + `(?)` button.
- **S6** cross-fix coexistence regression: all 3 surfaces in same browser session.

## 11. NEW forward-binding lessons banked

No NEW forward-binding lessons surfaced at executing-plans phase. All 13 inherited from prior phases (9 brainstorm + 4 writing-plans) applied per plan §M without amendment. The implementer subagent-driven dispatch surfaced 3 minor banking-worthy observations:
1. **Test-fixture-shape drift discipline applied** -- T-2.1 caught the pre-fix `_StubOhlcvCache.get_or_fetch(self, tickers)` (positional list) silently coexisting with the broken production signature (bare except Exception swallowed the TypeError). Already covered by CLAUDE.md "Synthetic-fixture-vs-production-emitter shape drift" gotcha family; this is the 5TH cumulative instance.
2. **`Trade` dataclass has no `fetch_trade_by_id` repo helper** -- T-1.2 implementer had to use direct SQL for readback. Already implied by orchestrator-side spec verification but worth noting for future trade-touching tasks.
3. **Build-site connection reopening** -- T-3.1 needed a separate `conn_p14n3` because the existing dashboard tile-build loop runs AFTER `conn.close()`. The fix encapsulates open + close in `finally`. Worth observing that `build_dashboard` doesn't carry one persistent connection through its full lifecycle -- future dashboard-VM extensions may want to refactor this rather than open additional connections.

These are NOT yet promoted to CLAUDE.md cumulative gotchas; let Codex chain decide.

## 12. ASCII discipline scope (gotcha #32)

**NEW files (full ASCII verified):**
- `swing/diagnostics/__init__.py`
- `swing/diagnostics/backfill_trades_sector_industry.py`
- `tests/data/repos/test_candidates_sector_industry_helper.py`
- `tests/cli/test_diagnose_backfill_trades_sector_industry.py`
- `tests/web/view_models/__init__.py`
- `tests/web/view_models/test_dashboard_view_model.py`
- `tests/integration/test_l2_lock_source_grep.py`
- `tests/integration/test_phase14_sub_bundle_1_cross_item.py`

**MODIFIED files (NEW regions ASCII verified; pre-existing non-ASCII unchanged per gotcha #16 ASCII-scope-clarity):**
- `swing/data/repos/candidates.py` -- pre-existing 2 em-dashes scrubbed; file now fully ASCII (verified via test_helper_module_source_is_ascii_only).
- `swing/cli.py` -- NEW subcommand region ASCII verified; pre-existing earlier-phase `§` glyphs unchanged.
- `swing/web/routes/dashboard.py` -- pre-existing 2 em-dashes scrubbed; full file ASCII (verified via test_dashboard_route_module_ascii_only).
- `swing/web/view_models/dashboard.py` + `swing/web/view_models/trades.py` -- NEW kwargs + new VM fields ASCII; pre-existing Phase 7-13 docstrings unchanged.
- `swing/web/templates/partials/daily_management_tile.html.j2` -- FULL FILE ASCII (operator-facing render surface; gotcha #32 source-of-truth).
- `tests/web/test_routes/test_dashboard_chart_integration.py` + `tests/web/test_daily_management_tile.py` -- ASCII discipline tests added.

## 13. Cumulative gotcha set application summary

Per plan §F.3 per-task matrix:
- T-1.1: #17 (signature contract) + #18 (1:1 JOIN cardinality via ROW_NUMBER) + #20 (dynamic ? + empty-input short-circuit) + #32 (ASCII).
- T-1.2: #1 (trust test count from pytest) + #4 (PriceCache last-known per ticker analog) + #11 (CLI output discipline) + #21 (cumulative regression cascade audit) + #22 (per-counter accumulation) + #27 (silent-skip-without-audit via per-action SKIP labels) + #32 (ASCII).
- T-2.1: #5 (OHLCV fetch scope unchanged) + #11 (no new HTMX surface) + #17 (signature contract via mock assertion) + #27 (log.warning before 409 degrade) + #32 (ASCII).
- T-3.1: #11 (template + VM audited together) + #17 (signature contract on resolver) + #19 (cascade-call-graph: compute_position_capital_utilization NOT _compute_position_util_pct) + #23 (4 NEW fields attribution unambiguous) + #32 (ASCII).
- T-4.1: #32 (ASCII) + #34 (brief-prescription cross-table verification).
- T-4.2: #1 (trust pytest) + #32 (ASCII final sweep) + #36 (single Codex chain noted).

## 14. Worktree teardown status

Worktree at `.worktrees/phase14-sub-bundle-1-data-wiring-executing-plans/` REMAINS until orchestrator-side merge + post-merge housekeeping. Branch `phase14-sub-bundle-1-data-wiring-executing-plans` ready to push to origin per orchestrator instructions.

## 15. ZERO Co-Authored-By footer drift confirmation

`git log --pretty='%(trailers)' main..HEAD` returns EMPTY (one blank line per commit; ZERO trailer content). Verified across all 5 (pre-closer) + 1 (this closer) = 6 branch commits. Test `test_sub_bundle_1_branch_has_no_co_authored_by_trailers` codifies this as a regression check.

**Cumulative streak preserved: ~599+ commits cumulative ZERO `Co-Authored-By` footer drift through merge of this branch when shipped.** Verified post-Codex-R1-fix-bundle (`9a9836b`): trailer audit clean.

## 16. CLAUDE.md status-line refresh draft text (informational)

Suggested status-line update post-merge of this executing-plans branch (orchestrator decides whether to apply at major milestone):

> **Current state (2026-05-28, HEAD `<merge-sha>`):** Phase 14 Sub-bundle 1 data-wiring SHIPPED end-to-end. 3 defects closed: V2.G3 VSAT lost Sector/Industry on /dashboard (NEW backfill repo helper + diagnose CLI subcommand + restore-SQL artifact); V2.G4 /dashboard "Refresh weather chart" SPY OHLCV error (call-signature fix + module-level logger + narrow ValueError-only catch); P14.N3 /daily-management Capital % PROVISIONAL badge wired (4-field VM contract + denominator-stamping + tooltip + ARIA focusable affordance). 6 commits + 49 NEW fast tests + ZERO Co-Authored-By trailer drift + Schema v21 LOCKED + L2 LOCK preserved via multiset Counter test. 47th cumulative C.C lesson #6 validation slot consumed by this dispatch. Forward-binding lessons 1-13 applied without amendment. Sub-bundle 2 (temporal log V1+) is next per Sec 9.1 Q1 sequencing LOCK.

## 17. Operator-witnessed gate handback summary

This dispatch is **COMPLETE**. Branch `phase14-sub-bundle-1-data-wiring-executing-plans` at HEAD `9a9836b` (7 commits ahead of main `6e65e87`). Codex MCP single-chain CONVERGED at R2 NO_NEW_CRITICAL_MAJOR (2 rounds; 0 CRITICAL + 2 MAJOR + 6 MINOR cumulative; ALL MAJOR resolved in-place via R1 fix bundle; 6 minors banked V2). Operator-witnessed gate S1-S6 + S5a/S5b/S5c ready per plan §I.

Handback to orchestrator for:
1. ~~Codex MCP single-chain adversarial review~~ DONE (R2 NO_NEW_CRITICAL_MAJOR converged).
2. ~~Codex Major findings fix bundles + return-to-Codex~~ DONE (1 fix bundle `9a9836b`; R2 verified resolution).
3. Push branch to origin.
4. Operator-witnessed gate scheduling at plan §I runbook.
5. Merge --no-ff to main + post-merge housekeeping per `feedback_orchestrator_performs_merge` BINDING.
