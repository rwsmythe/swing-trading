# D79: the exit form records the SELECTED broker order's fill, once -- WRITING-PLANS dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Mission.** Write the implementation PLAN for D79, encoding the rulings already landed, and run it through the plan-stage review protocol. **This dispatch is PLAN ONLY.** You write no production code and make no production commits. Executing is a separate dispatch that needs a separate word from the operator.

**Authority (operator, verbatim):** 2026-10-19 "dispatch D79". This follows the 2026-10-18 round-0 go. It covers this writing-plans dispatch ONLY.

**Base:** `main` @ the commit that adds this brief. **Worktree:** `.worktrees/d79-plan`, branch `d79-plan`. The orchestrator cuts it, so do not create it; `cd` into it and work there. The base carries every rule this brief names: recipe section 3's plan-stage protocol, the banner assertions, copy-per-round preservation and return-at-each-round-gate.

**Cell:** `implementer-opus-high`, the writing-plans default.

## 0. Read first, in this order

1. `docs/implementer-dispatch-recipe.md` in full, and `CLAUDE.md`. Recipe section 3's **PLAN-STAGE PROTOCOL binds** (rules 1-5).
2. **The rulings, which are BINDING:** `docs/superpowers/plans/2026-10-19-d79-exit-identity.plan-ledger.md`. It holds every round-0 item ruled by its one ruler: RD on K2, K3, K5c, K7.1 and K7.2; CHARC on K1 and K6, including the scoped `swing/trades/exit.py` carve-out and CHARC's required K1 test shapes (i)-(v); the orchestrator on K4, K5 and K7.3-5. Read every word.
3. **The round-0 record:** `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\round0\return-report.md` (re-set, not verbatim). Its probes (`test_d79_round0_probe.py`, `test_d79_round0_item4_probe.py`) and `probe_*.json` are beside it. The probes reproduce F2-A, F2-B and F1 through the real route, so reuse their fixture shapes.
4. **The round-0 brief, for context only:** `docs/d79-exit-order-identity-brief.md`. **Two of its statements are SUPERSEDED:**
   - its citation `swing/integrations/schwab/trader.py:_compute_signature_hash` is WRONG; the exit candidate hash is `swing/trades/exit_auto_fill.py` (function ~:1652-1691, the call ~:1234);
   - its "Codex at `strong`" for the plan is replaced by recipe rule 5: plan rounds run at `fast`.

## 1. The ruling intake check (recipe rule 1, last paragraph): do it FIRST

The rulings' REASONING binds. Their incidental FACTS are inputs you verify against the code before you encode them: line numbers, symbol names, caller counts, the claim that `_handle_split_into_partials` never calls `record_exit`, and the claim that both `record_exit` callers enter with no open transaction.
- If a fact is wrong, encode the code's fact and report "the ruling named X; the code has Y; encoded Y".
- **If verifying a fact OPENS A FORK** (a ruling cannot be encoded as written, or two rulings conflict on the code), STOP before any review round and return the fork with both branches specified. No round runs while a ruling is outstanding.

## 2. The plan

