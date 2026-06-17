# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** This is the one always-current state pointer for the CHARC (Tool Development Director) role. The dated session log in [`docs/tool-director-context.md`](tool-director-context.md) §6 is APPEND-ONLY history; current state lives HERE only. Bootstrap reads this file FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-06-16 (eve). **Phase 18 ACTIVE** (data-collection integrity). **Schema v31** (0031 untracked_broker_position; operator-witnessed live-migration). main HEAD ~`b00ce9e8`; ahead of origin (pushed once this session at `0bc82fe8`). ZERO `Co-Authored-By` intact. **Topology: ONE live generation** — orch-2 (Phase-18); orch-1 (harness) decommissioned. `main` moves under it → `git symbolic-ref --short HEAD == main` guard + pathspec commits (§5.8).

---

## No arc in flight — awaiting operator sequencing of the next -H item

**18-H.6.1 — orphan attribution (banner + clear + sensible state): COMMISSIONED, brief + prompt ready, HELD for operator dispatch.** Brief + my §3 pass: [`docs/phase18-arc-h6-1-dispatch-brief.md`](phase18-arc-h6-1-dispatch-brief.md) (`986e0690`). Three parts (witness-surfaced): (1) orphan banner/count inclusion; (2) a no-FK-safe terminal resolver; (3) route `untracked_broker_position` to `unresolved`, NOT the `pending_ambiguity_resolution` limbo. **Carve-out** = `swing/trades/{reconciliation,reconciliation_classifier,schwab_reconciliation}.py` + `swing/data/repos/reconciliation.py` (+ metrics/cli/web reconcile, not lock-restricted). **NO new schema on the recommended design** (the resolver reuses `acknowledged_immaterial`; C2 STOP-and-flag to CHARC if a new RESOLUTION_TYPES value is needed → a schema sub-decision). Cell opus-high. Dispatch AFTER nothing (18-H.6 is merged) — just awaiting your go. On dispatch → review-strong+codex-auto-review → CHARC QA → the §5.10 operator live-witness (SPCX orphan now banners + unresolved + clearable; resolves cleanly after journaling).

## Phase-18 -H remaining (operator-sequenced)

- **18-H.6.1** — brief ready (above), awaiting dispatch.
- **18-H.5** — dead-code hardening audit (brief `f3b95d3e`; AUDIT-FIRST, default KEEP). HOLD.
- **18-G** — broad brief-corpus sweep (D10; harness hygiene, my lane).
- **RD watch-standard amendment** (RD-lane).
- **AT PHASE-18 CLOSE:** CLAUDE.md line-3 re-compaction + the §6 session-log compaction (overdue).

## CHARC follow-ups (not yet actioned)

- **F1 — codex-auto-review WSL-CRLF phantom** (large/multi-file diffs via WSL; cross-check vs Windows `git diff --numstat`; candidate -H `.gitattributes` normalization). Adoption-scoring signal.
- **F2 — Accept-header media-range parser** (web-polish R2 Minor; D8-like two-handler dup).
- **Scaffold germination backlog** [`docs/harness-template-scaffold-backlog.md`](harness-template-scaffold-backlog.md) — B-1..B-5 OPEN (coa-chess germination; deferred-correction; incl. swing `tool-director-context.md` §5.1 peer-dissent sharpening via B-5).

## Closed this session window

- **18-H.6 MERGED + CLOSED** (`2817b299`; close-out `b00ce9e8`; **schema v30→v31**; 8588 green) — `untracked_broker_position` first-class discrepancy; the journal-driven recon blind spot closed. Operator live-witnesses 2/2 (migration v31 clean; recon caught the real SPCX orphan). C4 caller-gate RATIFIED; B [P1] orphan-attribution CITED → 18-H.6.1.
- **Harness scaffold dogfood build DONE + ACCEPTED** (harness-template `master @ d8ad5c9`); orch-1 decommissioned; germinating as coa-chess (operator-run; the scaffold backlog B-1..B-5 accruing).
- **18-H.1** (`1a2a774d`; live-witness 3/3) · **web-polish 18-H.2/.3 + R1** (`e53b0886`; gate 3/3) · **director state-pointer convention** (`fb4b61a9`; THIS file = reference instance).

## Debt register (§4): CLOSED D6/D3/D11/D13/D14 · PARTIAL D1 · WATCH D5/D9/D12 · OPEN D7(=R1 declared)/D8/D10(=18-G)/D15.

## Probe: all within thresholds (last bootstrap run). My inbox: 0 unread.

## Behavioral load-bearing (full text in charter §5)

§5.1 director = PEER, push back at a LOW threshold — **state disagreement plainly + UNPREFACED, don't ask permission to dissent** (B-5; no deference-drift after a correction) · **FYI ≠ act — action needs EXPLICIT direction** · §5.7 verify-the-negative on disk (incl. tripwire premises) · §5.8 **pathspec-commit + `symbolic-ref==main` guard** · §5.9 orchestrator scope swimlane-limited (harness architecture → CHARC) · §2.7 directors do design dialogue, NEVER run copowers cycles · commit briefs BEFORE the inline prompt · QA on disk, never from the self-report.
