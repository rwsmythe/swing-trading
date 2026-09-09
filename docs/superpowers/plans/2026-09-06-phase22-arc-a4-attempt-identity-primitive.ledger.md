# 22-A4 — REVIEW LEDGER

**Committed per CHARC's ruling of 2026-09-07 (recipe rule 2 + `harness-architecture.md` §5.1, `7a870eab`):
the ledger is the RECORD and it lives in the repo; the transcripts stay at the durable path outside it,
NAMED here by path and byte size.** Previously this content existed only in a gitignored file — which,
in an arc whose subject is provenance, and after a night in which the canonical copy of this evidence
sat single-copy in a session-scoped temp directory, was the wrong place for it.

**Design record:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.md`
**Executing extract:** `docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md`

## Round ledger

| round | tier / model / effort | C / MAJ / MIN | new | reopened | reverted | verdict |
|---|---|---|---|---|---|---|
| 1 | `strong` / `gpt-5.6-sol` / `high` | 1 / 6 / 3 | 10 | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| 2 | `strong` / `gpt-5.6-sol` / `high` | 0 / 7 / 2 | 9 | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| 3 | `strong` / `gpt-5.6-sol` / `high` | 1 / 8 / 3 | 12 | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| 4 | `strong` / `gpt-5.6-sol` / `high` | 1 / 10 / 1 | 12 | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| SS | *(uncounted self-sweep, no Codex)* | 0 / 0 / 9 | 9 | - | - | *no verdict; no effect on convergence* |
| 5 | `strong` / `gpt-5.6-sol` / `high` | 1 / 7 / 4 | 12 | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **6** | `strong` / `gpt-5.6-sol` / `high` | 0 / 11 / 2 | 13 (**6 new ground, 7 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| AUDIT | *(deterministic self-audit, 68 probes, no Codex)* | -- | 2 real gaps | -- | -- | *no verdict* |
| **7** | `strong` / `gpt-5.6-sol` / `high` | 0 / 9 / 3 | 12 (**6 new ground, 6 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| SWEEP | *(deterministic consistency sweep, no Codex)* | -- | 3 bookkeeping | -- | -- | *no verdict* |
| **8** | `strong` / `gpt-5.6-sol` / `high` | 0 / 5 / 1 | 6 (**2 new ground, 4 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| 9-DQ | *(DISQUALIFIED -- provider capacity)* | -- | -- | -- | -- | **NO VERDICT; 2 anchored `^ERROR`, exit 1. 316,797 tokens spent, NOT counted.** |
| **9** | `strong` / `gpt-5.6-sol` / `high` | 0 / 9 / 0 | 9 (**6 new ground, 3 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| AMEND | *(2026-09-07 amendment pass on RD's three rulings; sweep 41/41/41, per-location audit 38 probes)* | -- | -- | -- | -- | *no verdict; no effect on convergence* |
| 10-DEAD | *(NOT A ROUND -- MSYS path-mangling; harness exit 0, 0-byte transcript)* | -- | -- | -- | -- | **NO BANNER, NO FOOTER, NO VERDICT. 0 tokens.** |
| **10** | `strong` / `gpt-5.6-sol` / `high` | 1 / 5 / 1 | 7 (**1 new ground, 6 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **SETTLE** | *(2026-09-07 DEDICATED SETTLING SWEEP -- gate-holder ruled; RD's two round-10 rulings applied, then `SS-9`..`SS-16`; NO Codex, NO round number)* | -- | **8 uncounted (`SS-9`..`SS-16`)** | -- | -- | *no verdict; NO effect on convergence* |
| **11** | `strong` / `gpt-5.6-sol` / `high` | 1 / 11 / 2 | 14 (**8 new ground, 6 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **FIX** | *(2026-09-07 FIX LEG -- operator-authorized, **NO CODEX ROUND**; four instruments re-run, two strengthened)* | -- | **13 of round 11 FIXED, 1 ROUTED** | 0 | 0 | *no verdict; **NO effect on convergence** -- a fix leg is not a round* |
| **SETTLE-9** | *(2026-09-07 orchestrator NETWORK FETCH; **NO CODEX**)* | -- | **`A4-R11-9` CLOSED; SOURCE (S1) confirmed upstream; the citation rule amended -- pin the UPSTREAM digest, never a local copy's** | -- | -- | *no verdict; NO effect on convergence* |

## Round-11 dispositions

| finding | severity | disposition |
|---|---|---|
| `A4-R11-1` | CRITICAL | **FIXED** -- `_CONTEXT_SLOT`, the base-slot read, ALARM-direction containment; the "structurally impossible" sentence STRUCK; (k7a)-(k7b) added in Task 3 |
| `A4-R11-2` | MAJOR | **FIXED** -- RD's ruling adopted with all three conditions; (RD-a4) rebuilt as a four-row matrix; `sys.exc_info()[1]` (a measured premise correction to the relayed `sys.exception()`) |
| `A4-R11-3` | MAJOR | **FIXED** -- dissolved by the `_read_resolution` split; the deferred retry is GONE, which restores the pre-arc behaviour |
| `A4-R11-4` | MAJOR | **FIXED** -- the shared thing is the NON-MUTATING read; the immediate ladder keeps `raise cleanup_error from write_error`, pinned by (k6b) |
| `A4-R11-5` | MAJOR | **FIXED** -- Task 3 SPLITS the pre-arc gate (behaviour unchanged); (k3a) asserts the split itself |
| `A4-R11-6` | MAJOR | **FIXED** -- (k6a)-(k6b), the immediate path's Task-3 discriminators, no probe and no `record_entry` |
| `A4-R11-7` | MAJOR | **FIXED** -- (pr1)-(pr4), one row per unpinned Task-4 requirement |
| `A4-R11-8` | MAJOR | **FIXED** -- (m3) split into (m3a)/(m3b)/(m3c); the gate proven INVOKED and LOAD-BEARING; S6's witness compares against a live before-image, not the constant |
| `A4-R11-9` | MAJOR | **SETTLED** (S8 item 8) -- ROUTED by this leg with the settling method written down; the orchestrator then ran exactly that method. **UPSTREAM sha256 `8cc0d9df...`, 80,695 bytes, content-identical after newline normalisation. SOURCE (S1) holds.** It also FORCED A CORRECTION AGAINST OUR OWN CITATION RULE: the previously pinned `7487db46...` was the hash of OUR copy (LF->CRLF on a text-mode write) -- **a local copy's digest is provenance of the READING, never of the SOURCE.** RD-ratified remedy now standing: pin the UPSTREAM digest with the fetch URL |
| `A4-R11-10` | MAJOR | **FIXED** -- (pr5) + the `file:...?mode=rw` URI open, VERIFIED BY EXECUTION on this box |
| `A4-R11-11` | MAJOR | **FIXED** -- the below-HEAD census re-measured per file as CALL counts; the drop-path reason holds for ONE site |
| `A4-R11-12` | MAJOR | **FIXED** -- the live journal mode relabelled INFERRED at both sites; S6 step 0 asks for `PRAGMA journal_mode` |
| `A4-R11-13` | MINOR | **FIXED** -- SEVEN at `:178-196`, corrected at BOTH sites; the sweep gained CONTRADICTION probes |
| `A4-R11-14` | MINOR | **FIXED** -- (RD-a2) in Task 4, not Task 5 |
| `SS-17` | (uncounted) | **FIXED** -- the `insert_trade_with_event` grep's REAL output is nine hits, of which one is a call |

## Sweep findings (uncounted)

| id | what | class |
|---|---|---|
| **`SS-9`** | applying RD's PIN 1 naively left the (then-mutating) shared observer UNCONDITIONAL in `_entry_transaction`'s deferred handler, which reaches the **pre-arc BODY-RAISE branch** and would issue a rollback that path never issued -- 22-A LOCK clause (c)'s subject, widened by a fix for something else. Both observations moved to `record_entry`; the deferred branch is now LITERALLY UNEDITED and (k3a) asserts it. | a fix that widened the blast radius of the thing it fixed |
| **`SS-10`** | S1.4 still said the arc adds "the three NEW observation fields" to the deferred path. | residual of the same pass, in a section it did not visit |
| **`SS-11`** | THREE stale in-repo line anchors, found by a script that resolves all 54 and prints what each lands on: `entry.py:1128` is `conn.rollback()` not the immediate `committed` assignment (`:1107`); `entry.py:880` is inside a comment block, not the shipped guard (`:884`) -- **and `:880` is the number this dispatch's own PIN 1 was relayed with, so it had propagated to three sites before the sweep caught it**; `entry.py:1489` is one line above the UNIQUE mapper. | citation drift |
| **`SS-12`** | S8 item 4 cited FOUR anchors for "the four pre-commit logging calls in `_record_entry_inner`". **`_record_entry_inner` begins at `:1166`; all four pointed into `record_entry`, and not one is a logging call.** MEASURED by AST walk: `:1227`, `:1295`, `:1306`, `:1321`. **The COUNT was right and every ANCHOR was wrong** -- the arrangement that reassures a reader checking the number and misdirects one checking the code. | the in-repo twin of `A4-R10-5` |
| **`SS-13`** | `A4-R10-3`'s generalisation turned into an INSTRUMENT (`assertion_schedule_audit.py`) instead of a paragraph: it walks all 44 rows, collects the symbols each names, and reports every row scheduled before something it names. | a rule with no check is a wish |
| **`SS-14`** | what `SS-13` found on its first run, in a row **this same pass had added four hours earlier**: (k3a)'s new ordering assertion named `_settle_by_attempt_identity` and was scheduled in Task 3. **Its failure mode is worse than the four counted instances:** an AST walk asserting an ORDERING finds no such node, therefore finds no ordering to violate, and reports SUCCESS. **Scheduling-by-artifact does not always produce a red test; it can produce a vacuous green one.** | the class, met inside its own fix |
| **`SS-15`** | S3's roster still described (k3a)/(k3b) as asserting the `committed` assignment is "inside the protected suite on BOTH paths" -- false one commit after `SS-9`. | residual, at the smallest scale it comes in |
| **`SS-16`** | Task 1b said "THREE call sites" for four rounds while the heading above its tests claimed **EVERY OPERATOR SURFACE**; nothing connected them. Closure established by AST walk + a raw-SQL grep: `_update_journal_field` has exactly four callers and is the ONLY site writing an operator-supplied journal field, so the backstop IS the closure and the two early checks are ordering refinements. **And the finding behind the finding:** the plan's whole argument for the tier-3 early check is that its INSERT comes first, and nobody had checked whether the other surfaces share that shape. They do not, for a DIFFERENT reason each. | a roster is the same instrument as the count it replaced |

## Transcript manifest

Durable path: `C:/Users/rwsmy/swing-data/review-transcripts/22-a4-plan/` (dotfiles — use `ls -a`).

| transcript | bytes |
|---|---|
| `.codex-review-r1.txt` | 971,232 |
| `.codex-review-r10.txt` | 1,145,895 |
| `.codex-review-r11.txt` | 1,606,610 |
| `.codex-review-r2.txt` | 640,482 |
| `.codex-review-r3.txt` | 972,415 |
| `.codex-review-r4.txt` | 1,037,971 |
| `.codex-review-r5.txt` | 1,069,399 |
| `.codex-review-r6.txt` | 1,102,235 |
| `.codex-review-r7.txt` | 1,320,409 |
| `.codex-review-r8.txt` | 1,382,826 |
| `.codex-review-r9-DISQUALIFIED-capacity.txt` | 1,000,211 |
| `.codex-review-r9.txt` | 1,080,516 |

Also preserved there: every `.codex-prompt-r<N>.md`, the four instruments
(`plan_consistency_sweep.py`, `per_location_audit.py`, `assertion_schedule_audit.py`, `citecheck.py`),
the RD-a4 matrix measurement script, the item-2 experiment record, and the pinned CPython source
(`connection.c`, upstream sha256 `8cc0d9df05860c0b3fe6929ff392f8f85c9e1a5ef89c0cba31ab09ba03b3369e`,
2,717 lines, 80,695 bytes — pin the DIGEST and the fetch URL; a line count is a convenience, never a pin).

## Extract losslessness — the id-set diff (mechanical, no Codex)

Run at extract creation, 2026-09-07: **task ids design=10 / extract=10, MISSING=0.**
**Test ids: 5 apparent misses, ALL RESOLVED BY READING, none a real gap.** Four were artifacts of an
over-broad regex — `(exc)` is a C fragment in the pinned source quote, `(iii)` a prose enumeration,
`(path)` a function signature, `(x3)` a count. The fifth, **`(e3)`, is real but belongs to the BANKED
`(S-d)` allocator branch** RD did not select: it occurs exactly once in 4,415 lines, inside S2's
"test consequences if (S-d) were chosen", and correctly appears in no roster and no ladder.
**Recorded so the next run of this diff does not re-derive it** — and noted as the mirror image of
`A4-R6-4`, where a fix landed in the banked branch instead of the shipping one.

---

# 22-A4 writing-plans -- Codex A-loop findings ledger

Artifact: `docs/superpowers/plans/2026-09-06-phase22-arc-a4-attempt-identity-primitive.md`
Base `edfea928`, worktree `.worktrees/22-a4-plan`.
Transport: WSL codex-cli 0.152.1, `codex exec -p strong -s read-only --skip-git-repo-check -`,
stdin bundle (prompt + full plan) with the worktree as cwd so the reviewer can verify the plan's
code claims against the repository.

**Criterion (recipe, plan/doc reviews):** blocking = RESULT-BEARING; convergence = TWO consecutive
rounds with zero result-bearing findings; a contested classification counts result-bearing.

---

## LEDGER CONVENTIONS -- **added 2026-09-07, because this ledger's own totals were used as
## convergence evidence and were not establishable from it**

`A4-R9-9` found the totals wrong twice over. The arithmetic was then corrected -- **and the
document still could not be PARSED to check it**, which is the deeper defect: three different
counts had been reported as fact, including to a director, and every one of them was produced by a
human reading a document whose headers had five different shapes. **A total used as evidence is
evidence, and evidence has to be re-derivable by someone who does not trust the author.**

**EVERY finding now carries ONE header shape, and nothing else in this file does:**

```
**A4-R<round>-<n> -- <SEVERITY> -- <CLASS> -- <text>
```

- **SEVERITY** is exactly one of `CRITICAL` / `MAJOR` / `MINOR`. Complete for all 95 findings.
- **CLASS** is exactly one of:
  - **`NEW GROUND`** -- a subject no earlier finding in this loop had raised.
  - **`RESIDUAL`** -- a defect in, or an incompleteness of, a fix this loop made for an
    earlier finding. (The Expansion-#13 cascade signature; the gate-holder weighs it.)
  - **`CLASS-UNRECORDED`** -- **the loop did not record this finding's class at the time, and it
    is NOT being backfilled by inference now.** Rounds 6-9 recorded a round-level split and rounds
    7-9 labelled most findings individually; rounds 2-6 did not, so a per-finding class for them
    would be my reading today rather than the round's record. **Reconstructing a record is exactly
    the failure this arc exists to refuse**, so the field says so instead. Where a round-1-to-5
    entry states its own provenance in its own text (*"a residual of R4-2's fix"*), that statement
    is the record and the class is set from it.
  - Round 1's ten are `NEW GROUND` **by construction**: no fix existed yet to be residual to.
- **THE `new` / `reopened` / `reverted` COLUMNS IN THE ROUND TABLES ARE A DIFFERENT AXIS** and are
  unchanged: they record NEW-versus-REOPENED (was this finding raised and dispositioned before?),
  **not** NEW-GROUND-versus-RESIDUAL. Conflating the two is how "NEW = 12" came to sit beside a
  round whose own prose said a growing share were residuals of its own fixes.
- **Round 5's eleven gate-deferred findings were written as `- **R5-N (SEVERITY) -- ...`** -- a
  sixth header shape, in a bullet list, without the `A4-` prefix, which is why a regex over the
  file found 84 ids where there were 95 findings. **They now carry the same header as everything
  else.** No id changed meaning; `R5-2` and `A4-R5-2` are the same finding.

**THE TOTALS, AND THE COMMAND THAT PRODUCES THEM** (run against this file; if it disagrees with
the prose, the command is right and the prose is the bug):

```
python -c "import re,collections,pathlib; \
h=re.findall(r'\*\*A4-R(\d+)-(\d+) -- (CRITICAL|MAJOR|MINOR) -- (NEW GROUND|RESIDUAL|CLASS-UNRECORDED) --', \
pathlib.Path('.copowers-findings.md').read_text(encoding='utf-8')); \
print(len(h), collections.Counter(x[2] for x in h), collections.Counter(x[3] for x in h), \
collections.Counter(int(x[0]) for x in h))"
```

**MEASURED OUTPUT, 2026-09-07, after round 10 was recorded:**
- **102 findings** across TEN counted rounds.
- **SEVERITY: 5 CRITICAL / 77 MAJOR / 20 MINOR.**
- **CLASS: 23 NEW GROUND / 30 RESIDUAL / 49 CLASS-UNRECORDED.**
- **PER ROUND: R1 10, R2 9, R3 12, R4 12, R5 12, R6 13, R7 12, R8 6, R9 9, R10 7.**
- Zero REOPENED and zero REVERTED across all ten rounds.
- *(Through round 9 only, the number carried in the round-9 verdict block: 95 findings,
  4 CRITICAL / 72 MAJOR / 19 MINOR.)*

**UNCOUNTED WORK IS NOT IN THAT TOTAL AND NEVER ENTERS IT:** the post-round-4 self-sweep
(`SS-1`..`SS-9`), the post-round-6 deterministic self-audit (68 probes, 2 real gaps), the
pre-round-8 consistency sweep (3 bookkeeping items), and the 2026-09-07 amendment pass's own
per-location audit. **They carry no round number, no Codex verdict, and no effect on convergence** --
which is the whole point of keeping them uncounted.

**Transport note, round 1 attempt 1 -- A DEAD ROUND THAT REPORTED SUCCESS.**
`wsl.exe bash /mnt/c/.../.codex-run-r1.sh` produced
`bash: C:/Program Files/Git/mnt/c/Users/rwsmy/.../.codex-run-r1.sh: No such file or directory`
and the harness reported **exit 0**. This is the MSYS path-mangling mechanism the recipe records,
and the recipe's stated remedy -- "make the argument NON-PATH-INITIAL, e.g. `bash /home/.../run.sh`"
-- was already satisfied and was NOT sufficient: the mangling hit the SECOND argument, the one that
begins with `/`. The transcript was 0 bytes and the exit file empty, so the round was disqualified
by the two-signal rule (exit code MEASURED and transcript NON-EMPTY; here the exit signal lied and
the transcript told the truth). Working form:
`cd <worktree> && MSYS_NO_PATHCONV=1 wsl.exe bash -lc 'bash /mnt/c/.../run.sh'` -- the `-c` STRING
begins with `bash`, so no argument MSYS parses begins with `/`.

---

## Round 1

### Mechanical assertions -- ALL FIVE PASS

| # | assertion | value |
|---|---|---|
| 1 | banner model is the binding tier | `model: gpt-5.6-sol` |
| 2 | reasoning effort | `reasoning effort: high` |
| 3 | `grep -c '^ERROR'` | **0** |
| 4 | `grep -c '^tokens used'` anchored footer | **1** |
| 5 | anchored verdict tokens | `^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0** |

codex-cli 0.152.1 emits the final message twice, so the invariant asserted is ONE DISTINCT token
present and the other absent. Exit file `0`, measured. Transcript 971,232 bytes / 8,829 lines,
non-empty. The process demonstrably exited before the transcript was read or judged. No
content-filter event: no refusal or rewrite reported or visible.

**Scratch-in-input check:** the reviewer ran `ls -la` and a repo-wide `rg`, which matched inside its
OWN in-progress transcript while searching for the baseline suite number. It read no PRIOR round's
findings, because none existed. **Mitigation for rounds 2+: every `.codex-*` artifact is moved to
the session scratchpad immediately after each round, so no earlier transcript or findings file
exists in the worktree while a later round runs.**

### Counts

**10 findings: 1 CRITICAL, 6 MAJOR, 3 MINOR. NEW = 10. REOPENED = 0. REVERTED = 0.**
One MAJOR carries the reviewer's own `[OUT-OF-ENVELOPE]` tag (R1-7).

### Per-finding adjudication

**A4-R1-1 -- CRITICAL -- NEW GROUND -- the UNIQUE index does not enforce uniqueness across ROLLED-BACK attempts.**
**ACCEPTED; the plan's claim was simply false.** S2.0 said the index makes a duplicated token
"IMPOSSIBLE TO COMMIT". A rolled-back token leaves no trace in the index, so a later attempt that
independently minted the same token would be admitted. Adjudication of the two halves:

- The CLAIM is wrong and is rewritten. What the index actually buys: at most one LIVE row per token
  (so the probe can never find two), and a systematic token-reuse BUG becomes a loud pre-commit
  failure. It cannot defend against a collision with a token that no longer exists.
- The DESIGN still satisfies RD constraint 2 as ruled -- "never reusable across attempts", glossed
  by "rowid fails by construction" -- because uuid4 is not RE-ISSUED by anything; the exposure is an
  RNG COLLISION, not reuse. But that makes uniqueness PROBABILISTIC rather than STRUCTURAL, and the
  plan must say so. Arithmetic, stated because the plan's own discipline requires it: with n
  lifetime entries the collision probability is about n^2 / 2^123; at n = 10^5 that is about 1e-27,
  and the sequence additionally requires the colliding attempt to carry the SAME TICKER to pass
  corroboration.
- The reviewer's proposed remedy (a durable token reservation surviving row rollback) is DECLINED
  with its reason: a reservation that survives a rollback must be committed independently of the
  entry transaction, which makes it a STAMP (not co-durable, gotcha #30) and adds a second commit to
  the money path whose own failure re-creates the original problem.
- ACTIONS: S2.0's index paragraph rewritten; new S7.7 declaring probabilistic uniqueness with the
  arithmetic; new test (RD-b2) pinning the declared residual BY EXECUTION; S9's RD block now asks
  him to rule on the probabilistic reading of constraint 2 explicitly.

**A4-R1-2 -- MAJOR -- NEW GROUND -- the deferred-path premise generalised a direct-commit measurement to the
context manager.** **ACCEPTED. RE-MEASURED, and the reviewer is right.** Same world, two forms:
`conn.execute(INSERT); conn.commit()` with the commit failing leaves `in_transaction` TRUE;
`with conn:` around the same INSERT with the automatic commit failing leaves `in_transaction` FALSE
-- the context manager rolls back. The plan's S1.4 claim (leaves the transaction OPEN and no
rollback is attempted at all) was FALSE, and three tests were written against a value the real path
does not produce. This SIMPLIFIES the design: the deferred path needs no rollback added, so S7.3's
declared behaviour change is DELETED along with CHARC routing item 3, and the pre-arc path keeps its
exception identity byte-for-byte. The wrapper now OBSERVES `conn.in_transaction` rather than
resolving, and attempts a rollback only in the residual case where the context manager's own
rollback failed and left the transaction open.

**A4-R1-3 -- MAJOR -- NEW GROUND -- the deferred pseudocode left the committed-flag assignment OUTSIDE the guarded
region.** **ACCEPTED; a real hole, and it contradicted S7.12 in the plan's own text.** An
asynchronous exception after the with-block returned (commit durable) but before the assignment left
body_completed=True, committed=False, resolution=unattempted, which the settle gate rejects, so a
failure would be reported over a durable entry. Fixed by moving the assignment INSIDE the try,
matching the immediate path. The reviewer's requested boundary test is not constructible (the
interval contains no statement), so the property is pinned the way it actually can be: new test
(k3), a STATIC AST assertion that on BOTH paths the committed assignment is lexically inside the
protected suite.

**A4-R1-4 -- MAJOR -- NEW GROUND -- the closure test's branch and exclusion counts are wrong, and S3 contradicted
itself.** **ACCEPTED; verified by reading `swing/data/repos/trades.py`.** Three existing INSERT
branches (v27+, v21-v26, pre-v21) plus the new v38 branch = FOUR statements, ONE carrying the column
and THREE reasoned era exclusions. S3 (r5) and Task 2 corrected; the mutation proof now covers both
directions the reviewer names -- omission from the v38 branch, and an unreasoned fifth statement.

**A4-R1-5 -- MAJOR -- NEW GROUND -- the schema-version mirror census is incomplete.** **ACCEPTED, verified, and
the census is worse than the reviewer says.** Re-counted by grepping each SPELLING separately rather
than the concept: `EXPECTED_SCHEMA_VERSION == 37` = 26; bare-literal assertions on
version / ver[0] / version_row[0] / row[0] / post / cur.fetchone()[0] = 11;
`_current_version(...) == 37` = 4; the INEQUALITY ceiling `versions[-1] <= 37` = 1; a chained
`version == EXPECTED_SCHEMA_VERSION == 37` = 1; and a sixth family the reviewer did not name --
15 `run_migrations(..., target_version=37, ...)` call sites whose INTENT is migrate-to-HEAD, which
after the bump would silently leave those fixtures one version BELOW head and run `record_entry`
against a schema with no attempt_id column. That family also FALSIFIES the plan's own S1.6 claim
that no `record_entry` call site runs below HEAD -- true today, false the moment HEAD moves. This is
the recipe's "a token grep bounds the family from BELOW" lesson landing on the plan that quotes it.
ACTIONS: S1.6's census rewritten with all six spellings and the method for each; the inequality
guard named explicitly in Task 1 as an AUTHORIZATION gate whose bump belongs in the migration's own
commit; the HEAD-intent target_version=37 sites re-spelled as EXPECTED_SCHEMA_VERSION so they cannot
rot again, with the deliberately-old sites (36, 16) excluded by name; S1.6's below-HEAD claim
corrected.

**A4-R1-6 -- MAJOR -- NEW GROUND -- the live-migration witness has no before-image.** **ACCEPTED.** S6 steps 3-4
assert unchanged against nothing. New step 0 records version, total trades, the non-existence of
attempt_id, the latch-link count and the full open-trade (id, ticker, state) set BEFORE migrating.

**A4-R1-7 -- MAJOR -- NEW GROUND -- OUT-OF-ENVELOPE -- the printed backup is not the arc-gate backup.**
**ACCEPTED; verified at `swing/cli.py:258-270` and `:310`.** `swing db-migrate` prints its own
general snapshot in backups_dir and then calls `ensure_schema(...)` with no backup_dir, so the arc
gate's `swing-pre-22a4-migration-<ISO>.db` defaults to `src_path.parent` (the DB's own directory)
and its name is never printed. S6 now names BOTH artifacts and where each lives. The suggested CLI
change is DECLINED as out-of-envelope, and the underlying gap -- arc backups landing in the DB root,
invisible to backup-directory sweeps -- is BANKED in S8 with an owner and a trigger.

**A4-R1-8 -- MINOR -- NEW GROUND -- (d), (i) and (j) pass under both paths, contradicting S3's universal claim.**
**ACCEPTED with one correction to the finding.** (i) and (j) are pure regression CONTROLS and are
re-labelled as such. (d) is NOT: it discriminates against an implementation whose settle invents a
success from a probe error or a missing token, which is a live design risk in this arc; its
pre-fix-identical line refers to the CURRENT tree, not to the naive implementation it excludes, and
it is rewritten to say so. S3's header claim is narrowed to the discriminating roster.

**A4-R1-9 -- MINOR -- NEW GROUND -- (m4) and (m5) pre-fix values are computable, not n/a.** **ACCEPTED.** On the
current tree `run_migrations(target_version=38)` is capped at EXPECTED_SCHEMA_VERSION 37, so (m4)'s
version assertion reads 37, and (m5)'s attempt_id query raises "no such column". Both recorded.

**A4-R1-10 -- MINOR -- NEW GROUND -- S7.4 contradicts S2.1's attempt-start location.** **ACCEPTED.** The gauntlet
refusals occur BEFORE the mint, so they mint nothing at all; only failures between the mint and the
INSERT mint an unstored token. S7.4 narrowed.

### Verdict

`NEW_CRITICAL_MAJOR_FOUND` -- anchored, 2 occurrences of the one token, the other token absent.

---

## Round 2

Artifact frozen before the round; sha256 `dd5682c2d34fdefa74c9fce11526d023c0c408abea2d5c1b6b0b3b17ae0a77d1`
(111,786 bytes). Round 1's transcript and this ledger were moved OUT of the worktree first, so no
prior-round findings existed on disk while round 2 ran.

### Mechanical assertions -- ALL FIVE PASS

model `gpt-5.6-sol`; reasoning effort `high`; `grep -c '^ERROR'` = **0**;
`grep -c '^tokens used'` = **1**; `^NEW_CRITICAL_MAJOR_FOUND` = **2** and `^NO_NEW_CRITICAL_MAJOR` =
**0**. Exit file `0`, measured; transcript 640,482 bytes, non-empty; process exited before the file
was read. No content-filter event reported or visible.

### Counts

**9 findings: 0 CRITICAL, 7 MAJOR, 2 MINOR. NEW = 9. REOPENED = 0. REVERTED = 0.**

### Per-finding adjudication

**A4-R2-1 -- MAJOR -- CLASS-UNRECORDED -- the durable ALLOCATOR was rejected for a false reason.** **ACCEPTED, and the
reviewer is right on the mechanism.** The plan dismissed a token reservation as "a STAMP (gotcha
#30)". It is not: an allocator that burns an identifier in its OWN committed transaction BEFORE the
attempt, and then writes that identifier into `trades.attempt_id` in the entry INSERT, keeps
co-durability intact -- the allocator row is never used as evidence that the trade landed, and the
probe still reads `trades`. An allocator-commit failure also cannot recreate the ambiguity, because
it precedes the entry transaction. ACTION: a FOURTH design alternative **(S-d)** is added to S2.0's
table with its real costs (a table, a second migration object, an attempt-log by side effect the arc
declined at S2.6, and a second COMMIT on the money path), the plan states its recommendation as a
judgment about proportion, and S9 routes the CHOICE to RD rather than presenting a dismissal.

**A4-R2-2 -- MAJOR -- CLASS-UNRECORDED -- the `target_version=37` sites are not one class, and re-spelling them would
bypass the new gate.** **ACCEPTED; verified by READING all 15.** Eight are in
`tests/data/test_22a_task2_migration_0037.py` and are 0037's own subject or literal arguments to the
22-A backup gate under test (`:106`, `:129`, `:143`, `:148`, `:163`, `:393`, `:567`, `:748`); two of
the four `_current_version(...) == 37` sites are 0037-result assertions in the same file. Those STAY
at 37. The remaining seven build a v36 world and then want production HEAD. **And the reviewer's
sharpest point is structural:** `run_migrations` evaluates every gate ONCE against the INITIAL
`current`, so a single 36 -> 38 jump can never satisfy `current_version == 37` and would exercise
0038 WITHOUT its strict-equality backup gate. ACTION: Task 1 now classifies by reading, keeps the
eight pinned, and for the seven ADDS a second `run_migrations(..., EXPECTED_SCHEMA_VERSION)` call
after the existing 37 call so BOTH gates fire. The "43 sites" headline is WITHDRAWN -- the counts
are floors with overlap and are explicitly not an edit manifest.

**A4-R2-3 -- MAJOR -- CLASS-UNRECORDED -- the schema and its Python mirrors were split across two commits.**
**ACCEPTED without reservation; it contradicted three things at once** -- gotcha #11's
one-task rule, the commissioning brief's "Mirrors in ONE commit (#11)", and the plan's own S2.5
sentence. ACTION: Tasks 1 and 2 are MERGED into a single red/green task and commit carrying the
migration, the version/gate work, `ATTEMPT_ID_LENGTH`, the repo write/read, the validator, the
IntegrityError narrowing and both drift comparators. Subsequent tasks renumbered.

**A4-R2-4 -- MAJOR -- CLASS-UNRECORDED -- nothing proved ONE token flows mint -> INSERT -> probe.** **ACCEPTED.** Every
identity row planted a CONSTANT token, which masks two defects: an implementation that mints
separately for the INSERT and for the settlement (green suite, re-raises over every durable lost
commit in production), and one whose `record_entry` calls the repo with `attempt_id=None` and stamps
later. ACTION: new test **(w)** -- the mint returns a DIFFERENT valid value on each call; assert it
is called EXACTLY ONCE; capture the `attempt_id` argument at `insert_trade_with_event` and the token
handed to the probe; all three plus the persisted value must be equal.

**A4-R2-5 -- MAJOR -- CLASS-UNRECORDED -- test (e) could not tell co-durability from a LATE STAMP.** **ACCEPTED; the
counterexample is exact.** "Committed row carries the token / rolled-back leaves none" is satisfied
by committing without the token and updating it in a second transaction. ACTION: (e) is rewritten to
observe the TRANSACTION BOUNDARY -- a proxy whose `commit()` first reads the pending row on the
WRITER's connection (must already show the token) and counts it on a FRESH connection (must be zero)
-- so the late-stamp implementation fails at read (a), which is where it must.

**A4-R2-6 -- MAJOR -- CLASS-UNRECORDED -- (k3) was too weak AND its founding claim was false.** **ACCEPTED on both
halves.** The AST predicate "inside SOME `try` whose handlers cover `BaseException`" is satisfied by
a nested decoy that records no resolution -- so the test could have blessed the very window it was
written to close. And "the window cannot be simulated" is wrong: a `sys.settrace` line hook can
raise immediately before the assignment. ACTION: (k3a) tightens the predicate to "directly in the
`Try.body` whose handler writes `resolution` and re-raises", and (k3b) adds the trace-hook runtime
test that demonstrates the durable-row/false-failure outcome against the first draft's shape. Both
are kept: the hook proves one line, the walk proves the property for assignments added later.

