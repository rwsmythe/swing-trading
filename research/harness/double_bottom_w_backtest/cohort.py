"""Cohort extraction + dedup for the D1 double_bottom_w walk-forward backtest.

Reads the pattern_cohort_evaluator results.csv (typically ~287 MB), filters to
pattern_class='double_bottom_w' AND composite_score >= threshold, parses each
row's structural_evidence_json, deduplicates per dispatch brief §1.3:

  Step 1: group verdicts by (ticker, trough_1_date); keep the highest-composite
          verdict per group as the "primary verdict" for that W structure.
  Step 2: optional within-ticker adjacency merge: trough_1_dates differing by
          fewer than 5 trading (business) days are treated as variants of the
          same W and merged into a single primary.

A SEPARATE filter (filter_recent_patterns) restricts to RECENT W's where
trough_2_date is within N days of the cohort_entry's data_asof_date. This
captures "the W that just completed at the cohort asof" -- the actionable
subset. The wider 172-pattern universe is dominated by historical W's whose
center_peak was crossed years before the asof and whose forward bars contain
no resolution of the W's breakout.

Pattern dataclass collects all fields needed by the walk-forward engine:
ticker + anchor_asof_date + trough_1/center_peak/trough_2 dates + prices +
pivot_price + scores. JSON-round-trippable via to_dict / from_dict.
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path


_DEFAULT_RECENCY_DAYS = 60
_DEFAULT_COMPOSITE_THRESHOLD = 0.7
_TROUGH_MERGE_BUSINESS_DAYS = 5


@dataclass(frozen=True)
class PrimaryVerdict:
    """Highest-composite verdict for a unique (ticker, trough_1_date) W structure.

    Holds all fields needed by the walk-forward backtest engine. Multiple
    cohort_entry sources may collapse into one PrimaryVerdict if they share
    (ticker, trough_1_date); the verdict tracks aux_count + aux_cohort_entry_ids
    for audit.

    anchor_asof_date: the asof of the highest-composite observation (used for
        the trigger search window).
    max_observed_asof_date: the MOST RECENT observation across all
        cohort_entries that map to this W. Differs from anchor_asof_date
        when a lower-composite observation has a later asof; used for
        recency-filter semantics (Codex R1 M#3 fix) so the most-recent
        observation determines whether the W is actionable at study time.
    observed_asof_dates: ALL observations' asof_dates, sorted; preserved for
        full audit trail.
    """

    ticker: str
    anchor_asof_date: date
    trough_1_date: date
    trough_1_price: float
    center_peak_date: date
    center_peak_price: float
    trough_2_date: date
    trough_2_price: float
    pivot_price: float
    composite_score: float
    geometric_score: float
    template_match_score: float | None
    cohort_entry_ids: tuple[int, ...] = field(default_factory=tuple)
    aux_window_indices: tuple[int, ...] = field(default_factory=tuple)
    max_observed_asof_date: date | None = None
    observed_asof_dates: tuple[date, ...] = field(default_factory=tuple)
    window_count: int = 0

    @property
    def pattern_id(self) -> str:
        return f"{self.ticker}-{self.trough_1_date.isoformat()}"

    @property
    def initial_stop(self) -> float:
        """Canonical W-bottom stop: 1% below the right shoulder low."""
        return self.trough_2_price * 0.99

    @property
    def trigger_threshold(self) -> float:
        """W-bottom neckline = center_peak_price (the entry-trigger reference)."""
        return self.center_peak_price

    @property
    def trigger_lower_bound_date(self) -> date:
        """Earliest date on which a trigger can fire.

        Per dispatch brief Section 2: trigger fires AFTER max(trough_1,
        trough_2, asof). Codex R2 M#1 fix: when max_observed_asof_date >
        anchor_asof_date (this W was observed AGAIN by a later cohort_entry),
        the EFFECTIVE backtest-as-of is the most-recent observation -- a real
        operator couldn't have acted before that observation existed. Use
        max(anchor, max_observed) as the asof reference; otherwise the
        recency-filter-admit-via-max-observed semantics would be inconsistent
        with a walk-forward that started at the earlier anchor's asof.
        """
        return max(
            self.trough_1_date, self.trough_2_date, self.effective_asof_date
        )

    @property
    def effective_asof_date(self) -> date:
        """Backtest-as-of date used as the trigger-window's reference asof.

        Codex R2 M#1: anchor_asof = highest-composite observation; max_observed
        = most-recent observation. The effective backtest asof is the LATEST
        of the two; walk-forward + recency filter both use this.
        """
        return max(
            self.anchor_asof_date,
            self.max_observed_asof_date or self.anchor_asof_date,
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["anchor_asof_date"] = self.anchor_asof_date.isoformat()
        d["trough_1_date"] = self.trough_1_date.isoformat()
        d["center_peak_date"] = self.center_peak_date.isoformat()
        d["trough_2_date"] = self.trough_2_date.isoformat()
        d["cohort_entry_ids"] = list(self.cohort_entry_ids)
        d["aux_window_indices"] = list(self.aux_window_indices)
        d["max_observed_asof_date"] = (
            self.max_observed_asof_date.isoformat()
            if self.max_observed_asof_date is not None
            else None
        )
        d["observed_asof_dates"] = [d.isoformat() for d in self.observed_asof_dates]
        d["window_count"] = self.window_count
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PrimaryVerdict":
        return cls(
            ticker=d["ticker"],
            anchor_asof_date=date.fromisoformat(d["anchor_asof_date"]),
            trough_1_date=date.fromisoformat(d["trough_1_date"]),
            trough_1_price=float(d["trough_1_price"]),
            center_peak_date=date.fromisoformat(d["center_peak_date"]),
            center_peak_price=float(d["center_peak_price"]),
            trough_2_date=date.fromisoformat(d["trough_2_date"]),
            trough_2_price=float(d["trough_2_price"]),
            pivot_price=float(d["pivot_price"]),
            composite_score=float(d["composite_score"]),
            geometric_score=float(d["geometric_score"]),
            template_match_score=(
                float(d["template_match_score"])
                if d.get("template_match_score") is not None
                else None
            ),
            cohort_entry_ids=tuple(d.get("cohort_entry_ids", [])),
            aux_window_indices=tuple(d.get("aux_window_indices", [])),
            max_observed_asof_date=(
                date.fromisoformat(d["max_observed_asof_date"])
                if d.get("max_observed_asof_date")
                else None
            ),
            observed_asof_dates=tuple(
                date.fromisoformat(s) for s in d.get("observed_asof_dates", [])
            ),
            window_count=int(d.get("window_count", 0)),
        )


def _parse_optional_float(s: str) -> float | None:
    if s == "" or s is None:
        return None
    return float(s)


def extract_primary_verdicts_from_csv(
    csv_path: Path,
    *,
    composite_threshold: float = _DEFAULT_COMPOSITE_THRESHOLD,
) -> list[PrimaryVerdict]:
    """Stream-parse the pattern_cohort_evaluator results.csv.

    Filters to pattern_class='double_bottom_w' AND composite_score >=
    composite_threshold; per (ticker, trough_1_date), keeps the row with
    the HIGHEST composite_score; auxiliary cohort_entry_ids + window_indices
    are accumulated for audit.

    Raises FileNotFoundError if csv_path missing.
    Raises ValueError on malformed structural_evidence_json (no silent skip).
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"results.csv not found at {csv_path}")
    # Bump field-size limit; structural_evidence_json contains long contraction
    # lists (~tens of KB per row for VCP). Mirror cumulative gotcha #28-family
    # discipline: silent silent-skip is the failure mode; raise loudly here.
    csv.field_size_limit(sys.maxsize)

    by_key: dict[tuple[str, str], dict] = {}
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("pattern_class") != "double_bottom_w":
                continue
            composite_raw = row.get("composite_score") or ""
            if not composite_raw:
                continue
            composite = float(composite_raw)
            if composite < composite_threshold:
                continue
            ev_raw = row.get("structural_evidence_json") or ""
            if not ev_raw:
                continue
            ev = json.loads(ev_raw)
            ticker = row["ticker"]
            t1_iso = ev["trough_1_date"]
            key = (ticker, t1_iso)
            cohort_entry_id = int(row["cohort_entry_id"])
            window_index = int(row["window_index"])
            row_asof = date.fromisoformat(row["asof_date"])
            current = by_key.get(key)
            if current is None:
                by_key[key] = {
                    "composite": composite,
                    "row": row,
                    "ev": ev,
                    "aux_cohort_entry_ids": [cohort_entry_id],
                    "aux_window_indices": [window_index],
                    "observed_asofs": [row_asof],
                }
                continue
            # Accumulate audit IDs + observed asofs regardless of primary winner
            # (Codex R1 M#3: max(observed_asofs) feeds recency filter so the
            # most-recent cohort_entry that observes this W is what determines
            # recency, not the highest-composite observation.)
            current["aux_cohort_entry_ids"].append(cohort_entry_id)
            current["aux_window_indices"].append(window_index)
            current["observed_asofs"].append(row_asof)
            # Promote new row to primary if its composite is higher
            if composite > current["composite"]:
                current["composite"] = composite
                current["row"] = row
                current["ev"] = ev

    verdicts: list[PrimaryVerdict] = []
    for key, payload in by_key.items():
        ev = payload["ev"]
        row = payload["row"]
        observed_asofs = sorted(set(payload["observed_asofs"]))
        verdicts.append(
            PrimaryVerdict(
                ticker=row["ticker"],
                anchor_asof_date=date.fromisoformat(row["asof_date"]),
                trough_1_date=date.fromisoformat(ev["trough_1_date"]),
                trough_1_price=float(ev["trough_1_price"]),
                center_peak_date=date.fromisoformat(ev["center_peak_date"]),
                center_peak_price=float(ev["center_peak_price"]),
                trough_2_date=date.fromisoformat(ev["trough_2_date"]),
                trough_2_price=float(ev["trough_2_price"]),
                pivot_price=float(ev["pivot_price"]),
                composite_score=float(row["composite_score"]),
                geometric_score=float(row["geometric_score"]),
                template_match_score=_parse_optional_float(
                    row.get("template_match_score") or ""
                ),
                cohort_entry_ids=tuple(sorted(set(payload["aux_cohort_entry_ids"]))),
                aux_window_indices=tuple(sorted(set(payload["aux_window_indices"]))),
                max_observed_asof_date=max(observed_asofs),
                observed_asof_dates=tuple(observed_asofs),
                window_count=len(set(payload["aux_window_indices"])),
            )
        )
    verdicts.sort(key=lambda v: (v.ticker, v.trough_1_date))
    return verdicts


