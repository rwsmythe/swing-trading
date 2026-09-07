# 22-A4 EXECUTING — Task 0b + Task 1 dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.
**Worktree:** `.worktrees/22-a4-exec` — branch `22-a4-exec`, clean, **zero commits**. Your base is the
commit that adds this brief; **capture it yourself before your first commit** (`git rev-parse HEAD`) and
quote it in the return report. No SHA is hardcoded here, because the commit carrying this line would
have changed it.
**Plan of record:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md` (1,889 lines — the
EXTRACT, CHARC's ruling). **NOT** the 4,370-line design record. Do not redirect yourself to it.

---

## 1. SCOPE — Task 0b + Task 1, and nothing else

- **Task 0b** (extract `:129`) — the 22-A LOCK-A amendment. **It lands in Task 1's commit**, by the
  plan's own text. Not a separate commit.
- **Task 1** (extract `:164`) — the schema and every mirror, in one commit: migration 0038, the repo
  write/read, the version-mirror family, the `IntegrityError` narrowing.

**OUT OF SCOPE — do not start these, do not "while I'm here" them:**
Task 1b (the corrector's typed refusal), Tasks 3/4/5, the Codex review loop (it belongs between the
plan's Tasks 6 and 7, after the whole ladder), and **the live database** — migration 0038 is applied
only at an operator-witnessed POST-MERGE gate (extract S6, `:1761`). Nobody in a worktree touches it.

**Why the ladder is split here:** the round-0 cell reached 251,009 tokens on a premise census alone.
Task 1 is the mirror family across ~30 files. One task, one cell, returned while it can still be QA'd.

---

## 2. THE RULING PACKET — binding, and its FACTS are yours to verify at intake

Per `docs/implementer-dispatch-recipe.md` (byte-identical in your tree): **a ruling's REASONING is
binding; its FACTS are inputs you verify against the code at intake.** Two of four rulings on this arc
were corrected on their own facts, both caught by the implementing cell. The relay is a defect surface.
**If a fact below fails intake: STOP and route to me. Do not proceed on a corrected premise of your own
invention.**

### RULING 1 — `(m3c)` takes BRANCH A (CHARC, PRIMARY, 2026-09-07)

The plan demanded the expected-tables constant **EQUAL** a fresh v37 schema while prescribing a
derivation that yields **37 against 42 real tables**.

**The mechanic (verified on disk before this brief was written):** `swing/data/db.py:575` reads
`missing = expected_tables - actual_tables` — a **SUBSET** test. The gate's contract has always been a
**FLOOR**. The plan wrote a test against the instrument it imagined rather than the one on disk.
CHARC's reason: a pre-image with MORE tables is still a valid backup, so equality points the wrong way
— branch B would not widen the roster, it would **reverse the gate's direction**.

**Encoding:**

- `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES = PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES | {0037's three}`
  — **37**, the derivation exactly as the plan specifies. (`PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES`
  is at `swing/data/db.py:382`, consumed at `:2022` — both verified.)
- `(m3c)` asserts the constant is a **SUBSET** of the fresh-v37 set — **naming the offending member on
  failure** — **AND** that 0037's three tables are **MEMBERS**.
- Gate strictness **identical to 22-A's**. S6 step 1 unchanged in form.

**SUPERSEDED TEXT STILL ON DISK IN YOUR TREE — strike it:**

- `2026-09-06-phase22-arc-a4-EXECUTING.md:724` — the constant **EQUALS** the table set measured off a
  freshly-built schema.
- `2026-09-06-phase22-arc-a4-EXECUTING.md:925` — **"EQUALITY, NEVER A SUPERSET CHECK -- CHARC made this
  the MANDATORY member of the mirror set"**.

Strike the `:925` sentence **and its stated reason**. The ledger records the **supersession, citing this
ruling** — not a silent edit. The ruling is also readable in your own tree at
`docs/orchestrator-handoff-2026-09-07-22a4-executing.md:99,106`; reconcile the two sources and say so.

**BANKED TO CHARC'S REGISTER, NOT THIS ARC:** a schema-manifest drift comparator (fresh v(HEAD) table
set compared by EQUALITY against a committed manifest, updated in the same commit as any migration).
That is the equality the plan wanted. It lives beside the backup gate, not inside it. **Do not build it.**

### RULING 2 — rename ALL SIX mis-named version tests (orchestrator, my lane)

The plan names one. **Five more already document the opposite of what they check**, and this arc edits
all six bodies to 38, which makes the drift worse at every one. All five verified on disk at these exact
lines before this brief was written:

