# Broad-Watch-Baseline Hypothesis — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance, no prior conversation context.
**Mission:** IMPLEMENT the Codex-converged broad-watch-baseline plan, task by task, in an isolated worktree.
The plan is BINDING; the spec is binding behind it. Converge the implementation through adversarial Codex review,
then return for research-director QA + merge. **Do NOT merge to `main` yourself.**
**Prepared:** 2026-06-09 by the research-director/evaluator instance, after QA-PASS of the writing-plans return
(all five spec-ambiguity resolutions independently re-verified against shipped code + the live DB).
**Phase:** copowers:executing-plans (wraps superpowers:subagent-driven-development + adversarial Codex review).

---

## 0. Read first

1. `CLAUDE.md` — conventions (conventional commits; NO co-author footer; NO `--no-verify`; TDD) + gotchas #9
   (migration explicit `BEGIN;…COMMIT;`), #11 (atomic schema/constant/test landing), the backup-gate
   strict-equality shape, and the Windows notes.
2. **The BINDING plan** — `docs/superpowers/plans/2026-06-09-broad-watch-baseline-hypothesis.md` (commit
   `75b6d291`, Codex-converged R2 clean, 0 crit / 0 maj across the chain). Execute its 4 tasks in order; every
   step's content is complete (no placeholders). Its Task-2 Step-6 "run + triage any failure not listed" gate is
   part of the plan — honor it.
3. **The BINDING spec behind it** — `docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md`
   (`99e0608f`). If plan and spec ever appear to conflict, STOP and reconcile explicitly in your findings file —
   do not silently pick one (the plan's "Spec ambiguities resolved" section already covers the five known
   divergences; they are spec-faithful and verified).
4. The dispatch chain for context: `docs/broad-watch-baseline-hypothesis-brainstorming-dispatch-brief.md` +
   `docs/broad-watch-baseline-hypothesis-writing-plans-dispatch-brief.md`.

---

## 1. Execution constraints

- **Isolated worktree** off current `main` HEAD (superpowers:using-git-worktrees). `main` is active (Phase 16
  Arc 2 + Arc 5 are in flight) — at branch time, verify migration number `0026` is still free (`ls
  swing/data/migrations/`); if another arc landed an 0026, renumber to the next free number AND adjust the gate
  (`current == <new-1> AND target >= <new>`), the `EXPECTED_SCHEMA_VERSION` bump, and every version literal the
  plan pins — then note the renumber in your return report.
- **The live DB `~/swing-data/swing.db` is READ-ONLY for you** (verification queries only, `mode=ro` URI). The
  migration runs only against test fixture DBs. The live v25→v26 migration happens post-merge on the operator's
  first `ensure_schema` touch, where the new backup gate snapshots the v25 DB — that is by design; do not
  pre-migrate it.
- **Locks (spec §8 / plan File Map "NOT touched"):** production changes are EXACTLY four files —
  `swing/data/migrations/0026_*.sql` (new), `swing/data/db.py`, `swing/recommendations/hypothesis.py`,
  `research/harness/shadow_expectancy/attribution.py` — plus tests. `swing/metrics/tier.py` + the tier/deviation
  VMs stay untouched (their `== 4` assertions STAY 4); `models.py`/`repos/hypothesis.py`/live call sites/Family-2
  surface code untouched; the four frozen H1–H4 registry rows untouched; the engine's
  simulator/bracket/funnel/scorecard/`constants.py` untouched; no new dependency. The engine's forbidden-import L2
  test must stay green.
- **TDD per task:** failing test → see it fail → minimal implementation → see it pass → commit. The plan gives
  exact pre/post values for every flipped assertion — if an observed value differs from the plan's prediction,
  STOP and root-cause (do not adjust the assertion to whatever you observed).
- **Frozen text:** migration 0026's registry-row literals are FROZEN spec §2 text — byte-faithful (modulo the
  documented `||`-wrapping equivalence). Do not editorialize the statement/criteria/notes strings.

---

## 2. Verification tail (plan Task 4, binding)

- Full fast suite (`python -m pytest -m "not slow" -q`) GREEN on the worktree head — read the actual counts; never
  carry a stale count forward (memory `feedback_no_false_green_claim`).
- `ruff check swing/` clean.
- Migrate-twice no-op, the containment smoke (default-off vs opt-in), and the lock-grep from Task 4.
- A read-only live-DB sanity probe: confirm `schema_version=25` + 4 registry rows pre-merge (your change must not
  have touched it).

---

## 3. Codex transport + review mandate (this machine)

WSL CLI (MCP codex tools are dead in the VS Code extension):
```
wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C "<worktree root>" - < "<worktree root>/.copowers-review-prompt.txt"'
```
Liveness `codex --version` → `codex-cli 0.135.0`; round 2+ `codex exec resume --last -c sandbox_mode="read-only"
--skip-git-repo-check`. The worktree's `.git` is unreachable from WSL — pre-generate the diff on the Windows side
and tell Codex not to run git. Run to convergence (`NO_NEW_CRITICAL_MAJOR`); 5-round cap suspended.
- **Persist EVERY round's full RESPONSE** (including Round 1) to the gitignored findings file.
- Mandate Codex verify the diff against the shipped signatures + the plan's predicted assertion flips + the live-DB
  data claims (supplied query output) — the standing `feedback_adversarial_review_verify_data_shapes` mandate.

---

## 4. Done criteria + handoff

- All 4 plan tasks committed (conventional, per-task; zero co-author trailers — verify
  `git log --format='%(trailers)' <base>..HEAD` shows all `[]`).
- Fast suite green + ruff clean on the worktree head; Codex converged with responses persisted.
- **Do NOT merge.** Leave the worktree intact and return a report: per-task commit SHAs, the suite counts you
  actually observed, any plan deviations (with reconciliation), the Codex convergence verdict, and anything you
  pushed back on. The research director QAs the worktree, performs the merge, and owns the post-merge suite run.
