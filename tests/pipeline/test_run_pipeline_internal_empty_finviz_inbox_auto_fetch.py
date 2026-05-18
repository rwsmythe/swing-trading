"""Pipeline runner auto-fetches Finviz CSV when inbox is empty.

Closes pre-existing bug at ``docs/phase3e-todo.md:940-958`` (operator-reported
2026-05-15 during Phase 12 Sub-bundle A S5 gate; 3rd gate-blocker occurrence
at Phase 12.5 #1 S6 2026-05-18). Before fix: ``select_csv`` at
``swing/pipeline/runner.py:524-528`` raises ``NoFilesError`` and bails BEFORE
the pipeline-step ``_step_finviz_fetch`` (lines 596-606) has a chance to
auto-populate the inbox via the Finviz Elite API. Fresh worktrees always start
with an empty inbox and so always trip this.

Discriminating signals:
  1. Auto-fetch fires (monkeypatch ``_step_finviz_fetch`` invocation count >= 1)
     when the inbox is empty AND the CSV the fake writes makes the retry
     ``select_csv`` succeed → pipeline does NOT fail on the
     ``"No CSV files"`` cause.
  2. Combined error message preserves BOTH the initial NoFilesError cause AND
     the auto-fetch failure cause when the inline auto-fetch raises.
  3. AmbiguousInboxError stays fail-fast — auto-fetch is NOT invoked because
     the bug is an operator manual-override misconfiguration that auto-fetch
     cannot resolve.
  4. No double-fire — when inline auto-fetch fires, the pipeline-step body at
     site 2 is skipped (only 1 invocation across the whole run).

See dispatch brief: ``docs/phase12-5-finviz-inbox-auto-fetch-fix-dispatch-brief.md``.
"""
from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path

import pytest

from swing.config import load
from swing.data.db import ensure_schema
from swing.evaluation.dates import action_session_for_run
from swing.pipeline import run_pipeline
from tests.cli.test_cli_eval import _minimal_config


_CANONICAL_FINVIZ_HEADER = (
    "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
    "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
)
_CANONICAL_FINVIZ_ROW = (
    "1,AAPL,Technology,Consumer Electronics,USA,200.00,0.50,50000000,"
    "1.20,3.50,210.00,150.00,3000000000000\n"
)


def _today_finviz_csv_name() -> str:
    """Compute today's canonical finviz CSV filename per runner's anchor."""
    session = action_session_for_run(datetime.now())
    fmt = "%#d" if platform.system() == "Windows" else "%-d"
    return f"finviz{session.strftime(f'{fmt}%b%Y')}.csv"


def _setup_world(tmp_path: Path):
    """Bootstrap project + home + minimal cfg + ensured schema."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    ensure_schema(cfg.paths.db_path).close()
    cfg.paths.finviz_inbox_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def test_empty_inbox_triggers_inline_auto_fetch_and_clears_no_csv_cause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty inbox + auto-fetch writes CSV → pipeline does NOT fail on NoFilesError.

    Before fix: ``select_csv`` raises NoFilesError + pipeline state='failed'
    + error_message='No CSV files in <dir>' + ``_step_finviz_fetch`` NEVER
    invoked.

    After fix: NoFilesError caught + inline ``_step_finviz_fetch`` invoked
    once + writes a CSV + retry ``select_csv`` succeeds + pipeline proceeds
    past site 1. Pipeline may still fail downstream (yfinance / weather / etc.)
    but NOT on the empty-inbox cause; and the site-2 pipeline-step body is
    skipped (only 1 invocation total).
    """
    cfg = _setup_world(tmp_path)
    csv_path = cfg.paths.finviz_inbox_dir / _today_finviz_csv_name()

    invocation_count = {"n": 0}

    def fake_step_finviz_fetch(*, cfg, lease):
        invocation_count["n"] += 1
        csv_path.write_text(_CANONICAL_FINVIZ_HEADER + _CANONICAL_FINVIZ_ROW)

    monkeypatch.setattr(
        "swing.pipeline.runner._step_finviz_fetch",
        fake_step_finviz_fetch,
    )

    result = run_pipeline(cfg=cfg, trigger="manual")

    # Discriminating signal #1: auto-fetch fired EXACTLY ONCE — site-2 body
    # was skipped via ``finviz_fetched_inline=True`` (no double-fire).
    assert invocation_count["n"] == 1, (
        f"expected exactly 1 _step_finviz_fetch invocation (inline only; "
        f"site-2 pipeline-step body skipped); got {invocation_count['n']}"
    )

    # Discriminating signal #2: CSV is now present (fake wrote it).
    assert csv_path.exists(), (
        f"expected fake auto-fetch to write {csv_path}; not found"
    )

    # Discriminating signal #3: pipeline did NOT fail on the empty-inbox
    # cause. The run may still fail downstream (yfinance/weather/Schwab),
    # but the error_message must NOT carry the "No CSV files" substring.
    msg = (result.error_message or "").lower()
    assert "no csv files" not in msg, (
        f"empty-inbox cause should be cleared by auto-fetch; "
        f"got state={result.state!r} error_message={result.error_message!r}"
    )


