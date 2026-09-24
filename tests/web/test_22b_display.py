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
    _assert_intent_legend_on_its_own_line(r.text)


def _assert_intent_legend_on_its_own_line(html: str) -> None:
    """RULING G3a (ii), CHARC 2026-09-24: the intent legend takes its OWN
    line -- it shares a baseline with neither the series-swatch row nor any
    grade-axis label -- and it sits inside the grades panel (no clipping).
    Pre-fix the legend sat at the swatch row's baseline (y=15), where its
    Segoe UI 16px text ends x~385 against the first swatch at x=360."""
    from swing.web.view_models.metrics.process_grade_trend import (
        GRADES_SVG_HEIGHT,
    )

    svg = re.search(r'<svg[^>]*data-panel="grades"[^>]*>(.*?)</svg>',
                    html, re.S).group(1)
    legend_y = float(re.search(
        r'<text[^>]*\by="([^"]+)"[^>]*data-marker="grades-intent-legend"',
        svg, re.S).group(1))
    group = re.search(r'<g[^>]*data-marker="grades-legend"[^>]*>(.*?)</g>',
                      svg, re.S).group(1)
    # The series-swatch row: each swatch <rect> band and its <text> label.
    swatch_bands = [
        (float(y), float(y) + float(h)) for y, h in re.findall(
            r'<rect[^>]*class="process-grade-legend-swatch[^"]*"[^>]*'
            r'\by="([^"]+)"[^>]*\bheight="([^"]+)"', group, re.S)]
    swatch_text_ys = [
        float(y) for y in re.findall(
            r'<text[^>]*\by="([^"]+)"[^>]*>(?:process|entry|management|exit)<',
            group, re.S)]
    assert len(swatch_bands) == 4 and len(swatch_text_ys) == 4
    assert legend_y not in swatch_text_ys
    for top, bottom in swatch_bands:
        assert not (top <= legend_y <= bottom + 10), (legend_y, top, bottom)
    axis = re.search(
        r'<g[^>]*data-marker="grade-axis-encoding"[^>]*>(.*?)</g>',
        svg, re.S).group(1)
    axis_ys = [float(y) for y in re.findall(r'\by="([^"]+)"', axis)]
    assert len(axis_ys) == 5
    for y in axis_ys:
        assert abs(legend_y - y) >= 16, (legend_y, y)
    # Inside the panel: a 16px line's descent (5px, Segoe UI) fits below it.
    assert 16 <= legend_y <= GRADES_SVG_HEIGHT - 5, legend_y


def test_process_card_filter_offers_the_value_b22_141(seeded_db) -> None:
    from swing.trades.intent import entry_intent_label
    from swing.web.view_models.metrics.trade_process_card import INTENT_FACETS

    assert (UNINTENDED, entry_intent_label(UNINTENDED)) in INTENT_FACETS
    assert entry_intent_label(UNINTENDED) == "Unintended execution"
    # RULING G3a (iii), CHARC 2026-09-24: ONE label source. Every facet whose
    # value is a stored entry_intent value is labelled by entry_intent_label;
    # a re-hard-coded label goes RED here. The two sentinels ("" = All,
    # "__unclassified__" = IS NULL) are not values: entry_intent_label has no
    # label for them (None -> None; an unknown token -> itself).
    from swing.data.models import ENTRY_INTENTS

    value_facets = [(v, lbl) for v, lbl in INTENT_FACETS if v in ENTRY_INTENTS]
    assert {v for v, _ in value_facets} == set(ENTRY_INTENTS)
    for value, label in value_facets:
        assert label == entry_intent_label(value), (value, label)
    assert dict(INTENT_FACETS)["standard"] == "Standard entry"
    sentinels = [v for v, _ in INTENT_FACETS if v not in ENTRY_INTENTS]
    assert sentinels == ["", "__unclassified__"]
    # The equality above cannot see a hard-coded label that happens to match
    # today's text; the SOURCE must call the label home for every value facet.
    _assert_value_facets_call_the_label_home(ENTRY_INTENTS)
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
    # G3a (iii) as the witness sees it: the card renders the label home's text.
    assert "Standard entry" in by_label and "Standard" not in by_label
    href, cls = by_label["Unintended execution"]
    assert href == f"?cohort=__all__&amp;intent={UNINTENDED}"
    # The route accepts the value (not normalized to the All facet).
    assert "active" in cls.split()
    assert "active" not in by_label["All"][1].split()


