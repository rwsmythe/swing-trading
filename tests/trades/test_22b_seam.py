"""Arc 22-B Task 2 -- the single-writer seam (F5 x 8 surfaces, E10, E11).

`unintended_execution` is evidence-bearing: it is written ONLY by
`swing trade assign-intent`. Every GENERIC writer of `trades.entry_intent`
validates against `ENTRY_INTENTS_ASSERTABLE` and refuses the value with the
typed `SEAM_MESSAGE` -- landed BEFORE `ENTRY_INTENTS` widens (Task 3), so no
commit ever has the value accepted by a generic writer.

The eight surfaces (census C.4): (1) `trade entry --entry-intent`,
(2) `trade review --entry-intent`, (3) `trade backfill-intent`'s prompt,
(4) the web entry form, (5) the web review form, (6) `EntryRequest`,
(7) `update_entry_intent`, (8) the audited corrector's reservation.
"""
from __future__ import annotations

import ast
import html
import tomllib
from dataclasses import replace as dc_replace
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from swing.cli import main
from swing.config import load
from swing.data.db import connect, ensure_schema
from swing.data.models import (
    ENTRY_INTENTS_ASSERTABLE,
    SEAM_MESSAGE,
    UNINTENDED_EXECUTION,
    EntryIntentSeamError,
    Fill,
    Trade,
)
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event, update_entry_intent
from swing.trades.entry import EntryRequest
from swing.trades.reconciliation_auto_correct import (
    ReservedJournalFieldError,
    _update_journal_field,
)
from tests.cli.test_cli_eval import _minimal_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SURFACES = (
    "cli_entry", "cli_review", "cli_backfill", "web_entry", "web_review",
    "entry_request", "update_entry_intent", "corrector",
)


def _seed_closed_trade(db_path: Path, *, entry_intent: str | None = None) -> int:
    conn = ensure_schema(db_path)
    try:
        with conn:
            tid = insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="VIR", entry_date="2026-04-20",
                    entry_price=10.0, initial_shares=10, initial_stop=9.0,
                    current_stop=9.0, state="entered",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None, trade_origin="manual_off_pipeline",
                    pre_trade_locked_at="2026-04-20T09:30:00",
                    entry_intent=entry_intent,
                ),
                event_ts="2026-04-20T09:30:00",
            )
            insert_fill_with_event(
                conn,
                Fill(fill_id=None, trade_id=tid,
                     fill_datetime="2026-04-20T09:30:00", action="entry",
                     quantity=10.0, price=10.0),
                event_ts="2026-04-20T09:30:00", rationale="seed-entry",
            )
            insert_fill_with_event(
                conn,
                Fill(fill_id=None, trade_id=tid,
                     fill_datetime="2026-04-25T09:30:00", action="exit",
                     quantity=10.0, price=11.5, reason="manual"),
                event_ts="2026-04-25T09:30:00", rationale="seed-exit",
            )
            conn.execute("UPDATE trades SET state='closed' WHERE id=?", (tid,))
    finally:
        conn.close()
    return tid


