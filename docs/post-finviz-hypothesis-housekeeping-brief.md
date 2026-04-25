# Post-Finviz-Pool + Hypothesis-Label Housekeeping — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Single small commit closing tracking and documentation drift after both 2026-04-25 parallel-work sessions completed (Finviz-pool per-criterion analysis + trade hypothesis label Phase 3e change). The orchestrator has already made all substantive content edits to tracked files; the implementer's task is purely mechanical — verify the working tree state, stage the listed files, commit. Larger-than-typical content footprint due to substantial framing-update batch from this conversation, but mechanical scope unchanged.
**Expected duration:** ~10 minutes.
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, conventional-commits + no-Claude-co-author + no-amend rules. The orchestrator has updated CLAUDE.md's headline (test count 504 → 822) and Quick Start fast-suite count; verify those edits are present in the staged version.
2. `docs/orchestrator-context.md` — orchestrator handoff file. Has been updated by the orchestrator with:
   - "Last updated" timestamp moved to "post-Finviz-pool + hypothesis-label + binding-constraint analysis settled"
   - "Currently in-flight" rewritten to reflect three SHIPPED items (S&P 1500, Finviz-pool study, hypothesis-label Phase 3e) and refined operator-constraints subsection
   - 7 new entries appended under "Recent decisions and framings" (operational branch as evidence-generation surface, A+ ≠ trades discipline, identification-rate recalibration, binding-constraint-is-capital, chart-pattern-is-encoding-not-throughput, next-horizon-priority-is-operational, 10%-target-math)
   - 1 new lesson under "Lessons captured" (grouping-key-fields-need-canonicalization-at-persistence-boundary)
3. `docs/phase3e-todo.md` — operational backlog. Has been updated by the orchestrator with:
   - The "Proposed next study" entry marked SHIPPED
   - New section "2026-04-25 Finviz-pool study + hypothesis-label follow-ups" appended with: watch-staging UI, longer-window re-run, path-resolution policy (defer indefinitely), single-ticker caveat noted, VIS backfill (operator-driven), future formalization to controlled vocabulary, post-hoc trade analysis CLI tool, chart-pattern-algorithm framing cross-reference

**Skill posture.** Do NOT invoke any `copowers:*` wrapper skills — purely housekeeping. Invoke `superpowers:verification-before-completion` before declaring done. No other skills required.

---

## 1. Scope — one commit, five files

| # | File | State expected | Action |
|---|------|----------------|--------|
| 1 | `CLAUDE.md` | Modified — orchestrator updated headline + Quick Start test count | `git add` |
| 2 | `docs/orchestrator-context.md` | Modified — orchestrator updated multiple sections | `git add` |
| 3 | `docs/phase3e-todo.md` | Modified — orchestrator appended a new section + marked one SHIPPED | `git add` |
| 4 | `docs/trade-hypothesis-label-brief.md` | Untracked — orchestrator-authored brief, not committed by hypothesis-label implementer session | `git add` |
| 5 | `docs/post-finviz-hypothesis-housekeeping-brief.md` | Untracked — this brief itself | `git add` |

### Verification step before staging

```bash
git status
```

**Expected output (in some order):**

- `CLAUDE.md` — modified
- `docs/orchestrator-context.md` — modified
- `docs/phase3e-todo.md` — modified
- `docs/trade-hypothesis-label-brief.md` — untracked
- `docs/post-finviz-hypothesis-housekeeping-brief.md` — untracked

**If unexpected files appear**, do NOT silently stage them. Flag in the return report and proceed only with the five listed above.

**If `research/finviz_pool_analysis/out/` content appears in git status as untracked**, the Finviz-pool study committed its small artifacts directly (per its D3 commit `1ea72f6`); any additional uncommitted output would be a follow-up gitignore concern. Verify the Finviz-pool D3 artifacts are tracked; if uncommitted artifacts appear that look like fresh runs, do NOT stage them and flag in return report.

### Explicitly out of scope

- Any code change.
- Any modification to file content beyond what the orchestrator has already edited.
- Adversarial review (no code, nothing substantive to review).
- VIS hypothesis_label backfill (operator-driven SQL UPDATE; not a commit).
- Any other follow-up item from the 2026-04-25 backlog additions.

---

## 2. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. **No Claude co-author footer. No `--no-verify`. No amending.**
- **Tests:** fast suite green (no code changed; sanity-check with `python -m pytest -m "not slow" -q` before commit). Expected baseline 822 passing (post-`123f83c` from the hypothesis-label session combined with parallel Finviz-pool study).
- **Ruff:** N/A (no code changed).

