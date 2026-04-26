# Post-Monday-Prep Housekeeping — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Single small commit closing tracking and documentation drift after the 2026-04-25 evening Monday-prep operational batch (4 implementer sessions: weekly DB backup, `swing trade analyze` CLI, hypothesis recommendation backend, hypothesis recommendation frontend). The orchestrator has already made all substantive content edits to tracked files; the implementer's task is purely mechanical — verify the working tree state, stage the listed files, commit. Larger content footprint than typical housekeeping due to the substantial framing-update batch from this conversation, but mechanical scope unchanged.
**Expected duration:** ~10 minutes.
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, conventional-commits + no-Claude-co-author + no-amend rules. Orchestrator has updated CLAUDE.md's headline (test count 822 → 969; mention of hypothesis-investigation engine being operational) and Quick Start fast-suite count.
2. `docs/orchestrator-context.md` — orchestrator handoff file. Has been updated by the orchestrator with:
   - "Last updated" timestamp moved to "post-hypothesis-engine + backup + analyze-CLI; full Monday-prep operational batch shipped"
   - "Currently in-flight" rewritten to reflect 4 new SHIPPED items (3a backup, 3c analyze CLI, hyp1 backend, hyp2 frontend) alongside the morning's 3 SHIPPED items
   - 3 new entries appended under "Recent decisions and framings": hypothesis investigation plan v0.1 OPERATIONAL, prefix-label convention (operator-facing), hypothesis-recommendation-engine framing (dashboard PROPOSES, operator DISPOSES)
   - 2 new entries appended under "Lessons captured": transient parallel-execution test errors resolve when all commits land, production-gating-aware-vs-literal-spec mismatch is a recurring class (3 occurrences documented)
3. `docs/phase3e-todo.md` — operational backlog. Has been updated by the orchestrator with:
   - Multiple items marked SHIPPED 2026-04-25 (weekly DB backup, watch-staging UI [subsumed into hyp engine], post-hoc trade analysis CLI)
   - New section "2026-04-25 hypothesis-engine + analyze + backup follow-ups" appended with: optional WatchlistVM extension (hyp2-declined per scope discipline), monitor for first hypothesis closure → revisit longer-horizon planning, registry-mutation discipline (operator-facing convention), commit-attribution housekeeping (leave as-is per orchestrator-context.md lesson), cross-contamination commit-title misattribution note

**Skill posture.** Do NOT invoke any `copowers:*` wrapper skills — purely housekeeping. Invoke `superpowers:verification-before-completion` before declaring done. No other skills required.

---

## 1. Scope — one commit, six files

| # | File | State expected | Action |
|---|------|----------------|--------|
| 1 | `CLAUDE.md` | Modified — orchestrator updated headline + Quick Start test count | `git add` |
| 2 | `docs/orchestrator-context.md` | Modified — orchestrator updated multiple sections (continuation of edits already in working tree from earlier in conversation) | `git add` |
| 3 | `docs/phase3e-todo.md` | Modified — orchestrator marked items SHIPPED + appended new section | `git add` |
| 4 | `docs/weekly-db-backup-brief.md` | Untracked — orchestrator-authored brief, not committed by 3a implementer | `git add` |
| 5 | `docs/trade-analyze-cli-brief.md` | Untracked — orchestrator-authored brief, not committed by 3c implementer | `git add` |
| 6 | `docs/hypothesis-recommendation-backend-brief.md` | Untracked — orchestrator-authored brief, not committed by hyp1 implementer | `git add` |
| 7 | `docs/hypothesis-recommendation-frontend-brief.md` | Untracked — orchestrator-authored brief, not committed by hyp2 implementer | `git add` |
| 8 | `docs/post-monday-prep-housekeeping-brief.md` | Untracked — this brief itself | `git add` |

**Eight files total** (3 modified + 5 untracked).

### Verification step before staging

```bash
git status
```

**Expected output (in some order):**

- `CLAUDE.md` — modified
- `docs/orchestrator-context.md` — modified
- `docs/phase3e-todo.md` — modified
- `docs/weekly-db-backup-brief.md` — untracked
- `docs/trade-analyze-cli-brief.md` — untracked
- `docs/hypothesis-recommendation-backend-brief.md` — untracked
- `docs/hypothesis-recommendation-frontend-brief.md` — untracked
- `docs/post-monday-prep-housekeeping-brief.md` — untracked

**If unexpected files appear**, do NOT silently stage them. Flag in the return report and proceed only with the eight listed above. Possible: `~/swing-data/backups/` path may have produced new artifacts during pipeline runs; those are NOT in the repo (separate filesystem).

### Explicitly out of scope

