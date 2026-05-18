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


def test_empty_inbox_inline_auto_fetch_writes_exactly_one_audit_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Brief §0.3 contract #5 pin: exactly 1 finviz_api_calls audit row when inline fires.

    Codex R1 Major #2 fix: the earlier tests monkeypatch
    ``_step_finviz_fetch`` ENTIRELY which bypasses the real audit-row
    insertion path. This test instead monkeypatches the lower-level
    ``_finviz_fetch_core`` to return a synthetic OK result dict so the
    REAL ``_step_finviz_fetch`` body runs end-to-end (including the
    lease-fenced audit-row insert at ``runner.py:2196`` and the file
    shadow-write + promote dance). Discriminating signals: (a) auto-fetch
    pathway emits EXACTLY ONE ``finviz_api_calls`` row + (b) row's
    ``status='ok'`` + (c) site-2 body skipped so no SECOND row is
    written for the same pipeline run.

    A pre-fix regression where the double-fire-skip is removed at site 2
    would surface 2 rows; a regression where ``_step_finviz_fetch``
    drops the audit insert would surface 0 rows.
    """
    cfg = _setup_world(tmp_path)
    csv_text = _CANONICAL_FINVIZ_HEADER + _CANONICAL_FINVIZ_ROW

    # Synthetic ``_finviz_fetch_core`` result mirroring the OK-path shape
    # from ``swing/pipeline/runner.py:2123-2129`` (real return dict keys).
    import platform as _platform
    session_today = action_session_for_run(datetime.now())
    fmt = "%#d" if _platform.system() == "Windows" else "%-d"
    target_csv = cfg.paths.finviz_inbox_dir / (
        f"finviz{session_today.strftime(f'{fmt}%b%Y')}.csv"
    )

    def fake_finviz_fetch_core(cfg_in):
        return {
            "status": "ok",
            "csv_text": csv_text,
            "csv_path": target_csv,
            "row_count": 1,
            "response_time_ms": 5,
            "signature_hash": "deadbeef" * 8,  # 64-char hex
            "rate_limit_remaining": 100,
            "error_message": None,
        }

    monkeypatch.setattr(
        "swing.pipeline.runner._finviz_fetch_core",
        fake_finviz_fetch_core,
    )

    result = run_pipeline(cfg=cfg, trigger="manual")

    # Read post-run finviz_api_calls table directly via fresh connection.
    import sqlite3
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        rows = conn.execute(
            "SELECT call_id, status, error_message, signature_hash "
            "FROM finviz_api_calls ORDER BY call_id ASC"
        ).fetchall()
    finally:
        conn.close()

    # Discriminating signal #1 (THE KEY ONE): exactly 1 audit row written.
    # A site-2 double-fire regression would surface 2; a missing-insert
    # regression would surface 0.
    assert len(rows) == 1, (
        f"brief §0.3 contract #5: expected EXACTLY 1 finviz_api_calls audit row "
        f"per pipeline run when inline auto-fetch fires; got {len(rows)} rows: "
        f"{rows}"
    )

    # Discriminating signal #2: the single row reflects the OK result.
    _call_id, status, error_message, signature_hash = rows[0]
    assert status == "ok", (
        f"expected status='ok' from synthetic _finviz_fetch_core; "
        f"got status={status!r} error_message={error_message!r}"
    )
    assert signature_hash == "deadbeef" * 8, (
        f"expected signature_hash to roundtrip from synthetic result; "
        f"got {signature_hash!r}"
    )

    # Discriminating signal #3: pipeline did NOT fail on empty-inbox cause.
    msg = (result.error_message or "").lower()
    assert "no csv files" not in msg, (
        f"empty-inbox cause should be cleared by auto-fetch; "
        f"got state={result.state!r} error_message={result.error_message!r}"
    )

    # Discriminating signal #4: target CSV is present post-run (real shadow-
    # write + promote dance ran via _step_finviz_fetch).
    assert target_csv.exists(), (
        f"_step_finviz_fetch shadow-write + promote should have created "
        f"{target_csv}; not found"
    )


def test_empty_inbox_silent_fetch_error_surfaces_audit_detail_in_combined_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Brief Codex R1 Major #1 pin: silent ``_finviz_fetch_core`` status='error' surfaces in combined report.

    The COMMON real-world failure mode (operator missing Finviz token,
    auth failure, rate limit, schema parity) does NOT raise from
    ``_step_finviz_fetch`` — ``_finviz_fetch_core`` returns
    ``status='error'`` + an audit row is inserted + the function returns
    normally. Without R1 M#1's diagnostic enrichment, the retry-NoFilesError
    combined message would carry only a redundant "No CSV files in <dir>
    (initial: No CSV files in <dir>)" — the operator sees the same
    "no CSV files" twice and no hint about WHY the auto-fetch produced
    no CSV.

    With R1 M#1 fix: ``_read_latest_finviz_call_diagnostic`` reads the
    just-inserted audit row + the combined message embeds
    ``[auto-fetch audit: status='error', error=<the real cause>]``.

    Discriminating signal: simulate the missing-token error path; assert
    the combined error_message contains BOTH the canonical audit detail
    substring ('auto-fetch audit:') AND the real-cause substring
    (e.g. ``FinvizConfigMissingError`` text).
    """
    cfg = _setup_world(tmp_path)

    target_csv = cfg.paths.finviz_inbox_dir / _today_finviz_csv_name()

    def fake_finviz_fetch_core_silent_error(cfg_in):
        # Mirrors the missing-token return shape from
        # ``swing/pipeline/runner.py:2098-2103`` verbatim — _step_finviz_fetch
        # body runs normally + inserts an audit row with status='error' +
        # returns silently (does NOT raise).
        return {
            "status": "error",
            "csv_text": None,
            "csv_path": target_csv,
            "row_count": None,
            "response_time_ms": 0,
            "signature_hash": None,
            "rate_limit_remaining": None,
            "error_message": "FinvizConfigMissingError: token is missing",
        }

    monkeypatch.setattr(
        "swing.pipeline.runner._finviz_fetch_core",
        fake_finviz_fetch_core_silent_error,
    )

    result = run_pipeline(cfg=cfg, trigger="manual")

    # state=failed because retry select_csv still raises NoFilesError
    # (no CSV was written; the fake returned status='error').
    assert result.state == "failed", (
        f"expected state='failed' on silent _finviz_fetch_core error; "
        f"got state={result.state!r} error_message={result.error_message!r}"
    )

    msg = result.error_message or ""
    msg_lower = msg.lower()

    # Discriminating signal #1: canonical diagnostic-enrichment marker
    # present (proves _read_latest_finviz_call_diagnostic ran + retrieved
    # the audit row).
    assert "auto-fetch audit:" in msg_lower, (
        f"R1 M#1 diagnostic enrichment should embed 'auto-fetch audit:' "
        f"marker referencing the just-written audit row; got: {msg!r}"
    )

    # Discriminating signal #2: the real underlying cause from
    # _finviz_fetch_core's error_message bubbles through to the operator
    # via the audit-row read (NOT redundant 'No CSV files' twice).
    assert "finvizconfigmissingerror" in msg_lower, (
        f"R1 M#1 diagnostic enrichment should include the audit row's "
        f"underlying error_message; got: {msg!r}"
    )

    # Discriminating signal #3: status='error' from the audit row is
    # surfaced (operator can grep the message for the audit status).
    assert "status='error'" in msg or "status=error" in msg, (
        f"R1 M#1 diagnostic enrichment should include the audit row's "
        f"status; got: {msg!r}"
    )

    # Discriminating signal #4: initial NoFilesError cause is STILL
    # preserved in the combined message (brief §0.3 contract #2).
    assert "no csv files" in msg_lower, (
        f"combined error_message should still preserve the initial "
        f"NoFilesError cause substring; got: {msg!r}"
    )


