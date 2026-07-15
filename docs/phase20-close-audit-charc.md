# Phase-20 Close Audit — CHARC

**Auditor:** CHARC. **Date:** 2026-07-15. **Audited HEAD:** `e3b6570f` (the close ritual's last commit). **Phase:** 20 — Reconciliation Integrity & Correction Paths (scoped 2026-07-11 → closed 2026-07-15; the substantive weekend target met — 20-A landed pre-Monday-open as directed, B/C/riders on calm cadence after).

## §1 Verdict

**CLEAN TO CLOSE.** All three arcs + three riders shipped, witnessed, merged; every binding gate re-verified by CHARC first-hand; zero schema migrations (v31 held a SECOND consecutive phase); zero tripwire false-negatives; the register retires the ENTIRE D22–D25 cluster — the phase completed the mission it was scoped for: the trading-ledger measurement chain is corrected, guard-protected, and reconciled to the broker to the cent.

## §2 Binding gates (CHARC-verified first-hand at/around `e3b6570f`)

| Gate | Result | Verification |
|---|---|---|
| Fast suite | **9115 passed / 5 skipped / 0 failed** | CHARC's own fresh `-n auto` run on `e3b6570f`, postdating the ritual's last commit (the D21 rule, honored at its second close) |
| ruff | clean | own run |
| Schema | **v31**, latest migration 0031 — zero Phase-20 migrations (the SCHEMA-STOP held: the void shipped no-schema; A4 took the no-schema fallback) | own read |
| Trailer streak | ~3,983 (orchestrator deep-scan; CHARC 100-window corroborates zero non-empty) | own scan |
| Probe | zero ATTENTION (line-3 at 4,470/9,000 post-compaction; docs 32 top-level after the sweep 35→31+audit) | orchestrator run + CHARC re-check |
| Sweep safety (2nd exercise) | PASSED — **and it caught a real keep:** the forensic doc is PRODUCTION-cited (the 20-C diagnostic + its test); moving it would have broken a test and dead-linked the UI | verified from the ritual report + the file's top-level presence |
| Ledger↔broker | **TO THE CENT** ($1,555.80), dual-path (RD's raw-fills derivation ∥ the production readers) | RD's witnessed B3 + CHARC's forensic arithmetic |

## §3 Roster (all CLOSED)

| Arc | Outcome |
|---|---|
| **20-A** corrector + corrections (D25) | The tier-1 matcher can no longer wrong-leg-corrupt (A1 ambiguity→tier-2, A2 side/date/2%-band, A3 re-correction alarm, A4 fills↔trades invariant); the 3 fills corrected via audited overrides; SATL voided no-schema (audit-visible, cohorts exclude); AMN −$9.60→**+$1.17 exact**; **proven in anger** — run 78 + five scheduled runs reconciled over the exact causal geometry with zero re-corruption. RD: "the August read opens on corrected, guard-protected, to-the-cent-reconciled values" — 3 weeks early |
| **20-B** resolve gate (D22) | Orphans pass (19-F predicate reused, single-def), legit-pending refuses, `--force` records the bypass + still enforces reason-required (the codex-auto-review catch — 4 real findings the diff-pass missed, again) |
| **20-C** coherence UX (D23+D24) | The badge links in BOTH lit states; the netted diagnostic (kill-test −10.94 vs −465.84); the recurring-holding guidance; principle shipped: findings route to the DATA FIX |
| **Riders** | R1 the stop-hook fail-open (the 4th scaffold behavior finally ported); R2 AGENTS.md → a 23-line pointer, **codex-follows-it verified live**; R3 the registry singleton reconciled, comms history untouched |

## §4 Tripwires + decisions

One §3 carve-out lane (swing/trades, 20-A) — pass embedded, conditions verified through merge; 20-B needed NO carve-out (CLI-layer); 20-C web-only. **The SCHEMA-STOP fired correctly TWICE** (the void design + A4) and both resolved no-schema. The 6-decision plan-stage surface (D#0/A4/B2/A2/ORDER/#33) was ruled by both directors within 20 seconds of each other with zero conflicts; one ruling (D-#33) was REVISED on live-grain evidence and the revision was RIGHT (the shipped guard already handled the case by design). Zero tripwire false-negatives. One self-cert correction: the 20-A brief's A5 file list was INCOMPLETE (CHARC's cite-without-verify on `_compute_execution_price`) — caught by the plan's re-grounding, ratified as D#0.

## §5 Register motion

- **CLOSED this phase: D22 · D23 · D24 · D25** — the entire cluster born from the $10.94 badge (2026-07-10 → 2026-07-15, five days investigation-to-retirement).
- **OPENED + carried:** the 0032 taxonomy follow-up (`fills_trades_price_divergence` dedicated type, the #11 one-commit discipline — a lull item) · two V2 candidates (execution↔fill IDENTITY linking; the strict-ALL stats choke point — RD's bound-b, a NEW stats surface still needs manual helper injection until it exists).
- **UNCHANGED WATCH:** D1 · **D5 FIRES — the audit suite ran 5:14 at 9115 tests, CROSSING the 5-minute watch line for the first time; the runtime paydown is a Phase-21 headline candidate, no longer deferrable** · D8 · D9 · D12 · D15 · D16 · D17 · D11.
- **Housekeeping candidates logged:** 2 pre-existing brief-named top-level docs (`comms-stage1-…-dispatch-brief.md`, `phase19-close-housekeeping-commissioning-brief.md`) — Phase-19/comms residuals for a future sweep; the schwab-setup order-sensitive test (did NOT recur at any merged head — watch only).

## §6 CHARC self-critique (owned; all net-caught)

1. **Twice recommended dismissing the $10.94** ("not worth chasing for $11") — the operator's insistence on decomposition found systemic corruption. The size-of-residual ≠ nature-of-residual lesson is now in both directors' behavioral lists (RD's formulation: a monitor that fires gets a decomposition before it gets an explanation).
2. **Two wrong residual attributions in one thread** (OOF-P&L; open-position unrealized) — both refuted by one query each; retracted on the record before they misled.
3. **The A5 cite-without-verify** (`_compute_execution_price` attributed to the classifier off a comment) — the same class as Phase-19's C4 miss; caught at plan re-grounding.
4. The counterpart record: RD's #33 chain-grain premise-miss (his second, owned with the sharpened trace-the-key-structure lesson) and his two in-stream B3 arithmetic bugs — the peer-symmetric net at work. **Nothing wrong reached a witnessed merge in either phase this generation ran.**
5. **The instrument beat the directors:** the $10 equity_delta tolerance caught real corruption within 24h while both directors argued it was noise. The register now records the badge as vindicated; the tolerance unchanged and proven.

## §7 Carried to Phase-21 (the scope-proposal seed list)

D5 suite runtime (**CROSSED the watch line: 5:14** — likely the headline paydown) · the 0032 taxonomy type · the two V2 candidates · S4U/explicit-data-root · D15 base-VM consolidation · the 2 residual brief-named docs · D16/D17 (decide-as-reached) · RD-lane watches (floor-ratio band; the shadow-twin divergence at n-of-a-few). Weigh against RD demand at scoping; RD's posture remains STOP-ENGINEERING + MARKET TIME — H1 needs trading days, and both measurement chains are now clean.

**Phase 20 is CLOSED.**
