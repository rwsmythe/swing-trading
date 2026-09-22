# Orchestrator handoff — 2026-09-22 — D56 merged and closed; the cell_depth rider (now model-id + build) is the next dispatch

**Supersedes** `orchestrator-handoff-2026-09-15-d32-d50-d57-merged.md`.
**From:** the generation launched 2026-09-15 07:20 HST (session `daef757e`, map name `swing-orchestrator-20260915-0720`).
**Rolled at:** 385,832 (`cell_depth.py --sessions --live 1`), under the 400K trigger, on the operator's word at a clean boundary — the MIRROR rule is why nothing new was dispatched: the owed rider would have started with ~14K of headroom and its QA would have been yours anyway.
**Precondition met:** no cell in flight (`cell_depth --live 2`: nothing written in 2h), no worktree but `main`, no ruling outstanding, inbox empty at act 1.
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` (its §"Currently in-flight" was rewritten from disk at the close of the 09-15 sitting and again for D53.1/CHARC's rollover) → this file.

**Every fact below was re-derived from disk at write time. Re-derive; do not carry these numbers.**

---

## 1. STATE

- **`main` @ `e3f9054f`, 1 commit AHEAD of origin, UNPUSHED** (CHARC's own charter §2.11 commit). Zero `Co-Authored-By` by trailer KEY in that range. Push is the operator's to authorize — ask.
- Tree clean except the untracked coa-chess finding `docs/cli-autoupdate-run-poisoning-finding-coa.md` (not ours, never was).
- **Live DB schema v38** (`schema_version` = 38; `EXPECTED_SCHEMA_VERSION` = 38). Pipeline runs through **181**, `state=complete`, `export_status=ok` on 179/180/181 — **D42's export failure has not recurred**; do not carry the old "failed on every run since 160" line forward.
- **THE BOOK IS FLAT. `trades` holds 28 rows, ALL `reviewed`; ZERO open positions.** The five that were live on 09-15 (23 CADL, 24 RHI, 25 OII, 26 NRIX, 28 PBF) closed during the idle week — four were reviewed on 2026-09-22 itself (09:31-09:33). This is the single biggest change since the last handoff and it was found by re-deriving, not by being told.
- Latest evaluation run **167**: 37 `skip`, 21 `watch`, 1 `excluded`, **ZERO `aplus`** — the admitting gate stays open.
- Reconciliation discrepancies by `resolution` (lifetime rows): 43 acknowledged_immaterial, 21 operator_resolved_ambiguity, 14 journal_corrected, 6 auto_corrected_from_schwab, 6 operator_overridden, **5 `pending_ambiguity_resolution`, 1 `unresolved`** — the last two are the open ones; nobody has looked at them this sitting.

## 2. WHAT THIS GENERATION DID

| Item | Result |
|---|---|
| **F4 step (b)** (D32 disposition) | **DONE.** 21 twin CLI backup copies deleted ONE PAIR AT A TIME on a delete-time re-hash of BOTH members + a sidecar check printed into the ledger beside each delete. **4,617,224,192 bytes freed; 21 of 21 proven; zero stops.** Rows 46-50 by the operator's hand, 52-68 delegated to me mid-sitting (recorded in the ledger). The 3 withheld true twins and everything else KEPT. Ledger `docs/phase22-arc-d32-d50-ledger.md`. |
| **D57** | CLOSED by CHARC on a witness THIS SEAT WAS — his ping woke me as a new turn in ~2 s with zero Monitor calls; the mail post alone produced no record. |
| **D56** | **MERGED `d12aa7b6` (`--no-ff`) and CLOSED by CHARC at `dde335c2`.** Error regions on the review form + the exemplars page; one trough-1 helper feeding both the C3 pre-fill and the refusal text. Merged-head suite **12,469 passed / 13 skipped / 0 failed**, ruff clean. Live witness **3 of 3 with a measured zero-write proof** (`pattern_exemplars` 35/35 across four read-only measurements). Ledger `docs/phase22-arc-d56-ledger.md`; evidence `~/swing-data/review-transcripts/d56-exec/` (12 files). |
| **D53.1** | CLOSED by CHARC at run 177; I re-read both non-zero DBW rows `mode=ro` and confirmed `window_start_date == trough_1_date` (7860 LILAK 2026-08-20, 7865 NEOG 2026-08-06). |
| Teardown | Worktree + branch gone, branch proven contained in `main` first, evidence reconciled by sha256 with **two worktree-only files recovered** (`.codex-bundle-r2.txt`, `.codex-diff.txt` — the bundle and diff actually fed to Reviewer A). |

**Spend, D56:** Reviewer A 422,575 (R2 counted 212,208 + R1 disqualified 210,367); Reviewer B 191,332; cell dispatches 355,019 + 411,423.

## 3. AUTHORITIES GRANTED BY CELL MESSAGE (state, not history)

All cells finished; **no grant is open.** Record: one fix leg authorized to the D56 cell by message — Reviewer B's B-1 (the F-B three-kind pin) and B-2 (the coverage docstring), declared as post-convergence test-only corrections with **no further Codex round**, verified by the suite.

## 4. QUEUE — owners named

1. **THE cell_depth RIDER — YOURS, the next dispatch.** Now two riders in one, per the new CHARC's FYI of 2026-09-22 (`comms/orchestrator/read/20260922T222308Z-charc-*`, decision-of-record charter §2.11): (a) `cell_depth.py --sessions` and `--live` print the **BUILD** (`version`) and the **RESOLVED MODEL ID** (`model`) per session and per cell, read from the same transcript records the depth sum already reads; (b) the recipe's accept/return record names the cell's resolved model id, **dispatcher-read** (a cell cannot see its own); (c) a **POSITIVE CONTROL at the first Opus 5.5 cell accept** — count `"type":"text"` vs `"type":"thinking"` records in that cell's transcript and report both with the command. Tests-only + `scripts/`; **no Codex round required — declare it with the reason on the row.** Gates nothing.
2. **The `opus` alias FLOATS and we accept it** (operator-ruled 2026-09-22). Claude Code 2.1.280 resolves `opus` → Opus 5.5; your launch row and the three `implementer-opus-*` cells use the alias, so every opus cell you dispatch is Opus 5.5 with no file change. **Do NOT pin.** Effort is explicit everywhere, so 5.5's medium default reaches nothing. Two builds are live again (2.1.272 in-process for seats launched before, 2.1.280 on disk); any seat launched from now on is 2.1.280 — **including you.**
3. **Tiny riders still mine→yours:** the `_is_head` version-mirror rename (its trigger fired at the 0038 merge; its own commit, NEVER beside a version bump); the non-ASCII em-dash in `swing/cli.py`'s pre-18 WARN line.
4. **CHARC's** (seat `swing-charc-20260915-1803`): the D32 production proof at the **22-B** witness; **D51 before 22-B**; the D58 shape ruling when sequenced; the **Gotchas cap compression** (§Gotchas at the ~55K soft cap — and inside it, the **"`swing db-migrate` writes TWO backups" gotcha is now FALSE**: D32 made it one, echoed); the **D56 residual** banked on the closed row (the exemplars route's 500 path, `routes/patterns.py:264,273`, has NO test — found by grepping for the raise's message text while correcting a docstring that claimed it was covered); then D55, B-2, `ReservedJournalFieldError`'s bare base, D42, D46, D45, D44/D47, the D39 sweep.
5. The 5 `pending_ambiguity_resolution` + 1 `unresolved` discrepancies above — nobody's, formally. Raise them rather than assume they are known.

## 5. WHAT WILL BITE YOU

- **THE WAKE CUE IS THE PING (D57, closed).** Never arm an inbox Monitor. After EVERY `role_mail post`, run the `ping ->` line(s) it prints — one SendMessage per recipient, to the EXACT name printed. **`comms/.sessions.json` lags a rollover:** it named the retired CHARC seat for a day after he rolled. Trust the printed line, never a remembered name. Directors at write time: `swing-charc-20260915-1803` (rolled in, on the ping convention) and `director-rd-20260914-1932` (**RD has NOT rolled** — still the old name, still the interim Monitor rule).
- **A pin can read as coverage and discriminate nothing.** D56's whole lesson: Reviewer B passed the CODE and failed a TEST — CHARC's ruled three-row-kind pin had been written over the two kinds where the old and new values COINCIDE, so reverting the fix left it green. Ask of every new pin: *on which input do the pre-fix and post-fix values actually differ?*
- **A review round's prompt can disqualify its own round.** D56's Reviewer A R1 wrote the verdict tokens line-initially, so the anchored grep matched the prompt's echo in the transcript. Its findings were still acted on — the gate is on ENDING the loop, not on using the content.
- **A register row's line citations are a lead, not evidence.** D56's row cited the exemplars route's lines as the review route's — CHARC's own, corrected at `ac3f6a80` only because round 0 read the code instead of the citation. Round 0 is a PREMISE census; run it.
- **`!` runs in BASH, not PowerShell.** The first F4 delete was handed to the operator as `Remove-Item` and died with `command not found`; give operator commands as `! rm -v '<path>'`. Verify with a listing before the retry — it deleted nothing, but only the listing proved that.
- **Heredoc-driven `python - <<EOF` edits can silently no-op here** (two edits and a ledger line vanished without an error this sitting). Use the Edit tool for file edits, and re-read after.
- **Git Bash mangles `/mnt/c/...` for `wsl.exe`** — launch WSL runners from PowerShell (`wsl.exe bash /mnt/c/.../run.sh`), runner scripts written with `printf '%s\n'` (LF), output + exit files pre-created Windows-side.
- **`git worktree remove` can leave the DIRECTORY behind on Windows** while de-registering the worktree (permission denied on the delete). `git worktree prune` + `rmdir` the empty husk; `git branch -d` (never `-D`) after proving containment.
- **Suite:** `-n 4` in this seat (D52 as amended); `-n auto` is memory-killed on this box. The merged-head run is the binding gate, never a branch count.
- Stash stack is shared across worktrees and holds one unrelated 2026-05-31 entry — **never pop it**.
- Everything in the prior handoffs' §5 still applies (cp1252 both sides, dotfile evidence, `role_mail` `--body-file` + cd-to-main + verify-on-disk).

**The admitting gate stays open and the book is FLAT. Re-derive candidate, A+ and position counts before quoting them.**
