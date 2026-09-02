# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** The one always-current state pointer for the CHARC (Tool Development Director) role. The dated §6 log in [`docs/tool-director-context.md`](tool-director-context.md) is APPEND-ONLY history; the §4 register holds debt; [`harness-architecture.md`](harness-architecture.md) holds the cross-role rules. Current state lives HERE. Bootstrap reads this FIRST. Convention: [`harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-09-02 — 22-A MERGED, S9 step 0 PASSED, live DB still v36; #1 rewritten, register D40–D43 added.

---

## #1 — WHERE THINGS STAND

**PHASE 22 ACTIVE. 22-A IS MERGED TO `main` @ `9e4a8618`** (161 arc commits, ZERO trailers across `a18a3771..HEAD`; **merged-head suite 12,077 / 13 skipped / 0 failed**, run by the orchestrator ON THE MERGED HEAD; ruff clean). **S9 STEP 0 PASSES: `swing pipeline run` against a v37-migrated COPY — ZERO barrier aborts; `_step_evaluate` APPENDED 55 candidate rows through the barrier** (the one thing 26 Codex rounds + 2 B passes were structurally blind to). Migration on the copy v36→v37, six triggers, backfill exactly one link row (OII, 12284, `pre_barrier_reconstructed`), epoch boundary 13591. **Step 0 is a FLOOR, not a proof of absence** (no UPDATE/DELETE occurred on `candidates`, so rarer paths are unproven — the orchestrator said so rather than overclaiming). **LIVE DB STILL v36, `0037` UNAPPLIED. `main` UNPUSHED (~75+).**

**NEXT: S9 steps 1–6, operator-witnessed, one at a time** (the live v36→v37 migration, then the witnessed application). **BINDING (D43): the retained v37 copy wrote into the LIVE artifact tree on step 0 — any further execution against it enumerates and redirects its write surfaces FIRST.** The arc corrects NEITHER trade 24 NOR 25; both carry as named pending rows into the September read. **PBF (entered 09-01) is a NAMED PENDING member of H2's reads** (D41).

**Recorded against the gate, by the orchestrator against itself: a Condition-1 ORDERING BREACH** — step 0 was sequenced AFTER the merge in its own package §7 and executed in that order; the operator authorized against the mis-ordered package and then ruled proceed-immediately over reset-then-re-merge. **What it cost: the ordering guarantee, not the protection** — main unpushed, DB untouched, step 0 against a copy, STOP semantics fully available. My read: the ruling stands; the lesson is that a gate's ORDER in a package is part of the gate and the §7 sequence must be checked against the conditions it implements.

