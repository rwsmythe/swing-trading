# Writing-Plans Dispatch Brief — Phase 16 / Arc 6: Evaluate-Step Performance

**Arc:** Phase 16 / **Arc 6** — the evaluate-step perf fix (batched gap pre-warm + weekly-storm stagger). SECOND of the full copowers cycle; the brainstorm spec is LOCKED + merged.
**Cycle stage:** `copowers:writing-plans` (produce an executing-ready implementation plan, Codex-converged).
**Source of truth (LOCKED, merged to main):** [`docs/superpowers/specs/2026-06-10-evaluate-perf-design.md`](superpowers/specs/2026-06-10-evaluate-perf-design.md) — **READ IT END-TO-END.** The plan implements that spec; it does NOT re-litigate it. The §8 testing/benchmark contracts + §10 "open items handed to writing-plans" are your raw material. If you believe the spec is wrong, STOP and flag (the brainstorm probed its premises empirically — §2 binds).
**Branch-from:** main HEAD at worktree creation (currently `eb6f3428`; re-verify with `git log --oneline -3` — the operator commits in parallel).
**Schema:** **NONE — v26 holds.** The `[archive]` config additions are a CONFIG surface, not a migration.
**Deliverable:** an executing-ready plan at `docs/superpowers/plans/2026-06-10-evaluate-perf-plan.md` + Codex convergence (`NO_NEW_CRITICAL_MAJOR`) + `.copowers-findings.md` (prompts AND responses). Commit ONLY the plan doc.

---

## 1. Mandate (one line)

Turn the LOCKED design into an ordered, TDD-structured, executing-ready plan: `warm_archives_batch` (chunked multi-ticker `yf.download(threads=False, group_by="ticker")` over the two cohorts, per-ticker validation ladder + F6 all-NaN guard, serial fallback, `WarmReport` → #27 audit) + the shared `_full_refresh_due` predicate/stagger with kill-switch + the `_step_evaluate` pre-warm call + the in-cycle benchmark + the warm-on/warm-off data-content parity proof — baseline 522s, target ≤90s.

---

## 2. STEP 0 — re-ground (the spec grounded on `ac27a652`; only the spec doc landed since)

Re-confirm at your HEAD: `_step_evaluate` (runner.py ~1299) + its two fetch loops + the SPY fetch; `PriceFetcher.get` (prices.py:26); `read_or_fetch_archive` (ohlcv_archive.py:204) + `_yf_download_window` + `_write_archive_atomic` + the meta sidecar shape (`last_full_refresh_date`); the `run_warnings` plumbing into `_step_evaluate` (it currently does NOT take `run_warnings` — find the real call site + the param-precedent, mirroring the #16-arc pattern); yfinance pin (probe was on 1.2.2 — confirm the installed version matches).

---

## 3. The spec §10 open items YOU resolve in the plan

1. **Config-read mechanics** for `[archive] stagger_full_refresh` + tunables (`GAP_DEEP_BAND_TRADING_DAYS`, `chunk_size`): where the dataclass fields land (`cfg.archive` already exists — `archive_history_days`), the cascade behavior, and how the single module-level resolver in `ohlcv_archive.py` reads it WITHOUT a config import cycle (the spec's `_full_refresh_stagger_enabled()` resolver — decide injection vs lazy read; keep ONE resolver shared by warm + serial so they cannot diverge).
2. **Dry-run report delivery** (the stagger/cohort visibility surface): CLI subcommand vs flag vs logged line. Lean SMALL (a logged INFO summary line + the `WarmReport` fields in `warnings_json` may suffice for V1 — justify if you add CLI surface).
3. **Benchmark harness shape** (spec §8): the chunk-size sweep (50-100, default 75) + the deep-gap band measured separately (Codex R3 advisory) + `threads=False`-first with `threads=True` only as the documented stretch if ≤90s is unreachable. Decide: a slow-marked test vs a script vs an operator-gated live probe — it must measure the REAL ~580-ticker universe, and its evidence gates the executing phase's final numbers.
4. **Warm-on/warm-off parity proof mechanics:** the spec's binding invariant — identical archives + identical evaluate outputs with the warm enabled vs disabled on the same fixture set. Design the discriminating test ([[feedback_regression_test_arithmetic]]): it must FAIL under any warm path that writes different bars (e.g. the R2-Major-1 promotion bug the spec removed — use it as the naive-path foil).

---

## 4. Plan shape (guidance — you own the decomposition; map tasks to spec §8)

A natural ordering: (1) the pure cohort classifier + window computation (local I/O only, no fetches — unit-testable); (2) the chunked-batch machine + per-ticker validation ladder (mock the `yf.download` boundary with PROBE-SHAPED fixtures — `group_by="ticker"` MultiIndex, the present-but-all-NaN missing ticker, `Adj Close` present); (3) the shared `_full_refresh_due` predicate + stagger + kill-switch (swap the inline `>= 7` in `read_or_fetch_archive` for the shared predicate — with a no-behavior-change-when-disabled regression); (4) `warm_archives_batch` assembly + `WarmReport` + serial-fallback wiring; (5) the `_step_evaluate` call + `warnings_json` plumbing; (6) the parity proof; (7) the benchmark; (8) full suite + ruff.

**Fixture discipline (binding):** batch-response fixtures derive from the PROBE-CONFIRMED shape (spec §2) — `group_by="ticker"` level0=ticker, missing ticker present-but-all-NaN, `Adj Close` column present-and-dropped. A fixture that drops the missing ticker's columns (absence) would mask the F6 guard — the exact synthetic-vs-real drift family this project documents.

---

## 5. Locks / invariants (from spec §7 — propagate verbatim into the plan)

The §7 carve-out is the boundary: `ohlcv_archive.py` (warm + predicate + resolver; `read_or_fetch_archive` public signature unchanged, internal change = the shared predicate swap ONLY), `runner.py` (the pre-warm call + plumbing), `prices.py` only if unavoidable (lean: untouched), config surface. **NO** repo/model/DB-schema changes; **NO** `swing/trades/`; **NO** Shape-A sidecar touches (Arc-3 territory). F6 per-ticker (all-NaN guard); `_write_archive_atomic` the only write path; full-archive-return; warm = pure accelerator (correctness never depends on it; wholesale failure → serial fallback + #27 audit); `threads=False` the law (threads=True documented stretch only); deep-gap band stays INCREMENTAL (no full-refresh promotion — the R2-Major-1 parity lock); schema v26 frozen.

---

## 6. copowers process (binding)

- **Run `copowers:writing-plans`** → adversarial Codex loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED).
- **Codex transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows; tell Codex not to run git.
- Persist BOTH prompts AND responses to gitignored `.copowers-findings.md`. Commit ONLY the plan doc; conventional; no `Co-Authored-By`; no `--no-verify`; final `-m` paragraph plain prose; trailers `[]`.
- **Return a report:** the plan path; the §3 resolutions (config mechanics, dry-run delivery, benchmark shape, parity mechanics); the Codex verdict (rounds + final line); flagged items for executing. Then STOP — executing is a separate commission after orchestrator QA.
