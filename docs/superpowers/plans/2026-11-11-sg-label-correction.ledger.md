# Ledger: the watch-origin label correction arc plan

Plan: `docs/superpowers/plans/2026-11-11-sg-label-correction.md`. Brief: `docs/sg-label-correction-arc-brief.md` (`3b64f9ec`). Base `main` `f1eb4051`. Recipe read at the MAIN copy (main `8c1ceae2`) on 2026-11-11.
Transcripts: `C:\Users\rwsmy\swing-data\review-transcripts\sg-label\` (per-round copies, named in the round table with byte sizes).

## Rulings of round 0 (verbatim, binding)

### CHARC, `20261111T181814Z` (msg-id `3761be35a1dc689e`)

```text
file: 20261111T181814Z-charc-ruling-sg-arc-round-0-f1-f9-ruled-f2-b-l.md
------------------------------------------------------------------------
---
from: charc
to: orchestrator
type: status
subject: RULING: SG arc round 0 -- F1-F9 ruled (F2 = B last fire, RD concurs; F5 gains the by_design gate); P5, P13
posted: 2026-11-11T18:18:14Z
msg-id: 3761be35a1dc689e
---

CHARC round-0 rulings on the SG label arc packet (20261111T181545Z; ledger bafddb6a on sg-label). Every premise correction was re-read at the code at this seat 2026-11-11: 0039 is the live rebuild (admission_tier at :210-211, four triggers incl. trg_pc_no_replace :695; the citation graph requires a today_decision row :783-792; the update trigger compares the recommendation columns with = at :740-751); 0040 uses PRAGMA legacy_alter_table for the rename (:301-303); H4 is _capital_blocked_match on aplus only (hypothesis.py:285). The brief's six premises are CORRECTED as the ledger says; the brief is not re-issued, the ledger is the record (the plan-stage protocol).

PREMISE NOTES
- P5: state the DIRECTION from the live 0041 trigger text before encoding. A bare `WHEN NOT (... = ...)` with a NULL operand evaluates NULL and the trigger DOES NOT FIRE (fails OPEN: the forbidden update passes); only a COALESCE wrapper turns it into an ABORT. The two outcomes are opposite and both wrong; `IS` fixes either. Test 1g asserts BOTH: the permitted FK SET NULL succeeds on a kind-2 row, and a forbidden column change on a kind-2 row with NULL recommendation columns is still ABORTED.
- P13: YES. db.py's EXPECTED_SCHEMA_VERSION, the BackupGateSpec row and the expected-table floor are INSIDE "migration 0042" by definition; the lock reads that way.
- P11 (LQDA, candidate night post-dating the entry): BANKED to CHARC as a register row at the arc's close (the charter is at its cap; the row lands with that compression). Same #30 family, not this arc.
- P15: 36 is the count; my 37 was a -l over a broader pattern. Closed.
- F0: the orchestrator's ruling stands (fast tier, three counted rounds + self-sweep; the recipe governs the plan loop; the brief's strong chain is the executing loop's). No dissent.

THE FORKS
- F1: A. correction_kind IN (fill_unset_provenance, watch_fire_relabel); admission_tier gains last_fire; a coupling CHECK (kind 1 <-> the three old tiers, kind 2 <-> last_fire). Two axes, two mirror families, both in the drift test. last_word on a kind-2 row would be a false label.
- F2: B, LAST FIRE, with the confirmation idiom made exact. The cited row is DERIVED: the newest candidates row of the ticker within the window (action session <= the fill session) whose as-of narrow matcher (include_baseline=False) returns exactly one match; the operator's --cite-fire-candidate must EQUAL the derived id, and a mismatch REFUSES naming both ids (never "closest wins"). For trade 29 the derivation is 15901. Citation-shopping is closed by mechanism, and the label cost of choosing between two H2 fires is zero by construction (same exact failing set, same label). THE ASYMMETRY WITH T2 IS INTENDED and I rule it so, subject to RD's cohort reading: the forward path (T2) has the operator present at the decision and no persisted record of it, so assertion is the ONLY source and the night is operator-asserted (D96's tier); the retro path (T1) has only persisted rows, so derivation is the ONLY evidence and the operator's id is a confirmation. One rule per path, each the strongest its evidence admits. RD's reading landed before this post (20261111T181710Z) and CONCURS: B, the asymmetry intended by the admissibility test (T2 records pre-outcome; T1 runs post-outcome, so a choice there is post-outcome testimony). F2 is CLOSED in one round. RD's read rule (H2 n split three ways: last-word entries, operator-named earlier nights, kind-2 rows; no new column) is RD's to land in the watch-standard at the merge; the plan says in \xa70 whether the backlink expresses the partition, and says so if not.
- F3: A. The three recommendation columns nullable; kind 2 -> all NULL, kind 1 -> all NOT NULL by CHECK. The citation-graph trigger's kind-2 arm KEEPS every other leg (candidate belongs to the cited run and is bucket 'watch'; the frozen run anchors are that run's own columns; the pipeline row owns the run, is complete, supplied the bound; the hypothesis-status interval is what was frozen) and drops only the recommendation leg. Write the kind-2 arm as its own `WHEN NOT COALESCE(...)` branch; a NULL anywhere in it must ABORT, never pass.
- F4: A. corrected_fields_json = exactly ["trades.hypothesis_label", "trades.candidate_id"]; pre/applied envelopes carry all three keys, origin equal both sides.
- F5: A, PLUS RD's condition (20261111T181710Z item 3), RULED IN: kind 2 is admissible ONLY for a trade whose entry_intent is ALREADY hypothesis_test_by_design. The derivation finds a fire in the rows; it cannot find that the operator ACTED on it; the intent recorded at the lock, pre-outcome, is the admissible evidence that a program fired the trade. A standard-intent watch trade within five rows of a one-night flicker stays H5 practice. The correction fixes the LABEL, never the intent. Full eligibility: trade_origin pipeline_watch_manual; entry_intent hypothesis_test_by_design; label and candidate_id non-null; the current candidate_id IS the ticker's last-word row before the fill (the batch-night signature, existing ranking reused); not latched; no prior correction (SELECT-first returns the existing id). Refused eligibility names the failing condition. No fourth include_baseline site; the governance tripwire stands. RD's item 4 (the fill against the cited fire's pivot): RECORDED, never gated -- both values already sit in the cited candidate snapshot and the entry fill snapshot on the row; the plan adds no column and no comparison.
- F6: A. T2 offers the last N rows from COMPLETE runs, restricted to the bucket of the latest complete run's row, so origin, bucket and label agree by construction. RD CC.
- F7: A. CLI behaviour unchanged; the prefill line prints the night it used; the CLI chooser banked (trigger: an operator CLI entry mis-stamp).
- F8: A. No sandbox branch; nothing here is Schwab-derived; kind 1 has none.
- F9: A. One closure extended with the watch rules; the digest moves; one DERIVATION_RULE_HISTORY entry; both kinds write the head; live rows keep theirs.
- N = 5 stands unless RD adjusts; the ledger's rationale (one briefing week covers a GTC buy-stop placed off a briefing) is recorded as the reason, not measured.

The plan's own choices (kind-1 CHECKs verbatim inside a CASE correction_kind wrapper; no new column; the two candidate_id readers that shift toward the acted-on night, named; T4's one canonical-date gate and the finite-positive price at both services) are ACCEPTED as written. The two shifting readers get one sentence each in the plan's \xa70 limitations and one test each pinning the shifted reading.

Fresh cell folds these in, runs the fast loop, and the plan comes back to charc for the plan-stage read (RD CC). Nothing else open at this seat on this arc.
```

### RD, `20261111T181710Z` (msg-id `4ad77b989edf42e3`)

```text
file: 20261111T181710Z-rd-reading-sg-arc-f2-b-derived-t1-t2-asymme.md
------------------------------------------------------------------------
---
from: rd
to: orchestrator
type: status
subject: READING: SG arc F2 = B derived, T1/T2 asymmetry intended; ask F5 gate on by_design intent; N=5 accepted; F6 CC
posted: 2026-11-11T18:17:10Z
msg-id: 4ad77b989edf42e3
---

RD on the SG arc round-0 packet (orchestrator 20261111T181545Z; ledger at bafddb6a, F2/F5/F6/N read there). CHARC rules the forms; this is my cohort reading given now so the ruling and the reading land in one round. If CHARC rules F2 otherwise I re-read; nothing here binds a form.

F2 -- COHORT READING: B (last fire, derived) for the correction instrument, and the asymmetry with T2 is INTENDED. T1 and T2 must NOT share one rule.
1. The reason is the admissibility test the intent contract already carries: evidence is admissible iff recorded before the outcome was known and immutable since. T2 (the entry form) records the operator's named decision night AT THE LOCK, before the outcome: operator-asserted, D96's tier, admissible. T1 (the correction) runs AFTER the outcome is known: an operator CHOICE among nights at that point is post-outcome testimony, so the night must be DERIVED from persisted rows and the operator's id can only confirm it. A would let a closed trade's cohort be chosen with its R in view. B closes that.
2. Why B costs the cohort nothing: H2 is the exact set {proximity_20ma}, so every H2 fire for a ticker carries the same label; which fire night is cited moves the cited row's pivot and stop, never the cohort. And since D84 a watch citation reaches H2 only (P4), so kind 2 is an H2-only instrument. Confirmed for trade 29: 15901 is the only narrow match in its window.
3. ONE CONDITION I ASK CHARC TO PUT IN F5 (cohort semantics, mine to state): kind 2 is admissible only for a trade whose entry_intent is ALREADY hypothesis_test_by_design. B derives a fire from the rows; it cannot derive that the operator ACTED on it. A standard-intent watch trade that happens to sit within five rows of a one-night H2 flicker must not become an H2 sample by correction: by clause (3) it is practice, counted in H5 standard. The intent was recorded at the lock, pre-outcome, so it is the admissible evidence that a program fired the trade; the correction fixes the LABEL, never the intent. Trade 29 satisfies it.
4. Record, do not gate: the entry fill against the cited fire's pivot (trade 29: 11.95 vs 11.949). It is the mechanical corroboration that the filled order was the fire's order; a gap fill makes it unreliable as a gate, and it is worth having on the row for the H2 read.
5. READ RULE for H2 from this arc forward (I will put it in the watch-standard at the merge): every H2 decision read reports n split three ways -- fire-night-is-last-word entries, operator-named earlier-night entries (T2; derivable as trades.candidate_id's run differing from the ticker's last-word run before the fill), and kind-2 corrected rows -- with a sensitivity excluding the operator-named ones. No new column is needed for that partition; if the plan finds the backlink cannot express it, say so and I re-read.

N -- WATCH_FIRE_WINDOW_ROWS = 5: ACCEPTED, with its consequence stated. A fill more than five of the ticker's rows after its fire is not an H2 program fire, in T2's offer or T1's walk. The live case that would have tested it: GTLB fired on eval 187 (10-27) and its order rested unfilled until the name rotated out about two weeks later; a fill in the second week would have been outside the window and correctly so, a one-night fire with the match long lapsed is a different trade. I will tell the operator the practical form: a resting hyprec order older than a week of briefings is cancelled or it stops counting. Not adjusted.

F6 -- CC, no dissent with A (same-bucket restriction). Cohort note only: when the latest night is aplus, the offer is aplus nights and the latch path governs; a watch-night fire followed by an aplus night is then an A+ entry, which is the right reading.

P4 noted for my record: H4 is unreachable by a watch citation since D84; the brief's "H2/H4" for kind 2 is H2 in practice.
```

## Rulings of the fold (verbatim, binding; source `fold-rulings.txt`, 7,333 bytes)

### CHARC, `20261111T183325Z` (msg-id `b3be7323baec557b`) -- E3/E1/E2 confirmed

```text
file: 20261111T183325Z-charc-ruling-sg-fold-e3-refuse-confirmed-e1-an.md
------------------------------------------------------------------------
---
from: charc
to: orchestrator
type: status
subject: RULING: SG fold -- E3 REFUSE confirmed, E1 and E2 confirmed; R1 my pivot claim was wrong, RD rules R1 + E4
posted: 2026-11-11T18:33:25Z
msg-id: b3be7323baec557b
---

CHARC on 20261111T183248Z (fold 08ee3b57). E3 CONFIRMED: REFUSE. A window row whose as-of narrow matcher returns two or more matches is AMBIGUOUS, and the walk must never pass it to derive an older fire past a newer one; the refusal names the row, its run and the match set. That it cannot occur on today's registry is why it is cheap; a registry edit is what would make it matter, which is exactly when a silent pass-over would be wrong. Test it with a scratch registry that produces two narrow matches on the newest row. E1 CONFIRMED: the by_design intent gate enforced in SQL in the kind-2 arm's trade EXISTS, with the Python mirror models.PROVENANCE_WATCH_FIRE_ENTRY_INTENT compared to the trigger literal by drift test 1m; grep the member separately. E2 CONFIRMED: the citation trigger's top-level WHEN NOT gets the COALESCE wrap; no kind-1 outcome changes, and one test asserts that on the two live rows' shapes. P5 as folded is the correct reading (the live trigger is the COALESCE form, so the permitted FK SET NULL would ABORT; IS fixes both; 1g asserts both halves with the bare-form sibling) -- recorded. R1: MY INCIDENTAL CLAIM WAS WRONG. I wrote that the pivot already sits in the cited candidate snapshot; candidate_provenance_snapshot (cohort_provenance_correction.py:807) carries no pivot. A ruling's reasoning binds, its incidental factual claims are claims (harness section 2); this one failed at the code and I own it. The backlink reads the pivot through cited_candidate_id -> candidates.pivot, immutable under 0037's candidates triggers, and the fill price is in the fill snapshot. Whether the backlink suffices or the pivot goes into the row's own text is RD's (R1), as is E4 (the partition: join to provenance_corrections plus direction strictly-earlier, with the after-fill LQDA rows as a named residual). I hold on both. F6's edge (no aplus-or-watch row on the latest complete run -> empty offer, today's form, test 2k) ACCEPTED. Round 1 opens on RD's R1 + E4.
```

### RD, `20261111T183327Z` (msg-id `469aa43adc1ca7ba`) -- R1 and E4

```text
file: 20261111T183327Z-rd-ruling-sg-plan-r1-the-immutable-backlink.md
------------------------------------------------------------------------
---
from: rd
to: orchestrator
type: status
subject: RULING: SG plan R1 = the immutable backlink is enough; E4 = four-line H2 partition, corrections join first
posted: 2026-11-11T18:33:27Z
msg-id: 469aa43adc1ca7ba
---

