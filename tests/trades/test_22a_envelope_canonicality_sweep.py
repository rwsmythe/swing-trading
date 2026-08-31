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

import ast
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

    # ---------- AN UNDECODABLE DOCUMENT IS REFUSED, NOT CANONICAL (Codex
    # 22A-R11-01).  Under the OLD mirror shape the question was "do the two
    # engines agree", and for a document NEITHER could read the answer was yes
    # -- both read absence.  PERSIST-CANONICAL deleted the second engine, so
    # the question is now "can the AUTHORITY say what this document names",
    # and for an undecodable document it cannot.  Answering `canonical` with
    # both identities NULL makes an UNREADABLE prior consumer indistinguishable
    # from a document that genuinely names nothing, and rung 6 then reads
    # ignorance as evidence of ABSENCE.
    "malformed JSON": ('{bad', (ENVELOPE_REFUSED, None, None)),
    "a bare truncated array": ('[1, 2', (ENVELOPE_REFUSED, None, None)),

    # ---------- THE WRONG-REFUSAL CONTROLS.  A canonicaliser that counted
    # NESTED keys, or that refused a DECODABLE document naming no order, would
    # fail here -- and either would block the last_word ladder for a real fill.
    # `[1, 2, 3]` stays CANONICAL precisely because it DECODES: the authority
    # read it and it names nothing, which is a statement rather than a silence.
    "a NESTED key of the same name": (
        json.dumps({"schwab_order_id": ID,
                    "raw": {"schwab_order_id": "unrelated"}}),
        (ENVELOPE_CANONICAL, ID, None)),
    "not an object": ('[1, 2, 3]', (ENVELOPE_CANONICAL, None, None)),

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


def _sql_envelope_reads(text: str) -> list[int]:
    r"""1-based line numbers of every SQL read of a fill envelope in ``text``.

    THE WINDOW IS THE WHOLE BODY, NEVER THE LINE (Codex 22A-R12-04).  The
    predecessor iterated ``splitlines()`` and searched each line on its own, so
    a forbidden expression spelled across two lines -- ``json_extract(`` on one
    and the column on the next -- passed.  The pattern already carried ``re.S``
    and the ``\s*`` that make the split form matchable; only the per-line
    iteration prevented it from ever meeting one.

    COMMENT-ONLY LINES ARE BLANKED RATHER THAN DROPPED, so the reported line
    numbers stay true to the file while prose naming the forbidden form is
    still not a hit.  Blanking cannot HIDE an occurrence: a comment sitting
    inside a genuine split spelling leaves ``\s*`` matching across the blank,
    which ``_SPLIT_WITH_A_COMMENT_INSIDE`` asserts.

    RESIDUAL, STATED RATHER THAN LEFT TO LOOK COMPLETE: a forbidden form typed
    as a TRAILING comment on an otherwise-live line is still a hit, exactly as
    it was under the per-line rule.  That direction is a wrong REFUSAL -- loud,
    cheap and fixable at the offending line -- and the tree currently contains
    none, measured by this walk returning empty.
    """
    scrubbed = "\n".join(
        "" if line.lstrip().startswith(("#", "--")) else line
        for line in text.splitlines())
    return [scrubbed.count("\n", 0, m.start()) + 1
            for m in _SQL_READS_ENVELOPE.finditer(scrubbed)]


