"""22-F R1-08 (Reviewer A round 1; CHARC-ruled FIX by NAMING) -- `schwab
fetch --all` runs the snapshot step, which COMMITS an account snapshot, and
then the orders step.  When the orders step's refusal fires after the
snapshot is durable, S-B02's "the refusal wins" governs the EXIT CODE (1),
not the message's completeness: PRE-FIX the refusal said only "Orders step
failed: ...", omitting the durable snapshot (the D68 shape in a CLI
message).  POST-FIX it reads "the account snapshot IS recorded (snapshot_id
<n>); the orders step failed: <error>".

The ruling also asked for a READ of `record_snapshot`'s same-day handling:
`record_snapshot` -> `repos.account_equity_snapshots.upsert_snapshot`, a
SELECT-then-UPDATE-or-INSERT keyed on (snapshot_date, source, basis) inside
`BEGIN IMMEDIATE`, so a same-day retry UPDATEs the existing row's mutable
columns in place (PK preserved; 0041's `trg_aes_immutable` admits exactly
those columns).  No INSERT conflicts, so the retry is not a new escape; the
retry CONTROL below pins it.  Did-it-fire: the planted orders step is a
counting wrapper asserted called.
"""
from __future__ import annotations

import sqlite3

from swing.integrations.schwab.client import SchwabSchemaParityError
from tests._22f_proxies import raising
from tests.integrations.test_schwab_fetch_cli import (  # noqa: F401
    _make_cfg,
    _stub_schwabdev_client,
    invoke_cli,
    isolated_db,
    isolated_home,
)

_PARITY = "<accounts.orders: missing required key 'x'>"


def _snapshots(db) -> list[int]:
    c = sqlite3.connect(db)
    try:
        return [r[0] for r in c.execute(
            "SELECT snapshot_id FROM account_equity_snapshots "
            "WHERE source = 'schwab_api' ORDER BY snapshot_id")]
    finally:
        c.close()


def test_r1_08_orders_refusal_after_snapshot_names_the_snapshot(
        isolated_db, invoke_cli, monkeypatch):
    _stub_schwabdev_client(monkeypatch)
    planted = raising(SchwabSchemaParityError(_PARITY))
    monkeypatch.setattr(
        "swing.integrations.schwab.pipeline_steps._step_schwab_orders",
        planted)
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    result = invoke_cli(cfg, "fetch", "--all")
    assert planted.calls == 1  # did-it-fire
    snaps = _snapshots(isolated_db)
    assert len(snaps) == 1  # the snapshot IS durable (fresh read)
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert (f"Error: the account snapshot IS recorded (snapshot_id "
            f"{snaps[0]}); the orders step failed:") in result.output
    assert result.output.isascii()


def test_r1_08_same_day_retry_updates_the_snapshot_in_place_control(
        isolated_db, invoke_cli, monkeypatch):
    """CONTROL (both trees): a same-day `fetch --all` retry reaches
    `upsert_snapshot`'s UPDATE branch -- one row, the same snapshot_id,
    exit 0 both times."""
    _stub_schwabdev_client(monkeypatch)
    cfg = _make_cfg(db_path=isolated_db, environment="production")
    first = invoke_cli(cfg, "fetch", "--all")
    assert first.exit_code == 0, first.output
    snaps = _snapshots(isolated_db)
    assert len(snaps) == 1
    retry = invoke_cli(cfg, "fetch", "--all")
    assert retry.exit_code == 0, retry.output
    assert _snapshots(isolated_db) == snaps
