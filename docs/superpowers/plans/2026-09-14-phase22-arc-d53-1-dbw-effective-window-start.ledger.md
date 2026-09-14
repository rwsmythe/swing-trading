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

## Cell intake (executing cell)

Rules read from the MAIN repo (`C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md`,
`docs/harness-architecture.md` section 5.1) at main SHA `d44081450d103f95c00639f1d3dcb28546d689b4`.

### STOP before F1 -- premise correction plus two forks the brief and rulings do not settle

No code written, no production commit made. Returned to the orchestrator for a ruling.

1. **Premise correction (brief section 2 F1 parenthetical).** The brief says a zero-envelope row
   lacks a parseable `trough_1_date`. The code: `_build_zero_evidence` stamps
   `trough_1_date = anchor_date` (`swing/patterns/double_bottom_w.py:231`), and every caller passes
   `anchor_date=candidate_window.end_date` (`:530`, `:544`, `:556`, `:575`). Live (plain sqlite3,
   `mode=ro`, `SELECT ... FROM pattern_evaluations WHERE pattern_class='double_bottom_w'`):
   1,563 DBW rows, 1,563 with `geometric_score = 0`, and all 1,563 carry
   `trough_1_date == window_end_date`. Every DBW row reviewable today is a zero envelope with a
   parseable trough 1 equal to the window END. Encoded literally, F1 turns a confirm of any of
   them into a `start_date == end_date` exemplar. (Incidental: the brief's "1,563 evaluations for
   all five classes" is 1,563 PER class, 7,815 total; latest run 175 is still `v1.0.0`, so the
   interim span has not started.)
2. **Fork A -- zero-envelope rows.** A1: derive whenever parseable (one-day exemplars). A2: treat
   `geometric_score == 0` as "no usable trough 1" and refuse like missing/unparseable (matches
   F2's non-zero condition and the brief's stated reason).
3. **Fork B -- decision scope.** The route writes `start_date = window_start_date` for all six
   decisions. B1: `confirm` only (leaves `pattern_present_outside_window` without a corrected
   start and `multiple_overlapping_patterns`, both `confirmed` and read by
   `pattern_outcomes.py:110`, plus `watch`, read by the template corpus at `runner.py:2480`).
   B2: every decision whose exemplar is a measurement input (`confirm`, `watch`,
   `pattern_present_outside_window` without a corrected start, `multiple_overlapping_patterns`);
   `reject`/`relabel` keep today's start. B3: all six, which under A2 makes zero-score DBW rows
   (all 1,563 today) un-rejectable.
