# Phase 13 Closer — Next-Phase Triage Agenda

**Status:** STUB landed at T-T4.SB.6 SHIPPED. Operator-paired triage
session driven by T-T4.SB.1 sensitivity-harness OUTPUT.

## Decision points

1. **Path selection per OQ-CL.2 (§1.5.2 deferred disposition):**
   - **Path A** — Phase 14 (operator-defined operational scope).
   - **Path B** — Applied Research focus per V2.1 §X tranche progression
     (first method-record selection from `research/phase-0-tasks.md`
     "Next" section, now containing the A+-like-indicators entry
     promoted at T-T4.SB.1).
   - **Path C** — Combination (Phase 14 + research-branch concurrent
     per V2.1 §V branch posture).

2. **Inputs:**
   - Operator runs `swing diagnose aplus-sensitivity --eval-runs 63`
     against own DB → reviews CSV + markdown at `exports/diagnostics/`.
   - Findings answer: "which A+ criterion thresholds, if loosened, would
     materially increase A+ pipeline volume?"
   - If concentration in 1-2 criteria → threshold-loosening cfg-policy
     proposals candidate for Phase 14 (or for a research-branch method
     record validating the loosening).
   - If distributed → broader research-branch sweep warranted.

3. **OQ-CL.3 — research-branch first-method-record selection meeting:**
   - Scheduled separately post-T4.SB-SHIPPED (operator-paired session).
   - Inputs: sensitivity-harness output + 8 candidate A+-like indicators
     in `research/phase-0-tasks.md`.

## Cross-references

- T-T4.SB.1 deliverables:
  - `research/harness/aplus_sensitivity/` (harness modules).
  - `research/studies/aplus-criterion-sensitivity-2026-05-22.md` (study writeup; findings TBD).
  - `research/method-records/aplus-criteria-calibration.md` (method record stub).
  - `exports/diagnostics/aplus-sensitivity-<ISO>.{md,csv}` (operator-run output).
- T-T4.SB.2 deliverables: metrics wiring audit live; Option 7C fix at 4 surfaces.
- T-T4.SB.3/4/5/6: see T4.SB return report at `docs/phase13-t4-sb-return-report.md`.
