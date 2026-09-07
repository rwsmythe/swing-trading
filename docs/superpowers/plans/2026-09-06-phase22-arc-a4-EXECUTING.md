# 22-A4 EXECUTING EXTRACT — the plan of record for the executing dispatch

**THIS FILE IS A MECHANICAL EXTRACT. NOTHING HERE IS REWRITTEN.** Sections are copied verbatim and
in order per CHARC's ruling of 2026-09-07: S10 (what an executor must read), S4 (file structure),
S5 (the task ladder), S3 (the test roster), S6 (the live-migration gate), Global Constraints.

**DESIGN RECORD (the full plan):** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.md`
on branch `22-a4-plan` (4370 lines at the commit that introduced this extract). **LEDGER:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.ledger.md`.
S1/S2/S7/S8/S9/S11 are argument, limitations, routing and review history — the executor does not act
on them; they stay in the design record. **Read them only to answer a question this extract raises.**

**WHY AN EXTRACT AND NOT A SPLIT (CHARC, 2026-09-07):** the ~1,000-line cap bounds the REVIEW LOOP —
a prose reviewer has no fixpoint on a growing artifact. That loop is closed (eleven counted rounds,
operator-capped, design settled by four director rulings). A split now would re-plan a settled design
and discard or re-review 4.30M tokens of adjudicated record. The cap is a trigger to split an arc
whose design is still MOVING; this arc's design is fixed and its ladder is its ladder.

**LOSSLESSNESS CHECK (mechanical, no Codex):** every task id and every test id in the design record
appears here. Verified by id-set diff at creation — see the ledger.

---

## S10. WHAT AN EXECUTOR MUST READ BEFORE TOUCHING ANYTHING

1. This plan's **S1** -- it is the only place the three constraints are tied to code, and every
   design decision downstream cites it.
2. `swing/trades/entry.py:628-1163` -- `record_entry` (`:628-942`), `_CommitOutcome`, the DECLARED-RESIDUAL block,
   and both `_entry_transaction` paths. The block at `:973-1030` explains why the shipped code has
   the shape it has; **Task 5** rewrites it and cannot do so honestly without having read it.
3. `docs/22-a-merge-request.md` **S4.4** -- the ruling, and the two reproductions this arc's tests
   re-derive.
4. `docs/superpowers/plans/2026-09-02-phase22-arc-a3-record-entry-caller-half.md` **S7** -- the
   limitation-declaration standard, and the containment idiom (`log_contained`,
   `log_contained_note`, `safe_text`, `ascii_safe`) this arc reuses rather than re-invents.
5. `CLAUDE.md` §Gotchas -- #9 (executescript / explicit BEGIN), #11 and its 2026-08 amendments (the
   mirror family is bigger than the canonical triple; the comparator is mandatory; grep each member
   separately), the migration backup-gate strict-equality clause, the rolled-back-rowid entry and the
   writer-quoting-itself entry.
6. `swing/data/migrations/0037_latch_order_mandate_links.sql`'s header -- the
   one-migration-one-version-bump rule and the reversibility-header format this arc copies.

---


## S4. FILE STRUCTURE

**New:**

