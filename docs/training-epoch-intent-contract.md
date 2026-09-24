# Training-epoch intent contract

**Status:** LIVE doctrine, created 2026-09-23 by Arc 22-B (F1, RD branch (a)). This file is the live home of the forward intent contract. Clauses (1)-(3) are the 2026-06-10 declaration, quoted verbatim from its former only home, `docs/research-director-context-archive.md` line 84, which stays as the provenance record (an archive is not a home). Clause (4) is the V2.1 section VII.F amendment ratified by the operator on 2026-09-23.

**Pin rule.** The single line below that begins with the block-quote marker and `**(4)` is the pin input: its sha256, taken over the line's UTF-8 bytes with the leading two-byte marker removed and no line terminator, is the value Arc 22-B records in migration `0040`'s header, derived by test from this file. The migration never reads this file. Any edit to that line is a NEW amendment with a new hash and a new ratification, never a correction.

## Clauses (1)-(3): the 2026-06-10 forward intent contract (verbatim)

> (1) A+ fires → take per program, `standard` intent; (2) H2/H4 narrow-cohort fires → the ONLY legitimate `by_design` entries remaining (pre-registered program, not retired tuition; H3 is closed — its question is answered); (3) everything else discretionary → either DON'T enter (the shadow engine prices the watch pool free) or enter as `standard` and be graded as practice.

## Clause (4): `unintended_execution` (amendment of 2026-09-23)

Copied byte-for-byte from `docs/phase22-arc-b-rd-rulings-f1-f3.md` at `e5feec2a`, section 1:

> **(4) `unintended_execution` — an execution nobody decided to make.** A fill produced by the framework's own resting order after its mandate had died (invalidation, lapse, horizon, or the operator's decline), or any fill no entry decision produced. It is NOT `standard` (no decision was made to take the trade) and NOT `hypothesis_test_by_design` (no program fired it). It counts toward NO hypothesis cohort. It is never inferred from text; it is assigned only through the evidence-bearing surface, with the evidence tier and the cited evidence recorded on the row, under the admissibility test: evidence is admissible iff it was recorded before the outcome was known AND is immutable since, immutability verified against the audit trail. A trade already carrying `standard` or `hypothesis_test_by_design` is never relabelled to this value — that is a different evidence class with its own record. Its realized result is reported in the trade-process card's own facet as an execution datum, never as a hypothesis sample.

**Ratification.** The operator, 2026-09-23 ~17:15Z, in the RD session, his words verbatim as recorded by RD (`docs/phase22-arc-b-rd-rulings-f1-f3.md` section 1): *"clause (4) is ratified."*
