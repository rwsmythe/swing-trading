# Implementation Plan — Schwab `transaction_id` numeric constraint (`^[0-9]+$`)

**Arc:** register **D20** — Phase-18-close hardening.
**Brief (binding design contract):** `docs/schwab-txn-id-numeric-constraint-commissioning-brief.md` (committed `4a363f95`).
**Base:** `main` @ `0f0c273d`. Worktree: `.worktrees/d20-schwab-txnid-plan`.
**QA routing:** CHARC-lane (validation-only; NO measurement-value change). RD fyi. NO operator §5.10 live-witness.
**Plan tier:** writing-plans (this doc), Codex `review-fast`. Execution tier: `implementer-opus-high`, Codex `review-strong` + codex-auto-review.

---

## 0. One-paragraph summary

Add a single `^[0-9]+$` regex check to `SchwabTransactionResponse.__post_init__`
(`swing/integrations/schwab/models.py`), after the existing non-empty check. This
is the SINGLE construction chokepoint for the dataclass (the F6 "enforce at the
`__post_init__` construction barrier" gotcha) — every caller (the production mapper,
all tests, any future caller) passes through it, so NO parallel check at the mapper or
path-param is needed (brief §4, §7). The Schwab spec types the id as `integer ($int64)`
and the production mapper builds `transaction_id=str(int_id)`, which is always `^[0-9]+$`
— so the constraint enforces exactly what the spec already guarantees and rejects ONLY
out-of-spec input (the `oof:`/`void:` self-source collision proofs depend on tx-ids being
numeric; this makes that proof SELF-ENFORCING instead of assumed). The remaining real work
is (a) converting every non-numeric `transaction_id` in the `tests/` tree to numeric while
keeping each test's assertions green, and (b) appending a one-line comment at the two
`schwab_reconciliation.py` proof sites noting the proof is now enforced at the barrier (D20).

---

## 1. No-tripwire self-certification (brief §3 — verified on disk)

| Tripwire | Crossed? | Disposition (verified on disk) |
|---|---|---|
| New schema / migration | **NO** | Schema **v31 UNCHANGED**. A dataclass `__post_init__` validator; no DB change, no `.sql`. |
| New module / package | **NO** | Edits existing `swing/integrations/schwab/models.py` (adds `import re` + a module-level compiled regex). |
| New external dependency | **NO** | `re` is stdlib. No `pyproject.toml` change. |
| New standing process | **NO** | — |
| `swing/trades` \| `swing/data` carve-out | **NO** | The constraint lands in `swing/integrations/schwab/`. The `swing/trades/schwab_reconciliation.py` touch is **COMMENT HYGIENE ONLY — no logic change** (executable source / AST unchanged; only comment text added). |
| Measurement-VALUE change | **NO** | Validation-only — it rejects out-of-spec input; it changes NO equity/recon/measurement value. The production mapper builds numeric ids, so NO valid live data is rejected. |

The executing implementer MUST re-assert this table in the return report and confirm
on-disk: the constraint at the single chokepoint, `integrations/schwab` the only
EXECUTABLE-production-logic touch (the `swing/trades/schwab_reconciliation.py` touch is
comment-only — see Task 4), `schwab_reconciliation.py` executable source / AST unchanged
(comment-only diff), fixtures converted, ZERO `Co-Authored-By`, schema v31 unchanged.

---

## 2. The `tests/` grep-sweep (the binding enumeration — do NOT re-discover)

This is the load-bearing artifact of the plan. Every `SchwabTransactionResponse(...)`
construction AND every helper/factory that builds one was grepped across the WHOLE
`tests/` tree (`grep -rn "SchwabTransactionResponse" tests/` + the `_mk_tx`/`_tx`
helper-caller sweep). For each site: the current `transaction_id`, whether it is already
numeric (`^[0-9]+$`), the converted value, and the COUPLED edits needed to keep
assertions green.

> **The coupling rule:** the PASS-1 matcher matches a Schwab tx to a journal
> `cash_movement` by `str(tx.transaction_id) == cm.ref`. So whenever a test sets a
> journal `cash_movements.ref` (or a `journal_cash` tuple's 4th element, or a dict-key
> assertion keyed on the ref string) EQUAL to the tx id to force a ref-match, that
> coupled value MUST be converted in lockstep with the tx id. A journal `ref` itself is
> NOT a `SchwabTransactionResponse` field, so it has no numeric constraint — but it must
> stay equal-or-not-equal to the tx id exactly as the test intends.

