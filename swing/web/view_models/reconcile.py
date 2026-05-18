"""View-model module for the web Tier-2 discrepancy-resolution surface
(Phase 12.5 #2).

This module hosts the helpers, dataclasses, and builder for
`GET /reconcile/discrepancy/{id}/resolve` and the POST companion route.
T-2.1 ships only the `_parse_parametric_pick_count` pure helper; subsequent
tasks (T-2.2..T-2.10) extend this module with the VM dataclasses, error VM,
and the builder function.

Spec references (BINDING):

- spec §5.4 ``Parametric pick_schwab_record_<N> entries derived from
  resolution_reason text — the classifier emits ``Schwab returned <N>
  orders within the match window`` in `reconciliation_discrepancies.
  resolution_reason`; the web VM parses N and synthesizes N parametric
  ChoiceMenuItem entries in the menu (mirrors the CLI behavior at
  `swing/cli.py` near line 2291).

- spec §16.7 LOCK ``_parse_parametric_pick_count helper duplicated
  private in web VM (CLI refactor V2-deferred)`` — accepted at brainstorm
  defaults 2026-05-18 (Phase 12.5 #2 brainstorm return report §16.7).

- spec §15.13 V2 candidate ``DRY consolidation of the
  _parse_parametric_pick_count helper between the CLI surface
  (`swing/cli.py:~2291`) and this module``. V1 ships the duplicate verbatim
  rather than coupling the modules; refactor deferred to a follow-up
  dispatch.

The regex pattern below is BYTE-FOR-BYTE identical to the CLI's compiled
pattern at `swing/cli.py` line 2291-2294 per LOCK §1.2 #11 of the
executing-plans plan; behavioral parity is pinned by the test at
`tests/web/test_reconcile_parametric_pick_count.py:
test_parse_parametric_pick_count_byte_identical_to_cli_parser`.
"""

from __future__ import annotations

import re


def _parse_parametric_pick_count(resolution_reason: str | None) -> int:
    """Parse the parametric pick-record count N from a discrepancy
    `resolution_reason`.

    The classifier (`swing/trades/reconciliation_classifier.py`) emits a
    substring of the form ``Schwab returned <N> orders within the match
    window`` inside the resolution_reason for `multi_match_within_window`
    ambiguity-kind discrepancies. This helper extracts N so the web Tier-2
    builder can synthesize N parametric `pick_schwab_record_<i>` choice
    entries (1-indexed) — mirroring the CLI behavior at
    `swing/cli.py:~2291`.

    Returns 0 when:
      - input is None
      - input is the empty string
      - the regex does not match (no "Schwab returned ... within the match
        window" substring)
      - the regex matches with N=0 (no parametric entries to build)

    The function is PURE — no DB access, no I/O, no logging, no
    side-effects. Mirrors the project's "Classifier is a PURE function"
    discipline applied to a parser helper.
    """
    text = resolution_reason or ""
    m = re.search(
        r"Schwab returned\s+(\d+)\s+orders within the match window",
        text,
    )
    if not m:
        return 0
    return int(m.group(1))
