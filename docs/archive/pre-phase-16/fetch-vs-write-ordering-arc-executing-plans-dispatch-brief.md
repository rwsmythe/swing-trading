# Fetch-vs-Write-Ordering Fix Arc -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the executing-plans implementer for the OHLCV-fetch-inside-held-`fenced_write` deadlock fix. No prior conversation context.

**Mission:** Execute the LOCKed, Codex-converged plan task-by-task (TDD) into a SHIPPED, merge-ready fix that eliminates the Run-92 `database is locked` deadlock (the pipeline holds a `lease.fenced_write()` write transaction across a network OHLCV fetch; the fetch's audit writes on a separate connection deadlock on the held lock).

**Plan (AUTHORITATIVE -- execute verbatim):** `docs/superpowers/plans/2026-06-06-fetch-vs-write-ordering-plan.md` (938 lines, 5 TDD tasks ~28 steps; Codex-converged round 1 `NO_NEW_CRITICAL_MAJOR`). Each task is a red->green->commit unit with exact file:line, real code, and the discriminating deadlock-repro test. **Re-grep every cited file:line at STEP 0** (discipline #2) -- the plan was grounded on `219698d7`; you branch from `0f77731a` (the plan-merge HEAD; swing/ code identical -- only the plan doc changed since).

**Spec (reference only):** `docs/superpowers/specs/2026-06-06-fetch-vs-write-ordering-design.md`.

**Context:** main HEAD at this dispatch = **`0f77731a`** (branch from it). ~7214 fast tests green; **schema v24 (this arc adds NO schema -- fetch-vs-write reordering + a #27 divergence audit + the stopgap revert)**. NO dependency change -> standard `pip install -e ".[dev,web]"` in the worktree (no isolated venv).

**Cumulative discipline (BINDING):** the **lease-fencing contract** (the WRITE stays inside `fenced_write` + the in-tx lease check; ONLY the FETCH moves out -- do not move writes out, do not leave network I/O in); the **audit single-tx discipline** (untouched); **#5 no-re-fetch / L2 LOCK** (reuse detect Pass-1 `bars_by_ticker`; exemplar fetched exactly once); **#27** (the OQ-E divergence audit + any new early-return emits a `warnings_json` entry); **#28/#29 exemplar OHLCV depth** (the moved-out pre-fetch keeps `window_days=400` byte-identical); Windows cp1252 -> ASCII. **TDD** (failing test -> SEE fail -> minimal impl -> SEE pass -> commit, per task). **ZERO `Co-Authored-By`; no `--no-verify`; final `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]`.**

**Skill posture:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`). After ALL tasks, run the **SINGLE Codex chain to convergence** (`NO_NEW_CRITICAL_MAJOR`; ~5-round cap suspended). **Codex transport (MCP DEAD):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; cat prompt.txt | codex exec -s read-only --skip-git-repo-check -'` (PATH prefix REQUIRED; codex-cli 0.135.0; pre-generate the diff on Windows; tell Codex NOT to run git). **Persist BOTH prompts AND responses** (incl. the final `NO_NEW_CRITICAL_MAJOR`) to `.copowers-findings.md`.

---

## §1 What ships (the plan's 5 tasks)
1. **Detect Pass-2 reorder** (runner.py:1898): SNAPSHOT `list_exemplars` + pre-fetch exemplar bars (window_days=400) BEFORE the fence -> the snapshot is AUTHORITATIVE for both bars AND scoring membership; drop the in-fence `get_or_fetch` @1994; keep `canonical_existing` re-read + `match_forward` + INSERT in-fence; reuse Pass-1 `bars_by_ticker`. (The cfg=None/no-`_conn` edge reads exemplars via a short PURE-read `fenced_write` -- the Codex R1 MINOR fix.) 2. **OQ-E divergence guard** (#27): a cheap in-fence `SELECT id` eligible-exemplar re-read vs the snapshot -> `warnings_json` (added/removed) on mid-run corpus mutation. 3. **Observe reorder** (runner.py:2628): the compute pass (idempotency/shed/`_bar_for_date`/`_advance_status`/row-build) OUTSIDE the fence; one short fence wraps ONLY `insert_observation`; preserve shed/no-bar #27 + telemetry. 4. **Stopgap revert (OQ-B):** DELETE the `[web] db_busy_timeout_ms = 5000` key + the TEMPORARY-STOPGAP comment block from `swing.config.toml` (resolves to `db.py DEFAULT_BUSY_TIMEOUT_MS = 30000`). 5. **Post-fix re-audit + gate:** re-run the §2 `fenced_write` audit (the 2 loci flip safe; #16 stays banked) + full fast suite + ruff.

## §2 Preserve exactly
- **`_step_charts` is NOT touched** (already correct -- fetch outside the fences).
- **daily_management #16 is OUT** (OQ-D banked) -- do NOT touch it.
- The **binding deadlock-repro test** (`_DeadlockProbeCache`: a 2nd connection attempts `BEGIN IMMEDIATE` with a short busy_timeout against a real held fence on a file DB; pre-fix `deadlock_observed=True` FAILS, post-fix PASS; the spy records the flag rather than RAISING -- the pre-fix `try/except: continue` would swallow a raise; anti-false-pass asserts `get_or_fetch` fired). Implement it as the plan specifies; it is the proof the fix works.

## §3 Pre-merge gate YOU deliver (in the worktree)
1. **Full fast suite green** (`python -m pytest -m "not slow" -q`). Isolate the 3 known xdist co-residency flakes (`test_ohlcv_reader_re_export_identity`, `test_read_cohort_csv_against_committed_v2trf`, `test_prices_refresh_uses_pipeline_eval_anchor`) `-n0` if they co-resident-fail. Report the exact count (`feedback_no_false_green_claim`). 2. Both loci's deadlock-repro tests green. 3. `ruff check swing/` clean. 4. Codex convergence (`.copowers-findings.md`).

## §4 Operator gate (POST-merge; you do NOT run it -- enumerate as PENDING)
**Operator-witnessed RE-RUN live gate** (the Run-92 repeat): a normal UNSEEDED `swing pipeline run --manual` MUST now show the `database is locked` fallback COLLAPSE -- NO `BEGIN IMMEDIATE FAILED` lines; Schwab becomes the primary source for the ~13-22 cache-miss tickers. The stopgap is reverted (busy_timeout back to 30000) so the gate confirms the deadlock does NOT recur even at the full 30 s. `feedback_seeded_gate_masks_default_state` (unseeded). You do NOT touch the operator's live DB.

## §5 OUT OF SCOPE
daily_management #16 (banked); the bad-bar fix (queued); the lock-contention arc's keepers (untouched except the stopgap config revert); any schema change.

## §6 Dispatch metadata
- **Subagent:** `general-purpose`, foreground, harness-default model. **Worktree:** branch `fetch-vs-write-ordering-arc-executing-plans` from main HEAD **`0f77731a`**. `python -m swing.cli`; re-check `git branch --show-current` before EACH commit (degraded-harness discipline -- single sequential calls + re-Read before each Edit + verify each commit if tool calls cancel). **You do NOT merge** (orchestrator action). **Leave the worktree INTACT** at return (holds `.copowers-findings.md`). SINGLE Codex chain after all tasks.

## §7 Return report (mirror prior executing returns)
Final HEAD + commit list (by task); the worktree fast-suite result (exact count + any `-n0` isolation); `ruff` clean; the Codex convergent verdict (cite `.copowers-findings.md` + the verbatim `NO_NEW_CRITICAL_MAJOR`); confirm the 2-loci reorder shipped (only the FETCH moved out; writes stay in-fence) + the OQ-E #27 guard + the stopgap revert (cfg default 30000, no [web] key); the post-fix §2 re-audit (2 loci safe, #16 banked); schema verdict (NONE -- v24); the operator RE-RUN live gate enumerated as PENDING; per-axis test-arithmetic (esp. the deadlock-repro); ZERO `Co-Authored-By`; worktree INTACT; merge-readiness.

---

*End of brief. Execute the converged 5-task plan: pre-fetch OHLCV OUTSIDE the `lease.fenced_write()` at the 2 loci (detect Pass-2 snapshot-authoritative + #27 divergence guard; observe compute-outside/insert-inside) + revert the busy_timeout stopgap to 30000. Charts untouched; daily-mgmt #16 banked. NO schema (v24). The binding proof is the in-process deadlock-repro test; the binding post-merge gate is the operator RE-RUN confirming the deadlock COLLAPSES at 30s.*
