# Shadow-Expectancy Engine — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance, no prior conversation context.
**Mission:** Execute the Codex-converged 17-task implementation plan to build the shadow-expectancy engine — a read-only research harness that forward-walks every emitted temporal-log signal through one fixed mechanical ruleset to a realized R, surfaced via one new `swing diagnose shadow-expectancy` CLI subcommand.
**Prepared:** 2026-06-09 by the orchestrator/evaluator instance.
**Expected duration:** 1–2 sessions (17 TDD tasks + a Codex adversarial pass to convergence).

---

## 0. Read first (in order)

1. **`CLAUDE.md`** — project conventions: conventional commits; **NO Claude co-author footer; NO `--no-verify`; no amend**; TDD discipline; fast-suite-must-stay-green; Phase isolation; the Windows/ASCII gotchas.
2. **The PLAN — `docs/superpowers/plans/2026-06-09-shadow-expectancy-engine.md`** (Codex-converged at commit `2ee03c1b`). This is your authoritative, task-by-task spec: 17 TDD tasks, each with REAL failing-test code → exact pytest command + expected failure → REAL minimal implementation → expect-PASS → commit. Read it COMPLETELY before starting.
3. The PLAN's top sections **"Spec ambiguities resolved"** + **"Reuse-target signatures that DIFFER from a naive spec reading"** — these are the load-bearing interpretation calls. They are Codex-converged; **do NOT re-litigate them** (§3 below lists the ones to implement faithfully).
4. **The SPEC — `docs/superpowers/specs/2026-06-08-shadow-expectancy-engine-design.md`** — for the WHY (locked decisions D1–D12, the simulator semantics §5, the funnel contract §7). The plan implements the spec; where they ever differ, the plan's grounded resolution wins (it was checked against real source).
5. **The precedent harness — `research/harness/minervini_primary_base_recall/`** + `tests/research/minervini_primary_base_recall/` — MIRROR its structure: the L2-lock test (hardened `sys.modules`), the `swing diagnose` CLI registration, the output writers (results/per_session CSV + summary.md + manifest.json) with the `_assert_ascii` guard, and the `.gitignore` output allowlist.

**Skill posture:** invoke **`copowers:executing-plans`** (wraps `superpowers:subagent-driven-development` + an adversarial Codex review run to convergence). Use `superpowers:using-git-worktrees` for isolation (see §1). Invoke `superpowers:verification-before-completion` before declaring done.

---

## 1. Workflow

- **Isolated worktree:** work in a fresh git worktree branched from **`main` HEAD** (which carries the plan at `2ee03c1b`). Do NOT commit to `main` directly; the orchestrator performs the merge after QA.
- **Task-by-task TDD** per the plan: failing test → see it fail (run the exact pytest command, confirm the expected failure) → minimal real implementation → see it pass → commit. **One commit per task minimum**; use the plan's commit messages (conventional; no co-author footer).
- **After all 17 tasks land:** run the copowers adversarial **Codex review to CONVERGENCE** — iterate until `NO_NEW_CRITICAL_MAJOR`. The 5-round cap is **suspended** for this project; keep going while crit/major surface, don't pad after convergence.
- **Persist each Codex RESPONSE** (verdicts/findings + the final `NO_NEW_CRITICAL_MAJOR` line), not just prompts, to a gitignored on-disk file (e.g. append under the existing `.copowers-findings.md`) so the orchestrator can independently confirm convergence at QA.

---

## 2. Hard constraints — LOCKS (do not violate)

