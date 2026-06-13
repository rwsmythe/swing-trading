"""Phase-0 characterization matrix for the runner step wrappers (Arc 17-B).

Pins every ``lease.step``-guarded site's observable failure contract against
the REAL ``run_pipeline`` so the step_guard extraction is provably
behavior-preserving. Lands GREEN on the un-refactored code FIRST; the
extraction keeps it green. The SITES list is the single source of truth --
the AST completeness guard (bottom of file) fails if runner.py grows a
``lease.step(...)`` site not represented here.
"""
from __future__ import annotations

import ast
import json
import logging
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest

from swing.config import load
from swing.data.db import ensure_schema
from swing.data.repos.pipeline import LeaseRevokedError, find_run
from swing.pipeline import run_pipeline
from tests.cli.test_cli_eval import _minimal_config

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "swing" / "pipeline" / "runner.py"
PHASE2_FIXTURE = (
    REPO / "tests" / "fixtures" / "finviz" / "finviz13Apr2026-phase2.csv"
)


@dataclass(frozen=True)
class Site:
    name: str                 # the lease.step("<name>") literal
    status_key: str | None    # the *_status column, or None for B sites
    wrapped: bool             # True iff this site becomes `with step_guard(...)`
    inject: str | None        # dotted patch target to raise from, or None (complete)
    inbox: str                # "csv" (fixture present) or "empty"
    state_on_exc: str         # RunResult.state when the body raises Exception
    revoke_propagates: bool   # True iff a planted LeaseRevokedError aborts the run
    # The breadcrumb name flushed to pipeline_step_timings. For most sites this
    # is `name`; review_log_cadence runs under the "complete" breadcrumb so it
    # has NO breadcrumb of its own.
    breadcrumb: str | None
    # The EXACT warning line the runner emits when the body raises
    # RuntimeError(f"injected into {name}"). Set for the 9 wrapped sites so the
    # characterization pins the production warning text byte-identically pre- AND
    # post-extraction (Codex R3 #2). None for non-wrapped/fatal/terminal sites.
    expected_warning: str | None = None


# THE SINGLE SOURCE OF TRUTH. Order mirrors execution order in run_pipeline.
SITES: list[Site] = [
    Site("finviz_fetch_site1", None, False,
         "swing.pipeline.runner._step_finviz_fetch", "empty",
         "failed", True, "finviz_fetch"),
    Site("weather", "weather_status", True,
         "swing.weather.classifier.classify_weather", "csv",
         "complete", True, "weather",
         expected_warning="weather failed: injected into weather"),
    Site("finviz_fetch_site2", None, False,
         "swing.pipeline.runner._step_finviz_fetch", "csv",
         "complete", True, "finviz_fetch"),
    Site("evaluate", "evaluation_status", False,
         "swing.pipeline.runner._step_evaluate", "csv",
         "failed", True, "evaluate"),
    Site("daily_management", None, True,
         "swing.pipeline.runner._step_daily_management", "csv",
         "complete", True, "daily_management",
         expected_warning=("daily_management step programming error "
                           "(continuing): injected into daily_management")),
    Site("watchlist", "watchlist_status", True,
         "swing.pipeline.runner._step_watchlist", "csv",
         "complete", True, "watchlist",
         expected_warning="watchlist failed: injected into watchlist"),
    Site("recommendations", "recommendations_status", True,
         "swing.pipeline.runner._step_recommendations", "csv",
         "complete", True, "recommendations",
         expected_warning="recommendations failed: injected into recommendations"),
    Site("pattern_detect", None, True,
         "swing.pipeline.runner._step_pattern_detect", "csv",
         "complete", True, "pattern_detect",
         expected_warning="pattern_detect failed: injected into pattern_detect"),
    Site("pattern_observe", None, True,
         "swing.pipeline.runner._step_pattern_observe", "csv",
         "complete", True, "pattern_observe",
         expected_warning="pattern_observe failed: injected into pattern_observe"),
    Site("schwab_snapshot", None, True,
         "swing.integrations.schwab.pipeline_steps._step_schwab_snapshot", "csv",
         "complete", True, "schwab_snapshot",
         expected_warning="schwab_snapshot failed (continuing pipeline): RuntimeError"),
    Site("schwab_orders", None, True,
         "swing.integrations.schwab.pipeline_steps._step_schwab_orders", "csv",
         "complete", True, "schwab_orders",
         expected_warning="schwab_orders failed (continuing pipeline): RuntimeError"),
    Site("charts", "charts_status", False,
         "swing.pipeline.runner._step_charts", "csv",
         "complete", True, "charts"),
    Site("export", "export_status", True,
         "swing.pipeline.runner._step_export", "csv",
         "complete", True, "export",
         expected_warning="export failed: injected into export"),
    Site("shadow_expectancy", None, False,
         "swing.pipeline.runner._step_shadow_expectancy", "csv",
         "complete", True, "shadow_expectancy"),
    Site("complete", None, False, None, "csv",
         "complete", False, "complete"),
    Site("review_log_cadence", None, False,
         "swing.pipeline.runner._step_review_log_cadence", "csv",
         "complete", False, None),  # revoke_propagates=False: bare except swallows it
]

