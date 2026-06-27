# Phase 13 Closer — Next-Phase Triage Agenda

**Status:** **RESOLVED 2026-05-23** — operator-paired triage decision LOCKED post S2-S5 gate session + S3 sensitivity-harness output review. **Path B (Applied Research focus) LOCKED** per operator decision 2026-05-23 PM. See §"OPERATOR DECISION LOCKED" + §"Next-action sequence" below for next-phase substrate.

## Decision points

1. **Path selection per OQ-CL.2 (§1.5.2 deferred disposition):**
   - **Path A** — Phase 14 (operator-defined operational scope).
   - **Path B** — Applied Research focus per V2.1 §X tranche progression
     (first method-record selection from `research/phase-0-tasks.md`
     "Next" section, now containing the A+-like-indicators entry
     promoted at T-T4.SB.1).
   - **Path C** — Combination (Phase 14 + research-branch concurrent
     per V2.1 §V branch posture).

2. **Inputs:**
   - Operator runs `swing diagnose aplus-sensitivity --eval-runs 63`
     against own DB → reviews CSV + markdown at `exports/diagnostics/`.
   - Findings answer: "which A+ criterion thresholds, if loosened, would
     materially increase A+ pipeline volume?"
   - If concentration in 1-2 criteria → threshold-loosening cfg-policy
     proposals candidate for Phase 14 (or for a research-branch method
     record validating the loosening).
   - If distributed → broader research-branch sweep warranted.

3. **OQ-CL.3 — research-branch first-method-record selection meeting:**
   - Scheduled separately post-T4.SB-SHIPPED (operator-paired session).
   - Inputs: sensitivity-harness output + 8 candidate A+-like indicators
     in `research/phase-0-tasks.md`.

## Cross-references

- T-T4.SB.1 deliverables:
  - `research/harness/aplus_sensitivity/` (harness modules).
  - `research/studies/aplus-criterion-sensitivity-2026-05-22.md` (study writeup; findings TBD).
  - `research/method-records/aplus-criteria-calibration.md` (method record stub).
  - `exports/diagnostics/aplus-sensitivity-<ISO>.{md,csv}` (operator-run output).
- T-T4.SB.2 deliverables: metrics wiring audit live; Option 7C fix at 4 surfaces.
- T-T4.SB.3/4/5/6: see T4.SB return report at `docs/phase13-t4-sb-return-report.md`.

---

## Findings from 2026-05-23 S3 sensitivity-harness review

**Run**: operator-paired post-T4.SB-executing-plans-merge gate session 2026-05-23. Orchestrator drove `python -m swing.cli diagnose aplus-sensitivity --eval-runs 63 --output-dir exports/diagnostics`.

**Output artifacts** (retained):
- `exports/diagnostics/aplus-sensitivity-20260523T065514Z.md` (134 lines; sensitivity matrix + Notes)
- `exports/diagnostics/aplus-sensitivity-20260523T065514Z.csv` (118 rows; 9 cols including Kind taxonomy)

**Baseline distribution (5681 candidates across last 63 eval_runs)**:
- Gate-variable view: A+ = **5** / Watch = **1184** / Skip = **4492** / Excluded = 0
- Threshold-variable view: A+ = **5** / Watch = **1186** / Skip = **4277** / Excluded = **168**
- Discrepancy is a V1 harness artifact (gate-row uses live `bucket_for` recompute; threshold-row uses persisted-bucket passthrough; the two paths attribute "excluded" differently). Headline counts hold.

### Gate findings (LIVE-recompute data; 2 of 17 variables)

| Variable | Current | Sweep result | Headline |
|---|---|---|---|
| `trend_template.min_passes` | 7 | Loosening to 5/6 → **ZERO delta** on A+ and Watch. Tightening to 8 → A+ UNCHANGED at 5, Watch -87 (-7%). Tightening to 9 → A+ collapses to **0** (only 8 TT criteria exist; 9 = impossible — implicit ceiling). | TT-pass gate is **NOT binding** at the watch→A+ boundary. **Cannot increase A+ pipeline by loosening this gate.** |
| `vcp.watch_max_fails` | 2 | Sweep 0→4 produces **0 / 234 / 1184 / 2874 / 3968** Watch counts. **A+ count UNCHANGED at 5 across all sweep points.** | Pure Watch-fanout dial. **Cannot increase A+ pipeline; affects only Watch filter strictness.** |

