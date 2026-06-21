# D20 writing-plans — Codex review-fast findings transcript

Plan: docs/plans/schwab-txn-id-numeric-constraint-plan.md
Tier: review-fast (profile absent -> -p omitted, -c model_reasoning_effort=high)
Convergence target: NO_NEW_CRITICAL_MAJOR

## Round 1

### Codex response (verbatim)

**MAJOR**

- `docs/plans/schwab-txn-id-numeric-constraint-plan.md`, Task 1: the instruction that
  `re.match(r"^[0-9]+$", value)` is equivalent to a full-string numeric check is false in
  Python. `$` matches before a final newline, so `"123\n"` passes with `match`. That weakens
  the stated `^[0-9]+$` construction barrier. Use `_TXN_ID_RE.fullmatch(self.transaction_id)`
  or `\A[0-9]+\Z`, and add `"123\n"` as a raise case so the test distinguishes this bug.

**MINOR**

- The §2 helper-caller sweep claims every `schwab_txs` caller is enumerated, but it omits
  `tests/trades/test_schwab_equity_coherence.py:89`, which passes explicit numeric id
  `"900099"`. This will not raise post-fix and needs no edit, but the binding enumeration is
  not literally complete.

- §2.D lists only two unaffected local mirror dataclasses. There is another local `_Txn`
  mirror in `tests/cli/test_oof_buy_command.py:438`. It currently uses numeric
  `"115520131470"` and will not raise, but if §2.D is meant to prevent "fixing" mirror
  classes, the list is incomplete.

**NIT**

- Task 4 says to append a "one-line note" but the example is three comment lines. Harmless,
  but tighten the wording so the executor does not over-optimize for one physical line.

(Closing summary: no missing post-fix-raising SchwabTransactionResponse construction or
helper caller found beyond the plan's non-numeric sites; the listed coupled ref/assertion
edits are otherwise correct; the listed raise-test arithmetic is sound for the named cases.)

Verdict line: (no NO_NEW_CRITICAL_MAJOR — one MAJOR raised)

### Adjudication (mine)

- MAJOR (re.match vs fullmatch / trailing-newline) — ACCEPTED, valid and load-bearing.
  Verified independently in Codex's own exec: re.match(r"^[0-9]+$", "123\n") -> match span
  (0,3) (TRUE); fullmatch -> None. A "123\n" id would slip the barrier under .match. FIXED:
  Task 1 now compiles r"[0-9]+" and uses .fullmatch; the message still prints ^[0-9]+$;
  "123\n" added as a RAISE case in Task 1's parametrization; the arithmetic section now
  reasons the newline case both pre-fix (accepted today) and as the match-vs-fullmatch
  discriminator. This is a real plan defect the review caught.
- MINOR (equity_coherence:89 omitted) — ACCEPTED for completeness. Added §2.B row #14 +
  an enumeration-completeness note (numeric, no edit). The original §2.B already excluded it
  correctly by the "only non-numeric callers need conversion" rule, but the binding
  enumeration should be literally complete; now it is.
- MINOR (third _Txn mirror in test_cli/test_oof_buy_command.py:438) — ACCEPTED. Verified on
  disk: local `_Txn` dataclass at :438, numeric "115520131470" at :467. Added to §2.D so the
  executor does not "fix" it.
- NIT (Task 4 one-line vs three-line) — ACCEPTED. Reworded Task 4 to say "one or two wrapped
  comment lines; physical line count immaterial".

## Round 2

### Codex response (verbatim)

**MAJOR**

Task 1 cannot satisfy its own red/green/commit contract. It adds the new validator, then
says `python -m pytest tests/integrations/test_schwab_trader.py -q` should be green before
Task 2. But Task 2 defers converting the existing mapper happy-path payload
`"transactionId": "T123"` and assertion in test_schwab_trader.py:247. Once Task 1's validator
exists, that existing test raises during mapper construction, so the whole file cannot be
green. Fix by either running Task 1 acceptance with `-k` limited to the new construction
tests, or moving the `T123` conversion into Task 1 / combining Tasks 1 and 2 before the first
commit.

**MINOR** — sweep of real construction sites looks complete; no missing direct/helper caller
that would raise post-fix.

