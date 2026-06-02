"""Shared lazy-thumbnail render cap (Phase 14 close-out P14.N1).

Extracted from routes/journal.py so the journal thumbnail route AND the
dashboard open-positions / hyp-rec thumbnail paths share ONE process-wide
matplotlib render cap. Behavior-identical to the SB4 journal constants.
"""
from __future__ import annotations

import threading

# Caps CONCURRENT thumbnail renders across ALL thumbnail routes; a burst that
# exhausts it returns a transient 200+busy fragment (self-retries) rather than
# piling workers behind the matplotlib render lock.
_THUMBNAIL_RENDER_SEMAPHORE = threading.BoundedSemaphore(2)
# Short acquire timeout (module constant so tests can shrink it).
_THUMBNAIL_RENDER_TIMEOUT_S = 2.0
# Short cache lifetime for cacheable (svg / unavailable / not-found) contracts.
# Busy is transient backpressure -> Cache-Control: no-store instead.
_THUMBNAIL_CACHE_CONTROL = "private, max-age=60"
