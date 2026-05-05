"""CLI: swing trade entry / exit / list / stop-adjust / advisory."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


# Phase 7 Sub-B B.8 — minimal pre-trade-field flag set required by the
# entry-create validator (`OPERATION_REQUIRED_FIELDS["entry_create"]` +
# conditional rules). Helper keeps legacy tests focused on what they
# actually assert (rationale taxonomy, exit/stop-adjust semantics, etc.)
# without each test repeating 18 flags.
_PRE_TRADE_OK_FLAGS: tuple[str, ...] = (
    "--thesis", "Setup meets criteria",
    "--why-now", "Trigger today",
    "--invalidation", "Close below stop",
    "--expected-scenario", "Run to target",
    "--premortem-technical", "Stop hits on weak hold",
    "--premortem-market-sector", "Sector rolls over",
    "--premortem-execution", "Slippage on entry",
    "--emotional-state", "calm",
    "--manual-entry-confidence", "normal",
    "--market-regime", "Bullish",
    "--catalyst", "technical_only",
)


def test_trade_entry_then_list(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "vcp-breakout",
        *_PRE_TRADE_OK_FLAGS,
    ])
    assert result.exit_code == 0, result.output
    assert "trade id" in result.output.lower() or "entered" in result.output.lower()

    result2 = runner.invoke(main, ["--config", str(cfg), "trade", "list"])
    assert result2.exit_code == 0
    assert "AAPL" in result2.output


def _read_hypothesis_label(cfg_path: Path, ticker: str) -> str | None:
    """Helper: read trades.hypothesis_label for the given ticker via the repo
    layer (round-trip through the same SELECT path the dashboard uses)."""
    import tomllib
    from swing.data.db import connect
    from swing.data.repos.trades import find_any_open_trade

    cfg_data = tomllib.loads(cfg_path.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        t = find_any_open_trade(conn, ticker=ticker)
        return t.hypothesis_label if t is not None else None
    finally:
        conn.close()


def test_trade_entry_without_hypothesis_flag_stores_null(tmp_path: Path):
    """Existing call site preservation: invoking entry without --hypothesis
    stores NULL on the trades row (no behavior change for legacy invocations)."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "BBB", "--entry-date", "2026-04-15",
        "--entry-price", "100.0", "--shares", "1",
        "--initial-stop", "90.0", "--rationale", "vcp-breakout",
        *_PRE_TRADE_OK_FLAGS,
    ])
    assert result.exit_code == 0, result.output
    assert _read_hypothesis_label(cfg, "BBB") is None