- Any code change.
- Any modification to file content beyond what the orchestrator has already edited.
- Adversarial review (no code, nothing substantive to review).
- Cross-contamination commit cleanup (commits `375344f` and `43b4d35` have mixed-scope titles; per orchestrator-context.md 2026-04-25 lesson, leave as-is).
- Any work related to operator's actual Monday trading (operator-action; not commit scope).
- Any other follow-up item from the 2026-04-25 backlog additions.

---

## 2. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. **No Claude co-author footer. No `--no-verify`. No amending.**
- **Tests:** fast suite green (no code changed; sanity-check with `python -m pytest -m "not slow" -q` before commit). Expected baseline 969 passing (post-`fe270a6`).
- **Ruff:** N/A (no code changed).

---

## 3. Stage and commit

```bash
git add CLAUDE.md docs/orchestrator-context.md docs/phase3e-todo.md \
        docs/weekly-db-backup-brief.md \
        docs/trade-analyze-cli-brief.md \
        docs/hypothesis-recommendation-backend-brief.md \
        docs/hypothesis-recommendation-frontend-brief.md \
        docs/post-monday-prep-housekeeping-brief.md
git status  # confirm expected state
```

**Commit message:**

```
docs: post-Monday-prep housekeeping — orchestrator context, backlog, brief tracking, framing updates

Closes documentation drift after the 2026-04-25 evening Monday-prep
operational batch shipped four implementer sessions: weekly DB
backup (commits 4a565c6..1540489), swing trade analyze CLI (commits
375344f cross-contaminated + 2815daa + 4c2fdbd..d5b1753), hypothesis
recommendation backend (commits 7cd1d72..6866864), and hypothesis
recommendation frontend (commits b24506b..fe270a6).

- Update CLAUDE.md headline test count (822 → 969) and Quick Start
  fast-suite count; mention hypothesis-investigation engine being
  operational.
- Update docs/orchestrator-context.md: in-flight section now reflects
  cumulative 7 SHIPPED items today (3 morning + 4 evening); 4 new
  "Recent decisions" entries on hypothesis-investigation plan v0.1
  operational, prefix-label convention (operator-facing), and
  recommendation-engine PROPOSES/operator DISPOSES framing; 2 new
  "Lessons captured" entries on transient parallel-execution test
  errors and the recurring production-gating-aware-vs-literal-spec
  mismatch class (3 occurrences documented).
- Update docs/phase3e-todo.md: mark weekly DB backup, watch-staging
  UI (subsumed into hyp engine), and post-hoc trade analyze CLI as
  SHIPPED. Append new section "2026-04-25 hypothesis-engine +
  analyze + backup follow-ups" with: optional WatchlistVM extension,
  monitor-for-first-hypothesis-closure planning revisit, registry-
  mutation discipline (operator-facing convention), commit-
  attribution housekeeping (leave as-is per lesson).
- Track docs/weekly-db-backup-brief.md, docs/trade-analyze-cli-brief.md,
  docs/hypothesis-recommendation-backend-brief.md, docs/hypothesis-
  recommendation-frontend-brief.md, and
  docs/post-monday-prep-housekeeping-brief.md.
```

Run `python -m pytest -m "not slow" -q` after the commit. Expected green at 969 passing (no code changed).

---

## 4. Done criteria

- One commit on `main` with the message above.
- All 3 modified files staged.
- All 5 untracked briefs staged.
- Fast test suite green at 969 passing (sanity check; no expected change).
- Return report produced.

---

## 5. Return report format

```
## Post-Monday-prep housekeeping return report

### Commit landed
- <SHA> docs: post-Monday-prep housekeeping — orchestrator context, backlog, brief tracking, framing updates

### Files staged
- CLAUDE.md (modified)
- docs/orchestrator-context.md (modified)
- docs/phase3e-todo.md (modified)
- docs/weekly-db-backup-brief.md (new)
- docs/trade-analyze-cli-brief.md (new)
- docs/hypothesis-recommendation-backend-brief.md (new)
- docs/hypothesis-recommendation-frontend-brief.md (new)
- docs/post-monday-prep-housekeeping-brief.md (new)

### Tests
- After: <N> passing, 0 failing (fast suite). Expected: 969 passing baseline unchanged.

### Other untracked files discovered
<List any unexpected untracked files. Empty if git status matched expectations.>

### Open questions for orchestrator
<Empty if none.>
```

---

## 6. If you get stuck

- If `git status` shows files the brief doesn't list, flag in return report and stage only the listed files.
- If a substantive edit conflict appears (CLAUDE.md, orchestrator-context.md, or phase3e-todo.md were modified by someone else between orchestrator drafting and dispatch), flag in return report; do NOT attempt to merge or revert.
- If push fails (the project has a remote at `origin/main` post-folder-move): flag in return report; the operator drives push decisions.