BY_NAME = {s.name: s for s in SITES}


def _make_cfg(tmp_path: Path, *, inbox: str):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = load(_minimal_config(project, home))
    ensure_schema(cfg.paths.db_path).close()
    inbox_dir = cfg.paths.finviz_inbox_dir
    inbox_dir.mkdir(parents=True, exist_ok=True)
    if inbox == "csv":
        if not PHASE2_FIXTURE.exists():
            pytest.skip(f"fixture not found: {PHASE2_FIXTURE}")
        shutil.copy2(PHASE2_FIXTURE, inbox_dir / PHASE2_FIXTURE.name)
    return cfg


def _stub_prices(monkeypatch):
    closes = [100.0 + i * 0.5 for i in range(260)]
    idx = pd.bdate_range(end="2026-04-13", periods=260)
    df = pd.DataFrame({
        "Open": closes, "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes], "Close": closes,
        "Volume": [1_000_000] * 260,
    }, index=idx)
    monkeypatch.setattr(
        "swing.prices.PriceFetcher.get",
        lambda self, ticker, lookback_days, *, as_of_date=None: df,
    )


# Heavy step bodies stubbed to fast no-ops so each parametrized run is light.
# The TARGET site is NEVER stubbed here (the per-test injection overrides it).
# Light steps (weather inline, daily_management, watchlist, recommendations,
# schwab [client=None silent-skip], review_log_cadence) run for real on the
# synthetic fixture. _step_evaluate must return an int eval_run_id.
_HEAVY_STUBS: dict[str, object] = {
    "swing.pipeline.runner._step_evaluate": lambda *a, **k: 1,
    "swing.pipeline.runner._step_pattern_detect": lambda *a, **k: None,
    "swing.pipeline.runner._step_pattern_observe": lambda *a, **k: None,
    "swing.pipeline.runner._step_charts": lambda *a, **k: {},
    "swing.pipeline.runner._step_export": lambda *a, **k: None,
    "swing.pipeline.runner._step_shadow_expectancy": lambda *a, **k: None,
}


def _apply_default_stubs(monkeypatch, *, skip: str | None):
    for target, fn in _HEAVY_STUBS.items():
        if target == skip:
            continue
        monkeypatch.setattr(target, fn)


def _find_run(cfg, run_id):
    # Closes the connection (sqlite3's `with conn` manages the TRANSACTION, not
    # close). (Codex R2 #2 -- avoid leaking connections in the assertions.)
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        return find_run(conn, run_id)
    finally:
        conn.close()


def _step_timings(cfg) -> list[str]:
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        # Order by `ordinal` (the repo's canonical ordering -- see
        # pipeline_step_timings.py:58 / list_step_timings), NOT by `id`.
        # (Codex R1 #4.)
        return [
            r[0] for r in conn.execute(
                "SELECT step_name FROM pipeline_step_timings ORDER BY ordinal ASC"
            ).fetchall()
        ]
    finally:
        conn.close()


