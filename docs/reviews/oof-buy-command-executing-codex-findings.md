# OOF-buy cash-coherence command — executing Codex review transcript (CONVERGED)

**Arc:** Phase-18 deferred follow-up #1 — `swing journal oof-buy` (the cash-recon ROOT fix).
**Plan:** `docs/plans/oof-buy-command-plan.md`. **Brief:** `docs/oof-buy-command-commissioning-brief.md`.
**Worktree base:** `308b4a35` (the plan commit on `main`). **Branch:** `oof-buy-exec`.
**Tier:** `review-strong` (gpt-5.5 / reasoning-effort high) WITH REPO ACCESS (production-code), run to
`NO_NEW_CRITICAL_MAJOR` (the project's 5-round cap is suspended) — PLUS `codex-auto-review`
(the adopted complementary second eye, repo-access, matched-HIGH effort). **Date:** 2026-06-18.

**Outcome:** CONVERGED. `review-strong` reached `NO_NEW_CRITICAL_MAJOR` at Round 6, R7 caught a
real defect in the [P2] fix's belt (fixed), Round 8 re-confirmed `NO_NEW_CRITICAL_MAJOR` on the final
state. `codex-auto-review` raised one `[P2]` (resolved). 8 review-strong rounds total. Every round's
verbatim Codex response + the per-finding adjudication is below (the gitignored working transcript
`.copowers-findings.md` carries the same content round-by-round).

The §2.4 measurement arithmetic (the both-sides-exclude orthogonality — the binding RD claim) was
INDEPENDENTLY CONFIRMED by Codex in rounds 2, 3, 4, and 8 ("the cash withdrawal affects ledger equity,
while `declared_oof_mv` is summed from broker positions, so both sides exclude the OOF holding").

---

## Summary of findings + resolutions (by round)

| Round | Verdict | Finding(s) | Resolution |
| --- | --- | --- | --- |
| 1 | NEW_CRITICAL_MAJOR_FOUND | R1-MAJOR-1 prefix-only predicate skips any `oof:`-prefixed ref; R1-MAJOR-2 non-finite `--cost` lands / mis-reported | `c39ef88d` canonical-shape regex; `f93dfc6c` finite-cost guard |
| 2 | NEW_CRITICAL_MAJOR_FOUND | R2-MAJOR-1 a canonical-ref NON-withdraw row is skipped | `8d1114b6` add `kind=='withdraw'` to the branch guard |
| 3 | NEW_CRITICAL_MAJOR_FOUND | R3-MAJOR-1 `journal cash --ref oof:...` writes a skippable non-OOF row; R3-MAJOR-2 ticker-domain mismatch (`BRK/B`) | `d17de173` reserve `oof:` at `journal cash`; `46c92588` predicate ticker `[^:]+` + colon-reject |
| 4 | NEW_CRITICAL_MAJOR_FOUND | R4-MAJOR-1 TOS import / other writers; R4-MAJOR-2 colon-bearing ticker | `385b5591` neutralize `oof:` in TOS import; `46c92588` (colon-reject) |
| 5 | NEW_CRITICAL_MAJOR_FOUND | R5-MAJOR skip not gated on the ticker being CURRENTLY declared OOF | `54f88242` gate skip on `_oof_ref_ticker(ref) in out_of_framework_set` |
| 6 | **NO_NEW_CRITICAL_MAJOR** | — (converged) | — |
| auto-review | `[P2]` | conflicting-cost replay reported as a silent no-op | `f195b26f` SELECT-first conflict check |
| 7 | NEW_CRITICAL_MAJOR_FOUND | R7-MAJOR-1 the IntegrityError belt doesn't apply the conflict check; R7-MAJOR-2 pre-existing/raw-DB rows (cited V1 boundary) | `6e5a1819` belt re-fetches + conflict-checks; R7-MAJOR-2 cited |
| 8 | **NO_NEW_CRITICAL_MAJOR** | — (re-confirmed on the final state) | — |

**The one CITED residual (R5 sub-point B / R7-MAJOR-2 — the V1 design boundary):** a RAW out-of-band DB
write (bypassing every repo) of a forged `oof:<declared-ticker>:<YYYY-MM-DD>` `withdraw` row would be
skipped as self-sourced. After the fixes, ALL production writers of a free-form ref are closed
(`journal cash` rejects `oof:`; the TOS import neutralizes `oof:`; the Schwab cash-ingest writes only
numeric `transaction_id` refs; `journal oof-buy` is the sole `oof:` writer and gates on the declared
set). The `oof:` convention is introduced by this arc, so no pre-existing `oof:` row exists on the
live DB. The only un-prevented vector is a raw out-of-band DB write — the "genuinely-unconstrained
input" class the recipe handles with GENERAL visibility (the matcher increments
`cash_oof_self_sourced_count`, surfaced in the run's `cash_ingest_summary` envelope every run), NOT a
per-case branch. FULLY preventing it requires a schema `origin`/`source` column on `cash_movements` —
a tripwire the brief §3 + plan §6 EXPLICITLY forbid (the settled design's marker IS the `oof:` ref,
plan §3). **V2 dependency flagged to CHARC:** a cryptographic origin column would close the raw-DB
residual; it is out of this arc's authorized scope (a second carve-out + a migration).

---

## Round 1 — review-strong

### Codex response (verbatim)

MAJOR: `_is_oof_sentinel_ref` is prefix-only, so the step-7 branch skips any cash row whose free-form `ref` starts with `oof:`. `journal cash --ref` can already write arbitrary refs, and the branch at `swing/trades/schwab_reconciliation.py:1807` does not verify canonical shape, `kind == "withdraw"`, date, or that the row was produced by `oof-buy`. Example: a normal unmatched deposit with `ref="oof:manual"` would have emitted `cash_movement_mismatch` before; now it is silently counted as self-sourced. This violates Lock 1.

MAJOR: `--cost` accepts non-finite floats. Click's `type=float` plus the validation lets `inf` through, and the insert records it as a `withdraw` amount. SQLite's `amount >= 0` check does not reject positive infinity, and later `current_equity` propagates it into a non-finite ledger value, suppressing equity-coherence evaluation instead of producing a trustworthy signal. `nan` is also mishandled: it trips an `IntegrityError` and is reported as "already recorded" because the catch treats every integrity failure as a unique-ref race.

NEW_CRITICAL_MAJOR_FOUND

### Adjudication
Both ACCEPTED + fixed. R1-MAJOR-1: tighten `_is_oof_sentinel_ref` to the canonical regex (the plan §3
authorized this); `_build_oof_ref` only emits canonical refs so the command path is unaffected
(`c39ef88d`). R1-MAJOR-2: add `math.isfinite(cost)` guard before the write (`f93dfc6c`).

## Round 2 — review-strong

### Codex response (verbatim)
MAJOR: The matcher branch is not guard-only for non-OOF rows. `_is_oof_sentinel_ref` accepts any canonical-shaped free-form ref, and PASS 2 skips immediately on that ref alone. Existing `journal cash` still allows arbitrary `--ref`. So a non-OOF row like `journal cash --deposit 100 --date 2026-06-18 --ref oof:SPCX:2026-06-18` now bypasses all kind/sign/amount/date matching and never emits `cash_movement_mismatch`. This violates Binding Lock 1. The §2.4 arithmetic itself checks out: `declared_oof_mv` is summed from positions, not `cash_movements`.

NEW_CRITICAL_MAJOR_FOUND

### Adjudication
ACCEPTED + fixed. The OOF command ALWAYS writes `kind="withdraw"`, so gate the branch on
`cm.kind == "withdraw"` too -> a non-withdraw canonical-ref row (deposit/interest/dividend/fee) is no
longer skipped (`8d1114b6`). Codex confirmed the §2.4 orthogonality.

## Round 3 — review-strong

### Codex response (verbatim)
MAJOR: The matcher skips any `withdraw` with a canonical-looking `oof:<TICKER>:<DATE>` ref, even if it was not created by `journal oof-buy`. `journal cash` still accepts arbitrary `--ref`. A manual `journal cash --withdraw 123 --date 2026-06-18 --ref oof:SPCX:2026-06-18` is a non-OOF cash movement but will be treated as self-sourced. That violates Lock 1.

MAJOR: `_build_oof_ref` and `_is_oof_sentinel_ref` do not accept the same ticker domain. The registry normalizer accepts any non-empty string; a registered ticker such as `BRK/B` writes `oof:BRK/B:...`, but the predicate only recognizes `[A-Z0-9.-]+` -> the genuine OOF row still emits `cash_movement_mismatch`.

NEW_CRITICAL_MAJOR_FOUND

### Adjudication
Both ACCEPTED + fixed. R3-MAJOR-1: RESERVE the `oof:` namespace by rejecting an `oof:`-prefixed
`--ref` at `journal cash` (`d17de173`) -> `journal oof-buy` becomes the only `oof:` writer.
R3-MAJOR-2: broaden the predicate ticker segment to `[^:]+` (matches the builder's domain — tickers
contain no colon) (`46c92588`).

## Round 4 — review-strong

### Codex response (verbatim)
MAJOR: Lock 1 is not enforced for existing or non-`journal cash` cash rows. The reservation guard only covers `journal cash`, but TOS import reads `REF #` directly into `CashMovement.ref` and commits via `insert_cash`. Also a pre-existing manual `withdraw` row with `ref='oof:SPCX:2026-06-18'` now silently changes disposition.

MAJOR: `_build_oof_ref` and `_is_oof_sentinel_ref` do not agree on the ticker domain — the registry accepts a colon (`NYSE:SPCX`); `_build_oof_ref` emits it verbatim; the predicate's single non-colon segment can't match.

The core arithmetic claim checks out: `withdraw` subtracts from ledger equity, while `declared_oof_mv` is summed from positions, not cash movements.

NEW_CRITICAL_MAJOR_FOUND

### Adjudication
R4-MAJOR-1: the only unguarded free-form-ref production writer is the TOS import (the Schwab ingest
writes numeric refs). A real broker `REF #` is never `oof:`-prefixed; neutralize an `oof:`-prefixed
TOS REF# to ref-less so the row keeps its pre-arc disposition (`385b5591`). R4-MAJOR-2: `_build_oof_ref`
rejects a colon-bearing ticker (raise -> the CLI wraps it as a ClickException) (`46c92588`). Codex
confirmed the §2.4 arithmetic again.

## Round 5 — review-strong

### Codex response (verbatim)
Major Finding: the matcher skips any `withdraw` whose `ref` matches `^oof:[^:]+:\d{4}-\d{2}-\d{2}$`, without checking that the ticker is currently declared OOF or that the row was produced by `journal oof-buy`. Concrete break: `kind='withdraw', ref='oof:AAPL:2026-06-18'` in a run where `out_of_framework_tickers=('SPCX',)` now bypasses the heuristic and never emits. That violates Lock 1.

NEW_CRITICAL_MAJOR_FOUND

### Adjudication
Sub-point A ACCEPTED + fixed: gate the skip on `_oof_ref_ticker(cm.ref) in out_of_framework_set` (the
new `_oof_ref_ticker` helper) — a legitimate OOF transfer-out is only ever for a declared ticker
(`54f88242`). Sub-point B (raw-DB / pre-existing rows) is the cited V1 boundary (see the summary).

## Round 6 — review-strong — CONVERGED

### Codex response (verbatim)
No critical or major defects found in the reviewed diff. I verified the matcher branch is guard-only for normal non-OOF rows, OOF refs cannot collide with numeric Schwab transaction IDs, the CLI uses `apply_overrides`, ticker/ref canonicalization is consistent, sandbox gating occurs after validation and before write, and `insert_cash` transaction/idempotency behavior is handled correctly.

NO_NEW_CRITICAL_MAJOR

## codex-auto-review (complementary second eye; repo-access, gpt-5.5/high)

Run via `codex exec review --base main -c model_reasoning_effort=high` on a WSL-native clone of the
arc (the worktree `.git` file is not WSL-resolvable for `--base`).

### Codex response (verbatim)
The new OOF buy command can silently ignore conflicting same ticker/date entries, leaving the cash ledger inaccurate while reporting success.

- [P2] Reject conflicting OOF buy replays — `swing/cli.py`: when the operator reruns this command for the same ticker/date with a different `--cost` (to correct a mistyped amount, or after a second same-day OOF buy), this branch treats the existing ref as a successful no-op without checking the stored amount/kind. Because the sentinel ref does not include cost, the ledger remains wrong while reconciliation will still consider the row self-sourced; please detect an existing row whose payload differs and surface a conflict.

### Adjudication
ACCEPTED + fixed (resolved, not just cited — measurement-core). The SELECT-first idempotency path now
compares the existing row's amount to the requested cost at cent precision: same cost = clean no-op;
different cost = a CONFLICT ClickException (`f195b26f`).

## Round 7 — review-strong — post-[P2]-fix confirmation

### Codex response (verbatim)
MAJOR: `swing/cli.py` silently accepts a conflicting TOCTOU duplicate. The normal `find_by_ref` path rejects same ticker/date with a different `--cost`, but the `IntegrityError` belt does not re-read the row or compare amount/kind/date. The belt needs to re-fetch by `ref` and apply the same conflict validation before treating it as idempotent.

MAJOR: `swing/trades/schwab_reconciliation.py` is not guard-only for all existing non-OOF rows ... pre-existing cash rows ... nor other callers of the public `insert_cash` ... a legacy/manual non-OOF withdraw with `ref='oof:SPCX:2026-06-18'` and `SPCX` declared now bypasses the old heuristic/emit path.

NEW_CRITICAL_MAJOR_FOUND

### Adjudication
R7-MAJOR-1 ACCEPTED + fixed: extract the no-op-or-conflict logic into a shared helper called from BOTH
the SELECT-first path AND the belt (which now re-fetches by ref) (`6e5a1819`). R7-MAJOR-2 is the SAME
residual as R5 sub-point B — re-grounded (all 4 production `insert_cash` callers closed; no pre-existing
`oof:` rows; the raw-DB residual needs the un-authorized schema origin column) and CONVERGENCE-cited
(see the summary). The matcher's `cash_oof_self_sourced_count` (in the run `summary_json`) is the
general-visibility mechanism for the unconstrained-input class.

## Round 8 — review-strong — CONVERGED (final state)

### Codex response (verbatim)
No critical or major defects found in this round. Reviewed in context: `schwab_reconciliation.py` (two-pass matcher, OOF skip placement, ref collision behavior, cash counters, swing-NLV arithmetic), `cash.py` (`insert_cash`/`find_by_ref` transaction behavior), `cli.py` (`journal cash`, new `journal oof-buy`, config override read, validation ordering, sandbox gate, idempotency belt), `config_overrides.py` (override materialization), `tos_import.py` (reserved `oof:` neutralization). The matcher branch is additive for production writers: numeric Schwab refs cannot collide with `oof:`, the OOF skip is gated by `withdraw` plus canonical sentinel plus declared ticker, and the OOF row no longer emits `cash_movement_mismatch`. The measurement arithmetic also holds: the cash withdrawal affects ledger equity, while `declared_oof_mv` is summed from broker positions, so both sides exclude the OOF holding after the row is recorded.

NO_NEW_CRITICAL_MAJOR
