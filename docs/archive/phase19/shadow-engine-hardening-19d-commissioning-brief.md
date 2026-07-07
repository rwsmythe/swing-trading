# Commissioning Brief — 19-D: shadow-engine hardening (risk-unit floor + epsilon-tolerant reader + capture-timing trace)

**From:** CHARC. **To:** the Phase-19 orchestrator. **Arc:** 19-D ([`phase19-scope-charc.md`](phase19-scope-charc.md), scope AMENDED 2026-07-04 — operator-approved three-part bundle). **Committed:** 2026-07-04 HST.
**§3 verdict:** SUB-TRIPWIRE (all changes in `research/harness/shadow_expectancy/` — NO `swing/` file, NO schema [v31], NO new module under `swing/`, NO dependency, NO standing process, NO carve-out). **BUT measurement-chain → RD authority is BINDING: RD plan-stage review RULES the semantic design choices (floor form + epsilon threshold); RD merge-blocking QA; RD's pre-committed T4 confirmatory re-read is the terminal measurement gate.** The engine is PURE RECOMPUTE (read-only conn, zero DB writes, fresh timestamped artifact per run) → every fix is retroactive-by-re-run; no backfill, reversible by construction.

## §0 References

- **RD threads:** `shadow-engine-risk-unit-artifact` (2026-06-30, the VSTS +27.3R flag) · the T4 evidence mail (2026-07-03: `entry_bar_ambiguous` degenerate 165/165; open-mark artifacts PGNY +18.9R / DFTX +13.5R / LTH +10.5R; TVTX +7.84R = tight-but-REAL) · the invalid_ohlc adjudication (2026-07-04: 16 ragged-SHAPE bars / 12 tickers, magnitudes 0.04–0.77% + CALY 1.66%; 38/353 = 10.8% attrition and growing; ZERO duplicates, ZERO post-baseline non-finite) · the cross-vendor observation (2026-07-04 stage-a witness: run-123 `schwab_api_calls` shows 2 Schwab-side pricehistory OHLC-consistency rejections).
- **Artifacts:** `exports/research/shadow-expectancy-20260630T010654Z` (VSTS A+ +27.333R, results.csv + summary.md) · the T4 study `research/studies/2026-07-03-broad-watch-baseline-t4-decision-read.md` (frozen 0026 criteria; PROVISIONAL-NEGATIVE banked).
- **Code (CHARC-traced on disk 2026-07-04):** `simulator.py:97-107` (`entry_fill = max(pivot, entry_bar.open)`; `initial_stop = entry_bar.low`; `rps = entry_fill − initial_stop`; the guard `if entry_fill <= initial_stop` = a ZERO-floor; `ambiguous = entry_bar.low < entry_fill`) · `validate.py:32-48` (`validate_bars`: `low > min(o,c)` / `high < max(o,c)` → `invalid_ohlc`; one bad bar excludes the WHOLE signal) · `run.py:176-190` (the degenerate/exclusion emit path) · `constants.py:41-47` (the exclusion-reason taxonomy) · `io.py` (the bar-read boundary — the reader-clamp locus, exact seam pinned at writing-plans).

## §1 The three verified mechanisms

1. **Risk-unit collapse:** the `degenerate_risk` guard floors rps at ZERO, not at meaningfulness. A breakout whose entry bar closes near its low yields rps → $0.03–0.04 (VSTS: 0.25% of price, ~0.07× ATR) → a normal +7.9% move prices as +27.3R and DRIVES the A+ per-signal expectancy (n=1 → 13.667). The `entry_bar_ambiguous` flag cannot gate it — it is true by construction on ~every daily bar (165/165). All `horizon_mtm` inflated; the realized broad-watch cohort clean so far; a LATENT T4 hazard as opens close.
2. **Ragged-shape attrition:** `validate_bars` excludes the whole signal on one sub-cent/cent-level shape violation anywhere in the forward walk. 38/353 (10.8%) of signals already lost; the inflow accrues (6-bar burst 07-01) — a slow leak in exactly the N the H1/T4 program needs. The immutable log is CORRECT to record the source verbatim; the excess is in the READ-side all-or-nothing.
3. **Capture-timing (hypothesis, unproven):** the inflow may correlate with same-evening capture before provider consolidation completes (the AMN volume revision 426k→622k; the 07-01 burst). Now also a cross-vendor family (the Schwab-side rejections).

## §2 Requirements (the plan PROPOSES with evidence; RD RULES the semantics)

