# 22-A4 EXECUTING — the R3-03 structural leg + R3-04 + round 4 (dispatch brief)

**Audience:** a fresh implementer cell with no prior conversation context.
**Worktree:** `.worktrees/22-a4-exec` — branch `22-a4-exec`, clean at `df231195`. Capture your base
yourself (`git rev-parse HEAD`) and quote it. **Do not rebase.**

**Form of the ruling in §2: LITERAL BLOCK QUOTE of CHARC's posted body.** Not a re-setting. CHARC is
the author of every quoted clause; I am the courier. Role-mail is transport and `comms/` is
gitignored, so the operative text lives here, in git. (Convention: `orchestrator-context.md`
§"Posting to the directors", rule 4.)

## 0. WHICH COPY OF THE RULES GOVERNS YOU

Read the **MAIN-REPO** copies, not your worktree's:
`C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md` (**§3 is your review protocol**)
and `C:/Users/rwsmy/swing-trading/docs/harness-architecture.md`. **Main's copy wins on any
difference.** This brief lives at
`C:/Users/rwsmy/swing-trading/docs/22-a4-r3-03-structural-leg-dispatch-brief.md`.

**Plan of record:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md`.
**Ledger** (append to the executing section, do not start a second):
`docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.ledger.md`.
**Preserved evidence** (rounds 1–3, prompts, findings, `run_r3.sh`):
`~/swing-data/review-transcripts/22-a4-exec/`.

**Line anchors across this arc have drifted hard** — one earlier task's target moved ~600 lines.
**Ground on symbols and re-locate at read time.** The line numbers in §2 and §3 are as-measured on
`df231195` and are given so you can find the seam, not so you can trust them.

## 1. WRITTEN AUTHORIZATION FOR A FOURTH COUNTED ROUND

**Granted by the orchestrator, 2026-09-08, after reading the outgoing cell's depth (320,695).**

**The task-bearing finding that is the named ground: `A4X-R3-03`** — the resolved-name normalizer
misses three further column spellings, ruled **INTRODUCED** by CHARC (this arc's own code, Task 1b +
round-1 fix `74cb2815`, which claimed spelling coverage in its own subject).

This is a **fourth COUNTED round**, not a settling step. It is counted because R2/R3 below are **new
task-bearing work on the ruled surface**, not residuals of a previous fix's wording. **It opens only
AFTER R2 and R3 land** — one round, reviewing the final shape once, never its own wake.

**A FIFTH counted round would need a fresh written authorization naming its own task-bearing
finding, and you do not hold one.** If round 4 finds task-bearing work, **STOP and report the full
cumulative ledger.** **A stopped-short loop is a permitted, reportable outcome and is never
relabelled as convergence** — the outgoing cell did exactly this and it was the right call.

## 2. THE RULING — CHARC, 2026-09-08, PRIMARY. Literal block quote.

> ## R1. A4X-R3-03 is INTRODUCED, not banked. Default-to-introduced binds and the provenance is not even contested: the normalizer and the early immutable check are this arc's code (Task 1b, `74cb2815`), and the arc CLAIMED spelling coverage in `74cb2815`'s own subject. A coverage hole in a guard the arc built is the arc's, whatever the age of the delivery type behind it.
>
> ## R2. The fix shape, and it is structural, not three more spellings.
>
> The finding is the third and fourth spelling found after the first three were enumerated -- the
> enumeration IS the defect. SQLite's identifier grammar is not the corrector's to re-implement.
> The invariant to build: **the operator-supplied field name is validated BYTE-EXACT against
> `PRAGMA table_info` as the FIRST gate on every corrector path, before any check that INTERPRETS the
> name and before any write; every later check, the immutable membership included, compares the
> CANONICAL name only.** Once that holds, no non-canonical spelling survives to any later check, the
> normalizer is dead code, and it is DELETED (a resolver that exists so an earlier check can catch
> what a later byte-exact check would refuse anyway is the D46 shape: machinery defending an
> interface that should not have admitted the input). The cell finds the seam; I do not name the
> line. If `_assert_real_column_name` cannot run first because the early check has no connection at
> that point, that ordering constraint is the finding to route, not a reason to keep the normalizer.
>
> Closure test, red-first by the arc's mutation discipline: each of the SIX known non-canonical
> spellings (the three of R1 Major 3 and the three of R3-03) is refused with ZERO rows written --
> including tier-3 steps 4-5's rows -- which is also the execution that settles Codex's ordering
> claim. The existing (m8e) negative control (a different column whose name contains an immutable
> one) keeps passing.
>
> Legibility of the refusal that survives (`ReservedJournalFieldError`, bare `Exception`) stays
> D34's; the reason text is already right. That is the ONLY part of R3-03 that goes to the register,
> and it is already there as the third instance.
>
> ## R3. A4X-R3-04 (MINOR): fix in the fix leg, one line -- the docstring's `pre_version == (target - 1)` parenthetical becomes the implementation's own `current_version == 37 AND target_version >= 38`. The implementation is the Phase-9 canonical shape and is right. Post-verdict minor scope; the suite covers it; no round is bought by it.
>
> ## R4. Sequencing [...] R3-03 is a TASK-BEARING finding and is the named ground for a fourth counted round under the orchestrator's written authorization. [...] The round opens AFTER R2 and R3 land on the branch -- one round, reviewing the final shape once, never its own wake -- and the B pass then runs over the tree that carries both fixes plus RD's declaration wording (semantic bound, measured span as illustration).

**CHARC also recorded what he verified before ruling, and you should not re-derive it blind:** the
normalizer strips ONE matched pair from `[]`, `""`, backticks, then casefolds — single quotes,
parentheses and a leading comment are not in its set. What stands between the miss and a write:
`_assert_real_column_name` (byte-exact against `PRAGMA table_info`) and migration 0038's
`trg_trades_attempt_id_immutable` (`BEFORE UPDATE OF attempt_id`, which aborts every update of the
column regardless of spelling). **So the reachable defect he identified is the WRONG REFUSAL, not a
write** — the arc's typed, specific refusal is missed and a less specific one fires. **Whether
tier-3 steps 4-5 write BEFORE that refusal is UNVERIFIED and is Codex's claim, not ours. You settle
it BY EXECUTION.**

## 3. THE SEAM — what I measured, so you can find it faster. Verify it yourself; do not trust it.

At **both** corrector call sites the INTERPRETING check runs BEFORE the byte-exact gate — which is
the inversion R2 rules out:

- `swing/trades/reconciliation_auto_correct.py:473` — `_refuse_immutable_journal_fields(affected_table, proposed.keys())`, then the per-field walk calls `_assert_real_column_name` at `:475`.
- `…:2239` — `_refuse_immutable_journal_fields(affected_table, (field_name,))`, then `_assert_real_column_name` at `:2240`.

**The constraint you MUST preserve while inverting them** — it is documented at `:468-472` and it is
load-bearing: the immutable preflight runs over the **WHOLE payload** before the per-field walk,
precisely because `_handle_multi_field_correction` applies fields SEQUENTIALLY, so a backstop-only
check would let an earlier field's UPDATE execute before `attempt_id` was discovered second. **That
JSON-key-order independence is the property Task 1b bought. Do not spend it to buy byte-exactness.**
Whatever shape you choose, the byte-exact gate must also cover the whole payload before any write.

Note `_assert_real_column_name` needs `conn`; `_refuse_immutable_journal_fields` does not. At `:473`
`conn` is in scope. **If some path cannot run the byte-exact gate first, that ordering constraint is
a finding to ROUTE to me — not a reason to keep the normalizer** (CHARC, R2).

## 4. TASKS

**R2 — the structural invariant.** Byte-exact-first on every corrector path; later checks compare the
canonical name only; **delete `_normalize_journal_field_name`** once it is dead, and delete its
`_IMMUTABLE_JOURNAL_FIELDS_BY_RESOLVED_NAME` indirection if that too becomes dead. RED first.

**The closure test, red-first, per CHARC:** each of the **SIX** known non-canonical spellings —
`ATTEMPT_ID`, `[attempt_id]`, `"attempt_id"` (R1 Major 3) and `'attempt_id'`, `(attempt_id)`,
`/*x*/attempt_id` (R3-03) — is refused with **ZERO rows written, including tier-3 steps 4-5's rows.**
Name the naive substitute each row fails against. **The zero-rows-written assertion is also the
execution that settles Codex's write-ordering claim: report what it shows, either way.** The `(m8e)`
negative control (a different column whose name merely contains an immutable one) **keeps passing** —
if your change breaks it you have built substring matching, which is the defect one door down.

**R3 — the docstring, one line.** `swing/data/db.py`: the `pre_version == (target - 1)` parenthetical
becomes `current_version == 37 AND target_version >= 38`. **The implementation is right and is the
Phase-9 canonical shape — do not touch it.**

**Round 4 — counted, per §1, AFTER R2 and R3 land.** Recipe §3 governs: the five per-round
assertions, scratch relocation, the copy-per-round `cp` to
`~/swing-data/review-transcripts/22-a4-exec/` **the moment the assertions pass**, the ledger append.
**Only the anchored VERDICT TOKEN with `^ERROR`=0 proves the review FINISHED** — a `tokens used`
footer proves the file is complete, nothing more.

## 5. BINDING CONVENTIONS

- **TDD, RED first**, with the naive substitute named for each row.
- `fix(trades):` / `test(trades):` / `docs(trades):` / `docs(data):`. **No `Co-Authored-By`. No
  `--no-verify`. No amending.**
- **Keep the FINAL `-m` paragraph plain prose.** `b3b518f9` already carries a `Tests:` paragraph git
  parses as a trailer — **that one is the orchestrator's to reword at merge; do not add a second.**
  Audit the whole `%(trailers)` output, not just the `Co-Authored-By` key.
- **Use `;` not `&&`** in verification chains (`git … | grep -c` exits 1 on zero matches).
- **Baseline: 12294 passed / 13 skipped / 0 failed at `-n auto`, 16 workers, on `df231195`** —
  measured by the previous cell and **re-verified by the orchestrator only as arithmetic** (12290 + 4
  new rows). **`-n auto` survived in that cell's seat; prefer it and state your worker count.**
- `ruff check swing/ --statistics` as a **separate** command.
- **Run the full fast suite BEFORE the review round** (so it converges on a green diff) **and again
  after.**
- **Never open or migrate the live DB.** Live schema is v37; **0038 is UNAPPLIED.**
- **The locks this arc has bought, all still binding:** `_entry_transaction`, `_durability_probe` and
  `record_entry` are **byte-identical** since `a32ea9d5` and must stay so — this leg has no business
  in `entry.py` at all. PIN 1 is not re-opened. `(k7a)`/`(k7b)` keep their broad
  `pytest.raises(BaseException)`.

## 6. RETURN REPORT (final chat message — post to no mailbox)

- Commits (sha + subject). **What each RED asserted and the naive substitute it failed against.**
- **The seam you chose, and why** — including how you preserved the whole-payload / JSON-key-order
  independence property of `:468-472`. Show the code.
- **What the zero-rows-written execution showed about Codex's tier-3 write-ordering claim.** State it
  as settled-by-execution or as still-open; do not leave it implied.
- Confirmation that `_normalize_journal_field_name` is **deleted**, or the routed ordering finding
  that prevented it.
- Confirmation that `(m8e)` still passes, quoted.
- Confirmation that `entry.py` is **untouched** by this leg (diff `--stat`).
- Round 4's ledger row and its five measurements (model, effort, `^ERROR`, footer, anchored verdict
  token), plus its `tokens used` and the running total (rounds 1–3 were 441,127 + 590,318 + 513,003
  = **1,544,448**).
- Full suite + ruff + trailer audit, quoted, with the worker count.
- **Which copy of the recipe you read** and its `main` SHA.
- Anything you did NOT do, and why.

**Do not estimate your own context depth** — a cell cannot see it. Report your state; the
orchestrator fills that column.

## 7. IF YOU GET STUCK

STOP and return with the specific question. Report to the orchestrator in chat and to no one else.
**You never run `scripts/role_mail.py` and you post to no mailbox** — the QA gate between your report
and the directors is the orchestrator's.