| path | what |
|---|---|
| `swing/data/migrations/0038_trade_attempt_identity.sql` | `ALTER TABLE trades ADD COLUMN attempt_id TEXT CHECK (...)`, the UNIQUE partial index, **the `trg_trades_attempt_id_immutable` BEFORE-UPDATE trigger (S2.0 -- MANDATORY; it is what closes the `A4-R4-1` false-success path)**, `UPDATE schema_version SET version = 38`, inside an explicit `BEGIN; ... COMMIT;` (gotcha #9), with a reversibility header naming BOTH the `DROP INDEX` and the `DROP TRIGGER` |
| `tests/data/test_migration_0038_attempt_identity.py` | (m1)-(m6), **(m7) the schema trigger**, (r4), (r5) -- all in Task 1's single commit |
| `tests/trades/test_22a4_corrector_refusal.py` | **(m8a) typed refusal, (m8b) order-independence, (m8d) the tier-3 override path** -- Task 1b |
| `tests/cli/test_22a4_corrector_refusal_cli.py` + `tests/web/test_routes/test_22a4_corrector_refusal_delivery.py` | **(m8c) delivery through the UNCHANGED callers** -- Task 1b |
| `tests/trades/test_22a4_attempt_identity.py` | (e), (e2), **(w)**, **(w2) the mint contract**, (f), (g), (h), (r1)-(r3), (r6), **(r7) the schema-aware probe** |
| `tests/trades/test_22a4_clause2_settlement.py` | (RD-a1), (RD-a2), (RD-a3), **(RD-a4)**, **(RD-a5)**, (RD-b), **(RD-b2)**, (c2), (k), (k2), **(k3a)-(k3b)**, **(k4a)-(k4b)**, **(k5)**, **(k6a)-(k6b)**, **(k7a)-(k7b)**, **(pr1)-(pr5)**. **Task 3 lands (k), (k2), (k3a), (k5) and (k6a)-(k6b) and (k7a)-(k7b); Task 4 lands (k3b), (k4a), (k4b), (RD-a4), (RD-a5) and the probe-call-count assertions ADDED to (k2), (k7a) and (k7b)** (`A4-R9-7`, `A4-R10-3`, `A4-R11-6`) |

**Edited:**

| path | what |
|---|---|
| `swing/data/db.py` | `EXPECTED_SCHEMA_VERSION` 37 -> 38; `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES`; `_create_pre_phase22_arc_a4_migration_backup`; `_phase22_arc_a4_backup_gate` + its call in `run_migrations` |
| `swing/data/repos/trades.py` | `insert_trade_with_event(..., attempt_id=None)` + the v38 INSERT branch + the shape guard + the pre-v38 contained drop; new `find_trade_id_by_attempt_id`; `ATTEMPT_ID_LENGTH`; **new `validate_attempt_id` -- the SINGLE validation authority, also called from `entry.py` (`A4-R9-1`)** |
| `swing/trades/entry.py` | `_mint_attempt_token`, `_AttemptIdentity`, `_begin_attempt_identity`, `_durability_probe`, `_settle_by_attempt_identity`, **`_read_resolution` (NON-MUTATING -- `A4-R11-4`)**, `_CONTEXT_SLOT`, **`_exit_rollback_failed` (`A4-R9-2`; its CALL relocated to the `record_entry` frame by `A4-R10-1` + `SS-9`)**; `_CommitOutcome` +2 fields (`resolution`, `cleanup_raised`) for THREE observations total; `_entry_transaction`'s IMMEDIATE path only -- **its `if not immediate:` branch is NOT EDITED AT ALL: no `try`, no `except`, no `as` binding, and `with conn:`'s suite stays exactly `yield`, asserted by (k3a)**; the post-commit handler, which gains BOTH deferred-path observations (Task 3) and then the settle branch (Task 4); the narrowed IntegrityError match; the declaration block rewritten |
| `swing/trades/reconciliation_auto_correct.py` | **THE ONE MODULE CHARC'S CONDITION WIDENED THE ENVELOPE BY, and it was MISSING FROM THIS TABLE until the 2026-09-07 per-location audit -- the manifest-with-a-hole class this plan already paid for twice.** Task 1b ONLY: the `_IMMUTABLE_JOURNAL_FIELDS` sibling set, `ImmutableJournalFieldError(ValueError)`, one message constant, and the shared predicate at THREE call sites -- `_preflight_reserved_transitions`, `_update_journal_field`, and the head of `_apply_tier3_override_inner` (`A4-R9-5`). **No other change and no sweep.** |
| `tests/trades/test_22a_task9_entry_wiring.py` | `test_CONTRACT_a_commit_whose_own_return_was_LOST_re_raises` rewritten in place as the settled-by-identity row (test **(c)**); its declaration prose kept as the record of what changed. **AND THE THREE ROWS THAT LIVE IN THIS FILE AND MUST STAY GREEN, named because the sweep found them scheduled with no file:** **(d)** the row-ABSENT re-raise (existing, gains the probe-called-once assertions), **(i)** the belt control, **(j)** the post-commit-STEP control |
| the version mirror family, **SEVEN spellings across ~30 files -- SIX a value-grep can see, plus SEMANTIC NAMES AND COMMENTS (`A4-R7-12`) which it cannot; NO total quoted** | 26 `EXPECTED_SCHEMA_VERSION == 37`; 11 bare-literal assertions; 4 `_current_version(...) == 37` (**2 of which stay at 37**); 1 chained (overlaps row 1); **1 INEQUALITY ceiling `versions[-1] <= 37` -- the L3 authorization gate**; and **15 `target_version=37` call sites -- 12 `run_migrations(...)` calls plus 3 direct `_phase22_arc_a_backup_gate(...)` calls -- of which 8 STAY PINNED and 7 gain a SECOND call to `EXPECTED_SCHEMA_VERSION`**. Counts are FLOORS and OVERLAP (`A4-R4-10`); the manifest is the greps plus a READ of every hit. The closure check is the full suite for the assertion families and a READ for the call sites, which fail nothing. |

**Untouched, and named so the envelope is checkable:** `swing/web/**`, `swing/cli.py`,
`swing/data/models.py`, `swing/trades/latched_origin.py`, `swing/trades/cohort_provenance_correction.py`.

---


## S5. TASK LADDER (TDD; one red -> green -> commit per task)

### Task 0: **RULED 2026-09-06 -- CLOSED. Recorded here because the ladder below was blocked on it.**

- [x] **RD RULED: `uuid4` SATISFIES constraint 2. The shape is (S-b).** **The canonical reading,
      binding on every future appeal:** *"never reusable" means the mechanism must contain **NO PATH
      THAT REISSUES** a token.* The rowid failed **because the ENGINE ITSELF hands a rolled-back id
      to the next insert -- reuse is an active, designed-in mechanism.** `uuid4` has no reissue path;
      a repetition is an RNG FAILURE, not a behaviour of the mechanism. **And it demands no certainty
      beyond what this project's evidence chain already rests on:** the H1 amendment text is pinned
      by sha256 and broker snapshots by digest -- **collision-resistance IS the admissibility
      standard elsewhere in this system.**
- [x] **CHARC RATIFIED five items** (S9): migration 0038 as shaped, the LOCK-A amendment in the
      stated shape, the `<= 37` -> `<= 38` ceiling **opened for 0038 only**, the backup gate and its
      expected-tables set, and **the S2.0 divergence** (no `Trade` field, no `_row_to_trade` change --
      he verified 57 / 56 / `{risk_policy_id_at_lock}` on the live database himself).
- [x] **ONE CONDITION ATTACHED, and it WIDENS THE ENVELOPE: S8.6 is NOT banked -- the corrector's
      typed refusal SHIPS IN THIS ARC.** See Global Constraints and Task 1b.
- [x] **RIDER CLAUSE 1 -- RD's S7.7 DETECTION REASON. ROUTED BACK, RULED 2026-09-06, REPLACEMENT
      CORRECTED 2026-09-07.** He attached it as load-bearing
      and instructed stop-and-route if it failed. **It failed:** *"a rolled-back token leaves no row
      to confirm"* is true at the instant of rollback and does not survive to probe time
      (REPRODUCED). **He confirmed both replacement wordings** -- half A with S2.5's mapper
      narrowing attached as a precondition, half B with his absolute replaced by a probability
      statement -- **and round 9 then found half B's replacement wrong in his favour** (`A4-R9-4`:
      an equality where only a strict bound holds). **S7.7 now reads
      **AT MOST `P(collision)` by CONTAINMENT, with no independence assumed and no strictness
      claimed** -- RD's verbatim sentence, ruled 2026-09-07 on `A4-R10-2`, the FOURTH and final
      statement of it (`A4-R9-4`'s strict bound was the third and was not established either).**
      **Scope, so it does not read stronger than it is:**
      the counterexample lives ENTIRELY INSIDE the collision branch, so it refutes the REASON without
      changing the practical weight.
- [x] **RIDER CLAUSE 2 -- the `fork` RE-OPEN TRIGGER for the banked allocator. STRUCK, RULED
      2026-09-06.**
      MEASURED from CPython 3.14 source: `uuid4` is `int.from_bytes(os.urandom(16))` per call, with
      no process-local PRNG state, so a POSIX port that acquires `fork` would fire the trigger with
      no hazard present. Bare `fork` is struck; generator-change and entropy-duplication survive,
      **with VM snapshot-resume recorded as an INSTANCE of entropy-duplication and never as an
      independent trigger.**
      **THIS SECOND BOX EXISTS BECAUSE THE CHECKLIST PREVIOUSLY SAID "ONE CLAUSE" WHILE THE FRONT
      MATTER AND S9 SAID TWO** (`A4-R7-4`) -- an authorization checklist that can be marked closed
      without disposing of a director-owned clause is the claimed-fix-not-present class applied to
      governance.
- [x] **NEITHER CLAUSE AFFECTED THE RULING**, which rests on the no-reissue-path reading and
      verifies. What was open was wording RD owns, and he ruled it.
- [x] **A FOURTH ITEM WAS ROUTED AFTER ROUND 9 AND RULED 2026-09-07: `A4-R9-2`, BRANCH A.** Round 9
      falsified the plan's premise that `__exit__`'s internal rollback failure is invisible to the
      wrapper. **RD SELECTED Branch A: `with conn:` stays byte-identical and the wrapper inspects
      what propagates and its `__context__` chain at the except site; a detected rollback failure
      VOIDS the probe exactly as on the immediate path.** Rule (i) is now literal on both paths
      (S2.2, S2.4, S7.15), CHARC's routed item 8 is closed without either of its two options being
      taken, and **the composition window `A4-R9-3` closes STRUCTURALLY** -- with RD's own
      2026-09-06 item-3 acceptance recorded as SUPERSEDED rather than left standing beside it.

### Task 0b: **THE 22-A LOCK-A AMENDMENT** -- lands in Task 1's commit, ruled at Task 0

**The defect this closes was found by review, not by the suite** (`A4-R3-2`, verified at the source).
`tests/trades/test_22a_task9_entry_wiring.py:1037-1041` asserts BOTH
`set(a) == set(LOCK_A_PRE_ARC_ROW)` (the complete `trades` COLUMN SET) and `a ==
LOCK_A_PRE_ARC_ROW` (full dict equality) against a golden captured by running `record_entry` at the
pre-arc commit `a18a3771`. **Adding `attempt_id` fails both**, and the test's own docstring
ANTICIPATED this arc: *"If a later change adds a `trades` column, a dict comparison would fail on the
diff -- but a comparison written to tolerate that (subset, or key intersection) would silently stop
covering the new column, so the failure is left loud."*

- [ ] **The amendment is therefore constrained by that docstring and must NOT soften the
      comparison.** Assert `set(a) == set(LOCK_A_PRE_ARC_ROW) | {"attempt_id"}` -- the addition
      NAMED, not tolerated -- then `{k: v for k, v in a.items() if k != "attempt_id"} ==
      LOCK_A_PRE_ARC_ROW` (byte identity preserved for every PRE-EXISTING column), then a THIRD
      assertion that `a["attempt_id"]` is a valid non-NULL token. The lock gets STRONGER: it now
      covers the new column explicitly instead of merely failing on it.
- [ ] **BOTH ROWS, NOT ONE** (`A4-R4-2`). The shipped test compares `a` (the `cfg`-PASSED run) AND
      `b` (the `cfg=None` run) against the golden; the first draft of this task amended only `a`, and
      `b == LOCK_A_PRE_ARC_ROW` fails for the same reason the moment the column exists. Both get the
      three-assertion treatment, **and `b`'s token must be non-NULL too** -- which is the assertion
      that pins S2.1's decision to mint regardless of `cfg`.
- [ ] **THIS IS WHY THE MINT LANDS IN TASK 1 AND NOT LATER** (`A4-R4-2`, the sequencing half): a task
      that adds the column and the repo capability but leaves `record_entry` passing the new
      `attempt_id=None` default cannot satisfy its own amended lock, so the prescribed
      red -> green -> commit cycle could not close. Task 1 therefore carries the mint and the
      threading as well; Task 2 keeps only what does not affect the persisted row.
- [ ] **`record_entry`'s docstring becomes false and is rewritten in the same commit.**
      `swing/trades/entry.py:633` promises that `cfg=None` leaves *"every persisted value
      byte-identical to the pre-arc behaviour"*, and S2.1 writes a token regardless of `cfg`. Leaving
      it is the #31 class -- a comment that still reads true while the code moved underneath it. New
      text: byte-identical for every pre-arc COLUMN, plus a per-attempt `attempt_id` that is not
      part of the pre-arc row and carries no domain meaning.
- [ ] **ROUTED, not assumed** (S9 CHARC item **5**): LOCK clause (a) belongs to a merged arc.

### Task 1: **THE SCHEMA AND EVERY MIRROR, IN ONE COMMIT** (migration 0038 + the repo write/read + the version-mirror family + the IntegrityError narrowing)

> **Tasks 1 and 2 were SEPARATE in the first draft and are now ONE** (`A4-R2-3`). Splitting them
> contradicted gotcha #11 (*"schema-CHECK + Python-constant + dataclass-validator MUST land in ONE
> task for atomic consistency"*), the commissioning brief's *"Mirrors in ONE commit (#11)"*, and this
> plan's own S2.5 sentence saying a schema change and the Python mirror that keeps it honest are one
> atomic deliverable. It would also have produced an intermediate revision carrying schema v38 with
> no validator, no carrying INSERT branch and no closure check.

- [ ] Write `0038_trade_attempt_identity.sql`: explicit `BEGIN;`, one `ALTER TABLE trades ADD COLUMN
      attempt_id TEXT CHECK (attempt_id IS NULL OR (typeof(attempt_id) = 'text' AND
      length(attempt_id) = 36))` -- **the `typeof` half is REQUIRED and this checklist carried the
      vulnerable length-only form for a full round after S2.0 was corrected** (`A4-R7-1`; MEASURED:
      a 36-BYTE BLOB passes length-only and sits in the UNIQUE index beside its byte-identical text
      twin) -- one
      `CREATE UNIQUE INDEX ux_trades_attempt_id ON trades(attempt_id) WHERE attempt_id IS NOT NULL`,
      **one `CREATE TRIGGER trg_trades_attempt_id_immutable BEFORE UPDATE OF attempt_id ON trades
      BEGIN SELECT RAISE(ABORT, '...'); END;`**, `UPDATE schema_version SET version = 38` as the
      FINAL statement, `COMMIT;`. The header carries: the reversibility clause -- **BOTH
      `DROP INDEX ux_trades_attempt_id;` AND `DROP TRIGGER trg_trades_attempt_id_immutable;`**, the
      column staying because it is nullable and inert -- why nullable, why partial, why the CHECK is
      length-only, why the trigger is unconditional and carries no `WHEN`, the
      one-migration-one-version-bump rule, **and the TWO JURISDICTION NOTES CHARC requires in the
      header itself (2026-09-06)**:
      **(A) A `BEFORE UPDATE` TRIGGER CANNOT SEE `INSERT OR REPLACE`.** The header states that the
      guard covers **UPDATE**, and that the REPLACE family was **GREPPED EMPTY against `trades`** --
      so a future REPLACE writer is **a DECLARED BREACH rather than an unknown**. *Method and count,
      recorded because a bare "we checked" is what this class survives on:* CHARC grepped the family
      across `swing/`; re-run here, `insert or replace into trades` / `replace into trades` returns
      **ZERO**, and the broader `insert or replace|replace into` returns 45 hits across 22 files of
      which **ZERO are executable statements** -- every one is prose in a migration header, a trigger
      message, or a docstring warning about this very class.
      **(B) 22-B DEMAND A REBUILDS `trades` (DROP + CREATE).** A rebuild that does not RE-CREATE both
      `ux_trades_attempt_id` and `trg_trades_attempt_id_immutable` **silently drops the guard** --
      the 0035 header's own lesson about what a rebuild costs, applied forward. CHARC has banked it
      as a **22-B precondition**; this header records it so the next rebuild's author meets it in the
      file rather than in a review.
      **THE TRIGGER IS NOT OPTIONAL, AND ITS ABSENCE FROM THIS CHECKLIST WAS THE ROUND-5 CRITICAL**
      (`A4-R5-1`): round 4 added it to S2.0's prose and to the test roster and to NOTHING an executor
      reads as a work item, so a plan whose prose called it mandatory shipped a ladder that omitted
      it -- and the omitted thing is the only guard against the `A4-R4-1` false success.
- [ ] `swing/data/db.py`: `EXPECTED_SCHEMA_VERSION = 38`;
      `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES = PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES |
      {"candidates_immutability_epoch", "latch_order_mandate_links", "fill_envelope_identity"}` (the
      three tables 0037 created, read out of the migration file rather than recalled);
      `_create_pre_phase22_arc_a4_migration_backup` (the 0037 mirror, filename
      `swing-pre-22a4-migration-<ISO>.db`); `_phase22_arc_a4_backup_gate` firing ONLY at
      `current_version == 37 and target_version >= 38`; its call added to `run_migrations` after the
      22-A gate.
- [ ] `swing/data/repos/trades.py`, **in this same commit**: `ATTEMPT_ID_LENGTH = 36` (the Python
      side of the CHECK's length half) and **`validate_attempt_id(value)` -- THE SINGLE VALIDATION
      AUTHORITY, called by BOTH this repo's pre-write guard and `entry.py`'s
      `_begin_attempt_identity`** (S2.1 carries the body and the reasoning);
      `insert_trade_with_event(conn, trade, *, event_ts, rationale=None,
      attempt_id=None)` with the shape validation BEFORE any write -- **`None`, OR
      `validate_attempt_id(attempt_id)` -> `ValueError`.**
      **THE PREDICATE IS `isinstance(str)` + exact length + `uuid.UUID` PARSE + `version == 4` +
      CANONICAL ROUND-TRIP, and each clause is load-bearing** (`A4-R7-1` gave the first two;
      **`A4-R9-1` gave the rest**): a 36-byte `bytes` value satisfies a bare length test in Python
      exactly as a BLOB satisfies `length()` in SQLite; **a 35-character string plus a NUL has
      Python length 36 and SQL `length()` 35, so it clears a length test and is refused by the
      CHECK -- inside the money-bearing INSERT; a lone surrogate clears it and fails at PARAMETER
      BINDING, a layer below the CHECK; and an uppercase canonical uuid4 clears the CHECK entirely
      and defeats the UNIQUE index, which keys on the exact text.** A length-only validator is
      therefore not a weaker mirror of the CHECK, it is a mirror of only ONE of the three layers a
      bad token can fail at. The FOURTH era branch selected by
      `"attempt_id" in cols`, identical to the v27+ branch plus the one column and one placeholder,
      **with the new column's bound parameter verified against its position, not just its name**;
      the pre-v38 contained-WARNING drop; and `find_trade_id_by_attempt_id(conn, attempt_id)`,
      schema-aware.
- [ ] `swing/trades/entry.py`: narrow the IntegrityError match to
      `"UNIQUE constraint failed: trades.ticker"` (S2.5), with the measured message quoted at the
      site and the reason -- the new index makes the loose match a FALSE "already an open position".
- [ ] **THE MINT AND THE THREADING LAND HERE, AS ACTUAL CHECKBOXES** (`A4-R6-2`: Task 0b and Task 2
      both said the mint had moved into Task 1 and Task 1 contained no such work, while Task 2 still
      scheduled it -- the amendment was announced in two places and performed in neither):
      `_mint_attempt_token()`, `_AttemptIdentity`, **the COMPLETE `_begin_attempt_identity(conn)` per
      S2.1 -- `Exception`-not-`BaseException` containment AND result validation **through the SAME
      `validate_attempt_id` the repo guard calls** (`A4-R9-1`: two hand-written predicates over one
      column are a mirror pair, and the drift that matters is the one where the SERVICE side admits
      what the WRITE side refuses -- which turns a contained degradation into a failed
      money-bearing entry), not a stub to be hardened later** (`A4-R7-2`: splitting the
      helper across two commits meant Task 1 either shipped a helper that could fail an otherwise
      successful entry, or Task 2 had no genuine red) -- and the
      `record_entry` -> `_record_entry_inner` -> `insert_trade_with_event(attempt_id=...)` threading.
      **Task 1's amended LOCK-A asserts a non-NULL token on BOTH rows, so without these the task
      cannot reach its own green.**
- [ ] **(e) and (e2) ARE SCHEDULED HERE TOO**, with the complete helper they test (`A4-R7-2`).
      **(e2) is written with ALL ELEVEN contained variants PLUS the `KeyboardInterrupt`
      propagation control -- TWELVE scenarios -- ENUMERATED FROM S3's roster so the two manifests
      cannot drift, and the COUNT is read off that roster rather than copied** (`A4-R6-9`,
      `A4-R6-4`, `A4-R9-1`; the count in this line has now been wrong twice, which is why S3 says
      the roster wins).
      *This requirement lived only in Task 2's checklist and was DROPPED when Task 2 was withdrawn
      above -- found by this plan's own post-round-7 self-audit looking for exactly that class, and
      restored here. A withdrawal is an edit, and an edit can lose a fix as easily as a rewrite can.*
- [ ] **(w2), THE MINT-CONTRACT TEST, IS SCHEDULED HERE -- it goes where the mint goes.** Found
      missing by the post-round-6 SELF-AUDIT: (w2) was specified in S3, listed in S4's file manifest
      and cited in S7.8, and appeared in **no task checklist at all** -- a decision propagated into
      the argument and not into the work, which is `A4-R5-1`'s exact class recurring on a different
      object. It patches `uuid.uuid4` (one level BELOW `_mint_attempt_token`), asserts one provider
      call per mint and exact stringification, and drives TWO attempts with the first rolled back,
      requiring DISTINCT tokens.
- [ ] **Sweep the version mirror family -- ALL SIX SPELLINGS of S1.6, in THIS commit, CLASSIFYING
      EACH BY READING IT** (`A4-R2-2`). The rules:
      - **The five ASSERTION families become 38 where the assertion is about HEAD.** Two
        `_current_version(...) == 37` sites in `tests/data/test_22a_task2_migration_0037.py` are
        assertions about **migration 0037's own result** and STAY at 37.
      - **The INEQUALITY ceiling `versions[-1] <= 37`** (`tests/data/test_no_schema_change_v3.py:41`)
        becomes 38 HERE and nowhere else -- its own comment says raising it is *"the guard WORKING AS
        DESIGNED for an AUTHORIZED migration ... which is why the bump belongs in the same commit as
        the migration and nowhere else."*
      - **The 15 `target_version=37` call sites are NOT a single class.** Eight of them are in
        `tests/data/test_22a_task2_migration_0037.py` (`:106`, `:129`, `:143`, `:148`, `:163`,
        `:393`, `:567`, `:748`) and are **0037's own subject or literal arguments to the 22-A backup
        gate under test -- they STAY at 37.** The remaining seven build a v36 world and then want
        PRODUCTION HEAD (`test_22a_task3_epoch_reader.py:306`;
        `test_22a_task4_authorization_ladder.py:90/:944/:1030`;
        `test_22a_task6a_competitor_liveness.py:97/:588`; `test_22a_task9_entry_wiring.py:89`).
      - **For those seven, ADD a second call rather than retargeting the first:** keep
        `run_migrations(..., target_version=37, ...)` and follow it with
        `run_migrations(..., target_version=EXPECTED_SCHEMA_VERSION, ...)`. **A single 36 -> 38 jump
        would bypass the new gate**, because `run_migrations` evaluates every gate ONCE against the
        INITIAL `current`, so a call starting at 36 can never satisfy `current_version == 37` -- the
        strict-equality design working as intended, and a silent hole if the plan had said
        "retarget".
      - **Sites whose intent really is an OLDER schema (`target_version=36` before seeding a
        pre-barrier world, `target_version=16` in `test_exit.py`) are NOT touched.**
      - **A SEVENTH SPELLING: SEMANTIC NAMES AND COMMENTS, which no value-grep can see**
        (`A4-R7-12`). `tests/data/test_22a_task2_migration_0037.py:98` is
        `def test_expected_schema_version_is_37()` whose BODY is a HEAD assertion -- the assertion
        becomes 38 and **the NAME must too**, or the file documents the opposite of what it checks.
        `tests/data/test_no_schema_change_v3.py:34` carries the comment *"so the ceiling is now 37"*
        beside the ceiling this commit raises. **Distinguish these from 0037-SPECIFIC test names,
        which correctly stay pinned.** Not behaviour-bearing; documentation-bearing, in executable
        files.
      - **The counts in S1.6 are FLOORS WITH OVERLAP and are not an edit manifest.** The manifest is
        produced by running the six VALUE greps and READING every hit -- **plus this seventh
        spelling, which no value grep reaches; S1.6 counts the family as SEVEN for that reason**
        (`A4-R10-7`).
- [ ] **Tests:** (m1)-(m6), **(m7) HALF 1 ONLY -- the schema trigger, direct UPDATE, with its
      MUTATION PROOF (remove the `CREATE TRIGGER`, show it RED, restore) required before this task
      can go green.** **(m7) HALF 2 -- the corrector's TYPED refusal -- belongs to Task 1b and MUST
      NOT be required here** (`A4-R6-3`: requiring the whole of (m7) before the task that implements
      the refusal made Task 1 unreachable in its own prescribed order, the amendment-induced
      dependency error the one-cycle-per-task rule exists to prevent). Also (r1)-(r4), (r6), **(r7) the schema-aware probe on a v37 database** (`A4-R8-5`), and
      (r5) the static INSERT closure walk over **FOUR**
      statements -- ONE carrying and **THREE** reasoned era exclusions -- **with its mutation proof
      run and shown RED IN BOTH DIRECTIONS** (column removed from the v38 branch; an unreasoned fifth
      statement added). **RED first**: (m1)'s FIRST assertion, `EXPECTED_SCHEMA_VERSION == 38`, fails with
      `AssertionError` (it reads 37); the SQL assertions that NAME the column raise
      `OperationalError: no such column` (`A4-R4-12` -- the two are different transcripts and the
      task must declare the one it will actually see).
- [ ] Commit: `feat(data): Task 1 -- migration 0038 trades.attempt_id, the UNIQUE partial index, the repo write/read mirrors and the version-mirror family, in one commit`

### Task 1b: **THE CORRECTOR'S TYPED REFUSAL** -- CHARC's attached condition, shipping in this arc

> **Ruled 2026-09-06.** This was S8.6, proposed as a banked follow-on; CHARC refused the banking and
> widened the envelope by exactly `swing/trades/reconciliation_auto_correct.py` (Global Constraints).
> **The trigger stays the GUARD OF RECORD** -- it covers writers not yet written -- **and the typed
> refusal is its LEGIBLE FACE.**

- [ ] Add the refusal so `field_name="attempt_id"` on `trades` is refused BEFORE the UPDATE is
      composed, with a typed error, not an abort from the database.
- [ ] **THE SHAPE IS THIS PLAN'S, THE BEHAVIOUR IS RULED.** A **SIBLING set** (e.g.
      `_IMMUTABLE_JOURNAL_FIELDS`) is the likely shape rather than a new entry in
      `_RESERVED_JOURNAL_FIELDS`, because **the existing dict means something different**: its
      **SEVEN** members (`A4-R7-10`; counted at `reconciliation_auto_correct.py:178-196` -- the range read `:178-190` and was short, MEASURED 2026-09-07 per `A4-R11-13`; and they
      span `fills` as well as `trades` -- `fills.action` and `fills.trade_id` are ROLE columns added
      later) encode COUPLED invariants that can only be written coherently alongside other rows, and
      its message directs the operator to the surface that writes them together. `attempt_id` has no
      such surface.
- [ ] **THE MESSAGE MUST NOT NAME A "COUPLED SURFACE" -- THERE IS NONE.** It names the column as
      **WRITE-ONCE IDENTITY THAT NO SURFACE WRITES**: set by the entry INSERT, never corrected,
      never re-assigned, and refusing it is not a routing hint but a statement that the operation
      does not exist. A message copied from the coupled-surface family would send an operator
      looking for a screen that cannot be built.
- [ ] **THE TYPE MUST BE CALLER-COMPATIBLE, OR THE CONDITION IS NOT MET** (`A4-R6-6`, verified at
      the source). The sibling type is **`ImmutableJournalFieldError(ValueError)`** -- NOT a bare
      `Exception` subclass. The existing `ReservedJournalFieldError` inherits **directly from
      `Exception`** (`reconciliation_auto_correct.py:109`), and both callers reach a `ValueError`
      handler with no handler for that type (`swing/cli.py:3929` region;
      `swing/web/routes/reconcile.py:1640`) -- so a bare-`Exception` refusal would surface as an
      uncaught CLI traceback and a web 500. **That is the same operator experience CHARC's condition
      exists to replace**, arriving one layer out. Deriving from `ValueError` reaches both existing
      handlers with **no production caller edit**.
- [ ] **THE CHECK GOES IN THREE PLACES, SHARING ONE PREDICATE AND ONE MESSAGE** (`A4-R6-7` gave two,
      verified at the source; `A4-R9-5` found the third and it is the one an operator can actually
      reach): `_preflight_reserved_transitions`, `_update_journal_field`, **and the head of
      `_apply_tier3_override_inner`.** The module
      applies multi-field corrections SEQUENTIALLY and preflights the whole payload for exactly that
      reason -- its own comment says a per-field-only check made refusal depend on **JSON KEY
      ORDER**. A backstop-only implementation would execute an earlier field's UPDATE before
      discovering `attempt_id` second.
- [ ] **THE THIRD SITE, AND WHY IT IS NOT A SWEEP** (`A4-R9-5`, verified by reading the module).
      `_preflight_reserved_transitions` is called from **exactly one place** --
      `_handle_multi_field_correction:2655` -- and **NOT** from `_apply_tier3_override_inner:1608`,
      which is a SUPPORTED OPERATOR SURFACE (`swing journal ... --override`). That path INSERTs the
      new correction row (step 4), advances the prior row's `superseded_by_correction_id` (step 5),
      and only then walks `operator_truth_value` field by field (step 6) -- so with `attempt_id`
      LAST, two writes and every earlier field's UPDATE have already executed when
      `_update_journal_field`'s backstop refuses. **What that costs, stated exactly rather than
      dramatised:** the PUBLIC entry point `apply_tier3_override:910` owns `BEGIN IMMEDIATE` /
      COMMIT / ROLLBACK and rolls the whole thing back, so *"Nothing was written"* stays TRUE there;
      the exposure is (a) the module's own documented composition surface -- its docstring invites
      callers to *"compose via `_apply_tier3_override_inner` inside an existing tx"*, and such a
      caller owns the rollback -- and (b) the ORDER-INDEPENDENCE property (m8b) exists to establish,
      which is simply **not established on this surface** by a backstop.
      **The fix is scoped to the NEW immutable set ONLY: a call to the same shared predicate over
      `operator_truth_value` at the head of `_apply_tier3_override_inner`, before step 4.**
      **AND THE THREE SITES ARE A CLOSURE, NOT A ROSTER -- STATED WITH ITS METHOD** (`SS-16`,
      2026-09-07; the Demand-C lesson applied before a reviewer has to apply it). A list of call
      sites is the same instrument as the count it replaced unless something establishes it is
      COMPLETE. **`_update_journal_field` IS the closure**, and here is how that was established, by
      an AST walk of the module plus a grep for raw SQL rather than by reading the call sites the
      plan already knew about:
      **(1)** the module has FIVE public functions (`apply_tier1_correction`,
      `apply_tier2_resolution`, `apply_source_direction_resolution`, `apply_tier3_override`,
      `stamp_pending_ambiguity`);
      **(2)** `_update_journal_field` has exactly FOUR callers --
      `_apply_tier1_correction_inner:1348`, `_apply_tier3_override_inner:1749`,
      `_handle_single_field_correction:2542`, `_handle_multi_field_correction:2680`;
      **(3)** it is the ONLY site in the module that writes an OPERATOR-SUPPLIED journal field --
      the module's other `UPDATE trades` / `UPDATE fills` statements (`:1419`, `:2594`, `:2734`)
      each write the fixed `reconciliation_status` column and cannot carry `attempt_id`.
      **So the backstop reaches every operator surface, which is what the (m8a)-(m8d) heading
      claims, and the two EARLY checks are ORDERING refinements on the two surfaces where ordering
      is observable.** The other two need none, and the reason is per-surface rather than general:
      `_handle_single_field_correction` writes ONE field, so ordering is vacuous; tier-1 calls
      `_update_journal_field` at its step 5 and INSERTs its correction row at step 7, so the refusal
      precedes every write it makes. *Stated because "three call sites" read as an enumeration for
      four rounds, and an enumeration is exactly what this project has a standing rule against
      trusting.*
      **Calling `_preflight_reserved_transitions` there instead is DECLINED and the reason is
      CHARC's own bound:** that would newly refuse the SEVEN pre-existing `_RESERVED_JOURNAL_FIELDS`
      members earlier on this path too -- a behaviour change to shipped functionality, i.e. the sweep
      his condition explicitly excluded. **Refusing `attempt_id` early changes the behaviour of
      nothing that exists today**, because the column does not exist today.
- [ ] **Tests: (m8a), (m8b), (m8c) and (m8d)** -- the named S3 rows for this task (`A4-R7-3`): the
      typed service refusal, the multi-field preflight asserting ZERO journal UPDATEs, DELIVERY
      through the unchanged CLI (exit 2, no traceback) and web (status 400) callers, and
      **(m8d) the TIER-3 OVERRIDE path** (`A4-R9-5`). **(m7) half 2 is
      SUPERSEDED by (m8a)** -- it belonged to a red base that no longer exists once Task 1 lands the
      trigger. **Declared first red: (m8a)'s `sqlite3.IntegrityError`.**
- [ ] **Bounded:** one sibling refusal set, one message constant, the shared predicate at three call
      sites, and the assertions above. **No other change to that module and no sweep** -- the
      widening is exactly this, and the third call site is inside it because it refuses only the
      column this arc introduces.
- [ ] Commit: `feat(trades): Task 1b -- the corrector refuses attempt_id with a typed error instead of authorizing it into a trigger abort`

### Task 2: **WITHDRAWN -- folded into Task 1. The number is kept so every downstream reference stays valid.**

> **`A4-R7-2`.** Task 2 held the identity apparatus's SAFETY behaviour while Task 1 held the mint
> itself, and the two could not both have honest red/green contracts: if Task 1 implemented S2.1
> fully, Task 2's (e2) was already green; if it did not, Task 1 committed a helper that could fail an
> otherwise successful entry -- on the money path, for a commit. **Task 1 now owns the complete
> helper and both tests.**
>
> **The heading is kept as a withdrawal stub rather than deleted, and the tasks below are NOT
> renumbered.** Renumbering is what produced `A4-R3-11` and then `A4-R7-11`: every stale
> "Task N" reference in this document is a defect this loop has already paid for twice, and a
> withdrawal stub costs one paragraph where a renumber costs a sweep that has failed before.
>
> **One item moved OUT of this task rather than into Task 1:** the direct import of
> `find_trade_id_by_attempt_id` into `entry.py` now lands in **Task 4**, with its first consumer
> (`_durability_probe`). Adding it earlier would commit an unused import and **break the Ruff-clean
> gate this plan requires of every commit** -- the import seam's discipline (`A4-R4-7`) is recorded
> at Task 4 instead.

### Task 3: the THREE observations (TWO new fields) -- the immediate path in the wrapper, the deferred path in `record_entry`

> **THE SCHEDULING RULE THIS TASK IS NOW WRITTEN AGAINST -- and it is the plan's answer to a class
> that has cost four rounds** (`A4-R7-2`, `A4-R8-3`, `A4-R9-7`, `A4-R10-3`). The first three were
> each fixed by MOVING A TEST LATER, and **that is what produced the fourth**: Task 3 was left
> shipping `_exit_rollback_failed` with every test of it in Task 4, so the task would have gone green
> against a predicate that could have been `return False` throughout.
> **THE CLASS IS NOT "a task schedules a test it cannot run". IT IS "the plan schedules by ARTIFACT
> rather than by the ASSERTION each test makes."** A task list built from artifacts can put code in
> one commit and its discriminator in another and still read as complete on both.
> **THE RULE: every task ships only code for which an assertion IN THAT TASK distinguishes the
> shipped implementation from its naive substitute.** Applied here: `_exit_rollback_failed` STAYS in
> Task 3 -- because its call site (the observation block below) is in Task 3 -- and Task 3 gains
> **(k5)**, a row that discriminates it from `return False` **using no probe at all**. What moves to
> Task 4 is only the assertions that need the probe. *The naive fix -- move the code -- was tried
> first in this very pass and reversed: it left Task 3 with no deferred-path deliverable and pushed
> the discriminator problem one task along.*

- [ ] `_CommitOutcome` gains `resolution` and `cleanup_raised`, each documented
      as an OBSERVATION -- and `resolution` is RE-READ from `conn.in_transaction` after any rollback
      attempt, never inferred from the fact that the call raised (`A4-R2-7`).
      **NO `body_completed` FIELD** (RD's PIN 1 on `A4-R10-1`): `record_entry`'s shipped
      `result is not None` guard is that observation already.
- [ ] **`_read_resolution(conn, *, attempted)` -- the shared helper, NON-MUTATING** (`A4-R11-4`,
      which dissolves `A4-R11-3`): it re-reads `conn.in_transaction` and NAMES the state
      (`still_open` / `rolled_back` / `not_needed`). **It issues no SQL, performs NO rollback, and
      cannot change what escapes.** Contained in the ALARM direction (`still_open`).
      *The retired version owned a rollback; it could not both contain that failure and preserve the
      immediate ladder's `raise cleanup_error from write_error`, and on the deferred path it retried
      on a wounded connection BEFORE the failure had been detected.*
- [ ] Immediate path: set `resolution` + `cleanup_raised` in all
      arms of the existing cleanup ladder **without changing either existing message and WITHOUT
      touching `raise cleanup_error from write_error`**, naming the state through
      `_read_resolution` so the two paths cannot drift on the one thing they share.
- [ ] **`_CONTEXT_SLOT` and `_exit_rollback_failed(escaping, ambient)`** (S2.2): the
      `isinstance` filter is REMOVED (RD, `A4-R10-1`); the read goes through the BASE GETSET
      DESCRIPTOR and is contained in the ALARM direction (`A4-R11-1`, CRITICAL); the captured
      ambient exception is excluded by **`is`-identity, never equality** (RD, `A4-R11-2`).
      `_CONTEXT_SLOT` is built from `BaseException.__dict__["__context__"]`, the same source as this
      module's existing `_EVIDENCE_SLOTS`. Its docstring anchors its CPython citation on
      CONTENT (the function name and the verbatim "Commit failed; try to rollback" comment) with the
      **UPSTREAM digest + fetch URL** in SOURCE (S1), **never on bare line numbers and never on a
      local copy's hash** (Global Constraints, as amended 2026-09-07).
- [ ] **The ambient capture in `record_entry`:** `ambient = sys.exc_info()[1]` on the line
      IMMEDIATELY BEFORE the `try` that opens the guarded region. **`sys.exc_info()[1]`, not
      `sys.exception()`** -- the latter is Python 3.12+ and `pyproject.toml:9` declares `>=3.11`.
- [ ] **The ORDER is DETECT then READ** (`A4-R11-3`): `_exit_rollback_failed` first,
      `_read_resolution` second. Nothing in the deferred block mutates the connection, and the order
      states rule (i) rather than merely satisfying it.
- [ ] **THE PRE-ARC GATE IS SPLIT IN THIS TASK** (`A4-R11-5`): `if result is None or not
      outcome.committed: raise` becomes `if result is None: raise` followed by `if not
      outcome.committed:` whose body ends in the same bare `raise`. **The behaviour is unchanged --
      both arms re-raise** -- and without the split there is no branch for the observation to sit
      under, so (k3a)'s Task-3 half asserts a shape this task would not have created. *Task 4 then
      only replaces that bare `raise` with the settle; it does not split anything.*
- [ ] **The DEFERRED path's observation block, in `record_entry`'s post-commit handler** (S2.2,
      S2.4) -- inside `result is not None and not outcome.committed and not _reserve`, calling
      `_exit_rollback_failed(post_commit_error, ambient)` and then `_read_resolution(conn,
      attempted=False)`. **NO rollback, NO log, NO statement on this path** -- `__exit__` owns the
      rollback and its failure is already what escaped. The fields are written and nothing reads
      them yet.
- [ ] **`_entry_transaction`'s `if not immediate:` BRANCH IS NOT EDITED** -- no `try`, no `except`,
      no `as` binding, no statement added inside `with conn:`, whose suite stays exactly `yield`
      (`SS-9`; RD's PIN 1). **(k3a) asserts this as an AST property.** *An earlier version of this
      task put an unconditional state-observer in a new handler there, which reached the
      pre-arc BODY-RAISE branch and would have issued a rollback that path never issued -- 22-A LOCK
      clause (c)'s subject. The observation belongs in the frame that already has the scope.*
- [ ] **Tests: (k), (k2), (k3a), (k5), (k6a)-(k6b) and (k7a)-(k7b) ARE SCHEDULED HERE.**
      **(k7a)-(k7b) are here because `_CONTEXT_SLOT` and the base-slot read SHIP here**
      (`A4-R11-6`'s rule; the inverse schedule check found this on the fix leg's own edit, where
      the two subclass rows had been written into the four-row-matrix row, scheduled in Task 4, so
      Task 3 would have gone green against `escaping.__context__` -- the exact `A4-R11-1` defect, in
      the task that ships its fix). **RED first**:
      (k) asserts a `resolution` field that does not yet exist; (k3a)'s AST walk fails against any
      shape that leaves the immediate assignment unguarded, puts a `try` on the deferred branch, OR
      leaves the pre-arc gate unsplit (`A4-R11-5`);
      **(k5) fails against `return False`**, which is the assertion this task previously had none of;
      **(k6a)-(k6b) fail against a naive IMMEDIATE-path implementation** -- one that assigns
      `rolled_back` whenever `rollback()` returns, and one that routes the immediate path through a
      containing shared helper and so loses `raise cleanup_error from write_error` -- which is the
      direction this task previously had none of either (`A4-R11-6`, `A4-R11-4`).
- [ ] **WHAT IS EXPLICITLY *NOT* HERE, AND WHY EACH ITEM IS NOT** (`A4-R9-7`, `A4-R10-3`; siblings
      `A4-R7-2`, `A4-R8-3`). **(k3b)**, **(k4a)**, **(k4b)**, **(RD-a4)**, **(RD-a5)** and
      **(k2)'s probe-call-count-of-ZERO assertion** all assert what `record_entry` DOES with these
      observations -- it settles by probe, or refuses to -- and **`_durability_probe` and
      `_settle_by_attempt_identity` do not exist until Task 4.** **Every one of them is excluded for
      the SAME single reason: it names the probe.** *Stated as a checklist line rather than fixed
      silently, because the class has cost this plan four rounds and the cheap defence is a task
      list that says what it is not doing and why -- one reason, not a list of special cases.*
- [ ] Commit: `feat(trades): Task 3 -- the transaction wrapper observes resolution and cleanup failure, and record_entry observes them for the deferred path`

### Task 4: clause 2 returns

- [ ] `_durability_probe(db_path, attempt_id)` per S2.3 -- `open_connection`, bounded busy timeout,
      contained close.
- [ ] **The direct import of `find_trade_id_by_attempt_id` into `entry.py` lands HERE, with its
      first consumer** (`A4-R7-2`): earlier would be an unused import and a Ruff-clean violation.
      **Keep `entry.py`'s existing `from swing.data.repos.trades import ...` style**, so test
      (RD-a2)'s patch target -- `swing.trades.entry.find_trade_id_by_attempt_id` -- is the name the
      service actually consults (`A4-R4-7`).
- [ ] **`_settle_by_attempt_identity(attempt, outcome, req, post_commit_error)`** per S2.4 -- the
      FOUR-argument signature (`A4-R4-6`: Task 4 previously specified three, which makes S2.4's
      required exception-preservation impossible without hidden exception discovery), the four
      observed conditions, `BaseException`-contained, ticker-corroborated, returning the probe's
      `tuple[int, str] | None` UNCHANGED, ALARM on anything unproven.
- [ ] **The settle replaces the bare `raise`** in the `if not outcome.committed:` branch **Task 3
      already split** (`A4-R11-5`), beneath the observation block Task 3 already put there. **This
      task splits nothing.** The lost-commit warning text (ASCII, naming the trade id and saying
      DO NOT RETRY).
- [ ] **Tests: (pr1)-(pr5) ARE SCHEDULED HERE** (`A4-R11-7`, `A4-R11-10`) -- the five probe
      design requirements, each with the assertion that goes red if the requirement is dropped.
      **RED first**: every one of them names `_durability_probe`, which this commit introduces.
- [ ] **Tests:** **(w)** the end-to-end token-flow row, **(RD-a1) in ALL THREE rollback shapes --
      raises-without-effect, raises-after-effect, and RETURNS-without-effect; the third is the only
      one that discriminates the returning-arm re-read** (`A4-R8-2`), (RD-a2),
      (RD-a3), (RD-b), **(RD-b2)**, (c) -- **rewriting
      `test_CONTRACT_a_commit_whose_own_return_was_LOST_re_raises` in place** -- (c2), (d), (f),
      (g), (h), plus the two regression controls (i) and (j).
- [ ] **AND THE ASSERTIONS DEFERRED OUT OF TASK 3, ALL FOR ONE REASON -- THEY NAME THE PROBE --
      Tests: (k3b), (k4a), (k4b), (RD-a4) and (RD-a5) ARE SCHEDULED HERE**
      (`A4-R9-7`, `A4-R10-3`, `A4-R10-1`): **(k3b)** the `sys.settrace` row that asserts a settled
      SUCCESS through `record_entry`'s own observation; **(k4a)** and **(k4b)** the two deferred
      rollback-failure sequences, each asserting a probe call count of **0** and the ORIGINAL
      surfacing (their DETECTION half is already pinned by (k5) in Task 3, and each row re-asserts
      it so the row stands alone); **(RD-a4)** the bare predicate's named false positive; **(RD-a5)**
      the caller-side obligation the `body_completed` removal rests on;
      **(k7a)-(k7b) each GAIN their probe-call-count-of-ZERO assertion here** (`A4-R11-6`: their
      no-probe halves shipped in Task 3 with the base-slot read they discriminate);
      and **the two assertions ADDED to rows Task 3 already shipped: (k2)'s probe-call-count-of-ZERO,
      and (k3a)'s ordering half** -- that `_read_resolution` is LEXICALLY BEFORE
      `_settle_by_attempt_identity` in `record_entry`'s handler, which **cannot be written in Task 3
      and would PASS VACUOUSLY there** on an AST walk that finds no such call (`SS-14`).
      **All of them patch `swing.trades.entry._durability_probe`, which exists only from this
      commit.**
- [ ] Commit: `feat(trades): Task 4 -- clause 2 returns, settled by a fresh-connection read on attempt identity`

### Task 5: the declaration in code says what is now true

- [ ] Rewrite `swing/trades/entry.py:973-1030`'s DECLARED-RESIDUAL block: it currently says the
      residual is declared and the primitive is *"deliberately NOT built here."* It becomes the
      record of BOTH -- what the residual was, both reproductions, and how each precondition is now
      supplied -- because the two reproductions are the reason the design has the shape it has, and
      deleting them would leave the shape unexplained.
- [ ] Update `_entry_transaction`'s and `_CommitOutcome`'s docstrings for the new observations.
- [ ] No behaviour change; the suite must be unchanged-green.
- [ ] Commit: `docs(trades): Task 5 -- the entry-path declaration records the supplied preconditions, not a residual`

### Task 6: the PRE-REVIEW full-suite gate

- [ ] `python -m pytest -m "not slow" -q` from the worktree; fix to GREEN **before** the Codex loop,
      so the review converges on a green diff. Compare against the plan-time baseline in S11.
- [ ] `ruff check swing/` clean.

### Task 7: the POST-CONVERGENCE final-head gate

- [ ] Re-run the full fast suite on the final head after the last review fix; the number in the
      return report is READ OFF THAT RUN.
- [ ] `git log <base>..HEAD --format='%H%n%(trailers)'` -- every commit's trailers empty.

---


## S3. TEST DESIGN -- every assertion computed under BOTH paths

> **The rule this section is written against:** a DISCRIMINATING test that passes under both the
> pre-fix and the post-fix path is worthless, so each discriminating entry states **what the
> assertion evaluates to before the change and after it**. Where "before" is not a state this tree
> has ever been in, the pre-fix path is the NAIVE implementation the test exists to exclude, and it
> is named.
>
> **A SECOND, SEPARATE ROSTER EXISTS AND IS LABELLED AS SUCH** (`A4-R1-8`): (i) and (j) are
> REGRESSION CONTROLS. They pass identically on both trees BY DESIGN -- their job is to fail if this
> arc breaks something it must not touch -- and they are NOT evidence that clause 2 was implemented.
> The first draft of this section swept them under a universal claim; separating the rosters is the
> fix, because a control counted as evidence inflates the evidence.
>
> **CHARC's standing trap is honoured throughout:** a test asserting only *"it raised"* or *"it did
> not crash"* passes an implementation that swallows everything. Every row below asserts the RESULT
> SHAPE, the ROW COUNT, or the IDENTITY of what escaped.
>
> **AND THE ROSTER IS NOW CHECKED BY AN INSTRUMENT, NOT BY READING** (`SS-13`, 2026-09-07 --
> `A4-R10-3`'s generalisation turned into a check). `assertion_schedule_audit.py`, preserved beside
> this arc's review evidence, walks every row, collects the CODE SYMBOLS its text names, finds the
> TASK that schedules the row and the TASK that ships each symbol, and reports every row scheduled
> BEFORE something it names. **It is deliberately over-inclusive -- prose counts -- so every hit is
> READ**, and the three that survive as prose are named here so nobody re-adjudicates them:
> **(k2)**, **(k3a)** and **(k5)** each EXPLAIN why an assertion of theirs is deferred to Task 4,
> and **(r7)** names
> `_settle_by_attempt_identity` in its *why this row exists* rationale while asserting only on the
> repo function Task 1 ships. **Three rows are therefore SPLIT across two tasks and each says so in
> its own text** -- which is what the rule asks for, and is why the instrument cannot be made to
> read clean without either lying in the row or removing the explanation. **It found one real defect on its first run, in a row this same pass
> had just added** -- see (k3a).

### The full roster

| id | subject | kills |
|---|---|---|
| (m1)-(m6) | migration 0038: column, CHECK, index, gate, no-op re-run, data preserved, CHECK/Python drift | a schema that does not enforce what the design assumes |
| **(m7)** | the IMMUTABILITY trigger: a direct `UPDATE trades SET attempt_id` ABORTs (schema half) | **`A4-R4-1` -- a token re-assignable after insertion is not identity** |
| **(m8a)-(m8d)** | the corrector's TYPED refusal, its ORDER-INDEPENDENCE, its DELIVERY through unchanged CLI/web callers, and **the TIER-3 OVERRIDE path** | **`A4-R6-6`/`A4-R6-7`/`A4-R7-3`/`A4-R9-5` -- authorize-then-abort, key-order dependence, a refusal the operator never sees, and a supported operator surface the preflight never reached** |
| (r1)-(r6) | repo: write, pre-v38 drop, malformed reject, model/schema drift comparator, static INSERT closure walk, IntegrityError mapping | the mirror family (#11) and the defect the index introduces |
| **(r7)** | the PROBE is schema-aware: on v37 it returns `None` WITHOUT raising | **`A4-R8-5` -- an unconditional `WHERE attempt_id = ?` passes the whole suite while the advertised branch does not exist** |
| **(RD-a1)** | the probe is NOT CALLED when the rollback RAISED -- in BOTH its shapes | **R10-02 by assertion, not comment** |
| **(RD-a2)** | the probe NEVER receives the writer's connection | **R10-02's structural half** |
| **(RD-a3)** | rollback raises before taking effect, row PENDING -> NOT SUCCESS | **R10-02's reproduction** |
| **(RD-a4)** | the predicate's FOUR-ROW MATRIX -- {`inside_except` x `chained`}, every cell computed under BOTH predicates -- plus the TWO subclass-descriptor rows | **`A4-R11-2` + `A4-R11-1`: a one-row pin passed a false premise upward; the matrix is the repair** |
| **(RD-b)** | a concurrent insert takes our freed rowid -> NOT confirmed as ours | **R10-03** |
| **(RD-b2)** | a rolled-back token REUSED by a later committed row IS confirmed -- the declared residual, VERIFIED not asserted | a declaration nobody executed (`A4-R1-1`) |
| (c) | commit raises, row LANDED -> SUCCESS with warning, both paths | the arc's headline |
| (c2) | a REAL (unproxied) commit failure -> resolved, probe absent, re-raise | proxy-only test theatre |
| (d) | commit raises, row ABSENT -> re-raises the ORIGINAL | a settle that invents rows |
| **(w)** | ONE token flows mint -> INSERT argument -> probe argument, with a mint that returns DIFFERENT values each call | **a disconnected or double-minted identity that every constant-token test blesses** |
| **(w2)** | the MINT'S OWN CONTRACT: it calls `uuid.uuid4` once per mint, and two attempts yield two tokens | **`A4-R6-5` -- a constant mint that every `_mint_attempt_token`-level patch blesses** |
| (e) | co-durability OBSERVED AT THE TRANSACTION BOUNDARY: the writer sees the token while a fresh connection sees no row | **a post-commit stamp that the committed/rolled-back pair cannot tell from the real thing** |
| (e2) | the identity apparatus cannot FAIL an entry | a nicety that breaks the money path |
| (f) | no database path (in-memory) -> today's behaviour, no crash | an unguarded probe |
| (g) | a raising probe leaves the ORIGINAL exception untouched | the R11-03 class inside the new code |
| (h) | the probe connection reads `read_uncommitted = 0` | visibility assumed rather than pinned |
| (k) | the deferred path OBSERVES its own already-resolved lost commit | a wrapper that assumes instead of reading |
| (k2) | the deferred path's exception identity is UNCHANGED | an arc that quietly re-plumbs the pre-arc path |
| **(k3a)-(k3b)** | STATIC (AST) and RUNTIME (`sys.settrace`): the `A4-R1-3` window is closed on BOTH paths -- by a guarded `try` on the immediate one, and by `record_entry`'s own observation on the deferred one, whose branch (k3a) asserts contains **no `try` at all** | **`A4-R1-3`'s window -- (k3a) proves the property statically on each branch and pins the byte-lock; (k3b) proves the behaviour at the one line** |
| **(k7a)-(k7b)** | the `__context__` data descriptor that LIES and the one that RAISES -- the base-slot read's discriminator, IN TASK 3 where the read ships | **`A4-R11-1` reproduced; scheduled by `A4-R11-6`'s rule after the inverse check indicted the pass that wrote it** |
| **(k6a)-(k6b)** | the IMMEDIATE path's returning-arm re-read and its took-effect-then-raised ladder, discriminated IN TASK 3 with no probe and no `record_entry` | **`A4-R11-6`: Task 3 shipped the immediate path's semantics with every discriminator in Task 4** |
| **(k5)** | the chained `__context__` signal is DETECTED, with NO probe -- the Task-3 discriminator | **`A4-R10-3` -- a task that ships a predicate and schedules every test of it in the NEXT task goes green against `return False`** |
| **(k4a)-(k4b)** | the deferred path's two rollback-FAILURE sequences -- **DETECTION and OUTCOME both pinned** | **`A4-R9-2` (RD, 2026-09-07): rule (i) is literal on this path too; each row fails an implementation with no detection, which the OUTCOME-only version certified** |

**REGRESSION CONTROLS -- a separate roster, identical under both paths by design:**

| id | subject | what it protects |
|---|---|---|
| **(pr1)-(pr5)** | the probe's five design requirements, each with the assertion that would go red if it were dropped: the 2000 ms bound, a contained close AFTER a good read, the ticker corroboration S7.7 rests on, no-token-no-probe, and **the probe cannot CREATE a database** | **`A4-R11-7` + `A4-R11-10`: four decisions with no discriminator, and one that let an observe-only mechanism write to disk** |
| (i) | the belt still refuses a same-ticker retry | the belt is not mistaken for the fix, and is not weakened by it |
| **(RD-a5)** | a body that raises never reaches the probe, on BOTH paths | **the CALLER-SIDE obligation the `body_completed` removal rests on (gotcha #31)** |
| (j) | the post-commit-STEP path is byte-unchanged | 22-A3's shipped clause-1 behaviour, through a handler this arc edits |

---

### (m1) The column, the CHECK, and the version

**Post-fix:** `EXPECTED_SCHEMA_VERSION == 38`; after `run_migrations(target_version=38)`,
`PRAGMA table_info(trades)` contains `attempt_id`; `INSERT ... attempt_id = NULL` succeeds;
`attempt_id = <36 chars>` succeeds; `attempt_id = ''`, `attempt_id = <35 chars>` **and a 36-BYTE
BLOB (`b"..."` of length 36)** each raise `sqlite3.IntegrityError` naming the CHECK. **The BLOB case
is the one that fails a length-only predicate** (`A4-R7-1`; MEASURED: length-only ACCEPTS it and the
UNIQUE index then holds it beside its byte-identical text twin, so this row is what makes the
`typeof` half testable rather than merely written down). **Pre-fix:** the constant is 37 and the column does not
exist, so the first two assertions raise `OperationalError: no such column`. **Pre-fix, per assertion** (`A4-R3-10`, and the sentence this replaces still said "the first
assertions fail with `no such column`" two lines before contradicting itself -- `A4-R6-13`): `EXPECTED_SCHEMA_VERSION == 38` fails with `AssertionError`
(it is 37); the `PRAGMA table_info` membership check fails with `AssertionError`; only the SQL that
NAMES `attempt_id` raises `OperationalError: no such column`. **Task 1's declared first red is the
`AssertionError` on the constant**, which is the first assertion in file order. **MEASURED already**
for the CHECK's two rejections and its acceptance (S2.0), so the test encodes a verified behaviour
rather than an expected one.

### (m2) The UNIQUE partial index

**Post-fix:** two rows with the same non-NULL token -> `IntegrityError: UNIQUE constraint failed:
trades.attempt_id`; **N rows with NULL tokens all commit** (MEASURED). **Pre-fix:** no index, both
insert cleanly -- so a test that only asserted "NULLs are allowed" would pass on both trees and is
not sufficient on its own; the duplicate-rejection half is what distinguishes.

### (m3) The backup gate -- **THREE assertions, because the first one alone proved the least**

> **STRENGTHENED 2026-09-07 (`A4-R11-8`, the round-11 MAJOR most consequential for the LIVE
> database**, which crosses this migration exactly once holding real money-bearing trades). The
> previous version of this row called the gate FUNCTION directly. **A gate that is written and never
> WIRED passes it**, and so does an expected-table set that omits one of 0037's three tables --
> and S6's live witness then compared the backup against "the expected set", which makes the check
> confirm the constant against itself rather than against the database.

**(m3a) THE GATE'S OWN BEHAVIOUR, called directly.** `_phase22_arc_a4_backup_gate` writes a
`swing-pre-22a4-migration-<ISO>.db` and verifies it when `current_version == 37 and target_version
>= 38`; it does **nothing** at `current_version == 36` (STRICT equality, the
`pre_version == (target - 1)` gotcha) and raises `MigrationBackupRequiredException` for an in-memory
source. **Pre-fix:** the function does not exist. The 36-and-target-38 case is the one that
distinguishes a `<=` gate from an `==` gate and is asserted explicitly.

**(m3b) `run_migrations` INVOKES IT -- asserted through the RUNNER, and asserted to be
LOAD-BEARING.** Build a v37 file-backed database, then call
`run_migrations(conn, target_version=38, backup_dir=tmp)` and assert exactly one
`swing-pre-22a4-migration-*.db` appears in `tmp`. **And the discriminating half, which mere
appearance does not give:** monkeypatch the gate to raise `MigrationBackupRequiredException`, call
the runner again on a fresh v37 database, and assert the exception propagates **and
`SELECT version FROM schema_version` still reads 37** -- i.e. **0038 did not run.**
**Against a gate that is defined but never called from `run_migrations`:** the first assertion fails
on the missing file, and the second fails because the migration applies anyway.
*The second is the one that matters: a gate whose failure does not STOP the migration is decoration,
and nothing in the previous row could tell the two apart.*

**(m3c) THE EXPECTED-TABLE SET IS PINNED AGAINST A REAL v37 DATABASE, NOT AGAINST ITSELF.** Assert
`PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES` **EQUALS** the table set measured off a freshly
migrated v37 database (`SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE
'sqlite_%'`). **Against a set that omits any of 0037's three tables --
`candidates_immutability_epoch`, `latch_order_mandate_links`, `fill_envelope_identity`
(`swing/data/migrations/0037_latch_order_mandate_links.sql:121`, `:289`, `:518`)** -- the equality
fails naming the missing member. *Derive the new constant as
`PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES | {the three}`, the deterministic-derivation shape the
Phase-8 set already uses (`swing/data/db.py:382`), so provenance is readable; then let this row
prove the derivation rather than trusting it.*

### (m4) Re-running the migration is a no-op

Run `run_migrations(target_version=38)` **twice**; the second call changes nothing (version stays
38, one `attempt_id` column, one index). **Pre-fix, and it is COMPUTABLE rather than "n/a"
(`A4-R1-9`):** the runner caps at `min(target_version, EXPECTED_SCHEMA_VERSION)`, which is 37 today,
so the version assertion reads **37** and the test fails on the first call. This is the standing
run-db-migrate-twice discipline.

### (m5) Existing rows survive and backfill to NULL

Seed three v37 trades, migrate to 38, assert all three rows are present with identical values and
their ids unchanged, and `attempt_id IS NULL`. **Pre-fix, COMPUTABLE (`A4-R1-9`):** the
`attempt_id` query raises `OperationalError: no such column: attempt_id`. **Post-fix if the
migration were a REBUILD rather than an `ADD COLUMN`:** this is the test that would notice a silent
id renumbering.

### (m6) DRIFT COMPARATOR #1 -- the CHECK text versus the Python constant

Read `SELECT sql FROM sqlite_master WHERE name = 'trades'` on a v38 database and assert it contains
**BOTH** `typeof(attempt_id) = 'text'` **AND** `length(attempt_id) = {ATTEMPT_ID_LENGTH}` built from
the Python constant. **Asserting only the length fragment would PASS THE DEFECTIVE DDL**
(`A4-R7-1`) -- the comparator would certify a CHECK that admits a BLOB, which is the one thing a
drift comparator must never do. **Post-fix:** passes. **Pre-fix / on drift:** changing either
representation alone fails, and dropping the `typeof` clause from the migration fails HERE. **MEASURED:** SQLite preserves
the `ALTER TABLE ... ADD COLUMN ... CHECK (...)` clause verbatim in the stored schema text, so this
comparator reads the real constraint and not a copy of it.

### (m7) THE TOKEN IS WRITE-ONCE -- asserted at the schema AND through the real corrector path

**Post-fix, half 1 -- the SCHEMA guard:** a direct `UPDATE trades SET attempt_id = <a VALID 36-char
token> WHERE id = ?` on a v38 database raises `sqlite3.IntegrityError` naming the trigger.
**THE VALUE IS CHECK-VALID SO THE TRIGGER IS ISOLATED FROM EVERY OTHER CONSTRAINT** -- and the
REASON first given for that was FALSE, which is worth recording because it was believed for two
rounds. `A4-R5-6` said `'x'` "trips the CHECK before reaching the trigger"; **MEASURED, it does not:
a BEFORE UPDATE trigger fires FIRST, so both an invalid and a valid value abort with the trigger's
own `immutable` message.** A valid token is still the right choice -- it removes any doubt about
WHICH constraint refused -- but the discriminator is not the CHECK ordering; it is the
**MUTATION PROOF** (remove the `CREATE TRIGGER`, show this RED), which is why the proof gates Task 1
rather than decorating it.

**Post-fix, half 2 -- the CORRECTOR path, and it asserts the TYPED error:** driven through
`swing/trades/reconciliation_auto_correct.py`'s tier-2 operator-truth path with
`field_name="attempt_id"`, the correction is refused with the **typed refusal from Task 1b -- NOT a
raw `sqlite3.IntegrityError`** -- and the row's token is unchanged. Asserting the TYPE is the whole
point of CHARC's condition: an `IntegrityError` surfacing from a trigger IS the authorize-then-abort
shape, so a test satisfied by it would ratify the defect.

**Pre-fix (the column with no trigger and no refusal -- what the first three drafts specified):**
both halves succeed, and the second is the reachable one: an operator correction re-assigns a
rolled-back token to a different trade in the same ticker, and the settle then confirms a row this
attempt did not write. **Half 2 is the load-bearing one** -- the direct UPDATE proves the trigger
exists; only the corrector path proves it covers the writer that actually reaches it, and only the
TYPE assertion proves the operator is told why.

### (m8a)-(m8d) THE CORRECTOR REFUSES `attempt_id` -- typed, order-independent, DELIVERED, and on EVERY OPERATOR SURFACE

**FOUR named rows** (three from `A4-R7-3`, which caught Task 1b's test classes having no ids, no
pre-/post-fix values, no exact result shapes and no files; **the fourth added by `A4-R9-5`**). They
are separated from (m7) because **their red base is different**: at Task 1b, Task 1's trigger already
exists, so the pre-fix behaviour is a raw `sqlite3.IntegrityError` -- **not** (m7)'s older
"both writes succeed" world.

**(m8a) SERVICE -- the typed refusal.** Drive the tier-2 operator-truth path with
`field_name="attempt_id"`. **Pre-fix (Task 1 landed, Task 1b not yet):** `sqlite3.IntegrityError`
from the trigger. **Post-fix:** exactly `ImmutableJournalFieldError`, the row's token unchanged, and
the message naming the column as WRITE-ONCE IDENTITY that no surface writes.

**(m8b) ORDER-INDEPENDENCE -- the preflight half.** A MULTI-FIELD correction with an ordinary field
FIRST and `attempt_id` LAST. **Post-fix:** the refusal is raised by
`_preflight_reserved_transitions` before any write, **ZERO journal `UPDATE` statements are issued**
(counted on an instrumented connection), and no correction or audit row is written. **Against a
backstop-only implementation** (the check only in `_update_journal_field`): the ordinary field's
UPDATE has already executed when the refusal fires, and the statement count is non-zero -- which is
the key-order dependence the module's own comment says it was restructured to eliminate.

**(m8c) DELIVERY through the UNCHANGED callers -- the half that makes this CHARC's condition rather
than a type change.** Both mappings were read at the source:
- **CLI** (`swing/cli.py:3941`): `ValueError` -> `click.UsageError` -> **exit code 2**, the refusal
  message on stderr, **no traceback**.
- **WEB** (`swing/web/routes/reconcile.py:1670`): `ValueError` -> **status 400** with the message in
  the error band and the operator's submission preserved.
**Pre-fix:** `ImmutableJournalFieldError` deriving from bare `Exception` (the shape `A4-R6-6`
caught) reaches NEITHER handler -- an uncaught CLI traceback and a web 500. **The assertions are the
exact exit code and the exact status**, not merely "not success": a weak delivery row would pass on
any non-success result and would certify nothing about legibility.

**(m8d) THE TIER-3 OVERRIDE PATH -- the surface the preflight never reached** (`A4-R9-5`). Drive
`apply_tier3_override` with an `operator_truth_value` of TWO keys, an ordinary journal field FIRST
and `attempt_id` LAST, against a correction row whose `affected_table` is `trades`.
**Post-fix:** exactly `ImmutableJournalFieldError`; on a connection instrumented with
`set_trace_callback`, **ZERO `INSERT INTO reconciliation_corrections`, ZERO `UPDATE
reconciliation_corrections`, and ZERO `UPDATE trades` statements were issued** -- the refusal
precedes step 4.
**Against a backstop-only implementation (the check in `_update_journal_field` alone -- i.e. exactly
what Task 1b shipped before this row existed):** the SAME typed error is raised and the SAME
persisted state is observed, **because the public entry point's own ROLLBACK erases the
difference** -- so a state-only assertion certifies a backstop-only implementation and this row
would be vacuous. **The statement counts are the discriminator, and they read `>= 3` there** (the
correction INSERT, the supersession UPDATE, the first field's UPDATE). *This is the counterfactual
requirement applied to a rollback: when the outcome is identical by construction, assert the work
that was done, not the state that survived.*
**A second arm, on the module's own documented composition surface:** call
`_apply_tier3_override_inner` directly inside a caller-held transaction (its docstring's invitation),
then roll back nothing and read the table. **Post-fix:** zero `reconciliation_corrections` rows.
**Against backstop-only:** a correction row EXISTS and the prior head's
`superseded_by_correction_id` has MOVED -- persisted, because on this surface nobody rolled back.
**Pre-fix (Task 1 landed, Task 1b not yet):** `sqlite3.IntegrityError` from the trigger, after the
same writes.

**Files:** `tests/trades/test_22a4_corrector_refusal.py` (m8a, m8b, **m8d**) and
`tests/web/test_routes/test_22a4_corrector_refusal_delivery.py` + the CLI half in
`tests/cli/test_22a4_corrector_refusal_cli.py` (m8c). **Task 1b's declared first red is (m8a)'s
`sqlite3.IntegrityError`.**

### (r1) The repo writes the token

`insert_trade_with_event(conn, trade, event_ts=..., attempt_id=TOK)` on a v38 database ->
`SELECT attempt_id FROM trades WHERE id = ?` returns `TOK`. **Pre-fix:** `TypeError: unexpected
keyword argument`.

### (r2) A pre-v38 schema DROPS the token and still inserts

On a v37 database, the same call inserts the row, returns an id, and logs a contained WARNING.
**AND A SECOND VARIANT WITH A RAISING LOG HANDLER, because the first does not test containment at
all** (`A4-R7-9`): `swing/data/repos/trades.py` has **no logger and no containment helper today**, so
a plain `log.warning(...)` would satisfy the first variant and **abort the transaction** when the
sink raises -- failing a money-bearing entry for an identity nicety, which is precisely what S7.5's
reason forbids. **Task 1 therefore specifies the containment explicitly** (the same
contain-and-continue shape as `entry.py`'s `log_contained`, or a local equivalent; the repo may not
import the entry service).
**Post-fix, both variants -- AND THE ASSERTION IS WHAT THE v37 DATABASE CAN ACTUALLY ANSWER**
(`A4-R8-3`: the previous text asserted `attempt_id IS NULL` **on a v37 database, where SQL naming
that column raises `OperationalError: no such column`** -- the migration is what creates it, so the
declared post-fix value was impossible and Task 1 could not have reached its declared green):
**row count 1, the insert returned an id, and `PRAGMA table_info(trades)` does NOT contain
`attempt_id`.** If the NULL reading is wanted, it is a SECOND step -- migrate that same database to
v38 and then assert the legacy row reads NULL -- and it is written as such rather than folded into
the v37 assertion. **The alternative implementation this excludes** is one that raises: that
would make the identity apparatus able to FAIL an entry, which S2.1's whole containment posture
forbids, and the consequence of dropping is exactly today's behaviour (the probe is schema-aware and
answers ABSENT, so the caller re-raises as it does today).

### (r3) A malformed token is refused BEFORE any write

**SEVEN malformed values, and the last three are the ones `A4-R9-1` added:** `attempt_id=""`,
`attempt_id="short"`, a 37-character string, **a 36-BYTE `bytes` value**, **a 35-character string
followed by an embedded NUL (`"0" * 35 + "\x00"`)**, **a 36-character string containing a LONE
SURROGATE (`"\ud800" + "0" * 35`)**, and **an UPPERCASE canonical uuid4 string**
-> `ValueError` from the repo, and `SELECT COUNT(*) FROM trades` is **0** (the row-count half is what
distinguishes a pre-write guard from a post-write one).
**The `bytes` case pins the `isinstance`
half of the validator** (`A4-R7-1`): a 36-byte `bytes` passes a bare `len(...) == 36` in Python
exactly as a BLOB passes `length()` in SQLite, so a length-only validator would let it through to
the CHECK -- or, on a tree whose CHECK is also length-only, all the way into the index.
**THE THREE NEW CASES EACH DEFEAT A DIFFERENT LAYER, WHICH IS WHY THREE AND NOT ONE** (`A4-R9-1`):
- **NUL:** Python `len` = 36, SQLite `length()` = **35**, so the value clears the old predicate and
  is refused by the **CHECK**, as an `IntegrityError` raised from inside the money-bearing INSERT.
- **LONE SURROGATE:** Python `len` = 36 and it never reaches the CHECK at all -- `sqlite3` raises at
  **PARAMETER BINDING**, a layer BELOW the CHECK that a plan reasoning only about the CHECK cannot
  see.
- **UPPERCASE:** it satisfies the CHECK and BINDS cleanly, and is refused only by the
  canonical-round-trip clause. It is here because `'A...'` and `'a...'` are DIFFERENT text keys, so
  a mint that ever returned upper-case hex would defeat `ux_trades_attempt_id` -- the index S7.8
  says catches a live duplicate -- **silently, with every other assertion in this suite green.**
**Against the OLD `isinstance(str) and len == 36` predicate:** the first four still fail correctly
and **all three new cases PASS the validator**, then produce, respectively, an `IntegrityError` from
the CHECK, a binding error, and a silently index-defeating row. **That is the discrimination: the
row is not "more cases", it is three layers the old predicate could not reach.**
**Pre-fix, concretely rather than "n/a":** `insert_trade_with_event` has no `attempt_id` keyword, so
the call raises `TypeError` for all seven.

### (r7) THE PROBE IS SCHEMA-AWARE -- asserted directly, on a v37 database

**Why this row exists (`A4-R8-5`): nothing tested it.** `(r2)` exercises only the WRITE side's drop;
`(f)` never reaches the probe because there is no database path; every settlement row runs on v38.
**So an implementation that unconditionally executes `WHERE attempt_id = ?` passes the entire suite:**
`_settle_by_attempt_identity` contains the resulting `OperationalError`, re-raises the original
commit error, and every high-level assertion still holds -- while the advertised schema-aware ABSENT
branch does not exist and S7.5's stated consequence ("the probe answers ABSENT, so the caller
re-raises as it does today") is untested.

**Post-fix:** on a v37 database, `find_trade_id_by_attempt_id(conn, tok)` returns **`None`, WITHOUT
raising**. **Pre-fix / against the unconditional implementation:** it raises
`OperationalError: no such column: attempt_id`. **The distinction is not cosmetic:** the suite must
be able to tell ABSENCE from INTERNAL PROBE FAILURE, because those two produce the same caller-facing
outcome and only one of them is the designed behaviour.

### (r4) DRIFT COMPARATOR #2 -- the schema versus the model

`{c for c in PRAGMA table_info(trades)} - {f.name for f in dataclasses.fields(Trade)} ==
{"risk_policy_id_at_lock", "attempt_id"}`, with the reason for each member in the test's docstring.
**EQUALITY, NEVER A SUPERSET CHECK -- CHARC made this the MANDATORY member of the mirror set**
(2026-09-06): *"the one mirror that defends the set."* A `>=` or subset form would silently absorb the
next column added without a decision, which is precisely the failure the comparator exists to catch,
and it is the same softening the LOCK-A docstring refuses one section over.
**Post-fix:** passes. **Pre-fix:** the set is `{"risk_policy_id_at_lock"}` (MEASURED today), so the
test fails on the current tree and passes only once the column exists -- and it fails again the day
a third column is added without a decision. This is the mandatory comparator of the mirror set: the
one mirror that does not depend on choosing the right grep.

### (r5) STATIC CLOSURE CHECK -- every entry INSERT carries the column

Walk every `INSERT INTO trades` statement in `swing/` (string constants via `ast`, plus a raw-text
scan for the dynamic-SQL family, so the walk cannot be defeated by an f-string). **THE TABLE NAME IS
MATCHED AS A TOKEN WITH A WORD BOUNDARY, AND `__pycache__` IS EXCLUDED** (`A4-R7-6`): a raw substring
also matches `INSERT INTO trades_new` -- the Phase-7 rebuild, a different table -- which the walk
would otherwise report as an unreasoned fifth writer and fail on. Historical migration rebuild
statements are classified explicitly rather than left to the substring. Then assert each
EITHER names `attempt_id` OR is on a **THREE-member REASONED EXCLUSION list**, each cited by the
schema era it serves.

**The counts, corrected (`A4-R1-4` -- the first draft said "two excluded" and "three statements ...
makes four" in the same paragraph, which is both wrong and self-contradictory).** Read off
`swing/data/repos/trades.py`: the existing branches are **v27+ (`:246`), v21-v26 (`:305`) and
pre-v21 (`:369`)** -- THREE. Adding the v38 branch makes **FOUR statements: ONE carrying the column
and THREE reasoned era exclusions.**

**Post-fix:** four statements, the assertion passes. **Pre-fix:** three statements, none carrying
the column, so the assertion fails on the carrying-branch requirement.

**THE MUTATION PROOF IS PART OF THE TASK, IS RUN, AND IS SHOWN RED IN BOTH DIRECTIONS:**
(1) remove `attempt_id` from the v38 INSERT column list -> the test must fail;
(2) add a fifth `INSERT INTO trades` statement that neither carries the column nor is on the
exclusion list -> the test must fail. Direction (2) is the one that matters for the future, because
it is how a new writer would actually arrive. Per the recipe, the fix is not the list -- it is the
closure check that walks what the code actually contains and asserts every item is on the list or
on the reasoned exclusion list, and it is a STATIC walk rather than a runtime trace because a trace
only sees the branches a fixture happened to take.

### (r6) The IntegrityError mapping no longer mis-labels -- **RD's attached pin for S7.7 half A**

**THIS ROW IS LOAD-BEARING FOR A DIRECTOR'S RULING, which is why it asserts a POSITIVE TYPED SURFACE
rather than the absence of noise** (RD, 2026-09-06). S7.7 half A's "loud AND legible" holds only in
combination with S2.5's narrowing, so the narrowing gets a discriminating pin.

Two rows with the same non-NULL token through `record_entry`'s own inner path ->
**`sqlite3.IntegrityError` propagates, and the assertion is on its TYPE and its MESSAGE**
(`UNIQUE constraint failed: trades.attempt_id`) -- **NOT on the absence of
`DuplicateOpenPositionError`.** A row written as *"no `DuplicateOpenPositionError` was raised"* would
**pass an implementation that raised nothing at all**, which is the vacuous-negative shape this
project has been caught by before; asserting the typed surface cannot pass that way.
And a genuine same-ticker open duplicate still raises `DuplicateOpenPositionError` naming the ticker.

**Pre-fix (the loose match plus the new index):** the first case raises
`DuplicateOpenPositionError("Already an open position in AAA (race-detected)")` **over a ticker with
no open position** -- loud, and mislabelled as the position race S7.7 half A depends on it not being.
**MEASURED:** both SQLite messages, so the assertion is written against the real strings.

---

### (RD-a1) THE PROBE IS NOT CALLED WHEN THE ROLLBACK RAISED

**THREE fixtures, because a rollback can fail in TWO ways and RETURN-WITHOUT-EFFECT in a third, and
each admits or refuses the probe differently** (`A4-R2-7` added the second; `A4-R7-8` added the
third; `A4-R8-2` caught that this paragraph still said "TWO" and that Task 4 still scheduled only
"BOTH shapes", which would have permitted omitting the ONLY fixture that discriminates round 7's
re-read correction):
**(a)** a proxy whose `commit()` raises and whose `rollback()` raises WITHOUT taking effect -- the
transaction stays open, the row stays pending;
**(b)** a NEW combined proxy -- `commit()` raises WITHOUT landing, and `rollback()` performs the
REAL rollback and THEN raises -- so the transaction is RESOLVED and the row is gone while
`cleanup_raised` is True. **The existing `_RollbackAfterEffect`
(`tests/trades/test_22a_task9_entry_wiring.py:3039`) CANNOT be reused for this** (`A4-R3-3`,
verified at the source): its `commit()` commits normally and returns, so `record_entry` succeeds and
its raising `rollback()` is never reached. Making the BODY fail instead is not equivalent either --
`result` stays `None` and the settle gate refuses at condition 0, before `cleanup_raised` can
discriminate anything. The new proxy borrows `_RollbackAfterEffect`'s rollback half and
`_CommitNeverLands`'s commit half.
**(c)** a THIRD fixture whose `rollback()` RETURNS NORMALLY while leaving `in_transaction` TRUE --
the arm no earlier fixture covered (`A4-R7-8`). **Post-fix:** `resolution` reads `"still_open"` (the
state RE-READ, not inferred from the call returning) and the probe count is **0**. **Against the
pseudocode this replaces**, which assigned `"rolled_back"` whenever the call returned: the resolution
is misclassified and **the probe is ADMITTED** -- a read let in under a falsely clean label.
`_durability_probe` is monkeypatched to a sentinel that RECORDS calls.

**Post-fix:** `record_entry` raises; **the sentinel's call count is 0**; `outcome.cleanup_raised`
is True and `outcome.resolution` reads `"still_open"` (the state RE-READ, not inferred).
In shape **(b)** the same assertions hold with `resolution == "rolled_back"` and `cleanup_raised`
True -- **the read is refused because the CALL raised, not because the transaction is open.** That is
rule (i) taken literally, and shape (b) is the row that proves the gate reads both fields rather than
inferring one from the other.
**Pre-fix (the naive implementation this excludes -- one that probes whenever the commit is lost):**
the count is 1 in both shapes. **Against the first draft's single-field gate:** shape (b) would be
labelled `"unresolved"` on a resolved transaction, so the state model would be wrong even where the
outcome happened to be right. RD's rule (i) is closed by an assertion instead of by the comment that
R10-02's own site carried while the next line walked past it.

*Teardown:* the writer's transaction is rolled back in a `finally` so the temporary database is not
left locked for the rest of the module.

### (RD-a2) THE PROBE NEVER RECEIVES THE WRITER'S CONNECTION

**`swing.trades.entry.find_trade_id_by_attempt_id` is monkeypatched** -- the name AS BOUND IN THE
CONSUMING MODULE, not at its definition site (`A4-R4-7`). `entry.py` imports its repo functions
directly (`entry.py:14`), so patching `swing.data.repos.trades.<name>` would rebind a name the
service no longer consults, and the capture would silently record nothing. **Task 4 additionally
requires the import to stay in that established style** (it moved there with its first consumer when
Task 2 was withdrawn -- `A4-R8-6`), so the patch target and the code style are
pinned together rather than one drifting from the other. The patch captures the connection object it
is handed. Drive the (c) fixture (commit raises with the row landed).

**Post-fix:** the captured object **is not** the writer's connection, and it is a
`sqlite3.Connection` opened on the same path. **Pre-fix (the R10-02 shape -- reading on the writer's
own handle):** the captured object IS the writer's connection. This is the half of VISIBILITY that
is closed by construction, and it is pinned so a later refactor cannot quietly re-introduce the
convenience of "we already have a connection right here".

### (RD-a3) R10-02 REPRODUCED -- a pending row is never reported durable

**Fixture:** commit raises without landing; `rollback()` raises **before taking effect**, so the
writer's transaction stays OPEN with the entry row PENDING.

**Post-fix:** `record_entry` RAISES (the cleanup error chained from the write error); no
`EntryResult` is returned; **a FRESH connection sees `COUNT(*) = 0`** for the ticker -- which is the
sharpest part of the row, because it shows that the false SUCCESS in R10-02 came specifically from
reading the WRITER's own connection and not from any property of the ledger.
**Pre-fix (the reverted clause-2 helper, and any implementation that reads on `conn`):** the read
observes the writer's own uncommitted row and returns SUCCESS carrying a "DURABLE" warning over a
merely-pending row.

### (RD-a4) THE PREDICATE'S FOUR-ROW MATRIX, EACH CELL COMPUTED UNDER BOTH PATHS

**REBUILT 2026-09-07 FROM A ONE-ROW PIN INTO A FOUR-ROW MATRIX (RD, on `A4-R11-2`), AND THE REASON
IS AN INCIDENT RATHER THAN A PREFERENCE.** The previous version of this row pinned ONE case -- the
ambient-`except` false positive -- and asserted it as a declared COST. When the orchestrator ran
RD's validity pin for that ruling it executed the `inside_except=False` leg only and reported the
result as confirming a scope argument that was entirely about the `inside_except=True` leg. **RD's
words, kept because they name the obligation: *"That rule's violation is exactly how the one-row pin
passed a false premise to me; the repaired test is the apology that compiles."*** So the row is now
a MATRIX over the two independent axes -- `inside_except` and `chained` -- **and every cell asserts
the predicate's output under BOTH the pre-fix and the post-fix predicate**, which is the recipe's
compute-it-under-both-paths rule applied to a truth table rather than to a single number.

**THE AXES.** `inside_except`: whether `record_entry` is called with a live handled exception on the
thread (`sys.exc_info()[1] is not None`, ASSERTED ON THE FIXTURE ITSELF so a fixture that stops
establishing the ambient context fails loudly instead of turning cells green). `chained`: whether
`__exit__`'s own rollback ALSO failed -- the proxy shape (k4a)/(k4b) specify, raising the rollback
error from inside the `except` handling the commit error, so `__context__` is set by the interpreter
exactly as `_PyErr_ChainExceptions1` sets it.

**THE MATRIX. MEASURED BY EXECUTION 2026-09-07, CPython 3.14.2 / sqlite3 3.50.4** -- these are the
values the test asserts, not values derived from the source:

| # | `inside_except` | `chained` | `escaping.__context__` | is it `ambient`? | **PRE-FIX** (bare `__context__ is not None`) | **POST-FIX** (base slot, non-None, `is not ambient`) |
|---|---|---|---|---|---|---|
| 1 | False | False | `None` | -- | **False** | **False** |
| 2 | False | True | the COMMIT `OperationalError` | no | **True** | **True** |
| 3 | **True** | False | the ambient `ValueError` | **yes** | **True** -- THE FALSE POSITIVE | **False** -- the amendment's whole subject |
| 4 | **True** | True | the COMMIT `OperationalError` | no | **True** | **True** |

**READ THE MATRIX AS A DISCRIMINATOR, WHICH IS THE ONLY REASON TO HAVE ONE:** rows 1, 2 and 4 are
IDENTICAL under both predicates, so **row 3 is the entire delta** -- and a matrix in which only one
cell moves is the honest statement that the amendment is narrow. **Row 4 is the row that proves the
nested case composes without a branch:** the ambient is live AND the rollback failed, and the
predicate still answers True, because `__exit__` chains the COMMIT error at the FIRST link and the
first link is the only one the predicate reads.

**WHAT EACH ROW ASSERTS THROUGH `record_entry`, not merely on the predicate:**
- **rows 1 and 3** (rollback OK): `outcome.cleanup_raised` is **False**, `_durability_probe` is
  called **ONCE**, and `record_entry` returns SUCCESS with the lost-commit warning over the durable
  row. **Row 3 is the one that would RE-RAISE under the pre-fix predicate**, and it additionally
  asserts `COUNT(*) = 1` on a fresh connection, because the cost of getting this wrong in either
  direction is measured against the ledger and never against the warning text.
- **rows 2 and 4** (rollback failed): `outcome.cleanup_raised` is **True**, the probe call count is
  **0**, `record_entry` RE-RAISES, and a fresh connection sees **0** rows.
- **every row** asserts `sys.exc_info()[1] is not None` (rows 3-4) or `is None` (rows 1-2) INSIDE
  the fixture before `record_entry` is entered.

**THE FIXTURE.** Rows 1 and 3 use the (c) shape -- deferred path, body completes, commit's own
return LOST, the row LANDED. Rows 2 and 4 use the (k4a) proxy. The `inside_except` axis is the same
call wrapped in `try: raise ValueError(...) except ValueError:`.

**THE PREDICATE'S OTHER AXIS -- THE SUBCLASS DATA DESCRIPTOR (`A4-R11-1`) -- IS (k7a)-(k7b), IN
TASK 3, AND NOT THIS ROW.** The base-slot read SHIPS in Task 3, so its discriminator belongs there;
scheduling it here would have left Task 3 green against `escaping.__context__` (`A4-R11-6`'s class,
caught by the inverse schedule check). The measurements are recorded here because this is where the
predicate's truth table lives, and (k7a)-(k7b) execute them. **MEASURED by execution 2026-09-07 on
the same interpreter:**

| subclass of `sqlite3.OperationalError` | base-slot `__context__` | **PRE-FIX** bare read | **POST-FIX** |
|---|---|---|---|
| `__context__` is a `@property` returning `None` | the real `OperationalError` | **False** -- a FALSE NEGATIVE that ADMITS the probe | **True** |
| `__context__` is a `@property` that RAISES | the real `OperationalError` | **raises `RuntimeError`, replacing the escaping exception** | **True** |

**Against the pre-fix predicate the first row ADMITS a probe on a wounded connection** -- the
`A4-R9-3` window, rebuilt -- **and the second replaces the operator's evidence with the attacker's
exception.** (k7a)-(k7b) drive both through `record_entry`, land their no-probe halves in Task 3,
and gain their probe-call-count-of-ZERO assertions in Task 4.

### (RD-a5) THE CALLER-SIDE OBLIGATION THE `body_completed` REMOVAL RESTS ON

**Why this row exists.** Removing the field is sound *only because* `record_entry`'s
`if result is None: raise` runs first. **That is a claim about the CALLER, and gotcha #31 is
explicit that a caller-side obligation is pinned by a test rather than described in a comment** --
the callee's absence is what the deleted field's tests would have pinned, and it is the wrong half.

**Fixture:** `_record_entry_inner` raises after its INSERT (the body-raised shape), on **BOTH**
paths -- `_reserve=True` and `_reserve=False`.

**Post-fix:** `result` is None, so the handler's FIRST branch re-raises; **`_durability_probe`'s
sentinel call count is 0** and `_settle_by_attempt_identity`'s is 0; what escapes is the BODY's own
exception with its type, args and `__cause__` unchanged; a fresh connection sees **0** rows.
**Against an implementation that moved the settle above the `result is None` branch** (the shape the
removal would be unsound under): the probe is called, and on the immediate path -- where the rollback
is the wrapper's own and `resolution` reads `rolled_back` -- the gate would reach the probe on a
transaction whose body never finished. **Pre-fix:** identical to post-fix, because the guard is
PRE-ARC -- **so this row is explicitly a LOCK, listed in the regression-control roster and not
counted as evidence that clause 2 works** (`A4-R1-8`'s separation, applied to a row this pass
added).

### (RD-b) A CONCURRENT INSERT TAKING OUR ROWID IS NOT CONFIRMED AS OURS

**Fixture:** a connection proxy whose `commit()` raises without landing, and whose `rollback()`
performs the real rollback and **then, on a SECOND connection, inserts a different trade** -- which
is issued the rowid our rolled-back attempt had just used (MEASURED: this is the default on a bare
`INTEGER PRIMARY KEY`, and it is also what `AUTOINCREMENT` would have done).

**Premise asserted first, so the test cannot pass for the wrong reason:** `SELECT ticker FROM trades
WHERE id = <our INSERT's lastrowid>` returns the OTHER ticker, and its `attempt_id` is not ours.

**Post-fix:** the probe is keyed `WHERE attempt_id = ?`, finds nothing, and `record_entry` re-raises
the ORIGINAL `OperationalError`; `SELECT COUNT(*) FROM trades WHERE ticker = <ours>` is **0**.
**Pre-fix (a rowid-keyed probe -- the reverted helper):** the read finds the OTHER row and returns
SUCCESS naming a trade the operator never entered. That is `22A-FIX-R10-03`, reproduced on this tree
rather than quoted, and killed.

### (RD-b2) THE DECLARED RESIDUAL, VERIFIED BY EXECUTION -- a rolled-back token CAN be re-minted

**Why this row exists:** `A4-R1-1` showed the plan's claim that the index makes a duplicate token
"impossible to commit" is FALSE for a token that was rolled back -- the index keeps no memory of it.
The design is unchanged (S2.0), the claim is rewritten, and the residual is DECLARED at S7.7. **A
declaration nobody executes is a claim, so this row executes it.**

**Fixture:** attempt A mints token `X` and its commit fails without landing; A rolls back, so `X`
exists nowhere. A second connection then commits a row for the SAME ticker carrying `X` (planted by
raw INSERT -- a `uuid4` collision is not reproducible, and the test's subject is the CONSEQUENCE of
one, not its likelihood). The probe then runs.

**Post-fix:** the probe **DOES** return that row and the settle would confirm it -- **and the test
ASSERTS exactly that**, with a docstring naming it as S7.7's declared residual, its arithmetic
(about `n^2 / 2^123`; ~1e-27 at `n = 10^5`), and the two independent conditions a real occurrence
would need (an RNG collision AND the same ticker). **Pre-fix:** the column does not exist.
**This test must be READ AS A DECLARATION, not as an aspiration:** if a future arc makes uniqueness
structural, this row is the one that must be inverted, and its failure is the notification.

### (c) A COMMIT WHOSE OWN RETURN WAS LOST, WITH THE ROW LANDED -> SUCCESS

**Fixture:** the module's existing `_RaiseAfterCommit` proxy (performs the REAL commit, then
raises), parametrised over BOTH paths -- on the latched path the raise comes from `commit()`, on the
pre-arc path from `with conn:`'s `__exit__`.

**Post-fix:** `record_entry` RETURNS an `EntryResult`; `result.trade_id` equals the id the probe
read; **exactly ONE** row exists for the ticker; `result.post_commit_warnings` contains an entry
naming the trade id and saying the commit's own return was lost, durability was confirmed by attempt
identity, and the entry must NOT be retried; the connection is not left in a transaction.
**Pre-fix (today's tree):** `sqlite3.OperationalError` propagates -- which is precisely what
`tests/trades/test_22a_task9_entry_wiring.py:3191` asserts today. **That test is this row's pre-fix
half; Task 4 REWRITES it in place rather than deleting it**, keeping its declaration prose as the
record of what changed and why.

### (c2) A REAL COMMIT FAILURE, NO PROXY

**Fixture, taken from MEASURED (3)/(3b) rather than invented:** a rollback-journal database, a
second connection holding an open READ transaction, and the entry's commit failing with `database is
locked`. Run on **both** paths, because MEASURED (3b) proved they differ.

**Post-fix, deferred path:** `__exit__` rolled back, so `conn.in_transaction` is **False**,
`resolution` reads `"not_needed"`, the probe runs on a fresh connection **and succeeds** (it is
blocked while the writer holds the PENDING lock and is not after resolution -- MEASURED (3)),
returns ABSENT, and the ORIGINAL `OperationalError` propagates; `COUNT(*) == 0`.
**Post-fix, immediate path:** identical outcome, reached through the wrapper's OWN rollback,
`resolution == "rolled_back"`.
**Pre-fix, both paths:** the same `OperationalError` propagates -- so the ESCAPING EXCEPTION does
not discriminate, and **the discriminating assertion is `resolution` plus the fact that the probe
ran and returned ABSENT** (captured via the same monkeypatch as RD-a1). Stated explicitly because a
row whose only assertion is "it raised" would pass on both trees.
*Why this row exists at all:* every other lost-commit row uses a proxy, and a proxy tests the
handler rather than the condition. This one produces the real condition, on the real context
manager, and it is the row that would have caught the first draft's `A4-R1-2` premise error.

### (d) A COMMIT WHOSE OWN RETURN WAS LOST, WITH THE ROW ABSENT -> RE-RAISE

The module's existing `_CommitNeverLands` proxy. **Post-fix:** the ORIGINAL exception's CLASS and
MESSAGE propagate (`sqlite3.OperationalError`, "database is locked"), `COUNT(*) == 0`, and
`conn.in_transaction` is False.

**AND THAT IS NOT ENOUGH, BECAUSE ALL THREE ARE ALSO TRUE ON TODAY'S TREE** (`A4-R3-7`; the first
draft answered this by naming a hypothetical naive implementation, which does not make the row
evidence for THIS arc). **The discriminating assertions are added:** the probe was called **exactly
once**, **with the minted token**, **on a connection that is not the writer's**, and it returned
`None`. **Pre-fix on the current tree:** there is no probe, so the call count is 0 and the row
fails. That also excludes an implementation which skips settlement entirely and re-raises by
accident -- which would otherwise look identical from the outside.

### (w) ONE TOKEN, END TO END -- mint to INSERT argument to probe argument

**Why this row exists (`A4-R2-4`): every other identity row plants a CONSTANT token, and a constant
masks the two defects that matter.** An implementation that minted separately for the INSERT and for
the settlement would pass every constant-token test and then, in production, probe for a token it
never wrote -- re-raising over every durable lost commit, silently, with the suite green. And no row
asserted that `record_entry` passes its OWN token to the repo at all: a correct repo (r1) plus a
`record_entry` that calls it with `attempt_id=None` and stamps later also passes.

**Fixture:** `_mint_attempt_token` monkeypatched to return a DIFFERENT valid 36-character value on
each call; `insert_trade_with_event` wrapped to capture its `attempt_id` keyword;
`find_trade_id_by_attempt_id` wrapped to capture the token it is handed. Drive the (c) lost-commit
fixture so all three points are reached.

**Post-fix:** the mint is called **exactly once**; the captured INSERT argument **equals** the minted
value; the captured probe argument **equals** the same value; and the persisted row's `attempt_id`
equals it too. **Pre-fix / against the two defective implementations named above:** the mint-count
assertion fails the double-mint, and the INSERT-argument assertion fails the disconnected one --
neither of which any constant-token row can see.

### (w2) THE MINT'S OWN CONTRACT -- that it draws from `uuid.uuid4` at all

**Why this row exists (`A4-R6-5`): every identity row including (w) monkeypatches
`_mint_attempt_token` ITSELF, so a production mint returning a CONSTANT valid 36-character string
passes all of them** -- and LOCK-A only checks that the token is valid and non-NULL. A constant mint
is precisely the systematic-reuse defect S7.8 says is deterministic rather than astronomical, and the
plan claimed (w) excluded it "by construction". **It did not.**

**Post-fix:** patch **`uuid.uuid4`** (one level BELOW the mint) with distinct sentinel UUIDs; assert
`_mint_attempt_token` calls the provider **exactly once per mint** and returns **exactly
`str(sentinel)`**; then drive **TWO attempts, the first rolled back**, and assert the second mint
produced a **DIFFERENT** token. **Pre-fix / against a caching or constant mint:** the second attempt
returns the first token and the row fails -- which no `_mint_attempt_token`-level patch can detect.
**S7.8's claim is narrowed to match:** (w) proves the token is threaded consistently; **(w2)** is
what excludes a reissuing generator, and neither makes reuse impossible *by construction* -- that
word belonged to the banked allocator and has been removed.

### (e) CO-DURABILITY, OBSERVED AT THE TRANSACTION BOUNDARY

> **Rewritten after `A4-R2-5`.** The first version asserted "committed row carries the token /
> rolled-back leaves none", and the reviewer showed that pair is satisfied by a LATE STAMP: commit
> the trade with no token, then `UPDATE` it in a second transaction. The committed half sees a
> token, the rolled-back half never reaches the update, and the test goes green over a design that
> violates the constraint it exists to prove. The observation has to happen at the boundary.

**Fixture:** a connection proxy whose `commit()` FIRST performs two reads and only then commits --
(a) on the WRITER's own connection, `SELECT attempt_id FROM trades WHERE id = ?`; (b) on a FRESH
connection, `SELECT COUNT(*) FROM trades WHERE attempt_id = ?`.

**Post-fix, at the boundary:** (a) returns the minted token -- the writer already holds it, so it
was written by the INSERT and not afterwards -- while (b) returns **0**, because nothing is durable
yet. **Post-fix, after the commit:** exactly one row, `attempt_id == TOK`, and the entry event, the
fill and the risk-policy stamp all present -- the token's presence coincides with the whole
transaction's.
**Post-fix, rolled back** (drive an entry whose body raises after the INSERT): `SELECT COUNT(*) FROM
trades WHERE attempt_id IS NOT NULL` is **0** and `COUNT(*) FROM trades` is 0.
**Against the LATE-STAMP implementation:** read (a) returns `None` at the boundary -- the row exists,
pending, with no token -- and the test fails there, which is precisely where it must.
**Pre-fix:** the column does not exist.

### (e2) THE IDENTITY APPARATUS CANNOT FAIL AN ENTRY

**ELEVEN CONTAINED-FAILURE VARIANTS PLUS ONE INTERRUPT-PROPAGATION CONTROL -- TWELVE SCENARIOS, AND
THE COUNT IS STATED ONCE AND ONLY ONCE.** (`A4-R6-9` caught the first version saying "six" and
enumerating seven; `A4-R6-4` then appended a "NINTH" beneath a heading still reading "eight
scenarios", so the same defect was live again one round later, in the fix for it. **The lesson
applied here rather than restated: the roster below is the manifest, and the number in the heading is
derived from it -- if they ever disagree, the roster wins and the heading is the bug.**)

**The eleven contained failures.** (1) `_mint_attempt_token` RAISES. It RETURNS: (2) `""`;
(3) `"short"`; (4) a 37-character string; (5) `b"..."` (bytes of some other length); (6) `None`;
(7) a 36-BYTE BLOB (`A4-R6-4` -- passes a bare length check); (8) a 35-character string plus an
embedded NUL; (9) a 36-character string containing a lone surrogate; (10) an UPPERCASE canonical
uuid4 string (**(8)-(10) added by `A4-R9-1`; each defeats a different layer -- the CHECK, the
parameter BINDING, and the UNIQUE index's text key -- and (r3) states which**). And (11)
`_resolve_main_db_path` RAISES.
**Plus (12), a CONTROL of the opposite polarity:** a `KeyboardInterrupt` from the mint PROPAGATES
and is not swallowed.

**The malformed-RETURN variants are the ones that matter**: without result validation in
`_begin_attempt_identity` (S2.1) the value reaches the repo, trips the pre-write `ValueError` that
(r3) requires, and FAILS AN ENTRY THAT WOULD HAVE SUCCEEDED -- the exact outcome the containment
exists to prevent, arriving through the containment's own blind spot. **And (8)-(10) are why S2.1's
validator is now `uuid.UUID`-parsing rather than length-checking**: under the old predicate those
three are not contained at all, they are ADMITTED, and the entry then fails inside the INSERT.
**Post-fix, all ELEVEN contained variants:** `record_entry` SUCCEEDS; the row is
present with `attempt_id IS NULL` (the raise and the nine malformed returns) or with a valid token but
no probe available (the path variant); and a WARNING is logged in each case.

**AND EACH OF THE TWO `<contained WARNING>` SITES IN `_begin_attempt_identity` IS ALSO RUN WITH A
RAISING LOG HANDLER** (`A4-R8-5`'s sibling `A4-R8-4`). Round 7 added hostile-sink coverage for the
REPO's pre-v38 warning and **left the SERVICE-side warning arms tested only with a working
logger** -- so a plain `log.warning(...)` at either of them passes every variant above and then, when
a handler raises, **converts a contained failure into a failed entry**, which is the precise claim
S2.1 makes and this row exists to defend. **Both arms route through ONE containment helper**
(so there is one thing to get right, not two), and each is asserted with a raising handler:
the entry still SUCCEEDS with the expected degradation.
**THE COUNT WAS THREE UNTIL 2026-09-07 AND THE FIX FOR `A4-R9-1` IS WHAT MADE IT TWO**
(`A4-R10-6`). S2.1 used to carry a SEPARATE arm for a malformed mint RETURN; collapsing that check
into the `validate_attempt_id` call inside the existing `try` merged two arms into one, and this
roster went on demanding coverage of a branch that no longer exists. **Read S2.1's pseudocode, not
this sentence, if they ever disagree: the sites are the `except Exception:` after the mint-and-
validate `try`, and the `except Exception:` after `_resolve_main_db_path`. TWO.** *A count in a test
roster is a manifest of branches, so a fix that removes a branch owes this roster an edit -- which
is the residual class this arc has now paid for at every level including its own bookkeeping.*
**Post-fix, the control:** the `KeyboardInterrupt` escapes and no row is written.
**Pre-fix (an uncontained implementation):** the exception escapes and a money-bearing entry fails
because an identity nicety was unavailable.
*Both variants also assert the exit condition of the containment: a `KeyboardInterrupt` from the
mint is NOT swallowed* -- the `Exception`-not-`BaseException` choice of S2.1, asserted rather than
described.

### (f) NO DATABASE PATH -> TODAY'S BEHAVIOUR

An in-memory connection (`_resolve_main_db_path` returns `None`) driven through the (c) fixture.
**Post-fix:** the ORIGINAL exception propagates; no crash inside the settle; a contained WARNING
records that the probe was unavailable. **Pre-fix (an implementation that assumes a path):**
`TypeError`/`OperationalError` from `open_connection(None)` -- a NEW failure mode introduced on the
lost-commit path, which is the one place a new failure mode is least welcome.

### (g) A RAISING PROBE LEAVES THE ORIGINAL EXCEPTION UNTOUCHED

`_durability_probe` monkeypatched to raise a distinctive exception.

**What `log_contained_note` ACTUALLY does, because the first draft of this row described it wrongly**
(`A4-R4-5`, verified at `swing/trades/entry.py:251-315`): it EMITS the message through the logger and
attaches a note to the escaping exception **only when the logging SINK itself raises**. With a
working logger there is no note. The helper is still the right one -- the probe failure IS reported,
the escaping exception's evidence IS preserved across the whole sequence, and a failing sink is
itself surfaced -- but the assertion has to match.

**Post-fix, working sink:** the ORIGINAL commit exception escapes with its **type, `args`,
`__cause__` and `__context__` unchanged**, and an ERROR record naming the probe failure was emitted.
**Post-fix, RAISING sink:** same exception, same evidence, **plus** a note recording the sink
failure. **Pre-fix (an uncontained probe):** the probe's exception replaces the commit's and the
caller is told about a probe rather than about the entry. This is the R11-03 property applied to the
code this arc adds -- asserted on the IDENTITY of what escapes, never on "no crash".

### (h) THE PROBE CONNECTION IS NOT SHARED-CACHE

**The PRAGMA is executed INSIDE the monkeypatched repo reader, while it still owns the LIVE probe
connection, and only the scalar is stored** (`A4-R2-8`: the first draft said "capture the connection
as in RD-a2 and then query it", which runs against a connection `_durability_probe` has already
closed in its `finally`).
**Post-fix:** the stored scalar is 0. **Pre-fix, concretely:** `_durability_probe` does not exist,
so the monkeypatch target cannot be imported -- this pins the construction-time precondition that makes "a fresh connection sees only committed state" TRUE rather than assumed,
without adding a runtime branch that would be defensive dead code.

### (pr1)-(pr5) THE PROBE'S FIVE DESIGN REQUIREMENTS, EACH WITH AN ASSERTION THAT DISTINGUISHES IT

**Why this block exists (`A4-R11-7`, plus `A4-R11-10`).** S2.3 states five properties of
`_durability_probe` as design decisions -- a bounded busy timeout, a contained close, ticker
corroboration, a token precondition, and (as of 2026-09-07) a fail-closed open -- **and four of them
had no row in this roster that would go red if they were dropped.** A design decision with no
discriminating assertion is a paragraph, and this plan's own standard for a paragraph is that it
does not ship.

**(pr1) THE BUSY TIMEOUT IS BOUNDED, AND THE BOUND IS CAPTURED.** Monkeypatch
`swing.trades.entry.open_connection` (the name as bound in the CONSUMING module -- (RD-a2)'s rule)
and record its kwargs. **Post-fix:** it receives `busy_timeout_ms=_PROBE_BUSY_TIMEOUT_MS`, and the
constant is **2000**. **Against an implementation that simply omits the kwarg:** the call carries
`DEFAULT_BUSY_TIMEOUT_MS`, **30000** (`swing/data/db.py:92`) -- *a lost-commit probe that hangs a
money-bearing web submit for thirty seconds, on a path whose fallback is the alarm anyway.* The row
asserts the NUMBER and not merely that some timeout was passed, because a silent restoration of the
project default is exactly the shape a value-free assertion cannot see.

**(pr2) A `close()` THAT RAISES AFTER A SUCCESSFUL READ DOES NOT DISCARD THE READ.** The
monkeypatched repo reader returns the row normally; the probe connection's `close()` then raises.
**Post-fix:** `_durability_probe` returns the row, `record_entry` settles, and SUCCESS is returned
with the lost-commit warning; the close failure is reported through `log_contained_note` on the
escaping exception rather than replacing anything. **Against a naive `finally: probe.close()` with
no containment:** the close's exception propagates out of the `finally`, the valid result is thrown
away, and `record_entry` re-raises **over a durable entry** -- which is clause 1's own subject
arriving inside the machinery built to serve it. *(g) is the neighbouring row and is NOT the same
one: (g) drives a probe that fails to READ; this one drives a probe that read SUCCESSFULLY and then
failed to tidy up, and only this ordering distinguishes "contained close" from "contained probe".*

**(pr3) THE RIGHT TOKEN ON THE WRONG TICKER IS THE ALARM -- AND S7.7's SAME-TICKER BOUND RESTS ON
THIS ROW.** Plant, by raw INSERT on a second connection, a committed row carrying OUR token with a
DIFFERENT ticker. **Premise asserted first:** the probe's returned tuple's ticker is not
`req.ticker`. **Post-fix:** `_settle_by_attempt_identity` returns `None`, `record_entry` RE-RAISES
the original, and an ERROR record names the mismatch. **Against an implementation that omits the
corroboration** (S2.4 condition 4's second half): the settle SUCCEEDS and returns a trade id for a
ticker the operator did not enter. **Every other row in this roster would pass that
implementation**, which is the finding's sharp edge: the accepted limitation at S7.7 bounds the
false-confirm probability by requiring an RNG collision **AND** the same ticker, and without this
row nothing in the suite holds up the second conjunct.

**(pr4) NO TOKEN -> NO PROBE.** Drive the (c) shape with the mint contained-failed, so
`attempt.token is None` while the database path resolved (the `e2` apparatus-cannot-fail-an-entry
path produces exactly this). **Post-fix:** `_durability_probe`'s sentinel call count is **0**,
`record_entry` re-raises. **Against an implementation whose condition 3 checks only the database
path:** the probe runs with `attempt_id = None`, and `WHERE attempt_id = ?` bound to `NULL` matches
nothing in SQL -- **so the defect is INVISIBLE in its outcome and visible only in the call count**,
which is why this row asserts the count rather than the result.

**(pr5) THE PROBE CANNOT CREATE A DATABASE** (`A4-R11-10`, VERIFIED AT THE CODE). Point the resolved
database path at a name that does not exist. **Post-fix:** the URI open raises
`sqlite3.OperationalError: unable to open database file`, the failure is CONTAINED,
`record_entry` re-raises the ORIGINAL, **and no file exists at that path afterwards**.
**Pre-fix (a bare path handed to `open_connection`):** `sqlite3.connect` CREATES the file
(`swing/data/db.py:126`), the probe answers ABSENT, and the arc has written a zero-table database
onto an already-failing money path **by the mechanism whose entire purpose is to observe without
acting.** The no-file assertion is the discriminating one; the exception type alone is not, because
a created-then-empty database also produces no row.

### (i) THE BELT IS STILL THE BELT -- a CONTROL, not a fix

After a settled SUCCESS from (c), a second `record_entry` for the same ticker raises
`DuplicateOpenPositionError` naming the ticker. **Post-fix and pre-fix: identical.** It is here so
the belt is not mistaken for the fix and so the arc cannot silently weaken it: what CHANGED is that
the operator is now TOLD the entry exists, so the retry that the belt refuses should no longer
happen.

### (j) THE POST-COMMIT-STEP PATH IS UNCHANGED

`outcome.committed` True with a later failure -> the existing degraded warning text, byte for byte,
and no lost-commit warning. **Post-fix and pre-fix: identical.** A regression control on 22-A3's
shipped clause-1 behaviour, because S2.4 edits the handler both branches run through.

### (k) THE DEFERRED PATH OBSERVES ITS OWN RESOLUTION -- it does not perform it

> **Rewritten after `A4-R1-2`.** The first draft asserted `in_transaction is True` pre-fix and
> proposed adding a rollback. MEASURED (3b) says otherwise: `sqlite3.Connection.__exit__` rolls back
> when its own commit fails, so `in_transaction` reads **False** on both trees. The row that would
> have gone green against a false premise is replaced by the one that measures the real thing.

`_CommitNeverLands`-shaped failure on the **pre-arc** path (the commit raises without landing).

**Post-fix:** `conn.in_transaction` is **False** afterwards (unchanged from pre-fix -- Python did
that, not this arc); `result` is not None inside `record_entry`, `outcome.committed` is False, and
**`outcome.resolution == "not_needed"`**; nothing partial is visible to a fresh connection; the
ORIGINAL exception propagated. **Pre-fix:** `_CommitOutcome` has no `resolution` field at all, so
the assertion raises `AttributeError`. **The discriminator is the OBSERVATION, not the connection
state** -- which is the honest statement, because the connection state was never this arc's to fix
on that path.

### (k2) THE DEFERRED PATH'S EXCEPTION IDENTITY IS UNCHANGED -- a LOCK assertion

> **Also rewritten after `A4-R1-2`,** and its polarity is INVERTED: the first draft declared a
> behaviour change here and routed it to CHARC. There is no change to declare, so this row now pins
> the ABSENCE of one.

> **REWRITTEN 2026-09-07 for the `_read_resolution` SPLIT** (`A4-R11-3`, `A4-R11-4`). The previous
> version drove *"the residual `_observe_resolution` rollback arm"*. **There is no such arm** -- the
> deferred path performs no rollback -- so the fixture that named it is replaced by the one that
> produces the same flag through the only route left.

Drive the pre-arc path with the (k4a) proxy: the body completes, `__exit__` raises a commit error,
performs the REAL rollback, and then raises a rollback error from inside the `except` handling the
commit error, so `__context__` is set by the interpreter.

**Post-fix:** the exception `__exit__` produced escapes UNCHANGED -- **not** re-wrapped, **not** a
chained `raise ... from ...` added by us -- with its type, args, `__cause__` and `__context__`
exactly as Python left them; `outcome.cleanup_raised` is True; **and the deferred path emitted NO
log record and issued NO rollback of its own** (assert the caplog handler saw nothing from this
module, and that the proxy's `rollback` call count did not increase after `__exit__` returned).
**Pre-fix:** the original escapes too (there is no observation at all) -- so **the discriminating
assertion is `cleanup_raised is True`**, and the other three are LOCKS. They fail an implementation
that copies the immediate path's `raise cleanup_error from write_error` onto the deferred path
(which the first draft would have shipped) **and one that keeps this sweep's retired retry arm**
(which the settling sweep DID ship, and `A4-R11-3` caught).

**THE ROW IS SPLIT ACROSS TWO TASKS, AND SAYING SO IS THE POINT** (`A4-R9-7`, generalised -- the
finding named Task 3's (k3b)/(k4a)/(k4b), and this row has the same defect one assertion deep).
The version before that also asserted *"and the probe is NOT called"*, naming a ZERO call count among
its discriminating assertions. **`_durability_probe` does not exist until Task 4**, so that
assertion cannot be written in Task 3 and the row as specified could not have gone green there.
**Task 3 ships (k2) with the observation assertions above. Task 4 ADDS the probe-call-count-of-ZERO
assertion to the same test**, where the sentinel it patches exists. Both task lists say so.

### (k5) THE CHAINED SIGNAL IS DETECTED -- the Task-3 discriminator for `_exit_rollback_failed`, with NO probe

**Why this row exists (`A4-R10-3`, and it is that finding's structural fix rather than its
workaround).** `_exit_rollback_failed` ships in Task 3, and every OTHER row that touches it --
(k4a), (k4b) -- also asserts a probe call count, so all of them need Task 4's `_durability_probe`.
**Task 3 would therefore have gone green against `def _exit_rollback_failed(e): return False`.**
This row is the assertion that does not need the probe: it asserts the SIGNAL, in the task that
ships the code producing it.

**Fixture:** the (k4a) proxy exactly -- deferred path, body completes, `__exit__` raises a commit
error, performs the REAL rollback, then raises a rollback error **from inside the `except` handling
the commit error**, so `__context__` is set by the interpreter as `_PyErr_ChainExceptions1` sets it
(SOURCE (S1)). **The fixture's own chaining is asserted first**
(`type(escaping.__context__) is sqlite3.OperationalError`), for the reason (k4a) gives.

**Post-fix:** `outcome.resolution == "not_needed"` (the rollback took effect, so `in_transaction`
reads False) **AND `outcome.cleanup_raised is True`** -- the two together are the point, and since
the `_read_resolution` split (`A4-R11-4`) the deferred path has **no rollback arm at all**, so
**the flag can only have come from the chained exception.** *That used to be a property of this
FIXTURE (the retry arm happened not to run on it); it is now a property of the CODE, which is a
strictly better thing for a discriminator to rest on.* `record_entry` re-raises; a fresh connection sees **0** rows.
**Against `return False`:** `cleanup_raised` is False with `resolution == "not_needed"` -- the
`A4-R9-3` admitting state, which in Task 4 becomes a live false-confirm window. **Against the
`isinstance(sqlite3.Error)` predicate RD removed:** identical here (the context IS a `sqlite3.Error`),
which is correct -- this row discriminates PRESENCE of the detection, and **(RD-a4) is the row that
discriminates the two predicate SHAPES.**
**Pre-fix:** `_CommitOutcome` has no `cleanup_raised` field, so the assertion raises `AttributeError`.

### (k6a)-(k6b) THE IMMEDIATE PATH'S OBSERVATIONS, DISCRIMINATED IN TASK 3, WITH NO PROBE

**Why these rows exist (`A4-R11-6`), and the reason is the sweep's own rule failing on the other
path.** Task 3 ships the IMMEDIATE path's observation semantics -- the returning-arm re-read
(`rolled_back` vs `still_open`) and `cleanup_raised` from the wrapper's own rollback -- and every
row that discriminated them, (RD-a1)'s three fixtures, was scheduled wholly in **Task 4**, because
those rows also assert a probe call count. **So a naive Task-3 implementation that assigned
`rolled_back` whenever `rollback()` returned would reach Task-3 green**, which is precisely the
condition Task 3's own scheduling rule was written to forbid: *every task ships only code for which
an assertion IN THAT TASK distinguishes the shipped implementation from its naive substitute.* The
settling sweep applied that rule to the DEFERRED path -- splitting (k5) out for exactly this reason
-- **and never asked the same question of the IMMEDIATE one.**

**These rows need NO probe and NO `record_entry`.** They drive `_entry_transaction` DIRECTLY with an
explicit `outcome=_CommitOutcome()`, which is the wrapper's own contract and is entirely Task-3
material; the connection PROXIES they use are test helpers that name no production symbol, and
(RD-a1) reuses them in Task 4. *That is the general answer to the class: when a row cannot be
scheduled with its code because its discriminator names a later symbol, look for the discriminator
that does not -- do not move the code.*

**(k6a) THE RETURNING ARM THAT DID NOT TAKE EFFECT.** `immediate=True`; a proxy whose `commit()`
raises without landing and whose `rollback()` **RETURNS NORMALLY while leaving `in_transaction`
True`**.
**Post-fix:** `outcome.resolution == "still_open"` and `outcome.cleanup_raised is False`; the write
error propagates unchanged.
**Against the naive substitute** -- assigning `"rolled_back"` whenever `rollback()` returns:
`resolution` reads `"rolled_back"`, which in Task 4 ADMITS the probe under a falsely clean label.
**Pre-fix:** `_CommitOutcome` has no `resolution` field, so the assertion raises `AttributeError`.

**(k6b) THE ROLLBACK THAT TOOK EFFECT AND THEN RAISED, AND THE LADDER THAT MUST SURVIVE IT.**
`immediate=True`; the proxy performs the REAL rollback and THEN raises.
**Post-fix:** `outcome.cleanup_raised is True` **and** `outcome.resolution == "rolled_back"` -- the
two are different facts and the row asserts both; **and what escapes is the CLEANUP error with the
WRITE error as its `__cause__`** (`raise cleanup_error from write_error`), with the existing
took-effect cleanup message present in the logs.
**Against a naive substitute that infers the state from the raise** (`"still_open"`, or the first
draft's `"unresolved"`): the resolution assertion fails on a transaction that is resolved.
**AND AGAINST THE SHAPE `A4-R11-4` IS ABOUT** -- routing the immediate path through a shared helper
that CONTAINS its rollback failure: the escaping exception is the WRITE error with no `__cause__`,
and the row goes red. **That is the assertion which makes "the shared thing is the non-mutating
read, never the rollback" a test rather than a paragraph.**
**Pre-fix:** no `cleanup_raised` field -> `AttributeError`; the chained-escape half passes pre-fix
and is therefore a **LOCK**, listed as such and not counted as evidence that the observations work.

### (k7a)-(k7b) THE SUBCLASS-DESCRIPTOR ROWS -- **the base-slot read's Task-3 discriminator**

**Why these are their OWN rows and not two lines of (RD-a4)** (`A4-R11-6`'s class, found by the
strengthened `assertion_schedule_audit.py` **on this fix leg's own edit**, 2026-09-07). `_CONTEXT_SLOT`
and the base-slot read ship in **Task 3**, and the two subclass rows that discriminate them were
written into (RD-a4), which is scheduled in **Task 4** because its four matrix cells assert probe
call counts. **So Task 3 would have gone green against `escaping.__context__`** -- the exact
`A4-R11-1` defect, in the task that ships its fix. *The instrument that caught it is the inverse
check added in the same pass: "does the task that SHIPS a symbol contain any row that NAMES it?" It
had never been asked, and its first run indicted the pass that added it.*

**The split is (k5)'s and (k2)'s, applied again:** the halves that need no probe land in Task 3; the
probe-call-count halves are ADDED to the same tests in Task 4.

**(k7a) A `__context__` DATA DESCRIPTOR THAT LIES.** A `sqlite3.OperationalError` subclass whose
`__context__` is a `@property` returning `None`, raised as the rollback failure from inside the
`except` handling the commit error, so the real `OperationalError` IS in the base slot.
**Premise asserted first:** `BaseException.__dict__["__context__"].__get__(e, type(e))` is the
commit error while `e.__context__` is `None` -- *the fixture asserts the divergence it exists to
exercise, so a future CPython that closed the hole turns this row red instead of vacuously green.*
**Post-fix (Task 3):** `outcome.cleanup_raised is True` and `outcome.resolution == "not_needed"`.
**Against the bare attribute read:** `cleanup_raised` is False -- **a FALSE NEGATIVE, and in Task 4
that state ADMITS the probe and rebuilds the `A4-R9-3` window.**
**Task 4 ADDS:** `_durability_probe`'s sentinel call count is **0**.

**(k7b) A `__context__` DATA DESCRIPTOR THAT RAISES.** The same shape with a getter that raises
`RuntimeError`.
**Post-fix (Task 3):** `outcome.cleanup_raised is True`, and **what escapes `record_entry` is the
SUBCLASS instance with its own type and args** -- not the getter's `RuntimeError`.
**Against the bare attribute read:** the getter fires, its `RuntimeError` propagates, and the
operator's evidence about what actually failed has been replaced by the hostile exception. **That
second assertion is the discriminating one**; `cleanup_raised` alone cannot distinguish the two
implementations here, because the bare read never returns at all.
**Task 4 ADDS:** the probe call count of **0**.
*Note what these rows do NOT prove: the base descriptor runs no user code, so the getter never fires
under the shipped read and the ALARM-direction `except` arm in `_exit_rollback_failed` is NOT
exercised by either row. No construction found in this pass makes
`BaseException.__dict__["__context__"].__get__` raise. The containment is kept for the direction it
costs nothing to have and is declared UNTESTED rather than counted as covered.*

### (k4a)-(k4b) THE DEFERRED PATH'S TWO ROLLBACK-FAILURE SEQUENCES -- **the SIGNAL and the OUTCOME, both pinned**

**REWRITTEN 2026-09-07 for RD's `A4-R9-2` ruling (Branch A).** These two rows were written when the
plan believed `__exit__`'s rollback failure was UNOBSERVABLE, so they pinned only the OUTCOME. It is
observable (SOURCE (S1), MEASURED (6)), rule (i) is literal on this path, and **each row now asserts
BOTH: that the failure was DETECTED and that the probe was consequently NOT RUN.** *Keeping only the
outcome assertions would leave two rows that pass against an implementation with no detection at
all -- which is precisely the shape they were written under and must no longer certify.*

**THE FIXTURE FIDELITY REQUIREMENT, STATED BEFORE THE ROWS BECAUSE IT IS THE PRECONDITION FOR BOTH.**
The commit-fail arm cannot be driven natively (MEASURED (6a): the post-commit-failure rollback makes
ZERO progress-handler callbacks, and MEASURED (5): a `factory=`-installed Python `rollback()` is
never invoked by the C `__exit__`). **So both rows use a connection PROXY whose `__exit__` stands in
for CPython's, and a proxy that does not reproduce the chaining tests the proxy rather than the
code.** The proxy's `__exit__` MUST therefore raise the rollback error **from inside an `except`
block handling the commit error**, so that `__context__` is set by the interpreter exactly as
`_PyErr_ChainExceptions1` sets it in the branch SOURCE (S1) anchors (`connection.c:2399`, a
convenience against the UPSTREAM-pinned bytes SOURCE (S1) names by digest and URL):

```
def __exit__(self, exc_type, exc, tb):
    try:
        raise sqlite3.OperationalError("commit failed")     # the COMMIT error
    except sqlite3.OperationalError:
        <perform, or do not perform, the real rollback>
        raise sqlite3.OperationalError("rollback failed")   # __context__ is set here
```

**A test asserting this shape is part of the row, not a note about it:** each row asserts
`type(escaping.__context__) is sqlite3.OperationalError` **on the fixture itself** before asserting
anything about `record_entry`, so a proxy that silently stops chaining fails loudly instead of
quietly turning both rows green against a broken predicate. *This is the synthetic-fixture-vs-real-
emitter discipline applied to an interpreter behaviour rather than to a data shape: the emitter here
is CPython, and SOURCE (S1) is what the fixture is derived FROM.*

**(k4a) THE INTERNAL ROLLBACK TAKES EFFECT AND THEN RAISES.** The proxy performs the REAL rollback
and then raises. **Post-fix:** `conn.in_transaction` reads False so `_read_resolution` records
`resolution == "not_needed"`; **`_exit_rollback_failed` returns True and `outcome.cleanup_raised` is
True**; S2.4 condition 2 refuses; **`_durability_probe`'s sentinel call count is 0**; `record_entry`
RE-RAISES, and what escapes is the ROLLBACK's exception with the COMMIT's as its `__context__`
(Python's own behaviour, unchanged by this arc). A fresh connection sees **0** rows for the ticker.
**Against the pre-ruling shape in this same plan** (`resolution="not_needed"`, `cleanup_raised=False`):
the flag is False, the probe call count is **1**, and the probe reads ABSENT -- so the OUTCOME is the
same and **only the two new assertions discriminate.** That is the whole reason they are here: the
outcome-only version of this row certified the admitting implementation.
**And it is the row that closes `A4-R9-3`:** with the probe not run, there is no window in which a
concurrently-committed colliding token can be read and confirmed.

**(k4b) THE INTERNAL ROLLBACK RAISES BEFORE TAKING EFFECT -- the WOUNDED CONNECTION.** The proxy
does NOT roll back and raises; the writer's transaction stays OPEN holding its lock.
> **REWRITTEN 2026-09-07 for the `_read_resolution` SPLIT** (`A4-R11-3`, `A4-R11-4`): the retry arm
> this row described is GONE, and with it the "either route" hedge.

**Post-fix:** `_read_resolution` sees `in_transaction` True and records `resolution ==
"still_open"`, **issuing no rollback and no statement**; `cleanup_raised` is True **from the ONE
remaining route, `_exit_rollback_failed` on the chained exception**, and the row asserts that route
by ALSO asserting the proxy's `rollback` call count is unchanged after `__exit__` returned -- *the
previous version deliberately declined to say which arm set the flag, and there is now only one, so
declining would be hiding an assertion the code can support*; the probe's call count is **0**; the
ORIGINAL error surfaces; a fresh connection sees **0** rows.

**AND THIS ROW NAMES ITS OWN JOURNAL MODE, BECAUSE IT MAKES A FRESH-CONNECTION CLAIM WHILE THE
WRITER STILL HOLDS THE LOCK** (`A4-R10-4`'s rule, applied to the one row in this suite that had
dropped its blocking claim without noticing it still had a blocking-SENSITIVE assertion; found while
rewriting the row, 2026-09-07). The fixture database is built through `ensure_schema` and the test
**asserts `PRAGMA journal_mode` reads `wal`** before the `COUNT(*)` read. In WAL the fresh reader
sees the pre-transaction snapshot and answers 0; on a `delete`-mode database the same read would
block to the busy timeout and then raise `database is locked`, and the row would be red for a reason
that has nothing to do with its subject.
**AND THE JOURNAL-MODE CLAIM IS GONE** (`A4-R9-6`). The pre-ruling version asserted that the fresh
probe *"BLOCKS OR FAILS"* against the held lock, citing MEASURED (3) -- **a ROLLBACK-JOURNAL
measurement, while the live database is INFERRED-WAL (S2.2's label, `A4-R11-12`), where
MEASURED (2) admitted a fresh reader against an
open write transaction.** Under Branch A the probe does not run, so the row makes no claim about blocking in either
mode and the generalisation disappears rather than being parameterised. **The fail-closed probe
behaviour it used to carry is not lost:** it is (g)'s subject (a raising probe leaves the original
exception untouched) and (c2)'s (a real `database is locked`, on an explicitly rollback-journal
database), and both name their mode.
**Against the pre-ruling shape:** the probe runs, and on a WAL test database it neither blocks nor
fails -- it succeeds and reads ABSENT -- so the assertion as written would have been **wrong on the
live mode and right only on the fixture's**.
**Against this sweep's retired retry arm:** the proxy's `rollback` call count is 1 rather than 0,
and the row goes red -- which is the assertion `A4-R11-3` says was missing.

**Both rows are DEFERRED-PATH ONLY** -- on the immediate path the wrapper issues the rollback itself
and `cleanup_raised` is a direct observation of its own call, which (RD-a1)'s three fixtures already
cover.

### (k3a)-(k3b) THE `committed` OBSERVATION IS INSIDE THE RESOLVING SUITE -- static AND runtime

> **Rewritten after `A4-R2-6`, which disproved this row's founding claim and then weakened its
> assertion.** The first version said the window "cannot be simulated"; it can, with a
> `sys.settrace` line hook. And its AST predicate -- "inside SOME `try` whose handlers cover
> `BaseException`" -- is satisfied by an unrelated or nested `try/except BaseException: raise` that
> records no resolution at all, so the test could have blessed the very window it was written to
> close.

**(k3a) STATIC, and it now has TWO branch-specific predicates, because the two branches close the
window in DIFFERENT places** (`SS-9`). Parse `swing/trades/entry.py` with `ast`.

- **IMMEDIATE branch:** every assignment to `outcome.committed` inside `_entry_transaction`'s
  `immediate` arm sits directly in the `Try.body` of a `try` **whose handler both (i) writes
  `outcome.resolution` (directly or through the shared `_read_resolution` call) and (ii)
  re-raises.** **Against the first draft's shape:** the assignment is outside the `Try` -> fails.
  **Against a nested-decoy shape:** the enclosing handler writes no resolution -> fails, where the
  earlier weak predicate ("inside SOME try covering `BaseException`") passed.
- **DEFERRED branch -- THE BYTE-LOCK, ASSERTED RATHER THAN PROMISED.** The `if not immediate:` arm
  contains **NO `Try` node at all**, and its `With` node's body is **exactly one `Expr` whose value
  is a bare `Yield`**. **Against every shape this plan has proposed for that branch and then
  withdrawn** -- a `body_completed` assignment inside the `with`, an enclosing `try/except`, an
  `except ... as` binding -- the assertion FAILS. *This is the one claim three separate sections
  made in prose for three rounds while the pseudocode contradicted it; it is now a test.*
- **RECORD_ENTRY's side of the deferred window, in the same walk -- AND IT IS SPLIT ACROSS THE TWO
  TASKS, BECAUSE HALF OF IT NAMES A FUNCTION TASK 3 DOES NOT SHIP** (`SS-14`; the schedule-by-
  assertion audit caught this row, added in the same pass that wrote the rule, breaking the rule).
  - **TASK 3's half:** inside `record_entry`'s post-commit handler, the `_read_resolution` call
    sits under a branch guarded by `not outcome.committed` and `not _reserve`, **after** the
    `result is None` raise. **Against an implementation that observes unconditionally:** the call is
    not under that branch -> fails, and that is the `SS-9` shape this row exists to lock out.
    **THIS HALF IS REACHABLE ONLY BECAUSE TASK 3 SPLITS THE GUARD** (`A4-R11-5`): with the shipped
    `if result is None or not outcome.committed: raise` intact there is no `not outcome.committed`
    branch for the call to sit under, so the assertion could not describe any shape Task 3 creates.
    The walk therefore ALSO asserts the split itself -- the handler's first statement is
    `If(test=Compare(result is None), body=[Raise()])` with no `or` in its test -- **which is the
    assertion that turns "the guard is split" from a checklist line into a red test.**
  - **TASK 4 ADDS:** the same walk asserts `_read_resolution` is LEXICALLY BEFORE the
    `_settle_by_attempt_identity` call. **`_settle_by_attempt_identity` does not exist in Task 3**,
    so the assertion cannot be written there -- it would either fail or, worse, pass VACUOUSLY on an
    empty match set. **Against an implementation that consults the gate before observing:**
    `resolution` reads `"unattempted"`, the gate refuses, and a durable entry
    is reported as a failure -- the `A4-R1-3` defect relocated rather than fixed, which is exactly
    what a caller-side obligation test exists to catch (gotcha #31).
  - *A vacuous PASS is why this split matters more than the earlier four instances of the class.
    (k4a)/(k4b) scheduled in Task 3 would have FAILED loudly on a missing patch target; an AST walk
    that finds no `_settle_by_attempt_identity` node finds no ordering to violate and reports
    success. **The failure mode of scheduling-by-artifact is not always a red test.**

**(k3b) RUNTIME, because it turns out to be reachable:** install a `sys.settrace` local trace hook
that raises a sentinel exception at the line of the deferred path's `outcome.committed = True`,
after the `with` has returned. **Post-fix:** the handler catches it, `resolution` reads
`"not_needed"`, `record_entry` settles by probe and returns SUCCESS over the durable row.
**Against the first draft's shape:** the sentinel escapes `_entry_transaction` uncaught,
`resolution` is `"unattempted"`, the settle gate refuses, and `record_entry` re-raises **over a
durable entry** -- the exact defect, demonstrated rather than argued. *Kept alongside (k3a) rather
than replacing it: the trace hook proves the behaviour at ONE line, the AST walk proves the property
for every assignment including ones added later.*

---


## S6. THE LIVE-MIGRATION GATE -- **operator-witnessed, POST-MERGE, and it is not optional**

**This arc bumps `EXPECTED_SCHEMA_VERSION`, and `connect()` REFUSES a database whose version does
not match** (`swing/data/db.py:2251-2256`). So the moment this merges, the operator's live v37
database is refused by every surface until `swing db-migrate` runs. That is not a side effect to be
discovered; it is the gate.

- **Nobody in this worktree touches the live database.** The executing implementer's tests all build
  their own `tmp_path` databases, and the plan author did not open it.
- **TWO BACKUPS ARE TAKEN AND THEY LIVE IN DIFFERENT PLACES -- the witness must not confuse them**
  (`A4-R1-7`, verified at the source). `swing db-migrate` takes its OWN general snapshot into
  `cfg.paths.backups_dir` and **prints that path** (`swing/cli.py:258-270`); it then calls
  `ensure_schema(db_path)` with **no** `backup_dir` (`:310`), so the ARC gate's backup defaults to
  `src_path.parent` -- the database's own directory, `~/swing-data/` -- and **its name is never
  printed.** The arc backup is the VERIFIED one: `_phase22_arc_a4_backup_gate` fires at exactly
  `current_version == 37`, writes `swing-pre-22a4-migration-<ISO>.db`, and checks it against
  `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES` before any statement of 0038 runs; on failure it
  raises `MigrationBackupRequiredException` and the source database is untouched. **Both are usable
  for recovery** (the general one is a full `Connection.backup()` taken immediately before), so the
  correction here is to the INSTRUCTIONS, not to the safety. Making the CLI print the arc backup, or
  route it through `backups_dir`, would touch `swing/cli.py` and is **out of envelope**; the
  underlying gap is BANKED at S8.
- **The witness steps, one at a time, each awaiting the operator's result** (the standing
  step-by-step rule -- a batched runbook collapses the gate into a self-report):
  0. **BEFORE MIGRATING -- record the BEFORE-IMAGE** (`A4-R1-6`; without it steps 3 and 4 compare
     against nothing): `SELECT version FROM schema_version`; `SELECT COUNT(*) FROM trades`;
     `PRAGMA table_info(trades)` (assert `attempt_id` is ABSENT, so step 3 is a real transition and
     not a re-read); `SELECT COUNT(*) FROM latch_order_mandate_links`; the FULL
     `SELECT id, ticker, state FROM trades WHERE state IN ('entered','managing','partial_exited')
     ORDER BY id`; **`SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE
     'sqlite_%' ORDER BY name`** (the INDEPENDENT before-image the backup is checked against at
     step 1 -- `A4-R11-8`: comparing the backup to "the expected set" checks the constant against
     itself, and a constant is exactly the thing that can be wrong); **and `PRAGMA journal_mode`,
     which SETTLES a claim this plan has been INFERRING** (`A4-R11-12`: Global Constraints says the
     live database was not opened by this plan, so "the live database is WAL" was read off a
     `tmp_path` database built through `ensure_schema` -- that establishes CONSTRUCTION behaviour,
     not this file's current mode). Report all seven.
  0b. **`ls ~/swing-data/swing-pre-22a4-migration-*.db` BEFORE migrating and record the result**
     (normally empty). Without this, step 1's `ls` is satisfied by a leftover file from a failed or
     earlier attempt and would CERTIFY A BACKUP THE GATE DID NOT TAKE (`A4-R3-8`).
  1. `swing db-migrate` -> report the printed version and the printed GENERAL backup path, then
     `ls ~/swing-data/swing-pre-22a4-migration-*.db` again and **identify the EXACTLY ONE path that
     is new relative to step 0b**. Open THAT file read-only (a COPY -- never through `ensure_schema`,
     which would migrate the recovery artifact away) and confirm `SELECT version FROM schema_version`
     is **37** and **its table set is byte-identical to step 0's `sqlite_master` list** -- the
     LIVE before-image, not the constant, so the check cannot pass by agreeing with the thing under
     test (`A4-R11-8`). A backup nobody opened is a filename, not a pre-image.
  2. `SELECT version FROM schema_version` -> 38.
  3. `PRAGMA table_info(trades)` -> `attempt_id` present; `SELECT COUNT(*) FROM trades` **equal to
     step 0's count**; `SELECT COUNT(*) FROM trades WHERE attempt_id IS NOT NULL` -> 0.
  4. `SELECT COUNT(*) FROM latch_order_mandate_links` **equal to step 0's**, and
     `SELECT id, ticker, state FROM trades WHERE state IN ('entered','managing','partial_exited')
     ORDER BY id` **byte-identical to step 0's list** -- ids included, because an `ADD COLUMN` must
     not renumber anything and this is the assertion that would notice if it had.
  5. `swing web` loads the dashboard and the trade-entry form renders.
  6. **The first real entry after the migration carries a non-NULL `attempt_id`** -- the only
     end-to-end proof that the token is being written on the production path, and the one step a
     seeded fixture cannot substitute for (the seeded-gate-masks-default-state lesson).
- **Rollback**, if step 3 or 4 disagrees: restore the pre-migration backup; the index is droppable
  in one statement and the column is nullable and inert.

---


## Global Constraints

- **ENVELOPE, as widened by CHARC's ruling of 2026-09-06.** The brief's text was
  `swing/trades/entry.py`, `swing/data/` (migration 0038, models, repo), tests -- **nothing in
  `swing/web/` or `swing/cli.py`**, which remains true and is why the warning this arc emits reaches
  the operator with no further caller work (verified at both sites: S1.5).
  **IT NOW ADDS EXACTLY ONE MODULE: `swing/trades/reconciliation_auto_correct.py`.**
  **CHARC's ground, and it is a ruling ABOUT this plan's own scoping:** *"I cannot rule the class
  binding one week and bank its next instance because the plan's envelope was drawn one module
  short."* The tier-2 corrector ADMITS `field_name="attempt_id"` today and the new trigger then
  ABORTs it, so the operator receives a raw `sqlite3.IntegrityError` -- **authorize-then-abort, the
  class he ruled on 2026-09-01 after five instances in 22-A.** The widening is bounded to the typed
  refusal and its test (Task 1b); **no other change to that module, and no sweep.**
- **RD'S THREE CONSTRAINTS ARE BINDING AND ARE NOT NEGOTIABLE BY THIS PLAN** (S1). If a design
  cannot satisfy all three, the plan STOPS and routes rather than designing around one.
- **THE LIVE DATABASE IS NOT TOUCHED.** It is at v37 with real money-bearing trades and four live
  latch links. This plan did NOT open it; the migration set on disk tops out at
  `0037_latch_order_mandate_links.sql`, whose final statement is `UPDATE schema_version SET version
  = 37` (read from the FILE). Every test in this plan builds its own `tmp_path` database. The live
  migration is an OPERATOR-WITNESSED, POST-MERGE gate (S6) and belongs to nobody in this worktree.
- **Branch:** all work on the arc branch; conventional commits (`feat(data):`, `feat(trades):`,
  `fix(trades):`, `test(...)`). **ZERO `Co-Authored-By`. No `--no-verify`. No amend.**
- **TDD:** failing test -> see it fail -> minimal implementation -> see it pass -> commit, one
  red/green cycle per task. **Every regression assertion is computed under BOTH the pre-fix and the
  post-fix path**, and this plan states both values for every test it specifies.
- **ONE MIGRATION, ONE VERSION BUMP, ONE ATOMIC FILE** (the 0037 header's own rule): the runner
  applies a version once and only when strictly greater than the database's current version, so
  anything added to `0038` after any database has recorded v38 never runs on that database again,
  silently, with CI green because fresh fixtures always apply the whole file.
- **`ruff check swing/` clean.** Test-file lint is out of scope; match each test file's existing
  style.
- **EVERY CITATION TO A FILE OUTSIDE THIS REPOSITORY IS ANCHORED ON CONTENT AND PINS THE FILE BY
  ITS UPSTREAM DIGEST TOGETHER WITH THE FETCH URL** (adopted 2026-09-07 from `A4-R10-5`;
  **AMENDED THE SAME DAY, RD-ratified, when the network fetch that closed `A4-R11-9` showed this
  rule's own worked example was breaking it**). A bare line number into a file no reader here can
  open is unverifiable, and this plan has already had one such citation confidently refuted with
  counter-line-numbers that were themselves unsourced. Cite the FUNCTION NAME and a VERBATIM
  fragment a reader can grep; give **the UPSTREAM digest and the URL it was fetched from**; keep
  line numbers as a convenience against the pinned bytes.
  **A LOCAL COPY'S DIGEST IS PROVENANCE OF THE READING, NEVER OF THE SOURCE -- and the failure is
  invisible, because the hash is real and it verifies.** SOURCE (S1) pinned `7487db46...` for two
  weeks; that digest was the hash of OUR copy, whose LF had been converted to CRLF by a text-mode
  write. It pinned WHICH BYTES WERE READ and said nothing about WHOSE they were, which is the exact
  gap this rule exists to close -- **so the rule as first written closed only half of it.** Two
  readers verified against that copy and were both right about the copy.
  **THE COROLLARY ON COUNTS: a line count is a CONVENIENCE, never a pin.** Three numbers have been
  asserted for that one file (2,532 / 2,717 / 2,718); the byte size and the digest never moved.
  Report a count with the METHOD that produced it (`wc -l` and `splitlines()` agree at 2,717 on a
  file ending in a newline; an editor showing a phantom trailing line reports 2,718).
  **The rule binds the code this plan ships too** -- `_exit_rollback_failed`'s docstring
  carries the content anchor, not the line range (Task 3).
  **AND IT HAS AN IN-REPO COROLLARY, ADDED THE SAME DAY BY THE SWEEP THAT FOUND FOUR IN-REPO
  ANCHORS WRONG AT ONCE (`SS-12`): every `file.py:N` citation NAMES THE SYMBOL it points at.** An
  in-repo line number is checkable, so it is weaker than the out-of-repo case -- but it DRIFTS,
  nobody re-checks it, and this plan carried a set of four that pointed into the wrong function
  entirely while their COUNT was correct. The symbol is what survives an edit; the number is a
  convenience. **The sweep's method was an AST walk, not a grep** -- a grep for `log\.` finds
  logging calls but cannot tell you which FUNCTION contains them, which is the fact the entry was
  making.
- **ASCII in user-facing strings.** The new warning text reaches the CLI's stderr through 22-A3's
  reader, and Windows cp1252 crashes on non-ASCII (`pytest` `capsys` hides it). The warning is
  ASCII by construction and is additionally passed through 22-A3's `ascii_safe` on the CLI side.

---