RD rulings on the two cohort items in the orchestrator's 20261111T183248Z (SG plan folded at 08ee3b57). Round 1 may open on these as far as my seat goes.

R1 -- THE BACKLINK IS ENOUGH. No pivot text on the row, no column, no comparison. The evidence rule asks two things of the pivot: recorded before the outcome, immutable since. candidates.pivot was written by the fire night's evaluation run and 0037's triggers make the candidates row immutable, so cited_candidate_id -> candidates.pivot satisfies both; copying it into the row would add a second copy that can only agree or be wrong. Correction to my own item 4 and to the ruling text that followed it: the pivot is NOT in candidate_provenance_snapshot; it is reached through the backlink. One condition so the read stays honest: the plan's section 0 names the two sources by path (pivot = candidates.pivot via cited_candidate_id; fill = entry_fill_snapshot_json $.price) and states that the pair is RECORDED EVIDENCE, NOT A GATE. If any path can null cited_candidate_id on a kind-2 row (an FK SET NULL), say so in section 0 and I re-read; an immutable candidates row should make that unreachable.

E4 -- ACCEPTED: the join plus direction, no new column, FOUR lines. The H2 read rule I land in the watch-standard at the merge is, for every trade whose label is H2, evaluated in this order:
 (1) KIND-2 CORRECTED: a provenance_corrections row with correction_kind watch_fire_relabel exists for the trade. Checked FIRST, whatever the candidate's night.
 (2) LAST-WORD ENTRY: no such correction, and trades.candidate_id's evaluation run IS the ticker's last-word run before the fill.
 (3) OPERATOR-NAMED EARLIER NIGHT: no such correction, and the candidate's run is STRICTLY EARLIER than that last-word run (T2's assertion; D96's tier).
 (4) RESIDUAL, AFTER-FILL: the candidate's night is after the fill (the banked LQDA class, P11). Reported as its own named line, counted in none of the three, never folded silently into (3).
Every H2 decision read reports all four and a sensitivity excluding (3). The plan's section 0.2 should state exactly this order; a test that pins the classifier on one row of each line (trade 29 after correction is line 1) is welcome but is CHARC's call on form.

CHARC: E1 (my intent gate also enforced in the kind-2 trigger arm, with the drift mirror) is the stronger form and I have no dissent; E2 and E3 are yours. On E3 my cohort note only: REFUSE on a multi-match row is the right reading, an ambiguous newer row must never be passed over to reach an older fire.
```

### CHARC, `20261111T183404Z` (msg-id `c4334e2ee24ce9b7`) -- the classifier-test lock; R1's condition

```text
file: 20261111T183404Z-charc-ruling-sg-fold-closed-rd-s-r1-e4-stand-t.md
------------------------------------------------------------------------
---
from: charc
to: orchestrator
type: status
subject: RULING: SG fold closed -- RD's R1/E4 stand; the four-line H2 classifier test is NOT this arc's (lock); round 1 opens
posted: 2026-11-11T18:34:04Z
msg-id: c4334e2ee24ce9b7
---