**A4-R2-7 -- MAJOR -- CLASS-UNRECORDED -- `resolution` conflated the TRANSACTION's state with the CALL's failure.**
**ACCEPTED, and the counterexample is a fixture ALREADY IN THIS TREE.** `_RollbackAfterEffect`
(`tests/trades/test_22a_task9_entry_wiring.py:3039`) performs the REAL rollback and then raises, so
the transaction is RESOLVED and the row is GONE -- and the draft labelled it `"unresolved"`, making
S2.4's "unresolved implies `in_transaction` True" false against pinned production behaviour. The
production handler four lines away already re-derives its message from `conn.in_transaction` for
exactly this reason. ACTION: the state model splits into `resolution` (PHYSICAL, re-read from
`conn.in_transaction` after the attempt: `not_needed` / `rolled_back` / `still_open`) and
`cleanup_raised` (the CALL raised). The admissibility gate reads BOTH and refuses on either --
rule (i) taken LITERALLY. S2.4's cost-is-zero argument is REBUILT by enumerating the two refusal
branches and showing the row is provably absent in each. RD-a1 gains the after-effect fixture as its
second shape.

**A4-R2-8 -- MINOR -- CLASS-UNRECORDED -- test (h) would query a connection the probe has already closed.**
**ACCEPTED.** The PRAGMA now executes INSIDE the monkeypatched repo reader, while it owns the live
connection, and only the scalar is stored.

**A4-R2-9 -- MINOR -- CLASS-UNRECORDED -- S7.4 said a pre-INSERT failure rolls the token back "with its row".**
**ACCEPTED.** Between the mint and the INSERT the token exists only in Python memory; only a failure
AFTER the INSERT leaves a written token to roll back. S7.4 now distinguishes the three cases.

### Verdict

`NEW_CRITICAL_MAJOR_FOUND` -- anchored, 2 occurrences of the one token, the other token absent.
**Loop CONTINUES: nine NEW, in-scope, non-reopened findings, seven of them MAJOR, zero reopened,
zero reverted -- the round-5 gate's own criterion for continuing.**

---

## Round 3

Artifact frozen before the round; sha256 `84a6d327b6cc4dfa597ea8c4dc1fe93e55f5db47526c3dfa6ac32d88b09bbbae`
(124,568 bytes). Rounds 1-2 artifacts moved out of the worktree first.

### Mechanical assertions -- ALL FIVE PASS

model `gpt-5.6-sol`; effort `high`; `^ERROR` = **0**; `^tokens used` = **1**;
`^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0**. Exit `0` measured; transcript
972,415 bytes; process exited before the file was read. No content-filter event.

### Counts

**12 findings: 1 CRITICAL, 8 MAJOR, 3 MINOR. NEW = 12. REOPENED = 0 as findings** (R3-1 revisits the
uniqueness question, but on a NEW ground -- the superseded reasoning left live in two other sections
-- so it is counted NEW). **REVERTED = 0.**

### Per-finding adjudication

**A4-R3-1 -- CRITICAL -- RESIDUAL -- the plan SELECTED a shape that satisfies the binding constraint only
probabilistically, and left the disproved "stamp" reasoning live in two sections.**
**ACCEPTED IN FULL, and it is the round's most consequential finding.** Two halves:
(a) S2.0 was corrected after `A4-R2-1` but **S7.7 and S9 still called the allocator a stamp whose
failed commit recreates the ambiguity** -- the fix-the-instance-leave-the-class failure the recipe
names explicitly. Both are rewritten. (b) More importantly, the plan had no business SELECTING
(S-b). The dispatch is explicit: *"If you cannot satisfy all three, STOP and route -- do not design
around a constraint."* ACTIONS: the shape becomes a **BLOCKING RULING (Task 0)**; **(S-d) is
SPECIFIED IN FULL at a new S2.0.1** (the allocation table, the `AUTOINCREMENT` sequence, the separate
connection, the CHECK/mirror deltas, and the test consequences including (RD-b2)'s INVERSION) so the
ruling costs no further planning pass; the plan RECOMMENDS (S-b) on proportion and says in terms
that proportion is not a ground on which a plan may narrow a binding constraint.

**A4-R3-2 -- MAJOR -- CLASS-UNRECORDED -- the schema change breaks 22-A's LOCK-A byte-identity test, undispositioned.**
**ACCEPTED; verified at `tests/trades/test_22a_task9_entry_wiring.py:918/949/1037`.** The test
asserts BOTH the complete `trades` column set and full dict equality against a golden captured at
pre-arc commit `a18a3771`, and `attempt_id` breaks both. **The test's own docstring anticipated this
arc** and says the failure is left LOUD precisely so a later column cannot be silently tolerated --
which CONSTRAINS the amendment's shape. ACTIONS: new **Task 0b** -- name the addition in the
column-set assertion (`| {"attempt_id"}`), keep byte identity for every pre-existing column, and ADD
a third assertion on the new column, so the lock gets stronger rather than softer; rewrite
`record_entry`'s docstring at `entry.py:633`, which promises `cfg=None` leaves "every persisted value
byte-identical" and becomes false (#31 class); **ROUTE the amendment to CHARC** as S9 CHARC item 5,
because LOCK clause (a) belongs to a merged arc.

**A4-R3-3 -- MAJOR -- CLASS-UNRECORDED -- RD-a1's second fixture cannot produce the path it claims.** **ACCEPTED;
verified at the source.** `_RollbackAfterEffect.commit()` commits normally and returns, so
`record_entry` succeeds and its raising `rollback()` is never reached; and failing the BODY instead
is not equivalent, because `result` stays `None` and the settle gate refuses before `cleanup_raised`
can discriminate. ACTION: specify a NEW combined proxy (commit raises without landing + rollback
takes effect then raises), stating why the existing one cannot be reused.

**A4-R3-4 -- MAJOR -- CLASS-UNRECORDED -- the settlement return type is internally inconsistent.** **ACCEPTED.** The
probe returns `tuple[int, str] | None` and the handler read `settled.trade_id`; no such dataclass
exists. ACTION: the helper returns the probe's tuple UNCHANGED and the handler UNPACKS it. A literal
implementation of the first draft would have crashed on the headline success path.

**A4-R3-5 -- MAJOR -- CLASS-UNRECORDED -- the settle helper cannot honour its exception-preservation contract with the
signature given.** **ACCEPTED.** S2.4 requires probe failures to be attached to the ESCAPING
exception and test (g) asserts that object's identity survives, but the helper was never handed it.
ACTION: `_settle_by_attempt_identity(attempt, outcome, req, post_commit_error)`.

**A4-R3-6 -- MAJOR -- CLASS-UNRECORDED -- a malformed mint RETURN is not contained, and the "never fails an entry" claim
is too wide.** **ACCEPTED on both halves.** Containment wrapped the CALL, so a mint returning `""` /
`"short"` / bytes is accepted and then rejected by the repo's pre-write validator -- failing an
entry solely because the identity apparatus exists, which is the one thing S2.1 promises cannot
happen. The empty string is not hypothetical: it is why the CHECK exists. ACTIONS: validate the
RESULT inside `_begin_attempt_identity` (`isinstance(str)` + exact length) and contain it as
identity-unavailable; add the malformed-return variant to (e2); and NARROW the claim to ordinary
`Exception`-class failures, naming the two deliberate exceptions (the propagated interrupt, and the
UNIQUE-index refusal of S7.8).

**A4-R3-7 -- MAJOR -- CLASS-UNRECORDED -- test (d) does not discriminate against the ACTUAL pre-fix tree.** **ACCEPTED.**
Naming a hypothetical naive implementation as "pre-fix" does not make the row evidence for this arc.
ACTION: (d) additionally asserts the probe was called EXACTLY ONCE, with the MINTED token, on a
connection that is not the writer's, and returned `None`. That fails on the current tree (call count
0) and also excludes an implementation that skips settlement and re-raises by accident.

**A4-R3-8 -- MAJOR -- CLASS-UNRECORDED -- the live backup witness can pass on a STALE file.** **ACCEPTED.** `ls
~/swing-data/swing-pre-22a4-migration-*.db` treats any match as proof the gate fired. ACTION: new
step 0b records the matching set BEFORE; step 1 identifies the EXACTLY ONE new path and OPENS it
(a copy, never through `ensure_schema`) to confirm version 37 and the expected table set. A backup
nobody opened is a filename, not a pre-image.

**A4-R3-9 -- MAJOR -- CLASS-UNRECORDED -- the `_CommitOutcome` field count contradicts itself at implementation-bearing
sites.** **ACCEPTED.** S4's manifest said "+2 fields" while S2.2's table listed three; an executor
following the manifest would have dropped `cleanup_raised`, which is a mandatory gate input and
RD-a1's after-effect discriminator. ACTION: stated consistently everywhere as FOUR observations,
THREE new fields.

**A4-R3-10 -- MINOR -- CLASS-UNRECORDED -- (m1)'s stated red is wrong for two of its three assertions.** **ACCEPTED**:
`AssertionError` on the constant and on the PRAGMA membership check; `OperationalError` only where
SQL names the column. Task 1's declared first red now matches the first assertion in file order.

**A4-R3-11 -- MINOR -- RESIDUAL -- commit subjects carry the pre-renumber task ids.** **ACCEPTED** -- collateral
from merging Tasks 1 and 2 in round 2. All commit subjects and the S11 references realigned.

**A4-R3-12 -- MINOR -- RESIDUAL -- stale counts and labels.** **ACCEPTED**: "Three shapes" with four presented;
two S9 items numbered 5; the retired `"unresolved"` enum label surviving in S7.1 and S9 after S2.2
renamed it `"still_open"`. All corrected.

### Verdict

`NEW_CRITICAL_MAJOR_FOUND` -- anchored, 2 occurrences of the one token, the other absent.
**Loop CONTINUES: twelve NEW findings, one CRITICAL and eight MAJOR, zero reopened, zero reverted.**

---

## Round 4

Artifact frozen; sha256 `9c0fd713663a0135f7e8f9b130ea9d8f1c51156054a2abeae266b8bbb185a0bd`
(136,337 bytes). Rounds 1-3 artifacts moved out of the worktree first.

### Mechanical assertions -- ALL FIVE PASS

model `gpt-5.6-sol`; effort `high`; `^ERROR` = **0**; `^tokens used` = **1**;
`^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0**. Exit `0` measured; transcript
1,037,971 bytes; process exited before the file was read. No content-filter event.

### Counts

**12 findings: 1 CRITICAL, 10 MAJOR, 1 MINOR. NEW = 12. REOPENED = 0. REVERTED = 0.**
Three (R4-9, R4-10, R4-12) are RESIDUALS OF THIS LOOP'S OWN FIXES -- superseded text left live in
sections an earlier fix did not sweep. Counted NEW, flagged as residuals.

### Per-finding adjudication

**A4-R4-1 -- CRITICAL -- CLASS-UNRECORDED -- `attempt_id` becomes writable through an existing GENERIC dynamic UPDATE.**
**ACCEPTED, verified at the source, and it is the best finding of the loop.**
`swing/trades/reconciliation_auto_correct.py:_update_journal_field` composes
`UPDATE trades SET {field_name} = ?` with the COLUMN NAME INTERPOLATED, allowlisted BY EXCLUSION
(`_RESERVED_JOURNAL_FIELDS`, `:178-183`, five entries), and `validate_trade_correction` checks only
`current_stop` and `state`. **A new `trades` column is writable through the tier-2 operator-truth
path from the moment it exists**, and a re-assignable token is not identity: A rolls back, a
correction attaches A's token to a different trade in the same ticker, A's probe confirms it -- a
FALSE SUCCESS in the expensive direction. **This is the D36 lesson landing on the plan that cites
D36:** S1.1 swept the dynamic-SQL family for INSERTs and asserted "the only writer" from it.
ACTIONS: S1.1's census corrected with both halves and the method; an immutability TRIGGER added to
0038 (`BEFORE UPDATE OF attempt_id ... RAISE(ABORT)`) -- chosen over the allowlist entry because it
is IN ENVELOPE and covers every writer including future ones, where the dict entry covers one module
outside the envelope; new test **(m7)** asserting BOTH a direct UPDATE and the real corrector path;
the allowlist entry BANKED at S8.6 as a message-quality belt and routed.

**A4-R4-2 -- MAJOR -- CLASS-UNRECORDED -- the prescribed TDD sequence cannot go green.** **ACCEPTED, both halves.**
Task 0b's amended LOCK-A asserts a non-NULL token, but Task 1 shipped only the migration and the
repo, so `record_entry` would still pass the new default and Task 1 would fail its own lock. And the
shipped test compares BOTH `a` (cfg passed) and `b` (cfg=None); the amendment covered only `a`.
ACTIONS: the mint and threading move UP into Task 1; Task 2 keeps only what does not change the
persisted row; both rows get the three-assertion treatment, and `b`'s non-NULL token is the
assertion that pins S2.1's mint-regardless-of-cfg decision.

**A4-R4-3 -- MAJOR -- CLASS-UNRECORDED -- the (S-d) branch is not implementation-ready, and its CHECK is unsafe.**
**ACCEPTED; the typing half REPRODUCED here.** "TEXT or INTEGER" is not a branch -- it changes the
column type, the Python type, the validator, the CHECK, the probe parameter and both drift tests.
And **MEASURED on this runtime: `CHECK(a IS NULL OR a > 0)` ACCEPTS `'abc'` on a TEXT column AND on
an INTEGER column** (affinity ranks text above integers); adding `typeof(a) = 'integer'` rejects both
`'abc'` and `''`. ACTIONS: S2.0.1 chooses INTEGER, carries the typed CHECK with the measurement, and
specifies the allocator's full lifecycle -- open / INSERT / commit / close each contained, the close
contained separately, and the bounded probe timeout rather than the 30-second default (a contained
30-second failure still delays an ordinary entry by 30 seconds). Four allocator-failure variants and
a new (e3) for the durable-allocation-before-a-downstream-refusal side effect.

**A4-R4-4 -- MAJOR -- RESIDUAL -- (e2) omits the malformed-RETURN defect round 3 introduced the fix for.**
**ACCEPTED**, and it is the sharper form of `A4-R3-6`: S2.1 now validates the RESULT, but the test
that proves the apparatus cannot fail an entry still exercised only the raising mint, so an
implementation that skipped result validation passed. ACTION: (e2) parameterised over six variants
(raises, empty, short, 37 chars, bytes, None), each asserting a SUCCESSFUL entry with a NULL token.

**A4-R4-5 -- MAJOR -- CLASS-UNRECORDED -- the claimed NOTE behaviour is not what `log_contained_note` does.**
**ACCEPTED; verified at `entry.py:251-315`.** The helper EMITS the message and attaches a note only
when the logging SINK itself raises; with a working logger there is no note, so test (g) as written
could not pass. **The helper choice stands -- the description was wrong.** ACTION: (g) asserts the
ERROR record plus unchanged exception evidence with a working sink, and the note only in the
raising-sink variant; S2.4's prose corrected.

