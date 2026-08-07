"""`swing latches parity` -- the monthly execution-parity read (Arc 21-B Task 9).

READ-ONLY. This command makes NO Schwab call, writes NO row, and computes
nothing the pure classifier does not already compute: it is a RENDERER over
`swing/latches/classification.py`, so the number RD reads and the number the
tests assert are produced by the same code.

ASCII ONLY, and this binds HARD here rather than by convention: Windows
PowerShell stdout defaults to cp1252, so a single non-ASCII glyph in any line
below raises `UnicodeEncodeError` and CRASHES the command. pytest's `capsys`
bypasses the OS encoder, so a byte test cannot see it -- the subprocess test can.
"""
from __future__ import annotations

from datetime import date, datetime

import click

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.data.repos.latch_order_intents import (
    list_intents_for_latch,
    list_intents_since,
)
from swing.data.repos.latch_view_events import list_views_for_latch
from swing.latches.classification import (
    LatchDisposition,
    ParityObservation,
    TelemetryHealth,
    TelemetryWindowTooLongError,
    admissible_decisions,
    assess_telemetry_health,
    classify_latch,
    current_cycle_place,
    decision_bounds_for,
    telemetry_window_sessions,
)
from swing.latches.constants import (
    ACTIONABLE_VIEW_SURFACES,
    DISPLACED_UNANSWERABLE,
    LATCH_BROKER_ORDER_ID_KINDS,
    LATCH_DISPOSITIONS,
    R_BUCKETS,
)
from swing.latches.order_intent import canonical_duration
from swing.latches.reader import build_latch_derivation

# The report's field width, so the columns line up without a table library.
_W = 34


@click.group("latches")
def latches_group() -> None:
    """Entry-latch mandate reads (read-only)."""


# RD RULING 4 (2026-07-30) -- THE ZERO-DATA STATE MUST BE DISTINGUISHABLE FROM
# THE GOOD STATE AND MUST BE LABELLED AS UNMEASURED, for EVERY rate and EVERY
# classification this ledger reports.
#
# Imposed as a CLASS rather than defect by defect, because the class is
# structural: every failure mode of a RECORDING instrument is SILENCE, and on
# this instrument silence reads as "he did fine". Absent data yields no lapse
# recorded, no mismatch flagged and no disagreement counted -- so an unlabelled
# zero is not a neutral default, it is a favourable verdict delivered by
# omission. This is RD's labelled-reduction rule generalised from ALARMS to
# RATES, and the same reasoning that produced "a sum over nothing is not a zero"
# for the R buckets one round earlier.
#
# ONE constant, so a rate that grows a new zero-data path cannot invent a
# private spelling the reader has to learn twice.
_UNMEASURED = "NOT YET MEASURABLE"


def _fmt_rate(value: float | None) -> str:
    return _UNMEASURED if value is None else f"{value * 100:.1f}%"


def _agreement_line(report) -> str:
    """The agreement rate, or the LABELLED unmeasured state.

    `n/a (0/0)` renders a NUMBER; `NOT YET MEASURABLE` states something about
    the MEASUREMENT, and only the second keeps a reader from filing "no
    disagreements recorded" as "the framework and the operator agree". This rate
    is the arc's headline deliverable and the thing that earns stage 2, so the
    difference between "measured at 100%" and "not measured" is the whole point.
    """
    if report.agreement_denominator == 0:
        return (f"{_UNMEASURED} - no place intent yet has a broker-confirmed "
                "outcome, so there is no denominator")
    return (f"{_fmt_rate(report.agreement_rate)} "
            f"({report.agreement_numerator}/{report.agreement_denominator})")


def _framework_side(intent) -> dict | None:
    if intent is None or intent.framework_order_type is None:
        return None
    return {
        "order_type": intent.framework_order_type,
        "duration": intent.framework_duration,
        "stop_price": intent.framework_stop_price,
        "limit_price": intent.framework_limit_price,
        "quantity": intent.framework_quantity,
    }


