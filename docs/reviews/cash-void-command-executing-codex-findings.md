# Codex review transcript — `swing journal cash-void` (Phase-18 D19), executing

Review tier: `review-strong` (gpt-5.5-class, `model_reasoning_effort=high`), repo-access
(cwd = worktree, `-s read-only`). Base = `6872606a`. Liveness: codex-cli 0.135.0.

---

## Round 1

### Codex response (verbatim findings + verdict)

[MAJOR] swing/integrations/schwab/models.py:364 — The three-prefix collision proof is not
enforced. `SchwabTransactionResponse.transaction_id` only has to be a non-empty string, and the
mapper casts arbitrary `transactionId`/`activityId` via `str(...)` at mappers.py:605. Step 7 then
exact-ref matches before the void skip at schwab_reconciliation.py:1948, so an
upstream/non-realistic-but-accepted transaction id like `void:5` can consume a void row in PASS 1
or cause a ref-mismatch emit. Step 6.5 also `find_by_ref(tx_id)` before insert, so a real cash
transaction with `tx_id == "void:5"` would be silently deduped against the void row. Concrete fix:
enforce `transaction_id` as `^[0-9]+$` in the Schwab mapper/model boundary and update
tests/fixtures to numeric ids, or explicitly exclude sentinel-shaped refs from Schwab
transaction-id matching/dedup if arbitrary string ids must remain supported.

[MAJOR] swing/cli.py:2167 — `cash-void` copies `original.amount` into the reversing row with no
finite/positive guard. This is not schema-prevented: migration 0029 only has `amount REAL NOT NULL
CHECK (amount >= 0)` at 0029_cash_reconciliation.sql:18, which does not reject `+inf`, and
`CashMovement.__post_init__` has no amount validation. A reachable original can come from
`journal cash`, whose only amount guard is `amount <= 0` at cli.py:1729; `inf` passes. Voiding an
infinite withdraw with an infinite deposit produces `-inf + inf == NaN` in `net_cash_movements` at
equity.py:25, so `current_equity` is not restored and the reconciliation equity check normalizes
the poisoned ledger to `None`, suppressing the signal. Concrete fix: add `math.isfinite(...) and
original.amount > 0` validation before deriving/writing the void, fail loud if violated, and add
the same finite guard to `journal cash` to stop future poisoned originals.

Verdict: NEW_CRITICAL_MAJOR_FOUND

### Adjudication

**MAJOR 1 (transaction_id `^[0-9]+$` not enforced) — ADJUDICATED OUT-OF-SCOPE FOR THIS ARC +
FLAGGED to the orchestrator (recipe §5 stop-and-flag, NOT worked around).** Reasons:
  1. **Not a new defect; a PRE-EXISTING, OOF-SHARED property.** `SchwabTransactionResponse`
     (`models.py:357,363-367`) requires `transaction_id` be a non-empty STRING only — it has
     never been constrained to `^[0-9]+$`, and that model was last touched by the Schwab bundle
     (`7797ceb9`/`45157978`/…), NOT by the OOF arc NOR this arc. The merged OOF arc's `oof:`
     collision proof (`schwab_reconciliation.py:218-224`) relies on the EXACT same un-enforced
     "Schwab transaction_ids are numeric [0-9]+" assumption. So a `void:`-shaped (or `oof:`-shaped)
     `transactionId` from a garbage/adversarial upstream is a pre-existing system property; the
     void arc does not introduce or worsen it (it adds a THIRD disjoint prefix that is symmetric
     with the OOF prefix).
  2. **The prescribed fix is a THIRD carve-out my brief FORBIDS.** Enforcing `^[0-9]+$` at
     `swing/integrations/schwab/models.py`/`mappers.py` is a new edit to the Schwab-integration
     boundary (a distinct `swing/` module, not one of my TWO authorized carve-outs), changes
     `SchwabTransactionResponse` validation behaviour across the WHOLE reconciliation system, and
     would require updating fixtures repo-wide. The brief is explicit: "EXACTLY TWO additive
     carve-outs … NO THIRD carve-out. If the design needs … a third carve-out … STOP and surface
     it (recipe §5) — do NOT work around it." This is therefore flagged up, not self-fixed.
  3. **Reachability is non-real-world.** Real Schwab `transactionId`/`activityId` values are large
     numeric strings (the captured spec example `"115520131470"`); a colon-prefixed `void:5`/`oof:…`
     id is not producible by the live broker. The §2.3 collision proof holds for every real input.
  Disposition: out-of-scope for the void arc; FLAGGED to the orchestrator/CHARC as an
  OOF-symmetric, system-wide hardening candidate (a single `^[0-9]+$` constraint at the Schwab
  txn-id boundary would close it for BOTH the oof: and void: sentinels at once). NOT a void-arc
  regression; does NOT block this merge on its own.

