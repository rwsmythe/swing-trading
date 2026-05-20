"""Phase 13 ``swing/patterns/`` top-level module (T2.SB1 + later sub-bundles).

Per plan §A.2 + §A.14 constant placement LOCK: this ``__init__.py`` re-exports
``DETECTOR_PATTERN_CLASSES`` from ``swing.data.models`` for namespace
convenience. Primary constant definitions live in ``swing.data.models`` per
§A.14 LOCK (closes Codex R2 Major #1 + R3 Minor #1).

T-A.1.1 (this commit) re-exports ``DETECTOR_PATTERN_CLASSES`` ONLY. Later
sub-bundles extend re-exports as their modules land:

- T2.SB2 (``foundation.py``): re-export ``Swing``, ``CandidateWindow``,
  ``VolumeSegment``, and foundation primitives.
- T2.SB3 (``vcp.py``, ``flat_base.py``, ``cup_with_handle.py``): re-export
  per-detector ``*Evidence`` dataclasses.
- T2.SB4 (``high_tight_flag.py``, ``double_bottom_w.py``): re-export
  per-detector ``*Evidence`` dataclasses.
- T2.SB5 (``template_matching.py``, ``composite.py``): re-export
  ``TemplateMatchHit`` + ``compute_composite_score``.

Per Codex R3 Minor #3 closure: T-A.1.1 ``__init__`` MUST NOT preemptively
reference symbols whose modules don't exist yet. Re-exports stay tight
to ``DETECTOR_PATTERN_CLASSES`` until the corresponding modules land.
"""
from __future__ import annotations

from swing.data.models import DETECTOR_PATTERN_CLASSES

__all__ = ["DETECTOR_PATTERN_CLASSES"]