def test_trade_entry_with_hypothesis_flag_stores_label(tmp_path: Path):
    """Brief §4.4: --hypothesis TEXT carries through to trades.hypothesis_label."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "CCC", "--entry-date", "2026-04-15",
        "--entry-price", "100.0", "--shares", "1",
        "--initial-stop", "90.0", "--rationale", "vcp-breakout",
        "--hypothesis", "Sub-A+ candidate meeting TT + price threshold",
        *_PRE_TRADE_OK_FLAGS,
    ])
    assert result.exit_code == 0, result.output
    assert _read_hypothesis_label(cfg, "CCC") == \
        "Sub-A+ candidate meeting TT + price threshold"


def test_trade_list_shows_remaining_shares_after_partial_exit(tmp_path: Path):
    """Regression: `trade list` displayed `initial_shares` instead of
    remaining shares after partial exits. The web dashboard correctly
    computed remaining; the CLI did not. Both surfaces must agree."""
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "VIR", "--entry-date", "2026-04-20",
        "--entry-price", "10.76", "--shares", "2",
        "--initial-stop", "8.26", "--rationale", "near-trigger-breakout",
        *_PRE_TRADE_OK_FLAGS,
    ])
    runner.invoke(main, [
        "--config", str(cfg), "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-04-20",
        "--exit-price", "11.50", "--shares", "1",
        "--reason", "partial",
    ])
    result = runner.invoke(main, ["--config", str(cfg), "trade", "list"])
    assert result.exit_code == 0, result.output
    # Output row should show 1 share remaining (2 initial - 1 exited),
    # not 2. Column is space-padded; grep for the VIR row and assert the
    # shares column.
    vir_lines = [ln for ln in result.output.splitlines() if "VIR" in ln]
    assert len(vir_lines) == 1, f"expected 1 VIR row, got {vir_lines}"
    row = vir_lines[0]
    # B.7 column rewrite: the rightmost column is now the lifecycle state
    # ('partial_exited' after a partial exit, formerly 'open'). The shares
    # column is the token immediately before that state.
    parts = row.split()
    sh_idx = parts.index("partial_exited") - 1
    assert parts[sh_idx] == "1", (
        f"trade list showed {parts[sh_idx]} shares after partial exit; "
        f"expected 1. full row: {row!r}"
    )


def test_trade_exit(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-04-22",
        "--exit-price", "200.0", "--shares", "5",
        "--reason", "target",
    ])
    assert result.exit_code == 0, result.output
    assert "R" in result.output


def test_trade_stop_adjust_blocked_when_lowering(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust",
        "--trade-id", "1", "--new-stop", "165.0", "--rationale", "manual-trail",
    ])
    assert result.exit_code != 0
    assert "regression" in result.output.lower() or "force" in result.output.lower()


def test_trade_stop_adjust_persists_notes(tmp_path: Path):
    """Bug 3b: `swing trade stop-adjust --notes ...` writes notes to
    trade_events.notes (distinct from rationale)."""
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust",
        "--trade-id", "1", "--new-stop", "175.0",
        "--rationale", "trail-10ma",
        "--notes", "low-volume up-day",
    ])
    assert result.exit_code == 0, result.output

    # Verify persisted notes via the repo, mirroring the service-level test
    # pattern (matches how other CLI tests read-back results).
    from swing.config import load as load_cfg
    from swing.data.db import connect
    from swing.data.repos.trades import list_events_for_trade
    conn = connect(load_cfg(cfg).paths.db_path)
    try:
        adj = next(
            e for e in list_events_for_trade(conn, 1) if e.event_type == "stop_adjust"
        )
    finally:
        conn.close()
    assert adj.rationale == "trail-10ma"
    assert adj.notes == "low-volume up-day"


# ---------------------------------------------------------------------------
# Tranche B-ops T4 — CLI side: --rationale closed taxonomy
# ---------------------------------------------------------------------------

def test_trade_entry_cli_rejects_invalid_rationale(tmp_path: Path):
    """T4: `swing trade entry --rationale foo` where foo is not an enum value
    exits non-zero. Pre-T4 any free-text string was accepted."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0",
        "--rationale", "my-favourite-setup",
    ])
    assert result.exit_code != 0, result.output
    # click.Choice surfaces the valid options in its error output.
    assert "invalid" in result.output.lower() or "choice" in result.output.lower()
    assert "aplus-setup" in result.output


def test_trade_entry_cli_other_requires_notes(tmp_path: Path):
    """T4: `--rationale other` without `--notes` → ClickException.
    With `--notes` the entry succeeds."""
    runner, cfg = _setup(tmp_path)
    bad = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "other",
    ])
    assert bad.exit_code != 0
    assert "notes" in bad.output.lower()

    good = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "other",
        "--notes", "unclassified — spec-break test",
        *_PRE_TRADE_OK_FLAGS,
    ])
    assert good.exit_code == 0, good.output


# ---------------------------------------------------------------------------
# Tranche B-ops T5 — CLI side: --rationale closed taxonomy for stop-adjust
# ---------------------------------------------------------------------------

def test_trade_stop_adjust_cli_rejects_invalid_rationale(tmp_path: Path):
    """T5: `swing trade stop-adjust --rationale trail-10MA` (wrong case) →
    non-zero exit. Pre-T5 free text was accepted."""
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust",
        "--trade-id", "1", "--new-stop", "175.0",
        "--rationale", "trail-10MA",  # wrong case — lowercase only
    ])
    assert result.exit_code != 0, result.output
    assert "invalid" in result.output.lower() or "choice" in result.output.lower()
    assert "trail-10ma" in result.output


def test_trade_stop_adjust_cli_other_requires_notes(tmp_path: Path):
    """T5: `--rationale other` without `--notes` → ClickException.
    With `--notes` the adjust succeeds."""
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    bad = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust",
        "--trade-id", "1", "--new-stop", "175.0", "--rationale", "other",
    ])
    assert bad.exit_code != 0
    assert "notes" in bad.output.lower()

    good = runner.invoke(main, [
        "--config", str(cfg), "trade", "stop-adjust",
        "--trade-id", "1", "--new-stop", "175.0", "--rationale", "other",
        "--notes", "unenumerated case",
    ])
    assert good.exit_code == 0, good.output


# ---------------------------------------------------------------------------
# Tranche B-ops T6 — exit rationale dropped; synthesized from --reason
# ---------------------------------------------------------------------------

