# Lever-1 cap rank fix — dispatch brief (rider)

**Commissioned:** 2026-10-28 HST, under CHARC's form ruling `20261029T020502Z` (RD CC, no dissent, `20261029T020601Z`). The operator said "go".
**Scope:** `swing/pipeline/runner.py` and `tests/` ONLY. No schema change, no new column, no config change, no `swing/data` or `swing/trades` touch.
**Branch:** the worktree branch this dispatch gives you, off `main` at or after `fbcd4dcf` (the safe-floor commit: `detect_watch_pool_cap` is unset on main, so production is uncapped while this lands).

## The defect (verified by RD and CHARC on the live DB, mode=ro)

`swing/pipeline/runner.py` (the "Dormant Lever 1" block, about lines 2046-2077) sorts the watch detect pool with `key=lambda c: c.rs_rank` before keeping `_watch[:_cap]`.

1. **`candidates.rs_rank` is NULL on every live watch row.** TT8 runs on the SPY fallback (`rs_method = 'fallback_spy'`). Two `None`s cannot be ordered, so the sort raises `TypeError: '<' not supported between instances of 'NoneType' and 'NoneType'`. `step_guard` swallows it: pattern_detect wrote ZERO rows on runs 201 and 202, and the runs stamped complete.
2. **The direction is inverted.** `rs_rank` is a 0-99 percentile where 99 is STRONGEST (`swing/evaluation/rs.py:81-85`). Ascending sort + `[:cap]` keeps the WEAKEST names.
3. **The suite never reached either failure** because the seeding helper `_seed_aplus_watch_skip_candidates_and_run` (`tests/pipeline/conftest_temporal.py:220`) plants `rs_rank=85`, `rs_method="universe"` on every row.

## The ruled fix (CHARC's form; do not change the rank key or the audit fields without stopping and reporting)

1. **Sort key:** `candidates.rs_return_12w_vs_spy` DESCENDING, `None` LAST, `ticker` ASC as the deterministic tiebreak:
   `key=lambda c: (c.rs_return_12w_vs_spy is None, -(c.rs_return_12w_vs_spy or 0.0), c.ticker)`. Keep `_watch[:_cap]`. **Never read `rs_rank`.**
2. **The #27 cap audit row** (the `run_warnings.append` with `dropped_count`) gains two keys:
   - `"rank_key": "rs_return_12w_vs_spy desc"`
   - `"dropped_tickers": sorted(<the watch tickers not kept>)`
   All existing keys stay, with the same values.
3. **Rewrite the block comment** to say what the code does today: aplus never capped; watch ranked by `rs_return_12w_vs_spy` desc, None last, ticker asc; truncated to the cap. No mention of `rs_rank`, and no promise about future behaviour (CLAUDE.md gotcha #31).

## Tests (TDD: each discriminator RED on current code first, then GREEN)

Build them from the LIVE shape: `rs_rank=None`, `rs_method='fallback_spy'`, distinct `rs_return_12w_vs_spy` values (live values are fractions, e.g. `1.145`, `0.083`).

- **Seeding helper:** give `_seed_aplus_watch_skip_candidates_and_run` an optional per-row RS override (for example `rs_overrides: dict[str, tuple[int | None, float | None, str]] | None = None`, mapping ticker → `(rs_rank, rs_return_12w_vs_spy, rs_method)`). The default stays exactly as today, so no other fixture changes.
- **(a)** Three watch rows, all `rs_rank=None`, excess `0.083`, `1.145`, `0.40`, cap 1 → no raise; detections are written for the aplus row and the `1.145` row only; the audit's `dropped_tickers` names the other two, sorted; `rank_key` is present. (RED today: the TypeError.)
- **(b)** One watch row with excess `None` sorts LAST and is dropped before any numeric row (e.g. cap 2 over three rows, one None → the None row is the one dropped).
- **(c)** Equal excess values → ticker ASC decides which survive.
- **(d) Direction discriminator with `rs_rank` POPULATED:** rows where `rs_rank` and excess disagree (e.g. W1 rs_rank 95 / excess 0.05, W2 rs_rank 10 / excess 0.90), cap 1 → W2 survives. This pins that `rs_rank` is not the key in either direction.
- **Existing `test_lever1_active_cap_audit_accuracy`:** keeps every count assertion and additionally asserts WHICH watch name survived and the `dropped_tickers` list. With the helper's default (all rows equal excess `12.0`), ticker ASC decides: `W1` survives, `["W2", "W3"]` dropped. Work that value out before you assert it.
- `test_lever1_dormant_default_no_cap_no_audit` must stay green unchanged.

Verify each discriminator's arithmetic under the OLD code and the NEW code before you lock it: it must fail before the fix and pass after.

## Gates

1. `python -m pytest tests/pipeline/test_pattern_pool_dormant_levers.py -q` green.
2. `ruff check swing/pipeline/runner.py tests/pipeline/` clean, with no new findings.
3. The full fast suite on your branch: `python -m pytest -m "not slow" -q -p no:cacheprovider -n 8`, with output to a file under `~/swing-data/review-transcripts/cap-fix/`. Report passed/skipped/failed and the exit code from that file.
4. Conventional commits, pathspec commits, no `Co-Authored-By`, no `--no-verify`, no amend.

## Do NOT

- touch `swing.config.toml` or `~/swing-data/user-config.toml` (the operator restores the cap to 15 after the merge);
- open the live DB for writing; you need no live DB read at all;
- add a `step_guard` warnings entry for raises (that is D100, its own rider) or a research-health check (D101);
- run Codex. The orchestrator runs Reviewer B on the diff after your return.

## Return report (to the orchestrator, in chat; you never post to mailboxes)

Commits (sha + subject), the diff stat, each discriminator with its RED evidence (the failing assertion or the TypeError) and its GREEN, the full-suite counts and the transcript path, and anything you had to decide that this brief did not settle.
