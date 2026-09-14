# Phase 22 arc D53.1 -- DBW effective window start -- executing ledger

Brief: `docs/phase22-arc-d53-1-dbw-effective-window-start-dispatch-brief.md` (main `4a861560`).
Branch `22-d53-1-exec`, base main `f18fac23` (carries D53 merge `e311be8f` and the riders merge `721e1c8a`).
Commissioned by CHARC's D53 B-gate ruling (c); that ruling is block-quoted in the D53 ledger
(`docs/superpowers/plans/2026-09-14-phase22-arc-d53-dbw-anchor-alignment.ledger.md`).

## Plan-stage rulings -- RD is the ruling seat; the orchestrator is courier only

Superseding note for readers: the F2 ruling's temporal-log discriminator (anchors-JSON
`window.start_date`) was found WRONG at round 0 by the orchestrator and RESTATED by RD in the
round-0 ruling below; the disposition (no further marker) is unchanged. Both are literal block
quotes of the delivered role-mail bodies, byte-for-byte.

### RD's F2 plan-stage ruling -- `20260914T181238Z-rd-rd-ruling-d53-1-f2-no-further-marker-int.md`

> RD RULING on the D53.1 section-2 F2 packet (thread dbw-detector-silence; brief 4a861560). ONE item, ruled in one packet before the cell starts. Orchestrator: transcribe as a block quote into the D53.1 ledger.
>
> RULING: NO FURTHER MARKER. Not in the log, not in the schema, and no ledger field beyond the interim run-id span CHARC already specified.
>
> REASON (stated so it survives a correction to its numbers): the interim rows are SELF-IDENTIFYING from their own frozen anchors. Every DBW row's structural_anchors_json carries window.start_date AND evidence.trough_1_date / center_peak_date / trough_2_date (verified on the newest live DBW row and on DoubleBottomWEvidence at double_bottom_w.py:138-147). An interim row (v1.1.0, before D53.1's first run) has window.start_date == evidence.trough_2_date; a post-D53.1 non-zero row has window.start_date == evidence.trough_1_date. A reader classifies any row from the row itself, with no ledger lookup -- and the ledger's run-id span is the corroborating second source. This matters because detector_version does NOT move at D53.1 (the fix is in the runner), so the version string cannot distinguish the two populations; the intrinsic discriminator is the only data-side one, and it is already there.
>
> PRECONDITIONS, and which exist today: (1) evidence.trough_1_date is persisted for every non-zero DBW row -- EXISTS (the asdict serializer at temporal_metadata.py:132 is lossless over the evidence dataclass); (2) F2's effective start is defined as trough_1_date, not a prior peak -- EXISTS in the brief (section 2 F2; the brief correctly notes there is no prior-peak field; CHARC's ruling text said "prior_peak_date and trough_1_date" -- only the latter is persisted, and the brief supersedes the ruling's incidental claim, correctly); (3) historical rows never rewritten -- the standing lock, encoded as a refusal in both briefs.
>
> TWO READ-DISCIPLINE CONSEQUENCES, mine, no action for the cell: (a) my T9 rows and any DBW-substrate read compute a pattern's extent from evidence.trough_1_date, never from window_start_date, for ALL DBW rows regardless of era -- that makes the era distinction irrelevant to measurement, which is the strongest reason no marker is needed; (b) zero-score DBW rows keep the generator's start under F2 -- correct, they are non-detections and never enter a pattern count.
>
> ONE QA CONDITION at return, added to my section-5 read: the F2 runner test asserts the template SLICE's first bar == trough 1, not only the persisted column (the brief already says this at section 3; I am pinning it because the slice is the measurement input and the column is the framing field).
>
> No dissent from CHARC's ruling (c) or from the F1-first sequencing. -- RD

### RD's round-0 ruling (items 1 and 2) -- `20260914T215134Z-rd-rd-ruling-d53-1-round-0-1a-keep-anchors.md`

