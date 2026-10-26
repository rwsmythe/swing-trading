# D84 -- the capital soft-stop arc: WRITING-PLANS continuation brief, cell 3

**Audience:** a fresh implementer cell with no prior conversation context.
- Cell 1 ran the round-0 census.
- Cell 2 drafted the plan, stopped on four forks (P1-P4), and ran out of context.
- Both directors have ruled every item.
- **You encode the remaining rulings into the committed draft, then drive Reviewer A to convergence.**

**Authority:** unchanged and plans-only. The operator said "Stop before executing (Recommended)" on 2026-10-25. You write no `swing/` or `tests/` code.

**Cell:** `implementer-opus-high`. Every design fork is ruled; this is encoding plus convergence.

## 0. Read ONLY these, in order

1. **The plan ledger (BINDING)**, at `b1415630` or later: `docs/superpowers/plans/2026-10-26-d84-soft-stop.plan-ledger.md` on branch `d84-plan`. It block-quotes four rulings mails: RD r0, CHARC r0, RD cell-2 and CHARC cell-2. **Where a later ruling differs from an earlier one, the later ruling wins** (for example, E-d is REVERSED by RD's cell-2 ruling).
2. **The plan DRAFT** you continue: `docs/superpowers/plans/2026-10-26-d84-soft-stop.md` on the same branch, committed at `156f1611`. It carries file:line for most of what you need. **Do not re-survey the codebase. Cell 2 died at 463K doing that.** Open code only to encode a specific task.
3. `docs/d84-soft-stop-plan-continuation-brief-cell2.md` on main. Its section 1 checklist and section 2 rounds rules still bind.
4. The cell-2 fork packet: `C:\Users\rwsmy\swing-data\review-transcripts\d84-soft-stop\plan\cell2-census\fork-packet.md`.
5. `docs/implementer-dispatch-recipe.md` section 3.

Do NOT read `comms/`, the director state files, or any other arc's ledger.

**Worktree:** the EXISTING `C:\Users\rwsmy\swing-trading\.worktrees\d84-plan`, branch `d84-plan`, clean at `b1415630`. Use `PYTHONPATH=.`. Read the live DB only on a `mode=ro` URI through plain `sqlite3`.

## 1. What changes in the draft (a checklist; the ledger rulings govern)

- **P1 (CHARC):** a criteria-derived MARKER at the three tag sites, with no sizing numbers.
  - It is ASCII and sort-neutral, built through the same E2 adapter as P2, and held in a SIBLING mapping to `_flag_tags`.
  - The briefing and watchlist expansion grids also render the risk criterion's row.
  - The briefing pin is a render assertion, not TestClient.
- **P2 (CHARC):** the flag and the attest affordance are keyed on the fire's stored criteria through the E2 adapter.
  - They render on live AND terminal cards inside the display lookback, until an attestation or decision governs.
  - State the 0-of-19 disagreement band.
- **P3 (CHARC):** keep 21-B's withheld-reason precedence.
  - Sizing runs after `limit_below_pivot` and before the regime branch.
  - `PreparedOrderResult.sizing` is admitted beside `regime_undeterminable` and `sizing_infeasible` ONLY, pinned in `__post_init__`.
- **P4 (RD, with CHARC on scope):** the five research sentences become era pins (RD's two texts), and the cross-check's two risk-fail cases assert BOTH sides under an "era divergence, D84" case id.
  - List every research path under T11. The aggregator path is `research/finviz_pool_analysis/aggregator.py`.
  - The un-realigned mirrors become a declared limitation, with RD's reason.
- **E-a:** `SizingResult` carries the budget as `max_risk_dollars`, beside `risk_per_share`.
- **E-b:** `zero_share_line` owns BOTH forms: the stated-zero line, and the criteria-only marker.
- **E-c with E-d REVERSED:**
  - `RiskInputs(risk_result_count, risk_non_pass_count)`;
  - `risk_layer_passes` holds iff the count is at least 1 and nothing fails;
  - an EMPTY layer is neither pass nor fail: no marker, no flag, and the matcher returns `[]`;
  - one test per consumer pins the empty case.
- **E-h:** acceptance (iii) is a guard test. **RUN the mutation** (H4 defined as aplus-only) once against it in a scratch copy, and quote its red line in the ledger. Replacement (iv) is red today and needs no mutant.
- **E-g:**
  - `D84-MERGE-DATE.1` is filled in one tip commit before `merge --no-ff`. The merge-gate check is `git grep -n "D84-MERGE-DATE"`, which must return nothing. State why the digest does not move.
  - `<D84 merge sha>` is filled in a docs-only commit on main AFTER the merge, as a named orchestrator close-list step.
- **E-i:** the D84 attest-section lead paragraph is DISTINCT from the terminal-no-action one. Use CHARC's content.
- **E-e, E-f, E-j:** as accepted.
- **The H4 declared limitation** gains RD's prefill sentence verbatim: "the prefill is derived from the latest run's candidate, not the fire's; the label is operator-asserted; correction via the Demand-C tier-2 surface."
- Keep the draft's section 5 list of the 26 newly failing tests, each with its disposition. Update any that the rulings change.

## 2. Rounds and gates

- **Reviewer A:** the `fast` tier with `-p fast` (a missing profile FAILS LOUDLY). At most THREE counted rounds, then the uncounted self-sweep.
- Rulings go to Codex inlined, or as a ledger copy cut before its round section.
- Verdict tokens are described, never written line-initially; prove it by grep.
- A per-item checklist; no prior-round reads.
- Every per-round assertion holds. Only the anchored verdict token with `^ERROR` = 0 proves a round finished.
- Save prompts AND RESPONSES to `C:\Users\rwsmy\swing-data\review-transcripts\d84-soft-stop\plan\round<N>\`.
- **STOP AND RETURN at EVERY counted round gate** with its ledger row (depth column empty) and your proposed finding dispositions. The orchestrator rules and resumes you.
- This SUPERSEDES the cell-2 brief's commit-once-at-convergence rule, because the draft is already committed at `156f1611`. Before round 1, commit the encoded plan once, so the round reviews a SHA. Each round's fixes go in their own commit.
- The convergence commit carries the final ledger rows.
- Pathspec commits, `%(trailers)` empty, no amend.
- **Return in chat only.** You never post to a mailbox and never run `scripts/role_mail.py`.
- **If a ruling cannot be carried as written, or a new fork appears: STOP and return with both branches.**
