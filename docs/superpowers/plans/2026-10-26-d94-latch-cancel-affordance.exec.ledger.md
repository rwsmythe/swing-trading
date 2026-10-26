# D94 (a)+(b) EXECUTING ledger -- the latch validity prompt gate + the ledger-keyed cancel affordance

**Plan:** `docs/superpowers/plans/2026-10-26-d94-latch-cancel-affordance.plan.md` (cleared at `fafb92ac`).
**Plan ledger:** `docs/superpowers/plans/2026-10-26-d94-latch-cancel-affordance.plan.ledger.md`.
**Brief:** `docs/d94-latch-cancel-affordance-exec-dispatch-brief.md` (main `7b2dca9e`).
**Worktree / branch / diff base:** `.worktrees/d94-cancel`, `d94-cancel`, `8acea975`.
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d94-cancel\exec\` (`tdd-evidence\`, `round<N>\`).

## 1. Rulings received during executing (verbatim, with authors)

### 1.1 Orchestrator -- the Task-3 misfit (T3.2 placement) and the C-1 naming. Author: the orchestrator.

Raised by this cell at the Task-3 boundary: T3.2's assertion (iii) (exactly one `latch-cancel-form`
for 5002) names the LEDGER-KEYED control, which Task 4 renders, so it could not be GREEN at the
Task-3 commit.

> T3.2 placement: OPTION A. T3.2 lands in Task 3 with assertions (i), (ii) and (iv). Assertion (iii), exactly one ledger-keyed `latch-cancel-form` for 5002, is ADDED to the same test function in the Task-4 commit, where the control is wired, and must be RED on the Task-3 tree. This is a test-SEQUENCING correction of the SS-1/SS-2 kind: no code, gate, envelope or assertion content changes, so it does not re-open the directors' clearance. The plan text stays as committed; this ruling and the ledger record the move.
> The naming deviation (`resting_order_ids` for the plan's `book_order_ids`, per CHARC C-1) is ACCEPTED. Use the same name for Task 3's `_displaced_cycle_prompts` keyword.

## 2. Deviations from the plan text (each with its authority)

- **D-1 (naming, CHARC C-1; accepted in 1.1).** The gate's keyword and `_displaced_cycle_prompts`'
  keyword are `resting_order_ids` (the plan's code blocks say `book_order_ids`); the same set is
  exposed on `_ValidityRender.resting_order_ids` (C-2).
- **D-2 (test sequencing, ruling 1.1).** T3.2 (iii) lands in the Task-4 commit, RED on the Task-3
  tree.

## 3. Pre-review gates (Task 6), read off saved output

- **Full fast suite** (`-m "not slow" -q -n 8 -p no:cacheprovider`, head `0bda0385`):
  `1 failed, 15556 passed, 13 skipped` in 913.53 s. The one red is OUTSIDE this arc:
  `tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py::test_ohlcv_cache_get_or_fetch_invariant`,
  `ValueError: No data for AAPL`. Mechanism: a WALL-CLOCK TIME BOMB. The fixture's bars are dated
  2026-04-01..03 and the cache cuts at `last_completed_session(now) - window_days(200)`
  (`swing/web/ohlcv_cache.py:282-283`), which has passed 2026-04-03 since the session of
  2026-10-21. Reproduced at `-n 0` on this worktree AND on `main` @ `7b2dca9e` (1 failed, both).
  No file of this arc touches `swing/web/ohlcv_cache.py` or `tests/pipeline/`. Not re-run.
- **Ruff:** `ruff check swing/` clean; zero findings on the two new test modules.
- **Envelope:** `git diff --stat 8acea975..HEAD -- swing/data swing/trades swing/web/routes scripts research`
  is EMPTY. The `swing/` files changed: `swing/latches/classification.py`,
  `swing/web/view_models/latches.py`, `swing/web/templates/partials/latch_orders.html.j2`.
- **Live census probe** (plain sqlite3 `mode=ro`, anchor 2026-10-26, derivation session
  2026-10-23, 14 latches, EMPTY book, worktree code): every row matches plan Task 6 step 3 --
  DFTX place 5 and IMNM place 6 the cancel lines (intents 11 and 10); OII place 1 the fill line
  (accepted 2026-08-10, filled 2026-08-17); IMNM place 7 the W1 correction for 1007804578712 plus
  ONE ledger control (source `ledger`, W2); IMNM place 12 and RHI place 4 first-answer absence
  prompts only; CADL nothing. Output: `exec\tdd-evidence\census-probe.txt`.
- **Mutations** (scratch, each reverted, `git diff --exit-code swing/` = 0 after each), all RED:
  M1 the shipped short-circuit (G2 falls through) -> T2.1; M2 latest-wins -> T3.4; M3 2B -> T3.2;
  M4 union without the resting check -> T4.4; M5 the VM re-spells the fill conjunction -> T2.3;
  M6 W1 dropped -> T3.3. Output: `exec\tdd-evidence\mutations.txt`.

## 4. Reviewer A round table

| round | tier / model / effort (banner) | footer | verdict token | `^ERROR` | crit | major | minor | new / reopened | reverts | tokens used | context depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | strong / `gpt-5.6-sol` / `high` (equal to `~/.codex/strong.config.toml`) | present | the findings token, 2 anchored (double emission); the clean token 0 | 0 | 0 | 2 | 2 | 4 new / 0 reopened | 0 | 287,340 | |

### Round 1

**Invocation.** `wsl.exe bash -lc 'bash .../exec/run_round.sh 1'` (LF runner, checked with `file`).
cwd = the worktree (repo read access, `-s read-only --skip-git-repo-check`); stdin = the prompt,
the plan-ledger CUT (sections 0-5, lines 1-306) and `git diff -U8 8acea975..HEAD -- swing tests`
(generated on Windows). codex-cli 0.162.1. Output and exit files pre-created Windows-side.

**Assertions** (`exec\round1\assertions-r1.txt`): exit code MEASURED 0; transcript 1,269,903 bytes;
`model: gpt-5.6-sol` = the profile's `model`; `reasoning effort: high` = the profile's; `^ERROR` 0;
`^tokens used` 1 (287,340); the findings token anchored 2, the clean token 0; no codex process
left. Prompt grep for either token line-initially: 0. Scratch/ledger reach: the transcript's hits
for `.codex|copowers|ledger.md|review-transcripts` are the prompt echo, the ledger-cut echo and
`CLAUDE.md` / `docs/orchestrator-context.md` prose only; no ledger or prior-output file was read.
Content filter: none ("not a safety-layer refusal or rewrite"). Codex could not run pytest
(no interpreter in WSL); it AST-parsed the four Python files.

**Checklist:** 9 HOLDS, item 2 FAILS (on findings R1-2 and R1-3 below).

**Findings and proposed dispositions** (the orchestrator rules; nothing is fixed yet):

| id | sev | finding | proposed disposition |
|---|---|---|---|
| R1-1 | major | On a fill-cleared latch (G2) whose accepted order STILL rests (a partial-fill remainder, or a stale WORKING/indeterminate status), the fill line renders AND the shipped BOOK cancel control for that order renders; G2 says "no cancel control". | DECLINE, cited. The book source is shipped and unchanged by ruling: CHARC 1.2 (b) "the union of attribution and the unexplained accepted rows" and "the existing resting-book cancel controls unchanged (the union keeps them)"; plan Task 4 step 3 "book_controls is the shipped ... comprehension, unchanged"; T4.4 pins exactly one control for a resting accepted order. G2's "NO cancel control" is the gate's own output (no LEDGER control). A resting remainder is a real, cancellable order, so suppressing its book control would gate the RECORD affordance on the fill -- RD's recording-vs-detecting principle. Changing the book source is outside the plan: a director question if wanted. |
| R1-2 | major | `join.indeterminate` is TICKER-wide (`orders.py:874`); `_validity_prompts` `continue`s before both the displaced and current paths, so one indeterminate same-ticker BUY order suppresses the explained lines AND the ledger-keyed control for an accepted, absent, unexplained order on that latch. | FORK -- route; not mine to choose. The skip is SHIPPED, pre-arc (docstring bullet "the ticker's broker status is not INDETERMINATE ... no prompt"), and plan section 1 is silent on it. Branch A: keep it, declare an accepted limitation (the broker's own answer on that ticker is unknown, the same asymmetry as RD item 6's UNKNOWN book; the order the operator just cancelled is itself indeterminate and so in `B`, i.e. G4, with the shipped book control and its status note). Branch B: run the gate (lines + ledger controls only, prompts still suppressed) before the indeterminate skip -- a code change beyond the plan, re-opening the clearance. Live incidence not measurable here (Schwab token expired; the census probe ran on an empty book). |
| R1-3 | minor | The governing-child selection is spelled twice: `_displaced_cycle_prompts` (`answered = max(children, key=_order_key)`) and `_accepted_row_gate`. | FIX (no behaviour change): one helper `_governing_validity_child(place, intents)` called by both. |
| R1-4 | minor | Comments (`LatchOrdersFragmentVM.validity_explained`, the template block) say an explained line is for an "accepted row whose absence" is explained; G2 fires for ANY validity child, before the accepted / book checks. | FIX the wording (#31): a fill explains the place whatever its child says; a recorded cancel explains an accepted row whose order is gone. |

**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d94-cancel\exec\round1\`:
`codex-review-r1.txt` (1,269,903 bytes), `prompt-r1.md` (9,910), `ledger-cut-r1.md` (38,848),
`diff-r1.txt` (80,652), `codex-exit-r1.txt`, `assertions-r1.txt`, `run_round.sh`, `assert_round.sh`.
