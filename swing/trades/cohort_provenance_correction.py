"""Demand C -- the audited cohort-key provenance-correction surface.

Writes the three cohort keys -- ``trades.hypothesis_label``,
``trades.candidate_id``, ``trades.trade_origin`` -- on ONE trade, deriving
every written value from a STRUCTURALLY CITED pair of contemporaneous pipeline
records, and recording the correction in ``provenance_corrections``, whose
schema refuses a correction without its citation.

**RD's evidence rule is the binding constraint.** A cohort key may be written
only from the framework's OWN contemporaneous record. Two consequences shape
every line below: the operator supplies no VALUE (only two row ids and a
reason, so free-typing is unrepresentable rather than refused), and no value
may be COMPOSED from sibling rows -- reading trades 17/18's clean
``'A+ baseline (aplus)'`` off the cohort would be a cohort VOTE, which is why
this surface writes the label the FRAMEWORK's own builder produces for the
CITED candidate, suffix and all.

THE PLAN-WIDE SELECTION RULE (found at three separate sites over three review
rounds, so it is stated once and applied everywhere): **no SQL predicate here
may filter, order or limit on an unconstrained TEXT timestamp.** Every
timestamp this module reads -- ``evaluation_runs.run_ts`` /
``action_session_date``, ``daily_recommendations.action_session_date``,
``fills.fill_datetime``, ``pipeline_runs.finished_ts``,
``hypothesis_status_history.effective_from`` / ``effective_to`` /
``recorded_at`` -- is bare ``TEXT``. A lexical comparison over one of those
does not order them by time, and worse, a malformed row that a
``WHERE``/``ORDER BY``/``LIMIT`` excludes NEVER REACHES THE VALIDATOR. Verified
on the production shapes: ``'2026-08-12T16:00:00' < '20260811T160000'`` is
True, so ``get_authoritative_entry_fill``'s ``ORDER BY fill_datetime ASC LIMIT
1`` returns the LATER row as "earliest" when a schema-legal basic-form row
exists -- handing the gate a day-later, MORE PERMISSIVE anchor. So: LOAD all
candidate rows unfiltered, VALIDATE every timestamp on every loaded row,
REFUSE the whole operation on any malformed one, THEN filter, order and select
in Python on PARSED values.

Transaction contract (CLAUDE.md): the outer function ALWAYS owns
``BEGIN IMMEDIATE`` / COMMIT / ROLLBACK and REJECTS a caller-held transaction
-- never auto-detects, because an auto-detect guard re-introduces the race the
explicit lock closed. The inner never commits, so a future flow can compose it
under a SAVEPOINT.
"""
from __future__ import annotations

import contextlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from swing.data.models import (
    PROVENANCE_CORRECTED_FIELDS,
    PROVENANCE_CORRECTION_APPLIED_BY,
    ProvenanceCorrection,
)
from swing.data.repos.candidates import (
    fetch_candidate_by_id,
    get_evaluation_run_by_id,
)
from swing.data.repos.recommendations import get_daily_recommendation_by_id
from swing.data.repos.trades import get_trade
from swing.evaluation.dates import PIPELINE_LOCAL_TIMEZONE, is_trading_session

__all__ = [
    "APLUS_BUCKET",
    "COHORT_CORRECTED_FIELDS",
    "DERIVATION_RULE_DEPENDENCIES",
    "DERIVATION_RULE_HISTORY",
    "DERIVATION_RULE_SOURCE_SHA256",
    "DERIVATION_RULE_VERSION",
    "REQUIRED_RECOMMENDATION",
    "UNSET_TRADE_ORIGIN",
    "CallerHeldTransactionError",
    "CohortProvenanceCorrectionError",
    "CohortProvenanceCorrectionPreview",
    "CohortProvenanceCorrectionResult",
    "ProvenanceCorrectionReport",
    "correct_cohort_provenance",
    "preview_cohort_provenance_correction",
    "read_provenance_corrections",
]

# The manifest of what ONE correction touches -- imported from `models.py`
# rather than re-spelled, so there is exactly one copy (#11).
COHORT_CORRECTED_FIELDS: tuple[str, ...] = PROVENANCE_CORRECTED_FIELDS

# `bucket='aplus'` is the BOUNDARY OF WHAT IS DERIVABLE, not a convenience
# restriction. `origin.py:69-72` maps `watch` to `pipeline_watch_hyp_recs` OR
# `pipeline_watch_manual` according to `entry_path`, and `entry_path` is an
# in-process enum persisted NOWHERE -- so for a watch candidate the framework's
# own record cannot say which origin is true and a correction would have to
# COMPOSE the value. Only `aplus` is a total function of the persisted row.
APLUS_BUCKET = "aplus"

# A `near_trigger` row says "watching, approaching"; it is not the framework
# recording a DECISION for that session, and 58 of the 182 live DR rows (every
# one a `near_trigger`) have no candidate row in their own run at all.
REQUIRED_RECOMMENDATION = "today_decision"

# The state all three cohort keys must currently be in. This surface FILLS
# empty provenance; it does not re-decide provenance the framework recorded.
UNSET_TRADE_ORIGIN = "manual_off_pipeline"

# The ±24h band around either window bound inside which a wrong-by-hours zone
# conversion could flip the verdict. A naive stamp carries no zone and nothing
# records where the box was when it was written, so inside the band the honest
# answer is to decline rather than to guess.
CLOCK_MARGIN = timedelta(hours=24)


def _applied_at_now() -> str:
    """The audit stamp, taken by THIS surface and by nobody else."""
    from swing.trades.reconciliation_auto_correct import _utc_now_iso_ms

    return _utc_now_iso_ms()


# The seam a test patches for determinism. It is a module attribute rather
# than a parameter precisely so it is not part of the PUBLIC surface: an audit
# time a caller can supply is an audit time a caller can falsify.
_APPLIED_AT_CLOCK = _applied_at_now

# The EXACT naive-ISO grammar every timestamp this module reads must satisfy:
# `YYYY-MM-DDTHH:MM:SS` with an optional fractional part, a LITERAL `T`, no
# offset, no `Z`, and no surrounding whitespace. Anchored at both ends.
_NAIVE_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?$")

# An offset or `Z` suffix, detected SEPARATELY so it earns its own
# unsupported-representation message rather than a generic grammar one.
_OFFSET_SUFFIX_RE = re.compile(r"([Zz]|[+-]\d{2}:?\d{2})$")

# THE DERIVATION RULE, PINNED RATHER THAN PROMISED.
#
# `_descriptive_label`'s format and `_non_pass_criterion_names`'s
# `na`-counts-as-non-pass semantics are CODE, not data, so no FK can anchor
# them. A version constant that "is bumped by hand when either changes" would
# be gotcha #31 -- an unenforceable promise about future discipline, and
# `_descriptive_label`'s own docstring even invites the drift ("the descriptive
# suffix may evolve"). Two corrections would then claim the same derivation
# version while using different rules.
#
# So the version is paired with a sha256 of both functions' SOURCE, asserted by
# a test. Changing either function fails that test until the hash AND the
# version move in the same commit. This is the project's own idiom -- the H1
# amendment text is pinned by sha256 for exactly this reason.
# A CHECKED-IN (version, digest) HISTORY, not a bare pair (Codex R2 Minor 6).
# A lone constant plus a lone digest lets a maintainer change the builder and
# update ONLY the digest -- the test goes green while two different rules share
# one audit version, which is the exact failure the pin was added to prevent.
# The history is append-only and both columns are asserted UNIQUE, so a new
# digest can only be recorded alongside a NEW version.
#
# AND IT COVERS EVERY FUNCTION THAT DECIDES THE STORED VALUE (Codex R4 Major
# 4). The first digest covered only `_descriptive_label` and
# `_non_pass_criterion_names` -- but the written label ALSO passes through
# `canonicalize_hypothesis_label`, and WHICH hypothesis is selected comes from
# `match_candidate_to_hypotheses` and the `_aplus_baseline_match` predicate.
# Changing the canonicalizer could therefore change every stored label while
# the pin stayed green and new corrections kept claiming the same version.
# That is REACHABLE AFTER A ROUTINE CODE UPGRADE, which is the one class a pin
# like this exists for.
# AND ITS SHAPE IS A DEPENDENCY MANIFEST, NOT A FUNCTION LIST (Codex R5 Major
# 4). This pin has now been widened three times -- functions, then selection
# and canonicalization, then the CONSTANTS those functions read -- and a
# fourth widening would be the wrong move: hashing function SOURCE cannot see
# a value the source merely NAMES, so `H_APLUS_BASELINE` could be re-spelled,
# selecting a different registry row, without moving the digest by one bit.
# The manifest makes the dependency set an EXPLICIT, EDITABLE ROSTER.
#
# AND THAT WAS NOT ENOUGH ON ITS OWN. Its first outing shipped with TWO HOLES:
# `_derive` -- the function that SELECTS the match and CONSTRUCTS the stored
# label -- was absent, and so were three of the sibling matcher predicates. A
# routine upgrade to `_derive`'s label transformation, or to an omitted
# predicate such that a different hypothesis becomes the sole match, would
# change the written label while the digest stayed put, and the audit row
# would claim a rule version it no longer implements. No raw write required.
#
# THE LESSON IS NOT A LONGER LIST. A hand-enumerated roster is the same
# instrument as the count it replaced and it fails the same way: the feeling of
# having swept is identical to having swept. So this roster is paired with a
# CLOSURE CHECK (`tests/trades/test_cohort_provenance_derivation.py`) that
# walks what `_derive` actually depends on and fails unless every swing-local
# function and constant it reaches is EITHER here OR on an exclusion list with
# a stated reason. A fifth omission fails loudly instead of shipping.
#
# `_derive` IS HASHED WHOLESALE, AND THE NOISE IS ACCEPTED DELIBERATELY
# (coordinator-ruled). Its source contains refusal messages, so a cosmetic
# wording edit moves the digest and forces a version bump that nothing
# semantic required. That is a FALSE ALARM and it is the correct trade:
# fail-closed matches RD's governing asymmetry on this arc -- a wrong refusal
# costs a legible message and a human escalation, a wrong acceptance
# contaminates H1 invisibly and permanently. DO NOT "fix" the noise by
# narrowing the hash to part of the function; that reintroduces exactly the
# hole this widening closed.
DERIVATION_RULE_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    # THE ROOT: selection + label construction happen here.
    ("function", "swing.trades.cohort_provenance_correction:_derive"),
    # Label construction.
    ("function", "swing.recommendations.hypothesis:_descriptive_label"),
    ("function", "swing.recommendations.hypothesis:_non_pass_criterion_names"),
    ("function", "swing.trades.entry:canonicalize_hypothesis_label"),
    # SELECTION -- the matcher and EVERY predicate it consults. Any one of
    # them becoming true or false for a candidate changes which hypothesis is
    # the sole match, and therefore the label's name component.
    ("function",
     "swing.recommendations.hypothesis:match_candidate_to_hypotheses"),
    ("function", "swing.recommendations.hypothesis:_aplus_baseline_match"),
    ("function",
     "swing.recommendations.hypothesis:_near_aplus_extension_match"),
    ("function",
     "swing.recommendations.hypothesis:_sub_aplus_vcp_not_formed_match"),
    ("function", "swing.recommendations.hypothesis:_capital_blocked_match"),
    ("function",
     "swing.recommendations.hypothesis:_broad_watch_baseline_match"),
    # THE AS-OF REGISTRY. These decide which hypotheses are ACTIVE as of the
    # cited record, and the matcher filters on exactly that -- so they decide
    # the selection as surely as the predicates do.
    ("function",
     "swing.trades.cohort_provenance_correction:_load_validated_intervals"),
    ("function", "swing.trades.cohort_provenance_correction:_as_of_status"),
    ("function",
     "swing.trades.cohort_provenance_correction"
     ":_assert_contemporaneous_interval"),
    ("function",
     "swing.trades.cohort_provenance_correction"
     ":_assert_outside_the_clock_margin"),
    ("function", "swing.trades.cohort_provenance_correction:_to_utc_naive"),
    ("function",
     "swing.trades.cohort_provenance_correction:_require_naive_datetime"),
    # The readers that supply the registry rows, the intervals and the window
    # bound. Their column rosters and row mappers decide what the matcher
    # sees.
    ("function", "swing.data.repos.hypothesis:list_hypotheses"),
    ("function", "swing.data.repos.hypothesis:_row_to_entry"),
    ("function",
     "swing.data.repos.hypothesis_status_history:list_history_for_hypothesis"),
    ("function", "swing.data.repos.hypothesis_status_history:_row_to_model"),
    ("function", "swing.data.repos.pipeline:evaluation_run_persistence_bound"),
    # The hypothesis NAMES decide WHICH registry row the matcher selects and
    # which name the label carries.
    ("constant", "swing.recommendations.hypothesis:H_APLUS_BASELINE"),
    ("constant", "swing.recommendations.hypothesis:H_NEAR_APLUS_EXTENSION"),
    ("constant", "swing.recommendations.hypothesis:H_SUB_APLUS_VCP"),
    ("constant", "swing.recommendations.hypothesis:H_CAPITAL_BLOCKED"),
    ("constant", "swing.recommendations.hypothesis:H_BROAD_WATCH_BASELINE"),
    # The defensible-miss set is a matcher input with a default.
    ("constant",
     "swing.recommendations.hypothesis:DOCTRINE_DEFENSIBLE_MISS_SET"),
    # The SELECT column rosters the row mappers index positionally.
    ("constant", "swing.data.repos.hypothesis:_SELECT_COLUMNS"),
    ("constant",
     "swing.data.repos.hypothesis_status_history:_SELECT_COLUMNS"),
    # The clock inputs to the as-of window.
    ("constant", "swing.trades.cohort_provenance_correction:CLOCK_MARGIN"),
    ("constant",
     "swing.trades.cohort_provenance_correction:PIPELINE_LOCAL_TIMEZONE"),
    # And the two values this surface itself writes.
    ("constant", "swing.metrics.funnel:APLUS_TRADE_ORIGIN"),
    ("constant", "swing.trades.cohort_provenance_correction:APLUS_BUCKET"),
)


