# Shadow-Expectancy Entry/Join Correction — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance, no prior conversation context.
**Mission:** Turn the Codex-converged correction-design spec into a TDD implementation plan. This is a **correction to ALREADY-SHIPPED code** — the plan EDITS existing harness modules per the spec's enumerated change surface, rewrites the affected tests, and adds real-emitter fixtures. It is NOT a greenfield build.
**Prepared:** 2026-06-09 by the orchestrator/evaluator instance.
**Phase:** copowers:writing-plans. Output → a plan doc → (later) executing-plans.

---

## 0. Read first (in order)

1. `CLAUDE.md` — conventions: conventional commits; **NO Claude co-author footer; NO `--no-verify`; no amend**; TDD; the Windows/ASCII gotchas; **especially "Synthetic-fixture-vs-production-emitter shape drift"** (the bug this corrects).
2. **The authoritative spec — `docs/superpowers/specs/2026-06-09-shadow-expectancy-entry-join-correction-design.md`** (Codex-converged, `6fd664f7`). Its **§5 / §5.1 are the exact edit map**; §9 is the supersede/preserve ledger; §7 is the test strategy; §8 is the re-runnable live-DB verification appendix. **Do not redesign — translate §5/§7 into bite-sized TDD tasks.**
3. The **original spec** (`docs/superpowers/specs/2026-06-08-shadow-expectancy-engine-design.md`) and **original plan** (`docs/superpowers/plans/2026-06-09-shadow-expectancy-engine.md`) — context for what's PRESERVED (the bracket, censoring, scorecard, simulator internals, funnel two-level structure). Do not touch the preserved surface.
4. **The shipped code you will edit** — `research/harness/shadow_expectancy/` (esp. `collapse.py`, `run.py`, `validate.py`, `constants.py`, `funnel.py`, `scorecard.py`, `output.py`) + `tests/research/shadow_expectancy/` + the `diagnose` group in `swing/cli.py`. **Recon the CURRENT signatures** (e.g. `collapse_detections(...)`, the entry/forward search in `run.py`, `validate_candidate_levels`/`validate_signal`, the `SimResult`/`SignalOutcome` dataclasses, `build_funnel`, the constants tuples) so the plan's edits are real against the shipped code, not the original plan's text.

**Skill posture:** invoke `copowers:writing-plans` (wraps superpowers:writing-plans + a Codex adversarial review run to convergence). Use `superpowers:using-git-worktrees` if you want isolation; writing-plans is doc-only so a worktree is optional.

---

## 1. What this plan must produce (a correction, not a build)

A bite-sized TDD plan that, task by task, **edits the shipped harness** to the corrected contract. For a correction, the TDD rhythm is:

> rewrite/extend the test to the NEW contract → run it, see it FAIL against the shipped code → make the §5 edit → run it, see it PASS → commit.