def merge_adjacent_troughs(
    verdicts: list[PrimaryVerdict],
    *,
    max_gap_business_days: int = _TROUGH_MERGE_BUSINESS_DAYS,
) -> list[PrimaryVerdict]:
    """Per-ticker, merge primary verdicts whose trough_1_date differ by < N BD.

    Within a merge group, the HIGHEST-composite verdict wins; cohort_entry_ids
    and aux_window_indices are unioned. trough_1_date difference uses
    np.busday_count for business-day precision (per V2 patterns.py precedent).

    Pure function; does not mutate input.
    """
    if not verdicts:
        return []
    # Lazy-import numpy to keep cohort.py import cost low when unused.
    import numpy as np

    by_ticker: dict[str, list[PrimaryVerdict]] = {}
    for v in verdicts:
        by_ticker.setdefault(v.ticker, []).append(v)

    merged: list[PrimaryVerdict] = []
    for ticker in sorted(by_ticker):
        rows = sorted(by_ticker[ticker], key=lambda v: v.trough_1_date)
        cluster: list[PrimaryVerdict] = []

        def _emit() -> None:
            if not cluster:
                return
            best = max(cluster, key=lambda v: v.composite_score)
            all_entries = sorted({eid for v in cluster for eid in v.cohort_entry_ids})
            all_windows = sorted({wi for v in cluster for wi in v.aux_window_indices})
            all_asofs = sorted(
                {d for v in cluster for d in (v.observed_asof_dates or (v.anchor_asof_date,))}
            )
            merged.append(
                PrimaryVerdict(
                    ticker=best.ticker,
                    anchor_asof_date=best.anchor_asof_date,
                    trough_1_date=best.trough_1_date,
                    trough_1_price=best.trough_1_price,
                    center_peak_date=best.center_peak_date,
                    center_peak_price=best.center_peak_price,
                    trough_2_date=best.trough_2_date,
                    trough_2_price=best.trough_2_price,
                    pivot_price=best.pivot_price,
                    composite_score=best.composite_score,
                    geometric_score=best.geometric_score,
                    template_match_score=best.template_match_score,
                    cohort_entry_ids=tuple(all_entries),
                    aux_window_indices=tuple(all_windows),
                    max_observed_asof_date=max(all_asofs),
                    observed_asof_dates=tuple(all_asofs),
                    window_count=len(all_windows),
                )
            )

        for v in rows:
            if not cluster:
                cluster.append(v)
                continue
            prev = cluster[-1]
            bd_gap = int(np.busday_count(prev.trough_1_date, v.trough_1_date))
            if bd_gap < max_gap_business_days:
                cluster.append(v)
            else:
                _emit()
                cluster = [v]
        _emit()
    return merged


