"""Fetch-vs-write-ordering fix: in-process deadlock-reproduction + parity tests.

Binding regression (spec section 7.1): a real file-backed SQLite DB + a spy
ohlcv_cache whose get_or_fetch opens a SECOND connection and attempts
BEGIN IMMEDIATE. If a lease.fenced_write() tx is held on another connection in
this process, that second-connection BEGIN IMMEDIATE times out (the Run-92
`database is locked` deadlock). Pre-fix the exemplar/observe fetch runs inside
the held fence -> deadlock_observed=True; post-fix the fetch runs lock-free.
"""
from __future__ import annotations

import sqlite3
from unittest.mock import patch

from swing.data.models import PatternExemplar
from swing.data.repos.pattern_exemplars import insert_exemplar
from tests.pipeline.conftest_temporal import (  # noqa: F401
    _build_bars,
    _cfg,
    _drive_detect,
    _FakeLease,
    _plant_detection,
    _seed_aplus_candidate_and_run,
    _stub_window,
    tmp_db_v22,
)

_OBS = "2026-05-29"


class _DeadlockProbeCache:
    """ohlcv_cache spy. Each get_or_fetch opens a SECOND connection to the same
    file DB and attempts BEGIN IMMEDIATE with a short busy_timeout. A timeout
    means another connection in THIS process holds the write lock (the fence) ->
    records deadlock_observed=True. Always returns canned bars afterwards (so the
    detect exemplar try/except cannot swallow the signal). Optional inject_on/
    on_inject hook fires a concurrent mutation AFTER the probe on the call whose
    ticker matches inject_on (OQ-E divergence test). inject_on is the EXEMPLAR
    ticker (fetched during the post-snapshot pre-fetch), NOT a candidate (Pass-1
    candidate fetches precede the snapshot)."""

    def __init__(self, db_path, bars_by_ticker, *, probe_timeout_ms=200,
                 inject_on=None, on_inject=None, raise_for=()):
        self._db_path = str(db_path)
        self._bars = bars_by_ticker
        self._probe_timeout_ms = probe_timeout_ms
        self._inject_on = inject_on.upper() if inject_on else None
        self._on_inject = on_inject
        self._raise_for = {t.upper() for t in raise_for}
        self.calls: list[str] = []
        self.deadlock_observed = False

    def get_or_fetch(self, *, ticker, window_days=180):
        self.calls.append(ticker.upper())
        probe = sqlite3.connect(self._db_path)
        try:
            probe.execute(f"PRAGMA busy_timeout={self._probe_timeout_ms}")
            try:
                probe.execute("BEGIN IMMEDIATE")
                probe.execute("ROLLBACK")
            except sqlite3.OperationalError:
                self.deadlock_observed = True
        finally:
            probe.close()
        if (self._inject_on is not None and ticker.upper() == self._inject_on
                and self._on_inject is not None):
            self._on_inject()
        if ticker.upper() in self._raise_for:
            raise KeyError(ticker)
        df = self._bars.get(ticker.upper())
        if df is None:
            raise KeyError(ticker)
        return df

    def drain_telemetry(self):  # observe reads this; counts are not asserted here
        return {"fetch_window": 0, "in_memory_hit": 0}


def _seed_confirmed_exemplar(conn, *, ticker="HIST", pattern_class="vcp",
                             start_date="2025-11-15", end_date="2025-11-25",
                             final_decision="confirmed"):
    """Insert one labeled exemplar via the real repo (production INSERT shape).
    Dates intersect _build_bars() (2025-06-01 + 180d) so the close slice is
    non-empty. Returns the exemplar id."""
    return insert_exemplar(conn, PatternExemplar(
        id=None, ticker=ticker, timeframe="daily",
        start_date=start_date, end_date=end_date,
        proposed_pattern_class=pattern_class, final_decision=final_decision,
        label_source="curated_gold", structural_evidence_json="{}",
        created_at="2025-07-20T00:00:00", created_by="operator",
        quality_grade=5, gold_validated_at="2025-07-20T00:00:00",
        geometric_score_json="{}", labeler_evidence_json="{}"))


def _drive_observe(cfg, lease, cache, warnings):
    with (
        patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
              return_value=_stub_window(9.0, date_=_OBS)),
        patch("swing.pipeline.runner.lease_data_asof", return_value=_OBS),
    ):
        from swing.pipeline.runner import _step_pattern_observe
        _step_pattern_observe(cfg=cfg, lease=lease, ohlcv_cache=cache,
                              run_warnings=warnings)


