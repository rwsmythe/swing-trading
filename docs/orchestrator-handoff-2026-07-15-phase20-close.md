# Orchestrator handoff — 2026-07-15 — Phase-20 CLOSE

**From:** orchestrator gen `d67f7279` (drove all of Phase 20: the 20-A D25 corrector fix + witnessed data correction, 20-B, 20-C, the R1/R2/R3 riders, and the close ritual; handing off at the operator's direction after completing the close ritual).
**To:** the next orchestrator generation.
**Bootstrap first:** `scripts/orchestrator_bootstrap.md` → `docs/orchestrator-context.md` → this file.
**Main HEAD at handoff: `e6b9b40b`** (+ the commit of this handoff). **Schema v31 (Phase 20 = ZERO migrations). Suite ~9115/5/0. Streak 3983 trailer-clean.**

---

## State

- **PHASE 20 (Reconciliation Integrity & Correction Paths) CLOSED 2026-07-15.** All three production arcs + all three riders shipped, witnessed, and merged; the close ritual (archival sweep + CLAUDE.md line-3 + orchestrator-context in-flight) is done. **No active phase.**
- **REMAINING (NOT the orchestrator's):** the **CHARC close audit** on the post-ritual HEAD — CHARC runs its own fresh suite + verifies the close on disk. Then, per the operator's standing directive (banked at `b87d7ba9`), **CHARC's own generational-handoff prep follows the audit.** After that, **await the operator's next commission.**

## What shipped in Phase 20

- **20-A (D25) — the headline.** A 2026-07-10 operator-driven forensic reconciliation (`docs/broker-ledger-forensic-reconciliation-2026-07-10.md`) decomposed a $10.94 equity_delta to the cent and pinned the reconciliation tier-1 auto-corrector corrupting 3 fill rows (wrong-leg matching on same-qty pairs). Half-A guards (A1 same-qty→tier-2, A2 side/date/2.0%-band, A3 dedicated `ReCorrectionContradictionError`, A4 fills↔trades watchdog) + Half-B data (3 audited tier-3 fill overrides, the SATL trade-11 no-schema void, tuition 16→15) merged at `d5999345`. **B3 RD-witnessed to the cent** (AMN −$9.60→+$1.17; ledger↔broker $1555.80 exact; the badge self-cleared via re-evaluation; run-78 proved the guards in anger). A scope-premise correction was caught at writing-plans (the root-cause matcher was `schwab_reconciliation.py`, NOT the classifier); the #33 chain-stamp was WITHDRAWN by RD after the orchestrator's cross-discrepancy flag caught his premise-miss.
- **20-B (D22, `f7fb1aa2`)** — gated the general `discrepancy resolve` (subject-exists pending → refuse; FK-orphans pass via the reused 19-F `orphaned_affected_target`; `--force` records the audited bypass + keeps the reason contract). codex-auto-review surfaced all 4 majors the diff-only review missed (the 18-H.4 pattern again).
- **20-C (D23/D24, `ec348221`)** — the coherence-UX cluster (untracked-position out-of-framework guidance block, guidance-not-write-path; a netted-basis equity_delta diagnostic view; the badge links in BOTH lit states). NO new base-VM field.
- **Riders:** **R1** `comms_stop_hook` sibling-import fail-open (`b6cee694`) · **R2** AGENTS.md → a thin CLAUDE.md pointer (`ac9e7d42`; codex-verified followed) · **R3** the gitignored `.sessions.json` dead-gen tidy.

## Banked for a future lull (CHARC-registered)

- The **A-4 dedicated `discrepancy_type`** (migration 0032 + the #11 one-commit multi-mirror discipline) — the semantically-clean version of 20-C/20-A's no-schema fallback.
- **V2 candidate: execution↔fill identity linking** — the same-side/same-qty price-swap blind spot (economically neutral in V1).
- **V2 candidate: the strict-ALL stats-only aggregation choke point** (RD's D-B2 bound-b) — the closed-world SATL-void completeness.
- **Trailing:** director docs (`charc-state.md`, `rd-state.md`, `tool-director-context.md`, `phase20-scope-charc.md`) may carry stale relative links to the 20-A/B/C briefs now under `docs/archive/phase20/` — CHARC/RD reconcile their own state docs at the audit (flagged in the close return report; NOT the orchestrator's lane to edit director docs).

## Process learnings (this session — carry forward)

- **The witness seed helper pattern.** For an operator+CHARC witness of *lit/active* states that the clean DB doesn't currently show (a lit badge, a pending-ambiguity row, an untracked position), build a **reversible dry-run-first seed helper**: `--seed` plants production-shape rows (tagged with a sentinel in `delta_text`) on the live DB, the operator/CHARC witness the CLI/GUI against the worktree code, then `--cleanup` deletes by the sentinel. Verify the full seed→cleanup cycle YOURSELF first (the CHECK constraints are strict — a `pending_ambiguity_resolution` row needs a non-NULL `ambiguity_kind`; an FK-orphan needs a dangling FK inserted with `PRAGMA foreign_keys=OFF`). Satisfies the seeded-gate memory (witness the clean default too).
- **The D25 verify-don't-assume discipline, applied twice.** (1) The scope-premise correction at writing-plans (the matcher was in a file the brief didn't name). (2) The #33 cross-discrepancy flag: the live DB showed #33/#34 on SEPARATE discrepancies (not a single broken chain as the plan framed), so a director-ruled stamp was flagged BEFORE encoding — RD then withdrew it. **When the live DB contradicts the plan's/brief's/director's premise, FLAG it before acting.**
- **Live-DB mutation drivers are dry-run-first.** The Half-B driver + the witness seed helper both defaulted to a read-only preview + printed the exact planned mutations; the orchestrator verified against the live shape before the operator ran `--execute`. Ground every field against the real INSERT shape (the `_row_to_*` / schema `SELECT sql` probe).
- **The badge is stored-discrepancy-driven, not a live recompute.** `_compute_cash_coherence_badge` reads the most-recent completed schwab_api run's unresolved equity_delta — a data fix doesn't clear it until a fresh reconciliation re-evaluates (a `swing schwab fetch --all`), which is also the guards' live-fire proof. NOT the D24 acknowledge (RD's route-to-data-fix principle).
- **Dead-gen registry hygiene.** Accidental orchestrator spin-ups can clobber the legacy `comms/.sessions.json` orchestrator singleton (launcher read-modify-write). The G6 `comms/sessions/` registry self-expires strays; the singleton needs a manual reconcile to the live gen. `comms/` is gitignored — no commit.
- **Sweep-safety (D21) is binding at the close.** Grep `tests/`+`swing/`+`scripts/` for EVERY moved filename before a docs `git mv`; a production-cited doc (the forensic, cited by the 20-C diagnostic + its test) STAYS top-level. The close's green claim postdates the ritual's LAST commit.

## Standing facts

- **Directors:** CHARC (`docs/charc-state.md`) + RD (`docs/rd-state.md`). A director's ACTION-BEARING inbox message = operator-pre-authorized; act on it as an operator-hand-carried prompt. `decision_request` stays operator-only. You POST status/return_report to directors after YOUR QA; implementers never post to directors.
- **Dispatch:** the orchestrator spawns `.claude/agents/implementer-<model>-<effort>` cells via the Agent tool (announce the cell + wait-vetoable before spawn); the protocol SPOF is `docs/implementer-dispatch-recipe.md`; worktrees at `<repo>/.worktrees/<name>` (all Phase-20 worktrees cleaned; `.worktrees/` is empty). Fold writing-plans into a single executing dispatch only for settled small designs (CHARC-authorized per-arc).
- **Local-first:** this gen did NOT push to origin — local `main` is many commits ahead of `origin/main`. No schema phase-wide (v31).
- **Comms:** run `scripts/role_mail.py` from the MAIN repo dir; bodies via the Bash tool must be BACKTICK-FREE and `$`-free (both get mangled by the shell).
