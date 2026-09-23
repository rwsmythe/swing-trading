# Phase 22 arc 22-A2 -- PROOF MACHINERY (tier-2 admission class + trade 25's correction) -- PLAN

- **Ledger (arguments, rulings, premises, accepted-limitation REASONS, review history):**
  `docs/superpowers/plans/2026-09-22-phase22-arc-a2-proof-machinery.ledger.md`. This plan is a task
  ladder + test roster ONLY. Where this plan and a ruling (R0.7-R0.12) differ, the RULING governs;
  report the difference, do not resolve it silently.
- **Brief:** `docs/phase22-arc-a2-commissioning-brief.md`. **Doctrine:** the 22-A plan's S12
  (`docs/superpowers/plans/2026-08-24-phase22-arc-a-entry-path-order-mandate-binding.md`
  :4057-4160), S4.3a (:2602), lifted as ruled.
- **Base:** `c212238a` (branch `22-a2-plan`). Premise file:line anchors were read at `e2b4d9c3`;
  only ledger commits landed since. **Re-ground each anchor before editing** (line numbers drift).
- **Executing cell:** `implementer-opus-high` (schema migration on the audit table of record).
  Reviewer A at `strong`; Reviewer B at the orchestrator's gate (production code under
  `swing/trades` + `swing/data`).
- **Live acceptance case:** trade 25 (OII) ONLY. Trades 19/24/28 stay NAMED-PENDING (F1.1 = b,
  F3.1 = b). No path for them is built here.

## 0. Carve-out and file set

**`swing/data` carve-out (this arc, spec-scoped):**
- `swing/data/migrations/0039_provenance_corrections_tier2.sql` -- NEW (the rebuild).
- `swing/data/db.py` -- `EXPECTED_SCHEMA_VERSION` 38 -> 39; `PHASE22_ARC_A2_PRE_MIGRATION_EXPECTED_TABLES`;
  one `BackupGateSpec(38, ...)` row; one `_bind_gate_wrapper(38)` wrapper.
- `swing/data/models.py` -- `PROVENANCE_ADMISSION_TIER_LATCH_TIER2`, three-valued
  `PROVENANCE_ADMISSION_TIERS`, `PROVENANCE_TIER2_EVIDENCE_FIELD`, `ProvenanceCorrection` seventh field
  + three-way paired-NULL validator.
- `swing/data/repos/provenance_corrections.py` -- insert column list + row mapper (#11 read+write in
  one task).

**`swing/trades` carve-out:**
- `swing/trades/frozen_value_evidence.py` -- NEW (F4 = a): git preflight, conjunction evaluation,
  blob builder, `replay_verdict`, `tier2_cohort_exclusions`. NO DB write, NO transaction.
- `swing/trades/latched_origin.py` -- rung-9 escape seam, verdict vocabulary, tier-2 probe-blob
  version, `LatchedProvenance.frozen_value_evidence`, one decline reason.
- `swing/trades/cohort_provenance_correction.py` -- wiring (tier detection, deferred preflight,
  single `applied_at` stamp, preview/result fields, drift-reader verdicts).

**Outside the carve-out (reader + CLI surfaces F10 binds):** `swing/cli.py` (option, output, drift
reader rendering, hypothesis list exclusion line); `swing/journal/stats.py`; `swing/metrics/tier.py`;
`swing/recommendations/hypothesis.py`; `swing/web/view_models/metrics/hypothesis_progress_card.py`
(+ the template(s) rendering the card and the tier surface -- found by the executing cell, named in
its report). **Fixture:** `tests/data/schema_manifest_head.tsv` (regenerated in the migration commit).

**NOT touched:** `record_entry` / the entry path (byte-unchanged; the escape is never passed there);
0036/0037/0038 files; `latch_order_mandate_links`; `candidates*`; `LATCH_FREEZE_TIERS` (stays
two-valued, F2 = b).

## 1. Constants and vocabulary (named once; every task uses these spellings)