def test_trade_exit_cli_rejects_rationale_option(tmp_path: Path):
    """T6: `swing trade exit --rationale ...` now errors with 'no such option'.
    Pre-T6 --rationale was required."""
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-04-22",
        "--exit-price", "200.0", "--shares", "5",
        "--reason", "target", "--rationale", "hit target",
    ])
    assert result.exit_code != 0, result.output
    assert "no such option" in result.output.lower()
    assert "--rationale" in result.output


# ---------------------------------------------------------------------------
# Phase 7 Sub-B B.7 — display column rewrite (Status → State)
# ---------------------------------------------------------------------------


def test_trade_list_shows_state_column_not_status(tmp_path: Path):
    """B.7: ``trade list`` header is 'State' (formerly 'Status') and the column
    renders the lifecycle state ('entered'|'managing'|'partial_exited'|
    'closed'|'reviewed'), NOT the legacy ('open'|'closed') vocabulary.

    Pre-fix: header showed 'Status'; column showed t.status ('open'/'closed').
    Post-fix: header shows 'State'; column shows t.state. Width 14 to fit
    'partial_exited'.

    Seeds via the repo layer to side-step the Sub-B B.1 entry validation gate
    (the CLI ``trade entry`` requires pre-trade fields the test doesn't
    provide).
    """
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.config import load as load_cfg

    runner, cfg = _setup(tmp_path)
    db_path = load_cfg(cfg).paths.db_path
    conn = connect(db_path)
    try:
        with conn:
            insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="MMM", entry_date="2026-04-15",
                    entry_price=100.0, initial_shares=10,
                    initial_stop=90.0, current_stop=90.0,
                    state="managing",
                    watchlist_entry_target=None,
                    watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-15T09:30:00",
            )
    finally:
        conn.close()

    result = runner.invoke(main, ["--config", str(cfg), "trade", "list"])
    assert result.exit_code == 0, result.output
    # Header: "State" replaces "Status"
    assert "State" in result.output, (
        f"expected 'State' header in trade list; got {result.output!r}"
    )
    assert "Status" not in result.output, (
        f"legacy 'Status' header still present; got {result.output!r}"
    )
    # Row: state column shows the lifecycle state, not the legacy 'open' value
    mmm_lines = [ln for ln in result.output.splitlines() if "MMM" in ln]
    assert len(mmm_lines) == 1, f"expected 1 MMM row, got {mmm_lines}"
    assert "managing" in mmm_lines[0]
    assert " open " not in mmm_lines[0]


# ---------------------------------------------------------------------------
# Phase 7 Sub-C C.11 — list_all_exits → fills migration in CLI
# ---------------------------------------------------------------------------


def test_c11_swing_trade_list_does_not_import_list_all_exits(tmp_path: Path):
    """C.11: ``swing trade list`` no longer imports ``list_all_exits`` from
    swing.data.repos.trades; the remaining-shares calculation iterates the
    fills-derived ``_list_all_exitshape_via_fills`` helper.

    Discriminating: under the unmigrated code path, after C.14 deletes
    ``list_all_exits`` the ``trade list`` command would ImportError at
    invocation time. This test forward-protects by verifying the symbol
    is gone from cli.py source — the C.10 helper name
    ``_list_all_exitshape_via_fills`` is preserved (different identifier).
    """
    import re
    import inspect

    from swing import cli

    src = inspect.getsource(cli)
    # Match the bare symbol with word boundaries so the helper
    # ``_list_all_exitshape_via_fills`` (which contains the substring
    # `list_all_exit`) does not register as a match.
    matches = re.findall(r"\blist_all_exits\b", src)
    assert matches == [], (
        f"swing/cli.py still references list_all_exits ({len(matches)} hits); "
        "C.11 migration incomplete. Search for the symbol and replace with "
        "the local _list_all_exitshape_via_fills helper."
    )


def test_c11_swing_trade_list_shows_remaining_after_partial_exit_via_fills(
    tmp_path: Path,
):
    """C.11: ``swing trade list`` continues to show remaining shares after a
    partial exit — same operator-facing output as the pre-C.11 shim path,
    now sourced via fills.

    Discriminating: a buggy migration that walked entry+exit fills together
    would subtract entry quantity too, showing 0 or negative remaining.
    """
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "PXP", "--entry-date", "2026-04-20",
        "--entry-price", "10.0", "--shares", "5",
        "--initial-stop", "8.0", "--rationale", "near-trigger-breakout",
        *_PRE_TRADE_OK_FLAGS,
    ])
    runner.invoke(main, [
        "--config", str(cfg), "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-04-21",
        "--exit-price", "11.0", "--shares", "2",
        "--reason", "partial",
    ])
    result = runner.invoke(main, ["--config", str(cfg), "trade", "list"])
    assert result.exit_code == 0, result.output
    pxp_lines = [ln for ln in result.output.splitlines() if "PXP" in ln]
    assert len(pxp_lines) == 1, f"expected 1 PXP row, got {pxp_lines}"
    parts = pxp_lines[0].split()
    sh_idx = parts.index("partial_exited") - 1
    assert parts[sh_idx] == "3", (
        f"trade list showed {parts[sh_idx]} shares after 2-share partial "
        f"exit; expected 3 remaining (5-2). full row: {pxp_lines[0]!r}"
    )