**MINOR** — coupled fixture edits for the matcher tests look behaviorally correct (ref-equality
moves together; EFT_REF_456 stays non-matching; T2 decoy stays distinct).

**MINOR** — the mapper `0` note is factually sloppy: mapper uses `transactionId or activityId`,
so a raw integer `0` transactionId is falsy and not `str(0)` unless activityId supplies it.
Out of scope, but the plan should not say `str(0)="0"` passes "regardless" at the mapper path.

**MINOR** — the explanation that `_OOF_REF_RE.match`/`_VOID_REF_RE.match` are safe because their
bodies "forbid newlines differently" is false for trailing newlines (Python `$` matches
before a final newline). Does not damage the new impl (plan correctly requires fullmatch),
but the rationale should be corrected.

**NIT** — "schwab_reconciliation.py logic byte-unchanged" / "bytecode byte-equivalent" is not
reliable after inserting comments (line tables change). Say executable source / AST unchanged.

### Adjudication (mine)

- MAJOR (Task 1 acceptance impossible because Task 2 defers T123 in the same file) — ACCEPTED,
  valid. FIXED: moved the §2.A #4 test_schwab_trader.py:247/:265 T123->123 conversion INTO
  Task 1 (the file co-hosting the new validator tests), removed it from Task 2, and rewrote
  both acceptance lines: Task 1 acceptance now = test_schwab_trader.py FULLY green (new tests
  + converted test_05); Task 2 covers the other three files; the plan notes the broader suite
  is intentionally not-yet-green between Task 1 and Task 2.
- MINOR (sweep complete) — informational, no action (confirms §2 enumeration).
- MINOR (coupled edits correct) — informational, no action (confirms §2.A/§2.B coupling).
- MINOR (mapper 0 note sloppy) — ACCEPTED. Rewrote the §2.E `0`-quirk parenthetical to
  describe the `transactionId or activityId` field-selection quirk accurately and to state
  the constraint never interacts with it (any str(int) the mapper builds is ^[0-9]+$),
  dropping the "passes regardless" claim.
- MINOR (OOF/VOID .match newline rationale false) — ACCEPTED. Rewrote the GREEN-step note:
  the existing `$` + `.match` calls would ALSO accept a trailing newline; do NOT cite them as
  a newline-safe precedent; out of D20 scope and unchanged.
- NIT (byte-unchanged phrasing) — ACCEPTED. Replaced "AST/bytecode byte-equivalent" and
  "logic byte-unchanged" with "executable source / AST unchanged" at the §1 table, the §1
  re-assert sentence, and the §6 acceptance bullet.

## Round 3

### Codex response (verbatim)

CRITICAL: None.
MAJOR: None.

MINOR:
- Task 3's red/green sequencing is inconsistent if run as a separate ordered task. After Task
  1 lands, the void:/oof: construction barrier already exists, so the Task 3 "RED" test will
  not fail when added after Task 2. The discriminating arithmetic is correct only relative to
  pre-Task-1 code. The plan partly acknowledges this by allowing the test to fold into Task 1;
  it should make that the required path or drop the separate "RED" claim.
- §1 / §6 say integrations/schwab is the only production touch, but Task 4 intentionally
  touches swing/trades/schwab_reconciliation.py comments. The intended claim appears to be
  "only executable production logic touch." As written, it is a small reporting contradiction.

NIT:
- Several test comments in test_schwab_cash_matcher_window.py will become stale after T1/T2
  literals become 1/2. Not behavior-breaking, but the plan should allow nearby comment
  updates if it wants the converted fixture docs to stay truthful.

(Closing: no missed real SchwabTransactionResponse construction or _mk_tx/_tx helper-caller
that would raise post-fix; coupled ref/id-key edits correct; raise-test arithmetic including
the "123\n" fullmatch discriminator is sound.)

Verdict line: NO_NEW_CRITICAL_MAJOR

### Adjudication (mine)

CONVERGED at R3 (NO_NEW_CRITICAL_MAJOR — zero critical/major). The remaining MINOR/NIT are
quality tightenings; addressed anyway:
- MINOR (Task 3 sequencing) — ACCEPTED. Rewrote Task 3 to REQUIRE folding the proof-closure
  test into Task 1's commit (written before the validator, seen to fail); removed the
  separate-commit option; the distinguishing note now states the arithmetic holds only
  because the test rides the Task 1 commit.
