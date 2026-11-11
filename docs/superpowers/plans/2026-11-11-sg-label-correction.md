# Plan: the watch-origin label correction arc (D102 + D103 + D104 + D86)

**Brief:** `docs/sg-label-correction-arc-brief.md` (CHARC, `3b64f9ec`). **Base:** `main` at `f1eb4051`. **Worktree:** `.worktrees/sg-label`, branch `sg-label`.
**Ledger (round-0 census, the fork packet, every round):** `docs/superpowers/plans/2026-11-11-sg-label-correction.ledger.md`. Rulings and their reasoning live there, not here.
**Status:** DRAFT at round 0. Every fork is encoded on its RECOMMENDED branch and tagged `[F#]`; a ruling for the other branch replaces the tagged text before round 1.

Order of work: T3, T4, T1, T2 (T3 and T4 are independent and small; T1 lands the schema T2's tests do not need, but T1's service reads the same `candidate_id` semantics T2 changes, so T1 is proven on the pre-T2 entry path first). One commit per task step below. Fast suite green before Reviewer A on the executing diff.

Locks (brief section 2, restated as file sets): `swing/trades/` edits ONLY in `cohort_provenance_correction.py`, `entry.py`, `exit.py`. `swing/data/` edits ONLY in `migrations/0042_*.sql`, `models.py`, `repos/provenance_corrections.py`, plus `db.py` (the version constant and the backup-gate row every migration adds; flagged in the ledger as P13 for CHARC to confirm it is inside "migration 0042"). `swing/data/repos/trades.py`, `swing/trades/origin.py`, `swing/trades/latched_origin.py` are NOT edited. No price-path, sizing, latch or parity-ledger change. `0033`/`0034` text does not move.

---

## T3 (D103) -- one comment line

**File:** `swing/recommendations/hypothesis.py:379`.

Replace `The ONLY opt-in caller is the shadow-expectancy attribution wrapper.` with:

`Every opt-in caller is pinned by tests/integration/test_include_baseline_inventory_guard.py (an AST census of the call sites); this comment does not enumerate them.`

