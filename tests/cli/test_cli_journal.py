"""CLI: swing journal review / cash."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    home = tmp_path / "home"; home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return runner, cfg


def test_journal_review_empty(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, ["--config", str(cfg), "journal", "review"])
    assert r.exit_code == 0
    assert "0 trades" in r.output or "no trades" in r.output.lower()
    # No closed trades → no breakdown section emitted at all (no header noise).
    assert "Hypothesis breakdown" not in r.output


def _record_closed_trade(
    cfg_path: Path, *, ticker: str, hypothesis: str | None,
    exit_price: float, entry_date: str = "2026-04-15",
    exit_date: str = "2026-04-20",
) -> None:
    """Record an entry then a full exit, optionally tagging a hypothesis label.

    Uses the CLI surfaces (not the repo) so the test exercises the same path
    operators do. Entry shares = 1, entry price = 100, stop = 90 — keeps the
    arithmetic obvious.
    """
    runner = CliRunner()
    args = [
        "--config", str(cfg_path), "trade", "entry",
        "--ticker", ticker, "--entry-date", entry_date,
        "--entry-price", "100.0", "--shares", "1",
        "--initial-stop", "90.0", "--rationale", "vcp-breakout",
    ]
    if hypothesis is not None:
        args += ["--hypothesis", hypothesis]
    r = runner.invoke(main, args)
    assert r.exit_code == 0, r.output

    # Look up the trade id from the CLI listing — keeps the test free of repo
    # imports.
    listing = runner.invoke(main, ["--config", str(cfg_path), "trade", "list"])
    assert listing.exit_code == 0, listing.output
    tid = next(
        ln.split()[0] for ln in listing.output.splitlines()
        if ticker in ln and ln.split() and ln.split()[0].isdigit()
    )

    r = runner.invoke(main, [
        "--config", str(cfg_path), "trade", "exit",
        "--trade-id", tid, "--exit-date", exit_date,
        "--exit-price", str(exit_price), "--shares", "1",
        "--reason", "target" if exit_price > 100.0 else "stop-hit",
    ])
    assert r.exit_code == 0, r.output


def test_journal_review_unlabeled_only_renders_no_label_bucket(tmp_path: Path):
    """Brief §4.5: trades without --hypothesis fall under "(no label)"."""
    runner, cfg = _setup(tmp_path)
    _record_closed_trade(cfg, ticker="AAA", hypothesis=None, exit_price=110.0)
    _record_closed_trade(cfg, ticker="BBB", hypothesis=None, exit_price=95.0)
    r = runner.invoke(main, ["--config", str(cfg), "journal", "review"])
    assert r.exit_code == 0, r.output
    assert "Hypothesis breakdown" in r.output
    assert "(no label)" in r.output
    # Total P&L for the (no label) group: $10 - $5 = $5 (1 share * delta).
    assert "$5.00" in r.output
    # N=2 → win_rate suppressed in the breakdown bucket. Scope the assertion
    # to the breakdown section because the existing review output above also
    # mentions "Win rate" for the overall journal stats.
    section = r.output[r.output.index("Hypothesis breakdown"):]
    no_label_line = next(
        ln for ln in section.splitlines() if "(no label)" in ln
    )
    assert "%" not in no_label_line
    assert "win rate" not in no_label_line.lower()


def test_journal_review_groups_by_label_with_win_rate_at_three(tmp_path: Path):
    """Win rate appears for groups with >=3 trades; not for smaller groups.
    Existing review header (period, win rate, expectancy) preserved."""
    runner, cfg = _setup(tmp_path)
    # Three "alpha" trades: 2 wins, 1 loss → win rate 2/3 = 66.7%
    _record_closed_trade(cfg, ticker="A1", hypothesis="alpha", exit_price=110.0)
    _record_closed_trade(cfg, ticker="A2", hypothesis="alpha", exit_price=110.0)
    _record_closed_trade(cfg, ticker="A3", hypothesis="alpha", exit_price=95.0)
    # One "beta" trade: 1 win → win rate suppressed (N<3).
    _record_closed_trade(cfg, ticker="B1", hypothesis="beta", exit_price=110.0)

    r = runner.invoke(main, ["--config", str(cfg), "journal", "review"])
    assert r.exit_code == 0, r.output

    # Existing review output preserved (additive, not replacing).
    assert "Journal Review" in r.output
    assert "trades" in r.output

    out = r.output
    assert "Hypothesis breakdown" in out
    # alpha row reports 3 trades + win rate.
    alpha_line = next(ln for ln in out.splitlines() if '"alpha"' in ln)
    assert "3 trades" in alpha_line
    assert "66.7%" in alpha_line  # 2/3
    # beta row reports 1 trade, no win rate.
    beta_line = next(ln for ln in out.splitlines() if '"beta"' in ln)
    assert "1 trade" in beta_line
    assert "%" not in beta_line


def test_journal_review_label_with_special_chars_does_not_break_formatting(tmp_path: Path):
    """Free-text safety (brief §5): newlines/quotes in labels must not break
    the table layout — each bucket renders as exactly one output line."""
    runner, cfg = _setup(tmp_path)
    nasty = 'has "quotes" and\nnewline'
    _record_closed_trade(cfg, ticker="NAS", hypothesis=nasty, exit_price=110.0)

    r = runner.invoke(main, ["--config", str(cfg), "journal", "review"])
    assert r.exit_code == 0, r.output
    out = r.output
    assert "Hypothesis breakdown" in out
    # Find lines under the breakdown section and assert each starts with "- ".
    section_start = out.index("Hypothesis breakdown")
    section = out[section_start:].splitlines()[1:]
    bullet_lines = [ln for ln in section if ln.strip()]
    # Exactly one bucket recorded → exactly one bullet line below the header.
    assert len(bullet_lines) == 1
    assert bullet_lines[0].lstrip().startswith("- ")
    # Newline and quote characters are sanitized so the row stays single-line.
    assert "\n" not in bullet_lines[0]


def test_journal_cash_deposit(tmp_path: Path):
    runner, cfg = _setup(tmp_path)
    r = runner.invoke(main, [
        "--config", str(cfg), "journal", "cash",
        "--deposit", "200.0", "--date", "2026-04-01",
        "--ref", "DEP-X", "--note", "test deposit",
    ])
    assert r.exit_code == 0, r.output
    assert "DEP-X" in r.output or "deposit" in r.output.lower()
