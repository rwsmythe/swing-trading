# Phase 22 — D53.1: the DBW window start is trough 2 everywhere downstream (the effective-window-start composition)

**Author:** CHARC, 2026-09-14. **Commissioned:** by CHARC's D53 B-gate ruling (branch (c), mail `20260914T180551Z`, thread `dbw-detector-silence`; the operator's standing "proceed" covers the queue). **Sequenced by the orchestrator** off the merged main that carries D53 (`double_bottom_w@v1.1.0`); never in parallel with D53 (same runner/route files).
**Executor:** orchestrator → implementer cell, **opus-high** (runner + a measurement-input route). Reviewer A strong tier to convergence; **Reviewer B REQUIRED** (production code). RD reads the `window_start_date` semantic (§2 F2) — a plan-stage director review, one packet, before the cell starts.
**Tripwire (harness §5):** none crossed (no schema, no module, no dependency, no process, no `swing/trades`/`swing/data`).

---

## §0 READ FIRST (pointers)

1. The D53 ledger's REVIEWER B section and CHARC's ruling (block quote) — B major #1 is this arc's specification.
2. `swing/pipeline/runner.py` — the pattern-detect step: the template close-series slice from `window.start_date` (the `_window_mask` block) and the `window_start_date=window.start_date.isoformat()` persist.
3. `swing/web/routes/patterns.py` — the review confirm path: `start_date = evaluation.window_start_date` with the `pattern_present_outside_window` operator override; the `PatternExemplar(...)` build.
4. `swing/web/charts.py` — the pattern window band from `pattern_evaluation.window_start_date`.
5. `swing/patterns/double_bottom_w.py` — `DoubleBottomWEvidence` (`trough_1_date` is the documented base START; there is no prior-peak field) and the module docstring's anchor contract as rewritten by D53.
6. `swing/patterns/foundation.py` `generate_candidate_windows` zigzag branch (`start_date = anchor_date = swing low`) — UNCHANGED by this arc.
7. `docs/harness-architecture.md` §5.1: the composition gap (this is instance 6: D53's fix made a downstream framing defect REACHABLE); SUPERSESSION-BY-REPLACEMENT.

## §1 THE DEFECT (B major #1, CHARC-confirmed at main 2026-09-14)

After D53 a DBW verdict is produced on the trough-2-anchored window, so `window.start_date` = trough 2. Four consumers treat that as the pattern's start: (1) the runner's template-match close slice starts at trough 2 and omits trough 1 + the center peak; (2) the runner persists `window_start_date` = trough 2 on every DBW row; (3) the chart band shades from trough 2; (4) a review CONFIRM seeds a `pattern_exemplars` row whose `start_date` is trough 2 unless the operator picked `pattern_present_outside_window` and typed a corrected start. Severity measured (orchestrator, live DB `mode=ro`): `template_match_score` is NULL on all 1,563 evaluations for all five classes — (1) is LATENT; (2)–(4) are LIVE the first time a DBW row is emitted or confirmed. Three confirmed DBW exemplars exist today (pre-D53, hand-framed).

## §2 FORK CENSUS

**F1 — the guard first (the exemplar corpus is a MEASUREMENT INPUT). CHOSEN, and it is the FIRST commit — RE-SPECIFIED 2026-09-14 by CHARC's round-0 ruling (mail thread `dbw-detector-silence`, 22:1xZ) after the cell's clean stop: the original text's premise ("a zero-envelope row cannot be confirmed as a W in any case") was FALSE — `_build_zero_evidence` stamps `trough_1_date = window END`, so every one of the 1,563 zero-score DBW rows carries a parseable trough 1 that is not a trough.** The guard, in the review route, for `pattern_class == "double_bottom_w"` and every decision whose exemplar row is READ as a pattern instance (`confirm`, `pattern_present_outside_window`, `multiple_overlapping_patterns` → `confirmed`; `watch` → read by the template corpus); `reject` and `relabel` UNCHANGED: (i) a submitted `corrected_window_start_date` EQUAL to `evaluation.window_start_date` is NOT a correction (the form pre-fills it, so an untouched browser submit is indistinguishable from a typed one; under v1.1.0 the generator start is never a DBW pattern start, so equality is never a deliberate choice) — route-local, undefeatable by the form; (ii) with a genuine operator-typed start, that start wins, always; (iii) otherwise, for a NON-ZERO `geometric_score` row, `start_date` = `structural_evidence_json["trough_1_date"]`; (iv) otherwise (a ZERO-score row — the detector found no W; the operator who sees one is the only source of its start) the route REFUSES with a typed message naming the recovery: enter the first-trough date in the window-correction start. The false-negative label stays reachable, through the honest path. Tests: the four cases above as four tests (the untouched-submit case built with the PRE-FILLED value, not a bare POST); `reject` on a zero row still writes. **BROWSER WITNESS BINDING before merge** (HTMX form class): the operator drives, step by step, (1) an untouched submit on a live zero-score DBW row → the typed refusal; (2) the same row with a typed start → an exemplar with that start; (3) a non-zero row's confirm → trough 1 (a live non-zero row exists only after the first v1.1.0 hit; if seeded on a copy, the unseeded live state is witnessed too). C3 (pre-filling the form with trough 1) is DECLINED here — outside the arc's sites and it still lets an unedited submit through on a zero row; banked as a UX rider.

**F2 — the persisted `window_start_date` and the template slice. CHOSEN:** an EFFECTIVE window start for DBW = `evidence.trough_1_date` when the verdict is non-zero and the evidence carries it; otherwise the generator's `start_date` (unchanged). Applied in the runner at BOTH sites (the `_window_mask` slice and the persist) from ONE local, so the two cannot diverge. Other classes UNCHANGED (their anchor IS the base start). One verdict per class stays; `windows[-1]` stays. **RD reads this packet BEFORE the cell starts:** the `window_start_date` semantic on the temporal log changes for DBW rows from "generator anchor" to "pattern start per evidence" at this arc's first run; the D53 ledger already records the interim span (first `v1.1.0` run .. this arc's merge run) and every interim row's true start is recoverable from `structural_evidence_json`. RD rules whether the log needs any further marker (e.g. a `window_start_source` note in the ledger only — NO schema). Rejected: a schema column for the source (a tripwire for a framing field the evidence already makes derivable).

**F3 — the chart band. CHOSEN:** the band reads the persisted `window_start_date`, so it follows F2 for new rows with no chart change; for pre-existing DBW rows (all zero-score) it is moot. No edit unless the band derives from something else — verify by reading, report.

**F4 — should the generator instead emit a trough-1-anchored window for DBW?** REJECTED (again, as in D53): it changes the one-verdict-per-ticker contract and the anchor semantic for all five classes.

## §3 TESTS

- F1 route test (red first) + its refusal case + the override twin.
- F2 runner test: a synthetic W through the production generator → `windows[-1]` → the persisted `window_start_date` == trough 1 AND the template slice's first bar == trough 1 (assert the slice, not only the column); a non-DBW class through the same path keeps `window_start_date == window.start_date` (the discriminator against an over-wide change).
- The D53 composition test and the four alignment tests stay green unchanged.
- Full fast suite on the final head (`-n 4` if `-n auto` is memory-killed — D52); ruff clean.

## §4 LOCKS

- No schema. No `foundation.py` change. No detector change (D53 owns the detector; a needed detector change is a fork → stop, return).
- Historical `pattern_evaluations`/`pattern_exemplars` rows are NEVER rewritten (RD's lock).
- Supersession by replacement in every comment/docstring that states the window start is the anchor for DBW.

## §5 RETURN (the ORCHESTRATOR posts to `charc,rd` after QA)

Head SHA; the four sites as changed (file:symbol); the F3 determination; the A verdict; the B transcript path + verdict + banked findings with evidence; RD's plan-stage reading quoted; the suite line with SHA. D53 closes on the first post-merge nightly's non-zero DBW count; D53.1 closes when that same run's DBW rows carry a trough-1 `window_start_date`.
