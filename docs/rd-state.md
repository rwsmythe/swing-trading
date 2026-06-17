# RD — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** This is the one always-current state pointer for the RD (Research Director / CIO) role. The dated session log in [`docs/research-director-context.md`](research-director-context.md) §7 is APPEND-ONLY history; current state lives HERE only. Bootstrap reads this file FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

---

**Last overwritten:** 2026-06-17 (first real overwrite — replaced the CHARC FORM scaffold). **Program state:** the 2026-06-13 data-collection audit chain is CLOSED + automated (18-A/B/C/D/B.1 + nightly half + 2 calibrations); watch-standard **v2** adopted 2026-06-16; posture = **STOP-ENGINEERING + market time** (the measurement chain is live + autonomous). **main HEAD = `78d6d5e6`** (my SPCX brief commit, on top of orchestrator `516c24f3`); **schema v31**; ~8618 fast green; trailers `[]`. Local-only commits — main is ahead of origin (operator push cadence; do not push).

## Live workstreams / arcs in flight
- **SPCX out-of-framework holding carve-out — PATH B (ignore-entirely).** Operator bought 2 SPCX IPO shares (~$412) outside the framework to hold long-term; 18-H.6/.6.1 made it a per-run `untracked_broker_position` orphan. Operator chose B 2026-06-17. **Brief committed `78d6d5e6`** (`docs/out-of-framework-holding-carveout-commissioning-brief.md`); **posted to CHARC + operator** (thread `spcx-out-of-framework-carveout`, `20260617T093619Z`) requesting the architecture pass. **Status: awaiting CHARC architecture pass** → then operator sequences the orchestrator writing-plans dispatch. **RD merge-blocking on locks L1–L4** (zero contamination by construction / no false equity signal / explicit-auditable-never-blanket carve-out / measurement chain untouched). Carve-out is at the recon boundary (orphan pass `schwab_reconciliation.py:1304-1367` + optional both-flat coherence refinement); it never enters the `trades` table.

## Pending RD decisions (operator-sequenced)
- None owed by RD right now. Ball is with **CHARC** (SPCX architecture pass: registry mechanism, equity-coherence refinement now-vs-defer, existing-orphan-row disposition), then **operator** (dispatch sequencing). RD acts again at the writing-plans QA + executing merge-block sign-off.

## Closed recently
- The full 2026-06-13 audit chain (18-A writer fix → 18-B consolidation → 18-C yfinance observability → 18-D monitor + FIX-1 baseline → 18-B.1 structural prevention → nightly step + calibrations A/B). Watch-standard **v2** authored + operator-adopted. All RD-lane Phase-18 audit work is done.

## Watch-standard / tripwire status (T1–T7) — as of 2026-06-17 glance
- **All clear.** Drumbeat alive (run `20260617T070016Z`, artifact age 0d); unattributed **0** across all 7 shown runs (no T2); accrual healthy (51→114 signals). No new live trades this week — epoch intact (no T5/T6/T7). `invalid_ohlc=23` stable (baselined 06-10 cohort; not a #2 regression).
- **The glance's lone `ATTENTION` is the known T3 heuristic re-fire** (it trips on any nonzero trigger rate). **T3 is CLOSED** (golden gate + 2 hand-walks, 06-13; N past 10). Not actionable.
- **Broad-watch priced N ≈ 26 triggered signals** (run `20260617T070016Z`) — numerically approaching the **T4 N≥30** gate (was 10 on 06-13). **BUT zero realized edge:** closed-only **0/7 wins, −0.714R**; the +0.382R `mtm_at_horizon` headline is entirely UNREALIZED marks on 19 open positions; 14/26 triggered are weak-close intraday-touch entries; signal-count overstates evidence (correlated re-detections, ~handful of unique names). Meaningless at this N by design; floors suppress correctly. **At the T4 read, weight closed-only realized — not the blended open-mark number.**
- **First monthly read due: first trading week of July 2026.** T4 (N≥30) is the binding next event; T9 (log N≥100) and T10 (2026-12) pending.

## Behavioral load-bearing (pointers into the charter)
- Blunt over sycophantic; evidence before assertion (every number freshly queried from the live DB / artifacts — never carried forward). Verify intent before labeling a mistake, then be direct.
- QA the DIVERGENCE, never defend the brief (directive #10). Verify the actual code/UI surface before operational guidance (directive #9) — ground claims in `file:line`, not architecture-from-memory.
- Commissioning briefs crossing a CHARC §3 tripwire (new schema / module / dependency / standing process / `swing/{trades,data}` carve-out) route through CHARC pre-dispatch (`harness-architecture.md` §5). RD is merge-blocking on measurement integrity; CHARC challenges measurement locks through the operator, not by override.
- Default posture: STOP-ENGINEERING + market time. Deviations need written justification (the SPCX carve-out is justified as instrument-integrity, not research).
