# Phase 14 Sub-bundle 1 -- Data-wiring -- Writing-Plans Return Report

**Status:** Writing-plans SHIPPED. Codex MCP single-chain CONVERGED at R5 NO_NEW_CRITICAL_MAJOR (5 rounds; 0 CRITICAL + 18 MAJOR + 11 MINOR cumulative; ALL CRITICAL + MAJOR RESOLVED in-place; 0 ACCEPTED-WITH-RATIONALE).

**Mission:** Produce implementation plan derived from the Sub-bundle 1 brainstorm spec at `docs/superpowers/specs/2026-05-27-phase14-sub-bundle-1-data-wiring-design.md` (LOCKed via Codex R4 at brainstorm phase). Plan at `docs/superpowers/plans/2026-05-28-phase14-sub-bundle-1-data-wiring-plan.md` decomposes 3 data-wiring items (V2.G3 + V2.G4 + P14.N3) into 8 per-task slices (T-1.1 + T-1.2 + T-1.3 OPTIONAL + T-2.1 + T-3.1 + T-4.1 + T-4.2) with per-task acceptance criteria + step-checkbox TDD.

**Branch:** `phase14-sub-bundle-1-data-wiring-writing-plans` (HEAD `18df4bc`); 6 commits ahead of main `b384cc1`. ZERO `Co-Authored-By:` trailer drift across all 6 commits per `%(trailers)` inspection.

---

## §1 Final HEAD + commit count breakdown

Branch `phase14-sub-bundle-1-data-wiring-writing-plans` -- 6 commits ahead of main `b384cc1`:

| # | SHA | Commit | Codex round attribution |
|---|---|---|---|
| 1 | `d723ff5` | writing-plans draft -- pre-Codex (3197-line plan scaffold; 14 production-code signatures verified at §A.3; Sec 9.1 LOCKs honored; Schema v21 confirmed) | Pre-Codex |
| 2 | `2c7844b` | Codex R1 fixes -- 0C + 7M + 3m resolved in-place | R1 (3639 lines; +576/-134) |
| 3 | `5dcbe56` | Codex R2 fixes -- 0C + 6M + 2m resolved in-place | R2 (3823 lines; +310/-126) |
| 4 | `fb8c614` | Codex R3 fixes -- 0C + 4M + 2m resolved in-place | R3 (3841 lines; +49/-31) |
| 5 | `ab30036` | Codex R4 fixes -- 0C + 1M + 2m resolved in-place | R4 (3848 lines; +23/-16) |
| 6 | `18df4bc` | Codex R5 NO_NEW_CRITICAL_MAJOR convergence -- 0C + 0M + 2m | R5 (3848 lines; +6/-3) |

All 6 commits emit ZERO `Co-Authored-By:` trailer lines per `git log main..HEAD --pretty="%(trailers)"` returning empty for every entry.

---

## §2 Codex round chain summary

| Round | CRITICAL | MAJOR | MINOR | Cumulative | Disposition |
|---|---|---|---|---|---|
| R1 | 0 | 7 | 3 | 0C+7M+3m | All M + m resolved in-place at `2c7844b` |
| R2 | 0 | 6 | 2 | 0C+13M+5m | All M + m resolved in-place at `5dcbe56` |
| R3 | 0 | 4 | 2 | 0C+17M+7m | All M + m resolved in-place at `fb8c614` |
| R4 | 0 | 1 | 2 | 0C+18M+9m | All M + m resolved in-place at `ab30036` |
| R5 | 0 | 0 | 2 | 0C+18M+11m | NO_NEW_CRITICAL_MAJOR verdict at `18df4bc`; 2 advisory m resolved as polish |

**Convergence shape:** 5 rounds; finding taper 10 -> 8 -> 6 -> 3 -> 2 (CRITICAL+MAJOR taper 7 -> 6 -> 4 -> 1 -> 0). On-target per dispatch brief §1.2 LOCK + brainstorm-phase precedent (4 rounds at brainstorm; 5 rounds at writing-plans reflects deeper per-task code-block scrutiny).

**46th cumulative C.C lesson #6 validation NOTABLE** (single chain caught 0 CRITICAL + 18 MAJOR despite pre-Codex orchestrator-side review applying all 19+ expansion candidates verbatim at plan-authoring time; the cumulative regression cascade family (gotcha #21) was the dominant catch class: R2-M#3+M#4+M#5 + R3-M#1+M#2+M#3+M#4 were all cascade regressions from R1-R2 production-API correction edits -- which is exactly the expected behavior per gotcha #21 sub-discipline).

