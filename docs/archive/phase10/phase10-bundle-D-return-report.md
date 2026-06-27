# Phase 10 Sub-bundle D — executing-plans return report

**Branch:** `phase10-bundle-D-capital-maturity-funnel` (worktree at
`.worktrees/phase10-bundle-D-capital-maturity-funnel`).
**Baseline:** `3af36d0` (HEAD of main pre-dispatch-brief; post-Sub-bundle-
C-ship housekeeping).
**Final HEAD pre-return-report:** `8254a3b`.

Sub-bundle D ships the fifth + sixth + seventh operator-visible Phase 10
dashboard surfaces (§4.4 capital-friction + §4.5 maturity-stage + §4.6
identification-vs-trade-funnel). FIRST PROVISIONAL/LIVE dynamic badge
contract dispatch. All 8 tasks (T-D.0..T-D.7) land ZERO new schema;
consume the AMENDED Sub-bundle A interfaces + Sub-bundle B + C
implementation conventions.

---

## §1 Final HEAD + commit count breakdown

11 commits total on top of the dispatch brief commit `d9b1401`:

| Commit  | Task | Shape | Description |
|---------|------|-------|---|
| `4b168b1` | T-D.1 | task-impl | feat(metrics): §3.4 capital-friction computations + dynamic PROVISIONAL contract |
| `bdf6525` | T-D.2 | task-impl | feat(metrics): capital-friction VM + route + template |
| `82c67a4` | T-D.3 | task-impl | feat(metrics): §3.5 maturity-stage computations |
| `fb1b2ff` | T-D.4 | task-impl | feat(metrics): maturity-stage VM + route + template |
| `7a00e54` | T-D.5 | task-impl | feat(metrics): §3.6 identification-vs-trade-funnel computations |
| `d048955` | T-D.6 | task-impl | feat(metrics): identification-funnel VM + route + template |
| `d339919` | T-D.7 | task-impl | chore(metrics): Sub-bundle D integration sweep |
| `b2dc23d` | R1 fix | Codex-fix | fix(phase10-bundle-D): Codex R1 Major #1+#2+#3 + Minor #1+#2 |
| `be343dc` | R2 fix | Codex-fix | fix(phase10-bundle-D): Codex R2 Major #1+#2 + Minor #1+#2 |
| `8254a3b` | R3 fix | Codex-fix | fix(phase10-bundle-D): Codex R3 Minor #1 + #2 (advisory) |
| (this commit) | return-report | docs | docs(phase10): Sub-bundle D return report |

= 7 task-impl + 3 Codex-fix + 1 return-report = 11 commits.

T-D.0 (recon) intentionally has no commit per plan §G (read-only
verification; captured inline in this return-report §1.1).

### §1.1 T-D.0 recon — verified intact

- Sub-bundle A interfaces all present (`honesty.py`, `policy.py`,
  `cohort.py`, `discrepancies.py`, `equity_resolver.py`).
- `resolve_live_capital_denominator_dollars(conn, *, asof_date, at_trade_time_policy)`
  shipped signature takes `at_trade_time_policy` as kwarg (NOT the brief
  §0.5 short signature `(conn, *, asof_date)`); on LIVE returns
  `snapshot.equity_dollars` directly (NOT `max(floor, equity)` as brief
  §0.8 wording incorrectly stated). Plan §A.6 + shipped code are
  authoritative — banked as deviation D1 (see §5).
- `swing/data/repos/account_equity_snapshots.get_latest_snapshot_on_or_before(conn, *, asof_date: str)`
  takes ISO STRING (not `date`); equity_resolver wraps `.isoformat()`.
- `swing/evaluation/criteria/risk_feasibility.py:NAME = "risk_feasibility"`.
- 18 EXPECTED criterion names enumerated from shipped modules
  (`adr/ma_stack_short.STACK_NAME/RISING_NAME/orderliness/prior_trend/
  proximity/pullback/risk_feasibility/tightness/vcp/*trend_template.CHECK_NAMES`).
- `swing/data/repos/daily_management.list_open_position_active_snapshots(conn)`
  shipped + clamped to latest `data_asof_session` per trade.
- `swing/evaluation/dates.last_completed_session(now)` backward-looking.
- `_SUB_VM_EXCLUSIONS` already includes `BaseLayoutVM`, `ConfidenceBadgeVM`,
  `ProvisionalBadgeVM`, `SuppressionRowVM`, `CohortTabVM`, `CohortProgressVM`
  — Sub-bundle D introduces ZERO new sub-VMs ending in `VM` that don't
  extend `BaseLayoutVM`, so NO updates to the exclusion set required.

