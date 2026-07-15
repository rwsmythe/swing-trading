# Plan — 20-A: fix the tier-1 corrector, then correct the data (D25)

**Arc:** Phase-20 20-A (the opener). **Author:** writing-plans implementer (opus-xhigh).
**Base:** main `6d3981d0` (worktree `.worktrees/20a-corrector`, branch `20a-corrector`).
**Brief:** [`docs/reconciliation-corrector-fix-20a-commissioning-brief.md`](../reconciliation-corrector-fix-20a-commissioning-brief.md) (BINDING — §2 A1-A4/B1-B3, §3 A5 + SCHEMA-STOP, §4 gates).
**Evidence:** [`docs/broker-ledger-forensic-reconciliation-2026-07-10.md`](../broker-ledger-forensic-reconciliation-2026-07-10.md) (the founding artifact; the correction arithmetic is the B3 fixture).
**Deadline:** complete before Monday's open; corrected values must exist before RD's August monthly read.
**Schema:** v31, ZERO migrations (SCHEMA-STOP honored — see §11).

---

## 0. How to read this plan

This is a **guards + void-mechanism design**, not an algorithm design. It is written so the **executing implementer** follows it as a locked TDD sequence. Two things must be read FIRST, because they change the brief's stated scope and are the RD/CHARC plan-stage decision surface:

