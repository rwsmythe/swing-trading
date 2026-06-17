# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** This is the one always-current state pointer for the CHARC (Tool Development Director) role. The dated session log in [`docs/tool-director-context.md`](tool-director-context.md) §6 is APPEND-ONLY history; current state lives HERE only. Bootstrap reads this file FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-06-16 (eve). **Phase 18 ACTIVE** (data-collection integrity). **Schema v30** (→v31 in flight via 18-H.6). main HEAD `3c5c1ec6`-ish; ahead of origin (pushed once this session at `0bc82fe8`). ZERO `Co-Authored-By` intact. **Topology: ONE live generation** — orch-2 (Phase-18); orch-1 (harness) DECOMMISSIONED. `main` moves under it → `git symbolic-ref --short HEAD == main` guard + pathspec commits (§5.8).

---

## ONE live workstream — 18-H.6 (executing)

**18-H.6 — untracked broker position → a first-class `untracked_broker_position` discrepancy.** Option (a), operator-concurred. EXECUTING (`.worktrees/18-H.6-untracked-broker-position`, `implementer-opus-high`). Brief + my §3 architecture pass: [`docs/phase18-arc-h6-dispatch-brief.md`](phase18-arc-h6-dispatch-brief.md) (`3c5c1ec6`).
- **Scope:** a new Schwab-driven orphan pass (loop `schwab_positions`, emit the discrepancy for each ticker with no journal open_trade, qty+market_value, additive); the #11 atomic enum widening (CHECK + `DISCREPANCY_TYPES` + `_DISCREPANCY_TYPES` + validator + `MATERIAL_BY_TYPE`, one commit); **migration 0031 (v30→v31**, 0019 rebuild pattern, strict `pre==30` backup-gate); REPLACE the journal-flat `orphan_broker_position` warning. **TRIPWIRE** (schema + `swing/trades`/`swing/data` carve-out) — brief IS the pass; C1–C5 binding.
- **Carve-out:** `schwab_reconciliation.py` + `reconciliation.py` + `models.py` + `0031_*.sql` + `db.py` (version/backup-gate ONLY — confirm at QA). Read-only default returns after.
- **ON RETURN → MY LEG:** QA-on-disk (the #11 trio + the migration discipline + additive-only + sandbox gate + db.py scoped to version/gate) → the **operator MIGRATION live-witness** (v30→v31) + the **§5.10 BINDING operator RECON live-witness** (the discrepancy fires for the operator's real IPO shares; a tracked position doesn't false-orphan) → merge. NO RD merge-block (operational recon, not the research measurement core).

## CHARC follow-ups (not yet actioned)

- **F1 — codex-auto-review WSL-CRLF phantom** (large/multi-file diffs via WSL only; cross-check vs Windows `git diff --numstat`; candidate -H `.gitattributes` normalization, non-trivial). Adoption-scoring signal.
- **F2 — Accept-header media-range parser** (web-polish R2 Minor; D8-like two-handler dup; candidate follow-up).

## Pending CHARC items (operator-sequenced, after 18-H.6)

- **18-H.7** — `role_mail`-on-ATTENTION = CHARC comms-sender ruling + nightly-pipeline-step touch.
- **18-H.5** — dead-code hardening audit (brief `f3b95d3e`; AUDIT-FIRST, default KEEP). · **18-G** — brief sweep (D10).
- **AT PHASE-18 CLOSE:** CLAUDE.md line-3 re-compaction + the §6 session-log compaction (overdue/verbose).

## Closed this session window

- **Harness scaffold dogfood build DONE + ACCEPTED** (harness-template `master @ d8ad5c9`; 168 green, guard green, zero-hard-dep, R1 traversal triple-verified; bare-clone bootstrap-dry-run witness PASS). MAJOR-4 broad-guard model ratified; AR-MAJOR-1 identity-invariant fold; 3 codex-auto-review V2 items in the scaffold's `.copowers-findings.md`. Germination = the new repo's own CHARC, later (NOT swing). orch-1 decommissioned.
- **Director current-state-pointer convention SHIPPED** (`fb4b61a9`) — THIS file is the reference instance.
- **18-H.1** Schwab token configured-but-absent→YELLOW (`1a2a774d`; operator live-witness 3/3). **Web-polish 18-H.2/.3 + R1** (`e53b0886`; gate 3/3).
- 18-D nightly half (`4d17492b`); 18-H.4/.4.1 (`1a916375`); the codex-auto-review A/B → 3 binding harness changes.

## Debt register (§4): CLOSED D6/D3/D11/D13/D14 · PARTIAL D1 · WATCH D5/D9/D12 · OPEN D7(=R1 now declared)/D8(F2 fresh instance)/D10(=18-G)/D15.

## Probe: all within thresholds (last bootstrap run). My inbox: 0 unread.

## Behavioral load-bearing (full text in charter §5)

§5.1 director = PEER, push back at a LOW threshold (no deference-drift after a correction) · **FYI ≠ act — action needs EXPLICIT direction** · §5.7 verify-the-negative on disk before asserting (incl. tripwire premises) · §5.8 **pathspec-commit + `symbolic-ref==main` guard** · §5.9 orchestrator scope swimlane-limited (harness architecture → CHARC) · §2.7 directors do design dialogue, NEVER run copowers cycles · commit briefs BEFORE the inline prompt · QA on disk, never from the self-report.
