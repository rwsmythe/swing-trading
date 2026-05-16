"""Phase 12 C.D T-D.6 — CLI: ``swing journal reconcile-backfill`` scaffold.

Per plan §E.6 acceptance criteria — scaffold for the backfill orchestrator
that consumes unresolved discrepancies + dispatches Pass-1 / Pass-2
classification + tier-1 auto-apply + tier-2 stamp. T-D.6 scaffolds only
the iteration shell + ``BackfillPipelineActiveError`` guard + filter
behavior + dry-run-vs-apply-mode dispatch + Click mutually-exclusive
flag rejection.

Per-discrepancy classification logic + Pass-1 / Pass-2 mechanics are
deferred to T-D.7 + T-D.8 + T-D.9 (the ``_classify_and_apply`` callback
is a stub at T-D.6).

Discriminating tests:
  1. Dry-run with no ``--apply`` is the default + does NOT mutate journal.
  2. ``--apply --dry-run`` BOTH: Click rejects with usage error.
  3. Empty unresolved set: prints ``(no unresolved discrepancies)`` exit 0.
  4. ``--ticker DHC`` filter scopes iteration to DHC-only.
  5. ``BackfillPipelineActiveError``: plant pipeline_runs row with
     state='running'; invoke run_backfill; assert it raises.
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
    """Insert a minimal reconciliation_runs row + return run_id."""
    cur = conn.execute(
        "INSERT INTO reconciliation_runs ("
        "  source, started_ts, state, period_start, period_end"
        ") VALUES (?, ?, ?, ?, ?)",
        ("tos_csv", "2026-05-16T10:00:00", "completed",
         "2026-05-10", "2026-05-16"),
    )
    return int(cur.lastrowid)


def _plant_unresolved(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    ticker: str,
    discrepancy_type: str = "entry_price_mismatch",
    field_name: str = "price",
    created_at: str = "2026-05-16T10:05:00",
) -> int:
    """Insert one ``resolution='unresolved'`` discrepancy + return id."""
    cur = conn.execute(
        "INSERT INTO reconciliation_discrepancies ("
        "  run_id, discrepancy_type, ticker, field_name, "
        "  material_to_review, resolution, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, discrepancy_type, ticker, field_name,
            1, "unresolved", created_at,
        ),
    )
    return int(cur.lastrowid)


# ============================================================================
# CLI surface — Click flag interaction + default behavior
# ============================================================================


def test_dry_run_is_default_no_apply_flag(cli_workspace):
    """Per plan §E.6 #2 + discriminating test #1 — default is --dry-run."""
    runner, cfg, _db = cli_workspace
    r = runner.invoke(
        main, ["--config", str(cfg), "journal", "reconcile-backfill"],
    )
    assert r.exit_code == 0, r.output
    # Even with no discrepancies the empty-set message fires (not a crash).
    assert "(no unresolved discrepancies)" in r.output


def test_apply_and_dry_run_mutually_exclusive(cli_workspace):
    """Per plan §E.6 #3 + discriminating test #2 — both flags rejected."""
    runner, cfg, _db = cli_workspace
    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--apply", "--dry-run",
        ],
    )
    assert r.exit_code != 0
    # Click usage-error wording mentions the mutually exclusive constraint.
    assert "mutually exclusive" in r.output.lower() or "--apply" in r.output


def test_empty_unresolved_set_message(cli_workspace):
    """Discriminating test #3 — empty set → ``(no unresolved discrepancies)``."""
    runner, cfg, _db = cli_workspace
    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--dry-run",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "(no unresolved discrepancies)" in r.output