def test_migration_0037_never_reads_a_fill_envelope() -> None:
    """SQL VERIFIES A FACT; IT MUST NEVER RE-DERIVE A JUDGMENT ACROSS AN
    ENGINE BOUNDARY (CHARC, adopting RD's sentence verbatim, 2026-08-26).

    The citation trigger consumes ``fill_envelope_identity`` -- the AUTHORITY'S
    persisted reading, bound to the exact document it was read from -- and
    compares stored values.  It parses nothing out of the operator's envelope.
    """
    hits = _sql_envelope_reads(MIGRATION_0037.read_text(encoding="utf-8"))
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
        hits = _sql_envelope_reads(path.read_text(encoding="utf-8"))
        if hits:
            offenders[str(path.relative_to(REPO_ROOT))] = hits
    assert not offenders, (
        f"SQL reads a fill's envelope at {offenders} (path -> 1-based line "
        f"numbers); the stored reading in "
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


def _per_line_reads(text: str) -> list[int]:
    """The RETIRED per-line rule, kept as the discriminator's control.

    A regression test is worth nothing unless it distinguishes, so the
    superseded rule is measured beside the new one on the same input rather
    than described in a comment.
    """
    return [n for n, line in enumerate(text.splitlines(), 1)
            if not line.lstrip().startswith(("#", "--"))
            and _SQL_READS_ENVELOPE.search(line)]


_SPLIT_ACROSS_LINES = """         AND json_extract(
                 f.schwab_source_value_json,
                 '$.schwab_order_id') = l.broker_order_id
"""

_SPLIT_WITH_A_COMMENT_INSIDE = """         AND json_extract(
                 -- an innocent-looking note
                 f.schwab_source_value_json, '$.x')
"""


def test_the_walk_finds_a_forbidden_form_SPLIT_ACROSS_LINES() -> None:
    """THE EVASION THE WALK NOW CATCHES, AND IT USED TO PASS (22A-R12-04).

    The whole-tree check compiled its pattern with ``re.S`` and searched each
    source line SEPARATELY, so a forbidden expression spelled across two lines
    passed a check whose docstring promised it caught every SQL read.  Its own
    discriminator agreed, because the discriminator only ever offered it
    single-line spellings -- an instrument whose evasion case is untested is
    the same defect one level down.

    The retired rule is run on the SAME inputs below.  It finds NEITHER split
    spelling, so a revert to line iteration fails HERE rather than in some
    future reviewer's imagination; and both rules agree on the single-line
    spelling and on prose, so the change is a WIDENING and not a different
    check.
    """
    assert _sql_envelope_reads(_SPLIT_ACROSS_LINES) == [1]
    assert _sql_envelope_reads(_SPLIT_WITH_A_COMMENT_INSIDE) == [1]

    assert _per_line_reads(_SPLIT_ACROSS_LINES) == []
    assert _per_line_reads(_SPLIT_WITH_A_COMMENT_INSIDE) == []

    single = "AND json_valid(f.schwab_source_value_json)\n"
    assert _sql_envelope_reads(single) == _per_line_reads(single) == [1]

    prose = "-- json_extract(f.schwab_source_value_json, '$.schwab_order_id')"
    assert _sql_envelope_reads(prose) == _per_line_reads(prose) == []


# ---------------------------------------------------------------------------
# THE EXCEPTION-ROSTER CLOSURE CHECK (Codex 22A-R10-04)
#
# A HAND-ENUMERATED ROSTER IS THE SAME INSTRUMENT AS THE COUNT IT REPLACED.
# SS-2 stated this class -- enumerating the types ``json.loads`` can raise is a
# roster, and ``RecursionError`` is not on it -- then swept "the three envelope
# readers" and stopped at the service boundary.  The production ENTRY ROUTE was
# left on the roster and 500ed a money-bearing POST over an unreadable audit
# blob; the EXIT route, the D31 correction surface and the exit-envelope reader
# in the entry-form VM were all in the same state.
#
# So the fix is not the four sites.  It is this walk: every reader of a fill's
# envelope, anywhere in the declared envelope, found by following the ONE token
# that identifies such a reader, with its containment asserted rather than
# remembered.
# ---------------------------------------------------------------------------
_ENVELOPE_READER_ROOTS = (
    "swing/trades", "swing/data", "swing/cli.py", "swing/latches",
    "swing/web/routes/trades.py", "swing/web/view_models/trades.py",
)
_BROAD_CONTAINMENT = frozenset({"Exception", "BaseException"})


def _json_loads_in(stmts: list[ast.stmt]) -> bool:
    """Does this statement list parse JSON in its OWN body?

    Nested ``try`` subtrees are NOT descended into: an inner ``try`` carries
    its own containment, and charging the outer handler for it would flag
    correct code -- the false-positive direction a mechanical check cannot
    afford, because a check that cries wolf is one people learn to override.
    """
    stack: list[ast.AST] = list(stmts)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Try):
            continue
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "loads"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in ("json", "_json")):
            return True
        stack.extend(ast.iter_child_nodes(node))
    return False


