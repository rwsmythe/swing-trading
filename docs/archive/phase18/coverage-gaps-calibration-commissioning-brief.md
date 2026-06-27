# Commissioning brief — `coverage_gaps` current-vs-historical calibration (research-health monitor #3)

**Author:** Research Director (watch-standard owner + the check's demand-side). **Date:** 2026-06-24.
**Routed to CHARC** — `swing/monitoring/research_health.py` is CHARC-buildable; RD owns the calibration semantics / the watch standard.
**Tripwire:** SUB-tripwire — a calibration WITHIN the existing `_check_coverage_gaps` (read-only monitor; NO schema, NO new module, NO `swing/{trades,data}` carve-out, NO measurement-VALUE change). Same class as the shipped 18-D FIX-1 / CALIBRATION-A/B. CHARC self-certs the tripwire.

## §1 Problem (live instance 2026-06-24 — the first live research-health RED)
`coverage_gaps` counts PERMANENT historical missing-observations toward its red threshold. The observe step records forward-ONLY (NEVER backfills), so a one-time benign event leaves immutable gaps that hold the check — and the 18-F research stoplight — RED for WEEKS (until the affected detections age out of the mature set).

Live: a SINGLE missed manual run on 2026-06-22 (the pipeline is operator-triggered, not a cron) left **842** permanent single-session gaps → overall RED. The drumbeat is HEALTHY (06-24 fully observed, 945 obs), the substrate INTACT (#1 finiteness + #4 structural GREEN), the check is CORRECT (the gaps ARE missing) and calendar-aware (06-19 Juneteenth was correctly excluded — NO holiday bug). With a MANUAL pipeline, missed runs RECUR → recurring weeks-long false-reds → the monitor cries wolf and loses signal value. The SEVERITY semantics conflate benign immutable historical residue with an actionable CURRENT coverage failure.

## §2 Design intent (CHARC + implementer converge the exact rule)
Red `coverage_gaps` ONLY on a CURRENT/ongoing coverage failure — the drumbeat failing to observe the RECENT expected sessions (a trailing lag beyond the existing CALIBRATION-A grace, or a never-observed recent mature detection). ACCEPT (surface in DETAIL, don't drive RED) HISTORICAL gaps the drumbeat has provably moved PAST: the latest expected sessions ARE observed → the drumbeat is healthy → the historical holes are immutable benign residue. Mirrors the #1/#2 baseline philosophy (accept known-historical; red on new/ongoing).

Two candidate discriminators (implementer's call, weigh against §3):
- **(a) trailing-vs-interior:** an interior/leading gap (observations exist AFTER it, up to current) is permanent historical residue → accept; only a TRAILING gap reds (extends CALIBRATION-A). Simplest, but blinds a genuine interior observe-step bug.
- **(b) RD LEAN — whole-session + skip-warning-explained:** a WHOLE-SESSION gap (no pipeline run for that session → EVERY mature detection missing it = a missed run, the 06-22 class) ACCEPTS; a PER-DETECTION interior hole ACCEPTS IF explained by a recorded `pattern_observe` skip-warning (`no bar for observation_date` / `non_finite_ohlc` — the DINO 06-15 class), ELSE REDs (an UNEXPLAINED per-detection interior hole = a real observe-step-bug signal, PRESERVED). Keeps the check's original purpose while accepting the two KNOWN benign classes.

## §3 Locks / verification (RD watch-standard mandates)
- STILL reds on a genuine CURRENT/ongoing failure: a trailing lag >=2 (drumbeat behind/dead) AND a recent never-observed mature detection → RED. Discriminating tests, with pre/post arithmetic.
- The 06-22 class (a whole missed-run session, drumbeat since moved past) → ACCEPTED — the BINDING test: flips RED→green/accepted on the live-DB data shape.
- The DINO class (per-ticker `no bar` ragged skip) → ACCEPTED. (If (b)) an UNEXPLAINED per-detection interior hole → STILL RED (the real-bug signal preserved).
- Accepted historical gaps STILL surface in the check DETAIL (count + sample) — auditable, NEVER silently dropped (#27 silent-skip discipline).
- Real-derived tests (built from the live-DB 06-22 / DINO shapes, NOT premise-constructed — the verify-vs-live discipline).
- NO schema / NO measurement-VALUE change / NO new module / NO carve-out (read-only `research_health.py` #3 only; `compute_research_health` + `write_research_health_artifact` value-unchanged).
- Calibration semantics documented IN the check (like the #1/#2/#3 CALIBRATION comments) + handed to RD for the watch-standard §3.1 amendment.

## §4 Routing / gate
CHARC commissions + sequences (owns the monitor engineering + the tripwire self-cert). **RD reviews the calibration SEMANTICS at the executing return** — the accept-rule + the still-reds-on-a-real-failure discriminators — a watch-standard-owner sign-off, NOT a measurement-integrity merge-block (the monitor is read-only / not measurement-core). Post-build: RD amends watch-standard §3.1 to cite the new accept-semantics. Operator authorizes the dispatch + the merge.
