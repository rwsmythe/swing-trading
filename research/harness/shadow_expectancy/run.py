from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from research.harness.shadow_expectancy import constants as c
from research.harness.shadow_expectancy import io, output
from research.harness.shadow_expectancy.attribution import attribute_hypotheses
from research.harness.shadow_expectancy.collapse import collapse_detections
from research.harness.shadow_expectancy.exceptions import ShadowExpectancyError
from research.harness.shadow_expectancy.funnel import (
    DetectionLevel,
    SignalOutcome,
    build_funnel,
)
from research.harness.shadow_expectancy.scorecard import (
    ShadowTrade,
    build_hypothesis_scorecard,
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


def _ohlc_tuple(j):
    d = json.loads(j)
    return (d["open"], d["high"], d["low"], d["close"])


def _series_key(chain):
    return tuple((o.observation_date,) + _ohlc_tuple(o.ohlc_today_json) for o in chain)


def run_harness(*, db_path, output_dir, source=c.SOURCE,
                partial_session_n=c.PARTIAL_SESSION_N,
                breakeven_r=c.BREAKEVEN_R_TRIGGER,
                horizon_sessions=c.HORIZON_SESSIONS, only=None):
    conn = io.open_ro(db_path)
    registry = list_hypotheses(conn, status_filter="active")
    detections = io.list_pipeline_detections(conn, source=source)
    # Codex R1-M2: apply the --only ticker filter UP FRONT so total_detections,
    # unique_signals, and collapsed_duplicate all derive from the same filtered set
    # (the detection-level funnel must reconcile under --only too).
    if only:
        detections = [d for d in detections if d.ticker in only]

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
        initial_shares=c.INITIAL_SHARES, partial_session_n=partial_session_n,
        partial_pct=c.PARTIAL_PCT, breakeven_r_trigger=breakeven_r,
        maturity_fast_ma_r=c.MATURITY_FAST_MA_R, ma_fast_period=c.MA_FAST_PERIOD,
        ma_slow_period=c.MA_SLOW_PERIOD, horizon_sessions=horizon_sessions)

    for (pipeline_run_id, ticker), dets in sorted(groups.items(),
                                                  key=lambda kv: (kv[0][0] or -1, kv[0][1])):
        # (the --only filter is applied to `detections` up front; every remaining group
        # is a real unique signal.)
        unique_signals += 1
        candidate = io.resolve_candidate(conn, pipeline_run_id=pipeline_run_id, ticker=ticker)
        # build detection views (chain + trigger session) for collapse.
        views = []
        chains = {}
        for d in dets:
            chain = io.read_observation_chain(conn, d.detection_id)
            chains[d.detection_id] = chain
            entry, _fwd = _entry_and_forward(chain)
            pivot = json.loads(d.structural_anchors_json)["evidence"].get("pivot_price")
            views.append(_DetView(d.detection_id, pivot, _series_key(chain),
                                  entry.observation_date if entry else None))
        cand_pivot = candidate.pivot if candidate is not None else None
        res = collapse_detections(views, candidate_pivot=cand_pivot)
        # Codex R1-M3: every (pipeline_run_id, ticker) group collapses its detections to ONE
        # unique signal, so it contributes len(dets) - 1 duplicate detections REGARDLESS of
        # whether the group is excluded. On the success path this equals len(res.collapsed_ids);
        # on an exclusion path (no_candidate_join / no_canonical_detection / inconsistent_*)
        # collapse returns collapsed_ids=[], so counting len(dets) - 1 here keeps the
        # detection-level reconciliation (total == unique + collapsed) exact for excluded
        # multi-detection groups too.
        collapsed_duplicate += len(dets) - 1
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
                # Codex R1-M1: a never-triggered ATTRIBUTED signal is still a SIGNAL for that
                # hypothesis -- it MUST contribute to the scorecard's signal denominator
                # (trigger rate over len(group); per-signal expectancy counts it as 0R; D11).
                # Emit a non-triggered ShadowTrade so the scorecard population matches the
                # funnel's per-hypothesis terminal-status counts (which already count it).
                shadow_trades.append(ShadowTrade(
                    hypothesis=h, triggered=False, open_at_horizon=False,
                    realized_r=None, entry_bar_ambiguous=False,
                    holding_sessions=0, censoring_scenarios=None))
            continue
        entry_bar = io.parse_bar(entry.ohlc_today_json, session=entry.observation_date)
        # FULL forward chain (NOT pre-truncated) so the simulator can read the post-horizon
        # open for the forced-exit scenario (Codex M3).
        forward_bars = [io.parse_bar(o.ohlc_today_json, session=o.observation_date)
                        for o in forward]

        # validate: candidate PIVOT sanity (C1/R2-M1 -- candidate.initial_stop is NOT consulted;
        # the trade stop is entry_bar.low) + every bar on the path. A failure on this ATTRIBUTED
        # signal routes PER-HYPOTHESIS (Codex M5), not unattributed.
        reason = validate_signal(pivot=candidate.pivot, bars=[entry_bar, *forward_bars])
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
        detection_date = next(d.detection_date for d in dets
                              if d.detection_id == res.canonical.detection_id)
        for h in hyps:
            signal_outcomes.append(SignalOutcome(h, terminal, None))
            shadow_trades.append(ShadowTrade(
                hypothesis=h, triggered=True,
                open_at_horizon=sim.open_at_horizon, realized_r=sim.realized_r,
                entry_bar_ambiguous=sim.entry_bar_ambiguous,
                holding_sessions=sim.holding_sessions,
                censoring_scenarios=sim.censoring_scenarios))
            results_rows.append({
                "ticker": ticker, "detection_date": detection_date,
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
    # Codex R1-M4: enforce the reconciliation invariant at the PRODUCER (run_harness emits
    # exactly one terminal SignalOutcome per unique signal). build_funnel itself stays a pure
    # structural aggregator (it is legitimately called with partial detection-level data in the
    # unit tests), so the invariant is checked HERE, against the harness's own emitted counts,
    # before any artifact is written.
    _unattr_total = sum(funnel["unattributed"].values())
    _per_hyp_total = sum(
        card["closed"] + card["open_at_horizon"] + card["never_triggered"]
        + sum(card["excluded"].values())
        for card in funnel["per_hypothesis"].values())
    if _unattr_total + _per_hyp_total != unique_signals:
        raise ShadowExpectancyError(
            "funnel reconciliation invariant violated: "
            f"unattributed({_unattr_total}) + per_hypothesis_terminals({_per_hyp_total}) "
            f"!= unique_signals({unique_signals})")
    scorecard = build_hypothesis_scorecard(
        shadow_trades, sample_floor_mean=c.SAMPLE_FLOOR_MEAN,
        sample_floor_rate=c.SAMPLE_FLOOR_RATE, profit_factor_floor=c.PROFIT_FACTOR_FLOOR)

    results_path = run_dir / "results.csv"
    per_session_path = run_dir / "per_session.csv"
    summary_path = run_dir / "summary.md"
    manifest_path = run_dir / "manifest.json"
    output.write_results_csv(results_rows, results_path)
    output.write_per_session_csv(ledger_rows, per_session_path)
    output.write_summary_md(_summary_lines(funnel, scorecard), summary_path)
    output.write_manifest_json({
        "harness_version": c.HARNESS_VERSION, "source": source,
        "params": {"partial_session_n": partial_session_n, "breakeven_r": breakeven_r,
                   "horizon_sessions": horizon_sessions,
                   "ma_staging": [c.MA_FAST_PERIOD, c.MA_SLOW_PERIOD]},
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
    for reason in c.UNATTRIBUTED_REASONS:
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
    p.add_argument("--source", type=str, default=c.SOURCE)
    p.add_argument("--partial-session-n", type=int, default=c.PARTIAL_SESSION_N)
    p.add_argument("--breakeven-r", type=float, default=c.BREAKEVEN_R_TRIGGER)
    p.add_argument("--horizon-sessions", type=int, default=c.HORIZON_SESSIONS)
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
