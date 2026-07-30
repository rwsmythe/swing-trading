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

from datetime import datetime

import click

from swing.config_overrides import apply_overrides
from swing.data.db import connect
from swing.data.repos.latch_order_intents import list_intents_since
from swing.data.repos.latch_view_events import list_views_for_latch
from swing.latches.classification import (
    LatchDisposition,
    ParityObservation,
    assess_telemetry_health,
    classify_latch,
    governing_intent,
    telemetry_window_sessions,
)
from swing.latches.constants import (
    ACTIONABLE_VIEW_SURFACES,
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


def _fmt_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


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


def _observations(conn, cfg, *, since_ts: str, now: datetime):
    """`(observations, health, intents_in_window, unattached)`. Pure reads only.

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
    """
    derivation = build_latch_derivation(conn, cfg, now=now)
    latches = list(derivation.latches)
    intents = list_intents_since(conn, since_ts=since_ts)
    by_latch: dict[int, list] = {}
    for row in intents:
        by_latch.setdefault(row.candidate_id, []).append(row)
    derivable = {latch.identity.candidate_id for latch in latches}
    unattached = sorted(cid for cid in by_latch if cid not in derivable)

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
    sessions = telemetry_window_sessions(latches, derivation.horizon_session)
    health = assess_telemetry_health(
        sessions=sessions, latches=latches, views=views)

    observations = []
    for latch in latches:
        cid = latch.identity.candidate_id
        latch_intents = by_latch.get(cid, [])
        disposition: LatchDisposition = classify_latch(
            latch=latch, views=views_by_latch.get(cid, ()),
            intents=latch_intents, telemetry_health=health)
        place = governing_intent(latch_intents, "place")
        validity = None
        if place is not None:
            children = [
                i for i in latch_intents
                if i.intent_kind == "validity"
                and i.validated_place_intent_id == place.intent_id
            ]
            if children:
                validity = max(
                    children, key=lambda i: (i.recorded_ts, i.intent_id or 0))
        observations.append(ParityObservation(
            disposition=disposition,
            framework=_framework_side(place),
            actual=_actual_side(validity)))
    return observations, health, intents, unattached


@latches_group.command("parity")
@click.option("--since", "since", default=None,
              help="ISO date; include intents RECORDED at or after it.")
@click.pass_context
def parity_cmd(ctx: click.Context, since: str | None) -> None:
    """Print the execution-parity read over the latch ledger."""
    from swing.latches.classification import compute_execution_parity
    cfg = apply_overrides(ctx.obj["config"])
    # THE TIME AXIS IS `recorded_ts`, NOT `action_session_date`. A validity row
    # recorded in month N ABOUT a month-N-1 render belongs to month N, and a
    # post-month-end CORRECTION must not drop out of the current read. Both are
    # silent misbucketings of a measurement read once a month.
    since_ts = "" if since is None else f"{since}T00:00:00"
    conn = connect(cfg.paths.db_path)
    try:
        observations, health, intents, unattached = _observations(
            conn, cfg, since_ts=since_ts, now=datetime.now())
    finally:
        conn.close()
    report = compute_execution_parity(observations, health=health)

    click.echo("EXECUTION PARITY -- the latch ledger")
    click.echo("  since (recorded_ts):".ljust(_W) + (since or "the beginning"))
    click.echo("  observations (distinct latches):".ljust(_W)
               + str(report.total_observations))
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
        click.echo(f"  {bucket}:".ljust(_W)
                   + f"{report.bucket_counts[bucket]} fires, "
                     f"{report.bucket_r[bucket]:+.2f}R")
    click.echo("  pending_r is REPORTED, NEVER SCORED -- it is excluded from")
    click.echo("  every denominator, so the reader sees the pipeline rather")
    click.echo("  than a silently smaller corpus.")

    click.echo("")
    click.echo("AWAY RATE")
    away = report.away
    verdict = f"telemetry {health.verdict.upper()}"
    if away.withheld_reason:
        click.echo("  OBJECTIVE (primary):".ljust(_W)
                   + f"WITHHELD -- {verdict}")
        click.echo("  ATTESTED (upper bound):".ljust(_W)
                   + f"WITHHELD -- {verdict}")
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

    click.echo("")
    click.echo("EXCLUSIONS (unattributable -- not scored against his judgment)")
    for name in ("pre_telemetry", "never_actionable", "telemetry_unhealthy"):
        click.echo(f"  {name}:".ljust(_W)
                   + str(report.disposition_counts.get(name, 0)))

    click.echo("")
    click.echo("AGREEMENT (framework order vs the order actually placed)")
    click.echo("  rate:".ljust(_W)
               + (f"{_fmt_rate(report.agreement_rate)} "
                  f"({report.agreement_numerator}/"
                  f"{report.agreement_denominator})"))
    click.echo("  validity UNKNOWN:".ljust(_W) + str(report.validity_unknown))
    click.echo("  validity FAILED:".ljust(_W) + str(report.validity_failed))
    click.echo("  actual side unknown:".ljust(_W)
               + str(report.actual_side_unknown))
    click.echo("  validity_unknown will DOMINATE the first months: the outcome")
    click.echo("  is only ever set by the operator answering the prompt.")

    click.echo("")
    click.echo("PER-FIELD DELTA TOTALS")
    for field in sorted(report.delta_totals):
        click.echo(f"  {field}:".ljust(_W) + str(report.delta_totals[field]))

    click.echo("")
    click.echo("OBSERVED BROKER ORDERS")
    places = {i.intent_id: i for i in intents if i.intent_kind == "place"}
    observed = [
        i for i in intents
        if i.actual_broker_order_id and i.intent_kind in ("validity", "cancel")
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
