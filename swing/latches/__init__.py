"""Phase 21 Arc A -- the A+ entry-latch derivation (pure) + its readers.

The derivation is a PURE function over pre-fetched inputs: no DB access, no
network, no transaction management (the Phase-12 classifier convention). All
I/O lives in `reader.py` and the web layer.
"""
from swing.latches.identity import LATCH_IDENTITY_COLUMNS, LatchIdentity

__all__ = ["LATCH_IDENTITY_COLUMNS", "LatchIdentity"]
