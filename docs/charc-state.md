# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** The one always-current state pointer for the CHARC (Tool Development Director) role. The dated §6 log in [`docs/tool-director-context.md`](tool-director-context.md) is APPEND-ONLY history; current state lives HERE. Bootstrap reads this FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-07-28 (compaction at the 21-A/21-D close — the per-turn layers were purged). **PHASE 21 ACTIVE: 21-A + 21-D MERGED and LIVE; 21-B is next.** Phase 20 closed 2026-07-15 (audit CLEAN). *(Note: a generational handoff was PREPARED 2026-07-15 but NOT taken — the operator resumed this same generation; the handoff artifacts remain valid for whenever a fresh gen launches.)*

---

## #1 — PHASE 21 (Latched-Entry Execution Surface & Comms Simplification). Scope: [`phase21-scope-charc.md`](phase21-scope-charc.md) — operator-approved 2026-07-27.

**Theme:** take memory and arithmetic out of the entry loop **without taking the human out of it**. Driver: the FTRE entry-window miss, RD-quantified at **+1.22R** shadow-vs-live, and the A+ LATCH posture the operator adopted 07-23.

| Arc | State |
|---|---|
| **21-A** latch panel + order awareness + view telemetry | **MERGED + LIVE 2026-07-28** (`1955aa59`; suite **9450/7/0** on merged main; **schema v31→v32**, the first migration in three phases; backup gate fired on the strict clause; live DB verified post-migration — 18 trades / 11725 candidates / all 11 A+ fires intact). **Production-verified on the live migrated DB: FTRE renders pivot 18.34 · invalidation 14.88 · cap 18.89 · horizon 2026-08-31.** |
| **21-D** comms singular inbox | **MERGED + LIVE 2026-07-27** (`57e4e797`; 67 files relocated sha256-matched, ZERO deleted; F5 + the explicit-sid discipline + the stray-spin-up class + the R3 tidy class all RETIRED; director traffic runs on it now) |
| **21-B** prepared-order form, LOG-ONLY | **DISPATCHED 2026-07-28** (brief `ba0746e3`, thread `phase21-arcs-b-g-parallel`; schema tripwire — CHARC pass embedded B1–B7; v32→v33). The form with DERIVATION visible + the three-state classification (pessimistic default BINDING) + the execution-parity ledger (both identities) + the telemetry surface column + RD's away-rate health gate. **NO Schwab write of any kind.** Acceptance test = FTRE classifies AWAY and its +1.22R lands in the away bucket. *(Was: NEXT.)* Scope is materially richer than when written — the three-state capture + away-rate consumption it always had, PLUS the two JOINT priorities (RD's stale-close asymmetry + the run-level-stamp provenance gap — scoped together because a fix for either alone leaves the false-all-clear reachable by the other route), PLUS the `data_asof_date` consumer SURVEY, PLUS the banked separated-claims construction + pending-vs-permanent wording, PLUS the telemetry surface column riding 21-B's own migration |
| **21-G** the two joint false-all-clear fixes + survey | **DISPATCHED 2026-07-28 IN PARALLEL with 21-B** (brief `d54c078b`; split out at commissioning). One rule resolves both routes (stale close AND run-level stamp): **mismatch alarm YES, match assertion NO.** Plus the `data_asof_date` consumer survey (reports; does not authorize fixing every hit) with a **hard STOP if the WRITE path must change** — that would be its own schema arc. **BINDING: 21-G MERGES BEFORE 21-B's ledger** (a stale regime writes a wrong order TYPE into the ledger → a framework defect masquerading as operator divergence). RD's rulings ARE the design; his gates are primary |
| **21-F** dashboard surfacing | PROPOSED (operator-originated at the 21-A witness). **CHARC: a broker call on the dashboard path is FORBIDDEN → the order-state cache is a PREREQUISITE, not a V2.** Sequenced WITH-or-AFTER 21-B (telemetry contract first) |
| **21-C** execution (preview→live) | DEFERRED behind stage-1 evidence + an **operator-signed L2 endpoint diff** (schwabdev has place/cancel/preview/replace; swing has ZERO write endpoints today) |
| **21-E** D5 runtime | **RETIRED** — the firing was CHARC's n=1 error, retracted on a four-sample measurement |

**The arc's thesis proved on itself:** the two figures that were WRONG when 21-A was commissioned — FTRE's invalidation (RD quoted the drifted **16.51**; fire-time is **14.88**, ~11% early) and the horizon (an untraced "~20 sessions" that became its own citation; the real bound is **30**, derived from `observe_max_pending_window_sessions`) — are now **correct on a surface the operator can open**, and both were corrected by TRACING rather than by argument.

**CHARC owns next:** the phase close ritual + close audit, sequenced whenever 21-B lands or the operator calls the phase. Nothing blocks either.