- MINOR (§1/§6 "only production touch" contradiction with Task 4 comments) — ACCEPTED.
  Reworded both spots to "only EXECUTABLE-production-logic touch is integrations/schwab; the
  swing/trades touch is comment-only".
- NIT (stale T1/T2 comments in matcher_window) — ACCEPTED. Added a comment-truth allowance to
  Task 2 (MAY update nearby comments to numeric literals; cosmetic, rides Task 2 commit).

A confirming Round 4 was run on the final text to ensure these edits introduced no new
crit/major (see Round 4).

## Round 4 (confirming)

### Codex response (verbatim)

CRITICAL: None.
MAJOR: None.
MINOR: None.

NIT:
- Task 1's first regression-arithmetic bullet says "For each RAISE case" but the inline list
  omits "123\n". The later bullets correctly analyze "123\n" and the test design is sound, so
  this is wording cleanup only.

(Closing: no missing SchwabTransactionResponse construction or helper caller that would raise
post-fix; the mapper-driven "T123" case in test_schwab_trader.py is correctly included; the
coupled ref/assertion edits preserve the intended ref==tx_id / ref!=tx_id relationships; the
raise-test arithmetic is sound — non-empty guard accepts all bad values pre-fix, fullmatch
rejects post-fix, "123\n" catches the .match/$ newline bug.)

Verdict line: NO_NEW_CRITICAL_MAJOR

### Adjudication (mine)

CONVERGED. Two consecutive NO_NEW_CRITICAL_MAJOR (R3, R4); R4 returned ZERO MINOR and a
single cosmetic NIT. Addressed the NIT (added "123\n" to the first arithmetic bullet's inline
list) — a prose-only cleanup that cannot introduce a new finding. No further rounds needed.

## Convergence summary
- Round 1: 1 MAJOR (re.match vs fullmatch / trailing-newline) + 2 MINOR + 1 NIT — all fixed.
- Round 2: 1 MAJOR (Task 1 acceptance impossible w/ deferred T123) + 3 MINOR + 1 NIT — all fixed.
- Round 3: 0 CRIT/MAJOR (NO_NEW_CRITICAL_MAJOR) + 2 MINOR + 1 NIT — all fixed.
- Round 4: 0 CRIT/MAJOR/MINOR (NO_NEW_CRITICAL_MAJOR) + 1 cosmetic NIT — fixed.
Final verdict: NO_NEW_CRITICAL_MAJOR (converged).

# EXECUTING REVIEW (D20 implementation)

Base for the review diff: the plan commit `64d3c649`. Reviewer: codex-cli 0.135.0,
profile `review-strong` (gpt-5.5/high), `-s read-only` repo access at the worktree
(it grepped schwab_reconciliation.py + mappers.py + trader.py + pipeline_steps.py to
verify the construction chokepoint and the disjointness proof). Full raw output:
`.codex-review-r1.txt` (gitignored).

## Round 1 (review-strong, repo-access)

### Codex response (summary; full verbatim in .codex-review-r1.txt)
Codex grepped every `SchwabTransactionResponse(` construction site (mappers.py:605
the production one; the test conftests/helpers; the three `_Txn` mirror dataclasses
which it correctly identified as NOT the real class) and confirmed the
`__post_init__` is the single chokepoint covering production. It confirmed:
- the regex uses `fullmatch` correctly (match-vs-fullmatch newline issue handled),
- `"0"` is accepted, `""` still rejected,
- the schwab_reconciliation.py change is comment-only,
- the fixture conversions preserve the behavioral assertions.

One finding:
- MINOR `swing/integrations/schwab/models.py` (the new transaction_id rejection
  message): `f"... got {self.transaction_id!r}"` can embed PRINTABLE Unicode for a
  non-ASCII rejected id (e.g. fullwidth digits `１２３` -> `got '１２３'`), so the
  ERROR STRING is not ASCII-stable even though the regex correctly rejects the value.
  Violates the project's ASCII-only message discipline. Fix: `ascii(...)` (or
  otherwise escape) the interpolated value.

