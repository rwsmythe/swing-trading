"""Slow-marked live integration test for Finviz Elite API.

Hits the real Finviz API. Skipped automatically when the operator's token is
not present in user-config — so a fresh-clone CI without the secret never
fails. Manually run via:

    python -m pytest -m slow tests/integrations/test_finviz_api_live.py -v

Purpose: drift-detection harness. If Finviz changes column ordering, adds a
new column, or alters response Content-Type, this test fails on schema-shape
mismatch and the cassettes need re-recording per plan §G runbook.
"""
from __future__ import annotations

import pytest

from swing.config import load
from swing.config_overrides import apply_overrides
from swing.integrations.finviz_api import FinvizClient
from swing.pipeline.finviz_schema import REQUIRED_COLUMNS


@pytest.mark.slow
def test_finviz_live_fetch_and_normalize_schema_parity(tmp_path) -> None:
    from pathlib import Path
    cfg = apply_overrides(load(Path("swing.config.toml")))
    if not cfg.integrations.finviz.token or not cfg.integrations.finviz.screen_query:
        pytest.skip(
            "Finviz token / screen_query not in user-config; "
            "skipping live API test (per plan §K)."
        )

    client = FinvizClient(cfg)
    body = client.fetch_screen()
    assert isinstance(body, bytes)
    canonical = client.normalize_to_canonical_csv(body)
    header = canonical.split("\n", 1)[0]
    columns = tuple(c.strip() for c in header.split(","))
    assert columns == REQUIRED_COLUMNS, columns

    data_rows = [line for line in canonical.split("\n")[1:] if line.strip()]
    assert len(data_rows) > 0


@pytest.mark.slow
def test_finviz_live_signature_hash_stable_within_session() -> None:
    """Two back-to-back live calls produce the same signature (column-set
    + first-row Ticker/Sector/Industry don't drift in a few seconds)."""
    from pathlib import Path
    cfg = apply_overrides(load(Path("swing.config.toml")))
    if not cfg.integrations.finviz.token or not cfg.integrations.finviz.screen_query:
        pytest.skip("Finviz creds absent; skipping live signature stability test.")

    client = FinvizClient(cfg)
    sig_a = client.compute_signature_hash(client.fetch_screen())
    sig_b = client.compute_signature_hash(client.fetch_screen())
    assert sig_a == sig_b, (sig_a, sig_b)
