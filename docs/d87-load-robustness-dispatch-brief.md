# D87 -- suite load-robustness rider: EXECUTING dispatch brief (tests only)

**Audience:** a fresh implementer cell with no prior conversation context.

**Authority:**
- Operator-approved 2026-10-19: "I also concur with fixing those tests", and for `test_run_stub_skip_exits_zero`, "yes, fix it in the same batch".
- Registered by CHARC as D87 (charter commit `c80268de`).
- CHARC's form is BINDING. It is quoted in section 2 from `comms/orchestrator/read/20261019T171941Z-charc-d87-registered-suite-load-robustness-3-m.md`; read that file in full.
- Sequencing is the orchestrator's: this rider runs FIRST, before the maintenance rider.

**Cell:** `implementer-opus-high`. The design is settled, but concurrency test synchronisation and mutation discriminators need care.

**Worktree:** create `C:\Users\rwsmy\swing-trading\.worktrees\d87-load` on a new branch `d87-load` off main `0b6cc895`. Run all your tests from the worktree with `PYTHONPATH=.`, because the editable install resolves MAIN.

## 0. Envelope (hard)

- **IN:** test files and test helpers/conftest under `tests/` only.
- **OUT:**
  - anything under `swing/`, `scripts/` or `research/`;
  - any schema, migration or dependency;
  - any standing process;
  - `pyproject.toml` / pytest configuration, unless a fork is ruled.
- **Never:** delete a test, skip it, mark it `xfail` or `flaky`, add retries, or reorder tests as "the fix".

## 1. The roster (ten tests; measured red under xdist load in D79's runs, green with `-n 0`)

1. `tests/research/test_l2_lock_sys_modules_isolation_regression.py::test_research_l2lock_del_does_not_break_web_route_exception_identity`: a child pytest, `timeout=300`.
2. `tests/integrations/schwab/test_ladder_stress_production_path.py::test_forced_start_lock_leaves_no_audit_row`: "DID NOT RAISE OperationalError".
3. `tests/integrations/schwab/test_ladder_stress_production_path.py::test_forced_finish_lock_leaves_in_flight_row`.
4. `tests/integrations/test_schwab_setup_cli.py::test_setup_auth_failure_audit_status_and_sentinel_redaction`: intermittent since Phase 12 (`docs/archive/phase12/phase12-bundle-B-return-report.md:152`).
5. `tests/cli/test_diagnose_subcommands.py::test_diagnose_aplus_sensitivity_stdout_is_ascii_safe`.
6. `tests/trades/test_22a2_cohort_readers.py::test_a2_94[admit]`.
7. `tests/trades/test_22a2_cohort_readers.py::test_a2_95[admit]`.
8. `tests/research/test_aplus_v2_ohlcv_run.py::test_subprocess_aplus_sensitivity_v2_help_cp1252_safe`.
9. `tests/scripts/test_weeknight_wrapper.py::test_run_stub_skip_exits_zero`: CLAUDE.md's recorded xdist load flake (a real PowerShell subprocess writing a temp log).
10. Any sibling in the same file that READS the same mechanism. Name it, and include it only if it shares the defect, by read.

Items 5-8 came from a D79 run whose output showed subprocess `TimeoutExpired` at 120 s for at least some of them. **Classify each from the TEST'S CODE, never from that report.**

## 2. CHARC's form (binding; three mechanisms, one form each)

