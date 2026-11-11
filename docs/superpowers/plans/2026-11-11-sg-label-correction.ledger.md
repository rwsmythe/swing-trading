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

## Encoding choices the rulings do not state literally (CHARC's plan-stage read)

- **E1 -- RD's intent gate also lives in SQL.** The kind-2 arm's trade `EXISTS` carries `t.entry_intent = 'hypothesis_test_by_design'`. **Reason:** this table's schema IS the evidence rule (0036). Intent is a FACT on the trade, not a ranking, so SQL may verify it. Without the clause, a raw kind-2 insert for a standard-intent trade satisfies every structural check. **Cost:** one literal more in the mirror family, compared by 1m.
- **E2 -- the citation trigger's top-level WHEN gets 0041's two-substitution wrap (edit 0).** **Reason:** the brief's section 1 T1 bullet says "Every `WHEN NOT (...)` arm is `WHEN NOT COALESCE(..., 0)`", and F3 says "a NULL anywhere in it must ABORT". No kind-1 outcome changes, because every top-level conjunct is `EXISTS` or `COALESCE`.
- **E3 (UNSETTLED by the ruled text) -- a window row with two or more narrow matches REFUSES the correction and is not passed over.** The ruled text is "the newest ... row ... whose as-of narrow matcher ... returns exactly one match". Read literally, it would pass over a multi-match row and derive an OLDER fire past a NEWER one. The plan encodes the fail-safe refusal. The case is unreachable on today's registry, because a watch row reaches H2 alone since D84 and H3 is closed. CHARC to confirm or reverse at the plan-stage read.
- **E4 -- the H2 partition (section 0.2) cannot be expressed by the backlink alone.** RD asked to be told if so, and is.

## Banked / follow-on dispositions (RULED)

- P11, the LQDA candidate night post-dating the entry: BANKED. Owner CHARC; a register row lands at the arc's close, with the charter compression.
- F7-B, the CLI chooser: BANKED. Owner CHARC; trigger: an operator CLI entry mis-stamp.
- D86's verbatim-ticker clause stays BANKED on the D86 row (no test in this arc shows it bites).
- The H2 three-way read rule: owner RD. It lands in the watch-standard at the merge (RD item 5), reading section 0.2's statement.

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

| Round | Kind | Tier / banner | `^ERROR` | footer | verdict token | crit/maj/min (reviewer) | task-bearing | NEW / REOPENED | reverts | tokens used | depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | premise + fork census, NO Codex (`bafddb6a`) | -- | -- | -- | -- | -- | 10 forks routed (F0-F9) | -- | -- | 0 | |
| 0-fold | rulings folded, NO Codex (continuation cell) | -- | -- | -- | -- | -- | 0 (E1-E4 declared; E3 unsettled) | -- | -- | 0 | |
