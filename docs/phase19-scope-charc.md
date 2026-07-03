# Phase 19 — Launch-Context Robustness & Measurement Parity (CHARC scope)

**Status:** OPERATOR-APPROVED 2026-07-02 (chat: all six arcs + both riders — "let's add the riders and get started"). **Author:** CHARC per §2.3 (propose/approve). **Baseline at scoping:** main HEAD `321c4a27`; schema **v31** (no schema change expected anywhere this phase); fast suite 8881 green at the Phase-18 close; harness probe clean (the one stale-artifact ATTENTION disposed 2026-07-02, `.copowers-session-2bb8b39216b4.json` deleted).

## Theme

Two clusters, one phase:

1. **Launch-context robustness** — the #5 anchor-consistency fix and the weeknight scheduled task it gates (an unattended scheduled task IS a non-interactive launch context — the exact #5 vector; ordering is HARD).
2. **Measurement parity + monitor signal hygiene** — the live-vs-shadow ruleset divergences and monitor false-REDs surfaced 2026-06-30..07-03 by RD and the operator (coverage_gaps trailing-delisting false-RED; shadow-engine risk-unit collapse; the Day-3-5 partial-trim advisory gap; the unresolvable cash-review nag).

All arcs are small-to-medium. Default phase posture is **read-only** on `swing/trades/` + `swing/data/` with two ANTICIPATED §3 carve-outs (19-E certain; 19-F possible — both get the CHARC architecture pass at commissioning).

## Arcs