| file:line | current name | actually asserts |
|---|---|---|
| `tests/data/test_migration_0036_provenance_corrections.py:56` | `test_expected_schema_version_is_36` | 37 |
| `tests/data/test_migration_0036_provenance_corrections.py:60` | `test_migration_applies_and_stamps_version_36` | 37 |
| `tests/data/test_migration_0033.py:141` | `test_expected_schema_version_is_33` | 37 |
| `tests/data/test_migration_0031_untracked_broker_position.py:55` | `test_expected_schema_version_is_31` | 37 |
| `tests/data/test_migration_0030_yfinance_calls.py:33` | `test_expected_schema_version_is_30` | 37 |

The plan's own rule reads identically on all six: **the NAME must match, or the file documents the
opposite of what it checks.** One line each, zero behaviour change.

### THE THREE INTAKE CATCHES from round 0 — already corrected against code, no ruling needed

1. **`import sys` is not in `swing/trades/entry.py` at all** (zero hits in 1,516 lines) → **Task 3**
   adds it. Out of your scope; noted so you do not assume it is present.
2. The lone-surrogate token raises **`UnicodeEncodeError`, not a `sqlite3.*` error.** The plan's claim
   held; the **type** was wrong. Narrow the `IntegrityError` handling accordingly.
3. **Two `_current_version == 37` sites live in a file the plan never names** — its count was right,
   its roster was not. Grep before you trust the roster.

---

## 3. READ FIRST (the plan's own S10, `:23`)

1. The plan's **S1** — the only place the three constraints are tied to code.
2. `swing/trades/entry.py:628-1163` — `record_entry`, `_CommitOutcome`, the DECLARED-RESIDUAL block
   (`:973-1030`), both `_entry_transaction` paths.
3. `docs/22-a-merge-request.md` **S4.4**.
4. `docs/superpowers/plans/2026-09-02-phase22-arc-a3-record-entry-caller-half.md` **S7** — the
   limitation-declaration standard and the containment idiom this arc **reuses rather than re-invents**.
5. `CLAUDE.md` §Gotchas — **#9** (executescript / explicit BEGIN), **#11 and its 2026-08 amendments**
   (the mirror family is bigger than the canonical triple; **the comparator is the mandatory member**;
   **grep each enum member SEPARATELY, never the tuple**), the migration backup-gate **strict-equality**
   clause, the rolled-back-rowid entry, the writer-quoting-itself entry.
6. `swing/data/migrations/0037_latch_order_mandate_links.sql`'s header — the one-migration-one-version-bump
   rule and the reversibility-header format this arc copies.

---

## 4. BINDING CONVENTIONS

- **TDD, one red → green → commit per logical change.** See the red fail before writing the implementation.
- **Conventional commits**, task id in the subject: `feat(data): Task 1 — ...`.
  **No `Co-Authored-By` trailer** (a 4,574-commit streak). **No `--no-verify`. No amending.**
- Observable verification before each task commit, ERE mode (the `-E` is required or it silently
  returns empty): `git log -E --pretty="%s" --grep="^[a-z]+\([a-z]+\): Task 1"`
- Worktree CLI: `PYTHONPATH=. python -m swing.cli ...` — the bare `swing` entry point resolves to the
  editable install in the MAIN repo, not your tree.
- **Never open or migrate the live DB** (`~/swing-data/swing.db`). Tests use `tmp_path`.
- Ruff: `ruff check swing/` — baseline is E501-only; introduce no new violations.

## 5. VERIFICATION BEFORE YOU RETURN

1. **Full fast suite**: `python -m pytest -m "not slow" -q`. Baseline on your base is **12180 passed /
   13 skipped / 0 failed** — re-measure it and **READ the result**. Run pytest and ruff as **separate
   commands**: a chained `pytest ; ruff` reports ruff's exit code, and **exit 0 is not evidence pytest
   ran** (this cost a near-false-green on this arc a day ago).
2. `ruff check swing/ --statistics`.
3. Trailer audit: `git log --format="%(trailers:key=Co-Authored-By)" <your captured base>..HEAD` must be
   empty. Filter on the trailer KEY, not a text match on the block.
4. **Report an absence with the search that produced it.** "There is no X" requires saying what you
   searched and whether it could have found X.

## 6. RETURN REPORT (your final chat message — do NOT post to any mailbox)

- Commits landed (sha + subject), and what each red step actually asserted.
- **Intake result on each of the two rulings and the three catches** — verified, or corrected, with the
  evidence. Say explicitly how you reconciled the plan's `:724`/`:925` text against the ruling.
- The mirror-family roster you closed over, and **how you established it was complete** (per-member
  greps plus a READ, per gotcha #11 — a value-grep is provably insufficient here).
- Suite + ruff + trailer results, quoted.
- Anything you did NOT do, and why.
- **Your `tokens used` figure** (the arc's spend is being measured).
- Out-of-scope defects noticed: name them, do not fix them.

## 7. IF YOU GET STUCK

STOP and return with the specific question. A fork discovered mid-task stops the task and routes to me
— it does not get settled inside the work. You report to the orchestrator in chat and to no one else.