def test_happy_path_fires_every_breadcrumb(tmp_path, monkeypatch):
    """All 14 CSV-path breadcrumbs fire in order on a clean run. finviz_fetch
    appears ONCE here (site-2); site-1's empty-inbox breadcrumb is covered
    separately (it fires only when the inbox is empty)."""
    cfg = _make_cfg(tmp_path, inbox="csv")
    _stub_prices(monkeypatch)
    _apply_default_stubs(monkeypatch, skip=None)
    result = run_pipeline(cfg=cfg, trigger="manual")
    assert result.state == "complete", result.error_message
    fired = _step_timings(cfg)
    expected = [
        "weather", "finviz_fetch", "evaluate", "daily_management",
        "watchlist", "recommendations", "pattern_detect", "pattern_observe",
        "schwab_snapshot", "schwab_orders", "charts", "export",
        "shadow_expectancy", "complete",
    ]
    assert fired == expected


_EXC_SITES = [
    s for s in SITES
    if s.inject is not None and s.name not in {"finviz_fetch_site1", "evaluate"}
]


@pytest.mark.parametrize("site", _EXC_SITES, ids=lambda s: s.name)
def test_injected_exception_contract(site, tmp_path, monkeypatch, caplog):
    """A raised Exception in each best-effort/explicit step: run CONTINUES,
    the *_status flips to 'failed' (BS sites) or stays absent (B sites), the
    step's breadcrumb still fired (lease.step ran before the body), AND the
    PRODUCTION warning text is byte-identical (Codex R3 #2 -- pins the real
    runner site, not a synthetic lambda)."""
    cfg = _make_cfg(tmp_path, inbox=site.inbox)
    _stub_prices(monkeypatch)
    _apply_default_stubs(monkeypatch, skip=site.inject)

    # *args too: several targets are called POSITIONALLY -- classify_weather(ohlcv)
    # (runner.py:750), _step_schwab_snapshot(_conn, cfg, ...) (runner.py:966),
    # _step_schwab_orders(_conn, cfg, ...) (runner.py:988). A **kwargs-only
    # injector would raise TypeError BEFORE our exception and false-pass. (Codex R1 #2.)
    def _boom(*args, **kwargs):
        raise RuntimeError(f"injected into {site.name}")

    monkeypatch.setattr(site.inject, _boom)
    with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
        result = run_pipeline(cfg=cfg, trigger="manual")

    assert result.state == site.state_on_exc, result.error_message
    if site.breadcrumb is not None:
        assert site.breadcrumb in _step_timings(cfg)
    if site.status_key is not None and site.state_on_exc == "complete":
        run = _find_run(cfg, result.run_id)
        assert getattr(run, site.status_key) == "failed"
    if site.expected_warning is not None:
        msgs = [
            r.getMessage() for r in caplog.records
            if r.name == "swing.pipeline.runner"
        ]
        assert site.expected_warning in msgs, (
            f"expected warning not emitted on swing.pipeline.runner: "
            f"{site.expected_warning!r}; got {msgs!r}"
        )


_REVOKE_SITES = [s for s in SITES if s.inject is not None]


@pytest.mark.parametrize("site", _REVOKE_SITES, ids=lambda s: s.name)
def test_planted_lease_revoked_propagation(site, tmp_path, monkeypatch):
    """A planted LeaseRevokedError ABORTS the run (state='force_cleared')
    for every guarded site EXCEPT review_log_cadence (bare except swallows it
    -> run completes) and finviz_fetch_site1 (outside the L741 try -> raises
    out of run_pipeline)."""
    cfg = _make_cfg(tmp_path, inbox=site.inbox)
    _stub_prices(monkeypatch)
    _apply_default_stubs(monkeypatch, skip=site.inject)

    # *args too -- see Codex R1 #2 note above (positionally-called targets).
    def _revoke(*args, **kwargs):
        raise LeaseRevokedError(f"planted revoke at {site.name}")

    monkeypatch.setattr(site.inject, _revoke)

    if site.name == "finviz_fetch_site1":
        # Not inside the L741 try/except LeaseRevokedError -> propagates out.
        with pytest.raises(LeaseRevokedError):
            run_pipeline(cfg=cfg, trigger="manual")
        return

    result = run_pipeline(cfg=cfg, trigger="manual")
    if site.revoke_propagates:
        # The planted LeaseRevokedError propagates to the outer handler
        # (runner.py:1075), which RETURNS RunResult(state="force_cleared").
        # NOTE: the planted path does not itself force-clear the pipeline_runs
        # row (no real force_clear mutation occurs); we assert on RunResult.state
        # only. (Codex R2 #3.)
        assert result.state == "force_cleared"
    else:
        # review_log_cadence: bare `except Exception` swallows LeaseRevokedError.
        assert result.state == "complete"


