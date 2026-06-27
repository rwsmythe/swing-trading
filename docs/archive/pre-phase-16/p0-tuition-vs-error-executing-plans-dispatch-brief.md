# P0 — Tuition-vs-Error Instrumentation — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance, no prior conversation context.
**Mission:** IMPLEMENT the Codex-converged `entry_intent` plan, task by task, in an isolated worktree. The plan is
BINDING; the spec is binding behind it. Converge through adversarial Codex review, then return for
research-director QA + merge. **Do NOT merge to `main` yourself.**
**Prepared:** 2026-06-10 by the research-director/evaluator instance, after QA-PASS of the writing-plans return
(the four-era projection / INSERT-branch resolution, the no-count-sweep simplification, and the task shape all
independently verified against disk; the two-call execution-discipline fetch is accepted as primary).
**Phase:** copowers:executing-plans (wraps superpowers:subagent-driven-development + adversarial Codex review).

---

## 0. Read first

1. `CLAUDE.md` — conventions (conventional commits; NO co-author footer; NO `--no-verify`; TDD) + the gotcha
   families in play: migrations (#9, strict backup-gate equality, #11 atomicity + version-pin sweep), web forms
   (server-stamp; `... or None`; rejection ladder; soft-warn round-trip), service-tx-nesting, `Literal`
   not-enforced, CLI `ValueError`→`ClickException`, #16 ASCII/cp1252.
2. **The BINDING plan** — `docs/superpowers/plans/2026-06-10-tuition-vs-error-instrumentation.md` (commit
   `92ccf13d`, Codex-converged R2; R1's two majors — the soft-warn `is not None` discriminator and the normalized
   PGT CSS map — are already folded in). Execute its 9 tasks in order; every step's content is complete. Task 1 is
   deliberately large (the #11-atomic schema unit + pin sweep — the 0026 precedent); do not split it in a way that
   leaves an intermediate red commit.
3. **The BINDING spec behind it** — `docs/superpowers/specs/2026-06-10-tuition-vs-error-instrumentation-design.md`
   (`0c1efe71`): operator decisions D1–D6 and locks L1–L7 are closed. If plan and spec appear to conflict, STOP and
   reconcile explicitly in your findings file (the plan's "ambiguities resolved" section already covers the known
   divergences — all spec-faithful and QA-verified).
4. The dispatch chain for context: `docs/p0-tuition-vs-error-instrumentation-brainstorming-dispatch-brief.md` +
   `docs/p0-tuition-vs-error-writing-plans-dispatch-brief.md`.

---

## 1. Execution constraints

- **Isolated worktree** off current `main` HEAD (superpowers:using-git-worktrees). **Migration-number preflight
  (plan Task 1 includes it):** verify `0027` is still free at branch time (`ls swing/data/migrations/`) — Phase 16
  has a perf arc in flight and the Arc-7 watchlist-pin arc queued, either of which may take a migration. If `0027`
  is taken, renumber (next free) AND adjust the gate equality, `EXPECTED_SCHEMA_VERSION`, and every version literal
  the plan pins — note the renumber in your return report.
- **The live DB `~/swing-data/swing.db` is READ-ONLY for you** (`mode=ro` verification queries only). The migration
  runs only against test fixture DBs; the live v26→v27 migration fires post-merge on the operator's next write-path
  touch, backup-gated — do not pre-migrate it. (Read-only sanity probe in the verification tail: live DB still v26,
  `entry_intent` absent, 16 trades.)
- **Locks (spec L1–L7 / plan locks-grep):**
  - Production changes ONLY where the plan's tasks specify: `swing/data/migrations/0027_*.sql` (new),
    `swing/data/db.py`, `swing/data/models.py`, `swing/data/repos/trades.py`, `swing/trades/intent.py` (new),
    `swing/trades/entry.py`, the entry/review web routes + templates + VMs, `swing/cli.py`,
    `swing/metrics/process.py`, `swing/metrics/cohort.py`, the trade-process-card VM/template,
    `swing/metrics/process_grade_trend.py` + its VM/template (marker only) — plus tests.
  - UNTOUCHED: the measurement chain (hypothesis registry/matcher/tripwires/progress/shadow engine/temporal log —
    L1); `compute_process_grade` / `validate_mistake_tags` / `canonicalize_mistake_tags` / `MISTAKE_TAGS` /
    `disqualifying_process_violation` semantics (L2); `update_trade_review_fields` (the dedicated
    `update_entry_intent` exists instead); the #22 PGT rolling series + every existing route-test hook (L5 —
    the no-matplotlib guard stays green); every §7.5/§7.6 leave-unchanged surface; `swing/metrics/tier.py`.
- **TDD per task:** failing test → see it fail → minimal implementation → see it pass → commit. The plan computed
  pre/post values for every flipped assertion — if an observed value differs from the prediction, STOP and
  root-cause; never adjust an assertion to what you observed.
- **Fixtures use the REAL §1 label strings** (incl. VIR's `inaugural trade test`, the NULL-label VSAT/PTEN shapes) —
  the synthetic-drift gotcha.
- **Re-anchor before each edit:** main has moved since the plan's line anchors were verified; the plan names the
  signatures — find them on disk, don't trust raw line numbers.

---

## 2. Verification tail (plan Task 9, binding)

- Full fast suite GREEN on the worktree head — report the counts you actually observed (never carry a stale count;
  memory `feedback_no_false_green_claim`).
- `ruff check swing/` clean.
- Migrate-twice no-op; the orthogonality gate (the execution-discipline panel IDENTICAL across intent-filter
  states; `CHASED` absent from the panel); the locks grep; the live-DB read-only probe.
- The operator-gate doc (what the operator witnesses post-merge per spec §10.1: facet render incl. honest
  under-populated states, panel invariance while toggling, PGT markers light+dark, entry/review set/correct,
  the 16-trade backfill walk + NULL→Unclassified rendering).

---

## 3. Codex transport + review mandate (this machine)

WSL CLI (MCP codex tools dead in the VS Code extension):
```
wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C "<worktree root>" - < "<worktree root>/.copowers-review-prompt.txt"'
```
Liveness `codex --version`; round 2+ `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check`.
The worktree's `.git` is unreachable from WSL — pre-generate the diff on the Windows side and tell Codex not to run
git. Run to convergence (`NO_NEW_CRITICAL_MAJOR`); cap suspended. **Persist EVERY round's full RESPONSE (including
Round 1)** to gitignored files. Mandate Codex verify the diff against the shipped signatures + the plan's predicted
assertion flips + the §1 live-record claims (supplied query output).

---

## 4. Done criteria + handoff

- All 9 plan tasks committed (conventional, per-task; zero co-author trailers — verify
  `git log --format='%(trailers)' <base>..HEAD` shows all `[]`).
- Fast suite green + ruff clean on the worktree head; Codex converged with responses persisted.
- **Do NOT merge.** Leave the worktree intact and return: per-task commit SHAs, observed suite counts, any plan
  deviations (with reconciliation), the Codex verdict, and anything you pushed back on. The research director QAs
  the worktree, performs the merge, and owns the post-merge suite run; the operator browser/CLI gate (§10.1) and
  the live v26→v27 migration are post-merge operator actions.
