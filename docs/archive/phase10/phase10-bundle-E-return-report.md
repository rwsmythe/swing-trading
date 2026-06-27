# Phase 10 Sub-bundle E — return report (CLOSES Phase 10)

**Branch:** `phase10-bundle-E-process-grade-trend-and-polish`
**Worktree:** `.worktrees/phase10-bundle-E-process-grade-trend-and-polish/`
**HEAD:** `4787a0a fix(phase10-bundle-E): Codex R1 Major #1 — rolling-sum line for point-class metrics`
**Baseline:** `5d86751` (main HEAD at worktree-creation time; brief commit).

## §1 Final HEAD + commit count breakdown

7 commits on the branch:

| # | SHA | Description |
|---|---|---|
| 1 | `5a29450` | feat(metrics): §3.8 process-grade-trend computations (T-E.1) |
| 2 | `7e8d1ba` | feat(metrics): process-grade-trend VM + route + template — inline SVG (T-E.2) |
| 3 | `fb6e48a` | feat(metrics): unresolved-material discrepancy banner — base.html.j2 + 6 existing base-layout VMs (T-E.3) |
| 4 | `f5a4f59` | feat(web): manual snapshot capture web form (T-E.5 elective) |
| 5 | `334effb` | feat(web): per-trade unresolved-material indicator on trade detail (T-E.6 elective) |
| 6 | `4a666d1` | docs(phase10): Phase 10 closer — Phase 11 hand-off + final integration sweep (T-E.4) |
| 7 | `4787a0a` | fix(phase10-bundle-E): Codex R1 Major #1 — rolling-sum line for point-class metrics |

**Breakdown:** 6 task-impl + 1 Codex-fix. Return report commit will be #8 (this file).

## §2 Codex round chain

**2 rounds → NO_NEW_CRITICAL_MAJOR — ties FASTEST Phase 10 chain** (matches Sub-bundles B + C precedent; Phase 9 Sub-bundle E precedent).

| Round | Critical | Major | Minor | Outcome |
|---|---:|---:|---:|---|
| R1 | 0 | 1 | 0 | M#1 rolling-sum line for point-class fix |
| R2 | 0 | 0 | 0 | NO_NEW_CRITICAL_MAJOR — confirmed all binding LOCKs intact |

**ZERO Critical findings** + **ZERO ACCEPT-WITH-RATIONALE** — matches Sub-bundle A/B/C/D/E clean record. **Cleanest 5-bundle arc-final state in project history (Phase 10 = ZERO ACCEPT-WITH-RATIONALE across the entire arc).**

## §3 Test count delta + ruff baseline delta

| Metric | Baseline (worktree) | Sub-bundle E ship | Delta |
|---|---:|---:|---:|
| Fast tests passing | 3147 + 6 skipped | **3254 + 5 skipped** | **+107** |
| Ruff (E501 only) | 18 | 18 | 0 |
| Schema version | 17 | 17 | 0 |

**+107 above projection (+48..+77)** — matches Sub-bundle A (+128) + B (+73) + C (+84) + D (+102) overshoot precedent.

**Phase 10 arc total: 3254 fast tests** (from pre-Phase-9 baseline 1957 → +1297 across Phase 9 + Phase 10).

Pre-existing failures (NOT regressions): 3 in `tests/integration/test_phase8_pipeline_walkthrough.py` — predate this bundle per CLAUDE.md status line.

Cross-bundle T-A.7 pin un-skipped at T-E.3 SAME COMMIT (`fb6e48a`); test passes.

## §4 Operator-witnessed verification surfaces (PENDING)

S1 (inline pytest + ruff + verify_phase10) PASS. S2-S7 PENDING orchestrator-driven gate per dispatch brief §2:

- S2: `/metrics/process-grade-trend` (Chrome MCP; SVG markers + polyline gating + 3 distinct text targets per lesson #23)
- S3: Reconciliation banner FIRES (production-write — plant 1 unresolved discrepancy)
- S4: Reconciliation banner CLEARS (resolve discrepancy back)
- S5: `/metrics` umbrella + 8-tile smoke
- S6: T-E.5 web-form GET + POST → HX-Redirect (production-write — operator submits cash basis equity)
- S7: T-E.6 trade detail discrepancy indicator (plant + revert pattern)

## §5 Per-task deviations from the plan (with rationale)

Banked as V2.1 §VII.F amendment candidates:

1. **T-E.3 ConfigPageVM (not ConfigVM per brief §0.11)** — actual class name in `swing/web/view_models/config.py` is `ConfigPageVM`; brief used the abbreviated form. No code drift, just a name-mismatch in the brief.

2. **T-E.3 retrofitted 10 base-layout VMs (not 6 per plan)** — plan §H named 6 (Dashboard/Pipeline/Journal/Watchlist/Config/PageError). Implementation retrofitted those 6 PLUS 4 more whose templates extend `base.html.j2` (ReviewVM / CadenceCompleteVM / ReviewsPendingVM / TradeDetailVM). Defense-in-depth per CLAUDE.md "base.html.j2 is shared" gotcha — if any VM that extends base.html.j2 lacks the new field, Jinja would raise UndefinedError on render. The cross-bundle pin (which checks DashboardVM specifically) is satisfied by the 6 named; the additional 4 closed remaining surfaces preemptively.

3. **T-E.5 service is `record_snapshot` (NOT `record_snapshot_with_audit` per brief §0.5)** — Phase 9 Sub-bundle C ship-time naming preserved (`swing/trades/account_equity_snapshots.py:record_snapshot`). Brief referenced a different name that was never landed. Service-layer transactional discipline (BEGIN IMMEDIATE / COMMIT / ROLLBACK + reject-caller-held-tx) is honored.

4. **T-E.1 confidence-floor warning never drops at production callsite by construction** — with `N=10` (spec §8.5 LOCK) and `global_confidence_floor_n=20`, the predicate `effective_n < global_confidence_floor_n` is always True since `effective_n = min(len(samples), N) ≤ 10 < 20`. Implementation follows the §A.4 LOCK; the spec §5.4 "warning drops at effective_n ≥ global_confidence_floor_n" band is reachable only with an explicit `window_size ≥ 20` override. Discriminating test exercises `window_size=20` to verify the band semantics are reachable.

5. **T-E.1 `mistake_cost_R_rolling_N_total` rolling LINE renders SUM** (NOT mean; Codex R1 M#1 fix) — surfaced + fixed in-tree at `4787a0a` with a discriminating regression test. The value-slot already returned the window sum via `render_class_d(underlying_class='point')`; the line builder was mistakenly using the mean formula. Now symmetric.

## §6 Codex Major findings ACCEPTED with rationale (if any)

**ZERO ACCEPT-WITH-RATIONALE** — all 1 Major finding resolved in-tree with a code-content fix + discriminating test. Matches Sub-bundle A/B/C/D + Phase 9 Sub-bundle E clean record.

## §7 Watch items for orchestrator

1. **Operator-witnessed gate S2-S7 pending** — 6 browser-side checks via Chrome MCP on port 8081. S3+S4+S6+S7 require production-write authorization (plant + revert for banner / discrepancy + snapshot record).

2. **Cross-bundle pin un-skip verified at integration merge** — `tests/web/test_view_models/test_base_layout_vm_coverage.py::test_existing_dashboard_vm_has_unresolved_material_field` no longer carries the `@pytest.mark.skip` decorator + passes against the retrofitted DashboardVM.

3. **Sub-bundle E ship CLOSES Phase 10** — Phase 11 candidate triage UNBLOCKED + 3 post-Phase-10 standalone dispatches UNBLOCKED (cleanup-script `-DeregisterFirst` extension + test-runtime xdist analysis + §8.4 Corporate_Actions MVP). All enumerated at `docs/phase3e-todo.md` 2026-05-13 Phase 10 closer section.

4. **CLAUDE.md status-line update** — orchestrator drafts the Sub-bundle E SHIPPED entry per Phase 9 Sub-bundle E pattern; includes the Phase 10 arc closer aggregate (§9 below).

5. **Worktree husk** — Sub-bundle E teardown expected to leave ACL-locked husk; 7th in cleanup-script queue.

## §8 V2 candidates banked (NEW from Sub-bundle E)

1. **Orphan-emit discrepancy detail page** — global banner counts only trade-attributed discrepancies via `count_unresolved_material` which JOINs on `trades.id`. Orphan emits (sector_tamper / equity_delta / cash_movement_mismatch with NULL trade_id) are not surfaced anywhere. V2: dedicated orphan-discrepancy detail page or a sub-section on the discrepancy CLI's list view.

2. **`render_class_d` underlying_class='B' + 'point' dual mode for `mistake_cost_R_rolling_N_per_trade` + `_total`** — the per-trade-mean Class B variant + the cohort-total "point" variant could be unified through a `samples_aggregator: Literal["mean", "sum"]` parameter on `render_class_d` so future sum-class metrics inherit consistent behavior.

## §9 Phase 10 arc closer aggregate

| Sub-bundle | Commits | Codex rounds | Tests delta | Critical-resolved | Major-resolved | ACCEPT-WITH-RATIONALE | CLAUDE.md gotchas promoted |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 15 | 4 | +128 | 0 | 3 | 0 | 0 |
| B | 9 | 2 | +73 | 0 | 2 | 0 | 0 |
| C | 8 | 2 | +84 | 0 | 2 | 0 | 0 |
| D | 12 | 3 | +102 | 0 | 5 | 0 | 0 |
| E | 8 | 2 | +107 | 0 | 1 | 0 | 0 |
| **Total** | **52** | **13** | **+494** | **0** | **13** | **0** | **0** |

**Phase 10 closer highlights:**

- **52 commits across A+B+C+D+E** (34 task-impl + 12 Codex-fix + 5 return-reports + 1 ruff).
- **13 Codex rounds total** (4+2+2+3+2) — tied with Phase 9 D + E for tight convergence.
- **+494 cumulative fast tests** (final 3254). Above the +198..+316 projection.
- **ZERO Critical findings entire arc.**
- **ZERO ACCEPT-WITH-RATIONALE banked** — cleanest 5-bundle arc-final state in project history. Phase 9 had 4 banked (2 A + 1 B-later-resolved-C + 1 C).
- **ZERO CLAUDE.md gotchas promoted** — every defect class hit during Phase 10 was already covered by existing gotchas; no new ones surfaced.
- **27 V2.1 §VII.F amendments pending** (3 A + 5 B + 5 C + 5 D + 4 E + 2 Phase 9 amendments). Enumerated in `docs/phase3e-todo.md` 2026-05-13 closer section.
- **3 post-Phase-10 standalone dispatches unblocked** (cleanup-script `-DeregisterFirst` + test-runtime xdist + §8.4 Corporate_Actions MVP).
- **§A.0 ZERO-new-schema LOCK preserved** through entire arc — schema v17 unchanged through Phase 10 V1.

## §10 Phase 11 hand-off pointer

`docs/phase3e-todo.md` 2026-05-13 Phase 10 closer section enumerates Phase 11 candidates:
- §8.4 Corporate_Actions MVP (standalone dispatch).
- Schwab API Phase A integration.
- `mistake_cost_R_rolling_N_total` sum-class with bootstrap CI.
- Schwab inception-CSV ingestion.
- `account_equity_snapshots.equity_dollars` cash-basis-vs-MTM semantic formalization.
- Orphan discrepancy detail surface.
- Per-cohort "exclude paused-interval trades" filter (T-C.5 UI pattern reuse).

## §11 Composition-surface verification via `^def` grep

Per lesson #5 forward-binding (`^def` grep for definition surfaces — NOT caller-site grep):

- `grep -rn "^def " swing/metrics/process_grade_trend.py` → 10 internal helpers + 1 public `compute_process_grade_trend`.
- `grep -rn "^def " swing/web/view_models/metrics/process_grade_trend.py` → 8 internal helpers + 1 public `build_process_grade_trend_vm`.
- `grep -rn "^def " swing/web/routes/account.py` → 3 public route handlers (`account_snapshot_form`, `account_snapshot_post`) + 1 helper (`_render_form`).
- `grep -rn "^def list_unresolved_material" swing/metrics/discrepancies.py` → 1 definition (`list_unresolved_material_for_trade`).
- `grep -rn "^def _to_discrepancy_display" swing/web/view_models/trades.py` → 1 definition.

## §12 Plan-text amendments applied in-tree during Codex rounds

ZERO plan-text amendments needed in-tree during the chain. R1 M#1 was a code-content fix (mean → sum line for point-class), not a plan-text drift. Plan §A.21 was already correct in spec'ing "point" as sum semantics; the implementation just needed to match in the line builder.

---

*End of return report. Sub-bundle E CLOSES Phase 10. Orchestrator drives operator-witnessed gate + integration merge + CLAUDE.md / phase3e-todo housekeeping.*