def test_detect_pass2_exemplar_fetch_runs_outside_fence_no_deadlock(
        tmp_db_v22, tmp_path):
    """BINDING (spec 7.1, locus #8). Pre-fix: exemplar get_or_fetch @1994 runs
    inside the held fence -> second-conn BEGIN IMMEDIATE deadlocks. Post-fix: the
    exemplar bars are pre-fetched before the fence -> no deadlock."""
    conn, db_path = tmp_db_v22
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run((conn, db_path))
    _seed_confirmed_exemplar(conn, ticker="HIST", pattern_class="vcp")
    conn.commit()
    cache = _DeadlockProbeCache(
        db_path, {"AAA": _build_bars(), "HIST": _build_bars()})
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    # Anti-false-pass: the exemplar fetch MUST have fired (so the assertion is
    # not vacuous), and at least one get_or_fetch occurred.
    assert "HIST" in cache.calls
    assert len(cache.calls) >= 1
    # The exemplar bar fetch ran with NO held fence -> no second-conn deadlock.
    assert cache.deadlock_observed is False


def test_detect_pass2_exemplar_bars_fetched_once_candidates_not_refetched(
        tmp_db_v22, tmp_path):
    """#5 (spec 7.3): the Pass-2 reorder only ADDS the exemplar pre-fetch.
    Each exemplar ticker is fetched exactly once; candidate tickers fetched in
    Pass-1 are not re-fetched for exemplar purposes."""
    conn, db_path = tmp_db_v22
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run((conn, db_path))
    _seed_confirmed_exemplar(conn, ticker="HIST", pattern_class="vcp")
    conn.commit()
    cache = _DeadlockProbeCache(
        db_path, {"AAA": _build_bars(), "HIST": _build_bars()})
    _drive_detect(conn, cfg, lease, eval_run_id, cache, [])
    # Exemplar fetched exactly once.
    assert cache.calls.count("HIST") == 1
    # Candidate AAA fetched in Pass-1 (>=1); never an EXTRA exemplar fetch
    # (AAA is not an exemplar ticker).
    assert cache.calls.count("AAA") >= 1


def test_detect_pass2_exemplar_bar_failure_emits_27_audit_and_absent_from_match(
        tmp_db_v22, tmp_path):
    """spec 7.4(b): an exemplar whose bars fail to fetch is uniformly absent
    from match+universe, emits a #27 warnings_json entry, and NO in-fence fetch
    is attempted (the failure happens in the pre-fetch, outside the fence)."""
    conn, db_path = tmp_db_v22
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run((conn, db_path))
    _seed_confirmed_exemplar(conn, ticker="BADX", pattern_class="vcp")
    conn.commit()
    cache = _DeadlockProbeCache(
        db_path, {"AAA": _build_bars()}, raise_for=("BADX",))
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    # #27 audit emitted for the failed exemplar.
    assert any(
        w.get("step") == "pattern_detect"
        and w.get("exemplar_ticker") == "BADX"
        and w.get("reason") == "exemplar bars unavailable"
        for w in warnings
    )
    # The failed exemplar fetch happened OUTSIDE the fence (no deadlock).
    assert cache.deadlock_observed is False
    # vcp rows persisted with template_match_score NULL (exemplar absent from
    # match -> compute_composite_score fallback).
    rows = conn.execute(
        "SELECT template_match_score FROM pattern_evaluations "
        "WHERE ticker='AAA' AND pattern_class='vcp'").fetchall()
    assert rows
    assert all(r[0] is None for r in rows)


def test_detect_pass2_list_exemplars_read_exactly_once(tmp_db_v22, tmp_path):
    """spec 7.4(c): list_exemplars is read exactly ONCE per run (the snapshot);
    the in-fence path no longer re-reads it for bar sourcing."""
    conn, db_path = tmp_db_v22
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run((conn, db_path))
    _seed_confirmed_exemplar(conn, ticker="HIST", pattern_class="vcp")
    conn.commit()
    cache = _DeadlockProbeCache(
        db_path, {"AAA": _build_bars(), "HIST": _build_bars()})
    import swing.data.repos.pattern_exemplars as _pe
    real = _pe.list_exemplars
    count = {"n": 0}

    def _counting(*a, **k):
        count["n"] += 1
        return real(*a, **k)

    with patch.object(_pe, "list_exemplars", _counting):
        _drive_detect(conn, cfg, lease, eval_run_id, cache, [])
    assert count["n"] == 1


def _insert_extra_eligible_exemplar(db_path):
    """Concurrent web/CLI-style write: add an eligible exemplar on a SEPARATE
    committed connection (simulates a mid-run corpus mutation)."""
    c = sqlite3.connect(str(db_path))
    try:
        c.execute("PRAGMA foreign_keys=ON")
        from swing.data.models import PatternExemplar
        from swing.data.repos.pattern_exemplars import insert_exemplar
        with c:
            insert_exemplar(c, PatternExemplar(
                id=None, ticker="MIDRUN", timeframe="daily",
                start_date="2025-11-15", end_date="2025-11-25",
                proposed_pattern_class="vcp", final_decision="confirmed",
                label_source="curated_gold", structural_evidence_json="{}",
                created_at="2025-07-20T00:00:00", created_by="operator",
                quality_grade=5, gold_validated_at="2025-07-20T00:00:00",
                geometric_score_json="{}", labeler_evidence_json="{}"))
    finally:
        c.close()


