# Phase 17 Arc 17-A — Single Evaluation Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the comment-enforced parallel copy between `swing/cli.py:eval_cmd` and `swing/pipeline/runner.py:_step_evaluate` with ONE shared orchestration path consumed by both entry points, so standalone `swing eval` and the nightly pipeline persist classification identically (modulo operator-ruled intentional differences).

**Architecture:** A new pure-ish module `swing/evaluation/orchestration.py` owns the evaluation-run orchestration (CSV parse → sector/industry map → RS universe → SPY benchmark → OHLCV fetch → context assembly → `evaluate_batch` → synthesized excluded/error rows → sector/industry plumb → run-row assembly). The genuinely-different concerns are explicit **injection seams**: the universe-augmentation set (open-trade close-only union + Arc-7 pin injection), the per-ticker `current_equity`, the pipeline-only pre-fetch side effects (`_warm_pipeline_marketdata` + `_prewarm_evaluate_archives`), the output channel (click.echo vs run-warnings), and the persistence strategy (plain `with conn:` vs `lease.fenced_write()` + `set_evaluation_run_id`). Two thin adapters (`eval_cmd`, `_step_evaluate`) become parameter-assembly + call + result-handling. Everything not injected is shared code. NO schema, NO new dependency.

**Tech Stack:** Python 3.14, pandas, click, SQLite (via `swing.data.db`), pytest (`-m "not slow"`), the existing `swing.data.ohlcv_archive` per-ticker parquet archive, `swing.evaluation.evaluate_batch`.

---

## Pre-flight: re-grounding result (verified on disk 2026-06-12 at branch start)

The brief's §2 anchors were re-verified against the live tree (branch `arc17a-plan`, HEAD `c7eeed4a`). Drift from the brief's stated line numbers is **cosmetic** (a few lines), recorded here for the implementer:

| Brief anchor | Verified location | Note |
|---|---|---|
| `eval_cmd` at `cli.py:360` | `swing/cli.py:360` (`def eval_cmd`), command decorator `cli.py:355` | exact |
| mirror comment "~cli.py:380" | `swing/cli.py:379-388` (the "Mirrors the `_step_evaluate` plumbing … persist classification identically" block) | the phase17-todo cites `cli.py:369-374`; the actual mirror prose is **379-388** |
| `_step_evaluate` at `runner.py:1382` | `swing/pipeline/runner.py:1382` | exact |
| open-trades union "runner ~1420" | `runner.py:1416-1427` (`list_open_trades(open_conn)` at **1419**) | exact |
| Arc-7 pin injection "runner 1437-1448" | `runner.py:1429-1450` (`list_active_watchlist` at **1438**, `pin_injection` warning **1446-1450**) | exact |
| 8 parallel stages (§2) | all present in both bodies | confirmed |

**Both pre-grounded divergences CONFIRMED present on disk:**
- `_step_evaluate` unions `list_open_trades` tickers into the fetch set (`runner.py:1416-1427`) and into `excluded` (close-only, `runner.py:1530-1531`). `eval_cmd` does neither (`list_open_trades` is imported/used at `cli.py` for other commands only, never inside `eval_cmd`).
- `_step_evaluate` injects pinned watchlist tickers (`runner.py:1429-1450`) into full evaluation + emits a `pin_injection` run-warning. `eval_cmd` predates Arc-7 and has no pin logic.

**Additional divergence candidates discovered during re-grounding** (the Phase-0 harness CONFIRMS or REFUTES each; all route to the operator at the §4 checkpoint — the implementer resolves NONE of them):

- **D-EQUITY:** `current_equity` fed to `CandidateContext`. `_step_evaluate` computes `sizing_equity(real_equity=current_equity(...), floor=...)` (`runner.py:1514-1525`); `eval_cmd` uses `cfg.account.starting_equity` (`cli.py:493`). Surfaces in the diff ONLY if it perturbs a persisted candidate column.
- **D-EXCLUDED-CLOSE:** `_step_evaluate` preserves a held ticker's last close on its `excluded` row (`runner.py:1548-1555`); `eval_cmd` always writes `close=None` on excluded rows (`cli.py:500-507`). For blocklist tickers (never fetched) both are `None`; the difference only manifests for held tickers, which only exist in the runner path (a row-presence diff under DIVERGENCE-1).
- **D-ERROR-DEDUP:** `_step_evaluate` de-dupes `error_tickers` against `excluded` (`runner.py:1564-1570`) so a blocklisted/held ticker whose fetch ALSO fails emits ONE row; `eval_cmd` does NOT dedup (`cli.py:508-515`) → a blocklist ticker that fails fetch emits TWO rows (excluded + error). **This perturbs persisted rows even with an empty augmentation** — the harness MUST probe it with a blocklist-ticker-that-fails-fetch fixture.
- **D-SPY-GUARD:** `eval_cmd` wraps the SPY fetch in try/except + emits warnings on failure/insufficient-bars (`cli.py:412-426`); `_step_evaluate` runs SPY straight-line (`runner.py:1471-1477`) → a SPY fetch exception raises and FAILS the step. Identical `spy_return` on the success path; the difference is an error-path/failure-semantics divergence.
- **D-ASOF:** `eval_cmd` threads its `--as-of-date` flag into every `fetcher.get(..., as_of_date=as_of_date)`; `_step_evaluate` hardcodes `as_of_date=None`. This is a CLI-only parity affordance, not a pipeline concern — modelled as a parameter (default `None`), not a divergence to ratify.

> The implementer does NOT decide any of D-EQUITY / D-EXCLUDED-CLOSE / D-ERROR-DEDUP / D-SPY-GUARD / the two pre-grounded divergences. They are surfaced by the Phase-0 harness, pinned AS divergences, and routed to the operator at the §4 checkpoint (Task C). Each ruling becomes either unified behavior (assertion migrated) or an intentional injected-seam difference (tested as intentional).

---

## Binding conventions (this arc)

