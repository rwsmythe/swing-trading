"""Phase 13 ``swing/patterns/`` top-level module (T2.SB1 + later sub-bundles).

Per plan §A.2 + §A.14 constant placement LOCK: this ``__init__.py`` re-exports
``DETECTOR_PATTERN_CLASSES`` from ``swing.data.models`` for namespace
convenience. Primary constant definitions live in ``swing.data.models`` per
§A.14 LOCK (closes Codex R2 Major #1 + R3 Minor #1).

Re-exports extend per landing sub-bundle:

- T-A.1.1 (landed): ``DETECTOR_PATTERN_CLASSES``.
- T2.SB2 ``foundation.py``: foundation primitives consumed via direct
  ``swing.patterns.foundation`` imports.
- T2.SB3 / T2.SB4 ``vcp``/``flat_base``/``cup_with_handle``/``high_tight_flag``/
  ``double_bottom_w``: per-detector ``*Evidence`` dataclasses consumed via
  direct imports.
- T2.SB5 T-A.5.1 (this commit): ``TemplateMatchHit`` + ``TemplateMatchExemplar``
  (frozen dataclasses from ``template_matching``).
- T2.SB5 T-A.5.2: retrieval functions consumed via direct
  ``swing.patterns.template_matching`` imports.
- T2.SB5 T-A.5.3: ``compute_composite_score`` from ``composite``.

Per Codex R3 Minor #3 closure: ``__init__`` MUST NOT preemptively reference
symbols whose modules don't exist yet. Each re-export lands with the module
it points to.
"""
from __future__ import annotations

from swing.data.models import DETECTOR_PATTERN_CLASSES
from swing.patterns.composite import compute_composite_score
from swing.patterns.template_matching import (
    TemplateMatchExemplar,
    TemplateMatchHit,
)

__all__ = [
    "DETECTOR_PATTERN_CLASSES",
    "TemplateMatchExemplar",
    "TemplateMatchHit",
    "compute_composite_score",
]
