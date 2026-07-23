# RD — Current State (single source of truth)

> **OVERWRITE this file each session/handoff — do NOT append.** This is the one always-current state pointer for the RD (Research Director / CIO) role. The dated session log in [`docs/research-director-context.md`](research-director-context.md) §7 is APPEND-ONLY history; current state lives HERE only. Bootstrap reads this file FIRST. Convention: [`docs/harness-architecture.md`](harness-architecture.md) §6.

---

**Last overwritten:** 2026-07-23 (session resume; all numbers below FRESHLY QUERIED this date — glance + monitor + live DB). **Phases 19 AND 20 are CLOSED** (audits clean at `0d560822` / `e3b6570f`); main HEAD `b25ab488`, 65 ahead of origin (local-first; operator pushes, do NOT push); schema **v31** (two consecutive zero-migration phases); ~9115 fast green.

**Program state:** **T4 = CONFIRMED-NEGATIVE, FINAL — A+ gate selectivity validation BANKED** (study + §8: `research/studies/2026-07-03-broad-watch-baseline-t4-decision-read.md`; its 4 cited artifacts are git-tracked under the study's `artifacts/` per watch-standard **v2.1** cite=commit). Both measurement chains have now been forensically hardened and witnessed: the RESEARCH chain in Phase 19 (shadow-engine risk-unit floor + epsilon clamp; my T4 confirmatory re-read discharged it) and the TRADING LEDGER in Phase 20 (the D25 tier-1-corrector corruption — 3 fills + a phantom trade — fixed, corrected, RD-witnessed to the cent, and proven live against its own causal geometry by run 78). **Posture: STOP-ENGINEERING + MARKET TIME.**

## Live state (fresh 2026-07-23)
- **Research health: ALL SEVEN CHECKS GREEN** — the first fully-green monitor read in program history. Notably **`invalid_ohlc` is back to EXACTLY baseline 23** (was 38 / +15 pre-19-D): the epsilon reader-clamp closed the ~11% signal-attrition leak completely. **That watch item is RESOLVED.**
- **Drumbeat healthy + unattended:** 650 unique signals (545 → 650 over 8 days), `total_unattributed = 0` throughout, newest artifact 0 days old. The 19-C weeknight scheduler has fired every weekday unattended (runs 135–138+, all `trigger='scheduled'`) — **the scheduled-path confirmation I owed as a glance item is SATISFIED.**
- **H1 = 2/20 closed** (both `standard`, both now `reviewed`): VSTS +$1.80 (+0.05R) · AMN +$1.17 (the D25-corrected true value). Shadow A+ closed n=1 (AMN twin 0.0R).
- **A+ supply = 4 signals ever:** NVCR 06-18 (untriggered) · VSTS 06-25 · AMN 07-01 · **FTRE 2026-07-20 — NOT taken live (see Pending).**
- **VSTS did NOT re-qualify A+** — still `watch`, pivot has risen 15.06 → 16.90, price ~15.90 (it ran ~11% without re-entering the gate). The `tightness`-only miss continues.

## Open watch items
- **Broad-watch closed cohort has grown 100 → 267 signals and the mean R has drifted −0.637 → −0.224** (still negative; the banked verdict's DIRECTION holds). The magnitude softening as N grows is a real observation to examine at read #2 — NOT grounds to reopen a frozen criterion, and the positive branch is untriggered (mean is still < 0).
- **PGNY-class floor-boundary marks** (risk/ADR ratio 0.15–0.2 band still amplifies): revisit ONLY on realized evidence, no ad-hoc re-tune.
- **T9 pattern-count gate**: needs a deliberate operationalization (matured-forward-walk reading vs raw counts) at a future read.
- **Shadow-twin divergence** (live day-3 partial vs engine day-4 fire point): n=1, revisit only if it systematically biases live-vs-shadow at scale.
- **Banked semantics:** `equity_delta_dollars` stores the RAW OOF-INCLUSIVE gap — never read it without OOF-netting (the badge/emit path nets).

## Pending RD
- **T5 QUESTION OWED TO THE OPERATOR: FTRE (A+ 2026-07-20) was not taken.** Per T5 each A+ fire is precious to a starved H1 — ask the intent story (correctly skipped for extension/capital/away-from-screen, or a missed fire?). Verify before labeling; then be direct.
- **CATCH-UP DISCIPLINE TRIGGERED** (watch-standard §1): 20 days since the last logged read (#1, 07-03) exceeds the ~2-week bar, so a §3 checklist run is owed by any RD instance spun up in between. Monthly read **#2 is due first trading week of August** (~9 days out) — operator sequences: run the catch-up now, or fold it into read #2.
- Phase-21 scoping comes via the fresh CHARC generation (D5 suite-runtime = likely headline; my riders: the 0032 taxonomy type, the two V2 candidates — execution↔fill identity + the bound-b stats choke point).
- A+ spot-check cadence continues to N=10 priced (currently 2 priced).

## Behavioral load-bearing (pointers into the charter)
- Blunt over sycophantic; evidence before assertion (every number freshly queried — never carried forward). Verify intent before labeling a mistake, then be direct.
- **Adjudicate residuals by DECOMPOSITION, never prior plausibility** — D25's headline: the $10 equity_delta instrument caught a real corruption BOTH directors nearly dismissed as deposit drift. A monitor that fires gets a decomposition before it gets an explanation.
- QA the DIVERGENCE, never defend the brief — **including my own rulings** (Option-C; the #33 stamp withdrawal). **Trace the neighboring system / the key structure before ruling on a mechanism** (the pruner miss; the per-discrepancy chain-grain miss).
- Weight REALIZED (closed-only) over marks in every expectancy read; when primary scenarios disagree in sign, the pre-committed realized read binds (T4 precedent).
- Run `role_mail` posts with a `cd <main-repo> &&` prefix in the SAME command — never trust a prior cd (2 misdelivery instances banked).
- Briefs crossing a CHARC §3 tripwire route through CHARC pre-dispatch; RD is merge-blocking on measurement integrity; deviations from stop-engineering need written justification.
