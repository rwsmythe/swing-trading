# Follow-up riders bundle (2026-09-28) -- dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.
**Mission:** land four small, independent test/script riders from the orchestrator's queue, each RED-first. The operator directed them on 2026-09-28 ("perform the followups and the cell_depth --live change").
**Scope:** `tests/`, `scripts/`, and the docstrings in those files only. **No `swing/` change of any kind.**
**Base:** `main` @ `dcb39030`. **Worktree:** `.worktrees/followups-riders`, branch `followups-riders` (`git worktree add -b followups-riders .worktrees/followups-riders dcb39030`).
**Cell:** `implementer-sonnet-high`, the executing default. The design is settled here, and every item is tests or scripts.

## 0. Read first

- `docs/implementer-dispatch-recipe.md`, in full. It is the protocol: §1 worktree, §2 TDD and commits, §3 the Codex review, §4 the return report, §5 disciplines.
- `CLAUDE.md`, the gotchas. The relevant ones here are "Adding a write-barrier ..." (seeding tests), the xdist/import-order entries, and cp1252.
- The four files named in §2, read end to end before editing.

**Skill posture:** no copowers skills, because they are absent in a sub-agent. Run Codex by hand per recipe §3 at the **`strong`** tier: code-shipping, and `cell_depth.py` is a harness instrument.

## 1. Binding conventions

The recipe governs. In brief:
- conventional commits, one per item, with the item id in the subject (`test(metrics): R-1 -- ...`);
- no `Co-Authored-By`, no `--no-verify`, no amend;
- the final `-m` paragraph is plain prose;
- bare `git` from the worktree cwd;
- `ruff check swing/` stays clean. You should not be touching `swing/`; if you find you need to, STOP.

## 2. The four items

### R-1: re-anchor the census test on call TEXT, not line numbers

**File:** `tests/metrics/test_22b_r1_3_surfaces_census.py`.

**The problem:** `_ONE_HOP_CALLERS` keys each site as `path:lineno`, so ANY edit above a pinned line in `swing/cli.py` breaks the test. It needed re-derivation on at least four consecutive landings (D67/D69, the 22-I branch and merge, and 22-F several times), each time with no new caller. A mirror that rots on every unrelated edit teaches people to re-pin it without reading.

**Required behaviour:**
- Key each rostered site by `(path, the stripped source line text)`, compared as a MULTISET (`collections.Counter`), so two identical call lines in one file are counted, not collapsed.
- The test still FAILS when a NEW one-hop caller appears, when a rostered caller disappears, or when a call line's text changes.
- It PASSES when unrelated edits move a rostered line.
- Keep every classification string, and keep `test_every_classification_is_one_of_the_named_dispositions`.
- Update the module docstring's METHOD paragraph to say text, not line.

**Discriminating tests.** Make the walk take a root (e.g. `_grep_call_sites(name, root=...)`) and add meta-tests over a `tmp_path` fake tree:
- (a) insert blank lines above a rostered call: PASS;
- (b) add a new caller line: FAIL, naming it;
- (c) delete a rostered caller: FAIL.

RED for (a) on the unmodified test is the line-number keying failing; show it.

**Derive the new roster BY MEASUREMENT from the current tree and READ each line.** Do not transcribe it from the old dict; state the method in the commit body.

### R-2: the D67 L1 follow-on (CHARC-ruled 2026-09-24, tests-only)

**File:** `tests/web/conftest.py`, the autouse fixture that wraps `insert_trade_with_event`. Its docstring records the D67 mechanism.

**The problem:** `swing/trades/entry.py` binds `insert_trade_with_event` BY NAME at its own first import. The fixture patches only `swing.data.repos.trades` and `swing.web.routes.trades`. So in a full run, where `tests/trades/` imports `swing.trades.entry` first, `record_entry` calls the REAL function and the wrapper is never reached; run alone, it is.

**The ruling, verbatim:**

> "the fixture patches the name at its LOOKUP SITE (swing.trades.entry.insert_trade_with_event); never an entry.py edit for a test's sake. Discriminator: a sentinel side-effect asserted after record_entry in a module that imports AFTER tests/trades/ in the full-run order -- the wrapper must be REACHED."

**Required behaviour:**
- The fixture also does `monkeypatch.setattr(swing.trades.entry, "insert_trade_with_event", wrapped)`, guarded like the existing route-module patch.
- The wrapper's existing `called_via_record_entry` skip, which keys on the PRESENCE of `attempt_id` in kwargs, already makes reaching it through `record_entry` fill-neutral. Keep it byte-unchanged and keep its comment block.
- No `swing/` edit.

**Discriminator:**
- A new test under `tests/web/` that imports `swing.trades.entry` at MODULE TOP. That forces the by-name binding to be captured BEFORE the autouse fixture runs, which is the full-run order, made deterministic in isolation.
- The test drives `record_entry` (or the POST that calls it) and asserts a sentinel the wrapper sets, e.g. a counter the fixture exposes.
- RED on the unmodified conftest: the sentinel is not set. GREEN after.
- Also assert the trade carries exactly ONE entry fill and the expected `current_size`, so the wrapper's skip still holds.

Run `tests/web` in full after the change and read the result, because every web test now routes `record_entry` through the wrapper.

### R-3: `cell_depth --live` also lists PARKED cells of live sessions

