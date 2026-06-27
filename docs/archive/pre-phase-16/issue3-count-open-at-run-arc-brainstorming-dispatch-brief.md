# Brainstorming Dispatch Brief — Issue #3: `_count_open_at_run` Metrics Predicate Fix

**Arc:** Phase 15 / metrics-correctness fix — the capital-friction "concurrent open positions at run time" predicate (integration-review Issue #3).
**Cycle stage:** `copowers:brainstorming` (produce a LOCKED design spec, Codex-converged). **LEAN cycle** — the code change is one small predicate, but the *design* (how to define "open at run time") is non-obvious and operator-decision-worthy, so it gets a proper (but fast) brainstorm → writing-plans → executing.
**Branch-from:** main HEAD at worktree creation (currently `5c581eb1`; re-verify with `git log --oneline -3`).
**Schema:** NONE expected — v24 holds. The spec §8/OQ-5 root cause is "the `trades` table has NO terminal-timestamp column"; the intended fix DERIVES the answer, it does NOT add a column. If your design concludes a column/migration is warranted, STOP and flag it as a pivotal OQ (it would change the cycle's risk profile).
**Deliverable:** a locked design spec at `docs/superpowers/specs/2026-06-07-count-open-at-run-predicate-design.md` + Codex convergence + `.copowers-findings.md` (prompts AND responses).

---

## 1. Mandate (one line)

Fix `_count_open_at_run` ([swing/metrics/capital.py:418](../swing/metrics/capital.py)) so it correctly counts trades that were open *at a given historical run's start time* — currently it under-counts because its predicate keys on `last_fill_at`, which is the most-recent fill of ANY action, so a trade entered BEFORE the run and still open is wrongly excluded. Lock the correct "open at run time R" predicate, with all edge cases (stops, partial exits, the boundary, no-fills trades) resolved.

---

## 2. The bug (grounded on HEAD `5c581eb1`)

`_count_open_at_run(conn, *, started_ts)` (capital.py:418-433) currently runs:

```sql
SELECT COUNT(*) FROM trades
WHERE pre_trade_locked_at IS NOT NULL AND pre_trade_locked_at <> ''
  AND pre_trade_locked_at <= ?                         -- entered at/before the run
  AND (last_fill_at IS NULL OR last_fill_at = '' OR last_fill_at >= ?)   -- :BUG:
```

**The defect (integration-review Issue #3, root-caused in the data-integrity spec §8/OQ-5):** the `(last_fill_at >= started_ts)` clause treats `last_fill_at` as a *close time* for EVERY trade. But `last_fill_at` is the timestamp of the most-recent fill of ANY action (`entry`/`trim`/`exit`/`stop`). For a trade entered 5/28 whose only fill is that entry and is still open at a 6/04 run, `last_fill_at = 5/28 < started_ts = 6/04` and is not NULL → the clause is FALSE → the trade is EXCLUDED. **Concrete symptom:** capital-friction `concurrent_open_positions = 0` for Run#89 despite SKYT open since 5/28 (the integration-review finding). `last_fill_at` is a valid close-proxy ONLY for trades that are already closed (their last fill IS the closing fill).

**Callers (both must be correct):** capital.py:585 (`concurrent_open_positions=_count_open_at_run(...)`) and capital.py:611 (`run_open_count`). Both feed the capital-friction trend surface.

**Scope correction (handoff):** the fix is in the TRADE domain (`trades` + possibly `fills`), NOT `account_equity_snapshots` — the integration review's snapshot-read hypothesis was wrong (data-integrity spec §8/OQ-5 routed Issue #3 OUT of that arc to here).

---

## 3. The central design question (the brainstorm's core deliverable)

**What is the correct "open at run time R" predicate?** A trade is open during run R iff it was *entered at/before R_start* AND *not yet closed at R_start*. "Entered" ≈ `pre_trade_locked_at <= started_ts` (the entry proxy, consistent with the holding-period calc at capital.py:397). The hard part is **the terminal ("closed-at") timestamp**, which the `trades` table does not store directly.

**Grounding the brainstorm has already surfaced (verify, then design):**
- **Fills action enum** is `('entry','trim','exit','stop')` — [migration 0014:12](../swing/data/migrations/0014_phase7_state_machine_and_fills.sql). **A stop-out is recorded as `action='stop'`, NOT `'exit'`** ([exit.py:175](../swing/trades/exit.py) sets `action = "stop"`; :179 sets `"exit"`). **So OQ-5's literal "derive exited_at from `fills WHERE action='exit'`" is INCOMPLETE — it misses stop-closed trades.** Any fill-based terminal timestamp must be `action IN ('exit','stop')` at minimum.
- A trade reaches a terminal state via `state_transition(..., new_state="closed")` ([exit.py:236/250/260](../swing/trades/exit.py)); the holding-period query (capital.py:397-402) treats `state IN ('closed','reviewed')` as terminal.
- **For an already-closed trade, `last_fill_at` IS its close time** (the closing exit/stop fill is its most-recent fill). For a still-open trade, `last_fill_at` is an entry/trim — NOT a close.

**Candidate approaches to weigh (pick + justify; surface trade-offs to the operator):**
- **(A) State-based, reads only `trades`:** `pre_trade_locked_at <= started_ts AND (state NOT IN ('closed','reviewed') OR last_fill_at >= started_ts)`. Rationale: a still-open trade was open at any R after entry (ignore `last_fill_at`); a closed trade was open at R iff it closed at/after R_start (and for closed trades `last_fill_at` IS the close time, covering stops too since the stop fill is the last fill). Cleanest; no `fills` join; handles stops for free. **Verify the "last_fill_at == close-time for all closed trades" assumption holds** (e.g. no post-close fills; reviewed-state trades).
- **(B) Fill-derived terminal timestamp:** `exited_at = MAX(ts) FROM fills WHERE trade_id=t AND action IN ('exit','stop')`; open at R iff entered ≤ R AND (exited_at IS NULL OR exited_at >= started_ts). Closer to OQ-5's wording (corrected for stops). Risk: does a PARTIAL `action='exit'` (scale-out that leaves the position open) exist, or are partials always `action='trim'`? If partial exits can be `'exit'`, MAX(exit/stop ts) could predate the true close and mis-handle a still-open partially-exited trade. **Resolve whether `'exit'` is always a full close vs can be partial** (read the exit service).
- **(C) State-transition-event timestamp:** if a `trade_events`/state-transition log records the `→closed` transition ts, derive the terminal timestamp from it. Most semantically precise; investigate whether such a timestamped record exists and is reliable.

**Resolve which approach + WHY, with the edge cases below explicitly covered.**

---

## 4. Edge cases to nail (each needs a test)

- **Stop-closed-before-run:** a trade stopped out (action='stop', state='closed') before R_start → must NOT count at R. (The bug-prone case for approach B if it only checks 'exit'.)
- **Closed-during/at-run:** a trade that closed at/after R_start → SHOULD count (it was open when R started). Lock the boundary: is the predicate `>= started_ts` or `> started_ts`? (Per the session-anchor gotcha family, state the directionality + justify; `started_ts` is a precise timestamp, not a session date.)
- **Still-open, entered-before-run** (the SKYT case): MUST count.
- **Partial exit / trim then still open:** entered, trimmed (or partially exited), still open at R → MUST count. (Tests approach B's partial-exit hazard.)
- **Entered-after-run:** `pre_trade_locked_at > started_ts` → must NOT count (unchanged).
- **No-fills / null-timestamp trades:** the existing `pre_trade_locked_at IS NOT NULL AND <> ''` guards stay; confirm the new predicate degrades safely.
- **`reviewed` vs `closed`:** both are terminal in the holding-period query — confirm the open-count predicate treats them identically.

---

## 5. Locks / invariants

- **Schema NONE** (v24) — derive, don't add a terminal-timestamp column (flag if you disagree). DB-outside-Drive.
- **Phase isolation:** `swing/metrics/` is the change locus; `swing/trades/` + `swing/data/` are READ-only references (read the exit service + state machine to ground the close model; do NOT modify them).
- **Read-path correctness for BOTH callers** (capital.py:585, 611) — the predicate change must be correct for the live trend AND the per-run count.
- **Discriminating tests** (`feedback_regression_test_arithmetic`): each test computes the count under BOTH the old predicate and the new one to confirm it distinguishes (the SKYT case: old → 0, new → 1).

---

## 6. Open questions for the operator (brainstorming surfaces these)

- **OQ-1 — terminal-timestamp mechanism:** approach A (state-based, trades-only) vs B (exit∪stop fill MAX) vs C (state-transition event ts). Recommend with rationale; the operator confirms (this is the pivotal decision — the spec §8/OQ-5 said "fills WHERE action='exit'" but grounding shows that misses stops).
- **OQ-2 — boundary semantics:** `>= started_ts` vs `> started_ts` for "closed at/after the run start." (Does a trade that closed at the exact run-start instant count as open during that run? Likely yes → `>=`.)
- **OQ-3 — partial-exit semantics:** does `action='exit'` ever leave a position open (partial), or is partial always `'trim'`? (Determines whether approach B is safe; ground it in the exit service.)

---

## 7. copowers process (binding)

- Run `copowers:brainstorming` (wraps `superpowers:brainstorming` — explore the design WITH the operator on the §6 OQs — then the adversarial Codex loop **to convergence**, `NO_NEW_CRITICAL_MAJOR`; the 5-round cap is SUSPENDED).
- **Codex transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Worktree `.git` unreachable from WSL — pre-generate the diff on Windows + tell Codex not to run git.
- **Persist BOTH prompts AND responses** of every round (incl. the final `NO_NEW_CRITICAL_MAJOR`) to gitignored `.copowers-findings.md`.
- No `Co-Authored-By`; no `--no-verify`; conventional commits; final `-m` paragraph plain prose. Commit ONLY the spec doc.
- **Return a report:** the spec path, the resolved §6 OQs (the chosen terminal-timestamp mechanism + WHY), the Codex convergence verdict (round count + final line), anything flagged for writing-plans. Then STOP — do NOT proceed to writing-plans (a separate commission after the orchestrator QAs the spec).

---

## 8. What this arc is NOT

NOT a schema change. NOT a `swing/trades/` or `swing/data/` modification (metrics-only fix; trade/data are read-only references). NOT (a) #16 (closed), NOT (c) Gate 4 (the quote cassette — deferred to market open). NOT a rework of the capital-friction surface beyond the open-count predicate. The banked reconciliation trade-field allowlist is unrelated.
