# tos-import silent zero-result diagnostic — INVESTIGATION-FIRST brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Diagnose why `swing tos-import --csv "...\2026-05-08-AccountStatement.csv"` produces all-zero counters (`Cash: 0 new, 0 duplicate; Fills: matched=0, already-reconciled=0, price-mismatch=0, unmatched OPEN=0, unmatched CLOSE=0`) despite the operator having open trades + recent stop-change activity that should appear in the CSV. Then add operator-facing observability (`--verbose` flag) so future silent-zero results become observable-with-context. This is **INVESTIGATION-FIRST** per orchestrator-context.md §"Bug-fix briefs and operator-confirmation gate" — implementer surfaces findings + waits for operator confirmation BEFORE designing any non-trivial parser fix.

**Expected duration:**
- Investigation phase: 30-60 min
- Operator-confirmation gate: ~5 min orchestrator-paced
- Fix + hardening phase: 30-90 min depending on root cause
- Total: 1-3 hr

**Skill posture:**
- DO NOT invoke `superpowers:writing-plans` upfront — investigation might surface a one-line fix that doesn't warrant a plan dispatch.
- Use `superpowers:systematic-debugging` to structure the investigation phase.
- Use `superpowers:test-driven-development` for any code changes (fix + hardening).
- Adversarial review via `copowers:adversarial-critic` after fix lands; iterate to NO_NEW_CRITICAL_MAJOR. Investigation-first dispatches typically need 2-3 rounds (empirical work, not architectural).
- DO NOT invoke `copowers:executing-plans` wrapper — this is bug-fix dispatch shape, not plan-driven feature work.

---

## §0 Read first

### §0.1 Backlog entry (canonical context)
- `docs/phase3e-todo.md` §3e.12 — full context, investigation steps already enumerated, possible mechanisms enumerated.

