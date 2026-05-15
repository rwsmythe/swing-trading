# Schwab API Sub-bundle D — executing-plans return report (CLOSES the Schwab arc)

**Status: READY FOR INTEGRATION** — adversarial Codex chain converged at Round 3 to NO_NEW_CRITICAL_MAJOR. **Sub-bundle D CLOSES the 4-bundle Schwab API integration arc (Phase 11).** Operator-witnessed verification surfaces S2-S4 + S7-S8 PENDING orchestrator-driven gate; S1+S5+S6+S9 inline PASS.

**Sub-bundle scope:** `swing schwab status` full per-environment surface; `docs/cycle-checklist.md` §I.1-§I.4 updates; E2E happy-path integration test (service-composition); `CLAUDE.md` 12 new Gotchas entries (6 brief §3 + 6 plan §J supplementary); briefing.md "Schwab integration: degraded" banner; migration 0018 atomicity verification + `swing db-migrate` manual-backup warning; review_form.html.j2 polish; Phase 11 hand-off SHIPPED entry in phase3e-todo.

**Format precedent:** `docs/schwab-bundle-{A,B,C}-return-report.md`.

---

## §1 Final HEAD + commit breakdown

- **Branch:** `schwab-bundle-D-arc-closer`
- **Worktree:** `.worktrees/schwab-bundle-D-arc-closer/`
- **BASELINE_SHA:** `23161a0` (main HEAD pre-dispatch)
- **Final HEAD (this report becomes the 16th commit):** `9028ab6` pre-report; this report adds 1 more
- **Total commits since BASELINE_SHA:** **15 pre-report + 1 (this report) = 16 commits**

**Commit chain (chronological):**

```
9ff7967 feat(schwab): swing schwab status full per-environment surface              ← T-D.1
3f462c8 docs(schwab): cycle-checklist updates per §I                                ← T-D.2
6aa8f44 test(schwab): E2E happy-path integration test                               ← T-D.3
0cf2ade docs(schwab): CLAUDE.md gotchas per §J                                      ← T-D.4
37084bf fix(schwab-bundle-D): spec-review §J.5 — reword cassette runbook V2-PLANNED ← T-D.4 fix
4b6153e feat(schwab): briefing.md degraded banner when last call failed             ← T-D.5
7339957 test(schwab): verify migration 0018 BEGIN/COMMIT + manual-backup warning    ← T-D.7
1f30cb3 feat(web): replace stale "Phase 7 auto-derive" parenthetical                ← T-D.elective.1
edf0e43 fix(schwab-bundle-D): pre-Codex review — align cycle-checklist TTL 7d       ← final-review fix
a0d618d fix(schwab-bundle-D): Codex R1 Major #1+#2 — PROVISIONAL + tokens parse     ← R1 fix
0327845 fix(schwab-bundle-D): Codex R1 Major #3 — setup message hand-edit guidance  ← R1 fix
9341fd9 fix(schwab-bundle-D): Codex R1 Major #4 — E2E docstring ACCEPT-WITH-RAT     ← R1 fix
2703341 fix(schwab-bundle-D): Codex R1 Minor #1 — narrow cycle-checklist banner    ← R1 fix
cae6e7f fix(schwab-bundle-D): Codex R2 M#1+#2 + Minor #1+#2 — token_dict bypass    ← R2 fix (bundled)
9028ab6 docs(schwab-api): Phase 11 SHIPPED entry — Sub-bundle D arc-closer agg     ← T-D.6
```

**Breakdown by class:**
- **7 task-impl commits** (T-D.1 through T-D.elective.1; one per task)
- **2 pre-Codex review fixes** (§J.5 cassette reword via spec-review; cycle-checklist TTL via final-review)
- **5 Codex-fix commits** (4 R1 + 1 R2-bundled)
- **1 T-D.6 SHIPPED entry** (phase3e-todo arc-closer aggregate)
- **0 return-report commits** (this doc is the 16th when committed)

NO `--no-verify`; NO `--amend`; NO co-author footer used.

---

## §2 Codex round chain

**3 rounds total → NO_NEW_CRITICAL_MAJOR convergent tapering (FASTEST of the 4-bundle Schwab arc):**

| Round | Critical | Major | Minor | Verdict |
|---|---:|---:|---:|---|
| R1 | 0 | 4 | 2 | ISSUES_FOUND |
| R2 | 0 | 2 | 2 | ISSUES_FOUND |
| **R3** | **0** | **0** | **1** | **NO_NEW_CRITICAL_MAJOR** |