4. **Fork C -- the override twin is not reachable as specified through a browser.**
   `swing/web/templates/patterns/review.html.j2:205-206` pre-fills `corrected_window_start_date`
   with `vm.window_start_date`, so every browser submit carries it. Under
   `pattern_present_outside_window` an unedited form therefore sends the generator start (trough 2
   under v1.1.0) as the "corrected" start, and the route cannot tell a typed value from the
   pre-fill. The refusal's named recovery sends the operator down that path. C1: accept (byte
   tests pass; the defect stays live on the recovery path). C2: treat a submitted start equal to
   `evaluation.window_start_date` as not-corrected for DBW. C3: pre-fill the DBW form with trough 1
   (a VM/template edit outside the brief's four sites).

## Rounds

(Reviewer A rounds appended by the cell; Reviewer B by the orchestrator.)

### Round table (Reviewer A, tier `strong`, executing)

| Round | Reviewed head | Crit | Major | Minor | New / reopened | Reverts | Verdict | Context depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|---|
| 1 | `edcc4217` | 0 | 1 | 1 | 2 new / 0 reopened | 0 | NEW_CRITICAL_MAJOR_FOUND | |
| 2 | `c227db38` | 0 | 0 | 0 | 0 new / 0 reopened | 0 | NO_NEW_CRITICAL_MAJOR (loop ends) | |

Pre-review suite at `edcc4217`: `12358 passed, 13 skipped` (`-n 4`), ruff clean.

### Round 1 -- mechanical assertions

- Invocation: `MSYS_NO_PATHCONV=1 wsl.exe bash <scratchpad>/loop531/run_r1.sh` (runner:
  `cat prompt diff | codex exec -p strong -s read-only --skip-git-repo-check -`, cwd = the worktree for
  repo read access; runner written LF via `printf`, output and exit files pre-created Windows-side).
- Exit code MEASURED: `0` (written by the runner to `codex-exit-r1.txt`; the wrapper's `wsl rc=0` awaited
  before reading).
- Transcript non-empty: 794,216 bytes.
- Banner: `model: gpt-5.6-sol`, `reasoning effort: high`.
- `grep -c '^ERROR'` = 0.
- `grep -c '^tokens used'` = 1; value **223,482**.
- Verdict tokens: `^NEW_CRITICAL_MAJOR_FOUND` = 2 (the 0.152.1 double emission), `^NO_NEW_CRITICAL_MAJOR` = 0.
- Scratch-in-input: no `.codex*`/`.copowers*` files exist in the worktree; the transcript's only hits on
  those names are the prompt echo and CLAUDE.md/doc prose.
- Content filter: none observed.

### Round 1 -- evidence (durable copy)

`~/swing-data/review-transcripts/22-d53-1-exec/`: `codex-prompt-r1.md` (6,970 bytes),
`codex-diff-r1.txt` (39,822 bytes; `git diff -U8 25e7a79f..edcc4217`), `codex-review-r1.txt`
(794,216 bytes), `codex-exit-r1.txt` (2 bytes, `0`), `run_r1.sh` (818 bytes).

### Round 1 -- findings and adjudication

1. **major** -- `swing/web/routes/patterns.py` (the DBW guard): a typed corrected start was trusted as
   arbitrary text; any value differing byte-for-byte from the pre-fill won, so a zero-score row could
   bypass the refusal with a non-date, an inverted interval, or another spelling of the pre-filled date.
   **Disposition: ACCEPTED, INTRODUCED** (the byte comparison and the typed-start recovery are this
   arc's; the route's pre-existing acceptance of arbitrary corrected text for OTHER classes is untouched
   and noted as pre-existing, not banked by this arc). **FIXED in `c227db38`:** typed start and end parse
   as dates or refuse (typed 400); the untouched-submit comparison is by date; a start after the end
   refuses; all before any write. Tests RED first (4 failed), then green.
2. **minor** -- declared exclusions unpinned (relabel on a zero row; a typed start ignored under
   confirm/watch/multiple_overlapping_patterns). **FIXED in `c227db38`** (pins; they pass on both sides by
   design, they guard against a future widening).


## Fork ruling after the cell's pre-F1 stop -- CHARC is the ruling seat; the orchestrator is courier only

Serialized: RD reviews this ruling once landed, for the measurement-input half, and dissents upward only.
Brief section 2 F1 was superseded by replacement on main at `693eb333`; the ruling is its text.
Literal block quote of `20260914T221000Z-charc-ruling-d53-1-forks-a2-c2-together-b2-typ.md`, body byte-for-byte:

> RULING (CHARC, the named ruler; serialized: RD reviews this once LANDED for the measurement-input
> half and dissents upward only). Courier: block-quote into the D53.1 ledger, post the path, then
> resume the cell. Every claim in your packet that I ruled on I verified on disk first.
>
> PREMISE CORRECTION OWNED: my F1 parenthetical was false. _build_zero_evidence stamps
> trough_1_date = window end on every zero row, so "lacks a parseable trough_1_date" never
> happens and F1 as I wrote it would have seeded one-day exemplars. Brief section 2 F1 is
> SUPERSEDED BY REPLACEMENT at 693eb333; the ruling below is its text.
>
> FORK A -- A2, with the flag ANSWERED rather than accepted: "no usable trough 1" = geometric_score
> == 0 (ONE condition, shared with F2's non-zero test). The refusal is NOT "a zero row cannot be
> confirmed." A zero row is confirmable ONLY with an operator-TYPED start: the detector found no W,
> so the operator who sees one is the only source of where it starts, and the honest record is
> their date, not a derived end-date or a trough-2 anchor. The refusal message names exactly that
> recovery. The false-negative label you flagged stays reachable, by the path that records the
> truth. A2 and C2 are ruled TOGETHER, as you said they must be.
>
> FORK B -- B2. The guard covers every decision whose exemplar row is READ as a pattern instance:
> confirm, pattern_present_outside_window, multiple_overlapping_patterns (all final 'confirmed',
> read by pattern_outcomes) and watch (read by the template corpus at runner.py:2480). reject
> UNCHANGED -- rejecting must always be possible; relabel UNCHANGED -- it declares another class
> whose start semantic is that class's (report-only if the cell sees a hazard there). B3 refused.
>
> FORK C -- C2, route-local: for a DBW evaluation a submitted corrected_window_start_date EQUAL
> to evaluation.window_start_date is NOT a correction. The form pre-fills it, so an untouched
> browser submit is indistinguishable from a typed one, and under v1.1.0 the generator start is
> never a DBW pattern start, so equality is never a deliberate choice. A start that DIFFERS is
> typed and wins, always. Order in the route: (i) equal-to-generator -> not corrected; (ii) typed
> -> wins; (iii) non-zero score -> evidence trough_1_date; (iv) zero score -> refuse, name the
> recovery. C3 DECLINED in this arc (outside the sites; still lets an unedited submit through on a
> zero row) -- banked as a UX rider. Tests: four cases, the untouched-submit case built with the
> PRE-FILLED value not a bare POST; reject on a zero row still writes.
>
> BROWSER WITNESS BINDING before merge (the HTMX form class; TestClient cannot see the pre-fill):
> the operator drives, one step at a time: (1) untouched submit on a live zero-score DBW row ->
> the typed refusal renders; (2) same row, typed start -> an exemplar with that start; (3) a
> non-zero row's confirm -> trough 1. A live non-zero row exists only after the first v1.1.0
> hit (run 176 at the earliest); if (3) is seeded on a copy, the unseeded live state is witnessed
> too (the seeded-gate rule). You sequence the witness against run 176.
>
> Everything in "checked and holding" stands as you verified it; the F2 tuple-append carrying one
> value to both sites is the shape the brief asked for. The widened interim instruction (no
> confirm / watch / outside-window / overlapping on DBW rows until F1 merges) is correct.
>
> -- CHARC

### Round 2 -- mechanical assertions

- Invocation: `MSYS_NO_PATHCONV=1 wsl.exe bash <scratchpad>/loop531/run_r2.sh` (same runner shape as r1;
  LF verified with `file`; output and exit files pre-created Windows-side).
- Exit code MEASURED: `0` (`codex-exit-r2.txt`; `wsl rc=0` observed before reading).
- Transcript non-empty: 1,089,454 bytes.
- Banner: `model: gpt-5.6-sol`, `reasoning effort: high`.
- `grep -c '^ERROR'` = 0.
- `grep -c '^tokens used'` = 1; value **212,957**.
- Verdict tokens: `^NO_NEW_CRITICAL_MAJOR` = 2 (0.152.1 double emission), `^NEW_CRITICAL_MAJOR_FOUND` = 0.
- Scratch-in-input DISCLOSURE: no `.codex*`/`.copowers*` files were read, but the reviewer read this
  COMMITTED ledger from the worktree (transcript lines 10003 and 10020 echo its round-1 section), so it
  had the round-1 adjudication in view. The committed per-round ledger is the protocol's record and sits
  in the reviewed tree by design; the round's verdict is clean, so there is no replayed finding to
  discount. Recorded, not re-run.
- Content filter: none observed.

### Round 2 -- evidence (durable copy)

`~/swing-data/review-transcripts/22-d53-1-exec/`: `codex-prompt-r2.md`, `codex-diff-r2.txt` (45,979 bytes;
`git diff -U8 25e7a79f..c227db38 -- swing tests`), `codex-review-r2.txt` (1,089,454 bytes),
`codex-exit-r2.txt` (`0`), `run_r2.sh`.

### Round 2 -- findings and adjudication

None. Reviewer's summary: the ruled route order, pre-write refusals, tuple carriage and indexing, the
effective start reused at slice and persist, the unchanged anchors JSON, chart propagation and test
coverage all confirmed. It could not execute pytest in WSL (no pytest there); the suite is run
Windows-side by the cell.

### Convergence

Loop ended at round 2 (first clean verdict), inside the three-round ceiling. Summed `tokens used`
across counted rounds: 223,482 + 212,957 = **436,439**.

Final-head suite at `12d1b888` (code identical to `c227db38`): `12366 passed, 13 skipped` (`-n 4`), ruff clean.


## Reviewer B (orchestrator's gate) -- recorded by the orchestrator

- Reviewed head `064a6490` (code = `c227db38`), cold audit, repo read access, cwd = the worktree.
  Invocation `MSYS_NO_PATHCONV=1 wsl.exe bash .../reviewer-b/run_b.sh` (`codex exec -p strong -s read-only`).
- Assertions: exit code MEASURED `0`; transcript non-empty; banner `gpt-5.6-sol` / reasoning effort `high`;
  `^ERROR` = 0; `^tokens used` = 1, value **199,773**; `^NEW_CRITICAL_MAJOR_FOUND` present (x3, the 0.152.1 echo),
  `^NO_NEW_CRITICAL_MAJOR` = 0.
- Evidence: `~/swing-data/review-transcripts/22-d53-1-exec/reviewer-b/` (`prompt-b.md`, `diff-b.txt`
  = `git diff f18fac23..064a6490 -- swing tests`, `review-b.txt`, `exit-b.txt`, `run_b.sh`).
- Claims 1-5 HOLD (no DBW exemplar from window_start_date or a zero envelope under the four decisions; refusal
  precedes every write; pre-fill equality not defeatable; tuple extension complete; other classes unchanged).
- **major #1** -- the refusal fragment replaces the review form (no `hx-target`; `app.py` `_handle_http_exc`),
  destroying the recovery controls it names. PRE-EXISTING across every 400 the route raises; D53.1 placed a 400
  on the ruled recovery path. **minor m2** -- a malformed persisted `window_end_date` passes through (single
  writer, no CHECK). **minor m3** -- seven invariant pins pass on both sides (labelled, twins exist).

## B-gate ruling -- CHARC is the ruling seat; the orchestrator is courier only

Literal block quote of `20260914T233826Z-charc-ruling-d53-1-b-gate-i-reload-first-text.md`, body byte-for-byte:

> RULING (CHARC, the named ruler; RD CC holds). Courier: block-quote into the D53.1 ledger.
> Verified on disk by me before ruling: review.html.j2 form carries hx-post + hx-headers and NO
> hx-target (innerHTML of the form itself); app.py _handle_http_exc returns a fragment for an
> HX-Request; base.html.j2's responseHandling override makes the 4xx swap happen. B major #1 is
> real and PRE-EXISTING across every 400 the route raises; D53.1 put a 400 on the ruled
> recovery path, which is what made it visible.
>
> B major #1 -- BRANCH (i), with the rider COMMISSIONED rather than banked:
> 1. In this arc: the refusal text tells the operator to RELOAD the page, then choose
>    pattern_present_outside_window and type the first-trough start. Route text only, inside
>    the ruled sites. The witness reloads between steps. This is a documented recovery on a
>    defect that writes nothing; the structural fix widens a measurement-guard arc into a
>    form-wide UX change with its own browser witness, and "fix the surrounding surface at the
>    gate" is the unbounded-arc failure the introduced-vs-banked boundary exists to stop.
> 2. The structural fix is D56, its own register row and a tests+template rider, sequenced by
>    you after D32+D50: the review form's error fragment renders in a sibling region (hx-target
>    on the form to an error div beside it, the form surviving), covering EVERY 400 the route
>    raises -- and C3 (pre-fill the DBW correction start with trough 1 for non-zero rows) rides
>    WITH it, same template, same class. Its own browser witness. I bank the row now.
> 3. Not accepted as a defense: "a reload restores the form" without the message saying so.
>    An undocumented recovery is the unactionable-surface class (D35); a documented one is not.
>
> m2 -- OUT OF SCOPE as you propose, and thank you for stating it rests on the single writer,
> not on the schema; the row that carries this must say the same (window_end_date has no CHECK).
> Not a schema-prevented value; a single-writer value. If a second writer ever lands, it re-opens.
> m3 -- NO ACTION. A deliberate pass-both-sides pin is a pin when it is LABELLED as one and its
> discriminating twin exists; the cell labelled them and ran the mutation on the zero-score pin.
>
> WITNESS: steps 1-5 on the live DB against the worktree's code on a side port, reload between
> steps, as you laid out. Step 4 (typed-start exemplar) and step 5 (reject) WRITE live exemplar
> rows: the operator chooses live-honest vs copy at each, per RD's concurrence; a witness must not
> mint an exemplar to pass. Step 6 waits for run 176 or a seeded copy plus the unseeded live state.
> The refusal text change is a code change after B ran: minor scope (message text), suite on the
> final head, no re-round (the stopping rule); B does not re-run for it.
>
> -- CHARC
