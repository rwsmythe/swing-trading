# Orchestrator handoff -- 2026-11-11 -- three arcs in flight, every cell parked; re-dispatch from the ledgers

**Supersedes:** `orchestrator-handoff-2026-10-26-d94-closed.md` and the 10-26 set.

**From:** the generation that has run since 2026-10-26 (session `c53dc3dd`, Opus 5.5). It rolls at ~413K self-read, past the 400K floor, on a clean boundary: every cell it dispatched is PARKED at a yield and QA'd. A subagent dies with the session that spawned it, so **none of those cells can be resumed. Continue each arc with a FRESH cell from its ledger.**

**Re-derive every fact below at HEAD and on disk before acting on it.**

## 1. STANDING GRANT (STATE)

- **Operator, 2026-11-11, verbatim:** "Execute the work you have been authorized to perform by CHARC, including pushing, send CHARC your recommended items that do not yet have authorization."
  - It covers dispatch, merge and push of the three arcs below, on CHARC's dispatches and gates.
  - It does NOT cover operator config, which per harness §2 (`ba96747b`) needs a per-instance grant in his own words.
  - It does NOT cover the live migration, which is his witnessed step.
- **Operator, 2026-11-11, to CHARC directly:** "1. yes; 2. A". D86 rides the SG arc; stage 2 = A, already applied by RD.

## 2. ARCS (each branch is off main; worktrees under `.worktrees/`)

### 2a. Codex implementer lane (CHARC brief `e0d3ddd9`)
- **Branch and head:** `codex-lane` @ `c9a37ae1`, base `9e3d6cf3`. P0-P6 are built; round-1 fixes and CHARC rulings A1-amended and B1 are landed.
- **Resume record:** `.worktrees/codex-lane/.copowers-findings.md`, section "RESUME HERE -- round 2".
  - Round 2 is STAGED, not run: `~/swing-data/review-transcripts/codex-lane/review/{prompt-r2.md, codex-diff-r2.txt, run_r2.sh}`.
  - Regenerate the diff if the head moves.
- **Build ledger:** `~/swing-data/review-transcripts/codex-lane/build-ledger.md`. It quotes every CHARC ruling verbatim.
- **Evidence so far:**
  - The branch suite at `3687e871` was 15875/13/0. Targeted tests at `c9a37ae1`: 736 passed.
  - ruff shows 4 pre-existing findings only.
- **Next:**
  1. A fresh `implementer-opus-xhigh` cell runs round 2 (strong) onward to convergence; the round-5 check-in binds.
  2. Then the full suite at the final head.
  3. Then Reviewer B (yours) and CHARC's merge gate.
  4. Merge with **`--no-ff`, NEVER rebase**: the ledgers and mail cite branch SHAs. CHARC said "rebase" once; the recipe's MERGE FORM rule governs. Main's `f237d324` touched recipe 2A line 59, and the branch's P5 and N2 also edit the recipe, so resolve any overlap in the merge commit.
  5. Then the merged-head suite, the push, and the operator's step-by-step witness (brief §5: one Codex turn on a toy brief; `commit` showing the footer in `%(trailers)`; `review` returning a JSON verdict; both usage readouts).