def _assert_value_facets_call_the_label_home(entry_intents) -> None:
    """Static read of ``INTENT_FACETS``: every (value, label) entry whose value
    is a stored entry_intent value has a label expression that CALLS
    ``entry_intent_label`` (bare or under ``or``) -- no string literal."""
    import ast
    import pathlib

    import swing.web.view_models.metrics.trade_process_card as mod

    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    names = {"UNINTENDED_EXECUTION": UNINTENDED}
    [node] = [n for n in ast.walk(tree) if isinstance(n, ast.AnnAssign)
              and getattr(n.target, "id", None) == "INTENT_FACETS"]
    seen = set()
    for elt in node.value.elts:
        key, label = elt.elts
        value = (key.value if isinstance(key, ast.Constant)
                 else names[key.id])
        if value not in entry_intents:
            continue
        calls = [c for c in ast.walk(label) if isinstance(c, ast.Call)
                 and getattr(c.func, "id", None) == "entry_intent_label"]
        assert calls, f"facet {value!r} label is not from entry_intent_label"
        assert not isinstance(label, ast.Constant), value
        seen.add(value)
    assert seen == set(entry_intents)


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


def _null_label_literal_sites() -> tuple[list[str], int, int]:
    """Static walk for the NULL entry_intent label's text under ``swing/``.

    ``*.py``: every AST ``str`` constant (f-string pieces included) EXCEPT
    docstrings (the first statement of a module/class/function body) -- so
    comments are excluded by construction (the tokenizer drops them) and
    docstrings by position. ``*.j2``: the template text after removing
    ``{# ... #}`` Jinja comments (HTML comments stay: they reach the page).
    Returns (violations as ``path:line``, py files read, j2 files read).
    """
    import ast
    import pathlib

    import swing

    root = pathlib.Path(swing.__file__).parent
    needle = "Unclassified"
    hits: list[str] = []
    n_py = n_j2 = 0
    for path in sorted(root.rglob("*.py")):
        n_py += 1
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)) and node.body:
                first = node.body[0]
                if (isinstance(first, ast.Expr)
                        and isinstance(first.value, ast.Constant)
                        and isinstance(first.value.value, str)):
                    docstrings.add(id(first.value))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and needle in node.value and id(node) not in docstrings):
                hits.append(f"{path.relative_to(root.parent).as_posix()}"
                            f":{node.lineno}")
    for path in sorted(root.rglob("*.j2")):
        n_j2 += 1
        text = path.read_text(encoding="utf-8")
        stripped = re.sub(r"\{#.*?#\}",
                          lambda m: "\n" * m.group(0).count("\n"), text,
                          flags=re.S)
        for lineno, line in enumerate(stripped.splitlines(), start=1):
            if needle in line:
                hits.append(f"{path.relative_to(root.parent).as_posix()}"
                            f":{lineno}")
    return hits, n_py, n_j2


def test_null_entry_intent_label_has_one_home_b22_217() -> None:
    """RULING G3c (CHARC 2026-09-24): the NULL sentinel's text lives in ONE
    place, ``NULL_ENTRY_INTENT_LABEL`` in the label home; the two rendered
    sites (``trade analyze``, the card's Unclassified facet) import it."""
    hits, n_py, n_j2 = _null_label_literal_sites()
    assert n_py > 100 and n_j2 > 10, (n_py, n_j2)
    # Non-vacuity: the walk SEES the one home (the detector works on the
    # real tree) ...
    assert "swing/trades/intent.py" in {h.rsplit(":", 1)[0] for h in hits}
    # ... and nothing else carries the literal.
    others = [h for h in hits if not h.startswith("swing/trades/intent.py:")]
    assert others == [], f"'Unclassified' literal outside the label home: {others}"

    from swing.trades.intent import NULL_ENTRY_INTENT_LABEL, entry_intent_label

    assert NULL_ENTRY_INTENT_LABEL == "Unclassified"
    # The None contract is unchanged: callers rely on the falsy return.
    assert entry_intent_label(None) is None

    from swing.web.view_models.metrics.trade_process_card import INTENT_FACETS

    assert dict(INTENT_FACETS)["__unclassified__"] == NULL_ENTRY_INTENT_LABEL
    assert dict(INTENT_FACETS)[""] == "All"

    from swing.cli import _render_trade_analysis
    from swing.journal.analyze import TradeAnalysis

    a = TradeAnalysis(
        trade_id=2, ticker="TST", entry_date="2026-04-20",
        entry_price=100.0, initial_shares=5, initial_stop=90.0,
        current_stop=90.0, state="entered", status="open",
        hypothesis_label=None, notes=None,
        recommendations=(), exits=(),
        days_rec_to_entry=None, pct_above_pivot=None, stop_dev_pct=None,
        realized_pnl_total=0.0, r_multiple_avg=None,
        entry_intent=None,
    )
    intent_lines = [ln for ln in _render_trade_analysis(a)
                    if ln.startswith("Intent:")]
    assert intent_lines == [f"Intent: {NULL_ENTRY_INTENT_LABEL}"]
