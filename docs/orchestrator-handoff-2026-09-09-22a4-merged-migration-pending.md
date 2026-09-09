# Orchestrator handoff — 2026-09-09 — 22-A4 **MERGED**; the witnessed 0038 migration is the next action

**Supersedes** `orchestrator-handoff-2026-09-08-22a4-b-ruled-fix-leg-briefed.md`.
**From:** the generation that dispatched and QA'd the Reviewer-B fix leg, re-ran Reviewer B, carried
four director rulings into git, and merged the arc.
**Precondition met: NO cell in flight.** Both cells returned and were QA'd; nothing is dispatched.
**Bootstrap:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.

**Every fact here was re-derived from disk at write time. Do the same, and do not carry my numbers
forward as your own measurement.**

---

## 1. YOUR FIRST ACTIONS — in this order, and the order is CHARC's ruling

**The arc is MERGED. The live database is UNTOUCHED at v37 and migration 0038 is UNAPPLIED.**

1. **THE OPERATOR'S `-n auto` SUITE RUN ON THE MERGE COMMIT `82d20042`** — CHARC's gate check (6),
   the last thing his clearance waits on, and **he reads the result line himself.** It is the
   OPERATOR's run in HIS shell; you do not run it and do not claim it. Unaffected by the schema
   state — every test builds its own `tmp_path` database.
   ```
   cd "C:/Users/rwsmy/swing-trading"
   git log --oneline -1          # expect 82d20042
   python -m pytest -m "not slow" -q -n auto
   ```
   Relay the line to CHARC. **Do NOT carry forward the two `-n 4` runs (12,310 passed / 13 skipped /
   0 failed, on `03e6ecc3` and on `989d734f`) as the merged-head result** — they are cell-seat
   evidence and both directors have explicitly declined to treat them as the gate.
2. **THE OPERATOR-WITNESSED 0038 MIGRATION** — step by step, ONE STEP PER OPERATOR RESULT, never a
   runbook handed over in a batch (memory `feedback_witness_step_by_step`). Immediately before it,
   re-read the live DB: expect `schema_version` 37 and `trades.attempt_id` ABSENT.
3. **A BLOCKING, OPERATOR-WITNESSED LIVE PIPELINE RUN** on the shipping code against the migrated DB,
   **in daylight, before 17:30 HST**. Its comparison is **run 171** (see §3). `export_status=failed`
   is EXPECTED (D42). Any failure NOT present in run 171 is the arc's or the migration's and BLOCKS.
   **D43's copy-run enumeration does NOT apply** — this is a live run, no copy.
4. The scheduled task then fires at 17:30 as the unattended second confirmation.

## 2. THE CLOCK — decide before 17:30 HST today

`SwingWeeknightPipeline` is **Ready**, runs `scripts/run-weeknight-pipeline.ps1` out of the merged
main repo, **next run 2026-09-09 17:30 HST**. If step 3 above cannot complete before ~16:30 HST,
**DISABLE THE TASK FOR TONIGHT** (CHARC's recommendation; the operator's call). **A guard-killed run
writes NO `pipeline_runs` row at all** — `connect` raises at `runner.py:768`, before the lease — so it
would be a SILENT miss read later as unexplained staleness. An explicit disable is a recorded
decision; a silent miss is a mystery for the next reader.

## 3. THE TRAP THIS GENERATION FELL INTO — read this before you plan anything involving the live DB

**The merge made the next step in the recited ladder UNRUNNABLE, and five seats had recited it.**
`swing/data/db.py::connect` raises `SchemaVersionMismatchError` whenever the live version differs from
`EXPECTED_SCHEMA_VERSION`; the merge moved that constant to **38** while the live DB is **37**; and
`swing/pipeline/runner.py:768` opens every run through exactly that `connect`. So *"S9 step 0, a
BLOCKING live pipeline run → then the witnessed migration"* cannot execute after the merge.