def _actual_side(intent) -> dict | None:
    if intent is None or intent.actual_order_type is None:
        return None
    return {
        "order_type": intent.actual_order_type,
        "duration": canonical_duration(intent.actual_duration),
        "stop_price": intent.actual_stop_price,
        "limit_price": intent.actual_limit_price,
        "quantity": intent.actual_quantity,
    }


def _inferred_origin(order_intent, place_intents) -> tuple[str, str]:
    """`(inferred_origin, basis)` for one observed broker order.

    THE FIELD IS NAMED `inferred_origin` AND NEVER `origin`, and the basis is
    printed beside it. A params match is a HEURISTIC -- two identical orders are
    indistinguishable by params -- so a report presenting inference as identity
    would be an overclaim. V1 delivers distinguishability as a QUERY, not as an
    order tag; a broker-side client order id is the 21-C dependency that makes it
    exact IN GENERAL.

    The ONE place V1 IS exact is named as such: where a broker order id was
    captured on a `cancel` or `validity` row, THAT order's association with a
    ledger row is exact rather than inferred, and the report distinguishes the
    two cases rather than averaging them.
    """
    parent = order_intent.validated_place_intent_id
    if parent is not None and parent in place_intents:
        return "framework_inferred", "EXACT (captured broker order id)"
    for place in place_intents.values():
        if (place.candidate_id == order_intent.candidate_id
                and place.framework_limit_price == order_intent.actual_limit_price
                and place.framework_quantity == order_intent.actual_quantity):
            return "framework_inferred", "INFERRED (params match a place intent)"
    if any(p.candidate_id == order_intent.candidate_id
           for p in place_intents.values()):
        return "operator_inferred", "INFERRED (latch match, no place intent match)"
    return "unattributed", "INFERRED (no latch and no place intent match)"


def _family_intents(conn, latch) -> list:
    """Every intent on a latch's WHOLE candidate family, canonically ordered.

    Mirrors the panel's reader for the same reason: a latch's identity is its
    opening fire PLUS its re-confirmations, and the lifecycle resolves its
    terminal over exactly that set.
    """
    rows: list = []
    for cid in sorted(latch.candidate_set):
        rows.extend(list_intents_for_latch(conn, candidate_id=cid))
    rows.sort(key=lambda r: (r.recorded_ts, r.intent_id or 0))
    return rows