def derivation_rule_digest() -> str:
    """sha256 over the ENUMERATED dependency manifest.

    Functions contribute their SOURCE; constants contribute a CANONICAL
    rendering. Both are keyed by their fully-qualified spec, so re-pointing a
    name is a change even when the value is unchanged.

    THE CANONICAL RENDERING IS NOT `repr`, AND THE PIN TEST I WROTE FOR THIS
    FIX CAUGHT IT ON ITS FIRST RUN. `repr(frozenset)` follows SET ITERATION
    ORDER, which for `str` elements depends on PYTHONHASHSEED and therefore
    VARIES BETWEEN PROCESSES -- `DOCTRINE_DEFENSIBLE_MISS_SET` printed two
    different orders across three subprocesses, and the digest came out
    different on three of four runs. A digest built on `repr` would have been a
    FLAKY pin: green locally, red intermittently in CI, and the fix a
    maintainer reaches for under that pressure is to WEAKEN the assertion --
    which would have quietly retired the guard. Sets and dicts are sorted
    before rendering, so the digest is a function of the VALUE and not of the
    run.
    """
    import hashlib
    import importlib
    import inspect

    def _canonical(obj: Any) -> str:
        if isinstance(obj, (set, frozenset)):
            return f"{type(obj).__name__}({sorted(map(repr, obj))!r})"
        if isinstance(obj, dict):
            return repr(sorted((repr(k), repr(v)) for k, v in obj.items()))
        return repr(obj)

    parts: list[str] = []
    for kind, spec in DERIVATION_RULE_DEPENDENCIES:
        module_name, attr = spec.split(":")
        obj = getattr(importlib.import_module(module_name), attr)
        body = inspect.getsource(obj) if kind == "function" else _canonical(obj)
        parts.append(f"{kind}\x1f{spec}\x1f{body}")
    return hashlib.sha256("\x1e".join(parts).encode("utf-8")).hexdigest()


DERIVATION_RULE_HISTORY: tuple[tuple[str, str], ...] = (
    # 2026-08-12.1 pinned only the two label functions; superseded rather than
    # edited, so the append-only property the history exists for is kept.
    ("2026-08-12.1",
     "5d00449acd1f16cc2b6626e843044f76118710a736790a8a506806500df9d878"),
    ("2026-08-13.1",
     "9bdb95d1877a02777dac1284e766db932299e1e44ed934c6b5b7a2d3eca18099"),
    ("2026-08-13.2",
     "29f5748aa00db73c13304152aae85f7c027b77307cb90f326b1e033c58a43692"),
    # 2026-08-13.3 closes the two holes the manifest shipped with -- `_derive`
    # itself and the sibling matcher predicates -- and adds the as-of registry
    # machinery and the readers that feed it. Appended, never edited.
    ("2026-08-13.3",
     "8b994668acfdccf758bb1e050f1728cfddc7beed330406edb3a071b2819a14a4"),
)
DERIVATION_RULE_VERSION: str = DERIVATION_RULE_HISTORY[-1][0]
DERIVATION_RULE_SOURCE_SHA256: str = DERIVATION_RULE_HISTORY[-1][1]


class CohortProvenanceCorrectionError(ValueError):
    """Any refusal from this surface.

    A ``ValueError`` so the CLI boundary's existing
    ``except ValueError -> ClickException`` discipline applies. Every message
    ends with "Nothing was written."
    """


class CallerHeldTransactionError(CohortProvenanceCorrectionError):
    """The outer function was called with a transaction already open."""


def _refuse(message: str) -> CohortProvenanceCorrectionError:
    return CohortProvenanceCorrectionError(f"{message} Nothing was written.")


# ---------------------------------------------------------------------------
# Canonical validation. EVERY value the DECISION reads passes through here --
# not merely every value the OPERATOR cited. Scoping validation to the cited
# rows was two-thirds of a guard: a hidden malformed COMPETITOR is exactly how
# the last-word guard gets fooled.
# ---------------------------------------------------------------------------