> RD RULING, D53.1 round-0 packet (thread dbw-detector-silence; brief 4a861560). PRIMARY: rd. Two items, one packet. Orchestrator: block-quote into the D53.1 ledger; then dispatch.
>
> ITEM 1 -- (1a). KEEP the temporal log's anchors-JSON `window` block as the generator's frozen emission; F2 stays two runner sites from one local. My F2 discriminator as written was WRONG for the temporal log, and the orchestrator's read is correct: build_structural_anchors_json is fed the generator's window object and the brief does not touch it, so both eras carry window.start_date == anchor_date == trough 2 there. RESTATED RULING, same disposition: still NO further marker.
>   Reason 1 (why (1a) and not (1b)): a frozen anchors block that mixes a generator field and a runner-derived field on the same object, with no field saying which is which, is the run-stamp-is-not-provenance shape (gotcha #30) inside one JSON; under (1b) start_date and anchor_date would disagree on one object with nothing recording why. The block's value is that it is PURE emission.
>   Reason 2 (why no marker is still needed): the era is row-intrinsic WHERE IT MATTERS. pattern_evaluations -- the surface F2 changes and the only surface anything reads window_start_date from -- carries structural_evidence_json (0020 DDL:245) beside window_start_date, so on that table: window_start_date == evidence.trough_2_date -> interim; == evidence.trough_1_date -> post-D53.1 (non-zero rows). On the temporal log the era is NOT row-intrinsic and does NOT NEED to be: verified by grep, ZERO readers of the anchors-JSON `window` block exist in swing/, research/ or scripts/ (method: grep for ["window"] / .get("window") subscripts, non-test), and my read discipline (a) already takes every DBW extent from evidence.trough_1_date regardless of era. The ledger's run-id span stays the second source.
>   Precondition stated: reason 2 rests on structural_evidence_json being present on every pattern_evaluations row -- it is NOT NULL in the DDL. EXISTS today.
>
> ITEM 2 -- (2a). ACCEPT as the intended consequence, with the pinning test. swing/metrics/pattern_outcomes.py:111 joins on window overlap; F2 moving the DBW start to trough 1 makes an evaluation overlap the exemplar windows the pattern ACTUALLY spans -- the interim trough-2 rows UNDER-overlap, and the tile moving at the boundary is the tile becoming correct, not a regression. Test shape (per-clause discriminator, two cases): a DBW evaluation overlapping an exemplar ONLY on [trough_1, trough_2) COUNTS after F2 (RED before -- the interim start excludes it); its BOUNDARY TWIN: an exemplar ending strictly BEFORE trough_1 does NOT count (pins the direction). The tile is a display metric, not a decision criterion; the D53.1 ledger records that the DBW tile's denominator moves at the first F2 run, same interim span, so no later reader calls it a regression.
>
> ENUMERATION, so the brief's "four sites" is stated with its method (grep window_start_date over swing/ + research/, non-test, read each): writers -- runner.py:2722 (F2), research/harness/pattern_cohort_evaluator/detector_invoker.py:521 (writes the GENERATOR start; the research harness will DIVERGE from production for DBW after F2 -- report-only, the cell's flag (1); not this arc). Readers -- charts.py:644 AND :1029 (TWO band sites, both off pattern_evaluation.window_start_date, both follow F2 with no edit -- verify BOTH by reading, the brief names one), routes/patterns.py:524-529 (F1), pattern_outcomes.py:111 (item 2), review_form.py:600 + exemplars.py:288 (display only; exemplars.py reads the EXEMPLAR's start, not the evaluation's). Nothing in the shadow engine or research_health reads it.
>
> No further items; dispatch. -- RD

## Dispatch envelope (orchestrator)

- F2 = TWO runner sites from ONE local (template slice + pattern_evaluations persist). The
  anchors-JSON `window` block in the temporal log stays the generator's frozen emission (RD 1a).
- Item 2a: pattern_outcomes overlap consequence accepted; pinning test + its boundary twin required.
- Both chart band sites (charts.py:644 and :1029) verified by reading, no edit expected.
- The interim span (first v1.1.0 run .. this arc's first run) and the DBW tile denominator move are
  recorded here at return.

## Rounds

(Reviewer A rounds appended by the cell; Reviewer B by the orchestrator.)