def _is_broad(handler: ast.ExceptHandler) -> bool:
    """A bare ``except:`` or a single ``Exception`` / ``BaseException``.

    EVERYTHING ELSE IS A ROSTER, whatever its arity or spelling (Codex
    22A-R12-05).  The predecessor matched the literal text
    ``except (ValueError, TypeError)`` and its reversal and nothing else, so
    ``(ValueError, TypeError, RecursionError)``, ``(json.JSONDecodeError,
    TypeError)`` and a bare ``except ValueError`` all regressed the
    containment ruling undetected -- and its self-discriminator tested only
    the one spelling it recognised.  Asking the SHAPE instead of the SPELLING
    is what makes this a closure check rather than a longer roster: the fix
    for a hand-maintained list is never a better list.
    """
    if handler.type is None:
        return True
    return (isinstance(handler.type, ast.Name)
            and handler.type.id in _BROAD_CONTAINMENT)


def _roster_contained_loads(source: str) -> list[int]:
    """1-based line numbers of every ROSTER handler protecting a JSON parse.

    THE WINDOW IS THE ``try`` BODY, NOT THE FUNCTION.  A first version of this
    walk flagged any roster anywhere in a function that also parsed an envelope
    somewhere, and it produced two false positives on its first run -- a
    ``fromisoformat`` guard and a numeric-coercion guard, both correct.  The
    AST asks the question exactly: does THIS ``try`` parse JSON, and is THIS
    handler narrower than the class.
    """
    hits: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Try) or not _json_loads_in(node.body):
            continue
        hits += [h.lineno for h in node.handlers if not _is_broad(h)]
    return sorted(hits)


def _envelope_reader_files() -> list[Path]:
    out: list[Path] = []
    for root in _ENVELOPE_READER_ROOTS:
        path = REPO_ROOT / root
        if path.is_file():
            out.append(path)
            continue
        out += [f for f in path.rglob("*.py") if "__pycache__" not in f.parts]
    return sorted(set(out))


def test_no_fill_envelope_reader_is_contained_by_a_TYPE_ROSTER() -> None:
    """Every function in the declared envelope that names
    ``schwab_source_value_json`` and parses JSON must contain its decode
    failure by CLASS, not by an enumerated tuple of types.

    The scope is deliberately the ENVELOPE READERS and not every
    ``json.loads`` in the tree: a reader of a blob THIS FRAMEWORK produced with
    ``json.dumps`` cannot be handed a 20000-deep document by an operator, and
    widening the sweep to those would be defensive dead code (the
    Expansion-#13 cascade).  The other such sites are enumerated in the return
    report with their blob source rather than silently swept.
    """
    offenders: dict[str, list[int]] = {}
    for f in _envelope_reader_files():
        source = f.read_text(encoding="utf-8")
        hits = _roster_contained_loads(source)      # REAL line numbers
        if not hits:
            continue
        # The FUNCTION-sized window: a module may legitimately parse other
        # blobs, and only the functions that touch a fill envelope are in
        # scope.  A function's span contains any nested function, so an inner
        # reader inherits the outer's scope rather than escaping it.
        in_scope = [
            fn for fn in ast.walk(ast.parse(source))
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
            and "schwab_source_value_json" in (
                ast.get_source_segment(source, fn) or "")
        ]
        for lineno in hits:
            if any(fn.lineno <= lineno <= (fn.end_lineno or fn.lineno)
                   for fn in in_scope):
                offenders.setdefault(
                    str(f.relative_to(REPO_ROOT)), []).append(lineno)
    assert not offenders, (
        f"a fill-envelope reader still enumerates its decode failures: "
        f"{offenders}. `json.loads` raises `RecursionError` -- a "
        f"`RuntimeError` -- on a deeply nested document, and neither arm of "
        f"that tuple catches it")


# The entry route's PRE-FIX text, verbatim, wrapped so it parses.  It 500ed a
# money-bearing POST over an unreadable audit blob, which is why it is the
# walk's true positive rather than an invented one.
_TRUE_POSITIVE = """
def _entry_form_vm(row):
    schwab_source_value_json = row["schwab_source_value_json"]
    try:
        anchor_envelope = _json.loads(schwab_source_value_json)
    except (ValueError, TypeError):
        anchor_envelope = None
    return anchor_envelope
"""

