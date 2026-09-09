# 22-A4 — the Reviewer-B fix leg (`B-1` + `B-3`)

**Audience:** a fresh implementer cell with no prior conversation context.
**Mission:** land two BOUNDED fixes that both directors have already ruled and prescribed, with their
discriminating tests, and stop. Nothing else.
**Expected size:** two commits plus a suite run. This is a small leg; its risk is not size, it is
SCOPE — two of the five constraints below are REFUSALS, and a leg that does more than this brief says
will be rejected at QA.

**Branch:** `22-a4-exec` (CONTINUE it — do not cut a new one). **Worktree:** `.worktrees/22-a4-exec`
(it exists; work in place). **Head at dispatch:** `0bbf825c`.
**Base SHA verified by the orchestrator at dispatch:** `2d9e4a34`. The five rules this brief leans on
were each confirmed PRESENT in THIS TREE's own copies of `docs/implementer-dispatch-recipe.md` and
`docs/harness-architecture.md` — a worktree carries the rules that existed when it was cut, so they
were checked here rather than assumed.

---

## §0 READ FIRST

1. **`docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.ledger.md`, the
   last three sections** — `REVIEWER B`, `CHARC'S RULING ON B-1`, `RD'S RULING ON B-3`. **Both
   rulings are literal block quotes.** They are your specification; this brief does not restate them
   in full and where this brief and a ruling differ, THE RULING WINS and you report the difference.
2. `swing/trades/reconciliation_auto_correct.py` — `_handle_single_field_correction` (~`:2716`),
   `_handle_operator_alternative` (~`:3431`), `_preflight_reserved_transitions` (~`:474`),
   `_update_journal_field` (~`:2235`). **Line numbers drift; ground on the SYMBOLS.**
3. `swing/trades/entry.py` — `_durability_probe` and its docstring.
4. `tests/trades/test_22a4_corrector_refusal.py` — especially the `(m8b)` rows, so you can see why
   they did not catch `B-1`, and `_seed_trade_anchored_world`, which takes `ambiguity_kind=`.
5. `tests/trades/test_22a4_attempt_identity.py` — test `(h)`, which `B-3` rewrites.
6. `CLAUDE.md` §Gotchas — the write-barrier/seeding entry and gotcha #11.

## §0.1 SKILL POSTURE

- **DO NOT run Codex. No adversarial round runs on this leg.** Both directors ruled it: CHARC —
  *"NO FIFTH COUNTED A ROUND"*; RD — *"No counted A round on B-3's account (scope-of-change rule)."*
  Do not invoke `copowers:*`, do not hand-run `codex exec`. **The orchestrator re-runs Reviewer B on
  your finished head** — that is not your job and you must not pre-empt it.
- Do NOT invoke `superpowers:brainstorming` or `writing-plans`. The design is settled by two rulings.
- **DO** use `superpowers:test-driven-development`. Every change here is red-first.
- **You never post to a mailbox.** Do not run `scripts/role_mail.py`. Do not address `charc` or `rd`.
  Your return report is your FINAL CHAT MESSAGE and nothing else.

---

## §1 TASK 1 — `B-1`: the whole-payload immutable refusal on the single-field path

**The defect, reproduced by the orchestrator at QA on a real migrated database:**
`_handle_operator_alternative` hands the WHOLE operator payload to
`_handle_single_field_correction`, which selects `field_name = next(iter(correction_target.keys()))`
and passes ONLY that key to the immutable guard inside `_update_journal_field`. The whole-payload
guard `_preflight_reserved_transitions` is called from exactly ONE production site,
`_handle_multi_field_correction`. So on the routed choice `("validator_rejected",
"operator_alternative")`, the payload `{"current_stop": 4.5, "attempt_id": <token>}` raised NOTHING,
returned `CorrectionResult(correction_id=1)`, wrote `current_stop`, left the token untouched, and
TERMINALIZED the discrepancy as `operator_resolved_ambiguity`. With the keys in the other order the
guard fires correctly. **The defect is key-order dependent.**

**CHARC's diagnosis, which is also the fix's justification:** the R3-03 leg already hoisted the
BYTE-EXACT gate (`_assert_real_column_names`) to whole-payload in this same function and left the
IMMUTABLE gate at first-key. *"Two gates in one function deciding over two different populations is
the defect; the fix makes them agree."*

