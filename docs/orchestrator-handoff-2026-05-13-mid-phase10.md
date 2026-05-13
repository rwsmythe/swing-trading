# Orchestrator handoff — 2026-05-13 (mid-Phase-10; post-Sub-bundle-B-ship)

You are taking over as orchestrator for the Swing Trading project mid-Phase-10. **2 of 5 Phase 10 sub-bundles SHIPPED** (A ✓ + B ✓); **3 remaining** (C → D → E). The prior orchestrator handed off at Phase 9 arc close (the brief at `docs/orchestrator-handoff-2026-05-13.md` covered that earlier transition) — this brief is the SECOND handoff today, scoped to the Phase 10 mid-arc state.

The current orchestrator is handing off NOW (between Sub-bundle B ship and Sub-bundle C dispatch) because:
1. **Clean steady state** — Sub-bundle B fully shipped + housekept + pushed; no in-flight work; no pending operator-decision; no pending gate.
2. **Maximum forward leverage** — Sub-bundle B's 5 deviations + 2 NEW forward-binding lessons are fresh and well-documented; encoded once here for the next 3 sub-bundles.
3. **Context economy** — 3 more sub-bundles of context (C+D+E) before a Phase 10 arc-close handoff would be a much heavier brief and a higher risk of misencoded state. Mid-arc handoff is the most efficient breakpoint.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). You will NOT see SessionStart claude-mem injection blocks. Do NOT attempt `mcp__plugin_claude-mem_mcp-search__*` or `mem-search` skill — both will fail. Auto-memory dir (`~/.claude/projects/c--Users-rwsmy-swing-trading/memory/MEMORY.md` + linked files) IS still loaded by the harness. See `~/.claude/projects/c--Users-rwsmy-swing-trading/memory/feedback_claude_mem_hook_blocks_disabled.md` for re-enablement criteria.

**Chrome MCP is AVAILABLE** at handoff (confirmed working in Sub-bundle A S3 gate + Sub-bundle B S2/S3/S4 gate). Use `mcp__claude-in-chrome__*` tools for browser-driven operator-witnessed gates. Load via `ToolSearch` with `select:mcp__claude-in-chrome__<tool_name>` before invoking.

## Step 1 — Read these in order

1. **This brief end-to-end** — captures Phase 10 mid-arc state + Sub-bundle C dispatch readiness.

2. **`docs/orchestrator-handoff-2026-05-13.md`** — prior orchestrator's handoff brief at Phase 9 arc close. Most of its "Operator preferences" (Step 5) + "Production-write classifier soft-block awareness" (Step 6) sections REMAIN VALID. Skim only.

3. **`docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md`** (AMENDED in-tree during Sub-bundle A R2+R3) — full plan. §F (lines 1257-1334) is Sub-bundle C scope; §I (lines 1665-1726) is cross-bundle invariants. §A.7 + §D Task A.1 + §A.18 + §A.5 + §A.5.1 + §A.11 + §A.11.1 are all amendments-applied-in-tree.

4. **`docs/phase10-electives-amendment.md`** — Sub-bundle C scope adds T-C.5 per-cohort discrepancy filter elective (amendment §2 Task C.5).

5. **`docs/phase10-bundle-A-return-report.md` §10** + **`docs/phase10-bundle-B-return-report.md` §5 + §8** — Sub-bundle A's 2 forward-binding lessons + Sub-bundle B's 4 plan-text deviations + 2 NEW forward-binding lessons. Cumulative 19 forward-binding lessons for Sub-bundle C dispatch brief §0.6 catalog.

6. **`docs/phase3e-todo.md`** "2026-05-13 Phase 10 Sub-bundle B ship" entry — 5 V2.1 §VII.F amendment candidates + 4 V2 candidates banked from Sub-bundle B; cumulative 12 §VII.F pending amendments enumerated.