Reason for this branch over enumerating three paths: the guard test IS the enforcement and fails on a fourth site; a path list in a comment is a hand-maintained roster (gotcha #31's shape). Verified by read today: the three AST sites are `research/harness/shadow_expectancy/attribution.py:19`, `swing/recommendations/hypothesis_prefill.py:73`, `swing/web/view_models/watchlist.py:40`; `cohort_provenance_correction.py:1567` is a comment, not a call.

No test (brief). Commit: `docs(recommendations): T3 (D103) -- the include_baseline caller comment points at its census`.

---

## T4 (D86) -- the trade-event input domain at both record services

### T4.1 the shared date normaliser

**File:** `swing/trades/exit.py:_normalize_trade_event_date_to_iso` (`:99`).

Today: date-only input goes through `date.fromisoformat`, which on Python 3.11+ ACCEPTS compact `20261019` and week `2026-W01-1` (measured on this box: `2026-W01-1` -> `2025-12-29`), and the T-branch goes through `datetime.fromisoformat`, which ACCEPTS `20261019T160000`. The function returns `f"{raw}T16:00:00"`, so the stored prefix is the raw string.

Change: a SHAPE gate before each parse, ASCII regexes compiled at module level:
- date-only: `^\d{4}-\d{2}-\d{2}$` then `date.fromisoformat` (calendar validity);
- T-form: `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?$` then `datetime.fromisoformat` and the existing tz-aware refusal (a `+hh:mm`/`Z` suffix now fails the shape gate first; keep the tz branch as the belt).
- Refusal text names the canonical form: `"{field_name} {raw!r} is not in the canonical form YYYY-MM-DD (or YYYY-MM-DDTHH:MM[:SS[.ffffff]])"`. `ValueError` (both callers already deliver `ValueError`).

`record_entry` (`entry.py:1172-1182`) already routes `entry_date` through this helper after its `"T" in` guard, so ONE change covers both services (D86's "never one side"). The entry route and CLI deliver `ValueError` unchanged.

### T4.2 the price refusal, both services

- **Exit:** `exit.py` `check_exit_preconditions` (`:397`): `if not (req.exit_price > 0)` -> `if not (math.isfinite(req.exit_price) and req.exit_price > 0)`; `ExitPriceRefusedError` text gains `finite`. (`NaN` was already refused: `nan > 0` is False.)
- **Entry:** `record_entry` has NO price-domain refusal today (read: the only price check is `initial_stop >= entry_price` at `entry.py:1188`, which `inf` passes and `NaN` passes into an `IntegrityError` at the NOT NULL). Add, immediately before that check: `if not (math.isfinite(req.entry_price) and req.entry_price > 0): raise ValueError("entry price must be a finite number > 0; got ...")`. Placed AFTER the date normalisation and BEFORE the stop comparison so LOCK clause (c)'s existing branch order is preserved for every input the old code accepted.

### T4.3 the entry route's raw-authority rung

**File:** `swing/web/routes/trades.py`, entry POST (`json.loads` at `:1215`). The exit POST's first rung is `_exit_raw_anchor_is_refused(raw)` (`:2475`) -> `_reject_anchor(_EXIT_RAW_ANCHOR_UNREADABLE_TEXT)`. Add the same rung BEFORE `json.loads` on the entry side: when `schwab_source_value_json.strip()` and the ONE authority (`canonical_envelope_identity`, the function `_exit_raw_anchor_is_refused` calls) refuses the raw string -> `_rerender_entry_form_with_error(..., error_message=_ENTRY_RAW_ANCHOR_UNREADABLE_TEXT, submitted_schwab_source_value_json=None, submitted_auto_fill_audit_at=None, ...)` with status 400 (the anchor CLEARED). Reuse: extract `_raw_anchor_is_refused(raw)` from `_exit_raw_anchor_is_refused` and keep the exit name as an alias, so the two ladders read one rung.

### T4 tests (RED first; file `tests/trades/test_d86_input_domain.py` + `tests/web/test_routes/test_d86_entry_raw_rung.py`)

| # | Test | Old code | New code |
|---|---|---|---|
| 4a | `record_exit` with `exit_date="20261019"` | accepted; fill stored `20261019T16:00:00` | `ValueError` naming `YYYY-MM-DD`; zero fills inserted |
| 4b | `record_entry` with `entry_date="20261019"` | accepted; `trades.entry_date='20261019'` | `ValueError`, no trade row |
| 4c | both, `"2026-W01-1"` | accepted (parses to 2025-12-29), stored verbatim | `ValueError` |
| 4d | both, T-form `"20261019T160000"` | accepted (exit) | `ValueError` |
| 4e | `record_exit` `exit_price=float("inf")` | fill row with `price=inf` | `ExitPriceRefusedError`, zero fills |
| 4f | `record_entry` `entry_price=float("inf")` | trade + fill with `inf` | `ValueError`, zero rows |
| 4g | regression keepers: `"2026-10-19"`, `"2026-10-19T09:31:00"`, `"2026-10-19T09:31:00.123456"` accepted unchanged | pass | pass |
| 4h | entry POST with a raw anchor the authority refuses (duplicate `schwab_order_id` key) and `fill_origin_at_form_render=schwab_auto` | `json.loads` keeps the last key; the request proceeds to `record_entry` | 400, the error text, the re-rendered form's hidden anchor is EMPTY (assert the input's `value=""`) |

The verbatim-ticker clause stays banked on the D86 row: no test in this arc shows it bites (the arc does not touch `list_observable_detections` or the warm).

Commits: `fix(trades): T4.1 (D86) -- one canonical date grammar at the shared normaliser`, `fix(trades): T4.2 (D86) -- finite-price refusal at record_entry and record_exit`, `fix(web): T4.3 (D86) -- the entry anchor ladder gets the exit ladder's raw rung`.

---

## T1 (D104) -- migration 0042: a second correction KIND on `provenance_corrections`

### T1.0 what the live HEAD actually is (premises P1-P5, ledger)

The live table is 0039's REBUILD (+ 0041's update trigger, + 0037's `trg_pc_no_replace` re-created by 0039), not 0036: FOUR triggers (`_citation_graph` 1,540 lines, `_append_only_update`, `_append_only_delete`, `trg_pc_no_replace`), an existing discriminator `admission_tier IN ('last_word','latch_ladder','latch_ladder_tier2')`, and `trg_eia_audit_trail` (0040, ON `entry_intent_attestations`) reading `provenance_corrections.corrected_fields_json`. Two live rows: id 1 (trade 23, `last_word`), id 2 (trade 25, `latch_ladder_tier2`); `sqlite_sequence.seq = 2`.

### T1.1 the column design `[F1 = A]`

- NEW `correction_kind TEXT NOT NULL DEFAULT 'fill_unset_provenance' CHECK (correction_kind IN ('fill_unset_provenance', 'watch_fire_relabel'))`. The two live rows backfill to `'fill_unset_provenance'` by the copy statement (explicitly, not by the DEFAULT).
- `admission_tier` widened by ONE value: `'last_fire'` `[F2 = B]`. A coupling CHECK: `(correction_kind = 'fill_unset_provenance' AND admission_tier IN ('last_word','latch_ladder','latch_ladder_tier2')) OR (correction_kind = 'watch_fire_relabel' AND admission_tier = 'last_fire')`.
- `cited_daily_recommendation_id`, `cited_recommendation_action_session_date`, `cited_recommendation_snapshot_json` lose `NOT NULL` `[F3 = NULL for kind 2]` (P2: there is NO `daily_recommendations` row for SG on eval 193 or 194 -- live SG rows are only 289/291/295, all `near_trigger`, evals 179/181/183). A kind CHECK: kind 1 -> all three NOT NULL; kind 2 -> all three NULL.

### T1.2 migration `swing/data/migrations/0042_provenance_corrections_watch_fire_relabel.sql`

Header: reversibility note, the two-row backfill, the rename hazard below, and the list of every object dropped and re-created by name (D51: a rebuild's manifest diff shows zero deletions unless the header names each).

Steps, inside the runner's `BEGIN`/`COMMIT` (`_apply_migration`, `foreign_keys=OFF`):

1. `CREATE TABLE provenance_corrections__0042 (...)`: every 0039 column and CHECK VERBATIM except the edits listed in T1.3, plus `correction_kind` as the LAST column.
2. `INSERT INTO provenance_corrections__0042 (<every 0039 column>, correction_kind) SELECT <every 0039 column>, 'fill_unset_provenance' FROM provenance_corrections;` (explicit column lists both sides; 0039 `:584-668` is the template).
3. Carry `sqlite_sequence` BY STATEMENT (0039 `:669-673` idiom, `__0042` name).
4. `DROP TABLE provenance_corrections;`
5. **`PRAGMA legacy_alter_table=ON; ALTER TABLE provenance_corrections__0042 RENAME TO provenance_corrections; PRAGMA legacy_alter_table=OFF;`** -- the 0040 `:301-303` idiom, NOT 0039's bare rename. MEASURED on SQLite 3.50.4 (this box): with `legacy_alter_table=0` the rename FAILS `error in trigger trg_b: no such table: main.a` when another table's trigger references the dropped name; `trg_eia_audit_trail` (created by 0040, AFTER 0039 ran) is exactly that reference. 0039's form would abort 0042 on every v41 DB. RED discriminator 1j below.
6. Re-create VERBATIM (source statements named in the header): `ux_provenance_corrections_trade`, `ix_provenance_corrections_cited_candidate`, `trg_provenance_corrections_append_only_delete`, `trg_pc_no_replace` -- created AFTER the rows exist (the REPLACE gotcha: a BEFORE INSERT barrier created after the seeded rows).
7. Re-create `trg_provenance_corrections_append_only_update` (body T1.4.3) and `trg_provenance_corrections_citation_graph` (body T1.4.1-2).
8. `UPDATE schema_version SET version = 42;`

`swing/data/db.py`: `EXPECTED_SCHEMA_VERSION = 42`; `PHASE22_SG_LABEL_PRE_MIGRATION_EXPECTED_TABLES = set(PHASE22_ARC_I_PRE_MIGRATION_EXPECTED_TABLES)` (0041 created no table; a floor, missing-only, comment cites the v41 measurement); append `BackupGateSpec(41, "sg-label", PHASE22_SG_LABEL_PRE_MIGRATION_EXPECTED_TABLES, "_sg_label_backup_gate", "pre-sg-label")`. The shared gate body fires on `current_version == 41 AND target_version >= 42` (the Phase-9 clause; never `<=`, never `== target - 1`). `python scripts/schema_manifest.py --write` in the SAME commit; the commit body lists the manifest's deleted lines (expected: none beyond the re-created objects' changed text).

### T1.3 the table CHECKs: each kind-1 arm VERBATIM inside a kind CASE

Form for every value-shape CHECK that kind 2 changes (the outer CASE has `ELSE 0`, so an unknown kind fails closed; each inner arm keeps 0039's own `CASE WHEN json_valid(...) THEN COALESCE(..., 0) ELSE 0 END`):

```sql
CHECK (CASE correction_kind
         WHEN 'fill_unset_provenance' THEN <0039 predicate, verbatim>
         WHEN 'watch_fire_relabel'    THEN <kind-2 predicate>
         ELSE 0 END)
```

Applied to these five (0039 text located by content, line numbers drift):

| CHECK | kind 1 (verbatim) | kind 2 |
|---|---|---|
| `corrected_fields_json` | exactly the 3 fields in order | `json_valid` AND `json_array_length = 2` AND `$[0]='trades.hypothesis_label'` AND `$[1]='trades.candidate_id'` `[F4]` |
| `applied_value_json` | cid = cited, label text non-empty, origin text = `'pipeline_aplus'` | cid = `cited_candidate_id`; `json_type(label)='text'` AND `length(trim(label))>0`; origin = `'pipeline_watch_manual'`; `json_type(... candidate_id) = 'integer'` |
| `pre_value_json` | origin `'manual_off_pipeline'`, label JSON null, cid JSON null | origin = `'pipeline_watch_manual'`; `json_type(label)='text'` AND `length(trim(label))>0`; `json_type(cid)='integer'`; AND the pre cid `!=` `cited_candidate_id` (a relabel that does not MOVE the anchor is not a fire relabel) |
| `cited_candidate_snapshot_json` | id, run, `bucket='aplus'`, criteria array | id, run, `bucket='watch'`, criteria array |
| recommendation presence (NEW) | all three NOT NULL | all three NULL |

Every kind-2 predicate is wrapped `COALESCE(<conjunction>, 0)` inside its `json_valid` CASE -- one NULL in any conjunct is a refusal, never a pass.

Two existing CHECKs gain an `IS NULL OR` prefix because their column became nullable, and the kind CHECK above is what forbids NULL for kind 1:
- the three-predicate date guard on `cited_recommendation_action_session_date`: `cited_recommendation_action_session_date IS NULL OR (<0039 three predicates>)` -- without the prefix `date(NULL) IS NOT NULL` is FALSE and every kind-2 row is refused;
- the recommendation snapshot CHECK: `cited_recommendation_snapshot_json IS NULL OR (<0039 CASE>)` -- `json_valid(NULL)` is NULL, the CASE falls to `ELSE 0`, so without the prefix every kind-2 row is refused.

`CHECK (cited_recommendation_action_session_date <= entry_fill_session_date)` stays verbatim (NULL passes; kind 1 is non-null by the presence CHECK). The coupling CHECK from T1.1. Every other 0039 CHECK verbatim.

### T1.4 the three trigger bodies

#### T1.4.1 `trg_provenance_corrections_citation_graph` -- one trigger, kind-dispatched at THREE clauses

The 0039 statement is copied VERBATIM with exactly three edits; all other clauses (run anchors, pipeline row, status interval, registry name, entry fill, ticker equality, the four fill-side operands block, the persist-canonical envelope clause, the latch/tier2 branch bodies) apply to BOTH kinds unchanged. The top-level shape stays `WHEN NOT ( ... )`; every top-level conjunct is `EXISTS`, `IS NULL`-boolean or `COALESCE(...,0)`, so the WHEN is never NULL (re-asserted by test 1h).

Edit 1 -- the candidate clause (first conjunct):

```sql
    EXISTS (SELECT 1 FROM candidates ca
            WHERE ca.id = NEW.cited_candidate_id
              AND ca.evaluation_run_id = NEW.cited_evaluation_run_id
              AND ca.bucket = CASE NEW.correction_kind
                                WHEN 'fill_unset_provenance' THEN 'aplus'
                                WHEN 'watch_fire_relabel'    THEN 'watch'
                              END)
```
(An unknown kind yields `ca.bucket = NULL` -> no row -> `EXISTS` false -> refusal.)

Edit 2 -- the recommendation clause (third conjunct), wrapped:

```sql
    AND COALESCE(CASE NEW.correction_kind
        WHEN 'fill_unset_provenance' THEN
            EXISTS (SELECT 1 FROM daily_recommendations dr
                    WHERE dr.id = NEW.cited_daily_recommendation_id
                      AND dr.evaluation_run_id = NEW.cited_evaluation_run_id
                      AND dr.recommendation = 'today_decision'
                      AND dr.action_session_date
                          = NEW.cited_recommendation_action_session_date
                      AND dr.ticker = (SELECT ca.ticker FROM candidates ca
                                       WHERE ca.id = NEW.cited_candidate_id))
        WHEN 'watch_fire_relabel' THEN
            (NEW.cited_daily_recommendation_id IS NULL
             AND NEW.cited_recommendation_action_session_date IS NULL
             AND NEW.cited_recommendation_snapshot_json IS NULL
             -- the row DESCRIBES the write of its own transaction: the
             -- service UPDATEs trades BEFORE it INSERTs this row
             -- (cohort_provenance_correction.py _correct_..._inner), so at
             -- INSERT time the trade carries the applied values.
             AND EXISTS (SELECT 1 FROM trades t
                         WHERE t.id = NEW.trade_id
                           AND t.trade_origin = 'pipeline_watch_manual'
                           AND t.candidate_id = NEW.cited_candidate_id
                           AND t.hypothesis_label = json_extract(
                               NEW.applied_value_json,
                               '$."trades.hypothesis_label"'))
             -- the anchor being MOVED names a real row of the same ticker
             AND EXISTS (SELECT 1 FROM candidates pc
                         WHERE pc.id = json_extract(NEW.pre_value_json,
                                                    '$."trades.candidate_id"')
                           AND pc.ticker = (SELECT ca.ticker FROM candidates ca
                                            WHERE ca.id = NEW.cited_candidate_id)))
        ELSE 0 END, 0)
```
(SQLite runs a BEFORE INSERT trigger BEFORE the row's CHECKs, so the table CHECKs do NOT protect these `json_extract` calls: on malformed JSON `json_extract` RAISES `malformed JSON` instead of reaching `RAISE(ABORT)` (22A-R3-12's class). The executing encoding therefore wraps each of the two reads in `CASE WHEN json_valid(NEW.<col>) THEN json_extract(...) END` -- a malformed document yields NULL, the `EXISTS` finds no row, the clause is false, the trigger fires its own message. Test 1i pins that.)

Edit 3 -- the 22-A tier block (`AND COALESCE(( ... ), 0)` headed `22-A: THE TIER AND ITS CITATION`) gains a THIRD disjunct beside the `last_word` and latch disjuncts, and the `last_word` and latch disjuncts each gain `NEW.correction_kind = 'fill_unset_provenance' AND` as their first conjunct:

```sql
        OR
        -- 'last_fire' (kind 2): no latch authority exists for this fill --
        -- the SAME absence-of-authority test the last_word branch makes
        -- (Codex 22A-R6-01's reason applies verbatim: a kind-2 row may not
        -- bypass a latch the fill's own order resolves to).
        (NEW.correction_kind = 'watch_fire_relabel'
         AND NEW.admission_tier = 'last_fire'
         AND NEW.cited_latch_link_id IS NULL
         AND NEW.cited_latch_validity_intent_id IS NULL
         AND NEW.cited_latch_place_intent_id IS NULL
         AND NEW.cited_latch_broker_order_id IS NULL
         AND NEW.cited_latch_probe_json IS NULL
         AND NEW.cited_frozen_value_evidence_json IS NULL
         AND NOT EXISTS (
             SELECT 1 FROM latch_order_mandate_links l
              WHERE l.broker_order_id = (
                  SELECT fei.broker_order_id
                    FROM fill_envelope_identity fei
                    JOIN fills f ON f.fill_id = fei.fill_id
                   WHERE fei.fill_id = NEW.entry_fill_id_at_correction
                     AND fei.envelope_raw = f.schwab_source_value_json
                     AND fei.envelope_state = 'canonical')))
```

The RAISE message gains one sentence naming the kind-2 graph (bucket `watch`, no recommendation, the trade carrying the applied values, the moved anchor of the same ticker, `last_fire` with no latch authority).

What the trigger does NOT enforce, by design, and where it IS enforced: "the cited fire is the LAST narrow-rule fire before the fill" is a ranking over the matcher's output, i.e. a Python judgment (RD's rule: SQL verifies a FACT, never re-derives a judgment across the engine boundary). It is enforced in the service (T1.6) and recorded in the row (`admission_tier='last_fire'`, the frozen candidate snapshot, `derivation_rule_version`) so the reader re-derives it (T1.7).

