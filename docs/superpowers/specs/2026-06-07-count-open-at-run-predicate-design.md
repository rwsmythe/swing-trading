# Design Spec — `_count_open_at_run` Metrics Predicate Fix (Issue #3)

**Date:** 2026-06-07
**Arc:** Phase 15 / metrics-correctness fix (integration-review Issue #3).
**Cycle:** `copowers:brainstorming` → LOCKED design spec.
**Branch-from:** `main` HEAD `4082d13c`.
**Schema:** NONE — v24 holds. Approach A derives the answer entirely from existing `trades` columns; **no terminal-timestamp column is added.**
**Change locus:** `swing/metrics/capital.py` only (`swing/trades/` + `swing/data/` are read-only references).

---

## 1. Problem statement

`_count_open_at_run(conn, *, started_ts)` ([capital.py:418-433](../../../swing/metrics/capital.py)) counts trades that were open *at a given historical pipeline run's start time*, feeding the capital-friction trend surface via two callers ([capital.py:585](../../../swing/metrics/capital.py) `concurrent_open_positions`, [capital.py:611](../../../swing/metrics/capital.py) `run_open_count`).

The current predicate:

```sql
SELECT COUNT(*) FROM trades
WHERE pre_trade_locked_at IS NOT NULL AND pre_trade_locked_at <> ''
  AND pre_trade_locked_at <= ?                                   -- entered at/before the run
  AND (last_fill_at IS NULL OR last_fill_at = '' OR last_fill_at >= ?)  -- :BUG:
```

**The defect (Issue #3; data-integrity spec §8/OQ-5 routed it here):** the `last_fill_at >= started_ts` clause treats `last_fill_at` as a *close time for EVERY trade*. But `last_fill_at = MAX(fill_datetime)` over **all** actions ([fills.py:139-141](../../../swing/data/repos/fills.py)). For a trade entered before the run whose only fill is the entry and is **still open**, `last_fill_at` is that entry datetime `< started_ts` (and non-NULL) → the clause is FALSE → the trade is wrongly **excluded**.

**Concrete symptom:** capital-friction `concurrent_open_positions = 0` for Run #89 despite SKYT open since 5/28 (the integration-review finding).

`last_fill_at` is a valid close-proxy **only for already-closed trades** (their last fill *is* the closing fill). The fix restricts the terminal clause to terminal-state trades.

---

## 2. Grounding (read-only; verified on HEAD `4082d13c`)

These facts, established by reading the exit service + state machine + fills repo, drive the mechanism choice in §3.

- **G1 — `last_fill_at` is the MAX fill datetime.** `last_fill_at = (SELECT MAX(fill_datetime) FROM fills WHERE trade_id = ?)` ([fills.py:139-141](../../../swing/data/repos/fills.py); same backfill in [migration 0014:120-122](../../../swing/data/migrations/0014_phase7_state_machine_and_fills.sql)). For a **closed/reviewed** trade no fills occur after close (exits are only permitted from active states — [exit.py:160-164](../../../swing/trades/exit.py)), so its MAX fill *is* the closing fill ⇒ **`last_fill_at` == close time for terminal trades**. A review adds no fills, so `reviewed` trades keep the same close `last_fill_at`.

- **G2 — action semantics (resolves OQ-3 factually).** [exit.py:173-179](../../../swing/trades/exit.py):
  - `action='exit'` ⟺ a **full** close (`new_size == 0`).
  - a partial scale-out is `action='trim'` (`new_size > 0`, non-stop).
  - **`STOP_HIT` wins over size**: `if req.reason == ExitReason.STOP_HIT: action = "stop"` regardless of `new_size`. So a **partial stop** (`shares < current_size`) records `action='stop'` yet transitions to `partial_exited` ([exit.py:253-257](../../../swing/trades/exit.py)) — i.e. a `'stop'` fill can sit on a **still-open** trade.

- **G3 — state machine terminal states.** A trade reaches a terminal state via `state_transition(..., new_state="closed")` ([exit.py:236/250/260](../../../swing/trades/exit.py)); the holding-period query ([capital.py:397-402](../../../swing/metrics/capital.py)) treats `state IN ('closed','reviewed')` as terminal. The full lifecycle enum is `entered | managing | partial_exited | closed | reviewed`.

- **G4 — timestamp format / boundary cleanliness.** Every stored trade-event timestamp (`pre_trade_locked_at`, `fill_datetime`→`last_fill_at`) is a **naive ISO datetime**; a date-only input synthesizes `T16:00:00` (NYSE close) via `_normalize_trade_event_date_to_iso` ([exit.py:84-133](../../../swing/trades/exit.py)); tz-aware values are rejected. `pre_trade_locked_at` is set to the same normalized entry datetime ([entry.py:279-282](../../../swing/trades/entry.py)). `pipeline_runs.started_ts` is likewise a naive ISO datetime. **Lexicographic `>=`/`<=` is therefore chronologically valid throughout** — no date-granularity hazard.

---

## 3. Mechanism (OQ-1 → **Approach A: state-based, trades-only**) — operator-confirmed

A trade is open during run R iff it was **entered at/before R_start** AND **not yet closed at R_start**.

- **Entered** ≈ `pre_trade_locked_at <= started_ts` (the entry proxy, consistent with the holding-period calc at [capital.py:397](../../../swing/metrics/capital.py)).
- **Not yet closed at R_start** keys on **state**, not on a fill-derived timestamp:
  - a **non-terminal** trade (`entered`/`managing`/`partial_exited`) was open at *any* R after its entry ⇒ counts whenever entered ≤ R_start, **regardless of `last_fill_at`**;
  - a **terminal** trade (`closed`/`reviewed`) was open at R iff it closed **at/after** R_start, which by G1 is exactly `last_fill_at >= started_ts`.

### 3.1 Locked predicate

```sql
SELECT COUNT(*) FROM trades
WHERE pre_trade_locked_at IS NOT NULL AND pre_trade_locked_at <> ''
  AND pre_trade_locked_at <= :started_ts
  AND ( state NOT IN ('closed','reviewed')              -- still open → open at any R after entry
        OR last_fill_at IS NULL OR last_fill_at = ''      -- closed but no close ts → degrade-to-count
        OR last_fill_at >= :started_ts )                  -- closed at/after R_start → was open at R_start
```

The only change from HEAD is wrapping the `last_fill_at` terminal clause behind the `state NOT IN ('closed','reviewed')` disjunct. The outer `pre_trade_locked_at` guards are unchanged; the two bind parameters (`started_ts` twice) are unchanged; the function signature and both callers are unchanged.

### 3.2 Why not B or C (rejected, operator-confirmed)

- **Approach B — `exited_at = MAX(fill ts WHERE action IN ('exit','stop'))`.** Rejected: by **G2**, a partial stop puts a `'stop'` fill on a **still-open** `partial_exited` trade. B would read that pre-run `'stop'` ts as the terminal timestamp and wrongly exclude a still-open trade. B also needs a `fills` join for no correctness gain over A. (Note: the original OQ-5 wording — "`fills WHERE action='exit'`" — is doubly wrong: it misses stop-closed trades *and* the partial-stop hazard.)
- **Approach C — `→closed` state-transition `event_ts` from `trade_events`.** Rejected: `state_transition` is called with `event_ts=req.event_ts` (operator-action time = now), **not** the backdated market close ([exit.py:233-251](../../../swing/trades/exit.py)). For a backdated close, C's timestamp is wrong for historical-run comparison. C is *less* precise than A despite sounding "most semantic."

---

## 4. Edge cases (each gets a test in writing-plans)

Boundary (OQ-2) is **`>=` inclusive** (operator-confirmed): a position closing at the exact run-start instant was still open at the observation instant ⇒ counts. Symmetric with the inclusive entry boundary `pre_trade_locked_at <= started_ts`.

| # | Case | State | `last_fill_at` vs R | Old result | New result | Distinguishing? |
|---|---|---|---|---|---|---|
| E1 | **SKYT**: still-open, entered before run | `managing` | entry ts `< R` | 0 ❌ | **1** ✅ | **YES** (old=0,new=1) |
| E2 | Stop-closed before run | `closed` (stop fill `< R`) | `< R` | 0 ✅ | 0 ✅ | no (agree) |
| E3 | Closed at/after run start | `closed` | `>= R` | 1 | 1 ✅ | no (agree) |
| E4 | **Partial-stop** then still open | `partial_exited` | `'stop'` fill `< R` | 0 ❌ | **1** ✅ | **YES** — B-hazard guard |
| E5 | **Trim** then still open | `partial_exited` | trim fill `< R` | 0 ❌ | **1** ✅ | **YES** |
| E6 | Entered after run | any | n/a (`locked > R`) | 0 | 0 ✅ | no (agree) |
| E7 | `reviewed`, closed before run | `reviewed` | `< R` | 0 ✅ | 0 ✅ | no — reviewed≡closed |
| E8 | Closed, NULL `last_fill_at` | `closed` | NULL | 1 | 1 ✅ | no — degrade-to-count (OQ-3 null) |
| E9 | Boundary: closed exactly at R_start | `closed` | `== R` | 1 | 1 ✅ | no — `>=` inclusive |
| E10 | Legacy: NULL/empty `pre_trade_locked_at` | any | n/a | 0 | 0 ✅ | no — outer guard unchanged |

**E1, E4, E5 are the regression-distinguishing cases** (old predicate → 0, new → 1) and MUST each be asserted under both predicates per the `feedback_regression_test_arithmetic` discipline.

**Reviewed vs closed (E7):** the open-count predicate treats them identically (both in the terminal set), matching the holding-period query's `state IN ('closed','reviewed')`.

**NULL-close degradation (E8):** an anomalous `closed` row with no `last_fill_at` (e.g. a tier-3 state mutation that set `state='closed'` without a closing fill) **counts** — preserving the original NULL-permissive branch and the still-open default. Documented as a known, bounded over-count of an unknowable case (operator-confirmed OQ-3 disposition).

---

## 5. Locks / invariants

- **Schema NONE (v24)** — derive, no column added. DB-outside-Drive invariant untouched.
- **Phase isolation:** `swing/metrics/capital.py` is the sole change locus. `swing/trades/` + `swing/data/` are read-only references (read to ground the close model; not modified).
- **Both callers correct:** the predicate change is correct for the live per-run trend ([capital.py:585](../../../swing/metrics/capital.py)) AND the per-run count ([capital.py:611](../../../swing/metrics/capital.py)); no caller edit needed.
- **Signature unchanged:** `_count_open_at_run(conn, *, started_ts: str) -> int`.
- **Discriminating tests** (`feedback_regression_test_arithmetic`): each test computes the count under BOTH the old and new predicate to confirm it distinguishes; E1/E4/E5 are the witnesses.
- **Docstring updated** to describe the state-based predicate (the current docstring describes the buggy `last_fill_at`-as-close proxy).

---

## 6. Resolved open questions

- **OQ-1 — terminal-timestamp mechanism:** **Approach A (state-based, trades-only).** Rationale: trades-only (no `fills` join), handles stops for free by keying on *state* not *action*, and is immune to the partial-stop hazard that breaks B (G2). C is rejected because its `event_ts` is operator-action time, not the backdated market close (G3/§3.2). *Operator-confirmed.*
- **OQ-2 — boundary semantics:** **`>=` (inclusive).** A trade closing at the exact run-start instant was open at the observation instant; symmetric with the inclusive entry boundary. *Operator-confirmed.*
- **OQ-3 — partial-exit semantics + NULL-close:** factually resolved by G2 (`'exit'` is always a full close; partials are `'trim'`; a `'stop'` can be partial — the reason A beats B). NULL-`last_fill_at` closed trades **count** (degrade-to-include). *Operator-confirmed.*
- **Schema OQ (column?):** NO column added — Approach A derives from existing state. No deviation from the schema-NONE mandate to flag.

---

## 7. Out of scope

NOT a schema change. NOT a `swing/trades/` or `swing/data/` modification. NOT a rework of the capital-friction surface beyond the open-count predicate. The `account_equity_snapshots` snapshot-read hypothesis (original integration-review framing) was wrong and is out of scope — the fix is in the trade domain. The banked reconciliation trade-field allowlist is unrelated.

---

## 8. Hand-off to writing-plans

A single-task plan: (1) replace the predicate in `_count_open_at_run` per §3.1; (2) update the docstring per §5; (3) add the E1-E10 test matrix per §4 (E1/E4/E5 dual-predicate discriminating). Fast suite green; ruff clean; commit conventional, no Co-Authored-By, final `-m` paragraph plain prose.
