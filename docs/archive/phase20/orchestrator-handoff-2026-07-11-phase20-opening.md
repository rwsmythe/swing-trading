# Orchestrator handoff — 2026-07-11 — Phase-20 opening (20-A queued, deadline pre-Monday-open)

**From:** orchestrator gen `3ebd6c5b` (closed Phase 19 clean; oriented to Phase 20; handing off at context-capacity — NOT because work stalled).
**To:** the next orchestrator generation.
**Bootstrap first:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file → then the 20-A brief + the Phase-20 scope.
**Main HEAD at handoff: `ea62639e`. Schema v31. Suite 9033/5/0. Trailer-free streak 3915 at the Phase-19 close; all my commits trailer-clean.**

---

## State

- **PHASE 19 CLOSED, clean** (2026-07-07; CHARC audit `docs/phase19-close-audit-charc.md`). Six arcs shipped+witnessed, close housekeeping + the shadow-expectancy Option-C coda done, worktrees cleaned. Nothing from Phase 19 is outstanding. My carried flags all found Phase-20 homes (D22→20-B, AGENTS.md→R2 thin-pointer [operator-resolved], dead-gen→R3, stop-hook import→R1).
- **PHASE 20 SCOPED + operator-approved** 2026-07-11 (`docs/phase20-scope-charc.md`). Theme: harden the **trading-ledger measurement chain** — the mirror of Phase-19's research-chain hardening. Origin: the 2026-07-10 operator-driven forensic reconciliation pinned **D25** (the tier-1 auto-corrector corrupted 3 fill rows via wrong-leg matching on same-qty pairs; AMN's H1 outcome materially wrong −$9.60 vs true +$1.17; a phantom SATL trade). The equity_delta instrument caught it in 24h; BOTH directors nearly dismissed it — the phase exists because the operator decomposed instead.
- **NOTHING is dispatched to me yet** — my orchestrator inbox was EMPTY at handoff. The 20-A brief is COMMITTED but not inbox-dispatched. **Await the operator's go before dispatching** (the amended dispatch-authority model applies to an inbox action-bearing message; a committed-but-not-sent brief is not that).

## YOUR QUEUED WORK

### 20-A (D25) — THE URGENT HEADLINE. Deadline: COMPLETE pre-Monday-open + before RD's August monthly read.
**Brief: `docs/reconciliation-corrector-fix-20a-commissioning-brief.md` — READ IN FULL.** Founding evidence: `docs/broker-ledger-forensic-reconciliation-2026-07-10.md` (the 3 corrupted fills, the PINNED mechanism, the safeguard fix-list) + the corrector's confession rows in `reconciliation_corrections` (#28/#30/#33/#34).
- **Half A (corrector) MERGES FIRST / atomic-with Half B — NEVER data-first (RD-BINDING order; #33→#34 proves re-corruption reapplies).** A1 same-qty multi-candidate = ambiguity → tier-2 (never tier-1 auto); A2 side/date-proximity/%-band plausibility guards; A3 re-correction alarm (a 2nd differing auto-correction on an already-auto_applied fill → BLOCKED + material tier-2); A4 fills↔trades consistency invariant.
- **Half B (data):** B1 the 3 fill corrections via the audited operator-override path (fill 17→13.00, 28→24.53, 37→35.65; append-only supersede-chain); B2 **SATL trade-11 VOID — no-schema mechanism (the state CHECK enum has NO 'voided' → SCHEMA-STOP: if a CHECK widening/new column is genuinely needed, STOP and route to CHARC; NEVER raw-delete per D19); tuition restates 16→15**; B3 post-verify (RD-WITNESSED H1 re-derivation Σ-to-the-cent; badge self-clears ~$0.17; AMN flips −9.60→+1.17).
- **Scope (A5):** `swing/trades/reconciliation_classifier.py` (stays PURE — no I/O) + `reconciliation_auto_correct.py` (sandbox-gated, SAVEPOINT-per-discrepancy) + B2's touchpoints + tests. Tier-2 demotions flow through the EXISTING ambiguity machinery (`reconciliation_ambiguity_choices.py`/`get_choice_menu`). Fixtures = REAL PTEN/DFTX/AMN geometries + broker-true values (never synthetic-to-satisfy-guards).
- **Cells:** writing-plans `implementer-opus-xhigh` (matcher/guard + the B2 void design), executing `implementer-opus-high`. **Gates:** RD plan-stage review (SATL void mechanics + A2 band + ordering — RD has pre-committed weekend availability) → review-strong + codex-auto-review → suite/ruff/merged-head per merge → RD merge-blocking QA + RD-witnessed B3 + operator badge-death witness.

### 20-B (D22) — after 20-A (same module family). Gate the ungated general `discrepancy resolve` (FK-orphans pass; legit tier-2 pending needs the choice-menu or `--force`). Small; RD light + operator CLI witness.
### 20-C (D23/D24) — parallelizable with 20-A (file-disjoint, web-only). Coherence-UX: OOF-declare path + equity_delta diagnostic breakdown; principle (RD): coherence findings route to the DATA FIX, not the acknowledge. operator GUI witness (HTMX family).
### Riders: R1 `comms_unread_hook` bare-import hardening · R2 AGENTS.md thin-pointer (operator-resolved 2026-07-11; verify repo-access reviews follow the pointer) · R3 dead-gen registry tidy.

## Process learnings (this session — carry forward)
- **Extended-D21:** the tests-grep sweep-safety AND the after-change suite run apply to ANY tracked-config change (`.gitignore` included), not just doc MOVES. My H4 gitignore edit broke a research reproducibility test because I skipped both; the implementer's before-review suite caught it; I reverted to green + routed up → the directors turned it into a better design (Option C: default-ignore the ephemeral path + copy cited artifacts into the study's tracked location + a real git-tracking test). Applied correctly at the coda.
- **codex-auto-review on a Windows-checked-out WORKTREE hits a CRLF mass-diff** (WSL git flags the whole tree → codex reviews a whole-repo garbage diff). Fix = repo-local `git config core.autocrlf true` (cleans plain WSL git) BUT codex's internal git can still noise — prefer the `codex exec -s read-only` FILE-READING cold-audit on worktrees; from a MAIN checkout `codex exec review` runs clean. Banked in `docs/implementer-dispatch-recipe.md` §3.
- **role_mail bodies via the Bash tool must be BACKTICK-FREE** (bash command substitution mangles them — plain text only).
- **The dispatch machinery held** across the 3-arc parallel batch: writing-plans sub-agent → QA-on-disk (convergence from the REAL `.copowers-findings.md`) → plan-stage director review → executing (review-strong + codex-auto-review) → QA → rebase-onto-main + `--ff-only` + merged-head no-false-green PER MERGE → the binding witness → merge. Hold to it. `role_mail` ALWAYS from the MAIN repo dir.

## Standing facts
- **Directors:** CHARC (`docs/charc-state.md`) + RD (`docs/rd-state.md`). RD available over the weekend for the three 20-A gates. `decision_request` stays operator-only.
- Cells library `.claude/agents/implementer-*.md`; dispatch SPOF `docs/implementer-dispatch-recipe.md`; worktrees at `<repo>/.worktrees/<name>` (all Phase-19 worktrees cleaned; `.worktrees/` is empty).
- I did NOT push to origin (local-first). No schema expected phase-wide (v31); the 20-A void carries the explicit schema-STOP.