def test_evaluate_is_fatal(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path, inbox="csv")
    _stub_prices(monkeypatch)
    _apply_default_stubs(monkeypatch, skip="swing.pipeline.runner._step_evaluate")
    monkeypatch.setattr(
        "swing.pipeline.runner._step_evaluate",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("eval boom")),
    )
    result = run_pipeline(cfg=cfg, trigger="manual")
    assert result.state == "failed"
    run = _find_run(cfg, result.run_id)
    assert run.evaluation_status == "failed"


def test_finviz_site1_empty_inbox_is_fatal(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path, inbox="empty")
    _stub_prices(monkeypatch)
    monkeypatch.setattr(
        "swing.pipeline.runner._step_finviz_fetch",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fetch boom")),
    )
    result = run_pipeline(cfg=cfg, trigger="manual")
    assert result.state == "failed"


def test_charts_unavailable_sets_skipped(tmp_path, monkeypatch):
    from swing.pipeline.runner import ChartingUnavailableError
    cfg = _make_cfg(tmp_path, inbox="csv")
    _stub_prices(monkeypatch)
    _apply_default_stubs(monkeypatch, skip="swing.pipeline.runner._step_charts")
    monkeypatch.setattr(
        "swing.pipeline.runner._step_charts",
        lambda *a, **k: (_ for _ in ()).throw(ChartingUnavailableError("no mpl")),
    )
    result = run_pipeline(cfg=cfg, trigger="manual")
    assert result.state == "complete"
    run = _find_run(cfg, result.run_id)
    assert run.charts_status == "skipped"


def test_shadow_expectancy_failure_appends_run_warning(tmp_path, monkeypatch):
    """A RuntimeError in _step_shadow_expectancy: run completes AND a
    run_warnings entry is persisted to pipeline_runs.warnings_json with
    step='shadow_expectancy', reason='unexpected step error', bounded detail."""
    cfg = _make_cfg(tmp_path, inbox="csv")
    _stub_prices(monkeypatch)
    _apply_default_stubs(
        monkeypatch, skip="swing.pipeline.runner._step_shadow_expectancy")
    monkeypatch.setattr(
        "swing.pipeline.runner._step_shadow_expectancy",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("shadow boom")),
    )
    result = run_pipeline(cfg=cfg, trigger="manual")
    assert result.state == "complete", result.error_message

    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        row = conn.execute(
            "SELECT warnings_json FROM pipeline_runs WHERE id=?", (result.run_id,)
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] is not None, "warnings_json should be set"
    warnings = json.loads(row[0])
    shadow = [w for w in warnings if w.get("step") == "shadow_expectancy"]
    assert len(shadow) == 1, f"expected one shadow warning, got {warnings!r}"
    assert shadow[0]["reason"] == "unexpected step error"
    assert shadow[0].get("detail")  # bounded, non-empty


def _runner_step_site_literals() -> list[str]:
    """Every step-site breadcrumb string literal in runner.py (by AST):
    the 1st positional arg of ``lease.step("X")`` AND the 2nd positional arg
    of ``step_guard(lease, "X", ...)``. Together these are the complete set of
    per-step breadcrumb sites, invariant across the extraction."""
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # lease.step("X")
        if (getattr(func, "attr", None) == "step"
                and getattr(getattr(func, "value", None), "id", None) == "lease"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            names.append(node.args[0].value)
        # step_guard(lease, "X", ...) -- match a bare name `step_guard` OR an
        # attribute access `<mod>.step_guard` (Codex R1 #5: don't miss an
        # attribute-qualified call). Aliasing the import is forbidden by the
        # Task-2 implementation note, so a bare-name match is the common case.
        # Require the receiver arg to be literally `lease` (Codex R5 #3) so a
        # `step_guard(other_lease, "weather", ...)` cannot falsely satisfy the
        # runner-breadcrumb inventory.
        elif ((getattr(func, "id", None) == "step_guard"
               or getattr(func, "attr", None) == "step_guard")
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "lease"
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)):
            names.append(node.args[1].value)
    return names