def _observations(conn, cfg, *, since_ts: str, now: datetime):
    """`(observations, health, intents_in_window, unattached, places,
    superseded_cycles)`.

    Pure reads only.

    THE CORPUS IS LATCH-DRIVEN AND THE REDUCTION IS LABELLED (Codex exec R1
    MAJOR 2). Classification is a property of a LATCH, not of an intent row, so
    the observations are built by walking `derivation.latches` -- but that means
    an intent whose latch the derivation does not produce would VANISH from a
    report that claims to read the ledger window. In practice it cannot happen
    (`candidate_id` is `NOT NULL ... ON DELETE RESTRICT`, `candidates` is
    append-only in production, and every intent was written against a latch the
    panel had already derived), and that is precisely why an UNLABELLED drop
    would be dangerous: nobody would ever look. So the count is computed and
    RENDERED. An unlabelled reduction is a quiet all-clear by omission.

    THE WINDOW SELECTS ROWS TO REPORT; IT MUST NOT TRUNCATE THE EVIDENCE THE
    CLASSIFIER REASONS FROM (Codex exec R3 MAJOR 1). Those are two different
    questions and they were being answered by one read. The arc's own worked
    case is a JULY mandate ANSWERED in August, so an August-onward read holds
    the validity row while its parent `place` sits before the cutoff: with a
    windowed intent set `governing_intent(..., "place")` returns None, rung 1
    never fires, and a latch the operator demonstrably ACCEPTED is reclassified
    as a lapse or an away -- the instrument losing evidence it is holding and
    scoring the loss against its subject. A latch's disposition is not a
    function of the calendar window someone asked about, so classification reads
    the latch's WHOLE history while `intents_in_window` stays the windowed read
    the report's ledger sections are computed from.
    """
    derivation = build_latch_derivation(conn, cfg, now=now)
    latches = list(derivation.latches)
    intents = list_intents_since(conn, since_ts=since_ts)
    by_latch: dict[int, list] = {}
    for row in intents:
        by_latch.setdefault(row.candidate_id, []).append(row)
    # THE WHOLE CANDIDATE FAMILY, matching `history` below (Codex R2 MAJOR 3).
    # An intent recorded against a RE-CONFIRMATION candidate is read by the
    # history reader and used to classify its latch, so listing it as UNATTACHED
    # would have the audit line contradict the classification computed from the
    # very same row.
    derivable = {cid for latch in latches for cid in latch.candidate_set}
    unattached = sorted(cid for cid in by_latch if cid not in derivable)

    # The FULL per-latch history -- the classifier's evidence, never the
    # report's window.
    # KEYED ON THE FIRE, READ OVER THE WHOLE CANDIDATE FAMILY (item 3a): the
    # resolver decides a terminal over `candidate_set`, so a fire-id-only read
    # would let a decision recorded against a re-confirmation clear the latch
    # while this report classified it as something else entirely.
    history: dict[int, list] = {
        latch.identity.candidate_id: _family_intents(conn, latch)
        for latch in latches
    }
    # THE PARENT LOOKUP IS NOT A WINDOW QUESTION EITHER, and this is the same
    # defect one function over: `_inferred_origin` resolves an observed broker
    # order back to the `place` that mandated it, so a cancel recorded this
    # month against a place recorded last month would read `unattributed` --
    # reporting "we cannot attribute this order" about an order the ledger CAN
    # attribute. The observed-orders LIST stays windowed; only the parent map
    # it resolves against is complete.
    places = {
        row.intent_id: row
        for rows in history.values()
        for row in rows if row.intent_kind == "place"
    }

    views: list = []
    views_by_latch: dict[int, list] = {}
    for latch in latches:
        cid = latch.identity.candidate_id
        rows = list_views_for_latch(
            conn, candidate_id=cid, surfaces=ACTIONABLE_VIEW_SURFACES)
        views_by_latch[cid] = rows
        views.extend(rows)

    # THE WINDOW MUST ENUMERATE THE SILENT SESSIONS (Codex exec R2 MAJOR 4).
    # Building it from `{view dates} | {anchors}` supplies only sessions that
    # ALREADY have a row, so `assess_telemetry_health` can never SEE a dark
    # session and `uncovered` stays near zero: a mostly-dark month with one
    # beacon hit would verdict `ok` and hand `away_unseen` straight to the away
    # rate -- manufacturing away-rate evidence out of an instrument that was
    # dark, which is the exact corruption the health gate exists to prevent.
    # The full NYSE session walk is shared with the panel so the two surfaces
    # cannot answer the same question differently.
    #
    # BOUNDED BY THE DERIVATION'S SESSION ANCHOR, NEVER BY `now.date()`. The
    # walk steps with `session_offset`, which REFUSES a non-session, so a raw
    # calendar date crashes the command outright every Saturday, Sunday and
    # market holiday -- a monthly report is exactly the thing run at a weekend.
    # `horizon_session` is `action_session_for_run`, so it is a session by
    # construction, and it is the SAME bound the panel passes: the two surfaces
    # now share the bound as well as the walk.
    #
    # AN UNASSESSABLE WINDOW WITHHOLDS; IT NEVER DEGRADES TO `ok` (Codex exec
    # R5). The walk is hard-bounded, and on an aging DB a genuinely old
    # post-epoch latch can exceed it -- at which point the honest answer is that
    # this window cannot be assessed, NOT that it was fine. Degrading to `ok`
    # here would let the classifier score never-assessed sessions as
    # `away_unseen`, which is the fabricated away-fire the whole gate exists to
    # prevent. The panel's degrade path already lands on `indeterminate`; this
    # is the same answer at the other surface.
    try:
        sessions = telemetry_window_sessions(latches, derivation.horizon_session)
        health = assess_telemetry_health(
            sessions=sessions, latches=latches, views=views)
    except TelemetryWindowTooLongError:
        health = TelemetryHealth(verdict="indeterminate")

    observations = []
    superseded: list[tuple] = []
    for latch in latches:
        cid = latch.identity.candidate_id
        latch_intents = history.get(cid, [])
        # THE SAME WINDOW THE RESOLVER USED, as on the panel. The monthly read
        # and the lifecycle must not disagree about which decision governs a
        # latch; `fill_bound` is the derivation's forward anchor, which is what
        # `service.py` `_close` passes on the production path.
        bounds = decision_bounds_for(
            latch, fill_bound=derivation.horizon_session)
        disposition: LatchDisposition = classify_latch(
            latch=latch, views=views_by_latch.get(cid, ()),
            intents=latch_intents, telemetry_health=health,
            decision_bounds=bounds)
        # THE CURRENT-CYCLE PLACE (Codex exec R7 MAJOR). Keying on the latest
        # place BY KIND meant a `place -> rejected validity -> later decline`
        # sequence reported neither the rejection (the superseded place was
        # still "the" place, so its failure was scored as the current cycle's
        # outcome only if it happened to be the same row) nor an earlier-cycle
        # line for it. The decision family resolves ONCE, here as in the
        # classifier and the panel, and every DISPLACED place -- including all of
        # them when the governing decision is a DECLINE -- enters the labelled
        # disclosure below.
        #
        # RESOLVED OVER THE SAME ADMISSIBLE VIEW THE CLASSIFIER USED (Codex R2
        # CRITICAL 1). Leaving this read unbounded while `classify_latch` reads
        # the bounded one lets the two pick DIFFERENT places for one latch, and
        # the observation then carries P1's disposition and execution outcome
        # beside P2's order data -- a single row mixing two cycles, silently
        # corrupting the agreement and delta measurements this report exists to
        # produce. One population, one governing answer.
        admissible = admissible_decisions(
            latch_intents, candidate_set=latch.candidate_set,
            lower=bounds[0], upper=bounds[1], decline_upper=bounds[2],
            upper_exclusive_kinds=(
                ("decline",) if latch.clear_reason == "fill" else ()))
        place = current_cycle_place(admissible)
        validity = _governing_validity_child(latch_intents, place)
        # EARLIER PLACE/VALIDITY CYCLES ARE LABELLED, NEVER SILENTLY DISCARDED
        # (auto-review CRITICAL 2). The resolver explicitly supports several
        # cycles on one latch -- he places, it is rejected, he re-places -- but
        # the observation reads the GOVERNING place intent only, so an initial
        # REJECTION followed by an accepted retry reported validity_failed = 0
        # and up to 100% agreement over incomplete evidence.
        #
        # THE FIX IS NOT A SECOND OBSERVATION. RD CARRY 1 fixes the ledger's
        # UNIT as the LATCH (the opportunity), and a second row for one
        # opportunity would inflate EVERY denominator -- including the away
        # rate, the number that will justify or kill stage-3 auto-place. So the
        # earlier cycles are REPORTED beside the numbers rather than folded into
        # them: the reader sees the evidence the agreement rate does not
        # contain, instead of never learning it existed.
        for earlier in latch_intents:
            if earlier.intent_kind != "place":
                continue
            if place is not None and earlier.intent_id == place.intent_id:
                continue
            # A CHILDLESS EARLIER CYCLE IS REPORTED TOO (Codex exec R6 MAJOR).
            # Skipping it meant an UNRESOLVED first attempt followed by an
            # accepted retry produced neither an earlier-cycle line nor an
            # unknown count, so the governing retry could show 100% agreement
            # over evidence the ledger was holding and not showing. An
            # unanswered cycle is exactly the absence RD's ruling 4 says must be
            # labelled rather than left to read as nothing-to-see.
            # THE OUTCOME ALONE IS NOT THE EVIDENCE (Codex exec R9 MAJOR). An
            # earlier `accepted_by_broker` cycle carrying a PRICE or QUANTITY
            # mismatch printed simply as "accepted_by_broker" while an exact
            # current retry displayed 100% agreement -- so the disclosure named
            # the cycle and still hid the divergence, which is the thing the
            # reader is being shown it for.
            # AN UNANSWERED DISPLACED CYCLE CARRIES A NAMED CATEGORY, NOT PROSE
            # (RD ruling, 2026-07-30). "unknown (never answered)" was a
            # sentence; `displaced_unanswerable` is a NAME, which is what lets
            # the report COUNT it and disclose the count beside the agreement
            # rate it was excluded from. The bias it guards is the dangerous
            # kind: a failed first attempt going permanently unmeasured while
            # its accepted retry supplies the scored agreement is a SUBSTITUTION
            # OF A SUCCESS FOR A FAILURE, not a missing datum.
            child = _governing_validity_child(latch_intents, earlier)
            superseded.append((
                cid, latch.identity.ticker, earlier.intent_id,
                DISPLACED_UNANSWERABLE if child is None
                else child.validity_outcome,
                _delta_summary(earlier, child)))
        observations.append(ParityObservation(
            disposition=disposition,
            framework=_framework_side(place),
            actual=_actual_side(validity)))
    return observations, health, intents, unattached, places, tuple(superseded)


