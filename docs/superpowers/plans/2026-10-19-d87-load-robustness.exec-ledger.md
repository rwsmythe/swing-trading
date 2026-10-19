# D87 -- suite load-robustness rider: executing ledger

Brief: `docs/d87-load-robustness-dispatch-brief.md` (main `9845b799`). Worktree
`.worktrees/d87-load`, branch `d87-load`, base `9845b799`. Tests only.

Status: the fork packet (section 4) was ruled by CHARC and the orchestrator
(section 4A, verbatim) and executed (section 4B). All roster items are
dispositioned; Reviewer A rounds are in section 5. Round 1's findings were
ruled (section 4C, verbatim) and fixed by a second cell (section 4D,
brief `docs/d87-exec-continuation-brief-cell2.md`, main `555e4e45`).

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

## 4A. Rulings on the fork packet

### CHARC (ruling of record: `comms/orchestrator/read/20261019T200436Z-charc-d87-fork-ruled-mech-2-ext-ok-f1-shape-a.md`; transcribed verbatim as relayed by the orchestrator)

Author: CHARC.

> MECHANISM-(2) EXTENSION -- ACCEPTED. A holder that lets go on its own timer while the main thread is still on its way to the write is the same race from the other side; the fix is release-on-signal, and every test releases in `finally` (verified at all three). The 30 s is a hang guard, not a budget, and the file says so at :42-44. One addition, small: `_external_lock_holder` sets `held` only after `BEGIN IMMEDIATE` returns, so a holder whose BEGIN raises leaves the test to `_HELD_WAIT`'s 60 s assertion. Acceptable (it is a broken-fixture path, and the assertion names it); do not widen the wait. The post-fix test keeps its 0.5 s self-release because that release IS its premise, and it is now non-vacuous because it waits on `held` first. Good catch on the vacuous pass.
>
> MECHANISM (3) -- form accepted (register in the test's own setup, in-place restore). ONE TEXT CORRECTION, by replacement: the fixture docstring claims a production fact the test does not pin ("a secret the process has already seen ..., the state production's Layer-0 redaction depends on"). That is the #31 class: a comment asserting behaviour elsewhere. It says instead what the fixture does and why: the sentinel's underscores defeat both Layer-1 regexes (`client.py:116-128`), so only a registered secret is redacted, and the test registers it. Your challenge to Reviewer A on the real-token path stands as content.
>
> FORK F1, items 1, 5, 8 -- SHAPE A, with the measurement basis corrected in my form. My "5x isolated" named the wrong basis: the budget covers interpreter start, import and collection, which the isolated number does not measure and which load inflates 25-50x (the D79 L2 run: ~275 of 300 s before the child's own clock started). The rule becomes: budget = max(5x isolated, 5x under-the-harness), BOTH numbers quoted in a comment at the constant, with the harness named (full suite at -n 16 plus the saturator, the box state). Values as you measured: L2 300 -> 900 s; diagnose 120 -> 300 s; v2-help 60 -> 300 s. The assertion stays on the child's exit status and output; `TimeoutExpired` stays a failure, never a skip. Shape B rejected: a fourth form, machinery in every subprocess test, and a reference child timed under the same load is itself the noisy quantity. The hang latency is accepted and stated: a true hang surfaces within 15 min inside a run that already takes 13-24.
>
> FORK F1, item 9 -- CONCUR: NO CHANGE under D87, no 1 s stub. The budget mechanism is RULED OUT (308x; 0 of 256 under load). The handle hypothesis is UNCONFIRMED and I doubt it: `$null = $p.Handle` is the standard cache idiom and a `-PassThru` object comes from `Process.Start`, which owns its handle; but a doubt is not a reading, so the loop decides. ORDERED as an execution step in D87's return, not a code change: a tight loop of the wrapper plus the millisecond stub, N >= 500, under the saturator, counts quoted. If it reproduces, it is registered on my seat as a confirmed `scripts/` defect, owner orchestrator, fixed outside D87 with the mechanism read from the reproduction. If it does not, the CLAUDE.md line (yours, after merge) says: budget ruled out, not reproduced in N under load, the handle hypothesis open, and "xdist LOAD flake" is no longer the recorded classification. Either way the line stops saying a thing nobody has measured.
>
> FORK F2, items 6 and 7 -- SHAPE B, applied to the whole parametrization of both tests. These tests assert what renders per state; the production budget is the one non-hermetic input, and freezing the clock removes it while leaving the constant, the code path and the three budget tests (:585, :608, :659 -- two wall-clock, one counts the budget value) untouched. Safe by read: the module reads `time.monotonic` at exactly three sites, all deadline arithmetic; no sleep, no clock-driven loop; the `unverifiable` state is produced by the git-timeout stub, not the clock, so it renders unchanged under a frozen one. FORM OF THE FREEZE: delegate, do not stub -- `monkeypatch.setattr(fve, "time", <object whose monotonic returns a constant and whose every other attribute forwards to the real module>)`, so a later `time.` use in the module cannot fail into an AttributeError that reads as a test defect. Shape A rejected: two bindings of one constant is the mirror family (#11); a value patched at two sites is a third spelling.

### Orchestrator (brief owner; relayed in the resume message)

> - Fix the pre-existing SIM105 at tests/conftest.py:335. The gate is "ruff clean on the files you touched", and conftest.py is touched. Give it its own commit.
> - The cp1252 decode-and-re-encode weakness is banked to me. Do not touch it in D87.

Two facts read at encoding time, reported up: the "0 of 256" in CHARC's
item-9 paragraph is the sum of my two targeted runs (64 + 192); and the
three budget tests' lines (`:585`, `:608`, `:659`) are on the base file and
shift by 34 lines after the F2 commit (defs `test_a2_97b` 569 -> 603,
`test_a2_97c` 595 -> 629,
`test_charc_g_t10_1_web_invocations_per_route_each_under_the_web_budget`
644 -> 678). Their bodies are unchanged: the F2 diff touches only the new
`_FrozenReplayClock` class and `_named_page`.

## 4B. Post-ruling execution

Commits after the ruling, in order: `a81d188c` (mechanism-3 docstring
correction), `df0d95c8` (F1 shape A), `4447ec29` (F2 shape B), `4ff43a9d`
(SIM105), `64b621af` (pre-existing lint in the A2 file).

### 4B.1 Mechanism 3 text correction (`a81d188c`)

The test docstring now says what the fixture does and why: the sentinel's
underscores defeat both Layer-1 regexes (`client.py:116-128`), so only a
registered secret is redacted, and the test registers it. The fixture
docstring's "never-narrowed in production" clause is narrowed to the cited
fact that the registry is a process-global set (`client.py:80`).

### 4B.2 F1 shape A, items 1, 5, 8 (`df0d95c8`)

| Item | Isolated (5x) | Harness (5x) | Budget | Comment at |
|---|---|---|---|---|
| 1 L2 child | 5.5-6.4 s (32 s) | 157.65 s (788 s) | 300 -> 900 s, `_CHILD_BUDGET_SECONDS` | module constant |
| 5 diagnose | 1.89-1.95 s (10 s) | 52.24 s (261 s) | 120 -> 300 s | at the `subprocess.run` |
| 8 v2 help | 1.86-2.08 s (10 s) | 55.58 s (278 s) | 60 -> 300 s | at the `subprocess.run` |

Harness named in each comment: the full fast suite at `-n 16` plus a
16-process CPU saturator, base `9845b799`, with intermittent foreign pytest
load on the box. Assertions unchanged (exit status and output);
`TimeoutExpired` is still a failure. The L2 timeout message now prints the
constant.

Mutation discriminators (the guarded behaviour, never the budget):

- Item 1, `l2_norestore` (plugin `d87_mut_l2.py`, injected into the CHILD via
  `PYTEST_ADDOPTS=-p d87_mut_l2`): the tests/research conftest's
  `_restore_swing_modules` becomes a no-op in the child. The test **reds**
  with its own 17-D.4 message (child victim returns 500). Control (no
  mutation, same injection): passes.
- Items 5 and 8, `cli_exit_nonzero` (a `sitecustomize.py` on PYTHONPATH,
  active only in a process whose `__main__` spec is `swing.cli` and which
  has not imported pytest): the CLI child exits 3. Both tests **red** on
  `assert proc.returncode == 0` (`assert 3 == 0`). Controls pass.
- Items 5 and 8, `cli_glyph` (every `click.echo` appends U+2192): both
  tests **PASS**. Measured on the diagnose child: rc 0, stdout carries the
  UTF-8 bytes `e2 86 92`, which the parent decodes as cp1252 mojibake and
  then re-encodes without error. This is the decode-and-re-encode weakness
  the orchestrator banked; demonstrated here by execution, not touched.

### 4B.3 F2 shape B, items 6 and 7 (`4447ec29`)

`_FrozenReplayClock` stands in for `fve.time` in `_named_page`, so every
state of both tests: `monotonic` returns a constant captured at
construction, every other attribute forwards to the real module
(`__getattr__`), and `calls` counts reads. `_named_page` asserts
`clock.calls > 0` after the GET, so the freeze cannot pass vacuously if the
module stops reading its clock through `time`. The budget constant, the code
path and the three budget tests are untouched (one-hunk diff).

Mutations (plugin `d87_mut_f2.py`, wrapping `fve.tier2_cohort_exclusions`,
10 tests per run, `-n 8`):

| Mutation | Reds | Passes |
|---|---|---|
| none (control) | 0 | 10 |
| `drop_exclusions` | `rewritten`, `unverifiable` x2 pages = 4 | 6 |
| `drop_observations` | `moved` x2 = 2 | 8 |
| `budget_exhausted` (zero budget: the D79 production outcome) | `admit`, `moved`, `rewritten` x2 = 6 | 4 |
| `zero_spawns_git` (a git call with zero rows) | `zero` x2, plus `unverifiable` x2 (its git-timeout stub raises on the extra call) = 4 | 6 |
| `unfreeze_slow_git` (stand-in ticks in real time, git slowed to 0.6 s) | `admit`, `moved`, `rewritten` x2 = 6 | 4 |
| `slow_git_frozen` (same slow git, freeze intact) | 0 | 10 |

Every state reds under at least one mutation. The last two rows are the fix
itself: the same slow git reds three states with a ticking clock and none
with the frozen one. The whole file passes (83), and with
`tests/metrics/test_22b_cohort_read_race.py` 95.

### 4B.4 Item 9: the ordered loop (no code change)

`scratchpad/d87/item9_loop.py`: exactly the test's invocation (powershell
`-File run-weeknight-pipeline.ps1`, a `stub.cmd` that does `exit /b 75`),
no timeout, 8 concurrent attempts, under the 16-process saturator. GOOD =
rc 0 and exactly one log line containing `SKIP exit=75`.

- **N = 600: 600 good, 0 bad.** Wall per attempt: min 1.463 s, median
  2.641 s, max 5.208 s. Saved: `scratchpad/d87/item9-n600-sat.json`.
- Not reproduced. Per CHARC's ruling, no `scripts/` registration; the
  CLAUDE.md line (orchestrator's, after merge) records: budget ruled out,
  not reproduced in 600 under load (plus the earlier 256), the handle
  hypothesis open.

### 4B.5 Lint (`4ff43a9d`, `64b621af`)

- `tests/conftest.py:335` SIM105: `try/except AttributeError/pass` ->
  `contextlib.suppress(AttributeError)`, own commit, as ruled.
- `tests/trades/test_22a2_cohort_readers.py` became a touched file with F2
  and carried 22 pre-existing findings (18 F811, 4 E501). The F811s came
  from test parameters named after the imported `ticking_clock` fixture;
  the fixture is now bound by a module-level assignment from
  `test_22a2_correction_service`, which pytest discovers identically (83
  tests collect and pass, as before). The E501s were one docstring line and
  three comment rulers. Own commit. Flagged: not covered by an explicit
  ruling, and `tests/metrics/test_22b_cohort_read_race.py` keeps the same
  import idiom.

### 4B.6 Load harness and gates on the final code head (`64b621af`)

- Roster under the saturator, `-n 16`, 10 iterations, 23 tests each (all
  five states of both A2 tests, the whole weeknight file): **10 of 10
  green** (each roster test 10/10). Iteration times 139-288 s.
- Full fast suite under the saturator, `-n auto --durations=0`:
  **15498 passed, 13 skipped, 0 failed in 2060.89 s**
  (`scratchpad/d87/load/full-64b621af-sat.txt`). Child durations in that
  run: L2 182.03 s, v2 help **87.97 s**, diagnose **85.88 s**. The v2-help
  child would have red at its OLD 60 s budget; diagnose would have held its
  old 120 s by 34 s. Under the new 300 s both pass with 3.4-3.5x margin, and
  L2 has 4.9x under 900 s. These are above the 55.58 / 52.24 s basis, which
  is why a single pre-fix harness run is a floor, not a ceiling.
- Full fast suite without the saturator, `-n auto -p no:cacheprovider`:
  **15498 passed, 13 skipped, 0 failed in 888.24 s**
  (`scratchpad/d87/load/full-64b621af-nosat.txt`).
- Ruff on every touched test file: clean (5 files).
- `git diff --stat 9845b799..HEAD -- swing/ scripts/ research/`: empty.
- `%(trailers)` empty on every commit.

## 4C. Rulings on Reviewer A round 1

### CHARC (ruling of record: `comms/orchestrator/read/20261019T221138Z-charc-d87-r1-ruled-r1-01-and-r1-02-upheld-max.md`, main repo)

Author: CHARC.

> CHARC RULINGS, D87 Reviewer A round 1 (R1-01, R1-02; R1-03's bank accepted). PRIMARY: CHARC on all three (the form is mine; both findings contradict my sentences and both are right). Read at this seat: the L2 constant and its comment on d87-load (:50-58); the post-fix test (:181-206); `auth.py:1147` (the token registry write follows the successful construction -- Codex's premise holds on disk); `client.py:116-128`. And one fact ESTABLISHED BY EXECUTION here, because R1-02's fix rests on it: `sqlite3.Connection.set_trace_callback` fires for `BEGIN IMMEDIATE` BEFORE the busy handler gives up -- a connection with `timeout=0.001` against a held RESERVED lock traced `['BEGIN IMMEDIATE']` and then raised `database is locked`, the trace stamp earlier than the raise. Transcribe as block quotes with CHARC as author.
>
> R1-01 -- UPHELD. The orchestrator's recommendation ADOPTED: the basis is the MAX over every harness run measured, each run quoted at the constant with its date and box state; 5x that, rounded UP to a round figure. L2 1000 s; diagnose 450 s; v2-help 450 s. The 15 minutes in my ruling was a stated consequence of one sample, not a cap; a cap would make the rule and the number conflict at exactly the test the rule exists for, so there is no cap, and the comment says what the latency now is (about 16.7 min for L2) in those words. Two additions to the form, both because a constant measured once DECAYS (D21): (i) the comment carries the re-open condition -- any later harness measurement above budget/5 re-opens the constant, by the next arc that reads it, not by a flake wave-through; (ii) the figures are written as measured (788.25, 10.4), rounded only at the budget. One run that is 16% higher than the run before it is the reason a single sample was the wrong input; the reviewer measured my rule against its own basis and found the input short. Correct.
>
> R1-02 -- UPHELD; Codex's fix ADOPTED as mechanism (2) applied to the second half of the handshake. My sentence "non-vacuous because it waits on `held` first" closed the holder's side of the race and left the main thread's side open: the 0.5 s timer starts at `held`, and a main thread descheduled past 0.5 s between `_wait_held` and the audit `BEGIN IMMEDIATE` meets no lock and passes for nothing -- the very window this arc closes. The fix: a `set_trace_callback` on the audit connection (test-side; the test passes that connection in; nothing under `swing/`), filtered to a statement beginning `BEGIN`, sets `begun`; the holder waits on `begun` (bounded) and only THEN starts its 0.5 s. Contention is structural: the trace fires when the statement starts, before the busy wait (verified above). The 0.5 s release stays as the test's premise. FORM, three points: (a) a DID-IT-FIRE assertion after the call -- the test asserts `begun.is_set()`, so a handshake that never fired cannot pass as a green (the B-06 class); (b) the holder's wait on `begun` is bounded (60 s, the `_HELD_WAIT` figure) and on expiry it still releases and records the failure into the per-test holder-exception collection R1-04 adds, so the test fails on an assertion, never hangs; (c) the callback body only sets the event -- no SQL, no assertion, no logging inside the trace. Mutation to show RED first: a holder that starts its 0.5 s at `held` as today, with the main thread delayed 0.6 s before the call, must fail the fixed test's `begun`-gated path and pass the old one vacuously; quote both.
>
> R1-03 (pre-existing half) -- BANKED ON MY REGISTER as D88, accepted: production registers the live tokens at `auth.py:1147` AFTER the successful construction, so a token carried inside a construction-time exception (the auth-failure path) is redacted by the Layer-1 heuristics ALONE (`[a-fA-F0-9]{32,}`, the base64 run), and NO test pins that path with a realistic token shape; the sentinel test cannot, because its sentinel's underscores defeat Layer 1 by design. Owner CHARC for placement (the redaction-by-construction architecture is form); trigger the next `swing/integrations/schwab/` touch or the D39 sweep. Discriminator when it runs: a construction-time exception carrying a Schwab-shaped token (the dotted base64 segments of a real access token, not hex) -> absent from stdout and from the audit row's error text, with NO registration. A test that exposes a `swing/` defect there is a `swing/` arc, outside D87, as you said. The in-scope half (the module comment at :30-33 claiming both regexes "target" the sentinel) is a false comment in normative position; fixed in round 2 under your gate.
>
> ROUND COUNT: round 1 counted; round 2 is the confirming round on the fixed tree from a fresh cell (the cell is over the cap; the continuation brief commits to main first). This is a tests-only rider at round 1 of a fresh loop; no check-in question arises yet.
>
> Nothing else open on my seat for D87 round 1.

### Orchestrator (brief owner; continuation brief section 2)

> - **R1-03, in-scope half:** the module comment at `tests/integrations/test_schwab_setup_cli.py:30-33` says both Layer-1 regexes "target" the sentinel. That is false: the sentinel's underscores defeat both. Rewrite the comment to say what is true. The sentinel is redacted only through the Layer-0 registry, which is why the `sentinel_registered` fixture exists.
> - **R1-04 (minor, in scope):** in `_external_lock_holder`: close the connection in a `finally`; collect any holder exception in a per-test list; assert the list is empty after each `join()`, in all three tests. R1-02's bounded-wait expiry records into the same list.

## 4D. Cell-2 execution (head `41a16471` onward)

Commits, in order: `41a088de` (R1-04), `6fba8627` (R1-02), `51fbc04d`
(R1-01 budgets), `f33df595` (R1-03 comment), `d4d3d430` (R1-01: this cell's
harness run quoted at the constants), then this ledger commit. Mutation
plugin: `scratchpad/d87/mut/d87_mut_r102.py` (loaded with `-p`, no tracked
file edited); it also records `record_call_start`'s wall time, which is the
audit `BEGIN IMMEDIATE`'s wait and so the contention evidence. Outputs:
`mut/r102-old.txt`, `mut/r104-new.txt`, `mut/r102-new.txt` and the
`*-durations.txt` beside them.

### 4D.1 R1-04 (`41a088de`)

`_external_lock_holder` takes a per-test `errors` list, appends any
exception raised in the thread, and closes its connection in `finally`.
Each of the three tests asserts the list is empty after its join
(`_assert_holder_clean`). Red first, mutation `holder_commit_raises` (the
holder's `commit()` raises):

- old file (`41a16471`): both pre-fix tests **pass** (the thread exception is
  only a `PytestUnhandledThreadExceptionWarning`); the post-fix test fails on
  `database is locked` after 32.8 s (the dead thread's connection was never
  closed).
- fixed file: all three **red** on the holder assertion
  (`[RuntimeError('D87 mutation: holder commit raises')]`); the post-fix
  audit write itself succeeds because `finally` closed the connection.
- control, fixed file: 3 passed.

### 4D.2 R1-02 (`6fba8627`)

- `_begin_tracer(begun)` builds the audit connection's trace callback: it
  sets `begun` on a statement beginning `BEGIN`, and does nothing else (form
  point c). The first `BEGIN` on that connection is `record_call_start`'s
  `BEGIN IMMEDIATE` (`audit_service.py:186`); before it the connection runs
  only PRAGMAs.
- The holder, given `begun_evt`, waits on it through `_await_audit_begin`
  (`begun_evt.wait(_HELD_WAIT)`, 60 s). On expiry it records an
  AssertionError in `errors` and releases at once (form point b).
  Otherwise it waits its 0.5 s and, at release, records an AssertionError
  if `begun_evt` is still unset.
- The test asserts `begun.is_set()` in a `finally` around the call (form
  point a), so a handshake that never fired is reported as itself, with the
  lock timeout it causes chained as context.
- Encoding choice, flagged for review: the release-time check is not one of
  CHARC's three points. Without it CHARC's ordered mutation would PASS the
  fixed test: the trace still fires when the late main thread reaches its
  BEGIN, so `begun.is_set()` is true, and nothing else sees that the holder
  had already let go. The check is what makes "contention is structural" an
  assertion rather than a property of the unmutated holder.

Mutations, the whole file at `-n 0` (`record_call_start` wall time for the
post-fix test in the last column):

| File | Mutation | Post-fix test | Audit start |
|---|---|---|---|
| old `41a16471` | none | pass | 0.5547 s (contended) |
| old `41a16471` | `delay_call` (main sleeps 0.6 s before the call) | **pass, vacuously** | 0.0071 s (no contention) |
| fixed | none | pass | 0.5656 s |
| fixed | `delay_call` | pass | 0.5610 s (contended) |
| fixed | `no_await_begun` + `delay_call` (CHARC's ordered mutation: the holder starts its 0.5 s at `held`) | **red**: `the holder released before the audit BEGIN started: no contention` | 0.0077 s |
| fixed | `never_fires` (the callback never sets `begun`) | **red** on the did-it-fire assertion (`the audit connection's BEGIN was never traced`), `database is locked` chained; 60.97 s for the file, no hang | 32.84 s |

The two pre-fix tests passed under every R1-02 mutation (they take no
`begun_evt`).

### 4D.3 R1-01 (`51fbc04d`, `d4d3d430`)

Each constant now quotes every harness run with its date and box state, the
figures as measured, the latency sentence and the re-open condition:

| Child | Isolated (5x) | Base `9845b799` (5x) | Head `64b621af` (5x) | Head `f33df595` (5x) | Budget | budget/5 |
|---|---|---|---|---|---|---|
| L2 | 5.5-6.4 s (32.0) | 157.65 s (788.25) | 182.03 s (910.15) | 79.86 s (399.3) | 300 -> 1000 s (about 16.7 min) | 200 s |
| diagnose | 1.89-1.95 s (9.75) | 52.24 s (261.2) | 85.88 s (429.4) | 69.75 s (348.75) | 120 -> 450 s (7.5 min) | 90 s |
| v2 help | 1.86-2.08 s (10.4) | 55.58 s (277.9) | 87.97 s (439.85) | 57.26 s (286.3) | 60 -> 450 s (7.5 min) | 90 s |

Every harness run is the full fast suite at `-n 16` (or `-n auto`, which is
16 on this box: xdist falls back to `os.cpu_count()` without `psutil`, and
`PYTEST_XDIST_AUTO_NUM_WORKERS` is unset) under the 16-process saturator,
2026-10-19, with intermittent foreign pytest load on the box. This cell's
run (`f33df595`) measured below budget/5 for all three, so the ruled values
stand. The diagnose child is the tightest: 85.88 s against a 90 s re-open
line.

### 4D.4 R1-03 comment (`f33df595`)

The module comment now says the audit-row error message goes through
`auth.py:_redacted_excerpt` -> `client.py:_make_redactor_from_global`, that
the underscores cut each sentinel into runs of at most 22 characters so
neither Layer-1 regex matches, and that only the Layer-0 registry redacts a
sentinel, which is why the test registers it. One fact read at encoding
time, reported up: the old comment's second instrument,
`client.py:_redact_message`, is NOT a Layer-1 regex. Its pattern
(`[/=:][A-Za-z0-9_]{8,}`, `client.py:321-323`) includes the underscore and
would match `token=<sentinel>`; it is simply not on this test's path (it is
`_RedactedMessageError.__str__`, and the raised `SchwabAuthError` prints as
`SchwabAuthError(status=500, body=<N bytes>)`, `client.py:371-377`). The
comment says it is a different mask, off the audit-row path, rather than
that the underscores defeat it.

### 4D.5 Load harness and gates (head `f33df595`)

- Roster under the saturator (`scratchpad/d87/sat2.pids`, 16 burners), `-n 16`,
  10 consecutive iterations, 23 tests each (the three ladder tests, the
  setup-CLI test, the three child-budget tests, every state of both A2
  tests, the whole weeknight file): **10 of 10 green, 23 passed each** (230
  passes; each roster test 10/10). Iteration times 150.89-189.25 s.
  Outputs `scratchpad/d87/load/c2-1.txt` .. `c2-10.txt`.
- Full fast suite under the saturator, `-n 16 --durations=0`: **15498
  passed, 13 skipped, 0 failed in 1886.81 s**
  (`scratchpad/d87/load/full-f33df595-sat.txt`). Child times in 4D.3.
- The saturator was killed by PID and verified: `remaining: 0`, no python
  process matching `saturator|multiprocessing`.

### 4D.6 Gates on the reviewed head (`200d836d`)

- Full fast suite WITHOUT the saturator, `-m "not slow" -q -n auto -p
  no:cacheprovider`: **15498 passed, 13 skipped, 0 failed in 820.69 s**
  (`scratchpad/d87/load/full-200d836d-nosat.txt`). The code is unchanged
  from `f33df595` except `d4d3d430`'s comment lines.
- `ruff check` on every touched test file (7 files): clean.
- `git diff --stat 9845b799..HEAD -- swing/ scripts/ research/ pyproject.toml`:
  empty.
- `%(trailers)` empty on every commit `9845b799..HEAD`; zero
  `Co-Authored-By`; no final paragraph begins with `Word:`.
- Observed, not touched: an untracked `Microsoft/Windows/PowerShell/ModuleAnalysisCache`
  directory appeared at the worktree root at 13:09 during the saturated full
  suite (some test's PowerShell child wrote its module-analysis cache
  relative to its cwd). It is not in the diff; flagged to the orchestrator.

## 5. Review rounds

Reviewer A, `strong` tier, repo read access (cold-audit form, cwd = the
worktree, `-s read-only`), prompt plus `git diff -U8 9845b799..<head> -- tests/`
on stdin. Transcripts: `C:/Users/rwsmy/swing-data/review-transcripts/d87-load/`.

| Round | Model / effort | Footer | Verdict | Crit / Major / Minor | New / Reopened | Depth (orchestrator) |
|---|---|---|---|---|---|---|
| R1 (head `08e83e62`, diff `tests/` vs `9845b799`) | gpt-5.6-sol / high (= `strong.config.toml`) | 146,268; `^ERROR` 0 | NEW_CRITICAL_MAJOR_FOUND (x2, the duplicated final message; the other token 0) | 0 / 3 / 1 | 4 new / 0 reopened | |
| R2 (head `200d836d`, diff `tests/` vs `9845b799`; cell 2) | gpt-5.6-sol / high (= `strong.config.toml`) | 187,459; `^ERROR` 0 | NO_NEW_CRITICAL_MAJOR (x2, the duplicated final message; the other token 0) | 0 / 0 / 3 | 3 new / 0 reopened | |

R1 findings and dispositions (full text + adjudication: `C:/Users/rwsmy/swing-data/review-transcripts/d87-load/copowers-findings.md`; transcript `review-r1.txt`, 613,189 bytes; prompt `prompt-r1.md`, 44,004 bytes):

- R1-01 major: the final-head harness run measured the three children higher (182.03 / 85.88 / 87.97 s), so 5x exceeds the committed 900 / 300 / 300 s. VALID; routed (L2's 5x passes the 15-minute hang latency CHARC accepted). Proposed: basis = max over all harness runs, L2 1000 s, the two CLI children 450 s.
- R1-02 major: the post-fix sibling's 0.5 s self-release starts at `held`, so a descheduled main thread can still pass without contention. VALID by read; routed (it contradicts the ruling's "now non-vacuous"). Proposed: start the 0.5 s only once the audit connection's `BEGIN IMMEDIATE` has begun (`set_trace_callback` event).
- R1-03 major as filed: the module comment at `test_schwab_setup_cli.py:30-33` falsely says both regexes target the sentinel (VALID, comment fix in scope); the unpinned real-token construction path is pre-existing (Codex agrees), proposed BANKED to the orchestrator.
- R1-04 minor: the holder neither closes its connection in `finally` nor surfaces thread exceptions. VALID, fix in scope.

All four were ruled (section 4C) and fixed in cell 2 (section 4D).

R2 (cell 2): transcript `review-r2.txt`, 667,269 bytes; prompt
`prompt-r2.md`, 61,592 bytes (the verdict tokens described, never written:
0 line-initial and 0 anywhere, by grep); diff `diff-r2.txt`, 36,987 bytes;
findings appended to `copowers-findings.md`. The process had exited before
the transcript was read. No command read a round-1 file: the six hits of the
prior-findings grep are the prompt echo, docs prose and this ledger. No
content-filter event. Findings, with proposed dispositions (NOT applied: the
continuation brief stops at this gate):

- R2-01 minor: the module docstring at `test_schwab_setup_cli.py:11-13`
  (pre-D87 text) credits `client.py:_redact_message` as the sentinel tests'
  defense-in-depth; it is on neither the audit-row nor the stdout path.
  VALID; proposed docstring-only fix in scope, no new round.
- R2-02 minor: `_assert_holder_clean` sits after each outer `try/finally`,
  so a holder exception that coincides with a failing test body goes
  unreported. Cannot produce a false green, leak or hang. VALID; proposed:
  accept, or attach the holder errors to the propagating exception
  (`add_note`) in the outer `finally`. Orchestrator's call.
- R2-03 minor: the ledger had no unsaturated full-suite result on the
  final head when Codex read it. The gate had been run (15498 passed, 4D.6);
  recorded now. No code change.

Round 2 is the first clean verdict, so the A-loop ends here. Spend, A
rounds: 146,268 + 187,459 = 333,727 tokens.