### Verdict
`NO_NEW_CRITICAL_MAJOR`

### Adjudication (implementer)
- MINOR (ASCII-stability of the rejection message): ACCEPTED + FIXED. This is a
  genuine, in-scope ASCII-discipline concern (the repo runs on Windows cp1252;
  CLAUDE.md hard-bans non-ASCII in any stdout/click.echo path, and a rejected-id
  ValueError message can surface to stdout). `repr()` of a non-ASCII str leaves the
  glyphs printable; `ascii()` escapes them to `\uXXXX`. Switched the f-string to
  `ascii(self.transaction_id)`. Cheap, correct, no behavioral change to the
  validation itself (the regex rejection set is unchanged). Committed as a
  `fix(integrations): Codex R1 MINOR` commit.

## Round 2 (review-strong, repo-access) -- re-review after the R1 MINOR fix

### Codex response (summary; full verbatim in .codex-review-r2.txt)
Re-reviewed the full updated diff (base = plan commit, includes the R1 fix).
- Confirmed the R1 MINOR is RESOLVED: the message now uses `ascii(self.transaction_id)`
  so fullwidth digits are escaped; the regression test asserts `.isascii()`.
- Confirmed the production mapper (mappers.py:605) is the construction path, so
  `void:`/`oof:` ids cannot reach the matcher via the Schwab API path; any collision
  argument requiring those values is OUT-OF-SCOPE per the barrier (models.py:373).
- Zero new findings.

### Verdict
`NO_NEW_CRITICAL_MAJOR`

### Adjudication (implementer)
Convergence reached: two consecutive `NO_NEW_CRITICAL_MAJOR` verdicts, the only
finding (R1 MINOR) fixed and confirmed resolved, no new critical/major. review-strong
loop CONVERGED. (Codex could not run pytest in its sandbox shell -- the implementer's
before-review full fast suite is the test gate: 8745 passed / 5 skipped.)

## codex-auto-review (complementary second eye, matched-high effort, repo-access)

### Codex response (summary; full verbatim in .codex-autoreview.txt)
Independent review of the full diff with repo read-access. Confirmed: the regex
uses fullmatch + rejects trailing newline + rejects non-ASCII digits + accepts "0";
the rejection message is ASCII-stable via ascii(...); the schwab_reconciliation.py
diff is comment-only; the converted fixtures preserve their exact-ref / dedup /
sign-match behavior.

One finding:
- MINOR `swing/integrations/schwab/mappers.py:571`: the pre-existing
  `tx_id_raw = _opt(raw, "transactionId") or _opt(raw, "activityId")` is
  truthiness-based, so an integer transactionId of 0 falls through the `or` to
  activityId. With the dataclass now allowing "0", the mapper construction path
  does not preserve that edge. Fix: select fallback on absence/empty, not falsiness.

### Verdict
`NO_NEW_CRITICAL_MAJOR`

### Adjudication (implementer)
- MINOR (mappers.py:571 falsy-0 `or` quirk): OUT-OF-SCOPE / FLAGGED-NOT-FIXED.
  This is the EXACT pre-existing quirk the brief §7 and the plan §2.E + §7
  explicitly enumerate and leave: it is orthogonal to D20 (it concerns WHICH field
  supplies the id, not the numeric constraint), and it is NOT a regression from this
  change -- whatever id the mapper builds via str(...), str(int) is always ^[0-9]+$,
  so the new constraint never rejects valid mapper output and does not interact with
  the `0` quirk. The auto-reviewer itself rated it MINOR, not critical/major. Fixing
  it would change WHICH field supplies the id (a behavioral/measurement-adjacent
  change beyond D20's validation-only scope) and would need its own arc. Recorded
  here + surfaced in the return report for the orchestrator/CHARC; deliberately not
  touched (the void brief's §3-swimlane discipline -- do not expand scope inline).

## CONVERGENCE
review-strong: 2 rounds, both NO_NEW_CRITICAL_MAJOR (R1's single MINOR fixed +
re-confirmed in R2). codex-auto-review: NO_NEW_CRITICAL_MAJOR (its only MINOR is the
brief-enumerated out-of-scope mappers.py quirk). Both reviewers CONVERGED.