**The B gate worked on its second pass:** B ran on the tree being merged, all five assertions, `NEW_CRITICAL_MAJOR_FOUND` with every finding dispositioned — R11-02 found that `post_commit_warnings` has ZERO readers (clause 1 stops at the service boundary; `trades.py:1490` discards `record_entry`'s result) → **caller-half-first is the ruled follow-on ordering** (orchestrator-proposed, RD-agreed, CHARC-concurred 2026-09-02): the caller half is live-reachable and cheap; the attempt-identity primitive is schema work serving a correctly-reverted clause. **Six consecutive rounds carried the cascade signature (R7–R11 each residual of the preceding fix)** — the operator's stop was right and the arc shipped with declared residuals rather than a seventh.

## #2 — MY RULINGS THIS ARC (a cold resumer inherits these as DECISIONS, never re-derives them)

- **One-migration-one-task binds at the APPLICATION boundary.** Before any persistent DB applies the version, the migration file is part of the arc's single atomic deliverable and may be amended in place; after ANY persistent application, additions go in a new version, no exceptions.
- **The barrier's four conditions** (blocking live pipeline run as S9 step 0 — a trigger abort returns to CHARC, the trigger is never relaxed · legible named refusals asserted as CONTENT · reversibility in the migration header · additive) and **both Condition-4 exceptions** (the third epoch trigger, repurposed to close the `INSERT OR REPLACE` fail-open; the transactional trigger replacement — a DROP+CREATE replacing a guard with an equal-or-stronger guard is not a drop, but it is ALWAYS DECLARED).
- **The barrier-integrity check compares the trigger BODY, never the NAME** (T1b pattern, in the READER not a test), pinning all **six** triggers; the three-trigger `candidates` DDL pin ratified.
- **PERSIST-CANONICAL:** SQL verifies a FACT; it must never re-derive a JUDGMENT across an engine boundary — the twin mirrors the authority by CONSUMING ITS OUTPUT. (Three engine-semantic divergences in three rounds — NaN-JSON, whitespace-strip, type affinity — closed the class structurally. R5-02's epoch-boundary comparison SURVIVES: it is a fact comparison, both operands in SQL's domain.)
- **The `-1` PK sentinel idiom** — `(NEW.pk != -1 AND pk = NEW.pk)`; NEW tables carry `CHECK (pk > 0)`; existing tables verify-and-declare; **every site ships the three-direction set** (ordinary append SUCCEEDS · conflicting REPLACE ABORTS · explicit conflicting id ABORTS).
- **Fourth EXT-1 param REFUSED** — detect-and-refuse ratified, limitation declared with the asymmetry as its reason. **AL-3's scope RESTORED** (a limitation's scope moves by ruling; the reviewer's widening banked to 22-A2 with a trigger). **The envelope is EXT-1/2/3 and nothing more; EXT-4 struck.**

## #3 — OPEN ELSEWHERE (owner named)

| item | owner | state |
|---|---|---|
| **`main` UNPUSHED, 42 ahead** | operator | Verified this session |
| **Trades 24 + 25** | RD | Both carry as NAMED pending rows through the September read — 25 NULL-pending, 24 MISFILED-pending with H5's live reads EXCLUDING it and the reason stated. **October horizon: 22-A2 lands before that read if either has closed.** |
| **September monthly read #3** | RD | First trading week of September. Carries the clock-domain caution (D37) and the **shadow-A+ stop-geometry caveat** — 4 of 5 closed shadow rows died at the shadow's entry-bar-low stop while live counterparts survived; the arm's mean measures the SHADOW's stop placement, not live doctrine. |
| **VSTS deadlock** | ratified (c)+(d) | Expires 2026-09-08 untouched; abandonment intent → 22-C |
| **Unexplained FTRE cessation** · **Disc 86** | RD · — | Banked; the only open ledger discrepancy is 86 (immaterial) |
| **Trail contradiction** | RD doctrine / 22-D surface | Interim ruling stands: the eligibility gate governs; "Trail stop up to" is the defect speaking |
| **Import-time-binding flake** (`recommendations.py:39`) | banked | Pre-existing by byte-identity, outside the envelope; fix shape recorded |

## #4 — PHASE-22 QUEUE (after 22-A merges)

**22-A2** (proof machinery: continuity interval · tier-2 conjunction with the single-rounding-authority amendment · attestation/replay · eras + the era triggers + `gap_era_reconstructed` · **trade 25's correction**) — deferred rulings travel AS RULED · **22-B** Demand A `unintended_execution` (57-column `trades` REBUILD; §VII.F text ratification is a distinct gate) · **22-C** abandonment intent · **22-D** trail-surface one-voice · **22-E** Demand B · **22-F** handler-escape sweep · **22-G** unactionable-surface sweep · **22-H** D37+D38 timestamp sweep · **22-I** REPLACE-exposure sweep (five confirmed instances; the TRIPLE convention with both priced costs — the `ON CONFLICT` writer cost and the `-1` idiom) · wave leftovers D32 + D9 · the #11-SQL-twin gotcha amendment. Full text: [`phase22-scope-charc.md`](phase22-scope-charc.md).

## #5 — STANDING FACTS THAT ARE MISREAD IF ABBREVIATED

- **SIX open positions as of 2026-08-27, predicate `current_size > 0`, read this session:** ORKA (22, 1 sh, `by_design`) · CADL (23, 9 sh, `partial_exited`, keys CORRECTED) · **RHI (24, 3 sh — operator-confirmed MANDATE FILL, misfiled in H5)** · **OII (25, 2 sh — labels FROM THE FIRE per RD, keys deliberately EMPTY)** · NRIX (26, 6 sh, `by_design`) · TVTX (27, 2 sh). 27 trades total. **The prior pointer said TWO, from an 08-13 as-of — state a position set WITH its as-of and predicate, and re-derive before relying.**
- **Trade 20 (AMN): closed ≈ −0.996R, `entry_intent` NULL DELIBERATELY** pending 22-B. An entry NOBODY DECIDED TO MAKE (its own row's words); `trade_origin` alone misleads.
- **The doctrine bound, final form (RD):** a latch does not survive its own invalidation — the first COMPLETED session whose close (strict below, `_PRICE_DP`) breaches the frozen value, that close belonging to its `data_asof` session, NEVER `action_session_date` — and a fill on any LATER session does not label from the fire. **Fill-wins uniformly at every rung**, on the measurement ground: refusing same-session collapses censors H1's left tail.
- **H1 is 2/20 with 1 in flight.** The 20 is a static registry column; `current_sample` counts CLOSED trades.
- **An arc's PLAN must be on `main` before its branch is deletable** — and this arc extends it: the LEDGER and transcripts are gitignored and die with the worktree unless copied out.

## #6 — GOTCHAS LANDED THIS ARC (all in CLAUDE.md)

REPLACE fail-open to DELETE-trigger barriers (+ the `ON CONFLICT` indistinguishability facet) · #11's single-member facet (a value-set sweep misses a hard-coded member) · Python-vs-SQLite half-rounding · **NULL-`WHEN` triggers fail open silently** (COALESCE idiom; one missed nullable clause disarms the whole trigger). **The family they belong to: a guard that looks present and is structurally unreachable** — antidote is the **satisfiability proof** (a refusal-only test set cannot establish that a guard can EVER accept). Recipe additions: the transport cap pointing at §3's fallback · MSYS path-mangling · the CRLF runner hazard (exit-0 mechanisms three, four, five) · a transcript is not stable while its process lives.

## #7 — BEHAVIORAL (full text: charter §5; cross-role model: `harness-architecture.md`)

- **Director = PEER; disagree plainly, unprefaced, at a LOW threshold; own errors in the artifact.**
- **Premise-sourcing: five owners · a ruling is not a source · the TEMPORAL clause** (a quiet instrument only evidences the fix if it ran against the fixed code) · **independent verification means an independent DERIVATION PATH, not a second run of the same one.**
- **Report every count/absence WITH THE METHOD.** A token grep bounds from below; only a READ establishes a manifest; a column-name grep cannot see a dynamic-SQL writer (D36).
- **A COMMIT MESSAGE IS A CLAIM, AND STAGING A FILE IS NOT CHANGING IT** (2026-08-27, mine): a multi-edit script that aborts midway leaves earlier claims standing over absent text, and `git add` of an unchanged file raises nothing. **Read the DIFF of the commit you just made, not the exit code of the script that made it.**
- **An operator-concurred item is OWED, not queued.** A rule that changes what counts as DONE waits for the window; a rule that only makes someone STOP AND ASK lands immediately.
- **Comms:** subjects ≤80 chars (enforced in code) · `--body-file` same-step, backtick/dollar-free · post PER RECIPIENT and verify the `posted ->` lines (a repeated `--to` delivers only to the last) · `role_mail` from the MAIN repo dir · never truncate your own drain.
- **§2.7 directors never run copowers cycles. §5.8 pathspec commits; ZERO `Co-Authored-By` EVER.**
- **QA on disk, never from the self-report; the operator live-witness is the binding net; verify a gate is REACHABLE before spending the operator on it.**
