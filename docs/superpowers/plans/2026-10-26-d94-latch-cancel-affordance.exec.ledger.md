# D94 (a)+(b) EXECUTING ledger -- the latch validity prompt gate + the ledger-keyed cancel affordance

**Plan:** `docs/superpowers/plans/2026-10-26-d94-latch-cancel-affordance.plan.md` (cleared at `fafb92ac`).
**Plan ledger:** `docs/superpowers/plans/2026-10-26-d94-latch-cancel-affordance.plan.ledger.md`.
**Brief:** `docs/d94-latch-cancel-affordance-exec-dispatch-brief.md` (main `7b2dca9e`).
**Worktree / branch / diff base:** `.worktrees/d94-cancel`, `d94-cancel`, `8acea975`.
**Evidence:** `C:\Users\rwsmy\swing-data\review-transcripts\d94-cancel\exec\` (`tdd-evidence\`, `round<N>\`).

## 1. Rulings received during executing (verbatim, with authors)

### 1.1 Orchestrator -- the Task-3 misfit (T3.2 placement) and the C-1 naming. Author: the orchestrator.

Raised by this cell at the Task-3 boundary: T3.2's assertion (iii) (exactly one `latch-cancel-form`
for 5002) names the LEDGER-KEYED control, which Task 4 renders, so it could not be GREEN at the
Task-3 commit.

> T3.2 placement: OPTION A. T3.2 lands in Task 3 with assertions (i), (ii) and (iv). Assertion (iii), exactly one ledger-keyed `latch-cancel-form` for 5002, is ADDED to the same test function in the Task-4 commit, where the control is wired, and must be RED on the Task-3 tree. This is a test-SEQUENCING correction of the SS-1/SS-2 kind: no code, gate, envelope or assertion content changes, so it does not re-open the directors' clearance. The plan text stays as committed; this ruling and the ledger record the move.
> The naming deviation (`resting_order_ids` for the plan's `book_order_ids`, per CHARC C-1) is ACCEPTED. Use the same name for Task 3's `_displaced_cycle_prompts` keyword.

## 2. Deviations from the plan text (each with its authority)

- **D-1 (naming, CHARC C-1; accepted in 1.1).** The gate's keyword and `_displaced_cycle_prompts`'
  keyword are `resting_order_ids` (the plan's code blocks say `book_order_ids`); the same set is
  exposed on `_ValidityRender.resting_order_ids` (C-2).
- **D-2 (test sequencing, ruling 1.1).** T3.2 (iii) lands in the Task-4 commit, RED on the Task-3
  tree.
