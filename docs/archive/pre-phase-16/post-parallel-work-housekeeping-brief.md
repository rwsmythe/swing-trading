# Post-Parallel-Work Housekeeping — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Single small commit closing tracking and documentation drift after both parallel-work sessions completed (`build_watchlist` mixed-anchor fix and harness-vs-production parity check). The orchestrator has already made all substantive content edits to tracked files; the implementer's task is purely mechanical — verify the working tree state, stage the listed files, and commit.
**Expected duration:** ~10 minutes.
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, conventional-commits + no-Claude-co-author + no-amend rules.
2. `docs/orchestrator-context.md` — the orchestrator handoff file. Has been updated by the orchestrator with current in-flight state (both parallel-work items complete), three new "Recent decisions" entries (Hypothesis 5 closed, Path 1 selected, Bug 7 family closed in web layer), three new "Lessons captured" entries (manifest-integrity generalization, n=1-non-A+-bound on parity claims, brief drafting canonical-template-vs-prose-count), and one new anti-pattern entry (brief internal inconsistency).
3. `docs/phase3e-todo.md` — operational backlog. Has been updated by the orchestrator with a new "2026-04-25 parallel-work follow-ups" section appended (six new follow-ups: stale_banner on /watchlist, deterministic-tiebreaker class fix, multi-run parity, A+-surface parity, parity comparator cadence, PriceFetcher cache-stat introspection).

**Skill posture.** Do NOT invoke any `copowers:*` wrapper skills — purely housekeeping. Invoke `superpowers:verification-before-completion` before declaring done. No other skills required.

---

## 1. Scope — one commit, four files

| # | File | State expected | Action |
|---|------|----------------|--------|
| 1 | `docs/orchestrator-context.md` | Modified — orchestrator updated five sections | `git add` |
| 2 | `docs/phase3e-todo.md` | Modified — orchestrator appended a new section | `git add` |
| 3 | `docs/build-watchlist-mixed-anchor-fix-brief.md` | Untracked — orchestrator-authored brief, not tracked by the implementer session | `git add` |
| 4 | `docs/harness-vs-production-parity-brief.md` | Untracked — orchestrator-authored brief, not tracked by the implementer session | `git add` |
| 5 | `docs/post-parallel-work-housekeeping-brief.md` | Untracked — this brief itself | `git add` |

### Verification step before staging

```bash
git status
```

**Expected output (in some order):**

- `docs/orchestrator-context.md` — modified
- `docs/phase3e-todo.md` — modified
- `docs/build-watchlist-mixed-anchor-fix-brief.md` — untracked
- `docs/harness-vs-production-parity-brief.md` — untracked
- `docs/post-parallel-work-housekeeping-brief.md` — untracked

**If unexpected files appear**, do NOT silently stage them. Flag in the return report and proceed only with the five listed above.

**If `research/parity/out/` content appears in git status as untracked**, that's a gitignore gap from the parity-check session — the per-run `evaluations.csv`-style artifacts (if any) should be gitignored. Verify the parity-out `.gitignore` is in place; if not, that's a separate small fix worth flagging in the return report (but do NOT add the parity-out content to this commit).

### Explicitly out of scope

- Any code change.
- Any modification to file content beyond what the orchestrator has already edited.
- Adversarial review (no code, nothing substantive to review).
- Any other follow-up item from the 2026-04-25 parallel-work follow-ups list.
- Any work related to the planned project-folder move from Drive to `c:\Users\rwsmy\swing-trading\` (operator-driven; sequenced AFTER this commit lands).
- Any work related to the GitHub remote setup (the private repo `https://github.com/rwsmythe/swing-trading` already exists empty; `git remote add` and first push are sequenced AFTER the folder move).

---

## 2. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. **No Claude co-author footer. No `--no-verify`. No amending.**
- **Tests:** fast suite green (no code changed; sanity-check with `python -m pytest -m "not slow" -q` before commit). Expected baseline 755 passing (post-`1a88fb7` from the parity-check session).
- **Ruff:** N/A (no code changed).

---

## 3. Stage and commit

```bash
git add docs/orchestrator-context.md docs/phase3e-todo.md \
        docs/build-watchlist-mixed-anchor-fix-brief.md \
        docs/harness-vs-production-parity-brief.md \
        docs/post-parallel-work-housekeeping-brief.md
git status  # confirm expected state
```

**Commit message:**

```
docs: post-parallel-work housekeeping — orchestrator context, backlog, brief tracking

- Update docs/orchestrator-context.md: in-flight section reflects both
  parallel-work items SHIPPED and no work in flight; three new "Recent
  decisions" entries (Hypothesis 5 closed at Tier 1; Path 1 selected
  for residual-gap question; Bug 7 family confirmed closed in web
  layer); three new "Lessons captured" entries (manifest-integrity
  generalization; n=1 non-A+ sample bounds parity claims; brief
  drafting canonical-template vs prose-count); one new anti-pattern
  entry on brief internal inconsistency.
- Update docs/phase3e-todo.md with new "2026-04-25 parallel-work
  follow-ups" section: stale_banner on /watchlist, deterministic
  tiebreaker class-fix (defer indefinitely), multi-run parity
  characterization, A+-surface-exercising parity run, parity comparator
  cadence (recommend never-again unless triggering change), PriceFetcher
  cache-stat introspection.
- Track docs/build-watchlist-mixed-anchor-fix-brief.md,
  docs/harness-vs-production-parity-brief.md, and
  docs/post-parallel-work-housekeeping-brief.md.
```

Run `python -m pytest -m "not slow" -q` after the commit. Expected green at 755 passing (no code changed).

---

## 4. Done criteria

- One commit on `main` with the message above.
- `docs/orchestrator-context.md` modifications are tracked.
- `docs/phase3e-todo.md` modifications are tracked.
- `docs/build-watchlist-mixed-anchor-fix-brief.md` is tracked.
- `docs/harness-vs-production-parity-brief.md` is tracked.
- `docs/post-parallel-work-housekeeping-brief.md` is tracked.
- Fast test suite green (sanity check; no expected change from baseline 755).
- Return report produced.

---

## 5. Return report format

```
## Post-parallel-work housekeeping return report

### Commit landed
- <SHA> docs: post-parallel-work housekeeping — orchestrator context, backlog, brief tracking

### Files staged
- docs/orchestrator-context.md (modified)
- docs/phase3e-todo.md (modified)
- docs/build-watchlist-mixed-anchor-fix-brief.md (new)
- docs/harness-vs-production-parity-brief.md (new)
- docs/post-parallel-work-housekeeping-brief.md (new)

### Tests
- After: <N> passing, 0 failing (fast suite). Expected: 755 passing baseline unchanged.

### Other untracked files discovered
<List any unexpected untracked files. Empty if git status matched expectations.>

### Open questions for orchestrator
<Empty if none.>
```

---

## 6. If you get stuck

- If `git status` shows files the brief doesn't list, flag in return report and stage only the listed files. Don't silently broaden scope.
- If a `research/parity/out/` gitignore appears to be missing/insufficient (large `evaluations.csv`-style files appearing as untracked), flag in return report; this is a separate small fix worth a follow-up commit but NOT this commit.
- If a substantive edit conflict appears (orchestrator-context.md or phase3e-todo.md were modified by someone else between orchestrator drafting and dispatch), flag in return report; do NOT attempt to merge or revert.