### 1a. The change

In `_handle_single_field_correction`, call

```python
_refuse_immutable_journal_fields(affected_table, correction_target.keys())
```

over the COMPLETE payload, **immediately AFTER `_assert_real_column_names`** (byte-exact first, per
R3-03) and **BEFORE the `next(iter(...))` selection**. Same ordering as the two existing
whole-payload sites. Read those two sites and match their shape.

### 1b. The tests — `tests/trades/test_22a4_corrector_refusal.py`

Discriminating rows on the routed choice `("validator_rejected", "operator_alternative")`, driven
through `apply_tier2_resolution`, **in BOTH key orders**:

- `{"current_stop": 4.5, "attempt_id": OTHER_TOKEN}` — the trailing-key row
- `{"attempt_id": OTHER_TOKEN, "current_stop": 4.5}` — the leading-key row

Each asserts the typed `ImmutableJournalFieldError` **AND ZERO WRITES** — the closure shape the
R3-03 leg used, because *a refusal test that checks only the exception would have passed over the
persisted writes last time*. Zero writes means all of: no `reconciliation_corrections` row,
`current_stop` UNCHANGED at its seeded value, `attempt_id` UNCHANGED at `MINTED_TOKEN`, and the
discrepancy **still `pending_ambiguity_resolution`** — NOT terminalized. Use the statement-trace
helper the existing `(m8b)` rows use for the journal-UPDATE count.

Seed with `_seed_trade_anchored_world(conn, ambiguity_kind="validator_rejected")` — the existing
helper already takes that argument.

### 1c. Show the trailing-key row RED against the pre-fix tree

It reproduces today, so this is a **one-line witness, not an argument**: run that test before the fix
and record the actual failure output in your return report. Then make it green.

### 1d. **THE REFUSAL — read this twice**

**The fix must NOT reject payloads with more than one key, and must NOT change what happens to a
non-immutable extra key.** That is `B-2` — a PRE-EXISTING, OUT-OF-ENVELOPE defect (every payload field
after the first is silently discarded), banked to CHARC's register and explicitly NOT this arc's.
CHARC: *"A fix that closes `B-1` by closing `B-2` has widened the arc; refuse it at QA."* The
orchestrator will. If you believe `B-1` cannot be closed without touching `B-2`, **STOP AND ROUTE** —
do not decide it yourself.

**Nothing else in this function or this module.** No sweep.

---

## §2 TASK 2 — `B-3`: `cache=private` on the probe, and a test that measures what its name claims

**The defect:** `_durability_probe` opens `Path(db_path).resolve().as_uri() + "?mode=rw"` — no cache
parameter. Its docstring argues the construction-time precondition is *"pinned by test (h)"*; test
`(h)` is headed *"THE PROBE CONNECTION IS NOT SHARED-CACHE"* and its only assertion is
`PRAGMA read_uncommitted == 0`, which is not evidence of anything about cache sharing.

**RD's deciding reason:** the property currently holds by WRITER-ABSENCE — nothing in the repo enables
shared cache — which is *"a claim with a shelf life."* `cache=private` makes it a construction-time
guarantee for nine characters.

### 2a. The change

`_durability_probe`'s URI becomes `... + "?mode=rw&cache=private"`. **Nothing else in the function.**

**PREMISE ALREADY VERIFIED BY THE ORCHESTRATOR — do not re-derive it, but do confirm it at the code
in passing:** `swing/data/db.py::open_connection` passes `db_path_or_uri` straight into
`sqlite3.connect(db_path_or_uri, uri=uri, ...)` with no parsing, re-quoting or allowlist, and
`open_connection(<uri> + "?mode=rw&cache=private", uri=True)` was executed against a real migrated
database: it opened, `read_uncommitted` read 0, and the schema was readable. **If you nonetheless find
that `open_connection` rejects or mangles the parameter, that is a finding about `open_connection`
and NOT a licence to drop the parameter — STOP AND ROUTE** (RD pre-ruled this disposition).

### 2b. Test `(h)` is REWRITTEN, not appended

- Assert the **URI passed to `open_connection` carries `cache=private`** — spy the call, capture the
  URI string. That is the construction-time property the header names.
- **KEEP** the `read_uncommitted == 0` scalar as a second, **honestly-labelled** assertion: it is what
  the pragma reads under a private cache, and it is not evidence of cache separation.
