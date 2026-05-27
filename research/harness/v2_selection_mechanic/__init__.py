"""V2-selection-mechanic analytical orchestration module set.

ANALYTICAL / EXPLORATORY investigation module (per V2-selection-mechanic
investigation dispatch brief Sec 0 mission statement). NOT a backtest.
Examines WHY V2-binding-variable cohort selection produces W-pattern-thin
substrates by measuring per-V2-cohort:
  (a) substrate W-pattern density vs the bias-free D2 EXPANDED N=71 baseline
  (b) per-variable substrate regime fingerprint (90d return / ATR% /
      52w prox / sector mix)
  (c) cross-variable compatibility verdict synthesis with Ruleset E

Module map (per dispatch brief Sec 2.6):
  - __init__.py                       BINDING_SIGNALS_TABLE + D2 baseline
                                      anchor constants + L2 LOCK
  - substrate_characterization.py     per-ticker regime metric computation
                                      via direct legacy parquet reads
                                      (sidesteps V2 reader; gotcha #28 +
                                      brief Sec 6(d))
  - w_density_analysis.py             W-density measurement orchestration
  - synthesis.py                      narrative compatibility verdict
                                      (gotcha #33 LOCK: NO PARTIAL POSITIVE
                                      / NEGATIVE / POSITIVE verdict terms)
  - run.py                            top-level orchestration entrypoint

GOTCHA #34 FIRST CANONICAL APPLICATION (per dispatch brief Sec 4.4): the
BINDING_SIGNALS_TABLE constant below LOCKs the 5 (variable, max_delta_aplus,
binding_sweep_point) tuples. The discriminating test at
`tests/research/v2_selection_mechanic/test_binding_signals_table_cross_check.py`
re-derives these tuples at runtime by parsing the V2 sensitivity
SUMMARY TABLE (lines 13-22) AND the Sensitivity Matrix (lines 66+) and
asserts equality with this constant.

GOTCHA #34 SECOND CANONICAL APPLICATION: the per-variable
NON_WATCH_TRANSITION_GAP_TABLE LOCKs the per-variable gap between SUMMARY
TABLE max_delta_aplus and the drill-down watch->aplus transition count.
This gap reflects aplus-bucket churn beyond strict watch->aplus
transitions (e.g., aplus-baseline rows that stay aplus + are counted in
the Matrix delta but absent from the drill-down's transition-only rows).
LOCK values per the 2026-05-24 V2 sensitivity smoke artifact (Brief
Amendment 2 banked orchestrator-side):

  vcp.tightness_range_factor    +75 SUMMARY -> 67 drill-down (gap 8;  ~11%)
  vcp.tightness_days_required   +16 SUMMARY -> 15 drill-down (gap 1;  ~6%)
  vcp.adr_min_pct               +11 SUMMARY -> 11 drill-down (gap 0;   0%)
  vcp.proximity_max_pct         + 5 SUMMARY ->  5 drill-down (gap 0;   0%)
  vcp.orderliness_max_bar_ratio + 1 SUMMARY ->  1 drill-down (gap 0;   0%)

GOTCHA #33 THIRD CANONICAL APPLICATION REINFORCED: the investigation is
ANALYTICAL not verdict-producing. `synthesis.py` MUST NOT emit
"PARTIAL POSITIVE" / "NEGATIVE" / "POSITIVE" verdict terminology.
Descriptive labels only -- compatibility evidence narratives bounded by
the canonical filter composite>=0.5 + recency<=365d held FIXED across
all 5 V2 cohorts + the D2 EXPANDED N=71 bias-free baseline.

D2 EXPANDED N=71 BIAS-FREE BASELINE (per dispatch brief Sec 1.4 corrected
per Brief Amendment 2 banked orchestrator-side at investigation greenlight
2026-05-26 PM; original brief Sec 1.4 cited "88 unique S&P 500 tickers"
which was an orchestrator-side error; correct value is 516):

  manifest_timestamp:  20260526T000409Z
  universe_size:       516 unique S&P 500 tickers scanned
  input_entries:       2064 (= 516 tickers x 4 asof_date snapshots)
  input_asof_count:    4
  verdicts_emitted:    166007 across all 5 detector classes
  filtered_W_count:    71 (D2 EXPANDED Amendment 5 LOCK; composite>=0.5
                       + recency<=365d + 5-BD adjacency-merged)
  filtered_density:    71 / 516 = 0.1376 W per ticker

D_raw_baseline_w (the raw W-primary count BEFORE canonical filter) is
NOT AVAILABLE in V1: D2 baseline run emitted manifest.json + summary.md
but NOT results.csv (Option B fallback per orchestrator greenlight
2026-05-26 PM). The investigation surfaces only D_filt deltas + documents
the unavailability in findings doc Sec 10 as an L-style methodological
note. Banked V2 candidate: re-run D2 EXPANDED with results.csv emission
enabled to capture raw-W density.

L2 LOCK preserved: ZERO new Schwab API calls; ZERO production swing/
writes; reads only local V2 sensitivity markdown artifact + legacy
parquet OHLCV archives + D2 baseline manifest.
"""
from __future__ import annotations