def _cli(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    db_path = Path(tomllib.loads(cfg.read_text())["paths"]["db_path"])
    return runner, cfg, db_path


def _web_app(tmp_path: Path):
    from swing.web.app import create_app

    db_path = tmp_path / "seam.db"
    tid = _seed_closed_trade(db_path)
    base = load(REPO_ROOT / "swing.config.toml")
    cfg = dc_replace(base, paths=dc_replace(base.paths, db_path=db_path))
    return create_app(cfg), db_path, tid


def _intent(db_path: Path, tid: int) -> str | None:
    c = connect(db_path)
    try:
        return c.execute(
            "SELECT entry_intent FROM trades WHERE id=?", (tid,)).fetchone()[0]
    finally:
        c.close()


def _review_args(cfg: Path, tid: int, value: str) -> list[str]:
    return ["--config", str(cfg), "trade", "review", "--trade-id", str(tid),
            "--entry-grade", "A", "--management-grade", "A",
            "--exit-grade", "A", "--mistake-tags", "none_observed",
            "--lesson-learned", "clean", "--entry-intent", value]


def _entry_request(value: str | None) -> EntryRequest:
    return EntryRequest(
        ticker="ZZZ", entry_date="2026-04-15", entry_price=100.0, shares=1,
        initial_stop=90.0, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None, rationale="vcp-breakout",
        event_ts="2026-04-15T10:00:00", entry_intent=value,
    )


def _drive(surface: str, value: str | None, tmp_path: Path, monkeypatch):
    """Drive ONE surface with ``value``; return (refused, message, written)."""
    if surface == "cli_entry":
        runner, cfg, _ = _cli(tmp_path)
        res = runner.invoke(main, ["--config", str(cfg), "trade", "entry",
                                   "--entry-intent", value])
        return res.exit_code != 0 and "--entry-intent" in res.output, res.output, None
    if surface == "cli_review":
        runner, cfg, db = _cli(tmp_path)
        tid = _seed_closed_trade(db)
        res = runner.invoke(main, _review_args(cfg, tid, value))
        return res.exit_code != 0, res.output, _intent(db, tid)
    if surface == "cli_backfill":
        runner, cfg, db = _cli(tmp_path)
        tid = _seed_closed_trade(db)
        res = runner.invoke(
            main, ["--config", str(cfg), "trade", "backfill-intent"],
            input=f"{value}\n")
        written = _intent(db, tid)
        return written != value, res.output, written
    if surface in ("web_entry", "web_review"):
        app, db, tid = _web_app(tmp_path)
        from swing.web.price_cache import PriceCache, PriceSnapshot
        monkeypatch.setattr(
            PriceCache, "get_many",
            lambda self, tickers, deadline_seconds, *, executor=None: {
                "ZZZ": PriceSnapshot(ticker="ZZZ", price=100.0,
                                     asof=datetime.now(), is_stale=False,
                                     source="live")})
        with TestClient(app) as client:
            if surface == "web_entry":
                from tests.web.conftest import full_phase7_entry_payload
                r = client.post("/trades/entry", data=full_phase7_entry_payload(
                    ticker="ZZZ", entry_date="2026-04-15",
                    entry_price="100.0", shares="1", initial_stop="90.0",
                    rationale="vcp-breakout", sector="", industry="",
                    origin="watchlist", entry_intent=value,
                ), headers={"HX-Request": "true"})
                c = connect(db)
                try:
                    row = c.execute(
                        "SELECT entry_intent FROM trades WHERE ticker='ZZZ'"
                    ).fetchone()
                finally:
                    c.close()
                return (400 <= r.status_code < 500 and row is None), r.text, row
            r = client.post(
                f"/trades/{tid}/review",
                data={"entry_grade": "A", "management_grade": "A",
                      "exit_grade": "A", "lesson_learned": "clean",
                      "mistake_tags": ["none_observed"], "entry_intent": value},
                headers={"HX-Request": "true"}, follow_redirects=False)
            return 400 <= r.status_code < 500, r.text, _intent(db, tid)
    if surface == "entry_request":
        try:
            _entry_request(value)
        except ValueError as exc:
            return True, str(exc), None
        return False, "", None
    conn = ensure_schema(tmp_path / "direct.db")
    try:
        tid = _seed_closed_trade(tmp_path / "direct.db")
        try:
            if surface == "update_entry_intent":
                with conn:
                    update_entry_intent(conn, trade_id=tid, entry_intent=value)
            else:
                _update_journal_field(conn, "trades", tid, "entry_intent", value)
        except (ValueError, ReservedJournalFieldError) as exc:
            return True, str(exc), _intent(tmp_path / "direct.db", tid)
        return False, "", _intent(tmp_path / "direct.db", tid)
    finally:
        conn.close()


@pytest.mark.parametrize("surface", SURFACES)
def test_each_generic_surface_refuses_with_the_seam_message_b22_10(
    surface, tmp_path, monkeypatch,
) -> None:
    refused, message, written = _drive(
        surface, UNINTENDED_EXECUTION, tmp_path, monkeypatch)
    assert refused, (surface, message[-600:])
    assert written != UNINTENDED_EXECUTION
    flat = " ".join(html.unescape(message).split())
    if surface == "corrector":
        assert "swing trade assign-intent" in flat, flat
    else:
        assert SEAM_MESSAGE in flat, flat[-800:]


def test_the_typed_error_is_a_value_error_b22_10() -> None:
    with pytest.raises(EntryIntentSeamError):
        _entry_request(UNINTENDED_EXECUTION)
    assert issubclass(EntryIntentSeamError, ValueError)


_SEAM_FILES = {
    "swing/cli.py": ("cli_entry", "cli_review", "cli_backfill"),
    "swing/web/routes/trades.py": ("web_entry", "web_review"),
    "swing/trades/entry.py": ("entry_request",),
    "swing/data/repos/trades.py": ("update_entry_intent",),
}
# Every place in swing/ that may reference the SCHEMA enum ENTRY_INTENTS
# (Name/Attribute references, read by AST). A new membership check against the
# schema enum anywhere else would ACCEPT the evidence-bearing value.
_ENTRY_INTENTS_ALLOWED = {
    "swing/data/models.py",  # the definition + Trade.__post_init__ (widened)
    "swing/trades/entry_intent_assignment.py",  # the one writer (Task 5)
}


def _names(tree: ast.AST) -> set[str]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.alias):
            out.add(node.asname or node.name)
    return out


