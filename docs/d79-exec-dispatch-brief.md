# D79: the exit form records the SELECTED broker order's fill, once -- EXECUTING dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Mission.** Execute the converged, plan-stage-cleared D79 plan, T1-T8, TDD. Then run Reviewer A to convergence and return. **T9's operator-witnessed browser check is NOT yours.** The orchestrator runs it with the operator after QA. From T9 you do only step 1 (the gates) and prepare the census commands (steps 4-5).

**Authority:** the operator's executing word, "dispatch D79", relayed verbatim by CHARC as pre-authorized courier (`comms/orchestrator/read/20261019T022435Z-charc-d79-operator-word-dispatch-executing-rel.md`).

**Cell:** `implementer-opus-high`. This is above the sonnet-high executing default, for the stated reason that the arc changes the transaction shape of a money-bearing write and adds a two-POST confirm protocol with a Schwab re-fetch, where a wrong implementation reads correct. RD and CHARC concur.

**Worktree:** `C:\Users\rwsmy\swing-trading\.worktrees\d79-exec`, branch `d79-exec`, cut by the orchestrator from `d79-plan` @ `618d7b04` (the edited, cleared plan). `cd` into it; do not create another. **Your diff base is `618d7b04`.**

## 0. Read first, in this order

1. **The rule docs, read from the MAIN repo** (the worktree's copies predate a docs-only delta). Main was at `5a0b78b3` when this brief was written:
   - `C:\Users\rwsmy\swing-trading\docs\implementer-dispatch-recipe.md`, in full. Section 3 binds: the strong tier, repo access, the five per-round assertions, copy-per-round, scratch relocation, return at every round gate, round-5 check-in, stop at the first clean verdict.
   - `C:\Users\rwsmy\swing-trading\CLAUDE.md`, the Gotchas. Load-bearing here: the transaction family (`in_transaction` reject, not auto-detect; the rolled-back rowid; the writer quoting itself; Python vs SQLite rounding); the hidden-anchor family (round-trip through confirm `form_values`, the 4-tier ladder, `selected_X_audit_id` as an audit trail); the HTMX browser-only surfaces; cp1252 encode.
   - `C:\Users\rwsmy\swing-trading\docs\tool-director-context.md`, register row **D73**: the interrupt-at-cleanup template ruling that T1's helper must carry.
2. **The plan, the BINDING task ladder:** `docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md` in your worktree (531 lines, T1-T9, 48 roster rows including 4a).
3. **The ledger:** `docs/superpowers/plans/2026-10-19-d79-exit-identity.plan-ledger.md` in your worktree. It holds every ruling, block-quoted; the plan cites them by section. Read the "Plan-stage reviews" and "Post-review plan edits" sections closely.
4. **The round-0 probes,** for fixture shapes: `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\round0\`.

## 1. Before you write code

- Re-ground every file and line anchor in the plan against the code. Line numbers drift; the plan was read on `ed3d4f08`, and `swing/` has not changed since.
- If a plan step cannot be implemented as written, or two rulings conflict on the code, STOP and return it as a fork with both branches. Do not choose for yourself.
- **Run the full fast suite ONCE on the untouched base** and record the pass/skip/fail counts as your baseline. The suite takes ~11 min and outlives the 600 s Bash timeout, so background it and read the saved output.

## 2. Execute T1-T8

- **TDD per plan task:** RED (see it fail the RIGHT way, as the plan's pre-fix arithmetic predicts), then GREEN, then commit with the task id (`feat(trades): T1 -- ...`, `fix(web): T6 -- ...`, `test(cli): T8 -- ...`).
- **Commits:** one red-to-green cycle per logical change; bare git from the worktree cwd; no `Co-Authored-By`, no `--no-verify`, no amend; the final `-m` paragraph plain prose.
- **The envelope is the plan's "Declared envelope".** In particular:
  - nothing under `swing/data/`;
  - no change to `insert_fill_with_event`, the split handler, or the entry path;
  - no schema and no migration;
  - **no ADDED file under `swing/`** (new symbols live in existing modules; new files are tests only).
- **T6's supersession lists:** after T6-T7, run `tests/web/test_routes/` in full and classify EVERY red as either SUPERSEDED (rewritten by replacement; named in the commit body) or REGRESSION (fixed in code). Both lists go in your return report.
- **T9, your part only:**
  - step 1: the full suite green on the final head, `ruff check swing/` clean, and the trailer audit empty;
  - steps 4-5: verify the census SQL's column names against the live DDL (`mode=ro` read of `~/swing-data/swing.db` schema only), and write both census commands into the exec ledger, ready to run.
  - **Do NOT** start a web server, copy the live DB, or touch a browser.

## 3. Review (recipe section 3) -- Reviewer A only; B is the orchestrator's

- **Order:** the full fast suite GREEN first, then the review.
- **Tier:** `strong`, with REPO ACCESS (production code). Use the cold-audit form `codex exec -p strong -s read-only --skip-git-repo-check`, reading the changed files directly, or a stdin bundle carrying the plan's reference-graph files (plan "Executing posture"). Assert the banner model equals the `model =` line of `~/.codex/strong.config.toml` (today `gpt-5.6-sol`) at effort `high`. No `-p` fallback: a profile that does not resolve STOPS you.
- **The five per-round assertions** (banner model and effort, `^ERROR`=0, the anchored `^tokens used` footer, exactly one distinct anchored verdict token) all bind, and the process must have exited before you read the transcript. A round that fails them does not count.
- **The prompt carries:** the plan's declared envelope and accepted limitations AL-1..AL-9, each WITH its reason, with challenge invited; findings outside the envelope TAGGED, never suppressed; a prohibition on reading prior-round findings; and the two-token verdict as the final line, described but never written line-initially.
- **Scratch:** keep `.codex-*` and `.copowers-findings.md` OUT of the worktree during the loop, and restore them at the end.
- **Evidence:** copy each round's transcript, prompt and findings to `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\exec\` the moment its assertions pass.
- **Ledger:** commit, per round, the cumulative round table and every finding's adjudication to `docs/superpowers/plans/2026-10-19-d79-exit-identity.exec-ledger.md`. That is a NEW file; the plan ledger is not touched. Leave the depth column for the orchestrator.
- **STOP AND RETURN AT EVERY COUNTED-ROUND GATE,** with that round's ledger row as your final message. The orchestrator reads your depth and resumes you, or re-dispatches a fresh cell off your committed ledger past the 400K cap.
- **Stopping rules:** STOP at the first `NO_NEW_CRITICAL_MAJOR` round. Fix post-convergence minors without another round, and name them. At round 5, report the ledger for approval to continue. Two consecutive minors-only rounds mean you already converged.
- **After convergence:** run the full fast suite again on the final head and read the result.

## 4. What the merge gate will read (build toward it)

- the A transcripts and the per-round assertions;
- `git diff --stat 618d7b04..HEAD -- swing/`, which must show no ADDED file under `swing/`;
- no migration;
- `%(trailers)` empty across `618d7b04..HEAD`;
- the D73-shape helper visible in the diff (`raise original from cleanup_error` under `not isinstance(original, Exception)`);
- the two census commands, ready for T9.

## 5. Return report (your final chat message, to the orchestrator only; NEVER post to any mailbox, never run role_mail.py)

Per recipe section 4:
- commits in order (SHA + task id);
- the baseline and final-head suite counts, read off the output;
- the round ledger with the per-round assertions and the `tokens used` sum (the spend line);
- the T6 superseded vs regression lists;
- every plan condition as honored on disk (file:line);
- deviations and anything flagged-not-fixed;
- every follow-on with an explicit disposition.

## 6. If you get stuck

- **No live DB writes,** ever. `mode=ro` schema reads only.
- **STOP and return** if:
  - a fork appears;
  - the `strong` profile does not resolve;
  - WSL Codex is unreachable;
  - the work would cross the declared envelope.
