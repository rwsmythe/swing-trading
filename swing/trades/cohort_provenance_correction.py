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

import sqlite3
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from swing.data.models import PROVENANCE_CORRECTED_FIELDS
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
    "DERIVATION_RULE_SOURCE_SHA256",
    "DERIVATION_RULE_VERSION",
    "REQUIRED_RECOMMENDATION",
    "UNSET_TRADE_ORIGIN",
    "CallerHeldTransactionError",
    "CohortProvenanceCorrectionError",
    "CohortProvenanceCorrectionPreview",
    "preview_cohort_provenance_correction",
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
DERIVATION_RULE_VERSION: str = "2026-08-12.1"
DERIVATION_RULE_SOURCE_SHA256: str = (
    "5d00449acd1f16cc2b6626e843044f76118710a736790a8a506806500df9d878"
)


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
    value = raw.strip()
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
    value = raw.strip()
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise _refuse(
            f"{what} {value!r} is not a parseable ISO datetime. The column is "
            "a bare TEXT column, so a malformed value is schema-legal."
        ) from exc
    if parsed.tzinfo is not None:
        raise _refuse(
            f"{what} {value!r} carries a UTC offset or a Z suffix. That "
            "representation is UNSUPPORTED by this surface rather than "
            "silently mis-dated: its [:10] prefix is a calendar prefix, not an "
            "exchange session, and anchoring on it would land one session LATE "
            "-- i.e. more permissive. Route it to CHARC."
        )
    if value[:10] != parsed.date().isoformat():
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
            recorded_at_raw=str(row.recorded_at).strip(),
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
    if finished_parsed < anchored.run_ts_parsed:
        raise _refuse(
            f"pipeline run {bound.pipeline_run_id} finished "
            f"({bound.finished_ts}) BEFORE evaluation run {run_id} started "
            f"({anchored.run_ts_raw}); the window is inverted and cannot bound "
            "anything."
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


def _reason_or_refuse(reason: Any) -> str:
    if not isinstance(reason, str) or not reason.strip():
        raise _refuse("--reason must be a non-empty string.")
    return reason.strip()


@dataclass(frozen=True)
class _Authorized:
    anchored: _Anchored
    derived: _Derived


def _authorize(
    conn: sqlite3.Connection,
    *,
    trade_id: int,
    cited_candidate_id: int,
    cited_recommendation_id: int,
) -> _Authorized:
    """Every read-only check, in refusal-ladder order. Writes nothing."""
    anchored = _anchor_half(
        conn,
        trade_id=trade_id,
        cited_candidate_id=cited_candidate_id,
        cited_recommendation_id=cited_recommendation_id,
    )
    return _Authorized(anchored=anchored, derived=_derive(conn, anchored))


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
    _reason_or_refuse(reason)
    auth = _authorize(
        conn,
        trade_id=trade_id,
        cited_candidate_id=cited_candidate_id,
        cited_recommendation_id=cited_recommendation_id,
    )
    anchored, derived = auth.anchored, auth.derived
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