| name | value | home |
|---|---|---|
| `PROVENANCE_ADMISSION_TIER_LATCH_TIER2` | `"latch_ladder_tier2"` | models.py |
| `PROVENANCE_ADMISSION_TIERS` | `{last_word, latch_ladder, latch_ladder_tier2}` | models.py |
| `PROVENANCE_TIER2_EVIDENCE_FIELD` | `"cited_frozen_value_evidence_json"` | models.py |
| `AUTHORIZATION_VERDICT_PASS` / `_ESCAPED_BY_TIER2` | `"pass"` / `"escaped_by_tier2"` | latched_origin.py |
| `AUTHORIZATION_VERDICTS` | frozenset of the two | latched_origin.py |
| `LATCH_PROBE_EVIDENCE_VERSION` | `"2026-08-25.1"` UNCHANGED (latch_ladder blobs) | latched_origin.py |
| `LATCH_PROBE_TIER2_EVIDENCE_VERSION` | `"2026-09-23.1"` (probe blob of a tier-2 row) | latched_origin.py |
| `FROZEN_VALUE_EVIDENCE_VERSION` | `"2026-09-23.1"` (seventh-column blob) | frozen_value_evidence.py |
| decline reason `tier2_evidence_refused` | joins the decline-reason roster (22-A task 8 closure) | latched_origin.py |
| `GIT_TIMEOUT_SECONDS` | `10.0` | frozen_value_evidence.py |
| `REMOTE_REF` | `"refs/remotes/origin/main"` | frozen_value_evidence.py |
| `EVIDENCE_REPO_DIR` | repo root of the package (`Path(__file__).resolve().parents[2]`) | frozen_value_evidence.py |
| `RULING_CITATION` | module constant text naming S12.1 + RD 2026-08-24 + R0.7-R0.12 (F9 sub-choice) | frozen_value_evidence.py |
| `ANCHOR_STRENGTH` | `"remote_replicated_ancestry"` | frozen_value_evidence.py |
| `TIME_ANCHOR_RESIDUAL` | constant text: author/committer dates are caller-settable; ancestry is the anchor (S12.1 #7) | frozen_value_evidence.py |
| `EVIDENCE_FILE_KEYS` | `("artifact_path", "artifact_commit_sha", "quoted_text")` (F9) | frozen_value_evidence.py |
| replay verdicts | `"ADMIT"`, `"tier2_evidence_stale"`, `"tier2_unverifiable"` | frozen_value_evidence.py |

**Tier-2 refusal vocabulary** (the `field`/`reason` a refusal NAMES; F6, F7, F13): selection --
`evidence_file_malformed`, `artifact_unreadable`, `quoted_text_not_in_artifact`,
`quoted_text_not_one_line`; criterion 1 -- `not_ancestor_of_origin_main`; criterion 2 --
`recorded_on_fill_session`, `recorded_after_fill_session`; criterion 3 -- `ticker`,
`action_session`, `pivot`, `invalidation` (in THAT order); criterion 4 -- `window_negative`,
`window_indeterminate`; process -- `tier2_unverifiable` (git timeout / git missing / no `REMOTE_REF`
/ git exit other than 0 or 1). Evaluation order: selection -> 1 -> 2 -> 3 (ticker -> action_session
-> pivot -> invalidation) -> 4; the first failure speaks.

## 2. The seventh-column blob (`cited_frozen_value_evidence_json`) -- CLOSED key roster

Every key required; `json_remove(<blob>, <every key>) = '{}'` closes it. Values the service
COMPUTES unless marked (sel) = operator selection (F9).

| key | type | value / source | SQL binding in the trigger |
|---|---|---|---|
| `evidence_version` | text | `FROZEN_VALUE_EVIDENCE_VERSION` | `= '2026-09-23.1'` |
| `ruling_citation` | text | `RULING_CITATION` | type only |
| `verification_method` | text | constant describing the four checks | type only |
| `evaluated_at` | text | the single `applied_at` stamp | `= NEW.applied_at` |
| `artifact_path` (sel) | text | from the evidence file | type only |
| `artifact_commit_sha` (sel) | text | from the evidence file; 40 lowercase hex | `length = 40 AND NOT GLOB '*[^0-9a-f]*'` |
| `quoted_text` (sel) | text | byte-substring of `git show sha:path`, ONE line | no `char(10)`, no `char(13)` |
| `quoted_ticker_text` | text | the token found (= candidate ticker) | `= ca.ticker` AND `instr(quoted_text, .) > 0` |
| `quoted_action_session_text` | text | ISO `YYYY-MM-DD` if present as a token, else `MM-DD` under the year rule | `= er.action_session_date` OR (`= substr(er.action_session_date, 6)` AND `substr(author_date_et,1,4) = substr(er.action_session_date,1,4)`); AND `instr > 0` |
| `quoted_pivot_text` | text | `f"{round(ca.pivot, 2):.2f}"` found as a token | `instr(quoted_text, .) > 0` (F8, REQUIRED) |
| `quoted_invalidation_text` | text | `f"{round(ca.initial_stop, 2):.2f}"` found as a token | `instr(quoted_text, .) > 0` (F8, REQUIRED) |
| `live_pivot_raw` | real | `candidates.pivot` | `= ca.pivot` (plain identity, no rounding) |
| `live_invalidation_raw` | real | `candidates.initial_stop` | `= ca.initial_stop` |
| `pivot_equal_at_dp` / `invalidation_equal_at_dp` | integer | `1` (service verdict) | `= 1` |
| `compare_dp` | integer | `2` | `= 2` |
| `author_instant` | text | `git show -s --format=%aI sha` (offset kept) | type only |
| `author_date_et` | text | author instant -> America/New_York, `.date().isoformat()` (F7 a) | `< fill_session_date` (text compare of ISO dates; consistency only) |
| `committer_instant` | text | `%cI`; RECORDED, never verdict-bearing (F7 sub-choice) | type only |
| `fill_session_date` | text | the authoritative entry fill's session | `= NEW.entry_fill_session_date` |
| `resolved_remote_ref_sha` | text | `git rev-parse REMOTE_REF` at write | type only |
| `descendant_count` | integer | `git rev-list --count sha..<resolved>`; RECORDED | type only |
| `remote_ref_updated_at` | text/null | reflog instant of `REMOTE_REF` (encoding 5); null if none | type in (text, null) |
| `remote_ref_age_seconds` | integer/null | write instant minus the above; null if none | type in (integer, null) |
| `anchor_strength` | text | `ANCHOR_STRENGTH` | type only |
| `time_anchor_residual` | text | `TIME_ANCHOR_RESIDUAL` | type only |
| `interval` | object | F2.I (I-1) + (s1), below | closed; endpoints bound |
| `uncovered_window_prose` | text | rendered by the service (F9), never typed | type only |

**`interval` object (F2.I, I-1 + s1; encoding 4 supersedes the struck `uncovered_seconds` arithmetic):**
`{"endpoints": {E: {"raw": text, "utc": text, "clock_domain": text, "source": text}}, "segments": [...]}`
for `E` in:

| endpoint | `raw` source (SQL-bound) | clock domain | `utc` (service only) |
|---|---|---|---|
| `fire_lo` | `evaluation_runs.run_ts` (= `NEW.cited_run_ts_raw`) | `naive_local_pipeline` | `_to_utc_naive` (the ONE conversion authority, `cohort_provenance_correction.py:554`) |
| `fire_hi` | `pipeline_runs.finished_ts` (= `NEW.cited_pipeline_finished_ts_raw`) | `naive_local_pipeline` | same |
| `record_at` | the blob's own `author_instant` | `iso_offset` | offset-aware -> UTC |
| `barrier_armed_at` | `candidates_immutability_epoch.applied_at` (epoch_id 1) | `utc_z` | parsed |
| `read_at` | `NEW.applied_at` | `naive_utc_ms` | as stored |

`segments` = ordered list of `{"kind", "from", "to", "seconds"}`: `fire` = [fire_lo, fire_hi];
`writer_absence_only` = [fire_hi, record_at); `match_only` = [record_at, barrier_armed_at);
`covered` = [barrier_armed_at, read_at] iff the barrier is installed at evaluation (else kind
`uncovered_barrier_absent`). SQL binds each endpoint's `raw` to its source column and asserts the
four segment kinds are present in order; it recomputes NO duration and never reads `utc` (R8-03).
**Trade 25 (real values):** fire_lo `2026-08-07T17:30:02` -> `2026-08-08T03:30:02Z`; fire_hi
`2026-08-07T17:39:07` -> `03:39:07Z` (fire = 545 s); record_at `2026-08-10T02:41:33-10:00` ->
`12:41:33Z`; writer_absence_only = **205,346 s (2.3767 d -> "2.38 days")**; barrier_armed_at
`2026-09-02T10:03:33Z`; match_only = **1,977,720 s (22.8903 d)**; covered from `2026-09-02T10:03:33Z`
to read.

## 3. Migration 0039 -- outline and expected manifest delta (CHARC F12 = A, six conditions)

File `0039_provenance_corrections_tier2.sql`, `BEGIN; ... COMMIT;` (gotcha #9; runner holds
`foreign_keys=OFF`). Statement order (condition 3):

1. **Reversibility header (condition 5):** names the THREE textual edits (name; IN-list widened to
   `('last_word', 'latch_ladder', 'latch_ladder_tier2')`; `cited_frozen_value_evidence_json TEXT`
   appended as the LAST COLUMN, directly after `cited_latch_probe_json TEXT` and before the
   table-level CHECKs), the P28 gate row (`BackupGateSpec(38, "22a2", ...)`, pre 38 -> target >= 39), the
   seven objects dropped and re-created, and that a reverse is another rebuild to the v38 DDL (only
   legal while no `latch_ladder_tier2` row exists).
2. `CREATE TABLE provenance_corrections__0039 (<the STORED v38 DDL body, byte-copied from a fresh v38
   DB's sqlite_master.sql, with edits 2 and 3 applied>)`.
3. `INSERT INTO provenance_corrections__0039 (<the 40 v38 columns, explicit, incl.
   provenance_correction_id>) SELECT <same 40> FROM provenance_corrections;`
4. **Carry the AUTOINCREMENT counter by statement (encoding E-2):**
   `DELETE FROM sqlite_sequence WHERE name = 'provenance_corrections__0039';`
   `INSERT INTO sqlite_sequence(name, seq) SELECT 'provenance_corrections__0039', seq FROM
   sqlite_sequence WHERE name = 'provenance_corrections';`
5. `DROP TABLE provenance_corrections;` (takes its two indexes + four triggers).
6. `ALTER TABLE provenance_corrections__0039 RENAME TO provenance_corrections;`
7. Re-create VERBATIM (copy the text from its source migration, byte-for-byte):
   `ux_provenance_corrections_trade` + `ix_provenance_corrections_cited_candidate` (0036 :526-529),
   `trg_provenance_corrections_append_only_delete` (0036 :708), `trg_pc_no_replace` (0037 :2294).
8. `CREATE TRIGGER trg_provenance_corrections_append_only_update` = 0037 :2195 text + ONE added line
   `AND NEW.cited_frozen_value_evidence_json IS OLD.cited_frozen_value_evidence_json` (with `IS`).
9. `CREATE TRIGGER trg_provenance_corrections_citation_graph` = 0037 :896-2173 text with the Task-3
   edits (section 5, Task 3 step D) ONLY.
10. `UPDATE schema_version SET version = 39;` then `COMMIT;`.

**Expected D51 manifest delta (condition 4) -- exactly FOUR changed line pairs, ZERO deletions,
ZERO additions:** `# schema_version 38` -> `39`; `table provenance_corrections` (hash);
`trigger trg_provenance_corrections_append_only_update` (hash);
`trigger trg_provenance_corrections_citation_graph` (hash). The lines for
`ix_provenance_corrections_cited_candidate`, `ux_provenance_corrections_trade`, `trg_pc_no_replace`,
`trg_provenance_corrections_append_only_delete` hash IDENTICAL. Any other changed or deleted line is
an object the rebuild forgot. The diff is quoted in the merge request.

## 4. Rules every task obeys

- TDD: write the named failing test(s), run and SEE them fail for the stated reason, implement, SEE
  green, commit. Every discriminator states its pre-fix vs post-fix arithmetic (roster column).
- Fixtures from REAL emitter shapes: trade 25's measured values (ledger P2-P4, P8, P11, P24-P26, P31,
  P36) -- candidate 12284 (`pivot 53.97999954223633`, `initial_stop 41.41999816894531`, ticker `OII`,
  run 136, action session `2026-08-10`), rec 169, pipeline 150 (`finished_ts 2026-08-07T17:39:07`),
  link 1 (intent 2, order `1007523377009`, `pre_barrier_reconstructed`), fill 48 (session
  `2026-08-17`, 53.98 x 2, `schwab_auto`), epoch `(1, 13591, '2026-09-02T10:03:33Z')`. Never
  values built to satisfy the premise.
- Line-57 bytes: `tests/fixtures/tier2/rd_state_9f315cc6_line57.txt`, extracted once with
  `git show 9f315cc6:docs/rd-state.md` (BYTES, split on `b"\n"`, index 56), no trailing newline;
  **pinned: 1015 bytes, sha256 `abfd428aaa55e409fa1261f3c1813da8c1a2941621499ff581d81b37e96c5407`**,
  no `\r`. Tokens measured in it (char offsets): `2026-08-10` @16, `OII` @29, `53.98` @43/@434,
  `41.42` @457, `08-10` @21/@297/@470, `AMN` @405/@832, `40.50` @495, `37.89` @501.
