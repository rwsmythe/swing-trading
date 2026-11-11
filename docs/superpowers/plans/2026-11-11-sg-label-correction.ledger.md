# Ledger: the watch-origin label correction arc plan

Plan: `docs/superpowers/plans/2026-11-11-sg-label-correction.md`. Brief: `docs/sg-label-correction-arc-brief.md` (`3b64f9ec`). Base `main` `f1eb4051`. Recipe read at the MAIN copy on 2026-11-11.
Transcripts (when rounds run): `C:\Users\rwsmy\swing-data\review-transcripts\sg-label\`.

## Round table

| Round | Kind | Tier / banner | `^ERROR` | footer | verdict token | crit/maj/min (reviewer) | task-bearing | NEW / REOPENED | reverts | tokens used | depth (orchestrator fills) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | premise + fork census, NO Codex | -- | -- | -- | -- | -- | 10 forks routed (F0-F9) | -- | -- | 0 | |

## Round 0 -- the census

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

### Banked / follow-on dispositions (proposed)

- P11 LQDA post-dating candidate night: BANKED, owner CHARC, trigger = the next `record_entry` provenance arc.
- F7-B CLI chooser: BANKED, owner CHARC, trigger = an operator CLI entry mis-stamp.
- D86 verbatim-ticker clause: stays BANKED on the D86 row (no test bites in this arc).