# The two guards the FIRST version of this walk wrongly flagged.  Both are real
# code from the same two files, both correct, and both sit in functions that
# also read a fill envelope -- which is exactly why a function-sized window was
# the wrong instrument and the try body is the right one.
_A_DATE_GUARD = """
def _exit_form(row):
    envelope = json.loads(row["schwab_source_value_json"] or "{}")
    exit_date_ok = True
    try:
        _date_cls.fromisoformat(v_exit_date)
    except (TypeError, ValueError):
        exit_date_ok = False
    return envelope, exit_date_ok
"""

_A_NUMERIC_GUARD = """
def _fill_rows(rows):
    out = []
    for row in rows:
        envelope = json.loads(row["schwab_source_value_json"] or "{}")
        try:
            out.append(float(row["fill_qty"]))
        except (TypeError, ValueError):
            continue
    return out, envelope
"""

# EVERY ONE OF THESE EVADED THE RETIRED REGEX (Codex 22A-R12-05), and each is a
# real regression of the containment ruling: `json.loads` raises
# `RecursionError` -- a `RuntimeError` -- on a deeply nested document, and no
# member of any of these rosters catches it.
_EVASIONS = {
    "a THREE-member tuple": "except (ValueError, TypeError, RecursionError):",
    "a REORDERED three-member tuple":
        "except (TypeError, RecursionError, ValueError):",
    "a QUALIFIED name": "except (json.JSONDecodeError, TypeError):",
    "a SINGLE narrow name": "except ValueError:",
    "a FOUR-member tuple":
        "except (ValueError, TypeError, KeyError, AttributeError):",
}

# The retired rule, kept as the control so the change is measured and not
# merely asserted.
_RETIRED_TYPE_ROSTER = re.compile(
    r"^\s*except \((?:ValueError, TypeError|TypeError, ValueError)\)")


def _lineno_of(source: str, needle: str) -> int:
    for n, line in enumerate(source.splitlines(), 1):
        if needle in line:
            return n
    raise AssertionError(f"{needle!r} is not in the snippet")


def test_the_roster_walk_finds_the_form_it_forbids_and_only_that_form(
) -> None:
    """The walk's OWN discriminator, over the REAL shapes it met.

    The true positive is the entry route's pre-fix text.  The two false
    positives are the guards the first version of this walk wrongly flagged.
    """
    assert _roster_contained_loads(_TRUE_POSITIVE) == [
        _lineno_of(_TRUE_POSITIVE, "except (ValueError, TypeError):")]

    fixed = _TRUE_POSITIVE.replace(
        "except (ValueError, TypeError):", "except Exception:")
    assert _roster_contained_loads(fixed) == []

    assert _roster_contained_loads(_A_DATE_GUARD) == []
    assert _roster_contained_loads(_A_NUMERIC_GUARD) == []
    assert _envelope_reader_files(), "the file walk found nothing to check"


@pytest.mark.parametrize("label", sorted(_EVASIONS))
def test_the_roster_walk_catches_EVERY_spelling_of_a_roster(label) -> None:
    """AN INSTRUMENT WHOSE EVASION CASE IS UNTESTED IS THE SAME DEFECT ONE
    LEVEL DOWN (Codex 22A-R12-05).

    The retired rule recognised exactly two spellings, so a roster could be
    widened, reordered, qualified or narrowed to a single name and regress the
    containment ruling while a discriminator audit read green.  Each spelling
    below is asserted BOTH ways: the AST walk finds it, and the retired regex
    does NOT -- which is what makes this a regression test rather than a
    restatement.
    """
    handler = _EVASIONS[label]
    source = _TRUE_POSITIVE.replace("except (ValueError, TypeError):", handler)
    assert _roster_contained_loads(source) == [_lineno_of(source, handler)], (
        f"{label} evaded the closure walk")
    assert not _RETIRED_TYPE_ROSTER.match("        " + handler), (
        f"{label} is not an evasion of the RETIRED rule, so this case does "
        f"not distinguish the fix from what it replaced")


def test_the_retired_regex_DID_recognise_the_one_spelling_it_knew() -> None:
    """The control on the control.

    If the retired pattern matched nothing at all, every assertion above would
    pass vacuously and the parametrized family would read as five proofs while
    carrying none.
    """
    assert _RETIRED_TYPE_ROSTER.match("        except (ValueError, TypeError):")
    assert _RETIRED_TYPE_ROSTER.match("    except (TypeError, ValueError):")


