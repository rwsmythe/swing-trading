# Tranche B-cleanup — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Housekeeping commit before Tranche B proper begins. Session artifacts get tracked, the duplicate rebuttal file gets deleted, and one new gotcha lands in CLAUDE.md.
**Expected duration:** ~10 minutes.
**Prepared:** 2026-04-23 by orchestrator instance.

---

## 0. Read first

1. Read `CLAUDE.md`. Note especially the Gotchas section (you will append to it in T4) and the conventional-commits + no-Claude-co-author-footer rules.
2. Read `docs/tranche-a-brief.md` for context on what Tranche A shipped (you will track this file in T3).

**Skill posture.** Do NOT invoke the `copowers:*` wrapper skills — this is a housekeeping session, not design work. Invoke the `superpowers:verification-before-completion` skill before declaring done. No other skills required.

---

## 1. Tranche B-cleanup scope

Exactly four small artifacts, one commit.

| # | Artifact | Kind |
|---|----------|------|
| T1 | Delete duplicate rebuttal file at top of `reference/` | Docs |
| T2 | Track `docs/Bugs.txt` (currently untracked) | Docs |
| T3 | Track `docs/tranche-a-brief.md` (currently untracked) | Docs |
| T4 | Append template-duplication-drift gotcha to CLAUDE.md | Docs |

### Explicitly out of scope

- Any modification to the other Gotchas, Architecture, Invariants, or Conventions sections of CLAUDE.md beyond the one append in T4.
- Any changes to other untracked files you may notice (e.g., anything under `reference/Future Work/` — Tranche A archival left the intended state).
- Any Tranche B-ops or Tranche B-research work — those are separate briefs.

---

## 2. Binding conventions

- **Branch:** `main`. No feature branches.
- **Commits:** conventional-commits. **No Claude co-author footer.** **No `--no-verify`.** **No amending.**
- **Tests:** fast suite (`python -m pytest -m "not slow" -q`) must remain green. This session makes no code changes, but run it anyway as a final check before commit.
- **Ruff:** no new violations (not applicable — no code changes).

---

## 3. Task specifications

### T1 — Delete duplicate rebuttal file

**File to delete:** `reference/2026-04-22-rebuttal-critique-and-implementation-proposal.md`

This file is a top-level duplicate of the canonical copy at `reference/Future Work/2026-04-22-rebuttal-critique-and-implementation-proposal.md` (committed in Tranche A's Commit 1). The `reference/Future Work/` location is the canonical strategy-document location; the top-level copy is stray.

**Verify before deleting** that the two files have identical content:

```bash
diff "reference/2026-04-22-rebuttal-critique-and-implementation-proposal.md" "reference/Future Work/2026-04-22-rebuttal-critique-and-implementation-proposal.md"
```

Expected: no output (identical).

If `diff` shows differences, **stop and flag in the return report.** Do not delete; the orchestrator needs to decide which version is correct.

If identical, delete via `rm` (the file is untracked — no `git rm` needed; just remove from filesystem). It will simply not be added.

### T2 — Track `docs/Bugs.txt`

Verify `docs/Bugs.txt` exists and is untracked:

```bash
git ls-files docs/Bugs.txt
# expect: no output (not tracked)
ls "docs/Bugs.txt"
# expect: file exists
```

Stage it via `git add docs/Bugs.txt`. No edits — commit as-is.

### T3 — Track `docs/tranche-a-brief.md`

Same pattern as T2. Verify it exists and is untracked, then `git add docs/tranche-a-brief.md` without edits.

### T4 — Template-duplication-drift gotcha in CLAUDE.md

Append this bullet to the end of the **Gotchas** section in `CLAUDE.md` (the section starts with `## Gotchas` and contains bullets beginning with `**yfinance rate-limits.**`, `**Test-count drift in plan docs.**`, etc.).

Insert the new bullet as the **last** entry of the Gotchas section:

```markdown
- **HTMX OOB-swap partials that hand-duplicate full-page markup drift silently.** The refresh-now `prices_refresh_container.html.j2` partial hand-duplicated the watchlist `<table>` markup without the `<h2>` heading and "Show all (N)" link that live in `watchlist_top5_section.html.j2`. On OOB swap the heading vanished and the watchlist butted up against the Open Positions table; a hard browser refresh restored the layout because full-page render used the canonical partial. Cosmetic symptom, structural cause. Fix: OOB-swap partials and the full-page render must go through the SAME `{% include %}` target, not hand-duplicated markup. If you find yourself copying JSX/HTML fragments between two partials to avoid an include, stop — the drift failure is a matter of when, not if.
```

Match the surrounding bullets' style exactly (bold lead sentence, then 2–4 explanation sentences). Do NOT modify any other gotcha, any other section, or the position/ordering of existing bullets.

---

## 4. Commit

Stage the three changes (delete of `reference/2026-04-22-...md` happens via filesystem `rm`, not `git rm`, since the file is untracked — the deletion is a no-op for git; you're staging `docs/Bugs.txt`, `docs/tranche-a-brief.md`, and the `CLAUDE.md` edit):

```bash
git add docs/Bugs.txt docs/tranche-a-brief.md CLAUDE.md
git status  # verify expected state
```

Commit message:

```
docs: track tranche A session artifacts and document template-duplication gotcha

- Track docs/Bugs.txt (source-of-truth bug list referenced by Tranche A).
- Track docs/tranche-a-brief.md (historical record of Tranche A scoping).
- Delete stray duplicate of rebuttal-critique file from reference/ top level;
  canonical copy already lives at reference/Future Work/.
- Append template-duplication-drift gotcha to CLAUDE.md Gotchas section
  (new failure class surfaced by Tranche A Bug 1 root cause).
```

Run `python -m pytest -m "not slow" -q` after the commit. Must be green (no code changed, so no reason it wouldn't be, but verify).

---

## 5. Done criteria

- One commit on `main` with the message above.
- `reference/2026-04-22-rebuttal-critique-and-implementation-proposal.md` (top-level) no longer exists.
- `docs/Bugs.txt` and `docs/tranche-a-brief.md` are tracked.
- CLAUDE.md Gotchas section has exactly one new bullet at the end.
- Fast test suite green.
- Return report produced.

---

## 6. Return report format

```
## Tranche B-cleanup return report

### Commit landed
- <SHA> docs: track tranche A session artifacts and document template-duplication gotcha

### Tests
- After: <N> passing, 0 failing (fast suite). No change from baseline expected.

### Deviations from brief
<Anything different from the brief, and why. Empty if none.>

### Diff summary
- Deleted: reference/2026-04-22-rebuttal-critique-and-implementation-proposal.md
- Added:   docs/Bugs.txt (<NN> lines)
- Added:   docs/tranche-a-brief.md (<NNN> lines)
- Modified: CLAUDE.md (+<N> lines, Gotchas append only)

### Open questions for orchestrator
<Anything the brief under-specified. Empty if none.>
```

---

## 7. If `diff` in T1 shows differences

Do NOT delete either file. Report the diff contents in the return report and stop T1. Complete T2, T3, T4 and commit those three changes under a revised message omitting the "Delete stray duplicate" bullet. Orchestrator will triage the diff separately.