def test_ticker_filter_scopes_iteration(cli_workspace):
    """Discriminating test #4 — --ticker DHC scopes the iteration."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        _plant_unresolved(conn, run_id, ticker="CVGI")
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--dry-run", "--ticker", "DHC",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "DHC" in r.output
    assert "VSAT" not in r.output
    assert "CVGI" not in r.output


def test_ticker_filter_unscoped_shows_all(cli_workspace):
    """Sanity peer to test_ticker_filter_scopes_iteration: unscoped shows all."""
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        conn.commit()
    finally:
        conn.close()

    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--dry-run",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "DHC" in r.output
    assert "VSAT" in r.output


# ============================================================================
# Helper module — BackfillPipelineActiveError + iteration shell
# ============================================================================


def test_backfill_pipeline_active_error_raises(cli_workspace):
    """Discriminating test #5 — pipeline running → BackfillPipelineActiveError."""
    from swing.trades.reconciliation_backfill import (
        BackfillPipelineActiveError,
        run_backfill,
    )

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        # Plant a pipeline_runs row with state='running'.
        conn.execute(
            "INSERT INTO pipeline_runs ("
            "  started_ts, state, trigger, data_asof_date, "
            "  action_session_date, lease_token"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                "2026-05-16T10:00:00", "running", "manual",
                "2026-05-16", "2026-05-16", "test-lease-token",
            ),
        )
        conn.commit()

        with pytest.raises(BackfillPipelineActiveError):
            run_backfill(
                conn,
                dry_run=True,
                schwab_client=None,
                environment="production",
                account_hash=None,
            )
    finally:
        conn.close()


def test_backfill_pipeline_active_message_mentions_run_id(cli_workspace):
    """The error message names the active pipeline run for operator action."""
    from swing.trades.reconciliation_backfill import (
        BackfillPipelineActiveError,
        run_backfill,
    )

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO pipeline_runs ("
            "  started_ts, state, trigger, data_asof_date, "
            "  action_session_date, lease_token"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                "2026-05-16T10:00:00", "running", "manual",
                "2026-05-16", "2026-05-16", "test-lease-token",
            ),
        )
        run_id = int(cur.lastrowid)
        conn.commit()

        with pytest.raises(BackfillPipelineActiveError) as exc_info:
            run_backfill(
                conn,
                dry_run=True,
                schwab_client=None,
                environment="production",
                account_hash=None,
            )
        assert str(run_id) in str(exc_info.value)
    finally:
        conn.close()


def test_run_backfill_signature_keyword_only_post_star():
    """Plan §E.6 #4 — required-first then defaulted keyword-only after `*`."""
    import inspect

    from swing.trades.reconciliation_backfill import run_backfill

    sig = inspect.signature(run_backfill)
    params = list(sig.parameters.values())
    # ``conn`` is the single positional-or-keyword param.
    assert params[0].name == "conn"
    assert params[0].kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    # Remaining params are keyword-only.
    for p in params[1:]:
        assert p.kind == inspect.Parameter.KEYWORD_ONLY, (
            f"param {p.name!r} should be keyword-only; got {p.kind}"
        )
    # Required-first then defaulted ordering check: every required param
    # (no default) appears before any defaulted param.
    seen_default = False
    for p in params[1:]:
        if p.default is inspect.Parameter.empty:
            assert not seen_default, (
                f"required keyword param {p.name!r} appears after a "
                f"defaulted one — violates required-first ordering"
            )
        else:
            seen_default = True


def test_backfill_summary_dataclass_fields():
    """Plan §E.6 #5 — BackfillSummary has all required counter fields."""
    from swing.trades.reconciliation_backfill import BackfillSummary

    s = BackfillSummary()
    assert s.tier1_applied == 0
    assert s.tier2_stamped == 0
    assert s.tier_errored == 0
    assert s.pass_2_failed == 0
    assert s.skipped_already_resolved == 0
    assert s.skipped_pass_2_failed == 0
    assert s.per_discrepancy_outcomes == []


def test_backfill_outcome_dataclass_fields():
    """Plan §E.6 #6 — BackfillOutcome carries the per-row outcome record."""
    from swing.trades.reconciliation_backfill import BackfillOutcome

    o = BackfillOutcome(
        discrepancy_id=42,
        ticker="DHC",
        discrepancy_type="entry_price_mismatch",
        tier=1,
        outcome="tier1_applied",
    )
    assert o.discrepancy_id == 42
    assert o.ticker == "DHC"
    assert o.discrepancy_type == "entry_price_mismatch"
    assert o.tier == 1
    assert o.outcome == "tier1_applied"
    # Optional fields default sanely.
    assert o.ambiguity_kind is None
    assert o.correction_id is None
    assert o.pass_2_call_id is None
    assert o.reason is None


