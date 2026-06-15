# 18-B.1 — insert_observation OHLC write-barrier guard (dispatch brief)

**Audience:** a fresh implementer (sub-agent via a `.claude/agents/implementer-*` cell), NO prior context.
**Phase:** copowers executing — a NEW, small, precisely-scoped arc off CURRENT MAIN. **Measurement-core (RD merge-blocking):** the guard sits on the insert path to the measurement substrate. **CHARC arch-pass PASSED (`20260615T105631Z`) with the carve-out in §2.** Spec: `docs/data-collection-health-monitor-commissioning-brief.md` §6.6 FIX 2.
**Expected duration:** short (one guard in one function + two distinguishing tests + the review loop).

## §0 Read first
1. `docs/implementer-dispatch-recipe.md` — the protocol. 2. The repo `CLAUDE.md` (gotchas — esp. SQLite/repo-tx + the F6/finiteness family). 3. `swing/data/repos/pattern_forward_observations.py` — `insert_observation` (the ONLY function you change) + `_row_to_observation` / the `get_*` readers (the read path you must PROVE you do NOT regress). 4. `swing/data/ohlcv_finiteness.py` — `is_finite_ohlc` (the C1 shared predicate you reuse; note it RAISES `TypeError` on `None`). 5. `swing/pipeline/temporal_metadata.py:build_ohlc_today_json` — the writer-side shape of `ohlc_today_json` (`{open,high,low,close,volume,provider}`). 6. `docs/data-collection-health-monitor-commissioning-brief.md` §6.6 FIX 2. 7. This brief.

## §0 Skill posture
TDD (failing test → minimal impl → pass → commit). Hand-run the WSL-Codex review at the **`review-strong`** tier to convergence; persist each round to `.copowers-findings.md`. The bounded-scope adjudication applies (discipline #39 / memory `feedback_schema_boundary_defensive_scope`): a finding premised SOLELY on a schema-prevented value is not a blocking major (adjudicate out-of-scope WITH the cited constraint). Return your report to the ORCHESTRATOR only — no mailbox, no `role_mail`.

## §1 The change (`swing/data/repos/pattern_forward_observations.py` — `insert_observation` ONLY)
Add a **fail-loud OHLC finiteness write-barrier** that **RAISES on a non-finite `ohlc_today_json` BEFORE the INSERT** (so non-finite OHLC never reaches durable storage via this path going forward). Mirror the monitor's #1 extraction discipline:
- `json.loads(ohlc_today_json)`; for each of the 4 OHLC keys (`open`,`high`,`low`,`close`): if the key is **missing / None / not a number** → INVALID; else collect the value.
- Call `is_finite_ohlc(open, high, low, close)` (reuse the C1 predicate — `swing/data/ohlcv_finiteness.py`) for the NaN/inf case. The per-key None/missing/non-numeric guard MUST run BEFORE the predicate (it raises `TypeError` on `None`).
- On INVALID/non-finite → **raise** a clear, descriptive error (e.g. `ValueError` naming the offending field + the observation context) BEFORE any write. Volume is EXEMPT (finiteness of OHLC only — Arc-8). ASCII message.
- Keep it a thin guard reusing the shared predicate — do NOT re-implement NaN/inf detection.

## §2 CHARC carve-out + fence (authorized — do NOT exceed)
- **`insert_observation` guard ONLY.** This is a CHARC-AUTHORIZED `swing/data` carve-out scoped to exactly this guard.
- **NO `__post_init__` change.** CHARC deliberately RELOCATED the guard OFF the model's `__post_init__` because that fires on the READ mapper `_row_to_observation` and would **regress reads of the 103 accepted historical non-finite rows**. The barrier lives on the WRITE path only.
- **NO schema, NO new dependency.** **Append-only repo discipline preserved:** caller controls the transaction — `insert_observation` must NOT call `conn.commit()` (the guard raises before the INSERT; no tx change).
- Touch ONLY `swing/data/repos/pattern_forward_observations.py` + `tests/`. Nothing else.

## §3 Two REQUIRED distinguishing tests (C-18B1 — BOTH; do not omit either)
1. **WRITE-BARRIER (both-ways):** `insert_observation(...)` with a non-finite OHLC (`close=NaN`, the real shape) RAISES post-fix; pre-fix it would INSERT the row. State the pre-fix vs post-fix behavior in the docstring (memory `feedback_regression_test_arithmetic`). Also assert a FINITE OHLC still inserts cleanly (no false-positive on good data) — incl. a volume-less / `volume=NaN` finite-OHLC row stays accepted (volume exempt).
2. **READ-PRESERVATION (encodes the finding — MANDATORY):** seed a non-finite historical row **bypassing the new barrier** (raw SQL / direct `conn.execute` INSERT of the non-finite `ohlc_today_json` text — mirror the monitor's plan-Task-2 raw-insert technique), then read it back through `_row_to_observation` / the repo `get_*` and assert it does **NOT raise** — proving reads of the accepted 103 stay intact. This test is the guard against a future "consistency-fix" relocating the barrier back to `__post_init__` and silently regressing reads. A `__post_init__`-located guard FAILS this test.

## §4 Dispatch metadata
- **Worktree:** fresh `.worktrees/18-b1-write-barrier` off **CURRENT MAIN** (the orchestrator gives you the exact `BASELINE_SHA` in the spawn prompt): `git worktree add -b 18-b1-write-barrier .worktrees/18-b1-write-barrier <BASELINE_SHA>`. Do NOT use Agent isolation. Review diff base = that `BASELINE_SHA`.
- **Codex tier:** `review-strong` to `NO_NEW_CRITICAL_MAJOR`. Do NOT run `codex exec review` / the codex-auto-review A/B (orchestrator-owned). Leave the worktree intact (orchestrator rebases + ff-merges).

## §5 Verification
Run the FULL fast suite `python -m pytest -m "not slow" -q` to GREEN BEFORE the Codex review AND on the final post-convergence HEAD (no-false-green). `ruff check swing/` clean. Diff fence: ONLY `swing/data/repos/pattern_forward_observations.py` + `tests/` touched.

## §6 Return report (to the ORCHESTRATOR — final chat message; recipe §4)
The commit(s) + the guard (file:line); BOTH distinguishing tests (the write-barrier both-ways arithmetic + the read-preservation seeding technique); the carve-out stated honored-on-disk (insert_observation ONLY, NO `__post_init__`, caller-tx/no-commit preserved); Codex `review-strong` rounds + verdict + `.copowers-findings.md` path; any bounded-scope out-of-scope adjudications WITH the cited constraint; final-head suite count + ruff; the fence; deviations/flags. STOP-and-ask if the carve-out would need to widen (e.g. the guard can't be expressed without a `__post_init__` or schema change) — do NOT exceed the carve-out.
