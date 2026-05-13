# Phase 10 Sub-bundle C — executing-plans return report

**Branch:** `phase10-bundle-C-tier-and-deviation` (worktree at
`.worktrees/phase10-bundle-C-tier-and-deviation`).
**Baseline:** `5bddb02` (HEAD of main pre-dispatch-brief; mid-Phase-10
orchestrator handoff brief).
**Final HEAD pre-return-report:** `ffe916d`.

Sub-bundle C ships the third + fourth operator-visible Phase 10 dashboard
surfaces (§4.3 tier-comparison + §4.7 deviation-outcome) and the T-C.5
per-cohort discrepancy-filter elective. All 6 tasks (T-C.0..T-C.5) land
ZERO new schema; consume the AMENDED Sub-bundle A interfaces + Sub-bundle
B implementation conventions.

---

## §1 Final HEAD + commit count breakdown

7 commits total on top of the dispatch brief commit `e14a6bf`:

| Commit  | Task | Shape | Description |
|---------|------|-------|---|
| `eb3b512` | T-C.1 | task-impl | feat(metrics): §3.3 + §3.7 tier-comparison + deviation-outcome computations |
| `3d3eaae` | T-C.2 | task-impl | feat(metrics): tier-comparison VM + route + template — GET /metrics/tier-comparison |
| `da62a9e` | T-C.3 | task-impl | feat(metrics): deviation-outcome VM + route + template — GET /metrics/deviation-outcome |
| `e09b1ff` | T-C.4 | task-impl + ruff | chore(metrics): Sub-bundle C integration sweep |
| `b2d351e` | T-C.5 | task-impl (elective) | feat(metrics): per-cohort discrepancy-filter elective |
| `ffe916d` | R1 fix | Codex-fix | fix(phase10-bundle-C): Codex R1 Major #1 + #2 + Minor #1 |
| (this commit) | return-report | docs | docs(phase10): Sub-bundle C return report |

= 5 task-impl + 1 Codex-fix + 1 return-report = 7 commits.

T-C.0 (recon) intentionally has no commit per plan §F (read-only
verification; captured inline in this return-report §1.1).

### §1.1 T-C.0 recon — verified intact

Sub-bundle A interface (per dispatch brief §0.5):
- `swing/metrics/honesty.py`: `wilson_ci`, `bootstrap_ci_mean`,
  `suppress_for_n`, `badges_for_n` (PUBLIC),
  `render_class_a/b/c/d`, `HonestyBadges` (3 fields including
  `window_not_full_warning`), `WilsonCI`, `BootstrapCI`,
  `SuppressedMetric`, `HonestyClass`. All confirmed by import-level
  smoke + actual usage in tier.py.
- `swing/metrics/policy.py`: `read_live_policy`,
  `read_at_trade_time_policy` (takes `policy_id_stamp: int | None`),
  `read_at_review_time_policy`, `get_trade_policy_id_stamp`,
  `get_review_policy_id_stamp`. Confirmed.
- `swing/metrics/cohort.py`: `list_trades_for_cohort`,
  `list_closed_trades_for_cohort`, `count_per_cohort`. Confirmed (and
  extended by T-C.5 with `filter_trades_without_unresolved_material_discrepancies`).
- `swing/metrics/discrepancies.py:count_unresolved_material`. Confirmed
  + consumed by both new metrics VM factories.

Sub-bundle B aggregator (per dispatch brief §0.5):
- `swing/metrics/process.py:compute_trade_process_metrics`. Confirmed
  (read-only; NOT consumed by tier.py since tier.py needs only
  win/loss/scratch + realized_R — heavier process.py pipeline overkill).
- `swing/web/view_models/metrics/{trade_process_card,hypothesis_progress_card}.py`
  — confirmed; tier.py + deviation_outcome.py follow the same VM
  factory + base-layout-mixin shape (factory eagerly populates
  `unresolved_material_discrepancies_count` per plan §A.18 + §I.5).

Migration 0008 cohort governance config (verbatim transcription
banked from dispatch brief §0.11 and re-verified against
`swing/data/migrations/0008_hypothesis_registry.sql`):