- **Open for CHARC** (posted with this roll's announcement):
  - the ref comparison fails a review if `main` moves mid-review (narrow it to this branch's ref plus tags?);
  - confirm `PYTHONDONTWRITEBYTECODE=1` and `PYTEST_ADDOPTS=-p no:cacheprovider` in the review env;
  - `review --out` must point outside the worktree (dispatch note);
  - three older files outside the arc spell the elevated account name (fails safe, left).
- `.claude/settings.json` on the branch adds the exact rule `Bash(python scripts/usage_claude.py)` plus `permissions._comment_usage`. CHARC confirmed that placement (N1). It is not live until the merge.

### 2b. D101 per-run detection-count check (CHARC brief `3b64f9ec`)
- **Branch:** `refs/heads/d101` (the bare `d101` is ambiguous with a hex abbreviation). Base `f1eb4051`.
- **Head before option B:** `13a1b0b3`. Reviewer A (strong) CONVERGED at R1 there, and the branch suite was 15847/13/0.
- **CHARC's ruling** (`~/swing-data/review-transcripts/d101/charc-ruling-b.txt`, RD's note `rd-cc.txt`):
  - option B, rerun-aware: cover keyed on ticker + detection_date + pattern_class, with the covering runs named;
  - the one-night lag accepted and banked;
  - NULL eval reads yellow;
  - 4a (the scripts docstring) allowed.
- **Option B is DONE at `2ddc1fae`** (commits `439eea71`, `bd6d1ada`, `2ddc1fae`).
  - Reviewer A R2 (strong) on the changed diff: `NO_NEW_CRITICAL_MAJOR`, 0/0/4, minors fixed.
  - The final branch suite: 15853/13/0 (`~/swing-data/review-transcripts/d101/branch-suite-final-b.txt`).
  - A live-copy replay reads runs 103, 120, 121, 123 and 124 GREEN (naming their covering runs), 201 and 202 YELLOW, 203 and 211 GREEN.
  - The resume record is the state block at the top of `.worktrees/d101/.copowers-findings.md`.
- **Next:**
  1. Reviewer B over `f1eb4051..2ddc1fae`.
  2. CHARC's merge gate.
  3. The merge, `--no-ff` (the SHAs are cited).
  4. The merged-head suite, then the push.
- **One confirm owed by CHARC** (posted with this roll): the cell encoded "covered" as all 5 detector classes present for the ticker on that session under another run id. Live has exactly 5 rows per (run, ticker), 1754 of 1754. The class list is a stdlib copy of the runner's registry, with a drift test.
- **Banked out of the envelope:** if `detect_watch_pool_cap` is ever set again, a capped same-session rerun reads YELLOW for the dropped watch names. The trigger is whoever reintroduces the cap.
- **After the merge:** send RD the merge sha (it fixes watch-standard :164 docs-only). The operator witness is `python scripts/research_health.py` on the live DB, plus one `mode=ro` count of the latest complete run's detections.

### 2c. SG label correction arc (D102+D103+D104+D86; CHARC brief `3b64f9ec`)
- **Branch and head:** `sg-label` @ `b70ef5e0`.
- **The plan PASSED** CHARC's plan-stage read with RD's CC PASS (`~/swing-data/review-transcripts/sg-label/charc-plan-stage-pass.txt`, `rd-plan-pass.txt`). The amendment is folded at `e8a6ff1c`.
- **Executing so far** (worked in plan order T3, T4, T1, T2):
  - `063235a1` T3;
  - `7a2ed3ff` T4.1;
  - `8405528b` T4.2 (22 D86 tests pass).
  - The ledger section "Executing -- handoff 1" in `docs/superpowers/plans/2026-11-11-sg-label-correction.ledger.md` lists the remaining work: **T4.3, then T1 (3 commits, migration 0042, the amended step 7), then T2**, then the gates (full suite, ruff, migrate-twice, the drift test for both kinds, Reviewer A strong).
- **Next:**
  - A fresh `implementer-opus-high` cell from that ledger section, plus the plan and the brief's §2-4.
  - Then Reviewer B, then CHARC's merge gate: the mirror closure list by read, the trigger bodies, the candidate_id consumer table, the live-shape fixture.
  - Then the OPERATOR'S witnessed live migration:
    1. the lock probe (`BEGIN EXCLUSIVE; ROLLBACK`) after stopping `swing web`;
    2. the backup;
    3. `db-migrate` to v42;
    4. T5 on trade 29;
    5. the read-back `mode=ro`;
    6. RD's count (H2 4 -> 5).
  - A live run between the merge and the migration is unrunnable by the version guard.

## 3. MAIN

- Pushed through `dba134d5` this generation. Re-check `git status -sb`: directors commit to main continually.
- Schema v41. `detect_watch_pool_cap` unset (RD ruling, operator-agreed).
- Stage 2 of the Finviz widening was applied 2026-11-11 by RD on the operator's word. The 11-12 nightly is the first to evaluate it; RD writes the v2.6 note.

## 4. CELLS AT ROLL

All parked; none resumable by you:
- **codex-lane:** parked at `c9a37ae1`.
- **SG executing:** parked at `b70ef5e0`.
- **D101:** returned at `2ddc1fae`.

**The first acts, in order:**
1. Drain the inbox with `role_mail read`.
2. D101: Reviewer B, then the merge after CHARC's gate. It is the closest to done.
3. Dispatch the fresh Codex-lane round-2 cell and the fresh SG executing cell. They touch different files; run the census first.

## 5. WATCHES

- The first real auto-filled entry on a flagged ticker (D84 live-emitter watch; exec ledger).
- The first live risk-flagged A+ (RD).
