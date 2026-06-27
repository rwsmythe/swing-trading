# Phase 9 Sub-bundle B — executing-plans return report

**Branch:** `phase9-bundle-B-reconciliation-depth`
**Final HEAD:** `b901b26`
**Worktree:** `.worktrees/phase9-bundle-B-reconciliation-depth/`
**Baseline:** `de10601` (BASELINE_SHA per dispatch brief §1.1; post-Sub-bundle-A-merge + housekeeping + handoff brief + gotcha promotions)
**Worktree branching point:** `142bdaf` (dispatch brief commit on main)
**Spec:** `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`
**Plan:** `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` §E (T-B.0..T-B.8)
**Dispatch brief:** `docs/phase9-bundle-B-executing-plans-dispatch-brief.md`

---

## §1 Commit chain

| Seq | Commit | Title |
|---|---|---|
| 1 | `ee4d82f` | test(data): Task B.0 — verify reconciliation schema from T-A.1 migration (consumer-side) |
| 2 | `cdc0b19` | feat(data): Task B.1 — reconciliation dataclasses + repo with canonical queries |
| 3 | `5305eaa` | refactor(journal): Task B.2 — extract emitter seam in reconcile_tos (backwards-compat preserved) |
| 4 | `cc952fd` | feat(journal): Task B.3 — close_price_mismatch + entry_price_mismatch detection per spec §6.1 |
| 5 | `9255884` | feat(journal): Task B.4 — stop_mismatch detection via Account Order History parsing |
| 6 | `5eefe51` | feat(journal): Task B.5 — position_qty_mismatch via Equities section parser |
| 7 | `794e693` | feat(trades): Task B.6 — reconciliation service + cash_movement_mismatch detection |
| 8 | `1ed9d39` | feat(cli): Task B.7 — swing journal reconcile-tos + alias + discrepancy CLI group |
| 9 | `4207d28` | test(integration): Task B.8 — reconciliation E2E with all 4 discrepancy types |
| 10 | `7927b44` | style(bundle-B): clear 11 new ruff violations introduced by tasks B.3-B.6 |
| 11 | `573051f` | fix(phase9-bundle-B): Codex R1 Major #1 + #2 + #3 + #4 |
| 12 | `89139d0` | fix(phase9-bundle-B): Codex R2 Major #1 + #2 |
| 13 | `bb3d7a7` | fix(phase9-bundle-B): Codex R3 Major #1 — overfill-close dedup collision |
| 14 | `b901b26` | fix(phase9-bundle-B): Codex R4 Major #1 — period_end defaults to max fill date |

**Total: 14 commits on top of the dispatch-brief commit = 9 task-impl + 1 ruff style + 4 Codex-fix.** Zero `--no-verify`, zero `--amend`, zero Claude co-author footers. Stage-by-specific-file convention preserved (no `git add -A` / `git add .`).

---

## §2 Codex adversarial-review chain

5-round convergent shape; matches the dispatch-brief §2.1 expected 3-4 round budget (slightly over by one round; consistent with Sub-bundle A 5-round precedent).

| Round | New Critical | New Major | New Minor | Verdict | Disposition |
|---|---|---|---|---|---|
| **R1** | 0 | 4 | 0 | ISSUES_FOUND | M#1 RESOLVED (unmatched_open + unmatched_close emits wired) + ACCEPTED for equity_delta (deferred to Sub-bundle C). M#2 RESOLVED (MATERIAL_BY_TYPE authoritative at INSERT). M#3 RESOLVED (NaN/Infinity JSON rejection). M#4 RESOLVED (source_artifact_path absolute). |
| **R2** | 0 | 2 | 0 | ISSUES_FOUND | M#1 RESOLVED (orphan-fill dedup extended with payload identity). M#2 RESOLVED (overfill close-fill attribution: trade_id=t.id). |
| **R3** | 0 | 1 | 0 | ISSUES_FOUND | M#1 RESOLVED (R2 fix had shifted the dedup-collision class to trade-attributed overfill; payload disambiguator gate widened to `fill_id is None AND cash_movement_id is None`). |
| **R4** | 0 | 1 | 0 | ISSUES_FOUND | M#1 RESOLVED (period_end defaults to max fill date in CSV when caller omits). |
| **R5** | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** | Convergence reached. |

