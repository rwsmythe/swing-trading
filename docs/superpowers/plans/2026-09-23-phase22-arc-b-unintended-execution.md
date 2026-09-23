# 22-B — Demand A: `unintended_execution` (the third `entry_intent` value + its evidence-bearing assignment surface) — IMPLEMENTATION PLAN

**Status:** WRITTEN, review loop HELD (orchestrator instruction, 2026-09-23) pending three open forks (ledger R0.F-1..3). Each open fork is a **MARKED DROP-IN** below (`[FORK R0.F-n]`): the executing cell encodes the ruled branch and deletes the other; nothing else in the ladder moves.
**Ledger (arguments, rulings, census, review history):** `docs/superpowers/plans/2026-09-23-phase22-arc-b-unintended-execution.ledger.md` — R0.A (RD F1-F3), R0.B (CHARC scope + F4-F6), R0.C (census K1-K21, C.1-C.6, E1-E8), R0.D (CHARC N4), R0.E (RD N1/N2/N3/N5), R0.F (fresh-cell forks + E9-E15). **The brief of record is `docs/phase22-arc-b-commissioning-brief.md` @ `bd4314ea`**; where its §2 "assignment surface" bullet disagrees with R0.E, R0.E wins (R0.F-4).
**Base for executing:** `main` at or above `57187164` (22-A2 merged), with this plan merged. **Executing cell:** `implementer-opus-high` (schema migration on the journal of record). **Reviewer A:** `strong`, to convergence. **Reviewer B:** the orchestrator's, on the finished tree. **STOP LINE:** B clean by 2026-09-29 EOD HST or the witness waits for 10-21.

## Tripwires crossed (§3) — and only these

1. **Migration `0040`** (v39 → v40): a `trades` REBUILD carrying exactly ONE DDL edit (the `entry_intent` IN-list gains `'unintended_execution'`); the five existing `trades` dependants re-created VERBATIM; ONE new `trades` trigger `trg_trades_entry_intent_attested_terminal` (N4 layer 3, a D51 ADDITION); ONE new append-only table `entry_intent_attestations` with its triggers (D51 ADDITIONS); `[FORK R0.F-1]` possibly two or three `latch_view_events` belts (D51 ADDITIONS). Gate row `BackupGateSpec(39, "22b", …)`. ZERO D51 deletions.
2. **`swing/data` + `swing/trades` carve-out:** `swing/data/models.py` (enum widening, split constants, two error types, the attestation dataclass), `swing/data/db.py` (version + gate row), `swing/data/repos/trades.py` (`update_entry_intent` seam + N4 layer 1), `swing/trades/entry.py` (`EntryRequest` seam), `swing/trades/reconciliation_auto_correct.py` (N4 layer 2), `swing/trades/intent.py` (display split).
3. **`swing/metrics` cohort code** (N2 (a)): `swing/metrics/cohort_intent.py`, `swing/metrics/cohort.py`, and the four governed readers (`swing/journal/stats.py`, `swing/metrics/tier.py`, `swing/recommendations/hypothesis.py`, `swing/web/view_models/metrics/hypothesis_progress_card.py`) — no new tripwire, CHARC's §3 pass absorbs it.
4. **ONE new module:** `swing/trades/entry_intent_assignment.py` (F4). It ALSO owns the attestation table's SQL (no new `swing/data/repos/` module — that would be a second new module the tripwire did not grant).
Plus `swing/cli.py` (the `assign-intent` command; the seam at three existing commands), `swing/web/` (review form read-only, entry form seam, one CSS class, labels). **Nothing else.** OUT: see brief §2 OUT (22-C, 22-E, any UI for assignment, relabel paths, a death-then-fill primitive, D58, any second `trades` edit).

## Binding conventions for the executing cell

