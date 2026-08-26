"""The envelope-canonicality guard, measured AGAINST THE TWO REAL ENGINES.

NOT A COUNTED ROUND.  These are self-sweep (`SS-`) regressions from the
dedicated sweep the gate-holder ruled after round 9's composition.

WHY A DIFFERENTIAL TEST AND NOT ASSERTED VERDICTS.  ``envelope_is_canonical``
answers "would Python and SQLite read this document alike?", and the only
honest way to pin that answer is to ASK BOTH ENGINES rather than to re-assert
the guard's own model of them.  A table of hand-written expected verdicts is a
SECOND SPELLING of SQLite's semantics -- exactly the "two spellings that agree
today" class 22A-R8-01 refused -- and it would keep passing on the day either
engine changed.  So each row below runs ``json.loads`` + the service reader in
Python, runs ``json_extract`` in SQLite, and asserts the guard said ``False``
whenever and only whenever the two readings DIFFER.

The guard is deliberately allowed to be STRICTER than the differential on one
declared shape (two duplicate keys carrying the SAME value), and that
exemption is named in the table rather than left as a silent tolerance.

FROZEN CLOCK: nothing here reads a clock at all.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from swing.trades.latched_origin import (
    ENVELOPE_KEYS_READ_BY_BOTH_DOMAINS,
    SCHWAB_ORDER_ID_ENVELOPE_KEY,
    SCHWAB_SYMBOL_ENVELOPE_KEY,
    broker_order_id_from_envelope,
    envelope_is_canonical,
    envelope_recognises_an_order,
    instrument_symbol_from_envelope,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_0037 = (
    REPO_ROOT / "swing" / "data" / "migrations"
    / "0037_latch_order_mandate_links.sql"
)

_SERVICE_READER = {
    SCHWAB_ORDER_ID_ENVELOPE_KEY: broker_order_id_from_envelope,
    SCHWAB_SYMBOL_ENVELOPE_KEY: instrument_symbol_from_envelope,
}

# label -> (raw envelope, stricter_than_the_differential)
_ENVELOPES: dict[str, tuple[str, bool]] = {
    "clean, both keys": (
        '{"schwab_order_id": "1002937461", "schwab_instrument_symbol": "FTRE"}',
        False),
    "no envelope keys at all": ('{"entry_price": 18.5}', False),
    "order id JSON null": (
        '{"schwab_order_id": null, "schwab_instrument_symbol": "FTRE"}', False),
    "order id padded": ('{"schwab_order_id": "  1002937461  "}', False),
    "order id blank": ('{"schwab_order_id": "   "}', False),
    "order id empty": ('{"schwab_order_id": ""}', False),
    "order id numeric": ('{"schwab_order_id": 1002937461}', False),
    "order id boolean": ('{"schwab_order_id": true}', False),
    "order id an object": ('{"schwab_order_id": {"a": 1}}', False),
    "order id an array": ('{"schwab_order_id": [1]}', False),
    "symbol padded": (
        '{"schwab_order_id": "1002937461", '
        '"schwab_instrument_symbol": "  FTRE  "}', False),
    "symbol numeric": (
        '{"schwab_order_id": "1002937461", "schwab_instrument_symbol": 7}',
        False),
    "duplicate order id, last null": (
        '{"schwab_order_id": "1002937461", "schwab_order_id": null}', False),
    "duplicate order id, last numeric": (
        '{"schwab_order_id": "1002937461", "schwab_order_id": 42}', False),
    "duplicate order id, last empty": (
        '{"schwab_order_id": "1002937461", "schwab_order_id": ""}', False),
    "duplicate order id, both strings": (
        '{"schwab_order_id": "A", "schwab_order_id": "B"}', False),
    "duplicate symbol keys": (
        '{"schwab_instrument_symbol": "ZZZZ", '
        '"schwab_instrument_symbol": "FTRE"}', False),
    "a NESTED key of the same name": (
        '{"schwab_order_id": "1002937461", '
        '"raw": {"schwab_order_id": "unrelated"}}', False),
    "not an object": ('[1, 2, 3]', False),
    "malformed JSON": ('{bad', False),
    # DECLARED EXEMPTION, not a tolerance: the two readings AGREE here, and
    # the guard still refuses.  It is 22A-R8-01's shipped shape (a duplicate
    # key at all is the ambiguity), the direction is a wrong REFUSAL on a
    # document no emitter in this repo produces, and naming it here is what
    # stops the differential quietly widening the guard on a later pass.
    "duplicate order id, IDENTICAL values": (
        '{"schwab_order_id": "A", "schwab_order_id": "A"}', True),
}


def _sqlite_reading(conn: sqlite3.Connection, raw: str, key: str):
    """What every SQL site in 0037 reads: the extract under a ``json_valid``
    CASE, which is the exact form the migration uses."""
    return conn.execute(
        "SELECT CASE WHEN json_valid(?1) THEN json_extract(?1, ?2) END",
        (raw, "$." + key),
    ).fetchone()[0]


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    try:
        yield c
    finally:
        c.close()


@pytest.mark.parametrize("label", sorted(_ENVELOPES))
def test_the_guard_refuses_exactly_the_envelopes_the_two_engines_read_apart(
        conn, label) -> None:
    raw, stricter = _ENVELOPES[label]
    disagreements = {}
    for key in ENVELOPE_KEYS_READ_BY_BOTH_DOMAINS:
        service = _SERVICE_READER[key](raw)
        engine = _sqlite_reading(conn, raw, key)
        if service != engine and not (service is None and engine is None):
            disagreements[key] = (service, engine)
    verdict = envelope_is_canonical(raw)
    if disagreements:
        assert verdict is False, (
            f"{label!r}: the engines read {disagreements} and the guard "
            f"called the envelope canonical")
    elif stricter:
        assert verdict is False, (
            f"{label!r} is the DECLARED exemption and must stay refused; if "
            f"it now passes, update the declaration rather than the table")
    else:
        assert verdict is True, (
            f"{label!r}: both engines read alike and the guard refused it -- "
            f"a wrong REFUSAL manufactured by the guard itself")


@pytest.mark.parametrize("label", sorted(_ENVELOPES))
def test_a_refused_envelope_is_always_RECOGNISED(conn, label) -> None:
    """SS-1's other half: the refusal must SUPPRESS, never fall through.

    A guard that refuses and then lets the caller run the ordinary chain is
    worse than no guard: the row lands with TODAY's candidate and nothing
    records that a mandate was named.  So every envelope the guard refuses
    must ALSO be one the shared recognition trigger claims.
    """
    raw, _stricter = _ENVELOPES[label]
    if envelope_is_canonical(raw):
        pytest.skip("canonical; recognition is decided by the order id alone")
    assert envelope_recognises_an_order(raw) is True


def test_a_deeply_nested_envelope_does_not_RAISE_out_of_the_guard() -> None:
    """The exception-type roster, at the one place it still bounded a family.

    22A-R8-03 ruled that ENUMERATING the raisable types is the
    hand-maintained-roster failure, and widened the resolver's containment to
    ``Exception``.  The three envelope readers kept
    ``except (ValueError, TypeError)`` -- and ``json.loads`` raises
    ``RecursionError``, a ``RuntimeError``, on a deeply nested document.

    PRE-FIX this call raised out of ``envelope_is_canonical``, out of
    ``resolve_latched_provenance``, and rolled the money-bearing entry back.
    POST-FIX it answers ``False`` -- fail-CLOSED, because a question the
    decoder could not answer is not a pass.
    """
    deep = '{"schwab_order_id":' + '{"a":' * 20000 + '1' + '}' * 20000 + '}'
    with pytest.raises(RecursionError):
        json.loads(deep)                       # the PREMISE, measured here
    assert envelope_is_canonical(deep) is False
    assert envelope_recognises_an_order(deep) is True


# ---------------------------------------------------------------------------
# THE CLOSURE CHECK -- the roster is WALKED, never maintained by hand.
# ---------------------------------------------------------------------------
_ENVELOPE_EXTRACT = re.compile(
    r"json_extract\(\s*\w+\.schwab_source_value_json\s*,\s*'\$\.([a-z_]+)'",
    re.S,
)


def test_every_envelope_key_the_migration_reads_is_in_the_guarded_roster(
) -> None:
    """A HAND-ENUMERATED ROSTER IS THE SAME INSTRUMENT AS THE COUNT IT
    REPLACED (recipe, Demand C).  So the roster is not asserted; it is WALKED.

    Migration 0037 is the only place SQL reads a fill's envelope, and every
    key it extracts is a key BOTH domains read -- which is precisely the set
    the canonicality guard must cover.  Add a third extract to the trigger and
    this fails until the roster grows, rather than the guard silently covering
    two of three.
    """
    keys = set(_ENVELOPE_EXTRACT.findall(
        MIGRATION_0037.read_text(encoding="utf-8")))
    assert keys, (
        "no envelope extract found in migration 0037; the walk would then "
        "pass vacuously, which is the existence-is-not-completeness trap")
    unguarded = sorted(keys - set(ENVELOPE_KEYS_READ_BY_BOTH_DOMAINS))
    assert not unguarded, (
        f"migration 0037 reads {unguarded} out of a fill envelope and the "
        f"canonicality guard does not cover it, so Python and SQL can read "
        f"those keys apart with nothing to refuse the divergence")


def test_the_walk_finds_the_keys_it_is_supposed_to_find() -> None:
    """The closure check's OWN discriminator.

    A regex that matched nothing would make the check above vacuous while
    reading as a guarantee; a regex that matched everything would make it
    unfalsifiable.  Both keys are named here, so the walk is pinned to the
    two extracts that exist today.
    """
    keys = set(_ENVELOPE_EXTRACT.findall(
        MIGRATION_0037.read_text(encoding="utf-8")))
    assert keys == {SCHWAB_ORDER_ID_ENVELOPE_KEY, SCHWAB_SYMBOL_ENVELOPE_KEY}
