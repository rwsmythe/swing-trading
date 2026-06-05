# Orchestrator Handoff -- 2026-06-05 (Phase 15, mid data-integrity arc)

**Audience:** A fresh Claude Code instance taking on the ORCHESTRATOR role for Swing Trading (`c:\Users\rwsmy\swing-trading`). Replaces an outgoing orchestrator at ~10% context. You drive the copowers cycle + QA + merge; you do NOT implement. **Read the session-start `orchestrator-handoff-2026-06-04-phase15.md` for the durable role framing** (disciplines, transport, the WSL Codex form) -- this doc is the DELTA since then.

## 1. Clean boundary (verify: `git log --oneline -8` + `git status -sb`)
- **main HEAD = the commit adding the writing-plans dispatch brief** (one past `83927797`; verify). **main is ~7 AHEAD of origin -- and the range INCLUDES the operator's commit `56d51607` ("curate Minervini exemplars").** **PUSH IS HELD:** do NOT `git push` without asking -- it would push the operator's in-flight research commit. Ask before pushing.
- The operator has **PARALLEL uncommitted Minervini research work** on main: a `.gitignore` mod + untracked `research/harness/minervini_exemplar_recall/`, `research/data/qa/`, `reference/d_us_txt.zip`. **DISJOINT from all orchestrator arcs -- do NOT touch, stash, or commit it.**
- ~7130 fast tests green; **schema v24**; ZERO `Co-Authored-By` (~700+ commits); L2 LOCK re-anchored once (schwabdev-v3). The 3 known xdist co-residency flakes (`test_ohlcv_reader_re_export_identity`, `test_read_cohort_csv_against_committed_v2trf`, `test_prices_refresh_uses_pipeline_eval_anchor`) pass `-n0`.

## 2. Shipped this session (2026-06-04/05)
- **Pattern-observation pool widening `#23` `8ee98fc1`** (CLOSED; OQ-4 first-live-run gate passed Run 89; invisible-widen confirmed).
- **Finviz signature-provenance fix `52fcadb1`** (CLOSED; hash only `column_set`).
- **Phase-14 cross-sub-bundle integration review** (CLOSED 2026-06-05; `docs/phase14-integration-review-checklist.md`; verdict: sub-bundles cohere; **4 findings** -- #5 topbar-date anchor inconsistency [-> data-integrity arc], #3 capital-friction count [-> separate metrics fix], #2/#4 polish batch).
- **Data-integrity brainstorm `d3c21e31`** (spec MERGED; `docs/superpowers/specs/2026-06-05-data-integrity-regular-session-completed-day-design.md`, 465 lines; Codex R1[2crit]->R4 converged).

## 3. IN FLIGHT -- data-integrity writing-plans DISPATCHED
The **data-integrity writing-plans** is dispatched (brief `docs/data-integrity-arc-writing-plans-dispatch-brief.md`; the operator has the inline prompt). **AWAIT the implementer's return, then QA against disk -> merge (rebase-then-ff if main moved -- the operator commits Minervini work in parallel; §1) -> dispatch executing-plans.** The arc: 4 slices A(ext-hours pull)->C(write-barrier+lock-guard+remediation)->B(quotes,after OQ-3)->D(uniform topbar); NO schema (v24); 5 OQs (1b/3/4/5/7) resolved operator-paired at writing-plans; the binding gate is an **operator-witnessed LIVE Schwab re-fetch** (post-merge; confirms the ~16% `OhlcvBar invariant violated` rate collapses once ext-hours is off). Spec key points: the lock-guard is **date-only** (C2 -- cannot validate ext-hours; ext-hours fixed at the pull); Issue #5 = 3 anchor families (incl. a `date.today()` naive bug) -> a required-`PageKind` classifier; Issue #3 root cause = `_count_open_at_run last_fill_at >= started_ts` (metrics predicate, NOT the Schwab snapshot).

## 4. Banked / open (NOT in flight)
- **Issue #3 metrics fix** -- a separate small brief: `_count_open_at_run` should key "still open" on the exit/terminal ts, not `last_fill_at` (spec §8). OQ-5 decides open-now-or-bank.
- **Issue #2 + #4 polish batch** -- non-uniform empty-state messaging + `/schwab/status` not nav-linked. Small standalone.
- **B-1..B-8 + the Minervini exemplar-recall validation** -- APPLIED RESEARCH (research branch `research/phase-0-tasks.md`); NOT operational. The operator is ACTIVELY doing the Minervini work now (§1).
- Older §B backlog (Schwab Phase B/C, corporate actions, etc.) in `docs/phase3e-todo.md`.

## 5. Binding disciplines (unchanged; full detail in the 2026-06-04 handoff §7)
Merge is an orchestrator action at QA-pass/convergence/gate-pass (don't ask) -- EXCEPT the push is HELD (§1). QA every product against disk + AWAIT the return before QA. NEVER false-green (re-run the suite on the merged head; isolate the known flakes; for a docs-only merge the suite is unaffected -- state that). copowers Codex runs to convergence via the WSL prefix+stdin form (MCP dead). Operator gates are binding + witness the UNSEEDED default + kill the gate server by PID after. NO Co-Authored-By / NO --no-verify / final `-m` paragraph plain prose / verify `%(trailers)` is `[]` before every push. Commit the dispatch brief BEFORE the inline prompt + always provide a paste-ready inline prompt. **Divergence (operator commits land mid-flight): rebase the branch onto main then `merge --ff-only` (a fresh worktree if the original is gone -- happened this session).** The operator paces deliberately; "pause" = stop.

## 6. READ FIRST
1. `CLAUDE.md` line-3 + §Gotchas (esp. yfinance partial-bar + session-anchor families) + Invariants.
2. `docs/phase3e-todo.md` §A (the data-integrity bullet has the full arc record + OQs) + §"NEW operational items".
3. The data-integrity spec + the two dispatch briefs (§2/§3 above).
4. `docs/orchestrator-handoff-2026-06-04-phase15.md` (durable role framing) + `docs/orchestrator-context.md` + the `memory/` directory.

## 7. FIRST ACTION
Stand by. Greet the operator; confirm the clean boundary (main HEAD, the held push incl. their Minervini commit, ~7130 green, v24). The **data-integrity writing-plans is dispatched** -- when the implementer returns, AWAIT the operator's signal, QA against disk, merge (rebase-then-ff if needed), then author the executing-plans dispatch. Do NOT push without asking (§1). Do NOT touch the operator's Minervini work. Ask the operator whether to push the held commits.

*End of handoff. Phase 15: pool-widening + finviz fix + the Phase-14 integration review CLOSED this session; the data-integrity brainstorm SHIPPED + merged; the writing-plans is dispatched-and-awaiting. The push is held (the operator's Minervini commit is in-range). Land clean at the writing-plans-brief commit.*
