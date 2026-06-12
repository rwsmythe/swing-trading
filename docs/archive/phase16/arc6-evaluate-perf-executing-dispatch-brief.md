# Executing Dispatch Brief — Phase 16 / Arc 6: Evaluate-Step Performance

**Arc:** Phase 16 / **Arc 6** — the evaluate-perf fix (batched gap pre-warm + stagger). THIRD + final copowers stage.
**Cycle stage:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`; adversarial Codex review after ALL tasks land, run to convergence).
**Authoritative script (LOCKED, merged):** [`docs/superpowers/plans/2026-06-10-evaluate-perf-plan.md`](superpowers/plans/2026-06-10-evaluate-perf-plan.md) — **EXECUTE IT TASK-BY-TASK** (11 tasks; every code block, test, and commit message is in it). Spec: [`docs/superpowers/specs/2026-06-10-evaluate-perf-design.md`](superpowers/specs/2026-06-10-evaluate-perf-design.md) (the §2 probe findings BIND).
**Branch-from:** main HEAD at worktree creation (currently `76b89aba`; re-verify with `git log --oneline -3` — the operator commits in parallel).
**Schema:** **NONE — v26 frozen.** The `[archive] stagger_full_refresh` addition is config, not a migration.
**No isolated venv needed** — no shared-dependency re-pin (yfinance stays at the installed 1.2.2; verify at STEP 0 per the plan).

---

## 1. Mandate (one line)

Execute the 11-task plan: the cohort classifier + chunked-batch machine (`yf.download(list, threads=False, group_by="ticker")`, per-ticker validation ladder with the `dropna(how="all")` F6 guard, serial fallback, `WarmReport` + #27 audit), the shared `_full_refresh_due` predicate + crc32 stagger + lru_cache kill-switch resolver, the `_step_evaluate` pre-warm wiring, the warm-on/warm-off parity proof (the rejected-promotion foil), the benchmark script, and the full suite — TDD, green-per-commit, Codex-converged. The plan is the script; if it's wrong, STOP and flag.

---

## 2. Execution disciplines (binding; full detail in the plan)

- **Task-by-task, TDD, green-per-commit** (failing test → SEE fail → minimal impl → SEE pass → ruff → commit; conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; trailers `[]` each commit; the plan gives each commit message).
- **The probe-shaped fixture discipline is binding:** the fake `yf.download` BRANCHES on call shape (str → flat single-ticker frame; list → ticker-major `group_by="ticker"` MultiIndex with the missing ticker present-but-all-NaN and `Adj Close` present). A fixture modeling ticker ABSENCE masks the F6 guard — the documented synthetic-vs-real drift family.
- **The parity proof is the headline guard:** `assert_frame_equal` (values, `check_dtype=False`) + exact meta equality, warm-vs-serial over the same fixtures, WITH the deep-gap foil (stale > `GAP_DEEP_BAND_TRADING_DAYS` ticker gets NO `last_full_refresh_date` write + retains the old bar; the rejected R2-Major-1 promotion behavior must FAIL it).
- **The legacy weekly-refresh test note (plan Task-NOTE):** routing `read_or_fetch_archive` through the shared predicate makes existing 8-day-refresh tests stagger-sensitive — enumerate via the full `tests/data/` run and monkeypatch `_full_refresh_stagger_enabled → False` (+ `cache_clear()`) in each, IN THE SAME COMMIT, preserving their legacy-cadence intent.
- **The benchmark (plan §3.3):** gitignored `scripts/benchmark_evaluate_warm.py`, operator-run shape, sweeps `chunk_size ∈ {50,75,100}` `threads=False`-first, deep-gap band measured separately. **You MAY run it live once to pin `DEFAULT_CHUNK_SIZE`** (it's read-only fetch traffic against yfinance; keep one sweep, not repeated hammering). `threads=True` only if `threads=False` cannot reach the target. Record the table in the return report.
- **The dry-run preview:** before returning, run the documented `dry_run=True` snippet against the operator's real cache dir (zero fetches) and include the cohort counts in the return report — this previews the first-staggered-night full-refresh load for the gate.
- **Carve-out walls (spec §7):** `swing/data/ohlcv_archive.py` (warm + predicate + resolver; `read_or_fetch_archive` public signature UNCHANGED), `swing/pipeline/runner.py` (`_prewarm_evaluate_archives` + `_step_evaluate` wiring + `warnings_json`), `swing/config.py` (`ArchiveConfig.stagger_full_refresh`) + `swing.config.toml`, the script, tests. **NO** repo/model/schema; **NO** `swing/trades/`; **NO** Shape-A sidecars.
- **Full fast suite + ruff at the end ON YOUR FINAL HEAD** (actual count; isolate the 3 known xdist flakes `-n0` if they appear).
- **Degraded-harness guard:** on mid-batch tool cancellations → single sequential calls, re-Read before each Edit, verify each commit.

---

## 3. copowers Codex review (after ALL tasks land)

- Adversarial loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED) over the full diff vs plan + spec.
- **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows (`git diff main...HEAD > .codex-diff.txt`); tell Codex not to run git.
- Persist BOTH prompts AND responses every round to gitignored `.copowers-findings.md`. Scrutinize any rebuttal against disk before standing on it.

---

## 4. Return report (then STOP — do NOT merge)

The task commit SHAs + messages; the full fast-suite result ON YOUR FINAL HEAD (actual count); `ruff` clean; **the benchmark table + the pinned `DEFAULT_CHUNK_SIZE` + whether `threads=False` projects ≤90s**; **the dry-run cohort counts** (first-night full-refresh load preview); confirmation of NO schema / carve-out held / parity test green; the Codex verdict (rounds + final line); any deviation with justification. Then STOP — merge is the orchestrator's action after QA.

**Operator gate (6c — the orchestrator drives post-merge):** a live cold nightly with `pipeline_step_timings` showing `evaluate` ≤ 90s (baseline run #98 = 522s), the `WarmReport` cohort line in `pipeline.log`, no `#27` fallback storm, and data-content spot-parity (the next morning's briefing/buckets sane). The 7→≤13-day deep-history cadence note is flagged for the research director's awareness (kill-switch-reversible).