---

## 3. Stage and commit

```bash
git add CLAUDE.md docs/orchestrator-context.md docs/phase3e-todo.md \
        docs/trade-hypothesis-label-brief.md \
        docs/post-finviz-hypothesis-housekeeping-brief.md
git status  # confirm expected state
```

**Commit message:**

```
docs: post-Finviz-pool + hypothesis-label housekeeping — orchestrator context, backlog, brief tracking, framing updates

- Update CLAUDE.md headline test count (504 → 822) and Quick Start
  fast-suite count, reflecting the substantial test growth from
  Tranche C, parity check, build_watchlist fix, S&P 1500 study,
  Finviz-pool study, and hypothesis-label Phase 3e change.
- Update docs/orchestrator-context.md: in-flight section reflects
  three new SHIPPED items (S&P 1500 Tier 2 result, Finviz-pool
  study, hypothesis-label Phase 3e change). Active-operator-
  constraints subsection refined to capture binding-constraint
  analysis (capital primary; chart-pattern non-binding for
  throughput). Seven new "Recent decisions" entries from this
  conversation: operational-branch-as-evidence-generation,
  A+-identifications-vs-trades discipline, identification-rate
  recalibration to ~40-100/year on Finviz pool, binding-
  constraint-is-capital-not-rate, chart-pattern-algorithm-is-
  encoding-not-throughput, next-horizon-priority-is-operational-
  use, and 10%-return-target-math. One new "Lessons captured"
  entry on grouping-key fields needing canonicalization at the
  persistence boundary (from hypothesis-label R1/R2 review).
- Update docs/phase3e-todo.md: mark previous "Proposed next study"
  as SHIPPED. Append "2026-04-25 Finviz-pool study + hypothesis-
  label follow-ups" section: watch-staging UI for near-A+
  defensible candidates (modest scope, real value), longer-window
  Finviz re-run after 30-60 days, path-resolution policy edge
  case (defer), single-ticker caveat, VIS backfill (operator-
  driven), future controlled-vocabulary formalization, post-hoc
  trade analysis CLI tool (substantive new candidate), chart-
  pattern-algorithm framing cross-reference.
- Track docs/trade-hypothesis-label-brief.md and
  docs/post-finviz-hypothesis-housekeeping-brief.md.
```

Run `python -m pytest -m "not slow" -q` after the commit. Expected green at 822 passing (no code changed).

---

## 4. Done criteria

- One commit on `main` with the message above.
- `CLAUDE.md` modifications are tracked.
- `docs/orchestrator-context.md` modifications are tracked.
- `docs/phase3e-todo.md` modifications are tracked.
- `docs/trade-hypothesis-label-brief.md` is tracked.
- `docs/post-finviz-hypothesis-housekeeping-brief.md` is tracked.
- Fast test suite green at 822 passing (sanity check; no expected change).
- Return report produced.

---

## 5. Return report format

```
## Post-Finviz-pool + hypothesis-label housekeeping return report

### Commit landed
- <SHA> docs: post-Finviz-pool + hypothesis-label housekeeping — orchestrator context, backlog, brief tracking, framing updates

### Files staged
- CLAUDE.md (modified)
- docs/orchestrator-context.md (modified)
- docs/phase3e-todo.md (modified)
- docs/trade-hypothesis-label-brief.md (new)
- docs/post-finviz-hypothesis-housekeeping-brief.md (new)

### Tests
- After: <N> passing, 0 failing (fast suite). Expected: 822 passing baseline unchanged.

### Other untracked files discovered
<List any unexpected untracked files. Empty if git status matched expectations.>

### Open questions for orchestrator
<Empty if none.>
```

---

## 6. If you get stuck

- If `git status` shows files the brief doesn't list, flag in return report and stage only the listed files. Don't silently broaden scope.
- If `research/finviz_pool_analysis/out/` content appears as untracked: verify whether this is the committed D3 artifacts (already tracked per `1ea72f6`) or fresh runs (do NOT include in this commit). If unclear, flag in return report.
- If a substantive edit conflict appears (orchestrator-context.md, phase3e-todo.md, or CLAUDE.md were modified by someone else between orchestrator drafting and dispatch), flag in return report; do NOT attempt to merge or revert.
- If push fails (the project has a remote at `origin/main` post-folder-move): flag in return report; the operator drives push decisions.