def test_run_backfill_returns_summary_for_empty_set(cli_workspace):
    """run_backfill returns a BackfillSummary instance even with no rows."""
    from swing.trades.reconciliation_backfill import (
        BackfillSummary,
        run_backfill,
    )

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        summary = run_backfill(
            conn,
            dry_run=True,
            schwab_client=None,
            environment="production",
            account_hash=None,
        )
        assert isinstance(summary, BackfillSummary)
        assert summary.per_discrepancy_outcomes == []
    finally:
        conn.close()


def test_run_backfill_iteration_visits_unresolved_rows(cli_workspace):
    """T-D.6 scaffold iterates unresolved discrepancies + emits per-row outcomes.

    Per-discrepancy classification logic is T-D.7+. T-D.6 stub returns
    ``outcome='projection'`` for dry-run mode (placeholder).
    """
    from swing.trades.reconciliation_backfill import run_backfill

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        conn.commit()

        summary = run_backfill(
            conn,
            dry_run=True,
            schwab_client=None,
            environment="production",
            account_hash=None,
        )
        assert len(summary.per_discrepancy_outcomes) == 2
        tickers = {o.ticker for o in summary.per_discrepancy_outcomes}
        assert tickers == {"DHC", "VSAT"}
    finally:
        conn.close()


def test_run_backfill_ticker_kwarg_filters_iteration(cli_workspace):
    """The ``ticker`` kwarg restricts the iteration set."""
    from swing.trades.reconciliation_backfill import run_backfill

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        conn.commit()

        summary = run_backfill(
            conn,
            dry_run=True,
            schwab_client=None,
            environment="production",
            account_hash=None,
            ticker="DHC",
        )
        assert len(summary.per_discrepancy_outcomes) == 1
        assert summary.per_discrepancy_outcomes[0].ticker == "DHC"
    finally:
        conn.close()


def test_run_backfill_limit_kwarg_caps_iteration(cli_workspace):
    """The ``limit`` kwarg caps the iteration count."""
    from swing.trades.reconciliation_backfill import run_backfill

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        _plant_unresolved(conn, run_id, ticker="CVGI")
        conn.commit()

        summary = run_backfill(
            conn,
            dry_run=True,
            schwab_client=None,
            environment="production",
            account_hash=None,
            limit=2,
        )
        assert len(summary.per_discrepancy_outcomes) == 2
    finally:
        conn.close()


# ============================================================================
# Codex R1 Major #1 — CLI handler MUST construct schwab_client via the
# cfg-cascade (env vars > user-config.toml > prompt) + apply_overrides
# discipline. Without this, --apply for unmatched_*_fill discrepancies
# would call ``client.account_orders`` on None → AttributeError.
# ============================================================================


def test_apply_overrides_invoked_at_cli_entry(cli_workspace, monkeypatch):
    """Major #1 fix — apply_overrides() fires at CLI entry.

    Pin: monkeypatch ``swing.config_overrides.apply_overrides`` to a
    spy + invoke the CLI in dry-run; assert the spy was called with the
    raw cfg from ctx.obj.
    """
    runner, cfg, _db = cli_workspace
    calls: list = []
    from swing import config_overrides as _config_overrides

    real_apply = _config_overrides.apply_overrides

    def _spy(cfg_arg):
        calls.append(cfg_arg)
        return real_apply(cfg_arg)

    monkeypatch.setattr(
        "swing.cli.apply_overrides", _spy, raising=False,
    )
    # The CLI imports apply_overrides lazily via `from
    # swing.config_overrides import apply_overrides`, so we must patch
    # the source module too to catch the import.
    monkeypatch.setattr(_config_overrides, "apply_overrides", _spy)

    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--dry-run", "--no-pass-2-on-dry-run",
        ],
    )
    assert r.exit_code == 0, r.output
    assert len(calls) >= 1