**A4-R4-6 -- MAJOR -- RESIDUAL -- two incompatible settle signatures.** **ACCEPTED**: S2.4 requires the
four-argument form (round 3's fix) and Task 4 still directed three -- a residual of that same fix.
Corrected.

**A4-R4-7 -- MAJOR -- CLASS-UNRECORDED -- (RD-a2) patches the definition site, not the bound name.** **ACCEPTED.**
`entry.py` imports repo functions directly (`entry.py:14`), so patching the definition site would
rebind a name the service no longer consults and the capture would record nothing. ACTION: patch
`swing.trades.entry.find_trade_id_by_attempt_id`, and Task 2 pins the import style so the target and
the code cannot drift apart.

**A4-R4-8 -- MAJOR -- CLASS-UNRECORDED -- "after the ENTIRE pre-existing gauntlet" is false.** **ACCEPTED.** The
PE-anchor guard (`entry.py:1243-1287`) and the resolver's refusals live INSIDE
`_record_entry_inner`, downstream of the mint -- and S7.4 already said so, so the plan contradicted
itself. ACTION: S2.1 narrows the claim, enumerates what is upstream and what is not, and notes the
difference costs one wasted uuid4 under (S-b) but is MATERIAL under (S-d), which S2.0.1 now accepts
and tests as (e3).

**A4-R4-9 -- MAJOR -- RESIDUAL -- the RD routing packet still carried the disproved reasoning.** **ACCEPTED,
and this is the THIRD sweep of the same class** (R2-1 fixed S2.0; R3-1 fixed S7.7 and S9; this found
S7.8 still calling the index "constraint 2's enforcement"). It also adds a point neither earlier
round made: **the arithmetic prices INDEPENDENT RNG collision only** -- a systematic mint-reuse
defect whose first use ROLLED BACK is deterministic, not astronomical, and the index is silent about
it. ACTIONS: S7.8 rewritten (the index constrains simultaneously LIVE rows and nothing else); S7.7
states the arithmetic's scope; test (w) named as the instrument that actually excludes systematic
reuse.

**A4-R4-10 -- MAJOR -- RESIDUAL -- the census in S1.6/S4 contradicts Task 1's own classification.** **ACCEPTED.**
Round 3 corrected Task 1 and left S1.6 row 6 and the S4 summary claiming all 15 sites are HEAD
aliases. Measured split: 12 `run_migrations` calls + 3 direct gate calls; 8 stay pinned, 7 gain a
SECOND call. ACTIONS: row 6 and the S4 summary rewritten to the classified manifest, and **no total
is quoted at all** -- the families overlap, so a single number is a manifest that cannot be
reconciled.

**A4-R4-11 -- MAJOR -- CLASS-UNRECORDED -- S7.2 understates its own exposure.** **ACCEPTED.** S7.2 called every
probe-failure-over-a-durable-row "belt-covered" while S7.1 concedes the belt does not cover a ticker
CLOSED between attempts; the same exception applies to every alarm branch. ACTION: S7.2 qualifies
the protection as conditional on the original trade remaining open.

**A4-R4-12 -- MINOR -- RESIDUAL -- Task 1's declared first red still says `no such column`.** **ACCEPTED**;
another residual of R3-10's fix, which corrected S3 and not the task. Corrected.

### Verdict

`NEW_CRITICAL_MAJOR_FOUND` -- anchored, 2 occurrences of the one token, the other absent.

### UNCOUNTED SELF-SWEEP after round 4 (SS-1..SS-9)

Per the recipe: **state the class once, then RE-GREP THE WHOLE ARTIFACT for the superseded pattern.**
Three of round 4's twelve findings were residuals of this loop's own fixes, so before round 5 the
artifact was swept for every superseded pattern by token. **No Codex, no round number, NO effect on
convergence.** Nine hits:

- **SS-1 -- a FOURTH live copy of the disproved "the allocator is a STAMP" sentence, in S7.7.**
  The class had been "fixed" three times (S2.0 at R2-1, S7.7+S9 at R3-1, S7.8 at R4-9) and this copy
  survived all three, **because two of the three edit scripts aborted on a later assertion and never
  wrote** -- the fix was believed applied and was not. Corrected, and the fourth-time-of-asking is
  recorded in the entry itself.
- **SS-2** -- S7.1 still named the surviving residual by the retired `unresolved` enum.
- **SS-3** -- S9 RD item 2 still carried the SUPERSEDED cost argument that `A4-R2-7` disproved
  (another victim of the same aborted script).
- **SS-4/5/6** -- the shared helper is named `_observe_resolution` in S2.2 and `_try_rollback` in
  three other places (S3 (k2), S4's manifest, Task 3). Unified.
- **SS-7** -- S1.4 said "the three OBSERVATIONS" where the count is four observations / three new
  fields.
- **SS-8/9** -- two surviving `Pre-fix: n/a` entries in (r3) and (h), which `A4-R1-9` had ruled must
  state the concrete red (`TypeError` and an import failure respectively).

**PROCESS NOTE FOR THE ORCHESTRATOR, because it explains the residual rate:** three edit scripts in
this loop asserted a list of substitutions and aborted mid-list, writing NOTHING while printing
enough output to look partially successful. Two rounds' worth of "already fixed" items were
therefore still live. The sweep is what caught it; the per-round transcript would not have.

---

## Round 5 -- THE MANDATED CHECK-IN ROUND. THE LOOP IS STOPPED HERE.

Artifact frozen; sha256 `56d1441ef5008e5c1abdc8783b3da1e75328d725f15d2eb82541bbc5abd22d6e`
(151,062 bytes). Rounds 1-4 artifacts moved out of the worktree first.

### Mechanical assertions -- ALL FIVE PASS

model `gpt-5.6-sol`; effort `high`; `^ERROR` = **0**; `^tokens used` = **1**;
`^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0**. Exit `0` measured; transcript
1,069,399 bytes; process exited before the file was read. **The reviewer self-reported: "No
safety-layer refusal or rewriting occurred. I reviewed base commit `edfea928...` and did not read any
`.codex*` or `.copowers*` file."** It also self-reported that it could NOT re-run the Python 3.14
measurements from WSL (the Windows interpreter was unreachable through the interop socket), so its
findings derive from source, the migration runner, the tests and the plan's own state machine -- a
LIMITATION OF THE ROUND worth carrying into the gate decision, since three of this loop's strongest
findings came from re-measurement.

### Counts

**12 findings: 1 CRITICAL, 7 MAJOR, 4 MINOR. NEW = 12. REOPENED = 0. REVERTED = 0.**

### The one finding FIXED before stopping

**A4-R5-1 -- CRITICAL -- RESIDUAL -- the mandatory immutability trigger is absent from every
implementation-bearing manifest.** **ACCEPTED AND FIXED.** Round 4 added
`trg_trades_attempt_id_immutable` to S2.0's prose and to the (m7) roster row -- and to NOTHING an
executor reads as a work item: not S4's migration description, not Task 1's DDL checklist, not Task
1's test list, not the reversibility header, not S7.9's "one column and one index", not S9's ask to
CHARC. **An executor following the ladder would have shipped exactly the `A4-R4-1` false-success
path the prose calls critical.** It is the round-4 residual class again, one layer up: the DECISION
propagated into the argument and not into the work. Fixed in all six places, with (m7) and its
remove-the-trigger mutation proof made a gate on Task 1 going green.

### The eleven findings ADJUDICATED AND LEFT OPEN at the gate

Each is real; none is fixed, because the gate is here. Summarised so the orchestrator can weigh
continuation rather than take my word for the shape of the remainder:

- **A4-R5-2 -- MAJOR -- CLASS-UNRECORDED -- the deferred path cannot OBSERVE whether `__exit__`'s rollback raised.** Sharp
  and, I think, correct: `cleanup_raised` is knowable only for rollbacks the wrapper itself issues,
  and on the deferred path the rollback happens inside `__exit__`. So RD's rule (i) is enforced on
  one path and approximated on the other. **This is a DESIGN fork** (own the deferred
  commit/rollback explicitly, or declare the asymmetry) and is exactly the kind of item the gate
  exists to route rather than let an author settle at the keyboard.
- **A4-R5-3 -- MAJOR -- RESIDUAL -- "no rollback on the deferred path" contradicts `_observe_resolution`.** Correct.
  The residual arm DOES issue a rollback when `__exit__` left the transaction open; preserving the
  exception identity is not the same as leaving behaviour unchanged. Round 2 over-corrected round
  1's over-claim.
- **A4-R5-4 -- MAJOR -- RESIDUAL -- (w) cannot make systematic reuse "impossible by construction".** Correct: (w)
  stubs the mint, so it cannot detect a real mint that caches. Needs two attempts with `uuid.uuid4`
  controlled one level below, or the claim narrowed. **This partly undoes R4-9's fix**, which named
  (w) as the instrument that excludes systematic reuse.
- **A4-R5-5 -- MAJOR -- RESIDUAL -- Tasks 1 and 2 each say the other owns the mint/threading.** A residual of R4-2's
  fix.
- **A4-R5-6 -- MAJOR -- CLASS-UNRECORDED -- (m7) is defeated by the CHECK before it reaches the trigger.** Correct and
  embarrassing: the test's `UPDATE ... SET attempt_id = 'x'` trips the length CHECK, so it would go
  green against a tree with NO trigger. The mutation proof would have caught it; the test as
  specified would not.
- **A4-R5-7 -- MAJOR -- CLASS-UNRECORDED -- the identity-failure WARNING can itself fail an ordinary entry.** The
  containment covers the mint and the path read; the logging that reports their failure is outside
  it. The arc's own R11-03 class, inside the arc's own fix.
- **A4-R5-8 -- MAJOR -- CLASS-UNRECORDED -- (e2)'s variant count is internally inconsistent** (six named, more listed).
- **A4-R5-9 -- MINOR -- CLASS-UNRECORDED -- MEASURED (2) generalises "a fresh reader is not blocked" beyond the lock state
  actually measured**, and MEASURED (3) is the counterexample in the same plan.
- **A4-R5-10 -- MINOR -- CLASS-UNRECORDED -- (m2)'s stated current-tree pre-fix outcome is wrong.**
- **A4-R5-11 -- MINOR -- CLASS-UNRECORDED -- the version-mirror sweep does not cover narrative/prose mirrors.**
- **A4-R5-12 -- MINOR -- CLASS-UNRECORDED -- stale cross-references (S8.7, Task 5).**

### Verdict and GATE STATE

`NEW_CRITICAL_MAJOR_FOUND` -- anchored, 2 occurrences of the one token, the other absent.

**THE LOOP IS STOPPED AT THE MANDATED ROUND-5 GATE AND IS NOT CONVERGED.** The recipe's own
continuation criterion -- *"Continue ONLY if NEW, IN-SCOPE, NON-REOPENED critical/major findings are
still arriving"* -- reads CONTINUE on the composition (45 findings over five rounds: 3 CRITICAL, 32
MAJOR, 10 MINOR; ZERO reopened, ZERO reverted, every round in scope). **That is a report, not a
decision.** Two facts belong in the orchestrator's hands alongside it: the rate is not decaying
(10 / 9 / 12 / 12 / 12), and a growing share are RESIDUALS OF THIS LOOP'S OWN FIXES rather than
defects in the original design -- the Expansion-#13 cascade signature, which the recipe says the
gate-holder may answer with a dedicated self-sweep plus ONE confirming round instead of another
review round.

---

## AMENDMENT PASS (2026-09-06) -- both director rulings landed

**RD RULED: `uuid4` SATISFIES constraint 2.** Canonical reading, binding on future appeals: *"never
reusable" = the mechanism must contain NO PATH THAT REISSUES a token.* The rowid failed because the
ENGINE hands a rolled-back id to the next insert -- reuse is an active, designed-in mechanism -- while
a `uuid4` repetition is an RNG failure, not a behaviour of the mechanism; and collision-resistance is
already this system's admissibility standard (sha256-pinned amendment text, digest-pinned broker
snapshots). Three riders landed: S7.7 widened, RD-a/RD-b unchanged plus (RD-b2) in its (S-b)
polarity, and **(S-d) BANKED IN FULL** rather than deleted (a D46 call: more machinery, a second
commit surface and a separate connection on the money path, against a failure with no mechanism and
no observed instance).

**CHARC RATIFIED five items with ONE CONDITION.** Migration 0038 as shaped; the LOCK-A amendment;
the `<= 37` -> `<= 38` ceiling opened for 0038 only; the backup gate and expected-tables set; and the
S2.0 divergence (he verified 57/56/`{risk_policy_id_at_lock}` on the live DB himself, and made the
drift comparator's EQUALITY -- never superset -- the mandatory member of the mirror set).
**THE CONDITION: S8.6 is NOT banked; the corrector's typed refusal SHIPS**, widening the envelope by
exactly `swing/trades/reconciliation_auto_correct.py`. His ground: *"I cannot rule the class binding
one week and bank its next instance because the plan's envelope was drawn one module short."* Plus
two jurisdiction notes for the migration header (the REPLACE family grepped empty against `trades`
-> a future REPLACE writer is a DECLARED BREACH; 22-B Demand A rebuilds `trades` and must re-create
index AND trigger).

### THE LOAD-BEARING VERIFICATION RD DEMANDED -- ONE HALF FAILED, ROUTED BACK

He attached the S7.7 detection story as load-bearing with an explicit stop-and-route instruction.
Both halves were run against a model carrying the real CHECK, both real indexes and the real mapper:

- **"A committed-duplicate token is REFUSED LOUDLY by the UNIQUE index" -- VERIFIED**, with a
  dependency worth his attention: the message is `UNIQUE constraint failed: trades.attempt_id`, which
  **the SHIPPED mapper converts into "Already an open position in BBB (race-detected)"** -- loud, and
  false about a position that does not exist. It is TRUTHFULLY loud only because S2.5 narrows the
  match to `trades.ticker`, a fix that entered this plan in round 1 for an unrelated reason.
- **"The undetectable case has no false-confirm mechanism, because a rolled-back token leaves no row
  to confirm" -- NOT VERIFIED. THE OPPOSITE WAS REPRODUCED.** The premise is true at the instant of
  rollback and does not survive to probe time: A rolls back (zero rows carry X), a second connection
  mints the same X for the SAME ticker and COMMITS, A's probe finds that row, **ticker corroboration
  PASSES**, and A returns SUCCESS naming a trade it did not write.

**His RULING is unaffected** -- it rests on the no-reissue-path reading, which verifies. What failed
is the rider's stated REASON, and the plan states the verified version instead. ROUTED at S9 RD
item 2.

---

## Round 6 -- run on the frozen final shape

Artifact frozen; sha256 `7e7f9a7e4cd7b583dfb0303f38e832f0872873dec0f04e72886c497ed6538b33`
(169,779 bytes). Rounds 1-5 artifacts moved out of the worktree first. The prompt carried an
amendment-context block directing the reviewer at the newest text and **requiring each finding to be
labelled NEW GROUND or RESIDUAL**, because that classification decides whether the loop terminates.

### Mechanical assertions -- ALL FIVE PASS

model `gpt-5.6-sol`; effort `high`; `^ERROR` = **0**; `^tokens used` = **1** (307,420);
`^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0**. Exit `0` measured; transcript
1,102,235 bytes; process exited before the file was read. No content-filter event.

### Counts

**13 findings: 0 CRITICAL, 11 MAJOR, 2 MINOR. NEW = 13. REOPENED = 0. REVERTED = 0.**
**Reviewer-labelled: 6 NEW GROUND, 7 RESIDUAL OF THE AMENDMENTS.**
**First round of the loop with ZERO criticals.**

### Per-finding disposition -- 11 FIXED, 2 ROUTED

**NEW GROUND (6)**

**A4-R6-4 -- MAJOR -- CLASS-UNRECORDED -- a 36-BYTE BLOB passes `length()=36` and shares the index with its text twin.**
**ACCEPTED; REPRODUCED.** `[(1, 'text', 36), (2, 'blob', 36)]` -- two live rows, one token,
**falsifying S2.0's own "at most ONE LIVE row per token" at the schema boundary.** The
`typeof(attempt_id)='text'` guard rejects it (measured). **The asymmetry is the lesson:** round 4
added a `typeof` guard to the BANKED integer branch and left the SHIPPING text branch without one --
the fix was applied to the design that is not being built. **FIXED:** CHECK widened, Python mirror is
`isinstance(str)`, and (m1)/(m6)/(r3)/(e2) each gain a BLOB case.

**A4-R6-5 -- MAJOR -- CLASS-UNRECORDED -- no test proves the mint draws from `uuid.uuid4` at all.** **ACCEPTED.** Every
identity row patches `_mint_attempt_token` ITSELF, so **a production mint returning a constant valid
36-character string passes all of them**, and LOCK-A only checks validity and non-NULLity. That is
exactly the systematic-reuse defect S7.8 calls deterministic. **FIXED:** new test **(w2)** patches
`uuid.uuid4` one level below, asserts one provider call per mint and exact stringification, and
drives TWO attempts (first rolled back) requiring DISTINCT tokens. **S7.8's "impossible by
construction" claim is struck** -- that phrase belongs to the banked allocator and to nothing shipped.

**A4-R6-6 -- MAJOR -- CLASS-UNRECORDED -- "typed refusal" does not reach the operator.** **ACCEPTED; verified at the
source.** `ReservedJournalFieldError` inherits **directly from `Exception`**
(`reconciliation_auto_correct.py:109`), and both callers reach a `ValueError` handler with no handler
for it (`swing/cli.py:3929` region, `swing/web/routes/reconcile.py:1640`) -- so a service-only typed
refusal surfaces as an uncaught CLI traceback and a web 500. **That is the same operator experience
CHARC's condition exists to replace, one layer out.** **FIXED:** the sibling type is
`ImmutableJournalFieldError(ValueError)`, reaching both handlers with **no production caller edit**,
plus delivery tests through the unchanged CLI and web surfaces.

**A4-R6-7 -- MAJOR -- CLASS-UNRECORDED -- a one-field corrector test permits a key-order-sensitive refusal.**
**ACCEPTED; verified at the source.** The module preflights whole payloads precisely because it
applies fields SEQUENTIALLY -- its own comment says a per-field-only check made refusal depend on
**JSON KEY ORDER**. A backstop-only implementation executes an earlier UPDATE before discovering
`attempt_id` second. **FIXED:** the check goes in BOTH `_preflight_reserved_transitions` and
`_update_journal_field` sharing one predicate and message, plus a multi-field test with `attempt_id`
LAST asserting ZERO journal UPDATEs issued.

**A4-R6-10 -- MAJOR -- CLASS-UNRECORDED -- S7.12 calls the terminal-return windows "belt-covered" unconditionally.**
**ACCEPTED** -- S7.2 already concedes belt coverage lapses when the position is closed between
attempts, and the same exception applies here. **FIXED:** qualified identically in all three places.

**A4-R6-11 -- MAJOR -- CLASS-UNRECORDED -- "fork" is not a correlated-state mechanism for this implementation.**
**ACCEPTED; MEASURED from CPython 3.14 source: `uuid4` is `int.from_bytes(os.urandom(16))` PER
CALL**, with no process-local PRNG state to clone. So a POSIX port that merely acquires `fork` would
fire the re-open trigger with **no hazard present** and activate a materially more expensive design
on the money path. **FIXED in the plan AND ROUTED:** bare `fork` struck; the surviving triggers are a
GENERATOR change away from `os.urandom` or a measured condition duplicating the OS entropy stream.
**This is the SECOND RD rider clause that failed verification** and it is routed with the first.

**RESIDUAL OF THE AMENDMENTS (7)**

**A4-R6-1 -- MAJOR -- CLASS-UNRECORDED -- the plan calls itself final while holding an item RD told it to stop-and-route
on.** **ACCEPTED; the contradiction was mine.** **FIXED:** the status block now says plainly that the
plan is **NOT AUTHORIZED TO EXECUTE**, names both open rider clauses, and states that RD's ruling
itself is unaffected -- what is open is wording he owns.

**A4-R6-2 -- MAJOR -- CLASS-UNRECORDED -- the mint "moved into Task 1" in two prose statements and in no checklist.**
**ACCEPTED.** Task 0b and Task 2's preamble both announced the move; Task 1 had no such checkbox and
Task 2 still scheduled the work. **FIXED:** the mint, `_begin_attempt_identity` and the threading are
now actual Task 1 checkboxes; Task 2 keeps only the safety behaviour.

**A4-R6-3 -- MAJOR -- CLASS-UNRECORDED -- Task 1 required all of (m7) including the half Task 1b implements.**
**ACCEPTED** -- Task 1 could not reach green in its own prescribed order. **FIXED:** half 1 (schema
trigger + mutation proof) gates Task 1; half 2 (typed refusal) belongs to Task 1b and is explicitly
NOT required earlier.

**A4-R6-8 -- MAJOR -- CLASS-UNRECORDED -- S7.1 treats both refusal branches as indeterminate.** **ACCEPTED.** For
`rolled_back + cleanup_raised` the rollback TOOK EFFECT, the row is provably gone, and nothing can
commit it later -- S2.4 and S9 already had this right, so the entry overstated the arc's own residual.
**FIXED:** the two branches are separated, with only `still_open` carrying the possibly-durable-later
exposure.

**A4-R6-9 -- MAJOR -- CLASS-UNRECORDED -- "(e2)'s SIX variants" enumerates seven plus an interrupt control.**
**ACCEPTED** -- a manifest an executor can under-read by one. **FIXED:** stated as **eight contained
variants (seven plus the new BLOB case) plus one interrupt-propagation control**, enumerated
identically in S3 and Task 2 so the two cannot drift.

**A4-R6-12 -- MINOR -- CLASS-UNRECORDED -- the (m7) rationale's execution-order claim is false.** **ACCEPTED;
REPRODUCED.** A BEFORE UPDATE trigger fires FIRST: both an invalid and a valid value abort with the
trigger's `immutable` message, so `'x'` never "trips the CHECK before reaching the trigger". The
test's discriminator was sound anyway. **FIXED:** the false ordering claim is replaced -- a valid
token ISOLATES the trigger, and the MUTATION PROOF is the discriminator. *(Note: this partly
disproves `A4-R5-6`'s stated reason from the previous round, while its prescribed fix stands.)*

**A4-R6-13 -- MINOR -- CLASS-UNRECORDED -- six stale cross-references.** **ACCEPTED, all six FIXED:** S2.0's two
"routed"-not-"ruled" statements, the drift comparator attributed to Task 2 after the merge into
Task 1, (m1)'s self-contradicting pre-fix sentence, S4's test manifest omitting (m7) and (w2), S9
item 1 naming only `DROP INDEX`, and S9 item 4's `S8.6` -> `S8.7` renumbering.

### Verdict and STOP

`NEW_CRITICAL_MAJOR_FOUND` -- anchored, 2 occurrences of the one token, the other absent.

**ROUND 7 WAS NOT OPENED.** The gate-holder's stop rule was *"if it returns residuals of these
amendments rather than new ground, STOP and disposition -- do not open round 7."* Round 6 returned a
**MIX** (6 new ground, 7 residual), which is not the rule's stated case; **opening round 7 was not
authorized, so the mixed result is reported to the gate-holder rather than resolved by the author.**
All 13 are dispositioned: **11 FIXED, 2 ROUTED to RD** (both failed rider clauses).

**Trend for the gate-holder:** 10 / 9 / 12 / 12 / 12 / 13 findings; CRITICALs 1 / 0 / 1 / 1 / 1 /
**0**; residual share rising to 7 of 13. The new ground round 6 did find was concentrated in the
AMENDMENTS -- the newest and least-reviewed text -- which is what that round was commissioned for,
and three of its four sharpest findings came from RE-MEASUREMENT rather than reading.

---

## POST-ROUND-6 SELF-AUDIT (orchestrator-directed, deterministic, uncounted)

**68 probes** over every ACCEPTED disposition in rounds 1-6, aimed at a known editing defect (three
earlier edit scripts asserted a substitution list, aborted mid-list, and wrote NOTHING while printing
partial success).

**Result: 3 probe misses, all three resolved as STALE PROBE WORDING** -- the fixes were present under
headings later legitimately reworded. **Plus TWO REAL GAPS, found by extending the probe list beyond
the dispositions:**

- **Task 2's commit subject still described work `A4-R6-2` had moved to Task 1** -- the `A4-R3-11`
  class re-created by round 6's own fix.
- **Test (w2) was specified in S3, listed in S4's manifest and cited in S7.8, and scheduled in NO
  TASK CHECKLIST AT ALL** -- `A4-R5-1`'s class on a different object.

Both fixed. A third, partial gap (S4's summary lacked the 12+3 instrument split) was tightened.

**THE AUDIT'S OWN LIMITATION, AND ROUND 7 PROVED IT COSTLY.** The probe list carried **ONE probe per
finding**, so it could only detect a fix written NOWHERE -- never one written in one of several named
locations. `A4-R7-1` is exactly that: the `typeof` fix was present in S2.0's prose (which the probe
found) and **absent from Task 1's DDL, the repo validator, (m1), (m6) and (r3)**. **A single-probe
audit cannot see a partially-propagated fix**, which is the dominant failure mode of this loop. The
round-7 audit was rebuilt PER-LOCATION (36 probes over 12 findings) and is the form to use hereafter.

---

## Round 7

Artifact frozen; sha256 `5e5e02fe54227a96de5e0858f6b020bf5dbd5e7c3dbb354f6a241ab135fc748f`
(182,830 bytes). The prompt carried the audit's result and an explicit request to report any
claimed-fix-not-present.

### Mechanical assertions -- ALL FIVE PASS

model `gpt-5.6-sol`; effort `high`; `^ERROR` = **0**; `^tokens used` = **1** (413,949);
`^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0**. Exit `0` MEASURED; transcript
1,320,409 bytes; process exit confirmed before the file was read or judged. No content-filter event.

### Counts

**12 findings: 0 CRITICAL, 9 MAJOR, 3 MINOR. NEW = 12. REOPENED = 0. REVERTED = 0.**
**Reviewer-labelled: 6 NEW GROUND, 6 RESIDUAL. ALL 12 FIXED.**

### Dispositions

**A4-R7-1 -- MAJOR -- RESIDUAL -- THE CLAIMED `typeof` FIX WAS ABSENT FROM THE EXECUTABLE PLAN.** The finding
the round was asked for, and the self-audit MISSED it. S2.0 claimed the validator and tests were
amended; Task 1's DDL still ordered the length-only CHECK, the repo validator still specified length
without `isinstance`, (m1) had no BLOB case, **(m6) asserted only the length fragment so it would
have PASSED the defective DDL**, and (r3) tested only strings. **FIXED at all five locations.**

**A4-R7-2 -- MAJOR -- RESIDUAL -- Task 1 and Task 2 could not both have honest red/green contracts.** Either
Task 1 implemented S2.1 fully (making Task 2's (e2) already green) or it committed a helper that
could fail an otherwise successful entry. Task 2 also ordered an import whose first consumer arrives
at Task 4 -- an unused import breaking the Ruff-clean gate. **FIXED:** Task 1 owns the complete
helper and (e)/(e2)/(w2); **Task 2 WITHDRAWN as a stub with numbering kept stable** (renumbering
produced `A4-R3-11` then `A4-R7-11`; a stub costs a paragraph, a renumber costs a sweep that has
failed twice); the import moves to Task 4.

**A4-R7-3 -- MAJOR -- RESIDUAL -- Task 1b's three test classes had no ids, result shapes or files.**
**FIXED:** new S3 rows **(m8a)** typed service refusal, **(m8b)** multi-field preflight asserting
ZERO journal UPDATEs, **(m8c)** delivery through UNCHANGED callers with mappings read at source
(CLI `ValueError` -> `UsageError` -> **exit 2**; web -> **status 400**). Task 1b's first red is
(m8a)'s `sqlite3.IntegrityError`; (m7) half 2 is superseded, its red base gone once Task 1 lands.

**A4-R7-4 -- MAJOR -- RESIDUAL -- the checklist named ONE open rider while the front matter and S9 said TWO.**
The claimed-fix-not-present class applied to governance. **FIXED:** two unchecked Task 0 boxes; S9's
heading and body corrected.

**A4-R7-5 -- MAJOR -- RESIDUAL -- S7.1 re-created `A4-R6-8` one round after closing it** ("in both" a later
commit could make the row durable). **FIXED:** scoped to `still_open` alone.

**A4-R7-6 -- MAJOR -- NEW GROUND -- the quoted census command does not produce the claimed count.**
**REPRODUCED: five hits, not three** -- the three era-branches plus `INSERT INTO trades_new` (the
Phase-7 rebuild, a DIFFERENT table the substring matches) plus a `__pycache__` binary match. The
"state what your grep PROVES" rule failing on the bullet that invokes it. **FIXED:** real output
reported; (r5) now specifies a word-boundary table-token parser excluding caches, without which the
walk would count `trades_new` as an unreasoned writer.

**A4-R7-7 -- MAJOR -- NEW GROUND -- S7.11's "independent backstops" share the walk's blind spot.** A
fragmented writer inserting into the existing schema without `attempt_id` changes no column ((r4)
green), does not touch `record_entry` ((e) green), and evades the walk by definition. **FIXED:** the
entry states what each instrument actually covers and declares **one heuristic guard, no independent
backstop** -- a smaller claim, and the one the evidence supports.

**A4-R7-8 -- MAJOR -- NEW GROUND -- `resolution` was INFERRED on the returning rollback arm.** The contract
says re-read after ANY rollback attempt; the pseudocode re-read only on the raising arm and assigned
`"rolled_back"` whenever the call returned -- so a rollback returning WITHOUT effect is misclassified
and **ADMITS the probe**. No fixture covered it. **FIXED:** re-read on both arms plus a third RD-a1
fixture asserting `still_open` and zero probe calls.

**A4-R7-9 -- MAJOR -- NEW GROUND -- (r2)'s "contained WARNING" was asserted and never tested.**
`swing/data/repos/trades.py` has no logger and no containment helper, so a plain `log.warning`
passes the specified test and aborts the transaction when the sink raises -- failing a money-bearing
entry, which S7.5's reason forbids. **FIXED:** containment specified in Task 1; raising-handler
variant added to (r2).

**A4-R7-10 -- MINOR -- CLASS-UNRECORDED -- `_RESERVED_JOURNAL_FIELDS` has SEVEN members, not five** (verified; they span
`fills` as well as `trades`). **FIXED.**

**A4-R7-11 -- MINOR -- CLASS-UNRECORDED -- stale task/routing references survived the self-audit** (Task 6 -> Tasks 4
and 5; S9 item 6 -> 5; "single DROP INDEX" vs both drops). **All FIXED**, and they are why Task 2 was
withdrawn as a stub rather than renumbered.

**A4-R7-12 -- MINOR -- CLASS-UNRECORDED -- a SEVENTH mirror spelling: semantic names and comments.**
`def test_expected_schema_version_is_37()` whose body is a HEAD assertion, and the comment *"the
ceiling is now 37"* (both verified). **FIXED** as a named spelling in the sweep.

### A REGRESSION THE POST-ROUND-7 AUDIT CAUGHT IN ITS OWN FIX

Withdrawing Task 2 **dropped `A4-R6-9`'s requirement** that (e2) enumerate all eight variants from
S3's list -- that instruction lived only in Task 2's checklist. Found by re-running the audit looking
for exactly that class, and restored into Task 1. *A withdrawal is an edit, and an edit can lose a
fix as easily as a rewrite can.*

### Verdict

`NEW_CRITICAL_MAJOR_FOUND` -- anchored, 2 occurrences of the one token, the other absent.
**STOPPED BY INSTRUCTION. Round 8 not opened -- that call is the gate-holder's.**

**Running totals across seven counted rounds: 70 findings (3 CRITICAL, 41 MAJOR, 16 MINOR), ZERO
reopened, ZERO reverted. Token spend 2,273,873.**

---

## PRE-ROUND-8 DETERMINISTIC CONSISTENCY SWEEP (orchestrator-directed, uncounted)

Built as a PARSER, not greps: task headings and spans, commit subjects vs enclosing task, task
cross-references, test-ID definitions vs roster vs task schedules vs S4 file manifest (with numeric
AND letter range expansion), section references, and fragile counts. Script preserved at
`plan_consistency_sweep.py`.

**Structural checks that PASSED:** every commit subject matches its enclosing task; every `Task N`
reference resolves; every section reference resolves.

**THREE BOOKKEEPING DEFECTS FOUND AND FIXED:**
- **`(m8)` heading vs `(m8a-c)` roster id** -- the S3 heading defined an id nothing else used.
- **`(w2)` had an S3 heading and was ABSENT from the S3 roster table** -- the roster is meant to be
  the complete list.
- **`(d)`, `(i)`, `(j)` were scheduled in tasks with NO FILE in the S4 manifest** -- they live in
  `test_22a_task9_entry_wiring.py` and the manifest named only `(c)`.

**The sweep then earned its keep twice more DURING round 8's fixes:** it caught the new test `(r7)`
defined-but-unscheduled and unrostered **on the very edit that introduced it**, and the per-location
audit's stale probe exposed **two further live instances of the rule-(i) overclaim** -- one of them
in the S9 packet going to RD, which would have told him rule (i) IS literal while the newly routed
item 8 told him it is not.

---

## Round 8

Artifact frozen; sha256 `1f1f564abf1ce3c764a8ae550f950056096fc8977e4e5eb2252c281b1889f441`
(192,767 bytes). Commissioned to review ROUND 7's OWN TWELVE FIXES -- including a schema DDL change
-- because shipping a plan whose last round's fixes are unreviewed is the trap the Demand C handoff
flagged against itself.

### Mechanical assertions -- ALL FIVE PASS

model `gpt-5.6-sol`; effort `high`; `^ERROR` = **0**; `^tokens used` = **1** (349,176);
`^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0**. Exit `0` MEASURED; transcript
1,382,826 bytes; process exit confirmed before the file was read. No content-filter event.

### Counts

**6 findings: 0 CRITICAL, 5 MAJOR, 1 MINOR. NEW = 6. REOPENED = 0. REVERTED = 0.**
**Reviewer-labelled: 2 NEW GROUND, 4 RESIDUAL.** Down from 13 and 12.

**What SURVIVED verification, stated because it is the round's actual product:** the additive DDL,
the `typeof(...)='text'` guard, the Python `isinstance` mirror, the corrector-refusal shape, the
caller delivery mappings and the backup-table-set derivation. **The reviewer found NO new
deterministic false-success path over a non-durable row.**

### Dispositions -- 5 FIXED, 1 FIXED-AND-ROUTED

**A4-R8-1 -- MAJOR -- RESIDUAL -- RULE (i) IS NOT ACTUALLY ENFORCED ON THE DEFERRED PATH, AND THE
PLAN CLAIMED "LITERALLY" FOR TWO ROUNDS.** `sqlite3.Connection.__exit__` owns the deferred commit AND
its rollback, so `cleanup_raised` cannot be an observation there. Two sequences defeat it: the
internal rollback takes effect then raises (`in_transaction` False -> `not_needed`), or it raises
before taking effect and the wrapper's OWN retry succeeds (`rolled_back`). **In both, a rollback
raised and the probe is ADMITTED.**
**PARTIALLY FIXED, DELIBERATELY:** the false claim is corrected everywhere it appeared (S2.4's gate,
S7.1's branch note, and **the S9 packet going to RD, which would otherwise have told him rule (i) IS
literal while the newly routed item told him it is not**); the asymmetry is DECLARED at **S7.15**
with both sequences and the measured cost (**in both, the row is provably GONE, so the probe returns
ABSENT and the outcome is identical -- what is unenforced is the RULE, not the result**).
**The DESIGN CHANGE IS ROUTED (S9 item 8), not taken:** the only fix is to own the deferred commit
and rollback explicitly, replacing `with conn:` and reproducing its exception semantics by hand, **on
the path 22-A locked byte-for-byte and that round 6 concluded should be observed rather than
re-plumbed.** A plan that re-plumbs a locked path on its own authority is the failure this arc has
already routed twice.

**A4-R8-2 -- MAJOR -- RESIDUAL -- round 7's third RD-a1 fixture was added to S3 and to nothing
else.** The section still opened "TWO fixtures" and Task 4 still scheduled "BOTH shapes" -- so the
executable manifest permitted omitting **the only fixture that discriminates round 7's own re-read
correction.** The propagation failure, one round after the propagation failure. **FIXED** in both
places.

**A4-R8-3 -- MAJOR -- NEW GROUND -- (r2)'s post-fix assertion was IMPOSSIBLE.** It asserted
`attempt_id IS NULL` **on a v37 database**, where SQL naming that column raises
`no such column` -- the migration is what creates it. Task 1 could not have reached its declared
green. **FIXED:** the v37 assertions are now what a v37 database can answer (row count, returned id,
`PRAGMA table_info` lacking the column), with the NULL reading written as an explicit second step
after migrating.

**A4-R8-4 -- MAJOR -- RESIDUAL -- round 7's hostile-sink coverage reached the REPO warning and not
the THREE SERVICE-side ones.** A plain `log.warning(...)` in `_begin_attempt_identity` passes every
(e2) variant and then fails an entry when a handler raises -- the exact claim S2.1 makes. **FIXED:**
all three arms route through ONE containment helper and each is asserted with a raising handler.

**A4-R8-5 -- MAJOR -- NEW GROUND -- nothing tested the probe's schema-aware branch.** An
implementation that unconditionally executes `WHERE attempt_id = ?` passes the whole suite, because
`_settle_by_attempt_identity` contains the `OperationalError` and re-raises the original anyway --
**so the suite cannot tell ABSENCE from INTERNAL PROBE FAILURE**, and S7.5's stated consequence is
untested. **FIXED:** new test **(r7)** asserting `find_trade_id_by_attempt_id` returns `None` WITHOUT
raising on v37.

**A4-R8-6 -- MINOR -- RESIDUAL -- stale statements survived the consistency sweep:** an (RD-a2)
reference to withdrawn Task 2, a DUPLICATED `### (r1)` heading (damage from my own (m8) insertion),
and S11 still saying six rounds ran and round 7 was not opened. **All FIXED**, and S11 now carries
rounds 7 and 8, both uncounted sweeps, and the eight-round token sum.

### Verdict

`NEW_CRITICAL_MAJOR_FOUND` -- anchored, 2 occurrences of the one token, the other absent.
**STOPPED BY INSTRUCTION. Round 9 not opened.**

**THE REVIEWER'S OWN JUDGEMENT, asked for directly and recorded verbatim because it DISSENTS from the
falling finding-count:** *"this plan is still yielding substantive design and evidence defects, not
mainly bookkeeping and prose; the deferred rollback-observation hole alone requires a
transaction-path design change."*

**RUNNING TOTALS, eight counted rounds: 76 findings -- 3 CRITICAL, 46 MAJOR, 17 MINOR. ZERO
reopened, ZERO reverted. Token spend 2,623,049.**

---

## AMENDMENT PASS 2 (2026-09-06) -- RD ruled all three open items

**1. S7.7 half A CONFIRMED, with a PRECONDITION attached.** The committed-duplicate refusal is loud
AND legible **only in combination with S2.5's mapper narrowing**; without it the refusal is loud but
mislabelled as a position race that does not exist. **S2.5 is therefore LOAD-BEARING for his ruling**
and gained a discriminating pin: **(r6) now asserts the TYPED SURFACE** of an attempt_id UNIQUE
failure, never the absence of the wrong message -- a test written as "no DuplicateOpenPositionError
was raised" would pass an implementation that raised nothing at all.

**2. S7.7 half B CONFIRMED**, with his absolute replaced by his own bound: the false-confirm path
EXISTS but lives entirely inside the collision event. *(Round 9 then found the replacement wording
itself is wrong -- see A4-R9-4.)*

**3. fork STRUCK on this plan's measurement.** Exactly two surviving triggers; **VM snapshot-resume
recorded as an INSTANCE of the entropy-duplication trigger, never as an independent one.**

**4. Item 3 = (a) ACCEPT, on HIS ground, which REPLACES the plan's.** The plan argued "the outcome
happens to be the same"; he declined that as self-standing and grounded it in **constraint 3**: rule
(i) exists to prevent R10-02's self-quote, and on the deferred path that read cannot happen at all
because the probe runs on a FRESH connection. S7.15 reframed from ACCEPTED risk to **COVERED risk --
an asymmetry of OBSERVABILITY, not of outcomes** -- and two tests **(k4a)/(k4b)** added to pin the
OUTCOME of each unobservable sequence. Option (b) REJECTED as the D46 direction.

Consistency sweep re-run: **clean, 39 tests defined / scheduled / manifested.** Per-location audit
over the amendments: **25 probes, zero missing.**

---

## Round 9 -- THE CONVERGENCE ROUND. IT DID NOT CONVERGE.

### FIRST ATTEMPT DISQUALIFIED -- provider capacity, and the footer lied again

exit **1**; **two anchored ^ERROR "Selected model is at capacity" lines**; **NO verdict token at
all** (NO_NEW=0, FOUND=0); transcript truncated mid-way through dumping a source file -- **and a
`tokens used` footer present anyway (316,797 tokens).** Disqualified by assertions 3 and 5.
**This is the cleanest demonstration in the whole loop of why the footer alone is not a completion
signal.** Artifact hash re-verified UNCHANGED before the re-run, so the re-run is the same round on
the same frozen shape. Transcript preserved as `.codex-review-r9-DISQUALIFIED-capacity.txt`.

### Re-run -- ALL FIVE ASSERTIONS PASS

model gpt-5.6-sol; effort high; ^ERROR = **0**; ^tokens used = **1** (463,310);
^NEW_CRITICAL_MAJOR_FOUND = **2**, ^NO_NEW_CRITICAL_MAJOR = **0**. Exit **0** MEASURED; transcript
1,080,516 bytes; process exit confirmed. Frozen at
`9d57c1b50b57cadae756818541ab7b107611f8967598d0c233fd1d6cc3cb80ba`.

### Counts

**9 findings: 0 CRITICAL, 9 MAJOR, 0 MINOR. 6 NEW GROUND, 3 RESIDUAL. Zero reopened, zero reverted.**

### The three bearing on rulings just made -- ROUTED, NOT AMENDED

**A4-R9-2 -- MAJOR -- NEW GROUND -- the premise under RD's item-3 acceptance may be FALSE.** His ruling rests on *the
wrapper cannot see whether __exit__'s internal rollback failed*. The reviewer cites CPython 3.14.2
connection.c as saving the commit exception, calling rollback, and **chaining the two if rollback
fails** -- an observable signal, and a cheaper third option nobody considered. **MEASURED HERE, and
the measurement is PARTIAL:** in the commit-fails / rollback-SUCCEEDS case there is **no chain**
(__context__ and __cause__ both None; Python 3.14.2, SQLite 3.50.4) -- consistent with chaining
marking the rollback-FAILS branch, which **I could not force natively.** Not refuted, not confirmed.

**A4-R9-3 -- MAJOR -- NEW GROUND -- S7.15's "zero outcome delta" is false when COMBINED with S7.7.** Rollback takes effect
then raises -> `not_needed` -> **before the probe, B commits the same token for the same ticker (the
collision event S7.7 accepts)** -> the fresh probe finds B and returns false SUCCESS, where literal
enforcement would have alarmed. **Freshness prevents self-quotation; it does not prevent false
attribution after another transaction commits the colliding identity.** Two separately-ruled
acceptances compose into an outcome neither covers.

**A4-R9-4 -- MAJOR -- NEW GROUND -- "EQUALS the collision probability" is mathematically wrong.** False confirmation is a
strict SUBSET: it also needs an unsettled rolled-back attempt, the collision landing before its
probe, a committed row, and a ticker match. **P(false confirm) <= P(collision), not =.**

### The other six

**A4-R9-1 -- MAJOR -- NEW GROUND -- `isinstance(str) and len == 36` is NOT equivalent to the SQLite CHECK.** A 35-char
string plus a NUL has Python length 36 and SQL length() 35; a lone surrogate fails at binding. Both
pass the validator and then **fail during the money-bearing INSERT** -- the ordinary-path failure
S2.1 exists to exclude. Fix: parse with uuid.UUID, require version 4 and canonical round-trip.

**A4-R9-5 -- MAJOR -- NEW GROUND -- the tier-3 override path has no preflight.** `_preflight_reserved_transitions` is called
only from `_handle_multi_field_correction`; `_apply_tier3_override_inner` inserts a correction row,
advances the supersession pointer, then processes fields sequentially -- so with attempt_id LAST,
mutations occur before the backstop refuses. Order-independence is **not established across a
supported operator surface.**

**A4-R9-6 -- MAJOR -- NEW GROUND -- (k4b) generalises a rollback-journal measurement to the WAL path.** The plan says the
live database is WAL and WAL readers are unblocked, then asserts the fresh probe "BLOCKS OR FAILS".
Fix: parameterise by journal mode, both arms re-raising the original.

**A4-R9-7 -- MAJOR -- RESIDUAL -- Task 3 cannot reach green.** It schedules (k3b), (k4a), (k4b), all needing
the probe and settlement Task 4 introduces. The task-boundary class, third instance.

**A4-R9-8 -- MAJOR -- RESIDUAL -- contradictory authorization state. FIXED.** The status block now states it
once and correctly: three items closed, three newly opened.

**A4-R9-9 -- MAJOR -- RESIDUAL -- MY LEDGER ARITHMETIC WAS WRONG, TWICE OVER. FIXED.** Per-round rows sum to
**86** through round 8 (**4 CRITICAL / 63 MAJOR / 19 MINOR**); I reported **76**, whose own
severities summed to **66**. **Carried into two return reports as convergence evidence.** A total
used as evidence is itself evidence and gets checked like evidence; this one was not, in a document
whose entire subject is claims that outrun what supports them.

### Verdict

`NEW_CRITICAL_MAJOR_FOUND`. **STOPPED BY INSTRUCTION -- round 10 is the gate-holder's call.**
**Reviewer's judgement, asked for directly:** *"still yielding substantive design and evidence
defects, especially around rollback observability, the 'covered risk' rationale, validation
containment, and an uncovered corrector path. It has not converged to prose and bookkeeping only."*

**TOTALS THROUGH ROUND 9: 95 findings -- 4 CRITICAL, 72 MAJOR, 19 MINOR. Zero reopened, zero
reverted.** Re-derivable by the command in LEDGER CONVENTIONS at the head of this file; the
class split is 22 NEW GROUND / 24 RESIDUAL / 49 CLASS-UNRECORDED.
**Token spend: 3,086,359 across nine counted rounds; 3,403,156 including both disqualified attempts.**

---

## AMENDMENT PASS 3 (2026-09-07) -- RD ruled all three routed items; the other four round-9 findings fixed

**Cell note:** this pass was executed by a FRESH implementer cell. The planning cell that ran rounds
1-9 retired at 779,749 tokens of context. Everything below was re-derived from the artifacts on disk
(the plan, this ledger, the nine transcripts, and the orchestrator's item-2 experiment script and
preserved CPython source), not from a handoff summary.

### The three routed items -- RULED

**1. `A4-R9-2` -- BRANCH A SELECTED. RULE (i) GOES LITERAL ON BOTH PATHS.** The plan's two-round
claim that *"the wrapper cannot see whether `__exit__`'s internal rollback raised"* is FALSE and is
struck at every location. Mechanism as ruled: **`with conn:` stays byte-identical** (so option (b),
hand-rolled transaction plumbing on the byte-locked money path, stays rejected) and the wrapper
**inspects what propagates AND its `__context__` chain at the except site**; a detected rollback
failure VOIDS the probe exactly as on the immediate path.

**The measurements that selected it** (orchestrator-run, Python 3.14.2 / sqlite3 3.50.4; script and
CPython source preserved at `~/swing-data/review-transcripts/22-a4-plan/`), now MEASURED (5)-(7) and
SOURCE (S1) in the plan's S1.3:
- a Python-level `rollback()` override installed via `sqlite3.connect(factory=...)` is **NOT
  invoked** by the C-level `__exit__` -- banked as a fact about the test LEVER, since `factory=` is
  the obvious reach for the next person who wants to intercept transaction control;
- forcing a rollback failure on the block-error arm propagated **`OperationalError: interrupted`
  with `__context__` set to the original `ValueError`** -- the failure reaches the caller, REPLACING
  the propagating exception and preserving the original as context;
- **a FAILED commit leaves `in_transaction` TRUE** -- the exit's rollback is real work, not a no-op.
  RD: *this is the fact that makes the whole clause non-vacuous*, and it has its own line in the plan.

**The one open residual was closed IN PARALLEL by the orchestrator, by source read, and the plan's
S7.15 states the resulting evidence grade in one sentence as instructed: MEASURED-AT-SOURCE.**
CPython v3.14.2 `Modules/_sqlite/connection.c`: `:2377` `pysqlite_connection_exit_impl`; `:2394-95`
the comment *"Commit failed; try to rollback in order to unlock the database. If rollback also
fails, chain the exceptions."*; `:2396` captures the COMMIT error; `:2397` calls **the identical
rollback implementation as the block-error arm's `:2389`**; `:2399` `_PyErr_ChainExceptions1` on
rollback failure; `:2403` re-raise of the commit error on rollback success. **The commit-fail arm is
therefore cited, not inferred**, and the branch selection did not have to re-open.

**2. `A4-R9-3` CLOSES STRUCTURALLY, AND RD'S 2026-09-06 ITEM-3 ACCEPTANCE IS SUPERSEDED.** Branch A
removes the ADMITTING step the composition needed. **The supersession is stated explicitly in S7.15,
S2.4, S9 CHARC item 8 and S9 RD item 3 -- one ruling governs this path, not two side by side.**

**3. `A4-R9-4` -- "EQUALS the collision probability" corrected to a strict bound.** False
confirmation is a strict SUBSET of the collision event (it additionally needs a rolled-back unsettled
attempt, the colliding commit landing before that attempt's probe, and a ticker match), so S7.7 now
declares **`P(false confirm) < P(collision)`**.

### The four unfixed round-9 findings -- ALL FIXED

- **`A4-R9-1`** -- the Python validator was not equivalent to the SQL CHECK. **FIXED by
  single-sourcing:** one `validate_attempt_id` in `swing/data/repos/trades.py`, called by BOTH the
  repo's pre-write guard AND `entry.py`'s `_begin_attempt_identity`, requiring `isinstance(str)` +
  exact length + `uuid.UUID` parse + `version == 4` + canonical round-trip. (r3) grows from four
  malformed values to SEVEN and (e2) from eight scenarios to twelve; **the three new cases each
  defeat a DIFFERENT layer** -- the CHECK (NUL: Python length 36, SQL `length()` 35), the parameter
  BINDING one layer below it (lone surrogate), and the UNIQUE index's exact text key (uppercase).
- **`A4-R9-5`** -- the tier-3 override path reaches no preflight. **FIXED, and the scoping is the
  argument:** the shared predicate gains a THIRD call site at the head of
  `_apply_tier3_override_inner`, refusing ONLY the new immutable set. Calling
  `_preflight_reserved_transitions` there instead is DECLINED, because it would newly refuse the
  seven pre-existing reserved fields earlier on that path -- a behaviour change to shipped
  functionality, i.e. the sweep CHARC's condition excluded. New test **(m8d)**, whose discriminator
  is STATEMENT COUNTS rather than persisted state: the public entry point's own ROLLBACK erases the
  state difference, so a state-only assertion would certify the backstop-only implementation.
- **`A4-R9-6`** -- a rollback-journal measurement generalised to WAL. **FIXED in THREE places, not
  one:** MEASURED (3) now names its journal mode; S2.2's *"blunter reason"* is withdrawn with its
  reason (it holds for every `tmp_path` test database and NOT for the live WAL one, so the design
  rests on the durable-ABSENT argument alone); and (k4b)'s *"BLOCKS OR FAILS"* claim disappears
  entirely, because under Branch A the probe does not run at all.
- **`A4-R9-7`** -- Task 3 could not reach green. **FIXED, and the class was re-swept rather than the
  instance patched** (`A4-R7-2` and `A4-R8-3` are the same class): (k3b), (k4a) and (k4b) move to
  Task 4 with the probe they need, **and the sweep found a FOURTH item the finding did not name** --
  (k2)'s *"the probe is NOT called"* assertion, which also cannot exist in Task 3. Task 3 now states
  what it is NOT doing.

### What the per-location audit found that no round did

**`swing/trades/reconciliation_auto_correct.py` -- the ONE module CHARC's condition widened the
envelope by -- was ABSENT from S4's "Edited" manifest**, while Task 1b edits it and the Global
Constraints name it. The roster-is-the-same-instrument-as-the-count class, on the roster this arc
added expressly to make the widening visible. Added.

### Instruments re-run

- **Consistency sweep** (`plan_consistency_sweep.py`, updated for the new ids and the new fragile
  counts): **clean -- 41 defined / 41 scheduled / 41 in the S4 manifest** (39 before; `(k3)` split
  into `(k3a)`/`(k3b)` and `(m8d)` added).
- **Per-location audit** (`per_location_audit.py`, written for this pass): **38 probes, 0 failing.**
  Both instruments are preserved at `~/swing-data/review-transcripts/22-a4-plan/`.
- **Ledger normalization:** see the LEDGER CONVENTIONS block at the head of this file. 95 findings
  now carry ONE header shape and the totals are re-derivable by a one-line command.

---

## Round 10 -- RAN ON THE AMENDED SHAPE. IT DID NOT CONVERGE.

### Transport note -- ONE DEAD ATTEMPT, ZERO TOKENS, NOT A ROUND

First invocation `wsl.exe bash /mnt/c/.../.codex-run-r10.sh` produced
`bash: C:/Program Files/Git/mnt/c/.../.codex-run-r10.sh: No such file or directory` with harness
**exit 0** -- the MSYS path-mangling mechanism, hitting the argument that begins with `/`, exactly as
this ledger's round-1 note records. **The two-signal rule caught it** (exit reported success; the
transcript was 0 bytes). Working form re-applied from that note:
`MSYS_NO_PATHCONV=1 wsl.exe bash -lc 'bash /mnt/c/.../run.sh'` -- the `-c` STRING begins with `bash`,
so no argument MSYS parses begins with `/`. **No transcript, no footer, 0 tokens; not counted.**
*Worth recording twice in one loop: the remedy was already written down and was not applied on the
first try, which is what a hazard note is for.*

### Mechanical assertions -- ALL FIVE PASS

model `gpt-5.6-sol`; effort `high`; `^ERROR` = **0**; `^tokens used` = **1** (**392,163**);
`^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0**. Exit **0** MEASURED (the
runner writes the exit file only after codex returns); transcript **1,145,895 bytes**, non-empty;
process exit confirmed. Reviewer self-report: "No safety-layer refusal or rewrite occurred."
**Scratch isolation verified:** `.copowers-findings.md` and every prior `.codex-review-r*.txt` were
moved OUT of the worktree for the duration; the nine transcript hits on `codex-review-r|copowers`
are all prompt echo or plan/CLAUDE.md text, none a file read.
Artifact frozen at sha256 `b61364441a8deb56427c0df22f1f3edbb8d2815d93ab2fcf2b3a06bc26265c5b`
(251,214 bytes), commit `c3295386`.

### Counts

**7 findings: 1 CRITICAL, 5 MAJOR, 1 MINOR. 1 NEW GROUND, 6 RESIDUAL. Zero reopened, zero reverted.**

**NOTHING BELOW IS FIXED.** The dispatch instruction was to run this round and STOP whatever it
returned; the gate-holder owns round 11. Four of the seven are residuals of THIS amendment pass's
own edits, two bear on director ruling text, and one is refuted below.

**A4-R10-1 -- CRITICAL -- RESIDUAL -- the amended predicate is not fail-closed, and the plan says so
in one place while claiming structural closure in another.** `_exit_rollback_failed` keys on
`isinstance(context, sqlite3.Error)`, so a non-`sqlite3.Error` commit failure followed by a rollback
failure returns False -- the residue S2.2 and S7.15 DECLARE -- and the reviewer composes that residue
with S7.7's accepted collision event to rebuild `A4-R9-3`'s false SUCCESS. **ASSESSED CORRECT as a
contradiction:** the plan cannot both declare that residue and say the composition window has "no
admitting step left". **NOT FIXED, AND IT ROUTES:** the remedy the reviewer names -- a bare
`__context__ is not None` test -- is the shape S2.2 rejects by argument (it fires on every caller
running inside an `except` block, silently disabling clause 2 in production), so choosing between a
narrower residue and a broader false-positive set is a RULING ON RD's OWN MECHANISM, not an author's
call. The alternative he offers second is option (b), which RD rejected twice.

**A4-R10-2 -- MAJOR -- RESIDUAL -- `P(false confirm) < P(collision)` is not established.** Event
containment gives the non-strict form; strictness needs a probability model assigning positive mass
to the difference, and the three extra conditions may not be multiplied without an independence
claim (a single-ticker workload makes the ticker conjunct 1). **ASSESSED CORRECT.** **NOT FIXED:**
this is the THIRD statement of a sentence RD owns, and the correction he issued on 2026-09-07 was
itself the second. The non-strict form is the safe one; the discrepancy is his to settle.

**A4-R10-3 -- MAJOR -- RESIDUAL -- Task 3 now ships `_exit_rollback_failed` with NO test that
exercises it.** `(k)` is the ordinary resolved path; `(k2)` gets `cleanup_raised` from
`_observe_resolution`'s own raising retry, so it passes with the predicate deleted; `(k3a)` is an AST
walk. **Task 3 goes green against a predicate that always returns False.** **ASSESSED CORRECT, AND IT
IS THE FOURTH INSTANCE OF THE CLASS THIS LOOP HAS PAID FOR** (`A4-R7-2`, `A4-R8-3`, `A4-R9-7`, now
this) -- and the first three were all fixed by MOVING tests later, which is precisely what created
this one. **The class is not "a task schedules a test it cannot run"; it is "the plan schedules tests
by artifact rather than by the assertion each one makes."** A predicate-signal test needs no probe
and belongs in Task 3; only the zero-call and settlement assertions need Task 4. **NOT FIXED.**

**A4-R10-4 -- MAJOR -- RESIDUAL -- and the half about `tmp_path` is MY OWN AMENDMENT'S FACTUAL
ERROR, VERIFIED AT THE CODE.** S2.2's new correction says the rollback-journal blocking reason holds
for "every `tmp_path` test database". **FALSE:** `ensure_schema` (`swing/data/db.py:2211`) opens
via `open_connection(db_path, reaffirm_wal=True)` and `open_connection:131` executes
`PRAGMA journal_mode=WAL`, so a test database built the normal way is **WAL**. Only `(c2)`'s
explicitly configured fixture is rollback-journal. **I fixed an over-generalisation by writing a
different over-generalisation in the same paragraph.** The reviewer's other half -- that MEASURED
(2)'s "readers never block" is itself broader than the experiment, since WAL can still return
`SQLITE_BUSY` on exclusive locking, recovery and last-connection cleanup -- is also correct and is
older text this pass did not touch. **NOT FIXED.**

**A4-R10-5 -- MAJOR -- NEW GROUND -- REFUTED ON THE EVIDENCE, and the underlying fragility is real.**
The claim is that `pysqlite_connection_exit_impl` sits at 2211-2243 in official CPython v3.14.2, so
the plan's 2377-2403 citation is unreproducible. **MEASURED AGAINST THE FILE THE CITATION WAS
TAKEN FROM** (`~/swing-data/review-transcripts/22-a4-plan/cpython-3.14.2-Modules-_sqlite-connection.c`,
2,717 lines, sha256 `7487db46afbdbb93681a508ec33c65f87d6460079f1564d1b6310b6d8d23d09c`):
line 2377 IS `pysqlite_connection_exit_impl`; 2394-95 IS the "Commit failed; try to rollback"
comment; 2396, 2399 and 2403 are `PyErr_GetRaisedException`, `_PyErr_ChainExceptions1` and
`PyErr_SetRaisedException` exactly as cited. Line 2211 in that file is inside `create_collation`.
**The round ran `sandbox: read-only` with `approval: never` and made no network call in its
transcript, so its counter-line-numbers are not themselves sourced.** **BUT THE FINDING IS WORTH
ACTING ON ANYWAY:** a line-numbered citation to a file that is NOT IN THE REPOSITORY is
unverifiable by any reviewer, which is how it drew a confident refutation. **Proposed fix, NOT
APPLIED:** anchor the citation on CONTENT (the function name plus the verbatim comment) and pin the
file by the sha256 above, keeping line numbers only as a convenience.

**A4-R10-6 -- MAJOR -- RESIDUAL -- MY AMENDMENT BROKE A COUNT IT DID NOT TOUCH.** (e2) requires
hostile-sink coverage at "each of the THREE contained-WARNING sites" in
`_begin_attempt_identity`. My `A4-R9-1` edit collapsed the separate malformed-return warning into
the `validate_attempt_id` call inside the existing `try`, leaving **TWO** sites. The executor is now
told to cover three branches, one of which no longer exists. **ASSESSED CORRECT.** **NOT FIXED.**

**A4-R10-7 -- MINOR -- RESIDUAL -- the version-mirror family is "SIX spellings" in S1.6/S4 and "a
SEVENTH SPELLING" in Task 1** (`A4-R7-12`'s fix, propagated to one location). Pre-existing, not
touched by this pass. **NOT FIXED.**

### Reviewer's judgement, asked for directly

"The plan is still yielding substantive DESIGN and EVIDENCE defects, not merely prose and
bookkeeping. In particular, the amended predicate retains a director-forbidden read and a
false-confirm composition, while the probability, journal-mode, and source claims remain unsound."

### Verdict

`NEW_CRITICAL_MAJOR_FOUND`. **STOPPED BY INSTRUCTION. Round 11 is the gate-holder's call.**

**TOTALS THROUGH ROUND 10: 102 findings -- 5 CRITICAL, 77 MAJOR, 20 MINOR.** Re-derivable by the
command in LEDGER CONVENTIONS; class split 23 NEW GROUND / 30 RESIDUAL / 49 CLASS-UNRECORDED.
Zero reopened, zero reverted across all ten counted rounds.
**Token spend: 3,478,522 across ten counted rounds** (3,086,359 + 392,163);
**3,795,319 including the three disqualified/dead attempts** (round 1 attempt 1: MSYS mangling,
0 tokens; round 9 attempt 1: provider capacity, 316,797 tokens; round 10 attempt 1: MSYS mangling,
0 tokens).

---

## THE 2026-09-07 SETTLING SWEEP -- **UNCOUNTED. No Codex, no round number, NO effect on convergence.**

Ruled by the gate-holder after round 10 returned **6 of 7 findings RESIDUAL**, four of them
residuals of the amendment pass written the same day. The recipe's Expansion-#13 provision
(`harness-architecture.md` §5.1). RD's two round-10 rulings were applied first, then the artifact
was swept, then ONE confirming round ran on the settled shape (round 11, below).

**Commits:** `1d2be8af` (RD's two rulings + the citation rule), `18cdf08e` (`SS-9` + the bookkeeping
the previous commit owed), `9e59416c` (`SS-10`/`SS-11`/`SS-12`), `778ebe20` (`SS-13`/`SS-14`),
`44149979` (`SS-15`/`SS-16`), `e76e4e1d` (the S11 record).

**SS-9 -- WOULD HAVE BEEN CRITICAL/MAJOR -- applying RD's PIN 1 naively widened the arc onto a
pre-arc failure branch.** Removing `body_completed` removed the scope condition
`_entry_transaction`'s deferred handler used; the first edit answered that by calling
`_observe_resolution` UNCONDITIONALLY there, which reaches the deferred BODY-RAISE branch and, where
`__exit__`'s own rollback also failed, would issue a rollback that path never issued. 22-A LOCK
clause (c)'s subject. **Fix:** both deferred observations moved to `record_entry`'s handler, which
raises at `result is None` first; `_entry_transaction`'s `if not immediate:` branch is now LITERALLY
UNEDITED and (k3a) asserts it by AST.

**SS-10 -- residual.** S1.4 still said the arc adds "the three NEW observation fields" to the
deferred path.

**SS-11 -- THREE stale in-repo line anchors,** found by `citecheck.py` (resolves all 54 in-repo
`file.py:N` citations and prints what each lands on). `entry.py:1128` is `conn.rollback()`, not the
immediate path's `outcome.committed = True` (`:1107`); `entry.py:880` is inside a comment block, not
the shipped guard (`:884`) -- **and `:880` is the number this dispatch's own PIN 1 was relayed with,
so it had propagated to three sites before the sweep caught it**; `entry.py:1489` is one line above
the UNIQUE mapper.

**SS-12 -- the in-repo twin of `A4-R10-5`.** S8 item 4 cited FOUR anchors for "the four pre-commit
logging calls in `_record_entry_inner`". That function begins at `:1166`; all four pointed into
`record_entry`, and **not one of them is a logging call**. MEASURED by AST walk: `:1227`, `:1295`,
`:1306`, `:1321`. **The COUNT was right and every ANCHOR was wrong.** Global Constraints gained the
in-repo corollary of the citation rule: every `file.py:N` citation NAMES THE SYMBOL.

**SS-13 -- `A4-R10-3`'s generalisation turned into an INSTRUMENT** (`assertion_schedule_audit.py`)
rather than a paragraph. **SS-14 -- what it caught on its first run, in a row this sweep had added
four hours earlier:** (k3a)'s ordering assertion named a Task-4 function while scheduled in Task 3,
and **its failure mode is a VACUOUS PASS** -- an AST walk asserting an ORDERING finds no node,
therefore finds no ordering to violate, and reports success.

**SS-15 -- residual.** S3's roster still described (k3a)/(k3b) as asserting the assignment is
"inside the protected suite on BOTH paths", false one commit after `SS-9`.

**SS-16 -- "THREE call sites" turned into a CLOSURE with its method.** AST walk + raw-SQL grep:
`_update_journal_field` has exactly four callers and is the ONLY site writing an operator-supplied
journal field, so the backstop IS the closure. **The finding behind the finding:** the plan's whole
argument for the tier-3 early check is that its INSERT comes first, and nobody had checked whether
the other surfaces share that shape. They do not, for a different reason each.

**AND ONE CORRECTION AGAINST THE RULING THIS PASS WAS APPLYING, MEASURED RATHER THAN INHERITED.**
`A4-R10-1` was relayed with the rationale that a cleanly-completed block leaves `__context__` None,
so the ambient-`except` false positive lives entirely in the excluded region. **MEASURED, CPython
3.14.2 / sqlite3 3.50.4:** it does not -- `__context__` is set from the THREAD's handled exception,
so a caller inside an `except` still produces a non-None context on the commit-failed/rollback-OK
row, and the removed type filter would have caught it. The DECISION stands on its other leg; the
REASON is now the measured one, and (RD-a4) drives the cost as a test.

---

## Round 11 -- THE ONE CONFIRMING ROUND ON THE SETTLED ARTIFACT. IT DID NOT CONVERGE.

### Transport

Working form applied on the FIRST attempt this time (`MSYS_NO_PATHCONV=1 wsl.exe bash -lc 'bash
/mnt/c/.../.codex-run-r11.sh'`, LF-verified runner, output and exit files pre-created
Windows-side). **No dead attempts.** codex-cli **0.152.1**.

### Mechanical assertions -- ALL FIVE PASS

model `gpt-5.6-sol`; effort `high`; `^ERROR` = **0**; `^tokens used` = **1** (**509,364**);
bare-line `^NEW_CRITICAL_MAJOR_FOUND` = **2** (0.152.1 emits the final message twice),
bare-line `^NO_NEW_CRITICAL_MAJOR` = **0**. Exit **0** MEASURED (the runner writes the exit file only
after codex returns); transcript **1,606,610 bytes**, non-empty. Reviewer self-report: *"No
safety-layer refusal or rewriting occurred."*
**Scratch isolation VERIFIED AND STRONGER THAN A PROHIBITION THIS ROUND:** `.copowers-findings.md`
and every prior `.codex-*` file were MOVED OUT of the worktree for the duration, so they were not
merely forbidden but absent. The transcript's 30 hits on `codex-review-r|copowers` are prompt echo
plus **two `rg` invocations that EXCLUDE them** (`--glob '!.codex*'`, `rg -v`). No read.
Artifact frozen at sha256 `c92a39535d6609ce7a9436303d83666c7a0a66361fc1a2b80b9420cfa50c7e76`
(297,089 bytes), commit `e76e4e1d`.

### Counts

**14 findings: 1 CRITICAL, 11 MAJOR, 2 MINOR. 8 NEW GROUND, 6 RESIDUAL. Zero reopened, zero
reverted.** *(The class split is DERIVED by the LEDGER CONVENTIONS command, not stated from memory:
a first draft of this block said "7 NEW GROUND, 7 RESIDUAL" and the command said 8/6 -- and three of
the fourteen headers did not match the regex at all, so the same draft's totals read 113 where they
should read 116. **`A4-R9-9`'s defect, live again in the block written to prevent it, caught by the
command that block installed.** Both are corrected here rather than quietly, because a total used as
evidence is evidence.)*

**NOTHING BELOW IS FIXED.** The dispatch instruction was to run ONE confirming round and STOP
whatever it returned; round 12 is the gate-holder's call. Each finding is adjudicated below, and the
cheap factual ones were VERIFIED BY EXECUTION rather than accepted or dismissed.

**A4-R11-1 -- CRITICAL -- NEW GROUND -- the bare `__context__` read is defeated by a subclass data
descriptor, and I REPRODUCED IT.** `escaping.__context__` is an ordinary attribute lookup; a
`sqlite3.OperationalError` subclass may define `__context__` as a property. **MEASURED, this
machine, CPython 3.14.2:** with the commit error chained beneath, `escaping.__context__ is not None`
reads **False** while `BaseException.__dict__["__context__"].__get__(e, type(e))` reads the
`OperationalError` -- a **FALSE NEGATIVE**, which sets `resolution = not_needed` with
`cleanup_raised` False, ADMITS the probe, and rebuilds exactly the `A4-R9-3` window RD's ruling
declared structurally closed. A second subclass whose getter RAISES replaced the escaping exception
(`RuntimeError: getter exploded`). **ASSESSED CORRECT.** Two things make it sharper than its
reachability: **(a)** the plan's post-ruling text upgraded the claim to *"false negatives
structurally impossible within its scope"*, and that sentence is now false -- the removal of the
type filter was sold partly on it; **(b)** this repository ALREADY documents the class one function
away (`swing/trades/entry.py:112-125`, `safe_text`, whose docstring says *"an exception class
overriding `__repr__` (and `__str__`) to raise is constructible"*) -- **so the plan reasoned about a
hostile exception's FORMATTING and not about its ATTRIBUTES, in the same file.** The reviewer's
correction (read the base slot, contain a raising read in the alarm direction, add Task-3 subclass
rows) is cheap and does not touch the ruling's shape. **NOT FIXED.**

**A4-R11-2 -- MAJOR -- NEW GROUND -- a cheaper discriminator for the ambient-`except` false positive
exists and was not weighed.** Capture `sys.exception()` in `record_entry` BEFORE `_entry_transaction`;
on rollback-success the re-raised commit error's context IS that captured ambient object, on rollback
failure the escaping rollback error's context is the COMMIT error. Excluding exactly that identity
removes the measured false positive with no type filter and no touch to `with conn:`. **ASSESSED
CORRECT AS A DESIGN OPTION, AND IT ROUTES:** it modifies a predicate RD ruled the shape of two days
running, and it reverses (RD-a4)'s expected outcome. The reviewer also argues the direction argument
is understated -- a false positive reports failure over a DURABLE entry, the retry-inducing
direction -- which is a fair challenge to a reason this pass wrote. **NOT FIXED; it is RD's.**

**A4-R11-3 -- MAJOR -- RESIDUAL -- (of this sweep's own `SS-9` fix) the two observations are in the
WRONG ORDER.** The handler calls `_observe_resolution` and THEN `_exit_rollback_failed`. Where
`__exit__`'s rollback raised BEFORE taking effect, `_observe_resolution` finds `in_transaction` True
and **calls `rollback()` again on the wounded connection** -- and (k4b) explicitly expects that
retry. Rule (i) as RD stated it is *"the connection is DISCARDED and NO read is attempted on it"*;
operating on it before detecting the failure is not that. **ASSESSED CORRECT.** *The relocation was
right and its ORDERING was inherited from the frame it moved out of, unexamined.* **NOT FIXED.**

**A4-R11-4 -- MAJOR -- RESIDUAL -- the shared `_observe_resolution` cannot preserve the immediate
ladder, and the plan's own pseudocode never calls it.** Task 3 says the helper owns a rollback,
contains its failure and does not change what escapes; the shipped immediate ladder must LOG that
exact cleanup exception and `raise cleanup_error from write_error` (`entry.py:1126-1163`). The two
cannot both hold. **ASSESSED CORRECT -- and it is worse than a contradiction the reviewer found,
because THIS PASS SAW THE TENSION AND WROTE A SENTENCE INSTEAD OF RESOLVING IT** (S2.2 now says the
helper is "shown INLINE below rather than as a call, because what it does is the point"). That is
the shape of an explanation standing in for a design. The reviewer's correction -- separate a
non-mutating `_read_resolution` from the deferred cleanup retry -- also dissolves `A4-R11-3`.
**NOT FIXED.**

**A4-R11-5 -- MAJOR -- RESIDUAL -- (of `SS-9`) Task 3 cannot reach its own specified green state.**
Task 3 says the existing combined guard `if result is None or not outcome.committed: raise`
(`entry.py:884`) stays UNSPLIT, while (k3a)'s Task-3 half requires the observation to sit AFTER the
`result is None` raise. With the guard intact, an observation after it is unreachable whenever
`committed` is False, and one before it violates the asserted ordering. **ASSESSED CORRECT.**
**This is the schedule/reachability class AGAIN, at instance five, produced by the fix for instance
four** -- and my own `assertion_schedule_audit.py` is blind to it, because it detects a test
scheduled before a SYMBOL exists and this is a test scheduled against a CODE SHAPE the task
declines to create. **NOT FIXED.**

**A4-R11-6 -- MAJOR -- RESIDUAL -- Task 3 ships the IMMEDIATE path's observation semantics with no
in-task discriminator.** Task 3's rows are all deferred-path ((k), (k2), (k5)) plus the structural
(k3a); the only row distinguishing the returning-arm re-read, `rolled_back` vs `still_open`, and
`cleanup_raised` after an immediate rollback failure is **(RD-a1), scheduled wholly in Task 4** --
and its OBSERVATION halves need no probe. A naive Task-3 implementation assigning `rolled_back`
whenever `rollback()` returns reaches Task-3 green. **ASSESSED CORRECT, and it is the exact rule
this sweep wrote, failed on the OTHER path.** The sweep split (k4a)/(k4b) for the deferred path and
never asked the same question of the immediate one. **My instrument cannot see this direction
either** -- it detects scheduled-too-early, not code-shipped-without-a-discriminator, which is the
direction that matters. **NOT FIXED.**

**A4-R11-7 -- MAJOR -- NEW GROUND -- four Task-4 design requirements have NO discriminating
assertion:** nothing captures `open_connection(..., busy_timeout_ms=2000)` (omitting it silently
restores the project's 30-second default on a money-path failure); nothing forces `close()` to raise
AFTER a successful read (a naive `finally: probe.close()` discards a valid result and forces the
alarm); nothing returns a row with the right token and the WRONG ticker (so omitting the ticker
corroboration passes every listed row -- **and S7.7's whole same-ticker bound rests on that
corroboration**); nothing drives a landed lost commit with `attempt.token is None`. **ASSESSED
CORRECT.** **NOT FIXED.**

**A4-R11-8 -- MAJOR -- NEW GROUND -- (m3) does not prove `run_migrations` INVOKES the backup gate,
nor pin the expected-table set.** A disconnected helper, or a set omitting one of 0037's three
tables, passes -- and S6's live witness compares the backup against "the expected set", making that
check self-confirming rather than independent. **ASSESSED CORRECT, and it is the most consequential
of the MAJORs for the LIVE database**, which crosses this migration once, holding real
money-bearing trades. **NOT FIXED.**

**A4-R11-9 -- MAJOR -- NEW GROUND -- I CANNOT SETTLE IT FROM HERE; REPORTED UNRESOLVED.** The
reviewer states official CPython v3.14.2's `connection.c` has **2,532 lines** with
`pysqlite_connection_exit_impl` at **2211-2243** -- the same numbers round 10 gave, and the reason
`A4-R10-5` was refuted. **What I can establish:** the preserved file at
`~/swing-data/review-transcripts/22-a4-plan/cpython-3.14.2-Modules-_sqlite-connection.c` is 2,717
lines, sha256 `7487db46...`, and at `:2377`/`:2394-95`/`:2396`/`:2399`/`:2403` says exactly what the
plan quotes -- **verified twice, by two different people, against THAT FILE.** **What I cannot
establish is that THAT FILE IS THE OFFICIAL v3.14.2 SOURCE.** The round ran `sandbox: read-only`
with `approval: never` and made no network call, so its counter-numbers are unsourced too; and the
preserved copy sits outside the worktree, so the reviewer could not open it. **Two rounds agreeing
is not two sources agreeing.** The digest pins WHICH FILE was read; it does not pin WHOSE. That is
precisely the gap `A4-R10-5`'s adopted rule was supposed to close and does not. **The semantic
branch is not in dispute** -- both sides agree the commit-failed branch chains on rollback failure
and re-raises on rollback success, which is all SOURCE (S1) is used for -- **so the exposure is
provenance, not behaviour.** Settling it needs a network fetch of the tagged file, which this cell
cannot make. **NOT FIXED; ROUTED with the method that would settle it.**

**A4-R11-10 -- MAJOR -- NEW GROUND -- the probe can CREATE a database. VERIFIED AT THE CODE.**
`open_connection` calls bare `sqlite3.connect(db_path_or_uri, uri=uri, ...)` (`swing/data/db.py:126`),
which creates the file when absent. If the database path is moved or renamed between capture and
probe, the confirming READ writes an empty database and then answers ABSENT -- a filesystem artifact
created on an already-failing money path, by the mechanism whose entire purpose is to observe
without acting. **`open_connection`'s OWN DOCSTRING names the remedy** (*"callers can pass a
`file:...?mode=rw` URI and KEEP fail-closed semantics"*), and the plan's probe does not use it.
**ASSESSED CORRECT.** **NOT FIXED.**

**A4-R11-11 -- MAJOR -- NEW GROUND -- the S1.6 below-HEAD census misclassifies six of seven call
sites. VERIFIED BY GREP.** `tests/trades/test_22a_task4_authorization_ladder.py` contains
`record_entry` **only in explanatory prose at `:277`** and never calls it;
`test_22a_task6a_competitor_liveness.py` and `test_22a_task3_epoch_reader.py` contain **zero**
`record_entry` hits. **Only `test_22a_task9_entry_wiring.py:89` among the seven actually drives the
service**, so the stated reason for advancing six fixtures to production HEAD does not hold for
them. **ASSESSED CORRECT.** *The census's own text says the manifest is the greps plus a READ of
every hit; the reason attached to the hits was not re-derived per file.* **NOT FIXED.**

**A4-R11-12 -- MAJOR -- NEW GROUND -- "the live database is WAL" is INFERRED, not MEASURED, and the
plan says both.** Global Constraints states the live database was NOT opened by this plan; the
journal-mode reading is of a `tmp_path` database built through `ensure_schema`. That establishes
CONSTRUCTION behaviour, not the live file's current mode. **ASSESSED CORRECT -- and it lands
squarely on ground this sweep just worked** (`A4-R10-4`), where I measured which FIXTURE shapes are
WAL and did not notice that the LIVE claim beside them has the same defect one level up. The
remedy is cheap and belongs in S6's pre-migration witness: add `PRAGMA journal_mode` to the
operator's steps and relabel until it is recorded. **NOT FIXED.**

**A4-R11-13 -- MINOR -- RESIDUAL -- `_RESERVED_JOURNAL_FIELDS` is "five" in S1.1 and "SEVEN" in
Task 1b. MEASURED: SEVEN**, spanning `:178-196` (both the S1.1 range `:178-183` and Task 1b's
`:178-190` are short). **ASSESSED CORRECT.** **And my own `plan_consistency_sweep.py` HAS a probe
for this exact number and passed** -- it asserts the string `**SEVEN** members` is PRESENT, which
Task 1b satisfies, and it cannot see a contradicting site elsewhere. **A presence probe is not a
consistency probe**, and that distinction is the same one `A4-R10-4` was about. **NOT FIXED.**

**A4-R11-14 -- MINOR -- RESIDUAL -- S2.3 says "Task 5 pins" the fresh connection; the test is
(RD-a2) in Task 4, and Task 5 is documentation-only.** **ASSESSED CORRECT.** **NOT FIXED.**

### Verdict

`NEW_CRITICAL_MAJOR_FOUND`. **STOPPED BY INSTRUCTION AFTER ONE ROUND. Round 12 is the
gate-holder's.**

### What this round says about the settling step, stated against my own interest

**The sweep did not make the artifact clean and the round proves it.** But the composition changed in
a way a count hides: round 10 was **6 of 7 RESIDUAL**; round 11 is **8 NEW GROUND, 6 RESIDUAL** --
and **four of the six residuals are residuals of THIS SWEEP'S OWN EDITS** (`A4-R11-3`, `-4`, `-5`,
`-6`; `-13` and `-14` are older). So the wake did not disappear; it moved. **What the sweep
bought is the eight NEW-GROUND findings** -- a base-slot descriptor hole, a probe that can create a
database, a backup gate nothing proves is wired, a census whose reason does not hold for six of
seven sites, an inferred journal mode called measured, four unpinned Task-4 requirements, and a
provenance gap -- **none of which any of ten prior rounds reached**, and several of which sat behind
the residue those rounds were spending themselves on.

**Two of my three instruments were blind to the two findings closest to their own subject.**
`assertion_schedule_audit.py` detects a row scheduled before a SYMBOL exists and cannot see
`A4-R11-5` (a row scheduled against a code SHAPE its task declines to create) or `A4-R11-6` (code
shipped with no in-task discriminator at all -- the direction that actually matters).
`plan_consistency_sweep.py` holds a probe for the very number `A4-R11-13` reports and passes,
because it checks PRESENCE of the right value and not ABSENCE of a wrong one. **Both are recorded
here rather than quietly improved, because an instrument's blind spot is worth more written down
than patched by the person who built it.**

**TOTALS THROUGH ROUND 11: 116 findings -- 6 CRITICAL, 88 MAJOR, 22 MINOR.** Re-derivable by the
command in LEDGER CONVENTIONS. Zero reopened, zero reverted across all eleven counted rounds.
**Token spend: 3,987,886 across eleven counted rounds** (3,478,522 + 509,364);
**4,304,683 including the three disqualified/dead attempts.** Round 11 had **no dead attempt** --
the working invocation was applied first, which this loop had failed to do twice.

---

## THE 2026-09-07 FIX LEG -- **NOT A ROUND. NO CODEX RAN.**

**Authorization, stated first:** the operator authorized **the fix leg, then a gate with a
disposition.** A twelfth counted round requires his WRITTEN authorization and does not exist. **No
Codex invocation was made in this leg and no prompt was prepared for one.** Convergence state is
UNCHANGED: eleven counted rounds, last verdict `NEW_CRITICAL_MAJOR_FOUND`.

**Why a fresh cell:** the settling-sweep cell that ran round 11 measured **446,282** against the
400K cap. Re-dispatch off the committed plan plus the preserved per-round evidence is the recipe's
normal outcome past the cap.

### Disposition of every open round-11 finding -- 13 FIXED, 1 ROUTED, 0 banked

| finding | sev | disposition | where it landed |
|---|---|---|---|
| `A4-R11-1` | CRITICAL | **FIXED** | `_CONTEXT_SLOT` + base-slot read + ALARM-direction containment (S2.2); the "structurally impossible" sentence STRUCK; **(k7a)-(k7b)** added in Task 3 |
| `A4-R11-2` | MAJOR | **FIXED (RD's ruling adopted, 3/3 conditions)** | capture point + `is`-identity (S2.2); **(RD-a4) rebuilt as a FOUR-ROW MATRIX** computed under both paths; containment covers the context read |
| `A4-R11-3` | MAJOR | **FIXED (dissolved)** | the deferred retry is GONE -> pre-arc behaviour restored; order is DETECT then READ |
| `A4-R11-4` | MAJOR | **FIXED** | `_read_resolution(conn, *, attempted)` NON-MUTATING; the immediate ladder keeps `raise cleanup_error from write_error`, pinned by **(k6b)** |
| `A4-R11-5` | MAJOR | **FIXED** | Task 3 SPLITS the pre-arc gate (behaviour unchanged); (k3a) asserts the split itself |
| `A4-R11-6` | MAJOR | **FIXED** | **(k6a)-(k6b)** -- the immediate path's Task-3 discriminators, no probe, no `record_entry` |
| `A4-R11-7` | MAJOR | **FIXED** | **(pr1)-(pr4)** |
| `A4-R11-8` | MAJOR | **FIXED** | **(m3a)/(m3b)/(m3c)**; the gate proven INVOKED **and LOAD-BEARING**; S6 compares the backup against a LIVE before-image, not the constant |
| `A4-R11-9` | MAJOR | **ROUTED** | S8 item 8 -- provenance, unsettleable without network; exposure narrowed by measurement; settling method written down |
| `A4-R11-10` | MAJOR | **FIXED** | **(pr5)** + the `file:...?mode=rw` URI open (S2.3), VERIFIED BY EXECUTION |
| `A4-R11-11` | MAJOR | **FIXED** | the below-HEAD census re-measured per file as a CALL-count table (S1.6) |
| `A4-R11-12` | MAJOR | **FIXED** | INFERRED-WAL at both sites; S6 step 0 asks `PRAGMA journal_mode` |
| `A4-R11-13` | MINOR | **FIXED** | SEVEN at `:178-196`, both sites; sweep gained CONTRADICTION probes |
| `A4-R11-14` | MINOR | **FIXED** | S2.3 points at **(RD-a2) in Task 4** |
| `SS-17` | uncounted | **FIXED** | the `insert_trade_with_event` grep's REAL output: NINE hits, one of them a call |

### The (RD-a4) matrix, MEASURED BY EXECUTION (CPython 3.14.2 / sqlite3 3.50.4)

Script preserved at `~/swing-data/review-transcripts/22-a4-plan/rd-a4-matrix-measurement.py`.

```
inside_except  chained |            __context__ | ctx is ambient |  BARE |  POST
        False    False |                   None |          False | False | False
        False     True | OperationalError(commit failed) |      False |  True |  True
         True    False | ValueError(the ambient handled exception) |  True |  True | False
         True     True | OperationalError(commit failed) |      False |  True |  True

    LyingContext | base-slot ctx = OperationalError | BARE = False | POST = True
  RaisingContext | base-slot ctx = OperationalError | BARE = RAISED RuntimeError: getter exploded | POST = True
```

**Row 3 is the entire delta.** Rows 1, 2 and 4 are identical under both predicates, which is the
matrix stating in its own shape that the amendment is narrow -- and row 4 is what shows the nested
case composes without a branch.

### A PREMISE CORRECTION AGAINST THE RULING THIS LEG APPLIED

The ruling was relayed naming **`sys.exception()`**. That is **Python 3.12+**, and
`pyproject.toml:9` declares `requires-python = ">=3.11"` (MEASURED by reading the file). The plan
specifies **`sys.exc_info()[1]`**, the same object inside the declared floor. A plan that had
adopted the NAME rather than the BEHAVIOUR would have shipped a 3.11 `AttributeError` on the money
path.

### Instruments -- all four re-run clean; two strengthened where round 11 found them blind

`plan_consistency_sweep.py` **53/53/53 clean** (+ a CONTRADICTION table: absence of the WRONG value,
which is the `A4-R11-13` blindness) - `per_location_audit.py` **120 probes, 0 failing** (38 -> 70 ->
120) - `assertion_schedule_audit.py` **53 rows, 0 naked symbols, 6 read-and-reasoned prose hits**
(+ the INVERSE check, + a BLIND-SPOT declaration printed every run) - `citecheck.py` **71 citations,
0 unresolved** (widened `.py` -> `.py|.sql|.toml`).

**THE INVERSE CHECK'S FIRST RUN INDICTED THIS LEG:** `_CONTEXT_SLOT` shipped in Task 3 with its only
discriminator in Task 4 -- `A4-R11-6`'s class inside the fix for `A4-R11-1`. That is what produced
(k7a)-(k7b). **And `citecheck.py`, once widened, caught two of this leg's own anchors** off by one
and four lines.

**WHAT THE INSTRUMENTS STILL CANNOT SEE, printed on every run rather than patched over:** a row
scheduled against a code SHAPE its task declines to create (`A4-R11-5` -- a shape is not a symbol);
a PATH-level discriminator gap (`A4-R11-6` itself -- the inverse check is satisfied by a row on the
OTHER path); and whether an assertion DISCRIMINATES at all, since the instrument reads prose.

### Gates

Four commits, `3548577c..24928c2f`, **all trailers empty**. **One file changed** (873 insertions,
216 deletions) -- the plan; no production code. `ruff check swing/` **All checks passed**.

---

## `A4-R11-9` — **SETTLED 2026-09-07 BY NETWORK FETCH. NOT A ROUND. NO CODEX.**

The fix leg ROUTED this item **with its method**, having no network. The orchestrator ran exactly
that method at 11:36Z the same day.

- **FETCH URL:** `https://raw.githubusercontent.com/python/cpython/v3.14.2/Modules/_sqlite/connection.c`
- **UPSTREAM: 80,695 bytes, sha256 `8cc0d9df05860c0b3fe6929ff392f8f85c9e1a5ef89c0cba31ab09ba03b3369e`**
- **CONTENT-IDENTICAL to the preserved copy after newline normalisation. SOURCE (S1) HOLDS at the
  tagged source**, so the chains-on-failure branch is confirmed upstream and not merely in a copy.
- Round 11's counter-claim (2,532 lines, the function at `:2211-2243`) matches neither the upstream
  file nor any counting convention of it, and — like round 10's — was produced with
  `sandbox: read-only`, `approval: never`, and no network.

**THE CORRECTION IT FORCED, AGAINST OUR OWN RULE.** The digest this plan pinned for two weeks
(`7487db46…`) was **the hash of OUR copy**, whose LF had been converted to CRLF by a text-mode write
while preserving it. **A local copy's digest pins WHICH BYTES WERE READ, never WHOSE THEY ARE** —
the exact gap the `A4-R10-5` citation rule was adopted to close, live inside that rule's own worked
example. Two readers verified against that copy and were each correct about the copy. The failure is
invisible because the hash is real and it verifies.

**RD-ratified remedy, now standing in Global Constraints and SOURCE (S1): PIN THE UPSTREAM DIGEST
TOGETHER WITH THE FETCH URL.** The preserved file has been renormalised; verified on disk here:
`sha256sum` → `8cc0d9df…`, 80,695 bytes, LF-only, final newline present.

**ONE COUNT CORRECTED IN THE OTHER DIRECTION, MEASURED HERE.** The settlement message reported the
upstream file as **2,718 lines**; measured on the pinned bytes, `wc -l` = **2,717** and Python
`splitlines()` = **2,717**. The file ends with a newline, so an editor showing a phantom trailing
line reports 2,718. **The bytes and the digest are identical either way and they are the pin** —
which is the corollary this episode adds to the rule: *a line count is a convenience, never a pin.*
Three numbers have now been asserted for this one file (2,532 / 2,717 / 2,718) and the byte size
never moved once.

**Instruments after the repoint — five stale probes found, all pinning the SUPERSEDED state:**
`per_location_audit.py`'s `R10-5 sha256 pin` and `R11-9 routed with its method`, plus three
authorization-state probes; `plan_consistency_sweep.py`'s `SOURCE (S1) sha256 pin`. **The sweep's
entry was enforcing the very defect the citation rule exists to prevent** — it required the presence
of our own copy's hash. Both are repointed to the UPSTREAM digest + fetch URL, and both now also
assert the **ABSENCE** of the retired digest as a live pin.
**And the instrument corrected one of my counts:** I allowed 3 quoted records of `7487db46…` and it
measured **5** (front matter, the Global Constraints rule, SOURCE (S1), S8 item 8, the S11
disposition row — every one of them the correction's own text). Allowance set to 5 with the sites
named; a sixth would mean the retired digest had been re-adopted somewhere.

**Result: `plan_consistency_sweep.py` 53/53/53 clean · `per_location_audit.py` 126 probes, 0 failing
· `assertion_schedule_audit.py` 53 rows, 0 naked symbols · `citecheck.py` 71 citations, 0
unresolved.** **NOTHING FROM ROUND 11 IS OPEN.**


---

## Executing dispatch — Task 0b + Task 1 intake (2026-09-07)

**No Codex round. This section records SUPERSESSIONS and INTAKE CORRECTIONS made by the executing
cell before writing code, per the recipe's rule that a ruling's REASONING is binding while its
incidental FACTS — line numbers, names, counts — are inputs the cell verifies against the code.**

### Supersession 1 — `(m3c)` takes BRANCH A (CHARC, PRIMARY, 2026-09-07)

`docs/superpowers/plans/2026-09-06-phase22-arc-a4-EXECUTING.md` `(m3c)` demanded the expected-tables
constant **EQUAL** a fresh v37 schema. **STRUCK BY REPLACEMENT, citing the ruling**, and the
replacement paragraph carries the ruling and its reason inline.

- **Mechanic re-verified on disk before encoding:** `swing/data/db.py:575` is
  `missing = expected_tables - actual_tables` inside `_verify_backup_integrity` — a **SUBSET** test.
  The gate's contract has always been a **FLOOR**.
- **Encoded:** `PHASE22_ARC_A4_PRE_MIGRATION_EXPECTED_TABLES =
  PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES | {the three 0037 tables}` (the derivation exactly as
  specified; `PHASE22_ARC_A_PRE_MIGRATION_EXPECTED_TABLES` verified at `swing/data/db.py:382`,
  consumed at `:2022`). `(m3c)` asserts **SUBSET, naming the offending member on failure**, **AND**
  membership of 0037's three tables. Gate strictness identical to 22-A's; S6 step 1 unchanged.
- **NOT built, banked to CHARC's register:** the schema-manifest drift comparator.

### Supersession 1a — the second strike anchor was MIS-PLACED, and the sentence at `:925` STANDS

**INTAKE CORRECTION (executing cell).** The dispatch brief instructed striking
`2026-09-06-phase22-arc-a4-EXECUTING.md:925`, quoted as *"EQUALITY, NEVER A SUPERSET CHECK -- CHARC
made this the MANDATORY member of the mirror set"*. **That line is inside `(r4)`, the
schema-versus-MODEL drift comparator — not inside `(m3c)`.** The two are different instruments:

- `(m3c)`'s subject is `_verify_backup_integrity`, whose implementation is a subset test with a
  floor contract. Equality there reverses the gate. **Struck.**
- `(r4)`'s subject is `{trades columns} - {Trade dataclass fields} == {two names}`. There is no
  subset instrument behind it; it is a DECISION LEDGER, and gotcha #11's 2026-08-24 amendment makes
  the drift comparator the **MANDATORY** member of the mirror set precisely because a `>=`/subset
  form silently absorbs the next column added without a decision. **NOT struck.**

The originating handoff (`docs/orchestrator-handoff-2026-09-07-22a4-executing.md:107`) names the
sentence by phrase and carries **no line number**; the brief resolved the phrase by literal match,
which landed in the wrong section. `(m3c)` at `:724` said "EQUALS", not "EQUALITY, NEVER A SUPERSET
CHECK", so no phrase match into `(m3c)` was available. **Encoded: `:724` struck, `:925` kept, and
`(r4)` now carries an explicit paragraph distinguishing the two so the next reader cannot conflate
them by phrase.** Reported to the orchestrator in the return report.

### Supersession 2 — the mis-named version tests (orchestrator, his lane, 2026-09-07)

**RULED: rename all six.** All five brief-supplied rows verified on disk at the exact lines given
(`test_migration_0036_provenance_corrections.py:56/:60`, `test_migration_0033.py:141`,
`test_migration_0031_untracked_broker_position.py:55`,
`test_migration_0030_yfinance_calls.py:33`), plus the plan's own
`test_22a_task2_migration_0037.py:98`. **Renamed to the `..._is_head` form** rather than `..._is_38`
— the form the codebase already converged on at its three most recent instances
(`test_migration_0032.py::test_expected_schema_version_is_current`,
`test_migration_0034_h1_criteria_amendment.py` and
`test_migration_0035_fills_trades_price_divergence.py`, both `..._is_head`). `..._is_38` satisfies
the rule for exactly one migration and then re-creates the defect; `head` satisfies it permanently.
This is a deviation from the plan's literal *"the assertion becomes 38 and the NAME must too"* and
is reported as such.

**INTAKE CORRECTION: the population is TWENTY-SIX, not six — and it is NOT homogeneous.** Measured
by an AST walk mapping every one of this commit's 44 version-mirror edit sites to its enclosing
function and reading each name (a value grep cannot do this; the seventh spelling is exactly the one
no value grep reaches). Twenty further test functions carry a stale version number in the NAME while
this commit edits their BODY to 38. **They were NOT renamed, because a recorded counter-convention
exists and it is not the executing cell's to supersede:**
`tests/data/test_phase13_t3_sb1_prerequisite.py:45-52` states *"Test name preserved to keep
grep-history continuity per cumulative discipline (the corresponding tests in test_migration_0017.py
etc. follow the same stale-name-but-current-assertion pattern)"*, and
`tests/data/test_v21_migration_trade_backlinks.py` repeats it verbatim for its own row. **The
ruling's rule and that convention conflict**, so the twenty are ROUTED to the orchestrator rather
than settled inside the work. The full roster is in the return report.

### Intake correction 3 — the plan's own `_current_version` classification was half right

**FOUND BY THE FULL SUITE, not by reading.** The plan's Task-1 sweep rule said *"Two
`_current_version(...) == 37` sites in `tests/data/test_22a_task2_migration_0037.py` are assertions
about migration 0037's own result and STAY at 37."* **Only ONE is.**

- `:107` `test_migration_applies_to_a_v36_fixture_and_stamps_37` builds a v36 database via the local
  `_v36` helper and runs to `target_version=37`. About 0037's own result. **Stays at 37.**
- `:130` `test_running_the_migration_twice_is_a_no_op` takes the module's `conn` FIXTURE, which is
  `ensure_schema` and therefore walks to **HEAD**. Its `target_version=37` call returns immediately
  (`current >= target_version`), so the assertion is about HEAD. **Becomes 38** — and it was the
  ONE red on the first full-suite run (`assert 38 == 37`).

*The classification was made by reading the call's ARGUMENTS and not its FIXTURE, which is a
classification of half the statement.* The plan text is superseded by replacement at both the S4
count row and the Task-1 rule.

### Intake correction 4 — a fixture that asserted nothing

`(r3)`'s and `(e2)`'s UPPERCASE-canonical rows were first written as `TOK_A.upper()` where
`TOK_A = "00000000-0000-4000-8000-000000000001"` — **all digits and hyphens, so `.upper()` is the
identity function** and the "uppercase defeats the UNIQUE index's text key" case was asserting the
lowercase case a second time. Caught by execution (the row went green against the canonical token
and red against the validator). Replaced with `TOK_MIXED = "0a0b0c0d-0e0f-4a1b-8c2d-0e3f4a5b6c7d"`,
which carries hex letters, and the reason is recorded beside the constant.

---

# 22-A4 EXECUTING -- Codex A-loop findings ledger

Artifact: the arc diff `2d9e4a34..HEAD` (`swing/`, `tests/`), worktree `.worktrees/22-a4-exec`.
Base `2d9e4a34`; pre-loop head `c9bc4838` (Tasks 0b/1, 1b, 3, 4, 5 -- **FIVE commits**, not the six
the dispatch brief said; measured by `git log --oneline 2d9e4a34..HEAD`, and Task 0b landed INSIDE
Task 1's commit `48029a06` exactly as the plan's Task 0b row specifies).
Transport: WSL codex-cli **0.152.1**, `codex exec -p strong -s read-only --skip-git-repo-check -`,
stdin bundle (prompt + full arc diff) with the WORKTREE as cwd so the reviewer can verify the code's
claims against the repository (recipe §3 REPO ACCESS, mandatory for production-code review).

**Criterion (recipe, executing/production-code reviews):** blocking = CRITICAL or MAJOR; convergence
= the FIRST round returning zero new critical/major. The plan-stage `fast` tier and the
result-bearing criterion do NOT apply here: this is production code and the tier is `strong`.

**Ledger conventions:** this section conforms to the `## LEDGER CONVENTIONS` block above. Every
finding carries ONE header shape -- `**A4X-R<round>-<n> -- <SEVERITY> -- <CLASS> -- <text>` -- with
SEVERITY in `CRITICAL`/`MAJOR`/`MINOR` and CLASS in `NEW GROUND`/`RESIDUAL`. The `A4X-` prefix
distinguishes the EXECUTING loop's ids from the writing-plans loop's `A4-` ids above; no id in this
section is the same finding as any id in that one.

## Round ledger

| round | tier / model / effort | C / MAJ / MIN | new | reopened | reverted | verdict |
|---|---|---|---|---|---|---|
| **1** | `strong` / `gpt-5.6-sol` / `high` | 1 / 4 / 5 | 10 (**10 new ground, 0 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **2** | `strong` / `gpt-5.6-sol` / `high` | 1 / 1 / 4 | 6 (**3 new ground, 3 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **STOP** | *(loop STOPPED at a DESIGN FORK, `A4X-R2-01`; NO round 3 opened -- no review round opens while a ruling is outstanding)* | -- | -- | -- | -- | **NOT convergence. A stopped-short loop, reported as one.** |

## Per-round mechanical assertions

### Round 1 -- ALL FIVE PASS, stated as measurements

| assertion | measured |
|---|---|
| 1. banner model | `model: gpt-5.6-sol` (transcript line 4) |
| 2. `model_reasoning_effort` | `reasoning effort: high` (transcript line 8) |
| 3. `grep -c '^ERROR'` | **0** |
| 4. `grep -c '^tokens used'` | **1**; footer value **441,127** |
| 5. anchored verdict token | `^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0** -- one distinct token present, the other absent, which is the invariant on 0.152.1 (that version emits the final message TWICE) |

Plus the TWO-SIGNAL rule, both measured and both required: **exit code 0** (read from
`.codex-exit-r1.txt`, written by the runner, not inferred from the harness) **AND** a NON-EMPTY
transcript (**1,550,758 bytes**). Process exit was confirmed by `pgrep -c codex` = 0 before the file
was read -- a transcript is not a stable artifact while its process lives.

**Content-filter events: NONE.** Codex self-attested in the response body: *"No safety-layer refusal
or rewriting occurred."*

**Prior-round-findings prohibition: HONORED, and here is the grep that shows it.**
`grep -n -i "copowers-findings\|codex-review-r\|codex-prompt-r\|\.ledger\.md"` over the round-1
transcript returns hits in exactly three classes, none of them a read: (a) the prompt's own
prohibition text echoed back, (b) the arc diff's own hunk header for the committed ledger file
(that file is part of the arc and is therefore legitimately in the review INPUT), and (c) prose in
`CLAUDE.md` / `docs/orchestrator-context.md` that merely mentions `.copowers-findings.md`.
**Codex went further than asked and excluded them at the tool level** -- transcript line 16499
shows its own ripgrep carrying `--glob '!*.ledger.md' --glob '!.codex-*' --glob
'!*.copowers-findings.md'`. It also self-attested: *"I did not run git or open any prohibited
review/ledger file."* The scratch relocation was the structural half: every `.codex-*` file and the
findings file lived in the session scratchpad for the whole loop, not at the worktree root.

## Round-1 dispositions

**Every premise below was checked against the code BEFORE anything was changed.** One CRITICAL and
one MAJOR were rejected on a verified premise correction; the other eight were fixed.

**`A4X-R1-01` -- CRITICAL -- NEW GROUND -- the mint's `PRAGMA database_list` on the body-raise path**
**PREMISE TRUE, CLASSIFICATION FALSE. NO CODE CHANGE.** The factual half is correct and I confirmed
it by reading: `_begin_attempt_identity` calls `_resolve_main_db_path`, which executes `PRAGMA
database_list` (`swing/data/db.py:605`), so on a body-raise the pre-arc tree had run one fewer
statement. **The classification is measured against a lock that does not exist.** 22-A LOCK clause
(c) reads, verbatim (`...-primitive.md:909-910`): *"every pre-existing failure branch raises the
same exception, with the same message, at the same point."* It locks the EXCEPTION, the MESSAGE and
the POINT. The pragma changes none of them, and the design plan states this outcome explicitly at
`:909-912` -- *"still holds for ALL of them, because the mint changes no branch and no ordering."*
The "NO statement" wording the finding leans on belongs to a DIFFERENT and narrower clause: the
deferred path's observation block in `record_entry`'s handler (`-EXECUTING.md:509-511`), which
gained no statement. **The over-broad paraphrase was MINE, in the round-1 prompt**, and the round-2
prompt quotes clause (c) verbatim instead. MEASURED on this box: `PRAGMA database_list` leaves
`in_transaction` False and a following `BEGIN IMMEDIATE` succeeds, so it perturbs nothing.
**The proposed remedy is independently rejected on the merits, and this is the load-bearing half:**
deferring `_resolve_main_db_path(conn)` into the lost-commit branch would issue a statement on the
writer's OWN connection AFTER a failed or indeterminate commit -- exactly what RD's rule (i) and
`_read_resolution`'s non-mutating design exist to forbid. It would move a statement from a safe
place to the most dangerous one on the path. Declared into the round-2 prompt WITH this reason and
with challenge invited.

**`A4X-R1-02` -- MAJOR -- NEW GROUND -- the body-raise lock test does not observe pre-body SQL**
**FALLS WITH `R1-01`. NO CODE CHANGE.** Its subject is "a non-discriminating test on an explicitly
locked path," and the locked path it names is the one clause (c) does not create. The lock that DOES
exist over that region is asserted, and by a stronger instrument than the one proposed: (k3a)'s AST
walk pins that `_entry_transaction`'s `if not immediate:` arm contains no `Try` node and that the
`with` body is exactly one bare `yield` -- a structural assertion a statement-trace could not make.

**`A4X-R1-03` -- MAJOR -- NEW GROUND -- the immutable-field refusal was byte-exact**
**FIXED** (`74cb2815`). Verified before fixing: `_assert_real_column_name` raises
`ReservedJournalFieldError`, which derives from bare `Exception` (`:109`), and BOTH delivery
handlers catch `ValueError` only (`swing/cli.py:3941` -> `click.UsageError`, exit 2; the web route's
`except ValueError` -> 400, with the bare-`Exception` fallthrough reaching the 500 handler at
`reconcile.py:1753`). So a casing or quoting variant of `attempt_id` WAS refused -- nothing durable
was ever at risk, and the trigger remains the guard of record -- but on the tier-3 surface the
refusal arrived at step 6, after steps 4 and 5 had inserted the new correction row and advanced the
prior head's chain pointer, which defeats the ORDERING property the early check exists for; and it
arrived as an exception neither delivery surface catches. `_normalize_journal_field_name` strips one
matched quoting pair and casefolds; the lookup table is DERIVED from `_IMMUTABLE_JOURNAL_FIELDS` so
the two cannot drift. **The widening refuses nothing that existed before this arc** -- the set's only
member is `trades.attempt_id`, a column migration 0038 creates. Nine (m8e) rows; **eight fail against
the byte-exact predicate** and the ninth is the negative control proving normalisation did not become
a substring test.

**`A4X-R1-04` -- MAJOR -- NEW GROUND -- the backup gate never tested `target_version > 38`**
**FIXED** (`1f8fb55c`). Matrix was (37,38), (36,38), (37,37) -- all satisfied by a `target_version ==
38` mutant, which would SKIP the pre-0038 backup for a v37 installation jumping straight to a later
head. **MUTANT BUILT AND RUN: `target_version == 38` fails the amended row.** The added case uses its
own directory, because the backup filename is stamped to the second and a same-second collision
would read as a count of 1 -- an artifact of the clock, not of the gate.

**`A4X-R1-05` -- MAJOR -- NEW GROUND -- the expected-table set did not prove its declared inheritance**
**FIXED** (`1f8fb55c`). Subset-of-real-v37 plus the three 0037 names is satisfied by a constant
holding ONLY those three. **MUTANT BUILT AND RUN: a parentless constant fails the amended row.** The
added assertion is equality against the SPECIFIED PARENT-DERIVED SET, which is a different claim
from the equality-against-the-real-v37-schema that CHARC's 2026-09-07 ruling rejected -- that one
would reverse the gate's floor direction; this one pins the constant to its own definition. The
ruling is not disturbed.

**`A4X-R1-06` -- MAJOR -- NEW GROUND -- migration 0038's transaction framing was untested**
**FIXED** (`1f8fb55c`). Nothing asserted BEGIN-first, COMMIT-last, the version bump immediately
before COMMIT, or that a mid-script failure persists nothing -- and gotcha #9 is precisely why that
matters. Added a normalized statement-ordering row and a planted-failure counterexample on a real
v37 database. **MUTANT BUILT AND RUN -- and the first attempt at it PASSED, which is itself the
finding-behind-the-finding:** the file HEADER contains the literal text `BEGIN;` and `COMMIT;` in
prose, so a bare string replace edited the comment and the mutant was never built. Anchoring on the
surrounding newlines built it, and **both new rows then failed.** The tests were never fooled -- the
helper strips comments -- only my mutant was, which is the same class this arc keeps meeting.

**`A4X-R1-07` -- MINOR -- NEW GROUND -- (m2) did not distinguish a partial index from a full one**
**FIXED** (`1f8fb55c`). Independently MEASURED: SQLite treats NULLs as distinct in a FULL unique
index too, so both the duplicate-token and four-NULL assertions pass either way; `PRAGMA index_list`
`partial` is the column that differs. **MUTANT BUILT AND RUN: a full unique index fails the amended
row.**

**`A4X-R1-08` -- MINOR -- NEW GROUND -- the trigger test did not prove the trigger is unconditional**
**FIXED** (`1f8fb55c`). All three tested transitions are value-CHANGING, so a `WHEN OLD.attempt_id
IS NOT NEW.attempt_id` trigger passes them while permitting `SET attempt_id = attempt_id` --
falsifying the migration header's stated contract. Two halves added, because each is weak alone: the
same-value assignment ABORTS (behaviour), and the stored trigger SQL carries no `WHEN` at all
(structure -- a `WHEN` that can evaluate to NULL fails OPEN, which is why the contract is no-WHEN
rather than a-correct-WHEN). **MUTANT BUILT AND RUN: the change-detecting trigger fails the new row.**
I had already measured the SHIPPED trigger aborting a same-value update during round 0, so the
finding is about the TEST, not the schema.

**`A4X-R1-09` -- MINOR -- NEW GROUND -- "never an inference" over-claimed one of the four fields**
**FIXED** (`06040d6e`). True of three; false of `cleanup_raised` on the DEFERRED path, where
`__exit__` owns the rollback, no Python frame observes the call, and the fact is DERIVED from the
escaping exception's `__context__`. The derivation is sound and contained toward the ALARM; the
wording now says derivation, because calling it an observation flattered it.

**`A4X-R1-10` -- MINOR -- NEW GROUND -- a stale "CLAUSE 2 IS REVERTED" above the guarded region**
**FIXED** (`06040d6e`). Gotcha #31's exact shape, one commit after this arc restored clause 2 as a
gated settle: the comment still read as an invariant while the code had moved. Amended to the
conditional contract.

**`A4X-R1-11` -- MINOR -- NEW GROUND -- `_log_contained`'s returned error is discarded**
**FIXED** (`06040d6e`). Documented rather than re-plumbed: the return exists for a caller WITH a
reporting channel, and this call site fires on a path where the entry SUCCEEDS, so there is no
escaping exception to attach a note to. The honest statement is that the path cannot surface a sink
failure, not that it declines to.

### What round 1 explicitly cleared

Codex reported no correctness defect in the core settle predicate, fresh-connection visibility,
probe-returned-id selection, ticker corroboration, v38 INSERT ordering, or the 45-column/45-parameter
binding (it counted both by AST and printed `placeholders 45 tuple 45`), and it verified the CPython
rollback-chain premise on BOTH the declared 3.11 floor and 3.14.2. It could not run pytest -- no
pytest in its sandbox -- and used static inspection plus targeted SQLite/Python probes instead.

### Verdict

`NEW_CRITICAL_MAJOR_FOUND` -- anchored, twice (0.152.1 duplicates the final message), with
`^NO_NEW_CRITICAL_MAJOR` at zero and `^ERROR` at zero.


## Round 2 -- ALL FIVE ASSERTIONS PASS

| assertion | measured |
|---|---|
| 1. banner model | `model: gpt-5.6-sol` |
| 2. `model_reasoning_effort` | `reasoning effort: high` |
| 3. `grep -c '^ERROR'` | **0** |
| 4. `grep -c '^tokens used'` | **1**; footer value **590,318** |
| 5. anchored verdict token | `^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0** |

Exit code MEASURED **0**; transcript NON-EMPTY (**1,869,407 bytes**); `pgrep -c codex` = 0 before the
file was read. **Content-filter events: NONE.** The prior-round-findings prohibition was HONORED --
the same grep as round 1 returns only the prompt's own echo, the arc diff's own ledger hunk header
(that file is part of the arc and is legitimately in the review INPUT), and `CLAUDE.md` /
`docs/orchestrator-context.md` prose that merely mentions `.copowers-findings.md`.

**The round-2 prompt QUOTED 22-A LOCK clause (c) VERBATIM** instead of paraphrasing it, and carried
the round-1 CRITICAL's adjudication as a declared item with its reason and challenge invited. Round
2 did not re-raise it.

**Round 2 independently re-derived the CPython premise BY NETWORK FETCH** of both `v3.11.0` and
`v3.14.2` `Modules/_sqlite/connection.c`, and confirmed SOURCE (S1) on both. It also cleared the
migration transaction framing, the v38 INSERT parameter alignment, the UNIQUE/CHECK relationship,
trigger firing semantics, backup-gate wiring, and all three corrector refusal sites.

## Round-2 dispositions

**A4X-R2-01 -- CRITICAL -- NEW GROUND -- the PROOF-TO-RETURN TAIL can discard a proven-durable entry**
**PREMISE VERIFIED AT THE CODE. NOT FIXED. ROUTED AS A DESIGN FORK -- THIS IS WHY THE LOOP STOPPED.**
Two windows, both confirmed by reading the shipped code:

1. `swing/trades/entry.py:1021` -- `return found` sits INSIDE
   `_settle_by_attempt_identity`'s own `try: ... except BaseException as settle_error: ... return
   None`. At that statement the fresh read has ALREADY returned a row and the ticker has ALREADY
   matched. A `BaseException` delivered there is converted to `None`, and the caller re-raises over
   a durable entry.
2. `swing/trades/entry.py:1387-1392` -- `settled_trade_id, _settled_ticker = settled` and the
   `dataclasses.replace` run INSIDE the `except BaseException as post_commit_error:` suite, with NO
   enclosing handler, so a fault there escapes despite the durable proof.

**The argument is the arc's OWN principle turned back on it.** `_durability_probe` contains its
`close()` failure precisely because a tidy-up failure after a successful read must not discard the
read -- its docstring says discarding a valid answer that way "would report a durable entry as a
failure." One frame up, the same asymmetry is unguarded. And the arc has ALREADY RATIFIED that this
injection class is reachable: (k3b) drives a `sys.settrace` fault at `outcome.committed = True` and
requires the settle to happen anyway.

**WHY IT IS A FORK AND NOT A FIX I MAY TAKE.** The reviewer's remedy is to "repeat the fresh
attempt-ID read" on a secondary fault. That is a SECOND PROBE -- a second fresh connection opened on
an already-failing money path, in a window where an asynchronous exception is in flight -- and it
**contradicts a shipped, deliberate assertion**: `tests/trades/test_22a4_attempt_identity.py`
asserts `probe_args == [token]` and that the mint ran exactly once, i.e. ONE probe per attempt, by
design. A cheaper shape exists, but choosing between the shapes is a design decision on this arc's
most safety-critical function, against a contract two directors ratified.

**A4X-R2-02 -- MAJOR -- NEW GROUND -- no test covers the proof-to-return boundary**
**NOT FIXED -- CONTINGENT ON THE SAME RULING.** Verified: the only `sys.settrace` injection in the
settlement suite targets `_entry_transaction`'s `outcome.committed = True`; nothing injects at the
matching `return found` or at the first post-settle line. The test to write is determined by which
branch of `A4X-R2-01` is ruled, so writing one now would pin whichever shape I picked.

**A4X-R2-03 -- MINOR -- RESIDUAL -- three comments still called clause 2 reverted**
**FIXED.** Two sites said "the reverted clause 2" and one said the split gate's "TWO BRANCHES THAT
BOTH RE-RAISE... THE BEHAVIOUR IS UNCHANGED" -- true when Task 3 split it, false one commit later
when Task 4 made the second branch settle. Gotcha #31, inside this arc's own Task-3-to-Task-4 seam.

**A4X-R2-04 -- MINOR -- RESIDUAL of my own A4X-R1-09 fix -- the count went incoherent**
**FIXED.** The R1-09 edit left "THREE OBSERVATIONS" in one paragraph and "ONE OF THE FOUR" in the
next. It is THREE FIELDS across FOUR path-specific provenance cases, one of which is the derivation,
and it now says exactly that.

**A4X-R2-05 -- MINOR -- RESIDUAL of my own A4X-R1-03 fix -- the backstop comment went stale in the fixing commit**
**FIXED.** The comment still described a casing variant as missing the immutable set and being
caught late by `_assert_real_column_name` -- which the normalization fix falsified in the very
commit that wrote the fix.

**A4X-R2-06 -- MINOR -- NEW GROUND -- the schema-head catalog stopped at 0037**
**FIXED.** The catalog immediately above `EXPECTED_SCHEMA_VERSION = 38` described the constant's
PREDECESSOR. Migration 0038 now has its entry.

## THE FORK, STATED FOR THE RULING

**Question:** how should a fault delivered AFTER the durability proof, but BEFORE the degraded
`EntryResult` reaches the caller, be handled?

- **Branch A -- RE-PROBE (the reviewer's proposal).** A nested boundary around the handoff that, on
  a secondary fault, repeats the fresh attempt-id read and returns degraded success on a match.
  *Cost:* a second connection open on a failing money path; **breaks the shipped
  one-probe-per-attempt assertion**, which would have to be re-specified rather than merely edited.
- **Branch B -- MAKE THE PROOF UNDISCARDABLE WITHOUT RE-READING.** Narrow
  `_settle_by_attempt_identity`'s `except BaseException` so it cannot convert a proof that already
  exists (the handler covers the READ and the corroboration, not the RETURN), and give
  `record_entry` a boundary over the two statements between the settle and the existing
  degraded-result construction. *Cost:* no new I/O and no new failure mode, but still a change to
  the containment shape of the arc's most safety-critical function.
- **Branch C -- DECLARE IT.** Accept the window as a named residual, on the ground that it needs an
  asynchronous `BaseException` inside a two-statement window on an already-failing path, and that
  `ux_trades_one_open_per_ticker` blocks the retry for any ticker still open. *Cost:* the declared
  uncovered direction (a ticker CLOSED between attempts) stays uncovered, and the arc would ship a
  known instance of the exact defect clause 1 exists to prevent.

**I did not choose.** `A4X-R2-02`'s test follows whichever branch is ruled.

## Transcript manifest -- EXECUTING loop (final)

Durable path: `C:/Users/rwsmy/swing-data/review-transcripts/22-a4-exec/` (dotfiles -- use `ls -a`).
Copied THE MOMENT the five assertions passed, per `harness-architecture.md` section 5.1.

| transcript | bytes |
|---|---|
| `.codex-review-r1.txt` | 1,550,758 |
| `.codex-review-r2.txt` | 1,869,407 |
| `.codex-prompt-r1.md` | 10,760 |
| `.codex-prompt-r2.md` | 13,678 |

**SPEND, both counted rounds: 441,127 + 590,318 = 1,031,445 tokens.**

## Round 3 -- THE CONFIRMING ROUND ON THE FIX LEG. IT DID NOT CONVERGE.

Artifact: `git diff -U8 2d9e4a34..HEAD -- swing/ tests/` at head `f7d78737` (the fix leg's three
commits `4589c2f9`, `dd714d4c`, `f7d78737` on top of the pre-loop head). **The FULL arc diff was
sent, not the fix leg alone** -- the fix leg's correctness depends on the code it changes, and a
defect in the COMPOSITION of the two is exactly what a fix-only diff cannot show.

| assertion | measured |
|---|---|
| 1. banner model | `model: gpt-5.6-sol` |
| 2. `model_reasoning_effort` | `reasoning effort: high` |
| 3. `grep -c '^ERROR'` | **0** |
| 4. `grep -c '^tokens used'` | **1**; footer value **513,003** |
| 5. anchored verdict token | `^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0** |

Exit code MEASURED **0**; transcript NON-EMPTY (**1,683,792 bytes**); `pgrep -c codex` = 0 before
the file was read. **Content-filter events: NONE** (Codex self-attested). Codex could not run the
pytest suite (no pytest on its interpreter) and said so; it ran AST, disassembly, SQLite and
`sys.settrace` probes instead. Prior-round-findings prohibition HONORED -- 17 grep hits, all four
classes benign, and Codex EXCLUDED the ledger and `.codex-*` at the tool level in its own ripgreps.

## Round-3 dispositions

**Every premise below was REPRODUCED BY EXECUTION before anything was changed** -- the two findings
against the fix leg were driven with `sys.settrace` through the production path, and the SQLite
claim was re-measured on this box's engine.

**A4X-R3-01 -- MAJOR -- NEW GROUND -- the capture MOVED the settle's window; the declaration said it
was GONE, and the alarm still said the read FAILED**
**FIXED (`fa6f0674`).** REPRODUCED: a `sys.settrace` fault at `proven = found`, with the probe
having returned a corroborated row, re-raised `OperationalError('commit lost (planted)')` with
**one durable row on disk**, and emitted *"the settle-by-attempt-identity read FAILED"*. **Both
halves of the finding land on the fix leg's own two commits**: the declaration's sentence that the
settle's whole proof-to-return tail was out of the alarm family was FALSE, and the no-proof arm's
wording reproduced the exact false sentence RD's ruling required be removed -- one statement
further along. The class is irreducible, so the capture boundary is now DECLARED as a member of the
family, and the arm says only what it can observe: *no corroborated proof was captured, either
because the read/gate yielded none or because a fault arrived before the capture landed.* Row
`(A4X-R2-02d)` drives it and fails against the wording as it shipped one commit earlier.

**A4X-R3-02 -- MAJOR -- NEW GROUND -- window 2 is not two statements**
**FIXED (`fa6f0674`).** REPRODUCED at TWO interior points: a fault at
`post_commit_error_text = safe_text(...)` and a fault at `return degraded` BOTH escaped over a
durable row, each carrying the original commit error as `__context__`. An exception raised inside an
`except` suite is not caught by the `try` whose handler is running, and the tail's only nested
handler protects the `log.error` call, so the exposure runs from the settle's return THROUGH
`return degraded`. **"Two statements" was an incidental FACT in the ruling packet**, carried into
the declaration unverified -- the intake check this cell owed and did not perform. The ruled
DIRECTION is untouched: both boundaries stay DECLARED, the family's composition and belt are
unchanged. The bound is now stated by NAMING ITS ENDPOINTS rather than by counting statements, and
row `(A4X-R2-02e)` measures the far end.

**A4X-R3-03 -- MAJOR -- NEW GROUND -- the resolved-name normalizer misses three more spellings**
**PREMISE VERIFIED. NOT FIXED -- OUT OF THIS LEG'S DISPATCH SCOPE; FLAGGED TO THE ORCHESTRATOR.**
Measured on this box (SQLite **3.50.4**, vs Codex's 3.45.1 -- same result):
`UPDATE t SET 'attempt_id' = ?`, `UPDATE t SET (attempt_id) = ?` and
`UPDATE t SET /*x*/attempt_id = ?` all changed the column, while
`_normalize_journal_field_name` returned `"'attempt_id'"`, `"(attempt_id)"` and `"/*x*/attempt_id"`
UNCHANGED -- so all three miss `_IMMUTABLE_JOURNAL_FIELDS_BY_RESOLVED_NAME`. This is Task 1b's and
round-1-fix `74cb2815`'s code, not the fork-fix leg's; recipe section 5 says a defect outside scope
is FLAGGED, never fixed inline. The tier-3 write-ordering half of the finding is Codex's claim,
reported as such -- this cell verified the normalizer bypass and the SQLite grammar, not the
step-4-to-6 write sequence.

**A4X-R3-04 -- MINOR -- NEW GROUND -- the backup gate's docstring formula**
**PREMISE VERIFIED. NOT FIXED -- OUT OF SCOPE; FLAGGED.** `swing/data/db.py`'s gate docstring cites
the `pre_version == (target - 1)` gotcha while the implemented condition is
`current_version == 37 AND target_version >= 38`, which fires at `target_version=39`. Note the
implementation is the PROJECT-CANONICAL shape (CLAUDE.md: *"Copy the Phase 9
`pre_version == 16 AND target >= 17` clause shape verbatim"*) and the docstring's own first sentence
states it correctly; only the parenthetical formula is loose. Task 1's code.

## THE LOOP IS STOPPED SHORT AT ROUND 3. THIS IS NOT CONVERGENCE.

Three counted rounds ran; **all three returned `NEW_CRITICAL_MAJOR_FOUND`**. The dispatch brief set
three counted rounds as the default and required **the orchestrator's written authorization, naming
the task-bearing finding, before a fourth**. That authorization was not held, so no round 4 opened.

**What that leaves outstanding, stated plainly rather than softened:**

* `A4X-R3-01` and `A4X-R3-02` were FIXED after the last counted round, so **the final head
  `fa6f0674` has not been reviewed by any Codex round.** A confirming round on it is unrun.
* `A4X-R3-03` (MAJOR) and `A4X-R3-04` (MINOR) are VERIFIED and UNFIXED, outside this leg's scope.

## Round ledger -- EXECUTING loop (cumulative)

| round | tier / model / effort | C / MAJ / MIN | new | reopened | reverted | verdict |
|---|---|---|---|---|---|---|
| **1** | `strong` / `gpt-5.6-sol` / `high` | 1 / 4 / 5 | 10 (**10 new ground, 0 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **2** | `strong` / `gpt-5.6-sol` / `high` | 1 / 1 / 4 | 6 (**3 new ground, 3 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **STOP** | *(loop STOPPED at a DESIGN FORK, `A4X-R2-01`; RD ruled it 2026-09-08)* | -- | -- | -- | -- | **routed, not convergence** |
| **3** | `strong` / `gpt-5.6-sol` / `high` | 0 / 3 / 1 | 4 (**4 new ground, 0 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **STOP** | *(three counted rounds is the default; a fourth needs written authorization naming the task-bearing finding, and it is not held)* | -- | -- | -- | -- | **A STOPPED-SHORT LOOP, reported as one. NOT convergence.** |

**Context-depth column: DELIBERATELY EMPTY.** A cell cannot see its own depth (no hook fires for a
subagent), so a self-estimate there is not a record; the orchestrator fills it from
`python scripts/cell_depth.py --live <h>`.

## Transcript manifest -- EXECUTING loop (through round 3)

Durable path: `C:/Users/rwsmy/swing-data/review-transcripts/22-a4-exec/` (dotfiles -- use `ls -a`).
Copied THE MOMENT the five assertions passed, per `harness-architecture.md` section 5.1.

| transcript | bytes |
|---|---|
| `.codex-review-r1.txt` | 1,550,758 |
| `.codex-review-r2.txt` | 1,869,407 |
| `.codex-review-r3.txt` | 1,683,792 |
| `.codex-prompt-r1.md` | 10,760 |
| `.codex-prompt-r2.md` | 13,678 |
| `.codex-prompt-r3.md` | 18,580 |
| `.codex-exit-r3.txt` | 2 |
| `run_r3.sh` (the round-3 runner, with its four hazards commented) | 1,266 |

**SPEND, all three counted rounds: 441,127 + 590,318 + 513,003 = 1,544,448 tokens.**

## Round 4 -- THE FOURTH COUNTED ROUND, ON THE FINAL SHAPE. IT DID NOT CONVERGE.

**Written authorization held** (orchestrator, 2026-09-08, dispatch brief
`docs/22-a4-r3-03-structural-leg-dispatch-brief.md` section 1), naming `A4X-R3-03` as the
task-bearing ground. The round opened only AFTER `2eebfbee` (R2, the structural invariant) and
`d34e1493` (R3, the docstring) landed -- one round, on the final shape, never its own wake.

Artifact: `git diff -U8 2d9e4a34..HEAD -- swing/ tests/` at head `d34e1493` (403,409 bytes).
**The FULL arc diff was sent again, not this leg alone** -- and this round is the first to see FOUR
commits: `fa6f0674` and `df231195` (the round-3 fixes, which landed after the last counted round)
plus this leg's `2eebfbee` and `d34e1493`.

| assertion | measured |
|---|---|
| 1. banner model | `model: gpt-5.6-sol` |
| 2. `model_reasoning_effort` | `reasoning effort: high` |
| 3. `grep -c '^ERROR'` | **0** |
| 4. `grep -c '^tokens used'` | **1**; footer value **604,767** |
| 5. anchored verdict token | `^NEW_CRITICAL_MAJOR_FOUND` = **2**, `^NO_NEW_CRITICAL_MAJOR` = **0** |

Exit code MEASURED **0** (`.codex-exit-r4.txt`); transcript NON-EMPTY (**1,635,869 bytes**,
27,836 lines); `pgrep -c codex` = **0** before the file was read. **Content-filter events: NONE**
(Codex self-attested: *"No safety-layer refusal or rewriting occurred."*). Codex could not run the
pytest suite (no pytest on its interpreter, no writable temp) and said so; it ran ripgrep, AST and
in-memory SQLite probes instead -- it applied migration 0038 in-memory and exercised the CHECK, the
partial UNIQUE index, the trigger, the repo INSERT binding order, and all seven non-canonical
spellings against the new gate. Prior-round-findings prohibition **HONORED** -- 8 grep hits for the
prohibited names, of which 2 are the prompt's own prohibition text, 3 are Codex EXCLUDING those
files at the tool level in its own ripgreps (`--glob '!**/*.ledger.md'` etc.), and 3 are incidental
prose inside repo docs it legitimately read (`CLAUDE.md`, `orchestrator-context.md`, an archived
brief). No read of any prior-round findings file.

**A launch note worth keeping, because it is the SIXTH correction to this seam and it is NEW:**
the round-3 invocation form `wsl.exe bash /mnt/c/.../run_r4.sh` -- "non-path-initial", the recipe's
stated remedy for MSYS mangling -- **FAILED at exit 127**: MSYS rewrote the SECOND argument to
`C:/Program Files/Git/mnt/c/...`. Making the argument non-path-initial is not sufficient when the
path is a separate argv element; MSYS converts any argument that LOOKS like a POSIX path, wherever
it sits. The form that ran is
`MSYS_NO_PATHCONV=1 wsl.exe bash -lc 'bash /mnt/c/.../run_r4.sh'` -- the env var disables the
conversion outright and the `-lc` string is itself non-path-initial. The failure was LOUD (exit 127
with a diagnostic), not one of the exit-0 family, and the pre-created empty redirect target
confirmed no round had happened.

## Round-4 dispositions -- EVERY PREMISE VERIFIED AGAINST THE CODE, NONE FIXED

**This leg holds no authorization for a fifth counted round**, and the brief's section 1 is
explicit: *"If round 4 finds task-bearing work, STOP and report the full cumulative ledger."* All
five findings below are therefore **VERIFIED AND UNFIXED**, routed to the orchestrator with the
smallest correct fix named. Fixing them here would leave the branch in a shape no round has seen,
which is the state the single-round authorization exists to prevent.

**What round 4 found NO defect in, stated because it is the round's main result:** the production
invariant this leg was dispatched to build. Codex independently enumerated the operator paths,
constructed key orderings against the whole-payload property, checked the cash
`net_amount -> amount` mapping at the gate / SELECT / UPDATE for consistency, and confirmed no
remaining reference to the deleted resolver. Its words: *"I found no new critical production-code
defect: the settlement gate, migration, repo mirrors, and production corrector ordering hold on the
reviewed head."* **All four majors and the one minor are against TESTS, COMMENTS and DOCSTRINGS.**

**A4X-R4-01 -- MAJOR -- NEW GROUND -- the single-field operator path has no discriminating row**
**PREMISE VERIFIED. NOT FIXED -- no round-5 authorization.** `grep -c operator_alternative
tests/trades/test_22a4_corrector_refusal.py` returns **0**. This leg added the byte-exact gate at
`swing/trades/reconciliation_auto_correct.py:2745` (`_handle_single_field_correction`, the path
`operator_alternative` reaches with an operator-supplied payload) and shipped NO row that fails
when that call is deleted: with it gone, `_validate_correction_target` and `_read_journal_value`
interpret a non-canonical key before `_update_journal_field`'s backstop refuses it, and every
`(m8f)` row still passes. **The gate I added to make "every corrector path" literally true is the
one path the closure test does not close.** Smallest fix: a parametrized `operator_alternative`
row spying on `_validate_correction_target` and `_read_journal_value` and asserting neither is
reached -- zero-write assertions alone do not discriminate this mutant, because no write precedes
the backstop on that path.

**A4X-R4-02 -- MAJOR -- NEW GROUND -- `Attempt_Id` was dropped in the (m8e) supersession**
**PREMISE VERIFIED. NOT FIXED -- no round-5 authorization.** The deleted `(m8e)` rows covered
`ATTEMPT_ID`, `Attempt_Id`, `[attempt_id]` and `"attempt_id"`; `_NON_CANONICAL_SPELLINGS` carries
six members and `Attempt_Id` is not among them. **The supersession note I wrote NAMES `Attempt_Id`
among what the deleted rows covered and then says they are "not relaxed" -- a false claim in
normative position, in the very comment written to record that nothing was lost.** Production is
correct (Codex executed the gate against `Attempt_Id` and it refuses), so this is a coverage
regression, not a bypass. Smallest fix: add `"Attempt_Id"` to the tuple; both parametrized surfaces
then cover it. This is the hand-enumerated-roster class arriving inside the commit that DELETED a
hand-enumeration for being one.

**A4X-R4-03 -- MINOR -- NEW GROUND -- the `affected_table` provenance comment omits one route**
**PREMISE VERIFIED. NOT FIXED.** `swing/trades/reconciliation_auto_correct.py:416-417` states
`affected_table` "comes from `_resolve_affected_target`, whose output is one of four module
constants" -- the injection-safety proof for the interpolated `PRAGMA table_info({affected_table})`.
On tier 3 it comes from `_select_correction_row` -> `get_correction` instead. The code is still
safe: `swing/data/migrations/0019_*.sql:48-50` CHECK-constrains
`reconciliation_corrections.affected_table` to the same four literals (VERIFIED by reading the
migration, per the cited-constraint rule). But **this leg made that comment more load-bearing** --
`2eebfbee` newly calls the gate from the tier-3 head, which is exactly the route the proof omits.
Smallest fix: name both sources.

**A4X-R4-04 -- MAJOR -- NEW GROUND -- the TEST twin of the defect `d34e1493` just fixed**
**PREMISE VERIFIED. NOT FIXED.** `tests/data/test_migration_0038_attempt_identity.py:150-151`
docstrings `test_m3a_the_gate_fires_only_on_the_exact_37_to_38_crossing` with *"STRICT EQUALITY on
pre_version per the ``pre_version == target - 1`` gotcha"* -- and the same test then asserts, at
lines 177-180 and with a comment explaining why, that the gate FIRES at
`current_version=37, target_version=39`, where that equation is false. **`d34e1493` fixed one
instance of this class and I did not re-grep the artifact for the rest** -- the
state-the-class-then-sweep discipline, missed on the commit that stated the class. Smallest fix:
the same rewrite, in the test docstring.

**A4X-R4-05 -- MAJOR -- NEW GROUND -- a window-1 test docstring calls the superseded shape "today's"**
**PREMISE VERIFIED. NOT FIXED -- and NOT this leg's code.**
`tests/trades/test_22a4_clause2_settlement.py:2148` reads *"THE NAIVE SUBSTITUTE IS TODAY'S SHIPPED
CODE"*, which was true when `dd714d4c` wrote it and was falsified by `4589c2f9` in the same leg:
`swing/trades/entry.py:1054-1055` now assigns `proven = found` then `return proven`, and `:1070`
returns it from the containment arm. The same paragraph already names `b3b518f9` as the measured
pre-fix shape, so the docstring contradicts itself. Smallest fix: *"the pre-fix `b3b518f9` shape."*

## THE LOOP IS STOPPED AT ROUND 4. THIS IS NOT CONVERGENCE.

Four counted rounds have run; **all four returned `NEW_CRITICAL_MAJOR_FOUND`.** The authorization
covered exactly one further round and said a fifth needs a fresh one naming its own task-bearing
finding. `A4X-R4-01`, `-02`, `-04` and `-05` are task-bearing (each changes a TEST or a docstring
that is load-bearing authority); `-03` is an instrument finding. None was fixed.

**What that leaves outstanding, stated plainly rather than softened:**

* Five findings VERIFIED and UNFIXED. Three of them (`-01`, `-02`, `-03`) are against this leg's
  own two commits; two (`-04`, `-05`) are older and were reached only because this round saw four
  previously-unreviewed commits.
* **The production change this leg was dispatched to make survived the round.** Zero critical and
  zero major findings against `swing/`.

## Round ledger -- EXECUTING loop (cumulative)

| round | tier / model / effort | C / MAJ / MIN | new | reopened | reverted | verdict |
|---|---|---|---|---|---|---|
| **1** | `strong` / `gpt-5.6-sol` / `high` | 1 / 4 / 5 | 10 (**10 new ground, 0 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **2** | `strong` / `gpt-5.6-sol` / `high` | 1 / 1 / 4 | 6 (**3 new ground, 3 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **STOP** | *(loop STOPPED at a DESIGN FORK, `A4X-R2-01`; RD ruled it 2026-09-08)* | -- | -- | -- | -- | **routed, not convergence** |
| **3** | `strong` / `gpt-5.6-sol` / `high` | 0 / 3 / 1 | 4 (**4 new ground, 0 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **STOP** | *(three counted rounds is the default; a fourth needs written authorization naming the task-bearing finding, and it was not held)* | -- | -- | -- | -- | **A STOPPED-SHORT LOOP, reported as one. NOT convergence.** |
| **4** | `strong` / `gpt-5.6-sol` / `high` | 0 / 4 / 1 | 5 (**5 new ground, 0 residual**) | 0 | 0 | `NEW_CRITICAL_MAJOR_FOUND` |
| **STOP** | *(the authorization covered ONE round; a fifth needs a fresh one naming its own task-bearing finding, and this cell does not hold one)* | -- | -- | -- | -- | **STOPPED SHORT AGAIN. NOT convergence.** |

**Context-depth column: DELIBERATELY EMPTY.** A cell cannot see its own depth (no hook fires for a
subagent), so a self-estimate there is not a record; the orchestrator fills it from
`python scripts/cell_depth.py --live <h>`.

## Transcript manifest -- EXECUTING loop (through round 4)

Durable path: `C:/Users/rwsmy/swing-data/review-transcripts/22-a4-exec/` (dotfiles -- use `ls -a`).
Copied THE MOMENT the five assertions passed, per `harness-architecture.md` section 5.1.

| transcript | bytes |
|---|---|
| `.codex-review-r1.txt` | 1,550,758 |
| `.codex-review-r2.txt` | 1,869,407 |
| `.codex-review-r3.txt` | 1,683,792 |
| `.codex-review-r4.txt` | 1,635,869 |
| `.codex-prompt-r1.md` | 10,760 |
| `.codex-prompt-r2.md` | 13,678 |
| `.codex-prompt-r3.md` | 18,580 |
| `.codex-prompt-r4.md` | 22,606 |
| `.codex-exit-r3.txt` / `.codex-exit-r4.txt` | 2 / 2 |
| `run_r3.sh` / `run_r4.sh` (the runners, with their hazards commented) | 1,266 / 1,269 |
| `fullsuite-prereview-r4.txt` (the pre-round-4 full-suite tail) | -- |

**SPEND, all four counted rounds: 441,127 + 590,318 + 513,003 + 604,767 = 2,149,215 tokens.**

---

## THE 2026-09-08 R4 RESIDUALS LEG -- **NOT A ROUND. NO CODEX RAN.**

Dispatched off `docs/22-a4-r4-residuals-leg-dispatch-brief.md` at base `8990f81f`. Round 4 cleared
production (zero critical, zero major against `swing/`); every finding it returned was against a
TEST, a comment, or a docstring. This leg closes those four findings and runs the uncounted
self-sweep §2 names, under the same discipline as the 2026-09-07 settling sweep: no round number, no
effect on convergence, which remains four counted rounds, none converged, loop stopped short.

### Disposition of the four round-4 findings -- 4 FIXED, 0 routed, 1 (`A4X-R4-03`, MINOR, out of
### this leg's authorized scope per the brief) left for the orchestrator

| finding | sev | disposition | commit |
|---|---|---|---|
| `A4X-R4-01` | MAJOR | **FIXED** | `0df336c2` -- a parametrized `operator_alternative` row (7 spellings) spies on `_validate_correction_target` / `_read_journal_value` and asserts neither is called; RED verified against `:2745` deleted (all 6 pre-existing spellings failed on `validate_spy.call_count == 1`), GREEN restored |
| `A4X-R4-02` | MAJOR | **FIXED** | `2782c5c0` -- `"Attempt_Id"` added to `_NON_CANONICAL_SPELLINGS` (now 7 members, read-counted); the SIX->SEVEN count corrected to match |
| `A4X-R4-04` | MAJOR | **FIXED** | `5fdd2e10` -- the test docstring now cites `current_version == 37 AND target_version >= 38`, matching `d34e1493`'s production-side wording exactly; test body unchanged |
| `A4X-R4-05` | MAJOR | **FIXED** | `25af3b53` -- the docstring now names the pre-fix `b3b518f9` shape instead of claiming "today's shipped code"; comment-only, `(k7a)`/`(k7b)` and every assertion unchanged |
| `A4X-R4-03` | MINOR | **NOT IN THIS LEG'S BRIEF** | the brief's four premises (`A4X-R4-01`, `-02`, `-04`, `-05`) did not include `A4X-R4-03` (the `affected_table` provenance comment omitting the tier-3 route); it remains open at round 4's own disposition and is the orchestrator's to route |

### THE UNCOUNTED SELF-SWEEP -- `SS-N` ids, no round number, no effect on convergence

Searched the arc's own artifacts (`swing/trades/reconciliation_auto_correct.py`,
`swing/trades/entry.py`, `swing/data/db.py`, `tests/trades/test_22a4_*.py`,
`tests/data/test_migration_0038_*.py`, this ledger) per class. Every hit found was one of the four
findings already fixed above; no additional instance surfaced in any class.

- **`SS-1` -- falsified naive-substitute / "today's shipped code" claims.** Grepped for
  `today'?s (shipped|code|implementation)`, `currently (does|is|ships)`, `the shipped
  (code|shape|implementation)`, `NAIVE SUBSTITUTE`, and bare `today` across all five artifacts.
  ONE hit: `A4X-R4-05` (fixed above). Every other bare-`today` occurrence (`entry.py:689,761,825,
  938,1463,2093`; `test_22a4_attempt_identity.py:720`; `test_22a4_clause2_settlement.py:1992`;
  `test_22a4_corrector_refusal.py:6`) was read in context and is either (a) a self-referential design
  tautology ("refusing costs today's behaviour" -- describing the COST of a design choice, not a
  claim a later commit could falsify) or (b) explicitly historical, scoped to the pre-fix world
  (`test_22a4_corrector_refusal.py`'s module docstring: "Pre-fix for every row here is the RED the
  plan declares"). `git blame` confirmed none of the `entry.py` sites sit inside code the window-1/
  window-2/`A4X-R3-03` fixes (`4589c2f9`, `f7d78737`, `fa6f0674`, `2eebfbee`) touched after the
  comment was written; the other four `entry.py` "naive substitute" paragraphs (`:2286`, `:2408`,
  `:2499`) name a counterfactual or an explicitly-superseded shape, never "today's", so they carry no
  exposure to this class. NIL beyond the one already-fixed instance.
- **`SS-2` -- coverage claims that outlived their coverage** (`not relaxed`, `still covered`,
  `superseded by replacement`, `each of N`, `covers all/every`). Two hits, both in
  `test_22a4_corrector_refusal.py` (`:441` "not relaxed", `:451` "covers all SIX") and both were
  `A4X-R4-02`'s own text -- fixed by the same commit that added `"Attempt_Id"` to the roster: "not
  relaxed" is now literally true (the (m8f) roster is a strict superset of (m8e)'s four), and the
  SIX->SEVEN correction was verified by a Python read of the tuple (7 members), not a grep. NIL
  further hits, including in `swing/trades/reconciliation_auto_correct.py`'s own "third of the four
  corrector paths" comment (`:2742`, production, unchanged) and this leg's own new (m8g) comment
  block, both re-read against the code and confirmed accurate.
- **`SS-3` -- totality claims with no discriminating row** (`every path`, `all call sites`, `no
  spelling survives`). Three candidate hits in `entry.py` (`:243` "every call site is a CLEANUP
  handler", `:962` "every path that can reach this gate", `:1022` "every path into that arm") --
  all three are pre-22-A4 (22-A3-era containment idiom, `086c1b6e`/`39104723`) design-rationale prose
  that is EXPLICITLY hedged against relying on the totality (`:962`'s own text: "it is rejected
  anyway, because the alternative is a gate whose safety depends on an exhaustiveness argument"), not
  a bare closure claim this leg's own residuals could have introduced -- routed nowhere, since none
  is false. This leg's OWN new totality claim ("deleting it still leaves every (m8f) row passing",
  `test_22a4_corrector_refusal.py:649`) was VERIFIED BY EXECUTION rather than left as prose: with
  `:2745` deleted, the full file reads 24 passed / 7 failed, and the 7 failures are exactly the seven
  parametrized (m8g) rows -- every (m8a)-(m8f) row still passes, confirming the claim precisely.
- **`SS-4` -- rule citations that disagree with the code beside them.** ONE hit:
  `A4X-R4-04` (fixed above). The other 19 `pre_version == (target - 1)` occurrences in
  `swing/data/db.py` (READ-counted via `grep -c`, matching the brief's own "the other 19" exactly)
  are explicitly out of scope per CHARC's ruling in the brief's §1 -- not touched. Every other
  `gotcha` citation in the four artifacts (`entry.py` gotcha #30/#31/#11 references,
  `test_migration_0038_attempt_identity.py:406`'s gotcha #11 equality claim) was spot-read against
  the code beside it and found consistent (the `#11` equality claim: `assert cols - fields ==
  {...}`, confirmed exact equality, not a superset form).

**Fixed inside the arc's own artifacts: all four §1 findings. Routed outside: `A4X-R4-03` (not in
this leg's brief; MINOR; round 4's own disposition stands). Nothing from the self-sweep required a
fix beyond the four already made.** No Codex round ran. Convergence state UNCHANGED: four counted
rounds, all `NEW_CRITICAL_MAJOR_FOUND`, loop stopped short.

### Gates

Four commits, `0df336c2..25af3b53`. All trailers empty (`git log 8990f81f..HEAD --format='%H%n
%(trailers)'`). Two files touched under `swing/trades/reconciliation_auto_correct.py` /
`swing/trades/entry.py` / `swing/data/db.py`: **ZERO** -- every change lands in
`tests/trades/test_22a4_corrector_refusal.py`, `tests/data/test_migration_0038_attempt_identity.py`
and `tests/trades/test_22a4_clause2_settlement.py`. No production behaviour change in this leg.

---

## REVIEWER B -- `codex-auto-review`, THE STANDING SECOND EYE. IT RAN, AND IT DID NOT RETURN CLEAN.

**Run by the ORCHESTRATOR, not by the author** (`harness-architecture.md` §5.1, operator-ruled
2026-08-11): B's entire value is a DIFFERENT perspective, which erodes when the author chooses its
prompt, its input set and the adjudication of its findings. Required on any production-code arc by
charter §2.9. **The precondition CHARC set on 2026-09-08 is met in all five of its parts** and each
part is measured below.

**Tree reviewed:** `84e90bab` (branch `22-a4-exec`), tree clean at review time.
**Date:** 2026-09-08.

### The invocation, and the hazard it caught live

The COLD-AUDIT form per recipe §3 -- `codex exec -p strong -s read-only --skip-git-repo-check -`,
cwd the worktree so Codex reads the repo itself. `codex exec review` is not usable from a worktree
on this box and there is no flag around it.

**The transport was PROBED at dispatch rather than inherited, and the probe caught a live failure:**
the harness expanded `$PATH` inside `wsl.exe bash -lc '...'` before WSL ever saw it, producing the
Windows PATH and a syntax error on an unquoted paren. This is the documented `$VAR`-expansion hazard
-- the one that once rewrote `echo $?` to `echo 0` and produced a green detector over a missing
transcript. Everything therefore ran from an LF-verified script file with LITERAL paths only,
non-PATH-initial invocation, relative redirect targets, and both output files pre-created
Windows-side. Runner preserved at `run_b_22a4.sh` beside the transcript.

Liveness proved by `codex-cli 0.152.1` resolving to `/home/rwsmythe/.local/node22/bin/codex` -- the
native binary, not the dead Windows npm shim.

### The five mechanical assertions -- ALL PASS, stated as measurements

| # | assertion | measured |
|---|---|---|
| 1 | banner model is the binding tier | `model: gpt-5.6-sol` -- the same model the A rounds carry |
| 2 | reasoning effort | `reasoning effort: high` |
| 3 | `grep -c '^ERROR'` | **0** (unanchored `grep -c 'ERROR'` reads **18** -- exactly the repo-prose false positive the anchor exists to defeat, on a cold audit that reads this repo) |
| 4 | `grep -c '^tokens used'` | **1** -- the file is complete, not mid-write |
| 5 | exactly one distinct anchored verdict token | `^NEW_CRITICAL_MAJOR_FOUND` = **2** (codex-cli 0.152.1 emits the final message twice), `^NO_NEW_CRITICAL_MAJOR` = **0** |

Belt-and-braces beyond the five: the process was confirmed EXITED before the transcript was read
(exit file polled, never the transcript -- a file that currently ends well can be mid-write), and the
redirect target was verified non-empty (1,832,058 bytes / 23,377 lines). Exit code was 0, which is
**not** evidence and is recorded only because both signals must agree.

**VERDICT: `NEW_CRITICAL_MAJOR_FOUND`.** B is not required to return clean; it is required to have
RUN on the merge tree. It ran, and it found something four counted A rounds did not.

### The contamination control, stated plainly

The recipe mandates repo read-access AND keeps `.copowers-findings.md` plus the `.codex-*`
transcripts at the worktree root -- which puts the review's own scratch inside the review's input.
All 13 A-loop files were RELOCATED out of the tree for the duration of B's pass and RESTORED
afterwards; nothing was deleted and the durable copies were never at risk. **Verified after the
fact:** B's transcript contains no read of any relocated file (the `.copowers-findings.md` string
appears only inside `CLAUDE.md` / `orchestrator-context.md` prose Codex read, FIVE times, never as a
path it opened).

The COMMITTED ledger (this file) stayed in the tree, because it merges. The prompt named it and
required B to say so explicitly if it restated a ledger finding. **B honoured that** -- it
distinguished its finding 1 from `A4X-R4-01` on the merits and its finding 4 from `A4-R7-12`,
naming both and saying why each is a different fact.

### CLAIMS FIRST -- B's first task, before any code-level lens

Nine of the arc's own top-level claims, measured end-to-end. **Six HOLD, three FAIL.**

| claim | B's result |
|---|---|
| 1 co-durability by construction | HOLDS -- one INSERT, no follow-up identity UPDATE |
| 2 unique per attempt by mechanism | HOLDS under the ruled definition -- one mint, no reissue path |
| 3 the probe sees only committed state | **FAILS in one required part** -- see finding 3 |
| 4 the settle identifies OUR attempt | FAILS only as an ABSOLUTE claim; this is declared limitation S7.7, and B challenged its reason and found it SOUND. Not a new finding. |
| 5 the apparatus cannot fail an entry | HOLDS |
| 6 the alarm still fires when it should | HOLDS -- bare `raise`, original object preserved |
| 7 the corrector refuses `attempt_id` on every operator surface | **FAILS** -- see finding 1 |
| 8 the envelope holds | HOLDS on non-git evidence |
| 9 the version-mirror family is complete | FAILS broadly; the 37->38 transition itself is CORRECT, and B confirms no deliberately-pinned 37 was moved. See finding 4. |

### The four findings, and the orchestrator's adjudication

**`B-1` -- MAJOR, `[INTRODUCED]`, IN ENVELOPE. `operator_alternative` does not refuse a trailing
`attempt_id`. CONFIRMED BY EXECUTION AT QA, BY MY OWN HANDS.**

`_handle_operator_alternative` passes the WHOLE operator payload to
`_handle_single_field_correction`, which selects `field_name = next(iter(correction_target.keys()))`
and passes **only that one key** to the guard inside `_update_journal_field`. The whole-payload
refusal `_preflight_reserved_transitions` is called from **exactly one** production site --
`_handle_multi_field_correction` -- measured by an AST walk over the call graph, not a grep:

```
_refuse_immutable_journal_fields called at :501  inside _preflight_reserved_transitions()
                                       :1829 inside _apply_tier3_override_inner()
                                       :2285 inside _update_journal_field()
_preflight_reserved_transitions  called at :2884 inside _handle_multi_field_correction()
```

So `("validator_rejected", "operator_alternative")` -- a real, routed production choice -- reaches
the guard with one field, and a second key is discarded before the guard ever sees it.

**I did not accept the read. I reproduced it**, on a `tmp_path` database built by the real migration
runner through 0038, through `apply_tier2_resolution`:

- payload `{"current_stop": 4.5, "attempt_id": <other token>}` -> **NO `ImmutableJournalFieldError`
  at all.** Returned `CorrectionResult(correction_id=1, field_name='current_stop',
  applied_value_json='{"current_stop": 4.5}')`, wrote `current_stop=4.5`, left the token untouched,
  and **terminalized the discrepancy as `operator_resolved_ambiguity`.**
- the SAME payload with the keys in the other order -> the guard fires correctly.

**The defect is key-order dependent, which is precisely the property (m8b) is named for.** (m8b)
exercises `choice_code="operator_truth"` -- the multi-field route, which does carry the whole-payload
preflight. No row in the roster puts a two-key payload through `operator_alternative`. The tests are
not wrong about what they assert; the roster has a hole where a fourth surface should be.

**This falsifies claim 7, and claim 7 is CHARC's attached condition -- the sole ground on which the
envelope was widened to include this module.** `authorize-then-abort` is not fully closed: on this
surface the operator's `attempt_id` is not refused, not applied, and not reported -- it is silently
dropped, which is a third outcome neither the condition nor the trigger anticipated.

*Remedy (NOT applied -- this is the gate's to rule):* apply `_refuse_immutable_journal_fields` to the
COMPLETE payload in `_handle_single_field_correction` before the `next(iter(...))` selection, with
discriminating rows in BOTH key orders on the `operator_alternative` route.

**`B-2` -- MAJOR, `[PRE-EXISTING]`, `[OUT-OF-ENVELOPE]`. `_handle_single_field_correction` silently
discards every payload field after the first.** The enabling condition for `B-1`, and wider than it:
`{"current_stop": 4.5, "state": "closed"}` applies the stop, ignores the state, audits only the
stop, and terminalizes the discrepancy. Both operator surfaces (CLI and web) accept arbitrary
mappings with no one-key restriction. B verified this by execution; my own `B-1` reproduction
exhibits the same mechanism. **This predates the arc and the arc does not worsen it** -- the
`next(iter(...))` selection is untouched by 22-A4. **Disposition: BANKED to the debt register, not
fixed here.** Fixing it is a corrector-semantics change (reject >1 key, or implement true
multi-field application) well outside a bounded typed-refusal condition.

**`B-3` -- MINOR, `[INTRODUCED]`, IN ENVELOPE. The probe's URI omits `cache=private`, and test (h)
cannot see the property it is named for.** `_durability_probe` opens
`Path(db_path).resolve().as_uri() + "?mode=rw"` (`entry.py:906`). The docstring argues the
construction-time precondition is "pinned by test (h)"; (h) asserts only
`PRAGMA read_uncommitted == 0` -- and its own failure message reads *"the probe connection is
shared-cache readable"*, a property that assertion does not measure. `read_uncommitted` only has
effect under shared cache, so a 0 reading is consistent with sharing one. B demonstrated the gap
against the SQLite C API directly. **This is an S7-invited hit on a STATED REASON, not a re-raise of
a declared limitation.**

**Measured reachability, so the severity is not a guess:** shared-cache mode is enabled NOWHERE in
this repository (`grep -rn "cache=shared|enable_shared_cache"` over `swing/`, `tests/`, `scripts/`:
zero enablers; the single textual hit is an unrelated OHLCV test's NAME). It requires a third party
to turn it on process-wide. MINOR stands. The remedy is one URI parameter -- `?mode=rw&cache=private`
-- turning an argument into a construction-time guarantee, plus tightening (h) or its message.

**`B-4` -- MINOR, `[PRE-EXISTING]`. Stale HEAD-version comments, failure messages and semantic names**
(`_is_21` asserting 38 while its message says 23; seven further files labelled 19-28). **The
executable 37->38 mirrors are CORRECT and B confirms no deliberately-pinned 37 was moved** -- this is
the naming layer only. **Disposition: ALREADY BANKED and OWNED** -- it is the version-mirror rename
rider in `docs/phase3e-todo.md`, whose trigger is explicitly AFTER this merge, under the CHARC ruling
of 2026-09-07 that naming and versioning are two changes and must not land in one commit. B
independently rediscovered a queued item; no action, and the rider's trigger is unchanged.

### What B changes about the arc's state

**Nothing merges on this section's authority.** `B-1` is a task-bearing MAJOR against production
code, in envelope, falsifying a claim a director attached as a condition. **It needs a fix leg and a
director disposition, and a fifth counted round -- if one is wanted -- needs the orchestrator's
fresh written authorization naming `B-1`; none is granted here.**

The instruments held, and they held in the direction the split was designed for: four counted A
rounds and a director ruling passed over this module, and the SECOND EYE found the third path's hole
because it did the one thing the roster never does -- hand `operator_alternative` a payload with two
keys. That is the 18-H.4 disjoint-finding-set pattern at N+1, and it is the reason B is run by
different hands.

### Transcript manifest -- Reviewer B

| artifact | bytes | durable path |
|---|---|---|
| `.reviewer-b-out.txt` | 1,832,058 | `~/swing-data/review-transcripts/22-a4-exec/` |
| `.reviewer-b-exit.txt` | 2 | same |
| `REVIEWER-B-prompt-22a4.md` | 11,331 | same |
| `run_b_22a4.sh` | 1,520 | same |

Copied the moment assertion 5 passed, per the copy-per-round rule -- not at report time, not at
teardown.


---

## CHARC'S RULING ON `B-1` -- **AUTHOR: CHARC. TRANSCRIBED BY THE ORCHESTRATOR AS COURIER ONLY.**

**This is a LITERAL BLOCK QUOTE**, built mechanically from the message file on disk
(`comms/orchestrator/read/20260908T172104Z-charc-charc-rules-b-1-fix-in-envelope-no-fifth.md`,
posted 2026-09-08T17:21:04Z, thread `22-a4-reviewer-b`, type `fyi`). It is not re-set and not
paraphrased. `comms/` is gitignored, so a ruling that lives only there decays in FINDABILITY with
every ack -- the ledger is the record, the mailbox was only the transport
(`orchestrator-context.md` posting rule 4, 2026-09-08).

**RD is CC on `B-1` and holds. `B-3` is RD's item and CHARC says nothing on it; that disposition is
still OUTSTANDING at the time of this transcription.**

**The ruling does NOT dispatch the fix leg.** CHARC names it "operator-directed dispatch" and states
the spend is the operator's to approve. Nothing is dispatched on this transcription.

> CHARC RULING on B-1 (the item that names my seat). RD is CC and holds on this item; B-3 is RD's and I say nothing on it. Fresh CHARC generation (first mail after bootstrap), 2026-09-08.
>
> == VERIFIED BEFORE RULING, METHOD STATED ==
> I did not rule off the report. On the worktree at c5991941 I read `_handle_single_field_correction` (reconciliation_auto_correct.py:2716) and ran an AST walk over every call to `_refuse_immutable_journal_fields`, naming the enclosing function of each site:
> - :501 inside `_preflight_reserved_transitions`, whose ONLY caller is `_handle_multi_field_correction` (:2884);
> - :1829 inside `_apply_tier3_override_inner` (tier 3);
> - :2285 inside `_update_journal_field`, over `(field_name,)` -- ONE key.
> The single-field handler selects `field_name = next(iter(correction_target.keys()))` at :2741, runs `_assert_real_column_names` over the WHOLE payload at :2754 (the R3-03 hoist), and never runs the immutable refusal over anything but the selected key. Finding confirmed by read; the orchestrator's key-order reproduction is consistent with it and I did not re-run it.
>
> == RULING 1: INTRODUCED, IN ENVELOPE, and the fix STAYS INSIDE the widening I authorized ==
> The condition that widened the envelope by exactly this module was: the corrector's typed refusal SHIPS on every operator surface (S8.6 not banked). B-1 is that condition unmet on one of the three operator-reachable paths. Completing the condition is not a new widening; it is the widening's own content. And the fix's shape already exists in the SAME FUNCTION for the OTHER gate: the R3-03 leg hoisted the byte-exact gate to whole-payload on this path and left the immutable gate at first-key. Two gates in one function deciding over two different populations is the defect; the fix makes them agree.
>
> PRESCRIBED SHAPE (bounded, so it cannot become B-2's fix):
> (a) In `_handle_single_field_correction`, call `_refuse_immutable_journal_fields(affected_table, correction_target.keys())` over the COMPLETE payload, immediately AFTER `_assert_real_column_names` (byte-exact first, per R3-03) and BEFORE the `next(iter(...))` selection. Same ordering as the two existing whole-payload sites.
> (b) Discriminating rows on the routed choice ("validator_rejected", "operator_alternative") through `apply_tier2_resolution`, in BOTH key orders: {current_stop, attempt_id} and {attempt_id, current_stop}. Each asserts the typed `ImmutableJournalFieldError` AND zero writes -- no correction row, `current_stop` unchanged, the token unchanged, the discrepancy NOT terminalized. The closure-test shape R3-03 used; a refusal test that checks only the exception would have passed over the persisted writes last time.
> (c) The trailing-key row must be shown RED against the pre-fix tree (it reproduces today, so this is a one-line witness, not an argument).
> (d) NOTHING ELSE on this function. In particular the fix must NOT reject >1 key or otherwise change what happens to a non-immutable extra key -- that is B-2, pre-existing, banked, out of envelope. A fix that closes B-1 by closing B-2 has widened the arc; refuse it at QA.
> (e) LOCK-A untouched by construction: the fix is in reconciliation_auto_correct.py, not entry.py. Re-measure anyway at the gate; I will.
>
> == RULING 2: NO FIFTH COUNTED A ROUND. B RE-RUNS ON THE POST-FIX TREE. (The spend is the operator's to approve; this is my recommendation.) ==
> Why no A round: round 4 stopped short and CLEARED PRODUCTION; it never converged, so there is no convergence to re-attach. The fix is one call in one function, mirroring a gate two lines above it, with its own both-orders closure test and the full fast suite. Buying a ~500K-token prose round to re-read a hoist the ladder has already reviewed twice is the treadmill section 5.1 names.
> Why B must re-run regardless: a clearance attaches to the tree the gate-holder verified, and anything touching code or tests re-opens the gate. The post-fix tree is not the tree B audited. B ran on 84e90bab; the merge tree will differ in code; B must have RUN on the tree being merged. Same form, same five assertions, same durable path, cold-audit from the worktree. It need not return clean; every finding dispositioned introduced-vs-banked. If the B re-run returns a NEW in-envelope introduced major, that is the moment to reconsider a counted A round -- not before.
>
> == B-2 (no ruling sought; register is mine) ==
> Banked. I will write the D-row when the operator directs file edits this generation; content as B stated it: silent discard of every payload field after the first on BOTH operator surfaces, pre-existing, the enabling condition of B-1 and wider than it. Its fix is corrector-semantics (one-key restriction or true multi-field), its own item, not this arc's.
>
> == SEQUENCE AS I NOW HOLD IT ==
> B-1 fix leg (cell, TDD per (a)-(e), operator-directed dispatch) -> full fast suite on the head -> B RE-RUN on that head -> the b3b518f9 trailer reword -> the operator's -n auto merged-head run -> merge request -> both director gates -> S9 step 0 -> the witnessed 0038 migration. RD's B-3 disposition (before merge or banked) slots into the fix leg if RD rules it in; that is RD's call and I do not pre-empt it.
>
> Register material accepted from the outgoing orchestrator's handoff: "a name survives a handoff more easily than the definition that governs it." Queued with the owed rows.
>
> -- CHARC

### The orchestrator's reading of what this binds

- The `B-1` fix is **IN ENVELOPE** -- completing the condition is the widening's own content, not a
  new widening. Shape prescribed in five parts (a)-(e), and **(d) is a REFUSAL I must enforce at QA**:
  a fix that closes `B-1` by closing `B-2` has widened the arc.
- **NO fifth counted A round.** Round 4 stopped short and cleared production, so there is no
  convergence to re-attach.
- **B RE-RUNS on the post-fix tree.** A clearance attaches to the tree its holder verified; the merge
  tree will differ in code from `84e90bab`, which is the tree B audited. Same form, same five
  assertions, same durable path. A NEW in-envelope introduced major from the re-run is the moment to
  reconsider a counted A round -- not before.
- **`B-2` banked** to CHARC's register, content as stated. **`B-4`** unchanged (the queued rename
  rider, trigger after merge).

---

## RD'S RULING ON `B-3` -- **AUTHOR: RD. TRANSCRIBED BY THE ORCHESTRATOR AS COURIER ONLY.**

**LITERAL BLOCK QUOTE**, built mechanically from the message file on disk
(`comms/orchestrator/read/20260908T172247Z-rd-rd-rules-b-3-cache-private-before-merge.md`, posted
2026-09-08T17:22:47Z, type `fyi`), front matter stripped and each line prefixed. Not re-set, not
paraphrased. Same treatment and same reason as CHARC's `B-1` ruling above.

**Both director items on Reviewer B are now RULED.** `B-1` -- CHARC, above. `B-3` -- RD, here. RD
concurs with `B-1` and says nothing on it; CHARC said nothing on `B-3`. One ruler per item, honoured
on both sides.

> RD RULING on B-3 (the item that names my seat; constraint 3 is mine). CHARC's B-1 ruling landed 17:21Z; I concur and say nothing on it. Fresh RD generation, 2026-09-08.
>
> == VERIFIED BEFORE RULING, METHOD STATED ==
> Read on the reviewed tree via `git show 84e90bab:` (never cd): `_durability_probe` opens `Path(...).as_uri() + "?mode=rw"` -- no cache parameter; its docstring says the construction-time precondition "is pinned by test (h)"; test (h) is headed "THE PROBE CONNECTION IS NOT SHARED-CACHE" and its only assertion is `PRAGMA read_uncommitted == 0` (tests/trades/test_22a4_attempt_identity.py:812-840). B's reading of all three is correct.
> Enabler absence: `git grep -iE "cache=shared|enable_shared_cache|SHAREDCACHE|cache=private"` over swing/ tests/ scripts/ = ZERO hits on 84e90bab AND on main. That is a token grep and bounds from below; it is corroborated by execution below, which is why the ruling does not rest on it.
> Executed on this box (Python 3.14.2 / SQLite 3.50.4, script in my scratchpad, deleted after): (1) `sqlite3.enable_shared_cache` DOES NOT EXIST on this runtime (removed in 3.12) -- from Python, shared cache is reachable only per-connection via `cache=shared`, so a C extension calling `sqlite3_enable_shared_cache` is the only path that could flip the probe's default; (2) `?mode=rw&cache=private` opens, reads, `read_uncommitted` = 0; (3) a `cache=shared` writer holding an uncommitted BEGIN IMMEDIATE insert is INVISIBLE to a `cache=private` reader on the same file (count 0). So the parameter delivers the property by mechanism, and it composes with the existing `mode=rw`.
>
> == RULING: FIX BEFORE MERGE, IN THE B-1 FIX LEG, MINOR SCOPE ==
> Reason 1 (the one that decides it): constraint 3 is the DURABLE-VISIBILITY READ of the evidence rule -- a fresh connection that sees only committed state. On the tree today that property holds by WRITER-ABSENCE ("nothing in this repo enables shared cache"), which is a claim with a shelf life, exactly the class I banked against myself on notes-writability: true today, rotting silently the moment a dependency or C extension flips the process default. `cache=private` converts it into a construction-time guarantee at the cost of nine characters. Admissibility machinery does not get to rest on writer-absence when a mechanism is one parameter away.
> Reason 2: the docstring and the test HEADER both assert a pin that the assertion does not measure. That is a stated reason in normative voice claiming coverage it lacks -- the version-mirror/`_is_head` class one rung down: the NAME of the test is a claim, and the claim is false. Banking it would merge a false pin carrying a reviewed-at certification (the partial-cleanup-launders class). The correction is cheaper than the register row.
> Severity: MINOR STANDS as B graded it -- reachability measured (item 1 above), and the direction is not a false success: the ruling does not depend on how the CURRENT code behaves under shared cache, because the fix removes the case; I make no claim about SQLITE_LOCKED-vs-read there and want none written.
>
> == PRESCRIBED SHAPE (bounded) ==
> (a) `_durability_probe`: URI becomes `... + "?mode=rw&cache=private"`. Nothing else in the function. LOCK-A: this touches `_durability_probe`, one of the three AST-locked functions -- so the lock's baseline moves by exactly this one string literal and the gate re-measures against the NEW segment hash, stated in the ledger with the old and new sha256 side by side. That is a deliberate, named lock move, not an untouched claim; CHARC re-measures at his gate, as he said he would, and so do I.
> (b) Test (h) is REWRITTEN, not appended: assert the URI passed to `open_connection` carries `cache=private` (spy the call, capture the URI string -- construction-time, the property the header names) and KEEP the `read_uncommitted == 0` scalar as a second, honestly-labelled assertion (what the pragma reads under a private cache). The test's header and name say what it now pins; the failure message stops claiming what it cannot measure.
> (c) The entry.py docstring paragraph "PRAGMA read_uncommitted IS NOT CHECKED AT RUNTIME..." is corrected by REPLACEMENT: the precondition is a construction-time URI parameter pinned by (h)'s URI assertion; the runtime-branch-is-dead-code argument stays because it is still true.
> (d) No counted A round on B-3's account (scope-of-change rule: one literal, one test, one docstring). It rides the B-1 fix leg and CHARC's sequence unchanged: fix leg -> full fast suite -> B re-run on the post-fix head -> trailer reword -> operator's -n auto -> merge request -> both gates. My merge gate's check (b) will read the locked functions against the new hash.
>
> Flagged, unverified, disposition pre-ruled: whether `open_connection` re-encodes or validates URIs in a way that rejects a second query parameter. The cell verifies at the code; if it does, that is a finding about `open_connection`, not a licence to drop the parameter -- route back.
>
> -- RD

### THE LOCK-A BASELINE MOVES -- recorded here because it is a NAMED lock move, not an untouched claim

RD's part (a) changes one string literal inside `_durability_probe`, which is one of the three
AST-locked functions. **The lock is not broken; its baseline moves by exactly this change, and the
gate re-measures against the NEW segment hash.** The OLD hash is recorded now, before the fix, so
the move is auditable in both directions:

| locked function | sha256 of AST source segment at `a32ea9d5` == `84e90bab` | after the `B-3` fix |
|---|---|---|
| `_entry_transaction` | `c53b2786e3a7518d5c1341af399eeac9d4d8e16cc615c28d093e631c56240d69` (10,990 chars) | MUST BE UNCHANGED |
| `_durability_probe` | `c16ea4656c1c2e415beb04f3a04f141719cfc60a793465eb5d9b4e70616c4914` (4,113 chars) | **MOVES -- new hash recorded at the fix, diff must be the URI literal and the docstring paragraph ONLY** |
| `record_entry` | `5b6aa7466175ff4c91448bf8dbb6f18f19b6a2974e12dfab20d2e1aa41710fb7` (25,939 chars) | MUST BE UNCHANGED |

Measured by the orchestrator at Reviewer B's QA, `a32ea9d5` -> `84e90bab`, all three IDENTICAL --
against a `git diff --stat` on `entry.py` reading 123 insertions, which is the trap that has already
caught one reader. **`a32ea9d5` is a MID-ARC commit** (the rounds 1-2 ledger), so "identical to
`a32ea9d5`" means unchanged since the lock was SET, not untouched by the arc.

### RD's flagged item, answered by the orchestrator BEFORE dispatch rather than at the cell

RD flagged, unverified: whether `open_connection` re-encodes or validates URIs in a way that would
reject a second query parameter, and pre-ruled the disposition -- if it does, that is a finding about
`open_connection`, not a licence to drop the parameter, and it routes back. **Verifying a brief's
premise before commissioning is this seat's own standing obligation** (the #38 pre-commission premise
check; the round-0 premise census), so it was checked here rather than carried into the dispatch as
an assumption.

**ANSWER: `open_connection` does NOT re-encode or validate the URI. The premise holds and the fix leg
is a one-leg dispatch.** Verified two ways. By READ: `swing/data/db.py::open_connection` passes
`db_path_or_uri` straight into `sqlite3.connect(db_path_or_uri, uri=uri, ...)` and then issues only
PRAGMAs -- there is no parsing, re-quoting or allowlist anywhere in the function. By EXECUTION,
through the real function on a real migrated database:
`open_connection(<file uri> + "?mode=rw&cache=private", uri=True)` opened, `PRAGMA read_uncommitted`
read 0, and `schema_version` and `trades` were both readable.

**AND THE CAVEAT, STATED RATHER THAN DROPPED, BECAUSE IT IS THE HALF THAT COULD MISLEAD:** the
negative control I ran alongside it -- a deliberately bogus `?mode=rw&nonsense=1` -- was **ACCEPTED**,
not rejected. So SQLite ignores unrecognised query parameters here, and **the successful open
therefore proves only that nothing REJECTS or MANGLES the parameter; it does NOT by itself prove the
parameter TOOK EFFECT.** What proves the mechanism is RD's own execution in his ruling above (a
`cache=shared` writer's uncommitted insert measured INVISIBLE to a `cache=private` reader on the same
file, count 0) -- his measurement, not this seat's, and cited as his. A non-discriminating control is
reported as non-discriminating; the alternative is a bounded check presented as a total, which is
this arc's most-repeated failure class.

---

## THE REVIEWER-B FIX LEG -- SHIPPED AND QA'd AGAINST DISK (orchestrator-authored)

**Branch `22-a4-exec`; the leg's two commits are `21d78e07` (`B-1`) and `03e6ecc3` (`B-3`).** Cell
`implementer-sonnet-high`, dispatched 2026-09-09 off the brief at `b10be35d`. Tree clean, `ruff check
swing/` clean, both commits' trailers `[]`, four files touched (two production, two test) and no
others.

**THE RED WAS VERIFIED BY THE ORCHESTRATOR, NOT ACCEPTED FROM THE CELL.** Method: a throwaway
detached worktree at the pre-fix commit `b10be35d`, the three new tests copied in, run against the
OLD production code, then torn down (`git worktree remove --force` de-registered it; the directory
needed a forced delete afterwards -- the usual Windows lock).

| test | pre-fix, measured here | post-fix |
|---|---|---|
| `..._refuses_trailing_attempt_id_with_zero_writes` | **FAILED** -- `DID NOT RAISE ImmutableJournalFieldError` | passes |
| `..._refuses_leading_attempt_id_with_zero_writes` | **PASSED** -- not a discriminator | passes |
| `test_h_the_probe_opens_with_cache_private_...` | **FAILED** on the `cache=private` assertion | passes |

The leading-key row passing pre-fix is not a defect: `_update_journal_field`'s single-key backstop
already caught `attempt_id` when it happened to be the selected key, which is the same fact that
makes `B-1` key-order dependent. It is an order-independence pin, not a second discriminator, and
**the cell disclosed this itself** rather than presenting two reds.

**BOTH REFUSALS HELD.** `B-2` is untouched -- `field_name = next(iter(correction_target.keys()))` is
preserved verbatim and merely relocated BELOW the new whole-payload guard, so a multi-key payload
still discards after the first key exactly as before. Of the three AST-locked functions only
`_durability_probe` moved.

**Full fast suite, run independently by the orchestrator on `03e6ecc3` (`-n 4`, from the worktree):
12,310 passed, 13 skipped, 0 failed, exit 0, 848.95s.** Identical to the cell's reported numbers.

### THE ACCUSATION I MADE AGAINST THE CELL, AND ITS WITHDRAWAL

In my QA packet to CHARC (`comms`, 2026-09-09T02:36:14Z) I wrote, of the cell's Lock-A report:

> ALSO FOR THE RECORD, because it bears on how much the cell's own numbers are worth: the cell
> reported "old hashes measured fresh on my own checkout before either edit and matched the ledger's
> recorded values exactly, confirming I was diffing from the right baseline." For record_entry that
> claim cannot be true as stated -- no revision produces that value. [...] it is a claim that did not
> survive checking, and it is the third instance this arc of a total asserted over a search that was
> not run.

**WITHDRAWN 2026-09-09, ON THE RECORD, BENEATH ITS OWN QUOTE. THE CELL'S REPORT WAS TRUE AND MY
INSTRUMENT WAS BROKEN.** CHARC re-measured before ruling and found the cause by execution: my script
captured the blob with `subprocess.run(..., text=True)` and **no `encoding=`**, so Python decoded it
as **cp1252**, the Windows default. `record_entry` contains 7 non-ASCII characters (verified here:
`SECTION-SIGN`, `MULTIPLICATION-SIGN`, `EM-DASH`, `RIGHTWARDS-ARROW`) which under cp1252 become 17
mojibake characters -- +10 chars, and the hash moves. **Re-measured by me with an explicit UTF-8
decode of the same blob: `record_entry` = `5b6aa746...` (25,939), MATCHING THE LEDGER; the same blob
decoded cp1252 reproduces my wrong `14e12dfd...` (25,949) exactly.** `_entry_transaction` and
`_durability_probe` are pure ASCII, which is why two of three rows agreed under a broken decoder and
the third never could.

**The class label survives, one seat over, against the seat that owns it -- mine.** My 54-revision
hunt reported an ABSENCE as a total when the bound was not the revision range at all but the
decoder: an instrument that could not have found the value at ANY revision. A bounded search
reported as a total, which is this arc's most-repeated failure. The seven "extraction variants" I
tried all sat downstream of the decode and so could not reach it.

**LOCK A at `03e6ecc3`, re-measured with the correct decode, and the METHOD recorded beside it so
the next re-measurement is a comparison rather than a rediscovery:**

> **METHOD (binding for this table):** `git show <rev>:swing/trades/entry.py` captured as **BYTES**,
> decoded as **UTF-8 explicitly**, `ast.parse`, `ast.get_source_segment` for the single `FunctionDef`
> of each name, sha256 over that segment's UTF-8 encoding. Never a file diff; never an implicit
> decode.

| function | at `a32ea9d5` .. `b10be35d` | at `03e6ecc3` (HEAD) | verdict |
|---|---|---|---|
| `_entry_transaction` | `c53b2786...` (10,990) | `c53b2786...` (10,990) | **UNCHANGED** |
| `record_entry` | `5b6aa746...` (25,939) | `5b6aa746...` (25,939) | **UNCHANGED** |
| `_durability_probe` | `c16ea465...` (4,113) | `028cd659...` (4,625) | **MOVED, DECLARED** -- RD's `B-3`: the URI literal + one docstring paragraph, and nothing else |

`a32ea9d5` is a MID-ARC commit, so "unchanged since `a32ea9d5`" proves unchanged **since the lock was
set**, not untouched by the arc. Both directors re-measure at their own gates.

---

## CHARC'S RULING ON THE TWO QA ITEMS (Lock-A row; the guard docstring) -- **AUTHOR: CHARC. TRANSCRIBED BY THE ORCHESTRATOR AS COURIER ONLY.**

**Source:** `comms/orchestrator/read/20260909T023853Z-charc-charc-rules-qa-items-lock-a-row-correct.md`,
thread `22-a4-reviewer-b`, posted 2026-09-09T02:38:53Z. **Reproduced below as a LITERAL BLOCK QUOTE,
built mechanically from the message file and verified byte-for-byte by containment** -- it is not a
re-setting, and CHARC is not being asked to verify a paraphrase.

> CHARC RULING on the two QA items (both name my seat; RD is CC and re-measures at his gate). Thread 22-a4-reviewer-b.
>
> =====================================================================
> ITEM 1 -- LOCK A: THE RECORDED `record_entry` ROW IS CORRECT. THE INSTRUMENT THAT COULD NOT REPRODUCE IT DECODED THE BLOB AS cp1252.
> =====================================================================
>
> I re-measured before ruling. Method, stated so it is a comparison next time: `git show <rev>:swing/trades/entry.py` captured as BYTES, decoded as UTF-8, `ast.parse`, `ast.get_source_segment` for the one FunctionDef of each name, sha256 over the segment's UTF-8 encoding.
>
> Result at a32ea9d5, 84e90bab, b10be35d and 03e6ecc3 (HEAD):
>   _entry_transaction  c53b2786 (10,990) at all four -- matches the ledger.
>   record_entry        5b6aa746 (25,939) at all four -- MATCHES THE LEDGER. The recorded row REPRODUCES.
>   _durability_probe   c16ea465 (4,113) at the first three; 028cd659 (4,625) at HEAD -- the declared move, and your HEAD number agrees with mine.
>
> Then the cause, by execution rather than guess: the same blob decoded as cp1252 (the Windows default whenever `subprocess.run(..., text=True)` carries no `encoding=`) gives record_entry = 14e12dfd (25,949) -- YOUR number exactly. `record_entry` contains 7 non-ASCII characters (the docstring's typographic dashes and quotes); under cp1252 they decode to 17 mojibake characters, +10 chars, and the hash moves. The other two functions are pure ASCII, so both decoders agree on them -- which is why your method "found recorded values when they exist" for two rows and never for the third. The seven extraction variants you tried all sat downstream of the decode, so none could reach it.
>
> RULING:
> (1) The row STANDS as recorded. Do NOT replace the value. What is added beside the table is the METHOD line above, so the next re-measurement is a comparison rather than a rediscovery -- your recommendation, adopted for the method column and refused for the value.
> (2) Record the new `_durability_probe` hash 028cd659 (4,625) beside the old, with the diff stated: the URI literal plus the one docstring paragraph. I read that diff at HEAD; it is exactly RD's (a) and (c) and nothing else.
> (3) THE CELL'S REPORT WAS TRUE. "Old hashes measured fresh on my own checkout before either edit matched the ledger's recorded values exactly" is a claim that survives checking under the correct decoder; it was your instrument, not the cell's search, that did not run. The sentence in your QA calling it "a claim that did not survive checking" and "the third instance this arc of a total asserted over a search that was not run" is withdrawn on the record, in the same ledger section, beneath the quoted accusation -- the form the harness uses for a falsified assessment (I did it myself on R3-03 two days ago). The class label still applies, one seat over: your 54-revision hunt returned an ABSENCE from a search whose instrument could not have found the value at any revision. A bounded search reporting a total, with the bound in the decoder rather than the revision range. Bank it that way, against the seat that owns it.
> (4) Gotcha family: this is the CLAUDE.md Windows cp1252 stdout entry met on the READ side (a decode instead of an encode). The orchestrator owns the gotcha text; my suggested trigger+fix: "any `subprocess.run(text=True)` or `open()` over repo content on this box without `encoding='utf-8'` decodes as cp1252 -- a hash, length, or diff over that text is a hash of the mojibake. Pass the encoding, or hash bytes." Your call whether it lands as an amendment to the existing entry or its own line.
> (5) Lock A at my gate: HOLDS at 03e6ecc3 by my own measurement -- two rows unmoved since a32ea9d5, the probe moved by the declared literal + paragraph. Your precision stands: a32ea9d5 is mid-arc, so this proves unchanged-since-the-lock-was-set, not untouched-by-the-arc.
>
> =====================================================================
> ITEM 2 -- THE GUARD DOCSTRING: IN ENVELOPE, AS COMPLETION OF THE FIX. THIRD COMMIT, SAME CELL.
> =====================================================================
>
> Read at HEAD :256-290. Two claims are false: "called from THREE sites" (four, by the AST walk we both ran) -- false BY THIS LEG; and "`_update_journal_field` ... is the only site in this module that writes an operator-supplied journal field, so a check here reaches every operator surface" -- false BEFORE this leg, and it is B-1 in prose: the backstop reaches every WRITE but only the one key already selected, so on a two-key payload it never saw the operator's second key.
>
> RULING: IN ENVELOPE. The leg added the fourth call to this predicate; the predicate's own contract text is part of that change, not a neighbouring function swept in. And the second sentence is the harness's discharged-deferral rule met in code: when an arc discharges a claim, correcting the note is PART of the fix, and leaving it is the partial cleanup that launders what it keeps -- the next reader deciding whether a fifth site is needed will read this docstring, find "reaches every operator surface", and stop. The brief's "no sweep" clause is not breached: one function, its own docstring, the two false claims, nothing else.
>
> PRESCRIBED SHAPE (bounded):
> (a) Replace "THREE sites" with FOUR and add the fourth bullet: `_handle_single_field_correction` -- ORDERING on the single-field path, over the WHOLE payload before the `next(iter(...))` selection, because the backstop sees only the selected key (B-1, 2026-09-08).
> (b) Replace the backstop bullet's reach sentence with what the backstop actually sees: it is the only site that WRITES an operator-supplied field, so it catches every write -- but it is handed ONE field, the one already selected, so it cannot see a payload's other keys; the three ORDERING sites exist because of that. Describe what the code does today; promise nothing about future surfaces (gotcha #31).
> (c) Supersession by replacement -- no "was three, now four" annotation, no change narrative in the docstring; the narrative is this ruling and the commit message.
> (d) No behaviour, no test, no other line. Third commit on 22-a4-exec, same cell, trailers [].
>
> =====================================================================
> SEQUENCE
> =====================================================================
> Item 2's commit lands -> your QA against disk -> B RE-RUN on THAT head (you were right to hold B for it: B reviews the tree I want reviewed, and a docstring that says three sites would have cost B a finding and us a disposition) -> the b3b518f9 trailer reword -> the operator's -n auto merged-head run -> merge request -> both gates -> S9 step 0 -> the witnessed 0038 migration. The merge request cites the method line from item 1 beside all three hashes.
>
> -- CHARC


---

## REVIEWER B -- THE RE-RUN ON THE POST-FIX HEAD `989d734f`. **NO NEW INTRODUCED MAJOR.**

Run by the orchestrator (not the author, not the cell) per CHARC's ruling that *"a clearance attaches
to the tree its holder verified."* **Same form, same prompt file, same five assertions as the first
pass** -- the prompt read from the DURABLE preserved copy
(`~/swing-data/review-transcripts/22-a4-exec/REVIEWER-B-prompt-22a4.md`), not from any session
scratchpad. Runner preserved beside it as `run_b2_22a4.sh` with its five WSL hazards commented.

**CONTAMINATION CONTROL, PERFORMED NOT ASSERTED:** all 15 of Reviewer A's scratch files **and B's own
first-pass transcript and exit file** were moved out of the worktree before the run, under a written
manifest, and all 15 restored after (`git status` clean, verified). B reading its own prior verdict
would have defeated the point of a second eye; the recipe's hazard is that the review's output
otherwise sits inside its input.

### THE FIVE MECHANICAL ASSERTIONS -- ALL PASSED, AS MEASUREMENTS

| # | assertion | measured |
|---|---|---|
| 0 | process EXITED before the transcript was read | exit code **0**, from `.reviewer-b2-exit.txt` |
| 1 | model | `model: gpt-5.6-sol` |
| 2 | effort | `reasoning effort: high` |
| 3 | anchored `^ERROR` | **0** (unanchored: **37** -- the repo-prose false positives the anchor exists to defeat) |
| 4 | anchored `^tokens used` footer | **1** -> **678,193** |
| 5 | verdict token | `^NEW_CRITICAL_MAJOR_FOUND` **2**, `^NO_NEW_CRITICAL_MAJOR` **0**; final line is the token alone |

Transcript **2,479,419 bytes**, preserved to
`~/swing-data/review-transcripts/22-a4-exec/.reviewer-b2-out.txt` the moment assertion 5 passed.

### THE VERDICT TOKEN SAYS `FOUND`. THE CONTENT SAYS **NOTHING NEW**. BOTH HALVES ARE THE RESULT.

B's own opening line: *"No new introduced CRITICAL or MAJOR defect emerged on the post-fix tree. One
already-ledgered, pre-existing MAJOR remains unresolved and out of envelope, so the required verdict
is still NEW_CRITICAL_MAJOR_FOUND."* The prompt mandates that token for **ANY** finding rated
CRITICAL or MAJOR *"including one tagged out-of-envelope or pre-existing"* -- so the token is
mechanically correct and is **not** a merge blocker on its own. **It is also not nothing: a real
pre-existing MAJOR stands unfixed at merge, by ruling, and the merge request says so in those
words.** Reading the token as a block would be wrong; reading it away would be worse.

**CHARC's no-fifth-round condition is therefore NOT triggered.** No new in-envelope introduced major
surfaced, so no fresh written round authorization was needed and none was written.

### THE THREE FINDINGS, AND WHY EACH IS ALREADY OWNED

1. **MAJOR -- `_handle_single_field_correction` silently discards every payload key after the first.**
   `[PRE-EXISTING]` `[OUT-OF-ENVELOPE]`. This is **`B-2`**, banked to CHARC's register at the first
   pass. B states it plainly: *"It remains unresolved because the B-1 fix was directed to preserve
   next(iter(...)) and avoid widening into general corrector semantics. The arc did not introduce
   or worsen it."* **The independent eye confirms the refusal held** -- the fix did not close `B-2`,
   which is exactly what CHARC ruled it must not do.
2. **MINOR -- noncanonical spellings (`ATTEMPT_ID`, `[attempt_id]`) are refused correctly but arrive
   as a CLI traceback or a web 500**, because `ReservedJournalFieldError` derives directly from
   `Exception` while the CLI handlers catch `ValueError`. `[PRE-EXISTING]` `[OUT-OF-ENVELOPE]`. This
   is the queued `ReservedJournalFieldError` bare-`Exception` item (D34's third instance), which B
   **independently rediscovered** without being pointed at it. No corruption risk; delivery only.
3. **MINOR -- HEAD-version semantic names and diagnostics stale** (ten `_is_19`..`_is_28` functions
   asserting 38). `[PRE-EXISTING]` `[IN-ENVELOPE]`. This is **`B-4`**, already the post-merge
   version-mirror rename rider. B adds the useful negative: **no stale 37->38 executable mirror and
   no incorrectly moved v37 fixture was found.**

### WHAT B VERIFIED THAT MATTERS MOST -- CLAIM 7, THE ONE ITS FIRST PASS FALSIFIED

> *"Claim 7 -- Corrector refuses attempt_id: **HOLDS** for canonical `attempt_id` on every mutating
> operator route. The immutable predicate is reached from the multi-field preflight, tier-3 head,
> single-field whole-payload preflight, and write backstop. The post-ledger `B-1` fix at
> `_handle_single_field_correction` closes the trailing-key hole."*

Claim 7 was CHARC's attached condition and the sole ground for the envelope widening; B's first pass
falsified it and B's second pass confirms it closed -- **by a different eye than the one that wrote
the fix.** Claim 3 likewise now reads `mode=rw&cache=private` and HOLDS (RD's `B-3`).

B also reached, unprompted, the same conclusion the orchestrator reached at QA about the new tests:
*"the leading-key B-1 row is explicitly a paired order-independence control, while the trailing-key
row is the discriminator."* Two independent readings agreeing that one of the two new rows is a
control and not a second discriminator.

The accepted limitations S7.1 / S7.2 / S7.7 / S7.8 / S7.11 were challenged and **survived**; B went
to the CPython 3.11.14 and 3.12.0 `_sqlite/connection.c` sources to check the deferred-rollback
premise rather than reasoning about it.

### THE BOUND ON THIS CLEARANCE, STATED BECAUSE IT IS NOT NOTHING

B ran with **no `pytest` and no `git`** in its environment (the latter by instruction -- a worktree's
`.git` pointer it cannot resolve). So: it could not re-run the suite, and its **claim 8 (envelope
holds) is explicitly qualified** -- *"HOLDS on the available non-git evidence [...] exact historical
byte identity cannot be independently proved without a baseline."* The byte-identity half is proved
instead by the orchestrator's AST source-segment measurement of Lock A, under the method line
recorded above, and by the suite the orchestrator ran: **12,310 passed / 13 skipped / 0 failed on
`989d734f`** (`-n 4`, from the worktree), matching the run on `03e6ecc3` and proving the docstring
commit inert rather than assuming it.

---

## THE `Tests:` TRAILER ON `b3b518f9` -- A RECORDED BLEMISH, NOT A REWRITE (orchestrator-authored, per CHARC's part-1 ruling)

**The defect:** `b3b518f9`'s final `-m` paragraph begins `Tests:`, which git parses as a TRAILER. It
is the only non-empty trailer on the arc.

**Measured, not assumed:** `git log --format='%h %(trailers:key=Co-Authored-By)' main..HEAD` returns
**ZERO** rows with a value. The streak audit filters on the KEY and is UNAFFECTED. The pollution is
visible only to a naive *"is `%(trailers)` non-empty"* check.

**Why it was NOT rewritten.** `b3b518f9` sits **30 commits below HEAD**. Every load-bearing SHA this
arc records -- `a32ea9d5`, `84e90bab`, `b10be35d`, `03e6ecc3`, `989d734f`, `7f4e4c11`, `e7c52344` --
is at-or-after it and would change. This ledger cites **49 distinct 8-hex tokens**, and CHARC's `B-1`
ruling and RD's `B-3` ruling -- both transcribed as LITERAL BLOCK QUOTES precisely so they could not
drift -- cite `84e90bab` and `a32ea9d5` INSIDE the quoted text. **A rewrite would falsify those
citations while leaving them reading true**, which is gotcha #31's shape applied to git.

**The rule this bought, which is the larger half:** a history rewrite is a **TIP-ONLY** operation.
Once a committed ledger, a brief or a block-quoted ruling cites a SHA, that SHA is a CITATION. Past
that point a trailer or message defect is RECORDED, not rewritten. **And the same reasoning
governs the MERGE ITSELF** -- see CHARC's part 1 (3) below: the standing "rebase onto main +
`merge --ff-only`" recipe would have rewritten all 34 branch SHAs, doing by procedure exactly what
the reword was refused for doing by hand. **The orchestrator flagged the reword and did NOT flag the
merge procedure; CHARC caught it.** That is the finding of this exchange and it belongs to this seat:
having identified the class, I applied it to the item in front of me and not to the standing
procedure one line away in the same document.

---

## CHARC'S RULING ON SECTION 6 + HIS NINE-CHECK MERGE GATE -- **AUTHOR: CHARC. TRANSCRIBED BY THE ORCHESTRATOR AS COURIER ONLY.**

**Source:** `comms/orchestrator/read/20260909T033942Z-charc-charc-rules-sec-6-no-rewrite-merge-no-ff.md`, thread `22-a4-merge`, posted 2026-09-09T03:39:42Z.
**Reproduced below as a LITERAL BLOCK QUOTE, built mechanically from the message file and verified
byte-for-byte by containment.** Eight of nine checks PASS on his own measurement; check (6), the
merged-head `-n auto` run, is OWED and is the OPERATOR'S, on the MERGE COMMIT.

> CHARC on the 22-A4 merge request (e7c52344). Two parts: the section-6 ruling (names my seat), then my merge gate, eight of nine checks measured by me now, one owed to the operator's run. RD is CC on part 1 and rules his own gate.
>
> =====================================================================
> PART 1 -- RULING ON SECTION 6: DO NOT REWRITE b3b518f9. AND THE SAME REASON GOVERNS THE MERGE: MERGE COMMIT, NOT REBASE.
> =====================================================================
>
> (1) The `Tests:` trailer stays. The audit that matters filters on the `Co-Authored-By` KEY and I ran it myself: zero on main..HEAD. The blemish is a verbose final -m paragraph parsed as a trailer, visible only to a naive "is %(trailers) non-empty" check. Recorded in the ledger as a known blemish with the reason; my own gate check (7) is amended to "Co-Authored-By key count zero; the one `Tests:` trailer recorded".
>
> (2) The reason, stated as a rule you own the text for (recipe section 2, your file): a history rewrite is a TIP-ONLY operation. The moment a committed ledger, a brief or a block-quoted ruling cites a SHA, that SHA is a citation, and rewriting it falsifies the citation while leaving it reading true -- gotcha #31's shape applied to git. 49 tokens and two literal-block-quoted rulings cite descendants of b3b518f9. Not on the day of a money-bearing merge, not on any day.
>
> (3) THE CONSEQUENCE YOU DID NOT ASK ABOUT, AND IT IS THE LARGER ONE: the standing recipe merges by "rebase onto main + merge --ff-only" (recipe line 23; orchestrator-context :267). A rebase rewrites ALL 34 branch SHAs -- every one of the same citations, by a different door. I checked the geometry: merge-base 2d9e4a34; the branch is 34 ahead, main is 23 ahead. RULING FOR THIS MERGE: `git merge --no-ff 22-a4-exec` into main -- a merge commit that preserves every branch SHA, the form `0fac27ff` already used for this arc's plan merge. NEVER a rebase, NEVER a squash. The operator's `-n auto` run then runs on the MERGE COMMIT, which is the tree that ships.
>
> (4) Composition read for that merge, because a merge commit is the one place a composition defect can be caught (section 5.1): main's 23 commits touch NO `swing/` file and no test of the arc's surfaces -- CLAUDE.md, `scripts/start_directors.ps1` + its own test (the launcher named-window fix, c46c134f), and docs. Disjoint by read; the operator's merged-head suite is the instrument that confirms it.
>
> (5) Recipe text, yours to land with the arc's housekeeping (harness content routes through me; this is my ruling on its substance): "rebase + ff-only is the DEFAULT for a branch whose SHAs nothing cites. Once a committed ledger, brief or ruling cites branch SHAs, the branch merges with --no-ff and is never rebased or squashed; a trailer or message defect past the tip is recorded, not rewritten." Mirror it in orchestrator-context :267.
>
> =====================================================================
> PART 2 -- MY MERGE GATE, NINE CHECKS
> =====================================================================
>
> (1) Evidence by durable path -- PASS. ~/swing-data/review-transcripts/22-a4-exec/ holds A r1-r4 (prompt, review, exit), the ledger, B pass 1 (.reviewer-b-out/-exit + prompt + runner), B pass 2 (.reviewer-b2-out/-exit + run_b2). Listed with -a; every Codex artifact is a dotfile and a bare ls shows almost none of them.
>
> (2) B on THE TREE BEING MERGED, five assertions + verdict form -- PASS. Measured on .reviewer-b2-out.txt myself: exit 0; 2,479,419 bytes; `^ERROR` = 0; `^tokens used` = 1; `^NEW_CRITICAL_MAJOR_FOUND` = 2 with the file's last line the bare token; `^NO_NEW_CRITICAL_MAJOR` = 0; model gpt-5.6-sol; effort high. Tree identity: B has no git so the transcript cannot name 989d734f; identity is carried by run_b2_22a4.sh (cd into the worktree, header names 989d734f) AND by content -- the transcript discusses `cache=private` and `_handle_single_field_correction` 35 times each and the FOUR-sites docstring 5 times, none of which exist below 989d734f. e7c52344 over 989d734f is the ledger file only (git diff --stat: 1 file, 93 insertions) -- docs-only, verified, no re-clearance needed. The verdict token is mandated by the prompt for ANY major including banked ones; the content says no new introduced major, and both are read together, as you wrote.
>
> (3) LOCK A -- PASS, my own measurement at a32ea9d5 vs e7c52344 under the recorded method (bytes, explicit UTF-8, ast.get_source_segment, sha256): _entry_transaction c53b2786 (10,990) unchanged; record_entry 5b6aa746 (25,939) unchanged; _durability_probe c16ea465 (4,113) -> 028cd659 (4,625), the declared move, and I read that diff at HEAD: the URI literal plus one docstring paragraph, nothing else.
>
> (4) S8.6 typed refusal -- PASS. `class ImmutableJournalFieldError(ValueError)` at reconciliation_auto_correct.py:117; the fourth call site at :2768 closes the surface B-1 named.
>
> (5) Schema-prevented dismissals cite their constraint -- PASS VACUOUSLY, search stated: over the executing sections of the ledger (line 2058 on) for prevented|forbid|constraint-prevented|the CHECK|trigger refuses|NOT A FINDING -- two hits, neither a dismissal. No finding in this arc was dismissed on a schema-prevented ground.
>
> (6) Merged-head suite at 16 workers, READ BY ME -- OWED. The operator runs -n auto on the MERGE COMMIT (part 1 (3)); I read the result line myself before clearing. The two -n 4 runs (12,310/13/0 on 03e6ecc3 and on 989d734f) are the cell-seat evidence, not the gate.
>
> (7) Trailers -- PASS as amended: Co-Authored-By key count 0 on main..HEAD; exactly one non-empty trailer of another key (b3b518f9 `Tests:`), ruled a recorded blemish in part 1.
>
> (8) Ledger names every round + B -- PASS: Round 1-4 sections, B pass 1 (:2662), B re-run (:3120), transcript manifests.
>
> (9) Live DB v37 pre-merge -- PASS, read-only query by me just now: schema_version 37, `trades.attempt_id` ABSENT. 0038 unapplied. Re-verify again immediately before the witnessed migration; the witness is step-by-step, one step per operator result.
>
> CLEARANCE: CONDITIONAL on (6). When the operator's -n auto run on the merge commit is green and I have read its result line, my gate is CLEAR. Order after that: RD's gate -> S9 step 0 (blocking live pipeline run; D43 binds -- enumerate the copy's write surfaces first) -> the witnessed 0038 migration, step by step.
>
> Spend noted for the register: 3.28M review tokens against ~250K implementation on this arc. The sonnet-high cell needed zero rework across two dispatches; the one correction ran the other way. That is the datum the notch experiment was after.
>
> -- CHARC

---

## RD'S MERGE GATE -- **PASS, SEVEN OF SEVEN** -- **AUTHOR: RD. TRANSCRIBED BY THE ORCHESTRATOR AS COURIER ONLY.**

**Source:** `comms/orchestrator/read/20260909T035331Z-rd-rd-gate-22-a4-pass-on-tree-fd69bc22-fae5.md`, thread `22-a4-merge`, posted 2026-09-09T03:53:31Z.
**Reproduced below as a LITERAL BLOCK QUOTE, built mechanically from the message file and verified
byte-for-byte by containment.**

**BOTH DIRECTOR GATES ARE NOW IN.** CHARC: eight of nine, clearance conditional on his check (6), the
operator's `-n auto` run on the MERGE COMMIT, whose result line he reads himself. RD: seven of seven,
clearance attached to tree `fd69bc22f661` (`fae5c181`), with a post-merge re-verification he owes
before the migration step.

**Three things in RD's gate that this seat did NOT supply and should be read as independent:**

1. **He sharpened an inherited check rather than passing it.** The old (a) said "zero lines outside
   `0038` + `db.py`," which **under-specified the carve-out** -- the primitive's writer and reader
   necessarily live in `repos/trades.py`. He read every hunk of that file instead of failing it on a
   wording that was wrong, and states the arc's true production footprint: **exactly five files.**
2. **He re-derived the cp1252 error independently.** *"the cp1252 decode reproduces the orchestrator's
   earlier wrong value (14e12dfd / 25,949) -- measured by me before CHARC's ruling landed, same
   finding, not posted then because his ruling arrived first."* Two directors reached the same
   diagnosis of this seat's broken instrument by separate routes.
3. **He EXECUTED rather than read** where execution was available: 71 tests through the branch's OWN
   package (`PYTHONPATH=.` from the worktree, `swing.__file__` resolved and `EXPECTED_SCHEMA_VERSION`
   read 38 -- the editable-install-resolves-main gotcha checked, not assumed), covering the seven
   noncanonical spellings in both key orders and test `(h)` in its rewritten form.

**And he declines the suite claim explicitly:** *"THE SUITE CLAIM IS NOT MINE [...] I do not carry the
two `-n 4` figures forward as the merged-head result."* The binding green remains the operator's
`-n auto` run on the merge commit, and nobody in this arc has claimed otherwise.

> RD MERGE GATE -- 22-A4 (attempt-identity primitive). Seven checks, each run by me on the branch, method stated. Thread 22-a4-merge. CHARC's section-6 ruling (no rewrite; --no-ff) read and concurred; nothing said on it.
>
> TREE VERIFIED: branch `22-a4-exec` @ `fae5c181`, tree `fd69bc22f661`. The production/test/script content is identical to `e7c52344` (tree `8a59823fb6bf`): `git diff --stat e7c52344 22-a4-exec -- swing/ tests/ scripts/ pyproject.toml swing.config.toml` is EMPTY; the only file in that range is the ledger (+81). Docs-only landing, verified not assumed.
>
> (a) MEASUREMENT DIRS -- PASS, with the inherited wording SHARPENED. `git diff main...22-a4-exec -- swing/evaluation swing/recommendations swing/pipeline` = ZERO lines (the measurement chain is untouched). `swing/data` delta = three files: `migrations/0038_trade_attempt_identity.sql` (+121); `db.py` (`EXPECTED_SCHEMA_VERSION` 37->38, the A4 pre-migration backup gate + its hook in `run_migrations`, nothing else -- skeleton read by hunk); `repos/trades.py` (+234/-2). The inherited check said "zero lines outside 0038 + db.py"; that under-specified the carve-out, because the primitive's writer and reader necessarily live in the repo module. I READ every hunk of `repos/trades.py`: new imports, `_log_contained`, `ATTEMPT_ID_LENGTH` + `validate_attempt_id`, an `attempt_id` keyword on `insert_trade_with_event` validated before any write, a schema-aware INSERT branch that is the existing v27 branch plus the one column (the existing branch demoted `if`->`elif`; the two deleted lines are that keyword and a comment), and `find_trade_id_by_attempt_id`. NO existing read path, `_row_to_*` mapper, or cohort reader is touched. Production files changed on the whole arc: exactly five (`db.py`, `0038`, `repos/trades.py`, `trades/entry.py`, `trades/reconciliation_auto_correct.py`).
>
> (b) LOCK A -- PASS. Method: `git show <rev>:swing/trades/entry.py` as bytes -> UTF-8 -> ast.parse -> get_source_segment -> sha256. At a32ea9d5 / 84e90bab / e7c52344: `_entry_transaction` c53b2786 (10,990) x3; `record_entry` 5b6aa746 (25,939) x3; `_durability_probe` c16ea465 (4,113) -> (4,113) -> 028cd659 (4,625). The probe's non-docstring diff 84e90bab->HEAD is ONE line: `"?mode=rw"` -> `"?mode=rw&cache=private"` (my B-3 (a)); the rest is the docstring paragraph (my (c)). `with conn:` at :1849 has a body of exactly one `Expr(Yield)`. Independently corroborates CHARC's (3) and the orchestrator's table; the cp1252 decode reproduces the orchestrator's earlier wrong value (14e12dfd / 25,949) -- measured by me before CHARC's ruling landed, same finding, not posted then because his ruling arrived first.
>
> (c) THE SETTLE ENVELOPE -- PASS. `_settle_by_attempt_identity` is UNCHANGED since 84e90bab (58b594a1 / 9,418 at both), so this reads the text the fork ruling was written against. Capture-then-return: `proven = found; return proven` inside the try; the handler's proven arm logs a contained note and RETURNS THE PROOF (a TRUE success); the no-proof arm says only what it can distinguish (R3-01's wording: "either the read/gate yielded none, or a fault arrived before the proof was captured"). `except` scope UNCHANGED: the try body at 4589c2f9~1 vs HEAD is the same statement sequence plus the one capture Assign; the handler type is `BaseException` at both -- which exception escapes did not change. Window 2 is DECLARED above `_entry_transaction` as member (B) of the alarm family, bounded by ENDPOINTS ("from the settle's return THROUGH `return degraded`"), the composition stated ONCE for the family (alarm x operator retry x position closed between attempts; the ticker-closed direction named uncovered), weakest-sufficient bound with no independence assumed and no strictness claimed. As ruled.
>
> (d) TIER-3 ZERO-WRITE, SEVEN SPELLINGS -- PASS, by read AND by execution. `_normalize_journal_field_name` (the `74cb2815` normalizer) has ZERO hits in `swing/` at HEAD (the 8 hits for a wider pattern are the pre-existing 22-A `ENVELOPE_CANONICALIZER_VERSION`, a different concept). `_NON_CANONICAL_SPELLINGS` carries the seven (upper-case, mixed-case, bracket-quoted, double-quoted, single-quoted, parenthesised, leading-comment); (m8f) drives each through the tier-3 composition surface under a caller-held `BEGIN IMMEDIATE` and asserts: typed `ReservedJournalFieldError` that is NOT `ImmutableJournalFieldError` (byte-exact FIRST), zero `INSERT INTO reconciliation_corrections`, zero `UPDATE reconciliation_corrections`, zero journal UPDATE, the seeded chain head's `superseded_by_correction_id` unchanged, `current_stop`/`attempt_id` on the trade unchanged; a second parametrized row puts the ordinary field FIRST and the spelling LAST (the JSON-key-order property). EXECUTED BY ME against the BRANCH'S OWN package (`PYTHONPATH=.` from the worktree; `swing.__file__` resolved to the worktree and `EXPECTED_SCHEMA_VERSION` read 38 -- the editable-install-resolves-main gotcha checked, not assumed): `tests/trades/test_22a4_corrector_refusal.py` + `test_22a4_attempt_identity.py` -> 71 passed, 0 failed, `-n 0`. That run includes test (h) in its rewritten form (my B-3 (b)).
>
> (e) THE (id, ticker) CONTRACT -- PASS. `find_trade_id_by_attempt_id(...) -> tuple[int, str] | None`, `SELECT id, ticker FROM trades WHERE attempt_id = ?`, keyed on the TOKEN (never the rowid), schema-aware (answers None below v38). The settle UNPACKS `settled_id, settled_ticker = found`, compares the ticker to `req.ticker`, and on mismatch ALARMS (contained note, returns None -- "a mismatch may raise the alarm; only a match may be asserted from"); only a match becomes `proven`. Condition 4 met.
>
> (f) TRAILERS -- PASS. `git log --format='%(trailers:key=Co-Authored-By,valueonly)' main..22-a4-exec` -> 0 lines. Exactly one non-empty trailer block on the branch, `b3b518f9` `Tests:`, ruled a recorded blemish by CHARC; concurred.
>
> (g) LIVE DB -- PASS, read-only query by me just now: `schema_version` = 37; `trades.attempt_id` ABSENT; 0038 UNAPPLIED. 28 trades; open = 23 CADL / 24 RHI / 25 OII / 26 NRIX / 28 PBF. The named-pending rows are UNTOUCHED: 19 FTRE Broad-watch/11852/standard; 24 RHI Broad-watch/12518/standard; 25 OII NULL/NULL/standard; 28 PBF NULL/NULL/by_design -- exactly the September-read state. Re-verify immediately before the witnessed migration regardless.
>
> MY B-3 PRESCRIPTION (a)-(c): all three verified at HEAD -- the literal, test (h) rewritten to assert the URI parameter (executed, passes), the docstring paragraph replaced.
>
> CLEARANCE: PASS, attached to tree `fd69bc22f661` (`fae5c181`), swing/tests/scripts content identical to `8a59823fb6bf` (`e7c52344`). The three merge-blocking items -- (b), (d), (e) -- hold. POST-MERGE RE-VERIFICATION, owed by me before the migration step: on the `--no-ff` merge commit M, (1) `git diff 22-a4-exec M -- swing/` EMPTY, and (2) for every file the branch changed (`git diff --name-only 2d9e4a34 22-a4-exec`), the blob at M equals the blob at `22-a4-exec` -- i.e. main's own commits (docs, the launcher script and its test) reach M untouched and the arc's files reach M byte-identical. Any code/test landing between this clearance and M re-opens it; docs-only, grepped as above, does not.
>
> THE SUITE CLAIM IS NOT MINE: the operator's `-n auto` run on the merge commit is CHARC's check (6) and the binding green; my gate is the measurement-integrity read plus the 71-test execution above, and I do not carry the two `-n 4` figures forward as the merged-head result.
>
> -- RD

---

## CHARC'S RULING ON THE POST-MERGE SEQUENCE -- **RUN 171 IS STEP 0** -- **AUTHOR: CHARC. TRANSCRIBED BY THE ORCHESTRATOR AS COURIER ONLY.**

**Source:** `comms/orchestrator/read/20260909T065411Z-charc-charc-rules-order-run-171-is-step-0-suit.md`, thread `22-a4-merge`, posted 2026-09-09T06:54:11Z.
**LITERAL BLOCK QUOTE, built mechanically from the message file and verified by containment.**

**Why this ruling exists:** the merge set `EXPECTED_SCHEMA_VERSION = 38` while the live DB is 37, and
`connect()` refuses a mismatch -- so the sequence five seats had been reciting (*a BLOCKING live
pipeline run, THEN the witnessed migration*) became unrunnable the moment the merge landed. The
orchestrator caught it AFTER the merge, having run the merge's composition read on FILE SETS and
treated their disjointness as sufficient. **CHARC's answer did not require running anything: the
baseline step 0 wanted already existed** as pipeline run 171, executed by the real scheduled task on
pre-merge code against the live v37 DB about three hours before the merge.

**The general rule this bought, now recorded in `docs/phase22-arc-a-executing-resume.md` by
replacement:** *a step that OPENS THE LIVE DB is unrunnable between a schema-bumping merge and its
migration -- so the baseline is the last PRE-MERGE run, and the live verification is POST-migration by
construction.* CLAUDE.md already said the guard refuses a pre-merge schema; **it said it about
COMPARISONS, and five seats recited a sequence the same guard forbids.** The merge-time composition
read checks FILES; this was the RUNTIME composition of code with the live schema, a question the rung
did not have on its list and now does.

> CHARC RULING on the post-merge sequence (names my seat). RD is CC; nothing here disturbs his 82d20042 clearance. Thread 22-a4-merge.
>
> == THE FACT THAT DECIDES IT, MEASURED BEFORE RULING ==
> Step 0's purpose was a BASELINE: prove the pipeline healthy on the live DB before the DB is touched. That baseline ALREADY EXISTS and nobody has to run anything to get it. Read-only from the live DB just now:
>
>   run 171  started 2026-09-08T17:30:04  finished 17:48:42 (HST)  state=complete  data_asof=2026-09-08  export_status=failed  warnings: evaluate_warm degraded, 6 tickers re-fetched serially
>
> The merge commit is 2026-09-09T06:36Z = 2026-09-08 20:36 HST. Run 171 ran ~3 hours BEFORE it, from the scheduled task (`SwingWeeknightPipeline`, LastRunTime 9/8 5:30 PM, LastTaskResult 0), on pre-merge main whose guard expects 37, against the live v37 DB. That is step 0, executed by the real task in the real environment, with better provenance than any hand-run from a checkout could have. Its two blemishes are both PRE-EXISTING and both already on the register: `export_status=failed` is D42 (every run since 160, 2026-08-21, the exports ACL failure) and the warm-degraded warning is the recurring shape (runs 168-171 all carry it, fallback_count 6-8). Neither is a step-0 blocker, and NEITHER may be read as a migration effect afterwards -- that is what the baseline is for.
>
> == RULING: (A), WITH THE BASELINE NAMED. (B) AND (C) REFUSED. ==
> ORDER:
>   1. The operator's -n auto run on 82d20042 -> I read the line -> my clearance completes. (Unaffected by the DB, as you said: tmp_path databases only.)
>   2. THE WITNESSED 0038 MIGRATION, step by step, one step per operator result, with the v37 / attempt_id-ABSENT re-read immediately before it. Backup facts the witness names: `_create_pre_phase22_arc_a4_migration_backup` writes `swing-pre-22a4-migration-<ISO>.db` (~1.4 GB, SQLite-native backup) into the DB's parent dir -- the swing-data ROOT, the D32 pattern (two swing-pre-22a-* images of 1.39 GB each already sit there from 09-02); the standard db-migrate gate may write a second. 77 GB free on C:. Move-then-retain, never delete, as D32 rules. The migration is ADDITIVE (one ADD COLUMN, one partial UNIQUE index, one BEFORE UPDATE trigger, no rebuild, no backfill) and the pre-image is the ordinary way back -- so "touch the DB before the live run" is not a one-way door.
>   3. A BLOCKING, OPERATOR-WITNESSED LIVE PIPELINE RUN on the shipping code against the migrated DB, in daylight, BEFORE 17:30 HST. Its comparison is run 171: state complete; the same warm-degraded warning shape is expected; `export_status=failed` is EXPECTED (D42, unchanged by this arc). Any failure NOT in run 171 is the arc's or the migration's, and blocks. D43's copy-run enumeration does NOT apply -- this is a live run, no copy; its writes are the production writes.
>   4. The scheduled task then runs as normal at 17:30 as the unattended second confirmation.
>
> (B) REFUSED: it proves code that does not ship, and run 171 already supplies the pre-merge baseline with strictly better provenance. It would also need PYTHONPATH=. to run the checkout's package at all (the editable install resolves main), which is one more way to prove nothing.
> (C) REFUSED: three seats measured the merge sound; re-cutting it re-opens both clearances to answer an ordering question the baseline already answers.
>
> == THE CLOCK (operator's call, my recommendation) ==
> If step 3 cannot complete before ~16:30 HST today, DISABLE `SwingWeeknightPipeline` for tonight rather than let it fire. A guard-killed run does not write a `pipeline_runs` row (`connect` raises at runner.py:768, before the lease) -- it would be a SILENT miss, the 09-04 shape again, read by tool_health as staleness with no cause attached. An explicit disable is a recorded decision; a silent miss is a mystery for the next reader.
>
> == FOR THE RECORD ==
> - The sequence text at docs/phase22-arc-a-executing-resume.md:131 is falsified by the merge; orchestrator corrects it by replacement with this order (his doc). The general line is one I owe the harness text: A STEP THAT OPENS THE LIVE DB IS UNRUNNABLE BETWEEN A SCHEMA-BUMPING MERGE AND ITS MIGRATION -- so the baseline is the last pre-merge run, and the live verification is post-migration by construction. CLAUDE.md already says the guard refuses; it says it about comparisons, and five seats recited a sequence that the guard forbids. The composition read at merge checks FILES; this is the RUNTIME composition of code with the live schema, and the rung did not have that question on its list. It does now.
> - Orchestrator: your self-report is accurate and the check you ran (file-set disjointness) was the right check with a stated bound; the miss was a question absent from the rung, not a search run short. Recorded as the rung's gap, not this seat's.
>
> -- CHARC