**MAJOR 2 (non-finite `original.amount` poisons the void) — ACCEPTED + FIXED in scope.** This is a
genuine, void-SPECIFIC, reachable measurement-core defect: `journal cash --withdraw inf` passes
(`inf <= 0` is False), `CashMovement.__post_init__` has no amount validation, the `amount >= 0`
CHECK accepts `+inf`, and voiding an inf-withdraw with an inf-deposit yields `-inf + inf = NaN` in
`net_cash_movements` -> `current_equity` is NOT restored and the coherence eval is suppressed (the
opposite of a trustworthy signal). This is the SAME finding the OOF arc itself fixed at the same
layer (oof-buy's `if not math.isfinite(cost) or cost <= 0` guard, its Codex R1-MAJOR-2). The fix
is entirely within my authorized `swing/cli.py` cash-void command (NO new carve-out): a finiteness
+ positivity guard on `original.amount` BEFORE deriving the reversing row, failing loud. I do NOT
add the guard to `journal cash` (that is a separate pre-existing command outside my arc's task
scope; flagged as a parallel hardening candidate, but the void command's own guard fully closes
the void-arc vector — a non-finite original is rejected at void time). Test: R1-FIX (a void of a
non-finite-amount original -> ClickException, no void row).

---

## Round 2 (re-review on the R1-fixed diff)

### Codex response (verbatim findings + verdict)

No [CRITICAL] or [MAJOR] findings.

[MINOR] swing/trades/schwab_reconciliation.py:389 — `_VOID_REF_RE` accepts `void:0` and
`void:0005`, but `_build_void_ref()` rejects non-positive ids and never emits leading zero ids.
That widens the self-sourced skip beyond the constructor's domain. Fix by aligning the predicate
with the builder, e.g. `re.compile(r"^void:[1-9]\d*$")`, and add tests that `void:0` / `void:0005`
are not sentinels.

R1 MAJOR 2 is fixed for the void path: `journal_cash_void_cmd` rejects non-finite or non-positive
`original.amount` before deriving the reversing kind/ref or calling `insert_cash`, so the void
command cannot copy `inf` into a reversing row.

Verdict: NO_NEW_CRITICAL_MAJOR

### Adjudication

- **R1 MAJOR 2: confirmed FIXED by Codex** (the void path cannot copy `inf` into a reversing row).
- **R1 MAJOR 1: NOT re-raised as a new critical/major** — Codex accepted the round-1 disposition
  (out-of-scope for this arc + flagged upstream). Stays flagged to the orchestrator/CHARC.
- **R2 MINOR (predicate domain wider than the constructor): ACCEPTED + FIXED.** Although a MINOR
  and non-blocking, it is a clean defense-in-depth tightening of the canonical-shape predicate --
  exactly the OOF R1 canonical-shape lesson (the predicate must accept EXACTLY the domain the
  constructor can emit). `_build_void_ref` rejects id<1 and `int()` never emits leading zeros, so
  the matcher should never recognize `void:0`/`void:0005` as self-sourced. Tighten `_VOID_REF_RE`
  to `^void:[1-9]\d*$` and add C2-V assertions that `void:0` / `void:0005` are NOT sentinels.

Verdict: review-strong CONVERGED at Round 2 (NO_NEW_CRITICAL_MAJOR; one MINOR taken).

---

## Round 3 (confirm pass on the R2-MINOR-fixed diff)

### Codex response (verbatim findings + verdict)

No [CRITICAL] or [MAJOR] findings.

[MINOR] tests/cli/test_cash_void_command.py:3, tests/trades/test_cash_void.py:3, swing/cli.py:2057,
swing/trades/schwab_reconciliation.py:364 — Added cash-void comments/docstrings still contain
non-ASCII markers (section sign, em dash). Runtime behavior is unaffected, but it violates the
stated ASCII-only binding if interpreted literally. Fix: replace the section sign with "section",
em dashes with "--".

Verdict: NO_NEW_CRITICAL_MAJOR

### Adjudication

- **review-strong CONFIRMED converged** — the R2 MINOR fix introduced no new critical/major; no new
  blocking finding across two consecutive rounds.
- **R3 MINOR (non-ASCII in comments/docstrings): ACCEPTED + FIXED.** Codex itself notes "Runtime
  behavior is unaffected" — the glyphs are in COMMENTS / DOCSTRINGS / section banners, never in a
  user-facing stdout string (every click.echo / ClickException message I added was already pure
  ASCII; the cp1252 crash risk is a RUNTIME-stdout concern). Still, swept the section-sign +
  em-dash out of my added comments so the arc's diff is literally ASCII end-to-end (cosmetic,
  zero behavior change).