**CHARC's resolution required running nothing: the baseline already existed.** Pipeline **run 171**
(2026-09-08 17:30:04 → 17:48:42 HST, `state=complete`, `data_asof=2026-09-08`) was executed by the
real scheduled task on pre-merge code against the live v37 DB **about three hours before the merge** —
better provenance than any hand-run from a checkout. Its two blemishes are pre-existing and on the
register: `export_status=failed` is **D42** (every run since 160, 2026-08-21) and the warm-degraded
warning is the recurring shape (runs 168–171, fallback_count 6–8). **Neither may be read as a
migration effect afterwards — that is what a baseline is for.**

**THE RULE, now in `docs/phase22-arc-a-executing-resume.md` by replacement:** *a step that OPENS THE
LIVE DB is unrunnable between a schema-bumping merge and its migration — so the baseline is the last
PRE-MERGE run and the live verification is POST-migration by construction.*

**How I missed it:** I ran the merge's composition read on FILE SETS, found them disjoint, and called
the composition clean. Disjointness was necessary and I treated it as sufficient; the defect was in
the RUNTIME composition of code with the live schema. CHARC recorded this as **the rung's gap, not
the seat's** — the merge-time composition read did not have that question on its list and now does.
Do not repeat the flattering version of this story: the check I ran was correct and bounded, and I
reported its bound; what I got wrong was calling a bounded result a whole answer, which is the same
shape as the other three instances on this arc.

## 4. STATE, re-derived at write time

- **`main` @ `e50c8ec1`**, tree clean except ONE foreign untracked file (below). **34 commits ahead
  of origin, UNPUSHED.**
- **Merge commit `82d20042`**, parents `0af3cf07` (main) + `3b7140a7` (branch), **trailers `[]`**,
  made with `git merge --no-ff` per CHARC's ruling — **never rebase, never squash this arc.**
- **Branch `22-a4-exec` @ `3b7140a7`** and worktree `.worktrees/22-a4-exec` — **PRESERVED, do not
  tear down** until the migration is witnessed and the live run passes.
- `.worktrees/22-a4-plan` @ `f5e03921` still on disk, unused for four generations.
- **LIVE DB: `schema_version` 37, `trades.attempt_id` ABSENT, 0038 UNAPPLIED** — measured read-only by
  me, and independently by both directors within the hour. **Re-verify anyway before the migration.**
- **Untracked and NOT MINE:** `docs/cli-autoupdate-run-poisoning-finding-coa.md` appeared in the main
  worktree during the merge window; the tree was clean immediately before. RD says it is not his.
  Ask CHARC or the operator before touching it — I did not add, move or remove it.

## 5. BOTH DIRECTOR GATES ARE IN

- **CHARC: 8 of 9 PASS**, each on his own measurement. Check **(6)** — the merged-head `-n auto` run —
  is the only one outstanding, and he reads the result line himself.
- **RD: 7 of 7 PASS**, plus a post-merge re-verification he re-ran himself at `82d20042` (46 branch
  blobs + 20 main blobs, zero differing; Lock A re-measured at the merge; live DB v37). **His
  clearance now attaches to the MERGE COMMIT by measurement, not by tree hash** — a naive
  "tree must equal `fd69bc22f661`" check would false-alarm, because the ledger commits legitimately
  moved the tree hash while the code/test delta stayed empty.

**Reviewer B re-ran on the post-fix head and found NO NEW INTRODUCED MAJOR.** Its verdict token reads
`NEW_CRITICAL_MAJOR_FOUND` because the prompt mandates that token for ANY major including a banked
one. **Both halves are the result** — and `B-2` (single-field corrections silently discard every
payload key after the first) is a real pre-existing MAJOR standing unfixed at merge, by ruling, on
CHARC's register.

## 6. AUTHORITIES I GRANTED — the record, because a cell message is not one

**Two dispatches, both to `implementer-sonnet-high`, both QA'd against disk. NO envelope widening, NO
scope grant, NO mid-round fix authorization, and NO round authorization — none was needed, because
B's re-run surfaced no new in-envelope introduced major. NO FIFTH COUNTED A ROUND IS AUTHORIZED BY
ANYONE**; if one ever becomes necessary it needs a fresh written authorization naming the finding.