- Every subprocess over repo content captures BYTES and decodes `utf-8` explicitly (cp1252 decode
  gotcha). Every git call carries `timeout=GIT_TIMEOUT_SECONDS`, `cwd=repo_dir`, and never runs inside
  a SQLite transaction (S12.1 #9).
- Live-DB reads, if any: plain `sqlite3` `file:...?mode=ro`, never `swing`'s `connect`. A probe that
  writes (the Demand-C dry-run) runs only on a `sqlite3.backup()` COPY under a scratch config.
- Commit discipline: conventional, NO trailers, no amend, no `--no-verify`; `git log -1
  --format='%(trailers)'` empty after each commit. Full fast suite green BEFORE Reviewer A.
- Naming vs versioning: HEAD-tracking tests edited to 39 keep their names in the migration commit;
  no rename sweep in that commit (CLAUDE.md version-mirror gotcha).

## 5. Task ladder

### Task 1 -- F2.T (t1): the barrier-drop scan (tests only)

**Files:** `tests/data/test_22a2_barrier_drop_scan.py` (new).
**Build:** a pure `scan_migrations(dirpath) -> list[Violation]` in the test module: for each file
`NNNN_*.sql` with `NNNN > 37`, strip `--` comments, then find (case-insensitive, `IF EXISTS` and
`"quoted"` identifiers tolerated) `DROP TRIGGER <n>` for `n in BARRIER_TRIGGER_NAMES` (IMPORTED from
`swing.data.repos.candidates_immutability_epoch`, never re-typed) and `DROP TABLE candidates` /
`DROP TABLE candidates_immutability_epoch` (the TWO named tables ONLY -- never "any DROP TABLE";
0039 drops `provenance_corrections`). A hit is a violation unless the same comment-stripped file
contains `INSERT INTO candidates_immutability_epoch_events` (the era record; encoding E-5). The
failure message cites RD's F2 re-open condition (era model mandatory before that migration merges).
**Acceptance:** A2-01..A2-07 green; the scan over the real `swing/data/migrations/` returns `[]`.

### Task 2 -- 22-A2 case registry, closure, and the 22-A six-case byte pin (tests only)

**Files:** `tests/trades/case_registry_22a2.py`, `tests/trades/test_22a2_case_closure.py` (new).
**Build:** `CASES_22A2: dict[str, str]` mapping every roster id `A2-NN` (section 6) to its test
module. Closure test: collect test function names across the 22-A2 test modules; every registry id
appears as a `a2_NN` token in exactly one test name (or a parametrize id), and no test carries an
id absent from the registry. Six-case pin: read `tests/trades/case_registry_22a.py` for cases 1-6's
implementing test functions; pin `sha256(inspect.getsource(fn))` for each, captured at base
`c212238a`, as literals. (Registry ids for tasks not yet implemented are marked `pending` and the
closure test skips them BY NAME until their task lands; Task 12 removes every `pending`.)
**Acceptance:** A2-08, A2-09 green.

### Task 3 -- Migration 0039 + every mirror (#11: ONE commit)

**Files:** `0039_provenance_corrections_tier2.sql`; `swing/data/db.py`; `swing/data/models.py`;
`swing/data/repos/provenance_corrections.py`; `tests/data/schema_manifest_head.tsv`;
`tests/data/test_migration_0039_provenance_corrections_tier2.py` (new);
`tests/data/_migration_text.py` (new helper); `tests/data/test_backup_gate_table.py`;
`tests/data/test_22a_task3_epoch_reader.py`; `tests/data/test_22a_task2_migration_0037.py` (only
where a test asserts a HEAD property); the P34 set (step F); any HEAD-version test bodies (38 -> 39).

**A. Red first** -- write A2-10..A2-31 and the flipped/extended model + drift tests; run; see each
fail for its stated reason (0039 absent / tier unknown / enum two-valued). **Row 1 in the migration
fixtures (SS-1):** the production service cannot write a v38 row once this task lands (it writes the
v39 column list), so derive it from the real emitter one version up: build
`tests.trades._cohort_provenance_fixtures.build_cadl_case` on a v39 DB, apply
`correct_cohort_provenance` (the `_seed_correction` pattern, `test_22a_task2_migration_0037.py:879`),
read the row's 40 v38 columns; then build the SAME world on a v38 DB and plant that payload by RAW
INSERT naming the 40 columns (the `_insert_correction` pattern, `:907`) -- the v38 citation trigger
must ADMIT it; never plant with a trigger dropped.

**B. Generate the CREATE body** from a fresh v38 DB (`run_migrations(c, target_version=38,
backup_dir=...)`): read `sqlite_master.sql` for `provenance_corrections` (measured: 33,223 chars, 40
columns, last column `cited_latch_probe_json`). Assert the IN-list substring `'latch_ladder')` occurs
EXACTLY ONCE and apply edit 2 there. **Edit 3 is NOT "before the last `)`":** SQLite's ADD COLUMN
spliced the six 0037 columns in AFTER the last column definition and BEFORE the table-level CHECKs
(measured: the stored text reads `... cited_latch_broker_order_id TEXT, cited_latch_probe_json
TEXT,\n\n    -- Three-predicate date gu...`, and the text ENDS with a table CHECK). So assert
`cited_latch_probe_json TEXT` occurs EXACTLY ONCE and insert `, cited_frozen_value_evidence_json TEXT`
immediately after it -- the byte shape SQLite's own ADD COLUMN would have produced. (Inserting before
the final `)` puts a column after a table constraint: a syntax error.) Set the name token to
`provenance_corrections__0039`. Paste into the migration verbatim.

**C. Edit 1 is measured, then pinned.** SQLite's RENAME rewrites the stored name token. Measured at
plan time on 3.50.4 (scratch table, same statement sequence as section 3 incl. the sequence carry):
`CREATE TABLE pc__0039 (...)` + RENAME -> stored `CREATE TABLE "pc" (...)`, and the carried
`sqlite_sequence` row (seq 7 over max id 1) moved with the rename intact. So edit 1 =
`CREATE TABLE provenance_corrections (` -> `CREATE TABLE "provenance_corrections" (`; re-confirm on
the first green run and pin it as a literal in A2-10's three-edit function. The test applies exactly
three edits to the v38 text and asserts BYTEWISE equality.