- **§2 — the scope reality** (the root-cause matcher lives in a file the brief's A5 file-list did not name). This is the #1 decision.
- **§10 — the three RD plan-stage decisions** (the void mechanism + reader set, the A2 band, the ORDER encoding).

Every fixture in this plan is a **live-DB-verified real row** (read-only probe, 2026-07-11), never a synthetic value built to satisfy a guard (the binding fixture discipline). The live values are in §9.

---

## 1. The pinned mechanism (live-verified)

The fill->execution matcher in `run_schwab_reconciliation` (`swing/trades/schwab_reconciliation.py`, step 6, lines ~1745-1902) matches a journal fill to a Schwab execution by **`(ticker, quantity-within-$0.01)` ONLY** — the inner loop `break`s at the first unclaimed same-ticker/same-qty order (`schwab_reconciliation.py:1763-1780`):

- **NO side discrimination** — a BUY entry fill matches a SELL exit execution.
- **NO date-proximity** — a 07-07 fill matches a 07-09 execution.
- The matched execution price is emitted as an `entry_price_mismatch` / `close_price_mismatch` "Shape C" discrepancy (`:1866-1902`); the classifier (`_classify_entry_price_mismatch` / `_classify_close_price_mismatch`, Shape-C branch) faithfully returns **tier-1**; `_apply_tier1_correction_inner` faithfully overwrites `fills.price` with the wrong leg's price.

Every normal single-entry/single-exit (or trim/stop) round trip produces exactly two same-quantity executions, so the matcher mis-picks the wrong leg on the run AFTER the second leg executes, and later runs compare against the same mis-match -> self-sealing. Correction **#34** (fill 37, `35.65 -> 32.06`) re-fired over its own correct fix **#33** (`35.75 -> 35.65`) — proving the self-seal AND that the corrector does not maintain the supersede chain (both #33 and #34 carry `superseded_by = NULL` on fill 37; live-verified).

**The corruption is baked in at MATCH TIME.** The classifier and the auto-correct service are behaving correctly given a poisoned input. This is the central architectural fact that drives §2.

---

## 2. SCOPE REALITY — the root-cause file the brief's A5 list did not name (RD/CHARC decision #0)

The brief §3 A5 names the scope as `reconciliation_classifier.py` + `reconciliation_auto_correct.py` + the B2 touchpoints. But the **matcher that mis-picks the leg is `swing/trades/schwab_reconciliation.py`** (same `swing/trades/` carve-out lane, but not on the A5 file list). Three of the four Half-A guards cannot be honored without touching it:

| Guard | Can it live purely in classifier + auto_correct? | Why / why not |
|---|---|---|
| **A1** (>=2 candidate executions = ambiguity) | **NO** | Candidate *multiplicity* is only knowable at match time. The classifier receives a single already-resolved `{"price": X, ...}` payload — the matcher discarded the other candidate when it `break`ed. The matcher must enumerate + signal. |
| **A2-side** | **NO** (needs evidence enrichment) | The execution's side (`so.instruction`) is NOT in the emitted payload (Shape C carries `execution_legs` price/qty/time but no side). The matcher must add `execution_side` to the payload. |
| **A2-date** | Partly | The execution date IS in `execution_legs[].time` (in the payload). Decidable in the classifier via a calendar-day proxy, OR at the matcher via the NYSE-session helper. See §10.2. |
| **A2-magnitude** | **YES** (classifier, pure) | Computable from `source_payload["price"]` + `journal_row["price"]`. |
| **A3** (re-correction alarm) | **YES** (`reconciliation_auto_correct.py`, has DB) | Query prior corrections for the fill. |
| **A4** (fills<->trades invariant) | **NO** (needs a new emit check) | A fills-vs-trades consistency check is a detection/emit concern; it lives in the recon run (`schwab_reconciliation.py`). And it must be **no-schema** (`discrepancy_type` is CHECK-constrained; see §11). |

**Disposition (for RD/CHARC to ratify at the plan gate):** add `swing/trades/schwab_reconciliation.py` to the 20-A scope — it is in the same `swing/trades/` carve-out lane the §3 verdict already opened, it introduces **no schema, no new dependency, no cross-package reach**, and it is the ONLY place the root cause can be fixed. This is the plan's enumerated scope addition per A5's "enumerate every other `swing/trades` file the mechanism requires, with justification." The classifier stays a **pure function** (its architecture lock is preserved — all classifier changes are pure logic on the enriched payload).

**Both tier-1 firing sites are covered by the chokepoint placement (verified):**
1. The nightly pivot: `schwab_reconciliation.py:_pivot_classify_and_dispatch_for_run` -> `classify_discrepancy` -> `_apply_tier1_correction_inner`.
2. The backfill: `reconciliation_backfill.py` Pass-1 -> `classify_discrepancy` -> `apply_tier1_correction` (public -> same inner).

Both route through **`classify_discrepancy`** (so A1/A2 in the classifier cover both) and **`_apply_tier1_correction_inner`** (so A3 in the inner covers both). The matcher enrichment lands in the persisted `actual_value_json`, which the backfill re-reads. No per-site duplication.

---

## 3. Binding conditions — stated as honored

| Condition | How this plan honors it | Anchor |
|---|---|---|
| **ORDER (RD-binding):** Half A merges before/atomic-with Half B | Single branch, ordered commits: **A1-A4 commits FIRST, then B1-B3**. B is operator/RD-run on the live DB only AFTER the A-half code is merged. Encoded in §8. | §8 |
| Classifier STAYS a pure function (no I/O) | All classifier changes are pure logic on the (enriched) payload + `journal_row`. No DB, no calendar imports beyond stdlib + models. A2-date compares a matcher-precomputed int (`execution_sessions_from_fill`) — the session math lives at the matcher, not the classifier (§5.3, §10.2). | §5.3 |
| `reconciliation_corrections` stays APPEND-ONLY | B1 uses the existing tier-3 override path (`apply_tier3_override` -> INSERT `operator_overridden` + `update_superseded_by`); A3 never mutates a correction row in place. | `reconciliation_corrections.py:71-116,186-212` (INSERT + UPDATE-only supersede; no `INSERT OR REPLACE`) |
| Sandbox gating unchanged | A3 lives AFTER the existing `if environment == "sandbox"` short-circuit in `_apply_tier1_correction_inner` (`reconciliation_auto_correct.py:695-709`); under sandbox `correction_id is None` and no domain writes, unchanged. A4's emit is a discrepancy row (recon OUTPUT), not a journal mutation, so it is unaffected (mirrors every other `_emit`). | `reconciliation_auto_correct.py:695` |
| Tier-2 demotions flow through the EXISTING ambiguity machinery | A1/A2 demotions emit `tier=2` with an ambiguity_kind whose menu is already in `reconciliation_ambiguity_choices.py:get_choice_menu` (`multi_match_within_window` / `unsupported`) — NO parallel prompt path. | `reconciliation_ambiguity_choices.py:80-300` |
| SCHEMA-STOP (no `voided` in the state enum) | B2 uses a **no-schema** void mechanism (§7); A4 reuses an existing `discrepancy_type` (§6.4). Neither adds a migration. | `0014_...sql:139`, `state.py:136` |
| Fixture discipline (REAL geometries, never synthetic) | All fixtures are the live rows in §9; pre/post arithmetic computed per discriminator in §9. | §9 |

---

## 4. Architecture summary (where each guard lives)

```
schwab_reconciliation.py (MATCHER + EMITTER)          reconciliation_classifier.py (PURE)     reconciliation_auto_correct.py (SERVICE, DB)
------------------------------------------            -----------------------------------     ------------------------------------------
step 6 fill-matching:                                  Shape D branch (entry + close):          _apply_tier1_correction_inner:
  * enumerate ALL (ticker,qty) candidates                A1: candidate_count>=2 -> tier2          A3: re-correction alarm (query prior
    (side-agnostic; the A1 count)                        A2-side: exec_side vs action -> tier2        auto_applied corrections on the fill;
  * SIDE-AWARE suppress: no emit only if a               A2-date: exec_sessions_from_fill>1 ->        BLOCK a DIFFERENT re-correct -> material
    SAME-SIDE candidate matches fill.price                  tier2 (matcher-precomputed int)           tier-2, never a 2nd auto-apply)
  * A1: >=2 & not-suppressed -> emit LIST-shape         A2-magnitude: |d|/journal > band -> tier2
    (classifier multi_match_within_window tier2)         else -> tier1 (legit sub-cent fix)
  * else emit "Shape D" (+ candidate_count,             Shape C branch retained + magnitude belt
    + execution_side + execution_sessions_from_fill)
new step 6.5: A4 fills<->trades consistency check
    -> emits an existing material discrepancy_type
```

The classifier remains the **single tier-decision chokepoint** shared by both firing sites; the matcher only *enriches evidence* and adds the A4 watchdog; the service adds the DB-aware A3 belt.

---

## 5. Half A — the corrector (MERGES FIRST)

**On "independently sufficient" (restated precisely after Codex R2+R3 — NOT every guard catches every corruption; the union is redundant; the matcher never over-demotes a correct fill):** the three real corruptions (PTEN/DFTX/AMN) all resolve to `good_matches == []` (no fully-consistent candidate) with >=2 same-qty candidates, so **A1 alone catches all three**; and **A2-magnitude alone also catches all three** (5.35/9.66/10.07% all > 2%). A NORMAL correct round-trip fill has exactly ONE good match -> it is suppressed (no false demotion) — A1's ambiguity condition is `good_matches != 1`, NOT a raw `count >= 2`. The other guards are additional independent layers: **A2-side** demotes a single wrong-side candidate, **A2-date** demotes a >1-session single candidate (and is the criterion inside `good_matches` that excludes AMN's stop leg), **A3** is the re-fire/self-seal belt (catches #34 regardless of candidate count), **A4** is the fills<->trades watchdog. No guard relies on a matcher short-circuit it cannot itself re-evaluate (suppression requires price+side+session all pass — a strict subset of a classifier tier-1). The TDD order is A2-magnitude (pure, smallest) -> A1 + A2-side + A2-date (matcher `good_matches` + classifier) -> A3 -> A4. Every task: red -> see-fail -> minimal green -> commit.

### 5.1 Task A-1 — classifier magnitude band (pure; the A2-magnitude guard)

**File:** `reconciliation_classifier.py` (`_classify_entry_price_mismatch` + `_classify_close_price_mismatch` Shape-C tier-1 branch). Add a module constant `_MAX_TIER1_OVERWRITE_RATIO = 0.02` (RD-ruled — §10.2) and a helper `_overwrite_ratio(source_price, journal_price)`.

**Behavior:** on the Shape-C (and Shape-D) tier-1 path, before returning `tier=1`, compute `ratio = abs(source_price - journal_price) / abs(journal_price)`. If `journal_price` is falsy/None -> keep tier-1 (nothing to gate against; the write-boundary already guards finiteness). If `ratio > _MAX_TIER1_OVERWRITE_RATIO` -> return **tier-2** `unsupported` (or `multi_match_within_window` — §10) with a reason `"overwrite magnitude {ratio:.2%} exceeds tier-1 band {band:.0%}; requires operator disposition"`. The guard needs only the price + `journal_row["price"]` — pure.

**Acceptance:** PTEN Shape-C `{price: 12.305}` + journal 13.00 -> ratio 5.35% > 2% -> tier-2. AMN `{price: 32.06}` + journal 35.65 -> 10.07% -> tier-2. The legitimate CVGI-class fix `{price: 5.30}` + journal 5.23 -> 1.34% <= 2% -> tier-1 (unchanged). Discriminating arithmetic in §9.

### 5.2 Task A-2 — matcher candidate enumeration + Shape-D enrichment (A1 + A2-side evidence)

**File:** `schwab_reconciliation.py` step 6.

1. Replace the `break`-at-first-match with an **enumeration**: build `qty_candidates = [so for so in schwab_filled if so.instrument_symbol == ticker and abs(_resolve_match_quantity(so) - fill.qty) <= tol and so_idx not already claimed]` — **side-agnostic**, over the full fetched (recon-period) window. This is the A1 count basis (the brief's "same ticker + qty within the compare window"; the window is the recon period, NOT the 1-session window — else AMN's 2-sessions-apart legs would each look single-candidate). (Retain the greedy-claim `matched_schwab_idx` set so a candidate is not double-counted across fills.)

**Control flow (Codex R1+R2+R3 fix — "unique GOOD match" suppression; NEVER price-blind, NEVER over-broad):** define, for the fill,
`good_matches = [c for c in qty_candidates if abs(_compute_execution_price(c) - fill.price) <= tol AND _side_matches(c.instruction, fill.action) AND session_distance(c, fill) <= 1]`
— candidates FULLY consistent with the fill being correctly recorded (price AND side AND within-1-session, all three). Then:

2. **`len(good_matches) == 1` — the ONLY suppression case.** Exactly one fully-consistent candidate -> the fill is unambiguously correct -> claim `c`, **no emit** (no false pending). A NORMAL correct round-trip entry fill (13.00) has exactly ONE good match — the entry BUY leg (13.00, side+session+price all pass); the exit SELL counter-leg is NOT a good match (side differs) -> `len(good_matches)==1` -> **no false demotion** (fixes R3). Suppression requires ALL THREE A2 criteria to pass, so it is a STRICT SUBSET of a classifier tier-1 and can never bypass a demotion (fixes R2 circularity).
3. **`len(good_matches) != 1` AND `len(qty_candidates) >= 2` — A1 ambiguity.** The fill is not uniquely resolved AND there are >=2 same-qty candidates -> **emit** a **LIST-shaped** `actual_value_json` (per-candidate `{price, execution_legs, schwab_order_id, schwab_order_price, execution_side, execution_sessions_from_fill}` dicts) -> classifier's existing `isinstance(list) and len>1` branch -> **tier-2 `multi_match_within_window`** (add the symmetric list branch to `_classify_close_price_mismatch` in Task A-3). **This catches all three corruptions:** each corrupt fill has `good_matches == []` — PTEN/DFTX (the only price-matching leg is the opposite SIDE), AMN (the only price-matching leg is the SELL stop at 32.06, which fails the `<=1 session` test: 07-09 is 2 sessions from the 07-07 fill) — and `len(qty_candidates)==2` -> A1 tier-2. The session criterion inside `good_matches` is exactly what excludes AMN's wrong-leg without price-blindness (fixes R2's AMN hole).
4. **`len(good_matches) != 1` AND `len(qty_candidates) == 1` — single-candidate plausibility.** Emit **Shape D** = Shape C keys **plus** `execution_side` (`so.instruction`), `candidate_count` (`1`), `execution_sessions_from_fill` (int NYSE-session distance via `swing/evaluation/dates.py`) -> classifier applies A2-side / A2-date / A2-magnitude.
5. **`len(qty_candidates) == 0`:** existing `unmatched_*_fill` path (unchanged).

**Acceptance (all three geometries):**
- CORRECT round-trip entry fill (13.00, candidates entry BUY 13.00 + exit SELL 12.305): `good_matches = {entry BUY}` (exit fails side) -> `len==1` -> **no emit, no false demotion** (fixes R3).
- PTEN corrupt (entry 12.305): the entry BUY leg (13.00) fails price; the exit SELL leg (12.305) fails side -> `good_matches = []`, `qty_candidates=2` -> A1 tier-2.
- AMN corrupt trim (32.06): the trim SELL leg (35.65) fails price; the stop SELL leg (32.06) fails session (2 sessions) -> `good_matches = []`, `qty_candidates=2` -> A1 tier-2 (fixes R2).
Discriminating detail in §9.

### 5.3 Task A-3 — classifier Shape-D branch (A1 signal honoring + A2-side + A2-date)

**File:** `reconciliation_classifier.py`. Define `_SHAPE_D_EXPECTED_KEYS = _SHAPE_C_EXPECTED_KEYS | {"execution_side", "candidate_count", "execution_sessions_from_fill"}` (the EXACT enriched contract — exact-set-equality like Shape C). Add a Shape-D branch in `_classify_entry_price_mismatch` AND `_classify_close_price_mismatch` (both must gain it — AMN's trim fill routes to close).

**FAIL-CLOSED matcher-output contract (Codex R4+R6 — a matcher enrichment bug must never leak a corruption back to tier-1):** the Shape-D tier-1 path requires ALL enrichment fields present AND well-typed — `execution_side` a non-empty string, `candidate_count` a non-negative int, `execution_sessions_from_fill` an int OR the explicit `null` sentinel, `execution_legs` a non-empty list. **ANY missing / malformed / unexpected-extra key -> the classifier fail-closes to tier-2** (never tier-1) with reason `"Shape-D contract violation - demoting to manual"`. So a matcher that forgets to enrich (emits bare Shape C where Shape D was due), or emits a malformed field, degrades to tier-2 (safe), never silently re-enters the old unguarded tier-1 path. The Shape-C legacy branch (§6.1) keeps ONLY the magnitude belt and is reachable solely for genuinely-legacy persisted rows. On a valid Shape-D payload:

- **A1:** if `candidate_count >= 2` -> tier-2 `multi_match_within_window`.
- **A2-side:** expected side from `journal_row["action"]` — `entry -> {"BUY","BUY_TO_OPEN",...}`; `exit`/`trim`/`stop` -> `{"SELL","SELL_TO_CLOSE",...}` (map via a small helper; the live `fills.action` vocabulary includes `entry`/`exit`/`trim`, confirmed §9). If `execution_side` is not in the expected set -> tier-2 `multi_match_within_window` with reason `"execution side {execution_side} does not match fill action {action}"`.
- **A2-date (session-accurate — Codex R1 MAJOR fix):** the matcher supplies `execution_sessions_from_fill` (int NYSE-session distance, computed in `schwab_reconciliation.py` via `swing/evaluation/dates.py`). The classifier check is a pure integer compare: `if execution_sessions_from_fill > _MAX_TIER1_SESSION_DISTANCE` (propose **1**; RD-ruled §10.2) -> tier-2 `multi_match_within_window`. A **calendar-day proxy is inadequate** and was internally inconsistent: 07-07->07-09 is only 2 calendar days (would NOT exceed a 3-day proxy) yet is **2 NYSE sessions** (Mon->Wed); and a legitimate Fri->Mon 1-session fix is 3 calendar days. Only a session-accurate distance separates the AMN 2-session corruption from a legitimate <=1-session correction. The classifier stays pure — it compares the pre-computed int, never touching a calendar.
- **Session-distance robustness (Codex R4 — the classifier cannot re-derive it without breaking purity):** because `session_distance` is load-bearing for BOTH A2-date AND the matcher's `good_matches` suppression (a buggy small value could make AMN's stop leg a "good match" -> suppress AMN), the plan mandates: (a) a **discriminating unit test** on the matcher's session_distance using the AMN geometry (fill 2026-07-07 vs execution 2026-07-09 -> MUST equal 2 sessions; a same-day -> 0; a Fri->Mon -> 1) — computed under both a correct and a naive `(exec_date - fill_date).days` path to prove the test distinguishes; (b) **fail-safe toward EMIT — pinned matcher contract (Codex R5 MINOR):** on ANY session-resolution failure at the matcher (helper raises / returns `None` / an execution `time` is missing or unparseable), the matcher (i) treats that candidate as NOT session-consistent in `good_matches` (so it never contributes to a suppression), and (ii) emits Shape-D with the explicit sentinel `execution_sessions_from_fill = null`. The classifier treats a `null`/missing `execution_sessions_from_fill` as `> _MAX_TIER1_SESSION_DISTANCE` (i.e. force tier-2). A dedicated unit test exercises the fallback path (unparseable execution `time` -> Shape-D with `null` -> classifier tier-2) so a silent-suppression regression is caught. A session-calc failure thus always SURFACES the fill, never silently auto-applies. (c) Redundancy note: **A2-magnitude is independent of session-distance** — AMN's 10.07% magnitude demotes it even if every session computation were wrong, PROVIDED the discrepancy is emitted; the fail-safe-toward-emit in (b) guarantees emission so A2-magnitude always gets its chance.
- **A2-magnitude:** the Task A-1 magnitude band (shared helper).
- Only if ALL pass -> tier-1 (the legitimate single-candidate sub-cent fix).

Also add the symmetric **list branch** to `_classify_close_price_mismatch` (A1, close side).

**Acceptance:** the AMN 07-07 trim fill Shape-D `{price:32.06, execution_side:"SELL", candidate_count:2, execution_sessions_from_fill:2}` + journal action `trim`, fill_datetime `2026-07-07` -> A1 (count 2) tier-2 AND A2-date (2 sessions > 1) tier-2 AND A2-magnitude (10.07%) tier-2 — each independently. A PTEN Shape-D with `execution_side:"SELL"` + action `entry` -> A2-side tier-2. Each guard proven independently in §9.

### 5.4 Task A-4 — re-correction alarm (A3; the #34 killer)

**Placement — keyed on the FILL chain, and it must run on BOTH the fresh-discrepancy AND the terminal-discrepancy path (Codex R8).** The real #34 vector is a **fresh** discrepancy each recon run (live-verified: #33 = discrepancy 83, #34 = discrepancy 85 — distinct rows on the same fill 37), so a tier-1 apply targets an `unresolved` discrepancy and the existing terminal-idempotency return (`:723`) does NOT short-circuit -> A3 runs. But a same-discrepancy reapply against a B1-`operator_overridden` discrepancy WOULD hit the idempotency return (`operator_overridden` is terminal) BEFORE A3 — a silent no-op (no clobber, but no contradiction surfaced). So A3 is a **fill-chain contradiction check placed in TWO spots**: (1) the primary check AFTER the sandbox short-circuit and BEFORE the journal UPDATE (Step 5, `:764`) — catches the fresh-discrepancy #34/clobber vector; (2) a guard folded INTO the terminal-idempotency path (`:723`) — before returning idempotently, if the fill's effective chain-head value differs from what this tier-1 would apply, raise the contradiction instead of a silent no-op. Both keyed on the FILL's effective chain (persists across discrepancies), not the discrepancy resolution. When `affected_table == _AFFECTED_TABLE_FILLS`:

- **Base the alarm on the fill's EFFECTIVE correction chain, not just `auto_applied` rows (Codex R6 — the too-narrow fix).** Query `list_corrections_by_affected_row(conn, "fills", affected_row_id)` (`reconciliation_corrections.py:166`); resolve the **chain head** (the row with `superseded_by_correction_id IS NULL`, i.e. the currently-effective correction — auto OR operator). If a chain head exists (regardless of `correction_action`) AND its effective `applied_value_json` price differs from the new tier-1 `target_value` (beyond display precision) -> **BLOCK**: raise a new `ReCorrectionContradictionError`. This blocks BOTH the auto-re-fire (#34) AND — critically — a tier-1 that would **clobber an OPERATOR OVERRIDE** (e.g. after B1 sets fill 17 to `operator_overridden` 13.00, the old matcher re-proposing 12.305 is blocked — the corrector can never again remove the human). Blocking "any tier-1 that changes the effective canonical value" is the correct generalization: a canonical value that already exists and differs is a contradiction by definition, whatever tier set it.
- The pivot (`schwab_reconciliation.py:_pivot_classify_and_dispatch_for_run` tier-1 branch) and the backfill catch it and route to a **material tier-2** stamp (`multi_match_within_window`, reason `"canonical value changed - contradiction: fill {id} effective value {prior} ({prior_action}), new tier-1 proposal {target} differs"`). Add the catch beside the existing `except ValidatorRejectedError` fallback (`schwab_reconciliation.py:868-897`) — a FRESH savepoint stamp, mirroring that block.

**Design choice for RD/CHARC:** `ReCorrectionContradictionError` as a dedicated exception (clearest audit) vs. reusing `ValidatorRejectedError` (zero pivot change, generic reason). Recommend the dedicated exception + one pivot/backfill catch each (both firing sites). Both are no-schema.

**Acceptance:** (a) #34 replay — a FRESH `unresolved` discrepancy on fill 37 (live: disc 85, mirroring disc 83's #33), chain-head effective value 35.65, a new tier-1 proposes 32.06 -> A3 fires (fresh path, post-idempotency) -> BLOCKED -> material tier-2, not a 2nd auto-apply (makes #34 structurally impossible); (b) **operator-override protection** — a FRESH discrepancy on fill 17 (post-B1 chain head `operator_overridden` 13.00) proposing 12.305 -> A3 fires -> BLOCKED (the corrector cannot clobber the human fix); (c) **terminal-path belt** — a tier-1 targeting the SAME already-`operator_overridden` discrepancy with a differing value -> the idempotency-path guard raises the contradiction (not a silent no-op). All computed under pre-fix (would auto-apply / silent no-op) vs post-fix (blocked) in §9.

### 5.5 Task A-5 — fills<->trades consistency invariant (A4; the watchdog)

**File:** `schwab_reconciliation.py`, a new check pass (e.g. step 5.5, after the position-qty loop). It iterates **ALL trades that have entry fills — open AND closed/reviewed** (`list_open_trades` + `list_closed_trades`), NOT just open trades (Codex R4 — the divergence it protects against sat six weeks on CLOSED trades; an open-only watchdog would never have caught PTEN/DFTX/AMN). For each such trade with a non-null `entry_price`, compute the entry-fill VWAP from its entry-action fills; if `abs(vwap - trades.entry_price) > display_tol` ($0.005, display precision) -> `_emit` a **material** discrepancy.

**Routing — a genuine CHARC schema-route decision (Codex R4+R5):** the semantically-CLEAN A4 wants a **dedicated `discrepancy_type`** (isolated from every `entry_price_mismatch` consumer). Per the SCHEMA-STOP, that is a schema route (migration 0032 + CHECK widen + the #11 one-commit `DISCREPANCY_TYPES`/`MATERIAL_BY_TYPE`/`models._DISCREPANCY_TYPES` discipline) -> **flagged to CHARC (§10.4), NOT designed-past here.** The no-schema fallback (A4-i, if CHARC declines schema) reuses `entry_price_mismatch` with an `internal_consistency:"fills_vs_trades"` discriminator, and — **to make it a HARD non-auto-correcting internal diagnostic that structurally cannot flow through the broker-mismatch classifier path (Codex R6+R7)** — the classify-SKIP guard is extended to skip it **at BOTH firing sites** (Codex R7 — not just the pivot). The pivot already skips `untracked_broker_position` + `equity_delta` from classify/dispatch (`schwab_reconciliation.py:822-826`); A4-i's row is skipped the same way **by its discriminator** (`json_extract(actual_value_json,'$.internal_consistency') == 'fills_vs_trades'`) at (i) the pivot AND (ii) the **backfill** (`reconciliation_backfill.py`, wherever it selects unresolved discrepancies to re-classify) — so NO firing site can route it into `classify_discrepancy` / the tier-1 path. A shared skip-predicate helper (`_is_internal_consistency_diagnostic(disc)`) is consumed at both sites so the two paths cannot drift. Auto-correct is structurally impossible, not merely tier-2-gated. The row stays `unresolved` + **material** (surfaces in the material-discrepancy banner — CORRECT; A4 findings SHOULD demand attention) and is cleared via the manual resolver. **Residual isolation note (Codex R5):** a legacy consumer that merely COUNTS/DISPLAYS `entry_price_mismatch` rows will include A4's row in a material-discrepancy count — which is semantically CORRECT (it IS a material discrepancy). The only unsafe behavior (auto-correct) is now structurally prevented by the pivot-skip. The executing implementer still runs a **consumer audit** (grep every `entry_price_mismatch` consumer) to confirm none does something type-specific that the discriminator would break; if one does, the dedicated-type schema route becomes REQUIRED -> CHARC. See §6.4/§10.4.

**Acceptance:** A4 FIRES on the live PTEN/DFTX rows pre-B1 (fill 12.305 vs trade 13.00 = $0.695 > $0.005; fill 22.16 vs 24.53) EVEN THOUGH they are `reviewed`/closed (all-trades coverage), and goes QUIET post-B1 (fill corrected to 13.00 / 24.53 = 0 divergence). The discriminating test seeds the real reviewed-trade geometry and asserts the discriminator-keyed tier-2 emit pre-B1 / no emit post-B1. §9.

---

## 6. Half A design notes

### 6.1 Shape D is MANDATORY for every LIVE matcher emit; Shape C is legacy-read-only (Codex R7)
The matcher **always** emits Shape D (single-candidate) or the LIST shape (multi-candidate) for every LIVE entry/close price mismatch — it NEVER freshly emits Shape C. Shape C is reachable ONLY as a read over historically-persisted rows. Two belts enforce this so a corruption can never fall back to the weaker path:
- **Matcher-side:** a discriminating test asserts every LIVE price-mismatch emit is Shape-D-shaped (single) or list-shaped (multi) — a bare-Shape-C live emit is a test failure.
- **Classifier-side:** the Shape-C tier-1 branch retains ONLY the A2-magnitude belt (Task A-1) as defense-in-depth for a genuinely-legacy straggler, AND the fail-closed contract (§5.3) means a LIVE payload that is missing Shape-D enrichment does NOT silently take the Shape-C tier-1 path — it fails closed to tier-2. So even if the matcher regressed, the live path degrades to manual, never to an unguarded auto-apply. Only A1/A2-side/A2-date require the Shape-D evidence; A2-magnitude covers both shapes.

### 6.2 Tier-2 kind + menu
All A1/A2 demotions use `multi_match_within_window` (menu: `mark_unmatched` + `custom` + CLI-constructed `pick_schwab_record_N`) OR `unsupported` (menu: `operator_truth` + `acknowledge`) — both already in `get_choice_menu`. No new ambiguity_kind, no parallel prompt path. Recommend `multi_match_within_window` for the >=2-candidate case (semantically exact) and `unsupported` for the single-candidate implausible case.

### 6.3 A3 vs the validator chain
A3 is deliberately NOT a validator (`reconciliation_validators.py` is out of scope and validators are pure schema-mirror predicates). Placing A3 in `_apply_tier1_correction_inner` keeps it in the A5-named `reconciliation_auto_correct.py` and gives it the DB access the prior-corrections query needs.

### 6.4 A4 no-schema options (RD/CHARC picks)
- **A4-i (recommended, no-schema, semantically-distinct — Codex R4):** emit `entry_price_mismatch` with an `internal_consistency:"fills_vs_trades"` discriminator in `actual_value_json` (NOT `{"matched": null}`) + a dedicated classifier branch that returns a distinct tier-2 (accurate reason + `unsupported`/`operator_truth` menu), never auto-corrected. Reuses the material type without collapsing the fills-vs-trades invariant into the broker-no-match path (which would mislead the audit trail, the operator menu, and type-keyed alerting).
- **A4-ii (no-schema, lower fidelity):** append a `cash_warnings`-style summary entry + a `log.warning`, no formal discrepancy row. Zero risk; weaker than "material discrepancy."
- **A4-iii (SCHEMA ROUTE — STOP):** a new `fills_trades_price_divergence` discrepancy_type = migration 0032 + CHECK widen + `DISCREPANCY_TYPES`/`MATERIAL_BY_TYPE`/`models._DISCREPANCY_TYPES` (the #11 one-commit discipline). The SEMANTICALLY-CLEANEST option, but crosses the no-schema constraint -> route to CHARC; NOT taken unless CHARC approves schema. (A4-i is the no-schema approximation of A4-iii's clean semantics.)

---

## 7. Half B — the data (AFTER Half A merges)

Half B is **operator/RD-run on the live DB** via existing supported paths; the executing implementer supplies any thin driver + the B3 verification tests, and witnesses.

### 7.1 Task B-1 — the 3 fill corrections (supported audited override path)

Use the existing tier-3 override CLI `swing journal discrepancy override-correction` (wraps `apply_tier3_override` -> INSERT `operator_overridden` + `operator_truth_value_json` + `update_superseded_by` + journal UPDATE + `_recompute_aggregates`). Target the **current effective chain head** per fill (live-verified correction ids):

| Fill | Trade | Chain-head correction | operator_truth | Broker-true |
|---|---|---|---|---|
| 17 | 10 (PTEN) | **#28** (`13.00->12.305` auto) | `{"price": 13.00}` | entry 15 @ 13.00 |
| 28 | 16 (DFTX) | **#30** (`24.53->22.16` auto) | `{"price": 24.53}` | entry 7 @ 24.53 |
| 37 | 18 (AMN) | **#34** (`35.65->32.06` auto) | `{"price": 35.65}` | trim 3 @ 35.65 |

Reason string cites the forensic doc + broker statement. **Append-only** (INSERT `operator_overridden`, supersede — never mutate). **AMN caveat:** #33 and #34 both carry `superseded_by = NULL` on fill 37 (the corrector failed to chain — live-verified); `apply_tier3_override(correction_id=34)` is valid (#34's `superseded_by IS NULL`) and fixes the effective value; the dangling #33 is a pre-existing audit artifact left untouched (flag for RD/operator awareness — see §11 open questions).

### 7.2 Task B-2 — SATL trade-11 VOID (no-schema; RD-ruled semantic)

**Mechanism (no-schema; §10.1 is the RD decision):** an audited **`trade_events` annotation row** (`event_type = 'note'`, a valid enum value used by `state.py:154`; `payload_json = {"voided": true, "reason": "SATL phantom - no broker execution; forensic 2026-07-10", "voided_at": "..."}`), append-only, audit-visible — NEVER a raw DELETE (the D19 doctrine). Plus a **central exclusion predicate** `voided_trade_ids(conn) -> frozenset[int]` (SELECT DISTINCT trade_id FROM trade_events WHERE json_extract(payload_json,'$.voided') IS 1), placed in a small `swing/trades/` helper module and consumed by every cohort/stat/equity reader.

**The reader set the predicate must touch (enumerated; RD ratifies completeness — §10.1):**

| Reader | File | Why |
|---|---|---|
| cohort lists + counts | `swing/metrics/cohort.py` (`list_trades_for_cohort`, `list_closed_trades_for_cohort`, `count_per_cohort`) | the tuition/standard cohort membership + the 16->15 restatement |
| **fills-derived equity/realized** | `swing/trades/equity.py` (`list_all_exitshape_via_fills` -> `current_equity`) | SATL's +$0.01 realized rides its fills; excluding the trade must exclude its fills from realized/equity (the B3 -$0.01 component) |
| per-trade process/tier/honesty stats | `swing/metrics/process.py`, `tier.py`, `honesty.py`, `capital.py`, `pattern_outcomes.py` | any aggregation counting trades |
| tuition-vs-standard split surfaces | wherever `entry_intent`-cohort counts render (dashboard VMs, RD reports) | the 16->15 |

**Completeness — what V1 guarantees, and its honest limit (Codex R1+R2+R4).** Grep is a DISCOVERY tool only. The predicate `voided_trade_ids(conn)` is the **single source of truth** for "which trades are void," wired at the two shared aggregation entry points — `cohort.py:list_trades_for_cohort`/`count_per_cohort` (cohort stats) and `equity.py:list_all_exitshape_via_fills` (realized/equity). The binding artifacts are TWO test layers:
- **(module-export layer)** `test_voided_trade_excluded_everywhere` iterates each affected module's **public exports** (`__all__`/public trade-or-fill readers), seeds a voided trade + fills, and asserts each EXCLUDES the void OR is on an explicit AUDIT-EXEMPT allowlist (base repos `list_open_trades`/`list_closed_trades`/`list_all_fills` + trade-detail surfaces — audit-visible per D19). A new export without exclusion fails the test.
- **(render/summary layer — Codex R4)** assertions over the ACTUAL consuming surfaces the void must affect: `current_equity`, the tuition-cohort **count** surface (the 16->15 the RD read consumes), and the standard-cohort realized (AMN) — i.e. the exact surfaces B3 witnesses. This catches a surface that aggregates `trades`/`fills` WITHOUT going through the two entry points (a web VM / briefing renderer / RD report).

**V1 CLAIM (narrowed per Codex R5 — the plan promises exactly what it enforces):** B2 V1 excludes SATL from a **named, audited surface set** — the two shared entry points (`list_trades_for_cohort`/`count_per_cohort`, `list_all_exitshape_via_fills`) + every public reader enumerated by the module-export test + the B3-witnessed render surfaces (`current_equity`, the tuition-cohort count, the standard-cohort/AMN realized). The acceptance criteria (§9) are scoped to EXACTLY that set. V1 does **NOT** claim strict closed-world "no surface anywhere can ever count SATL" — that is the **V2 single-mandatory-aggregation-layer refactor** (re-routing every stat/render reader through one choke point), beyond 20-A's pre-Monday deadline. **There is NO V1 production acceptance claim of full/strict-ALL exclusion** (Codex R7) — the ONLY acceptance criteria B2 asserts are the named audited surfaces; the brief's literal "excluded from ALL cohorts and stats" is satisfied only AFTER the V2 single-choke-point refactor. This is the **RD/CHARC decision** (§10.1): is the narrowed V1 audited-surface exclusion acceptable for a one-trade phantom void (with the V2 refactor scheduled later), or does 20-A expand to the refactor now? The plan does not resolve it unilaterally — it states the claim it can prove and routes the "strict-ALL" gap to the owning directors.

**Live-verified impact:** tuition (`entry_intent='hypothesis_test_by_design'`) = 16 (all `reviewed`) -> 15 after void; standard = 2 (unchanged — AMN is standard). SATL fills 20 (entry 1@10.31) + 21 (exit 1@10.32) -> excluding the trade removes +$0.01 from realized/equity.

**The equity-path exclusion is MANDATORY, not optional (Codex R3 MAJOR).** The brief says SATL is excluded from **ALL cohorts and stats**; `current_equity` is a live financial stat, so the void MUST reach it — B2 wires the predicate into `equity.py:list_all_exitshape_via_fills` (the single shared realized/equity entry point that `current_equity` consumes) so SATL's fills are excluded from realized/equity. (The badge would clear on the +$10.77 AMN fix alone, but leaving SATL's +$0.01 in a financial total violates "ALL stats" and is not shipped.) The two shared entry points — `cohort.py:list_trades_for_cohort`/`count_per_cohort` (cohort stats) and `equity.py:list_all_exitshape_via_fills` (realized/equity) — are the exclusion choke points; the enumerate-public-readers completeness test proves no stat surface bypasses them. The reader set is the plan's largest surface and enlarges A5 beyond "classifier + auto_correct"; §10.1 is the RD gate on the mechanism + the choke-point completeness.

### 7.3 Task B-3 — post-correction verification (RD-WITNESSED; operator-witnessed)

**NOT self-certified by the executing implementer.** The forensic doc's arithmetic is the fixture:

| Check | Expected (forensic) | Witness |
|---|---|---|
| `current_equity` | rises ~+$10.94 (AMN fill +$10.77 dominant + SATL -$0.01 on void + penny/rounding) -> equity_delta ~= **-$0.17** (< $10 tol) -> the cash-review badge SELF-CLEARS with ZERO tolerance change | operator (live badge death) |
| AMN realized | recorded **-$9.60** -> true **+$1.17** (trim 35.65 + stop 32.06 vs entry 33.66) | RD |
| H1 epoch standard-cohort ledger | re-derived from corrected fills; **Sigma-realized reconciled to the broker TO THE CENT** | RD (the re-derivation) |

Executing implementer supplies: (a) a test asserting `current_equity` on a seeded DB with the corrected fills + voided SATL equals the forensic figure; (b) a test asserting AMN realized flips to +$1.17 after the fill correction; (c) a test asserting `voided_trade_ids` excludes SATL from `list_all_exitshape_via_fills` and the tuition cohort count. These are code tests; the LIVE re-derivation + badge death are the RD/operator gate.

---

## 8. The ORDER — commit sequence (RD-binding; §10.3)

Single branch `20a-corrector`; the ORDER is encoded as the commit sequence, and Half B is not run on the live DB until Half A is merged:

```
1. test(recon): A2-magnitude band discriminators (red)        # Task A-1
2. feat(recon): classifier magnitude band (green)
3. test(recon): matcher enumeration + Shape-D + A1 list (red) # Task A-2
4. feat(recon): matcher candidate enumeration + Shape-D emit
5. test(recon): classifier Shape-D A1/A2-side/A2-date (red)   # Task A-3
6. feat(recon): classifier Shape-D branch (both entry+close)
7. test(recon): A3 re-correction alarm discriminators (red)   # Task A-4
8. feat(recon): re-correction alarm + pivot/backfill catch
9. test(recon): A4 fills<->trades invariant (red)             # Task A-5
10. feat(recon): A4 consistency check emit
11. feat(trades): voided_trade_ids predicate + reader wiring  # Task B-2 CODE
12. test: B2 exclusion + B3 verification fixtures
--- HALF A + B2-code MERGE gate (RD QA + suite + codex) ---
--- THEN on the live DB (operator/RD-witnessed): B-1 overrides, B-2 SATL void annotation, B-3 verification ---
```

**Never data-first.** If any live fill were corrected while the old matcher could still run, #33->#34 proves the corruption reapplies. The A-half code (the matcher fix + the guards) MUST be merged before B-1/B-2 touch the live DB. B-2's *code* (the predicate + wiring) ships with Half A; B-2's *data* (the SATL annotation row) is an operator action post-merge.

---

## 9. Discriminating test matrix — live-verified fixtures + pre/post arithmetic

All fixtures are real live rows (read-only probe 2026-07-11). Every discriminator computes the assertion under BOTH the pre-fix and post-fix path to prove it distinguishes.

**Live geometries (fixtures):**
- PTEN: trade 10, fill **17** action `entry` qty **15** price **12.305** (corrupt; broker-true **13.00**) date 2026-05-19; executions entry BUY 15@13.00 + exit SELL 15@~12.305.
- DFTX: trade 16, fill **28** action `entry` qty **7** price **22.16** (corrupt; broker-true **24.53**) date 2026-06-01; executions entry BUY 7@24.53 + exit SELL 7@22.16.
- AMN: trade 18, fill **37** action `trim` qty **3** price **32.06** (corrupt; broker-true **35.65**) date 2026-07-07; executions trim SELL 3@35.65 (07-07) + stop SELL 3@32.06 (07-09).
- SATL: trade 11, fills 20 (entry 1@10.31) + 21 (exit 1@10.32); `entry_intent='hypothesis_test_by_design'`.
- Legitimate corrections (must stay tier-1): CVGI fill 9 `5.23->5.30` (**1.34%**), fill 15 `12.70->12.75` (0.39%), AMN #33 `35.75->35.65` (**0.28%**).

| Test | Guard | Pre-fix (today) | Post-fix | Distinguishes? |
|---|---|---|---|---|
| PTEN/DFTX/AMN corrupt -> tier-2 not auto (`good_matches==[]`, >=2 candidates -> A1) | A1 | matcher picks wrong leg -> tier-1 auto -> `fills.price` overwritten | corrupt fill has NO fully-consistent candidate (opposite side / 2-session stop) -> LIST-shape -> tier-2 `multi_match_within_window`; no auto-apply | YES (tier flips 1->2, all three) |
| NORMAL correct round-trip fill -> NOT demoted (no false pending) | A1 | (n/a — was correct) | `good_matches==1` (the correct same-side/same-session leg) -> suppressed, no emit | YES (guard does not over-fire on normal trades) |
| AMN #34 re-correction -> blocked + material | A3 | fill 37 already `auto_applied` 35.65; new tier-1 32.06 -> 2nd `auto_applied` (the #34 corruption) | `ReCorrectionContradictionError` -> material tier-2; fill stays 35.65 | YES (2nd auto vs block) |
| side-mismatch (entry fill, SELL exec) -> tier-2 | A2-side | Shape-C payload has no side; tier-1 | Shape-D `execution_side=SELL` vs action `entry` -> tier-2 | YES |
| date-distance (07-07 fill, 07-09 exec) -> tier-2 | A2-date | no date check; tier-1 | `execution_sessions_from_fill=2 > 1` -> tier-2 (07-07 Mon .. 07-09 Wed = 2 NYSE sessions, session-accurate — NOT the inadequate calendar-day proxy) | YES |
| magnitude PTEN 5.35% -> tier-2 | A2-mag | tier-1 (5.35% overwrite applied) | 5.35% > 2% -> tier-2 | YES |
| magnitude CVGI 1.34% -> STAYS tier-1 | A2-mag | tier-1 | 1.34% <= 2% -> tier-1 (unchanged) | YES (guards don't over-fire) |
| A4 fires on live PTEN/DFTX pre-B1, quiet post-B1 | A4 | no such check | fill 12.305 vs trade 13.00 = $0.695 > $0.005 -> material discrepancy; post-B1 fill 13.00 -> 0 divergence -> quiet | YES (fires vs quiet) |
| B3 AMN realized -9.60 -> +1.17 | B3 | realized from fill 32.06 = -9.60 | fill 35.65 -> +1.17 | YES |
| B2 SATL excluded from the AUDITED surface set (narrowed claim) | B2 | tuition count 16; SATL +$0.01 in `current_equity` | 15; SATL fills excluded from `list_all_exitshape_via_fills` -> `current_equity`; absent from every enumerated public reader | YES (asserted per-surface; strict-ALL is the flagged V2) |

**A2 band arithmetic (proves the band separates the two populations):** legitimate max = **1.34%** (CVGI); corruption min = **5.35%** (PTEN). Band **2.0%** -> all three corruptions (5.35/9.66/10.07%) demote; all legitimate fixes (1.34/0.39/0.28%) stay tier-1. Clean gap 1.34% .. 5.35%.

---

## 10. RD/CHARC PLAN-STAGE DECISION SURFACE (the items the directors rule on)

### 10.1 The B2 no-schema void mechanism + the reader set
- **Mechanism:** `trade_events` `note` annotation (`payload.voided=true`) + a central `voided_trade_ids(conn)` predicate. RD confirms this satisfies "excluded from ALL cohorts/stats, preserved audit-visible, NEVER raw-delete."
- **Completeness — narrowed V1 claim + the strict-ALL scope decision (Codex R2/R4/R5/R7/R9):** V1 excludes SATL from the NAMED audited surface set (two entry points + enumerated public readers + B3-witnessed render surfaces); the acceptance criteria are scoped to exactly that set, with NO production acceptance claim of full closed-world exclusion. **THE DECISION:** the brief's literal "ALL cohorts/stats" needs a **stats-only aggregation choke point** every cohort/stat/equity reader is forced through + a bypass-failing regression test (Codex's recommended mechanism). **Why it cannot be a lower-level base-repo filter:** the base readers (`list_all_fills`/`list_closed_trades`/`list_open_trades`) are shared by BOTH stats AND the AUDIT/trade-detail surfaces, which MUST keep displaying the voided row (D19 audit-visible) — so a base-repo filter would hide the void from audit (a D19 violation). A correct closed-world void therefore needs a NEW stats-only aggregation layer — the V2 refactor, a scope + architecture expansion beyond the pre-Monday, no-schema constraints. **RD/CHARC rule:** accept the narrowed V1 audited-surface exclusion for the one-trade phantom void (V2 scheduled later), OR expand 20-A scope to build the stats-only choke point now. A writing-plans implementer cannot self-authorize that scope/architecture expansion — the plan surfaces it rather than over-claiming or unilaterally expanding.
- **Reader set (RD ratifies):** `swing/metrics/cohort.py` (cohort counts — the 16->15) + **`swing/trades/equity.py` `list_all_exitshape_via_fills`** (the fills-derived equity/realized — the SATL -$0.01) + the per-trade stat aggregations (`process.py`/`tier.py`/`honesty.py`/`capital.py`/`pattern_outcomes.py`) + the tuition/standard split surfaces.
- **Equity exclusion is MANDATORY (Codex R3):** the void reaches `current_equity` via `equity.py:list_all_exitshape_via_fills` — SATL is excluded from ALL stats per the brief, not just cohort counts. The two shared choke points (`cohort.py` cohort readers + `equity.py:list_all_exitshape_via_fills`) carry the exclusion; the enumerate-public-readers test proves no surface bypasses them. A full single-mandatory-entrypoint refactor is a V2 consolidation (beyond the deadline); the test enforces completeness in V1. RD confirms the mechanism + that the two choke points are the closed set.

### 10.2 The A2 %-band (and the A2-date "1 session" definition)
- **Proposed band: 2.0% of the journal price**, live-derived: the legitimate fill-price-correction population maxes at 1.34% (CVGI 1.34%, 0.39%, 0.28% incl. the legit AMN #33 trim-fix); the three corruptions are 5.35% / 9.66% / 10.07%. A 2% band sits in the clean gap (>1.4x the largest legit, <0.4x the smallest corruption). RD may set 3% for extra headroom (still < 5.35%). Optional absolute belt (e.g. also demote if `abs(delta) >= $X`) is an RD option; V1 proposes pure %.
- **A2-date (RESOLVED toward session-accurate after Codex R1):** the distance is computed **session-accurately at the matcher** (`swing/evaluation/dates.py`) and passed into the payload as `execution_sessions_from_fill` (int); the classifier does a pure integer compare (`> 1 -> demote`). A calendar-day proxy was rejected: it cannot distinguish the AMN 2-session/2-calendar-day corruption from a legitimate Fri->Mon 1-session/3-calendar-day fix (Codex R1 MAJOR). RD rules ONLY the threshold — proposed **`> 1` session** (i.e. same-session or adjacent-session is "within 1 session," >1 demotes). The classifier purity lock is preserved (it never imports a calendar; it compares a pre-computed int).

### 10.3 The ORDER constraint encoding
- Encoded as the §8 commit sequence: **all A-half guard commits (1-10) + B2-predicate code (11-12) land and MERGE before any B-1/B-2 live-DB data action.** Half B data is operator/RD-run post-merge. Never data-first (the #33->#34 precedent). RD confirms the encoding.

### 10.4 A4's discrepancy routing — a CHARC schema-route decision (Codex R4+R5)
- The clean, safely-isolated A4 wants a **dedicated `discrepancy_type`** (migration 0032 + the #11 one-commit discipline). Per the SCHEMA-STOP the plan does NOT design past it: **CHARC rules** — approve the dedicated type (schema; cleanest isolation), OR take the no-schema fallback A4-i (`entry_price_mismatch` + `internal_consistency` discriminator + the mandated consumer audit). A4-i is deadline-compatible; the dedicated type is the semantically-correct target. If the consumer audit finds an unsafe type-keyed consumer, the schema route becomes required.

---

## 11. SCHEMA-STOP disposition + open questions / deviations

**SCHEMA-STOP — no migration is needed (design lands entirely no-schema):**
- **B2 void:** uses a `trade_events` `note` annotation (`event_type='note'` is already in the CHECK enum; `state.py:154` uses it) + a read-side predicate. The trade-state CHECK (`0014_...sql:139` / `state.py:136` = `entered|managing|partial_exited|closed|reviewed`, NO `voided`) is **untouched** — the void is an annotation, not a state value. **No CHECK widen, no new column.**
- **B1:** `operator_overridden` is already in the `correction_action` CHECK (`0019_...sql:44-45`). No schema.
- **A4:** reuses an existing `discrepancy_type` (§6.4 A4-i). The `discrepancy_type` CHECK (migration 0031) is untouched. If RD/CHARC instead want a dedicated `fills_trades_price_divergence` type (§6.4 A4-iii), THAT is a schema route -> **STOP and route to CHARC** (not taken in this plan).

**Deviations / open questions for RD / operator:**
1. **Scope addition (decision #0, §2):** `swing/trades/schwab_reconciliation.py` must join the 20-A scope (same carve-out lane; no schema/dependency). Needs RD/CHARC ratification at the plan gate — the plan cannot honor A1/A2-side/A4 without it.
2. **AMN correction-chain anomaly (§7.1):** live corrections #33 and #34 both carry `superseded_by = NULL` on fill 37 (the corrector failed to chain). B1 overrides #34 (the effective head) and leaves #33 as a dangling audit artifact. RD/operator: acceptable, or should B1 also stamp #33.superseded_by = #34 to repair the chain (a supported `update_superseded_by`, still append-only-consistent)?
3. **A4 coverage (RESOLVED after Codex R4):** A4 now iterates ALL trades with entry fills (open + closed/reviewed) — NOT open-only — so it protects the closed-trade surfaces where the six-week divergence actually lived. No open question remains; RD may still weigh the nightly cost of the all-trades pass (small: one VWAP per trade with entry fills).
4. **A3 exception design (§5.4):** dedicated `ReCorrectionContradictionError` (recommended) vs. reuse `ValidatorRejectedError` (zero pivot change). Confirm.
5. **A2-date threshold (§10.2):** session-accurate distance (computed at the matcher) is locked after Codex R1; RD rules only the threshold — proposed `> 1` session demotes.

---

## 12. Task checklist (executing implementer)

- [ ] A-1 magnitude band (classifier, pure) — TDD, both entry + close Shape-C branches.
- [ ] A-2 matcher enumeration + Shape-D emit + A1 list-shape (schwab_reconciliation.py).
- [ ] A-3 classifier Shape-D branch (entry + close) + close-side list branch + fail-closed contract (missing/malformed field -> tier-2) + the session-fallback (`null` sentinel) test.
- [ ] A-4 re-correction alarm — EFFECTIVE-chain-head based (blocks auto-re-fire AND operator-override clobber) + pivot + backfill catch. **Test BOTH firing sites** (pivot + backfill) against the same guard contract.
- [ ] A-5 fills<->trades invariant (schwab_reconciliation.py, ALL trades incl. closed; discriminator + pivot classify-skip so it is never auto-corrected) + consumer audit of `entry_price_mismatch`.
- [ ] B-2 code: `voided_trade_ids` predicate + reader wiring (grep-completeness pass).
- [ ] B-3 verification tests (current_equity / AMN realized / SATL exclusion).
- [ ] FULL fast suite green BEFORE codex review; ruff clean on `swing/`.
- [ ] review-strong to convergence + codex-auto-review (production measurement-chain code).
- [ ] RD plan-stage sign-off (§10) BEFORE executing; RD merge-blocking QA + RD-witnessed B-3 + operator badge-death witness AFTER.
- [ ] Live-DB B-1 overrides + B-2 SATL annotation: operator/RD-run, post-merge, order-respecting.
```

---

## 13. Director rulings — LOCKED 2026-07-11 (plan-stage gate resolved; operator: proceed)

All six plan-stage decisions were ruled by CHARC + RD (rulings reconciled, zero conflicts) and the operator authorized executing. **These are BINDING for the executing implementer — locked decisions, not options. Where §5-§11 offered a choice, the ruling below WINS.**

**D#0 — SCOPE (CHARC ratified, RD supported): `swing/trades/schwab_reconciliation.py` IS in the 20-A A5 scope.** The brief's A5 file list was incomplete (the root-cause matcher + `_compute_execution_price` at `:440` live here, not the classifier). Same `swing/trades/` carve-out lane under the SAME binding conditions: matcher edits only for A1/A2/A4 (+ the A5 watchdog); the step-6 match loop's EXISTING semantics preserved except the new guards; append-only corrections; sandbox gating untouched; NO reach beyond `swing/trades`.

**D-A4 — no-schema A4-i LOCKED (CHARC), with THREE binding conditions:**
1. the `internal_consistency` discriminator is a SINGLE NAMED CONSTANT (a distinct greppable marker) so the future dedicated-type migration is mechanical;
2. the consumer audit is REQUIRED (not optional): every existing `entry_price_mismatch` consumer (classifier branches, GUI render, counters, choice menus) verified to behave sanely on the internal-consistency variant, AND the both-firing-site classify-skip (pivot + backfill) proven by a discriminating test;
3. the dedicated `discrepancy_type` (migration 0032 + the #11 one-commit multi-mirror discipline) is FLAGGED in the return report as a NAMED follow-up for a lull / the Phase-20 close (the orchestrator registers it with CHARC) — the taxonomy debt is acknowledged, not denied.
Carve-back (RD-confirmed NOT invoked): if the consumer audit finds a type-keyed consumer that is unsafe on the overloaded type, STOP and route to CHARC for the migration (§11) — do NOT silently absorb.

**D-B2 — narrowed-V1 void LOCKED (RD), with TWO binding bounds:**
(a) the NAMED audited surface set MUST cover everything the August monthly read + weekly glance + journal stats consume — enumerate + wire the exclusion through: journal analyze/stats, trade-process/metrics surfaces, hypothesis progress counts, equity/realized aggregations. The B3 witness verifies SATL EXCLUDED from those AND voided-VISIBLE on the trade-detail surface (D19 audit-visibility).
(b) the strict-ALL stats-only aggregation choke point is BANKED as a V2 candidate, NOT commissioned.
Mechanism confirmed: `trade_events` `note` annotation + central `voided_trade_ids` predicate, no CHECK widen.

**D-A2 — band = 2.0% LOCKED (RD; declines 3%; declines the absolute-$ belt for V1).** `_MAX_TIER1_OVERWRITE_RATIO = 0.02` is fixed, not a proposal. Date threshold LOCKED: `execution_sessions_from_fill > 1` demotes (session-accurate at the matcher, pure-int compare in the classifier — classifier purity preserved).

**D-ORDER — CONFIRMED (RD).** The §8 commit sequence is binding: all A-half guards + the B2-predicate CODE merge (RD QA + suite + codex) BEFORE any live-DB B1/B2 data action. Never data-first.

**D-#33 — STAMP THE CHAIN (RD).** Half B's B1 step ALSO sets `#33.superseded_by = #34` via the supported append-only `update_superseded_by` (the corrector never wrote the pointer; two chain heads on fill 37 break head-queries + poison forensics). This is a live-DB Half-B action (operator/RD-run post-merge); the executing implementer supplies the driver/verification, not the live mutation.

**Micro-locks (RD):** A3's exception is the DEDICATED `ReCorrectionContradictionError` (distinct alarm identity — do NOT reuse `ValidatorRejectedError`). The A4 all-trades nightly VWAP pass cost is accepted.

**Executing scope boundary (reaffirmed):** the executing implementer ships CODE only — Half-A guards A1-A4, the B2 `voided_trade_ids` predicate + reader wiring, and the B3 verification TESTS (commits 1-12 of §8). It does NOT touch the live DB: B1 overrides + the #33 stamp + the B2 SATL annotation row are operator/RD-run AFTER merge (§8's post-merge block). B3's live re-derivation + badge death are the RD/operator witness gate, not implementer self-certification.

**Remaining gates (post-executing):** RD merge-blocking QA → orchestrator rebase + `--ff-only` + merged-head no-false-green → live-DB Half B (operator/RD-run: B1 overrides + #33 stamp, B2 SATL void) → RD-witnessed B3 (AMN -$9.60 -> +$1.17; equity_delta -> ~-$0.17, badge self-clears with zero tolerance change; H1 epoch re-derivation Sigma-to-the-cent) + operator badge-death witness.
