# Orchestrator handoff -- 2026-11-12 -- D101 and the Codex lane merged; SG at Reviewer A round 2

**Supersedes:** `orchestrator-handoff-2026-11-11-three-arcs-in-flight.md`.

**From:** session `7f461812` (Opus 5.5), online 2026-11-11 19:36Z. Rolls past 400K self-read on the first clean boundary after the SG round-2 cell returned and was QA'd. **Re-derive every fact below at HEAD and on disk before acting on it.**

## 1. STANDING GRANT (STATE, unchanged)

- **Operator, 2026-11-11, verbatim:** "Execute the work you have been authorized to perform by CHARC, including pushing, send CHARC your recommended items that do not yet have authorization." It covers dispatch, merge and push of the SG arc on CHARC's dispatches and gates. NOT operator config (harness section 2, `ba96747b`). NOT the live migration (his witnessed step).

**Authorities I granted by cell message (STATE):**
- Codex lane: a written round-4 authorization in its round ledger (spent; the arc merged).
- SG: round 2 dispatched with the rulings below; three counted rounds is the default -- **a FOURTH counted SG round needs the orchestrator's written authorization naming the task-bearing finding** (recipe section 3).

## 2. DONE THIS GENERATION

- **D101 MERGED** `dc982744` (`--no-ff` of `refs/heads/d101` @ `39dc0fcb`), merged-head 15857/13/0, pushed. CHARC's three conditions met (`7cef7480`, `1434c385`); my Reviewer B pass 1 major fixed (`39dc0fcb`), pass 2 major declined by read. **Operator witness PASSED** (run 211: 55 detections over a pool of 11; monitor == direct count). Branch `d101` kept; worktree removed. CHARC closes the D101 row (lag follow-on + capped-rerun sentence).
- **CODEX LANE MERGED** `83cdd7c6` (`--no-ff` of `codex-lane` @ `5fa893a6`), merged-head 15985/13/0, pushed. Reviewer A converged at round 4 (spend 649,228). CHARC's gate packet is block-quoted in the build ledger Group 9. Post-merge riders on CHARC's word: `e2582c0f` (codex-reviewer.md delta 11: `executed_ok`'s succeeded-in count is a declared limitation) and `88890eb9` (launcher `$SessionMarkers` gains `CLAUDE_CODE_SESSION_ATTENDED`, `AI_AGENT`, `TRACEPARENT`; the driver/launcher drift test is EQUALITY), suite 15985/13/0, pushed through `88890eb9`. Branch `codex-lane` kept; worktree removed.
- **CHARC RULED (harness form, binding now):** a Reviewer B pass with ZERO repo reads is diff-only and does not satisfy the B gate on an arc touching production code; the B prompt NAMES the files to open (callers, the schema/trigger written, consumers) and a pass counts only with at least one repo read in the transcript. It binds the SG arc's Reviewer B. Both of my fast B passes this generation read nothing and produced one false-premise major each.

## 3. IN FLIGHT

### 3a. Codex-lane OPERATOR WITNESS (brief section 5) -- step 1 not yet run
- Scratch worktree `.worktrees/codex-witness` (branch `codex-witness`, off main `88890eb9`). Staged prompt = the agent file + a toy brief (clamp + tests, test first): `~/swing-data/review-transcripts/codex-lane/witness/turn1-prompt.md` (the elevated account name is NOT in it -- checked).
- Step 1 (operator): `python scripts/codex_cell.py turn --worktree C:/Users/rwsmy/swing-trading/.worktrees/codex-witness --prompt C:/Users/rwsmy/swing-data/review-transcripts/codex-lane/witness/turn1-prompt.md --evidence C:/Users/rwsmy/swing-data/review-transcripts/codex-lane/witness --turn 1`. Read the JSON (model/effort pins, identity_ok, footer, FILES CHANGED naming the two files).
- Step 2: `python scripts/codex_cell.py commit --worktree <wt> --return-file <evidence>/return-1.md`, then `git -C <wt> log -1 --format=%(trailers)` shows the model footer.
- Step 3: `codex_cell.py review --worktree <wt> --base 88890eb9 --prompt <a short review prompt> --out <a folder OUTSIDE the worktree>` returns a JSON verdict.
- Step 4: `python scripts/usage_codex.py` and `python scripts/usage_claude.py` each print a reading (the allow rule for the latter is live since the merge).
- Item 4 of CHARC's gate: if the new stability test reds INSIDE the sandbox during the witness, it joins the agent file's residue list by name with the measured reason (a docs commit). Then remove the scratch worktree and branch.
- One step per message; never batch.

### 3b. SG label arc (D102+D103+D104, D86 riding) -- Reviewer A round 2
- Worktree `.worktrees/sg-label`, branch `sg-label`; executing-diff base `b120a6eb`. Ledger: `docs/superpowers/plans/2026-11-11-sg-label-correction.ledger.md` (every ruling block-quoted). Round ledger: the worktree's `.copowers-findings.md`, section "EXECUTING LOOP"; evidence `~/swing-data/review-transcripts/sg-label/exec/`.
- Executed through cells 2-6: T1 (migration 0042, `EXPECTED_SCHEMA_VERSION = 42`), T2, T3, T4.1-T4.3 (T4.3 in form C), the mirror closure by read.
- **Rulings, all landed and transcribed or being transcribed by the round-2 cell:** FX-1 = C (RD); FX-2 = Y, point 2 corrected (RD; the D47 companion banked and REGISTERED by CHARC at `b3a1abcc`); round-1 item A = B with RD's new entry-refusal rule, and CHARC's form ruling (one latch resolution; the night verdict moves into `record_entry` if the latch outcome is known only there); item B / R1-8 = keep as built (CHARC; docstring sentence + accepted limitation).
- **Round 1** counted (strong, `b120a6eb..7f53fb79`): 0/2/6, spend 349,358, cell depth 276,437 (filled).
- **Round 2 cell** (resumed cell 6): applies item A + RD's three test conditions + R1-3/R1-4/R1-6/R1-7 + the R1-8 docstring, the full suite (`exec-branch-suite-r2pre.txt`), then round 2, then yields. See section 5 for its return state.
- **After convergence:** Reviewer B (MINE; name the files to open -- `routes/trades.py` entry POST and `_rerender_entry_form_with_error`, `swing/trades/entry.py`, `cohort_provenance_correction.py`, migration 0042's triggers, the corrections repo, `hypothesis_prefill.py`, the CLI fire-candidate path; confirm >= 1 repo read before counting), then CHARC's merge gate (mirror closure by read, trigger bodies, candidate_id consumer table, live-shape fixture), then `--no-ff` merge + merged-head suite + push.
- **Merge-gate housekeeping owed (separate commits, never in a version-bump commit):** rename `test_a2_77` ("exactly_six", asserts seven) and the stale `v40` fixture name in `test_22f_d39_apply_migration.py`; correct plan section 0.3 / the review-form consumer row (cell 4 deviation 4: kind 2 does NOT move `_build_outcome_distribution`); the T5 runbook's dry-run step carries `--reason`.
- **Then the OPERATOR's witnessed live migration**, step by step: stop `swing web`; prove no holder by `BEGIN EXCLUSIVE; ROLLBACK` (plain sqlite3); backup; `swing db-migrate` to v42; T5 on trade 29 (`... 29 --cite-fire-candidate 15901 --reason "<text>" --dry-run`, then the real run); read-back `mode=ro`; RD's count (H2 4 -> 5). **A live pipeline run between the merge and the migration is UNRUNNABLE** (the version guard) -- time the merge to the operator's sitting, never just before a 17:30 nightly.

## 4. QUEUED (operator to commission, via CHARC at the SG close)
- The entry-form rider: the D47 companion (the early-400 re-render drops 15 typed values; RD ranks it above housekeeping) + D97 (unfloored sizing on the form) + D98 (stale sizing hint on a refused submit). swing/web only, no schema.
- `codex_cell.py`: count only a `succeeded in` line that closes an exec block (banked at the next touch).
- `research_health.py` YELLOW tail `more =(` spacing (CHARC's minor, next touch).

## 5. CELLS AT ROLL -- none in flight; the SG round-2 cell RETURNED and was QA'd

**SG at roll: Reviewer A CONVERGED at round 2.** `sg-label` @ `93f8bf26`, tree clean. Verified by me from the transcript: round 2 (strong, `b120a6eb..92dcb641`-era diff) gpt-6.1-sol / high, `^ERROR` 0, one `^tokens used` footer 305,630, exit 0, `NO_NEW_CRITICAL_MAJOR` x2 with the other 0, 0 line-initial prompt tokens, 21 exec blocks; findings 0/0/3. Depths filled: R1 276,437; R2 429,493 (the cell is PAST-CAP -- never resume it). Spend R1 349,358 + R2 305,630 = 654,988.
- Item A landed as RD ruled (`81b905c3`): the night verdict is enforced INSIDE `swing/trades/entry.py` (~`:2296`) after the single latch resolution (`:2148`); ordinary entries raise `DecisionNightRefusedError` (`:513`, not a ValueError) mapped to T2's 400 at `routes/trades.py:~2446`. RD's conditions 1-3 green (`tests/web/test_routes/test_entry_refusal_rule_decision_night.py`; condition 3's 400 reached via the "form was altered" branch, not a newer run displacing the night).
- **DEVIATION for CHARC's merge gate (must be read):** `list_decision_nights` is called once but in the ROUTE (`routes/trades.py:~1881`), NOT inside `record_entry`'s transaction as CHARC's form text said -- inside it the tier-2 replay returns UNVERIFIABLE (`frozen_value_evidence.py:1330-1331`) and git would run under the write lock (G-T7 Q1). The pairing window is closed instead by `_ORIGIN_NIGHT_BUCKET` refusing a night whose bucket disagrees with the service-derived origin; the cell-5 limitation was REPLACED by text saying so.
- Minors fixed: R1-3 (`c55bfa04` COMMITTED RED on the 22-A4 AST pin, fixed forward `c003379a`), R1-4 `04ef567b`, R1-6 `65fab509`, R1-7 `68c6588e` (manifest: one changed line), R1-8 docstring + derivation history `2026-11-12.1` (`3d9646e6`), R2-3 `92dcb641`. R1-5 service-prevented.
- **OWED, the successor's first SG acts:**
  1. R2-1 (duplicate key in a kind-2 envelope reads first-value in SQLite, last-value in Python; fix = a `json_each` count in the trigger + test + manifest) and R2-2 (a `\u0000` label: Python accepts, SQL `json_extract` raises). Both SERVICE-prevented (the sole writer serializes a dict; 0 kind-2 rows; 0 NUL labels live), both touch 0042. Post-convergence minors are fixed without a round -- but they change migration 0042's triggers, so ask CHARC whether to fix or bank BEFORE dispatching.
  2. The FINAL-HEAD gates were NOT run after `92dcb641`: full fast suite (exit status), `ruff check swing/`, migrate-twice, drift. Last green: `d432e5a0`, 16093/13/0 (`exec-branch-suite-r2pre.txt`).
  3. Then Reviewer B (mine; name the files; >= 1 repo read), CHARC's gate, merge, push, the operator's witnessed migration (section 3b).
- Caveat recorded by the cell: the round-2 diff included the committed ledger summarising round 1 (the plan-ledger relocation hazard).

**Codex-witness worktree** `.worktrees/codex-witness` exists, untouched; step 1 not run.

## 6. WATCHES
- The first real auto-filled entry on a flagged ticker (D84 live-emitter watch; exec ledger).
- The first live risk-flagged A+ (RD).
- RD's v2.6 boundary note on run 213 (the first stage-2 evaluation, the 11-12 nightly).
