# D87 -- suite load-robustness rider: executing ledger

Brief: `docs/d87-load-robustness-dispatch-brief.md` (main `9845b799`). Worktree
`.worktrees/d87-load`, branch `d87-load`, base `9845b799`. Tests only.

Status: the fork packet (section 4) was ruled by CHARC and the orchestrator
(section 4A, verbatim) and executed (section 4B). All roster items are
dispositioned; Reviewer A rounds are in section 5.

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

## 5. Review rounds

Reviewer A, `strong` tier, repo read access (cold-audit form, cwd = the
worktree, `-s read-only`), prompt plus `git diff -U8 9845b799..<head> -- tests/`
on stdin. Transcripts: `C:/Users/rwsmy/swing-data/review-transcripts/d87-load/`.

| Round | Model / effort | Footer | Verdict | Crit / Major / Minor | New / Reopened | Depth (orchestrator) |
|---|---|---|---|---|---|---|
| (none) | | | | | | |