### 2.A — Direct `SchwabTransactionResponse(...)` constructions

| # | File:line | Current `transaction_id` | Numeric? | Converted value | Coupled edits (keep assertions green) |
|---|---|---|---|---|---|
| 1 | `tests/integrations/test_schwab_pipeline_steps.py:1426` | `"T100"` | NO | `"100"` | Journal `cash_movements.ref` planted `"T100"` at `:1420` (4th INSERT arg) — convert to `"100"` so the ref-hit still suppresses `cash_movement_mismatch` (assert `:1451` unchanged). |
| 2 | `tests/integrations/test_schwab_pipeline_steps.py:1477` | `"T200"` | NO | `"200"` | Journal `cash_movements.ref` planted `"T200"` at `:1471` — convert to `"200"` (the step-6.5 ref-hit contract; assert `:1502` unchanged). |
| 3 | `tests/integrations/test_schwab_pipeline_steps.py:1521` | `"T201"` | NO | `"201"` | The journal ref at `:1515` is `"EFT_REF_456"` — DELIBERATELY non-matching (this test asserts a mismatch IS emitted). Leave `"EFT_REF_456"` (it is a journal ref, NOT a tx id → no constraint; and it must stay non-numeric/non-matching so the wrong-sign decoy still does not ref-match). Only the tx id `"T201"`→`"201"` changes. |
| 4 | `tests/integrations/test_schwab_trader.py` payload `:247` → mapper-built, assert `:265` | payload `"transactionId": "T123"`; asserts `t.transaction_id == "T123"` | NO | payload `"123"`, assert `"123"` | **Mapper-driven site NOT named in brief §2 — found by the sweep.** `map_transactions_to_response`/`get_account_transactions` build `transaction_id=str("T123")="T123"` which now RAISES. Convert the payload `"transactionId"` to `"123"` AND the `:265` assertion to `t.transaction_id == "123"`. (This is exactly why the sweep is binding — the brief's §2 list was non-exhaustive by design.) |

### 2.B — Helper/factory `_mk_tx` (`tests/trades/conftest.py:68`) and its callers

`_mk_tx(spec, idx)` builds `tid = str(spec[3]) if len(spec) > 3 and spec[3] is not None
else f"95000{idx}"` — the default (`95000{idx}`) is numeric; an explicit `spec[3]` is
`str()`-wrapped but NOT prefixed, so a non-numeric `spec[3]` produces a non-numeric tx id
that now RAISES. The helper itself needs NO change; the NON-NUMERIC `spec[3]` callers do.
Callers reach `_mk_tx` via the `cash_recon_full` fixture's `schwab_txs=[(type,date,amount[,tid[,desc]])]` param (`conftest.py:126`).

`schwab_txs` caller sweep (`grep -rn "schwab_txs" tests/trades/`) — only the tuples with a
4th element (`tid`) that is non-numeric need conversion:

| # | File:line | Current `tid` (spec[3]) | Numeric? | Converted value | Coupled edits |
|---|---|---|---|---|---|
| 5 | `tests/trades/test_schwab_cash_ingestion.py:179` | `"900088"` | YES | (unchanged) | none |
| 6 | `tests/trades/test_schwab_cash_ingestion.py:195` | `"SBX1"` | NO | `"9001"` (any numeric) | Sandbox-skip test; no ref-coupling — asserts `cash_movements` count is 0. No coupled edit. |
| 7 | `tests/trades/test_schwab_cash_ingestion.py:207` | `"PRD1"` | NO | `"9002"` | **Coupled:** `:210` asserts `WHERE ref='PRD1'` count == 1. Convert the assertion to `WHERE ref='9002'` (the ingest writes `cm.ref = str(tx.transaction_id)`). |
| 8 | `tests/trades/test_schwab_cash_matcher_window.py:16` | (no tid — 3-tuple) | n/a | default `95000{idx}` (numeric) | none |
| 9 | `tests/trades/test_schwab_cash_matcher_window.py:51` | `"T1"` | NO | `"1"` | **Coupled:** journal_cash ref `"T1"` at `:49`→`"1"`; the assertions `ids["T1"]`/`ids["NULL"]` at `:60`-`:61` key on the journal `ref` string → `ids["1"]`/`ids["NULL"]` (the `NULL` row is ref-less, unchanged). |
| 10 | `tests/trades/test_schwab_cash_matcher_window.py:70` | `"T1"` | NO | `"1"` | **Coupled:** journal_cash ref `"T1"` at `:69`→`"1"`. No id-keyed assertion (counts only). |
| 11 | `tests/trades/test_schwab_cash_matcher_window.py:86` | `"T1"` | NO | `"1"` | **Coupled:** journal_cash ref `"T1"` at `:84`→`"1"`. The decoy at `:87` is `"T2"` (see #12). |
| 12 | `tests/trades/test_schwab_cash_matcher_window.py:87` | `"T2"` (decoy) | NO | `"2"` | The same-amount decoy tx; must stay numerically DISTINCT from the ref (`"1"`). `"2"` preserves "different tx" semantics; counts-only assertion unchanged. |
| 13 | `tests/trades/test_schwab_cash_matcher_window.py:102` | `"TXI1"` | NO | `"11"` | **Coupled:** journal_cash ref `"TXI1"` at `:101`→`"11"` (income-kind ref-match within window; counts-only assertion). |

### 2.C — Helper/factory `_tx` (`tests/trades/test_schwab_cash_ingestion.py:17`)

`_tx(tid, ...)` builds `transaction_id=str(tid)`. ALL its callers
(`grep -n "_tx(" tests/trades/test_schwab_cash_ingestion.py`) pass numeric `tid`:
`1` (lines 27/32/37/42/47/48/54/59/64/71), `900042` (:80), `900001` (:92), `900002` (:108),
`900003` (:120), `900004` (:133), `900005`/`900006` (:150-151), `900007` (:215).
`str(int)` of each is `^[0-9]+$` → **ALL already numeric; NO change needed.** The helper
needs NO change.

**Enumeration-completeness note (Codex R1 MINOR):** the `schwab_txs` sweep also covers
`tests/trades/test_schwab_equity_coherence.py:89` (tid `"900099"` — already numeric, will NOT
raise post-fix) and the no-tid 3-tuple callers in `test_schwab_cash_matcher_window.py:16/31`
and `test_schwab_equity_coherence.py` (default `f"95000{idx}"`, numeric). These require NO
edit; listed here so the enumeration is literally complete (every `_mk_tx`-reaching caller
accounted for, numeric or converted).

### 2.D — Constructions that are INTENTIONALLY UNAFFECTED (record, do not touch)

| Site | Why unaffected |
|---|---|
| `tests/trades/test_cash_void.py:45-52` (`_Txn` mirror) | Local `@dataclass _Txn` with NO `__post_init__` — NOT the real `SchwabTransactionResponse`. It deliberately carries `transaction_id="void:..."` to exercise the matcher's self-source skip. Bypasses the constraint by construction. **Leave as-is.** |
| `tests/trades/test_oof_buy_cash_coherence.py:49-56` (`_Txn` mirror) | Same — local mirror dataclass; carries `oof:...` ids; bypasses the constraint. **Leave as-is.** |
| `tests/cli/test_oof_buy_command.py:438-439` (`_Txn` mirror) | Third local `_Txn` mirror dataclass (NOT `SchwabTransactionResponse`). Currently uses numeric `"115520131470"` at `:467` (will NOT raise even if it were the real class). Bypasses the constraint by construction. **Leave as-is.** Listed for completeness (Codex R1 MINOR) so the executor does not "fix" it. |

> The three mirror classes are tagged "Mirror SchwabTransactionResponse's matcher-relevant
> fields" — they exist precisely to feed the matcher arbitrary ids the real dataclass
> would (now) reject. They prove the matcher's skip logic, not the construction barrier. No
> brief obligation to change them; recorded here so the executing implementer does not
> "fix" them and break the very tests that prove the matcher.

### 2.E — Mapper-internal construction (production, NO change)

`swing/integrations/schwab/mappers.py:606` builds `transaction_id=str(tx_id_raw)` where
`tx_id_raw = _opt(raw, "transactionId") or _opt(raw, "activityId")` (raises if None). For a
spec-conformant integer payload `str(int)` is always `^[0-9]+$` → passes the new constraint.
**The mapper needs NO change.** (The pre-existing falsy-`0` `or` quirk at `:571` —
`_opt(raw, "transactionId") or _opt(raw, "activityId")` treats an integer-`0` transactionId
as falsy and falls through to `activityId` — is orthogonal to D20: it concerns WHICH field
supplies the id, not the numeric constraint. Whatever id the mapper ultimately builds via
`str(...)`, a `str(int)` is `^[0-9]+$`, so the new constraint never rejects valid mapper
output and does not interact with the `0` quirk; brief §7, leave it.)

---

## 3. Tasks (TDD, ordered; red -> green -> commit each)

> Per recipe §2: each task = write the failing test first, RUN it and SEE the correct
> failure, minimal implementation, RUN and SEE pass, commit. Run from inside the worktree
> cwd (`python -m pytest ... -q`; cwd-based discovery tests the worktree's code).

### Task 1 — Add the `^[0-9]+$` constraint to `SchwabTransactionResponse.__post_init__`

**RED — write the discriminating construction tests first.** Add to
`tests/integrations/test_schwab_trader.py` (it already imports `SchwabTransactionResponse`
at `:50`), a focused test class/function. Use the dataclass's existing valid kwargs for the
non-`transaction_id` fields (a valid `type` from `_SCHWAB_TRANSACTION_TYPES` e.g.
`"ACH_RECEIPT"`, a valid ISO `transaction_date` `"2026-06-15"`, finite `net_amount=1.0`,
`description=None`).

Parametrized RAISE cases (each MUST raise `ValueError`):
```
"void:6", "oof:SPCX:2026-06-15", "T100", "abc", "12.0", "123\n"
```
(`"123\n"` is the trailing-newline discriminator that pins `fullmatch` over `match` — see
the GREEN step's Codex-R1-MAJOR note.)
Use `with pytest.raises(ValueError):` (pin the EXACT type = `ValueError`, the dataclass's
existing convention). Optionally assert the message contains the ASCII token `^[0-9]+$`
(see message below) — but do NOT over-pin the full message (brittle).

Parametrized CONSTRUCT-FINE cases (must NOT raise; assert `.transaction_id` round-trips):
```
"123", "0"
```
(`"0"` is the edge: `^[0-9]+$` accepts a single zero; this proves the regex is `+` not a
"no leading zero" rule, and documents that a `str(0)` mapper output is accepted.)

Empty-string still rejected (existing behavior preserved):
```
"" -> ValueError
```

**Regression-distinguishing arithmetic (memory `feedback_regression_test_arithmetic`) —
reason BOTH paths, recorded so the executing implementer SEES the red before green:**

- PRE-fix `__post_init__` only checks `if not isinstance(self.transaction_id, str) or not
  self.transaction_id` (non-empty str). For each RAISE case the value is a non-empty str
  (`"void:6"`, `"oof:SPCX:2026-06-15"`, `"T100"`, `"abc"`, `"12.0"`, AND `"123\n"`) → the
  guard is False → construction SUCCEEDS → `pytest.raises(ValueError)` is NOT satisfied →
  **test FAILS pre-fix.**
  (The implementer MUST run the new test against the unmodified `models.py` and SEE it fail
  for exactly this reason — a `Failed: DID NOT RAISE ValueError`.)
- POST-fix the new `fullmatch(r"[0-9]+")` check raises `ValueError` for every
  non-fully-numeric value (`"void:6"` has `:` and letters; `"oof:..."` letters/colon;
  `"T100"` a `T`; `"abc"` letters; `"12.0"` a `.`; `"123\n"` a trailing newline that
  `fullmatch` rejects) → `pytest.raises` satisfied → **test PASSES post-fix.**
- The `"123\n"` case ALSO distinguishes `fullmatch` from a naive `^[0-9]+$` + `.match`
  impl: `re.match(r"^[0-9]+$", "123\n")` SUCCEEDS (no raise → that impl FAILS the test),
  whereas `fullmatch` raises (PASS). So this single case both fails-pre-fix (today's
  non-empty-only check accepts `"123\n"`) AND guards against the wrong-anchor regression.
- The two CONSTRUCT-FINE cases (`"123"`, `"0"`) pass BOTH pre- and post-fix (they are
  numeric + non-empty) — they are the no-false-positive guard, NOT the distinguisher.
- Empty `""` raises BOTH pre- and post-fix (non-empty check unchanged) — preserved behavior.
- Net: every RAISE case is a genuine distinguisher (fails pre, passes post); no raise-test
  passes under both paths (the "worthless test" trap is avoided).

**GREEN — minimal implementation in `swing/integrations/schwab/models.py`:**
1. Add `import re` to the top-of-module imports (after `import math` at `:22`; the
   `from __future__ import annotations` stays first).
2. Add a module-level compiled regex near the existing module constants:
   ```python
   _TXN_ID_RE = re.compile(r"[0-9]+")
   ```
3. In `__post_init__`, AFTER the existing non-empty check (the block ending at `:367`),
   add (the non-empty check is logically subsumed but KEPT for a clear message per brief §4):
   ```python
   if not _TXN_ID_RE.fullmatch(self.transaction_id):
       raise ValueError(
           "SchwabTransactionResponse.transaction_id must match ^[0-9]+$ "
           "(Schwab transaction ids are integer per spec); "
           f"got {self.transaction_id!r}"
       )
   ```
   - **ASCII-only** (cp1252 gotcha): the message uses only ASCII (`^[0-9]+$`, parens, `!r`).
     No em-dash, no glyphs.
   - Ordering matters: the non-empty check runs first (so `""` -> the "must be non-empty str"
     message; an empty string would ALSO fail the regex, but the existing message is clearer
     and the test for `""` asserts only `ValueError`, so either path is acceptable — keep the
     non-empty check first for the descriptive message).
   - **Use `.fullmatch`, NOT `.match` (Codex R1 MAJOR — load-bearing).** In Python the `$`
     anchor matches *before a trailing newline*, so `re.match(r"^[0-9]+$", "123\n")` SUCCEEDS
     — a `"123\n"` id would slip past a `^[0-9]+$` + `.match` check, defeating the barrier.
     `re.fullmatch(r"[0-9]+", value)` anchors BOTH ends with no newline exception (equivalent
     to `\A[0-9]+\Z`). Therefore the compiled pattern is `r"[0-9]+"` (no `^`/`$` needed —
     `fullmatch` anchors implicitly) and the check is `_TXN_ID_RE.fullmatch(...)`. The error
     MESSAGE still says `^[0-9]+$` (the human-readable contract). Do NOT copy the
     `_OOF_REF_RE.match`/`_VOID_REF_RE.match` form from `schwab_reconciliation.py` as a
     "newline-safe" precedent — those `$` + `.match` calls would ALSO accept a trailing
     newline; they are out of D20's scope and unchanged, but here the trailing newline IS the
     attack on the tx-id barrier, so `fullmatch` is mandatory.
   - **Add `"123\n"` (trailing newline) as a RAISE test case in Task 1's parametrization.**
     It is the discriminator that proves `fullmatch` (not `match`) was used: under a
     `^[0-9]+$` + `.match` impl it would NOT raise (test fails); under `fullmatch` it raises
     (test passes). Without this case the `match`-vs-`fullmatch` bug is invisible to the suite.

**Same-file fixture conversion — IN THIS TASK (Codex R2 MAJOR).** The validator and the new
tests live in `tests/integrations/test_schwab_trader.py`, but that SAME file already has a
mapper-driven happy-path test (`test_05_get_account_transactions_happy_path`, payload
`"transactionId": "T123"` at `:247`, assert `t.transaction_id == "T123"` at `:265`) that
RAISES the moment the validator exists. So the §2.A #4 conversion MUST land in THIS task's
commit — NOT deferred to Task 2 — or `test_schwab_trader.py` cannot be green at the Task 1
commit boundary (red/green/commit contract). Convert in Task 1:
- `tests/integrations/test_schwab_trader.py:247` payload `"transactionId": "T123"` -> `"123"`
- `:265` assertion `t.transaction_id == "T123"` -> `== "123"`
(The OTHER affected files — pipeline_steps, cash_ingestion, cash_matcher_window — are
untouched in Task 1; they turn red here but are converted in Task 2. Only the file that
co-hosts the new validator tests must be made green in lockstep with Task 1.)

**Acceptance:** `python -m pytest tests/integrations/test_schwab_trader.py -q` is FULLY GREEN
(the new construction tests pass AND the converted `test_05` passes). Note: the broader fast
suite is NOT yet green here — the §2.A/§2.B sites in the other three files are red until Task
2; that is expected and is the reason Task 2 immediately follows.

**Commit:** `feat(integrations): Task 1 — enforce ^[0-9]+$ on SchwabTransactionResponse.transaction_id`

---

### Task 2 — Convert the non-numeric `transaction_id` fixtures + coupled refs (the §2 sweep)

**RED is implicit here:** after Task 1, the remaining §2.A/§2.B non-numeric sites (in the
THREE files NOT touched by Task 1) now RAISE at construction — those existing tests turn RED.
This task turns them GREEN by converting each to numeric per the §2 table (mechanical). Run
the affected files FIRST to SEE them red
(`python -m pytest tests/integrations/test_schwab_pipeline_steps.py tests/trades/test_schwab_cash_ingestion.py tests/trades/test_schwab_cash_matcher_window.py -q`),
then apply the conversions, then re-run to GREEN. (`test_schwab_trader.py` was already made
green in Task 1 — do NOT re-convert §2.A #4 here.)

Apply EXACTLY the §2 table (§2.A #4 already done in Task 1):
- §2.A #1: `test_schwab_pipeline_steps.py:1426` tx `"T100"`->`"100"` + `:1420` ref `"T100"`->`"100"`.
- §2.A #2: `:1477` tx `"T200"`->`"200"` + `:1471` ref `"T200"`->`"200"`.
- §2.A #3: `:1521` tx `"T201"`->`"201"` (leave `:1515` ref `"EFT_REF_456"` — intentionally non-matching).
- §2.B #6: `test_schwab_cash_ingestion.py:195` tid `"SBX1"`->`"9001"`.
- §2.B #7: `:207` tid `"PRD1"`->`"9002"` + `:210` assert `WHERE ref='PRD1'`->`WHERE ref='9002'`.
- §2.B #9: `test_schwab_cash_matcher_window.py:51` tid `"T1"`->`"1"` + `:49` journal ref `"T1"`->`"1"` + `:60`-`:61` `ids["T1"]`->`ids["1"]`.
- §2.B #10: `:70` tid `"T1"`->`"1"` + `:69` journal ref `"T1"`->`"1"`.
- §2.B #11/#12: `:86` tid `"T1"`->`"1"` + `:84` journal ref `"T1"`->`"1"`; `:87` decoy `"T2"`->`"2"`.
- §2.B #13: `:102` tid `"TXI1"`->`"11"` + `:101` journal ref `"TXI1"`->`"11"`.

Do NOT touch: §2.C `_tx` callers (already numeric), §2.B #5 (`"900088"` numeric),
§2.B #8 (no tid), §2.D mirror classes.

**Comment-truth allowance (Codex R3 NIT):** several inline test comments in
`test_schwab_cash_matcher_window.py` reference the old literals (e.g. `ref='T1'`, "T2 $200").
The implementer MAY update those nearby comments to the new numeric literals so the converted
fixtures stay self-documenting — this is cosmetic and rides the Task 2 commit; not required
for green, but preferred for truthfulness.

**Distinguishing check for the conversions:** each converted test still asserts the SAME
outcome it did before (the ref-match suppresses/emits the same discrepancy; the same count;
the same id-keyed lookup). The conversion preserves the ref==tx-id (or ref!=tx-id) relation
that drives the matcher — so the test's BEHAVIORAL assertion is unchanged; only the literal
id strings move from non-numeric to numeric. Confirm each file goes green after conversion.

**Acceptance:** the three affected test files (pipeline_steps, cash_ingestion,
cash_matcher_window) green; combined with Task 1's already-green test_schwab_trader.py, all
four affected files are now green; the converted tests assert the same behaviors as before
(counts / ref-hits / id-keyed lookups all consistent with the new ids).

**Commit:** `test(integrations): Task 2 — convert non-numeric SchwabTransactionResponse fixtures to numeric (D20)`

---

### Task 3 — Proof-closure assertion (FOLDED INTO Task 1 — the collision is unreachable BY CONSTRUCTION)

**Sequencing (Codex R2/R3 MINOR — REQUIRED, not optional):** this proof-closure test MUST be
written AS PART OF Task 1 (in the same red-before-green window as the validator), NOT as a
separate task AFTER Task 1. Reason: once Task 1's barrier exists, a `void:`/`oof:`
construction test added later would NOT fail-first (the barrier is already in place) — the
red/green discipline is only meaningful relative to PRE-Task-1 code. So fold the test below
into Task 1's parametrization (or add it as a sibling function in the SAME Task 1 commit,
written before the validator and seen to fail). There is NO separate Task 3 commit.

**The proof-closure test** (brief §5 "a focused test asserting the construction barrier is
sufficient; a recon-boundary test is optional") — add inside Task 1, before the validator:
```python
def test_void_sentinel_id_cannot_be_constructed():
    # The PASS-1 find_by_ref(ref="void:6") collision against a void: sentinel
    # row is unreachable BY CONSTRUCTION: a Schwab transaction_id of "void:6"
    # can no longer be built (the ^[0-9]+$ barrier rejects it). Same for oof:.
    import pytest
    from swing.integrations.schwab.models import SchwabTransactionResponse
    for bad in ("void:6", "oof:SPCX:2026-06-15"):
        with pytest.raises(ValueError):
            SchwabTransactionResponse(
                transaction_id=bad, transaction_date="2026-06-15",
                type="ACH_RECEIPT", net_amount=1.0, description=None)
```
(This overlaps Task 1's parametrized RAISE cases but states the proof-closure INTENT
explicitly, which is the brief §5 obligation. Keep the intent visible — a docstring on the
folded test or this named function both satisfy §5.)

**Distinguishing:** identical arithmetic to Task 1 — pre-Task-1 these construct cleanly (no
raise → FAIL), post-fix they raise (→ PASS). This holds ONLY because the test ships in the
Task 1 commit (written before the validator); that is why Task 3 is folded, not separate.

**GREEN + Acceptance + Commit:** satisfied by Task 1 (this test rides Task 1's commit). NO
separate Task 3 commit.

---

### Task 4 — Comment hygiene at the two `schwab_reconciliation.py` proof sites (NO logic change)

**No test** (comment-only; brief §4 "No logic change in `schwab_reconciliation.py`").
Append a SHORT note (one or two wrapped comment lines — the physical line count is
immaterial, the content is "now enforced at the barrier") to the two PRIMARY
disjointness-proof comment blocks (re-grounded on disk; line numbers drift — anchor on the
comment TEXT, not the number):

1. The `_OOF_REF_PREFIX` proof block (currently ~`:219-224`, the "can NEVER collide with a
   real Schwab transaction_id: a transaction_id is a NUMERIC string ([0-9]+)" comment ending
   just before `_OOF_REF_PREFIX = "oof:"`). Append the D20 note, e.g.:
   ```
   #     (D20: the numeric [0-9]+ tx-id is now ENFORCED at
   #     SchwabTransactionResponse.__post_init__, so this disjointness is
   #     self-enforcing, not assumed.)
   ```
   (Wrap to fit the file's comment width; the exact physical line count does not matter.)
2. The `_VOID_REF_PREFIX` proof block (currently ~`:370-375`, the "Three disjoint
   ref-prefix domains ([0-9]+, oof:, void:)" comment ending just before
   `# KEY DIFFERENCE FROM THE OOF SENTINEL`). Append the same D20 note.

Constraints:
- **ASCII-only** (no em-dash, no glyphs) — these are source comments but keep ASCII per
  project discipline.
- **NO logic change** — only comment text is added; the `_OOF_REF_PREFIX` / `_VOID_REF_PREFIX`
  / `_OOF_REF_RE` / `_VOID_REF_RE` definitions and all executable lines are byte-identical.
  The executing implementer verifies via `git diff` that ONLY comment lines changed in this
  file (no `+`/`-` on any executable statement).
- The brief §1 also lists the predicate docstrings (`:329-330`, `:415-416`) and the PASS-1
  inline blocks (`:1998-2000`, `:2031-2032`) as proof sites. Appending to the TWO primary
  definition-block comments satisfies brief §4's "at the two proof sites" (the canonical
  `[0-9]+` disjointness claims live in the two definition blocks). The executing implementer
  MAY additionally annotate the docstrings/inline blocks if a Codex round flags them as
  stale; that stays comment-only and is OPTIONAL.

**Acceptance:** `git diff swing/trades/schwab_reconciliation.py` shows ONLY comment-line
additions; the full fast suite still green (comment change cannot affect behavior, but the
suite run confirms no accidental logic edit).

**Commit:** `docs(trades): Task 4 — annotate oof:/void: disjointness proof as enforced at __post_init__ (D20)`

---

## 4. Before-review gate (recipe §2, binding)

After all task-commits land and BEFORE the Codex loop:
1. Run the WHOLE fast suite from the worktree cwd: `python -m pytest -m "not slow" -q`.
   Fix any failure to green (cross-cutting tests are NOT exercised per-task). Read the tail;
   record the count for the return report (read off the FINAL head — never carry a mid-work
   count forward).
2. `ruff check swing/` clean (only `swing/` is gated; the constraint adds `import re` + a
   compiled regex + the check — keep lines <=100 chars, match existing style). Test-file lint
   is out of scope but match each file's existing style so no new violation.

---

## 5. Codex review (recipe §3)

- **Execution tier** (the actual implementation arc): `review-strong` (gpt-5.5/high,
  repo-access) to convergence + `codex-auto-review` (matched-high) — brief §6.
- **This writing-plans pass:** `review-fast` per the dispatch. Liveness-probe first; if the
  `review-fast` profile is absent, OMIT `-p` and pass `-c model_reasoning_effort=high`
  (NEVER `effort=none`). Pre-generate the diff on Windows, pipe via stdin, write output to a
  file. Iterate to `NO_NEW_CRITICAL_MAJOR`; persist every round verbatim + adjudication to
  the gitignored `.copowers-findings.md`.
- **Adjudication note (recipe §3 / memory `feedback_schema_boundary_defensive_scope`):** a
  Codex finding premised on a value the construction barrier itself prevents (e.g. "what if
  a non-numeric id reaches the matcher?") is OUT-OF-SCOPE — the `__post_init__` barrier is
  the very enforcement; cite the barrier line. The barrier is the writer-side enforcement
  here, so this is a CONSTRAINED-WRITER case, not a defensive-reader treadmill.

---

## 6. Acceptance summary (what "done" means)

- `SchwabTransactionResponse.transaction_id` rejects any non-`^[0-9]+$` value at
  construction; `"123"`/`"0"` construct; `""` still rejected.
- Every §2 non-numeric test site converted to numeric with coupled refs/assertions
  consistent; the four affected files + the full fast suite green.
- `schwab_reconciliation.py` comment-only diff (executable source / AST unchanged); the disjointness
  proof annotated as enforced at `__post_init__` (D20).
- No-tripwire table re-asserted on disk (schema v31 unchanged; the only
  executable-production-logic touch is `integrations/schwab`; the `swing/trades` touch is
  comment-only; `re` stdlib; no module/dep/process; no carve-out; no measurement value).
- ZERO `Co-Authored-By` (`git log <base>..HEAD --format='%H%n%(trailers)'` all empty); no
  `--no-verify`; no amend; final `-m` paragraph plain prose.
- Codex `review-strong` + codex-auto-review converged; `ruff check swing/` clean.

---

## 7. Out of scope / follow-ups (brief §7)

- Parallel check at the mapper / path-param — unnecessary (single `__post_init__` chokepoint).
- The `mappers.py:571` falsy-`0` `or` quirk — orthogonal; `str(0)="0"` passes `^[0-9]+$`;
  leave it (note only).
- Any change to the reconciliation MATCHING logic — the input constraint alone closes the
  proof; `schwab_reconciliation.py` gets comment hygiene only.
- The `_Txn` mirror dataclasses in `test_cash_void.py` / `test_oof_buy_cash_coherence.py`
  intentionally bypass the constraint to feed the matcher non-numeric ids — leave them.
