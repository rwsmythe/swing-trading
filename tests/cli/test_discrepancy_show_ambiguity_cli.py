"""Phase 12 C.D T-D.2 — CLI: ``swing journal discrepancy show-ambiguity``.

Per plan §E.2 acceptance criteria — prints discrepancy detail (shared
fields with ``discrepancy show``) PLUS the per-``ambiguity_kind``
candidate choice menu from
``swing.trades.reconciliation_ambiguity_choices.get_choice_menu``.

Discriminating tests:

1. Discrepancy not found → exit !=0 with click error.
2. ``multi_partial_vs_consolidated`` → 4 codes present + ``[RECOMMENDED]``
   tag on ``keep_journal_as_is`` first + REQUIRES marker on 3 entries.
3. ``multi_match_within_window`` → static + parametric
   ``pick_schwab_record_<N>`` entries (N derived from
   ``resolution_reason`` text).
4. ``unknown_schwab_subtype`` → 3 codes.
5. ``field_shape_incompatible`` → 2 codes.
6. ``schwab_returned_no_match`` → 2 codes.
7. ``validator_rejected`` → 2 codes.
8. ``unsupported`` → 2 codes.
9. NULL ``ambiguity_kind`` (defense-in-depth — schema allows it on
   non-tier-2 rows) → shared fields render + empty menu message.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from swing.cli import main
from tests.cli.test_cli_eval import _minimal_config


@pytest.fixture
def cli_workspace(tmp_path: Path):
    """Create a project + home dir + run db-migrate to land schema v19."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    assert r.exit_code == 0, r.output
    db_path = home / "swing-data" / "swing.db"
    return runner, cfg, db_path


def _seed_reconciliation_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO reconciliation_runs ("
        "  source, started_ts, state, period_start, period_end"
        ") VALUES (?, ?, ?, ?, ?)",
        ("tos_csv", "2026-05-16T10:00:00", "completed",
         "2026-05-10", "2026-05-16"),
    )
    return int(cur.lastrowid)


def _plant_pending_ambiguity(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    ticker: str = "DHC",
    ambiguity_kind: str | None = "multi_partial_vs_consolidated",
    discrepancy_type: str = "entry_price_mismatch",
    field_name: str = "price",
    resolution: str = "pending_ambiguity_resolution",
    resolution_reason: str | None = None,
    created_at: str = "2026-05-16T10:05:00",
) -> int:
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, ticker, field_name, "
        "  material_to_review, resolution, resolution_reason, "
        "  ambiguity_kind, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, discrepancy_type, ticker, field_name,
            1, resolution, resolution_reason, ambiguity_kind, created_at,
        ),
    )
    return int(cur.lastrowid)


# ===========================================================================
# §1 — Discrepancy not found.
# ===========================================================================


def test_show_ambiguity_unknown_id_errors(cli_workspace) -> None:
    runner, cfg, _db = cli_workspace
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", "9999",
    ])
    assert r.exit_code != 0
    assert "9999" in r.output


# ===========================================================================
# §2 — multi_partial_vs_consolidated (RECOMMENDED tag + 4 codes).
# ===========================================================================


