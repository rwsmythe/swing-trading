# D84 -- the capital soft-stop arc: WRITING-PLANS continuation brief, cell 2

**Audience:** a fresh implementer cell with no prior conversation context. You continue D84's writing-plans after round 0. Cell 1 ran the census and both directors have ruled every item.

**Authority:** unchanged and plans-only. The operator said "Stop before executing (Recommended)" on 2026-10-25. You write and converge the PLAN; you write no `swing/` or `tests/` code, and the arc stops for the operator before any executing cell.

**Cell:** `implementer-opus-xhigh`, kept by CHARC: E2's placement and the F1 affordance are still design inside the measured instrument.

## 0. Read ONLY these

1. `docs/d84-soft-stop-plan-dispatch-brief.md` (the original brief). Its section 3 (the plan) and section 4 (gates) still bind. Its section 2 (round 0) is DONE.
2. **The plan ledger, which is BINDING:** `docs/superpowers/plans/2026-10-26-d84-soft-stop.plan-ledger.md` on branch `d84-plan` at `c46c907f` or later. It block-quotes RD's rulings (`20261026T064737Z`) and CHARC's rulings (`20261026T065122Z`) in full. **The rulings govern. Where they differ from the proposal or the original brief, the rulings win.**
3. The round-0 census, for its file:line evidence: `C:\Users\rwsmy\swing-data\review-transcripts\d84-soft-stop\plan\round0\ruling-packet.md`.
4. `docs/implementer-dispatch-recipe.md` section 3.
5. The code the census and the rulings cite, as you need it.

Do NOT read `comms/`, the director state files, the proposal beyond what the rulings quote, or any other arc's ledger.

**Worktree:** the EXISTING `C:\Users\rwsmy\swing-trading\.worktrees\d84-plan`, branch `d84-plan`. It is clean at `c46c907f`. Run with `PYTHONPATH=.`. Read the live DB only on a `mode=ro` URI through plain `sqlite3`.

## 1. What the plan must carry (from the rulings; this list is a checklist, not a restatement)

**Front page:**
- **Tripwires:** the arc crosses the FIFTH tripwire (a `swing/trades` carve-out), AUTHORIZED by CHARC's S1 ruling and scoped to two tuples. There is NO migration anywhere in D84. Use CHARC's words; do not write "none".
- **The DECLARED LIMITATION on H4's evidence tier** under F1-A: H4 is an operator-asserted cohort. Carry RD's reason verbatim.
- **The operator-visible consequence:** every H4 fill takes the manual path (attest on the card, then the entry form), and the H4 label is the prefill's suggestion.
- **The grant:** plans only; the arc stops for the operator before executing.

**Tasks:**
- **S1:** the matcher change, the `DERIVATION_RULE_HISTORY` append and the digest constant land in ONE commit, under the pin test's same-commit rule. The version string's date is the MERGE's, so it is a named placeholder in the plan, filled at merge.
- **E2:** both the scoring predicate and its matcher adapter go into `DERIVATION_RULE_DEPENDENCIES`.
- **E1:** drop the `risk_results` parameter from `bucket_for`.
- **E2:** one layer-keyed risk-passes predicate beside `structural_gate_passes` in `scoring.py`, over a reduced form, with thin adapters. Propose exact names.
- **The old H4 form is DROPPED.** `_capital_blocked_match` becomes `aplus` AND risk non-pass.
- **E4:** the H4 label annotation, with the special-case branch in `_descriptive_label` DELETED.
- **F1-A, form conditions (1)-(5):**
  - the stated-zero heading and detail, with the derivation lines;
  - the new view-model attest affordance on a risk-withheld card. Verify, by reading 0033's CHECKs, that an `attest` row is writable on a latch with no `place` row, and say so;
  - `SizingResult.risk_per_share` as the ONE helper, with each surface naming its basis;
  - `_nightly_shares` mapping 0 to None;
  - the front-page consequence.
- **F3:** remove `risk_feasibility` from `STABLE_CRITERION_NAMES`. State the 30 rows / 12 tickers figure with its method.
- **F4:** prose only, at the named sites.
- **F6:** keep the L4 drop; the census's comment text is accepted.
- **E3:** RD's floor (1) plus (2), IN THIS ARC: one ASCII line shape from the one `SizingResult` field, at every named site. Each template site is pinned by a TestClient assertion.
- **#31 replacements** (never annotations): `scoring.py:13-16` and `:82-86`, the `_capital_blocked_match` docstring, `_descriptive_label`, `build.py:201`, `order_intent.py:463-467`, the `capital.py`/`metrics.py` docstrings, and the `research/harness/aplus_sensitivity/sweep.py` docstring (RD's exact replacement sentence, with a `<merge sha>` placeholder).
- **F2:** the bucket-population consumers whose membership moves, one line each, labelled a lower bound by grep. Also correct the proposal's "mandate shape check" consumer claim.

**Tests:**
- RED-first discriminators for acceptance (i), (ii), (iii) and (v).
- The REPLACED acceptance (iv): a pre-boundary-shaped candidate (`skip`, non-pass == {risk_feasibility}) matches NO hypothesis. Quote the measured zero in the docstring.
- The H4 positive pin uses the real KOD geometry.
- The inverted existing tests the census found, each superseded BY NAME with its reason.

**Not in the plan:**
- the unfloored entry-form sizing (BANKED; only its false-hint TEXT is in);
- F1-B (banked);
- the Finviz widening;
- any `hypothesis_status_history` row;
- any migration.

**Executing:** the plan is written for an `implementer-opus-high` executing cell, with an operator-witnessed browser step at the merge gate.

## 2. Rounds and gates

- The original brief's section 3 rounds rules bind: the `fast` tier with `-p fast`, and a missing profile FAILS LOUDLY.
- At most THREE counted Reviewer A rounds, then the uncounted self-sweep.
- The rulings go to Codex inlined, or as a ledger copy.
- Verdict tokens are described, never written line-initially.
- A per-item checklist; no prior-round reads.
- Every per-round assertion holds. Only the anchored verdict token with `^ERROR` = 0 proves a round finished.
- Save RESPONSES to `C:\Users\rwsmy\swing-data\review-transcripts\d84-soft-stop\plan\round<N>\`.
- **STOP AND RETURN at EVERY counted round gate** with its ledger row, leaving the depth column empty.
- Commit the plan ONCE, at convergence (the original brief's rule). The per-round ledger rows ride in that commit.
- Pathspec commits, `%(trailers)` empty, no amend.
- **Return in chat only.** You never post to a mailbox and never run `scripts/role_mail.py`.
- **If a ruling cannot be carried as written, or a new fork appears: STOP and return with both branches.** A fork found mid-loop stops the loop.