def _require_session_date(raw: Any, *, what: str) -> _date:
    """An EXTENDED-form ISO date that is an NYSE TRADING SESSION.

    Parsing is not enough. `action_session_for_run` always derives an NYSE
    session, so a non-session anchor CANNOT come from the real emitter and its
    presence is corruption rather than an edge case -- yet
    `action_session_date='2026-08-09'` is a Sunday that parses cleanly,
    round-trips, and satisfies `<= F` against a Monday fill. Manufacturing a
    contemporaneity verdict from it violates the binding rule as squarely as a
    mis-parsed date does.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise _refuse(f"{what} is missing or not a string ({raw!r}).")
    # NOT STRIPPED (Codex R1 Major 2). Stripping would make the anchor COLUMN
    # hold a canonicalized value while the frozen SNAPSHOT holds the raw one,
    # and the 0036 CHECK compares the two -- preview says GO, apply dies at the
    # INSERT. A surrounding-whitespace value is refused, not repaired.
    value = raw
    if value != value.strip():
        raise _refuse(
            f"{what} {value!r} carries surrounding whitespace. It is REFUSED "
            "rather than canonicalized: the anchor column would hold the "
            "trimmed value while the frozen snapshot holds the raw one, and "
            "the audit CHECK compares them."
        )
    try:
        parsed = _date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise _refuse(
            f"{what} {value!r} is not a parseable ISO date. The column is a "
            "bare TEXT column, so a malformed value is schema-legal; this "
            "surface refuses to compute a contemporaneity verdict from one."
        ) from exc
    if parsed.isoformat() != value:
        raise _refuse(
            f"{what} {value!r} is not EXTENDED-format YYYY-MM-DD (it parses "
            f"to {parsed.isoformat()}). A basic or week-date form is refused "
            "rather than silently canonicalized, because every downstream "
            "[:10] prefix and lexical comparison reads the stored string."
        )
    if value[:4] < "1900":
        raise _refuse(
            f"{what} {value} is before 1900; the audit schema refuses it.")
    if not is_trading_session(parsed):
        raise _refuse(
            f"{what} {value} is not an NYSE trading session. "
            "`action_session_for_run` always derives one, so a non-session "
            "anchor cannot have come from the real emitter -- its presence is "
            "corruption, not an edge case."
        )
    return parsed


def _require_naive_datetime(raw: Any, *, what: str) -> datetime:
    """A whole, parseable, EXTENDED-form, OFFSET-FREE ISO datetime.

    Offset-bearing and `Z`-suffixed values are REFUSED, not converted. A
    `[:10]` prefix is a UTC-or-naive calendar prefix, not an exchange session:
    a `2026-08-13T00:30:00Z` fill is the 2026-08-12 ET session, and taking the
    prefix would set the anchor one day LATE -- i.e. MORE PERMISSIVE, accepting
    a citation the correct anchor refuses. Converting would import a whole
    correctness surface into an arc with no other need of it, so the shape is
    named UNSUPPORTED and routed out. Item 5 takes the same posture for its own
    after-hours UTC-residue case.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise _refuse(f"{what} is missing or not a string ({raw!r}).")
    value = raw
    # THE EXACT EMITTER GRAMMAR, NOT MERELY "PARSEABLE" (Codex R1 Major 2).
    # `datetime.fromisoformat` accepts `2026-08-10`, `2026-08-10T17`, and
    # `2026-08-10 17:30:26`, and EVERY ONE of those passes a date-prefix check:
    # a date-only `run_ts` becomes MIDNIGHT and widens the hypothesis-status
    # window by hours, producing an authorization verdict from a timestamp
    # whose actual time is unknown. A space separator additionally breaks the
    # audit row's own lexical ordering CHECK, because ' ' (0x20) sorts before
    # 'T' (0x54). And stripping would split the anchor column from the frozen
    # snapshot the CHECK compares it to. So the grammar is asserted directly.
    #
    # The four live production shapes all satisfy it: fills / evaluation_runs /
    # pipeline_runs use `...T16:00:00` (19 chars) and
    # `hypothesis_status_history` uses the millisecond form
    # `2026-04-25T00:00:00.000` (23). A round-TRIP would wrongly refuse the
    # last -- `datetime.fromisoformat('...T00:00:00.000').isoformat()` drops
    # the `.000` -- which is why this is a grammar assertion, not a round-trip.
    # The OFFSET / `Z` case gets its own message FIRST, because it is a NAMED
    # unsupported REPRESENTATION rather than corruption: an offset-bearing
    # Schwab execution stamp is a real production shape elsewhere in this
    # codebase, and the operator needs to be told it is out of scope and
    # routable, not that his data is malformed.
    if _OFFSET_SUFFIX_RE.search(value):
        raise _refuse(
            f"{what} {value!r} carries a UTC offset or a Z suffix. That "
            "representation is UNSUPPORTED by this surface rather than "
            "silently mis-dated: its [:10] prefix is a calendar prefix, not an "
            "exchange session, and anchoring on it would land one session LATE "
            "-- i.e. more permissive. Route it to CHARC."
        )
    if not _NAIVE_ISO_RE.match(value):
        raise _refuse(
            f"{what} {value!r} is not a canonical naive ISO datetime "
            "(YYYY-MM-DDTHH:MM:SS with optional fractional seconds, a LITERAL "
            "'T', no offset, no 'Z', no surrounding whitespace). The column is "
            "a bare TEXT column, so a truncated, space-separated or "
            "offset-bearing value is schema-legal -- and a date-only value "
            "would silently be read as MIDNIGHT."
        )
    # THE 1900 FLOOR (Codex R4 Major 1). The audit schema refuses a pre-1900
    # timestamp, so accepting one HERE would let a dry run approve an apply
    # that necessarily dies at the INSERT -- the preview/apply divergence this
    # whole validator exists to prevent, arriving through a bound the two
    # layers did not share.
    if value[:4] < "1900":
        raise _refuse(
            f"{what} {value!r} is before 1900. The audit schema refuses it, so "
            "authorizing on it would approve a correction that cannot be "
            "recorded."
        )
    # Hour 24: `fromisoformat` ACCEPTS it and NORMALISES to the next day, so a
    # stamp would silently move by a calendar day.
    if value[11:13] > "23":
        raise _refuse(
            f"{what} {value!r} carries hour {value[11:13]}; no clock produced "
            "that time and parsing it would silently roll the stamp to the "
            "next day."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise _refuse(
            f"{what} {value!r} matches the ISO shape but is not a real "
            "datetime (an impossible day, month or time)."
        ) from exc
    if parsed.tzinfo is not None:  # pragma: no cover -- the regex forbids it
        raise _refuse(
            f"{what} {value!r} carries a UTC offset or a Z suffix. That "
            "representation is UNSUPPORTED by this surface rather than "
            "silently mis-dated: its [:10] prefix is a calendar prefix, not an "
            "exchange session, and anchoring on it would land one session LATE "
            "-- i.e. more permissive. Route it to CHARC."
        )
    if value[:10] != parsed.date().isoformat():  # pragma: no cover
        raise _refuse(
            f"{what} {value!r} is not in EXTENDED YYYY-MM-DD... form; its date "
            "prefix does not equal its own parsed date."
        )
    return parsed


def _to_utc_naive(local_naive: datetime) -> datetime:
    """A naive LOCAL pipeline stamp -> the SAME instant as naive UTC.

    The window and the status intervals are written by different clocks:
    `evaluation_runs.run_ts` and `pipeline_runs.finished_ts` come from bare
    `datetime.now()` (naive LOCAL), while `hypothesis_status_history` comes
    from `datetime_helpers.now_ms()` (naive UTC, and the module docstring says
    so). On this box that is TEN HOURS. Comparing them as text -- which is what
    a straightforward implementation does -- compares instants ten hours apart,
    so a status change physically inside a 17:30-17:44 HST window is stored as
    ~03:35 UTC the NEXT DAY, the old interval appears to cover the whole
    textual window, and the correction is authorized on a status that had
    already changed. Canonical parsing does not fix this: the strings are
    well-formed and mean different things.
    """
    localized = local_naive.replace(tzinfo=ZoneInfo(PIPELINE_LOCAL_TIMEZONE))
    return localized.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# `F` -- the authoritative entry fill's session.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _EntryFill:
    fill_id: int
    trade_id: int
    fill_datetime: str
    parsed: datetime

    @property
    def session_date(self) -> str:
        return self.fill_datetime[:10]

    def snapshot(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "trade_id": self.trade_id,
            "action": "entry",
            "fill_datetime": self.fill_datetime,
        }


def resolve_authoritative_entry_fill(
    conn: sqlite3.Connection, trade_id: int,
) -> _EntryFill:
    """The trade's authoritative entry fill, by the project's DEFINITION.

    The DEFINITION is reused -- "first entry fill by (fill_datetime ASC,
    fill_id ASC)", `repos/fills.py:216` -- and the SQL IMPLEMENTATION is NOT.
    `get_authoritative_entry_fill` performs that ordering as a LEXICAL
    `ORDER BY ... LIMIT 1` over an unconstrained TEXT column, which mis-ranks a
    schema-legal basic-form timestamp AND hides it from validation. This loads
    EVERY `action='entry'` fill, validates each, refuses on any malformed one,
    and selects the minimum on `(parsed_datetime, fill_id)`. On well-formed
    data it returns exactly what the repo helper returns -- pinned by an
    equivalence test -- so the divergence is scoped to the malformed case and
    cannot become a second definition.

    THE SAME RESOLVER SERVES BOTH AUTHORIZATION AND THE DRIFT READER, or the
    two would disagree about which fill is authoritative.
    """
    rows = conn.execute(
        "SELECT fill_id, trade_id, fill_datetime FROM fills "
        "WHERE trade_id = ? AND action = 'entry'",
        (trade_id,),
    ).fetchall()
    if not rows:
        raise _refuse(
            f"trade {trade_id} has no action='entry' fill, so it has no "
            "session to be contemporaneous WITH."
        )
    fills: list[_EntryFill] = []
    for fill_id, owner, raw in rows:
        parsed = _require_naive_datetime(
            raw, what=f"fill {int(fill_id)}'s fill_datetime")
        fills.append(_EntryFill(
            fill_id=int(fill_id), trade_id=int(owner),
            fill_datetime=str(raw).strip(), parsed=parsed,
        ))
    fills.sort(key=lambda f: (f.parsed, f.fill_id))
    return fills[0]


# ---------------------------------------------------------------------------
# Authorization -- the read-only half, shared by preview and apply.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Anchored:
    """What the contemporaneity half of `_authorize` establishes."""
    trade: Any
    entry_fill: _EntryFill
    fill_session: str
    cited: Any                 # CitedCandidate
    run: Any                   # EvaluationRun
    recommendation: Any        # DailyRecommendation
    candidate_anchor: str
    recommendation_anchor: str
    run_ts_raw: str
    run_ts_utc: str
    run_ts_parsed: datetime


@dataclass(frozen=True)
class _AsOfInterval:
    """One validated `hypothesis_status_history` interval."""
    history_id: int
    hypothesis_id: int
    status: str
    start: datetime
    end: datetime | None
    recorded_at: datetime
    recorded_at_raw: str
    effective_from_raw: str
    effective_to_raw: str | None


def candidate_provenance_snapshot(cited: Any) -> dict[str, Any]:
    """The cited candidate's DERIVATION-BEARING content, canonically.

    Frozen because re-derivation ALONE is not enough (Codex R4 Major 3):
    `_non_pass_criterion_names` observes only the SET OF NAMES whose result is
    not `pass`, so flipping the live CADL case's `TT8_rs_rank` from `na` to
    `fail` leaves the set and therefore the LABEL unchanged -- while the
    correction's stored reason specifically records the `na` evidence.
    Criterion `value`, `rule` and `layer` changes, and the deletion of a
    PASSING criterion, are invisible the same way. So the label is still
    re-derived (it catches what a snapshot comparison would miss about
    MEANING) and the snapshot is compared as well (it catches what
    re-derivation cannot see). Neither subsumes the other.

    Sorted by criterion name so the comparison is order-independent.
    """
    return {
        "id": int(cited.candidate_id),
        "evaluation_run_id": int(cited.evaluation_run_id),
        "ticker": str(cited.candidate.ticker),
        "bucket": str(cited.candidate.bucket),
        "rs_method": str(cited.candidate.rs_method),
        "criteria": [
            {
                "criterion_name": c.criterion_name,
                "layer": c.layer,
                "result": c.result,
                "value": c.value,
                "rule": c.rule,
            }
            for c in sorted(
                cited.candidate.criteria, key=lambda c: c.criterion_name)
        ],
    }


@dataclass(frozen=True)
class _Derived:
    """The three written values, plus the provenance that justifies each."""
    hypothesis_label: str
    candidate_id: int
    trade_origin: str
    hypothesis_id: int
    hypothesis_name: str
    status_interval: _AsOfInterval
    pipeline_run_id: int
    pipeline_finished_ts_raw: str
    pipeline_snapshot: dict[str, Any]
    status_window_upper_utc: str


def _load_trade_or_refuse(conn: sqlite3.Connection, trade_id: int) -> Any:
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise _refuse(f"trade {trade_id} not found.")
    return trade


def _gate_on_unset_state(trade: Any) -> None:
    """All three cohort keys must currently be UNSET. A VERDICT, and terminal.

    This surface FILLS empty provenance; it does not re-decide provenance the
    framework already recorded. A trade whose keys are set is refused with the
    reason named, so the operator is not left guessing whether he can force it.
    """
    set_fields = []
    if getattr(trade, "hypothesis_label", None) is not None:
        set_fields.append(
            f"hypothesis_label={trade.hypothesis_label!r}")
    if getattr(trade, "candidate_id", None) is not None:
        set_fields.append(f"candidate_id={trade.candidate_id!r}")
    if str(getattr(trade, "trade_origin", "")) != UNSET_TRADE_ORIGIN:
        set_fields.append(f"trade_origin={trade.trade_origin!r}")
    if set_fields:
        raise _refuse(
            f"trade {trade.id} already carries cohort provenance "
            f"({'; '.join(set_fields)}). This surface FILLS empty provenance; "
            "it does not re-decide provenance the framework already recorded."
        )


def _bind_the_recommendation(
    conn: sqlite3.Connection,
    *,
    evaluation_run_id: int,
    ticker: str,
    supplied_recommendation_id: int,
) -> None:
    """The DR row is LOOKED UP, not picked -- and CONFIRMED, never selected.

    Cardinality is established by a COUNT, not by ``fetchone()``. The unique
    index on ``daily_recommendations`` is
    ``(action_session_date, ticker, recommendation)`` -- NOT
    ``(evaluation_run_id, ticker, recommendation)`` -- and
    ``upsert_recommendation`` REWRITES ``evaluation_run_id`` in place on
    conflict, so two ``today_decision`` rows with different action sessions can
    legitimately carry the same run id. A bare ``fetchone()`` would let
    SQLite's row order -- or the operator's supplied id -- pick the citation,
    reopening the citation-shopping channel the last-word guard exists to
    close.

    THE CARDINALITY REFUSAL PRECEDES THE CONFIRMATION COMPARE, so a supplied
    id can never break a tie.

    Then ``--cited-recommendation`` is a CONFIRMATION of the row derived from
    the candidate's own run, never the source of it -- item 5's ``--to`` idiom
    applied to a citation.
    """
    from swing.data.repos.recommendations import (
        list_today_decisions_for_run_ticker,
    )

    rows = list_today_decisions_for_run_ticker(
        conn, evaluation_run_id=evaluation_run_id, ticker=ticker)
    if len(rows) != 1:
        raise _refuse(
            f"evaluation run {evaluation_run_id} carries {len(rows)} "
            f"'{REQUIRED_RECOMMENDATION}' daily_recommendations rows for "
            f"{ticker} (ids {[r.id for r in rows]}); exactly one is required. "
            "The unique index is keyed on (action_session_date, ticker, "
            "recommendation), NOT on evaluation_run_id, so more than one is "
            "schema-legal -- and picking among them is the citation-shopping "
            "this surface refuses."
        )
    derived_id = int(rows[0].id)
    if derived_id != supplied_recommendation_id:
        raise _refuse(
            f"--cited-recommendation {supplied_recommendation_id} is not the "
            f"row derived from the cited candidate's run ({derived_id}). The "
            "recommendation is LOOKED UP from the candidate's own "
            "evaluation_run_id; the supplied id is a CONFIRMATION, never the "
            "source."
        )


def _assert_last_word_before_the_fill(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    fill_session: str,
    cited_candidate_id: int,
) -> None:
    """The cited candidate must be THE FRAMEWORK'S LAST WORD BEFORE THE FILL.

    Contemporaneity alone does not close citation-shopping. CADL has 33
    `candidates` rows, four of them in the fill's vicinity -- `watch` on 08-06,
    `watch` on 08-07, `watch` on 08-10 and `aplus` on 08-11 -- and ALL FOUR
    pre-date the 08-12 fill, so all four are contemporaneous. An operator free
    to pick among them picks the bucket he likes, which is the curation the
    evidence rule exists to prevent, re-entering through the choice of WHICH
    true record to cite.

    So: the maximum under `(action_session_date, run_ts, candidate_id)` among
    all rows for the ticker whose run's `action_session_date <= F`.

    EVERY COMPETITOR ROW IS VALIDATED, not just the cited one. The filter and
    the ordering are comparisons over unconstrained TEXT, so a competitor
    carrying a basic-ISO date is SILENTLY DROPPED from the competitor set --
    verified, `'20260811' <= '2026-08-12'` is False because `'0'` sorts after
    `'-'` -- and the guard would then bless an OLDER operator-selected
    citation: precisely the citation-shopping it exists to prevent, arriving
    through its own comparison. Validation scope is every row the DECISION
    READS, not every row the OPERATOR CITED.
    """
    from swing.data.repos.candidates import list_candidates_for_ticker

    rows = list_candidates_for_ticker(conn, ticker)
    ranked: list[tuple[_date, datetime, int, int]] = []
    for candidate_id, run_id, _bucket in rows:
        run = get_evaluation_run_by_id(conn, run_id)
        if run is None:
            raise _refuse(
                f"candidate {candidate_id} ({ticker}) names evaluation run "
                f"{run_id}, which does not exist, so the last-word guard "
                "cannot rank it."
            )
        anchor = _require_session_date(
            run.action_session_date,
            what=(f"competitor candidate {candidate_id}'s evaluation run "
                  f"{run_id} action_session_date"),
        )
        run_ts = _require_naive_datetime(
            run.run_ts,
            what=(f"competitor candidate {candidate_id}'s evaluation run "
                  f"{run_id} run_ts"),
        )
        if anchor.isoformat() <= fill_session:
            ranked.append((anchor, run_ts, candidate_id, run_id))
    if not ranked:
        raise _refuse(
            f"no {ticker} candidates row pre-dates the entry fill's session "
            f"({fill_session}), so there is no framework record to cite."
        )
    last_word = max(ranked)
    if last_word[2] != cited_candidate_id:
        raise _refuse(
            f"candidate {cited_candidate_id} is NOT the framework's last word "
            f"before the fill: candidate {last_word[2]} (evaluation run "
            f"{last_word[3]}, action session {last_word[0].isoformat()}) is "
            "later and also pre-dates the fill. Citing an earlier record when "
            "a later one exists is the citation-shopping this guard refuses -- "
            "including when the later record is a `skip` or `watch` row, in "
            "which case the trade is UNCORRECTABLE through this surface and "
            "the case belongs to RD."
        )


def _anchor_half(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    cited_candidate_id: int,
    cited_recommendation_id: int,
) -> _Anchored:
    """Refusal-ladder rungs 1 and 4-14: eligibility and CONTEMPORANEITY.

    > A citation is CONTEMPORANEOUS iff the cited record's OWN action-session
    > anchor does not POST-DATE the session of the trade's authoritative entry
    > fill.

    `action_session_date`, never `data_asof_date`. `data_asof_date` is the
    cohort-max of the per-ticker bar dates the run consumed -- a BATCH
    aggregate, and gotcha #30 names that exact column as an instance. Beyond
    the doctrine it is strictly WEAKER: across all 138 live runs the two differ
    on every single row and `data_asof_date` is UNIFORMLY EARLIER, so the wrong
    anchor is not differently wrong, it is MONOTONICALLY MORE PERMISSIVE.

    `<=`, not strict `<`. The anchor compares SESSION LABELS while
    admissibility is about CREATION time: a session-N record is produced by the
    run on the EVENING of session N-1, so its creation strictly precedes any
    session-N fill by construction even when the labels are equal. Strict `<`
    refuses 10 of the 11 live candidate-bearing trades INCLUDING trades 17 and
    18 -- the very cohort rows the rule was derived from. A rule that refuses
    its own derivation base is mis-encoded, not strict. (RD-ruled.)

    The two cited rows are gated INDEPENDENTLY on their own columns. Their
    anchors agree on all 182 live rows, but that equality is NOT
    schema-enforced, so it is a regularity rather than a guarantee and
    inferring one row's anchor from the other's is premise-by-neighbour.
    """
    trade = _load_trade_or_refuse(conn, trade_id)
    _gate_on_unset_state(trade)

    entry_fill = resolve_authoritative_entry_fill(conn, trade_id)
    fill_session_date = _require_session_date(
        entry_fill.session_date,
        what=f"the authoritative entry fill (fill {entry_fill.fill_id})'s "
             "session date",
    )
    fill_session = fill_session_date.isoformat()

    cited = fetch_candidate_by_id(conn, cited_candidate_id)
    if cited is None:
        raise _refuse(f"candidate {cited_candidate_id} not found.")
    recommendation = get_daily_recommendation_by_id(
        conn, cited_recommendation_id)
    if recommendation is None:
        raise _refuse(
            f"daily_recommendations row {cited_recommendation_id} not found.")

    trade_ticker = str(trade.ticker)
    if str(cited.candidate.ticker) != trade_ticker:
        raise _refuse(
            f"candidate {cited_candidate_id} is "
            f"{cited.candidate.ticker!r} but trade {trade_id} is "
            f"{trade_ticker!r}.")
    if str(recommendation.ticker) != trade_ticker:
        raise _refuse(
            f"daily_recommendations row {cited_recommendation_id} is "
            f"{recommendation.ticker!r} but trade {trade_id} is "
            f"{trade_ticker!r}.")

    # Rung 8, HERE rather than below the cardinality lookup: a `near_trigger`
    # row can never share an id with the selected `today_decision`, so below
    # the lookup this rung is UNREACHABLE and the operator gets a confusing
    # confirmation-id error instead of the eligibility verdict.
    if str(recommendation.recommendation) != REQUIRED_RECOMMENDATION:
        raise _refuse(
            f"daily_recommendations row {cited_recommendation_id} is a "
            f"{recommendation.recommendation!r} row, not "
            f"{REQUIRED_RECOMMENDATION!r}. A near_trigger row says 'watching, "
            "approaching'; it is not the framework recording a DECISION for "
            "that session."
        )

    if str(cited.candidate.bucket) != APLUS_BUCKET:
        raise _refuse(
            f"candidate {cited_candidate_id} is bucket "
            f"{cited.candidate.bucket!r}, not {APLUS_BUCKET!r}. That is the "
            "boundary of what is DERIVABLE, not a convenience restriction: "
            "derive_trade_origin maps a `watch` bucket to one of two origins "
            "according to `entry_path`, which is persisted NOWHERE, so a watch "
            "correction would have to COMPOSE trade_origin rather than read "
            "it."
        )

    run = get_evaluation_run_by_id(conn, cited.evaluation_run_id)
    if run is None:
        raise _refuse(
            f"candidate {cited_candidate_id} names evaluation run "
            f"{cited.evaluation_run_id}, which does not exist.")

    # Rung 10 -- canonical validation BEFORE any comparison uses these values.
    # They live in `_authorize` and NOT only in the model / DDL, because
    # `--dry-run` constructs no model and inserts no row: with the checks one
    # layer down, a schema-legal '2026-02-30' passes a LEXICAL `<=` in preview
    # and the apply path then dies at model construction -- preview says GO,
    # apply says NO.
    candidate_anchor = _require_session_date(
        run.action_session_date,
        what=f"evaluation run {run.id}'s action_session_date",
    ).isoformat()
    recommendation_anchor = _require_session_date(
        recommendation.action_session_date,
        what=(f"daily_recommendations row {cited_recommendation_id}'s "
              "action_session_date"),
    ).isoformat()
    run_ts_parsed = _require_naive_datetime(
        run.run_ts, what=f"evaluation run {run.id}'s run_ts")
    run_ts_raw = str(run.run_ts).strip()

    # Rungs 11 and 12 -- CARDINALITY first, then the confirmation compare.
    _bind_the_recommendation(
        conn,
        evaluation_run_id=int(cited.evaluation_run_id),
        ticker=trade_ticker,
        supplied_recommendation_id=cited_recommendation_id,
    )

    # Rungs 13 and 14 -- the contemporaneity comparisons, on PARSED dates.
    if candidate_anchor > fill_session:
        raise _refuse(
            f"the cited candidate's evaluation_runs.action_session_date "
            f"({candidate_anchor}) POST-DATES the authoritative entry fill's "
            f"session ({fill_session}), so the framework wrote that record "
            "AFTER the trade was already filled. It cannot be the record this "
            "trade came from."
        )
    if recommendation_anchor > fill_session:
        raise _refuse(
            f"the cited daily_recommendations.action_session_date "
            f"({recommendation_anchor}) POST-DATES the authoritative entry "
            f"fill's session ({fill_session}), so the framework wrote that "
            "record AFTER the trade was already filled."
        )

    # Rung 15 -- the LAST-WORD guard.
    _assert_last_word_before_the_fill(
        conn,
        ticker=trade_ticker,
        fill_session=fill_session,
        cited_candidate_id=cited_candidate_id,
    )

    return _Anchored(
        trade=trade,
        entry_fill=entry_fill,
        fill_session=fill_session,
        cited=cited,
        run=run,
        recommendation=recommendation,
        candidate_anchor=candidate_anchor,
        recommendation_anchor=recommendation_anchor,
        run_ts_raw=run_ts_raw,
        run_ts_utc=_to_utc_naive(run_ts_parsed).isoformat(),
        run_ts_parsed=run_ts_parsed,
    )


# ---------------------------------------------------------------------------
# THE AS-OF REGISTRY (refusal-ladder rungs 16-18).
# ---------------------------------------------------------------------------


def _load_validated_intervals(
    conn: sqlite3.Connection, hypothesis_id: int,
) -> list[_AsOfInterval]:
    """ALL intervals for one hypothesis, every timestamp validated.

    Loaded through the EXISTING unfiltered ``list_history_for_hypothesis``.
    That reader does carry an ``ORDER BY effective_from ASC`` in SQL, which is
    harmless HERE precisely because it ORDERS without FILTERING -- no row is
    hidden -- and its ordering is discarded and re-derived on parsed values
    anyway. The rule against lexical SQL is about FILTERING and LIMITING,
    which lose rows; a pure ordering that loses none is safe to inherit and
    unsafe to RELY on.

    A lexical ``WHERE`` would drop a malformed interval that genuinely
    OVERLAPS the window (a basic-form ``20260811T033500`` sorts after a
    normalized ``2026-08-11T03:44:45`` bound), leaving a corrupt overlapping
    interval invisible and ONE valid interval looking uniquely authoritative --
    manufacturing exactly the false single-interval result this guard exists
    to prevent.

    ``recorded_at`` is validated too, and it was the one omission that
    mattered: it is the WHOLE retrospective guard, the column is bare
    ``TEXT NOT NULL``, and ``HypothesisStatusHistory.__post_init__`` does not
    validate it -- so ``recorded_at=''`` sorts before EVERY valid ``run_ts``,
    satisfies the guard lexically, and authorizes an interval whose recording
    time is unknowable. A validation manifest is complete only if it covers
    every value the DECISION reads, and this one was decisive precisely
    because it was newest.
    """
    from swing.data.repos.hypothesis_status_history import (
        list_history_for_hypothesis,
    )

    try:
        history = list_history_for_hypothesis(conn, hypothesis_id)
    except ValueError as exc:
        # `HypothesisStatusHistory.__post_init__` compares `effective_to`
        # against `effective_from` LEXICALLY, so a malformed basic-form bound
        # can make the READER itself raise while hydrating. Left bare, that
        # escapes as an untyped ValueError with no "Nothing was written" and
        # no hypothesis named -- a refusal the operator cannot act on. The
        # reader is still the project's existing UNFILTERED one; only the
        # hydration failure is given this surface's own voice.
        raise _refuse(
            f"hypothesis {hypothesis_id}'s status history could not be read: "
            f"{exc}. A malformed interval bound is schema-legal (the columns "
            "are bare TEXT), and this surface refuses rather than deriving a "
            "status from the rows that happen to hydrate."
        ) from exc
    out: list[_AsOfInterval] = []
    for row in history:
        what = f"hypothesis {hypothesis_id} history row {row.history_id}"
        start = _require_naive_datetime(
            row.effective_from, what=f"{what}'s effective_from")
        end = None
        if row.effective_to is not None:
            end = _require_naive_datetime(
                row.effective_to, what=f"{what}'s effective_to")
            if end < start:
                raise _refuse(
                    f"{what} ends ({row.effective_to}) before it begins "
                    f"({row.effective_from}).")
        recorded = _require_naive_datetime(
            row.recorded_at, what=f"{what}'s recorded_at")
        out.append(_AsOfInterval(
            history_id=int(row.history_id),
            hypothesis_id=int(row.hypothesis_id),
            status=str(row.status),
            start=start,
            end=end,
            recorded_at=recorded,
            recorded_at_raw=str(row.recorded_at),
            effective_from_raw=str(row.effective_from),
            effective_to_raw=(
                None if row.effective_to is None else str(row.effective_to)),
        ))
    return out


def _assert_outside_the_clock_margin(
    intervals: list[_AsOfInterval], *, lo: datetime, hi: datetime,
) -> None:
    """REFUSE when any inspected boundary sits within +/-24h of a window bound.

    A naive stamp carries no zone and nothing records where the box was when it
    was written; a laptop that travelled, or an HST assumption applied to a
    machine that later moved, silently shifts every historical comparison.
    Inside the band a wrong-by-hours conversion could flip the verdict; outside
    it the ten-hour question cannot change the answer. So inside, decline.

    **CALLED ONLY AFTER `_as_of_status` HAS ALREADY DECLINED TO REFUSE, and
    that ordering is load-bearing.** The margin exists to protect a verdict a
    wrong-by-hours conversion could FLIP; when the interval ladder has already
    refused, the verdict is the conservative one and no flip is possible. Run
    the other way round, this check PRE-EMPTS every in-window transition -- a
    transition strictly inside a 14-minute window is necessarily within 24
    hours of both bounds -- so the specific "the status CHANGED INSIDE the
    window" refusal becomes UNREACHABLE and its test can only ever assert the
    margin message. The accept/refuse behaviour is identical either way; only
    the message the operator reads differs, and it differs in the direction
    that tells him what actually happened.

    Live cost, measured: none. H1's only interval begins 2026-04-25 and never
    ends, while the CADL window is 107 days away -- which is exactly why the
    margin refusal CANNOT stand in for a positive normalization assertion.
    """
    for interval in intervals:
        for label, boundary in (
            ("effective_from", interval.start), ("effective_to", interval.end),
            # `recorded_at` BELONGS HERE (Codex R2 Major 3). The margin exists
            # to protect a verdict a wrong-by-hours conversion could flip, and
            # `_assert_contemporaneous_interval` DECIDES AUTHORIZATION by
            # comparing `recorded_at` against the zone-converted lower bound --
            # so omitting it left the one comparison the margin was built for
            # unprotected. Concretely: a 17:30 local run is assumed 03:30 UTC
            # under HST, so a 02:00 UTC `recorded_at` reads contemporaneous;
            # had that run actually been written under PDT its real UTC time
            # was 00:30 and the same record is RETROSPECTIVE. With distant
            # interval bounds the margin never fired and the claimed
            # accept/refuse equivalence was false.
            ("recorded_at", interval.recorded_at),
        ):
            if boundary is None:
                continue
            for bound_name, bound in (("lower", lo), ("upper", hi)):
                if abs(boundary - bound) <= CLOCK_MARGIN:
                    raise _refuse(
                        f"hypothesis {interval.hypothesis_id} history row "
                        f"{interval.history_id}'s {label} "
                        f"({boundary.isoformat()}) is within 24 hours of the "
                        f"{bound_name} window bound ({bound.isoformat()} UTC). "
                        "The pipeline's timestamps are naive LOCAL and the "
                        "audit table's are naive UTC, and nothing records "
                        "which zone the box was in when either was written -- "
                        "so inside that band a wrong-by-hours conversion could "
                        "flip this verdict and the honest answer is to decline "
                        "rather than guess."
                    )


def _as_of_status(
    intervals: list[_AsOfInterval],
    *,
    hypothesis_id: int,
    lo: datetime,
    hi: datetime,
) -> _AsOfInterval | None:
    """The covering interval, or None when the hypothesis was NOT YET PRESENT.

    THE QUERY IS ON INTERVALS INTERSECTING THE WINDOW, NOT COVERING IT, AND
    THAT DISTINCTION IS THE WHOLE GUARD. Counting only COVERING intervals and
    expecting "more than one" on a mid-window transition is wrong: the
    production writer CLOSES the predecessor (`UPDATE prior SET effective_to`)
    and THEN INSERTs the successor, both at the same instant `t`, so a
    transition strictly inside the window yields two ADJACENT half-open
    intervals NEITHER of which covers it -- and the rule would fall through to
    its "no covering interval" branch and SILENTLY EXCLUDE the hypothesis
    instead of refusing.

    Half-open `[effective_from, effective_to)`; `effective_to IS NULL` means
    still current.
    """
    if not intervals:
        raise _refuse(
            f"hypothesis {hypothesis_id} has NO status-history rows at all. "
            "The audit table this guard rests on is incomplete for it, so the "
            "status as of the cited record cannot be established."
        )
    intersecting = [
        i for i in intervals
        if i.start <= hi and (i.end is None or i.end > lo)
    ]
    if not intersecting:
        earliest = min(i.start for i in intervals)
        if hi < earliest:
            # NOT YET PRESENT -- exclude, do NOT refuse. Migration 0026 created
            # H5 on 2026-06-09 with its history starting there, so refusing on
            # absence would make EVERY citation older than that uncorrectable
            # because an unrelated FUTURE hypothesis had not yet existed. It is
            # also what the matcher itself does: it omits non-active rows
            # rather than erroring.
            return None
        raise _refuse(
            f"hypothesis {hypothesis_id}'s status history has a GAP over the "
            f"window [{lo.isoformat()}, {hi.isoformat()}] UTC: no interval "
            "intersects it and the window does not precede the hypothesis's "
            "earliest interval."
        )
    if len(intersecting) == 1:
        only = intersecting[0]
        covers = only.start <= lo and (only.end is None or only.end > hi)
        if covers:
            return only
    raise _refuse(
        f"hypothesis {hypothesis_id}'s status CHANGED INSIDE the window "
        f"[{lo.isoformat()}, {hi.isoformat()}] UTC "
        f"({len(intersecting)} intersecting interval(s), none covering it). "
        "run_ts is the run's START and the record is persisted later, so the "
        "status the framework evaluated against is ambiguous here."
    )


def _assert_contemporaneous_interval(
    interval: _AsOfInterval, *, run_ts_utc: datetime,
) -> None:
    """REFUSE a RETROSPECTIVE interval -- one recorded after the window began.

    ``0017_phase9_risk_policy_and_reconciliation.sql`` seeds one interval per
    registry row with ``effective_from`` = a day-start anchor of the registry's
    ``created_at`` but ``recorded_at`` = MIGRATION APPLY TIME -- the migration's
    own comment says so. Those seeds are BACKDATED ASSERTIONS, not
    contemporaneous records, and the binding rule admits only the framework's
    own contemporaneous record. Disclosure is not authorization, and "otherwise
    the correction is unavailable" is an AVAILABILITY argument rather than
    evidence of contemporaneity.

    Compared against the UTC bound and NEVER against the raw local one:
    ``recorded_at`` is naive UTC and that comparison would be wrong by ten
    hours.
    """
    if interval.recorded_at > run_ts_utc:
        raise _refuse(
            f"hypothesis {interval.hypothesis_id}'s status interval "
            f"(history row {interval.history_id}) was recorded at "
            f"{interval.recorded_at_raw} UTC, which POST-DATES the cited "
            f"record's window start ({run_ts_utc.isoformat()} UTC). It is a "
            "RETROSPECTIVE assertion -- migration 0017 backdated its seed "
            "intervals exactly this way -- and a backdated interval is not the "
            "framework's contemporaneous record of its own status."
        )


def _derive(
    conn: sqlite3.Connection, anchored: _Anchored,
) -> _Derived:
    """Rungs 16-18, then the three values -- each a function of the record."""
    from dataclasses import replace

    from swing.data.repos.hypothesis import list_hypotheses
    from swing.data.repos.pipeline import evaluation_run_persistence_bound
    from swing.metrics.funnel import APLUS_TRADE_ORIGIN
    from swing.recommendations.hypothesis import match_candidate_to_hypotheses
    from swing.trades.entry import canonicalize_hypothesis_label

    run_id = int(anchored.cited.evaluation_run_id)

    # Rung 16 -- the window's UPPER BOUND, and the row that supplies it.
    bound = evaluation_run_persistence_bound(conn, evaluation_run_id=run_id)
    if bound is None:
        raise _refuse(
            f"evaluation run {run_id} has no single COMPLETE pipeline_runs row "
            "with a finished_ts, so the instant at which its records were "
            "persisted is UNBOUNDED ABOVE. run_ts is a run-START stamp (14m19s "
            "of uncertainty on the live CADL run), so without an upper bound "
            "the hypothesis-status window cannot be closed."
        )
    finished_parsed = _require_naive_datetime(
        bound.finished_ts,
        what=f"pipeline run {bound.pipeline_run_id}'s finished_ts")
    # `started_ts` rides into the frozen snapshot, so it is validated too
    # (Codex R2 Major 2). It is a bare TEXT column like every other timestamp
    # here, and an unvalidated value would be frozen into an audit row as
    # though the surface had vouched for it.
    if bound.snapshot.get("started_ts") is not None:
        _require_naive_datetime(
            bound.snapshot["started_ts"],
            what=f"pipeline run {bound.pipeline_run_id}'s started_ts")
    if finished_parsed < anchored.run_ts_parsed:
        raise _refuse(
            f"pipeline run {bound.pipeline_run_id} finished "
            f"({bound.finished_ts}) BEFORE evaluation run {run_id} started "
            f"({anchored.run_ts_raw}); the window is inverted and cannot bound "
            "anything."
        )
    # RUNG 14a -- THE SAME-SESSION CREATION-ORDER GATE (Codex R1 Major 1).
    #
    # `<=` is the Director's ruling and is NOT relitigated here. His REASON for
    # it is that a session-N record is produced by the run on the EVENING of
    # session N-1, so its creation strictly precedes any session-N fill BY
    # CONSTRUCTION. That reason is true of the nightly schedule and FALSE in
    # general: `action_session_for_run` returns the CURRENT session before the
    # close, so a manual mid-session run on session N produces a session-N
    # record CREATED AFTER a trade that already filled that session. Measured
    # on the live DB: 25 of 139 evaluation runs have
    # `date(run_ts) == action_session_date`, and 3 `aplus` candidates live in
    # them -- so this is reachable, not theoretical.
    #
    # The gate ENFORCES the ruling's own reason instead of weakening its
    # encoding: equality still ACCEPTS wherever the reason holds, and refuses
    # ONLY where the record demonstrably could have been written after the
    # fill. It compares a naive-LOCAL pipeline stamp against a session DATE --
    # never a fill's clock TIME, which is the synthetic `T16:00:00` placeholder
    # on all 46 live fills and carries no information. Inventing a third clock
    # domain to order them is exactly what this arc refuses to do.
    #
    # Direction: a REFUSAL only. It can never accept something `<=` refuses.
    fill_session = anchored.fill_session
    for anchor, label in (
        (anchored.candidate_anchor, "the cited candidate's evaluation run"),
        (anchored.recommendation_anchor, "the cited recommendation's run"),
    ):
        if anchor != fill_session:
            continue
        if bound.finished_ts[:10] >= fill_session:
            raise _refuse(
                f"{label} carries action_session_date {anchor}, which EQUALS "
                f"the authoritative entry fill's session ({fill_session}), and "
                f"pipeline run {bound.pipeline_run_id} finished at "
                f"{bound.finished_ts} -- on that same session or later. "
                "Same-session citations are admissible because a session-N "
                "record is normally produced by the run on the EVENING of "
                "session N-1, so its creation precedes any session-N fill; "
                "this run does not have that shape, so it cannot be shown to "
                "pre-date the fill. The fill's own clock time is the synthetic "
                "T16:00:00 placeholder and cannot order them."
            )

    lo = _to_utc_naive(anchored.run_ts_parsed)
    hi = _to_utc_naive(finished_parsed)

    # Rung 17 -- the AS-OF registry.
    #
    # `match_candidate_to_hypotheses` filters `h.status == 'active'` on the
    # rows handed to it, so passing TODAY's `list_hypotheses(conn)` would make
    # the derived hypothesis a function of PRESENT-DAY MUTABLE STATE -- exactly
    # what the binding rule forbids, one level up from the values themselves.
    # The failure is two-directional and both directions are wrong: a
    # hypothesis PAUSED when the record was written but active today would be
    # assigned anyway, and one active then and closed now would be refused.
    # Not hypothetical -- H2 has a real active/paused/active cycle and H3 went
    # active -> closed-target-met; only H1's own history is uninterrupted,
    # which is why the CADL case would have come out right BY LUCK.
    as_of_rows = []
    covering_by_hypothesis: dict[int, _AsOfInterval] = {}
    for entry in list_hypotheses(conn):
        intervals = _load_validated_intervals(conn, int(entry.id))
        covering = _as_of_status(
            intervals, hypothesis_id=int(entry.id), lo=lo, hi=hi)
        # The margin guards a verdict that could FLIP, so it runs only where
        # the ladder above did NOT already refuse -- both the "use it" verdict
        # and the NOT-YET-PRESENT exclusion, since either lets the correction
        # proceed. See `_assert_outside_the_clock_margin`.
        _assert_outside_the_clock_margin(intervals, lo=lo, hi=hi)
        if covering is None:
            continue  # NOT YET PRESENT -- excluded, not refused.
        _assert_contemporaneous_interval(covering, run_ts_utc=lo)
        covering_by_hypothesis[int(entry.id)] = covering
        as_of_rows.append(replace(entry, status=covering.status))

    # Rung 18 -- the hypothesis is DERIVED, not chosen.
    #
    # `include_baseline` stays at its False default: the broad-watch fallback
    # is a caller-side opt-in for the recommendation surface, and firing it
    # here would let a FALLBACK rule label a correction.
    matches = match_candidate_to_hypotheses(
        anchored.cited.candidate, registry=as_of_rows)
    if len(matches) != 1:
        raise _refuse(
            f"the matcher returned {len(matches)} hypothesis matches for "
            f"candidate {anchored.cited.candidate_id} against the registry AS "
            f"OF the cited record "
            f"({[m.hypothesis_name for m in matches]}); exactly one is "
            "required. An `aplus` candidate matches the A+ baseline and only "
            "it today, but the registry is DATA and this asserts rather than "
            "assumes that."
        )
    match = matches[0]

    interval = covering_by_hypothesis[int(match.hypothesis_id)]
    if interval.status != "active":  # pragma: no cover -- matcher guarantees
        raise _refuse(
            f"hypothesis {match.hypothesis_id} matched while its as-of status "
            f"was {interval.status!r}.")
    # THE CITATION GRAPH IS ASSERTED, NOT MERELY ARRANGED (Codex R2 Major 1).
    # The audit row's FKs prove each cited row EXISTS; nothing in SQLite can
    # express "this interval belongs to that hypothesis" or "this candidate
    # belongs to that run" across tables without composite FKs against UNIQUE
    # indexes on tables this arc does not own. The SERVICE can and now does say
    # so about its own output, so the coherence it arranges is also CHECKED.
    if interval.hypothesis_id != int(match.hypothesis_id):  # pragma: no cover
        raise _refuse(
            f"the covering interval (history row {interval.history_id}) "
            f"belongs to hypothesis {interval.hypothesis_id}, not to the "
            f"matched hypothesis {match.hypothesis_id}.")
    if int(anchored.cited.evaluation_run_id) != int(anchored.run.id):
        raise _refuse(  # pragma: no cover -- the run is fetched BY that id
            f"candidate {anchored.cited.candidate_id} belongs to evaluation "
            f"run {anchored.cited.evaluation_run_id}, but the cited run is "
            f"{anchored.run.id}.")
    if int(bound.snapshot["evaluation_run_id"]) != run_id:  # pragma: no cover
        raise _refuse(
            f"pipeline run {bound.pipeline_run_id} owns evaluation run "
            f"{bound.snapshot['evaluation_run_id']}, not {run_id}.")

    label = canonicalize_hypothesis_label(match.suggested_label_descriptive)
    if not label:
        raise _refuse(
            "the framework's own label builder produced an empty label for "
            f"candidate {anchored.cited.candidate_id}.")

    return _Derived(
        hypothesis_label=label,
        candidate_id=int(anchored.cited.candidate_id),
        # IMPORTED from `swing.metrics.funnel`, never a third copy of the
        # literal (#11). A drift test pins it against `origin.py`'s mapping.
        trade_origin=APLUS_TRADE_ORIGIN,
        hypothesis_id=int(match.hypothesis_id),
        hypothesis_name=str(match.hypothesis_name),
        status_interval=interval,
        pipeline_run_id=bound.pipeline_run_id,
        pipeline_finished_ts_raw=str(bound.finished_ts),
        pipeline_snapshot=bound.snapshot,
        status_window_upper_utc=hi.isoformat(),
    )


@dataclass(frozen=True)
class CohortProvenanceCorrectionPreview:
    """What ``--dry-run`` knows, and what it deliberately does not.

    There is no predicted cohort read: forecasting ``in_flight_sample`` would
    re-implement ``compute_hypothesis_progress_breakdown`` in the preview path,
    and a second implementation of a derivation is the two-path-divergence
    class invited into a preview. A dry run may show what it knows and MUST
    say what it does not.
    """

    trade_id: int
    ticker: str
    state: str
    cited_candidate_id: int
    cited_daily_recommendation_id: int
    cited_evaluation_run_id: int
    cited_pipeline_run_id: int
    cited_hypothesis_id: int
    cited_hypothesis_name: str
    cited_hypothesis_status_history_id: int
    entry_fill_id: int
    entry_fill_session_date: str
    candidate_action_session_date: str
    recommendation_action_session_date: str
    run_ts_raw: str
    run_ts_utc: str
    pipeline_finished_ts_raw: str
    status_window_upper_utc: str
    derivation_rule_version: str
    pre_values: dict[str, Any]
    post_values: dict[str, Any]
    na_criterion_suffix_note: str | None = None
    already_applied_correction_id: int | None = None


def _reason_or_refuse(reason: Any) -> str:
    if not isinstance(reason, str) or not reason.strip():
        raise _refuse("--reason must be a non-empty string.")
    return reason.strip()


@dataclass(frozen=True)
class _Authorized:
    trade: Any
    already_applied: Any = None       # ProvenanceCorrection | None
    anchored: _Anchored | None = None
    derived: _Derived | None = None


def _authorize(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    cited_candidate_id: int,
    cited_recommendation_id: int,
    reason: Any,
) -> _Authorized:
    """Every read-only check, in refusal-ladder order. Writes nothing.

    SELECT-FIRST IDEMPOTENCY LEADS THE LADDER, and it sits ABOVE ``--reason``
    validation, not merely above the unset-state gate. CLAUDE.md states the
    rule directly: a terminal-state row must return its existing audit-row id
    even with a stale or None payload. With ``--reason`` checked first, an
    already-applied re-run carrying an empty reason REFUSES instead of
    returning its correction id -- and a happy-path test using a valid reason
    cannot catch that.
    """
    trade = _load_trade_or_refuse(conn, trade_id)

    # THE CITATION IDS ARE THE IDEMPOTENCY KEY, NOT PAYLOAD (Codex R1 Minor 5,
    # partially adopted). CLAUDE.md's SELECT-first rule is about a stale or
    # None PAYLOAD; the citation is what makes a request the SAME request, so
    # it cannot be optional without weakening the contract to "any re-run on
    # this trade_id succeeds" -- under which a typo'd replay would silently
    # report success against a citation it never named. `--reason` is the
    # payload and IS optional on the replay path; the citations stay required.
    #
    # What IS adopted: a non-int citation must produce this surface's typed
    # refusal rather than a bare `TypeError` from `int(...)` inside the
    # comparison below, which is reachable from a direct service call.
    for name, value in (
        ("cited_candidate_id", cited_candidate_id),
        ("cited_recommendation_id", cited_recommendation_id),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise _refuse(
                f"{name} must be an int row id; got {value!r}. The citation "
                "is the idempotency KEY, so it is required even on a replay."
            )

    from swing.data.repos.provenance_corrections import get_correction_for_trade

    existing = get_correction_for_trade(conn, trade_id)
    if existing is not None:
        same = (
            int(existing.cited_candidate_id) == int(cited_candidate_id)
            and int(existing.cited_daily_recommendation_id)
            == int(cited_recommendation_id)
        )
        if same:
            return _Authorized(trade=trade, already_applied=existing)
        raise _refuse(
            f"trade {trade_id} already has provenance correction "
            f"{existing.provenance_correction_id}, which cites candidate "
            f"{existing.cited_candidate_id} and daily_recommendations row "
            f"{existing.cited_daily_recommendation_id} -- not candidate "
            f"{cited_candidate_id} / row {cited_recommendation_id}. V1 records "
            "provenance ONCE per trade and there is no supersession path: "
            "re-deciding provenance is a different authority question."
        )

    # THE UNSET-STATE VERDICT PRECEDES THE REASON INSTRUCTION (Codex R3 Minor
    # 7). It is TERMINAL and true whatever payload arrives, while "supply a
    # reason" is an INSTRUCTION that implies the rest of the request is sound.
    # With the reason first, a trade whose cohort keys are already populated
    # sent the operator away to compose a justification for an operation that
    # can never be authorized. This is the plan's own ordering principle --
    # every VERDICT before any INSTRUCTION -- applied to its own ladder.
    _gate_on_unset_state(trade)
    _reason_or_refuse(reason)
    anchored = _anchor_half(
        conn,
        trade_id=trade_id,
        cited_candidate_id=cited_candidate_id,
        cited_recommendation_id=cited_recommendation_id,
    )
    return _Authorized(
        trade=trade, anchored=anchored, derived=_derive(conn, anchored))


def _na_suffix_note(anchored: _Anchored, derived: _Derived) -> str | None:
    """Explain a ``; failed: X`` suffix earned by an ``na`` result.

    A NAMED WART, not a hidden one. ``_non_pass_criterion_names`` counts `na`
    as non-pass -- matching `bucket_for`'s VCP gating -- so a criterion whose
    result is `na` renders under a `failed:` heading. That inaccuracy is
    PRE-EXISTING in the framework's own builder and fixing it would change
    every future recommendation label, so this surface reuses the builder
    rather than minting a second implementation, and SAYS SO wherever the
    string is shown.
    """
    na_names = sorted(
        c.criterion_name for c in anchored.cited.candidate.criteria
        if c.result == "na"
    )
    if not na_names or "; failed:" not in derived.hypothesis_label:
        return None
    return (
        "the derived label's `failed:` suffix includes "
        f"{', '.join(na_names)}, whose result is `na` rather than `fail`. "
        "The framework's own label builder counts `na` as non-pass, so the "
        "wording is a pre-existing inaccuracy in that builder and not "
        "something this correction introduced."
    )


def preview_cohort_provenance_correction(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    cited_candidate_id: int,
    cited_recommendation_id: int,
    reason: str | None = None,
) -> CohortProvenanceCorrectionPreview:
    """``--dry-run``: every read-only check, writing nothing.

    Raises the SAME refusals the write path raises, because both call the same
    authorization function -- one authorization function, two entry points, so
    ``--dry-run`` cannot diverge from apply.
    """
    # A DRY RUN MUST AT LEAST BE COHERENT WITH ITSELF (Codex R2 Major 4). The
    # authorization ladder runs a dozen separate SELECTs, and under sqlite3's
    # default isolation each one sees whatever is committed at that instant --
    # so a pipeline run, a status transition or a reconciliation landing
    # MID-LADDER could make the preview report a mix of two worlds. A DEFERRED
    # read transaction pins ONE snapshot for the whole ladder and is rolled
    # back unconditionally, so the preview still writes nothing and still takes
    # no write lock.
    #
    # WHAT THIS DOES NOT BUY, stated rather than implied: it does not bind the
    # preview to a LATER apply. The apply re-runs the ENTIRE ladder, so it can
    # never write on stale inputs -- it either derives afresh or refuses -- but
    # the operator may be shown one reading and get another outcome. Closing
    # that needs a digest threaded preview -> apply, and the CLI parameter
    # manifest is pinned at EXACTLY five by a test that exists to keep a VALUE
    # out of the operator's hands. Recorded as a V2 dependency; the apply
    # prints the anchors it actually used so a divergence is visible at the
    # moment of the write.
    owns_read_tx = not conn.in_transaction
    if owns_read_tx:
        conn.execute("BEGIN DEFERRED")
    try:
        auth = _authorize(
            conn,
            trade_id=trade_id,
            cited_candidate_id=cited_candidate_id,
            cited_recommendation_id=cited_recommendation_id,
            reason=reason,
        )
        if auth.already_applied is not None:
            return _preview_from_existing(auth.trade, auth.already_applied)
        anchored, derived = auth.anchored, auth.derived
    finally:
        if owns_read_tx:
            with contextlib.suppress(sqlite3.Error):
                conn.rollback()
    trade = anchored.trade
    return CohortProvenanceCorrectionPreview(
        trade_id=trade_id,
        ticker=str(trade.ticker),
        state=str(trade.state),
        cited_candidate_id=cited_candidate_id,
        cited_daily_recommendation_id=cited_recommendation_id,
        cited_evaluation_run_id=int(anchored.cited.evaluation_run_id),
        cited_pipeline_run_id=derived.pipeline_run_id,
        cited_hypothesis_id=derived.hypothesis_id,
        cited_hypothesis_name=derived.hypothesis_name,
        cited_hypothesis_status_history_id=derived.status_interval.history_id,
        entry_fill_id=anchored.entry_fill.fill_id,
        entry_fill_session_date=anchored.fill_session,
        candidate_action_session_date=anchored.candidate_anchor,
        recommendation_action_session_date=anchored.recommendation_anchor,
        run_ts_raw=anchored.run_ts_raw,
        run_ts_utc=anchored.run_ts_utc,
        pipeline_finished_ts_raw=derived.pipeline_finished_ts_raw,
        status_window_upper_utc=derived.status_window_upper_utc,
        derivation_rule_version=DERIVATION_RULE_VERSION,
        pre_values={
            "trades.hypothesis_label": trade.hypothesis_label,
            "trades.candidate_id": trade.candidate_id,
            "trades.trade_origin": trade.trade_origin,
        },
        post_values={
            "trades.hypothesis_label": derived.hypothesis_label,
            "trades.candidate_id": derived.candidate_id,
            "trades.trade_origin": derived.trade_origin,
        },
        na_criterion_suffix_note=_na_suffix_note(anchored, derived),
    )


def _preview_from_existing(trade: Any, existing: Any) -> CohortProvenanceCorrectionPreview:
    """The preview for an ALREADY-APPLIED trade, read off the audit row.

    Every value comes from the FROZEN columns rather than being re-derived, so
    the dry run reports what is RECORDED rather than what a fresh derivation
    would produce today. Those can differ -- a registry rename, a
    `_descriptive_label` change -- and reporting the re-derivation here would
    quietly show the operator a value his ledger does not contain.
    """
    applied = json.loads(existing.applied_value_json)
    pre = json.loads(existing.pre_value_json)
    return CohortProvenanceCorrectionPreview(
        trade_id=int(existing.trade_id),
        ticker=str(trade.ticker),
        state=str(trade.state),
        cited_candidate_id=int(existing.cited_candidate_id),
        cited_daily_recommendation_id=int(
            existing.cited_daily_recommendation_id),
        cited_evaluation_run_id=int(existing.cited_evaluation_run_id),
        cited_pipeline_run_id=int(existing.cited_pipeline_run_id),
        cited_hypothesis_id=int(existing.cited_hypothesis_id),
        cited_hypothesis_name=str(existing.cited_hypothesis_name_at_correction),
        cited_hypothesis_status_history_id=int(
            existing.cited_hypothesis_status_history_id),
        entry_fill_id=int(existing.entry_fill_id_at_correction),
        entry_fill_session_date=str(existing.entry_fill_session_date),
        candidate_action_session_date=str(
            existing.cited_candidate_action_session_date),
        recommendation_action_session_date=str(
            existing.cited_recommendation_action_session_date),
        run_ts_raw=str(existing.cited_run_ts_raw),
        run_ts_utc=str(existing.cited_run_ts_utc),
        pipeline_finished_ts_raw=str(existing.cited_pipeline_finished_ts_raw),
        status_window_upper_utc=str(existing.cited_status_window_upper_utc),
        derivation_rule_version=str(existing.derivation_rule_version),
        pre_values=pre,
        post_values=applied,
        already_applied_correction_id=int(existing.provenance_correction_id),
    )


@dataclass(frozen=True)
class CohortProvenanceCorrectionResult:
    correction_id: int
    trade_id: int
    already_applied: bool
    cited_candidate_id: int
    cited_daily_recommendation_id: int
    pre_values: dict[str, Any]
    applied_values: dict[str, Any]
    correction_reason: str
    follow_up_command: str


def _compose_reason(
    operator_reason: str, anchored: _Anchored, derived: _Derived,
) -> str:
    """The operator's reason plus the clause only the server can write.

    The audit trail explains its OWN string: which two rows were cited, what
    their anchors were, which fill supplied `F`, which hypothesis and interval
    authorized the label, and -- when it applies -- why the label carries a
    `failed:` heading over a criterion whose result was `na`.
    """
    parts = [
        operator_reason.strip(),
        "[server-derived: cohort keys taken from candidates row "
        f"{anchored.cited.candidate_id} (evaluation run "
        f"{anchored.cited.evaluation_run_id}, action session "
        f"{anchored.candidate_anchor}) confirmed by daily_recommendations row "
        f"{anchored.recommendation.id} (action session "
        f"{anchored.recommendation_anchor}); both pre-date the authoritative "
        f"entry fill {anchored.entry_fill.fill_id}'s session "
        f"{anchored.fill_session}. Hypothesis {derived.hypothesis_id} "
        f"({derived.hypothesis_name}) was 'active' over "
        f"[{anchored.run_ts_utc}, {derived.status_window_upper_utc}] UTC per "
        f"status-history row {derived.status_interval.history_id}. Label "
        f"written verbatim from the framework's own builder "
        f"(derivation rule {DERIVATION_RULE_VERSION}): "
        f"{derived.hypothesis_label!r}.]",
    ]
    note = _na_suffix_note(anchored, derived)
    if note:
        parts.append(f"[{note}]")
    return " ".join(parts)


def correct_cohort_provenance(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    cited_candidate_id: int,
    cited_recommendation_id: int,
    reason: str | None = None,
) -> CohortProvenanceCorrectionResult:
    """Outer: owns ``BEGIN IMMEDIATE`` / COMMIT / ROLLBACK, and REJECTS a
    caller-held transaction -- never auto-detects, because an auto-detect
    guard re-introduces the race the explicit lock closed.

    THERE IS NO ``applied_at`` PARAMETER (Codex R3 Major 1). A caller could
    previously pass ``applied_at='1900-01-01T00:00:00'`` and the audit row
    would durably record that the correction happened then -- reachable
    through a direct service call, and grammar validation established only
    that the value LOOKED like a timestamp, never that this surface OBSERVED
    it. In a table whose entire purpose is to hold claims that are true, the
    one field nobody may supply is when it happened. The clock is stamped
    INSIDE the transaction; tests that need determinism patch
    ``_APPLIED_AT_CLOCK``.
    """
    if conn.in_transaction:
        raise CallerHeldTransactionError(
            "correct_cohort_provenance must be called with no open "
            "transaction; compose via _correct_cohort_provenance_inner inside "
            "an existing tx. Nothing was written."
        )
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = _correct_cohort_provenance_inner(
            conn,
            trade_id=trade_id,
            cited_candidate_id=cited_candidate_id,
            cited_recommendation_id=cited_recommendation_id,
            reason=reason,
        )
        conn.commit()
        return result
    except Exception:
        with contextlib.suppress(sqlite3.Error):
            conn.rollback()
        raise


def _correct_cohort_provenance_inner(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    cited_candidate_id: int,
    cited_recommendation_id: int,
    reason: str | None = None,
) -> CohortProvenanceCorrectionResult:
    """Never commits. Every callee is repo-level, so no inner ``with conn:``
    can close the caller's transaction out from under it.

    THERE IS NO STEP AFTER THE AUDIT INSERT. V1 writes exactly one correction
    row per trade and never supersedes; ``ux_provenance_corrections_trade``
    makes a second row impossible even if this function were wrong.

    NO ``trade_events`` ROW IS EMITTED, DELIBERATELY. ``trade_events
    .event_type`` is a CHECK enum of exactly seven values -- read off the live
    DDL: entry, stop_adjust, note, exit, flag, pre_trade_edit,
    reconciliation_auto_correct -- and none of them truthfully names an
    operator cohort-provenance correction. Item 5 already carries
    ``reconciliation_auto_correct`` as recorded naming debt; repeating it here
    would be worse, because there is no reconciliation anywhere in this arc.
    Writing a MISLABELLED audit record beside a purpose-built correct one is
    the precise failure this arc exists to stop. CONSEQUENCE, NAMED: a
    ``trade_events``-backed timeline will not show this correction;
    ``swing journal provenance-corrections`` is the read surface.
    """
    from swing.data.repos.provenance_corrections import (
        insert_provenance_correction,
    )
    from swing.data.repos.recommendations import snapshot_recommendation_row
    from swing.data.repos.trades import update_cohort_provenance
    from swing.trades.reconciliation_auto_correct import (
        _maybe_get_active_risk_policy_id,
    )

    auth = _authorize(
        conn,
        trade_id=trade_id,
        cited_candidate_id=cited_candidate_id,
        cited_recommendation_id=cited_recommendation_id,
        reason=reason,
    )
    if auth.already_applied is not None:
        existing = auth.already_applied
        return CohortProvenanceCorrectionResult(
            correction_id=int(existing.provenance_correction_id),
            trade_id=trade_id,
            already_applied=True,
            cited_candidate_id=int(existing.cited_candidate_id),
            cited_daily_recommendation_id=int(
                existing.cited_daily_recommendation_id),
            pre_values=json.loads(existing.pre_value_json),
            applied_values=json.loads(existing.applied_value_json),
            correction_reason=str(existing.correction_reason),
            follow_up_command=(
                f"swing journal provenance-corrections {trade_id}"),
        )

    anchored = auth.anchored
    derived = auth.derived
    trade = auth.trade

    pre_values: dict[str, Any] = {
        "trades.hypothesis_label": trade.hypothesis_label,
        "trades.candidate_id": trade.candidate_id,
        "trades.trade_origin": trade.trade_origin,
    }
    applied_values: dict[str, Any] = {
        "trades.hypothesis_label": derived.hypothesis_label,
        "trades.candidate_id": derived.candidate_id,
        "trades.trade_origin": derived.trade_origin,
    }

    update_cohort_provenance(
        conn,
        trade_id=trade_id,
        hypothesis_label=derived.hypothesis_label,
        candidate_id=derived.candidate_id,
        trade_origin=derived.trade_origin,
    )

    snapshot = snapshot_recommendation_row(conn, cited_recommendation_id)
    if snapshot is None:  # pragma: no cover -- rung 6 already found the row
        raise _refuse(
            f"daily_recommendations row {cited_recommendation_id} vanished "
            "between authorization and the snapshot.")

    stored_reason = _compose_reason(str(reason), anchored, derived)
    correction_id = insert_provenance_correction(
        conn,
        ProvenanceCorrection(
            provenance_correction_id=None,
            trade_id=trade_id,
            entry_fill_id=anchored.entry_fill.fill_id,
            entry_fill_id_at_correction=anchored.entry_fill.fill_id,
            entry_fill_snapshot_json=json.dumps(
                anchored.entry_fill.snapshot(), sort_keys=True),
            cited_candidate_id=int(anchored.cited.candidate_id),
            cited_daily_recommendation_id=cited_recommendation_id,
            cited_evaluation_run_id=int(anchored.cited.evaluation_run_id),
            cited_hypothesis_id=derived.hypothesis_id,
            cited_hypothesis_status_history_id=(
                derived.status_interval.history_id),
            cited_hypothesis_status_at_record=derived.status_interval.status,
            cited_pipeline_finished_ts_raw=derived.pipeline_finished_ts_raw,
            cited_run_ts_utc=anchored.run_ts_utc,
            cited_status_window_upper_utc=derived.status_window_upper_utc,
            cited_pipeline_run_id=derived.pipeline_run_id,
            cited_pipeline_run_snapshot_json=json.dumps(
                derived.pipeline_snapshot, sort_keys=True),
            cited_hypothesis_status_recorded_at=(
                derived.status_interval.recorded_at_raw),
            cited_hypothesis_status_effective_from=(
                derived.status_interval.effective_from_raw),
            cited_hypothesis_status_effective_to=(
                derived.status_interval.effective_to_raw),
            cited_candidate_snapshot_json=json.dumps(
                candidate_provenance_snapshot(anchored.cited), sort_keys=True),
            cited_hypothesis_name_at_correction=derived.hypothesis_name,
            cited_candidate_action_session_date=anchored.candidate_anchor,
            cited_recommendation_action_session_date=(
                anchored.recommendation_anchor),
            entry_fill_session_date=anchored.fill_session,
            cited_run_ts_raw=anchored.run_ts_raw,
            cited_recommendation_snapshot_json=json.dumps(
                snapshot, sort_keys=True),
            derivation_rule_version=DERIVATION_RULE_VERSION,
            pre_value_json=json.dumps(pre_values, sort_keys=True),
            applied_value_json=json.dumps(applied_values, sort_keys=True),
            corrected_fields_json=json.dumps(list(COHORT_CORRECTED_FIELDS)),
            applied_at=_APPLIED_AT_CLOCK(),
            applied_by=PROVENANCE_CORRECTION_APPLIED_BY,
            correction_reason=stored_reason,
            risk_policy_id_at_correction=_maybe_get_active_risk_policy_id(conn),
        ),
    )

    return CohortProvenanceCorrectionResult(
        correction_id=correction_id,
        trade_id=trade_id,
        already_applied=False,
        cited_candidate_id=int(anchored.cited.candidate_id),
        cited_daily_recommendation_id=cited_recommendation_id,
        pre_values=pre_values,
        applied_values=applied_values,
        correction_reason=stored_reason,
        follow_up_command=f"swing journal provenance-corrections {trade_id}",
    )


# ---------------------------------------------------------------------------
# The READ surface -- and its drift reporting.
#
# Without it the audit table has no supported reader, and "verify against the
# audit trail" would need raw SQL. More importantly, a FROZEN SNAPSHOT NOBODY
# COMPARES IS DECORATION: a silent contradiction between the audit row and the
# row it cites is the failure mode, and a LOUD one is a finding the operator
# can act on.
# ---------------------------------------------------------------------------

CITATION_DRIFT = "CITATION DRIFT"
CITATION_SCHEMA_DRIFT = "CITATION SCHEMA DRIFT"
CITATION_ANCHOR_DRIFT = "CITATION ANCHOR DRIFT"
CITATION_ANCHOR_UNVERIFIABLE = "CITATION ANCHOR UNVERIFIABLE"
CITATION_INVALIDATED = "CITATION INVALIDATED"


@dataclass(frozen=True)
class ProvenanceCorrectionReport:
    correction: Any                 # ProvenanceCorrection
    drift_lines: tuple[str, ...]

    @property
    def has_drift(self) -> bool:
        return bool(self.drift_lines)


def _snapshot_drift(
    label: str, frozen: dict[str, Any], live: dict[str, Any] | None,
) -> list[str]:
    """Field-by-field over the SAME derived column set, plus schema drift."""
    if live is None:
        return [
            f"{CITATION_DRIFT}: the cited {label} row no longer exists."]
    lines: list[str] = []
    for missing in sorted(set(frozen) - set(live)):
        lines.append(
            f"{CITATION_SCHEMA_DRIFT}: {label}.{missing} was frozen but is "
            "absent from the live row.")
    for added in sorted(set(live) - set(frozen)):
        lines.append(
            f"{CITATION_SCHEMA_DRIFT}: {label}.{added} exists live but was "
            "not frozen at correction time.")
    for field in sorted(set(frozen) & set(live)):
        if frozen[field] != live[field]:
            lines.append(
                f"{CITATION_DRIFT}: {label}.{field} was {frozen[field]!r} now "
                f"{live[field]!r}")
    return lines


def _status_interval_drift(
    conn: sqlite3.Connection, correction: Any,
) -> list[str]:
    """RE-READ the cited status-history row (Codex R1 Major 4).

    The FK pins WHICH interval was cited; it does nothing about that interval
    CHANGING. ``update_close_open_interval`` rewrites ``effective_to`` IN PLACE
    on EVERY supported status transition
    (``repos/hypothesis_status_history.py:66``), so the row whose coverage the
    whole correction's authority rests on is mutable through a shipped
    service — and with nothing frozen to compare, the reader printed "no
    citation drift" after a real, supported mutation.

    Two questions, and they are DIFFERENT:
      - has the row MOVED at all (drift, reported whatever the consequence);
      - does it still COVER the frozen window (invalidation, escalated).
    A later closure is legitimate evolution and may leave the coverage claim
    true; it must still not be reported as no drift.

    The candidate row and its `candidate_criteria` are deliberately NOT tracked
    here, and the reason is checked rather than assumed: `grep -rniE
    "update candidate_criteria|delete from candidate_criteria"` over all of
    `swing/` returns ZERO sites, and `candidates` itself is held by an
    `ON DELETE RESTRICT` FK. They are written once at run creation and never
    mutated, so there is no live path for them to drift through.
    """
    frozen = {
        "hypothesis_id": int(correction.cited_hypothesis_id),
        "status": str(correction.cited_hypothesis_status_at_record),
        "effective_from": str(
            correction.cited_hypothesis_status_effective_from),
        "effective_to": correction.cited_hypothesis_status_effective_to,
        "recorded_at": str(correction.cited_hypothesis_status_recorded_at),
    }
    row = conn.execute(
        "SELECT hypothesis_id, status, effective_from, effective_to, "
        "recorded_at FROM hypothesis_status_history WHERE history_id = ?",
        (int(correction.cited_hypothesis_status_history_id),),
    ).fetchone()
    if row is None:
        return [
            f"{CITATION_DRIFT}: the cited hypothesis_status_history row "
            f"{correction.cited_hypothesis_status_history_id} no longer "
            "exists."
        ]
    live = {
        "hypothesis_id": int(row[0]), "status": str(row[1]),
        "effective_from": str(row[2]),
        "effective_to": None if row[3] is None else str(row[3]),
        "recorded_at": str(row[4]),
    }
    lines = _snapshot_drift("hypothesis_status_history", frozen, live)
    if not lines:
        return lines
    # THE LIVE BOUNDS ARE VALIDATED BEFORE ANY VERDICT IS COMPUTED FROM THEM
    # (Codex R3 Major 4). These are unconstrained TEXT columns, and the
    # coverage test below is a string comparison -- so closing the interval
    # with a basic-form `20260811T033500` produced an ordinary drift line and
    # NO invalidation, because the malformed value sorts AFTER the bound. A
    # reader must not manufacture a coverage verdict out of data it cannot
    # parse; it says so instead.
    for field in ("effective_from", "effective_to", "recorded_at"):
        value = live[field]
        if value is None:
            continue
        try:
            _require_naive_datetime(value, what=field)
        except CohortProvenanceCorrectionError:
            lines.append(
                f"{CITATION_ANCHOR_UNVERIFIABLE}: hypothesis_status_history "
                f"row {correction.cited_hypothesis_status_history_id}'s "
                f"{field} is {value!r}, which this surface cannot parse, so "
                "whether the interval still covers the cited window cannot be "
                "decided.")
            return lines
    # Does the interval STILL cover the window this correction proved it over?
    # Second-granular and strict, the SAME comparison the audit CHECKs make.
    upper = str(correction.cited_status_window_upper_utc)
    covers = (
        live["effective_from"][:19] < str(correction.cited_run_ts_utc)[:19]
        and (live["effective_to"] is None
             or live["effective_to"][:19] > upper[:19])
        and live["status"] == "active"
    )
    if not covers:
        lines.append(
            f"{CITATION_INVALIDATED}: the cohort assignment recorded by "
            f"correction {correction.provenance_correction_id} rests on "
            f"hypothesis_status_history row "
            f"{correction.cited_hypothesis_status_history_id} being 'active' "
            f"across [{correction.cited_run_ts_utc}, {upper}] UTC, and that "
            "interval no longer covers it."
        )
    return lines


def _derivation_input_drift(
    conn: sqlite3.Connection, correction: Any,
) -> list[str]:
    """RE-DERIVE the label and RE-READ the trade (Codex R2 Major 5).

    "No current UPDATE site" is not immutability, and a migration or an
    operator repair is exactly where an audit reader earns its keep. But
    freezing a field-by-field copy of the candidate and its criteria would need
    new columns for values that are already RECOVERABLE: the label this
    correction wrote is a total function of the candidate row, its criteria and
    the registry name, so RE-DERIVING it and comparing against
    ``applied_value_json`` catches a bucket change, a criterion change AND a
    registry rename in ONE comparison -- and catches them by the property that
    actually matters rather than by string equality on a snapshot.

    The evaluation run's two anchors are already frozen, so they are compared
    directly.

    And the TRADE ITSELF is re-read: the audit row asserts three values were
    written and nothing until now ever checked that the trade still carries
    them. That is the most direct honesty check in this file.
    """
    from swing.data.repos.candidates import (
        fetch_candidate_by_id,
        get_evaluation_run_by_id,
    )
    from swing.metrics.funnel import APLUS_TRADE_ORIGIN
    from swing.recommendations.hypothesis import _descriptive_label
    from swing.trades.entry import canonicalize_hypothesis_label

    lines: list[str] = []

    run = get_evaluation_run_by_id(
        conn, int(correction.cited_evaluation_run_id))
    if run is None:  # pragma: no cover -- ON DELETE RESTRICT
        lines.append(
            f"{CITATION_DRIFT}: the cited evaluation run "
            f"{correction.cited_evaluation_run_id} no longer exists.")
    else:
        for frozen, live, field in (
            (str(correction.cited_candidate_action_session_date),
             str(run.action_session_date), "action_session_date"),
            (str(correction.cited_run_ts_raw), str(run.run_ts), "run_ts"),
        ):
            if frozen != live:
                lines.append(
                    f"{CITATION_DRIFT}: evaluation_runs.{field} was "
                    f"{frozen!r} now {live!r}")

    applied = json.loads(correction.applied_value_json)
    cited = fetch_candidate_by_id(conn, int(correction.cited_candidate_id))
    name_row = conn.execute(
        "SELECT name FROM hypothesis_registry WHERE id = ?",
        (int(correction.cited_hypothesis_id),),
    ).fetchone()
    if cited is None or name_row is None:  # pragma: no cover -- RESTRICT
        lines.append(
            f"{CITATION_DRIFT}: the cited candidate or hypothesis registry row "
            "no longer exists.")
    else:
        if str(name_row[0]) != str(
                correction.cited_hypothesis_name_at_correction):
            lines.append(
                f"{CITATION_DRIFT}: hypothesis_registry.name was "
                f"{correction.cited_hypothesis_name_at_correction!r} now "
                f"{name_row[0]!r}")
        rederived = canonicalize_hypothesis_label(
            _descriptive_label(cited.candidate, str(name_row[0])))
        if rederived != applied.get("trades.hypothesis_label"):
            lines.append(
                f"{CITATION_DRIFT}: the label RE-DERIVED from candidate "
                f"{correction.cited_candidate_id} today is {rederived!r}, but "
                f"this correction wrote "
                f"{applied.get('trades.hypothesis_label')!r} -- the cited "
                "record's bucket, criteria or hypothesis name has moved.")
        frozen_candidate = json.loads(correction.cited_candidate_snapshot_json)
        live_candidate = candidate_provenance_snapshot(cited)
        if frozen_candidate != live_candidate:
            for key in sorted(set(frozen_candidate) | set(live_candidate)):
                if frozen_candidate.get(key) != live_candidate.get(key):
                    lines.append(
                        f"{CITATION_DRIFT}: candidates.{key} was "
                        f"{frozen_candidate.get(key)!r} now "
                        f"{live_candidate.get(key)!r}")
        # THE ORIGIN IS RE-DERIVED TOO (Codex R4 Major 2). The reader
        # re-derived the LABEL and checked the bucket, but never the origin --
        # so an audit row citing an A+ candidate with the correct label and
        # `trade_origin='pipeline_watch_manual'` reported CLEAN.
        expected_origin = (
            APLUS_TRADE_ORIGIN if str(cited.candidate.bucket) == APLUS_BUCKET
            else None)
        if applied.get("trades.trade_origin") != expected_origin:
            lines.append(
                f"{CITATION_DRIFT}: the origin RE-DERIVED from candidate "
                f"{correction.cited_candidate_id} today is "
                f"{expected_origin!r}, but this correction wrote "
                f"{applied.get('trades.trade_origin')!r}.")
        if str(cited.candidate.bucket) != APLUS_BUCKET:
            lines.append(
                f"{CITATION_DRIFT}: candidates.bucket was {APLUS_BUCKET!r} at "
                f"correction time and is {cited.candidate.bucket!r} now.")
        # CANDIDATE OWNERSHIP (Codex R3 Major 3). The audit's candidate and
        # evaluation-run FKs are INDEPENDENT, so moving the cited candidate to
        # a different run left its label and bucket unchanged and the reader
        # reported CLEAN -- while the correction's whole claim is that THIS
        # candidate came from THAT run. The run id is already frozen, so the
        # comparison costs nothing.
        if int(cited.evaluation_run_id) != int(
                correction.cited_evaluation_run_id):
            lines.append(
                f"{CITATION_DRIFT}: candidates.evaluation_run_id was "
                f"{correction.cited_evaluation_run_id} at correction time and "
                f"is {cited.evaluation_run_id} now -- the cited candidate no "
                "longer belongs to the cited run.")
        trade_ticker = conn.execute(
            "SELECT ticker FROM trades WHERE id = ?",
            (int(correction.trade_id),),
        ).fetchone()
        if trade_ticker is not None and str(
                cited.candidate.ticker) != str(trade_ticker[0]):
            lines.append(
                f"{CITATION_DRIFT}: the cited candidate is now ticker "
                f"{cited.candidate.ticker!r} while trade "
                f"{correction.trade_id} is {trade_ticker[0]!r}.")

    trade_row = conn.execute(
        "SELECT hypothesis_label, candidate_id, trade_origin FROM trades "
        "WHERE id = ?", (int(correction.trade_id),),
    ).fetchone()
    if trade_row is None:  # pragma: no cover -- ON DELETE RESTRICT
        lines.append(
            f"{CITATION_DRIFT}: trade {correction.trade_id} no longer exists.")
    else:
        live_triple = {
            "trades.hypothesis_label": trade_row[0],
            "trades.candidate_id": trade_row[1],
            "trades.trade_origin": trade_row[2],
        }
        for key in COHORT_CORRECTED_FIELDS:
            if applied.get(key) != live_triple[key]:
                lines.append(
                    f"{CITATION_DRIFT}: {key} was written as "
                    f"{applied.get(key)!r} but the trade now carries "
                    f"{live_triple[key]!r}")
    return lines


def _fill_anchor_drift(
    conn: sqlite3.Connection, correction: Any,
) -> list[str]:
    """Recompute the anchor; never merely re-read the frozen value.

    Ordering is load-bearing. **`entry_fill_id IS NULL` is CONCLUSIVE deletion
    drift and is checked FIRST, before any recomputation.** `fills.fill_id` is
    `INTEGER PRIMARY KEY` WITHOUT `AUTOINCREMENT` -- a bare rowid -- so SQLite
    REUSES the number when the deleted row held the maximum, and the
    production split handler deletes the consolidated fill and reinserts
    partials with no explicit id. Demonstrated: a date-PRESERVING split of the
    max fill reinserts a partial that comes back wearing the SAME fill_id with
    the SAME fill_datetime, so a check on `(fill_id, date)` alone reports NO
    DRIFT on a row that was deleted and replaced -- a false clean in the audit
    command. The FK's `ON DELETE SET NULL` fires at the DELETE and a later
    INSERT reusing the number does NOT restore it, which is what makes the
    NULL a reuse-proof marker.

    The recomputation goes through THE SAME LOCAL VALIDATED RESOLVER the
    authorization path uses, never `get_authoritative_entry_fill`; otherwise
    the reader would compute its verdict through the very lexical ordering
    this module forbids, hiding a malformed earlier fill and reporting NO
    drift, on a path no authorization test exercises.
    """
    lines: list[str] = []
    if correction.entry_fill_id is None:
        lines.append(
            f"{CITATION_ANCHOR_DRIFT}: the cited entry fill "
            f"{correction.entry_fill_id_at_correction} has been DELETED (the "
            "FK went NULL). The frozen snapshot still names what this "
            "correction anchored on; the row it named is gone.")
        return lines

    try:
        current = resolve_authoritative_entry_fill(
            conn, int(correction.trade_id))
    except CohortProvenanceCorrectionError as exc:
        # A reader must NOT manufacture a clean answer out of data its own
        # validator rejected.
        return [
            f"{CITATION_ANCHOR_UNVERIFIABLE}: trade {correction.trade_id} has "
            f"a malformed fill_datetime, so the anchor cannot be recomputed "
            f"({exc})."
        ]

    frozen = json.loads(correction.entry_fill_snapshot_json)
    live = current.snapshot()
    # The WHOLE frozen snapshot, not an id-and-date pair.
    for field in ("fill_id", "trade_id", "action", "fill_datetime"):
        if frozen.get(field) != live.get(field):
            lines.append(
                f"{CITATION_ANCHOR_DRIFT}: entry_fill.{field} was "
                f"{frozen.get(field)!r} at correction time and the trade's "
                f"authoritative entry fill now reports {live.get(field)!r} "
                f"(fill {current.fill_id}).")
    if lines:
        new_session = current.session_date
        for column, name in (
            (correction.cited_candidate_action_session_date,
             "the cited candidate's action session"),
            (correction.cited_recommendation_action_session_date,
             "the cited recommendation's action session"),
        ):
            if str(column) > new_session:
                lines.append(
                    f"{CITATION_INVALIDATED}: the cohort assignment recorded "
                    f"by correction {correction.provenance_correction_id} no "
                    f"longer satisfies contemporaneity -- {name} ({column}) "
                    f"post-dates the CURRENT authoritative entry fill's "
                    f"session ({new_session}).")
    return lines


def read_provenance_corrections(
    conn: sqlite3.Connection, *, trade_id: int | None = None,
) -> list[ProvenanceCorrectionReport]:
    """Every correction with its citations, its frozen anchors and any DRIFT."""
    # ONE READ SNAPSHOT FOR THE WHOLE REPORT (Codex R5 Major 3). This is the
    # EXACT defect already fixed for the preview, on the surface next door: the
    # reader runs many independent SELECTs, so a production
    # `upsert_recommendation` or a status transition committing mid-report
    # could leave it comparing half its checks against one world and half
    # against another -- and then print "no citation drift" about a citation
    # that had already moved. A drift reader that reports a MIXED image is
    # worse than one that reports a stale one, because the mixed image is not
    # a picture of any moment that ever existed.
    #
    # WAL gives a read transaction a consistent snapshot without blocking the
    # writer, so this costs concurrency nothing. Rolled back unconditionally:
    # the reader still writes nothing and still takes no write lock.
    owns_read_tx = not conn.in_transaction
    if owns_read_tx:
        conn.execute("BEGIN DEFERRED")
    try:
        return _read_provenance_corrections_inner(conn, trade_id=trade_id)
    finally:
        if owns_read_tx:
            with contextlib.suppress(sqlite3.Error):
                conn.rollback()


def _read_provenance_corrections_inner(
    conn: sqlite3.Connection, *, trade_id: int | None = None,
) -> list[ProvenanceCorrectionReport]:
    """Never opens a transaction; the caller owns the read snapshot."""
    from swing.data.repos.pipeline import evaluation_run_persistence_bound
    from swing.data.repos.provenance_corrections import (
        list_provenance_corrections,
    )
    from swing.data.repos.recommendations import snapshot_recommendation_row

    reports: list[ProvenanceCorrectionReport] = []
    for correction in list_provenance_corrections(conn, trade_id=trade_id):
        lines: list[str] = []
        lines.extend(_snapshot_drift(
            "daily_recommendations",
            json.loads(correction.cited_recommendation_snapshot_json),
            snapshot_recommendation_row(
                conn, int(correction.cited_daily_recommendation_id)),
        ))
        bound = evaluation_run_persistence_bound(
            conn, evaluation_run_id=int(correction.cited_evaluation_run_id))
        # THE CLAIM IS NARROWED, NOT THE SNAPSHOT WIDENED (Codex R5 Minor 6).
        # `pipeline_runs` has 23 columns and only the five PERSISTENCE-BOUND
        # ones are frozen. That projection is deliberate -- `lease_heartbeat_ts`,
        # `current_step`, `last_step_progress_ts` and the per-step status
        # columns churn legitimately, and freezing them would manufacture
        # constant false drift -- but the label said `pipeline_runs`, which
        # reads as a claim about the whole row. It now says what it checks.
        lines.extend(_snapshot_drift(
            "pipeline_runs[persistence-bound evidence]",
            json.loads(correction.cited_pipeline_run_snapshot_json),
            None if bound is None else bound.snapshot,
        ))
        lines.extend(_status_interval_drift(conn, correction))
        lines.extend(_derivation_input_drift(conn, correction))
        lines.extend(_fill_anchor_drift(conn, correction))
        reports.append(ProvenanceCorrectionReport(
            correction=correction, drift_lines=tuple(lines)))
    return reports