def test_apply_constructs_schwab_client_via_cli_schwab_helpers(
    cli_workspace, monkeypatch,
):
    """Major #1 fix — --apply path constructs schwab_client.

    Plant a discrepancy + invoke --apply against production env with
    account_hash configured via monkeypatch on cfg dataclass; assert
    ``_build_schwabdev_client_for_fetch`` was invoked with cfg + env +
    credentials. Without the fix, schwab_client would be None and Pass 2
    dispatch would AttributeError.
    """
    runner, cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(
            conn, run_id, ticker="DHC",
            discrepancy_type="unmatched_open_fill",
            field_name="match",
        )
        conn.commit()
    finally:
        conn.close()

    # Spy on the helpers invoked at CLI entry.
    build_calls: list = []
    resolve_calls: list = []

    class _FakeClient:
        def account_orders(self, *args, **kwargs):
            return []

    def _spy_resolve(cfg_arg, env_arg):
        resolve_calls.append((cfg_arg, env_arg))
        return ("spy-client-id", "spy-client-secret")

    def _spy_build(cfg_arg, env_arg, cid, csec):
        build_calls.append((cfg_arg, env_arg, cid, csec))
        return _FakeClient()

    from swing import cli_schwab as _cli_schwab

    monkeypatch.setattr(
        _cli_schwab, "_resolve_credentials_for_cli", _spy_resolve,
    )
    monkeypatch.setattr(
        _cli_schwab, "_build_schwabdev_client_for_fetch", _spy_build,
    )

    # Inject account_hash via apply_overrides override path. Use the
    # cfg-cascade write surface for realism: a user-config.toml fragment.
    from pathlib import Path as _Path
    home_str = cfg.parent.parent / "home"
    home = _Path(home_str)
    user_config = home / "swing-data" / "user-config.toml"
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text(
        "[integrations.schwab]\n"
        "environment = \"production\"\n"
        "account_hash = \"AAAAAAAA1234567890\"\n",
        encoding="utf-8",
    )
    # Suppress real apply_overrides home discovery — monkeypatch
    # USERPROFILE + HOME so the test does not leak to the operator's
    # real ~/swing-data/user-config.toml.
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    # Also clear potential env vars from the host shell.
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)

    # Stub Pass 2 audit-fetch so we do not need a real Schwab API.
    from swing.trades import reconciliation_backfill as _bf

    def _stub_audited(*args, **kwargs):
        return (None, [])

    monkeypatch.setattr(_bf, "get_account_orders_audited", _stub_audited)

    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--apply",
        ],
    )
    # If the cfg-cascade resolves credentials + the spy fires, exit 0.
    # Otherwise the SchwabConfigMissingError path raises ClickException
    # and exit_code != 0 — that itself proves the fix would block a
    # broken cfg from silently no-op'ing.
    assert r.exit_code == 0, r.output
    # Major #1 binding pin: build helper was invoked with cfg + env +
    # spy-resolved credentials.
    assert len(build_calls) == 1, (
        f"_build_schwabdev_client_for_fetch must be invoked at CLI "
        f"entry; got {len(build_calls)} call(s)"
    )
    assert build_calls[0][1] == "production"
    assert build_calls[0][2] == "spy-client-id"
    assert build_calls[0][3] == "spy-client-secret"
    # And the resolve helper too (cfg-cascade).
    assert len(resolve_calls) == 1


def test_dry_run_no_pass_2_does_not_construct_client(
    cli_workspace, monkeypatch,
):
    """Major #1 fix — --dry-run + --no-pass-2-on-dry-run skips construction.

    Per design comment in the CLI handler: client construction is
    skipped under sandbox OR (dry_run AND no_pass_2_on_dry_run). Pin
    the second branch so unnecessary prompts don't fire on a preview.
    """
    runner, cfg, _db = cli_workspace
    build_calls: list = []

    def _spy_build(*args, **kwargs):
        build_calls.append(args)
        raise AssertionError("must NOT be called under no-pass-2 dry-run")

    from swing import cli_schwab as _cli_schwab

    monkeypatch.setattr(
        _cli_schwab, "_build_schwabdev_client_for_fetch", _spy_build,
    )

    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--dry-run", "--no-pass-2-on-dry-run",
        ],
    )
    assert r.exit_code == 0, r.output
    assert len(build_calls) == 0


