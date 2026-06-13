"""_prewarm_evaluate_archives: warm call + #27 telemetry (Arc 6 §6)."""
from __future__ import annotations

from swing.pipeline import runner as rmod
from swing.data.ohlcv_archive import WarmReport


class _Cfg:
    """Minimal duck-typed cfg for the helper (only the fields it reads)."""
    class _Paths:
        prices_cache_dir = "/tmp/arc6-warm-test"
    class _Archive:
        archive_history_days = 1260
    class _RS:
        benchmark_ticker = "SPY"
    paths = _Paths()
    archive = _Archive()
    rs = _RS()


def test_prewarm_calls_warm_once_with_full_deduped_set(monkeypatch):
    captured = {}

    def spy(tickers, **kwargs):
        captured["tickers"] = tickers
        captured["kwargs"] = kwargs
        return WarmReport(cache_hit=3)

    monkeypatch.setattr(rmod, "warm_archives_batch", spy)
    run_warnings: list[dict] = []
    rmod._prewarm_evaluate_archives(
        cfg=_Cfg(), candidate_tickers=["AAPL", "MSFT"],
        universe_tickers=["AAPL", "NVDA"], run_now=None, run_warnings=run_warnings,
    )
    # Called once with benchmark + candidates + universe, deduped + uppercased
    # order-independent (warm_archives_batch dedupes internally; the helper passes
    # the full union).
    assert set(captured["tickers"]) >= {"SPY", "AAPL", "MSFT", "NVDA"}
    assert captured["kwargs"]["archive_history_days"] == 1260


def test_prewarm_degraded_report_appends_27_warning(monkeypatch):
    monkeypatch.setattr(
        rmod, "warm_archives_batch",
        lambda tickers, **k: WarmReport(cache_hit=1, gap=1, fallback=["AAPL"]),
    )
    run_warnings: list[dict] = []
    rmod._prewarm_evaluate_archives(
        cfg=_Cfg(), candidate_tickers=["AAPL"], universe_tickers=[],
        run_now=None, run_warnings=run_warnings,
    )
    assert len(run_warnings) == 1
    assert run_warnings[0]["step"] == "evaluate_warm"
    assert run_warnings[0]["fallback_count"] == 1


def test_prewarm_clean_report_appends_no_warning(monkeypatch):
    monkeypatch.setattr(
        rmod, "warm_archives_batch",
        lambda tickers, **k: WarmReport(cache_hit=5, gap=2),  # empty fallback, 0 chunk_failures
    )
    run_warnings: list[dict] = []
    rmod._prewarm_evaluate_archives(
        cfg=_Cfg(), candidate_tickers=["AAPL"], universe_tickers=["MSFT"],
        run_now=None, run_warnings=run_warnings,
    )
    assert run_warnings == []  # honest funnel — clean warm emits no warning (#27)


def test_prewarm_wholesale_failure_warns_not_raises(monkeypatch):
    def boom(tickers, **k):
        raise RuntimeError("rate limited everywhere")
    monkeypatch.setattr(rmod, "warm_archives_batch", boom)
    run_warnings: list[dict] = []
    # Must NOT raise — warm is best-effort.
    rmod._prewarm_evaluate_archives(
        cfg=_Cfg(), candidate_tickers=["AAPL"], universe_tickers=[],
        run_now=None, run_warnings=run_warnings,
    )
    assert len(run_warnings) == 1
    assert run_warnings[0]["step"] == "evaluate_warm"
    assert "wholesale" in run_warnings[0]["reason"]


def test_step_evaluate_wires_prewarm_before_fetch_loops():
    """Codex R2 Major #2: source-text wiring contract — the pre-warm runs BEFORE
    the serial fetch loops it accelerates.

    Arc 17-A split this across two functions: the PIPELINE adapter
    (`_step_evaluate`) calls `_prewarm_evaluate_archives` inside its
    `pre_fetch_hook` closure and hands that hook to `orchestrate_evaluation`; the
    ORCHESTRATOR invokes `pre_fetch_hook(...)` BEFORE its first `fetcher.get(`.
    The contract is preserved across both: (1) the adapter wires the prewarm into
    the hook + passes it; (2) the orchestrator calls the hook before any fetch."""
    import inspect
    import re

    from swing.evaluation import orchestration as omod

    # (1) The adapter wires the prewarm into the pre_fetch_hook + passes the hook.
    adapter_src = inspect.getsource(rmod._step_evaluate)
    assert re.search(r"^\s*_prewarm_evaluate_archives\(", adapter_src, re.MULTILINE), (
        "_step_evaluate does not CALL _prewarm_evaluate_archives(...)"
    )
    assert re.search(r"pre_fetch_hook\s*=", adapter_src), (
        "_step_evaluate does not pass pre_fetch_hook= to the orchestrator"
    )

    # (2) The orchestrator calls the hook before the first fetcher.get( loop.
    orch_src = inspect.getsource(omod.orchestrate_evaluation)
    hook_match = re.search(r"^\s*pre_fetch_hook\(", orch_src, re.MULTILINE)
    fetch_idx = orch_src.find("fetcher.get(")
    assert hook_match, "orchestrate_evaluation does not CALL pre_fetch_hook(...)"
    assert fetch_idx > -1, "orchestrate_evaluation has no fetcher.get( call (harness drift?)"
    assert hook_match.start() < fetch_idx, (
        f"pre_fetch_hook call (offset {hook_match.start()}) must precede the first "
        f"fetcher.get (offset {fetch_idx}); the warm must run BEFORE the serial loops."
    )


def test_prewarm_trim_appends_27_warning_even_when_clean(monkeypatch):
    """Arc 8: trailing-ragged trims emit a #27 warning entry even when the warm
    is otherwise clean (no fallback, no chunk failures)."""
    monkeypatch.setattr(
        rmod, "warm_archives_batch",
        lambda tickers, **k: WarmReport(cache_hit=5, gap=2, trailing_nan_trimmed=3),
    )
    run_warnings: list[dict] = []
    rmod._prewarm_evaluate_archives(
        cfg=_Cfg(), candidate_tickers=["AAPL"], universe_tickers=["MSFT"],
        run_now=None, run_warnings=run_warnings,
    )
    trim_entries = [w for w in run_warnings if w.get("trailing_nan_trimmed")]
    assert len(trim_entries) == 1
    assert trim_entries[0]["step"] == "evaluate_warm"
    assert trim_entries[0]["trailing_nan_trimmed"] == 3


def test_prewarm_info_line_includes_trim_count(monkeypatch, caplog):
    """Arc 8: the always-on warm telemetry INFO line surfaces the trim count."""
    import logging
    monkeypatch.setattr(
        rmod, "warm_archives_batch",
        lambda tickers, **k: WarmReport(cache_hit=5, trailing_nan_trimmed=2),
    )
    with caplog.at_level(logging.INFO, logger=rmod.log.name):
        rmod._prewarm_evaluate_archives(
            cfg=_Cfg(), candidate_tickers=["AAPL"], universe_tickers=[],
            run_now=None, run_warnings=[],
        )
    info = [r.message for r in caplog.records if "evaluate warm:" in r.message]
    assert info and "trimmed=2" in info[0]