**Monotonic Major decrease:** 4 → 2 → 0 (cleanest tapering shape in the arc; matches Phase 9 Sub-bundle E + Phase 10 Sub-bundle B/C/E + Phase 9 Sub-bundle D precedents for 2-3 round convergence on polish-scope bundles).

**ZERO Critical findings entire chain.**

**ACCEPT-WITH-RATIONALE positions banked: 1**
- **R1 M#4:** E2E happy-path test scope — service-composition-driven not CLI-driven. Test calls `_step_schwab_snapshot` + `_step_schwab_orders` + marketdata wrappers directly rather than through CliRunner. Rationale: per-CLI surfaces are already covered by existing tests (`tests/cli/test_schwab_status_d_full_surface.py` +13 tests T-D.1; `tests/integrations/test_cli_schwab_fetch_verify_marketdata.py`; `tests/integrations/test_schwab_setup_cli.py`); adding CliRunner-level E2E would duplicate per-CLI coverage without adding new defect-detection capability. The service-composition test verifies the chain (snapshot → orders → reconciliation → market-data → briefing render) in one connection — which the per-CLI tests don't do.

**All other Critical+Major findings resolved with code-content fixes + discriminating regression tests** (3 R1 + 2 R2 = 5 Major fully resolved across 3 rounds).

**Minor findings: 5 total** (2 R1 + 2 R2 + 1 R3); 4 resolved in-tree; **1 R3 banked as advisory** (test docstring still says `is_degraded` after three-state refactor; cosmetic).

---

## §3 Test count + ruff delta + schema delta

**Test count delta:** **+30 fast tests cumulative** (baseline pre-dispatch 3717 → final 3747; brief projected +19; overshoot matches A/B/C precedent for defensive parametrize + R1+R2 fix coverage).

- T-D.1: +13 (10 logical + 3 parametrize-expanded boundary cases)
- T-D.2: 0 (documentation)
- T-D.3: +1 (single comprehensive E2E test)
- T-D.4: 0 (documentation)
- T-D.5: +6 (banner presence/absence + multiple-run survival + endpoint name + token-byte sentinel + zero-rows guard)
- T-D.7: +2 (atomicity regex + db-migrate warning idempotent round-trip)
- T-D.elective.1: +2 (stale text absent + new text present)
- Codex R1 fixes: +7 (3 status signal tests + 1 PROVISIONAL test + 2 exact-boundary parametrize + 1 setup message + 1 banner-absent PROVISIONAL state)
- Codex R2 fixes: +3 (token_dictionary not-dict + refresh_token bytes missing + refresh_token_issued unparseable)

**Final fast-suite state:** **3747 passed, 5 skipped, 3 failed** (~62s wall-clock under `-n auto`).

**Pre-existing failures (3 confirmed pre-existing on `23161a0`; NOT regressions):**
1. `tests/integration/test_phase8_pipeline_walkthrough.py::test_phase8_pipeline_emits_snapshots_for_open_trades_only` — "archive returned None"; banked at CLAUDE.md Bundle 3 entry.
2. `tests/integration/test_phase8_pipeline_walkthrough.py::test_phase8_pipeline_second_same_day_run_upserts` — same family.
3. `tests/integration/test_phase8_pipeline_walkthrough.py::test_phase8_pipeline_run_id_is_pipeline_runs_id_not_evaluation_runs_id` — same family.

