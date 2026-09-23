"""22-A2 -- the frozen-value evidence class (tier-2): the preflight, the
four-part conjunction, the seventh-column blob and the read-time replay.

F4 (CHARC, ruled in the brief): this module performs NO DB WRITE and opens NO
TRANSACTION, module-wide; its callers are enumerated by test (A2-75).

This file is built across the 22-A2 task ladder; the constant below lands with
migration 0039 (Task 3) because the citation trigger binds the seventh-column
blob's version to it and the #11 drift test compares the two in the SAME
commit as the schema.
"""
from __future__ import annotations

# The seventh-column blob's own version (``$.evidence_version`` of
# ``cited_frozen_value_evidence_json``), mirrored by migration 0039's citation
# trigger literal.  A drift test reads the literal out of the HEAD trigger.
FROZEN_VALUE_EVIDENCE_VERSION = "2026-09-23.1"