Each task: exact **Files** (Modify `path:lines` / Test `path`), then steps with **real code** (the new test code + the new implementation code — no placeholders), the exact pytest command + expected fail/pass, and a conventional commit. **Delete** the obsolete tests explicitly (don't leave them). Cover every item in spec §5, §5.1, and §7.

---

## 2. The edit map (mirror spec §5/§5.1 exactly — do not invent scope)

- **`collapse.py`** — `collapse_detections` drops the `candidate_pivot` param; canonical = **longest chain, tie low `detection_id`**; implement the **strict date-prefix** `inconsistent_detection_series` gate (every non-canonical chain's date list == `canonical_dates[:len(chain)]` AND OHLC matches on shared dates — NOT overlap-only); **delete** the `no_canonical_detection` and `inconsistent_trigger_state` branches; return the canonical full bar series. (Spec §2.3, §3.1.)
- **`run.py`** — replace the `triggered_open`/`entry_fired` search with the **entry recompute**: `entry_idx = first i where bars[i].high >= candidate.pivot`; `forward_bars = bars[entry_idx+1:]`; `None` → `never_triggered`; **`entry_idx == len(bars)-1` → `insufficient_forward_depth`** (per-hypothesis, do NOT call `simulate`); emit the **`entry_bar_weak_close`** annotation; `candidate is None` → `no_candidate_join` here; pipeline order `collapse → join → attribute → validate(now returns `no_candidate_pivot`) → entry-recompute → simulate`. (Spec §2.1, §2.2, §5.)
- **`validate.py`** — `validate_candidate_levels` returns `"no_candidate_pivot"` (not `"invalid_ohlc"`) for `pivot` `None`/non-finite/`<=0`; bar checks still `"invalid_ohlc"`. (Spec §3.2.)
- **`constants.py`** — update `FUNNEL_REASONS` / `UNATTRIBUTED_REASONS` / `ATTRIBUTED_EXCLUDED_REASONS` per spec §3.4/§3.5: remove `no_canonical_detection`, `inconsistent_trigger_state`; add `no_candidate_pivot`. (Spec §3.)
- **`funnel.py`** — no structural change; consumes the updated vocabularies (its per-terminal reason validation must still pass).
- **`scorecard.py` / `output.py`** — **additive only:** the `entry_bar_weak_close` count + ledger column. The censoring/expectancy/Wilson math + CSV/manifest writers are otherwise untouched.
- **`simulator.py`, `bracket.py`, `attribution.py`, `exceptions.py`** — **UNCHANGED** (the `simulate(...)` contract is preserved; never called with empty `forward_bars`).
- **`swing/cli.py` (§5.1)** — add the idempotent `_ensure_research_importable()` helper (verbatim shape in spec §5.1) and call it before **EVERY** deferred `from research.harness…` import under the `diagnose` group. The rule is **mechanical (grep-enforced)**, not an enumerated list — a test greps `swing/cli.py` and asserts no un-guarded `from research.harness` site remains under `diagnose`. This is the ONLY `swing/` change.

---

## 3. Fixtures from REAL emitter shapes — non-negotiable (spec §7.1)

This is the whole reason the bug existed. The plan MUST:
- **Forbid forcing `detection.pivot == candidate.pivot`.** Every fixture sets `detection.pivot != candidate.pivot`, with per-pattern `pivot_price` **including `0.0`** for cup/dbw and a real level for vcp/flat_base/htf.
- Add the **BULZ run-89 golden fixture** (5 detections, geometric pivots `{49.89, 49.89, 0.0, 49.89, 0.0}`, `candidate.pivot=56.09`, identical frozen bars, `watch`) → expected `never_triggered` (regression guard that the live shape now routes honestly).
- Add a **breakout fixture** where a forward `high` EXCEEDS `candidate.pivot` so a trade prices through the full simulator (hand-verify the R bracket).
- Add a **mixed-first-trigger-session fixture** (cup/dbw pivot 0.0 trigger bar 1, vcp never) asserting the signal is **NOT** excluded (the `inconsistent_trigger_state` reason is gone) and the longest chain is the bar source.
- **Every fixture asserts `data_asof_date < observation_date`** for all forward bars (the §4 no-look-ahead invariant).

---

## 4. Hard constraints (LOCKS)

- **Surgical:** edit ONLY the §5/§5.1 surface + the affected tests/fixtures. Do NOT touch `simulator.py`/`bracket.py` math, the censoring/scorecard expectancy math, or the funnel two-level structure (D1–D8, D10–D12 stand).
- **L2 LOCK:** the only `swing/` change is `swing/cli.py` (the `_ensure_research_importable` helper + call sites). **No new `swing/` files.** If you'd edit any other `swing/` file, STOP and flag it.
- **No schema change** (v25 holds; harness stays a `mode=ro` read-only consumer).
- **No new production dependency / no forbidden imports** in the harness (`yfinance`/`schwabdev`/`swing.integrations.schwab`/`swing.data.ohlcv_archive`); the L2-lock test stays green.
- **Conventional commits; NO Claude co-author footer; NO `--no-verify`; no amend.** Verify `git log -1 --format='%(trailers)'` is `[]`.
- **Fast suite green** (baseline ~7504 on `main`; trust live pytest output; re-run on the head, don't hardcode counts).

---

## 5. Watch items (the Codex-resolved subtleties — implement them, don't re-derive)

- **The `inconsistent_detection_series` gate is STRICT date-prefix, not overlap-only** (Codex R1-#1). A gappy chain (`A=[d1,d3]` vs `B=[d1,d2,d3]`) MUST be excluded, not silently accepted. Test it.
- **Zero-forward-depth → `insufficient_forward_depth`** (Codex R1-#3): a trigger on the LAST bar excludes per-hypothesis and `simulate` is **never** called with empty `forward_bars`. Test that the simulator is not invoked.
- **`no_candidate_pivot` is split from `invalid_ohlc`** (Codex R2 / §3.2) and routes **per-hypothesis** (post-attribution), disjoint from `UNATTRIBUTED_REASONS`.
- **`entry_bar_weak_close` is annotation-only** — no behavior change; the trade still prices identically; it's a reported diagnostic (spec §2.2).
- **No-look-ahead** rests on `data_asof_date < observation_date` (source-enforced), NOT "after detection_date" (the first obs is on detection_date). Encode the fixture invariant accordingly (spec §4).
- **The invocation guard is grep-enforced** across ALL `diagnose`-group `research.harness` import sites, not a hand-list (spec §5.1).

---

## 6. Workflow + Codex transport

- `copowers:writing-plans` → run the Codex adversarial review **to convergence** (`NO_NEW_CRITICAL_MAJOR`; round cap suspended). **Persist each Codex RESPONSE** to a gitignored on-disk file.
- **Tell Codex to VERIFY the load-bearing claims against the shipped code AND the live DB** (it has read-only repo access; the spec §8 appendix gives the re-runnable queries) — that is exactly what the original review chain lacked and what made the correction necessary.
- Codex MCP is dead in the VS Code extension; use the WSL CLI fallback: `wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C "<repo root>" - < "<repo root>/.copowers-review-prompt.txt"'`; round 2+ via `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check`. Liveness `codex --version` → `codex-cli 0.135.0`.

---

## 7. Done criteria + handoff

- A complete bite-sized TDD plan saved to `docs/superpowers/plans/2026-06-09-shadow-expectancy-entry-join-correction.md`, covering every §5/§5.1 edit + every §7 test (including the deletions), with real test+impl code and no placeholders.
- Self-review passed (spec coverage vs the §9 ledger; no placeholders; type/name consistency against the shipped signatures).
- **Codex-converged** (`NO_NEW_CRITICAL_MAJOR`); responses persisted.
- Commit the plan (conventional; no co-author footer; trailers `[]`).
- **Do NOT implement.** Return for orchestrator QA; it routes to executing-plans next. Return a short summary: the task list, the shipped signatures you verified, the Codex verdict, and any pushback.