(Sub-bundle C dispatch brief had noted a 4th xdist-flaky setup-CLI failure; under D dispatch's xdist scheduling it passed consistently — variance per the gotcha noted in CLAUDE.md.)

**Ruff baseline:** 18 E501 errors **unchanged** (matches CLAUDE.md `Ruff baseline 18` invariant). No new E501; no new violations of any other class introduced.

**Schema version:** **v18 unchanged** (Sub-bundle D is consumer-side only per dispatch brief §0.7).

---

## §4 Operator-witnessed verification surfaces

Per dispatch brief §4 surface table. **Total: 9 surfaces** (4 inline + 5 operator-driven). **Operator-driven gate budget: 5 — slightly above 6-surface budget; brief notes orchestrator may bundle S2+S3 or S4+S7 for efficiency.**

| # | Surface | Type | Status |
|---|---|---|---|
| **S1** | pytest fast-suite | Inline | **PASS** — 3747 passed; 3 pre-existing Phase 8 walkthrough failures unchanged; 5 skipped; ~62s under `-n auto`. |
| **S2** | `swing schwab status --environment production` | **PENDING — operator-driven** | Verify: rendering matches spec §3.5 mock; LIVE/PROVISIONAL/DEGRADED tri-state correctly classified; per-environment counts present (recent-errors 24h/7d, snapshots-30d, reconciliation_runs schwab_api 30d, unresolved-material-discrepancies); recent-calls summary present; degraded indicator correct; days-remaining alert (`[WARN]` ≤24hr / `[!! ERROR !!]` ≤2hr visible if applicable); ZERO Schwab token bytes; account_hash masking via `mask_sensitive_value`. |
| **S3** | `swing schwab status --environment sandbox` | **PENDING — operator-driven** | Verify: handles "tokens-present-but-stale" case gracefully (per Sub-bundle C SHIPPED entry observation — sandbox tokens DB exists but expired); status surface displays appropriate DEGRADED state indicator with reason cite (expired refresh-token OR stale mtime > 7d) without invoking refresh. Tests T9 + 3 NEW R1+R2 tests cover. |
| **S4** | `swing pipeline run` → briefing.md banner | **PENDING — operator-driven (filesystem)** | Verify: most recent `exports/<action_session_date>/briefing.md` contains "Schwab integration: degraded" banner IF most recent `schwab_api_calls.status != 'success'` (operator can plant a degraded state by running `swing schwab fetch --verify-marketdata` against expired sandbox tokens; banner should appear in next pipeline-run-emitted briefing.md). Banner text matches spec §3.4.4 + §7.2 wording (WITH colon); NO token bytes; banner generic (does NOT include `error_message` content). T-D.3 cross-bundle pin asserts `"Schwab integration: degraded"` substring absence on happy path. |
| **S5** | E2E happy-path integration test | Inline | **PASS** — `pytest tests/integration/test_schwab_full_happy_path.py -v` GREEN — service-composition E2E (per Codex R1 M#4 ACCEPT-WITH-RATIONALE scope clarification) exercises OAuth bootstrap → snapshot → orders → reconciliation → market-data cache fill → briefing render in one MagicMock-driven transaction. Runtime 0.73s. |
| **S6** | Migration 0018 atomicity | Inline | **PASS** — `pytest tests/data/test_migration_0018_atomicity.py -v` + `pytest tests/cli/test_db_migrate_warning.py -v` GREEN. T-D.7 verifies migration 0018 SQL contains `^BEGIN;` + `^COMMIT;` markers (line-anchored multiline regex) AND `swing db-migrate` CLI warning text contains the manual-backup recommendation substring under `pre_version < 18` predicate (idempotent on second invocation). |
| **S7** | `cycle-checklist.md` review | **PENDING — operator review** | Operator reads `docs/cycle-checklist.md` post-merge; verifies one-time setup section + daily/weekly/recovery additions land cleanly + render in Markdown preview. Refresh-token TTL aligned to 7d uniform per operator-paired-gate observation (pre-Codex review fix `edf0e43`). Recovery sequence preserves `logout → setup` discipline. Pure documentation surface; NO test coverage. |
| **S8** | Review-form polish (T-D.elective.1) | **PENDING — operator browser** | Visit `/reviews/{id}/complete` or `/trades/{tid}/review` form; verify counterfactual fieldset helper text NO LONGER says "(Phase 7 will auto-derive this from Fills.)"; new phrasing "Auto-derivation from Fills is a future enhancement; manual entry V1." renders verbatim. |
| **S9** | ruff baseline | Inline | **PASS** — `ruff check swing/ --statistics` reports **18 E501 unchanged**. |

**Production state post-gate:** S2-S4 + S8 produce ZERO new audit rows + ZERO new domain rows + ZERO new cache writes (D scope is read-side only). S4's briefing.md emission overwrites the existing briefing.md for that action session — banked as expected behavior.

**Production-write classifier soft-block awareness:** D scope writes ZERO production data; soft-block should NOT trigger.

---

## §5 Per-task deviations from plan

**Total: ~13 banked deviations across T-D.1..T-D.elective.1** (mix of brief-vs-plan adaptations + Codex-cascade refactors).

### T-D.1 (4 deviations)

- **D1 (architectural; from Codex R1+R2):** Status surface uses THREE-state classifier (`"LIVE"` / `"PROVISIONAL"` / `"DEGRADED"`) NOT binary `is_degraded` boolean. PROVISIONAL state explicitly distinct from DEGRADED per R1 M#2; PROVISIONAL narrowed strictly to Signal 1 ("tokens DB missing on disk") per R2 M#2. Eight other signals classify as DEGRADED.
- **D2 (architectural; from Codex R1+R2):** Degraded predicate consults **NINE signals** (was 6 at original implementation; +3 from R1 + R2 hardening): (1) missing → (2) unparseable JSON → (3) token_dictionary not-dict → (4) refresh_token bytes missing/empty → (5) refresh_token_issued field missing → (6) refresh_token_issued unparseable → (7) refresh_token expired → (8) mtime > 7d → (9) recent call != success.
- **D3 (cosmetic):** Snapshots-30d count rendered without per-environment qualifier (the `account_equity_snapshots` table has no `environment` column V1; spec §3.5 mock didn't enforce per-env qualifier on that line). Active env shown in header line.
- **D4 (cosmetic; from R2 m#1):** Expiry boundary uses `<=` for consistency between `_compute_degraded_state` predicate and `_render_token_validity` renderer.

### T-D.2 (3 deviations)

- **D1 (CLI-surface gap caught + adapted):** Plan §I.1 step 3 prescribed `swing config set integrations.schwab.environment production` but V1 FIELD_REGISTRY (`swing/config_validation.py:43-91`) doesn't include the env field — only `web.chase_factor`, `pipeline.chart_top_n_watch`, `account.risk_equity_floor`, `integrations.schwab.account_hash`. Adapted §I.1 step 3 to recommend hand-edit `~/swing-data/user-config.toml` OR `--environment` flag per-invocation. **NEW V2 candidate banked** (#12 in T-D.6 SHIPPED entry).
- **D2 (cosmetic):** §I.1 step 2 wording "copy the 'code' query param from URL bar" adapted to "copy the FULL redirected URL" (schwabdev paste-back actually expects the full URL).
- **D3 (cosmetic):** §I.4 POSIX `rm` substituted with PowerShell `Remove-Item` to match cycle-checklist convention; relegated to last-resort fallback after pre-Codex review fix.

### T-D.3 (2 deviations)

- **D1 (scope; ACCEPT-WITH-RATIONALE per Codex R1 M#4):** E2E test is service-composition-driven (calls `_step_schwab_snapshot` + `_step_schwab_orders` + marketdata wrappers DIRECTLY), NOT CliRunner-driven. Rationale: per-CLI surfaces already covered by existing tests; adding CliRunner-level E2E would duplicate without adding new defect-detection capability.
- **D2 (cosmetic):** §4 used direct `get_quotes_batch` + `get_price_history` rather than `swing schwab fetch --verify-marketdata` CLI; same audit-row contract verified.

### T-D.4 (2 deviations)

- **D1 (scope expansion):** Added **12 CLAUDE.md gotcha entries** (brief §3 enumerated 6; implementer added 6 plan-§J supplementals per brief §3 closing paragraph "cumulative coverage; no original-plan gotcha is dropped" directive). Spec compliance reviewer approved 11; flagged §J.5 cassette runbook as premature (Schwab cassettes don't exist).
- **D2 (cosmetic; from pre-Codex spec-review fix):** §J.5 cassette runbook entry reworded as V2-PLANNED at `37084bf` to clarify V1 ships mock-based tests only.

### T-D.5 (2 deviations)

- **D1 (cross-bundle; cosmetic):** Banner text uses WITH-COLON variant `"Schwab integration: degraded"` per spec §3.4.4 + §7.2; T-D.3 cross-bundle pin substring updated at `4b6153e` to match (without-colon variant from initial T-D.3 commit would have made T-D.5 banner-on-happy-path false-negative).
- **D2 (architectural):** New `is_schwab_degraded(conn) -> tuple[bool, str | None]` helper at `swing/data/repos/schwab_api_calls.py` consumed by `_step_export` via new `schwab_degraded_endpoint` field on `BriefingInputs` + `BriefingViewModel`. Banner rendered conditionally in `swing/rendering/briefing_md.py`.

### T-D.7 (1 deviation)

- **D1 (scope expansion):** Brief described "verification-only" but the manual-backup warning text DIDN'T EXIST in V1 `db-migrate` CLI. Implementer ADDED the warning emission (+12 lines in `swing/cli.py`) so the test could pass. Discriminating idempotent round-trip test pins the warning predicate `pre_version < 18`.

### T-D.elective.1 (1 deviation)

- **D1 (cosmetic):** Implementer brief specified `/reviews/{id}/complete` as test URL; that endpoint renders `cadence_complete.html.j2`, NOT `review_form.html.j2`. Tests target the correct URL (`/trades/{tid}/review` via existing T-B.7 test pattern) matching the actually-rendering route.

### Pre-Codex review fix (final-review)

- **D1 (cosmetic; matches CLAUDE.md gotcha #4 + cli_schwab.py:47):** cycle-checklist.md weekly-section refresh-token TTL adapted from plan §I.3 "90-day production / 7-day sandbox" wording to uniform 7d per operator-paired-gate observation 2026-05-14. Both sandbox + production tier expire at 7d per actual schwabdev V1 behavior.

---

## §6 Codex Major findings ACCEPTED with rationale

**1 ACCEPT-WITH-RATIONALE position across the chain (vs Sub-bundle A: 1; Sub-bundle B: 1; Sub-bundle C: 2; Phase 10 arc: 0 — matches arc precedent).**

### §6.1 R1 M#4 — E2E happy-path test scope is service-composition, not CLI-driven

**Commit:** `9341fd9`

**Codex finding:** The E2E test is not actually an end-to-end path through setup, CLI fetches, pipeline wiring, or cache writing. It substitutes OAuth setup with schema bootstrap + injected `MagicMock` clients, calls `_step_schwab_snapshot` and `_step_schwab_orders` directly, and calls market-data wrappers directly rather than the CLI or pipeline ladder. This is useful integration coverage, but it does not satisfy the dispatch's "OAuth setup → snapshot → orders → reconciliation → market-data cache fill → briefing render" CLI-driven E2E claim.

**Rationale for ACCEPT:**
- Per-CLI surfaces are ALREADY covered by existing tests:
  - `swing schwab status` CLI covered by `tests/cli/test_schwab_status_d_full_surface.py` (+13 tests T-D.1)
  - `swing schwab fetch --verify-marketdata` covered by `tests/integrations/test_cli_schwab_fetch_verify_marketdata.py` (existing)
  - `swing schwab setup` covered by existing `tests/integrations/test_schwab_setup_cli.py`
  - Pipeline `_step_schwab_*` invocation under lease covered by existing pipeline tests at `tests/integrations/test_schwab_pipeline_*.py`
- Adding CLI-level E2E coverage would DUPLICATE existing per-CLI tests without adding new defect-detection capability.
- The existing E2E test verifies the SERVICE-COMPOSITION CHAIN (snapshot → orders → reconciliation → market-data → briefing render) in one connection — which the per-CLI tests don't do (each tests one CLI surface in isolation).
- Test file's top-of-file docstring updated to clarify what it actually exercises ("service-composition end-to-end" not "CLI-driven end-to-end") + cross-reference to per-CLI tests.

**Documentation-only commit; no production behavior change.**

---

## §7 Watch items for orchestrator (cross-bundle pins; V2 candidates; Phase 11 closure)

### §7.1 Cross-bundle pins

**ZERO cross-bundle pins remaining post-Sub-bundle-D-ship.** Both Sub-bundle C un-skips (T-C.5 `test_b6_10_fetch_verify_marketdata_NOT_protected` + T-C.7 Market Data API sentinel-coverage tests) un-skipped at C-ship + GREEN. Sub-bundle D added NO new cross-bundle pins.

T-D.3 → T-D.5 banner-substring is an intra-bundle pin (NOT cross-bundle): T-D.5 commit (`4b6153e`) updates the T-D.3 pin atomically.

### §7.2 V2 candidates banked (13 total — Phase 11 candidate triage UNBLOCKED)

Per dispatch brief §9 + return-report bank from D + accumulated from A+B+C:

**From spec §10 Q-deferrals:**
1. **Q3** — Multi-account support (V1 single-primary; spec §10 Q3).
2. **Q4** — WebSocket streaming endpoints (V2 candidate).
3. **Q5** — Web UI for Schwab integration (status surface only V1; web routes V2).
4. **Q6** — Schwab inception-CSV ingestion (separate dispatch per phase3e-todo 2026-05-12 entry).
5. **Q7** — TOS reconciliation deprecation (Schwab API replaces; V2 deprecation milestone).
6. **Q2** — Token encryption-at-rest (schwabdev's `encryption=<key>` constructor parameter; V1 ships plaintext SQLite).

**From Sub-bundle C return report §7.2:**
7. `_step_charts` ladder wiring (R1 M#5 from C).
8. `read_or_fetch_archive` Shape A read-path extension.
9. `empty_flag is True` pattern review across other JSON-boolean Schwab response flags.
10. `_yfinance_window_to_shape_a_df` heuristic conversion → explicit fallback contract.
11. Legacy parquet cleanup pass (after all consumers refactor to Shape A).
12. REPLACE-mode `write_window` for explicit archive reset.
13. Per-row `recorded_at` column as freshness signal alternative to filesystem mtime (R4 M#1 family).

**From Sub-bundle D return report (NEW; banked at T-D.6):**
14. **`swing config set integrations.schwab.environment` CLI surface** — currently V1 FIELD_REGISTRY doesn't include the env field; operators must hand-edit `user-config.toml` (caught by T-D.2 + adapted CLI message at R1 M#3; cycle-checklist + setup CLI message now both point at hand-edit path).
15. **Briefing always-present "Schwab integration" section** — V1 ships banner-only; spec §7.2 + cycle-checklist initially claimed always-present section with equity snapshot + reconciliation discrepancy count; cycle-checklist narrowed to banner-only at R1 m#1. V2 would add the full Schwab section to briefing.md per spec intent.
16. **`swing schwab setup` self-healing** — detect-and-rename stale tokens DB before invoking schwabdev (CLAUDE.md gotcha #3 from D T-D.4; current V1 recovery path is `logout → setup`).
17. **Pipeline `client_id`/`client_secret` env-var path** (T-C.6 D1 from C; pipeline can't prompt; V2 enhancement reads from env vars).
18. **Future Schwab live-test cassette infrastructure + cassette staleness runbook** (D T-D.4 §J.5 V2-PLANNED).

### §7.3 Plan-text amendments pending V2.1 §VII.F routing

Aggregate across the arc (~36+ deviations entering D; D added ~6 NEW):

**Sub-bundle D NEW V2.1 §VII.F amendment candidates:**
1. Refresh-token TTL claim — plan §I.3 "90d/7d split" → 7d uniform per operator-paired-gate observation.
2. `swing schwab setup` success message wording (R1 M#3) — plan §I.1 referenced non-existent `swing config set integrations.schwab.environment` CLI surface.
3. E2E test scope wording (R1 M#4) — plan §Tasks-D T-D.3 said "cassette-driven"; implementation is MagicMock-driven service-composition (no Schwab cassettes exist V1).
4. PROVISIONAL state narrowed strictly to "tokens DB missing on disk" per Codex R2 Major #2 (PROVISIONAL ≠ "any anomaly"; PROVISIONAL = "never configured yet").
5. Briefing always-present "Schwab integration" section was specified but ships banner-only V1 (spec §7.2 + cycle-checklist).
6. `swing db-migrate` manual-backup warning — T-D.7 brief said "verification-only" but implementer ADDED the warning emission (warning text didn't exist in V1).

### §7.4 R3 Minor advisory (not addressed inline)

1. **Test file header docstring still uses `is_degraded` language** — `tests/cli/test_schwab_status_d_full_surface.py:9` says "Multi-signal `is_degraded` predicate" even though the predicate is now a 3-state health classifier. Cosmetic; not behaviorally risky but future maintainers could misread the surface as boolean again. Sub-bundle D code-review absorb point OR opportunistic touch-up in a future bundle.

---

## §8 Worktree teardown status

**Expected ACL-locked husk per Phase 6/7/8/9/10/Sub-A/Sub-B/Sub-C precedent.** Branch `schwab-bundle-D-arc-closer` will be DELETED post-integration-merge by the orchestrator. The on-disk worktree directory `.worktrees/schwab-bundle-D-arc-closer/` becomes a still-registered husk until cleared by `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` (post-Phase-10 infrastructure bundle SHIPPED 2026-05-13 at `27ce96f`).

**D will be the 4th in operator's cleanup-script queue** (after A + B + C from prior bundles per Sub-bundle C SHIPPED entry).

**Marker file** `c:\Users\rwsmy\swing-trading\.copowers-subagent-active` will be REMOVED by orchestrator (or by this implementer pre-return-report commit per dispatch brief §1.2).

---

## §9 Phase 11 closure summary — 4-bundle Schwab arc aggregate (CLOSES THE ARC)

### §9.1 Per-bundle aggregate

| Sub-bundle | Merge SHA | Codex rounds | Commits | ACCEPT-WITH-RATIONALE |
|---|---|---:|---:|---:|
| **A** (foundational; schwabdev wrap + auth + migration 0018 + audit infrastructure) | `5b6e5ba` | 4 | 19 | 1 |
| **B** (Trader API + snapshot + orders + reconciliation) | `df29232` | 5 + 1 orchestrator-inline gate-fix at `34be84e` | ~24 (per CLAUDE.md) | 1 (lease status fields V2-deferred) |
| **C** (Market Data API + Shape A ladder + PriceCache/OhlcvCache + sandbox short-circuit + `--verify-marketdata` CLI) | `fd457de` | 5 | 26 | 2 (`_step_charts` ladder V2; file-level mtime V1 best-effort) |
| **D** (arc-closer; status + cycle-checklist + CLAUDE.md + E2E + banner + migration verify + review-form polish) | (pending operator-witnessed gate + integration merge) | 3 | 15 + return report | 1 (E2E test scope) |

### §9.2 Arc totals

- **17 Codex rounds total** across the 4 bundles (4 + 5 + 5 + 3).
- **~84 commits across the arc** (19 + ~24 + 26 + 15).
- **ZERO Critical findings entire arc** — first project-history Schwab integration of this complexity to ship with zero Critical issues.
- **5 ACCEPT-WITH-RATIONALE banked across arc** (1 A + 1 B + 2 C + 1 D).
- **+30 fast tests from D + +120 from C + +80 from B + +126 from A ≈ +356 cumulative** Schwab arc additions (3361 pre-A → 3717 post-C → 3747 post-D).
- **Schema version:** v17 → v18 in single atomic migration at A T-A.7; consumer-side only through B+C+D.

### §9.3 CLAUDE.md gotcha promotions (arc-wide)

- **Sub-bundle D promoted 12 new entries** (the 6 brief §3 entries + 6 plan §J supplementary). Sub-bundles A+B+C contributed source-material for the 12 entries (operator-paired gate findings; Codex chain findings).
- Cumulative CLAUDE.md `## Gotchas` count: ~48 → 60 entries post-D-ship.

### §9.4 Operator-paired live verification across the arc

- **Sub-bundle A:** Task 0.b phase-2 live OAuth setup paste-back; tokens DB persisted; account_hash captured.
- **Sub-bundle B:** Snapshot + orders production pipeline run; reconciliation_runs row written; `briefing.md` LIVE-badge equity from Schwab.
- **Sub-bundle C:** `--verify-marketdata` against live Schwab Market Data API; first `marketdata.quotes` + `marketdata.pricehistory` calls in production; 7-day refresh-token clock refreshed via `logout → setup` recovery sequence.
- **Sub-bundle D:** Operator gate PENDING (5 operator-driven surfaces — S2+S3+S4+S7+S8); no new schwabdev call surfaces in D (consumes A+B+C surfaces read-only).

### §9.5 Phase 11 CLOSED — Phase 12+ triage UNBLOCKED

Sub-bundle D ships **ALL 4 sub-bundles complete**. Phase 11 (Schwab API integration) labeled SHIPPED in `docs/phase3e-todo.md` (T-D.6 entry at `9028ab6`).

**Phase 12+ candidate triage UNBLOCKED.** Notable post-Phase-11 V2 candidates for orchestrator-paced dispatching:
- 6 spec §10 Q-deferrals (Q2-Q7).
- 7 Sub-bundle C return-report banked V2 items.
- 6 NEW Sub-bundle D V2 candidates banked at T-D.6.

3 post-Phase-11 standalone dispatches already enumerated:
- Schwab inception-CSV ingestion (Q6; separate dispatch per phase3e-todo 2026-05-12 entry).
- `swing config set integrations.schwab.environment` FIELD_REGISTRY extension (D T-D.2 D1).
- Briefing always-present "Schwab integration" section (D R1 m#1 spec-vs-shipped-state gap).

---

## §10 Composition-surface verification

Per dispatch brief §4.1 / §5 + Phase 9-10 forward-binding lesson on `^def` grep enumeration.

**`grep -rn "^def" swing/cli_schwab.py`** (T-D.1 extended):
- `_compute_degraded_state` (NEW; 9-signal predicate; lines ~579-680)
- `_render_refresh_token_with_severity` (NEW; WARN/ERROR escalation; lines ~682-720)
- `_count_recent_errors` (NEW; lines ~520+)
- `_count_snapshots_30d` (NEW; lines ~540+)
- `_count_recon_runs_30d` (NEW; lines ~558+)
- `_count_unresolved_material_discrepancies` (NEW; lines ~569+)
- `render_status` (EXTENDED; renders 3-state tri-line + per-env counts + reconciliation summary)
- Plus pre-existing T-A.6 skeleton helpers preserved.

**`grep -rn "^def" swing/data/repos/schwab_api_calls.py`** (T-D.5 extended):
- `is_schwab_degraded` (NEW; lines ~201-229; tuple[bool, str | None] with zero-rows-yet guard).
- Pre-existing repo helpers preserved.

**`grep -rn "build_briefing_view_model\|render_briefing_md" swing/`:**
- `build_briefing_view_model` invoked ONLY at `swing/pipeline/runner.py:_step_export` (single composition surface).
- `render_briefing_md` consumed ONLY by `swing/rendering/exporter.py:export_briefing` (downstream of `_step_export`).

**Single composition surface verified for T-D.5 banner emission.**

---

## §11 CLAUDE.md cumulative coverage diff

Sub-bundle D added **12 new gotcha entries** at end of `## Gotchas` section in `CLAUDE.md`:

### Brief §3 entries (6; arc-foundational findings)

1. Sub-bundle B `34be84e` defect family — schwabdev camelCase kwarg discipline.
2. Typed `SchwabApiError` audit-row close discipline (per Sub-bundle B R1 M#3).
3. `swing schwab setup` requires clean tokens DB state (Sub-bundle C gate observation).
4. 7-day Schwab refresh-token clock requires periodic re-auth.
5. schwabdev 2.5.1 `"Schwabdev"` capital-S logger prefix (Sub-bundle A T-A.10 D1).
6. schwabdev silent-failure-mode discipline — `update_tokens()` does NOT raise.

### Plan §J supplementary entries (6; reorganized post-§J.5 reword)

7. Schwab tokens DB plaintext OAuth state at rest V1.
8. Schwab CLI vs pipeline concurrency exclusion (`SchwabPipelineActiveError`).
9. Schwab production-only domain writes gate.
10. schwabdev LogRecordFactory three-layer redaction.
11. Schwab cassette runbook is V2 PLANNED — V1 ships mock-based tests only (reworded from §J.5).
12. Schwab API source-artifact reference URI shape locked.

**No duplicates with pre-existing CLAUDE.md content** (verified by spec compliance reviewer at T-D.4).

---

## §12 `reference/schwab-api/` + `reference/schwabdev/` distilled refs consumed during D

**Inherited from A+B+C; no new ref consumption at D.**

Sub-bundle D consumed the cumulative ref state for:
- `reference/schwabdev/troubleshooting.md` — `unsupported_token_type` → `update_tokens(force_refresh_token=True)`; CLAUDE.md gotcha #3 recovery sequence.
- `reference/schwabdev/client.md` — 30-min access + 7-day refresh-token lifecycle (CLAUDE.md gotcha #4).
- `reference/schwabdev/api-calls.md` — already comprehensively pre-checked across A+B+C; ZERO new wrapper additions in D.

No new schwabdev call surfaces in D; status surface reads filesystem + audit table only.

---

## §13 Cross-bundle pin status

**ZERO cross-bundle pins remaining post-D-ship.**

Sub-bundle C un-skipped both prior cross-bundle pins (T-C.5 + T-C.7) at C-ship + GREEN. Sub-bundle D added NO new cross-bundle pins (single intra-bundle T-D.3↔T-D.5 banner substring update was atomic via T-D.5 commit).

---

## §14 Phase 11 hand-off readiness summary

**Sub-bundle D ships the arc.** Phase 11 (Schwab API integration) labeled SHIPPED in `docs/phase3e-todo.md` post-T-D.6 commit `9028ab6`.

**V2 candidates list complete:** 18 candidates banked across Q-deferrals + return-report-§7 + Sub-bundle D NEW (per §7.2 above).

**Phase 12+ candidates UNBLOCKED for orchestrator triage:**
- Schwab inception-CSV ingestion (Q6).
- `swing config set integrations.schwab.environment` FIELD_REGISTRY extension.
- Briefing always-present "Schwab integration" section.
- Other backlog items at `docs/phase3e-todo.md`.

**Operator-paced post-arc-close.**

---

**End of return report.** Implementer hands off to orchestrator for:
1. Operator-driven gate surfaces S2-S4 + S7-S8 (5 surfaces; production-write classifier soft-block awareness; slightly above 6-surface gate-budget; orchestrator may bundle S2+S3 or S4+S7 if operator prefers).
2. Marker file `c:\Users\rwsmy\swing-trading\.copowers-subagent-active` removal (per dispatch brief §1.2 — orchestrator removes before final integration merge OR implementer removed pre-commit if convenient).
3. Integration merge to main (no `--ff` per Sub-bundle B/C precedent → preserves Codex-fix chain visibility).
4. Phase 11 closure post-Sub-bundle-D-merge.
5. Phase 12+ candidate triage commissioning (operator-paced).

**The Schwab API integration arc CLOSES with Sub-bundle D ship.**
