"""Arc 22-B Task 4 -- `swing/data/repos/entry_intent_attestations.py`.

CHARC-S3 condition 1: the attestation table's SQL lives in its own repo module
(the repo-per-table precedent of every evidence table); the service imports it
and holds no table SQL. The insert runs in the CALLER's transaction and passes
the REAL admission triggers.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.data.models import EntryIntentAttestation
from swing.data.repos.entry_intent_attestations import (
    get_attestation,
    insert_attestation,
)
from tests.data.test_migration_0040_attestations import _world, tier2_row


def test_insert_then_get_round_trips_through_the_real_triggers(tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        att = EntryIntentAttestation(attestation_id=None, **tier2_row())
        c.execute("BEGIN IMMEDIATE")
        new_id = insert_attestation(c, att)
        c.execute("COMMIT")
        got = get_attestation(c, 20)
    finally:
        c.close()
    assert new_id > 0
    assert got is not None and got.attestation_id == new_id
    assert got == EntryIntentAttestation(attestation_id=new_id, **tier2_row())


def test_get_attestation_is_none_for_an_unattested_trade(tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        assert get_attestation(c, 20) is None
    finally:
        c.close()


def test_insert_refuses_a_caller_supplied_id(tmp_path: Path) -> None:
    c = _world(tmp_path)
    try:
        with pytest.raises(ValueError, match="assigned by the DB"):
            insert_attestation(
                c, EntryIntentAttestation(attestation_id=5, **tier2_row()))
    finally:
        c.close()