#### T1.4.2 `trg_pc_no_replace`, `_append_only_delete`: verbatim (0039 `:688-702`).

#### T1.4.3 `trg_provenance_corrections_append_only_update`

0041's body VERBATIM with three `=` -> `IS` changes and one added line:

```sql
           AND (NEW.cited_daily_recommendation_id IS OLD.cited_daily_recommendation_id)
           ...
           AND (NEW.cited_recommendation_action_session_date
                IS OLD.cited_recommendation_action_session_date)
           ...
           AND (NEW.cited_recommendation_snapshot_json
                IS OLD.cited_recommendation_snapshot_json)
           ...
           AND NEW.correction_kind = OLD.correction_kind
```

Why (P5): with `=`, a kind-2 row's NULL makes the conjunction NULL, `COALESCE(...,0)` -> 0, `NOT 0` -> the trigger FIRES -- so the ONE permitted UPDATE (the FK-driven `entry_fill_id` SET NULL when `split_into_partials` deletes the cited fill, `reconciliation_auto_correct.py:2926`) would ABORT on a kind-2 row: the 0036 R7 priority inversion, re-introduced by the widening. `correction_kind` is NOT NULL, so `=` is exact there. RED discriminator 1g.

### T1.5 the Python mirrors (`swing/data/models.py`)