- TDD per task: failing test → SEE it fail the RIGHT way → minimal code → green → commit (`feat(…): Task N — …`). Compute every discriminator under BOTH the pre-fix and post-fix path.
- **One transaction per migration (gotcha #9)**; the migration runner owns BEGIN/COMMIT; `foreign_keys=OFF` at the runner, so `PRAGMA foreign_key_check` after RENAME is asserted by TEST.
- **Every trigger `WHEN` is `NOT COALESCE(<predicate>, 0)`** (a NULL `WHEN` fails open); **every table CHECK is NULL-closed** (a CHECK that evaluates NULL PASSES — each CHECK either is total over NOT NULL columns or is covered by the paired-tier CHECK; a per-CHECK NULL-mutation test proves it).
- **One rounding authority:** no numeric comparison crosses Python↔SQL in this arc; every compared value is TEXT (dates as `YYYY-MM-DD`, text snapshots as JSON strings) compared BYTEWISE.
- **Every migration commit regenerates the D51 manifest** (`python scripts/schema_manifest.py --write`, from THIS checkout) and the diff is READ: zero `-` lines.
- **Grep each enum member SEPARATELY** (`'standard'`, `'hypothesis_test_by_design'`, `'unintended_execution'`, `ENTRY_INTENTS`); a token grep is a LOWER bound — the manifest is established by READ, and the drift test is the only mirror that defends the set.
- **Version-number naming rule:** HEAD-tracking tests are `…_is_head`; the v39→v40 commit edits bodies only, never renames (a rename sweep never rides the version commit).
- **No test name carries an `a2_<digits>` token** (A2-08's roster regex walks all of `tests/`). New 22-B test ids are `b22_NN`.
- **ASCII** in every CLI/stdout string; the contract doc's non-ASCII bytes are read as BYTES (`encoding='utf-8'` or `rb`, one trailing `\r` stripped — autocrlf checkouts).
- Test fixtures derive from REAL row shapes (the live trade-20 / AMN / fill-41 bytes are quoted in ledger R0.C K5 and R0.F-2); a raw `conn.execute` INSERT plants pre-existing "bad" rows (the 18-B.1 technique) and `PRAGMA ignore_check_constraints=ON` plants schema-unreachable `provenance_corrections` rows (R0.C P2-a).
- Full fast suite (`python -m pytest -m "not slow" -q`) GREEN before Reviewer A and again at the end; `ruff check swing/` clean.

## Constants introduced (single-sourced; every other site imports them)

| name | home | value |
|---|---|---|
| `UNINTENDED_EXECUTION` | `swing/data/models.py` | `"unintended_execution"` |
| `ENTRY_INTENTS` | `swing/data/models.py` | widened to the three values (Task 3) — the SCHEMA enum |
| `ENTRY_INTENTS_ASSERTABLE` | `swing/data/models.py` | `frozenset({"standard","hypothesis_test_by_design"})` — what every GENERIC writer accepts (E10) |
| `EntryIntentSeamError(ValueError)` / `AttestedIntentError(ValueError)` | `swing/data/models.py` | the two typed refusals (E11) |
| `SEAM_MESSAGE` | `swing/data/models.py` | `"entry_intent 'unintended_execution' is evidence-bearing: it is written only by 'swing trade assign-intent', which records its evidence"` (ASCII) |
| `attested_message(attestation_id)` | `swing/data/models.py` | `"entry_intent is attested (entry_intent_attestations row {N}); no reversal surface exists -- a reversal is a NEW evidence class with its own record"` (N4's words, ASCII) |
| `CITABLE_FIELDS` / `DESCRIPTIVE_FIELDS` | `swing/trades/entry_intent_assignment.py` | `("notes","why_now","thesis","emotional_state_pre_trade")` / `("notes","why_now")` |
| `DEATH_RUNGS` | same | `("invalidation","criteria_lapsed","horizon","declined")` — the `clear_reason` tokens of `swing/latches/service.py:68-75` `_STATE_BY_CLEAR_REASON` (read by the plan cell; the non-death members are `fill` and `superseded`) |
| `INSTRUMENT_DEPLOYMENT_SESSION` | same | `"2026-08-03"`; docstring states the derivation (merge `d5d03bb9` COMMITTER date 2026-08-03 01:04 HST lower bound; w32 image 2026-08-03 17:30 HST at v33 with `latch_order_intents` present, 0 rows, upper bound — one calendar day, determined, not estimated) |
| `CONTRACT_EXCLUSION_CLAUSE` | `swing/metrics/cohort_intent.py` | `"It counts toward NO hypothesis cohort."` (verbatim sentence of clause (4)) |
| `CONTRACT_EXCLUDED_ENTRY_INTENTS` | same | `(UNINTENDED_EXECUTION,)` |
| `CLAUSE4_SHA256` | `0040` header text + a test constant | `5a78e547f64df25e0f891bd271c8d5e51bbd884866ca6d04c6c85b7803ef3886` |

---

## Task 0 — Preflight (no commit)

1. `git log -1` shows the base ≥ `57187164`; this plan and `docs/training-epoch-intent-contract.md` are present.
2. Re-ground every anchor this plan cites (line numbers drift): the eight seam surfaces (Task 2 table), `update_entry_intent` (`swing/data/repos/trades.py` ~`:970`), `_RESERVED_JOURNAL_FIELDS` (`reconciliation_auto_correct.py` ~`:200`), `find_accepted_latch_order` (`latched_origin.py` ~`:1181`), `mandate_alive_at` (~`:2400`), `broker_order_id_from_envelope` (~`:662`), the four readers (Task 8 table).
3. Capture the 22-A2 composition pin BEFORE any edit: a throwaway script computes `sha256(inspect.getsource(fn))` for every `CASES_22A2` implementing function (106 ids; the A2-08 discovery rule) and prints a dict literal; paste it into Task 12's test. Record the base SHA it was captured at in the test's docstring.
4. Run the fast suite on the untouched base; record the pass count. Any pre-existing red is reported, not fixed.

## Task 1 — The contract doc's pins (tests only; the doc is already committed by the plan cell)

**Files:** `tests/docs/test_training_epoch_intent_contract.py` (new).
- `test_clause4_line_occurs_exactly_once_b22_01` — read the doc as BYTES; lines split on `b"\n"`, one trailing `b"\r"` stripped; exactly ONE line starts with `b"> **(4)"`.
- `test_clause4_is_byte_identical_to_the_ratified_text_b22_02` — that line equals the single `> **(4)` line of `git show e5feec2a:docs/phase22-arc-b-rd-rulings-f1-f3.md` (via `subprocess.run([...], capture_output=True)` — BYTES, never `text=True`); skip-with-reason only if git is unavailable.
- `test_clause4_sha256_is_the_pinned_value_b22_03` — `sha256(line[2:])` == `CLAUSE4_SHA256` and `len(line[2:]) == 1024`.
- `test_clauses_1_to_3_are_verbatim_from_the_archive_b22_04` — the doc's clauses-(1)-(3) block-quote body equals `docs/research-director-context-archive.md` line 84 sliced from `(1) A+ fires` up to (not including) `**Epoch-integrity`, right-stripped (both read `encoding="utf-8"`).
- `test_ratification_is_quoted_b22_05` — the doc contains `"clause (4) is ratified."`.
Commit: `test(docs): Task 1 — pin the training-epoch intent contract (clause 4 bytes + hash, clauses 1-3 verbatim)`.

## Task 2 — The single-writer seam FIRST (behaviour-preserving for today's two values) — F5 × 8, E10, E11

**Why first:** once `ENTRY_INTENTS` widens (Task 3), every surface validating against it would ACCEPT the value. So every GENERIC writer is repointed to `ENTRY_INTENTS_ASSERTABLE` and given the typed refusal NOW; the widening then opens nothing.

| # | surface (census C.4) | change |
|---|---|---|
| 1 | `swing/cli.py` `trade entry --entry-intent` `click.Choice` (~`:602`) | choices = sorted `ENTRY_INTENTS_ASSERTABLE` (a literal list stays FORBIDDEN — import the constant); `unintended_execution` → click usage error naming `assign-intent` |
| 2 | `swing/cli.py` `trade review --entry-intent` (~`:1558`) | same |
| 3 | `swing/cli.py` `trade backfill-intent` free-text prompt (~`:1723-1778`) | a typed `unintended_execution` answer → `EntryIntentSeamError` caught → message echoed, row NOT written, loop continues |
| 4 | `swing/web/routes/trades.py` entry form early validation (~`:837`) | validate against `ENTRY_INTENTS_ASSERTABLE`; the value → the existing 4xx re-render with `SEAM_MESSAGE` |
| 5 | `swing/web/routes/trades.py` review form (~`:3545-3558`) | same, 4xx fragment |
| 6 | `swing/trades/entry.py` `EntryRequest.__post_init__` (~`:569`) | the value → `EntryIntentSeamError(SEAM_MESSAGE)`; other non-members keep today's message |
| 7 | `swing/data/repos/trades.py` `update_entry_intent` | the value → `EntryIntentSeamError`; validation against `ENTRY_INTENTS_ASSERTABLE` (N4's terminality check is Task 7) |
| 8 | `swing/trades/reconciliation_auto_correct.py` `_RESERVED_JOURNAL_FIELDS` | add `("trades","entry_intent")` → owning-surface text `"swing trade assign-intent (unintended_execution) / swing trade review --entry-intent (other values)"` (E14: unconditional, as ruled) |

Also: `swing/trades/intent.py` — `ENTRY_INTENT_DISPLAY` stays the two-choice tuple (it feeds BOTH `<select>`s) and gains a sibling `ENTRY_INTENT_LABELS` covering the value set (label for the new value lands in Task 3 with the widening); the no-drift test now asserts `{v for v,_ in ENTRY_INTENT_DISPLAY} == ENTRY_INTENTS_ASSERTABLE`.

**Tests** (`tests/trades/test_22b_seam.py`, new; plus edits to the existing no-drift test):
- `test_each_generic_surface_refuses_with_the_seam_message_b22_10` — parametrized over the 8 surfaces, BY EXECUTION: CLI via `CliRunner` (1-3), TestClient POST (4-5, asserting 4xx + the message in the fragment), `EntryRequest(...)` (6), `update_entry_intent(conn, …)` (7), the corrector's field-level entry with `("trades","entry_intent")` → `ReservedJournalFieldError` (8). Pre-fix the message is the generic "must be one of"/not reserved → RED.
- `test_seam_surfaces_import_the_assertable_constant_b22_11` — static: each of files 1-7 references `ENTRY_INTENTS_ASSERTABLE` (or `EntryIntentSeamError`) and none contains a two-element literal of the intent tokens (closure by READ: the test enumerates the files; a new `ENTRY_INTENTS` membership check anywhere in `swing/` outside `models.py`, `Trade.__post_init__`, the drift test, and the assignment module FAILS — the static closure walk over `ast` `Name`/`Attribute` references to `ENTRY_INTENTS`).
- `test_today_values_still_accepted_everywhere_b22_12` — `standard` and `hypothesis_test_by_design` still pass on all 8 surfaces (the refactor is behaviour-preserving).
Commit: `feat(trades): Task 2 — single-writer seam: eight generic surfaces refuse unintended_execution (typed, names assign-intent)`.

## Task 3 — Migration `0040` part 1: the `trades` rebuild, the N4 trigger, the gate, the widening (#11 in ONE commit)

**Files:** `swing/data/migrations/0040_entry_intent_unintended_execution.sql` (new), `swing/data/db.py`, `swing/data/models.py`, `swing/trades/intent.py`, `tests/data/schema_manifest_head.tsv` (regenerated), `tests/data/test_migration_0040_entry_intent.py` (new), `tests/data/test_backup_gate_table.py` (`POST_BASE_ROSTER` constant only), the version-mirror test bodies (39→40), `[FORK R0.F-3]` the three 22-A2 test bodies.

**0040 header (comment block, before `BEGIN`):** REVERSIBILITY HEADER naming: (i) the ONE edit (the `entry_intent` IN-list: `('standard','hypothesis_test_by_design')` → `('standard','hypothesis_test_by_design','unintended_execution')`); (ii) every object CREATED (the new trigger, the attestation table + its triggers, `[FORK R0.F-1]` belts) with its `DROP` statement; (iii) the five dependants re-created verbatim with their SOURCE (`0014:230` partial UNIQUE `ux_trades_one_open_per_ticker`; `0021:39,41` the two indexes; `0038:113,117` `ux_trades_attempt_id` + `trg_trades_attempt_id_immutable`); (iv) the gate `BackupGateSpec(39, "22b", …)`; (v) **the F1 pin:** `-- clause (4) sha256: 5a78e547f64df25e0f891bd271c8d5e51bbd884866ca6d04c6c85b7803ef3886 (docs/training-epoch-intent-contract.md; derived by test, never read at runtime)`; (vi) "`trades` has NO AUTOINCREMENT (`id INTEGER PRIMARY KEY`) — no sequence carry" (NOT 0039's sequence step).

**0040 body, in order (one transaction, the runner's):**
1. `CREATE TABLE trades_new (...)` = the STORED v39 `trades` DDL text with the ONE edit and the table name — the stored DDL begins `CREATE TABLE "trades" (` (quoted; the 0014 RENAME product, R0.C K8).
2. `INSERT INTO trades_new (<58 columns, explicit, in PRAGMA order>) SELECT <same 58> FROM trades;`
3. `DROP TABLE trades;` (drops the five dependants) → `ALTER TABLE trades_new RENAME TO trades;`
4. Re-create the five dependants VERBATIM from their sources (token-identical — D51 hashes under whitespace collapse + line-comment drop, R0.C K11).
5. `CREATE TRIGGER trg_trades_entry_intent_attested_terminal BEFORE UPDATE OF entry_intent ON trades FOR EACH ROW WHEN COALESCE(OLD.entry_intent,'') = 'unintended_execution' AND NEW.entry_intent IS NOT OLD.entry_intent BEGIN SELECT RAISE(ABORT, '<attested message, generic form without row id>'); END;` (both WHEN operands are non-NULL by construction — no NULL-`WHEN` hazard; a test pins it).
6. `[FORK R0.F-1]` — **branch (a)/(a'):** `trg_lve_actionable_ever_viewed_monotonic` (`BEFORE UPDATE OF actionable_ever_viewed ON latch_view_events WHEN NOT COALESCE(NEW.actionable_ever_viewed >= OLD.actionable_ever_viewed, 0)` → ABORT), `trg_lve_no_delete` (`BEFORE DELETE` → ABORT), and under (a') `trg_lve_no_replace` (`BEFORE INSERT … WHEN EXISTS (SELECT 1 FROM latch_view_events WHERE candidate_id = NEW.candidate_id AND view_session_date = NEW.view_session_date AND surface = NEW.surface)` → ABORT; the 0037 `trg_loml_no_replace` shape). **Branch (b):** nothing here; the AL text lands in Task 5's module docstring and the ledger.
7. (Task 4 appends the attestation table here.)
8. `UPDATE schema_version SET version = 40;` per the runner's convention (re-ground against 0039's tail).

**Python (same commit):** `ENTRY_INTENTS` gains the value; `Trade.__post_init__` accepts it (widened — the READ path must hydrate an attested row); `ENTRY_INTENT_LABELS[UNINTENDED_EXECUTION] = "Unintended execution"`; `entry_intent_label` reads `ENTRY_INTENT_LABELS`; `EXPECTED_SCHEMA_VERSION = 40`; `PHASE22_ARC_B_PRE_MIGRATION_EXPECTED_TABLES` (the v39 table set, measured by `sqlite_master` on a fresh v39 DB, not typed) + `_phase22_arc_b_backup_gate` + the `BackupGateSpec(39, "22b", PHASE22_ARC_B_PRE_MIGRATION_EXPECTED_TABLES, "_phase22_arc_b_backup_gate", "pre-22-B")` row (copy the 22a2 row's shape; gate clause `pre_version == 39 AND target >= 40`).

**`[FORK R0.F-3]` in this commit** (they go red the moment the version moves): **branch (a)** — A2-18 migrates v38 → 39 explicitly (use the module's existing migrate-to helper or add a `_migrate_to(c, 39)` beside `_migrate_to_head`); A2-19 renamed `test_a2_19_the_committed_fixture_matches_head`, the `"# schema_version 39\n"` literal replaced by the `EXPECTED_SCHEMA_VERSION`-derived header; A2-22 asserts `POST_BASE_ROSTER[0]` is the 22a2 row and the live table equals `ROSTER + POST_BASE_ROSTER`. **Branch (b)** — the three bodies bumped to v40 facts (A2-18's expected diff = 0039's three + 0040's objects; A2-19 reads `40`; A2-22's tuple gains the 22b row). Either way `POST_BASE_ROSTER` gains `(39, "22b", "_phase22_arc_b_backup_gate", "PHASE22_ARC_B_PRE_MIGRATION_EXPECTED_TABLES", "pre-22-B")`, and Task 12's pin lists exactly these three ids as named exemptions.

**Version-mirror sweep:** grep `EXPECTED_SCHEMA_VERSION\s*==\s*39|== 39\b` over `tests/` (44 lines / 32 files at `902ac83d` — a LOWER bound); READ each hit; edit only version assertions, bodies only.

**Tests** (`tests/data/test_migration_0040_entry_intent.py`):
- `test_one_edit_of_the_v39_stored_ddl_equals_the_v40_stored_ddl_b22_20` — build v39 (`_migrate(tmp, 39)`), read stored `trades` SQL, apply the ONE textual edit (the anchor occurs EXACTLY once — asserted), migrate to head, stored SQL equals the edited text BYTEWISE.
- `test_58_columns_in_order_and_every_row_tuple_identical_b22_21` — a v39 DB seeded with ≥3 real-shape trades (incl. trade-20's bytes: the two-space `notes`) + fills + a `daily_management_records`/`trade_events`/`reconciliation_discrepancies`/`provenance_corrections` child each; after migrate: `PRAGMA table_info` names/types/order identical; `SELECT *` tuples identical; the five child tables' row counts unchanged; `PRAGMA foreign_key_check` == `[]`.
- `test_the_partial_unique_still_refuses_a_second_open_trade_b22_22` (D30 discriminator) and `test_attempt_id_is_still_write_once_b22_23`.
- `test_the_five_dependants_are_verbatim_from_their_sources_b22_24` — stored SQL of each == `create_statement_in(<source migration>, name)` (the 0039 test helper shape).
- `test_the_manifest_diff_is_one_changed_table_plus_additions_zero_deletions_b22_25` — `schema_manifest.compare(v39, v40)`: `changed == {("table","trades")}` (the header line is not an object); `missing == ∅`; `unexpected ==` exactly {the N4 trigger, the attestation table + its indexes/triggers (Task 4 extends this set), `[FORK R0.F-1]` belts}.
- `test_head_fixture_is_regenerated_b22_26` — rides the existing `test_head_manifest_matches_fixture` (no new assertion; listed so the roster names it).
- `test_run_twice_is_a_noop_b22_27`; `test_the_22b_gate_fires_once_from_39_and_the_cli_echoes_one_image_b22_28` (the A2-21 shape: ONE image in `backups_dir`, none in the DB's parent — the D32 production shape).
- `test_header_carries_the_clause4_hash_and_it_matches_the_doc_b22_29` — parse `-- clause (4) sha256: <hex>` from 0040's header; equals `CLAUSE4_SHA256`; equals the hash derived INDEPENDENTLY from the doc (Task 1's reader, called fresh).
- `test_migration_never_reads_the_docs_tree_b22_30` — 0040's text contains no `docs/` path outside `--` comments (the runtime never opens the doc; the runner executes SQL only).
- `test_sql_check_equals_python_enum_b22_31` — **the drift test (the mandatory mirror, K12: absent today):** parse the IN-list out of the STORED head `trades` DDL; `set(...) == ENTRY_INTENTS`; and `ENTRY_INTENTS_ASSERTABLE < ENTRY_INTENTS` with the difference exactly `{UNINTENDED_EXECUTION}`.
- `test_the_model_rejects_a_fourth_value_b22_32`; `test_each_member_greps_separately_b22_33` — for each of the three tokens, the set of `swing/` files containing it (READ-classified list committed in the test as widened / tight-by-design / value-agnostic with one-line reasons) equals the grep result — a new site FAILS until classified.
- N4 layer 3 ALONE on plain `sqlite3` (no service): `test_raw_update_of_an_attested_row_aborts_b22_34` (`'unintended_execution'` → `'standard'` and → NULL: both ABORT); `test_same_value_update_passes_b22_35`; `test_null_to_value_passes_b22_36`; `test_the_trigger_when_clause_is_never_null_b22_37` (OLD NULL / NEW NULL combos evaluated).
- `[FORK R0.F-1 (a)/(a')]` `test_lve_raw_downgrade_aborts_b22_38`, `test_lve_writer_merge_still_passes_b22_39`, `test_lve_same_value_passes_b22_40`, `test_lve_raw_delete_aborts_b22_41`, (a') `test_lve_raw_replace_aborts_b22_42`, `test_lve_first_insert_race_still_merges_b22_43` (two connections, both `record_view` first-insert; final row `view_count == 2`, `actionable_ever_viewed == max`). Under (b): these ids are unused and `test_leg1_al_is_declared_b22_38` asserts the AL text in the module docstring.
Commit (ONE): `feat(data): Task 3 — migration 0040 part 1: trades rebuild (one edit), N4 terminal trigger, 22b gate, v40, enum widened with the drift test`.

## Task 4 — Migration `0040` part 2: `entry_intent_attestations` (its SCHEMA IS THE EVIDENCE RULE)

**Files:** `0040` (append before the version line), `swing/data/models.py` (`EntryIntentAttestation` frozen dataclass + `__post_init__` mirroring EVERY CHECK), manifest regenerated, `tests/data/test_migration_0040_attestations.py` (new).

**Table (columns; CHECKs NULL-closed):**
- `attestation_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `trade_id INTEGER NOT NULL UNIQUE REFERENCES trades(id) ON DELETE RESTRICT`
- `assigned_value TEXT NOT NULL CHECK (assigned_value = 'unintended_execution')`
- `admission_tier TEXT NOT NULL CHECK (admission_tier IN ('structural','contemporaneous_record'))`
- `trade_entry_date TEXT NOT NULL` (date round-trip CHECK, the 0032 idiom `length(x)=10 AND date(x)=x`)
- `entry_fill_id INTEGER NOT NULL REFERENCES fills(fill_id) ON DELETE RESTRICT`
- `entry_broker_order_id TEXT` (NULL iff the entry fill's envelope carries none — E9)
- **tier 2:** `placement_session TEXT`, `placement_session_source TEXT CHECK (placement_session_source IN ('schwab_envelope','entry_date_fallback'))`, `admitted_leg TEXT CHECK (admitted_leg IN ('telemetry','deployment'))`, `leg_evidence_json TEXT` (leg 1: `{"telemetry_rows":[{"view_event_id":N,"actionable_ever_viewed":0,"first_viewed_ts":"…","view_session_date":"…"}…]}`; leg 2: `{"deployment_session":"2026-08-03","placement_session":"…"}` — the replay input, N1)
- **structural (N5 (b): LINK ONLY; no `cited_latch_intent_id` column):** `cited_latch_link_id INTEGER REFERENCES latch_order_mandate_links(link_id) ON DELETE RESTRICT`, `cited_latch_terminal_rung TEXT CHECK (cited_latch_terminal_rung IN ('invalidation','criteria_lapsed','horizon','declined'))`, `cited_latch_terminal_session TEXT`, `cited_latch_probe_json TEXT` (`mandate_alive_at`'s `probe_evidence`, the `provenance_corrections.cited_latch_probe_json` precedent)
- **evidence:** `cited_fields_json TEXT NOT NULL`, `cited_text_snapshot_json TEXT NOT NULL`, `audit_trail_checked_at TEXT NOT NULL`, `corrections_touching_cited_fields INTEGER NOT NULL CHECK (corrections_touching_cited_fields = 0)`, `outcome_known_at TEXT` (NULL iff the trade had no non-entry fill at assignment), `reason TEXT NOT NULL CHECK (length(trim(reason)) > 0)`, `applied_at TEXT NOT NULL`, `applied_by TEXT NOT NULL`
- **paired-tier CHECK:** `(admission_tier = 'structural' AND cited_latch_link_id IS NOT NULL AND cited_latch_terminal_rung IS NOT NULL AND cited_latch_terminal_session IS NOT NULL AND cited_latch_probe_json IS NOT NULL AND placement_session IS NULL AND placement_session_source IS NULL AND admitted_leg IS NULL AND leg_evidence_json IS NULL) OR (admission_tier = 'contemporaneous_record' AND cited_latch_link_id IS NULL AND cited_latch_terminal_rung IS NULL AND cited_latch_terminal_session IS NULL AND cited_latch_probe_json IS NULL AND placement_session IS NOT NULL AND placement_session_source IS NOT NULL AND admitted_leg IS NOT NULL AND leg_evidence_json IS NOT NULL)` — total (every operand non-NULL by construction).
- **binds (each NULL-closed by the paired CHECK or `COALESCE(…,0)`):** `COALESCE(cited_latch_terminal_session < trade_entry_date, 1)` (death STRICTLY before the fill session — NULL only on tier 2, where the paired CHECK forces NULL); `COALESCE(admitted_leg <> 'deployment' OR placement_session < '2026-08-03', 1)`; `outcome_known_at IS NULL OR trade_entry_date < substr(outcome_known_at,1,10)`; `json_valid(cited_fields_json) AND json_type(cited_fields_json) = 'array' AND json_array_length(cited_fields_json) >= 1`; `json_valid(cited_text_snapshot_json) AND json_type(cited_text_snapshot_json) = 'object'`; `json_valid` on the three optional JSON columns when non-NULL.

**Triggers (BEFORE INSERT unless named; every `WHEN NOT COALESCE(…,0)`; each is the SQL twin of a Task-5 service check — Task 11 closure-checks it):**
- `trg_eia_trade_binding` — the trade exists; `NEW.trade_entry_date = trades.entry_date`; `trades.entry_intent IS NULL` at insert (no relabel; the service inserts BEFORE it updates `trades`); `NEW.entry_fill_id` is a fill of `NEW.trade_id` with `action = 'entry'`; `NEW.entry_broker_order_id IS json_extract(<that fill>.schwab_source_value_json,'$.schwab_order_id')` (re-ground the key against `broker_order_id_from_envelope`).
- `trg_eia_cited_fields` — every element of `cited_fields_json` ∈ `CITABLE_FIELDS` (`NOT EXISTS (SELECT 1 FROM json_each(NEW.cited_fields_json) WHERE value NOT IN (…))`); no duplicates; at least one of `notes`/`why_now` (F2 S4); the snapshot's key set == the cited set and each snapshot value `IS` the live `trades` column (TEXT vs TEXT, bytewise — `json_extract` returns the JSON string's text).
- `trg_eia_audit_trail` (P2 twin, F2 S2 + P2-b) — `NOT EXISTS` in `reconciliation_corrections` with `affected_table = 'trades' AND affected_row_id = NEW.trade_id` AND (`field_name` ∈ cited OR any key of `json_each(pre_correction_value_json)` / `json_each(applied_value_json)` ∈ cited ∪ `'trades.'||cited`); AND `NOT EXISTS` in `provenance_corrections` with `trade_id = NEW.trade_id` AND any element of `json_each(corrected_fields_json)` ∈ `'trades.'||cited` (P2-a: schema-vacuous today, required by S2).
- `trg_eia_outcome` (P3 twin) — `NEW.outcome_known_at IS (SELECT MIN(fill_datetime) FROM fills WHERE trade_id = NEW.trade_id AND action IN ('trim','exit','stop'))` (E2: the EARLIEST non-entry fill; NULL iff none).
- `trg_eia_tier2` (P1 twin; fires only when `NEW.admission_tier = 'contemporaneous_record'`) — `NOT EXISTS` a link with `broker_order_id = NEW.entry_broker_order_id`; `NOT EXISTS` a `latch_order_intents` row with `actual_broker_order_id = NEW.entry_broker_order_id`; when `entry_broker_order_id IS NULL`, `NOT EXISTS` a link or order-naming intent for the trade's ticker with `detection_date <= NEW.trade_entry_date` (E9); `placement_session` equals the envelope's `entry_date` when `placement_session_source = 'schwab_envelope'`, else `trade_entry_date`; **`[FORK R0.F-2]` the leg predicate** — let W = the trade's ticker's `latch_view_events` rows in the WINDOW and S = the SPEAKING subset: *(a)* W = `date(first_viewed_ts) <= placement_session`, S = W rows with `actionable_ever_viewed = 1` OR `date(first_viewed_ts) > '2026-08-03'`; *(b)* W = `view_session_date <= placement_session`, S = W. Then: `NOT EXISTS` a row of W with `actionable_ever_viewed = 1`; `admitted_leg = 'telemetry'` ⇒ `EXISTS` S AND every S row's id is in `leg_evidence_json` with its read value; `admitted_leg = 'deployment'` ⇒ `NOT EXISTS` S AND `placement_session < '2026-08-03'`.
- `trg_eia_structural` (fires when `'structural'`) — the cited link exists and `broker_order_id = NEW.entry_broker_order_id` (NOT NULL); the death-before-fill DERIVATION is service-only (`mandate_alive_at`, Python); the trigger binds the recorded rung/session shape (paired + bind CHECKs). Declared in Task 11's closure test as `service_only` with this reason.
- Append-only TRIPLE: `trg_eia_no_update` (`BEFORE UPDATE` → ABORT), `trg_eia_no_delete` (`BEFORE DELETE` → ABORT), `trg_eia_no_replace` (conflict-scoped `BEFORE INSERT … WHEN EXISTS (SELECT 1 FROM entry_intent_attestations WHERE trade_id = NEW.trade_id OR attestation_id = NEW.attestation_id)` → ABORT; the service's insert has no `ON CONFLICT`, so the third-facet hazard does not arise — a test pins it).

**Tests** (`tests/data/test_migration_0040_attestations.py`; each a ONE-mutation of a valid real-shape row planted RAW on plain `sqlite3`, trigger tested ALONE):
- `test_a_valid_tier2_row_inserts_b22_50` / `test_a_valid_structural_row_inserts_b22_51` (baselines).
- One test per CHECK with its NULL mutation (`…_null_does_not_pass_b22_52..`) — `admission_tier` NULL, a tier-2 row with `placement_session` NULL, a structural row with `cited_latch_terminal_session` NULL: each REFUSED.
- `test_terminal_session_equal_to_entry_refuses_b22_53` / `…_day_before_admits_b22_54` (inequality direction pinned).
- `test_deployment_leg_boundary_2026_08_03_refuses_b22_55` / `…_2026_08_02_admits_b22_56`.
- `test_cited_field_outside_allowlist_refuses_b22_57` (`pre_trade_locked_at`); `test_tag_only_citation_refuses_b22_58` (`["emotional_state_pre_trade"]`); `test_snapshot_not_equal_to_live_text_refuses_b22_59` (one byte: the two-space `notes` with one space).
- `test_a_reconciliation_correction_on_a_cited_field_refuses_b22_60` (planted `field_name = 'notes'`) and `test_a_multi_field_correction_carrying_notes_as_a_non_first_key_refuses_b22_61` (P2-b) and `test_a_provenance_correction_naming_trades_notes_refuses_b22_62` (planted under `ignore_check_constraints` from `tests/trades/_cohort_provenance_fixtures.py`, P2-a) — an implementation checking one table FAILS 60 or 62.
- `test_outcome_not_the_earliest_non_entry_fill_refuses_b22_63` (a `stop` then `exit`: recording the `exit` date refuses — E2).
- `test_tier2_with_a_link_for_the_order_refuses_b22_64`; `test_tier2_with_an_intent_naming_the_order_refuses_b22_65`; `test_no_order_id_and_a_ticker_link_refuses_b22_66` (E9).
- `[FORK R0.F-2]` leg twins: `test_leg1_row_with_actionable_1_refuses_b22_67`; `test_telemetry_leg_without_a_speaking_row_refuses_b22_68`; `test_deployment_leg_with_a_speaking_row_refuses_b22_69`; *(a) only:* `test_a_pre_deployment_zero_row_does_not_speak_b22_70`; *(b) only:* `test_a_view_session_after_placement_is_outside_the_window_b22_70`.
- `test_relabel_refused_when_trades_entry_intent_is_set_b22_71`; `test_update_delete_replace_abort_b22_72..74`.
- `test_model_post_init_mirrors_every_check_b22_75` — for each CHECK above a Python mutation raises `ValueError` (the #11 triple: CHECK + constant + `__post_init__`).
Commit: `feat(data): Task 4 — migration 0040 part 2: entry_intent_attestations (append-only triple, evidence triggers)`.

## Task 5 — The service `swing/trades/entry_intent_assignment.py` (F4)

**Shape (F4 conditions):** `preflight(conn, cfg, *, trade_id, cite, reason, now) -> AssignmentVerdict` runs OUTSIDE any transaction (reads only); `assign(conn, cfg, *, trade_id, cite, reason, applied_by, dry_run) -> AssignmentResult` REJECTS a caller-held transaction (`conn.in_transaction` → `RuntimeError`), re-runs `preflight` INSIDE `BEGIN IMMEDIATE`, then INSERTs the attestation row THEN `UPDATE trades SET entry_intent = 'unintended_execution' WHERE id = ? AND entry_intent IS NULL` (rowcount must be 1), COMMIT; any exception → ROLLBACK → re-raise. Both rows or neither. The module holds the table's SQL (insert + `get_attestation(conn, trade_id)`), no second module.

**`preflight`, in order; the FIRST failing step returns a typed refusal `(code, message)` — each message names its recovery, ASCII:**
1. Trade exists; not voided (`voided_trade_ids`); `entry_intent IS NULL` → else `already_set` ("no relabel path; a non-empty relabel is a new evidence class").
2. `cite` ⊆ `CITABLE_FIELDS`, non-empty, no duplicates → else `not_citable` (names the field); ∩ `DESCRIPTIVE_FIELDS` non-empty → else `no_descriptive_field` (F2 S4). Each cited field's live text non-NULL and non-blank → else `empty_cited_field`.
3. **P2** over BOTH audit tables, the Task-4 predicate in Python (field_name OR envelope keys; `provenance_corrections.corrected_fields_json`) → else `cited_field_corrected` (names field + correction id). Records `audit_trail_checked_at = now` and the count (must be 0).
4. **P3:** `outcome_known_at` = earliest non-entry fill `fill_datetime` or `None` (open trade — F2 edge (i): ADMISSIBLE; written once; the row carries NO P&L/MFE/MAE).
5. **Tier detection (DETECTED, never chosen):** the entry fill (the `action='entry'` fill; if >1, the earliest — re-ground against the resolver's "authoritative entry fill" helper and reuse it); `order_id = broker_order_id_from_envelope(fill.schwab_source_value_json)`.
   - `order_id` and `find_accepted_latch_order(conn, broker_order_id=order_id)` returns ≥1 link → **structural**: `mandate_alive_at(conn, cfg, order=links[0], fill_session=date.fromisoformat(entry_date), exclude_trade_ids=frozenset({trade_id}))` (NO second comparison — gotcha #31). Admit iff the result's `clear_reason` ∈ `DEATH_RUNGS` and `clear_session < entry_date`; `clear_reason` `fill`/`superseded`/None (live) → `mandate_fill` ("a mandate fill is `standard` under clause (1)"; names rung + both dates); death on/after the entry session → `death_not_before_fill` (names rung + both dates); a `_probe_refusal`/`recognised_but_underivable` → `structural_unprovable` (names the probe's decline reason). >1 link → `ambiguous_links` refusal.
   - `order_id` and NO link but a `latch_order_intents` row with `actual_broker_order_id = order_id` → `unlinked_intent` REFUSE (N5 (b): "a latch intent without an accepted-order link cannot tie this fill to a mandate; tier 2 cannot apply because the instrument recorded it; the recovery is a link backfilled under 22-A's rules").
   - no `order_id` → E9 fail-closed check; then tier 2 with `placement_session = entry_date`, source `entry_date_fallback`.
   - otherwise → **tier 2 (`contemporaneous_record`)**: `placement_session` = envelope `entry_date` (source `schwab_envelope`) else `entry_date`. **`[FORK R0.F-2]`** compute W and S (the Task-4 definitions, same branch) over `latch_view_events WHERE ticker = trade.ticker`: any W row with `actionable_ever_viewed = 1` → `instrument_offered` REFUSE ("the instrument offered the order and did not fire; this is not an unintended execution the record can prove"); S non-empty → ADMIT `telemetry` (evidence = the S rows); S empty and `placement_session < INSTRUMENT_DEPLOYMENT_SESSION` → ADMIT `deployment`; S empty and placement on/after it → `instrument_existed` REFUSE; placement underivable → `unprovable` REFUSE naming the missing fact (leg 3).
6. Snapshot: `{field: live_text}` for the cited fields, `json.dumps(…, ensure_ascii=False, sort_keys=True)`.

**`drift_report(conn, trade_id) -> list[str]` (E6, pure read):** names (i) a cited field whose live text differs from the snapshot; (ii) a `trade_entry_date` differing from live `entry_date`; (iii) `trades.entry_intent = 'unintended_execution'` with NO attestation row (the value written outside the seam — raw SQL is not schema-refused; this reader is its detector); (iv) `[FORK R0.F-2 / R0.F-1 (b)]` a leg-1 snapshot row whose live `actionable_ever_viewed` now differs.

**Tests** (`tests/trades/test_22b_assignment_service.py`; real-shape fixtures: trade 20's row bytes, fill 41's envelope `{"entry_date": "2026-08-01", …, "schwab_order_id": "1007427919619", …}`, fill 44 `stop` `2026-08-11T16:00:00`, the AMN telemetry row 5):
- `test_trade20_shape_admits_contemporaneous_record_b22_80` — tier `contemporaneous_record`, `admitted_leg` = `deployment` under both R0.F-2 branches (R0.F-2 facts), `placement_session = '2026-08-01'`, `outcome_known_at = '2026-08-11T16:00:00'`, snapshot byte-for-byte (two-space `notes`), `trades.entry_intent` set.
- `test_both_rows_or_neither_b22_81` — monkeypatch the `trades` UPDATE to raise after the INSERT: fresh connection sees NO attestation row and `entry_intent` NULL.
- `test_caller_held_transaction_is_rejected_b22_82`; `test_dry_run_writes_nothing_and_prints_the_predicates_b22_83` (fresh-connection read after).
- N1 discriminators (R0.E, one mutation each, real row shape): `test_amn_row_flipped_to_actionable_refuses_naming_the_offer_b22_84`; `test_no_telemetry_placement_0801_admits_on_deployment_b22_85`; `test_no_telemetry_placement_0803_refuses_b22_86`; `test_no_telemetry_placement_0802_admits_boundary_twin_b22_87`; `test_no_envelope_entry_date_0803_refuses_b22_88`; `test_oii_shape_routes_structural_not_tier2_b22_89` (actionable 1 + a validity row naming the order + a link → structural path, never tier 2).
- `[FORK R0.F-2 (a)]` `test_a_post_deployment_zero_row_admits_on_telemetry_b22_90` (a row first viewed 08-05, ever 0, placement 08-06 → `telemetry`). `[(b)]` `test_a_windowed_zero_row_admits_on_telemetry_b22_90` (view_session 08-05 ≤ placement 08-06).
- F3 structural, the AMN geometry (fire 08-03, `skip` + close 30.80 below invalidation 30.85 on 08-07, fill 08-07 @ 36.43; a synthetic link for that mandate): `test_invalidation_terminal_0806_fill_0807_admits_structural_b22_91`; `test_terminal_0807_same_session_refuses_b22_92`; `test_live_latch_refuses_as_mandate_fill_b22_93`; `test_terminal_fill_or_superseded_refuses_b22_94` (parametrized). These drive the REAL `mandate_alive_at` over a seeded derivation (reuse the 22-A task-9 fixture builders; do not stub the probe).
- N5: `test_unlinked_intent_naming_the_order_refuses_typed_b22_95`.
- F2: `test_open_trade_admits_with_outcome_null_b22_96` and `test_a_later_exit_does_not_backfill_b22_97` (row bytes identical after an exit fill lands); `test_pre_trade_locked_at_not_citable_b22_98`; `test_emotional_state_alone_refuses_b22_99`; `test_planted_reconciliation_correction_on_notes_refuses_b22_100`; `test_planted_provenance_correction_on_notes_refuses_b22_101`; `test_entry_intent_already_set_refuses_b22_102`; `test_drift_reader_names_a_changed_cited_field_b22_103`; `test_drift_reader_names_a_value_without_attestation_b22_104`.
Commit: `feat(trades): Task 5 — entry_intent_assignment service (tier detection, N1 legs, P2 both tables, P3, single transaction)`.

## Task 6 — CLI `swing trade assign-intent`

`@trade_group.command("assign-intent")`: `TRADE_ID`, `--value` (`click.Choice([UNINTENDED_EXECUTION])` — the ONLY writer that names it), `--cite` (comma list), `--reason` (required, non-blank), `--dry-run`, `--db` per the group's convention. Output (ASCII): tier, `admitted_leg` + evidence, the three predicates WITH their values (P1: placement vs deployment/telemetry rows; P2: `corrections 0/0 over reconciliation_corrections, provenance_corrections`; P3: outcome date or `open`), and on write the attestation id. Refusal → `ClickException(message)` (exit 1). Service `ValueError`s wrapped at the boundary.
**Tests** (`tests/cli/test_assign_intent_cli.py`): `test_dry_run_prints_predicates_and_writes_nothing_b22_110`; `test_write_prints_attestation_id_b22_111`; `test_refusal_exits_nonzero_with_the_typed_message_b22_112`; `test_stdout_is_ascii_b22_113` (subprocess, the cp1252 encode gotcha); `test_assign_intent_is_the_only_caller_of_assign_b22_114` — the AST caller walk over `swing/`: the only call site of `entry_intent_assignment.assign` is this command (F4: callers pinned).
Commit: `feat(cli): Task 6 — swing trade assign-intent (dry-run prints the three predicates with values)`.

## Task 7 — N4: the value is TERMINAL for every generic writer (layers 1-2 + the review form)

1. **Layer 1** `update_entry_intent`: read `entry_intent` for the row (inside the caller's `with conn:`); if it is `UNINTENDED_EXECUTION` and the new value differs → `AttestedIntentError(attested_message(<attestation_id read from the table, or '?' pre-v40>))`. Same value → no-op write passes.
2. `trade review --entry-intent`: the error → `ClickException` with the message. `backfill-intent`: the default query already skips non-NULL; under `--force` / `--trade-id`, an attested row is SKIPPED with the message echoed, never prompted.
3. **Layer 2** is Task 2's reservation (already landed) — this task adds its N4 test.
4. **Review form:** `review_form.html.j2` renders, for an attested trade, a read-only `<span>` with `entry_intent_label(...)` and NO `<select name="entry_intent">` (the field is absent from the POST, so the presence gate at `routes/trades.py` ~`:3553` preserves it); the VM gains `entry_intent_attested: bool` (review-form VM only — not a base-layout VM). A handcrafted POST carrying `entry_intent=""` for an attested trade → `AttestedIntentError` → 4xx fragment with the message; value preserved.
**Tests** (`tests/trades/test_22b_terminal.py`, `tests/web/test_routes/test_trade_review_attested.py`): `test_review_post_without_the_field_preserves_b22_120`; `test_review_post_with_empty_refuses_4xx_preserved_b22_121`; `test_review_form_renders_read_only_no_select_b22_122`; `test_cli_review_entry_intent_standard_refuses_b22_123`; `test_backfill_force_skips_attested_row_b22_124`; `test_corrector_on_entry_intent_raises_reserved_b22_125`; `test_update_entry_intent_same_value_passes_b22_126`; `test_layer1_alone_refuses_with_trigger_absent_b22_127` (a pre-trigger DB shape: DROP the trigger in the test DB; the service layer alone still refuses — so neither layer masks the other; layer 3 alone is b22_34).
Commit: `feat(trades): Task 7 — N4 terminality: update_entry_intent refuses a change from an attested value; review form read-only`.

## Task 8 — Cohort code: exclusion in CODE (N2 (a)) and per-cohort NAMING (N3 (a))

1. `cohort_intent.py`: `CONTRACT_EXCLUSION_CLAUSE`, `CONTRACT_EXCLUDED_ENTRY_INTENTS`; `cohort_excluded_entry_intents(name, *, registered_names=None) -> tuple[str, ...]` returns `CONTRACT_EXCLUDED_ENTRY_INTENTS` for EVERY name (clause (4) is program-wide: "NO hypothesis cohort"; an orphan label is not a hypothesis cohort, and excluding there is the fail-closed direction — declared); `trade_counts_toward_cohort` returns `False` when `entry_intent in CONTRACT_EXCLUDED_ENTRY_INTENTS`, BEFORE the criterion check (so H1 and H2-H5 agree). `cohort_intent_authority` UNCHANGED (H2-H5 still `epoch_contract` — the authority did not change, its text did). Module docstring: authority 2 re-points from the archive to `docs/training-epoch-intent-contract.md` and states clause (4)'s exclusion as a NAMED third grounding (docstring + the constant; no other semantic change).
2. `cohort.py` `list_trades_for_cohort` / `list_closed_trades_for_cohort`: new kwarg `exclude_entry_intents: Collection[str] = ()` → one `entry_intent IS NOT ?` clause per value (NULL-safe: NULL counts). Default EMPTY (E13): `metrics/process.py` and `count_per_cohort` stay unfiltered (observational; clause (4) routes the result to the process card's facet).
3. New helper `list_intent_excluded_for_cohort(conn, *, hypothesis_label, state_filter) -> list[int]` in `cohort.py`: label-matched (the same `label_matches_hypothesis_sql`), voided-excluded, `entry_intent IN CONTRACT_EXCLUDED_ENTRY_INTENTS` trade ids.
4. The FOUR governed readers each pass `exclude_entry_intents=cohort_excluded_entry_intents(name, …)` (SQL readers) or rely on `trade_counts_toward_cohort` (in-memory readers), AND populate a new sibling field `intent_excluded: tuple[tuple[int, str], ...] = ()` (E12) with `(trade_id, "unintended_execution")` for the cohort's label-matched excluded trades (closed + open where the reader counts open):

| reader | file (anchor) | result type |
|---|---|---|
| journal hypothesis progress | `swing/journal/stats.py` (~`:376-470`) | `HypothesisProgress` (~`:336`) |
| tier comparison | `swing/metrics/tier.py` (~`:700-752`) | `CohortStatistics` (~`:244`) |
| tripwire / `swing hypothesis list` | `swing/recommendations/hypothesis.py` `compute_tripwire_status` (~`:535-600`) | `TripwireStatus` (~`:202`) |
| hypothesis-progress card | `swing/web/view_models/metrics/hypothesis_progress_card.py` (~`:345`, `:441`) | its cohort VM (~`:145`) |

5. ONE renderer `intent_exclusion_lines(intent_excluded) -> tuple[str, ...]` (in `cohort_intent.py`; ASCII: `f"not counted: trade {tid} ({reason})"`), rendered BESIDE `tier2_cohort_lines(...)` at every site that renders those: `cli.py` (~`:4972`, `:5009`), `journal/stats.py` (~`:519`), `tier.py` (~`:252`), `hypothesis_progress_card.py` (~`:151`), and the dashboard's use at `web/view_models/dashboard.py` (~`:501`). `tier2_count_marker` is NOT fed intent exclusions.
6. Closure: `test_every_cohort_membership_reader_is_governed_or_reasoned_b22_130` — a STATIC walk over `swing/` for every call of `_label_matches_hypothesis`, `label_matches_hypothesis_sql`, `list_trades_for_cohort`, `list_closed_trades_for_cohort`, `count_per_cohort`; each call site's module is on the GOVERNED list (the four) or the REASONED-EXCLUSION list (`metrics/process.py` — observational facet; `metrics/cohort.py:count_per_cohort` — D29 observational tabs; `diagnostics/metrics_wiring_audit.py` — string mentions only; `metrics/label_match.py` — the matcher itself). A new site FAILS until classified.
**Tests** (`tests/metrics/test_22b_cohort_exclusion.py`):
- `test_contract_exclusion_clause_is_in_the_committed_doc_b22_131` — `CONTRACT_EXCLUSION_CLAUSE` is a substring of the doc's clause-(4) line (bytes read, Task-1 reader) — a doctrine edit dropping the sentence FAILS.
- `test_trade_counts_toward_cohort_false_for_every_cohort_b22_132` (H1, each registered H2-H5, an orphan name, with and without `registered_names`).
- `test_sql_and_memory_halves_agree_b22_133` — for a seeded DB with one trade per (intent ∈ {NULL, standard, by_design, unintended}) × (label ∈ {H1, H2}), the SQL reader set == the in-memory reader set per cohort.
- `test_h1_and_h2_labelled_unintended_trades_are_excluded_and_named_b22_134` — on all four readers + the `hypothesis list` CLI output: each synthetic trade is NOT counted and its line `not counted: trade N (unintended_execution)` appears under ITS cohort only.
- `test_null_intent_h2_trade_still_counts_b22_135` (N2's NULL twin).
- `test_an_else_branch_coercing_unknown_to_standard_fails_b22_136` — monkeypatch `trade_counts_toward_cohort` into the coercing variant; b22_134 goes red (the discriminator is proven by execution).
- `test_process_card_and_count_per_cohort_are_unchanged_b22_137` (observational surfaces still list the unintended trade under its label).
Commit: `feat(metrics): Task 8 — clause (4) exclusion in cohort code with per-cohort naming (four readers + hypothesis list)`.

## Task 9 — Display

- `swing/web/view_models/metrics/process_grade_trend.py` `_INTENT_CSS_CLASS` gains `"unintended_execution": "intent-unintended"`; `static/app.css` gains `.intent-unintended` built from EXISTING theme tokens (the no-raw-hex CSS contract); the legend `process_grade_trend.html.j2` (~`:58`) gains the entry.
- `swing/web/view_models/metrics/trade_process_card.py` (~`:52-54`) filter options gain the value (the facet clause (4) routes the result to), labelled via `entry_intent_label`.
- `review_form.html.j2` prose (~`:136`) — READ; edit only if it enumerates the values.
- CLI `trade analyze` (`cli.py` ~`:1356`) already maps via `entry_intent_label` — verify it renders `Unintended execution`, never `Unclassified`.
- Per RD §4 bullet 4: wherever the trade-process card shows a per-tab N, the tier page's N is quoted beside it until D61 lands (READ the current card; if the interim note already exists, it carries over unchanged — state which).
**Tests:** `test_trend_renders_own_class_not_standard_or_unclassified_b22_140` (TestClient); `test_process_card_filter_offers_the_value_b22_141`; `test_cli_analyze_label_b22_142`; `test_journal_trade_view_renders_own_label_b22_143` (the witness step-4 surface).
Commit: `feat(web): Task 9 — unintended_execution renders with its own class and label`.

## Task 10 — The two precondition pins (F2 S3, F3)

- `tests/trades/test_22b_preconditions.py::test_no_unaudited_writer_of_the_citable_fields_b22_150` — a STATIC walk (AST over every `swing/**/*.py` string constant + f-string template containing `UPDATE` and `trades`, plus the dynamic builders by NAME: `reconciliation_auto_correct.py` field-SET builder and `repos/trades.py` review-fields builder) asserting no statement SETs `notes|why_now|thesis|emotional_state_pre_trade` except the audited corrector (R0.C C.2: 10 production statements + the corrector's dynamic builder at the census; the test prints its own count). A new writer FAILS; the fix is a REPORTED finding, never a new channel.
- `test_death_then_fill_is_expressible_b22_151` — R0.C C.3 pinned by execution: a derivation where an `invalidation` lands on session D and a same-ticker in-zone fill on D+1 → `_resolve_terminal` returns the DEATH terminal (`clear_reason='invalidation'`, `clear_session=D`, `clear_trade_id` None); the same-session twin returns `fill` (R6 tie → fill).
Commit: `test(trades): Task 10 — pin the F2-S3 writer walk and the F3 death-then-fill precondition`.

## Task 11 — AUTHORIZE-THEN-ABORT closure (trigger predicate set ⊆ service predicate set)

`tests/trades/test_22b_authorize_then_abort.py::test_every_trigger_predicate_has_a_reached_service_check_b22_160` — a hand-written map `{trigger_name: [predicate_id, …]}` for the 0040 attestation triggers, CLOSURE-CHECKED against the stored head trigger SQL (every `RAISE(ABORT, '<code>: …')` message's `<code>` prefix — the executing cell writes each trigger's message with a stable code — is a key in the map, and every map key occurs in the stored SQL); each predicate id maps to a `preflight` refusal code, and a parametrized case drives the ONE-mutation fixture through `preflight` FIRST (asserting that refusal code) — so no row the service admits is aborted by SQL. Predicates with no service mirror are listed in `SERVICE_ONLY` / `SQL_ONLY` with reasons (expected: `SERVICE_ONLY = {death-before-fill derivation}`; `SQL_ONLY = ∅`).
Commit: `test(trades): Task 11 — authorize-then-abort closure over the attestation triggers`.

## Task 12 — Composition: the 22-A2 case set and the 22-A six-case gate on 22-B's tree

`tests/trades/test_22b_composition_pin.py`:
- `test_the_22a2_case_functions_are_byte_unchanged_except_the_named_three_b22_170` — the Task-0 dict of 106 shas; closure first (the implementing set, found by the A2-08 rule, equals the dict's keys); every function's sha equals its pinned value EXCEPT `[FORK R0.F-3]` A2-18, A2-19, A2-22, whose NEW shas are pinned in a separate `RULED_EXEMPTIONS` dict with the ruling cite (ledger R0.F-3 + its ruling commit).
- Rides unchanged: A2-09 (`test_a2_09_six_case_functions_are_byte_unchanged`) and A2-08 — both must pass on this tree.
- Run the full fast suite; every 22-A2 and 22-A case GREEN by EXECUTION (the 13 HEAD-reaching cases of R0.F-3's note included).
Commit: `test(trades): Task 12 — 22-A2 composition pin (106 cases; three ruled exemptions)`.

## Task 13 — Trade-20 acceptance on a live-shape DB copy + the witness script content

1. `tests/trades/test_22b_acceptance_trade20.py::test_trade20_before_and_after_every_reader_n_unchanged_b22_180` — a fixture DB carrying the live shapes (trade 20 + its fills 41/44 + AMN telemetry row 5 + ≥1 counted trade per cohort, real bytes): capture the four readers' N + `hypothesis list` output; assign trade 20 through `assign(...)`; every N identical; trade 20 in NO cohort's candidate set before AND after (asserted by calling each reader's membership step, not inferred from N); `hypothesis list` output line-for-line identical (N3 (a): 20 was in no cohort and is in none).
2. `test_trade20_attestation_readback_b22_181` — the row: tier, `admitted_leg` + evidence (`[FORK R0.F-2]`: `deployment`, `{"deployment_session":"2026-08-03","placement_session":"2026-08-01"}`), cited `["notes","why_now"]` (sorted), snapshot bytes, `outcome_known_at = '2026-08-11T16:00:00'`.
3. **Live dry-run (read-only, no write, executing cell):** copy the live DB to the scratchpad, `db-migrate` the COPY (never the live file; never open the live file through `swing`'s `connect`), run `assign-intent 20 … --dry-run` against the copy with `PYTHONPATH=.`; report the printed predicates.
4. **Witness script (post-merge, operator-executed, ONE step per result; the orchestrator scripts it from this list):** (1) stop `swing web`; plain-sqlite3 `BEGIN EXCLUSIVE; ROLLBACK` result stated; (2) `swing db-migrate` → the `22b` image path echoed, ONE image in `backups_dir`; `python scripts/schema_manifest.py --db <live>` clean at v40; `PRAGMA foreign_key_check` = []; (3) `swing trade assign-intent 20 --value unintended_execution --cite why_now,notes --reason "<r>" --dry-run` → ADMIT, tier `contemporaneous_record`, the predicates with values; (4) the same without `--dry-run`; the journal/trade view shows `Unintended execution`; `swing hypothesis list` line-for-line equal to a pre-image captured at step 3; the attestation row read on `mode=ro`; (5) RD re-reads the H-cohort counts on the live DB beside the readers' (no expected count pinned).
Commit: `test(trades): Task 13 — trade-20 acceptance on live shapes (readers unchanged, attestation read-back)`.

## Task 14 — Close-out (no new code)

Full fast suite green (report the count read off the final head); `ruff check swing/` clean; D51 diff re-read (zero deletions); the charter-§7 pointer line PROPOSED for RD in the return report (RD lands it; the cell never edits RD's charter): *"2026-09-23 — the forward intent contract now lives in `docs/training-epoch-intent-contract.md` (clause (4) `unintended_execution`, ratified; pinned by sha256 in migration 0040's header)."*; Reviewer A (`strong`) to convergence per recipe §3.

---

## Test roster → acceptance map (brief §4 @ `bd4314ea`, as restated by R0.D/R0.E)

| brief §4 item | tests |
|---|---|
| 4.1 trade 20 admits tier 2 citing `why_now`+`notes`; both-or-neither; snapshot bytes | b22_80, b22_81, b22_181; witness steps 3-4 |
| 4.2 structural required when a link exists; tier-2 refused there | b22_64, b22_89, b22_91 |
| 4.2 P1 (as RULED at N1: legs, not first-row) + boundary twins | b22_55/56, b22_84-88, b22_90, `[R0.F-2]` b22_67-70 |
| 4.2 F3 AMN geometry: 08-06 admit / 08-07 refuse / live refuse / fill+superseded refuse | b22_91-94, b22_53/54 |
| 4.2 P2 both tables (+ multi-field keys) | b22_60-62, b22_100/101 |
| 4.2 `pre_trade_locked_at` / tag-only / open trade / no back-fill / already-set / drift | b22_57/58, b22_96-99, b22_102-104, b22_71 |
| 4.2 N4 discriminators (review POST ×2, CLI review, backfill --force, corrector, raw UPDATE alone, same-value) | b22_120-127, b22_34-37 |
| 4.2 N5 unlinked intent refuses | b22_65, b22_95 |
| 4.3 NO cohort read, computed; H1/H2 synthetic named; NULL twin; else-branch fails | b22_130-137, b22_180 |
| 4.4 migration: one-edit proof, 58 cols, tuples, children, fk_check, partial UNIQUE, attempt_id, twice, D51, fourth value, `_is_head`, F1 hash | b22_20-33, b22_29, b22_50-75 |
| 4.5 single-writer seam — EIGHT surfaces by execution; only `assign-intent` writes | b22_10-12, b22_114 |
| 4.6 F2 S3 precondition walk | b22_150 |
| 4.7 display: own class/label; card N with tier N | b22_140-143 |
| 4.8 22-A2 cases green (byte-unchanged but the ruled three) | b22_170, A2-08, A2-09 |
| 4.9 death-then-fill precondition, file:line | b22_151; ledger R0.C C.3 |
| F1 contract doc | b22_01-05, b22_29-30 |
| `[R0.F-1]` telemetry belts or AL | b22_38-43 |

## Accepted limitations (declared; the reasons live in the ledger)

- **AL-1** The single-writer seam is SERVICE-enforced (eight surfaces), not schema-enforced: a raw `UPDATE trades SET entry_intent = 'unintended_execution'` without an attestation is not refused by SQL (F5/N4 rule ONE new `trades` trigger, for terminality); the drift reader (Task 5 (iii)) names it. Writer enumeration: R0.C C.2 + Task 10's walk; live incidence 0.
- **AL-2** Death-before-fill is derived in Python (`mandate_alive_at`), not in SQL; the trigger binds the recorded shape (Task 11 `SERVICE_ONLY`).
- **AL-3** `INSERT OR REPLACE INTO trades` would bypass the UPDATE-scoped N4 trigger; no production writer issues it (R0.C C.2: no `REPLACE INTO trades`), and the attestation FK is `ON DELETE RESTRICT`. Service-prevented, incidence 0.
- **AL-4** `[FORK R0.F-1 (b) only]` telemetry monotonicity is a writer property (ledger R0.F-1 (b) text).
- **AL-5** Orphan labels: the clause-(4) exclusion applies to every cohort name including unregistered ones (fail-closed direction; `cohort_intent_authority` still answers `none` for them).
