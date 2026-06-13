# Phase 17 Arc 17-C — Exports retention (`swing exports cleanup`) — Commissioning / Spec Brief

> **⚠ CLOSED 2026-06-13 — NOT BUILT. DO NOT DISPATCH.** This brief's founding premise was FALSE: dated-`exports/<date>/` retention already exists via `swing/rendering/retention.py:archive_old_exports` (zip→delete at 90d, inside `_step_export` every pipeline run). The proposed command would be redundant at 90d and data-unsafe at shorter windows. Caught at writing-plans (the implementer grounded the brief against live code). D3/P5 = resolved-by-pre-existing-mechanism. See [`phase17-todo.md`](phase17-todo.md) §"Arc 17-C — CLOSED". Retained only as a record of the mis-scoped commission + the brief-premise lesson. The brief body below is preserved verbatim for that record.

**Audience:** A fresh Claude Code instance with no prior conversation context, dispatched to run the **copowers writing-plans** phase for this arc (and, on a later dispatch, executing-plans). This brief IS the spec — turn it into an implementation plan.

**Mission:** Add an operator-gated, age-based retention command `swing exports cleanup` that prunes stale dated nightly export directories (`exports/<YYYY-MM-DD>/`), mirroring the safety-rail + ergonomics shape of the shipped `swing logs cleanup`. Deletion, not compression. Dry-run by default.

**Expected duration:** writing-plans ~30–60 min; executing ~1–2 hr. Small arc — one CLI subcommand + one small pure-logic module + tests.

**Tripwire status (orchestrator-self-certified):** CHARC pre-certified 17-C as crossing **NO §3 tripwire** ([`docs/tool-director-context.md`](tool-director-context.md) line 145: *"NO tripwire (no new module: mirrors the shipped `swing logs cleanup`)"*). This arc adds a new `swing/exports_maintenance.py`, but it is a **mechanical mirror** of the CHARC-blessed `swing/logs_maintenance.py` pattern (pure FS logic + CLI wiring split) — no novel architecture. **No CHARC architecture pass; dispatches under the normal Codex adversarial chain.** (The orchestrator notes this self-certification in the dispatch status post to the directors for the phase-close audit.)

---

## §0 Read first

- [`swing/logs_maintenance.py`](../swing/logs_maintenance.py) — **the canonical module to mirror.** Note: pure filesystem logic, no click/no DB (directly unit-testable); single-instance lock via `O_CREAT|O_EXCL`; a `*LockHeldError`; a `select_*` selector returning a `list[Path]`. You are mirroring its *structure + safety rails*, NOT its gzip/verify-before-unlink mechanic (exports cleanup **deletes**).
- [`swing/cli.py`](../swing/cli.py) — the `logs_cleanup_cmd` (≈L5522) + the `@main.group("logs")` (≈L5483) + the `_refuse_if_pipeline_running(cfg)` helper (≈L5489–5519). The new `exports` group + `cleanup` subcommand mirror these.
- [`tests/cli/test_logs_cleanup_cmd.py`](../tests/cli/test_logs_cleanup_cmd.py) + [`tests/test_logs_maintenance.py`](../tests/test_logs_maintenance.py) — **the canonical test templates.** Mirror `_setup` (uses `_minimal_config` from `tests/cli/test_cli_eval.py` + `CliRunner`).
- [`swing/pipeline/runner.py`](../swing/pipeline/runner.py) `_prune_shadow_expectancy_artifacts` (≈L1118) + `_SHADOW_EXPECTANCY_KEEP = 90` (L1066) — the EXISTING auto-prune for `exports/research/shadow-expectancy-*`. **You do not touch research at all** (see Scope), but know it exists so you don't reinvent it.
- [`.gitignore`](../.gitignore) lines 51–131 — **why research/diagnostics are out of scope:** `exports/<date>/` is fully gitignored (`exports/*`, no negation), so deleting dated dirs is git-clean. But `exports/research/*` and `exports/diagnostics/*` carry **git-tracked** ledger files (`summary.md`/`manifest.json`/`results.csv`/`per_session.csv`, the `cohorts/*.csv`); deleting those would clobber committed working copies. The dated tree is the only clean target.

**Skill posture:** Invoke `copowers:writing-plans` (wraps `superpowers:writing-plans` + adversarial Codex to convergence). Do NOT invoke brainstorming — the design is fully specified below. Do NOT write implementation code in this phase; produce the plan.

---

## §1 Strategic context (compressed)

Phase 17 is *Consolidation & Parity-Drift Elimination*. 17-A and 17-B (the parity/refactor headliners) shipped. 17-C is disjoint filler: disk-retention hygiene. The `exports/` dir has accumulated 41 dated nightly briefing+chart dirs back to 2026-04-20 with no retention mechanism (logs already got `swing logs cleanup` in Phase 16 Arc 2; exports never did — debt item D3/P5). This closes that gap with the same proven, operator-gated, dry-run-default shape. **NO schema migration.**

---

## §2 Scope