def test_pipeline_started_mid_iteration_aborts_loop(
    cli_workspace, monkeypatch,
):
    """Codex R1 Major #3 fix — per-iteration recheck closes the race window.

    Plant 3 discrepancies. Stub ``_classify_and_apply`` so that after
    the first iteration completes, a ``pipeline_runs`` row with
    state='running' is inserted. The next iteration's
    ``_check_pipeline_not_running`` recheck MUST raise
    ``BackfillPipelineActiveError`` + abort the loop. The first
    discrepancy's outcome persists in the summary; the 2nd + 3rd are
    NOT processed.
    """
    from swing.trades.reconciliation_backfill import (
        BackfillOutcome,
        BackfillPipelineActiveError,
        run_backfill,
    )
    from swing.trades import reconciliation_backfill as _bf

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        _plant_unresolved(conn, run_id, ticker="CVGI")
        conn.commit()

        call_count = {"n": 0}

        def _spy_classify_and_apply(conn_arg, disc, **kwargs):
            call_count["n"] += 1
            # After the FIRST iteration, plant a pipeline_runs row to
            # simulate a pipeline starting mid-backfill.
            if call_count["n"] == 1:
                conn_arg.execute(
                    "INSERT INTO pipeline_runs ("
                    "  started_ts, state, trigger, data_asof_date, "
                    "  action_session_date, lease_token"
                    ") VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "2026-05-16T10:30:00", "running", "manual",
                        "2026-05-16", "2026-05-16",
                        "race-test-lease",
                    ),
                )
                conn_arg.commit()
            return BackfillOutcome(
                discrepancy_id=int(disc.discrepancy_id or 0),
                ticker=disc.ticker,
                discrepancy_type=disc.discrepancy_type,
                tier=1,
                outcome="tier1_applied",
            )

        monkeypatch.setattr(
            _bf, "_classify_and_apply", _spy_classify_and_apply,
        )

        with pytest.raises(BackfillPipelineActiveError):
            run_backfill(
                conn,
                dry_run=False,
                schwab_client=None,
                environment="production",
                account_hash="acct-hash",
            )

        # First iteration ran (call_count==1). The second iteration's
        # recheck should have raised, so call_count stays at 1.
        assert call_count["n"] == 1, (
            f"expected exactly 1 iteration before recheck raised; "
            f"got {call_count['n']}"
        )
        # Verify the planted pipeline_runs row IS there (proves the
        # mid-iteration mutation took effect).
        running = conn.execute(
            "SELECT id FROM pipeline_runs WHERE state = 'running'",
        ).fetchone()
        assert running is not None
    finally:
        conn.close()


def test_pipeline_recheck_does_not_fire_when_no_active_pipeline(
    cli_workspace,
):
    """Sanity peer — recheck does NOT spuriously raise when clean."""
    from swing.trades.reconciliation_backfill import run_backfill

    _runner, _cfg, db_path = cli_workspace
    conn = sqlite3.connect(db_path)
    try:
        run_id = _seed_reconciliation_run(conn)
        _plant_unresolved(conn, run_id, ticker="DHC")
        _plant_unresolved(conn, run_id, ticker="VSAT")
        conn.commit()

        # No mock — full dry-run + no pipeline_runs running row.
        summary = run_backfill(
            conn,
            dry_run=True,
            schwab_client=None,
            environment="production",
            account_hash="acct-hash",
        )
        # Both rows iterated cleanly.
        assert len(summary.per_discrepancy_outcomes) == 2
    finally:
        conn.close()


def test_sandbox_env_does_not_construct_client(cli_workspace, monkeypatch):
    """Major #1 fix — sandbox env skips construction (C.C inner short-circuit)."""
    runner, cfg, _db = cli_workspace
    build_calls: list = []

    def _spy_build(*args, **kwargs):
        build_calls.append(args)
        raise AssertionError("must NOT be called under sandbox")

    from swing import cli_schwab as _cli_schwab

    monkeypatch.setattr(
        _cli_schwab, "_build_schwabdev_client_for_fetch", _spy_build,
    )
    # Inject environment='sandbox' via user-config.toml override.
    from pathlib import Path as _Path
    home = _Path(str(cfg.parent.parent / "home"))
    user_config = home / "swing-data" / "user-config.toml"
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text(
        "[integrations.schwab]\nenvironment = \"sandbox\"\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))

    r = runner.invoke(
        main, [
            "--config", str(cfg), "journal", "reconcile-backfill",
            "--dry-run",
        ],
    )
    assert r.exit_code == 0, r.output
    assert len(build_calls) == 0
