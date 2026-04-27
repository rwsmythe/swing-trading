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
    - JSON is read as UTF-8 (locale-independent); non-ASCII notes are supported.
    - JSON top-level value must be an object (dict); a syntactically valid file
      whose root is a list/string/number raises ``ValueError`` with the path.
    - Malformed CSV (parser failures, empty, missing OHLCV columns): raise
      ValueError with the file path in the message (operator-debuggability over
      silent skip — clearly unrecoverable, symmetric with malformed-JSON
      behavior). Per Codex R1 M1, parser failures (UnicodeDecodeError,
      ParserError, EmptyDataError, IOError) are caught at ``pd.read_csv`` and
      re-raised as ValueError BEFORE the missing-column check.
    - JSON schema (per Codex R1 M2 + R2 M2 + README §2): ``label`` must be
      ``"flag"`` or ``"none"``; ``notes`` is required (must be present, must
      be string — empty string allowed but missing key raises);
      ``expected_confidence_min`` (if present) must be a float in [0.0, 1.0]
      and is only allowed on ``"flag"`` fixtures. Violations raise ValueError
      with the json path.
    - Bar count: trims to the last 60 rows per spec §4.2 contract; raises
      ValueError if input has <60 rows (operator should use ``period='90d'`` or
      larger to ensure margin).
    """
    if not fixture_dir.exists():
        return []
    fixtures: list[LabeledFixture] = []
    for csv_path in sorted(fixture_dir.glob("*.csv")):
        json_path = csv_path.with_suffix(".json")
        if not json_path.exists():
            continue  # unpaired CSV; skip silently
        try:
            meta = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise json.JSONDecodeError(
                f"{exc.msg} (in {json_path})", exc.doc, exc.pos
            ) from exc
        # Per Codex R3 M1: top-level JSON value must be a dict; otherwise
        # downstream `.get` / `in` calls raise AttributeError / TypeError and
        # mask the path-bearing error contract for operators.
        if not isinstance(meta, dict):
            raise ValueError(
                f"Invalid JSON root in {json_path}: must be an object, got "
                f"{type(meta).__name__}."
            )
        # Per Codex R1 M1: catch real parser failures (binary content, encoding
        # errors, mismatched quotes) BEFORE the missing-column check; re-raise
        # as ValueError with the file path so operators see the path, not a
        # raw pandas internal exception.
        try:
            bars = pd.read_csv(csv_path, parse_dates=[0], index_col=0)
        except Exception as exc:
            raise ValueError(
                f"Malformed CSV at {csv_path}: parser error "
                f"({type(exc).__name__}: {exc})"
            ) from exc
        required_cols = {"Open", "High", "Low", "Close", "Volume"}
        missing = required_cols - set(bars.columns)
        if bars.empty or missing:
            raise ValueError(
                f"Malformed CSV at {csv_path}: empty or missing OHLCV columns "
                f"(missing={sorted(missing)!r})"
            )
        # Per Codex R1 M3 + spec §4.2: enforce 60-bar contract.
        if len(bars) < 60:
            raise ValueError(
                f"Insufficient bars in {csv_path}: spec §4.2 requires ≥60 daily "
                f"bars, got {len(bars)}."
            )
        bars = bars.iloc[-60:]
        # Per Codex R1 M2 + README §2: validate JSON schema.
        label = meta.get("label")
        if label not in ("flag", "none"):
            raise ValueError(
                f"Invalid label {label!r} in {json_path}: must be 'flag' or 'none'."
            )
        if "notes" not in meta:
            raise ValueError(
                f"Missing required 'notes' field in {json_path}: per README §2, "
                f"every fixture must record operator rationale."
            )
        notes = meta["notes"]
        if not isinstance(notes, str):
            raise ValueError(
                f"Invalid notes type in {json_path}: must be string, got "
                f"{type(notes).__name__}."
            )
        ecm = meta.get("expected_confidence_min")
        if ecm is not None:
            if not isinstance(ecm, (int, float)) or isinstance(ecm, bool):
                raise ValueError(
                    f"Invalid expected_confidence_min type in {json_path}: "
                    f"must be number, got {type(ecm).__name__}."
                )
            if not (0.0 <= float(ecm) <= 1.0):
                raise ValueError(
                    f"expected_confidence_min out of range in {json_path}: "
                    f"got {ecm!r}, must be in [0.0, 1.0]."
                )
            if label == "none":
                raise ValueError(
                    f"expected_confidence_min not allowed on 'none' fixture in "
                    f"{json_path}: per README §2, only 'flag' fixtures may pin "
                    f"a confidence floor."
                )
        fixtures.append(
            LabeledFixture(
                name=csv_path.stem,
                bars=bars,
                label=label,
                notes=notes,
                expected_confidence_min=float(ecm) if ecm is not None else None,
            )
        )
    return fixtures