### Threshold findings (15 of 17 variables — INERT under V1 harness per V1 LIMITATION)

All 15 threshold variables — `trend_template.rising_ma_period_days` + `trend_template.high_52w_margin_pct` + `trend_template.low_52w_min_pct` + `vcp.prior_trend_min_pct` + `vcp.adr_min_pct` + `vcp.pullback_max_pct` + `vcp.proximity_max_pct` + `vcp.tightness_days_required` + `vcp.tightness_range_factor` + `vcp.orderliness_max_bar_ratio` + `vcp.orderliness_max_range_cv` + `risk.max_risk_pct` + `rs.horizon_weeks` + `rs.rs_rank_min_pass` + `rs.fallback_extreme_pct` — report **ZERO delta** at every sweep point.

This is the V1 LIMITATION explicitly called out in the markdown's Notes section + writing-plans return report §4 item 1: the V1 harness returns `persisted_bucket` as-is without recomputing criterion outcomes against substituted thresholds. **V2 OHLCV criterion-evaluator harness** (banked at `research/method-records/aplus-criteria-calibration.md` V2 dependencies) is required to assess these 15 variables.

### Headline interpretation

Operator's motivating question per Decision Point #2: *"which A+ criterion thresholds, if loosened, would materially increase A+ pipeline volume?"*

**S3 answer**: V1 cannot answer for 15 of 17 variables. The 2 gate variables that V1 CAN assess **both demonstrate non-binding behavior at the A+ tier** — loosening neither would increase A+ pipeline volume. The 5-A+-candidates-across-63-runs constraint is therefore caused by EITHER:

1. **The 15 untested threshold criteria** — V2 OHLCV harness needed to identify which one(s) are binding.
2. **Market conditions** (no qualifying setups in the universe regardless of threshold).
3. **Other gates not enumerated as `kind=gate`** in V1 (e.g., `risk_feasibility` hard pre-filter, Stage-2 trend status that isn't part of TT8-count).

**This is a strong signal**: the easily-tunable gate parameters are NOT the bottleneck. The high-leverage tuning work requires V2 OHLCV harness FIRST.

---

## Orchestrator recommendation (2026-05-23)

| Path | Expected A+ volume impact | Rationale |
|---|---|---|
| **A — Phase 14 operational** | **None** (A+ pipeline unchanged) | Engineering on operational features (Schwab API extension, entry/exit polish) — does not address the operator's mission-critical A+ pipeline volume concern surfaced at T4.SB Item 1 |
| **B — Applied Research focus** | **HIGH** (after V2 OHLCV harness ships) | V2 OHLCV criterion-evaluator unblocks 15 threshold variables. Then threshold-loosening method-records evidence-based. The S3 output explicitly identifies V2 as the unblock. Aligned with V2.1 §IV.D + §VII.C lifecycle posture (method-records validate threshold proposals BEFORE cfg-policy changes) |
| **C — Combination** | Medium-HIGH | Path A + Path B concurrent per V2.1 §V branch posture; engineering-rich but pragmatic if bandwidth allows |

**Orchestrator recommended Path B**, anchored on building the V2 OHLCV criterion-evaluator harness as the first method-record under `research/method-records/aplus-criteria-calibration.md`. Rationale:
1. The S3 output explicitly demonstrates the V1 limitation; the 5-A+-candidate constraint cannot be resolved via tunable gates that V1 surfaces.
2. V2 OHLCV criterion-evaluator harness is the unblock for 15 threshold variables — without it, no threshold-loosening proposal can be evidence-based.
3. Building V2 in `research/` branch keeps production code stable (V2.1 §V branch posture).
4. Once V2 OHLCV harness ships + threshold-loosening method-records evaluated, a downstream Phase 14 can ship the cfg-policy-update path with high confidence.

**Side-effect gate findings** (low-leverage but operator-aware-disposition items):
- `vcp.watch_max_fails`: current 2 produces 1184 Watch; tightening to **1** drops Watch to **234** (-80%) if operator wants tighter watch filtering. Pure Watch-quality dial; no A+ impact.
- `trend_template.min_passes`: tightening to **8** trims 87 Watch (-7%); A+ preserved at 5. Cosmetic quality tradeoff.

---

## OPERATOR DECISION LOCKED 2026-05-23 PM

Per operator-paired triage session 2026-05-23 PM via AskUserQuestion:

1. **Triage path**: **Path B — Applied Research focus (V2 OHLCV harness first)** LOCKED. V2 OHLCV criterion-evaluator harness becomes the first method-record under `research/method-records/aplus-criteria-calibration.md`.
2. **Side-effect gate adjustments**: **NONE** — operator chose to leave both gates at current values. Rationale: defer the Watch-filter tightening decision until V2 OHLCV harness output gives full context on which variables actually constrain A+ volume.
3. **Triage agenda artifact update**: shipped THIS commit per operator decision.

**OQ-CL.2 disposition**: RESOLVED. Path B selected. Phase 14 commissioning DEFERRED until V2 Applied Research outputs (first method-record + at least one threshold-loosening evaluation) inform the operational scope.

**OQ-CL.3 disposition** (research-branch first-method-record selection): RESOLVED in-line with Path B. The first method-record is the V2 OHLCV criterion-evaluator harness build itself (anchoring the `aplus-criteria-calibration` lineage). No separate operator-paired selection meeting needed; subsequent method-records will follow per V2.1 §IV.D lifecycle.

---

## Next-action sequence (Path B execution)

Forward-binding for the next orchestrator session OR fresh dispatch:

1. **Brainstorm V2 OHLCV criterion-evaluator harness spec** at `research/method-records/aplus-criteria-calibration.md` (extend stub) + new spec doc at `docs/superpowers/specs/<date>-v2-ohlcv-criterion-evaluator-design.md` (or operator-paired naming). Scope per writing-plans return report §4 item 1 V2 dependency: harness consumes original OHLCV bars at `candidate.data_asof_date` + substitutes per-criterion thresholds + recomputes `bucket_for` end-to-end. Per V2.1 §IV.B minimum viable method-record field list.
2. **Establish research-branch dispatch workflow** mirroring `research/harness/earnings_proximity/` precedent: harness module + study writeup + method-record with `status='research'`. V2.1 §IV.D + §VII.C lifecycle posture.
3. **Inputs for V2 harness**:
   - 15 inert threshold variables from S3 (enumerated above)
   - OHLCV archive validity at historical `data_asof_date` (also banked as V2 dependency at writing-plans return report §4 item 9)
   - `bucket_for` full implementation at `swing/evaluation/scoring.py`
   - Operator DB candidate_criteria + candidates universe (5681 candidates across 63 eval_runs)
4. **Discriminating-test pattern**: plant synthetic candidate with known criterion-margin-of-failure at a specific threshold; sweep threshold across the failure boundary; assert bucket flips per substituted threshold.
5. **Expected first study output**: which of the 15 threshold variables (if any) are binding at the watch→A+ promotion boundary, ranked by marginal A+ count per loosening unit.
6. **Downstream**: if a binding threshold(s) identified, draft cfg-policy method-record + operator-paired threshold-loosening evaluation against retained validation universe. THEN consider Phase 14 commissioning for the cfg-policy-update path.

**Side-effect gate disposition deferred**: re-evaluate `vcp.watch_max_fails` + `trend_template.min_passes` tightening AFTER V2 OHLCV harness output gives full context (so adjustments can be made in concert with threshold-loosening proposals rather than in isolation).
