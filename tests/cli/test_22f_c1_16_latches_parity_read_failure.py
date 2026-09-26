"""22-F T-A8, C1-16 -- the RED ATTEMPT, CLI half: `swing latches parity` with
the decision-intent read planted to raise `sqlite3.OperationalError("database
is locked")` (patch target and did-it-fire as in the web half,
`tests/web/test_routes/test_22f_c1_16_latches_read_failure.py`).

Pins the OBSERVED outcome on this tree (recorded in the T-A8 commit and the
exec ledger).
"""
from __future__ import annotations

import sqlite3

from tests._22f_proxies import raising
from tests.cli.test_cli_latches_parity import (  # noqa: F401 -- fixture
    _run,
    _seed,
    seeded_db,
)

_TARGET = "swing.data.repos.latch_order_intents.list_intents_for_latch"


def test_C1_16_parity_read_failure_attempt(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed(cfg)
    planted = raising(sqlite3.OperationalError("database is locked"))
    monkeypatch.setattr(_TARGET, planted)
    result = _run(cfg_path)
    assert planted.calls >= 1, (planted.calls, result.output)  # did-it-fire
    assert result.exception is None or isinstance(
        result.exception, SystemExit), repr(result.exception)
    assert "Traceback" not in result.output