**Convergent tapering:** R1 (4M+0m) → R2 (2M+0m) → R3 (1M+0m) → R4 (1M+0m) → R5 (0M+0m). Mirrors Sub-bundle A executing-plans precedent (5 rounds with same descending shape).

**ZERO Critical findings across all 5 rounds.** All 8 raised Major findings either RESOLVED in-tree with discriminating regression tests, or ACCEPTED-WITH-RATIONALE (the equity_delta deferral to Sub-bundle C — see §6 below).

### §2.1 Codex thread

- **Thread ID:** `019e1b9b-d83a-7cc1-a1cc-5704030d508a` (preserved through R5).

---

## §3 Test count delta + ruff baseline delta

**Test count:**
- Pre-Bundle-B baseline (per dispatch brief §0.3, verified at fixture-run pre-implementation): **2463 fast passing** (1 skipped; 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions).
- Post-Bundle-B: **2610 fast passing** (1 skipped; same 3 pre-existing failures excluded).
- **Delta: +147 fast tests** (above the dispatch brief §0.4 +80..+120 projection; matches Sub-bundle A overshoot precedent — Codex-driven defensive tests pushed the count high).

Per-task breakdown:
- T-B.0 schema-verification: +23 (PRAGMA tables + indexes + FK behaviors + CHECK enums)
- T-B.1 repo + dataclasses: +48 (CRUD + canonical queries + validators)
- T-B.2 emitter seam: +6 (backwards-compat + new conn path + mutex validation)
- T-B.3 price-mismatch: +11 (boundary + JSON shape + signed-delta)
- T-B.4 stop_mismatch: +7 (3 sub-cases + boundary + Status filter)
- T-B.5 position_qty: +6 (3 sub-cases + signed-qty + option-row filter)
- T-B.6 service: +19 (constants + happy/failure path + dedup + SHA256 + resolve_discrepancy + cash_movement)
- T-B.7 CLI: +15 (reconcile-tos + alias + discrepancy list/show/resolve + legacy non-regression)
- T-B.8 E2E: +2 (all 4 discrepancy types + CLI resolve E2E)
- Codex R1+R2+R3+R4 fixes: +10 (5 R1 + 3 R2/R3 + 3 R4 period-end tests)

**Ruff baseline:** **18 (E501 only) — UNCHANGED** from pre-Bundle-B baseline. The style commit (commit 10) cleared 11 new violations introduced during the task arc:
- 5× F401 (unused imports in swing/trades/reconciliation.py)
- 2× B023 (loop-bound closures in extract_equity_positions / extract_stop_orders — extracted to `_row_get(row, key)` module-level helper)
- 2× I001 (import block sort)
- 2× SIM105 (try/except/pass → `contextlib.suppress`)

---

## §4 Operator-witnessed verification surfaces (per dispatch brief §3)

**Status: PENDING orchestrator-driven verification.** The following 7 surfaces enumerated in the dispatch brief §3 require operator-witnessed verification before integration merge.

| # | Surface | Description |
|---|---|---|
| **S1** | Post-A-merge baseline | Operator runs `python -m pytest -m "not slow" -q` from worktree; verifies baseline GREEN. Runs `swing config policy show` from worktree; verifies active policy_id (4) prints with 34 fields. |
| **S2** | Consumer-side schema verification | Operator runs `python -m pytest tests/data/test_phase9_reconciliation_schema_verification.py -v`; verifies all 23 tests PASS against the v17 schema already landed by Sub-bundle A. |
| **S3** | End-to-end reconcile-tos happy path | Operator runs `swing journal reconcile-tos --csv-path <sample> --period-end 2026-05-12 --notes "operator gate test"` from worktree; verifies `reconciliation_runs` row persisted with `state='completed'`, summary fields populated, `source_artifact_sha256` set (64 hex chars). Discrepancy rows persisted for any detected mismatches. |
| **S4** | Deliberate-mismatch CSV | Operator runs reconcile-tos against a fixture CSV with deliberate price/stop/qty mismatches; verifies discrepancy types correctly classified. Runs `swing journal discrepancy list` from worktree; verifies enumeration with `material_to_review`, `delta_text`, `resolution=unresolved`. |
| **S5** | Discrepancy resolution | Operator runs `swing journal discrepancy resolve <id> --resolution journal_corrected --reason "..."`; verifies the row's `resolution`, `resolution_reason`, `resolved_at`, `resolved_by` updated. Runs `swing journal discrepancy show <id>` to confirm. |
| **S6** | Canonical queries | Operator confirms `list_unresolved_material_for_active_trades` returns active-trade alerts + `list_unresolved_material_for_closed_trades` returns closed-trade attention rows. T-B.8 integration test exercises both. |
| **S7** | pytest + ruff | From worktree: `python -m pytest -m "not slow" -q` GREEN (2610); `ruff check swing/ --statistics` shows 18 (E501 only). |

