"""Pattern cohort detector evaluator research harness.

Cohort-input-driven invocation surface for Phase 13 chart-shape detectors.
Designed to answer the question gotcha #27 surfaced: production
_step_pattern_detect gates on bucket == 'aplus' BY DESIGN; the harness
runs detectors against loosened-A+ cohorts to test orthogonal-signal hypothesis.
"""
from __future__ import annotations

__version__ = "0.1.0"
