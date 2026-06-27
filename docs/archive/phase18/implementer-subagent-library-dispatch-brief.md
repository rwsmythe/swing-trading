# Implementer subagent library — build dispatch brief

**Authored:** 2026-06-14 by CHARC. **Tripwire:** harness architecture (the dispatch substrate) — CHARC-authored, so the architecture pass IS this brief. Not a §3 swing/-tripwire (no swing/ code, no schema, no dependency). **Cycle:** focused executing (design is settled — no brainstorm/plan cycle). **Origin:** the C-e amendment of `docs/orchestrator-subagent-dispatch-charc-architecture-pass.md` (`640cb2e5`); operator-directed library design.
**Why now:** this library is the prerequisite for executing-via-sub-agent (C-a) and the durable home for the implementer-dispatch protocol currently re-inlined per prompt. Sequence: build → **operator restarts the orchestrator to load the new agent-defs** → 18-B executing proceeds via the library.

## Deliverable (two parts)

### Part 1 — ONE canonical recipe doc: `docs/implementer-dispatch-recipe.md`
The invariant implementer-dispatch protocol, consolidated ONCE (not re-inlined per prompt). It is the SINGLE POINT OF FAILURE for all sub-agent dispatch — build it carefully; it gets a CHARC review (below). Consolidate from the existing memories + the 18-B pilot findings (do NOT re-derive):
- **Worktree:** create/use `<repo>/.worktrees/<name>` — NOT the Agent tool's `isolation: worktree` (C-b); the editable-install verify step; cleanup at end.
- **TDD:** failing test → see fail → minimal impl → see pass → commit, per task. Conventional commits; **ZERO `Co-Authored-By`**; no `--no-verify`; final `-m` paragraph plain prose (the trailer-parse hazard).
- **The WSL-Codex recipe (verbatim, the load-bearing part):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; …'` (the PATH prefix is REQUIRED — memory `feedback_wsl_native_codex_invocation`); `codex --version` liveness probe; the worktree `.git` is unreachable from WSL so PRE-GENERATE the diff on Windows + tell Codex not to run git; long prompts via STDIN (`codex exec - < file`, NOT as an argv arg — the word-split hazard); `--skip-git-repo-check` when run outside a repo dir; stage prompt files into `$HOME` via `/mnt/c` (WSL `/tmp` ≠ Windows `/tmp` — pilot friction). Run Codex **to convergence** (`NO_NEW_CRITICAL_MAJOR`, no round cap), and **persist EVERY round's RESPONSE** to a gitignored on-disk file (`.copowers-findings.md` / `.codex-review-*.md`) — memory `feedback_implementer_persist_codex_responses`.
- **Return:** report to the ORCHESTRATOR as the final message (structured: per-task commits, test counts read off the final head, Codex rounds + verdict, deviations, locks-honored). NEVER post to a director inbox (the comms taxonomy).
- **Discipline:** honor the dispatch brief's locks; QA-against-disk mindset; flag-don't-absorb on a STOP condition (route brief questions back up).
- It explicitly notes: a sub-agent does NOT inherit the orchestrator's memory/CLAUDE.md, which is WHY this recipe is a doc the cell bodies tell the sub-agent to read.

### Part 2 — the model×effort cell library: `.claude/agents/implementer-<model>-<effort>.md` (tracked)
Each cell is THIN: frontmatter only + a body that says "read and follow `docs/implementer-dispatch-recipe.md`, then execute the dispatched task." NO recipe duplication in the cells (DRY / C1). Frontmatter per cell:
- `name: implementer-<model>-<effort>`
- `description:` a when-to-use line keyed to the model/effort rubric (so the orchestrator selects by TASK requirements — reasoning-density/scope/leverage — NOT by phase).
- `model:` the alias (`opus` / `sonnet`) — aliases, not full ids (they rotate as models ship).
- `effort:` the level (`low`/`med`/`high`/`xhigh`/`max`).
- `tools:` the full implementer set (the sub-agent writes code, runs tests, commits, runs WSL-Codex): at minimum `Read, Edit, Write, Bash, Glob, Grep` (+ TodoWrite/Task if used). Confirm the exact list spawns cleanly.

**Proposed initial cells (operator approves/amends this set at dispatch):**
| cell | for (rubric) |
|---|---|
| `implementer-opus-max` | highest-stakes: measurement-chain / irreversible executing |
| `implementer-opus-xhigh` | high-reasoning-density / writing-plans / gate-blocked |
| `implementer-opus-high` | locked-plan disciplined TDD of a small change (the executing default) |
| `implementer-sonnet-high` | mechanical-but-non-trivial |
| `implementer-sonnet-med` | genuinely mechanical / large-but-simple volume |
(Fable cells deferred — ITAR-unavailable. Add/trim cells freely; the set is the operator's.)

## Locks / notes
- Agent-defs live in `.claude/agents/` and ARE tracked (gitignore negation `!.claude/agents/*.md` confirmed; pattern-labeler precedent). Verify the new files are tracked.
- **Verification is config-correctness + functional, NOT runtime-effort-readout.** A running sub-agent's effort/model is config, not observable (18-B pilot finding) — so "verify the cell works" = (a) frontmatter correct, (b) tracked, (c) a SMOKE SPAWN of one cell (e.g. `implementer-sonnet-med`) on a trivial throwaway task confirms it reads the recipe + acts + returns; NOT an attempt to read its effort at runtime (impossible).
- The recipe doc is the SPOF → it gets a **light Codex pass for completeness** + a **CHARC review checkpoint** before the library is declared ready.
- No swing/ change, no schema, no dependency. No measurement-chain touch → RD not in this gate.

## Gate + sequence
1. Orchestrator builds Part 1 + Part 2; QA-against-disk (cells tracked, frontmatter correct, recipe complete, smoke-spawn passes).
2. **CHARC reviews the recipe doc** (the SPOF) + spot-checks the cells. (No RD — harness tooling, not measurement.)
3. Return report → `charc, operator` (`--type return_report`) after QA.
4. **Operator restarts the orchestrator** to load the new agent-defs (agent-defs load at session start).
5. 18-B executing then proceeds via a library cell (executing-via-sub-agent now cleared — the two pilot risks are addressed).
