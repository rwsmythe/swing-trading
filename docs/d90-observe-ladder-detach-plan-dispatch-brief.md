# D90 -- detach the Schwab ladder from observe's populate: WRITING-PLANS dispatch brief

**Audience:** a fresh implementer cell with no prior conversation context.

**Authority:**
- **Operator, 2026-10-20, verbatim:** "Yes, D90 after D89 and before soft-stop arc".
- **D89 is MERGED** on main at `717e4ebe`.
- **The register row:** D90 in `docs/tool-director-context.md` (search `| D90`). Read it IN FULL. RD's measurement call, CHARC's FORM, the ADMISSIBILITY condition and the WITNESS in it are BINDING. The design is ruled; this cell encodes it.

**Cell:** `implementer-opus-xhigh` for writing-plans.

**KEEP YOUR READING NARROW.** Read ONLY:
- this brief;
- the D90 row;
- `docs/implementer-dispatch-recipe.md` section 3: the plan-stage protocol, the per-round assertions, and the ledger-cut note;
- for form only: the D89 plan and its N-V neutrality test, `docs/superpowers/plans/2026-10-20-d89-observe-read-memo.plan.md` and `tests/pipeline/test_observe_read_memo_neutrality.py`. D89 is the precedent this rider follows;
- the code named below.

Do NOT read `comms/`, director state files, or other arcs' ledgers.

**Worktree:** create `C:\Users\rwsmy\swing-trading\.worktrees\d90-detach` on a new branch `d90-detach`, off main at the commit that carries this brief.
- Run everything with `PYTHONPATH=.`.
- Live DB: `mode=ro` only; copies only by plain sqlite3 `backup`; NEVER through `swing`'s `connect`.
- Probe cache behaviour only on COPIES of cache files, never on the live prices-cache.

## 1. Code to read

- `swing/web/ohlcv_cache.py`: `get_or_fetch` (about :175-245), `_fetch_bars_window` (about :270-310), and the ladder versus no-ladder branches and what each stores in `_bars_store`.
- `swing/pipeline/runner.py`:
  - `_bar_for_date` and its populate call. D89 has just changed this function: the memo and `populate_ok`. Re-read it at HEAD.
  - The pipeline bars-hook install, `_install_pipeline_marketdata_caches` (about :340-380 and :481-509).
  - The other pipeline callers of `get_or_fetch` (evaluate, detect, charts). Name each one and confirm it stays on the ladder.
- `swing/web/app.py`: the web process's own ladder hook. It must be unchanged.
- `swing/integrations/schwab/marketdata_ladder.py` (about :505-530): the success path's yfinance re-read.
- The two callers of `swing.data.ohlcv_archive.resolve_ohlcv_window`: `runner.py` (observe) and `swing/latches/reader.py:695`. Both must be named in the plan's closure grep as unchanged.

## 2. Round 0, a premise check (no Codex). Its findings go into your return.

Verify, against the code and the live DB (`mode=ro`):
1. CHARC's form is implementable as stated:
   - `use_ladder: bool = True`, keyword-only, on `OhlcvCache.get_or_fetch`, threaded to `_fetch_bars_window`;
   - `False` takes the `read_or_fetch_archive` branch;
   - BOTH branches store the same full-archive read in `_bars_store`, so the store is safe to share across the two settings.
2. **The register row's admissibility (3):** the "one miss per ticker" reading (238 Schwab + 8 singles + fallbacks ≈ 248 tickers) agrees with the D83 warm writing the ARCHIVE and not `_bars_store`. Verify this at the warm's code before the plan quotes it.
3. **The ordering hazard:** the shared `_bars_store` key is `(ticker, window_days)`. If detect's Pass-1, or anything earlier in the run, stored a ticker through the LADDER branch, observe's `use_ladder=False` call is an in-memory HIT with no fetch at all.
   - State whether that changes any observation row. It should not: both branches store the same full-archive read.
   - State what it does to the witness (Schwab calls inside observe).
4. Run 195's baselines for the witness, from the live DB (`mode=ro`) and `pipeline.log`:
   - `schwab_api_calls` rows with `surface='pipeline'` inside observe's window: 238 expected;
   - their summed `response_time_ms`: 87,395 ms expected;
   - observe's wall.

   With D89 now merged, also note whether a post-D89 nightly exists yet. If one does, use it as the baseline; if not, say so.

**Decide:**
- If every premise HOLDS and no fork appears: write the plan, run the rounds per section 3, and report the census in your return.
- If ANY premise fails, or a design question the row does not settle appears: STOP AND RETURN with the census, every fork with BOTH branches, and the evidence saved to `C:\Users\rwsmy\swing-data\review-transcripts\d90-detach\plan\round0\`.

## 3. The plan (only if section 2 is clean)

Follow the recipe's plan-stage protocol:
- a task ladder plus a test roster, about 1,000 lines or fewer;
- the reasoning lives in a LEDGER beside the plan;
- the binding text is block-quoted in the ledger, with its author named: the D90 row's RD call, CHARC form, admissibility and witness.

**Required content:**
- **Tests:**
  - a discriminating test that observe's populate makes NO ladder/Schwab call (`use_ladder=False` reaches `_fetch_bars_window`);
  - a test that the default `use_ladder=True` path is byte-identical to today, for the bundle worker and for detect/evaluate;
  - an N-V-style two-world test, in D89's form: observation rows equal on the six measurement columns (`detection_id`, `observation_date`, `ohlc_today_json`, `status`, `status_change_event`, `sessions_since_detection`), with and without the detach;
  - one mutation the merge report quotes: observe passes `use_ladder=True`, and the no-Schwab test goes RED.
- **The docstring:** rewrite `_bar_for_date`'s docstring to what the code does after D90. That is, observe's populate never uses the ladder. Remove the D89-era "ladder when the run has a Schwab client" sentence by replacement, not by addition.
- **The closure grep:** it names both callers of `resolve_ohlcv_window` and states that neither changes.
- **The residual, for the merge report:** a ticker latched, then rotated out of the screen and never viewed, carries a provider-mixed range.
- **The witness, per the row:**
  - `schwab_api_calls` with `surface='pipeline'` inside observe = 0 on the merged night;
  - the observe wall drop ≈ the audited Schwab term;
  - rows byte-equal on the N-V set;
  - the docstring reads as the code does.

**Review rounds:**
- `fast` tier, at most THREE counted rounds, then the self-sweep;
- rulings inlined, or a ledger cut before any round section;
- the verdict tokens DESCRIBED, never written line-initially (grep the prompt);
- a per-item checklist, each item answered holds / fails / cannot-tell with a file:line;
- no prior-round reads (grep the transcripts);
- every per-round assertion;
- evidence saved to `...\d90-detach\plan\round<N>\`;
- **STOP AND RETURN at EVERY counted round gate with its ledger row.** Leave the depth column empty;
- commit the plan ONCE, at convergence.

## 4. Gates and return

- Conventional, pathspec-only commits.
- `%(trailers)` empty; no final `-m` paragraph begins with `Word:`.
- No Co-Authored-By, no `--no-verify`, no amend.
- No `swing/` change: this is planning.

**Return in chat only.** You NEVER post to a mailbox and never run `scripts/role_mail.py`. **If anything does not fit, STOP and return.** Do not choose for yourself.
