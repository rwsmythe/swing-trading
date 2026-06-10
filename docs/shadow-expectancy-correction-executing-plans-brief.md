# Shadow-Expectancy Entry/Join Correction — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance, no prior conversation context.
**Mission:** Execute the Codex-converged 7-task correction plan — EDIT the shipped shadow-expectancy harness so it prices live signals instead of routing 100% to `no_canonical_detection`. This is a **correction to ALREADY-SHIPPED code**, not a greenfield build.
**Prepared:** 2026-06-09 by the orchestrator/evaluator instance.
**Expected duration:** ~1 session (7 TDD tasks + a Codex adversarial pass to convergence).

---

## 0. Read first (in order)

1. `CLAUDE.md` — conventions: conventional commits; **NO Claude co-author footer; NO `--no-verify`; no amend**; TDD; the Windows/ASCII gotchas; **"Synthetic-fixture-vs-production-emitter shape drift"** (the bug this corrects — do not reintroduce it).
2. **The PLAN — `docs/superpowers/plans/2026-06-09-shadow-expectancy-entry-join-correction.md`** (Codex-converged, `b59541c7`). This is your authoritative, task-by-task spec: 7 TDD tasks with real test+impl code, the explicit test **deletions**, and the mandated real-emitter fixtures. Execute it in order.
3. **The correction spec — `docs/superpowers/specs/2026-06-09-shadow-expectancy-entry-join-correction-design.md`** (`6fd664f7`) — the WHY (§5 edit map, §9 supersede/preserve ledger, §8 re-runnable live-DB verification queries).
4. **The shipped code you will edit** — `research/harness/shadow_expectancy/{collapse,run,validate,constants,funnel,scorecard,output}.py`, `tests/research/shadow_expectancy/`, and the `diagnose` group in `swing/cli.py`. The PRESERVED modules (`simulator.py`, `bracket.py`, `attribution.py`, `exceptions.py`) are off-limits except as the plan specifies.

**Skill posture:** invoke `copowers:executing-plans` (wraps superpowers:subagent-driven-development + an adversarial Codex review run to convergence). Use `superpowers:using-git-worktrees` for isolation. Invoke `superpowers:verification-before-completion` before declaring done.

---

## 1. Workflow

- **Isolated worktree** branched from **`main` HEAD** (carries the plan + spec). Do NOT commit to `main`; the orchestrator performs the merge after QA. Note: `main` may advance during your work (parallel Phase-16 effort) — that's fine; the orchestrator handles the 3-way merge.
- **Correction TDD rhythm** per the plan: rewrite/extend the test to the NEW contract → run it, see it FAIL against the shipped code → make the §5 edit → see it PASS → commit. **DELETE the obsolete tests** the plan names (pivot-match canonical, `no_canonical_detection`, `inconsistent_trigger_state`, the tick tests) — don't leave them. Use the plan's commit messages.
- **After all tasks land:** run the copowers Codex review **to convergence** (`NO_NEW_CRITICAL_MAJOR`; round cap suspended). **Persist each Codex RESPONSE** to a gitignored on-disk file (append under `.copowers-findings.md`). **Tell Codex to VERIFY the load-bearing claims against the shipped code AND the live DB** (spec §8 gives the queries) — that discipline is what made the original engine ship a false premise; do not skip it.

---

## 2. Hard constraints — LOCKS