def test_empty_inbox_diagnostic_is_causally_scoped_to_this_pipeline_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Brief Codex R2 Major #1 pin: diagnostic read scoped to THIS call, not "latest globally".

    Plant a PRIOR ``finviz_api_calls`` row (status='ok' from some prior
    surface invocation) BEFORE invoking the pipeline. The R1 code
    (before R2 fix) would have used ``list_recent_calls(limit=1)`` and
    surfaced THE PRIOR ROW's status='ok' + error=None — a false
    confidence "auto-fetch succeeded" report when the actual inline
    fetch silently failed. With R2 M#1 ``after_call_id`` scoping, the
    diagnostic correctly surfaces the FRESH row inserted by this
    pipeline's inline ``_step_finviz_fetch`` (status='error' + the real
    underlying cause).

    Discriminating signal: the combined error message must contain the
    FRESH-row marker ('FinvizSchemaParityError' from this run's
    monkeypatched fake) AND must NOT contain any 'auto-fetch audit:
    status=\\'ok\\'' substring (the prior row's status). A regression
    that drops the ``after_call_id`` scoping would surface
    ``status='ok'`` from the planted prior row.
    """
    import sqlite3

    cfg = _setup_world(tmp_path)
    target_csv = cfg.paths.finviz_inbox_dir / _today_finviz_csv_name()

    # Plant a PRIOR successful audit row (call_id=1; from a hypothetical
    # earlier surface invocation). Its status='ok' would be surfaced by
    # the R1 unscoped "latest globally" read, which is the false-
    # attribution bug R2 M#1 fixes.
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        conn.execute(
            "INSERT INTO finviz_api_calls "
            "(ts, screen_query, status, row_count, response_time_ms, "
            " rate_limit_remaining, signature_hash, error_message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-01-01T00:00:00", "v=152", "ok", 100, 50,
                100, "deadbeef" * 8, None,
            ),
        )
        conn.commit()
        # Confirm the prior row exists + capture its call_id (expected 1).
        prior_row = conn.execute(
            "SELECT call_id, status FROM finviz_api_calls"
        ).fetchall()
        assert len(prior_row) == 1, f"setup error: expected 1 prior row; got {prior_row!r}"
        assert prior_row[0][1] == "ok", (
            f"setup error: prior row should be status='ok'; got {prior_row[0]!r}"
        )
    finally:
        conn.close()

    def fake_finviz_fetch_core_silent_schema_error(cfg_in):
        # Different distinguishable error than the prior gotcha test's
        # ConfigMissingError so the assertion is unambiguous.
        return {
            "status": "error",
            "csv_text": None,
            "csv_path": target_csv,
            "row_count": None,
            "response_time_ms": 12,
            "signature_hash": None,
            "rate_limit_remaining": None,
            "error_message": "FinvizSchemaParityError: expected 13 cols, got 12",
        }

    monkeypatch.setattr(
        "swing.pipeline.runner._finviz_fetch_core",
        fake_finviz_fetch_core_silent_schema_error,
    )

    result = run_pipeline(cfg=cfg, trigger="manual")

    assert result.state == "failed", (
        f"expected state='failed'; got state={result.state!r} "
        f"error_message={result.error_message!r}"
    )

    msg = result.error_message or ""

    # Discriminating signal #1 (THE KEY ONE): diagnostic surfaces THIS
    # pipeline's row, not the prior row.
    assert "FinvizSchemaParityError" in msg, (
        f"R2 M#1 causal-scoping: diagnostic should surface THIS "
        f"pipeline's audit row (status='error', FinvizSchemaParityError); "
        f"got: {msg!r}"
    )

    # Discriminating signal #2: prior row's status='ok' must NOT appear.
    # Match the canonical diagnostic-marker shape literally — the R1
    # code without scoping would have emitted
    # ``[auto-fetch audit: status='ok', ...]``.
    assert "status='ok'" not in msg, (
        f"R2 M#1 causal-scoping: prior-row status='ok' must NOT appear "
        f"in the diagnostic enrichment (would indicate the diagnostic "
        f"is reading the latest-globally row instead of THIS call's); "
        f"got: {msg!r}"
    )

    # Discriminating signal #3: status='error' (this call's row) IS
    # in the diagnostic.
    assert "status='error'" in msg, (
        f"R2 M#1 causal-scoping: this call's status='error' should be "
        f"in the diagnostic; got: {msg!r}"
    )

    # Discriminating signal #4: the row count post-run is 2 (prior + this).
    conn = sqlite3.connect(str(cfg.paths.db_path))
    try:
        post = conn.execute(
            "SELECT call_id, status, error_message FROM finviz_api_calls "
            "ORDER BY call_id ASC"
        ).fetchall()
    finally:
        conn.close()
    assert len(post) == 2, (
        f"expected 2 rows post-run (prior + inline auto-fetch); got {post!r}"
    )
    assert post[0][1] == "ok", f"prior row drift: {post[0]!r}"
    assert post[1][1] == "error", f"new row should be 'error': {post[1]!r}"
