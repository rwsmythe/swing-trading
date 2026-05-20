# Phase 13 T2.SB1 — T-A.1.7 operator-paired exemplar bootstrap corpus

**Session date:** 2026-05-19 to 2026-05-20 (operator-paired, multi-batch).

**Corpus dump:** `pattern_exemplars_dump.jsonl` (34 rows, full table snapshot from `~/swing-data/swing.db`).

## Summary

| Class | Gold | Silver | Total |
|---|---|---|---|
| vcp | 3 | 14 (incl. relabeled-out) | 17 |
| flat_base | 1 | 2 | 3 |
| cup_with_handle | 3 | 2 (incl. relabeled-out) | 5 |
| high_tight_flag | 3 | 0 | 3 |
| double_bottom_w | 3 | 1 | 4 |
| **Total** | **13** | **21** | **34** |

13 of 25 gold target (brief target was >=5 per class × 5 classes). Deviation documented below.

## Gold rows (13)

| id | ticker | window | proposed class | source |
|---|---|---|---|---|
| 1 | SNAP | 2020-07-01 to 2020-09-30 | vcp | watch (operator-promoted) |
| 10 | AMD | 2018-06-15 to 2018-07-26 | vcp | confirmed (textbook, score 1.0) |
| 12 | TGT | 2020-05-01 to 2020-08-31 | flat_base | confirmed (score 1.0) |
| 18 | NVDA | 2017-02-01 to 2017-03-30 | vcp | watch (operator-promoted) |
| 19 | COST | 2018-12-01 to 2019-04-15 | cup_with_handle | operator-promoted over subagent rejection (rounded-vs-V gate fired by 0.4% margin) |
| 21 | MSFT | 2018-12-01 to 2019-04-30 | cup_with_handle | operator-promoted over subagent rejection (rounded-vs-V gate) |
| 23 | NFLX | 2019-09-01 to 2020-01-31 | cup_with_handle | operator-promoted over subagent rejection (descent too fast per spec) |
| 24 | BLNK | 2020-11-01 to 2021-02-01 | high_tight_flag | operator-promoted over subagent rejection (consolidation 34% pullback / 36% width) |
| 25 | NIO | 2020-07-01 to 2020-08-31 | high_tight_flag | operator-promoted over subagent rejection (pole 9 days, below 28-day floor) |
| 26 | PLTR | 2020-12-01 to 2021-02-15 | high_tight_flag | operator-promoted over subagent rejection (pole 84%, below 90%) |
| 27 | AAPL | 2020-09-01 to 2020-11-15 | double_bottom_w | confirmed (textbook W, score 0.96) |
| 28 | TWLO | 2020-09-01 to 2020-11-15 | double_bottom_w | operator-promoted over subagent rejection (trough_2 14.6% above trough_1, alignment fail) |
| 32 | CRWD | 2020-09-01 to 2020-12-15 | double_bottom_w | confirmed (textbook W, score 0.86) |

## Deviations from T-A.1.7 brief

### 1. Gold count: 13/25 (52% of target)

The brief calls for >=5 gold per class × 5 classes = >=25. Reached 13. Per-class:
- vcp: 3/5 (-2)
- flat_base: 1/5 (-4)
- cup_with_handle: 3/5 (-2)
- high_tight_flag: 3/5 (-2)
- double_bottom_w: 3/5 (-2)

All 5 classes have at least one positive exemplar, which is sufficient corpus shape for T2.SB3+/SB4 detector builds to consume as bootstrap material. The under-representation is consistent across classes; not a class-specific blocker.

### 2. Spec-criteria-strictness observation (the headline finding)

