# Fetch-vs-Write-Ordering Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the audit-writing OHLCV fetch OUT of the held `lease.fenced_write()` transaction at the two confirmed deadlock loci in `swing/pipeline/runner.py` (detect Pass-2 exemplar bars; observe detection bars), so the pipeline's `audit_conn` no longer deadlocks on the lease's write lock; then revert the busy_timeout stopgap.

**Architecture:** The universal rule (spec §4): *fetch happens with NO held `fenced_write`; the fence wraps only fast SQLite reads + the persist.* For detect Pass-2 we snapshot the exemplar corpus rows once before the fence and pre-fetch their bars there — that snapshot is the run's AUTHORITATIVE scoring membership (membership == prefetched bars by construction, so no silent score change), with a cheap in-fence eligible-ID re-read emitting a #27 divergence audit if a concurrent web/CLI writer mutated the eligible set mid-run. For observe we split the per-detection loop into a compute pass (idempotency / shed / `_bar_for_date` fetch / `_advance_status` / row-build) outside the fence and a write pass (one short fence around `insert_observation`). `_step_charts` is already correctly ordered and is NOT touched. Daily-management (#16) is BANKED per OQ-D and is NOT touched.

**Tech Stack:** Python 3.14, SQLite (`sqlite3`, WAL), pytest (`-m "not slow"`, xdist), pandas/numpy. No schema change (v24 holds); no new dependencies.

---

## Invariants this plan MUST preserve (propagate from spec §6 + dispatch brief §3)

