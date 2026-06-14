# Implementer dispatch recipe — the ONE canonical protocol

**Audience:** a dispatched implementer (a sub-agent spawned via a `.claude/agents/implementer-<model>-<effort>` cell, OR a fresh Claude Code instance launched by the operator). You have **NO prior conversation context** and you do **NOT inherit the orchestrator's memory or CLAUDE.md** — that is exactly why this protocol is a doc you are told to read. Read it in full, then execute your dispatched task / brief.

**Status:** the single source of truth for sub-agent + window implementer dispatch (the protocol that used to be re-inlined per prompt). Harness tooling, CHARC-owned. If anything here conflicts with your specific dispatch brief, the brief's *task scope* wins but these *disciplines* still bind — if they truly conflict, STOP and ask the orchestrator.

---

## 0. The shape of a dispatch
1. Read this recipe, the repo's **`CLAUDE.md`** (load-bearing — it carries the project gotchas + conventions), and your dispatch brief/task in full. Re-ground every file/line anchor against live code before editing (line numbers drift).
2. Work in an isolated worktree (§1).
3. Execute the task TDD, one red→green→commit cycle per logical change (§2).
4. Run the Codex adversarial review to convergence and persist every response (§3) — when your brief calls for it (writing-plans / executing-plans / any code-shipping task).
5. Return a structured report to the ORCHESTRATOR as your final chat message (§4). Do NOT post to any role mailbox.
6. Honor the disciplines in §5.

---

## 1. Worktree (isolation)
- Create/use a worktree at **`<repo>/.worktrees/<name>`** — `git worktree add -b <name> .worktrees/<name> <base>`, where `<base>` is the base your brief specifies (a named commit / `BASELINE_SHA` if given, else `main`). The `<base>` arg is REQUIRED — without it `git worktree add` branches from current `HEAD`. Or reuse the existing worktree if your brief says the plan was committed there. The orchestrator owns main-currency at merge (it rebases your branch onto `main` before the `--ff-only` merge), so don't worry about `main` advancing while you work. **NEVER** use the Agent tool's `isolation: worktree` (it auto-creates a temp worktree outside this path, bypassing the editable-install verify, the cleanup script, and the gitignore coverage). The path `.worktrees/<name>` is binding — not `.claude/worktrees/`, not a repo-sibling.
- **Editable-install gotcha:** the `swing` package is editable-installed from the MAIN repo path, so a CLI entry point (`swing ...`) run from a worktree resolves the MAIN tree, not the worktree's code. For runtime/CLI verification from inside the worktree, run the package directly: PowerShell `$env:PYTHONPATH="."; python -m swing.cli <cmd>` / Bash `PYTHONPATH=. python -m swing.cli <cmd>`. **Pytest is NOT affected** (cwd-based discovery) — run `python -m pytest -m "not slow" -q` from inside the worktree and it tests the worktree's code.
- Leave the worktree intact at the end (the orchestrator rebases onto main + `merge --ff-only` + re-runs the suite on the merged head). Do NOT merge or push yourself.

