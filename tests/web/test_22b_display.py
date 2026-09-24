"""Arc 22-B Task 9 -- ``unintended_execution`` renders with its OWN class and
label on the display surfaces (brief 4.7; plan Task 9).

Fixture note (a consequence of the CHARC-S3 twins): a v40 DB refuses a raw
``unintended_execution`` write, so the value here is ATTESTED through the
real ``assign(...)`` on a deployment-leg shape (no entry-fill envelope, an
``entry_date`` before 2026-08-03, no link/intent/telemetry for its ticker,
the outcome fill the NEXT day) -- the idiom of
``tests/metrics/test_22b_cohort_exclusion.py``. No trigger is dropped.
"""
from __future__ import annotations

import re
import sqlite3

from click.testing import CliRunner
from fastapi.testclient import TestClient

from swing.data.db import open_connection
from swing.web.app import create_app

UNINTENDED = "unintended_execution"


def _seed_reviewed(conn: sqlite3.Connection, *, trade_id: int, ticker: str,
                   entry_intent: str | None, entry_date: str) -> None:
    """A reviewed trade (process grade B) with its entry + next-day exit fill;
    ``notes``/``why_now`` carry the text an attestation cites."""
    exit_date = entry_date[:8] + f"{int(entry_date[8:]) + 1:02d}"
    conn.execute(
        "INSERT INTO trades (id, ticker, entry_date, entry_price, "
        "initial_shares, initial_stop, current_stop, state, sector, "
        "industry, trade_origin, pre_trade_locked_at, current_size, "
        "process_grade, entry_grade, management_grade, exit_grade, "
        "disqualifying_process_violation, realized_R_if_plan_followed, "
        "reviewed_at, last_fill_at, entry_intent, risk_policy_id_at_lock, "
        "notes, why_now) VALUES (?, ?, ?, 10.0, 100, 9.0, 9.0, 'reviewed', "
        "'S', 'I', 'manual_off_pipeline', ?, 0, 'B', 'B', 'B', 'B', 0, 1.0, "
        "?, ?, ?, 1, ?, ?)",
        (trade_id, ticker, entry_date, entry_date + "T09:30:00",
         exit_date + "T16:00:00", exit_date + "T15:30:00", entry_intent,
         f"the note of {ticker}", f"why {ticker} now"))
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, 'entry', 100, 10.0, "
        "'unreconciled')", (trade_id, entry_date + "T09:30:00"))
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, 'exit', 100, 11.0, "
        "'unreconciled')", (trade_id, exit_date + "T15:30:00"))


def _attest(cfg, trade_id: int) -> None:
    """The value written by its ONE writer, with its evidence row."""
    from swing.trades.entry_intent_assignment import assign

    c = open_connection(cfg.paths.db_path)
    try:
        r = assign(c, None, trade_id=trade_id, cite=["notes", "why_now"],
                   reason="an execution nobody decided to make",
                   applied_by="operator")
    finally:
        c.close()
    assert r.admitted, r.message


def _seed_four_intents(cfg) -> None:
    """One reviewed trade per stored intent state; trade 4 is attested."""
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        for trade_id, ticker, intent, day in (
            (1, "STD", "standard", "2026-07-06"),
            (2, "BYD", "hypothesis_test_by_design", "2026-07-08"),
            (3, "UNC", None, "2026-07-13"),
            (4, "UXE", None, "2026-07-20"),
        ):
            _seed_reviewed(conn, trade_id=trade_id, ticker=ticker,
                           entry_intent=intent, entry_date=day)
        conn.commit()
    finally:
        conn.close()
    _attest(cfg, 4)
    conn = sqlite3.connect(cfg.paths.db_path)
    try:
        stored = conn.execute(
            "SELECT entry_intent FROM trades WHERE id = 4").fetchone()[0]
    finally:
        conn.close()
    assert stored == UNINTENDED


def _marker(html: str, trade_id: int) -> str:
    """The opening tag of trade ``trade_id``'s grades-panel marker circle."""
    m = re.search(
        rf'<circle[^>]*data-trade-id="{trade_id}"[^>]*>', html, re.S)
    assert m is not None, f"marker for trade {trade_id} missing"
    return m.group(0)


def test_trend_renders_own_class_not_standard_or_unclassified_b22_140(
    seeded_db,
) -> None:
    cfg, cfg_path = seeded_db
    _seed_four_intents(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/metrics/process-grade-trend")
    assert r.status_code == 200
    marker = _marker(r.text, 4)
    assert 'data-entry-intent="unintended"' in marker
    assert "process-grade-marker intent-unintended" in marker
    for other in ("standard", "by-design", "unclassified"):
        assert f'data-entry-intent="{other}"' not in marker
    # The template prefixes ``intent-``: the map holds the BARE token (R3-03).
    assert "intent-intent-" not in r.text
    # The raw enum token never leaks as a class / attribute value.
    assert f'"{UNINTENDED}"' not in marker
    # The other three keep their own tokens.
    assert 'data-entry-intent="standard"' in _marker(r.text, 1)
    assert 'data-entry-intent="by-design"' in _marker(r.text, 2)
    assert 'data-entry-intent="unclassified"' in _marker(r.text, 3)
    legend = re.search(
        r'data-marker="grades-intent-legend">([^<]*)<', r.text).group(1)
    assert legend == "intent: standard / by-design / unclassified / unintended"
    assert legend.isascii()


def test_process_card_filter_offers_the_value_b22_141(seeded_db) -> None:
    from swing.trades.intent import entry_intent_label
    from swing.web.view_models.metrics.trade_process_card import INTENT_FACETS

    assert (UNINTENDED, entry_intent_label(UNINTENDED)) in INTENT_FACETS
    assert entry_intent_label(UNINTENDED) == "Unintended execution"
    cfg, cfg_path = seeded_db
    _seed_four_intents(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/metrics/trade-process?cohort=__all__&intent={UNINTENDED}")
    assert r.status_code == 200
    nav = re.search(
        r'<nav class="intent-facet-selector".*?</nav>', r.text, re.S).group(0)
    links = re.findall(r'<a href="([^"]*)"\s+class="([^"]*)"[^>]*>([^<]*)</a>',
                       nav)
    by_label = {label: (href, cls) for href, cls, label in links}
    assert "Unintended execution" in by_label
    href, cls = by_label["Unintended execution"]
    assert href == f"?cohort=__all__&amp;intent={UNINTENDED}"
    # The route accepts the value (not normalized to the All facet).
    assert "active" in cls.split()
    assert "active" not in by_label["All"][1].split()


def test_cli_analyze_label_b22_142(seeded_db) -> None:
    from swing.cli import main

    cfg, cfg_path = seeded_db
    _seed_four_intents(cfg)
    result = CliRunner().invoke(
        main, ["--config", str(cfg_path), "trade", "analyze", "4"])
    assert result.exit_code == 0, result.output
    intent_lines = [ln for ln in result.output.splitlines()
                    if ln.startswith("Intent:")]
    assert intent_lines == ["Intent: Unintended execution"]
