# Focused-Executing Dispatch Brief — Phase 16 / Arc 8: Trailing-Bar NaN-Close Write Barrier

**Arc:** Phase 16 / **Arc 8** — operator-approved follow-up from the run-#99 (Arc 6c) data event. Registered in [`docs/phase16-todo.md`](phase16-todo.md) §Arc 8 (the locked design facts live there; this brief operationalizes them).
**Cycle stage:** **FOCUSED executing-with-Codex** (single cycle; the design space is small + empirically characterized — the Arc-5/Arc-8 precedent class). The design resolutions in §3 are LOCKED; if grounding contradicts one, STOP and flag.
**Branch-from:** main HEAD at worktree creation (currently `29e1cfc6`; re-verify — the operator commits in parallel).
**Schema:** **NONE — v28 holds.** Footprint: `swing/data/ohlcv_archive.py` (+ a `WarmReport` field surfaced through `runner.py`'s existing warm-warnings entry) + tests + a CLAUDE.md gotcha addendum. The Arc-6 §7 carve-out territory.
**Deliverable:** the barrier shipped TDD + Codex-converged + `.copowers-findings.md` (prompts AND responses).

---

## 1. Mandate (one line)

Stop ragged trailing bars (the run-#99 class: yfinance rows with NaN `Close` while O/H/L/V present) from being appended to the legacy archives — trim them at the fetch boundary with ONE shared helper covering both transports, leave the meta/archive state so the next call retries (the F6-transient posture), and audit every trim — so a yfinance adjustment-data event can never again poison SMAs/weather/charts for up to 13 days.

---

## 2. The evidence base (run #99, 2026-06-10 — verified; build the tests from THIS shape)

- **134 archives** took a trailing ragged bar in one night; the NaN pattern was **uniformly `('Close',)`** — O/H/L/V present, Close NaN (the yfinance adjusted-close derivation artifact).
- **Path-independent:** SPY's ragged bar came through the SERIAL single-ticker path (weather, before the warm ran); the warm batch wrote the rest identically. 8 instances predated Arc 6 (6×06-04, 2×06-09) — a recurring serial-path mode, amplified by early-evening run timing.
- **It does not self-heal:** the incremental gap fetch starts at `latest_stored + 1` — a stored ragged day is never re-fetched until the ≤13-day staggered full refresh. Downstream: weather crashed on `NOT NULL weather_runs.close`; charts crashed on ragged-NaN OHLC (mplfinance); NaN poisons rolling SMAs for every window containing the day. Run #99 required a manual 134-archive repair (drop the trailing row → next gap fetch re-pulls a settled bar) — **this arc automates exactly that semantic at write time.**

---

## 3. LOCKED design (implement this)

1. **One shared helper:** `_trim_trailing_ragged(df) -> tuple[pd.DataFrame, int]` (name yours) — iteratively drop rows FROM THE END while any of `Open/High/Low/Close` is NaN (multiple trailing ragged rows possible); return the trimmed frame + the count. **Volume-NaN alone does NOT trim** (legitimately volume-less bars exist). **Interior NaN rows are UNTOUCHED** — the Phase-15 bad-bar-accept posture for HISTORICAL bars is explicitly unchanged; this barrier guards only the incoming tail, where retry-tomorrow is cheap and strictly better.
2. **Two call sites, four write paths covered (parity by construction):**
   - **Serial:** apply to `_yf_download_window`'s returned frame (one site covers BOTH the full-refresh `fetched.tail→write` @[ohlcv_archive.py:708-709](../swing/data/ohlcv_archive.py) AND the gap `concat→write` @719-722). A gap frame trimmed to EMPTY composes with the existing `if not gap.empty` guard → no write, archive retained, meta stays stale → the next call retries — zero new control flow. A full-refresh frame trimmed by N rows still writes + stamps meta (the trimmed day arrives via tomorrow's gap fetch).
   - **Warm:** apply in the per-ticker validation ladder (right after the `dropna(how="all")` F6 step @406-407) so BOTH warm cohorts (`_merge_gap_subframe` @462→497-500 and the full-refresh write @511) receive pre-trimmed frames. A warm subframe trimmed to EMPTY: implementer's choice between (a) per-ticker miss → existing serial fallback (correct but re-fetches the same ragged bar — wasteful on an event night) or (b) **skip-without-fallback + counted (the lean)** — archives end identical either way (serial would also trim-to-empty and no-op); justify the pick in a comment.
3. **Audit (#27):** `log.warning` per trimmed ticker at the helper's call sites (ticker + trimmed date(s) — lands in `pipeline.log` via Arc 1; that covers the serial consumers [weather/charts/daily-mgmt] which have no `run_warnings` access). PLUS `WarmReport` gains `trailing_nan_trimmed: int` (field default 0 — additive, [ohlcv_archive.py:70-82](../swing/data/ohlcv_archive.py)) surfaced through `runner.py`'s existing warm telemetry INFO line + the degraded-warning entry (@runner.py:1329-1347 — add the field; emit a `run_warnings` entry when `trailing_nan_trimmed > 0` even if nothing else degraded: expected-vs-actual per #27).
4. **The CLAUDE.md gotcha addendum** (a docs commit in this arc): extend the F6 bullet in §Gotchas/yfinance — the trailing-bar NaN-Close class, the barrier, and the run-#99 provenance, compressed to trigger + fix.

---

## 4. Execution disciplines (binding)

- **TDD, green-per-commit** (failing test → SEE fail → minimal impl → SEE pass → ruff → commit; conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; trailers `[]`). Likely 2-3 commits — your decomposition.
- **Tests from the REAL #99 shape** (the synthetic-vs-production gotcha): the trailing row carries NaN Close with O/H/L/V PRESENT (not all-NaN — that's the existing F6 guard's case, which must still pass distinctly). Binding cases: (a) the #99 single-trailing-ragged row → trimmed, clean prefix written; (b) a multi-day gap window with only the tail ragged → prefix appended, tail trimmed; (c) MULTIPLE consecutive trailing ragged rows → all trimmed; (d) **interior** NaN-Close row → PRESERVED (FAILS under an over-eager drop-all-NaN-rows implementation — the discriminator); (e) trim-to-empty on the serial gap → no write, no meta change, archive byte-identical; (f) trim-to-empty on the serial full-refresh → falls back to the existing empty-fetch F6 handling (no archive clobber, meta stays stale); (g) warm/serial archive parity INCLUDING trims (extend the Arc-6 parity test's fixture set with a ragged-tail ticker); (h) `WarmReport.trailing_nan_trimmed` + the runner warning entry; (i) Volume-only-NaN trailing row → NOT trimmed.
- **Do not regress Arc 6:** the validation ladder's existing steps (required-columns, all-NaN, index-parse) stay; the trim slots after them; `_write_archive_atomic` remains the sole writer; `read_or_fetch_archive`'s public signature unchanged; NO Shape-A touches (`write_window`/`resolve_ohlcv_window` are Arc-3 territory).
- **Full fast suite + ruff at the end ON YOUR FINAL HEAD** (baseline 7758; actual count; isolate the 3 known xdist flakes `-n0` if they appear).
- **Degraded-harness guard:** on mid-batch tool cancellations → single sequential calls, re-Read before each Edit, verify each commit.

---

## 5. copowers Codex review (after all tasks land)

- Adversarial loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED) over the full diff vs this brief + the todo §Arc-8 design facts. Ask Codex specifically to probe: the interior-vs-trailing boundary, the trim-to-empty meta semantics on BOTH paths, warm/serial parity, and whether any consumer depended on the old append-ragged behavior.
- **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows (`git diff main...HEAD > .codex-diff.txt`); tell Codex not to run git. Persist BOTH prompts AND responses every round to gitignored `.copowers-findings.md`. Scrutinize any rebuttal against disk.

---

## 6. Return report (then STOP — do NOT merge)

The commit SHAs + messages; the full fast-suite result ON YOUR FINAL HEAD (actual count); `ruff` clean; the warm trim-to-empty choice (fallback vs skip) + why; confirmation NO schema / NO Shape-A / Arc-6 invariants held; the Codex verdict (rounds + final line); any deviation with justification. Then STOP — merge is the orchestrator's action after QA.

**8b verification note (surface in the return):** the barrier's live proof rides organically — the next yfinance raggedness event shows the trim warnings + clean archives instead of a repair job. No dedicated operator gate run is required (the unit/parity tests + the #99-shaped fixtures are the binding evidence); the orchestrator spot-checks `pipeline.log` for trim lines after the next few nightlies.