> - (1) Child-process budgets (the L2 test's `timeout=300` at :77; cell 7's five at 120 s). A budget raised is a measurement claim: measure the isolated wall time, quote it, set the budget at >= 5x, and keep the assertion on the child's exit status and output. A test that passes because the child merely finished has stopped guarding anything.
> - (2) The ladder stress tests. The 1 ms `busy_timeout` at :80 is the test's DESIGN (the pre-fix shape), not the defect; the race is that the holder thread (:69-71) may not yet hold RESERVED when the audit `BEGIN IMMEDIATE` runs. Synchronise: the holder sets an `Event` after its `BEGIN IMMEDIATE` returns and the test waits on it before opening the 1 ms connection. Lengthening the 1 ms would delete the test's premise.
> - (3) The sentinel-redaction test (:250) is ORDER-dependent, not load-dependent, and has been since Phase 12 (the archive's line 152: the sentinel is built by the test and never registered with the redactor). The fix registers the sentinel, or installs the factory the test asserts, in the test's own setup. Reordering or retrying it is not a fix.

> DISCRIMINATOR, per test, RED first: mutate the guarded behaviour and show the test still reds; then >= 10 passes under a synthetic load harness (the full suite at `-n 16` with a sibling process saturating CPU), the counts quoted in the return.

**A roster test that fits NONE of the three mechanisms is a FORK.** STOP and return it, with the mechanism you found and two fix shapes. Do not invent a fourth form.

## 3. Procedure, per test (one commit per mechanism class, or per test where the classes differ)

1. **Classify by read.** Quote the lines that show the mechanism.
2. **Reproduce the failure under load before fixing.** Use the load harness (below), or a targeted stress of the one test. Record the red count, e.g. "red 3 of 10 under load". If you cannot reproduce a red, say so; you still apply the form, but report the test as "red not reproduced".
3. **Fix it in the CHARC form.** For mechanism (1), quote the measured isolated wall time and the new budget (>= 5x).
4. **Mutation discriminator:** temporarily break the guarded behaviour, and show the fixed test reds. The mutation must be in a test helper, or a monkeypatched production symbol inside the test run, NEVER an edit to a file under `swing/`. If only a `swing/` edit can mutate it, make that edit and restore it byte-for-byte, verified by sha256, with `git diff -- swing/` empty afterwards. Record both results.
5. **Load harness:**
   - a sibling CPU saturator: e.g. `python -c "import multiprocessing as m; [m.Process(target=lambda: [0 for _ in iter(int,1)]).start() for _ in range(m.cpu_count())]"` run in the background, then KILLED and verified gone;
   - plus the roster tests run with `-n 16`;
   - >= 10 consecutive passes per test, with the counts quoted;
   - then one FULL fast suite at `-n auto` with the saturator running, read off the saved output.

## 4. Gates, then review

- The full fast suite on your final head WITHOUT the saturator: green, read off the saved output (`-m "not slow" -q -n auto -p no:cacheprovider`).
- `ruff check tests/` clean on the files you touched.
- `git diff --stat <base>..HEAD -- swing/ scripts/ research/` EMPTY.
- `%(trailers)` empty after EACH commit. No final `-m` paragraph may begin with `Word:`. No Co-Authored-By, no `--no-verify`, no amend.
- **Reviewer A, `strong`, repo access**, per `docs/implementer-dispatch-recipe.md` section 3, all five per-round assertions included:
  - The verdict tokens are DESCRIBED in the prompt, never written line-initially.
  - The prompt carries the envelope, CHARC's form verbatim, and the per-test classification, with challenge invited.
  - Return at EVERY counted-round gate, with its ledger row. Stop at the first `NO_NEW_CRITICAL_MAJOR`.
  - Save each round's evidence to `C:\Users\rwsmy\swing-data\review-transcripts\d87-load\`.
  - Reviewer B is NOT required (tests only).
- Keep a ledger at `docs/superpowers/plans/2026-10-19-d87-load-robustness.exec-ledger.md`: per-test classification, reproduction counts, mutation results, load-harness counts, and round rows. Leave the depth column empty.

## 5. Return (chat only)

You NEVER post to a mailbox and never run `scripts/role_mail.py`. Return:
- commits in order;
- per test: mechanism, quoted lines, reproduction count, fix, measured budget where relevant, mutation result, and load-harness pass count;
- the full-suite counts, with and without the saturator;
- the review ledger row(s);
- every deviation.

**If anything does not fit, STOP and return.** Do not choose for yourself.