Production state at dispatch time (per dispatch brief §0.4): 5 open
trades (DHC/YOU/VSAT/CVGI/LAR), active risk_policy_id=5
(`capital_floor_constant_dollars=7500.0`, `scratch_epsilon_R=0.10`), 60+
pipeline_runs. Schema version 17 unchanged.

### §1.2 Schema-table column-name reconciliation

The plan §A.19 SQL examples reference `criterion_results.criterion_name`,
but the actual SQL table is named `candidate_criteria` (migration
0001:48). The column name `criterion_name` matches actual schema.
Implementation uses `candidate_criteria` — banked as plan-text deviation
D2 (see §5).

---

## §2 Codex round chain

**3 rounds → NO_NEW_CRITICAL_MAJOR** convergent tapering. Matches the
heavy-Codex-density end of the dispatch-brief §3 estimate (3-5 rounds).

| Round | Critical | Major | Minor | Verdict |
|---:|---:|---:|---:|---|
| 1 | 0 | 3 | 2 | ISSUES_FOUND |
| 2 | 0 | 2 | 2 | ISSUES_FOUND |
| 3 | 0 | 0 | 2 | **NO_NEW_CRITICAL_MAJOR** |

**ZERO Critical findings entire chain.** **ZERO ACCEPT-WITH-RATIONALE**
— all 5 Major resolved in-tree with discriminating regression tests; the
6 Minor were all addressed too (R1 m#1+m#2 + R2 m#1+m#2 + R3 m#1+m#2 all
fixed). Matches Phase 10 Sub-bundle A + B + C clean record + Phase 9
Sub-bundle D + E clean record. Phase 10 arc cumulative ACCEPT-WITH-
RATIONALE entering E: **ZERO**.

### §2.1 Round 1 — 3 Major + 2 Minor

**R1 Major #1** — PROVISIONAL/LIVE template renders enum label only;
plan §A.6 line 233 requires inline explanatory text:
`"PROVISIONAL: $X,XXX floor used as live-capital fallback (no snapshot ≤
{asof_date})"`. Fixed by adding `format_capital_denominator_badge_text`
helper + `capital_denominator_badge_text` field on all 3 dataclasses
(`CapitalFrictionResult`, `CapitalFrictionTrendPoint`, `MaturityStageRow`)
+ template wiring.