def test_seam_surfaces_import_the_assertable_constant_b22_11() -> None:
    for rel in _SEAM_FILES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        names = _names(ast.parse(text))
        assert names & {"ENTRY_INTENTS_ASSERTABLE", "EntryIntentSeamError",
                        "EntryIntentParam", "SEAM_MESSAGE"}, rel
        # No hand-typed two-token list of the intent values (a stale mirror).
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                vals = {e.value for e in node.elts
                        if isinstance(e, ast.Constant)}
                assert not {"standard", "hypothesis_test_by_design"} <= vals, (
                    rel, ast.get_source_segment(text, node))
    offenders = []
    for path in sorted((REPO_ROOT / "swing").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in _ENTRY_INTENTS_ALLOWED:
            continue
        if "ENTRY_INTENTS" in _names(ast.parse(path.read_text(encoding="utf-8"))):
            offenders.append(rel)
    assert not offenders, offenders


@pytest.mark.parametrize("surface", SURFACES[:7])
@pytest.mark.parametrize("value", sorted(ENTRY_INTENTS_ASSERTABLE))
def test_today_values_still_accepted_on_surfaces_1_to_7_b22_12(
    surface, value, tmp_path, monkeypatch,
) -> None:
    refused, message, written = _drive(surface, value, tmp_path, monkeypatch)
    if surface == "cli_entry":
        # Parse succeeds for a member; the command then fails on its OTHER
        # missing required options, never on --entry-intent.
        assert "--entry-intent" not in message, message
        return
    assert not refused, (surface, message[-600:])
    if surface in ("cli_review", "cli_backfill", "web_review",
                   "update_entry_intent"):
        assert written == value


@pytest.mark.parametrize(
    "value", [None, "standard", "hypothesis_test_by_design", UNINTENDED_EXECUTION])
def test_the_corrector_reserves_entry_intent_for_every_value_b22_13(
    value, tmp_path,
) -> None:
    db = tmp_path / "c.db"
    tid = _seed_closed_trade(db)
    conn = connect(db)
    try:
        with pytest.raises(ReservedJournalFieldError) as exc:
            _update_journal_field(conn, "trades", tid, "entry_intent", value)
    finally:
        conn.close()
    msg = str(exc.value)
    assert "swing trade assign-intent" in msg
    assert "swing trade review --entry-intent" in msg
    assert _intent(db, tid) is None

