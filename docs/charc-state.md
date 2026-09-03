# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** The one always-current state pointer for the CHARC (Tool Development Director) role. The dated §6 log in [`docs/tool-director-context.md`](tool-director-context.md) is APPEND-ONLY history; the §4 register holds debt; [`harness-architecture.md`](harness-architecture.md) holds the cross-role rules. Current state lives HERE. Bootstrap reads this FIRST. Convention: [`harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-09-02 (late) — S9 COMPLETE, live DB v37, 22-A fully landed; the admitting-entry witness recorded as OPEN; D43 amended, D41 evidenced.

---

## #1 — WHERE THINGS STAND

**PHASE 22 ACTIVE. 22-A IS FULLY LANDED: merged to `main` @ `9e4a8618`, LIVE DB AT v37 (integrity ok; v36 backup `swing-20260902T000318.db` verified RESTORABLE, re-verified after cleanup), S9 COMPLETE — steps 0–4 and 6 executed, step 5 under my amended mechanism.** Suite 12,077/13/0 on the merged head; 161 arc commits, zero trailers. **`main` PUSHED 2026-09-02 (193 commits, `a44b8669..c977097e`, pre-push trailer audit ZERO on the KEY filter — the streak is now on the remote, which is the state that protects it); 5 CHARC docs commits since, verified `rev-list` this session.** Repo `git status` CLEAN — the strays are gone.

**S9 final record:** **0** full live pipeline on a v37 copy — PASS, zero barrier aborts, 55 candidates APPENDED through `_step_evaluate` · **1** live migration — PASS, one OII link row at `pre_barrier_reconstructed`, epoch 13591 · **2** refuse-by-default on trade 25 — PASS, `pre_barrier_unproven` + the citation-shopping refusal · **3** barrier-existence — PASS, one trigger dropped on a copy and the reason MOVED to `barrier_not_installed` (the cleanest discriminator of the arc; R9-01 demonstrated on live-shaped data) · **4** post-barrier admission — ADMITTED at `live_at_acceptance` with six counterfactuals, built through PRODUCTION writers · **5** unlatched path — **PASS ON ITS PROPERTY, carried by the no-accepted-link assertion, NOT by the byte-diff** (which fired at a shallower argument guard because D41 makes the intended guard unreachable for PBF — reported as a half-witness labelled, not a full one implied) · **6** browser gate — **PASS on render and write path** (HTMX form posted with `HX-Request` intact, screen and ledger agree to the second: intent 9), **PARTIAL on the admitting entry.**

**OPEN FROM S9, recorded not implied: a SUCCESSFUL entry submit through EXT-2 was NOT witnessed.** Four guards each refused correctly (IMNM's link consumed by step 4's own trade; RHI open against `ux_trades_one_open_per_ticker`; the copy at 7 positions against the hard cap of 6; the panel refusing a second prepared order on a latch with a place cycle). **The admitting entry stays unwitnessed until a latch opens post-barrier — the first live post-barrier fire is the gate, and it is a NAMED pending witness, not a done item.**

**Two things caught at S9 by the discipline, both recorded in the register:** the migration is itself a WRITE SURFACE (D43 amended — the 0037 arc mirror landed in the live `swing-data` root when the copy was migrated; benign by ordering only, and the near-miss is the lesson) · D41 biting live (no recommendations row exists for a watch/hyp-rec entry, so its aplus check is unreachable). Plus the `swing web` server that had held the DB since 08-28, caught by a pre-flight write-lock probe before the migration.

**Trades 24 and 25 remain named pending rows; PBF (28) is a named pending member of H2's reads.** 22-A corrected none of them by design — that is 22-A2's. **22-A3 EXECUTING — STOPPED AT THE OPERATOR-WITNESSED BROWSER GATE (S6, 2026-09-03): nine tasks shipped, envelope exact (7 declared production files), 9 commits zero trailers, suite 12,122/1 with the one red the known xdist flake (now a CLAUDE.md gotcha; the handoff's "fails on main" retired). Plan on `main` (`1a343f1c`+`0c261cfa`); round 6 ran NOT converged and was STATED as such (7-of-9 instrument findings; executing surfaces that class by running tests). Q1/Q2/sixth-site rulings verified in the plan; the degraded-success shape is browser-only, so S6 is BINDING and the operator's.** After S6: Task 11's suite + A-loop, Task 12, B at the orchestrator's gate, both director gates. **22-A4 dispatches AFTER 22-A3 merges.** **D45 measured** (the cancelled order's link IS a live competitor — pre-fix evidence for same-mandate collapse). **The admission gate stays DORMANT: run 168 put 55 candidates above the epoch, ZERO `aplus`; IMNM returned as `watch` (13627), not a re-fire — the first live post-barrier A+ is still the open named witness.** (brief committed first: [`phase22-arc-a3-a4-commissioning-brief.md`](phase22-arc-a3-a4-commissioning-brief.md)). The Phase-22 queue (#4) stands behind them.

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
