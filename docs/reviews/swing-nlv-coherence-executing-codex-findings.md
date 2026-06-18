# Codex review-strong findings — swing-NLV coherence (SPCX §2.4)

Tier: review-strong (profile present: gpt-5.5, model_reasoning_effort=high).
Transport: WSL-native Codex CLI 0.135.0, `-p review-strong -s read-only
--skip-git-repo-check`, repo-access (cwd = worktree) + stdin bundle (prompt +
diff + the C1 read-path excerpts from pipeline_steps.py + mappers.py).
Base: main (2d2e0b40).

---

## Round 1

### Codex response (verbatim, from .codex-review-r1.txt)

Header: `model: gpt-5.5 ... reasoning effort: high`.

**MAJOR: non-finite `ledger_equity` can produce a false coherent log and then
crash hydration.** Step 8 validates `source_nlv` and declared MV, but not
`ledger_equity`. If `starting_equity` is `nan`/`inf` or a persisted cash/realized
component is non-finite, `current_equity` propagates it. Then `eval_delta` becomes
non-finite, the fire predicate can evaluate false for `nan`, and the new coherent
log emits "coherent" without a valid finite comparison. Completion then stamps
`account_equity_journal_dollars=ledger_equity`, so `ReconciliationRun.__post_init__`
rejects the row on `get_run`. No write boundary prevents `cfg.account.starting_equity`
from being non-finite; `Account` has no finiteness validator. Fix: require finite
`ledger_equity` before fire/log/JSON/stamping.

**MAJOR: non-finite `source_nlv` is still stamped into the initial run row before
the new normalization exists.** `source_nlv` is computed raw, then inserted into
`account_equity_source_dollars` at the run-row INSERT. The new `finite_source_nlv`
normalization is not computed until step 8. On the happy completion path it gets
overwritten with `None`, but if any post-insert exception is preserved via the
failure path, `update_run_failed` only changes state/error fields and leaves the
non-finite source column intact -> `get_run`/`list_recent_runs` hydrate-crash on
that failed row. Normalize before `insert_run`, or ensure the failure update also
clears/normalizes these equity columns.

Confirmed otherwise: the swing MV sum reads `schwab_positions` from the SAME
`schwab_account` object as `source_nlv`; no second account-details fetch in the
production read path (C1 OK). The declared MV guard does not coerce
missing/non-numeric/non-finite values to zero in step 8 (C2 OK). For finite legacy
inputs, C3 shape is preserved: no swing log, `basis:"net_liq"`, no `summary_json`
key.

VERDICT: NEW_MAJOR: non-finite `ledger_equity` false-coherent/crash path;
non-finite `source_nlv` still persisted on failed run rows.

### Adjudication

Both MAJORs ACCEPTED and FIXED (both are reachable: `cfg.account.starting_equity`
has no finiteness validator — Codex verified `Account` has none — and the Schwab
mapper does `float(nlv)` with no finiteness check, so a non-finite NLV/ledger is
genuinely reachable, not schema-prevented; the recipe's schema-prevented-value
carve-out does NOT apply).