1. **(a) Risk-unit floor / discriminator.** Replace the zero-floor with a MEANINGFUL bound. Design space (RD's options — pick ONE primary + rationale): a minimum rps as % of entry price · an ATR-fraction floor · a risk-unit-to-ATR ratio discriminator · cap/winsorize per-signal R. **The binding distinction test (RD's own): VSTS (0.25% price, ~0.07× ATR) must be caught; TVTX (+7.84R at 1.4% risk) is tight-but-REAL and must SURVIVE with its R unchanged.** Propose the threshold from the LIVE artifact distribution, not intuition. Exclusion-vs-winsorize semantics (excluded as `degenerate_risk` vs floored denominator) = RD's ruling at plan review. Prefer the EXISTING taxonomy reasons; a new reason string only if RD blesses.
2. **(b) Epsilon-tolerant reader.** At the bar-READ boundary (before `validate_bars`): when a shape violation is ≤ a small % threshold, clamp `high = max(h,o,c)`, `low = min(l,o,c)`; ABOVE threshold → `invalid_ohlc` exactly as today. **The immutable log + OHLCV archive stay VERBATIM — reader-side ONLY** (the raw-log principle; RD's ruling). Threshold proposed from the live distribution (0.04–0.77% cluster, 1.66% outlier); RD rules where it sits and whether CALY-class outliers stay excluded. **Observability: emit a clamped-bar counter (+ per-ticker sample) in the artifact summary/manifest** so RD can watch the inflow without re-probing the DB.
3. **(c) Capture-timing trace (analysis, no production code).** Correlate the 38 violations' bar-dates against capture/write timing; fold in the Schwab-side rejections (run-123 audit rows). Findings = a short trace note posted with the return (informs 19-C's schedule rationale and whether later capture shrinks the inflow). If the data cannot discriminate, say so plainly — do not force a conclusion.

## §3 Locks

Pure-recompute preserved EXACTLY (read-only `io.open_ro` conn; zero INSERT/UPDATE; fresh timestamped `exports/research/shadow-expectancy-<ts>/` artifact). NO write-side/archive mutation anywhere. The 0026 frozen T4 criteria untouched. The funnel/attribution/partial (PARTIAL_SESSION_N=3) semantics untouched except where the floor lands by design. NO `swing/` edits (the 18-A/18-B archive-boundary semantics are OUT of scope — the reader clamp is engine-internal). R values CHANGE by design — that is the point; comparability is re-established by the full-corpus re-run + RD's re-read, never by patching history.

## §4 Discriminating tests (fixtures from REAL emitter data — binding)

Fixtures MUST derive from the REAL live shapes (the `feedback_adversarial_review_verify_data_shapes` mandate: Codex verifies the load-bearing data claims against the live DB/artifacts; never values built to satisfy the premise): the actual VSTS 06-25 signal geometry, the actual TVTX geometry, real ragged bars (DINO/CALY class) lifted from the live archive.

- **T1 (VSTS-class collapse):** pre-fix +27.333R; post-fix caught by the floor (excluded or winsorized per RD's ruling). Compute BOTH paths (`feedback_regression_test_arithmetic`).
- **T2 (TVTX-class tight-but-real):** R UNCHANGED pre→post. The over-eager-floor lock.
- **T3 (normal-stop signal):** R IDENTICAL pre→post — the fix must not move ordinary signals.
- **T4 (sub-threshold ragged bar in the walk):** pre-fix whole-signal `invalid_ohlc`; post-fix clamped + the signal RECOVERED with a sane R.
- **T5 (above-threshold violation, CALY-class):** still `invalid_ohlc` under BOTH paths — the clamp-everything lock.
- **T6:** the clamped-bar counter appears in the artifact with the right count.

## §5 Gates

1. **RD plan-stage review — RULES the design** (floor form + value, epsilon threshold, exclusion-vs-winsorize, outlier posture). Post the plan pointer to rd after your own plan QA; operator resolves.
2. review-strong to convergence + codex-auto-review (measurement-chain production code).
3. Fast suite + ruff + merged-head no-false-green.
4. **Post-merge measurement gate:** a fresh full-corpus engine run (turnkey) → artifact sanity (VSTS heals to a sane R; `invalid_ohlc` excluded count drops ~38 → the above-threshold residue; recovered signals enter the cohorts) → **RD's pre-committed T4 confirmatory re-read** = the binding close. No operator GUI witness (research lane); operator authorizes the merge.
5. The ORCHESTRATOR posts the return report to `charc,rd` AFTER its QA; the implementer never posts to directors.

## §6 Sizing + dispatch recommendation

Small-medium code, HIGH semantic density (the floor/threshold design is measurement policy). CHARC recommendation: **writing-plans `implementer-opus-xhigh`** (the semantic design + live-distribution evidence work), **executing `implementer-opus-high`** (locked plan; retroactive-by-re-run = reversible, so not `-max`). Orchestrator owns the final cell selection + announces before spawn.
