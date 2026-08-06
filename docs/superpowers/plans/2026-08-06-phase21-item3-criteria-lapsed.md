# Plan — Phase-21 boundary paydown item 3: the `criteria_lapsed` and `declined` latch clear reasons

**Status:** WRITING-PLANS deliverable, **REVISED against RD's rulings of 2026-08-06**. Plan only; nothing here is implemented.
**Base:** `main` @ `73eccb1d` (worktree `.worktrees/criteria-lapsed-plan`, branch `criteria-lapsed-plan`).
**Ruled content:** RD's amendment `20260801T145240Z` **as ruled and corrected by `20260806T114306Z`**. **RD owns the design; this plan owns how to build it.** Where this plan and either message disagree, **the 08-06 rulings govern**.
**Architecture pass:** CHARC, `docs/phase21-boundary-paydown-commissioning-brief.md` §3, as amended by `20260805T235402Z` — **condition 1 WITHDRAWN**, conditions 2–5 stand. **The §3 tripwire remains CLOSED under every ruling below (§0.2).**
**Cells:** planning opus-xhigh (this document) / executing opus-high.
**Gates:** RD merge-blocking (measurement) + operator witness on the latch surface.

---

## §0.1 THE FRAMING RULING — SHIP REPORT-ONLY. Read this before anything else.

**OQ-9 RULED: the automatic `criteria_lapsed` CLEAR sits behind a config arm flag, `criteria_lapse_armed`, DEFAULT OFF.** Everything else ships and runs: the streak, both conjuncts, the countdown, the UNVERIFIABLE render, the disposition machinery, the severity classification, and the whole diagnostic surface.

RD's reasoning, which the plan must not dilute: *"I cannot derive N; a wrong N withdraws a real mandate; and the plan's own honest residual (the declines-then-reverses class is REDUCED, not eliminated) is exactly the class report-only measures before it can bite."* He names it the instrument-before-armed lesson applied to his own rule.

**THE DESIGN CONSEQUENCE THAT MATTERS MORE THAN THE FLAG ITSELF: the resolver must compute the lapse IDENTICALLY whether armed or not, and record what it WOULD have done.** A flag that short-circuits the computation measures nothing, and measurement is the entire purpose. So the unarmed path runs every clause, resolves the would-be terminal, and surfaces `lapse_would_clear_session` — it simply does not emit the terminal. **`criteria_lapse_armed = True` must change exactly one thing: whether the resolved terminal is returned.** T4.20 pins that equivalence.

**The `declined` path (OQ-4) ships ARMED** — it is an operator action, no N is involved, and it delivers the off-screen corrective path immediately. **So this arc ships one armed terminal and one dormant one.**

## §0.2 CONDITION 4 — NOTHING IN THE RULED DESIGN IMPLICATES PERSISTENCE

Re-verified on disk after the rulings, because two of them looked like they might:

| Ruled addition | Persistence? | Evidence |
|---|---|---|
| `criteria_lapsed` clear reason | **No** | `LATCH_CLEAR_REASONS` is a pure Python frozenset; `clear_reason` appears in ZERO migrations |
| **`declined` clear reason (NEW)** | **No** | same set; the latch is DERIVED, the reason is never stored |
| **the `decline` INTENT that authors it** | **No — it already exists** | `LATCH_INTENT_KINDS` (`constants.py:387-389`) and the persisted `CHECK (intent_kind IN ('place','decline','cancel','attest','validity'))` at `0033:346` BOTH already carry it |
| reading those intents in the fold | **No** | `list_intents_for_latch` already exists (`swing/data/repos/latch_order_intents.py:66`) — a READ |
| the `declined` DISPOSITION | **No — it already exists** | `LATCH_DISPOSITIONS` (`constants.py:457`) and `DECISION_DISPOSITIONS` (`:531`); `classification.py:504` already emits it |
| `framework_withdrawn` disposition | **No** | `LATCH_DISPOSITIONS` has no SQL mirror |
| the arm flag + the calibrations | **No** | config dataclass fields |
| Option B state reuse | **No** | that is the point of Option B — the four `LATCH_STATES` CHECK clauses are untouched |

**No migration. No CHECK widening. No new module, dependency, process or carve-out. The tripwire stays CLOSED.**

## §0.3 THE THIRTEEN RULINGS, AND THE SIX RESIDUALS THIS PLAN MUST FLAG

| OQ | Ruling | Where |
|---|---|---|
| **1** | **critical-stale YES** — against CHARC's prior. Severity encodes the operator's outstanding DUTY; fault lives in the DISPOSITION | §3.7 |
| **2** | **OPTION B** — reuse `horizon_expired`, `criteria_lapsed` is the REASON, dedicated label branch. A′ rejected outright | §3.6 |
| **3** | the parity divergence is REAL, INTENDED and MEASURED, with its own monthly line; moot until the flag arms | §9 |
| **4** | **the decline TERMINATES — V1-B, UNIFORM.** New pure-Python reason `declined`; no new intent kind; ships ARMED | §3.2 |
| **7** | flat-underwater never clears: an ACCEPTED limitation, not a TODO | §3.3 |
| **8** | N retroactivity: accept + disclose; a real flipped attribution re-opens it as evidence | §3.2.1 |
| **9** | **REPORT-ONLY; the clear behind an arm flag, default OFF** | §0.1 |
| **10** | two-term floor ADOPTED, defaults 1.0 / 2.0; NULL ADR → UNVERIFIABLE, never a substitute | §3.3 |
| **11** | **BAR-DATED**, ratified on the look-ahead finding | §3.3 |
| **12** | **AMENDMENT A RATIFIED**, both costs accepted | §3.3 |
| **13** | **AMENDMENT B RATIFIED**; strict monotone rejected | §3.3 |
| **14** | **2a tests the HIGH**; invalidation stays close-based | §3.3 |
| **15** | generous PASS ratified **+ the conflict is a DATA-QUALITY SIGNAL, surfaced and counted** | §3.2 |
| **16** | the rung sits **ABOVE telemetry health** | §3.8 |
| **17** | **PAUSE** ratified, on structural grounds | §3.2 |
| **18** | **SPLIT**: within-session PASS beats a later non-verdict; across-session REJECTED | §3.2 |

**SIX RESIDUALS — points the rulings do not reach, flagged rather than silently decided.** Each is an application of a ruled principle to a case RD did not name; none blocks Task 1, and each is a one-line change if he rules otherwise.

* **R1 — `declined`'s STATE mapping.** OQ-2 ruled the state question for `criteria_lapsed`. `declined` needs a non-live state too, and the consistent application of OQ-2's own principle (*"the state enum is a mechanism"*) is to reuse `horizon_expired` with its own label branch. **Applied as an inference; flagged for confirmation.** §3.6.
* **R2 — `declined`'s SEVERITY.** OQ-1 ruled `criteria_lapsed` critical-stale because the alarm encodes DUTY. A resting order behind a DECLINED mandate carries the identical duty and the identical consequence, so the same reasoning puts `declined` in `_CRITICAL_STALE_CLEAR_REASONS`. **Applied as an inference; flagged.** §3.7.
* **R6 — `declined` versus `superseded`.** `superseded` is stamped by the FOLD, not by `_resolve_terminal`, so RD's five-rung ladder does not reach it. The plan rules the DECLINE WINS (a mandate the operator already declined was not live to be superseded, and stamping `superseded` would overwrite his decision with a framework inference) — **an extension of his ladder to a terminal he did not enumerate, so it is flagged.** §3.2, T4.21(n).
* **R5 — may a later decision on a SUCCESSOR latch amend its PREDECESSOR?** The plan rules NO — a decision amends only its own candidate family — because the alternative is circular under candidate-family scoping. §3.2, T4.21(l2).
* **R4 — does "record what it WOULD have done" mean DERIVED or DURABLE?** The plan implements the counterfactual as a DERIVED `Latch` field plus a CLI line — no persistence, consistent with latches being derived at read time. **If RD means a durable append-only series of would-clear observations** (so the calibration evidence survives archive drift, config changes and re-derivation) **that is a new table — a condition-4 STOP.** The derived form is recommended and sufficient for calibration over the report-only window; the durable form is the stronger instrument and costs schema. §0.1, §3.2.1.
* **R3 — the rung versus rung 4.** OQ-16 ruled the rung ABOVE telemetry health (rung 5) and its stated reason — the withdrawal is authored independently of the beacon — extends verbatim to rung 4's `pre_telemetry`. **RD ruled only on rung 5, so the plan places it between rungs 4 and 5 and does NOT extend the reasoning.** §3.8.

---
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

> **⚠ WHAT THIS TABLE IS, per RD's own correction of 2026-08-06 (OQ-11):** *"my 08-01 table was tabulating the EVIDENCE the verdicts consumed — the right table for demonstrating the direction test, the wrong one to inherit as window semantics."* **The SHIPPED window is BAR-DATED** (§3.3). The table above is correct as what it is — a verdict-evidence walk — and must not be read as the interval the resolver uses. Both readings are preserved here precisely because §2.2 query 5 proves they differ by a session that is not reliably one.

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
6. **The VSTS post-anchor HIGHS (OQ-14's input to the acceptance fixture)** — `resolve_ohlcv_window("VSTS", start="2026-07-27", end="2026-07-31", migrate=False)`, reading `high` rather than `close`: 15.85 / 15.74 / 15.61 / 15.32 / 14.74. None reaches the 16.90 pivot.
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

**RULED (OQ-17): an UNVERIFIABLE session PAUSES the streak, it does not BREAK it** — and RD's reason is structural rather than a preference: 2b's completeness requirement makes the PRICE evidence continuous over the whole `[first(W), last(W)]` span (decay must hold across every session of the gap, evaluated or not) and the terminal session of any clear is always a FRESH verified FAIL, so the structural evidence is sparse but bounded by the MANDATORY gap disclosure. *"BREAK would make an off-screen name's real accumulated decay evidence vanish on the day it left the screen — erasing history because the instrument went dark, which my partial-coverage rule forbids."* **The disclosure is therefore not cosmetic — it is the condition under which PAUSE is sound**, which is why §3.2.1 ruling 3 names the sessions rather than only counting them.

That third row IS RD's inverted default, stated once and applied everywhere: *"absent sessions must NOT count toward the decay streak... But they cannot count as passing either... the framework cannot check a mandate it cannot see, and it must not assert one it never checked."*

**THE TWO PREDICATES ARE DELIBERATELY ASYMMETRIC, AND THE ASYMMETRY IS THE WHOLE POINT.** A session can carry several rows — an ad-hoc `swing eval` after the nightly, or a run in which the ticker became held and was appended as a zero-criteria `excluded` sentinel. Two obvious tie-break rules exist and **each is unsafe in one direction**:

* *"the latest row wins"* — a later SENTINEL erases an earlier real FAILURE (harmless) **but also erases an earlier real PASS**, so the streak fails to reset and the latch moves toward a clear on the strength of a run that never looked at it. **Unsafe.**
* *"the latest VERIFIABLE row wins"* — a real verdict is never discarded, **but a FAILED verdict survives a later run that could not check the ticker**, which is asserting from evidence the most recent word contradicts. **Unsafe in the other direction.**

**AND THE STRICT HALF KEYS ON THE LATEST *RUN*, NOT THE LATEST *ROW* — a distinction an earlier draft missed and which is the ordinary case, not an edge case.** When a 09:00 run records a verifiable failure and an 18:00 run does not carry the ticker AT ALL (it went off-screen), the latest ROW belonging to the ticker is still the 09:00 failure — so a row-keyed rule calls the session FAILED even though the most recent run never checked it. Repeated over N sessions that clears a mandate on stale evidence, which is precisely what the strict half exists to prevent. **FAILED therefore requires the LATEST run for that action session to contain a verifiable failing row for this ticker.** T3.12.

So the rule is split by which direction each answer moves the latch. **PASSED is generous (ANY verifiable pass resets)** because resetting keeps a mandate ALIVE, and a live mandate is the conservative outcome. **FAILED is strict (the LATEST word must be a verified failure)** because incrementing moves the latch toward withdrawal, and withdrawal is the outcome that can destroy a trade. Anything else is UNVERIFIABLE. **Order runs by `(run_ts, evaluation_run_id)`, NOT `(run_ts, candidate_id)`.** The strict half asks which RUN was latest even when that run has NO row for this ticker — and such a run has no `candidate_id` to break a `run_ts` tie, so a candidate-keyed order cannot express the question. `evaluation_run_id` is on every run (and `_FIRE_SQL` already selects it); the schema's `UNIQUE(evaluation_run_id, ticker)` (`0001:41`) means at most one candidate per run per ticker, so `candidate_id` is only ever a within-run detail. T3.14 covers the equal-`run_ts` tie.

> **RULED — OQ-15 (generous PASS) and OQ-18 (the SPLIT). The split is the answer, and it scopes T3.2.**
> * **WITHIN a session:** a verified PASS beats a later NON-verdict (a sentinel or an absent row) — *"a non-check cannot erase a check."* **T3.2 stands, scoped to this case.**
> * **ACROSS sessions: REJECTED.** *"An earlier session's PASS never suppresses a later session's UNVERIFIABLE; the tail rule governs unconditionally, because the render is a claim about NOW and the framework must not assert a mandate it has not currently checked."* So `lapse_unverifiable_tail` and the UNVERIFIABLE render are computed with **no reference whatsoever to any earlier PASS** — session-scoped evidence resolution and current-state assertion are different questions. T3.16 pins the across-session half.
>
> The original text of this box is kept below because the costs it names are the ones RD accepted.
>
> **⚠ THIS ASYMMETRY WAS A POLICY THIS PLAN INVENTED — now RATIFIED with the split above.** RD ruled on ABSENT sessions; he did not rule that an earlier same-session PASS should override the latest verified FAIL. The generous half has a real cost in the other direction: if every date carries an early passing run and a later authoritative failing run, the streak resets forever and an unmistakably decaying setup (`98, 95, 92, 89, 86` under a pivot of 100) **never clears at all**. The same generosity can suppress the UNVERIFIABLE render when the latest run has no usable row but an earlier one passed. The safe-direction argument is genuine but it is an ARGUMENT, and T3.2/T3.10 currently encode it as though it followed from the ruling. **RD rules; the plan recommends and states both costs.**

**THE TWO PREDICATES OVERLAP, SO THE PRECEDENCE IS STATED RATHER THAN LEFT TO THE TABLE'S ROW ORDER.** A session with an earlier verifiable PASS and a later verifiable FAIL satisfies both ("ANY pass" and "the latest row is a verified failure"). **PASSED WINS** — evaluate it first and return. **RULED (OQ-15):** *"a session holding conflicting VERIFIED verdicts is AMBIGUOUS, and ambiguity must never advance a withdrawal — the conservative direction here is keep-alive."* The perpetual-reset pathology is accepted and disclosed.

**AND RD ADDED A REQUIREMENT THE PLAN DID NOT HAVE: THE CONFLICT IS A DATA-QUALITY SIGNAL AND MUST BE SURFACED, NEVER RESOLVED SILENTLY.** Two runs for one session disagreeing on the STRUCTURAL VERDICT is a fact about the pipeline, not a tie to be quietly broken — his 21-A same-session-duplicate rule applied here. **The data path, specified end-to-end rather than left as a requirement** (the fields, their owner and the task that carries each):

| Layer | Carries | Task |
|---|---|---|
| `SessionStructuralVerdict` | **`conflicted: bool`** — a FOURTH field beside `action_session` / `classification` / `cause` | 4 (reader) |
| `Latch` | **`lapse_conflicted_sessions: tuple[date, ...]`** — subject to the same `__post_init__` invariants as the other session tuples (strictly ascending, hence unique). **SCOPE: `[anchor, min(bar_bound, horizon_expiry)]` — the ANALYSIS window, deliberately NOT the current streak and NOT truncated at the actual terminal.** A conflicted session classifies PASSED and therefore RESETS the streak, so a streak-scoped tuple would DELETE the conflict the instant it was conservatively resolved — the ambiguity RD required to be surfaced would vanish precisely because it was resolved generously. Lifetime scope is the only one that survives its own resolution.

**AND ONE BOUND GOVERNS EVERY DIAGNOSTIC, STATED ONCE HERE BECAUSE THE ANSWER IS NOT OBVIOUS.** The counterfactual deliberately analyses structural evidence PAST the actual terminal — T4.23(a) computes a D5 qualifying lapse on a latch that actually filled on D4 — so the diagnostics cannot stop at the actual terminal without contradicting the very scan that produces them. **the CONFLICT tuple, the DIRECTIONAL flags and BOTH counterfactual sessions are computed over the ANALYSIS WINDOW `[anchor, min(bar_bound, horizon_expiry)]`** — the same window the hypothetical ladder walks — **while the streak tuples and their counts are CURRENT-STREAK evidence** (see the box in §3.2.1). The consequence a reader must not be surprised by: **a terminal card's ANALYSIS figures describe the analysis window, not the mandate's live life** — so a filled latch can carry a would-clear session dated AFTER its fill. That is correct for calibration (it is what the armed rule would have seen) and the card labels it as analysis rather than history. | 5b (resolver) |
| the card | the sessions NAMED in the detail line | 7 (render) |
| `swing latches report` | the count, as its own line | 7 |

**The count is DERIVED from the tuple** (`len(...)`), never carried alongside it — the same rule §3.2.1 applies to every other count, for the same reason. **T3.15 is a TASK-4 READER test asserting `conflicted=True` on the verdict and NOTHING about the card; T7.13 is the TASK-7 RENDER test asserting the sessions reach it** — an earlier draft made T3.15 span both layers, which no single test can do. That is the same conservative direction the split itself encodes: a session in which the framework at any point judged the setup structurally sound is not evidence of decay. T3.10 pins it, because a table read top-to-bottom by an implementer who never noticed the overlap would classify it FAILED.

Two consequences worth stating because they are easy to get backwards:

* **A re-confirmation resets the streak for free.** A later `aplus` fire is, by construction, a PASSED session. No special case is needed and none should be written.
* **Excluded-because-held is UNVERIFIABLE, not FAILED.** The moment the operator takes a position his ticker becomes `bucket='excluded'` with no criteria. Counting that as a structural failure would let the framework withdraw a mandate *because he acted on it*. In practice the `fill` clear usually pre-empts it, but the rule must be right independently rather than correct-by-luck through another rule's precedence.

#### The render, and why it is not a `LATCH_STATES` member

RD's body says the latch *"stops rendering as plain `armed` and becomes UNVERIFIABLE — awaiting an affirmative decision, with the default inverted."*

> **⚠ A PRESERVE-THE-QUOTE CORRECTION RD ISSUED AGAINST HIS OWN WORDS (2026-08-06), recorded here because earlier drafts of this plan leaned on the misreading.** His 08-01 section header reads *"OFF-SCREEN IS NOT FAILURE, AND IT NEEDS ITS OWN STATE"*, and this plan twice treated that as a possible requirement on `LATCH_STATES`. He rules: ***"it needs its own state" is a MISATTRIBUTION of my ruling — my words were its own DISPOSITION and its own CLEAR REASON.*** The state enum is a mechanism; **everything that must distinguish lapse from horizon — severity, the resolver, the disposition, the render — keys on the REASON, which is first-class.** The header is left standing as what he wrote; the requirement it does NOT carry is now recorded beside it.

**CHARC has already adjudicated which of those two readings binds.** Condition 4, verbatim: *"The off-screen UNVERIFIABLE state is a CLASSIFICATION/render change, not a schema state, unless the plan shows otherwise — if it needs a column, route BACK for a §3 amendment."* This plan does not re-decide that; it shows the "otherwise" does not arise:

* The latch is **still LIVE and still fillable**, so a terminal state would be a false statement.
* The in-tree precedent is exact: **zone escape is an attribute of `armed`, never a terminal state** (21-A plan §A.7.1; encoded at `view_models/latches.py:597-618`; locked by `tests/latches/test_identity.py:92-97`).
* A new non-terminal `LATCH_STATES` member would be schema (§0).

Mechanically: `_state_label` gains an UNVERIFIABLE composition alongside `IN ZONE` / `OUT OF ZONE`, driven by new `LatchRowVM` fields (§3.2.1).

#### The "affirmative decision" — RULED: IT TERMINATES (OQ-4, V1-B, UNIFORM, SHIPS ARMED)

**RD ruled the terminating form, uniformly.** *"A decline is a decline — special-casing off-screen would make the same operator act mean two different things."* So this is NOT an off-screen feature: **a decline terminates ANY live latch**, off-screen or not.

**It is pure Python, and §0.2 verifies every leg of that on disk.** The `decline` intent kind already exists in `LATCH_INTENT_KINDS` (`constants.py:387-389`) AND in the persisted CHECK at `0033:346`; `list_intents_for_latch` (`swing/data/repos/latch_order_intents.py:66`) already reads it. **Nothing schema moves.**

**A NEW CLEAR REASON `declined`** — operator-authored, distinct from every framework-authored terminal. It is the second of the two reasons this arc adds, so **`LATCH_CLEAR_REASONS` goes 4 → 6** and the §4.1 one-commit sweep covers BOTH, including both design mirrors for each.

**The intents reach the pure fold the way `bars` and `entries` already do** — loaded by the reader and passed to `derive_latches`, never a DB read inside the resolver (L8 unchanged). **But the mapping is `decision_intents_by_candidate_id: dict[int, tuple[Intent, ...]]`, and BOTH halves of that name are load-bearing:**
* **`decision_`, not `decline_`** — `governing_decision` resolves the `place`/`decline` FAMILY, so passing declines alone would re-create the exact regression this design exists to fix: `decline(D5) -> place(D6)` would terminate, because the correcting place was filtered out before the resolver could see it.
* **`by_candidate_id`, not `by_ticker`** — a ticker carries MANY historical latches, and a ticker-keyed mapping hands an old mandate's decline to a NEWER latch, terminating a mandate the operator never declined. **Each latch selects the intents whose `candidate_id` is in its OWN candidate family** — the opening fire plus its re-confirmations, which is the same identity rule the fill ladder's exact rung already uses (`service.py:172-175`).
  **AND THE SOURCE OF THAT FAMILY IS `_Draft.candidate_set`, NOT `_Draft.candidate_set` **and its parity with the finalized `Latch.candidate_set`**.** `_resolve_terminal` runs during the fold and receives a `_Draft`, never a finalized `Latch`; the draft already exposes the identical property (`service.py:66-68`, `{self.fire.candidate_id, *self.reconfirmation_candidate_ids}`). Citing the `Latch` property would send an implementer to an object the resolver does not have. **Per latch, the terminal is authored by `governing_decision(admissible)` — the classifier's EXISTING CROSS-KIND resolver (`classification.py:342-358`) — and the latch terminates as `declined` ONLY WHEN THAT WINNER IS A `decline`.**

**THE INTENT SET IS FILTERED BEFORE THE WINNER IS CHOSEN, NEVER AFTER — and an earlier draft of this revision had it backwards.** `admissible` = the decision-family intents whose `candidate_id` is in this latch's `candidate_set` AND whose action session lies in `[anchor, min(fill_bound, horizon_expiry)]`. **Choosing the winner first and rejecting it afterwards gets the as-of semantics wrong in BOTH directions:** with `decline(D5)`, `place(D10)` and a liveness probe as of D6, a global `governing_decision` picks the D10 place, so the D5 decline VANISHES from a probe that should see it; and rejecting an out-of-bound winner does not fall back to the earlier in-bound decision, it simply yields nothing. Filtering first makes the probe answer *"what did the operator's record say AS OF D6"*, which is the only question the probe is asking.

**A NARROWER "latest decline intent" RULE IS WRONG AND WOULD WITHDRAW A MANDATE THE OPERATOR HAD RE-PLACED.** `governing_decision` deliberately resolves the `place`/`decline` FAMILY together — they are *"the two MUTUALLY EXCLUSIVE answers to ONE question"* — so on `decline(D5)` then `place(D6)` the classifier returns `accepted`. A lifecycle keyed on the latest DECLINE would terminate that latch as `declined` at D5 **while the classifier scored it `accepted`**, i.e. the framework would withdraw a mandate after the operator corrected himself and re-placed it. An earlier draft of this revision claimed the two "cannot disagree"; they can, and only sharing the SAME cross-kind resolver makes the claim true. T4.21(i) pins the correction case.

**`declined` VERSUS `superseded` — RULED HERE AND FLAGGED AS RESIDUAL R6, because the five-rung ladder cannot answer it.** `superseded` is stamped by the FOLD (`service.py:369-372`), not by `_resolve_terminal`, so it never enters the rank table at all. The collision is real: a predecessor-family decline and a DIFFERENT-pivot re-fire resolving on the same action session. **RULED: the DECLINE WINS.** The supersede path exists to record that *the setup re-based while the mandate was still live*; if the operator had already declined that mandate, it was not live to be superseded, and stamping `superseded` would overwrite his own recorded decision with a framework inference — the exact inversion RD's `fill > declined > invalidation` ordering forbids. Mechanically the fold must therefore consult the decline BEFORE stamping `superseded`, which the liveness probe's session exclusion would otherwise prevent. **Flagged for RD because it extends his ladder to a terminal he did not enumerate.** T4.21(n).

**AND A LATER `place` LEGITIMATELY ERASES A DERIVED DECLINE TERMINAL — WHICH IS NOT AN L10 VIOLATION, BUT THE PLAN MUST SAY SO.** L10 forbids the RESOLVER rewriting a terminal from LATER EVIDENCE OF THE SAME KIND (a later bar un-clearing an earlier lapse). A later `place` is a different thing: it is **the operator amending his own answer**, and §3.2.1 ruling 6a already establishes that a derived model recomputes when its INPUTS change. **AND THE `decline(D5)` / re-fire `D6` / `place(D10)` CASE NEEDS AN EXPLICIT RULE, BECAUSE CANDIDATE-FAMILY SCOPING MAKES IT CIRCULAR.** At the D6 probe the D5 decline terminates the OLD latch, so D6 opens a NEW latch — and a D10 place recorded against the NEW latch's candidate id is NOT in the old latch's family, so it cannot erase the old decline; while assuming D6 IS in the old family presupposes the outcome. **RULED HERE, and flagged as residual R5 for RD:** a decision intent AMENDS ONLY THE LATCH WHOSE CANDIDATE FAMILY IT BELONGS TO. A later `place` on a SUCCESSOR latch never resurrects its predecessor — the operator placed an order against the NEW mandate, which says nothing about the old one he declined. So the D5 decline stands, D6 opens a new latch, and D10's place governs THAT latch only. The no-re-fire case (§3.2's `decline(D5) -> place(D6)` on the SAME family) is unaffected and still erases the decline. T4.21(l) is split into (l1) no-re-fire and (l2) with-re-fire.