- **TDD, per task:** write failing test → run → see fail → minimal impl → run → see pass → commit. Conventional commits (`feat(evaluation):`, `test(evaluation):`, `refactor(pipeline):`, `refactor(cli):`). **ZERO `Co-Authored-By`**, no `--no-verify`, no `git commit --amend`. The final `-m` paragraph is **plain prose** (the trailer-parse hazard — a paragraph starting `Word:` pollutes `%(trailers)`).
- **Frozen-clock convention (R2 rider / D9, `docs/orchestrator-context.md` §Binding conventions, added 2026-06-12):** EVERY new test in this arc touches dates (`datetime.now()`, `action_session_for_run`, archive freshness). Each new test MUST pin the clock via a frozen-clock fixture (monkeypatch `datetime.now` in BOTH `swing.cli` and `swing.pipeline.runner` to a fixed `run_now`), never the live wall clock. NO retrofit of existing tests.
- **Phase isolation:** this arc is read-and-write through existing public repo/service functions only. NO `swing/data/` or `swing/trades/` carve-out. NO migration. If a task appears to need a schema change, a new dependency, or a departure from the §3 module shape below — **STOP and route back through CHARC**; do not absorb it silently.
- **Behavior-preserving locks (§3), itemized for QA:**
  1. `_step_evaluate`'s lease/fence discipline (`lease.verify_held()`, `lease.fenced_write()`, `set_evaluation_run_id(conn, pipeline_run_id=lease.run_id, evaluation_run_id=run_id)`) stays ENTIRELY in the runner adapter — the orchestrator never imports `Lease` or touches a lease.
  2. The #16 fetch-hoist locus (the held-tickers boundary where `_warm_pipeline_marketdata` + `_prewarm_evaluate_archives` fire) stays in the runner adapter via the `pre_fetch_hook` seam — same call order, same arguments.
  3. The Arc-7 pin/held union semantics in the pipeline path are byte-identical: held → close-only `excluded`; pinned-off-screen-not-held → full `evaluate_batch`; pinned-already-seen → NOT re-injected; `pin_injection` run-warning shape unchanged.
  4. `evaluate_batch` and everything below it: UNTOUCHED.
  5. Per-step timing emission (#25 / Arc-1 `pipeline_step_timings`) UNCHANGED — the orchestrator is called from within the existing `_step_evaluate` body; no step boundary added/moved/renamed.
  6. NO schema, NO new dependency, NO change to `swing.config.toml` / `pyproject.toml` (R1 does NOT land here — this arc does not touch pyproject).
- **Gotchas in force:** the V1↔V2 parity-drift family (#24/#25/#26 — this IS that family in production); the byte-parity-insufficient gotcha (Phase-0 fixtures drive the PRODUCTION derivation chain — real CSV parse, real `read_or_fetch_archive`, real `evaluate_batch` — only the network boundary is pinned on disk); OHLCV-fetch-scope (held-ticker union is a freshness concern, pipeline-only); session-anchor forward-vs-backward (`action_session_for_run(run_now)` forward; `last_completed_session(run_now)` backward fallback — both consume the single captured `run_now`).

---

## File map

| File | Responsibility | Action |
|---|---|---|
| `swing/evaluation/orchestration.py` | The shared orchestration function + its seam dataclasses (`UniverseAugmentation`, `OrchestrationOutput`, `OrchestrationResult`). | **Create** |
| `swing/pipeline/runner.py` | `_step_evaluate` becomes the pipeline adapter: compute augmentation (held + pins) + `sizing_equity` + the warm/prewarm `pre_fetch_hook` + the `lease.fenced_write()` persist seam, call the orchestrator, set the eval-run binding. | **Modify** (`1382-1619`) |
| `swing/cli.py` | `eval_cmd` becomes the CLI adapter: parameter assembly + the plain `with conn:` persist seam + click.echo output, call the orchestrator. Delete the mirror comment, replace with a one-line pointer. | **Modify** (`355-561`) |
| `tests/evaluation/test_orchestration_parity_golden.py` | The Phase-0 golden-parity characterization harness: drives identical pinned inputs through BOTH production paths, diffs persisted candidate rows column-by-column, pins divergences as `DIVERGENCE-n` assertions. Permanent parity regression. | **Create** |
| `tests/evaluation/test_orchestration.py` | Unit tests of the orchestrator's seams (empty augmentation == CLI shape; augmentation drives held/pin rows; output callbacks fire; persist callback invoked once). | **Create** |
| `tests/cli/test_cli_eval.py` | Add a UX-characterization test pinning `swing eval` stdout text + exit code (operator-gate surface) before the CLI adapter swap. | **Modify** |

---

## The shared module API (canonical — every task below references these exact signatures)

```python
# swing/evaluation/orchestration.py
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from swing.data.models import Candidate, EvaluationRun


@dataclass(frozen=True)
class UniverseAugmentation:
    """Extra tickers folded into one evaluation run beyond the finviz screen.

    held_tickers:  open-position tickers — close-ONLY (added to `excluded`,
                   no buy/watch decision, fresh close preserved for the
                   dashboard price fallback). Supplied by the pipeline adapter.
    pinned_inject: Arc-7 pinned off-screen tickers — FULL evaluate_batch pass.
                   Supplied by the pipeline adapter.

    Empty default == the standalone-eval universe (finviz screen only).
    """
    held_tickers: tuple[str, ...] = ()
    pinned_inject: tuple[str, ...] = ()


@dataclass
class OrchestrationOutput:
    """Output channel seam. CLI wires click.echo; pipeline wires run-warnings."""
    info: Callable[[str], None] = lambda _msg: None
    warn: Callable[[str], None] = lambda _msg: None
    note_pin_injection: Callable[[list[str]], None] = lambda _tickers: None


@dataclass
class OrchestrationResult:
    run_id: int
    run: EvaluationRun
    candidates: list[Candidate]


def orchestrate_evaluation(
    *,
    cfg,
    csv_path: Path,
    universe,
    universe_hash: str,
    run_now: datetime,
    fetcher,
    current_equity: float,
    persist: Callable[[EvaluationRun, list[Candidate]], int],
    as_of_date: date | None = None,
    augmentation: UniverseAugmentation = UniverseAugmentation(),
    pre_fetch_hook: Callable[[list[str]], None] | None = None,
    output: OrchestrationOutput | None = None,
) -> OrchestrationResult:
    ...
```

**Seam contract (each maps to a re-grounding divergence or a §3 lock):**

- `augmentation` — the held/pin union (DIVERGENCE-1/2). Pipeline supplies computed sets; CLI supplies `UniverseAugmentation()` unless a §4 ruling says otherwise.
- `current_equity` — D-EQUITY. Pipeline supplies `sizing_equity(...)`; CLI supplies `cfg.account.starting_equity`. Kept a parameter so either §4 ruling is honorable.
- `pre_fetch_hook` — LOCK #16. Pipeline passes the warm+prewarm closure (fired at the held-tickers boundary, exact arg order); CLI passes `None`.
- `output` — the click.echo-vs-run-warnings channel. CLI: `info→echo`, `warn→echo(err=True)`, `note_pin_injection→no-op`. Pipeline: `info/warn→no-op`(or log), `note_pin_injection→run_warnings.append({step,kind,count,tickers})`.
- `persist` — LOCK #1. CLI: plain `with conn:` insert run+candidates → run_id. Pipeline: `lease.fenced_write()` insert run+candidates + `set_evaluation_run_id` → run_id.
- `as_of_date` — D-ASOF. CLI threads its flag; pipeline passes `None`.

---

# PHASE 0 — Golden-parity characterization harness (BINDING PRECONDITION, lands FIRST, green against CURRENT code)

> No production code changes in Phase 0. The harness pins TODAY'S behavior of both un-refactored paths, including every divergence it finds. It stays green through Phases 1-3 as the permanent parity regression.

## Task 0.1: Pinned-archive + frozen-clock fixture scaffolding

**Files:**
- Create: `tests/evaluation/test_orchestration_parity_golden.py`

- [ ] **Step 1: Write the fixture builders (no assertions yet — a smoke test that the fixtures load).**

The harness drives the PRODUCTION derivation chain. It pins the network boundary by seeding the on-disk per-ticker archive (`{TICKER}.parquet` + `{TICKER}.meta.json`) so the REAL `PriceFetcher.get → read_or_fetch_archive` returns pinned bars with ZERO `yf.download` calls (the archive is fresh: latest stored bar == the frozen session, `last_full_refresh_date` within 7 days). This is what distinguishes it from the existing `_StubFetcher` tests (the byte-parity-insufficient gotcha): real CSV parse, real archive reader, real `evaluate_batch`.

```python
"""Phase-0 golden-parity harness for Arc 17-A.

Drives IDENTICAL pinned inputs through BOTH production evaluation paths
(`swing eval` via CliRunner, and `_step_evaluate` via a fake lease) and diffs
the persisted `candidates` rows column-by-column. Divergences are pinned AS
divergences (DIVERGENCE-n) — the §4 checkpoint routes them to the operator.

Production-derivation discipline (byte-parity-insufficient gotcha): the network
boundary is pinned by SEEDING the on-disk OHLCV archive; the REAL PriceFetcher /
read_or_fetch_archive serves it. NO fetcher object is stubbed.

Frozen-clock convention (R2/D9): run_now is pinned; datetime.now is monkeypatched
in BOTH swing.cli and swing.pipeline.runner so action_session/data_asof are
deterministic AND the archive freshness gate passes.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

import swing.cli as cli_mod
import swing.pipeline.runner as runner_mod
from swing.data.db import run_migrations

# Frozen clock: a Thursday evening after a completed NYSE session.
RUN_NOW = datetime(2026, 6, 11, 18, 30, 0)
SESSION = date(2026, 6, 11)

SCREEN_TICKERS = ["AAA", "BBB", "CCC"]      # finviz screen
UNIVERSE_TICKERS = ["AAA", "UUU"]           # RS universe
HELD_TICKER = "HHH"                          # open position, OFF-screen
PINNED_TICKER = "PPP"                        # Arc-7 pin, OFF-screen, not held
BLOCKLIST_FAIL = "ZZZ"                       # blocklisted AND fetch fails (D-ERROR-DEDUP)
SPY = "SPY"


def _uptrend_frame(n: int = 420, end: date = SESSION) -> pd.DataFrame:
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=n)
    closes = [10.0 + i * 0.06 for i in range(n)]
    return pd.DataFrame(
        {"Open": closes, "High": [c * 1.02 for c in closes],
         "Low": [c * 0.98 for c in closes], "Close": closes,
         "Volume": [1_000_000] * n},
        index=idx,
    )


def _seed_archive(cache_dir: Path, ticker: str, frame: pd.DataFrame) -> None:
    """Write a FRESH per-ticker archive so read_or_fetch_archive serves it with
    zero network. Frame index is the bar dates; meta marks a recent full refresh."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    out.index.name = "date"
    out.reset_index().to_parquet(cache_dir / f"{ticker}.parquet", index=False)
    (cache_dir / f"{ticker}.meta.json").write_text(
        json.dumps({"last_full_refresh_date": SESSION.isoformat()})
    )
```

> **Implementer investigation (do this in Step 1, before writing assertions):** confirm the EXACT on-disk parquet shape `read_or_fetch_archive` expects by reading `swing/data/ohlcv_archive.py` (`_strip_incomplete_sessions` recognizes a `date` index vs an `asof_date` column — Shape-A). Seed whichever shape the live reader consumes so the REAL reader serves it. If the reader rejects the seeded shape, the fetch falls to network → the test will try to hit yfinance and fail deterministically — that failure IS the signal the seed shape is wrong; fix the seed, do not stub the fetcher. If after investigation the archive genuinely cannot be seeded to serve offline through the production reader, **STOP and flag for CHARC** (the production-derivation precondition would be unmet — a §4-scope problem, not an implementer workaround).

- [ ] **Step 2: Add a `_build_inputs(tmp_path)` helper** that writes: a real finviz CSV (`No.,Ticker,Sector,Industry,Price` columns, rows for `SCREEN_TICKERS` + `BLOCKLIST_FAIL` with real Sector/Industry strings), a real RS-universe file (the `# version:` / `# columns: ticker` header shape from `tests/cli/test_cli_eval.py:_minimal_universe`), and a seeded archive dir with `_uptrend_frame()` for every ticker EXCEPT `BLOCKLIST_FAIL` (left unseeded so its fetch raises → exercises the error path). Seed `SPY` too. Return a `SimpleNamespace(csv_path, universe_path, cache_dir, db_path)`.

- [ ] **Step 3: Add a `_make_config(tmp_path, inputs)` helper** mirroring `tests/pipeline/test_step_evaluate_pin_injection.py:_make_config` but with `manual_block = ["ZZZ"]` (so `BLOCKLIST_FAIL` is on the ETF blocklist) and `prices_cache_dir` pointed at the seeded archive dir. Real `Config` from a temp TOML.

- [ ] **Step 4: Add the frozen-clock fixture.**

```python
@pytest.fixture
def frozen_clock(monkeypatch):
    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return RUN_NOW
    monkeypatch.setattr(cli_mod, "datetime", _Clock)
    monkeypatch.setattr(runner_mod, "_dt", _Clock)  # runner imports datetime as _dt
    return RUN_NOW
```

> Verify the exact import aliases at branch start: `swing/cli.py` uses `from datetime import datetime` (patch `cli_mod.datetime`); `swing/pipeline/runner.py` aliases `datetime as _dt` and `date as _date` (patch `runner_mod._dt`). Adjust the monkeypatch targets to the real alias names. If `action_session_for_run` / `last_completed_session` read `datetime.now()` internally rather than receiving `run_now`, patch at THEIR module too — read `swing/evaluation/` date-semantics to confirm both paths funnel through the single captured `run_now` (they do: both bodies capture `run_now = datetime.now()` once and pass it down).

- [ ] **Step 5: Smoke test — fixtures load, archive serves offline.**

```python
def test_seeded_archive_serves_without_network(tmp_path, frozen_clock):
    inputs = _build_inputs(tmp_path)
    from swing.prices import PriceFetcher
    f = PriceFetcher(cache_dir=inputs.cache_dir, archive_history_days=1260)
    df = f.get("AAA", lookback_days=400, as_of_date=None)
    assert not df.empty
    assert df.index.max().date() == SESSION
```

- [ ] **Step 6: Run — verify the smoke test passes (proves offline-archive derivation works).** Run: `python -m pytest tests/evaluation/test_orchestration_parity_golden.py::test_seeded_archive_serves_without_network -v`. Expected: PASS. If it tries to reach the network (hang/ConnectionError), the seed shape is wrong — fix per Step 1's investigation note.

- [ ] **Step 7: Commit.**
```bash
git add tests/evaluation/test_orchestration_parity_golden.py
git commit -m "test(evaluation): Task 0.1 — Phase-0 parity harness scaffolding (offline-archive fixtures + frozen clock)"
```

## Task 0.2: Drive the CLI path; capture persisted rows

**Files:**
- Modify: `tests/evaluation/test_orchestration_parity_golden.py`

- [ ] **Step 1: Add `_run_cli_path(tmp_path, inputs, cfg_path)` → list of candidate dicts.** Use `CliRunner` to invoke `["--config", str(cfg_path), "eval", "--csv", str(inputs.csv_path)]` against a fresh migrated DB seeded with an open trade for `HELD_TICKER` and a pinned watchlist entry for `PINNED_TICKER` (identical seed to the runner path — Task 0.3). Read `candidates` joined to its run via `evaluation_runs` (the LATEST run). Return rows as dicts keyed by ticker, with EVERY persisted column.

```python
def _seed_open_and_pins(db_path: Path) -> None:
    """Seed one open trade (HHH) + one pinned watchlist entry (PPP). IDENTICAL
    for both paths so the diff reveals only path-divergent handling of them."""
    conn = sqlite3.connect(db_path)
    try:
        run_migrations(conn)
        # ... insert an open trade for HELD_TICKER via the real fills/trades repo
        #     helpers; insert a pinned WatchlistEntry for PINNED_TICKER via
        #     swing.data.repos.watchlist.upsert_watchlist_entry (pinned=True).
        conn.commit()
    finally:
        conn.close()
```

> Use the REAL repo helpers to seed (`upsert_watchlist_entry`, the open-trade/fills insert path used by `tests/pipeline/test_step_evaluate_pin_injection.py`) — do NOT hand-write INSERTs that could drift from the production row shape (the synthetic-fixture-vs-production-emitter gotcha). Crib the exact seed calls from `test_step_evaluate_pin_injection.py`.

- [ ] **Step 2: Add `_read_candidates(db_path)`** that selects all columns from `candidates` for the latest `evaluation_runs.id`, returns `{ticker: {col: val, ...}}`. Include `bucket, close, pivot, initial_stop, adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method, pattern_tag, notes, sector, industry` and the criteria join if persisted separately.

- [ ] **Step 3: Characterization assertion — pin the CLI row-set.**

```python
def test_cli_path_persists_screen_rows(tmp_path, frozen_clock):
    inputs = _build_inputs(tmp_path)
    cfg_path = _make_config(tmp_path, inputs)
    _seed_open_and_pins(inputs.db_path)
    rows = _run_cli_path(tmp_path, inputs, cfg_path)
    # CLI evaluates the finviz screen only. HELD/PINNED are absent (DIVERGENCE-1/2).
    assert HELD_TICKER not in rows
    assert PINNED_TICKER not in rows
    # ZZZ is blocklisted AND fetch-fails → CLI emits TWO rows? (D-ERROR-DEDUP)
    # Pin whatever the CURRENT code does (count rows for ZZZ across buckets).
    zzz = [t for t in rows if t == BLOCKLIST_FAIL]
    # record the observed multiplicity in the assertion (e.g. excluded + error)
```

> The assertion text MUST encode the OBSERVED current behavior (run it, read the rows, write the assertion to match). This is characterization, not aspiration. If `candidates` enforces a single row per (run, ticker) and the double-row can't persist, record THAT (the dedup may be moot) — and note it for the §4 checkpoint.

- [ ] **Step 4: Run + see pass; Commit.**
```bash
git add tests/evaluation/test_orchestration_parity_golden.py
git commit -m "test(evaluation): Task 0.2 — pin the standalone swing eval persisted row-set"
```

## Task 0.3: Drive the pipeline path; capture persisted rows

**Files:**
- Modify: `tests/evaluation/test_orchestration_parity_golden.py`

- [ ] **Step 1: Add `_FakeLease`** (crib verbatim from `tests/pipeline/test_step_evaluate_pin_injection.py:40-66` — `run_id`, `verify_held()` no-op, `step()` no-op, `fenced_write()` yielding a `BEGIN IMMEDIATE` conn to the same file DB).

- [ ] **Step 2: Add `_run_pipeline_path(tmp_path, inputs, cfg)` → list of candidate dicts.** Seed an IDENTICAL DB (`_seed_open_and_pins`). Construct a real `PriceFetcher` on the seeded `cache_dir`, load the universe + hash, then call `runner_mod._step_evaluate(cfg=cfg, fetcher=fetcher, csv_path=inputs.csv_path, universe=universe, universe_hash=universe_hash, run_now=RUN_NOW, action_session=SESSION, lease=_FakeLease(inputs.db_path, run_id=...), price_cache=None, run_warnings=warnings)`. Read candidates via `_read_candidates`. Return rows + the captured `run_warnings`.

> The pipeline path must seed a `pipeline_runs` row matching the `_FakeLease.run_id` so `set_evaluation_run_id` has a row to update (crib from the existing pin-injection test's DB seed). If `_prewarm_evaluate_archives` / `_warm_pipeline_marketdata` reach for config the temp setup lacks, give them the no-op path (price_cache=None handles the warm; the prewarm reads the same seeded archive — confirm it's a no-op cache-hit on the fresh seed).

- [ ] **Step 3: Characterization assertion — pin the pipeline row-set + the pin-injection warning.**

```python
def test_pipeline_path_persists_screen_plus_augmentation(tmp_path, frozen_clock):
    inputs = _build_inputs(tmp_path)
    cfg = ...  # Config.load(_make_config(...))
    _seed_open_and_pins(inputs.db_path)
    rows, warnings = _run_pipeline_path(tmp_path, inputs, cfg)
    # DIVERGENCE-1: held ticker present as excluded close-only.
    assert rows[HELD_TICKER]["bucket"] == "excluded"
    assert rows[HELD_TICKER]["close"] is not None        # D-EXCLUDED-CLOSE: preserved
    # DIVERGENCE-2: pinned off-screen ticker fully evaluated (real bucket).
    assert PINNED_TICKER in rows
    assert rows[PINNED_TICKER]["bucket"] in {"aplus", "watch", "skip"}
    assert any(w["kind"] == "pin_injection" for w in warnings)
```

- [ ] **Step 4: Run + see pass; Commit.**
```bash
git add tests/evaluation/test_orchestration_parity_golden.py
git commit -m "test(evaluation): Task 0.3 — pin the pipeline _step_evaluate persisted row-set + pin_injection warning"
```

## Task 0.4: The column-by-column parity diff + DIVERGENCE-n pins

**Files:**
- Modify: `tests/evaluation/test_orchestration_parity_golden.py`

- [ ] **Step 1: Add the diff test** that runs BOTH paths on identical inputs/seed and computes the row-set + per-column delta.

```python
def test_golden_parity_divergences_are_pinned(tmp_path, frozen_clock):
    inputs = _build_inputs(tmp_path)
    cfg_path = _make_config(tmp_path, inputs)
    cfg = ...  # the same Config object both paths consume
    # Two independent fresh DBs, IDENTICAL seed, IDENTICAL inputs.
    cli_rows = _run_cli_path(...)
    pipe_rows = _run_pipeline_path(...)

    cli_only = set(cli_rows) - set(pipe_rows)
    pipe_only = set(pipe_rows) - set(cli_rows)
    shared = set(cli_rows) & set(pipe_rows)

    # DIVERGENCE-1 (open-trades union): held ticker is pipeline-only, excluded.
    assert HELD_TICKER in pipe_only
    # DIVERGENCE-2 (Arc-7 pin injection): pinned ticker is pipeline-only.
    assert PINNED_TICKER in pipe_only
    # DIVERGENCE-3 (D-ERROR-DEDUP): the blocklist-fail ticker's row multiplicity
    #   differs (assert the observed counts on each side).
    # The SHARED screen tickers (AAA/BBB/CCC) MUST be column-identical EXCEPT for
    #   any column perturbed by D-EQUITY — diff every column and assert the set of
    #   differing columns is EXACTLY the pinned expected set (empty if equity does
    #   not perturb persisted columns).
    differing = {}
    for t in sorted(shared):
        for col in cli_rows[t]:
            if cli_rows[t][col] != pipe_rows[t][col]:
                differing.setdefault(t, set()).add(col)
    # Pin the observed `differing` map verbatim (DIVERGENCE-EQUITY if non-empty;
    # {} if equity is sizing-only and never reaches a persisted candidate column).
    assert differing == EXPECTED_SHARED_COLUMN_DIVERGENCES
```

- [ ] **Step 2: Define `EXPECTED_SHARED_COLUMN_DIVERGENCES`** as a module constant whose value is whatever the run OBSERVES (characterization). Tag each entry with the `DIVERGENCE-n` label in a comment so the §4 checkpoint can enumerate them mechanically.

- [ ] **Step 3: Run the FULL new file + see all pass on CURRENT (un-refactored) code.** Run: `python -m pytest tests/evaluation/test_orchestration_parity_golden.py -v`. Expected: ALL PASS. This is the green-against-current precondition.

- [ ] **Step 4: Commit.**
```bash
git add tests/evaluation/test_orchestration_parity_golden.py
git commit -m "test(evaluation): Task 0.4 — golden parity diff pins every divergence between the two eval paths"
```

- [ ] **Step 5: Produce the DIVERGENCE INVENTORY artifact for the operator** — append a fenced block at the top of the test file (or a sibling `docs/`-free comment) enumerating every pinned `DIVERGENCE-n` with: which side has it, the persisted-row effect, and the open question for the operator. This is the input to Task C.

---

# === CHECKPOINT — HARD STOP (§4) — DO NOT PROCEED TO PHASE 1 ===

## Task C: Operator divergence rulings

**This is a task boundary where execution PAUSES.** Phase 0 is green-against-current and the divergence inventory exists. The implementer does NOT resolve divergences. Hand the inventory to the operator and collect a ruling for EACH:

| Tag | Divergence | Ruling needed |
|---|---|---|
| DIVERGENCE-1 | Pipeline unions open-trade (held) tickers as `excluded`/close-only rows; CLI omits them. | Should standalone `swing eval` also include held tickers (unify), or is this a pipeline-only freshness concern (intentional seam)? |
| DIVERGENCE-2 | Pipeline injects pinned off-screen tickers for full evaluation; CLI omits them. | Unify (CLI gains pin injection) or intentional pipeline-only seam? |
| DIVERGENCE-EQUITY | `current_equity`: pipeline `sizing_equity(real_equity…)` vs CLI `starting_equity`. | Unify on real-equity sizing, or keep CLI on `starting_equity` (intentional)? Only matters for persisted columns if the diff showed any. |
| DIVERGENCE-ERROR-DEDUP | Pipeline de-dupes error vs excluded (one row); CLI may emit two. | Unify on dedup (intentional only if a reason exists). |
| DIVERGENCE-EXCLUDED-CLOSE | Pipeline preserves held close on excluded rows. | Follows DIVERGENCE-1's ruling. |
| DIVERGENCE-SPY-GUARD | CLI tolerates SPY fetch failure (warn + 0.0); pipeline raises (fails the step). | Unify on the guarded path, or keep pipeline hard-failing (intentional seam)? Success-path identical. |

**Each ruling resolves to ONE of:**
- **(a) Unify** → the behavior is shared code in the orchestrator; the harness's `DIVERGENCE-n` assertion is **MIGRATED** to a parity assertion (both paths now identical on that dimension) IN THE SAME TASK that implements the unification, keeping the harness green.
- **(b) Intentional** → the difference is kept as an injected-seam parameter and TESTED as intentional (the harness asserts the seam value drives the difference). No silent preservation.

> Record each ruling inline in the plan (or a `docs/`-tracked decision note) before Phase 1. **No silent unification, no silent preservation.** If a ruling demands a schema change or a new dependency to honor → STOP and route to CHARC.

---

# PHASE 1 — Extract the orchestrator + wire the PIPELINE adapter FIRST (the gate-bearing path)

> Pipeline first because it is the gate-bearing path (the nightly). The harness stays green at every commit.

## Task 1.1: Create the orchestrator module skeleton (seam dataclasses + signature)

**Files:**
- Create: `swing/evaluation/orchestration.py`
- Test: `tests/evaluation/test_orchestration.py`

- [ ] **Step 1: Write a failing unit test** asserting the dataclasses + function import with the canonical signature and that an empty `UniverseAugmentation()` has empty `held_tickers`/`pinned_inject`.

```python
def test_universe_augmentation_default_empty():
    from swing.evaluation.orchestration import UniverseAugmentation
    a = UniverseAugmentation()
    assert a.held_tickers == () and a.pinned_inject == ()
```

- [ ] **Step 2: Run → fail (module missing).** `python -m pytest tests/evaluation/test_orchestration.py::test_universe_augmentation_default_empty -v` → FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Create `swing/evaluation/orchestration.py`** with the EXACT dataclasses + `orchestrate_evaluation` signature from the canonical API block above, body `raise NotImplementedError` for now.

- [ ] **Step 4: Run → pass. Commit.**
```bash
git add swing/evaluation/orchestration.py tests/evaluation/test_orchestration.py
git commit -m "feat(evaluation): Task 1.1 — orchestration module seam dataclasses + signature"
```

## Task 1.2: Implement the orchestrator body (extract the shared stages verbatim)

**Files:**
- Modify: `swing/evaluation/orchestration.py`
- Test: `tests/evaluation/test_orchestration.py`

- [ ] **Step 1: Write failing unit tests** for the orchestrator driven directly (not through an adapter), using the Phase-0 offline-archive fixtures:
  - empty augmentation → only screen tickers evaluated; no pin_injection note fired; persisted-equivalent rows to the CLI golden.
  - augmentation with `held_tickers=("HHH",)` → HHH appears `excluded` with preserved close; `output.note_pin_injection` NOT fired for held.
  - augmentation with `pinned_inject=("PPP",)` not in seen → PPP fully evaluated; `note_pin_injection(["PPP"])` fired once.
  - `persist` callback invoked exactly once with `(run, candidates)`; its return value becomes `result.run_id`.
  - `pre_fetch_hook` invoked once with the merged ticker list BEFORE the fetch loop.

- [ ] **Step 2: Run → fail (`NotImplementedError`).**

- [ ] **Step 3: Implement the body** by lifting the SHARED stages from `_step_evaluate` (`runner.py:1388-1611`), parameterizing the seams. Order, lifted verbatim except for the seam substitutions:
  1. `finviz_df = pd.read_csv(csv_path)`; `Ticker` guard → `ValueError`; tickers list; `sector_industry_by_ticker` map (identical loop).
  2. `tickers` augmentation: `seen = set(tickers)`; append `augmentation.held_tickers` (not in seen); compute `injected_pins = [t for t in augmentation.pinned_inject if t not in seen]`, append; if `injected_pins`: `output.note_pin_injection(injected_pins)`.
  3. `if pre_fetch_hook is not None: pre_fetch_hook(list(tickers))` — at the held-tickers boundary (LOCK #16 — the hook IS the warm+prewarm in the pipeline adapter; called with the same merged set the runner currently passes).
  4. SPY fetch — implement the GUARDED (CLI) form by default IF the operator ruled DIVERGENCE-SPY-GUARD → unify; else keep straight-line and add an `on_spy_error` seam per the ruling. `as_of_date` threaded into `fetcher.get`.
  5. per-ticker OHLCV fetch + universe returns (identical loops; `as_of_date` threaded).
  6. `BatchContext(...)` (identical).
  7. `data_asof = max(max_dates).date() if max_dates else last_completed_session(run_now)`; `action_session = action_session_for_run(run_now)`.
  8. `excluded = set(cfg.etf_exclusion.manual_block) | set(augmentation.held_tickers)`; build `contexts` with `current_equity=current_equity` (the seam) — identical loop.
  9. `candidates = evaluate_batch(contexts)`.
  10. synthesize excluded rows — preserve close for held (per DIVERGENCE-EXCLUDED-CLOSE ruling); `notes = "open position" if t in held_set else "ETF/fund blocklist"`.
  11. `error_tickers` dedup vs excluded (per DIVERGENCE-ERROR-DEDUP ruling) — gated so the CLI behavior is honored if the ruling is "intentional".
  12. synthesize error rows.
  13. sector/industry `_dc_replace` plumb (identical).
  14. build `EvaluationRun(...)` (identical counts).
  15. `run_id = persist(run, candidates)`.
  16. `return OrchestrationResult(run_id=run_id, run=run, candidates=candidates)`.

> Every divergence-bearing branch (steps 4/8/10/11) is written to honor the Task-C ruling: if "unify", the branch is unconditional shared code; if "intentional", the branch is gated on the seam value (`augmentation`, `current_equity`, or a dedicated flag) so the CLI adapter reproduces its prior behavior exactly. Do NOT hardcode the pipeline behavior into shared code where the ruling said "intentional difference."

- [ ] **Step 4: Run the new unit tests → pass. Run the Phase-0 harness → STILL GREEN** (the orchestrator isn't wired into either path yet, so this just confirms no import-time breakage). Commit.
```bash
git add swing/evaluation/orchestration.py tests/evaluation/test_orchestration.py
git commit -m "feat(evaluation): Task 1.2 — orchestrate_evaluation body with explicit injection seams"
```

## Task 1.3: Wire `_step_evaluate` to the orchestrator (pipeline adapter)

**Files:**
- Modify: `swing/pipeline/runner.py:1382-1619`

- [ ] **Step 1: Confirm the Phase-0 pipeline golden test is green pre-change** (`test_pipeline_path_persists_screen_plus_augmentation`, `test_golden_parity_divergences_are_pinned`). This is the regression net for this task.

- [ ] **Step 2: Rewrite `_step_evaluate` as the adapter** — `lease.verify_held()`, then assemble the seam values and call the orchestrator:
  - compute `held_tickers` (the `list_open_trades` block, `runner.py:1416-1427`) and `pinned_inject` (the `list_active_watchlist` block, `runner.py:1435-1445`) → `UniverseAugmentation(held_tickers=tuple(held), pinned_inject=tuple(pins))`.
  - compute `sizing_eq` (the `current_equity`/`sizing_equity` block, `runner.py:1514-1525`) → pass as `current_equity`.
  - build the `pre_fetch_hook` closure capturing `cfg`, `price_cache`, `held_tickers`, `universe`, `run_now`, `run_warnings` and calling `_warm_pipeline_marketdata(...)` + `_prewarm_evaluate_archives(...)` in the SAME order with the SAME args (LOCK #16).
  - build `OrchestrationOutput(note_pin_injection=lambda tickers: run_warnings.append({"step":"evaluate","kind":"pin_injection","count":len(tickers),"tickers":tickers}) if run_warnings is not None else None)` — reproduce the exact warning dict (`runner.py:1446-1450`).
  - build the `persist` closure: `with lease.fenced_write() as conn: run_id = insert_evaluation_run(conn, run); insert_candidates(conn, run_id, candidates); set_evaluation_run_id(conn, pipeline_run_id=lease.run_id, evaluation_run_id=run_id); return run_id` (LOCK #1 — lease stays here).
  - `result = orchestrate_evaluation(cfg=cfg, csv_path=csv_path, universe=universe, universe_hash=universe_hash, run_now=run_now, fetcher=fetcher, current_equity=sizing_eq, persist=persist, as_of_date=None, augmentation=aug, pre_fetch_hook=hook, output=out)`; `return result.run_id`.

- [ ] **Step 3: Run the Phase-0 harness + the existing `tests/pipeline/test_step_evaluate_*.py` → ALL GREEN** (byte-identical persisted rows + warnings). Run: `python -m pytest tests/pipeline/test_step_evaluate_pin_injection.py tests/pipeline/test_step_evaluate_warm.py tests/evaluation/test_orchestration_parity_golden.py -v`. Expected: PASS. If any differ, the extraction changed pipeline behavior — fix the adapter, do not edit the golden.

- [ ] **Step 4: Commit.**
```bash
git add swing/pipeline/runner.py
git commit -m "refactor(pipeline): Task 1.3 — _step_evaluate delegates to orchestrate_evaluation; lease/fence + warm/prewarm stay in the adapter"
```

---

# PHASE 2 — Wire the CLI adapter SECOND

## Task 2.1: Pin the `swing eval` UX surface (stdout text + exit code) before the swap

**Files:**
- Modify: `tests/cli/test_cli_eval.py`

- [ ] **Step 1: Write a frozen-clock characterization test** asserting the current `swing eval` stdout lines (`Evaluating N tickers from <file>`, the `Run {id}: A+=… watch=… skip=… excluded=… error=…` summary, the `Data as of: … Action session: …` line) and `result.exit_code == 0`, driven through the offline-archive fixtures. This pins the operator-gate UX surface (§6).

- [ ] **Step 2: Run → pass on CURRENT CLI. Commit.**
```bash
git add tests/cli/test_cli_eval.py
git commit -m "test(cli): Task 2.1 — characterize swing eval stdout + exit code before the adapter swap"
```

## Task 2.2: Wire `eval_cmd` to the orchestrator (CLI adapter)

**Files:**
- Modify: `swing/cli.py:355-561`

- [ ] **Step 1: Confirm the Phase-0 CLI golden + the Task-2.1 UX test are green pre-change.**

- [ ] **Step 2: Rewrite `eval_cmd` as the adapter** — keep the click decorators, `cfg`, `csv_file`, `as_of_date` parsing, and `run_now = datetime.now()`. Then:
  - load `universe` + `universe_hash`, construct `PriceFetcher` (identical to `cli.py:403-409`).
  - `augmentation` per the Task-C ruling: `UniverseAugmentation()` if DIVERGENCE-1/2 ruled intentional-pipeline-only; or compute held/pins (mirroring the runner) if ruled unify.
  - `current_equity` per the DIVERGENCE-EQUITY ruling: `cfg.account.starting_equity` (intentional) or `sizing_equity(...)` (unify).
  - `output = OrchestrationOutput(info=click.echo, warn=lambda m: click.echo(m, err=True))` (note_pin_injection defaults to no-op unless DIVERGENCE-2 ruled unify).
  - `persist` closure: `conn = connect(cfg.paths.db_path); try: with conn: run_id = insert_evaluation_run(conn, run); insert_candidates(conn, run_id, candidates); finally: conn.close(); return run_id` (plain transaction — no lease).
  - emit the `Evaluating N tickers` line via `output.info` BEFORE the call (preserve ordering) — or pass it through and let the orchestrator emit; choose whichever keeps the Task-2.1 UX test byte-identical. **Simplest faithful choice:** keep the two human-facing echo lines (`Evaluating…`, the `Run … / Data as of …` summary) in the adapter, computed from `result` — the orchestrator's `output.info` carries only shared progress text, if any.
  - `result = orchestrate_evaluation(...); ` then echo the summary from `result.run`/`result.run_id`.

- [ ] **Step 3: Run the Task-2.1 UX test + the Phase-0 CLI golden + the full parity diff → ALL GREEN.** The CLI persisted rows now match its golden (modulo ruled unifications, whose assertions were migrated in the relevant Task-C-derived step). Run: `python -m pytest tests/cli/test_cli_eval.py tests/evaluation/test_orchestration_parity_golden.py -v`. Expected: PASS.

- [ ] **Step 4: Commit.**
```bash
git add swing/cli.py
git commit -m "refactor(cli): Task 2.2 — eval_cmd delegates to orchestrate_evaluation via the plain-transaction persist seam"
```

---

# PHASE 3 — Kill the mirror comment + final verification

## Task 3.1: Delete the mirror comment, replace with a one-line pointer

**Files:**
- Modify: `swing/cli.py` (the `379-388` mirror block) and `swing/pipeline/runner.py` (any reciprocal "mirrors eval_cmd" prose)

- [ ] **Step 1: Delete the mirror prose** at `cli.py:379-388` ("Mirrors the `_step_evaluate` plumbing … persist classification identically") and replace with one line: `# Sector/Industry + classification orchestration is shared: swing.evaluation.orchestration.orchestrate_evaluation (consumed by both eval_cmd and pipeline _step_evaluate).` Remove any now-stale reciprocal comment in `runner.py`.

- [ ] **Step 2: Grep to confirm the mirror is dead.** Run: `grep -rn "persist classification identically\|hand-mirror\|Mirrors the .*_step_evaluate\|Mirrors the runner" swing/`. Expected: no matches (or only the new pointer line).

- [ ] **Step 3: Run the Phase-0 harness once more → green. Commit.**
```bash
git add swing/cli.py swing/pipeline/runner.py
git commit -m "refactor(cli): Task 3.1 — delete the comment-enforced eval mirror; point to the shared orchestrator"
```

## Task 3.2: Full fast suite + ruff on the final head

**Files:** none (verification only)

- [ ] **Step 1: Full fast suite.** Run: `python -m pytest -m "not slow" -q`. Expected: green; the count is read OFF THE FINAL HEAD (never carry a branch/older count forward — the no-false-green discipline). Record the exact passed-count in the return report.

- [ ] **Step 2: Ruff.** Run: `ruff check swing/`. Expected: no NEW violations beyond the banked 18-E501 baseline. If a new violation is introduced, fix it (no incidental edits outside the bundle).

- [ ] **Step 3: Confirm the trailer audit is clean** before any push (orchestrator does the merge, not the implementer): `git log origin/main..HEAD --format='%(trailers)'` → every entry `[]` (ZERO `Co-Authored-By`).

- [ ] **Step 4: No commit** (verification only) — report results to the orchestrator for the §6 operator gate + merge.

---

## Done criteria

- [ ] Phase-0 golden-parity harness exists, drives BOTH paths through the production derivation chain (offline-seeded archive, NOT a stubbed fetcher), and is GREEN on the final head as the permanent parity regression.
- [ ] Every divergence the harness found was ruled by the operator at Task C; each ruling is either unified (assertion migrated) or intentional (seam-tested). No silent unification/preservation.
- [ ] `swing/evaluation/orchestration.py` is the single shared orchestration path; `eval_cmd` and `_step_evaluate` are thin adapters.
- [ ] LOCKS verified: lease/fence + `set_evaluation_run_id` only in the runner adapter; `_warm_pipeline_marketdata`+`_prewarm_evaluate_archives` fire at the same #16 boundary with the same args; Arc-7 pin/held semantics + `pin_injection` warning byte-identical; `evaluate_batch` untouched; no step boundary added/moved (#25 timings intact); NO schema, NO new dependency, no pyproject/config edit.
- [ ] The mirror comment is gone, replaced by a one-line pointer; `grep` confirms no mirror prose remains.
- [ ] `swing eval` UX surface (stdout text + exit code) unchanged (Task-2.1 characterization green).
- [ ] Full fast suite green (count read off the final head); ruff clean (no new violations).
- [ ] Codex adversarial review converged (zero new critical/major); every round's response persisted.

---

## Adversarial review section (for the writing-plans Codex pass + the executing-plans pass)

**Target:** the plan's faithfulness to the brief's §3 shape + §4 protocol, and the executed diff's behavior-preservation.

**Watch items:**
- Does the Phase-0 harness genuinely exercise the production derivation path (real `read_or_fetch_archive`, real `evaluate_batch`), or did it regress to a stubbed fetcher (the byte-parity-insufficient gotcha)?
- Are ALL divergences (the two pre-grounded + D-EQUITY + D-ERROR-DEDUP + D-EXCLUDED-CLOSE + D-SPY-GUARD) surfaced by the harness and routed to the operator — none silently unified or preserved by the implementer?
- Lease/fence + `set_evaluation_run_id` MUST NOT leak into the orchestrator. The orchestrator MUST NOT import `Lease`.
- The `pin_injection` run-warning dict shape MUST be byte-identical (`step`/`kind`/`count`/`tickers`).
- `_warm_pipeline_marketdata`/`_prewarm_evaluate_archives` call order + args unchanged (LOCK #16).
- Every new test pins the clock (R2/D9) — no live `datetime.now()` in a new test.
- The orchestrator must not be hardcoded to pipeline behavior where a ruling said "intentional CLI difference" (gate on the seam, don't bake the pipeline branch into shared code).
- Final fast-suite count read off the merged/ final head, never carried forward.

**Executing worktree:** `<repo>/.worktrees/arc17a-exec` (this plan was authored in `<repo>/.worktrees/arc17a-plan`).
