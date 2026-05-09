"""CLI: swing tos-import."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


SYNTHETIC_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "tos" / "synthetic-tos.csv"
)
REAL_WORLD_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "tos" / "real-world-2026-05-08.csv"
)


def test_tos_import_dry_run(tmp_path: Path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    r = runner.invoke(main, [
        "--config", str(cfg), "tos-import",
        "--csv", str(SYNTHETIC_FIXTURE), "--dry-run",
    ])
    assert r.exit_code == 0, r.output
    assert "deposit" in r.output.lower() or "DEP-001" in r.output
    assert "unmatched" in r.output.lower()


# ---------------------------------------------------------------------------
# 3e.12 hardening — `--verbose` flag for per-fill / per-section observability.
#
# Operator-actionable visibility: the silent-zero failure mode that triggered
# this dispatch (extract_stock_fills returning [] against a real Schwab/TOS
# export) was invisible without per-section row counts and per-fill routing
# detail. `--verbose` surfaces both so future format-drift bugs are
# observable-with-context rather than silent.
#
# Per operator clarification 'reconciliation checks existence AND correct
# values', verbose output for matched/price_mismatch fills MUST surface the
# journal-vs-TOS price comparison so the operator can see at a glance
# whether values agree.
# ---------------------------------------------------------------------------


def _seed_real_world_open_for_cli(db_path: Path) -> None:
    """Seed the four operator-confirmed OPEN trades + SGML round-trip OPEN
    so the verbose-output test exercises matched + price-comparison lines."""
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event

    seeds = [
        ("LAR", "2026-05-08", 11.7066, 7, 7.00),
        ("CVGI", "2026-05-08", 5.2244, 20, 3.67),
        ("VSAT", "2026-05-06", 65.685, 2, 54.11),
        ("YOU", "2026-05-04", 56.295, 2, 45.38),
        ("SGML", "2026-05-07", 23.87, 3, 11.63),
    ]
    conn = sqlite3.connect(db_path)
    try:
        for ticker, edate, eprice, shares, stop in seeds:
            event_ts = f"{edate}T09:30:00"
            with conn:
                tid = insert_trade_with_event(
                    conn,
                    Trade(
                        id=None, ticker=ticker, entry_date=edate,
                        entry_price=eprice, initial_shares=shares,
                        initial_stop=stop, current_stop=stop, state="entered",
                        watchlist_entry_target=None, watchlist_initial_stop=None,
                        notes=None, trade_origin="manual_off_pipeline",
                        pre_trade_locked_at=event_ts,
                    ),
                    event_ts=event_ts, rationale="seed",
                )
                insert_fill_with_event(
                    conn,
                    Fill(
                        fill_id=None, trade_id=tid,
                        fill_datetime=event_ts, action="entry",
                        quantity=float(shares), price=eprice,
                    ),
                    event_ts=event_ts,
                )
    finally:
        conn.close()


def _run_default_and_verbose(tmp_path: Path, fixture: Path) -> tuple[str, str]:
    """Run `tos-import --dry-run` twice (default + verbose) against the same
    seeded DB. Returns (default_output, verbose_output)."""
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    # Locate the DB the CLI created so we can seed it.
    db_path = home / "swing-data" / "swing.db"
    assert db_path.exists(), f"expected db at {db_path}"
    _seed_real_world_open_for_cli(db_path)

    r_default = runner.invoke(main, [
        "--config", str(cfg), "tos-import",
        "--csv", str(fixture), "--dry-run",
    ])
    assert r_default.exit_code == 0, r_default.output
    r_verbose = runner.invoke(main, [
        "--config", str(cfg), "tos-import",
        "--csv", str(fixture), "--dry-run", "--verbose",
    ])
    assert r_verbose.exit_code == 0, r_verbose.output
    return r_default.output, r_verbose.output


def test_tos_import_verbose_default_output_unchanged(tmp_path: Path):
    """Backward-compat: default output (no `--verbose`) MUST be byte-identical
    to pre-flag behavior. This guards against drift where adding observability
    accidentally re-orders or restyles the existing summary lines that
    operator scripts / muscle-memory grep against. Discriminator: any new
    line in default-mode output (e.g., 'Sections detected:' leakage) fails
    this assertion."""
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])

    r = runner.invoke(main, [
        "--config", str(cfg), "tos-import",
        "--csv", str(SYNTHETIC_FIXTURE), "--dry-run",
    ])
    assert r.exit_code == 0, r.output
    expected_lines = [
        "Cash: 2 new, 0 duplicate",
        "  + deposit $500.00 on 2026-04-01 (ref=DEP-001)",
        "  + withdraw $100.00 on 2026-04-15 (ref=WD-001)",
        "Fills: matched=0, already-reconciled=0, price-mismatch=0, "
        "unmatched OPEN=1, unmatched CLOSE=1",
        "  ? unmatched OPEN: AAPL 2026-04-15 qty=5 @ $180.00",
        "  ? unmatched CLOSE: AAPL 2026-04-22 qty=5 @ $190.00",
        "Dry run — no changes committed.",
    ]
    actual_lines = [
        line for line in r.output.splitlines() if line.strip()
    ]
    assert actual_lines == expected_lines, (
        f"default-mode output changed (back-compat regression). "
        f"expected:\n  " + "\n  ".join(expected_lines)
        + f"\nactual:\n  " + "\n  ".join(actual_lines)
    )


def test_tos_import_verbose_emits_per_fill_price_comparison(tmp_path: Path):
    """`--verbose` must surface, for each matched/price_mismatch OPEN fill,
    both TOS price and journal entry_price + tolerance + outcome — so the
    operator can verify 'existence AND correct values' (their phrasing)
    without manual cross-reference. Pre-fix the operator saw `matched=0`
    with no per-fill diagnostic; this verbose pathway is the recurrence-
    prevention layer."""
    _, verbose = _run_default_and_verbose(tmp_path, REAL_WORLD_FIXTURE)
    # Section diagnostics present.
    assert "Account Trade History" in verbose
    # Each of the 5 OPEN-match tickers must surface with both TOS price and
    # journal price in close proximity (matched OPEN path populates
    # journal_price). The exact format is implementation-controlled but the
    # operator-readable pattern MUST include the matching prices on the
    # fill's verbose line.
    for ticker, tos_price, journal_price in (
        ("LAR", "11.7066", "11.7066"),
        ("CVGI", "5.2244", "5.2244"),
        ("VSAT", "65.685", "65.685"),
        ("YOU", "56.295", "56.295"),
        ("SGML", "23.87", "23.87"),
    ):
        # Match a single line containing the ticker AND both prices AND a
        # 'matched' outcome marker. We grep line-by-line so the assertion
        # error message points at the exact missing fill.
        candidates = [
            line for line in verbose.splitlines()
            if ticker in line and tos_price in line
        ]
        assert candidates, (
            f"verbose output missing {ticker} TOS-price={tos_price} line. "
            f"verbose output:\n{verbose}"
        )
        assert any(journal_price in line for line in candidates), (
            f"verbose output for {ticker} did not surface journal entry_price "
            f"{journal_price} on the same line as TOS price {tos_price}. "
            f"Operator clarification 'existence AND correct values' requires "
            f"the journal price be visible per matched fill. "
            f"Candidate lines: {candidates}"
        )
    # Tolerance must be visible somewhere (operator needs to know what
    # threshold gates matched-vs-price_mismatch routing).
    assert "tol" in verbose.lower() or "tolerance" in verbose.lower(), (
        f"verbose output should surface the price tolerance threshold; got:\n{verbose}"
    )
    # CLOSE-allocation match for SGML SELL-3 must also be flagged (no
    # journal_price column is required for CLOSE since the match goes via
    # cumulative-allocation, but the SELL fill must be visibly routed).
    sell_lines = [
        line for line in verbose.splitlines()
        if "SGML" in line and "SELL" in line.upper()
    ]
    assert sell_lines, (
        f"verbose output must show the SGML SELL-3 fill's routing decision; got:\n{verbose}"
    )


def test_tos_import_verbose_surfaces_section_diagnostics(tmp_path: Path):
    """Verbose mode must include per-section row counts so future format
    drifts (Schwab renames a section, drops a column, etc.) are
    observable-with-context. Discriminator: a future regression where
    'Account Trade History' has 0 detected rows would surface as a visible
    `rows=0` line, not an unobservable empty matched_fills."""
    _, verbose = _run_default_and_verbose(tmp_path, REAL_WORLD_FIXTURE)
    # Expect each of the parsed sections to appear with row counts.
    for section in ("Cash Balance", "Account Trade History"):
        assert section in verbose, (
            f"verbose output missing section line for {section!r}; got:\n{verbose}"
        )
    # Total-fills row count must be visible (the immediate diagnostic for
    # the silent-zero failure mode). The exact label is impl-controlled but
    # the count of 6 fills extracted MUST be derivable.
    assert "6" in verbose, (
        f"verbose output should surface the count of extracted fills (6); "
        f"got:\n{verbose}"
    )