def filter_recent_patterns(
    verdicts: list[PrimaryVerdict],
    *,
    max_calendar_days: int = _DEFAULT_RECENCY_DAYS,
) -> list[PrimaryVerdict]:
    """Restrict to W's whose right shoulder (trough_2_date) is within N
    CALENDAR days of the MOST-RECENT observation's asof_date.

    Uses max_observed_asof_date (the latest cohort_entry that observed this W)
    rather than anchor_asof_date (the highest-composite observation) so that
    a W with multiple observations across cohort_entries is judged by its
    most-recent observation -- avoiding the failure mode where the highest-
    composite observation is OLDER than other observations of the same W
    (Codex R1 M#3 fix).

    Calendar days (not business days) per V2 backtest precedent for forward-
    window depth estimation; documented as a methodology choice in findings.

    A NEGATIVE value of (asof - trough_2) means trough_2 is AFTER asof
    (cohort observed during the W's right-shoulder formation); these are
    INCLUDED (recency = 0 effectively).
    """
    out: list[PrimaryVerdict] = []
    for v in verdicts:
        # Fall back to anchor_asof_date for fixtures pre-Codex-R1 that
        # lack max_observed_asof_date (defensive; new extractor always sets it).
        recency_anchor = v.max_observed_asof_date or v.anchor_asof_date
        days_since_t2 = (recency_anchor - v.trough_2_date).days
        if days_since_t2 <= max_calendar_days:
            out.append(v)
    return out


def write_cohort_fixture(verdicts: list[PrimaryVerdict], output_path: Path) -> None:
    """Emit list-of-PrimaryVerdict-as-dict JSON for use as a test fixture.

    Stable ordering: sorted by (ticker, trough_1_date) ascending.
    """
    sorted_v = sorted(verdicts, key=lambda v: (v.ticker, v.trough_1_date))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([v.to_dict() for v in sorted_v], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_cohort_fixture(input_path: Path) -> list[PrimaryVerdict]:
    """Inverse of write_cohort_fixture; reads JSON list-of-dict back into
    PrimaryVerdict objects."""
    data = json.loads(input_path.read_text(encoding="utf-8"))
    return [PrimaryVerdict.from_dict(d) for d in data]
