# D84 -- the capital SOFT-STOP arc (risk as a flag, not a gate): WRITING-PLANS dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Authority (a plans-only grant; read the limits):**
- **Operator, 2026-10-19:** RD's proposal approved ("Work on both may begin as conditions support").
- **Operator, 2026-10-25:** the hold is lifted. For D84 his choice was **"Stop before executing (Recommended)"**. The grant therefore covers brainstorm, writing-plans and the plan-stage director review, and NOTHING after them. Recorded in the orchestrator handoff at `7c54bca0` section 2 and carried by CHARC at `d9c9f149`.
- **The commissioning brief is RD's proposal** `docs/rd-proposal-soft-stop-arc-screen-widening-rider.md` @ `b266cc97`, sections 1, 2, 3 and 6. **Section 4 (the Finviz widening) is NOT yours.** It is an operator config edit made after the merge. Section 5 is a closed rider.
- **CHARC's dispatch** (BINDING on form): `comms/orchestrator/read/20261025T164200Z-charc-d84-opens-hold-lifted-2026-10-25-plan-lo.md`, items F1-F6. Its reading of "proceed" as end to end was WITHDRAWN; the operator's stop-before-executing governs.
- **RD's pre-formed views** (to be RULED at the packet, not yet rulings): the bullet beginning `**D84 PRE-FORMED VIEWS` in `docs/rd-state.md` section 5, items (i)-(vi).
- **The register row** is D84 in `docs/tool-director-context.md` (search `| D84`).

**Cell:** `implementer-opus-xhigh`. CHARC named the reason: there is an open design fork inside the measured instrument (F1, the zero-share shape), and F5 is a read that can look conclusive and be wrong.

**KEEP YOUR READING NARROW.** Two planning cells have died past 400K reading the comms record. Read ONLY these:
- this brief;
- the proposal (sections above), CHARC's dispatch mail, RD's one `rd-state.md` bullet, and the D84 register row;
- `docs/implementer-dispatch-recipe.md` section 3 (the plan-stage protocol and the per-round assertions);
- the code in section 1.

Do NOT read any other `comms/` file, director state file outside the one bullet, or any other arc's ledger.

**Worktree:** create `C:\Users\rwsmy\swing-trading\.worktrees\d84-plan` on a new branch `d84-plan`, off main at the commit that carries this brief. Never use the Agent tool's worktree isolation. Run with `PYTHONPATH=.`. Read the live DB ONLY on a `mode=ro` URI through plain `sqlite3`, never through `swing`'s `connect`.

## 0. Scope (summarised; the proposal and CHARC's mail govern)

- **Routing: V2.1 section VII.F.** `bucket_for` IS the A+ definition behind H1, H2 and H4. This arc unfreezes the gate on exactly ONE criterion, `risk_feasibility`, and nothing else.
- **(1) The gate becomes a flag.**
  - `bucket_for` (`swing/evaluation/scoring.py`, the "Risk is a hard filter" early return) no longer returns `skip` on the risk layer.
  - The criterion keeps computing and persisting `shares` and `risk_dollars`.
  - The result becomes a displayed FLAG on every A+ surface (card, mandate, prepared-order form): shares at the budget, risk dollars, and a plain statement that the operator is above budget if he proceeds.
  - **No surface refuses.**
- **(2) The cohort amendment, in the SAME change:**
  - H1 = `aplus` AND risk pass.
  - H4 = `aplus` AND risk fail, post-boundary.
  - The pre-boundary H4 form (`watch`/`skip` with risk the only miss) is RETAINED.
  - Both forms are dated at the boundary in `hypothesis_status_history`.
  - A live fill on a risk-flagged A+ labels H4, never H1.
- **(3) NOT touched:**
  - the 19-D `degenerate_risk` floor in the shadow engine;
  - the bucket enum VALUE set (SQL CHECK `0001:28`, `models.py`, `journal/analyze.py`), so no widening sweep;
  - `swing/data/`, `swing/trades/`.
- **Tripwires:** none formally, per the proposal. **But F5 can create a SCHEMA tripwire.** If the H1 amendment moves the sha256-pinned text of migration 0034, that is a new migration. You then STOP and return before writing any of it.
- **`swing/evaluation/` is the measured instrument.** Treat every change there as measurement-chain.

## 1. Code to read (CHARC's list, with path corrections applied)

- `swing/evaluation/scoring.py` (`bucket_for`).
- `swing/evaluation/criteria/risk_feasibility.py`.
- `swing/recommendations/hypothesis.py`:
  - from about :230 to :360;
  - `_aplus_baseline_match`, `_capital_blocked_match`, `_descriptive_label`.
- `swing/latches/reader.py`, about :300-360: the L4 risk drop. The correct path is `swing/latches/`, NOT `swing/web/view_models/latches/` as the proposal says.
- `swing/recommendations/sizing.py` (`compute_shares`, `SizingResult`).
- The `compute_shares` call sites, which CHARC listed by call site on `00af816b`. Re-find them on your base:
  - `swing/latches/order_intent.py`;
  - `swing/recommendations/build.py`;
  - `swing/web/routes/trades.py`;
  - `swing/web/view_models/dashboard.py` (two sites);
  - `swing/web/view_models/trades.py`.
- The 21-B parity-ledger scorer: `swing/latches/classification.py` `compute_execution_parity`, and the writer that persists its result.
- `swing/watchlist/service.py` (the static criteria roster).
- `swing/metrics/capital.py` (`risk_feasibility_blocked_rate`, plus the tile that renders it).
- `swing/data/migrations/0034_h1_decision_criteria_amendment.sql`: the H1 clause and the sha256 pin.