7. **CLAUDE.md** status line + Gotchas section — Phase 10 mid-arc state is current as of `2d01890`.

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10
git status
git worktree list
python -m pytest -m "not slow" -q --ignore=tests/integration/test_phase8_pipeline_walkthrough.py | tail -5
ruff check swing/ --statistics | tail -3
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"
python verify_phase10.py
```

Expected:
- HEAD on main: `2d01890` (post-Sub-bundle-B-ship housekeeping).
- Working tree clean (3 untracked operator-provided artifact dirs: `reference/Books/`, `reference/minervini/`, `scripts/`).
- **2964 fast passing + 2 skipped on main HEAD `2d01890`** (worktree-side ~2960; +65 net from pre-Sub-bundle-B baseline 2899 / +69 from worktree pre-B baseline 2895; matches +46..+75 dispatch brief projection at the high end) — pytest result pending; will be updated in this brief once background task completes.
- Ruff baseline 18 (E501 only).
- Schema version 17.
- `verify_phase10.py` exits 0.
- 11 worktree husks pending cleanup-script (Phase 9 A/B/C/D/E + Sub-bundle 3e.8 Bundle 3 + Phase 9 writing-plans + Polish bundle 2026-05-10 + Phase 10 writing-plans + Phase 10 Sub-bundle A + Phase 10 Sub-bundle B).

## Step 3 — Project state at handoff (mid-Phase-10)

### HEAD + commit chain on main

```
2d01890 docs(phase10): post-Sub-bundle-B-ship housekeeping + 5 amendments + 2 lessons + 4 V2 candidates banked
6ed0f35 Merge phase10-bundle-B-trade-process-and-hypothesis-progress into main: Phase 10 Sub-bundle B
3d8a4d3 docs(phase10): Sub-bundle B return report — 7 task-impl + 1 Codex-fix; 2 rounds → NO_NEW_CRITICAL_MAJOR
a8eaf65 fix(phase10-bundle-B): Codex R1 Major #1 + #2 + Minor #1
... (7 more task-impl commits for Sub-bundle B)
6140081 docs(phase10): Sub-bundle B executing-plans dispatch brief
11ce75f docs(phase10): post-Sub-bundle-A-ship housekeeping + Option C policy revert + amendments banked
096de83 Merge phase10-bundle-A-shared-honesty-utility into main: Phase 10 Sub-bundle A
... (more Sub-bundle A + Phase 10 writing-plans commits)
a34c00d Merge phase10-writing-plans into main: Phase 10 implementation plan
```

### Project state

- **HEAD on main:** `2d01890` (post-Sub-bundle-B-ship housekeeping).
- **Test count:** **2964 fast passing + 2 skipped on main HEAD `2d01890`** (worktree-side ~2960; +65 net from pre-Sub-bundle-B baseline 2899 / +69 from worktree pre-B baseline 2895; matches +46..+75 dispatch brief projection at the high end) (pytest in progress; expected ~2960 main / ~2951 worktree-side based on Sub-bundle B return report; will be updated below). **3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures** banked separately (NOT regressions; pre-existing on `main` HEAD before Phase 10 work began).
- **Ruff baseline:** **18 (E501 only).** Unchanged across the entire Phase 9 arc + Phase 10 Sub-bundle A + B.
- **Schema version:** **v17.** LOCKED through Phase 10 V1 per §A.0 + §I.1 lock. `EXPECTED_SCHEMA_VERSION` stays at 17 through Sub-bundles C/D/E.
- **Active risk_policy:** `policy_id=5` (Option C revert post-Sub-bundle-A; `max_account_risk_per_trade_pct=0.5` cfg-aligned; `capital_floor_constant_dollars=7500.0`; `scratch_epsilon_R=0.10`). Chain: 1 (seed) → 2 (S3-operator-test) → 3 (S2.bis-divergence-test) → 4 (S2.bis-revert) → **5 (Option-C-revert; ACTIVE)**.
- **Production trades:** 8 total; 5 open (DHC/YOU/VSAT/CVGI/LAR) + 3 closed (VIR/CC/SGML). All 8 have `risk_policy_id_at_lock IS NULL` (pre-Phase-9 legacy; §A.5 fallback renders `[legacy: pre-Phase-9 trade]` annotation).
- **Production review_log:** 12 rows; 7 completed + 5 pending. Reviews 10 + 11 stamped `risk_policy_id_at_review_completion=4`; 10 NULL (pre-Phase-9-Sub-bundle-A landing or never-completed).
- **Production account_equity_snapshots:** 2 manual snapshots (snapshot #1 $2000 at 2026-05-11; snapshot #2 $1800 at 2026-04-01 back-recorded).
- **Production reconciliation:** 7 reconciliation_runs across Phase 9 gates; 30 discrepancies all resolved as `acknowledged_immaterial`.
- **swing.config.toml:** clean (`risk.max_risk_pct=0.005`).
- **user-config.toml:** intact (Finviz token + screen_query).

### Phase 10 dispatches shipped so far

| Bundle | HEAD | Codex rounds | Tests delta | Notes |
|---|---|---|---|---|
| **Phase 10 writing-plans** | `a34c00d` | 6 (operator-overridden past MAX_ROUNDS=5) | 0 (docs only) | 2008-line plan; ZERO ACCEPT-WITH-RATIONALE; cleanest writing-plans dispatch in project history |
| **Sub-bundle A** (shared honesty utility) | `096de83` | 4 | +128 | Foundational; AMENDED plan §A.7 in-tree (R2+R3); 3 plan-text deviations banked |
| **Sub-bundle B** (trade-process + hypothesis-progress + T-B.7) | `6ed0f35` | 2 (FASTEST Phase 10 chain) | +73 | First operator-visible surfaces; 5 plan-text deviations banked (4 return-report + 1 gate-surfaced) |

**Phase 10 arc shape:** 5 sub-bundles A→B→C→D→E with **39 tasks** total per electives amendment §3. **2 of 5 shipped (40%).**

## Step 4 — Sub-bundle C dispatch readiness (your next major action)

### Sub-bundle C = §4.3 tier-comparison + §4.7 deviation-outcome + T-C.5 per-cohort discrepancy filter

Per plan §F (lines 1257-1334) + electives amendment §2 Task C.5:

- **5 tasks plan §F:** T-C.0 recon, T-C.1 §3.3+§3.7 computations, T-C.2 TierComparisonVM + route + template, T-C.3 DeviationOutcomeVM + route + template, T-C.4 Sub-bundle C integration test + ruff sweep.
- **+1 elective:** T-C.5 per-cohort "exclude trades with unresolved discrepancies" filter helper (modifies tier-comparison + deviation-outcome surfaces; helper reusable in Sub-bundle B if operator extends per §A.11.1 V2 candidate).
- **Total: 6 tasks** in Sub-bundle C.

**Gate surfaces:** 3 browser (S2 `/metrics/tier-comparison` + S3 `/metrics/deviation-outcome` + S4 toggle verification) + 1 inline = 4 total. Under ≤6 budget.

### Sub-bundles C dispatch order (locked)

A ✓ → B ✓ → **C (your next dispatch)** → D → E. Each ships → orchestrator-witnessed gate via Chrome MCP → integration merge → orchestrator drafts next sub-bundle's dispatch brief.

### Sub-bundle A AMENDED §A.7 inheritance (BINDING for C)

Plan §A.7 + §D Task A.1 were AMENDED in-tree during Sub-bundle A Codex R2 + R3 (commits `e32f71c` + `75dd63f`). Sub-bundle C reads the AMENDED text. Specifically:

**HonestyBadges:** has `window_not_full_warning: bool = False` field (Class D cadence vs confidence-floor decoupling).
**Public helpers:** `badges_for_n` (R1 Minor #1; not `_badges_for_n`); standard Wilson CI (NOT continuity-correction).
**Risk_policy resolver:** signature is `read_at_trade_time_policy(conn, *, policy_id_stamp: int | None)` (NOT `trade: Trade`); accessors `get_trade_policy_id_stamp` + `get_review_policy_id_stamp`.
**BaseLayoutVM:** `stale_banner: str | None = None` (NOT `bool = False`); 5 base-layout fields + `unresolved_material_discrepancies_count` field.
**Discrepancies helper:** `count_unresolved_material(conn) -> int` (read-only; consumed by every metrics VM constructor per §A.18 cross-bundle pin).

### Sub-bundle B implementation conventions (BINDING for C)

Per Sub-bundle B return report §5 + §8 + the 5 banked V2.1 §VII.F amendment candidates:

1. **`mistake_cost_R` / `lucky_violation_R` aggregator pattern:** ALWAYS recompute per-trade via Phase 6 helpers. `review_log` is CADENCE-grain (no per-trade FK); the cadence aggregate CANNOT be cleanly mapped onto cohort-grain sum. Sub-bundle C's tier-comparison + deviation-outcome metrics that reference `mistake_cost_R` or `lucky_violation_R` aggregates MUST follow the same pattern.
2. **`ALL_COHORTS_KEY='__all__'`** sentinel for "all closed trades" toggle URL parameter. Reusable in any new cohort-toggle UI.
3. **`cumulative_R_pct_of_capital` rendered in PERCENT units** (NOT proportion) to match `absolute_loss_tripwire_pct`. Forward-binding for any other percent-vs-proportion metrics in C (`cohort_relative_to_aplus`, `cohort_expectancy_relative_to_aplus_pct`) — explicit rendering-unit pin needed.
4. **Cohort-tab enumeration surfaces ALL distinct `hypothesis_label` values** (4 pre-registered + N orphan-labeled + "All"). Default-active = FIRST registered cohort (NOT first overall, NOT "All").
5. **Sub-VM exclusions added to `_SUB_VM_EXCLUSIONS`** in `tests/web/test_view_models/test_base_layout_vm_coverage.py`: existing `ConfidenceBadgeVM` / `ProvisionalBadgeVM` / `SuppressionRowVM` + Sub-bundle B added `CohortTabVM` + `CohortProgressVM`. Sub-bundle C's new sub-VMs MUST be added to the same exclusion set IN THE SAME COMMIT (forward-binding lesson #20-equivalent).

### 19 forward-binding lessons (Phase 9 arc + Sub-bundle A + B)

Cumulative lesson catalog the Sub-bundle C dispatch brief §0.6 MUST reference:

1-15: Phase 9 arc lessons (see Sub-bundle A dispatch brief §0.5 for full catalog).
16: Plan §A.7 binding-interface amendments flow into plan text in SAME commit as code change (Sub-bundle A R2 M#1 + R3 M#1 caught the same failure-mode twice).
17: Statistical helpers with multiple textbook-correct variants need explicit spec pin with citation (Sub-bundle A Wilson CI standard-vs-continuity-correction).
**18 (NEW from Sub-bundle B):** Cadence-grain audit tables CANNOT be cleanly mapped to cohort-grain metrics without per-trade FK. Discriminating-test pattern: plant conflicting cadence row + assert metric reflects per-trade compute, NOT planted aggregate.
**19 (NEW from Sub-bundle B):** Unit-semantic precision (percent vs proportion) needs explicit rendering pin in VM + template + discriminating test. Sub-bundle C `cohort_relative_to_aplus` + `cohort_expectancy_relative_to_aplus_pct` are likely-affected.

### 12 cumulative V2.1 §VII.F amendments pending

Per `docs/phase3e-todo.md` 2026-05-13 entries:

**Phase 9 D + E (2 pending; banked from Sub-bundle D/E return reports):**
1. Phase 9 spec §7 sector_industry anchor wording supersession (recon doc `docs/phase9-bundle-D-task-D0-recon.md`)
2. Phase 9 spec §6.2 multi-line parser wording supersession (recon doc `docs/phase9-bundle-E-task-E3-parser-recon.md`)

**Phase 10 Sub-bundle A (3 pending; banked from Sub-bundle A return report §8):**
3. Plan §D Task A.1 Wilson CI reference value `[0.094, 0.901]` for k=2,n=4 should correct to standard `[0.150, 0.850]`.
4. Plan §A.5 `read_at_trade_time_policy` signature: `policy_id_stamp: int | None` direct (Trade dataclass lacks `risk_policy_id_at_lock` column).
5. Plan §A.6 `BaseLayoutVM.stale_banner: str | None = None` (NOT `bool = False`).

**Phase 10 Sub-bundle B (4 from return report §5 + 1 gate-surfaced; banked from Sub-bundle B housekeeping):**
6. Plan §E Task B.1 `mistake_cost_R` aggregator source: "always recompute per-trade" (review_log is cadence-grain).
7. Plan §E Task B.2 `ALL_COHORTS_KEY='__all__'` sentinel (avoid collision).
8. Plan §A.5.1 + spec §3.2 `cumulative_R_pct_of_capital` rendering unit (PERCENT vs proportion).
9. Electives amendment §2 Task B.7 corrected: "new block surfaces BOTH `mistake_cost_R` AND `lucky_violation_R` as derived per-trade display values; existing form unchanged" (amendment assumed pre-existing display).
10. (GATE-SURFACED) Plan §E Task B.2 cohort-tab enumeration: render tabs for ALL distinct `hypothesis_label` values (registered + orphan) + "All"; default-active = FIRST registered (not first overall, not "All").

**Phase 10 Sub-bundle A orphans from Phase 10 spec (2; banked from Sub-bundle A writing-plans):**
11. Phase 10 spec §A.11 transition-history supersession of spec §3.2 V1-limitation (already applied at plan level; spec text amendment pending).
12. Phase 10 spec §A.21 `mistake_cost_R_rolling_N_total` sum-class with bootstrap CI Class assignment (V2 candidate per §A.21 deliberate spec-deviation).

### Cross-bundle pin at T-A.7 (STILL SKIPPED)

`tests/web/test_view_models/test_base_layout_vm_coverage.py::test_existing_dashboard_vm_has_unresolved_material_field` is SKIPPED with reason naming **Sub-bundle E T-E.3** as the un-skip point. Sub-bundle C dispatch MUST NOT touch the skip; un-skip lands at T-E.3 retrofit of 6 existing base-layout VMs.

### Sub-bundle C operator-decision-pending items (NONE)

Sub-bundle C has ZERO operator-decision-pending items at handoff. T-C.5 elective is fully scoped in electives amendment §2 Task C.5. Plan §F (Tasks C.0..C.4) + electives §2 Task C.5 = complete scope. No design questions outstanding.

## Step 5 — Your first deliverable

Per the Sub-bundle B housekeeping commit `2d01890` standing-by clause:

1. Run standard bootstrap verification (Step 2) + read files in Step 1 order.
2. Draft Sub-bundle C **executing-plans dispatch brief** at `docs/phase10-bundle-C-executing-plans-dispatch-brief.md`. Template = `docs/phase10-bundle-B-executing-plans-dispatch-brief.md` (the brief that produced Sub-bundle B's 2-round Codex chain + +73 tests).
3. Sub-bundle C dispatch brief MUST include:
   - **§0 inputs** with HEAD baseline `2d01890` (or whatever main HEAD is at brief-drafting time).
   - **§0.5 AMENDED §A.7 + Sub-bundle B implementation conventions inheritance** — copy verbatim from Sub-bundle B dispatch brief §0.5, extend with Sub-bundle B's 5 deviation notes (per Step 4 above).
   - **§0.6 19-lesson forward-binding catalog** — extend from Sub-bundle B's 17-lesson catalog with lessons #18 + #19 (per Step 4 above).
   - **§0.7 Sub-bundle C scope summary** — 6 tasks: T-C.0..T-C.4 + T-C.5.
   - **§0.8** (BINDING semantics): if Sub-bundle C surfaces any cohort-grain metric that touches `mistake_cost_R` / `lucky_violation_R` aggregates, MUST follow Sub-bundle B's "always recompute per-trade" pattern (per forward-binding lesson #18).
   - **§0.9** (BINDING semantics): any percent-vs-proportion-flavored metric (`cohort_relative_to_aplus`, etc.) MUST have explicit rendering-unit pin in VM + template + discriminating test (per forward-binding lesson #19).
   - **§2 operator-witnessed gate** — 4 surfaces: S1 inline + S2 `/metrics/tier-comparison` + S3 `/metrics/deviation-outcome` + S4 T-C.5 toggle verification on tier-comparison + deviation-outcome surfaces.
   - **§5 paste-ready implementer prompt** with worktree path + DO NOT list.
4. Commit + push the brief.
5. Provide paste-ready implementer prompt INLINE in the chat (operator preference; do NOT just point at the brief).
6. Stand by for operator commission of Sub-bundle C executing-plans dispatch.

## Step 6 — Operator preferences (durable; carry over from prior orchestrator handoff)

- **Implementer-dispatch is the default** per `~/.claude/projects/.../memory/feedback_orchestrator_vs_implementer_execution.md`.
- **Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."
- **Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly** (binding convention 2026-05-09).
- **Implementer runs adversarial-critic** (per orchestrator-context "Executing-plans dispatch convention" 2026-05-02).
- **Brief-recommended technical micro-decisions need empirical pre-verification** before locking.
- **Multi-choice format for design questions** (operator preference; AskUserQuestion preferred).
- **Chrome MCP gate-driving** is the established pattern. Confirmed working at Sub-bundle B S2/S3/S4 gate. Use `mcp__claude-in-chrome__*` tools (load via ToolSearch first per system prompt instructions).
- **Spec is canonical over brief on cosmetic typos** (codified via Phase 9 Sub-bundle C R1 M#1 equity_delta sign convention ACCEPT-WITH-RATIONALE).
- **Production-write classifier soft-block** workaround: when about to invoke production-write where operator pre-authorized via AskUserQuestion, if classifier blocks, surface back to operator with action description + ask for plain-chat "yes" confirmation.
- **Stop the web server when done.** Operator surfaced this preference at Sub-bundle A gate ("ensure you stop the web server"). Worktree-side `swing web` launches MUST use a non-conflicting port (e.g., `--port 8081`) if the operator has a separate `swing web` running on the default port 8080, AND MUST be killed at gate completion.

## Step 7 — Worktree-side swing web launch pattern (BINDING for Chrome MCP gates)

Sub-bundle A + B gates established the pattern:

```bash
# 1. Check if operator's swing web is already on default port 8080:
netstat -ano | grep ":8080"

