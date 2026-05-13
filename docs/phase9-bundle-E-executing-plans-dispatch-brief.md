# Phase 9 Sub-bundle E — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-bundle E (final polish + Phase 10 hand-off prep) of the Phase 9 implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` §H (3 tasks T-E.0 … T-E.2) PLUS one NEW task T-E.3 added by this brief from the operator-paced phase3e-todo backlog (Account Order History multi-line parser gap; banked 2026-05-12 from Sub-bundle B operator-witnessed gate finding).

**Expected duration:** ~6-10 hr implementation + ~1-2 hr Codex convergence. Total ~7-12 hr. Sub-bundle E is wider than D (which was 4-7 hr) because T-E.3 is a substantive parser refactor (multi-line order grouping + status filter widening + STP trigger-price extraction), but narrower than B (which was 14-18 hr; B introduced 5 new tables' worth of consumer code).

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-bundle E + the NEW T-E.3 carve-out per this brief §0.5 #6.
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 4 tasks land. Expected **2-4 Codex rounds**: T-E.3 has real-world fixture corpus + 3 operator-confirmed multi-line patterns, so Codex may explore tamper-vector-style attack surface as it did with D (which converged in 4).

---

## §0 Inputs

### §0.1 Plan
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (2257 lines; Codex R5 confirmation; LOCKED at `a0c7223`).
- **Sub-bundle E section:** §H (lines 2049-2113). 3 plan tasks T-E.0 / T-E.1 / T-E.2.
- **Plan §A resolved-during-planning items:** lines 13-216 — relevant for T-E.3 (the parser fix inherits §A.2 + §A.10 + §A.11 service-discipline lessons + §A.8 NO INSERT OR REPLACE).
- **Plan §B file-map:** lines 218-282. T-E.0..T-E.2 file scope is mostly tests + docs. T-E.3 adds parser fixes in `swing/journal/tos_import.py` + regression fixtures.
- **Plan §C decomposition (line 294):** Sub-bundle E depends on A + B + C + D landings. Closes Phase 9.
- **Plan §I watch items (lines 2116-2140):** cross-bundle invariants — Bundle E verifies the Phase 9 arc-final state.

### §0.2 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; LOCKED at `31ee51c`).
- **Read for §11 Phase 10 hand-off section** (BINDING for T-E.2 hand-off note).
- **Read §6.2 stop_mismatch detection** (BINDING for T-E.3 parser fix — clarifies the SPEC INTENT vs the parser's current narrow implementation).
- **Read §7 sector/industry tamper hardening** (BINDING for spec-amendment item — recon doc at `docs/phase9-bundle-D-task-D0-recon.md` carries the post-R2 supersession that should be reflected in spec text per Sub-bundle D return report §6.3 + §8 #1).

### §0.3 Project state at dispatch time
- **HEAD on `main`:** `6ba1925` at brief-commit time (post-Sub-bundle-D-merge `4894688` + housekeeping). After this brief commits, the worktree-branching-point is the brief commit SHA.
- **Test count:** **2757 fast (5 skipped — 4 implementer SKIP-on-absent for `thinkorswim/*.csv` in worktree; 1 prior); 3 pre-existing failures** on `tests/integration/test_phase8_pipeline_walkthrough.py` ("archive returned None"). NOT regressions; NOT Bundle-E-introduced. Banked for separate triage.
- **Ruff baseline:** **18 (E501 only).** Unchanged from Sub-bundle A + B + C + D baseline.
- **Schema version:** **v17.** Production DB at `%USERPROFILE%/swing-data/swing.db` has all Phase 9 tables. **Sub-bundle E does NOT bump the schema_version.**
- **Active risk_policy:** `policy_id=4`. Sub-bundle E tests SHOULD NOT depend on a specific policy_id; instead query `read_active_policy(conn)`.
- **Production reconciliation state:** 4 reconciliation_runs (B run #1 + C run #2 + D runs #3+#4); 13 discrepancies all resolved as `acknowledged_immaterial`. NOT touched by Bundle E unless T-E.0 E2E test exercises a new fixture run.
- **Production account_equity_snapshots:** 2 manual snapshots from Sub-bundle C gate.
- **Production hypothesis_status_history:** 4 seed + history from Sub-bundle C gate's id=2 transition cycle.
- **Worktree husks pending operator cleanup-script:** 7 (3e8-bundle-3 + phase9-bundle-A + phase9-bundle-B + phase9-bundle-C + phase9-bundle-D + phase9-writing-plans + polish-2026-05-10). Does NOT block dispatch.

### §0.4 Sub-bundle E scope (3 plan tasks + 1 NEW from backlog)

Per plan §H + the new T-E.3 from `docs/phase3e-todo.md` 2026-05-12 entry:

| Task | Title | Key files |
|---|---|---|
| **T-E.0** | Combined E2E happy path test exercising the operator's natural workflow across A + B + C + D surfaces (policy edit → reconcile-tos → resolve discrepancy → account snapshot → hypothesis update → tamper-attempt → audit row appears → canonical query returns expected count) | NEW `tests/integration/test_phase9_full_happy_path.py` |
| **T-E.1** | CLAUDE.md gotcha promotion candidates ratification (implementer drafts inline; orchestrator triages at integration merge) — **most candidates already promoted at orchestrator housekeeping commits `de10601` (3 gotchas from Sub-bundle A) + `6ba1925` (2 gotchas from Sub-bundle D)**; T-E.1's residual scope is verifying nothing was missed + drafting any additional candidates surfaced during T-E.0 + T-E.3 implementation | MODIFY `CLAUDE.md` if new candidates surface; else (recon-only) |
| **T-E.2** | Phase 10 hand-off note + final ruff sweep (verify Phase 9 introduced NO new ruff violations beyond the established 18 E501 baseline; enumerate the Phase 10 capture-needs that Phase 9's schema now satisfies) | MODIFY `docs/phase3e-todo.md` (Phase 10 hand-off note) + run `ruff check swing/ --statistics` (verify 18) |
| **T-E.3 (NEW; from phase3e-todo)** | Account Order History multi-line parser fix in `swing/journal/tos_import.py` (per phase3e-todo 2026-05-12 entry) — widens `extract_stop_orders` to detect multi-line order groups (header `MKT GTC WORKING` + continuation `<price> STP STD`); includes WAIT TRG status alongside WORKING; handles conditional `TRG BY #ID BASE-X.XX STP STD` chained pattern; regression tests against 4 real-world fixture CSVs at `thinkorswim/*.csv` (copy a subset to `tests/fixtures/tos/schwab-real-world-*.csv` for tracked regression corpus) | MODIFY `swing/journal/tos_import.py`; NEW fixture CSVs in `tests/fixtures/tos/` + NEW tests in `tests/journal/test_tos_import_stop_extractor.py` |

**Cross-bundle dependencies:** Sub-bundle E depends on Sub-bundles A + B + C + D landings. The combined E2E test (T-E.0) exercises all 4 prior bundles' surfaces. T-E.3 modifies Bundle B's parser code (explicit cross-bundle carve-out for the Bundle E polish task per operator instruction 2026-05-12).

### §0.5 BINDING contracts from plan §A + Sub-bundle A/B/C/D landings (DO NOT re-litigate)

1. **Migration 0017 is LOCKED + FROZEN.** Sub-bundle E DOES NOT modify it. `EXPECTED_SCHEMA_VERSION = 17` is in `swing/data/db.py`. Sub-bundle E ships tests + parser fix + docs on top.

2. **T-E.0 combined E2E happy path** exercises the operator's actual workflow but uses tmp-DB + tmp-cfg fixtures (NOT production DB). Discriminating tests cover (a) policy edit via CLI, (b) `swing journal reconcile-tos` against a fixture CSV with deliberate mismatches, (c) `swing journal discrepancy resolve`, (d) `swing account snapshot`, (e) `swing hypothesis update` with identity-transition INFO path, (f) `/trades/entry` POST with sector/industry tamper rejection emitting audit row, (g) `swing journal discrepancy list --unresolved --material` returning expected attention set. Mirror E2E test files from prior bundles.

3. **T-E.1 CLAUDE.md gotcha promotion ratification.** The orchestrator already banked 5 CLAUDE.md gotcha promotions across the Phase 9 arc (3 at de10601 from Sub-bundle A; 2 at 6ba1925 from Sub-bundle D). Sub-bundle E's T-E.1 is RESIDUAL — verify nothing else surfaced during T-E.0 + T-E.3 implementation that should be promoted. Likely zero new promotions; T-E.1 commit is "ratification + close-out" (no-op-or-tiny addition). If T-E.3 surfaces a Schwab/TOS parser-format gotcha, promote it.

4. **T-E.2 Phase 10 hand-off note** in `docs/phase3e-todo.md`. Enumerate the Phase 10 capture-needs Phase 9's schema satisfies: `risk_policy` (versioned governance + grade weights + low-sample-size thresholds + bootstrap_resample_count); `account_equity_snapshots` (live_capital_denominator_dollars source); `reconciliation_runs` + `reconciliation_discrepancies` (operator-paced material-attention surfaces for the metrics dashboard); `hypothesis_status_history` (per-hypothesis-cohort temporal filtering for metric aggregation per spec §11.3); `trades.risk_policy_id_at_lock` + `review_log.risk_policy_id_at_review_completion` (per-row policy stamping for historical-row re-interpretation prevention per spec §11.1). Final ruff sweep verifies 18 unchanged.

5. **T-E.3 parser fix BINDING contracts** (operator-confirmed during Sub-bundle B + C gates 2026-05-12 against real-world export `thinkorswim/2026-05-12-AccountStatement.csv` + 3 prior samples):

   - **Multi-line order grouping.** Account Order History uses 2-line groups: header `STOCK SELL TO CLOSE qty ticker ~ MKT GTC WORKING` + continuation `<price> STP STD`. Parser must read header + N continuation rows until next dated header OR section boundary.
   - **STP trigger extraction.** Continuation row's price column carries the actual STP trigger; handle both simple absolute (`4.36 STP STD`) AND conditional `TRG BY #ID BASE-X.XX STP STD` + absolute trigger row variants.
   - **Status filter widening.** Include `WAIT TRG` alongside `WORKING` (both indicate placed-but-not-yet-filled stops). `CANCELED` + `FILLED` correctly remain excluded.
   - **Backwards compatibility.** Existing fixture-based discriminating tests from Bundle B (boundary delta=0/0.005/0.01/0.02 + 3 stop_mismatch sub-cases) MUST still pass. The parser refactor adds capability; does NOT remove existing behavior.
   - **Real-world regression corpus.** Copy a subset of `thinkorswim/2026-05-12-AccountStatement.csv` + `2026-04-15-AccountStatement.csv` + `2026-04-30-AccountStatement.csv` + `2026-05-08-AccountStatement.csv` to `tests/fixtures/tos/` (operator hasn't formalized the corpus location yet; T-E.3 should). The 4 sample exports cover: simple absolute-price stops (3 of 4); conditional `TRG BY ... BASE-X.XX` + absolute trigger row chain (1 of 4: 2026-04-30 CC); `WAIT TRG` status (1 of 4: 2026-05-08 DHC); `CANCELED` rows (1 of 4: 2026-05-08).
   - **Regression test** that reconciles `thinkorswim/2026-05-12-AccountStatement.csv` against a fixture journal with the 5 open trades from operator's production state (DHC $7.62, YOU $54.06, VSAT $63.23, CVGI $4.36, LAR $7.00) + asserts ZERO stop_mismatch discrepancies emitted (the post-fix matching path). Mirror for 2026-05-08 export with `WAIT TRG` DHC.
   - **Spec §6.2 wording amendment** — current spec text describes single-line STP rows; T-E.3 introduces the multi-line group reality. The amendment can land via the recon-doc-supersession pattern (analogous to Sub-bundle D's `docs/phase9-bundle-D-task-D0-recon.md` carrying the spec §7 supersession) OR via direct spec amendment per V2.1 §VII.F. **Recommendation:** add a `docs/phase9-bundle-E-task-E3-parser-recon.md` note documenting the multi-line group structure observed in the operator's 4 sample exports + supersede spec §6.2's single-line assumption with the post-T-E.3 binding design.

6. **No new HTMX form-driven surfaces in Bundle E.** Bundle E is parser + tests + docs only. Phase 5 HTMX gotchas not relevant for Bundle E.

7. **No `INSERT OR REPLACE` anywhere in Bundle E.** Plan §A.8 baseline. T-E.3's parser fix is read-only on the CSV side; no new SQL writes (the emit path already exists via Bundle B's `insert_discrepancy`). Discriminating watch item: `grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/` post-Bundle-E returns zero matches.

8. **Bundle B's `MATERIAL_BY_TYPE` + `DISCREPANCY_TYPES` + `RESOLUTION_TYPES` constants are LOCKED.** Bundle E MUST NOT modify them. T-E.3 emits via existing `MATERIAL_BY_TYPE['stop_mismatch']` lookup (already set to 1 per Bundle B; correct for the post-fix matching path).

9. **Operator's `thinkorswim/*.csv` files are currently untracked** per Sub-bundle B/C gate findings. T-E.3 should formalize the corpus: copy a subset to `tests/fixtures/tos/schwab-real-world-*.csv` for the regression tests; keep the originals untracked at the operator's working location (avoids leaking account number `27097300SCHW` in tracked test fixtures). **Sanitize the copies:** strip the operator's actual account number from the header line; replace with `<account>` placeholder. Keep all order + fill + price + section content intact for parser exercising.

10. **2 V2 candidates banked in `docs/phase3e-todo.md` 2026-05-12** are NOT Bundle E scope: (a) Schwab inception-CSV ingestion (richer than 7-day; could seed cash_movements + account_equity_snapshots historical series); (b) `account_equity_snapshots.equity_dollars` semantic formalization (cash-basis vs net-liq). Both deferred to post-Phase-9 or V2. Bundle E's T-E.3 covers ONLY the parser-gap fix for stop_mismatch.

11. **Spec §7 wording amendment from Sub-bundle D** (recon doc `docs/phase9-bundle-D-task-D0-recon.md` §3+§4 carries the post-R2 supersession; spec text still names the original `(ticker, action_session_for_run(now))` design) is OPTIONAL Bundle E scope. If implementer has spare capacity, can land via the recon-doc-supersession pattern OR direct spec amendment per V2.1 §VII.F. Otherwise defer to Phase 10 spec review.

### §0.6 Sub-bundle A + B + C + D landed surfaces (FORWARD-BOUND)

Sub-bundle A merged at `6c8f3a9`. Sub-bundle B merged at `e96834a`. Sub-bundle C merged at `e5d5892`. Sub-bundle D merged at `4894688` + housekeeping at `6ba1925`. Sub-bundle E builds on:

- **Sub-bundle A's `swing/trades/risk_policy.py`** canonical service-layer entry points (T-E.0 E2E uses for the cfg-cascade leg).
- **Sub-bundle A's `swing/data/datetime_helpers.py:now_ms` + `validate_ms_iso`** — T-E.0 E2E uses for server-stamped fields.
- **Sub-bundle B's `swing/data/repos/reconciliation.py:insert_run` + `insert_discrepancy`** — T-E.0 + T-E.3 emit via these.
- **Sub-bundle B's `swing/trades/reconciliation.py:run_tos_reconciliation`** — T-E.0 E2E exercises the full reconcile flow; T-E.3 verifies the parser fix doesn't break this service.
- **Sub-bundle B's `swing/trades/reconciliation.py:MATERIAL_BY_TYPE` + `DISCREPANCY_TYPES` + `RESOLUTION_TYPES`** — T-E.3 uses lookup (NOT modification).
- **Sub-bundle C's `swing/trades/account_equity_snapshots.py:record_snapshot`** + `swing/trades/hypothesis.py:update_hypothesis_status_with_audit` + `swing/journal/tos_import.py:extract_account_summary_net_liq` — T-E.0 E2E uses all 3.
- **Sub-bundle D's `_emit_sector_tamper_audit` in `swing/web/routes/trades.py`** + `sector_industry_evaluation_run_id` hidden form anchor — T-E.0 E2E uses via TestClient simulation of the tamper rejection path (mirroring Sub-bundle D's `test_phase9_bundle_d_e2e_sector_tamper_audit_surfaces_in_cli_list`).
- **`tests/conftest.py` test fixtures** establishing a v17 DB + A + B + C + D fixtures. Bundle E tests inherit.

### §0.7 Sub-bundle A + B + C + D lessons FORWARD-BINDING

Per Sub-bundle A return report §7 + B + C + D + CLAUDE.md gotcha promotions at `de10601` + `6ba1925`:

- **CLAUDE.md gotchas banked 2026-05-12** (5 total: Phase 9 ratification single-fire; cascade emitter no-op-skip; USERPROFILE+HOME monkeypatch; form-anchor round-trip; POST-time-recompute TOCTOU). Bundle E's T-E.0 E2E test fixture-setup MUST monkeypatch USERPROFILE+HOME (the third gotcha). T-E.3 parser tests do NOT exercise write_user_overrides, so monkeypatch is defensive-only.
- **Sub-bundle B + C + D transactional-discipline lessons.** T-E.3 modifies the parser but NOT the service-layer transaction discipline (Bundle B's `run_tos_reconciliation` already owns its transaction; T-E.3 changes only the row-extraction logic inside that transaction).
- **Sub-bundle B Account Order History parser-gap** is the T-E.3 scope itself. Operator's 4 sample exports at `thinkorswim/*.csv` are the corpus.
- **Sub-bundle C inception-CSV ingestion candidate** is NOT Bundle E scope; banked V2 in phase3e-todo.
- **Sub-bundle C account_equity_snapshots semantic formalization** is NOT Bundle E scope; banked V2.
- **Sub-bundle D spec §7 wording amendment** is OPTIONAL Bundle E scope per §0.5 #11.
- **Sub-bundle D operator-witnessed gate findings** are integration-merged + housekept; no carry-over.

### §0.8 OPERATOR'S PRODUCTION DB STATE (T-E.3 regression-test target)

Operator's production DB at `%USERPROFILE%/swing-data/swing.db` has 5 open trades with `current_stop` values matching Schwab's working SELL TO CLOSE STP orders (per Sub-bundle B operator-witnessed gate finding):

| Ticker | trade_id | current_stop | Schwab STP trigger |
|---|---:|---:|---:|
| DHC | 2 | $7.62 | $7.62 (header `MKT GTC WORKING` + continuation `7.62 STP STD`) |
| YOU | 4 | $54.06 | $54.06 (same pattern) |
| VSAT | 5 | $63.23 | $63.23 |
| CVGI | 7 | $4.36 | $4.36 |
| LAR | 8 | $7.00 | $7.00 |

T-E.3's regression test: after parser fix, reconcile `thinkorswim/2026-05-12-AccountStatement.csv` against the production journal (via fixture-DB-copy) + assert ZERO stop_mismatch discrepancies emitted. **Pre-fix expectation:** 5 false-positive stop_mismatch discrepancies (current Bundle B behavior; operator-witnessed during Sub-bundle B gate). **Post-fix expectation:** 0 stop_mismatch discrepancies. This is the binding pass/fail criterion for T-E.3.

For multi-pattern coverage: also test `2026-04-30-AccountStatement.csv` (conditional TRG BY chain) + `2026-05-08-AccountStatement.csv` (WAIT TRG status) + `2026-04-15-AccountStatement.csv` (which has empty Account Order History — verify graceful empty-section handling).

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `phase9-bundle-E-polish-and-phase10-handoff`
- **Worktree directory:** `.worktrees/phase9-bundle-E-polish-and-phase10-handoff/` (project convention per CLAUDE.md + Sub-bundle A/B/C/D precedent).
- **BASELINE_SHA:** `6ba1925` (post-Sub-bundle-D-merge + housekeeping; HEAD of main BEFORE this brief commits).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the dispatch-brief commit SHA after this brief lands).
- The Codex diff (`6ba1925` → worktree HEAD) will include one doc-only commit (this dispatch brief). Harmless; Codex evaluates the IMPLEMENTATION against the PLAN scoped to Sub-bundle E + T-E.3.

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefix:
  - `test(integration): T-E.0 — combined E2E happy path across A+B+C+D surfaces`
  - `docs(claude-md): T-E.1 — Phase 9 candidate gotcha promotion ratification` (likely small or no-op; most candidates already promoted)
  - `docs(phase3e-todo): T-E.2 — Phase 10 hand-off note + final ruff sweep clean`
  - `feat(journal): T-E.3 — Account Order History multi-line parser fix (operator gate Bundle B finding 2026-05-12)`
  - `fix(area): Codex RN Major #X (internal) — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §H mark per-step boundaries (for T-E.0..T-E.2); T-E.3 follows its own brief-side acceptance criteria in §0.5 #5.
- **Prefer `git add <specific-files>` over `git add -A`** — Phase 8 R1 Critical 1 lesson banked 2026-05-07.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§3 surfaces below) — narrower than D's BINDING-browser scope; Bundle E is mostly test + parser + docs.
- **Orchestrator owns:** integration merge to main + post-merge housekeeping. **Bundle E SHIP CLOSES Phase 9.** Post-Bundle-E orchestrator queues Phase 10 writing-plans dispatch.

### §1.5 Verify command
PowerShell from inside worktree (per Phase 5 editable-install lesson + Sub-bundle A/B/C/D precedent):
```powershell
$env:PYTHONPATH = "."; python -m swing.cli journal reconcile-tos --csv-path "C:\Users\rwsmy\swing-trading\thinkorswim\2026-05-12-AccountStatement.csv" --period-end 2026-05-11 --notes "T-E.3 parser fix verification"
```
(After T-E.3 lands. Pre-fix this would emit 5 stop_mismatch false positives; post-fix should emit 0.)

---

## §2 Adversarial review (Codex)

### §2.1 Setup (IMPLEMENTER runs this)

After ALL 4 task-family commits land + tests GREEN at branch HEAD:

1. `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
2. Invoke `copowers:adversarial-critic` with:
   - `PHASE`: `phase9-bundle-E-polish-and-phase10-handoff`
   - `SPEC_PATH`: `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`
   - `PLAN_PATH`: `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (Codex scopes to §H Sub-bundle E PLUS the §0.5 #5 T-E.3 cross-bundle parser-fix carve-out)
   - `BASELINE_SHA`: `6ba1925`
3. Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **2-4 rounds**. T-E.0 + T-E.2 are mostly tests + docs (light Codex surface). T-E.1 is recon-only or tiny. T-E.3 is the substantive Codex target — multi-line parser edge cases + status-filter widening + conditional `TRG BY` chain handling could expose 2-3 rounds of refinement.

### §2.2 Codex value-add concentration

Adversarial review for Sub-bundle E typically catches:
- **T-E.3 parser edge cases.** Empty Account Order History section (1 of 4 sample exports); single-line orders without continuation (degraded export); WAIT TRG with no continuation; CANCELED with continuation (should be skipped); multi-stock chained continuations (e.g., BASE-X then absolute then another order).
- **T-E.3 over-matching.** If the parser is too liberal (e.g., treats EVERY MKT GTC WORKING row as a stop regardless of continuation), it could spuriously match orders that aren't actually stops. The continuation row is the discriminator — verify it's required.
- **T-E.3 status enum coverage.** If a new status surfaces in real-world exports (e.g., "ACCEPTED" or "ROUTING"), the parser must handle it (default: treat as not-working; skip).
- **T-E.0 E2E test fixture-DB contamination.** If the test forgets to monkeypatch USERPROFILE+HOME (CLAUDE.md gotcha), writes leak to operator's REAL `~/swing-data/user-config.toml`.
- **T-E.2 ruff sweep verifies 18 unchanged.** If T-E.3 introduces a single new violation (e.g., line-too-long in the new multi-line parser logic), Codex flags.
- **Section-header parsing edge cases.** The CSV section-header detection (Account Order History, Account Trade History, Equities, etc.) needs to be robust against extra whitespace / case variation / column-count variation. Operator's 4 samples are a baseline; future exports may vary.
- **Fixture sanitization completeness.** If T-E.3 copies CSVs to `tests/fixtures/tos/` and forgets to strip the operator's `27097300SCHW` account number from the header, that's a privacy leak in tracked-test-fixtures.

---

## §3 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR. Per plan §H + new T-E.3 verification:

- **S1 — Post-D-merge baseline + ruff sanity.** From worktree: `python -m pytest -m "not slow" -q` returns 2757+ pass / 5+ skip / 3 pre-existing failures (Bundle E adds ~10-25 tests). `ruff check swing/ --statistics` shows 18 (E501 only). `swing config policy show` returns active policy_id (4) with 34 fields.
- **S2 — T-E.0 combined E2E test runs.** `python -m pytest tests/integration/test_phase9_full_happy_path.py -v` GREEN.
- **S3 — T-E.3 parser-fix verification against operator's real-world exports.** From worktree: `swing journal reconcile-tos --csv-path "C:\Users\rwsmy\swing-trading\thinkorswim\2026-05-12-AccountStatement.csv" --period-end 2026-05-11 --notes "operator gate Bundle E S3 — T-E.3 verification"`. Expected: ZERO stop_mismatch discrepancies emitted (vs Bundle B baseline of 5 false positives). Verify via `swing journal discrepancy list` — should show only equity_delta (if applicable per Bundle C path) + cash_movement discrepancies (if any); NO stop_mismatch.
- **S4 — Alternate fixture verification.** Repeat S3 against `thinkorswim/2026-05-08-AccountStatement.csv` (has WAIT TRG DHC) + `thinkorswim/2026-04-30-AccountStatement.csv` (has TRG BY chain CC). Verify both produce ZERO stop_mismatch (matching path).
- **S5 — pytest + ruff final.** From worktree: `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows 18 (E501 only).

**Expected test count delta:** +10 to +30 fast tests (T-E.0 E2E adds ~2-5; T-E.1 zero; T-E.2 zero; T-E.3 adds ~5-15 across multi-line variants + boundary tests + 4 fixture-CSV regression tests + 1 production-state regression).

**Expected ruff baseline:** 18 (no change).

**Production-write classifier soft-block awareness:** S3 + S4 are production-write paths (new reconciliation_runs rows written each invocation). If the orchestrator-driven invocation is classifier-blocked, the orchestrator will surface back to the operator with a plain-chat confirmation request. Same pattern as Sub-bundles B + C gates.

**Post-gate cleanup:** S3 + S4 emit reconciliation_runs (run #5 + #6 + #7 from operator's production DB at gate time). Operator may elect to resolve the (likely zero) stop_mismatch discrepancies as the gate validation OR leave them as historical runs. No trade rows are created/modified.

---

## §4 Return report shape

After operator-gate PASS, draft return report at `docs/phase9-bundle-E-return-report.md` (mirroring `docs/phase9-bundle-D-return-report.md` shape):

1. Final HEAD on branch.
2. Commit count breakdown (task-impl per T-E.X + Codex-fix + operator-gate-fix).
3. Codex round chain.
4. Test count delta + ruff baseline delta.
5. Operator-gate surface results (S1-S5).
6. Per-task deviations from the plan (especially any T-E.3 deviations from the brief).
7. Codex Major findings ACCEPTED with rationale (target: zero; D achieved zero; E should also).
8. Watch items surfaced but not acted on (post-Phase-9 V2 candidates).
9. Worktree teardown status.
10. Composition-surface verification (T-E.3 may introduce new private helpers in `swing/journal/tos_import.py`; enumerate via `^def` grep).
11. **Phase 9 arc closing notes.** Total commits across A+B+C+D+E; total Codex rounds; total test additions; ACCEPT-WITH-RATIONALE breakdown; Phase 10 dispatch readiness.

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading phase9-bundle-E-polish-and-phase10-handoff dispatch.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase9-bundle-E-polish-and-phase10-handoff
BRANCH: phase9-bundle-E-polish-and-phase10-handoff
BASELINE_SHA: 6ba1925  (per dispatch brief §1.1; HEAD of main BEFORE the brief commit; post-Sub-bundle-D-merge + housekeeping)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (6ba1925 → worktree HEAD) will include one doc-only commit (this dispatch brief). Harmless; Codex evaluates the IMPLEMENTATION against the PLAN scoped to Sub-bundle E + the §0.5 #5 T-E.3 cross-bundle parser-fix.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase9-bundle-E-polish-and-phase10-handoff -b phase9-bundle-E-polish-and-phase10-handoff $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase9-bundle-E-executing-plans-dispatch-brief.md

Step 2 — Read the plan §A + §B + §C + §H + §I end-to-end:
  docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md

Step 3 — Read the spec (focus on §6.2 stop_mismatch detection for T-E.3 contract; §11 Phase 10 hand-off for T-E.2; §7 sector_industry tamper recon doc for optional spec amendment):
  docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md

Step 4 — Read binding conventions + Sub-bundle A + B + C + D landings:
  - CLAUDE.md (gotchas; project conventions; 5 NEW gotchas from Phase 9 arc landings — Sub-bundle A at de10601 + Sub-bundle D at 6ba1925 — all forward-binding)
  - docs/orchestrator-context.md (orchestrator-role framing; 2 lessons from Sub-bundle A at de10601)
  - docs/phase9-bundle-A-return-report.md (§7 + §10)
  - docs/phase9-bundle-B-return-report.md (§7 + §10)
  - docs/phase9-bundle-C-return-report.md (§7 + §10)
  - docs/phase9-bundle-D-return-report.md (§7 + §10 + §11; especially §8 #2+#3 gotcha promotion candidates already landed at 6ba1925 + §6.3 spec §7 wording amendment pending)
  - docs/phase9-bundle-D-task-D0-recon.md (template for the T-E.3 recon-doc-supersession pattern)
  - docs/phase3e-todo.md (3 V2/E candidates banked 2026-05-12: T-E.3 covers ONLY Account Order History parser-gap; inception-CSV + snapshot-semantics are V2 carve-outs)
  - docs/phase9-writing-plans-dispatch-brief.md §0.3 + §7 (9-lesson catalog FORWARD-BINDING)

Step 5 — Verify worktree state:
  git rev-parse HEAD                                          # expect current main HEAD (typically the dispatch brief commit)
  git status                                                  # expect clean
  python -m pytest -m "not slow" -q                           # expect baseline GREEN (2757 passed, 5 skipped; 3 pre-existing fails NOT regressions)
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 17

Step 6 — Pre-implementation grep recon (Bundle 2+3 + Sub-bundle A + B + C + D lesson applied):
  grep -rn "^def " swing/data/repos/reconciliation.py        # Bundle B's insert_run + insert_discrepancy
  grep -rn "extract_stop_orders\|stop_order_extractor" swing/journal/tos_import.py  # Bundle B's current parser (your T-E.3 fix target)
  grep -rn "MATERIAL_BY_TYPE\|DISCREPANCY_TYPES" swing/trades/reconciliation.py    # LOCKED constants (do not modify)
  grep -rn "_emit_sector_tamper_audit" swing/web/routes/trades.py    # Sub-bundle D's helper (T-E.0 E2E exercises)
  grep -rn "run_tos_reconciliation\|resolve_discrepancy" swing/  # Bundle B service entry points
  grep -rn "update_hypothesis_status_with_audit\|record_snapshot" swing/  # Bundle C service entry points
  ls thinkorswim/                                              # confirm 4 sample exports present (for T-E.3 corpus)
  head -3 thinkorswim/2026-05-12-AccountStatement.csv         # verify operator's account number is visible (need to sanitize for fixtures)
  grep -n "WORKING\|WAIT TRG\|STP STD" thinkorswim/2026-05-12-AccountStatement.csv  # familiarize with multi-line pattern
  ls swing/data/migrations/                                   # confirm 0017 is only Phase 9 migration + no 0018 attempt (BINDING — Bundle E does NOT modify migrations)
  Capture divergences from plan assumptions; surface in return report §6.

Step 7 — Invoke copowers:executing-plans:
  - PHASE: phase9-bundle-E-polish-and-phase10-handoff
  - SPEC_PATH: docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md
  - PLAN_PATH: docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
  - BASELINE_SHA: 6ba1925
  - SCOPE: Sub-bundle E only (tasks T-E.0 through T-E.2 in plan §H) PLUS T-E.3 cross-bundle parser-fix per dispatch brief §0.5 #5.

Step 8 — TDD per task. Plan §H per-task `- [ ]` boundaries cover T-E.0..T-E.2; T-E.3 follows brief §0.5 #5 acceptance criteria.

Step 9 — After ALL tasks land + GREEN, run adversarial review per dispatch brief §2.1. Iterate Codex rounds until NO_NEW_CRITICAL_MAJOR. Expected 2-4 rounds.

Step 10 — Draft return report at docs/phase9-bundle-E-return-report.md per dispatch brief §4. Include Phase 9 arc closing notes §11. Commit it.

Step 11 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator drives §3 witnessed verification gate; orchestrator handles integration merge; **Bundle E SHIP CLOSES Phase 9**. Orchestrator queues Phase 10 writing-plans dispatch next.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers
  - Skip the Step 6 pre-implementation grep recon
  - Modify migration 0017 in any way (Bundle E is consumer-side only; atomicity BINDING per Sub-bundle A landing)
  - Bump EXPECTED_SCHEMA_VERSION beyond 17 (Bundle E does NOT advance the schema)
  - Modify Bundle B's MATERIAL_BY_TYPE / DISCREPANCY_TYPES / RESOLUTION_TYPES constants (LOCKED)
  - Modify Bundle B's run_tos_reconciliation service signature (T-E.3 modifies ONLY the parser inside; service contract unchanged)
  - Add cross-bundle code BEYOND the §0.5 #5 T-E.3 carve-out (no inception-CSV ingestion — V2; no snapshot-semantics formalization — V2)
  - Add UPDATE schema_version statements
  - Use INSERT OR REPLACE or REPLACE INTO anywhere
  - Copy operator's `thinkorswim/*.csv` files to `tests/fixtures/tos/` WITHOUT sanitizing the account number (privacy leak risk)
  - Diverge from plan §A locked decisions without explicit Codex justification
  - Use `git add -A` or `git add .` (per Phase 8 R1 Critical 1 lesson; stage specific files)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-12 (post-Sub-bundle-D-merge + housekeeping; closing-Phase-9 brief).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `6ba1925` on main (post-Sub-bundle-D-merge + housekeeping).
- **Worktree path (binding):** `.worktrees/phase9-bundle-E-polish-and-phase10-handoff/`.
- **Baseline test count:** 2757 fast (5 skipped); 3 pre-existing failures NOT regressions.
- **Baseline ruff count:** 18 (E501 only).
- **Plan status:** SHIPPED 2026-05-11 at `a0c7223`.
- **Sub-bundle A status:** SHIPPED 2026-05-12 at `6c8f3a9`.
- **Sub-bundle B status:** SHIPPED 2026-05-12 at `e96834a`.
- **Sub-bundle C status:** SHIPPED 2026-05-12 at `e5d5892`.
- **Sub-bundle D status:** SHIPPED 2026-05-12 at `4894688`; ZERO ACCEPT-WITH-RATIONALE; 5-surface operator-witnessed gate ALL PASS.
- **Expected post-dispatch test count:** ~2767-2787 (+10-30; T-E.0..T-E.3).
- **Expected post-dispatch ruff count:** 18 (no change).
- **Expected schema version post-Bundle-E:** 17 (UNCHANGED; Bundle E is consumer-side only).
- **Phase 10 dispatch dependency:** Bundle E's combined E2E + Phase 10 hand-off note must merge to main before Phase 10 writing-plans dispatches. **Bundle E ship CLOSES Phase 9.**
- **Phase 9 arc remaining:** A ✓ → B ✓ → C ✓ → D ✓ → E (this dispatch — the closer). Then Phase 10 writing-plans.
