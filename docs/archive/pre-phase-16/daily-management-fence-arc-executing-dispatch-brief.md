# Executing Dispatch Brief — Daily-Management Network-Under-Fence (#16) Fetch-Hoist

**Arc:** Phase 15 / B-family operational hardening — the daily-management network-under-fence fix (`#16`), fetch-hoist. THIRD + final copowers stage.
**Cycle stage:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`; adversarial Codex review after ALL tasks land, run to convergence).
**Authoritative script (LOCKED, merged):** [`docs/superpowers/plans/2026-06-07-daily-management-fence-fetch-hoist-plan.md`](superpowers/plans/2026-06-07-daily-management-fence-fetch-hoist-plan.md) — EXECUTE IT TASK-BY-TASK. The plan has every code block, test, and commit message. Spec: [`docs/superpowers/specs/2026-06-07-daily-management-fence-archive-api-split-design.md`](superpowers/specs/2026-06-07-daily-management-fence-archive-api-split-design.md).
**Branch-from:** main HEAD at worktree creation (currently `2c61408e`; re-verify with `git log --oneline -3`).
**Schema:** NONE — v24 holds. Zero migrations.
**No isolated venv needed** — this arc touches only `swing/pipeline/runner.py` + `swing/trades/daily_management.py` + tests; it does NOT re-pin any shared user-site dependency (the isolated-venv discipline applies only to schwabdev-class shared re-pins).

---

## 1. Mandate (one line)

Execute the 5-task plan: make `compute_daily_approximate_snapshot` a pure compute returning `SnapshotComputeResult(fields, miss_reason)`, hoist the `read_or_fetch_archive` warm OUTSIDE the per-trade `lease.fenced_write`, add the `expected_ticker` guard + the #27 audited-skip funnel — so no network I/O runs under the daily-management write lock. Ship it TDD, green-per-commit, Codex-converged.

The plan is the script. Do not redesign. Where the plan says "byte-unchanged downstream of the `df` assignment," keep it byte-unchanged.

---

## 2. STEP 0 — re-ground (the plan's pre-flight, §"Pre-flight: re-confirm anchors")

Before Task 1, on your worktree HEAD, re-confirm the line anchors in the plan's pre-flight list (they were grounded on `a460961c`; only doc commits landed since, so they should hold — verify, don't assume). The orchestrator already disk-verified these load-bearing facts (you can trust them, but re-confirm at your HEAD):
- `compute_daily_approximate_snapshot` @daily_management.py:465; lazy `read_or_fetch_archive` import @503, call @510; lazy `from swing.data.repos.trades import get_trade` @503-504 (the ticker-guard test patches THIS source module, not a daily_management attribute).
- `_step_daily_management` @runner.py:3774; per-trade fence @3810; the REAL call site @runner.py:837 (currently does NOT pass `run_warnings`).
- `run_warnings` created @runner.py:815, serialized @1022, param-precedent `_step_pattern_observe(*, …, run_warnings)` @2663.
- Test fixture `synthetic_lease_and_trades` @tests/pipeline/test_daily_management_step.py:59 seeds DHC (trade 1, `managing`) + ZZ (trade 2, `entered`) as OPEN + VIR (trade 3, `closed`, excluded by `list_open_trades`) → the plan's `len(run_warnings) == 2` assertions are correct. `_seed_trade` is module-level @:15. `Trade` is `@dataclass(frozen=True)` (so `dataclasses.replace(t, ticker=…)` works in the ticker-guard test).

---

## 3. Execution disciplines (binding)

- **Task-by-task, TDD, green-per-commit.** Each task: write/migrate the failing test → run + SEE it fail (or, for Tasks 3-4, see it pass as honestly-labeled post-fix regression-locking) → minimal impl → run + SEE it pass → `ruff` → commit (conventional, NO `Co-Authored-By`, NO `--no-verify`, final `-m` paragraph plain prose).
- **Task 1 is ATOMIC** — the breaking signature/return change + its sole runner caller + ALL affected test migrations (6 service callers + the 2 step `compute_*` stubs + the fixture monkeypatch target + the walkthrough monkeypatch) land in ONE commit. Do not split it, or intermediate commits go red.
- **The two-namespace patch traps (do not get these wrong):** (a) the gold-standard lock-hold test (Task 3) patches BOTH `swing.data.ohlcv_archive.read_or_fetch_archive` (pre-fix lazy import) AND `swing.pipeline.runner.read_or_fetch_archive` (post-fix warm) with the same spy; (b) the ticker-guard test (Task 4) patches `swing.data.repos.trades.get_trade` (the lazy-import SOURCE), NOT a `swing.trades.daily_management` attribute (which would silently no-op).
- **`miss_reason` root-cause-wins** (Task 2): when the warm pre-set `warm_raised`/`warm_empty_or_stale`, the runner KEEPS it and does NOT overwrite with `res.miss_reason`; the typed return is authoritative for the in-fence cause only when the warm succeeded (`miss_reason is None`). The Task-4 overlap test locks this.
- **Gold-standard discrimination** (Task 3): the test lands post-fix (green on the committed tree); witness RED by TEMPORARILY restoring the in-fence fetch (revert only the Task-1 hoist) + re-running → `lock_observed` flips True. The test body omits `run_warnings` (optional) so it is callable against the pre-fix signature too. Per `feedback_regression_test_arithmetic`, confirm each test's EXACT value distinguishes pre/post.
- **Re-run the §2 in-fence audit** (Task 5 Step 3): grep `runner.py` for `read_or_fetch_archive`/`get_or_fetch` and confirm NONE sits inside a held `fenced_write` (locus #16 → ✅).
- **Full fast suite + ruff at the end** (Task 5 Step 4): `python -m pytest -m "not slow" -q` (baseline ≈7223 — report the ACTUAL count) + `ruff check swing/`. Isolate the 3 known xdist co-residency flakes if they appear (`test_ohlcv_reader_re_export_identity`, `test_read_cohort_csv_against_committed_v2trf`, `test_prices_refresh_uses_pipeline_eval_anchor` — pass `-n0`).
- **Degraded-harness guard** (`feedback_degraded_harness_sequential_tool_calls`): if you hit mid-batch tool cancellations, drop to single sequential tool calls + re-Read before each Edit + verify each commit; a failed call invalidates read-state and silently breaks later Edits.

---

## 4. copowers Codex review (after ALL 5 tasks land)

- **Run the adversarial Codex loop to convergence** (zero new crit/major / `NO_NEW_CRITICAL_MAJOR`; the 5-round cap is SUSPENDED). Review the FULL diff of all 5 commits against the plan + spec.
- **Codex transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Worktree `.git` unreachable from WSL — pre-generate the diff on Windows (e.g. `git diff main...HEAD > .codex-diff.txt`) + tell Codex not to run git.
- **Persist BOTH prompts AND responses** of every round (incl. the final `NO_NEW_CRITICAL_MAJOR`) to gitignored `.copowers-findings.md` for independent orchestrator convergence-confirmation at QA.
- If Codex surfaces a real crit/major, fix it (new TDD commit), re-run the suite, re-review. Scrutinize any REBUTTAL of a Codex finding against disk before standing on it.

---

## 5. Locks / invariants (do not regress — full list in plan §"Locks / invariants" + spec §6)

Schema NONE (v24); `read_or_fetch_archive` byte-identical (all 9 consumers untouched; `SnapshotComputeResult` lives in `swing.trades.daily_management`, NOT a new archive symbol); `LeaseRevokedError` re-raises from the per-trade loop; session-anchor `asof_session = last_completed_session(run_now)` not moved; `upsert_snapshot` idempotency + `entered → managing` in-fence; F6 transient-empty preserved (warm reuses `read_or_fetch_archive` unchanged); completed-day barrier + busy_timeout=30000 + serialized audit_conn + G2′ telemetry untouched; `trail_MA_period_days_default` name+N803 + the `PLR0913` noqa preserved. **NOT reconciliation hardening** (the `trades.ticker`-mutable gap is banked for a future arc — defend only via `expected_ticker`).

---

## 6. Return report (then STOP — do NOT merge)

Return to the orchestrator: the 5 commit SHAs + messages; the full-fast-suite result (ACTUAL pass count + any isolated flakes); `ruff` clean; the Task-5 in-fence-audit grep result (confirming locus #16 → ✅); the Codex convergence verdict (round count + the final `NO_NEW_CRITICAL_MAJOR` line); and any deviation from the plan (with justification). Then STOP. Merge is the orchestrator's action after QA. Do NOT merge, do NOT push to main.

**Operator gate note (surface to the orchestrator):** this is a pipeline-internal fence-ordering refactor with NO operator-visible surface change (no UI/HTMX/schema), so there is no browser gate. The gold-standard lock-hold test reproduces the mechanism in-process. An OPTIONAL confirming live `swing pipeline run` (witnessing daily-management snapshots still land + no `database is locked` warm degrade) is the operator's call — lower-severity than the deadlock's Run-93 gate since #16 is a latent lock-hold, not a deadlock.