**D. The citation trigger (F11, F8, F13, F2.I) -- edits to the 0037 :896 text, nothing else:**
1. The `latch_ladder` arm's head becomes `NEW.admission_tier IN ('latch_ladder',
   'latch_ladder_tier2')` so the ~800-line latch body is SHARED (encoding E-4; one `$.authorization`
   closure list for AL-3).
2. The seventh column's paired-NULL rule: the `last_word` arm gains
   `AND NEW.cited_frozen_value_evidence_json IS NULL`; inside the shared arm the step-4 CASE carries
   it per tier -- `latch_ladder` -> `IS NULL`; `latch_ladder_tier2` -> `IS NOT NULL` plus the step-5
   block.
3. The probe-blob version clause (0037 :1368) becomes `= CASE NEW.admission_tier WHEN
   'latch_ladder' THEN '2026-08-25.1' WHEN 'latch_ladder_tier2' THEN '2026-09-23.1' END`.
4. The rung-9 clause (0037 :2022-2039): the object-closure, `json_type(input) = 'text'` and
   `input = link.freeze_tier` stay common; the rest becomes
   `CASE NEW.admission_tier WHEN 'latch_ladder' THEN (verdict = 'pass' AND input =
   'live_at_acceptance' AND EXISTS(... cited_candidate_id > e.max_candidate_id_at_barrier) AND
   NEW.cited_frozen_value_evidence_json IS NULL) WHEN
   'latch_ladder_tier2' THEN (verdict = 'escaped_by_tier2' AND input = 'pre_barrier_reconstructed'
   AND EXISTS(... cited_candidate_id <= e.max_candidate_id_at_barrier) AND
   NEW.cited_frozen_value_evidence_json IS NOT NULL AND <the seventh-column block>)
   ELSE 0 END`.
5. The seventh-column block: `CASE WHEN json_valid(NEW.cited_frozen_value_evidence_json) THEN (...)
   ELSE 0 END` (the 0037 R3-12 precedent), carrying every binding in section 2's table, the closed
   `json_remove` key list, and the `interval` endpoint bindings + segment-kind order. Each predicate
   carries a marker comment `-- TIER2-PREDICATE <id>` (ids = `TIER2_TRIGGER_PREDICATES`, Task 5).
6. The RAISE message gains one sentence naming the `latch_ladder_tier2` branch. Everything else is
   byte-identical to 0037's text. **No ROUND/printf/CAST on a price anywhere** (A2-29).
   The whole trigger stays under the existing `WHEN NOT (... COALESCE((...), 0))` so any NULL fails
   CLOSED (NULL-WHEN gotcha; A2-27 plants a MISSING key to prove it).

**E. Mirrors in the same commit:** models.py constants (section 1) + `ProvenanceCorrection.
cited_frozen_value_evidence_json: str | None = None` + the three-way paired rule (`last_word`: five
latch + seventh NULL; `latch_ladder`: five present, seventh NULL; `latch_ladder_tier2`: all six
present; an unknown tier rejected); repo insert list + `_row_to_*` mapper; db.py
`EXPECTED_SCHEMA_VERSION = 39`, `PHASE22_ARC_A2_PRE_MIGRATION_EXPECTED_TABLES =
set(PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES)` (0038 created no table), `BackupGateSpec(38,
"22a2", PHASE22_ARC_A2_PRE_MIGRATION_EXPECTED_TABLES, "_phase22_arc_a2_backup_gate", "pre-22-A2")`,
`_phase22_arc_a2_backup_gate = _bind_gate_wrapper(38)`; `test_backup_gate_table.py` SPLIT (P33): the
base-derived roster stays 23 rows cross-checked against `eface268`, and a `POST_BASE_ROSTER` of one
row `(38, "22a2", "_phase22_arc_a2_backup_gate", "PHASE22_ARC_A2_PRE_MIGRATION_EXPECTED_TABLES",
"pre-22-A2")` is asserted against the live table; the table equals base + post-base in order.

**F. P34 re-pointing (condition 6, encoding 9):** add `head_create_statement(name) -> (Path, str)` in
`tests/data/_migration_text.py` (scans migrations ascending, returns the LAST file that CREATEs the
object and that statement's text). Enumerate consumers by
`grep -rln "0037_latch_order_mandate_links\|MIGRATION_0037" tests/` (lower bound; measured at base:
`test_22a_al3_closure.py`, `test_22a_authorize_then_abort_closure.py`,
`test_22a_canonicalizer_version_closure.py`, `test_22a_task11_citation_evidence.py`,
`test_22a_task2_migration_0037.py`, `test_22a_task3_epoch_reader.py`,
`tests/trades/test_22a_envelope_canonicality_sweep.py`), then READ each reference and classify:
(i) asserts a property of a trigger 0039 re-creates (citation graph / append-only update) -> re-point
to `head_create_statement`; (ii) asserts 0037's own text or v37 post-migrate state, or a barrier /
epoch / link / FEI object 0039 does not touch (0037 IS its HEAD) -> unchanged. Record the per-reference
classification table in the ledger. The evidence-version pin (`test_22a_task3_epoch_reader.py:449`)
becomes: the set of probe-version literals in the HEAD citation trigger ==
`{LATCH_PROBE_EVIDENCE_VERSION, LATCH_PROBE_TIER2_EVIDENCE_VERSION}`. The model test at `:440-443`
(tier2 REJECTED) flips: A2-24 replaces it.

**G. #11 sweep, closure-checked by READ:** grep EACH member separately across `swing/` (`*.py`,
`*.sql`): `latch_ladder_tier2`, `"latch_ladder"`, `'latch_ladder'`, `last_word`,
`PROVENANCE_ADMISSION_TIER`, `escaped_by_tier2`, `'pass'`/`"pass"` in latched_origin + 0039,
`2026-08-25.1`, `2026-09-23.1`, `cited_frozen_value_evidence_json`. Read every hit; record in the
ledger each as widened / tight-by-design / value-agnostic, with the search. (Lower bound at census:
R0.1 enum-member table.)

**H. Manifest:** `python scripts/schema_manifest.py --write`; `git diff tests/data/schema_manifest_head.tsv`
reads exactly section 3's four pairs, zero deletions. Quote it in the commit body.
**Acceptance:** A2-10..A2-31 green; full fast suite green; ruff clean.

### Task 4 -- `frozen_value_evidence.py`: the git preflight (no DB)

**Files:** `swing/trades/frozen_value_evidence.py` (new);
`tests/trades/test_22a2_frozen_value_preflight.py` (new); `tests/trades/_git_world.py` (new helper:
builds a temp repo + bare remote + fetch so `REMOTE_REF` exists; commits with explicit
`GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE`; `rewrite_remote_dropping(sha)` via force-push + fetch;
`grow_remote(n)`).
**Build:**
- `EvidenceSelection(artifact_path, artifact_commit_sha, quoted_text)`;
  `load_evidence_selection(path) -> EvidenceSelection | failure`: JSON object with EXACTLY
  `EVIDENCE_FILE_KEYS`, each a non-empty `str`; sha 40 lowercase hex; anything else -- including a
  missing/unreadable file or non-UTF-8 bytes -> `evidence_file_malformed` (duplicate keys refused via
  `object_pairs_hook`).
- `ArtifactFacts` (frozen): selection, `author_instant` (aware), `committer_instant`, `is_ancestor`,
  `resolved_remote_ref_sha`, `descendant_count`, `remote_ref_updated_at`, `remote_ref_age_seconds`.
- `read_artifact_facts(selection, *, repo_dir, now_utc) -> PreflightResult`: `git show sha:path`
  (bytes; `utf-8`) -> the quoted text must be a byte-substring (`quoted_text_not_in_artifact`) and
  contain no `\n`/`\r` (`quoted_text_not_one_line`); `git show -s --format=%aI%n%cI sha`;
  `git rev-parse REMOTE_REF`; `git merge-base --is-ancestor sha <resolved>` (exit 0 -> True, 1 ->
  False, other -> unverifiable); `git rev-list --count sha..<resolved>` (only when ancestor, else
  null); `git log -g -1 --date=iso-strict --format=%gd REMOTE_REF` parsed for the `@{...}` instant
  (null when no reflog). Object/path missing -> `artifact_unreadable`. Timeout, git absent, missing
  ref -> `tier2_unverifiable`.
- `PreflightResult(facts | None, failure | None, detail: str)` -- **never raises** (encoding E-6).
- `run_preflight(evidence_file, *, repo_dir=None, now_utc) -> PreflightResult` = load + read.
**Acceptance:** A2-32..A2-41 green. No `sqlite3` import in the module's preflight half (A2-41).

### Task 5 -- Conjunction evaluation, blob builder, predicate roster (DB read-only)

**Files:** `swing/trades/frozen_value_evidence.py`; `tests/trades/test_22a2_conjunction.py` (new).
**Build:**
- `render_price(v) -> str` = `f"{round(v, 2):.2f}"` (the ONE rounding authority, S4.3a).
- `find_token(text, token, *, kind)`: `ticker` bounded by non-`[A-Za-z0-9]`; `session`/`numeral`
  bounded by non-`[0-9.]`; returns the matched text or None.
- `evaluate_conjunction(conn, facts, *, candidate_id, fill_session: date, read_at: str,
  barrier_installed: bool) -> ConjunctionVerdict(admitted, criterion, reason, field, evidence)`.
  Reads (SELECT only) `candidates` (ticker, pivot, initial_stop, evaluation_run_id),
  `evaluation_runs` (run_ts, action_session_date), the owning `pipeline_runs` row (`finished_ts`,
  `state='complete'`), the epoch row. Order: criterion 1 (`facts.is_ancestor`); criterion 2 (ET date
  of `author_instant` via `ZoneInfo("America/New_York")` strictly `<` `fill_session`; equal ->
  `recorded_on_fill_session`, greater -> `recorded_after_fill_session`); criterion 3 (ticker ->
  action_session [ISO token preferred; else MM-DD token admitted only if ET author year ==
  action-session year] -> pivot -> invalidation, each by `find_token` of the SERVICE-RENDERED value);
  criterion 4 (endpoints resolvable; `record_at >= fire_hi` in UTC; `fire_lo <= record_at < fire_hi`
  -> `window_indeterminate`; `< fire_lo` -> `window_negative`). On admit, builds the section-2 blob
  (with `interval` + `uncovered_window_prose`, e.g. "writer_absence_only 2.38 days (2026-08-08T03:39:07Z
  to 2026-08-10T12:41:33Z); match_only 22.89 days; covered from 2026-09-02T10:03:33Z").
- `VERDICT_BEARING_KEYS` (frozenset): the selection, `quoted_*_text`, `live_*_raw`,
  `author_instant`, `author_date_et`, `fill_session_date`, every endpoint's `raw` and `utc`. Recorded-
  only keys (never compared at replay): `evaluated_at`, `resolved_remote_ref_sha`,
  `descendant_count`, `remote_ref_*`, `committer_instant`, `segments[*].kind` of `covered`.
- `TIER2_TRIGGER_PREDICATES: tuple[tuple[str, str], ...]` -- `(predicate_id, service_check_name)`,
  one per `-- TIER2-PREDICATE` marker in 0039 (AUTHORIZE-THEN-ABORT, brief section 4.4).
**Acceptance:** A2-42..A2-60 green.

### Task 6 -- The rung-9 escape seam in `latched_origin.py`

**Files:** `swing/trades/latched_origin.py`; `tests/trades/test_22a2_rung9_escape.py` (new).
**Build:**
- `Tier2Request(preflight: PreflightResult, applied_at: str)` (defined in frozen_value_evidence.py).
- New keyword-only `tier2: Tier2Request | None = None` on `resolve_latched_provenance` and
  `authorize_accepted_order`, threaded unchanged. Default `None` = today's behaviour byte-for-byte.
- Rung 9 (`:1819-1848`): the barrier check stays FIRST and unchanged. Then: if stored AND read-time
  tiers are both `live_at_acceptance` -> existing pass path, and **if `tier2` is not None, refuse
  `tier2_evidence_refused` with detail `no_escape_to_take` (encoding 3)**. If stored AND read-time
  are both `pre_barrier_reconstructed` AND `tier2` is not None: if `tier2.preflight.failure` ->
  refuse `tier2_evidence_refused` (detail = that failure); else `evaluate_conjunction(conn,
  tier2.preflight.facts, candidate_id=order.candidate_id, fill_session=fill_session,
  read_at=tier2.applied_at, barrier_installed=installed)`; not admitted -> refuse
  `tier2_evidence_refused` (detail = `criterion N: <reason/field>`); admitted -> ESCAPE: continue to
  the guards + probe unchanged. Any other combination (disagreement, or pre-barrier with no `tier2`)
  -> `pre_barrier_unproven` exactly as today (encoding 2).
- On an escaped admission: `_authorization_block` takes an optional `verdicts: dict[str, str]`
  override; rung 9 records `{"input": "pre_barrier_reconstructed", "verdict": "escaped_by_tier2"}`;
  the probe blob's `evidence_version` = `LATCH_PROBE_TIER2_EVIDENCE_VERSION`;
  `LatchedProvenance.frozen_value_evidence: dict | None = None` carries the seventh-column blob.
- `AUTHORIZATION_VERDICTS`; decline-reason roster gains `tier2_evidence_refused`; the refusal carries
  `tier2_refusal: str | None` (new `LatchedProvenance` field, default None).
- `record_entry` / the entry wiring pass no `tier2` (A2-65 pins the CALLER, gotcha #31).
**Acceptance:** A2-61..A2-66 green; the 22-A suite green with cases 1-6 byte-unchanged (A2-09).

### Task 7 -- Service wiring in `cohort_provenance_correction.py`

**Files:** `swing/trades/cohort_provenance_correction.py`;
`tests/trades/test_22a2_correction_service.py` (new).
**Build:**
- `correct_cohort_provenance(..., frozen_value_evidence: Path | None = None, evidence_repo:
  Path | None = None)` and the same on `preview_cohort_provenance_correction`. The OUTER function runs
  `run_preflight` (when a path is given) BEFORE `BEGIN IMMEDIATE`; the preview runs it before its
  SAVEPOINT. `run_preflight` PARSES and READS but can NEVER REFUSE: it returns a typed
  `PreflightResult` (failure included) and the only refusal-capable consumer of it is rung 9, which
  `_authorize` reaches AFTER its SELECT-first already-applied return. So a malformed file on an
  already-applied trade is parsed, its failure is never consulted, and the existing id returns --
  SELECT-first still precedes every payload REFUSAL (E-6; R2-01's reading adjudicated in the ledger).
- The inner takes `applied_at = _APPLIED_AT_CLOCK()` ONCE before `_authorize` and uses that one string
  for the column, the blob's `evaluated_at`, and the interval's `read_at` (E-7).
- `_authorize(..., tier2: Tier2Request | None)` -> `_resolve_latch_citation(..., tier2=tier2)` ->
  `resolve_latched_provenance(..., tier2=tier2)`.
- `_LatchCitation.frozen_value_evidence_json: str | None` (`json.dumps(..., sort_keys=True)`);
  `_Authorized.admission_tier` -> `last_word` (no latch) / `latch_ladder_tier2` (evidence present) /
  `latch_ladder`. The tier stays DETECTED, never chosen.
- Encoding 3, at `_authorize`: evidence supplied and `latch is None` -> refuse naming "no accepted
  latch order: tier-2 evidence is admissible only as rung 9's escape on a pre-barrier linked
  mandate"; a ladder refusal raised with evidence supplied appends "(the supplied
  --frozen-value-evidence was not consulted: <reason>)" unless the reason is
  `tier2_evidence_refused`, whose detail is printed.
- Insert: the seventh column written; `CohortProvenanceCorrectionPreview` / `...Result` gain
  `tier2_clauses: tuple[tuple[str, str], ...]` (criterion -> verdict text) and
  `tier2_interval_prose: str | None`.
- Already-applied path: unchanged SELECT-first return; when evidence was supplied, the result carries
  `tier2_note = "already applied; evidence not re-evaluated here -- the read-time verdict is on
  journal provenance-corrections"` (E-18).