def _delta_summary(place, validity) -> str:
    """The earlier cycle's per-field delta, or a LABELLED unmeasured state."""
    from swing.latches.order_intent import compute_order_delta
    actual = _actual_side(validity)
    if actual is None:
        return "delta NOT YET MEASURABLE (no observed order side recorded)"
    delta = compute_order_delta(_framework_side(place), actual)
    if delta.any_difference is None:
        return (f"delta NOT YET MEASURABLE (unknown: "
                f"{', '.join(delta.unknown_fields)})")
    if delta.any_difference is False:
        return "delta: none (framework and actual agree)"
    parts = []
    if delta.order_type_differs:
        parts.append("order_type")
    if delta.duration_differs:
        parts.append("duration")
    if delta.stop_leg == "compared" and delta.stop_price_delta:
        parts.append(f"stop {delta.stop_price_delta:+.2f}")
    elif delta.stop_leg == "one_sided":
        # NAMED, not numeric: one side has a stop leg and the other does not, so
        # there is no signed delta to print -- but it is a DIFFERENCE and must
        # not read as a silent zero.
        parts.append("stop leg present on one side only")
    if delta.limit_price_delta:
        parts.append(f"limit {delta.limit_price_delta:+.2f}")
    if delta.quantity_delta:
        parts.append(f"quantity {delta.quantity_delta:+d}")
    return "delta: " + ", ".join(parts)


