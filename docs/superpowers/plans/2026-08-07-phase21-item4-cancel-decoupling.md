# Plan — Phase-21 boundary paydown item 4: the cancel-affordance decoupling, the declined surface, `_PRICE_DP`, and the below-pivot refusal

**Status:** WRITING-PLANS deliverable. Plan only; nothing here is implemented.
**Base:** `main` @ `44abb5ba` (worktree `.worktrees/item4-cancel-decoupling`, branch `item4-cancel-decoupling`). Schema **v34**.
**Dispatch brief:** [`docs/wave-item4-cancel-decoupling-dispatch-brief.md`](../../wave-item4-cancel-decoupling-dispatch-brief.md).
**Ruled content:** RD's principle `20260803T110020Z` §3 (recording vs alarming) · RD's flag-B ruling (`docs/rd-state.md:48`) · CHARC's commissioning brief [§4](../../phase21-boundary-paydown-commissioning-brief.md) · the flag-3 routing (`docs/charc-state.md:11`). **Where this plan and a ruling disagree, the ruling governs.**
**Cells:** planning opus-high (this document) / executing opus-high.
**Gates:** RD merge-blocking (the classification consequences of new cancel rows; the decline session semantics) + operator witness.

---

## §0 READ THIS FIRST — three premise corrections and one SCHEMA-STOP

Every claim below was verified against the code in this worktree at `44abb5ba`, not against the brief. Four checks changed the shape of the plan.

### §0.1 Piece 4 is at a DIFFERENT SITE than the brief says. The brief's site is a bystander.

The dispatch brief §1 piece 4 locates "the below-pivot refusal" at `swing/latches/orders.py:156` — `expected_mandate_order_type`'s `if round(close, _PRICE_DP) < round(pivot, _PRICE_DP)`. That line is real and its equality disposition (`close == pivot` -> `PULLBACK`) is correctly described, **but it is not a refusal and it is not flag 3.** It selects between two mandate FORMS; it refuses nothing.

Flag 3 is traceable to its origin. `docs/charc-state.md:11` routes it: *"flag 3 -> item 4 with the collapsed-zone EQUALITY refinement verbatim (a `<=` would silently delete every collapsed-but-orderable zone)."* Flag 3 was raised by the item-2 sizing-basis arc, and that arc **wrote its own flag into the code it shipped** — `swing/recommendations/build.py:146-152`:

```
OUT OF SCOPE, FLAGGED: `compute_prepared_order` has the SAME hole as
check 4. Its breakout branch pairs `stop = latched_pivot` with
`limit = mandate_limit_price(zone_cap)`, so on that geometry it offers a
stop-limit whose limit sits below its own trigger; ...
That is 21-B's emitter, not this arc's scope.
```

Its sibling — the refusal item 4 must port — is `swing/recommendations/build.py:166`:

```python
if basis <= 0 or basis < pivot:
    return None, infeasible
```

**Strict `<`.** `basis == pivot` — the collapsed-but-orderable zone — is ACCEPTED. That is the equality refinement, verbatim, already implemented once. Item 4's job is to give `compute_prepared_order` the same refusal with the same strictness.

**Consequence for §2's stated interaction:** `compute_prepared_order` does not read `_PRICE_DP`, and neither does `mandate_limit_price` (it quantizes through `Decimal("0.01")` with `ROUND_FLOOR`, `constants.py:373-375`). **The 3x4 quantization coupling the brief names does not exist at the site flag 3 actually targets.** See §7 for what the coupling turned out to be instead, and §8 for the artifact-scale judgment that follows.

**Both equalities are pinned anyway.** The brief's `close == pivot` invariant is true, load-bearing and today only *indirectly* pinned (`tests/latches/test_orders.py:606` uses `18.339999`, a near-equal, not an equal). Task 4.3 pins it exactly. The dispatch's instruction to preserve it is honored to the letter.

### §0.2 SCHEMA-STOP — piece 2's READ half is UNWRITABLE at v34. Routed back, not worked around.

Piece 2's read half is *"the DECLINE control must remain available even when the prepared-order form is WITHHELD"* (plan test **T7.8**, pinned as a cost marker at `tests/web/test_view_models/test_latch_lapse_render.py:273`).

A prepared order is withheld in exactly three ways, and **all three return before any derivation object is built** (`swing/latches/order_intent.py:345-390`): `regime_undeterminable` (returns at :346), `sizing_degenerate` (:377), `sizing_infeasible` (:383). A decline recorded on a withheld card therefore carries **no framework block and no derivation block**.

Migration 0033 makes that row unwritable. **Codex R1 MINOR corrected the accounting below — the enforcement sites are FIVE, of three different kinds, and calling them all "mirrors" hid the fact that two of them need separate treatment.** Stated precisely:

**THREE WRITE BARRIERS — these are what make the row UNWRITABLE:**

| # | Kind | Location | The clause |
|---|---|---|---|
| 1 | Schema CHECK | `swing/data/migrations/0033_latch_order_intents.sql` | `CHECK (intent_kind NOT IN ('place','decline') OR (derivation_zone_cap_pct IS NOT NULL AND ... AND derivation_regime_close IS NOT NULL AND derivation_regime_close_session IS NOT NULL AND ...))` |
| 2 | Schema CHECK | same file | `CHECK (intent_kind NOT IN ('place','decline') OR (framework_order_type IS NOT NULL AND framework_limit_price IS NOT NULL AND framework_quantity IS NOT NULL AND framework_quantity > 0 AND framework_duration IS NOT NULL))` |
| 3 | Dataclass validator | `swing/data/models.py:_validate_shape_exclusion`, the `if kind in ("place", "decline")` branch | the same two requirements, derived from `DERIVATION_FIELD_MANIFEST` minus `DERIVATION_NULLABLE_ON_DECISION` |

**TWO FURTHER SITES that are NOT write barriers and must not be counted as such:**

| # | Kind | Location | What it actually is |
|---|---|---|---|
| 4 | **Route gate** (a 409 BEFORE any write) | `swing/web/routes/latches.py:1197-1206` | `if kind in _DECISION_KINDS: ... if block is None or not block.offered: return _conflict("... now WITHHELD ...")`. It refuses the submit earlier than the barriers do, so a fix that only relaxed the barriers would still 409 here. **It needs its own change and its own test.** |
| 5 | **Serializer branch** (no validation at all) | `swing/latches/order_intent.py:130`, `build_anchor_digest` | `if intent_kind in ("place","decline")` selects the framework-block digest. It VALIDATES nothing — `encode_derivation_value` deliberately encodes `None` as `""` — so it would silently produce a digest over an all-empty block rather than refusing. That silence is a hazard in its own right, not a barrier. |

**And a SIXTH obstacle, on the read side:** `rederive_prepared_order` (`swing/web/view_models/latches.py:1290-1315`) filters to **LIVE latches only**, and item 3a recorded, in that very comment, that *"an earlier cut of this arc WIDENED this filter and it was WRONG-SHAPED"*. So even with the barriers relaxed, the decision path for a withheld card is not a one-line widening.

The migration says *why* the barriers exist, in its own comment: **"decline -- the SAME framework + derivation block. Erasing it would leave RD unable to audit WHAT was declined."** That is a measurement decision, not an implementation accident.

**So T7.8 cannot be satisfied by a template edit.** Shipping the template edit alone would produce a control that renders and 400s on submit — precisely the defect 21-B's own review named at `swing/web/templates/partials/latch_orders.html.j2:180-182` (*"a control that renders and cannot be submitted"*), and precisely the review-ladder blind spot in `docs/harness-architecture.md` §5.1 (a ruling-fidelity sweep verifies MATCH, never WRITABILITY).

**Per the dispatch's stop condition, this routes back up.** Options, for the orchestrator/RD/CHARC to rule — this plan implements none of them:

* **(a) Migration 0035 — and it costs MORE than a migration.** Rebuilding `latch_order_intents` to relax barriers 1 and 2 for `decline` only (SQLite cannot drop a CHECK; a rebuild is the only path — the same shape as 0033's own `latch_view_events` rebuild) is necessary and **NOT sufficient**. The full list, and every item is load-bearing:
  1. barriers 1 + 2 — the migration;
  2. **barrier 3, `LatchOrderIntent._validate_shape_exclusion`** (`swing/data/models.py:2837-2857`), which independently raises `ValueError` for a `place`/`decline` row missing any non-exempt derivation field or any of the four framework fields, and which the route constructs BEFORE `record_intent` (`routes/latches.py:1232-1272`). **That edit is a `swing/data/` CARVE-OUT — a SECOND tripwire on top of the migration** (Codex R10 MAJOR: the first draft of this option listed the two CHECKs and the three non-barrier sites and silently skipped the barrier sitting between them, so option (a) as written was not buildable);
  3. site 4's route gate; site 5's digest branch (or a decision that an all-empty framework digest is acceptable); and the `rederive_prepared_order` liveness filter, carrying 3a's own recorded warning that widening it alone *"was WRONG-SHAPED"*;
  4. **the FORM itself, and the `decline_reason` chain that survives all of the above** (Codex R11 MAJOR). The withheld branch renders no form at all (`latch_prepared_order.html.j2:51-54`), so option (a) must also add a decline-only form carrying `candidate_id`, `view_session_date`, `prior_intent_id`, `intent_kind=decline` and a non-blank `decline_reason` — which stays REQUIRED at three independent layers that the relaxation does NOT touch and must not: step 2 (`routes/latches.py:1035-1037`), the dataclass (`models.py:2755-2759`) and the SQL CHECK (`0033`: `intent_kind <> 'decline' OR (decline_reason IS NOT NULL AND ...)`). A decline without a reason is unwritable and should stay unwritable; only the ORDER BLOCK is at issue.

  So option (a) crosses **TWO** of CHARC's §5 tripwires — new schema AND a `swing/data/` carve-out — and poses RD a measurement question underneath both: *a decline with no derivation block is a decline of what?* **That price is exactly why this is routed back rather than chosen here.**
* **(b) Route the withheld-card decline through `intent_kind='attest'` + `attested_disposition='chose_not_to_act'`**, which IS writable with no order block. That is a different disposition in a different place in the ladder (`declined` is a latch CLEAR REASON, `attest` is not), so it is RD's call, not an implementation choice.
* **(c) Ship the WRITE half only** and leave the read half labelled. **This plan takes (c) as its default**, because (c) needs no ruling and loses nothing: Task 2.1 ships flag B, Task 2.2 converts the silent absence into a LABELLED gap (the project's own standing rule — an unlabelled reduction is a quiet all-clear by omission), and Task 2.3 re-grounds the T7.8 cost marker on the real blocker.

### §0.3 A SEVEN-site FALSE CLAIM about `Latch.__post_init__`, found by checking the symbol rather than reading the prose

> **This heading said EIGHT in the first draft and the table below has always had seven rows** (Codex R1 MINOR). The miscount came from counting `order_intent.py:374-375` as two sites because the sentence spans two lines. It is recorded rather than silently corrected because it is the project's own existence-vs-completeness counting class, committed inside the section that exists to catch exactly that — and because the number is a return-report obligation.

Seven sites in `swing/` + `tests/` assert that `Latch.__post_init__` guarantees `pivot < zone_cap`. **It does not.** `swing/latches/models.py:266-295` is the whole method: it validates the state/reason enums, requires all three prices FINITE (`:279-280`), requires `latched_initial_stop < latched_pivot` (`:281-282`), checks the anchor type, the parallel reconfirmation tuples and the live/terminal coherence. **There is no `latched_pivot < zone_cap` check at all.**

Sites carrying the claim (`grep -rn` on the named symbol, `swing/` + `tests/`):

| Site | In scope? | The claim |
|---|---|---|
| `swing/latches/order_intent.py:374-375` | **yes** | "already guarantees latched_initial_stop < latched_pivot < zone_cap, so this cannot fire" |
| `tests/latches/test_order_intent.py:289` | **yes** | "already guarantees stop < pivot < cap so this cannot fire in production" |
| `swing/recommendations/build.py:139` | no | "(`Latch.__post_init__`: stop < pivot < zone_cap)" |
| `swing/recommendations/build.py:150` | no | "guarantees `pivot < zone_cap` on the RAW cap" |
| `swing/web/view_models/dashboard.py:756` | no | "(`Latch.__post_init__`: stop < pivot < zone_cap)" |
| `tests/recommendations/test_sizing_basis_is_the_limit.py:614` | no | same parenthetical |
| `tests/web/test_view_models/test_sizing_basis_is_the_limit.py:236` | no | same parenthetical |

What IS true: the production derivation builds `zone_cap` from `zone_cap_for_pivot(pivot)` (`swing/latches/service.py:99-103`), which is `round(p * 1.03, 4)` — greater than `p` for every ordinary pivot. It is **not** greater for a sub-normal one: `_usable_price` (`service.py:186-191`) admits any finite `pivot > 0.0`, and `round(1e-305 * 1.03, 4)` is `0.0`, so a `Latch` with `zone_cap == 0.0 < latched_pivot` is constructible from a real `candidates` row. So the invariant is a property of the *ordinary* derivation, not of the constructor, and stating it as a constructor guarantee is what let `compute_prepared_order` ship without the refusal.

This is the discharged-deferral class in `docs/harness-architecture.md` §5.1 rule 2 arriving one week later: **the keeper is the dangerous one.** Task 4.4 discharges `build.py`'s deferral note; the two in-scope claim sites are corrected in the same commit; the five out-of-scope sites are **FLAGGED in the return report, not fixed** (`swing/recommendations/` and `swing/web/view_models/dashboard.py` are outside the brief's scope list).

### §0.4 The `_PRICE_DP` count is FOUR — re-verified, and it is the definitions that are four, not the consumers

`grep -rn "_PRICE_DP" swing/ --include=*.py` in this worktree returns **33 lines across 4 files**: **4 definitions and 29 consumer lines**. A second grep across `swing/` + `tests/` for `PRICE_DP|PRICE_DECIMALS|price_dp|_DP = 2` returns nothing outside those four files except one *string literal* inside a belt test (`tests/web/test_routes/test_latch_cap_display_single_source.py:784`), which is a pre-fix specimen and not a definition.

> **This prose said "34 / 30" in the first two drafts while the table below said 5+19+3+2 = 29** (Codex R3 MINOR). The TABLE was right and the SUM was wrong — the third counting error in this document, after the seven-vs-eight of §0.3 and the fifty-vs-forty-three of §2 Task 1.1. Recorded rather than silently corrected: three instances in one artifact is the project's existence-vs-completeness class arriving as a *habit* rather than an accident, and the remedy that actually works is the one used here — **state the per-file rows, and derive the total from them rather than typing it.** (`--include=*.py` also matters: a bare `grep -rn` adds four `__pycache__` binary hits.)

| file | definition line | consumer LINES |
|---|---|---|
| `swing/latches/orders.py` | **40** | 156, 256, 257, 315, 427 (5 lines / 8 `round()` calls) |
| `swing/latches/service.py` | **56** | 287, 288, 289, 416, 417, 418, 419, 550, 552, 569, 570, 575, 584, 585, 799, 1168, 1169, 1216, 1217 (19 lines / 20 calls) |
| `swing/latches/order_intent.py` | **501** | 637, 722, 761 |
| `swing/web/view_models/latches.py` | **66** | 610, 611 |

The brief's corrected table (`service.py:56`, `view_models/latches.py:66`) matches the disk; the commissioning brief's `41` / `63` are stale, as the brief already said. **What this grep proves:** four `_PRICE_DP = 2` bindings and TWENTY-NINE consumer lines exist in `swing/`'s `.py` files. It does not prove no other module hard-codes `2` as a price precision by another name; a separate widening grep for that class is Task 3.4.

---

## §1 The four pieces, restated as what will actually be built

| Piece | What ships here | What does NOT |
|---|---|---|
| **1** cancel-affordance decoupling | The cancel control moves off the ALARM and onto the ORDER, and reaches INDETERMINATE (`PENDING_CANCEL`) orders | A cancel row against an order attributable to NO latch — blocked by the `bucket = 'aplus'` clause of `trg_loi_identity_coherent_insert`, and the LQDA case; see §5 |
| **2** the declined surface | **Flag B's write half**: a decline's effective session server-computed, backdating impossible by construction. Plus a LABELLED gap on the withheld branch | **The read half (T7.8) — SCHEMA-STOPPED**, §0.2 |
| **3** `_PRICE_DP` | Four definitions -> one public constant in `swing/latches/constants.py`; zero consumer behaviour change | Any change to the VALUE, the rounding sites, or which comparisons round |
| **4** the below-pivot refusal | `compute_prepared_order` refuses a limit BELOW the latched pivot, strict `<`, collapsed-but-orderable preserved. Plus both equality pins | The sibling in `swing/recommendations/build.py` (already correct) and the five out-of-scope false-claim sites |

**Task order is deliberate and is itself a finding (§8):** piece 3 lands FIRST and ALONE, so that every later diff in `orders.py` / `order_intent.py` / `view_models/latches.py` reads as behaviour rather than as rename churn.

---

## §2 Piece 3 — `_PRICE_DP` to a single source (lands first)

### The design

`swing/latches/constants.py` is the home. It is the module that *"imports NOTHING from `swing`"* (its own docstring, `:5-8`), it is already the domain owner of the latch price vocabulary (`mandate_limit_price`, `zone_cap_for_pivot`, `LATCH_ZONE_CAP_PCT`), and all four current definers already import from it or can without a cycle (`swing/web/view_models/latches.py` already does).

**Name: `PRICE_DP`** — public (it is now shared), and the same character count minus one, so no consumer line grows and no `E501` appears at the 100-char limit (`pyproject.toml:84`). The longest current consumer is `orders.py:427` at 84 chars.

**Each module imports the name; no module re-binds a literal.** A `from swing.latches.constants import PRICE_DP` binding in four modules is four names for ONE object and cannot drift; four `= 2` literals are four objects that can. This distinction is the whole point and is stated in the constant's docstring so the next reader does not "re-consolidate" the imports away.

The four existing rationale comments say the same thing in four voices (verified: `orders.py:37-39`, `service.py:53-55`, `view_models/latches.py:64-66` all cite the price-precision-parity gotcha; `order_intent.py:501` carries **no** rationale at all). The merged docstring states it once, and the consolidation gains `order_intent.py` a reason it never had.

### Tasks

**Task 3.1 — the constant.** Add `PRICE_DP = 2` to `swing/latches/constants.py` with the merged docstring: display precision on BOTH sides of every price comparison; an execution-grain sub-cent difference must not read as an edit or fork a latch or flip an agreement flag; and the note that consumers IMPORT it rather than re-binding a literal.

*Acceptance:* `from swing.latches.constants import PRICE_DP` works; `PRICE_DP == 2`.

**Task 3.2 — the four call sites.** Delete each `_PRICE_DP = 2`; import `PRICE_DP`; rewrite the **29** consumer lines mechanically. **No other edit rides this commit.**

*Acceptance:* `grep -rn "_PRICE_DP" swing/ --include='*.py' | wc -l` is **0** (RECURSIVE and `.py`-scoped: a bare `grep -c <dir>` errors rather than searching, and an unscoped `grep -r` counts four `__pycache__` binary hits, Codex R4 MINOR); `grep -c "^PRICE_DP = " swing/latches/constants.py` is 1; `ruff check swing/` clean; full fast suite green with **zero** test edits — a behaviour-preserving consolidation that needs a test changed is not behaviour-preserving.

**Task 3.3 — the discriminating tests.**

* `test_every_latch_price_comparison_reads_ONE_PRICE_DP` — walk `swing/latches/orders.py`, `service.py`, `order_intent.py`, `swing/web/view_models/latches.py` with `ast` and assert **three** things, because the first two alone are satisfiable by a module that keeps a hard-coded literal (Codex R5 MAJOR):
  1. **zero** bindings of `PRICE_DP` or `_PRICE_DP` **at ANY scope, by ANY binding form.** The check is *no `ast.Name` with a `Store` context and no `ast.arg`* carrying either name — which subsumes `Assign` / `AnnAssign` / `AugAssign` **and also** function parameters, `for` targets, `with ... as`, `except ... as` and walrus expressions (Codex R11 MINOR: a parameter named `PRICE_DP` shadows the import inside the function while every other assertion in this task still passes). The IMPORT binds through an `ast.alias`, not a `Name(Store)`, so it is permitted by construction and needs no exemption. **Node-type enumeration was the first fix and was still too narrow (Codex R7 MAJOR, then R11 MINOR):** `PRICE_DP: int = 2` is an `AnnAssign` and would have slipped past an `Assign`-only ban while every other assertion in this task still passed — the identity test cannot catch it either, because `2` is interned. An `Assign`-only ban is a single-source guarantee with a documented hole in it;
  2. `PRICE_DP` is imported from `swing.latches.constants`;
  3. **THE CONSUMERS ARE REACHED.** Every `ast.Call` to `round` in those four modules has a SECOND argument that is `ast.Name(id="PRICE_DP")` — never an `ast.Constant`. **Verified implementable today:** the only `round(x, <literal>)` text in those four files sits inside COMMENTS and DOCSTRINGS (`service.py:466-467`/`:578-579`, `order_intent.py:732`, `view_models/latches.py:594`), which `ast` does not see, so the rule is clean with no exemption roster. **Pair it with a count, and the count is 33, NOT 29** (Codex R6 MAJOR): post-change the `PRICE_DP` `ast.Name` references total **33** — `orders.py` 8, `service.py` 20, `order_intent.py` 3, `view_models/latches.py` 2 — because **29 is the number of distinct consumer LINES and several lines carry two `round()` calls** (`orders.py:156`, `:315`, `:427`; `service.py:799`). Asserting 29 would have made the belt fail against a CORRECTLY consolidated tree. **Two different quantities, and the coincidence is a trap:** 33 is ALSO the pre-change `.py` line count (4 definitions + 29 consumer lines), so the two 33s mean different things and neither may be derived from the other.
  *Discriminates:* red on the pre-fix tree (4 assignments, no importable `PRICE_DP`), and red on the half-done consolidation Codex named — imports added, a consumer left at `round(v, 2)`.
* `test_the_consolidated_constant_is_the_SAME_OBJECT_at_every_consumer` — `is`-identity across `orders.PRICE_DP`, `service.PRICE_DP`, `order_intent.PRICE_DP`, `view_models.latches.PRICE_DP`, `constants.PRICE_DP`.
  *Discriminates:* a re-binding `PRICE_DP = 2` inside a module would pass an `==` check and fail this one (`2 is 2` is True for small ints in CPython — so the assertion is on the **absence of a module-level Assign**, above, with this `is` test as the value-identity belt; both are required and neither is sufficient alone). **This is stated because a naive `is` test on a small int is vacuous** — see §9's vacuous-test discipline.
* `test_the_regime_boundary_still_uses_display_precision` — the existing `tests/latches/test_orders.py:606` case (`pivot 18.34`, `close 18.339999` -> `LIMIT`) re-run unchanged, asserting the consolidation did not move the rounding.

**Task 3.4 — the widening grep, and state what it proves.** Grep `swing/` for `round(.*, *2)` and `, 2)` in price contexts to determine whether any module hard-codes 2 as a price precision under another name. **Record the result in the return report as what the grep PROVES.** If hits exist outside the four files, FLAG them; do not widen scope.

**Task 3.5 — the cap-display belt is unaffected, verified not assumed.** `tests/web/test_routes/test_latch_cap_display_single_source.py` walks all of `swing/` for raw-cap renders. Its pattern `r"\bround\(\s*[\w.]*zone_cap\s*,"` (`:497`) matches only up to the comma, so the second argument's NAME is invisible to it, and its residual roster key `("latches/service.py", "round(draft.zone_cap,")` (`:519`) is stable across the rename. **Acceptance: that file's tests run and pass with no edit.** If the roster assertion fires, the consolidation touched something it should not have.

---

## §3 Piece 4 — the below-pivot refusal in `compute_prepared_order`

### The defect, with live arithmetic

`compute_prepared_order` (`swing/latches/order_intent.py:326-438`) computes `limit_price = mandate_limit_price(latch.zone_cap)` and, in the breakout regime, `stop_price = latch.latched_pivot`. Nothing checks their order.

| pivot | `zone_cap_for_pivot` | `mandate_limit_price` | today | correct |
|---|---|---|---|---|
| 0.019 | `round(0.019*1.03, 4)` = **0.0196** | **0.01** | offers `STOP_LIMIT stop 0.019 / limit 0.01` | **REFUSE** — the order cannot fill, and sizing off 0.01 against a 0.001 stop reports ~half the risk the 0.019 trigger actually carries |
| 0.25 | `round(0.25*1.03, 4)` = **0.2575** | **0.25** | offers `STOP_LIMIT stop 0.25 / limit 0.25` | **OFFER** — collapsed but ORDERABLE; this is exactly what the framework's own alarm side already treats as correct (`swing/latches/orders.py:545-555`) |
| 18.34 (FTRE) | 18.8902 | 18.89 | offers | offers — the control, unmoved |

The 0.019 row is the same harm `swing/recommendations/build.py:119-132` documents for its check 4, on the other surface. The 0.25 row is the equality the refinement protects.

### The trap the refinement exists to catch, and it is sitting in the same file

`swing/latches/orders.py:566-576` already carries:

```python
def _mandate_has_room(latch: Latch) -> bool:
    return _mandate_limit_of(latch) > latch.latched_pivot
```

**Strict `>`.** Reusing it as the refusal predicate (`if not _mandate_has_room(latch): withhold`) is a one-line, plausible-looking implementation that **refuses the collapsed-but-orderable zone** — the exact `<=` error the refinement forbids, wearing a helper's name. The two predicates answer different questions:

* `_mandate_has_room` — *does the cap clear the trigger*, i.e. is there a non-degenerate zone? Used to decide whether the "limit must be above the stop" SHAPE rule may be applied to an observed order at all.
* the refusal — *is the limit BELOW the pivot*, i.e. is the framework's own order impossible?

`==` sits inside the first and outside the second. **Do not reuse the helper.** Task 4.2's test is written to fail an implementation that does.

### Tasks

**Task 4.1 — the withheld reason.** Add `"limit_below_pivot"` to `LATCH_ORDER_WITHHELD_REASONS` (`swing/latches/constants.py:463`).

*Tripwire check, performed:* this frozenset has **no SQL mirror** — `grep -rn "regime_undeterminable|sizing_infeasible|sizing_degenerate" swing/data/migrations/*.sql` returns zero, and the value is never persisted (`PreparedOrderResult.withheld_reason` is a render-time field; `classification.py:1021`'s identically-named `AwayReport.withheld_reason` is an unrelated vocabulary validated against nothing). No test pins the set by equality (`grep -rn "LATCH_ORDER_WITHHELD_REASONS" tests/` returns zero). **No migration, no CHECK, no tripwire.**

*Acceptance:* `PreparedOrderResult(order=None, withheld_reason="limit_below_pivot", withheld_detail="x")` constructs.

**Task 4.2 — the refusal.** In `compute_prepared_order`, after `limit_price` and `stop_price` are computed and **before** `compute_shares`:

```python
if limit_price < float(latch.latched_pivot):
    return PreparedOrderResult(order=None, withheld_reason="limit_below_pivot", ...)
```

**Strict `<`, and the comment states why**, citing `build.py`'s check 4 as the sibling implementation and `_mandate_has_room` as the near-neighbour that must NOT be reused.

**Regime-independent, deliberately.** In the breakout regime the order cannot fill and the risk is understated; in the pullback regime the limit sits below the buy zone `[pivot, cap]` the mandate is defined over. In both, the quantized mandate is not the mandate. The sibling in `build.py` is regime-independent for the same reason.

*Acceptance:*
* pivot `0.019`, stop `0.001`, breakout -> `order is None`, `withheld_reason == "limit_below_pivot"`, non-blank detail.
* pivot `0.019`, stop `0.001`, **pullback** (`regime_order_type="LIMIT"`) -> same refusal.
* pivot `0.25`, stop `0.20`, breakout -> **order IS offered**, `limit_price == 0.25 == stop_price`.
* FTRE control (pivot 18.34) -> offered, byte-identical to today's result.

**Task 4.3 — the discriminating tests. Values computed under BOTH paths.**

| test | pre-fix | post-fix under strict `<` | post-fix under `<=` (the forbidden form) |
|---|---|---|---|
| `test_a_limit_BELOW_the_pivot_withholds_the_prepared_order` (pivot 0.019) | **FAIL** — order offered | PASS | PASS |
| `test_a_COLLAPSED_but_ORDERABLE_zone_is_STILL_offered` (pivot 0.25, limit == pivot == 0.25) | PASS | PASS | **FAIL** — withheld |
| `test_the_pullback_regime_refuses_the_same_geometry` (pivot 0.019, `LIMIT`) | **FAIL** | PASS | PASS |
| `test_the_FTRE_control_is_unmoved` | PASS | PASS | PASS |

**The first two together are the discriminator, and neither alone is.** The first distinguishes fixed from unfixed; the second distinguishes the correct fix from the over-eager one. This is the same two-sided construction the cap-display belt used with FTRE as its control (`tests/web/test_routes/test_latch_cap_display_single_source.py:19-24`) — and it is written that way for the same reason: an over-eager implementation passes every assertion in the first test.

**Plus the brief's equality, pinned exactly** (a new test in `tests/latches/test_orders.py`):

`test_close_EXACTLY_AT_the_pivot_is_the_PULLBACK_regime` — `expected_mandate_order_type(latched_pivot=P, last_close=P) == MANDATE_ORDER_TYPE_PULLBACK`, asserted at three pivots including one whose cent-rounding is non-trivial, **plus** the two neighbours that prove the boundary is where it is claimed: `close = P - 0.01` -> `BREAKOUT`, `close = P + 0.01` -> `PULLBACK`.

*Discrimination, computed both ways:* at `P = 18.34`, today `round(18.34,2) < round(18.34,2)` is `False` -> `PULLBACK`. Under a flipped `<=` it is `True` -> `BREAKOUT`, and the first assertion fails. Under a flip to `>` / an inverted return the `P - 0.01` neighbour fails. **The test fails if the boundary moves in either direction**, which is the dispatch's binding requirement. The existing `18.339999` case (`test_orders.py:606`) is a *near*-equality and passes under both `<` and `<=`, so it is not a substitute — that is why this test is added rather than relied upon.

**Task 4.4 — the discharged deferral in `build.py`: a CONFLICT BETWEEN TWO BINDING INSTRUCTIONS, ROUTED BACK rather than resolved here.**

`swing/recommendations/build.py:146-152` is a recorded deferral that Task 4.2 **discharges**. Two binding instructions collide:

* the dispatch brief §3 puts `swing/recommendations/` **out of scope** ("flag, never fix inline");
* `docs/harness-architecture.md` §5.1 rule 1 makes **deleting the deferral note PART of the fix**, and rule 2 requires re-verifying every claim it makes — which here means the two false `pivot < zone_cap` claims at `:139` and `:150` (§0.3 rows 3-4).

**The first draft resolved this unilaterally in favour of scope. Codex R1 MAJOR was right that this is not the implementer's call:** the shipped tree would then carry a note asserting a hole that no longer exists, forty lines from a check that no longer has a sibling — the exact corroborating-artifacts property §5.1 was banked to stop, freshly created by an arc that read the rule.

**ROUTED BACK. Two options, priced, for the orchestrator to rule BEFORE execution:**

| Option | Change | Cost |
|---|---|---|
| **(i) Documentation exception** — the executing implementer edits `swing/recommendations/build.py` comments ONLY (delete `:146-152`, correct `:139` and `:150`) in a dedicated `docs(recommendations):` commit | 3 comment blocks, zero executable lines, provable by a mechanical filter over the diff (the same proof form used for `b81da672`) | a named exception to the brief's scope list; needs the orchestrator's word |
| **(ii) Flag only** — `build.py` untouched; the return report carries the obligation | zero diff outside scope | the tree ships with a false note for at least one more arc; §5.1 rule 1 is knowingly not met |

**Precedent favours (i):** the `service.py:140` deferral of the same week was executed **inline as a comment-only commit** on the operator's word (`b81da672`), and doing so found a fourth false claim inside the half that was to be preserved. The plan's DEFAULT if no ruling arrives is **(ii)** — flag, do not touch — because an implementer may not grant itself a scope exception.

**Independent of that ruling, this task ships:**
1. `swing/latches/order_intent.py`'s new refusal comment names `build.py:146-152` as the deferral it discharges, cited by content search (`git log -S'OUT OF SCOPE, FLAGGED' -- swing/recommendations/build.py`), never by SHA — a rebase rewrites SHAs and does not rewrite the line.
2. The **in-scope** false-claim sites ARE corrected — `swing/latches/order_intent.py:374-375` and `tests/latches/test_order_intent.py:289` (§0.3 rows 1-2).
3. The five out-of-scope sites are named individually in the return report's flagged list, per the brief §4's rule that a deliberate not-fixed on a director-banked item lives in the flagged list and not only in a comment.

*Acceptance:* `grep -rn "post_init__" swing/latches/order_intent.py` shows no surviving claim that `pivot < zone_cap` is constructor-guaranteed; the corrected comment states what IS true (the ordinary derivation makes cap > pivot; the constructor does not, and `_usable_price` admits a pivot small enough to break it).

---

## §4 Piece 1 — the cancel-affordance decoupling

### The state on disk (all verified)

* The cancel form lives **inside the alarm loop**: `swing/web/templates/partials/latch_orders.html.j2:15` `{% for alarm in vm.alarms %}`, form at `:28-43`, gated `{% if alarm.broker_order_id and alarm.latch_candidate_id %}`.
* **Q2 confirmed:** `ORDER_RESTING_LATCH_CLEARED` is the ONLY alarm carrying a `broker_order_id` (`swing/latches/orders.py:788-798`); `LATCH_ARMED_NO_RESTING_ORDER` (`:745-751`) passes none. So it is the sole route to a `cancel` row.
* **Q1 confirmed, and it is worse than suppression:** an INDETERMINATE order never enters `resting_by_ticker` at all (`swing/latches/orders.py:644-645`, `if order.is_indeterminate: continue`), and its whole ticker is skipped by both alarm loops (`:707`, `:755`). `PENDING_CANCEL` is in `INDETERMINATE_ORDER_STATUSES` (`swing/latches/constants.py:170-173`). **So the order state produced BY the operator doing the right thing is exactly the state in which the framework offers him no way to record it.**
* Attribution already exists and is pure: `_match_latch` (`orders.py:443-465`), computed once per order at `:653-655`.
* `resolve_open_orders` -> `to_resting_orders` keeps `is_resting or is_indeterminate` (`orders.py:106-107`), so **indeterminate orders are already in the fragment's `orders` tuple** and already render in `vm.order_lines`. Nothing new needs to be fetched.

### THE DESIGN

**The affordance's subject is a BROKER ORDER the operator holds, not a problem the framework noticed.**

**Where it lives:** the orders fragment. It is the only surface holding the live broker book — `GET /latches` must not acquire one (A4, `swing/web/routes/latches.py:187`), and `POST /latches/intent` is forbidden from borrowing the Schwab client. A card-side control cannot know an order EXISTS.

**What it keys on — three conditions, and no fourth:**
1. the order is in THIS render's order set (BUY, resting **or** indeterminate);
2. `_match_latch` attributes it to a latch (live **or** terminal — `_latch_for_identity` already resolves both, `routes/latches.py:809-820`, and the shipped end-to-end test cancels against an INVALIDATED latch);
3. that is all.

**Explicitly NOT keyed on:** any alarm, the latch's liveness, the order's determinacy, or whether the order covers its mandate. Each of those is the alarm's predicate wearing a different name.

**Why unconditional over attributable orders rather than "when there's something wrong":** RD's principle says the affordance to record must not be gated on the alarm that detects. A gate of the form *"offer the control when the latch is terminal OR the order does not cover its mandate"* re-derives the alarm's own condition and fails the principle while appearing to satisfy it. The operator may decide to cancel at any time; the ledger exists to record that he did. The cost is one line and one button per attributable resting order — on today's live book, two or three.

### The alternative rejected, and why

**Rejected: keep the control on the alarm and WIDEN the alarm set** — emit a new alarm kind for indeterminate orders, and/or drop the `PENDING_CANCEL` suppression so the existing alarm fires there.

Three reasons:
1. **It re-couples recording to alarming.** A bigger alarm set is still an alarm set; the principle forbids the coupling, not the size.
2. **It would make the panel alarm on `PENDING_CANCEL`** — the state produced by the operator complying with the framework's own instruction. The framework would shout at him for doing what it asked. That is the erosion class this item exists to stop, inverted.
3. **The suppression is RULED CORRECT for alarms** (`orders.py:114-120`, `view_models/latches.py:1764-1768`: an unknown order book fires nothing; a false all-clear and a false alarm are both worse than an honest unknown). Widening it re-opens a false-alarm channel in order to gain a button. The alarm half stays byte-identical; only the recording half moves.

**Also rejected: put the control on the latch card**, keyed on latch state. The card has no broker book (above), and the schema requires a specific `actual_broker_order_id` (`CHECK (intent_kind <> 'cancel' OR (actual_broker_order_id IS NOT NULL AND length(trim(...)) > 0))`). A card-side control would have to ask the operator to TYPE an order id — a worse affordance, and one step from the by-ticker cancel hazard (c) the schema exists to make unwritable.

### Tasks

**Task 1.1 — the pure attribution surface.** In `swing/latches/orders.py`, add a frozen dataclass and a pure function:

```python
@dataclass(frozen=True)
class OrderAttribution:
    order_id: str
    ticker: str
    status: str
    is_indeterminate: bool
    latch_candidate_id: int | None

def attribute_orders_to_latches(*, latches, orders) -> tuple[OrderAttribution, ...]: ...
```

One row per BUY order that is resting OR indeterminate, `_match_latch`'d against that ticker's latches, **sorted by `order_id` in the RETURNED TUPLE ONLY**, for a stable render.

**`join_orders_to_latches` gains ONE optional keyword and no other signature change:**

```python
def join_orders_to_latches(*, latches, orders, attribution=None):
```

`attribution` is the tuple `attribute_orders_to_latches` returns. **`None` means "compute it internally"** — that default is load-bearing: `grep -rn "join_orders_to_latches(" tests/ --include=*.py | wc -l` is **43** invocation lines using the two-keyword form (across `tests/latches/test_orders.py`, `test_mandate_limit_contract.py`, `test_order_intent.py` and `tests/web/test_routes/test_latch_cap_display_single_source.py`), plus **one** production call site, and this task's acceptance is zero test edits. (The first draft said "~50"; Codex R3 MINOR counted it. An approximation is not evidence.) Internally the join derives its `{order_id: Latch | None}` map from the attribution rows, and **keeps building `resting_by_ticker` by iterating `orders` in INPUT ORDER** (`orders.py:641-648`).

> **Codex R1 MAJOR — the sort is not free, and the first draft got this wrong.** `_pick_reference_order` falls back to `orders[0]` (`orders.py:485`), and `LatchOrderJoin.orders` / `.unmatched_orders` are built from the per-ticker lists. Feeding the SORTED tuple into the join would re-order those lists, which can change which order becomes the reference and therefore change `order_stop_agrees` / `order_limit_agrees` — a silent behaviour change wearing a refactor's clothes, in the arc whose acceptance criterion is byte-identity. **Share the MAP, never the ordering.**

**THE CALLER COMPUTES IT ONCE (Codex R2 MAJOR).** `build_latch_orders_vm` (`swing/web/view_models/latches.py:2078-2080`) receives only `(joins, alarms)` today, so a VM that needs the attribution to build `cancel_controls` would call `attribute_orders_to_latches` a SECOND time — the exact prohibition this task states, re-created by following it. So the VM does, in this order:

```python
attribution = attribute_orders_to_latches(latches=derivation.latches, orders=orders)
joins, alarms = join_orders_to_latches(
    latches=derivation.latches, orders=orders, attribution=attribution)
```

and Task 1.2 builds `cancel_controls` / `cancel_unavailable_notes` from **that same tuple**. One `_match_latch` pass reaches both the alarms and the render — which is the property `orders.py:114-120` already demands for the sibling indeterminate predicate ("the SUPPRESSION and the RENDER must be computed from the SAME predicate over the SAME order set"). Both calls sit inside the existing `try/except` A6 ladder at `:2078-2088`, so an attribution failure degrades exactly as a join failure does today.

*Acceptance — one DISCRIMINATING test, one REGRESSION GUARD, labelled apart (Codex R2 MAJOR):*

* **DISCRIMINATING — `test_attribution_reaches_an_INDETERMINATE_order_the_join_drops`.** Seed a latch and a `PENDING_CANCEL` order at the latch's frozen prices. Assert `attribute_orders_to_latches` returns a row for it with the right `latch_candidate_id` and `is_indeterminate is True`, **and** that `join_orders_to_latches` still emits no alarm for that ticker. **Fails pre-fix: the function does not exist** (an `ImportError`/`AttributeError` is a red, and the alarm half pins that the drop is preserved).
* **REGRESSION GUARD, explicitly NOT discriminating — `test_the_join_still_picks_its_reference_order_in_BROKER_INPUT_ORDER`.** It passes on the pre-fix tree by construction; its whole job is to fail the ONE wrong implementation of this task (feeding the sorted tuple in). It is stated as a guard, not counted as acceptance evidence.
  **Its geometry is specified, because the obvious construction does not reach the fallback** (Codex R2): use TWO same-ticker orders sharing the CORRECT stop trigger and carrying DIFFERENT, both-wrong limits. `_match_latch` attributes on the stop leg, so **both** land in `mine`; neither agrees on both legs, so `_pick_reference_order` reaches `return orders[0]`. Supply them `[B, A]` with `A.order_id < B.order_id` and **assert `joins[cid].orders == (B, A)` — the ORDER OF THE RETURNED TUPLE, which is directly observable.**
  **Not the reference order (Codex R12 MAJOR):** `LatchOrderJoin` exposes no reference field (`models.py:485-507`), and on this geometry both candidates yield the SAME `order_stop_agrees=True` / `order_limit_agrees=False`, so the choice is unobservable through the agreement flags — the guard would have passed against the very implementation it exists to kill. Calling `_pick_reference_order` directly would test the helper rather than whether the join reordered its input. The tuple order IS what the sorted feed changes, so that is what the guard asserts. (The geometry is still the multiplicity shape the VM documents at `view_models/latches.py:2192-2199`.)
* `join_orders_to_latches`'s outputs are byte-identical for every existing test in `tests/latches/test_orders.py`, `test_mandate_limit_contract.py`, `test_order_intent.py` and `test_latch_cap_display_single_source.py`, with **zero test edits**.

**Task 1.2 — the VM.** Add to `swing/web/view_models/latches.py`:

* `LatchCancelControlVM(order_id, ticker, status_note, latch_candidate_id, prior_intent_id)`;
* `LatchOrdersFragmentVM.cancel_controls: tuple[LatchCancelControlVM, ...] = ()`;
* `LatchOrdersFragmentVM.cancel_unavailable_notes: tuple[str, ...] = ()` — one per order attributable to NO latch, so the gap stays LABELLED wherever it appears (today it is labelled only when the order also alarms).

`prior_intent_id` comes from the SAME `_prior_intent_id(intents_by_latch.get(cid, ()))` the alarm path uses today (`view_models/latches.py:2508-2509`) — the ruling-3 context anchor is unchanged.

`status_note` is display-ready: **exactly `broker status {STATUS}` when the order is INDETERMINATE, and the EMPTY STRING otherwise.** It exists so the operator can see WHY the framework is silent about that order while still offering to record his decision.

> **Codex R1 MAJOR — a VM field with no render instruction is dead weight, and the first draft's test would have passed without it.** The fragment already prints `ORDER STATUS INDETERMINATE` from `vm.indeterminate_tickers` (`latch_orders.html.j2:107-115`) **before any change**, so an assertion on "indeterminate is mentioned" is vacuous. Task 1.3 therefore specifies the markup and Task 1.4 asserts the exact per-order string, two-sided.

**Both new fields default to `()`** — every early-return `LatchOrdersFragmentVM(...)` in `build_latch_orders_vm` (`:2038`, `:2054`, `:2074`, `:2083`) must keep constructing, and an unavailable/degraded book must offer NO control (the same rule as the validity prompt: a control built on an unknown order book invites a decision he would infer from the panel's silence).

**Task 1.3 — the template.** In `swing/web/templates/partials/latch_orders.html.j2`:
* DELETE the inline cancel form and its `{% elif %}` note from the alarm loop (`:20-46`);
* add a `<section class="latch-cancel-log">` **outside** `{% if vm.alarms %}`, iterating `vm.cancel_controls`, each rendering the SAME `<form class="latch-cancel-form">` with the SAME field set and the SAME htmx attributes (`hx-post="/latches/intent"`, `hx-target="this"`, `hx-swap="outerHTML"`, `hx-headers='{"HX-Request": "true"}'`), then `vm.cancel_unavailable_notes`;
* **render `status_note` explicitly**, immediately before each control's form and only when non-empty:
  `{% if control.status_note %}<p class="latch-cancel-status">{{ control.status_note }}</p>{% endif %}`.
  Without this line the field is unreachable and Task 1.4's assertion is vacuous (Codex R1 MAJOR).

**Why delete rather than keep both:** two forms for one order emit identical fields, hence an identical idempotency key — the second is a harmless replay, but the operator sees the same button twice and the manifest gains a duplicate affordance. One control per order, one place.

**Class names, htmx attributes and field names are preserved verbatim** so the four shipped tests at `tests/web/test_routes/test_latches_orders_fragment.py:2432-2522` continue to bind. Checked, one by one:

| existing test | survives? | why |
|---|---|---|
| `test_a_stale_order_alarm_offers_a_CANCEL_control_bound_to_THAT_order_id` (`:2432`) | **yes** | it indexes on `'<form class="latch-cancel-form"'` and asserts fields — position-agnostic |
| `test_the_cancel_control_actually_writes_the_cancel_row_end_to_end` (`:2464`) | **yes** | same, plus the POST — the field set is unchanged |
| `test_an_UNATTRIBUTABLE_stale_order_LABELS_the_gap_instead_of_hiding_it` (`:2492`) | **yes** | the only seeded order is a stray -> attributable to no latch -> no control, note rendered |
| `test_the_absent_order_alarm_carries_NO_order_id_and_NO_control` (`:2512`) | **yes** | no orders seeded -> no controls |

`_invalidate`'s docstring (`:2420-2423`) claims invalidation is *"the only state that earns a cancel control"*. **That becomes false here and is corrected in the same commit** — a stale claim left beside a passing test is the §0.3 class.

**Task 1.4 — the discriminating tests** (new, in `tests/web/test_routes/test_latches_orders_fragment.py`; frozen clock via the existing `frozen_panel_clock` fixture):

* `test_a_PENDING_CANCEL_order_STILL_offers_the_cancel_control` — seed an ARMED FTRE latch and a matching order with `status="PENDING_CANCEL"`. Assert `latch-cancel-form` present, bound to that `order_id`; assert the **exact** per-order string `broker status PENDING_CANCEL` inside `class="latch-cancel-status"`; **and** assert `ORDER_RESTING_LATCH_CLEARED` / `LATCH_ARMED_NO_RESTING_ORDER` are ABSENT while `ORDER STATUS INDETERMINATE` is present — i.e. the ALARM half is untouched.
  *Discriminates:* pre-fix the whole ticker is skipped, so no control renders at all. The paired alarm assertions fail any implementation that bought the control by widening the alarm set. The **exact-string, class-scoped** status assertion is what keeps it from passing on the pre-existing `ORDER STATUS INDETERMINATE` banner (Codex R1 MAJOR).
* `test_an_ORDINARY_resting_order_carries_NO_status_note` — the healthy-covering-order state below, asserting `latch-cancel-status` is ABSENT from the render. **GUARD** (§9.1), and the other side of the two-sided pair: without it, an implementation that emits a status note unconditionally passes the test above.
* `test_a_HEALTHY_covering_order_ALSO_offers_the_cancel_control` — ARMED latch, correctly-shaped GTC covering order, **zero alarms**. Assert the all-clear line AND a cancel control for that order.
  *Discriminates:* this is Q2. Pre-fix there is no alarm, therefore no control. It fails any implementation that re-keys the control on a rediscovered alarm predicate.
* `test_the_cancel_control_on_a_NON_ALARMED_order_writes_the_row_end_to_end` — scrape the form from the previous state, POST it, assert one `('cancel', <order_id>)` row. Rendered is not reachable (the 21-B lesson, its own test at `:2464`).
* `test_the_alarm_block_no_longer_carries_a_FORM` — assert the whole **`<div class="latch-alarms">` CONTAINER** holds no `<form`, and separately that a `latch-cancel-form` exists under `<section class="latch-cancel-log">`.
  **Scope it to the CONTAINER, not to the `<p>` (Codex R4 MAJOR).** Today's form at `latch_orders.html.j2:29` is a SIBLING of the alarm `<p>` (which closes at `:19`) and a CHILD of `.latch-alarms` at `:14` — so a `<p>`-scoped assertion is GREEN pre-change and would let the inline form survive inside `.latch-alarms` while acceptance reported success. The container-scoped form is RED pre-change, which is what makes it a discriminator.
* `test_an_UNAVAILABLE_broker_book_offers_NO_cancel_control` — resolution kind != `ok`; assert no `latch-cancel-form`. **GUARD, not acceptance evidence** (§9.1): green pre-change too, because `build_latch_orders_vm` already returns early with no controls at `:2072-2076`. It kills the one wrong implementation — building controls outside the `available` branch.
* `test_an_order_attributable_to_NO_latch_gets_a_NOTE_and_no_control_even_with_NO_alarm` — a stray order beside a LIVE latch (which today produces no `ORDER_RESTING_LATCH_CLEARED`, `orders.py:763-765`). Assert the **exact new cancel-gap markup** — `class="latch-cancel-unavailable"` carrying "no mandate to log a cancel against" — and no control.
  **Assert the NEW class, never merely "a labelled note" (Codex R4 MAJOR).** The VM already appends a DISAGREEMENT line for every `join.unmatched_orders` (`view_models/latches.py:2452-2458`) and the template already renders it (`latch_orders.html.j2:122-128`), so "a note is present" is GREEN pre-change. Only the cancel-gap class is RED — today `cancel_unavailable_note` is reachable solely through an alarm, and this geometry produces none.

**Task 1.4b — THE ALARM-OWNERSHIP COMMENTS, corrected in the same commit as the move (Codex R8 MINOR).** Two in-scope comment blocks assert that the alarm's `broker_order_id` is what makes the browser's Cancel control possible, and both become FALSE the moment Task 1.3 moves the control:
* `swing/latches/models.py:517-523` — *"without this the panel cannot offer the per-order Cancel control ... so a `cancel` intent ... is unreachable in a browser"*;
* `swing/web/view_models/latches.py:300-307` — describes `broker_order_id` / `prior_intent_id` / `cancel_unavailable_note` as *"the per-order CANCEL control's anchors ... Present together or not at all"*, which stops being true when `prior_intent_id` and `cancel_unavailable_note` leave `LatchAlarmVM`.

Each must **state what the field is FOR after the move** — `OrderAlarm.broker_order_id` is retained as alarm CONTENT (which order the alarm is about), not as a control anchor — rather than being deleted and leaving the reader to infer it. **This is the §5.1 discharged-deferral rule applied prospectively:** the arc that falsifies a comment owns correcting it, and a comment that still READS true after being voided is the invisible failure the rule exists to stop.

**And TWO MORE blocks say the same thing in other words (Codex R9 MINOR) — the roster is FOUR, not two:**
* `swing/web/templates/partials/latch_orders.html.j2:20-27` — *"THE PER-ORDER CANCEL CONTROL on a stale-order alarm"*, which is the coupling this piece removes. It is deleted with the form in Task 1.3 and its surviving reasoning (log-only; targets a SPECIFIC broker order id, never a ticker — hazard (c)) moves to the new `.latch-cancel-log` block, because that reasoning is still true and still load-bearing;
* `tests/web/test_routes/test_latches_orders_fragment.py:2434-2443` — the docstring saying `OrderAlarm` *"now carries it STRUCTURALLY"* so the control can be bound. The TEST still passes (§4's survival table); its stated REASON is what changes.

**Enumerating four rather than accepting two is the point.** §0.3's whole lesson is that a claim about a symbol is checked against that symbol's CONSUMERS — so the executing implementer runs `grep -rn 'cancel control\|Cancel control' swing/ tests/` and treats the RESULT as the roster, rather than this list.

*Acceptance:* no surviving block asserts that the alarm field enables the control; each names its subject's surviving purpose; the grep above returns nothing that still claims the coupling.

**Task 1.5 — WITHDRAWN. `swing/web/static/app.css` IS OUT OF SCOPE (Codex R7 MAJOR).**

The dispatch brief §3's in-scope list is `swing/latches/*`, `swing/web/view_models/latches.py`, `swing/web/routes/latches.py`, `swing/web/templates/partials/latch_*` and their tests. **`swing/web/static/app.css` is not on it**, and the first draft put it there on the plan's own authority — the precise thing §3 Task 4.4 says an implementer may not do, committed four sections later in the same document.

**Consequence, and it is small:** `.latch-cancel-form` and `.latch-cancel-unavailable` are ALREADY styled (`app.css:608-612`) and are the classes the moved control keeps, so the control looks the same as today. The two NEW class names — `.latch-cancel-log` on the section and `.latch-cancel-status` on the status line — ship as **markup with no CSS rule**. A class needs no rule to exist, so **every test in §9.1 is unaffected**; the only cost is that the new block is unstyled. Nothing renders wrongly and nothing is hidden.

**AND THE FLAG CARRIES A FALSIFIED COMMENT, not just missing rules (Codex R9 MINOR):** `swing/web/static/app.css:605-607` reads *"The per-order cancel control rides INSIDE an alarm block, so it takes no box of its own -- a second bordered box inside an alarm reads as a second alarm."* After Task 1.3 the control does NOT ride inside an alarm block, so both the claim and the styling decision it justifies are void. **The flagged follow-up is therefore three lines, not two: the comment, `.latch-cancel-log`, `.latch-cancel-status`** — and the comment is the part that matters, because an unstyled class is visible and a false rationale is not.

**FLAGGED for the return report**, alongside the `build.py` item — the same shape of decision, and the same default: an implementer does not grant itself the exception.

---

## §5 Piece 1's flagged gap — the LQDA case is NOT fixable here

The brief §1 cites the live LQDA render as *"the erosion the principle exists to stop — the operator placed the order the framework told him to place."* The erosion is real and it is on screen today. **The fix is not in item 4.**

* LQDA's resting order implements a **hypothesis recommendation**, not a latch mandate (`docs/rd-state.md:26`). It matches no latch's frozen prices because there is no latch.
* **The DB does block it — but NOT for the reason the first draft gave, and the correction matters (Codex R6 MAJOR).** The draft said the `NOT NULL REFERENCES candidates(id)` FK prevents it. It does not: that FK only requires SOME `candidates` row, and there is no latch FK and no latch-existence CHECK anywhere in migration 0033. **The actual barrier is the trigger** `trg_loi_identity_coherent_insert` (`0033:729-742`), whose first clause is
  ```sql
  WHERE NOT EXISTS (SELECT 1 FROM candidates c JOIN evaluation_runs e ...
                    WHERE c.id = NEW.candidate_id AND c.bucket = 'aplus' ...)
  ```
  so **no `latch_order_intents` row of ANY kind may reference a non-A+ candidate.** RD's state pointer records LQDA as a `near_trigger` hyp-rec (`docs/rd-state.md:26`), which the trigger therefore refuses. *The doc is a lead: whoever scopes the Phase-22 item should read LQDA's actual `candidates.bucket` off the live DB rather than inherit that line.*
* Two further gates sit above the trigger and are NOT schema: `_latch_for_identity` (`routes/latches.py:809-820`) must find a derivable latch for the submitted `candidate_id`, and the panel only offers what it can attribute. **Naming them apart matters** — a plan that files a route gate under "schema-prevented" is doing the thing the adjudication rule forbids: claiming a defense without checking which layer actually holds it.
* The actual fix is **latch-on-acceptance for hyp-rec offers**, which RD has positioned (`docs/rd-state.md:49`) and which the dispatch brief §3 puts explicitly out of scope: *"Latch-on-acceptance for hyp-rec offers is Phase-22, not this arc, however tempting LQDA makes it."*

**What item 4 does change for LQDA:** nothing about the alarm, and the labelled note stays. What it does change is that the note is no longer *conditional on the alarm firing* — an unattributable order now gets its labelled gap on every render (Task 1.2's `cancel_unavailable_notes`), not only when it happens to alarm.

**FLAGGED for the return report**, not fixed.

### §5.1 A SECOND FLAG THIS ARC RAISES BUT MAY NOT FIX — the CLI origin report never marks a cancel EXACT

**Found at Codex R8, verified on disk, OUT OF SCOPE, and it is a FALSE COMMENT of the §0.3 family.**

`swing/cli_latches.py:130-134` states, as the docstring of `_inferred_origin`:

> *"The ONE place V1 IS exact is named as such: where a broker order id was captured on a `cancel` or `validity` row, THAT order's association with a ledger row is exact rather than inferred."*

The code two lines below gates exactness on the parent link:

```python
parent = order_intent.validated_place_intent_id
if parent is not None and parent in place_intents:
    return "framework_inferred", "EXACT (captured broker order id)"
```

**A `cancel` row can never satisfy it.** `validated_place_intent_id` is legal ONLY on a `validity` row — `LatchOrderIntent._validate_validity_columns` raises for any other kind, and migration 0033 mirrors it — so a cancel's parent is ALWAYS `None` and the branch is unreachable for that kind. Every cancel row falls through to the params heuristic and is reported as inferred. **The docstring's claim about `cancel` is false today**, and it is false for the same reason as §0.3's: nobody checked the named symbol against its consumers.

**Piece 1 does not create this defect — it makes it MATTER.** Today `cancel` is reachable only through a stale-order alarm, so the misclassified population is tiny. After piece 1 every attributable resting order can produce one, and the exact-linkage number RD reads is exactly what those rows were introduced to supply (`constants.py:421-432`, the `LATCH_BROKER_ORDER_ID_KINDS` derivation, whose own comment calls the attestation path *"the ONE path that exists for orders the framework did not prepare"*).

**Not fixed here:** `swing/cli_latches.py` is not on the brief §3 in-scope list, and the classification it produces is an **RD measurement surface**, not an implementation detail — whether a captured broker order id on a cancel row counts as EXACT linkage is his call, not the executing implementer's. **FLAGGED for the return report, with the mechanism, so RD can rule it beside the cancel-row classification question he is already gating.**

---

## §6 Piece 2 — flag B's write half (and the labelled gap)

### The defect flag B closes, traced to its consequence

`POST /latches/intent` sets `action_session_date = anchor.isoformat()` — the **form's** anchor (`swing/web/routes/latches.py:1176`) — for every kind except `validity`. And `_classify_anchor` (`:148-163`) returns `ok` while `sessions_behind(current, anchor) <= 1`, so a form rendered on session S and submitted during S+1 records a decline **filed under S**.

That is not cosmetic. `_resolve_decline` (`swing/latches/service.py:305-336`) reads `governing.action_session_date` **directly** as the `declined` terminal's session, and `_Terminal.order_key` is `(session, rank)` (`service.py:158-161`). **A backdated decline can therefore pre-empt a terminal dated between the render and the submit** — including a FILL. That is the orphaned-fill vector RD's ruling names.

### RD's ruling, verbatim (`docs/rd-state.md:48`)

> **`declined`:** operator-authored terminal, uniform, effective session = **CURRENT at POST, server-computed; a stale form anchor -> the beacon's reject-with-notice. Backdating impossible by construction** (flag B — its write half lands in item 4 with the render/route).

### The design — BOTH halves, because either alone leaves a hole

1. **Server-computed:** for `intent_kind == "decline"`, `action_session_date = action_session_for_run(now).isoformat()`, derived from the server clock and **never** from the form. This is what makes backdating impossible BY CONSTRUCTION rather than by validation — a forged or replayed anchor cannot reach the stored value at all.
2. **Anchor must EQUAL the current session:** a decline whose form anchor is 1 session behind gets `_stale_notice`-shaped rejection (a 409 telling him to reload), rather than being silently accepted and stamped with today. Without this, the operator answers about session S and the ledger records S+1 — server-computed but *dishonest*. This is the same strictness `POST /latches/orders` already applies for a closely-related reason (`routes/latches.py:221-230`: *"a stale anchor would judge orders placed or cancelled AFTER that session against the older mandates"*).

**With both, the two values are equal by construction**, which also keeps the idempotency key coherent: `build_idempotency_key` is passed `action_session_date=raw_session` (the form's raw spelling, `routes/latches.py:1092`) while the row would store the server's — an incoherence that (2) removes rather than papers over.

### The residual this plan POSES rather than decides

**RD ruled `declined`. He did not rule `cancel` or `attest`.** Both also store the form's anchor, and both are recordings of an operator act whose effective session has the same backdating exposure — though neither authors a latch terminal, so neither carries the orphaned-fill vector.

**This plan changes `decline` ONLY**, and asks the question at plan review rather than generalising RD's ruling for him. A silent extension to three kinds would be exactly the *"an implementer guess resolving a contradiction"* failure CHARC named on 21-B. Task 2.4 pins the *current* behaviour for `cancel` and `attest` so the divergence is visible rather than implicit.

### Tasks

**Task 2.1 — the write half.** In `POST /latches/intent`, **inside step 5 (FIRST-WRITE VALIDATION), immediately after the existing `_classify_anchor` verdict block** (`routes/latches.py:1162-1174`):
* `if kind == "decline"` and `anchor != current` -> return the stale 409 with a decline-specific message;
* set `action_session_date` from `action_session_for_run(now)` for `decline`, never from `anchor`.

The `validity` branch's server-copy from the parent (`routes/latches.py:1190-1194`) is untouched — it answers for a different session on purpose.

**WHY THE GATE STAYS IN STEP 5 AND IS NOT MOVED AHEAD OF THE REPLAY LOOKUP (Codex R2 MAJOR, adjudicated ACCEPTED-WITH-A-CORRECTION).** Codex is right that the replay gates (`get_intent_by_key` at `:1120`, `_semantic_replay` at `:1146`) run BEFORE the freshness check and can return 200. Its proposed fix — move the gate ahead of them — must NOT be taken: the project's SELECT-first idempotency discipline requires the terminal-state read to precede validation, the route's own docstring argues the ordering explicitly (`:960-961`), and moving it would make a double-click on a page that went stale between clicks FAIL instead of collapsing.

**And the vector Codex describes does not open for new writes**, because `build_idempotency_key` folds in `action_session_date=raw_session` (`:1092`) — the FORM's raw spelling. Post-fix, a stale-anchor decline is refused before it writes, so **no row bearing a stale-anchor key can ever come into existence**, so the replay lookup for that key can never hit. The replay path also writes nothing on any branch.

**What IS real, and is ROUTED to RD rather than decided here:**
1. **Rows written BEFORE this fix** keep an anchor-derived `action_session_date`, and `_resolve_decline` reads it directly as the terminal's session (`swing/latches/service.py:332-336`). Flag B is forward-looking; whether legacy `decline` rows need an audit or a correction is a measurement call. **The plan does not migrate or rewrite any row** (the ledger is append-only).
2. **A stale-form REPLAY of such a legacy row returns 200, not the ruling's reject-with-notice.** Nothing is written, so nothing is backdated; the gap is that the operator is not told his page is stale. Naming it is the honest treatment.

*Acceptance:* a decline submitted with a 1-session-stale anchor 409s and writes NOTHING; a decline submitted with a current anchor writes `action_session_date == action_session_for_run(now)`; every other kind's stored session is unchanged; **and a test asserts the replay ordering is UNCHANGED** — a `place` double-submit on a stale-but-previously-written key still collapses to its existing row rather than 409-ing, so the fix cannot be implemented by moving the gate.

**Task 2.2 — the labelled gap on the withheld branch.**

> **Codex R1 MAJOR — the first draft said "render a sentence from the VM" without naming a field, and `PreparedOrderVM` has none.** Following it literally would either reference an undefined attribute (Jinja renders `Undefined` as empty, so it would fail SILENTLY) or hand the wording to the template, which is forbidden by that template's own no-logic contract. The field is now named and its every construction path is enumerated.

1. **Add `decision_unavailable_note: str = ""` to `PreparedOrderVM`** (`swing/web/view_models/latches.py:155-184`), display-ready, with a docstring saying it is non-empty ONLY on the withheld branch.
2. **Populate it at every construction path**, and there are exactly two: `_withheld_block(reason, detail)` (`:427-439`) sets it; `_build_prepared_order_vm`'s offered return (`:578-587`) leaves it `""`. Both are asserted, because a default that is never overridden and a field that is set everywhere are indistinguishable from a test that only looks at one branch.
3. **Render it explicitly** in `latch_prepared_order.html.j2`'s `{% else %}` branch, below `po.withheld_detail`, guarded `{% if po.decision_unavailable_note %}`.

The sentence states that a decline cannot be recorded against a withheld order **and why** — the ledger requires the framework order a decline is a decision ABOUT (§0.2 barriers 1-3) — plus what to do instead. ASCII only.

**This does NOT satisfy T7.8** and the plan says so in the VM docstring as well as here. It converts a silent absence into a labelled one, which is the project's standing rule and the honest interim under §0.2 option (c).

*Acceptance:*
* `test_the_WITHHELD_branch_LABELS_why_a_decline_cannot_be_recorded` — withheld card renders the note text. **Discriminates:** fails pre-fix (no such string anywhere in the render).
* `test_the_OFFERED_branch_carries_NO_decision_unavailable_note` — offered card does not. **GUARD** (§9.1): green pre-change; it kills an implementation that sets the field on both construction paths.
* `test_the_WITHHELD_branch_STILL_offers_no_control` — **no `<form>` and no submit element** inside the prepared-order `<section>` on the withheld branch. **GUARD, not acceptance evidence** (§9.1): green pre-change (`latch_prepared_order.html.j2:51-54` already has none). **Scope the assertion to that `<section>`, not to the page** — the attest form at `:80-108` renders on the same page and would make a page-wide assertion either vacuous or wrong. It kills the one wrong implementation: adding an inert affordance while labelling the gap, which is the 21-B defect class this whole item is about.

**Task 2.3 — re-ground the T7.8 cost marker.** `tests/web/test_view_models/test_latch_lapse_render.py:273` asserts the decline button sits inside `{% if po.offered %}` and its docstring says item 4 will flip it. The **assertion stays** (the shape is unchanged); the **docstring is corrected** to record that the blocker is the ledger contract, not scope — naming the three mirrors of §0.2 and the migration a fix would need.

*Acceptance:* the test still passes; its stated reason matches the code. This is `docs/harness-architecture.md` §5.1 rule 2 applied to a test docstring: a deferral note WITH an assertion surface, whose prose half is still unreachable by the assertion.

**Task 2.4 — the divergence pins. TWO tests with DIFFERENT jobs, and they are labelled apart.**

**(a) THE DISCRIMINATING TEST — `test_a_DECLINE_with_a_STALE_anchor_is_REFUSED_and_writes_NOTHING`** (frozen clock).

*Discrimination, computed both ways.* The obvious construction is REJECTED as vacuous and the rejection is recorded so the next reader does not re-derive it: freeze `now` on session `S+1` and submit a form anchored at `S+1`, and the stored session is `S+1` **pre-fix (from the anchor) and post-fix (from the clock)** — identical, proving nothing.

The discriminating construction is the **stale anchor**: anchor `S`, clock `S+1`, where `S` is the previous NYSE session (so `_classify_anchor` returns `ok` today, `sessions_behind == 1`).

> **AND THE FIXTURE MUST MAKE THE PREPARED ORDER *OFFERED* AT `S`, OR THE TEST PROVES NOTHING (Codex R11 MAJOR).** `decline` stays in `_DECISION_KINDS`, so step 5 re-derives the block and 409s when it is WITHHELD (`routes/latches.py:1197-1206`) — and **withheld is the DEFAULT on today's substrate**, as §0.2 itself says. A carelessly seeded fixture therefore returns 409 + zero rows PRE-fix as well, for an unrelated reason, and the whole table below collapses into agreement. **And the corroborating evidence is dated `P = session_offset(S, -1)`, NOT `S` (Codex R12 MAJOR — the first attempt at this fixture was temporally impossible).** `build_latch_derivation` sets `derivation_session = session_offset(horizon_session, -1)` (`swing/latches/reader.py:892`) and loads bars only through it (`:948-950`), so with the anchor at `S` the derivation session is `P`: a bar dated `S` is never loaded, and a close STAMPED `S` classifies as `future_stamp` against `P` — leaving the regime undeterminable and the order withheld, which is the very failure this fixture exists to avoid. So the fixture seeds the A+ fire anchored at `S` but puts **`candidates.close`, `evaluation_runs.data_asof_date` AND the corroborating archive bar all at `P`** — rung A of the 21-G ladder evaluated at the session the derivation actually uses — plus a **feasible sizing geometry**. The test then asserts `prepared_order.offered is True` at anchor `S` as an INLINE PREMISE before advancing the clock. If that premise ever stops holding, the test fails on the premise line and says so, instead of passing for the wrong reason.

| | pre-fix | post-fix |
|---|---|---|
| HTTP status | **200** | **409** |
| `latch_order_intents` rows | **1**, `action_session_date == S` | **0** |

The test asserts BOTH, so it fails pre-fix on both counts and cannot pass vacuously. **The ledger starts EMPTY in this test and that is deliberate**: with an empty ledger neither replay gate can hit, so the test measures the freshness gate and nothing else (Codex R2 noted the empty ledger; it is a property of the test, not a blind spot in it — the replay interaction is pinned separately by Task 2.1's replay-ordering assertion).

**(b) THE COST MARKER — `test_a_NON_DECLINE_KIND_with_a_STALE_anchor_is_STILL_ACCEPTED_today`, PARAMETERISED over `("cancel", "attest")`** (frozen clock).

> **Codex R5 MAJOR — §6 claimed Task 2.4 pinned `cancel` AND `attest`, and only `cancel` was specified.** `attest` takes the same `action_session_date = anchor.isoformat()` at `routes/latches.py:1176`, so an accidental extension of flag B to it would have shipped with no failing test — on the kind whose prompt is DESIGNED to be answered long after the fact. One parameterised test makes the sentence true rather than narrowing it.

> **Codex R1 MINOR — the first draft named this a "divergence pin" and put it in the acceptance set, where it does not belong.** A *current*-anchor cancel stores the form anchor before and after this change, so that shape passes on both trees. **This is EXPLICITLY NOT a discriminating test and is not counted as acceptance evidence for any task.**

It is a cost marker with a real failing condition: anchor `S`, clock `S+1`, `intent_kind` in `("cancel", "attest")` -> **200 and one row stamped `S`** for each, which is today's behaviour and is what RD did NOT rule on (§6's residual).

> **EACH KIND'S PAYLOAD MUST BE COMPLETE OR THE TEST NEVER REACHES THE SESSION LOGIC (Codex R6 MAJOR).** Step 2 rejects an `attest` with no `attested_disposition` (`routes/latches.py:1038-1040`) and a `cancel` with no `actual_broker_order_id` (`:1056-1064`) — both **before** step 5's anchor handling. So the parameters carry their required field: `cancel` -> `actual_broker_order_id="4242"`; `attest` -> `attested_disposition="chose_not_to_act"` (chosen because `acted_manually` is the only disposition permitted to carry a broker order id, and this row carries none). Both also need a `candidate_id` resolving through `_latch_for_identity`, i.e. a real seeded latch.

**It fails the moment anyone extends flag B to either kind**, which is precisely when the next reader must come back to RD — the same construction as `test_the_DECISION_control_still_rides_on_the_prepared_order_block_TODAY` (`test_latch_lapse_render.py:273`), and its docstring says so.

---

## §7 The interaction the brief armed — what it actually turned out to be

The brief §2 warns that consolidating `_PRICE_DP` could flip breakout/pullback at the equality boundary piece 4 protects. **Checked, and it cannot, for two independent reasons:**

1. **Value identity.** All four definitions are the literal `2`. The consolidation binds one object where four equal objects stood. No rounding site moves; no comparison changes operand or precision. Task 3.3's AST test plus a green suite with zero test edits is the proof.
2. **The sites are disjoint.** Piece 4's refusal compares `mandate_limit_price(zone_cap)` against `latched_pivot`. `mandate_limit_price` quantizes through `Decimal("0.01")` + `ROUND_FLOOR` (`constants.py:373-375`) and never reads `_PRICE_DP`; neither does `compute_prepared_order`. The `_PRICE_DP`-mediated boundary at `orders.py:156` is a bystander that piece 4 does not touch — it only gains a pin.

**The real interaction is elsewhere and it is sharper:** `_mandate_has_room` (`orders.py:566-576`) is a strict-`>` predicate sitting in the same file as the refusal, whose reuse would silently implement the forbidden `<=`. §3 names it and Task 4.3's collapsed-zone test fails it. That is a piece-4-internal hazard against an existing helper, not a 3x4 coupling.

**The genuine cross-piece interaction is 1 x 2**, and it is a question, not a defect: both write through `POST /latches/intent`, and flag B's server-computed session immediately raises "does `cancel` get the same treatment?" — §6 poses it to RD rather than answering it.

---

## §8 ARTIFACT-SCALE JUDGMENT — ONE arc, with the evidence

CHARC's watch: *if the findings cluster as INTERACTIONS BETWEEN the pieces rather than defects WITHIN them, propose the split.* The findings are counted below.

| Finding | Piece | Within or between? |
|---|---|---|
| the alarm is the sole route to a cancel row | 1 | within |
| indeterminate orders are dropped before attribution | 1 | within |
| the unattributable note is itself alarm-conditional | 1 | within |
| the LQDA case is schema-prevented (flag) | 1 | within (and out of scope) |
| the decline control is inside `{% if po.offered %}` | 2 | within |
| **a decline with no order block is unwritable at three mirrors (SCHEMA-STOP)** | 2 | within |
| the form anchor backdates the terminal session | 2 | within |
| four `_PRICE_DP` definitions | 3 | within |
| `compute_prepared_order` has no below-pivot refusal | 4 | within |
| `_mandate_has_room` is the trap that implements the forbidden `<=` | 4 | within |
| the seven-site `__post_init__` false claim | 4 | within |
| the brief's 3x4 quantization coupling | 3 x 4 | **claimed, and ABSENT** (§7) |
| does `cancel` inherit flag B's server-computed session? | 1 x 2 | between — but a QUESTION for RD, not a defect |

**Eleven findings within pieces; one between, and it is a ruling request; one asserted between-finding that does not exist.** On CHARC's own criterion, this does not split.

**THE ADVERSARIAL REVIEW IS EVIDENCE ON THE SAME QUESTION, AND IT AGREES.** Round 1 raised **4 MAJOR + 3 MINOR, zero CRITICAL**, and every one of them is **WITHIN a single piece**: the sorted-attribution ordering break (piece 1), the unrendered `status_note` (piece 1), the unnamed withheld-note VM field (piece 2), the `build.py` scope-vs-deferral conflict (piece 4), the enforcement-site miscount (piece 2), the non-discriminating cancel test (piece 2), the seven-vs-eight miscount (piece 4). **Zero cross-piece findings.** That is the CHARC criterion measured on a second, independent instrument, and it points the same way.

Three further reasons, stated so the judgment is falsifiable rather than asserted:

1. **Splitting would MANUFACTURE the composition class.** Pieces 1, 2, 3 and 4 all touch `swing/latches/orders.py`, `swing/latches/order_intent.py` and/or `swing/web/view_models/latches.py`. Two arcs over that file set means a rebase and a composition gate (`harness-architecture.md` §5.1) spent on a mechanical rename. The cost lands on the exact step that phase 21 identified as the only place cross-arc defects are catchable — the wrong place to add load for no review benefit.
2. **Piece 3 is not review surface.** It is a rename plus four imports with a zero-test-edit acceptance criterion. It grew none of what grew item 3 (1116 lines across five propagation surfaces).
3. **Pieces 1 and 2 are ONE principle by construction** — an affordance gated on something it should not depend on, met once on the alarm and once on the prepared-order form. Splitting them puts the same ruling in two arcs and invites the two halves to diverge.

**Instead of a split, the plan takes a SEQUENCE, and the sequence carries the benefit a split would have bought.** Piece 3 lands FIRST and ALONE (Tasks 3.1-3.5, one commit for the mechanical change), so that no behavioural diff in those three files is ever read through rename churn. Then piece 4 (self-contained), then piece 1, then piece 2.

**The condition under which this judgment reverses, stated in advance:** if RD, at plan review, extends flag B's server-computed session to `cancel` and `attest`, pieces 1 and 2 acquire a shared write-path change across three intent kinds and the handler becomes the arc's centre of gravity rather than its edge. **That would be the moment to re-scope**, and it is why §6 poses the question at plan review rather than after execution.

---

## §9 Test-discipline notes that bind this plan

### §9.1 THE DISCRIMINATOR / GUARD LEDGER — every new test classified, once, in one place

**Codex raised "you labelled a non-discriminating test as acceptance evidence" FOUR TIMES across three rounds** (R1 #6, R2 #8, R3 #3, R3 #4). Four instances of one class is not four mistakes; it is a missing structure. So every test this plan adds is classified HERE, and a task's *Acceptance* line may cite only a **DISCRIMINATOR**.

* **DISCRIMINATOR** — verifiably RED on the pre-change tree and GREEN after. Only these are acceptance evidence.
* **GUARD** — green on both trees by construction. It exists to fail a specific WRONG implementation, or to pin a preserved behaviour. **Never acceptance evidence.** Each one below names the wrong implementation it kills; a guard that kills nothing is deleted.
* **CONTROL** — green on both trees, present so an over-eager fix is caught (the FTRE pattern from `test_latch_cap_display_single_source.py:19-24`).

| Test | Task | Class | RED pre-change on... / kills... |
|---|---|---|---|
| `test_every_latch_price_comparison_reads_ONE_PRICE_DP` | 3.3 | **DISCRIMINATOR** | 4 module-level `_PRICE_DP` assigns exist today |
| `test_the_consolidated_constant_is_the_SAME_OBJECT_at_every_consumer` | 3.3 | **DISCRIMINATOR** | pre-change the modules expose `_PRICE_DP`, NOT `PRICE_DP`, so `orders.PRICE_DP` raises `AttributeError` — it is RED today. It does **not** kill a re-binding (`2` is interned, so `is` succeeds); the AST test owns that job and this one owns *the name is importable from all four* (Codex R4 MAJOR reclassified it) |
| `test_the_regime_boundary_still_uses_display_precision` | 3.3 | GUARD | a consolidation that moves the rounding site |
| `test_a_limit_BELOW_the_pivot_withholds_the_prepared_order` | 4.3 | **DISCRIMINATOR** | the order is offered today |
| `test_the_pullback_regime_refuses_the_same_geometry` | 4.3 | **DISCRIMINATOR** | offered today |
| `test_a_COLLAPSED_but_ORDERABLE_zone_is_STILL_offered` | 4.3 | GUARD | the `<=` form, and reuse of `_mandate_has_room` |
| `test_the_FTRE_control_is_unmoved` | 4.3 | CONTROL | any over-eager refusal |
| `test_close_EXACTLY_AT_the_pivot_is_the_PULLBACK_regime` (+ both neighbours) | 4.3 | GUARD | a boundary flip in EITHER direction. Green today — that is the point; the dispatch requires the CURRENT disposition be preserved |
| `test_attribution_reaches_an_INDETERMINATE_order_the_join_drops` | 1.1 | **DISCRIMINATOR** | the function does not exist today |
| `test_the_join_still_picks_its_reference_order_in_BROKER_INPUT_ORDER` | 1.1 | GUARD | feeding the SORTED tuple into the join |
| `test_a_PENDING_CANCEL_order_STILL_offers_the_cancel_control` | 1.4 | **DISCRIMINATOR** | the ticker is skipped entirely today |
| `test_a_HEALTHY_covering_order_ALSO_offers_the_cancel_control` | 1.4 | **DISCRIMINATOR** | no alarm today, therefore no control |
| `test_the_cancel_control_on_a_NON_ALARMED_order_writes_the_row_end_to_end` | 1.4 | **DISCRIMINATOR** | unreachable today |
| `test_the_alarm_block_no_longer_carries_a_FORM` | 1.4 | **DISCRIMINATOR** | the form is a CHILD of `.latch-alarms` today (`:14`/`:29`). **Must be scoped to that container** — a `<p>`-scoped assertion is green pre-change (Codex R4 MAJOR) |
| `test_an_order_attributable_to_NO_latch_gets_a_NOTE_..._even_with_NO_alarm` | 1.4 | **DISCRIMINATOR** | today a stray beside a LIVE latch produces no alarm, hence no `latch-cancel-unavailable`. **Must assert THAT class** — a bare "a note exists" is green pre-change on the existing disagreement line (Codex R4 MAJOR) |
| `test_an_ORDINARY_resting_order_carries_NO_status_note` | 1.4 | GUARD | a `status_note` emitted unconditionally |
| `test_an_UNAVAILABLE_broker_book_offers_NO_cancel_control` | 1.4 | GUARD | a control built outside the `available` branch. Green today (`view_models/latches.py:2072-2076` already returns no controls) — Codex R3 MINOR |
| `test_the_WITHHELD_branch_LABELS_why_a_decline_cannot_be_recorded` | 2.2 | **DISCRIMINATOR** | the string does not exist today |
| `test_the_OFFERED_branch_carries_NO_decision_unavailable_note` | 2.2 | GUARD | a field set on both paths |
| `test_the_WITHHELD_branch_STILL_offers_no_control` | 2.2 | GUARD | an inert affordance added while labelling the gap. Green today (`latch_prepared_order.html.j2:51-54` has no form) — Codex R3 MINOR. **Scoped to the prepared-order `<section>`**, not the whole page, or the attest form below it makes it vacuous |
| `test_a_DECLINE_with_a_STALE_anchor_is_REFUSED_and_writes_NOTHING` | 2.4a | **DISCRIMINATOR** | 200 + one row today |
| `test_a_NON_DECLINE_KIND_with_a_STALE_anchor_is_STILL_ACCEPTED_today`, parameterised over `("cancel", "attest")` | 2.4b | GUARD (cost marker) | fails the moment flag B is extended to EITHER kind — the trigger to return to RD. Each parameter supplies its kind's required field (Codex R6) |
| the replay-ordering assertion | 2.1 | GUARD | implementing flag B by moving the gate ahead of the replay lookup |

**A CLASSIFICATION IS A CLAIM ABOUT THE PRE-CHANGE TREE AND MUST BE CHECKED AGAINST IT.** Round 4 found THREE rows of this very table wrongly marked DISCRIMINATOR — the error the table exists to prevent, committed inside the table itself. In every case the cause was the same: the test was scoped to the wrong ELEMENT (a `<p>` inside the container that actually changes) or asserted a STRING that a pre-existing surface already emits. **So the executing implementer RUNS each discriminator against the unmodified tree and records the RED before writing the implementation** — the plan's classification is a prediction, and TDD is what tests it.

**Twelve discriminators, ten guards, one control** across 23 rows — and this line has now been wrong TWICE (Codex R4 MINOR, then R5 MINOR after the row it corrected changed class). **FIFTH typed-total error in this document.** The remedy that finally holds is not a better count: **the executing implementer RE-DERIVES it from the table rather than reading it**, e.g. `grep -c 'DISCRIMINATOR'` over this section. A hand-maintained total beside a hand-maintained table is a second source for one fact — the item-6 drift class, in a document whose §0.4 says so. A task with no discriminator is a task with no evidence, and there is none such above.

### §9.2 The rest

* **Frozen clock** on every new date/session-touching test (`frozen_panel_clock` for fragment tests; explicit `monkeypatch` of `_now` for route tests). Tasks 2.1 and 2.4 are entirely clock-dependent.
* **Every discriminator's assertion is computed under BOTH paths.** §3 Task 4.3 and §6 Task 2.4 each show the table; Task 2.4 records a construction that was *rejected for being vacuous* rather than silently avoided.
* **No vacuous negative.** `test_the_alarm_block_no_longer_carries_a_FORM` asserts absence, so it is paired with a positive assertion that a control exists elsewhere on the same render — an absence test that would pass on an empty page is not a test. Same for the two scoping notes in the ledger above.
* **Do not seed through a barrier.** Nothing here adds a write barrier, but Task 1.4's PENDING_CANCEL seeding goes through the existing `_order(...)` helper with `status=`, matching the production `SchwabOrderResponse` shape (the synthetic-fixture-vs-real-emitter class).
* **ASCII only** in every user-facing string (the withheld note, the cancel labels, the status note, the 409 body).

---

## §10 Tripwire self-certification

| Tripwire | Crossed? | Evidence |
|---|---|---|
| New schema / CHECK widening | **NO for what ships.** **YES for piece 2's read half — which is therefore NOT in this plan** (§0.2) | `LATCH_ORDER_WITHHELD_REASONS` has no SQL mirror (grep of `swing/data/migrations/*.sql` for its three values: zero hits); no migration is authored |
| New module or package under `swing/` | NO | all edits land in existing modules |
| New external dependency | NO | none |
| New standing process | NO | no pipeline step, job, ritual or role |
| `swing/trades/` or `swing/data/` carve-out | NO | `swing/data/models.py` and the migrations are READ for evidence only; **no line of `swing/data/` or `swing/trades/` is edited** |

**In-scope file set (brief §3):** `swing/latches/constants.py`, `swing/latches/orders.py`, `swing/latches/order_intent.py`, `swing/latches/service.py`, `swing/web/view_models/latches.py`, `swing/web/routes/latches.py`, `swing/web/templates/partials/latch_orders.html.j2`, `swing/web/templates/partials/latch_prepared_order.html.j2`, and their tests. **`swing/web/static/app.css` is NOT in it** — see Task 1.5.

**Out of scope, FLAGGED not fixed:** `swing/recommendations/build.py` (the discharged deferral note + two false claims), `swing/web/view_models/dashboard.py:756` (one false claim), `tests/recommendations/test_sizing_basis_is_the_limit.py:614`, `tests/web/test_view_models/test_sizing_basis_is_the_limit.py:236`, the LQDA/hyp-rec cancel gap (Phase-22 — blocked by the trigger's `bucket = 'aplus'` clause, §5), **`swing/web/static/app.css` (the two unstyled new classes, Task 1.5)**, and `swing/data/ohlcv_archive.py:964` (named by the brief as already flagged).

---

## §11 Task summary, in shipping order

| # | Task | Commit type |
|---|---|---|
| 3.1-3.2 | `PRICE_DP` single source + four call sites | `refactor(latches):` |
| 3.3 | the AST + identity + boundary-preservation tests | `test(latches):` |
| 3.4-3.5 | the widening grep (report-only) + the cap-belt verification (no edit) | — |
| 4.1 | `limit_below_pivot` in `LATCH_ORDER_WITHHELD_REASONS` | `feat(latches):` |
| 4.2 | the refusal in `compute_prepared_order`, strict `<` | `feat(latches):` |
| 4.3 | the four refusal tests + the exact `close == pivot` pin | `test(latches):` |
| 4.4 | the two in-scope `__post_init__` claim corrections (+ `build.py` ONLY under a ruled scope exception — §3) | `docs(latches):` |
| 1.1 | `attribute_orders_to_latches` + the MAP-sharing join refactor + the input-order pin | `feat(latches):` |
| 1.2 | `LatchCancelControlVM` + the two VM fields | `feat(web):` |
| 1.3 | the template move, the `status_note` markup, the `_invalidate` docstring correction | `feat(web):` |
| 1.4 | the SEVEN cancel-decoupling tests — count derived from §9.1's Task-1.4 rows, not typed (Codex R9 MINOR; the SEVENTH count artefact) | `test(web):` |
| 1.4b | the two falsified alarm-ownership comments, corrected with the move | `docs(latches):` |
| ~~1.5~~ | **WITHDRAWN — `app.css` is out of scope (Codex R7 MAJOR).** The two new classes ship unstyled; flagged as a follow-up | — |
| 2.1 | flag B: the server-computed decline session + the strict anchor gate | `fix(web):` |
| 2.2 | `PreparedOrderVM.decision_unavailable_note` + its render + its three tests | `feat(web):` |
| 2.3 | the T7.8 cost-marker docstring, re-grounded | `docs(web):` |
| 2.4 | (a) the stale-anchor decline discriminator + (b) the cancel COST MARKER, labelled apart | `test(web):` |

**ONE DECISION IS OWED BEFORE EXECUTION** (§3 Task 4.4): whether the executing implementer may make a comment-only edit to `swing/recommendations/build.py` to discharge the deferral it is discharging. Default if unruled: flag, do not touch.

**Gates, per the brief §5:** full fast suite BEFORE the Codex loop -> Codex `strong` to `NO_NEW_CRITICAL_MAJOR` with all four per-round assertions -> `codex-auto-review` in the cold-audit form -> full fast suite AFTER convergence -> trailer audit filtered on the trailer KEY. Convergence attaches to the tree that ships.
