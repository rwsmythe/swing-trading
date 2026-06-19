# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** The one always-current state pointer for the CHARC (Tool Development Director) role. The dated §6 log in [`docs/tool-director-context.md`](tool-director-context.md) is APPEND-ONLY history; current state lives HERE. Bootstrap reads this FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-06-18 (CHARC **generational handoff** — prior gen at ~19% context). **Phase 18 ACTIVE.** **Schema v31** (unchanged this session — SPCX/§2.4/limbo were all no-schema). main HEAD ≈ `3ab23d86` (many docs commits this session, ALL `trailers []`, HEAD attached to main; the bootstrap's `git log`/`git status` give the live state — likely well ahead of origin/unpushed). ZERO `Co-Authored-By` intact. **Topology:** swing CHARC (you, fresh) + the Phase-18 orchestrator (shipped SPCX/§2.4/limbo this session) + RD; coa-chess germination runs in parallel in its OWN repo (own CHARC+orch — do NOT drive it or contaminate it with swing config).

---

## #1 — NO LIVE ARC. Await the operator. The swing-NLV / SPCX out-of-framework cluster CLOSED this session (3 arcs).

Nothing of CHARC's is in flight. The deferred follow-ups + queue (below) are operator-sequenced. Next obligations are operator-directed.

## Closed this session (full records: phase18-todo riders + the briefs + git history)
- **SPCX out-of-framework carve-out (path B) — MERGED @`5b24ef68`.** RD-commissioned (brief `78d6d5e6`) → CHARC §3 pass GO (`59f9fa4c`: `[reconciliation] out_of_framework_tickers` config-list, NO schema/module, carve-out in `swing/trades/schwab_reconciliation.py`, §2.4 deferred). Plan `52fc3ade`; all gates PASS (CHARC C1–C5 + RD L1–L4 + §5.10 live-witness; the dual review caught a real C2/L3 MAJOR — the TOML-table-keys silent carve-out).
- **swing-NLV §2.4 coherence — MERGED @`e1017b1e`.** Brief `3033c0f8`/`e9f3db3d` (+RD §9 L2 checklist), plan `3f6bd6e6`. CHARC C1–C5 + scope-extension RATIFIED + RD L2 PASS. **The §5.10 live-witness fired a TRUE drift** (a CHARC-owned brief PREMISE miss: the "math-sanity" `NLV−SPCX≈ledger` was false on the cited numbers — path B never recorded the swing cash that bought SPCX → ledger overstated). FIXED via **path (a)** — the operator records the OOF outlay as a swing `cash_movement` (`swing journal cash --withdraw <cost>`; brief §10 = the operational practice). Re-witness CLEAN. The live-witness was the net (tests + 2 directors missed the premise) → **lesson banked: memory `feedback_verify_premise_arithmetic_vs_live`** (verify a brief's quantitative premise on LIVE values; tests use real-derived inputs).
- **equity_delta limbo fix (§2.4 follow-up #2) — MERGED @`8fee6a1d`.** Brief `cb069227`/§8 (CHARC §3 pass; §0 ruled (A)), plan `3bcc483f`. The one-line pivot-skip widen (`_pivot_classify_and_dispatch_for_run` → skip `equity_delta` so a fired one stays `unresolved`/cleanable, not the tier-2 limbo — the 18-H.6.1 twin). CHARC C1–C4 PASS; §5.10 witness clean (id 71 cleared). **id 72** (path-(a) `cash_movement_mismatch`) = RD+CHARC **NON-ISSUE** (a one-time manual-cash acknowledge, same as the monthly deposit; correctly routed — it IS a record-matching ambiguity, unlike `equity_delta`; operator acknowledges → done; do NOT commission a fix).
- **Self-critique (carry forward):** THREE brief-grounding misses this session (the §2.4 premise; the limbo brief's "no sub-classifier" mechanism; its "material banner" wording — `equity_delta` is `material=0`). All caught at writing-plans grounding/QA (the gate worked). **Tighten:** ground ALL of a brief's load-bearing claims on disk before committing it, not just the edit site.

## Deferred follow-ups (low-priority, operator-sequenced — none active)
- **cash-recon ROOT fix** — auto-treat a declared-OOF Schwab TRADE-type txn as a swing transfer-out (automates the path-(a) manual practice; the recon SKIPs TRADE-type assuming journaled-via-P&L). CHARC §3 pass when commissioned.
- **(B) `equity_delta` materiality bump** — `MATERIAL_BY_TYPE 0→1` so a fired coherence drift hits the GUI material banner. Blast radius (all `equity_delta`; #11). Operator's call.
- **General cash-recon manual-cash ergonomic** — recognize ref-tagged/manual `cash_movements` as legitimately-unmatched (covers the monthly deposit + OOF reallocations). RD-flagged, PRE-EXISTING, CHARC-lane ops; **a §4 debt-register WATCH candidate** (fold into charter §4); only if the manual-acknowledge becomes a chore.
- **id 72** — operator acknowledges via the tier-2 reconcile flow (same as cm 4). Operator action.

## Operator standing directives (this session — load-bearing)
- **Phase-18-focus HOLD:** template/scaffold FIX work is HELD until Phase 18 lands (closes); **BANKING template feedback is explicitly OK.** This session banked **B-11** (comms-GUI dark-theme toggle), **B-12** (§8 peer-director-add checklist incomplete vs code), **B-13** (comms-GUI 5-sec-refresh-collapse → the SYSTEMIC finding: the scaffold's comms UI is a STALE pre-fix swing snapshot; recommend RE-SYNC, subsumes B-11) in [`docs/harness-template-scaffold-backlog.md`](harness-template-scaffold-backlog.md). Do NOT initiate scaffold-revision work until the operator lifts the hold at Phase-18 close.
- **WinError 10022** (`_ProactorBasePipeTransport._call_connection_lost` shutdown WSAEINVAL) = the benign asyncio/Windows uvicorn teardown race; **parked, benign-ignore** (operator-confirmed). Not a swing defect.

## Queued (not urgent)
- **18-G** brief-corpus sweep (D10) · **18-H.7** nightly→rd-push · **RD watch-standard amendment** (RD-lane). **AT PHASE-18 CLOSE:** CLAUDE.md line-3 + §6-log compaction (overdue) + my close audit + lift the template-work hold + the scaffold-revision pass (B-1..B-13).
- **Scaffold germination backlog** B-1..B-13 OPEN (deferred-correction; operator sequences a revision pass). Headline: **B-9 genericity-guard REDESIGN** (CHARC owns) · **B-13 RE-SYNC the comms UI from swing's current version** (subsumes B-11; the stale-snapshot root).

## Harness friction — RESOLVED
Sub-agent git-write: the recipe §2 bare-git-in-worktree-cwd convention WORKS — live-tested on the SPCX + §2.4 + limbo executing dispatches (no denial; trailers [] throughout). No permission broadening needed.

## CHARC follow-ups: F1 codex-auto-review WSL-CRLF phantom · F2 Accept-header media-range parser (D8-like).
## Debt register (§4): CLOSED D6/D3/D11/D13/D14 · PARTIAL D1 · WATCH D5/D9/D12 + NEW general-cash-recon-ergonomic candidate · OPEN D7/D8/D10(=18-G)/D15.

## Behavioral load-bearing (full text in charter §5; harness model in harness-architecture.md)
- **§5.1 director = PEER — state disagreement plainly + UNPREFACED; push back at a LOW threshold; never manufacture objections; a SCOPE/FRAMING correction does NOT lower the bar.** Blunt, call out the operator's errors (mine too — owned the §2.4 premise + the brief-grounding misses squarely this session).
- **Verify on disk before asserting** — the §2.4 premise miss + the 3 brief-grounding misses → ground ALL load-bearing brief claims (premise arithmetic, code mechanism, materiality flags) on disk, not just the edit site. The human/live-DB witness is the net; tests + Codex are fallible filters. (memories: `feedback_verify_premise_arithmetic_vs_live`, `feedback_adversarial_review_verify_data_shapes`, §5.7/§5.10.)
- **FYI ≠ act** — action needs EXPLICIT direction; else acknowledge + assess + await.
- **NO orchestrator inbox** — `role_mail --to` = `charc|rd|operator` only; route all orchestrator-facing comms VIA the operator (hand-carried inline prompts/relays). Dispatch-direction authority stays operator-hand-carried (comms taxonomy).
- **§2.7 directors do design dialogue + author/commit the brief + provide the inline prompt; NEVER run copowers cycles** (orchestrator/implementer-lane). **Commit the brief BEFORE the inline prompt.**
- **§5.8 pathspec-commit `git commit -- <file>`** (3 roles share main) + `symbolic-ref==main` guard before committing.
- **QA on disk, never from the self-report** — read the shipped diff/transcript at the tracked path; the orchestrator posts return reports to charc(+rd) after ITS QA; CHARC QAs the binding conditions; the operator §5.10 live-witness is binding.
- **Do NOT contaminate the generic scaffold with swing config** (recurring catch).