def _governing_validity_child(intents, place):
    """The LATEST validity row FOR THAT PARENT, or `None`.

    Per-parent and never "the latest validity row for this latch", which would
    let a second place/validity cycle retroactively rewrite the first one's
    reported outcome -- the same ruling `resolve_execution_outcome` carries.
    """
    if place is None:
        return None
    children = [
        i for i in intents
        if i.intent_kind == "validity"
        and i.validated_place_intent_id == place.intent_id
    ]
    if not children:
        return None
    return max(children, key=lambda i: (i.recorded_ts, i.intent_id or 0))


def _canonical_since(since: str) -> str:
    """`--since` as a CANONICAL `YYYY-MM-DD`, or a refusal (Codex exec R3
    MAJOR 2).

    THE WINDOW IS A LEXICOGRAPHIC COMPARISON OVER A TEXT COLUMN, so a
    plausible typo does not merely look untidy -- it silently measures the wrong
    month. `recorded_ts` is TEXT and the filter is `recorded_ts >= ?`, so an
    unpadded `2026-8-1` yields the cutoff `2026-8-1T00:00:00`, which sorts ABOVE
    every `2026-0X` and `2026-1X` stamp: the read excludes almost the whole year
    and reports a confident number over a window nobody asked for. A monthly
    measurement that can be corrupted by a shell typo must FAIL CLOSED.

    The 10-char check is load-bearing ON TOP of the parse: `date.fromisoformat`
    accepts the BASIC form `20260801` on 3.11+, which would then compare wrong
    for exactly the same reason.
    """
    text = (since or "").strip()
    error = click.ClickException(
        f"--since must be a canonical ISO date of the form YYYY-MM-DD "
        f"(zero-padded); got {since!r}. The ledger window is a text "
        f"comparison, so a non-canonical date silently measures the wrong "
        f"period rather than failing.")
    if len(text) != 10:
        raise error
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        raise error from None
    if parsed.isoformat() != text:
        raise error
    return text