- The test's header, its name and its failure message must say what it now pins. The current failure
  message claims the connection is not shared-cache readable; that claim must go.

### 2c. The docstring is corrected by REPLACEMENT

The `PRAGMA read_uncommitted IS NOT CHECKED AT RUNTIME, AND THAT IS A DECISION` paragraph in
`_durability_probe`: the precondition is now a construction-time URI parameter pinned by `(h)`'s URI
assertion. **The runtime-branch-is-dead-code argument STAYS — it is still true.** Replace, do not
append; this project's supersession rule is by replacement.

### 2d. **THE LOCK-A BASELINE MOVES, AND YOU MUST RECORD IT**

`_durability_probe` is one of THREE AST-locked functions. This is a **deliberate, named lock move**,
not an untouched claim. The old hashes, measured by the orchestrator across `a32ea9d5` → `84e90bab`
(all three IDENTICAL at that point) and recorded in the ledger:

| function | old sha256 of AST source segment | required after this leg |
|---|---|---|
| `_entry_transaction` | `c53b2786e3a7518d5c1341af399eeac9d4d8e16cc615c28d093e631c56240d69` (10,990 chars) | **UNCHANGED** |
| `_durability_probe` | `c16ea4656c1c2e415beb04f3a04f141719cfc60a793465eb5d9b4e70616c4914` (4,113 chars) | **MOVES** — diff must be the URI literal + the docstring paragraph ONLY |
| `record_entry` | `5b6aa7466175ff4c91448bf8dbb6f18f19b6a2974e12dfab20d2e1aa41710fb7` (25,939 chars) | **UNCHANGED** |

**Report the NEW `_durability_probe` hash beside the old one, and re-measure the other two and report
them as unchanged.** Measure by AST source segment (`ast.get_source_segment`), not by `git diff` —
`git diff --stat` on `entry.py` reads like a lock breach across this arc and is not one.

---

## §3 BINDING CONVENTIONS

- **Conventional commits.** `fix(trades): B-1 — ...`, `fix(trades): B-3 — ...`. **NO
  `Co-Authored-By` footer** (a 4,500+ commit streak). **No `--no-verify`. No amending.**
- Keep the final `-m` paragraph plain prose — a paragraph starting `Word:` is parsed by git as a
  trailer and pollutes the audit.
- **TDD: red first, and SEE the red.** Both tasks have a stated pre-fix behaviour; the tests must
  distinguish. A test that passes under both the pre-fix and post-fix path is worthless.
- Two commits (one per task) is the expected shape.
- `ruff check swing/` clean.
- The live database is NOT touched. Every test builds its own `tmp_path` database.
- **`-n auto` is memory-killed in some seats. Use `-n 4`** and say which you used.

## §4 THE SUITE GATE

Run the **full fast suite** — `python -m pytest -m "not slow" -q -n 4` — from the worktree, on your
final head, and report the exact numbers you read off that run. Since no Codex loop runs on this leg,
this is the binding verification. Fix any red before you return. If a red looks like the known
`tests/scripts/…::test_run_stub_skip_exits_zero` xdist LOAD flake, **reproduce it isolated with
`-n 0` first** — do not wave it away by citing the handoff.

## §5 IF YOU GET STUCK

**Stop and route** rather than deciding. Named stop-and-route triggers, all pre-ruled:
`B-1` seems to need `B-2`'s fix (§1d) · `open_connection` rejects the parameter (§2a) · a ruling and
this brief disagree (the ruling wins; report it) · a locked function other than `_durability_probe`
moves. Report in your final chat message; do not improvise past any of these.

## §6 RETURN REPORT (your final chat message — to the orchestrator only)

1. Per-task commits: SHA + subject, in shipped order.
2. **The `B-1` pre-fix RED** — the actual failure output of the trailing-key row against the pre-fix
   tree, quoted.
3. The new tests, by name, and for each: what it asserts and what it evaluated to **before** the fix.
4. **The LOCK-A table** — three functions, old hash and new hash, method stated.
5. `open_connection` confirmation (§2a) — what you found at the code.
6. Full-suite numbers read off the final run, plus `ruff`, plus the `-n` you used.
7. Anything you noticed and did NOT fix, with why — out-of-scope catches get a durable landing, so
   name them here rather than in passing.
8. Confirmation that you ran no Codex round and posted to no mailbox.