**Acceptance:** A2-67..A2-76 green.

### Task 8 -- CLI: `--frozen-value-evidence` + the manifest pin 5 -> 6

**Files:** `swing/cli.py`; `tests/cli/test_correct_cohort_provenance_command.py`.
**Build:** `@click.option("--frozen-value-evidence", "frozen_value_evidence",
type=click.Path(dir_okay=False, path_type=Path), default=None, help=...)` (NO `exists=True`: a
missing file must reach the service as a deferred preflight failure, A2-70) declared so the param is
LAST in `cmd.params`; passed through to both service entry points; the file is NOT parsed by click
(the service owns validation, E-6). Output (dry-run and apply) prints the tier, the four clauses one
per line (`criterion 1 ancestor of refs/remotes/origin/main at <sha>: PASS` ...), the interval prose,
and on refusal the tier-2 reason + field. ASCII only.
**Acceptance:** A2-77..A2-80 green; the pin test renamed to `..._exactly_six_entries` asserting
`["trade_id", "cited_candidate_id", "cited_recommendation_id", "reason", "dry_run",
"frozen_value_evidence"]`.

### Task 9 -- Replay: `replay_verdict`, exclusions, the drift reader

**Files:** `swing/trades/frozen_value_evidence.py`; `swing/trades/cohort_provenance_correction.py`
(`read_provenance_corrections`); `swing/cli.py` (`journal provenance-corrections` rendering);
`tests/trades/test_22a2_replay.py` (new).
**Build:**
- `replay_verdict(conn, row, *, now, repo_dir=None) -> ReplayVerdict(verdict, reason,
  evaluated_at, resolved_origin_main_sha, barrier_installed_at_read)` (P37: `conn` read-only, NO
  transaction opened, NO write). Steps: parse the stored seventh blob -> selection ->
  `read_artifact_facts` (same function as write, same timeout; `row.entry_fill_session_date` crosses
  the TEXT -> `date` boundary via `date.fromisoformat`, a malformed value a typed stale reason, never
  a deep `TypeError`) -> process failure -> `tier2_unverifiable`;
  git negative -> `tier2_evidence_stale` (E-10); stored `author_instant` != git's ->
  stale `author_instant_changed`; `evaluate_conjunction(conn, facts, candidate_id=row.cited_candidate_id,
  fill_session=row.entry_fill_session_date, read_at=row.applied_at, barrier_installed=<read now>)`
  -> not admitted -> stale naming criterion/field; admitted -> compare `VERDICT_BEARING_KEYS` of the
  recomputed blob with the stored blob -> any difference -> stale `<key>_mismatch`; else `ADMIT`.
  Descendant growth and ref-age change are never compared (doctrine #6).
- `tier2_cohort_exclusions(conn, *, now, repo_dir=None) -> dict[int, ReplayVerdict]` -- selects
  `provenance_corrections` rows with tier `latch_ladder_tier2`, calls `replay_verdict` per row with
  a memo scoped to THIS call keyed on `(provenance_correction_id, resolved_origin_main_sha)`, returns
  the non-ADMIT rows by `trade_id`. No cache across calls (F10-shape).
- Drift reader: tier-2 rows render `read-time verdict: <verdict> (<reason>) evaluated_at <now>,
  origin/main <sha>, barrier installed at read <bool>`; replay runs OUTSIDE any read transaction the
  reader holds (collect rows, release, then replay).
**Acceptance:** A2-81..A2-90 green.

### Task 10 -- The four cohort readers exclude BY NAME (F10, encoding 8)

**Files:** `swing/journal/stats.py`; `swing/metrics/tier.py`; `swing/recommendations/hypothesis.py`;
`swing/web/view_models/metrics/hypothesis_progress_card.py` (+ its template and the tier surface
template); `swing/cli.py` (hypothesis list line); `tests/trades/test_22a2_cohort_readers.py` (new);
web tests via `with TestClient(app) as client:`.
**Build:** each reader calls `tier2_cohort_exclusions(conn, now=...)` once per invocation, removes
those trade ids from what it counts (Python filter, or a dynamic `NOT IN (?,...)` with the
empty-list short-circuit), and exposes `tier2_excluded: tuple[(trade_id, verdict, reason), ...]`.
Surfaces: `swing hypothesis list` prints one line per excluded trade; the journal review-progress
output likewise; the web card + tier surface render one line (empty in the zero-data state -- the
field is on the VM with a safe default; no new base-layout field). No reader reads
`admission_tier` as a verdict.
**Acceptance:** A2-91..A2-97 green.

### Task 11 -- The acceptance case (trade 25) end to end + the live-copy evidence

**Files:** `tests/trades/test_22a2_acceptance_trade25.py` (new); `tests/fixtures/tier2/` (the
line-57 file + the git world built at test time).
**Build:** a DB world in trade 25's REAL row shape (section 4 values; reuse the 22-A task-9 probe-world
builder -- `build_world(tmp_path, name, *, closes=None, pre_barrier=True, ...)` at
`tests/trades/test_22a_task9_entry_wiring.py:67` over `tests/_latch_probe_world_22a.py`, whose
`pre_barrier=True` lands the epoch boundary ABOVE the fire so the link mints
`pre_barrier_reconstructed` -- parameterised with OII's candidate values and bars that leave the
mandate `armed` over sessions 2026-08-10..2026-08-14; extend the helper if it cannot take them) + a git world whose one
artifact commit carries line 57's exact bytes as line 57 of `docs/rd-state.md`, authored
`2026-08-10T02:41:33-10:00`, pushed and fetched. The evidence file = `{artifact_path:
"docs/rd-state.md", artifact_commit_sha: <that commit>, quoted_text: <line 57 decoded>}`.
**Live-copy evidence (NOT a committed test):** on a `sqlite3.backup()` copy of live under a scratch
config (the ledger R0.0 method), from the worktree with `PYTHONPATH=.`: `journal
correct-cohort-provenance 25 --cited-candidate 12284 --cited-recommendation 169 --reason "<r>"
--frozen-value-evidence <file naming 9f315cc6 / docs/rd-state.md / line 57> --dry-run` -> ADMIT with
the four clauses + interval printed; record the output + live size/mtime before/after in the ledger.
**Acceptance:** A2-98..A2-104 green; live-copy dry-run reads ADMIT.