### §0.2 Code surface (the parser)
- `swing/journal/tos_import.py` — current parser. Survey: section detection logic; row tokenization; transaction extraction; what counts as a "match."
- `swing/cli.py:1511-1564` — `tos_import_cmd` (the CLI surface that produces the operator's all-zero output).

### §0.3 Test fixtures
- `tests/fixtures/tos/synthetic-tos.csv` — synthetic fixture; first verify it currently passes (`python -m pytest tests/journal/test_tos_import.py -v`).
- `tests/journal/test_tos_import.py` — existing test surface.

### §0.4 Operator's actual CSV (the artifact that triggered this)
- `thinkorswim/2026-05-08-AccountStatement.csv` — the file the operator ran against. Read it raw (binary mode if needed for BOM/encoding inspection).

### §0.5 Lesson context (this is a recurring class of failure)
- CLAUDE.md gotcha "TOS-import TRD-as-withdrawal fix + Excel-quoted REF cleanup" (2026-04-30, commit `c9159c7`) — prior parser breakage on real-world export format. Same family.
- Archived lesson "Synthetic-fixture coverage gap can mask real-world data shape bugs even with full test-suite passing" (2026-05-01, in `docs/orchestrator-context-archive.md`) — same family. The synthetic fixture passing tests does NOT guarantee the parser handles real-world Schwab/TOS exports.
- The operator-witnessed gate pattern: empirical reproduction of operator's exact symptom is the binding ground truth — TestClient / synthetic fixtures verify structure but NOT real-world data shape.

---

## §1 Investigation phase (BEFORE designing any fix)

Use `superpowers:systematic-debugging` to structure this. Document findings as you go.

### §1.1 Verify synthetic fixture parses correctly
```powershell
python -m pytest tests/journal/test_tos_import.py -v
```
Expected: existing tests pass. If they DON'T, that's a different problem (recent regression); halt + escalate.

### §1.2 Inspect operator's actual CSV
- File size + encoding (BOM? UTF-8? UTF-16? CRLF vs LF?)
- Section headers present (`Cash Balance`, `Account Order History`, `Account Trade History`, etc.)
- Row counts per section
- Sample rows (first 2-3 of each section)

If you can't read the file (e.g., locked), halt + ask operator to provide structure summary.

### §1.3 Trace the parser
For each section the parser tries to extract:
- What section header does it look for?
- How does it tokenize rows?
- What's the predicate that determines "this row is a fill"?

Identify the FIRST place the pipeline produces an empty result. That's likely the mechanism.

### §1.4 Diff synthetic vs real-world structure
If §1.2 reveals the real-world CSV has a different structure than the synthetic fixture (different section headers, different column order, different encoding), that's the mechanism.

### §1.5 Run with diagnostic prints (temporarily)
Add temporary `print()` statements (or `logging.debug` if there's already a logger) inside the parser to surface:
- Section headers detected
- Row count per section
- Sample tokenization output for one row from each section

Do NOT commit these temporary prints — they're investigation scaffolding.

---

## §2 Operator-confirmation gate (BINDING)

**This gate is binding.** Do NOT proceed to fix-phase without operator confirmation.

After investigation phase, draft a "mechanism candidate" message containing:
- The mechanism you believe is causing the bug (specific: "Section header `Account Trade History` was renamed to `Trade History` in this Schwab/TOS export, causing the parser's `_find_section()` at line N to return None")
- The reproduction sequence you used to confirm it (concrete steps + commands)
- Specific evidence (operator's CSV section headers found vs. parser's expected headers; row counts per section; encoding details)
- Explicit confirmation request: "Does this match what you see when you open the CSV?"
- Proposed fix scope estimate (one-line constant change vs. parser refactor vs. multi-section overhaul)

Halt. Wait for operator confirmation.
- If operator confirms: proceed to §3 (fix + hardening).
- If operator says "that's not what I see": repeat §1 with the new information.
- If proposed fix scope > 2 hr: halt + escalate to orchestrator. Ship hardening (§3.2) only; fix becomes a separate dispatch.

---

## §3 Fix + hardening phase

### §3.1 Fix the identified mechanism

Per the agreed-upon fix scope from §2 gate. TDD discipline:
1. Add a discriminating test that uses operator's REAL CSV (sanitized — strip account numbers, dollar amounts can stay rounded; keep structural shape) as a NEW fixture at `tests/fixtures/tos/real-world-2026-05-08.csv` or similar. Test asserts parser produces non-zero matched fills (or whatever the correct count is).
2. Verify test fails RED on the unfixed parser.
3. Implement the fix.
4. Verify test passes GREEN.
5. Verify existing synthetic-fixture test STILL passes.
6. Commit with `fix(journal): tos-import — <mechanism> (closes 3e.12)` style message.

**If the fix is non-trivial** (>30 min implementation OR touches >1 module): halt before §3.2; surface the proposed implementation to operator + wait for go-ahead. Don't ship a multi-file refactor under an "investigation-first" brief.

### §3.2 Hardening: --verbose CLI flag

Add a `--verbose` flag to `swing tos-import` that prints (in addition to the current summary):
- Per-section: header detected (yes/no), row count, sample row
- Encoding detected (UTF-8 / UTF-16 / etc., BOM present)
- Total bytes parsed
- Any rows skipped + why (one-line reason per skipped-row category)

This is the "operator-observability for future format drifts" deliverable. Even if §3.1 fixes the immediate bug, §3.2 ships ALWAYS — it's the recurrence-prevention layer.

Discriminating tests:
- `--verbose` produces additional output beyond default
- Default output (no `--verbose`) is byte-identical to current behavior (backward-compat assertion)
- `--verbose` correctly identifies an empty section vs. a missing section vs. a section with N rows

Commit: `feat(cli): tos-import --verbose flag for per-section observability (3e.12 hardening)`

---

## §4 Worktree + binding conventions

### §4.1 Worktree setup

**Worktree path:** `.worktrees/tos-import-diagnostic/` at repo root (NOT `.claude/worktrees/...`). Per Phase 5/6/7/8 precedent + 2026-05-08 lesson on worktree directory path discipline.

**Branch name:** `tos-import-diagnostic`.

**BASELINE_SHA:** `f44b628` (current HEAD; verify via `git rev-parse main`).

```powershell
cd C:\Users\rwsmy\swing-trading
git worktree add .worktrees/tos-import-diagnostic -b tos-import-diagnostic main
cd .worktrees/tos-import-diagnostic
```

**Verify-command for runtime checks:** `$env:PYTHONPATH = "."; python -m swing.cli tos-import --csv "...\2026-05-08-AccountStatement.csv" --dry-run` from inside the worktree dir. Per CLAUDE.md gotcha + Phase 5 lesson on editable-install vs worktree.

### §4.2 Marker-file workflow (orchestrator-managed)

Orchestrator creates `.copowers-subagent-active` before subagent dispatch; removes before adversarial-critic. Subagents physically cannot invoke Codex per the global PreToolUse hook. Implementer does NOT touch the marker file.

### §4.3 Commit discipline

- Explicit `git add <file>` per commit. NO `git add -A`. Per Phase 8 R1 Critical 1 lesson.
- Conventional-commits with scope: `fix(journal):`, `feat(cli):`, `test(journal):`, `style(journal):`.
- For adversarial-fix commits: `fix(journal): Codex R1 Major 1 — <description>`.
- For internal-Codex commits (if any): `fix(journal): Codex R1 Major 1 (internal) — <description>`.

### §4.4 Test + ruff baseline

- Pre-dispatch: 2090 fast tests + 1 skipped; ruff `swing/` baseline 78.
- Post-dispatch: 2090 + N (N ≥ 2 — at least one §3.1 discriminating + at least one §3.2 verbose-flag test).
- Ruff baseline 78 must be preserved (no new violations; no incidental fixes to baseline).

---

## §5 Adversarial review (target + watch items)

**Target:** NO_NEW_CRITICAL_MAJOR after 2-3 Codex rounds. Investigation-first dispatches typically converge fast — empirical work, not architectural.

**Watch items the brief should pass to adversarial-critic:**

1. **Real-world fixture, not synthetic.** Does the new test in §3.1 use a sanitized version of the operator's actual CSV, or did the implementer fall back to extending the synthetic fixture? The CLAUDE.md gotcha "Synthetic-fixture coverage gap" is BINDING — the discriminating test MUST exercise real-world structure.
2. **Backward-compat default.** Does the `--verbose` flag preserve byte-identical default output when omitted? Existing scripts/tests that grep the CLI output should not break.
3. **Doesn't introduce new silent-fail.** Does the fix preserve "section absent → warn" semantics, OR does it silently accept absent sections under some new condition?
4. **No `git add -A`.** Per Phase 8 R1 Critical 1 lesson.
5. **No mid-dispatch commits to main.** Per "no main-side commits while executing-plans dispatch is in flight" lesson — orchestrator-side. Implementer-side: all commits land on the worktree branch, not main.
6. **Operator-confirmation gate landed.** Did the implementer actually halt at §2 + wait for operator confirmation, or skip the gate? The return report MUST document the operator-confirmation exchange (or escalate-and-halted state) per investigation-first discipline.

---

## §6 Done criteria

- [ ] Investigation findings documented in §1 + presented to operator at §2 gate.
- [ ] Operator-confirmation gate PASSED (or implementation halted at gate per investigation-first protocol).
- [ ] Fix landed in §3.1 with discriminating test using real-world CSV structure.
- [ ] `--verbose` flag landed in §3.2 with backward-compat assertion test.
- [ ] `python -m pytest -m "not slow" -q` shows 2090 + N passing (N ≥ 2).
- [ ] `ruff check swing/` shows 78 violations (baseline preserved).
- [ ] Adversarial review: NO_NEW_CRITICAL_MAJOR.
- [ ] Operator-witnessed verification: operator runs `swing tos-import --csv "...\2026-05-08-AccountStatement.csv" --dry-run` AND `--verbose` AND confirms the output now reflects the actual CSV state (non-zero where appropriate; clear diagnostic for any zero sections).
- [ ] Worktree branch ready for orchestrator merge.

---

## §7 Return report format

```markdown
# tos-import diagnostic — return report

## HEAD
{worktree branch HEAD SHA + branch name}

## Investigation findings
- Mechanism identified: {one-sentence summary}
- Reproduction: {commands + expected vs. actual}
- Evidence: {section-header diff, encoding, row counts}

## Operator-confirmation gate
- Mechanism candidate sent: {timestamp + summary}
- Operator confirmation: {timestamp + verbatim or paraphrase}
- Outcome: {gate-passed / gate-failed-and-re-investigated / halted-at-gate-fix-too-large}

## Fix landed (§3.1)
- {commit SHAs + one-line per commit}
- New test: {path + what it asserts}

## Hardening landed (§3.2)
- {commit SHAs + one-line per commit}
- New test: {path + what it asserts}

## Adversarial review chain
- R1: {N critical / N major / N minor} → {disposition}
- ...
- R-final: NO_NEW_CRITICAL_MAJOR

## Tests + ruff
- {baseline N} → {final N + delta}
- ruff baseline 78: {preserved / not-preserved}

## Operator-witnessed verification
- {PENDING (operator runs post-merge) / PASSED}

## Open questions for orchestrator
- {none / list}
```

---

## §8 If you get stuck

- **Investigation phase finds nothing wrong with parser AND CSV has actual transactions:** halt + escalate. The mechanism may be in the FILE (truncated / corrupted) rather than the parser.
- **Operator-confirmation gate produces conflicting evidence** ("the CSV has 8 trades but parser shows 0"): re-investigate with the operator's specific evidence; don't assume your investigation was correct.
- **Fix exceeds 2 hr scope:** halt + escalate. Ship §3.2 hardening only; the fix becomes a separate writing-plans dispatch.
- **`--verbose` flag implementation reveals deeper architectural issues** (e.g., parser is not sectioned cleanly enough to surface per-section row counts): ship a minimal-viable `--verbose` (just total rows + sections detected by header-string match) AND escalate the architectural concern as a separate backlog entry.
- **Adversarial review surfaces unrelated issues in `swing/journal/tos_import.py`:** flag in return report; do NOT fix mid-dispatch (per scope discipline). Banked as follow-up.

---

## §9 Dispatch metadata

- **Project root:** `c:\Users\rwsmy\swing-trading`
- **Base SHA:** `f44b628` (current main HEAD; verify via `git rev-parse main`)
- **Worktree path:** `.worktrees/tos-import-diagnostic/`
- **Worktree branch:** `tos-import-diagnostic`
- **Pre-dispatch test baseline:** 2090 fast tests + 1 skipped
- **Pre-dispatch ruff baseline:** 78
- **Pre-dispatch schema:** v16 (unchanged; this dispatch does NOT touch schema)
- **Brief target line range:** ~250-350 lines (this brief is ~290 lines; target met)
