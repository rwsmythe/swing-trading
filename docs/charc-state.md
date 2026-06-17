# CHARC — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** The one always-current state pointer for the CHARC (Tool Development Director) role. The dated §6 log in [`docs/tool-director-context.md`](tool-director-context.md) is APPEND-ONLY history; current state lives HERE. Bootstrap reads this FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

**Last overwritten:** 2026-06-17 (CHARC session handoff — prior session at 100% context). **Phase 18 ACTIVE.** **Schema v31.** main HEAD = the docs commit landing this file (the SPCX pass `59f9fa4c` + the 18-H.5 catalog `3de49440` are upstream). HEAD attached to main; ZERO `Co-Authored-By` intact. **Topology:** swing CHARC (you, resuming) + a Phase-18 orchestrator being spun up fresh (prior gen exhausting) + coa-chess germination running in parallel (its own CHARC+orch; do NOT drive its repo or contaminate it with swing config).

---

## #1 LIVE ARC — SPCX out-of-framework carve-out (path B). Pass DONE; awaiting the orchestrator writing-plans dispatch.

- **Status:** CHARC architecture pass **GO, operator-confirmed, recorded** ([`docs/out-of-framework-holding-carveout-charc-architecture-pass.md`](out-of-framework-holding-carveout-charc-architecture-pass.md), `59f9fa4c`) + **posted to RD**. RD commissioning brief: [`docs/out-of-framework-holding-carveout-commissioning-brief.md`](out-of-framework-holding-carveout-commissioning-brief.md) (`78d6d5e6`).
- **Rulings:** (1) registry = a `[reconciliation] out_of_framework_tickers` config-list in user-config.toml, **NO schema/table**; (2) §2.4 equity-coherence refinement **DEFERRED** (registered fast-follow — L2 false-coherence risk + narrow-window value; tradeoff: the coherence check stays suppressed while SPCX held); (3) resolve existing SPCX orphans → `acknowledged_immaterial`, scoped+audited, at landing. **No new module** (config field + carve-out in `swing/trades/schwab_reconciliation.py`). Binding conditions C1–C5 in the pass doc.
- **NEXT (orchestrator):** run **writing-plans** (cell `implementer-opus-xhigh`, Codex to convergence). **RD merge-blocking on L1–L4** (QAs at the executing return). Then executing (cell `implementer-opus-max` — measurement-adjacent recon code).
- **CHARC's remaining role:** none on writing-plans (the pass is the spec); QA the writing-plans + executing returns vs C1–C5; the §5.10 operator live-witness mirrors 18-H.6 (declared SPCX emits no orphan; an undeclared one still banners; banner clears).

## Harness friction — sub-agent git-write (gates the SPCX executing dispatch)
The allowlist ALREADY allows bare `git add`/`commit`; the recipe ALREADY directs bare-git-in-worktree-cwd. The 18-H.5 cell was denied because it used `git -C "<worktree>"` (allowlisted for read-ops only). **Fix applied:** recipe §2 now explicitly says commit with BARE git from the worktree cwd, NOT `git -C` ([`docs/implementer-dispatch-recipe.md`](implementer-dispatch-recipe.md)). **LIVE TEST = the SPCX executing dispatch:** if a cell's bare-git-in-worktree-cwd commit is STILL denied, the cause is deeper (sub-agent permission inheritance) → then a settings/mode change (NOT a broad `git -C:*` allow — too broad). Do not pre-broaden permissions; let the next dispatch tell us.

## Closed / done this session
- **18-H.5 CLOSED at Phase 1 (no Phase 2)** — operator-confirmed. The read-only dead-code-hardening audit (catalog `docs/18-H.5-phase1-dead-code-audit-catalog.md`, `3de49440`) found **A=1 / B=0 / C=8** over ~30+ sites → the reader/monitor layer is overwhelmingly KEEP (the treadmill corollary is honored going forward; almost no legacy dead-code). The lone **A-1** (the `ambiguity_kind is None` disjunct in the Tier-2 409 guard, dead per the 0019 cross-column CHECK) is LOW-VALUE to remove (general 409 net already covers it) + retains a residual manual-edit/CHECK-relax vector → **left as a documented deliberate-keep** (preserve-the-safety-net). The catalog IS the deliverable.
- **18-H.6.1 MERGED+CLOSED** (`6b7db700`/close `3ebbbcc8`) — orphan attribution; the R2 generalization live-validated (legacy ID-68 cleared). **18-H.6** (`2817b299`, v31).
- **Artifact hygiene:** root codex/copowers stale review files + home-dir 17-A leakage CLEARED (operator-authorized). Kept the active 3 (`.codex/`, `.copowers-findings.md`, `.copowers-session-*.json`).
- The director state-pointer convention (`fb4b61a9`, THIS file = the reference instance).

## Queued (not urgent)
- **18-G — expanded harness-hygiene sweep** (phase-close boundary): stale briefs (the D10 corpus) + the home/root artifact recurrence-prevention (repo-anchored artifact paths so cwd-drift can't leak above the repo; a review-file cleanup-at-arc-close convention) + the brief moves to `docs/archive/phase<N>/`.
- **Scaffold germination backlog** [`docs/harness-template-scaffold-backlog.md`](harness-template-scaffold-backlog.md) — **B-1..B-10 OPEN** (deferred-correction; operator sequences a scaffold-revision pass). Headline: **B-9 genericity-guard REDESIGN** (coa-chess's 4-point critique + reference impl `ec9856d`/`9aee81d` — scope genericity to the reusable CORE structurally + a designed instance-surface seam; CHARC owns it). B-3 = CHARC fixed opus/max (the one fixed role config).
- **Phase-18 -H trailing:** 18-H.7 (nightly→rd-push, minor, needs my comms-sender ruling) · RD watch-standard amendment (RD-lane). **AT PHASE CLOSE:** CLAUDE.md line-3 + §6 log compaction (overdue) + my close audit.

## CHARC follow-ups: F1 codex-auto-review WSL-CRLF phantom · F2 Accept-header media-range parser (D8-like).
## Debt register (§4): CLOSED D6/D3/D11/D13/D14 · PARTIAL D1 · WATCH D5/D9/D12 · OPEN D7/D8/D10(=18-G)/D15.

## Behavioral load-bearing (full text in charter §5)
§5.1 director = PEER — **state disagreement plainly + UNPREFACED**, don't ask permission to dissent · **do NOT contaminate the generic scaffold with swing config** (recurring catch — own it when caught; the genericity-guard critique was the 3rd instance) · **FYI ≠ act** · §5.7 verify-the-negative on disk (the git-write fix came from reading the actual allowlist, not assuming) · §5.8 **pathspec + `symbolic-ref==main` guard** (3 roles share main; a crash left it detached earlier this session) · §5.9 orchestrator scope swimlane-limited (harness architecture → CHARC) · §2.7 directors do design dialogue, NEVER run copowers cycles · commit briefs BEFORE the inline prompt · QA on disk, never from the self-report.
