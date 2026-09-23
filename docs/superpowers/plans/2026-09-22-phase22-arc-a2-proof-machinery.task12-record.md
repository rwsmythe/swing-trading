# Phase 22 arc 22-A2 (PROOF MACHINERY) -- Task 12 executing record

Plan: `2026-09-22-phase22-arc-a2-proof-machinery.md` (Task 12, section 5). Exec ledger: `...proof-machinery.exec-ledger.md` (the gate table and every ruling; rulings govern over the plan). This file is the record Task 12 owes. It does not edit the exec ledger; the orchestrator links it from there. Author: exec cell 12 (`implementer-opus-high`), branch `22-a2-exec`. Rules read from MAIN by absolute path at `a4ac72ee`.

Method, stated once. Every count below says how it was produced. A token grep bounds a family from BELOW; only a read establishes a manifest. Nothing in this file was measured against the live DB. Section (iii) cites the exec ledger's G-T11 row, where cell 11 recorded the live-copy evidence, and re-runs nothing.

---

## (i) P34 -- the migration-text tests, and what each now reads

**The rule** (plan Task 3 step F; CHARC F12 condition 6; encoding 9). 0039 re-creates the six dependants of `provenance_corrections`. Two indexes and two triggers are re-created verbatim: `trg_provenance_corrections_append_only_delete` and `trg_pc_no_replace`. Two triggers are CHANGED: `trg_provenance_corrections_append_only_update` and `trg_provenance_corrections_citation_graph`. The table itself is created as `provenance_corrections__0039` and RENAMED, so `head_create_statement("provenance_corrections")` still resolves to 0036 by design.

The classes are:
- **(i)** asserts a property of an object 0039 re-creates -> re-pointed to `tests/data/_migration_text.py::head_create_statement`, the LAST migration that CREATEs the object.
- **(ii)** asserts 0037's own text, or an object 0039 does not touch -> unchanged.

**How the set was produced.** (1) The plan's lower-bound grep `grep -rln "0037_latch_order_mandate_links\|MIGRATION_0037" tests/`, which returned 7 files. (2) Users of `head_create_statement` / `create_statement_in`, 8 files. (3) Every test file that reads a `00(36|37|38|39)_*.sql` text, 12 files. (4) Every test file naming a re-created trigger, 8 files. The union was READ reference by reference: each migration-text read, with its enclosing test function, was listed by an AST walk and then read. Cell 1 made the classification at Task 3 (G1 note 4, quoted in section (v)); what follows is that classification re-derived on disk at this head.

| test file | test / site | reads | class | note |
|---|---|---|---|---|
| `tests/data/test_22a_al3_closure.py` | module `CITATION_TRIGGER_MIGRATION` (`:69`) -> `_when_body` (`:177`), `test_DECLARED_the_boundness_walk_cannot_see_a_WEAKENED_predicate` (`:481`) and every walk built on them | the WHOLE HEAD migration file (`head_create_statement(...)[0]` = `0039_...sql`) | (i) | re-pointed |
| same | `test_a_non_blob_member_names_an_anchor_that_exists_in_0037` (`:278-294`) | the anchor asserted in BOTH 0037's text and the HEAD file | (i)+(ii) | kept on 0037 AND checked in HEAD |
| `tests/data/test_22a_authorize_then_abort_closure.py` | module `CITATION_TRIGGER_MIGRATION` (`:83`) -> the SQL-side walk (`:180`), `test_R3M2_a_COMMENT_ONLY_clause_satisfies_neither_walk` (`:605`) | the WHOLE HEAD migration file | (i) | re-pointed |
| `tests/data/test_22a_task2_migration_0037.py` | `test_the_migrations_authorization_closure_list_matches_the_roster` (`:840`) | HEAD citation-trigger statement | (i) | re-pointed |
| same | **`test_the_migrations_probe_evidence_closure_list_matches_the_roster` (`:1193`)** | **0037's file text** | **(i), NOT re-pointed** | **FINDING P34-1, below** |
| same | **`test_the_migrations_probe_guard_closure_list_matches_the_roster` (`:1207`)** | **0037's file text** | **(i), NOT re-pointed** | **FINDING P34-1, below** |
| same | `test_no_statement_sits_between_a_drop_and_its_create_case_44` (`:621`) | 0037's file text (its own BEGIN/COMMIT and DROP-then-CREATE order) | (ii) | a property of 0037's FILE; 0039's order is A2-16 |
| same | `test_the_migration_performs_no_rounding_in_a_price_position` (`:869`) | 0037's file text | (ii) | 0039's whole HEAD trigger has its own `round(` gate in A2-29 (`test_migration_0039...:613-624`) |
| same | `_old_append_only_columns` (`:648`), feeding case 43 | 0036's `append_only_update` text | (ii) | reads the OLD guarantee on purpose; case 43 then asserts it against the live HEAD DB |
| `tests/data/test_22a_task3_epoch_reader.py` | `test_the_epoch_is_read_in_exactly_one_place` (`:280-298`) | sites-of-token across `swing/`, with the HEAD citation file admitted as a legitimate site | (i) | re-pointed |
| same | `test_the_evidence_version_constant_matches_the_migration` (`:472`) | HEAD citation-trigger statement; the set of probe-version literals == `{LATCH_PROBE_EVIDENCE_VERSION, LATCH_PROBE_TIER2_EVIDENCE_VERSION}` | (i) | re-pointed; plan Task 3 F's pin, as specified |
| same | module constant `MIGRATION` (`:58`) | nothing: defined, never read (`grep -n "MIGRATION\b"` hits only the definition) | -- | FINDING P34-3 (dead constant, minor) |
| `tests/data/test_22a_canonicalizer_version_closure.py` | `_sql()` (`:90`) -> every FEI-marker / reference / claim / ships-empty / anchor test | 0037's file text | (ii) | the FEI table, its anchor and its ships-empty property live in 0037. The HEAD citation trigger is covered by a NEW HEAD pin (next row). FINDING P34-2 |
| `tests/data/test_migration_0039_provenance_corrections_tier2.py` | `test_the_head_citation_trigger_keeps_every_fei_consumer_marked` (`:699`) | HEAD citation statement vs 0037's statement | new HEAD pin | marker set equal to 0037's, and every FROM/JOIN reference in HEAD marked |
| same | A2-17 (`:305`), A2-25 (`:461`), A2-29 (`:613`), A2-31 (`:665`), `test_g_t7f_sql_asserts_the_derivation_version_type_and_never_its_value` (`:885`), `test_g_t7f_blob_closed_path_list_equals_the_python_roster` (`:894`) | HEAD statements (A2-17 also each re-created object's source text via `create_statement_in`) | born HEAD | -- |
| `tests/data/test_22a_task11_citation_evidence.py` | `test_the_migration_never_rounds_a_price_case_34g_gate` (`:602`) | 0037's file text | (ii) | as the task-2 no-rounding row |
| `tests/trades/test_22a_envelope_canonicality_sweep.py` | `test_migration_0037_never_reads_a_fill_envelope` (`:274-282`) | 0037's file text | (ii) | its sibling `test_no_sql_anywhere_in_swing_reads_a_fill_envelope` sweeps every SQL file, 0039 included |
| `tests/trades/test_22a2_conjunction.py` (`:581`), `tests/trades/test_22a2_acceptance_trade25.py` (`:365`) | the TIER2-PREDICATE twin roster | HEAD citation statement | born HEAD | -- |
| `tests/trades/test_cohort_provenance_write.py` | `:648` (trigger-disable helper), `:876` (docstring) | the live DB's triggers / PRAGMA, not migration text | not a text reader | -- |
| `tests/data/test_migration_0038_attempt_identity.py`, `tests/data/test_22a2_barrier_drop_scan.py`, `tests/data/test_22a_candidates_barrier_helper.py` | -- | 0038's own text / every migration file (Task 1's scan) / helper source | not P34 | objects 0039 does not touch |

The old model test that PINNED `latch_ladder_tier2` as rejected was flipped by design. Per cell 1 (G1 note 4), `test_an_unknown_admission_tier_is_rejected` now uses `latch_ladder_tier3` and matches the enum message, and A2-24 carries the three-way rule.

**FINDING P34-1 (flagged, not fixed: outside this unit's two commits).** Two tests in `tests/data/test_22a_task2_migration_0037.py` assert a property of `trg_provenance_corrections_citation_graph`, which 0039 re-creates, and they still read 0037's TEXT:
- `test_the_migrations_probe_evidence_closure_list_matches_the_roster` (`:1193`): the top-level `json_remove(NEW.cited_latch_probe_json, ...)` list == `PROBE_EVIDENCE_KEYS`.
- `test_the_migrations_probe_guard_closure_list_matches_the_roster` (`:1207`): the `$.probe_guards` list == `PROBE_GUARD_KEYS`.

That is class (i) left on a superseded definition, which is #31's shape and exactly what condition 6 exists to prevent. Cell 1's G1 note 4 names only "test_22a_task2_migration_0037's closure-list test" (singular: the `$.authorization` one, `:840`, which WAS re-pointed). No HEAD-level test compares these two lists to their rosters: `grep -rn "PROBE_EVIDENCE_KEYS\|PROBE_GUARD_KEYS"` over `tests/` finds only emitter-side and 22-A task-6 uses, and no reader of the HEAD statement.

Measured today, no live defect. Each marker occurs exactly once in both the HEAD statement and 0037's statement, and the extracted key SETS are equal (the script is in the cell's session scratchpad; not committed). The exposure is forward: an edit to either list in a later re-create would leave both tests green.

The fix shape is the one the rest of P34 used: read `head_create_statement("trg_provenance_corrections_citation_graph")[1]` in both tests, as `:840` already does. It is test-only; the pair would pass today on the measured equality. Recommended disposition: a one-commit follow-on before the merge, the orchestrator's call. CHARC owns condition 6's shape.

