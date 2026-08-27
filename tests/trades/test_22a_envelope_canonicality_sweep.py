"""The envelope canonicaliser -- THE ONE DERIVATION, and its verdicts.

PERSIST-CANONICAL (CHARC + RD, 2026-08-26).  This file used to hold a
DIFFERENTIAL test: it ran ``json.loads`` in Python and ``json_extract`` in
SQLite over the same document and asserted the guard refused exactly when the
two engines read the document apart.  That was the honest instrument for the
shape it tested -- a Python predicate MIRRORED in SQL -- and its own premise is
what ten review rounds retired.  Three consecutive rounds each produced a NEW
engine divergence (NaN documents, tab/newline/NBSP whitespace,
integer-vs-TEXT affinity), all reproduced, none a repeat.

So the mirror is gone: ``canonical_envelope_identity`` decides ONCE, its answer
is PERSISTED against the exact document it read, and every SQL consumer
compares stored values.  A verdict TABLE is now the right instrument for the
same reason it was the wrong one before -- there is no second engine for it to
be a second spelling of.  Keeping the differential would be worse than
redundant: it would ASSERT A RETIRED REQUIREMENT, and the NaN row below would
have to be "fixed" out of the canonicaliser to satisfy a property nothing needs
any more.

THE THREE MEASURED DIVERGENCES ARE FIRST-CLASS ROWS HERE, each resolved the way
the ruling requires -- canonicalised at the service, or refused at it.

FROZEN CLOCK: nothing here reads a clock at all.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from swing.trades.latched_origin import (
    ENVELOPE_CANONICAL,
    ENVELOPE_REFUSED,
    canonical_envelope_identity,
    envelope_is_canonical,
    envelope_recognises_an_order,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_0037 = (
    REPO_ROOT / "swing" / "data" / "migrations"
    / "0037_latch_order_mandate_links.sql"
)

ID = "1002937461"

# label -> (raw envelope, expected (state, broker_order_id, instrument_symbol))
_ENVELOPES: dict[str, tuple[str, tuple[str, str | None, str | None]]] = {
    "clean, both keys": (
        json.dumps({"schwab_order_id": ID, "schwab_instrument_symbol": "FTRE"}),
        (ENVELOPE_CANONICAL, ID, "FTRE")),
    "no envelope keys at all": (
        '{"entry_price": 18.5}', (ENVELOPE_CANONICAL, None, None)),
    "order id JSON null": (
        json.dumps({"schwab_order_id": None,
                    "schwab_instrument_symbol": "FTRE"}),
        (ENVELOPE_CANONICAL, None, "FTRE")),

    # ---------- DIVERGENCE 2, MEASURED: python str.strip removes tab, newline
    # and NBSP; sqlite trim() removes ASCII SPACE ONLY.  The predecessor built
    # the whole whitespace class out of the ONE character the two engines agree
    # about, which is why every test it wrote passed.  All four are REFUSED at
    # the service, so the class is closed by ONE rule rather than by a grammar
    # that has to enumerate whitespace.
    "order id padded, ASCII space": (
        json.dumps({"schwab_order_id": f"  {ID}  "}),
        (ENVELOPE_REFUSED, None, None)),
    "order id padded, TAB": (
        json.dumps({"schwab_order_id": f"\t{ID}\t"}),
        (ENVELOPE_REFUSED, None, None)),
    "order id padded, NEWLINE": (
        json.dumps({"schwab_order_id": f"\n{ID}\n"}),
        (ENVELOPE_REFUSED, None, None)),
    "order id padded, NBSP": (
        json.dumps({"schwab_order_id": f"\u00a0{ID}\u00a0"}),
        (ENVELOPE_REFUSED, None, None)),

    "order id blank": ('{"schwab_order_id": "   "}',
                       (ENVELOPE_REFUSED, None, None)),
    "order id empty": ('{"schwab_order_id": ""}',
                       (ENVELOPE_REFUSED, None, None)),

    # ---------- DIVERGENCE 3, MEASURED: `1002937461 == '1002937461'` is False
    # in Python and True in SQL against a TEXT-affinity column.  REFUSED at the
    # service, so no downstream comparison ever meets the ambiguity.
    "order id numeric": ('{"schwab_order_id": 1002937461}',
                         (ENVELOPE_REFUSED, None, None)),

    "order id boolean": ('{"schwab_order_id": true}',
                         (ENVELOPE_REFUSED, None, None)),
    "order id an object": ('{"schwab_order_id": {"a": 1}}',
                           (ENVELOPE_REFUSED, None, None)),
    "order id an array": ('{"schwab_order_id": [1]}',
                          (ENVELOPE_REFUSED, None, None)),
    "symbol padded": (
        json.dumps({"schwab_order_id": ID,
                    "schwab_instrument_symbol": "  FTRE  "}),
        (ENVELOPE_REFUSED, None, None)),
    "symbol numeric": (
        json.dumps({"schwab_order_id": ID, "schwab_instrument_symbol": 7}),
        (ENVELOPE_REFUSED, None, None)),
    "duplicate order id, last null": (
        '{"schwab_order_id": "%s", "schwab_order_id": null}' % ID,
        (ENVELOPE_REFUSED, None, None)),
    "duplicate order id, last numeric": (
        '{"schwab_order_id": "%s", "schwab_order_id": 42}' % ID,
        (ENVELOPE_REFUSED, None, None)),
    "duplicate order id, both strings": (
        '{"schwab_order_id": "A", "schwab_order_id": "B"}',
        (ENVELOPE_REFUSED, None, None)),
    "duplicate order id, IDENTICAL values": (
        '{"schwab_order_id": "A", "schwab_order_id": "A"}',
        (ENVELOPE_REFUSED, None, None)),
    "duplicate symbol keys": (
        '{"schwab_instrument_symbol": "ZZZZ", '
        '"schwab_instrument_symbol": "FTRE"}',
        (ENVELOPE_REFUSED, None, None)),

    # ---------- THE WRONG-REFUSAL CONTROLS.  A canonicaliser that counted
    # NESTED keys, or that refused a document it merely could not decode, would
    # fail here -- and either would block the last_word ladder for a real fill.
    "a NESTED key of the same name": (
        json.dumps({"schwab_order_id": ID,
                    "raw": {"schwab_order_id": "unrelated"}}),
        (ENVELOPE_CANONICAL, ID, None)),
    "not an object": ('[1, 2, 3]', (ENVELOPE_CANONICAL, None, None)),
    "malformed JSON": ('{bad', (ENVELOPE_CANONICAL, None, None)),

    # ---------- DIVERGENCE 1, MEASURED: python json.loads ACCEPTS NaN and
    # sqlite json_valid REJECTS the whole document.  It is CANONICALISED at the
    # service -- the authority reads the order id and stores it -- and that is
    # sound now precisely because SQL never opens the document again.  The old
    # shape could not do this: the trigger read json_valid=0, saw no order, and
    # would have admitted a `last_word` downgrade for a latch-governed fill.
    "NaN elsewhere in the document": (
        '{"schwab_order_id": "%s", "x": NaN}' % ID,
        (ENVELOPE_CANONICAL, ID, None)),
    "Infinity elsewhere in the document": (
        '{"schwab_order_id": "%s", "x": Infinity}' % ID,
        (ENVELOPE_CANONICAL, ID, None)),
}


@pytest.mark.parametrize("label", sorted(_ENVELOPES))
def test_the_canonicaliser_reads_each_document_exactly_one_way(label) -> None:
    raw, expected = _ENVELOPES[label]
    identity = canonical_envelope_identity(raw)
    assert (identity.state, identity.broker_order_id,
            identity.instrument_symbol) == expected, label


def test_the_table_covers_all_three_measured_divergences() -> None:
    """The table's own discriminator.

    A verdict table is only worth its rows, and the three shapes that ended a
    ten-round loop are the rows that must never quietly leave it.
    """
    for needed in ("order id numeric", "order id padded, TAB",
                   "order id padded, NBSP", "NaN elsewhere in the document"):
        assert needed in _ENVELOPES, needed


@pytest.mark.parametrize("label", sorted(_ENVELOPES))
def test_a_refused_envelope_is_always_RECOGNISED(label) -> None:
    """SS-1's other half: the refusal must SUPPRESS, never fall through.

    A guard that refuses and then lets the caller run the ordinary chain is
    worse than no guard: the row lands with TODAY's candidate and nothing
    records that a mandate was named.  So every envelope the guard refuses
    must ALSO be one the shared recognition trigger claims.
    """
    raw, _expected = _ENVELOPES[label]
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
    identity = canonical_envelope_identity(deep)
    assert (identity.state, identity.broker_order_id) == (ENVELOPE_REFUSED,
                                                          None)


# ---------------------------------------------------------------------------
# THE CLOSURE CHECK, INVERTED -- and the inversion IS the ruling, encoded.
#
# It used to walk migration 0037 for every `json_extract(<a fills envelope>,
# '$.KEY')` and assert each KEY was one the canonicality guard covered.  That
# was the right check for the SHAPE THAT NO LONGER EXISTS: it presumed SQL
# would go on reading the document and only asked that the two domains agree
# about the same key set.  Ten review rounds proved the presumption unpayable.
#
# PERSIST-CANONICAL (CHARC + RD, 2026-08-26) removes the reading rather than
# aligning it, so the property to pin is the ABSENCE, and it is pinned by the
# same static walk that used to pin the roster.  Add ANY json_extract /
# json_valid / json_each / json_type over a fill's envelope back into the
# migration and this fails -- which is what makes the convention enforceable
# by something other than memory.
# ---------------------------------------------------------------------------
_SQL_READS_ENVELOPE = re.compile(
    r"json_(?:extract|valid|each|type)\(\s*(?:\w+\.)?schwab_source_value_json",
    re.S,
)
# The `swing/` tree, restricted to the two languages that can contain a SQL
# read of the envelope.  A hand-listed pair of files would be the roster this
# check exists to replace, so the walk enumerates the tree.
SWING_ROOT = REPO_ROOT / "swing"


def test_migration_0037_never_reads_a_fill_envelope() -> None:
    """SQL VERIFIES A FACT; IT MUST NEVER RE-DERIVE A JUDGMENT ACROSS AN
    ENGINE BOUNDARY (CHARC, adopting RD's sentence verbatim, 2026-08-26).

    The citation trigger consumes ``fill_envelope_identity`` -- the AUTHORITY'S
    persisted reading, bound to the exact document it was read from -- and
    compares stored values.  It parses nothing out of the operator's envelope.
    """
    hits = _SQL_READS_ENVELOPE.findall(
        MIGRATION_0037.read_text(encoding="utf-8"))
    assert not hits, (
        f"migration 0037 reads a fill's envelope in SQL ({len(hits)} site(s)); "
        "the twin must consume the authority's stored OUTPUT, never "
        "reimplement its reasoning -- three measured engine divergences say "
        "the mirror cannot be finished")


def test_no_sql_anywhere_in_swing_reads_a_fill_envelope() -> None:
    """The class, stated once and re-grepped across the WHOLE tree.

    Fixing an instance leaves the class live: the union scan in the ladder was
    a SECOND spelling of the trigger's question and it produced its own
    divergence (22A-R10-03, integer-vs-TEXT affinity) three rounds after the
    first one was fixed.  So the walk covers every ``.py`` and ``.sql`` under
    ``swing/`` rather than the two files anyone happens to remember.
    """
    offenders = {}
    for path in sorted(SWING_ROOT.rglob("*")):
        if path.suffix not in (".py", ".sql") or "__pycache__" in path.parts:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.lstrip()
            if stripped.startswith(("#", "--")):
                continue          # prose naming the forbidden form is not it
            if _SQL_READS_ENVELOPE.search(line):
                offenders.setdefault(
                    str(path.relative_to(REPO_ROOT)), []).append(line.strip())
    assert not offenders, (
        f"SQL reads a fill's envelope at {offenders}; the stored reading in "
        "fill_envelope_identity is the single derivation and every consumer "
        "compares it")


def test_the_walk_can_still_find_the_form_it_forbids() -> None:
    """The closure check's OWN discriminator.

    A regex that matched nothing would make both checks above vacuous while
    reading as guarantees -- the existence-is-not-completeness trap, arriving
    through a pattern that quietly stopped matching.  So the pattern is proved
    against the four spellings the migration used to contain, verbatim from
    its own pre-reshape text, plus one it must NOT match.
    """
    for form in (
        "json_extract(f.schwab_source_value_json, '$.schwab_order_id')",
        "json_valid(f.schwab_source_value_json)",
        "json_each(f.schwab_source_value_json) k",
        "json_type(f.schwab_source_value_json) = 'object'",
    ):
        assert _SQL_READS_ENVELOPE.search(form), form
    assert not _SQL_READS_ENVELOPE.search(
        "fei.envelope_raw = f.schwab_source_value_json"), (
        "the permitted form -- a plain TEXT equality against the stored "
        "reading's document -- must NOT be flagged, or the check forbids the "
        "shape the ruling prescribes")