Verdict: review-strong CONVERGED (NO_NEW_CRITICAL_MAJOR across R2 + R3; both MINORs taken).

---

## codex-auto-review (complementary second eye; gpt-5.5, model_reasoning_effort=high, repo-access)

Invocation: `codex exec review --base main -c model_reasoning_effort=high` from the worktree
(cwd = repo, `-s read-only` by the review subcommand). The worktree `.git` was temporarily
re-pointed to the WSL-resolvable `/mnt/c/...` gitdir + WSL git `core.autocrlf=false`/`core.fileMode=false`
set for the review (else WSL renormalizes CRLF and the diff explodes to the whole tree); BOTH
restored afterwards (Windows `.git` pointer + WSL global config back to pre-run UNSET).

### Codex response (verbatim)

> The new cash-void command, repository helper, reserved ref handling, and reconciliation skip
> appear consistent with the intended append-only reversing-entry workflow. I did not identify a
> discrete introduced bug that would break existing behavior or the new feature.

(It grepped the surrounding code — ran `rg _OOF_REF_RE`, read the recon module / the orphan pass /
the step-7 loop — i.e. it read BEYOND the diff, the repo-access requirement.)

### Adjudication

- **codex-auto-review: CLEAN (no findings).** Disjoint-but-complementary to review-strong (it
  re-confirmed the matcher skip + reserved-ref handling + the append-only reversing-entry workflow
  with repo access). No B `major`/`[P1]` to adjudicate. Model = gpt-5.5, effort = high (the
  matched-HIGH requirement; NOT effort=none).

## Overall convergence

- **review-strong:** R1 (2 MAJOR: M2 fixed in scope; M1 adjudicated out-of-scope + flagged) ->
  R2 (NO_NEW_CRITICAL_MAJOR, 1 MINOR taken) -> R3 confirm (NO_NEW_CRITICAL_MAJOR, 1 MINOR taken).
- **codex-auto-review:** clean (no findings).
- **One item FLAGGED to the orchestrator/CHARC (not fixed, recipe §5):** R1 MAJOR 1 — enforce
  `^[0-9]+$` on `SchwabTransactionResponse.transaction_id` at the Schwab model/mapper boundary.
  Pre-existing + OOF-symmetric; the prescribed fix is a THIRD carve-out the brief forbids;
  non-real-world reachability. A single boundary constraint would close it for BOTH the oof: and
  void: sentinels at once.
