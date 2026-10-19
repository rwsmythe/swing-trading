# Phase 22 rider — D81: the in-run `coverage_gaps` monitor cannot see its own run's skip-warnings (dispatch brief)

**From:** CHARC. **To:** the orchestrator (riders stage: executing directly, no plan loop). **Operator pre-authorized 2026-10-18 ("concur with the fix", relayed verbatim by RD at `20261018T235613Z`).** **Cell:** `implementer-sonnet-high` (settled design; one plumbing seam, one call-site line, tests). **Reviewer A:** one `strong` round to convergence per the recipe. **Reviewer B:** at the orchestrator's gate, over the finished tree (production code under `swing/` is touched). **Priority (RD's timing view, operator-visible):** low — it costs a false RED only on the nightly after a missed night; it need not land before the pause ends 10-20. **No tripwire:** no schema, no new module, no dependency, no new process, no `swing/trades`/`swing/data` carve-out.

## §0 READ FIRST (pointers; re-ground every line number against live code)

- The finding, CHARC status `20261018T235433Z` (RD + operator inboxes), and register row **D81** in `docs/tool-director-context.md` §4.
- `swing/pipeline/runner.py:1069-1087`: `_step_research_health` runs INSIDE the run, after `_step_shadow_expectancy`, BEFORE `lease.step("complete")` and `lease.release(state="complete", warnings_json=json.dumps(run_warnings))`. The run's `warnings_json` reaches the ledger only at release — AFTER the monitor has read.
- `swing/pipeline/runner.py:1343-1441`: the step. It already receives `run_id` and `run_warnings` by argument and uses `run_warnings` ONLY to append its own broken-context entry (`:1419-1424`). It opens its own `mode=ro` connection (C-NH2) and calls `_rh.compute_research_health(conn, cfg=cfg, exports_root=exports_root)` (`:1403`).
- `swing/monitoring/research_health.py`: `compute_research_health` (`:2114`) → `_check_coverage_gaps(conn, now=now)` (`:1409`) → the three CALIBRATION-C globals at `:1461-1463`: `_global_observed_sessions` (reads `pattern_forward_observations` — the live run's observations ARE visible), `_run_observed_sessions` (`:1192`, `state='complete'` ONLY), `_observe_skip_index` (`:1101`, `state='complete'` ONLY, tie `observation_date == that row's data_asof_date`). The clause text is the CALIBRATION C block at `:1055-1083` and the partition docstring at `:1333-1366`.
- The live run's session date is the ledger's own value: `pipeline_runs.data_asof_date` on the `state='running'` row keyed by `run_id` (written at `acquire_lease`, `runner.py:610` / `lease.py:243`).
- Tests: `tests/monitoring/test_research_health_checks.py` — fixtures `_seed_detection` (`:41`), `_seed_observation` (`:66`), `_seed_pipeline_run` (`:89`, a RAW `pipeline_runs` insert carrying `warnings`); the CALIBRATION-C tests from `:1082` (`test_coverage_calib_c_*`) are the shape to copy, especially `_dino_skip_warning_accepted` (`:1169`) and `_zero_obs_observe_failure_still_red` (`:1330`).

## §1 THE PREMISE (verify before building; the fact belongs to the code)

Every acceptance clause that consults the RUN LEDGER reads only `state='complete'` rows, and the running run's `warnings_json` is written at release. So at step time the live run's `pattern_observe` skip-warnings are structurally invisible: a ticker whose current session is skip-explained has no observation (clause-1's observed half false), no visible skip (clause-1's skip half false, clause-2b false), and clause-2a stays locked behind clause-1 — every missed session on that ticker COUNTS. Twenty seconds later the row is complete and the same holes are ACCEPTED.

Reproduced on the live DB (`mode=ro`, 2026-10-18): run 191 carried 391 tied skip-warnings and the pause left 5 missed sessions for those tickers → 391 × 5 = **1955**, the 10-11 RED mail's count; run 194 carried 205 and 2 missed sessions → 205 × 2 = **410**, the 10-18 RED mail's count and exactly the number RD's probe saw move to accepted 20 s later. **Cell: re-run this count yourself** (`SELECT data_asof_date, warnings_json FROM pipeline_runs WHERE id IN (191,194)` on a `mode=ro` connection; count `step='pattern_observe'` entries with `reason` in `_OBSERVE_SKIP_REASONS` and `observation_date == data_asof_date`). If the numbers do not reproduce, STOP and route back.

## §2 THE CHANGE, exactly

**C1 — `swing/monitoring/research_health.py`: the monitor may be told about the LIVE run.** Add a keyword-only `live_run: tuple[str, list[dict]] | None = None` to `compute_research_health`, threaded to `_check_coverage_gaps`, and from there into BOTH ledger readers:

- `_observe_skip_index(conn, *, live_run=None)`: after the completed-rows loop, if `live_run` is given, run the SAME per-item filter (step == `pattern_observe`, reason in `_OBSERVE_SKIP_REASONS`, both dates canonicalize, `obs_c == asof_c` where `asof_c` is the live run's `data_asof_date`) over the live list and add the pairs. ONE filter body, two input sources — extract the per-row loop into a helper so the completed-row path and the live path cannot diverge (the two-entry-paths-one-derivation shape the file already uses at `:1372-1377`).
- `_run_observed_sessions(conn, *, live_run=None)`: if the completed-run read returns a set, add the live run's canonical `data_asof_date` to it. If the live asof does not canonicalize, IGNORE the live run for this reader (conservative: the ledger half stays as it was; never return `None` because of the live value, and never accept-everything). If the completed-run read returns `None` (no completed runs / unavailable), it STAYS `None` — a live run does not prove a ledger.

Semantics preserved, stated so RD's gate can read it: the three clauses (1 / 2a / 2b) and the accepted-historical surfacing are UNCHANGED; what changes is the VISIBILITY TIMING of evidence the run itself produces. The admission rule is not loosened: a live run's session added to `run_observed_sessions` makes a hole AT that session a non-2a case (a zero-observation observe failure at the live session stays RED unless skip-explained), which is the strictly conservative direction.

**C2 — `swing/pipeline/runner.py` `_step_research_health`:** while the `mode=ro` connection is open, read the live row's `data_asof_date` by `run_id` (`SELECT data_asof_date FROM pipeline_runs WHERE id = ?`; `run_id is None` or no row → `live_run=None`, unchanged behavior) and pass `live_run=(asof, run_warnings or [])` to `compute_research_health`. The script path (`scripts/research_health.py`) passes nothing and is unchanged. The step's existing `run_warnings.append(...)` for the broken-context guard is unchanged.

**C3 — docstrings, by REPLACEMENT (harness-architecture §2: supersession is replacement, never annotation).** `_observe_skip_index`'s and `_run_observed_sessions`'s "ONLY state='complete' runs" sentences become: completed runs PLUS, when supplied, the live run that is about to complete — a FAILED or stale run's warnings still never explain a hole, because only completed rows are read from the ledger and the live run is supplied solely by the in-run step. The CALIBRATION C block (`:1055-1083`) gains ONE sentence naming the live-run input; no clause text changes. The step docstring in `runner.py` gains one sentence under C-NH2. No history narrative in any docstring — it goes in the commit message.

## §3 FORK CENSUS (the rulings are made; nothing is open)

- **Where the live asof comes from:** the ledger row by `run_id`, not a runner local — the same value release will leave, sourced from the row (gotcha #30 shape: the row's own provenance).
- **Moving the step after `lease.release`:** REFUSED. It would run outside the lease and lose the step's own `run_warnings` append (the RD 8.1(b) broken-context entry), and the artifact/push ordering the 19-B guards assume.
- **Gating the push only (compute stale, suppress the mail):** REFUSED. The artifact `latest.json` and the GUI stoplight would still show the stale RED for one cycle; the fix is to compute the state the run will have.
- **Failed-after-step runs:** ACCEPTED LIMITATION, declared with reason (§6).

## §4 SCOPE — exactly this, refuse the rest

`swing/monitoring/research_health.py` (C1, C3) · `swing/pipeline/runner.py` `_step_research_health` body + docstring only (C2, C3) · `tests/monitoring/test_research_health_checks.py` (+ a runner-step test beside the existing step tests if one exists; else in `tests/monitoring/`). NOTHING else: no change to the push helper, the artifact writer, the guards, the watch-standard, the GUI, the script. The 205-ticker standing skip population and the `invalid_ohlc`/`degenerate_risk` watches are RD's and out of scope. Suite: the fast suite on the final head; `ruff check swing/` clean.

## §5 TESTS — RED first, each fails the null implementation of one clause

Build every fixture with the existing raw-insert helpers; the "live" run is a `_seed_pipeline_run(..., state='running')`-shaped row (add a `state=` parameter to the helper if it lacks one) whose `warnings_json` is NULL, with the warnings passed through `live_run` instead — the production shape (the ledger row exists, its warnings are not yet written).

1. **`test_coverage_calib_c_live_run_skip_explains_missed_sessions`** (the cry-wolf): completed prior run observed S1 for ticker T (observation seeded); sessions S2 (missed night: no run row, no observations anywhere) and S3 (the live session); a `running` row with `data_asof_date=S3`; `live_run=(S3, [pattern_observe skip for (T, S3), reason "no bar for observation_date"])`. Without `live_run` → RED/YELLOW with 2 missing for T (assert this FIRST — it is today's behaviour and the RED half). With `live_run` → GREEN, both S2 (2a via clause-1's skip half) and S3 (2b) accepted and named in `detail`.
2. **`test_coverage_calib_c_live_run_skip_tie_must_match_asof`**: same, but the live skip's `observation_date` is S2 while the live asof is S3 → the skip is NOT indexed; S3 stays counted (the MAJOR-R2-2 tie survives the merge).
3. **`test_coverage_calib_c_live_run_zero_obs_at_live_session_still_red`**: a live run at S3 with NO skip for T and no observation of T at S3 → S3 counted (adding the live session to `run_observed_sessions` makes it a non-2a case; the zero-observation observe failure is never explained by liveness).
4. **`test_coverage_calib_c_live_run_does_not_create_a_ledger`**: zero completed runs (reader returns `None`) plus a live run → clause-2a stays disabled; a missed-session hole is still counted unless 2b explains it.
5. **`test_coverage_calib_c_live_run_malformed_asof_ignored`**: live asof `"20261016"` (non-canonical) → neither reader uses it; result identical to `live_run=None`.
6. **Runner step test**: `_step_research_health` with a seeded `running` row and `run_warnings` carrying a skip → `compute_research_health` receives `live_run=(row asof, the list)` (assert via monkeypatching `_rh.compute_research_health` and capturing kwargs); with `run_id=None` → `live_run=None`. The existing broken-context append must still occur.

Every existing `test_coverage_calib_c_*` stays green unchanged — the no-`live_run` path is byte-equivalent.

## §6 ACCEPTED LIMITATION (declared in the Reviewer A/B prompts WITH its reason; the reviewer is invited to challenge it)

A run that FAILS after `_step_research_health` has already counted its own warnings produced one artifact + possibly one GREEN/no-mail where the strict completed-only reading would have mailed RED. Reason accepted: the next run (or `scripts/research_health.py`) overwrites `latest.json`; the cost is a false GREEN for at most one night after a failed run, versus the current cost of a false RED on every nightly after any missed night on the one channel that is supposed to mean a barrier regression. The direction is explicitly traded; the brief says so and the ledger records it.

## §7 RETURN (the orchestrator posts after QA; the implementer reports to the orchestrator in chat, never to a director inbox)

The return names: the two counts re-derived in §1; the six tests with their RED→GREEN evidence; the Reviewer A transcript (banner, `tokens used` footer, anchored verdict token, `^ERROR`=0) and the per-round evidence set copied to `~/swing-data/review-transcripts/<worktree>/`; the merged-head suite line with its SHA. The orchestrator's B transcript on the tree being merged is named in the merge request (harness-architecture §5.1). RD's gate item (his `20261018T235613Z`): the watch-standard's #3 clause-1/2a/2b accept rule and the accepted-historical surfacing read unchanged — the return quotes the C3 sentences so RD can read that from the text.
