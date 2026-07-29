# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** The one always-current state pointer for the CHARC (Tool Development Director) role. The dated §6 log in [`docs/tool-director-context.md`](tool-director-context.md) is APPEND-ONLY history; current state lives HERE. Bootstrap reads this FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-07-29 — **THE GENERATIONAL-HANDOFF OVERWRITE. You are the fresh CHARC; the prior generation (bootstrapped 2026-07-02, ran Phases 19 + 20 and half of 21) hands off HERE, mid-phase and mid-flight.** Read this, then [`phase21-scope-charc.md`](phase21-scope-charc.md), then the two open briefs. Charter §6 carries the tenure record; **do not re-derive history.**

---

## #1 — PHASE 21 IS LIVE AND MID-FLIGHT. Two arcs merged, two in flight, one proposed.

**Theme:** take memory and arithmetic out of the entry loop **without taking the human out of it.** Driver: the FTRE entry-window miss (**+1.22R** shadow-vs-live, RD-quantified) and the A+ LATCH posture the operator adopted 07-23.

| Arc | State |
|---|---|
| **21-A** latch panel + order awareness + telemetry | **MERGED + LIVE** `1955aa59` · **schema v31→v32** (live-migrated; backup `swing-20260728T111453.db`) · production-verified: FTRE renders **18.34 / 14.88 / 18.89 / 2026-08-31** |
| **21-D** comms singular inbox | **MERGED + LIVE** `57e4e797` · 67 files relocated, ZERO deleted · retired F5, the explicit-sid discipline, the stray-spin-up + registry-tidy classes |
| **21-G** the two joint false-all-clear fixes + survey | **EXECUTING** (brief `d54c078b`, plan `acc762f7`; RD's 4 rulings folded). One rule: *from a stale close AS FROM a run-level stamp you may raise a MISMATCH ALARM but may NOT assert a MATCH.* **⚠ BINDING: 21-G MERGES BEFORE 21-B's LEDGER** — a stale regime writes a WRONG order TYPE into the ledger, making a framework defect look like operator divergence |
| **21-B** prepared-order form (LOG-ONLY) + ledger | **WRITING-PLANS** (brief `ba0746e3`, corrected `1a9ab926`); **returned NOT CONVERGED at 18 rounds and was SENT BACK** to run review-strong until it actually converges — it reported its own non-convergence rather than padding a verdict, and its two strong rounds each produced a CRITICAL invalidating the arc's own worked example, a class 16 fast rounds never touched. **Also self-reported a verification gap now fixed structurally: three multi-edit scripts aborted mid-batch so fixes silently never landed WHILE THE TRANSCRIPT RECORDED THEM AS DONE** — per-round grep-verification is now the guard (a false-record class worth remembering). Three-state classification, execution-parity ledger, **NO Schwab write of any kind** |
| **21-F** dashboard surfacing | PROPOSED. **A broker call on the dashboard path is FORBIDDEN → the order cache is a PREREQUISITE.** With-or-after 21-B |
| **21-C** execution (preview→live) | DEFERRED behind stage-1 evidence + an **operator-signed L2 endpoint diff** |
| **21-E** D5 runtime | **RETIRED** — the firing was CHARC's n=1 error |

**Open on YOU when the arcs return:** QA the returns on disk (never from the self-report) · the §3 pass on anything reaching `swing/evaluation/` write paths · the **21-F order-cache prerequisite** · the phase close ritual + close audit when 21-B/21-G land or the operator calls it.

**Standing:** schema **v32** (next is 0033, 21-B's) · suite **9450/7/0** · streak intact · the weeknight task runs Mon–Fri 17:30 HST and **the first v32 production run (142) was clean and faster than its predecessors** · main is LOCAL-FIRST (operator pushes at his cadence; verify trailers + fast-forward before any push) · **topology:** CHARC + RD + one orchestrator, all on the **singular** `--to orchestrator` inbox · coa-chess is its OWN repo — do NOT drive/contaminate.

## Register quick-state (full table: charter §4)

- **OPENED this tenure:** **D26** unguarded health-VM banner (rider) · **D27** `data_asof_date` names TWO quantities across tables — bar-derived vs clock-derived, agreeing only by healthy-nightly coincidence, diverging exactly when degraded (**keep OUT of 21-G**; phase-close or Phase 22) · **D28** the comms/shell body hazard survives knowing about it (mechanical-guard rider).
- **WATCH:** D1 · D5 (firing RETRACTED — variance dominates; do NOT scope a paydown off one sample) · D8 · **D9 (upgraded + reframed: *a test asserting against ambient state the repo does not control*; highest-risk-subset sweep proposed for a phase boundary)** · D11 · D12 · D15 · D16 · D17.
- **Riders banked:** the deferred taxonomy `discrepancy_type` (**no longer "0032"**) · the 2 residual brief-named docs · F2/F3/F4 · the gotcha-#30 pointer rider (orchestrator authors at 21-G merge) · 21-A's V2s (per-order reporting; no-order-fetch cache).
- **RD's, not ours to schedule:** the 3 research-side survey hits inside his own chain (deadline: his August monthly read) · the floor-ratio band · the shadow-twin divergence.

## Behavioral load-bearing (full text charter §5; harness model [`harness-architecture.md`](harness-architecture.md))

- **§5.1 director = PEER — disagree plainly and UNPREFACED at a LOW threshold; never manufacture objections.** Call out the operator's errors and your own. The prior gen owned SEVEN; every one was net-caught and none reached a witnessed merge. Own yours the same way — plainly, in the artifact, not just in chat.
- **SOURCE EVERY PREMISE FROM THE ROLE OR ARTIFACT THAT OWNS IT** (harness-arch §2, four owners): a **fact** → the CODE, not a doc · a **position** → the role that holds it, re-checked at POST time · **dispatch state** → the ORCHESTRATOR only · **gate state** → the gate-holder. **A stale POSITION decays far faster than a stale FACT.**
- **Verify on disk before asserting — trace the FULL branch, the NEIGHBOURING system, and the KEY STRUCTURE.** A citation is only as good as the verified `def`. **And check the DATA can support a test before making it binding** (the vacuous-FTRE lesson).
- **A probe-class threshold is never declared crossed on n=1** (the D5 retraction).
- **Comms:** operator pre-authorizes the ACTION; the director couriers to the **singular** `--to orchestrator` inbox (commit the brief FIRST); `decision_request` operator-only; **a message that REVERSES an earlier position says so IN THE SUBJECT**; bodies **BACKTICK-FREE and DOLLAR-FREE** (the shell executes them — D28); `role_mail` from the MAIN repo dir; the mailbox is TRANSPORT, not a tracker.
- **§2.7 directors do design dialogue + author/commit briefs + dispatch; NEVER run copowers cycles.**
- **§5.8 pathspec-commit `git commit -- <file>`** (+ `git add` first for NEW files); final `-m` paragraph plain prose; **ZERO `Co-Authored-By` EVER.**
- **QA on disk, never from the self-report; the operator live-witness is the binding net** — drive witnesses step-by-step with recorded baselines and verified teardowns.
- **The D21 sweep-safety discipline:** any moved-path OR tracked-config change gets a tests-grep BEFORE and a suite run AFTER; a close's green claim postdates the close's LAST commit.
- **The SCHEMA-STOP pattern works** — name the schema temptation in the brief, forbid designing past it, route back on genuine need.
- **The late-reopen test:** a COUNT PLUS A STRING over an existing rendering path may ship late; a MODEL change may not.
- **`codex-auto-review` is STANDING/REQUIRED on production arcs (§2.9)** — and **verify its invocation at dispatch; never assume the last one still works** (three distinct breakages; the argv form let repo source reach the shell).
- **Do NOT contaminate the generic scaffold with swing config**; coa-chess has its own directors.