def test_detect_pass2_midrun_corpus_divergence_emits_27_audit(
        tmp_db_v22, tmp_path):
    """OQ-E (spec 7.6): a concurrent eligible-exemplar write between the snapshot
    and the in-fence ID re-read emits a #27 divergence audit (added=1, removed=0)
    WITHOUT an in-fence fetch; scoring still uses the snapshot."""
    conn, db_path = tmp_db_v22
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run((conn, db_path))
    _seed_confirmed_exemplar(conn, ticker="HIST", pattern_class="vcp")
    conn.commit()
    # The injected insert commits DURING the EXEMPLAR pre-fetch (inject_on="HIST"
    # fires after the snapshot list_exemplars, before the fence) -> the in-fence
    # ID re-read sees the extra eligible ID. (Pass-1 candidate fetches, e.g. AAA,
    # precede the snapshot, so injecting there would land before the snapshot and
    # produce NO divergence -- hence inject_on the exemplar ticker.)
    cache = _DeadlockProbeCache(
        db_path, {"AAA": _build_bars(), "HIST": _build_bars()},
        inject_on="HIST",
        on_inject=lambda: _insert_extra_eligible_exemplar(db_path))
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    divergence = [
        w for w in warnings
        if w.get("step") == "pattern_detect"
        and "membership changed mid-run" in (w.get("reason") or "")
    ]
    assert len(divergence) == 1, warnings
    assert divergence[0]["added"] == 1
    assert divergence[0]["removed"] == 0
    # MIDRUN was added after the snapshot -> never fetched (scoring used the
    # snapshot corpus only).
    assert "MIDRUN" not in cache.calls
    assert cache.deadlock_observed is False


def test_detect_pass2_no_divergence_no_audit(tmp_db_v22, tmp_path):
    """OQ-E control: a stable corpus emits NO divergence warning."""
    conn, db_path = tmp_db_v22
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run((conn, db_path))
    _seed_confirmed_exemplar(conn, ticker="HIST", pattern_class="vcp")
    conn.commit()
    cache = _DeadlockProbeCache(
        db_path, {"AAA": _build_bars(), "HIST": _build_bars()})
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    assert not [
        w for w in warnings
        if "membership changed mid-run" in (w.get("reason") or "")
    ]


def test_observe_bar_fetch_runs_outside_fence_no_deadlock(tmp_db_v22, tmp_path):
    """BINDING (spec 7.1, locus #9). Pre-fix: _bar_for_date -> get_or_fetch @2525
    runs inside the held fence @2628 -> second-conn BEGIN IMMEDIATE deadlocks.
    Post-fix: the compute pass (incl. the fetch) runs before the insert fence."""
    conn, db_path = tmp_db_v22
    _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    cache = _DeadlockProbeCache(db_path, {"AAA": _build_bars()})
    warnings: list[dict] = []
    _drive_observe(cfg, _FakeLease(db_path, 1, _OBS), cache, warnings)
    # Anti-false-pass: a non-idempotent, non-shed detection MUST have fetched.
    assert "AAA" in cache.calls
    assert len(cache.calls) >= 1
    # The bar fetch ran with NO held fence -> no second-conn deadlock.
    assert cache.deadlock_observed is False


def test_observe_split_preserves_idempotency_and_observed_count(
        tmp_db_v22, tmp_path):
    """spec 7.5: the split is behavior-preserving. First drive observes the open
    detection (1 row); a same-day re-drive is idempotent (still 1 row)."""
    from swing.data.repos.pattern_forward_observations import (
        get_observations_for_detection)
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    cache = _DeadlockProbeCache(db_path, {"AAA": _build_bars()})
    _drive_observe(cfg, _FakeLease(db_path, 1, _OBS), cache, [])
    assert len(get_observations_for_detection(conn, det_id)) == 1
    # Idempotent re-drive: still 1 (the idempotency skip runs in the compute
    # pass, before the fetch -> no second fetch, no duplicate row).
    cache2 = _DeadlockProbeCache(db_path, {"AAA": _build_bars()})
    _drive_observe(cfg, _FakeLease(db_path, 2, _OBS), cache2, [])
    assert len(get_observations_for_detection(conn, det_id)) == 1
    assert cache2.calls == []  # idempotent -> never fetched