**THE DECLINE SESSION IS BOUNDED LIKE EVERY OTHER TERMINAL, and an unbounded one corrupts the fold.** `decline_session` = the governing decision's `action_session_date`, admitted ONLY when it is **at or before the resolver's `fill_bound`** (the as-of bound, which the liveness PROBE deliberately pulls back to the session before a re-fire, `service.py:246-260`) **and at or before `horizon_expiry`**. Without the first bound an intent recorded on D10 makes the old latch look dead at a D5 probe, corrupting the reconfirmation/supersede topology; without the second, a post-horizon decline overwrites a mandate that had already lapsed — the same cap the invalidation and lapse walks already carry. T4.21(j)(k).

**PRECEDENCE — `fill > declined > invalidation > criteria_lapsed > horizon`** (RD, extending his 08-01 ladder). Operator FACTS beat operator DECISIONS beat framework EVIDENCE beats deadlines. Two consequences the resolver must implement exactly:
* **A fill at or before the decline session WINS** — *"you cannot decline a filled mandate."* So the fill rung's existing `entry.entry_date <= nonfill.session` comparison applies to a `declined` terminal unchanged.
* **`declined` outranks `invalidation` on a SAME-SESSION tie**, and — per L10 — the earliest-dated terminal still wins across different sessions. `declined` therefore joins the earliest-date-wins candidate set with its rank, exactly like `criteria_lapsed`.

**ONE ADMISSIBILITY HELPER, SHARED BY THE LIFECYCLE AND THE CLASSIFIER — otherwise they resolve DIFFERENT governing decisions.** `classify_latch` calls `governing_decision(intents)` with no candidate-family or as-of filtering (`classification.py:498`), so a post-horizon decline that the LIFECYCLE correctly refuses (T4.21(k)) would still reach the CLASSIFIER and emit `declined`, putting the latch in `decision_r` while its terminal says `horizon`. The same split appears for a cross-latch intent. **So the filter is a named helper and BOTH callers use it:**

```
swing/latches/classification.py        # OWNER -- it already owns governing_decision,
                                       # so the filter and the resolver it feeds stay together
def admissible_decisions(intents, *, candidate_set, lower, upper) -> tuple:
    # the place/decline FAMILY whose candidate_id is in `candidate_set` and whose
    # action session is in [lower, upper]. PURE.

classify_latch(..., decision_bounds=None)   # NEW keyword, defaulted
    # None => today's behaviour (no filtering), so every existing caller and
    # fixture is unchanged. Production passes (latch.anchor, min(fill_bound,
    # horizon_expiry)) -- the SAME bounds the resolver used.
```

**THE CLASSIFIER IS BOUNDED BY THE LATCH'S ACTUAL TERMINAL, NOT MERELY BY THE HORIZON — otherwise the lifecycle and the disposition contradict each other on ORDINARY collisions.** With a fill on D4 and a decline on D5, the LIFECYCLE returns `fill` (D4 <= D5, and *"you cannot decline a filled mandate"*) while an unbounded classifier returns `declined` — **putting a FILLED latch into `decision_r` as a decline.** Same for invalidation D3 / decline D5. **So `upper` is `min(clear_session or horizon_expiry, fill_bound)`: a decision recorded AFTER the mandate terminated cannot be a decision about it.** **SAME-SESSION FILL AND DECLINE NEEDS AN EXPLICIT RULE, because an inclusive bound does not deliver it.** With both on D5, `upper = D5` leaves the decline admissible, `governing_decision` selects it, and rung 1 returns `declined` while the lifecycle returns `fill` — so *"ties follow the lifecycle's rank"* is not something the bound achieves on its own. **RULED: when `latch.clear_reason == "fill"` a decision dated ON the clear session is INADMISSIBLE** (strictly-before on that one boundary); for every other terminal the bound stays inclusive. This is the classifier READING the lifecycle's answer rather than re-deriving it. T6.13 asserts the terminal and the disposition TOGETHER, because either alone passes while the two disagree.

**ONLY THE DECISION FAMILY IS FILTERED — the classifier's OTHER intent consumers keep the FULL set, and conflating the two would delete evidence.** `classify_latch` also reads intents for `governing_intent(..., "place")`, `resolve_execution_outcome_for` (which needs its `validity` children) and the attestation rung. **Replacing `intents` wholesale with the helper's output would make attestations, cancels and validity evidence vanish.** So the helper feeds `governing_decision` **and** `governing_intent(..., "place")` — the latter because an out-of-bound or cross-latch place could otherwise still become `governing_place_intent_id` and drive the EXECUTION outcome while a different, in-bound decision drove the DISPOSITION — while every other consumer keeps the unfiltered set. **Two views, named apart: `admissible` and `intents`.** T6.14.

**THE BOUNDS PROBLEM IS REAL AND THIS IS HOW IT IS SOLVED:** a finalized `Latch` does not carry the resolver's `fill_bound`, so the classifier cannot re-derive it. It does not need to — **`fill_bound` equals `horizon_session` on the production path** (`service.py:374-377`), which the caller already holds, and the probe's pulled-back bound applies only INSIDE the fold, never to classification. **Task 5a owns the helper, the `decision_bounds` keyword AND the production call site that passes the bounds** — named in its edit list and in the manifest row, since an earlier draft left the helper without an owner; Task 6 owns the rung. T6.13 pins the pair.

**CLASSIFICATION — the existing decision LADDER is unchanged (no new rung, no new disposition); only the intent SET it is handed is filtered.** A declined latch already classifies `declined` at rung 1-2 (`classification.py:498-504`), `declined` is already in `LATCH_DISPOSITIONS` and `DECISION_DISPOSITIONS`, and `DECISION_SUBKIND` already maps it to `logged`. **No disposition work at all.** RD: *"21-B already treats decline as a terminal decision; this aligns the LIFECYCLE with the classification it already has."*

> **⚠ A MEASUREMENT CONSEQUENCE THE PLAN MUST STATE, because it moves live numbers.** Today a declined latch stays LIVE, so `r_bucket_for` gates it to `pending_r` — *reported, never scored*. Once the decline TERMINATES it, `is_terminal` becomes True and the same latch lands in **`decision_r`**, entering `classifiable_fires` and therefore the away-rate DENOMINATOR. **That is RD's intent** (*"scored, his call"*) and it is the correct direction — a decline is a real decision and belongs in the discipline signal — **but it is a retroactive change to a published denominator, because latches are derived and every past decline is re-classified on the next render.** T6.12 pins the transition; the monthly read should expect the shift once.

**This closes the gap an earlier draft could only name.** The V1-A limitation — *the decision is captured, the stale pivot is NOT corrected* — is gone: the decision now terminates the mandate, which is precisely RD's *"making it a decision point IS the corrective path."*

#### The supersede-disable closure — already true, nothing to build

RD: *"off-screen disables SUPERSEDE. A name that cannot re-fire cannot supersede, so its frozen pivot can go stale with no corrective path... Making it a decision point IS the corrective path."*

Read against the code this is an OBSERVATION about existing mechanics, not a rule to implement. Supersede fires in `_fold_ticker` only when a NEW fire row arrives with a different pivot (`service.py:443-452`); off-screen means no fire row, so supersede is already unreachable. **There is nothing to disable.** An implementer who reads this as "add code to suppress supersede when off-screen" would be writing dead code against a condition that cannot occur. **The corrective path he names is now DELIVERED rather than deferred: under OQ-4 the decline terminates the latch, so the stale frozen pivot is retired by the operator's own decision.**

### §3.2.1 The UNVERIFIABLE / calibration rulings the executor must NOT invent

**The domain, first, because two different absences are NOT the same fact:**

* **A trading session with NO evaluation run at all is OUTSIDE the domain entirely.** It is not an evaluated session for ANY ticker (live: there is no run for 2026-08-05). It is not counted, not rendered as unchecked, and says nothing about this mandate — the framework was not running, which is a fact about the pipeline, not about the setup.
* **A session WITH a run but no verifiable verdict for this ticker IS UNVERIFIABLE** and DOES count toward the rendered tail. The framework ran and did not check this name. That is the state RD's inverted default is about.

`SessionStructuralVerdict` therefore carries `action_session: date`, `classification: PASSED|FAILED|UNVERIFIABLE`, `cause: str | None`, and **`conflicted: bool` (OQ-15)** (`absent` / `sentinel_row` / `incomplete_roster` / `malformed_result`) — the cause is carried so the detail line can explain the tail without the card having to re-derive it.

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
                        decision_intents_by_candidate_id=None,
                        criteria_lapse_armed=False,
                        criteria_lapse_sessions=DEFAULT_...,
                        criteria_lapse_min_widening_adr=DEFAULT_...,
                        criteria_lapse_min_widening_pct=DEFAULT_...)
         # SIX new keyword parameters, all defaulted, so every existing caller
         # and fixture stays valid.
         #
         # `criteria_lapse_armed` IS A PARAMETER, NOT A cfg READ. The service is
         # PURE (L8) and cannot reach `cfg`; it must be threaded
         # build_latch_derivation -> derive_latches -> _fold_ticker ->
         # _resolve_terminal exactly as `horizon_sessions` already is. Its
         # DEFAULT IS FALSE so a caller that forgets it gets the SAFE state --
         # an omitted flag can never silently arm the clear. T5.6 pins the
         # production path (cfg.latches.criteria_lapse_armed reaches the
         # resolver) because a defaulted parameter that production forgets to
         # pass is invisible to every direct-resolver fixture.
         #
         # `decision_intents_by_candidate_id` is the OQ-4 input: the WHOLE
         # place/decline family, keyed by candidate id. NOT declines-only (that
         # drops the correcting place) and NOT by ticker (that hands an old
         # mandate's decline to a newer latch). Section 3.2. `_fold_ticker` receives that ticker's tuple
         # the same way it already receives `bars` and `entries`.
         # verdicts=None or an empty tuple => no lapse is ever resolved (the
         # feature is inert, never a fabricated clear).
