# Phase 17 — 17-D.4: `-n auto` test-pollution hunt (INVESTIGATION-FIRST)

**Audience:** A fresh Claude Code instance, no prior context. A debugging task: find and fix a process-global test polluter that makes web-route tests fail nondeterministically under `pytest -n auto`. The mechanism is NOT yet diagnosed — **investigation comes first, the fix comes second, and the gate between them is DETERMINISTIC REPRODUCTION.** Single dispatch (not parallel).

**Mission:** Some test, when xdist co-locates it on the same worker as certain web-route tests, mutates a **process-global and does not restore it**, intermittently failing the co-located tests. Identify the exact polluter + the exact global, fix it so the failure is deterministically gone, and add a regression guard. Make the suite reliable again.

**Expected duration:** unbounded-ish (it's a hunt) — but the deterministic-repro gate keeps it honest. Budget a few hours.

---

## §0 Read first
- The **17-D.4 entry** in [`docs/phase17-todo.md`](phase17-todo.md) — the full provenance: nondeterministic (same commit → 8117 / 17-fail / 8117), the victims pass in isolation, the candidate polluters, and the "reproduce with `-n 0` + explicit ordering, NOT by re-running `-n auto`" mandate.
- **The two confirmed victim files** (both pass 23–31/N in isolation, fail intermittently under `-n auto`): `tests/web/test_routes/test_hyp_recs_expand_route.py` (the original) and `tests/web/test_routes/test_schwab_setup_route.py` (observed 2026-06-13 at the 17-D.3 + 17-D.5 merges). The victim set is "web-route tests that read the corrupted global" — there may be more.
- **Candidate polluters** (starting hypotheses — confirm empirically, don't assume): the schwab logging `logging.setLogRecordFactory` redaction wrapper; the `install_logging` composition root (Phase 16 Arc 2 — `swing/logging_setup.py` / `swing/logging_config.py` / `swing/log_correlation.py`); any module-level singleton or process-global mutated without teardown. CLAUDE.md §"Windows/tooling/test-discipline" documents the `-n auto` perturbs-worker-balance family + the `setLogRecordFactory` redaction global.
- CLAUDE.md §Gotchas on `setLogRecordFactory` (child-emitted records skip ancestor filters; the factory is a process-global) and the research-harness `del sys.modules` xdist-order fragility (a related-but-distinct family — note it, it may or may not be the culprit).

**Skill posture:** `superpowers:systematic-debugging` (rigid — follow it; form a hypothesis, find the smallest deterministic reproduction, bisect, confirm root cause, THEN fix). TDD for the fix (a regression test that DETERMINISTICALLY fails pre-fix). A light-to-moderate standalone `copowers:review` to convergence after the fix; persist responses to a gitignored `.copowers-findings.md`.

---

## §1 Known facts (don't re-derive)
- The failures are **nondeterministic under `-n auto`** and **absent under `-n 0`** (in-process) — classic process-global pollution surfaced by xdist worker placement, NOT a logic bug in the victim tests.
- The victim tests are temp-DB-isolated (`seeded_db`) + per-test `monkeypatch`, so their OWN setup is clean — the corruption comes from a CO-WORKER test on the same process that mutates a global and never restores it.
- 17-B's +43 tests shifted worker distribution and SURFACED this latent polluter; it is NOT a 17-B regression (the victim files predate it).

## §2 Investigation methodology (the gate is here)
1. **Do NOT chase it with `-n auto`** — it's nondeterministic; re-running proves nothing. Reproduce DETERMINISTICALLY:
2. Establish the victim's clean baseline: `python -m pytest <victim_file> -n 0 -q` → passes.
3. **Bisect for the polluter under `-n 0` with explicit ordering.** Run the victim file in the SAME in-process session as suspected co-worker files/tests, in order, e.g. `python -m pytest <suspect_file> <victim_file> -n 0 -q` (a global mutated by `<suspect>` and not restored will fail `<victim>` deterministically). Narrow by halving the candidate set (start from the logging/schwab/singleton candidates, but be willing to bisect the whole suite if needed — `pytest --co -q` to enumerate, then divide-and-conquer).
4. **Identify the EXACT global + the EXACT mutation site** (which test/fixture/module-import sets it, what it sets, why it's never restored). Name the precise process-global (e.g. `logging.getLogRecordFactory()` identity, a module attribute, an env var, a singleton instance).
5. **DETERMINISTIC-REPRODUCTION GATE (hard):** do NOT design or commit a fix until you can make the victim fail **deterministically** (a fixed `-n 0` command + ordering that reproduces it every run). A fix you can't first deterministically red is a plausible-but-wrong-mechanism risk (the Bug-2 failure family). State the exact reproduction command in your return.

## §3 The fix
- **Prefer fixing the POLLUTER (make it hermetic), not the victims.** A save/restore (fixture `yield` teardown, or `monkeypatch` of the global, or a context manager) at the mutation site closes the WHOLE class — every latent victim, not just the two observed. Making only `test_hyp_recs_expand_route` + `test_schwab_setup_route` resilient is a band-aid that leaves other latent victims (call that out if you must do it as a fallback).
- **Regression test:** add a guard that DETERMINISTICALLY fails on the old (polluting) behavior and passes on the fixed one — e.g. a test asserting the global is restored after the polluting test/fixture runs, or the deterministic victim+polluter ordering now passes. It must distinguish pre-fix from post-fix (no vacuous test — memory `feedback_regression_test_arithmetic`).
- If the root cause is the schwab `setLogRecordFactory` / `install_logging` global: the fix likely belongs in the test fixture that installs it (save+restore the factory), NOT in production code — but if a production composition root leaks a global without an idempotent reset, that's a legitimate (spec-scoped) fix; justify it.

## §4 Binding conventions
- **Worktree:** `git worktree add .worktrees/17d4 -b 17d4` from the repo root (the committed brief is present there); work entirely inside it; commit to the `17d4` branch; do NOT push or merge to main (the orchestrator merges). Your `.copowers-findings.md` lives at the worktree root.
- Conventional commits (`fix(...): 17-D.4 — ...` / `test(...): 17-D.4 — ...`); NO `Co-Authored-By`, NO `--no-verify`, NO amend; `git log -1 --format='%(trailers)'` empty.
- **R2 frozen-clock:** if you add a NEW date-touching test, pin the clock (you likely won't here).
- copowers:review from the worktree: pre-generate the diff on Windows (`git diff main...HEAD`) and pass it to Codex; tell Codex NOT to run git (worktree `.git` is unreachable from WSL).
- After the fix: run the fast suite. Because the bug is `-n auto`-nondeterministic, "green" means BOTH (a) your deterministic reproduction now passes, AND (b) several `-n auto` full runs show the victim files clean (run it 3+ times — if the polluter is truly fixed, the intermittent failures stop). Note honestly if any OTHER `-n auto` flake remains (there may be more than one polluter).

## §5 Adversarial review — watch items
- **Did the fix address the ROOT global (closing the whole class), or just paper over the two observed victims?** This is the primary watch item.
- Is the deterministic reproduction real (a fixed command that reds pre-fix), or did the implementer rely on `-n auto` luck?
- Does the regression test distinguish pre-fix from post-fix (run it against the unfixed code mentally/actually)?
- Did the fix avoid changing production logging/redaction behavior (the schwab redaction factory is a security control — a test-fixture save/restore must NOT weaken the production redaction; see CLAUDE.md schwab redaction gotcha)?

## §6 Done criteria + GATE
- The exact polluter + global identified; a deterministic reproduction documented (the fixed `-n 0` ordering command); the fix makes it deterministically pass; a non-vacuous regression guard added.
- Fast suite green; 3+ `-n auto` full runs show the victim files clean (report the counts honestly — if a residual flake remains, say so + characterize it); ruff clean; trailers `[]`.
- `copowers:review` converged (responses persisted).
- No production redaction/logging behavior weakened.

## §7 Return report (final chat message ONLY)
Report: worktree path (`.worktrees/17d4`) + branch (`17d4`) + commit SHA(s); the ROOT CAUSE (exact polluter test/fixture/module + exact global + why it wasn't restored); the DETERMINISTIC reproduction command (pre-fix red); the fix (hermetic-at-polluter vs victim-resilient, with rationale); the regression test + proof it distinguishes pre/post-fix; the `-n auto` re-run results (3+ runs, honest counts); the `copowers:review` verdict + persisted-findings path; confirmation production redaction is unchanged. Do NOT post to the mailbox or any director.
