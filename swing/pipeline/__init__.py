"""Public entry point for the nightly pipeline.

Usage from CLI: `python -m swing.cli pipeline run`
Usage from code: `from swing.pipeline import run_pipeline; run_pipeline(cfg=...)`
"""
from __future__ import annotations

from swing.pipeline.runner import RunResult, run_pipeline_internal

__all__ = ["RunResult", "run_pipeline"]


def run_pipeline(*, cfg, trigger: str = "manual") -> RunResult:
    return run_pipeline_internal(cfg=cfg, trigger=trigger)