```

**THE RENDER DIAGNOSTICS TRAVEL ON `Latch`, NOT RECOMPUTED IN THE VIEW MODEL.** The shipped `Latch` has no streak fields, and Task 7 cannot render what Task 5 does not emit. Recomputing the streak in the VM would be a second implementation of the resolver — the D6/item-6 drift class this arc is already single-sourcing the gate to avoid. So the resolver's working state is surfaced as **trailing defaulted fields on `Latch`**: `lapse_failed_count: int = 0`, `lapse_unchecked_count: int = 0`, `lapse_unverifiable_tail: int = 0`, `directional_evaluable: bool = True`, `directional_block_reason: str | None = None`, **`lapse_failed_sessions: tuple[date, ...] = ()`**, **`lapse_unverifiable_sessions: tuple[date, ...] = ()`**, **`lapse_unverifiable_causes: tuple[str, ...] = ()`**, **`lapse_conflicted_sessions: tuple[date, ...] = ()`** (OQ-15), **`lapse_qualifying_session: date | None = None`** (the conjunct result) and **`lapse_would_clear_session: date | None = None`** (the PRECEDENCE-RESOLVED counterfactual — §3.5; DERIVED, §0.1).

**THE ELEVEN DIAGNOSTIC FIELDS ARE NAMED ONCE, IN `LATCH_LAPSE_DIAGNOSTIC_FIELDS`**, declared beside the dataclass: `lapse_failed_sessions`, `lapse_unverifiable_sessions`, `lapse_unverifiable_causes`, `lapse_conflicted_sessions`, `lapse_failed_count`, `lapse_unchecked_count`, `lapse_unverifiable_tail`, `directional_evaluable`, `directional_block_reason`, `lapse_qualifying_session`, `lapse_would_clear_session`. **T4.20a asserts the roster EQUALS that exact literal set** — an iteration test over a roster that can itself omit a field proves nothing, which is how `lapse_qualifying_session` would have gone missing from the dataclass, the manifest and the comparison at once.

**THE TUPLES ARE THE AUTHORITATIVE REPRESENTATION AND EVERY COUNT IS DERIVED FROM THEM IN `__post_init__`** — `lapse_failed_count == len(lapse_failed_sessions)`, `lapse_unchecked_count == len(lapse_unverifiable_sessions)`, `lapse_unverifiable_causes` PARALLEL to `lapse_unverifiable_sessions` (the same parallel-tuple validation `reconfirmation_candidate_ids`/`reconfirmation_sessions` already carries at `models.py:188-191`), and `lapse_unverifiable_tail` equal to the actual UNVERIFIABLE SUFFIX of the merged, chronologically ordered verdict sequence — not merely `<= lapse_unchecked_count`, which permits an arbitrary tail. **Each session tuple must also be STRICTLY ASCENDING (hence unique) and the two tuples DISJOINT** — a session is failed or unverifiable, never both — because without those a `Latch` can name one session twice or claim a tail it does not have, and the card states a false fact with nothing to catch it. **Counts are DERIVED, never accepted:** `__post_init__` REJECTS a caller-supplied count that disagrees with its tuple rather than silently overwriting it, matching the raise-don't-absorb posture the rest of the module takes. T7.12. Without that, a `Latch` could carry "4 failures" while naming two sessions and the card would state a false fact with nothing to catch it — two independent representations of one quantity is the drift class this arc keeps closing elsewhere.

The last two exist because an earlier draft carried only COUNTS, and counts cannot satisfy two things the plan itself requires: §3.2.1 ruling 2 says the detail line explains the tail by CAUSE (`absent` / `sentinel_row` / `incomplete_roster` / `malformed_result`), and witness step 1 requires the card to NAME the sessions that produced VSTS's streak (07-28, 07-29, 07-30). With counts alone Task 7 could satisfy neither without either inventing fields or recomputing the streak in the view — the duplication §3.1 exists to prevent. T7.10 asserts both are rendered.

**`directional_evaluable` IS DEFINED FOR A PARTIAL STREAK, and the definition is the operator-meaningful one:** it answers *"if this streak reached N, COULD the directional test be evaluated?"* — i.e. lifetime-2a coverage is establishable over `[anchor, latest in-domain session]` (archive status `ok`, no gap, no ambiguous duplicate) AND the fire carries a usable `adr_pct`. It is NOT "2b currently holds" (2b is undefined below N) and NOT a prediction. That is what lets T7.3's partial-streak card say `failed 3 of 5 ... directional test NOT EVALUABLE (archive gap 2026-07-24)` truthfully rather than implying a verdict it has not reached. Trailing + defaulted is what keeps every existing `Latch(...)` construction and every fixture valid (the shipped `bars_available` / `bars_through` fields have exactly this shape). The VM READS them; it never derives them.

**THE TWO COUNTS ARE DIFFERENT QUESTIONS AND ARE DEFINED SEPARATELY** (an earlier draft rendered `<u> unchecked` without saying over what interval, which for `PASS / ABSENT / FAIL / ABSENT / FAIL` could plausibly mean 0, 2, or every unchecked run since the anchor):
> **⚠ TWO REPRESENTATIONS, NAMED APART, BECAUSE ONE SET OF TUPLES CANNOT SERVE BOTH CONTRACTS.** The ANALYSIS-WINDOW rule says the tuples span `[anchor, min(bar_bound, horizon_expiry)]`; the COUNT definitions say they describe the CURRENT streak after the last PASS. On `FAIL D1 / PASS D2 / FAIL D3` a full-window failed tuple is `(D1, D3)` -> count 2, while the current streak is **1**; on `UNVERIFIABLE D1 / PASS D2 / FAIL D3` the full-window unverifiable tuple has length 1 while the defined unchecked count is **0**. **The dataclass cannot satisfy both, and T4.20 would not notice because armed and unarmed can be identically wrong.** So:
> * **`lapse_failed_sessions` / `lapse_unverifiable_sessions` / `lapse_unverifiable_causes` are CURRENT-STREAK evidence** — the interval after the last PASSED session — and the counts are `len()` of them. **These drive the CARD**, which is a claim about the mandate's current state.
> * **`lapse_conflicted_sessions` is ANALYSIS-WINDOW evidence** (`[anchor, min(bar_bound, horizon_expiry)]`), for the reason already given: a conflict resolves to PASS and would delete itself from a streak-scoped tuple.
> * **`lapse_qualifying_session` / `lapse_would_clear_session` are ANALYSIS-WINDOW** results, since the counterfactual deliberately scans past the actual terminal.
> A pre-reset fixture (`FAIL / PASS / FAIL`) pins the distinction — T4.25.

* **`lapse_unchecked_count`** = UNVERIFIABLE in-domain sessions in the interval **beginning immediately AFTER the last PASSED session** (or at the anchor when there is none) **and ending at the latest in-domain session.** For `PASS / ABSENT / FAIL / ABSENT / FAIL` that is **2**. *An earlier draft said "from the first FAILED session of the streak", which for that same example yields **1** and contradicted both the stated answer and T7.9 — the interval must start where the streak's evidence starts, which is after the last reset, not at its first failure.*
* **`lapse_unverifiable_tail`** = the count of CONSECUTIVE UNVERIFIABLE in-domain sessions at the END of the window. This is what drives the UNVERIFIABLE render (ruling 1). For the example above it is **0** (the latest session is a FAIL).

1. **One UNVERIFIABLE session at the TAIL is enough to render UNVERIFIABLE.** The claim being withheld is "the framework checked this mandate for the session you are about to trade", and one unchecked session falsifies it. The tail is counted over consecutive **in-domain action sessions** (runs that happened), most recent first, and the card names the count.
2. **Every UNVERIFIABLE cause contributes to the displayed tail count** — absent row, sentinel row, incomplete roster, malformed result. They are one class to the operator ("we could not check this"), and splitting them on the card would imply a distinction he cannot act on. The CAUSE is in the detail line.
2a. **AN UNUSABLE PRICE HISTORY IS ITS OWN UNVERIFIABLE, RENDERED SEPARATELY.** The structural half and the directional half can fail independently: the gate can be perfectly checkable while the archive cannot support §3.3's completeness requirement (a gap, or `archive_status == 'unavailable'`). The card must NOT show a complete failed streak beside a plain live status while the directional predicate had no data — that would imply the mandate is one session from withdrawal when in fact it is unwithdrawable. `LatchRowVM` carries `directional_evaluable: bool` + its reason, and the countdown renders `failed <k> of <N>, directional test NOT EVALUABLE (<reason>)` in that state.
3. **The countdown renders on every live latch**, not only UNVERIFIABLE ones — and **it discloses the unchecked sessions rather than implying adjacency**: `failed <k> of <N> checked sessions (<u> unchecked)`. **`k` CAN EXCEED `N`, and there are now TWO reasons a latch stays live past the threshold — the card must distinguish them or it states a falsehood.** Once `k >= N`:
   * **the conjuncts REFUSED** (T4.6's shape: lifetime 2a permanently blocking) -> **`<k> failures; threshold <N>; directional condition NOT MET`**;
   * **the conjuncts MET and the feature is UNARMED** -> **`<k> failures; threshold <N>; WOULD WITHDRAW on <lapse_would_clear_session> — REPORT ONLY (not armed)`**.
   **Printing "directional condition NOT MET" in the second case would be a FLAT FALSEHOOD about a condition that DID meet**, on the one surface whose entire purpose is to show the operator what the unarmed rule is doing. `directional_evaluable` does not disambiguate — it says the test COULD run, not that it passed. T7.11 asserts BOTH branches.

   **AND REPORT-ONLY MEASURES THE FIRST HYPOTHETICAL CLEAR PER LATCH, NOT THE WHOLE ARMED CORPUS — AN ACCEPTED LIMITATION, RECORDED RATHER THAN GLOSSED.** Arming changes latch TOPOLOGY (T4.22): a post-lapse same-pivot re-fire RECONFIRMS the old latch when unarmed but opens a NEW latch when armed. So the unarmed derivation never produces that counterfactual successor latch and cannot measure its streak, its directional result, its fill attribution or its decline. **What report-only measures is: for each latch the framework actually derives, would the rule have withdrawn it, and when.** That is the right question for calibrating N and the floors, and it is NOT a full simulation of the armed world. The calibration read must not claim more. (R4's durable-history question is separate: this is about SCOPE, that one is about PERSISTENCE.)

**AND THE COUNTERFACTUAL IS DERIVED, NEVER STORED — which is what keeps this inside condition 4.** `lapse_would_clear_session` is recomputed on every derivation from the same inputs as the armed path; RD's *"record what it WOULD have done"* is satisfied by a DERIVED field on `Latch` plus the CLI report's would-clear line, exactly as every other latch fact is derived. **If RD instead wants a DURABLE historical time series of would-clears — an append-only record surviving archive drift and config changes — that is a persisted table and a CONDITION-4 STOP (L1), not something to improvise.** Flagged in §0.3 as residual R4. The bare form `failed 3 of 5 evaluated sessions` would read as three consecutive sessions when the algorithm skips arbitrarily many UNVERIFIABLE ones in between, so three failures separated by twenty unchecked runs would render identically to three in a row. Making the calibration visible before it bites is the cheapest defence against a wrong N; making the gaps visible is what stops the countdown itself from being a false statement.
4. **UNVERIFIABLE ADDS NO SUPPRESSION OF ITS OWN — and the DECLINE control is INDEPENDENT of the prepared-order form.** Two distinct statements, because an earlier draft ran them together and over-claimed:
   * The prepared-order form's availability is decided ENTIRELY by 21-B's existing rules (`LATCH_ORDER_WITHHELD_REASONS` = `regime_undeterminable` / `sizing_infeasible` / `sizing_degenerate`, `constants.py:432-434`). An off-screen latch with an uncorroborated close may legitimately hit `regime_undeterminable`, and this arc neither changes that nor asserts otherwise. The requirement is only that being UNVERIFIABLE adds NO NEW suppression (T7.4).
   * **The decision (decline) control MUST remain available even when the prepared-order form is withheld.** This is the item-4 principle applied directly — *recording an operator action and alarming on a detected problem are different functions; the affordance to record must not be gated on the alarm that detects* (RD `20260803T110020Z` §3). A latch the framework cannot price is exactly the one whose mandate he most needs to be able to resolve, and gating his answer on the form's availability would re-create the defect item 4 exists to remove, one surface over.
5. **"Default inverted" means exactly this and nothing more:** an unchecked session may not contribute evidence that the mandate is HEALTHY. It never advances the streak, never resets it, and never supports an affirmative render.
6. **A DECLINE TERMINATES THE LATCH, so the UNVERIFIABLE question stops arising for it (OQ-4 RULED).** A terminated latch is not live and renders its `DECLINED - operator declined on <session>` label, not an UNVERIFIABLE armed card. *This ruling REPLACED a drafted V1-A rule which said the opposite — that a decline left the latch live and the state unchanged. That text was an operative executor instruction and is deleted rather than kept as history, because a reader following it would build the rejected design.*
6a. **A TERMINAL IS NOT PERMANENT, BECAUSE THE ARCHIVE IS MUTABLE — and L10 must be read as forbidding a rewrite BY THE RESOLVER, not as promising immutability.** Bounding 2a at the candidate terminal `s` stops a LATER-DATED bar from resurrecting a cleared latch (T4.16), but it cannot stop HISTORY ITSELF from changing: gotcha #26 records that yfinance re-fetches drift historical bars 0.5-3% and that `write_window`'s `drop_duplicates(keep='last')` rewrites them, and a missing bar can be BACKFILLED at any time. So a D3 bar corrected upward to `101` can retroactively disqualify a D5 lapse, and a backfilled D3 can retroactively CREATE one — in both directions changing whether a D6 fill is attributed. **This is inherent to a DERIVED model over a MUTABLE archive and is not fixable inside this arc** (an immutable-archive-snapshot is the standing V2/V3 answer already banked under #26). It is disclosed here, and the claim that lost coverage is "permanently" unestablishable is corrected: it holds only until someone backfills. T4.18.
7. **CHANGING `N` RETROACTIVELY REWRITES HISTORY, AND THAT IS INHERENT, NOT A BUG TO PATCH.** Latches are DERIVED at read time (`build_latch_derivation`), so every past latch is recomputed under the CURRENT config on every render. Raising N can resurrect a previously-lapsed latch; lowering it can withdraw one that used to survive. **The sharp edge:** `_resolve_terminal` counts a fill only when `entry.entry_date <= nonfill.session` (`service.py:301`), so a fill dated AFTER a lapse is not attributed to that latch — meaning **N can flip whether a real position is attributed to its own mandate.** The mitigation is not a mechanism, it is disclosure: N is a deliberate operator/RD calibration, the panel states the N in force, and T5.5 pins the behaviour so a future reader meets it as an asserted fact. Posed to RD as OQ-8.

### §3.3 The directional conjunct

> ### ✅ THIS SECTION PROPOSED THREE AMENDMENTS TO RD'S RULING. **ALL THREE ARE NOW RATIFIED** (`20260806T114306Z`), with their stated costs accepted. The box is kept because the counterexamples are the record of WHY.
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
> **RATIFIED:** A (OQ-12) — *"the failure it prevents is the founding class displaced a week; the ruling would have been wrong without it."* B (OQ-13) — strict monotone REJECTED for the plan's stated reason, *"a rule that never fires is worse than no rule because it looks like coverage."* C (OQ-10) — the two-term floor adopted, *"each term covers the other's blind spot and both counterexamples are real."*
> **Under the framing ruling the constants they introduce are calibration STARTING POINTS measured during report-only, not answers.**



RD: *"The close is BELOW the frozen pivot and the shortfall has WIDENED across the window."* And: *"Conjunct 2 is what makes it safe: FTRE fails it on day 3 (price closed above the pivot); VSTS satisfies it (7.8% → 11.7%, monotone)."*

**THE TWO CONJUNCTS ARE EVALUATED OVER DIFFERENT DOMAINS AND ARE NEVER JOINED ROW-BY-ROW.** §2.2 query 5 is the reason: a candidates row stamped action session S carries the close of **S−1**, so pairing "the verdict for S" with "the archive close dated S" would use tomorrow's price to judge today's verdict — a one-session look-ahead, and gotcha #30 committed inside a rule whose entire safety rests on the price trajectory. The streak counts **evaluated sessions**; the directional test reads **archive bars by their own date**. No bar is ever claimed to be any verdict's input.

**Conjunct 2a — the LIFETIME rule (promoted from a window rule), and it REQUIRES COMPLETE COVERAGE.**

> **RULED (OQ-14): 2a TESTS THE SESSION HIGH.** For a CANDIDATE lapse window whose last failed session is `s`, `criteria_lapsed` is unavailable if ANY archive bar dated in `[anchor, s]` has a **HIGH** at or above the latched pivot (compared at `_PRICE_DP = 2` on both sides)
> **— and 2a may only be ASSERTED when `[anchor, s]` is COMPLETE: `archive_status == ARCHIVE_STATUS_OK` for the ticker AND a bar exists for EVERY NYSE trading session in the range. Otherwise the latch is DIRECTIONALLY UNVERIFIABLE and `criteria_lapsed` is unavailable.**

**THE UPPER BOUND IS THE CANDIDATE TERMINAL `s`, NOT `derivation_session` — AND AN EARLIER DRAFT HAD THAT WRONG IN A WAY THAT BROKE ITS OWN LOCK.** Bounding 2a at "today" means FUTURE evidence can retroactively erase a past terminal: a latch whose D1–D5 closes are `95, 94, 93, 92, 90` lapses on D5, and a D6 close of `105` then makes lifetime-2a fail, **resurrecting a latch that had already cleared — and making a D6 fill attributable to it.** That is precisely the history-rewriting L10 forbids, arriving through the conjunct instead of through the precedence. Evaluating each candidate window's 2a **through that window's own terminal date** makes the answer permanent: once a window qualifies, no later bar can unqualify it. T4.16.

The completeness requirement is not defensive padding — **without it 2a is an argument from silence and the safety guarantee is void.** Concretely, with pivot 100 and five structurally failing sessions whose true closes are `99, 101, 98, 97, 96`, an archive missing the `101` bar leaves the loaded series `99, 98, 97, 96`: no close reaches the pivot, the window ends at its low, and **the rule withdraws the mandate from a stock that DID break out.** 2a's whole claim is "price never traded through the pivot", and a gap cannot support it. This is 21-G's own asymmetry — an absence caused by our ignorance may never license an assertion — and `bar_status_by_ticker` (`ARCHIVE_STATUS_OK` / `_UNAVAILABLE`) already exists and need only be passed down into the fold.

**COMPLETENESS, DEFINED EXECUTABLY** (a safety check whose failure can clear a breakout may not be left to the implementer's judgement): enumerate the NYSE sessions of the closed interval `[anchor, s]` with `swing/evaluation/dates.py`'s `session_offset` + `is_trading_session` — the same helpers `reader.py` and `service.py` already use — and require the SET of session dates present in the eligible bars to EQUAL that enumeration exactly. **Duplicate bars for one date are handled BEFORE any clause reads `B`, and they are not merely "collapsed":** two rows for one date collapse to one ONLY IF THEY AGREE ON EVERY FIELD THE CONJUNCTS READ (to `_PRICE_DP`); any disagreement makes the interval **UNVERIFIABLE**, because the framework cannot say which was that session's bar and `first(B)`, `min(B)` and the widening would all depend on row order. **"Every field the conjuncts read" means the CLOSE and — if OQ-14 selects the HIGH variant — THE HIGH TOO.** A close-only rule is unsafe under OQ-14: two D3 rows both closing `95` but with highs `101` and `99` would collapse silently, and if the `99` row survived, 2a would see no pivot touch and clear a latch whose stop-limit had triggered at `101`. Non-finite values in any read field likewise make the date UNVERIFIABLE. T4.19. Canonicalization happens once, ahead of clauses 1-4, so no clause sees a raw duplicate; non-session bars cannot appear (`reader.py:227-236` already drops them); the upper bound `s ≤ min(bar_bound, horizon_expiry) ≤ derivation_session` is a completed session by construction, so the interval never reaches for a bar that could not exist yet. `archive_status != ok` short-circuits to UNVERIFIABLE before the enumeration.

A window-scoped 2a is likewise unsafe: a breakout close ages OUT of a rolling N-session window, so a stock that broke out successfully and is now pulling back would clear a few sessions later — the FTRE geometry displaced by a week. Once price has traded through the frozen pivot the mandate's premise has been REALIZED: the entry is live as a resting buy-limit at the cap, 21-A's own pullback regime (`expected_mandate_order_type`, `orders.py:109-140`). Withdrawing that would withdraw an entry that is still working.

**TWO WINDOWS, AND CONFLATING THEM RE-CREATES THE RESURRECTION BUG.** The OUTER eligible POOL is `_eligible_bars(bars, anchor=draft.anchor, upper=min(bar_bound, draft.horizon_expiry))` — the same call the invalidation walk makes (`service.py:270-272`), so the two walks cannot drift about which bars exist. **But 2a for a candidate window terminating at `s` reads only the SLICE of that pool dated `<= s`.** Using the outer bound directly would let a bar dated AFTER `s` disqualify that window — exactly the future-evidence resurrection T4.16 exists to catch, re-entering through the pool instead of through the bound. The completeness check applies to the SLICE, `[anchor, s]`.

**Conjunct 2b — the decay test over the streak window.**

**The window, ruled explicitly rather than left to fall out of the code.** `W` = a trailing run of N consecutive FAILED evaluated sessions; `B` = the eligible bars dated in `[first(W), last(W)]`.

> **2b holds iff ALL of:**
> 1. `B` is COMPLETE over `[first(W), last(W)]` — every NYSE session in the span has exactly one canonical bar. (**A separate `len(B) >= 2` clause was drafted and DELETED as unreachable:** with `N >= 2` distinct failed action sessions and complete coverage, `B` necessarily holds at least two session bars, so a fixture with fewer is already incomplete and the guard could never be the reason for a refusal. A test for it would pass under both implementations — the defensive-dead-code class.)
> 2. `last(B).close < first(B).close` — the period ends lower than it began;
> 3. `last(B).close <= min(b.close for b in B)` — the period ENDS AT ITS OWN LOW;
> 4. `first(B).close - last(B).close >= materiality_floor` — **the widening is MATERIAL** (see below).

**THE SCAN ORDER, so the clear date is stable (and so a window that fails now can qualify later).** Walk the failed-session sequence CHRONOLOGICALLY; for each trailing N-failure window in order, test 1–4; **return the EARLIEST qualifying window**, and `lapse_session = last(W)` of that window. This is the only formulation that satisfies both requirements at once: a window failing the conjunct does not end the matter (later windows are still tried — T4.8), and once a window qualifies the answer never moves (re-deriving tomorrow returns the same earliest window — T4.11). "The last N failures" alone would slide the clear date forward every session.

**THE ONE-SESSION QUESTION, ruled, disclosed — AND CONSEQUENTIAL.** `B` spans `[first(W), last(W)]` in BAR dates, while `W` is in ACTION-SESSION dates, and §2.2 query 5 shows those differ by one session. For VSTS's 07-28/29/30 failures, `B` is the bars dated 07-28/29/30 (`15.36, 14.92, 14.59`), whereas RD's table tabulates `15.35, 15.36, 14.92` (the bars dated 07-27/28/29). **The plan takes the bar-dated reading deliberately:** it is a claim about *price action during the period the gate was failing* and asserts nothing about which bar produced which verdict — exactly the provenance claim §2.2 forbids. Shifting `B` back one session to match the verdicts would re-introduce that assertion as an arithmetic assumption.

**The two readings DISAGREE on the motivating case once materiality is applied, so this is not a cosmetic choice.** On VSTS at N=3 with the recommended 1.0×ADR floor of **$0.68** (rounded; `0.6796` unrounded): the bar-dated window widens `15.36 → 14.59` = **$0.77** and CLEARS; the verdict-shifted window widens `15.35 → 14.92` = **$0.43** and does NOT. **RULED (OQ-11): BAR-DATED**, on this plan's own look-ahead finding — *"the verdict-shifted reading requires the one-session offset to be FIXED, and the plan's own look-ahead finding establishes it is not; encoding it would bake an unreliable offset into the semantics."* **And RD corrects his own table's ROLE rather than its values:** *"my 08-01 table was tabulating the EVIDENCE the verdicts consumed — the right table for demonstrating the direction test, the wrong one to inherit as window semantics."* It stays quoted in §1 as exactly that: a verdict-evidence walk. (At the SHIPPED default N=5 VSTS has only three failed sessions and clears under neither reading, so nothing live turns on it today; the fixture and the calibration do.)

* **No division, no percentage.** The pivot is fixed across the window, so "the shortfall widened" is exactly "the close is lower".
* **PRECISION IS STATED FOR EVERY CLAUSE, INCLUDING CLAUSE 4.** All four clauses normalize to `_PRICE_DP = 2` FIRST and compare the normalized values: **2a compares `round(bar.high, 2)` against `round(pivot, 2)`** (OQ-14 RULED — the HIGH, not the close; an earlier draft of this revision left "close" here after the ruling); clauses 2–3 compare rounded closes; **clause 4 ROUNDS THE WIDENING ITSELF — `round(first_close - last_close, _PRICE_DP) >= round(floor, _PRICE_DP)` — rounding AFTER the subtraction, never before.** Rounding each operand first does NOT help and an earlier draft specified exactly that: verified on this box, `round(64.02, 2) - round(61.02, 2)` is still `2.999999999999993`, because rounding a float returns a float, not a decimal. Only `round(64.02 - 61.02, 2)` yields `3.0`. (Integer cents or `Decimal` are equally correct; the point is that the normalization must come after the arithmetic.) Leaving clause 4 unspecified would let a `$2.00` widening the panel displays as exactly `$2.00` evaluate as `1.9999999998` and refuse — or the reverse — flipping a terminal while the card shows equality, which is the price-precision-parity gotcha landing on the one comparison that withdraws a mandate. T4.17 pins the exact-equality boundary in both directions.
* **Clause 3 is load-bearing.** A bare endpoint test clears a stock that collapsed then recovered hard: over `95.00, 80.00, 85.00, 90.00, 94.99` against a pivot of 100, every close is below the pivot and the last is a penny under the first — an endpoint-only rule withdraws the mandate from a name that has rallied 19% off its low and is about to cross the pivot.
* **CLAUSE 4 IS NEW AND IT CLOSES A REAL HOLE.** Without a materiality floor, `99.00, 99.04, 99.03, 99.02, 98.99` against a pivot of 100 satisfies clauses 1–3: nothing reaches the pivot, the window ends at its low, and the "widening" is **one cent over five sessions.** That is a tight consolidation immediately beneath the pivot — the most constructive pre-breakout shape there is — and the rule would withdraw the mandate on the eve of the move. RD's ruling says *"the shortfall has WIDENED"* and does not say by how much, so **a materiality threshold is a genuine gap in the ruling, posed as OQ-10 and now **RULED — the two-term floor ADOPTED, defaults 1.0 / 2.0** — not silently defined as "one rounded cent is enough."**

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

**⚠ WHY 2a TESTS THE HIGH (OQ-14 RULED) — a CLOSE-based 2a would not see an intraday pivot cross, and the "traded through the pivot" justification would be narrower than it sounds.** The mandate is a GTC **STOP_LIMIT triggered at the frozen pivot** (`constants.py:149-167`), so it fires when price TOUCHES the pivot intraday, not when it closes above it. A session with high `101` and close `99` against a pivot of `100` therefore filled — or could have filled — the operator's resting order, while a close-based 2a sees nothing: with closes `99, 98, 97, 96, 95` every clause passes and the latch clears on D5, **withdrawing a mandate whose order may already have triggered.** So *"once price has traded through the frozen pivot, amendment A makes it permanently immune"* is true ONLY of a close at or above the pivot, and an earlier draft claimed the stronger thing.

**RULED (OQ-14): 2a TESTS THE SESSION HIGH.** RD: *"the mandate is a stop-limit that TRIGGERS ON A TOUCH; 2a's question is was the entry trigger reached, and the touch is the fact."* His constraint 6 (*"closes, not intraday touches"*) **stands untouched for INVALIDATION** — a different question (did the mandate die) — and he names the asymmetry as principled: *"both choices err toward mandate-preservation — high-based 2a immunizes more latches; close-based invalidation kills fewer."* `DailyBar` already carries `high` (`models.py:83-98`), so it costs nothing; it is strictly MORE protective; and it matches 2a's actual question — *was the entry trigger reached?* — rather than borrowing the decay conjunct's close semantics. `DailyBar` already carries `high` (`models.py:83-98`), so it costs nothing, and duplicate-bar canonicalization must include the high (§3.3) — which OQ-14 makes unconditional rather than branch-conditional.

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
    # OQ-9 RULED: report-only first. The CLEAR is dormant until this is armed;
    # every diagnostic, the countdown, the render and the disposition machinery
    # ship and run regardless. `declined` is NOT gated by this -- it is an
    # operator action with no N in it and ships armed.
    criteria_lapse_armed: bool = False
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
        if not isinstance(self.criteria_lapse_armed, bool):
            raise ValueError("criteria_lapse_armed must be a bool")
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

### §3.5 Precedence: `fill > declined > invalidation > criteria_lapsed > horizon` (RULED, OQ-4)

`_resolve_terminal` (`service.py:225-303`) already implements `fill > invalidation > horizon` as: walk for invalidation → else horizon → then compare a fill by date.

**EARLIEST DATE WINS; RANK BREAKS TIES. A NAIVE "CHECK INVALIDATION FIRST" STRUCTURE IS WRONG AND REWRITES HISTORY** — an earlier draft of this plan had it, and the failure is worth recording because it is silent:

> A latch lapses on D5. On D8 the close finally breaks the frozen stop. A resolver that scans the whole eligible bar range for invalidation BEFORE considering the lapse finds D8 and stamps `invalidation/D8` — **retroactively changing a terminal that had already resolved three sessions earlier.** Worse, the fill rung then compares against D8 instead of D5, so a fill on D6 satisfies `entry_date <= nonfill.session` and is attributed to a mandate the framework had already withdrawn — contradicting this plan's own T4.9(d) and T5.5.

A terminal is an event with a DATE; the first one to occur ends the mandate, and nothing later can un-happen it. Rank matters only when two terminals land on the SAME session:

```
_RANK = {"declined": 0, "invalidation": 1, "criteria_lapsed": 2}   # ties only