**R1 Major #2** — Trend-window SQL filtered by `data_asof_date` but plan
§G T-D.5 line 1498 + §A.6 line 231 pin `started_ts.date()`. The two
differ on weekend/holiday runs (e.g., a Sat-evening run anchors data on
Fri's session but `started_ts.date() = Sat`). Fixed in both capital-
friction `_list_runs_in_trend_window` and funnel SQL to use
`substr(started_ts, 1, 10) IN (?)` + trade-match query in funnel uses
`started_ts[:10]` (NOT `data_asof_date`). Discriminating regression test
`test_funnel_window_anchors_on_started_ts_not_data_asof_date` seeds a
run with `started_ts` in window + `data_asof_date` outside window;
asserts the run IS included.

**R1 Major #3** — `aplus_take_rate_per_run` clamped to [0, 1] masks
data-quality anomalies. If 3 trades attributed to A+ on a session with
only 2 A+ identifications (operator override, attribution defect), the
honest 1.5 is silenced to 1.0. Fixed: removed the clamp; validator now
permits ≥0 finite values. Discriminating test
`test_aplus_take_rate_not_clamped_at_1_when_anomaly` seeds the worked
example + asserts rate=1.5.

**R1 Minor #1** — Maturity-stage util_pct underreports when
`current_avg_cost` is NULL (entered-no-fill state). Fixed: SELECT
`entry_price` too, use `effective_avg_cost = current_avg_cost if not
None else entry_price` matching capital.py COALESCE pattern.

**R1 Minor #2** — Unparseable historical `data_asof_date` silently falls
back to page-level asof, which may flip the badge LIVE incorrectly.
Fixed: append a suppressed trend point with `current_capital_utilization_pct=
None / heat=None / pressure=None` + page-level denom_dollars/badge —
operator sees the row absence-of-data rather than a misleading badge.

### §2.2 Round 2 — 2 Major + 2 Minor

**R2 Major #1** — Maturity-stage per-row badge_text was attached to
`title="..."` only (hover-only on mouse; mobile + non-mouse fail).
Fixed: moved to VISIBLE muted span `<br><span class="muted"
data-badge-text="row-utilization-{trade_id}">{{ badge_text }}</span>`.

**R2 Major #2** — Capital-friction trend-row badge_text was also `title=`-
only. Fixed identically with `data-badge-text="trend-{run_id}"` marker.

**R2 Minor #1** — Stale dataclass-field comment said `PROPORTION [0, 1]`
after R1 M#3 removed the clamp. Fixed: docstring updated to
`PROPORTION ≥ 0. Values >1.0 are allowed (and NOT clamped) to surface
data-quality / attribution anomalies...`.

**R2 Minor #2** — Badge-text format test used substring containment;
punctuation/ordering drift could pass. Fixed: replaced with EXACT
full-string equality for both PROVISIONAL + LIVE format strings.

### §2.3 Round 3 — 0 Major + 2 Minor (advisory)

**R3 Minor #1** — `compute_capital_friction` latest-run SELECT uses
`ORDER BY started_ts DESC LIMIT 1`. On tied timestamps SQLite picks
arbitrarily. Fixed: added `, id DESC` deterministic tiebreaker.

**R3 Minor #2** — New "not hover-only" route tests pinned only the
page-level marker; trend-row markers had no test. Fixed: new test
`test_capital_friction_trend_row_renders_badge_text_inline` seeds 5
trading-session runs to unsuppress the trend + asserts ≥5
`data-badge-text="trend-..."` markers + no `title=PROVISIONAL...` leak.

---

## §3 Test count + ruff baseline delta

| Metric | Pre-dispatch | Post-dispatch | Delta |
|---|---:|---:|---:|
| Fast tests passing (worktree) | 3045 | **3147** | **+102** |
| Tests skipped | 6 | 6 | 0 |
| Pre-existing failures (`test_phase8_pipeline_walkthrough.py`) | 3 | 3 | 0 (unchanged) |
| Ruff E501 baseline | 18 | 18 | 0 (unchanged) |
| Schema version | 17 | 17 | 0 (§A.0 LOCK preserved) |

**Test runtime:** S1 inline gate ~6:00 wall-clock at 3147 tests (within
the dispatch brief §0.4 projection of 5-6 min). +102 net is at the upper
end of the §0.7 projection (+67..+104) — matches Sub-bundle A + B + C
overshoot precedent. Codex R1+R2+R3 fix commits added ~19 net new tests
on top of the original ~83 task-impl tests = ~102 total.

---

## §4 Operator-witnessed verification surfaces

**S1 (inline)** — PASS: `python -m pytest -m "not slow" -q` GREEN at
3147 fast tests; `ruff check swing/ --statistics` reports 18 E501
baseline unchanged; `python verify_phase10.py` exits 0.

**S2 (browser, `/metrics/capital-friction`)** — **PENDING** orchestrator-
driven Chrome MCP walkthrough on port 8081 per dispatch brief §2.
Expected acceptance per S2: (a) page 200; (b) PROVISIONAL badge text
inline (`data-badge-text="capital-denominator"` marker); (c) risk-
feasibility_blocked_rate § A.19 render; (d) multi-run trend suppressed
(production has many sessions; if ≥5 trading sessions of completed
pipeline_runs exist, trend renders + §A.0.1 footnote verbatim); (e)
base-layout integration intact; (f) no console errors.

**S3 (browser, `/metrics/maturity-stage`)** — **PENDING** orchestrator
walkthrough. Expected: (a) page 200; (b) 5 open positions (DHC/YOU/
VSAT/CVGI/LAR) render as per-position rows; (c) NULL Phase-8-capture-
need cells render `<em>—</em>` placeholder NOT "[Phase 8 capture pending]";
(d) per-row badge_text inline visible; (e) aggregate count by stage.

**S4 (browser, `/metrics/identification-funnel`)** — **PENDING**. Expected:
(a) page 200; (b) per-run rows for recent pipeline_runs (production has
60+); (c) 30-trading-session trend renders (production ≥10 runs); (d)
§A.0.1 footnote verbatim; (e) NO `watch_take_rate` field anywhere.

**S5 (round-trip PROVISIONAL → LIVE)** — **PENDING**. Acceptance via
either `swing account snapshot record` CLI OR orchestrator-driven plain-
chat operator authorization. Production already has snapshots #1+#2
recorded (per dispatch brief §0.4), so the production state may show
LIVE on initial load. To re-test PROVISIONAL: temporarily delete the
most-recent snapshot (gated by operator), reload, verify PROVISIONAL,
re-insert. Alternatively, leave production state untouched + verify the
S5 round-trip via the BINDING integration test
`test_e2e_capital_friction_provisional_to_live_round_trip` in
`tests/integration/test_phase10_bundle_d_e2e.py` which already exercises
this contract end-to-end with a clean DB.

---

## §5 Per-task deviations from the plan + spec amendment candidates

5 new V2.1 §VII.F amendment candidates surfaced this dispatch. Cumulative
pending entering Sub-bundle E: **22** (17 entering D + 5 new from D).

### D1: Dispatch brief §0.8 PROVISIONAL/LIVE math wording incorrect

Brief §0.8 stated `LIVE: denominator = max(capital_floor_constant_dollars,
snapshot.equity_dollars)`. Plan §A.6 line 222 + the shipped
`resolve_live_capital_denominator_dollars` return `snapshot.equity_dollars`
directly (NO max-with-floor). Implementation follows plan + shipped code.
Brief §0.8 should amend to remove the `max()` wording.

**Rationale:** Plan §A.6 is the authoritative interface contract for
Sub-bundle A's shipped helper. The brief author's `max()` was a
restating-error; the shipped code from Sub-bundle A R1 already returns
raw equity_dollars. Implementation cannot diverge from the shipped
helper without an §A amendment.

### D2: Plan §A.19 SQL references `criterion_results.criterion_name`; actual schema is `candidate_criteria`

Plan §A.19 lines 463-490 use `criterion_results cr ON cr.candidate_id ...`
in the worked SQL example. Actual schema table (migration 0001:48) is
`candidate_criteria` with the same column names. Implementation uses
`candidate_criteria`; plan §A.19 should amend to either match the actual
table name OR clarify the example is a logical pseudo-schema.

### D3: Capital-friction trend window inherits the 30-trading-session window from funnel

Plan §G T-D.1 + spec §4.4 do not explicitly pin the multi-run trend
window size for capital-friction (spec §4.4 only specifies "≥5 runs").
Implementation uses the SAME 30-session window as the funnel surface for
operator-readability parity. Banked as plan §G T-D.1 wording amendment
candidate (add explicit window-size lock).

### D4: Maturity-stage row carries `capital_denominator_dollars` field

`MaturityStageRow` dataclass gains both `capital_denominator_dollars: float`
and `capital_denominator_badge_text: str` (per Codex R1 M#1 + R2 M#1
fixes). Plan §G T-D.3 acceptance listed only `position_capital_utilization_pct
(with PROVISIONAL/LIVE per §A.6)` — implementation adds the denominator
value too for template parity with `format_capital_denominator_badge_text`
+ visibility per plan §A.6 line 233 inline-text LOCK. Banked as plan §G
T-D.3 acceptance-criteria amendment candidate.

### D5: `IdentificationFunnelPoint.aplus_take_rate_per_run` is NOT clamped to [0, 1]

Per Codex R1 M#3 fix, the rate is honestly emitted as `aplus_taken /
aplus_id` without bounding. Plan §G T-D.5 + spec §3.6 say "proportion"
which implies [0, 1] in typical reading; the §VII.F amendment would
clarify "≥0; values >1 surface as data-quality anomaly signals (not
clamped)".

---

## §6 Codex Major findings ACCEPTED with rationale (if any)

**NONE.** All 5 Major findings across R1+R2 resolved in-tree with
discriminating regression tests + plan-anchored fixes. Matches Phase 10
A+B+C clean record entering D + Phase 9 D+E clean record.

---

## §7 Watch items for orchestrator (post-Sub-bundle-D-ship)

1. **Operator-witnessed gates S2 + S3 + S4 + S5** — 4 browser-side
   checks (orchestrator-driven via Chrome MCP on port 8081). S5 requires
   either production snapshot manipulation OR can be deferred to the
   integration-test coverage (see §4 S5 note).

2. **Cross-bundle pin at T-A.7** — still SKIPPED with reason naming
   T-E.3 un-skip point. Sub-bundle D did NOT touch the skip.

3. **Sub-VM exclusion-set propagation** — Sub-bundle D introduced ZERO
   new sub-VMs (all 3 new VMs extend `BaseLayoutVM` directly). No
   updates to `_SUB_VM_EXCLUSIONS` required.

4. **Cumulative pending V2.1 §VII.F amendments: 22** (was 17 entering D;
   +5 this dispatch — D1 brief math; D2 plan §A.19 table name; D3
   capital trend window; D4 MaturityStageRow denominator field; D5
   funnel rate ≥0 honest semantics).

5. **§A.6 PROVISIONAL/LIVE FIRST surface CLOSED** — Sub-bundle D is the
   first + ONLY Phase 10 surface to render the dynamic badge. Sub-bundle
   E (process-grade-trend) does NOT reuse the contract.

6. **§A.0.1 historical-disclosure footnote** — shipped on 2 surfaces
   (capital-friction trend + funnel trend). Sub-bundle E
   process-grade-trend MAY need the same footnote if its multi-run
   aggregation also reconstructs from current trade state; verify at E
   dispatch brief drafting time.

7. **`verify_phase10.py`** — UNCHANGED + still PASS. Sub-bundle D did NOT
   extend it (the per-bundle E2E test
   `tests/integration/test_phase10_bundle_d_e2e.py` is picked up
   automatically by verify_phase10's per-bundle loop in step 6).

8. **Test count overshoot** — projected +67..+104; actual +102 (within
   range, upper end). Matches Sub-bundle A overshoot precedent (+128 vs
   +35..+55 projection). Final main-HEAD baseline projection:
   ~3150 fast tests (3147 worktree-side ≈ +2-3 main HEAD difference
   from cross-bundle test discovery).

9. **Worktree husk** — Sub-bundle D teardown will leave ACL-locked husk;
   6th in cleanup-script queue (after 4 Phase 9 husks + Sub-bundle C
   husk). Cleanup-script `-DeregisterFirst` extension deferred
   post-Phase-10 per `phase3e-todo.md` 2026-05-13 entry.

10. **Sub-bundle E dispatch dependencies** — post-Sub-bundle-D-ship the
    next brief drafts Sub-bundle E (Tasks T-E.0..T-E.3 + electives T-E.5
    + T-E.6 + T-E.4 closer per electives amendment). Sub-bundle E closes
    Phase 10.

11. **Sub-bundle D forward-binding lessons** — 4 new lessons for
    Sub-bundle E (see §9 below).

---

## §8 Worktree teardown status

ACL-locked husk EXPECTED at integration merge time. Branch
`phase10-bundle-D-capital-maturity-funnel` will be deleted post-merge;
on-disk husk persists until cleanup-script `-DeregisterFirst` extension
ships (deferred to standalone post-Phase-10 dispatch).

---

## §9 Sub-bundle E forward-binding lessons

4 new lessons surface from this dispatch (cumulative catalog now at
**26** — was 22 entering D):

**#23 (NEW from D R1 M#1):** When a plan §A clause prescribes a verbatim
explanatory text format, the implementation MUST surface that text
through a dedicated dataclass FIELD + template rendering target. Burying
the text in a `title=` attribute fails mobile + non-mouse usage AND
loses the audit-trail intent (operator must see what the system claims
about the denominator). Discriminating-test pattern: assert
`data-{marker}=` substring in body PLUS assert `title="{format_prefix}"`
substring is absent.

**#24 (NEW from D R1 M#2):** Session-anchor read/write mismatch family
extension — when a plan pins per-run aggregation on
`pipeline_runs.started_ts.date()`, the implementation MUST use exactly
that column (NOT `data_asof_date`, NOT `action_session_date`). These
diverge on weekend/holiday runs in ways that silently drop or misbucket
historical data points. Discriminating-test pattern: seed a row with
`started_ts` and `data_asof_date` divergent, assert correct inclusion.

**#25 (NEW from D R1 M#3):** When a metric definition implies a bounded
range ([0, 1] for proportions, ≥0 for counts), the implementation MUST
distinguish between (a) mathematically-bounded cases (e.g.,
`num <= denom` by SQL construction → rate ∈ [0,1] guaranteed) and (b)
two-source aggregates (numerator + denominator independently computed
→ ratio can exceed 1 in anomaly cases). Clamping the latter HIDES
data-quality issues. Pattern: bounded-by-construction → assert bounds;
two-source → allow honest values + add anomaly badge surface.

**#26 (NEW from D R3 m#1):** SQL `ORDER BY` clauses on potentially-tied
columns MUST include a deterministic tiebreaker (typically `id DESC`).
Plan + Codex consistently catch nondeterminism in latest-record queries.

---

## §10 Composition-surface verification via `^def` grep

Per Phase 9 + Sub-bundle A forward-binding lesson #5: grep `^def` in
Sub-bundle D scope to verify no missed composition surfaces.

```text
swing/metrics/capital.py — 9 functions:
  format_capital_denominator_badge_text (NEW — exported helper)
  compute_capital_friction (NEW — public entry point)
  _compute_risk_feasibility_blocked_rate (private)
  _count_concurrent_open_positions, _sum_open_position_exposure_dollars,
  _sum_open_position_heat_dollars, _capital_cycle_time_days,
  _count_open_at_run, _list_runs_in_trend_window (private helpers)

swing/metrics/maturity.py — 4 functions:
  compute_maturity_stage (NEW — public entry point)
  _compute_position_util_pct, _compute_heat_contrib,
  _compute_trail_ma_eligibility (private helpers)

swing/metrics/funnel.py — 3 functions:
  compute_identification_funnel (NEW — public entry point)
  _session_dates_in_window, _compute_per_run_aggregate (private helpers)

swing/web/view_models/metrics/capital_friction.py — 1 function:
  build_capital_friction_vm (factory)

swing/web/view_models/metrics/maturity_stage.py — 1 function:
  build_maturity_stage_vm (factory)

swing/web/view_models/metrics/identification_funnel.py — 1 function:
  build_identification_funnel_vm (factory)

swing/web/routes/metrics.py — 3 NEW route handlers:
  metrics_capital_friction (GET /metrics/capital-friction)
  metrics_maturity_stage (GET /metrics/maturity-stage)
  metrics_identification_funnel (GET /metrics/identification-funnel)
```

All public entry points are surfaced through exactly one VM factory +
one route handler each. No orphan helpers; no duplicate composition
paths.

---

## §11 Plan-text amendments applied in-tree during Codex rounds

**NONE.** Plan §A.6 + §A.19 + §G T-D.5 are LOCKED entering D + remain
LOCKED post-D. All Codex R1 + R2 + R3 fixes were CODE-CONTENT changes
(no plan §A or §G amendments). The 5 spec amendment candidates banked in
§5 are FORWARD-BINDING (route through V2.1 §VII.F at orchestrator
discretion), NOT in-tree plan edits.

Matches Sub-bundle B + C clean record (no in-tree plan amendments;
forward-binding-only). Differs from Sub-bundle A which made in-tree
amendments to plan §A.7 + §D Task A.1 (interface contracts changed
during R2+R3); D's interface contracts inherited from A unchanged.

---

## §12 Aggregate (per-phase progression)

| Sub-bundle | Codex rounds | Task-impl commits | Codex-fix commits | Net new tests | Critical | Major | ACCEPT-WITH-RATIONALE |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 4 | 11 | 3 | +128 | 0 | 3 (all resolved) | 0 |
| B | 2 | 7 | 1 | +73 | 0 | 2 (all resolved) | 0 |
| C | 2 | 5 | 1 | +84 | 0 | 2 (all resolved) | 0 |
| **D** | **3** | **7** | **3** | **+102** | **0** | **5 (all resolved)** | **0** |
| E (pending) | — | — | — | — | — | — | — |

Phase 10 cumulative: 11 Codex rounds across A+B+C+D, +387 cumulative
fast tests (final 3147 worktree-side), **0 Critical** + **12 Major all
resolved**, **0 ACCEPT-WITH-RATIONALE** (cleanest 4-sub-bundle arc
state). Sub-bundle E will close the phase.

---

*End of return report. Sub-bundle D ships ZERO new schema (§A.0 LOCK
preserved), FIRST PROVISIONAL/LIVE dynamic badge contract surface,
§A.0.1 historical-reconstruction disclosure footnote landed on 2 trend
surfaces, §A.19 risk_feasibility_blocked_rate with 9 BINDING
discriminating tests + set-membership guard against missing-or-extra
criterion names, 30-trading-day window off-by-one defense, §A.20 zero-A+
suppression text verbatim, §A.15 session-anchor BINDING (asof_date is
backward-looking last_completed_session(now) per plan + Codex R1 M#2
fix), Phase 8 NULL capture-need rendering ("—" placeholder NOT "[Phase
8 capture pending]"), NO watch_take_rate_per_run per spec §3.6 R1 M#2
LOCK. 3 Codex rounds → NO_NEW_CRITICAL_MAJOR with ZERO ACCEPT-WITH-
RATIONALE. Phase 10 Sub-bundle E executing-plans dispatch UNBLOCKED.*
