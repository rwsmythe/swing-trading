"""T7 -- the criteria-lapse render (item 3b, Task 7).

The card is a claim about the mandate's state NOW, so every string here is
checked for the FALSEHOOD it would state if the branch were wrong, not merely
for presence.
"""
from __future__ import annotations

import pathlib
from datetime import date

from swing.latches.identity import LatchIdentity
from swing.latches.models import Latch
from swing.web.view_models.latches import (
    _lapse_countdown,
    _lapse_detail,
    _state_label,
    _unverifiable_label,
)

D = [date(2026, 7, 28), date(2026, 7, 29), date(2026, 7, 30),
     date(2026, 7, 31), date(2026, 8, 3)]


def _latch(**kw) -> Latch:
    base = dict(
        identity=LatchIdentity(
            candidate_id=8851, evaluation_run_id=126, ticker="VSTS",
            detection_date="2026-07-27", pipeline_run_id=140),
        latched_pivot=16.90, latched_initial_stop=13.40, zone_cap=17.4070,
        anchor=date(2026, 7, 27), horizon_expiry=date(2026, 9, 8),
        sessions_elapsed=5, sessions_to_horizon=25, state="armed")
    base.update(kw)
    return Latch(**base)


# ---------------------------------------------------------------------------
# T7.1 -- the UNVERIFIABLE render
# ---------------------------------------------------------------------------
def test_an_off_screen_live_latch_renders_UNVERIFIABLE_and_names_the_count():
    """T7.1. ONE unchecked session at the TAIL is enough: the claim being
    withheld is "the framework checked this mandate for the session you are
    about to trade", and one unchecked session falsifies it.

    It is a RENDER attribute of a LIVE latch -- the mandate is still live and
    still fillable, so a terminal state would be a FALSE statement. The in-tree
    precedent is exact: zone escape is an attribute of `armed`, never a clear
    reason.
    """
    latch = _latch(
        lapse_failed_sessions=(D[0], D[1], D[2]), lapse_failed_count=3,
        lapse_unverifiable_sessions=(D[3],),
        lapse_unverifiable_causes=("absent",),
        lapse_unchecked_count=1, lapse_unverifiable_tail=1)
    label = _unverifiable_label(latch)
    assert "UNVERIFIABLE - OFF SCREEN" in label
    assert "last 1 evaluated session" in label
    assert latch.is_live                       # NOT a terminal state
    assert _state_label(latch, "unknown") == "ARMED"


def test_a_currently_checked_live_latch_renders_NO_unverifiable_banner():
    """The bound. Without it, an implementation that always rendered the banner
    passes the test above and shouts on every healthy card -- which is how a
    real warning stops being read."""
    latch = _latch(lapse_failed_sessions=(D[0],), lapse_failed_count=1)
    assert _unverifiable_label(latch) == ""


def test_a_TERMINAL_latch_renders_neither_banner_nor_countdown():
    """A terminated mandate is not awaiting a check and has no countdown left
    to run."""
    latch = _latch(state="horizon_expired", clear_reason="criteria_lapsed",
                   clear_session=D[4], lapse_unverifiable_tail=2,
                   lapse_unverifiable_sessions=(D[2], D[3]),
                   lapse_unverifiable_causes=("absent", "absent"),
                   lapse_unchecked_count=2)
    assert _unverifiable_label(latch) == ""
    assert _lapse_countdown(latch, sessions=5) == ""


# ---------------------------------------------------------------------------
# T7.3 / T7.9 -- the countdown
# ---------------------------------------------------------------------------
def test_the_countdown_DISCLOSES_the_unchecked_sessions():
    """T7.3 + T7.9. The bare form "failed 3 of 5" reads as three CONSECUTIVE
    sessions, when the algorithm skips arbitrarily many UNVERIFIABLE ones in
    between -- three failures separated by twenty unchecked runs would render
    identically to three in a row.

    Disclosing the gap is what stops the countdown itself being a false
    statement, and it is the condition under which OQ-17's PAUSE is sound at
    all: the structural evidence is sparse, and the card says so.
    """
    latch = _latch(
        lapse_failed_sessions=(D[1], D[3]), lapse_failed_count=2,
        lapse_unverifiable_sessions=(D[0], D[2]),
        lapse_unverifiable_causes=("absent", "absent"),
        lapse_unchecked_count=2)
    assert _lapse_countdown(latch, sessions=5) == (
        "failed 2 of 5 checked sessions (2 unchecked)")


def test_the_countdown_states_NOT_EVALUABLE_when_the_directional_half_has_no_data():
    """T7.3's second half (ruling 2a). The structural and directional halves
    fail INDEPENDENTLY: the gate can be perfectly checkable while the archive
    cannot support the completeness requirement.

    Discriminator: a card showing "failed 4 of 5" beside a plain live status
    while the directional predicate had NO DATA tells the operator a withdrawal
    is one session away when it is in fact UNREACHABLE.
    """
    latch = _latch(
        lapse_failed_sessions=(D[0], D[1], D[2], D[3]), lapse_failed_count=4,
        directional_evaluable=False,
        directional_block_reason="archive gap 2026-07-24")
    got = _lapse_countdown(latch, sessions=5)
    assert "failed 4 of 5 checked sessions (0 unchecked)" in got
    assert "directional test NOT EVALUABLE (archive gap 2026-07-24)" in got


