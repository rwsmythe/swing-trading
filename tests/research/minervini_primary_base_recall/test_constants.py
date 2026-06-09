from __future__ import annotations

from research.harness.minervini_primary_base_recall import constants as c


def test_scalar_constants_match_spec():
    assert c.MIN_HISTORY_BARS == 40
    assert c.MIN_BASE_BARS == 15
    assert c.ZIGZAG_THRESHOLD_PCT == 3.0
    assert c.MAX_CONTROL_AGE_BARS == 504
    assert c.YOUNG_NAME_CEILING_BARS == 221
    assert c.CONTROL_K == 5
    assert c.WINDOW_BACK == 60
    assert c.WINDOW_FWD == 5
    # Re-exported from the FROZEN harness (reuse, not redefine).
    assert c.CONTROL_GAP_BARS == 120
    assert c.DEFAULT_CONTROL_SEED == 20260608


def test_depth_cap_ladder_boundaries():
    # WRONG-PATH (a flat single cap, e.g. always 0.35) would return 0.35 at dur=25 and 0.50.
    # RIGHT-PATH (graduated ladder):
    assert c.depth_cap(10) == 0.25
    assert c.depth_cap(25) == 0.25      # boundary: <=25 -> 0.25
    assert c.depth_cap(26) == 0.35      # boundary: 26 -> 0.35
    assert c.depth_cap(200) == 0.35     # boundary: <=200 -> 0.35
    assert c.depth_cap(201) == 0.50     # boundary: >200 -> 0.50
    assert c.depth_cap(999) == 0.50