The session ran 34 dispatches across well-known retrospective pattern instances (Minervini/O'Neil/Qullamaggie canonical material). Subagent applied spec section 5.2-5.6 criteria rigorously and **rejected approximately 75% of candidates** including textbook instances like:
- COST 2018-12 cup_with_handle (rejected: rounded-vs-V hard gate fired by 0.4% margin on a 0.4% borderline)
- MSFT 2018-12 cup_with_handle (rejected: descent too V-like)
- BLNK 2020-12 parabolic HTF (rejected: 34% consolidation pullback vs spec's 25% cap)
- NIO 2020-07 parabolic HTF (rejected: 9-day pole vs spec's 28-day floor)

Operator visual override (overriding subagent rejections via web Promote button) yielded 7 of the 13 gold rows. Subagent-confirmed-and-operator-agreed yielded 4. Subagent-watch-and-operator-promoted yielded 2.

**Implication for T2.SB3+/SB4 detector phases:** spec thresholds may warrant relaxation during V1 detector calibration. Specifically:
- Cup-with-handle rounded-vs-V hard gate: 4 of 5 dispatched cups failed by sub-1% margins. Either widen the tolerance band or downgrade from hard-reject to scoring penalty.
- HTF consolidation tightness (pullback <= 25%, width <= 15%): real parabolic HTFs consistently exceed these. Possibly widen pullback to 35% / width to 25% for high-pole-magnitude cases.
- VCP monotonic-tightening: real bases sometimes break monotonicity due to news/earnings. Consider 1-violation tolerance for high-confidence other-criteria-pass cases.

These are V2/T2.SB3+/SB4 calibration questions; banked here for downstream evaluator awareness.

### 3. Subagent labeling reproducibility variance

SNAP 2020-07-01 to 2020-09-30 vcp was dispatched twice in this session (pre-hotfix abort + post-hotfix retry). Same window, same criteria, two different swing-detection outcomes:
- First dispatch: T3 = 2020-09-02 to 2020-09-04 depth 9.10% → monotonicity violated → `rejected`
- Second dispatch: T3 = 2020-09-09 to 2020-09-10 depth 4.10% → monotonicity passes → `watch`

Different swing-detection algorithm choices flip the label between rejected and watch. Worth noting for T-A.1.8 cassette-mode tests + future corpus reproducibility.

### 4. TSM window-framing inconsistency across pattern classes

TSM 2020-05-01 to 2020-08-31 was dispatched as vcp (id=29) and flat_base (id=30). VCP dispatch correctly bounded the base to pre-breakout 2020-07-23 (base_top=59.07), giving a sensible relabel-to-flat_base outcome. Flat_base dispatch failed to sub-window — took full window min/max including the 2020-07-24 breakout to 83.40, blowing the range to 68.9%. Same window, opposite framings, due to FlatBaseEvidence schema lacking explicit `base_start_date`/`base_end_date` fields like VCPEvidence has. Flagged as 5th T-A.1.6 deficiency.

## T-A.1.6 web-surface deficiencies discovered

The operator-paired session surfaced 5 deficiencies in the T-A.1.6-shipped `/patterns/exemplars` route + template:

1. **No chart rendering.** Template shows metadata only (id/ticker/window/class/decision/source). Operator cannot visually inspect the OHLCV window to make an informed promote/reject decision. Workaround: this session generated 28 PNG charts to `tmp/phase13-labeling/charts/` via a one-off mplfinance script. Permanent fix needed in T-A.1.8 or a follow-up web-refinement task.

2. **No structural_evidence_json display.** Operator cannot see the per-criterion pass/fail table the subagent produced. The reasoning the operator needs to evaluate is invisible.

3. **No geometric_evidence_narrative display.** Operator cannot read the subagent's plain-English reasoning. Both 2 and 3 are referenced in spec section 5.10 closed-loop "8-item checklist" but T-A.1.6 didn't implement them.

4. **Relabel-then-promote-to-gold path is broken.** `_apply_action.promote_to_gold` at `swing/web/routes/patterns.py:163-168` hard-codes `final_pattern_class = NULL`, overwriting any prior relabel's class. Operator who relabels a row then promotes loses the relabel decision; the gold row records the original `proposed_pattern_class` not the corrected `final_pattern_class`. No path exists in the as-built UI to promote a relabeled row to gold under its corrected class.

5. **FlatBaseEvidence schema lacks explicit base_start_date/base_end_date** (vs VCPEvidence which has them). Causes the subagent to compute range over the full window including breakouts, blowing flat_base candidates' bounded-range criterion.

## Workflow artifacts

Tmp/untracked artifacts (not committed; available for inspection during this session):
- `tmp/phase13-labeling/payload_*.json` — 34 dispatch payloads (one per attempt).
- `tmp/phase13-labeling/silver_*.json` — 34 subagent responses.
- `tmp/phase13-labeling/charts/*.png` — 34 rendered candlestick charts.
- `tmp/phase13-labeling/render_charts.py` — one-off mplfinance script.

These can be regenerated by the implementer T-A.1.8 from the `pattern_exemplars_dump.jsonl` if cassette infrastructure or visual verification is needed.

## Commit SHA + resume protocol

This README + the JSONL dump are committed to the worktree branch `phase13-t2-sb1-dev-time-labeling-infra`. Resume signal to the orchestrator session uses this commit SHA + the deviations listed above.
