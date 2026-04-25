# Post-Tranche-C Housekeeping — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Single small commit closing tracking and documentation drift after both Tranche C sessions completed (pipeline-linkage bundle and candidate-sparsity diagnostic). The orchestrator has already made all substantive content edits to tracked files; the implementer's task is purely mechanical — verify the working tree state, stage the listed files, and commit.
**Expected duration:** ~10 minutes.
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, conventional-commits + no-Claude-co-author + no-amend rules.
2. `docs/orchestrator-context.md` — the orchestrator handoff file. Has been updated by the orchestrator with current in-flight state (both Tranche C sessions complete), new "Recent decisions" entries, and new "Lessons captured" entries.
3. `docs/phase3e-todo.md` — operational backlog. Has been updated by the orchestrator with a new "Tranche C deferred items (2026-04-25)" section appended.

**Skill posture.** Do NOT invoke any `copowers:*` wrapper skills — purely housekeeping. Invoke `superpowers:verification-before-completion` before declaring done. No other skills required.

---

## 1. Scope — one commit, three or four files

| # | File | State expected | Action |
|---|------|----------------|--------|
| 1 | `docs/orchestrator-context.md` | Untracked — new file (created and edited by orchestrator) | `git add` |
| 2 | `docs/phase3e-todo.md` | Modified — orchestrator appended a new section | `git add` |
| 3 | `docs/tranche-c-pipeline-linkage-brief.md` | Likely untracked — orchestrator-authored brief, may not have been tracked by the pipeline-linkage session itself | `git add` if untracked, otherwise skip |
| 4 | `docs/tranche-c-candidate-sparsity-diagnostic-brief.md` | Should be tracked already (diagnostic session's D0 commit `1b33e21` was titled "track Tranche C candidate-sparsity diagnostic brief") | Verify, no action needed |
| 5 | `docs/post-tranche-c-housekeeping-brief.md` | Untracked — this brief itself | `git add` |

### Verification step before staging

```bash
git status
```

**Expected output (in some order):**

- `docs/orchestrator-context.md` — untracked
- `docs/phase3e-todo.md` — modified
- `docs/tranche-c-pipeline-linkage-brief.md` — untracked OR already tracked (depends on prior session)
- `docs/post-tranche-c-housekeeping-brief.md` — untracked
- Possibly `research/harness/earnings_proximity/diagnostic-out/...` — IF gitignored, won't appear; if appearing, see below

**If unexpected files appear**, do NOT silently stage them. Flag in the return report and proceed only with the four/five listed above.

**If `research/harness/earnings_proximity/diagnostic-out/` content appears in git status as untracked**, that's a gitignore gap from the diagnostic session — those large `evaluations.csv` files should be gitignored. Verify the diagnostic-out `.gitignore` is in place; if not, that's a separate small fix worth flagging in the return report (but do NOT add the diagnostic-out content to this commit).

### Explicitly out of scope

- Any code change.
- Any modification to file content beyond what the orchestrator has already edited.
- Adversarial review (no code, nothing substantive to review).
- Any other follow-up item from the Tranche C deferred-items list.

---

## 2. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. **No Claude co-author footer. No `--no-verify`. No amending.**
- **Tests:** fast suite green (no code changed; sanity-check with `python -m pytest -m "not slow" -q` before commit).
- **Ruff:** N/A (no code changed).

---

## 3. Stage and commit

```bash
git add docs/orchestrator-context.md docs/phase3e-todo.md docs/post-tranche-c-housekeeping-brief.md
# Add the pipeline-linkage brief if it's untracked:
git add docs/tranche-c-pipeline-linkage-brief.md
git status  # confirm expected state
```

**Commit message:**

```
docs: post-Tranche-C housekeeping — orchestrator context, backlog, brief tracking

- Track docs/orchestrator-context.md (new orchestrator-role handoff file
  created during Tranche C; durable bootstrap context for future
  orchestrator sessions).
- Update docs/phase3e-todo.md with new "Tranche C deferred items
  (2026-04-25)" section: build_watchlist mixed-anchor fix, stale
  pipeline_chart_targets cleanup, hypothesis-5 parity check, hypothesis-6
  Finviz universe reconstruction, supplementary $100k parity run,
  Newcombe interval refinement, recompute_binding_prod_gated.py
  parameterization, capital-sensitivity disposition note.
- Track docs/tranche-c-pipeline-linkage-brief.md and
  docs/post-tranche-c-housekeeping-brief.md.
```

(If the pipeline-linkage brief is already tracked, drop the corresponding bullet from the commit message.)

Run `python -m pytest -m "not slow" -q` after the commit. Expected green (no code changed).

---

## 4. Done criteria

- One commit on `main` with the message above.
- `docs/orchestrator-context.md` is tracked.
- `docs/phase3e-todo.md` modifications are tracked.
- `docs/post-tranche-c-housekeeping-brief.md` is tracked.
- `docs/tranche-c-pipeline-linkage-brief.md` is tracked (either by this commit or already by a prior session).
- Fast test suite green (sanity check; no expected change from baseline 721).
- Return report produced.

---

## 5. Return report format

```
## Post-Tranche-C housekeeping return report

### Commit landed
- <SHA> docs: post-Tranche-C housekeeping — orchestrator context, backlog, brief tracking

### Files staged
- docs/orchestrator-context.md (new)
- docs/phase3e-todo.md (modified)
- docs/post-tranche-c-housekeeping-brief.md (new)
- docs/tranche-c-pipeline-linkage-brief.md (new OR was already tracked — note which)

### Tests
- After: <N> passing, 0 failing (fast suite). Expected: 721 passing baseline unchanged.

### Other untracked files discovered
<List any unexpected untracked files. Empty if git status matched expectations.>

### Open questions for orchestrator
<Empty if none.>
```

---

## 6. If you get stuck

- If `git status` shows files the brief doesn't list, flag in return report and stage only the listed files. Don't silently broaden scope.
- If the diagnostic-out gitignore appears to be missing/insufficient (large `evaluations.csv` files appearing as untracked), flag in return report; this is a separate small fix worth a follow-up commit but NOT this commit.
- If a substantive edit conflict appears (orchestrator-context.md or phase3e-todo.md were modified by someone else between orchestrator drafting and dispatch), flag in return report; do NOT attempt to merge or revert.
