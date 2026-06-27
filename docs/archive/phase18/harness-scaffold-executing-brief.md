# Harness Scaffold — executing-plans dispatch brief

**Authored:** 2026-06-16 by CHARC. **Phase:** copowers **executing-plans** — build the scaffold per the merged plan, task-by-task (TDD-or-acceptance), then the review loop to convergence. **This is harness-architecture work (CHARC-owned), the dogfood culmination — swing's harness builds the new scaffold.**

## 1. Binding inputs
- **The merged plan (THE task decomposition — execute EXACTLY):** `docs/superpowers/plans/2026-06-16-generic-harness-scaffold-plan.md` (on `main` @ `4d148a79`). Each task carries its files, the failing-test/acceptance cycle, and the commit message. Do not redesign; if a plan anchor diverges from live source, STOP-and-ask (recipe §5).
- **The design (binding):** `docs/superpowers/specs/2026-06-16-generic-harness-scaffold-design.md` (adversarial-converged + the direction-asymmetric-addressing amendment).
- **Dogfooding-source artifacts (READ to extract-from):** swing's `scripts/role_mail.py`, `scripts/comms_ui.py`, `scripts/start_directors.ps1`, the unread hook + `.claude/settings.json`, `docs/orchestrator-context.md`, `docs/implementer-dispatch-recipe.md`, `docs/tool-director-context.md`, `scripts/director_bootstrap_charc.md`, `.claude/agents/implementer-*.md`, `docs/comms-stage2-orchestrator-inbox-design.md`.

## 2. The CROSS-REPO shape (LOAD-BEARING — read carefully)
- **READS are in the swing repo** (`C:/Users/rwsmy/swing-trading`): the merged plan + spec + the dogfooding-source artifacts.
- **WRITES — the scaffold itself — go in the NEW repo `C:/Users/rwsmy/harness-template`** (operator git-inited; DECISION B1). The implementer works on **a branch of `harness-template`** (NOT a swing worktree, NOT swing's `.worktrees/`). A.1 POPULATES the repo; it does NOT `git init` (the operator already did — B1).
- **Commits land in `harness-template`** with the plan's task ids (`feat(comms): Task B.1 — …`), **ZERO `Co-Authored-By`**, no `--no-verify`, no amend (new commit per fix).
- The merged plan + spec + this brief STAY in swing (the design record); only the scaffold is built in the new repo.

## 3. Test substrate + the guard (binding, from the plan)
- **Tests = stdlib `unittest`, NOT pytest** (the §8 genericity guard forbids `pytest` in the tracked tree — plan §1 "Test substrate"). No pytest dep, no `pytest`-named path.
- **The genericity guard (plan Task Group F) is the binding no-app-contamination gate** — green over the WHOLE new-repo tree at accept (plan F.2/J.2). It is authored EARLY (F.1 between A.1 and A.2). Zero `swing`/`rd`/finance/chess/COA content anywhere; substrate terms only in the §8-exception files.

## 4. Review methodology (the NEW 18-H.4 protocol — binding)
- **Tier = `review-strong`** (harness PRODUCTION code: comms infra + the session registry + lifecycle hooks + the guard build-test). Run-to-`NO_NEW_CRITICAL_MAJOR`; cap suspended; persist every response.
- **REPO ACCESS, not diff-only** (recipe §3, the 18-H.4 lesson `00199c51`): the reviewer reads the new repo's surrounding code (the registry/closure/hook reference graph), not just the diff. Codex runs with cwd at `/mnt/c/Users/rwsmy/harness-template`, `-s read-only`.
- **`codex-auto-review` = GATING-complementary second-eye** (the 18-H.4 adoption): the ORCHESTRATOR runs it (repo-access, matched-HIGH `-c model_reasoning_effort=high`) on the new repo; a B `[P1]`/major is resolved-or-cited before merge.
- **before-AND-after full suite:** run the scaffold's `unittest` suite to green BEFORE the review loop, and again on the final head.

## 5. Operator decisions (settled — baked in, NOT re-litigated)
- **A** = repo `harness-template` at `C:/Users/rwsmy/harness-template`. (Every `<harness-template>` plan token resolves to this.)
- **B1** = operator inited the empty repo; A.1 populates (does NOT `git init`).
- **C** = per-generation director→orchestrator addressing (direction-asymmetric — shared orchestrator→director + operator's own inbox; the amended spec §5.1). The plan builds it (B.1/D.5/D.7).

## 6. Cell + gate
- **Cell: `implementer-opus-xhigh`** (the registry build-from-a-deferred-spec + the genericity-guard regex + the seam contracts are judgment-dense; the doc-lifts are mechanical — plan §7).
- **Gate:** the scaffold's full `unittest` suite green (before + after) + the genericity guard green over the whole new-repo tree + `review-strong` convergence + the `codex-auto-review` gating-complementary clear → **orchestrator QA-against-disk** → **CHARC verifies** the build matches the plan/spec (every seam, the registry, the guard, the §2.1 manifest accounting, the per-generation addressing, zero hard deps) → the **operator bootstrap-dry-run witness** (the §5.5 staged guarantee: CHARC-op works on a bare clone of the new repo). The implementer reports to the ORCHESTRATOR in chat; it does NOT post to any director mailbox.

## 7. After accept (NOT this dispatch)
Once the scaffold is built + accepted, the NEW repo's own CHARC bootstraps it (the germination — instantiate → launch CHARC → the application-definition interview). That is a SEPARATE, later step (and not in swing-trading). This dispatch ends at "the empty scaffold is built, guard-green, dry-run-witnessed."