### In scope
- A new pure-logic module **`swing/exports_maintenance.py`** mirroring `logs_maintenance.py` (selector + remove helper + single-instance lock + a `*LockHeldError`).
- A new **`@main.group("exports")`** + **`exports cleanup`** subcommand in `swing/cli.py`.
- Tests: `tests/test_exports_maintenance.py` (pure logic) + `tests/cli/test_exports_cleanup_cmd.py` (CLI), mirroring the logs templates.

### Out of scope (explicit — do NOT touch)
- **`exports/research/`** — any handling whatsoever. Shadow-expectancy is auto-pruned (keep-90); the rest is the intentional **committed research ledger**. Leave it entirely alone.
- **`exports/diagnostics/`** — tracked research-ledger CSVs. Never touched (and it won't match the dated-dir selector anyway).
- **The top-level chart cache `swing-data/charts/`** — separate tree (`cfg.paths.charts_dir`), chart-cache-prune territory, not this arc. (Per-session charts live *inside* `exports/<date>/charts/` and die with their dated parent — that's correct and in scope.)
- Compression/gzip (this is deletion).
- Any schema change, any scheduling/automation (operator-invoked only; **never auto-runs**, never wired into the pipeline or startup).
- Any change to `exports/research/` retention policy or `_prune_shadow_expectancy_artifacts`.

---

## §3 Design spec (locked — operator-decided 2026-06-13)

### §3.1 Module `swing/exports_maintenance.py`
Pure filesystem logic, no click, no DB. Module docstring states: removes ONLY dated session dirs (`exports/<YYYY-MM-DD>/`) older than the window; NEVER touches `research/`/`diagnostics/`/any non-date entry; mirrors the `swing logs cleanup` shape; never auto-runs.

```python
_DATED_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")

class ExportsCleanupLockHeldError(RuntimeError): ...

def select_stale_export_dirs(
    exports_dir: Path, *, older_than_days: int, today: date
) -> list[Path]:
    """Dated session dirs whose NAME-date is strictly older than
    (today - older_than_days). Boundary KEPT (>= cutoff is retained). Skips:
    non-dirs, names failing the strict YYYY-MM-DD regex, names failing
    date.fromisoformat (defensive). Returns sorted ascending. Never selects
    'research'/'diagnostics'/any non-date name (they fail the regex)."""

def remove_export_dir(path: Path, exports_dir: Path) -> None:
    """Defensive: raise ValueError unless `path` is a DIRECT child of
    exports_dir AND its name matches _DATED_DIR; then shutil.rmtree(path).
    (Hardens the public helper against misuse — mirror logs_maintenance's
    `path.resolve().parent != logs_dir.resolve()` guard.)"""

def acquire_single_instance_lock(exports_dir: Path) -> _SingleInstanceLock:
    """`.exports-cleanup.lock` in exports_dir via O_CREAT|O_EXCL; raise
    ExportsCleanupLockHeldError if held. Mirror logs_maintenance verbatim."""
```

- **`today` is an injected parameter** (not read inside the function) so tests pin it — this satisfies the **R2 frozen-clock convention** for new date-touching tests (see §4). The CLI passes `date.today()`.
- **Age axis = the directory NAME**, not mtime (the name IS the `action_session` date; matches how the shadow-expectancy prune sorts by name). No filesystem mtime read.
- Boundary semantics: a dir is stale iff `dir_date < today - timedelta(days=older_than_days)`. A dir exactly on the cutoff is **kept**.

### §3.2 CLI `swing exports cleanup`
Mirror `logs_cleanup_cmd`:
- `@main.group("exports")` (mirror the `logs_group` definition shape) + `@exports_group.command("cleanup")`.
- Options: `--older-than-days INTEGER` (`default=90, show_default=True`); `--yes` (is_flag, "Skip the confirmation prompt (scripted use).").
- Flow: resolve `exports_dir = cfg.paths.exports_dir`; if it doesn't exist → `click.echo("No exports directory; nothing to do.")` + return. → **`_refuse_if_pipeline_running(cfg)`** (reuse the existing helper) → acquire the single-instance lock (ClickException on held) → `select_stale_export_dirs(...today=date.today())` → if empty, echo "No export dirs older than N days." + return → **list each candidate** (name; SHOULD include a recursive byte size via `sum(f.stat().st_size for f in p.rglob('*') if f.is_file())` + a total, mirroring the logs "Total to reclaim" line) → **`if not yes: click.confirm("Proceed?", abort=True)`** → `for p in candidates: remove_export_dir(p, exports_dir)` + echo `f"Removed {p.name}"` → "Done." → **lock released in `finally`**.
- Default behavior (no `--yes`) = dry-run-then-confirm: the abort path deletes nothing.

### §3.3 Safety rails (all mandatory)
- Single-instance lock (`.exports-cleanup.lock`), released in `finally`.
- `_refuse_if_pipeline_running(cfg)` before any work (the pipeline writes `exports/<today>/` during a run; refusing is the consistent, safe choice).
- Dry-run default via the confirm prompt; `--yes` bypasses for scripted use.
- `remove_export_dir`'s direct-child + dated-name guard (defense-in-depth; the selector already constrains, but the public helper hardens).
- **ASCII only** in every `click.echo`/prompt string (Windows cp1252 stdout gotcha — no `→`, `§`, em-dash, etc.). Add a subprocess-through-PowerShell stdout test if you add any borderline glyph (you shouldn't).

---

## §4 Binding conventions
- Branch `main`; conventional commits; **NO `Co-Authored-By` footer; NO `--no-verify`; NO amending.** Verify `git log -1 --format='%(trailers)'` is empty before finishing each commit batch. Keep the final `-m` paragraph plain prose (trailer-parse hazard).
- TDD: failing test → see fail → minimal impl → see pass → commit, per logical change. Task-ID commit subjects (`feat(cli): Task N — ...`, `test(...): ...`).
- **R2 frozen-clock convention (binding for NEW date tests):** the selector test MUST pin `today` (pass a fixed `date(2026, 6, 13)` etc.) — never read the live wall clock. The injected-`today` design above makes this trivial; assert a boundary dir is kept and a one-day-older dir is deleted.
- **R1 rider does NOT apply** (no `pyproject.toml` change here — no new dependency; `re`/`shutil`/`datetime`/`os` are stdlib).
- Worktree (executing phase only): `.worktrees/<name>` at repo root — NOT a repo sibling, NOT `.claude/worktrees/`. Specify the path explicitly.
- Fast suite `python -m pytest -m "not slow" -q` stays green; `ruff check swing/` introduces zero new violations (baseline 18 E501).
- Adversarial Codex to **convergence** (zero new crit/major; the 5-round cap is suspended for this project). Persist every Codex round's **prompt AND response** to a gitignored `.copowers-findings.md` (writing-plans phase) so the orchestrator can confirm convergence at QA. WSL-native Codex transport per `docs/orchestrator-context.md`.

---

## §5 Suggested task decomposition (the plan refines this)
1. **Module skeleton + selector (TDD):** `select_stale_export_dirs` with the boundary/skip/strict-regex/`fromisoformat`-guard cases + the frozen-`today` test (boundary kept, older deleted, research/diagnostics names never selected, non-dir skipped).
2. **`remove_export_dir` + lock (TDD):** the direct-child + dated-name guard (raises on a non-child / non-dated path); the single-instance lock + `ExportsCleanupLockHeldError`.
3. **CLI group + command (TDD):** the `exports cleanup` command — dry-run-default lists + confirm-abort deletes nothing; `--yes` deletes; empty/missing exports dir; pipeline-running refusal; lock-held → ClickException; ASCII stdout.
4. **Integration sanity:** a CliRunner test against a seeded temp `exports/` containing dated dirs (old + recent) + a fake `research/` dir + a fake `diagnostics/` dir, asserting ONLY the stale dated dirs are removed and `research`/`diagnostics` survive.

---

## §6 Adversarial review — watch items
- **Selector strictness:** never matches `research`/`diagnostics`/`cohorts`/non-date names; `date.fromisoformat` ValueError → skip (don't crash); symlink/junction not followed into deletion of a non-child.
- **Boundary off-by-one:** `< cutoff` deletes, `>= cutoff` keeps; the frozen-clock test pins both sides.
- **Dry-run integrity:** the no-`--yes` abort path deletes nothing (assert all dirs still present after an aborted invoke).
- **Lock release in `finally`**; pipeline-running refusal fires before any deletion.
- **`remove_export_dir` guard** rejects a path outside `exports_dir` and a non-dated name.
- **Empty/missing exports dir** → graceful "nothing to do", exit 0.
- **No collision** of the new `exports` group with existing commands; help text ASCII-clean.

---

## §7 Done criteria + gate
- `swing exports cleanup` lists dated dirs older than `--older-than-days` (default 90), dry-run by default, `--yes` acts, refuses while a pipeline is running, single-instance-locked.
- New module `swing/exports_maintenance.py` + tests `tests/test_exports_maintenance.py` + `tests/cli/test_exports_cleanup_cmd.py`.
- Fast suite green (re-run on the merged head — no false-green); ruff clean; trailers `[]`.
- Codex converged (NO_NEW_CRITICAL_MAJOR), responses persisted.
- **Operator-witnessed gate (at executing close):** operator runs `swing exports cleanup` (no `--yes`) against the real `exports/` and confirms the candidate list contains ONLY dated `YYYY-MM-DD` dirs older than 90 days — and explicitly NOT `research/` or `diagnostics/`. Then optionally `--yes` to act. Witness the UNSEEDED real-tree behavior, not just seeded tests.

---

## §8 Return report (writing-plans phase)
As your final chat message, report: the plan path (`docs/superpowers/plans/...`); the task list it produced; the Codex convergence verdict + round count (with the persisted-findings path); any spec ambiguities you resolved or escalated; any deviation from this brief with rationale. **Do NOT post to the mailbox or to any director** — your return report is your final chat message only; the orchestrator QAs it and posts post-QA.
