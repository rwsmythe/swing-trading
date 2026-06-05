# tests/evaluation/test_completed_day_anchors.py
from datetime import datetime

from swing.evaluation.dates import action_session_for_run, last_completed_session


def _hst(y, m, d, hh, mm):
    # naive local HST datetime as the helpers expect (tz applied internally).
    return datetime(y, m, d, hh, mm)


def test_last_completed_session_never_names_in_progress():
    # 2026-06-04 is a Thursday (NYSE session). HST is ET-6 (DST) / -5; the
    # helper converts internally. Pre-open ET -> prior session; post-close ->
    # today; weekend -> Friday.
    pre_open = last_completed_session(_hst(2026, 6, 4, 2, 0))    # ~08:00 ET (before close)
    assert pre_open.isoformat() < "2026-06-04"
    post_close = last_completed_session(_hst(2026, 6, 4, 12, 0))  # ~18:00 ET (after close)
    assert post_close.isoformat() == "2026-06-04"
    # 2026-06-06 is a Saturday; the last completed session is Friday 2026-06-05.
    weekend = last_completed_session(_hst(2026, 6, 6, 12, 0))
    assert weekend.isoformat() == "2026-06-05"


def test_action_vs_completed_diverge_post_close():
    """Post-close on a session day, action (forward) names the NEXT session
    while completed (backward) names today -- the divergence Slice D relies
    on."""
    t = _hst(2026, 6, 4, 12, 0)  # post-close ET
    assert action_session_for_run(t) != last_completed_session(t)