### Task 12 -- Close-out

Remove every `pending` from the registry (A2-08 green with zero skips); full fast suite on the final
head READ from the tail; `ruff check swing/`; `python scripts/schema_manifest.py --check`; trailer
audit `git log c212238a..HEAD --format='%H%n%(trailers)'`; ledger updated (P34 classification, #11
sweep table, live-copy evidence, CLAUDE.md side-flag: the "db-migrate writes TWO backups" gotcha is
stale vs `cli.py:284-289` -- FLAGGED, not edited here).

## 6. Test roster

Pre -> post = what the discriminator reads under the NULL / pre-fix implementation vs the correct one.

### Task 1 -- (t1) scan

| id | assertion | pre -> post |
|---|---|---|
| A2-01 | synthetic `0040_x.sql` with `DROP TRIGGER trg_candidates_no_update;` -> violation | scan absent: none -> 1 |
| A2-02 | `DROP TABLE candidates;` -> violation | none -> 1 |
| A2-03 | `DROP TABLE IF EXISTS "candidates_immutability_epoch";` -> violation | none -> 1 |
| A2-04 | `DROP TABLE provenance_corrections;` -> NO violation (the two tables only; 0039's shape) | an "any DROP TABLE" scan: 1 -> 0 |
| A2-05 | a drop + `INSERT INTO candidates_immutability_epoch_events ...` -> no violation | 1 -> 0 |
| A2-06 | a drop and the INSERT only inside `--` comments -> violation (comment-stripped) | 0 -> 1 |
| A2-07 | real `swing/data/migrations/` scan == `[]`; names imported (`is` the module's tuple) | -- |

### Task 2 -- registry

| id | assertion | pre -> post |
|---|---|---|
| A2-08 | every registry id has exactly one implementing test; no phantom ids | -- |
| A2-09 | cases 1-6 test-function sources hash to the base-pinned sha256 values | an edited case: mismatch -> fail |

### Task 3 -- migration 0039 (conditions 1-6) and mirrors

| id | assertion | pre -> post |
|---|---|---|
| A2-10 | (C1) three edits applied to the v38 stored DDL == v39 stored DDL, BYTEWISE | a lost CHECK / extra edit: unequal -> fail |
| A2-11 | (C1) in the v38 text the IN-list substring and `cited_latch_probe_json TEXT` each occur exactly once; v39 `PRAGMA table_info` = the 40 v38 columns in order + `cited_frozen_value_evidence_json` at position 41 | a before-last-`)` edit: CREATE fails (column after a table CHECK) |
| A2-12 | (C2) row 1 (trade 23, `last_word`): `quote(col)` tuple over the 40 v38 columns identical before/after; seventh col NULL after | a DEFAULT-refill or positional copy: differs |
| A2-13 | (C2) `sqlite_sequence` for `provenance_corrections` equal before/after on a fixture with seq **7** and max id **1** | naive copy: 7 -> 1 (fail); carried: 7 -> 7 |
| A2-14 | (C2) same on the live-shape fixture (seq 1, max id 1) and on a zero-row DB (no seq row before or after) | -- |
| A2-15 | (C2) `PRAGMA foreign_key_check` empty after migrating a v38 DB carrying row 1's real citation graph | -- |
| A2-16 | (C3) statement order in 0039 (comment-stripped): CREATE new < INSERT..SELECT < seq carry < DROP < RENAME < every CREATE INDEX/TRIGGER | a trigger before the copy: order fails |
| A2-17 | (C3) the four verbatim objects' `sql` byte-equal to their 0036/0037 source statement text | -- |
| A2-18 | (C4) manifest(v38) vs manifest(v39) via `read_manifest`/`compare`: changed == {table provenance_corrections, trigger ..._append_only_update, trigger ..._citation_graph}; removed == added == {} | a forgotten index: removed = {ix_...} |
| A2-19 | (C4) `test_head_manifest_matches_fixture` green with the regenerated fixture at 39 | -- |
| A2-20 | (C5) 0039 header names the three edits and the gate row (text assertion on the header block) | -- |
| A2-21 | (P28) `backup_gate_for_pre_version(38)` returns the 22a2 spec; migrating a v38 DB writes `swing-pre-22a2-migration-*.db` and the CLI echoes it | no row: None / CLI no-gate snapshot |
| A2-22 | (P33) base roster 23 rows vs `eface268` + post-base roster 1 row; table == base + post-base | -- |
| A2-23 | drift: SQL `admission_tier IN (...)` (live `sqlite_master`) == `PROVENANCE_ADMISSION_TIERS` (three) | two-valued: `{last_word, latch_ladder}` != three |
| A2-24 | model: `latch_ladder_tier2` with all six present -> accepted; with the seventh None -> "is missing"; `latch_ladder` with seventh set -> rejected; `last_word` with seventh set -> rejected; `latch_ladder_tier3` -> rejected | old validator: tier2 rejected |
| A2-25 | drift: tier literals parsed from the HEAD citation trigger == `PROVENANCE_ADMISSION_TIERS`; rung-9 verdict literals == `AUTHORIZATION_VERDICTS`; probe-version literals == {both constants}; seventh-blob version literal == `FROZEN_VALUE_EVIDENCE_VERSION` | a hard-coded single member missing: set differs |
| A2-26 | a truthful tier-2 row inserts via RAW `conn.execute`: built on the 22-A truthful-`latch_ladder`-row world of `tests/data/test_22a_task11_citation_evidence.py`, re-pointed to a candidate id <= boundary with trade-25 values, rung 9 escaped, probe version `2026-09-23.1`, and the literal seventh blob `tests/fixtures/tier2/trade25_seventh_blob.json` (hand-built from section 2) | trigger without the tier2 arm: ABORT |
| A2-27 | raw tier-2 insert whose seventh blob OMITS `interval` -> ABORT (NULL-WHEN fail-open probe; brief 4.2 "interval left uncomputed") | un-COALESCEd arm: ACCEPTED |
| A2-28 | parametrized raw-insert mutations of A2-26, each -> ABORT: rung9 verdict `pass`; rung9 input `live_at_acceptance`; seventh NULL; seventh `'{bad'`; extra key; `evidence_version` wrong; `artifact_commit_sha` 39 chars; `quoted_text` with `\n`; `quoted_ticker_text` `OIS`; `quoted_pivot_text` `53.97` (not in text); `live_pivot_raw` 53.98 (!= 53.97999954223633); `pivot_equal_at_dp` 0; `compare_dp` 3; `fill_session_date` 2026-08-18; `author_date_et` 2026-08-17; `fire_lo.raw` altered; `read_at.raw` != applied_at; `barrier_armed_at.raw` altered; segment kinds reordered; `quoted_action_session_text` `08-11`. (The `<= boundary` clause has NO isolatable mutation: the minting CASE makes a `pre_barrier_reconstructed` link imply `<= boundary`, so it is a declared BELT, the twin of 0037's `> boundary` clause.) | each: missing predicate -> ACCEPTED |
| A2-29 | within the HEAD citation trigger's span from the first to the last `-- TIER2-PREDICATE` marker, comment-stripped and case/whitespace-normalized, there is no `round(`, `printf(`, `format(` or `cast(` (R9-05 grep-gate hardening: `ROUND (` and `Round(` are caught) | a SQLite-rounding arm: found |
| A2-30 | `latch_ladder` row with rung9 `escaped_by_tier2` + version `2026-08-25.1` -> ABORT (verdict clause); `latch_ladder` row with rung9 `pass` + version `2026-09-23.1` -> ABORT (version clause) (F11 inverse clause, per-clause) | each clause removed: ACCEPTED |
| A2-31 | append-only: UPDATE of `cited_frozen_value_evidence_json` on a tier-2 row -> ABORT; `INSERT OR REPLACE` on id 1 -> ABORT; DELETE -> ABORT; the PRAGMA-driven closure test sees 41 columns | update trigger without the new line: UPDATE succeeds |

### Task 4 -- preflight

| id | assertion | pre -> post |
|---|---|---|
| A2-32 | evidence file with a 4th key / missing key / non-str / duplicate key / 39-char sha -> `evidence_file_malformed` | -- |
| A2-33 | quoted text not a byte-substring of the artifact -> `quoted_text_not_in_artifact` | -- |
| A2-34 | quoted text spanning two lines (contains `\n`) -> `quoted_text_not_one_line` (s-i) | whole-file selection accepted |
| A2-35 | line-57 fixture in a git world: facts carry author `2026-08-10T02:41:33-10:00`, `is_ancestor` True, resolved sha == the bare remote's tip | -- |
| A2-36 | (C1 discriminator, brief 4.2) commit present locally but NOT an ancestor of `REMOTE_REF` -> `is_ancestor` False | ancestry check absent: True |
| A2-37 | non-ASCII artifact line (the em-dash in line 57) round-trips; decoding as cp1252 would fail the substring check (bytes-captured) | `text=True` default: mismatch |
| A2-38 | git subprocess `TimeoutExpired` (monkeypatched) -> `tier2_unverifiable`, no raise | -- |
| A2-39 | no `REMOTE_REF` in the repo -> `tier2_unverifiable` | -- |
| A2-40 | reflog absent -> `remote_ref_updated_at`/`age` null; present -> age = now - reflog instant | -- |
| A2-41 | `run_preflight` never raises for any A2-32..A2-40 input; the module imports no DB writer (AST: no `.execute(` with INSERT/UPDATE/DELETE, no `BEGIN`) | -- |

### Task 5 -- conjunction (per-clause discriminators on the trade-25 world unless stated)

| id | assertion | pre -> post |
|---|---|---|
| A2-42 | trade-25 values: ADMIT; blob keys == section-2 roster; `quoted_*` = `OII`, `2026-08-10`, `53.98`, `41.42`; builder output equals the hand-built A2-26 literal on `VERDICT_BEARING_KEYS` (two independent representations) and inserts raw | -- |
| A2-43 | interval: writer_absence_only **205,346 s**, match_only **1,977,720 s**, fire **545 s**; prose contains `2.38 days` and `22.89 days` | point-fire impl: 205,891 s (from run START) |
| A2-44 | (C1) `is_ancestor` False -> REFUSE criterion 1 `not_ancestor_of_origin_main` | -- |
| A2-45 | (C2 boundary twin, F7) author `2026-08-17T09:00:00-04:00` (ET date = fill session) -> REFUSE `recorded_on_fill_session` | a `<=` impl: ADMIT |
| A2-46 | (F7 a vs c) author `2026-08-16T20:00:00-10:00` (ET `2026-08-17T02:00`) -> REFUSE `recorded_on_fill_session` | local-offset-date impl: 08-16 < 08-17 ADMIT |
| A2-47 | author `2026-08-16T23:59:59-04:00` -> criterion 2 PASSES | -- |
| A2-48 | committer date != author date (committer on the fill session) -> criterion 2 still PASSES (committer never verdict-bearing) | committer-date impl: REFUSE |
| A2-49 | (C3 five-cent, R0.6) candidate pivot **53.93**, text quotes 53.98 -> REFUSE `pivot` | no pivot check: ADMIT |
| A2-50 | (C3 eighth-dollar, R0.6/F8) candidate pivot **22.125**, text quotes `22.12` -> ADMIT (Python half-even renders `22.12`) | SQLite-rounding impl renders `22.13`: REFUSE |
| A2-51 | candidate pivot **22.1249**, text `22.12` -> ADMIT (control: both engines render 22.12; documents why A2-50, not this, discriminates) | -- |
| A2-52 | (F6 iii) line 57, candidate ticker `OI` -> REFUSE `ticker` (token-bounded; `OI` inside `OII` is no token) | substring impl: ADMIT |
| A2-53 | (F6 iii, RD's discriminator) same numerals, candidate ticker `VSTS` (absent from line 57) -> REFUSE `ticker` | no ticker check: ADMIT |
| A2-54 | (F6 iii) candidate action session `2026-08-11` -> REFUSE `action_session` | -- |
| A2-55 | (F13 year rule) line 57 with its `2026-08-10` token removed, author `2025-08-09T10:00:00-10:00` -> REFUSE `action_session` (criterion 3 speaks before 4) | no year rule: REFUSE `window_negative` |
| A2-56 | (F13 year rule, ISO present) line 57 as-is, same prior-year author -> REFUSE `window_negative` (criterion 3 passes on the ISO token) | year rule applied to ISO: REFUSE `action_session` |
| A2-57 | (F6 ii) record = fire_hi (`2026-08-07T17:39:07-10:00`) -> ADMIT; fire_hi - 1 s -> REFUSE `window_indeterminate`; fire_lo - 1 s -> REFUSE `window_negative` | no bracket: fire_hi-1s ADMITS |
| A2-58 | refusal order: ticker AND pivot both wrong -> names `ticker`; pivot AND invalidation wrong -> names `pivot` | -- |
| A2-59 | DECLARED-LIMIT pins (fail if the blindness ever narrows silently): a line reading `pivot 41.42 / stop 53.98` for candidate 53.98/41.42 -> ADMIT (AL2-3); line 57 for a candidate ticker `AMN` with OII's session and values -> ADMIT (AL2-2) | -- |
| A2-60 | AUTHORIZE-THEN-ABORT closure (brief 4.4): `-- TIER2-PREDICATE` ids parsed from the HEAD trigger == ids in `TIER2_TRIGGER_PREDICATES`, both directions; every service check name exists in the module and is reached from `evaluate_conjunction` (AST call walk) | a trigger predicate with no service check: set differs |

### Task 6 -- rung 9

| id | assertion | pre -> post |
|---|---|---|
| A2-61 | pre-barrier link + passing `tier2` -> admitted; rung9 `{input: pre_barrier_reconstructed, verdict: escaped_by_tier2}`; probe version `2026-09-23.1`; `frozen_value_evidence` set | today: `pre_barrier_unproven` |
| A2-62 | pre-barrier link, NO `tier2` -> `pre_barrier_unproven` (unchanged) | -- |
| A2-63 | barrier NOT installed + passing `tier2` -> `barrier_not_installed` (barrier check first) | escape-before-barrier impl: admitted |
| A2-64 | stored `live_at_acceptance`, read-time `pre_barrier_reconstructed` (or reverse) + `tier2` -> `pre_barrier_unproven` | -- |
| A2-65 | caller obligation (#31): the entry path's call to `resolve_latched_provenance` passes no `tier2` keyword (AST over the entry wiring) | -- |
| A2-66 | post-barrier admission + `tier2` supplied -> `tier2_evidence_refused` / `no_escape_to_take` | silent ignore: admitted `latch_ladder` |

### Task 7 -- service

| id | assertion | pre -> post |
|---|---|---|
| A2-67 | trade-25 world apply: row tier `latch_ladder_tier2`, all six citation columns non-NULL, trade keys `A+ baseline (aplus)` / 12284 / `pipeline_aplus` | -- |
| A2-68 | `applied_at` column == blob `evaluated_at` == `interval.endpoints.read_at.raw` (one stamp) | two clock reads: differ by the gap |
| A2-69 | the preflight runs before `BEGIN IMMEDIATE`: monkeypatched git asserts `conn.in_transaction` is False at every call | -- |
| A2-70 | already-applied trade + (a) a malformed evidence file, (b) a path that does not exist -> returns the existing id with `tier2_note`, through ALL THREE entry points: `correct_cohort_provenance`, `preview_cohort_provenance_correction`, and the CLI (exit 0; the caller-side obligation that click never parses or existence-checks the file, #31) | a preflight that refuses, or `click.Path(exists=True)`: refuses / exit 2 |
| A2-71 | evidence on a last-word trade (no link) -> refuse naming "no accepted latch order" | silent ignore: last_word row written |
| A2-72 | evidence + a ladder refusal at an earlier rung -> message carries "was not consulted" | -- |
| A2-73 | evidence failing criterion 3 -> refusal message names `tier2_evidence_refused` + `criterion 3: pivot`; nothing written | -- |
| A2-74 | dry-run == apply's authorization (same refusals, same tier) and leaves the DB byte-identical (`iterdump` equal) | -- |
| A2-75 | the git preflight is called only from the two service entry points (AST walk of `swing/`: callers of `run_preflight`) | -- |
| A2-76 | the fill-48 `fill_envelope_identity` reading is written by the apply and absent after the dry-run | -- |

### Task 8 -- CLI

| id | assertion | pre -> post |
|---|---|---|
| A2-77 | params manifest == the six, `frozen_value_evidence` last | five -> six |
| A2-78 | dry-run output lists the four clauses one per line + the interval prose; ASCII only (encode as cp1252 succeeds) | -- |
| A2-79 | refusal output names the tier-2 reason + field; exit code 1 | -- |
| A2-80 | help text: the option documents the three-key file and that values are never typed | -- |

### Task 9 -- replay (F10, brief 4.3)

| id | assertion | pre -> post |
|---|---|---|
| A2-81 | trade-25 row, remote unchanged -> `ADMIT` | -- |
| A2-82 | REWRITTEN remote (history drops the cited commit) -> `tier2_evidence_stale` / `not_ancestor_of_origin_main` | stored-grade reader: counts it |
| A2-83 | GROWN remote (+3 commits) -> `ADMIT`; recomputed `descendant_count` larger, not compared | growth-as-staleness impl: stale |
| A2-84 | git timeout -> `tier2_unverifiable`; missing `REMOTE_REF` -> `tier2_unverifiable` | -- |
| A2-85 | current candidate pivot changed (barrier lifted by the 22-A test helper, then re-armed) -> stale naming `pivot` | -- |
| A2-86 | `replace(row, cited_frozen_value_evidence_json=<fire_hi.raw altered>)` -> stale `..._mismatch` | -- |
| A2-87 | `replay_verdict` opens no transaction and writes nothing: works on a `mode=ro` URI connection; `total_changes` unchanged | -- |
| A2-88 | barrier absent at read -> verdict unchanged, `barrier_installed_at_read` False (observation only) | -- |
| A2-89 | `tier2_cohort_exclusions`: exactly one `replay_verdict` per tier-2 row per call (memo keyed `(provenance_correction_id, resolved_origin_main_sha)`); a SECOND call re-runs git (no cross-call cache -- a cached verdict is a stored grade, F10-shape) | a module-level cache: second call makes no git call |
| A2-90 | `journal provenance-corrections` renders the verdict line for a tier-2 row; `last_word`/`latch_ladder` rows render as today | -- |

### Task 10 -- readers (F10 sub-ruling: a stale row does NOT count, NAMED)

| id | assertion | pre -> post |
|---|---|---|
| A2-91 | `compute_tripwire_status` (H1): REWRITTEN -> N drops by exactly one and the exclusion names trade + reason; GROWN -> N unchanged | stored-tier reader: N unchanged |
| A2-92 | journal review progress: same pair | -- |
| A2-93 | tier surface (`swing/metrics/tier.py`): same pair | -- |
| A2-94 | web hypothesis progress card (TestClient, lifespan): exclusion line rendered; zero-data state renders none and 200 | -- |
| A2-95 | tier surface page (TestClient): same | -- |
| A2-96 | `swing hypothesis list` prints the exclusion line | -- |
| A2-97 | `tier2_unverifiable` excludes and names too (never admitted on the stored grade) | -- |

### Task 11 -- acceptance (brief section 4)

| id | assertion | pre -> post |
|---|---|---|
| A2-98 | (4.1) trade 25 ADMITS on tier-2 from line 57 @ an ancestor commit authored `2026-08-10T02:41:33-10:00`: keys H1 / 12284 / `pipeline_aplus`; row tier, citation JSON, interval (2.38 d / 22.89 d), attestation (`evaluated_at`, `verification_method`, `resolved_remote_ref_sha`) | today: `pre_barrier_unproven` |
| A2-99 | (4.2) each of criteria 1-4 refuses on the trade-25 world with ONE mutation, re-run end-to-end through `correct_cohort_provenance` with nothing written: non-ancestor (A2-44), ET date = fill session (A2-45), five-cent pivot (A2-49), record at fire_hi - 1 s (A2-57); plus the uncomputed interval refused at the TRIGGER (A2-27) | -- |
| A2-100 | (4.3) replay REWRITTEN -> H1 count drops by one, trade 25 named; GROWN -> ADMIT, count unchanged | -- |
| A2-101 | (4.4) = A2-60 re-asserted against the migrated HEAD schema | -- |
| A2-102 | (4.5) = A2-09 green on the final head | -- |
| A2-103 | (4.6) = A2-23 + A2-25 | -- |
| A2-104 | real-repo check, SKIPPED only when `git cat-file -e 9f315cc6` fails: `git show 9f315cc6:docs/rd-state.md` line 57 hashes to the pinned sha256 (the fixture IS the record) | -- |

## 7. Accepted limitations (ids; each REASON is in the ledger, R1.0 section "AL2")

AL2-1 SQL cannot verify the service's criterion-3 verdict (S4.3a residual; F8). AL2-2 containment
proves mention, not exclusivity (the AMN mention; F13). AL2-3 swapped numerals admit (F13).
AL2-4 a hand-run barrier DROP is undetectable; (t1) sees file-borne drops only (P14, F2.T).
AL2-5 `gap_era_reconstructed` is named and UNMINTED; two-valued `LATCH_FREEZE_TIERS` does not close
the vocabulary (F2). AL2-6 the time anchor is practical, not cryptographic; ref age recorded, never
verdict-bearing (S12.1 #7, F5). AL2-7 `match_only` is net-change evidence, recorded as a gap kind,
never coverage (F2.I s1). AL2-8 an MM-DD record across a year boundary refuses; the ISO form admits
(F13 year rule). AL2-9 SQL binds endpoints raw only; UTC conversions and durations are service-recorded
(R8-03). AL2-10 replay needs the local repo + git; without them rows read `tier2_unverifiable` and are
excluded. AL2-11 the S12.2b instrument items are carved to `22-A2i` (brief OUT).

## 8. Envelope (for every review prompt; from brief section 2)

IN: the tier-2 class end to end (seventh column, third tier, the four-part conjunction as a preflight
with attestation, fail-closed read-time replay, the CLI option + pin bump, the single rounding
authority); trade 25's correction at a witnessed gate; the continuity interval recorded on the row;
the #11 sweep for the tier enum + the verdict vocabulary; the 0039 rebuild under CHARC's six
conditions; (t1); the four readers' named exclusion. OUT: trades 19/24/28 (named-pending); the era
model and three-valued `LATCH_FREEZE_TIERS` (22-A2i); the S12.2b items (22-A2i); 22-B; a
`trades.initial_stop` correction surface; any new UI surface (the two exclusion render lines are F10's
"never silently uncounted" on existing readers, R0.12 note 8).

## 9. The witness (post-merge; ONE step per operator result; orchestrator-run)

1. Stop `swing web`; plain sqlite3 `BEGIN EXCLUSIVE; ROLLBACK` on live succeeds.
2. `swing db-migrate`: the 22a2 gate image is written and its path ECHOED (the D32 production proof);
   read `fill_envelope_identity` for fill 48 (expect absent).
3. `python scripts/schema_manifest.py --db <live>` clean at v39.
4. `swing journal correct-cohort-provenance 25 --cited-candidate 12284 --cited-recommendation 169
   --reason "<r>" --frozen-value-evidence <file> --dry-run` -> ADMIT, four clauses + interval printed.
5. The same without `--dry-run`; `journal provenance-corrections` shows the row + `ADMIT`; fill 48's
   `fill_envelope_identity` row now present.
6. RD re-reads the H1 count; the witness QUOTES the reader's number (no expected count is pinned).