## 2. TDD + commit conventions
- **TDD:** write the failing test → run it, SEE it fail (the right way) → minimal implementation → run it, SEE it pass → commit. One red→green cycle per logical change. Compute a regression test's assertion under BOTH the pre-fix and post-fix paths to prove it distinguishes (a test that passes under both is worthless).
- **Conventional commits** carrying the task id: `feat(area): Task X.Y — …`, `fix(area): Codex R1 Major 2 — …`, `refactor(...)`, `test(...)`, `style(...)`.
- **ZERO `Co-Authored-By`** — no co-author footer, ever. **No `--no-verify`. No amend** (new commit per fix). Before handoff, verify the WHOLE dispatch is trailer-clean: `git log <base>..HEAD --format='%H%n%(trailers)'` — every commit must show empty trailers. **If a forbidden trailer slipped in** (`Co-Authored-By`, or a prose `Word:` final paragraph git mis-parsed as a trailer): **STOP and flag it in the return report** — do NOT `--no-verify`, hide it, or silently hand off. The orchestrator resolves it at merge (amend + force-with-lease); the "no amend" rule is precisely why this is a stop-and-flag, not a self-fix.
- **Trailer-parse hazard:** keep the FINAL `-m` paragraph plain prose — a paragraph starting `Word:` (e.g. `Fixes:`) is parsed by git as a trailer and pollutes the zero-`Co-Authored-By` audit.
- **Ruff:** the lint gate is `ruff check swing/` (the `swing/` tree only). Introduce no new violations there. Test-file lint is out of scope unless your brief says otherwise; match each test file's existing style (≤100-char lines, local imports) so you add no new violation.
- **ASCII discipline:** user-facing strings flowing through stdout/CLI must be ASCII (Windows cp1252 crashes on `§ → ↔ ✓ ✗`, em-dash, fractions). pytest `capsys` hides this — prefer ASCII swaps in added code.
- **WRITING-PLANS phases commit the plan ONCE at convergence** (added 2026-06-14): a writing-plans dispatch is plan-only — write the plan, run Codex to convergence, then make a SINGLE `docs(plan): …` commit of the converged plan. Do NOT commit the plan once per Codex round (18-C's writing-plans produced 18 per-round commits — verbose history with no value). The converged plan is the deliverable; the round-by-round iteration belongs in `.copowers-findings.md`, not the git history.

## 3. The WSL-Codex adversarial review (the load-bearing part — verbatim)
The MCP `codex` tools are dead in this environment; the working transport is the **WSL-native Codex CLI**. The copowers `adversarial-critic` Skill scaffolding may be **absent in a sub-agent** — if so, HAND-RUN the loop exactly as below.

**Liveness probe FIRST (the PATH prefix is REQUIRED — `~/.bashrc` does NOT reliably prepend node22 on its own):**
```
wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex --version'
```
Expect a `codex-cli <version>` line (0.135.0 at time of writing) — ANY successful version output proves liveness; don't hard-fail on a newer version. The check is that codex resolves the NATIVE binary, not the dead Windows npm shim. Use `codex --version` as the liveness proof, NOT `command -v codex` (which can resolve the shim `/mnt/c/.../npm/codex` → `node: not found`, or print empty even when codex runs). (Run these from your Windows shell — the Bash tool is Git Bash invoking `wsl.exe`. If you are already inside a WSL shell, drop the `wsl.exe bash -ilc` wrapper and run `export PATH=…; codex …` directly.)

**Staging (pilot frictions — do these or the call fails):**
- The worktree's `.git` is a *file* pointing at a Windows path WSL git CANNOT resolve, so **never let Codex run git**: pass **`--skip-git-repo-check`** and **pre-generate the diff from the WINDOWS shell** (Git Bash or PowerShell, run IN the worktree dir — NOT from WSL bash, which cannot resolve the worktree `.git`): `git diff -U8 <base>..HEAD > .codex-diff.txt`, where **`<base>`** is the baseline your brief gives you (the worktree's branch point / the plan-commit / an orchestrator-provided `BASELINE_SHA`) — i.e. the commit your work started from, so the diff is exactly YOUR changes. (Ensure your work is COMMITTED first — a clean `git status` — so no final uncommitted edit escapes the review.)
- **PRIMARY — pipe everything via STDIN inside the WSL+PATH wrapper; Codex needs to READ no repo files (everything arrives via stdin).** Redirect Codex's output to a FILE (never the terminal — its glyphs crash Windows cp1252 stdout). `<...>` below are placeholders:
  ```
  wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; cat <prompt>.md .codex-diff.txt [optional source-excerpt files] | codex exec -s read-only --skip-git-repo-check - > .codex-review-r<N>.txt 2>&1'
  ```
  (trailing `-` reads stdin.) Then append `.codex-review-r<N>.txt` VERBATIM into `.copowers-findings.md`, followed by YOUR per-finding adjudication for that round (so the file holds raw Codex output + your dispositions — the persist step). These `.codex-*` / `.copowers-findings.md` names are all gitignored, so they don't dirty the worktree for the §2 clean-status / trailer check. `cat` runs in WSL and reads `/mnt/c/...` fine, so you can cat straight from the worktree path and Codex never touches the filesystem — cwd/paths are irrelevant to CODEX (it reads stdin), though `cat` itself still needs resolvable paths (use absolute `/mnt/c/...` paths, or run from a WSL-visible cwd). A bare `cat | codex` copied into a Windows/PowerShell shell will fail or hit the dead npm shim — KEEP the `wsl.exe bash -ilc 'export PATH=…; …'` wrapper. **Never** pass the prompt as an argv arg (`codex exec "$(cat …)"` word-splits / dies on parens/special chars). (This is the path the recipe-doc review itself used — validated.)