- `PROVENANCE_CORRECTION_KIND_FILL_UNSET = "fill_unset_provenance"`, `PROVENANCE_CORRECTION_KIND_WATCH_FIRE = "watch_fire_relabel"`, `PROVENANCE_CORRECTION_KINDS = frozenset({...})`.
- `PROVENANCE_ADMISSION_TIER_LAST_FIRE = "last_fire"`; `PROVENANCE_ADMISSION_TIERS` becomes the FOUR values (it is the SQL IN-list mirror); NEW `PROVENANCE_ADMISSION_TIERS_BY_KIND = {FILL_UNSET: frozenset(3 old), WATCH_FIRE: frozenset({"last_fire"})}`.
- `PROVENANCE_WATCH_FIRE_CORRECTED_FIELDS = ("trades.hypothesis_label", "trades.candidate_id")`; `PROVENANCE_CORRECTED_FIELDS` unchanged (kind 1).
- `PROVENANCE_WATCH_FIRE_ORIGIN = "pipeline_watch_manual"`.
- `ProvenanceCorrection`: `cited_daily_recommendation_id: int | None`, `cited_recommendation_action_session_date: str | None`, `cited_recommendation_snapshot_json: str | None`; new field `correction_kind: str = PROVENANCE_CORRECTION_KIND_FILL_UNSET` (last, defaulted). `__post_init__`: kind in KINDS; tier in `TIERS_BY_KIND[kind]` (so `last_fire` on kind 1 and `last_word` on kind 2 both raise); recommendation triple presence by kind; corrected-fields list by kind; `_require_value_envelope` gains a `kind` parameter carrying the T1.3 kind-2 rules (pre: origin `pipeline_watch_manual`, label non-empty str, cid int and `!=` cited; applied: origin `pipeline_watch_manual`, cid == cited, label non-empty); candidate snapshot `bucket` by kind; the recommendation snapshot validated only when present. The kind-2 latch-citation rule reuses the `last_word` branch's "all seven NULL".
- `swing/data/repos/provenance_corrections.py`: append `"correction_kind"` to `_COLUMNS` (the mapper is `_COLUMNS`-driven, so read and write widen together); `test_a2_24`'s `repo._COLUMNS[-1] == PROVENANCE_TIER2_EVIDENCE_FIELD` pin moves to `[-2]` with `[-1] == "correction_kind"`.

### T1.6 the service (`swing/trades/cohort_provenance_correction.py`)

New public pair, the existing kind-1 pair untouched in signature:

- `correct_watch_fire_label(conn, *, trade_id: int, fire_candidate_id: int, reason: str | None, cfg=None) -> CohortProvenanceCorrectionResult` -- OUTER: rejects a caller-held transaction (`CallerHeldTransactionError`), owns `BEGIN IMMEDIATE` / COMMIT / ROLLBACK, the shape of `correct_cohort_provenance` (`:2793`).
- `preview_watch_fire_label(...)` -- dry run through the existing SAVEPOINT preview machinery.
- `_correct_watch_fire_label_inner(...)` -- never commits; repo-level callees only.
- `[F8]` NO sandbox short-circuit, mirroring kind 1 (read: the module has none; nothing here writes a Schwab-derived domain row).

