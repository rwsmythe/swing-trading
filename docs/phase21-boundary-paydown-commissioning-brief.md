# Commissioning Brief — the Phase-21 boundary paydown queue

**From:** CHARC → the orchestrator. **Authorized:** operator, in-session 2026-08-04 ("commission the boundary queue as briefed").
**Posture:** every item below is ALREADY RULED — this brief binds pointers, gates, cells, and sequencing. It deliberately restates nothing a ruled source owns (the artifact-scale lesson: a brief that re-states invites divergence from what it re-states). **Where this brief and a cited ruling disagree, the ruling governs.**
**Baseline:** main `81d2c95c`+ (Phase 21 closed, v34, suite 10158/7/0).

---

## §0 Sequencing rules

- **Items 1 → 2 run FIRST, in that order** (RD's re-prioritization: a live surface contradicting a shipped governance criterion outranks a disclosed divergence whose ordering surface is correct). Items 3–7 follow at your cadence.
- **Serial is the default.** Parallelism is PERMITTED only with the merge-integration **composition step named as a gate** in your dispatch (harness-architecture §5.1 — three composition-class instances this phase; the rebase/integration step is where they are caught).
- Every arc: the standard machinery — tier `strong` + codex-auto-review on production code, banner + footer assertions per round, merged-head suite published, trailer audit, QA-on-disk before it reaches a director.
- Migration numbers: **next free at AUTHORING time**, re-verified in the worktree. Two collisions this phase; 0035 is presumptively next but never assumed.

## §1 D29 — the four-site `entry_intent` fix (FIRST; live-visible)

**Ruled content:** the D29 register row (`tool-director-context.md` §4, re-scoped 2026-08-04) + RD's ruling `20260804T053603Z`. One change across ALL FOUR readers (`metrics/tier.py`, `web/view_models/metrics/hypothesis_progress_card.py`, `recommendations/hypothesis.py`, `journal/stats.py`) — a partial fix leaves H1 evidence self-contradicting with one unfixed reader driving TRIPWIRES. **The brief's binding design note (RD): each reader's predicate grounds in the RIGHT AUTHORITY** — H1's filter is CRITERION-mandated; H2/H4's follows from the EPOCH CONTRACT — so a future criterion amendment cannot silently change what the journal counts. **Rides with it (RD-ruled):** the `tier.py` stale 0008-seed docstrings (14/353/456) + the preserved-original PROVENANCE-DETAIL render (secondary render, not inline prose). **Acceptance anchor:** `swing hypothesis list` on live v34 reads H1 at **2/20**.
**Tripwire:** none (existing modules, no schema). **Gate:** RD merge-blocking (measurement-path) + an operator glance at the corrected card. **Cell:** implementer-opus-high.

## §2 Sizing-basis — the LIMIT basis lands on the dashboard paths (SECOND)

**Ruled content:** RD `20260804T020619Z` §2 (inherits 07-30 verbatim: sizing basis = the LIMIT, both regimes, applied to `dashboard.py:781/787` + the `build_recommendations` path). **The §D.3 divergence-disclosure machinery comes OUT in the same change** (the note, the `nightly_recommendation_shares` delta render, their tests — a guard outliving its condition once the surfaces agree). Measurement-adjacent care: **its own commit**, the ledger's anchor semantics re-checked; RD traced consumers (no expectancy computation reads `daily_recommendations.shares`).
**Tripwire:** none. **Gate:** RD merge-blocking + operator witness (the nightly share count CHANGES — he sees the new number with the worked case). **Cell:** implementer-opus-high.

## §3 criteria_lapsed — **CHARC §3 ARCHITECTURE PASS: GO**, performed here

**Ruled content:** RD's amendment `20260801T145240Z` — the 5th clear reason with the DIRECTIONAL CONJUNCT (structural-gate failure AND below-pivot-with-widening-shortfall over N consecutive EVALUATED sessions), `risk_feasibility` EXCLUDED, streak-on-the-GATE, N=5 CONFIG-BOUND never hardcoded, precedence `fill > invalidation > criteria_lapsed > horizon`, the off-screen UNVERIFIABLE state with the inverted default + supersede-disable closure, and the measurement disposition (a framework-withdrawn mandate: its own disposition, excluded from discipline AND away rates).
**The pass (binding conditions — CONDITION 1 WITHDRAWN 2026-08-05, orchestrator-challenged and CHARC-verified on disk):**
1. **NO TRIPWIRE.** The original condition declared a `LATCH_CLEAR_REASONS` CHECK-widening tripwire — **wrong: `clear_reason` is NEVER PERSISTED.** Verified four ways (zero migration mentions; no live column; `Latch.clear_reason` is a dataclass field validated in memory at `models.py:173`; latches are DERIVED at read time — the only latch tables are `latch_view_events` and `latch_order_intents`, neither carrying a reason). `LATCH_CLEAR_REASONS` is a pure Python frozenset (`constants.py:123`) with no SQL mirror. **No migration, no rebuild, no CHECK — the arc is pure-Python and crosses NO §3 tripwire** (no schema, no new module, no dependency, no process, no carve-out). *The original condition was written from the CHECK-enum-widening class pattern without verifying the mirror existed — asserting schema PRESENCE without the grep, the converse of the §5.7 absence-claim rule, owned by CHARC.*
2. **Gotcha #11 binds in its reduced form — EVERY Python mirror in ONE commit**, and the pattern-grep already found what a name-grep would miss: **at least THREE mirrors** — the `constants.py:123` frozenset · `orders.py:56` `_CRITICAL_STALE_CLEAR_REASONS` (**a DESIGN decision, not a mechanical edit: is `criteria_lapsed` critical-stale? That is RD's severity/measurement call — the PLAN poses it, RD rules at plan review**) · `service.py:48` `_STATE_BY_CLEAR_REASON` (the new reason needs a state mapping — and if it needs a NEW `LATCH_STATES` member, that set's own mirrors join the one-commit sweep). Grep the PATTERN across all of `swing/` before authoring; the enumeration in the plan, not in whoever last grepped.
3. **The FTRE counterexample is QUOTED IN THE PLAN** (RD's own requirement): the rule that would have destroyed the founding case sits beside the rule that replaced it, with the live-row table.
4. The off-screen UNVERIFIABLE state is a CLASSIFICATION/render change, not a schema state, unless the plan shows otherwise — if it needs a column, route BACK for a §3 amendment (the SCHEMA-STOP pattern).
5. The new disposition's bucket exclusions get discriminating tests per the both-halves-pinned standard.
**Phases:** writing-plans (real design surface: the state machine + default inversion — **and the cell holds at opus-xhigh WITHOUT the migration**: the two design questions the premise-check surfaced, the severity classification and the state mapping, add reasoning density rather than removing it) → executing. **Cells:** opus-xhigh planning / opus-high executing. **Gates:** RD merge-blocking (measurement) + operator witness on the latch surface (VSTS is the live worked example).

## §4 The cancel-affordance decoupling + `_PRICE_DP`×4 (PAIRED — both live in `swing/latches`)

**Ruled content:** RD's principle `20260803T110020Z` §3 — **recording an operator action and alarming on a detected problem are different functions; the affordance to record must not be gated on the alarm that detects.** Q1: `PENDING_CANCEL` suppression is correct for the ALARM, backwards for the INTENT affordance. Q2: `ORDER_RESTING_LATCH_CLEARED` must not be the sole route to a cancel row. Design the recording surface off the OPERATOR'S state, not the alarm set. **Riding:** consolidate `_PRICE_DP` to ONE definition (orders.py:40, order_intent.py:501, service.py:41, view_models/latches.py:63) — the quantization-divergence area, single-source per the item-6 lesson.
**Tripwire:** none expected; if the design grows schema, route back. **Gate:** RD (the classification consequences of new cancel rows) + operator witness. **Cell:** implementer-opus-high.

## §5 D31 + A-4 — the entry-date arc (RD's three parts + the dedicated discrepancy type)

**Ruled content:** RD `20260801T145327Z`: (1) mapper takes the EXECUTION timestamp (`execution_legs[].time` — the discrepancy path already reads it correctly); (2) the audited entry-date correction surface (the D19/cash-void precedent: audited override, append-only, reason-required); (3) retro-correct trade 19 to 07-31 under it — resolves all four symptoms, discrepancy 95 then closes HONESTLY (never `mark_unmatched` — it would write a false statement). **A-4 rides:** the dedicated `fills_trades_price_divergence`-class `discrepancy_type` — discrepancy 95 is its live evidence.
**CHARC §3, performed here: A-4 is a CHECK-enum widening → tripwire CROSSED — GO** under the same #11 one-commit + table-rebuild-or-widening conditions as §3 above; the correction surface itself follows the cash-void no-schema precedent unless the plan shows otherwise (SCHEMA-STOP applies). **Sequencing note (RD):** order-independent with D29 EXCEPT both precede any H1-consuming read (September). **Gates:** RD merge-blocking (H1-cohort data correction) + operator witness (the retro-correction of his live trade + discrepancy 95 closing). **Cells:** opus-xhigh planning / opus-high executing (measurement-chain data correction on the live ledger).

## §6 D32 — backups retention (SMALL)

**Ruled content:** the D32 register row. Default the arc-mirror pre-migration backup destination to the BACKUPS directory; one-time **MOVE-THEN-RETAIN** of the three root files (RD's constraint verbatim: distinguish large-and-misplaced from large-and-the-last-copy-of-something; nothing deleted until the retention policy names them). **Tripwire:** none. **Gate:** operator confirm on the moves (his data). **Cell:** implementer-sonnet-high.

## §7 The D9 ambient-state sweep (SCHEDULED at this close, operator-concurred)

**Ruled content:** the D9 register row (five instances; the class = CODE OR TEST coupled to ambient state the repo does not control). **Highest-risk subset ONLY:** grep the boundary CONSTANTS (retention/expiry/staleness windows) and PRODUCTION date/clock boundaries — not all ~90 live-clock files; fix what the triage confirms, freeze-the-clock convention per the D9 fix precedent. Full retrofit stays REJECTED. **Tripwire:** none. **Gate:** standard. **Cell:** implementer-opus-high (the triage is the judgment; the fixes are mechanical).

## §8 NOT in this wave — deferred to Phase-22 scoping (CHARC's §2.3 deliverable, next)

The prescriptiveness audit (one artifact at a time, the discriminating rule) · the D27 provenance arc (+ rung-A EQUALS + `latches.py:1381`) · the Phase-22 demand decomposition (item 1 = knob removal + config-vs-two-sources pin + disclosure-block deletion + the one-cent exemption revisit) · the backup-gate manifest retrofit (18 gates) · the ACKED≠ACTIONED comms fix · 21-F (still blocked on the telemetry contract) · 21-C (deferred behind evidence + the signed L2 diff).

## §8.5 WAVE-CLOSE WARNING-CLEANUP PASS (operator-originated 2026-08-10; RD-inventoried) — RUNS AFTER item 5 + the sweep

**Operator's ask:** a small post-wave pass to *correctly* clear the standing warnings, on his belief that existing tools suffice. **RD's inventory says that holds for everything except two rows, and both are already sequenced to Phase 22** — so the pass is real work with a bounded scope, not a sweep-everything.

| standing warning | route | tool state |
|---|---|---|
| **VSTS latch UNVERIFIABLE** (off-screen since 07-30) | operator DECLINES (the 3a terminal) + cancels the broker buy-stop + logs the cancel | **EXISTING** — 3a + item 4 |
| **discrepancy 95 pending** | item 5's correction surface + the `journal_corrected` close | **IN FLIGHT — not manual cleanup** |
| **AMN latch** (filled → trade 20) | should clear as `fill` in the derivation | **verify at wave close**; no action expected |
| **LQDA stray-order warning** | the §3.5 latch-on-acceptance case — **cannot be correctly cleared by existing tools while the order stays wanted**; persists BY DESIGN until Phase 22 (or the order fills/cancels) | **Phase-22-gated** |
| **trade-20 `entry_intent` NULL** | Demand A — a DELIBERATE null per the operator's 2026-08-10 ruling, not an omission | **Phase-22-gated** |
| `invalid_ohlc` 52 | a watch, not a clearable warning | n/a |

**Binding on the pass when it runs (RD):** clearing VSTS via decline follows the per-latch rule (**R5 — decisions are PER-LATCH, never retroactive**), and the decline's effective session is **server-computed** (flag B, live in item 4's write half). **The cleanup goes THROUGH the surfaces, not around them** — it is exactly the case those rules were built for, and hand-clearing a warning the machinery is meant to clear would waste the machinery and leave the ledger unable to say what happened.

**Why this is written here rather than carried:** it is an operator-originated obligation with no arc, which is the class that cost this project five days on H1 and recurred twice more in this wave. It now has a parent.

## §9 Returns

Per arc: orchestrator QAs on disk, then posts the return to the directors. RD's merge-blocking gates are named per item above; **gate visibility binds** — a held gate is stated, an override is stated in one clause. The operator witnesses are step-by-step per his standing preference.
