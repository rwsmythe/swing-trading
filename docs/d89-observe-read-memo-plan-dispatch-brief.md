# D89 -- observe's per-detection read cost: WRITING-PLANS dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Authority:**
- **Operator, 2026-10-20, verbatim:** "D89 is approved, then soft-stop arc". This lifts the stop-engineering posture for D89 by name. The soft-stop arc (D84) follows it, and is not this cell's work.
- **The register row:** D89 in `docs/tool-director-context.md` (search `| D89`). Read it in full. Its "Binding form" is quoted in section 1 and binds.

**Cell:** `implementer-opus-xhigh`. This is writing-plans: a premise census, a measurement-neutrality design, and arithmetic for discriminating tests.

**KEEP YOUR READING NARROW.** Two earlier planning cells ran past the context cap by reading the whole comms record. Read ONLY:
- this brief;
- the D89 row;
- `docs/implementer-dispatch-recipe.md` section 3: the PLAN-STAGE PROTOCOL and the per-round assertions;
- the code named in section 2;
- for its form only, the maintenance rider's plan `docs/superpowers/plans/2026-10-20-maintenance-rider-d82-d83.plan.md`. It is the house shape of a converged plan, and its N-V neutrality test is the precedent for this one.

Do NOT read `comms/`, director state files, or other arcs' ledgers.

**Worktree:** create `C:\Users\rwsmy\swing-trading\.worktrees\d89-memo` on a new branch `d89-memo`, off main at the commit that carries this brief. Run everything from the worktree with `PYTHONPATH=.`. Live DB: `mode=ro` only; copies only by plain sqlite3 `backup`; NEVER through `swing`'s `connect`.

## 1. The work (the register row's binding form, verbatim)

> Binding form: observe's READ path, so the measurement-neutral obligation holds as for D83 — observation rows byte-equal with and without the memo, quoted; the memo is per-run (no cross-run state), keyed by ticker, and never outlives the step; a cache miss falls through to today's call. No tripwire unless a new module is proposed.

The lead, which is the round-0 cell's and not yet a ruling: a per-run, per-ticker memo of the resolved window, cutting about 7,177 calls to about 248 reads.

The first live bound, from run 195 with the D83 warm in place: about **64 ms per detection iteration**, an UPPER bound. That is the number to beat.

## 2. Code to read (and nothing wider unless a premise sends you there)

- `swing/pipeline/runner.py`:
  - `_bar_for_date` (about :3073-3135);
  - its call site in `_step_pattern_observe` (about :3255);
  - the loop around that call site.
- `swing/data/ohlcv_archive.py:resolve_ohlcv_window` (about :971), to know what it reads. It is under `swing/data`, so it is OUT of the envelope unless a fork is ruled.
- `swing/web/ohlcv_cache.py:get_or_fetch`: the populate step that runs before the read on every detection.
- The existing observe tests, `tests/pipeline/test_step_pattern_observe.py` and its conftest, plus the maintenance rider's N-V test `tests/pipeline/test_step_evaluate_warm_neutrality.py` as the neutrality precedent.

## 3. ROUND 0 FIRST: a premise and fork census, NO Codex, then STOP AND RETURN

Under recipe section 3 plan rule 1, do this before writing a plan.

**Re-derive, from the code and the live DB (`mode=ro`):**
1. Where the per-detection cost actually sits:
   - `resolve_ohlcv_window` itself, or the per-detection `get_or_fetch`, or the frame slicing that follows.
   - Measure it on COPIES of a few tickers' cache files in your scratchpad, never the live prices-cache. A copy of `swing.db` is allowed only through sqlite3 `backup`.
   - State the method.
2. The distinct-ticker count and detections per ticker for the newest run (run 195, observation_date 2026-10-19), from the live DB.

**Answer each of these and name it a FORK if the code does not settle it:**
- **(a) The memo key.** Within one run the observation_date is fixed (`lease_data_asof`). So is "keyed by ticker" sufficient, or does the key need the date and the window too? Prove it from the call sites.
- **(b) What is memoized.** The resolved FRAME plus its provenance (each detection still selects its own row), or the final bar dict per (ticker, date)? Both branches, with their neutrality argument.
- **(c) THE NEUTRALITY HAZARD.** Today every detection runs `get_or_fetch` before its read, so a transient populate failure on the first detection of a ticker can be healed by a later detection's populate in the same run. A memo that stores the FIRST read's result, including a `None` or an empty frame, would freeze that failure for every later detection of the ticker. That would be a behaviour change, not an accelerator.
  - State whether this can happen on the live code path.
  - Give the memo rule that keeps observation rows byte-equal, for example: memoize only a successful read, or only after a successful populate. Give both branches.
- **(d) Whether the per-detection `get_or_fetch` call stays per detection.** It is mostly an in-memory hit. Or does it collapse to once per ticker as well? What does each choice change?
- **(e) Envelope.** Whether the memo lives in `runner.py` only (no new module, no `swing/data` touch), and the exact functions it changes.
- **(f) The witness.** What the merge report quotes. Propose it the way CHARC's F8 was defined:
  - the observe step wall and the per-iteration remainder, against run 195's bound;
  - the number of `resolve_ohlcv_window` calls, if they can be counted without instrumenting production code;
  - how a Schwab-ladder-ON night reads.

**The census return lists:**
- every premise, verified or failed, with file:line;
- every fork, with BOTH branches;
- the measurements, with method and source;
- the evidence saved to `C:\Users\rwsmy\swing-data\review-transcripts\d89-memo\plan\round0\`.

**Then STOP AND RETURN.** I route the forks to their rulers. The plan and its review rounds come after the rulings, possibly in a continuation cell.

## 4. Later (for context only; do not start)

After the rulings, the plan follows the recipe's plan-stage protocol:
- `fast` tier;
- at most three counted rounds plus the self-sweep;
- a task ladder of about 1,000 lines or fewer;
- the ledger beside the plan; reviewers get rulings inlined or a cut ledger, never the round history.

Then a plan-stage director review, CHARC on form and RD on measurement neutrality, and then executing.

## 5. Gates and return

- Commits are conventional, pathspec-only.
- `%(trailers)` empty after each commit; no final `-m` paragraph begins with `Word:`.
- No Co-Authored-By, no `--no-verify`, no amend.
- No `swing/` change: this is planning.

**Return in chat only.** You NEVER post to a mailbox and never run `scripts/role_mail.py`. **If anything does not fit, STOP and return.** Do not choose for yourself.
