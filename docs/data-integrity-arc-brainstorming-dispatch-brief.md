# Regular-Session + Completed-Day Data Integrity -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the data-integrity-arc brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming DESIGN SPEC (no production code) for a **data-integrity arc** that enforces a single principle the operator stated: **the tool only ever pulls + locks REGULAR-SESSION, COMPLETED-TRADING-DAY data.** Four threads, one coherent arc:
1. **No extended-hours data on ANY Schwab market-data call** -- `price_history` (`needExtendedHoursData=False`) AND `quotes` (regular-session fields, not extended/last).
2. **Completed-trading-day enforcement** -- when the pipeline/web runs DURING or AFTER trading hours, **discount the current (in-progress) day's data** entirely; use only the last *completed* session. No partial mid-day bar, no after-hours print.
3. **A lock-guard** -- the append-only temporal log (`pattern_forward_observations.ohlc_today_json`, locked-at-observation, NEVER re-fetched) must be *unable* to lock a partial/extended bar. The lock is a one-way door (the operator's framing: "we lock data after pulling it to prevent post-facto changes" -- so what gets locked must be clean at pull time).
4. **(FOLDED IN -- integration-review Issue #5)** a **uniform topbar-date anchor policy** across the base-layout VMs (today they disagree -- some use the forward `action_session_for_run`, some the backward `last_completed_session`).

**The motivating principle (operator, 2026-06-05):** the Phase-14 temporal observation log is append-only with lock-at-observation -- a locked bar is permanent, with no post-facto correction. The pool-widening (`#23`) just put the nightly pipeline into the business of locking forward-walk data every night. So the data pulled + locked MUST be completed-regular-session, enforced at the PULL stage (before the lock), or it is permanently wrong.

**Brief:** `docs/data-integrity-arc-brainstorming-dispatch-brief.md` (this file).

**Status / provenance:** THE big near-term Phase-15 arc. Both small items closed 2026-06-05 (the finviz signature fix `52fcadb1`; the Phase-14 cross-sub-bundle integration review). This arc was scoped operator-paired in the 2026-06-04/05 session + sharpened by the integration-review findings; the operator's blanket policy ("never consider extended-hours trading in this tool at this point in time" + "enforce only data from closed trading days") is LOCKED (§1).

**Context:** main HEAD at this dispatch: see §8 (branch from it). ~7130 fast tests green; schema v24. Whether this arc needs a schema change is an OPEN question (likely NO -- it hardens existing pull/anchor logic; confirm at brainstorm). The Schwab **L2 LOCK** (zero new Schwab REST *endpoints*) is preserved -- adding `needExtendedHoursData=False` is a PARAMETER on the EXISTING `price_history` endpoint, not a new endpoint.

**Cumulative discipline:** the CLAUDE.md **yfinance/market-data** gotchas (the in-progress partial-bar strip; `action_session_for_run` vs `date.today()`; OHLCV-fetch-scope; the write-through-archive F6 empty-result rule) + the **Schwab** gotchas (camelCase kwargs; the price_history minute-default footgun; sandbox-vs-production domain-row gating) + the **session-anchor read/write mismatch** gotcha family (the recurring forward-vs-backward bug that Issue #5 is an instance of) are BINDING. ZERO `Co-Authored-By`; ASCII discipline.

**Expected duration:** ~3-5 hours brainstorming + a Codex chain to convergence. Spec line target **~500-700 lines** (the bulk is the data-pull-and-lock + session-anchor AUDIT + the enforcement design + the Issue-#5 topbar policy).

**Skill posture:**
- Invoke the `copowers:brainstorming` skill against this brief.
- **Codex chain count: SINGLE chain** at end, run to CONVERGENCE (`NO_NEW_CRITICAL_MAJOR`; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`). (This arc has a methodology dimension -- the completed-day semantics -- so if the spec makes a claim about WHICH session is "completed" under various clocks, consider whether a second chain is warranted; orchestrator discretion at the spec phase.)
- **Codex transport -- WSL fallback (MCP `codex`/`codex-reply` DEAD).** USE EXACTLY: `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'` (PATH prefix REQUIRED; prove liveness with `codex --version` -> `codex-cli 0.135.0`). Pass the prompt via STDIN (`cat prompt.txt | codex exec -s read-only --skip-git-repo-check -`). Pre-generate the diff on Windows; tell Codex NOT to run git. PERSIST each round's PROMPT AND RESPONSE (incl. `### Verdict`) to `.copowers-findings.md`. Memory `feedback_wsl_native_codex_invocation` + `feedback_implementer_persist_codex_responses`.
- Output: design spec at `docs/superpowers/specs/2026-06-05-data-integrity-regular-session-completed-day-design.md`.

---

## §0 Read first (orchestrator-verified grounding from the 2026-06-04/05 session; re-grep at writing-plans per #2)
1. **THIS BRIEF end-to-end.**
2. **The ext-hours root cause (verified):** `swing/integrations/schwab/marketdata.py:428-436` -- the `client.price_history(...)` call passes `periodType/period/frequencyType/frequency/startDate/endDate` but **OMITS `needExtendedHoursData` + `needPreviousClose`** (the docstring `:38-44` lists them as valid kwargs) -> Schwab's server default `needExtendedHoursData=true` -> daily candles fold in pre/post-market prints -> a post-market close above the regular high (or pre-market open below the low) -> the strict `OhlcvBar` invariant (`swing/integrations/schwab/models.py:540-551`: `if self.low > oc_min` / `if self.high < oc_max`, NO tolerance) raises `ValueError` -> the ladder's `except Exception` (`marketdata_ladder.py` `fetch_window_via_ladder`) logs "unexpected error from T-C.1 wrapper" -> yfinance fallback. **Live evidence:** the `schwab_api_calls` audit table holds ~50 `error` rows with `OhlcvBar invariant violated` messages; ~16% of `marketdata.pricehistory` calls error; the `/schwab/status` page surfaces the success/error mix.
3. **The quotes path:** `swing/integrations/schwab/marketdata.py` `get_quotes_batch` + `swing/integrations/schwab/mappers.py` `map_quotes_to_price_cache_entries` -- audit whether the quote mapping reads REGULAR-session fields (e.g. `regularMarketLastPrice`/`regularMarketTradeTime`) vs the extended/last fields. (The Schwab `/quotes` response carries both.)
4. **The session-anchor machinery (EXISTS -- the arc hardens/enforces, does NOT rebuild):** `swing/evaluation/dates.py:21` `last_completed_session(now)` ("never serve a partial in-progress daily bar") + `:43` `action_session_for_run(now)` (forward); `swing/pipeline/runner.py:1020` `lease_data_asof(cfg, lease)` (reads the run's `data_asof_date`); `swing/pipeline/temporal_metadata.py:30` `_slice_to_asof(bars, asof)` ("strips the yfinance in-progress partial bar"). The CLAUDE.md gotcha: yfinance `history(interval="1d")` includes the in-progress partial bar -> strip it via the exchange-session helper (HST lags ET).
5. **The lock surface:** `swing/data/migrations/0022_phase14_temporal_log.sql` -- `pattern_forward_observations.ohlc_today_json` is NOT NULL, LOCKED at observation, never re-fetched; the observe step `swing/pipeline/runner.py:2503` (`_step_pattern_observe`) calls `_bar_for_date(cfg, ohlcv_cache, ticker, observation_date)` (`:2427`) then `build_ohlc_today_json(bar)`. Also the OHLCV archive (`swing/data/ohlcv_archive.py`) + the web `OhlcvCache` (`swing/web/ohlcv_cache.py`).
6. **Issue #5 (the topbar inconsistency, verified via a same-moment sweep 2026-06-05):** the shared `base.html.j2` topbar `session_date` is set PER-VM; at one moment dashboard/watchlist/journal/metrics showed `action_session` (6/5) while reviews/patterns-queue showed `last_completed_session` (6/4). The #22 fix aligned `/reviews/pending` to `last_completed_session` but journal + metrics (also backward-looking) still use the forward anchor. Audit EVERY base-layout VM's `session_date` source: `DashboardVM`, `WatchlistVM`, `JournalVM`, the reviews VMs, the metrics VMs, `PipelineVM`, `PageErrorVM` (the shared-`base.html.j2` 5-VM-rule family).
7. **The integration-review findings + the capital-friction Issue #3:** `docs/phase14-integration-review-checklist.md` (the issues log). Issue #3 (capital-friction position count=0 for Run#89 from `account_equity_snapshots` despite an open trade) is ADJACENT -- decide in/out at the brainstorm (Q5).
8. **`docs/orchestrator-context.md`** (brief-authoring disciplines) + the **memory/** directory (esp. `feedback_orchestrator_qa_implementer_product`, `feedback_await_return_before_qa`, `feedback_no_false_green_claim`, `feedback_verify_regression_test_arithmetic`, `feedback_codex_round_limit_suspended`, `feedback_isolated_venv_for_shared_dependency_migration` [N/A unless a shared dep moves -- it should not], `feedback_seeded_gate_masks_default_state`).

---

## §1 LOCKed scope (operator-stated; BINDING -- propagate, do NOT re-open)
- **L1 (no extended hours -- ALL Schwab market-data calls).** The tool **NEVER considers extended-hours data** (operator: "at this point in time"). `price_history` requests regular-session-only (`needExtendedHoursData=False`); `quotes` uses the regular-session fields. Applies to EVERY Schwab market-data call site (pipeline + web + CLI verify).
- **L2 (completed-trading-day only).** When run DURING or AFTER trading hours, the tool **discounts the current (in-progress) day** and uses only the last COMPLETED session. No partial/in-progress bar, no after-hours print, ever enters a computation or a lock.
- **L3 (the lock is sacred).** The append-only + `ohlc_today_json` lock-at-observation invariant is PRESERVED. The arc ADDS a guard so the lock can never capture a partial/extended/current-day bar -- it does NOT loosen the lock (no re-fetch/regeneration of locked facts).
- **L4 (harden, don't rebuild).** The arc HARDENS + uniformly ENFORCES the existing `last_completed_session`/`action_session_for_run`/`data_asof_date`/`_slice_to_asof` machinery. It does NOT rewrite the date system.
- **L5 (Schwab L2 LOCK preserved).** `needExtendedHoursData=False` is a parameter on the EXISTING `price_history` endpoint -- ZERO new Schwab REST endpoints. Re-validate the kwarg exists on the schwabdev 3.0.5 signature (the signature-pin test).
- **L6 (Issue #5 folded in).** A uniform topbar-date anchor policy: forward (`action_session_for_run`) for forward-planning pages, backward (`last_completed_session`) for history/analysis pages -- applied CONSISTENTLY across all base-layout VMs. The brainstorm fixes the inconsistency, not just one page.

---

## §2 The FIRST MOVE -- a data-pull-and-lock + session-anchor AUDIT (the spec's spine)
Before designing the enforcement, ENUMERATE (a table in the spec) every surface where market data is PULLED, where it is LOCKED, and where a session date is ANCHORED. For each: the current source/anchor, whether it includes ext-hours, whether it can include the current/partial day, and the proposed enforcement. At minimum:
- **Schwab `price_history`** (pipeline detect/observe/charts + web OhlcvCache ladder + CLI `--verify-marketdata`) -- ext-hours: YES (default); fix: `needExtendedHoursData=False`.
- **Schwab `quotes`** -- ext-hours: AUDIT; fix: regular-session fields.
- **yfinance fallback** (`OhlcvCache`/`ohlcv_archive`/the legacy `PriceFetcher`) -- partial-bar: the in-progress bar IS included by yfinance; is it stripped everywhere (or only in `_slice_to_asof` on the detect path)?
- **The OHLCV archive** (`ohlcv_archive.py`) -- does it ever persist a current-day/partial bar that a later read locks?
- **The temporal-log observe lock** (`_step_pattern_observe` -> `_bar_for_date` -> `build_ohlc_today_json`) -- can `observation_date` ever be the current/in-progress session? can the bar be partial/extended? (THE critical lock surface.)
- **The price cache / `account_equity_snapshots`** (Issue #3) -- Schwab-sourced; current-day/partial relevance.
- **Every base-layout VM topbar `session_date`** (Issue #5) -- forward vs backward; the audit table from §0.6.

---

## §3 Open design questions (brainstorm, operator-paired)
- **Q1 -- completed-day enforcement mechanism + locus.** WHERE is the current/partial-day strip enforced so it is UNIFORM (a single chokepoint -- e.g. the `OhlcvCache`/archive read -- vs per-consumer)? Is `data_asof_date` ALWAYS the last completed session even when a run starts mid-session or after-hours? (Confirm `data_asof_date`'s computation.) How does the HST/ET timezone + the exchange calendar drive "completed"?
- **Q2 -- the uniform topbar policy (Issue #5).** The forward-vs-backward classification per page; enforce via a shared helper so a VM can't silently pick the wrong anchor; a test that the topbar date is consistent across same-type pages.
- **Q3 -- quotes regular-session.** Does the quote mapping need to switch to `regularMarket*` fields? Does the quote even feed a locked surface, or only ephemeral display?
- **Q4 -- the lock-guard.** The assertion/test that the temporal log can NEVER lock a partial/extended/current-day bar (e.g. reject at `build_ohlc_today_json`/`_bar_for_date` if the bar's date == the current in-progress session OR the bar fails a regular-session sanity check). Where does it sit?
- **Q5 -- Issue #3 in/out.** Is the capital-friction position-count-from-`account_equity_snapshots` discrepancy a data-integrity-arc item (a snapshot-completeness issue) or a separate small fix? Audit where the count is sourced + why Run#89 recorded 0 with an open trade.
- **Q6 -- the OhlcvBar invariant + error classification.** Once ext-hours is off, do the invariant violations vanish (regular-session OHLC is internally consistent)? Should the invariant ALSO gain a tiny float-rounding epsilon? Should an OHLC-consistency failure be classified DISTINCTLY (a typed `SchwabBarConsistencyError`) instead of the catch-all "unexpected error" (so residual cases log clearly + the `/schwab/status` page reads honestly)?
- **Q7 -- migration?** Does any of this need a schema change (likely NO -- it is pull/anchor logic)? If a lock-guard needs to record "regular-session-verified" provenance, weigh it (D4-style: prefer no schema).

---

## §4 OUT OF SCOPE (do not design into V1)
- The broader **Schwab Phase B/C** (the `cfg.data_source.primary` yfinance->schwab flip + parity study; trade automation) -- separate, larger.
- A **rewrite** of the date/session machinery (L4 -- harden + enforce the existing helpers).
- **Issue #2 + #4** (the non-uniform empty-state messaging + the Schwab nav link) -- the separate small polish batch.
- **Historical backfill / re-locking** of already-locked temporal-log bars (the lock is append-only; V1 is forward-only -- clean data from ship date; document any already-locked ext-hours bars as an accepted L6-style limitation).
- Intraday/sub-day precision (the tool is daily-bar; current-day means the in-progress daily session).

---

## §5 Cumulative discipline BINDING
- The **session-anchor read/write mismatch** gotcha family (read the WRITER's anchor before locking a read predicate; `>=` forward / strict `>` backward; write-then-read round-trip tests) -- Issue #5 is a direct instance.
- The **yfinance partial-bar strip** + **OHLCV-fetch-scope** + the **F6 write-through-archive empty-result** rule.
- The **Schwab** camelCase-kwarg signature-pin discipline (re-validate `needExtendedHoursData` on 3.0.5); the price_history minute-default footgun; the sandbox-vs-production domain-row gating (market-data ladder falls through to yfinance under sandbox).
- The **append-only / lock-at-observation** invariant (L3); `feedback_verify_regression_test_arithmetic` (each test value under both the old ext-hours/current-day path AND the regular-session/completed-day path); ZERO `Co-Authored-By`; ASCII; re-run the suite on the MERGED HEAD before any green claim (isolate the known xdist flakes).

---

## §6 Workflow + §7 Deliverable
A single copowers cycle: `copowers:brainstorming` (this) -> `copowers:writing-plans` -> `copowers:executing-plans`. **Output:** design spec at `docs/superpowers/specs/2026-06-05-data-integrity-regular-session-completed-day-design.md` (mirror the prior brainstorm spec format): §1 Architecture + the motivating lock-principle · §2 the data-pull-and-lock + session-anchor AUDIT table (the spine) · §3 L1-L6 · §4 the ext-hours fix (price_history + quotes) · §5 the completed-day enforcement (locus + mechanism) · §6 the lock-guard · §7 the uniform topbar policy (Issue #5) · §8 Issue #3 disposition (Q5) · §9 the OhlcvBar invariant + error-classification (Q6) · §10 Test + gate strategy (incl. a live re-fetch gate to confirm the OhlcvBar errors vanish) · §11 Schema impact · §12 Slice recommendation · §13 OQs · §14 Cumulative discipline · §15 Out-of-scope. **Commit stem:** `docs(data-integrity-spec): brainstorm <draft|R1|...> -- ...` (final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `data-integrity-arc-brainstorming`. Dir `.worktrees/data-integrity-arc-brainstorming/`. **Branch from main HEAD = the commit that ADDS this brief** (the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief + the integration-review checklist). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). **NO live-DB touch** -- this is BRAINSTORMING (a spec); do NOT run a connecting `swing pipeline`/`swing schwab fetch` against the operator's live DB. (You MAY read the live `schwab_api_calls`/`trades`/`account_equity_snapshots` tables READ-ONLY [`mode=ro`] to ground the audit -- but do NOT write.)
- **Codex chain count:** SINGLE chain at end, to convergence via the WSL prefix + stdin form.

---

## §9 If you get stuck / return report
- If the ext-hours fix seems to need a new Schwab endpoint, STOP -- it is a PARAMETER on the existing `price_history` (L5).
- If completed-day enforcement seems to need a date-system rewrite, STOP -- harden the existing helpers (L4).
- If a fix seems to need loosening the append-only lock, STOP -- the lock is sacred (L3); guard at the pull stage.
- HOLD THE LINE: regular-session-only on ALL Schwab calls; completed-day-only data; the lock can never capture a partial/extended bar; a uniform topbar anchor.
- **Return report:** mirror the prior brainstorm return reports -- final HEAD + commit breakdown; the Codex convergent verdict (cite `.copowers-findings.md`); the AUDIT table (every pull/lock/anchor surface + its disposition); the L1-L6 verification; the ext-hours fix design (price_history + quotes); the completed-day enforcement locus; the lock-guard; the uniform-topbar policy + the per-VM audit; the Issue-#3 disposition (Q5); the OhlcvBar-invariant/error-classification decision (Q6); the schema verdict; the OQs flagged for the operator at writing-plans; ZERO Co-Authored-By; worktree teardown status; writing-plans dispatch-readiness.

---

*End of brief. Regular-session + completed-day data-integrity brainstorming dispatch (THE big near-term Phase-15 arc) -- design how to enforce that the tool only ever PULLS + LOCKS regular-session, completed-trading-day data: no extended-hours on ANY Schwab call (`price_history needExtendedHoursData=False` + the quotes regular-session fields); discount current-day/partial data when running during/after hours; a guard so the append-only temporal log can never lock a partial/extended bar; AND (folded in) a uniform topbar-date anchor across the base-layout VMs (integration-review Issue #5). HARDEN the existing session-anchor machinery, don't rebuild it. The lock-at-observation is sacred -- enforce at the PULL stage. First move: the data-pull-and-lock + session-anchor AUDIT. OUTPUT: a design spec the writing-plans phase can derive a plan from.*