- **L2 LOCK — the ONLY `swing/` change is the CLI registration** of `swing diagnose shadow-expectancy` in `swing/cli.py` (one command, deferred import of the harness `run_harness`). Everything else lives under `research/harness/shadow_expectancy/`, `tests/research/shadow_expectancy/`, `research/studies/`, `research/method-records/`, and `.gitignore`. **If you find yourself editing any other `swing/` file, STOP and flag it** in the return report — do not broaden the lock.
- **NO schema change** (v24 holds). The harness is a **READ-ONLY consumer** of the v22 temporal log — open the DB with `sqlite3.connect(<uri>?mode=ro, uri=True)`. No writes, no migration.
- **NO new production dependency, no forbidden imports.** Reuse only the pure-leaf production functions named in the plan's reuse matrix. The harness must NOT import `yfinance`, `schwabdev`, `swing.integrations.schwab`, or `swing.data.ohlcv_archive` at module scope — the L2-lock test (Task 14) enforces this; keep it.
- **Conventions:** conventional commits; **NO Claude co-author footer; NO `--no-verify`; no amend.** Verify `git log -1 --format='%(trailers)'` is `[]` before finishing (keep the final `-m` paragraph plain prose so git doesn't parse a trailer).
- **TDD is binding.** The plan's tests ENCODE the writing-plans-review fixes — do NOT "simplify" them away: `initial_stop = entry_bar.low` (not candidate.initial_stop); the **fixed-denominator** multi-leg R (`Σ realized_pnl / (rps × initial_shares)`, NOT per-leg); the **four** censoring-scenario means including closed trades; the **whole-group** canonical-detection collapse; and the **airtight** `build_funnel` contract (raises on every malformed `SignalOutcome` on both the unattributed and attributed sides) + the reconciliation invariant.
- **Windows / ASCII:** ASCII-only in any CLI/`print`/`click.echo` path (Windows cp1252 stdout raises `UnicodeEncodeError` in production even when `capsys` masks it in tests). The output writers' `_assert_ascii` guard is load-bearing — preserve it. Quote Drive paths.
- **Fast suite green:** `python -m pytest -m "not slow" -q` must stay green (baseline ~7376 on `main`, 2026-06-09). **Trust live pytest output; do not hardcode counts** in assertions, and re-run on the worktree head before claiming green (never carry a count forward).

---

## 3. Watch items — the plan's load-bearing calls (implement faithfully, don't re-derive)

- **Advisory reuse is NOT a function call.** `swing/trades/advisory.py`'s `suggest_breakeven` / `suggest_trail_ma` / `suggest_exit_close_below_ma` / `suggest_maturity_stage_trail_ma_hint` are **message-emitters** that take a production `Trade` + DB-backed `AdvisoryContext`. The simulator **reimplements** the management decisions as a pure state machine, reusing only the **thresholds** (`StopAdvisoryConfig.breakeven_r_trigger=1.0`; the `≥+2R→10MA else 20MA` maturity staging from `advisory._MATURITY_STAGE_TRAIL_MA`), the `equity.r_so_far` formula, and `derived_metrics` R-math. The **anti-drift tests import those production constants** and assert the harness constants equal them — keep them.
- **Candidate join path:** `detection.pipeline_run_id` → `pipeline_runs.evaluation_run_id` → `fetch_candidates_for_run(conn, eval_run_id)` filtered by ticker. **`fetch_candidates_for_run`'s `run_id` is an `evaluation_runs.id`, NOT a `pipeline_run_id`.** A missing link → `no_candidate_join` (unattributed); a candidate present but no detection pivot matches → `no_canonical_detection` (unattributed).
- **Entry** = the canonical detection's FROZEN first `triggered_open` forward observation (no recompute, no look-ahead); the detection pivot lives in `structural_anchors_json → evidence.pivot_price`; `entry_fill = max(detection.pivot, entry_bar.open)`; `initial_stop = entry_bar.low`.
- **Funnel contract:** the single `unattributed` bucket reports a per-reason breakdown (`no_candidate_join`, `matched_no_hypothesis`, `multi_match`, `no_canonical_detection`, `inconsistent_detection_series`, `inconsistent_trigger_state`); `invalid_ohlc`/`degenerate_risk` on an attributed signal are PER-HYPOTHESIS; `build_funnel` raises on any malformed outcome; the reconciliation invariant `Σ(unattributed reasons) + Σ(per-hypothesis terminals) == unique_signals` holds and is tested.
- **Hypotheses are already seeded** (migration 0008); read the active registry via `list_hypotheses(conn, status_filter='active')` — do NOT re-seed.

---

## 4. Codex transport (this machine)

The MCP `codex`/`codex-reply` tools are **dead in the VS Code extension** (1s deadline). Drive Codex via the **WSL CLI**:
```
wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C "<WSL_ROOT>" - < "<WSL_ROOT>/.copowers-review-prompt.txt"'
```
- The PATH-prefix export is REQUIRED (bare `codex` resolves the dead Windows npm shim). Liveness probe: `codex --version` → `codex-cli 0.135.0`.
- A **worktree's `.git` is a file unreachable from WSL** → pre-generate the diff on the Windows side, pass `--skip-git-repo-check`, and tell Codex in the prompt to review the provided files/diff and NOT run any `git` command.
- Round 2+ continue the thread via `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check`.

---

## 5. Done criteria

- All 17 plan tasks landed (≥1 commit each), in plan order.
- copowers Codex review **converged** (`NO_NEW_CRITICAL_MAJOR`); every round's response persisted on disk.
- Fast suite green **on the worktree head** (re-run + read the real result).
- `swing diagnose shadow-expectancy --help` registers; the end-to-end `test_run` exercises the harness over a synthetic in-memory temporal-log DB and the reproducibility test passes.
- **L2 LOCK preserved** (the only `swing/` change is the CLI registration); no schema change (v24); `ruff check` clean; zero co-author trailers.
- Return report per §6. **Do NOT merge to `main`** — return for orchestrator QA + merge. There is no live-DB / operator browser gate for this arc (read-only research, no schema, no deadlock surface).

---

## 6. Return report format

```
## Shadow-expectancy engine executing-plans — return report
### Commits landed (worktree branch <name>)
- <SHA> <task 1 commit subject>
- ... (one+ per task) + any Codex-fix commits
### Files created/modified
- research/harness/shadow_expectancy/*.py (list)
- tests/research/shadow_expectancy/*.py (list)
- swing/cli.py (the ONE swing/ change — CLI registration)
- .gitignore (output allowlist) ; research/studies/ + research/method-records/ docs
### Tests
- Before: <baseline> passing ; After: <N> passing, 0 failing ; new tests: <count>
### Adversarial review
- Verdict: <NO_NEW_CRITICAL_MAJOR after R rounds> ; responses persisted at <path>
- Totals: <C crit / M major / m minor, all resolved/accepted>
### Locks + hygiene
- L2: only swing/ change = CLI registration (confirm) ; schema: v24 unchanged ; ruff clean ; trailers []
### Deviations from the plan (signatures that differed from reality, etc.)
- <empty if none>
### Open questions for orchestrator
- <empty if none>
```

---

## 7. If you get stuck

- The plan's task code is authoritative. If a real production signature DIFFERS from what the plan shows (the codebase may have moved since the plan was Codex-verified), implement against reality and **flag the divergence** in the return report — don't silently diverge.
- If a golden-walk numeric doesn't match, recompute the hand-arithmetic under BOTH the pre-fix and post-fix paths to confirm the test discriminates (don't just relax the assertion).
- If a Codex finding seems wrong, push back with reasoning (read `superpowers:receiving-code-review`) rather than mis-applying — but the plan was already hardened through 6 rounds, so most contract questions are settled in it.
