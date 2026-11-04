# The Codex implementer lane -- arc commissioning brief (CHARC, 2026-11-03)

**Commissioned by the operator 2026-11-03** ("conduct an arc to implement it. Remove the trailer limitation, it is no longer of concern"), in the harness-template merge (`docs/harness-template-merge-2026-11-03-brief.md` section 3 item 2). **Owner:** CHARC (harness FORM). **Dispatcher:** the orchestrator. **Cell:** `implementer-opus-xhigh` (the Stage-0 sandbox probing and the authoring of a cell template are reasoning-dense; the ports are mechanical and could drop to `opus-high` after Stage 0 if the orchestrator splits it). **Worktree:** `.worktrees/codex-lane`, branch `codex-lane` from `main`.

## 0. What this buys

A second implementer lane: a Codex cell (`gpt-6.1-sol` at high, per the template's pins) run as `codex exec` processes in a worktree by a stdlib driver, with a Claude read-only pass as its Reviewer A ("the reviewer is the OTHER model from the implementer" -- both lanes), and two weekly-usage readouts so the orchestrator can send a well-specified build to whichever lane has budget. Cost: one arc, roughly five ported files (~900 lines, template-authored and tested there), one new agent file, three doc edits, two tests files ported, one test retired. The template's own suite for these files is green on this box (382 OK, 2026-11-02).

## 1. Source (read-only)

`C:\Users\rwsmy\harness-template`, `master` @ `4335ff6`: `git -C C:/Users/rwsmy/harness-template show master:<path>`. Files: `scripts/codex_cell.py` (394 lines; `turn` / `commit` / `review`), `scripts/usage_codex.py` (159), `scripts/usage_claude.py` (119), `.claude/agents/implementer-codex-template.md` (116), `docs/codex-reviewer.md` (the "Codex as an IMPLEMENTER" section :344-376 holds the probed facts), `docs/dispatch-recipe.md` (the reviewer-is-the-other-model and process-run-cell paragraphs), `tests/harness/test_codex_cell.py` (197), `tests/harness/test_usage_readouts.py` (86), `.claude/settings.json` (the `Bash(python scripts/usage_claude.py)` allow rule). Never check out, edit or commit in the template clone.

## 2. Stage 0 -- facts before code (the cell's FIRST turn; a return report, not a commit)

Probe, record verbatim in the ledger, STOP and report if any fails:
1. `codex --version` from Git Bash on Windows (observed 2026-11-03: `codex-cli 0.162.1`; `~/.codex/config.toml` exists, `model = "gpt-6-astra"`, `sandbox = "elevated"`). The lane runs the WINDOWS-NATIVE CLI with `-c windows.sandbox="unelevated"`; this instance's older note that Windows `codex exec` is dead (2026-06, sandbox spawn) is superseded if the probe passes -- record which.
2. A throwaway worktree write probe under `-s workspace-write -c windows.sandbox="unelevated"`: a file inside the worktree appears; a write outside the roots is swallowed silently (template fact). Record the writable roots this project's test runner needs (the pip/uv cache; `%TEMP%`).
3. `python -m pytest -m "not slow" -q -x -p no:randomly tests/scripts` INSIDE the sandbox: on Windows the restricted token makes pytest's own 0o700 temp dirs unreadable (template fact). If it fails, the project ships a small pytest plugin that widens the mode, named in the cell's test command; gate runs at the dispatcher's seat never load it. Scope that plugin as part of this arc only if the probe shows it is needed.
4. `codex exec resume` on a session id works and takes no `-m`/`-s`/`--add-dir` (every turn carries the `-c` overrides).
5. Model catalog at this login (`app-server` `model/list`): confirm `gpt-6.1-sol` is served; otherwise pin the served default and say so.

## 3. The ports (TDD; one commit per item; recipe section 2)

- **P1** `scripts/codex_cell.py` -- as-is with the SEAM block tuned: `CODEX_MODEL`/`CODEX_EFFORT` to the Stage-0 pins; `CODEX_FOOTER = "Co-Authored-By: <served model> via Codex <noreply@openai.com>"` (the footer STAYS -- the operator retired the trailer prohibition 2026-11-03); `CLAUDE_MODEL`/`CLAUDE_EFFORT` for the reviewer pass = `opus` / `high` (the recipe's `strong` tier is Codex's; the Claude reviewer for a Codex cell is Opus at high). Tests: `tests/scripts/test_codex_cell.py` from the template's.
- **P2** `scripts/usage_codex.py`, `scripts/usage_claude.py` + `tests/scripts/test_usage_readouts.py`. `usage_claude.py` reads the Claude Code OAuth token from `~/.claude/.credentials.json` once and sends it only to `api.anthropic.com`; **the standing permission for the orchestrator and director sessions to run it is the OPERATOR'S GRANT, given by commissioning this arc 2026-11-03** -- record that sentence in `.claude/settings.json` as the `_comment_usage` the template carries, and add the EXACT allow rule `Bash(python scripts/usage_claude.py)` (no wildcard) to the existing `permissions.allow`. No other credential access.
- **P3** `.claude/agents/implementer-codex-sol-high.md` authored FROM the template's `implementer-codex-template.md`: `<application>` = the Swing Trading project; the binding-rules block from CLAUDE.md's Invariants (DB location outside the Drive dir; `swing/trades/` + `swing/data/` read-only unless the brief scopes a carve-out; no new dependency unless granted by name; `exclusive` briefs run alone); the test command from Stage 0 item 3; the recipe pointer to `docs/implementer-dispatch-recipe.md` by MAIN-repo absolute path (the worktree copy is stale by design -- the same sentence `implementer-opus-high.md` carries). Frontmatter `model: codex/gpt-6.1-sol`, `effort: high` (documentary -- the driver passes them per turn).
- **P4** `docs/codex-reviewer.md` adopted as a reference doc (this instance's REVIEW transport stays the recipe's WSL invocation until a Windows-native review probe is recorded; the doc's "Codex as an IMPLEMENTER" facts are the lane's record). Mark instance deltas `[swing]`.
- **P5** `docs/implementer-dispatch-recipe.md`: add to section 3 the one rule "Two implementer lanes, one rule: the reviewer is the OTHER model from the implementer. A Claude cell's Reviewer A is the Codex reviewer; a Codex cell's Reviewer A is a Claude pass its dispatcher runs between the cell's turns (`scripts/codex_cell.py review`). A Codex cell never runs the staged Codex invocation on its own diff." Section 2A: a row for the Codex lane (well-specified builds only: a brief that fixes interfaces, algorithms and tests; never a package that designs or touches a frozen interface) and the lane TIEBREAK (read both weekly readouts; send the build to the lane with the lower `pace`). Section 5A's process-run-cell paragraph: replace its "NOT adopted here" parenthetical with the lane's name.
- **P6** Retire `tests/integration/test_phase14_sub_bundle_1_cross_item.py::test_sub_bundle_1_branch_has_no_co_authored_by_trailers` (delete the test, keep the file's other tests). Grep `tests/`, `scripts/`, `.claude/` for any other trailer pin and retire it the same way; list each in the return report.

## 4. Locks

- Nothing under `swing/`. No schema. No change to `scripts/role_mail.py`, the hooks, or the launcher (the merge cell on `harness-merge` owns those this week; rebase onto `main` after it merges if the arc lands second).
- The ORCHESTRATOR fills its own `docs/orchestrator-context.md` dispatch-model text and the CLAUDE.md Conventions line ("No Claude co-author footer" -> retired) -- CONTENT, not this cell's; the cell FLAGS both in its return report.
- `codex_cell.py review` runs `claude -p` with a read-only tool policy; never `--bare`.

## 5. Gate

Reviewer A to convergence (the WSL Codex chain, recipe section 3, `strong`); Reviewer B at the orchestrator's seat; `python -m pytest -m "not slow" -q` green on the merged head; `ruff check scripts/`. **Operator witness after merge (step by step, one step per message):** one Codex cell turn on a toy brief in a scratch worktree (a one-function change with a test), the driver's `commit` producing a commit whose `%(trailers)` shows the model footer, the `review` pass returning a JSON verdict, and both usage readouts printing a reading. CHARC's plan-stage read before executing (post the plan to charc; RD is not a tripwire owner here).

## 6. Decisions already made (do not reopen)

Trailer prohibition retired (operator 2026-11-03). Launcher vehicle stays Windows Terminal (operator 2026-11-03) -- the lane runs cells as processes, not psmux windows. The 120-char subject cap (operator 2026-11-03) is the merge cell's. `cell_depth.py` is not this arc's.