def test_the_over_threshold_card_distinguishes_BOTH_reasons_it_is_still_live():
    """T7.11 -- and the second branch is the one that catches the falsehood.

    (a) `k = 8` against `N = 5`, still live because lifetime 2a REFUSES.
    (b) THE REPORT-ONLY BRANCH: `k >= N`, the conjuncts MET, unarmed, so
        `lapse_would_clear_session` is populated.

    Discriminator for (b): an implementation that keeps printing "directional
    condition NOT MET" in report-only mode passes (a) and every T4 resolver test
    while telling the operator a condition did not meet WHEN IT DID -- on the one
    surface whose entire purpose is showing him what the unarmed rule is doing.
    `directional_evaluable` does not disambiguate them: it says the test COULD
    run, not that it passed.

    Neither branch renders the nonsensical "8 of 5".
    """
    failed = (D[0], D[1], D[2], D[3], D[4], date(2026, 8, 4),
              date(2026, 8, 5), date(2026, 8, 6))
    refused = _latch(lapse_failed_sessions=failed, lapse_failed_count=8)
    got_a = _lapse_countdown(refused, sessions=5)
    assert got_a == "8 failures; threshold 5; directional condition NOT MET"
    assert "8 of 5" not in got_a

    met = _latch(lapse_failed_sessions=failed, lapse_failed_count=8,
                 lapse_qualifying_session=D[4],
                 lapse_would_clear_session=D[4])
    got_b = _lapse_countdown(met, sessions=5)
    assert got_b == ("8 failures; threshold 5; WOULD WITHDRAW on 2026-08-03 - "
                     "REPORT ONLY (not armed)")
    assert "NOT MET" not in got_b
    assert "8 of 5" not in got_b


def test_the_countdown_tracks_the_N_IN_FORCE_rather_than_a_literal():
    """Section 3.2.1 ruling 7: N is a deliberate calibration and changing it
    REWRITES history, so the panel states the N actually in force. An
    implementation hard-coding 5 renders a false threshold the moment the
    operator retunes it."""
    latch = _latch(lapse_failed_sessions=(D[0],), lapse_failed_count=1)
    assert "of 7 checked" in _lapse_countdown(latch, sessions=7)


# ---------------------------------------------------------------------------
# T7.10 / T7.13 -- the detail line
# ---------------------------------------------------------------------------
def test_the_detail_line_NAMES_the_sessions_and_their_causes():
    """T7.10(a). A card carrying only COUNTS can render NEITHER the named
    sessions the PAUSE disclosure requires NOR the cause the detail line owes
    the operator -- without either inventing fields or recomputing the streak in
    the view, which is the duplication this arc exists to prevent."""
    latch = _latch(
        lapse_failed_sessions=(D[0], D[1], D[2]), lapse_failed_count=3,
        lapse_unverifiable_sessions=(D[3],),
        lapse_unverifiable_causes=("sentinel_row",), lapse_unchecked_count=1)
    got = _lapse_detail(latch)
    assert "failed: 2026-07-28, 2026-07-29, 2026-07-30" in got
    assert "unchecked: 2026-07-31 (sentinel_row)" in got


def test_the_detail_line_is_read_from_the_LATCH_not_recomputed():
    """T7.10(b) -- PROVENANCE, OBSERVED RATHER THAN ASSERTED.

    On a CONSISTENT fixture a reading VM and a recomputing VM render
    IDENTICALLY, so "assert the VM reads them" is untestable as stated. So the
    inputs are POISONED: the `Latch` names sessions no plausible recomputation
    would produce, and the card must render the LATCH's dates.

    A VM that re-derived the streak renders the other set and fails. (The view
    is also never handed the verdict sequence at all, so recomputation is
    impossible by construction -- this test pins that it stays so.)
    """
    poisoned = (date(2001, 1, 2), date(2001, 1, 3))
    latch = _latch(lapse_failed_sessions=poisoned, lapse_failed_count=2)
    got = _lapse_detail(latch)
    assert "2001-01-02, 2001-01-03" in got


def test_the_conflict_signal_reaches_the_card():
    """T7.13 -- OQ-15's addition, render half.

    Discriminator: an implementation that resolves generously and carries
    `conflicted` no further renders NOTHING, and the ambiguity RD required to be
    SURFACED is silently absorbed -- the flattering-by-omission shape his 21-A
    same-session-duplicate rule forbids.
    """
    latch = _latch(
        lapse_failed_sessions=(D[2],), lapse_failed_count=1,
        lapse_conflicted_sessions=(D[0],))
    got = _lapse_detail(latch)
    assert "conflicting verdicts: 2026-07-28" in got