def test_runner_step_sites_match_inventory():
    """The set+multiplicity of per-step breadcrumb sites in runner.py equals
    the characterized inventory, invariant across the extraction. finviz_fetch
    appears TWICE (sites 1 and 2); review_log_cadence is breadcrumb-less so it
    is NOT in this multiset."""
    from collections import Counter
    actual = Counter(_runner_step_site_literals())
    expected = Counter(
        s.breadcrumb for s in SITES
        if s.breadcrumb is not None and s.name != "review_log_cadence"
    )
    # finviz_fetch has two breadcrumb sites (site1 + site2) -> count 2.
    assert actual == expected, (
        f"runner.py step-site breadcrumbs drifted from the inventory.\n"
        f"actual={dict(actual)}\nexpected={dict(expected)}"
    )


# The bespoke/fatal/terminal sites that MUST stay direct lease.step("X") calls
# and must NEVER be folded into step_guard(...). finviz_fetch covers BOTH the
# fatal site-1 and the best-effort site-2 (both stay explicit).
EXPLICIT_BREADCRUMB_NAMES = {
    "finviz_fetch", "evaluate", "charts", "shadow_expectancy", "complete",
}


def test_explicit_sites_never_wrapped_in_step_guard():
    """Durable regression (Codex R5 #4): the explicit/fatal sites stay direct
    lease.step("X") calls and never appear as step_guard(lease, "X", ...).
    Replaces the manual git-diff grep with a permanent AST assertion."""
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    lease_step_names: set[str] = set()
    step_guard_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (getattr(func, "attr", None) == "step"
                and getattr(getattr(func, "value", None), "id", None) == "lease"
                and node.args and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            lease_step_names.add(node.args[0].value)
        elif ((getattr(func, "id", None) == "step_guard"
               or getattr(func, "attr", None) == "step_guard")
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)):
            step_guard_names.add(node.args[1].value)
    # Each explicit/fatal name stays a direct lease.step call ...
    missing = EXPLICIT_BREADCRUMB_NAMES - lease_step_names
    assert not missing, f"explicit sites no longer direct lease.step calls: {missing}"
    # ... and is NEVER wrapped by step_guard.
    wrapped = EXPLICIT_BREADCRUMB_NAMES & step_guard_names
    assert not wrapped, f"explicit/fatal sites wrongly wrapped in step_guard: {wrapped}"


def _runner_step_guard_names() -> set[str]:
    """Every ``step_guard(lease, "X", ...)`` breadcrumb literal in runner.py."""
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if ((getattr(func, "id", None) == "step_guard"
             or getattr(func, "attr", None) == "step_guard")
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "lease"
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)):
            names.add(node.args[1].value)
    return names


def test_wrapped_sites_routed_through_step_guard():
    """Positive inventory regression (Codex exec R1 minor #1): the nine
    wrapped=True sites ARE implemented as ``step_guard(lease, "X", ...)`` and the
    explicit sites are NOT. The completeness guard accepts EITHER call form (so
    breadcrumb coverage is invariant across the extraction); this test
    additionally pins the wrapped-vs-explicit SPLIT, so a future revert of a
    wrapped site back to an inline ``try/except`` (that kept its breadcrumb)
    is caught."""
    step_guard_names = _runner_step_guard_names()
    wrapped = {s.breadcrumb for s in SITES if s.wrapped and s.breadcrumb is not None}
    assert wrapped == {
        "weather", "daily_management", "watchlist", "recommendations",
        "pattern_detect", "pattern_observe", "schwab_snapshot",
        "schwab_orders", "export",
    }
    missing = wrapped - step_guard_names
    assert not missing, f"wrapped sites not routed through step_guard: {missing}"
    leaked = EXPLICIT_BREADCRUMB_NAMES & step_guard_names
    assert not leaked, f"explicit/fatal sites wrongly wrapped in step_guard: {leaked}"