Inner step order (the SELECT-first idempotency order):
1. `_load_trade_or_refuse`; `fire_candidate_id` must be a non-bool `int`.
2. SELECT `get_correction_for_trade`. Existing kind-2 row citing the same candidate -> `already_applied` (return its id; payload not re-validated). Existing row of either kind otherwise -> refusal naming its kind and citation. **The kind-1 `_authorize` comparison (`int(existing.cited_daily_recommendation_id)`, `:2125`) is changed to compare kind first** so a kind-1 call against a trade carrying a kind-2 row refuses by message instead of `TypeError` on `int(None)` (mirror-closure item).
3. Kind-2 eligibility gate `[F5]` (terminal, reason named): `trade_origin == 'pipeline_watch_manual'`; `hypothesis_label` non-empty; `candidate_id` non-null; and the current `candidate_id` IS the ticker's last-word row before the fill (the existing `_assert_last_word_before_the_fill` ranking, reused unchanged, applied to `trade.candidate_id`) -- the D102 defect signature, so this instrument corrects a batch-night stamp and nothing else.
4. `_reason_or_refuse(reason)`.
5. `resolve_authoritative_entry_fill`; `_resolve_latch_citation` -> a latched trade is REFUSED ("the latch path is untouched; a latched fill's label is the fire's by construction").
6. Anchor the cited fire: candidate row exists, same ticker as the trade, `bucket == 'watch'`, its run + action session + run_ts validated by the existing helpers; `action_session_date <= fill session` (the evidence rule, unchanged).
7. **The last-fire guard `[F2 = B]`:** over the ticker's candidate rows ranked by the existing last-word key `(action_session_date, run_ts, candidate_id)` with `action_session_date <= fill session`, EVERY competitor validated (the `_assert_last_word_before_the_fill` validation scope), walk from the newest: the first row for which `derive_cohort_keys_for_fire` (as-of registry, `include_baseline=False`) returns exactly one match is THE last fire. Refuse if it is not `fire_candidate_id` (message names the derived fire, the `--to` confirmation idiom), if none exists within the window, or if the walk leaves the window `WATCH_FIRE_WINDOW_ROWS = 5` (the same N as T2, one constant imported by both). A derivation refusal on a competitor (multi-match, clock margin, no pipeline bound) is a refusal of the correction, not a skip -- a row the ranking cannot read cannot be passed over.
8. `derive_cohort_keys_for_fire(conn, candidate=..., candidate_id=fire_candidate_id, evaluation_run_id=..., run_ts_parsed=..., gate=<the rung-14a same-session gate>)` CALLED UNCHANGED; the kind-2 applied origin is the trade's own (`pipeline_watch_manual`), and `keys.trade_origin` (hard-coded `APLUS_TRADE_ORIGIN`) is not read on this path. Applied label = `keys.hypothesis_label`; refuse if it equals the current label AND the current candidate is the fire (no-op).
9. `update_cohort_provenance(conn, trade_id, hypothesis_label=label, candidate_id=fire_candidate_id, trade_origin='pipeline_watch_manual')` (the existing repo writer, unchanged; origin re-written to its own value).
10. `insert_provenance_correction(..., correction_kind='watch_fire_relabel', admission_tier='last_fire', cited_daily_recommendation_id=None, cited_recommendation_action_session_date=None, cited_recommendation_snapshot_json=None, corrected_fields_json=json.dumps(list(PROVENANCE_WATCH_FIRE_CORRECTED_FIELDS)), pre/applied envelopes with all three keys, every other cited_* column filled exactly as kind 1 fills it)`.

`derivation_rule_version` `[F9]`: the derivation closure gains the watch rules (`_near_aplus_extension_match`, `_sub_aplus_vcp_not_formed_match`, `DOCTRINE_DEFENSIBLE_MISS_SET`, `match_candidate_to_hypotheses` if the closure walker reports it). Membership is decided by the existing closure-walker test, not by this list; the digest moves, so `DERIVATION_RULE_HISTORY` gains `("2026-11-1x.1", <digest>)` and both kinds write the head. The two live rows keep their versions (history is append-only).

### T1.7 the reader and the CLI

- `read_provenance_corrections` / `_read_provenance_corrections_inner` / `_snapshot_drift` / `_derivation_input_drift` (`:3270`, re-derives the label and checks `bucket == APLUS_BUCKET` at `:3359-3369`): dispatch on `row.correction_kind`. Kind 2: skip the recommendation snapshot drift (nothing cited); bucket expectation `watch`; re-derive with the kind-2 rule including the last-fire ranking (`CITATION DRIFT` when the derived last fire is no longer the cited row). Kind 1 unchanged.
- `swing/cli.py` `journal correct-cohort-provenance`: `--cited-candidate` and `--cited-recommendation` become `required=False`; NEW `--cite-fire-candidate <candidate_id>`; exactly one mode: (`--cited-candidate` AND `--cited-recommendation`) XOR `--cite-fire-candidate`, else `click.UsageError`. The fire mode calls `correct_watch_fire_label` / `preview_watch_fire_label`; `--frozen-value-evidence` with fire mode is a usage error. Service `ValueError` -> `click.ClickException` (the existing wrap). The docstring gains one paragraph for the fire mode (ASCII only).
- `swing journal provenance-corrections` (`COHORT_FIELD_ORDER`, `cli.py:3587`): prints `correction_kind`; renders the recommendation citation as `(none: watch-fire relabel)` for kind 2.

### T1 tests (RED first)

