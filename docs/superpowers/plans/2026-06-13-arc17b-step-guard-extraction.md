# Phase 17 Arc 17-B — `step_guard` Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the ~9 repeated best-effort per-step wrapper blocks in `swing/pipeline/runner.py` (`lease.step(name)` + `try/except LeaseRevokedError/except Exception`) into ONE tested context manager `swing/pipeline/step_guard.py`, with zero change to pipeline behavior.

**Architecture:** A small, independently unit-testable `@contextmanager step_guard(...)` handles the BEST-EFFORT variants only (BS = best-effort-with-`*_status`; B = best-effort-no-status). On `__enter__` it fires `lease.step(name)` (the #25 timing breadcrumb, at the same point as today); on clean exit it sets `lease.status(<key>="ok")` when a `status_key` is given; on `LeaseRevokedError` it re-raises (propagate); on any other `Exception` it logs a warning, sets `lease.status(<key>="failed")` when a `status_key` is given, and swallows. The single FATAL step (`_step_evaluate`) and the genuinely-bespoke sites (the two `finviz_fetch` branches, `charts`'s three-way handler, `shadow_expectancy`'s failure-side `run_warnings` append, `complete`, and `review_log_cadence`'s LeaseRevoked-swallowing bare-`except`) stay EXPLICIT and untouched. A Phase-0 characterization matrix pins every guarded site's failure contract green against the current un-refactored code FIRST, then the extraction keeps it green.

**Tech Stack:** Python 3.14, `contextlib.contextmanager`, pytest (`monkeypatch`, `caplog`), `ast` for the completeness guard. No new dependency, no schema, no `swing/data`/`swing/trades`/config/pyproject touch.

---

## Background — re-grounding (verified on disk at branch start, HEAD `43e9a5e8`, `runner.py` 4,529 lines)

`run_pipeline_internal` (`swing/pipeline/runner.py:544`; reached via the public `run_pipeline` at `swing/pipeline/__init__.py:14`) contains **15 `lease.step("…")` breadcrumb call sites** plus **one breadcrumb-less guarded call** (`_step_review_log_cadence`). `LeaseRevokedError` is `class LeaseRevokedError(Exception)` (`swing/data/repos/pipeline.py:15`) — a plain `Exception` subclass, so an `except LeaseRevokedError: raise` placed BEFORE `except Exception:` is what makes revoke propagate; a bare `except Exception:` with no prior `LeaseRevokedError` clause SWALLOWS it. The runner logger is `log = logging.getLogger(__name__)` → records emit on `"swing.pipeline.runner"` (`runner.py:122`). `lease.step(name: str)` and `lease.status(**cols: str)` (`swing/pipeline/lease.py:104,156`); the allowed `*_status` columns are EXACTLY `weather_status, evaluation_status, watchlist_status, recommendations_status, charts_status, export_status` (`swing/data/repos/pipeline.py:97-98`).

### The single-source site inventory (THE canonical artifact — Task 0 encodes it verbatim)

| # | step name | line | variant | `status_key` | wrapped by `step_guard`? | injection target (dotted) | inbox state | on-Exception run state | on-Exception status | LeaseRevoked propagates? |
|---|-----------|------|---------|--------------|--------------------------|---------------------------|-------------|------------------------|---------------------|--------------------------|
| 1 | `finviz_fetch` (site-1, inline empty-inbox recovery) | 653 | **F-bespoke** | — | **NO (explicit, untouched)** | `swing.pipeline.runner._step_finviz_fetch` | EMPTY | run aborts → `RunResult(state="failed")` (`lease.release`+`return`) | — | YES (`raise`; not inside the L741 try → propagates out of `run_pipeline`) |
| 2 | `weather` | 742 | **BS** | `weather_status` | **YES** | `swing.weather.classifier.classify_weather` (inline step) | csv | `complete` (continue) | `failed` | YES |
| 3 | `finviz_fetch` (site-2) | 777 | **B** | — | **NO (explicit — unconditional breadcrumb + conditional `finviz_fetched_inline` skip body)** | `swing.pipeline.runner._step_finviz_fetch` | csv | `complete` (continue) | — | YES |
| 4 | `evaluate` | 836 | **F (FATAL)** | `evaluation_status` | **NO (explicit, untouched — the only sanctioned fatal step)** | `swing.pipeline.runner._step_evaluate` | csv | run aborts → `RunResult(state="failed")` | `failed` | YES |
| 5 | `daily_management` | 855 | **B (custom log text)** | — | **YES** | `swing.pipeline.runner._step_daily_management` | csv | `complete` | — | YES |
| 6 | `watchlist` | 875 | **BS** | `watchlist_status` | **YES** | `swing.pipeline.runner._step_watchlist` | csv | `complete` | `failed` | YES |
| 7 | `recommendations` | 887 | **BS** | `recommendations_status` | **YES** | `swing.pipeline.runner._step_recommendations` | csv | `complete` | `failed` | YES |
| 8 | `pattern_detect` | 905 | **B** | — | **YES** | `swing.pipeline.runner._step_pattern_detect` | csv | `complete` | — | YES |
| 9 | `pattern_observe` | 924 | **B** | — | **YES** | `swing.pipeline.runner._step_pattern_observe` | csv | `complete` | — | YES |
| 10 | `schwab_snapshot` | 951 | **B (custom log text; logs `type(exc).__name__`)** | — | **YES** | `swing.integrations.schwab.pipeline_steps._step_schwab_snapshot` (LOCAL import) | csv | `complete` | — | YES |
| 11 | `schwab_orders` | 980 | **B (custom log text; logs `type(exc).__name__`)** | — | **YES** | `swing.integrations.schwab.pipeline_steps._step_schwab_orders` (LOCAL import) | csv | `complete` | — | YES |
| 12 | `charts` | 1007 | **BS (THREE-way: `ChartingUnavailableError`→`charts_status="skipped"` no-warn; else→`failed`)** | `charts_status` | **NO (explicit, untouched — the typed third branch is not worth contorting the guard for; same §3 logic as `evaluate`)** | `swing.pipeline.runner._step_charts` | csv | `complete` | `failed` (or `skipped` for `ChartingUnavailableError`) | YES |
| 13 | `export` | 1024 | **BS** | `export_status` | **YES** | `swing.pipeline.runner._step_export` | csv | `complete` | `failed` | YES |
| 14 | `shadow_expectancy` | 1046 | **B (+ appends a `run_warnings` entry in the FAILURE handler)** | — | **NO (explicit, untouched — LOCK #2: `run_warnings` stays in the site, never the guard)** | `swing.pipeline.runner._step_shadow_expectancy` | csv | `complete` | — (+ one `run_warnings` dict) | YES |
| 15 | `complete` | 1063 | **TERMINAL (breadcrumb + `lease.release`)** | — | **NO (no step body — breadcrumb only)** | — (no injectable body) | csv | n/a | n/a | n/a |
| — | `review_log_cadence` | 1065 | **OUTSIDE (plain call under the `complete` breadcrumb; bare `except Exception` — NO prior `LeaseRevokedError: raise`)** | — | **NO (explicit, untouched — wrapping it would ADD a breadcrumb [LOCK #1 violation] AND re-raise LeaseRevoked [behavior change])** | `swing.pipeline.runner._step_review_log_cadence` | csv | `complete` | — | **NO — bare `except` SWALLOWS LeaseRevokedError; run completes** |

**Wrapped set (9): `weather, daily_management, watchlist, recommendations, pattern_detect, pattern_observe, schwab_snapshot, schwab_orders, export`.** Everything else stays byte-identical and explicit. This matches §3's "the win is the ~9–10 best-effort sites."

### Two nuances the brief told me to resolve precisely

- **`review_log_cadence` (the breadcrumb-less site):** it has **no `lease.step("review_log_cadence")` breadcrumb** — it runs under the `complete` breadcrumb (`runner.py:1063-1070`) and its handler is a **bare `except Exception`** with **no `except LeaseRevokedError: raise`** before it. So it **does not propagate LeaseRevokedError** (it swallows it). It is OUTSIDE the guard set: wrapping it would both add a breadcrumb (violating LOCK #1) and change the revoke contract. **Left untouched.** Its divergent revoke behavior is pinned in Task 0 as a permanent regression.
- **The two `finviz_fetch` sites:** site-1 (`runner.py:653`, inside the empty-inbox `NoFilesError` recovery branch) is **FATAL** (`log.error`→`lease.release(state="failed")`→`return RunResult(state="failed")`) and structurally bespoke (it snapshots `pre_call_max_id`, runs a diagnostic read, has two nested error paths); site-2 (`runner.py:777`/`791`) is **best-effort-continue (B)** but fires its breadcrumb UNCONDITIONALLY and then runs its body only when `finviz_fetched_inline` is `False`. **Neither is wrapped** — site-1 because it is fatal+bespoke (same disposition as `evaluate`), site-2 because the breadcrumb must fire even when the body is skipped (LOCK #1: wrapping would move/double-fire the breadcrumb). Both are pinned in Task 0.

> **CHARC routing check (per the dispatch brief):** site-1 `finviz_fetch` being FATAL is a SECOND fatal control-flow site beyond `evaluate`. It does **NOT** change the guard's variant set, because — exactly like `evaluate` — it stays EXPLICIT and is never wrapped; the guard still handles only BS + B. The brief already anticipated two `finviz_fetch` sites and asked me to enumerate/tag them. This is surfaced to CHARC in the return report for visibility, but it does **not** require re-routing: no new module, no schema, no dependency, no change to the settled §3 abstraction. If execution discovers a way this forces a guard change, STOP and route to CHARC.

### Disciplines preserved (CLAUDE.md §Gotchas)

- **#25 per-step timings** — `lease.step(name)` is the Arc-1 timing breadcrumb; the guard fires it in `__enter__`, at the same point (before the body) as today. No breadcrumb added/moved/renamed.
- **#27 `run_warnings` semantics** — the accumulator is threaded into step BODIES only; the guard never references `run_warnings`. `shadow_expectancy` (which appends to `run_warnings` in its FAILURE handler) and `schwab_orders` (which `run_warnings.extend(...)` inside its body) keep that logic in the site, not the guard.
- **#16 fetch-hoist** — the `read_or_fetch_archive` warm hoist is not in the wrapper boilerplate; untouched.
- **LeaseRevokedError propagation contract** — the guard re-raises it; a planted-revoke test proves it is never swallowed. The one site that legitimately swallows it (`review_log_cadence`) is left explicit.

---

## File Map

- **Create:** `swing/pipeline/step_guard.py` — the `step_guard` context manager (the only new production module). Pipeline-internal; NOT in `swing/data` or `swing/trades`.
- **Modify:** `swing/pipeline/runner.py` — rewrite the 9 wrapped best-effort call sites to `with step_guard(...):`. No step body, no explicit site (evaluate/finviz/charts/shadow/complete/review_log_cadence) touched.
- **Create:** `tests/pipeline/test_step_guard.py` — unit tests for the context manager in isolation (fake lease, no DB).
- **Create:** `tests/pipeline/test_step_failure_characterization.py` — the Phase-0 characterization matrix (drives real `run_pipeline`; parametrized over the single-source inventory) + the AST completeness guard. Lands GREEN against current code in Task 0, stays green through the extraction.
- **Keep green (do not rewrite):** `tests/pipeline/test_e2e.py`, `tests/pipeline/test_run_pipeline_internal_empty_finviz_inbox_auto_fetch.py`, `tests/pipeline/test_step_finviz_fetch_ordering.py`, `tests/integrations/test_pipeline_log_redaction.py`, `tests/test_cli_log_surface.py`.

**Executing worktree (for the executing-plans cycle that follows this plan): `<repo>/.worktrees/arc17b-exec`.**

---

## Task 0: Phase-0 failure-mode characterization (BINDING PRECONDITION — lands GREEN on current, un-refactored code)

**Files:**
- Create: `tests/pipeline/test_step_failure_characterization.py`

This task ships the permanent regression that proves byte-identical behavior. It must pass against the CURRENT code BEFORE any extraction. The extraction tasks (1–4) must keep it green at every step.

- [ ] **Step 1: Write the single-source inventory + the characterization harness**

Create `tests/pipeline/test_step_failure_characterization.py`. The inventory list is the ONE source of truth; the parametrized tests and the AST completeness guard both consume it.

```python
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
```

Note: confirm the `pipeline_step_timings` column names (`step_name`, `ordinal`) against `swing/data/repos/pipeline_step_timings.py` when landing this; prefer calling the repo's `list_step_timings` helper if it returns rows in `ordinal` order. This is the first thing Phase-0 will surface.

- [ ] **Step 2: Write the happy-path breadcrumb completeness assertion**

```python
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
```

- [ ] **Step 3: Write the parametrized Exception-injection contract**

```python
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
```

> **Phase-0 robustness note:** if the pipeline's `install_logging` composition root detaches propagation to the root logger (so `caplog` sees nothing), assert against the rendered `pipeline.log` file under the tmp config instead (the existing redaction tests `tests/integrations/test_pipeline_log_redaction.py` read that surface) — that is an even more faithful LOCK #5 check (the actual rendered line). Resolve this when landing Task 0 green; the `expected_warning` strings are unchanged either way. The same byte-identical strings must still hold AFTER the extraction (Tasks 2/4) — that is the whole point of pinning them now.

Note on the two excluded names: `evaluate` (FATAL → `state="failed"`, asserted separately in Step 5) and `finviz_fetch_site1` (FATAL + needs the empty-inbox fixture, asserted separately in Step 5). `charts`'s generic-Exception branch IS exercised here (`charts_status == "failed"`); its `ChartingUnavailableError`→`"skipped"` branch is pinned in Step 6.

- [ ] **Step 4: Write the planted-`LeaseRevokedError` propagation contract**

```python
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
```

This is the load-bearing divergence pin: `review_log_cadence` is the ONE site where `revoke_propagates is False`. If a future refactor wraps it in `step_guard` (which re-raises), this test flips red.

- [ ] **Step 5: Pin the two FATAL sites explicitly**

```python
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
```

- [ ] **Step 6: Pin the `charts` `ChartingUnavailableError`→`skipped` branch**

```python
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
```

- [ ] **Step 7: Write the AST completeness guard (the DIVERGENCES-inventory pattern)**

Mirrors `tests/integration/test_include_baseline_inventory_guard.py`: an AST scan of `runner.py` enumerates every `lease.step(<string literal>)` call; the multiset of names MUST equal the inventory's expectation. A site added later without an inventory entry fails this test.

This matcher counts BOTH forms of a step-site breadcrumb literal so it is green on the CURRENT code (where all 15 are `lease.step("X")` and there are zero `step_guard(...)` calls) AND after the extraction (where 9 literals move into `step_guard(lease, "X", ...)` 2nd-positional args and 6 stay as `lease.step("X")`). No mid-plan edit is needed — the expected multiset is identical in both states.

```python
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
        elif ((getattr(func, "id", None) == "step_guard"
               or getattr(func, "attr", None) == "step_guard")
                and len(node.args) >= 2
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
```

- [ ] **Step 8: Run the full Task-0 suite GREEN against the CURRENT (un-refactored) code**

Run: `python -m pytest tests/pipeline/test_step_failure_characterization.py -v`
Expected: ALL PASS. This is the binding precondition — the extraction does not begin until this is green on `HEAD` with zero `step_guard` code present. Fix any harness issues here (e.g. the `step_name` column name, a step body that no-ops with the stubbed `eval_run_id=1`, the `complete` breadcrumb ordering) NOW, while behavior is the un-refactored baseline.

- [ ] **Step 9: Commit**

```bash
git add tests/pipeline/test_step_failure_characterization.py
git commit -m "test(pipeline): Arc 17-B Phase-0 step-failure characterization matrix"
```

---

## Task 1: the `step_guard` context manager (TDD, unit-tested in isolation)

**Files:**
- Create: `swing/pipeline/step_guard.py`
- Create: `tests/pipeline/test_step_guard.py`

The guard is unit-tested against a FAKE lease (no DB, no pipeline) so its contract is proven independently of the runner.

- [ ] **Step 1: Write the failing unit tests**

Create `tests/pipeline/test_step_guard.py`:

```python
"""Unit tests for swing.pipeline.step_guard — the best-effort step wrapper."""
from __future__ import annotations

import logging

import pytest

from swing.data.repos.pipeline import LeaseRevokedError
from swing.pipeline.step_guard import step_guard


class FakeLease:
    def __init__(self):
        self.steps: list[str] = []
        self.statuses: dict[str, str] = {}

    def step(self, name: str) -> None:
        self.steps.append(name)

    def status(self, **cols: str) -> None:
        self.statuses.update(cols)


def test_enter_fires_lease_step_before_body():
    lease = FakeLease()
    seen_at_body = None
    with step_guard(lease, "weather", status_key="weather_status",
                    logger=logging.getLogger("t")):
        seen_at_body = list(lease.steps)
    assert seen_at_body == ["weather"]          # breadcrumb fired on __enter__
    assert lease.statuses == {"weather_status": "ok"}


def test_clean_exit_no_status_key_sets_nothing():
    lease = FakeLease()
    with step_guard(lease, "pattern_detect", logger=logging.getLogger("t")):
        pass
    assert lease.steps == ["pattern_detect"]
    assert lease.statuses == {}                 # B site: no status surface


def test_lease_revoked_propagates():
    lease = FakeLease()
    with pytest.raises(LeaseRevokedError):
        with step_guard(lease, "weather", status_key="weather_status",
                        logger=logging.getLogger("t")):
            raise LeaseRevokedError("revoked")
    assert lease.statuses == {}                 # no "ok", no "failed" on revoke


def test_other_exception_swallowed_status_failed(caplog):
    lease = FakeLease()
    log = logging.getLogger("swing.pipeline.runner")
    with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
        with step_guard(lease, "watchlist", status_key="watchlist_status",
                        logger=log):
            raise RuntimeError("boom")
    assert lease.statuses == {"watchlist_status": "failed"}
    assert "watchlist failed: boom" in caplog.text
    assert caplog.records[0].name == "swing.pipeline.runner"   # LOCK #5 logger name


def test_other_exception_swallowed_no_status_key(caplog):
    lease = FakeLease()
    log = logging.getLogger("swing.pipeline.runner")
    with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
        with step_guard(lease, "pattern_detect", logger=log):
            raise RuntimeError("boom")
    assert lease.statuses == {}                 # B site: no status flip on failure
    assert "pattern_detect failed: boom" in caplog.text


def test_exception_from_ok_status_write_is_caught_not_propagated(caplog):
    """Byte-identical to the inline sites: the success ``lease.status(ok)`` is
    INSIDE the guarded try, so if it raises a non-revoke Exception the guard
    logs + writes 'failed' + swallows (does NOT propagate). (Codex R1 #1.)"""
    class OkRaisesLease(FakeLease):
        def status(self, **cols: str) -> None:
            if cols.get("weather_status") == "ok":
                raise RuntimeError("ok-write boom")
            super().status(**cols)

    lease = OkRaisesLease()
    log = logging.getLogger("swing.pipeline.runner")
    with caplog.at_level(logging.WARNING, logger="swing.pipeline.runner"):
        with step_guard(lease, "weather", status_key="weather_status", logger=log):
            pass  # clean body; the failure comes from the ok-status write
    assert lease.statuses == {"weather_status": "failed"}
    assert "weather failed: ok-write boom" in caplog.text


def test_custom_log_failure_callable_preserves_exact_text():
    lease = FakeLease()
    captured = []
    with step_guard(
        lease, "schwab_snapshot",
        logger=logging.getLogger("t"),
        log_failure=lambda lg, name, exc: captured.append(
            f"{name} failed (continuing pipeline): {type(exc).__name__}"),
    ):
        raise KeyError("x")
    assert captured == ["schwab_snapshot failed (continuing pipeline): KeyError"]
    assert lease.statuses == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/pipeline/test_step_guard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'swing.pipeline.step_guard'`.

- [ ] **Step 3: Write the minimal `step_guard` implementation**

Create `swing/pipeline/step_guard.py`:

```python
"""The best-effort per-step wrapper for the pipeline runner (Arc 17-B).

Collapses the repeated ``lease.step(name)`` + ``try/except LeaseRevokedError/
except Exception`` boilerplate around best-effort step calls into one tested
context manager. Handles ONLY the two best-effort variants:

  * BS (best-effort + status): pass ``status_key`` -> sets ``<key>="ok"`` on
    clean exit, ``<key>="failed"`` when the body raises a non-revoke Exception.
  * B  (best-effort, no status): omit ``status_key`` -> no status writes.

NOT handled here (left explicit in runner.py): the FATAL ``evaluate`` step
(returns RunResult from run_pipeline -- a context manager cannot), the two
``finviz_fetch`` branches, ``charts`` (a three-way typed handler), the
``shadow_expectancy`` failure-side run_warnings append (gotcha #27 keeps
run_warnings in the SITE, never the guard), ``complete``, and
``review_log_cadence`` (a bare-except site that deliberately swallows
LeaseRevokedError).

LOCK invariants (Arc 17-B brief §5): lease.step fires in __enter__ at the same
point as today (#25); LeaseRevokedError ALWAYS re-raises (#4); the failure log
emits on the caller-supplied ``logger`` so records keep the runner logger name
-> the RENDERED log line, logger name, level, and message are byte-identical and
redaction routing + the [logging.loggers] override table are unaffected (#5; see
the Round-2 caller-metadata caveat in the plan's design notes); the guard never
touches run_warnings (#27).
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from swing.data.repos.pipeline import LeaseRevokedError


@contextmanager
def step_guard(
    lease,
    name: str,
    *,
    logger: logging.Logger,
    status_key: str | None = None,
    log_failure: Callable[[logging.Logger, str, Exception], None] | None = None,
) -> Iterator[None]:
    """Wrap a best-effort pipeline step.

    Args:
        lease: the run lease (provides ``.step(name)`` and ``.status(**cols)``).
        name: the step name -> the ``lease.step`` timing breadcrumb (#25).
        logger: the logger used for the default failure warning. The runner
            passes its own ``log`` so records emit on ``swing.pipeline.runner``
            (LOCK #5 byte-identical log surface).
        status_key: the ``*_status`` column for a BS site, or None for a B site.
        log_failure: optional override invoked as ``log_failure(logger, name,
            exc)`` to reproduce a site's exact current warning text (e.g. the
            ``"... (continuing pipeline): <type>"`` schwab wording). When None,
            the default ``logger.warning("%s failed: %s", name, exc)`` is used.
    """
    lease.step(name)
    try:
        yield
        # The success status write lives INSIDE the try (not an `else:`) so it
        # has byte-identical behavior to the inline runner sites, where
        # `lease.status(<key>="ok")` sits inside the step `try` (e.g. weather
        # runner.py:770, watchlist:880, recommendations:893, export:1031): if
        # the "ok" write itself raises a non-revoke Exception, the current code
        # logs the warning + writes "failed" + continues. An `else:` clause
        # would let that exception PROPAGATE -- a behavior change. (Codex R1 #1.)
        if status_key is not None:
            lease.status(**{status_key: "ok"})
    except LeaseRevokedError:
        raise
    except Exception as exc:  # noqa: BLE001 -- best-effort swallow by design
        if log_failure is not None:
            log_failure(logger, name, exc)
        else:
            logger.warning("%s failed: %s", name, exc)
        if status_key is not None:
            lease.status(**{status_key: "failed"})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_step_guard.py -v`
Expected: ALL PASS.

- [ ] **Step 5: ruff the new module**

Run: `ruff check swing/pipeline/step_guard.py tests/pipeline/test_step_guard.py`
Expected: clean (the `# noqa: BLE001` is intentional — the broad catch is the documented best-effort contract).

- [ ] **Step 6: Commit**

```bash
git add swing/pipeline/step_guard.py tests/pipeline/test_step_guard.py
git commit -m "feat(pipeline): add step_guard best-effort step wrapper context manager"
```

---

## Task 2: rewrite the BS-default sites (`weather`, `watchlist`, `recommendations`, `export`)

These four use the DEFAULT warning text (`"<name> failed: %s", exc`) and have a `*_status` column. Rewrite each to `with step_guard(...)`, passing `logger=log`.

**Files:**
- Modify: `swing/pipeline/runner.py` (the four call sites)

- [ ] **Step 1: Rewrite `weather` (runner.py ~742-775)**

The weather step is INLINE (no `_step_weather`). Wrap the existing inline body. Replace:

```python
            lease.step("weather")
            try:
                from swing.data.models import WeatherRun
                # ... inline body ...
                lease.status(weather_status="ok")
            except LeaseRevokedError:
                raise
            except Exception as exc:
                log.warning("weather failed: %s", exc)
                lease.status(weather_status="failed")
```

with:

```python
            with step_guard(lease, "weather", status_key="weather_status", logger=log):
                from swing.data.models import WeatherRun
                # ... inline body UNCHANGED ...
                # (delete the trailing `lease.status(weather_status="ok")` -- the
                #  guard sets it on clean exit)
```

Keep every line of the inline body byte-identical; only the wrapper changes. Delete the now-redundant `lease.status(weather_status="ok")` inside the body (the guard's clean-exit path sets it).

- [ ] **Step 2: Rewrite `watchlist` (runner.py ~875-885)**

```python
            with step_guard(lease, "watchlist", status_key="watchlist_status", logger=log):
                _step_watchlist(cfg=cfg, eval_run_id=eval_run_id,
                                data_asof_date=lease_data_asof(cfg, lease),
                                lease=lease, run_warnings=run_warnings)
```

(`run_warnings` stays an argument to the BODY — the guard never sees it. LOCK #27.)

- [ ] **Step 3: Rewrite `recommendations` (runner.py ~887-898)**

```python
            with step_guard(lease, "recommendations",
                            status_key="recommendations_status", logger=log):
                _step_recommendations(cfg=cfg, eval_run_id=eval_run_id,
                                       action_session=action_session,
                                       data_asof=lease_data_asof(cfg, lease),
                                       lease=lease)
```

- [ ] **Step 4: Rewrite `export` (runner.py ~1024-1036)**

```python
            with step_guard(lease, "export", status_key="export_status", logger=log):
                _step_export(cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                             action_session=action_session,
                             data_asof=lease_data_asof(cfg, lease),
                             chart_paths=chart_paths,
                             fetcher=fetcher)
```

- [ ] **Step 5: Add the `step_guard` import to runner.py**

Add near the other `swing.pipeline` imports (top of file). Import the symbol DIRECTLY by its real name — do NOT alias it (`as sg`) and do NOT call it attribute-qualified (`mod.step_guard(...)`); the AST completeness guard counts bare-name and attribute calls but the no-alias rule keeps the matcher unambiguous (Codex R1 #5):

```python
from swing.pipeline.step_guard import step_guard
```

- [ ] **Step 6: Run the characterization + the BS-status pipeline tests**

Run: `python -m pytest tests/pipeline/test_step_failure_characterization.py tests/pipeline/test_e2e.py -v`
Expected: ALL PASS (the four rewritten sites' `weather`/`watchlist`/`recommendations`/`export` Exception cases still flip `*_status` to `failed`; the happy path still sets `ok`; breadcrumbs unchanged).

- [ ] **Step 7: Commit**

```bash
git add swing/pipeline/runner.py
git commit -m "refactor(pipeline): route the four BS-status steps through step_guard"
```

---

## Task 3: rewrite the B-default sites (`pattern_detect`, `pattern_observe`)

Best-effort, no status, default warning text. Pure `with step_guard(lease, name, logger=log):`.

**Files:**
- Modify: `swing/pipeline/runner.py`

- [ ] **Step 1: Rewrite `pattern_detect` (runner.py ~905-917)**

```python
            with step_guard(lease, "pattern_detect", logger=log):
                _step_pattern_detect(
                    cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                    ohlcv_cache=ohlcv_cache, run_warnings=run_warnings,
                )
```

- [ ] **Step 2: Rewrite `pattern_observe` (runner.py ~924-933)**

```python
            with step_guard(lease, "pattern_observe", logger=log):
                _step_pattern_observe(
                    cfg=cfg, lease=lease, ohlcv_cache=ohlcv_cache,
                    run_warnings=run_warnings,
                )
```

- [ ] **Step 3: Run the characterization**

Run: `python -m pytest tests/pipeline/test_step_failure_characterization.py -v`
Expected: ALL PASS (both sites continue on Exception with no status flip; breadcrumbs intact; planted revoke aborts).

- [ ] **Step 4: Commit**

```bash
git add swing/pipeline/runner.py
git commit -m "refactor(pipeline): route pattern_detect and pattern_observe through step_guard"
```

---

## Task 4: rewrite the custom-log-text sites (`daily_management`, `schwab_snapshot`, `schwab_orders`)

These three keep their EXACT current warning text via a `log_failure` callable. `daily_management` logs `exc`; the two schwab steps log `type(exc).__name__`. The schwab steps' bodies (the `_conn = connect(...)` / `try…finally _conn.close()`, and `schwab_orders`' `run_warnings.extend(...)`) stay INSIDE the `with` block, unchanged (LOCK #27 — run_warnings stays in the body).

**Files:**
- Modify: `swing/pipeline/runner.py`

- [ ] **Step 1: Rewrite `daily_management` (runner.py ~855-873)**

```python
            with step_guard(
                lease, "daily_management", logger=log,
                log_failure=lambda lg, name, exc: lg.warning(
                    "daily_management step programming error (continuing): %s", exc),
            ):
                _step_daily_management(
                    lease=lease, run_now=run_now, eval_run_id=eval_run_id,
                    archive_history_days=cfg.archive.archive_history_days,
                    ohlcv_archive_dir=cfg.paths.prices_cache_dir,
                    run_warnings=run_warnings,
                )
```

- [ ] **Step 2: Rewrite `schwab_snapshot` (runner.py ~951-978)**

```python
            with step_guard(
                lease, "schwab_snapshot", logger=log,
                log_failure=lambda lg, name, exc: lg.warning(
                    "schwab_snapshot failed (continuing pipeline): %s",
                    type(exc).__name__),
            ):
                from swing.integrations.schwab.pipeline_steps import (
                    _step_schwab_snapshot,
                )
                _conn = connect(cfg.paths.db_path)
                try:
                    _step_schwab_snapshot(
                        _conn, cfg, pipeline_run_id=lease.run_id,
                        client=schwab_client, surface="pipeline",
                    )
                finally:
                    _conn.close()
```

- [ ] **Step 3: Rewrite `schwab_orders` (runner.py ~980-1005)**

```python
            with step_guard(
                lease, "schwab_orders", logger=log,
                log_failure=lambda lg, name, exc: lg.warning(
                    "schwab_orders failed (continuing pipeline): %s",
                    type(exc).__name__),
            ):
                from swing.integrations.schwab.pipeline_steps import (
                    _step_schwab_orders,
                )
                _conn = connect(cfg.paths.db_path)
                try:
                    _schwab_result = _step_schwab_orders(
                        _conn, cfg, pipeline_run_id=lease.run_id,
                        client=schwab_client, surface="pipeline",
                    )
                    _schwab_warnings = (_schwab_result or {}).get("warnings") or []
                    if _schwab_warnings:
                        run_warnings.extend(_schwab_warnings)
                finally:
                    _conn.close()
```

- [ ] **Step 4: Run the characterization + the log-surface tests**

Run: `python -m pytest tests/pipeline/test_step_failure_characterization.py tests/integrations/test_pipeline_log_redaction.py tests/test_cli_log_surface.py -v`
Expected: ALL PASS. (The custom warning text is byte-identical; the schwab steps still continue on Exception; the planted revoke still aborts.)

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/runner.py
git commit -m "refactor(pipeline): route daily_management and schwab steps through step_guard"
```

---

## Task 5: final verification gate (§7) + leftover-explicit-sites confirmation

**Files:**
- (verification only; no new edits expected)

- [ ] **Step 1: Confirm the explicit sites were NOT touched**

Run: `git diff HEAD~4 -- swing/pipeline/runner.py | grep -n "lease.step(\"evaluate\")\|lease.step(\"charts\")\|lease.step(\"shadow_expectancy\")\|lease.step(\"complete\")\|_step_review_log_cadence\|finviz_fetch"`
Expected: the `evaluate`, `charts`, `shadow_expectancy`, `complete`, `review_log_cadence`, and both `finviz_fetch` blocks show NO change (they appear only as unchanged context, not as `+`/`-` lines for their wrapper logic). Visually confirm the FATAL `evaluate` path still returns `RunResult(state="failed")` inline and `shadow_expectancy` still appends to `run_warnings` in its handler.

- [ ] **Step 2: Re-run the AST completeness guard**

Run: `python -m pytest tests/pipeline/test_step_failure_characterization.py::test_runner_step_sites_match_inventory -v`
Expected: PASS unchanged. The matcher (written in Task 0 Step 7) already counts BOTH `lease.step("X")` (the 6 remaining explicit sites: finviz×2, evaluate, charts, shadow_expectancy, complete) AND `step_guard(lease, "X", ...)` (the 9 wrapped sites) → multiset still equals the inventory. No matcher edit is needed here.

- [ ] **Step 3: ruff the whole touched surface**

Run: `ruff check swing/pipeline/`
Expected: clean.

- [ ] **Step 4: Full fast suite (no-false-green — run on the MERGED head shape)**

Run: `python -m pytest -m "not slow" -q`
Expected: green; the baseline (~8053 fast tests) plus the new `test_step_guard.py` cases and the characterization module. READ the actual final line; do not carry a branch count forward.

- [ ] **Step 5: Smoke — a real pipeline run completes**

Run the slow e2e to confirm an actual pipeline run still completes normally end-to-end:
Run: `python -m pytest tests/pipeline/test_e2e.py -v`
Expected: `test_pipeline_e2e_smoke` and `test_pipeline_e2e_realistic_batch` PASS (`result.state == "complete"`, the `*_status` columns all `ok`, briefing emitted). This is the orchestrator's smoke check per §7. (The orchestrator additionally drives a real `swing pipeline run` at QA; no operator-witnessed live gate is required.)

- [ ] **Step 6: No-op check — nothing left uncommitted**

Run: `git status --short`
Expected: clean working tree (all edits committed in Tasks 0–4). If the verification surfaced any required fix, commit it with a `refactor(pipeline):` or `test(pipeline):` message (plain-prose final paragraph; ZERO `Co-Authored-By`).

---

## Design notes — faithfulness to §3 and the explicit-site decisions (for QA / CHARC visibility)

- **The guard handles ONLY BS + B** (the settled §3 shape). It is a `@contextmanager`, independently unit-tested (Task 1), pipeline-internal (`swing/pipeline/`), no new dependency, no schema, no `swing/data`/`swing/trades`/config/pyproject touch.
- **`logger` is a required keyword param.** §3's illustration (`step_guard(lease, "watchlist", status_key=...)`) is schematic. The `logger` param exists solely to keep failure-warning records on `"swing.pipeline.runner"` (LOCK #5) rather than a new `"swing.pipeline.step_guard"` logger. This is a mechanical realization of "preserve the log surface," not a §3 abstraction change. Phase-0 pins `record.name == "swing.pipeline.runner"`.
- **LOCK #5 log-surface claim, scoped precisely (Codex R2 #1).** "Byte-identical log surface" means the RENDERED log line, the logger **name**, the **level**, and the **message** are unchanged — which is exactly what the active formatter emits (`logging_config.py:23` = `%(name)s … %(message)s`, no caller metadata) and what redaction-by-construction + the `[logging.loggers]` override table key on. The `LogRecord` **caller-metadata** fields (`pathname`/`filename`/`module`/`funcName`/`lineno`) DO shift — for the 6 default-path sites the warning now emits from `step_guard.py`; for the 3 custom-`log_failure` sites it emits from the lambda defined in `runner.py`. This is **acceptable**: no formatter, no test, and no operator surface in the repo consumes those fields (the Phase-0 characterization asserts `record.name` + message text, not `funcName`/`lineno`). We deliberately do NOT chase `stacklevel` gymnastics through the contextmanager frame for V1 — it would not even resolve to the `with`-site reliably and buys nothing the rendered line shows.
- **`log_failure` is a callable, not a plain message string.** §3 sanctions "an overridable message/level param to preserve a step's exact current log text." A plain string is insufficient because `schwab_snapshot`/`schwab_orders` log `type(exc).__name__` (a per-exception dynamic value), not `exc`. A `(logger, name, exc) -> None` callable is the minimal faithful realization. Only 3 sites use it.
- **`charts` stays EXPLICIT** (not wrapped). Its handler is a THREE-way branch (`ChartingUnavailableError`→`charts_status="skipped"` with NO warning; else→`"failed"`). Forcing the guard to support a typed exception→status mapping would add a `skip_statuses`-style param for ONE site — net-negative by the exact §3 logic that keeps `evaluate` explicit ("contorting the guard … for ONE site"). Rejected alternative: a `skip_statuses: Mapping[type, str]` param. Left explicit; Phase-0 pins both its `failed` and `skipped` branches.
- **`shadow_expectancy` stays EXPLICIT.** Its failure handler appends to `run_warnings` (gotcha #27). LOCK #2 forbids the guard from touching `run_warnings`; the failure-side append can only happen after the exception is caught (inside a handler), so it must stay in the site. Wrapping it would either drop the warning entry or leak `run_warnings` into the guard.
- **Both `finviz_fetch` sites and `complete` and `review_log_cadence` stay EXPLICIT** per the inventory rationale above. `review_log_cadence`'s LeaseRevoked-swallowing bare-`except` is the load-bearing divergence pinned by `test_planted_lease_revoked_propagation`.
- **Scope boundary (§6) — DEFERRED, NOT done in this arc:** no relocation of the non-step infrastructure (the finviz CSV select at `runner.py:~4264-4576`, the shadow-expectancy helpers, the chart/briefing composers `~3076-3887`). 17-B is wrapper-extraction ONLY. If runner.py navigability still bites after this lands, infra relocation becomes a separate operator-decided candidate arc (17-B.2 / future).

## Return-report routing (§8)

The implementer reports to its ORCHESTRATOR as its FINAL CHAT message and NEVER posts to a director inbox / `role_mail`. The ORCHESTRATOR posts the return report to `charc,operator` AFTER its QA gate. No step in this plan instructs a mailbox post.