- **Schema: NONE.** v24 holds. Zero migrations, zero CHECK changes, zero column adds.
- **Lease-fencing contract:** every WRITE still happens inside `fenced_write` with the in-tx lease check; only the FETCH moves out. The `canonical_existing` re-read (detect Pass-2 reconcile-before-serialize) and the INSERT loops STAY in-fence.
- **Audit single-tx discipline:** `audit_conn` / `_AUDIT_WRITE_LOCK` untouched. This arc removes the held lock so the audit's `BEGIN IMMEDIATE` no longer blocks.
- **#5 no-re-fetch / L2 LOCK:** Pass-1 `bars_by_ticker` reused unchanged; exemplar bars fetched exactly once (now outside the fence); no new re-fetch introduced.
- **#27 silent-skip-audit:** every new early-return / skip path emits a `warnings_json` entry (exemplar bar-fetch failure; exemplar eligible-ID mid-run divergence; the unchanged observe no-bar + shed audits).
- **#28/#29 exemplar OHLCV depth:** preserved by reusing the identical `get_or_fetch(window_days=400)` call params at the moved-out site (byte-for-byte).
- **Charts unchanged; daily-management (#16) BANKED (do NOT touch `_step_daily_management` / `daily_management.py` / `ohlcv_archive.py`).**
- **Process:** conventional commits (`fix(pipeline):`, `test(pipeline):`, `refactor(...)`, `chore(config):`); **ZERO `Co-Authored-By`**, no `--no-verify`; ASCII-only in all user-facing strings.

---

## STEP-0 grounding (already performed by the plan author — re-confirm if the tree moved)

The spec was grounded at HEAD `cadbff61`; this plan was authored on branch `fetch-vs-write-ordering-arc-writing-plans` off main HEAD `219698d7`. The docs-only commits since `cadbff61` did NOT shift `runner.py`; every cited line matches the spec:

| Citation | Confirmed at | What |
|----------|--------------|------|
| `runner.py:1898` | unchanged | detect Pass-2 `with lease.fenced_write() as conn:` |
| `runner.py:1920` | unchanged | `canonical_existing` re-read (STAYS in-fence) |
| `runner.py:1973-2024` | unchanged | in-fence exemplar build (`list_exemplars` @1977, `get_or_fetch` @1994) — MOVES OUT |
| `runner.py:2036-2098` | unchanged | `resolved_emit_list` / `match_forward` loop (STAYS in-fence) |
| `runner.py:1714-1723` | unchanged | `detector_read_conn` cfg/`getattr(lease,"_conn",None)` discipline to MIRROR |
| `runner.py:2525` | unchanged | `ohlcv_cache.get_or_fetch` inside `_bar_for_date` |
| `runner.py:2576` | unchanged | `def _step_pattern_observe(*, cfg, lease, ohlcv_cache, run_warnings)` |
| `runner.py:2626-2627` | unchanged | `drain_telemetry()` reset (STAYS before the compute pass) |
| `runner.py:2628` | unchanged | observe `with lease.fenced_write() as conn:` |
| `runner.py:2662` | unchanged | `_bar_for_date(...)` (the fetch) |
| `runner.py:2675` | unchanged | `insert_observation(conn, ...)` (the only fence-needing op) |
| `swing.config.toml:128-137` | confirmed | `[web]` + `TEMPORARY STOPGAP` comment + `db_busy_timeout_ms = 5000` |
| `swing/config.py:397` | confirmed | `db_busy_timeout_ms: int = 30000` (dataclass default — deleting the toml key resolves to this) |
| `swing/data/db.py:54` | confirmed | `DEFAULT_BUSY_TIMEOUT_MS = 30000` |

Confirmed imports already in scope: `connect` (module-level `runner.py:18`), `TemplateMatchExemplar` (`runner.py:70`), `list_exemplars` (local import in `_step_pattern_detect` `runner.py:1513`), `pd` / `_np_pd_inner` (local in detect). `run_warnings: list[dict] | None = None` is threaded through `_step_pattern_detect` with `if run_warnings is not None` guards.

---

## File Map

| File | Change | Responsibility |
|------|--------|----------------|
| `swing/pipeline/runner.py` | Modify `_step_pattern_detect` (~1888-2024) | Snapshot exemplar corpus + pre-fetch bars BEFORE the fence; drop the in-fence `get_or_fetch`; add the OQ-E in-fence eligible-ID divergence guard. |
| `swing/pipeline/runner.py` | Modify `_step_pattern_observe` (~2620-2685) | Split compute pass (outside fence) / write pass (one short fence around `insert_observation`). |
| `swing.config.toml` | Modify `[web]` (128-137) | Delete the stopgap `db_busy_timeout_ms = 5000` key + the `TEMPORARY STOPGAP` comment block; add a one-line pointer. |
| `tests/pipeline/test_fetch_vs_write_ordering.py` | **Create** | The binding in-process deadlock-reproduction tests (both loci) + ordering / #5 / exemplar-failure-#27 / list_exemplars-once / OQ-E divergence / stopgap-revert tests. Shared `_DeadlockProbeCache` spy + `_seed_confirmed_exemplar` helper. |

Existing tests that MUST stay green (behavior-preserving parity — these are the §7.5 / §7.4(a) parity coverage; do NOT modify them):
`tests/pipeline/test_step_pattern_detect_template_matching.py`, `tests/pipeline/test_step_pattern_detect.py`, `tests/pipeline/test_step_pattern_observe.py`, `tests/pipeline/test_observe_load_instrumentation.py`, `tests/pipeline/test_pattern_pool_dormant_levers.py`, `tests/integration/test_phase14_temporal_log_e2e.py`, `tests/integration/test_phase13_t2_sb5_template_matching_e2e.py`.

---

## Shared test scaffolding (created in Task 1, reused by Tasks 2-4)

All new tests live in `tests/pipeline/test_fetch_vs_write_ordering.py`. The module begins with this scaffolding (the spy is the heart of the binding regression — it reproduces the Run-92 mechanism in-process):

```python
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

import pytest

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
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.0, date_=_OBS)):
        with patch("swing.pipeline.runner.lease_data_asof", return_value=_OBS):
            from swing.pipeline.runner import _step_pattern_observe
            _step_pattern_observe(cfg=cfg, lease=lease, ohlcv_cache=cache,
                                  run_warnings=warnings)
```

> **Why the spy returns bars even after observing the deadlock:** in the *pre-fix* detect code the exemplar `get_or_fetch` is wrapped in a `try/except Exception: continue` (`runner.py:1993-2021`). If the spy *raised* on the deadlock, that except would swallow it and the test could not distinguish the bug. So the spy records `deadlock_observed` from the probe and then returns normally; the assertion is on the flag, not on an exception.

> **Why this is discriminating (`feedback_regression_test_arithmetic`):** pre-fix the seeded exemplar/observe fetch executes while `_FakeLease.fenced_write()` holds `BEGIN IMMEDIATE` on the file DB → the spy's second-connection `BEGIN IMMEDIATE` blocks past 200 ms → `OperationalError` → `deadlock_observed=True` → the `assert ... is False` FAILS. Post-fix the fetch executes before the fence opens → the probe acquires + releases the write lock → `deadlock_observed=False` → PASS. Each test also asserts `get_or_fetch` fired (anti-false-pass per spec §7.1), so "no deadlock" cannot pass vacuously on a fixture that never reached the fetch.

---

## Task 1: Detect Pass-2 — snapshot exemplar corpus + pre-fetch bars OUTSIDE the fence

**Goal:** Eliminate deadlock locus #8. Read the exemplar corpus + fetch its bars once, before `with lease.fenced_write()`; that snapshot is the authoritative scoring membership. Drop the in-fence `get_or_fetch` (@1994). Emit a #27 audit when an exemplar's bars are unavailable. (The OQ-E in-fence ID divergence guard is layered on in Task 2.)

**Files:**
- Create: `tests/pipeline/test_fetch_vs_write_ordering.py`
- Modify: `swing/pipeline/runner.py` (`_step_pattern_detect`, ~1888-2024)

- [ ] **Step 1: Write the module scaffolding + the binding detect deadlock-repro test (RED).**

Create `tests/pipeline/test_fetch_vs_write_ordering.py` with the **Shared test scaffolding** block above, then append:

```python
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
```

- [ ] **Step 2: Run the test to verify it FAILS (reproduces the deadlock).**

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py::test_detect_pass2_exemplar_fetch_runs_outside_fence_no_deadlock -v`
Expected: **FAIL** — `assert cache.deadlock_observed is False` fails because the pre-fix exemplar `get_or_fetch` runs inside the held fence (`deadlock_observed` is `True`). (`"HIST" in cache.calls` already passes — the exemplar IS fetched, just in the wrong place.)

- [ ] **Step 3: Implement the reorder — insert the snapshot + pre-fetch block BEFORE the fence.**

In `swing/pipeline/runner.py`, between the `if not emit_queue:` early-return block (ending at `return`, ~1896) and `with lease.fenced_write() as conn:` (~1898), INSERT:

```python
    # ----------------------------------------------------------------------
    # Fetch-vs-write-ordering fix (locus #8): snapshot the exemplar corpus +
    # pre-fetch its bars OUTSIDE the lease.fenced_write() transaction. The
    # exemplar bar fetch is an audit-writing network call (Schwab market-data
    # ladder -> audit_conn BEGIN IMMEDIATE) that MUST NOT run under a held
    # fence, or audit_conn deadlocks on the lease's write lock (Run-92).
    #
    # OQ-A/C: this snapshot is the run's AUTHORITATIVE scoring membership.
    # Membership == prefetched bars BY CONSTRUCTION, so there is no silent
    # score-lowering path (Codex R1 MAJOR #1): every exemplar that contributes
    # to a composite had its bars prefetched; every exemplar whose bars failed
    # is uniformly absent from BOTH the match and the universe (and #27-audited).
    # The cfg=None test-stub path reuses lease._conn WITHOUT entering
    # fenced_write (mirrors the detector_read_conn discipline ~1714-1723) so the
    # snapshot read stays lock-free.
    exemplar_snapshot_conn = (
        connect(cfg.paths.db_path) if cfg is not None
        else getattr(lease, "_conn", None)
    )
    snapshot_exemplar_rows: list = []
    try:
        if exemplar_snapshot_conn is not None:
            try:
                snapshot_exemplar_rows = list_exemplars(exemplar_snapshot_conn)
            except Exception as exc:
                log.warning(
                    "pattern_detect: exemplar corpus snapshot failed "
                    "(continuing with empty corpus; template_match_score "
                    "will be NULL): %s",
                    exc,
                )
                snapshot_exemplar_rows = []
        else:
            # Defensive edge (Codex R1 MINOR): cfg is None AND the lease exposes
            # no shared _conn. Read the corpus via a SHORT lease.fenced_write() --
            # a PURE READ (no audit-writing fetch inside, so deadlock-safe) --
            # mirroring the pre-fix in-fence list_exemplars so this unreachable
            # stub path does not silently degrade to an empty corpus. Bars are
            # still pre-fetched OUTSIDE any fence below.
            try:
                with lease.fenced_write() as _snap_conn:
                    snapshot_exemplar_rows = list_exemplars(_snap_conn)
            except Exception as exc:
                log.warning(
                    "pattern_detect: exemplar corpus snapshot via lease fence "
                    "failed (continuing with empty corpus): %s",
                    exc,
                )
                snapshot_exemplar_rows = []
    finally:
        if cfg is not None and exemplar_snapshot_conn is not None:
            exemplar_snapshot_conn.close()

    # Build the exemplar bundles from the snapshot (filter confirmed+watch only,
    # the same filter previously at @1989). snapshot_eligible_ids is the
    # authoritative eligible-ID set for the OQ-E in-fence divergence guard
    # (Task 2). Per-exemplar bar-fetch failure / empty-slice is isolated and
    # #27-audited (silent-skip-without-audit is forbidden).
    exemplar_bundles_by_class: dict[str, list[TemplateMatchExemplar]] = {}
    snapshot_eligible_ids: set[int] = set()
    _valid_exemplar_decisions = ("confirmed", "watch")
    for ex_row in snapshot_exemplar_rows:
        if ex_row.final_decision not in _valid_exemplar_decisions:
            continue
        snapshot_eligible_ids.add(int(ex_row.id))
        try:
            # window_days=400 IDENTICAL to the prior in-fence call (#28/#29
            # historical depth preserved byte-for-byte).
            ex_bars = ohlcv_cache.get_or_fetch(
                ticker=ex_row.ticker, window_days=400
            )
            _ex_start = pd.Timestamp(ex_row.start_date)
            _ex_end = pd.Timestamp(ex_row.end_date)
            _mask = (ex_bars.index >= _ex_start) & (ex_bars.index <= _ex_end)
            _ex_close = ex_bars.loc[_mask, "Close"]
            if hasattr(_ex_close, "ndim") and _ex_close.ndim == 2:
                _ex_close = _ex_close.iloc[:, 0]
            ex_close_arr = _np_pd_inner.asarray(_ex_close.values, dtype=float)
            if ex_close_arr.size == 0:
                if run_warnings is not None:
                    run_warnings.append({
                        "step": "pattern_detect",
                        "exemplar_ticker": ex_row.ticker,
                        "reason": "exemplar bars unavailable",
                    })
                continue
            bundle = TemplateMatchExemplar(
                exemplar=ex_row, close_prices=ex_close_arr
            )
        except Exception as exc:
            log.info(
                "pattern_detect: exemplar bars pre-fetch failed for "
                "exemplar_id=%s ticker=%s (continuing): %s",
                ex_row.id, ex_row.ticker, exc,
            )
            if run_warnings is not None:
                run_warnings.append({
                    "step": "pattern_detect",
                    "exemplar_ticker": ex_row.ticker,
                    "reason": "exemplar bars unavailable",
                })
            continue
        exemplar_bundles_by_class.setdefault(
            ex_row.proposed_pattern_class, []
        ).append(bundle)

```

- [ ] **Step 4: Implement the reorder — DELETE the in-fence exemplar build block.**

In `_step_pattern_detect`, inside the fence, DELETE the entire in-fence exemplar block — from the comment `# T2.SB5 T-A.5.4: load pattern_exemplars corpus + slice` (~1966) through the end of the `exemplar_bundles_by_class.setdefault(...).append(bundle)` loop (~2024). This is: the `exemplar_bundles_by_class: dict[...] = {}` declaration (~1973-1975), the `try: exemplar_rows = list_exemplars(conn)` block (~1976-1984), and the `for ex_row in exemplar_rows:` filter/fetch/slice loop (~1986-2024).

The `canonical_existing` re-read (~1920-1938), the `final_emit_list` reconcile (~1947-1964), and the `resolved_emit_list` / `match_forward` loop (~2030+) STAY in-fence and now consume the `exemplar_bundles_by_class` built outside (same variable name, same function scope). After deletion, the fence body flows: `canonical_existing` re-read → reconcile → (Task 2 will insert the OQ-E guard here) → `resolved_emit_list` loop → `final_universe_scores` → anchors → INSERT loop. **No `get_or_fetch` remains inside the fence.**

- [ ] **Step 5: Run the binding deadlock test + the existing detect template-matching suite to verify PASS.**

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py::test_detect_pass2_exemplar_fetch_runs_outside_fence_no_deadlock tests/pipeline/test_step_pattern_detect_template_matching.py tests/pipeline/test_step_pattern_detect.py tests/pipeline/test_pattern_pool_dormant_levers.py -v`
Expected: **PASS** — `deadlock_observed is False`; the existing template-matching tests (composite-score parity, empty-corpus fallback, DBW clamp) and the dormant-levers detect tests stay green (behavior-preserving reorder; spec §7.4(a) parity).

- [ ] **Step 6: Write the #5 no-re-fetch + exemplar-failure-#27 + list_exemplars-once tests (RED then GREEN against the new code).**

Append to `tests/pipeline/test_fetch_vs_write_ordering.py`:

```python
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
```

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py -v`
Expected: **PASS** (all three; the reorder from Steps 3-4 satisfies them).

- [ ] **Step 7: Run ruff on the touched files.**

Run: `python -m ruff check swing/pipeline/runner.py tests/pipeline/test_fetch_vs_write_ordering.py`
Expected: no errors.

- [ ] **Step 8: Commit.**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_fetch_vs_write_ordering.py
git commit -m "fix(pipeline): pre-fetch detect Pass-2 exemplar bars outside the lease fence

Snapshot the exemplar corpus + pre-fetch its bars before opening
lease.fenced_write() so the audit-writing market-data fetch no longer
deadlocks audit_conn on the held write lock (Run-92). The snapshot is the
run's authoritative scoring membership; bar-fetch failure emits a #27 audit
and is uniformly absent from match+universe. window_days=400 preserved."
```

---

## Task 2: Detect Pass-2 — OQ-E in-fence eligible-ID divergence guard (#27)

**Goal:** `pattern_exemplars` has live writers OUTSIDE the pipeline lease (web routes, CLI labeling, backfill). Scoring this run uses the Pass-2-entry snapshot (≤ 1-run staleness); a cheap in-fence re-read of just the eligible exemplar IDs detects a mid-run membership change and emits a #27 divergence audit (never silent). No bars, no network — pure SQLite read on the fence connection.

**Files:**
- Modify: `swing/pipeline/runner.py` (`_step_pattern_detect`, in-fence, after the reconcile)
- Modify: `tests/pipeline/test_fetch_vs_write_ordering.py` (add OQ-E tests)

- [ ] **Step 1: Write the OQ-E divergence + no-divergence-control tests (RED).**

Append to `tests/pipeline/test_fetch_vs_write_ordering.py`:

```python
def _insert_extra_eligible_exemplar(db_path):
    """Concurrent web/CLI-style write: add an eligible exemplar on a SEPARATE
    committed connection (simulates a mid-run corpus mutation)."""
    c = sqlite3.connect(str(db_path))
    try:
        c.execute("PRAGMA foreign_keys=ON")
        from swing.data.repos.pattern_exemplars import insert_exemplar
        from swing.data.models import PatternExemplar
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
```

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py::test_detect_pass2_midrun_corpus_divergence_emits_27_audit -v`
Expected: **FAIL** — no divergence warning is emitted yet (the guard does not exist).

- [ ] **Step 2: Implement the in-fence eligible-ID divergence guard.**

In `_step_pattern_detect`, INSIDE the fence, AFTER the `final_emit_list` reconcile loop (~1964) and BEFORE the `resolved_emit_list` declaration (~2030), INSERT:

```python
        # OQ-E observable-divergence guard (spec section 3). pattern_exemplars
        # has live writers OUTSIDE the pipeline lease (web routes, CLI labeling,
        # backfill), so the corpus can change mid-run. Scoring uses the
        # Pass-2-entry snapshot (<=1-run staleness, benign for a forward-walk
        # substrate); a CHEAP in-fence re-read of just the eligible IDs (no bars,
        # no network) detects a membership change and AUDITS it (#27) rather than
        # silently. This detects ID-set membership changes, NOT same-ID
        # confirmed<->watch decision flips (which do not change scoring
        # membership). Scoring still proceeds from the snapshot bundles.
        try:
            _infence_eligible_ids = {
                int(_r[0]) for _r in conn.execute(
                    "SELECT id FROM pattern_exemplars "
                    "WHERE final_decision IN ('confirmed','watch')"
                ).fetchall()
            }
        except Exception as exc:
            log.warning(
                "pattern_detect: in-fence exemplar-ID re-read failed "
                "(continuing; divergence guard skipped): %s",
                exc,
            )
            _infence_eligible_ids = snapshot_eligible_ids
        _eligible_added = _infence_eligible_ids - snapshot_eligible_ids
        _eligible_removed = snapshot_eligible_ids - _infence_eligible_ids
        if (_eligible_added or _eligible_removed) and run_warnings is not None:
            run_warnings.append({
                "step": "pattern_detect",
                "reason": (
                    "exemplar eligible-ID membership changed mid-run; "
                    "run used Pass-2-entry snapshot"
                ),
                "added": len(_eligible_added),
                "removed": len(_eligible_removed),
            })
```

- [ ] **Step 3: Run the OQ-E tests + the Task-1 tests to verify PASS.**

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py -v`
Expected: **PASS** — divergence test emits `added=1, removed=0`; control test emits no divergence; all Task-1 tests still green.

- [ ] **Step 4: Run the existing detect suite to confirm no spurious divergence warnings.**

Run: `python -m pytest tests/pipeline/test_step_pattern_detect_template_matching.py tests/pipeline/test_step_pattern_detect.py tests/pipeline/test_pattern_pool_dormant_levers.py -v`
Expected: **PASS** — in the cfg=None `_StubLease` path the snapshot reads `lease._conn` and the in-fence guard reads the same `conn`, so `snapshot_eligible_ids == _infence_eligible_ids` → no spurious warning.

- [ ] **Step 5: Run ruff + commit.**

```bash
python -m ruff check swing/pipeline/runner.py tests/pipeline/test_fetch_vs_write_ordering.py
git add swing/pipeline/runner.py tests/pipeline/test_fetch_vs_write_ordering.py
git commit -m "fix(pipeline): audit detect Pass-2 exemplar eligible-ID mid-run divergence

Add a cheap in-fence eligible-ID re-read vs the Pass-2-entry snapshot; emit a
#27 warnings_json divergence entry (added/removed counts) when a concurrent
web/CLI corpus write changes the eligible set mid-run. Scoring still uses the
snapshot (<=1-run staleness), now audited rather than silent (OQ-E)."
```

---

## Task 3: Observe — compute pass outside the fence, write pass inside

**Goal:** Eliminate deadlock locus #9. The entire per-detection loop body is fence-independent except `insert_observation`. Run idempotency / shed / `_bar_for_date` (fetch) / `_advance_status` / row-build in a compute pass outside the fence; collect rows; wrap only the insert loop in one short fence.

**Files:**
- Modify: `swing/pipeline/runner.py` (`_step_pattern_observe`, ~2620-2685)
- Modify: `tests/pipeline/test_fetch_vs_write_ordering.py` (add observe tests)

- [ ] **Step 1: Write the binding observe deadlock-repro test (RED).**

Append to `tests/pipeline/test_fetch_vs_write_ordering.py`:

```python
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
```

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py::test_observe_bar_fetch_runs_outside_fence_no_deadlock -v`
Expected: **FAIL** — `deadlock_observed` is `True` (pre-fix `_bar_for_date` runs inside the fence).

- [ ] **Step 2: Implement the compute/write split.**

In `_step_pattern_observe`, REPLACE the fence block (`runner.py:2628-2685`, from `with lease.fenced_write() as conn:` through `_observed_count += 1`) with a compute pass (outside the fence) collecting `to_insert`, then a single short fence around the inserts. The `drain_telemetry()` reset (~2626-2627) stays IMMEDIATELY before this; the shed #27 audit + observe_load telemetry (~2687-2709) stay AFTER, unchanged.

Replace:

```python
    with lease.fenced_write() as conn:
        for det in open_dets:
            prev = latest.get(det.detection_id)
            if prev is not None and prev.observation_date == observation_date:
                continue  # idempotent: already observed today
            ...  # watch-shed block
            bar = _bar_for_date(cfg, ohlcv_cache, det.ticker, observation_date)
            if bar is None:
                run_warnings.append({...})
                continue
            sessions = _sessions_since(det.data_asof_date, observation_date)
            status, change = _advance_status(...)
            insert_observation(conn, PatternForwardObservation(...))
            _observed_count += 1
```

with (preserve every inner branch verbatim; only the fence boundary moves):

```python
    # Fetch-vs-write-ordering fix (locus #9): COMPUTE PASS outside the fence.
    # The per-detection body (idempotency skip, watch-shed, _bar_for_date fetch,
    # _advance_status, row-build) is fence-independent; only insert_observation
    # needs the lease. Running _bar_for_date (-> get_or_fetch -> audit-writing
    # market-data ladder) here means it never executes under a held write lock
    # (Run-92 deadlock removed). Shed is evaluated BEFORE _bar_for_date, so shed
    # tickers are still never fetched (OQ-A; identical Schwab quota to today).
    to_insert: list[PatternForwardObservation] = []
    for det in open_dets:
        prev = latest.get(det.detection_id)
        if prev is not None and prev.observation_date == observation_date:
            continue  # idempotent: already observed today
        # Dormant Lever 2 (pool-widening 2026-06-04): watch-origin pre-fetch
        # shed. A no-fetch SKIP (NOT an `expired` transition). Bucket read from
        # the LOCKED finviz_screen_state. Horizon is STATUS-AWARE (mirrors
        # _advance_status).
        if _pend_w is not None or _post_w is not None:
            _bucket = None
            if det.finviz_screen_state:
                try:
                    _bucket = json.loads(det.finviz_screen_state).get("bucket")
                except (ValueError, TypeError):
                    _bucket = None
            if _bucket == "watch":
                _sess = _sessions_since(det.data_asof_date, observation_date)
                _prev_status = prev.status if prev is not None else "pending"
                if _prev_status == "triggered_open":
                    _horizon = (
                        (_pend_w if _pend_w is not None else max_pending)
                        + (_post_w if _post_w is not None else max_post))
                else:  # pending / no observation yet
                    _horizon = (
                        _pend_w if _pend_w is not None else max_pending)
                if _sess > _horizon:
                    _shed_count += 1
                    continue  # no fetch, no observation row, no terminal
        bar = _bar_for_date(cfg, ohlcv_cache, det.ticker, observation_date)
        if bar is None:
            run_warnings.append({
                "step": "pattern_observe", "ticker": det.ticker,
                "observation_date": observation_date,
                "reason": "no bar for observation_date",
            })
            continue
        sessions = _sessions_since(det.data_asof_date, observation_date)
        status, change = _advance_status(
            det, prev=prev, bar=bar,
            sessions_since_detection=sessions,
            max_pending=max_pending, max_post_trigger=max_post)
        to_insert.append(PatternForwardObservation(
            observation_id=None, detection_id=det.detection_id,
            observation_date=observation_date,
            ohlc_today_json=build_ohlc_today_json(
                bar, observation_date=observation_date, cutoff=observe_cutoff,
            ),  # validated shape + provider domain + completed-day guard
            status=status, status_change_event=change,
            sessions_since_detection=sessions,
            created_at=datetime.now(UTC).isoformat(),
        ))

    # WRITE PASS: a single short fence wraps ONLY the inserts (the lease-fencing
    # contract is preserved; the write still happens inside fenced_write).
    if to_insert:
        with lease.fenced_write() as conn:
            for row in to_insert:
                insert_observation(conn, row)
                _observed_count += 1
```

- [ ] **Step 3: Run the binding observe test + the existing observe suite to verify PASS.**

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py::test_observe_bar_fetch_runs_outside_fence_no_deadlock tests/pipeline/test_step_pattern_observe.py tests/pipeline/test_observe_load_instrumentation.py tests/pipeline/test_pattern_pool_dormant_levers.py -v`
Expected: **PASS** — `deadlock_observed is False`; `_observed_count`, `_shed_count`, the shed #27 audit, the no-bar #27 audit, and `observe_load` telemetry (`fetch_window`/`in_memory_hit`) are identical to pre-fix (spec §7.5 parity; the `drain_telemetry()` reset still precedes the compute pass, so fetch counts are unchanged).

- [ ] **Step 4: Write the observe parity test (idempotent / shed / no-bar / normal mix).**

Append to `tests/pipeline/test_fetch_vs_write_ordering.py`:

```python
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
```

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py::test_observe_split_preserves_idempotency_and_observed_count -v`
Expected: **PASS**.

- [ ] **Step 5: Run ruff + commit.**

```bash
python -m ruff check swing/pipeline/runner.py tests/pipeline/test_fetch_vs_write_ordering.py
git add swing/pipeline/runner.py tests/pipeline/test_fetch_vs_write_ordering.py
git commit -m "fix(pipeline): split observe compute-pass outside the lease fence

Run the per-detection compute pass (idempotency, watch-shed, _bar_for_date
fetch, _advance_status, row-build) outside lease.fenced_write(); wrap only the
insert_observation loop in one short fence. The audit-writing bar fetch no
longer deadlocks audit_conn (Run-92). Shed still precedes the fetch (OQ-A);
idempotency + shed #27 + no-bar #27 + observe_load telemetry preserved."
```

---

## Task 4: Stopgap revert (OQ-B)

**Goal:** With both deadlock loci removed, 30s is again the correct safe busy_timeout. Delete the `db_busy_timeout_ms = 5000` override from `swing.config.toml` (single source of truth = `swing/config.py` dataclass default `30000` + `db.py DEFAULT_BUSY_TIMEOUT_MS = 30000`) and remove the `TEMPORARY STOPGAP` comment block.

**Files:**
- Modify: `swing.config.toml` (`[web]`, 128-137)
- Modify: `tests/pipeline/test_fetch_vs_write_ordering.py` (add the revert test)

- [ ] **Step 1: Write the stopgap-revert test (RED).**

Append to `tests/pipeline/test_fetch_vs_write_ordering.py`:

```python
def test_stopgap_reverted_busy_timeout_resolves_to_30000():
    """OQ-B (spec 7.7): the [web] db_busy_timeout_ms stopgap key is deleted from
    the tracked swing.config.toml; the resolved value falls back to the dataclass
    default (30000). Discriminating: pre-fix the toml override is 5000."""
    import tomllib
    from pathlib import Path

    from swing.config import Config

    cfg = Config.from_defaults()
    assert cfg.web.db_busy_timeout_ms == 30000
    # Lock the "delete the key" decision: the tracked toml [web] section must not
    # carry the stopgap override at all (single source of truth = the default).
    project_root = Path(__file__).resolve().parents[2]
    with open(project_root / "swing.config.toml", "rb") as f:
        raw = tomllib.load(f)
    assert "db_busy_timeout_ms" not in raw.get("web", {})
```

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py::test_stopgap_reverted_busy_timeout_resolves_to_30000 -v`
Expected: **FAIL** — the toml still has `db_busy_timeout_ms = 5000` (both assertions fail).

- [ ] **Step 2: Delete the stopgap key + comment from `swing.config.toml`.**

In `swing.config.toml`, replace the entire `[web]` stopgap block (lines ~128-137):

```toml
[web]
# TEMPORARY STOPGAP (2026-06-06, Run-92 live gate). The SQLite lock-contention
# arc set the audit-connection busy_timeout to 30000ms, but the TRUE root cause
# (OHLCV fetch inside a held lease.fenced_write -- runner.py:1898/1994 + the
# charts/observe steps) is NOT yet fixed, so deadlocked audit writes now wait the
# full 30s before falling back to yfinance (slower nightly pipeline). Lowered to
# 5000ms (the old effective wait) until the fetch-vs-write-ordering fix arc ships.
# REVERT to 30000 (or delete this key -> db.py DEFAULT_BUSY_TIMEOUT_MS=30000)
# once that fix lands.
db_busy_timeout_ms = 5000
```

with (key deleted; one-line pointer; empty `[web]` section retained so the loader's section handling is unchanged):

```toml
[web]
# db_busy_timeout_ms intentionally OMITTED -- single source of truth is the
# 30000ms default (config.py + db.py DEFAULT_BUSY_TIMEOUT_MS). The 2026-06-06
# Run-92 stopgap (5000ms) was reverted once the fetch-vs-write-ordering fix arc
# structurally removed the OHLCV-fetch-inside-held-fence deadlock.
```

> If `[web]` becomes a fully empty section and the config loader's `required_sections` check (`config.py:478`) or a `web` parser objects to an empty table, keep the comment lines (a TOML section with only comments is valid and non-empty as a table). Verify by running the revert test (Step 3) — `Config.from_defaults()` must load without error.

- [ ] **Step 3: Run the revert test to verify PASS.**

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py::test_stopgap_reverted_busy_timeout_resolves_to_30000 -v`
Expected: **PASS** — `cfg.web.db_busy_timeout_ms == 30000` and no `db_busy_timeout_ms` key in the toml `[web]` table.

- [ ] **Step 4: Run the config suite to confirm no load regression.**

Run: `python -m pytest tests/config/test_config.py -v`
Expected: **PASS** — the loader still parses `swing.config.toml`.

- [ ] **Step 5: Commit.**

```bash
git add swing.config.toml tests/pipeline/test_fetch_vs_write_ordering.py
git commit -m "chore(config): revert busy_timeout stopgap to the 30000ms default

The fetch-vs-write-ordering fix structurally removed the
OHLCV-fetch-inside-held-fence deadlock, so 30s is again the correct safe
busy_timeout. Delete the [web] db_busy_timeout_ms=5000 override + the
TEMPORARY STOPGAP comment; single source of truth is the config.py /
db.py DEFAULT_BUSY_TIMEOUT_MS=30000 default (OQ-B)."
```

---

## Task 5: Post-fix verification — `fenced_write` audit re-grep + full suite + ruff

**Goal:** Prove the acceptance criteria: re-run the §2 audit on the post-fix tree (the two deadlock loci flip to safe; #16 daily-management stays banked-🟡); full fast suite green; ruff clean.

**Files:** none modified (verification only).

- [ ] **Step 1: Re-run the §2 `fenced_write` audit — confirm no audit-writing fetch remains inside any held fence.**

Run (a manual STEP-0-style re-audit; inspect each `fenced_write` block in `runner.py`):
```bash
grep -n "lease.fenced_write()" swing/pipeline/runner.py
grep -n "get_or_fetch\|price_cache.get\|fetch_window_via_ladder\|fetch_quote_via_ladder\|get_price_history\|get_quotes_batch" swing/pipeline/runner.py
```
Expected: for detect Pass-2 (~1898) and observe (~2628), NO `get_or_fetch`/ladder/`price_cache.get` call appears between the `with lease.fenced_write()` and its dedent. Specifically confirm:
- detect: the only in-fence DB ops are the `canonical_existing` SELECT, the OQ-E `SELECT id` re-read, and the INSERT loop — no `get_or_fetch`.
- observe: the in-fence block is only the `for row in to_insert: insert_observation(...)` loop — no `_bar_for_date` / `get_or_fetch`.
- `_step_charts` (~2826/2855/2895/2954) unchanged; `_step_daily_management` (~3705/3709) unchanged (banked-🟡 per OQ-D).

- [ ] **Step 2: Run the full new test module + the touched-area suites.**

Run: `python -m pytest tests/pipeline/test_fetch_vs_write_ordering.py tests/pipeline/ tests/integration/test_phase14_temporal_log_e2e.py tests/integration/test_phase13_t2_sb5_template_matching_e2e.py tests/config/test_config.py -v`
Expected: all green.

- [ ] **Step 3: Run the full fast suite (isolate the known xdist date-flakes).**

Run: `python -m pytest -m "not slow" -q`
Expected: green at the ~7128+ baseline. Per `feedback_no_false_green_claim`: if any failure appears, confirm it is one of the 3 known date-sensitive xdist flakes (re-run that test file serially to confirm it is pre-existing and date-driven, NOT introduced by this arc) before claiming green. Read the actual result — never carry a prior pass-count forward.

- [ ] **Step 4: Run ruff across the package.**

Run: `python -m ruff check swing/`
Expected: clean.

- [ ] **Step 5: Final review commit (only if Step 1-4 surfaced a fix; otherwise no commit).**

If the audit/suite surfaced a residual issue, fix it minimally, re-run Steps 1-4, and commit with a `fix(pipeline):` / `test(pipeline):` message. Otherwise this task produces no commit (verification only).

---

## Operator-witnessed live gate (post-merge — NOT an implementer step; recorded here for the orchestrator/operator)

After merge, the operator re-runs the SAME first-instrumented-live-run that FAILED at Run 92: a normal UNSEEDED `swing pipeline run --manual`. Binding pass conditions (spec §1 + brief §5):
1. The `database is locked` yfinance-degrade fallback COLLAPSES — NO `BEGIN IMMEDIATE FAILED (database is locked)` audit telemetry lines; Schwab becomes the primary source for the ~13-22 cache-miss tickers.
2. The G2′ lock-wait telemetry shows no long waits.
3. The busy_timeout is back at 30000 (stopgap reverted) — so the gate ALSO confirms the deadlock does NOT recur at the full 30s.

Note (spec §8): some Run-92 candidate-ticker yfinance tags may have come from the *separate* banked Schwab market-data ladder T-C.1 per-ticker wrapper-error cause; the absence of `BEGIN IMMEDIATE ... database is locked` telemetry disambiguates this arc's deadlock fix from that banked cause at the gate.

---

## Self-Review (run by the plan author)

**1. Spec coverage** (every spec §-requirement → task):
- §2 audit / acceptance "no audit-writing fetch inside any held fence" → Task 5 Step 1.
- §3 OQ-A per-locus pre-fetch → Task 1 (detect) + Task 3 (observe), each fetches just-before its own write.
- §3 OQ-B stopgap revert → Task 4.
- §3 OQ-C snapshot-authoritative membership → Task 1 (snapshot is the scoring membership).
- §3 OQ-D daily-management banked → explicitly NOT touched (File Map + invariants + Task 5 Step 1).
- §3/§4.1 OQ-E in-fence ID divergence guard → Task 2.
- §4.1 detect reorder (snapshot out, drop in-fence get_or_fetch, canonical_existing + match + INSERT stay) → Task 1 Steps 3-4.
- §4.2 observe compute/write split → Task 3 Step 2.
- §4.3 stopgap revert details (delete key + comment) → Task 4 Step 2.
- §6 invariants (schema NONE, #5, #27, #28/#29, lease-fencing, audit single-tx) → "Invariants" section + per-task comments/asserts.
- §7.1 deadlock-repro (both loci) → Task 1 Step 1 (detect), Task 3 Step 1 (observe); anti-false-pass `get_or_fetch >= 1` in both.
- §7.2 ordering assertion → covered by the binding `deadlock_observed is False` (the spy probes the exact write-lock contention; a lighter `in_fenced_write` flag is redundant given the probe directly measures lock acquisition).
- §7.3 #5 no-re-fetch → Task 1 Step 6 (`test_..._fetched_once_candidates_not_refetched`).
- §7.4 composite-parity + exemplar-failure #27 + list_exemplars-once → §7.4(a) by the existing template-matching tests staying green (Task 1 Step 5) + §7.4(b)/(c) Task 1 Step 6.
- §7.5 observe parity → existing observe tests staying green (Task 3 Step 3) + Task 3 Step 4 explicit.
- §7.6 OQ-E divergence audit + control → Task 2 Step 1.
- §7.7 stopgap revert → Task 4 Step 1.
- §7.8 full suite + ruff → Task 5 Steps 3-4.

**2. Placeholder scan:** no TBD/TODO/"add error handling"/"similar to Task N"; every code step shows complete code; every test step shows the test body + the exact `pytest` command + expected fail/pass.

**3. Type/name consistency:** `exemplar_bundles_by_class` (dict[str, list[TemplateMatchExemplar]]) declared in Task 1's out-of-fence block, consumed by the unchanged in-fence `match_forward` loop; `snapshot_eligible_ids` (set[int]) built in Task 1, consumed by Task 2's guard; `to_insert` (list[PatternForwardObservation]) built + consumed within Task 3; `_DeadlockProbeCache` / `_seed_confirmed_exemplar` / `_drive_observe` defined once in Task 1's scaffolding, reused in Tasks 2-4. `get_or_fetch(window_days=400)` params byte-identical at the moved site. Conftest helpers (`_seed_aplus_candidate_and_run`, `_drive_detect`, `_plant_detection`, `_cfg`, `_FakeLease`, `_build_bars`, `_stub_window`) used with their verified signatures.