Fixture: `tests/trades/_cohort_provenance_fixtures.py::build_sg_case(conn) -> dict`, seeded from the LIVE shape read `mode=ro` 2026-11-11 (ledger "live-shape facts"): eval 193 (`run_ts 2026-11-04T17:30:04`, action `2026-11-05`, data_asof `2026-11-04`) + pipeline run (complete, finished `2026-11-04T17:34:17`); eval 194 (`2026-11-05T17:30:15`, action `2026-11-06`) + pipeline run (finished `2026-11-05T17:36:20`); eval 192 (action `2026-11-04`) for the window; candidates with EXPLICIT ids 15811/15901/15980 (watch) carrying the live 18 criteria each (15901: all pass except `proximity_20ma` fail; 15980: `proximity_20ma` + `tightness` fail; 15811: as live, read at execution); registry ids 1-5 with the live names and statuses and the live history rows 1-8 verbatim (incl. H2's paused/active pair and H3 `closed-target-met`); trade 29 shape (`SG`, `pipeline_watch_manual`, `hypothesis_test_by_design`, label `'Broad-watch baseline (watch); failed: proximity_20ma, tightness'`, `candidate_id 15980`, entry 2026-11-06 @ 11.95, 11 sh); fill (entry, `2026-11-06T16:00:00`, qty 11, price 11.95, `schwab_auto_then_operator_corrected`, the live envelope text) + its canonical `fill_envelope_identity` row (broker order `1008560562620`); NO `daily_recommendations` row for SG on 193/194; no latch link. No value is chosen to make a test pass; any value not read live is read at execution and recorded.

| # | Test (file) | Pre-change (v41 / old code) | Post-change |
|---|---|---|---|
| 1a | `correct_watch_fire_label(trade, fire_candidate_id=15901)` on `build_sg_case` writes label `'Near-A+ defensible: extension test (watch); failed: proximity_20ma'`, `candidate_id=15901`, origin unchanged; row kind 2 / `last_fire` (`tests/trades/test_cohort_provenance_watch_fire.py`) | `ImportError` (no function) | passes; the label string asserted is the one RD witnessed in the briefing, NOT a fixture constant |
| 1b | the same truthful row, re-inserted RAW with `correction_kind='fill_unset_provenance'`/`admission_tier='last_word'` into a fresh `build_sg_case` DB -> `IntegrityError` (`tests/data/test_migration_0042_*.py`) | v41: refused (bucket/origin/pre CHECKs) -- RED only on the accept half | accept as kind 2, refuse as kind 1 |
| 1c | kind-2 row citing an `aplus` candidate (fixture variant: 15901 seeded `aplus`) -> refused (trigger edit 1 + snapshot CHECK) | n/a (column absent) | `IntegrityError` |
| 1d | kind-2 row whose cited candidate's action session (`2026-11-07`) post-dates the fill session -> refused by `cited_candidate_action_session_date <= entry_fill_session_date` | n/a | refused |
| 1e | kind-2 row with `applied_value_json` MISSING `"trades.hypothesis_label"` / `pre_value_json` missing `"trades.candidate_id"` -> refused (the COALESCE arms; brief item 4 re-read: kind 2 carries no probe blob, so the missing-key probe is the envelope) | n/a | refused; and a mutation test flips one kind-2 COALESCE to bare form and asserts the row is then ACCEPTED (proves the arm is load-bearing) |
| 1f | `INSERT OR REPLACE` and `INSERT ... ON CONFLICT DO NOTHING` of a second row for trade 29 -> `trg_pc_no_replace` ABORT; row count 1, id unchanged | same as today for kind 1 | same, for a kind-2 existing row |
| 1g | on a kind-2 row, `DELETE FROM fills WHERE fill_id = <cited>` (FK SET NULL) succeeds and leaves `entry_fill_id IS NULL`; any other UPDATE refused | with `=` on the recommendation columns: the delete ABORTS (computed: `NULL = NULL` -> NULL -> `COALESCE` 0 -> fires) | delete succeeds |
| 1h | the citation trigger's WHEN never evaluates NULL for a kind-2 row with every nullable column NULL (assert a deliberately broken kind-2 row RAISES the trigger message, not a CHECK message, by inserting with CHECKs satisfied and the graph broken: wrong ticker on the moved anchor) | n/a | trigger message |
| 1i | malformed `applied_value_json` on a kind-2 row reaches `RAISE(ABORT)`/CHECK, never `OperationalError: malformed JSON` | n/a | `IntegrityError` |
| 1j | `run_migrations` from a v41 DB built by `ensure_schema(target 41)` (carries `trg_eia_audit_trail`) applies 0042; a variant with 0039's bare RENAME is asserted to fail (pins the PRAGMA idiom) | the bare rename: `error in trigger trg_eia_audit_trail: no such table` | applies; version 42 |
| 1k | migrate a v41 DB holding the two live-shaped rows -> both present, `correction_kind='fill_unset_provenance'`, every column byte-equal, `sqlite_sequence.seq` carried; `db-migrate` twice is a no-op (row counts, schema text, `sqlite_sequence` unchanged) | n/a | passes |
| 1l | the backup gate fires at `current==41, target>=42` and not at `current==40` (the existing gate-table tests extended by one row) | gate absent | passes |
| 1m | DRIFT (mandatory member): the SQL `correction_kind IN (...)` set == `PROVENANCE_CORRECTION_KINDS`; the SQL `admission_tier IN (...)` set == `PROVENANCE_ADMISSION_TIERS` (4); the coupling CHECK's per-kind tier sets == `PROVENANCE_ADMISSION_TIERS_BY_KIND`; the trigger's kind literals (edit 1 CASE, edit 2 CASE, edit 3) == the Python constants; the kind-2 `bucket` literal == `'watch'`; the corrected-fields literals per kind == the two Python tuples. `test_a2_23`'s `len == 3` and `test_a2_25`'s regex `'(last_word|latch_ladder\w*)'` are updated to the four-value set (they would otherwise silently MISS `last_fire`) | `test_a2_23` asserts 3 | asserts 4, both kinds |
| 1n | service refusals, each with its message: trade origin `manual_off_pipeline`; latched trade; current candidate not the last-word row; cited 15811 when 15901 is the last fire (`--to` idiom: message names 15901); no fire within 5 rows; existing kind-1 row on the trade (refusal, no `TypeError`); replay of the same call -> `already_applied` with the same id (SELECT-first precedes the reason check: replay with `reason=None` succeeds) | `ImportError` | passes |
| 1o | caller-held transaction -> `CallerHeldTransactionError`; a failure after the trade UPDATE rolls back both writes (trade label unchanged, zero rows) | n/a | passes |
| 1p | reader: a kind-2 row reports no recommendation drift, re-derives clean; mutating the cited candidate's criteria in a scratch copy (raw, through the epoch barrier's test seam if one exists, else a pre-epoch id) reports `CITATION DRIFT` | n/a | passes |
| 1q | CLI (`tests/cli/test_correct_cohort_provenance_command.py`): `--cite-fire-candidate 15901 --dry-run` prints before/after with the exact label and writes nothing; with `--reason` writes; mode conflicts are `UsageError`; a service refusal is a `ClickException` (exit 1, no traceback); output ASCII | option absent | passes |

Mirror closure (BY READ, ledger lists the read per site; each enum member grepped SEPARATELY -- `'aplus'`, `"aplus"`, `pipeline_aplus`, `manual_off_pipeline`, `today_decision`, `last_word`, `latch_ladder`, plus the two new kind literals and `last_fire`):
SQL: the five kind-CASE CHECKs, the two `IS NULL OR` CHECKs, the coupling CHECK, the presence CHECK, trigger edits 1-3, the update trigger's four lines. Python: `models.py` constants + `ProvenanceCorrection.__post_init__` + `_require_value_envelope`; repo `_COLUMNS`; service `APLUS_BUCKET` gate (`:1106`, kind-1 only, unchanged), `REQUIRED_RECOMMENDATION` (`:1097`, kind-1 only), `UNSET_TRADE_ORIGIN` gate (`:878`, kind-1 only), the `_authorize` existing-row comparison (`:2125`, changed), `CohortProvenanceCorrectionResult.cited_daily_recommendation_id` (typed `int | None`), `_preview_from_existing`, the reader's bucket and re-derivation sites (`:3359-3369`, `:3405-3408`), `frozen_value_evidence.py:1305-1311/1393-1397` (tier2-only filters: unchanged, read), `latched_origin.py:44-47,103-106` (re-exports `PROVENANCE_ADMISSION_TIERS`: read every consumer of the re-export at execution), `entry_intent_assignment.py:307-316` (reads `corrected_fields_json` as a set: value-agnostic, unchanged), `trg_eia_audit_trail` (value-agnostic, unchanged), `cli.py:3587` + the command. JSON envelope keys (pre/applied: three keys both kinds; corrected-fields: per kind). Prose: the CLI docstrings/help, the migration header, `db.py`'s gate comment. Comparator: test 1m.