| Arc | Scope | Tripwire | Gates | Size | Sequence |
|---|---|---|---|---|---|
| **19-A** coverage_gaps CALIBRATION-C trailing-delisting fix | Accept clause-2b (skip-warning-explained) holes REGARDLESS of clause-1; clause-1 continues to gate ONLY clause-2a (whole-session-miss). Kills the live recurring false-RED (CNTA delisting, 60 gaps, run 117). Brief: [`coverage-gaps-trailing-delisting-fix-commissioning-brief.md`](coverage-gaps-trailing-delisting-fix-commissioning-brief.md) | none (edits existing `swing/monitoring/research_health.py`) | RD plan-stage review + RD merge-blocking QA (measurement semantics — RD designed CALIBRATION C and requested review); live-DB gate (the RED must flip GREEN) | tiny | **FIRST** — the only live-symptom arc |
| **19-B** #5 anchor-consistency + guard | RE-SCOPE brief `19185b04` (its absolutize-`config_path` approach is the WRONG root — would mask worktree isolation): a launch context reads+writes+pushes ONE root (its own), fully isolated from main's production artifacts, + the write-nothing-on-suspicious-empty guard as backstop. Pin the residual sub-symptoms at resume (`run id: unknown`; the empty-db coverage symptom via a divergent-config worktree) | none expected | RD guard-semantics review | small-med | after 19-A (same file: `research_health.py` — sequential, never concurrent). Operator window: the ~07-04/05 weekend revisit |
| **19-C** weeknight-pipeline scheduled task | Windows Scheduled Task running the pipeline unattended on weeknights. Banked design-Q list: lease coexistence with manual runs (graceful already-running skip), run-time vs EOD data availability (+ HST↔ET offset), holiday/non-session graceful no-op, Schwab 7-day token-TTL degrade, `swing.exe`/`python -m swing` entry-point + PATH, unattended logging + monitors reading the right artifacts. MUST launch from the MAIN repo root with the standard profile | **YES — new standing process** → CHARC architecture pass at commissioning | CHARC §3 pass; operator witness of the scheduled run | medium (the least-small arc) | **HARD after 19-B** — landing it first = a permanent unattended #5 trigger poisoning production every weeknight |
| **19-D** shadow-engine risk-unit fix | Fix the risk-unit collapse (VSTS +27.3R; effective risk unit ~13-17× tighter than ATR). T4 evidence RE-SCOPES the original plan: `entry_bar_ambiguous=True` is DEGENERATE by construction (165/165 broad-watch signals) — gating on the flag would gate the whole population. Fix = risk-unit FLOOR and/or a REAL discriminator (risk-unit-to-ATR ratio); trace WHY VSTS slipped the existing `degenerate_risk` guard (run.py:183). Engine is pure-recompute → retroactive-by-re-run, NO backfill, no clock. RD's confirmatory T4 re-read is pre-committed on the first post-fix artifact | none expected (edits existing `research/harness/shadow_expectancy/simulator.py`) | **RD merge-blocking QA (measurement chain)** + RD plan-stage review | small-med | parallelizable (file-disjoint from everything) |
| **19-E** Day-3-5 partial-trim advisory | Calendar-triggered partial advisory in the recommendations surface (day 3–5, entry day = day 1), defaults aligned with the engine (`PARTIAL_SESSION_N=3`, 50%, close>entry). Root cause verified by RD: `advisory.py:135` triggers on R>=+1R only — dead on wide-stop geometries (VSTS: +1R = +17%), while the engine mechanically assumes the day-3 partial → the measured strategy and the GUI-prompted strategy diverge; a standard-cohort operator cannot execute what H1 is measured under. **The DST 4.B trigger fork (second trigger alongside +1R vs re-trigger/replace) is an OPERATOR decision at commissioning** — the transcription explicitly left it unresolved | **YES — `swing/trades/advisory.py` = phase-isolation carve-out** (RD's "no tripwire apparent" corrected; same class as the historical 3d advisory carve-out) → CHARC §3 pass | CHARC §3 pass; RD trigger-semantics review (cohort parity); operator GUI witness (binding for HTMX/advisory surfaces) | small | parallelizable; highest operator salience (missed trade action on VSTS trade 17) |
| **19-F** dashboard "cash review" nag — unresolvable via CLI or GUI | **DIAGNOSIS-FIRST.** Step 1 = read-only live-DB triage: the exact discrepancy row(s), type, run-over-run emit history, the operator's acknowledge audit trail. Leading hypothesis = **D16** (step-7 re-emit suppression at `schwab_reconciliation.py:1795` covers only `pending_ambiguity_resolution`, NOT `acknowledged_immaterial` → acknowledge succeeds but next recon re-emits; the "cross-run re-emit NOT yet verified" caveat arriving live). Candidate set also: a genuinely unrecorded month-end ~$100 deposit (timing fits 07-02) needing a record-a-deposit path (capability gap?), or a real coherence drift. Fix scoped AFTER diagnosis; if D16 confirms, fix = the sketched suppression-widening (no schema) and D16 closes | possible — if the fix lands in `swing/trades/schwab_reconciliation.py` (carve-out) → CHARC §3 pass at fix-scoping | RD review if recon/coherence semantics move (`current_equity` feeds sizing); operator GUI witness on the acknowledge surface | small (post-diagnosis est.) | parallelizable; triage can run any time |

## Riders (operator-approved 2026-07-02; dispatch in any lull, independent of arc order)

- **R1 — F6 `comms_stop_hook.py` hardening back-port** (swing's live Stop hook ← the scaffold's Arc-C hardened version): strict-decode fail-open + missing-`stop_hook_active`→allow-stop + block only on exact `is not False`. Swing's live hook can fail-CLOSED in edge cases → a loop risk. Small, measurement-neutral, sub-tripwire.
- **R2 — D18-FORM `harness_probe` research-size ceiling** (brief archived at [`archive/phase18/harness-probe-size-check-commissioning-brief.md`](archive/phase18/harness-probe-size-check-commissioning-brief.md) — it was deferred-to-close but NOT executed at the Phase-18 close; the 2026-07-02 probe output confirms no size-check line). v1 ceilings 500 MB / 200 MB on `exports/research` + `research/harness`; quiet at the post-cleanup 1.9M/2.9M baseline — purely a forward-looking regrowth guard. CHARC-lane QA.

## Sequencing constraints (the binding ones)

1. **19-A before 19-B** — both edit `swing/monitoring/research_health.py` (different regions: the CALIBRATION-C clause logic vs read/write anchoring + guard). Sequential, never concurrent.
2. **19-B before 19-C** — HARD. Rationale in the 19-C row.
3. **19-D / 19-E / 19-F are file-disjoint** from the chain and from each other — parallelizable at the operator's dispatch cadence.
4. Riders anytime.

## Corrections of record at scoping

- **19-E tripwire self-cert corrected:** RD's mail said "no schema/module/dependency tripwire apparent" — `advisory.py` IS a `swing/trades/` phase-isolation carve-out (§3 tripwire #5). Procedural consequence only (CHARC pass at commissioning); logged because tripwire misses are what the phase audit exists to catch.
- **Brief `19185b04`** ([`drumbeat-false-red-root-fix-5-commissioning-brief.md`](drumbeat-false-red-root-fix-5-commissioning-brief.md), still top-level — correctly NOT archived, it is live) **requires re-scope before the 19-B dispatch**; its absolutize-config approach is superseded by anchor-consistency + guard (CHARC + RD concur, 2026-06-27).
- **19-D re-scoped on T4 evidence** (RD 2026-07-03 mail): the ambiguous-entry flag is degenerate — floor/ATR-discriminator, not flag-gating.
- **D16 ↔ 19-F:** D16 is the leading hypothesis, not the diagnosis; the register entry moves with 19-F's outcome.

## Register motion expected this phase

D16 (via 19-F) · D18-FORM (via R2) · the #5 item + brief-19185b04 re-scope (via 19-B) · new entries as 19-F diagnoses. Phase-close audit per the standing §2.4 gate posture; §4.3 archival sweep of this phase's dead briefs at close.