# -----------------------------------------------------------------------
# BINDING_SIGNALS_TABLE -- gotcha #34 FIRST CANONICAL APPLICATION LOCK
# -----------------------------------------------------------------------
# Each tuple: (variable_name, max_delta_aplus, binding_sweep_point)
# Per V2 sensitivity SUMMARY TABLE (lines 13-22) + Sensitivity Matrix
# (lines 66+) of the canonical source artifact
# `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`.
#
# Convention for `binding_sweep_point` LOCK: the sweep_point where the
# Sensitivity Matrix's `delta_aplus` column equals the SUMMARY TABLE's
# `max_delta_aplus`. If multiple sweep_points yield the same max delta
# (e.g., vcp.orderliness_max_bar_ratio at sp=3.75 AND sp=4.5 both yield
# +1 delta_aplus), the LOCK is the LOWEST such sweep_point per "first
# crossing" convention (operator-paired LOCK at dispatch brief Sec 2.3).
# -----------------------------------------------------------------------
BINDING_SIGNALS_TABLE: tuple[tuple[str, int, float], ...] = (
    ("vcp.tightness_range_factor", 75, 1.005),
    ("vcp.tightness_days_required", 16, 1.0),
    ("vcp.adr_min_pct", 11, 2.0),
    ("vcp.proximity_max_pct", 5, 7.5),
    ("vcp.orderliness_max_bar_ratio", 1, 3.75),
)

# -----------------------------------------------------------------------
# NON_WATCH_TRANSITION_GAP_TABLE -- gotcha #34 SECOND CANONICAL APPLICATION
# -----------------------------------------------------------------------
# Each tuple: (variable_name, max_delta_aplus, drill_down_watch_aplus_count,
#              gap, gap_pct_of_max_delta)
# Methodological side-finding per dispatch brief Sec 2.1 + operator
# greenlight 2026-05-26 PM: the drill-down's strict watch->aplus filter
# yields fewer rows than the Sensitivity Matrix's net delta_aplus for
# 2 of 5 V2 binding variables. The gap reflects aplus-bucket churn
# beyond strict watch->aplus transitions (some aplus-baseline candidates
# remain aplus + are counted in the Matrix delta but absent from the
# drill-down's transition-only rows; or skip->aplus transitions not
# emitted to drill-down at this V2 emitter version).
# -----------------------------------------------------------------------
NON_WATCH_TRANSITION_GAP_TABLE: tuple[
    tuple[str, int, int, int, float], ...
] = (
    ("vcp.tightness_range_factor", 75, 67, 8, 8 / 75 * 100),
    ("vcp.tightness_days_required", 16, 15, 1, 1 / 16 * 100),
    ("vcp.adr_min_pct", 11, 11, 0, 0.0),
    ("vcp.proximity_max_pct", 5, 5, 0, 0.0),
    ("vcp.orderliness_max_bar_ratio", 1, 1, 0, 0.0),
)

# -----------------------------------------------------------------------
# D2 EXPANDED N=71 BIAS-FREE BASELINE ANCHORS
# -----------------------------------------------------------------------
# Per Brief Amendment 2 banked orchestrator-side at investigation
# greenlight 2026-05-26 PM (original brief Sec 1.4 cited "88 unique S&P
# 500 tickers" which was orchestrator-side error; correct value is 516).
# Source: D2 baseline run manifest at
# `exports/research/pattern-cohort-detection-20260526T000409Z/manifest.json`.
# -----------------------------------------------------------------------
D2_BASELINE_MANIFEST_TIMESTAMP = "20260526T000409Z"
D2_BASELINE_MANIFEST_PATH = (
    "exports/research/pattern-cohort-detection-20260526T000409Z/manifest.json"
)
D2_BASELINE_UNIVERSE_SIZE = 516
D2_BASELINE_INPUT_ENTRIES = 2064
D2_BASELINE_INPUT_ASOF_COUNT = 4
D2_BASELINE_VERDICTS_EMITTED_ALL_CLASSES = 166007
D2_BASELINE_COHORT_CSV_PATH = (
    "exports/research/cohorts/w_bottom_ruleset_comparison_sp500_apr_may_2026.csv"
)
# SHA-256 captured from the D2 baseline manifest's `cohort_input_sha256`
# field. Audit-stable identity lock for the D2 cohort CSV used as the
# universe input to the bias-free baseline run.
D2_BASELINE_COHORT_CSV_SHA256 = (
    "98214d29f2200aaed7e3b6bfcd0795112d016bfe60d4d0fae10b1148eee998de"
)
# Per D2 findings doc Amendment 5 LOCK: 71 W primaries surviving the
# canonical filter composite>=0.5 + recency<=365d + 5-BD adjacency merge.
D2_BASELINE_FILTERED_W_COUNT = 71
# Derived: filtered density = filtered_W_count / universe_size
D2_BASELINE_FILTERED_DENSITY = 71 / 516

# Canonical evaluation filter held FIXED across ALL 5 V2 cohorts + the
# D2 EXPANDED baseline (gotcha #33 third canonical application
# REINFORCED). Alternative filter scopes (composite>=0.7 + recency<=120d
# etc.) MAY be documented in the findings doc as sub-cohort exploration
# BUT MUST NOT be used to substitute the canonical density measurement
# or the compatibility verdict.
CANONICAL_COMPOSITE_THRESHOLD = 0.5
CANONICAL_RECENCY_DAYS = 365

# Canonical source artifact SHA-256 + size lock for the V2 sensitivity
# smoke artifact (mirrors v2_tightness_range_factor /
# v2_proximity_max_pct / v2_orderliness_max_bar_ratio sibling
# constants; SAME source artifact).
CANONICAL_SOURCE_SHA256 = (
    "b25bcde944c33c7a44d049167e78e9d5c7b3d4fc5538ccc5e9cdc8e01e27a143"
)
CANONICAL_SOURCE_SIZE_BYTES = 830034
CANONICAL_SOURCE_PATH = (
    "exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md"
)