CHARC on RD's 20261111T183327Z. R1 and E4 stand as ruled; no dissent. The one form item RD left to me: a classifier test pinning one row per partition line is NOT this arc's. The arc's lock names its files (cohort_provenance_correction.py, entry.py, exit.py, migration 0042, models.py, the corrections repo, the entry form) and no H2 reader is among them; the four-line order is RECORDED in the plan's section 0.2 verbatim as RD wrote it (kind-2 corrected first; last-word; strictly-earlier operator-named; after-fill residual, its own line, never folded) and lands in the watch-standard at the merge as RD's docs-only text. The classifier and its four-row test come with the FIRST reader change that implements the partition (owner RD on semantics, CHARC on form), with trade 29 post-correction as the line-1 row. R1's condition is accepted into the plan: section 0 names both sources by path (candidates.pivot via cited_candidate_id; entry_fill_snapshot_json $.price), states the pair is recorded evidence and not a gate, and states whether any path can null cited_candidate_id on a kind-2 row (the FK's ON DELETE clause, read at the DDL; if SET NULL, say so; if the candidates row is immutable the path is unreachable and the sentence says that). Round 1 opens. Nothing else is outstanding at this seat before the plan-stage read.
```

### Fold-2 record (commit after `08ee3b57`, before round 1)

- **E3 RULED, REFUSE (CHARC; RD concurs).** T1.6 step 7: the refusal names the row, its run and the match set. Test 1n's case is now the NEWEST window row matching two narrow hypotheses under a scratch registry.
- **E1 RULED (CHARC; RD no dissent).** The encoding is unchanged. The member `hypothesis_test_by_design` is already on the separately-grepped list in the mirror closure, and 1m compares it.
- **E2 RULED (CHARC).** NEW test 1v: the two live rows' shapes are accepted, and the same shapes with one leg broken are refused, identically at v41 and v42. 1v lands in the T1.1 commit.
- **R1 RULED (RD): the backlink is enough.** Section 0.4 is rewritten:
  - both sources are named by path, and the pair is called RECORDED EVIDENCE, NOT A GATE;
  - the FK is read at the DDL: `0039:126` is `NOT NULL ... ON DELETE RESTRICT`, NOT SET NULL, and it is copied verbatim;
  - `candidates` is immutable through 0037's triggers, so the null path is UNREACHABLE, and the section says so;
  - the fill price is frozen in the snapshot and survives the permitted `entry_fill_id` SET NULL.
- **E4 RULED (RD) and the classifier lock (CHARC `20261111T183404Z`).** Section 0.2 now RECORDS RD's four lines VERBATIM, in RD's order. No H2 reader changes. The classifier and its four-row test are NOT this arc's: they come with the first reader change that implements the partition, with trade 29 post-correction as the line-1 row.
- **Flagged to RD, not classified by the plan:** an H2-labelled trade with `candidate_id IS NULL` meets none of the four lines.

## Fold record (each fork, its ruled branch, and where the plan now carries it)

- **F0 (A, orchestrator; CHARC no dissent).** The loop runs at the `fast` tier, with the banner expected to read `gpt-6-luna` / `medium`. It has three counted rounds and then an uncounted self-sweep, and a fourth round needs the orchestrator's written authorization. The plan's status line carries this.
- **F1 (A).** T1.1, unchanged encoding: `correction_kind` (two values), `admission_tier` + `last_fire`, the coupling CHECK, two mirror families in 1m.
- **F2 (B; RD concurs, asymmetry intended).**
  - T1.6 step 7 is rewritten to the exact idiom. The last fire is DERIVED as the newest window row whose as-of narrow matcher (`include_baseline=False`) returns exactly one match. `--cite-fire-candidate` must EQUAL it, and a mismatch refuses NAMING BOTH ids.
  - The matcher step is factored out of `derive_cohort_keys_for_fire` as `_as_of_narrow_matches`, so the walk can pass over a zero-match row. `derive_cohort_keys_for_fire` keeps its `len != 1` refusal.
  - Section 0.1 states the T1/T2 asymmetry.
  - Test 1n's mismatch case asserts both ids.
- **F3 (A).**
  - T1.4.1 edit 2: the kind-2 arm is its OWN `COALESCE((...), 0)` branch. Its two JSON reads are now written `json_valid`-guarded in the plan; the draft had deferred that to execution.
  - The plan lists every other leg as KEPT for kind 2.
  - Edit 0 (NEW) wraps the trigger's top-level WHEN (see E2).
- **F4 (A).** The T1.3 table row, tag only.
- **F5 (A + RD's intent gate, ruled in).**
  - T1.6 step 3 is rewritten as the ordered conditions (a)-(e), each refusal naming its condition.
  - Not-latched stays at step 5, and SELECT-first stays at step 2, ahead of eligibility.
  - The SQL side of the intent gate is in edit 2 (E1). T1.5 gains `PROVENANCE_WATCH_FIRE_ENTRY_INTENT`, and 1m compares the two.
  - Tests: 1n both modes (the standard-intent trade is refused and its by-design twin 1a is accepted); 1h second case.
  - RD item 4, the fill against the pivot, is RECORDED and not gated: section 0.4 and test 1r. See the fact correction R1.
- **F6 (A; RD CC).**
  - T2.1 calls `origin._latest_complete_evaluation_run_id` instead of re-spelling it.
  - NEW edge: when the latest complete run holds no aplus or watch row for the ticker, the lister returns `[]` and the form is today's form (test 2k). Without this, the F6 restriction was undefined in exactly the case where origin is `manual_off_pipeline`.
- **F7 (A).** T2.4, tag. The chooser is banked with CHARC's trigger.
- **F8 (A).** T1.6, tag.
- **F9 (A).** T1.6, tag.
- **N = 5 (CHARC stands, RD accepted).** T2.1, and section 0.5 item 6 states RD's consequence.
- **P5 (direction, from the live text).**
  - T1.4.3 is rewritten. The live update trigger is the 0041 COALESCE form (`0041:126/:180`; `sqlite_master` read `mode=ro`, 4,153 chars), with `=` at `:144/:159/:162`.
  - The live direction is therefore an ABORT of the permitted FK SET NULL on a kind-2 row (fail-closed). A bare form would fail OPEN on a NULL -> value change. `IS` fixes both.
  - Test 1g asserts both halves, plus a sibling run on a bare-form scratch trigger that proves the forbidden half discriminates the fail-open direction.
- **P13 (yes).** The Locks line now says the `db.py` version, gate row and floor are inside migration 0042, in T1's first commit.
- **P11.** BANKED to CHARC as a register row at the arc's close (dispositions below).
- **P15.** Closed at 36; the consumer-table method line says so.
- **The plan's own choices (ACCEPTED).**
  - The two shifting readers each get one sentence in section 0.3: `pattern_outcomes._count_reached_1r_hit_stop` (test 2j, through the T2 POST, aplus nights) and `review_form._build_outcome_distribution` (test 1u, through a kind-2 correction).
  - The trailing "Accepted limitations" list moved into section 0.5 and gained items 5 and 6.
- **RD's H2 read rule (item 5).** Section 0.2 says plainly that the backlink ALONE does not express the partition as RD phrased it. A kind-2 row and a P11 post-dating row both "differ from the last-word run". With the corrections-table join and a direction (strictly earlier) the partition is expressible with no column, and a residual fourth line is named. RD re-reads.

## Facts in the rulings re-read at the code (the intake check, recipe section 3 rule 1)

- **R1.** The ruling says the pivot "already sit[s] in the cited candidate snapshot". **The code differs:** `candidate_provenance_snapshot` (`cohort_provenance_correction.py:807-840`) carries id, run, ticker, bucket, `rs_method` and criteria, and NO `pivot`. **The encoding:** the pivot is recorded BY BACKLINK, `cited_candidate_id -> candidates.pivot`. `candidates` rows are structurally immutable through 0037's `trg_candidates_no_update`, `_no_delete` and `_no_replace`, all three present in the live `sqlite_master`. The fill price IS in `entry_fill_snapshot_json` `$.price`, as required by the 22A-R15-01 clause. The plan adds no column and no comparison. Live values: fill 60 is 11.95, and the pivot of 15901 is 11.949 (as are 15811 and 15980).
- **R2.** CHARC's 0039 anchors (`:695`, `:783-792`, `:740-751`) are re-read and agree with the file. The live update trigger is 0041's copy of `0039:704-763` with the wrap. The direction in P5 follows the LIVE (0041) text, as encoded.
- **R3.** The live citation trigger has 1,539 stored lines; the draft said 1,540. Its WHEN is the bare `WHEN NOT (`, which is why edit 0 exists.
- **R4.** "For trade 29 the derivation is 15901": this re-reads true from the census criteria. 15980's non-pass set has two members, so it has zero narrow matches. 15901's set is `{proximity_20ma}`, which gives one match, H2. Test 1a executes it.

## Encoding choices the rulings did not state literally (all four now RULED; see the fold rulings)

- **E1 (RULED, CHARC `20261111T183325Z`) -- RD's intent gate also lives in SQL.** The kind-2 arm's trade `EXISTS` carries `t.entry_intent = 'hypothesis_test_by_design'`. **Reason:** this table's schema IS the evidence rule (0036). Intent is a FACT on the trade, not a ranking, so SQL may verify it. Without the clause, a raw kind-2 insert for a standard-intent trade satisfies every structural check. **Cost:** one literal more in the mirror family, compared by 1m.
- **E2 (RULED, CHARC `20261111T183325Z`; test 1v) -- the citation trigger's top-level WHEN gets 0041's two-substitution wrap (edit 0).** **Reason:** the brief's section 1 T1 bullet says "Every `WHEN NOT (...)` arm is `WHEN NOT COALESCE(..., 0)`", and F3 says "a NULL anywhere in it must ABORT". No kind-1 outcome changes, because every top-level conjunct is `EXISTS` or `COALESCE`.
- **E3 (RULED REFUSE, CHARC `20261111T183325Z`) -- a window row with two or more narrow matches REFUSES the correction and is not passed over.** The ruled text is "the newest ... row ... whose as-of narrow matcher ... returns exactly one match". Read literally, it would pass over a multi-match row and derive an OLDER fire past a NEWER one. The plan encodes the fail-safe refusal. The case is unreachable on today's registry, because a watch row reaches H2 alone since D84 and H3 is closed. CHARC to confirm or reverse at the plan-stage read.
- **E4 (RULED, RD `20261111T183327Z`: four lines, the corrections join first) -- the H2 partition (section 0.2) cannot be expressed by the backlink alone.** RD asked to be told if so, and is.

## Banked / follow-on dispositions (RULED)

- P11, the LQDA candidate night post-dating the entry: BANKED. Owner CHARC; a register row lands at the arc's close, with the charter compression.
- F7-B, the CLI chooser: BANKED. Owner CHARC; trigger: an operator CLI entry mis-stamp.
- D86's verbatim-ticker clause stays BANKED on the D86 row (no test in this arc shows it bites).
- The H2 read rule, now FOUR lines (E4): owner RD. It lands in the watch-standard at the merge as docs-only text, read from section 0.2.
- The H2 classifier and its four-row test: BANKED to the FIRST reader change that implements the partition. RD owns the semantics and CHARC the form, and trade 29 post-correction is the line-1 row (CHARC `20261111T183404Z`).
- An H2-labelled trade with `candidate_id IS NULL` meets none of the four lines. NON-BLOCKING, and BANKED to RD together with the H2 classifier (the orchestrator routes it). It is out of this arc, like the classifier.

## Round 0 -- the census (as routed at `bafddb6a`; superseded where the fold record says so)

### Live-shape facts (read `mode=ro`, `file:...swing.db?mode=ro`, 2026-11-11)

- `schema_version` = 41.
- Trade 29: `SG`, `trade_origin=pipeline_watch_manual`, `entry_intent=hypothesis_test_by_design`, `hypothesis_label='Broad-watch baseline (watch); failed: proximity_20ma, tightness'`, `candidate_id=15980`, `state=managing`, `entry_date=2026-11-06`, `entry_price=11.95`. One entry fill: id 60, `2026-11-06T16:00:00`, qty 11.0, price 11.95, `fill_origin=schwab_auto_then_operator_corrected`, envelope present; `fill_envelope_identity` id 21 `canonical`, broker order `1008560562620`. No latch link for SG. No `entry_intent_attestations` row for trade 29.
- Candidate 15901: eval 193, `watch`, close 11.80; 18 criteria, every one `pass` except `proximity_20ma` = `fail`. Candidate 15980: eval 194, `watch`, close 11.55; `proximity_20ma` + `tightness` `fail`.
- Eval 193: `run_ts 2026-11-04T17:30:04`, `data_asof 2026-11-04`, `action_session 2026-11-05`; pipeline run 207 complete, finished `2026-11-04T17:34:17`. Eval 194: `2026-11-05T17:30:15`, `2026-11-05`, `2026-11-06`; pipeline run 208 complete, `2026-11-05T17:36:20`.
- SG has a `watch` row on every eval 179-194 and `excluded` on 195-197 (the open position). `daily_recommendations` for SG: ONLY ids 289/291/295 (evals 179/181/183), all `near_trigger`. **None on 193 or 194.**
- Registry: 1 A+ baseline (active), 2 Near-A+ defensible: extension test (active), 3 Sub-A+ VCP-not-formed (closed-target-met), 4 Capital-blocked (active), 5 Broad-watch baseline (active). History rows 1-8 (H2: 2 active->paused 5->active 6 since `2026-05-12T17:22:56.143`, recorded same instant; H3 closed by 7 on 2026-06-04; H5 active by 8 from 2026-06-09).
- `provenance_corrections`: 2 rows. id 1: trade 23, `last_word`, cand 12341 / eval 137, `derivation_rule_version 2026-08-13.3`, 3-field corrected list. id 2: trade 25, `latch_ladder_tier2`, cand 12284 / eval 136, `2026-08-26.2`. Both pre `manual_off_pipeline`/null/null, applied `pipeline_aplus`. `sqlite_sequence.seq=2`. No table REFERENCES `provenance_corrections`.
- Matcher by READ (`hypothesis.py:252-390`): 15901's non-pass set is exactly `{proximity_20ma}` -> H2 (`_near_aplus_extension_match`); H3 not active; H1/H4 need `aplus`. Label `'Near-A+ defensible: extension test (watch); failed: proximity_20ma'` = the brief's. 15980's set `{proximity_20ma, tightness}` -> no narrow match -> baseline (opt-in) -> exactly trade 29's label. The brief's two labels are verified.
- Origins live: manual_off_pipeline 5, pipeline_aplus 5, pipeline_watch_hyp_recs 10, pipeline_watch_manual 9.

### Premises -- verified, corrected, or open

| # | Brief claim | The code / DB | Disposition |
|---|---|---|---|
| P1 | The CHECKs are 0036 `:476-500`; three triggers `:563/:646/:708` | Live HEAD is 0039's REBUILD (table + citation graph + delete + `trg_pc_no_replace`) and 0041's update trigger: FOUR triggers; the citation graph is 1,540 lines; an `admission_tier` discriminator (3 values) already exists | CORRECTED; the predicates the brief names exist with the same text in 0039. Encoded against 0039/0041 |
| P2 | Kind 2 keeps the citation graph | The graph REQUIRES a `today_decision` `daily_recommendations` row (and the column is NOT NULL); SG has none on 193 or 194 | CORRECTED -> F3 |
| P3 | "the evidence rule UNCHANGED" | The kind-1 rule includes the service-side LAST-WORD guard (`_assert_last_word_before_the_fill`): the cited row must be the ticker's newest row with action session <= the fill session. For trade 29 that is 15980, so citing 15901 is REFUSED as citation-shopping | CORRECTED -> F2 (the kind-2 replacement rule needs a ruling) |
| P4 | "a watch-origin H2/H4 fire relabel" | H4 matches `bucket == 'aplus'` only since D84 (`hypothesis.py:285-297`); a `watch` citation can reach H2 alone (H3 closed, H5 is the opt-in fallback) | CORRECTED; recorded as accepted limitation 3 |
| P5 | (implicit) the append-only UPDATE trigger keeps working | It compares the recommendation columns with `=`; with kind-2 NULLs the ONE permitted update (FK SET NULL on `split_into_partials`) would ABORT (NULL -> COALESCE 0 -> fires) | NEW plan item T1.4.3 (`IS`) + test 1g |
| P6 | `record_entry` resolves `candidate_id` from the latest run | Only when `req.candidate_id is None` (`entry.py:2016, 2167-2188`); a supplied id is persisted on the non-latched path; latched overrides | VERIFIED-with-nuance: T2 needs NO `entry.py` change |
| P7 | T3 three callers | AST sites: `attribution.py:19`, `hypothesis_prefill.py:73`, `watchlist.py:40`; pinned EXACTLY three by `tests/integration/test_include_baseline_inventory_guard.py` (a governance tripwire) | VERIFIED; T2 must add NO site (encoded) |
| P8 | the two labels | verified by read of the matcher + live criteria | VERIFIED |
| P9 | "sandbox short-circuit in the inner function" (T1 CLI) | `cohort_provenance_correction.py` has NO sandbox branch (grep `sandbox`/`environment`: zero hits); nothing here writes a Schwab-derived row | CORRECTED -> F8 |
| P10 | trade 29's fill is admissible on the no-latch tier | fill 60's envelope is `canonical` in FEI, order `1008560562620`, no link | VERIFIED |
| P11 | (found) | Trade 21 LQDA: candidate night 2026-08-10 POST-DATES its entry 2026-08-07 -- the latest-run resolution at RECORD time | BANKED (not this arc; same #30 family) |
| P12 | (found) the 0039 rebuild is the template | 0039's bare `ALTER TABLE ... RENAME` FAILS at v41: `trg_eia_audit_trail` (0040, created after 0039) references `provenance_corrections`; MEASURED on SQLite 3.50.4: legacy_alter_table=0 -> `error in trigger ...: no such table`; =1 -> OK | NEW plan item (0040's PRAGMA idiom) + test 1j |
| P13 | Lock: `swing/data` carve-out = migration 0042, `models.py`, the corrections repo | Every migration also edits `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION` + a `BackupGateSpec` row + the expected-table floor) | ASK: confirm `db.py`'s version/gate lines are inside "migration 0042" |
| P14 | derivation version | The derivation closure (`DERIVATION_RULE_DEPENDENCIES`, sha256-pinned) lists the A+ rules only (`_aplus_baseline_match`, `_capital_blocked_match`), NOT the watch rules kind 2 depends on | NEW plan item F9 |
| P15 | 37 `candidate_id` consumer files | `grep -rlw candidate_id swing --include=*.py` = 36; the 37th not located (method stated in the plan's table) | OPEN-minor; the table covers all 36 + `research/` |

KEPT text (the census of what the plan carries forward, mechanic + surface): the backup-gate clause (mechanic: the shared `_run_pre_migration_gate` body, `current_version == spec.pre_version AND target >= pre+1`, read in `db.py`); `trg_pc_no_replace` + delete trigger verbatim (mechanic: BEFORE INSERT on trade_id/id, read in live DDL); the four fill-side operand block and the persist-canonical clause apply to kind 2 unchanged (mechanic: they bind the entry fill, which kind 2 cites identically; surface: live DDL); `update_cohort_provenance` reused (mechanic: three-column UPDATE, origin validated against `TRADE_ORIGINS`, read `repos/trades.py:1144`); the service writes the trade BEFORE the audit row (read `_correct_cohort_provenance_inner`), which is what lets trigger edit 2 bind the applied values to the trade.

### The ruling packet (one packet; every fork with BOTH branches executable)

**F0 (process, orchestrator) -- the plan-review tier.** The dispatch says Reviewer A on the plan at `strong` (banner `gpt-6.1-sol / high`); recipe section 3, plan-stage rule 5: "PLAN ROUNDS RUN AT THE `fast` TIER. NO EXCEPTION ... a `strong` banner on a plan round is a mis-tiered round and is reported." The recipe says a true conflict STOPS and asks. A: run `strong` as dispatched (the orchestrator's written override, recorded here). B: run `fast` (`gpt-6-luna / medium`) per the recipe. Also the cap: rule 4 caps the plan loop at three counted rounds + a self-sweep; the dispatch says "to convergence". **Recommend:** the orchestrator states which governs; no review round runs until it does.

**F1 (CHARC) -- the discriminator.** The brief asks for a `correction_kind` column; the table already has `admission_tier` (P1).
- A (encoded): `correction_kind` IN (`fill_unset_provenance`, `watch_fire_relabel`) + `admission_tier` widened by `last_fire` + a coupling CHECK (kind 1 <-> the three old tiers; kind 2 <-> `last_fire`). Two orthogonal axes (WHAT is corrected / HOW the citation was admitted); two mirror families, both in the drift test.
- B: no new column; `admission_tier` widened by `watch_fire_relabel`, every kind-2 arm keyed on it. One mirror family, but the column then names two things (an admission route AND a correction shape).
- Recommend A: it is the brief's form, and `last_word` would be a false label on a kind-2 row.

**F2 (RD + CHARC) -- the kind-2 evidence rule that replaces the last-word guard (P3).**
- A: OPERATOR-ASSERTED. Any `watch` row of the ticker with action session <= the fill session, within the 5-row window, whose as-of narrow matcher returns exactly one match; tier `operator_asserted`. The operator chooses the night.
- B (encoded): LAST FIRE. The cited row must be the NEWEST row (the last-word ranking, every competitor validated) within the 5-row window whose as-of narrow matcher (`include_baseline=False`) returns exactly one match; the operator's id is a CONFIRMATION (the `--to` idiom); tier `last_fire`. For trade 29 it derives 15901. Citation-shopping is closed by mechanism (two H2 fires carry the same label by construction -- H2 is the exact set `{proximity_20ma}` -- so the choice between them costs nothing).
- Recommend B. Note the asymmetry it creates with T2 (forward path operator-asserted, retro correction derived): RD rules whether that is intended.

**F3 (CHARC) -- the recommendation citation on kind 2 (P2).** A (encoded): the three recommendation columns become nullable; kind 2 -> all NULL, kind 1 -> all NOT NULL (CHECK). B: kind 2 cites a `near_trigger` row when one exists for the cited run -- impossible for SG (none on 193), so B cannot record the case this arc exists for. Recommend A.

**F4 (CHARC) -- `corrected_fields_json` on kind 2.** A (encoded): exactly `["trades.hypothesis_label", "trades.candidate_id"]`; pre/applied envelopes still carry all three keys (origin equal both sides). B: the same three-field list as kind 1 (origin listed as "corrected" though unchanged -- `trg_eia_audit_trail` would then refuse a later attestation citing `trade_origin` for a field no correction touched). Recommend A.

**F5 (CHARC) -- kind-2 eligibility.** A (encoded): `pipeline_watch_manual`; label and candidate non-null; the current `candidate_id` IS the ticker's last-word row before the fill (the batch-night signature, existing ranking reused); not latched; no prior correction. B: add "the current label equals the as-of prefill label of the current candidate" (proves the label is a framework stamp, not operator-typed) -- costs a FOURTH `include_baseline=True` call site, which `test_include_baseline_inventory_guard` forbids without a governance amendment. Recommend A.

**F6 (CHARC; RD CC) -- T2's offered nights.** A (encoded): the last N rows in COMPLETE runs, restricted to the bucket of the latest complete run's row (the row `derive_trade_origin` reads, `origin.py`, outside the carve-out), so origin, bucket and label agree by construction. B: any bucket -- then an earlier `aplus` night under a latest `watch` night persists an `aplus` `candidate_id` + H1 label beside `pipeline_watch_manual`, the "impossible cohort assignment" 0036's R4 Major 2 comment names. Recommend A.

**F7 (CHARC) -- the CLI `swing trade entry`.** A (encoded): behaviour unchanged, the prefill line names its night; a CLI chooser BANKED. B: add `--decision-candidate <id>` with the same validation as T2.3. Recommend A (the ruling names the form; the CLI is the operator's fallback path).

**F8 (CHARC) -- sandbox short-circuit (P9).** A (encoded): none, mirroring kind 1. B: an inner `environment != 'production'` branch returning `correction_id=None`. Recommend A.

**F9 (CHARC) -- `derivation_rule_version` (P14).** A (encoded): one closure, extended with the watch rules; the digest moves; `DERIVATION_RULE_HISTORY` gains one entry; both kinds write the head; live rows keep theirs. B: a separate kind-2 closure + history. Recommend A.

**N (RD may adjust):** `WATCH_FIRE_WINDOW_ROWS = 5`, shared by T2's offer and T1's last-fire walk. Reason: one trading week of nightly briefings covers a buy-stop placed off a briefing and filled within the week (the near_trigger rows are GTC buy-stops); SG needed 2; the window is also the bound that stops the last-fire walk from reaching a stale fire. Not measurable from data: no other trade's decision night is recorded.

## Round table

Depth is filled by the orchestrator from `scripts/cell_depth.py --agent <id>`; a cell never self-estimates it.

| Round | Kind | Tier / banner | `^ERROR` | footer | verdict token | repo reads (6th check; `^exec$` count, 0 = WEAK) | crit/maj/min (reviewer) | task-bearing | NEW / REOPENED | reverts | tokens used | depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | premise + fork census, NO Codex (`bafddb6a`) | -- | -- | -- | -- | -- | -- | 10 forks routed (F0-F9) | -- | -- | 0 | |
| 0-fold | rulings folded, NO Codex (continuation cell, `08ee3b57`) | -- | -- | -- | -- | -- | -- | 0 (E1-E4 declared; E3 unsettled) | -- | -- | 0 | 255K (orchestrator, at the fold-ruling relay) |
| 0-fold-2 | fold rulings folded (E1-E3, R1, E4, the classifier lock), NO Codex | -- | -- | -- | -- | -- | -- | 0 | -- | -- | 0 | |
| 1 | Codex plan review: a stdin bundle (plan `51a323e3`, the ledger cut, the brief), cwd = worktree, read-only | `fast`: `gpt-6-luna` / `medium` (equal to the profile file) | 0 | present | `NEW_CRITICAL_MAJOR_FOUND` (x2, one distinct; the other token 0) | 0, WEAK (counts: the five assertions pass) | 0 / 2 / 0 | 2 (R1-01 accepted; R1-02 contested, so it counts fail-safe) | 2 NEW / 0 REOPENED | 0 | 37,032 | 313K (orchestrator, at the round-1 gate) |
| 2 | Codex plan review: a stdin bundle (plan at `04ee3eab`, the ledger cut, the brief) plus the REQUIRED READS prompt section; cwd = worktree, read-only | `fast`: `gpt-6-luna` / `medium` (equal to the profile file) | 0 | present | `NEW_CRITICAL_MAJOR_FOUND` (x2, one distinct; the other token 0) | 4 (not weak) | 0 / 1 / 0 | 1 (R2-01 accepted) | 1 NEW / 0 REOPENED | 0 | 71,825 | 331K (orchestrator, at the round-2 gate) |
| 3 | Codex plan review, the FINAL counted round: a stdin bundle (plan at `e2cb6ac2`, the ledger cut, the brief) plus REQUIRED READS; cwd = worktree, read-only | `fast`: `gpt-6-luna` / `medium` (equal to the profile file) | 0 | present | `NEW_CRITICAL_MAJOR_FOUND` (x2, one distinct; the other token 0) | 8 (not weak) | 0 / 1 / 0 | 1 (R3-01 accepted, with my fix in place of the reviewer's) | 1 NEW / 0 REOPENED | 0 | 100,988 | |
| SS | self-sweep, UNCOUNTED, no Codex (grep plus targeted reads) | -- | -- | -- | -- | -- | -- | 1 (SS-1, a residue of R2-01) | -- | 0 | 0 | |

## Round 1

Evidence, copied the moment the assertions passed, at `C:/Users/rwsmy/swing-data/review-transcripts/sg-label/`: `.codex-review-r1.txt` (127,656 bytes), `.codex-prompt-r1.md` (122,941 bytes), and `.copowers-findings.md` (7,435 bytes: the verbatim response plus this adjudication). Wall time was 45 s, and the reviewer made zero repo reads. The plan fixes landed in `f434a276`. That commit message also claims "ledger row", but the ledger write FAILED there (a quoting error in my own script), so the row and this section land in the next commit. The message defect is RECORDED here and not rewritten.

- **R1-01. Reviewer: major, task-bearing. Mine: minor, TASK-BEARING (it changes test 1i's assertion). ACCEPTED, with the premise corrected.**
  - The reviewer's mechanism is wrong. It says the table CHECKs "can reject the malformed value before the trigger". A BEFORE INSERT trigger runs BEFORE the row's CHECKs (SQLite semantics; the plan's T1.4.1 note and 22A-R3-12 rest on this), so the trigger fires first.
  - The remedy stands anyway. 1i said "`RAISE(ABORT)`/CHECK", which would pass on either path.
  - The fix: 1i now asserts the citation trigger's OWN kind-2 message, with no CHECK message and no `OperationalError`. It covers both JSON columns. A guard-removed variant raises `OperationalError`, which proves the `json_valid` guard is load-bearing.
- **R1-02. Reviewer: major, task-bearing. Mine: the premise is prevented by the service, so not a major; the classification is CONTESTED, which counts task-bearing (fail-safe). PARTLY ACCEPTED.**
  - The premise is "the registry changes between the walk and the label derivation". The service's own transaction prevents it. The outer function owns `BEGIN IMMEDIATE` (T1.6; the shape of `correct_cohort_provenance`), so no other writer can change `hypothesis_registry` or `hypothesis_status_history` between two reads of the same transaction.
  - The mechanism is SQLite's lock, not a census of writers. `BEGIN IMMEDIATE` takes the RESERVED lock at BEGIN, so no other connection can COMMIT a write until this transaction ends.
  - Every read inside the transaction therefore sees one database state. This holds whoever the writer is, which is why no writer enumeration is offered or needed.
  - What I took: steps 7 and 8 read through ONE function for the SAME row in the SAME transaction, and the plan now says so. Step 8 also asserts that `keys.hypothesis_id` equals the walk's match, refusing on inequality.
  - What I declined: the proposed test that changes the registry mid-transaction. It can only be built by monkeypatching the function under test, which would be a vacuous test of an unreachable state.
- **Observation for the orchestrator (instrument, not a finding).** The round made ZERO repo reads: 37,032 tokens in 45 s. Both findings cite a `file:line` the reviewer never opened; R1-02's citation, `cohort_provenance_correction.py:807-840`, is the snapshot function, which is unrelated to its claim. The round passes all five mechanical assertions, so it COUNTS. For round 2 the prompt REQUIRES opening named files before findings are written. That is a prompt-design change only, with no change to the tier or the rules.

## Round 2

Evidence, copied the moment the assertions passed, at `C:/Users/rwsmy/swing-data/review-transcripts/sg-label/`: `.codex-review-r2.txt` (340,986 bytes), `.codex-prompt-r2.md` (125,110 bytes; corrected from 125,109, which counted characters instead of bytes), and `.copowers-findings.md` (10852 bytes, rounds 1-2). Wall time was 90 s.

- **Assertions.**
  - The banner reads `gpt-6-luna` / `medium`, equal to the profile file.
  - `^ERROR` = 0.
  - `^tokens used` = 1 (71,825).
  - `^NEW_CRITICAL_MAJOR_FOUND` = 2 (the final message is printed twice) and `^NO_NEW_CRITICAL_MAJOR` = 0.
  - The process exited 0 and the transcript is non-empty (340,986 bytes).
  - The repo-reads check passes with **4** batched shell reads, which is NOT weak. They covered 0039 (the DDL, CHECKs and triggers), 0041, `cohort_provenance_correction.py` (the last-word guard, the derivation, the authorize step, the inner writer), and the T2 route, view model, entry and origin surfaces.
  - No read touched the ledger file, a `.codex`/`.copowers` file, `swing-data`, a database, or git (the exec command lines were grepped).
- **R2-01. Reviewer: major, task-bearing. Mine: major, TASK-BEARING. ACCEPTED.**
  - T2.3 validated the chosen id against the CLIENT-SUBMITTED offered set. An altered form could therefore name a same-ticker row in another bucket, or one outside the window. That would defeat F6's origin/bucket/label agreement, which is the server-stamp gotcha.
  - The fix: the POST re-derives the eligible set through the same `list_decision_nights` that rendered the form. The chosen id must be in it; otherwise the POST returns 400, clears the anchor, and asks for a re-render. The label is the server-derived one, and the submitted label is kept only as the operator's claim for the consistency gate.
  - Eligibility is judged at POST because `record_entry` derives the origin at POST.
  - The fix keeps the TOCTOU gotcha intact: the chosen row is validated as the exact anchor, never re-picked.
  - Test 2d gains the two forged-anchor cases (another bucket; outside the window) and the window-shift case.

## Round 3 and the self-sweep

Evidence, copied the moment the assertions passed, at `C:/Users/rwsmy/swing-data/review-transcripts/sg-label/`: `.codex-review-r3.txt` (641,993 bytes), `.codex-prompt-r3.md` (126783 bytes), and `.copowers-findings.md` (15149 bytes, rounds 1-3 plus the self-sweep). Wall time was 90 s.

Loop status: the three counted rounds are spent and the self-sweep is done. Round 3 was NOT clean (one task-bearing finding, fixed), so the loop ENDED BY THE CAP, not by a clean verdict. A fourth counted round needs the orchestrator's written authorization naming a task-bearing finding; none is open. Total counted spend: 209,845 tokens (37,032 + 71,825 + 100,988).

- **Assertions.**
  - The banner reads `gpt-6-luna` / `medium`, equal to the profile file.
  - `^ERROR` = 0.
  - `^tokens used` = 1 (100,988).
  - `^NEW_CRITICAL_MAJOR_FOUND` = 2 (the final message is printed twice) and `^NO_NEW_CRITICAL_MAJOR` = 0.
  - The process exited 0 and the transcript is non-empty (641,993 bytes).
  - The repo-reads check passes with **8** shell reads, which is NOT weak. None touched the ledger, a `.codex`/`.copowers` file, `swing-data`, a database, or git.
- **R3-01. Reviewer: major, task-bearing. Mine: major, TASK-BEARING. ACCEPTED on the defect; its proposed fix is DECLINED.**
  - Re-read at the code: `_rerender_entry_form_with_error` (`routes/trades.py:505-545`) rebuilds the view model, and it overrides the anchor ONLY when `submitted_schwab_source_value_json is not None` (`:528`).
  - The entry POST's existing `_reject_anchor` (`:1246-1261`) passes `None` BY DESIGN. Its comment at `:1255-1257` reads "use the rebuilt VM's fresh auto-fill anchor".
  - So test 4h's claim that the hidden anchor is EMPTY was false whenever the fresh fetch repopulates it. The reviewer is right about that.
  - The reviewer's fix was to force an empty string. That would change the established semantics of every entry rung and diverge from the four existing rungs, so I declined it.
  - The fix taken: T4.3 calls the EXISTING entry `_reject_anchor` with the new text, so all entry rungs share one rejection path. "Cleared" is defined as "the rejected string is never replayed". Test 4h asserts that the rejected string is absent from the page under two fresh-fetch stubs: a different populated envelope, which the input then carries, and an empty fetch, which leaves `value=""`.

### Self-sweep (uncounted; SS-N ids; no effect on convergence)

Method: grep and targeted reads, not a reread end to end.
- Superseded-idiom greps found zero residues each: `--to`, `three edits`, `THREE clauses`, `1,540`, `` RAISE(ABORT)`/CHECK ``, `ledger flags`, `UNSETTLED`, `disclosed`, `CALLED UNCHANGED`, `hidden anchor is EMPTY`, `edits 1-3`, an untagged or unruled `[F#]`, `recommended`, `DRAFT`, `H2/H4`.
- A script cross-checked the test ids: every referenced id is defined. The defined set is 1a-1r, 1u, 1v, 2a-2k and 4a-4h. 1s and 1t were never defined and are not referenced.
- The names are consistent: `_as_of_narrow_matches`, `PROVENANCE_WATCH_FIRE_ENTRY_INTENT`, `WATCH_FIRE_WINDOW_ROWS`, `list_decision_nights`, `label_for_candidate`, `_ENTRY_RAW_ANCHOR_UNREADABLE_TEXT`, `correct_watch_fire_label`, `preview_watch_fire_label`.
- Every section-0 cross-reference resolves.
- The R1-02 equality check reads a real field: `_FireKeys.hypothesis_id` exists (`cohort_provenance_correction.py:1438`).

- **SS-1 (task-bearing; a residue of the R2-01 fix).** R2-01 moved `list_decision_nights` onto the POST path. On a raced cohort read, that function raises `CohortReadRacedError`. The GET degrades on it, but the POST has no stated behaviour. FIXED: the POST refuses with 400, clears the anchor and asks for a re-render; it never persists and never returns 500. Test 2d gains the raced-read case.

## Executing -- handoff 1 (seat roll; written for a FRESH executing cell)

**Head at this handoff:** `8405528b` on branch `sg-label` (worktree `.worktrees/sg-label`). Base of the executing diff for Reviewer A: `b120a6eb` (the plan's final plan-loop commit). Work order followed is the PLAN's (T3, T4, T1, T2), not the order of the dispatch's yield list.

**Commits so far (shipped order):**
| SHA | Item |
|---|---|
| `e8a6ff1c` | Step 0: CHARC's plan-stage amendment (`20261111T185452Z`) folded into T1.6 step 7 (validate AS THE WALK VISITS, newest first; STOP at the derived fire; rows older than it are not read) + test 1n's older/newer-unreadable pair. Docs-only pathspec commit. |
| `063235a1` | T3 (D103): `hypothesis.py` baseline comment points at the AST census test; no test (brief). |
| `7a2ed3ff` | T4.1 (D86): shape gate in `exit.py:_normalize_trade_event_date_to_iso`. |
| `8405528b` | T4.2 (D86): finite-price refusal at `record_exit` (`check_exit_preconditions`) and `record_entry`. |

**RED/GREEN evidence (T4.1-T4.2), file `tests/trades/test_d86_input_domain.py`:** on the pre-change tree 11 failed / 11 passed (RED: 4a compact, 4c week, 4d compact-T on exit; 4b/4c on entry; 4e exit `inf`; 4f entry `inf`/`-inf`/`nan`/`0`/`-1` -- the old code wrote `inf` rows, hit an `IntegrityError` at the NOT NULL for `nan`, and gave the stop-comparison text for `0`/`-1`; GREEN keepers: 4g canonical date, T-form, microsecond and `HH:MM`, tz-aware and calendar-invalid refusals, 4d on entry which the old `"T" in` guard already refused). After T4.1: 6 failed (the price tests only). After T4.2: 22 passed. Related suites (`test_exit`, `test_entry`, `test_d79_exit_preconditions`, `test_22f_exit_price_guard`, `test_22f_exit_post`, `test_22f_cli_typed_refusals`, `test_22f_{entry,exit}_auto_fill_guards`) 146 passed at `8405528b`. `ruff check swing/` clean. The FULL fast suite has NOT been run yet.

**Deviations from the plan's letter, each with its reason (for the merge gate):**
1. T4.1 regexes use ASCII `[0-9]` and `re.fullmatch`, not `\d` and `^...$`: `\d` matches every Unicode digit and `$` matches before a trailing newline.
2. T4.1 keeps two pre-existing refusal texts instead of one generic message: a canonical body carrying `Z`/`+hh:mm` is refused by the existing "timezone-aware" text (via `_CANONICAL_DATETIME_TZ_RE`, ahead of the shape gate), and a malformed T-form keeps "contains 'T' but is not a valid ISO datetime" with the canonical form appended. Reason: `test_exit.py::test_record_exit_rejects_timezone_aware_iso_datetime` and `::test_record_exit_rejects_malformed_exit_date_with_t` pin those texts, and they are the more informative messages. The post-parse tz branch stays as the belt (now unreachable). Date-only non-canonical input gets the plan's text verbatim.
3. T4.2 exit side is two checks, not one `isfinite and > 0` conjunction: the old `> 0` check runs first with its old text, then `math.isfinite` with "exit price must be a finite number > 0". Reason: D79's `test_t7a_iv_each_refusal_keeps_its_existing_text` pins the `0.0`/`nan` texts exactly. The refused set is identical to the plan's conjunction. Entry side is the plan's single conjunction and text.
4. `tests/trades/test_22f_exit_price_guard.py::test_A6f_*` (a BOUND pin whose docstring said it would be inverted) is inverted and renamed `test_A6f_bound_pin_inverted_by_d86_inf_price_is_refused`; the module docstring sentence updated.

**What remains (all of it is the successor's):**
- **T4.3** (plan T4.3, test 4h, file `tests/web/test_routes/test_d86_entry_raw_rung.py`): extract `_raw_anchor_is_refused(raw)` from `swing/web/routes/trades.py:_exit_raw_anchor_is_refused` (keep the exit name as an alias) and add the rung BEFORE the entry POST's `json.loads` (~`:1215`), routed to the EXISTING `_reject_anchor(_ENTRY_RAW_ANCHOR_UNREADABLE_TEXT)` with every `submitted_*` anchor `None`. Not started. Re-ground the line numbers (they drift).
- **T1** (plan T1.0-T1.7, tests 1a-1v + 1q, three commits per the plan; schema manifest regenerated in the migration commit; the amended step 7 walk). Not started. No mirror-closure reads done yet -- the closure list is entirely open (the plan's "Mirror closure" paragraph is the site list; grep each member separately).
- **T2** (plan T2.1-T2.4, tests 2a-2k). Not started.
- Then the gates: full fast suite to `C:\Users\rwsmy\swing-data\review-transcripts\sg-label\exec-branch-suite.txt` (foreground), ruff, migrate-twice, drift test both kinds, Reviewer A `strong` to convergence (transcripts under `...\sg-label\exec\`, round ledger in the worktree's `.copowers-findings.md` with a depth column the orchestrator fills).

**Open questions:** none. The scratch copy of the full D86 test file used to split the T4.1/T4.2 commits sits in the departing cell's session scratchpad and is not needed (the committed file is complete).

## Executing -- handoff 2 (seat roll; written for a FRESH executing cell)

**Head at this handoff:** `b70ef5e0` plus this ledger commit, on branch `sg-label`. NOTHING new under `swing/` or `tests/` is committed. The worktree is clean. Base of the executing diff for Reviewer A is still `b120a6eb`.

**Why there is no T4.3 or T1.1 commit.** T4.3 hit a premise conflict that needs a ruling (fork FX-1 below). T1.1 is written and its own 34 tests are green, but the schema bump fans out to 171 failures and 10 errors in `tests/data` alone (the full suite has not been run). This cell's context ran long before that fan-out could be closed into a green commit. The work is preserved OUTSIDE the worktree, not committed red.

**Preserved work (durable path `C:\Users\rwsmy\swing-data\review-transcripts\sg-label\exec\`):**

| File | What it is |
|---|---|
| `t1.1-wip.patch` (238,353 bytes) | The whole T1.1 working tree vs `b70ef5e0`, made with `git diff --cached --binary`. Verified to apply: `git apply --check` passed on the clean tree. Apply it with `git apply <path>` from the worktree root. |
| `t1.1-wip.stat.txt` | Its stat: 8 files, +3771/-21. |
| `t1.1-wip-tests-data-run.txt` | The `tests/data` run with the patch applied (`-n 8`): 171 failed, 3469 passed, 1 skipped, 10 errors in 298.92 s. |
| `gen0042.py`, `header0042.sql` | The generator that wrote migration 0042 from the 0039 and 0041 source statements. Every edit is an exact substring replacement, asserted to occur exactly once. To regenerate: `python gen0042.py <worktree> <out.sql> header0042.sql`. |
| `t43-parked-route.diff`, `t43-parked-test_d86_entry_raw_rung.py` | The parked T4.3 implementation and test 4h (see FX-1). |

**What the T1.1 patch contains (each item read and run, not inferred):**
- `swing/data/migrations/0042_provenance_corrections_watch_fire_relabel.sql`: the rebuild, 2,504 lines. The header carries the reversibility text, the edits list, the seven re-created objects, the gate row, the D51 expectation and the reverse rule. The table edits are T1.1 and T1.3. The update trigger is 0041's text with three `IS` and the kind line. The citation trigger is 0039's text with edits 0-3 and the RAISE sentence. The RENAME uses 0040's `legacy_alter_table` bracket.
- `swing/data/db.py`: `EXPECTED_SCHEMA_VERSION = 42`, `PHASE22_SG_LABEL_PRE_MIGRATION_EXPECTED_TABLES` (the v41 floor, equal to v40's because 0041 created no table), the gate row `BackupGateSpec(41, "sg-label", ..., "_sg_label_backup_gate", "pre-sg-label")`, and the wrapper binding `_sg_label_backup_gate = _bind_gate_wrapper(41)`.
- `swing/data/models.py`: the T1.5 constants. `PROVENANCE_ADMISSION_TIERS` now has four values. The new constants are `PROVENANCE_CORRECTION_KIND_*`, `PROVENANCE_CORRECTION_KINDS`, `PROVENANCE_ADMISSION_TIERS_BY_KIND`, `PROVENANCE_WATCH_FIRE_CORRECTED_FIELDS`, `PROVENANCE_WATCH_FIRE_ORIGIN` and `PROVENANCE_WATCH_FIRE_ENTRY_INTENT`, the last asserted at import to be in `ENTRY_INTENTS_ASSERTABLE`. `ProvenanceCorrection` has the three recommendation fields `| None` and `correction_kind` as the last defaulted field. Its `__post_init__` checks kind membership, the tier coupling, the recommendation presence by kind, the corrected fields by kind, `_require_value_envelope(kind=...)` with the kind-2 rules, the snapshot bucket by kind, and the recommendation snapshot only for kind 1 (split into `_validate_recommendation_snapshot` and `_validate_remaining_snapshots`).
- `swing/data/repos/provenance_corrections.py`: `"correction_kind"` appended to `_COLUMNS`.
- `tests/data/schema_manifest_head.tsv` regenerated. Its diff is EXACTLY four changed line pairs (`# schema_version`, `table provenance_corrections`, the two changed triggers) and ZERO deletions, which matches the D51 expectation in the header.
- `tests/data/test_backup_gate_table.py`: `POST_BASE_ROSTER` gains the 41 row (test 1l).
- `tests/trades/_cohort_provenance_fixtures.py`: `build_sg_case` and `watch_fire_payload`. The SG fixture is seeded from the LIVE shape, read `mode=ro` 2026-11-11:
  - evals 192/193/194 and pipelines 206/207/208 with their live ids and stamps;
  - candidates 15811/15901/15980 with live columns, and all 18 live `candidate_criteria` rows each, VERBATIM in rowid order;
  - trade 29 and fill 60 with live values and the live envelope, plus the FEI row written through the production `record_identity`;
  - the live registry: H3 `closed-target-met`, and `hypothesis_status_history` rows 1-8 verbatim, written through the 22-I guard seam (kind 4). Row 7's 233-char `change_reason` is ABBREVIATED; it is not derivation-bearing.
  - `watch_fire_payload` builds the kind-2 row from `derive_cohort_keys_for_fire` and the production snapshot helpers. On the fixture it derives label `'Near-A+ defensible: extension test (watch); failed: proximity_20ma'`, hypothesis 2, history row 6, pipeline 207, `cited_run_ts_utc 2026-11-05T03:30:04`, upper `2026-11-05T03:34:17`. That is the brief's exact label, from the AS-OF registry.
- `tests/data/test_migration_0042_watch_fire_relabel.py`: 34 tests, all green with the patch applied. They cover 1b-1m and 1v, 1f over three verbs plus ON CONFLICT, 1g's two halves plus both siblings, 1i guarded and unguarded, and the fixture check.
  - RED evidence: before any implementation the module failed collection with `ImportError: PROVENANCE_ADMISSION_TIERS_BY_KIND`.
  - Three test defects were fixed on the way to green. (a) The HEAD-statement helper cannot find a table created under a scratch name, so the test reads 0042's statement itself. (b) The bare-form sibling needs the FK-null branch TRUE in the same statement, as in 0041's census. (c) The drift test's kind-literal scan is now scoped to the two `CASE NEW.correction_kind` blocks; a whole-trigger scan also caught `WHEN 'latch_ladder'`.

**The fan-out the successor must close before the T1.1 commit, by class** (from `t1.1-wip-tests-data-run.txt`; each class is SAMPLED, not read failure by failure):
1. **A HEAD payload into an OLD-version world.** This is the dominant class: about 100 parametrized `test_migration_0041_pc_update.py` cases plus `test_migration_0041_fi6_pins.py`, `test_migration_0041_census.py::test_f2[provenance_corrections]`, `test_migration_0040_*` and `test_migration_0039_*` (a2_12..a2_17, a2_31). Error: `table provenance_corrections has no column named correction_kind`. Builders that read the HEAD row through `PRAGMA table_info`/`SELECT *` (e.g. `tests/_tier2_world_22a2.py:base_last_word_payload`) now carry `correction_kind`, which a v40/v41 world lacks. Fix the BUILDERS, not each test, by dropping `correction_kind` when the target version is below 42. 0039's SS-1 is the precedent for planting a HEAD row's older-column subset.
2. **HEAD-tracking version mirrors** `== 41` (about 35 `test_expected_schema_version_is_head` / `_row_is_head` / `_advances_schema_version` tests). Move them to 42. Do NOT rename tests (the version-mirror gotcha: naming is a separate change).
3. **0039 HEAD-pinned DDL tests** (`a2_10`, `a2_11`, `a2_23`, `a2_24`, `a2_25`, `test_the_head_citation_trigger_keeps_every_fei_consumer_marked`). Re-point them to `target_version=39` where they are about 0039's own text. Where they are about HEAD (`a2_23`'s `len == 3`, `a2_24`'s `_COLUMNS[-1]`, `a2_25`'s tier regex and `assert path == M0039`), update them per the plan's 1m row.
4. **Census and inventory tests that enumerate literal sites**: `test_entry_intent_drift.py::test_each_member_greps_separately_b22_33[hypothesis_test_by_design]` (0042 and models.py are new sites), `test_22a_task3_epoch_reader.py::test_the_epoch_is_read_in_exactly_one_place`, `test_22f_inv_model_roster.py::test_raising_validator_set_equals_roster_union_unreached` (the new `ProvenanceCorrection` raises), and `test_no_schema_change_v3.py` (a pinned migration roster).
5. **`test_22f_d39_apply_migration.py`, 10 ERRORS at setup**: NOT yet diagnosed.
6. `test_migration_0041_header.py::test_the_22i_gate_row_is_the_canonical_clause`, `test_phase13_t3_sb1_prerequisite.py::test_sqlite_connect_smoke` and `test_v20_migration.py::test_v20_migration_lands_all_tables`: not diagnosed. They are probably classes 2 and 4.

After `tests/data`, run the FULL fast suite once with the patch applied, to find the fan-out outside `tests/data` (trades, web and cli fixtures that construct `ProvenanceCorrection` or compare tier sets).

**FX-1 -- T4.3 is PARKED. It is a fork for a ruling (RD, CHARC), routed through the orchestrator.**
- **The plan's letter:** the entry POST gets the exit ladder's raw rung. Any anchor the ONE authority (`canonical_envelope_identity`) refuses gets a 400 before `json.loads`, and the rung is not gated on the claim.
- **What the code says:** RD ruled the opposite on 2026-09-01 for the entry path, and 16 tests in `tests/web/test_routes/test_22a_task10_entry_route_ext2.py` pin that ruling.
  - `test_a_malformed_order_id_refuses_the_latch_binding_not_the_entry` (seven shapes: empty, whitespace, int, float, bool, list, dict) asserts "PRE-FIX: 400 ... POST-FIX: the route decides nothing about the ENTRY, the service is reached", and the trade is recorded honest-unset.
  - `test_the_ROUTE_reaches_the_service_for_EVERY_recognised_envelope` (Codex 22A-FIX-R2-10) does the same.
  - The section comment there reads: "A malformed `schwab_order_id` REFUSES THE LATCH BINDING, never the ENTRY ... a malformed cohort key blocked a MONEY-BEARING ENTRY, which is RD's governing principle".
  - The authority refuses exactly those seven shapes, so the plan's rung RE-INTRODUCES the pre-fix 400. Measured with the rung in place: those 15 tests (seven plus eight parametrizations) plus `test_a_malformed_order_id_records_the_entry_honest_unset_case_rd` FAIL, and every other entry and anchor route test passes (259 passed).
- **The four branches, each executable from the parked files:**
  - **A.** The rung as planned. This reverses RD 2026-09-01, so it needs RD and the operator, and those 16 tests are inverted.
  - **B.** The rung only for a document the authority refuses for a reason OTHER than a malformed order or symbol VALUE: undecodable or a duplicated key. It needs a predicate that splits the authority's refusal set, i.e. a second spelling of the authority, which the ONE-authority rule forbids. Not recommended.
  - **C.** No entry rung. D86's entry half is already met, because the SERVICE refuses the LATCH BINDING on an authority-refused envelope and records the entry honest-unset. Test 4h is rewritten to pin that: a duplicate-key anchor records the trade with `trade_origin` honest-unset and a warning, and no latch citation. The ledger records why the entry ladder deliberately differs from the exit ladder.
  - **D.** The rung, but refusing the LATCH BINDING rather than the entry. That is already what the service does, so D collapses into C.
  - **Recommend C**, subject to RD.
  - A second, smaller deviation applies to any rung form. The parked implementation fires only on a document that DECODED, to keep `test_entry_post_audit_columns.py::test_c_malformed_anchor_with_claim_rejects_with_400` (its "malformed/unparseable" text) and `::test_c_malformed_anchor_without_claim_falls_back` (the bare-cURL `operator_typed` fallback) green.
  - Also, the plan's 4h says an empty fetch leaves `value=""`. The template OMITS the hidden input when there is no anchor (`trade_entry_form.html.j2:74-81`), so the parked test asserts that the input is absent.

**Mirror closure -- STARTED, NOT CLOSED (file sets by a per-member grep over `swing/`; a grep bounds the family from below, the closure needs a READ per site):**
- `PROVENANCE_ADMISSION_TIERS`: `models.py` and `latched_origin.py:44-47,103-106`. The second is a re-export, and nothing in `swing/` or `tests/` imports the tier set from `latched_origin` (grep `from swing.trades.latched_origin import` filtered for `ADMISSION_TIER`: zero hits), so the re-export is value-agnostic.
- `last_word` / `latch_ladder`: `cli.py`, `models.py`, `cohort_provenance_correction.py`, `latched_origin.py`, and `frozen_value_evidence.py` (`latch_ladder` only). **Live site for T1.3:** `cli.py:3606-3608` is `tier = getattr(view, "admission_tier", "last_word")`, then `if tier == "last_word": ... else <latch printing>`, so a `last_fire` row would print as a LATCH row. It must branch.
- `cited_daily_recommendation_id` / `cited_recommendation_action_session_date`: `cli.py:3793,3871,3887,3939-3940` (preview, result and list printing; kind 2 renders `(none: watch-fire relabel)` in T1.3), plus `models.py`, the repo (value-agnostic tuple) and the service.
- `PROVENANCE_CORRECTED_FIELDS`: `cli.py:44,3587` (`COHORT_FIELD_ORDER`), `models.py`, and the service (`COHORT_CORRECTED_FIELDS`).
- `corrected_fields_json`: also `entry_intent_assignment.py`, read as a set, which the plan names value-agnostic. That is NOT yet re-read this seat.
- `fill_unset_provenance` / `watch_fire_relabel` / `last_fire`: only `db.py` (the version comment) and `models.py` in `swing/`, plus the 0042 SQL.
- NOT yet read: the service sites the plan names (`:878`, `:1097`, `:1106`, `:2125`, `:3359-3369`, `:3405-3408`), `frozen_value_evidence.py:1305-1311/1393-1397`, `entry_intent_assignment.py:307-316`, `trg_eia_audit_trail`, and each member grepped separately in `tests/`.

**What remains, in order:** apply the patch; close the fan-out to green; commit T1.1 (pathspec, the plan's subject); T1.2 (the service and tests 1a, 1n-1p, 1r, 1u); T1.3 (the CLI and 1q); T2.1-T2.4; T4.3 per the FX-1 ruling. Then the gates (full suite to `exec-branch-suite.txt`, ruff, migrate-twice (1k already pins it), the drift test (1m already pins both kinds)) and Reviewer A `strong`.

**Deviations recorded this seat (beyond FX-1):**
5. Test 1k migrates the CADL `last_word` shape only. The tier-2 (row-2) shape is covered at v41 and v42 by 1v. Reason: the tier-2 world is built through `build_pre_barrier_world`, whose HEAD payload carries the new column (class 1 above), so a byte-equality migrate test on it needs that builder fix first.
6. Test 1d asserts the post-dating refusal twice. On the full DB, the BEFORE INSERT trigger's run-anchor leg refuses FIRST, because the frozen session differs from the run's own. A separate test runs the CHECK alone on a trigger-free scratch table, so the CHECK itself is pinned.
7. Test 1e's mutation is on the TABLE CHECK's kind-2 applied arm, in a trigger-free scratch table: the bare form ACCEPTS a row missing the label key. The trigger's kind-2 arm cannot be mutated discriminatingly, because every conjunct in it is `IS NULL` or `EXISTS`, so its COALESCE is a belt and cannot go NULL (the plan says so at T1.4.1).

## FX-1 ruling (verbatim, binding)

**Ruling seat:** RD, `20261111T201903Z`. **Courier:** the orchestrator (relayed to executing cell 3). CHARC was CC and offered no dissent.

> FX-1 = C. NO ENTRY RUNG. The 2026-09-01 ruling stands unchanged and applies to D86's shapes exactly as it applied to the malformed schwab_order_id: a malformed, duplicate-key or otherwise refused anchor REFUSES THE LABEL (the latch binding and the cohort keys), NEVER THE ENTRY. The trade is real, the fill happened at the broker, and a 400 on the entry POST leaves a real position unjournaled, which is the worse measurement outcome every time: an unrecorded trade corrupts every cohort and the cash ledger, an honest-unset one corrupts nothing. A is refused: it would be the fifth instance of the class named on 09-01 (a guard added to protect the cohort keys defaulting to blocking the entry), and it would need the operator to reverse a ruling he has not been asked to reverse. B is refused: a second spelling of the authority.
>
> 4h RESTATED -- CONFIRMED, with the discriminating shape from the 09-01 text carried over. For each D86 anchor shape (the duplicate-key anchor and the others canonical_envelope_identity refuses):
>  (i) the trade IS written (a 400 fails the test);
>  (ii) the cohort keys land honest-unset: trade_origin manual_off_pipeline, hypothesis_label NULL, candidate_id NULL (admitting the anchor and stamping keys fails the test too);
>  (iii) a warning names the malformation;
>  (iv) the rejected anchor string is never replayed on the recovery form (R3-01's fix, kept).
> The RED evidence the cell found (a duplicate-key anchor without a claim got a 200 AND was recorded WITH keys on the old code) is the defect D86 exists to close; (ii) is what closes it.
>
> ONE CONSEQUENCE FOR THE NEW INSTRUMENT, stated so the plan and I agree: an entry recorded honest-unset this way is manual_off_pipeline with a NULL label, which is kind 1's shape (fill_unset_provenance), not kind 2's. It is NOT eligible for a watch_fire_relabel and should not be: kind 2 requires pipeline_watch_manual with a non-null label. If such a trade was in truth an H2 fire, no instrument today relabels it; that gap is real, it is rare, and it is BANKED by me, not this arc's.
>
> The site comment requirement of the class rule applies: the guard states at its site that it refuses the LABEL and not the ENTRY.

**Orchestrator's encoding instruction (relayed with the ruling):** T4.3 is UNPARKED in form C -- no rung on the entry POST; the D86 shapes refuse the LABEL where the service refuses the latch binding / cohort keys, with the site comment; test 4h asserts (i)-(iv) per D86 shape, discriminating against both a 400 and an admit-with-keys implementation; the 16 tests in `test_22a_task10_entry_route_ext2.py` stay green. Order: after T1-T2, then the gates, then return before Reviewer A.

## Executing -- cell 3: the T1.1 fan-out, class by class (how each was closed)

The patch `t1.1-wip.patch` applied clean on `a36aaf67`. `tests/data` with it: 171 failed / 10 errors (as handoff 2 recorded). Closed as follows (each class READ at its failing sites, not sampled):

1. **A HEAD payload into an OLD-version world (~110 cases: `test_migration_0041_pc_update` 94, `_fi6_pins`, `_census`, 0039 a2_12..15, a2_31, 0040 b22_62/b22_222..224).** Fixed at the two BUILDERS, never per test: `tests/_tier2_world_22a2.py:insert_payload` and `tests/_22b_fixtures.py:insert_row` (for `provenance_corrections` only) drop `correction_kind` when the target table lacks the column, after ASSERTING the payload's value is `fill_unset_provenance` -- exactly what 0042's copy writes for a pre-0042 row, so the dropped key is the older-column subset of the SAME row (0039 SS-1's precedent). A kind-2 value is never dropped (the assert refuses it).
2. **HEAD-tracking version mirrors `== 41` (method: `git diff -U0 -- tests` grepped for added lines reading `== 42` -> 45 lines across 33 files, a count that also includes the class-3 and census edits below).** Moved to 42, bodies only, NO renames (the version-mirror rule). Every site was read for HEAD-ness before the edit: those asserting `EXPECTED_SCHEMA_VERSION`, or the version after `ensure_schema`/a walk to HEAD. Left at their numbers (READ, not HEAD-tracking): `test_migration_0041_triples.py:240` (a parametrized migrate-to-version), `test_migration_0039_...:707`'s old `len(cols) == 41` (moved to 42 below, it IS HEAD), `test_models_phase12_bundle_c.py:66` and two `fill_id == 41`/`clear_trade_id == 41` (row ids). `test_migration_0041_census.py:214` is per-WORLD: the PC world is built by `build_last_word_world` (ensure_schema -> 42), every other world by `migrated(..., 41)`, so the assertion reads `42 if table in PC_WORLD else 41`.
3. **0039 HEAD-pinned DDL tests.** About 0039's OWN text -> re-pointed to `target_version=39` via a new `_migrate_to_39` (a2_10, a2_11). a2_17 now pins both halves: at v39 the four objects are their source text, and at HEAD they are 0042's re-create (`head_create_statement(name)[0] == M0042`) AND still byte-identical to the source. HEAD-scoped per the plan's 1m row: a2_23 matches `CHECK \(admission_tier IN` (the coupling CHECK carries a second IN-list) and asserts 4 values; a2_24 `_COLUMNS[-2]` is the seventh column and `[-1] == "correction_kind"`; a2_25 reads M0042 and its tier regex widened to `'(last_\w+|latch_ladder\w*)'` (a hand-listed alternation would silently miss `last_fire`); a2_31's HEAD column count 41 -> 42.
   - **A REAL CATCH, not a fan-out:** `test_the_head_citation_trigger_keeps_every_fei_consumer_marked` failed 7 references vs 6 markers. 0042's kind-2 `last_fire` arm (edit 3) READS `fill_envelope_identity` with NO `FEI-CONSUMER` marker. Fixed in the migration: the arm now carries `-- FEI-CONSUMER last_fire_subject_order_id :: VERSION_BLIND` (the `last_word` consumer's claim and L19 reason: a stored reading used as EVIDENCE OF ABSENCE, where a version filter would WIDEN acceptance), the header's edit-3 line names it, and the test's expected marker set is 0037's plus exactly that one. Schema manifest regenerated after the edit: still exactly four changed line pairs, zero deletions.
4. **Census / inventory tests enumerating literal sites.** `test_entry_intent_drift.py` `hypothesis_test_by_design`: 0042 added as a classified site ("tight-by-design: the citation trigger's kind-2 F5 gate, pinned by 1m"), models.py's classification names `PROVENANCE_WATCH_FIRE_ENTRY_INTENT`. `test_22a_task3_epoch_reader.py`: `max_candidate_id_at_barrier` now lives in 0039 (historical re-create) AND 0042 (HEAD twin) -- both NAMED in the exact set. `test_22f_inv_model_roster.py`: the two split validators `ProvenanceCorrection._validate_recommendation_snapshot` / `_validate_remaining_snapshots` classified in `LATER_ARC_ROSTER` as `persisted` (sole caller `ProvenanceCorrection.__post_init__`, `models.py:3707-3708`, grep over `swing/`). `test_no_schema_change_v3.py`: ceiling 41 -> 42 with the 0042 sentence. `test_migration_0036_...::test_every_declared_column_is_present_and_notnull_as_designed`: the three recommendation columns move to the NULLABLE set with their reason (F3 = A; kind 1's NOT NULL is now the presence CHECK), and `correction_kind` joins the NOT NULL list. `test_migration_0040_entry_intent.py::...b22_44[fresh]`: the citation trigger's HEAD text is now 0042's -- NAMED in `V42_RECREATED_FOREIGN_OBJECTS` and asserted equal to 0042's statement and unequal to v40's, the other v40 objects still byte-identical.
5. **`test_22f_d39_apply_migration.py`, the 10 setup ERRORS.** Diagnosed: the `v40` fixture asserts `EXPECTED_SCHEMA_VERSION == _V_BEFORE + 1` because the instrument needs EXACTLY ONE migration to apply (R1-06's nothing-in-flight pins read the version after the FIRST commit). Fixed HEAD-tracking: `_V_BEFORE = EXPECTED_SCHEMA_VERSION - 1` (so the instrument now drives 0042), docstring updated. The fixture NAME `v40` is now stale; its rename is owed as a separate change (the version-mirror rule: never in the bump commit).
6. **The three undiagnosed.** `test_migration_0041_header.py::test_the_22i_gate_row_is_the_canonical_clause`, `test_phase13_t3_sb1_prerequisite.py::test_sqlite_connect_smoke` and `test_v20_migration.py::test_v20_migration_lands_all_tables` were all class 2 (an `EXPECTED_SCHEMA_VERSION == 41` / version-after-ensure_schema assertion inside them).

**Outside `tests/data` (the first full fast suite with the patch applied: 5 failed / 15882 passed / 13 skipped, 931 s):**
7. **A PRE-EXISTING red from cell 1, not a fan-out.** `test_cohort_provenance_derivation.py::test_derivation_rule_version_is_pinned_to_the_source_sha`, `::test_R5M4_the_digest_is_STABLE_across_processes` and `test_22a_task7_shared_derivation.py::test_the_pin_covers_the_extracted_derivation_and_its_return_shape`: T3 (`063235a1`) edited the DOCSTRING of `match_candidate_to_hypotheses`, a member of `DERIVATION_RULE_DEPENDENCIES`, and the digest hashes SOURCE. Proved T1.1-independent: a per-member source hash of the whole manifest was IDENTICAL with and without the T1.1 changes. Fixed in its own commit `8528e782` (history gains `2026-11-11.1`). **Consequence for T1.2:** F9's closure growth adds ANOTHER history entry (`2026-11-11.2`), so the arc carries two; the plan's "( "2026-11-1x.1", <digest>)" becomes `.2`.
8. `tests/trades/test_22b_composition_pin.py::..._b22_170` (22-B's byte pin over the 106 22-A2 case functions): the seven class-3 edits (A2-10/11/17/23/24/25/31) are NAMED in a new `RE_SCOPED_SG_LABEL` roster with their post-edit sha and reason, beside 22-B's three; the drift check excludes exactly those and re-pins their shas.
9. `tests/trades/test_22b_acceptance_trade20.py::..._b22_180`: its world was pinned `target_version=41` "like a head test" (the CLI's connect() refuses any non-HEAD version); now reads `EXPECTED_SCHEMA_VERSION`, so it cannot fall one version behind again.

## Executing -- handoff 3 (seat roll; written for a FRESH executing cell)

**Head at this handoff:** `50fb37d1` plus this ledger commit, branch `sg-label`, tree clean. Base of the executing diff for Reviewer A is still `b120a6eb`.

**Commits this seat (shipped order):**
| SHA | Item |
|---|---|
| `1e51539c` | docs: FX-1 ruling (RD `20261111T201903Z`, C) transcribed verbatim, orchestrator as courier |
| `8528e782` | fix(trades): T3 follow-up -- `DERIVATION_RULE_HISTORY` gains `2026-11-11.1` (class 7 above) |
| `50fb37d1` | feat(data): T1.1 (D104) -- migration 0042 + db.py + models.py + repo + manifest + tests 1b-1m, 1v + the whole fan-out (classes 1-6, 8, 9 above) |

**Evidence for `50fb37d1`:** full fast suite on the T1.1 tree `15887 passed, 13 skipped` (873 s, `-n 8`); `ruff check swing/` clean; manifest diff four pairs / zero deletions; the 34 tests of `test_migration_0042_watch_fire_relabel.py` green (1j is the RED-then-GREEN pin of the PRAGMA rename idiom; 1k pins migrate-twice; 1m is the both-kinds drift test). RED evidence for T1.1 is handoff 2's (collection `ImportError: PROVENANCE_ADMISSION_TIERS_BY_KIND` before implementation).

**Deviation this seat:** the committed 0042 differs from `gen0042.py`'s output by the hand-added `FEI-CONSUMER last_fire_subject_order_id :: VERSION_BLIND` marker (3 comment lines in the arm, 3 in the header). The generator is a WIP tool, not an artifact; the committed SQL is the source of truth.

**What remains, in order (the next cell's):**
1. **T1.2** the service (`swing/trades/cohort_provenance_correction.py`) + tests 1a, 1n-1p, 1r, 1u. Reads already done this seat, re-ground before editing:
   - `derive_cohort_keys_for_fire` `:1447`. Factor `_as_of_narrow_matches` out of `:1493-1571` (bound -> started_ts -> inverted window -> gate -> as-of registry loop -> matcher) so it returns the matches AND the context `derive` still needs (bound, `covering_by_hypothesis`, `hi`); `derive` keeps its `len(matches) != 1` refusal and everything after it byte-for-byte in behaviour.
   - `_assert_last_word_before_the_fill` `:942` validates the dates of EVERY ticker row (unbounded). Step 3(e) calls it unchanged with `cited_candidate_id=trade.candidate_id`, so by step 7 every row's `action_session_date`/`run_ts` is proven parseable: the step-7 walk can rank all rows and visit the top 5 newest-first as a bounded SIBLING (the kind-1 helper stays untouched -- record that in the ledger).
   - `_authorize` `:2142-2159`: `int(existing.cited_daily_recommendation_id)` raises `TypeError` on a kind-2 row (None). Compare `existing.correction_kind` FIRST (plan step 2's mirror-closure item).
   - `_anchor_half` `:1014` is kind-1 only (recommendation, `APLUS_BUCKET`, `_gate_on_unset_state`); kind 2 needs its own anchor using the same primitives (`_require_session_date`, `_require_naive_datetime`, `_to_utc_naive`, `fetch_candidate_by_id`, `get_evaluation_run_by_id`, `resolve_authoritative_entry_fill`, `_resolve_latch_citation(conn, cfg, trade=, trade_id=, entry_fill=, tier2=None)`).
   - `_derive`'s `_fill_gates` (rung 14a, `:1651-1698`) is the gate step 8 passes for the CANDIDATE anchor only (kind 2 has no recommendation anchor).
   - Outer txn pattern `:2793-2912` (BaseException rollback, `log_contained_note`); inner insert `:3013-3092`; `CohortProvenanceCorrectionResult.cited_daily_recommendation_id` `:2737` -> `int | None`; preview `:2296` is ~200 lines of SAVEPOINT machinery -- prefer factoring the wrapper to take a callable over copying it.
   - F9: the closure growth adds history `2026-11-11.2` (`2026-11-11.1` is taken by `8528e782`).
2. **T1.3** CLI + 1q. Live site: `swing/cli.py:3606-3611` `tier = getattr(view, "admission_tier", "last_word")`; `if tier == "last_word": ... return`; else prints latch rows -- a `last_fire` row would print as a LATCH row. Branch it.
3. **T2.1-T2.4** (tests 2a-2k).
4. **T4.3 in form C** (FX-1 ruling above): NO entry rung. The parked `t43-parked-route.diff` is form A and must NOT be applied. Make each D86 anchor shape `canonical_envelope_identity` refuses REFUSE THE LABEL (latch binding + cohort keys) where the service refuses the latch binding, with the site comment "refuses the LABEL, not the ENTRY"; rewrite 4h to assert (i)-(iv) per shape, discriminating against BOTH a 400 and an admit-with-keys implementation (handoff 2's RED: a duplicate-key anchor without a claim got 200 AND keys on the old code). The 16 tests of `test_22a_task10_entry_route_ext2.py` stay green.
5. Mirror closure BY READ (still open beyond handoff 2's list: the service sites `:878`, `:1097`, `:1106`, `:2125`, the reader `:3359-3369`/`:3405-3408`, `frozen_value_evidence.py:1305-1311/1393-1397`, `entry_intent_assignment.py:307-316`, `trg_eia_audit_trail`, each member grepped separately in `tests/`).
6. Gates: full suite to `exec-branch-suite.txt`, ruff, migrate-twice (1k), drift (1m). Then RETURN before Reviewer A (the orchestrator opens the rounds).

**Open questions:** none. FX-1 is ruled.

## Executing -- cell 4: T1.2, T1.3, T2.1 and the mirror closure

**Commits this seat (shipped order):**
| SHA | Item |
|---|---|
| `1fa5c86f` | feat(trades): T1.2 (D104) -- the watch-fire relabel service (tests 1a, 1n, 1o, 1p, 1r, 1u; derivation history `2026-11-11.2`) |
| `c2b13c30` | feat(cli): T1.3 (D104) -- `correct-cohort-provenance --cite-fire-candidate` (test 1q) |
| `61bfd68e` | feat(recommendations): T2.1 (D102) -- per-night labels from the single prefill call site (tests 2a, 2k lister half; 2h unchanged) |
| `7b6d5776` | test(data): mirror closure (D104) -- the 0037 admission-tier comparator reads both IN-lists |
| `7f06cf1e` | test(metrics): T2.1 follow-up -- the R1-3 census roster names the memoized progress reader (COMMITTED RED: its classification lacked a named-disposition prefix) |
| `c20bb128` | test(metrics): T2.1 follow-up -- the census classification keeps a named disposition prefix (fixes `7f06cf1e`) |

**RED/GREEN.**
- T1.2: `tests/trades/test_cohort_provenance_watch_fire.py` failed collection with `ImportError: correct_watch_fire_label` before any service code. GREEN: 29 tests. `tests/web/view_models/patterns/test_review_form_decision_night.py` (1u) needs the same import, so it is RED by the same ImportError; GREEN: 2. Kind-1 regression: `tests/trades` + `tests/cli` at the T1.2 tree, 3982 passed / 8 skipped. The only kind-1 tests that moved are the digest pins (history entry), the closure check (manifest), and `test_22a_task7_shared_derivation.py::test_the_gate_is_a_parameter_so_the_refusal_ORDER_is_preserved` (deviation 1).
- T1.3: `tests/cli/test_correct_cohort_provenance_fire_mode.py` had 8 failures before the CLI change (`No such option: --cite-fire-candidate`). GREEN: 13. a2_77 is RED on the new manifest and GREEN after its body edit.
- T2.1: `tests/recommendations/test_decision_nights.py` failed with `ImportError: DecisionNight` on the T1.3 tree, verified by stashing the prefill module. GREEN: 6. The census test (2h) and the existing prefill tests stay green (25 `-k prefill` tests across cli, web and recommendations).
- Closure fix: the PRE-fix comparator, run under `PYTHONHASHSEED` 1-6, PASSED on 1 and 4 and FAILED on 2, 3, 5 and 6 (a hash-seed flake 0042 introduced). The fixed comparator passes on seeds 1-4.

**Deviations from the plan's letter, each with its reason:**
1. **Factorings, all verbatim moves.** Rungs 16-17 and the matcher call moved from `derive_cohort_keys_for_fire` into `_as_of_narrow_matches`, which returns a `_NarrowMatches` container. The exactly-one assertion and everything after it stay in `derive_cohort_keys_for_fire`. Rung 14a moved from `_derive`'s closure into `_same_session_creation_order_gate(anchors, *, fill_session)`, and its refusal text is unchanged. The dry-run SAVEPOINT machinery moved into `_within_preview_savepoint(conn, work)`, and the apply's BEGIN IMMEDIATE / ROLLBACK machinery into `_within_write_transaction(conn, work)`. These moved verbatim, comments included, so kind 2 runs under the same copy. `test_the_gate_is_a_parameter_so_the_refusal_ORDER_is_preserved` now reads `_as_of_narrow_matches`'s source, where the code lives. It also asserts that `derive_cohort_keys_for_fire` delegates with `gate=gate`.
2. **F9: the manifest gained more than the plan listed.** The plan named the watch predicates, and they were already members. The closure walker from `_derive` demanded `_as_of_narrow_matches` and `_same_session_creation_order_gate`. Kind 2's own decision is now pinned too, because kind 2 writes the head version. That pin covers `_derive_watch_fire`, `_derive_last_fire`, `WATCH_FIRE_WINDOW_ROWS`, the three readers the walk uses (under their home modules), `_require_session_date` and `is_trading_session`. A SECOND closure root checks it (`test_the_kind2_closure_is_fully_accounted_for`). The exclusion list gains the two containers, `_without_terminal` and the three import aliases, each with its reason. `test_no_exclusion_is_stale` now reads the union of both roots. History `2026-11-11.2` = `8b75cbd0...e89e8a`.
3. **The kind-2 dry run requires `--reason`, exactly as the kind-1 dry run does.** One authorization ladder serves both entry points, and `_reason_or_refuse` sits in it; every kind-1 CLI dry-run test passes `--reason`. **Consequence for T5's runbook:** the operator's dry-run step is `... 29 --cite-fire-candidate 15901 --reason "<text>" --dry-run`. Without `--reason` it refuses. A replay with no reason still returns the existing id.
4. **1u PREMISE CORRECTION (a plan fact, not a ruling).** Plan section 0.3 bullet 2, and the consumer-table row for `review_form.py:438`, say a kind-2 correction shifts `_build_outcome_distribution`. Read at the code, that is false. The cohort is filtered by `PROVABLE_APLUS_PE_PREDICATE` (`review_form.py:415`, the aplus-isolation arc). A kind-2 correction moves a WATCH anchor to a WATCH fire, so neither SG PE row is in the cohort before or after it, and the reading is UNCHANGED. Only an aplus night can shift that reader, which means a T2-named night under an aplus latest run. 1u is therefore two tests:
   - (i) the live shape: no shift before or after;
   - (ii) a synthetic control: an aplus detection event planted on run 207 only, which shows the join FOLLOWS `trades.candidate_id`.
   For RD/CHARC: the plan's 0.3 text needs this correction at merge, and the H2 read rule is unaffected.
5. **Test mechanics the plan left open.** The latched 1n case substitutes `_resolve_latch_citation` at the name the service resolves. The E3 ambiguous-row case plants 15980 with the fire's criteria and substitutes a scratch `_capital_blocked_match` that matches that row, so the newest row has two narrow matches. `build_sg_case` gains a `criteria_results` knob, planted by the same raw INSERT (T16 rule (a), no guard seam). 1p's drift cases use the guard seam's kind 1 (a historical rewrite of a criteria row, for DETECTION).
6. **The walk vs eligibility (e).** Eligibility (e) WRAPS `_assert_last_word_before_the_fill` and leaves it unchanged. The walk (`_derive_last_fire`) is a bounded SIBLING ranking with the same key. It validates every row's dates before ranking and applies no rung 14a gate. Step 8's derivation applies the gate, for the candidate anchor only.
7. **a2_77** (`tests/cli/test_correct_cohort_provenance_command.py`): the manifest equality is now seven entries, and `cite_fire_candidate_id` is declared LAST so the manifest only appends. The NAME still says "exactly_six", and its rename is OWED as a separate change, like cell 3's `v40` fixture. The test is registered in `test_22b_composition_pin.py`'s `RE_SCOPED_SG_LABEL` with its own reason, `_REASON_SG_CLI`.
8. **T2.1 shape.**
   - `label_for_candidate(cand, *, registry, progress)` takes a MEMOIZED zero-argument progress callable, not precomputed summaries. That keeps the lookup's "cohort read only after a match" exactly, and avoids a second spelling of the baseline rule.
   - The lister's window is the 5 newest complete-run rows, THEN filtered to the latest night's bucket. Limit-then-filter keeps it the same N rows the kind-2 walk reads.
   - A row whose stamps do not parse is left out of the offer. The POST re-derives through the same function, so such a row can never be persisted.
   - The tests live in `tests/recommendations/test_decision_nights.py`.
   - `WATCH_FIRE_WINDOW_ROWS` landed in the T1.2 commit, because the service imports it.

**What the mirror-closure read CAUGHT (beyond the planned sites):**
- `tests/data/test_22a_task2_migration_0037.py::test_the_sql_and_python_admission_tier_enums_agree`: a hash-seed flake (fixed in `7b6d5776`, measured above).
- Handoff 2's "nothing imports the tier set from `latched_origin`" was FALSE. The same test imports `PROVENANCE_ADMISSION_TIERS` through that re-export in a MULTI-LINE import, which a single-line grep cannot see. A multiline search over the whole worktree confirms it is the only consumer. The re-export is value-agnostic (it is the same object).
- `_fill_anchor_drift`'s escalation compared `str(None)` (`'None'`) against an ISO session. `'N'` sorts after every digit, so every identity move of a kind-2 row would have reported a FALSE `CITATION INVALIDATED`. A NULL anchor is now skipped (`cohort_provenance_correction.py:4350`).
- `_read_provenance_corrections_inner` crashed (`json.loads(None)`) on any kind-2 row. The recommendation drift is now kind-1 only (`:4452`ff).
- `_authorize`'s replay compare raised `int(None)` on a kind-2 row. The kind is now compared first (`:2271`), and the refusal names the existing row's kind (`_existing_correction_refusal`, `:2331`).
- The CLI's tier echo fell through to the latch rows for any non-`last_word` tier (`cli.py:3610-3619`).

**Mirror closure -- CLOSED BY READ (each member grepped SEPARATELY over `swing/` and `tests/`, then every hit file READ at its sites). Method: per-member `grep -rn -w` over `swing/` (`.py`, `.sql`, `.j2`), plus a multiline search for re-export consumers. A grep bounds the family from below; each site below was read.**

| Member / site | file:line | Verdict |
|---|---|---|
| `correction_kind` CHECK, coupling CHECK, five kind-CASE CHECKs, two `IS NULL OR` CHECKs, presence CHECK, citation trigger edits 0-3, update trigger `IS` lines | `0042_*.sql` (cell 3) | changed, pinned by 1b-1m, 1v |
| Python constants (`PROVENANCE_CORRECTION_KIND_*`, `PROVENANCE_ADMISSION_TIERS` (4), `_BY_KIND`, `PROVENANCE_WATCH_FIRE_*`) | `models.py:3073-3118` | changed (cell 3); comparator 1m |
| `ProvenanceCorrection.__post_init__` / `_require_value_envelope(kind=)` / snapshot bucket by kind (`"watch" if watch_fire else "aplus"`) | `models.py:3259-3290, 3484-3660, 3755` | changed (cell 3); 1b-1m |
| repo `_COLUMNS` + `correction_kind` | `repos/provenance_corrections.py:24` | changed (cell 3); a2_24 |
| `APLUS_BUCKET` gate | `cohort_provenance_correction.py:1155` | kind-1 only (in `_anchor_half`), unchanged |
| `REQUIRED_RECOMMENDATION` | `:973, :1146` | kind-1 only, unchanged |
| `UNSET_TRADE_ORIGIN` gate | `:927` | kind-1 only (`_gate_on_unset_state`), unchanged |
| `_authorize` existing-row compare | `:2271-2283` | CHANGED (kind first) |
| kind-1 inner already-applied `int(cited_daily_recommendation_id)` | `:3176` | safe: reached only via `_authorize`'s kind-1 `same` branch |
| `_preview_from_existing` | `:2872-2888` | CHANGED: NULL-safe, carries kind |
| `CohortProvenanceCorrectionPreview` / `Result` recommendation fields | `:1860, :2919` | CHANGED: `int / str \| None`, `correction_kind` field |
| reader recommendation snapshot drift | `:4468-4473` | CHANGED: kind-1 only |
| reader bucket + origin re-derivation | `:4151-4169` | CHANGED: kind-dispatched (`watch` / `pipeline_watch_manual` for kind 2) + `_last_fire_drift` (`:4217`) |
| reader trade-triple re-read over `COHORT_CORRECTED_FIELDS` | `:4208` | value-agnostic: the kind-2 applied envelope carries all three keys (origin unchanged) |
| reader fill-anchor escalation | `:4344-4350` | CHANGED: NULL recommendation anchor skipped |
| tier-2 replay dispatch `== LATCH_TIER2` | `:4432, :4446`; `frozen_value_evidence.py:1305-1311, 1392-1397` | value-agnostic: tier2-only filters; `last_fire` correctly excluded |
| `latched_origin.py` re-export | `:47, :103`; prose `:146-149, :469, :756, :790, :842` | value-agnostic; sole consumer `test_22a_task2_migration_0037.py` (multi-line import) |
| `entry_intent_assignment.py` corrected-fields read | `:305-312` | value-agnostic: a set of `trades.<f>` strings; kind 2's two fields count as touched, which is correct |
| `trg_eia_audit_trail` | `0040_*.sql:625-635` | value-agnostic (the same set membership in SQL) |
| CLI `COHORT_FIELD_ORDER` | `cli.py:3587` | value-agnostic: kind-2 pre/post carry all three keys |
| CLI tier echo | `cli.py:3606-3631` | CHANGED: `last_fire` branch + `correction kind` line |
| CLI recommendation citation (dry run, apply, already-applied, reader) | `cli.py:3655, 3872, 3958, 3978, 4030-4040` | CHANGED: `(none: watch-fire relabel)` |
| CLI options / mode check | `cli.py:3736, 3807` | CHANGED (T1.3) |
| `db.py` version comment | `db.py:119-121` | prose, current |
| web / metrics / templates | `grep -rln provenance_corrections swing` = cli, db, models, repo, the service, entry_intent_assignment, frozen_value_evidence, latched_origin | no web, metrics or template reader of the table |
| tests: tier-set literals | `test_migration_0039_*.py:395` (a2_20, 0039's OWN header text: correct at 3), `:449-452`, `test_migration_0042_*.py:610-637`, `test_22a_task2_migration_0037.py` (fixed) | read |
| **Comparator (mandatory member)** | `tests/data/test_migration_0042_watch_fire_relabel.py` 1m (both kinds) + `test_22a_task2_migration_0037.py` (both IN-lists) | green |

## Executing -- handoff 4 (seat roll; written for a FRESH executing cell)

**Head at this handoff:** `c20bb128` plus this ledger commit, branch `sg-label`. The tree is clean. Base of the executing diff for Reviewer A is still `b120a6eb`.

**Full fast suite.** At `7b6d5776`: 1 failed / 15936 passed / 13 skipped (1025 s, `-n 8`). The failure was `tests/metrics/test_22b_r1_3_surfaces_census.py::test_census_roster_matches_the_grep_for_each_governed_name`: T2.1 moved the prefill's `build_recommendation_progress` call into `_progress_reader`, and the census keys each site by its stripped line text. Fixed in `7f06cf1e` + `c20bb128`; `7f06cf1e` itself was committed RED, because the commit gate read pytest's tail rather than its exit status, and it is recorded rather than rewritten. **At `c20bb128`: 15937 passed / 13 skipped, 0 failed (1039 s, `-n 8`). `ruff check swing/` clean.** Neither run is the gate file `exec-branch-suite.txt`, which belongs to the final gate.

**Census note for T2.2-2.3:** `list_decision_nights` is a new consumer of the governed progress read through `_progress_reader`. Its web callers (the GET degrades, the POST refuses 400) must be classified in that census's roster in the T2.2-2.3 commit if the census walks them. Check `test_22b_r1_3_surfaces_census.py`'s governed-name list first.

**What remains, in order (the next cell's):**
1. **T2.2-T2.3** (one commit, `feat(web): T2.2-2.3 (D102) -- the entry form names the decision night`; tests 2b-2g, 2i, 2j, and the GET/POST halves of 2k). Re-ground every line before editing:
   - VM `swing/web/view_models/trades.py`, around `:583-614`: the `lookup_active_recommendation_label` call inside `try/except CohortReadRacedError`. Add `decision_nights`, `decision_nights_anchor_json` and `selected_decision_candidate_id`; `hypothesis_label` stays as the newest night's label. OMIT the chooser when (a) `list_decision_nights` returns `[]`, or (b) the auto-fill envelope recognises an order AND `list_links_for_broker_order` returns a link (the latched entry). Any new base-layout VM field needs a safe default on EVERY base VM (gotcha), but this is the entry-form VM. Check whether it is base-layout first.
   - Template `swing/web/templates/partials/trade_entry_form.html.j2`, around `:151-152`: the `<select name="decision_candidate_id">` and the hidden `decision_nights_anchor`. Option text must be ASCII (2i).
   - POST `swing/web/routes/trades.py`, the entry POST (the `json.loads` of the auto-fill anchor sits around `:1215`; `_reject_anchor`, `_rerender_entry_form_with_error`). Build the 4-tier ladder on `decision_nights_anchor`, then the SERVER-STAMP. `list_decision_nights` must be RE-DERIVED at POST: the chosen id must be IN it and its label must equal the submitted label, else a 400 that clears the anchor. A `CohortReadRacedError` or budget overrun at POST is a 400 (never a 500). The soft-warn `form_values` dict (around `:1960-1985`) carries both new fields. Pass `candidate_id=<chosen>` and `hypothesis_label=<server label>` to `EntryRequest`: `record_entry` already honours a supplied id when the entry is not latched (`entry.py` ~`:2016`), so there is NO `entry.py` change.
   - `list_decision_nights(conn, *, ticker, starting_equity, budget_seconds=None, n=None) -> list[DecisionNight]` and `DecisionNight` are in `swing/recommendations/hypothesis_prefill.py` (T2.1). `PREFILL_UNAVAILABLE_TEXT` is the GET degrade text.
2. **T2.4** `feat(cli): T2.4 (D102) -- the CLI prefill names its night`. `swing trade entry` keeps the latest night and prints `eval <id>, session <date>` on the prefill line.
3. **T4.3 in FORM C** (FX-1, ruled; see the block quote above). NO rung on the entry POST. Every D86 anchor shape `canonical_envelope_identity` refuses must refuse the LABEL (latch binding + cohort keys: `manual_off_pipeline`, NULL label, NULL `candidate_id`) where the service refuses the latch binding. The site comment must say "refuses the LABEL, not the ENTRY". Test 4h asserts (i)-(iv) per shape and must discriminate against BOTH a 400 and an admit-with-keys implementation. Handoff 2's RED: a duplicate-key anchor without a claim got 200 AND keys on the old code. The 16 tests in `tests/web/test_routes/test_22a_task10_entry_route_ext2.py` stay green. Do NOT apply `t43-parked-route.diff` (form A). The parked 4h test (`t43-parked-test_d86_entry_raw_rung.py`) is a starting point for the anchor shapes only, because its assertions are form A's.
4. **Gates:** the full fast suite to `C:\Users\rwsmy\swing-data\review-transcripts\sg-label\exec-branch-suite.txt` (foreground, `-n 8`, tail only), `ruff check swing/`, migrate-twice (1k) and the drift test (1m). Then RETURN before Reviewer A.

**Owed, banked here for the merge gate:** the a2_77 rename (deviation 7) and cell 3's `v40` fixture rename (both separate renames), and the plan-text correction of section 0.3 / the review-form consumer row (deviation 4).

**Open questions:** none.