@latches_group.command("parity")
@click.option("--since", "since", default=None,
              help="Canonical ISO date YYYY-MM-DD; include intents RECORDED "
                   "at or after it.")
@click.pass_context
def parity_cmd(ctx: click.Context, since: str | None) -> None:
    """Print the execution-parity read over the latch ledger."""
    from swing.latches.classification import compute_execution_parity
    cfg = apply_overrides(ctx.obj["config"])
    # THE TIME AXIS IS `recorded_ts`, NOT `action_session_date`. A validity row
    # recorded in month N ABOUT a month-N-1 render belongs to month N, and a
    # post-month-end CORRECTION must not drop out of the current read. Both are
    # silent misbucketings of a measurement read once a month.
    since_ts = "" if since is None else f"{_canonical_since(since)}T00:00:00"
    conn = connect(cfg.paths.db_path)
    try:
        (observations, health, intents, unattached, places,
         superseded) = _observations(
            conn, cfg, since_ts=since_ts, now=datetime.now())
    finally:
        conn.close()
    report = compute_execution_parity(observations, health=health)

    click.echo("EXECUTION PARITY -- the latch ledger")
    click.echo("  since (recorded_ts):".ljust(_W) + (since or "the beginning"))
    click.echo("  observations (distinct latches):".ljust(_W)
               + str(report.total_observations))
    if report.total_observations == 0:
        # THE HEADLINE ZERO-DATA LABEL, stated BEFORE any histogram: a
        # disposition histogram of zeros and a delta table of zeros both read as
        # findings -- "nothing wrong was found" -- when what happened is that
        # nothing was examined.
        click.echo("  NO OBSERVATIONS -- every count and every rate below is")
        click.echo("  UNMEASURED, not clean.")
    if report.duplicate_latch_observations:
        # LABELLED, never silent: an unlabelled reduction is a quiet all-clear
        # by omission.
        click.echo("  duplicate latch rows dropped:".ljust(_W)
                   + str(report.duplicate_latch_observations))
    if unattached:
        # A LABELLED REDUCTION, not a silent one. These ledger rows exist in the
        # requested window but their latch is not derivable, so no disposition
        # could be computed for them and they are in NO bucket. That should be
        # impossible -- which is exactly why it is printed rather than dropped.
        click.echo("  LEDGER ROWS WITH NO DERIVABLE LATCH:".ljust(_W)
                   + f"{len(unattached)} (candidate_id {unattached}) -- these "
                     "are in NO bucket and NO denominator; investigate")

    click.echo("")
    click.echo("DISPOSITIONS")
    for name in sorted(LATCH_DISPOSITIONS):
        click.echo(f"  {name}:".ljust(_W)
                   + str(report.disposition_counts.get(name, 0)))

    click.echo("")
    click.echo("R BUCKETS (a partition -- every observation lands in exactly one)")
    for bucket in sorted(R_BUCKETS):
        # A SUM OVER NOTHING IS NOT A ZERO (Codex exec R4 MAJOR 3). No V1
        # emitter attributes an R to an observation, so every bucket summed to
        # 0.0 and the report printed an authoritative `+0.00R` -- a confident
        # measurement over no evidence at all, which is precisely the fabricated
        # all-clear this arc exists to refuse. Where nothing was attributed the
        # report says so and names the gap.
        attributed = report.bucket_r_attributed[bucket]
        r_text = (
            f"{report.bucket_r[bucket]:+.2f}R (R from {attributed} of "
            f"{report.bucket_counts[bucket]})"
            if attributed
            else "R UNAVAILABLE - no observation in this bucket carries one")
        click.echo(f"  {bucket}:".ljust(_W)
                   + f"{report.bucket_counts[bucket]} fires, " + r_text)
    click.echo("  pending_r is REPORTED, NEVER SCORED -- it is excluded from")
    click.echo("  every denominator, so the reader sees the pipeline rather")
    click.echo("  than a silently smaller corpus.")

    click.echo("")
    click.echo("AWAY RATE")
    away = report.away
    verdict = f"telemetry {health.verdict.upper()}"
    if away.withheld_reason:
        # TWO UNMEASURED STATES, NAMED APART (RD ruling 4). An unreliable beacon
        # and an empty corpus are different facts with different responses -- fix
        # the instrument, versus wait for a fire -- so one label for both would
        # hide a broken beacon behind a quiet start-up state. `0.0%` appears in
        # neither, because a zero away rate over nothing measured is the
        # flattering reading of the number that would justify stage-3 auto-place.
        label = ("WITHHELD" if away.unmeasured_kind == "withheld"
                 else _UNMEASURED)
        click.echo("  OBJECTIVE (primary):".ljust(_W) + f"{label} -- {verdict}")
        click.echo("  ATTESTED (upper bound):".ljust(_W)
                   + f"{label} -- {verdict}")
        click.echo(f"  reason: {away.withheld_reason}")
    else:
        click.echo("  OBJECTIVE (primary):".ljust(_W)
                   + f"{_fmt_rate(away.objective_rate)} "
                     f"({away.away_unseen_fires}/{away.classifiable_fires}) "
                     f"-- {verdict}")
        click.echo("  ATTESTED (upper bound):".ljust(_W)
                   + f"{_fmt_rate(away.attested_rate)} "
                     f"({away.away_unseen_fires + away.attested_was_away_fires}"
                     f"/{away.classifiable_fires}) -- {verdict}")
    click.echo("  coverage:".ljust(_W)
               + f"covered={health.covered_sessions} "
                 f"uncovered={health.uncovered_sessions} "
                 f"uninstrumented={health.uninstrumented_sessions}")
    click.echo("  Stage-3 auto-place reads the OBJECTIVE rate as PRIMARY and")
    click.echo("  the ATTESTED rate as an explicit UPPER BOUND. Testimony is")
    click.echo("  not telemetry.")

    click.echo("")
    click.echo("DECISION EVIDENCE KINDS (they sum to decision_r)")
    click.echo("  decision_r_logged:".ljust(_W) + str(report.decision_r_logged))
    click.echo("  decision_r_attested:".ljust(_W)
               + str(report.decision_r_attested))
    click.echo("  decision_r_inferred:".ljust(_W)
               + str(report.decision_r_inferred))
    click.echo("  decision_r:".ljust(_W)
               + str(report.bucket_counts["decision_r"]))
    if report.bucket_counts["decision_r"] == 0:
        # RD, verbatim: a discipline signal with NO terminal observations
        # renders "no observations", never "clean". Three sub-counts summing to
        # zero is precisely the shape that reads as a clean record.
        click.echo("  NO TERMINAL OBSERVATIONS -- the discipline signal is")
        click.echo(f"  {_UNMEASURED}, not clean.")

    click.echo("")
    click.echo("EXCLUSIONS (unattributable -- not scored against his judgment)")
    for name in ("pre_telemetry", "never_actionable", "telemetry_unhealthy"):
        click.echo(f"  {name}:".ljust(_W)
                   + str(report.disposition_counts.get(name, 0)))

    click.echo("")
    click.echo("AGREEMENT (framework order vs the order actually placed)")
    click.echo("  rate:".ljust(_W) + _agreement_line(report))
    # THE RATE DISCLOSES ITS OWN EXCLUSIONS, ON THE LINE UNDER IT (RD ruling,
    # 2026-07-30). A count printed twenty lines below is not a disclosure OF THE
    # RATE -- it is a separate fact the reader has to think to connect. It is
    # CONDITIONAL: a permanent caveat on a clean report is noise the reader
    # learns to skip, which is how a real one gets missed.
    unanswerable = sum(
        1 for row in superseded if row[3] == DISPLACED_UNANSWERABLE)
    click.echo(f"  {DISPLACED_UNANSWERABLE}:".ljust(_W) + str(unanswerable))
    if unanswerable:
        click.echo(f"  the rate above EXCLUDES {unanswerable} displaced place")
        click.echo("  cycle(s) with NO recorded outcome. A failed first attempt")
        click.echo("  whose accepted retry supplies the scored agreement would")
        click.echo("  otherwise read as a clean measurement.")
    click.echo("  validity UNKNOWN:".ljust(_W) + str(report.validity_unknown))
    click.echo("  validity FAILED:".ljust(_W) + str(report.validity_failed))
    click.echo("  actual side unknown:".ljust(_W)
               + str(report.actual_side_unknown))
    click.echo("  validity_unknown will DOMINATE the first months: the outcome")
    click.echo("  is only ever set by the operator answering the prompt.")
    if superseded:
        click.echo("  EARLIER PLACE/VALIDITY CYCLES NOT IN THE NUMBERS ABOVE:")
        for cid, ticker, place_id, outcome, delta in superseded:
            click.echo(f"    {ticker} (candidate {cid}) place intent "
                       f"{place_id}: {outcome}; {delta}")
        click.echo("    The ledger's UNIT is the LATCH, so one opportunity")
        click.echo("    contributes ONE observation and the agreement numbers")
        click.echo("    read its GOVERNING cycle. An earlier rejection is real")
        click.echo("    evidence that those numbers do not contain, so it is")
        click.echo("    printed here rather than dropped.")

    click.echo("")
    click.echo("PER-FIELD DELTA TOTALS")
    if report.agreement_denominator == 0:
        # Five zeros here is the most inviting misreading in the report: it
        # looks like five checks that PASSED. Nothing reached the comparison.
        click.echo(f"  {_UNMEASURED} -- no observation reached the delta")
        click.echo("  comparison, so these zeros are absences and NOT results.")
    for field in sorted(report.delta_totals):
        click.echo(f"  {field}:".ljust(_W) + str(report.delta_totals[field]))

    click.echo("")
    click.echo("OBSERVED BROKER ORDERS")
    # EVERY KIND THE SCHEMA LETS CARRY A BROKER ORDER ID (Codex exec R5 MAJOR
    # 5). `attest` was omitted, yet the writer and the schema both PERMIT
    # `actual_broker_order_id` on one -- `acted_manually` is precisely the case
    # where the operator names the order he placed by hand, which is the ONE
    # path that exists for orders the framework did not prepare. Filtering it
    # out dropped that order from the distinguishability query entirely, so
    # framework-versus-operator attribution did not survive the attestation
    # path. Derived from the ROSTER rather than re-listed, so a kind that gains
    # the column cannot be silently omitted here.
    observed = [
        i for i in intents
        if i.actual_broker_order_id
        and i.intent_kind in LATCH_BROKER_ORDER_ID_KINDS
    ]
    if not observed:
        click.echo("  none recorded in this window.")
    for row in observed:
        origin, basis = _inferred_origin(row, places)
        click.echo(f"  order {row.actual_broker_order_id} ({row.ticker}): "
                   f"inferred_origin={origin} [{basis}]")
    click.echo("  Distinguishability is a QUERY, not an order tag: a params")
    click.echo("  match is a heuristic and two identical orders are")
    click.echo("  indistinguishable by params. A broker-side client order id")
    click.echo("  is the 21-C dependency that makes this exact in general.")
