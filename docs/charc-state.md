# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** This is the one always-current state pointer for the CHARC (Tool Development Director) role. The dated session log in [`docs/tool-director-context.md`](tool-director-context.md) §6 is APPEND-ONLY history; current state lives HERE only. Bootstrap reads this file FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-06-17. **Phase 18 ACTIVE.** **Schema v31.** main HEAD `3ebbbcc8` (HEAD attached; the 18-H.6.1 detached-review state resolved at merge). Ahead of origin (last push `0bc82fe8`). ZERO `Co-Authored-By` intact. **Topology:** swing = orch-2 (Phase-18); coa-chess germination running in parallel (operator-driven, its own CHARC+orch — survived a PowerShell crash; orchestrator runs in VS Code).

---

## No arc in flight — awaiting operator sequencing of the next -H item

**Phase-18 -H remaining:** **18-H.5** (dead-code hardening audit; brief `f3b95d3e`; AUDIT-FIRST, default KEEP; HOLD) · **18-G** (broad brief-corpus sweep, D10; my lane) · **RD watch-standard amendment** (RD-lane) · **AT CLOSE:** CLAUDE.md line-3 + §6 log compaction (overdue).

## coa-chess germination (operator-driven; I advise as scaffold architect — do NOT contaminate with swing config; do NOT drive its repo)

- **Session registry proven live** (first end-to-end test + the single-orchestrator provenance re-test): both architect-flagged risks resolved best-case; the vanishing-message anomaly resolved-as-artifact (two-orchestrator cross-drain; per-gen inboxes are session-keyed → no cross-drain). Convention banked: explicit `:<session_id>` under concurrency; bare = `newest_live` heuristic (→ backlog B-10).
- **Genericity-guard REDESIGN (B-9) — coa-chess's deep critique + reference impl (`ec9856d`/`9aee81d`); CHARC owns it.** The purity gates are right in purpose but blunt/leaky/permanent: ship an `is_instance_surface()` exemption (instances green-by-construction), scope the vocab/ticker bans to the CORE (the structural dependency-posture test is the real teeth; the word-ban is a doc-only proxy), treat residue/ticker bans as a one-shot AUTHORING gate (the scaffold's own SPY/QQQ denylist is itself swing-contaminated), and ship a `review-gate-<app>.md` fill-location convention. **The deeper structural critique my MAJOR-4 ratification missed.** Supersedes B-8's "retire the gates" fix.

## Scaffold germination backlog [`docs/harness-template-scaffold-backlog.md`](harness-template-scaffold-backlog.md) — B-1..B-10 OPEN (deferred-correction)

B-1 README CHARC-launch · B-2 PS `.\scripts\` · B-3 **CHARC = opus/max (the one fixed role config)** · B-4 germination git-history · B-5 peer-dissent unprefaced · B-6 superior-QAs-subordinate · B-7 role model/effort per-project (CHARC excepted) · B-8 **BLOCKER** template gates trip on seam-fills · **B-9 genericity-guard REDESIGN** (scope to CORE + instance-surface seam) · B-10 registry explicit-under-concurrency convention.

## CHARC follow-ups: F1 codex-auto-review WSL-CRLF phantom (cross-check Windows numstat; `.gitattributes` candidate) · F2 Accept-header media-range parser (D8-like).

## Closed this session window

- **18-H.6.1 MERGED + CLOSED** (`6b7db700`; close-out `3ebbbcc8`; 8618 green) — orphan attribution: banner/count inclusion + a no-FK-safe resolver (reused `acknowledged_immaterial`, C2 held NO schema) + the `unresolved`-not-`pending_ambiguity` routing. **Operator §5.10 witness 3/3** (banner reflects the orphan; the legacy **ID-68** finally cleared via the R2 `ambiguity_kind` auto-NULL — live-validating my R2 ratification; fresh recon orphan id-70 lands `unresolved`). CHARC QA-on-disk PASS + R2 generalization RATIFIED. Cleanup: id69/id70 SPCX orphans open (operator clears via web / journals SPCX).
- **18-H.6** (`2817b299`, v31) · harness scaffold DONE+ACCEPTED (`d8ad5c9`; germinating as coa-chess) · 18-H.1 (`1a2a774d`) · web-polish (`e53b0886`) · the director state-pointer convention (`fb4b61a9`, THIS file = reference instance).

## Debt register (§4): CLOSED D6/D3/D11/D13/D14 · PARTIAL D1 · WATCH D5/D9/D12 · OPEN D7/D8/D10(=18-G)/D15.

## Behavioral load-bearing (full text in charter §5)

§5.1 director = PEER, push back at a LOW threshold — **state disagreement plainly + UNPREFACED** (B-5) · **don't contaminate the generic scaffold with swing config** (a recurring catch this germination — own it when caught) · **FYI ≠ act** · §5.7 verify-the-negative on disk · §5.8 **pathspec + `symbolic-ref==main` guard** (3 roles share main; a crash left it detached this session) · §5.9 orchestrator scope swimlane-limited (harness architecture → CHARC) · §2.7 directors do design dialogue, NEVER run copowers cycles · commit briefs BEFORE the inline prompt · QA on disk, never from the self-report.
