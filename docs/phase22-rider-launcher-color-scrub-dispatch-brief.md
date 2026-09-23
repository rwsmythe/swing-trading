# Phase 22 rider — the launcher scrubs the Bash-tool environment leak (`NO_COLOR`, `GIT_EDITOR`) — dispatch brief

**From:** CHARC. **To:** the orchestrator (riders stage: executing directly, no plan loop; no reviewer B — nothing under `swing/`; no Codex round, declared with reason: a two-name addition to a pinned list + its test, suite-covered, the witness is the binding check). **Operator-authorized 2026-09-23 ("Post the rider") after the diagnosis below.** **Cell:** `implementer-sonnet-high`. **Worktree:** `.worktrees/launcher-color-scrub` off `main` at or above this brief's commit. **Rules read from main:** `docs/implementer-dispatch-recipe.md`; the cell names the SHA.

## §0 THE FINDING (CHARC, 2026-09-23, measured on this seat)

Every director seat launched by a ROLLOVER renders without colors or highlights; coa-chess seats do not. Cause: **`NO_COLOR=1` is present in the seat's environment** and Claude Code honors it. It is set NOWHERE in config — verified: not the user or machine environment (`[Environment]::GetEnvironmentVariable` both scopes empty), not any PowerShell profile (grep of all three `$PROFILE` paths), not `.claude/settings*.json` in either project, not the Windows Terminal profile, and the decoded `-EncodedCommand` blob that spawned this seat sets no such variable. **It arrives by inheritance:** Claude Code injects `NO_COLOR=1` and `GIT_EDITOR=true` (beside `CLAUDECODE=1` and the ten session markers) into the shell its Bash tool runs commands in; the rollover sequence (harness §6 act 4) runs `start_directors.ps1` from exactly that shell; `Start-Process wt.exe` / `Start-Process powershell` inherit the parent's environment; the launcher's `$SessionMarkers` scrub removes the ten Claude markers and NOT these two. So a self-launched successor starts with `NO_COLOR=1`, and so does every generation after it. coa-chess is unaffected only because its psmux vehicle hands role windows the psmux SERVER's environment (the operator's own shell), never the launching session's; its `Start-Process` fallback has the same defect.

`GIT_EDITOR=true` rides along: in the seat's own shell it makes any `git commit` without `-m` abort on an empty message. Harmless in our pathspec-with-`-m` discipline; wrong to inherit.

## §1 THE CHANGE, exactly

**C1 — `scripts/start_directors.ps1`:** append `'NO_COLOR'` and `'GIT_EDITOR'` to `$SessionMarkers` (the list at ~`:151-155`), with a comment naming this brief and the mechanism (two lines: injected by the Bash tool, inherited by a self-launch, honored by the successor). Nothing else in the launcher changes; the scrub already runs inside the spawned shell on BOTH vehicles, so the fix covers the wt tab and the plain window identically.

**C2 — `tests/scripts/test_start_directors_orchestrator.py`:** the pinned marker list at ~`:231` gains the two names; the existing assertions at ~`:237-250`, `:292`, `:333` (the `$SessionMarkers` block and the `Remove-Item Env:<name>` stanza in the built launch command for both paths) then cover them with NO new test shape. Add ONE discriminator: a test that builds the launch command and asserts the stanza order keeps the scrub BEFORE `$env:DISABLE_AUTOUPDATER='1'` (the scrub must precede the sets, so a scrubbed name can never be re-set by accident) — pre-fix: the two names absent from the command (fails); post-fix: present, before the sets.

**C3 — nothing under `swing/`; no bootstrap text changes.**

## §2 SCOPE — exactly this, refuse the rest

The two files above. NOT `FORCE_COLOR` (never observed; adding an unobserved name is a roster guess). NOT `TERM` (`xterm-256color`, correct). NOT coa-chess (the operator relays the finding; its fallback path is theirs).

## §3 THE WITNESS (operator-executed, one step)

After merge, at the NEXT rollover of any seat (no seat is rolled for this): the successor's pane renders colors, and `! $env:NO_COLOR` typed into it prints empty. Control: the outgoing seat (pre-rider generation) prints `1`. Until each seat rolls it keeps the inherited value — expected, not a failure.

## §4 RETURN

The ORCHESTRATOR posts the return report to `charc` after QA (suite line with the SHA; the built launch command quoted with both stanzas). CHARC closes on the §3 witness at the first post-rider rollover.
