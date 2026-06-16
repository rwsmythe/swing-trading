# Harness Scaffold — executing-plans dispatch brief

**Authored:** 2026-06-16 by the orchestrator (CHARC-commissioned arc). **Phase:** copowers **executing-plans** — build the generic harness scaffold in its NEW clean-room repo per the converged plan. **Audience:** a dispatched implementer cell (sub-agent). **This is CHARC-owned harness-architecture work, dogfooded by the swing harness — NOT a swing application arc.** The product lives in a SEPARATE repo; nothing built here lands in the swing tree.

## 1. Mission
Build the generic, application-agnostic multi-agent **harness scaffold** in the new repo at **`C:/Users/rwsmy/harness-template`** (already `git init`-ed by the operator — empty, default branch `master`, zero commits) by executing the converged implementation plan task-by-task (TDD/acceptance per task), running the production-code review to convergence, and clearing the binding genericity-guard gate. The scaffold = docs + comms scripts + agent-cell files + the session registry + the genericity guard, with **zero application/domain content** and **zero hard runtime deps** in the core.

## 2. Read first (in order; re-ground every anchor against live code)
1. `docs/implementer-dispatch-recipe.md` — THE dispatch protocol. **Read §3 in full**, especially the **REPO-ACCESS for PRODUCTION-CODE review** note + the **`codex-auto-review` complementary second-eye** note (both added 2026-06-16, `00199c51` — LOAD-BEARING for this arc; see §6 here).
2. `docs/superpowers/plans/2026-06-16-generic-harness-scaffold-plan.md` — **THE BINDING TASK SPEC.** Execute it. Task groups A–J, ~30 tasks, each with its files + failing-test/acceptance-check + commit message. The plan's §2 execution order is binding: **A.1 → F.1 → A.2 → A.3 → B → D → E → C/G/H → I → J** (F.1 the guard lands BEFORE any content doc).
3. `docs/superpowers/specs/2026-06-16-generic-harness-scaffold-design.md` — the binding DESIGN (adversarial-converged + CHARC-ratified, incl. the §5.1 direction-asymmetric addressing tighten `01021c27`). The plan decomposes it; if plan vs spec ever conflict, STOP-and-ask.
4. `CLAUDE.md` (swing root) — read for the DISPATCH DISCIPLINES (commit conventions, ZERO `Co-Authored-By`, ASCII-stdout, Windows/WSL gotchas). **It is NOT scaffold content** — the new repo has its OWN (empty) context; do not copy swing gotchas/finance content into the scaffold (the genericity guard forbids it).

## 3. The workspace — the NEW repo (NOT a swing worktree)
- Build in **`C:/Users/rwsmy/harness-template`** (operator-inited per decision **B1**: the repo exists + is empty; **A.1 POPULATES it — A.1 does NOT run `git init`**). Default branch is `master`.
- Work on a build branch in that repo (`git -C C:/Users/rwsmy/harness-template checkout -b scaffold-build`) so the orchestrator can review the build as a clean commit range; commit per task there. The recipe's "isolated workspace" = your branch in the NEW repo (there is NO swing `.worktrees/` involvement, NO cross-repo merge into swing's main — the new repo IS the product).
- All file paths in the plan's "Files (new repo)" lines are relative to `C:/Users/rwsmy/harness-template`. The plan's `<harness-template>` token resolves to this path.
- **Editable-install note does NOT apply** (this is a fresh repo, no `swing` package). Run the scaffold's own tests from the new repo dir.

## 4. Settled decisions (do NOT reopen — fold them in as the plan already records)
- **A** = the repo is `C:/Users/rwsmy/harness-template`. **B1** = operator inited it (you populate; you do NOT `git init`). **C** = per-generation director→orchestrator addressing (already built into the plan: `comms/orchestrator/<session_id>/inbox`, `--to orchestrator:<session_id>` / bare `--to orchestrator` = newest-live; shared `--to charc` + `--to operator` own-inbox). The shared-inbox/atomic-move-claim/handoff model is NOT built.
- **CHARC-RATIFIED (build exactly as the plan specifies; do NOT re-litigate):**
  - **#1 — the §8 genericity-guard "finance tickers" realization** = the CLOSED swing-residue denylist (plan F.1: `SPY/QQQ/NDX/SPX/RUT` + `trade`/`trading`/`finance`/`ticker`/`yfinance`, word-boundary matched; a universal uppercase matcher is REJECTED). Ratified as the §8 guard contract.
  - **#2 — the §5.3-vs-§8 seam-doc/codex-pointer placement** = `review-gate-seam.md` stays 100% substrate-free (no substrate word OR path); the `codex-reviewer.md` pointer is routed via `dispatch-recipe.md` + `README.md`/`charc-bootstrap.md`; the guard's file-scope exceptions stay EXACTLY the spec §8 two files (plan G.1/G.2/F.1(c)). Ratified.