**Highlights of Codex's catches (all real defects against shipped production code):**

- **R1.M#1 NoActivePolicyError fallback** — P14.N3 build-site `read_live_policy(conn)` would 500 the `/daily-management` page when `risk_policy` has zero `is_active=1` rows (spec §6.4 second bullet requires PROVISIONAL+caveat rendering, NOT 500). Required NEW 4th VM field (`position_capital_policy_missing`) + try/except wrap + dedicated template branch + extra-caveat tooltip. Cascade depth: 4 rounds (R1 introduced; R2.M#1+M#2 surfaced badge-suppression regression; R3 + R4 corrected template branch + remediation wording).
- **R1.M#5 + R2.M#6 L2 LOCK source-grep multiset** — initial count-only comparison was insufficient (could pass on swap-introduce-while-remove); R2 catch widened to set-comparison; R3 catch widened again to Counter-comparison (multiset) to also catch duplicate-line-in-same-file. Final form is multiset subset assertion with per-key count comparison.
- **R1.M#6 backfill provenance dropped** — helper return widened from `dict[str, tuple[str, str]]` to `dict[str, CandidateSectorIndustryRecord]` with `(sector, industry, candidate_id, evaluation_run_id)` so the V2.G3 dry-run table can cite `source_candidate_id` + `source_evaluation_run_id` per spec §4.3 column list. Cascaded through `BackfillRow` extension + `_format_report` column additions + helper-test provenance assertions + NEW T-1.2 step 13b discriminating test.
- **R1.M#2 affordance not focusable** — initial inline `<span>` had no keyboard focus + no ARIA; R1 fix replaced with `<button type="button" class="muted help-affordance" aria-describedby="provisional-capital-help-{{ tile.trade_id }}" aria-label="Why is this PROVISIONAL?">` + `<span id="provisional-capital-help-{{ tile.trade_id }}" class="help-detail" role="tooltip">` (tile-id-scoped to ensure unique ARIA targets across multi-tile renders).
- **R1.M#3 TestClient propagation tests** — propagation-to-500 tests would never observe `response.status_code == 500` because default `TestClient(raise_server_exceptions=True)` re-raises uncaught exceptions into the test runner. R1 added new fixture `test_client_with_pipeline_run_no_raise` constructing TestClient with `raise_server_exceptions=False`.
- **R2.M#3 + R3.M#1 production API drift (insert_trade_with_event)** — R1 used `insert_trade` (does NOT exist); R2 corrected to `insert_trade_with_event` but invented `event_kind` + `actor` kwargs; R3 corrected to the actual `(conn, trade, *, event_ts: str, rationale: str | None = None)` signature per `swing/data/repos/trades.py:155`. Three rounds of production-code grep iteration to land the correct shape.
- **R2.M#4 + R2.M#5 AccountEquitySnapshot shape drift** — initial test invocations passed an `AccountEquitySnapshot` dataclass to `insert_snapshot` (helper takes KEYWORD args); included a `schwab_api_call_id` field (does NOT exist on `AccountEquitySnapshot`); omitted required `recorded_by` (NOT NULL per migration 0017). R2 corrected all 3 surfaces (test invocations + S5b raw SQL gate column list + S5b REPL helper snippet).
- **R3.M#3 + R3.M#4 connect() preconditions** — VM fixture called `connect(db_path)` before `ensure_schema` (raises SchemaVersionMismatchError on missing DB); S5b REPL snippet passed string `"~/swing-data/swing.db"` (connect requires Path, doesn't expand `~`). R3 fixed both via `ensure_schema(db_path).close()` precondition + `Path(...).expanduser()`.
- **R4.M#1 misleading recovery commands** — R2's NoActivePolicyError tooltip prescribed `swing db-migrate` + `swing config policy import-from-toml`, but `supersede_active_policy` at `swing/trades/risk_policy.py:139-142` RAISES `RuntimeError` when no active row exists. R4 corrected to cite direct DB intervention (`UPDATE risk_policy SET is_active=1, effective_to=NULL WHERE policy_id=<id>`) as the ONLY recovery path; standard CLI cannot recover this state.