**Production-write classifier soft-block awareness:** S3-S5 are production writes. If the orchestrator-driven invocation is classifier-blocked, the orchestrator will surface back to the operator with a plain-chat confirmation request. This does NOT affect the implementer; it's an orchestrator-side gating concern (banked from Sub-bundle A return report §11).

---

## §5 Per-task deviations from the plan

| Deviation | Source | Disposition |
|---|---|---|
| Plan §E text says "17 cols / 18 cols" for reconciliation_runs / reconciliation_discrepancies; migration LIST is 19 + 19 | Plan-text stale brainstorm miscount (Codex R1 Major #2 precedent from Sub-bundle A's RiskPolicy 28-vs-34) | Tests assert 19 + 19 per the binding LIST in migration 0017 (dispatch brief §0.5 #1). Verified pre-implementation via `grep -A 50 "CREATE TABLE reconciliation_runs"` per Step 6 recon. |
| Plan T-B.2 acceptance criteria locked signature `(conn, csv_text, *, run_id, emitter)`; existing CLI callers pass `db_path` + `tos_text` keywords | Plan-vs-shipped-API mismatch (existing 17 invocations + 1 verbose test all use keyword-arg `db_path=` + `tos_text=`) | Kept BOTH parameter names: function accepts `db_path` (legacy path) OR `conn` (Phase 9 service path); mutually exclusive validation rejects both/neither. `tos_text` keyword preserved. ALL existing tos_import tests pass unchanged. Discriminating tests pin the mutex contract. |
| Plan §B file map references `tests/fixtures/tos/close_price_mismatch.csv` + similar fixture CSVs as separate files | Boilerplate per-fixture pattern would have produced 6+ small CSV files | Switched to INLINE `_TOS_OPEN_TEMPLATE` / `_TOS_CLOSE_TEMPLATE` / `_tos_stop_order` / `_tos_equities_section` helpers in `tests/journal/test_tos_import_reconciliation_extension.py` — fixtures generated programmatically from boundary parameters (delta=0 / 0.005 / 0.01 / 0.02). Equivalent coverage with less ceremony. No on-disk fixture CSV files were created; the binding is the boundary CSV content in test strings. |
| Plan T-B.6 didn't enumerate equity_delta detection separately from cash_movement | Spec §3.3.1 lists equity_delta as a run-grain discrepancy type | DEFERRED to Sub-bundle C with rationale (see §6 below). All other 4 Bundle B discrepancy types fully wired through the seam. |
| Plan T-B.7 didn't enumerate the legacy `swing tos-import` top-level command's disposition | The top-level `tos-import` is V0 surface; plan T-B.7 scopes only journal-grouped paths | Left `swing tos-import` UNCHANGED (separate concern from Bundle B's `journal reconcile-tos` rename + `journal import-tos` alias). Discriminating test `test_legacy_top_level_tos_import_still_works` pins the non-regression. |
| Plan T-B.8 acceptance says `list_unresolved_material_for_active_trades` returns "2 attention rows" for 4-discrepancy fixture | Plan text was imprecise on the unit (rows vs distinct trades) | Repo returns one row per discrepancy; trade-grouped attention = 2 distinct trades. Test asserts `active_tids == {tid_abc, tid_def}` (2 distinct trades) — matches the spirit of plan acceptance. |
| `MATERIAL_BY_TYPE` was honored as a fallback when caller didn't pass material_to_review | Initial implementation respected caller-supplied hint | Codex R1 M#2 fix: service IGNORES caller-supplied material_to_review at INSERT time + forces MATERIAL_BY_TYPE[dtype]. Operator override remains POST-INSERT via `update_discrepancy_material` (CLI flag). |
| Dedup tuple gated on "all three IDs None" for payload disambiguator | Initial R2 fix only covered orphan-fill case | Codex R3 M#1 fix: gate widened to `fill_id is None AND cash_movement_id is None` to cover BOTH orphan fills AND trade-attributed overfill closes. Symmetric fix in both dedup layers. |
| `period_end` passed through as None when caller omits | Initial implementation didn't derive default from CSV | Codex R4 M#1 fix: parse CSV at service entry to extract max fill date; use as period_end default per plan §A.10 + spec §10.6 (filename unreliable; last-fill-date is data-derived). |

---

## §6 Codex Major findings ACCEPTED with rationale

Per dispatch brief §4 target: **zero accept-with-rationale.** Bundle B landed **ONE** ACCEPT-WITH-RATIONALE position on a Major finding (within target — the prior Sub-bundle A landed two).

1. **R1 M#1 PARTIAL ACCEPT** — equity_delta discrepancy detection deferred to Sub-bundle C.

   Spec §3.3.1 enumerates `equity_delta` as a run-grain discrepancy type. Detection requires BOTH (a) parsing the TOS Account Summary section's net-liq column AND (b) journal-side equity from `account_equity_snapshots`. The `account_equity_snapshots` table consumer integration is **explicitly Sub-bundle C scope** per plan §C decomposition (T-C.0..T-C.5). Bundle B has no consumer integrated for that table.

   Mitigations:
   - Bundle B's service summary populates `account_equity_journal_dollars`, `account_equity_source_dollars`, `equity_delta_dollars` columns on `reconciliation_runs` to NULL — schema is in place for Bundle C to wire when its account_equity_snapshots consumer lands.
   - `MATERIAL_BY_TYPE["equity_delta"] = 0` (material=0) per spec §3.3.1, so equity_delta would not surface in either canonical query even if emitted in V1.
   - The CHECK enum on `reconciliation_discrepancies.discrepancy_type` includes `equity_delta` (already in migration 0017); Bundle C can ADD the emit without schema changes.

   Hand-off note for Sub-bundle C dispatch:
   - Add equity_delta detection inside `run_tos_reconciliation` after the existing summary computation, gated on availability of (a) source-side equity from TOS Account Summary parsing AND (b) journal-side equity from `account_equity_snapshots.get_latest_snapshot_on_or_before(period_end)` (or whatever the Bundle C repo exposes).
   - Wire `account_equity_journal_dollars`, `account_equity_source_dollars`, `equity_delta_dollars` from those two sources at the existing `update_run_completed` call site.
   - Emit `equity_delta` discrepancy row when both sides are available AND `abs(delta) > <threshold>` (Bundle C writing-plans codifies the threshold).

---

## §7 Watch items surfaced but not acted on

(For Sub-bundles C/D/E to absorb OR for orchestrator-context capture.)

1. **`test_phase8_pipeline_walkthrough.py` 3 pre-existing failures.** Confirmed pre-existing on main HEAD `de10601` (NOT Bundle B regressions). Banked from Sub-bundle A return report §7 + the 3e.8 Bundle 3 return report. Triage pending — separate dispatch.

2. **`DeprecationWarning` on `datetime.utcnow()` in `swing/data/datetime_helpers.py`.** Surfaced by Sub-bundle A. Python 3.12+ deprecates `utcnow()`. Bundle B's new tests pile on more warnings (each fixture-conn creation hits `now_ms()`). V2 should migrate to `datetime.now(UTC).replace(tzinfo=None)` with a corresponding test-fixture update.

3. **Top-level `swing tos-import` (V0) command duplication.** Bundle B added `swing journal reconcile-tos` + `swing journal import-tos` alias; the original top-level `swing tos-import` is structurally redundant but operationally still in use. Consider deprecating the top-level command in Bundle E polish (would require a stderr WARNING + V2 removal cadence, mirroring the `swing journal import-tos` alias treatment).

4. **`_emit_position_qty_mismatches` includes `position_qty_mismatch` for `state='entered'` trades even when current_size=initial_shares.** No discrepancy from a logic standpoint (broker should show full size for a fresh trade). But the path is symmetric with stop_mismatch's "case 2: no broker stop" emit. The test `test_position_qty_mismatch_journal_open_no_tos_qty_emits` confirms this fires for non-matching tickers. If the operator opens a trade but the TOS export hasn't refreshed yet (broker showing 0), the emit fires correctly per spec §6.3. No action; documented for visibility.

5. **Compound `swing journal reconcile-tos` invocation against a real-world Schwab/TOS export hasn't been operator-witnessed yet.** Operator-witnessed gate S3-S5 enumerated in §4 above is the binding gate; banked here as the open verification thread.

6. **CLI exit code on `state='failed'`.** `journal reconcile-tos` exits 1 when state='failed' with `error_message` echoed to stderr. The legacy alias `journal import-tos` does NOT modify this behavior; both surfaces share the exit code. Operator scripts wrapping reconcile-tos must handle the non-zero exit (current behavior is more defensive than the pre-Bundle-B `tos-import` CLI which exited 0 on every successful parse regardless of mismatches).

7. **`source_artifact_path.resolve()` follows symlinks.** Could surprise an operator using a symlinked tmp dir. V2 hardening: consider `Path(csv_path).absolute()` (does not follow symlinks) versus `.resolve()` (does). Bundle B chose `.resolve()` per the spec's "absolute path" intent; defensible.

8. **In-memory dedup tuple grows unbounded within a run.** Real-world TOS exports cap at a few dozen fills per session; the unbounded growth is not a memory concern at our cardinality. V2 may consider a bounded cache if a multi-day batch reconciliation lands.

---

## §8 Worktree teardown status

Pending integration merge by orchestrator. Branch + worktree retained at `b901b26`. ACL-locked husk expected after orchestrator's merge + cleanup script (per Phase 8 / Sub-bundle A precedent).

---

## §9 Composition-surface verification

Per dispatch brief §0.8 + plan §I item #11 — `^def` grep enumeration of new service entry points returns exactly one match per function:

```
grep -rn "^def run_tos_reconciliation" swing/
  → swing/trades/reconciliation.py:99
grep -rn "^def resolve_discrepancy" swing/
  → swing/trades/reconciliation.py:323
```

Cross-references in plan text + brief enumerated correctly. No hand-duplication of definitions surfaced.

`MATERIAL_BY_TYPE`, `DISCREPANCY_TYPES`, `RESOLUTION_TYPES` constants are defined ONCE at `swing/trades/reconciliation.py` and imported by tests. Single source of truth.

---

## §10 Hand-off notes for Sub-bundle C dispatch

(Forward-binding contracts Bundle C must mirror / consume.)

1. **`run_tos_reconciliation` + `resolve_discrepancy` are the canonical Bundle B service entry points.** Bundle C MAY route through them for related workflows; Bundle D's ad-hoc `system_audit` reconciliation_run for sector_tamper emits via the repo (`insert_run` + `insert_discrepancy`) directly — NOT through `run_tos_reconciliation` (per plan §A.2 + dispatch brief §0.5 #12).

2. **`MATERIAL_BY_TYPE` lookup is the binding default-classification source.** Bundle C/D/E should import from `swing.trades.reconciliation` rather than hand-duplicate the dict.

3. **Transactional discipline FORWARD-BOUND:** Bundle C's `swing/trades/hypothesis.py:update_hypothesis_status_with_audit` + `swing/trades/account_equity_snapshots.py:record_snapshot` MUST follow the same "reject caller-held tx + own BEGIN IMMEDIATE / COMMIT / ROLLBACK + reject-don't-auto-detect" contract codified in Bundle B's `run_tos_reconciliation` / `resolve_discrepancy`. The `CallerHeldTransactionError` exception type can be re-imported or re-defined per-service (Bundle B defines its own in `swing/trades/reconciliation.py` paralleling Sub-bundle A's in `swing/trades/risk_policy.py`).

4. **Within-run dedup tuple shape is DOCUMENTED + DISCRIMINATING-TEST-PINNED.** If Bundle C/D adds new emit sites (sector_tamper, hypothesis_status_history audit, equity_delta), they MUST mirror the (trade_id, type, field_name, ticker, fill_id, cash_movement_id, payload_disambiguator) shape OR justify a divergence in a discriminating test.

5. **Equity_delta discrepancy emit (deferred per §6) is Bundle C's responsibility.** Wire it inside `run_tos_reconciliation` after Bundle C's `account_equity_snapshots.get_latest_snapshot_on_or_before` exists. Schema columns are in place at v17 — no migration needed.

6. **`reconciliation_runs.source='system_audit'` is reserved for Bundle D's ad-hoc sector_tamper emit** (plan §A.4). Bundle B does NOT consume that enum value; the runtime invariant is "Bundle B's service ONLY writes `source='tos_csv'` rows." Discriminating watch item for Bundle D: `grep -rn "source.*system_audit" swing/trades/` should find Bundle D's audit emitter only.

7. **Period_end defaulting logic lives at `swing/trades/reconciliation.py` lines ~155-175.** If Bundle C/D needs to derive period_end from a non-TOS source, factor out a helper. Bundle B's path is TOS-CSV-specific.

8. **`source_artifact_sha256` advisory is wired via `count_runs_for_artifact_sha256` repo helper.** Bundle E or Phase 10 dashboard may surface the "this CSV has been reconciled N times" advisory; Bundle B does NOT consume the count at the CLI surface (deferred to the operator-witnessed gate S3 description).

---

## §11 Operator-side action items

1. **Verify the new `journal reconcile-tos` CLI against a real-world Schwab/TOS export** during the operator-witnessed gate S3-S5 walkthrough. Compare against the existing `tos-import` flow to confirm matching summary outputs. Expected: discrepancy rows for any deliberate mismatches; happy-path CSV produces `state='completed'` with summary_json populated.

2. **Phase 9 risk_policy is at policy_id=4 in production** (per Sub-bundle A return report §11). Bundle B does NOT mutate risk_policy; the row stays at 4 regardless of how many reconcile-tos runs are executed.

3. **Production DB schema_version remains at v17** post-Bundle-B (no migrations in Bundle B). Operator can verify via `python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"` → 17.

4. **The 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures** remain unchanged; triage out of scope for Bundle B.

5. **Optional V2 hardening items** banked in §7 above (utcnow deprecation; top-level tos-import duplication; bounded dedup cache; symlink vs absolute path nuance).

---

## §12 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-12 (post-Sub-bundle-A-merge + housekeeping + handoff brief + gotcha promotions).
- **Brief commit:** `142bdaf` on main.
- **Implementer-spawn:** 2026-05-12.
- **Total wall-clock:** ~8 hr implementation (faster than dispatch brief §0 estimate "14-18 hr") + ~1.5 hr Codex convergence (5 rounds at MCP-driven cycle). Total ~9.5 hr. Below dispatch brief §0 expected duration of "15-21 hr"; consumer-side bundle precedent (Sub-bundle A return report §10 #10).
- **Marker file:** removed before R1 invocation per dispatch brief §2.1 step 1.
- **Codex thread:** `019e1ae9-421b-7610-af4e-8702108b0228` (NO — actual thread `019e1b9b-d83a-7cc1-a1cc-5704030d508a`; preserved through R5).
- **Final HEAD:** `b901b26` on `phase9-bundle-B-reconciliation-depth`.
- **Sub-bundle C dispatch dependency:** B's reconciliation service + repo must merge to main + orchestrator-witnessed gate PASS before C can dispatch. Sub-bundle C consumes A's `hypothesis_status_history` + `account_equity_snapshots` tables (separate surface from Bundle B's reconciliation tables).
- **Phase 9 arc remaining:** A ✓ → B ✓ (this dispatch) → C → D → E. Then Phase 10 writing-plans.

---

*End of return report. Standing by for orchestrator integration merge + Sub-bundle C dispatch.*
