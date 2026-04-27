"""Fixture-loader for chart-pattern flag-v1 integration tests (Task 7.2).

Scans `tests/evaluation/patterns/fixtures/` for paired CSV + JSON files;
returns parametrized test cases. Per spec §4.2, fixtures are immutable
operator-labeled OHLCV pulls; this module just loads them.

Leading-underscore module name opts out of pytest collection (pytest
treats `_fixtures` as a private helper, not a test module).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class LabeledFixture:
    name: str
    bars: pd.DataFrame
    label: str  # 'flag' or 'none'
    notes: str
    expected_confidence_min: float | None


def load_labeled_fixtures(fixture_dir: Path = FIXTURE_DIR) -> list[LabeledFixture]:
    """Scan ``fixture_dir`` for paired CSV + JSON files; return ``LabeledFixture`` list.

    - Returns ``[]`` if directory is missing or empty.
    - Skips unpaired CSV (no JSON sibling) silently.
    - Returns list sorted by ``csv_path.stem`` (deterministic for parametrize ids).
    - Malformed JSON: raise ``json.JSONDecodeError`` with the path in the message
      (operator-debuggability over silent skip — clearly unrecoverable).
    """
    if not fixture_dir.exists():
        return []
    fixtures: list[LabeledFixture] = []
    for csv_path in sorted(fixture_dir.glob("*.csv")):
        json_path = csv_path.with_suffix(".json")
        if not json_path.exists():
            continue  # unpaired CSV; skip silently
        try:
            meta = json.loads(json_path.read_text())
        except json.JSONDecodeError as exc:
            raise json.JSONDecodeError(
                f"{exc.msg} (in {json_path})", exc.doc, exc.pos
            ) from exc
        bars = pd.read_csv(csv_path, parse_dates=[0], index_col=0)
        fixtures.append(
            LabeledFixture(
                name=csv_path.stem,
                bars=bars,
                label=meta["label"],
                notes=meta.get("notes", ""),
                expected_confidence_min=meta.get("expected_confidence_min"),
            )
        )
    return fixtures
