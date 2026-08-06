# Plan — Phase-21 boundary paydown item 3: the `criteria_lapsed` latch clear reason

**Status:** WRITING-PLANS deliverable. Plan only; nothing here is implemented.
**Base:** `main` @ `73eccb1d` (worktree `.worktrees/criteria-lapsed-plan`, branch `criteria-lapsed-plan`).
**Ruled content:** RD's amendment `20260801T145240Z-rd-amendment-to-the-latch-posture-i-authore.md`. **RD owns the design; this plan owns how to build it.** Where this plan and the amendment disagree, the amendment governs.
**Architecture pass:** CHARC, `docs/phase21-boundary-paydown-commissioning-brief.md` §3, as amended by `20260805T235402Z` — **condition 1 WITHDRAWN**, conditions 2–5 stand.
**Cells:** planning opus-xhigh (this document) / executing opus-high.
**Gates:** RD merge-blocking (measurement) + operator witness on the latch surface.

> **TWELVE BLOCKING QUESTIONS — the canonical list. Ten must be answered BEFORE TASK 1 (OQ-1, 2, 4, 10-18) and OQ-3 before MERGE — the canonical list, and the ONLY one in this document (§5 Gate 0 and §9 refer to it, they do not restate it):**
>
> | OQ | Question | Ruler | Why it blocks |
> |---|---|---|---|
> | **1** | Is `criteria_lapsed` critical-stale? | RD | it is an EDIT INSIDE Task 1's one-commit sweep |
> | **2** | The state representation (a SCHEMA consequence) | CHARC, RD consulted | it is the `_STATE_BY_CLEAR_REASON` entry in Task 1 |
> | **4** | Must the off-screen decision TERMINATE the latch? | RD | changes what Tasks 5–7 build; **semantic, NOT necessarily schema** |
> | **10** | What makes a widening MATERIAL? | RD | the rule clears a constructive setup without it |
> | **11** | Which bar interval expresses "across the N sessions"? | RD | the two readings give OPPOSITE answers on his own worked case |
> | **12** | **AMENDMENT A** — may 2a become a LIFETIME predicate? | RD | it is a change to HIS conjunct, with a permanent-immunity cost |
> | **13** | **AMENDMENT B** — may the window be required to END AT ITS LOW? | RD | likewise a change to his "has WIDENED" semantics |
> | **14** | Does 2a test the session HIGH or the CLOSE? | RD | a close-based 2a MISSES an intraday pivot cross that would have triggered the mandate |
> | **15** | May an earlier same-session PASS override the latest verified FAIL? | RD | the generous half can make a decaying setup never clear at all |
> | **16** | Does the withdrawal rung sit above or below telemetry health? | RD | rates are invariant; the LABEL is not, and the placement is not forced |
> | **17** | Does an UNVERIFIABLE session PAUSE the streak or BREAK it? | RD | `FAIL / 20 absent runs / FAIL / FAIL` clearing at N=3 is not plainly "N CONSECUTIVE evaluated sessions" |
> | **18** | May an earlier PASS override a LATEST run that did not check the ticker? | RD | it suppresses the UNVERIFIABLE render RD explicitly ruled for off-screen latches |
>
> **OQ-3 (the live-vs-shadow parity window) is the MERGE-STAGE blocker, additional to the twelve above,** — it does not change what is built, but it must be answered before the arc merges, and an earlier draft left it floating outside every gate list.
>
> None is defaulted; the executing arc stops at all TWELVE. **OQ-12 and OQ-13 are on this list because they are the two LARGEST deviations from RD's ruling** — an executor who started without them would be implementing unratified amendments to a director's rule.

---

## §0 The thing to read before anything else

CHARC withdrew the schema tripwire because **`LATCH_CLEAR_REASONS` has no SQL mirror.** That is true, and this plan re-verified it independently (§2).

**But `LATCH_STATES` DOES have a SQL mirror — four `CHECK` enums — and CHARC's condition 2 routes into it.** He wrote: *"if the new reason needs a NEW `LATCH_STATES` member, that set's own mirrors join the same one-commit sweep."* Those mirrors are:

| # | Site | Kind |
|---|---|---|
| 1 | `swing/latches/constants.py:112-115` | the frozenset (canonical) |
| 2 | `swing/latches/models.py:170` | dataclass validator (IMPORTS #1) |
| 3 | `swing/data/models.py:39` | `_LATCH_VIEW_STATES` (IMPORTS #1, `is`-identity pinned) |
| 4 | **`swing/data/migrations/0032_latch_view_telemetry.sql:55-60`** | **TWO SQL `CHECK` enums** |
| 5 | **`swing/data/migrations/0033_latch_order_intents.sql:71-74`** | **TWO SQL `CHECK` enums** |
| 6 | `tests/data/test_migration_0032.py:133` | **exact set equality** `sql_states == LATCH_STATES == set(_LATCH_VIEW_STATES)` |
| 7 | `tests/data/test_migration_0032.py:96-108` | inserts EVERY member through the CHECK |
| 8 | `tests/data/test_migration_0033.py:1291-1292` | CHECK-enum map for both columns |
| 9 | `tests/latches/test_identity.py:66-68` | exact set equality (lock test) |

SQLite cannot `ALTER` a `CHECK`. **So a new `LATCH_STATES` member is a two-table rebuild migration — the §3 tripwire CHARC just withdrew, arriving through the other door.**

Condition 4 cuts both ways, in CHARC's own words: *"if the plan concludes anything here DOES need persistence, that is a genuine schema need and routes back to me."*

**This plan's position:** a new `LATCH_STATES` member is not *required* — §3.6 gives a representation that avoids it and loses no information. But choosing between that representation and the precedent-consistent one is **not this plan's call to default**, because RD's amendment carries a header reading *"OFF-SCREEN IS NOT FAILURE, AND IT NEEDS ITS OWN STATE"*. **OQ-2 is therefore a BLOCKING gate, not a recommendation the executor may proceed past.**

Two related vocabularies were checked for the same trap: `LATCH_DISPOSITIONS` has **no** SQL mirror (the measurement half is pure Python), and `intent_kind` **does** have one (`0033:346`), which is why §3.2 does not invent an intent kind.

---

## §1 The FTRE counterexample — QUOTED VERBATIM (condition 3)

RD's own requirement: *"When it is written, the FTRE counterexample must be quoted in it. A rule that would have destroyed the founding case belongs in the record beside the rule that replaced it — that is the part a future reader needs, not the final formulation."*

Reproduced verbatim from the amendment, section `=== THE TRAP THAT KILLS THE OBVIOUS FIX ===`, including his live-row table. **Preserve-the-quote applies to his worked example the same as to his rulings. If it needs tightening, RD tightens it.**

> === THE TRAP THAT KILLS THE OBVIOUS FIX ===
>
> The obvious repair — "clear after N sessions of failing the A+ gate" — **would have destroyed the founding case.** Measured on the live rows:
>
> | | FTRE (pivot 18.34) | VSTS (pivot 16.90) |
> |---|---|---|
> | fire | aplus, −3.2% | aplus, −7.8% |
> | +1 | watch, −3.3% | watch, −9.2% |
> | +2 | watch, −2.3% | watch, −9.1% |
> | +3 | watch, **+0.8% ABOVE** | watch, −11.7% |
> | +4 | watch, +6.3% above | off-screen |
>
> **FTRE fell out of A+ on 07-20 and stayed `watch` for EIGHT consecutive sessions — while advancing through its pivot and running to 20.70.** A 5-session criteria rule clears it around 07-27, four days before the operator's actual fill. It destroys the exact trade the latch posture exists to protect.
>
> The reason is structural and I should have seen it before proposing the rule: **a name that breaks out and runs MECHANICALLY fails the A+ criteria** — no longer tight, no longer near the 20MA, no longer in a base. **Success and decay are indistinguishable in the criteria.** Only the price trajectory separates them.

### §1.1 RD's table re-derived from the live DB — every cell reproduces

Recorded because a worked example nobody re-derived is a lead, not evidence, and because the executing implementer builds fixtures from these rows. RD tabulated `candidates.close`; so does this table.

FTRE, fire = candidate 11261 on 2026-07-20, pivot 18.34, initial_stop 14.88:

| action session | bucket | `candidates.close` | vs pivot |
|---|---|---|---|
| 2026-07-20 (fire) | aplus | 17.76 | −3.16% |
| 2026-07-21 (+1) | watch | 17.73 | −3.33% |
| 2026-07-22 (+2) | watch | 17.91 | −2.34% |
| 2026-07-23 (+3) | watch | **18.49** | **+0.82% ABOVE** |
| 2026-07-24 (+4) | watch | 19.50 | +6.33% |

VSTS, fire = candidate 11629 on 2026-07-27, pivot 16.90, initial_stop 13.40:

| action session | bucket | `candidates.close` | vs pivot |
|---|---|---|---|
| 2026-07-27 (fire) | aplus | 15.58 | −7.81% |
| 2026-07-28 (+1) | watch | 15.35 | −9.17% |
| 2026-07-29 (+2) | watch | 15.36 | −9.11% |
| 2026-07-30 (+3) | watch | 14.92 | −11.72% |
| 2026-07-31 (+4) | **no candidates row** | — | off-screen |

**Three facts the live rows add that the table does not show. All three change the design.**

1. **FTRE was itself OFF-SCREEN on 2026-07-27 and 2026-07-30.** Runs 126 and 129 evaluated 56 and 61 tickers and neither included FTRE. So the founding case exercises the absent-session rule too, not only the directional conjunct. Under "absent sessions do not advance the streak", FTRE's fifth *evaluated* non-A+ session is 2026-07-28 — which is why RD wrote "clears it around 07-27".
2. **`candidates.close` for action session S is the close of session S−1** (§2.2 query 5). This is decisive for §3.3 and is the reason the two conjuncts are evaluated over different domains rather than joined row-by-row.
3. **FTRE's rows become `bucket='excluded'` from 2026-08-03** — the operator's fill; held tickers are appended as `excluded` with `criteria=()` (`swing/evaluation/orchestration.py:264-280`), carrying ZERO `candidate_criteria` rows.

---

## §2 Premise verification on disk

### §2.1 Code claims

Every claim this plan rests on, grounded before authoring. Line numbers are from `73eccb1d`.

| Claim | Verified how | Result |
|---|---|---|
| `clear_reason` is never persisted | `grep -rn clear_reason swing/data/migrations/*.sql` and across `swing/` | ZERO migration hits. Only `swing/latches/{models,service,orders,classification}.py`, `swing/web/view_models/latches.py:208,718`, `swing/web/templates/latches.html.j2:54-57`. **CHARC's withdrawal confirmed independently.** |
| `LATCH_CLEAR_REASONS` has no SQL mirror | same | Confirmed — pure Python frozenset, `constants.py:123-125`. |
| `LATCH_STATES` HAS a SQL mirror | `grep -rn latch_state swing/data/migrations/*.sql` | **FOUR CHECK enums across 0032 and 0033, plus an exact-set-equality test.** §0. |
| `LATCH_DISPOSITIONS` has no SQL mirror | grep of every disposition value against the migrations | ZERO hits. **The measurement half is pure Python.** |
| `intent_kind` HAS a SQL mirror | `grep -n intent_kind swing/data/migrations/0033*.sql` | `CHECK (intent_kind IN ('place','decline','cancel','attest','validity'))`, `0033:346`. **A new intent kind is schema** — §3.2 designs around it. |
| The beacon can only ever write a LIVE state | `swing/web/routes/latches.py:296-299` builds `live = {latch.identity.candidate_id: latch for latch in derivation.latches if latch.is_live}`; `:349-353` builds `matched` by intersecting the payload ids with `live`; `:358-363` iterates `matched` calling `record_view(..., latch_state=latch.state, ...)`. **The chain is closed: `record_view`'s `latch_state` can only be `armed` or `order_resting`, so a terminal state is unwritable by the production writer.** Bears on OQ-2 option A′. |
| The 0033 `latch_state` CHECK carries the SAME six values as 0032 | `swing/data/migrations/0033_latch_order_intents.sql:71-76` — `CHECK (latch_state_at_first_view IN ('armed','order_resting','filled','invalidated','horizon_expired','superseded'))` and the same for `_at_last_view`; `tests/data/test_migration_0033.py:1283-1292` imports `LATCH_STATES` and maps both columns to it in its CHECK-enum table | So a new member requires editing FOUR CHECK clauses across TWO migrations plus their tests — the §0 count is exact, not an estimate. |
| Per-criterion results are persisted | `0001_phase1_initial.sql:48-56` + live query | `candidate_criteria(candidate_id, criterion_name, layer, result, ...)`, `layer IN ('trend_template','vcp','risk')`. **The structural gate is recomputable with the risk layer excluded — no schema, no re-fetch.** |
| **The roster is NOT schema-enforced** | PK is `(candidate_id, criterion_name)`; no roster constraint exists | **A partial criterion set is representable.** §3.1 therefore validates the roster explicitly rather than assuming completeness. |
| `excluded` / `error` rows carry no criteria | `swing/evaluation/orchestration.py:274-293` | Both synthesize `Candidate(..., criteria=())`. Zero rows ⟹ not structurally evaluated — but **NOT the converse** (see the roster row above). |
| The A+ gate's shape | `swing/evaluation/scoring.py:13-39` | risk is a hard pre-filter → `skip`; then the TT gate; then `vcp_fails == 0 → aplus`, `≤ 2 → watch`, else `skip`. |
| The frozen "floor" is an (at most) 20-bar Donchian low | `swing/evaluation/evaluator.py:58-60` | `tail = ctx.ohlcv.iloc[-20:] if len(ctx.ohlcv) >= 20 else ctx.ohlcv; pivot = tail["High"].max(); initial_stop = tail["Low"].min()`. **RD's founding premise confirmed in code** — with the precision that on a short history the window is SHORTER than 20 bars, so "20-bar" is an upper bound, not an invariant. |
| `archive_closes` is built AFTER the fold | `swing/latches/service.py:530-543` | Constructed in `derive_latches` after `_fold_ticker` returns. **It CANNOT be an input to the resolver** — §3.3 uses the `bars` list already passed in. |
| The bar window already covers what is needed | `swing/latches/reader.py:461-496` | Bars loaded `[min(anchor, derivation_session), derivation_session]` per ticker. **No new I/O.** |
| A `[latches]` config section is additive | `swing/config.py` `load()` `required_sections` | `latches` not required; the `web`/`classifier`/`archive` pattern applies unchanged. |
| The latch horizon is bound to the shadow entry window | `swing/latches/constants.py:28-42`; `swing/pipeline/runner.py:3074` | `latch_horizon_sessions(cfg) = cfg.pipeline.observe_max_pending_window_sessions` (30), with an explicit docstring warning that a SHORTER live window manufactures a divergence. **An early clear re-opens exactly that window — OQ-3.** |
| A decline does NOT clear a latch | `swing/latches/service.py:225-303`; `classification.py:498-504` | `_resolve_terminal` consumes bars and entry records ONLY; a `decline` intent yields the DISPOSITION `declined` and nothing else. **The latch stays live and fillable.** §3.2 states this rather than assuming otherwise. |

**A NOTE ON EVIDENCE, for a reviewer working from an excerpt bundle rather than the tree.** Every row above was verified against the working tree at `73eccb1d` and each cites the file:line to re-check. A packet of excerpts necessarily carries only what was excerpted, so several premises here — `DailyBar.high` and its validation, `FireRow`'s exact field order, `_FIRE_SQL`'s raw hydration, `evaluation_runs.run_ts` ordering, the non-session-bar filter, and the NYSE-calendar helpers' exact enumeration behaviour — **are stated as verified-on-disk and must be RE-VERIFIED by the executing implementer at Task 0 before any of them is relied on.** That is the standing "the doc is a lead, the code is the evidence" discipline, and it applies to this plan's own premises as much as to anyone else's.

### §2.2 The live-data queries, reproducible

Every live claim in this plan is re-runnable. DB: `%USERPROFILE%/swing-data/swing.db`, opened `mode=ro`.

1. **The FTRE/VSTS candidate series** (§1.1):
   `SELECT e.action_session_date, c.bucket, c.close, c.pivot, c.id FROM candidates c JOIN evaluation_runs e ON e.id=c.evaluation_run_id WHERE c.ticker=? AND e.action_session_date>='2026-07-15' ORDER BY e.action_session_date, e.run_ts`
2. **The fire rows:** `SELECT ticker,bucket,close,pivot,initial_stop FROM candidates WHERE id IN (11261, 11629)` → FTRE `aplus/17.76/18.34/14.88`; VSTS `aplus/15.58/16.90/13.40`.
3. **The run cadence** (proving evaluated ≠ calendar sessions):
   `SELECT action_session_date, id, tickers_evaluated FROM evaluation_runs WHERE action_session_date>='2026-07-27' ORDER BY action_session_date`
   → 07-27/126/56, 07-28/127/60, 07-29/128/61, 07-30/129/61, 07-31/130/62, 08-03/131/64, 08-04/132/61, 08-06/133/67. **There is no 2026-08-05 run at all**, and VSTS appears in none of 130–133.
4. **The roster is stable in practice:** every one of the 11,819 `bucket IN ('aplus','watch','skip')` candidates carries **exactly 18** `candidate_criteria` rows, and a sample of 4,000 shows **one identical roster** (TT1–TT8, the 9 vcp criteria, `risk_feasibility`). So §3.1's roster check costs nothing today and only ever fires on genuinely malformed data.
5. **THE OFFSET — the single most load-bearing live fact in this plan.** Comparing `candidates.close` against `resolve_ohlcv_window(ticker, ..., migrate=False)`:

   | VSTS action session | `candidates.close` | archive bar dated | archive close |
   |---|---|---|---|
   | 2026-07-28 | 15.35 | **2026-07-27** | 15.35 |
   | 2026-07-29 | 15.36 | **2026-07-28** | 15.36 |
   | 2026-07-30 | 14.92 | **2026-07-29** | 14.92 |

   FTRE is identical in shape: the `18.49` that RD tabulates against action session 07-23 is **the archive bar dated 07-22**.

   **On these rows a candidates row stamped action session S carries the close of S−1**, because the nightly runs on the evening of S−1 for the forward-looking action session S (`reader.py:483-486` states the same geometry for fires).

   **THIS IS AN OBSERVATION, NOT AN INVARIANT — AND THAT MAKES THE ARGUMENT STRONGER, NOT WEAKER.** `reader.py:284-293` states plainly that a ticker whose archive lagged the cohort at evaluation time is persisted with an OLDER close under a fresher stamp, so the lag can be TWO OR MORE sessions and is not fixed. There is therefore **no offset at which a verdict/bar join would be correct**: a one-session shift is not a "verdict-aligned" reading, merely a differently-wrong one. **Any rule that joins a criterion verdict to a dated bar is unsound at every offset**, which is why §3.3 contains no join at any offset rather than a corrected one.

### §2.3 Two premises that do NOT match live code — flagged, not worked around

**(a) The dispatch brief's VSTS description is stale.** It says *"VSTS (currently `watch`, ... ~14% below pivot ...)"*. **VSTS has had no `candidates` row since 2026-07-30** (query 3). RD's own amendment says so: *"VSTS produces no candidate row at all"*, *"off the screen entirely"*. **Consequence for the witness (§10): VSTS today demonstrates the OFF-SCREEN UNVERIFIABLE state, not a `criteria_lapsed` clear.** Its streak is frozen at 3 of 5 and has been since 07-30 — the design working correctly, and the more valuable thing to witness, but a different demonstration from the one the brief describes.

**(b) A CROSS-ARC DEPENDENCY ON ITEM 5 OF THIS SAME QUEUE.** Live trade 19 (FTRE) carries `entry_date='2026-07-23'` while its `candidate_id=11852` is the **2026-07-31** candidates row. That is precisely the D31 defect **item 5** exists to retro-correct (brief §5: *"retro-correct trade 19 to 07-31"*). **Item 5 therefore MOVES FTRE's latch fill date, which moves this arc's acceptance fixture.** This plan builds the FTRE fixture on the CORRECTED **2026-07-31** date, which is also what makes RD's "four days before the operator's actual fill" arithmetic come out (streak reaches 5 at 07-28; fill at 07-31). **Flagged to the orchestrator as a composition-gate item (harness-architecture §5.1); not resolved here.**

---

## §3 The design

### §3.1 The A+ STRUCTURAL gate — single-sourced, and roster-validated

RD: *"The name fails the A+ STRUCTURAL gate"*, with *"`risk_feasibility` EXCLUDED"* and *"the streak is on failing the GATE, not on failing one named criterion."*

The gate is `bucket_for` **minus its risk pre-filter**: the TT gate, then `vcp_fails == 0`.

**It must not be written twice.** A second independently-plausible implementation of one rule is the D6/item-6 drift class this phase spent itself fighting (`mandate_limit_price`'s `round` vs `floor`; `_PRICE_DP`×4). So:

```
swing/evaluation/scoring.py            # the ONE authority

@dataclass(frozen=True)
class StructuralInputs:
    """The reduced form BOTH callers can supply.

    The evaluator holds `Result` objects; the latch reader holds
    `candidate_criteria` ROWS. Neither can hand the other its own type, so the
    shared rule is stated over the reduction they can both produce -- one rule,
    two adapters, never two rules.
    """
    tt_pass_count: int
    tt_failed_names: tuple[str, ...]
    vcp_fail_count: int

def structural_inputs_from_results(tt_results, vcp_results) -> StructuralInputs
def structural_gate_passes(inputs: StructuralInputs, config) -> bool
def bucket_for(tt_results, vcp_results, risk_results, config) -> str   # SIGNATURE UNCHANGED
```

`bucket_for` is refactored to compose `structural_gate_passes`, keeping its own risk pre-filter and its own `watch` band. Behaviour-identical, pinned by T2.1.

**The roster check — the reason `structural_inputs_from_rows` can return `None`.**
The schema constrains each ROW's `layer` and `result` but enforces **no roster**: the PK is `(candidate_id, criterion_name)`, so a candidate with three vcp rows is representable. A missing vcp failure would yield `vcp_fail_count == 0` and a **false PASS**; a missing TT pass would yield a **false FAILURE**, and a false failure plus the price conjunct can clear a live mandate. So:

```
swing/evaluation/scoring.py            # beside the gate it protects

EXPECTED_TT_CRITERIA: frozenset[str]    # TT1_above_150_200 ... TT8_rs_rank
EXPECTED_VCP_CRITERIA: frozenset[str]   # the 9 vcp criterion names

swing/latches/reader.py

def structural_inputs_from_rows(rows) -> StructuralInputs | None
    # None (UNVERIFIABLE) when ANY of:
    #   * zero rows                       -- an `excluded`/`error` sentinel
    #   * the TT names present  != EXPECTED_TT_CRITERIA
    #   * the vcp names present != EXPECTED_VCP_CRITERIA
    #   * any `result` outside {'pass','fail','na'}
    #
    # `na` IS A NON-PASS ON **BOTH** LAYERS, and the TT half is stated
    # explicitly because it is the half a reader forgets: shipped `bucket_for`
    # counts `tt_passes` as `r.result == "pass"`, so EVERY non-pass TT result --
    # `fail` AND `na` -- reduces the pass count, while `vcp_fail_count` counts
    # `result in ("fail", "na")`. An adapter that treats TT `na` as neutral can
    # falsely PASS the structural gate. T2.6 covers both layers.
```

**HOW THE ROSTER IS OBTAINED — an EXPLICIT constant plus a DRIFT-PIN TEST, not a runtime derivation.** An earlier draft said "derived from the evaluator's own criterion modules", which is not implementable: `trend_template.evaluate(ctx)` is a RUNTIME call returning a list, there is no static name export, and obtaining names that way would need a constructed `CandidateContext` and risk an import cycle. The workable form is the one this codebase already uses for `DEFAULT_LATCH_HORIZON_SESSIONS` (`constants.py:45-48`, drift-pinned against `PipelineConfig`): **write the roster out once, and pin it with a test that runs a REAL `evaluate_one` and asserts the emitted criterion names equal the constant** (T2.7). A criterion added, renamed or removed then fails that test rather than silently changing a gate. The constant lives in `scoring.py` beside the gate that consumes it, so the latch reader imports the gate and its roster from one module.

Grounded: all 11,819 evaluated rows carry one identical 18-criterion roster (§2.2 query 4), so the check fires only on genuinely malformed data, and it fails in the SAFE direction (UNVERIFIABLE never clears anything).

**Deliberately NOT read: `candidates.bucket`.** A `skip` produced by `risk_feasibility` alone is structurally A+ — the hard pre-filter returns before the TT/vcp tests — so reading the bucket label would let the operator's capital clear his own mandate, the precise thing RD's exclusion forbids. T2.2 discriminates.

### §3.2 The evaluated-session sequence, and the off-screen UNVERIFIABLE state

**The streak's domain is EVALUATED sessions, not calendar sessions.** The live cadence proves the distinction is real: there is no evaluation run for 2026-08-05 at all, and FTRE has no row on 07-27 or 07-30 despite runs existing on both.

Per latch, over `[anchor, min(derivation_session, horizon_expiry)]`, each `evaluation_runs.action_session_date` classifies into exactly one of three:

| Class | Predicate | Effect on the streak |
|---|---|---|
| **PASSED** | **ANY** structurally verifiable row for the session passes the gate | **RESET to 0** |
| **FAILED** | the **LATEST RUN** for the session produced a structurally verifiable row for this ticker, AND it fails the gate | **increment** |
| **UNVERIFIABLE** | everything else | **neither increments nor resets — omitted from the sequence** |

That third row IS RD's inverted default, stated once and applied everywhere: *"absent sessions must NOT count toward the decay streak... But they cannot count as passing either... the framework cannot check a mandate it cannot see, and it must not assert one it never checked."*

**THE TWO PREDICATES ARE DELIBERATELY ASYMMETRIC, AND THE ASYMMETRY IS THE WHOLE POINT.** A session can carry several rows — an ad-hoc `swing eval` after the nightly, or a run in which the ticker became held and was appended as a zero-criteria `excluded` sentinel. Two obvious tie-break rules exist and **each is unsafe in one direction**:

* *"the latest row wins"* — a later SENTINEL erases an earlier real FAILURE (harmless) **but also erases an earlier real PASS**, so the streak fails to reset and the latch moves toward a clear on the strength of a run that never looked at it. **Unsafe.**
* *"the latest VERIFIABLE row wins"* — a real verdict is never discarded, **but a FAILED verdict survives a later run that could not check the ticker**, which is asserting from evidence the most recent word contradicts. **Unsafe in the other direction.**

**AND THE STRICT HALF KEYS ON THE LATEST *RUN*, NOT THE LATEST *ROW* — a distinction an earlier draft missed and which is the ordinary case, not an edge case.** When a 09:00 run records a verifiable failure and an 18:00 run does not carry the ticker AT ALL (it went off-screen), the latest ROW belonging to the ticker is still the 09:00 failure — so a row-keyed rule calls the session FAILED even though the most recent run never checked it. Repeated over N sessions that clears a mandate on stale evidence, which is precisely what the strict half exists to prevent. **FAILED therefore requires the LATEST run for that action session to contain a verifiable failing row for this ticker.** T3.12.

So the rule is split by which direction each answer moves the latch. **PASSED is generous (ANY verifiable pass resets)** because resetting keeps a mandate ALIVE, and a live mandate is the conservative outcome. **FAILED is strict (the LATEST word must be a verified failure)** because incrementing moves the latch toward withdrawal, and withdrawal is the outcome that can destroy a trade. Anything else is UNVERIFIABLE. **Order runs by `(run_ts, evaluation_run_id)`, NOT `(run_ts, candidate_id)`.** The strict half asks which RUN was latest even when that run has NO row for this ticker — and such a run has no `candidate_id` to break a `run_ts` tie, so a candidate-keyed order cannot express the question. `evaluation_run_id` is on every run (and `_FIRE_SQL` already selects it); the schema's `UNIQUE(evaluation_run_id, ticker)` (`0001:41`) means at most one candidate per run per ticker, so `candidate_id` is only ever a within-run detail. T3.14 covers the equal-`run_ts` tie.

> **⚠ THIS ASYMMETRY IS A POLICY THIS PLAN INVENTED, NOT A CONSEQUENCE OF THE RULING — OQ-15, BLOCKING.** RD ruled on ABSENT sessions; he did not rule that an earlier same-session PASS should override the latest verified FAIL. The generous half has a real cost in the other direction: if every date carries an early passing run and a later authoritative failing run, the streak resets forever and an unmistakably decaying setup (`98, 95, 92, 89, 86` under a pivot of 100) **never clears at all**. The same generosity can suppress the UNVERIFIABLE render when the latest run has no usable row but an earlier one passed. The safe-direction argument is genuine but it is an ARGUMENT, and T3.2/T3.10 currently encode it as though it followed from the ruling. **RD rules; the plan recommends and states both costs.**

**THE TWO PREDICATES OVERLAP, SO THE PRECEDENCE IS STATED RATHER THAN LEFT TO THE TABLE'S ROW ORDER.** A session with an earlier verifiable PASS and a later verifiable FAIL satisfies both ("ANY pass" and "the latest row is a verified failure"). **PASSED WINS** — evaluate it first and return. That is the same conservative direction the split itself encodes: a session in which the framework at any point judged the setup structurally sound is not evidence of decay. T3.10 pins it, because a table read top-to-bottom by an implementer who never noticed the overlap would classify it FAILED.

Two consequences worth stating because they are easy to get backwards:

* **A re-confirmation resets the streak for free.** A later `aplus` fire is, by construction, a PASSED session. No special case is needed and none should be written.
* **Excluded-because-held is UNVERIFIABLE, not FAILED.** The moment the operator takes a position his ticker becomes `bucket='excluded'` with no criteria. Counting that as a structural failure would let the framework withdraw a mandate *because he acted on it*. In practice the `fill` clear usually pre-empts it, but the rule must be right independently rather than correct-by-luck through another rule's precedence.

#### The render, and why it is not a `LATCH_STATES` member

RD's section header reads *"OFF-SCREEN IS NOT FAILURE, AND IT NEEDS ITS OWN STATE"*; his body says the latch *"stops rendering as plain `armed` and becomes UNVERIFIABLE — awaiting an affirmative decision, with the default inverted."*

**CHARC has already adjudicated which of those two readings binds.** Condition 4, verbatim: *"The off-screen UNVERIFIABLE state is a CLASSIFICATION/render change, not a schema state, unless the plan shows otherwise — if it needs a column, route BACK for a §3 amendment."* This plan does not re-decide that; it shows the "otherwise" does not arise:

* The latch is **still LIVE and still fillable**, so a terminal state would be a false statement.
* The in-tree precedent is exact: **zone escape is an attribute of `armed`, never a terminal state** (21-A plan §A.7.1; encoded at `view_models/latches.py:597-618`; locked by `tests/latches/test_identity.py:92-97`).
* A new non-terminal `LATCH_STATES` member would be schema (§0).

Mechanically: `_state_label` gains an UNVERIFIABLE composition alongside `IN ZONE` / `OUT OF ZONE`, driven by new `LatchRowVM` fields (§3.2.1).

#### The "affirmative decision" — what V1 can and CANNOT do

**A correction to an earlier draft of this plan, kept visible because the error is instructive.** It is NOT true that the existing `decline` intent "resolves the mandate". Verified at `swing/latches/service.py:225-303`: `_resolve_terminal` consumes **bars and entry records only**. It has no access to `latch_order_intents` and never has. A `decline` produces the measurement disposition `declined` (`classification.py:498-504`) and **nothing else** — after pressing decline the latch remains live, remains fillable, keeps its stale frozen pivot, and can render UNVERIFIABLE again tomorrow.

So the two available shapes are:

* **V1-A (measurement-only) — what this plan can build under its authorization.** The panel surfaces the existing `decline` affordance on an UNVERIFIABLE latch and records his answer in the append-only ledger. The RENDER stops asserting a mandate the framework cannot verify, and his answer is measured. **The limitation, named rather than glossed: this does NOT terminate the latch and does NOT correct the stale pivot.** RD's *"making it a decision point IS the corrective path"* is only partially delivered — the decision is captured; the correction is not applied.
* **V1-B (terminating) — NOT authorized here.** Making the decision actually terminate the latch requires the PURE derivation to consume intents (an architectural change to a function whose purity is a standing lock) and a way to name the resulting terminal — plausibly a new intent kind, which is CHECK-constrained at `0033:346`, i.e. **schema**.

**This is OQ-4, a BLOCKING question.** The plan does not silently ship V1-A as if it satisfied the ruling.

#### The supersede-disable closure — already true, nothing to build

RD: *"off-screen disables SUPERSEDE. A name that cannot re-fire cannot supersede, so its frozen pivot can go stale with no corrective path... Making it a decision point IS the corrective path."*

Read against the code this is an OBSERVATION about existing mechanics, not a rule to implement. Supersede fires in `_fold_ticker` only when a NEW fire row arrives with a different pivot (`service.py:443-452`); off-screen means no fire row, so supersede is already unreachable. **There is nothing to disable.** An implementer who reads this as "add code to suppress supersede when off-screen" would be writing dead code against a condition that cannot occur. The deliverable is the decision point, subject to OQ-4.

### §3.2.1 The UNVERIFIABLE / calibration rulings the executor must NOT invent

**The domain, first, because two different absences are NOT the same fact:**

* **A trading session with NO evaluation run at all is OUTSIDE the domain entirely.** It is not an evaluated session for ANY ticker (live: there is no run for 2026-08-05). It is not counted, not rendered as unchecked, and says nothing about this mandate — the framework was not running, which is a fact about the pipeline, not about the setup.
* **A session WITH a run but no verifiable verdict for this ticker IS UNVERIFIABLE** and DOES count toward the rendered tail. The framework ran and did not check this name. That is the state RD's inverted default is about.

`SessionStructuralVerdict` therefore carries `action_session: date`, `classification: PASSED|FAILED|UNVERIFIABLE`, and `cause: str | None` (`absent` / `sentinel_row` / `incomplete_roster` / `malformed_result`) — the cause is carried so the detail line can explain the tail without the card having to re-derive it.

**THE VERDICT DATA PATH, specified end-to-end** (an earlier draft said `build_latch_derivation` passes the verdicts "through" and left the interface to be invented, even though it decides whether an absent latest run becomes UNVERIFIABLE):

```
reader:  load_session_structural_verdicts(conn, cfg, *, tickers, start, end)
             -> dict[str, tuple[SessionStructuralVerdict, ...]]
         # keyed by TICKER, ordered by action_session ascending, covering EVERY
         # evaluation run in [start, end] -- including runs with NO row for the
         # ticker, which is exactly how an absent latest run becomes an
         # UNVERIFIABLE verdict rather than a silent gap. Per-TICKER, not
         # per-latch: two latches on one ticker with different anchors slice the
         # SAME sequence by their own [anchor, ...] window, so the reader never
         # needs to know about anchors and cannot disagree with itself between
         # two latches.

service: derive_latches(..., structural_verdicts_by_ticker=None,
                        criteria_lapse_sessions=DEFAULT_...,
                        criteria_lapse_min_widening_adr=DEFAULT_...,
                        criteria_lapse_min_widening_pct=DEFAULT_...)
         # FOUR new keyword parameters, all defaulted, so every existing caller
         # and fixture stays valid. `_fold_ticker` receives that ticker's tuple
         # the same way it already receives `bars` and `entries`.
         # verdicts=None or an empty tuple => no lapse is ever resolved (the
         # feature is inert, never a fabricated clear).
```

**THE RENDER DIAGNOSTICS TRAVEL ON `Latch`, NOT RECOMPUTED IN THE VIEW MODEL.** The shipped `Latch` has no streak fields, and Task 7 cannot render what Task 5 does not emit. Recomputing the streak in the VM would be a second implementation of the resolver — the D6/item-6 drift class this arc is already single-sourcing the gate to avoid. So the resolver's working state is surfaced as **trailing defaulted fields on `Latch`**: `lapse_failed_count: int = 0`, `lapse_unchecked_count: int = 0`, `lapse_unverifiable_tail: int = 0`, `directional_evaluable: bool = True`, `directional_block_reason: str | None = None`, **`lapse_failed_sessions: tuple[date, ...] = ()`**, **`lapse_unverifiable_sessions: tuple[date, ...] = ()`** and **`lapse_unverifiable_causes: tuple[str, ...] = ()`**.

**THE TUPLES ARE THE AUTHORITATIVE REPRESENTATION AND EVERY COUNT IS DERIVED FROM THEM IN `__post_init__`** — `lapse_failed_count == len(lapse_failed_sessions)`, `lapse_unchecked_count == len(lapse_unverifiable_sessions)`, `lapse_unverifiable_causes` PARALLEL to `lapse_unverifiable_sessions` (the same parallel-tuple validation `reconfirmation_candidate_ids`/`reconfirmation_sessions` already carries at `models.py:188-191`), and `lapse_unverifiable_tail` equal to the actual UNVERIFIABLE SUFFIX of the merged, chronologically ordered verdict sequence — not merely `<= lapse_unchecked_count`, which permits an arbitrary tail. **Each session tuple must also be STRICTLY ASCENDING (hence unique) and the two tuples DISJOINT** — a session is failed or unverifiable, never both — because without those a `Latch` can name one session twice or claim a tail it does not have, and the card states a false fact with nothing to catch it. **Counts are DERIVED, never accepted:** `__post_init__` REJECTS a caller-supplied count that disagrees with its tuple rather than silently overwriting it, matching the raise-don't-absorb posture the rest of the module takes. T7.12. Without that, a `Latch` could carry "4 failures" while naming two sessions and the card would state a false fact with nothing to catch it — two independent representations of one quantity is the drift class this arc keeps closing elsewhere.

The last two exist because an earlier draft carried only COUNTS, and counts cannot satisfy two things the plan itself requires: §3.2.1 ruling 2 says the detail line explains the tail by CAUSE (`absent` / `sentinel_row` / `incomplete_roster` / `malformed_result`), and witness step 1 requires the card to NAME the sessions that produced VSTS's streak (07-28, 07-29, 07-30). With counts alone Task 7 could satisfy neither without either inventing fields or recomputing the streak in the view — the duplication §3.1 exists to prevent. T7.10 asserts both are rendered.

**`directional_evaluable` IS DEFINED FOR A PARTIAL STREAK, and the definition is the operator-meaningful one:** it answers *"if this streak reached N, COULD the directional test be evaluated?"* — i.e. lifetime-2a coverage is establishable over `[anchor, latest in-domain session]` (archive status `ok`, no gap, no ambiguous duplicate) AND the fire carries a usable `adr_pct`. It is NOT "2b currently holds" (2b is undefined below N) and NOT a prediction. That is what lets T7.3's partial-streak card say `failed 3 of 5 ... directional test NOT EVALUABLE (archive gap 2026-07-24)` truthfully rather than implying a verdict it has not reached. Trailing + defaulted is what keeps every existing `Latch(...)` construction and every fixture valid (the shipped `bars_available` / `bars_through` fields have exactly this shape). The VM READS them; it never derives them.

**THE TWO COUNTS ARE DIFFERENT QUESTIONS AND ARE DEFINED SEPARATELY** (an earlier draft rendered `<u> unchecked` without saying over what interval, which for `PASS / ABSENT / FAIL / ABSENT / FAIL` could plausibly mean 0, 2, or every unchecked run since the anchor):
* **`lapse_unchecked_count`** = UNVERIFIABLE in-domain sessions in the interval **beginning immediately AFTER the last PASSED session** (or at the anchor when there is none) **and ending at the latest in-domain session.** For `PASS / ABSENT / FAIL / ABSENT / FAIL` that is **2**. *An earlier draft said "from the first FAILED session of the streak", which for that same example yields **1** and contradicted both the stated answer and T7.9 — the interval must start where the streak's evidence starts, which is after the last reset, not at its first failure.*
* **`lapse_unverifiable_tail`** = the count of CONSECUTIVE UNVERIFIABLE in-domain sessions at the END of the window. This is what drives the UNVERIFIABLE render (ruling 1). For the example above it is **0** (the latest session is a FAIL).

1. **One UNVERIFIABLE session at the TAIL is enough to render UNVERIFIABLE.** The claim being withheld is "the framework checked this mandate for the session you are about to trade", and one unchecked session falsifies it. The tail is counted over consecutive **in-domain action sessions** (runs that happened), most recent first, and the card names the count.
2. **Every UNVERIFIABLE cause contributes to the displayed tail count** — absent row, sentinel row, incomplete roster, malformed result. They are one class to the operator ("we could not check this"), and splitting them on the card would imply a distinction he cannot act on. The CAUSE is in the detail line.
2a. **AN UNUSABLE PRICE HISTORY IS ITS OWN UNVERIFIABLE, RENDERED SEPARATELY.** The structural half and the directional half can fail independently: the gate can be perfectly checkable while the archive cannot support §3.3's completeness requirement (a gap, or `archive_status == 'unavailable'`). The card must NOT show a complete failed streak beside a plain live status while the directional predicate had no data — that would imply the mandate is one session from withdrawal when in fact it is unwithdrawable. `LatchRowVM` carries `directional_evaluable: bool` + its reason, and the countdown renders `failed <k> of <N>, directional test NOT EVALUABLE (<reason>)` in that state.
3. **The countdown renders on every live latch**, not only UNVERIFIABLE ones — and **it discloses the unchecked sessions rather than implying adjacency**: `failed <k> of <N> checked sessions (<u> unchecked)`. **`k` CAN EXCEED `N` and the card must not print `failed 8 of 5`.** A latch stays live past the threshold whenever 2a or 2b refuses every window — T4.6 constructs exactly that state (eight failures, lifetime 2a permanently blocking) — so once `k >= N` the card switches to **`<k> failures; threshold <N>; directional condition NOT MET`**, naming why it is still armed instead of printing a nonsensical fraction with no explanation. `directional_evaluable` does not cover this: it says the test COULD run, not that it passed. T7.11. The bare form `failed 3 of 5 evaluated sessions` would read as three consecutive sessions when the algorithm skips arbitrarily many UNVERIFIABLE ones in between, so three failures separated by twenty unchecked runs would render identically to three in a row. Making the calibration visible before it bites is the cheapest defence against a wrong N; making the gaps visible is what stops the countdown itself from being a false statement.
4. **UNVERIFIABLE ADDS NO SUPPRESSION OF ITS OWN — and the DECLINE control is INDEPENDENT of the prepared-order form.** Two distinct statements, because an earlier draft ran them together and over-claimed:
   * The prepared-order form's availability is decided ENTIRELY by 21-B's existing rules (`LATCH_ORDER_WITHHELD_REASONS` = `regime_undeterminable` / `sizing_infeasible` / `sizing_degenerate`, `constants.py:432-434`). An off-screen latch with an uncorroborated close may legitimately hit `regime_undeterminable`, and this arc neither changes that nor asserts otherwise. The requirement is only that being UNVERIFIABLE adds NO NEW suppression (T7.4).
   * **The decision (decline) control MUST remain available even when the prepared-order form is withheld.** This is the item-4 principle applied directly — *recording an operator action and alarming on a detected problem are different functions; the affordance to record must not be gated on the alarm that detects* (RD `20260803T110020Z` §3). A latch the framework cannot price is exactly the one whose mandate he most needs to be able to resolve, and gating his answer on the form's availability would re-create the defect item 4 exists to remove, one surface over.
5. **"Default inverted" means exactly this and nothing more:** an unchecked session may not contribute evidence that the mandate is HEALTHY. It never advances the streak, never resets it, and never supports an affirmative render.
6. **A decline does not suppress the UNVERIFIABLE render** under V1-A, because it does not terminate the latch. The card records that a decision exists and shows it; the state is unchanged. (This is the visible face of the V1-A limitation, and it is why OQ-4 is blocking rather than deferred.)
6a. **A TERMINAL IS NOT PERMANENT, BECAUSE THE ARCHIVE IS MUTABLE — and L10 must be read as forbidding a rewrite BY THE RESOLVER, not as promising immutability.** Bounding 2a at the candidate terminal `s` stops a LATER-DATED bar from resurrecting a cleared latch (T4.16), but it cannot stop HISTORY ITSELF from changing: gotcha #26 records that yfinance re-fetches drift historical bars 0.5-3% and that `write_window`'s `drop_duplicates(keep='last')` rewrites them, and a missing bar can be BACKFILLED at any time. So a D3 bar corrected upward to `101` can retroactively disqualify a D5 lapse, and a backfilled D3 can retroactively CREATE one — in both directions changing whether a D6 fill is attributed. **This is inherent to a DERIVED model over a MUTABLE archive and is not fixable inside this arc** (an immutable-archive-snapshot is the standing V2/V3 answer already banked under #26). It is disclosed here, and the claim that lost coverage is "permanently" unestablishable is corrected: it holds only until someone backfills. T4.18.
7. **CHANGING `N` RETROACTIVELY REWRITES HISTORY, AND THAT IS INHERENT, NOT A BUG TO PATCH.** Latches are DERIVED at read time (`build_latch_derivation`), so every past latch is recomputed under the CURRENT config on every render. Raising N can resurrect a previously-lapsed latch; lowering it can withdraw one that used to survive. **The sharp edge:** `_resolve_terminal` counts a fill only when `entry.entry_date <= nonfill.session` (`service.py:301`), so a fill dated AFTER a lapse is not attributed to that latch — meaning **N can flip whether a real position is attributed to its own mandate.** The mitigation is not a mechanism, it is disclosure: N is a deliberate operator/RD calibration, the panel states the N in force, and T5.5 pins the behaviour so a future reader meets it as an asserted fact. Posed to RD as OQ-8.

### §3.3 The directional conjunct

> ### ⚠ THIS SECTION PROPOSES THREE AMENDMENTS TO RD'S RULING. IT DOES NOT IMPLEMENT IT LITERALLY, AND THAT IS A DECISION ONLY RD CAN RATIFY.
>
> RD ruled: *"over N consecutive **evaluated sessions**, BOTH hold: the name fails the A+ structural gate, and the close is BELOW the frozen pivot and the shortfall has WIDENED across the window."*
>
> **Implementing that text literally produces three concrete failures, each demonstrated below on a worked series.** The amendments this section proposes are the minimal changes that refuse each failure — but they are AMENDMENTS, not readings, and an earlier draft of this plan presented two of them as settled design. That was the plan overstepping: **RD owns the semantics of his own conjunct.**
>
> | # | RD's text | Proposed amendment | The failure that forces it | Blocking OQ |
> |---|---|---|---|---|
> | A | conjunct 2 holds "across the window" | **2a becomes a LIFETIME predicate** over `[anchor, s]` rather than over the N-session window | a breakout close AGES OUT of a rolling window, so a stock that broke out and is pulling back clears a few sessions later — the FTRE geometry displaced by a week | **OQ-12** |
| B | "the shortfall has WIDENED" | **the window must also END AT ITS OWN LOW** | a stock that collapsed then rallied 19% off its low (`95.00, 80.00, 85.00, 88.00, 90.00`) satisfies "widened" on the endpoints and clears | **OQ-13** |
| C | (silent on magnitude) | **a materiality FLOOR** | a one-cent "widening" over five sessions (`99.00 … 98.99`) clears a tight consolidation right under the pivot | **OQ-10** |
>
> Each is presented with its counterexample so RD can rule on evidence rather than on assertion. **If he prefers his literal text, the counterexamples are the cost he is accepting, and they should be recorded as such rather than silently engineered away.**



RD: *"The close is BELOW the frozen pivot and the shortfall has WIDENED across the window."* And: *"Conjunct 2 is what makes it safe: FTRE fails it on day 3 (price closed above the pivot); VSTS satisfies it (7.8% → 11.7%, monotone)."*

**THE TWO CONJUNCTS ARE EVALUATED OVER DIFFERENT DOMAINS AND ARE NEVER JOINED ROW-BY-ROW.** §2.2 query 5 is the reason: a candidates row stamped action session S carries the close of **S−1**, so pairing "the verdict for S" with "the archive close dated S" would use tomorrow's price to judge today's verdict — a one-session look-ahead, and gotcha #30 committed inside a rule whose entire safety rests on the price trajectory. The streak counts **evaluated sessions**; the directional test reads **archive bars by their own date**. No bar is ever claimed to be any verdict's input.

**Conjunct 2a — the LIFETIME rule (promoted from a window rule), and it REQUIRES COMPLETE COVERAGE.**

> **For a CANDIDATE lapse window whose last failed session is `s`, `criteria_lapsed` is unavailable if ANY archive close dated in `[anchor, s]` is at or above the latched pivot** (compared at `_PRICE_DP = 2` on both sides)
> **— and 2a may only be ASSERTED when `[anchor, s]` is COMPLETE: `archive_status == ARCHIVE_STATUS_OK` for the ticker AND a bar exists for EVERY NYSE trading session in the range. Otherwise the latch is DIRECTIONALLY UNVERIFIABLE and `criteria_lapsed` is unavailable.**

**THE UPPER BOUND IS THE CANDIDATE TERMINAL `s`, NOT `derivation_session` — AND AN EARLIER DRAFT HAD THAT WRONG IN A WAY THAT BROKE ITS OWN LOCK.** Bounding 2a at "today" means FUTURE evidence can retroactively erase a past terminal: a latch whose D1–D5 closes are `95, 94, 93, 92, 90` lapses on D5, and a D6 close of `105` then makes lifetime-2a fail, **resurrecting a latch that had already cleared — and making a D6 fill attributable to it.** That is precisely the history-rewriting L10 forbids, arriving through the conjunct instead of through the precedence. Evaluating each candidate window's 2a **through that window's own terminal date** makes the answer permanent: once a window qualifies, no later bar can unqualify it. T4.16.

The completeness requirement is not defensive padding — **without it 2a is an argument from silence and the safety guarantee is void.** Concretely, with pivot 100 and five structurally failing sessions whose true closes are `99, 101, 98, 97, 96`, an archive missing the `101` bar leaves the loaded series `99, 98, 97, 96`: no close reaches the pivot, the window ends at its low, and **the rule withdraws the mandate from a stock that DID break out.** 2a's whole claim is "price never traded through the pivot", and a gap cannot support it. This is 21-G's own asymmetry — an absence caused by our ignorance may never license an assertion — and `bar_status_by_ticker` (`ARCHIVE_STATUS_OK` / `_UNAVAILABLE`) already exists and need only be passed down into the fold.

**COMPLETENESS, DEFINED EXECUTABLY** (a safety check whose failure can clear a breakout may not be left to the implementer's judgement): enumerate the NYSE sessions of the closed interval `[anchor, s]` with `swing/evaluation/dates.py`'s `session_offset` + `is_trading_session` — the same helpers `reader.py` and `service.py` already use — and require the SET of session dates present in the eligible bars to EQUAL that enumeration exactly. **Duplicate bars for one date are handled BEFORE any clause reads `B`, and they are not merely "collapsed":** two rows for one date collapse to one ONLY IF THEY AGREE ON EVERY FIELD THE CONJUNCTS READ (to `_PRICE_DP`); any disagreement makes the interval **UNVERIFIABLE**, because the framework cannot say which was that session's bar and `first(B)`, `min(B)` and the widening would all depend on row order. **"Every field the conjuncts read" means the CLOSE and — if OQ-14 selects the HIGH variant — THE HIGH TOO.** A close-only rule is unsafe under OQ-14: two D3 rows both closing `95` but with highs `101` and `99` would collapse silently, and if the `99` row survived, 2a would see no pivot touch and clear a latch whose stop-limit had triggered at `101`. Non-finite values in any read field likewise make the date UNVERIFIABLE. T4.19. Canonicalization happens once, ahead of clauses 1-4, so no clause sees a raw duplicate; non-session bars cannot appear (`reader.py:227-236` already drops them); the upper bound `s ≤ min(bar_bound, horizon_expiry) ≤ derivation_session` is a completed session by construction, so the interval never reaches for a bar that could not exist yet. `archive_status != ok` short-circuits to UNVERIFIABLE before the enumeration.

A window-scoped 2a is likewise unsafe: a breakout close ages OUT of a rolling N-session window, so a stock that broke out successfully and is now pulling back would clear a few sessions later — the FTRE geometry displaced by a week. Once price has traded through the frozen pivot the mandate's premise has been REALIZED: the entry is live as a resting buy-limit at the cap, 21-A's own pullback regime (`expected_mandate_order_type`, `orders.py:109-140`). Withdrawing that would withdraw an entry that is still working.

**The eligible bar set is `_eligible_bars(bars, anchor=draft.anchor, upper=min(bar_bound, draft.horizon_expiry))` — the SAME call the invalidation walk already makes** (`service.py:270-272`). Reusing the expression rather than re-deriving the window makes drift between the two walks unrepresentable.

**Conjunct 2b — the decay test over the streak window.**

**The window, ruled explicitly rather than left to fall out of the code.** `W` = a trailing run of N consecutive FAILED evaluated sessions; `B` = the eligible bars dated in `[first(W), last(W)]`.

> **2b holds iff ALL of:**
> 1. `B` is COMPLETE over `[first(W), last(W)]` — every NYSE session in the span has exactly one canonical bar. (**A separate `len(B) >= 2` clause was drafted and DELETED as unreachable:** with `N >= 2` distinct failed action sessions and complete coverage, `B` necessarily holds at least two session bars, so a fixture with fewer is already incomplete and the guard could never be the reason for a refusal. A test for it would pass under both implementations — the defensive-dead-code class.)
> 2. `last(B).close < first(B).close` — the period ends lower than it began;
> 3. `last(B).close <= min(b.close for b in B)` — the period ENDS AT ITS OWN LOW;
> 4. `first(B).close - last(B).close >= materiality_floor` — **the widening is MATERIAL** (see below).

**THE SCAN ORDER, so the clear date is stable (and so a window that fails now can qualify later).** Walk the failed-session sequence CHRONOLOGICALLY; for each trailing N-failure window in order, test 1–4; **return the EARLIEST qualifying window**, and `lapse_session = last(W)` of that window. This is the only formulation that satisfies both requirements at once: a window failing the conjunct does not end the matter (later windows are still tried — T4.8), and once a window qualifies the answer never moves (re-deriving tomorrow returns the same earliest window — T4.11). "The last N failures" alone would slide the clear date forward every session.

**THE ONE-SESSION QUESTION, ruled, disclosed — AND CONSEQUENTIAL.** `B` spans `[first(W), last(W)]` in BAR dates, while `W` is in ACTION-SESSION dates, and §2.2 query 5 shows those differ by one session. For VSTS's 07-28/29/30 failures, `B` is the bars dated 07-28/29/30 (`15.36, 14.92, 14.59`), whereas RD's table tabulates `15.35, 15.36, 14.92` (the bars dated 07-27/28/29). **The plan takes the bar-dated reading deliberately:** it is a claim about *price action during the period the gate was failing* and asserts nothing about which bar produced which verdict — exactly the provenance claim §2.2 forbids. Shifting `B` back one session to match the verdicts would re-introduce that assertion as an arithmetic assumption.

**The two readings DISAGREE on the motivating case once materiality is applied, so this is not a cosmetic choice.** On VSTS at N=3 with the recommended 1.0×ADR floor of **$0.68** (rounded; `0.6796` unrounded): the bar-dated window widens `15.36 → 14.59` = **$0.77** and CLEARS; the verdict-shifted window widens `15.35 → 14.92` = **$0.43** and does NOT. **Posed as OQ-11, and it is RD's to rule** — it is his trajectory semantics and his worked example. (At the SHIPPED default N=5 VSTS has only three failed sessions and clears under neither reading, so nothing live turns on it today; the fixture and the calibration do.)

* **No division, no percentage.** The pivot is fixed across the window, so "the shortfall widened" is exactly "the close is lower".
* **PRECISION IS STATED FOR EVERY CLAUSE, INCLUDING CLAUSE 4.** All four clauses normalize to `_PRICE_DP = 2` FIRST and compare the normalized values: 2a compares `round(close, 2)` against `round(pivot, 2)`; clauses 2–3 compare rounded closes; **clause 4 ROUNDS THE WIDENING ITSELF — `round(first_close - last_close, _PRICE_DP) >= round(floor, _PRICE_DP)` — rounding AFTER the subtraction, never before.** Rounding each operand first does NOT help and an earlier draft specified exactly that: verified on this box, `round(64.02, 2) - round(61.02, 2)` is still `2.999999999999993`, because rounding a float returns a float, not a decimal. Only `round(64.02 - 61.02, 2)` yields `3.0`. (Integer cents or `Decimal` are equally correct; the point is that the normalization must come after the arithmetic.) Leaving clause 4 unspecified would let a `$2.00` widening the panel displays as exactly `$2.00` evaluate as `1.9999999998` and refuse — or the reverse — flipping a terminal while the card shows equality, which is the price-precision-parity gotcha landing on the one comparison that withdraws a mandate. T4.17 pins the exact-equality boundary in both directions.
* **Clause 3 is load-bearing.** A bare endpoint test clears a stock that collapsed then recovered hard: over `95.00, 80.00, 85.00, 90.00, 94.99` against a pivot of 100, every close is below the pivot and the last is a penny under the first — an endpoint-only rule withdraws the mandate from a name that has rallied 19% off its low and is about to cross the pivot.
* **CLAUSE 4 IS NEW AND IT CLOSES A REAL HOLE.** Without a materiality floor, `99.00, 99.04, 99.03, 99.02, 98.99` against a pivot of 100 satisfies clauses 1–3: nothing reaches the pivot, the window ends at its low, and the "widening" is **one cent over five sessions.** That is a tight consolidation immediately beneath the pivot — the most constructive pre-breakout shape there is — and the rule would withdraw the mandate on the eve of the move. RD's ruling says *"the shortfall has WIDENED"* and does not say by how much, so **a materiality threshold is a genuine gap in the ruling, posed as OQ-10 (BLOCKING), not silently defined as "one rounded cent is enough."**

  **Recommended floor — the LARGER of an ADR-relative and a pivot-relative term:**

  ```
  materiality_floor = max(adr_multiple * (adr_pct / 100) * latched_pivot,
                          min_widening_pct / 100 * latched_pivot)
  ```

  with `adr_pct` from the FIRE's own `candidates` row (a per-row value, already persisted, no #30 exposure), `adr_multiple` defaulting to **1.0** and `min_widening_pct` to **2.0**, both config-bound.

  **BOTH TERMS ARE NECESSARY, AND THE SECOND WAS ADDED BECAUSE AN ADR-ONLY FLOOR STILL CLEARS A CONSTRUCTIVE SETUP.** ADR-scaling is weakest exactly where it matters most — a tight, low-ADR name sitting under its pivot. With a pivot of 100 and an ADR of 0.40%, the series `99.80, 99.90, 99.75, 99.60, 99.30` widens $0.50, clears a $0.40 ADR-only floor, and the panel tells the operator to cancel a sub-1% consolidation the session before it could break to 103. The pivot-relative term makes that floor `$2.00` and refuses. Conversely the ADR term is what stops a 12%-ADR name from lapsing on ordinary noise. Live check: VSTS's floor becomes `max(0.6796, 0.338) = $0.6796` (the ADR term still binds) and its $0.77 widening still clears.

  **Fallback when `adr_pct` is NULL or non-finite:** the latch is DIRECTIONALLY UNVERIFIABLE and does not clear — **never a hard-coded percentage substitute**, because a substitute silently re-introduces the arbitrary threshold this whole clause exists to avoid. T4.15 is built to defeat exactly that shortcut.

  **THE `adr_pct` DATA PATH, specified — "the column exists" does not make a value reachable from a PURE function.** The resolver sees `_Draft`, whose only data is a `FireRow`, and `FireRow` (`models.py:46-80`) carries no `adr_pct`. So: **widen `FireRow` with `adr_pct: float | None = None`** (trailing + defaulted, so every existing construction stays valid — the same shape `pipeline_run_id` already has) and **add `c.adr_pct` to `_FIRE_SQL`** (`reader.py:40-48`), which already SELECTs from `candidates`. `_Draft` reads it through `draft.fire.adr_pct`. **RAW, NOT COERCED, exactly like `pivot`/`initial_stop` at `reader.py:74-75`:** SQLite will hold TEXT in a REAL column, and an eager `float()` here would raise and drop the whole fire, contradicting the reader's degrade-don't-drop contract. The resolver applies the same `_usable_price`-shaped check and treats an unusable value as DIRECTIONALLY UNVERIFIABLE.
* **Not strict monotonicity.** A real decay rarely ticks lower every session, so a monotone rule would approach dead-on-arrival — and a rule that never fires is worse than no rule, because it looks like coverage.

**WHAT THE CONJUNCT DOES AND DOES NOT ELIMINATE — the safety claim, stated honestly.** An earlier draft implied the directional conjunct made the rule safe. It does not, and cannot:

* **ELIMINATED — the FTRE class:** a name whose CLOSE has reached its frozen pivot. Amendment A makes it permanently immune, which is the founding case and the reason the amendment exists. **Under a close-based 2a this does NOT cover an INTRADAY-only cross** (high above the pivot, close below) even though the stop-limit mandate would have triggered — see the OQ-14 box above; the high-based variant closes that gap.
* **REDUCED, NOT ELIMINATED — the "declines then reverses" class.** With pivot 100, ADR 2%, and complete closes `99, 98, 97, 96, 95`, every clause is satisfied: nothing reaches the pivot, the window ends at its low, and the $4.00 widening clears both floor terms. The latch clears on D5 — **and if D6 gaps to 104, a real breakout was withdrawn the session before it happened.** No backward-looking rule can refuse that, because on D5 the series is indistinguishable from genuine decay. The floors move the threshold; they do not remove the class.

**That residual is the irreducible cost of the ruling itself, and it is the strongest argument for OQ-9 (ship report-only first).** The plan states it rather than claiming a safety it cannot deliver.

**Both live cases, re-verified against the archive series (§2.2 query 5):**

| | FTRE (pivot 18.34, anchor 07-20, `adr_pct` 5.122) | VSTS (pivot 16.90, anchor 07-27, `adr_pct` 4.021) |
|---|---|---|
| eligible bars from anchor | 17.73, 17.91, **18.49**, 19.50, 19.52, 19.20, 20.70, … | 15.35, 15.36, 14.92, 14.59, 14.46, 14.27, 14.17 |
| **2a (lifetime, no close ≥ pivot)** | **FAILS at the bar dated 07-22 (18.49 ≥ 18.34)** | holds — nothing reaches 16.90 |
| 2b clauses 2+3 | not reached | with N=3, `B` = 15.36, 14.92, 14.59 → last < first ✓, last is the min ✓ |
| 2b clause 4 (materiality, 1.0×ADR) | not reached | floor **$0.68** (the rounded value the resolver actually compares and the panel can display; unrounded `0.6796`); widening **$0.77** → passes by 13% |
| **verdict** | **NEVER clears by `criteria_lapsed` — the founding case is safe** (permanently, *subject to §3.2.1 ruling 6a: a historical correction to the 07-22 bar could in principle change this, as it could any derived terminal*) | clears at the third failed evaluated session (N=3); does not reach N=5 |

**A calibration fact RD should see before ruling OQ-10:** at the recommended 1.0×ADR the motivating case passes materiality by only 13%. At 1.5×ADR (floor $1.019) **VSTS would NOT clear** — the multiple is therefore a live lever on the very case that produced the amendment, not a formality.

**⚠ 2a IS CLOSE-BASED, SO IT DOES NOT SEE AN INTRADAY PIVOT CROSS — AND THAT MAKES THE "TRADED THROUGH THE PIVOT" JUSTIFICATION NARROWER THAN IT SOUNDS.** The mandate is a GTC **STOP_LIMIT triggered at the frozen pivot** (`constants.py:149-167`), so it fires when price TOUCHES the pivot intraday, not when it closes above it. A session with high `101` and close `99` against a pivot of `100` therefore filled — or could have filled — the operator's resting order, while a close-based 2a sees nothing: with closes `99, 98, 97, 96, 95` every clause passes and the latch clears on D5, **withdrawing a mandate whose order may already have triggered.** So *"once price has traded through the frozen pivot, amendment A makes it permanently immune"* is true ONLY of a close at or above the pivot, and an earlier draft claimed the stronger thing.

**The plan RECOMMENDS that 2a test the session HIGH rather than the close.** `DailyBar` already carries `high` (`models.py:83-98`), so it costs nothing; it is strictly MORE protective; and it matches 2a's actual question — *was the entry trigger reached?* — rather than borrowing the decay conjunct's close semantics. **It does not contradict RD's constraint 6** (*"CLOSES, not intraday touches"*), which governs INVALIDATION — whether a mandate DIED — a different question from whether its ENTRY FIRED. But the tension is close enough that it is **posed as OQ-14 (BLOCKING), not taken.** If RD prefers close-based, the safety claim must be narrowed in the text to "closed at or above" and the intraday case recorded as a known false clear.

**THE TWO COSTS OF AMENDMENT A, both larger than an earlier draft admitted, and both material to RD's OQ-12 ruling:**

1. **One tick above the pivot confers PERMANENT immunity.** A close of `100.01` on an early failed session, followed by `95, 90, 85, 80, 75`, is unmistakable decay that `criteria_lapsed` can never touch — only the horizon removes it. Bounded at 30 sessions, and in the safe direction, but it is a genuine false-negative policy and not a rounding detail.
2. **ONE MISSING ARCHIVE BAR ANYWHERE IN `[anchor, s]` DISABLES THE FEATURE FOR THAT LATCH UNTIL THE BAR IS BACKFILLED** — the interval only grows, so a gap is never outrun; but per §3.2.1 ruling 6a the archive is MUTABLE, so a backfill can restore evaluability (and retroactively create a lapse). "Permanently" would be the wrong word and an earlier draft used it. This is the sharper cost and it is a direct consequence of pairing a lifetime predicate with a completeness requirement. The alternative (window-scoped completeness) re-opens the argument-from-silence hole the requirement exists to close. **Both halves of that trade-off belong to RD at OQ-12**, and the plan does not pretend one is obviously right.

**A named limitation of 2b, stated because RD's wording produces it:** a stock that gaps down and then sits FLAT far below its pivot never satisfies "widened" and never clears. RD's word is *WIDENED*, and this plan will not silently re-engineer his ruling into "below by more than X%". Posed as OQ-7.

### §3.4 N is a calibration, bound to config, never hard-coded

RD: *"N is a CALIBRATION, not a derivation — I would start at 5 evaluated sessions (one full trading week) and bind it to config, never hard-code it. I cannot derive 5 from anything and I would rather say so than dress it up."*

```
swing/config.py

@dataclass(frozen=True)
class LatchesConfig:
    """Latch-derivation calibrations. A latch calibration is not a pipeline
    setting; it gets its own section so `swing config show` names it honestly."""
    criteria_lapse_sessions: int = 5
    # The OQ-10 materiality floor: the LARGER of these two terms (section 3.3).
    criteria_lapse_min_widening_adr: float = 1.0     # x the FIRE's own adr_pct
    criteria_lapse_min_widening_pct: float = 2.0     # % of the latched pivot

    def __post_init__(self) -> None:
        # EXACT int, NOT bool, and >= 2. Each clause closes a way to configure
        # a knob that LOOKS armed and is not:
        #   * `2.5` passes a bare `< 2` check and is then silently truncated by
        #     the derivation's int() -- a config value that does not mean what
        #     it says.
        #   * `True` is an int in Python and passes every numeric comparison.
        #   * N=1 makes conjunct 2b unsatisfiable (first(B) IS last(B)), so the
        #     whole feature is inert with no error anywhere.
        if isinstance(self.criteria_lapse_sessions, bool) or not isinstance(
                self.criteria_lapse_sessions, int):
            raise ValueError("criteria_lapse_sessions must be an int (not bool)")
        if self.criteria_lapse_sessions < 2:
            raise ValueError("criteria_lapse_sessions must be >= 2")
        # FINITE, not merely positive: `inf` passes `> 0` and disables the lapse
        # forever -- silently, which is the shape this project keeps meeting.
        for name in ("criteria_lapse_min_widening_adr",
                     "criteria_lapse_min_widening_pct"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number (not bool)")
            if not math.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"{name} must be finite and > 0")
```

Wired as `latches: LatchesConfig = field(default_factory=LatchesConfig)` on `Config` and `latches=LatchesConfig(**raw.get("latches", {}))` in `load()` — the additive pattern `web`/`classifier`/`archive` already use. `[latches]` is NOT added to `required_sections`, so every existing config file keeps loading.

**Not `PipelineConfig`.** `latch_horizon_sessions(cfg)` reads `cfg.pipeline.observe_max_pending_window_sessions` because it is DERIVED from that quantity for parity — a deliberate binding-at-the-source, not a filing decision. Filing a new independent calibration under `[pipeline]` because a section already exists there is how a config surface stops describing the system.

**The pure derivation takes ALL THREE calibrations as keyword arguments** — `criteria_lapse_sessions`, `criteria_lapse_min_widening_adr`, `criteria_lapse_min_widening_pct` — each with a module-level default (`DEFAULT_CRITERIA_LAPSE_SESSIONS = 5`, `DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR = 1.0`, `DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT = 2.0`) mirroring the dataclass, so every EXISTING direct `derive_latches` caller and fixture stays valid. Each is drift-pinned in the shape of the shipped `test_default_horizon_mirrors_the_pipeline_config_default` (`tests/latches/test_identity.py:83-90`). Production passes all three from `cfg.latches`. **There are TWO materiality knobs, not "the materiality multiple"** — an earlier draft used the singular in three places while the design needs both terms of the `max(...)`, which is exactly how one of them would have been left unplumbed and silently default-only.

### §3.5 Precedence: `fill > invalidation > criteria_lapsed > horizon`

`_resolve_terminal` (`service.py:225-303`) already implements `fill > invalidation > horizon` as: walk for invalidation → else horizon → then compare a fill by date.

**EARLIEST DATE WINS; RANK BREAKS TIES. A NAIVE "CHECK INVALIDATION FIRST" STRUCTURE IS WRONG AND REWRITES HISTORY** — an earlier draft of this plan had it, and the failure is worth recording because it is silent:

> A latch lapses on D5. On D8 the close finally breaks the frozen stop. A resolver that scans the whole eligible bar range for invalidation BEFORE considering the lapse finds D8 and stamps `invalidation/D8` — **retroactively changing a terminal that had already resolved three sessions earlier.** Worse, the fill rung then compares against D8 instead of D5, so a fill on D6 satisfies `entry_date <= nonfill.session` and is attributed to a mandate the framework had already withdrawn — contradicting this plan's own T4.9(d) and T5.5.

A terminal is an event with a DATE; the first one to occur ends the mandate, and nothing later can un-happen it. Rank matters only when two terminals land on the SAME session:

```
inval_session = first eligible bar (anchor..min(bar_bound, horizon_expiry)) closing below the stop
lapse_session = _resolve_criteria_lapse(...)          # NEW, identical bounds

candidates = [("invalidation", inval_session), ("criteria_lapsed", lapse_session)]
candidates = [c for c in candidates if c[1] is not None]
if candidates:
    # EARLIEST DATE FIRST; RANK ONLY BREAKS A TIE (invalidation outranks lapse).
    nonfill = min(candidates, key=lambda c: (c[1], _RANK[c[0]]))
elif sessions_behind(...) >= horizon_sessions:
    nonfill = _Terminal("horizon", draft.horizon_expiry)
```

The horizon stays last: both walks are capped at `horizon_expiry`, so neither can resolve after it, and the horizon applies only when neither fired. The fill rung is UNCHANGED (`entry.entry_date <= nonfill.session`) and now compares against the genuinely earliest terminal.

**T4.9 therefore tests SAME-SESSION collisions AND the later-invalidation case**, because two terminals on different dates pass under either structure and prove nothing.

**The lapse resolution is bounded by `min(bar_bound, horizon_expiry)`, mirroring the invalidation walk's cap verbatim and for the identical reason** (`service.py:263-269`): once the mandate is dead, a later structural failure is not a withdrawal *of it*, and letting one through would overwrite `horizon_expired`, move the clear session forward, and change a stale-order alarm's severity for a mandate that had already lapsed.

`lapse_session` = **the action session of the Nth failed evaluated session in `W`**, i.e. `last(W)` — not the session the derivation happens to run on. The clear must be dated when it happened, or re-deriving next week would move it (T4.9).

**The resolver reads the `bars` list already passed into `_resolve_terminal`, NOT `LatchDerivation.archive_closes`.** The latter is built in `derive_latches` AFTER `_fold_ticker` returns (`service.py:530-543`), so it cannot be an input to the fold. Same data, no new plumbing, and no circular dependency.

**Bound selection:** the lapse uses `bar_bound` (the backward anchor), because it is a judgement about completed sessions' closes and completed evaluation runs. The liveness PROBE therefore cannot see a lapse at the re-fire session itself, consistent with how the probe already treats invalidation (`service.py:246-260`).

### §3.6 The state representation — BLOCKING (OQ-2)

`Latch.__post_init__` requires `state in LATCH_STATES`, `clear_reason in LATCH_CLEAR_REASONS or None`, and **`state in _LIVE_STATES ⟺ clear_reason is None`**. So `criteria_lapsed` needs a NON-LIVE state: one of `filled`, `invalidated`, `horizon_expired`, `superseded`, or a new one.

**Option A — a new `LATCH_STATES` member (`criteria_lapsed`).**
Consistent with the arc's own precedent: `superseded` was made distinct deliberately (`constants.py:116-122` — *"deliberately DISTINCT from `horizon` so 21-B can separate 'unfilled because the setup re-based' from 'unfilled because it went stale'"*). By that reasoning a framework withdrawal deserves its own state, and RD's *"it needs its own state"* may be read as requiring exactly this.
**Cost: a two-table `CHECK` rebuild migration (0032 + 0033, two columns each) — the §3 tripwire.** `superseded` was free because 0032 was being authored at the time. **→ Routes BACK to CHARC under condition 4.**

**Option A′ — a new member, CHECKs untouched, mirror TESTS reframed.**
The beacon can only ever write a LIVE state (§2.1), so a new TERMINAL member is unwritable by the production writer and the CHECK never needs to accept it for correctness. Only the tests force the migration. The honest contract would be a named `LATCH_VIEW_WRITABLE_STATES` (= the live states) that the CHECK mirrors.
**Cost: this WEAKENS a shipped #11 guard**, whose own docstring names the danger (*"a CHECK that ACCEPTS a value the Python validator REJECTS means the DB holds rows the read path cannot hydrate"*). **→ Also routes back.**

**Option B — reuse `horizon_expired` as the state; `criteria_lapsed` is the REASON.**
Zero schema, zero guard-weakening. Justification and cost:

* **No information is lost.** `clear_reason` is a first-class `Latch` field, rendered by the panel (`latches.html.j2:54-57`) and read by every consumer that cares: the stale-order severity (`orders.py:757,777`) and the execution resolver (`classification.py:401`) both key on the REASON. The new disposition (§3.8) keys on it too.
* **`horizon_expired` is the nearest neighbour and adjacent in the precedence ladder** — both are framework-side, non-price, non-action terminations.
* **The card does not lie**, because `_state_label` already branches on a specific case BEFORE the label map — `superseded` at `view_models/latches.py:606-608`. `criteria_lapsed` gets the same treatment: `WITHDRAWN - criteria lapsed on <session>`, never `HORIZON EXPIRED`.
* **The cost, stated:** a consumer reading `latch.state` instead of `latch.clear_reason` conflates the two, and `state` is exposed on the VM (`view_models/latches.py:716`). Mitigation is a test, not a comment (gotcha #31): T1.3 pins the CALLER-SIDE obligation — that the severity path and the execution resolver consult `clear_reason` — rather than merely documenting the conflation.

**This plan does not default.** OQ-2 is answered by CHARC (schema authority) with RD consulted on whether *"it needs its own state"* binds on `LATCH_STATES`. **Task 1 does not start until it is answered**, because Task 1 contains the `_STATE_BY_CLEAR_REASON` entry.

### §3.7 Is `criteria_lapsed` critical-stale? — POSED, NOT DECIDED (OQ-1)

`_CRITICAL_STALE_CLEAR_REASONS = frozenset({"invalidation", "superseded"})` (`orders.py:56`) selects `critical` vs `warning` for the `ORDER_RESTING_LATCH_CLEARED` alarm (`orders.py:776-778`) — the alarm telling the operator to cancel a resting order behind a dead mandate.

CHARC's prior, offered as a prior and explicitly not a ruling: **NOT critical-stale** — `invalidation` and `superseded` mean the mandate is WRONG, whereas `criteria_lapsed` means the framework WITHDREW it; that is RD's own its-own-disposition reasoning applied to severity.

The argument on the other side, so RD rules on both: an order resting behind a withdrawn mandate is just as *outstanding* as one behind an invalidated mandate — the manual duty (cancel it) is identical, and severity here encodes DUTY, not blame.

**The classification drives alarm display, which is RD's channel.** One-line frozenset edit either way, pinned by T1.4 so the answer cannot drift silently.

### §3.8 The measurement disposition — `framework_withdrawn`

RD: *"A `criteria_lapsed` clear is a mandate the FRAMEWORK WITHDREW, not an action the operator declined. It gets its own disposition, excluded from the discipline signal AND from the away rate."*

**All pure Python — `LATCH_DISPOSITIONS` has no SQL mirror (§2.1).**

```
swing/latches/constants.py
LATCH_DISPOSITIONS         += {"framework_withdrawn"}
_ALL_EXCLUDED_DISPOSITIONS += {"framework_withdrawn"}
```

`UNATTRIBUTABLE_DISPOSITIONS` is DERIVED by subtraction (`constants.py:539-543`), so the new disposition lands in `unattributable_r` without a second edit. `_RULED_DISPOSITIONS` is derived too, so `r_bucket_for`'s no-default guard is satisfied automatically and the shipped `_RULED_DISPOSITIONS == LATCH_DISPOSITIONS` conclusion test catches a half-done edit.

**BUT THE DERIVATION DOES NOT MAKE AN OVERLAP UNREPRESENTABLE, and an earlier draft claimed it did.** The subtraction removes only `AWAY_RATE_COUNTED_DISPOSITIONS` and `ATTESTED_AWAY_DISPOSITIONS` — **not `DECISION_DISPOSITIONS`** — so a disposition added to `_ALL_EXCLUDED_DISPOSITIONS` *and* `DECISION_DISPOSITIONS` sits in both, and `r_bucket_for`'s ladder tests unattributable first and silently returns `unattributable_r`. The rate arithmetic then looks correct while the sets are incoherent. **T6.10 asserts pairwise disjointness directly**, because a property this design depends on must be checked, not inferred from the shape of an expression.

That placement delivers RD's requirement, and the arithmetic is checkable:
* **Excluded from the away rate:** `AWAY_RATE_COUNTED_DISPOSITIONS` is `{"away_unseen"}` and nothing else (`constants.py:525`).
* **Excluded from the discipline signal:** `classifiable_fires = decision_r + away_r + attested_away_r` (`classification.py:861`), and `unattributable_r` is in none of them — so it leaves the DENOMINATOR too, the stronger and correct reading of "excluded".
* **`prompt_required` is False** — not in `PROMPT_DISPOSITIONS` (`classification.py:200`), and it must not be: prompting a man to attest about a mandate the system retracted is the purest form of the train-the-dismissal-reflex failure that comment names.

**The classifier rung goes BEFORE rung 6 (actionable views). THREE of its four edges are FORCED; the fourth — whether it sits above or below rung 5 (telemetry health) — is NOT, and is OQ-16.** An earlier draft called the whole placement forced.

* **It must be BELOW rungs 1–3.** Those are operator ground truth. If he placed an order, that stays `accepted` — a later withdrawal cannot retroactively un-decide what he did.
* **BELOW RUNG 5 (telemetry health) IS THE ONE EDGE THAT IS *NOT* FORCED — OQ-16.** With a non-OK beacon a `criteria_lapsed` latch labels `telemetry_unhealthy` rather than `framework_withdrawn`. Both land in `unattributable_r`, so no RATE moves — but the LABEL does, and there is a real argument for the other order: a framework-authored terminal is objective evidence about why the mandate ended, and beacon health has nothing to do with that reason, which is close to RD's own its-own-disposition reasoning. **An earlier draft called the whole placement "forced"; three of its four edges are, and this one is not.** RD rules; a non-OK-health fixture is specified either way (T6.11).
* **It must be BELOW rung 4.** The source states rung 4 is *"THE ONLY ROUTE to `pre_telemetry`"* and that *"nothing may pre-empt a ruling"* (`classification.py:513-522`). Inserting above it would break a stated invariant of RD's own ruled table. Below it, a withdrawn latch in an uncovered window still labels `pre_telemetry` — which is honest and lands in the same bucket.
* **It must be ABOVE rung 6, and ABOVE RUNG 7, and rung 7 is the binding reason.** Above rung 6 prevents `discipline_lapse` — charging the operator for failing to act on an opportunity the system retracted. But **rung 7 is where the requirement actually bites**: a withdrawn latch he never viewed would otherwise fall through to `away_unseen`, which is `away_r` — **inside the away rate RD explicitly excludes it from.** So the placement is derived from the ruling, not chosen. T6.6 discriminates exactly this case.

### §3.9 Non-goals, stated so they are not drifted into

* **The invalidation rule.** The 20-bar Donchian floor stays exactly as it is. RD's amendment diagnoses it; it does not replace it. Base detection is not in scope.
* **The horizon.** `latch_horizon_sessions` is untouched.
* **`bucket_for`'s output.** The §3.1 refactor is behaviour-preserving and pinned as such.
* **The fill ladder, the supersede rule, the open-latch rule, the beacon, the prepared-order form, the parity ledger.** Untouched.
* **`swing/data/` and `swing/trades/`.** No carve-out requested or needed: the new reads are SELECTs from `candidates` / `candidate_criteria` / `evaluation_runs` inside `swing/latches/reader.py`, where the latch arc's I/O already lives.

---

## §4 The #11 one-commit mirror sweep (condition 2)

**Every Python mirror of the latch clear-reason vocabulary lands in ONE commit (Task 1).** The inventory was produced by grepping the VALUES as quoted literals across `swing/`, `tests/`, `scripts/` and `research/` — not the constant NAME, which would have returned only `constants.py` and `models.py` and missed all three that matter.

### §4.1 Clear-reason mirrors — the complete set

| # | Site | Edit | Nature |
|---|---|---|---|
| 1 | `swing/latches/constants.py:123-125` `LATCH_CLEAR_REASONS` | add `"criteria_lapsed"` | canonical |
| 2 | `swing/latches/models.py:173-176` | **none** — imports #1 | derives |
| 3 | `swing/latches/service.py:46-51` `_STATE_BY_CLEAR_REASON` | add the mapping | **BLOCKED on OQ-2** |
| 4 | `swing/latches/orders.py:56` `_CRITICAL_STALE_CLEAR_REASONS` | per RD's OQ-1 ruling | **severity design** |
| 5 | `swing/latches/classification.py:401` `clear_reason == "fill"` | **none** — reviewed, correct | single-value equality; a withdrawal is not a fill |
| 6 | `swing/web/view_models/latches.py:597-618` `_state_label` | add the `criteria_lapsed` branch | render |
| 7 | `swing/web/view_models/latches.py:94-98` `_TERMINAL_STATE_LABELS` | **none** under Option B (#6 pre-empts it, as it does for `superseded`) | render |
| 8 | `swing/web/templates/latches.html.j2:54-57` | **none** — renders `row.clear_reason` verbatim | render |
| 9 | `tests/latches/test_identity.py:69` `test_locked_constants` | update the asserted set | **lock test — same commit** |
| 10 | `tests/latches/test_close_provenance.py:28` | **none** | **inspected**: the vocabulary grep hit is a DOCSTRING mention of "the 21-A `LATCH_STATES` precedent", not a mirror |
| 11 | `docs/rd-state.md:50` | update | doc mirror; reads FALSE after Task 1 |
| 12 | `swing/latches/service.py:239-245` | update | the `_resolve_terminal` docstring describes THREE passes and the precedence `fill > invalidation > horizon`. **Task 5 reverses both** (a fourth terminal; earliest-date-wins with rank as tiebreak). A docstring that survives the change it describes is the D21 decay class. |
| 14 | `swing/latches/constants.py:535-536` | **update** | the comment claims deriving `UNATTRIBUTABLE_DISPOSITIONS` by subtraction makes an overlap *"UNREPRESENTABLE rather than merely tested-against"*. **§3.8 proves that false** (`DECISION_DISPOSITIONS` is not subtracted). Task 6 corrects the comment; adding T6.10 beside a comment that still claims the guarantee would leave the next reader trusting it. |
| 13 | `swing/latches/service.py:479-484` | update | `derive_latches` states that `bar_status_by_ticker` is *"pass-through display/provenance context: the FOLD, the eligible set and `_finalize` do not consult either"*. **Task 5 makes the fold consult it** (2a's completeness gate), so the sentence becomes false. |

**Sites 2, 5, 7, 8 and 10 are listed precisely because they need NO edit.** An inventory that records only what changes cannot be checked by the next reader, and #10 in particular was surfaced by the grep and would otherwise have been silently dropped.

### §4.2 State mirrors — engaged ONLY if OQ-2 resolves to Option A/A′

The nine sites in §0. **Four are SQL `CHECK` enums.** Under Option B none is touched.

### §4.3 Disposition mirrors

| # | Site | Edit |
|---|---|---|
| 1 | `swing/latches/constants.py:455-460` `LATCH_DISPOSITIONS` | add `"framework_withdrawn"` |
| 2 | `swing/latches/constants.py:513-516` `_ALL_EXCLUDED_DISPOSITIONS` | add it |
| 3 | `UNATTRIBUTABLE_DISPOSITIONS`, `_RULED_DISPOSITIONS` | **none** — derived by subtraction |
| 4 | `swing/latches/classification.py:173` validator | **none** — reads #1 |
| 5 | `swing/cli_latches.py:452` | **none** — iterates `sorted(LATCH_DISPOSITIONS)` |
| 6 | `swing/latches/classification.py` `DECISION_SUBKIND` | **none** — keyed on `decision_r` members only |
| 7 | `swing/latches/classification.py:200` `PROMPT_DISPOSITIONS` | **none — and the NON-membership is LOAD-BEARING**, not incidental: §3.8 and T6.8 both depend on `framework_withdrawn` staying out of it, because prompting a man to attest about a mandate the system retracted is the train-the-dismissal-reflex failure that comment names. **Omitted from an earlier draft of this table**, which is exactly the "existence is not completeness" class — a subset the design DEPENDS on being unchanged still belongs in the sweep inventory. |
| 8 | `swing/latches/constants.py` `AWAY_RATE_COUNTED_DISPOSITIONS`, `ATTESTED_AWAY_DISPOSITIONS`, `PENDING_DISPOSITIONS`, `DECISION_DISPOSITIONS` | **none — each non-membership is load-bearing** and is what routes `framework_withdrawn` to `unattributable_r` by subtraction. T6.1's three-way discriminator is the check. |

**Every subset and partition of `LATCH_DISPOSITIONS` is listed above, whether or not it changes** — a disposition's bucket is decided by which sets it is IN and which it is OUT of, so an inventory of only the edited sets cannot be checked. **No site states a cardinality**, matching `constants.py:356-358`.

### §4.4 Vocabularies with SQL mirrors that this arc does NOT widen

Recorded so the next reader does not have to re-derive the negative: `candidates.bucket`, `candidate_criteria.layer`, `candidate_criteria.result` and `candidates.rs_method` all carry `CHECK` enums (`0001_phase1_initial.sql:28,38,51,52`). This arc READS all four and widens none.

---

## §5 Tasks (TDD; one red → green → commit cycle each)

**GATE 0 — the TWELVE blocking questions in the table at the head of this document (OQ-1, 2, 4, 10-18) are ANSWERED — *and answered COMPATIBLY with what this plan designed.***

**"ANSWERED" IS NOT SUFFICIENT, AND THAT IS THE POINT OF THIS PARAGRAPH.** Several questions have answers this plan has NOT designed for, and an executor holding an answer but no design would have to invent policy at exactly the points the questions were raised to protect:
* **OQ-12 rejected** (2a stays window-scoped) contradicts L6, which calls the lifetime property non-negotiable.
* **OQ-13 rejected** (RD prefers his literal "widened", or strict monotone) removes T4.7's subject while L3 marks it non-droppable.
* **OQ-10 rejected** (no materiality floor, or a different form) invalidates the T4 baseline, T4.14 and both config knobs.
* **OQ-4 answered "it must TERMINATE"** needs a terminal reason, intent semantics, a precedence slot and tests — none of which exist here.
* **OQ-15 rejected** inverts §3.2's classification table.
**So Gate 0 has a second condition: if an answer selects a branch this plan did not design, THE PLAN RETURNS FOR REVISION AND RE-APPROVAL before Task 1.** It is cheaper to re-plan than to let an executor improvise a director's semantics. That table is the single canonical statement of what blocks; this line does not restate it.

**THE ORDER BELOW IS CONFIG-BEFORE-EMITTER, DELIBERATELY.** An earlier draft resolved the lapse (Task 4) before wiring `[latches]` (Task 5), which would have left an intermediate production commit deriving `criteria_lapsed` from the module DEFAULT instead of the bound calibration — a live commit violating L5 for the length of one task.

**Task 1 — the vocabulary + EVERY Python mirror, ONE COMMIT (#11).**
`LATCH_CLEAR_REASONS` += `criteria_lapsed`; the `_STATE_BY_CLEAR_REASON` entry per OQ-2; `_CRITICAL_STALE_CLEAR_REASONS` per OQ-1; the `_state_label` branch; `tests/latches/test_identity.py:69`; `docs/rd-state.md:50`. No emitter yet — the value is legal and simply never occurs, so no commit boundary sees an inconsistent vocabulary.
`feat(latches): Task 1 — criteria_lapsed joins the clear-reason vocabulary with every Python mirror`

**Task 2 — single-source the structural gate.** The characterization table FIRST (T2.1, green against the shipped `bucket_for`), then `StructuralInputs` + `structural_inputs_from_results` + `structural_gate_passes` + `EXPECTED_TT_CRITERIA` / `EXPECTED_VCP_CRITERIA` + the roster drift-pin (T2.7), then `bucket_for` refactored to compose them, signature unchanged.
`refactor(evaluation): Task 2 — extract the A+ structural gate as the ONE authority`

**Task 3 — the config calibration (BEFORE any emitter).** `LatchesConfig` (N ≥ 2, plus the OQ-10 materiality multiple) + `Config.latches` + `load()` wiring + `DEFAULT_CRITERIA_LAPSE_SESSIONS` + the mirror-drift test + the `swing.config.toml` `[latches]` block.
`feat(config): Task 3 — criteria_lapse_sessions as a bound calibration, never a literal`

**Task 4 — the reader, STANDING ALONE.** `FireRow.adr_pct` + the `_FIRE_SQL` hydration; `structural_inputs_from_rows` with the roster check; `load_session_structural_verdicts` with the §3.2 asymmetric classification. Read-only SELECTs; malformed rows degrade to UNVERIFIABLE. **It does NOT wire `build_latch_derivation` into `derive_latches`'s new parameters** — those do not exist until Task 5, so wiring here would either call a signature that is not there or force premature service edits, and the task could not be green at its own boundary. Its tests (T3.x) exercise the reader functions directly, which is what makes it a standalone red→green cycle. T3.11 and T3.13, which assert a LAPSE outcome, belong to **Task 5** for the same reason.
`feat(latches): Task 4 — per-session structural verdicts, roster-validated`

**Task 5 — the pure lapse resolution + precedence + THE WIRING.** `_resolve_criteria_lapse` (the chronological earliest-qualifying-window scan); conjuncts 2a/2b over `_eligible_bars` with the completeness requirement; the earliest-date-wins terminal selection; the `min(bar_bound, horizon_expiry)` cap; `bar_status_by_ticker` threaded into the fold; the `Latch` diagnostic fields; **the FOUR new `derive_latches` keyword parameters** — `structural_verdicts_by_ticker` PLUS the three calibrations — each defaulted (§3.2.1); **and only now `build_latch_derivation` passing the reader's verdicts and `cfg.latches` through.** The two service docstrings (§4.1 rows 12-13) are corrected in this task, not left to rot.
`feat(latches): Task 5 — the criteria_lapsed terminal, with the directional conjunct`

**Task 6 — the measurement disposition.** `framework_withdrawn` + bucket membership + **the rung at the placement OQ-16 rules** (the plan's recommendation is between 5 and 6; an above-health answer is a designed alternative, not a re-plan — only the rung's insertion point moves and T6.11 asserts the same rate-invariance either way) + the condition-5 discriminating tests + the `constants.py:535-536` comment correction (§4.1 row 14).
`feat(latches): Task 6 — framework_withdrawn, excluded from the discipline signal and the away rate`

**Task 7 — the UNVERIFIABLE render.** The VM fields (incl. `directional_evaluable`), the `_state_label` composition, the countdown on every live latch, the §3.2.1 rulings.
`feat(web): Task 7 — the off-screen UNVERIFIABLE render and its decision point`

**Then, before the Codex review:** the FULL fast suite to green (recipe §2). `ruff check swing/`.

---

## §6 Tests

Every test is specified so it **FAILS under the wrong behaviour** — the both-halves-pinned standard. Where the discriminator is not self-evident, the value under the wrong implementation is stated.

### T1 — vocabulary
* **T1.1** `LATCH_CLEAR_REASONS == frozenset({"fill","invalidation","horizon","superseded","criteria_lapsed"})`.
* **T1.2** Two assertions, because a membership test alone does not pin a mapping: (a) **iterating** `LATCH_CLEAR_REASONS`, every reason has a `_STATE_BY_CLEAR_REASON` entry whose state is in `LATCH_STATES` and NOT in `_LIVE_STATES` — so a sixth reason gains the test automatically; (b) the **exact literal** `_STATE_BY_CLEAR_REASON["criteria_lapsed"] == "<the OQ-2 answer>"`. **Discriminator:** (a) alone passes if the reason maps to `filled` or `invalidated`.
* **T1.3 — THE CALLER-SIDE OBLIGATION (gotcha #31). CORRECTED: an earlier draft's version could not fail.** Under Option B, `criteria_lapsed` and `horizon` share a `state`, so a discriminating test must find a consumer whose output DIFFERS between them. Two candidates were checked and **only one qualifies**:
  * **The execution resolver does NOT discriminate.** `classification.py:401` keys on `clear_reason == "fill"`; a wrong implementation keyed on `state == "filled"` gives the same answer for both latches, so asserting "not `accepted_by_broker`" passes under the exact defect it claims to catch. **Dropped.**
  * **The severity path discriminates ONLY IF OQ-1 rules `criteria_lapsed` critical-stale.** If it rules NOT critical-stale, both reasons yield `warning` and no discriminator exists there either. **So this half is CONDITIONAL on OQ-1 and is written only under that ruling.**
  * **The RENDER path discriminates unconditionally, and is therefore the binding form:** two latches with an IDENTICAL `state` of `horizon_expired`, differing only in `clear_reason`, must produce DIFFERENT `_state_label` output (`WITHDRAWN - criteria lapsed ...` vs `HORIZON EXPIRED`). **Discriminator:** any implementation keyed on `state` returns the same label for both and fails.
  This is the honest consequence of Option B, and stating it is part of the cost §3.6 records: under Option B + a not-critical-stale OQ-1, **the RENDER is the only surface whose output differs among the surfaces that existed BEFORE this arc** — and it is the surface the operator reads. **This arc then ADDS a second, stronger one:** the classifier rung (§3.8) must distinguish the two reasons or it re-labels every horizon-expired latch as `framework_withdrawn`, so T6.4(b) is a caller-side obligation test in exactly the same sense. (The template also prints `clear_reason` verbatim at `latches.html.j2:54-57`, which is a second place the difference is VISIBLE — but a raw enum string beside a state label that says HORIZON EXPIRED is not a distinction the card MAKES, which is why `_state_label` carries the obligation.)
* **T1.4** the RD-ruled severity (OQ-1), asserted as a literal so drift in either direction fails.

### T2 — the structural gate
* **T2.1 (NOT DROPPABLE) — a CHARACTERIZATION table of LITERALS, committed BEFORE the refactor.** A hand-written table of `(tt_pass_count, tt_failed_names, vcp_fail_count, risk_pass) -> expected_bucket` covering: risk-fail with a perfect structure; TT below `min_passes`; a TT fail outside `allowed_miss_names`; `vcp_fails` 0 / 1 / 2 / 3. The expected values are LITERALS in the test, so the oracle is independent of the implementation. Run green against the shipped `bucket_for`, commit, then refactor and it must stay green. **A test that called the pre-refactor function as its oracle would be comparing the function with itself and could not fail** — that is why this form is specified.
* **T2.2** `risk_feasibility` is EXCLUDED: criterion rows of TT-all-pass + vcp-all-pass + `risk_feasibility=fail` give `bucket == 'skip'` **and** `structural_gate_passes is True`. **This is the test that fails if the implementation reads `candidates.bucket`.**
* **T2.3** built from the LIVE VSTS 2026-07-28 rows: 18 rows, `risk=pass`, TT1–8 pass, `adr=fail`, `tightness=fail` → gate FAILS. A real-emitter fixture.
* **T2.4** zero criterion rows → `None`.
* **T2.5 (the roster check)** three cases, each returning `None`: (a) **the only FAILING vcp criterion is missing** — **discriminator:** without the check `vcp_fail_count == 0` and the gate falsely PASSES; (b) **enough PASSING TT criteria are missing to drop `tt_pass_count` below `config.trend_template.min_passes`** — without the check the gate falsely FAILS, and a false failure can clear a live mandate (**a single arbitrary missing TT row does NOT necessarily cross `min_passes`, so the fixture must be built to cross it or the test does not discriminate**); (c) an unexpected criterion name present.
* **T2.6 — `na` IS A NON-PASS ON BOTH LAYERS, tested on both.** (a) a vcp `na` counts as a vcp FAIL. (b) **the TT half, which an earlier draft claimed T2.6 covered while asserting only the vcp case:** a roster with enough TT passes to satisfy `min_passes` EXCEPT that one criterion OUTSIDE `allowed_miss_names` is `na` → the structural gate FAILS. **Discriminator:** an adapter that counts only `result == "fail"` into `tt_failed_names`/the pass count treats `na` as neutral, keeps `tt_pass_count` above `min_passes` with no disallowed fail, and falsely PASSES the gate — while every assertion in the vcp-only version of this test stays green.
* **T2.7 — THE ROSTER DRIFT-PIN.** Run a real `evaluate_one` on a synthetic `CandidateContext` and assert the emitted `trend_template` and `vcp` criterion names equal `EXPECTED_TT_CRITERIA` / `EXPECTED_VCP_CRITERIA` exactly. **Discriminator:** a criterion added, renamed or removed changes the gate's meaning silently; this test fails instead. It is what makes the explicit roster safe to hand-write.

### T3 — the reader (pure T4 fixtures can all pass while the SQL feeds the fold wrong data; no site states a count)
* **T3.1** only runs whose `action_session_date` falls in the latch window are considered.
* **T3.2 — THE ASYMMETRIC TIEBREAK, PASSED HALF.** One action session with an earlier row that PASSES the gate and a LATER zero-criteria sentinel → the session is **PASSED** (the streak resets). **Discriminator:** a "latest row wins" implementation returns UNVERIFIABLE, the streak fails to reset, and the latch moves toward withdrawal on the strength of a run that never looked at it.
* **T3.3 — THE ASYMMETRIC TIEBREAK, FAILED HALF.** One action session with an earlier row that FAILS the gate and a LATER zero-criteria sentinel → the session is **UNVERIFIABLE**, not FAILED. **Discriminator:** a "latest verifiable row wins" implementation returns FAILED and advances the streak on evidence the most recent run contradicts. **T3.2 and T3.3 together are what pin the asymmetry; either alone is satisfied by one of the two naive rules.**
* **T3.4** a ticker absent from a run in the window → UNVERIFIABLE, not a fabricated pass or fail.
* **T3.5** a trading session with NO evaluation run at all is OUTSIDE the domain — it does not appear in the verdict sequence and does not contribute to the rendered UNVERIFIABLE tail (§3.2.1).
* **T3.6** the risk layer is excluded from the reduction.
* **T3.7** an empty ticker list short-circuits without issuing SQL (the shipped `load_entry_records` / `load_last_closes` convention at `reader.py:95-97,295-298`).
* **T3.8** a malformed `result` value degrades to UNVERIFIABLE and does not raise.
* **T3.9** the returned verdicts carry the ACTION SESSION date and a `cause`.
* **T3.12 — THE LATEST *RUN*, NOT THE LATEST *ROW*.** One action session, two runs: the earlier carries a verifiable FAILING row for the ticker; the later carries NO row for it at all. The session is **UNVERIFIABLE**, not FAILED. **Discriminator:** a row-keyed implementation still sees the earlier failure as "the latest row" and returns FAILED, advancing the streak on a run that never checked the ticker. **This is the ordinary off-screen case, not an edge case.**
* **T3.14 — THE RUN ORDER IS `(run_ts, evaluation_run_id)`.** One action session with two runs sharing an identical `run_ts`: the lower `evaluation_run_id` carries a verifiable FAILING row, the higher carries NO row for the ticker. The session is UNVERIFIABLE. **Discriminator:** an implementation ordering by `(run_ts, candidate_id)` cannot break the tie at all (the later run has no `candidate_id` for this ticker) and falls back to the failing row.
* **T3.13 — `adr_pct` REACHES THE RESOLVER THROUGH THE PRODUCTION PATH (the fixtures-bypass-the-derivation-path gotcha).** A DB-backed test that seeds a real `candidates` row carrying `adr_pct`, runs `build_latch_derivation` (not a hand-built `FireRow`), and asserts the value arrives at the resolver — an otherwise-qualifying latch CLEARS. **Discriminator:** an implementation that adds `FireRow.adr_pct = None` but forgets `c.adr_pct` in `_FIRE_SQL` passes every direct-resolver fixture (they construct `FireRow` with an ADR by hand) while PRODUCTION marks every latch directionally unverifiable and the feature never fires at all. Byte-tests over hand-built inputs cannot see that; only a test through the real SELECT can.
* **T3.10 — THE OVERLAP.** One action session with an earlier verifiable PASS and a LATER verifiable FAIL → the session is **PASSED** and the streak RESETS. **Discriminator:** an implementation evaluating the §3.2 table in written order without noticing the overlap classifies it FAILED and advances the streak.
* **T3.11 — THE NO-JOIN OBLIGATION, PINNED BY OUTCOME (gotcha #31). REBUILT ON 2b, because the 2a version was IMPOSSIBLE.** An earlier draft asked for bars dated `S1..S5` satisfying 2a while the shifted bars `S1-1..S5-1` contained a pivot crossing — **but the shifted dates lie inside `[anchor, s]`, which lifetime 2a also scans, so both readings see the crossing and the promised opposite outcomes cannot exist.** The two readings differ on **2b's interval and therefore on MATERIALITY**, which is exactly where the live VSTS case separates them ($0.77 vs $0.43). So: construct failing sessions whose bar-dated window `[first(W), last(W)]` widens PAST the floor while the verdict-shifted window `[first(W)-1, last(W)-1]` widens BELOW it, with no close reaching the pivot anywhere in `[anchor, s]`. Assert the ruled (bar-dated) outcome: CLEARS. **Discriminator:** a row-by-row-joining implementation computes the shifted window, falls under the floor, and does not clear. Run the mirror-image fixture (shifted clears, bar-dated does not) so the test pins the ruled reading rather than merely detecting *a* difference. **If OQ-11 rules the other way, both fixtures invert — the test survives the ruling either way, only its expected values move.**

### T4 — the streak and the conjuncts. **The FTRE and VSTS cases are the binding acceptance tests.**

> **THE T4 FIXTURE BASELINE — every value that decides an outcome is stated, never inherited by assumption.** Unless a test says otherwise: `adr_pct = 3.0` on the fire row, `criteria_lapse_min_widening_adr = 1.0`, `min_widening_pct = 2.0`, `criteria_lapse_sessions = 5`, and the archive is COMPLETE over every interval the test exercises. At the baseline (pivot 100) the floor is `max(1.0 × 3.0% × 100, 2.0% × 100) = $3.00`.
>
> **AND A BASELINE PRICE PATH, because the parameters alone are not enough.** Any test asserting a CLEAR must also supply a series that actually satisfies 2a and 2b — otherwise the directional half refuses and the assertion passes for a reason that has nothing to do with what the test claims to check. **The canonical QUALIFYING path is `98, 95, 92, 89, 86`** (pivot 100: no close reaches it, ends at its low, widens $12 ≫ $3). **The canonical NON-QUALIFYING path is `98, 95, 92, 89, 97`** (ends above its low). Tests that are about the STREAK rather than the conjuncts (T4.3, T4.5, T5.2, T5.5) use the qualifying path so their asserted terminal is reached for the reason under test.
>
> **AND THE BASELINE FIXES `initial_stop`, THE FILL SET AND THE HORIZON — without which every NEGATIVE test is non-discriminating.** `_resolve_terminal` invalidates on the first close below `initial_stop` and that terminal outranks or predates a lapse, so a fixture whose stop sits above its lows passes "does not clear by `criteria_lapsed`" **because it INVALIDATED**, not because the lapse rule was right. T4.7 reaches 80 and T4.15 falls to 75, so this is not hypothetical. **Baseline: `initial_stop = 1.00` (below every close in every T4 fixture), NO entry records, and a horizon far beyond the window.** Any test that wants an invalidation or a fill states it explicitly.
>
> **This is load-bearing rather than tidy-minded:** with the materiality clause and the NULL-ADR rule in place, a fixture that omits `adr_pct` or supplies no qualifying series does not clear AT ALL, so an "expected clear" assertion fails spuriously and an "expected no-clear" assertion passes under every implementation, correct or not.

* **T4.1 — THE FTRE COUNTEREXAMPLE, NOT DROPPABLE. Complete fixture, no omitted rows.**
  Fire: candidate 11261, action session 2026-07-20, pivot 18.34, stop 14.88.
  Evaluated rows (all structurally FAILING; `bucket='watch'`): 07-21, 07-22, 07-23, 07-24, **07-28, 07-29, 07-31**.
  **ABSENT (no candidates row): 07-27 and 07-30.**
  Archive bars, by their own date: 07-20 17.73, 07-21 17.91, **07-22 18.49**, 07-23 19.50, 07-24 19.52, 07-27 19.20, 07-28 20.70, 07-29 20.40, 07-30 19.08, 07-31 19.17.
  Entry record: trade 19, **`entry_date = 2026-07-31`** (the item-5-corrected date; §2.3(b)), `candidate_id = 11852`, price 18.80.
  **Assertions:** with N=5 the latch NEVER carries `clear_reason == "criteria_lapsed"` at any derivation session; it clears by `fill` on 2026-07-31.
  **What this fixture ACTUALLY discriminates — corrected, because an earlier draft over-claimed it.** The streak DOES reach 5 on 07-28, so **a naive gate-only rule (no directional conjunct at all) clears three sessions before the operator's fill** — that is RD's counterexample and this fixture pins it exactly. It does **NOT** discriminate the other two design choices, and saying so is the point: at the fifth failure `B` runs 17.91 → 20.70, so an **endpoint-only 2b does not clear either** (last > first), and every remaining bar after 07-22 ages out is still above 18.34, so a **window-scoped 2a also refuses**. FTRE is the RULING's acceptance test, not a universal discriminator. **T4.6 and T4.7 are the tests that discriminate lifetime-vs-window and endpoint-vs-ends-at-low, and they are non-droppable for exactly that reason.**
* **T4.2 — THE VSTS CASE.** Fire candidate 11629, 2026-07-27, pivot 16.90. Failing evaluated sessions 07-28, 07-29, 07-30; absent thereafter. Archive bars 07-27 15.35, 07-28 15.36, 07-29 14.92, 07-30 14.59. **With N=3 the latch clears `criteria_lapsed` at 2026-07-30; with N=5 it does NOT clear and the streak is frozen at 3.** **UNDER THE OQ-14 HIGH BRANCH THIS FIXTURE MUST ALSO SUPPLY THE POST-ANCHOR HIGHS, and the clear is only correct if every one is below 16.90** — a single high touching the pivot blocks it, and neither the closes above nor the live-row queries in §2.2 establish the highs. **The executing implementer must read VSTS's actual highs for 07-27..07-30 from the archive before asserting this outcome** (§2.2 query 5's method, `high` instead of `close`); if any reaches 16.90 the fixture's expected result changes and that is a real finding about the live case, not a fixture inconvenience. Both assertions, pinning the config binding as well as the rule.
* **T4.3** absent sessions neither advance nor reset: FAIL/ABSENT/FAIL/ABSENT/FAIL with N=3 clears on the third FAILED session. **Discriminator:** counting calendar sessions clears earlier; RESETTING on absence never clears.
* **T4.4** an `excluded` (held-position) row is UNVERIFIABLE, not FAILED. Fails if `bucket != 'aplus'` is the predicate.
* **T4.5** a PASSED session resets the streak to zero, including the re-confirmation case (a later `aplus` fire).
* **T4.6 — 2a IS A LIFETIME PROPERTY.** Pivot 100, baseline fixture. Closes `95, 97, 101, 99, 98, 97, 96, 95`, every session structurally failing, N=5. The latch NEVER clears. **Discriminator:** under a window-scoped 2a the `101` ages out and the trailing five `99, 98, 97, 96, 95` satisfy clauses 2–3 with a widening of **$4.00 > the $3.00 floor**, so the wrong implementation genuinely clears. (The widening is stated because a fixture whose widening fell under the floor would refuse under BOTH implementations and discriminate nothing.)
* **T4.7 — 2b REQUIRES THE WINDOW TO END AT ITS LOW. REBUILT: the earlier fixture stopped discriminating the moment clause 4 was added.** Pivot 100, baseline fixture, N=5, all failing, closes `95.00, 80.00, 85.00, 88.00, 90.00`. The latch does NOT clear. **Discriminator:** an endpoint-only rule sees `90.00 < 95.00` with a widening of **$5.00 > the $3.00 floor** and clears a stock that has rallied 12.5% off its low; the correct rule refuses because `90.00` is not the window minimum (`80.00` is). **The earlier fixture (`95.00 … 94.99`) had a one-cent endpoint difference, which clause 4 rejects anyway — so correct and incorrect implementations both refused and the test could not fail.**
* **T4.8 — ROLLING, NOT ONE-SHOT** (conjunct false at N, true later). Pivot 100, baseline fixture, N=3, all sessions failing, closes `90, 84, 92, 88, 80`. At the third failure the window `90, 84, 92` does not end at its low → no clear. Two sessions later the window `92, 88, 80` ends at its low and widens **$12.00 > $3.00** → the latch clears at that session. **Discriminator:** a one-shot implementation tested only when the counter first reaches N never clears at all.
* **T4.9 — PRECEDENCE, and the LATER-INVALIDATION case is the one that matters.**
  (a) **A lapse on D5 followed by an invalidation on D8 stays `criteria_lapsed` at D5.** **Discriminator:** a resolver that scans for invalidation across the whole range before considering the lapse returns `invalidation`/D8 and silently rewrites a terminal that had already resolved. **This is the case an earlier draft of this plan got wrong.**
  (b) The same fixture plus a fill on D6: the fill is NOT attributed (it is after the D5 terminal). **Discriminator:** under the wrong structure D6 ≤ D8 and the fill IS attributed — a real position credited to a mandate the framework had already withdrawn.
  (c)–(d) SAME-SESSION collisions, where rank is the only tiebreak: invalidation and lapse on the same session → `invalidation`; lapse and horizon on the same session → `criteria_lapsed`.
  (e) a fill dated at-or-before the lapse → `fill`.
  **Different-session non-fill terminals alone prove nothing** — they pass under both structures, which is why (a) and (b) are specified explicitly.
* **T4.10** the lapse walk is capped at `horizon_expiry`: a streak completing AFTER expiry leaves `clear_reason='horizon'` at the horizon's clear session.
* **T4.11 — STABILITY OF THE CLEAR DATE, with MULTIPLE qualifying windows.** Baseline fixture, pivot 100, N=5, all failing, closes `98, 95, 92, 89, 86, 83` — the D1–D5 window (`98…86`, widening $12) qualifies AND the D2–D6 window (`95…83`, widening $12) qualifies. Assert `clear_session` is D5 and that re-deriving one session later still returns D5. **Discriminator:** a literal "last N failures" implementation returns D6 on the second derivation and the clear date walks forward every session.
* **T4.19 — DUPLICATE-BAR CANONICALIZATION COVERS EVERY READ FIELD. *Branch-conditional on OQ-14:* the differing-HIGH case is only a defect if 2a reads the high; under a CLOSE answer, `high` is not a conjunct input and a high disagreement must be IRRELEVANT — so the test asserts whichever OQ-14 rules, and asserting the HIGH form unconditionally would make the suite wrong under a permitted answer.** Two rows for one date agreeing on close but DISAGREEING on high (`close 95 / high 101` and `close 95 / high 99`) make that date UNVERIFIABLE. **Discriminator:** a close-only canonicalization collapses them, and under the OQ-14 HIGH variant a surviving `high 99` row hides a pivot touch at `101` — clearing a latch whose stop-limit had triggered. Also assert a non-finite value in any read field makes the date UNVERIFIABLE.
* **T4.18 — A HISTORICAL BAR CORRECTION MOVES A TERMINAL, AND THAT IS DISCLOSED BEHAVIOUR (§3.2.1 ruling 6a).** Derive a lapse from `95, 94, 93, 92, 90`; then CORRECT the D3 bar to `101` and re-derive: the latch is no longer `criteria_lapsed`. Then backfill a previously-missing D3 into an incomplete window and re-derive: a lapse now appears. Assert both. **This test does not defend a property — it PINS a known consequence of deriving over a mutable archive (gotcha #26), so that a future reader meets it as a recorded decision rather than as a mystery**, and so that any later immutable-snapshot work has an explicit statement to change.
* **T4.17 — THE MATERIALITY BOUNDARY, with the float artifact STATED (a generic `98.00 → 95.00` pair evaluates identically under both implementations and would prove nothing).** Baseline fixture, pivot 100, floor exactly `$3.00`. Use operands whose IEEE-754 difference falls just below the decimal value: **the complete five-bar series `64.02, 63.50, 63.00, 62.00, 61.02`** (all below the pivot, strictly descending so clause 3 holds, `first = 64.02`, `last = 61.02`) — verified on this box, `64.02 - 61.02` evaluates to **`2.999999999999993`**, while both closes round to exactly `64.02` and `61.02` and the panel displays a `$3.00` widening. **Set BOTH floor terms to $3.00 explicitly: pivot `150.00`, `adr_pct = 2.0` (ADR term `1.0 × 2% × 150 = $3.00`), `min_widening_pct = 2.0` (pivot term `$3.00`) → floor `max(3.00, 3.00) = $3.00`.** The T4 baseline's `adr_pct = 3.0` would make the ADR term `$4.50` and the test could not clear at all — a second reason it would have passed for the wrong reason. Assert the latch CLEARS. **Discriminator:** an implementation that differences the raw floats — **OR that rounds the operands and then subtracts, which is the same thing** — gets `2.999999999999993 < 3.00` and REFUSES, withdrawing nothing while the card states equality. Then assert a genuine `$2.99` widening does NOT clear, pinning both sides.
  **A note on how this value was obtained, because it matters:** an earlier draft asserted `100.10 - 97.10 == 2.9999999999999947`. **That is FALSE — it evaluates to exactly `3.0`** — and a test built on it would have passed under both implementations, i.e. the boundary test guarding the precision rule would itself have been precision-blind. The pair above came from an exhaustive scan of two-decimal pairs. **The executing implementer must re-verify it on the box before relying on it.**
* **T4.16 — A LATER PIVOT CROSSING CANNOT RESURRECT A CLEARED LATCH.** Baseline fixture, pivot 100, N=5, all failing, closes `95, 94, 93, 92, 90` (widening $5.00 > $3.00) → clears at D5. Then add a D6 bar closing `105` and re-derive. Assert the latch is STILL `criteria_lapsed` at D5, and that a fill dated D6 is NOT attributed. **Discriminator:** an implementation bounding 2a at `derivation_session` instead of at the candidate terminal `s` finds the `105` crossing, disqualifies 2a, and RESURRECTS a latch that had already cleared — breaking L10 through the conjunct rather than through the precedence. **This is a defect an earlier draft of this plan contained.**
* **T4.12 — display precision, ARITHMETIC CHECKED UNDER BOTH PATHS.** Against a pivot of 18.34 at `_PRICE_DP = 2`: a close of `18.3400001` rounds to `18.34`, is at-or-above the pivot, and DISQUALIFIES 2a; a close of **`18.3349`** rounds to `18.33`, is below, and does NOT. **An earlier draft used `18.3399` for the second case, which rounds to `18.34` and also disqualifies — the test asserted an outcome no correct implementation could produce.**
* **T4.13 — LIFETIME-2a COMPLETENESS, ISOLATED. The gap must sit BEFORE the streak window or the test proves nothing.** Pivot 100, baseline fixture. **The N-failure window itself is COMPLETE and fully qualifying** (closes `99, 96, 95, 94, 92`), while the MISSING bar — the one whose true close was `101` — lies **after the anchor but BEFORE `first(W)`**, inside lifetime 2a's `[anchor, s]` and OUTSIDE 2b's `[first(W), last(W)]`. The latch does NOT clear and is reported DIRECTIONALLY UNVERIFIABLE. **Discriminator:** an implementation that omits LIFETIME-2a completeness but implements 2b's completeness correctly still clears — the streak window is complete and qualifying, so 2b is satisfied, and 2a sees no pivot close because the crossing bar is simply absent. **An earlier draft put the missing bar INSIDE the streak window, where 2b's own completeness check already refuses it, so the test passed under an implementation with no lifetime-2a completeness at all.** Plus one sibling case: `archive_status == 'unavailable'` over an otherwise-qualifying series → no clear. (**A `len(B) < 2` sibling was dropped**: completeness plus `N >= 2` makes it unreachable, so it would pass under both implementations.)
* **T4.14 — MATERIALITY, both terms of the floor (OQ-10).** Two fixtures, because the two terms fail on different shapes:
  (a) **the ADR term binds:** pivot 100, `adr_pct = 4.0` (floor `max(4.00, 2.00) = $4.00`), closes `99.00, 99.04, 99.03, 99.02, 98.99` → widening $0.01, no clear. **Discriminator:** without clause 4 this satisfies 2a and clauses 2–3 and a one-cent "decay" withdraws the mandate.
  (b) **THE PIVOT-RELATIVE TERM BINDS, and an ADR-only floor FAILS THIS ONE:** pivot 100, `adr_pct = 0.40` (ADR term $0.40; pivot term $2.00; floor $2.00), closes `99.80, 99.90, 99.75, 99.60, 99.30` → widening $0.50, no clear. **Discriminator:** an ADR-only floor of $0.40 is exceeded by $0.50 and CLEARS a sub-1% consolidation sitting under its pivot.
* **T4.15 — NULL ADR SUPPRESSES, AND THE FIXTURE DEFEATS A HARD-CODED FALLBACK.** Pivot 100, `adr_pct` NULL, N=5, all failing, closes `95, 90, 85, 80, 75` — a widening of **$20**, which exceeds any plausible hard-coded substitute (5% of pivot = $5, a flat $10, 1×a-typical-ADR = $3). The latch does NOT clear and is DIRECTIONALLY UNVERIFIABLE. **Discriminator — and "exceeds any plausible fallback" is NOT one, because a 25%-of-pivot substitute refuses this series too and passes both assertions.** The enforceable form asserts the ORDER OF OPERATIONS instead: with `adr_pct` absent the latch reports `directional_evaluable = False` with `directional_block_reason` naming the MISSING ADR — **proving the resolver exited before any floor was computed** — rather than merely reporting "no clear", which any substitute also produces. Pair it with a second fixture identical except that `adr_pct` IS present and small enough that the same series CLEARS, so the two differ only in the ADR's presence. Repeat with a non-finite `adr_pct`.

### T5 — the calibration
* **T5.0a — THE THREE DEFAULTS EQUAL THE RULED LITERALS.** After OQ-10 is answered, assert the exact values (`5`, `1.0`, `2.0` as recommended): mirror-to-mirror equality alone passes when all three mirrors are changed together, so a synchronized drift to `1.5`/`5.0` would go unnoticed and every T4 test — which passes explicit arguments — would stay green.
* **T5.0 — ALL THREE MODULE DEFAULTS ARE PINNED, not just N.** `DEFAULT_CRITERIA_LAPSE_SESSIONS == LatchesConfig().criteria_lapse_sessions`, `DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR == LatchesConfig().criteria_lapse_min_widening_adr`, `DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT == LatchesConfig().criteria_lapse_min_widening_pct`. **Discriminator:** an earlier draft pinned only N, so either materiality module default could drift from its dataclass while every test stayed green — and the pure derivation would then silently use a different floor from production.
* **T5.1 — THE MIRROR PIN COVERS THE SHIPPED TOML TOO, WHICH IS A THIRD MIRROR AN EARLIER DRAFT MISSED.** `DEFAULT_CRITERIA_LAPSE_SESSIONS == LatchesConfig().criteria_lapse_sessions == 5` pins the module constant against the dataclass — **but production loads `swing.config.toml`, not the dataclass default**, so an explicit `[latches]` block in the tracked config is a THIRD copy that can drift from both while every test stays green. **Fix: the tracked TOML carries ALL THREE keys** (`criteria_lapse_sessions`, `criteria_lapse_min_widening_adr`, `criteria_lapse_min_widening_pct` — the earlier draft shipped only the first, so the two materiality knobs were config-bound in prose and default-only in fact) **and T5.1 asserts against the RAW TRACKED TOML TEXT, not the loaded config.** Comparing the LOADED values to the dataclass defaults **cannot fail**: if the `[latches]` block — or just one key — is absent, `load()` supplies those very defaults and the comparison passes over the exact missing-mirror defect it claims to catch (T5.3 proves the section is optional). So the test PARSES `swing.config.toml` and asserts every field of `LatchesConfig` is EXPLICITLY PRESENT as a key with a value equal to the dataclass default, iterating `dataclasses.fields(LatchesConfig)` so a fourth knob joins the pin automatically.
* **T5.2** the derivation honours a non-default N (7 → clears later). Fails against any hard-coded 5.
* **T5.3** a config file with no `[latches]` section loads and defaults.
* **T5.4 — THE INERT-CONFIGURATION FAMILY, one assertion each.** `criteria_lapse_sessions` = `1` raises (2b unsatisfiable); `2.5` raises (**discriminator:** a bare `< 2` check accepts it and the derivation's `int()` silently truncates to 2); `True` raises (**discriminator:** `bool` is an `int` and passes every numeric comparison). `criteria_lapse_min_widening_adr` = `float("inf")` raises (**discriminator:** it satisfies `> 0` and disables the lapse forever, silently); `0` and `-1` raise; `float("nan")` raises (every ordered comparison against `nan` is False, so a `> 0` guard admits it — the same hole `zone_cap_for_pivot`'s docstring records at `constants.py:83-93`). Same set for `criteria_lapse_min_widening_pct`.
* **T5.5 — RETROACTIVITY IS PINNED, NOT LEFT TO BE DISCOVERED (§3.2.1 ruling 7).** One fixture, two configs: with N=5 the latch clears `criteria_lapsed` before a day-6 entry and that entry is NOT attributed; with N=7 the same fixture clears by `fill` on the day-6 entry. Assert both. **Discriminator:** it fails if anyone later freezes N per-latch — which would be a reasonable change, and this test makes it a deliberate one.

### T6 — the measurement disposition (CONDITION 5 — the discriminating bucket exclusions)

* **T6.1 — EXCLUDED FROM THE AWAY RATE.** Corpus: 1 `framework_withdrawn` + 1 `away_unseen` + 1 `accepted`, all terminal, health `ok`. Assert `objective_rate == 0.5` **and** `classifiable_fires == 2` **and** `bucket_counts["unattributable_r"] == 1`.
  **Discriminators:** in `AWAY_RATE_COUNTED_DISPOSITIONS` → `2/3` and `3`; in `DECISION_DISPOSITIONS` **as well as** `_ALL_EXCLUDED_DISPOSITIONS` → see T6.10, which this test does NOT catch.
* **T6.11 — THE HEALTH EDGE (OQ-16).** A terminal `criteria_lapsed` latch with a NON-OK telemetry verdict. Assert whichever disposition OQ-16 rules, and assert in BOTH cases that `away_r`, `decision_r` and `classifiable_fires` are unchanged — the rates are invariant to this edge, only the label moves, which is what makes it a labelling ruling rather than a measurement one.
* **T6.10 — THE BUCKET SETS ARE A PARTITION, ASSERTED DIRECTLY. T6.1 ALONE IS NOT SUFFICIENT AND AN EARLIER DRAFT CLAIMED IT WAS.** `UNATTRIBUTABLE_DISPOSITIONS` is derived as `_ALL_EXCLUDED_DISPOSITIONS - AWAY_RATE_COUNTED_DISPOSITIONS - ATTESTED_AWAY_DISPOSITIONS` (`constants.py:539-543`) — **it does NOT subtract `DECISION_DISPOSITIONS`.** So a disposition added to BOTH `_ALL_EXCLUDED_DISPOSITIONS` and `DECISION_DISPOSITIONS` stays in `UNATTRIBUTABLE_DISPOSITIONS`, and because `r_bucket_for` tests unattributable BEFORE decision (`classification.py:761-768`) it still returns `unattributable_r` — **so T6.1 reads `0.5`, `2` and one unattributable cell and passes over the wrong implementation.** My claim that an overlap is "unrepresentable by construction" was FALSE. **Fix: assert the five bucket sets are PAIRWISE DISJOINT and that their union is `_RULED_DISPOSITIONS`,** iterating the sets so a sixth gains the assertion automatically.
* **T6.2 — EXCLUDED FROM THE DISCIPLINE SIGNAL.** Same corpus: `bucket_counts["decision_r"] == 1`, `decision_r_logged == 1`, `decision_r_inferred == 0`. **Discriminator:** if the latch classified `discipline_lapse`, `decision_r == 2` and `decision_r_inferred == 1`.
* **T6.3** `r_bucket_for("framework_withdrawn", is_terminal=True) == "unattributable_r"`; with `is_terminal=False` → `pending_r` (the terminality gate is not bypassed).
* **T6.4 — THE RUNG PRE-EMPTS `discipline_lapse`, AND KEYS ON `clear_reason` NOT `state`.** (a) A TERMINAL `criteria_lapsed` latch with actionable view rows and NO intents classifies `framework_withdrawn`. **Discriminator:** with no rung it classifies `discipline_lapse`. (b) **THE SIBLING THAT MAKES (a) MEAN ANYTHING:** an ordinary `horizon` latch in the same shape classifies `discipline_lapse`, NOT `framework_withdrawn`. **Discriminator:** under Option B both latches carry `state == "horizon_expired"`, so a rung written `if latch.state == "horizon_expired"` passes (a) and every other positive lapse test while silently re-labelling every horizon-expired latch — removing real discipline evidence from the signal.
* **T6.5 — THE RUNG DOES NOT SWALLOW A DECISION.** The same latch with a governing `place` classifies `accepted`; with a governing `decline`, `declined`. **Discriminator:** fails if the rung sits above rungs 1–3.
* **T6.6 — THE RUNG PRE-EMPTS `away_unseen`, WHICH IS WHAT RD'S RULING ACTUALLY REQUIRES.** A TERMINAL `criteria_lapsed` latch with FULL coverage, health `ok`, and **NO view rows at all** classifies `framework_withdrawn`, and `bucket_counts["away_r"] == 0`. **Discriminator:** with the rung below rung 7 it classifies `away_unseen`, `away_r == 1`, and the withdrawn mandate enters the away rate RD excluded it from. **This is the test that pins the placement.**
* **T6.7 — THE RUNG DOES NOT PRE-EMPT RUNG 4.** A `criteria_lapsed` latch whose coverage is `none` classifies `pre_telemetry`, preserving *"the ONLY route to `pre_telemetry`"*. **Discriminator:** fails if the rung is placed above rung 4.
* **T6.8** `prompt_required is False`; absent from `PROMPT_DISPOSITIONS`.
* **T6.9** the shipped `_RULED_DISPOSITIONS == LATCH_DISPOSITIONS` conclusion test still passes.

### T7 — the render
* **T7.1** an off-screen live latch renders UNVERIFIABLE, not plain `ARMED`, and names the count.
* **T7.2** a `criteria_lapsed` latch renders `WITHDRAWN - criteria lapsed on <session>` and **never** `HORIZON EXPIRED`. Under Option B, assert against a latch whose `state` IS `horizon_expired`, so the test fails if the label is keyed on `state`.
* **T7.3** the countdown renders on a live latch with a partial streak (§3.2.1 ruling 3), and renders the `directional test NOT EVALUABLE` form when the archive cannot support §3.3 (§3.2.1 ruling 2a). **Discriminator:** a card showing `failed 4 of 5` beside a plain live status while the directional predicate had no data tells the operator a withdrawal is one session away when it is in fact unreachable.
* **T7.4 — UNVERIFIABLE ADDS NO NEW SUPPRESSION. Narrowed, because the earlier form asserted more than the source supports.** The requirement is NOT "the prepared order is always offered on an UNVERIFIABLE latch" — 21-B already withholds it for its own reasons (`LATCH_ORDER_WITHHELD_REASONS` = `regime_undeterminable` / `sizing_infeasible` / `sizing_degenerate`, `constants.py:432-434`), and an off-screen latch with an uncorroborated close may legitimately hit `regime_undeterminable` under 21-G's ladder. The testable requirement is: **for a pair of latches identical except that one is UNVERIFIABLE, the withheld/offered outcome is the SAME — and the control latch MUST be constructed so the prepared order is actually OFFERED.** If the pair is built carelessly and both hit `regime_undeterminable`, both are withheld before and after an erroneous UNVERIFIABLE suppression and the equality assertion passes over the exact defect it names. **Discriminator:** fails if UNVERIFIABLE is implemented by adding a suppression of its own — the alarm-gates-the-affordance defect item 4 of this queue exists to remove. Whether 21-B's EXISTING rules already withhold on a stale close is a pre-existing property this arc neither changes nor asserts.
* **T7.5** every base-layout VM still constructs (the shared-`base.html.j2` gotcha); `GET /latches` returns 200 with zero latches, a live latch, an UNVERIFIABLE latch and a withdrawn one.
* **T7.8 — THE DECLINE CONTROL SURVIVES A WITHHELD PREPARED ORDER (§3.2.1 ruling 4, second half).** Construct a latch that hits an EXISTING 21-B withholding reason (`regime_undeterminable`) and assert the decision (decline) control is STILL rendered. **Discriminator:** an implementation that hangs the decision affordance off the prepared-order block renders nothing, and the operator cannot resolve the one mandate the framework admits it cannot price — the item-4 defect, one surface over. T7.4 does not cover this: it only asserts UNVERIFIABLE adds no suppression of the FORM.
* **T7.11 — THE OVER-THRESHOLD CARD.** A live latch with `k = 8` failures against `N = 5`, still armed because lifetime 2a refuses (the T4.6 shape). Assert the card renders `8 failures; threshold 5; directional condition NOT MET` and **never** the string `8 of 5`. **Discriminator:** an implementation rendering the fraction unconditionally prints a nonsensical countdown with no explanation on a latch that will never lapse.
* **T7.12 — THE `Latch` DIAGNOSTIC INVARIANTS.** Constructing a `Latch` RAISES when: a count disagrees with its tuple; a session tuple is not strictly ascending; the failed and unverifiable tuples intersect; the causes tuple is not parallel to the unverifiable sessions; or `lapse_unverifiable_tail` is not the actual unverifiable suffix. **Discriminator:** without these a latch can name one session twice or claim an arbitrary tail, and T7.10 — which tests PROVENANCE — would not notice.
* **T7.10 — THE CARD NAMES THE SESSIONS AND THE CAUSE, FROM THE RESOLVER.** For VSTS's live shape, the card names the failed sessions `2026-07-28, 2026-07-29, 2026-07-30` and states the UNVERIFIABLE cause (`absent`). **Discriminator (a): an implementation carrying only counts cannot render either.** **Discriminator (b) — PROVENANCE, OBSERVED RATHER THAN ASSERTED:** on a CONSISTENT fixture a reading VM and a recomputing VM render identically, so "assert the VM reads them" is untestable as stated. **Poison the inputs instead:** hand the VM a `Latch` whose `lapse_failed_sessions` are DELIBERATELY different from what the raw verdict sequence would produce, and assert the card renders **the `Latch`'s** dates. A VM that recomputes renders the other set and fails. (An equally valid form is to withhold the verdict sequence from the VM entirely so recomputation is impossible by construction — that is the stronger design and is preferred if the wiring allows it.)
* **T7.9 — THE UNCHECKED COUNT IS RENDERED FROM THE RESOLVER, NOT RE-ENUMERATED IN THE VIEW.** Build a window whose IN-DOMAIN sequence is `PASS / ABSENT / FAIL / ABSENT / FAIL` — i.e. **TWO runs in which the ticker was absent** — **PLUS a separate trading session on which NO RUN EXISTS AT ALL.** Assert the card shows `failed 2 of 5 checked sessions (2 unchecked)`: the two ticker-absent runs count, the no-run day contributes NOTHING. **Discriminator:** a VM that enumerates trading sessions counts the no-run day and renders `3 unchecked` — a false statement about what the framework failed to check. *(An earlier draft's fixture had only ONE ticker-absent run beside the no-run day, so the correct implementation would have rendered `1` and the stated expectation of `2` was unreachable — the fixture and its assertion contradicted each other.)* T3.5 pins the reader; this pins the surface the operator actually reads.
* **T7.6** `GET /latches` still writes NOTHING (the 21-A A4 property) with the new reads in place.
* **T7.7** ASCII-only in every added user-facing string.

---

## §7 File manifest

| File | Change |
|---|---|
| `swing/latches/constants.py` | `LATCH_CLEAR_REASONS`; `LATCH_DISPOSITIONS`; `_ALL_EXCLUDED_DISPOSITIONS`; **all THREE** module defaults — `DEFAULT_CRITERIA_LAPSE_SESSIONS`, `DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR`, `DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT` |
| `swing/latches/service.py` | `_STATE_BY_CLEAR_REASON`; `_resolve_criteria_lapse`; the earliest-date-wins precedence; **the FOUR new `derive_latches` keyword parameters** (`structural_verdicts_by_ticker` + the three calibrations); `bar_status_by_ticker` threaded into the fold; the two stale docstrings (§4.1 rows 12-13) |
| `swing/latches/reader.py` | `structural_inputs_from_rows`; `load_session_structural_verdicts`; **`c.adr_pct` added to `_FIRE_SQL` + hydrated RAW into `FireRow`**; `build_latch_derivation` wiring |
| `swing/latches/models.py` | a `SessionStructuralVerdict` value type (`action_session`, `classification`, `cause`); **`FireRow.adr_pct` (trailing, defaulted, RAW)**; **the EIGHT trailing defaulted `Latch` diagnostic fields** — `lapse_failed_sessions`, `lapse_unverifiable_sessions`, `lapse_unverifiable_causes`, `lapse_failed_count`, `lapse_unchecked_count`, `lapse_unverifiable_tail`, `directional_evaluable`, `directional_block_reason` — **with `__post_init__` deriving/validating every COUNT against its TUPLE** (see §3.2.1) |
| `swing/latches/classification.py` | the `framework_withdrawn` rung (between 5 and 6) |
| `swing/latches/orders.py` | `_CRITICAL_STALE_CLEAR_REASONS` per OQ-1 |
| `swing/evaluation/scoring.py` | `StructuralInputs`, `structural_inputs_from_results`, `structural_gate_passes`, `EXPECTED_TT_CRITERIA`, `EXPECTED_VCP_CRITERIA`; `bucket_for` composes them |
| `swing/config.py` | `LatchesConfig` (N + the materiality multiple); `Config.latches`; `load()` wiring |
| `swing.config.toml` | `[latches]` with **ALL THREE keys explicitly present** — `criteria_lapse_sessions = 5`, `criteria_lapse_min_widening_adr = 1.0`, `criteria_lapse_min_widening_pct = 2.0` (T5.1 parses the raw file and fails if any is missing) |
| `swing/web/view_models/latches.py` | `_state_label` branch; the UNVERIFIABLE + countdown + `directional_evaluable` fields |
| `swing/web/templates/latches.html.j2` | the UNVERIFIABLE render + the countdown |
| `docs/rd-state.md:50` | the doc mirror |
| `tests/latches/test_identity.py` | `test_locked_constants`, T1 |
| `tests/latches/test_criteria_lapse.py` | NEW — T4 (incl. the FTRE counterexample) |
| `tests/latches/test_classification.py` | T6 |
| `tests/latches/test_reader.py` | T3 |
| `tests/evaluation/test_scoring.py` | T2 |
| `tests/web/...latches...` | T7 |

**No migration. No `swing/data/` or `swing/trades/` edit. No new dependency.**

---

## §8 Locks

* **L1 — NO SCHEMA.** If any part of the executing arc appears to require a persisted column, a widened `CHECK`, or a new `LATCH_STATES` / `intent_kind` member: **STOP and route to CHARC.** Do not author a migration inside this arc.
* **L2 — #11 ONE COMMIT.** Task 1 carries every Python mirror of the clear-reason vocabulary.
* **L3 — T4.1 (FTRE), T4.6 (lifetime 2a), T4.7 (ends at its low), T4.9(a)(b) (the later-invalidation rewrite), T4.13 (archive completeness), T4.14 (materiality) and T2.1 ARE NOT DROPPABLE.** Each is the sole discriminator for a design choice that a plausible alternative implementation gets wrong — and each corresponds to a defect a draft of this plan actually contained.
* **L4 — `risk_feasibility` NEVER ENTERS THE GATE.** T2.2 is the guard.
* **L5 — N AND THE MATERIALITY MULTIPLE ARE NEVER LITERALS** outside `LatchesConfig`'s defaults and the mirror constant, drift-pinned. The materiality floor is derived from the fire's own `adr_pct` and is never a hard-coded percentage.
* **L6 — THE DIRECTIONAL CONJUNCT IS NON-NEGOTIABLE.** No variant that clears on gate failure alone ships, in any config state. 2a is a LIFETIME property and may be ASSERTED ONLY over a COMPLETE bar range.
* **L7 — NO VERDICT IS EVER JOINED TO A BAR.** The streak reads evaluated sessions; the conjuncts read archive bars by their own date. `candidates.close` is never read as a session's close (§2.2 query 5, gotcha #30).
* **L10 — A TERMINAL IS NEVER REWRITTEN BY A LATER EVENT.** Terminal selection is earliest-date-wins with rank only as a same-session tiebreak (§3.5). No later invalidation may overwrite an earlier lapse, and the fill rung compares against the earliest terminal.
* **L8 — PURITY.** `service.py` and `classification.py` stay pure: no DB, no network, no transactions. All I/O in `reader.py`.
* **L9 — `GET /latches` WRITES NOTHING** (21-A A4); `load_bars_with_status`'s `migrate=False` posture preserved. T7.6.

---

## §9 Open questions

**Which of these BLOCK is stated once, in the table at the head of this document** (TWELVE at Task 1; OQ-3 at merge, making THIRTEEN in all). The entries below give each question's substance.

1. **BLOCKING — Is `criteria_lapsed` critical-stale?** (`_CRITICAL_STALE_CLEAR_REASONS`, `orders.py:56`.) **RD's call**, routed to him by CHARC at plan review. CHARC's prior: NOT critical-stale. Counter-argument for RD to weigh: severity here encodes the operator's outstanding manual DUTY, which is identical in both cases. It blocks because it is an edit inside Task 1's one-commit sweep. §3.7.
2. **BLOCKING — Is a new `LATCH_STATES` member required, and if so what is it called?** **A SCHEMA question, not a naming one** — §0 documents four SQL `CHECK` mirrors plus an exact-set-equality test. Option B (reuse `horizon_expired`; `criteria_lapsed` is the reason; dedicated label branch) is executable within the authorized scope and loses no information. **Options A/A′ route back to CHARC.** RD's header says *"it needs its own state"*; whether that binds on `LATCH_STATES` or on the render is the question. §3.6.
3. **The live-vs-shadow parity window.** `latch_horizon_sessions` binds the latch horizon to `observe_max_pending_window_sessions` (30) with an explicit docstring warning that a SHORTER live window manufactures a divergence — *"sessions beyond it become a window where the shadow can enter and live has no mandate, a MANUFACTURED divergence, the FTRE-class defect this arc exists to eliminate."* **A `criteria_lapsed` clear at session N < 30 re-opens exactly that window**, and the observe step (`runner.py:3074`) tracks detections with no knowledge of latch state. RD may rule the divergence REAL and worth measuring, but it is his lane and the amendment does not address it. Must be answered before merge.
4. **BLOCKING — Must the off-screen decision TERMINATE the latch? (The question is SEMANTIC; an earlier draft wrongly asserted it was necessarily a schema question.)** V1-A (measurement-only) is buildable now but delivers only half of *"making it a decision point IS the corrective path"*: the decision is captured, the stale pivot is NOT corrected, the latch stays live. V1-B (terminating) is **not automatically schema and not automatically a purity violation** — passing intents into a pure function as an explicit argument is exactly how `bars` and `entries` already arrive, and `decline` is already persisted and CHECK-accepted. **The real question is semantic:** may an existing `decline` govern TERMINATION as well as measurement, and what clear reason truthfully names the resulting terminal? A new clear reason is pure Python; a new `intent_kind` would be schema (`0033:346`). RD rules the semantics; only if his answer requires a new intent kind does this route back. §3.2.
5. **SUPERSEDED BY OQ-12 AND OQ-13 — and an earlier draft's "RESOLVED in this plan" was an overstep I am recording rather than deleting.** The plan has no authority to resolve RD's semantics; what it can do is show the counterexamples and recommend. Endpoint-vs-monotone-vs-ends-at-low is now OQ-13, and the window-vs-lifetime question is OQ-12. §3.3.
12. **BLOCKING — AMENDMENT A: may conjunct 2a become a LIFETIME predicate over `[anchor, s]`?** RD's text scopes both conjuncts to the N-session window. **The failure that forces the question:** a breakout close AGES OUT of a rolling window, so `95, 97, 101, 99, 98, 97, 96, 95` clears once the `101` leaves the window — the FTRE geometry a week later. **The cost of saying yes:** one tick above the pivot confers permanent immunity, and one missing archive bar disables the feature for that latch until the bar is backfilled. Both are stated in §3.3 so he is ruling on evidence.
13. **BLOCKING — AMENDMENT B: may the window be required to END AT ITS OWN LOW?** RD's text says "the shortfall has WIDENED across the window" and describes VSTS as monotone. **The failure that forces the question:** `95.00, 80.00, 85.00, 88.00, 90.00` widened on the endpoints while rallying 12.5% off its low. **The alternative he may prefer** is his literal monotone reading, which is stricter still and would refuse more. §3.3.
6. ~~The rung's placement~~ — **RESOLVED and shown to be FORCED**, not a preference: below rung 4 (which is *"the ONLY route to `pre_telemetry`"*) and above rung 7 (or a withdrawn latch he never saw scores `away_unseen` and enters the away rate RD excludes it from). §3.8, T6.6/T6.7.
14. **BLOCKING — Does conjunct 2a test the session HIGH or the CLOSE?** The mandate is a stop-limit TRIGGERED at the pivot, so an intraday touch fires it; a close-based 2a is blind to a session with high `101` / close `99` and will clear a mandate whose order may already have executed. The plan recommends the HIGH (strictly more protective, `DailyBar.high` already exists, and it matches 2a's question rather than the decay conjunct's). The tension to weigh is RD's constraint 6 (*"CLOSES, not intraday touches"*), which governs invalidation rather than entry. §3.3.
15. **BLOCKING — May an earlier same-session PASS override the latest VERIFIED FAIL?** RD ruled on ABSENT sessions; this asymmetry (generous PASS / strict FAIL) is the plan's own policy. **The cost of saying yes:** if every date carries an early passing run and a later authoritative failing run, the streak resets forever and a plainly decaying setup (`98, 95, 92, 89, 86` under a pivot of 100) never clears at all. **The cost of saying no:** a later sentinel erases a real PASS and the latch moves toward withdrawal on a run that never checked it. Both directions are unsafe in some case; the plan picks the one that keeps a mandate ALIVE. §3.2.
17. **BLOCKING — Does an UNVERIFIABLE session PAUSE the streak or BREAK it?** §3.2 omits unverifiable sessions from the sequence, so `FAIL / ABSENT / FAIL / ABSENT / FAIL` clears at N=3 (T4.3) — and so would `FAIL / 20 absent runs / FAIL / FAIL`, assembling a "streak" from structural evidence weeks apart. RD ruled absence is neither failure nor pass; **he did NOT rule whether it pauses adjacency or breaks it**, and the plan chose PAUSE without saying so. A complete price span does not cure missing structural evidence. §3.2, T4.3.
18. **BLOCKING — May an earlier PASS override a LATEST run that did not check the ticker?** OQ-15 asks about PASS-vs-latest-FAIL; this is the neighbouring case the same rule decides — T3.2 makes an earlier PASS beat a later sentinel or absent row, which **suppresses the UNVERIFIABLE render RD explicitly ruled for off-screen latches** (*"must not assert one it never checked"*). Distinct from OQ-15 and needs its own answer. §3.2.
16. **BLOCKING — Does the `framework_withdrawn` rung sit ABOVE or BELOW telemetry health (rung 5)?** Below it, a `criteria_lapsed` latch under a broken beacon labels `telemetry_unhealthy` instead. **Every rate is invariant either way** (both are `unattributable_r`) — only the label moves. The argument for ABOVE: a framework-authored terminal is objective evidence about why the mandate ended, and beacon health has nothing to do with that reason. The other three edges of the placement ARE forced; this one is not. §3.8, T6.11.
7. **A flat, deeply-underwater stock never clears.** RD's word is *WIDENED*, so a name that gaps down and sits still satisfies 2a but never 2b, and only the horizon removes it. This plan will not silently re-engineer his ruling into "below by more than X%". Does he accept the limitation? §3.3.
8. **Does changing N retroactively rewriting history need a mitigation?** Latches are derived, so it is inherent; the sharp edge is that N can flip whether a real position is attributed to its own mandate (§3.2.1 ruling 7, T5.5). Options: accept + disclose (recommended), or freeze N per-latch at fire time (which would need persistence — **schema, routes back**).
9. **Should V1 ship report-only first?** RD states plainly he cannot derive N, and a wrong N destroys a real trade. A report-only mode (the countdown renders; the clear does not fire) would produce the calibration evidence at near-zero cost. **RD ruled `criteria_lapsed` a clear reason and this plan implements it as one** — posed only because he may prefer to observe before arming. The countdown ships regardless.
10. **BLOCKING — What makes a widening MATERIAL?** RD's ruling says *"the shortfall has WIDENED"* and is silent on magnitude, and the silence is load-bearing. With no floor, `99.00, 99.04, 99.03, 99.02, 98.99` against a pivot of 100 clears — a **one-cent** "decay" over five sessions. With an ADR-ONLY floor, a low-ADR name still clears: at `adr_pct = 0.40`, `99.80, 99.90, 99.75, 99.60, 99.30` widens $0.50 past a $0.40 floor and the panel tells the operator to cancel a sub-1% consolidation. This plan therefore recommends **the LARGER of an ADR term and a pivot-relative term** (`adr_multiple = 1.0`, `min_widening_pct = 2.0`), with a NULL `adr_pct` making the latch directionally unverifiable and **no hard-coded substitute ever**. **The calibration is a live lever on the motivating case:** at 1.0×ADR, VSTS (N=3) passes by 13% ($0.77 vs $0.6796); at 1.5× it would not clear at all. §3.3, T4.14/T4.15.
11. **BLOCKING — Which completed-bar interval expresses "across the N evaluated sessions"?** A candidates row stamped session S carries the close of S−1 (§2.2 query 5), so a bar-dated window `[first(W), last(W)]` and a verdict-aligned window shifted back one session are both defensible — and **they give OPPOSITE answers on RD's own worked case once materiality applies** ($0.77 clears vs $0.43 does not). This plan takes the bar-dated reading because it asserts no per-row provenance; but gotcha #30 forbids treating a run stamp as proof of a close's date, which is not the same as authorizing a *later* price series in place of RD's tabulated values. **The trajectory semantics are his and his table uses the other alignment, so it blocks rather than defaults.** §3.3.

---

## §10 The operator witness

Step-by-step per the operator's standing preference; the orchestrator drives one step and waits for his result before the next.

1. `GET /latches` on the live DB. **VSTS (fire 2026-07-27, pivot 16.90) renders UNVERIFIABLE — OFF SCREEN**, not plain `ARMED`, with its streak frozen at 3 of 5 and the sessions that produced it named (07-28, 07-29, 07-30). It is still LIVE and still fillable. **This is the case that motivated the amendment and it is the primary witness.** (Note §2.3(a): the brief describes VSTS as `watch`; it is not, and has not been since 07-30.)
2. The same card offers the **decision (decline) control** and the countdown. **The prepared-order form's presence is whatever 21-B's existing withholding rules decide** (§3.2.1 ruling 4) — an off-screen latch with an uncorroborated close may legitimately be withheld as `regime_undeterminable`, and the witness records which it is rather than requiring one. What IS required and witnessed: the decision control is present EITHER WAY.
3. **FTRE (fire 2026-07-20, pivot 18.34) shows NO `criteria_lapsed` clear anywhere in its history** — it cleared by `fill`. The founding case survives on live data, not only in a fixture. (Its fill date depends on item 5; §2.3(b).)
4. A seeded reversible demonstration of an actual `criteria_lapsed` clear — no live latch has reached N — following the 20-C reversible-seed-helper precedent: the `WITHDRAWN - criteria lapsed` label and the alarm at RD's ruled severity.
5. `swing latches report` shows the withdrawn fire under `unattributable_r`, absent from the away rate and the discipline signal, with the away rate numerically unchanged by its presence.

---

## §11 Risks

| Risk | Mitigation |
|---|---|
| **A false clear destroys a real trade** — the FTRE class | 2a as a LIFETIME property; 2b ends-at-its-low; the materiality floor; T4.1/T4.6/T4.7/T4.14 non-droppable; N config-bound; OQ-9 poses report-only |
| **An archive gap makes 2a an argument from silence** and clears a stock that DID break out | the completeness requirement + `archive_status`; T4.13 |
| **A near-flat consolidation below the pivot reads as decay** | the OQ-10 materiality floor at 1.0×ADR; T4.14 |
| **A later invalidation rewrites an earlier lapse** and re-attributes a fill | L10; earliest-date-wins; T4.9(a)(b) |
| **The clear date walks forward** as the rolling window slides | the earliest-qualifying-window scan; T4.11 |
| **A one-session look-ahead in the trajectory** | L7; the conjuncts are never joined to verdicts; §2.2 query 5 is the evidence; T3.11 |
| **A partial criterion roster produces a false gate verdict** | §3.1 roster check; T2.5's three cases; fails SAFE (UNVERIFIABLE) |
| **A sentinel row erases a valid structural PASS**, so the streak never resets | the ASYMMETRIC rule (§3.2): generous PASS / strict FAIL — **NOT "latest-verifiable wins", which is explicitly rejected for the FAILED half**; T3.2 + T3.3 together |
| **N is underived** | RD says so explicitly; config-bound; the countdown makes it observable before it bites; T5.5 pins the retroactivity |
| **Two implementations of the A+ gate drift** (D6 / item-6) | §3.1 single-sources it; T2.1's literal oracle |
| **`candidates.bucket` used as the gate**, so a capital failure clears a mandate | L4; T2.2 |
| **A partial #11 sweep** | Task 1 one-commit; T1.1/T1.2 iterate the frozenset |
| **The state question smuggles in a migration** | L1; §0; OQ-2 BLOCKS Task 1 |
| **The decision affordance appears to correct something it does not** | §3.2 states the V1-A limitation explicitly; OQ-4 BLOCKS Task 1 |
| **Cross-arc composition** | Serial per brief §0; merge-integration named as a GATE (harness-architecture §5.1). **Two concrete couplings:** item 4 edits `swing/latches/orders.py`, the same file as OQ-1's frozenset; **item 5 moves trade 19's entry_date, which moves this arc's FTRE fixture** (§2.3(b)) |
| **The brief's VSTS premise is stale** | §2.3(a); the witness is built on the off-screen state |