**Standing:** **Schema v32** (migration `0032_latch_view_telemetry`, live-migrated 2026-07-28 — ends two consecutive zero-migration phases). Suite **9450/7/0**. Streak intact (re-audited post-rebase across the largest arc of the phase). The weeknight task runs Mon–Fri 17:30 HST; **tonight is the first production exercise of the migrated schema**. Main is LOCAL-FIRST (operator pushes at his cadence). **Topology:** CHARC + RD + one orchestrator gen, all on the SINGULAR `--to orchestrator` inbox. coa-chess is its OWN repo — do NOT drive/contaminate.

## Register quick-state (full table: charter §4)

- **CLOSED in Phases 19–20:** D3 D6 D10 D13 D14 D18 D19 D20 D21 **D22 D23 D24 D25** + F1/F6.
- **OPEN/WATCH:** D1 (runner size) · **D5 (FIRED — runtime)** · D8 · D9 · D12 · D15 · D16 · D17 · D11 (orchestrator-context ~109K, re-WATCH).
- **Follow-ups:** F2 Accept-header parser · F3 WSL-Codex CWD · F4 hook-file-absence · ~~F5 `newest_live` staleness~~ **RETIRED by 21-D** (the singular inbox removes the resolution entirely) · the 0032 taxonomy type · the two V2 candidates.

## Behavioral load-bearing (full text charter §5; harness model [`harness-architecture.md`](harness-architecture.md))

- **§5.1 director = PEER — disagree plainly + UNPREFACED at a LOW threshold; never manufacture objections; a SCOPE/FRAMING correction does NOT lower the bar.** Call out the operator's errors and yours. The prior gen owned FIVE (two dismiss-recommendations on the $10.94; two wrong residual attributions; the A5 cite-without-verify) — all net-caught; own yours the same way.
- **THE HEADLINE LESSON (both directors' lists): a monitor that fires gets a DECOMPOSITION before it gets an explanation.** Size-of-residual ≠ nature-of-residual; prior-plausibility ("it's the deposit drift") is how both directors nearly dismissed real corruption the instrument caught in 24h.
- **Verify on disk before asserting — TRACE THE FULL BRANCH + THE NEIGHBORING SYSTEM + THE KEY STRUCTURE** (the C4, pruner, and #33-chain lessons: reading code ≠ walking it; a mechanism claim must trace what interacts with it; a chain-repair ruling must know what the chain is keyed on).
- **A citation is only as good as the verified DEF** — never cite a symbol's location off a comment reference (the A5 miss); the §5.7/§5.11 grep-the-negative + verify-pre-existence + content-currency disciplines all bind.
- **FYI ≠ act** — action needs EXPLICIT direction; else acknowledge + assess + await.
- **Comms:** operator pre-authorizes the ACTION; the director couriers dispatches to the **SINGULAR** `--to orchestrator` inbox (commit the brief FIRST). **Per-generation addressing is RETIRED (21-D, 2026-07-27): a `:<session_id>` suffix now FAILS LOUDLY with a non-zero exit — do NOT use it.** `decision_request` operator-only; **a message that REVERSES/SUPERSEDES an earlier position says so IN THE SUBJECT and names what it supersedes** (adopted 2026-07-28, `harness-architecture` §3 — the inbox LISTING is where a reader decides if they are current; **a stale POSITION decays far faster than a stale FACT**, so re-check second-hand claims about another role's decision at POST time, not read time); bodies BACKTICK-FREE (bash substitution mangles); `role_mail` from the MAIN repo dir; the mailbox is TRANSPORT not a tracker — must-persist content goes in a committed doc.
- **§2.7 directors do design dialogue + author/commit briefs + dispatch; NEVER run copowers cycles.**
- **§5.8 pathspec-commit `git commit -- <file>`** (+ `git add` first for NEW files) + `symbolic-ref==main` guard; final `-m` paragraph plain prose (trailer hazard); ZERO `Co-Authored-By` EVER (the ~3,983 streak).
- **QA on disk, never from the self-report; the operator live-witness is the binding net.** CHARC drives witnesses STEP-BY-STEP with recorded baselines + verified teardowns (the 19-B/19-C/20-A/20-BC pattern — witnesses found 3 runbook defects, discriminated a design ruling live, and validated every D25 gate).
- **The D21 sweep-safety discipline (BOTH charters): any moved-path OR tracked-config change gets a tests-grep BEFORE + a suite run AFTER; a close's green claim postdates the close's LAST commit; brief-coupled doc-assertions retire-at-close per the RD standard (retirement markers on new ones).**
- **The SCHEMA-STOP pattern works — keep using it:** name the schema temptation in the brief, forbid designing past it, route back on genuine need (it fired twice in Phase 20; both resolved no-schema).
- **Do NOT contaminate the generic scaffold with swing config**; coa-chess has its own directors.
- **Sub-agent 529 recovery:** inspect the worktree first; dispatch a NARROW recovery agent for only the missing gate.
