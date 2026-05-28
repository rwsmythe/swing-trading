"""Discipline-locking tests for G2 dispatch (Slice 5a).

Per dispatch brief Sec 4.3 + Sec 5.3 + Sec 6:
  - L2 LOCK: source-grep over NEW G2 module set for forbidden imports
  - ASCII discipline (gotcha #32): all NEW G2 source / test / artifact
    Python files encode as ASCII
  - Byte-stability LOCK for existing A-F harness + R2-A/D2 cohort fixtures
  - Gotcha #33 banned-verdict-terms LOCK: scorecard module + narrative
    output emitters MUST NOT emit PARTIAL POSITIVE / NEGATIVE / POSITIVE
  - Gotcha #35 prior-arc-anchor metric-definition citation discipline:
    when narrative templates cite prior-arc numerical anchors, the metric
    definition MUST be cited too
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest


# Repo root: resolves the project root via this test file's location.
# `tests/research/g2_w_bottom_ruleset/test_locks.py` -> parents[3] = repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Files covered by the G2 dispatch (NEW only; existing harness is byte-stable).
G2_PACKAGE_DIR = REPO_ROOT / "research" / "harness" / "g2_w_bottom_ruleset_backtest"
G2_TESTS_DIR = REPO_ROOT / "tests" / "research" / "g2_w_bottom_ruleset"


def _enumerate_g2_python_files() -> list[Path]:
    """All NEW G2 Python files (package + tests)."""
    return sorted(
        list(G2_PACKAGE_DIR.rglob("*.py"))
        + list(G2_TESTS_DIR.rglob("*.py"))
    )


# ---------------------------------------------------------------------------
# L2 LOCK: source-grep for forbidden imports
# ---------------------------------------------------------------------------
# Codex R1 MINOR #1 ACCEPTED-with-rationale: this LOCK catches static
# import statements only (not dynamic importlib.import_module / __import__
# / monkey-patched attribute access / etc.). For the G2 harness scope this
# is sufficient -- the harness is pure-Python research code with no need
# for dynamic-import patterns. The L2 LOCK is one layer of defense in
# depth alongside the cohort-fixture byte-stability LOCK + the manifest
# emission's `schwab_api_calls: 0` + `yfinance_fetches_at_backtest_time:
# 0` assertions (which surface runtime breach in the smoke artifact).
FORBIDDEN_L2_PATTERNS = [
    r"\bimport\s+schwabdev\b",
    r"\bfrom\s+schwabdev\b",
    r"\bimport\s+yfinance\b",
    r"\bfrom\s+yfinance\b",
    r"\bfrom\s+swing\.integrations\.schwab\b",
    r"\bimport\s+swing\.integrations\.schwab\b",
]


@pytest.mark.parametrize("py_path", _enumerate_g2_python_files(), ids=lambda p: p.name)
def test_l2_lock_no_forbidden_imports_in_g2_module(py_path):
    """LOCK: each NEW G2 module must NOT import schwabdev / yfinance /
    swing.integrations.schwab. The harness consumes OHLCV via the existing
    V2 Shape A reader (read_yfinance_shape_a) inherited from the existing
    harness module set.

    Exception: test_locks.py (THIS file) is excluded from its own scan
    because it MUST literally contain the forbidden patterns inside its
    FORBIDDEN_L2_PATTERNS list to enforce the discipline.
    """
    # Skip THIS test file (which contains the forbidden patterns by design).
    if py_path.name == "test_locks.py":
        pytest.skip("test_locks.py contains forbidden patterns as detection rules")
    text = py_path.read_text(encoding="utf-8")
    for pattern in FORBIDDEN_L2_PATTERNS:
        matches = re.findall(pattern, text)
        assert not matches, (
            f"L2 LOCK violation in {py_path.relative_to(REPO_ROOT)}: "
            f"forbidden import pattern {pattern!r} matched {matches}"
        )


# ---------------------------------------------------------------------------
# ASCII discipline (gotcha #32)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("py_path", _enumerate_g2_python_files(), ids=lambda p: p.name)
def test_ascii_discipline_g2_python_files_encode_clean(py_path):
    """LOCK: all NEW G2 source + test files must encode as ASCII (gotcha
    #32 declared-scope; pre-empts Windows cp1252 stdout encoding errors)."""
    text = py_path.read_text(encoding="utf-8")
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        # Find the first offending line for actionable error message.
        bad_lines = []
        for line_num, line in enumerate(text.splitlines(), start=1):
            try:
                line.encode("ascii")
            except UnicodeEncodeError:
                bad_lines.append(f"  line {line_num}: {line!r}")
                if len(bad_lines) >= 5:
                    bad_lines.append("  ...")
                    break
        raise AssertionError(
            f"ASCII LOCK violation in {py_path.relative_to(REPO_ROOT)}:\n"
            + "\n".join(bad_lines)
            + f"\n\nFirst error: {exc}"
        )


# ---------------------------------------------------------------------------
# Byte-stability LOCK: existing A-F harness + cohort fixtures
# ---------------------------------------------------------------------------
# Per brief Sec 1.6 + Sec 5.3: A-F rulesets module + R2-A + D2 cohort
# fixtures must remain UNTOUCHED through the G2 dispatch. SHA-256 anchored
# at dispatch baseline 423f21d (main HEAD at dispatch time).
EXISTING_HARNESS_BYTE_STABILITY = {
    "research/harness/w_bottom_ruleset_comparison/__init__.py": (
        "da9653678609860276365e7b0eabdfc0c2c66e061b6c6a79383996fa8bd63a26"
    ),
    "research/harness/w_bottom_ruleset_comparison/rulesets.py": (
        "d4bd9f4f330dc4442b7d66bd23f5ae3d5f1311b1b62199a476f295c3de5f0981"
    ),
    "research/harness/w_bottom_ruleset_comparison/walkforward.py": (
        "91bc871faf07b90ecbeb3d20f5b1d9982dbc04d560063653ec0928bda6c52db5"
    ),
    "research/harness/w_bottom_ruleset_comparison/run.py": (
        "7f6bbc9a63fe3e71c10f27ea0b3214d4959d3a1dfc33b62b9c402bcfb589657d"
    ),
    "research/harness/w_bottom_ruleset_comparison/io.py": (
        "80d4c5fda4ac123394776d5d17e636fdcf2f4dcb417405bfc2e17067861980a6"
    ),
}

COHORT_FIXTURE_BYTE_STABILITY = {
    "tests/fixtures/research/r2a_tightness_days_required/cohort.json": (
        "758675b897affb4cf779259fdfe41398a3305b9480e8e3e510a358d83c4a35e7"
    ),
    "tests/fixtures/research/double_bottom_w_backtest/cohort.json": (
        "9075ac66d70401a19f11c06b681d859d3a5fbcd16e373e282c4db991bd6cc40c"
    ),
}


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "rel_path,expected_sha",
    list(COHORT_FIXTURE_BYTE_STABILITY.items()),
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_cohort_fixture_byte_stable_through_g2_dispatch(rel_path, expected_sha):
    """LOCK: R2-A + D2 cohort fixtures (the G2 substrates) byte-stable per
    brief Sec 1.6 ('REUSE VERBATIM'). SHA-256 anchored at dispatch baseline
    main commit 423f21d."""
    if expected_sha is None:
        pytest.skip(f"{rel_path}: SHA not anchored (informational entry)")
    path = REPO_ROOT / rel_path
    actual = _sha256_of(path)
    assert actual == expected_sha, (
        f"Cohort fixture {rel_path} drifted from dispatch baseline. "
        f"Expected SHA {expected_sha}, got {actual}. The G2 dispatch "
        f"BANS modification of these fixtures (brief Sec 1.6 + Sec 5.3)."
    )


@pytest.mark.parametrize(
    "rel_path,expected_sha", list(EXISTING_HARNESS_BYTE_STABILITY.items())
)
def test_existing_harness_byte_stable_through_g2_dispatch(rel_path, expected_sha):
    """LOCK: existing w_bottom_ruleset_comparison/ harness files are
    byte-stable through the G2 dispatch. SHA-256 anchored to dispatch
    baseline main commit 423f21d. Per Codex R1 MAJOR #3 closure:
    upgraded from file-presence-only check to actual byte-stability
    verification so any accidental drift in A-F is caught."""
    path = REPO_ROOT / rel_path
    assert path.exists(), (
        f"Existing harness file {rel_path} missing. The G2 dispatch BANS "
        f"modification or removal of the existing harness (brief Sec 5.3 "
        f"sibling-module strategy LOCK)."
    )
    actual_sha = _sha256_of(path)
    assert actual_sha == expected_sha, (
        f"Existing harness file {rel_path} drifted from dispatch baseline. "
        f"Expected SHA256 {expected_sha}, got {actual_sha}. The G2 dispatch "
        f"BANS modification of these files (brief Sec 5.3 sibling-module "
        f"strategy LOCK)."
    )


# ---------------------------------------------------------------------------
# Gotcha #33 banned-verdict-terms LOCK (scorecard + narrative emitters)
# ---------------------------------------------------------------------------
# Per brief Sec 1.4 + Sec 6 + gotcha #33 third canonical application: the
# scorecard module + ANY narrative output emitter in the G2 package must
# NOT emit PARTIAL POSITIVE / NEGATIVE / POSITIVE as verdict labels.
# Banned forms: case-insensitive word-boundary matches in PRODUCTION CODE
# (not test files; tests legitimately reference the terms when discussing
# the ban).
_BANNED_VERDICT_PATTERNS = [
    r"\bPARTIAL\s+POSITIVE\b",
    r"\bPOSITIVE\b",
    r"\bNEGATIVE\b",
]


def _enumerate_g2_production_python_files() -> list[Path]:
    """Production G2 modules ONLY (excludes tests/)."""
    return sorted(G2_PACKAGE_DIR.rglob("*.py"))


def _strip_python_string_literals_and_comments(text: str) -> str:
    """Best-effort removal of string literals + line comments + docstrings.

    Used so banned-term scans do NOT flag legitimate descriptive language
    in docstrings/comments (e.g., 'NO PARTIAL POSITIVE / NEGATIVE / POSITIVE
    in scorecard or narrative output per gotcha #33'). The scorecard module
    docstring uses this phrasing to DOCUMENT the ban.

    The strip is conservative; if it misses an edge case, the test would
    over-flag (a false positive) rather than miss a real violation.
    """
    # Drop triple-quoted strings (both """ and ''')
    text = re.sub(r'""".*?"""', '""', text, flags=re.DOTALL)
    text = re.sub(r"'''.*?'''", "''", text, flags=re.DOTALL)
    # Drop single-line string literals (best-effort)
    text = re.sub(r'"[^"\n\\]*(?:\\.[^"\n\\]*)*"', '""', text)
    text = re.sub(r"'[^'\n\\]*(?:\\.[^'\n\\]*)*'", "''", text)
    # Drop line comments
    text = re.sub(r"#[^\n]*", "", text)
    return text


# Brief Amendment 1 (BANKED post-Codex R1 MAJOR #2): the brief Sec 1.3
# states 'D2 EXPANDED N=71' citing D2 Amendment 5 source-of-truth. At
# dispatch baseline (cohort.json SHA 9075ac66...), the same filter
# (composite>=0.5 + recency<=365d + adjacency merge) yields N=42, NOT
# N=71. The cohort fixture has drifted since D2 Amendment 5 was run
# (likely due to a regenerate-cohort pass that updated
# max_observed_asof_date timestamps, shifting verdicts out of the
# 365d recency window). Per gotcha #34 (brief-prescription cross-table
# verification), the SHA-locked fixture + brief-locked filter yields
# the AUTHORITATIVE count. N=42 is the actual D2 EXPANDED substrate
# size for this G2 dispatch; brief's N=71 was a stale snapshot.
D2_EXPANDED_ACTUAL_N = 42


def test_d2_expanded_filter_yields_actual_n_against_real_cohort_fixture():
    """LOCK (Codex R1 MAJOR #2 closure + Brief Amendment 1): the D2
    EXPANDED filter applied to the real D2 cohort fixture MUST yield
    `D2_EXPANDED_ACTUAL_N` verdicts. Brief Sec 1.3 stated N=71 (stale
    snapshot from D2 Amendment 5); the SHA-locked fixture + brief-
    locked filter actually yields N=42 at dispatch baseline.

    This is a regression guard: any future drift in the D2 cohort.json
    OR the _filter_d2_expanded implementation will trip this test
    BEFORE silently shifting the G2 substrate size.
    """
    from research.harness.double_bottom_w_backtest.cohort import (
        load_cohort_fixture,
    )
    from research.harness.g2_w_bottom_ruleset_backtest.run import (
        _filter_d2_expanded,
    )

    d2_path = REPO_ROOT / "tests/fixtures/research/double_bottom_w_backtest/cohort.json"
    raw = load_cohort_fixture(d2_path)
    assert len(raw) == 172, (
        f"D2 raw cohort drifted from baseline N=172; got {len(raw)}. "
        f"Check SHA256 byte-stability test for D2 fixture."
    )
    filtered = _filter_d2_expanded(raw)
    assert len(filtered) == D2_EXPANDED_ACTUAL_N, (
        f"D2 EXPANDED filter drifted; expected N={D2_EXPANDED_ACTUAL_N} "
        f"(Brief Amendment 1; actual dispatch-baseline count); got "
        f"{len(filtered)}. The brief Sec 1.3 stated N=71 as a stale "
        f"snapshot from D2 Amendment 5; the current fixture (SHA-locked) "
        f"with the brief-locked filter yields N={D2_EXPANDED_ACTUAL_N}."
    )


def test_r2a_canonical_substrate_n65_verbatim():
    """LOCK: R2-A cohort fixture is consumed VERBATIM (N=65) per brief
    Sec 1.3. Sibling to the D2 EXPANDED regression test."""
    from research.harness.double_bottom_w_backtest.cohort import (
        load_cohort_fixture,
    )

    r2a_path = REPO_ROOT / "tests/fixtures/research/r2a_tightness_days_required/cohort.json"
    verdicts = load_cohort_fixture(r2a_path)
    assert len(verdicts) == 65, (
        f"R2-A canonical cohort drifted from baseline N=65 per brief "
        f"Sec 1.3 LOCK; got {len(verdicts)}."
    )


# ---------------------------------------------------------------------------
# Gotcha #35 prior-arc-anchor citation discipline
# ---------------------------------------------------------------------------
# Per brief Sec 6 + gotcha #35 first canonical application post-banking:
# any narrative referencing prior-arc numerical anchors (R2-A '22.5%
# win-rate'; D2 '+1.220R mean R'; V2-mechanic 'D_filt 7.2x-70x baseline'
# etc.) MUST cite the metric definition (composite_filter spec; recency
# filter; per-ticker vs per-cohort denominator).
#
# The NARRATIVE_SYNTHESIS emitter in io.py is pure-metric-rendering;
# it does NOT quote prior-arc anchors. This test defensively verifies
# the emitter remains anchor-free at smoke time. The findings doc
# (Slice 6) will have its own gotcha #35 enforcement.

# Prior-arc numerical anchors (must be absent OR co-cited with metric defs)
_PRIOR_ARC_ANCHOR_PATTERNS = [
    r"22\.5\s*%",      # R2-A win-rate
    r"\+1\.220\s*R",   # D2 mean R
    r"\bD_filt\b",     # V2-mechanic per-ticker density
    r"7\.2x[-\s]?70x", # V2-mechanic baseline ratio
    r"\-1\.086\s*R",   # R2-A mean R closed
    r"\+0\.512\s*R",   # R2-A E winners
    r"\-1\.55\s*R",    # R2-A E losers
]


def test_gotcha_35_narrative_synthesis_emitter_does_not_quote_prior_arc_anchors():
    """LOCK gotcha #35: the narrative_synthesis emitter renders metrics
    descriptively across (ruleset, substrate) cells; it does NOT quote
    prior-arc numerical anchors (R2-A 22.5%; D2 +1.220R; V2-mechanic
    D_filt 7.2x-70x; etc.). Verifies via synthetic input rendered through
    the emitter (Codex R1 MAJOR #4+#5 closure: artifact-emission-level
    enforcement, not just source-code-grep)."""
    from datetime import date as date_cls, datetime as datetime_cls, timezone as timezone_cls
    from research.harness.g2_w_bottom_ruleset_backtest.io import (
        write_narrative_synthesis_markdown,
        write_summary_markdown,
    )
    from research.harness.g2_w_bottom_ruleset_backtest.scorecard import (
        ScorecardRow,
    )

    rows = [
        ScorecardRow(
            ruleset_name="G_bulkowski_double_bottom",
            substrate_name="r2a_canonical_n65",
            n_patterns=65, n_triggered=40, n_closed=30,
            expectancy_R=0.5, win_rate=0.4, avg_win_R=2.0, avg_loss_R=0.5,
            profit_factor=2.667, trigger_conversion_rate=0.615,
            median_time_in_trade_sessions=15, open_at_tail_count=10, open_at_tail_rate=0.25,
            estimated_dollar_per_period=750.0, substrate_window_days=365,
        ),
    ]
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as fp:
        narrative_path = Path(fp.name)
    try:
        write_narrative_synthesis_markdown(narrative_path, scorecard_rows=rows)
        text = narrative_path.read_text(encoding="utf-8")
        for pattern in _PRIOR_ARC_ANCHOR_PATTERNS:
            matches = re.findall(pattern, text)
            assert not matches, (
                f"Gotcha #35 LOCK violation: narrative_synthesis emitter "
                f"output contains prior-arc anchor pattern {pattern!r}: "
                f"{matches}. The V1 emitter must remain anchor-free; the "
                f"findings doc (Slice 6) has its own enforcement."
            )
    finally:
        narrative_path.unlink(missing_ok=True)


def test_gotcha_35_summary_markdown_emitter_does_not_quote_prior_arc_anchors():
    """LOCK gotcha #35: summary.md emitter is also anchor-free."""
    from datetime import datetime as datetime_cls, timezone as timezone_cls
    from research.harness.g2_w_bottom_ruleset_backtest.io import (
        write_summary_markdown,
    )
    from research.harness.g2_w_bottom_ruleset_backtest.scorecard import (
        ScorecardRow,
    )

    rows = [
        ScorecardRow(
            ruleset_name="G_bulkowski_double_bottom",
            substrate_name="r2a_canonical_n65",
            n_patterns=65, n_triggered=40, n_closed=30,
            expectancy_R=0.5, win_rate=0.4, avg_win_R=2.0, avg_loss_R=0.5,
            profit_factor=2.667, trigger_conversion_rate=0.615,
            median_time_in_trade_sessions=15, open_at_tail_count=10, open_at_tail_rate=0.25,
            estimated_dollar_per_period=750.0, substrate_window_days=365,
        ),
    ]
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as fp:
        summary_path = Path(fp.name)
    try:
        write_summary_markdown(
            summary_path,
            started_at_utc=datetime_cls.now(timezone_cls.utc),
            scorecard_rows=rows,
            substrates_summary={
                "r2a_canonical_n65": {
                    "fixture_path": "tests/fixtures/...",
                    "cohort_sha256": "deadbeef",
                    "n_raw": 65, "n_filtered": 65,
                    "filter_spec": "verbatim",
                    "substrate_window_days": 365,
                },
            },
            cache_dir="/fake/cache",
        )
        text = summary_path.read_text(encoding="utf-8")
        for pattern in _PRIOR_ARC_ANCHOR_PATTERNS:
            matches = re.findall(pattern, text)
            assert not matches, (
                f"Gotcha #35 LOCK violation: summary.md emitter output "
                f"contains prior-arc anchor pattern {pattern!r}: {matches}."
            )
    finally:
        summary_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Gotcha #33 banned-verdict-terms at the EMITTED-ARTIFACT layer
# ---------------------------------------------------------------------------
def test_gotcha_33_summary_markdown_emitter_does_not_contain_banned_verdict_terms():
    """LOCK gotcha #33 (Codex R1 MAJOR #5 closure): the summary.md emitter
    rendered output MUST NOT contain PARTIAL POSITIVE / NEGATIVE / POSITIVE.
    The production-code-grep test in test_gotcha_33_no_banned_verdict_terms
    is necessary-but-insufficient (it strips string literals). This test
    exercises the actual emitter against synthetic input + scans
    rendered output."""
    from datetime import datetime as datetime_cls, timezone as timezone_cls
    from research.harness.g2_w_bottom_ruleset_backtest.io import (
        write_summary_markdown,
    )
    from research.harness.g2_w_bottom_ruleset_backtest.scorecard import (
        ScorecardRow,
    )

    rows = [
        ScorecardRow(
            ruleset_name="G_bulkowski_double_bottom",
            substrate_name="r2a_canonical_n65",
            n_patterns=65, n_triggered=40, n_closed=30,
            expectancy_R=0.5, win_rate=0.4, avg_win_R=2.0, avg_loss_R=0.5,
            profit_factor=2.667, trigger_conversion_rate=0.615,
            median_time_in_trade_sessions=15, open_at_tail_count=10, open_at_tail_rate=0.25,
            estimated_dollar_per_period=750.0, substrate_window_days=365,
        ),
    ]
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as fp:
        summary_path = Path(fp.name)
    try:
        write_summary_markdown(
            summary_path,
            started_at_utc=datetime_cls.now(timezone_cls.utc),
            scorecard_rows=rows,
            substrates_summary={
                "r2a_canonical_n65": {
                    "fixture_path": "x", "cohort_sha256": "x",
                    "n_raw": 65, "n_filtered": 65, "filter_spec": "verbatim",
                    "substrate_window_days": 365,
                },
            },
            cache_dir="/fake",
        )
        text = summary_path.read_text(encoding="utf-8")
        for pattern in _BANNED_VERDICT_PATTERNS:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            assert not matches, (
                f"Gotcha #33 LOCK violation: summary.md contains banned "
                f"verdict pattern {pattern!r}: {matches}"
            )
    finally:
        summary_path.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "py_path", _enumerate_g2_production_python_files(), ids=lambda p: p.name
)
def test_gotcha_33_no_banned_verdict_terms_in_g2_production_code(py_path):
    """LOCK gotcha #33: scorecard + narrative emitters MUST NOT emit
    PARTIAL POSITIVE / NEGATIVE / POSITIVE as verdict labels in EXECUTABLE
    code (string literals + comments + docstrings exempt; the discipline
    is about emitted OUTPUT, not source-code documentation of the ban).

    The strip helper drops literal strings + docstrings + comments so
    legitimate references in module docstrings (documenting the ban) do
    NOT trip the assertion.
    """
    raw = py_path.read_text(encoding="utf-8")
    stripped = _strip_python_string_literals_and_comments(raw)
    for pattern in _BANNED_VERDICT_PATTERNS:
        matches = re.findall(pattern, stripped, flags=re.IGNORECASE)
        assert not matches, (
            f"Gotcha #33 LOCK violation in "
            f"{py_path.relative_to(REPO_ROOT)}: banned verdict pattern "
            f"{pattern!r} matched in executable code: {matches}"
        )