def test_c11_journal_review_does_not_import_list_all_exits(tmp_path: Path):
    """C.11: ``swing journal review`` no longer imports ``list_all_exits``;
    its all_exits collection is sourced from fills via the local helper.

    Discriminating: pre-migration the symbol appeared at the function-local
    import line; post-migration it must be absent.
    """
    import re
    import inspect

    from swing import cli

    src = inspect.getsource(cli)
    matches = re.findall(r"\blist_all_exits\b", src)
    assert matches == [], (
        f"swing/cli.py still references list_all_exits ({len(matches)} hits); "
        "applies to both `trade list` and `journal review` paths."
    )


def test_trade_exit_cli_persists_reason_as_rationale(tmp_path: Path):
    """T6: trade_events.rationale after a successful exit equals the reason
    value. Pre-T6 rationale was independent free text from --rationale."""
    runner, cfg = _setup(tmp_path)
    runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "AAPL", "--entry-date", "2026-04-15",
        "--entry-price", "180.0", "--shares", "5",
        "--initial-stop", "170.0", "--rationale", "aplus-setup",
        *_PRE_TRADE_OK_FLAGS,
    ])
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "exit",
        "--trade-id", "1", "--exit-date", "2026-04-22",
        "--exit-price", "200.0", "--shares", "5",
        "--reason", "target",
    ])
    assert result.exit_code == 0, result.output

    from swing.config import load as load_cfg
    from swing.data.db import connect
    from swing.data.repos.trades import list_events_for_trade
    conn = connect(load_cfg(cfg).paths.db_path)
    try:
        exit_ev = next(
            e for e in list_events_for_trade(conn, 1) if e.event_type == "exit"
        )
    finally:
        conn.close()
    assert exit_ev.rationale == "target"


# ---------------------------------------------------------------------------
# Phase 7 Sub-B B.8 — CLI new entry options for 18 pre-trade fields
# ---------------------------------------------------------------------------


def _entry_args_minus(*omit: str) -> list[str]:
    """Return _PRE_TRADE_OK_FLAGS as a list with the given flag(s) (and their
    associated value tokens) removed. Used by tests that need to exercise the
    "missing field" gate without re-typing the full 18-flag set."""
    flags = list(_PRE_TRADE_OK_FLAGS)
    out: list[str] = []
    i = 0
    while i < len(flags):
        if flags[i] in omit:
            # skip the flag + its value
            i += 2
            continue
        out.append(flags[i])
        out.append(flags[i + 1])
        i += 2
    return out