- **FALLBACK — only when the diff/sources are too large to inline** and Codex must READ files itself: copy them into WSL **`$HOME`** (NOT `/mnt/c`, whose reads can be flaky under Codex's sandbox — and WSL `/tmp` ≠ Windows `/tmp`), run `codex` from `$HOME`, and reference the `$HOME` paths in the prompt. For more than one or two files, write a small **staging script** and run it (a long inline `-ilc '...'` with many files is var-expansion-fragile).

**Run to convergence, persist EVERY response:**
- Iterate rounds until **`NO_NEW_CRITICAL_MAJOR`** (zero new critical/major). The project's old 5-round cap is **suspended** — keep going while majors surface; don't pad after convergence.
- After EACH round, append the round's **full verbatim Codex RESPONSE** (findings + your per-finding adjudication + the verdict line) to a **gitignored** on-disk file: `.copowers-findings.md` at the worktree root (the `## Round N` / `### Codex response` / `### Verdict` shape). The orchestrator independently verifies convergence by reading this REAL transcript at QA — so persist responses, not just prompts; do not claim convergence without them.
- Codex output is large and contains glyphs that crash Python's cp1252 stdout — write it to a file and Read it; don't `print()` it.

## 4. Return report (to the ORCHESTRATOR only)
Your FINAL chat message is the return report. **Do NOT run `scripts/role_mail.py`, do NOT post to any director (charc/rd) inbox, do NOT use `--from orchestrator`** — the orchestrator QAs your work and posts to the directors after QA (the comms taxonomy: you report up in chat; authority/comms routing is the orchestrator's). Include:
- Per-task commits (SHA + task id) in shipped order.
- Test counts READ OFF THE FINAL HEAD (`pytest -m "not slow" -q` tail) — never carry a mid-work or branch count forward.
- Codex rounds + the final verdict + the `.copowers-findings.md` path.
- Every LOCK / brief condition, stated as honored-on-disk (file:line where it matters).
- Deviations, V1 simplifications (with the V2 dependency), and anything you flagged-not-fixed.

## 5. Disciplines
- **Honor the brief's locks.** They are binding. A defect/gap OUTSIDE your scope gets FLAGGED in the return report (or, if your brief says so, a `role_mail` fyi the ORCHESTRATOR will send) — never fixed inline (mid-session scope creep), never silently absorbed.
- **STOP-and-ask** if a brief premise doesn't match live code, or a fix would need a schema/migration/new dependency your brief didn't authorize (those cross a tripwire → route back up). Report the discrepancy; do not work around it.
- **QA-against-disk mindset:** verify data shapes against the live DB/code + real emitter output, not just the spec text; derive fixtures from real emitter output.
- **You do NOT inherit the orchestrator's memory or CLAUDE.md.** Everything load-bearing for the dispatch is in this recipe + your brief + the repo's `CLAUDE.md` (read it — it carries the project gotchas). When in doubt, read the code.