**FINDING P34-2 (recorded; cell 1's (ii) classification stands, the exposure is named).** `test_22a_canonicalizer_version_closure.py` walks every FEI consumer in 0037's FILE, including 0037's own copy of the citation trigger. That copy is superseded. The HEAD pin (`test_the_head_citation_trigger_keeps_every_fei_consumer_marked`) asserts two things: marker-set equality with 0037's citation trigger, and that every HEAD reference is marked. It does NOT re-measure each HEAD span's claim (`VERSION_CHECKED` / `VERSION_BLIND` against what the span contains), which `test_each_marker_CLAIM_matches_what_its_span_actually_contains` does for 0037.

Measured today: a `difflib` opcode walk of 0037's citation statement (1276 lines) against the HEAD statement (1539 lines) gives 7 non-equal opcodes. NONE touches, on either side, a line in a hunk containing `fill_envelope_identity`, `FEI-CONSUMER` or `canonicalizer_version`. The HEAD spans are therefore byte-identical to the measured 0037 spans at this head; the exposure is forward only, the same shape as P34-1.

**FINDING P34-3 (minor).** `tests/data/test_22a_task3_epoch_reader.py:58` defines `MIGRATION = ... 0037_latch_order_mandate_links.sql` and nothing reads it. The test at `:280` builds its own string literal. A dead constant that names a superseded file is the kind a later reader re-reads as live.

---

## (ii) The #11 sweep -- closure-checked by READ, each member grepped separately

**Method.** A scratch script (session scratchpad, not committed) searched `swing/**/*.py`, `swing/**/*.sql` and `swing/**/*.j2` for EACH member as a separate fixed string. Quote styles were searched separately, and `'pass'`/`"pass"` was scoped to `latched_origin.py` + 0039 as plan Task 3 G specifies. The counts are lines/files. Every hit was then READ. The member set is the plan's step-G list, plus the verdict vocabulary, plus every constant a ruling added (F2.I-NEG, G-NEG, G-U1, G-T7F/AMEND, G-T7FE, G-T9, G-T10-1/-2). Beyond the member greps, every `admission_tier` read site in `swing/` was read, to catch a branch on the tier that names no member (the paraphrase class).

Classes: **widened** = carries the new member; **tight-by-design** = names a subset on purpose; **value-agnostic** = passes the value through without naming a member; **historical** = a comment in an immutable migration that describes its own time.

| member | hits (lines / files) | sites READ and classified |
|---|---|---|
| `latch_ladder_tier2` | 24 / 7 | 0039 CHECK `:211` (widened); 0039 shared arm `:1149` and version CASE `:1250`, rung-9 CASE `:1936` (widened); `models.py:3033` constant (widened), `:3480/:3498` paired-rule prose/message (widened); `cohort_provenance_correction.py` detector `:2059` (widened); `frozen_value_evidence.py:1244` selector (widened); `latched_origin.py:146` comment; `cli.py:2656/:2769` comments; 0037 `:780` "arrives with 22-A2" (historical) |
| `'latch_ladder'` / `"latch_ladder"` | 12 / 2, 2 / 2 | 0037 CHECK `:788` + arm `:1272` (historical, superseded by 0039); 0039 `:211`, `:1149`, `:1249`, `:1927` (widened / tight-by-design per arm); `models.py:3032` constant; `cohort_provenance_correction.py:1785` comment |
| `'last_word'` / `"last_word"` | 12 / 3, 3 / 2 | 0039 CHECK default + arm `:1124` (tight-by-design: all five latch NULL and the seventh NULL); `models.py:3031` constant, `:3488` message; **`cli.py:2639/:2641` hard-coded `"last_word"` literal**: correct for all three tiers (it branches last_word vs the latch family; tier-2 extras render off `tier2_clauses`), but a hard-coded single member rather than the constant (the 22-A twelfth-site shape), FINDING S-2 |
| `PROVENANCE_ADMISSION_TIER*` | 34 / 5 | `models.py:3031-3036` (set of three), `:3470` membership, `:3482`/`:3492` paired rule (widened); `cohort_provenance_correction.py:2062-2065` detector, `:3561/:3575` render (widened); `frozen_value_evidence.py:1173/:1249` (tight-by-design: tier-2 only); `latched_origin.py:44-47/:103-106` re-export (value-agnostic) |
| `admission_tier` (all read sites, by read) | -- | `cli.py:2623-2662` render (see `"last_word"`); `repos/provenance_corrections.py:61` column list (value-agnostic); `cohort_provenance_correction.py:2513/:2633/:2692/:2956/:3052/:3077` pass-throughs (value-agnostic); no template names it |
| `PROVENANCE_TIER2_EVIDENCE_FIELD` / `cited_frozen_value_evidence_json` | 5 / 1; 133 / 5 | `models.py:3042/:3372/:3481-3497` (widened); `repos/provenance_corrections.py:69` insert/select list (widened); `cohort_provenance_correction.py:3061` writer; `frozen_value_evidence.py:1195` replay read; 0039 `:214` column, `:759` append-only UPDATE guard (widened: the seventh column is immutable); the other 0039 hits are the trigger's seventh-column block |
| `escaped_by_tier2` / `AUTHORIZATION_VERDICT*` | 9 / 2; 11 / 1 | `latched_origin.py:159-162` constants + set, `:1366` override vocabulary check, `:1372` default, `:1974` the one override site (widened); 0039 `:1939` tier-2 arm (widened) |
| `'pass'` / `"pass"` (latched_origin + 0039) | 22 / 2; 3 / 1 | 0039: 21 `... .verdict') = 'pass'` predicates, each a probe-guard or non-rung-9 authorization clause, plus rung 9 on the `latch_ladder` arm `:1929` (tight-by-design: only rung 9 on a tier-2 row may differ, F11); `latched_origin.py:2292` `_probe_guard_block` (tight-by-design, docstring `:2277-2283` gives why); `:461/:2281` comments |
| `pre_barrier_reconstructed` / `live_at_acceptance` | 4+1 / 3; 6+1 / 3 | `models.py:3019/:3020` constants; 0037 `:320` freeze-tier CHECK + `:730/:764` minting CASE (0037 is HEAD for these); 0039 `:1931` (`latch_ladder`: `live_at_acceptance`), `:1943` (tier-2: `pre_barrier_reconstructed`) -- tight-by-design per arm |
| `gap_era_reconstructed` | 3 / 2 | comments / message only (AL2-5: named and UNMINTED) |
| `2026-08-25.1` | 5 / 4 | `latched_origin.py:144` `LATCH_PROBE_EVIDENCE_VERSION`; 0037 `:1368` (historical); 0039 `:1249` (`latch_ladder` arm); `cohort_provenance_correction.py:375/:383` -- a DIFFERENT constant, the `_derive` `DERIVATION_RULE_HISTORY` pair that happens to share the string (value-coincident, not a mirror) |
| `2026-09-23.1` | 5 / 3 | `latched_origin.py:152` `LATCH_PROBE_TIER2_EVIDENCE_VERSION`; `frozen_value_evidence.py:47` `FROZEN_VALUE_EVIDENCE_VERSION` (grammar); 0039 `:1250` (probe, tier-2) and `:1974` (seventh blob): two constants, one string, each bound to its own SQL literal; `frozen_value_evidence.py:1507` comment on why `.1` is not reused for the derivation history |
| `2026-09-23.2` / `.3` / `FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION` / `derivation_version` | 1/1, 2/1, 7/2, 15/2 | `frozen_value_evidence.py:58` current `.3`, `:1517-1519` append-only history (`.2`, `.3`); `:796` emitted; `:864-866` type twin; `:1199-1202` replay observation; 0039 `:1961` blob_closed list, `:1979` `json_type = 'text'` ONLY (G-T7F item 3: SQL never asserts its value) |
| replay verdicts `ADMIT` / `tier2_evidence_stale` / `tier2_unverifiable`, `VERDICT_*` | 1/1, 1/1, 11/2 | `frozen_value_evidence.py:169-172` constants + `REPLAY_VERDICTS`; every return in `replay_verdict` `:1183-1239` and the excluder `:1300/:1342/:1348` uses the constants; `cohort_provenance_correction.py:3506` docstring. Python-only (never crosses SQL). **Name collision, not a mirror:** `swing/latches/models.py:100` `VERDICT_UNVERIFIABLE = "UNVERIFIABLE"` is the latch-validity vocabulary, unrelated |
| `derivation_version_moved`, `web_budget_exhausted` / `REASON_WEB_BUDGET_EXHAUSTED`, `WEB_REPLAY_BUDGET_SECONDS`, `Tier2CohortRead` | 3/1, 3+4/1, 19/11, 8/3 | Python-only. `WEB_REPLAY_BUDGET_SECONDS` 11 files: the constant `frozen_value_evidence.py` + the web callers G-T10-1 (2) names (dashboard VM, trade-entry prefill, tier VM, card route) and their threading through `journal/stats.py`, `metrics/tier.py`, `recommendations/hypothesis_prefill.py`, `web/routes/metrics.py`, `web/view_models/{dashboard,trades}.py`, `metrics/{deviation_outcome,hypothesis_progress_card,index,tier_comparison}.py` -- imported from `swing/trades/frozen_value_evidence`, never re-typed (read) |
| `tier2_evidence_refused` | 9 / 2 | `latched_origin.py:289` decline roster member; `:1938/:1946` emit; **`latched_origin.py:637` and `cohort_provenance_correction.py:1954` compare the string LITERAL**, value-correct, FINDING S-2 |
| `window_indeterminate` / `window_negative` | 1/1, 1/1 | `frozen_value_evidence.py:118-119` constants only (G-U1); Python-only |
| `record_position`, `before_barrier`, `inside_coverage` | 18/2, 6/2, 6/2 | `frozen_value_evidence.py:149-152` constants + `RECORD_POSITIONS`, `:163` `VERDICT_BEARING_KEYS` entry, `:640` emit, `:956-958` / `:1026-1032` twins (constants); 0039 `:2066` interval_closed, `:2068-2070` type + IN-list, `:2170-2171` the G-NEG belt (widened). **Crosses SQL + Python: no SQL-vs-Python comparator, FINDING S-1** |
| segment kinds `fire` / `writer_absence_only` / `match_only` / `covered` / `uncovered_barrier_absent` | 1+2/2, 7/2, 12/2, 2+2/3, 4/2 | `frozen_value_evidence.py:144-146` constants; **`:627-629` and `:648` use string LITERALS** for `fire` / `writer_absence_only` / `match_only` rather than `SEGMENT_KINDS` (value-correct, FINDING S-2); `:1005-1023` twin uses the constants; 0039 `:2142-2151` order predicate (widened: G-NEG's 3-or-4). `web/view_models/latches.py:1832` "covered" is prose in an unrelated comment. **Crosses SQL + Python: no comparator, FINDING S-1** |

**The SQL-vs-Python drift comparators (the mirror set's mandatory member, #11).** Named, each read:
- `tests/data/test_migration_0039_provenance_corrections_tier2.py::test_a2_23_sql_admission_tier_check_equals_the_python_enum` -- the stored table CHECK's IN-list (read from `sqlite_master` on a fresh HEAD DB) == `PROVENANCE_ADMISSION_TIERS`, and `len == 3`.
- `...::test_a2_25_trigger_literals_equal_their_python_mirrors` -- from the HEAD citation trigger: tier literals == `PROVENANCE_ADMISSION_TIERS`; rung-9 verdict literals == `AUTHORIZATION_VERDICTS`; probe-version CASE literals == `{LATCH_PROBE_EVIDENCE_VERSION, LATCH_PROBE_TIER2_EVIDENCE_VERSION}`; seventh-blob version literal == `{FROZEN_VALUE_EVIDENCE_VERSION}`.
- `...::test_g_t7f_blob_closed_path_list_equals_the_python_roster` -- the `json_remove` path list == `FROZEN_VALUE_BLOB_KEYS` (29 keys, `derivation_version` included).
- `tests/data/test_22a_task3_epoch_reader.py::test_the_evidence_version_constant_matches_the_migration` -- the probe-version CASE, from the HEAD statement (the P34 re-point).
- `tests/data/test_22a_task2_migration_0037.py::test_the_migrations_authorization_closure_list_matches_the_roster` -- the `$.authorization` closure == `AUTHORIZATION_CLAUSES` (HEAD).
- The TIER2-PREDICATE twin roster (A2-60 in `tests/trades/test_22a2_conjunction.py`) closes predicate NAMES both ways. It is a name comparator, not a value comparator.

**FINDING S-1 (flagged, not fixed).** The interval vocabulary crosses SQL + Python (0039 `:2066-2171` vs `frozen_value_evidence.py:144-152`) and has NO SQL-vs-Python comparator:
- `record_position` IN (`before_barrier`, `inside_coverage`) vs `RECORD_POSITIONS`;
- the segment kinds vs `SEGMENT_KINDS` / `SEGMENT_COVERED` / `SEGMENT_UNCOVERED_BARRIER_ABSENT`.

`grep -rn "RECORD_POSITIONS\|SEGMENT_KINDS\|SEGMENT_COVERED\|SEGMENT_UNCOVERED\|RECORD_POSITION_"` over `tests/` returns nothing. The defences that exist are behavioural:
- G-NEG's forged-position discriminators (`test_g_neg_the_record_position_belt_refuses_a_forged_position`);
- `test_g_neg_interval_admits_exactly_one_more_typed_key`;
- the truthful-row inserts, which exercise `before_barrier` + four segments (e.g. `tests/trades/test_22a2_acceptance_trade25.py:197`);
- the F2.I-NEG cases (in the 0039 test file and `tests/trades/test_22a2_conjunction.py`, the two files naming `inside_coverage`), which exercise `inside_coverage` + three.

`grep -rln "uncovered_barrier_absent\|SEGMENT_UNCOVERED" tests/` returns ZERO files: no test names that segment kind at all. Per #11's 2026-08-24 amendment the comparator is a MANDATORY member of the mirror set. The shape would be one test in the 0039 file parsing the IN-list and the four order-predicate literals from the HEAD statement against the Python constants. Routed for disposition: PRIMARY CHARC (mirror-set shape).

**FINDING S-2 (recorded, value-correct today).** Hard-coded single members where a constant exists:
- `cli.py:2639/:2641` `"last_word"`;
- `latched_origin.py:637` and `cohort_provenance_correction.py:1954` `"tier2_evidence_refused"`;
- `frozen_value_evidence.py:627-629/:648` segment-kind literals.

Each reads correctly for every current member, by READ. None is a stale mirror. They are the shape the 22-A twelfth-site lesson warns a value-set sweep does not find; they are named here so the next widening greps them.

---

## (iii) The live-copy evidence (cited, not re-run)

Source: the exec ledger's gate-table row **G-T11** (exec cell 11, commit `9a1f6638`). Quoted verbatim from that row:

> **LIVE-COPY EVIDENCE (plan Task 11; not committed):** `sqlite3.backup()` of live from a `mode=ro` source into the session scratchpad (1,656,672,256 bytes, v38, `integrity_check` ok, 28 trades, 1 provenance row); `db-migrate` ON THE COPY under a scratch config (all nine `[paths]` in the scratchpad, `USERPROFILE`/`HOME` scratch; resolver proof `swing.__file__` = the worktree, `EXPECTED_SCHEMA_VERSION` 39) -> v39, `integrity_check` ok, **ONE backup written (the gate image `swing-pre-22a2-migration-20260923T053644Z.db`), echoed** -- nothing written outside the scratchpad (9,672-file before/after snapshot of `~/swing-data`). Dry run `journal correct-cohort-provenance 25 --cited-candidate 12284 --cited-recommendation 169 ... --frozen-value-evidence <9f315cc6 / docs/rd-state.md / line 57> --dry-run` with `EVIDENCE_REPO_DIR` = the real repo: exit 0, **ADMIT**, criteria 1-4 PASS (ancestor of `refs/remotes/origin/main` @ `a4ac72ee`), tier `latch_ladder_tier2`, interval writer_absence_only 2.38 d + match_only 22.89 d, fields `hypothesis_label` None -> 'A+ baseline (aplus)', `candidate_id` None -> 12284, `trade_origin` 'manual_off_pipeline' -> 'pipeline_aplus'. Live `swing.db` size/mtime_ns `1656672256` / `1790135382505575400` IDENTICAL before and after (orchestrator re-stat after the return: identical); only `-shm`'s mtime moved, at the cell's own `mode=ro` open (the documented behaviour).

The same row's notes to Task 12, verbatim:

> **Notes to Task 12:** (a) one backup, echoed -- confirms the CLAUDE.md TWO-backups gotcha stale; (b) `PENDING` empty; (c) OUT OF ARC, routed to CHARC fyi: live `PRAGMA foreign_key_check` returns `reconciliation_discrepancies` rows 72 and 73 -> `cash_movements` (orchestrator re-read `mode=ro`: both carry `cash_movement_id = 5`; `cash_movements` has no id 5; the FK is `ON DELETE SET NULL`, so the parent was deleted with FKs off) -- identical in the v38 image, not 0039's; (d) at the witness `EVIDENCE_REPO_DIR` defaults to main's root, no override; (e) the citation-trigger abort escapes as raw `sqlite3.IntegrityError` (authorize-then-abort; recorded, not asked); (f) 3 ruff F811 in the new test file, same pattern as its siblings; `swing/` clean. NOT resumed.

**FK note (c), since dispositioned by CHARC.** Rows 72/73 are the D19 duplicate delete of `cash_movements` id 5 on 2026-06-20, made on a plain connection with foreign keys off. They are to be NULLed under the witness if the operator agrees, and a `foreign_key_check` probe is banked post-merge. Source: `comms/orchestrator/read/20260923T054426Z-charc-charc-fk-orphan-72-73-d19-dupe-delete-06.md` (cited only; the cell took no action on it).

---

## (iv) CLAUDE.md side-flag -- FLAGGED, not edited here

The CLAUDE.md gotcha **"`swing db-migrate` writes TWO backups, not one"** (section SQLite / transactions / migrations / schema) is STALE against the code. At this head `swing/cli.py:284-289` reads: "ONE backup per migration (D32/D50 F2, operator-ruled branch (b)). A gate in swing.data.db covers the transition -> the gate writes its named, integrity-verified image into backups_dir and the CLI takes NO copy." The CLI's own `swing-<ts>.db` snapshot (`:298-331`) is written only when `backup_gate_for_pre_version(pre_version)` is None. The gate's image path is ECHOED (`:359`, "Backup (pre-migration gate, integrity-verified): ..."). G-T11 measured exactly this on the live copy: ONE backup (`swing-pre-22a2-migration-20260923T053644Z.db`), echoed, and nothing written outside the scratchpad (G-T11 note (a)). CLAUDE.md is not edited by this arc; the correction belongs to whoever owns the gotcha text.

---

## Deviations recorded for Reviewer B (each with where it is recorded)

1. **Task 5 tests written AFTER the implementation**, with no red-first run. Cell 2 substituted ten one-line mutations, each failing exactly its targeted discriminator. RD accepted this as a substitute for THAT task, NOT as TDD. Recorded in the exec ledger's G-T5 record and the note under RULING F2.I-NEG.
2. **G-T7FE: one test written post-implementation** (`..._a_moved_version_is_on_every_stale_reason_line`), pinning the cell's reading 3 and checked by mutation. RD accepted it for THIS pin on the strength of its mutation check. Recorded in the RULING G-T7FE-B header and the G-T7FE row.
3. **G-T9F: six pins on existing behaviour passed on first run** (NOT faked red). Each was proved by mutation M1-M5 (`_mismatch`-only suffix, always-append, append-on-unverifiable, resolve-under-caller-tx, module-level cache), each reverted `cmp` byte-identical. Recorded in the G-T9F row.
4. **Task 11: the 11 roster tests passed on first run** on Tasks 3-10's shipped code (NOT faked red). Each was proved by mutation M1-M8, restored and sha256-verified. Recorded in the G-T11 row.
5. **Task 10: post-code tests** -- the `/hyp-recs/refresh` rows (found by M6; checked by M6/M3/M4) -- and four A2-08 renames/splits with bodies unchanged. Recorded in the G-T10 (done) row.
6. **G-T7F: the tip was reworded by the orchestrator.** The cell committed `889e5e72`, whose body began `Q1:` and was parsed as a trailer. A message-only amend produced `ee157a28`; tree `dfbdd5e7` is byte-identical. `889e5e72` is unreachable and must never be cited. Recorded in the G-T7F row.
7. **Task 3: the 0039 SQL was composed by an UNCOMMITTED scratch generator**, working from the stored v38 DDL and the verbatim 0036/0037 statement texts. The generated SQL is the reviewed artifact. Recorded in G1 note 5 and the G1 record.
8. **G-F4: the status test was renamed** to `test_hypothesis_status_renders_the_named_lines_and_no_marker` in the same red-first commit (`3b696fcc`). The old name asserted the behaviour the ruling removes. Recorded in the G-F4 row.
9. **Task 12 (a): a retirement with no red path.** Removing `PENDING` changes no passing behaviour. It was proved by an in-process mutation: adding an unimplemented `A2-105` to `CASES_22A2` turns A2-08 red (`A2-105: 0 implementing tests []`), so no skip path masks an unlanded id. Commit `ef851af2`.

---

## (v) Every gate's report, VERBATIM (the "notes carried to Task 12's record")

**Method.** A scratch script (session scratchpad, `extract_gates.py`) loaded each subagent transcript line by line. From the assistant messages it kept the `SubagentHandback` tool-use payloads, where each cell delivered its gate report as `input.message`. It wrote each one out unedited. No transcript was read whole.

All eleven named transcripts were present. Every gate in the exec ledger's table has a report, and no gate report was missing: 17 reports across 12 cells, with cells 2, 3, 4, 6 and 10 gating twice. Cell 4's two gates are the G-U1 fork stop and G-U1 done; the ledger lists both as G-U1 rows. G-F4's report is cell 12's own, taken from its own transcript.

Each report below is reproduced byte-for-byte. The `> ` prefix on each line is the transcriber's and is the ONLY added byte. The ledger's "notes carried to Task 12" are inside these reports:
- cell 1, G1 note 4 (P34) and notes 1-5;
- cell 3, G-T6 "Encodings 1-5";
- cell 4, G-U1 "encodings 1-3";
- cell 5, G-T7 "notes 1-9";
- cell 6, G-T8 "notes 1-7";
- cell 10, G-T10's notes;
- cell 11, G-T11 notes (a)-(f).

| gate | cell | transcript (`C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/...`) | handback timestamp |
|---|---|---|---|
| G1 | 1 | `.../7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-a421d96371fe3d363.jsonl` | 2026-09-23T01:20:24.822Z |
| G-T4 | 2 | `.../7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-adcbedd74a5bd3669.jsonl` | 2026-09-23T01:28:31.324Z |
| G-T5 | 2 | `.../7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-adcbedd74a5bd3669.jsonl` | 2026-09-23T01:38:50.662Z |
| G-T6 | 3 | `.../7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-a9b1c2cfbbaee3611.jsonl` | 2026-09-23T01:51:54.028Z |
| G-NEG | 3 | `.../7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-a9b1c2cfbbaee3611.jsonl` | 2026-09-23T01:53:22.832Z |
| G-U1 (fork stop) | 4 | `.../7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-ac0c0d9e79dd8330b.jsonl` | 2026-09-23T01:58:42.074Z |
| G-U1 (done) | 4 | `.../7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-ac0c0d9e79dd8330b.jsonl` | 2026-09-23T02:13:23.509Z |
| G-T7 | 5 | `.../4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-ab8261314c6f42e9b.jsonl` | 2026-09-23T02:42:59.258Z |
| G-T8 | 6 | `.../4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-a856643950e9089c7.jsonl` | 2026-09-23T02:56:59.930Z |
| G-T7F | 6 | `.../4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-a856643950e9089c7.jsonl` | 2026-09-23T03:09:47.351Z |
| G-T9 | 7 | `.../4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-a4e61db52e508b458.jsonl` | 2026-09-23T03:29:11.555Z |
| G-T7FE | 8 | `.../4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-ab73d967f8ca03ff8.jsonl` | 2026-09-23T03:56:33.933Z |
| G-T9F | 9 | `.../4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-a4290dedf741ec2e4.jsonl` | 2026-09-23T04:20:04.525Z |
| G-T10 (fork stop) | 10 | `.../0492607f-f8bc-42a1-a1f6-6b52b831c884/subagents/agent-ab728b5c18d19e905.jsonl` | 2026-09-23T04:29:35.532Z |
| G-T10 (done) | 10 | `.../0492607f-f8bc-42a1-a1f6-6b52b831c884/subagents/agent-ab728b5c18d19e905.jsonl` | 2026-09-23T05:14:56.008Z |
| G-T11 | 11 | `.../0492607f-f8bc-42a1-a1f6-6b52b831c884/subagents/agent-a518eefad1996d4d5.jsonl` | 2026-09-23T05:39:34.552Z |
| G-F4 | 12 | `.../0492607f-f8bc-42a1-a1f6-6b52b831c884/subagents/agent-afb3dbd7827207768.jsonl` | 2026-09-23T05:48:44.189Z |

### G1 -- exec cell 1

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-a421d96371fe3d363.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T01:20:24.822Z.

> GATE G1 (after Task 3) -- 22-A2 executing cell, worktree C:/Users/rwsmy/swing-trading/.worktrees/22-a2-exec (branch 22-a2-exec)
>
> Last commit: 010e8f9f. Trailers are empty on all four branch commits (checked with `git log -1 --format='%(trailers)'` after each one).
>
> Commits so far:
> - 84f63a63 docs(plan): R4.0 edits applied by replacement. Covers CHARC rulings 1-3 (WEB_REPLAY_BUDGET_SECONDS=2.0 plus the budget_seconds semantics, A2-97b/A2-97c, A2-94 no-subprocess, A2-75 now three caller sets, section 9 OPERATOR-EXECUTED ORCHESTRATOR-SCRIPTED) and RD corrections 1-2 plus the Task 11 note. The ledger's E-13 and AL2-10 text was replaced, and E-16 now points at the widened A2-75.
> - 37bd7929 test(data): Task 1. The (t1) barrier-drop scan, A2-01..07. A mutation check that disables the scan turns A2-01/02/03/06 red.
> - a045835b test(trades): Task 2. The registry, the two-direction closure (A2-08), and the six-case byte pin (A2-09). The pin covers 13 functions: cases 1, 2, 3, 4, 5a, 5b, 6 plus 1-pre, 5b-pre, 6-pre. A one-comment edit to one of them turns A2-09 red.
> - 010e8f9f feat(data): Task 3. Migration 0039 plus every #11 mirror, in ONE commit. A2-10..A2-31 green (A2-22 sits in test_backup_gate_table.py).
>
> 0039 manifest delta: `scripts/schema_manifest.py --db` on a fresh v38 image reports exactly 3 changed objects and no missing or unexpected ones. On the v38 image migrated to v39 it reads clean. The committed fixture diff is exactly four changed line pairs with zero deletions, and it is quoted in the 010e8f9f commit body:
>   # schema_version 38 -> 39
>   table provenance_corrections 17540224... -> c82dc450...
>   trigger trg_provenance_corrections_append_only_update 1fc87a83... -> 41eab096...
>   trigger trg_provenance_corrections_citation_graph 0d75e644... -> 38689302...
>
> Suite: not the full fast suite yet; that comes at G3. I ran tests/data + tests/trades + tests/cli at -n 8: 5003 passed, 1 failed. The failure was the HEAD-tracking nullable-column roster in test_migration_0036 (the seventh column needed adding); it is fixed and re-run green. The 22-A mutation matrix (test_22a_task11_citation_evidence.py) passes against the HEAD 0039 trigger unchanged. That is the byte-unchanged-semantics evidence for the latch_ladder arm. ruff check swing/: clean.
>
> Plan-vs-implementation notes (none re-opens a ruling):
> 1. I created swing/trades/frozen_value_evidence.py in Task 3, holding only FROZEN_VALUE_EVIDENCE_VERSION. A2-25's drift test needs it in the SAME commit as the trigger literal (#11). LATCH_PROBE_TIER2_EVIDENCE_VERSION and AUTHORIZATION_VERDICTS landed in latched_origin in Task 3 for the same reason.
> 2. `-- TIER2-PREDICATE` markers also sit on the four rung-9 tier-2 predicates, not only on the seventh-column block (F11: "every predicate of both branches"). Their service checks live in latched_origin, so A2-60 (Task 5) will resolve each id in its own module.
> 3. A2-28 gained one mutation, ticker_AMN_in_text. OIS is refused by containment and the binding together; AMN, which appears in line 57, isolates the ticker binding. Spot-checks against a migration with the predicate neutralized confirm the discriminators for ticker/AMN, author_date, rung-9 verdict and live_pivot_raw.
> 4. P34 classification, to be recorded in the ledger at Task 12:
>    - (i) re-pointed to the HEAD definition: test_22a_al3_closure (walks plus anchor also checked in HEAD), test_22a_authorize_then_abort_closure, test_22a_task2_migration_0037's closure-list test, test_22a_task3_epoch_reader (epoch-read sites plus the probe-version pin, now both constants).
>    - (ii) kept on 0037's own text: test_22a_canonicalizer_version_closure (the FEI table, its anchor and ships-empty live in 0037), test_22a_envelope_canonicality_sweep's 0037 test (the whole-tree sweep covers 0039), test_22a_task11 round-gate, test_22a_task2's no-rounding gate. Plus a new HEAD pin in the 0039 test file: FEI-CONSUMER markers are unchanged in the HEAD citation trigger.
>    - The old test_an_unknown_admission_tier_is_rejected now uses latch_ladder_tier3 and matches the enum message.
> 5. The 0039 file was composed by a scratch generator from the stored v38 DDL and the verbatim 0036/0037 statement texts. It is not committed; the generated SQL is what is reviewed.
>
> Next: Task 4 (git preflight). Code and tests are drafted in the session scratchpad; tests go in first.

### G-T4 -- exec cell 2

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-adcbedd74a5bd3669.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T01:28:31.324Z.

> GATE G-T4 (22-A2 exec cell 2): Task 4 is done.
>
> **Last commit:** `cd02374b`, branch `22-a2-exec`, worktree `C:/Users/rwsmy/swing-trading/.worktrees/22-a2-exec`. Trailers are empty on both commits.
> - `10c424de` feat(trades): Task 4 -- the frozen_value_evidence git preflight (A2-32..A2-41)
> - `cd02374b` style(trades): Task 4 -- rewrote the duplicate-key fixture to drop percent formatting (ruff UP031 in the test file)
>
> **Built:**
> - `swing/trades/frozen_value_evidence.py` holds the preflight half of the module:
>   - constants `GIT_TIMEOUT_SECONDS`, `REMOTE_REF`, `EVIDENCE_REPO_DIR`, `EVIDENCE_FILE_KEYS`, the five failure names and `PREFLIGHT_FUNCTIONS`
>   - the dataclasses `EvidenceSelection`, `ArtifactFacts` and `PreflightResult`
>   - the functions `load_evidence_selection`, `read_artifact_facts` and `run_preflight`
> - Git runs as bytes in, bytes out: no `text=`/`encoding=`, `timeout=GIT_TIMEOUT_SECONDS`, `cwd=repo_dir`.
> - The call order is: rev-parse `REMOTE_REF^{commit}` → `show -s %aI%n%cI sha^{commit}` → `cat-file blob sha:path` → byte-substring check → one-line check → `merge-base --is-ancestor` → `rev-list --count` (only when it is an ancestor) → `log -g -1 --date=iso-strict --format=%gD REMOTE_REF`.
> - Failure mapping:
>   - A process failure is `tier2_unverifiable`: a timeout, git not found, no ref, a merge-base exit other than 0/1, or any unexpected exception.
>   - A missing commit or path is `artifact_unreadable`.
>   - The preflight never raises (E-6).
> - New helper `tests/trades/_git_world.py`: a work repo plus a bare remote, with pinned author and committer dates; `push`, `grow_remote(n)` and `rewrite_remote_dropping(sha)`. The push date also pins the reflog instant.
> - New test file `tests/trades/test_22a2_frozen_value_preflight.py`. The registry's PENDING list now excludes A2-32..A2-41.
>
> **Tests:**
> - I saw the new tests fail first (AttributeError on the missing API).
> - `tests/trades/test_22a2_frozen_value_preflight.py` + `test_22a2_case_closure.py`: 128 passed (20 in the preflight file). The A2-08 closure is green with Task 4's ids live.
> - `ruff check swing/`: clean. Both new test files: clean.
> - The full fast suite has not run yet; that is due at G3.
>
> **Plan vs implementation:**
> 1. **Premise error in the plan (section 4) and ledger R1.0:** they say line 57 is "1006 chars". Measured from the fixture and from `git show 9f315cc6:docs/rd-state.md` directly, it is 1015 bytes and **1005 chars** (five 3-byte em-dashes). The sha256 and every token offset match the pin; only the char count is wrong. A2-37 asserts the measured 1005.
> 2. The artifact is read with `git cat-file blob sha:path`, not `git show sha:path`. For a blob the bytes are identical; cat-file also refuses a tree path and never applies textconv. The commit check reads the dates via `sha^{commit}`, so a tree or blob sha reads `artifact_unreadable`.
> 3. When the ref has no reflog, `git log -g` exits 0 with empty output (measured). That is how "reflog absent → null" is detected; no `reflog exists` call is needed.
> 4. `load_evidence_selection` returns `EvidenceSelection | PreflightResult` (a failed result).
> 5. A naive `now_utc` fails closed as `tier2_unverifiable`.
>
> **Next:** Task 5 (conjunction evaluation, the blob builder, the predicate roster; reads the DB only).

### G-T5 -- exec cell 2

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-adcbedd74a5bd3669.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T01:38:50.662Z.

> GATE G-T5 (22-A2 exec cell 2): Task 5 is done.
>
> **Last commit:** `503e27b2`, on top of your ledger commit `4f0f64d7`. Trailers are empty.
> - `503e27b2` feat(trades): Task 5 -- the four-part conjunction, the seventh-column blob builder and the TIER2-PREDICATE service-check roster (A2-42..A2-60)
>
> **Built** (all in `swing/trades/frozen_value_evidence.py`; it only runs SELECTs):
> - **Helpers:** `render_price` (Python half-even at 2 dp) and `find_token` (ticker bounded by non-`[A-Za-z0-9]`; session and numeral bounded by non-`[0-9.]`).
> - **`build_interval`:** the five endpoints (raw, utc, clock_domain, source) and the four segments in order. Fire times convert through `cohort_provenance_correction._to_utc_naive`, imported at call time to avoid an import cycle. `render_uncovered_window_prose` renders the prose.
> - **`evaluate_conjunction(conn, facts, *, candidate_id, fill_session, read_at, barrier_installed) -> ConjunctionVerdict`:**
>   - Reads the candidate joined to its `evaluation_runs` row, the run's one complete `pipeline_runs` row via `evaluation_run_persistence_bound`, and the epoch row.
>   - Criteria run in order 1 → 2 (ET date of the author instant) → 3 (ticker → action_session → pivot → invalidation, with the F13 year rule) → 4 (a record before `fire_lo` is `window_negative`; inside `[fire_lo, fire_hi)` it is `window_indeterminate`).
>   - Criterion 3 puts the failing field name in both `reason` and `field`.
> - **The blob:** built with its closed 28-key roster. The constant texts are byte-equal to the fixture cell 1 hand-built.
> - **Authorize-then-abort:**
>   - A mirror function `_tp_<id>` exists for each of the 25 blob predicates and runs on the built blob.
>   - If a mirror fails, the service refuses legibly: `criterion=None`, `reason='tier2_unverifiable'`, `field=<predicate id>`. The row never reaches a raw trigger abort.
>   - `TIER2_TRIGGER_PREDICATES` holds 28 `(id, "module:check")` pairs.
> - `VERDICT_BEARING_KEYS` is stored as dotted paths.
>
> **Tests:**
> - The Task 5 tests were written after the implementation, so there was no red-first run. As a substitute, I ran ten one-line mutations of the module, one per discriminator, and each failed exactly its targeted test:
>   - A2-50: SQLite-style half-up rounding
>   - A2-45: a `<=` implementation
>   - A2-46: the local-offset date
>   - A2-48: the committer date
>   - A2-52: substring matching for the ticker
>   - A2-55: no year rule
>   - A2-56: the year rule applied to the ISO form
>   - A2-57: no fire bracket
>   - A2-44: no ancestry check
>   - A2-49: no pivot check
> - `tests/trades/test_22a2_conjunction.py` + closure + preflight: 147 passed.
> - `test_migration_0039_*` + `test_22a_authorize_then_abort_closure.py` + conjunction: 96 passed.
> - A2-42 inserts the builder's blob as a raw INSERT on the real pre-barrier world, and the HEAD citation trigger admits it.
> - A2-43's interval and prose equal the fixture literal exactly: 545, 205,346 and 1,977,720 s, "2.38 days", "22.89 days".
> - `ruff check swing/` is clean, and so is the test file.
> - The PENDING list now excludes A2-01..A2-60.
>
> **Plan vs implementation (encodings for Task 12's record):**
> 1. **A2-60 and the rung-9 predicates.**
>    - The HEAD trigger carries 28 markers.
>    - Three of them map to where rung 9 lives: `rung9_escaped_verdict` → `latched_origin:_authorization_block`, `rung9_pre_barrier_input` → `latched_origin:authorize_accepted_order`, `rung9_pre_barrier_candidate` → `candidates_immutability_epoch:freeze_tier_for_candidate`.
>    - `seventh_present` is a blob mirror.
>    - A2-60 asserts the id set both ways, that each check resolves, and that each is reachable. For `frozen_value_evidence` checks that means name-reference reachability from `evaluate_conjunction`, walked transitively through module defs and assignments, so the `_BLOB_MIRRORS` tuple counts. The plan said an "AST call walk"; I walk name references instead. For `latched_origin` checks it means reachability from `authorize_accepted_order`; the epoch function must be called in `latched_origin`.
>    - At Task 5 the rung-9 checks are only proved to exist and be reached. Task 6's A2-61..66 prove their behaviour.
> 2. **A mirror failure is an extra refusal class.** It returns `tier2_unverifiable` naming the predicate; the plan's vocabulary lists this reason only for process failures. An absent epoch row, or an unparseable endpoint while the blob is being built, gives `field="blob_unbuildable"`. An unresolvable fire bracket is criterion 4 `window_indeterminate`.
> 3. **UTC rendering.** Aware instants render as `isoformat()` of naive UTC plus "Z". `read_at.utc` is the raw value plus "Z", matching the literal.
> 4. A2-42 compares the builder and the literal on `VERDICT_BEARING_KEYS` plus the constants. Segments and prose depend on the world's epoch time, so they are covered by A2-43 on live values instead.
>
> **Open item, for your routing:**
> - The `match_only` segment is `[record_at, barrier_armed_at)`. A record authored after the barrier was armed, which is possible for a long-latched pre-barrier mandate, gives negative seconds. The plan does not address this case.
> - Trade 25 is unaffected.
> - I compute it literally. Options: clamp to zero, emit a distinct kind, or refuse. This belongs to RD, since F2.I is his ruling.
>
> **For Task 7:** the correction service keeps a dependency manifest that names `_to_utc_naive` (`cohort_provenance_correction.py:258/287`). When the service starts importing this module, that closure may need a line.
>
> **Next:** Task 6, the rung-9 escape seam in `latched_origin.py`.

### G-T6 -- exec cell 3

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-a9b1c2cfbbaee3611.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T01:51:54.028Z.

> GATE G-T6 -- exec cell 3, Task 6 done. Last commit: aa2d44eb (branch 22-a2-exec, worktree C:/Users/rwsmy/swing-trading/.worktrees/22-a2-exec). Trailers are empty (`git log -1 --format='%(trailers)'` printed only a newline).
>
> **What was done (Task 6: the rung-9 escape seam)**
> - `swing/trades/frozen_value_evidence.py`: added `Tier2Request(preflight: PreflightResult, applied_at: str)`.
> - `swing/trades/latched_origin.py`:
>   - A keyword-only `tier2: Tier2Request | None = None` on both `resolve_latched_provenance` and `authorize_accepted_order`, passed through unchanged.
>   - Rung 9: the barrier check is still first and unchanged. Then:
>     - Both tiers `live_at_acceptance`: the existing path. If `tier2` is supplied, it refuses `tier2_evidence_refused` with `no_escape_to_take` (encoding 3).
>     - Both tiers `pre_barrier_reconstructed` and `tier2` supplied: a new helper `_rung9_tier2_escape` decides. If the conjunction admits, the escape continues to the guards and the probe unchanged. If not, it refuses with a detail.
>     - Anything else: `pre_barrier_unproven` exactly as before (encoding 2).
>   - `_rung9_tier2_escape` is the only caller of `fve.evaluate_conjunction`. It calls through the module attribute, so A2-75's walk must match attribute calls.
>   - `_authorization_block(inputs, verdicts=None)`: an override is checked against the roster keys and `AUTHORIZATION_VERDICTS`. When the escape is taken, rung 9 records `{"input": "pre_barrier_reconstructed", "verdict": "escaped_by_tier2"}` and the probe blob's `evidence_version` becomes `LATCH_PROBE_TIER2_EVIDENCE_VERSION`.
>   - `LatchedProvenance` gains `frozen_value_evidence` and `tier2_refusal` (both default None), with validators: `tier2_refusal` is only allowed on a `tier2_evidence_refused` decline, and the blob only on an admission.
>   - `DECLINE_REASONS` goes from 36 to 37 (`tier2_evidence_refused`).
> - Tests:
>   - New `tests/trades/test_22a2_rung9_escape.py`: A2-61..A2-66 plus four legibility tests without roster ids (criterion-3 and criterion-1 refusal details, a failed preflight's detail, a raising conjunction contained as a refusal) and a roster-size pin.
>   - `tests/_tier2_world_22a2.py` gains `T25_CLOSES` and `t25_cfg`.
>   - `case_registry_22a2.PENDING` now covers ids from A2-67 on.
>   - `test_22a_task8_resolver.py` roster-size test changed from 36 to 37.
>
> **Red, then green**
> - Red first: I wrote the test file and ran it before any implementation. All 10 failed for the expected reasons:
>   - `AttributeError: ... has no attribute 'Tier2Request'`
>   - `TypeError: resolve_latched_provenance() got an unexpected keyword argument 'tier2'`
>   - A2-65: the `tier2` parameter did not exist (`assert None is not None`). A2-65 pins that the parameter exists as well as that entry.py does not pass it, so it cannot pass on a module that never added the keyword.
>   - The roster did not contain `tier2_evidence_refused`.
> - First partial green: 8 passed, 2 failed. A2-61 and A2-63's control failed with `aliveness_unverifiable`: candidate 12284 carries the full criterion roster, so the latch derivation needs `cfg.trend_template`. The fixture is fixed with production's values, the same form 22-A task 11's CADL fixture uses. This was a fixture problem, not a code change.
> - Final: 10/10 green.
> - A2-61 also inserts the escape's real probe blob and the service-built seventh-column blob, raw, on the production service's base row for trade 25. The HEAD 0039 citation trigger admitted it (`latch_ladder_tier2`, then rolled back). So what rung 9 emits matches what the trigger checks.
>
> **Suites**
> - `pytest tests/trades tests/data tests/cli -n 8`: 5054 passed, 9 skipped, 0 failed. This includes A2-09 (the six 22-A case functions are still byte-identical by hash), the 22-A decline-roster closure both ways, AL-3 and A2-60.
> - `ruff check swing/`: all checks passed.
> - The full fast suite has not run yet; it is scheduled for G3.
>
> **Plan vs ruling / encodings to record for Task 12**
> 1. Refusal detail format. Plan says "detail = that failure" and "`criterion N: <reason/field>`". Encoded as:
>    - A failed preflight: `"<failure>: <detail>"`, or just `<failure>` when the detail is empty.
>    - A conjunction refusal: `"criterion N: <field or reason>"`, e.g. `criterion 3: pivot`.
>    - A blob mirror failing (criterion None): `"tier2_unverifiable: <predicate>"`.
>    - A conjunction that raises: `"tier2_unverifiable: <ExcType>: <msg>"`, logged. This is an added encoding: without it, the broad handler in `resolve_latched_provenance` would return `aliveness_unverifiable` and hide which input failed. Both outcomes are fail-closed.
> 2. The `tier2_refusal` validator is one-directional. The 22-A task 8/9 tests build every roster reason bare, so the detail cannot be required by the validator; rung 9 always supplies it.
> 3. The trade-25 probe-window closes (2026-08-10..08-14, between the stop and the pivot) are SYNTHETIC and declared as such in the test and fixture docstrings. The live OII bars belong to Task 11.
> 4. A2-64's reverse direction and A2-66 reuse 22-A's FTRE post-barrier world (helpers imported from `test_22a_task9_entry_wiring`, none of them the pinned case functions). The disagreement is forged through the dataclass (`dataclasses.replace` on `freeze_tier`), which is 22-A's own `_forged_link` technique.
> 5. The open match_only question (RD) is untouched.
>
> **Next:** Task 7, wiring the correction service in `cohort_provenance_correction.py`, A2-67..A2-76. The `_to_utc_naive` dependency-manifest note from the ledger applies there.

### G-NEG -- exec cell 3

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-a9b1c2cfbbaee3611.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T01:53:22.832Z.

> GATE G-NEG: STOPPED before writing anything, as instructed. F2.I-NEG requires changing the 0039 trigger text. Nothing was committed and the worktree is clean. HEAD is still 392b106f, your docs commit.
>
> **Why I stopped (measured by running a probe, not read off the SQL)**
>
> The 0039 citation trigger currently has two predicates that fix the old shape:
>
> - **`interval_segment_order`** (0039 ~:2105-2114) requires
>   - `json_array_length($.interval.segments) = 4`,
>   - `segments[2].kind = 'match_only'`,
>   - and segments 0, 1 and 3 fixed as `fire`, `writer_absence_only`, and `covered`/`uncovered_barrier_absent`.
>   - So consequence (i), "match_only OPTIONAL", cannot be admitted.
> - **`interval_closed`** (~:2037-2041) closes `$.interval` to exactly `endpoints` and `segments`. Separately, `blob_closed` closes the top-level blob to the 28-key roster.
>   - So consequence (iii)'s `record_position` has nowhere legal to live, inside `interval` or at the top level.
>
> The probe raw-inserted the truthful trade-25 tier-2 payload (the `truthful_tier2_payload` fixture) with one mutation each:
>
> | mutation | result |
> |---|---|
> | none (control) | ADMITTED |
> | 3 segments, `match_only` dropped (the `inside_coverage` shape RD rules) | REFUSED |
> | `record_position` added inside `interval` | REFUSED |
> | `record_position` added at the top level | REFUSED |
>
> Every refusal was IntegrityError "the cited rows exist but do not form the citation graph".
>
> The Python mirrors `_tp_interval_segment_order` and `_tp_interval_closed` apply the same rule. So a Python-only change would not abort a write. The service would instead refuse `tier2_unverifiable: interval_segment_order` on exactly the stronger evidence RD says to admit. That is the outcome his ruling rejects as (c), reached by accident. Trade 25 itself (`before_barrier`, 4 segments) would stay admissible either way.
>
> **The fork: routed to CHARC (schema shape) and the orchestrator**
>
> - **Option A (recommended): amend 0039 in the branch.** 0039 is unmerged and unapplied, so this is an edit to the migration file, not a new migration.
>   - `interval_segment_order` becomes the canonical order with `match_only` optional: length 3 or 4; `[0]='fire'`, `[1]='writer_absence_only'`; then either `[2]='match_only'` plus `[3]` in the covered pair, or `[2]` in the covered pair when the length is 3.
>   - `interval_closed` admits one more key, `record_position`, typed `IN ('before_barrier','inside_coverage')`.
>   - The presence rule (`match_only` present iff record_at.utc < barrier_armed_at.utc) stays a service check with its own `-- TIER2-PREDICATE` twin. Consequence (i) already anticipates this, since SQL binds raws only under R8-03.
>   - Cost: the D51 manifest delta stays four changed pairs, but the `citation_graph` hash changes again. The fixture must be regenerated in the same commit, and the 0039 migration tests plus A2-60's closure re-run. Mechanically this is a Task-3 edit, so it needs your authorization to reopen 0039.
> - **Option B: put `record_position` inside `interval` only, and relax only the segment predicate.** This is Option A with a narrower closure change. It is still a 0039 text edit, so it is not really a separate branch.
> - **Option C: defer the fix to a later arc.** Trade 25 is unaffected, but a record-after-barrier correction would refuse `tier2_unverifiable` until then. That contradicts RD's reason for rejecting (c). Not recommended.
>
> **Ready to run once authorized**
>
> - RD's three discriminators are specified, not yet written: barrier+1s, barrier-1s giving `match_only` 1 s, and equality giving no `match_only`.
> - On the Python side: `build_interval` with `writer_absence_only` END = `min(record_at, barrier_armed_at)`, a zero-or-negative segment never emitted, `record_position`, the inside-coverage prose form, and `VERDICT_BEARING_KEYS` gaining `record_position`.
> - Red-first as instructed. Trade 25 / A2-43 stay as they are: 22.89 d, `before_barrier`.
>
> **Question 1 for you:** does the reopen fold into the `fix(trades): Task 5 follow-on -- F2.I-NEG` commit, or go as its own `fix(data): Task 3 follow-on` commit before it? The fixture regeneration has to ride with whichever commit changes the 0039 text.
>
> **Question 2 for you:** should `record_position` sit inside `interval` (my lean: RD says "record_at stays in the endpoints with a recorded record_position", which reads as interval-local), or at the top level? At the top level the section-2 roster grows from 28 to 29 keys and A2-42 moves with it.
>
> Tests run for this gate: the probe above only. No suite ran and no code changed.

### G-U1 (fork stop) -- exec cell 4

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-ac0c0d9e79dd8330b.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T01:58:42.074Z.

> GATE REPORT, cell 4, unit 1: STOPPED ON A DESIGN FORK before writing anything. Nothing is committed and the worktree is clean at 758e1103.
>
> **The fork: the two landed rulings, applied together, refuse a case that A2-57 and F6(ii) admit.**
> - **RD's rule (F2.I-NEG):** "a segment of zero or negative length is NOT EMITTED; every emitted segment has seconds > 0". It is a general rule, and it covers writer_absence_only as well as match_only.
> - **CHARC's shape (G-NEG):** `[1] = 'writer_absence_only'` always. Only match_only is optional (length 3 or 4). The length-keyed belt then ties `record_position` to length.
> - **Where they collide:** criterion 4 admits `record_at >= fire_hi` (F6(ii)). A2-57 pins the boundary: record = fire_hi (`2026-08-07T17:39:07-10:00`) must ADMIT. At that point writer_absence_only = [fire_hi, min(record_at, barrier)) is exactly 0 s. The current code emits it with `seconds: 0`, which is why A2-57 passes today.
> - **What happens if I encode both rulings literally:** writer_absence_only is dropped, so segments are [fire, match_only, covered]. CHARC's order predicate then refuses it ([1] is not writer_absence_only; at length 3, [2] must be covered). The mirror refuses it the same way, as `tier2_unverifiable interval_segment_order`. A2-57's at_hi flips from ADMIT to refusal. I cannot write this as a green commit without resolving the fork.
>
> **Measured facts for the ruler:**
> - **The equality is order-indeterminate at the one-second grain.** `pipeline_runs.finished_ts` is written by `swing/pipeline/lease.py:38-39` `_now_iso()` = `datetime.now().isoformat(timespec="seconds")`, which truncates. The live DB (read-only) confirms the grain: 152/152 complete runs have a 19-char `finished_ts`. A git author instant is also whole seconds. So equal seconds do not prove the record came after the true fire end: the record could be 17:39:07.2 and the finish 17:39:07.9.
> - **Only this boundary produces a zero or negative writer_absence_only live.** Its end is `min(record_at, barrier)`, so it can also go non-positive if a fire ended at or after the barrier. Live: for all 138 complete pipeline runs that have a candidate with id <= `max_candidate_id_at_barrier` (13591), fire_hi < barrier_armed_at (`2026-09-02T10:03:33Z`); zero exceptions. I computed this by converting each run's `finished_ts` to UTC with `_to_utc_naive` and comparing it to the epoch row.
> - **Trade 25 is unaffected under every option below:** 205,346 s / 1,977,720 s, before_barrier, 4 segments.
>
> **Options:**
> - **(a) Tighten criterion 4 to strict `record_at > fire_hi`.** A record at the same second as `finished_ts` refuses as `window_indeterminate`.
>   - The one-second truncation above makes equality genuinely indeterminate, so the refusal names a real uncertainty; it does not refuse better evidence.
>   - Both rulings stay literal and CHARC's SQL shape is unchanged.
>   - Cost: A2-57's at_hi assertion flips to REFUSE, and the plan's criterion-4 wording and `fire_lo <= record_at < fire_hi` bracket become `<= fire_hi`.
>   - Ruler: **RD** (F6(ii) is his).
> - **(b) Make writer_absence_only optional in SQL as well.**
>   - Segments are then a canonical-order subsequence: [0] = fire, last in the covered pair, match_only and writer_absence_only each optional, length 2 to 4.
>   - The belt must be re-keyed from length to "match_only present".
>   - A2-57 stays ADMIT. This changes CHARC's ruled shape.
>   - Ruler: **CHARC**, with RD concurring.
> - **(c) Carve writer_absence_only out of the zero rule** and emit it with `seconds 0` when record == fire_hi. This contradicts RD's express reasoning against a zero-length segment ("a misstatement in the row's own voice"). Not recommended.
>
> **Recommendation: (a), PRIMARY ruler RD.** Once the grain is taken into account it is the sound reading of "at or after". It needs no SQL change beyond G-NEG as ruled, and it closes the zero-writer_absence_only case at the only place it is reachable live. A2-57's other three assertions (fire_hi - 1 s indeterminate, fire_lo indeterminate, fire_lo - 1 s negative) are unchanged; only at_hi flips.
>
> **Also in scope once the fork is ruled, noted now so it is not rediscovered:**
> - A2-60 hard-codes `len(sql_ids) == 28`. Adding `record_position_consistent` makes it 29, and the test is edited in the unit-1 commit.
> - I plan to put the presence IFF (match_only iff record_at.utc < barrier.utc) inside `_tp_interval_segment_order`'s service mirror, together with a seconds > 0 check on every segment. That makes it reachable under A2-60's existing id without a new marker, as RD's consequence (i) asks.
>
> On resume I execute unit 1 exactly as briefed, with the ruled option folded in, red-first.
>
> **Spend:** zero Codex rounds (none were due in this unit).

### G-U1 (done) -- exec cell 4

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/7fd2ec08-c083-42ad-b931-9eb52beff237/subagents/agent-ac0c0d9e79dd8330b.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T02:13:23.509Z.

> GATE G-U1, cell 4, unit 1: DONE. One commit, **d3bef313** `fix(data,trades): Tasks 3+5 follow-on -- F2.I-NEG (RD) + G-NEG (CHARC)`, on top of 01bb5193. Its trailers are empty (`git log -1 --format='%(trailers)'` printed only a newline), and the worktree is clean. Six files changed: 0039's SQL, `frozen_value_evidence.py`, the manifest fixture, the trade-25 seventh-blob literal, and the two test files. Task 7 was NOT started.
>
> **Red run** (tests written first; `tests/trades/test_22a2_conjunction.py` + `tests/data/test_migration_0039_provenance_corrections_tier2.py`, `-n 0`): 35 failed / 35 passed. The failures that matter, and why each failed:
> - **RD, record = barrier + 1 s:** the kind list did not match. The old code emitted a match_only segment of -1 s.
> - **RD, record == barrier:** `'match_only' not in [...]` failed; the old code emitted a 0-second match_only.
> - **RD, record = barrier - 1 s:** `KeyError: 'record_position'` (the key did not exist yet).
> - **End-to-end conjunction and the service-mirror discriminators:** KeyError / `'interval_closed' == 'interval_segment_order'`. The old closed interval rejected the new key.
> - **A2-57 at_hi:** `(True is False)`, meaning the old `>=` check admitted it.
> - **A2-60:** `28 == 29`.
> - **CHARC's belt test (both cases):** `assert 4 == 3` on the +1 s shape. On the -1 s shape, the truthful control was refused ("assert not True"), because old 0039 rejected `record_position`.
> - **A2-26 / A2-28 / A2-31 controls:** refused by the citation-graph trigger. The literal fixture now carries `record_position`, which old 0039 did not accept. This is the expected red.
>
> **Green run:**
> - The same two files after the change: 69 passed and 1 failed. The failure was A2-19 (the committed manifest fixture), which is stale until the fixture is regenerated.
> - After `python scripts/schema_manifest.py --write` (163 objects): **`tests/trades tests/data tests/cli -n 8`: 5062 passed, 9 skipped, 0 failed (305.59 s).** `ruff check swing/`: All checks passed.
> - Trade 25 is unchanged: A2-42 and A2-43 are green, with 205,346 s / 1,977,720 s, `before_barrier`, and 4 segments.
>
> **What changed:**
> - **0039 text** (edited in place; no new migration):
>   - `interval_segment_order`: the segment list is length 3 or 4. [0] = fire and [1] = writer_absence_only. At length 4, [2] = match_only and [3] is covered or uncovered_barrier_absent. At length 3, [2] is covered or uncovered_barrier_absent.
>   - `interval_closed`: `json_remove` now also strips `$.record_position`, and the key must be typed `'text'` and be `IN ('before_barrier','inside_coverage')`.
>   - New `-- TIER2-PREDICATE record_position_consistent`: `CASE json_array_length(...) WHEN 4 THEN rp = 'before_barrier' WHEN 3 THEN rp = 'inside_coverage' ELSE 0 END`.
>   - No OR was added, so any NULL collapses through the enclosing COALESCE to a refusal.
> - **Python:**
>   - `build_interval` ends writer_absence_only at min(record_at, barrier), drops any segment whose end is not after its start, and computes `record_position`.
>   - The prose gains the inside-coverage form, e.g. "...; covered from X; record authored inside coverage at <record_at utc>".
>   - `VERDICT_BEARING_KEYS` gains `interval.record_position`.
>   - `_tp_interval_closed` is widened to the extra key.
>   - `_tp_interval_segment_order` carries the order check, the presence IFF (via the utc text of the two endpoints) and seconds > 0 on every segment.
>   - New `_tp_record_position_consistent` is appended to `_BLOB_MIRRORS`.
>   - G-U1: criterion 4 now refuses `record_at <= fire_hi` as `window_indeterminate`.
> - **Tests added or changed:**
>   - RD's three discriminators, on `build_interval`, check the exact kind lists, seconds > 0, and writer_absence_only ending at the barrier (205,345 s). The +1 s case also checks the exact prose.
>   - The same three cases run end to end through `evaluate_conjunction`, with only the barrier moved by monkeypatching `_read_context`.
>   - Service-mirror discriminators, run on forged blobs:
>     - a match_only forged into an inside-coverage blob, with the belt satisfied, is refused by `interval_segment_order` (SQL cannot see this);
>     - a 0 s segment is refused by `interval_segment_order`;
>     - a forged position is refused by `record_position_consistent`;
>     - a bad or missing position is refused by `interval_closed`.
>   - CHARC's two cases on the raw-insert path, each run three ways:
>     - the truthful position is ADMITTED;
>     - the forged position ABORTS;
>     - the forged position is ACCEPTED once the belt clause is cut out of the trigger.
>   - A test that `interval_closed` admits exactly one more typed key.
>   - A2-57: at_hi now refuses as `window_indeterminate`, and the new fire_hi + 1 s twin admits with `writer_absence_only.seconds == 1`. The other three assertions are unchanged.
>   - A2-60's count is now 29.
>
> **Fixture delta**, `git diff 05702929 -- tests/data/schema_manifest_head.tsv`: exactly four changed pairs, zero deletions, zero additions.
> ```
> -# schema_version 38
> +# schema_version 39
> -table	provenance_corrections	...	175402245803b8bf9c9d75fefd609ccde58f8edaee844bddec4ff803b58c034f
> +table	provenance_corrections	...	c82dc45068fbc9cfb23264bef1cb8c976dce0452d69bd39db3be800828da0471
> -trigger	trg_provenance_corrections_append_only_update	...	1fc87a83346ebd841c482fe90892d9dfa571a8b7a270827e874f705738224352
> +trigger	trg_provenance_corrections_append_only_update	...	41eab09694357514b3be2fd0d61c349549b602f4fcab61ec80ff56245847bd45
> -trigger	trg_provenance_corrections_citation_graph	...	0d75e644a0c995fe40ae51d0d0da60c22c321dfda184c10fc83b1bffc9f5b3d0
> +trigger	trg_provenance_corrections_citation_graph	...	d0bd5bb822fe129acc0832651cc25dee6d61c6719648973c4aa01c8af731f048
> ```
> Against HEAD~1, only the citation_graph hash moved (38689302... to d0bd5bb8...). `scripts/schema_manifest.py` itself was not touched.
>
> **Encodings to record at Task 12:**
> 1. The `VERIFICATION_METHOD` constant's clause (4) now reads "strictly after the fire's pipeline finished_ts", per G-U1. The trade-25 literal (`tests/fixtures/tier2/trade25_seventh_blob.json`) was updated to match, and also gained `interval.record_position = "before_barrier"`.
> 2. The zero/negative-span rule is general, so a zero-length fire (run_ts == finished_ts) or covered segment would also be dropped. The service mirror then refuses it as `tier2_unverifiable interval_segment_order`. Live incidence of a zero-length fire: 0 of 152 complete runs (checked read-only).
> 3. The belt-removed tests re-create the HEAD citation trigger in their own test world, with only the belt block cut. The helper asserts that exactly that block went and that `interval_closed` still binds the key.
>
> **Spend:** zero Codex rounds (none were due in this unit).

### G-T7 -- exec cell 5

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-ab8261314c6f42e9b.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T02:42:59.258Z.

> ## GATE G-T7: Task 7 (service wiring, A2-67..A2-76) is done
>
> **Commit:** `91b3f19448de4e86bb81f9a6e560d13a24e1cd3d`, `feat(trades): Task 7 -- the correction service's tier-2 wiring (A2-67..A2-76)`. `git log -1 --format='%(trailers)'` is empty and the worktree is clean. I staged five paths by name:
> - `swing/trades/cohort_provenance_correction.py`
> - `tests/trades/test_22a2_correction_service.py` (new)
> - `tests/_tier2_world_22a2.py`
> - `tests/trades/case_registry_22a2.py`
> - `tests/cli/test_correct_cohort_provenance_command.py`
>
> I did not edit the exec ledger, run git stash, amend, push or merge.
>
> ### Red first, then green
> - **Red:** 14 tests collected. 13 failed and 1 passed; the pass was the no-evidence counterfactual, which should pass before the change.
>   - 8 failed with `TypeError: correct_cohort_provenance() got an unexpected keyword argument 'frozen_value_evidence'`.
>   - 4 failed with the same `TypeError` on `preview_cohort_provenance_correction`.
>   - A2-75 failed with `AssertionError`: the `run_preflight` caller set was `set()`, expected the two entry points.
> - **Green:** 14 passed.
> - **Mutation checks** (each one-line mutation turned only its target red, then I restored the file):
>   - A2-68: stamping the column with a second clock read turned A2-68 red.
>   - A2-69: moving the preflight inside `BEGIN IMMEDIATE` turned `A2-69[apply]` red.
> - **First full run of the three suites** caught 2 failures, both fixed in the commit:
>   - A2-08 closure: `PENDING` still held A2-67..76, and two test names carried the `a2_67` token. I widened `PENDING` to `range(1, 77)` and renamed the counterfactual so it has no roster token.
>   - The CLI's service-signature pin (`test_the_service_signature_accepts_no_cohort_VALUE`) asserted SIX parameters. It now asserts EIGHT (adds `frozen_value_evidence` and `evidence_repo`), and its docstring says why neither carries a cohort value.
>
> ### Results
> - `tests/trades tests/data tests/cli -m "not slow" -n 8`: **5076 passed, 9 skipped, 0 failed** (356s).
> - `ruff check swing/`: **All checks passed.**
>
> ### Notes to carry to Task 12's record
> 1. **A2-70's CLI leg is deferred to Task 8.** The option doesn't exist yet, so A2-70 covers both service entry points × {malformed, missing}, plus a no-evidence case asserting `tier2_note is None`. The test docstring names the deferral.
> 2. **A2-75 pins two of the three entry points today:** `run_preflight` has exactly the two correction entry points as callers, and `evaluate_conjunction` has exactly `latched_origin:_rung9_tier2_escape`. `tier2_cohort_exclusions` and `replay_verdict` don't exist yet; Tasks 9 and 10 add them to `_EXPECTED_CALLERS` in the new test file. The walk counts every Name/Attribute reference under `swing/`, not only calls, keyed by enclosing function. To keep the caller set exact, `run_preflight` is called directly in each entry point rather than through a shared helper.
> 3. **The preflight's `now_utc` is a separate read of `_APPLIED_AT_CLOCK`, taken before the transaction.** It is only the reference for the recorded-only `remote_ref_age_seconds`, parsed to aware UTC. So the age is measured at preflight time, not at the write instant that plan section 2 names, and differs by the preflight-plus-authorization duration. The key is never verdict-bearing and replay excludes it (E-15).
> 4. **The preview under a caller-held transaction.** The preview accepts a caller-held transaction by design (it uses a SAVEPOINT). In that posture the preflight necessarily runs inside the caller's transaction, which S12.1 #9 says git never should. The plan's "before its SAVEPOINT" is encoded literally. The apply rejects a caller-held transaction before it preflights. The only production caller of the preview is the CLI, which holds no transaction. Choices are: record it, or make the preview refuse evidence under a caller-held transaction. I'd record it; the shape is CHARC's to rule. I did not treat it as a blocking fork.
> 5. **The preview reads the clock only when evidence is supplied.** It writes no row, so it stays clock-free otherwise, as it was before this arc. The apply's inner stamps once before `_authorize` in every call (E-7).
> 6. **Where encoding 3 is applied:**
>    - Every ladder refusal other than `tier2_evidence_refused`, when evidence was supplied, appends `(the supplied --frozen-value-evidence was not consulted: <decline_reason>)`.
>    - `tier2_evidence_refused` prints `(tier2_evidence_refused: <tier2_refusal>)`, e.g. `criterion 3: pivot`. Task 6's `no_escape_to_take` (a tier-1 admission with evidence) arrives by this path.
>    - When the fill resolves to no latch order (this includes the `origin_envelope_inconsistent` fallthrough), the refusal names `TIER2_NO_LATCH_REFUSAL`.
>    - Refusals outside the ladder (unset state, the anchor half, the forced-fire mismatch) get no suffix; they refuse the whole correction anyway.
>    - A2-72's earlier-rung refusal is `cfg=None`, which gives `no_config` on a linked fill.
> 7. **The G-T5 manifest note: no line added.** The derivation manifest's closure check walks from `_derive` / `derive_cohort_keys_for_fire`. Neither reaches `frozen_value_evidence`, and that closure test is green in the run above. `_to_utc_naive` is already a manifest member, so any edit to it moves the derivation digest. The reverse dependency has no pin of its own, though: the tier-2 interval's UTC conversion runs on `_to_utc_naive`, and editing it would not move `FROZEN_VALUE_EVIDENCE_VERSION`. Whether `frozen_value_evidence` needs its own manifest is a question for Task 12 or Reviewer B.
> 8. **Clause shape:** `tier2_clauses` is `((criterion_text, "PASS"), ...)`, e.g. `"criterion 1 ancestor of refs/remotes/origin/main at <resolved sha> (commit <sha>)"`. That matches Task 8's output line `f"{c}: {v}"`. The clauses and the prose are read off the one blob the row carries, so the preview, the result and the row cannot disagree (A2-74 asserts equality).
> 9. **Test-helper additions:** `build_pre_barrier_world(..., with_envelope_reading=True)`, a default-preserving keyword that A2-76 uses, and `build_last_word_world(tmp_path)`.
>
> ### What Task 8 needs
> - Add the option `--frozen-value-evidence` as `click.Path(dir_okay=False, path_type=Path)` with no `exists=True`, declared last, and pass `frozen_value_evidence=` to both service calls.
> - The plan's CLI manifest has no `--evidence-repo`. With `repo_dir=None`, `run_preflight` reads `fve.EVIDENCE_REPO_DIR` at call time, so CLI tests can monkeypatch that constant to a `GitWorld`. `_evidence()` in the new test file shows how to build one.
> - Output fields: `tier2_clauses`, `tier2_interval_prose` and `tier2_note` exist on both `CohortProvenanceCorrectionPreview` and `CohortProvenanceCorrectionResult`. A refusal is a `CohortProvenanceCorrectionError` whose message carries `tier2_evidence_refused: criterion N: <field>`.
> - A2-70's CLI leg (exit 0 plus the note) lands with Task 8.
> - Task 8's "manifest pin 5 -> 6" is the CLI params manifest, which is separate from the service-signature pin I moved to EIGHT here.
>

### G-T8 -- exec cell 6

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-a856643950e9089c7.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T02:56:59.930Z.

> GATE G-T8: Task 8 is committed, with red-then-green evidence.
>
> **SHA:** `2f4b47f08979b91b80cf0fce70442d543111280e` (`feat(cli): Task 8 -- --frozen-value-evidence on journal correct-cohort-provenance (A2-77..A2-80)`) on branch `22-a2-exec`, parent `18f16237`. `git log -1 --format='%(trailers)'` printed empty. `git status` is clean. I staged 4 paths by name:
> - `swing/cli.py`
> - `tests/cli/test_correct_cohort_provenance_command.py`
> - `tests/trades/case_registry_22a2.py`
> - `tests/trades/test_22a2_correction_service.py` (the A2-70 docstring only)
>
> **Red first.** I ran the CLI file and the case closure with `-n 0`: 7 failed and 125 passed. Every red was for the right reason: the option did not exist.
> - A2-77: the manifest equality failed with 5 entries against the expected 6.
> - A2-78 [dry-run], A2-78 [apply], A2-79, and the A2-70 CLI leg [malformed] and [missing]: all 5 exited 2 with `Error: No such option: --frozen-value-evidence`.
> - A2-80: the help had no option to name. My grep filter hid this test's assertion line, so I only saw it listed as FAILED; I infer the reason from the absent option.
>
> I widened the case closure's `PENDING` to `range(1, 81)` before the red run, so the closure test (among the 125 passing) accepted the new `a2_77..a2_80` tests. No non-roster test name carries a roster token. The A2-70 CLI leg is named `test_an_already_applied_replay_with_a_bad_evidence_file_exits_zero`.
>
> **Green.** The same two files gave 132 passed.
> - I also mutated the option to `click.Path(exists=True, ...)`. The A2-70 CLI [missing] case then failed with `Invalid value for '--frozen-value-evidence': File ... does not exist.` (exit 2), and [malformed] still passed, as it should. I reverted the mutation and confirmed the line on disk.
>
> **Results:**
> - `tests/trades tests/data tests/cli -m "not slow" -n 8`: **5082 passed / 9 skipped / 0 failed** (331.72 s). That is 5076 plus 6 new test ids; the manifest test was renamed, not added.
> - `ruff check swing/`: all checks passed.
> - The full fast suite was not run; that is outside this unit.
>
> **Notes for Task 12's record (plan vs implementation):**
> 1. **The CLI tests use trade 25's world end-to-end, not a printer stub.** `_t25_world` builds `build_pre_barrier_world`, sets `fve.EVIDENCE_REPO_DIR` to a `GitWorld`, and swaps in `t25_cfg` by monkeypatching `swing.config_overrides.apply_overrides`. That works because the command imports it at call time. The `--config` file exists only so the command group can load. The real clock is used; no ticking clock was needed.
> 2. **The output lives in the shared printer.** The clauses and prose print at the end of the existing `_echo_admission_tier`, so both surfaces print them from one helper:
>    - Each clause prints as `f"  {criterion}: {verdict}"`.
>    - The prose prints as `f"  {'uncovered window':<30}{prose}"`.
>    - Nothing prints for other tiers, and a counterfactual assertion to that effect was added to the existing `test_both_surfaces_print_the_admission_tier`.
>    - The new `_echo_tier2_note` prints `  NOTE: <tier2_note>` in both already-applied branches (dry-run and apply).
> 3. **Refusals needed no new code.** A refusal was already a `ClickException` with exit 1, and its message carries `tier2_evidence_refused` and `criterion 3: pivot`. A2-79 pins both, on the dry run and on the apply.
> 4. **The help text** names `artifact_path`, `artifact_commit_sha` and `quoted_text`, and says the values are "never typed". A2-80 reads the key names from `fve.EVIDENCE_FILE_KEYS`, so a key added to that constant but not to the help fails the test.
> 5. **A2-78 is parametrized over the dry run and the apply,** because the plan's Build says both surfaces print. On the apply leg, the printed prose must end with the stored blob's `uncovered_window_prose`, and the commit SHA must appear in criterion 1's line.
> 6. **The two service calls pass `frozen_value_evidence=` only.** `evidence_repo` is left at None, since there is no CLI repo option in the manifest.
> 7. **The command's docstring** gained one paragraph on the tier-2 escape.
>
> **What Task 9 needs:**
> - The replay work lives in `swing/trades/frozen_value_evidence.py`: `replay_verdict` and `tier2_cohort_exclusions` (with its budget and the per-call memo).
> - The drift reader is `read_provenance_corrections` in `cohort_provenance_correction.py`. Its rendering is `journal provenance-corrections` in `swing/cli.py`, which starts right after the correct command at about line 2890.
> - The new test file is `tests/trades/test_22a2_replay.py` (A2-81..A2-90). `PENDING` must widen to `range(1, 91)`.
> - The replay helpers already exist in `tests/trades/test_22a2_correction_service.py`: `_evidence()` builds a `GitWorld` plus the selection file, and `_t25`/`_apply` write a real tier-2 row.
> - A2-75's AST caller walk pins the callers of `tier2_cohort_exclusions` to exactly the P35 reader set plus the drift reader, and the callers of `evaluate_conjunction` to rung 9 plus `replay_verdict`. Task 9 adds real callers, so that test will fail until each one is a named member. It is worth running early.
> - No new design fork surfaced in this unit.

### G-T7F -- exec cell 6

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-a856643950e9089c7.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T03:09:47.351Z.

> GATE G-T7F: the G-T7 follow-on is committed, red-first. **Trailer defect on the tip, flagged here and not fixed.**
>
> **SHA:** `889e5e7242039368d18c8ca803fbf9f9a69bf7fa` (`fix(trades): Task 7 follow-on -- G-T7 Q1 + Q2 (CHARC)`), parent `dfa9efa9`. `git status` is clean. I staged three files by name:
> - `swing/trades/cohort_provenance_correction.py` (+11)
> - `swing/trades/frozen_value_evidence.py` (+144)
> - `tests/trades/test_22a2_g_t7_followon.py` (+165, new)
>
> **TRAILER DEFECT.** The commit body's only paragraph begins with `Q1:`, and git parsed the whole paragraph as a trailer. `git log -1 --format='%(trailers)'` is therefore NOT empty: one `Q1` trailer. There is no `Co-Authored-By` (`%(trailers:key=Co-Authored-By)` is empty). I did not amend: amending is forbidden, and the recipe says to stop and flag. It is the TIP commit and nothing cites it yet. A tip-only fix is to reword the message with a plain-prose final paragraph, for example by prefixing it with "This commit: ". That is yours to authorize.
>
> **Red first.** The new test file ran with `-n 0`: 5 failed and 1 passed.
> - Q1 discriminator: `DID NOT RAISE`. With a counting wrapper that delegates to the real `_run_git`, the preview ran git inside the caller's `BEGIN` and returned.
> - Three Q2 tests failed with `AttributeError`: `frozen_value_evidence_digest` and `frozen_value_evidence_digest_parts` did not exist.
> - The hash-seed test failed because its subprocess import errored.
> - The one pass is the Q1 twin (no evidence under an open transaction still previews), which is the counterfactual and should pass before and after.
>
> **Green.**
> - The new file plus `test_22a2_conjunction.py` (A2-60), `test_22a2_correction_service.py` (A2-75) and the case closure, run with `-n 0`: 152 passed.
> - `tests/trades tests/data tests/cli -m "not slow" -n 8`: **5088 passed / 9 skipped / 0 failed** (297 s). That is 5082 plus the 6 new tests.
> - `ruff check swing/`: all checks passed.
> - A2-60's closure and A2-75's caller walk are green unchanged. The new digest code names its roots as STRINGS, so it adds no name reference to `evaluate_conjunction` that the caller walk would see.
>
> **Q1 as encoded.**
> - The guard is the first statement of `preview_cohort_provenance_correction`: `if frozen_value_evidence is not None and conn.in_transaction: raise CallerHeldTransactionError("tier-2 evidence needs a preflight outside any transaction; call the preview on a connection that holds none. Nothing was written.")`.
> - It fires before `run_preflight`.
> - `CallerHeldTransactionError` subclasses `CohortProvenanceCorrectionError`, so it is the typed error the ruling asks for, and the CLI's except clause still catches it.
> - I added " Nothing was written." because the error class's docstring requires every refusal message to end with it.
> - The discriminator asserts zero git calls, the typed class, the ruled text, and that the caller's transaction is still open afterwards.
>
> **Q2: the member set differs from the ruling's list.** The ruling names six members; the code's closure is larger. Following the recipe's rule for rulings (the reasoning binds; the incidental facts are checked against the code), I encoded the ruling's principle, "every function the blob is a function of":
> - The six named members are the ROOTS (`FROZEN_VALUE_EVIDENCE_DIGEST_ROOTS`).
> - The digest covers their STATIC REFERENCE CLOSURE. That is every module-level function, class and constant a member names, followed transitively. It follows imports into other `swing` modules, both at module level and inside function bodies, and resolves re-exports to their home definition.
> - Stdlib and third-party names are outside the walk. The walk raises `LookupError` on a name it cannot place.
> - The only exclusion is `FROZEN_VALUE_EVIDENCE_VERSION` itself, because it is what the digest pins.
> - The same pattern as `DERIVATION_RULE_HISTORY`:
>   - Functions and classes are hashed by source; constants by a canonical rendering.
>   - Sets and dicts are sorted.
>   - A callable renders as `module:qualname`, because `_BLOB_MIRRORS` holds functions and their `repr` includes a memory address.
> - `FROZEN_VALUE_EVIDENCE_HISTORY = (("2026-09-23.1", "23893a66d73f0a30529eaa7f458e136bd296b1c5b017d277318526eff7cbdb31"),)`.
>
> **Members as computed: 79** (48 functions, 27 constants, 4 classes).
> - Outside `frozen_value_evidence`:
>   - `swing.trades.cohort_provenance_correction:_to_utc_naive`
>   - `swing.evaluation.dates:PIPELINE_LOCAL_TIMEZONE` (re-exported through the correction module)
>   - `swing.data.repos.candidates_immutability_epoch:epoch_boundary`
>   - `swing.data.repos.pipeline:evaluation_run_persistence_bound`
>   - `swing.data.repos.pipeline:EvaluationRunPersistenceBound`
> - Beyond the six, the unnamed members are:
>   - the helpers the blob values come from: `_utc_text`, `_local_naive_utc`, `_seconds`, `render_uncovered_window_prose`, `_criterion3`, `_read_context`
>   - the 26 `_tp_*` mirrors plus `_BLOB_MIRRORS`, `_first_failing_mirror` and their helpers
>   - `_refused`, the refusal reason strings, the text and roster constants, the data classes, `_SHA_RE` and `ET_ZONE`
>
> To narrow to the literal six, the walk would stop at the roots, which is a one-line change. That is CHARC's call.
>
> **Tests (all in `test_22a2_g_t7_followon.py`):**
> - The current version/digest pair is asserted, the history has unique versions, and its first entry is `2026-09-23.1`.
> - The six ruled members are asserted present by name, and the version is asserted absent.
> - One-character-edit discriminator: the unmodified parts reproduce the live digest, and changing the last character of ANY member's body (the six included, all 79 in a loop) moves it. This runs on strings and never edits the module on disk.
> - Two subprocesses with `PYTHONHASHSEED` 0 and 12345 produce the same digest.
>
> **Notes for Task 12's record:**
> 1. The member set was widened from 6 named to 79 computed, as above. It needs CHARC's confirmation.
> 2. **Not in the closure: `read_artifact_facts` and `_parse_reflog_instant`.** They produce the facts the blob records: `author_instant` (verdict-bearing), the committer instant, the resolved SHA, the descendant count and the ref age. They are INPUTS to `evaluate_conjunction`, not names it references, so the walk does not reach them and the ruling does not name them. A change to how `%aI` is parsed would move a verdict-bearing key without a version bump. Adding them as a seventh root is a one-line change; I am reporting it, not deciding it.
> 3. **Cost of a wide set.** 0039's trigger binds `$.evidence_version` to the literal `'2026-09-23.1'`. Once 0039 is applied live, a version bump needs a trigger change, which is a migration. So any future edit to any of the 79 members, including a mirror or a docstring inside one, costs a migration. The ruling accepted this consequence for its six; the wider set makes it bite more often.
> 4. Like the derivation pin, the digest hashes docstrings and comments inside members, and the constants' `repr` (ZoneInfo, re.Pattern) could in principle differ across Python versions. It is stable across line endings, because `inspect.getsource` translates newlines.
> 5. The replay reason `evidence_version_moved (stored X, current Y)` is not in this commit. It lands with `replay_verdict` in Task 9, which should compare the stored blob's `evidence_version` with `FROZEN_VALUE_EVIDENCE_VERSION` before any key comparison.
> 6. The Q1 guard also comes before the SELECT-first already-applied return: under a caller-held transaction, evidence on an already-applied trade is refused rather than returning the existing id. The apply path already refuses any caller-held transaction first, so this matches it. It is not a payload refusal, so E-6 is untouched.
>
> Stopped at gate G-T7F.

### G-T9 -- exec cell 7

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-a4e61db52e508b458.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T03:29:11.555Z.

> GATE G-T9: Task 9 is done in one red-first commit.
>
> **SHA:** `9f175d2e811e270c995874034e44783d8d71f833`, `feat(trades): Task 9 -- replay_verdict, tier2_cohort_exclusions, the drift reader verdict line`. `git log -1 --format='%(trailers)'` prints empty. Nothing was amended or pushed, and no Codex round ran in this unit.
>
> Files changed: `swing/trades/frozen_value_evidence.py`, `swing/trades/cohort_provenance_correction.py`, `swing/cli.py`, the new `tests/trades/test_22a2_replay.py`, `tests/trades/test_22a2_correction_service.py` (A2-75's `_EXPECTED_CALLERS`) and `tests/trades/case_registry_22a2.py` (PENDING widened to `range(1, 91)`).
>
> **Scope change honoured:** there is no version-moved check or test anywhere. I never wrote one, so there was nothing to remove.
>
> ## Red, then green
> - **New file, red run (`-n 0`):** 18 collected, 18 failed.
>   - 16 failed on `AttributeError` because `replay_verdict`, `tier2_cohort_exclusions` or `_tier2_rows` did not exist.
>   - A2-90 failed on `'ProvenanceCorrectionReport' object has no attribute 'replay'`.
>   - The budget test first failed on a bug in the test itself: `dataclasses.replace(trade_id=26)` was refused by the model. I switched it to a duck-typed copy, re-ran it, and it went red for the expected reason (the missing functions).
> - **A2-75, red:** "Extra items in the right set: `swing.trades.frozen_value_evidence:replay_verdict`", after I added the new callers by name before writing any code.
> - **One regression during implementation:** my first budget design passed a `deadline` argument into `_run_git`. That broke A2-69, because its `_watched` wrapper takes no keyword arguments. I moved the budget check into a local wrapper inside `read_artifact_facts`, so `_run_git`'s signature is unchanged.
> - **Green:**
>   - The five 22-A2 files (replay, correction service, G-T7 follow-on, case closure, preflight): 166 passed.
>   - `tests/trades`, `tests/data` and `tests/cli` at `-n 8`: **5106 passed / 9 skipped / 0 failed**. That is 5088 plus the 18 new tests.
>   - `ruff check swing/`: clean.
> - **Digest pin:** `frozen_value_evidence_digest()` still equals `FROZEN_VALUE_EVIDENCE_HISTORY[-1]`, with 79 closure members. No digest member was edited. I checked that `read_artifact_facts`, `_run_git` and `VERDICT_BEARING_KEYS` are outside the closure before editing them.
>
> ## Notes for Task 12's record
> 1. **The drift reader's caller doesn't match R4.2 ruling 2's wording. CHARC should confirm.**
>    - R4.2 lists the drift reader among `tier2_cohort_exclusions`'s callers. I have it call `replay_verdict` directly instead.
>    - The reason: it has to render every tier-2 row, including ADMIT rows with their SHA and `evaluated_at`. The exclusions dict carries only non-ADMIT rows, so it cannot supply those.
>    - A2-75 now pins:
>      - `evaluate_conjunction`: `_rung9_tier2_escape` plus `replay_verdict`.
>      - `replay_verdict`: `tier2_cohort_exclusions` plus `read_provenance_corrections`.
>      - `tier2_cohort_exclusions`: the empty set until Task 10.
> 2. **Signature additions beyond the plan.** `replay_verdict` takes an extra `deadline=` (a `time.monotonic()` instant), and `read_artifact_facts` gained `deadline=None`. The write path passes nothing, so its behaviour is unchanged. The budget is checked before each git call starts and never interrupts a running call, so the worst case is the budget plus one call timeout.
> 3. **New replay reasons:**
>    - `caller_holds_transaction` → unverifiable, and no git starts. This is the G-T7 Q1 principle applied to the replay.
>    - `stored_evidence_malformed` → stale.
>    - `entry_fill_session_date_malformed` → stale. It enforces a full round-trip, so a week date such as `2026-W33-1` is refused as well as garbage and `None`. The model already refuses these at construction, so the test uses `SimpleNamespace` copies.
>    - `author_instant_changed` → stale, as the plan says.
> 4. **Reason formats:**
>    - A conjunction refusal reads stale `criterion N: <reason>`, the same form the write side uses (for example `criterion 1: not_ancestor_of_origin_main`, `criterion 3: pivot`).
>    - A refusal with no criterion (the blob could not be built, or a trigger-mirror check failed) reads `tier2_unverifiable`, naming the predicate.
>    - A process failure's reason is git's detail text (for example "...timed out after 10.0s"). Budget overrun is exactly `web_budget_exhausted`.
> 5. **Mismatch comparison:** the recomputed blob goes through a JSON round trip, and the first differing key in `sorted(VERDICT_BEARING_KEYS)` is named `<key>_mismatch`. A2-86 also checks that changing a recorded-only key still admits.
> 6. **Memo:** it is keyed `(id, resolved_sha)` as ruled but looked up by id within the call. The SHA half is recorded, not consulted, because re-resolving the ref first would cost the git call the memo is meant to save. Rows are unique by primary key, so the memo only matters if the select returns a row twice; I tested that by monkeypatching `_tier2_rows`.
> 7. **Barrier observation:** `replay_verdict` reads `barrier_installed(conn)` first (a plain read, before any git) and passes that same value to `evaluate_conjunction`.
> 8. **Non-tier-2 rows:** `replay_verdict` raises `ValueError` for them, since that is a caller bug. For a tier-2 row it never raises; any unexpected error reads unverifiable.
> 9. **Drift reader:** the signature is now `read_provenance_corrections(conn, *, trade_id=None, now=None)`, and `ProvenanceCorrectionReport` gained `replay` (default `None`). The CLI line is `  read-time verdict: <V>[ (<reason>)] evaluated_at <iso>, origin/main <sha|unresolved>, barrier installed at read <bool>`. The parenthetical is left out for ADMIT.
>
> ## Where the derivation-version observation would fit
> `ReplayVerdict` is a frozen dataclass with five fields. Every test reads its fields by name, and the one place it is built internally uses keywords; no test builds or compares whole instances.
>
> So an optional last field with a default (for example `derivation_version_moved: str | None = None`) does not disturb A2-81..A2-90. One caveat: A2-90 asserts the CLI line `endswith("barrier installed at read True")`. If the follow-on appends the observation to that line, the assertion needs updating; putting it on its own line avoids that.
>
> ## What Task 10 needs
> - The call is `tier2_cohort_exclusions(conn, *, now, repo_dir=None, budget_seconds=None)`, which returns the non-ADMIT rows as `{trade_id: ReplayVerdict}`.
> - The web readers pass `fve.WEB_REPLAY_BUDGET_SECONDS` (2.0, a new constant). The CLI readers pass nothing.
> - Add each new reader to `_EXPECTED_CALLERS["tier2_cohort_exclusions"]` by name.
> - **Readers must not call it inside a transaction they hold.** If they do, every tier-2 row reads `caller_holds_transaction`: excluded, which fails closed, but with the wrong reason.
> - For A2-97b/c, the `_GitCounter(monkeypatch, delay=...)` helper in `tests/trades/test_22a2_replay.py` gives a slow git. It patches the global `subprocess.run`, so install it after any GitWorld setup. The `_tier2_world(tmp_path)` helper in the same file builds a real tier-2 row.

### G-T7FE -- exec cell 8

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-ab73d967f8ca03ff8.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T03:56:33.933Z.

> GATE G-T7FE: unit 1 (G-T7F + G-T7F-AMEND) is committed. One ruling fact was wrong and I encoded the code's behaviour instead (item 1 of the last section). I have not started Task 10.
>
> **SHA:** `abcbd632cb4210e38b4dd71175497961df2ba79d` on `22-a2-exec`, one commit on top of `c629a3eb`. `git log -1 --format='%(trailers)'` prints empty. I did not amend, push or merge, and I did not touch the ledger.
>
> **Red, then green**
> - **Red run** (`-n 0`, four files: follow-on, conjunction, 0039 tests, replay): 49 failed and 65 passed. Every failure was for the expected reason:
>   - **23 tests that insert the truthful row** (A2-26, A2-28 x21, A2-31): the fixture now carries `derivation_version` and the old trigger refused it as an extra key (`IntegrityError` from blob_closed).
>   - **G-NEG x3 and my 0039 tests x3:** the same extra-key refusal on the control row.
>   - **Absent-key case:** "absent" was not refused, because there was no type clause yet.
>   - **Missing names:** `AttributeError` or `ImportError` on `FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION`, `_member_body` and `ReplayVerdict.derivation_observation`.
>   - **Old digest behaviour:** member bodies were source text (the `epoch_boundary` body began `def epoch_boundary(`); a constant digested as `'2'` rather than `Constant(value=2)`; `read_artifact_facts` was missing from the closure; the one-token edit left the digest unchanged because `_parse_reflog_instant` was outside the closure.
>   - **Counts and text:** A2-42 found the key sets unequal, A2-60 read 29 predicates where 30 are expected, the blob_closed path list read 28 where 29 are expected, and the grammar-bump obligation was missing from the header.
>   - **Replay:** a `KeyError` on `derivation_version`, and the `evidence_version_moved` grep hit a comment in `frozen_value_evidence.py`.
> - **Green:** 128 passed across the four files plus the correction-service file (A2-75).
> - **One test was written after the implementation:** `test_g_t7f_amend_a_moved_version_is_on_every_stale_reason_line` pins encoding choice 3 below. I checked it by mutation instead: limiting the suffix to `_mismatch` reasons turns it red.
> - **Mutations of RD's discriminators, each reverted** (the file is byte-identical afterwards, checked with `cmp`, and the digest is unchanged):
>   - A version-only-stale version turns the keys-equal ADMIT test red, along with three others.
>   - A keys-only version turns the names-both test red, along with one other.
>
> **Results on the committed head**
> - `tests/trades tests/data tests/cli -n 8`: **5127 passed, 9 skipped, 0 failed**. G-T9 was 5106.
> - `ruff check swing/`: all checks passed.
> - The E501 line wrap I fixed after the first run left the digest unchanged, which shows by execution that layout does not move it.
>
> **Fixture delta, `05702929..HEAD` on `tests/data/schema_manifest_head.tsv`:** numstat `4 4`, exactly four changed pairs, zero deletions:
> ```
> -# schema_version 38
> +# schema_version 39
> -table	provenance_corrections	...	175402245803b8bf...
> +table	provenance_corrections	...	c82dc45068fbc9cf...
> -trigger	trg_provenance_corrections_append_only_update	...	1fc87a83346ebd84...
> -trigger	trg_provenance_corrections_citation_graph	...	0d75e644a0c995fe...
> +trigger	trg_provenance_corrections_append_only_update	...	41eab09694357514...
> +trigger	trg_provenance_corrections_citation_graph	...	2f202f9485fd5970...
> ```
> I did not otherwise touch `scripts/schema_manifest.py`.
>
> **New member count: 95** (54 functions, 34 constants, 7 classes), counted from `frozen_value_evidence_digest_parts()`. How it got there from 79:
> - The six roots alone now give 81. The two additions are the grammar constant `FROZEN_VALUE_EVIDENCE_VERSION`, now a member (note 2), and `_tp_derivation_version`.
> - The seventh root adds 14: `read_artifact_facts`, `_parse_reflog_instant`, `_run_git`, `_stderr`, `_refuse`, `PreflightResult`, `_GitProcessError`, `_BudgetExhaustedError`, `REMOTE_REF`, `GIT_TIMEOUT_SECONDS`, `REASON_WEB_BUDGET_EXHAUSTED`, `FAILURE_ARTIFACT_UNREADABLE`, `FAILURE_QUOTED_TEXT_NOT_IN_ARTIFACT`, `FAILURE_QUOTED_TEXT_NOT_ONE_LINE`.
> - CHARC's "80" did not count this second-level closure. Cell 7's check that `_run_git` was outside the closure is superseded: it is now a member.
>
> **First derivation version: `2026-09-23.2`, digest `e098e9cddd4327b545dac89dbc7f017442f016bf9f82c5b9731d4b815fec1c1b`.** Why `.2`:
> - `2026-09-23.1` is the grammar literal. If the two constants shared a value, a builder that wrote one constant under the other's key would pass every literal comparison.
> - `.1` was also the version string that the old source-text pair (`23893a66...`, cited at `ee157a28`) carried on this branch, and an append-only history should never bind one version string to a second digest.
> - The history was re-seeded, not appended, as you instructed. A comment in the module explains the `.2`.
> - If you would rather have a distinct scheme, the one-line change is the constant, the history entry and the literal in `trade25_seventh_blob.json`.
>
> **Notes for Task 12's record**
> 1. **Where each piece lives:** blob key `derivation_version` sits right after `evidence_version` (roster 29). The SQL `json_remove` list gains `'$.derivation_version'` on the evidence_version line. The new clause `-- TIER2-PREDICATE derivation_version` asserts `json_type(...) = 'text'` only; a test asserts the path occurs exactly twice in the trigger and is never passed to `json_extract`. A2-60 now asserts 30 predicates and checks the new one by name. A2-42 asserts length 29 and adds `derivation_version` to its constants loop.
> 2. **New comparator test:** the trigger's blob_closed path list must equal `FROZEN_VALUE_BLOB_KEYS`. No such test existed; it is the gotcha-#11 comparator for this roster.
> 3. **Digest details:**
>    - Docstrings are stripped from nested functions and classes as well as top-level ones.
>    - Constants are digested from the AST of their assigned value, not their runtime value, so `_canonical` was deleted as unused. The hash-seed test is still green.
>    - The old "one-character edit" test now flips a character of the `ast.dump` string. It still proves the hash is sensitive, but it is no longer a source-edit test; the new copy-based docstring, comment and one-token tests cover that.
> 4. **Replay:**
>    - `ReplayVerdict.derivation_observation: str | None = None` is the last field.
>    - The observation is computed whenever the stored blob parses as a dict. A missing key renders as `stored None`, which the trigger prevents in practice.
>    - The drift reader prints `  observation: derivation_version_moved (stored X, current Y)` on the line right after the verdict line. A2-90's verdict-line ending is unchanged. On a stale row the text therefore appears twice, once in the reason and once on the observation line; that is intentional.
> 5. **0039 header:** the reversibility header now has a "GRAMMAR-BUMP OBLIGATION" paragraph: a grammar-bumping migration must declare either a per-version recompute adapter or a declared exclusion with its reason, because the gate reads code x the live rows, not only code x the live schema.
> 6. **For Task 10, likely a fork:** `tier2_cohort_exclusions` returns only non-ADMIT rows. The AMEND asks the four readers to render the observation, but an ADMITTED row whose derivation version moved never reaches them through the current API. The return shape needs to carry admitted rows' observations, for example by returning every verdict and letting readers filter. That is CHARC's shape call.
> 7. **Plan text not updated:** plan sections 1 and 2 (the 28-key roster table, the vocabulary) do not yet show the split; I followed the rulings.
>
> **What I could not encode as written, and the choices I made**
> 1. **Fact corrected — the absent-key abort is not blob_closed.** The ruling says a raw insert without `derivation_version` aborts at blob_closed. It does not: `json_remove(...) = '{}'` refuses an EXTRA key and passes a missing one. Absence aborts on the new type clause, because `json_type` of a missing path is NULL and the enclosing COALESCE turns that into a refusal. I encoded the true attribution. Absent, integer, null and object each ABORT and are ACCEPTED once the type clause is cut. Separately, cutting blob_closed's new entry makes the truthful row refuse as an extra key, which shows that entry is what admits it. No option is needed; I am recording the correction.
> 2. **My choice — the grammar version is now in the digest closure.** It used to be excluded because it was the pinned constant. I included it because the builder emits it, so a grammar bump also forces a derivation bump. Alternative: add it to `_DIGEST_EXCLUDED` (one line). I recommend keeping it in. Ruler: CHARC.
> 3. **My reading — the moved version is appended to every stale reason, not only `<key>_mismatch`.** I took the AMEND's "the moved version is always on the reason line" to cover criterion refusals and `author_instant_changed` too. Unverifiable verdicts carry the observation field but not in their reason. Alternative: suffix only key mismatches. That is a one-line change, and the post-implementation pin test would flip. I recommend my reading. Ruler: CHARC, with RD on the doctrine.
>
> Files: `C:/Users/rwsmy/swing-trading/.worktrees/22-a2-exec/swing/trades/frozen_value_evidence.py`, `.../swing/cli.py`, `.../swing/data/migrations/0039_provenance_corrections_tier2.sql`, `.../tests/data/schema_manifest_head.tsv`, `.../tests/fixtures/tier2/trade25_seventh_blob.json`, `.../tests/trades/test_22a2_g_t7_followon.py`, `.../tests/trades/test_22a2_conjunction.py`, `.../tests/trades/test_22a2_replay.py`, `.../tests/data/test_migration_0039_provenance_corrections_tier2.py`. No Codex rounds were in scope for this unit, so there is no spend line.

### G-T9F -- exec cell 9

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/4b561058-2f22-45ac-b0e7-c3dc04defdcd/subagents/agent-a4290dedf741ec2e4.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T04:20:04.525Z.

> GATE G-T9F: exec cell 9. The G-T9 item 2 unit and the G-T7FE-B pins are in ONE commit. I have stopped here.
>
> **SHA:** `112202cb3bc83f3ed859720e705eb3d741e58441` on `22-a2-exec`. Its parent is your ledger commit `29da90db`. `git log -1 --format='%(trailers)'` prints empty. No amend, no push, and I did not touch the ledger.
>
> **Red, then green** (`-n 0`, `tests/trades/test_22a2_replay.py`)
> - **Red:** 32 collected, 3 failed for the expected reasons, 29 passed.
>   - A2-89 read `(rev-parse, reflog) = (3, 3)` against the expected `(1, 1)`. That is the per-row-resolve failure, with 3 rows.
>   - The drift-reader once-per-invocation test also read `(3, 3)` against `(1, 1)`.
>   - The wrong-repo test raised `AttributeError`: `resolve_remote_ref` did not exist yet.
> - **Test-side fix during the red run:** my first A2-89 draft read `(6, 3)`. The test's own `w.git.remote_tip()` calls go through the same patched `subprocess.run`, so the counter saw them. I moved `tip = w.git.remote_tip()` ahead of the counter. That was a counting error in the test, not in the code.
> - **Passed on first run, as expected:** the 4 G-T7FE-B pins, the direct-call pin and the caller-held-transaction pin. All six pin behaviour that already existed. None was faked red; each is proven by a mutation below.
> - **Green:** all of the above pass.
>
> **Mutation evidence** (one line each, then reverted; `cmp` against a saved copy was byte-identical after every revert)
> - **M1, suffix only on `_mismatch` reasons:** red on the G-T7FE-B criterion-3 pin, the G-T7FE-B `author_instant_changed` pin, and the existing AMEND criterion-1 pin.
> - **M2, always append (the observation computed unconditionally):** red on `test_g_t7fe_b_an_unmoved_version_is_on_no_stale_reason`, plus 9 other stale-reason tests.
> - **M3, append on unverifiable too:** red on `test_g_t7fe_b_unverifiable_under_a_moved_version_carries_it_in_the_field_only` and the existing AMEND test.
> - **M4, resolve even under a caller-held transaction:** red on the caller-held-transaction test.
> - **M5, a module-level resolution cache:** red on A2-89 leg (iii), which read `(1, 1)` against `(2, 2)`.
>
> **Results**
> - `tests/trades tests/data tests/cli -m "not slow" -n 8`: **5135 passed / 9 skipped / 0 failed**.
> - `ruff check swing/`: All checks passed.
> - The first full run had 1 failure. A2-08 (case closure) found 4 test functions carrying the `a2_89` token. I renamed the three support tests off the token (details below). A2-08 is unchanged and the final run above is after the rename.
> - A2-60 and A2-75 are green and unchanged. `replay_verdict`'s callers are still exactly {`tier2_cohort_exclusions`, `read_provenance_corrections`}.
>
> **Design: which way I went, and why**
> I edited the member. A new entry point outside the digest would not have been clean. `read_artifact_facts` has no place to inject a pre-resolved ref, so an entry point outside the digest would have to copy the show / cat-file / merge-base / rev-list logic. That copy would produce verdict-bearing facts outside the digest, which is the exact gap G-T7F item 2 closed. It would also break the plan's "same function as write" property.
>
> What changed:
> - `read_artifact_facts(..., resolution: RemoteRefResolution | None = None)`.
>   - With `None` (the write path, the preflight, a direct `replay_verdict`), it reads the ref and the reflog itself, at the same two points and in the same git call order as before. Every existing test on those paths is unchanged.
>   - A resolution's two stages stand in at those same points, so each row gets the verdict a self-resolving read would give.
>   - A resolution made for a different repo is refused as unverifiable.
> - New helpers: `resolve_remote_ref(repo_dir, *, deadline)`, which never raises, plus `_ref_stage`, `_reflog_stage`, `_budgeted_git`, `_failure_detail` and the class `RemoteRefResolution`.
> - Both invocation sites resolve once, after collecting their rows, and never under a caller-held transaction. Zero tier-2 rows still means zero git calls.
> - The budget is still checked before every git call, including the resolution's two, and an overrun still reads `web_budget_exhausted`.
> - The four new helper names are added to `PREFLIGHT_FUNCTIONS`, so A2-41 checks them too.
>
> **Digest outcome: moved**
> - New pair appended: `("2026-09-23.3", "f99090619b500e866bf104556bb419b7c26ab85e1cc82ce6e6ddc4b0d1eb5193")`. `FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION` is now `2026-09-23.3`. The `.2` entry is untouched.
> - Members changed, found by diffing `frozen_value_evidence_digest_parts()` at HEAD (a `git archive` copy) against the working tree:
>   - **Changed:** `read_artifact_facts` only.
>   - **Added:** `RemoteRefResolution`, `_budgeted_git`, `_failure_detail`, `_ref_stage`, `_reflog_stage`.
>   - **Removed:** none.
>   - The closure went from 95 to 100 members (58 functions, 34 constants, 8 classes).
> - **Trade 25's stored-blob literal:** `tests/fixtures/tier2/trade25_seventh_blob.json` needed the new version. One pair changed, `derivation_version` from `.2` to `.3`; numstat against HEAD is `1 1`. A2-42 compares that key to the module constant; A2-43 did not need a change.
> - **Test reconciled by name:** `test_the_grammar_version_is_split_from_the_derivation_version` in `tests/trades/test_22a2_g_t7_followon.py` asserted the current version == `FIRST_DERIVATION_VERSION`. It now asserts `CURRENT_DERIVATION_VERSION = "2026-09-23.3"`, and additionally that the history's versions are exactly `[".2", ".3"]`. `FIRST_DERIVATION_VERSION` still pins `history[0]`. This is tighter than before, not looser.
>
> **Notes for Task 12's record**
> 1. **Possible design fork, routing to CHARC.** `resolve_remote_ref` is NOT a digest member. The static walk does not reach it, because `read_artifact_facts` calls the stages directly; I did that to keep the write path's git order unchanged. Its stages are members; its own composition (skip the reflog when the ref fails, map failures) is not. It is only on the replay path and never writes a blob, so by the "what the blob is a function of" principle it is correctly outside. It does decide which ref the replay's merge-base checks against. If CHARC wants it inside the digest, making it an eighth root is a one-line change that forces another version bump. I did not encode that.
> 2. **Roster.** A2-89 is now `test_a2_89_one_replay_per_row_and_one_ref_resolution_per_invocation`. It covers legs (i), (ii) and (iii) over three rows: the real trade-25 row plus two duck-typed copies with ids 91 and 92. The plan's A2-89 row text ("memo keyed ...") is now superseded by G-T9. Four support tests carry no roster token:
>    - `test_a_direct_replay_resolves_the_ref_itself`
>    - `test_the_drift_reader_resolves_the_ref_once_per_invocation`
>    - `test_a_resolution_for_another_repo_is_refused_not_used`
>    - `test_the_invocation_resolves_no_ref_under_a_caller_held_transaction`
> 3. **G-T7FE-B.** Four pins were added under a `G-T7FE-B` section: criterion 3 (the five-cent pivot) plus a moved version; `author_instant_changed` plus a moved version; any stale reason under an unchanged version (checked across three stale classes); and unverifiable (a git timeout) plus a moved version. They pin behaviour already encoded at `abcbd632`, and the mutations above prove each one. `tier2_cohort_exclusions` still returns a plain dict; `Tier2CohortRead` (G-T7FE-A+C item C) is left for Task 10, untouched.
> 4. **Count method.** The member counts come from a JSON diff of `frozen_value_evidence_digest_parts()` between the two trees, not from grep. The git-call counts in the tests use the `_GitCounter` wrapper on `fve.subprocess.run`, matching `args[1:2] == ("rev-parse",)` and `args[1:3] == ("log", "-g")`.
>
> **Files:**
> - `C:/Users/rwsmy/swing-trading/.worktrees/22-a2-exec/swing/trades/frozen_value_evidence.py`
> - `C:/Users/rwsmy/swing-trading/.worktrees/22-a2-exec/swing/trades/cohort_provenance_correction.py`
> - `C:/Users/rwsmy/swing-trading/.worktrees/22-a2-exec/tests/trades/test_22a2_replay.py`
> - `C:/Users/rwsmy/swing-trading/.worktrees/22-a2-exec/tests/trades/test_22a2_g_t7_followon.py`
> - `C:/Users/rwsmy/swing-trading/.worktrees/22-a2-exec/tests/fixtures/tier2/trade25_seventh_blob.json`

### G-T10 (fork stop) -- exec cell 10

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/0492607f-f8bc-42a1-a1f6-6b52b831c884/subagents/agent-ab728b5c18d19e905.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T04:29:35.532Z.

> GATE G-T10: STOPPED ON A FORK. Nothing written, nothing committed. HEAD is still b6903a0a and the worktree is clean. I read the rules from main at b16804722b1add5a64056b0599394f36a88cb2cb.
>
> The fork is the one your brief named: "the four P35 readers" do not map onto four call sites where each is called ONCE per invocation with the right budget. One P35 reader calls another. And two of the readers the plan classes as CLI readers are also reached from web GETs.
>
> **How I established the map:** I grepped each reader's name across `swing/` (`--include=*.py`) and then read each hit. The grep only gives a lower bound; the reads are what establish the set.
>
> 1. `compute_hypothesis_progress_breakdown` (swing/journal/stats.py:334).
>    - It calls `compute_tripwire_status` inside its `for h in hypotheses` loop (stats.py:374, :416), so it reaches the verdict through another P35 reader.
>    - If both functions call `tier2_cohort_exclusions`, one journal-review invocation runs the replay 1+H times. The registry holds five rows (docstring at stats.py:341-343).
>    - Consumers:
>      - the CLI `journal review` (cli.py:1908).
>      - WEB: the dashboard, via `build_recommendation_progress` (dashboard.py:239), called at dashboard.py:559 and :1204.
>      - WEB: the trade-entry VM (web/view_models/trades.py:575 -> recommendations/hypothesis_prefill.py:59 -> `build_recommendation_progress`).
>      - the CLI prefill (cli.py:795).
> 2. `compute_tripwire_status` (swing/recommendations/hypothesis.py:474).
>    - Consumers: `swing hypothesis list`, which calls it once per hypothesis (cli.py:4952-4956), so one command means H replays; `swing hypothesis status` (cli.py:4982), a second CLI surface that is not in the roster; and reader 1 above, which puts it on the dashboard and trade-entry web paths too.
> 3. `compute_tier_comparison` (swing/metrics/tier.py:625).
>    - Consumers are all web: the tier VM (tier_comparison.py:95); `compute_deviation_outcome` (tier.py:778), which feeds the deviation-outcome VM (:93); and the metrics index (index.py:259).
> 4. `build_hypothesis_progress_card_vm`.
>    - Consumers: the route at web/routes/metrics.py:293 and the metrics index (index.py:252).
>    - So one metrics-index GET runs two budgeted replays: this card and the tier VM.
>
> **Why I stopped:**
>
> - **P1:** "once per invocation" is false for reader 1 unless reader 2 takes a pre-computed read.
> - **P2:** the dashboard and the trade-entry form are web GETs reaching readers 1 and 2. The plan classes those as CLI readers with no budget.
>   - Each git call is bounded by `GIT_TIMEOUT_SECONDS = 10.0`, so a slow git holds the dashboard for rows x calls x 10 s. That is exactly what A2-97b guards against on the card.
>   - The dashboard also displays N (`hypothesis_progress_n`, dashboard.py:468) with no exclusion line. That is the "silently uncounted" case F10 forbids, on the most-loaded page.
> - **P3:** `hypothesis list` fans out to H replays. It is also unclear whether its exclusion line prints per hypothesis row or once, and `hypothesis status` is an unrostered surface.
> - **P4 (minor):** tier.py would hard-code the web budget constant. That is true today (every consumer is web), but it ties `swing/metrics` to a web constant.
>
> **Options:**
>
> - **(a) Four call sites, with the read and the budget threaded through.** Recommended.
>   - `compute_tripwire_status` takes an optional `cohort_read: Tier2CohortRead | None = None` and calls `tier2_cohort_exclusions` only when it is None.
>   - `compute_hypothesis_progress_breakdown` calls it once and passes the read into every `compute_tripwire_status`.
>   - `budget_seconds` is threaded through `compute_hypothesis_progress_breakdown` and `build_recommendation_progress`: the dashboard and the web trade VM pass `WEB_REPLAY_BUDGET_SECONDS`; the journal review and CLI prefill pass None.
>   - The A2-75 set is exactly the four P35 functions.
>   - `hypothesis list` accepts H invocations, each with one ref resolution, because hoisting the call into the command would make a fifth caller.
>   - Open sub-question: must the dashboard and trade-entry surfaces render the named exclusion, or is naming carried only on the named surfaces?
> - **(b) Hoist the call to the surfaces.** Readers take a required `cohort_read`, and every entry point calls `tier2_cohort_exclusions` once with its own budget. Once-per-invocation and budget-by-surface are both clean, but the caller set becomes about 10 surfaces, not four. That contradicts "exactly the four P35 readers".
> - **(c) Take the four literally with no threading.** The journal review and dashboard run 1+H replays, and the dashboard and trade-entry paths are unbudgeted. Not recommended.
>
> **Rulers:** CHARC is primary (the caller set, threading the contract through the readers, and which surfaces count as web and get the budget). RD should be CC'd on the (a) sub-question: whether a web surface that displays N (the dashboard recommendation rows) must render the named exclusion. That is F10's "excluded and NAMED" measurement semantic.
>
> **Digest check (done, nothing edited):** `frozen_value_evidence_digest_parts()` gives 100 members and digest `f99090619b50...5193`, which matches `.3`. `tier2_cohort_exclusions`, `ReplayVerdict`, `_tier2_rows` and the `VERDICT_*` constants are NOT members. `REASON_WEB_BUDGET_EXHAUSTED` IS a member. So adding `Tier2CohortRead` and changing the return shape leaves the digest unchanged under every option, as long as that constant is not touched. No `.4` pair is expected.
>
> **Notes for Task 12's record:**
> - The P35 row in the plan ledger lists four readers and the one-hop surface `swing hypothesis list`. It does not record the reader-1 -> reader-2 nesting, the two web consumers, or `hypothesis status`.
> - It is the same kind of short count the recipe warns about: a grep bounds the family from below, and the fan-out only showed up when the callers were read.

### G-T10 (done) -- exec cell 10

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/0492607f-f8bc-42a1-a1f6-6b52b831c884/subagents/agent-ab728b5c18d19e905.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T05:14:56.008Z.

> GATE G-T10: Task 10 is done in one commit, `fc5df8632ee5d3d055ef455e3a413c1bdddd6a64` on 22-a2-exec (parent 047c7f8c). The wide run is green, the derivation digest did not move, and two facts differ from the rulings (see "Rulings encoded" 1 and 2). I read the rules from main at b16804722b1add5a64056b0599394f36a88cb2cb. The commit's trailers are empty (`git log -1 --format='%(trailers)'` printed `[]`), the worktree is clean, and I did no stash, amend, push, merge or mailbox post.
>
> **Results (final tree)**
> - tests/trades, data, cli, web, journal, metrics, recommendations (`-n 8`, not slow): 8506 passed, 9 skipped, 0 failed.
> - `ruff check swing/`: clean. `python scripts/schema_manifest.py --check`: clean (no schema change).
> - A2-60 and A2-89: green. Task set (the new cohort-readers file, the case closure, replay, correction service): 236 passed.
>
> **Red, then green**
> - First run at `-n 0`, before any code: 110 collected, 73 failed, 37 passed.
> - In the new file, 66 failed, each for the expected reason:
>   - 24 `AttributeError`: `tier2_excluded` missing on `TripwireStatus`, `HypothesisProgress`, `CohortStatistics` and `CohortProgressVM`.
>   - The named lines were missing from `journal review`, `hypothesis list`, `hypothesis status`, the card page and the tier page.
>   - The marker was missing on `/` and on the deviation page.
>   - Invocation counts read `[]`, because no reader called the read yet (web expected `[2.0]` and `[2.0]*3`; CLI expected `[None]` and `[None]*5`).
>   - The prefill raised `TypeError` on the new `budget_seconds` argument; `Tier2CohortRead` did not exist; code indexed a bare dict.
>   - A2-97c finished in 0.02 s with 0 git calls (no replay at all).
> - In the edited replay tests, 6 failed: bare dict (`.exclusions` missing) or `Tier2CohortRead` missing.
> - A2-75 failed: the caller set was empty, the test expected the four readers.
> - The 11 new tests that passed before the code are all zero-exclusion "must be absent" cases. I checked them by mutation (M3, M7 below).
>
> **Mutations** (each run on the relevant tests, then restored and confirmed byte-identical)
>
> | # | Wrong implementation | Result |
> |---|---|---|
> | M1 | Excludes a row because it has an observation | 10 red |
> | M2 | Ignores observations | 10 red |
> | M3 | Always renders the marker | 4 red |
> | M4 | Counts unverifiable as excluded | 4 red |
> | M5 | Breakdown does not pass its read down | journal review invocation test red, zero-row and one-row |
> | M6 | hyp-recs section passes no budget | 2 red |
> | M7 | Always renders the lines | 10 red |
> | M8 | CLI reader leaks the web budget | A2-97c and CLI invocation tests red |
>
> **Tests written after the code**
> - `/hyp-recs/refresh` in the invocation table and in the marker tests. I found this route through M6. It is checked by M6 (2 red) and by M3/M4 (its admit and unverifiable cases red).
> - Renames for A2-08's rule of exactly one implementing test per roster id; test bodies did not change:
>   - `test_a2_92_journal_review...` became `test_journal_review_renders_the_line_under_its_cohort_only`.
>   - `test_a2_94_card_vm...` became `test_card_vm_counts_from_exclusions_and_names_both`.
>   - The two combined A2-94/A2-95 functions were split into `test_a2_94_the_card_page...` and `test_a2_95_the_tier_page...`. Each is parametrized over the four states plus `zero`, with the same assertions as before.
> - The registry (`tests/trades/case_registry_22a2.py`) now marks A2-91 through A2-97, A2-97b and A2-97c as landed; only A2-98 to A2-104 (Task 11) remain pending.
>
> **A2-75 caller set as encoded** (exact, pinned both ways)
> - `swing.recommendations.hypothesis:compute_tripwire_status`
> - `swing.journal.stats:compute_hypothesis_progress_breakdown`
> - `swing.metrics.tier:compute_tier_comparison`
> - `swing.web.view_models.metrics.hypothesis_progress_card:build_hypothesis_progress_card_vm`
>
> The `replay_verdict` callers are unchanged: `tier2_cohort_exclusions` and `read_provenance_corrections`.
>
> **Digest:** unchanged. Still 100 members, `f99090619b50...5193`, version `.3`, and no `.4` pair. `Tier2CohortRead`, `tier2_cohort_exclusions` and the two render helpers are not closure members; `REASON_WEB_BUDGET_EXHAUSTED` is a member and was not touched. I checked membership before editing.
>
> **Shape shipped**
> - `Tier2CohortRead(exclusions, observations)` is a frozen dataclass with two render-only helpers, `excluded_among` and `observed_among`. Count logic reads `.exclusions` only.
> - Two pure helpers live in `frozen_value_evidence.py`:
>   - `tier2_cohort_lines` renders `tier-2 not counted: trade N <verdict> (<reason>)` and `tier-2 counted with observation: trade N (<obs>)`.
>   - `tier2_count_marker` renders `(1 excluded: see <surface>)` or `(1 unverifiable: ...)`, and nothing at zero.
> - Readers filter in Python; no `NOT IN` SQL.
> - Each reader's own view model or dataclass gets its field with a default; no base-layout field was added.
> - `compute_tripwire_status(cohort_read=None)` reads only when handed none. The breakdown reads once and passes that read into every hypothesis.
>
> **Rulings encoded, and facts that differ from them**
> 1. **The metrics index makes 3 invocations, not 2.** The deviation-outcome card also reaches `compute_tier_comparison`, through `compute_deviation_outcome`. The test pins 3. At one tier-2 row the worst case is about 3 × (2 s + one call timeout), not the ≤ 4 s CHARC declared. CHARC should confirm or rule differently.
> 2. **More web callers than CHARC listed now pass the web budget,** by the ruling's own rule: the deviation-outcome view model (`compute_deviation_outcome` now takes `budget_seconds`), the metrics-index card extractor, and `/hyp-recs/refresh`. Every web route is pinned at 1 invocation with the web budget in both the zero-row and one-row states: `/`, `/hyp-recs/refresh`, the card page, the tier page, the deviation page, and `/trades/entry/form`.
> 3. **Marker surfaces (RD G-T10-2):**
>    - The marker appears on the dashboard hyp-recs row (on `/` and `/hyp-recs/refresh`), the deviation-outcome N ("see tier comparison") and `hypothesis status`.
>    - My reading of RD's count rule: the metrics-index cards show an expectancy, a delta %, and a count of registered cohorts, none of them a cohort N, so they get no marker. RD should confirm.
>    - The trade-entry prefill renders no number, so it renders nothing.
> 4. **`hypothesis status` prints the marker beside N and the named lines below it.** CHARC's (4) says "the named line"; RD says full names should not be duplicated outside the four named surfaces. RD and CHARC should reconcile this if they disagree.
> 5. **In-flight trades:** a tier-2 exclusion also removes the trade from the in-flight "(+K in flight)" count, since it is the same cohort question. The breakdown names excluded trades whether closed or in flight.
> 6. **Tier page:** the tier-2 exclusion runs before the unresolved-discrepancy filter, so `excluded_trades_count` still counts only discrepancies.
> 7. **`hypothesis list`:** H = 5 invocations, with lines printed once under each hypothesis's own row.
>
> **Notes for Task 12's record**
> - **Cohort counts outside the four readers.** Other code builds cohort counts without the tier-2 read: `swing/metrics/process.py` (`list_closed_trades_for_cohort` at :590 and :598) and `trade_process_card.py:161` (`count_per_cohort`). I did not touch them; wiring them in would create a fifth caller. They need a disposition: commission, bank with an owner, or decline with a ground.
> - **Test world.** Trade 25 is closed by one exit fill, and a second closed H1 trade (26) sits beside it, so N reads 2 when admitted and 1 when excluded. Web tests copy the world's DB into a real config and point `EVIDENCE_REPO_DIR` at the git world.
> - **Slow tests.** A2-97b and A2-97c use the real 2.0 s web budget and each take about 3 s.
> - **No Codex review ran in this unit**, so there is no spend line; the brief did not call for one.
>
> Files changed: 17 under `swing/` (5 templates included) and 4 under `tests/`, plus the new `tests/trades/test_22a2_cohort_readers.py`.

### G-T11 -- exec cell 11

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/0492607f-f8bc-42a1-a1f6-6b52b831c884/subagents/agent-a518eefad1996d4d5.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T05:39:34.552Z.

> GATE G-T11: EXECUTING cell 11, 22-A2 Task 11. The unit is committed, and I have stopped here.
>
> **Commit:** `9a1f66381a9f1ee66f937a1cee1267820c0fd4c6`, `test(trades): Task 11 -- the trade-25 acceptance case end to end (A2-98..A2-104)`.
> - Its parent is `d973fd74`. Your three ledger commits (`3439ed13`, `6ab2523f`, `d973fd74`) landed under it while I was working.
> - It touches two files only: `tests/trades/test_22a2_acceptance_trade25.py` (new, 422 lines) and `tests/trades/case_registry_22a2.py` (one line: the landed range goes from 1..97 to 1..104, so `PENDING` is now an empty set).
> - Trailers: `git log 1bdb13e2..HEAD --format='%H%n%(trailers)'` prints empty for all four commits. Working tree is clean. No push, merge or amend, and I did not run any stash command.
> - I read the rules from the main copy at `a4ac72ee47aa4ec992daaba46e52377973e645bb`.
>
> ## Red first, then green (all runs at `-n 0`)
> - **The only real red:** I marked A2-98..A2-104 landed in the registry before writing any test. A2-08 then went red for the expected reason: `A2-98 .. A2-104: 0 implementing tests`, 7 ids.
> - **Then I wrote the tests.** The first run had one failure, in A2-98, and it was my bug: the stored blob is `json.dumps(sort_keys=True)`, so asserting key order was wrong. I changed it to compare sorted key sets.
> - **Every new roster test then passed on its first run.** That is 11 collected: A2-99 is one function with five parametrized legs. They pass because Tasks 3-10 already shipped the production code. I did not fake a red for any of them. Each one is proved by a mutation instead.
>
> Every mutation was applied by a scratch harness and then restored. I checked the restore by sha256 each time, and `git hash-object` on all five mutated files matched the values I recorded before starting. In the list, "red" means that test failed under the mutation.
> - **M1 (A2-98):** changed `latched_origin.py` to `elif False and both_pre and tier2 is not None:`. Red: the ladder REFUSED with `pre_barrier_unproven`, which is the roster's stated pre-state.
> - **M2 (A2-99):** made all four criteria checks in `evaluate_conjunction` no-ops at once. Exactly the 4 criterion legs went red and the trigger leg stayed green. Each red leg lost its named reason: the refusal fell through to a later check instead (`remote_ref_attestation`, `author_date_before_fill`, `KeyError: 'pivot'`, `interval_segment_order`).
> - **M3 (A2-99 trigger leg, test-side):** removed the `del blob["interval"]`. Red: `DID NOT RAISE IntegrityError`.
> - **M4 (A2-100):** set `is_ancestor = True` in `read_artifact_facts`. Red: the rewritten leg read `assert 2 == (2 - 1)`.
> - **M4b (A2-100):** added `descendant_count` to `VERDICT_BEARING_KEYS`, i.e. growth treated as staleness. Red: the grown leg read N=1, with trade 25 excluded as `descendant_count_mismatch`.
> - **M5 (A2-101, re-asserts A2-60):** dropped `rung9_pre_barrier_candidate` from `TIER2_TRIGGER_PREDICATES`. Red: "trigger predicate with no service check".
> - **M6 (A2-102, re-asserts A2-09):** added a comment line inside `test_a_latched_fill_labels_from_the_fire_case_1`. Red: the six-case functions drifted.
> - **M7 (A2-103, re-asserts A2-23 + A2-25):** dropped `LATCH_TIER2` from `PROVENANCE_ADMISSION_TIERS`. Red: the SQL set is not equal to the Python set.
> - **M8 (A2-104):** changed one byte in the line-57 fixture (53.98 to 53.99). Red at byte index 49.
>
> **The re-assertion tests** are A2-101 (= A2-60), A2-102 (= A2-09) and A2-103 (= A2-23 + A2-25). Each one imports and calls the original test inside its own body, so the assertion cannot drift from the original and pytest does not collect it twice.
>
> ## Results
> - `tests/trades tests/data tests/cli -m "not slow" -n 8`: **5228 passed / 9 skipped / 0 failed** (268 s).
> - `ruff check swing/`: clean.
> - `python scripts/schema_manifest.py --check`: clean.
> - The acceptance file at `-n 0`: 11 passed, 0 skipped. 9f315cc6 is present in this clone, so A2-104 ran.
> - The closure and registry test A2-08 is green.
>
> ## Digest check
> - The derivation digest did not move: version `2026-09-23.3`, **100 members**, digest `f99090619b500e866bf104556bb419b7c26ab85e1cc82ce6e6ddc4b0d1eb5193`, the same value G-T9F recorded.
> - `tests/trades/test_22a2_g_t7_followon.py`: 12 passed.
> - `git diff 1bdb13e2..HEAD -- swing tests/fixtures` is empty. No production code or fixture changed.
>
> ## Live-copy evidence (not committed)
> Scratch location: `C:\Users\rwsmy\AppData\Local\Temp\claude\C--Users-rwsmy-swing-trading\0492607f-f8bc-42a1-a1f6-6b52b831c884\scratchpad\livecopy\`.
>
> **Step 1: stat, then copy.**
> - Live before: `size=1656672256 mtime_ns=1790135382505575400`.
> - Side files at that moment: `-wal` size 0, mtime_ns 1790140284748690400; `-shm` size 32768, mtime_ns 1790140598892166400; no `-journal`.
> - Copy method: `sqlite3.connect('file:<live>?mode=ro', uri=True).backup()` into the new file `livecopy\data\swing.db`.
> - Copy: 1656672256 bytes, `schema_version` 38, `integrity_check` ok, 28 trades, 1 provenance row.
> - Trade 25 on the copy: `(25,'OII',None,None,'manual_off_pipeline','reviewed')`.
>
> **Step 2: db-migrate the copy.**
> - Every one of the nine `[paths]` entries points into the scratchpad. I checked this on the config file and again on the config as `swing.config.load` resolved it. `USERPROFILE` and `HOME` were set to a scratch `home`.
> - I copied OII's three price-cache files into the scratch prices-cache. Their bytes and mtimes are unchanged afterwards.
> - Resolver proof, from the same process that ran the CLI: interpreter `C:\Python314\python.exe`, `swing.__file__ = ...\.worktrees\22-a2-exec\swing\__init__.py`, `EXPECTED_SCHEMA_VERSION 39`. The CLI was run through `runpy.run_module('swing.cli', run_name='__main__')`, which is equivalent to `python -m swing.cli`.
>
> Migrate output, verbatim:
> ```
> Backup (pre-migration gate, integrity-verified): C:\Users\rwsmy\AppData\Local\Temp\claude\C--Users-rwsmy-swing-trading\0492607f-f8bc-42a1-a1f6-6b52b831c884\scratchpad\livecopy\data\backups\swing-pre-22a2-migration-20260923T053644Z.db
> DB at C:\Users\rwsmy\AppData\Local\Temp\claude\C--Users-rwsmy-swing-trading\0492607f-f8bc-42a1-a1f6-6b52b831c884\scratchpad\livecopy\data\swing.db - schema version 39
> ```
> - **Backups written:** exactly one file, the gate image `data\backups\swing-pre-22a2-migration-20260923T053644Z.db` (1656672256 bytes, schema 38). There is no second image anywhere, including the DB's parent directory `data\`.
> - The `-shm` and `-wal` files next to that backup were created by my own later read probe, not by the migrate.
> - **Nothing was written outside the scratchpad.** I snapshotted every file under `~/swing-data` to depth 2, plus the three real OII archive files (9672 files), before and after. Nothing was added, removed or changed.
> - **After migrate:** `schema_version` 39 and `integrity_check` ok.
>
> **Step 3: the dry run, on the migrated copy with the same scratch config.**
> - The CLI has no evidence-repo option. In the same process I set `fve.EVIDENCE_REPO_DIR = C:\Users\rwsmy\swing-trading` (the real repo); by default it resolves to the worktree root.
> - The evidence file was built from the real repo: `artifact_commit_sha 9f315cc64a8f171049b510021e6418bc261c50b7`, `artifact_path docs/rd-state.md`, and line 57 (1015 bytes, sha256 `abfd428a...c5407`).
> - Exit code 0. **ADMIT.** Output, verbatim:
> ```
> DRY RUN -- nothing written. trade 25 (OII, state=reviewed).
>   cited candidates row          12284 (action session 2026-08-10)
>   cited daily_recommendations   169 (action session 2026-08-10)
>   cited evaluation run          136
>   cited pipeline run            150
>   authoritative entry fill      48 (session F = 2026-08-17)
>   hypothesis                    1 (A+ baseline), status-history row 1
>   status window (UTC)           2026-08-08T03:30:02 -> 2026-08-08T03:39:07
>   status window (raw, local)    2026-08-07T17:30:02 -> 2026-08-07T17:39:07
>   derivation rule               2026-08-26.2
>   admission tier                latch_ladder_tier2
>   cited latch link              1 (broker order 1007523377009)
>   cited latch intents           place 1, validity 2
>   probe admission basis         armed
>   criterion 1 ancestor of refs/remotes/origin/main at a4ac72ee47aa4ec992daaba46e52377973e645bb (commit 9f315cc64a8f171049b510021e6418bc261c50b7): PASS
>   criterion 2 authored 2026-08-10 (America/New_York) before the fill session 2026-08-17: PASS
>   criterion 3 quoted text carries ticker OII, action session 2026-08-10, pivot 53.98, invalidation 41.42: PASS
>   criterion 4 recorded 2026-08-10T12:41:33Z after the fire's upper bound 2026-08-08T03:39:07Z: PASS
>   uncovered window              writer_absence_only 2.38 days (2026-08-08T03:39:07Z to 2026-08-10T12:41:33Z); match_only 22.89 days (2026-08-10T12:41:33Z to 2026-09-02T10:03:33Z); covered from 2026-09-02T10:03:33Z
>
>   field                        before -> after
>   trades.hypothesis_label      None -> 'A+ baseline (aplus)'
>   trades.candidate_id          None -> 12284
>   trades.trade_origin          'manual_off_pipeline' -> 'pipeline_aplus'
>
>   V1 records provenance ONCE per trade; there is no supported re-correction path, so THIS reading is the decision point.
> ```
>
> **Step 4: re-stat live.**
> - `AFTER size=1656672256 mtime_ns=1790135382505575400`. **Identical to step 1.**
> - `-wal` is unchanged. The `-shm` mtime moved from 1790140598892166400 to 1790141717951818100. My snapshot taken right after the step-1 copy already held the new value, and it did not change through the migrate or the dry run. So my own `mode=ro` open in step 1 moved it, which is the documented CLAUDE.md `-shm` behaviour.
> - Nothing outside the scratchpad changed. `git status` on main shows only the untracked file that was already there when this session started.
>
> ## Where the plan and the landed rulings differ, and what I encoded
> 1. **Which world builder.** The plan names `build_world` (`test_22a_task9_entry_wiring.py:67`). That builder uses a synthetic FTRE-shaped fire (run 121). I used `tests/_tier2_world_22a2.build_pre_barrier_world` plus `t25_cfg` instead. They carry trade 25's real row ids, mint the link the same pre-barrier way, and `t25_cfg` writes its closes with `_latch_probe_world_22a.write_closes`. The git world and the H1-count harness are reused by import (`_world`, `ticking_clock`, `_rd_state_bytes`, `_pivot_absent_line`), not copied.
> 2. **The 22.89 d interval cannot be reproduced in a test world.** Migration 0037 stamps the epoch's `applied_at` when the world is migrated, the row is immutable, and the citation trigger requires `barrier_armed_at.raw` to equal it. So A2-98 checks 205,346 s / "2.38 days" on the row the service actually wrote. It gets the 22.89 d (1,977,720 s) by rebuilding the interval from that row's recorded endpoints with the live barrier `2026-09-02T10:03:33Z` swapped in. The live dry run above shows 22.89 d on the real barrier.
> 3. **A2-99's five-cent-pivot leg changes the evidence, not the candidate.** The quoted line says 53.93 while candidate 12284 stays at 53.98, the same shape as A2-73. A2-49 changes the candidate instead. I did not do that here because I expect the link's frozen pivot would then differ from the live pivot and the probe would refuse before the conjunction runs. That is my reasoning, not something I measured.
> 4. **A2-99's trigger leg runs through the service.** I wrap `fve.evaluate_conjunction` so it returns an admitted blob with no interval, which bypasses the service's own check. `correct_cohort_provenance` then raises a raw `sqlite3.IntegrityError` ("citation graph"). Nothing is written and no transaction is left open. The test also includes a control: the same wrapped path with the interval intact inserts normally.
> 5. **Rulings applied:**
>    - A2-98 pins derivation version `.3`.
>    - A2-100 reads `Tier2CohortRead.exclusions` (G-T10).
>    - Under G-T7F-AMEND and G-T7FE-B, the rewritten case reads stale with reason `criterion 1: not_ancestor_of_origin_main` and no derivation-version token, because the version has not moved.
>    - A2-104 asserts 1005 chars, per the G-T4 correction; plan section 4 still says 1006.
>
> ## Notes for Task 12's record
> - **a.** Measured here: `db-migrate` wrote ONE backup, the gate image in `backups_dir`, echoed on the console. This confirms the plan's side-flag that the CLAUDE.md "`swing db-migrate` writes TWO backups" gotcha is stale.
> - **b.** `PENDING` in the registry now evaluates to an empty set. Task 12 removes the construct.
> - **c. Unrelated to this arc:** live data has two existing FK violations, `reconciliation_discrepancies` rowids 72 and 73 pointing to `cash_movements` (parent id 1). They are the same in the v38 backup image, so 0039 did not cause them. They need a disposition.
> - **d.** The dry run found `refs/remotes/origin/main` at `a4ac72ee`. At the post-merge witness, `EVIDENCE_REPO_DIR` defaults to the root of whichever checkout is running (main, run from main), so no override is needed there.
> - **e.** When the citation trigger aborts, the service lets the raw `sqlite3.IntegrityError` escape instead of wrapping it in `CohortProvenanceCorrectionError`. This can only happen if the service's own check fails first, which is the authorize-then-abort design. I am recording it, not asking for a change.
> - **f.** The new test file has 3 ruff F811 hits from the `ticking_clock` fixture import. Its two sibling files, `test_22a2_correction_service.py` and `test_22a2_replay.py`, already use the same pattern (27 hits between them). Test-file lint is out of scope; `swing/` is clean.
>
> I found no production defect and no new design fork.
>

### G-F4 -- exec cell 12

Source: `C:/Users/rwsmy/.claude/projects/C--Users-rwsmy-swing-trading/0492607f-f8bc-42a1-a1f6-6b52b831c884/subagents/agent-afb3dbd7827207768.jsonl`, assistant `SubagentHandback` tool-use `input.message`, timestamp 2026-09-23T05:48:44.189Z.

> GATE G-F4: unit 1 (the G-T10-F4 follow-on) is committed. I have stopped and am waiting to be resumed for unit 2 (Task 12).
>
> I read the rules from main at `a4ac72ee47aa4ec992daaba46e52377973e645bb` (C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md, all 162 lines). Worktree HEAD was 954a7279 before the commit.
>
> **Commit:** `3b696fcc42dabda899628c54f537b3e1c92a0d8a`, `fix(cli): G-T10-F4 follow-on (RD) -- hypothesis status renders the named lines and no marker`. `git log -1 --format='%(trailers)'` prints empty and the worktree is clean afterwards. Only `swing/cli.py` and `tests/trades/test_22a2_cohort_readers.py` were staged, by name.
>
> **Red first:**
> - In `tests/trades/test_22a2_cohort_readers.py`, `test_hypothesis_status_carries_the_marker_and_the_named_line` is rewritten and renamed to `test_hypothesis_status_renders_the_named_lines_and_no_marker`. The old name described the behaviour the ruling removes, so I renamed it. Nothing outside the file cites the old name; I checked with a grep over `tests/` and the arc's plan files.
> - It keeps the same four states (rewritten, unverifiable, admit, moved). It now asserts that `see hypothesis list`, `(1 excluded` and `(1 unverifiable:` all appear nowhere in the output.
> - For one excluded row, the sample line is exactly `1` and the next line is the STALE line. For one unverifiable row, the sample is `1` and the next line starts with the unverifiable prefix. For the admit and moved states nothing changed.
> - Run with `-n 0`: **2 failed, 2 passed**. Rewritten and unverifiable failed at `assert "see hypothesis list" not in out`; the output showed `(1 unverifiable: see hypothesis list)` on the sample line, so the marker was present, which is the expected reason. Admit and moved passed because nothing is excluded, so their behaviour is unchanged.
>
> **Green:**
> - In `hypothesis_status_cmd` in `swing/cli.py`, I removed the `tier2_count_marker` import, the marker call and the marker append. The sample line is now just `Current sample: {N}`, and the `tier2_cohort_lines` loop is kept. The comment above it now describes what the code does today.
> - Run with `-n 0`: **4 passed**.
> - Nothing else changed: no reader, digest, budget or other surface. `tier2_count_marker` is still used by `swing/metrics/tier.py` and `swing/web/view_models/dashboard.py` (grep).
>
> **Results:**
> - `python -m pytest tests/trades tests/cli -m "not slow" -n 8 -q`: `3291 passed, 8 skipped, 683 warnings in 196.75s (0:03:16)`. The 8 skips are 7 in `test_22a_envelope_canonicality_sweep.py:191` and 1 in `test_schwab_cash_ingestion.py:246`, all existing.
> - `ruff check swing/`: `All checks passed!`
> - The digest stays at `.3`. The pins `"2026-09-23.3"` (`test_22a2_acceptance_trade25.py:193`, `test_22a2_g_t7_followon.py:68`) pass in that run and no digest-member file was touched. I did not count the 100 members separately; my evidence is that these digest pins pass and that this commit touches only those two files.
>
> Trailers are empty for the one commit this unit made.
