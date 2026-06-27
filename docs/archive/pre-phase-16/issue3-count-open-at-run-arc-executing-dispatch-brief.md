# Executing Dispatch Brief — Issue #3 `_count_open_at_run` Predicate Fix (focused, writing-plans folded in)

**Arc:** Phase 15 / metrics-correctness fix — the capital-friction "open at run time" predicate (integration-review Issue #3).
**Cycle stage:** **focused `copowers:executing-plans`** — the spec is so precise (one predicate swap + an enumerated E1–E11 matrix) that the standalone writing-plans phase is folded in here: **the spec §8 IS the plan.** Implement it TDD, then run the adversarial Codex loop on the diff to convergence. (Orchestrator process decision for a one-function fix; the full adversarial rigor stays — on the implementation diff.)
**Authoritative source (LOCKED, Codex-converged, merged):** [`docs/superpowers/specs/2026-06-07-count-open-at-run-predicate-design.md`](superpowers/specs/2026-06-07-count-open-at-run-predicate-design.md) — READ IT END-TO-END. Implement exactly what it specifies; do NOT redesign.
**Branch-from:** main HEAD at worktree creation (currently `9059a980`; re-verify with `git log --oneline -3`).
**Schema:** NONE — v24 holds. Zero migrations. Approach A derives from existing `trades` columns.
**Deliverable:** the code change + tests on a branch, Codex-converged (`NO_NEW_CRITICAL_MAJOR`) + `.copowers-findings.md` (prompts AND responses). Commit the code (TDD, per the spec's single-task shape). Then STOP — do NOT merge.

---

## 1. Mandate (one line)

Fix `_count_open_at_run` ([swing/metrics/capital.py:418-433](../swing/metrics/capital.py)) per the LOCKED spec's **Approach A** (state-based, trades-only): a non-terminal trade (`entered`/`managing`/`partial_exited`) counts whenever entered ≤ run-start; a terminal trade (`closed`/`reviewed`) counts iff `last_fill_at >= started_ts`. Lock it with the E1–E11 test matrix.

---

## 2. The exact change (spec §3.1 — implement verbatim)

Replace the predicate so the `last_fill_at` terminal clause is gated behind the non-terminal-state disjunct:

```sql
SELECT COUNT(*) FROM trades
WHERE pre_trade_locked_at IS NOT NULL AND pre_trade_locked_at <> ''
  AND pre_trade_locked_at <= :started_ts
  AND ( state NOT IN ('closed','reviewed')              -- still open → open at any R after entry
        OR last_fill_at IS NULL OR last_fill_at = ''      -- closed but no close ts → degrade-to-count
        OR last_fill_at >= :started_ts )                  -- closed at/after R_start → was open at R_start
```

- The ONLY change from HEAD is wrapping the existing `last_fill_at` terminal clause behind `state NOT IN ('closed','reviewed')`. The outer `pre_trade_locked_at` guards, the function signature (`_count_open_at_run(conn, *, started_ts: str) -> int`), and BOTH callers ([capital.py:585](../swing/metrics/capital.py), [capital.py:611](../swing/metrics/capital.py)) are UNCHANGED.
- The two bind parameters stay `(started_ts, started_ts)` — verify the parameter count matches the `?`/named placeholders you use.
- **Update the docstring** (currently describes the buggy `last_fill_at`-as-close-for-all-trades proxy) to describe the state-based predicate + note the G1/G4 best-effort caveats (spec §5, §2).

---

## 3. Tests — the E1–E11 matrix (spec §4; implement each)

Add tests to the capital-metrics test module (find the existing `_count_open_at_run` / capital-friction tests; mirror their fixture style). The spec §4 table gives each case's state / `last_fill_at` vs R / old result / new result:

- **E1 (SKYT), E4 (partial-stop still open), E5 (trim still open)** are the DISCRIMINATING regressions (old predicate → 0, new → 1). Per `feedback_regression_test_arithmetic`, **assert each under BOTH the old and the new predicate** (compute the old-predicate count to prove it's 0/wrong and the new-predicate count to prove it's 1/right) — so the test genuinely distinguishes the fix, not just confirms the new behavior. E4 is the key guard for the G2 partial-stop hazard (a `'stop'` fill on a still-open `partial_exited` trade).
- **E2 (stop-closed-before-run), E3 (closed at/after run), E6 (entered after run), E7 (`reviewed` closed before run), E9 (boundary: closed exactly at R_start → `>=` inclusive counts), E10 (NULL/empty `pre_trade_locked_at`)** — agreement/behavior cases; assert the new predicate gives the spec's stated result.
- **E8 (closed, NULL `last_fill_at` → degrade-to-count)** — assert it counts (preserves the NULL-permissive branch).
- **E11 (malformed/mixed-shape `last_fill_at` on a closed row → degrade-safe)** — per spec §4 E11: assert (a) the call returns an `int` and does NOT raise; (b) the **deterministic delta** — count N well-formed rows (known total), re-count after adding exactly one malformed-`last_fill_at` closed row, assert the difference equals that row's explicitly-specified lexicographic outcome (0 or 1) for the chosen `started_ts`. (COUNT(*) can't observe per-row contribution, so use the delta.)

Seed fixtures with the real trade/fill shapes (the state enum is `entered|managing|partial_exited|closed|reviewed`; `pre_trade_locked_at` + `last_fill_at` are naive ISO datetime strings). Confirm against the existing capital tests' seeding helpers.

---

## 4. Locks / invariants (spec §5 — do not regress)

- **Schema NONE** (v24). DB-outside-Drive.
- **Phase isolation:** `swing/metrics/capital.py` is the SOLE change locus. `swing/trades/` + `swing/data/` are READ-ONLY (do not modify; the reconciliation `fill_datetime` normalization gap is OUT of scope — defended via E11, not fixed at source).
- Signature + both callers unchanged. `started_ts` is a precise timestamp; the boundary is `>=` inclusive (spec §4/OQ-2).
- ASCII-only in any user-facing string (no new ones expected here, but the Windows cp1252 gotcha stands).

---

## 5. Process (binding)

- **TDD:** write the E-matrix tests → see the discriminating ones fail on the pre-fix predicate → apply the §3.1 predicate swap + docstring → see them pass → `ruff check swing/` → commit (conventional, NO `Co-Authored-By`, NO `--no-verify`, final `-m` paragraph plain prose). The spec's single-task shape means this can be one commit (predicate + docstring + tests) or test-then-impl split — your call, but every commit stays green.
- **Full fast suite + ruff** at the end: `python -m pytest -m "not slow" -q` (baseline ≈7235 — report the ACTUAL count + the net-new test delta; isolate the 3 known xdist flakes with `-n0` if they appear: `test_ohlcv_reader_re_export_identity`, `test_read_cohort_csv_against_committed_v2trf`, `test_prices_refresh_uses_pipeline_eval_anchor`) + `ruff check swing/`.
- **Codex review to convergence** on the diff (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED). **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Worktree `.git` unreachable from WSL — pre-generate the diff on Windows (`git diff main...HEAD > .codex-diff.txt`) + tell Codex not to run git. **Persist BOTH prompts AND responses** to gitignored `.copowers-findings.md`.
- **Degraded-harness guard** (`feedback_degraded_harness_sequential_tool_calls`): if you hit mid-batch tool cancellations, drop to single sequential calls + re-Read before each Edit + verify each commit.

---

## 6. Return report (then STOP — do NOT merge)

Return: the commit SHA(s) + messages; the full-suite result (ACTUAL count + net-new delta + any isolated flakes); `ruff` clean; the Codex convergence verdict (round count + the final `NO_NEW_CRITICAL_MAJOR` line); and any deviation from the spec (with justification). Then STOP. Merge is the orchestrator's action after QA. Do NOT merge or push to main.

**Note for the orchestrator (carry forward):** the spec §8 carries one out-of-scope item — the reconciliation/legacy `fill_datetime` normalization gap (G4 caveat: correction-path fills aren't re-normalized via `_normalize_trade_event_date_to_iso`). It's a pre-existing `swing/trades/` data-hygiene issue, defended here via E11, NOT fixed. A candidate future hardening item alongside the banked reconciliation trade-field allowlist.

---

## 7. What this arc is NOT

NOT a schema change. NOT a `swing/trades/`/`swing/data/` modification. NOT a capital-friction surface rework beyond the open-count predicate. NOT (a) #16 (closed) or (c) Gate 4 (the quote cassette, deferred to market open). NOT the reconciliation normalization fix (banked).