inval_session   = first eligible bar (anchor..min(bar_bound, horizon_expiry))
                  closing below the stop
decline_session = governing decline intent's action session, or None
lapse_session   = _resolve_criteria_lapse(...) or None
                  # ALWAYS COMPUTED -- see the arm flag below

candidates = [("declined", decline_session), ("invalidation", inval_session)]
if criteria_lapse_armed:                    # <-- THE ONLY THING THE FLAG GATES
    candidates.append(("criteria_lapsed", lapse_session))
candidates = [c for c in candidates if c[1] is not None]
if candidates:
    # EARLIEST DATE FIRST; RANK ONLY BREAKS A SAME-SESSION TIE.
    nonfill = min(candidates, key=lambda c: (c[1], _RANK[c[0]]))
elif sessions_behind(...) >= horizon_sessions:
    nonfill = _Terminal("horizon", draft.horizon_expiry)
```

**THE ARM FLAG GATES ONE LINE, AND THAT IS THE WHOLE DESIGN (§0.1).** `lapse_session` is resolved on EVERY path, armed or not, and only the `candidates.append` is conditional.

**BUT THE RECORDED COUNTERFACTUAL IS THE PRECEDENCE-RESOLVED ONE, NOT THE RAW QUALIFYING SESSION — AND CONFLATING THEM MAKES REPORT-ONLY LIE.** With an invalidation on D3, a fill on D4 and a qualifying lapse on D5, the ARMED resolver clears by fill; a field that simply echoes `lapse_session` would nonetheless report *"would withdraw on D5"* — measuring a withdrawal the armed rule would never have performed, and inflating exactly the count the calibration decision reads. So **TWO fields, named apart:**
* **`lapse_qualifying_session`** — the earliest window that satisfies the conjuncts. The streak/conjunct diagnostic.
* **`lapse_would_clear_session`** — **populated ONLY when a side-effect-free re-run of the ENTIRE terminal resolution, INCLUDING THE FILL PASS, resolves to `criteria_lapsed`.**

  **"A SECOND `min(...)` OVER THE CANDIDATE LIST" IS NOT THE FULL LADDER AND WOULD STILL OVER-REPORT.** The fill is NOT in that list — it is a separate `_match_fill` pass whose window depends on `effective_end`, i.e. on which non-fill terminal won (`service.py:289-302`). So a `min(...)`-only counterfactual misses a FILL-ONLY collision entirely: with a fill on D4, a qualifying lapse on D5 and NO earlier non-fill terminal, the armed resolver clears by `fill` while the defective counterfactual reports *"would withdraw on D5"*.

  **The implementable form is ONE shared ladder invoked TWICE** — the counterfactual pass with `dry_run=True` and the lapse forced IN, then the actual pass with the configured arm state. `_resolve_terminal` ALREADY carries `dry_run` for exactly this purpose (*"a probe never consumes a trade the real resolution must see"*, `service.py:260`), so the machinery exists and **only the ACTUAL pass may consume a trade.** No second implementation of the ladder, and no possibility of the two drifting. **A flag placed anywhere earlier — skipping the streak fold, the conjuncts, or the diagnostics — would make report-only measure nothing, which defeats the ruling that created it.** T4.20 pins the equivalence: for one fixture, armed and unarmed must produce IDENTICAL diagnostics and differ ONLY in `clear_reason`/`state`.

`declined` carries rank 0 because RD ruled operator decisions above framework evidence; the fill rung is unchanged, so a fill at or before the decline session still wins.

The horizon stays last: both walks are capped at `horizon_expiry`, so neither can resolve after it, and the horizon applies only when neither fired. The fill rung is UNCHANGED (`entry.entry_date <= nonfill.session`) and now compares against the genuinely earliest terminal.

**T4.9 therefore tests SAME-SESSION collisions AND the later-invalidation case**, because two terminals on different dates pass under either structure and prove nothing.

**The lapse resolution is bounded by `min(bar_bound, horizon_expiry)`, mirroring the invalidation walk's cap verbatim and for the identical reason** (`service.py:263-269`): once the mandate is dead, a later structural failure is not a withdrawal *of it*, and letting one through would overwrite `horizon_expired`, move the clear session forward, and change a stale-order alarm's severity for a mandate that had already lapsed.

`lapse_session` = **the action session of the Nth failed evaluated session in `W`**, i.e. `last(W)` — not the session the derivation happens to run on. The clear must be dated when it happened, or re-deriving next week would move it (T4.9).

**The resolver reads the `bars` list already passed into `_resolve_terminal`, NOT `LatchDerivation.archive_closes`.** The latter is built in `derive_latches` AFTER `_fold_ticker` returns (`service.py:530-543`), so it cannot be an input to the fold. Same data, no new plumbing, and no circular dependency.

**Bound selection:** the lapse uses `bar_bound` (the backward anchor), because it is a judgement about completed sessions' closes and completed evaluation runs. The liveness PROBE therefore cannot see a lapse at the re-fire session itself, consistent with how the probe already treats invalidation (`service.py:246-260`).

### §3.6 The state representation — RULED: OPTION B (OQ-2)

`Latch.__post_init__` requires `state in LATCH_STATES`, `clear_reason in LATCH_CLEAR_REASONS or None`, and **`state in _LIVE_STATES ⟺ clear_reason is None`**. So `criteria_lapsed` needs a NON-LIVE state: one of `filled`, `invalidated`, `horizon_expired`, `superseded`, or a new one.

**Option A — a new `LATCH_STATES` member (`criteria_lapsed`).**
Consistent with the arc's own precedent: `superseded` was made distinct deliberately (`constants.py:116-122` — *"deliberately DISTINCT from `horizon` so 21-B can separate 'unfilled because the setup re-based' from 'unfilled because it went stale'"*). **RULED AGAINST (OQ-2):** a two-table CHECK rebuild *"would buy nothing the reason does not already provide"*, and the header this plan cited as support for it was a misattribution (see the correction in §3.2).
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

**RULED — OPTION B.** RD (consulted; CHARC holds schema authority and the tripwire stays closed): the reason is first-class and carries every distinction that matters; **A′ is REJECTED OUTRIGHT for weakening a shipped #11 guard.** T1.3's caller-side pins are the ratified mitigation.

**RESIDUAL R1 — `declined` NEEDS THE SAME DECISION AND RD RULED ONLY `criteria_lapsed`.** `declined` is also a non-live terminal, so it also needs a state. The consistent application of OQ-2's own principle is **`declined` → `horizon_expired` with its own dedicated label branch** (`DECLINED - operator declined on <session>`), leaving `filled`/`invalidated`/`superseded` untouched and their meanings intact. **This is an INFERENCE from a ruled principle, not a ruling; it is flagged in §0.3 and is a one-line change if RD prefers otherwise.** Three reasons map to one state after this arc, which is exactly what OQ-2 says the state enum is for.

### §3.7 Is `criteria_lapsed` critical-stale? — RULED: YES (OQ-1)

`_CRITICAL_STALE_CLEAR_REASONS = frozenset({"invalidation", "superseded"})` (`orders.py:56`) selects `critical` vs `warning` for the `ORDER_RESTING_LATCH_CLEARED` alarm (`orders.py:776-778`) — the alarm telling the operator to cancel a resting order behind a dead mandate.

**RULED YES — RD, against CHARC's prior, and the plan's own counter-argument is what decided it.** RD: *"blame already lives where I put it: in the DISPOSITION (`framework_withdrawn`, excluded from the discipline signal). The ALARM channel encodes the operator's outstanding DUTY and its consequence, not fault"* — his own item-4 principle. The duty (cancel a resting order behind a dead mandate) and its consequence (an unmandated fill on a rally through a retracted pivot) are identical to the invalidation case. **Severity follows duty; fault follows disposition.**

The prior that was ruled against, kept for the record: **NOT critical-stale** — `invalidation` and `superseded` mean the mandate is WRONG, whereas `criteria_lapsed` means the framework WITHDREW it; that is RD's own its-own-disposition reasoning applied to severity.

The argument on the other side, so RD rules on both: an order resting behind a withdrawn mandate is just as *outstanding* as one behind an invalidated mandate — the manual duty (cancel it) is identical, and severity here encodes DUTY, not blame.

T1.4 pins BOTH reasons as literals so neither can drift silently.

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

**RULED: the classifier rung goes AFTER rung 4 (the coverage table) and BEFORE rung 5 (telemetry health).** Three edges were forced by the plan's own analysis; the fourth was ruled by RD at OQ-16.

* **It must be BELOW rungs 1–3.** Those are operator ground truth. If he placed an order, that stays `accepted` — a later withdrawal cannot retroactively un-decide what he did.
* **RULED (OQ-16): THE RUNG SITS *ABOVE* TELEMETRY HEALTH.** RD: *"the withdrawal is authored by the structural-verdict + archive chain, which is INDEPENDENT of the view-telemetry beacon — labelling it `telemetry_unhealthy` asserts a false cause."* **The refinement he asks to be recorded: rung 5 gates classifications that DEPEND on view telemetry (away / lapse / attest); it must not swallow classifications that do not.** Rates are invariant either way; the label follows its evidence. T6.11.
* **RESIDUAL R3 — RUNG 4 IS *NOT* RULED AND THIS PLAN DOES NOT EXTEND THE REASONING.** OQ-16's argument (the withdrawal is authored independently of the beacon) applies verbatim to rung 4's `pre_telemetry`, which is equally a telemetry-coverage claim. **RD ruled only on rung 5, so the rung is placed BETWEEN rungs 4 and 5** and a `criteria_lapsed` latch in an uncovered window still labels `pre_telemetry`. Flagged in §0.3; T6.7 pins the placement as ruled, and the extension is a one-line move if he wants it.
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

**Every Python mirror of the latch clear-reason vocabulary lands in ONE commit (Task 1) — and after the OQ-4 ruling that vocabulary grows by TWO, not one: `LATCH_CLEAR_REASONS` goes 4 → 6 (`criteria_lapsed` + `declined`). Every row below carries BOTH, including both design mirrors for each.** The inventory was produced by grepping the VALUES as quoted literals across `swing/`, `tests/`, `scripts/` and `research/` — not the constant NAME, which would have returned only `constants.py` and `models.py` and missed all three that matter.

### §4.1 Clear-reason mirrors — the complete set

| # | Site | Edit | Nature |
|---|---|---|---|
| 1 | `swing/latches/constants.py:123-125` `LATCH_CLEAR_REASONS` | add **`"criteria_lapsed"` AND `"declined"`** | canonical; 4 -> 6 |
| 2 | `swing/latches/models.py:173-176` | **none** — imports #1 | derives |
| 3 | `swing/latches/service.py:46-51` `_STATE_BY_CLEAR_REASON` | **BOTH** map to `horizon_expired` (OQ-2 ruled; `declined` per residual R1) | state-machine design |
| 4 | `swing/latches/orders.py:56` `_CRITICAL_STALE_CLEAR_REASONS` | add **`"criteria_lapsed"` (OQ-1 RULED) and `"declined"` (residual R2)** | severity design |
| 5 | `swing/latches/classification.py:401` `clear_reason == "fill"` | **none** — reviewed, correct | single-value equality; a withdrawal is not a fill |
| 6 | `swing/web/view_models/latches.py:597-618` `_state_label` | add **TWO** branches — `WITHDRAWN - criteria lapsed on <session>` and `DECLINED - operator declined on <session>` — so neither ever renders `HORIZON EXPIRED` | render |
| 7 | `swing/web/view_models/latches.py:94-98` `_TERMINAL_STATE_LABELS` | **none** under Option B (#6 pre-empts it, as it does for `superseded`) | render |
| 8 | `swing/web/templates/latches.html.j2:54-57` | **none** — renders `row.clear_reason` verbatim | render |
| 9 | `tests/latches/test_identity.py:69` `test_locked_constants` | update the asserted set to the SIX reasons | **lock test — same commit** |
| 10 | `tests/latches/test_close_provenance.py:28` | **none** | **inspected**: the vocabulary grep hit is a DOCSTRING mention of "the 21-A `LATCH_STATES` precedent", not a mirror |
| 11 | `docs/rd-state.md:50` | update | doc mirror; reads FALSE after Task 1 |
| 12 | `swing/latches/service.py:239-245` | update **in Task 5a** | **NOT a clear-reason VALUE mirror, so it is deliberately OUT of Task 1's one-commit sweep** — it is a PROSE description of the precedence, which Task 1 does not change and Task 5a does. Listing it here without that distinction made the "every mirror in ONE commit" claim false. | the `_resolve_terminal` docstring describes THREE passes and the precedence `fill > invalidation > horizon`. **Task 5 reverses both** (a fourth terminal; earliest-date-wins with rank as tiebreak). A docstring that survives the change it describes is the D21 decay class. |
| 14 | `swing/latches/constants.py:535-536` | **update** | the comment claims deriving `UNATTRIBUTABLE_DISPOSITIONS` by subtraction makes an overlap *"UNREPRESENTABLE rather than merely tested-against"*. **§3.8 proves that false** (`DECISION_DISPOSITIONS` is not subtracted). Task 6 corrects the comment; adding T6.10 beside a comment that still claims the guarantee would leave the next reader trusting it. |
| 13 | `swing/latches/service.py:479-484` | update | `derive_latches` states that `bar_status_by_ticker` is *"pass-through display/provenance context: the FOLD, the eligible set and `_finalize` do not consult either"*. **Task 5 makes the fold consult it** (2a's completeness gate), so the sentence becomes false. |

**WHAT COUNTS AS A "MIRROR" FOR TASK 1'S SWEEP — stated because the plan was applying the word inconsistently.** A **MIRROR** is a site that ENUMERATES THE VOCABULARY: a frozenset of reasons, a reason->state map, a reason->label branch, a reason->severity set. Those all land in Task 1. A site that BRANCHES ON ONE REASON TO PRODUCE NEW BEHAVIOUR is **not** a mirror but a FEATURE, and lands with its feature — the `framework_withdrawn` classifier rung (Task 6) requires a disposition vocabulary that does not exist at Task 1, and the `declined` terminal (Task 5a) requires the intent plumbing. **The test of the distinction: after Task 1 the six-value vocabulary is COMPLETE and CONSISTENT at every site that enumerates it, so no site can be handed a reason it does not know** — which is exactly what #11 protects against — while behaviour arrives with its own task.

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

**TASK 0 — RE-VERIFY THE PREMISES (no commit).** The §2.1 evidence note requires the named source premises to be re-checked on the tree before they are relied on: `DailyBar.high` and its validation, `FireRow`'s field order, `_FIRE_SQL`'s raw hydration, `evaluation_runs.run_ts` ordering, the non-session-bar filter, the NYSE-calendar helpers, `governing_decision`'s signature, and `Latch.candidate_set`. Referenced repeatedly by earlier drafts and never listed as a task; it is one now.

**GATE 0 — DISCHARGED.** All thirteen questions were ruled on 2026-08-06 (§0.3), and the answers select branches this plan designed: Option B, both amendments, the two-term floor, bar-dated, HIGH, PAUSE, the split, the rung above health. **Task 1 may start.** The three residuals (§0.3) are flagged for RD's confirmation and block nothing.

**THE SECOND GATE-0 CONDITION SURVIVES AND IS NOW FORWARD-LOOKING:** if any residual is later ruled against this plan's inference, or if the arm flag is set, **the plan returns for revision before that change is made** — a re-plan is cheaper than an executor improvising a director's semantics.

**THE ORDER BELOW IS CONFIG-BEFORE-EMITTER, DELIBERATELY.** An earlier draft resolved the lapse (Task 4) before wiring `[latches]` (Task 5), which would have left an intermediate production commit deriving `criteria_lapsed` from the module DEFAULT instead of the bound calibration — a live commit violating L5 for the length of one task.

**Task 1 — the vocabulary + EVERY Python mirror, ONE COMMIT (#11).**
`LATCH_CLEAR_REASONS` += **`criteria_lapsed` AND `declined`**; BOTH `_STATE_BY_CLEAR_REASON` entries; BOTH additions to `_CRITICAL_STALE_CLEAR_REASONS`; BOTH `_state_label` branches; `tests/latches/test_identity.py:69`; `docs/rd-state.md:50`. No emitter yet — the value is legal and simply never occurs, so no commit boundary sees an inconsistent vocabulary.
`feat(latches): Task 1 — criteria_lapsed joins the clear-reason vocabulary with every Python mirror`

**Task 2 — single-source the structural gate.** The characterization table FIRST (T2.1, green against the shipped `bucket_for`), then `StructuralInputs` + `structural_inputs_from_results` + `structural_gate_passes` + `EXPECTED_TT_CRITERIA` / `EXPECTED_VCP_CRITERIA` + the roster drift-pin (T2.7), then `bucket_for` refactored to compose them, signature unchanged.
`refactor(evaluation): Task 2 — extract the A+ structural gate as the ONE authority`

**Task 3 — the config calibration (BEFORE any emitter).** `LatchesConfig` with **ALL FOUR fields — `criteria_lapse_armed` (bool, default False), `criteria_lapse_sessions` (≥ 2), `criteria_lapse_min_widening_adr` (1.0), `criteria_lapse_min_widening_pct` (2.0)** — the exact roster T5.1 parses the tracked TOML for + `Config.latches` + `load()` wiring + `DEFAULT_CRITERIA_LAPSE_SESSIONS` + the mirror-drift test + the `swing.config.toml` `[latches]` block.
`feat(config): Task 3 — the four latch calibrations, arm flag included, bound not literal`

**Task 4 — the reader, STANDING ALONE.** `FireRow.adr_pct` + the `_FIRE_SQL` hydration; `structural_inputs_from_rows` with the roster check; `load_session_structural_verdicts` with the §3.2 asymmetric classification. Read-only SELECTs; malformed rows degrade to UNVERIFIABLE. **It does NOT wire `build_latch_derivation` into `derive_latches`'s new parameters** — those do not exist until Task 5, so wiring here would either call a signature that is not there or force premature service edits, and the task could not be green at its own boundary. Its tests (T3.x) exercise the reader functions directly, which is what makes it a standalone red→green cycle. T3.11 and T3.13, which assert a LAPSE outcome, belong to **Task 5** for the same reason.
`feat(latches): Task 4 — per-session structural verdicts, roster-validated`

**Task 5a — THE `declined` TERMINAL (ships ARMED, and is INDEPENDENT of the lapse machinery).** The reader's `decision_intents_by_candidate_id` load — the WHOLE place/decline family keyed by candidate id (via the existing `list_intents_for_latch`); the governing-decline resolution reusing `classification.py`'s `(recorded_ts, intent_id)` order; the `declined` terminal in the earliest-date-wins candidate set at rank 0; the fill-wins-at-or-before rule. **Sequenced BEFORE the lapse work deliberately: it is armed, it delivers the operator's corrective path, and it must not be blocked behind a dormant feature.** **It corrects the PRECEDENCE docstring (§4.1 row 12) — Task 5a is the first task to falsify it.** The PRECEDENCE docstring (§4.1 row 12) is corrected HERE in 5a — the first task to falsify it — while the `bar_status_by_ticker` pass-through docstring (row 13) is corrected in **Task 5b**, which is where the completeness check first consults it; rewriting it in 5a would describe behaviour that does not yet exist.
`feat(latches): Task 5a — a decline terminates the mandate (the corrective path, armed)`

**Task 5b — the lapse resolution as a HYPOTHETICAL ONLY. It does NOT insert a terminal.** It computes the streak, both conjuncts, the earliest qualifying window and `lapse_would_clear_session`, and surfaces every diagnostic — **but the lapse enters the candidate list ONLY on the DRY-RUN counterfactual invocation, never on the actual one — so no latch can clear by `criteria_lapsed` at this commit.** *An earlier draft said nothing entered the list at all, which made the task impossible on its own terms: without a forced-lapse dry-run pass, 5b cannot distinguish a clean hypothetical from T4.23's fill-precedence loser, and the executor would have to invent an interim second implementation or falsely copy `lapse_qualifying_session` across.* **T4.23 lands HERE, in 5b.** Task 5c then adds only the ACTUAL invocation's one-line conditional inclusion. *An earlier draft had Task 5b implement the terminal and Task 5c add the gate afterwards, which would have shipped an ARMED clear at a commit boundary in direct contradiction of the default-OFF ruling.* **The terminal insertion and its gate land ATOMICALLY in Task 5c.** `_resolve_criteria_lapse` (the chronological earliest-qualifying-window scan); conjuncts 2a/2b over `_eligible_bars` with the completeness requirement; the earliest-date-wins terminal selection; the `min(bar_bound, horizon_expiry)` cap; `bar_status_by_ticker` threaded into the fold; the `Latch` diagnostic fields; **the FOUR new `derive_latches` keyword parameters** — `structural_verdicts_by_ticker` PLUS the three calibrations — each defaulted (§3.2.1); **and only now `build_latch_derivation` passing the reader's verdicts and `cfg.latches` through.** **The `bar_status_by_ticker` pass-through docstring (§4.1 row 13) is corrected HERE**, in the task whose completeness check first consults it; the PRECEDENCE docstring (row 12) was corrected in Task 5a, the task that falsified it. *Each docstring is fixed by the task that makes it false — never earlier (describing behaviour that does not exist yet) and never later (shipping a commit whose docstring contradicts its own code).*
`feat(latches): Task 5b — the lapse hypothetical and its diagnostics (no terminal yet)`

**Task 6 — the measurement disposition. RE-SEQUENCED BEFORE TASK 5c, and the reason is a live harm.** Task 5c is the first commit at which `criteria_lapse_armed=True` can emit a terminal (T5.6 exercises exactly that), and until `framework_withdrawn` and its rung exist, an armed lapse falls through to `discipline_lapse` — **charging the operator for failing to act on a mandate the framework retracted** — or to `away_unseen`, entering the away rate. Both are precisely what RD's disposition ruling forbids. Default-OFF does not make the 5c commit safe, because that commit's own test arms it. **So the disposition lands FIRST and the emitter finds it waiting.** `framework_withdrawn` + bucket membership + **the rung between rungs 4 and 5** (OQ-16 RULED: ABOVE telemetry health) + the condition-5 discriminating tests + the `constants.py:535-536` comment correction (§4.1 row 14).
`feat(latches): Task 6 — framework_withdrawn, excluded from the discipline signal and the away rate`

**Task 5c — THE TERMINAL AND ITS GATE, ATOMICALLY (AFTER Task 6).** The `criteria_lapsed` entry in the earliest-date-wins candidate set, gated by `criteria_lapse_armed`, plus that parameter threaded build_latch_derivation -> derive_latches -> _fold_ticker -> _resolve_terminal, plus the production-path test (T5.6). **Terminal and gate in ONE commit** so no commit ever contains an ungated clear; the diff is small enough that the one-line gate stays reviewable in isolation. This is the commit that decides whether report-only measures anything.
`feat(latches): Task 5c — the report-only arm flag, gating the terminal and nothing else`

**Task 7 — the render AND the report surfaces.** *An earlier draft scoped this to web rendering only, so an executor could follow every listed file change and silently omit BOTH required report-only measurements.* The VM fields (incl. `directional_evaluable`), the `_state_label` composition, the countdown on every live latch, the §3.2.1 rulings.
`feat(web): Task 7 — the off-screen UNVERIFIABLE render and its decision point`

**Then, before the Codex review:** the FULL fast suite to green (recipe §2). `ruff check swing/`.

---

## §6 Tests

Every test is specified so it **FAILS under the wrong behaviour** — the both-halves-pinned standard. Where the discriminator is not self-evident, the value under the wrong implementation is stated.

### T1 — vocabulary
* **T1.1** `LATCH_CLEAR_REASONS == frozenset({"fill","invalidation","horizon","superseded","criteria_lapsed","declined"})` — **SIX**. *An earlier draft of this revision left the five-value set here, so a correct Task-1 implementation would have failed its own vocabulary lock.*
* **T1.2** Two assertions, because a membership test alone does not pin a mapping: (a) **iterating** `LATCH_CLEAR_REASONS`, every reason has a `_STATE_BY_CLEAR_REASON` entry whose state is in `LATCH_STATES` and NOT in `_LIVE_STATES` — so a sixth reason gains the test automatically; (b) the **exact literals for BOTH new reasons** — `_STATE_BY_CLEAR_REASON["criteria_lapsed"] == "horizon_expired"` AND `_STATE_BY_CLEAR_REASON["declined"] == "horizon_expired"`. **The second pins residual R1**: without it `declined` could map to `filled` or `invalidated` and still satisfy (a)'s generic non-live assertion, which is how an inferred mirror ships wrong. **Discriminator:** (a) alone passes if the reason maps to `filled` or `invalidated`.
* **T1.3 — THE CALLER-SIDE OBLIGATION (gotcha #31). CORRECTED: an earlier draft's version could not fail.** Under Option B, `criteria_lapsed` and `horizon` share a `state`, so a discriminating test must find a consumer whose output DIFFERS between them. Two candidates were checked and **only one qualifies**:
  * **The execution resolver does NOT discriminate.** `classification.py:401` keys on `clear_reason == "fill"`; a wrong implementation keyed on `state == "filled"` gives the same answer for both latches, so asserting "not `accepted_by_broker`" passes under the exact defect it claims to catch. **Dropped.**
  * **The severity path DOES discriminate, now that OQ-1 has ruled YES.** `criteria_lapsed` and `declined` alarm CRITICAL while `horizon` alarms `warning`, from latches whose `state` is identical — so a state-keyed implementation gives the same answer for all three and fails. *(This half was conditional while OQ-1 was open; the ruling made it binding.)*
  * **The RENDER path discriminates unconditionally, and is therefore the binding form:** two latches with an IDENTICAL `state` of `horizon_expired`, differing only in `clear_reason`, must produce DIFFERENT `_state_label` output (`WITHDRAWN - criteria lapsed ...` vs `HORIZON EXPIRED`). **Discriminator:** any implementation keyed on `state` returns the same label for both and fails.
  This is the honest consequence of Option B, and stating it is part of the cost §3.6 records: under Option B + a not-critical-stale OQ-1, **the RENDER is the only surface whose output differs among the surfaces that existed BEFORE this arc** — and it is the surface the operator reads. **This arc then ADDS a second, stronger one:** the classifier rung (§3.8) must distinguish the two reasons or it re-labels every horizon-expired latch as `framework_withdrawn`, so T6.4(b) is a caller-side obligation test in exactly the same sense. (The template also prints `clear_reason` verbatim at `latches.html.j2:54-57`, which is a second place the difference is VISIBLE — but a raw enum string beside a state label that says HORIZON EXPIRED is not a distinction the card MAKES, which is why `_state_label` carries the obligation.)
* **T1.4 — SEVERITY, BOTH REASONS, as literals.** `_CRITICAL_STALE_CLEAR_REASONS == frozenset({"invalidation","superseded","criteria_lapsed","declined"})`, and behaviourally: a resting order behind a `criteria_lapsed` latch alarms **critical** (OQ-1 RULED) and behind a `declined` latch alarms **critical** (residual R2). **The `declined` half pins an INFERENCE and is the one to revisit if RD rules R2 the other way.**

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
* **T3.15 — A SAME-SESSION VERIFIED CONFLICT IS SURFACED, NOT SILENTLY RESOLVED (OQ-15's addition).** One action session with an earlier verified PASS and a later verified FAIL: the session classifies **PASSED** (generous), **AND** carries `conflicted = True`, **AND** `conflicted is True` on the returned verdict. **NOTHING ABOUT THE CARD** — that is T7.13's job at Task 7, and asserting it here would make Task 4 unable to be the standalone green commit §5 promises (the `Latch` diagnostics do not exist until 5b and the render not until 7). **Discriminator:** an implementation that resolves generously and says nothing passes every earlier T3 assertion — RD's requirement is that ambiguity be REPORTED, and a silent generous resolution is exactly the flattering-by-omission shape his 21-A duplicate rule forbids.
* **T3.16 — ACROSS SESSIONS, AN EARLIER PASS DOES NOT SUPPRESS A LATER UNVERIFIABLE (OQ-18's rejected half). *Belongs to TASK 5b, not Task 4*** — the tail is a resolver output and Task 4 is reader-only, so asserting it in the Task-4 suite would prevent Task 4 being the standalone green commit §5 promises. A window whose earlier sessions PASSED and whose LATEST in-domain session is UNVERIFIABLE yields `lapse_unverifiable_tail == 1`. **Discriminator:** an implementation that lets the earlier PASS satisfy "the framework checked this" suppresses the render and asserts a mandate it has not currently checked — which is the half RD REJECTED, while T3.2's within-session half stands.
* **T3.12 — THE LATEST *RUN*, NOT THE LATEST *ROW*.** One action session, two runs: the earlier carries a verifiable FAILING row for the ticker; the later carries NO row for it at all. The session is **UNVERIFIABLE**, not FAILED. **Discriminator:** a row-keyed implementation still sees the earlier failure as "the latest row" and returns FAILED, advancing the streak on a run that never checked the ticker. **This is the ordinary off-screen case, not an edge case.**
* **T3.14 — THE RUN ORDER IS `(run_ts, evaluation_run_id)`.** One action session with two runs sharing an identical `run_ts`: the lower `evaluation_run_id` carries a verifiable FAILING row, the higher carries NO row for the ticker. The session is UNVERIFIABLE. **Discriminator:** an implementation ordering by `(run_ts, candidate_id)` cannot break the tie at all (the later run has no `candidate_id` for this ticker) and falls back to the failing row.
* **T3.13 — `adr_pct` REACHES THE RESOLVER THROUGH THE PRODUCTION PATH (the fixtures-bypass-the-derivation-path gotcha).** A DB-backed test that seeds a real `candidates` row carrying `adr_pct`, runs `build_latch_derivation` (not a hand-built `FireRow`), **with `criteria_lapse_armed = True` in the config it loads**, and asserts the value arrives at the resolver — an otherwise-qualifying latch CLEARS. **Discriminator:** an implementation that adds `FireRow.adr_pct = None` but forgets `c.adr_pct` in `_FIRE_SQL` passes every direct-resolver fixture (they construct `FireRow` with an ADR by hand) while PRODUCTION marks every latch directionally unverifiable and the feature never fires at all. Byte-tests over hand-built inputs cannot see that; only a test through the real SELECT can.
* **T3.10 — THE OVERLAP.** One action session with an earlier verifiable PASS and a LATER verifiable FAIL → the session is **PASSED** and the streak RESETS. **Discriminator:** an implementation evaluating the §3.2 table in written order without noticing the overlap classifies it FAILED and advances the streak.
* **T3.11 — THE NO-JOIN OBLIGATION, PINNED BY OUTCOME (gotcha #31). REBUILT ON 2b, because the 2a version was IMPOSSIBLE.** An earlier draft asked for bars dated `S1..S5` satisfying 2a while the shifted bars `S1-1..S5-1` contained a pivot crossing — **but the shifted dates lie inside `[anchor, s]`, which lifetime 2a also scans, so both readings see the crossing and the promised opposite outcomes cannot exist.** The two readings differ on **2b's interval and therefore on MATERIALITY**, which is exactly where the live VSTS case separates them ($0.77 vs $0.43). So: construct failing sessions whose bar-dated window `[first(W), last(W)]` widens PAST the floor while the verdict-shifted window `[first(W)-1, last(W)-1]` widens BELOW it, with no close reaching the pivot anywhere in `[anchor, s]`. Assert the ruled (bar-dated) outcome: CLEARS. **Discriminator:** a row-by-row-joining implementation computes the shifted window, falls under the floor, and does not clear. Run the mirror-image fixture (shifted clears, bar-dated does not) so the test pins the ruled reading rather than merely detecting *a* difference. *(OQ-11 is RULED bar-dated, so the expected values are fixed; the mirror-image fixture stays as the proof that the test pins the RULED reading rather than merely detecting a difference.)*

### T4 — the streak and the conjuncts. **The FTRE and VSTS cases are the binding acceptance tests.**

> **EVERY T4 FIXTURE STATES HIGHS AS WELL AS CLOSES (OQ-14).** With 2a ruled onto the HIGH, a fixture giving only closes is under-specified: a correct high-based resolver may refuse a "positive clear" fixture whose unstated highs reach the pivot. **Baseline rule: unless a test says otherwise, `high == close` on every bar**, so the stated closes fully determine 2a; any test exercising an intraday cross states the differing high explicitly — **and T4.26 is the ONE fixture that discriminates the ruling itself.**
>
> **THE T4 FIXTURE BASELINE — every value that decides an outcome is stated, never inherited by assumption.** Unless a test says otherwise: `adr_pct = 3.0` on the fire row, `criteria_lapse_min_widening_adr = 1.0`, `min_widening_pct = 2.0`, `criteria_lapse_sessions = 5`,, the archive is COMPLETE over every interval the test exercises, and — **RULED DEFAULT-OFF, so this is now load-bearing — `criteria_lapse_armed = False`.** **EVERY test that asserts an actual `criteria_lapsed` TERMINAL sets it TRUE explicitly.**

> **⚠ AND EVERY *NEGATIVE* RULE TEST ASSERTS THE COUNTERFACTUAL, NOT MERELY "IT DID NOT CLEAR" — OTHERWISE THE ARM FLAG MAKES IT VACUOUS.** This is the single most dangerous interaction the report-only ruling introduced. A test whose only assertion is *the latch did not clear by `criteria_lapsed`* **passes under the shipped default NO MATTER WHAT THE CONJUNCTS DO**, because the flag suppresses the terminal regardless. That silently guts the arc's safety locks: **T4.1 (the FTRE founding case) would pass under the naive gate-only rule**, T4.6 under a window-scoped 2a, T4.7 under an endpoint-only 2b, and T4.14 with the materiality floor omitted — every one of them a test this plan marks NOT DROPPABLE.
>
> **So each negative rule test asserts `lapse_qualifying_session is None` AND `lapse_would_clear_session is None`** — the hypothetical the wrong implementation would have produced — **and T4.1 additionally runs BOTH armed and unarmed**, proving no hypothetical lapse exists in either derivation. The founding-case lock has to bite in the shipped configuration, not only in a configuration nobody runs. At the baseline (pivot 100) the floor is `max(1.0 × 3.0% × 100, 2.0% × 100) = $3.00`.
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
* **T4.2 — THE VSTS CASE.** Fire candidate 11629, 2026-07-27, pivot 16.90. Failing evaluated sessions 07-28, 07-29, 07-30; absent thereafter. Archive bars 07-27 15.35, 07-28 15.36, 07-29 14.92, 07-30 14.59. **With N=3 the latch clears `criteria_lapsed` at 2026-07-30; with N=5 it does NOT clear and the streak is frozen at 3.** **THE POST-ANCHOR HIGHS, READ FROM THE LIVE ARCHIVE AND STATED LITERALLY (§2.2 query 6), because a binding acceptance oracle may not be left to runtime discovery:** 07-27 **15.85**, 07-28 **15.74**, 07-29 **15.61**, 07-30 **15.32**, 07-31 **14.74**. **Every one is below the 16.90 pivot, so the OQ-14 HIGH ruling does NOT change VSTS's expected result** — the clear at N=3 stands. A fixture is hermetic: these values go in as literals and the test never touches the operator's DB. Both assertions, pinning the config binding as well as the rule.
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
* **T4.20a — THE DIAGNOSTIC ROSTER IS EXACT.** `LATCH_LAPSE_DIAGNOSTIC_FIELDS` equals the eleven-name literal set, and every name is a real `Latch` field. **Discriminator:** without it, T4.20's iteration passes over a roster that silently omits the newest field.
* **T4.20 — THE HYPOTHETICAL IS COMPUTED IDENTICALLY ARMED OR NOT. Scoped correctly, because "differ in exactly one thing" is impossible.** One qualifying fixture, derived twice. **The invariant is over the RESOLVER'S HYPOTHETICAL, not the whole latch:** `lapse_would_clear_session` and EVERY diagnostic — asserted by **ITERATING a NAMED module-level roster, `LATCH_LAPSE_DIAGNOSTIC_FIELDS`, declared beside the dataclass and covering all ELEVEN diagnostic fields** — rather than by listing a subset or restating a count. A test that enumerates its own subset omits exactly the newest field, which is how `lapse_conflicted_sessions` and `lapse_would_clear_session` would have escaped; and *an earlier draft said "eight" when the model had ten*, which is the same defect in prose. The roster is the single authority and both T4.20 and T5.6 walk it — are byte-identical between the two runs. Unarmed the latch is LIVE; armed it is `criteria_lapsed` at exactly `lapse_would_clear_session`.
  **Two corrections to an earlier draft of this test, both of which made it wrong:** (a) returning a terminal necessarily also changes `clear_session`, `is_live`, the state label, the classification and possibly the alarms, so "differ ONLY in `clear_reason`/`state`" could never hold; (b) its equality list ENUMERATED a subset, so an implementation gating `directional_block_reason` or the conflict fields would have passed — iterating the field set closes that.
  **Discriminator:** an implementation short-circuiting the streak fold or the conjuncts when unarmed produces empty or different diagnostics, and report-only measures NOTHING — the failure that would make the framing ruling worthless. **NOT DROPPABLE.**
* **T4.22 — THE ARM FLAG CHANGES LATCH TOPOLOGY, AND THAT IS EXPECTED RATHER THAN A VIOLATION OF T4.20.** A same-pivot RE-FIRE arriving after the hypothetical lapse session: **unarmed** the old latch is still live so the re-fire is a RE-CONFIRMATION; **armed** it had cleared, so the re-fire opens a NEW latch. Assert both. This is the legitimate downstream consequence T4.20's scoping excludes, tested separately rather than hidden — and it is a real fact for whoever arms the flag: **arming changes the latch corpus, not merely the labels.**
* **T4.21 — THE `declined` TERMINAL AND ITS PRECEDENCE (OQ-4).** (a) a decline intent on session D terminates a live latch as `clear_reason='declined'` at D; (b) it terminates an OFF-SCREEN and an ON-SCREEN latch identically (UNIFORM — no off-screen special case); (c) a fill dated at or before D wins (*"you cannot decline a filled mandate"*); (d) a fill AFTER D does not; (e) a decline and an invalidation on the SAME session resolve `declined` (rank 0); (f) an invalidation dated EARLIER than the decline wins (earliest-date-wins, L10); (g) the governing decline is the LATEST by `(recorded_ts, intent_id)` when several exist. (h) **`declined` is NOT gated by the arm flag** — it terminates with `criteria_lapse_armed = False`.
  **(i) THE CROSS-KIND CORRECTION — the revision's headline protection.** `decline(D5)` followed by `place(D6)`: the latch does **NOT** terminate `declined`, and the classifier returns `accepted`. **Discriminator:** an implementation keyed on the latest DECLINE terminates at D5 and withdraws a mandate the operator had re-placed. *(g) covers several declines and does NOT reach this.*
  **(j) THE AS-OF BOUND.** `decline(D10)` with a liveness probe as of D6: the probe does NOT see it and the old latch is still live at D6. **Discriminator:** an unbounded decline makes the old latch look dead at D6 and corrupts the reconfirm/supersede topology.
  **(k) THE HORIZON BOUND.** A decline dated after `horizon_expiry` leaves `clear_reason='horizon'` unchanged.
  **(l) THE FILTER RUNS BEFORE THE WINNER IS CHOSEN.** `decline(D5)` + `place(D10)`, probe as of D6 → the probe sees the D5 DECLINE (the D10 place is out of bounds and is filtered OUT before `governing_decision` runs). **Discriminator:** an implementation calling `governing_decision` over ALL intents and bounding the winner afterwards picks the D10 place, drops it as out-of-bound, and returns NOTHING — so the D5 decline vanishes from a probe that should see it.
  **(l2) A LATER `place` ON A SUCCESSOR NEVER RESURRECTS ITS PREDECESSOR.** `decline(D5)`, re-fire `D6` (a new latch), `place(D10)` recorded against the D6 candidate: the OLD latch stays `declined` at D5 and the D10 place governs the NEW latch only. **Discriminator:** an implementation matching decisions by TICKER, or widening the predecessor's family to include its successor, erases the D5 decline and resurrects a mandate the operator declined. *(The no-re-fire case — `decline(D5)` then `place(D6)` on the SAME family, which DOES erase the decline — is (i).)*
  **(n) `declined` BEATS `superseded` ON THE SAME SESSION.** A predecessor-family decline and a different-pivot re-fire on one action session: assert **TWO latches**: the predecessor clears `declined` (NOT `superseded`), **and a DISTINCT LIVE successor exists carrying the new candidate id and the new frozen pivot, with no inherited decline.** **Discriminators, two of them:** an implementation that stamps `superseded` overwrites the operator's decision with a framework inference; and one that marks the predecessor `declined` but DROPS the incoming fire — or absorbs it as a re-confirmation — passes a predecessor-only assertion **while silently losing the succeeding mandate entirely.**
  **(o) THE TWO ADJACENT TIES THE LADDER'S NEW RUNG CREATES.** Same-session `declined` vs `criteria_lapsed` -> `declined`; same-session `declined` vs `horizon` (a decline dated exactly `horizon_expiry`) -> `declined`. **Discriminator:** an implementation ranking `criteria_lapsed` above `declined`, or excluding a decline ON the horizon session through an off-by-one bound, passes every other collision test — the neighbouring rungs are the ones a new insertion gets wrong.
  **(m) TWO LATCHES ON ONE TICKER DO NOT CROSS-CONTAMINATE.** An older latch's decline does not terminate a newer latch on the same ticker. **Discriminator:** a ticker-keyed intent mapping terminates the newer mandate the operator never declined. Production-path (DB-backed), because a hand-built per-latch mapping cannot exhibit the defect.
* **T4.19 — DUPLICATE-BAR CANONICALIZATION COVERS EVERY READ FIELD, INCLUDING THE HIGH (unconditional under the OQ-14 ruling).** Two rows for one date agreeing on close but DISAGREEING on high (`close 95 / high 101` and `close 95 / high 99`) make that date UNVERIFIABLE. **Discriminator:** a close-only canonicalization collapses them, and under the OQ-14 HIGH variant a surviving `high 99` row hides a pivot touch at `101` — clearing a latch whose stop-limit had triggered. Also assert a non-finite value in any read field makes the date UNVERIFIABLE.
* **T4.18 — A HISTORICAL BAR CORRECTION MOVES A TERMINAL, AND THAT IS DISCLOSED BEHAVIOUR (§3.2.1 ruling 6a).** Derive a lapse from `95, 94, 93, 92, 90`; then CORRECT the D3 bar to `101` and re-derive: the latch is no longer `criteria_lapsed`. Then backfill a previously-missing D3 into an incomplete window and re-derive: a lapse now appears. Assert both. **This test does not defend a property — it PINS a known consequence of deriving over a mutable archive (gotcha #26), so that a future reader meets it as a recorded decision rather than as a mystery**, and so that any later immutable-snapshot work has an explicit statement to change.
* **T4.17 — THE MATERIALITY BOUNDARY, with the float artifact STATED (a generic `98.00 → 95.00` pair evaluates identically under both implementations and would prove nothing).** Baseline fixture, pivot 100, floor exactly `$3.00`. Use operands whose IEEE-754 difference falls just below the decimal value: **the complete five-bar series `64.02, 63.50, 63.00, 62.00, 61.02`** (all below the pivot, strictly descending so clause 3 holds, `first = 64.02`, `last = 61.02`) — verified on this box, `64.02 - 61.02` evaluates to **`2.999999999999993`**, while both closes round to exactly `64.02` and `61.02` and the panel displays a `$3.00` widening. **Set BOTH floor terms to $3.00 explicitly: pivot `150.00`, `adr_pct = 2.0` (ADR term `1.0 × 2% × 150 = $3.00`), `min_widening_pct = 2.0` (pivot term `$3.00`) → floor `max(3.00, 3.00) = $3.00`.** The T4 baseline's `adr_pct = 3.0` would make the ADR term `$4.50` and the test could not clear at all — a second reason it would have passed for the wrong reason. Assert the latch CLEARS. **Discriminator:** an implementation that differences the raw floats — **OR that rounds the operands and then subtracts, which is the same thing** — gets `2.999999999999993 < 3.00` and REFUSES, withdrawing nothing while the card states equality. Then assert a genuine `$2.99` widening does NOT clear, pinning both sides.
  **A note on how this value was obtained, because it matters:** an earlier draft asserted `100.10 - 97.10 == 2.9999999999999947`. **That is FALSE — it evaluates to exactly `3.0`** — and a test built on it would have passed under both implementations, i.e. the boundary test guarding the precision rule would itself have been precision-blind. The pair above came from an exhaustive scan of two-decimal pairs. **The executing implementer must re-verify it on the box before relying on it.**
* **T4.16 — A LATER PIVOT CROSSING CANNOT RESURRECT A CLEARED LATCH.** Baseline fixture, pivot 100, N=5, all failing, closes `95, 94, 93, 92, 90` (widening $5.00 > $3.00) → clears at D5. Then add a D6 bar closing `105` and re-derive. Assert the latch is STILL `criteria_lapsed` at D5, and that a fill dated D6 is NOT attributed. **Discriminator:** an implementation bounding 2a at `derivation_session` instead of at the candidate terminal `s` finds the `105` crossing, disqualifies 2a, and RESURRECTS a latch that had already cleared — breaking L10 through the conjunct rather than through the precedence. **This is a defect an earlier draft of this plan contained.**
* **T4.12 — display precision, ARITHMETIC CHECKED UNDER BOTH PATHS.** Against a pivot of 18.34 at `_PRICE_DP = 2`: a close of `18.3400001` rounds to `18.34`, is at-or-above the pivot, and DISQUALIFIES 2a; a close of **`18.3349`** rounds to `18.33`, is below, and does NOT. **An earlier draft used `18.3399` for the second case, which rounds to `18.34` and also disqualifies — the test asserted an outcome no correct implementation could produce.**
* **T4.13 — LIFETIME-2a COMPLETENESS, ISOLATED. The gap must sit BEFORE the streak window or the test proves nothing.** Pivot 100, baseline fixture. **The N-failure window itself is COMPLETE and fully qualifying** (closes `99, 96, 95, 94, 92`), while the MISSING bar — the one whose true close was `101` — lies **after the anchor but BEFORE `first(W)`**, inside lifetime 2a's `[anchor, s]` and OUTSIDE 2b's `[first(W), last(W)]`. The latch does NOT clear and is reported DIRECTIONALLY UNVERIFIABLE. **Discriminator:** an implementation that omits LIFETIME-2a completeness but implements 2b's completeness correctly still clears — the streak window is complete and qualifying, so 2b is satisfied, and 2a sees no pivot close because the crossing bar is simply absent. **An earlier draft put the missing bar INSIDE the streak window, where 2b's own completeness check already refuses it, so the test passed under an implementation with no lifetime-2a completeness at all.** Plus one sibling case: `archive_status == 'unavailable'` over an otherwise-qualifying series → no clear. (**A `len(B) < 2` sibling was dropped**: completeness plus `N >= 2` makes it unreachable, so it would pass under both implementations.)
* **T4.14 — MATERIALITY, both terms of the floor (OQ-10).** Two fixtures, because the two terms fail on different shapes:
  (a) **the ADR term binds:** pivot 100, `adr_pct = 4.0` (floor `max(4.00, 2.00) = $4.00`), closes `99.00, 99.04, 99.03, 99.02, 98.99` → widening $0.01, no clear. **Discriminator:** without clause 4 this satisfies 2a and clauses 2–3 and a one-cent "decay" withdraws the mandate.
  (b) **THE PIVOT-RELATIVE TERM BINDS, and an ADR-only floor FAILS THIS ONE:** pivot 100, `adr_pct = 0.40` (ADR term $0.40; pivot term $2.00; floor $2.00), closes `99.80, 99.90, 99.75, 99.60, 99.30` → widening $0.50, no clear. **Discriminator:** an ADR-only floor of $0.40 is exceeded by $0.50 and CLEARS a sub-1% consolidation sitting under its pivot.
* **T4.15 — NULL ADR SUPPRESSES, AND THE GUARANTEE IS TESTED AT A PURE HELPER BECAUSE IT IS OBSERVATIONALLY INVISIBLE FROM OUTSIDE.** *Two earlier drafts of this test were both unfalsifiable: "exceeds any plausible fallback" fails because a 25%-of-pivot substitute refuses the series too, and the "order of operations" form fails because such an implementation can ALSO emit `directional_evaluable = False` with a missing-ADR reason — every black-box output identical.* **So the floor is computed in ONE pure function and the test calls it directly:**

  ```
  swing/latches/service.py
  def materiality_floor(*, adr_pct, pivot, adr_multiple, min_widening_pct) -> float | None
      # RETURNS None for a NULL or non-finite adr_pct. The ONLY place the floor
      # is computed, so "no substitute" becomes a property of one function
      # instead of a claim about a call graph.
  ```

  **The discriminating assertion is `materiality_floor(adr_pct=None, ...) is None`** (and the same for `nan` / `inf`) — **which no fallback implementation can satisfy, because returning any number IS the fallback.** The resolver-level fixtures remain as integration cover: pivot 100 with `adr_pct` NULL and closes `95, 90, 85, 80, 75` (a $20 widening) does NOT clear and is DIRECTIONALLY UNVERIFIABLE, while the identical series with a usable `adr_pct` DOES clear — the pair differing only in the ADR's presence.

### T5 — the calibration
* **T5.0a — THE THREE DEFAULTS EQUAL THE RULED LITERALS.** After OQ-10 is answered, assert the exact values (`5`, `1.0`, `2.0` as recommended): mirror-to-mirror equality alone passes when all three mirrors are changed together, so a synchronized drift to `1.5`/`5.0` would go unnoticed and every T4 test — which passes explicit arguments — would stay green.
* **T5.0 — ALL THREE MODULE DEFAULTS ARE PINNED, not just N.** `DEFAULT_CRITERIA_LAPSE_SESSIONS == LatchesConfig().criteria_lapse_sessions`, `DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR == LatchesConfig().criteria_lapse_min_widening_adr`, `DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT == LatchesConfig().criteria_lapse_min_widening_pct`. **Discriminator:** an earlier draft pinned only N, so either materiality module default could drift from its dataclass while every test stayed green — and the pure derivation would then silently use a different floor from production.
* **T5.1 — THE MIRROR PIN COVERS THE SHIPPED TOML TOO, WHICH IS A THIRD MIRROR AN EARLIER DRAFT MISSED.** `DEFAULT_CRITERIA_LAPSE_SESSIONS == LatchesConfig().criteria_lapse_sessions == 5` pins the module constant against the dataclass — **but production loads `swing.config.toml`, not the dataclass default**, so an explicit `[latches]` block in the tracked config is a THIRD copy that can drift from both while every test stays green. **Fix: the tracked TOML carries ALL FOUR keys** (the arm flag + the three calibrations) (`criteria_lapse_sessions`, `criteria_lapse_min_widening_adr`, `criteria_lapse_min_widening_pct` — the earlier draft shipped only the first, so the two materiality knobs were config-bound in prose and default-only in fact) **and T5.1 asserts against the RAW TRACKED TOML TEXT, not the loaded config.** Comparing the LOADED values to the dataclass defaults **cannot fail**: if the `[latches]` block — or just one key — is absent, `load()` supplies those very defaults and the comparison passes over the exact missing-mirror defect it claims to catch (T5.3 proves the section is optional). So the test PARSES `swing.config.toml` and asserts every field of `LatchesConfig` is EXPLICITLY PRESENT as a key with a value equal to the dataclass default, iterating `dataclasses.fields(LatchesConfig)` so a fourth knob joins the pin automatically.
* **T5.2** the derivation honours a non-default N (7 → clears later). Fails against any hard-coded 5.
* **T5.3** a config file with no `[latches]` section loads and defaults.
* **T5.6 — THE ARM FLAG REACHES THE PURE RESOLVER FROM PRODUCTION CONFIG.** DB-backed through `build_latch_derivation`: with `criteria_lapse_armed = True` in the loaded config an otherwise-qualifying latch CLEARS; with the key ABSENT (the shipped default) the same fixture stays LIVE with `lapse_would_clear_session` set **AND every field in `LATCH_LAPSE_DIAGNOSTIC_FIELDS` populated identically to the armed run** — a builder that conditionally drops conflict sessions, causes or the block reason while unarmed would otherwise pass both T4.20 (pure layer) and a would-clear-only T5.6. **Discriminator:** the flag is a DEFAULTED parameter, so an implementation that threads it through `derive_latches` but forgets to pass `cfg.latches.criteria_lapse_armed` from `build_latch_derivation` passes every direct-resolver fixture while production can NEVER arm — the feature would be permanently dead and no unit test would notice.
* **T5.4 — THE INERT-CONFIGURATION FAMILY, one assertion each.** `criteria_lapse_sessions` = `1` raises (2b unsatisfiable); `2.5` raises (**discriminator:** a bare `< 2` check accepts it and the derivation's `int()` silently truncates to 2); `True` raises (**discriminator:** `bool` is an `int` and passes every numeric comparison). `criteria_lapse_min_widening_adr` = `float("inf")` raises (**discriminator:** it satisfies `> 0` and disables the lapse forever, silently); `0` and `-1` raise; `float("nan")` raises (every ordered comparison against `nan` is False, so a `> 0` guard admits it — the same hole `zone_cap_for_pivot`'s docstring records at `constants.py:83-93`). Same set for `criteria_lapse_min_widening_pct`. **And `criteria_lapse_armed` rejects every non-bool** — `1`, `0`, `"false"`, `"true"`, `None`. **Discriminator:** a loader coercing `1` or `"false"` could silently ARM the terminal while every other listed test stays green — the one configuration error whose blast radius is a withdrawn mandate.
* **T5.5 — RETROACTIVITY IS PINNED, NOT LEFT TO BE DISCOVERED (§3.2.1 ruling 7).** One fixture, two configs: with N=5 the latch clears `criteria_lapsed` before a day-6 entry and that entry is NOT attributed; with N=7 the same fixture clears by `fill` on the day-6 entry. Assert both. **Discriminator:** it fails if anyone later freezes N per-latch — which would be a reasonable change, and this test makes it a deliberate one.

### T6 — the measurement disposition (CONDITION 5 — the discriminating bucket exclusions)

* **T6.1 — EXCLUDED FROM THE AWAY RATE.** Corpus: 1 `framework_withdrawn` + 1 `away_unseen` + 1 `accepted`, all terminal, health `ok`. Assert `objective_rate == 0.5` **and** `classifiable_fires == 2` **and** `bucket_counts["unattributable_r"] == 1`.
  **Discriminators:** in `AWAY_RATE_COUNTED_DISPOSITIONS` → `2/3` and `3`; in `DECISION_DISPOSITIONS` **as well as** `_ALL_EXCLUDED_DISPOSITIONS` → see T6.10, which this test does NOT catch.
* **T6.11 — THE HEALTH EDGE, RULED (OQ-16).** A terminal `criteria_lapsed` latch with a NON-OK telemetry verdict classifies **`framework_withdrawn`, literally — NOT `telemetry_unhealthy`.** *An earlier draft said "assert whichever disposition OQ-16 rules", which is unwritable now that it HAS ruled and would let a wrong below-health implementation be blessed by a test written to match it.* Also assert that `away_r`, `decision_r` and `classifiable_fires` are unchanged — the rates are invariant to this edge, only the label moves, which is what makes it a labelling ruling rather than a measurement one.
* **T6.12 — THE DECLINE'S MEASUREMENT TRANSITION, PINNED BECAUSE IT MOVES A PUBLISHED DENOMINATOR.** A latch with a governing decline: assert it is TERMINAL, classifies `declined`, and buckets to **`decision_r`** — entering `classifiable_fires` and therefore the away-rate denominator. **Discriminator:** before OQ-4 the same latch was LIVE and gated to `pending_r` (reported, never scored), so this test fails against the pre-ruling lifecycle and documents the shift RD intended (*"scored, his call"*). **With a LITERAL corpus and LITERAL expected values, so the engineer invents nothing:** 1 declined + 1 `away_unseen` + 1 `accepted`, all otherwise terminal, health `ok`. **Before OQ-4** the declined latch is LIVE -> `pending_r`, so `classifiable_fires == 2` and `objective_rate == 0.5`. **After** it is terminal -> `decision_r`, so `classifiable_fires == 3` and `objective_rate == 1/3`. Assert the post-ruling pair; the pre-ruling pair is stated so the shift is legible.
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
* **T7.11 — THE OVER-THRESHOLD CARD, BOTH BRANCHES (the second is the one that catches the falsehood).** **(a)** a live latch with `k = 8` against `N = 5`, still live because lifetime 2a REFUSES (the T4.6 shape): the card renders `8 failures; threshold 5; directional condition NOT MET`. **(b) THE REPORT-ONLY BRANCH:** `k >= N`, the conjuncts MET, `criteria_lapse_armed = False`, `lapse_would_clear_session` populated: the card renders `WOULD WITHDRAW on <session> — REPORT ONLY (not armed)`. **Discriminator for (b):** an implementation that keeps printing "directional condition NOT MET" in report-only mode passes (a) and every T4 resolver test while telling the operator a condition did not meet when it did. Neither branch renders `8 of 5`. **Discriminator:** an implementation rendering the fraction unconditionally prints a nonsensical countdown with no explanation on a latch that will never lapse.
* **T7.12 — THE `Latch` DIAGNOSTIC INVARIANTS.** Constructing a `Latch` RAISES when: a count disagrees with its tuple; a session tuple is not strictly ascending; the failed and unverifiable tuples intersect; the causes tuple is not parallel to the unverifiable sessions; or the tuples are not disjoint. **Discriminator:** without these a latch can name one session twice, and T7.10 — which tests PROVENANCE — would not notice.
  **THE TAIL INVARIANT IS NARROWED HONESTLY, because `Latch` cannot establish the strong form.** `__post_init__` was asked to verify that `lapse_unverifiable_tail` equals the UNVERIFIABLE suffix of the *actual verdict sequence* — but `Latch` carries only the failed and unverifiable sessions, **never the PASSED ones**, so a caller supplying an unverifiable D2 with tail `1` while omitting a later PASSED D3 is undetectable at the constructor. **So the dataclass validates only what it can see** (`lapse_unverifiable_tail <= lapse_unchecked_count`, and the tail's sessions are the latest members of the unverifiable tuple), **and the RESOLVER owns the real suffix computation, pinned by a resolver test (T4.24) rather than a constructor invariant.** Claiming the stronger check would be a guard that cannot fire.
* **T7.10 — THE CARD NAMES THE SESSIONS AND THE CAUSE, FROM THE RESOLVER.** For VSTS's live shape, the card names the failed sessions `2026-07-28, 2026-07-29, 2026-07-30` and states the UNVERIFIABLE cause (`absent`). **Discriminator (a): an implementation carrying only counts cannot render either.** **Discriminator (b) — PROVENANCE, OBSERVED RATHER THAN ASSERTED:** on a CONSISTENT fixture a reading VM and a recomputing VM render identically, so "assert the VM reads them" is untestable as stated. **Poison the inputs instead:** hand the VM a `Latch` whose `lapse_failed_sessions` are DELIBERATELY different from what the raw verdict sequence would produce, and assert the card renders **the `Latch`'s** dates. A VM that recomputes renders the other set and fails. (An equally valid form is to withhold the verdict sequence from the VM entirely so recomputation is impossible by construction — that is the stronger design and is preferred if the wiring allows it.)
* **T4.26 — 2a READS THE HIGH, NOT THE CLOSE (the OQ-14 ruling's ONLY discriminator).** Pivot 100, baseline, five structurally failing sessions, duplicate-free: closes `99, 98, 97, 96, 95` — an otherwise fully qualifying decay (all below the pivot, ends at its low, widening $4 > the $3 floor) — with highs `99, `**`101`**`, 97, 96, 95`. Assert **both** `lapse_qualifying_session` and `lapse_would_clear_session` are `None`. **Discriminator: this is the only listed test the rejected CLOSE-based 2a fails.** FTRE crosses on the CLOSE so it disqualifies either way; VSTS stays below on both; T4.12 varies only closes; and T4.19's duplicate highs make the date UNVERIFIABLE *before* 2a runs, so an implementation that canonicalizes highs correctly and then wrongly tests the close still passes it. **Without T4.26 the ruled design and the rejected one are observationally identical across the entire suite.**
* **T4.25 — THE STREAK TUPLES ARE CURRENT-STREAK, THE ANALYSIS FIELDS ARE NOT (the §3.2.1 split).** Sequence `FAIL D1 / PASS D2 / FAIL D3`: `lapse_failed_sessions == (D3,)` and `lapse_failed_count == 1` — **not** `(D1, D3)` / 2. Sequence `UNVERIFIABLE D1 / PASS D2 / FAIL D3`: `lapse_unchecked_count == 0`. Meanwhile a conflict on D1 STILL appears in `lapse_conflicted_sessions`, and a qualifying lapse after an actual D-earlier terminal still populates `lapse_qualifying_session`. **Discriminator:** a single analysis-window rule for all tuples makes the first two assertions fail; a single streak-scoped rule makes the last two fail. Only the split satisfies both, and T4.20's armed/unarmed equality would not notice either error because both runs would be identically wrong.
* **T4.24 — THE RESOLVER OWNS THE UNVERIFIABLE SUFFIX.** Over a verdict sequence `FAIL / UNVERIFIABLE / PASS / UNVERIFIABLE / UNVERIFIABLE`, the resolver emits `lapse_unverifiable_tail == 2`. **Discriminator:** this is the check T7.12 CANNOT make — `Latch` never carries the PASSED session, so a constructor cannot tell a genuine 2-tail from one that ignored an intervening PASS. Owning it at the resolver is what makes the claim true rather than merely asserted.
* **T4.23 — THE COUNTERFACTUAL RESPECTS THE FULL LADDER, INCLUDING THE FILL.** Three cases, unarmed: **(a) FILL-ONLY** — a fill on D4, a qualifying lapse on D5, NO earlier non-fill terminal: `lapse_qualifying_session == D5` but **`lapse_would_clear_session is None`**, because armed the latch clears by `fill`. **Discriminator: this is the ONLY fixture that catches a counterfactual built as a `min(...)` over the non-fill candidate list** — that implementation reports a withdrawal on D5 and inflates the calibration count. **(b) INVALIDATION** — invalidation D3, qualifying lapse D5: `lapse_would_clear_session is None`. **(c) CLEAN** — a qualifying lapse with no competing terminal: `lapse_would_clear_session == lapse_qualifying_session`.
  **(d) THE ROSTER SURVIVES A PRECEDENCE LOSS.** For (a) and (b), derive armed and unarmed and assert **every field in `LATCH_LAPSE_DIAGNOSTIC_FIELDS` is equal across the pair AND populated with the stated expected values** (the streak, the gap sessions, the conflict tuple, the directional flags). **Discriminator:** T4.20 and T5.6 compare only the CLEAN winning-lapse case, so an implementation that stops populating diagnostics whenever another terminal wins passes both — losing the streak, gap and conflict evidence on exactly the precedence-losing latches the calibration read needs to distinguish.
* **T6.13 — THE LIFECYCLE AND THE CLASSIFIER AGREE, ASSERTED AS A PAIR ON EVERY COLLISION.** For each of: fill D4 / decline D5; fill and decline BOTH on D5; invalidation D3 / decline D5; a POST-HORIZON decline; and a decline belonging to a DIFFERENT latch on the same ticker — assert the lifecycle TERMINAL and the DISPOSITION together. The first three give `fill` / `fill` / `invalidation` with a disposition that is **NOT** `declined`. **Discriminator:** an unbounded classifier returns `declined` for all three — a FILLED latch scored in `decision_r` as a decline — and a test asserting only one side of the pair passes while the two contradict each other about the same latch.
* **T6.14 — FILTERING THE DECISION FAMILY DOES NOT DELETE THE OTHER INTENT EVIDENCE. THREE SEPARATE FIXTURES, because the three states are mutually exclusive in one latch** (*an earlier draft demanded all three at once: if the only place is out of bounds the execution outcome has no governing parent, and if an admissible place is added then rung 1 returns `accepted` and the attestation rung cannot fire — the fixture was unsatisfiable*):
  **(a)** an OUT-OF-BOUND place + an attestation -> the **attestation governs** (the out-of-bound place does not pre-empt rung 3).
  **(b)** an ADMISSIBLE place + its validity and cancel children -> the execution evidence **survives the filtering** and `resolve_execution_outcome_for` returns the child's outcome.
  **(c)** an OUT-OF-BOUND place ALONE -> it is **not** `governing_place_intent_id` and its child does not drive the execution outcome.
  **Discriminator:** an implementation replacing `intents` wholesale with the helper's output fails (a) and (b) by losing attestations and validity children; one filtering only `governing_decision` fails (c). **Discriminator:** a classifier still calling `governing_decision(intents)` unfiltered emits `declined` against a `horizon` terminal — the lifecycle and the measurement contradicting each other about the same latch.
* **T7.14 — THE CLI WOULD-CLEAR LINE IS THE CALIBRATION INSTRUMENT AND IS TESTED AS ONE.** A corpus with (1) one TRUE would-clear and (2) one qualifying-but-precedence-losing latch (the T4.23(a) shape). `swing latches report` counts **ONE**, lists its session, and **EXCLUDES the loser**. **Discriminator:** a CLI reading `lapse_qualifying_session` counts TWO — the instrument inflated on the very number that decides whether the rule gets armed, while T7.11 (web card) and T7.13 (conflict line) both stay green.
* **T7.13 — THE CONFLICT SIGNAL REACHES THE CARD (OQ-15's addition, render half).** A latch whose window contains a same-session verified-PASS/verified-FAIL conflict: the card's detail line NAMES the conflicted session and the report line counts it. **Discriminator:** an implementation that resolves generously and carries `conflicted` no further renders nothing, and the ambiguity RD required to be surfaced is silently absorbed — which is the shape his 21-A duplicate rule forbids.
* **T7.9 — THE UNCHECKED COUNT IS RENDERED FROM THE RESOLVER, NOT RE-ENUMERATED IN THE VIEW.** Build a window whose IN-DOMAIN sequence is `PASS / ABSENT / FAIL / ABSENT / FAIL` — i.e. **TWO runs in which the ticker was absent** — **PLUS a separate trading session on which NO RUN EXISTS AT ALL.** Assert the card shows `failed 2 of 5 checked sessions (2 unchecked)`: the two ticker-absent runs count, the no-run day contributes NOTHING. **Discriminator:** a VM that enumerates trading sessions counts the no-run day and renders `3 unchecked` — a false statement about what the framework failed to check. *(An earlier draft's fixture had only ONE ticker-absent run beside the no-run day, so the correct implementation would have rendered `1` and the stated expectation of `2` was unreachable — the fixture and its assertion contradicted each other.)* T3.5 pins the reader; this pins the surface the operator actually reads.
* **T7.6** `GET /latches` still writes NOTHING (the 21-A A4 property) with the new reads in place.
* **T7.7** ASCII-only in every added user-facing string.

---

## §7 File manifest

| File | Change |
|---|---|
| `swing/latches/constants.py` | `LATCH_CLEAR_REASONS`; `LATCH_DISPOSITIONS`; `_ALL_EXCLUDED_DISPOSITIONS`; **all THREE** module defaults — `DEFAULT_CRITERIA_LAPSE_SESSIONS`, `DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_ADR`, `DEFAULT_CRITERIA_LAPSE_MIN_WIDENING_PCT` |
| `swing/latches/service.py` | `_STATE_BY_CLEAR_REASON` (**both** reasons); `_resolve_criteria_lapse`; the `declined` terminal via `governing_decision`; the earliest-date-wins precedence; **the SIX new `derive_latches` keyword parameters** (verdicts, decline intents, the arm flag, three calibrations) ; `bar_status_by_ticker` threaded into the fold; the two stale docstrings (§4.1 rows 12-13) |
| `swing/latches/reader.py` | **`load_decision_intents` -> `dict[int, tuple[Intent, ...]]` keyed by candidate id, loading the WHOLE place/decline family (via the existing `list_intents_for_latch`)**; `structural_inputs_from_rows`; `load_session_structural_verdicts`; **`c.adr_pct` added to `_FIRE_SQL` + hydrated RAW into `FireRow`**; `build_latch_derivation` wiring |
| `swing/latches/models.py` | a `SessionStructuralVerdict` value type (`action_session`, `classification`, `cause`, **`conflicted`**); **`FireRow.adr_pct` (trailing, defaulted, RAW)**; **the ELEVEN trailing defaulted `Latch` diagnostic fields** — `lapse_failed_sessions`, `lapse_unverifiable_sessions`, `lapse_unverifiable_causes`, **`lapse_conflicted_sessions`**, `lapse_failed_count`, `lapse_unchecked_count`, `lapse_unverifiable_tail`, `directional_evaluable`, `directional_block_reason`, **`lapse_qualifying_session`**, **`lapse_would_clear_session`** — **plus the `LATCH_LAPSE_DIAGNOSTIC_FIELDS` roster** (§3.2.1) | — `lapse_failed_sessions`, `lapse_unverifiable_sessions`, `lapse_unverifiable_causes`, `lapse_failed_count`, `lapse_unchecked_count`, `lapse_unverifiable_tail`, `directional_evaluable`, `directional_block_reason` — **with `__post_init__` deriving/validating every COUNT against its TUPLE** (see §3.2.1) |
| `swing/latches/classification.py` | **`admissible_decisions()`** + the defaulted **`decision_bounds`** keyword on `classify_latch` + its production call site (Task 5a); the **`framework_withdrawn`** rung between rungs 4 and 5 — ABOVE telemetry health, OQ-16 (Task 6) |
| `swing/latches/orders.py` | `_CRITICAL_STALE_CLEAR_REASONS` per OQ-1 |
| `swing/evaluation/scoring.py` | `StructuralInputs`, `structural_inputs_from_results`, `structural_gate_passes`, `EXPECTED_TT_CRITERIA`, `EXPECTED_VCP_CRITERIA`; `bucket_for` composes them |
| `swing/config.py` | `LatchesConfig` — **all FOUR fields** (`criteria_lapse_armed`, `criteria_lapse_sessions`, `criteria_lapse_min_widening_adr`, `criteria_lapse_min_widening_pct`); `Config.latches`; `load()` wiring |
| `swing.config.toml` | `[latches]` with **ALL FOUR keys explicitly present** — `criteria_lapse_armed = false` first , `criteria_lapse_sessions = 5`, `criteria_lapse_min_widening_adr = 1.0`, `criteria_lapse_min_widening_pct = 2.0` (T5.1 parses the raw file and fails if any is missing) |
| `swing/web/view_models/latches.py` | `_state_label` branch; the UNVERIFIABLE + countdown + `directional_evaluable` fields |
| `swing/web/templates/latches.html.j2` | the UNVERIFIABLE render + the countdown + both over-threshold branches |
| `swing/cli_latches.py` | **the two report-only measurements** — the WOULD-CLEAR line (count + sessions, the calibration evidence OQ-9 exists to gather) and the same-session CONFLICT count (OQ-15). §4.3 marks the existing `sorted(LATCH_DISPOSITIONS)` iteration as needing no edit; that covers DISPOSITIONS and says nothing about these, which are new diagnostics on a different axis |
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
* **L5 — THE ARM FLAG, N AND *BOTH* MATERIALITY TERMS ARE NEVER LITERALS** outside `LatchesConfig`'s defaults and the mirror constant, drift-pinned. The materiality floor is derived from the fire's own `adr_pct` and is never a hard-coded percentage.
* **L6 — THE DIRECTIONAL CONJUNCT IS NON-NEGOTIABLE.** No variant that clears on gate failure alone ships, in any config state. 2a is a LIFETIME property and may be ASSERTED ONLY over a COMPLETE bar range.
* **L7 — NO VERDICT IS EVER JOINED TO A BAR.** The streak reads evaluated sessions; the conjuncts read archive bars by their own date. `candidates.close` is never read as a session's close (§2.2 query 5, gotcha #30).
* **L10 — A TERMINAL IS NEVER REWRITTEN BY A LATER EVENT.** Terminal selection is earliest-date-wins with rank only as a same-session tiebreak (§3.5). No later invalidation may overwrite an earlier lapse, and the fill rung compares against the earliest terminal.
* **L8 — PURITY.** `service.py` and `classification.py` stay pure: no DB, no network, no transactions. All I/O in `reader.py`.
* **L9 — `GET /latches` WRITES NOTHING** (21-A A4); `load_bars_with_status`'s `migrate=False` posture preserved. T7.6.

---

## §9 The rulings, and what remains open

**ALL THIRTEEN QUESTIONS ARE RULED** (`20260806T114306Z`). The canonical record is §0.3; the substance of each is at the section cited there. **Gate 0 is DISCHARGED — Task 1 may start.**

**What remains open, and it is deliberately small:**

* **THE SIX RESIDUALS (§0.3, R1-R6)**, and they are NOT all the same size:
  * **R1** (`declined` -> `horizon_expired`), **R2** (`declined` critical-stale) and **R3** (the rung vs rung 4) are **one-line changes** — a frozenset member, a map entry, a rung index.
  * **R4** (durable vs derived would-clear history) is a **schema decision and a condition-4 STOP** if answered "durable".
  * **R5** (may a successor's decision amend its predecessor?) and **R6** (`declined` vs `superseded`) are **lifecycle-semantics rulings that would change the fold**, not one-liners.
  **None blocks Task 1**; all six are flagged so they are RD's to correct rather than mine to have decided.
* **OQ-3, at MERGE.** Ruled in substance — the parity divergence is REAL, INTENDED and MEASURED, with its own line in the monthly read, never treated as drift. **Moot until the arm flag is set**, since the divergence window does not open under report-only. The requirement to carry it as a named expected-divergence class stands for whoever arms the flag.
* **THE CALIBRATION ITSELF.** N, the ADR multiple and the pivot-relative floor ship as `5 / 1.0 / 2.0` and are, by the framing ruling, **starting points to be measured rather than answers**. The report-only period exists to replace them with evidence. RD's own note: the 13% margin on VSTS at 1.0x says the lever is LIVE on the motivating case.
* **THE ACCEPTED LIMITATIONS, recorded as ruled — NOT as TODOs.** Flat-underwater never clears (OQ-7). One tick above the pivot confers immunity until the horizon (OQ-12). A missing archive bar disables the feature until backfilled (OQ-12). The declines-then-reverses class is REDUCED, not eliminated (§3.3) — **the residual the framing ruling exists to measure.** N retroactivity is accepted and disclosed, with a real flipped attribution logged as evidence that would re-open it (OQ-8).

## §10 The operator witness

Step-by-step per the operator's standing preference; the orchestrator drives one step and waits for his result before the next.

1. `GET /latches` on the live DB. **VSTS (fire 2026-07-27, pivot 16.90) renders UNVERIFIABLE — OFF SCREEN**, not plain `ARMED`, with its streak frozen at 3 of 5 and the sessions that produced it named (07-28, 07-29, 07-30). It is still LIVE and still fillable. **This is the case that motivated the amendment and it is the primary witness.** (Note §2.3(a): the brief describes VSTS as `watch`; it is not, and has not been since 07-30.)
2. **THE STEP RD ADDED, AND THE ONE THAT MATTERS MOST: the VSTS card's DECLINE CONTROL, LIVE.** Under OQ-4 the operator can resolve the off-screen latch he actually owns — the corrective path arriving rather than being described. **His choice here is his own real decision, not a demo**, so the witness is genuinely operator-authored evidence: if he declines, VSTS terminates `declined` at that session, leaves the live set, and enters `decision_r` scored as his call (T6.12). If he does not, the latch stays armed and UNVERIFIABLE and nothing is lost. **Either outcome is a valid witness** — which is what makes it safe to put in front of him. **The prepared-order form's presence is whatever 21-B's existing withholding rules decide** (§3.2.1 ruling 4) — an off-screen latch with an uncorroborated close may legitimately be withheld as `regime_undeterminable`, and the witness records which it is rather than requiring one. What IS required and witnessed: the decision control is present EITHER WAY.
3. **FTRE (fire 2026-07-20, pivot 18.34) shows NO `criteria_lapsed` clear anywhere in its history** — it cleared by `fill`. The founding case survives on live data, not only in a fixture. (Its fill date depends on item 5; §2.3(b).)
4. **The countdown on a live card, with the arm flag OFF — which is what SHIPS.** The operator sees `failed k of N checked sessions (u unchecked)` with the sessions named, and the panel states the N in force. **Nothing clears**, and that is the ruling being witnessed: the instrument runs before it is armed.
5. A seeded reversible demonstration of an actual `criteria_lapsed` clear **with the flag temporarily ARMED** — no live latch has reached N — following the 20-C reversible-seed-helper precedent: the `WITHDRAWN - criteria lapsed` label and the alarm at the ruled CRITICAL severity. **The flag is returned to OFF at the end of the step, and the return states that it was.**
6. `swing latches report` shows the withdrawn fire under `unattributable_r`, absent from the away rate and the discipline signal, with the away rate numerically unchanged by its presence.

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
| **A decline is recorded but the mandate stays live** — the V1-A gap | **CLOSED by the OQ-4 ruling**: the decline TERMINATES, so the decision point now corrects the stale pivot rather than only noting it. T4.21 |
| **Cross-arc composition** | Serial per brief §0; merge-integration named as a GATE (harness-architecture §5.1). **Two concrete couplings:** item 4 edits `swing/latches/orders.py`, the same file as OQ-1's frozenset; **item 5 moves trade 19's entry_date, which moves this arc's FTRE fixture** (§2.3(b)) |
| **The brief's VSTS premise is stale** | §2.3(a); the witness is built on the off-screen state |