def test_show_ambiguity_multi_partial_vs_consolidated(cli_workspace) -> None:
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_pending_ambiguity(
            conn, run_id,
            ticker="DHC",
            ambiguity_kind="multi_partial_vs_consolidated",
            resolution_reason=(
                "Schwab returned 2 separate orders summing to qty=39; "
                "V1 mapper exposes order-level price only"
            ),
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    # Shared fields rendered.
    assert f"discrepancy_id: {did}" in r.output
    assert "ticker:" in r.output and "DHC" in r.output
    assert "ambiguity_kind: multi_partial_vs_consolidated" in r.output
    # Menu header.
    assert "Candidate choices" in r.output
    # All 4 codes appear.
    assert "keep_journal_as_is" in r.output
    assert "consolidate_using_operator_vwap" in r.output
    assert "split_into_partials" in r.output
    assert "custom" in r.output
    # [RECOMMENDED] tag appears next to keep_journal_as_is.
    assert "[RECOMMENDED] keep_journal_as_is" in r.output
    # REQUIRES marker appears for the 3 custom-value-required codes
    # (must appear at least 3 times — once per requires_custom_value=True
    # row; using --custom-value substring to be robust).
    require_count = r.output.count("--custom-value")
    assert require_count >= 3, (
        f"expected --custom-value REQUIRES marker on 3+ rows, "
        f"got {require_count} in output:\n{r.output}"
    )
    # RECOMMENDED ordering: keep_journal_as_is renders BEFORE the other
    # 3 codes (operator scan-first ordering per OQ-4).
    idx_keep = r.output.index("keep_journal_as_is")
    idx_vwap = r.output.index("consolidate_using_operator_vwap")
    idx_split = r.output.index("split_into_partials")
    assert idx_keep < idx_vwap < idx_split


# ===========================================================================
# §3 — multi_match_within_window (parametric pick_schwab_record_<N>).
# ===========================================================================


def test_show_ambiguity_multi_match_within_window_parametric(
    cli_workspace,
) -> None:
    """V1 source for N = parse ``resolution_reason`` text per plan §E.2
    acceptance criterion #4. With ``Schwab returned 3 orders`` in the
    reason, CLI must surface pick_schwab_record_1 / _2 / _3 entries +
    the static mark_unmatched / custom."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_pending_ambiguity(
            conn, run_id,
            ticker="VSAT",
            ambiguity_kind="multi_match_within_window",
            resolution_reason=(
                "unmatched_open_fill on (ticker='VSAT', fill_id=2): "
                "Schwab returned 3 orders within the match window with "
                "sum-qty=42 != journal qty=40"
            ),
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    assert "ambiguity_kind: multi_match_within_window" in r.output
    # Parametric pick_schwab_record_<N> entries (3 of them).
    assert "pick_schwab_record_1" in r.output
    assert "pick_schwab_record_2" in r.output
    assert "pick_schwab_record_3" in r.output
    assert "pick_schwab_record_4" not in r.output  # only 3 candidates
    # Static menu entries.
    assert "mark_unmatched" in r.output
    assert "custom" in r.output


def test_show_ambiguity_multi_match_window_no_count_falls_back_static(
    cli_workspace,
) -> None:
    """When ``resolution_reason`` is NULL OR doesn't contain a parseable
    candidate count, CLI surfaces only the static menu (no parametric
    pick_schwab_record entries). Defense-in-depth — pre-empts a parse
    failure crashing the surface."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_pending_ambiguity(
            conn, run_id,
            ticker="VSAT",
            ambiguity_kind="multi_match_within_window",
            resolution_reason=None,  # no parseable count
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    # Static menu always present.
    assert "mark_unmatched" in r.output
    assert "custom" in r.output
    # No parametric entries.
    assert "pick_schwab_record_" not in r.output


# ===========================================================================
# §4-8 — Remaining ambiguity_kinds render their menu codes.
# ===========================================================================


@pytest.mark.parametrize(
    ("ambiguity_kind", "expected_codes"),
    [
        (
            "unknown_schwab_subtype",
            ("acknowledge", "operator_truth", "custom"),
        ),
        (
            "field_shape_incompatible",
            ("acknowledge", "custom"),
        ),
        (
            "schwab_returned_no_match",
            ("mark_unmatched", "operator_truth"),
        ),
        (
            "validator_rejected",
            ("acknowledge", "operator_alternative"),
        ),
        (
            "unsupported",
            ("operator_truth", "acknowledge"),
        ),
    ],
)
def test_show_ambiguity_per_kind_codes_appear(
    cli_workspace, ambiguity_kind, expected_codes,
) -> None:
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_pending_ambiguity(
            conn, run_id,
            ticker="CVGI",
            ambiguity_kind=ambiguity_kind,
            resolution_reason=f"plant for {ambiguity_kind}",
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    assert f"ambiguity_kind: {ambiguity_kind}" in r.output
    for code in expected_codes:
        assert code in r.output, (
            f"missing code {code!r} for kind {ambiguity_kind!r} in "
            f"output:\n{r.output}"
        )


# ===========================================================================
# §9 — NULL ambiguity_kind (defense-in-depth — schema allows NULL on
# non-tier-2 rows).
# ===========================================================================


def test_show_ambiguity_null_kind_renders_shared_fields(
    cli_workspace,
) -> None:
    """A discrepancy in resolution='unresolved' with NULL ambiguity_kind
    is not a Tier-2 backlog row — but operator may still pass its id to
    show-ambiguity. CLI MUST NOT crash; renders shared fields + empty-
    menu advisory."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_pending_ambiguity(
            conn, run_id,
            ticker="DHC",
            ambiguity_kind=None,
            resolution="unresolved",
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    assert f"discrepancy_id: {did}" in r.output
    # Empty-menu advisory message; phrasing kept loose.
    assert ("no candidate choices" in r.output.lower()
            or "no ambiguity_kind" in r.output.lower())


# ===========================================================================
# T-Q2.4 — ASCII comparison table rendered by show-ambiguity.
# ===========================================================================


def _plant_disc_with_json(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    ticker: str = "CVGI",
    discrepancy_type: str = "stop_mismatch",
    field_name: str = "stop_price",
    ambiguity_kind: str | None = "unsupported",
    resolution: str = "pending_ambiguity_resolution",
    expected_value_json: str | None = None,
    actual_value_json: str | None = None,
    resolution_reason: str | None = None,
    created_at: str = "2026-05-18T09:00:00",
) -> int:
    """Plant a discrepancy row with explicit expected/actual JSON payloads.

    Extends the existing ``_plant_pending_ambiguity`` helper to support
    the ``expected_value_json`` and ``actual_value_json`` columns needed
    by T-Q2.4 tests.
    """
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, ticker, field_name, "
        "  material_to_review, resolution, resolution_reason, "
        "  ambiguity_kind, expected_value_json, actual_value_json, "
        "  created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, discrepancy_type, ticker, field_name,
            1, resolution, resolution_reason, ambiguity_kind,
            expected_value_json, actual_value_json,
            created_at,
        ),
    )
    return int(cur.lastrowid)


def test_show_ambiguity_renders_ascii_table_for_tabular_discrepancy(
    cli_workspace,
) -> None:
    """T-Q2.4 — stop_mismatch with valid JSON payloads triggers ASCII table.

    Discriminating assertions:
    - Header columns "Field", "Journal", "Schwab" rendered.
    - "|" column separator present.
    - Values 5.30 and 5.50 appear (formatted to 2dp by _format_value).
    - Table appears AFTER "created_at:" AND BEFORE "Candidate choices" /
      "(no candidate choices" advisory (i.e., before choice menu).
    """
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_disc_with_json(
            conn, run_id,
            ticker="CVGI",
            discrepancy_type="stop_mismatch",
            field_name="current_stop",
            ambiguity_kind="unsupported",
            # Production emitter shape (schwab_reconciliation.py:837,840):
            #   expected_value_json = {"current_stop": <journal>}  (asymmetric)
            #   actual_value_json   = {"stop_price":   <schwab>}
            expected_value_json='{"current_stop": 5.30}',
            actual_value_json='{"stop_price": 5.50}',
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    # Header columns appear.
    assert "Field" in r.output
    assert "Journal" in r.output
    assert "Schwab" in r.output
    # Column separator present.
    assert "|" in r.output
    # Values appear (formatted 2dp).
    assert "5.30" in r.output
    assert "5.50" in r.output
    # Ordering: table appears AFTER "created_at:" AND BEFORE choice menu.
    idx_created = r.output.index("created_at:")
    # The table separator "-+-" is distinctive; locate it.
    idx_rule = r.output.index("-+-")
    assert idx_created < idx_rule, (
        "Table should appear after created_at: header; "
        f"created_at at {idx_created}, table rule at {idx_rule}"
    )
    # Choice menu or advisory appears after the table.
    menu_marker = (
        r.output.index("Candidate choices")
        if "Candidate choices" in r.output
        else r.output.index("no candidate choices", 0)
        if "no candidate choices" in r.output
        else None
    )
    if menu_marker is not None:
        assert idx_rule < menu_marker, (
            "Table should appear before choice menu/advisory; "
            f"table rule at {idx_rule}, menu at {menu_marker}"
        )


def test_show_ambiguity_omits_table_for_unmatched_open_fill(
    cli_workspace,
) -> None:
    """T-Q2.4 — unmatched_open_fill returns None from build_compared_pairs;
    no table should be rendered, but the choice menu still renders.

    Discriminating: "Field | Journal" substring absent from output while
    Candidate choices block is still present.
    """
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_disc_with_json(
            conn, run_id,
            ticker="DHC",
            discrepancy_type="unmatched_open_fill",
            field_name="fill_match",
            ambiguity_kind="schwab_returned_no_match",
            expected_value_json='{"matched": null}',
            actual_value_json='{"matched": null}',
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    # Table header columns should NOT appear (no tabular comparison for
    # unmatched_open_fill; build_compared_pairs returns None).
    # Use the rule separator as the discriminating signal — it only appears
    # when the table is rendered.
    assert "-+-" not in r.output, (
        "Table separator '-+-' should be absent for unmatched_open_fill; "
        f"output:\n{r.output}"
    )
    # Choice menu still rendered.
    assert "Candidate choices" in r.output or "mark_unmatched" in r.output


def test_show_ambiguity_omits_table_on_non_dict_json(
    cli_workspace,
) -> None:
    """T-Q2.4 — JSON payload that parses successfully but is not a dict
    (e.g. a JSON array) causes the isinstance guard to skip table rendering
    silently, exit_code == 0.

    This tests the ``isinstance(_exp, dict) and isinstance(_act, dict)``
    guard in the CLI code.  A JSON array is valid JSON (passes the
    ReconciliationDiscrepancy dataclass's json.loads validation) but is
    not a dict; the guard short-circuits and no table is rendered.

    Note: genuinely malformed JSON (e.g. "not valid json") cannot be
    inserted via the normal path — the ``ReconciliationDiscrepancy``
    dataclass ``__post_init__`` validates JSON well-formedness at read-back
    time (in ``_row_to_discrepancy``), so the CLI would receive a ValueError
    before our defensive try/except even fires.  The non-dict path tests
    the same ``isinstance`` defensive layer against a realistically-insertable
    edge case.
    """
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_disc_with_json(
            conn, run_id,
            ticker="LION",
            discrepancy_type="stop_mismatch",
            field_name="stop_price",
            ambiguity_kind="unsupported",
            # A JSON array is valid JSON but not a dict — exercises the
            # isinstance guard in the CLI table-rendering block.
            expected_value_json="[5.30, 5.50]",
            actual_value_json="[5.50]",
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    # Must NOT crash — isinstance guard silently skips the table.
    assert r.exit_code == 0, (
        f"CLI should not crash on non-dict JSON; got exit_code={r.exit_code};"
        f"\n{r.output}"
    )
    # Table separator absent (no table rendered when payload is not a dict).
    assert "-+-" not in r.output


def test_show_ambiguity_output_is_ascii_only(
    cli_workspace,
) -> None:
    """T-Q2.4 — entire output of show-ambiguity for a tabular discrepancy
    contains only ASCII characters (ord < 128).

    This test discriminatingly validates the cp1252 safety invariant —
    any non-ASCII byte in the rendered output would raise UnicodeEncodeError
    on a Windows cp1252 terminal (CLAUDE.md gotcha).

    Uses CliRunner which captures via Python-level mechanisms; the companion
    slow-marked subprocess test (test_show_ambiguity_subprocess_cp1252_safety)
    exercises the actual OS encoder.
    """
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        did = _plant_disc_with_json(
            conn, run_id,
            ticker="VSAT",
            discrepancy_type="stop_mismatch",
            field_name="current_stop",
            ambiguity_kind="unsupported",
            # Production emitter shape (schwab_reconciliation.py:837,840):
            #   expected_value_json = {"current_stop": <journal>}
            #   actual_value_json   = {"stop_price":   <schwab>}
            expected_value_json='{"current_stop": 12.75}',
            actual_value_json='{"stop_price": 12.50}',
        )
        conn.commit()
    finally:
        conn.close()
    r = runner.invoke(main, [
        "--config", str(cfg),
        "journal", "discrepancy", "show-ambiguity", str(did),
    ])
    assert r.exit_code == 0, r.output
    # Every character in the output must be ASCII (ord < 128).
    non_ascii = [
        (i, c, ord(c))
        for i, c in enumerate(r.output)
        if ord(c) >= 128
    ]
    assert not non_ascii, (
        f"Non-ASCII chars found in show-ambiguity output: {non_ascii[:5]}"
    )


@pytest.mark.slow
def test_show_ambiguity_subprocess_cp1252_safety(
    cli_workspace,
) -> None:
    """T-Q2.4 — subprocess invocation validates actual OS stdout encoding.

    CliRunner captures stdout via Python-level mechanisms that bypass the
    Windows OS encoder (cp1252 / PYTHONIOENCODING-unset).  This slow-marked
    subprocess test uses the script-eval pattern (CLAUDE.md "Discriminating-
    test gap" + brief §A.4 acceptance bullet 6) to exercise the same code
    path through the real process encoder without requiring a full DB setup.

    Approach: ``subprocess.run([sys.executable, "-c", "<script>"])`` where
    the script imports ``render_journal_schwab_comparison_table_ascii`` +
    prints the result.  This is leaner than spawning the full CLI (which
    requires a DB-populated environment) while still passing the output
    through the real cp1252 encoder on Windows.

    Rationale for script-eval over full end-to-end CLI subprocess
    (Codex R1 Major #4 acceptance rationale — ACCEPTED WITH RATIONALE;
    V2.1 §VII.F amendment banked for brief §A.4):

    (a) The renderer's ``_sanitize`` function + internal ASCII-only assertion
        ``assert all(ord(c) < 128 ...)`` guarantee the output string is
        printable-ASCII before it reaches ``click.echo``.  Any non-ASCII byte
        can only originate from the renderer itself — not from Click's argument
        parsing or DB access layers.
    (b) ``click.echo(ascii_string)`` is a thin wrapper calling
        ``sys.stdout.write(ascii_string)`` + ``sys.stdout.flush()``.  When the
        rendered string is already ASCII-only, ``click.echo`` cannot introduce
        non-ASCII bytes.
    (c) The script-eval path uses ``print(table)`` which calls the same
        ``sys.stdout.write`` path as ``click.echo``, exercising the same OS
        encoder (cp1252 on Windows when PYTHONIOENCODING is unset).
    (d) Full end-to-end CLI testing with a seeded tmp DB would require ~150 LOC
        of fixture plumbing (DB schema creation, fixture seeding, env-var
        wiring, CLI runner subprocess invocation) for marginal additional
        coverage — the failure mode we are guarding against (CLAUDE.md cp1252
        gotcha: non-ASCII byte at stdout write time) IS captured by the
        script-eval form.

    The brief §A.4 acceptance criterion 6 explicitly notes "operator-accepted
    SKIP-with-rationale if cross-platform constraints intervene"; we go one
    step further by shipping a discriminating test that exercises the encoder
    path end-to-end through the process stdout.
    """
    import os
    import subprocess
    import sys

    # Build a small self-contained script that exercises the renderer directly.
    # Uses pairs that exercise the full _format_value path (float formatting).
    # Uses the production emitter shape for stop_mismatch (asymmetric keys):
    #   expected_value_json = {"current_stop": <journal>}
    #   actual_value_json   = {"stop_price":   <schwab>}
    script = (
        "from swing.trades.reconciliation_render import ("
        "render_journal_schwab_comparison_table_ascii, build_compared_pairs"
        "); "
        "pairs = build_compared_pairs('stop_mismatch', "
        "{'current_stop': 5.30}, {'stop_price': 5.50}); "
        "table = render_journal_schwab_comparison_table_ascii(list(pairs)); "
        "print(table)"
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTHONIOENCODING"}
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        timeout=30,
        env=env,
    )
    assert proc.returncode == 0, (
        f"Script exited non-zero: {proc.returncode}\n"
        f"stderr: {proc.stderr.decode('utf-8', errors='replace')}"
    )
    # No UnicodeEncodeError in stderr (cp1252 crash signature).
    assert b"UnicodeEncodeError" not in proc.stderr, (
        f"UnicodeEncodeError detected in subprocess stderr:\n"
        f"{proc.stderr.decode('utf-8', errors='replace')}"
    )
    # Table separator present (confirms the table was actually rendered
    # and printed through the process stdout).
    assert b"|" in proc.stdout, (
        f"Expected '|' table separator in subprocess stdout; got:\n"
        f"{proc.stdout.decode('utf-8', errors='replace')}"
    )


# ===========================================================================
# T-Q2.4 Major #3 — None vs empty-list semantics for build_compared_pairs.
# ===========================================================================


def test_cli_renders_placeholder_for_empty_tuple_compared_pairs(
    monkeypatch,
) -> None:
    """Codex R1 Major #3 — CLI distinguishes None (hidden) from empty list
    (placeholder rendered).

    The builder ``build_compared_pairs`` currently NEVER returns an empty
    list — it always returns None (for unmatched/unknown types) or a non-empty
    list (for known types).  This test uses ``monkeypatch`` to mock the builder
    returning ``[]`` and asserts the CLI renders '(no comparison data)' instead
    of silently omitting the section.

    Discriminating:
    - '(no comparison data)' appears in output.
    - Table separator '-+-' does NOT appear (no table rows).
    - CLI does not crash (exit_code == 0).
    """
    from unittest.mock import patch

    # Use CliRunner's mix_stderr=False to isolate stdout.
    from click.testing import CliRunner as _CliRunner
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        project = tmp_path / "project"
        project.mkdir()
        home = tmp_path / "home"
        home.mkdir()
        from tests.cli.test_cli_eval import _minimal_config
        cfg = _minimal_config(project, home)
        runner = _CliRunner()
        r = runner.invoke(main, ["--config", str(cfg), "db-migrate"])
        assert r.exit_code == 0, r.output
        db_path = home / "swing-data" / "swing.db"
        conn = sqlite3.connect(str(db_path))
        try:
            run_id = _seed_reconciliation_run(conn)
            # Plant a tabular discrepancy type (entry_price_mismatch).
            did = _plant_disc_with_json(
                conn, run_id,
                ticker="DHC",
                discrepancy_type="entry_price_mismatch",
                field_name="price",
                ambiguity_kind="unsupported",
                expected_value_json='{"price": 5.30}',
                actual_value_json='{"price": 5.23}',
            )
            conn.commit()
        finally:
            conn.close()

        # Mock build_compared_pairs to return empty list (simulates the empty
        # case that the builder itself never produces — pure boundary test).
        # The function is lazily imported inside the CLI handler from
        # swing.trades.reconciliation_render; patch the source module so the
        # lazy import re-binds to the mock.
        with patch(
            "swing.trades.reconciliation_render.build_compared_pairs",
            return_value=[],
        ):
            r = runner.invoke(main, [
                "--config", str(cfg),
                "journal", "discrepancy", "show-ambiguity", str(did),
            ])

    assert r.exit_code == 0, r.output
    # Placeholder text MUST appear (empty list, not None).
    assert "(no comparison data)" in r.output, (
        f"Expected '(no comparison data)' in output; got:\n{r.output}"
    )
    # Table separator must NOT appear (no rows to render).
    assert "-+-" not in r.output, (
        f"Table separator '-+-' should be absent for empty list; output:\n{r.output}"
    )
