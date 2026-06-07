# Fetch-vs-Write-Ordering Fix Arc -- Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the writing-plans implementer for the OHLCV-fetch-inside-held-`fenced_write` deadlock fix. No prior conversation context.

**Mission:** Turn the LOCKed, Codex-converged brainstorm spec into an executing-plans-ready, TDD-task-decomposed implementation plan.

**Spec (AUTHORITATIVE):** `docs/superpowers/specs/2026-06-06-fetch-vs-write-ordering-design.md` (430 lines; merged to main `7d8f109e`; Codex-converged R1[2maj/2min]->R2[2 new maj]->R3 `NO_NEW_CRITICAL_MAJOR`). Execute its design verbatim; **re-grep every cited file:line at writing-plans STEP 0** (discipline #2) -- the spec was grounded on the pre-merge checkout; you branch from the SHA in the inline prompt.

**Context:** main HEAD at this dispatch: see §5 (branch from it). ~7214 fast tests green; **schema v24 (this arc adds NO schema -- pure fetch-vs-write reordering + a #27 divergence audit + the stopgap revert)**. The root cause is operator-witnessed (Run 92) + orchestrator-verified: the pipeline holds a `lease.fenced_write()` write transaction open across a network OHLCV fetch, so the fetch's audit writes (separate `audit_conn`) deadlock on the held lock -> 30s/5s busy_timeout -> fail -> yfinance degrade.

**Skill posture:** `copowers:writing-plans`. **SINGLE Codex chain** to convergence (`NO_NEW_CRITICAL_MAJOR`; ~5-round cap suspended). **Codex transport (MCP DEAD):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; cat prompt.txt | codex exec -s read-only --skip-git-repo-check -'` (PATH prefix REQUIRED; codex-cli 0.135.0; pre-generate any diff on Windows; tell Codex NOT to run git). **Persist BOTH prompts AND responses** (incl. the final `NO_NEW_CRITICAL_MAJOR`) to `.copowers-findings.md`. Output: plan at `docs/superpowers/plans/2026-06-06-fetch-vs-write-ordering-plan.md`.

---

## §1 The two loci + the reorder (spec §2/§4 -- propagate)
- **Locus #8 -- `_step_pattern_detect` Pass-2** (runner.py:1898 fence wrapping the exemplar `get_or_fetch` @1994). Reorder: SNAPSHOT the exemplar rows (`list_exemplars`) + pre-fetch their bars (window_days=400, #28/#29 depth) BEFORE the fence; that snapshot is AUTHORITATIVE for both bars AND scoring membership (no silent score change). Drop the in-fence `get_or_fetch`. Keep IN-fence: the `canonical_existing` re-read (@1920), `match_forward`, the INSERT, AND a cheap `SELECT id` exemplar re-read that emits a **#27 divergence audit** if the in-fence eligible-ID set != the snapshot (Codex R2: web/CLI write `pattern_exemplars` outside the lease -> <=1-run staleness, AUDITED not silent). Reuse detect Pass-1 `bars_by_ticker` for candidates (#5 no-re-fetch).
- **Locus #9 -- `_step_pattern_observe`** (runner.py:2628 fence wrapping `_bar_for_date`->`get_or_fetch` @2662/2525). Reorder: split the compute-pass (idempotency/shed/`_bar_for_date`/`_advance_status`/row-build) OUTSIDE the fence; the single fence wraps ONLY `insert_observation`. Preserve the shed/no-bar #27 warnings + the observe telemetry.
- **`_step_charts` is NOT a locus** (already fetch-outside-fence -- the target shape; do NOT change it).

## §2 LOCKed OQ resolutions (operator-paired 2026-06-06 -- propagate, do NOT re-open)
- **OQ-A** per-locus pre-fetch (each locus fetches its own bars just-before its write, not one bulk up-front pre-fetch).
- **OQ-B** REVERT the stopgap in the executing phase: DELETE the `[web] db_busy_timeout_ms = 5000` key + its TEMPORARY-STOPGAP comment block from `swing.config.toml` (single source of truth = `db.py` `DEFAULT_BUSY_TIMEOUT_MS = 30000`). Once the deadlock is gone, 30s is the correct safe value.
- **OQ-C** snapshot-authoritative exemplar membership (the §1 detect Pass-2 design).
- **OQ-D** BANK the daily-management yfinance-under-fence locus (#16) -- OUT of this arc (operator scope decision; NOT a deadlock, no Schwab audit write; tracked as a separate follow-up). Do NOT touch daily_management.
- **OQ-E** the in-fence observable-divergence guard (the #27 audit in §1 detect Pass-2).

## §3 Locks / invariants (propagate)
NO schema (v24); the **lease-fencing contract** (the WRITE stays inside `fenced_write` + the in-tx lease check; only the FETCH moves out); the **audit single-tx discipline** (untouched); #5 no-re-fetch / L2 LOCK (reuse Pass-1 bars); #27 silent-skip-audit (the divergence audit + any new early-return emits a warnings_json entry); #28/#29 exemplar OHLCV depth (the moved-out pre-fetch preserves window_days=400 / period depth); the lock-contention arc keepers (busy_timeout/serialized writer/telemetry) intact EXCEPT the stopgap config revert; ZERO `Co-Authored-By`; ASCII.

## §4 Test strategy (spec §7 -- discriminating; `feedback_regression_test_arithmetic`)
The binding one: an **in-process deadlock-reproduction test** -- a real file-backed SQLite DB + a cold spy that opens a 2nd connection and attempts `BEGIN IMMEDIATE` while the step runs; pre-fix the audit write deadlocks (fetch inside the fence), post-fix it does not (fetch moved out). Each repro test asserts the fetch path was exercised (`get_or_fetch` call-count >= 1 -- it only fires under seeded conditions: valid exemplar rows / non-idempotent-non-shed open detections). Plus: the snapshot-membership scoring test (a mid-run exemplar-row race does NOT lower a persisted composite score -> the divergence is audited, not silent); the observe compute-outside/insert-inside split test; the stopgap-revert test (cfg default == 30000; no [web] key).

## §5 Gate (binding)
1. fast suite green on the MERGED HEAD (isolate the 3 known xdist date-flakes per `feedback_no_false_green_claim`). 2. the deadlock-repro test green. 3. **operator-witnessed RE-RUN live gate** (post-merge; the SAME first-instrumented-live-run that FAILED at Run 92): a normal UNSEEDED `swing pipeline run --manual` MUST now show the `database is locked` fallback COLLAPSE (no `BEGIN IMMEDIATE FAILED` lines; Schwab becomes the primary source for the ~13-22 tickers) + the G2' lock-wait telemetry shows no long waits. The stopgap is reverted (busy_timeout back to 30000) so the gate also confirms the deadlock does NOT recur at the full 30s.

## §6 Dispatch metadata
- **Subagent:** `general-purpose`, foreground, harness-default model. **Worktree:** branch `fetch-vs-write-ordering-arc-writing-plans` from main HEAD = the commit that ADDS this brief (orchestrator states the SHA in the inline prompt). Writing-plans writes a PLAN (no code); you MAY read live tables `mode=ro`. SINGLE Codex chain to convergence. Leave the worktree INTACT at return.

## §7 Return report (mirror prior writing-plans returns)
Final HEAD + commits; Codex convergent verdict (cite `.copowers-findings.md`); plan line/task count; the 2-loci reorder reflected + the snapshot-membership + #27 divergence guard; the LOCKed OQ resolutions (incl. OQ-B stopgap revert as a task, OQ-D daily-mgmt OUT); the schema verdict (NONE); the gate enumerated (incl. the operator re-run live gate + stopgap revert); per-axis test-arithmetic (esp. the deadlock-repro); ZERO `Co-Authored-By`; worktree intact; executing-plans readiness.

---

*End of brief. Writing-plans for the fetch-vs-write-ordering fix: pre-fetch OHLCV OUTSIDE the `lease.fenced_write()` at the 2 confirmed loci (detect Pass-2 snapshot-authoritative exemplar membership + #27 divergence guard; observe compute-outside/insert-inside) + revert the busy_timeout stopgap to 30000. Charts unchanged; daily-mgmt #16 BANKED. NO schema (v24). The binding gate is the operator re-run live gate confirming the database-locked deadlock COLLAPSES. OUTPUT: an executing-ready plan.*
