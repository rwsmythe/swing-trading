# D87 -- suite load-robustness rider: executing ledger

Brief: `docs/d87-load-robustness-dispatch-brief.md` (main `9845b799`). Worktree
`.worktrees/d87-load`, branch `d87-load`, base `9845b799`. Tests only.

Status at this commit: mechanisms 2 and 3 fixed and committed. Items 1, 5, 6,
7, 8 and 9 are STOPPED as forks (section 4); Reviewer A has not run (no
counted rounds yet), because the review must cover the final tree.

## 1. Load harness (as run)

- Saturator: `scratchpad/d87/saturator.py`. One busy-loop process per CPU
  (16). The brief's one-liner uses a `lambda` target, which cannot pickle
  under Windows spawn, so the saturator is a module-level function behind
  `__main__`, and every child has a hard self-deadline. Every run was KILLED
  by PID afterwards and verified (`remaining: 0`, no stray
  `saturator|multiprocessing` python process).
- Roster runs: the roster nodes (section 2) plus all of
  `tests/scripts/test_weeknight_wrapper.py`: 23 tests, `-n 16`, under the
  saturator, 10 iterations.
- Targeted stress: one file repeated with `--keep-duplicates` (32 copies),
  `-n 16`, under the saturator. `--keep-duplicates` does NOT duplicate
  parametrized node ids, so the file form plus `-k` was used where needed.
- Full suite under the saturator, PRE-fix (base `9845b799`), `-n 16
  --durations=0`: **15498 passed, 13 skipped, 0 failed in 3264.03 s**. Zero
  roster reds that run; the per-test call durations are used in section 4.
- Foreign load during the session, not controllable: a coa-chess `pytest -n 8`
  and clearwater witness processes ran intermittently. The orchestrator's
  D79 `-n 8` run in the main checkout was waited out before the first load
  run (it finished 15498 passed).

## 2. Per-test classification (by read)

| # | Test | Mechanism | Lines read |
|---|---|---|---|
| 1 | `test_l2_lock_sys_modules_isolation_regression.py::test_research_l2lock_del_does_not_break_web_route_exception_identity` | (1) child budget | `:69-78` `subprocess.run([... pytest ... -n 0 ...], timeout=300)`; asserts `proc.returncode == 0` at `:91` |
| 2 | `test_ladder_stress_production_path.py::test_forced_start_lock_leaves_no_audit_row` | (2) unsynchronised holder | pre-fix `:82-84` holder `start()` then `time.sleep(0.05)`; holder `:69-71` `BEGIN IMMEDIATE` then `release_evt.wait(timeout=2.0)` |
| 3 | `...::test_forced_finish_lock_leaves_in_flight_row` | (2) | pre-fix `:114-116` holder spawned in `_on_http`, `time.sleep(0.1)` |
| 10a | `...::test_post_fix_30s_all_attempts_complete` (sibling) | (2), shares the defect by read: `:146-148` `time.sleep(0.05)` "ensure the holder owns the lock first". Never reds; it passes VACUOUSLY when the holder is late (no contention, so no drain is exercised) | included |
| 4 | `test_schwab_setup_cli.py::test_setup_auth_failure_audit_status_and_sentinel_redaction` | (3) order-dependent sentinel | `:259-263` the sentinel is built by the test and never registered; `swing/integrations/schwab/client.py:116-128` only Layer 0 (the registry) can redact it, because the underscores break both Layer-1 regexes; `tests/conftest.py` docstring named the dependency on a sibling happy-path test |
| 5 | `test_diagnose_subcommands.py::test_diagnose_aplus_sensitivity_stdout_is_ascii_safe` | (1) child budget, timeout 120 | `:225-233` |
| 6/7 | `test_22a2_cohort_readers.py::test_a2_94[admit]`, `::test_a2_95[admit]` | **FITS NONE (fork F2)** | the test has no child budget. `_named_page` `:386-408` GETs a page whose replay runs under the PRODUCTION `WEB_REPLAY_BUDGET_SECONDS = 2.0` (`swing/trades/frozen_value_evidence.py:199`; deadline read at `:404`, `:1504`, `:1524`); the admit state asserts `"tier-2" not in html` (`:406`) |
| 8 | `test_aplus_v2_ohlcv_run.py::test_subprocess_aplus_sensitivity_v2_help_cp1252_safe` | (1) child budget, timeout 60 | `:448-452` |
| 9 | `test_weeknight_wrapper.py::test_run_stub_skip_exits_zero` | (1) by read: the only timing dependence is `_ps_file`'s `timeout=120` (`:33-38`); the wrapper's own bound is 45 minutes. Fork F1 (see 4.1) | `:129-141` |

