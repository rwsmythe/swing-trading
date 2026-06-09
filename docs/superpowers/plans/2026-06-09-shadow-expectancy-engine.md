# Shadow-Expectancy Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only research harness that mechanically forward-walks every emitted temporal-log signal through one fixed management ruleset to a realized R-multiple, accumulating per-hypothesis expectancy evidence at signal-pace, surfaced via one new `swing diagnose shadow-expectancy` CLI subcommand.

**Architecture:** Thin Approach-A modules under `research/harness/shadow_expectancy/` mirroring the `minervini_primary_base_recall` precedent exactly: a read-only consumer of the frozen v22 temporal log (`pattern_detection_events` + `pattern_forward_observations`) joined to per-run `candidates` rows, with hypothesis attribution via `swing.recommendations.hypothesis.match_candidate_to_hypotheses`, a NEW bar-by-bar multi-leg management simulator, a two-level denominator funnel, a per-hypothesis four-scenario scorecard, and a per-run artifact writer (results/per_session CSV + summary.md + manifest.json) with an ASCII guard. The only `swing/` change is the CLI registration (L2 LOCK stays light). No production schema change (v24 holds); no production write path.

**Tech Stack:** python 3.14, sqlite3 (read-only URI), pandas (none required — pure dict bars), click (CLI), pytest (TDD). Reuses pure-leaf production functions: `swing.trades.derived_metrics` (R math), `swing.metrics.honesty.wilson_ci` (Wilson CI), `swing.recommendations.hypothesis` (attribution), `swing.data.repos.{pattern_detection_events,pattern_forward_observations,candidates,hypothesis,pipeline}` (read-only).

---

## Spec ambiguities resolved (READ FIRST — these are the load-bearing interpretation calls)

The design spec (`docs/superpowers/specs/2026-06-08-shadow-expectancy-engine-design.md`) is authoritative for *what*; the recon below resolves *how* against real signatures. Each call is flagged for adversarial scrutiny.

1. **The candidate join key is NOT a direct `(pipeline_run_id, ticker)` column on `candidates`.** Spec §4/§6 describes the join as "`(pipeline_run_id, ticker)`", but `candidates` is keyed by `evaluation_run_id` (migration 0001), NOT `pipeline_run_id`. The production detect step (`swing/pipeline/runner.py:_step_pattern_detect`, lines 1462-1547) writes `pattern_detection_events.pipeline_run_id = lease.run_id` AND fetches candidates via `fetch_candidates_for_run(conn, eval_run_id)`; the two are tied together by `set_evaluation_run_id(conn, pipeline_run_id=..., evaluation_run_id=...)` (`swing/data/repos/pipeline.py:210`) which stamps `pipeline_runs.evaluation_run_id` (column added migration 0006). **Resolution:** the harness join path is `detection.pipeline_run_id` → `pipeline_runs.id` → read `pipeline_runs.evaluation_run_id` → `candidates WHERE evaluation_run_id = ? AND ticker = ?`. A detection whose `pipeline_run_id` is NULL, or whose `pipeline_runs` row is missing / has NULL `evaluation_run_id`, or whose `(evaluation_run_id, ticker)` has no candidate row → funnel reason `no_candidate_join` (`unattributed` bucket). `candidates` carries `UNIQUE(evaluation_run_id, ticker)` (migration 0001:41), satisfying spec §6's uniqueness assertion — the harness still asserts ≤1 row defensively.

2. **Advisory predicates (`suggest_breakeven` / `suggest_trail_ma` / `suggest_exit_close_below_ma` / `suggest_maturity_stage_trail_ma_hint`) are NOT pure float-leaf decision functions.** They take a production `Trade` dataclass + `AdvisoryContext` and EMIT advisory MESSAGE strings via `r_so_far(trade, current_price)`; they answer "should I show the operator a hint?", not "what management action does the simulator take?" (`swing/trades/advisory.py`). The pure leaf they all sit on is `swing.trades.equity.r_so_far(trade, current_price)` + `risk_per_share(trade)`. **Resolution:** the simulator reuses the *thresholds and the R-math* — `r_so_far`'s formula `(price - entry) / (entry - stop)`, `derived_metrics.initial_risk_per_share`, `breakeven_r_trigger=1.0` default (`StopAdvisoryConfig`, `swing/config.py:92`), the maturity 10/20 staging from `advisory._MATURITY_STAGE_TRAIL_MA` semantics (≥+2R → 10MA, else 20MA) — but implements the management *decisions* directly in `simulator.py` as a pure state machine, because the advisory functions are message-emitters coupled to the `Trade` model and the DB-backed `AdvisoryContext`. The plan adds `attribution.py`/`simulator.py` unit tests asserting the simulator's breakeven trigger and maturity MA-period selection match the advisory thresholds (anti-drift), so the reuse is *of the doctrine constants*, not the message functions. **This is the single largest deviation from a literal reading of the spec's reuse-matrix and §5.4/§5.5 "reuse `suggest_*`"; flagged prominently for Codex.**

3. **R-math reuse with FRACTIONAL shares + the FIXED multi-leg denominator (Codex C2).** `derived_metrics.realized_pnl` / `r_multiple` accept `quantity: float` (no integer assumption — `swing/trades/derived_metrics.py:16,26`), so the spec's "fractional, exact" `initial_shares=100.0` units flow through unchanged. The MECHANICAL initial stop is `entry_bar.low` (spec §5.2/D6), so `rps = initial_risk_per_share(entry_price=entry_fill, initial_stop=entry_bar.low) = entry_fill - entry_bar.low` (can be ≤0 only when `entry_bar.low == entry_bar.open` and `pivot <= open`; the harness gates `degenerate_risk` on `entry_fill <= entry_bar.low` BEFORE calling `r_multiple`). **Multi-leg R uses ONE FIXED denominator, NOT per-leg denominators (spec §5.8):** `total_R = (Σ over legs of realized_pnl(entry_price=entry_fill, exit_price=leg_exit, quantity=leg_qty)) / (rps * initial_shares)` — implemented as Σ per-leg `realized_pnl`, then a SINGLE `r_multiple(realized_pnl=total_pnl, initial_risk_per_share=rps, quantity=initial_shares)`. Summing `r_multiple(...quantity=leg_qty)` per leg would divide each leg by its OWN denominator and double-count (a 50%@+1.2R + 50%@+2.0R exit would wrongly total 3.2R instead of the correct 1.6R). `r_multiple` raises `ValueError` when `rps*initial_shares == 0` — the harness never reaches it for excluded `degenerate_risk` trades.

4. **Output directory.** Spec §7 suggests `research/studies/shadow-expectancy-runs/<run-id>/`, but every harness precedent + the `.gitignore` allowlist uses `exports/research/<slug>-<ISO>/`. **Resolution:** write to `exports/research/shadow-expectancy-<ISO>/` (CLI `--output-dir` default `exports/research`), matching the precedent and the gitignore-allowlist convention; add the `.gitignore` negation block in the output task. The study/method-record docs live under `research/studies/` + `research/method-records/` (unchanged convention).

5. **Wilson CI source.** Spec §6.1/§7.2 says reuse `swing/metrics/`. `swing.metrics.honesty.wilson_ci(k, n)` is DB-free importable (verified) and returns `WilsonCI(point, lower, upper)`. The `minervini_*` precedent instead defines a local `wilson_interval`. **Resolution:** reuse `swing.metrics.honesty.wilson_ci` directly (it is a pure leaf), honoring the spec's "reuse `swing/metrics/`" literally, and add it to the L2-lock `_EVALUATOR_MODULES` import-safety test. Sample-floor suppression uses a harness-local integer floor constant (NOT `suppress_for_n`, which requires a DB-backed `RiskPolicy`); profit-factor/expectancy below the floor emit the spec §7.2 suppression annotation.

6. **Entry bar identification.** The entry session is the canonical detection's FIRST `pattern_forward_observations` row with `status == 'triggered_open'` AND `status_change_event == 'entry_fired'` (the production observe step stamps `entry_fired` exactly once on the breakout bar — `runner.py:_advance_status:2570`; subsequent triggered bars carry `status_change_event = None`). The entry-bar OHLC is that row's `ohlc_today_json`. Forward bars for management are the observations STRICTLY AFTER the entry session (`observation_date > entry.observation_date`), ordered ascending. This satisfies spec §5.1's "strictly after `detection_date`" no-look-ahead because the production observe step only emits `triggered_open` on sessions with `data_asof_date < observation_date`.

7. **`ohlc_today_json` shape is `{open,high,low,close,volume,provider}`** (lowercase keys; `swing/pipeline/temporal_metadata.py:146` `_OHLC_TODAY_KEYS`). The simulator/validator read these exact keys. `provider ∈ {schwab_api, yfinance}`; the harness ignores `provider` for math.

---

## Reuse-target signatures that DIFFER from a naive spec reading (flag for QA)