- **Surgical.** Edit ONLY the plan's surface: `collapse.py`, `run.py`, `validate.py`, `constants.py`, `funnel.py` (consumes the new vocab), the additive `entry_bar_weak_close` in `scorecard.py`/`output.py`, the affected tests/fixtures, and `swing/cli.py`. **Do NOT touch** `simulator.py`/`bracket.py` math, the censoring/scorecard expectancy/Wilson math, or the funnel two-level structure. If a change tempts you outside this surface, STOP and flag it.
- **L2 LOCK:** the only `swing/` change is `swing/cli.py` (the `_ensure_research_importable` helper + its call sites). **No new `swing/` files.**
- **No schema change** (v25 holds; the harness stays a `mode=ro` read-only consumer). `testkit` stays at v24 by design (the harness reads nothing v25 added) — the plan does not touch it; leave it.
- **No new production dependency / no forbidden imports** in the harness (`yfinance`/`schwabdev`/`swing.integrations.schwab`/`swing.data.ohlcv_archive`); the L2-lock import-safety test stays green.
- **Conventions:** conventional commits; **NO Claude co-author footer; NO `--no-verify`; no amend.** Verify `git log -1 --format='%(trailers)'` is `[]` (keep the final `-m` paragraph plain prose so git parses no trailer).
- **Fast suite green** on the worktree head (baseline ~7504 on `main`; **trust live pytest output, re-run on the head, don't hardcode counts**).
- **The Task-3 coupling is expected, not a bug to "fix":** Task 3 edits `collapse.py` + `run.py` together (the `collapse_detections` signature drop is atomic across both) and pulls the one-line `ShadowTrade.entry_bar_weak_close` field forward from Task 4 so the run-loop rewrite stays self-consistent. The plan documents this. Each task ends with its targeted tests green; Task 7 confirms the full fast suite. Follow it as written.

---

## 3. Watch items (Codex-resolved subtleties — implement faithfully, the plan encodes them)

- **`inconsistent_detection_series` is a STRICT date-prefix gate, not overlap-only** — a gappy chain (`A=[d1,d3]` vs `B=[d1,d2,d3]`) MUST be excluded. Keep the strengthened invariant + its test.
- **Zero-forward-depth → `insufficient_forward_depth`** — a trigger on the LAST bar excludes per-hypothesis and `simulate` is **never** called with empty `forward_bars`. Keep the "simulator not invoked" assertion.
- **`no_candidate_pivot` is split from `invalid_ohlc`** (pivot `None`/`<=0` → `no_candidate_pivot`, per-hypothesis; bad bars → `invalid_ohlc`).
- **`entry_bar_weak_close` is annotation-only** — no behavior change; the trade still prices identically.
- **No-look-ahead fixture invariant** = `data_asof_date < observation_date` (NOT "after detection_date"; the first obs is on detection_date). The verification query JOINs `pattern_forward_observations` to `pattern_detection_events` on **`detection_id`** (the PK — Codex caught a prior `e.id` typo); keep it correct.
- **The invocation guard is grep-enforced** across ALL 8 `diagnose`-group `from research.harness` import sites; the importability test asserts `sys.path[0]` directly, prunes cwd-equivalents, and requires a non-empty absolute root that actually contains `research/harness` (don't let it false-pass off the `sys.modules` cache or `sys.path[0]==""`).
- **Real-emitter fixtures only** — `detection.pivot != candidate.pivot`, per-pattern `0.0` for cup/dbw; the BULZ run-89 golden (→ `never_triggered`), a breakout fixture priced end-to-end (hand-verified bracket realistic −2.0 / favorable −1.0), the mixed-first-trigger fixture. Never force the two pivots equal.

---

## 4. Codex transport (this machine)

MCP `codex` tools are dead in the VS Code extension. Drive via WSL CLI:
```
wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C "<WSL_ROOT>" - < "<WSL_ROOT>/.copowers-review-prompt.txt"'
```
- PATH-prefix export REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`; round 2+ via `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check`.
- A worktree's `.git` is a file **unreachable from WSL** → pre-generate the diff on the Windows side, pass `--skip-git-repo-check`, and tell Codex in the prompt to review the provided diff/files and NOT run any `git` command.
- **Re-sync the review copy before each round** (a stale `.copowers-review-*.md` copy caused a false-alarm round in writing-plans — copy the canonical doc fresh each round).

---

## 5. Done criteria + return report

- All 7 tasks landed (≥1 commit each), in plan order, with the obsolete tests deleted.
- copowers Codex review **converged** (`NO_NEW_CRITICAL_MAJOR`); every round's response persisted.
- **Fast suite green on the worktree head** (re-run + read the real result).
- `swing diagnose shadow-expectancy --db <live>` runs from the installed entry point **without `PYTHONPATH`** (the invocation fix) and routes live signals honestly (never_triggered / open-at-horizon / per-hypothesis exclusions — **not** 100% `no_canonical_detection`); the breakout golden fixture prices end-to-end.
- **L2 LOCK preserved** (only `swing/cli.py` in `swing/`); no schema change (v25); `ruff check` clean; zero co-author trailers.
- **Do NOT merge to `main`** — return for orchestrator QA + merge. No live-DB/operator-browser gate for this arc (read-only research, no schema).
- Return report: commits (worktree branch), files touched, tests before/after, the Codex verdict + persisted-transcript path, deviations (signatures that differed from the plan), L2 confirmation, and any open questions.

---

## 6. If you get stuck

- The plan's task code is authoritative; if a shipped signature DIFFERS from the plan (the codebase may have moved), implement against reality and FLAG it in the return report — don't silently diverge.
- If a golden-walk numeric doesn't match, recompute the hand-arithmetic under BOTH the pre/post paths to confirm the test discriminates (don't relax the assertion).
- If a Codex finding seems wrong, push back with reasoning (`superpowers:receiving-code-review`) — but the plan was hardened through 4 rounds against live data, so most contract questions are settled in it.