| name | target_sample_size | consecutive_loss_tripwire | absolute_loss_tripwire_pct | decision_criteria |
|---|---:|---:|---:|---|
| `A+ baseline` | 20 | 5 | 5.0 | `Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%` |
| `Near-A+ defensible: extension test` | 10 | 4 | 5.0 | `Mean R-multiple within 25% of A+ baseline mean` |
| `Sub-A+ VCP-not-formed` | 5 | 3 | 5.0 | `Confirm negative mean R-multiple` |
| `Capital-blocked: smaller-position test` | 10 | 4 | 5.0 | `Mean R-multiple positive; defensibility of smaller-position approach` |

The 4 `decision_criteria` strings are the BINDING seed text that
deviation-outcome's `decision_criterion_evaluation_text` field renders
verbatim per spec §3.7 R1 M4 LOCK.

---

## §2 Codex round chain

**2 rounds → NO_NEW_CRITICAL_MAJOR** (matches FASTEST Phase 10 chain;
ties Phase 10 Sub-bundle B + Phase 9 Sub-bundle E).

| Round | Critical | Major | Minor | Verdict |
|---:|---:|---:|---:|---|
| 1 | 0 | 2 | 1 | ISSUES_FOUND |
| 2 | 0 | 0 | 0 | NO_NEW_CRITICAL_MAJOR |

**R1 Major #1** — Discrepancy-filter toggle href used absolute path
`/metrics/tier-comparison?exclude_discrepancies=1` instead of the
relative form `?exclude_discrepancies=1` specified verbatim in
electives amendment §2 + dispatch brief §0.12. The locked-pattern
mismatch + the deployment-survivability concern (mounted-app /
root-path deployments) were both addressed by the fix.

**R1 Major #2** — Percent-unit rendering checks at the page-body
level (`assert "%" in body`) were not discriminating because the
decision-criteria seed text contains literal `%` substrings (e.g.,
"win rate > 30%", "within 25% of A+ baseline mean"). Forward-binding
lesson #19 requires asserting numeric value AND exact rendered
substring with unit string.

**R1 Minor #1** — `swing/metrics/cohort.py` filter helper docstring
claimed orphan-emit discrepancies "remain counted by the global
`unresolved_material_discrepancies_count` banner" — incorrect because
`count_unresolved_material` JOINs on `trades.id` and excludes orphans
today (V1 SCOPE LIMITATION documented in `swing/metrics/discrepancies.py`).

**ZERO ACCEPT-WITH-RATIONALE positions banked** — all 2 Major + 1 Minor
resolved with code-content fixes. Matches Sub-bundles D + E + Phase 10
Sub-bundle B's clean record (Phase 9 arc precedent: 4 ACCEPT positions
across A+B+C+D+E; Phase 10 A+B+C arc: ZERO so far).

R2 verified all 3 R1 resolutions hold + asked for new findings on the
relative-href routing semantics + percent-substring robustness + orphan-
banner docstring accuracy. ZERO new findings.

---

## §3 Test count delta + ruff baseline delta

### §3.1 Fast test count