Write `docs/superpowers/plans/2026-10-19-d79-exit-identity.plan.md`.
- **Form:** a TASK LADDER and a TEST ROSTER, **capped at ~1,000 lines** (rule 2). Reasoning, rulings and review history live in the ledger, not the plan. Cite the ledger's sections instead of restating them.
- **Each task gives:** the files and symbols it touches; its RED test(s), with the pre-fix and post-fix arithmetic (the recipe's section 2 rule: a test that passes under both is worthless); and the null implementation each test kills.
- **The test roster MUST include:**
  - CHARC's K1 discriminators (i)-(v), as worded in the ledger;
  - the round-0 cell's list (record, "The cell's test list"), mapped onto the RULED shapes. Item 4 is now "same id, different signature -> REFUSED"; item 12 is in scope, because K7.1 ruled GLOBAL;
  - the orchestrator's K7.3 tests (unconfirmed contradiction writes nothing; the top-level id is the SELECTED one);
  - RD K3 precondition (4), which makes the single-candidate shape stamp `selected_*`;
  - the K5 confirm bound to its acknowledged flags (an unacknowledged flag re-asks; a d2 world change voids the confirmation);
  - K7.5's ASCII assertion over the flag-text constants;
  - the split-handler pin (test 11).
- **Supersession by replacement:** the retention-rule rationale block (RD K3) and the `_exit_candidates_maps_equal` docstring (K7.4) are rewritten in the task that makes their new text true. Name that task.
- **Executing posture to state in the plan:**
  - the full fast suite runs before AND after the executing review;
  - the executing review tier is `strong`, with repo access (production code);
  - the arc ends in an OPERATOR-WITNESSED browser check on a scratch DB copy, which is binding for HTMX form work. The witness includes CHARC's census query (linked exit fills grouped by extracted id with count > 1, excluding split-partial provenance; only the known partial sets are expected).
- **Declared envelope (state it in the plan header; the review prompt TAGS findings outside it):**
  - **IN:** the exit POST route, `swing/web/routes/trades.py`, and its re-render helpers; `swing/trades/exit_auto_fill.py` (flags, `possible_duplicates` reason labels); the exit form VM's exclusion (`swing/web/view_models/trades.py`); the exit form template; `swing/trades/exit.py:record_exit`, EXACTLY the CHARC K1 carve-out (transaction shape, identity lookup, typed refusal); the CLI `trade exit` confirm flag and the `ClickException` wrap.
  - **OUT:** anything under `swing/data/`; `insert_fill_with_event`; the split handler; the ENTRY path; ANY schema or migration (K6 ruled against); a duplicate-id monitor (banked); a JS refill, `hx-get`, or a "use these values" button (K4); backfilling 22-A readings on exit fills.
- **Accepted limitations, each WITH its reason (the review prompt carries them and invites challenge):**
  - no schema backstop (CHARC K6: there is no column, `json_extract` is a different reader, and split partials legitimately share an id);
  - F1 is checked in the route, not the service (CHARC K1: the service never sees what the form showed);
  - no client-side refill (K4: no JS harness; the server check is the barrier);
  - 13 exit fills have no stored 22-A reading (round 0; the guard reads the raw envelope through `canonical_envelope_identity`, per RD K2).

## 3. Review (recipe section 3 + plan-stage rules 3-5)

- **Tier:** `fast` profile. Assert the banner model equals the `model =` line in `~/.codex/fast.config.toml`. No `-p` fallback. The five per-round assertions bind.
- **Rounds:**
  - **AT MOST THREE COUNTED rounds;** stop at the FIRST round with zero TASK-BEARING findings.
  - Classify every finding as task-bearing (changes a task, a test or the envelope) or instrument. Report both the reviewer's severity and your class. A contested class counts as task-bearing.
  - After the last round, do an uncounted self-sweep (SS-N ids) over the whole plan for residuals of your own fixes.
  - A fourth round needs the orchestrator's written authorization.
- **The prompt carries:** the envelope and the accepted limitations above; a prohibition on reading prior-round findings; and the two-token verdict as the response's final line. Describe the tokens; never write either one line-initially in the prompt.
- **Scratch:** relocate `.codex-*` and `.copowers-findings.md` to the session scratchpad during the loop, and restore them at the end (the recipe's default).
- **Evidence:**
  - copy each round's transcript, prompt and findings to `C:\Users\rwsmy\swing-data\review-transcripts\d79-exit-identity\plan\` the moment the assertions pass;
  - append the cumulative round table and every finding's adjudication to the COMMITTED ledger `docs/superpowers/plans/2026-10-19-d79-exit-identity.plan-ledger.md`, in a new section "Plan review". This is that existing file, not a second ledger. **Never edit the block-quoted ruling sections.**
- **STOP AND RETURN AT EACH COUNTED-ROUND GATE.** Do that once the round's evidence is copied and the ledger row is committed. Your final message is the round's ledger row. The orchestrator reads your depth and resumes you.
- **Commits:**
  - the plan is committed ONCE, at convergence (`docs(plan): ...`), and ledger rows are committed per round;
  - commit with bare git from the worktree cwd;
  - no `Co-Authored-By`, `--no-verify` or amend; keep the final `-m` paragraph plain prose;
  - before return, `git log <base>..HEAD --format='%H%n%(trailers)'` must be empty for every commit.

## 4. Return report (your final chat message, to the orchestrator only; NEVER post to any mailbox)

- The intake-check results (each verified fact, each correction).
- The plan path, its line count, and the task and test counts.
- The round ledger: per round, the asserted model, effort, footer and verdict token; the findings by class; the `tokens used` sum (the spend line).
- The self-sweep findings.
- Every follow-on with an explicit disposition (COMMISSIONED / BANKED with owner and trigger / DECLINED with ground).
- Your recommendation for the EXECUTING cell (model and effort), with a one-line reason.

## 5. If you get stuck

- **Do not open or write the live DB** except `mode=ro` reads.
- **STOP and return** if:
  - a premise or ruling does not match the code in a way that opens a fork;
  - the plan cannot fit ~1,000 lines (then it is two arcs; propose the split);
  - the `fast` profile does not resolve.