- **`fetch_candidates_for_run(conn, run_id)`** takes an `evaluation_runs.id`, NOT a `pipeline_run_id` (see ambiguity #1). Returns `list[Candidate]`. The harness MUST resolve `eval_run_id` from `pipeline_runs` first.
- **`match_candidate_to_hypotheses`** is keyword-only for `registry` and `doctrine_defensible_set`: `match_candidate_to_hypotheses(candidate, *, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET, registry)`. `registry` is `Iterable[HypothesisRegistryEntry]`; only `status=='active'` entries match. Read the active registry via `swing.data.repos.hypothesis.list_hypotheses(conn, status_filter='active')`.
- **Detection pivot lives in `structural_anchors_json` → `json.loads(...)['evidence']['pivot_price']`** (a string column; `runner.py:_advance_status:2532`), NOT a top-level `pivot` column on the detection. The candidate pivot is `candidate.pivot` (nullable float). The canonical-detection match (§6) compares these two at normalized tick precision.
- **Advisory predicates are message-emitters, not decision leaves** (ambiguity #2).
- **No direct temporal-log "reader for the trade path" exists beyond the repos.** `get_observations_for_detection(conn, detection_id)` returns the full ASC chain; that is the bar source. `list_detection_events(conn, source='pipeline', ...)` enumerates detections.

---

## Implementation substrate (exact signatures / paths / line numbers)

**Harness precedent (mirror):** `research/harness/minervini_primary_base_recall/` — `run.py` (CLI `main()` argparse + `run_harness(...) -> (results, per_session, summary, manifest)` paths), `output.py` (`_assert_ascii`, `_write_csv`, `write_results_csv`, `write_per_session_csv`, `write_summary_md`, `write_manifest_json` — JSON `sort_keys=True`, `l2_lock_preserved` default True), `constants.py`, `exceptions.py`, `scorecard.py`, empty `__init__.py`. Tests: `tests/research/minervini_primary_base_recall/` — `test_l2_lock.py` (HARDENED `monkeypatch.delitem/setitem` sys.modules pattern; `_FORBIDDEN`, `_EVALUATOR_MODULES`, source-grep banned-import test), `test_cli.py` (CliRunner `--help` registration + ValueError→ClickException + PowerShell ASCII subprocess), `test_run.py`, `test_study_doc.py`.

**Temporal log (read-only):**
- `swing/data/migrations/0022_phase14_temporal_log.sql` — `pattern_detection_events(detection_id PK, ticker, detection_date, data_asof_date, pattern_class, structural_anchors_json, composite_score, detector_version, finviz_screen_state, source, per_pattern_metadata_json, pipeline_run_id→pipeline_runs(id), chart_render_id, created_at)`; `pattern_forward_observations(observation_id PK, detection_id→pattern_detection_events, observation_date, ohlc_today_json, status CHECK∈{pending,triggered_open,triggered_closed_at_target,triggered_closed_at_stop,invalidated,expired}, status_change_event, sessions_since_detection, created_at, UNIQUE(detection_id, observation_date))`.
- `swing/data/repos/pattern_detection_events.py`: `list_detection_events(conn, *, ticker=None, pattern_class=None, source=None, pipeline_run_id=None, limit=None, offset=0) -> list[PatternDetectionEvent]`; `get_detection_event_by_id(conn, detection_id)`.
- `swing/data/repos/pattern_forward_observations.py`: `get_observations_for_detection(conn, detection_id) -> list[PatternForwardObservation]` (ASC by date).
- Models `swing/data/models.py`: `PatternDetectionEvent` (line 2052; fields above), `PatternForwardObservation` (line 2088: `observation_id, detection_id, observation_date, ohlc_today_json, status, sessions_since_detection, created_at, status_change_event=None`).
- `ohlc_today_json` keys = `("open","high","low","close","volume","provider")`, `provider∈{"schwab_api","yfinance"}` (`swing/pipeline/temporal_metadata.py:145-146`).
- Trigger semantics: `swing/pipeline/runner.py:_advance_status:2522-2573` — `triggered_open` + `status_change_event='entry_fired'` on `bar["high"] >= pivot`; pivot from `json.loads(det.structural_anchors_json)['evidence']['pivot_price']`.

**Candidates (read-only):** `swing/data/repos/candidates.py:fetch_candidates_for_run(conn, run_id) -> list[Candidate]` (run_id = evaluation_runs.id). `candidates` schema migration 0001:24-42 (`UNIQUE(evaluation_run_id, ticker)`); columns `bucket, close, pivot, initial_stop, adr_pct, ..., rs_method, pattern_tag, sector, industry` + `candidate_criteria(criterion_name, layer, result, value, rule)`. Model `Candidate` (models.py:135: `ticker, bucket, close, pivot, initial_stop, adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method, pattern_tag, notes, criteria: tuple[CriterionResult,...], sector="", industry=""`); `CriterionResult` (models.py:127: `criterion_name, layer, result∈{pass,fail,na}, value=None, rule=None`).

**Pipeline→eval-run linkage:** `pipeline_runs.evaluation_run_id` (migration 0006:18, nullable FK→evaluation_runs); `swing/data/repos/pipeline.py:set_evaluation_run_id` is the writer (read it directly via SQL in the harness: `SELECT evaluation_run_id FROM pipeline_runs WHERE id=?`).

**Hypothesis attribution:** `swing/recommendations/hypothesis.py:match_candidate_to_hypotheses(candidate, *, doctrine_defensible_set=DOCTRINE_DEFENSIBLE_MISS_SET, registry) -> list[HypothesisMatch]`; `HypothesisMatch(hypothesis_id, hypothesis_name, suggested_label_descriptive, priority_hint, candidate_ticker)`; constants `H_APLUS_BASELINE="A+ baseline"`, `H_NEAR_APLUS_EXTENSION`, `H_SUB_APLUS_VCP`, `H_CAPITAL_BLOCKED`; `DOCTRINE_DEFENSIBLE_MISS_SET=frozenset({"TT8_rs_rank","risk_feasibility","proximity_20ma"})`. Registry reader `swing/data/repos/hypothesis.py:list_hypotheses(conn, *, status_filter=None)`; model `HypothesisRegistryEntry` (models.py:498: `id, name, statement, target_sample_size, decision_criteria, status, consecutive_loss_tripwire, absolute_loss_tripwire_pct, created_at, ...`).

**R-math:** `swing/trades/derived_metrics.py` — `initial_risk_per_share(*, entry_price, initial_stop) -> float`; `realized_pnl(*, entry_price, exit_price, quantity) -> float`; `r_multiple(*, realized_pnl, initial_risk_per_share, quantity) -> float` (raises ValueError when `rps*qty==0`). `swing/trades/equity.py:r_so_far(trade, current_price)` formula `(price-entry)/(entry-stop)` (reference for the simulator's running-R).

**Advisory thresholds (constants reused, not the functions):** `swing/config.py:StopAdvisoryConfig` (line 91: `breakeven_r_trigger=1.0`, `trail_10ma_buffer_pct=0.3`, `trail_20ma_buffer_pct=0.3`). `swing/trades/advisory.py:_MATURITY_STAGE_TRAIL_MA` (≥+2R→10MA else 20MA semantics), `suggest_breakeven` (R≥trigger AND stop<entry → raise to entry), `suggest_exit_close_below_ma` (close<MA → exit).

**Metrics:** `swing/metrics/honesty.py:wilson_ci(*, k, n, alpha=0.05) -> WilsonCI(point, lower, upper)` (DB-free, pure). Harness-local sample-floor constant for profit-factor/expectancy suppression.

**DB connect (read-only):** precedent `research/harness/pattern_cohort_evaluator/run.py:119-121` — `sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)`. CLI registration precedent `swing/cli.py:diagnose_group` (line 4761), `_validate_diagnose_db_path` (4766), `diagnose_minervini_recall` (4897), `diagnose_pattern_cohort_detect` (4966, the `--db` precedent).

**Test DB schema:** `from swing.data.db import run_migrations; run_migrations(conn, target_version=24, backup_dir=tmp_path)` then `conn.execute("PRAGMA foreign_keys=ON")` (`tests/data/repos/test_pattern_detection_events_repo.py:18-23`).

**Baseline:** ~7376 fast tests collected on `main` (2026-06-09). Trust live pytest output; do not hardcode counts in assertions.

---

## File Structure / File Map

### Created — `research/harness/shadow_expectancy/`
- `__init__.py` — empty package marker (mirrors precedent).
- `constants.py` — harness-tunable defaults: `INITIAL_SHARES=100.0`, `PARTIAL_SESSION_N=3`, `PARTIAL_PCT=0.5`, `BREAKEVEN_R_TRIGGER=1.0`, `MATURITY_FAST_MA_R=2.0`, `MA_FAST_PERIOD=10`, `MA_SLOW_PERIOD=20`, `HORIZON_SESSIONS=126`, `SOURCE="pipeline"`, `SAMPLE_FLOOR_MEAN=5`, `SAMPLE_FLOOR_RATE=5`, `PROFIT_FACTOR_FLOOR=5`, `PRICE_TICK_DECIMALS=4`. Plus funnel-reason + exit-reason string tuples.
- `exceptions.py` — `ShadowExpectancyError(Exception)` base + `InvalidLogStructureError`.
- `io.py` — read-only temporal-log + candidate reader/joiner: `open_ro(db_path)`, `read_signals(conn, *, source) -> list[RawSignal]` (enumerate detections, collapse to unique `(pipeline_run_id, ticker)`, attach observation chains), `resolve_candidate(conn, pipeline_run_id, ticker) -> Candidate | None` (via `pipeline_runs.evaluation_run_id` → `fetch_candidates_for_run`), `parse_bar(ohlc_today_json) -> Bar`.
- `collapse.py` — canonical-detection collapse + consistency gates (§6): `collapse_detections(detections_for_run_ticker, candidate_pivot) -> CollapseResult` (the group = ALL detections sharing `(pipeline_run_id, ticker)`; canonical = the detection whose `pivot==candidate.pivot` tick-normalized, tie-broken by lowest `detection_id`; the consistency gates run over the WHOLE group, not just the pivot-matching subset — ANY divergence in the frozen forward-OHLC series → `inconsistent_detection_series`, ANY divergence in the first `triggered_open` session → `inconsistent_trigger_state`; `collapsed_ids` = ALL non-canonical detection ids in the group, so `collapsed_duplicate == group_size - 1`), `normalize_tick(price)`.
- `validate.py` — §5.0.1 input validation: `validate_signal(*, pivot, initial_stop, bars) -> str | None` (returns the funnel reason `invalid_ohlc` or None — `degenerate_risk` is decided inside the simulator off `entry_bar.low`, NOT here; the candidate-level `pivot`/`initial_stop` sanity checks per spec §5.0.1 are validated here but the trade stop is derived from `entry_bar.low`, NOT `candidate.initial_stop` — see C1).
- `attribution.py` — matcher glue: `attribute_hypotheses(candidate, *, registry) -> list[str]` (hypothesis names; an empty list routes to the `matched_no_hypothesis` reason and a >1-element list routes to the `multi_match` reason [R3-M1] — both WITHIN the `unattributed` bucket [C-review M1], decided by `run.py`; all other pre-/non-attribution `unattributed` reasons also resolve at funnel level), thin wrapper over `match_candidate_to_hypotheses`. The wrapper itself returns the raw name list; the zero-/multi-match bucketing decisions live in `run.py`.
- `bracket.py` — the `[realistic, favorable_reprice]` exit-fill model (§5.6/§5.8): `price_stop_fill(arm, *, stop, bar_open)`, `ma_exit_fill(arm, *, signal_close, next_open)`.
- `simulator.py` — the NEW bar-by-bar multi-leg state machine (§5.0-§5.8): `simulate(*, pivot, entry_bar, forward_bars, params) -> SimResult` (the MECHANICAL initial stop is `entry_bar.low` per D6/§5.2 — NOT passed from the candidate; `risk_per_share = entry_fill - entry_bar.low`; `degenerate_risk` gate = `entry_fill <= entry_bar.low`; emits legs, exit_reason, open_at_horizon, ambiguous flag, per-arm realized R on a FIXED `rps*initial_shares` denominator, four censoring scenarios).
- `scorecard.py` — per-hypothesis aggregation (§7.2): `build_hypothesis_scorecard(trades, *, sample_floor_mean, sample_floor_rate, profit_factor_floor) -> dict` (FOUR scenario means per arm, each computed over ALL triggered trades [closed contributes its realized R in all four; open contributes scenario-specific, excluded only in closed-only]; the headline = realistic-arm closed-only; trigger rate, per-signal expectancy, win rate + Wilson, avg win/loss R, payoff, profit factor [suppressed below floor], median holding, same-bar-adverse sensitivity). Reuses `swing.metrics.honesty.wilson_ci`.
- `funnel.py` — two-level denominator funnel (§7.1): `build_funnel(detection_level, *, signal_outcomes) -> Funnel` (detection→collapsed→unique; signal→joinable→triggered→{closed,open}→excluded-with-reasons; ONE `unattributed` bucket holding all PRE-/NON-attribution states as per-reason counters: `no_candidate_join`, `matched_no_hypothesis` [joined candidate attributes to zero hypotheses], `multi_match` [joined candidate matches >1 hypothesis — defensive, excluded so it is never double-counted; R3-M1], `no_canonical_detection` [candidate present but no detection pivot matches it; C-review M4], `inconsistent_detection_series`, `inconsistent_trigger_state` [caught before the matcher]. `matched_no_hypothesis` and `multi_match` are REASONS WITHIN `unattributed`, NOT separate top-level buckets [C-review M1 / R3-M1]. `build_funnel` RAISES `ShadowExpectancyError` on a `hypothesis is None` outcome lacking a valid `UNATTRIBUTED_REASONS` reason [m1 — no silent `no_candidate_join` default]. POST-attribution per-hypothesis exclusions [`invalid_ohlc`, `degenerate_risk`] land in each matched hypothesis's `excluded[...]`, never `unattributed`. The per-reason breakdown is surfaced in `summary.md` [M2], not just the manifest.
- `output.py` — writers + ASCII guard: `write_results_csv`, `write_per_session_csv` (ledger legs), `write_summary_md`, `write_manifest_json`; `_assert_ascii`. Mirrors precedent.
- `run.py` — orchestrator + `main()` argparse entry: `run_harness(*, db_path, output_dir, source, partial_session_n, breakeven_r, horizon_sessions, only) -> (results, per_session, summary, manifest)`.

### Modified — `swing/`
- `swing/cli.py` — register `@diagnose_group.command("shadow-expectancy")` (the ONLY swing/ change; deferred import of `run_harness`).
- `.gitignore` — add the `exports/research/shadow-expectancy-*` artifact allowlist block (summary.md + manifest.json + results.csv + per_session.csv tracked).

### Created — `tests/research/shadow_expectancy/`
- `__init__.py`
- `test_l2_lock.py` — HARDENED sys.modules import-safety + source-grep banned-import (forbidden: yfinance, schwabdev, swing.integrations.schwab, swing.data.ohlcv_archive).
- `test_io.py` — reader/joiner: detection enumeration, eval-run resolution, candidate join, `no_candidate_join`, bar parse.
- `test_collapse.py` — canonical-detection collapse + `inconsistent_detection_series`/`inconsistent_trigger_state` + tick-normalized pivot match.
- `test_validate.py` — §5.0.1 candidate-sanity (`pivot`/`initial_stop`) + bar-OHLC `invalid_ohlc` checks ONLY. (`degenerate_risk` is decided in the SIMULATOR off `entry_bar.low`, not `validate.py` — see `test_simulator.py`, golden walk (f); m2.)
- `test_attribution.py` — A+→H1, watch∩proximity→H2, etc.; empty match (the caller buckets it `matched_no_hypothesis`).
- `test_bracket.py` — favorable ≥ realistic per arm on a fixed denominator.
- `test_simulator.py` — §5.0 precedence + entry + stop + `degenerate_risk` (entry_fill ≤ entry_bar.low; m2) + partial + breakeven + maturity-staged MA trail + exits + censoring + golden walks (a)-(g).
- `test_scorecard.py` — four-scenario expectancy, trigger rate, per-signal vs triggered, Wilson, profit-factor suppression, same-bar-adverse.
- `test_funnel.py` — two-level reconciliation, one terminal bucket per signal, reasons recorded.
- `test_run.py` — end-to-end over a synthetic in-memory temporal-log DB; reproducibility (identical canonical manifest across re-runs).
- `test_cli.py` — CliRunner `--help` registration + ValueError→ClickException + PowerShell ASCII subprocess.
- `test_study_doc.py` — study + method-record doc presence with required sections (mirrors precedent).

### Created — docs
- `research/studies/2026-06-09-shadow-expectancy-engine.md`
- `research/method-records/shadow-expectancy-engine.md`

---

## Task sequencing

Each task is self-contained and independently testable. TDD throughout: failing test → see fail → minimal real implementation → see pass → commit. Run `python -m pytest -m "not slow" -q` is NOT required per-task (slow); per-task run the targeted file. Run the full fast suite at the final task. Conventional commits; NO Claude co-author footer; NO `--no-verify`; NO amend; branch `main`.

---

### Task 1: Package scaffold + constants + exceptions

**Files:**
- Create `research/harness/shadow_expectancy/__init__.py`
- Create `research/harness/shadow_expectancy/constants.py`
- Create `research/harness/shadow_expectancy/exceptions.py`
- Test `tests/research/shadow_expectancy/__init__.py`, `tests/research/shadow_expectancy/test_constants.py`

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_constants.py`:
```python
from __future__ import annotations

from research.harness.shadow_expectancy import constants as C


def test_simulator_defaults_match_doctrine_constants():
    assert C.INITIAL_SHARES == 100.0
    assert C.PARTIAL_SESSION_N == 3
    assert C.PARTIAL_PCT == 0.5
    assert C.BREAKEVEN_R_TRIGGER == 1.0  # mirrors StopAdvisoryConfig.breakeven_r_trigger
    assert C.MATURITY_FAST_MA_R == 2.0   # >=+2R -> 10MA per _MATURITY_STAGE_TRAIL_MA
    assert (C.MA_FAST_PERIOD, C.MA_SLOW_PERIOD) == (10, 20)
    assert C.HORIZON_SESSIONS == 126
    assert C.SOURCE == "pipeline"


def test_breakeven_trigger_is_NOT_drifted_from_production():
    # Codex M4: a REAL anti-drift binding -- import the production config so a doctrine
    # change to breakeven_r_trigger breaks this harness test (not a hardcoded mirror).
    from swing.config import StopAdvisoryConfig
    assert C.BREAKEVEN_R_TRIGGER == StopAdvisoryConfig().breakeven_r_trigger


def test_maturity_ma_staging_is_NOT_drifted_from_production():
    # Codex M4: bind the harness 10/20 + >=+2R staging to the production
    # advisory._MATURITY_STAGE_TRAIL_MA dict. The pre-maturity stages map to "20MA"
    # (= MA_SLOW_PERIOD), the >=+2R-eligible stage maps to "10MA" (= MA_FAST_PERIOD).
    # A doctrine change to the staging dict breaks this test.
    from swing.trades.advisory import _MATURITY_STAGE_TRAIL_MA
    assert _MATURITY_STAGE_TRAIL_MA[">=+2R_trail_eligible"] == f"{C.MA_FAST_PERIOD}MA"
    assert _MATURITY_STAGE_TRAIL_MA["pre_+1.5R"] == f"{C.MA_SLOW_PERIOD}MA"
    assert _MATURITY_STAGE_TRAIL_MA["+1.5R_to_+2R"] == f"{C.MA_SLOW_PERIOD}MA"


def test_reason_vocabularies_are_frozen_tuples():
    assert "no_candidate_join" in C.FUNNEL_REASONS
    assert "invalid_ohlc" in C.FUNNEL_REASONS
    assert "degenerate_risk" in C.FUNNEL_REASONS
    assert "inconsistent_detection_series" in C.FUNNEL_REASONS
    assert "inconsistent_trigger_state" in C.FUNNEL_REASONS
    assert "never_triggered" in C.FUNNEL_REASONS
    assert "matched_no_hypothesis" in C.FUNNEL_REASONS  # C-review M1: a reason WITHIN unattributed
    assert "no_canonical_detection" in C.FUNNEL_REASONS  # C-review M4: candidate present, no pivot match
    assert "multi_match" in C.FUNNEL_REASONS             # R3-M1: defensive >1-hypothesis guard
    # The unattributed bucket's six PRE-/NON-attribution reasons (spec 7.1; C-review M1/M4 +
    # R3-M1 multi_match -- a signal matching >1 hypothesis is excluded here, NOT counted in
    # each, so the reconciliation invariant stays exact).
    assert set(C.UNATTRIBUTED_REASONS) == {
        "no_candidate_join", "matched_no_hypothesis", "no_canonical_detection",
        "multi_match", "inconsistent_detection_series", "inconsistent_trigger_state",
    }
    # writing-plans R5: post-attribution `excluded` reasons, DISJOINT from the unattributed set.
    assert set(C.ATTRIBUTED_EXCLUDED_REASONS) == {
        "invalid_ohlc", "degenerate_risk", "insufficient_forward_depth",
        "missing_observations", "lifecycle",
    }
    assert set(C.ATTRIBUTED_EXCLUDED_REASONS).isdisjoint(set(C.UNATTRIBUTED_REASONS))
    assert set(C.EXIT_REASONS) == {
        "initial_stop", "breakeven_stop", "ma_close_below",
        "horizon_mtm", "never_triggered", "degenerate_risk",
    }
    assert set(C.BRACKET_ARMS) == {"realistic", "favorable_reprice"}
    assert set(C.CENSORING_SCENARIOS) == {
        "closed_only", "mtm_at_horizon", "forced_exit_at_horizon_open",
        "stop_level_adverse",
    }
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_constants.py -q`. Expected: `ModuleNotFoundError: No module named 'research.harness.shadow_expectancy'`.

- [ ] **Step: minimal implementation** —
  - `research/harness/shadow_expectancy/__init__.py`: empty file.
  - `tests/research/shadow_expectancy/__init__.py`: empty file.
  - `research/harness/shadow_expectancy/exceptions.py`:
```python
from __future__ import annotations


class ShadowExpectancyError(Exception):
    """Base class for all shadow_expectancy harness errors."""


class InvalidLogStructureError(ShadowExpectancyError):
    """The temporal log violated a structural invariant the harness relies on."""
```
  - `research/harness/shadow_expectancy/constants.py`:
```python
from __future__ import annotations

# --- Simulator unit-of-analysis defaults (spec D1-D12) ---
INITIAL_SHARES = 100.0          # nominal fractional entry unit (D2/5.1)
PARTIAL_SESSION_N = 3           # Day-3 partial (D4/5.3); session-N configurable
PARTIAL_PCT = 0.5               # sell 50% of initial_shares (D4)
BREAKEVEN_R_TRIGGER = 1.0       # mirrors swing.config.StopAdvisoryConfig.breakeven_r_trigger (5.4)
MATURITY_FAST_MA_R = 2.0        # >=+2R -> 10MA per advisory._MATURITY_STAGE_TRAIL_MA (D12/5.5)
MA_FAST_PERIOD = 10             # maturity-staged 10/20 proxy (D12)
MA_SLOW_PERIOD = 20
HORIZON_SESSIONS = 126          # ~6 months (D5); bounded by available bars
SOURCE = "pipeline"            # temporal-log detection source filter (6: A+ isolation)
PRICE_TICK_DECIMALS = 4         # normalized pivot-match precision (6, Codex R5-m1)

# --- Honesty / suppression sample floors (7.2) ---
SAMPLE_FLOOR_MEAN = 5           # mean-R suppression floor
SAMPLE_FLOOR_RATE = 5           # win-rate Wilson floor (still reported, annotated)
PROFIT_FACTOR_FLOOR = 5         # profit-factor suppressed below this n

# --- Funnel reason vocabulary (7.1) ---
FUNNEL_REASONS = (
    "no_candidate_join", "matched_no_hypothesis", "multi_match",
    "no_canonical_detection", "invalid_ohlc", "inconsistent_detection_series",
    "inconsistent_trigger_state", "degenerate_risk", "insufficient_forward_depth",
    "missing_observations", "lifecycle", "never_triggered",
)
# Reasons reported WITHIN the unattributed bucket (PRE-/NON-attribution states only;
# Codex R4-m1 + C-review M1/M2/M4 + R3-M1, spec 7.1). Under the join -> attribute ->
# validate -> simulate order, the unattributed states are the JOIN/COLLAPSE-stage ones
# below PLUS matched_no_hypothesis (candidate joined + valid but matched ZERO hypotheses)
# PLUS multi_match (candidate matched >1 hypothesis). All six are REASONS within the
# single `unattributed` bucket -- each reported with its own counter in the reason
# breakdown; there is NO separate top-level matched_no_hypothesis / multi_match bucket
# (C-review M1). matched_no_hypothesis is DISTINCT from no_candidate_join (candidate row
# missing) and from no_canonical_detection (candidate present but no detection pivot
# matches it -- a collapse/substrate-integrity fault; C-review M4). multi_match (R3-M1)
# is a DEFENSIVE reason: the 4 seeded hypotheses are mutually exclusive by their
# exact-miss-set definitions, so it should be ~0 today, but excluding a >1-match signal
# here (rather than emitting one outcome PER matched hypothesis) keeps the reconciliation
# invariant -- Sum(unattributed reason counts) + Sum(per-hypothesis terminal-status
# counts) == unique_signals -- exact for a future non-exclusive hypothesis.
# Validation/simulation failures on an ATTRIBUTED (exactly-one-match) signal (invalid_ohlc
# / degenerate_risk) are caught AFTER attribution and reported PER-HYPOTHESIS in that
# hypothesis's excluded[...], NOT unattributed (spec 7.1).
UNATTRIBUTED_REASONS = (
    "no_candidate_join", "matched_no_hypothesis", "multi_match",
    "no_canonical_detection", "inconsistent_detection_series",
    "inconsistent_trigger_state",
)
# writing-plans R5: the ONLY reasons a POST-attribution (per-hypothesis) `excluded` terminal may
# carry. DISJOINT from UNATTRIBUTED_REASONS by construction, so an unattributed-only reason can
# never be silently miscounted under a hypothesis (build_funnel rejects it).
ATTRIBUTED_EXCLUDED_REASONS = (
    "invalid_ohlc", "degenerate_risk", "insufficient_forward_depth",
    "missing_observations", "lifecycle",
)

EXIT_REASONS = (
    "initial_stop", "breakeven_stop", "ma_close_below",
    "horizon_mtm", "never_triggered", "degenerate_risk",
)
BRACKET_ARMS = ("realistic", "favorable_reprice")
CENSORING_SCENARIOS = (
    "closed_only", "mtm_at_horizon", "forced_exit_at_horizon_open",
    "stop_level_adverse",
)
HARNESS_VERSION = "0.1.0"
```

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_constants.py -q`. Expect 4 passed (the four test functions in this file).

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/__init__.py research/harness/shadow_expectancy/constants.py research/harness/shadow_expectancy/exceptions.py tests/research/shadow_expectancy/__init__.py tests/research/shadow_expectancy/test_constants.py && git commit -m "feat(research): shadow-expectancy harness scaffold + constants/exceptions"`

---

### Task 2: Bar dataclass + `ohlc_today_json` parser + input validation (§5.0.1)

**Files:**
- Create `research/harness/shadow_expectancy/validate.py`
- Modify `research/harness/shadow_expectancy/io.py` (create `Bar` + `parse_bar`)
- Test `tests/research/shadow_expectancy/test_validate.py`

**C1 note:** `validate_candidate_levels(pivot, initial_stop)` validates `candidate.pivot`/`candidate.initial_stop` for SANITY only (finite, pivot>0, initial_stop>=0, pivot>initial_stop). The candidate's `initial_stop` is NOT the mechanical trade stop — per spec §5.2/D6 the simulator derives the trade stop from `entry_bar.low` (see Task 7). This validator only screens out structurally-broken candidate rows; `degenerate_risk` is decided in the simulator off `entry_bar.low`, not here.

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_validate.py`:
```python
from __future__ import annotations

import json
import math

import pytest

from research.harness.shadow_expectancy.io import Bar, parse_bar
from research.harness.shadow_expectancy.validate import (
    validate_bars,
    validate_candidate_levels,
    validate_signal,
)


def _ohlc(o, h, l, c, v=1000.0, provider="yfinance"):
    return json.dumps({"open": o, "high": h, "low": l, "close": c,
                       "volume": v, "provider": provider})


def test_parse_bar_reads_lowercase_keys():
    b = parse_bar(_ohlc(10.0, 11.0, 9.5, 10.5), session="2026-05-29")
    assert (b.open, b.high, b.low, b.close, b.session) == (10.0, 11.0, 9.5, 10.5, "2026-05-29")


def test_candidate_levels_ok():
    assert validate_candidate_levels(pivot=10.0, initial_stop=9.0) is None


@pytest.mark.parametrize("pivot,stop", [
    (0.0, -1.0), (-5.0, -6.0), (float("nan"), 1.0), (10.0, 10.0), (9.0, 10.0),
])
def test_candidate_levels_reject(pivot, stop):
    assert validate_candidate_levels(pivot=pivot, initial_stop=stop) == "invalid_ohlc"


def test_bars_reject_high_lt_low():
    bars = [Bar("2026-05-29", 10.0, 9.0, 11.0, 9.5)]  # high < low
    assert validate_bars(bars) == "invalid_ohlc"


def test_bars_reject_nan_and_negative():
    assert validate_bars([Bar("2026-05-29", 10.0, 11.0, -1.0, 10.5)]) == "invalid_ohlc"
    assert validate_bars([Bar("2026-05-29", 10.0, float("inf"), 9.0, 10.5)]) == "invalid_ohlc"


def test_bars_reject_non_chronological_and_duplicate():
    a = Bar("2026-05-30", 10.0, 11.0, 9.5, 10.5)
    b = Bar("2026-05-29", 10.0, 11.0, 9.5, 10.5)
    assert validate_bars([a, b]) == "invalid_ohlc"
    assert validate_bars([b, b]) == "invalid_ohlc"


def test_validate_signal_chains_levels_then_bars():
    good = [Bar("2026-05-29", 10.0, 11.0, 9.5, 10.5)]
    assert validate_signal(pivot=10.0, initial_stop=9.0, bars=good) is None
    assert validate_signal(pivot=10.0, initial_stop=10.0, bars=good) == "invalid_ohlc"
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_validate.py -q`. Expected: `ModuleNotFoundError: No module named 'research.harness.shadow_expectancy.io'`.

- [ ] **Step: minimal implementation** —
  - `research/harness/shadow_expectancy/io.py` (create with `Bar` + `parse_bar` only; reader added Task 3):
```python
from __future__ import annotations

import json
from dataclasses import dataclass

_OHLC_KEYS = ("open", "high", "low", "close", "volume", "provider")


@dataclass(frozen=True)
class Bar:
    session: str   # ISO observation_date
    open: float
    high: float
    low: float
    close: float


def parse_bar(ohlc_today_json: str, *, session: str) -> Bar:
    d = json.loads(ohlc_today_json)
    missing = [k for k in _OHLC_KEYS if k not in d]
    if missing:
        raise KeyError(f"ohlc_today_json missing keys: {missing}")
    return Bar(
        session=session,
        open=float(d["open"]), high=float(d["high"]),
        low=float(d["low"]), close=float(d["close"]),
    )
```
  - `research/harness/shadow_expectancy/validate.py`:
```python
from __future__ import annotations

import math
from collections.abc import Sequence

from research.harness.shadow_expectancy.io import Bar

_REASON = "invalid_ohlc"


def _finite_nonneg(*vals: float) -> bool:
    return all(math.isfinite(v) and v >= 0 for v in vals)


def validate_candidate_levels(*, pivot, initial_stop) -> str | None:
    """spec 5.0.1: pivot/initial_stop finite, pivot > 0, initial_stop >= 0,
    pivot > initial_stop. Any failure -> 'invalid_ohlc'."""
    if pivot is None or initial_stop is None:
        return _REASON
    if not (math.isfinite(pivot) and math.isfinite(initial_stop)):
        return _REASON
    if pivot <= 0 or initial_stop < 0 or pivot <= initial_stop:
        return _REASON
    return None


def validate_bars(bars: Sequence[Bar]) -> str | None:
    """spec 5.0.1: every bar OHLC finite + non-negative; low <= min(open,close);
    high >= max(open,close); high >= low; strictly chronological, no dup sessions."""
    prev_session: str | None = None
    for b in bars:
        if not _finite_nonneg(b.open, b.high, b.low, b.close):
            return _REASON
        if b.low > min(b.open, b.close):
            return _REASON
        if b.high < max(b.open, b.close):
            return _REASON
        if b.high < b.low:
            return _REASON
        if prev_session is not None and b.session <= prev_session:
            return _REASON  # non-chronological OR duplicate session
        prev_session = b.session
    return None


def validate_signal(*, pivot, initial_stop, bars: Sequence[Bar]) -> str | None:
    reason = validate_candidate_levels(pivot=pivot, initial_stop=initial_stop)
    if reason is not None:
        return reason
    return validate_bars(bars)
```

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_validate.py -q`. Expect all passed.

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/io.py research/harness/shadow_expectancy/validate.py tests/research/shadow_expectancy/test_validate.py && git commit -m "feat(research): shadow-expectancy Bar parser + 5.0.1 input validation (invalid_ohlc)"`

---

### Task 3: Temporal-log reader + candidate joiner (`io.py`)

**Files:**
- Modify `research/harness/shadow_expectancy/io.py`
- Test `tests/research/shadow_expectancy/test_io.py`

Note: `RawSignal` collapse to canonical detection happens in Task 4; Task 3 reads per-detection observation chains and resolves the candidate join.

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_io.py`:
```python
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from research.harness.shadow_expectancy import io
from tests.research.shadow_expectancy.testkit import (  # built in this task
    insert_candidate, insert_detection, insert_observation, insert_pipeline_run, make_db,
)


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    return make_db(tmp_path)


def test_resolve_candidate_joins_via_pipeline_evaluation_run(conn):
    eval_id = insert_candidate(conn, ticker="AAA", bucket="aplus", pivot=10.0,
                               initial_stop=9.0)
    pr_id = insert_pipeline_run(conn, eval_id)  # testkit INSERTS the pipeline_runs row
    cand = io.resolve_candidate(conn, pipeline_run_id=pr_id, ticker="AAA")
    assert cand is not None and cand.bucket == "aplus" and cand.pivot == 10.0


def test_resolve_candidate_missing_returns_none(conn):
    assert io.resolve_candidate(conn, pipeline_run_id=999, ticker="ZZZ") is None


def test_read_observation_chain_returns_bars_with_status(conn):
    eval_id = insert_candidate(conn, ticker="AAA", bucket="aplus", pivot=10.0, initial_stop=9.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker="AAA", pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-05-29", o=9, h=9.8, l=8.9, c=9.5,
                       status="pending")
    insert_observation(conn, det_id, "2026-06-01", o=9.6, h=10.2, l=9.5, c=10.1,
                       status="triggered_open", event="entry_fired")
    chain = io.read_observation_chain(conn, det_id)
    assert [o.observation_date for o in chain] == ["2026-05-29", "2026-06-01"]
    assert chain[1].status == "triggered_open" and chain[1].status_change_event == "entry_fired"
```

A `testkit` helper module is needed by several test files; build it here in `tests/research/shadow_expectancy/testkit.py` with real schema inserts.

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_io.py -q`. Expected: `ModuleNotFoundError: No module named 'research.harness.shadow_expectancy.testkit'` (or `AttributeError: resolve_candidate`).

- [ ] **Step: minimal implementation** —
  - Append to `research/harness/shadow_expectancy/io.py`:
```python
import sqlite3

from swing.data.models import Candidate
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.pattern_detection_events import list_detection_events
from swing.data.repos.pattern_forward_observations import (
    get_observations_for_detection,
)


def open_ro(db_path) -> sqlite3.Connection:
    """Read-only connection (mode=ro URI) -- harness never writes (L2-light)."""
    from pathlib import Path

    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _eval_run_for_pipeline(conn, pipeline_run_id) -> int | None:
    row = conn.execute(
        "SELECT evaluation_run_id FROM pipeline_runs WHERE id = ?",
        (pipeline_run_id,),
    ).fetchone()
    return int(row[0]) if row is not None and row[0] is not None else None


def resolve_candidate(conn, *, pipeline_run_id, ticker) -> Candidate | None:
    """Join detection -> pipeline_runs.evaluation_run_id -> candidates (ticker).

    NOTE (spec ambiguity #1): candidates are keyed by evaluation_run_id, NOT
    pipeline_run_id; pipeline_runs.evaluation_run_id bridges them.
    """
    if pipeline_run_id is None:
        return None
    eval_run_id = _eval_run_for_pipeline(conn, pipeline_run_id)
    if eval_run_id is None:
        return None
    cands = [c for c in fetch_candidates_for_run(conn, eval_run_id) if c.ticker == ticker]
    if not cands:
        return None
    if len(cands) > 1:  # candidates has UNIQUE(evaluation_run_id, ticker); defensive
        cands.sort(key=lambda c: c.ticker)
    return cands[0]


def read_observation_chain(conn, detection_id):
    """The full ASC forward-observation chain (one row per session)."""
    return get_observations_for_detection(conn, detection_id)


def list_pipeline_detections(conn, *, source):
    """All detections for a temporal-log source, oldest-first deterministic."""
    events = list_detection_events(conn, source=source)
    return sorted(events, key=lambda d: (d.pipeline_run_id or -1, d.ticker, d.detection_id))
```
  - `tests/research/shadow_expectancy/testkit.py` — real-schema inserts (used by io/run tests):
```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from swing.data.db import run_migrations


def make_db(tmp_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp_path / "t.db")
    c.execute("PRAGMA foreign_keys=ON")
    run_migrations(c, target_version=24, backup_dir=tmp_path)
    return c


def insert_candidate(conn, *, ticker, bucket, pivot, initial_stop, close=None,
                     criteria=()):
    cur = conn.execute(
        "INSERT INTO evaluation_runs (run_ts, data_asof_date, action_session_date,"
        " finviz_csv_path, tickers_evaluated, aplus_count, watch_count, skip_count,"
        " excluded_count, error_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("2026-05-29T00:00:00Z", "2026-05-28", "2026-05-29", None, 1, 1, 0, 0, 0, 0),
    )
    eval_id = int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, pivot,"
        " initial_stop, rs_method) VALUES (?,?,?,?,?,?,?)",
        (eval_id, ticker, bucket, close, pivot, initial_stop, "fallback_spy"),
    )
    cid = int(cur.lastrowid)
    for name, layer, result in criteria:
        conn.execute(
            "INSERT INTO candidate_criteria (candidate_id, criterion_name, layer,"
            " result) VALUES (?,?,?,?)",
            (cid, name, layer, result),
        )
    conn.commit()
    return eval_id


def insert_pipeline_run(conn, eval_run_id, *, state="complete"):
    """INSERT a pipeline_runs row bound to eval_run_id; return its id."""
    cur = conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date,"
        " action_session_date, state, lease_token, evaluation_run_id)"
        " VALUES (?,?,?,?,?,?,?)",
        ("2026-05-29T00:00:00Z", "manual", "2026-05-28", "2026-05-29", state,
         f"tok-{eval_run_id}", eval_run_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_detection(conn, *, ticker, pipeline_run_id, pivot, data_asof_date,
                     detection_date, pattern_class="vcp", structural_low=None):
    evidence = {"pivot_price": pivot}
    if structural_low is not None:
        evidence["structural_low"] = structural_low
    anchors = json.dumps({"window": {}, "evidence": evidence})
    cur = conn.execute(
        "INSERT INTO pattern_detection_events (ticker, detection_date, data_asof_date,"
        " pattern_class, structural_anchors_json, composite_score, detector_version,"
        " source, per_pattern_metadata_json, pipeline_run_id, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (ticker, detection_date, data_asof_date, pattern_class, anchors, 0.7,
         "vcp_v1", "pipeline", "{}", pipeline_run_id, "2026-05-29T00:00:00Z"),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_observation(conn, detection_id, observation_date, *, o, h, l, c,
                       status, event=None, sessions_since=0, v=1000.0,
                       provider="yfinance"):
    ohlc = json.dumps({"open": o, "high": h, "low": l, "close": c, "volume": v,
                       "provider": provider})
    conn.execute(
        "INSERT INTO pattern_forward_observations (detection_id, observation_date,"
        " ohlc_today_json, status, status_change_event, sessions_since_detection,"
        " created_at) VALUES (?,?,?,?,?,?,?)",
        (detection_id, observation_date, ohlc, status, event, sessions_since,
         "2026-05-29T00:00:00Z"),
    )
    conn.commit()


# Re-export the eval->pipeline helper under the io module's name for the test.
```
  The `testkit.insert_pipeline_run(conn, eval_id)` helper (above) INSERTS the `pipeline_runs` row + returns its id; `io.resolve_candidate` then READS the join. The two responsibilities are kept in separate modules/names (testkit inserts; io reads) to avoid the collision risk a single shared helper name would create.

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_io.py -q`. Expect all passed.

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/io.py tests/research/shadow_expectancy/testkit.py tests/research/shadow_expectancy/test_io.py && git commit -m "feat(research): shadow-expectancy temporal-log reader + candidate joiner"`

---

### Task 4: Canonical-detection collapse + consistency gates (§6)

**Files:**
- Create `research/harness/shadow_expectancy/collapse.py`
- Test `tests/research/shadow_expectancy/test_collapse.py`

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_collapse.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

from research.harness.shadow_expectancy.collapse import (
    collapse_detections, normalize_tick,
)


@dataclass
class _Det:  # minimal detection view the collapser needs
    detection_id: int
    pivot: float
    forward_series_key: tuple   # (session, o, h, l, c) tuple-of-tuples
    first_trigger_session: str | None


def _det(did, pivot, series=(("2026-06-01", 9.6, 10.2, 9.5, 10.1),), trig="2026-06-01"):
    return _Det(did, pivot, tuple(series), trig)


def test_canonical_is_pivot_match_and_collapses_ALL_non_canonical():
    # Codex C4: the group is ALL detections for (run, ticker). The canonical is the
    # pivot-matching one (tie-broken by lowest id); collapsed_ids covers EVERY other
    # detection in the group -- INCLUDING the non-pivot-matching det 9 -- as long as the
    # whole group shares an identical frozen series + first trigger.
    dets = [_det(5, 10.0), _det(2, 10.0), _det(9, 11.0)]
    res = collapse_detections(dets, candidate_pivot=10.0)
    assert res.canonical.detection_id == 2
    assert sorted(res.collapsed_ids) == [5, 9]   # group_size - 1 (C4)
    assert res.exclusion_reason is None


def test_pivot_mismatch_yields_no_canonical_detection():
    # C-review M4: a candidate EXISTS (candidate_pivot=10.0) but NO detection pivot matches
    # it -> a canonical-detection integrity fault, distinct from a missing candidate row.
    dets = [_det(1, 11.0)]
    res = collapse_detections(dets, candidate_pivot=10.0)
    assert res.canonical is None and res.exclusion_reason == "no_canonical_detection"


def test_missing_candidate_yields_no_candidate_join():
    # No candidate row at all (candidate_pivot is None) -> no_candidate_join (NOT
    # no_canonical_detection -- that reason is reserved for a present-but-unmatchable pivot).
    dets = [_det(1, 11.0)]
    res = collapse_detections(dets, candidate_pivot=None)
    assert res.canonical is None and res.exclusion_reason == "no_candidate_join"


def test_tick_normalized_pivot_match():
    dets = [_det(1, 10.00004)]
    res = collapse_detections(dets, candidate_pivot=10.00001)  # equal at 4 decimals
    assert res.canonical is not None and res.exclusion_reason is None


def test_divergent_forward_series_excludes():
    a = _det(1, 10.0, series=(("2026-06-01", 9.6, 10.2, 9.5, 10.1),))
    b = _det(2, 10.0, series=(("2026-06-01", 9.6, 10.9, 9.5, 10.1),))  # diff high
    res = collapse_detections([a, b], candidate_pivot=10.0)
    assert res.exclusion_reason == "inconsistent_detection_series"


def test_NON_pivot_matching_divergent_series_still_excludes():
    # Codex C4: a non-pivot-matching detection whose frozen series DIVERGES from the
    # canonical's MUST exclude the whole signal -- the old code only checked the pivot-
    # matching subset and would have missed this.
    canonical = _det(1, 10.0, series=(("2026-06-01", 9.6, 10.2, 9.5, 10.1),))
    other = _det(2, 11.0, series=(("2026-06-01", 9.6, 10.9, 9.5, 10.1),))  # diff pivot AND high
    res = collapse_detections([canonical, other], candidate_pivot=10.0)
    assert res.exclusion_reason == "inconsistent_detection_series"


def test_divergent_trigger_session_excludes():
    a = _det(1, 10.0, trig="2026-06-01")
    b = _det(2, 10.0, trig="2026-06-02")  # same series shape but diff trigger
    b.forward_series_key = a.forward_series_key
    res = collapse_detections([a, b], candidate_pivot=10.0)
    assert res.exclusion_reason == "inconsistent_trigger_state"
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_collapse.py -q`. Expected: `ModuleNotFoundError: No module named 'research.harness.shadow_expectancy.collapse'`.

- [ ] **Step: minimal implementation** — `research/harness/shadow_expectancy/collapse.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research.harness.shadow_expectancy.constants import PRICE_TICK_DECIMALS


def normalize_tick(price: float) -> float:
    return round(float(price), PRICE_TICK_DECIMALS)


@dataclass(frozen=True)
class CollapseResult:
    canonical: Any | None
    collapsed_ids: list[int]
    # no_candidate_join (no candidate row) | no_canonical_detection (candidate present, no
    # pivot match; C-review M4) | inconsistent_detection_series | inconsistent_trigger_state
    # | None
    exclusion_reason: str | None


def collapse_detections(detections, candidate_pivot) -> CollapseResult:
    """Spec 6 / Codex C4: one shadow-trade per unique (run, ticker). The group is
    ALL detections for that (run, ticker). The canonical detection is the one whose
    pivot == candidate.pivot (tick-normalized), tie-broken by lowest detection_id.
    The consistency gates run over the WHOLE group (NOT just the pivot-matching
    subset): EVERY detection in the group MUST share an identical frozen forward
    series AND an identical first triggered_open session, else exclude. The collapsed
    set is every non-canonical detection in the group, so collapsed_duplicate ==
    group_size - 1 (covering non-pivot-matching detections too).
    """
    if candidate_pivot is None:
        return CollapseResult(None, [], "no_candidate_join")
    group = sorted(detections, key=lambda d: d.detection_id)
    target = normalize_tick(candidate_pivot)
    matching = [d for d in group if normalize_tick(d.pivot) == target]
    if not matching:
        # C-review M4: the candidate row EXISTS (candidate_pivot is not None) but NO
        # detection pivot matches it -> a canonical-detection / collapse integrity fault,
        # NOT a missing candidate. Distinct reason `no_canonical_detection`, routed to the
        # unattributed bucket like `inconsistent_*` (a substrate-integrity exclusion).
        return CollapseResult(None, [], "no_canonical_detection")
    # Consistency gates across the ENTIRE group (Codex C4 + R5-M1), keyed off the
    # canonical's frozen series / first trigger.
    canonical = matching[0]  # group is id-sorted, so this is the lowest-id pivot match
    if any(d.forward_series_key != canonical.forward_series_key for d in group):
        return CollapseResult(None, [], "inconsistent_detection_series")
    if any(d.first_trigger_session != canonical.first_trigger_session for d in group):
        return CollapseResult(None, [], "inconsistent_trigger_state")
    collapsed = [d.detection_id for d in group if d.detection_id != canonical.detection_id]
    return CollapseResult(canonical, collapsed, None)
```

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_collapse.py -q`. Expect all passed.

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/collapse.py tests/research/shadow_expectancy/test_collapse.py && git commit -m "feat(research): shadow-expectancy canonical-detection collapse + consistency gates (6)"`

---

### Task 5: Hypothesis attribution glue (§6/§6.1) + unattributed handling

**Files:**
- Create `research/harness/shadow_expectancy/attribution.py`
- Test `tests/research/shadow_expectancy/test_attribution.py`

**IMPORTANT (recon correction):** migration 0008 ALREADY seeds the four v0.1 hypotheses with `status='active'` (verified: `swing/data/migrations/0008_hypothesis_registry.sql:45-68`, `INSERT OR IGNORE` keyed on `UNIQUE name`). Because `run_migrations(conn, target_version=24)` runs 0008, the registry is live in EVERY test DB — do NOT add a `seed_default_registry` helper (it would collide on `UNIQUE(name)` with an `IntegrityError`). Read the active registry directly via `list_hypotheses(conn, status_filter='active')`.

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_attribution.py`:
```python
from __future__ import annotations

from research.harness.shadow_expectancy.attribution import attribute_hypotheses
from tests.research.shadow_expectancy.testkit import make_db
from swing.data.models import Candidate, CriterionResult
from swing.data.repos.hypothesis import list_hypotheses


def _cand(bucket, criteria):
    return Candidate(
        ticker="AAA", bucket=bucket, close=10.0, pivot=10.0, initial_stop=9.0,
        adr_pct=None, tight_streak=None, pullback_pct=None, prior_trend_pct=None,
        rs_rank=None, rs_return_12w_vs_spy=None, rs_method="fallback_spy",
        pattern_tag=None, notes=None,
        criteria=tuple(CriterionResult(n, lyr, r) for n, lyr, r in criteria),
    )


def _active_registry(conn):
    return list_hypotheses(conn, status_filter="active")


def test_aplus_maps_to_h1(tmp_path):
    conn = make_db(tmp_path)  # migration 0008 seeds the 4 active hypotheses
    names = attribute_hypotheses(_cand("aplus", []), registry=_active_registry(conn))
    assert "A+ baseline" in names


def test_watch_proximity_only_maps_to_h2(tmp_path):
    conn = make_db(tmp_path)
    cand = _cand("watch", [("proximity_20ma", "trend_template", "fail")])
    names = attribute_hypotheses(cand, registry=_active_registry(conn))
    assert "Near-A+ defensible: extension test" in names
    # exclusivity: a proximity-only miss is NOT H3/H4.
    assert "Sub-A+ VCP-not-formed" not in names
    assert "Capital-blocked: smaller-position test" not in names


def test_watch_tightness_miss_maps_to_h3(tmp_path):
    # Verified against swing/recommendations/hypothesis.py _sub_aplus_vcp_not_formed_match:
    # watch AND (tightness OR vcp_volume_contraction) in non-pass AND non-pass subset of
    # (DOCTRINE_DEFENSIBLE_MISS_SET | {tightness, vcp_volume_contraction}).
    conn = make_db(tmp_path)
    cand = _cand("watch", [("tightness", "vcp", "fail")])
    names = attribute_hypotheses(cand, registry=_active_registry(conn))
    assert "Sub-A+ VCP-not-formed" in names
    assert "Near-A+ defensible: extension test" not in names  # not a proximity-only miss


def test_watch_vcp_volume_contraction_miss_also_maps_to_h3(tmp_path):
    conn = make_db(tmp_path)
    cand = _cand("watch", [("vcp_volume_contraction", "vcp", "fail")])
    assert "Sub-A+ VCP-not-formed" in attribute_hypotheses(
        cand, registry=_active_registry(conn))


def test_watch_risk_feasibility_only_maps_to_h4(tmp_path):
    # Verified against _capital_blocked_match: bucket in (watch, skip) AND non-pass set
    # is EXACTLY {risk_feasibility}.
    conn = make_db(tmp_path)
    cand = _cand("watch", [("risk_feasibility", "risk", "fail")])
    names = attribute_hypotheses(cand, registry=_active_registry(conn))
    assert "Capital-blocked: smaller-position test" in names
    assert "Sub-A+ VCP-not-formed" not in names   # risk_feasibility is not a VCP trigger


def test_SKIP_risk_feasibility_only_maps_to_h4(tmp_path):
    # C-review M5 + spec 6.1: production _capital_blocked_match accepts bucket in
    # ("watch", "skip") for a risk_feasibility-ONLY miss -- and `skip` is in fact the
    # production-realized bucket (risk_feasibility is a hard pre-filter that drives
    # bucket_for to 'skip'). The watch-only test above missed the dominant real case.
    # Verified against swing/recommendations/hypothesis.py:_capital_blocked_match:254-256.
    conn = make_db(tmp_path)
    cand = _cand("skip", [("risk_feasibility", "risk", "fail")])
    names = attribute_hypotheses(cand, registry=_active_registry(conn))
    assert "Capital-blocked: smaller-position test" in names
    assert "Sub-A+ VCP-not-formed" not in names


def test_no_match_returns_empty(tmp_path):
    # 'orderliness' is neither a VCP trigger nor proximity/risk-only, so no hypothesis
    # fires -> empty list -> the caller buckets this as the matched_no_hypothesis REASON
    # WITHIN the unattributed funnel bucket (C-review M1).
    conn = make_db(tmp_path)
    cand = _cand("watch", [("orderliness", "vcp", "fail")])
    assert attribute_hypotheses(cand, registry=_active_registry(conn)) == []
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_attribution.py -q`. Expected: `ModuleNotFoundError: No module named 'research.harness.shadow_expectancy.attribution'`.

- [ ] **Step: minimal implementation** —
  - `research/harness/shadow_expectancy/attribution.py`:
```python
from __future__ import annotations

from collections.abc import Iterable

from swing.data.models import Candidate, HypothesisRegistryEntry
from swing.recommendations.hypothesis import match_candidate_to_hypotheses


def attribute_hypotheses(
    candidate: Candidate, *, registry: Iterable[HypothesisRegistryEntry],
) -> list[str]:
    """Post-hoc hypothesis names this signal advances (spec 6/6.1).

    Thin wrapper over the production matcher (pure, keyword-only registry).
    A signal with zero matches is the caller's responsibility to bucket
    (unattributed is a FUNNEL concern, decided in funnel.py / run.py).
    """
    matches = match_candidate_to_hypotheses(candidate, registry=list(registry))
    return [m.hypothesis_name for m in matches]
```
  No `testkit` change is needed — migration 0008 already seeds the four active hypotheses into every test DB (see the recon-correction note above). The matcher consumes them via `list_hypotheses(conn, status_filter='active')`.

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_attribution.py -q`. Expect all passed.

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/attribution.py tests/research/shadow_expectancy/test_attribution.py && git commit -m "feat(research): shadow-expectancy hypothesis attribution glue (6.1)"`

---

### Task 6: Exit-fill bracket model (§5.6/§5.8)

**Files:**
- Create `research/harness/shadow_expectancy/bracket.py`
- Test `tests/research/shadow_expectancy/test_bracket.py`

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_bracket.py`:
```python
from __future__ import annotations

import pytest

from research.harness.shadow_expectancy.bracket import (
    ma_exit_fill, price_stop_fill,
)


def test_price_stop_realistic_gaps_through_below_stop():
    # gap-down open below stop: realistic fills at min(stop, open) = open
    assert price_stop_fill("realistic", stop=9.0, bar_open=8.5) == 8.5


def test_price_stop_realistic_no_gap_fills_at_stop():
    assert price_stop_fill("realistic", stop=9.0, bar_open=9.4) == 9.0


def test_price_stop_favorable_always_at_stop():
    assert price_stop_fill("favorable_reprice", stop=9.0, bar_open=8.5) == 9.0


def test_ma_exit_realistic_is_next_open():
    assert ma_exit_fill("realistic", signal_close=11.0, next_open=10.6) == 10.6


def test_ma_exit_favorable_is_max_of_close_and_open():
    assert ma_exit_fill("favorable_reprice", signal_close=11.0, next_open=10.6) == 11.0
    assert ma_exit_fill("favorable_reprice", signal_close=10.4, next_open=10.9) == 10.9


def test_favorable_ge_realistic_for_a_given_exit():
    for arm_pair in [(9.0, 8.5), (9.0, 9.4)]:
        stop, op = arm_pair
        assert (price_stop_fill("favorable_reprice", stop=stop, bar_open=op)
                >= price_stop_fill("realistic", stop=stop, bar_open=op))
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_bracket.py -q`. Expected `ModuleNotFoundError: ...bracket`.

- [ ] **Step: minimal implementation** — `research/harness/shadow_expectancy/bracket.py`:
```python
from __future__ import annotations


def price_stop_fill(arm: str, *, stop: float, bar_open: float) -> float:
    """Spec 5.6 price-level stop fill. realistic = min(stop, open) (gap-down
    realizes the >1R loss); favorable_reprice = stop exactly."""
    if arm == "realistic":
        return min(stop, bar_open)
    if arm == "favorable_reprice":
        return stop
    raise ValueError(f"unknown bracket arm: {arm!r}")


def ma_exit_fill(arm: str, *, signal_close: float, next_open: float) -> float:
    """Spec 5.6 close-below-MA trail fill. realistic = next-session open;
    favorable_reprice = max(signal_close, next_open) (non-executable upper bound)."""
    if arm == "realistic":
        return next_open
    if arm == "favorable_reprice":
        return max(signal_close, next_open)
    raise ValueError(f"unknown bracket arm: {arm!r}")
```

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_bracket.py -q`. Expect all passed.

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/bracket.py tests/research/shadow_expectancy/test_bracket.py && git commit -m "feat(research): shadow-expectancy exit-fill bracket model (5.6/5.8)"`

---

### Task 7: Simulator state machine — entry, stop, degenerate-risk, exit-reason taxonomy (§5.0-§5.2, §5.6)

**Files:**
- Create `research/harness/shadow_expectancy/simulator.py` (SimParams, SimResult, Leg, `simulate`)
- Test `tests/research/shadow_expectancy/test_simulator.py` (golden walks a, b, f)

This task lands the simulator core (entry fill, the §5.0 precedence skeleton, the price-stop test, degenerate-risk exclusion, the realistic/favorable arms via Task 6). The partial/breakeven/MA-trail and full censoring land in Tasks 8-9.

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_simulator.py` (golden walks a/b/f):
```python
from __future__ import annotations

import math

import pytest

from research.harness.shadow_expectancy.io import Bar
from research.harness.shadow_expectancy.simulator import SimParams, simulate


def _params(**kw):
    base = dict(initial_shares=100.0, partial_session_n=3, partial_pct=0.5,
                breakeven_r_trigger=1.0, maturity_fast_ma_r=2.0, ma_fast_period=10,
                ma_slow_period=20, horizon_sessions=126)
    base.update(kw)
    return SimParams(**base)


def test_golden_a_gap_up_entry_single_fill_ambiguity_flag():
    # detection pivot 10; entry bar gaps up: open 10.5 > pivot -> entry_fill = 10.5.
    # MECHANICAL initial stop = entry_bar.low = 10.2 (C1: NOT a candidate input).
    # entry_bar.low(10.2) < entry_fill(10.5) -> ambiguous subset; rps = 10.5 - 10.2 = 0.3.
    entry_bar = Bar("2026-06-01", open=10.5, high=11.0, low=10.2, close=10.8)
    # one calm forward bar that never trips the entry-bar-low stop, then horizon.
    fwd = [Bar("2026-06-02", 10.8, 11.2, 10.6, 11.0)]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=1))
    assert res.entry_fill == 10.5
    assert res.initial_stop == 10.2                 # C1: derived from entry_bar.low
    assert res.entry_bar_ambiguous is True          # low(10.2) < entry_fill(10.5)
    assert res.degenerate is False
    assert math.isclose(res.risk_per_share, 0.3)    # 10.5 - 10.2


def test_golden_b_gap_down_stop_blows_through_1R():
    # entry_fill 10.0, MECHANICAL initial stop = entry_bar.low = 9.0 (rps = 1.0).
    # Next bar gaps down: open 8.5 (< stop), low 8.0. realistic fills at min(stop,open)=8.5
    # -> single-leg R = (8.5-10.0)*100 / (1.0*100) = -1.5; favorable fills at stop 9.0 -> -1R.
    entry_bar = Bar("2026-06-01", open=10.0, high=10.4, low=9.0, close=10.2)
    fwd = [Bar("2026-06-02", open=8.5, high=8.6, low=8.0, close=8.2)]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd, params=_params())
    assert res.initial_stop == 9.0                  # C1: entry_bar.low
    assert math.isclose(res.risk_per_share, 1.0)
    assert res.exit_reason == "initial_stop"
    assert math.isclose(res.realized_r["realistic"], -1.5)
    assert math.isclose(res.realized_r["favorable_reprice"], -1.0)
    assert res.realized_r["favorable_reprice"] >= res.realized_r["realistic"]


def test_golden_f_degenerate_risk_excluded():
    # C1: degenerate requires entry_fill <= entry_bar.low. Since entry_fill = max(pivot,open)
    # and low <= open, this happens only when entry_bar.low == entry_bar.open AND pivot <= open
    # (a flat-bottomed bar that opens on its low). pivot 9.0, open 9.0, low 9.0 -> entry_fill 9.0,
    # initial_stop 9.0, rps 0 -> degenerate.
    entry_bar = Bar("2026-06-01", open=9.0, high=9.5, low=9.0, close=9.2)
    res = simulate(pivot=9.0, entry_bar=entry_bar, forward_bars=[], params=_params())
    assert res.degenerate is True
    assert res.exit_reason == "degenerate_risk"
    assert res.realized_r is None
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_simulator.py -q`. Expected `ModuleNotFoundError: ...simulator`.

- [ ] **Step: minimal implementation** — `research/harness/shadow_expectancy/simulator.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field

from research.harness.shadow_expectancy.bracket import price_stop_fill
from research.harness.shadow_expectancy.constants import BRACKET_ARMS
from research.harness.shadow_expectancy.io import Bar
from swing.trades.derived_metrics import (
    initial_risk_per_share, r_multiple, realized_pnl,
)


@dataclass(frozen=True)
class SimParams:
    initial_shares: float
    partial_session_n: int
    partial_pct: float
    breakeven_r_trigger: float
    maturity_fast_ma_r: float
    ma_fast_period: int
    ma_slow_period: int
    horizon_sessions: int


@dataclass(frozen=True)
class Leg:
    action: str        # 'entry' | 'partial' | 'exit' | 'mtm'
    qty: float
    price: float       # per ARM; stored as a dict at the SimResult level
    session: str


@dataclass
class SimResult:
    entry_fill: float
    initial_stop: float          # C1: mechanical stop = entry_bar.low (NOT candidate-supplied)
    risk_per_share: float
    entry_bar_ambiguous: bool
    degenerate: bool
    exit_reason: str
    open_at_horizon: bool
    # per-arm: {"realistic": R, "favorable_reprice": R}; None when degenerate.
    realized_r: dict | None
    legs: list = field(default_factory=list)
    holding_sessions: int = 0
    # m3 (defined HERE at the dataclass's definition site so Task 8's price-stop return
    # can set it independently of Task 9): the per-arm terminal exit fill
    # {"realistic": x, "favorable_reprice": y} for a CLOSED trade's terminal leg; None for
    # open/MTM/degenerate where both arms coincide. Task 8's stop-exit return and Task 9's
    # MA-exit return populate it; the horizon/degenerate returns leave it None.
    terminal_fill: dict | None = None
    # Censoring/horizon annotations (Task 9 sets these on the open-at-horizon return; the
    # closed/degenerate returns leave them defaulted).
    censoring_scenarios: dict | None = None
    forced_exit_collapsed_to_mtm: bool = False


def _entry_fill(pivot: float, entry_bar: Bar) -> float:
    return max(pivot, entry_bar.open)


def _r_for_legs(entry_fill, rps, initial_shares, legs_priced) -> float:
    """Multi-leg R on ONE FIXED denominator (spec 5.8 / Codex C2).

    legs_priced: list of (qty, price). Sum the per-leg realized P&L, then divide
    ONCE by (rps * initial_shares) via a single r_multiple call. Summing
    r_multiple(...quantity=leg_qty) per leg would divide each leg by its OWN
    denominator (rps*leg_qty) and double-count (50%@+1.2R + 50%@+2.0R would total
    3.2R instead of the correct 1.6R).
    """
    total_pnl = sum(
        realized_pnl(entry_price=entry_fill, exit_price=price, quantity=qty)
        for qty, price in legs_priced
    )
    return r_multiple(realized_pnl=total_pnl, initial_risk_per_share=rps,
                      quantity=initial_shares)


def simulate(*, pivot, entry_bar: Bar, forward_bars, params: SimParams):
    # C1 / spec 5.2 / D6: the MECHANICAL initial stop is the entry bar's low-of-day,
    # derived internally -- NOT passed from the candidate. risk_per_share = entry_fill
    # - entry_bar.low; degenerate gate = entry_fill <= entry_bar.low.
    entry_fill = _entry_fill(pivot, entry_bar)
    initial_stop = entry_bar.low
    rps = initial_risk_per_share(entry_price=entry_fill, initial_stop=initial_stop)
    ambiguous = entry_bar.low < entry_fill
    if entry_fill <= initial_stop:  # spec 5.2 / D6 -> non-positive denominator
        return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                         risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                         degenerate=True, exit_reason="degenerate_risk",
                         open_at_horizon=False, realized_r=None)
    current_stop = initial_stop
    shares = params.initial_shares
    horizon = min(params.horizon_sessions, len(forward_bars))
    # Core (Task 7): stop test only. Partial/breakeven/MA land in Tasks 8-9.
    for i in range(horizon):
        bar = forward_bars[i]
        # 5.0 precedence step 1: intrabar price-level stop test on prior close stop.
        if bar.low <= current_stop:
            realized = {}
            terminal_by_arm = {}
            for arm in BRACKET_ARMS:
                fill = price_stop_fill(arm, stop=current_stop, bar_open=bar.open)
                terminal_by_arm[arm] = fill
                realized[arm] = _r_for_legs(entry_fill, rps, shares, [(shares, fill)])
            return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                             risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                             degenerate=False, exit_reason="initial_stop",
                             open_at_horizon=False, realized_r=realized,
                             holding_sessions=i + 1,
                             legs=[Leg("exit", shares, terminal_by_arm["realistic"],
                                       bar.session)])
    # Reached horizon with no exit -> open-at-horizon (scenarios computed in scorecard;
    # Task 9 fills the four censoring numbers). Placeholder MTM for the core task.
    last_close = forward_bars[horizon - 1].close if horizon else entry_fill
    realized = {arm: _r_for_legs(entry_fill, rps, shares, [(shares, last_close)])
                for arm in BRACKET_ARMS}
    return SimResult(entry_fill=entry_fill, initial_stop=initial_stop, risk_per_share=rps,
                     entry_bar_ambiguous=ambiguous, degenerate=False,
                     exit_reason="horizon_mtm", open_at_horizon=True,
                     realized_r=realized, holding_sessions=horizon)
```

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_simulator.py -q`. Expect a/b/f passed.

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/simulator.py tests/research/shadow_expectancy/test_simulator.py && git commit -m "feat(research): shadow-expectancy simulator core -- entry/stop/degenerate-risk (5.0-5.2)"`

---

### Task 8: Simulator — Day-N partial + breakeven + EOD precedence (§5.0, §5.3, §5.4)

**Files:**
- Modify `research/harness/shadow_expectancy/simulator.py`
- Modify `tests/research/shadow_expectancy/test_simulator.py` (golden walks c-partial-leg, e-not-in-profit, precedence)

- [ ] **Step: write failing test** — append to `test_simulator.py`:
```python
def test_golden_e_not_in_profit_at_N_no_partial():
    # entry_fill 10.0, mechanical stop = entry_bar.low = 9.0. session 3 close 9.8
    # (< entry_fill) -> NO partial. (lows kept >= 9.0 so no stop-out before s3.)
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.1)
    fwd = [
        Bar("2026-06-02", 10.1, 10.3, 9.7, 9.9),   # s1
        Bar("2026-06-03", 9.9, 10.0, 9.6, 9.85),   # s2
        Bar("2026-06-04", 9.85, 9.95, 9.6, 9.8),   # s3 close 9.8 < entry -> no partial
    ]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=3))
    assert res.initial_stop == 9.0
    assert all(leg.action != "partial" for leg in res.legs)


def test_partial_fires_at_session_3_when_in_profit():
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.1)   # stop = low = 9.0
    fwd = [
        Bar("2026-06-02", 10.2, 10.6, 10.0, 10.5),
        Bar("2026-06-03", 10.5, 10.9, 10.3, 10.8),
        Bar("2026-06-04", 10.8, 11.4, 10.7, 11.2),   # s3 close 11.2 > entry -> partial
    ]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=3))
    partials = [leg for leg in res.legs if leg.action == "partial"]
    assert len(partials) == 1 and partials[0].qty == 50.0 and partials[0].price == 11.2


def test_breakeven_raises_stop_to_entry_after_1R():
    # entry_fill 10.0, mechanical stop = entry_bar.low = 9.0 (rps 1). s1 close 11.2 ->
    # r_so_far >= 1 -> stop -> 10.0. s2 low 9.9 <= BE stop 10.0 (and > old 9.0) -> BE exit.
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.1)
    fwd = [
        Bar("2026-06-02", 10.5, 11.3, 10.4, 11.2),  # s1 close -> +1.2R, BE raise
        Bar("2026-06-03", 11.0, 11.1, 9.9, 10.0),   # s2 low 9.9 <= BE stop 10.0 -> exit
    ]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=2))
    assert res.exit_reason == "breakeven_stop"


def test_precedence_stop_wins_over_partial_and_ma_same_bar():
    # A bar where stop-eligibility AND partial-eligibility both hold: stop (step 1) wins.
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.1)   # stop = low = 9.0
    fwd = [
        Bar("2026-06-02", 10.2, 10.6, 10.0, 10.5),
        Bar("2026-06-03", 10.5, 10.9, 10.3, 10.8),
        # s3: low 8.9 <= stop 9.0 (stop test) AND close 11.0 > entry (partial-eligible)
        Bar("2026-06-04", 10.8, 11.2, 8.9, 11.0),
    ]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=3))
    assert res.exit_reason == "initial_stop"
    assert all(leg.action != "partial" for leg in res.legs)  # stop terminated before partial


def test_multi_leg_r_uses_fixed_denominator_golden_1p6R():
    # Codex C2 golden: assert the multi-leg R helper directly (the load-bearing denominator
    # math). Two 50-share legs at +1.2R-equiv (11.2) and +2.0R-equiv (12.0); entry_fill 10.0,
    # rps 1.0, initial_shares 100. FIXED denominator: total_pnl = (11.2-10)*50 + (12.0-10)*50
    # = 60 + 100 = 160; R = 160/(1.0*100) = 1.6R. The OLD buggy per-leg sum would have been
    # 60/(1*50) + 100/(1*50) = 1.2 + 2.0 = 3.2R -- so 1.6 vs 3.2 discriminates the fix.
    from research.harness.shadow_expectancy.simulator import _r_for_legs
    total = _r_for_legs(entry_fill=10.0, rps=1.0, initial_shares=100.0,
                        legs_priced=[(50.0, 11.2), (50.0, 12.0)])
    assert math.isclose(total, 1.6)
    per_leg_buggy = (11.2 - 10.0) * 50 / (1.0 * 50) + (12.0 - 10.0) * 50 / (1.0 * 50)
    assert math.isclose(per_leg_buggy, 3.2) and per_leg_buggy != total
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_simulator.py -q`. Expect the 4 new tests FAIL (no partial/breakeven logic yet; precedence/legs absent).

- [ ] **Step: minimal implementation** — extend `simulate`'s loop in `simulator.py`. Replace the core loop with the full per-bar EOD precedence and track `shares_remaining` + multi-leg fills per arm:
```python
def _running_r(entry_fill, rps, price) -> float:
    return (price - entry_fill) / rps  # mirrors equity.r_so_far formula


def simulate(*, pivot, entry_bar: Bar, forward_bars, params: SimParams):
    # C1 / spec 5.2 / D6: mechanical stop = entry_bar.low (derived, not candidate-supplied).
    entry_fill = _entry_fill(pivot, entry_bar)
    initial_stop = entry_bar.low
    rps = initial_risk_per_share(entry_price=entry_fill, initial_stop=initial_stop)
    ambiguous = entry_bar.low < entry_fill
    if entry_fill <= initial_stop:
        return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                         risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                         degenerate=True, exit_reason="degenerate_risk",
                         open_at_horizon=False, realized_r=None)

    current_stop = initial_stop
    shares = params.initial_shares
    shares_remaining = shares
    horizon = min(params.horizon_sessions, len(forward_bars))
    # legs carry an ARM-INDEPENDENT price for partials (a close, identical across arms)
    # and an ARM-DEPENDENT price only for the terminal stop/MA exit (computed at exit).
    closed_legs: list[tuple[str, float, float, str]] = []  # (action, qty, price, session)

    for i in range(horizon):
        bar = forward_bars[i]
        session_index = i + 1  # 1-based sessions after entry

        # 5.0 step 1: intrabar price-level stop on the PRIOR session's close stop.
        if bar.low <= current_stop:
            exit_reason = "breakeven_stop" if current_stop >= entry_fill else "initial_stop"
            realized = {}
            terminal_legs_by_arm = {}
            for arm in BRACKET_ARMS:
                fill = price_stop_fill(arm, stop=current_stop, bar_open=bar.open)
                priced = [(q, p) for (_a, q, p, _s) in closed_legs] + \
                         [(shares_remaining, fill)]
                # FIXED denominator: rps * initial_shares (C2), NOT per-leg.
                realized[arm] = _r_for_legs(entry_fill, rps, shares, priced)
                terminal_legs_by_arm[arm] = fill
            legs = [Leg(a, q, p, s) for (a, q, p, s) in closed_legs]
            legs.append(Leg("exit", shares_remaining,
                            terminal_legs_by_arm["realistic"], bar.session))
            return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                             risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                             degenerate=False, exit_reason=exit_reason,
                             open_at_horizon=False, realized_r=realized,
                             holding_sessions=session_index, legs=legs,
                             terminal_fill=dict(terminal_legs_by_arm))  # m3: both arms

        # 5.0 step 2: EOD signals on bar.close, fixed order.
        # (a) MA-trail close-below lands in Task 9; (b) Day-N partial; (c) breakeven.
        if (session_index == params.partial_session_n
                and bar.close > entry_fill and shares_remaining == params.initial_shares):
            qty = params.initial_shares * params.partial_pct
            closed_legs.append(("partial", qty, bar.close, bar.session))
            shares_remaining -= qty
        # (c) breakeven raise for NEXT session (5.4): once r_so_far >= trigger and stop<entry.
        if (_running_r(entry_fill, rps, bar.close) >= params.breakeven_r_trigger
                and current_stop < entry_fill):
            current_stop = entry_fill

    # horizon reached: open-at-horizon MTM placeholder (Task 9 computes 4 scenarios).
    last_close = forward_bars[horizon - 1].close if horizon else entry_fill
    realized = {}
    for arm in BRACKET_ARMS:
        priced = [(q, p) for (_a, q, p, _s) in closed_legs] + [(shares_remaining, last_close)]
        realized[arm] = _r_for_legs(entry_fill, rps, shares, priced)
    legs = [Leg(a, q, p, s) for (a, q, p, s) in closed_legs]
    legs.append(Leg("mtm", shares_remaining, last_close,
                    forward_bars[horizon - 1].session if horizon else entry_bar.session))
    return SimResult(entry_fill=entry_fill, initial_stop=initial_stop, risk_per_share=rps,
                     entry_bar_ambiguous=ambiguous, degenerate=False,
                     exit_reason="horizon_mtm", open_at_horizon=True,
                     realized_r=realized, holding_sessions=horizon, legs=legs)
```

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_simulator.py -q`. Expect all (a/b/f + the 4 new) passed.

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/simulator.py tests/research/shadow_expectancy/test_simulator.py && git commit -m "feat(research): shadow-expectancy partial + breakeven + EOD precedence (5.0/5.3/5.4)"`

---

### Task 9: Simulator — maturity-staged 10/20 MA trail + four censoring scenarios (§5.5, §5.7, D10)

**Files:**
- Modify `research/harness/shadow_expectancy/simulator.py` (MA trail + `censoring_scenarios` dict on SimResult)
- Modify `tests/research/shadow_expectancy/test_simulator.py` (golden c-trail-winner, d-horizon-censored-runner)

- [ ] **Step: write failing test** — append to `test_simulator.py`:
```python
def test_golden_c_partial_then_ma_close_below_trail_winner():
    # Codex M1: construct so ONLY ma_close_below can fire. entry_fill 10.0, mechanical stop
    # = entry_bar.low = 9.0 (rps 1.0); after the s1 +1R close the BE stop raises to 10.0, and
    # EVERY post-entry low is kept >= 10.5 (> the BE stop) so no price-stop can pre-empt. A
    # steadily-rising series sits ABOVE its own SMA, so the trail only fires on the engineered
    # drop bar (i=20), which closes BELOW the SMA while its LOW (10.5) stays above the stop.
    # i=21 exists as the next bar so the realistic MA fill is its open (next-session open).
    from datetime import date, timedelta
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.5)   # entry_fill 10.0, stop 9.0
    closes = [10.6 + 0.1 * i for i in range(22)]           # steady rise, all closes >= 10.6
    d = date(2026, 6, 2)
    fwd = [Bar((d + timedelta(days=i)).isoformat(), c - 0.05, c + 0.2, c - 0.1, c)
           for i, c in enumerate(closes)]                  # lows = c - 0.1 >= 10.5 > stop 10.0
    # engineer the MA-exit on bar i=20 (NOT the last bar): close drops below the trailing MA
    # but the low stays at 10.6 (> BE stop 10.0). i=21 remains as the next bar (next-open fill).
    drop = fwd[20]
    fwd[20] = Bar(drop.session, drop.open, drop.high, 10.6, 11.0)  # close 11.0 < SMA; low 10.6
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=22))
    assert res.exit_reason == "ma_close_below"            # EXACTLY -- no stop pre-empts (M1)
    assert any(leg.action == "partial" for leg in res.legs)   # multi-leg: partial at s3
    # realistic terminal fill is the NEXT bar's open (5.6); favorable >= realistic.
    assert res.realized_r["favorable_reprice"] >= res.realized_r["realistic"]


def test_ma_close_below_at_horizon_edge_exits_at_signal_close():
    # Codex M2: the MA-close-below fires on the LAST available bar (no next session). The exit
    # must fill at the SIGNAL close (realistic) / favorable per 5.6 -- NOT silently censor.
    from datetime import date, timedelta
    entry_bar = Bar("2026-06-01", 10.0, 10.4, 9.0, 10.5)
    closes = [10.6 + 0.1 * i for i in range(21)]
    d = date(2026, 6, 2)
    fwd = [Bar((d + timedelta(days=i)).isoformat(), c - 0.05, c + 0.2, c - 0.1, c)
           for i, c in enumerate(closes)]
    drop = fwd[-1]                                          # the LAST bar fires the trail
    fwd[-1] = Bar(drop.session, drop.open, drop.high, 10.6, 11.0)
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=21))
    assert res.exit_reason == "ma_close_below"             # NOT horizon_mtm / censored
    assert res.open_at_horizon is False
    # signal-close fill on the edge: realistic == favorable (both at the signal close, no
    # next open to gap) -- 11.0 is the terminal leg price.
    term = [leg for leg in res.legs if leg.action == "exit"][-1]
    assert term.price == 11.0


def test_golden_d_horizon_censored_runner_four_scenarios():
    # A monotonic runner that never stops/MA-exits within a SHORT horizon -> open_at_horizon.
    from datetime import date, timedelta
    entry_bar = Bar("2026-06-01", 10.0, 10.2, 9.0, 10.1)   # stop = low = 9.0
    d = date(2026, 6, 2)
    fwd = [Bar((d + timedelta(days=i)).isoformat(), 10.1 + i, 10.3 + i, 10.0 + i, 10.2 + i)
           for i in range(5)]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=5))
    assert res.open_at_horizon is True
    sc = res.censoring_scenarios
    assert set(sc) == {"closed_only", "mtm_at_horizon",
                       "forced_exit_at_horizon_open", "stop_level_adverse"}
    # This runner takes the s3 50% partial at close 12.2 (= +1.1R-equiv on the 50-share leg,
    # = (12.2-10.0)*50/(1.0*100) = 1.1R). closed_only counts ONLY that realized partial leg
    # (the still-open 50-share remainder is EXCLUDED): closed_only == 1.1R.
    assert math.isclose(sc["closed_only"]["realistic"], 1.1)
    # realistic == favorable for an open trade under MTM/forced/stop-adverse (5.8).
    for scenario in ("mtm_at_horizon", "forced_exit_at_horizon_open", "stop_level_adverse"):
        assert sc[scenario]["realistic"] == sc[scenario]["favorable_reprice"]
    # stop_level_adverse marks the open remainder at the current (breakeven-raised) stop.
    assert sc["stop_level_adverse"]["realistic"] <= sc["mtm_at_horizon"]["realistic"]
    # this log has NO post-horizon bar -> forced-exit collapses to MTM (5.7 / M3), annotated.
    assert res.forced_exit_collapsed_to_mtm is True
    assert math.isclose(sc["forced_exit_at_horizon_open"]["realistic"],
                        sc["mtm_at_horizon"]["realistic"])
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_simulator.py -q`. Expect the 2 new FAIL (`AttributeError: censoring_scenarios`; MA trail absent).

- [ ] **Step: minimal implementation** — add to `simulator.py`:
  1. An SMA helper computed from frozen forward closes only:
```python
def _sma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _trail_ma_period(running_r: float, params: SimParams) -> int:
    """Maturity-staged 10/20 proxy (D12): >=+2R -> 10MA else 20MA."""
    return params.ma_fast_period if running_r >= params.maturity_fast_ma_r \
        else params.ma_slow_period
```
  The `SimResult` dataclass ALREADY carries `terminal_fill`, `censoring_scenarios`, and `forced_exit_collapsed_to_mtm` (defined at its definition site in Task 7 — M3; do NOT re-declare them). This task only SETS their values: the MA-exit return populates `terminal_fill` (m3: the per-arm terminal exit fill `{"realistic": x, "favorable_reprice": y}` for a CLOSED trade's terminal leg; None for open/MTM where both arms coincide), and the open-at-horizon return populates `censoring_scenarios` + `forced_exit_collapsed_to_mtm`. The price-stop return (Task 8) already sets `terminal_fill`; the horizon/degenerate returns leave it None.
  2. In the EOD block, MA-trail is step 2a, evaluated BEFORE the partial 2b — re-order so MA-trail-close-below is evaluated FIRST and terminates EOD processing. **Codex M2:** the no-next-bar case is NOT silently skipped — it exits at the SIGNAL close (so a natural MA exit at the horizon edge is never misclassified as censored). Import `ma_exit_fill` at the top of `simulator.py` alongside `price_stop_fill`:
```python
        # 5.0 step 2a: MA-trail close-below (evaluated BEFORE the partial; terminates EOD).
        closes_so_far = [b.close for b in forward_bars[: i + 1]]
        running_r = _running_r(entry_fill, rps, bar.close)
        period = _trail_ma_period(running_r, params)
        sma = _sma(closes_so_far, period)
        if sma is not None and bar.close < sma:
            # schedule a full exit at NEXT session open (5.6); Codex M2: if NO next session
            # exists (i+1 >= horizon), exit at the SIGNAL close instead -- this is a genuine
            # MA exit, NOT a censored open trade.
            if i + 1 < horizon:
                nxt = forward_bars[i + 1]
                next_open = nxt.open
                exit_session = nxt.session
                holding = i + 2
            else:
                next_open = bar.close          # M2 edge: no next open -> fill at signal close
                exit_session = bar.session
                holding = i + 1
            realized = {}
            terminal_by_arm = {}
            for arm in BRACKET_ARMS:
                fill = ma_exit_fill(arm, signal_close=bar.close, next_open=next_open)
                terminal_by_arm[arm] = fill
                priced = [(q, p) for (_a, q, p, _s) in closed_legs] + \
                         [(shares_remaining, fill)]
                realized[arm] = _r_for_legs(entry_fill, rps, shares, priced)
            legs = [Leg(a, q, p, s) for (a, q, p, s) in closed_legs]
            legs.append(Leg("exit", shares_remaining,
                            terminal_by_arm["realistic"], exit_session))
            return SimResult(entry_fill=entry_fill, initial_stop=initial_stop,
                             risk_per_share=rps, entry_bar_ambiguous=ambiguous,
                             degenerate=False, exit_reason="ma_close_below",
                             open_at_horizon=False, realized_r=realized,
                             holding_sessions=holding, legs=legs,
                             terminal_fill=dict(terminal_by_arm))  # m3: both arms
```
  3. At horizon, compute the four censoring scenarios over the OPEN remainder. **Codex M3:** the `forced_exit_at_horizon_open` price is the **next available OPEN after the horizon** when `forward_bars` extends beyond `horizon` (the harness passes the FULL chain, NOT a pre-truncated one); it collapses to MTM (last frozen close) ONLY when no post-horizon bar exists, and that collapse is annotated via `forced_exit_collapsed_to_mtm`:
```python
    def _scenarios():
        closed_priced = [(q, p) for (_a, q, p, _s) in closed_legs]
        last = forward_bars[horizon - 1] if horizon else None
        last_close = last.close if last else entry_fill
        # closed_only (PER-TRADE grain; m3): the realized R from THIS trade's already-closed
        # legs only (e.g. a Day-3 partial), dropping the still-open remainder. NOTE this is a
        # DIFFERENT grain from the scorecard's aggregate `closed_only` SCENARIO (Task 10),
        # which EXCLUDES a still-open trade entirely from the closed-only mean. Here we report
        # what this one open trade has realized so far; the scorecard chooses NOT to fold that
        # partial realization into its headline closed-only population. Same label, two grains
        # -- documented in both tasks (m3).
        closed_only = (_r_for_legs(entry_fill, rps, shares, closed_priced)
                       if closed_priced else 0.0)
        mtm = _r_for_legs(entry_fill, rps, shares,
                          closed_priced + [(shares_remaining, last_close)])
        # forced-exit at the next available open AFTER the horizon (5.7 / M3). If the log has
        # no post-horizon bar, collapse to MTM (last close) and annotate.
        if len(forward_bars) > horizon:
            forced_price = forward_bars[horizon].open
            collapsed = False
        else:
            forced_price = last_close
            collapsed = True
        forced = _r_for_legs(entry_fill, rps, shares,
                             closed_priced + [(shares_remaining, forced_price)])
        stop_adv = _r_for_legs(entry_fill, rps, shares,
                               closed_priced + [(shares_remaining, current_stop)])
        def arms(v):  # realistic == favorable for an open trade (5.8)
            return {"realistic": v, "favorable_reprice": v}
        return {
            "closed_only": arms(closed_only),
            "mtm_at_horizon": arms(mtm),
            "forced_exit_at_horizon_open": arms(forced),
            "stop_level_adverse": arms(stop_adv),
        }, collapsed
    scenarios, forced_collapsed = _scenarios()
```
  Set `censoring_scenarios=scenarios` and `forced_exit_collapsed_to_mtm=forced_collapsed` on the horizon `SimResult` return (the one built after the loop). For CLOSED trades (stop/MA exits), leave both at their dataclass defaults (`censoring_scenarios=None`, `forced_exit_collapsed_to_mtm=False`) — the realized R bracket is the answer; the scorecard reads `realized_r` for closed and `censoring_scenarios` for open. The degenerate-risk early return also leaves both defaulted.

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_simulator.py -q`. Expect all golden walks pass. (If a golden numeric is off, adjust the test's hand-computed expectation — recompute under BOTH pre/post paths to confirm the test discriminates, per the regression-arithmetic discipline.)

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/simulator.py tests/research/shadow_expectancy/test_simulator.py && git commit -m "feat(research): shadow-expectancy MA-trail + four censoring scenarios (5.5/5.7/D10)"`

---

### Task 10: Per-hypothesis scorecard (§7.2 + Wilson + honesty suppression + same-bar-adverse)

**Files:**
- Modify `research/harness/shadow_expectancy/scorecard.py` (create)
- Test `tests/research/shadow_expectancy/test_scorecard.py`

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_scorecard.py`:
```python
from __future__ import annotations

import math

from research.harness.shadow_expectancy.scorecard import (
    ShadowTrade, build_hypothesis_scorecard,
)


def _arms(v):
    return {"realistic": v, "favorable_reprice": v}


def _t(hyp, realistic_r, favorable_r, *, triggered=True, open_h=False,
       ambiguous=False, sessions=5, scenarios=None):
    return ShadowTrade(hypothesis=hyp, triggered=triggered, open_at_horizon=open_h,
                       realized_r={"realistic": realistic_r,
                                   "favorable_reprice": favorable_r},
                       entry_bar_ambiguous=ambiguous, holding_sessions=sessions,
                       censoring_scenarios=scenarios)


def test_four_scenario_means_over_all_triggered_trades():
    # Codex C3: each scenario mean is over ALL triggered trades. A closed trade contributes
    # its realized R in ALL FOUR scenarios; an open trade is EXCLUDED in closed_only but
    # contributes its scenario-specific value elsewhere.
    closed = [_t("A+ baseline", 2.0, 2.0), _t("A+ baseline", -1.0, -1.0)]
    open_t = _t("A+ baseline", 0.5, 0.5, open_h=True, scenarios={
        "closed_only": _arms(0.0), "mtm_at_horizon": _arms(0.6),
        "forced_exit_at_horizon_open": _arms(0.4), "stop_level_adverse": _arms(-0.2)})
    sc = build_hypothesis_scorecard([*closed, open_t], sample_floor_mean=2,
                                    sample_floor_rate=2, profit_factor_floor=2)
    card = sc["A+ baseline"]
    s = card["scenarios"]
    # closed_only: the open trade is EXCLUDED -> mean over the 2 closed only = (2.0-1.0)/2 = 0.5
    assert math.isclose(s["closed_only"]["realistic"], 0.5)
    assert s["closed_only"]["n"] == 2          # open trade dropped
    # mtm: closed contribute realized R; open contributes its mtm value 0.6 -> (2-1+0.6)/3
    assert math.isclose(s["mtm_at_horizon"]["realistic"], (2.0 - 1.0 + 0.6) / 3)
    assert math.isclose(s["forced_exit_at_horizon_open"]["realistic"], (2.0 - 1.0 + 0.4) / 3)
    assert math.isclose(s["stop_level_adverse"]["realistic"], (2.0 - 1.0 - 0.2) / 3)
    # headline = realistic-arm closed-only, explicitly labeled (no MTM leak).
    assert math.isclose(card["headline_realistic_closed_only"], 0.5)
    # both arms reported for every scenario.
    for name in ("closed_only", "mtm_at_horizon", "forced_exit_at_horizon_open",
                 "stop_level_adverse"):
        assert set(s[name]) >= {"realistic", "favorable_reprice", "n", "suppressed"}


def test_closed_only_winrate_wilson_no_mtm_leak():
    # win rate + Wilson computed on the CLOSED-only realized R (no open-trade MTM leak).
    closed = [_t("A+ baseline", 2.0, 2.0), _t("A+ baseline", -1.0, -1.0),
              _t("A+ baseline", 1.5, 1.5), _t("A+ baseline", -1.0, -1.0)]
    open_t = _t("A+ baseline", 9.9, 9.9, open_h=True, scenarios={
        "closed_only": _arms(0.0), "mtm_at_horizon": _arms(9.9),
        "forced_exit_at_horizon_open": _arms(9.9), "stop_level_adverse": _arms(0.0)})
    sc = build_hypothesis_scorecard([*closed, open_t], sample_floor_mean=2,
                                    sample_floor_rate=2, profit_factor_floor=2)
    card = sc["A+ baseline"]
    assert card["win_rate"]["k"] == 2 and card["win_rate"]["n"] == 4   # open NOT counted
    assert "wilson" in card["win_rate"]
    assert card["trigger_rate"]["triggered"] == 5     # trigger rate IS over all triggered


def test_profit_factor_suppressed_below_floor():
    trades = [_t("H3", 1.0, 1.0), _t("H3", -1.0, -1.0)]
    sc = build_hypothesis_scorecard(trades, sample_floor_mean=10, sample_floor_rate=10,
                                    profit_factor_floor=10)
    assert sc["H3"]["profit_factor"]["suppressed"] is True
    assert sc["H3"]["scenarios"]["closed_only"]["suppressed"] is True


def test_per_signal_vs_triggered_distinct():
    trades = [_t("H4", 2.0, 2.0, triggered=True),
              _t("H4", 0.0, 0.0, triggered=False)]
    sc = build_hypothesis_scorecard(trades, sample_floor_mean=1, sample_floor_rate=1,
                                    profit_factor_floor=1)
    # headline (closed-only) over 1 closed triggered trade = 2.0; per-signal over 2 signals = 1.0
    assert math.isclose(sc["H4"]["headline_realistic_closed_only"], 2.0)
    assert math.isclose(sc["H4"]["per_signal_expectancy"]["realistic"], 1.0)


def test_same_bar_adverse_sensitivity_only_over_ambiguous():
    trades = [_t("A+ baseline", 2.0, 2.0, ambiguous=True),
              _t("A+ baseline", 1.0, 1.0, ambiguous=False)]
    sc = build_hypothesis_scorecard(trades, sample_floor_mean=1, sample_floor_rate=1,
                                    profit_factor_floor=1)
    card = sc["A+ baseline"]
    # base closed-only mean = 1.5; adverse forces the ambiguous trade to -1R -> (-1 + 1)/2 = 0.0
    assert math.isclose(card["headline_realistic_closed_only"], 1.5)
    assert math.isclose(card["same_bar_adverse_mean_r"]["realistic"], 0.0)
    assert card["ambiguous_count"] == 1
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_scorecard.py -q`. Expect `ModuleNotFoundError`/`ImportError`.

- [ ] **Step: minimal implementation** — `research/harness/shadow_expectancy/scorecard.py`:
```python
from __future__ import annotations

import statistics
from dataclasses import dataclass

from research.harness.shadow_expectancy.constants import BRACKET_ARMS
from swing.metrics.honesty import wilson_ci


@dataclass(frozen=True)
class ShadowTrade:
    hypothesis: str
    triggered: bool
    open_at_horizon: bool
    realized_r: dict | None   # {"realistic":R,"favorable_reprice":R}; None if degenerate
    entry_bar_ambiguous: bool
    holding_sessions: int
    censoring_scenarios: dict | None = None


_SCENARIO_NAMES = ("closed_only", "mtm_at_horizon",
                   "forced_exit_at_horizon_open", "stop_level_adverse")


def _mean(vals):
    return sum(vals) / len(vals) if vals else 0.0


def _scenario_value(trade: "ShadowTrade", scenario: str, arm: str):
    """Codex C3: the per-trade contribution to a scenario mean.

    A CLOSED trade contributes its realized R in ALL FOUR scenarios (identical).
    An OPEN-at-horizon trade is EXCLUDED from closed_only (return None) and
    contributes its scenario-specific value in the other three.

    GRAIN NOTE (m3): this aggregate `closed_only` SCENARIO drops a still-open trade
    ENTIRELY (return None) -- it is the population of fully-closed trades. It is a
    DIFFERENT grain from the simulator's PER-TRADE `censoring_scenarios["closed_only"]`
    (Task 9), which reports a single open trade's already-realized partial-leg R. We
    intentionally do NOT fold an open trade's realized partial into the headline
    closed-only mean here; the per-trade value is available in the ledger/manifest for
    inspection. Same label, two grains -- documented in both tasks.
    """
    if not trade.open_at_horizon:
        return trade.realized_r[arm]
    if scenario == "closed_only":
        return None          # open trade excluded from the aggregate closed-only population
    return trade.censoring_scenarios[scenario][arm]


def build_hypothesis_scorecard(trades, *, sample_floor_mean, sample_floor_rate,
                               profit_factor_floor) -> dict:
    by_hyp: dict[str, list[ShadowTrade]] = {}
    for t in trades:
        by_hyp.setdefault(t.hypothesis, []).append(t)

    out: dict[str, dict] = {}
    for hyp, group in by_hyp.items():
        triggered = [t for t in group if t.triggered and t.realized_r is not None]
        closed = [t for t in triggered if not t.open_at_horizon]
        n_trig = len(triggered)
        n_closed = len(closed)
        card: dict = {}

        # FOUR censoring-scenario means, EACH over ALL triggered trades (D10 / C3).
        # closed contributes realized R in all four; open contributes scenario value
        # (excluded only in closed_only). n is the count actually contributing.
        scenarios: dict = {}
        for sc_name in _SCENARIO_NAMES:
            sc_entry: dict = {}
            n_contrib = None
            for arm in BRACKET_ARMS:
                vals = [v for t in triggered
                        if (v := _scenario_value(t, sc_name, arm)) is not None]
                sc_entry[arm] = _mean(vals)
                n_contrib = len(vals)
            sc_entry["n"] = n_contrib
            sc_entry["suppressed"] = n_contrib < sample_floor_mean
            scenarios[sc_name] = sc_entry
        card["scenarios"] = scenarios

        # Headline = realistic-arm closed-only (no MTM leak), explicitly labeled.
        card["headline_realistic_closed_only"] = scenarios["closed_only"]["realistic"]

        # per-signal expectancy (non-triggers count as 0R; D11). Realized R for closed,
        # MTM (realized_r) for open -- this is the "what did the signal do" per-signal view.
        n_signals = len(group)
        per_signal = {}
        for arm in BRACKET_ARMS:
            vals = [(t.realized_r[arm] if (t.triggered and t.realized_r is not None) else 0.0)
                    for t in group]
            per_signal[arm] = _mean(vals)
        card["per_signal_expectancy"] = per_signal

        # trigger rate (over ALL signals).
        card["trigger_rate"] = {"triggered": n_trig, "signals": n_signals,
                                "rate": (n_trig / n_signals if n_signals else 0.0)}

        # win rate + Wilson + avg win/loss + payoff + profit factor: CLOSED-only realized R
        # (no open-trade MTM leak; matches the headline basis).
        wins = sum(1 for t in closed if t.realized_r["realistic"] > 0)
        wci = wilson_ci(k=wins, n=n_closed) if n_closed else None
        card["win_rate"] = {
            "k": wins, "n": n_closed,
            "wilson": ({"point": wci.point, "lower": wci.lower, "upper": wci.upper}
                       if wci else None),
            "suppressed": n_closed < sample_floor_rate,
        }
        win_rs = [t.realized_r["realistic"] for t in closed if t.realized_r["realistic"] > 0]
        loss_rs = [t.realized_r["realistic"] for t in closed if t.realized_r["realistic"] <= 0]
        avg_win = _mean(win_rs)
        avg_loss = _mean(loss_rs)
        gross_win = sum(win_rs)
        gross_loss = -sum(loss_rs)
        card["avg_win_r"] = avg_win
        card["avg_loss_r"] = avg_loss
        card["payoff_ratio"] = (avg_win / abs(avg_loss)) if avg_loss < 0 else None
        card["profit_factor"] = {
            "value": (gross_win / gross_loss) if gross_loss > 0 else None,
            "suppressed": n_closed < profit_factor_floor,
        }
        card["median_holding_sessions"] = (
            statistics.median([t.holding_sessions for t in triggered]) if triggered else None)

        # same-bar-adverse sensitivity (D9): on the CLOSED-only basis, ambiguous trades -> -1R.
        ambiguous = [t for t in closed if t.entry_bar_ambiguous]
        card["ambiguous_count"] = len(ambiguous)
        adverse_mean = {}
        for arm in BRACKET_ARMS:
            vals = [(-1.0 if t.entry_bar_ambiguous else t.realized_r[arm]) for t in closed]
            adverse_mean[arm] = _mean(vals)
        card["same_bar_adverse_mean_r"] = adverse_mean

        out[hyp] = card
    return out
```

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_scorecard.py -q`. Expect all passed.

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/scorecard.py tests/research/shadow_expectancy/test_scorecard.py && git commit -m "feat(research): shadow-expectancy per-hypothesis scorecard + Wilson + suppression (7.2)"`

---

### Task 11: Two-level denominator funnel (§7.1)

**Files:**
- Create `research/harness/shadow_expectancy/funnel.py`
- Test `tests/research/shadow_expectancy/test_funnel.py`

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_funnel.py`:
```python
from __future__ import annotations

import pytest

from research.harness.shadow_expectancy.collapse import collapse_detections
from research.harness.shadow_expectancy.exceptions import ShadowExpectancyError
from research.harness.shadow_expectancy.funnel import (
    DetectionLevel, SignalOutcome, build_funnel,
)


def test_detection_level_reconciles():
    det = DetectionLevel(total_detections=10, collapsed_duplicate=3, unique_signals=7)
    f = build_funnel(det, signal_outcomes=[])
    assert f["detection_level"]["total_detections"] == 10
    assert (f["detection_level"]["collapsed_duplicate_detection"]
            + f["detection_level"]["unique_signals"]) == 10


def test_unattributed_reasons_vs_per_hypothesis():
    # C-review M1/M4: ALL pre-/non-attribution states are per-reason counters INSIDE the
    # single `unattributed` bucket -- no_candidate_join, no_canonical_detection (candidate
    # present, no pivot match), inconsistent_*, AND matched_no_hypothesis (joined+valid but
    # zero hypotheses). matched_no_hypothesis is a REASON within unattributed, NOT a separate
    # top-level bucket. validate/simulate failures on an ATTRIBUTED signal (invalid_ohlc /
    # degenerate_risk) -> PER-HYPOTHESIS excluded.
    outs = [
        SignalOutcome(hypothesis=None, terminal="unattributed", reason="no_candidate_join"),
        SignalOutcome(hypothesis=None, terminal="unattributed",
                      reason="no_canonical_detection"),
        SignalOutcome(hypothesis=None, terminal="unattributed",
                      reason="inconsistent_detection_series"),
        SignalOutcome(hypothesis=None, terminal="unattributed",
                      reason="matched_no_hypothesis"),
        SignalOutcome(hypothesis=None, terminal="unattributed", reason="multi_match"),  # R3-M1
        SignalOutcome(hypothesis="A+ baseline", terminal="closed", reason=None),
        SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason="invalid_ohlc"),
        SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason="degenerate_risk"),
        SignalOutcome(hypothesis="A+ baseline", terminal="open_at_horizon", reason=None),
        SignalOutcome(hypothesis="A+ baseline", terminal="never_triggered",
                      reason="never_triggered"),
    ]
    det = DetectionLevel(total_detections=10, collapsed_duplicate=0, unique_signals=10)
    f = build_funnel(det, signal_outcomes=outs)
    # ONE unattributed bucket; matched_no_hypothesis + multi_match are counters WITHIN it (M1).
    assert f["unattributed"]["no_candidate_join"] == 1
    assert f["unattributed"]["no_canonical_detection"] == 1          # M4
    assert f["unattributed"]["inconsistent_detection_series"] == 1
    assert f["unattributed"]["matched_no_hypothesis"] == 1           # reason WITHIN unattributed
    assert f["unattributed"]["multi_match"] == 1                     # R3-M1 reason WITHIN unattributed
    assert "matched_no_hypothesis" not in f                          # NOT a top-level bucket (M1)
    assert "multi_match" not in f                                    # NOT a top-level bucket (R3-M1)
    h1 = f["per_hypothesis"]["A+ baseline"]
    assert h1["closed"] == 1 and h1["open_at_horizon"] == 1
    assert h1["excluded"]["degenerate_risk"] == 1
    assert h1["excluded"]["invalid_ohlc"] == 1   # M5: attributed validation failure is per-hyp
    assert h1["never_triggered"] == 1
    assert "no_candidate_join" not in h1.get("excluded", {})


def test_each_signal_lands_in_exactly_one_terminal_bucket():
    outs = [SignalOutcome(hypothesis="A+ baseline", terminal="closed", reason=None)]
    det = DetectionLevel(total_detections=1, collapsed_duplicate=0, unique_signals=1)
    f = build_funnel(det, signal_outcomes=outs)
    h1 = f["per_hypothesis"]["A+ baseline"]
    total = (h1["closed"] + h1["open_at_horizon"] + h1["never_triggered"]
             + sum(h1["excluded"].values()))
    assert total == 1


def test_multi_match_is_a_reason_within_unattributed():
    # R3-M1: a synthetic multi-match signal is excluded under the `multi_match` REASON within
    # the single `unattributed` bucket -- NOT a separate top-level bucket, NOT per-hypothesis.
    det = DetectionLevel(total_detections=1, collapsed_duplicate=0, unique_signals=1)
    f = build_funnel(det, signal_outcomes=[
        SignalOutcome(hypothesis=None, terminal="unattributed", reason="multi_match")])
    assert f["unattributed"]["multi_match"] == 1
    assert "multi_match" not in f          # not a top-level bucket
    assert f["per_hypothesis"] == {}       # no per-hypothesis contribution


@pytest.mark.parametrize("bad", [
    # m1: a hypothesis-None outcome whose reason is missing/None or not in UNATTRIBUTED_REASONS
    # is a producer-contract violation -- build_funnel RAISES rather than silently defaulting it
    # to no_candidate_join (which would mask the malformed outcome).
    SignalOutcome(hypothesis=None, terminal="unattributed", reason=None),
    SignalOutcome(hypothesis=None, terminal="unattributed", reason=""),
    # an exclusion reason that belongs to the PER-HYPOTHESIS path must never reach here with a
    # None hypothesis.
    SignalOutcome(hypothesis=None, terminal="unattributed", reason="invalid_ohlc"),
    SignalOutcome(hypothesis=None, terminal="unattributed", reason="degenerate_risk"),
    # a malformed terminal (not "unattributed") on a None-hypothesis outcome.
    SignalOutcome(hypothesis=None, terminal="closed", reason=None),
    # writing-plans R4-M1: a VALID unattributed reason but a mismatched terminal on a
    # None-hypothesis outcome must still raise (ALL THREE conditions are required).
    SignalOutcome(hypothesis=None, terminal="closed", reason="no_candidate_join"),
    # writing-plans R4-M1: terminal=="unattributed" but a hypothesis IS set -> raise.
    SignalOutcome(hypothesis="A+ baseline", terminal="unattributed", reason="multi_match"),
    # writing-plans R4-M1: an unknown terminal on an ATTRIBUTED signal -> raise.
    SignalOutcome(hypothesis="A+ baseline", terminal="bogus", reason=None),
])
def test_build_funnel_raises_on_malformed_unattributed_outcome(bad):
    det = DetectionLevel(total_detections=1, collapsed_duplicate=0, unique_signals=1)
    with pytest.raises(ShadowExpectancyError):
        build_funnel(det, signal_outcomes=[bad])


@pytest.mark.parametrize("bad", [
    # writing-plans R5: an ATTRIBUTED terminal must carry its producer-contract reason; a wrong
    # reason -- especially an UNATTRIBUTED_REASONS reason on a hypothesis -- must RAISE, never be
    # silently counted under that hypothesis.
    SignalOutcome(hypothesis="A+ baseline", terminal="closed", reason="invalid_ohlc"),
    SignalOutcome(hypothesis="A+ baseline", terminal="open_at_horizon", reason="lifecycle"),
    SignalOutcome(hypothesis="A+ baseline", terminal="never_triggered", reason=None),
    SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason="no_candidate_join"),
    SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason="multi_match"),
    SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason=None),
])
def test_build_funnel_raises_on_malformed_attributed_outcome(bad):
    det = DetectionLevel(total_detections=1, collapsed_duplicate=0, unique_signals=1)
    with pytest.raises(ShadowExpectancyError):
        build_funnel(det, signal_outcomes=[bad])


def test_build_funnel_accepts_valid_attributed_exclusion_reasons():
    # The five post-attribution per-hypothesis `excluded` reasons are accepted + counted.
    det = DetectionLevel(total_detections=5, collapsed_duplicate=0, unique_signals=5)
    outs = [SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason=r)
            for r in ("invalid_ohlc", "degenerate_risk", "insufficient_forward_depth",
                      "missing_observations", "lifecycle")]
    f = build_funnel(det, signal_outcomes=outs)
    assert dict(f["per_hypothesis"]["A+ baseline"]["excluded"]) == {
        "invalid_ohlc": 1, "degenerate_risk": 1, "insufficient_forward_depth": 1,
        "missing_observations": 1, "lifecycle": 1}


def test_detection_reconciliation_from_REAL_collapse_output():
    # Codex M8: drive the detection-level reconciliation from the REAL collapser over an
    # actual multi-detection group, NOT a hand-built consistent object, so a C4 undercount
    # would surface. Three detections for one (run,ticker): a pivot-10 canonical, a duplicate
    # pivot-10, and a non-pivot-matching pivot-11 -- all sharing an identical frozen series +
    # trigger -> 1 unique signal + 2 collapsed.
    from dataclasses import dataclass

    @dataclass
    class _Det:
        detection_id: int
        pivot: float
        forward_series_key: tuple
        first_trigger_session: str | None

    series = (("2026-06-01", 9.6, 10.2, 9.5, 10.1),)
    dets = [_Det(5, 10.0, series, "2026-06-01"),
            _Det(2, 10.0, series, "2026-06-01"),
            _Det(9, 11.0, series, "2026-06-01")]
    res = collapse_detections(dets, candidate_pivot=10.0)
    assert res.exclusion_reason is None
    total_detections = len(dets)
    collapsed_duplicate = len(res.collapsed_ids)
    unique_signals = 1   # this one (run,ticker) group collapsed to a single canonical signal
    det = DetectionLevel(total_detections, collapsed_duplicate, unique_signals)
    f = build_funnel(det, signal_outcomes=[
        SignalOutcome(hypothesis="A+ baseline", terminal="closed", reason=None)])
    dl = f["detection_level"]
    # the C4 reconciliation: total == unique + collapsed (the group fully reconciles).
    assert (dl["unique_signals"] + dl["collapsed_duplicate_detection"]
            == dl["total_detections"] == 3)
    assert collapsed_duplicate == 2   # group_size - 1 (C4), NOT just the pivot-matching subset
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_funnel.py -q`. Expect `ModuleNotFoundError`.

- [ ] **Step: minimal implementation** — `research/harness/shadow_expectancy/funnel.py`:
```python
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from research.harness.shadow_expectancy.constants import (
    UNATTRIBUTED_REASONS, ATTRIBUTED_EXCLUDED_REASONS)
from research.harness.shadow_expectancy.exceptions import ShadowExpectancyError


@dataclass(frozen=True)
class DetectionLevel:
    total_detections: int
    collapsed_duplicate: int
    unique_signals: int


@dataclass(frozen=True)
class SignalOutcome:
    hypothesis: str | None   # None = a PRE-/NON-attribution unattributed state
    terminal: str            # 'closed'|'open_at_horizon'|'never_triggered'|'excluded'
                             #  |'unattributed'
    reason: str | None       # funnel reason for excluded/never_triggered/unattributed, else None


def build_funnel(detection: DetectionLevel, *, signal_outcomes) -> dict:
    # C-review M1 + R3-M1: ONE `unattributed` bucket whose value is a per-reason breakdown. The
    # six PRE-/NON-attribution reasons (no_candidate_join, matched_no_hypothesis, multi_match,
    # no_canonical_detection, inconsistent_detection_series, inconsistent_trigger_state) are
    # COUNTERS inside it -- matched_no_hypothesis and multi_match are reasons WITHIN
    # unattributed, NOT separate top-level buckets.
    unattributed: dict[str, int] = defaultdict(int)
    per_hyp: dict[str, dict] = {}

    def _blank():
        return {"closed": 0, "open_at_horizon": 0, "never_triggered": 0,
                "excluded": defaultdict(int)}

    for o in signal_outcomes:
        is_unattr_terminal = o.terminal == "unattributed"
        is_no_hypothesis = o.hypothesis is None
        if is_unattr_terminal or is_no_hypothesis:
            # A PRE-/NON-attribution state (Codex R4-m1 / writing-plans R4-M1): one of the six
            # UNATTRIBUTED_REASONS (no_candidate_join, matched_no_hypothesis, multi_match,
            # no_canonical_detection, inconsistent_detection_series, inconsistent_trigger_state)
            # -> a per-reason counter inside `unattributed`, never a hypothesis. (invalid_ohlc /
            # degenerate_risk on an ATTRIBUTED signal are per-hypothesis -- the branch below --
            # so they never reach here.)
            #
            # Defensive integrity (writing-plans R4-M1): a VALID unattributed outcome must
            # satisfy ALL THREE -- hypothesis is None AND terminal == "unattributed" AND reason in
            # UNATTRIBUTED_REASONS. ANY partial combination is a producer-contract violation and
            # RAISES (not silently counted): e.g. (hypothesis=None, terminal="closed",
            # reason="no_candidate_join") or (hypothesis="A+ baseline", terminal="unattributed",
            # reason="multi_match"). Unlike a bare `assert`, this is not stripped under -O.
            if not (is_unattr_terminal and is_no_hypothesis
                    and o.reason in UNATTRIBUTED_REASONS):
                raise ShadowExpectancyError(
                    "malformed unattributed outcome: require hypothesis is None AND "
                    "terminal=='unattributed' AND reason in UNATTRIBUTED_REASONS; "
                    f"got hypothesis={o.hypothesis!r} terminal={o.terminal!r} "
                    f"reason={o.reason!r}")
            unattributed[o.reason] += 1
            continue
        # Attributed branch: hypothesis is set AND terminal != "unattributed".
        # writing-plans R5: validate the reason PER terminal so an UNATTRIBUTED_REASONS reason (or
        # any wrong reason) can never be silently miscounted under a hypothesis. The producer
        # (run_harness) sets reason=None for closed/open_at_horizon, reason="never_triggered" for
        # never_triggered, and a post-attribution ATTRIBUTED_EXCLUDED_REASONS reason for excluded.
        card = per_hyp.setdefault(o.hypothesis, _blank())
        if o.terminal in ("closed", "open_at_horizon"):
            if o.reason is not None:
                raise ShadowExpectancyError(
                    f"attributed {o.terminal!r} outcome must have reason=None; got "
                    f"reason={o.reason!r} (hypothesis={o.hypothesis!r})")
            card[o.terminal] += 1
        elif o.terminal == "never_triggered":
            if o.reason != "never_triggered":
                raise ShadowExpectancyError(
                    "attributed never_triggered outcome must have reason=='never_triggered'; got "
                    f"reason={o.reason!r} (hypothesis={o.hypothesis!r})")
            card["never_triggered"] += 1
        elif o.terminal == "excluded":  # Codex M5: post-attribution per-hypothesis exclusion
            if o.reason not in ATTRIBUTED_EXCLUDED_REASONS:
                raise ShadowExpectancyError(
                    "attributed excluded outcome requires a post-attribution exclusion reason "
                    f"(one of {sorted(ATTRIBUTED_EXCLUDED_REASONS)}); got reason={o.reason!r} "
                    f"(hypothesis={o.hypothesis!r}) -- UNATTRIBUTED_REASONS are rejected here")
            card["excluded"][o.reason] += 1
        else:  # writing-plans R4-M1: an unknown terminal on an attributed signal is a contract violation
            raise ShadowExpectancyError(
                f"unknown terminal status {o.terminal!r} for attributed signal "
                f"hypothesis={o.hypothesis!r}")

    return {
        "detection_level": {
            "total_detections": detection.total_detections,
            "collapsed_duplicate_detection": detection.collapsed_duplicate,
            "unique_signals": detection.unique_signals,
        },
        # ONE bucket; its value is the per-reason breakdown (incl. matched_no_hypothesis +
        # multi_match).
        "unattributed": dict(unattributed),
        "per_hypothesis": {
            h: {**{k: v for k, v in c.items() if k != "excluded"},
                "excluded": dict(c["excluded"])}
            for h, c in per_hyp.items()
        },
    }
```

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_funnel.py -q`. Expect all passed.

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/funnel.py tests/research/shadow_expectancy/test_funnel.py && git commit -m "feat(research): shadow-expectancy two-level denominator funnel (7.1)"`

---

### Task 12: Output writers + ASCII guard (artifact dir)

**Files:**
- Create `research/harness/shadow_expectancy/output.py`
- Test `tests/research/shadow_expectancy/test_output.py`

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_output.py`:
```python
from __future__ import annotations

import json

import pytest

from research.harness.shadow_expectancy import output


def test_assert_ascii_rejects_non_ascii():
    with pytest.raises(UnicodeEncodeError):
        output._assert_ascii("em—dash")


def test_write_results_and_ledger_csv(tmp_path):
    rows = [{"ticker": "AAA", "hypothesis": "A+ baseline", "bucket": "aplus",
             "realistic_r": "1.50", "favorable_r": "1.50", "exit_reason": "initial_stop",
             "open_at_horizon": "False", "entry_bar_ambiguous": "False",
             "detection_date": "2026-05-29", "run_id": "1"}]
    p = tmp_path / "results.csv"
    output.write_results_csv(rows, p)
    assert "A+ baseline" in p.read_text(encoding="utf-8")


def test_write_per_session_legs_csv(tmp_path):
    rows = [{"ticker": "AAA", "hypothesis": "A+ baseline", "action": "exit",
             "qty": "50.0", "price": "10.60", "price_favorable": "11.00",
             "session": "2026-06-04"}]
    p = tmp_path / "per_session.csv"
    output.write_per_session_csv(rows, p)
    text = p.read_text(encoding="utf-8")
    assert "price_favorable" in text   # m3: both arms reconstructable from the ledger
    assert "11.00" in text


def test_write_summary_and_manifest(tmp_path):
    output.write_summary_md(["# Shadow-expectancy", "headline: H1 ..."], tmp_path / "s.md")
    output.write_manifest_json({"harness_version": "0.1.0"}, tmp_path / "m.json")
    m = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert m["l2_lock_preserved"] is True
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_output.py -q`. Expect `ModuleNotFoundError`.

- [ ] **Step: minimal implementation** — `research/harness/shadow_expectancy/output.py` (mirror the precedent exactly):
```python
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

RESULTS_HEADER = (
    "ticker", "detection_date", "run_id", "hypothesis", "bucket",
    "realistic_r", "favorable_r", "exit_reason", "open_at_horizon",
    "entry_bar_ambiguous",
)
PER_SESSION_HEADER = ("ticker", "hypothesis", "action", "qty", "price",
                      "price_favorable", "session")  # m3: both arms for terminal legs


def _assert_ascii(text: str) -> str:
    text.encode("ascii")  # spec section 8: ASCII-only (stricter than cp1252)
    return text


def _write_csv(header, rows, path: Path) -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(header), lineterminator="\n",
                            extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    Path(path).write_text(_assert_ascii(buf.getvalue()), encoding="utf-8")


def write_results_csv(rows, path: Path) -> None:
    _write_csv(RESULTS_HEADER, rows, path)


def write_per_session_csv(rows, path: Path) -> None:
    _write_csv(PER_SESSION_HEADER, rows, path)


def write_summary_md(lines: list[str], path: Path) -> None:
    Path(path).write_text(_assert_ascii("\n".join(lines) + "\n"), encoding="utf-8")


def write_manifest_json(manifest: dict, path: Path) -> None:
    payload = dict(manifest)
    payload.setdefault("l2_lock_preserved", True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    Path(path).write_text(_assert_ascii(text), encoding="utf-8")
```

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_output.py -q`. Expect all passed.

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/output.py tests/research/shadow_expectancy/test_output.py && git commit -m "feat(research): shadow-expectancy output writers + ASCII guard"`

---

### Task 13: Orchestrator `run.py` end-to-end + reproducibility (§8)

**Files:**
- Create `research/harness/shadow_expectancy/run.py`
- Test `tests/research/shadow_expectancy/test_run.py`

**Pipeline ORDER (Codex M5 + C-review M1/M4 + R3-M1):** per (run, ticker) group: **collapse/join → attribute → validate → simulate**. (1) collapse/join states (`no_candidate_join`, `no_canonical_detection` [candidate present but no detection pivot matches it; M4], `inconsistent_detection_series`, `inconsistent_trigger_state`) → the `unattributed` bucket as per-reason counters. (2) a joined candidate that attributes to ZERO hypotheses → the `matched_no_hypothesis` REASON WITHIN `unattributed` (a counter inside that one bucket, NOT a separate top-level bucket; M1; we never reach validate/simulate). (2b) a joined candidate that matches MORE THAN ONE hypothesis → the `multi_match` REASON WITHIN `unattributed` (R3-M1; defensive — the 4 seeded hypotheses are mutually exclusive so this is ~0 today, but emitting one outcome PER matched hypothesis would count the same signal in multiple per-hypothesis buckets and BREAK the reconciliation invariant; we exclude it here and never simulate). Exactly-one match flows on. (3) on an ATTRIBUTED (exactly-one-match) signal, a `validate_signal` failure (`invalid_ohlc`) or a `simulate` `degenerate_risk` routes to that matched hypothesis's `excluded[...]` (PER-HYPOTHESIS, NOT unattributed). All (1)+(2)+(2b) states are emitted as `SignalOutcome(hypothesis=None, terminal="unattributed", reason=...)`. **Reconciliation invariant (R3-M1, spec §7.1):** because each unique signal lands in EXACTLY ONE of {one unattributed reason, one per-hypothesis terminal status}, `Σ(unattributed reason counts) + Σ(per-hypothesis terminal-status counts) == unique_signals` holds exactly — asserted in `test_run.py` over an attributed-closed + attributed-open + unattributed + (synthetic) multi-match corpus. The simulator receives the FULL forward chain (no pre-truncation) so the post-horizon open is readable for the forced-exit scenario (M3); and `simulate` derives the mechanical stop from `entry_bar.low` (C1) — `candidate.initial_stop` is only sanity-validated.

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_run.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.harness.shadow_expectancy.run import run_harness
from tests.research.shadow_expectancy.testkit import (
    insert_candidate, insert_detection, insert_observation, insert_pipeline_run,
    make_db,
)


def _seed_one_aplus_winner(conn):
    # migration 0008 already seeded the active registry via make_db.
    eval_id = insert_candidate(conn, ticker="AAA", bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker="AAA", pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    # entry bar triggers (high >= pivot), then a stop-out.
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, det_id, "2026-06-02", o=8.5, h=8.6, l=8.0, c=8.2,
                       status="triggered_open")
    conn.commit()


def test_run_harness_emits_four_artifacts(tmp_path):
    conn = make_db(tmp_path)        # creates + migrates tmp_path/t.db
    _seed_one_aplus_winner(conn)    # writes candidate/detection/observations into it
    out = tmp_path / "out"
    results, per_session, summary, manifest = run_harness(
        db_path=tmp_path / "t.db", output_dir=out, source="pipeline")
    for p in (results, per_session, summary, manifest):
        assert Path(p).exists()
    m = json.loads(Path(manifest).read_text(encoding="utf-8"))
    assert m["l2_lock_preserved"] is True
    summary_text = Path(summary).read_text(encoding="utf-8")
    assert "A+ baseline" in summary_text
    # M2 (spec 7.1): the unattributed reason breakdown is surfaced in summary.md. EVERY
    # canonical reason label renders (0 when absent) so the funnel's pre-/non-attribution
    # losses are externally visible, not buried in the manifest.
    assert "## Unattributed signals" in summary_text
    for reason in ("no_candidate_join", "matched_no_hypothesis", "multi_match",
                   "no_canonical_detection", "inconsistent_detection_series",
                   "inconsistent_trigger_state"):
        assert f"{reason}=" in summary_text


def test_reproducible_canonical_manifest(tmp_path):
    conn = make_db(tmp_path)
    _seed_one_aplus_winner(conn)
    out = tmp_path / "out"
    _, _, _, m1 = run_harness(db_path=tmp_path / "t.db", output_dir=out, source="pipeline")
    _, _, _, m2 = run_harness(db_path=tmp_path / "t.db", output_dir=out, source="pipeline")

    def _canonical(p):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        for k in ("run_id", "started_iso_utc", "finished_iso_utc"):
            d.pop(k, None)
        return json.dumps(d, sort_keys=True)

    assert _canonical(m1) == _canonical(m2)


def _seed_attributed_open_runner(conn):
    # A second aplus signal that TRIGGERS then stays OPEN through a short horizon (no stop
    # hit on its single forward bar). Attributes to H1 (A+ baseline) via the real matcher.
    eval_id = insert_candidate(conn, ticker="BBB", bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker="BBB", pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    # forward bar: low 10.1 > entry_bar.low (9.6) -> never stops -> open at horizon=1.
    insert_observation(conn, det_id, "2026-06-02", o=10.3, h=10.6, l=10.1, c=10.5,
                       status="triggered_open")
    conn.commit()


def _seed_no_candidate_join(conn):
    # A detection for CCC under a pipeline_run whose eval_run has NO CCC candidate row ->
    # resolve_candidate returns None -> collapse emits `no_candidate_join` (unattributed).
    eval_id = insert_candidate(conn, ticker="OTHER", bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker="CCC", pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    conn.commit()


def _seed_multi_match_signal(conn):
    # A real aplus signal MMM; the matcher is MONKEYPATCHED in the test to return TWO
    # hypotheses for MMM (the 4 seeded hypotheses are mutually exclusive, so a real
    # multi-match is impossible -- it MUST be synthesized to exercise the guard).
    eval_id = insert_candidate(conn, ticker="MMM", bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker="MMM", pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, det_id, "2026-06-02", o=8.5, h=8.6, l=8.0, c=8.2,
                       status="triggered_open")
    conn.commit()


def test_reconciliation_invariant_over_real_corpus(tmp_path, monkeypatch):
    # R3-M1 (spec 7.1): Sum(unattributed reason counts) + Sum(per-hypothesis terminal-status
    # counts) == unique_signals, asserted over a REAL run_harness corpus that includes an
    # attributed-CLOSED signal (AAA stops out -> H1.closed), an attributed-OPEN signal
    # (BBB -> H1.open_at_horizon at horizon=1), an UNATTRIBUTED signal (CCC -> no_candidate_join),
    # and a (synthetic) MULTI-MATCH signal (MMM, matcher monkeypatched to return 2 hypotheses).
    import research.harness.shadow_expectancy.run as run_mod

    conn = make_db(tmp_path)
    _seed_one_aplus_winner(conn)        # AAA -> H1, stops out -> closed
    _seed_attributed_open_runner(conn)  # BBB -> H1, open at horizon
    _seed_no_candidate_join(conn)       # CCC -> unattributed: no_candidate_join
    _seed_multi_match_signal(conn)      # MMM -> (patched) 2 hypotheses -> multi_match

    real_attribute = run_mod.attribute_hypotheses

    def _patched(candidate, *, registry):
        if candidate.ticker == "MMM":
            # synthesize a non-exclusive (>1) match the seeded registry can never produce.
            return ["A+ baseline", "Sub-A+ VCP-not-formed"]
        return real_attribute(candidate, registry=registry)

    monkeypatch.setattr(run_mod, "attribute_hypotheses", _patched)

    out = tmp_path / "out"
    # horizon=1 so BBB (one clean forward bar) lands open-at-horizon; AAA still stops on
    # its single forward bar (low 8.0 <= entry_bar.low 9.6).
    _, _, summary, manifest = run_mod.run_harness(
        db_path=tmp_path / "t.db", output_dir=out, source="pipeline", horizon_sessions=1)
    funnel = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    # M2: the non-zero unattributed reasons render in summary.md with their counts.
    summary_text = Path(summary).read_text(encoding="utf-8")
    assert "no_candidate_join=1" in summary_text
    assert "multi_match=1" in summary_text

    unattributed_total = sum(funnel["unattributed"].values())
    per_hyp_terminal_total = 0
    for card in funnel["per_hypothesis"].values():
        per_hyp_terminal_total += (
            card["closed"] + card["open_at_horizon"] + card["never_triggered"]
            + sum(card["excluded"].values()))
    unique_signals = funnel["detection_level"]["unique_signals"]

    # the corpus exercises every branch of the invariant.
    assert funnel["unattributed"]["no_candidate_join"] == 1
    assert funnel["unattributed"]["multi_match"] == 1   # MMM excluded, NOT counted in 2 hyps
    h1 = funnel["per_hypothesis"]["A+ baseline"]
    assert h1["closed"] == 1 and h1["open_at_horizon"] == 1
    # MMM did NOT contribute to any per-hypothesis bucket (it was excluded as multi_match).
    assert "Sub-A+ VCP-not-formed" not in funnel["per_hypothesis"]
    # THE INVARIANT, exact:
    assert unattributed_total + per_hyp_terminal_total == unique_signals == 4
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_run.py -q`. Expect `ModuleNotFoundError`.

- [ ] **Step: minimal implementation** — `research/harness/shadow_expectancy/run.py` (orchestrate the modules; build `RawSignal` collapse-views from per-detection observation chains; thread funnel + scorecard; write artifacts). Key real code:
```python
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from research.harness.shadow_expectancy import constants as C
from research.harness.shadow_expectancy import io, output
from research.harness.shadow_expectancy.attribution import attribute_hypotheses
from research.harness.shadow_expectancy.collapse import collapse_detections
from research.harness.shadow_expectancy.funnel import (
    DetectionLevel, SignalOutcome, build_funnel,
)
from research.harness.shadow_expectancy.scorecard import (
    ShadowTrade, build_hypothesis_scorecard,
)
from research.harness.shadow_expectancy.simulator import SimParams, simulate
from research.harness.shadow_expectancy.validate import validate_signal
from swing.data.repos.hypothesis import list_hypotheses


@dataclass
class _DetView:
    detection_id: int
    pivot: float
    forward_series_key: tuple
    first_trigger_session: str | None


def _entry_and_forward(chain):
    """Return (entry_obs, forward_obs[]) -- entry = first triggered_open+entry_fired."""
    entry_idx = next((i for i, o in enumerate(chain)
                      if o.status == "triggered_open"
                      and o.status_change_event == "entry_fired"), None)
    if entry_idx is None:
        return None, []
    return chain[entry_idx], chain[entry_idx + 1:]


def _series_key(chain):
    return tuple((o.observation_date,) + _ohlc_tuple(o.ohlc_today_json) for o in chain)


def _ohlc_tuple(j):
    import json
    d = json.loads(j)
    return (d["open"], d["high"], d["low"], d["close"])


def run_harness(*, db_path, output_dir, source=C.SOURCE,
                partial_session_n=C.PARTIAL_SESSION_N,
                breakeven_r=C.BREAKEVEN_R_TRIGGER,
                horizon_sessions=C.HORIZON_SESSIONS, only=None):
    conn = io.open_ro(db_path)
    registry = list_hypotheses(conn, status_filter="active")
    detections = io.list_pipeline_detections(conn, source=source)

    # group detections by (pipeline_run_id, ticker).
    groups: dict[tuple, list] = defaultdict(list)
    for d in detections:
        groups[(d.pipeline_run_id, d.ticker)].append(d)

    iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(output_dir) / f"shadow-expectancy-{iso}"
    run_dir.mkdir(parents=True, exist_ok=True)

    total_detections = len(detections)
    collapsed_duplicate = 0
    unique_signals = 0
    signal_outcomes: list[SignalOutcome] = []
    shadow_trades: list[ShadowTrade] = []
    results_rows: list[dict] = []
    ledger_rows: list[dict] = []

    params = SimParams(
        initial_shares=C.INITIAL_SHARES, partial_session_n=partial_session_n,
        partial_pct=C.PARTIAL_PCT, breakeven_r_trigger=breakeven_r,
        maturity_fast_ma_r=C.MATURITY_FAST_MA_R, ma_fast_period=C.MA_FAST_PERIOD,
        ma_slow_period=C.MA_SLOW_PERIOD, horizon_sessions=horizon_sessions)

    for (pipeline_run_id, ticker), dets in sorted(groups.items(),
                                                  key=lambda kv: (kv[0][0] or -1, kv[0][1])):
        if only and ticker not in only:
            continue
        unique_signals += 1
        candidate = io.resolve_candidate(conn, pipeline_run_id=pipeline_run_id, ticker=ticker)
        # build detection views (chain + trigger session) for collapse.
        views = []
        chains = {}
        for d in dets:
            chain = io.read_observation_chain(conn, d.detection_id)
            chains[d.detection_id] = chain
            entry, _fwd = _entry_and_forward(chain)
            import json
            pivot = json.loads(d.structural_anchors_json)["evidence"].get("pivot_price")
            views.append(_DetView(d.detection_id, pivot, _series_key(chain),
                                  entry.observation_date if entry else None))
        cand_pivot = candidate.pivot if candidate is not None else None
        res = collapse_detections(views, candidate_pivot=cand_pivot)
        collapsed_duplicate += len(res.collapsed_ids)
        if res.exclusion_reason is not None:
            # JOIN/COLLAPSE-level (pre-attribution) state -> the `unattributed` bucket as a
            # per-reason counter (C-review M1/M4): no_candidate_join / no_canonical_detection
            # (candidate present, no pivot match) / inconsistent_detection_series /
            # inconsistent_trigger_state.
            signal_outcomes.append(
                SignalOutcome(None, "unattributed", res.exclusion_reason))
            continue

        # ORDER (Codex M5): join (done) -> ATTRIBUTE -> validate -> simulate.
        hyps = attribute_hypotheses(candidate, registry=registry)
        if not hyps:
            # C-review M1: candidate joined + present but matched zero hypotheses. This is the
            # `matched_no_hypothesis` REASON WITHIN the `unattributed` bucket (NOT a separate
            # top-level bucket), distinct from no_candidate_join. Excluded from per-hypothesis
            # means.
            signal_outcomes.append(
                SignalOutcome(None, "unattributed", "matched_no_hypothesis"))
            continue
        if len(hyps) > 1:
            # R3-M1 (reconciliation safety): the 4 seeded hypotheses are mutually exclusive by
            # their exact-miss-set definitions, so this is ~0 today -- but a future non-exclusive
            # hypothesis would otherwise emit ONE outcome PER matched hypothesis, counting the
            # SAME signal in multiple per-hypothesis terminal buckets and BREAKING the
            # reconciliation invariant (Sum(unattributed) + Sum(per-hyp terminal-status) ==
            # unique_signals) with no test failing. Defensively exclude the multi-matching signal
            # under the `multi_match` REASON WITHIN the single `unattributed` bucket; do NOT
            # simulate or emit per-hypothesis outcomes. Exactly-one match flows on below.
            signal_outcomes.append(
                SignalOutcome(None, "unattributed", "multi_match"))
            continue

        chain = chains[res.canonical.detection_id]
        entry, forward = _entry_and_forward(chain)
        if entry is None:
            for h in hyps:
                signal_outcomes.append(
                    SignalOutcome(h, "never_triggered", "never_triggered"))
            continue
        entry_bar = io.parse_bar(entry.ohlc_today_json, session=entry.observation_date)
        # FULL forward chain (NOT pre-truncated) so the simulator can read the post-horizon
        # open for the forced-exit scenario (Codex M3).
        forward_bars = [io.parse_bar(o.ohlc_today_json, session=o.observation_date)
                        for o in forward]

        # validate: candidate-level SANITY (pivot/initial_stop finite etc.; C1 -- the trade
        # stop is entry_bar.low, NOT candidate.initial_stop) + every bar on the path. A
        # failure on this ATTRIBUTED signal routes PER-HYPOTHESIS (Codex M5), not unattributed.
        reason = validate_signal(pivot=candidate.pivot, initial_stop=candidate.initial_stop,
                                 bars=[entry_bar, *forward_bars])
        if reason is not None:
            for h in hyps:
                signal_outcomes.append(SignalOutcome(h, "excluded", reason))
            continue

        # C1: simulate derives the mechanical stop from entry_bar.low internally.
        sim = simulate(pivot=candidate.pivot, entry_bar=entry_bar,
                       forward_bars=forward_bars, params=params)
        if sim.degenerate:
            for h in hyps:
                signal_outcomes.append(SignalOutcome(h, "excluded", "degenerate_risk"))
            continue
        terminal = "open_at_horizon" if sim.open_at_horizon else "closed"
        for h in hyps:
            signal_outcomes.append(SignalOutcome(h, terminal, None))
            shadow_trades.append(ShadowTrade(
                hypothesis=h, triggered=True,
                open_at_horizon=sim.open_at_horizon, realized_r=sim.realized_r,
                entry_bar_ambiguous=sim.entry_bar_ambiguous,
                holding_sessions=sim.holding_sessions,
                censoring_scenarios=sim.censoring_scenarios))
            results_rows.append({
                "ticker": ticker, "detection_date": res.canonical.detection_id and
                next(d.detection_date for d in dets
                     if d.detection_id == res.canonical.detection_id),
                "run_id": pipeline_run_id, "hypothesis": h,
                "bucket": candidate.bucket,
                "realistic_r": f"{sim.realized_r['realistic']:.4f}",
                "favorable_r": f"{sim.realized_r['favorable_reprice']:.4f}",
                "exit_reason": sim.exit_reason,
                "open_at_horizon": str(sim.open_at_horizon),
                "entry_bar_ambiguous": str(sim.entry_bar_ambiguous)})
            for leg in sim.legs:
                # m3: record BOTH arm fills. Non-terminal legs (partials) are arm-independent
                # (price_favorable == price); the terminal exit leg carries the favorable fill
                # from sim.terminal_fill so the [realistic, favorable] bracket reconstructs.
                fav = (sim.terminal_fill["favorable_reprice"]
                       if (sim.terminal_fill is not None and leg.action == "exit")
                       else leg.price)
                ledger_rows.append({"ticker": ticker, "hypothesis": h,
                                    "action": leg.action, "qty": f"{leg.qty:.4f}",
                                    "price": f"{leg.price:.4f}",
                                    "price_favorable": f"{fav:.4f}",
                                    "session": leg.session})

    funnel = build_funnel(
        DetectionLevel(total_detections, collapsed_duplicate, unique_signals),
        signal_outcomes=signal_outcomes)
    scorecard = build_hypothesis_scorecard(
        shadow_trades, sample_floor_mean=C.SAMPLE_FLOOR_MEAN,
        sample_floor_rate=C.SAMPLE_FLOOR_RATE, profit_factor_floor=C.PROFIT_FACTOR_FLOOR)

    results_path = run_dir / "results.csv"
    per_session_path = run_dir / "per_session.csv"
    summary_path = run_dir / "summary.md"
    manifest_path = run_dir / "manifest.json"
    output.write_results_csv(results_rows, results_path)
    output.write_per_session_csv(ledger_rows, per_session_path)
    output.write_summary_md(_summary_lines(funnel, scorecard), summary_path)
    output.write_manifest_json({
        "harness_version": C.HARNESS_VERSION, "source": source,
        "params": {"partial_session_n": partial_session_n, "breakeven_r": breakeven_r,
                   "horizon_sessions": horizon_sessions,
                   "ma_staging": [C.MA_FAST_PERIOD, C.MA_SLOW_PERIOD]},
        "funnel": funnel, "scorecard": scorecard,
        "started_iso_utc": iso, "l2_lock_preserved": True,
    }, manifest_path)
    conn.close()
    return results_path, per_session_path, summary_path, manifest_path


def _summary_lines(funnel, scorecard) -> list[str]:
    lines = ["# Shadow-expectancy engine - summary", "",
             "Mechanical-ruleset SHADOW evidence (NOT live hand-traded counts; spec 1).", ""]
    lines.append("## Denominator funnel (detection-level)")
    dl = funnel["detection_level"]
    lines.append(f"total_detections={dl['total_detections']} "
                 f"collapsed_duplicate={dl['collapsed_duplicate_detection']} "
                 f"unique_signals={dl['unique_signals']}")
    lines.append("")
    # M2 (spec 7.1): surface the `unattributed` reason breakdown in summary.md (not just the
    # manifest), so the denominator funnel's pre-/non-attribution losses are externally
    # visible. Emit EVERY reason in the canonical UNATTRIBUTED_REASONS order (0 when absent)
    # so the section shape is stable across runs and a missing-reason regression is visible.
    lines.append("## Unattributed signals (pre-/non-attribution; spec 7.1)")
    unattributed = funnel["unattributed"]
    for reason in C.UNATTRIBUTED_REASONS:
        lines.append(f"  {reason}={unattributed.get(reason, 0)}")
    lines.append(f"  total_unattributed={sum(unattributed.values())}")
    lines.append("")
    for hyp, card in sorted(scorecard.items()):
        lines.append(f"## {hyp}")
        # Headline = realistic-arm closed-only expectancy (no MTM leak; C3), explicitly labeled.
        co = card["scenarios"]["closed_only"]
        flag = " [SUPPRESSED n<floor]" if co["suppressed"] else ""
        lines.append(f"HEADLINE realistic closed-only mean R="
                     f"{card['headline_realistic_closed_only']:.3f} "
                     f"(n={co['n']}){flag}")
        # The four censoring scenarios, both arms (realistic / favorable_reprice).
        for sc_name in ("closed_only", "mtm_at_horizon",
                        "forced_exit_at_horizon_open", "stop_level_adverse"):
            s = card["scenarios"][sc_name]
            lines.append(f"  {sc_name}: realistic={s['realistic']:.3f} "
                         f"favorable={s['favorable_reprice']:.3f} (n={s['n']})")
        wr = card["win_rate"]
        lines.append(f"win rate (closed-only) {wr['k']}/{wr['n']}")
        ps = card["per_signal_expectancy"]
        tr = card["trigger_rate"]
        lines.append(f"trigger rate {tr['triggered']}/{tr['signals']}; "
                     f"per-signal expectancy [realistic]={ps['realistic']:.3f}")
        lines.append("")
    return lines


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="shadow-expectancy")
    p.add_argument("--db", dest="db_path", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("exports/research"))
    p.add_argument("--source", type=str, default=C.SOURCE)
    p.add_argument("--partial-session-n", type=int, default=C.PARTIAL_SESSION_N)
    p.add_argument("--breakeven-r", type=float, default=C.BREAKEVEN_R_TRIGGER)
    p.add_argument("--horizon-sessions", type=int, default=C.HORIZON_SESSIONS)
    p.add_argument("--only", type=str, default=None)
    a = p.parse_args(argv)
    only = tuple(s.strip() for s in a.only.split(",") if s.strip()) if a.only else None
    results, per_session, summary, manifest = run_harness(
        db_path=a.db_path, output_dir=a.output_dir, source=a.source,
        partial_session_n=a.partial_session_n, breakeven_r=a.breakeven_r,
        horizon_sessions=a.horizon_sessions, only=only)
    print(f"results.csv:     {results}")
    print(f"per_session.csv: {per_session}")
    print(f"summary.md:      {summary}")
    print(f"manifest.json:   {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
  NOTE during implementation: the reproducibility test pops `started_iso_utc`/`finished_iso_utc`/`run_id`; ensure the manifest's `funnel`/`scorecard` carry NO timestamps so the canonical payload is stable (spec §8). If a `defaultdict` leaks into JSON, cast to `dict` (the funnel already does).

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_run.py -q`. Expect all three passed (four-artifacts, reproducible-manifest, reconciliation-invariant).

- [ ] **Step: commit** — `git add research/harness/shadow_expectancy/run.py tests/research/shadow_expectancy/test_run.py && git commit -m "feat(research): shadow-expectancy orchestrator + reproducibility + reconciliation invariant (8/7.1)"`

---

### Task 14: L2-lock import-safety test

**Files:**
- Test `tests/research/shadow_expectancy/test_l2_lock.py`

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_l2_lock.py` (mirror the HARDENED precedent; include `wilson_ci`'s `swing.metrics.honesty` is ALLOWED — only the four forbidden modules are banned):
```python
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import research.harness.shadow_expectancy as pkg

_FORBIDDEN = (
    "yfinance", "schwabdev", "swing.integrations.schwab", "swing.data.ohlcv_archive",
)
_EVALUATOR_MODULES = (
    "constants", "exceptions", "io", "validate", "collapse", "attribution",
    "bracket", "simulator", "scorecard", "funnel", "output", "run",
)


class _NoImportSentinel:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, item):
        raise AssertionError(f"L2 LOCK violated: forbidden module {self._name!r} imported")


def test_evaluator_modules_do_not_import_forbidden(monkeypatch):
    for name in list(sys.modules):
        if name.startswith("research.harness.shadow_expectancy") or name in _FORBIDDEN:
            monkeypatch.delitem(sys.modules, name, raising=False)
    for forbidden in _FORBIDDEN:
        monkeypatch.setitem(sys.modules, forbidden, _NoImportSentinel(forbidden))
    for mod in _EVALUATOR_MODULES:
        importlib.import_module(f"research.harness.shadow_expectancy.{mod}")
    for forbidden in _FORBIDDEN:
        assert isinstance(sys.modules.get(forbidden), _NoImportSentinel), \
            f"L2 LOCK: {forbidden} was replaced by a real import"


def test_evaluator_sources_contain_no_forbidden_import_lines():
    pkg_dir = Path(pkg.__file__).parent
    banned = (
        "import yfinance", "from yfinance", "import schwabdev", "from schwabdev",
        "from swing.integrations.schwab", "swing.integrations.schwab.",
        "from swing.data.ohlcv_archive", "swing.data.ohlcv_archive.",
        "import swing.data.ohlcv_archive",
    )
    for mod in _EVALUATOR_MODULES:
        src = (pkg_dir / f"{mod}.py").read_text(encoding="utf-8")
        for line in src.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            for token in banned:
                assert token not in stripped, f"{mod}.py imports forbidden: {stripped!r}"
```

- [ ] **Step: run it, expect FAIL THEN PASS** — `python -m pytest tests/research/shadow_expectancy/test_l2_lock.py -q`. If any module imports a forbidden module, it FAILS first; fix the offending import (the harness should import only `swing.data.repos.*`, `swing.data.models`, `swing.recommendations.hypothesis`, `swing.trades.derived_metrics`, `swing.metrics.honesty`, `swing.config` — none of which transitively pull a forbidden module in import-safe mode). Expect PASS once clean.

- [ ] **Step: commit** — `git add tests/research/shadow_expectancy/test_l2_lock.py && git commit -m "test(research): shadow-expectancy L2-lock import-safety guard"`

---

### Task 15: CLI registration `swing diagnose shadow-expectancy`

**Files:**
- Modify `swing/cli.py`
- Test `tests/research/shadow_expectancy/test_cli.py`

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_cli.py`:
```python
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main


def test_command_is_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["diagnose", "shadow-expectancy", "--help"])
    assert result.exit_code == 0
    assert "--db" in result.output
    assert "--source" in result.output


def test_missing_db_is_friendly_error(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["diagnose", "shadow-expectancy", "--db",
                                  str(tmp_path / "nope.db"), "--output-dir", str(tmp_path)])
    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "Traceback" not in result.output


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="powershell.exe absent")
def test_cli_stdout_is_ascii_through_powershell(tmp_path):
    # Build a minimal real DB via the harness testkit, then run through the OS encoder.
    # make_db runs migration 0008 which seeds the active hypothesis registry.
    from tests.research.shadow_expectancy.testkit import make_db
    make_db(tmp_path)
    out = tmp_path / "out"
    cmd = (
        f"{sys.executable} -m research.harness.shadow_expectancy.run "
        f"--db {tmp_path / 't.db'} --output-dir {out}"
    )
    proc = subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True,
                          cwd=str(Path(__file__).resolve().parents[3]))
    assert "UnicodeEncodeError" not in proc.stderr
    assert proc.returncode == 0, proc.stderr
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_cli.py -q`. Expect `test_command_is_registered` FAIL (`No such command 'shadow-expectancy'`).

- [ ] **Step: minimal implementation** — add to `swing/cli.py` after `diagnose_pattern_cohort_detect` (use the `_validate_diagnose_db_path` precedent + ValueError→ClickException + deferred import):
```python
@diagnose_group.command("shadow-expectancy")
@click.option("--db", "db_path", required=True, type=click.Path(path_type=Path))
@click.option("--output-dir", "output_dir", type=click.Path(path_type=Path),
              default=Path("exports/research"), show_default=True)
@click.option("--source", type=str, default="pipeline", show_default=True,
              help="temporal-log detection source filter")
@click.option("--partial-session-n", type=int, default=3, show_default=True)
@click.option("--breakeven-r", type=float, default=1.0, show_default=True)
@click.option("--horizon-sessions", type=int, default=126, show_default=True)
@click.option("--only", type=str, default=None, help="Comma-separated ticker filter.")
def diagnose_shadow_expectancy(db_path, output_dir, source, partial_session_n,
                               breakeven_r, horizon_sessions, only):
    """Mechanical shadow-expectancy engine over the frozen v22 temporal log.

    Read-only: forward-walks every emitted signal through one fixed ruleset to a
    realized R-multiple, accumulating per-hypothesis expectancy evidence. Writes a
    per-run artifact (funnel + four-scenario scorecard + ledger + manifest). NOT an
    operator trading surface; never co-mingled with live hand-traded counts."""
    _validate_diagnose_db_path(db_path)
    from research.harness.shadow_expectancy.run import run_harness  # deferred import

    only_tuple = tuple(s.strip() for s in only.split(",") if s.strip()) if only else None
    try:
        results, per_session, summary, manifest = run_harness(
            db_path=db_path, output_dir=output_dir, source=source,
            partial_session_n=partial_session_n, breakeven_r=breakeven_r,
            horizon_sessions=horizon_sessions, only=only_tuple)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    except sqlite3.OperationalError as exc:
        raise click.ClickException(f"Database error reading {db_path}: {exc}") from exc
    click.echo(f"results.csv:     {results}")
    click.echo(f"per_session.csv: {per_session}")
    click.echo(f"summary.md:      {summary}")
    click.echo(f"manifest.json:   {manifest}")
```

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_cli.py -q`. Expect all passed.

- [ ] **Step: commit** — `git add swing/cli.py tests/research/shadow_expectancy/test_cli.py && git commit -m "feat(cli): register swing diagnose shadow-expectancy (the only swing/ change; L2-light)"`

---

### Task 16: `.gitignore` artifact allowlist + study + method-record docs

**Files:**
- Modify `.gitignore`
- Create `research/studies/2026-06-09-shadow-expectancy-engine.md`
- Create `research/method-records/shadow-expectancy-engine.md`
- Test `tests/research/shadow_expectancy/test_study_doc.py`

- [ ] **Step: write failing test** — `tests/research/shadow_expectancy/test_study_doc.py`:
```python
from __future__ import annotations

from pathlib import Path

_STUDY = Path("research/studies/2026-06-09-shadow-expectancy-engine.md")
_METHOD = Path("research/method-records/shadow-expectancy-engine.md")


def test_study_doc_exists_with_required_sections():
    assert _STUDY.exists()
    text = _STUDY.read_text(encoding="utf-8")
    for heading in ("## Question", "## Null hypothesis", "## Methodology",
                    "## Results", "## Limitations", "## Conclusion"):
        assert heading in text, f"study missing {heading!r}"
    assert "../method-records/shadow-expectancy-engine.md" in text
    assert "mechanical-ruleset shadow evidence" in text.lower()
    text.encode("ascii")  # ASCII-only (spec section 8)


def test_method_record_exists():
    assert _METHOD.exists()
    _METHOD.read_text(encoding="utf-8").encode("ascii")


def test_gitignore_allowlists_artifact_dir():
    gi = Path(".gitignore").read_text(encoding="utf-8")
    assert "!exports/research/shadow-expectancy-*" in gi
    assert "!exports/research/shadow-expectancy-*/summary.md" in gi
    assert "!exports/research/shadow-expectancy-*/manifest.json" in gi
    assert "!exports/research/shadow-expectancy-*/results.csv" in gi
    assert "!exports/research/shadow-expectancy-*/per_session.csv" in gi
```

- [ ] **Step: run it, expect FAIL** — `python -m pytest tests/research/shadow_expectancy/test_study_doc.py -q`. Expect FAIL (docs + gitignore entries absent).

- [ ] **Step: minimal implementation** —
  - Append to `.gitignore` (after the primary-base-recall block, ~line 116):
```
# Shadow-expectancy engine harness outputs: keep summary/manifest/results/per_session.
!exports/research/shadow-expectancy-*
exports/research/shadow-expectancy-*/*
!exports/research/shadow-expectancy-*/summary.md
!exports/research/shadow-expectancy-*/manifest.json
!exports/research/shadow-expectancy-*/results.csv
!exports/research/shadow-expectancy-*/per_session.csv
```
  - `research/studies/2026-06-09-shadow-expectancy-engine.md` — ASCII-only, with the six required headings + the relative link `../method-records/shadow-expectancy-engine.md` + the explicit phrase "mechanical-ruleset shadow evidence" + the headline framing (H1 triggered-trade count and realistic four-scenario expectancy; the engine accelerates H1 evidence relative to hand-trading; favorable-reprice is a non-executable upper bound). Reuse the `2026-06-09-minervini-primary-base-recall.md` study layout.
  - `research/method-records/shadow-expectancy-engine.md` — ASCII-only, the V2.1 §IV.B minimum field list (question, data substrate = v22 temporal log, ruleset = Core+Day-3 partial, hypothesis registry version/hash, the four censoring scenarios, the realistic vs favorable bracket, reproducibility scope). Reuse the `_template.md` field set.

- [ ] **Step: run, expect PASS** — `python -m pytest tests/research/shadow_expectancy/test_study_doc.py -q`. Expect all passed.

- [ ] **Step: commit** — `git add .gitignore research/studies/2026-06-09-shadow-expectancy-engine.md research/method-records/shadow-expectancy-engine.md tests/research/shadow_expectancy/test_study_doc.py && git commit -m "docs(research): shadow-expectancy study + method-record + gitignore artifact allowlist"`

---

### Task 17: Bracket-bound invariant + full fast-suite green

**Files:**
- Modify `tests/research/shadow_expectancy/test_simulator.py` (the §9 bracket-bound + identical-denominator invariant over a parametrized set of walks)

- [ ] **Step: write failing test** — append to `test_simulator.py`:
```python
@pytest.mark.parametrize("stop,fwd_open,fwd_low", [
    (9.0, 8.5, 8.0),   # gap-down stop -> favorable -1R, realistic < -1R
    (9.0, 9.4, 8.9),   # no-gap stop -> equal arms (both at stop)
])
def test_bracket_bound_favorable_ge_realistic_fixed_denominator(stop, fwd_open, fwd_low):
    # C1: the mechanical stop is entry_bar.low, so set the entry bar's low to the
    # parametrized stop level (NOT a candidate input). entry_fill = max(pivot, open) = 10.0.
    entry_bar = Bar("2026-06-01", 10.0, 10.4, stop, 10.2)   # entry_bar.low == stop
    fwd = [Bar("2026-06-02", fwd_open, fwd_open + 0.3, fwd_low, fwd_open + 0.1)]
    res = simulate(pivot=10.0, entry_bar=entry_bar, forward_bars=fwd,
                   params=_params(horizon_sessions=1))
    assert res.initial_stop == stop
    assert res.realized_r["favorable_reprice"] >= res.realized_r["realistic"]
    # identical denominator across arms: risk_per_share is single-entry-fill derived.
    assert res.risk_per_share == 10.0 - stop  # entry_fill == max(pivot, open) == 10.0
```

- [ ] **Step: run it, expect PASS (already satisfied by Tasks 6-9)** — `python -m pytest tests/research/shadow_expectancy/test_simulator.py -q`. The invariant should hold; if a numeric mismatches, the implementation has a bracket bug — fix it (do NOT weaken the assertion).

- [ ] **Step: run the FULL fast suite** — `python -m pytest -m "not slow" -q`. Confirm green (READ the actual pass count — do not assume; baseline ~7376 + the new harness tests, ZERO failures). If any pre-existing test regresses, investigate before proceeding.

- [ ] **Step: commit** — `git add tests/research/shadow_expectancy/test_simulator.py && git commit -m "test(research): shadow-expectancy bracket-bound invariant (favorable >= realistic, fixed denominator)"`

---

## Final verification checklist (before declaring complete)

- [ ] `python -m pytest -m "not slow" -q` green on the merged head (READ the count; never carry a branch count forward).
- [ ] `ruff check swing/ research/harness/shadow_expectancy/` clean.
- [ ] `swing diagnose shadow-expectancy --help` lists `--db --source --partial-session-n --breakeven-r --horizon-sessions --only`.
- [ ] L2 LOCK: `tests/research/shadow_expectancy/test_l2_lock.py` green; only `swing/cli.py` changed in `swing/`; NO migration; schema v24 holds.
- [ ] Manifest `l2_lock_preserved: true`; artifacts under `exports/research/shadow-expectancy-<ISO>/`; all output ASCII.
- [ ] Every commit conventional, NO Claude co-author footer, NO `--no-verify`, NO amend.

---

## Spec-decision honor map (D1-D12)

- D1 (v22 read-only) → Tasks 3, 13 (`io.open_ro` mode=ro; no writes).
- D2 (single entry fill, exit-only bracket, FIXED denominator) → Tasks 6, 7, 8 (`_entry_fill=max(pivot,open)`; `_r_for_legs` single `rps*initial_shares` denominator [C2]; Task 17 invariant).
- D3/D4 (Core + Day-3 partial) → Task 8.
- D5 (126-session horizon, report effective) → Tasks 7, 9, 13 (manifest params; FULL forward chain passed so the post-horizon open is readable [M3]).
- D6 (MECHANICAL initial stop = entry_bar.low [C1]; `degenerate_risk` = `entry_fill <= entry_bar.low`) → Tasks 7, 8 (derived in `simulate`, NOT a candidate input; candidate `pivot`/`initial_stop` are SANITY-validated in Task 2 only).
- D7 (MA from frozen forward closes) → Task 9 (`_sma` over `forward_bars` closes only).
- D8 (no schema; per-run artifact) → Tasks 12, 13, 16.
- D9 (entry-bar ordering + same-bar-adverse) → Tasks 7 (`entry_bar_ambiguous`), 10 (`same_bar_adverse_mean_r`, on the closed-only basis).
- D10 (four censoring scenarios, each over ALL triggered trades [C3]; no lower-bound claim; forced-exit at post-horizon open / annotated MTM-collapse [M3]) → Tasks 9, 10.
- D11 (headline = realistic closed-only [C3] + trigger rate + per-signal) → Task 10.
- D12 (maturity-staged 10/20 proxy) → Task 9 (`_trail_ma_period`).