Baseline (worktree-side at `5bddb02`): **2961 passed + 6 skipped** (3
pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py`
failures inherited; NOT Sub-bundle C regressions).

Sub-bundle C delta: **+80 fast tests** (final 3041 passed + 6 skipped;
3 pre-existing failures unchanged).

Within projected band +34..+56 lower bound but well above the upper
estimate — matches Sub-bundle A (+128) + Sub-bundle B (+73) precedent
for discriminating-test-rich Phase 10 work.

Breakdown:
- T-C.1 (`tests/metrics/test_tier.py`): +30 tests.
- T-C.2 (`tests/web/test_view_models/test_tier_comparison_vm.py` +
  `tests/web/test_routes/test_metrics_routes.py` additions): +15 tests.
- T-C.3 (`tests/web/test_view_models/test_deviation_outcome_vm.py` +
  route additions): +16 tests.
- T-C.4 (`tests/integration/test_phase10_bundle_c_e2e.py`): +4 tests.
- T-C.5 (`tests/metrics/test_cohort_filter.py`): +14 tests.
- R1 Major #1 + #2 follow-up regressions (in `test_phase10_bundle_c_e2e.py`): **+4 tests**
  (2 toggle-href + 2 exact-percent-substring discriminating regressions).

### §3.2 Ruff baseline

**Unchanged at 18 (E501-only)** before AND after R1 ruff sweep at T-C.4.
T-C.4 commit also cleaned 3 SIM114 + 2 F401 + 1 N806 violations that
crept in across T-C.1..T-C.3; net delta is 0.

### §3.3 verify_phase10.py

Exits 0; OK message reported.

### §3.4 Schema version

`EXPECTED_SCHEMA_VERSION` remains at 17. No migrations added; no ALTERs.
Per plan §A.0 LOCK + §I.1 BINDING preserved.

---

## §4 Operator-witnessed verification surfaces

**PENDING orchestrator-driven gate.**

- **S1 (inline)** — pytest fast-suite + ruff + `verify_phase10.py`:
  - `python -m pytest -m "not slow" -q`: 3041 passed + 6 skipped + 3
    pre-existing failures (`test_phase8_pipeline_walkthrough.py` —
    "archive returned None" family; NOT Sub-bundle C regressions per
    dispatch brief §0.4).
  - `ruff check swing/ --statistics`: 18 E501 (baseline unchanged).
  - `python verify_phase10.py`: exit 0.
  - **PASS** (inline).
- **S2 (browser, orchestrator-driven via Chrome MCP on port 8081)** —
  `GET /metrics/tier-comparison`: 4-cohort side-by-side table; n=0
  cohort cells suppressed; `cohort_ci_overlap_descriptor` rendered as
  the suppression placeholder text; relative-to-A+ row shows "—" for
  all cohorts; base-layout integration intact.
  **PENDING.**
- **S3 (browser, orchestrator-driven via Chrome MCP)** —
  `GET /metrics/deviation-outcome`: 4-cohort rows; each row shows
  doctrine_deviation_class enum + decision-criterion seed text verbatim
  + "n too low" placeholder for relative-pct cells at our current state.
  **PENDING.**
- **S4 (browser, orchestrator-driven via Chrome MCP)** — T-C.5 toggle
  on both surfaces: navigate without filter → click "Hide trades with
  unresolved discrepancies" → URL becomes `?exclude_discrepancies=1` →
  cohort denominators ≤ baseline (zero excluded if all production
  discrepancies are resolved); repeat for deviation-outcome.
  **PENDING.**

S2 + S3 + S4 = 3 browser surfaces + S1 inline = 4 total gate surfaces.
Under the ≤6-surface budget (dispatch brief §2 + §1.3).

---

## §5 Per-task deviations from the plan (with rationale)

### 5.1 T-C.1 `cohort_relative_to_aplus` rendering unit (vs spec §3.3 definition)

**Spec §3.3 row 147** defines `cohort_relative_to_aplus` as
`cohort_expectancy_R / aplus_expectancy_R - 1` (delta proportion;
e.g., 0.25/2.0 - 1 = -0.875 = -87.5%).

**Dispatch brief §0.9 LOCK** specifies: render as PERCENT raw-ratio
`cohort_expectancy / aplus_expectancy * 100` (e.g., 25.0 for
0.5R/2.0R = 25% of A+ baseline).

**Implementation followed the brief LOCK.** Brief is the normative
implementer-facing artifact per dispatch brief §0.3 + §0.9; spec text
is a V2.1 §VII.F amendment candidate.

**Banked as V2.1 §VII.F amendment candidate.** Two semantically
distinct metrics exist at the same numeric value: `cohort_relative_to_aplus_pct`
(§3.3) is "what fraction of A+ does this cohort achieve?" (range
0–200% typically); `cohort_expectancy_relative_to_aplus_pct` (§3.7) is
"how far above/below A+ is this cohort?" (range -100% to +∞%). Spec
§3.7 says the §3.7 field "= `cohort_relative_to_aplus` from §3.3,
surfaced here as deviation-outcome lens" but the brief makes them
distinct. Implementation respects the brief; spec text amendment
needed to clarify the two-rendering-semantics split.

### 5.2 T-C.1 `cohort_doctrine_deviation_class` baseline enum value

**Spec §3.7 row 205** uses `0` as the baseline cohort's deviation
class ("A+ baseline = 0"). The other 3 values are descriptive
strings (`missing_proximity_20ma`, etc.).

**Implementation uses the string `"baseline"` instead of `"0"`** for
the A+ row. Rationale: the field is rendered as text in the
deviation-outcome surface; integer `0` would visually collide with
the spec's distinction between the descriptive enum strings + the
operator's mental model that the baseline IS a class label not a
numeric "zero deviation" metric. Test
`test_doctrine_deviation_class_mapping_per_spec_3_7` pins the
string `"baseline"` for A+.

**Banked as V2.1 §VII.F amendment candidate** (cosmetic spec-text
amendment; "baseline" vs "0" is a label choice with operator-visibility
implications).

### 5.3 T-C.5 `resolution IS NULL` (amendment text) vs `resolution = 'unresolved'` (schema)

**Electives amendment §2 Task C.5 acceptance** specifies the filter
helper's SQL predicate as `resolution IS NULL` — but the Phase 9
schema (migration 0017) stores `resolution` as **NOT NULL** with the
sentinel string `'unresolved'` as the DEFAULT enum value.

**Implementation uses `resolution = 'unresolved'`** matching
`swing/data/repos/reconciliation.py:list_unresolved_material_for_active_trades`
+ the Phase 9 Sub-bundle B established convention.

**Banked as V2.1 §VII.F amendment candidate** (electives amendment §2
acceptance text wording; the schema reality is unambiguous and matches
the resolution enum CHECK constraint).

### 5.4 T-C.5 filter helper threading (compute vs VM)

**Acceptance amendment §2** specifies `CohortFilter` enum extended OR
new bool param on tier + deviation VMs. **Implementation chose** the
bool param `exclude_unresolved_discrepancies: bool = False` on BOTH
the compute functions (`compute_tier_comparison`, `compute_deviation_outcome`)
AND the VM factories. The filter is applied AT THE COMPUTE LAYER (before
classification) so the surface-locked cohort suppression cascade fires
correctly (filter brings n<5 → cells re-suppress). VM factory threads
the parameter directly without a CohortFilter enum dataclass (simpler;
single bool suffices for V1).

**Banked as V2.1 §VII.F amendment candidate** — minor; aligns with
"new bool param" alternative in the amendment text.

### 5.5 T-C.5 toggle href shape

**Electives amendment §2 acceptance** shows `<a href="/metrics/tier-comparison?exclude_discrepancies=1">`
(absolute path).

**Implementation uses relative query href** `<a href="?exclude_discrepancies=1">`
+ `<a href="?">` per Codex R1 Major #1 fix. Relative form is more
robust under mounted-app / root-path deployments AND matches the
"…?exclude_discrepancies=1" verbatim shape in the amendment text
(the path prefix in the amendment example is illustrative; the binding
shape is the query suffix).

**Banked as V2.1 §VII.F amendment candidate** — minor; amendment text
clarification.

---

## §6 Codex Major findings ACCEPTED with rationale

**None.** All 2 R1 Major + 1 Minor findings RESOLVED in-tree at
commit `ffe916d`. Matches Sub-bundle D + E + Phase 10 Sub-bundle B
clean-record precedent.

Phase 10 arc cumulative ACCEPT-WITH-RATIONALE count (A + B + C):
**ZERO.** Phase 9 arc carried 4 ACCEPT positions (2 A + 1 B + 1 C);
Phase 10 has a cleaner record entering Sub-bundle D.

---

## §7 Watch items for orchestrator (post-Sub-bundle-C-ship)

1. **Operator-witnessed gates S2 + S3 + S4** — 3 browser-side checks
   (orchestrator-driven via Chrome MCP on port 8081 to avoid collision
   with operator's 8080 session). See §4 above.

2. **Cross-bundle pin at T-A.7 (still SKIPPED)** — Sub-bundle C did
   NOT touch the skip on
   `test_existing_dashboard_vm_has_unresolved_material_field`. The
   un-skip lands at T-E.3 retrofit of the 6 existing base-layout VMs.
   Skip remains in place at integration merge.

3. **Sub-VM exclusion-set in `_SUB_VM_EXCLUSIONS`** — Sub-bundle C did
   NOT add new entries (the comment in
   `tests/web/test_view_models/test_base_layout_vm_coverage.py` was
   extended to document this). Reason: cohort-level data lives in
   `swing.metrics.tier.CohortStatistics` / `DeviationOutcomeRow`
   (outside the `swing/web/view_models/metrics/` auto-discovery
   scope); `TierComparisonVM` + `DeviationOutcomeVM` are PAGE VMs
   (extend `BaseLayoutVM` directly).

4. **Spec amendment candidates banked (5 from this dispatch; see §5):**
   - 5.1 `cohort_relative_to_aplus` rendering: spec §3.3 says delta
     proportion; brief §0.9 says raw-ratio percent; implementation
     follows brief.
   - 5.2 `cohort_doctrine_deviation_class` baseline enum: spec says
     `"0"`; implementation says `"baseline"`.
   - 5.3 T-C.5 filter SQL predicate: amendment says `IS NULL`;
     schema reality is `= 'unresolved'`.
   - 5.4 T-C.5 threading: amendment says CohortFilter enum OR bool;
     implementation chose bool throughout.
   - 5.5 T-C.5 toggle href shape: amendment shows absolute path;
     implementation uses relative query form (also addresses Codex R1
     M#1 mount-path concern).

   **Cumulative pending V2.1 §VII.F amendments stand at 17** entering
   Sub-bundle D dispatch (was 12 entering Sub-bundle C per dispatch
   brief §7.4 — Sub-bundle A added 3, Sub-bundle B added 5,
   Sub-bundle C adds 5; Phase 9 left 2).

5. **§3.3 R1 M3 + §3.7 R1 M4 spec LOCKs honored.** Cohort CI overlap
   descriptor is TEXT-only with verbatim format; decision-criterion
   text is seed text verbatim — NO automated evaluation. Codex R1 did
   not flag either lock.

6. **`verify_phase10.py` not extended in this dispatch.** Sub-bundle
   A's verification script covers `/metrics` umbrella + module
   import smoke; the new `/metrics/tier-comparison` and
   `/metrics/deviation-outcome` routes are exercised by route-level
   tests + integration E2E test. Banked as orchestrator-decision: if
   operator wants verify_phase10 extended to assert the new routes
   are registered, Sub-bundle E T-E.4 closer or a polish bundle can
   land it.

7. **Sub-bundle D dispatch dependencies.** No new ones surfaced.
   Sub-bundle D will introduce the first PROVISIONAL/LIVE dynamic
   badge surface (`resolve_live_capital_denominator_dollars`). T-C.5's
   filter helper is reusable on Sub-bundle D surfaces (capital-friction +
   maturity-stage) per the V2 candidate banked in electives amendment
   §7 #1.

8. **Worktree husk teardown.** This dispatch's branch + worktree
   become the 12th ACL-locked husk in the operator cleanup-script
   queue post-merge.

---

## §8 Composition-surface verification via `^def` grep

Per Phase 9 + Sub-bundle A forward-binding lesson #5: surface
enumeration via `^def` grep, not memory.

```
grep -rn "^def " swing/metrics/honesty.py swing/metrics/policy.py \
  swing/metrics/cohort.py swing/metrics/discrepancies.py \
  swing/metrics/process.py swing/metrics/tier.py
```

Sub-bundle A surface (CONSUMED by tier.py):
- `wilson_ci`, `bootstrap_ci_mean`, `suppress_for_n`, `badges_for_n`,
  `render_class_a/b/c/d` (only `wilson_ci` + `bootstrap_ci_mean` +
  `badges_for_n` actually used; surface-locked floor of 5 bypasses
  `render_class_a/b` since tier.py applies its own suppression).
- `read_live_policy`, `read_at_trade_time_policy`,
  `get_trade_policy_id_stamp`.
- `list_closed_trades_for_cohort`.
- `count_unresolved_material`.

Sub-bundle B surface (NOT consumed by tier.py — narrow re-implementation
in `_per_trade_realized_R` matches the
`hypothesis_progress_card._per_trade_net_pnl_and_at_trade_time_policy`
precedent + avoids the heavier process.py dataclass pipeline overkill
for the 2-output cohort-comparison computation).

NEW T-C.5 helper in `swing/metrics/cohort.py`:
`filter_trades_without_unresolved_material_discrepancies`.

NEW T-C.1 publics in `swing/metrics/tier.py`:
`compute_tier_comparison`, `compute_deviation_outcome`,
dataclasses `CohortStatistics`, `TierComparisonResult`,
`DeviationOutcomeRow`, `DeviationOutcomeResult`,
constants `COHORT_MINIMUM_N`, `TAXONOMY_COHORTS`, `APLUS_COHORT`,
`SUB_APLUS_COHORT`, `DOCTRINE_DEVIATION_CLASS`.

NEW T-C.2/T-C.3 VM factories:
`swing.web.view_models.metrics.tier_comparison.build_tier_comparison_vm`,
`swing.web.view_models.metrics.deviation_outcome.build_deviation_outcome_vm`.

NEW route handlers in `swing/web/routes/metrics.py`:
`metrics_tier_comparison` (GET `/metrics/tier-comparison`),
`metrics_deviation_outcome` (GET `/metrics/deviation-outcome`).
Both accept `exclude_discrepancies: int = Query(default=0)`.

---

## §9 Sub-bundle D forward-binding lessons

Per Phase 9 + Phase 10 Sub-bundle A + B + C cumulative learnings, banked
for Sub-bundle D dispatch brief drafting:

**NEW lesson #20 (from R1 Major #2 fix):** Body-wide substring assertion
on metric units is non-discriminating when the page contains seed text
that includes the same unit substring (e.g., decision-criteria seed text
contains literal `%` from "win rate > 30%"). Discriminating-test pattern
for unit-rendering: **seed a specific worked example + assert the EXACT
rendered numeric+unit substring at the cell location, NOT a body-wide
`unit_string in body` check.** Forward-relevance for Sub-bundle D:
capital-friction surfaces will render multiple percent-unit metrics +
PROVISIONAL/LIVE badge text — all should be tested with exact rendered
substrings per worked example.

**NEW lesson #21 (from R1 Major #1 fix):** Toggle / filter links that
modify the current URL's query parameters should use **relative query
hrefs** (`href="?param=value"` to set + `href="?"` to clear) rather
than absolute path hrefs (`href="/path?param=value"`). Relative form
matches the URI spec for query-only references AND survives mounted-app
/ root-path deployments. Forward-relevance for Sub-bundle D: capital-
friction + identification-funnel + maturity-stage surfaces may need
similar per-cohort or per-stage filter toggles. Pattern: `<a href="?key=value">`
+ `<a href="?">`.

**NEW lesson #22 (T-C.5 filter compute-layer vs VM-layer integration):**
Per-cohort filters that affect cell suppression MUST be applied at the
compute layer (before the surface-locked suppression cascade fires).
Applying at VM-layer post-compute would require duplicating the
suppression logic. Discriminating test: seed cohort with N trades where
N>=5 but K trades have the filter-trigger condition; filter-active
should bring cohort to (N-K) AND re-trigger suppression cascade if
(N-K) < surface floor.

(Lessons #1–#19 from prior phases carry forward; documented in
dispatch brief §0.6 + Sub-bundle A + B return reports.)

---

## §10 Plan-text amendments applied in-tree

**None.** Plan §A.7 binding interface was AMENDED during Sub-bundle A
R2 + R3 (added `HonestyBadges.window_not_full_warning` + public
`badges_for_n` + decoupling discipline paragraph). Sub-bundle B
introduced 5 plan-text deviations banked as V2.1 §VII.F amendment
candidates without in-tree plan changes. Sub-bundle C follows the
same pattern: 5 deviations banked at §5 of this return report as V2.1
§VII.F amendment candidates; plan text NOT modified in-tree.

Pattern: orchestrator triages the cumulative V2.1 §VII.F amendment
candidates at Phase 10 closer (Sub-bundle E T-E.4 or post-merge).

---

## §11 Worktree teardown status

**PENDING orchestrator action.** After operator-witnessed S2 + S3 + S4
gates pass + orchestrator merges to main:

- `git branch -d phase10-bundle-C-tier-and-deviation` (delete branch).
- `git worktree remove .worktrees\phase10-bundle-C-tier-and-deviation`
  (12th ACL-locked husk in cleanup-script queue per dispatch brief
  §7.8).

Operator's `.copowers-subagent-active` marker file at repo root
removed by implementer (this session) before signaling orchestrator
per dispatch brief §1.2.

---

*End of Sub-bundle C return report. Sub-bundle D dispatch brief drafting
unblocked post-merge.*