Commits: `feat(data): T1.1 (D104) -- migration 0042 rebuilds provenance_corrections with a second correction kind` (migration + `db.py` + manifest + `models.py` + repo + tests 1b-1m), `feat(trades): T1.2 (D104) -- the watch-fire relabel service` (service + tests 1a, 1n-1p), `feat(cli): T1.3 (D104) -- correct-cohort-provenance --cite-fire-candidate` (CLI + 1q). (#11: SQL CHECK + Python constant + dataclass validator land in ONE commit, the first.)

---

## T2 (D102) -- the entry form names the decision night

### T2.1 the label source (`swing/recommendations/hypothesis_prefill.py`)

The governance tripwire `tests/integration/test_include_baseline_inventory_guard.py` pins the `include_baseline=True` call sites at EXACTLY three (an AST census by path and line). T2 therefore adds NO call site: the ONE call at `:73` moves into a per-candidate helper, and both the old entry point and the new lister reach it.

- `label_for_candidate(conn, cand, *, registry, progress_summaries) -> str | None` -- the single `match_candidate_to_hypotheses(..., include_baseline=True)` call + `prioritize_recommendations`; returns `prioritized[0].suggested_label_descriptive` or `None`.
- `lookup_active_recommendation_label(...)` -- behaviour-identical, now: latest eval, its candidate, `label_for_candidate`.
- NEW `list_decision_nights(conn, *, ticker, starting_equity, budget_seconds=None, n=WATCH_FIRE_WINDOW_ROWS) -> list[DecisionNight]` where `DecisionNight(candidate_id, evaluation_run_id, action_session_date, data_asof_date, bucket, label)`. Rows: the ticker's `candidates` rows in runs owned by a COMPLETE `pipeline_runs` row, newest first by the last-word key, at most `n`, restricted to the bucket of the LATEST complete run's row for the ticker `[F6]` (the row `derive_trade_origin` reads -- so origin, candidate bucket and label cannot disagree). Registry and progress read ONCE (`build_recommendation_progress` is the expensive call). `CohortReadRacedError` propagates exactly as today (the VM degrades).
- `WATCH_FIRE_WINDOW_ROWS = 5` lives here (imported by T1.6). **N = 5** rationale in the ledger (one trading week of nightly briefings; SG needed 2; the window bounds both the operator's choice and the correction's last-fire walk).

### T2.2 the form (VM + template)

- `swing/web/view_models/trades.py` (the entry-form VM, `:583-614`): replace the single label with `decision_nights` (the list) + `decision_nights_anchor_json` (the offered set as JSON: `[{"candidate_id", "evaluation_run_id", "label"}]`) + `selected_decision_candidate_id` (default: the newest = today's behaviour). `hypothesis_label` stays populated with the newest night's label so every existing reader of the VM field is unchanged. The chooser is OMITTED (fields empty, today's hidden label path) when (a) no complete run holds a row for the ticker, or (b) the auto-filled envelope recognises an order (`envelope_recognises_an_order`, query-free) AND `list_links_for_broker_order` returns a link for it -- the latched entry (brief: "the chooser is absent on a latched entry").
- `swing/web/templates/partials/trade_entry_form.html.j2:151-152`: a `<select name="decision_candidate_id">`, one `<option>` per night showing `action_session_date (eval N, bucket): label` or `(no hypothesis match)`, newest selected; the hidden `decision_nights_anchor` input carries the JSON; the hidden `hypothesis_label` input is kept for the anchor-less path only.

### T2.3 the POST (`swing/web/routes/trades.py`, entry POST)

New form params `decision_candidate_id: str = Form("")`, `decision_nights_anchor: str = Form("")`. When `decision_nights_anchor` is non-blank, the 4-tier ladder, each rung -> 400 via `_rerender_entry_form_with_error` with the decision anchor CLEARED (`submitted_decision_nights_anchor=None`, `submitted_decision_candidate_id=None`, so the re-render re-lists fresh nights):
(a) malformed JSON; (b) not a list; (c) an entry missing `candidate_id`/`evaluation_run_id`/`label`; (d) invalid shapes: a non-int id, `decision_candidate_id` not an int or not IN the offered set, the chosen row absent or of another ticker or of a run whose `pipeline_runs` row is not complete.
Then SERVER-STAMP: the label is RECOMPUTED from the chosen row (`label_for_candidate`, current registry); if it differs from the offered set's `label` for that id -> 400 "the suggestion for <date> changed since the form was rendered; re-render" + cleared (the claimed-value consistency gate; the operator is never recorded under a label he did not see). The POST passes `candidate_id=<chosen>` and `hypothesis_label=<recomputed>` to `EntryRequest`; `record_entry` already honours a supplied `candidate_id` (`entry.py:2016`, used when not latched) -- no `entry.py` change for T2.
Anchor ABSENT (bare cURL, CLI tests, latched form): today's path verbatim.
The soft-warn confirm `form_values` dict (`:1960-1985`) carries `decision_candidate_id` and `decision_nights_anchor` (the gotcha: a `force=true` resubmit must not drop the anchor). Latched POST: the latch wins (existing `entry.py:2136-2144`), pinned by a test.
No fill-date validation of the chosen night: a non-latched decision night is OPERATOR-ASSERTED (D96 tier; RD states the cohort consequence at the plan read). The LQDA shape (trade 21: candidate night 2026-08-10 post-dates entry 2026-08-07) is recorded as banked, not refused.

### T2.4 the CLI `swing trade entry` `[F7]`

Unchanged behaviour (latest night); the prefill line prints the night it used (`eval <id>, session <date>`). A CLI chooser is BANKED (ledger).

### T2 tests (RED first)

| # | Test | Old | New |
|---|---|---|---|
| 2a | `list_decision_nights` on SG rows on three nights (192/193/194 shape) -> three entries newest-first with dates and labels (`Broad-watch baseline ... tightness` / `Near-A+ ... proximity_20ma` / 15811's) (`tests/recommendations/test_hypothesis_prefill.py`) | `ImportError` | passes |
| 2b | GET form renders three `<option>`s with the dates, newest `selected`; the anchor JSON lists three ids | one hidden label | passes |
| 2c | POST choosing the MIDDLE night (15901) persists `candidate_id=15901` and the H2 label; origin `pipeline_watch_manual` | persisted 15980 + baseline label | passes |
| 2d | POST with `decision_candidate_id` of a night with no row for the ticker / not in the anchor set -> 400, anchor cleared in the re-render; one test per ladder rung (a)-(d) and the label-changed gate | n/a | passes |
| 2e | default (no change of selection) persists the newest night -- today's values exactly | same | same (keeper) |
| 2f | latched entry: GET with an auto-filled envelope whose order has a link -> no `<select>`; POST carrying a decision anchor on a latched admission persists `latched.candidate_id` + latched label; the existing latch tests green unchanged | chooser absent (n/a) | passes |
| 2g | soft-warn `force=true` resubmit carries the anchor and persists the chosen night | n/a | passes |
| 2h | `test_include_baseline_true_call_sites_are_exactly_three` stays green (no new site) | green | green |
| 2i | ASCII: the option text and every new error message encode cp1252 | n/a | passes |

Commits: `feat(recommendations): T2.1 (D102) -- per-night labels from the single prefill call site`, `feat(web): T2.2-2.3 (D102) -- the entry form names the decision night`, `feat(cli): T2.4 (D102) -- the CLI prefill names its night`.

---

## T5 -- NOT this cell's: the operator's witnessed post-merge step

Sequence (brief section 2; the version guard makes a live run between merge and migration UNRUNNABLE): merge -> stop `swing web` -> exclusive-lock probe (plain `sqlite3`, `BEGIN EXCLUSIVE; ROLLBACK`) -> backup (the gate writes `pre-sg-label`; the pre-image is opened only as a COPY) -> `swing db-migrate` -> version 42 read `mode=ro` -> restart web -> `swing journal correct-cohort-provenance 29 --cite-fire-candidate 15901 --dry-run` (one step per message) -> the same with `--reason` -> the row read back `mode=ro` (`correction_kind='watch_fire_relabel'`, `admission_tier='last_fire'`, label, `candidate_id=15901`) -> RD's witness against eval 193 and the H2 count 4 -> 5. The cell proves the path on `build_sg_case` only.

---

## The `candidate_id` consumer table

Method: `grep -rlw candidate_id swing --include=*.py` -> 36 files (the brief says 37; the 37th is outside `swing/*.py` -- not located, the census used `-w` on `.py` only); then `grep` for the TRADE reads (`(t|trade|tr|row|existing).candidate_id`, `trades.candidate_id`, `ON t.candidate_id`) and a READ of each matched site. Files whose `candidate_id` is ANOTHER table's column are listed as such.

| Consumer | Reads `trades.candidate_id`? | Decision-night vs fill-night anchor |
|---|---|---|
| `trades/entry.py` (`:2016`, `:2167-2188`) | WRITER | a supplied id is persisted (non-latched); latched path overrides; T2 supplies the chosen night |
| `data/repos/trades.py` (`:428/491/554` insert params; `update_cohort_provenance` `:1144`) | WRITER | unchanged code; kind 2 writes through `update_cohort_provenance` |
| `trades/cohort_provenance_correction.py` | reads (gate, envelopes, reader) | kind 1 unchanged; kind 2 MOVES it to the fire |
| `web/view_models/journal.py:359,505` | reads -> `candidates.bucket` (`aplus_bucket` column) | changes only if the nights' buckets differ; T2 restricts offered nights to the origin night's bucket `[F6]`, kind 2 is watch->watch: reading UNCHANGED |
| `metrics/pattern_outcomes.py:127` | `LEFT JOIN trades t ON t.candidate_id = c.id` under `PROVABLE_APLUS_PE_PREDICATE` | aplus PEs only; watch-origin trades never join either way: UNCHANGED for kind 2 and for watch nights. An aplus non-latched trade choosing an earlier aplus night would attribute to that night's PE -- the night the operator acted on (more correct); disclosed |
| `web/view_models/patterns/review_form.py:438` | `LEFT JOIN trades t ON t.candidate_id = c.id` (per-PE hit-stop counts) | a trade's outcome attributes to the DECISION night's PE row instead of the fill night's -- CHANGES, toward the night the operator acted on; disclosed to RD |
| `trades/reconciliation_auto_correct.py:232` | lists `("trades","candidate_id")` as a coupled cohort surface the corrector refuses | unchanged (refusal is value-agnostic) |
| `latches/service.py:229` | prose (nullable FK reasoning) | none |
| `latches/identity.py:12` | prose | none |
| `cli.py:3711` | docstring | none |
| `data/models.py` (`Trade`, provenance envelopes) | type + envelope keys | T1.5 |
| `trades/latched_origin.py`, `web/view_models/latches.py`, `web/routes/latches.py`, `latches/service.py`, `latches/reader.py`, `latches/order_intent.py`, `latches/models.py`, `latches/classification.py`, `latches/orders.py`, `latches/constants.py`, `cli_latches.py`, `data/repos/latch_view_events.py`, `data/repos/latch_order_intents.py`, `data/repos/latch_order_mandate_links.py`, `trades/entry_intent_assignment.py:366`, `trades/frozen_value_evidence.py` | the LATCH tables' `candidate_id` (the fire), not the trade's | UNTOUCHED (latch path; brief) |
| `data/repos/candidates.py`, `data/repos/candidates_immutability_epoch.py`, `data/db.py`, `journal/analyze.py:176`, `metrics/capital.py`, `patterns/{foundation,template_matching,active_learning}.py`, `web/routes/patterns.py`, `diagnostics/backfill_trades_sector_industry.py` | `candidate_criteria.candidate_id` / `candidates.id` / pattern-evaluation surrogates; `analyze.py` selects by ticker + entry date, NOT by the trade's id | none |
| `research/**` | no read of `trades.candidate_id` (grep over `research/`) | none |

No consumer needs a column: every trade-side reader reads the night through the backlink, so the brief's "no new column" stands with no exception argued.

---

## Accepted limitations (each with its reason; challenge invited)

1. The decision-night label at T2 is computed against the CURRENT registry, not the as-of registry of that night (the prefill's semantics today); the kind-2 correction uses the AS-OF registry. Reason: the form is a suggestion the operator confirms; the correction is evidence. The label-changed gate (T2.3) stops a GET/POST drift.
2. Kind 2 covers `pipeline_watch_manual` only (brief). `pipeline_watch_hyp_recs` trades take their label from the night's own hyp-rec button.
3. H4 relabels are unreachable through kind 2 (P4: H4 is `aplus`-only since D84); an aplus mis-stamp is kind-1-shaped and out of scope.
4. `last_fire` is a Python ranking recorded in the row and re-derived by the reader; SQL verifies the facts (bucket, no recommendation, applied values on the trade, no latch authority), never the ranking.
