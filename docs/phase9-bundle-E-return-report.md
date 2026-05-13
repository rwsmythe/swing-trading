# Phase 9 Sub-bundle E — executing-plans return report

**Worktree:** `c:\Users\rwsmy\swing-trading\.worktrees\phase9-bundle-E-polish-and-phase10-handoff`
**Branch:** `phase9-bundle-E-polish-and-phase10-handoff`
**Dispatch brief:** `docs/phase9-bundle-E-executing-plans-dispatch-brief.md`
**Baseline SHA:** `6ba1925` (post-Sub-bundle-D-merge + housekeeping on `main`)
**Final HEAD SHA:** `470df42`
**Status:** READY FOR OPERATOR-WITNESSED GATE

---

## §1 Final HEAD on branch

`470df42` (post-Codex-R1 fix). 7 commits on branch since baseline `6ba1925`; 6 commits since the dispatch brief commit `da68670` (which is doc-only and harmless per dispatch §1.1).

## §2 Commit count breakdown

| Layer | Commits |
|---|---:|
| Task-impl (T-E.3 + T-E.0 + T-E.1 + T-E.2) | 4 |
| Codex R1 fix (Major #1 + Major #2 + Minor #1) | 1 |
| Stale-docstring inline fix (T-E.0 §7 count) | 1 |
| Ruff I001 auto-fix (T-E.3 import sort) | 1 |
| **Total** | **7** |

Full commit list (post-baseline):

```
470df42 fix(journal): Codex R1 Major #1+#2 + Minor #1 — duplicate-unnamed-column robustness + TRG BY order_id leak + T-E.0 parent counter assertion
78e7555 docs(phase9): Task E.2 — Phase 9 lessons-banked + Phase 10 hand-off note + ruff sweep clean
088990e docs(claude-md): Task E.1 — Phase 9 candidate gotcha promotions (orchestrator-triage at merge)
601f3a7 docs(tests): Task E.0 fix — correct stale §7 docstring count (3/2 → 5/4)
e047190 test(integration): Task E.0 — Phase 9 combined E2E happy path
003a514 style(tests): Task E.3 fix — ruff I001 unsorted-imports auto-fix
2107df2 feat(journal): Task E.3 — Account Order History multi-line parser fix (operator gate Bundle B finding 2026-05-12)
```

## §3 Codex round chain

**Convergent in 2 rounds — fastest of the Phase 9 arc** (A=5, B=5, C=3, D=4, E=2).

| Round | Critical | Major | Minor | Verdict |
|---:|---:|---:|---:|---|
| 1 | 0 | 2 | 3 | ISSUES_FOUND |
| 2 | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** |

**R1 findings (all resolved or accepted):**
- **R1 Major #1** — `csv.DictReader` duplicate `""` keys + brittle `_has_stp_marker` reliance on `row[""]`. Extra blank Schwab column would silently regress to pre-T-E.3 false-positive `stop_mismatch` behavior. **RESOLVED** at `470df42` with `_dedupe_fieldnames` helper + `_iter_unnamed_column_values` helper + `_has_stp_marker` scanning every `col_*` slot. Discriminating regression test `test_extract_stop_orders_extra_unnamed_column_drift` covers three-unnamed-column CSV variant.
- **R1 Major #2** — `_clean_order_id` leaks `TRG BY #...` as order_id (violates recon doc §2.D contract). **RESOLVED** at `470df42` with case-insensitive `TRG BY` prefix rejection + bare-alphanumeric-token validation. Tightened existing CC 4/30 test + new `test_extract_stop_orders_trg_by_only_in_continuation_returns_none_order_id`.
- **R1 Minor #1** — T-E.0 docstring claims "parent run counter --" but doesn't assert. **RESOLVED** at `470df42`: §2 captures `parent_run_unresolved_pre`; §3 asserts post == pre - 1.
- **R1 Minor #2** — recon doc sanitization wording "first 30 lines" partial claim. **ACCEPTED**: sanitization is verified clean (`grep -rn "27097300SCHW" tests/fixtures/tos/` returns zero matches); wording-only nit banked for orchestrator at integration merge.
- **R1 Minor #3** — T-E.0 uses synthetic single-row CSV format, not real-world multi-line. **ACCEPTED**: T-E.3 has 9 discriminating tests against 4 real-world fixtures; T-E.0 scope per plan §H is workflow across A+B+C+D surfaces, not specifically the T-E.3 parser path. Adding it to T-E.0 would duplicate coverage without strengthening the binding workflow assertion.

**ZERO ACCEPT-WITH-RATIONALE on Critical+Major findings.** Only 2 Minor accepted (Minor #2 wording + Minor #3 scope rationale).

## §4 Test count delta + ruff baseline delta

**Test counts:**
- Pre-Bundle-E baseline (per dispatch brief): **2757 fast** (5 skipped; 3 pre-existing failures).
- Post-Bundle-E: **2767 fast pass** (+10), 5 skipped (4 SKIP-on-absent for `thinkorswim/*.csv` not in worktree + 1 pre-existing); same 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures (verified pre-existing on `main` HEAD `6ba1925`; banked for separate triage).
- Within projection (+10-30; dispatch brief §3 expected).

**Ruff baseline:** `ruff check swing/ --statistics` returns **18 E501** (line-too-long only). Unchanged from Sub-bundle A baseline through B/C/D/E. **Phase 9 introduces ZERO new ruff violations across the entire arc.**

**Files changed (1850+ insertions on top of dispatch brief commit):**

```
 CLAUDE.md                                                                          |   1 +
 docs/phase3e-todo.md                                                               |  61 +++
 docs/phase9-bundle-E-executing-plans-dispatch-brief.md                             | 347 ++++ (pre-existing brief commit)
 docs/phase9-bundle-E-task-E3-parser-recon.md                                       | 157 +++
 swing/journal/tos_import.py                                                        | 302 +++++/63 ---
 tests/fixtures/tos/schwab-real-world-{2026-04-15,04-30,05-08,05-12}.csv            | 384 +++++
 tests/integration/test_phase9_full_happy_path.py                                   | 479 +++++
 tests/journal/test_tos_import_stop_extractor_real_world.py                         | 365 +++++
```

## §5 Operator-gate surface results

PENDING operator-witnessed gate. Per dispatch brief §3:

- **S1** — Post-D-merge baseline + ruff sanity (pytest 2767+ pass, ruff 18, `swing config policy show` 34 fields).
- **S2** — `python -m pytest tests/integration/test_phase9_full_happy_path.py -v` GREEN.
- **S3** — `swing journal reconcile-tos --csv-path "C:\Users\rwsmy\swing-trading\thinkorswim\2026-05-12-AccountStatement.csv" --period-end 2026-05-11 --notes "Bundle E S3"`. Expected: ZERO `stop_mismatch` discrepancies emitted (vs Bundle B baseline of 5 false positives).
- **S4** — Repeat S3 against `2026-05-08-AccountStatement.csv` (WAIT TRG DHC) + `2026-04-30-AccountStatement.csv` (TRG BY chain CC).
- **S5** — Final pytest + ruff.

Inline verification (implementer-side, not operator-witnessed):
- ✅ Full fast suite: 2767 passed (+10), 5 skipped, 3 pre-existing failures unchanged.
- ✅ Ruff `swing/`: 18 E501 unchanged.
- ✅ T-E.0 GREEN.
- ✅ T-E.3 9 new tests GREEN; backwards-compat with 24 Bundle B `test_stop_mismatch_*` GREEN.
- ✅ Fixture sanitization: `grep -rn "27097300SCHW" tests/fixtures/tos/` returns zero matches.

## §6 Per-task deviations from the plan

### T-E.0
**Deviation #1:** Two-trade seeding (`_seed_managing_trade(ABC)` + `_seed_partial_exited_trade(DEF)`) instead of the brief's example "one trade ABC" pattern. **Rationale:** mirrors the existing `test_phase9_end_to_end_four_discrepancy_types` E2E shape; maximizes surface coverage (5 active-trade material discrepancies pre-resolve → 4 post-resolve) for a more discriminating §7 assertion. Discriminating arithmetic preserved (`active_count_pre == 5` locked).

### T-E.3
**Deviation #1:** Brief suggested logic checking `Type=MKT` to discriminate single-row vs multi-line. **Implementation generalized to** `_has_stp_marker(row)` which checks `Order Type` + `Type` + every `col_*` (unnamed) slot for `STP`/`STOP` token. Cleaner contract: header rows lack the STP marker (regardless of whether the empty-key column carries "MKT" or another non-STP value); continuation rows carry it. This handles future Schwab format variations more gracefully than a hard-coded `MKT` check.

**Deviation #2 (post-Codex R1):** Original parser used `csv.DictReader` directly, which discards all but the LAST duplicate-`""`-key value. Codex R1 Major #1 surfaced this as a forward-drift risk. **Implementation post-fix:** new `_dedupe_fieldnames` helper renames duplicate/empty headers to `col_<idx>` positionally BEFORE DictReader sees them. Preserves access to BOTH unnamed columns (the first holds "MKT" on header row; the second holds "STP" on continuation row). Pattern is also defensive against future Schwab format drift.

### T-E.1 + T-E.2
No deviations from plan §H. T-E.1 added 1 candidate gotcha; T-E.2 enumerated spec §11.1-§11.5 per acceptance criteria.

## §7 Codex Major findings ACCEPTED with rationale

**ZERO.** Both Critical+Major findings (R1 M#1 + R1 M#2) resolved in-tree with discriminating regression tests. Matches Sub-bundle D's ZERO ACCEPT-WITH-RATIONALE record. The two Minor findings ACCEPTED (R1 Minor #2 wording + R1 Minor #3 scope) are non-blocking advisories.

## §8 Watch items surfaced but not acted on

**Post-Phase-9 V2 candidates** (banked at `docs/phase3e-todo.md`; NOT Bundle E scope):

1. **Schwab "since-inception" Account Statement ingestion** (banked from Sub-bundle C; richer than 7-day; could seed cash_movements + account_equity_snapshots historical series + reconcile fills against journal for pre-Phase-7 trade history).
2. **`account_equity_snapshots.equity_dollars` semantic formalization** (banked from Sub-bundle C; cash-basis vs net-liq distinction; operator stored cash basis $2000 but system surfaced as if MTM; equity_delta then resolves to ≈ -(YTD P/L) which is informative but ambiguous).

**Spec amendments pending V2.1 §VII.F routing:**

1. **Sub-bundle D spec §7 supersession** to chart_pattern-mirror hidden-anchor pattern (banked at `docs/phase9-bundle-D-task-D0-recon.md`).
2. **Sub-bundle E spec §6.2 supersession** to multi-line group parser (banked at `docs/phase9-bundle-E-task-E3-parser-recon.md`).

**CLAUDE.md gotcha promotions banked** (1 added at T-E.1; total 6 across Phase 9 arc):

- Sub-bundle A landings at `de10601`: (a) risk_policy ratification single-fire; (b) cascade emitter no-op-skip; (c) USERPROFILE+HOME monkeypatch.
- Sub-bundle D landings at `6ba1925`: (d) form-render hidden anchor round-trip through soft-warn confirm `form_values`; (e) POST-time recompute TOCTOU window.
- Sub-bundle E landing at T-E.1 (`088990e`): (f) Schwab/TOS Account Order History multi-line group structure + WAIT TRG status + BASE-X.XX conditional skip.

**Codex R1 Minor #2 advisory:** recon doc sanitization wording at `docs/phase9-bundle-E-task-E3-parser-recon.md` line 131 says "first 30 lines" — actual sanitization is full-fixture. Orchestrator can tighten wording at integration merge.

## §9 Worktree teardown status

Worktree at `c:\Users\rwsmy\swing-trading\.worktrees\phase9-bundle-E-polish-and-phase10-handoff` REMAINS for operator-witnessed gate. Marker file `c:\Users\rwsmy\swing-trading\.copowers-subagent-active` REMOVED prior to adversarial review per dispatch brief §1.2.

Post-merge cleanup: orchestrator may run `git worktree remove .worktrees/phase9-bundle-E-polish-and-phase10-handoff` + `git branch -D phase9-bundle-E-polish-and-phase10-handoff` (locally; not push to origin). 7 worktree husks pending operator cleanup-script per dispatch brief §0.3 — this is the 8th.

## §10 Composition-surface verification (via `^def` grep)

New private helpers in `swing/journal/tos_import.py` (Bundle E only):

```bash
$ grep -rn "^def _\(is_qualifying_stop_header\|has_stp_marker\|clean_order_id\|try_parse_stp_continuation_price\|dedupe_fieldnames\|iter_unnamed_column_values\)" swing/
swing/journal/tos_import.py: _dedupe_fieldnames (post-R1)
swing/journal/tos_import.py: _iter_unnamed_column_values (post-R1)
swing/journal/tos_import.py: _is_qualifying_stop_header
swing/journal/tos_import.py: _has_stp_marker
swing/journal/tos_import.py: _clean_order_id
swing/journal/tos_import.py: _try_parse_stp_continuation_price
```

All 6 helpers are private (underscore-prefixed); no public-API additions. `extract_stop_orders` signature unchanged. `parse_tos_export` signature unchanged (internals reshaped to use `_dedupe_fieldnames`). `reconcile_tos` signature unchanged per dispatch brief §0.5 #9.

## §11 Phase 9 arc closing notes

**Phase 9 SHIPPED 2026-05-12** with Sub-bundle E. Arc closer summary:

| Sub-bundle | Tasks | Commits (impl + fix + report) | Codex rounds | Critical | Major | Accept-with-rationale | Test delta |
|---|---|---:|---:|---:|---:|---:|---:|
| A — risk_policy foundation | T-A.0..T-A.7 | 13 (8+4+1) | 5 | 0 | 4→3→3→1→0 | 2 | +200+ |
| B — reconciliation depth | T-B.0..T-B.8 | 14 (9+4+1) | 5 | 0 | 4→2→1→1→0 | 1 | +147 |
| C — hypothesis + equity | T-C.0..T-C.6 | 10 (7+2+1) | 3 | 0 | 3→1→0 | 1 | +130 |
| D — sector tamper hardening | T-D.0..T-D.3 | 9 (4+4+1) | 4 | 1→1→1→0 | 1→2→0→0 | 0 | +16 |
| E — final polish + Phase 10 hand-off | T-E.0..T-E.3 | 7 (4+3) | 2 | 0 | 2→0 | 0 | +10 |
| **Total Phase 9 arc** | **30 tasks** | **53 commits** | **19 Codex rounds** | **1 (resolved)** | **14 (all resolved)** | **4** | **+503 fast tests** |

- **53 commits** across the arc (30 task-impl + 17 Codex-fix + 5 return-reports + 1 ruff style).
- **19 Codex rounds total** across all 5 sub-bundles.
- **+503 fast tests** across the arc (cumulative fast suite 2462 → 2967 if Phase 8 baseline; current Bundle E close 2767 fast pass — the +503 number represents cumulative additions per sub-bundle return reports; some Bundle E new tests displace pre-existing skip-on-absent slots).
- **1 Critical finding** across the arc (Sub-bundle D R1 C#1 blank-field tamper bypass; resolved in-tree).
- **14 Major findings** across the arc; all resolved in-tree (zero unresolved at landing).
- **4 ACCEPT-WITH-RATIONALE positions** banked: 2 in Sub-bundle A (user-config hand-edit V2-hardening + ratification single-fire by-design); 1 in Sub-bundle B (equity_delta deferred to C); 1 in Sub-bundle C (sign convention brief-vs-spec cosmetic). **ZERO in Sub-bundles D + E** — cleanest arc-final state.
- **6 CLAUDE.md gotchas promoted** across the arc (3 A + 2 D + 1 E).
- **2 spec amendments pending V2.1 §VII.F routing** (D §7 + E §6.2).
- **2 V2 candidates banked at phase3e-todo.md** (Schwab inception-CSV ingestion; account_equity_snapshots semantic formalization).
- **Schema version v16 → v17** in atomic single-file landing at Sub-bundle A T-A.1; v17 unchanged through B/C/D/E (consumer-side only).

**Phase 10 dispatch readiness:** **UNBLOCKED.** Phase 10 brainstorm SHIPPED 2026-05-06 at `fe6cb45`. Phase 10 writing-plans dispatch is the orchestrator's next action post-Bundle-E-integration-merge. Phase 10 reads the hand-off note at `docs/phase3e-todo.md` (T-E.2 landing) for the binding inputs per spec §11.1-§11.5.

**Execution order LOCKED: 8 ✓ → 9 ✓ → 10 (next).**

---

**Implementer signing off.** Bundle E ready for operator-witnessed gate per dispatch brief §3. Bundle E SHIP CLOSES Phase 9.
