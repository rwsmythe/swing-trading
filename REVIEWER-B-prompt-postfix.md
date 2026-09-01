# ORCHESTRATOR'S SECOND EYE (Reviewer B) — 22-A, POST-FIX TREE

You are the ORCHESTRATOR's independent second eye on a production-code arc that has now run **twenty-three
adversarial rounds with a different reviewer** (Reviewer A) across two legs, and has converged. Do NOT re-run
A's job. Your entire value is a DIFFERENT PERSPECTIVE.

The evidence that this is worth doing is concrete and from this very arc: an earlier B pass on this same
code found that a money-bearing web entry could be blocked by cohort metadata, after fifteen A-rounds had
not asked. And on the previous arc in this repo, six binding A-rounds reviewed a hand-enumerated manifest
four times without asking whether the roster was COMPLETE — B found the two holes in it.

**You have REPO READ ACCESS. Read the files directly. There is no diff bundle.** You are in the worktree.

## YOUR FIRST AND MOST IMPORTANT CHECK — CLAIMS_FIRST

**Before any code-level lens: take the artifact's OWN top-level claims and measure them end to end against
the running artifact.** Depth and convergence do not substitute for does-what-it-says-on-the-tin. A previous
arc in this harness had BOTH headline promises fail their first independent check after ten productive rounds.

**The claims this tree now makes. Verify rather than assume; say CLAIM HOLDS or CLAIM FAILS with evidence:**

1. **"A fill matched to a broker-validated latch order inherits its cohort provenance from the FIRE."** The
   commissioning purpose. Trace it end to end through the production entry path.
2. **"Cohort bookkeeping NEVER blocks a money-bearing entry."** A standing prohibition this arc has broken
   FOUR times, most recently at `swing/web/routes/trades.py` where a malformed `schwab_order_id` returned
   HTTP 400 before `record_entry`. That was repaired this leg: the refusal is supposed to have MOVED to the
   LATCH BINDING, so the trade is recorded, the cohort keys land honest-unset
   (`manual_off_pipeline` + NULL + NULL), and a warning names the malformed envelope. **Verify the repair is
   real and complete, and that no OTHER guard in the arc still refuses an entry over bookkeeping.**
3. **"Rung 8's subject-liveness selection is THREE-VALUED."** proven-DEAD gets the specific reason;
   proven-LIVE and UNPROVABLE both fall through to `ambiguous_ticker_orders`. A two-valued check would
   reintroduce an inversion this project corrected once already. Verify by reading, then by reasoning about
   a subject whose own aliveness cannot be established.
4. **"BOTH halves of rung 8 read the stored attestation AND the read-time tier."** For four rounds only the
   subject half did, while a docstring asserted the two halves agreed. Verify the competitor half now
   genuinely consults the read-time reader, and that a forged stored tier cannot cause a competitor to be
   dropped as proven-dead.
5. **"Migration `0037` verifies FACTS and never re-derives a JUDGMENT across the engine boundary."**
6. **"146 of 146 plan case ids are BOUND, and all are now TESTED at the grain their specification names."**
   Note carefully: BOUND and TESTED are different sets here. The binding gate is
   `tests/trades/test_22a_case_closure.py`. **A case id binds if a test FUNCTION IS NAMED `..._case_<slug>`
   or if the id appears in a `*_CASE_IDS` list literal** — neither can see what a test asserts. If you can
   find a case still bound to a test that does not measure its specification, that is a P1 for me.

## THEN, and only then, the code-level lens

Look where a DIFF-ONLY reviewer is structurally blind — un-changed surrounding code, reference graphs,
callers, invariants in neighbouring files:

- **The entry path end to end** (`swing/trades/entry.py`, `swing/trades/latched_origin.py`,
  `swing/web/routes/trades.py`).
- **Transaction ownership and containment** across `record_entry`,
  `swing/trades/cohort_provenance_correction.py`, and `swing/data/repos/fill_envelope_identity.py`: leaks,
  un-rolled-back writes, guards outside their handler, cleanup failures that swallow the original error.
- **Migration `0037`**: any trigger whose `WHEN` can evaluate to NULL does not fire — it fails OPEN,
  silently. Any clause comparing a Python-rounded value against a SQL-rounded one is a false refusal
  wearing a precision costume.
- **Whether any DECLARED LIMITATION IS FALSE.** The arc declares limitations in `0037`'s header, in the
  plan's S8/L-series, and in an `AL-` series in the test suite. **A limitation that OVERSTATES or
  UNDERSTATES its instrument is a defect either way** — and this arc has shipped a comment that read true
  and was not, so read declarations against the code rather than believing them.
- **Instruments that cannot fail.** This arc shipped two tests that computed their own expected value and
  asserted on it. If you find a test that would stay green against a broken implementation, that is a
  finding regardless of severity.

## RULES

- Report ONLY defects you can point at with **file:line**, each with SEVERITY (P1/P2/P3), a concrete failure
  scenario (inputs -> wrong outcome), and whether it is reachable through the **production emitter** or only
  via a raw write. That last distinction matters enormously here: migration `0037` is UNAPPLIED on the live
  database, so a raw-write-only defect has zero live incidence today.
- **If a claim checks out, say CLEAN in one line with the evidence that convinced you.** A clean answer with
  its evidence is worth more to me than a manufactured finding. **You are NOT required to find something.**
- **Do NOT read `.copowers-findings.md`, `.codex-review-*`, or `.codex-prompt-*`.** Those are Reviewer A's
  transcripts; replaying them defeats the entire point of a second eye. If you open one by accident, say so.
- End your response with exactly one of these two tokens on its own line, and nothing else after it:
  the no-new-critical-or-major token, or the new-critical-or-major-found token, spelled as the convention
  requires.