# ---------------------------------------------------------------------------
# 22A-R13-01 -- THE AUTHORITY MUST NOT CERTIFY A DOCUMENT IT NEVER READ
#
# `envelope_is_canonical` answered `True` for ANY non-`str`, on the ground that
# "no envelope means nothing to disagree about".  That ground is TRUE OF `None`
# and of a blank string and FALSE of a value of the wrong TYPE: a BLOB bound
# into the TEXT column `fills.schwab_source_value_json` comes back as `bytes`
# (SQLite does not enforce column affinity, and there is no
# `typeof(...) = 'text'` CHECK anywhere in the migrations -- measured), the
# readers return `None` for it, and the identity persisted was
# `('canonical', NULL, NULL)`: "I read this document and it names no order",
# recorded for a document the authority never opened.
#
# It is 22A-R11-01's class -- IGNORANCE MUST NOT BE RECORDED AS ABSENCE --
# arriving on the WRONG-TYPE branch, which R11-01's merge of the two decode
# branches left answering `canonical`.  Direction: WRONG ACCEPTANCE.
# ---------------------------------------------------------------------------
_BLOB_DOC = json.dumps({"schwab_order_id": ID, "schwab_instrument_symbol":
                        "FTRE"})


def test_a_TEXT_column_really_does_return_a_BLOB_as_bytes() -> None:
    """THE PREMISE, MEASURED HERE rather than asserted in a comment.

    If SQLite ever began enforcing TEXT affinity the finding would be
    schema-prevented and the guard below would be defensive dead code, so the
    premise is a row of its own and fails loudly if it stops holding.
    """
    import sqlite3
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t (v) VALUES (?)", (_BLOB_DOC.encode(),))
        value, kind = conn.execute("SELECT v, typeof(v) FROM t").fetchone()
    finally:
        conn.close()
    assert kind == "blob"
    assert isinstance(value, bytes)
    assert value == _BLOB_DOC.encode()


@pytest.mark.parametrize("raw", [
    pytest.param(_BLOB_DOC.encode(), id="bytes-naming-an-order"),
    pytest.param(b"{}", id="bytes-naming-nothing"),
    pytest.param(bytearray(_BLOB_DOC.encode()), id="bytearray"),
    pytest.param(memoryview(_BLOB_DOC.encode()), id="memoryview"),
    pytest.param(1002937461, id="int"),
    pytest.param({"schwab_order_id": ID}, id="an-already-parsed-dict"),
])
def test_an_UNREADABLE_TYPE_is_REFUSED_not_certified(raw) -> None:
    """PRE-FIX every row here returned `True` and persisted
    `('canonical', None, None)` -- MEASURED on the bytes row, whose same bytes
    as a `str` yield `('canonical', '1002937461', 'FTRE')`.

    POST-FIX the authority says what is true: it could not read this, so it
    refuses, and the ladder's three-valued rule turns the refusal into an
    honest-unset entry rather than into today's candidate.
    """
    assert envelope_is_canonical(raw) is False
    identity = canonical_envelope_identity(raw)
    assert (identity.state, identity.broker_order_id,
            identity.instrument_symbol) == (ENVELOPE_REFUSED, None, None)


@pytest.mark.parametrize("raw", [
    pytest.param(None, id="None"),
    pytest.param("", id="empty-string"),
    pytest.param("   \t\n", id="whitespace-only"),
])
def test_a_GENUINE_ABSENCE_still_passes_and_that_bounds_the_fix(raw) -> None:
    """THE OVER-REFUSAL CONTROL, and it is what keeps the fix three lines wide.

    Every pre-22-A fill has NO envelope, and the whole `last_word` ladder
    depends on that state passing.  A fix that refused `None` would refuse the
    entire journal -- a wrong REFUSAL manufactured by the guard, which is the
    failure mode this arc has now met on four separate rosters.
    """
    assert envelope_is_canonical(raw) is True
    identity = canonical_envelope_identity(raw)
    assert (identity.state, identity.broker_order_id,
            identity.instrument_symbol) == (ENVELOPE_CANONICAL, None, None)
