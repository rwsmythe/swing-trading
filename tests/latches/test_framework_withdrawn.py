"""T6 -- `framework_withdrawn`, the measurement half of item 3b.

RD: *"A `criteria_lapsed` clear is a mandate the FRAMEWORK WITHDREW, not an
action the operator declined. It gets its own disposition, excluded from the
discipline signal AND from the away rate."*

THE RUNG'S PLACEMENT IS DERIVED FROM THAT RULING, NOT CHOSEN, and every edge has
its own discriminating test here: below rungs 1-3 (operator ground truth), below
rung 4 (residual R3 -- RD ruled only rung 5), ABOVE rung 5 (OQ-16), above rung 6
(no `discipline_lapse`) and above rung 7 (no `away_unseen`, which is where the
requirement actually bites).
"""
from __future__ import annotations

from datetime import date

from swing.latches.classification import (
    PROMPT_DISPOSITIONS,
    TelemetryHealth,
    classify_latch,
    compute_away_rate,
    r_bucket_for,
)
from swing.latches.constants import (
    ATTESTED_AWAY_DISPOSITIONS,
    AWAY_RATE_COUNTED_DISPOSITIONS,
    DECISION_DISPOSITIONS,
    LATCH_DISPOSITIONS,
    LATCH_TELEMETRY_EPOCH_SESSION,
    PENDING_DISPOSITIONS,
    UNATTRIBUTABLE_DISPOSITIONS,
    _RULED_DISPOSITIONS,
)

from tests.latches.test_classification import _intent, _latch, _view

EPOCH = LATCH_TELEMETRY_EPOCH_SESSION          # date(2026, 7, 29)
LAST = date(2026, 8, 12)


def _withdrawn(anchor: date = EPOCH, last: date = LAST):
    return _latch(anchor=anchor, last=last, state="horizon_expired",
                  clear_reason="criteria_lapsed", clear_session=last)


def test_framework_withdrawn_is_in_the_vocabulary_and_buckets_unattributable():
    """T6.3. `UNATTRIBUTABLE_DISPOSITIONS` is DERIVED by subtraction, so adding
    the disposition to `_ALL_EXCLUDED_DISPOSITIONS` routes it without a second
    edit -- and the TERMINALITY gate is not bypassed."""
    assert "framework_withdrawn" in LATCH_DISPOSITIONS
    assert "framework_withdrawn" in UNATTRIBUTABLE_DISPOSITIONS
    assert r_bucket_for("framework_withdrawn", is_terminal=True) == (
        "unattributable_r")
    assert r_bucket_for("framework_withdrawn", is_terminal=False) == "pending_r"