**File:** `scripts/cell_depth.py` (docstring + code); tests in `tests/scripts/test_cell_depth.py`.

**The problem:** `--live H` selects cells by transcript MTIME. A cell parked at a review-round gate writes nothing, so after H hours it drops out of the listing while newer cells still show. The census then silently omits a resumable cell. `--agent <id>` (`b09bbc02`) fixed the round-GATE read; this item fixes the CENSUS.

**The mechanism to use:**
- A cell's transcript is `<project-slug>/<session-id>/subagents/agent-<id>.jsonl`, and its parent session's own transcript is `<project-slug>/<session-id>.jsonl`.
- A sub-agent dies with its session, so a cell is resumable only while its parent session is live.
- **Rule:** `--live H` lists every cell written within H hours (unchanged), PLUS every older cell whose PARENT session transcript was written within H hours. Mark the second group in the existing `flag` column as `parked`, and keep `OVER` visible (e.g. `OVER,parked`; pick one form and document it).

**Unchanged:**
- `--sessions` output;
- `--agent`;
- the `--cap` exit-status semantics (parked cells ARE listed, so they count toward the cap check);
- the ASCII-only output.

Update the module docstring's `--live` paragraph to say what `--live` now includes and why, and keep the `--agent` round-gate text.

**Discriminating tests,** building synthetic trees under `tmp_path` the way the existing tests do:
- (a) an old cell + a fresh parent session: listed, flagged `parked`. RED on the unmodified script.
- (b) an old cell + an old parent: NOT listed.
- (c) a fresh cell: listed, NOT `parked`.
- (d) a parked cell over the cap: exit 1.

Read how the existing tests set mtimes, and match them.

### R-4: `probe_22i_guard_census.py` `#SUMMARY` undercounts INFO

**File:** `scripts/probe_22i_guard_census.py`.

**Located cause (orchestrator, by read):**
- `exposure()` (~`:708-713`) writes an `E-exposure ... empty ... INFO` row for every EMPTY exposure table WITHOUT `p.n_info += 1`.
- The three other direct INFO writes (~`:867`, `:887`, `:951`) do increment it.
- So a DB with two empty exposure tables prints 142 INFO rows against `#SUMMARY INFO=140`, which RD saw at the 22-I witness.

**Required behaviour:**
- Increment the counter at that write.
- Better, route every direct INFO write through ONE helper so the counter and the row cannot diverge again. Your choice; state which.

**Discriminating test:** in `tests/scripts/` (see `test_probe_22i_post_migrate.py` for how the probe is driven), run the probe over a DB with at least one empty exposure table. Assert that the count of rows whose verdict column is `INFO` equals the `#SUMMARY` INFO value. RED first.

**Do NOT open or write the live DB** (`~/swing-data/swing.db`). Use tmp DBs only.

## 3. Verification

- The FULL fast suite (`python -m pytest -m "not slow" -q`) to GREEN BEFORE the Codex review, and again after convergence. Save both under `C:\Users\rwsmy\swing-data\review-transcripts\followups-riders\`.
- Print the RESOLVER line (`python -c "import swing; print(swing.__file__)"` from the worktree). Pytest runs from the worktree cwd.
- Known order-dependent reds to reproduce with `-n 0` FIRST before treating as yours:
  - `tests/integrations/test_schwab_setup_cli.py::test_setup_auth_failure_audit_status_and_sentinel_redaction` fails ISOLATED on main and passes in its file;
  - `test_phase8_pipeline_second_same_day_run_upserts` and `tests/trades/test_22a2_cohort_readers.py::test_a2_94_*` have gone red under xdist load.

## 4. Adversarial review

- Recipe §3, the `strong` tier, run to convergence (`NO_NEW_CRITICAL_MAJOR`).
- Persist every round's prompt, diff, transcript, findings and exit to `...\review-transcripts\followups-riders\r<N>\`.
- Every validity assertion in §3 binds: banner with the model name, `^ERROR` 0, the anchored verdict token, the footer, exit 0.
- Three counted rounds, then a self-sweep. A fourth round needs the orchestrator's written authorization naming the finding.

**Watch items for the prompt:**
- R-1: can the text keying miss a new caller whose line text duplicates an existing one? (That is the multiset's job.)
- R-2: does any web test now double-insert a fill, and is the sentinel test truly order-independent?
- R-3: does `parked` ever list a cell from a DIFFERENT project slug? Does a missing parent transcript crash the listing?
- R-4: can any other INFO write bypass the counter?

## 5. Done criteria

- Four items committed, each with its RED in the commit body.
- The pre- and post-review fast suites green and saved.
- Codex converged on disk.
- A clean trailer audit over `dcb39030..HEAD`.

## 6. Return report (your final chat message, to the orchestrator only; never post to any mailbox)

- Per item: the commits, the RED text, and what changed.
- Both suite summary lines, verbatim, with the RESOLVER line.
- Codex: per round, the verdict, the token footer, and the findings with dispositions; the path to each persisted file.
- Anything you found outside scope: FLAG it, do not fix it.

## 7. If you get stuck

- STOP and return at the stuck point with what you measured if:
  - a premise here does not match the code;
  - an item would need a `swing/` edit;
  - an R-2 test would need an `entry.py` edit.
- Do not work around it.