def test_every_added_render_string_is_ASCII():
    """T7.7. Windows cp1252 stdout crashes on a non-ASCII glyph, and pytest
    capsys hides it."""
    latch = _latch(
        lapse_failed_sessions=(D[0], D[1]), lapse_failed_count=2,
        lapse_unverifiable_sessions=(D[2],),
        lapse_unverifiable_causes=("absent",), lapse_unchecked_count=1,
        lapse_unverifiable_tail=1, lapse_conflicted_sessions=(D[3],),
        directional_evaluable=False, directional_block_reason="archive gap")
    for text in (_lapse_countdown(latch, sessions=5), _lapse_detail(latch),
                 _unverifiable_label(latch)):
        text.encode("ascii")          # raises on any non-ASCII glyph


# ---------------------------------------------------------------------------
# T7.4 / T7.8 -- UNVERIFIABLE adds NO suppression of its own
# ---------------------------------------------------------------------------
def test_being_UNVERIFIABLE_adds_NO_new_prepared_order_suppression():
    """T7.4, NARROWED to what the source actually supports.

    The requirement is NOT "the prepared order is always offered on an
    UNVERIFIABLE latch" -- 21-B withholds it for its own reasons
    (`regime_undeterminable` / `sizing_infeasible` / `sizing_degenerate`), and an
    off-screen latch with an uncorroborated close may legitimately hit
    `regime_undeterminable`. The testable requirement is that for a PAIR of
    latches identical except that one is UNVERIFIABLE, the offered/withheld
    outcome is the SAME.

    AND THE CONTROL LATCH IS BUILT SO THE ORDER IS ACTUALLY OFFERED -- if the
    pair were built carelessly and BOTH hit `regime_undeterminable`, both would
    be withheld before and after an erroneous UNVERIFIABLE suppression and the
    equality assertion would pass over the exact defect it names.

    Discriminator: fails if UNVERIFIABLE is implemented by adding a suppression
    of its own -- the alarm-gates-the-affordance defect item 4 of this queue
    exists to remove.
    """
    from swing.latches.order_intent import SizingInputs, compute_prepared_order

    sizing = SizingInputs(
        real_equity=1300.0, equity_floor=7500.0, sizing_equity=7500.0,
        max_risk_pct=0.005, position_pct_cap=0.15)
    checked = _latch(lapse_failed_sessions=(D[0],), lapse_failed_count=1)
    unverifiable = _latch(
        lapse_failed_sessions=(D[0],), lapse_failed_count=1,
        lapse_unverifiable_sessions=(D[3],),
        lapse_unverifiable_causes=("absent",), lapse_unchecked_count=1,
        lapse_unverifiable_tail=1)
    kw = dict(regime_order_type="STOP_LIMIT", regime_close=15.58,
              regime_close_session="2026-07-31", sizing_inputs=sizing)
    a = compute_prepared_order(latch=checked, **kw)
    b = compute_prepared_order(latch=unverifiable, **kw)
    # The CONTROL is genuinely OFFERED, or the equality below proves nothing.
    assert a.order is not None and a.withheld_reason is None
    assert (b.order is None) == (a.order is None)
    assert b.withheld_reason == a.withheld_reason
    assert b.order == a.order


def test_the_DECISION_control_still_rides_on_the_prepared_order_block_TODAY():
    """T7.8 -- RECORDED AS A PINNED COST, NOT FIXED HERE, and the boundary is
    deliberate.

    Section 3.2.1 ruling 4 requires the DECLINE control to remain available even
    when the prepared-order form is WITHHELD: a latch the framework cannot price
    is exactly the one whose mandate the operator most needs to resolve, and
    gating his answer on the form's availability re-creates the item-4 defect
    one surface over.

    THE SHIPPED TEMPLATE PUTS THE DECLINE BUTTON INSIDE `{% if po.offered %}`,
    so today it does NOT survive a withheld form. Item 3a built exactly this
    affordance, then REVERTED it -- a POST-only widening reachable solely by
    replaying a pre-decline form is a stale-form hole dressed as a corrective
    path -- and RD SIGNED OFF on routing the render/route half to wave item 4,
    which already owns the governing principle. Fixing it here would re-open a
    scope he closed.

    So this test pins the CURRENT shape and names what flips when item 4 ships,
    the same way 3a pinned its own reversal cost. It is a FLAG with a failing
    condition attached, not an endorsement.
    """
    partial = (pathlib.Path(__file__).resolve().parents[3]
               / "swing" / "web" / "templates" / "partials"
               / "latch_prepared_order.html.j2").read_text(encoding="utf-8")
    offered_at = partial.index("{% if po.offered %}")
    decline_at = partial.index('value="decline"')
    withheld_at = partial.index("po.withheld_detail")
    # The decline control lives INSIDE the offered branch -- above the withheld
    # paragraph -- which is precisely the gating item 4 must remove.
    assert offered_at < decline_at < withheld_at