def test_empty_inbox_auto_fetch_failure_yields_combined_error_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty inbox + auto-fetch raises → state='failed' + combined message preserves both causes.

    Per dispatch brief §0.3 contract #2: "if the inline ``_step_finviz_fetch``
    fails OR retry still finds no CSV → fail with combined error message
    preserving both causes."

    Per ``docs/phase3e-todo.md:940-958`` recommendation: combined error
    message includes the auto-fetch failure cause AND the initial empty-inbox
    cause substring so operator triage sees both halves of the story.
    """
    cfg = _setup_world(tmp_path)

    class _SimulatedFinvizApiError(RuntimeError):
        pass

    def fake_step_finviz_fetch_raising(*, cfg, lease):
        raise _SimulatedFinvizApiError("simulated Finviz API auth failure")

    monkeypatch.setattr(
        "swing.pipeline.runner._step_finviz_fetch",
        fake_step_finviz_fetch_raising,
    )

    result = run_pipeline(cfg=cfg, trigger="manual")

    # Discriminating: state is 'failed' on the combined cause.
    assert result.state == "failed", (
        f"expected state='failed' on auto-fetch failure; "
        f"got state={result.state!r} error_message={result.error_message!r}"
    )

    msg = result.error_message or ""
    msg_lower = msg.lower()

    # Discriminating signal #1: combined message names the auto-fetch
    # failure leg (substring 'auto-fetch' present).
    assert "auto-fetch" in msg_lower, (
        f"combined error_message should reference the auto-fetch failure "
        f"leg; got: {msg!r}"
    )

    # Discriminating signal #2: combined message preserves the initial
    # NoFilesError cause substring ('no csv files' present).
    assert "no csv files" in msg_lower, (
        f"combined error_message should preserve the initial empty-inbox "
        f"cause substring; got: {msg!r}"
    )

    # Discriminating signal #3: the simulated exception's message bubbles
    # into the combined report (operator triage anchor).
    assert "simulated finviz api auth failure" in msg_lower, (
        f"combined error_message should embed the auto-fetch failure "
        f"detail; got: {msg!r}"
    )


def test_ambiguous_inbox_still_fails_fast_without_auto_fetch_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multiple CSVs in inbox → AmbiguousInboxError fail-fast + auto-fetch NOT invoked.

    Per dispatch brief §0.3 contract #1: "``AmbiguousInboxError`` catch stays
    fail-fast — only ``NoFilesError`` triggers the inline retry.
    AmbiguousInboxError is operator's manual-override misconfiguration;
    auto-fetch wouldn't help."

    Discriminating: ``_step_finviz_fetch`` invocation count MUST be 0 — the
    split catch must NOT funnel AmbiguousInboxError into the retry path.
    """
    cfg = _setup_world(tmp_path)
    # Plant two CSVs whose filename date stamps both parse to the SAME date
    # via the ``_FILENAME_DATE_RE`` regex — that is the canonical
    # AmbiguousInboxError trigger per ``swing/pipeline/finviz_select.py:74``.
    # ``finviz1Jan2025.csv`` and ``finviz1Jan2025-copy.csv`` both match the
    # ``(\d{1,2})([A-Za-z]{3})(\d{4})`` substring "1Jan2025" so both tie at
    # the noon-timestamp key for 2025-01-01 → ``dated_tied`` length > 1 →
    # ambiguity raised.
    (cfg.paths.finviz_inbox_dir / "finviz1Jan2025.csv").write_text(
        _CANONICAL_FINVIZ_HEADER + _CANONICAL_FINVIZ_ROW
    )
    (cfg.paths.finviz_inbox_dir / "finviz1Jan2025-copy.csv").write_text(
        _CANONICAL_FINVIZ_HEADER + _CANONICAL_FINVIZ_ROW
    )

    invocation_count = {"n": 0}

    def fake_step_finviz_fetch(*, cfg, lease):
        invocation_count["n"] += 1

    monkeypatch.setattr(
        "swing.pipeline.runner._step_finviz_fetch",
        fake_step_finviz_fetch,
    )

    result = run_pipeline(cfg=cfg, trigger="manual")

    # Discriminating signal #1: state='failed' on ambiguous-inbox cause.
    assert result.state == "failed", (
        f"expected state='failed' on AmbiguousInboxError; "
        f"got state={result.state!r} error_message={result.error_message!r}"
    )

    # Discriminating signal #2: error_message names the ambiguous-inbox
    # cause. ``AmbiguousInboxError`` text from ``swing/pipeline/finviz_select.py``
    # surfaces as "ambiguous candidates" or similar — assert a stable
    # substring marker without locking the exact wording.
    msg = (result.error_message or "").lower()
    assert ("ambiguous" in msg or "multiple" in msg), (
        f"expected AmbiguousInboxError-style message; got: {result.error_message!r}"
    )

    # Discriminating signal #3 (THE KEY ONE): auto-fetch was NOT invoked.
    # Before fix: combined catch routes BOTH NoFilesError + AmbiguousInboxError
    # through the same path; widening to call auto-fetch on AmbiguousInboxError
    # would burn a Finviz API quota call needlessly + persist a confusing
    # audit row (the operator's manual-override files would still be there,
    # ambiguity unresolved).
    assert invocation_count["n"] == 0, (
        f"AmbiguousInboxError must NOT route through auto-fetch retry; "
        f"got {invocation_count['n']} invocations"
    )