## 5. Binding conventions (in the NEW repo)
- **TDD:** failing test (or acceptance check for docs) → see it fail → minimal impl → see it pass → commit. One red→green per logical change. Distinguishing tests (compute under pre/post — a test that passes both ways is worthless).
- **Test substrate = stdlib `unittest`, NOT pytest** (plan §1: the §8 guard forbids `pytest` in the tracked tree — no pytest dep, no `pytest`-named path). The optional `[web]` UI tests use FastAPI's `TestClient` (works under `unittest`).
- **Zero hard runtime deps in the core** (`role_mail.py` + the hooks + the registry are stdlib-only); the UI is an optional `[web]` extra. A.1's dependency-posture test (subprocess-no-site-packages + AST belt) is binding.
- **Conventional commits carrying the task id** (`feat(comms): Task B.1 — …`, `feat(registry): Task D.2 — …`, `feat(guard): Task F.1 — …`). **ZERO `Co-Authored-By`. No `--no-verify`. No amend** (new commit per fix). Keep the final `-m` paragraph plain prose (trailer-parse hazard). Verify trailer-clean before handoff.
- **ASCII discipline** for user-facing stdout (the comms CLI, the unread notice) — Windows cp1252 crashes on `§ → ✓` etc.
- **The genericity guard (Task F) is the binding no-app-contamination gate** — green over the WHOLE tracked tree at accept (J.2). A guard hole = a blocking major. NO `swing`/`trading`/`finance`/`chess`/`COA`/forbidden-vocab anywhere in the tracked tree (the F.1 denylist + the self-exclusion of the list file).

## 6. Review — PRODUCTION CODE → `review-strong` WITH REPO ACCESS + `codex-auto-review` second-eye
This is the **production-code** executing review. Per recipe §3 (the `00199c51` methodology):
- **`review-strong`** is the binding iterative gate. Run to **`NO_NEW_CRITICAL_MAJOR`** (cap suspended). **MUST use REPO ACCESS, not pure diff-only** — the scaffold's correctness depends on the surrounding reference graph (the three lifecycle hooks sharing the registry logic; the comms claim/atomicity; the guard's scan-target + exclude set; the import-isolation of the UI from the core). Either point Codex's cwd at the new-repo checkout (`-s read-only`, so it greps the surrounding code itself) OR bundle the reference-graph surrounding files alongside the diff in stdin. A pure-diff stdin form is INSUFFICIENT here.
- **`codex-auto-review` as a COMPLEMENTARY second-eye** (repo-access, MATCHED-HIGH: `codex exec review --commit <pre-review-sha> -c model_reasoning_effort=high`), run alongside `review-strong`. A B `major`/`[P1]` is adjudicated + resolved-or-cited before accept. `review-strong` stays the binding gate.
- **Persist EVERY response** (both reviewers) to a gitignored `.copowers-findings.md` at the new-repo root (round-by-round verbatim + your per-finding adjudication). The orchestrator verifies convergence from this real transcript.
- **Adjudication:** the recipe's §39 schema-prevented-value bound does NOT broadly apply (this is mostly new code, not a read-only DB consumer) — but the same "adjudicate-don't-blind-fix; cite the constraint; converge once only the genuinely-out-of-scope class remains" discipline holds.
- **Full suite to GREEN BEFORE the review AND after** (recipe §2): run the scaffold's `unittest` suite to green after the task-commits land + before starting Codex (catches the cross-cutting tests — the whole-tree genericity guard J.2, the dependency-posture A.1, the comms/registry suites J.1/J.2), and again on the final converged tree.

## 7. Done criteria (maps to the plan §J.3 + the spec §1 success criterion)
- Every plan task A–J shipped (TDD/acceptance green), in the plan's execution order.
- The whole-tree **genericity guard is green** (zero forbidden vocab; every substrate term in-scope) — the no-app-contamination proof.
- Core is **zero-hard-dep** (A.1 green); the UI is `[web]`-gated + import-isolated.
- The **comms round-trip** (J.1) + the **registry suite** (J.2: register / heartbeat / prune / recreate-if-missing / role-gated / SessionEnd-tidy-if-empty / per-generation addressing) are green.
- The **bootstrap dry-run** (J.3) confirms a fresh CHARC can verify comms (PRE-step-5) + reach the interview with no further setup; step-5 orchestrator bring-up is executable-as-written (`launch_role.ps1 -Role orchestrator -DryRun` produces the correct `HARNESS_ROLE=orchestrator` command).
- The ~14-file shipped manifest (plan §2.1) is exactly the §4 manifest; every tracked file is either manifest or the support appendix (one accounting model).
- Both reviewers converged/adjudicated; `.copowers-findings.md` complete.

## 8. Return report (to the ORCHESTRATOR only — chat, final message)
Do NOT post to any mailbox / use `--from orchestrator`. Include: the new-repo branch + the per-task commit range (SHA + task id); the scaffold's final `unittest` count (read off the final tree); the `review-strong` rounds + final verdict + the `codex-auto-review` verdict + adjudications + the `.copowers-findings.md` path; the genericity-guard whole-tree green confirmation; each plan lock honored-on-disk; A/B1/C + the two ratified items honored; deviations / STOP-and-ask. The orchestrator QAs against the new repo, verifies both reviewers' convergence from the real transcript, then the operator witnesses (the bootstrap dry-run is the irreducible reality check) before accept.

## 9. If you get stuck
- Plan-vs-spec conflict, or a task whose premise doesn't match the new-repo reality → STOP and report (don't work around).
- WSL-Codex unreachable → report; the orchestrator takes over the review.
- Anything that would need a new dependency the plan didn't authorize (the core must stay stdlib) → STOP and flag.
