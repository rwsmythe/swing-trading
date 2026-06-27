# Tranche B-ops cleanup — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Two small docs changes and one brief-tracking step, in a single commit. Closes drift from Session 3.
**Expected duration:** ~30 minutes.
**Prepared:** 2026-04-24 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, conventional-commits + no-Claude-co-author rules.
2. `docs/superpowers/specs/2026-04-23-tranche-b-ops-session-1-design.md` — the design spec you'll amend in T1 below. Read §5 ("Stop-form field preservation") and §6 ("Schema, template, VM, and CLI impact summary") back-to-back to understand the amendment rationale.
3. `docs/phase3e-todo.md` — backlog file you'll append to in T2.

**Skill posture.** Do NOT invoke any `copowers:*` wrapper skills — this is a docs-only housekeeping commit. Invoke `superpowers:verification-before-completion` before declaring done. No other skills required.

---

## 1. Scope — one commit, four tasks

| # | Task | Kind |
|---|------|------|
| T1 | Amend spec §6 to strike `force` from `TradeStopFormVM` field list | Docs |
| T2 | Append two new backlog items to `phase3e-todo.md` | Docs |
| T3 | Add a troubleshooting row to `docs/cycle-checklist.md` covering the "restart web server after Python code changes" failure mode | Docs |
| T4 | Verify this brief itself is the only untracked artifact; track it | Docs |

### Out of scope

- Any code change. Zero. The two backlog items describe future code-cleanup work; executing them is NOT this session.
- Any other spec edit, any other phase3e-todo.md edit beyond the specific appends described below.
- Revisiting any Session 2 or Session 3 decisions.

---

## 2. Task specifications

### T1 — Amend spec §6 to strike `force` from `TradeStopFormVM`

**Background.** Session 3 C5 (adversarial-review Round 1 Minor 2) discovered that spec §6 and spec §5 disagreed about whether `TradeStopFormVM` should carry a `force` preservation field. §5's "Decision" states "Force is not auto-ticked by the re-render," which means there is no template consumer for a preserved `force` value. §6's VM impact list included `force` anyway — pattern-matching across all VM preservation fields rather than enforcing §5's explicit decision. The field was dead weight.

Session 3 resolved this by dropping `force` from the VM. The design spec's §6 text now mis-describes the shipped code.

**Edit.** Open `docs/superpowers/specs/2026-04-23-tranche-b-ops-session-1-design.md`. Find the table row in §6 "VM impacts" reading:

```
| `TradeStopFormVM` | +`rationale_options`, `new_stop_input`, `rationale`, `notes`, `force` | T5 + T7 |
```

Replace with:

```
| `TradeStopFormVM` | +`rationale_options`, `new_stop_input`, `rationale`, `notes` | T5 + T7 |
```

(Drop the trailing `, `force``.)

**Then add** a new amendment note at the end of §6 (after the Service-layer impacts subsection and before the `---` section break that precedes §7). Format:

```markdown
### Amendments

- **2026-04-24 — Strike `force` from `TradeStopFormVM` field list.** Session 3 adversarial review (Round 1 Minor 2) found the field dead: §5's "Force is not auto-ticked by the re-render" decision means the template never reads `vm.force`, so preserving it on the VM had no consumer. Field removed in Session 3 C5 (commit `90e730a`). Convention for future sessions: when §3 / §5 "Decision" subsections disagree with §6 "Impact summary" content, Decision wins and §6 is amended.
```

Do not touch any other section of the spec.

### T2 — Append two backlog items to `phase3e-todo.md`

**Background.** Two small cleanup items surfaced in Session 3 that were deliberately out-of-scope for that session (scope discipline held). They belong in the operational backlog.

**Edit.** Open `docs/phase3e-todo.md`. Under the existing `## Tranche B-ops deferred items (2026-04-24)` section (added in Session 3 C0), add two new bullets at the end of that section. Keep the section's existing bullets intact.

**Pattern to match the section's existing style.** The new bullets go at the very end of the section, after the Session 2 adversarial-review items but before the trailing `---` separator.

Text to add:

```markdown
### From Session 3 adversarial review:

- **`TradeEntryFormVM.force` pre-existing dead field** — symmetric to the `TradeStopFormVM.force` removal shipped in Session 3 C5. No template consumer; no re-render usage. Session 3 declined to touch it mid-session per scope discipline. ~5-minute cleanup commit.
- **`(str, Enum)` → `StrEnum` migration across three enums** — `ExitReason`, `EntryRationale`, `StopAdjustRationale` all currently use the `(str, Enum)` pattern and carry `# noqa: UP042`. A single-commit migration clears all three `noqa` comments at once. Cohesive, small, low-priority.
```

### T3 — Add troubleshooting row for stale-server failure mode

**Background.** On 2026-04-24 the operator hit a `jinja2.exceptions.UndefinedError: 'StatusStripVM object' has no attribute 'open_risk_dollars'` on dashboard render after performing an exit. Root cause: the `swing web` server process predated Session 2 deployment. Jinja templates auto-reload from disk and picked up Session 2's new field reference; Python dataclass definitions do not reload without process restart, so the in-memory `StatusStripVM` class lacked the new field that the fresh template expected.

Restarting the web server resolved it instantly. The code on disk was correct and had been since Session 2 (commit `307d338`). This is a deployment failure mode, not a code defect.

A troubleshooting row captures the failure class so the operator recognizes it next time without needing to re-diagnose.

**Edit.** Open `docs/cycle-checklist.md`. Find the `## Troubleshooting quick-ref` section's table (begins around line 200). Add a new row to the table. Preserve existing rows as-is. Insert near the top of the table (it's a high-impact failure; user won't scroll past it):

```markdown
| Dashboard or other template crashes with `UndefinedError: 'X object has no attribute Y'` | Web server process predates latest code; Python dataclass definitions stale while Jinja templates reloaded | Restart `swing web` (Ctrl-C the running process, re-run `swing web`) |
```

Do not change any other part of `cycle-checklist.md`.

### T4 — Track this brief

Verify `docs/tranche-b-ops-cleanup-brief.md` (this file) is the only untracked file relevant to the session:

```bash
git status
```

Stage it:

```bash
git add docs/tranche-b-ops-cleanup-brief.md
```

If other untracked files relevant to recent sessions appear, flag them in the return report rather than silently staging — the orchestrator will triage.

---

## 3. Commit

Stage the four changes:

```bash
git add docs/superpowers/specs/2026-04-23-tranche-b-ops-session-1-design.md docs/phase3e-todo.md docs/cycle-checklist.md docs/tranche-b-ops-cleanup-brief.md
git status
```

Commit message:

```
docs: amend tranche-b-ops design spec, capture session-3 backlog items, add stale-server troubleshooting row

- Strike `force` from TradeStopFormVM field list in spec §6 VM-impacts
  table; add §6 "Amendments" subsection documenting the convention
  (Decision sections win over Impact summary when they disagree).
- Append two Session 3 adversarial-review backlog items to
  docs/phase3e-todo.md under the Tranche B-ops deferred items section:
  TradeEntryFormVM.force dead-field cleanup (~5min), and (str, Enum) →
  StrEnum migration across ExitReason / EntryRationale /
  StopAdjustRationale.
- Add stale-server troubleshooting row to docs/cycle-checklist.md
  (Jinja templates auto-reload; Python dataclasses do not; restart
  required after class/field changes). Live operator hit on 2026-04-24.
- Track docs/tranche-b-ops-cleanup-brief.md.
```

Run `python -m pytest -m "not slow" -q` after the commit (no code changed, expected green; run as sanity check).

---

## 4. Done criteria

- One commit on `main` with the message above.
- Spec §6 VM-impacts table no longer lists `force` for `TradeStopFormVM`.
- Spec §6 has a new "Amendments" subsection documenting the 2026-04-24 amendment.
- `phase3e-todo.md` has two new bullets in the Session 3 subsection.
- `cycle-checklist.md` has a new troubleshooting row for the stale-server failure mode.
- This brief is tracked.
- Fast test suite green.
- Return report produced.

---

## 5. Return report format

```
## Tranche B-ops cleanup return report

### Commit landed
- <SHA> docs: amend tranche-b-ops design spec and capture session-3 backlog items

### Tests
- After: <N> passing, 0 failing (fast suite). No change from 568 baseline expected.

### Deviations from brief
<Anything different, empty if none.>

### Other untracked artifacts discovered
<List any untracked files the orchestrator should know about. Empty if this brief was the only one.>

### Open questions for orchestrator
<Anything the brief under-specified. Empty if none.>
```