**One correction I made and had to withdraw.** I told CHARC the cell's Lock-A hash claim "did not
survive checking." **It did.** My measuring script used `subprocess.run(..., text=True)` with no
`encoding=`, so it decoded the blob as **cp1252**; `record_entry` carries 7 non-ASCII characters that
become 17 mojibake ones. The withdrawal is in the ledger beneath its own quote, the cell was told
directly, and the gotcha is banked (`ae87d2e3`). **RD independently re-derived the same error before
CHARC's ruling landed.**

## 7. WHAT I LANDED THAT OUTLIVES THE ARC

- **`ae87d2e3`** — CLAUDE.md's cp1252 gotcha gains its DECODE side: *the encode side crashes, the
  decode side lies*, and it agrees with a correct measurement on pure-ASCII input, which is how it
  passes its own sanity check. Forensic in the archive. **The merged bullet is 1,253 chars against a
  ~700 per-gotcha soft cap** — two gotchas in one bullet by design, flagged in its own commit message.
- **`0af3cf07`** — the recipe §1 and orchestrator-context both gain: **a history rewrite is a TIP-ONLY
  operation.** Rebase + `--ff-only` only while nothing cites the branch's SHAs; once a ledger, brief
  or block-quoted ruling cites them, `--no-ff`, never rebased, never squashed.
- **`e50c8ec1`** — the resume doc's falsified sequence corrected by replacement (§3).
- Four director rulings transcribed into the arc ledger as **literal block quotes built mechanically
  from the message files and verified by containment**, each with the ruling seat named as author and
  this seat as courier only.

## 8. WHAT WILL BITE YOU

- **`role_mail.py` caps the subject at 80 chars** and refuses the post outright — nothing written. It
  bit me once. `--body-file` always; `cd` to the MAIN repo in the SAME invocation; **verify delivery
  on disk** — the `posted ->` line reads identical on a misdelivery. Both directors' sessions are live
  and drain within seconds, so an empty `inbox/` usually means delivered-and-read: check `read/`.
- **The Bash tool's PATH lacks `/usr/bin`** — `export PATH="/usr/bin:/bin:$PATH"` first, every time.
- **MSYS rewrites a `/mnt/c/...` argument** into `C:/Program Files/Git/mnt/c/...` — confirmed live
  this generation. Invoke WSL through **PowerShell**, not the Bash tool. Codex answers
  `codex-cli 0.152.1` to the `--version` liveness probe.
- **`git merge -F -` does NOT read stdin** (unlike `git commit -F -`) — write the message to a file.
- **A bash heredoc containing certain prose fails to parse**; when a `<<'PY'` block misbehaves, write
  the script with the Write tool instead of debugging the quoting.
- **`-n auto` is memory-killed in this seat** — use `-n 4`; the binding `-n auto` run is the
  OPERATOR'S.
- **ANCHOR EVERY GREP over a Codex transcript.** An unanchored `tokens used` search matched CLAUDE.md's
  own text quoted inside a 1.6 MB transcript and cost me several thousand tokens. `^ERROR` vs `ERROR`
  on this arc's own assertions is 0 vs 37 — the same lesson, already paid for once.
- **All Codex artifacts are DOTFILES** — `ls -a` under `~/swing-data/review-transcripts/22-a4-exec/`
  or you will conclude they are missing. A r1–r4, B pass 1, B pass 2, both runners, both prompts.

## 9. QUEUE BEHIND 22-A4

`B-2` (CHARC's register) · the version-mirror rename rider, **trigger: AFTER the merge — that trigger
has now FIRED** · `ReservedJournalFieldError`'s bare-`Exception` base, which **Reviewer B rediscovered
independently** (D34's third instance) · D42's export failure, now visible on every run since 160 ·
D32 (arc-mirror backups in the `swing-data/` root — the 0038 migration writes another ~1.4 GB
pre-image there; move-then-retain, never delete; 77 GB free) · then D46, D45, D44/D47, the D39 sweep.

**The admitting gate stays open: 131 post-barrier candidates, zero A+. Open trades: 23 CADL
(partial_exited), 24 RHI, 25 OII, 26 NRIX, 28 PBF. Real money, and the migration ahead of you touches
the database that holds it.**