## 2. Round 0: the premise and fork census (NO Codex)

Work at the code and on the live DB (`mode=ro`). Answer every item with file:line or a query and its output.

**A. Premises.** Verify the proposal's section 2 facts 1, 3 and 5 against your base. Verify each line CHARC re-verified in his dispatch. Record every drift.

**B. CHARC's F1-F6.** For each item, give the answer the plan will carry:
- **F1:** for each `compute_shares` consumer, what a ZERO-share result renders and what the operator can do from there. Then the parity ledger: how a one-share take on a zero-share framework order scores DEVIATING-BY-DECLARATION, never "deviated from an order of zero". Propose a shape. If more than one shape is defensible, give both branches with their consequences. CHARC rules it.
- **F2:** every reader of the risk result, found by READ, not grep. For each, what changes and what does not.
- **F3:** whether the watchlist's add, requalify, streak and remove semantics move when a risk-fail name is bucketed `aplus` (or, per RD's view (iv), `watch`). State it; do not assume neutrality.
- **F4:** name the metric tile and the docstring whose meaning moves from blocked to flagged.
- **F5:** does "H1 = aplus AND risk pass" change 0034's PINNED TEXT, or only matcher code plus status-history rows? Quote the pinned clause. **If the pinned text moves: STOP AND RETURN.**
- **F6:** the single source after the arc. Either the reader keeps its L4 drop, now redundant, or it reads the evaluator's flag. Name it, and give the rewritten L4 comment (gotcha #31: describe what the code does after the change).

**C. RD's views (i)-(vi).** Confirm or refute each at the code, with file:line. Two of them need live counts:
- **For (iii), the H4 width delta:** count the historical `skip` rows whose non-pass set is exactly `{risk_feasibility}`, and those whose non-pass set is `{risk_feasibility}` plus one allowed trend-template miss.
- **For (iv), the watch widening:** count the risk-fail rows whose other results would route them to `watch` with the pre-skip removed. Simulate `bucket_for` over the persisted criteria; do NOT re-evaluate.

State the query and the run or date window for each count.

**D. Acceptance (i)-(v)** from the proposal section 3. For each, name the discriminator test and show that it FAILS on today's code. (v) is the one CHARC shapes.

**E. Forks.** List every point where the code admits two designs, with both branches.

**RETURN at the end of round 0, every time,** with the census as a ruling packet: each item addressed to ONE ruler. CHARC rules F1-F6 and the form. RD rules the population and the H1/H4 cohort items. Where both must speak, say who goes first. Do not write the plan before the packet is ruled. The orchestrator posts the packet as ONE query and returns the rulings to you, or to a continuation cell.

## 3. The plan (after the round-0 rulings)

Follow the recipe's plan-stage protocol:
- a task ladder and a test roster of about 1,000 lines or fewer;
- a plan ledger beside it, with every ruling BLOCK-QUOTED and its author named;
- RED-first discriminators for acceptance (i)-(v), plus every ruled F-item;
- the anti-vacuity check for (ii): the H1 matcher returns False on a risk-fail `aplus` row. This kills a bucket-only amendment;
- the (iv) check: the pre-boundary H4 form still matches a pre-boundary `skip` row;
- the #31 rewrites as named tasks: the reader's L4 comment, the `_capital_blocked_match` docstring, the `_descriptive_label` annotation, and the `capital.py` docstring and tile prose;
- the `hypothesis_status_history` boundary rows. State who writes them (an operator CLI action? a migration? RD at the merge?) and when;
- the executing cell is `implementer-opus-high` (CHARC's choice), and the plan is written for it.

**This arc is HTMX-adjacent:** the flag renders on the card, the mandate and the prepared-order form. The plan carries an **operator-witnessed browser step at the merge gate.**

**Rounds:**
- `fast` tier with `-p fast`; a missing profile fails the round loudly. At most THREE counted rounds, then the self-sweep.
- Rulings are inlined in the prompt, or given as a ledger copy cut before its round section.
- The verdict tokens are DESCRIBED, never written line-initially; grep the prompt to prove it.
- A per-item checklist, each item answered holds / fails / cannot-tell with file:line.
- No prior-round reads, proved by grep.
- Every per-round assertion in the recipe holds. Only the anchored verdict token with `^ERROR` = 0 proves a round finished.
- Evidence goes to `C:\Users\rwsmy\swing-data\review-transcripts\d84-soft-stop\plan\round<N>\`, with responses saved, not only prompts.
- **STOP AND RETURN at EVERY counted round gate** with its ledger row, leaving the depth column empty (the orchestrator fills it).
- Commit the plan ONCE, at convergence.

**After convergence the plan goes to the plan-stage director review, which the orchestrator posts. Then the arc STOPS for the operator. You do NOT start executing, and you write no `swing/` code.**

## 4. Gates and return

- Commits are conventional and pathspec-only. `%(trailers)` is empty; no final `-m` paragraph begins with `Word:`; no Co-Authored-By, no `--no-verify`, no amend.
- No `swing/` or `tests/` change: this is planning.
- **Return in chat only.** You NEVER post to a mailbox and never run `scripts/role_mail.py`.
- **If anything does not fit, STOP and return.** Do not choose for yourself. That covers a fork, an F5 schema answer, a premise that fails, and a scope question.