def test_cli_trade_entry_rejects_missing_thesis(tmp_path: Path):
    """B.8: CLI entry without --thesis exits non-zero with the missing flag
    surfaced in stderr/output. The validator's MissingPreTradeFieldsException
    is translated to a click.UsageError with the operator-facing flag name."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "TST", "--entry-date", "2026-04-15",
        "--entry-price", "10.0", "--shares", "1",
        "--initial-stop", "9.0", "--rationale", "vcp-breakout",
        *_entry_args_minus("--thesis"),
    ])
    assert result.exit_code != 0, result.output
    assert "--thesis" in result.output, result.output


def test_cli_trade_entry_succeeds_with_all_pre_trade_fields(tmp_path: Path):
    """B.8: CLI entry with the full 18+1 Phase 7 flag set succeeds and
    persists every pre-trade field on the trades row."""
    import tomllib
    from swing.data.db import connect

    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "DDD", "--entry-date", "2026-04-15",
        "--entry-price", "100.0", "--shares", "3",
        "--initial-stop", "90.0", "--rationale", "vcp-breakout",
        "--entry-path", "cli_manual",
        *_PRE_TRADE_OK_FLAGS,
    ])
    assert result.exit_code == 0, result.output

    cfg_data = tomllib.loads(Path(cfg).read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        row = conn.execute(
            """SELECT id, thesis, why_now, invalidation_condition,
                      expected_scenario, premortem_technical,
                      premortem_market_sector, premortem_execution,
                      market_regime, catalyst,
                      emotional_state_pre_trade, event_risk_present,
                      gap_risk_present, trade_origin
               FROM trades WHERE ticker = 'DDD'""",
        ).fetchone()
        # manual_entry_confidence is a fills-table column (B.3 atomic
        # entry-fill insert); read it from the entry fill row.
        fill_row = conn.execute(
            "SELECT manual_entry_confidence FROM fills "
            "WHERE trade_id = ? AND action = 'entry'",
            (row[0],),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    (_id, thesis, why_now, inv, exp_sc, pm_t, pm_ms, pm_e,
     regime, cat, emo, ev_r, gap_r, origin) = row
    assert thesis == "Setup meets criteria"
    assert why_now == "Trigger today"
    assert inv == "Close below stop"
    assert exp_sc == "Run to target"
    assert pm_t == "Stop hits on weak hold"
    assert pm_ms == "Sector rolls over"
    assert pm_e == "Slippage on entry"
    assert regime == "Bullish"
    assert cat == "technical_only"
    assert emo == '["calm"]'
    assert ev_r == 0
    assert gap_r == 0
    # entry_path 'cli_manual' off-pipeline → trade_origin
    # 'manual_off_pipeline' (per derive_trade_origin fallback).
    assert origin in ("manual_off_pipeline", "cli_manual")
    assert fill_row is not None
    assert fill_row[0] == "normal"


def test_cli_trade_entry_emotional_state_multiple_flags(tmp_path: Path):
    """B.8: --emotional-state can be repeated; the CLI persists the click
    multiple-tuple as a JSON-list TEXT (matching the Trade dataclass field
    convention)."""
    import tomllib
    from swing.data.db import connect

    runner, cfg = _setup(tmp_path)
    # Use the no-emotion-state baseline + manually-supplied multi-flag.
    args = _entry_args_minus("--emotional-state")
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "EEE", "--entry-date", "2026-04-15",
        "--entry-price", "100.0", "--shares", "1",
        "--initial-stop", "90.0", "--rationale", "vcp-breakout",
        *args,
        "--emotional-state", "calm",
        "--emotional-state", "confident",
    ])
    assert result.exit_code == 0, result.output

    cfg_data = tomllib.loads(Path(cfg).read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT emotional_state_pre_trade FROM trades WHERE ticker = 'EEE'",
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == '["calm", "confident"]'


def test_cli_trade_entry_event_risk_yes_requires_handling_type_date(
    tmp_path: Path,
):
    """B.8: --event-risk yes without --event-handling/--event-type/--event-date
    fails with all three missing flags surfaced in the error."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "FFF", "--entry-date", "2026-04-15",
        "--entry-price", "100.0", "--shares", "1",
        "--initial-stop", "90.0", "--rationale", "vcp-breakout",
        *_PRE_TRADE_OK_FLAGS,
        "--event-risk", "yes",
        # deliberately omit --event-handling/--event-type/--event-date
    ])
    assert result.exit_code != 0, result.output
    out = result.output
    assert "--event-handling" in out, out
    assert "--event-type" in out, out
    assert "--event-date" in out, out


def test_cli_trade_entry_catalyst_other_requires_description(tmp_path: Path):
    """B.8: --catalyst other without --catalyst-other-description fails with
    that flag surfaced in the error (conditional-rule enforcement)."""
    runner, cfg = _setup(tmp_path)
    args = _entry_args_minus("--catalyst")
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "GGG", "--entry-date", "2026-04-15",
        "--entry-price", "100.0", "--shares", "1",
        "--initial-stop", "90.0", "--rationale", "vcp-breakout",
        *args,
        "--catalyst", "other",
        # deliberately omit --catalyst-other-description
    ])
    assert result.exit_code != 0, result.output
    assert "--catalyst-other-description" in result.output, result.output


def test_cli_trade_entry_force_does_NOT_bypass_pre_trade_gate(tmp_path: Path):
    """B.8: --force does NOT bypass MissingPreTradeFieldsException (spec §9.3:
    pre-trade gate is non-bypassable; --force only bypasses soft-warn cap)."""
    runner, cfg = _setup(tmp_path)
    result = runner.invoke(main, [
        "--config", str(cfg), "trade", "entry",
        "--ticker", "HHH", "--entry-date", "2026-04-15",
        "--entry-price", "100.0", "--shares", "1",
        "--initial-stop", "90.0", "--rationale", "vcp-breakout",
        "--force",
        *_entry_args_minus("--thesis"),
    ])
    assert result.exit_code != 0, result.output
    assert "--thesis" in result.output, result.output
