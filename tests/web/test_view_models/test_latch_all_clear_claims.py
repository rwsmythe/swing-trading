"""B6 (Arc 21-B) -- the SEPARATED-CLAIMS construction, at the VM.

The route-level suite (`tests/web/test_routes/test_latches_orders_fragment.py`)
covers the zero-case, the all-checked case and the findings-branch
unreachability against the real builder. It CANNOT cover a MIXED
pending+permanent page: `_build_form_check_notes` reads
`count_session_recorded_closes` ONCE per fragment, so every note on a given
render shares one severity by construction. The mixed case is nonetheless the
whole point of B6 -- carrying the pending-vs-permanent distinction into the
page-level line -- so it is pinned HERE, where the VM can be constructed
directly, rather than left unpinned because the builder cannot reach it.
"""
from __future__ import annotations

from swing.web.view_models.latches import (
    _FORM_CHECK_CLAIM_PHRASINGS,
    _FORM_CHECK_HEADLINES,
    LatchOrdersFragmentVM,
    MandateFormCheckVM,
)


def _note(ticker: str, severity: str) -> MandateFormCheckVM:
    return MandateFormCheckVM(
        ticker=ticker, severity=severity,
        headline=f"headline-{severity}", detail=f"detail-{severity}")


def _vm(notes: tuple[MandateFormCheckVM, ...], ran: int) -> LatchOrdersFragmentVM:
    return LatchOrdersFragmentVM(
        available=True, resolution_kind="ok", resolution_detail="",
        alarms=(), order_lines=(),
        mandate_form_check_skipped=notes, form_check_ran_count=ran)


def test_a_mixed_page_states_pending_and_permanent_as_separate_claims():
    """The B6 refinement itself. The superseded sentence lumped a
    self-resolving WAIT together with a permanently-inert latch behind one
    undifferentiated 'not form-checked' count; the operator could not tell which
    latches would clear on the next nightly and which never will."""
    vm = _vm((_note("FTRE", "pending"), _note("AMN", "permanent"),
              _note("VSTS", "permanent")), ran=2)
    assert vm.all_clear_claims == (
        "No alarms.",
        "Mandate-form check pending for 1 latch.",
        "Mandate-form check inert for 2 latches - see the labels below.",
    )
    assert vm.all_clear_note == " ".join(vm.all_clear_claims)


def test_the_unknown_severity_gets_its_own_claim_and_is_never_folded_in():
    """`unknown` means the panel could not tell pending from permanent. Folding
    it into either would be the panel asserting the very thing it just said it
    could not determine."""
    vm = _vm((_note("FTRE", "unknown"), _note("AMN", "pending")), ran=0)
    assert vm.all_clear_claims == (
        "No alarms.",
        "Mandate-form check pending for 1 latch.",
        "Mandate-form check status unknown for 1 latch.",
    )


def test_the_alarm_all_clear_is_unscoped_and_carries_no_denominator():
    """The claim is COMPLETE, not scoped: only the two-form SELECTION is ever
    skipped. A denominator would re-import the scoping that made the zero-case
    vacuous."""
    vm = _vm((_note("FTRE", "pending"),), ran=0)
    assert vm.all_clear_claims[0] == "No alarms."
    assert "among the" not in vm.all_clear_note
    assert "form-checked" not in vm.all_clear_note
    # ...and `form_check_ran_count` SURVIVES on the VM (the CLI report and the
    # route tests read it); it simply stops appearing in the prose.
    assert vm.form_check_ran_count == 0


def test_a_fully_checked_page_emits_exactly_one_claim():
    vm = _vm((), ran=3)
    assert vm.all_clear_claims == ("No alarms.",)
    assert vm.all_clear_note == "No alarms."


# --- B6 (Arc 21-B) x the close-provenance ladder (Arc 21-G) ------------------
#
# 21-G's page-level sentence LED WITH THE REDUCTION ("{M} latches checked from
# an uncorroborated close - no all-clear is asserted for those.") because under
# the SCOPED construction the "No alarms" clause was itself qualified and
# skimmable. RD retired that STRUCTURE, not that FACT: "the check ran from a
# close whose date could not be proved" is a DIFFERENT statement from "the
# check did not run", so under the separated construction it is simply another
# claim. These pin the composition.
def test_every_form_check_severity_reaches_the_page_level_line():
    """THE DRIFT GUARD, and the reason it is a test rather than a comment.

    An unlabelled reduction is a quiet all-clear by omission -- that is the rule
    both the 21-A ruling and B6 rest on. A severity that renders a per-latch
    label but silently fails to reach the page-level line is exactly such an
    omission, and it is the failure mode a severity added by a LATER arc walks
    straight into. So the roster and the headline table are pinned EQUAL (the
    #11 multi-mirror discipline): a new severity cannot ship green while being
    dropped from the line."""
    claimed = {s for severities, _ in _FORM_CHECK_CLAIM_PHRASINGS
               for s in severities}
    assert claimed == set(_FORM_CHECK_HEADLINES)
    # ...and no severity is claimed twice, which would double-count a page.
    flat = [s for severities, _ in _FORM_CHECK_CLAIM_PHRASINGS for s in severities]
    assert len(flat) == len(set(flat))


def test_the_uncorroborated_close_claim_is_preserved_as_its_own_claim():
    """21-G's provenance fact, carried into B6's structure verbatim, and placed
    FIRST among the reductions -- Codex R7's lead-with-the-reduction ruling
    honoured as far as the separated structure allows. "No alarms." still leads
    the whole line and stays UNSCOPED: it is COMPLETE (every latch IS
    alarm-checked), so skimming it yields a TRUE belief, which is precisely what
    the superseded scoped sentence could not offer."""
    vm = _vm((_note("FTRE", "stale_regime"), _note("AMN", "pending")), ran=0)
    assert vm.all_clear_claims == (
        "No alarms.",
        "1 latch checked from an uncorroborated close - no all-clear is "
        "asserted for those.",
        "Mandate-form check pending for 1 latch.",
    )


def test_the_two_rung_f_headlines_share_one_page_level_claim():
    """`future_stamp` and `unplaceable_stamp` are two HEADLINES over ONE rung
    (a stamp after this session, or one that cannot be parsed at all). The
    per-latch labels separate them -- the reason must be TRUE, not merely safe
    -- but the page-level fact they share is the single one that matters here,
    so they contribute ONE claim with a combined count, not two."""
    vm = _vm((_note("FTRE", "future_stamp"),
              _note("AMN", "unplaceable_stamp")), ran=0)
    assert vm.all_clear_claims == (
        "No alarms.",
        "Mandate-form check inert for 2 latches - the recorded close cannot be "
        "placed in time; see the labels below.",
    )


def test_a_value_conflict_is_not_folded_into_the_permanent_claim():
    """B-conflict is CONTRADICTED by dated evidence the panel is holding, which
    is a different fact from a latch that has simply fallen off the screen --
    and it resolves when the data is repaired rather than never. Folding it into
    `permanent` would re-commit the very lumping B6 exists to undo."""
    vm = _vm((_note("FTRE", "value_conflict"), _note("AMN", "permanent")), ran=0)
    assert vm.all_clear_claims == (
        "No alarms.",
        "Mandate-form check inert for 1 latch - the recorded close is "
        "contradicted by the archive; see the labels below.",
        "Mandate-form check inert for 1 latch - see the labels below.",
    )
