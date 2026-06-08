# research/harness/minervini_exemplar_recall/timing.py
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from swing.config import Config

from . import detector_eval, screen_eval, stage_db
from .detector_eval import DetectorVerdict
from .exemplar_reader import ExemplarRow
from .screen_eval import ScreenResult

_BUCKET_RANK = {"aplus": 2, "watch": 1, "skip": 0}
_OUTCOME_RANK = {
    "surfaced_aplus": 4,
    "surfaced_watch": 3,
    "skip_gate_rejection": 2,
    "skip_insufficient_history": 1,
    "no_data": 0,
}


@dataclass(frozen=True)
class SessionEval:
    session: date
    screen: ScreenResult
    h2_faithful: DetectorVerdict
    h2_isolated: DetectorVerdict


@dataclass(frozen=True)
class ExemplarTimingResult:
    mode: str  # "single_session" | "window_sweep"
    sessions: tuple[SessionEval, ...]
    best_bucket: str
    best_h1_outcome: str
    h2_faithful_fired_expected: bool
    h2_isolated_fired_expected: bool
    firing_sessions_faithful: tuple[date, ...]
    firing_sessions_isolated: tuple[date, ...]


def _entry_pos(bars: pd.DataFrame, entry_anchor: date) -> int | None:
    mask = bars.index.date >= entry_anchor
    if not mask.any():
        return None
    return int(mask.argmax())


def sweep_sessions(
    bars: pd.DataFrame, entry_anchor: date, *, window_back: int, window_fwd: int
) -> list[date]:
    pos = _entry_pos(bars, entry_anchor)
    if pos is None:
        return []
    start = max(0, pos - window_back)
    end = pos + window_fwd + 1  # inclusive of the +window_fwd bar; truncates at len naturally
    return [d.date() for d in bars.index[start:end]]


def single_session(bars: pd.DataFrame, entry_anchor: date) -> list[date]:
    pos = _entry_pos(bars, entry_anchor)
    return [] if pos is None else [bars.index[pos].date()]


def best_bucket_of(buckets) -> str:
    best = "skip"
    for b in buckets:
        if _BUCKET_RANK.get(b, 0) > _BUCKET_RANK.get(best, 0):
            best = b
    return best


def _eval_one_session(
    *,
    exemplar: ExemplarRow,
    session: date,
    exemplar_full: pd.DataFrame,
    spy_full: pd.DataFrame | None,
    config: Config,
    faith_conn,
    iso_conn,
) -> SessionEval:
    screen = screen_eval.evaluate_h1(
        ticker=exemplar.tiingo_symbol,
        exemplar_full=exemplar_full,
        spy_full=spy_full,
        session=session,
        config=config,
    )
    # Seed isolated (always); seed faithful only when we have the 8 TT (no_data has none).
    stage_db.seed_session(
        iso_conn, ticker=exemplar.tiingo_symbol, session=session, tt_results=(), mode="isolated"
    )
    if len(screen.tt_criteria) == 8:
        stage_db.seed_session(
            faith_conn,
            ticker=exemplar.tiingo_symbol,
            session=session,
            tt_results=screen.tt_criteria,
            mode="faithful",
        )
        h2_faith = detector_eval.evaluate_h2(
            exemplar=exemplar, session=session, exemplar_full=exemplar_full, stage_conn=faith_conn
        )
    else:
        h2_faith = detector_eval._skip_verdict("coverage_skip", exemplar.detector_class)
    h2_iso = detector_eval.evaluate_h2(
        exemplar=exemplar, session=session, exemplar_full=exemplar_full, stage_conn=iso_conn
    )
    return SessionEval(session=session, screen=screen, h2_faithful=h2_faith, h2_isolated=h2_iso)


def _aggregate(mode: str, evals: list[SessionEval]) -> ExemplarTimingResult:
    if not evals:
        return ExemplarTimingResult(mode, (), "skip", "no_data", False, False, (), ())
    best_bucket = best_bucket_of([e.screen.bucket or "skip" for e in evals])
    best_outcome = max((e.screen.outcome for e in evals), key=lambda o: _OUTCOME_RANK.get(o, 0))
    fire_faith = tuple(e.session for e in evals if e.h2_faithful.fired_expected_class is True)
    fire_iso = tuple(e.session for e in evals if e.h2_isolated.fired_expected_class is True)
    return ExemplarTimingResult(
        mode=mode,
        sessions=tuple(evals),
        best_bucket=best_bucket,
        best_h1_outcome=best_outcome,
        h2_faithful_fired_expected=len(fire_faith) > 0,
        h2_isolated_fired_expected=len(fire_iso) > 0,
        firing_sessions_faithful=fire_faith,
        firing_sessions_isolated=fire_iso,
    )


def evaluate_exemplar(
    exemplar: ExemplarRow,
    *,
    exemplar_full: pd.DataFrame,
    spy_full: pd.DataFrame | None,
    config: Config,
    window_back: int = 60,
    window_fwd: int = 5,
) -> dict[str, ExemplarTimingResult]:
    out: dict[str, ExemplarTimingResult] = {}
    modes = {
        "single_session": single_session(exemplar_full, exemplar.entry_anchor),
        "window_sweep": sweep_sessions(
            exemplar_full, exemplar.entry_anchor, window_back=window_back, window_fwd=window_fwd
        ),
    }
    for mode, sessions in modes.items():
        with tempfile.TemporaryDirectory() as td:
            faith_conn = stage_db.build_stage_db(Path(td) / "faithful.db")
            iso_conn = stage_db.build_stage_db(Path(td) / "isolated.db")
            try:
                evals = [
                    _eval_one_session(
                        exemplar=exemplar,
                        session=s,
                        exemplar_full=exemplar_full,
                        spy_full=spy_full,
                        config=config,
                        faith_conn=faith_conn,
                        iso_conn=iso_conn,
                    )
                    for s in sessions
                ]
            finally:
                faith_conn.close()
                iso_conn.close()
        out[mode] = _aggregate(mode, evals)
    return out