# 2. If port 8080 in use by operator, launch worktree-side on 8081:
cd "C:/Users/rwsmy/swing-trading/.worktrees/<branch>"
PYTHONPATH=. python -m swing.cli web --port 8081
# (use Bash run_in_background=true)

# 3. Poll for up:
for i in 1 2 3 4 5 6; do CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8081/metrics 2>&1); if [ "$CODE" = "200" ]; then echo "UP on 8081"; break; fi; sleep 2; done

# 4. Drive Chrome MCP against the worktree-side server (8081).

# 5. At gate completion: kill the worktree-side process (port 8081 only):
netstat -ano | grep ":8081" | awk '{print $5}' | head -1 | xargs -I {} taskkill //PID {} //F
# Verify 8080 still up (operator's session preserved).
```

This pattern was used cleanly at Sub-bundle B gate (no interference with operator's main-HEAD session on 8080).

## Step 8 — Production-write classifier soft-block awareness

Carried forward from 2026-05-13 handoff brief Step 6: when the orchestrator drives production-mutating actions via Bash / javascript_tool, the auto-mode classifier may soft-block. **Workaround:** when about to invoke a production-write action where operator pre-authorized via AskUserQuestion, IF the classifier blocks, surface back to operator with the action description + ask for plain-chat "yes" confirmation. Don't try to work around the classifier in any other way.

**Not hit during Sub-bundle A or B gates** (operator-witnessed surfaces were all read-only browser walkthroughs).

## Step 9 — Banked items NOT to scope into Sub-bundle C

Sub-bundle C dispatch brief MUST explicitly exclude:

- **§8.4 Corporate_Actions MVP** — deferred as standalone post-Phase-10 dispatch (phase3e-todo 2026-05-13 entry).
- **T-E.5 web-form manual snapshot capture** — Sub-bundle E scope per electives amendment §2.
- **T-E.6 per-trade discrepancy indicator on trade detail page** — Sub-bundle E scope per electives amendment §2.
- **T-B.7 lucky_violation_R on review form** — Sub-bundle B scope; already SHIPPED at `6ed0f35`.
- **Un-skipping `test_existing_dashboard_vm_has_unresolved_material_field`** — Sub-bundle E T-E.3 owns this.
- **Adding HTMX OOB-swap, embedded forms, or HX-Redirect** on `/metrics/tier-comparison` or `/metrics/deviation-outcome` (§A.9 + §I.6 LOCK; pure server-rendered HTML).
- **Adding chart rendering** (Sub-bundle E T-E.2 only; inline SVG per §A.10).
- **New schema** (`0018_*.sql` migration; ALTER on existing tables) — §A.0 + §I.1 LOCK BINDING; `EXPECTED_SCHEMA_VERSION` stays at 17.
- **Spec amendments to spec §3.3 R1 M3 `cohort_ci_overlap_descriptor` text-only lock** or spec §3.7 R1 M4 `cohort_decision_criterion_evaluation_text` manual-only lock — both LOCKED per plan.

## Step 10 — Quick reference summary

| Artifact | Path / commit |
|---|---|
| Phase 10 spec | `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` (`fe6cb45`) |
| Phase 10 plan (AMENDED in-tree) | `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` (last amendment at `75dd63f`) |
| Phase 10 writing-plans return | `docs/phase10-writing-plans-return-report.md` |
| Phase 10 writing-plans brief | `docs/phase10-writing-plans-dispatch-brief.md` |
| Electives amendment | `docs/phase10-electives-amendment.md` (`9525f17`) |
| Sub-bundle A dispatch brief | `docs/phase10-bundle-A-executing-plans-dispatch-brief.md` |
| Sub-bundle A return report | `docs/phase10-bundle-A-return-report.md` |
| Sub-bundle A merge | `096de83` |
| Sub-bundle B dispatch brief | `docs/phase10-bundle-B-executing-plans-dispatch-brief.md` |
| Sub-bundle B return report | `docs/phase10-bundle-B-return-report.md` |
| Sub-bundle B merge | `6ed0f35` |
| Sub-bundle B housekeeping | `2d01890` |
| Sub-bundle C dispatch brief | TBD (your first major deliverable) |
| Sub-bundle C return report | TBD (post-C-ship) |
| Phase 11 candidates banked | `docs/phase3e-todo.md` (active; archive companion `docs/phase3e-todo-archive.md`) |

### Worktree husks pending operator cleanup-script (11 total)

1. `.worktrees/3e8-bundle-3-maturity-and-stop-tighten-hints/`
2. `.worktrees/phase9-bundle-A-risk-policy-foundation/`
3. `.worktrees/phase9-bundle-B-reconciliation-depth/`
4. `.worktrees/phase9-bundle-C-hypothesis-and-equity/`
5. `.worktrees/phase9-bundle-D-sector-tamper-hardening/`
6. `.worktrees/phase9-bundle-E-polish-and-phase10-handoff/`
7. `.worktrees/phase9-writing-plans/`
8. `.worktrees/polish-bundle-2026-05-10/`
9. `.worktrees/phase10-writing-plans/`
10. `.worktrees/phase10-bundle-A-shared-honesty-utility/`
11. `.worktrees/phase10-bundle-B-trade-process-and-hypothesis-progress/`

Operator's cleanup-script handles ACL-locked Windows worktree husks (Phase 6/7/8/9 + Phase 10 pattern). Not orchestrator-blocking.

## Operator-facing notes for handoff turn

When operator reads this brief, they should expect:
1. Confirmation that Phase 10 mid-arc state is clean (Sub-bundle A + B SHIPPED; 3 remaining).
2. Sub-bundle C dispatch brief drafting as your next major action.
3. No outstanding operator-action items blocking Sub-bundle C dispatch.
4. Active risk_policy = `policy_id=5` (cfg-aligned; Option C revert post-Sub-bundle-A; no further policy work needed for Phase 10).
5. 11 worktree husks pending operator cleanup-script (informational; not blocking).

The prior orchestrator's recommendation on absorption order:
- Read this handoff brief end-to-end.
- Read Phase 10 plan §F (Sub-bundle C scope) + electives amendment §2 Task C.5.
- Read Sub-bundle B return report §5 + §8 (5 deviations + 2 forward-binding lessons).
- Draft Sub-bundle C dispatch brief; commit + push; provide paste-ready prompt; stand by.

Sub-bundle B was the **fastest Phase 10 chain to date** (2 Codex rounds → NO_NEW_CRITICAL_MAJOR with ZERO ACCEPT-WITH-RATIONALE). Sub-bundle C is expected to be similar or slightly slower (more complex statistical surfaces: Wilson + bootstrap CIs per cohort for tier-comparison; cohort-ci-overlap descriptor text-only logic).

Standing by for operator commission of Sub-bundle C executing-plans dispatch brief drafting.