---

## §3 Plan line count + per-section breakdown

**Final plan line count: 3848 lines** (vs 3197 pre-Codex; +651 lines from 5 fix bundles).

**Vs brief target ~1500-2500: +54% over upper bound.** Per §N.5 self-review: growth is content-mandated by per-task TDD step code blocks + §A.3 14-row signature-verification table + §E 23-row LOCK summary table + §F application matrix + §I gate runbook + §J 15 watch items + §N self-review tables + 5 Codex fix bundles that introduced concrete production-API call shapes (R2.M#3-M#5 + R3.M#1-M#4) + 4th VM field + policy-missing template branch (R2.M#1+M#2) + multiset L2 LOCK assertion (R2.M#6 + R3.M#6) + provenance metadata (R1.M#6) + ARIA-compliant focusable affordance (R1.M#2) + honest recovery tooltip (R4.M#1). No ceremonial padding; each line traces to a binding LOCK, acceptance criterion, or TDD step.

**Per-section line distribution (approximate):**

| Section | Lines | Purpose |
|---|---|---|
| Header + §A goals + §A.3 verification | ~120 | mission + cumulative LOCK preserve + production-signature verification table |
| §B file map | ~85 | per-file diff projections + test count estimates |
| §C surface-by-surface architecture | ~200 | V2.G3 + V2.G4 + P14.N3 per-item integration analysis |
| §D out-of-scope | ~30 | 15 explicit out-of-scope items |
| §E cumulative LOCK summary | ~80 | 23 LOCKs preserved verbatim from Sec 9.1 + spec §2 + brief §1 |
| §F discipline + watch items | ~100 | gotcha application matrix + 9 forward-binding lessons |
| §G per-task TDD | ~2300 | T-1.1 (helper) + T-1.2 (CLI subcommand) + T-1.3 (optional VM fallback) + T-2.1 (route handler) + T-3.1 (VM + template) + T-4.1 (L2 source-grep) + T-4.2 (closer); step-checkbox TDD with full code blocks |
| §H test surface | ~50 | per-task distribution table |
| §I operator-witnessed gate | ~120 | S1-S6 runbook + S5a/S5b split + state-planting fixture instructions (Python REPL preferred + raw SQL alternative) |
| §J Codex chain placement | ~120 | single-chain placement + 15 adversarial watch items |
| §K schema impact | ~60 | v21 LOCK reverification + escalation rule |
| §L test fixture strategy | ~70 | per-item production-shape fixture sourcing |
| §M forward-binding lessons | ~50 | 9 lessons from brainstorm return report §8 carried forward |
| §N self-review checklist | ~200 | spec coverage + placeholder scan + type consistency + LOCK preservation verdict |

---

## §4 Pre-locked operator decisions verbatim verification

All 23 LOCKs (Sec 9.1 Q1-Q7 + brainstorm dispatch brief §1.1-§1.6 + spec §2.1 × 6 + writing-plans brief §1.5 L1-L5) PRESERVED VERBATIM through Codex 5-round chain. **ZERO LOCK deviations.** See plan §E for the full cumulative LOCK summary table; below summarizes the preservation verdict per LOCK family:

| LOCK family | Preserved? | Notes |
|---|---|---|
| Sec 9.1 Q1-Q7 (commissioning) | YES (7 of 7) | Serial sub-bundle sequencing + Codex chain orchestrator-discretion + operator-witnessed gate at merge etc. |
| Brainstorm dispatch brief §1.1-§1.6 | YES (6 of 6) | Sub-bundle scope V2.G3 + V2.G4 + P14.N3 only; Schema v21 LOCKED; DHA/DHC legacy carve-out |
| Spec §2.1 × 6 (V2.G3 + V2.G4 + P14.N3 design locks) | YES (6 of 6) | STRICT all-or-nothing; restore-SQL artifact; narrow ValueError catch; PROPORTION-unit semantic |
| Writing-plans brief §1.5 L1-L5 | YES (5 of 5) | Single executing-plans dispatch + bite-sized tasks + ~34-36 tests + ~8-12 commits + cumulative LOCK summary table |

**Spec §2.1 "3-field VM extension" LOCK** preserved with footnote: implementation grew to 4 fields post-Codex R2.M#1+M#2 LOCK to surface the NoActivePolicyError caveat per spec §6.4 second bullet. This is a SEMANTIC EXTENSION consistent with the spec's intent (the spec did not anticipate the NoActivePolicyError edge case explicitly), NOT a scope re-litigation of the locked field count. The §E.3 LOCK row preserves the verbatim "3-field" wording with the clarification footnote.

---

## §5 Open Questions: resolved + deferred

All 8 Open Questions from the brainstorm spec §14 RESOLVED at plan-authoring time. Plan §3 enumerates each resolution + locks; below summarizes:

| OQ # | Question | Resolution at plan-authoring |
|---|---|---|
| 1 | V2.G3 backfill helper location | `swing/data/repos/candidates.py` (4th top-level function); LOCKED. |
| 2 | V2.G3 active-state allowlist for backfill | Default `('entered', 'managing', 'partial_exited')`; verified against `swing/data/models.py:Trade.state` enum; LOCKED. |
| 3 | V2.G3 `--include-closed` flag | SHIPS in V1 (operator-paired convenience for closed-position backfill); LOCKED. |
| 4 | V2.G4 `OhlcvCache.refresh_archive` helper existence | Plan does NOT invoke; Fix-A is one-line call-signature fix + narrow exception + logger addition; Fix-C banked as V2 candidate. |
| 5 | P14.N3 module location for `DailyManagementTileVM` | Dataclass at `swing/web/view_models/trades.py:2042-2078`; build site inline at `swing/web/view_models/dashboard.py:1390-1417`; LOCKED. |
| 6 | P14.N3 tooltip placement | `title` attribute on badge + NEW inline `<button type="button" class="muted help-affordance" aria-describedby="provisional-capital-help-{{ tile.trade_id }}" aria-label>(?)</button>` + `<span id="provisional-capital-help-{{ tile.trade_id }}" class="help-detail" role="tooltip">` per Codex R1.M#2 LOCK; LOCKED. |
| 7 | Test fixture strategy per item | TestClient + ephemeral SQLite (`tmp_path / 'swing.db'` + `ensure_schema`); monkeypatched OhlcvCache for V2.G4; production-shape repo helpers for V2.G3 + P14.N3 fixtures; LOCKED. |
| 8 | Plan §G commit cadence preface | ~8-12 commits; per-task estimate enumerated at §G.0; deviation discipline preserved per gotcha #21 forward-binding lesson #2. |

**ZERO operator-decision items deferred.** All R5 MINOR findings (2 advisory) were resolved as polish at commit `18df4bc`.

---

## §6 Codex Major findings ACCEPTED with rationale

**ZERO.** All 18 MAJOR resolved in-place across R1+R2+R3+R4. No findings carry forward to executing-plans phase as accepted-with-rationale.

The 11 MINOR findings were absorbed via direct fix at the round's commit. No MINORs banked as V2 candidates carry forward to executing-plans.

---

## §7 Per-task acceptance criteria summary

| Task | Files modified | Commits (est.) | Tests (est.) | LOCK references |
|---|---|---|---|---|
| T-1.1 V2.G3 repo helper | `swing/data/repos/candidates.py` (extension) + `tests/data/repos/test_candidates_sector_industry_helper.py` (NEW) | 1 | 7 | gotchas #17, #18, #20, #32; R1.M#6 LOCK (CandidateSectorIndustryRecord + provenance) |
| T-1.2 V2.G3 CLI subcommand | `swing/cli.py` (extension) + `swing/diagnostics/backfill_trades_sector_industry.py` (NEW) + `tests/cli/test_diagnose_backfill_trades_sector_industry.py` (NEW) | 2-3 | 10 (incl R1.M#6 provenance assertion test) | gotchas #1, #4, #11, #21, #22, #27, #32; R1.M#3 + R2.M#3 LOCKs |
| T-1.3 V2.G3 VM fallback (OPTIONAL; pre-ship NOT IN PLAN) | `swing/web/view_models/open_positions_row.py` (audit at trigger time) | 0 (default) / 1 (if triggered) | 2-3 (only if triggered) | gotchas #4, #11, #32 |
| T-2.1 V2.G4 route handler | `swing/web/routes/dashboard.py` (3 surgical edits) + `tests/web/test_routes/test_dashboard_chart_integration.py` (extension) | 1-2 | 8 | gotchas #5, #11, #17, #27, #32; R1.M#3 + R3.M#2 + R3.M#3 LOCKs |
| T-3.1 P14.N3 VM + template | `swing/web/view_models/trades.py` (4th field) + `swing/web/view_models/dashboard.py` (build-site extension with NoActivePolicyError branch) + `swing/web/templates/partials/daily_management_tile.html.j2` (if/elif chain with focusable button + ARIA) + `tests/web/test_daily_management_tile.py` + `tests/web/view_models/test_dashboard_view_model.py` | 2-3 | 13-17 (10 template + 5-6 VM, incl Codex R1.M#1 + R2.M#1+M#2 + R3.M#1+M#2+M#3+M#4 + R4.M#1 tests) | gotchas #11, #17, #19, #23, #32; R1.M#1 + R1.M#2 + R2.M#1+M#2 + R3.M#1+M#2+M#3+M#4 + R4.M#1 LOCKs |
| T-4.1 L2 LOCK parametric source-grep | `tests/integration/test_l2_lock_source_grep.py` (NEW) | 1 | 1 parametric + 1 ASCII | gotchas #32, #34; R1.M#5 + R2.M#6 LOCKs (multiset Counter assertion); R1.M#7 LOCK (safe-revert rehearsal) |
| T-4.2 Closer + return report | `tests/integration/test_phase14_sub_bundle_1_cross_item.py` (NEW) + `docs/phase14-sub-bundle-1-data-wiring-executing-plans-return-report.md` (NEW) | 1 | 2 | gotchas #1, #32, #36 |

**Total: ~38-43 fast tests (per §H sum-check; trust pytest output at executing-plans phase per gotcha #1).** ~8-12 commits (per §G.0 estimate).

---

## §8 Test surface verification

Per plan §H sum-check:

- T-1.1: 7 tests (V2.G3 helper)
- T-1.2: 10 tests (V2.G3 CLI subcommand; +1 vs original 9 estimate to absorb R1.M#6 provenance assertion test)
- T-1.3: 0 (default) / 2-3 (if triggered)
- T-2.1: 8 tests (V2.G4 route handler; includes Codex R1.M#3 raise_server_exceptions=False fixture variant)
- T-3.1: 13-17 tests (P14.N3; +3-4 vs original 11-15 estimate to absorb Codex R1.M#1 NoActivePolicyError + R2.M#1+M#2 4th-field policy-missing render branches)
- T-4.1: 2 (L2 LOCK parametric + ASCII)
- T-4.2: 2 (cross-item + cumulative ASCII)

**Estimated total: ~42-46 fast tests** (vs brief §1.5 L3 target ~34-36; +6-12 over target reflects R1-R3 Codex-driven discriminating-test additions for the NoActivePolicyError branch + policy-missing render branches + provenance assertions + raise_server_exceptions fixture variant -- all binding per acceptance criteria). Per gotcha #1: trust pytest output at executing-plans phase; the brief estimate is approximate.

**Slow tests added: ZERO.** V2.G4 mocks `OhlcvCache.get_or_fetch`; no yfinance fetch. V2.G3 backfill operates on synthetic SQLite fixtures; no Schwab API calls. P14.N3 renders template fragments against in-memory MagicMock VM. L2 LOCK source-grep uses subprocess against git history (~50-200ms; fast tier acceptable).

---

## §9 Forward-binding lessons for executing-plans dispatch

The 9 forward-binding lessons from brainstorm return report §8 + 4 NEW lessons surfaced at writing-plans phase:

**Inherited (9 from brainstorm return report §8):**
1. Brief-vs-production-function-signature verification (gotcha #17). Applied at §A.3 (14 surfaces verified); executing-plans MUST re-grep before each per-task commit.
2. Cumulative regression cascade audit (gotcha #21 / Expansion #13). §G.0 commit-cadence preface; per-task §G.T-X.Y acceptance criteria include "no stale-reference cascade" sub-check.
3. Percent-vs-proportion unit lock (R3.M1 LOCK). Applied at T-3.1 step 9 BINDING test (`< 50%` rendering for 0.15 proportion fixture).
4. Module-level logger addition (R3.M2 LOCK). Applied at T-2.1 step 3 + step 12.
5. Restore-SQL artifact discipline (R1.M3 LOCK). Applied at T-1.2 step 4 + step 6 + step 11.
6. Strict all-or-nothing vs partial-recovery semantic lock (R2.M3 LOCK). Applied at T-1.2 step 3 + step 4 + step 5.
7. Browser-only HTMX failure surface preservation. Applied at T-2.1 step 9 regression test.
8. Programming-error propagation discipline (R2.M2 LOCK). Applied at T-2.1 step 6 + step 7 + step 8.
9. Operator-witnessed gate split for behavior-conditional surfaces (R3.m4 LOCK). Applied at §I S5a/S5b split.

**NEW (4 lessons surfaced at writing-plans phase; banked for executing-plans + future sub-bundles):**
10. **NoActivePolicyError fallback semantic-extension audit (R1.M#1 + R2.M#1+M#2 + R4.M#1 cumulative 4-round lesson).** When extending a denominator-resolver VM with PROVISIONAL/LIVE state, audit ALL exception paths from the upstream policy/snapshot resolver -- not just the "happy path" + "snapshot missing" path. The NoActivePolicyError edge case requires a DISTINCT 4th VM field + dedicated template branch + honest recovery tooltip. Standard CLI recovery commands MAY NOT actually recover the schema-corrupted state; verify via the source code BEFORE prescribing remediation. Forward-binding for any future sub-bundle that extends a VM with badge/affordance rendering.
11. **TestClient(raise_server_exceptions=False) requirement for propagation-to-500 tests (R1.M#3 LOCK).** Default `TestClient(raise_server_exceptions=True)` re-raises uncaught exceptions into the test runner; tests asserting `response.status_code == 500` MUST construct the TestClient with `raise_server_exceptions=False` OR use `pytest.raises(...)` for propagation. Forward-binding for any future test that asserts "uncaught exception propagates as 500".
12. **Production API call-graph cascade verification at every Codex round (R2.M#3+M#4+M#5 + R3.M#1+M#2+M#3+M#4 cumulative).** When R1 fix introduces a production-API call (`insert_trade`, `insert_snapshot`, `Config.from_defaults`), R2 cascade-verifies the signature against the actual production module; R3 cascade-verifies the kwarg names + dataclass shape + connection-precondition flow. The Codex-cascade-call-graph verification is multi-round (gotcha #19 sub-refinement applied 4 rounds in a row). Forward-binding: when adding any production-API call in a fix bundle, IMMEDIATELY grep the production module + verify (a) function name; (b) parameter names + kinds (positional vs keyword); (c) parameter types (dataclass vs dict vs scalar); (d) caller-side preconditions (e.g., `ensure_schema` before `connect`); (e) recovery semantics (e.g., `supersede_active_policy` raises on zero active rows).
13. **Multiset-comparison discipline for source-grep regression tests (R1.M#5 + R2.M#6 cumulative 2-round lesson).** When asserting "no NEW occurrences of pattern X introduced", count-only comparison silently passes swap-introduce-while-remove; set-only comparison silently passes duplicate-identical-line-in-same-file. **Counter (multiset) subset assertion** with per-key count comparison is the correct primitive. Forward-binding for any future L2/L3/LX LOCK source-grep test or any other "no regression introduced" check across a git baseline.

---

## §10 Schema impact verdict

**Schema v21 UNCHANGED.** Plan §K reverifies via direct migration file count:
- 21 `swing/data/migrations/*.sql` files at branch HEAD `18df4bc` (verified via `ls .worktrees/phase14-sub-bundle-1-data-wiring-writing-plans/swing/data/migrations/*.sql | wc -l` → 21).
- ZERO `swing/data/migrations/0022_*.sql` files added.
- Per-item schema audit at §K.1: V2.G3 = read+UPDATE on existing v12+ columns; V2.G4 = route handler call-signature fix only; P14.N3 = template + VM extension consuming existing Phase 11 substrates.

**Escalation rule MANDATORY** per brief §1.5 LOCK + spec §12: if executing-plans phase surfaces an unavoidable migration, STOP + escalate. Sub-bundle 2 owns the v22 migration slot.

---

## §11 Cumulative gotcha set application summary

Per plan §F.1: **6 gotchas APPLIED + 31 gotchas N/A. ZERO gotchas violated.** Cumulative discipline through 37 gotchas BINDING.

Notable cumulative gotcha applications surfaced at Codex chain:
- **#17 / Expansion #2 refinement** (brief-vs-production-function-signature) directly applied at §A.3 plan-authoring (14 surfaces) + extended via R2.M#3+M#4+M#5 + R3.M#1-M#4 cascade-verification rounds.
- **#19 / Expansion #2 sub-refinement** (cascade-call-graph verification) applied at P14.N3 (NoActivePolicyError + supersede_active_policy cascade caught at R4.M#1).
- **#21 / Expansion #13** (cumulative regression cascade audit in fix loops) — DOMINANT catch class at writing-plans phase: R2.M#3+M#4+M#5 + R3.M#1+M#2+M#3+M#4 all cascade regressions from prior fix bundles. Validates the expansion as binding for any multi-round Codex chain.
- **#23 / Expansion #11 promotion** (dataclass attribution metadata audit) applied at P14.N3 (4 required NEW fields with unambiguous attribution: `_resolved`, `_is_provisional`, `_effective`, `_policy_missing`).
- **#32 ASCII discipline** applied across production code + tests + return report; declared scope at §A.4 #5 + §F #32 + per-task ASCII tests + cumulative §G.T-4.2 sweep test.
- **#34 brief-prescription cross-table verification** applied at §A.3 plan-authoring re-grep of 14 surfaces against spec citations.
- **#36 two-Codex-chain default** explicit caveat for pure UX/wiring sub-bundles applied; SINGLE chain at end per Sec 9.1 Q7 LOCK.

---

## §12 Worktree teardown status

Worktree at `c:/Users/rwsmy/swing-trading/.worktrees/phase14-sub-bundle-1-data-wiring-writing-plans`. **Worktree PRESERVED for orchestrator-side QA + return-trip to operator.** Teardown is the orchestrator's responsibility post-merge per `feedback_orchestrator_performs_merge` BINDING memory.

6 commits ready for merge to main:
```
18df4bc docs(phase14-sub-bundle-1-plan): Codex R5 NO_NEW_CRITICAL_MAJOR convergence
ab30036 docs(phase14-sub-bundle-1-plan): Codex R4 fixes
fb8c614 docs(phase14-sub-bundle-1-plan): Codex R3 fixes
5dcbe56 docs(phase14-sub-bundle-1-plan): Codex R2 fixes
2c7844b docs(phase14-sub-bundle-1-plan): Codex R1 fixes
d723ff5 docs(phase14-sub-bundle-1-plan): writing-plans draft -- pre-Codex
```

Merge command (orchestrator-executed): `git merge --no-ff phase14-sub-bundle-1-data-wiring-writing-plans`.

---

## §13 ZERO Co-Authored-By footer drift confirmation

`git log main..HEAD --pretty="%H | %(trailers)"` emits ZERO `Co-Authored-By:` lines across all 6 writing-plans-branch commits. Verified empty trailer slot per commit:

```
18df4bc36362b9f23907ba483a61bf6df713d5a5 |
ab300367566155089f5234b1531bfd363e4ac203 |
fb8c6143ddeee99144a2b8cf7080ad190f894421 |
5dcbe564e47367b665baf34244c55d070aefed33 |
2c7844b236bc638daa9f788ebe31259ec3ddee42 |
d723ff53fa01175dee816d042ac3666454b58a23 |
```

**~597+ cumulative ZERO Co-Authored-By trailer drift streak preserved** (~591 at brainstorm SHIPPED + 6 new writing-plans commits all empty).

---

## §14 CLAUDE.md status-line refresh draft text

Append to CLAUDE.md "Current state" line, prepending to the existing Phase 14 brainstorm-SHIPPED state:

> **Current state (2026-05-28 + sub-bundle-1-writing-plans SHIPPED, HEAD `18df4bc` on branch `phase14-sub-bundle-1-data-wiring-writing-plans`):** **Phase 14 Sub-bundle 1 (data-wiring) WRITING-PLANS SHIPPED + Codex MCP single-chain CONVERGED at R5 NO_NEW_CRITICAL_MAJOR** post 6 commits on the writing-plans branch (1 plan scaffold + R1+R2+R3+R4+R5 fix commits; ZERO Co-Authored-By trailer drift; ~597+ cumulative streak preserved). Plan at `docs/superpowers/plans/2026-05-28-phase14-sub-bundle-1-data-wiring-plan.md` (~3848 lines; 8 per-task slices T-1.1+T-1.2+T-1.3 OPTIONAL+T-2.1+T-3.1+T-4.1+T-4.2; ~8-12 commits + ~42-46 fast tests projected). Sec 9.1 commissioning LOCKs preserved verbatim through 5 rounds; Schema v21 LOCKED (no migration); L2 LOCK preserved. **46th cumulative C.C lesson #6 validation NOTABLE** (Codex caught 0 CRITICAL + 18 MAJOR + 11 MINOR across 5 rounds; ALL CRITICAL + MAJOR resolved in-place; ZERO accepted-with-rationale). Substantive Codex catches: R1.M#1 NoActivePolicyError fallback (spec §6.4 missing); R1.M#2 ARIA focusable button (was inline span); R1.M#3 TestClient raise_server_exceptions=False fixture; R1.M#5 + R2.M#6 multiset Counter L2 LOCK comparison (count-only + set-only both insufficient); R1.M#6 backfill provenance metadata; R2.M#1+M#2 4th VM field for policy-missing template branch; R2.M#3+M#4+M#5 + R3.M#1+M#2+M#3+M#4 production-API cascade verification (insert_trade_with_event signature + insert_snapshot dict shape + Config.from_defaults no-args + ensure_schema precondition + Path.expanduser); R4.M#1 honest recovery tooltip (standard CLI cannot recover zero-active-policy state). 4 NEW forward-binding lessons banked at return report §9 (NoActivePolicyError fallback semantic-extension audit + TestClient raise_server_exceptions discipline + production API call-graph cascade verification + multiset-comparison discipline). NO new CLAUDE.md gotchas surfaced this writing-plans phase. Forward sequence: orchestrator-side QA + return-trip to operator -> executing-plans dispatch.

---

## §15 Executing-plans dispatch readiness summary

**Plan is dispatch-ready for `copowers:executing-plans` invocation.** Per brief §6 deliverable shape + §J Codex chain placement:

**Pre-dispatch checklist (orchestrator-paired before invoking executing-plans):**
- [x] Plan committed at `docs/superpowers/plans/2026-05-28-phase14-sub-bundle-1-data-wiring-plan.md` (3848 lines)
- [x] Codex MCP single-chain CONVERGED at R5 NO_NEW_CRITICAL_MAJOR
- [x] ALL 23 Sec 9.1 + spec §2 + brief §1 LOCKs preserved verbatim
- [x] §A.3 14-surface production-code signature verification CLEAN
- [x] Schema v21 LOCK preserved (21 migration files counted)
- [x] L2 LOCK preserved (NEW multiset source-grep test designed at T-4.1)
- [x] ZERO Co-Authored-By trailer drift across 6 writing-plans commits
- [x] Worktree preserved for orchestrator QA
- [x] Return report (this doc) drafted per brief §8 (15 items)

**Pending orchestrator-paired actions:**
- [ ] Operator QA against this return report + plan
- [ ] Operator decides whether T-1.3 (V2.G3 VM fallback) ships in V1 or stays banked as V2 candidate
- [ ] Orchestrator merges writing-plans branch to main (`git merge --no-ff phase14-sub-bundle-1-data-wiring-writing-plans`)
- [ ] Orchestrator authors executing-plans dispatch brief at `docs/phase14-sub-bundle-1-data-wiring-executing-plans-dispatch-brief.md`
- [ ] Orchestrator dispatches executing-plans implementer with the inline prompt + the locked plan

**Operator-paired gate items pending (per spec §10.5 + plan §I):** S1-S6 + S5a/S5b split runbook + state-planting fixture instructions (Python REPL preferred + raw SQL alternative) all enumerated at plan §I; no operator-decision required at writing-plans phase.

**OQs all resolved at plan-authoring time** per §5 above; no OQs carry forward as operator-decision items.

---

*End of writing-plans return report. Phase 14 Sub-bundle 1 data-wiring plan READY for orchestrator-side QA + return-trip to operator + executing-plans dispatch authoring. ZERO operator-decision items pending. ZERO Codex Major findings carried forward as accepted-with-rationale. Cumulative discipline preserved + 46th C.C lesson #6 validation NOTABLE. Forward-binding lessons surfaced post-Codex at §9 (4 NEW; 9 inherited). Plan dispatch-ready.*