- **MAJOR 1 (non-finite ledger):** ACCEPTED. My change introduced a NEW
  false-coherent LOG surface (the coherent log would emit on a `nan` ledger) and
  the completion stamp of `account_equity_journal_dollars=ledger_equity` would
  crash `__post_init__` at read-back (pre-existing, but my test claimed "run
  completes"). FIX (in step 8): added `finite_ledger_equity = ledger_equity if
  math.isfinite(ledger_equity) else None`; gated `swing_nlv_computable` and the
  coherence computation/fire/log on it; the eval delta + the fired
  `expected_value_json` + the coherent log all use `finite_ledger_equity`; the
  completion stamp uses `finite_ledger_equity` (None on non-finite). New test
  `test_nonfinite_ledger_degrades_no_fire_no_log` (non-finite starting_equity ->
  run completes, no fire, no log, NULL journal stamp).

- **MAJOR 2 (failed-run row preserves a non-finite source):** ACCEPTED. The
  run-row INSERT stamped raw `source_nlv`; on a failure path the row is preserved
  by `update_run_failed` (which does not clear equity columns) -> a later
  `get_run`/`list_recent_runs` of that failed row crashes on a non-finite source.
  FIX: moved the `finite_source_nlv` normalization UP to immediately after the
  `source_nlv` definition (pre-BEGIN) so the run-row INSERT, the completion stamp,
  AND step 8 all share the single normalized value (None on non-finite). This is
  the single-source-of-truth fix. SCOPE NOTE: the literal dispatch scope said
  "step 8 ONLY"; this fix also touches the `source_nlv` definition (~:1252) + the
  run-row INSERT stamp (~:1313) — SAME file, SAME function, a minimal
  finiteness-degrade that changes NO finite-value behavior and directly serves the
  plan's "no stamped column carries non-finite / run completes instead of crashes"
  contract. FLAGGED in the return report for orchestrator/RD review rather than
  silently absorbed. (A forced-failure test for the preserved failed-row is
  impractical without a fault-injection seam; the structural fix — INSERT stamps
  finite — closes it; the completed-path non-finite-NLV test covers read-back
  safety.)

C1 / C2 / C3 explicitly CONFIRMED by Codex — no change needed there.

---

## Round 2

### Codex response (verbatim tail, from .codex-review-r2.txt)

Header: `model: gpt-5.5 ... reasoning effort: high`.

No critical/major findings.

Confirmed against the code paths:
- C1 same-snapshot holds: production makes one `get_account_details(...)` call and
  passes `details` into `run_schwab_reconciliation`; mapper fills both
  `net_liquidating_value` and `positions` from that one response.
- C2 holds in step 8: declared MV None, non-numeric, or non-finite sets
  `declared_mv_available=False`, then `eval_nlv/eval_delta=None`, so no fire and no
  swing-coherent log.
- Non-finite source NLV and ledger are normalized before run-row stamps and emitted
  JSON, so no stamped equity column carries NaN/inf.
- C3 legacy behavior holds for no declared/held position: `broker_flat_swing`
  reduces to legacy broker-flat, basis remains `"net_liq"`, and the legacy emitted
  JSON shape is unchanged for finite inputs.
- Fire/log paths are mutually exclusive via `fired`, and the coherent log is gated
  only on swing-scoped computability plus flat-for-swing.

Minor note: swing-scoped fired `actual_value_json` no longer includes
`equity_dollars`, so the existing generic equity-delta side-by-side renderer will
show the actual side as blank unless it is taught `swing_nlv`. The raw JSON and
`delta_text` still carry the values, so I do not classify this as a
correctness/safety blocker under the stated contract.

NO_NEW_CRITICAL_MAJOR

### Adjudication

CONVERGED at Round 2: `NO_NEW_CRITICAL_MAJOR`. Both R1 MAJORs verified fixed; C1,
C2, C3, finite-stamp, and fire/log mutual-exclusivity all explicitly confirmed.

MINOR (renderer blank-actual on a swing-scoped fire) — ADJUDICATED OUT-OF-SCOPE,
NOT FIXED. `swing/trades/reconciliation_render.py:_pairs_equity_delta` reads
`actual.get("equity_dollars")` (a `.get`, returns None -> blank, NO crash; the
existing `test_equity_delta_render_tolerates_basis_keys` confirms no crash on basis
keys). The swing-scoped fire's `expected_value_json` still carries
`{"equity_dollars": ..., "basis": "ledger"}` so `expected["equity_dollars"]` does
NOT KeyError. The "schwab/actual" cell renders blank for a swing-scoped fire; the
raw JSON + `delta_text` (`$X (ledger minus swing_nlv)`) carry the values. This is a
DOWNSTREAM display nicety in a file OUTSIDE the authorized step-8-only scope
(recipe §5: flag, never fix inline). FLAGGED in the return report for orchestrator
/RD to decide a follow-up (teach `_pairs_equity_delta` the `swing_nlv` key). The
mandated swing-scoped `actual_value_json` shape (plan §2.4) is correct as shipped;
this is purely the renderer's pair-extractor not yet knowing the new key.