Siblings checked and NOT included: the other `test_weeknight_wrapper.py`
tests share `_ps_command`/`_ps_file` and so the same 120 s budget (they ride
with item 9's ruling); `test_aplus_v2_ohlcv_run.py:650` is env-gated off;
`test_schwab_setup_cli.py`'s other tests either register their own tokens
(happy paths) or assert no sentinel; no other test in the L2 or diagnose file
spawns a child.

## 3. Mechanisms 2 and 3: fixed

### 3.1 Mechanism 2 (commit `49344b6c`)

- Fix: `_external_lock_holder` takes a `held` event and sets it only after
  `BEGIN IMMEDIATE` returns; each test waits on it (`_wait_held`, 60 s,
  asserting) before the contended write, and the start-lock test opens its
  1 ms connection only after that wait. The pre-fix holders hold until the
  test releases them (`_PRE_FIX_HOLD_BOUND = 30.0`, a hang guard). The 1 ms
  `busy_timeout` is unchanged. The post-fix sibling gets the same wait and
  keeps its 0.5 s hold. The finish test now joins its holder.
- One extension, flagged for challenge: the hold bound moved 2.0 s -> 30 s.
  CHARC's form names only the late-holder race; a holder that releases on
  its own 2 s timer before a loaded main thread reaches the audit write is
  the same race from the other side, so the pre-fix holders now release on
  the test's signal.
- Reproduction, PRE-fix, under the saturator: finish-lock **red 3 of 10**
  roster iterations, **red 6 of 64** targeted (two 32-copy runs, 3 each),
  all `DID NOT RAISE <class 'sqlite3.OperationalError'>`. Start-lock: 0 of
  10 roster, 0 of 64 targeted (it red in D79's first merged-head run,
  `merged-head-suite.txt:402`).
- Mutations (plugin `scratchpad/d87/mut/d87_mut_ladder.py`, loaded with
  `-p`, no tracked file edited), on the FIXED tests, `-n 0`:
  - `wait_start` (record_call_start sets busy_timeout 30 s first, the
    post-fix shape the test's arithmetic names): start **red**, finish
    **red** (the pragma persists on the connection), post-fix passes.
  - `wait_finish`: finish **red**, others pass.
  - `swallow_both` (the audit layer swallows OperationalError): start
    **red**, finish **red**.
  - `nolock_holder` (holder reports held without taking RESERVED): start
    **red**, finish **red**, all `DID NOT RAISE`.
  - A first attempt, `swallow_start` alone, did NOT red the start test: the
    finish write then meets the same lock and raises, so that mutation does
    not break the contract the test pins. Recorded, not counted.
- Load harness, POST-fix: **10 of 10** roster iterations green (each of the
  three ladder tests 10/10); targeted **64 of 64** per test (two 32-copy
  runs, 96 passed each).

### 3.2 Mechanism 3 (commit `60ef62bd`)

- Fix: a `sentinel_registered` fixture registers the sentinel via
  `register_schwab_secrets` in the test's own setup and restores
  `_GLOBAL_KNOWN_SECRETS` in place at teardown (the snapshot/restore shape at
  `tests/integration/test_pipeline_marketdata_ladder_integration.py:64-74`).
  The `tests/conftest.py` docstring that documented the cross-test
  dependency is updated.
- Reproduction, PRE-fix: run ALONE (`-n 0`, one node) it reds
  deterministically (`sentinel leaked to audit error_message`); under the
  saturator **red 10 of 10** roster iterations (it never shares a worker
  with a happy-path sibling there). The full pre-fix suite happened to pass
  it (ordering).
- Mutation (plugin `d87_mut_redact.py`): `_redact_error_message_for_audit`
  -> identity: the fixed test **reds** with the sentinel in the audit row.
- POST-fix: alone **passes**; the whole file `-n 0` 27 passed; under the
  saturator **10 of 10** roster iterations green.

## 4. Forks (STOPPED; not chosen)

### 4.1 F1: mechanism (1)'s premise does not hold (items 1, 5, 8, 9)

CHARC's form: measure the isolated wall time, set the budget >= 5x. Measured
(quiet box, warm bytecode, `scratchpad/d87/measure_children.py`, three runs
each, the test's own argv):

| Child | Isolated | Current budget | Ratio | Under the harness (full suite, pre-fix) | D79 |
|---|---|---|---|---|---|
| L2 child pytest (item 1) | 5.5-6.4 s | 300 s | 47x | 157.65 s (budget margin 1.9x) | rerun: killed at 300 s although the child's own session read `3 passed in 24.57s` |
| `diagnose aplus-sensitivity` (item 5) | 1.89-1.95 s | 120 s | 62x | 52.24 s (2.3x) | `TimeoutExpired` 120 s |
| `diagnose aplus-sensitivity-v2 --help` (item 8) | 1.86-2.08 s | 60 s | 29x | 55.58 s (**1.08x**) | `TimeoutExpired` 60 s |
| weeknight wrapper + stub (item 9) | 0.36-0.39 s | 120 s | 308x | 1.79 s | no recorded signature anywhere |

Every budget is ALREADY >= 5x isolated, so the form as written changes
nothing and the reds stand. The load slowdown of a fresh Python child is
25-60x isolated and more, past any 5x-of-isolated floor. Reproduction under
my harness: items 1, 5, 8 **0 of 10** roster + 0 in the full run; item 9
**0 of 64** targeted roster-only, **0 of 192** (6 tests x 32) under the full
suite plus saturator, 0 of 10 roster.

- Shape A: keep ">= 5x", but take the basis from the HARNESS wall time:
  L2 300 -> 900 s (5.7x of 157.65), v2-help 60 -> 300 s (5.4x of 55.58),
  diagnose 120 -> 300 s (5.7x of 52.24); weeknight unchanged (120 s is 67x
  its harness time). Assertions unchanged. Cost: a hung child surfaces after
  up to 15 minutes; foreign load beyond the harness can still exceed it.
- Shape B: a load-calibrated budget. Each test first times a reference child
  on the same box at the same moment (e.g. `python -c "import swing.cli"`),
  and sets `timeout = max(5x isolated, K x reference)`. That is a fourth
  form, offered only as a shape.
- Item 9 separately: a possible non-budget mechanism by read, unconfirmed:
  `scripts/run-weeknight-pipeline.ps1` reads `$p.ExitCode` after
  `Start-Process -PassThru` and caches `$p.Handle` one statement later. A
  child that exits before the handle is cached is a known PowerShell race
  (ExitCode null -> 0 -> an `OK` line, which fails `"SKIP exit=75" in
  lines[0]`). If that is the mechanism the fix is in `scripts/`, outside
  this envelope. Not reproduced.

### 4.2 F2: items 6 and 7 fit none of the three mechanisms

The red is a PRODUCTION budget behaving as designed: `WEB_REPLAY_BUDGET_SECONDS
= 2.0` exhausts under load and the page correctly renders `tier-2 not counted:
trade 25 tier2_unverifiable (web_budget_exhausted)` (D79 run output
`full-a0b895e0.txt:415` and `:555`). The isolated replay takes 0.18-0.31 s
(probe plugin `d87_time_replay.py`, 6 calls), so 6.5-11x headroom. Not
reproduced under my harness: 0 of 32 targeted, 0 of 10 roster, 0 in the
full run (12.52 s per test there). By read the [rewritten] and [moved]
states of the same tests have the same exposure (an exhausted budget turns
them unverifiable too), and `test_a2_97b`'s wall-clock upper bound
(`assert elapsed < fve.WEB_REPLAY_BUDGET_SECONDS + 2.5 + 3.0`, `:592`) is a
second load-sensitive assertion in the same file, not on the roster and not
seen red.

- Shape A (test-only): in `_named_page`, monkeypatch the web budget at the
  call-site bindings the two pages reach, each bound by name at import:
  `swing/web/routes/metrics.py:17` (used `:296`, the card page) and
  `swing/web/view_models/metrics/tier_comparison.py:41` (used `:112`, the
  tier page). `swing/web/view_models/metrics/index.py:29` is a third binding
  these pages do not reach (found by grep of the constant's name over
  `swing/`; a grep bounds the set from below). Patch them to a measured
  larger value. The 2.0 s value
  stays pinned by the existing budget tests (`:592`, `:610`, `:661`). Cost:
  the page tests no longer run at the production budget.
- Shape B (test-only): give the replay a controlled clock. Monkeypatch
  `fve.time` with a namespace whose `monotonic` is frozen. The deadline is
  computed and checked only through `time.monotonic` (`:404`, `:1504`,
  `:1524`; `import time` at `:34`, no other `time.` use in the module), so
  the production 2.0 s value and code path stay and wall time cannot exhaust
  the budget in these page tests.
- Out of envelope, not offered as in-scope: changing the production budget.

## 5. Review rounds

None yet. Reviewer A (`strong`) runs on the final tree after F1 and F2 are
ruled.

| Round | Model / effort | Footer | Verdict | Crit / Major / Minor | New / Reopened | Depth (orchestrator) |
|---|---|---|---|---|---|---|
| (none) | | | | | | |