def test_the_bucket_sets_are_a_PARTITION_asserted_directly():
    """T6.10 -- and T6.1 ALONE IS NOT SUFFICIENT, which an earlier draft of the
    plan claimed it was.

    `UNATTRIBUTABLE_DISPOSITIONS` subtracts `AWAY_RATE_COUNTED_DISPOSITIONS` and
    `ATTESTED_AWAY_DISPOSITIONS` -- it does NOT subtract
    `DECISION_DISPOSITIONS`. So a disposition added to BOTH
    `_ALL_EXCLUDED_DISPOSITIONS` and `DECISION_DISPOSITIONS` stays in
    `UNATTRIBUTABLE_DISPOSITIONS`, and because `r_bucket_for` tests
    unattributable BEFORE decision it still returns `unattributable_r` -- so the
    rate arithmetic looks correct while the sets are incoherent, and T6.1 passes
    over it.

    A property this design depends on must be CHECKED, not inferred from the
    shape of an expression. Iterating the sets is what makes a SIXTH bucket gain
    the assertion automatically.
    """
    buckets = {
        "away_r": AWAY_RATE_COUNTED_DISPOSITIONS,
        "attested_away_r": ATTESTED_AWAY_DISPOSITIONS,
        "unattributable_r": UNATTRIBUTABLE_DISPOSITIONS,
        "decision_r": DECISION_DISPOSITIONS,
        "pending_r": PENDING_DISPOSITIONS,
    }
    names = sorted(buckets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not (buckets[a] & buckets[b]), f"{a} and {b} overlap"
    assert set().union(*buckets.values()) == set(_RULED_DISPOSITIONS)


def test_the_rung_PRE_EMPTS_discipline_lapse_and_keys_on_the_REASON():
    """T6.4.

    (a) A TERMINAL `criteria_lapsed` latch with actionable view rows and NO
        intents classifies `framework_withdrawn`. Without the rung it
        classifies `discipline_lapse` -- charging the operator for failing to
        act on a mandate the framework RETRACTED.

    (b) THE SIBLING THAT MAKES (a) MEAN ANYTHING. Under Option B an ordinary
        `horizon` latch carries the IDENTICAL `state == "horizon_expired"`, so a
        rung written `if latch.state == "horizon_expired"` passes (a) and every
        other positive lapse test while silently RE-LABELLING every
        horizon-expired latch -- removing real discipline evidence from the
        signal. This is the caller-side obligation Option B creates (gotcha
        #31), in the same sense as the render and severity pins.
    """
    lapsed = _withdrawn()
    assert classify_latch(
        latch=lapsed, views=[_view(EPOCH)]).disposition == "framework_withdrawn"

    expired = _latch(anchor=EPOCH, last=LAST, state="horizon_expired",
                     clear_reason="horizon", clear_session=LAST)
    assert expired.state == lapsed.state == "horizon_expired"
    assert classify_latch(
        latch=expired, views=[_view(EPOCH)]).disposition == "discipline_lapse"


def test_the_rung_PRE_EMPTS_away_unseen_which_is_where_the_ruling_bites():
    """T6.6 -- THE TEST THAT PINS THE PLACEMENT.

    A TERMINAL `criteria_lapsed` latch with FULL coverage, health `ok`, and NO
    view rows at all.

    Discriminator: with the rung below rung 7 it classifies `away_unseen`, which
    is `away_r` -- putting the withdrawn mandate INSIDE the away rate RD
    explicitly excluded it from. Placing it above rung 6 alone does not catch
    this, which is why rung 7 is the binding reason rather than rung 6.
    """
    got = classify_latch(latch=_withdrawn(), views=[])
    assert got.disposition == "framework_withdrawn"
    assert r_bucket_for(got.disposition, is_terminal=True) == "unattributable_r"


def test_the_rung_does_NOT_swallow_an_operator_decision():
    """T6.5. Rungs 1-3 are operator GROUND TRUTH: if he placed an order that
    stays `accepted`, and a later framework withdrawal cannot retroactively
    un-decide what he did.

    Discriminator: fails if the rung sits above rungs 1-3.
    """
    latch = _withdrawn()
    place = _intent("place", intent_id=1, recorded_ts="2026-08-03T10:00:00")
    assert classify_latch(
        latch=latch, views=[_view(EPOCH)], intents=[place],
    ).disposition == "accepted"
    decline = _intent("decline", intent_id=2, recorded_ts="2026-08-03T10:00:00")
    assert classify_latch(
        latch=latch, views=[_view(EPOCH)], intents=[decline],
    ).disposition == "declined"


def test_the_rung_does_NOT_pre_empt_rung_4s_pre_telemetry():
    """T6.7 -- residual R3, pinned AS RULED rather than as extended.

    OQ-16's argument (the withdrawal is authored independently of the beacon)
    applies verbatim to rung 4's `pre_telemetry`, which is equally a
    telemetry-coverage claim. RD RULED ONLY ON RUNG 5, so the rung sits BETWEEN
    rungs 4 and 5 and a `criteria_lapsed` latch in an UNCOVERED window still
    labels `pre_telemetry` -- preserving rung 4's own stated invariant that it
    is "THE ONLY ROUTE" there, and landing in the same bucket either way.

    A one-line move if he rules the extension.
    """
    anchor = date(2026, 7, 1)          # BEFORE the telemetry epoch
    latch = _latch(anchor=anchor, last=date(2026, 7, 20),
                   state="horizon_expired", clear_reason="criteria_lapsed",
                   clear_session=date(2026, 7, 20))
    assert classify_latch(latch=latch, views=[]).disposition == "pre_telemetry"


def test_the_rung_sits_ABOVE_telemetry_health():
    """T6.11 -- OQ-16 RULED, asserted as a LITERAL rather than "whichever OQ-16
    rules", which would let a wrong below-health implementation be blessed by a
    test written to match it.

    RD: "the withdrawal is authored by the structural-verdict + archive chain,
    which is INDEPENDENT of the view-telemetry beacon -- labelling it
    `telemetry_unhealthy` asserts a false cause." His refinement to record: rung
    5 gates classifications that DEPEND on view telemetry (away / lapse /
    attest); it must not swallow classifications that do not.

    The RATES are invariant either way -- only the LABEL moves -- which is what
    makes this a labelling ruling rather than a measurement one.
    """
    got = classify_latch(
        latch=_withdrawn(), views=[_view(EPOCH)],
        telemetry_health=TelemetryHealth(verdict="broken"))
    assert got.disposition == "framework_withdrawn"
    # And the rate arithmetic is untouched by the edge.
    assert r_bucket_for(got.disposition, is_terminal=True) == "unattributable_r"


def test_framework_withdrawn_never_prompts():
    """T6.8, and the NON-membership is load-bearing rather than incidental:
    prompting a man to attest about a mandate THE SYSTEM RETRACTED is the purest
    form of the train-the-dismissal-reflex failure `PROMPT_DISPOSITIONS`' own
    comment names."""
    got = classify_latch(latch=_withdrawn(), views=[_view(EPOCH)])
    assert got.prompt_required is False
    assert "framework_withdrawn" not in PROMPT_DISPOSITIONS


def test_a_withdrawn_fire_leaves_BOTH_the_away_rate_and_the_denominator():
    """T6.1 + T6.2. Corpus: 1 framework_withdrawn + 1 away_unseen + 1 accepted,
    all terminal, health ok.

    `classifiable_fires = decision_r + away_r + attested_away_r`, and
    `unattributable_r` is in NONE of them -- so the withdrawal leaves the
    DENOMINATOR too, which is the stronger and correct reading of "excluded".

    Discriminators: in `AWAY_RATE_COUNTED_DISPOSITIONS` the rate reads 2/3 over
    3 classifiable; classified `discipline_lapse` it lands in `decision_r` and
    the discipline signal counts a lapse the operator never had a chance to
    avoid.
    """
    counts: dict[str, int] = {}
    for disposition in ("framework_withdrawn", "away_unseen", "accepted"):
        bucket = r_bucket_for(disposition, is_terminal=True)
        counts[bucket] = counts.get(bucket, 0) + 1
    assert counts == {"unattributable_r": 1, "away_r": 1, "decision_r": 1}
    result = compute_away_rate(
        bucket_counts=counts, health=TelemetryHealth(verdict="ok"))
    assert result.classifiable_fires == 2
    assert result.objective_rate == 0.5


def test_the_ruled_dispositions_conclusion_still_holds():
    """T6.9. The shipped `_RULED_DISPOSITIONS == LATCH_DISPOSITIONS` conclusion
    catches a half-done edit -- a disposition added to the enum without anyone
    ruling which bucket it belongs to."""
    assert set(_RULED_DISPOSITIONS) == set(LATCH_DISPOSITIONS)
