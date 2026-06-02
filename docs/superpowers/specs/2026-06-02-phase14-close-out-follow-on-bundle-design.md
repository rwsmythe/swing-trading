# Phase 14 Close-Out FOLLOW-ON Bundle -- Design Spec

**Date:** 2026-06-02
**Phase:** 14 close-out tail (FOLLOW-ON bundle; SERIAL, AFTER the close-out polish batch SHIPPED at `f2cd376`, BEFORE B-7)
**Brief:** `docs/phase14-close-out-follow-on-bundle-brainstorming-dispatch-brief.md` (committed `7e89b26`)
**Branch:** `phase14-close-out-follow-on-bundle-brainstorming` (from main HEAD `7e89b26`)
**Skill posture:** copowers:brainstorming; SINGLE Codex chain to convergence.

---

## §1 Overview

Four issues surfaced at the operator-witnessed UNSEEDED gate of the close-out polish batch.
This is a **read-mostly corrections bundle** -- NO new feature, NO schema change (v23 held),
L2-LOCK green (F-1 adds ZERO new `schwabdev.Client.*` sites).

- **F-1 (deep):** the `swing web` server shows the A-7 topbar badge as `Schwab?` **UNKNOWN**
  under healthy production tokens, because no checker liveness sidecar is written in normal
  operation. **The brief's stated hypothesis (the seed `update_tokens()` is a no-op when the
  access token is still valid, so no STARTING sidecar is written) is REFUTED by the code at
  `7e89b26`** -- see §3. The seed writes STARTING before any network call, so an absent sidecar means
  either client-construction returned None (Class A; likely credential plumbing) or the sidecar write
  itself failed silently (Class B); a one-shot diagnostic pins which.
- **F-2 (deep):** the market-weather chart shows `trend: undefined`. **The brief's stated
  hypothesis (the Trend Template bails to NA at `<200` closes; widen the fetch) is INCOMPLETE
  -- the decisive cause is that the trend STATE is read from PERSISTED `candidate_criteria`
  via `current_stage`, and the benchmark (SPY) is not in the evaluated ticker set (finviz + open
  trades), so in the observed path it has no persisted criteria and the read is `undefined`
  regardless of bar count.** See §4. The fix realigns the state-derivation with the operator's ruling
  (compute the classification live from fetched bars; decouple compute-window from display-window).
- **F-3 (short):** the process-grade-trend rolling lines bridge `None` gaps with straight
  diagonals (one `<polyline>` skips `None`s). Emit one polyline per contiguous run. §5.
- **F-4 (short):** hyp-rec / watchlist thumbnails show matplotlib default axes-spine boxes.
  Hide the spines. §6.

**The two load-bearing deliverables: (1) the F-1 root-cause + fix + UNSEEDED real-token gate;
(2) the F-2 compute-vs-display architecture (incl. the `current_stage` structural finding).**

---

## §2 Pre-locked decisions + LOCKs (binding; brief §1 + §0.1)

- **Sec 9.1 Q2** SERIAL (own cycle, after the close-out batch, before B-7). **Q6** operator-witnessed
  gate at merge. **Q7** single Codex chain.
- **F-2 ruling (operator 2026-06-02):** do NOT pursue a visible 200-MA line; fetch enough history
  for the trend classification + decouple compute-vs-display. The 200-MA's value is the regime STATE.
- **L1** Scope = F-1 + F-2 + F-3 + F-4 ONLY. NO B-7, NO close-out review, NO Phase 15 (the
  schwabdev v3 upgrade stays `#9`; F-1 may INFORM it, does NOT do it), NO new feature.
- **L2** Expected NO schema change (v23 held). Any persisted row/column -> STOP + escalate. F-1's
  liveness stays the existing ephemeral sidecar; NO v24.
- **L3 (L2-LOCK, F-1)** F-1 adds ZERO new `schwabdev.Client.*` call sites (the L2 source-grep test
  `tests/integration/test_l2_lock_source_grep.py` greps `schwabdev.Client.` in `swing/` at HEAD vs
  baseline `bf7e071` and stays green). Do NOT regress the `"Schwabdev"` `setLogRecordFactory`
  redaction.
- **L4** REUSE, do not re-implement. F-1 fixes/wraps the existing P14.N7 seed + checker path
  (reuse `CheckerLiveness`/`record_tick`/`write_liveness_sidecar`/`evaluate_liveness_state`);
  F-2 reuses the existing fetch helpers + the trend-template SMA logic; F-3 reuses
  `_polyline_x`/`_polyline_y`; F-4 reuses the existing renderer.
- **L5** Read-mostly. ZERO swing-domain DB writes (the liveness sidecar is an ephemeral file;
  the chart paths are render-direct; F-2 stays SELECT/compute-only).
- **L6** Production-path tests (#15). F-1's automated test exercises the REAL `create_app` ->
  `_install_web_marketdata_caches` seed path (a sidecar appears under valid-token conditions)
  WITHOUT hand-seeding the sidecar. F-2's test asserts the trend classifies (not `undefined`)
  given >=250 bars via the real fetch/compute path. **Do NOT validate F-1 with a hand-seeded
  sidecar** (the SB5.5 gate's exact mistake; `feedback_seeded_gate_masks_default_state`).
- **L7** ASCII + the A-7 close-out fix preserved (the badge keeps rendering UNKNOWN when no sidecar
  exists; F-1 makes the sidecar actually appear so the badge shows STARTING/ALIVE in normal use).

---

## §3 F-1 -- P14.N7 web-checker liveness in normal operation (the deep item)

### §3.1 The orchestrator-verified mechanics (what the code at `7e89b26` actually does)

Install + seed path (`swing/web/app.py`):
- `create_app` calls `_install_web_marketdata_caches(cfg, price_cache, ohlcv_cache)` **synchronously**
  at startup (`app.py:407-409`) on the startup thread.
- `_install_web_marketdata_caches` (`app.py:251`): `client = _construct_web_schwab_client(cfg)`
  (`:258`); **if `client is None` it RETURNS None at `:259-260`** -- no checker installed, no seed,
  no sidecar. Otherwise it constructs a `CheckerLiveness` (`:269`), calls
  `install_resilient_checker(client, liveness=...)` (`:273`), then the seed
  `client.tokens.update_tokens()` (`:274`).
- `install_resilient_checker` (`checker_resilience.py:115`) replaces `client.tokens.update_tokens`
  with `resilient_update_tokens`, capturing `startup_thread = threading.current_thread()`.
- The wrapper (`:123-149`): a bare `update_tokens()` call (no force flags) takes `origin = "seed"`
  iff it runs on the startup thread, then calls **`liveness.record_tick(origin)` at `:130` BEFORE
  calling `original()` at `:135`.**
- `record_tick("seed")` (`:54-65`) sets `write = True` unconditionally for a seed origin and calls
  `_write_sidecar()` -> `write_liveness_sidecar(...)` -> atomic write to
  `checker_liveness_sidecar_path(env)` (`:154`) = `~/swing-data/schwab-checker-liveness.{env}.json`.

Daemon path (`schwabdev/client.py:50-56`, validated against the installed 2.5.1):
```python
def checker():
    while True:
        if self.tokens.update_tokens() and use_session:
            self._session = requests.Session()
        time.sleep(30)
threading.Thread(target=checker, daemon=True).start()
```
The daemon calls `self.tokens.update_tokens()` via **attribute lookup each iteration** -- so once
`install_resilient_checker` replaces the attribute, the daemon's next tick (within ~30s) reaches
the wrapper -> `origin = "daemon"` -> `record_tick("daemon")` writes a heartbeat sidecar (first tick
+ every 4th tick). **There is NO captured-bound-method bug; the daemon DOES heartbeat once the
client is constructed.** (OQ-2 resolved: the daemon reaches the wrapper.)

The badge VM (`view_models/schwab_checker_badge.py`): `build_schwab_checker_badge(cfg)` returns
`None` (hidden) unless `_is_ladder_active(cfg)` is True (production AND `marketdata_ladder_enabled`);
otherwise it reads the sidecar via `read_liveness_sidecar` + `evaluate_liveness_state` and maps
`{ALIVE,STARTING,DEGRADED,UNKNOWN}` -> labels. `data is None` -> UNKNOWN with the reason
"Schwab client unavailable - no checker running; check credentials/tokens".

### §3.2 The decisive deduction (root cause)

`evaluate_liveness_state(data=None, ...)` returns UNKNOWN **only when the sidecar file is absent /
unreadable** (`read_liveness_sidecar` returns None). Per §3.1, **whenever `_construct_web_schwab_client`
returns a non-None client, the seed writes a STARTING sidecar BEFORE any network call** (the
`record_tick("seed")` fires before `original()`; it is NOT contingent on whether the access token
needed refreshing). Therefore:

> **An observed UNKNOWN (= absent sidecar) with the badge VISIBLE means `_is_ladder_active(cfg)` is
> True (else the badge would be hidden) AND EITHER (a) `_construct_web_schwab_client(cfg)` returned
> None even though the operator's tokens are healthy, OR (b) the seed sidecar WRITE itself silently
> failed.** The brief's "seed no-op" hypothesis is refuted: the seed call is reached and writes BEFORE
> any network round-trip; the gate is no longer the token validity but EITHER client construction OR
> the sidecar write.

**Caveat (Codex R1 Major #1):** `CheckerLiveness._write_sidecar` (`checker_resilience.py:104-108`)
catches every exception and logs only at `debug` level, so a failed sidecar write (e.g. `_user_home()`
resolving to a non-writable / different path under the web process, a permissions error, or the dest
dir not existing) leaves NO sidecar AND NO visible log -- an absent sidecar therefore does NOT
STRICTLY prove construction returned None. The two candidate failure CLASSES are:

**Class A -- construction returned None.** `_construct_web_schwab_client` (`app.py:148-183`) returns
None on exactly these paths (all guarded by the SAME `_is_ladder_active` gate the badge uses, so they
cannot diverge on the config gate):
1. `_is_ladder_active(cfg)` False -> None. **Excluded** by the observed VISIBLE badge.
2. `resolve_credentials_env_or_prompt(cfg, env, allow_prompt=False)` raises `SchwabConfigMissingError`
   (partial env-tier: one of `SCHWAB_CLIENT_ID`/`SCHWAB_CLIENT_SECRET` set, the other missing/blank)
   -> caught at `:164-168` -> None.
3. The same call returns `(None, None)` -- CLIENT_ID/SECRET resolvable at NEITHER the env tier NOR the
   cfg tier (`~/swing-data/user-config.toml [integrations.schwab]`), and `allow_prompt=False` -> None
   at `:170-171`. **Leading hypothesis** (the OAuth *tokens* DB can be healthy while the
   CLIENT_ID/SECRET are absent from the env/cfg the web process reads).
4. `construct_authenticated_client(...)` raises (schwabdev `Client()` init error or the
   post-construction `SchwabAuthError` access-token check) -> caught at `:176-183` -> None.

**Class B -- construction succeeded but the seed sidecar write failed silently** (the `debug`-only
swallow above). The §3.3 diagnostic + the install-anchored write below distinguish A vs B definitively.

### §3.3 The diagnosis step (convert the guess to a fact at executing-plans -- #15, no-guess)

The brainstorm CANNOT run the operator's live `swing web` with production credentials, so the exact
cause (Class A None-path #2/#3/#4 vs Class B silent-write-failure) is not statically determinable. The
plan MUST add a **one-shot, redacted startup INFO log** in `_install_web_marketdata_caches` that
states, in order:
- whether `_is_ladder_active(cfg)` is True;
- whether `_construct_web_schwab_client` returned a client or None **and which None-path fired**
  (creds-missing / creds-partial-raise / construction-raise), via a redacted reason (distinguishes
  Class A);
- the absolute `checker_liveness_sidecar_path(env)` the seed will write to, AND **whether a readback of
  that path immediately after the install-anchored STARTING write SUCCEEDED** (i.e.
  `read_liveness_sidecar(path) is not None`) -- this distinguishes Class B (write failed) from a clean
  STARTING. Because the install-anchored write (§3.4) is no longer swallowed-silent for diagnostic
  purposes, a write failure surfaces in this one line.

The operator reads ONE startup line and the executing-plans implementer pins the cause (A vs B, and
which sub-path). This honors the no-guess discipline + #15 (exercise the real derivation path) without
a rework.

### §3.4 The fix (robust to the diagnosed cause)

**Primary fix (most-likely cause, §3.2 #3): make the web process resolve the Schwab credentials so
`_construct_web_schwab_client` returns a real client.** The genuine fix is to ensure the web `cfg`
carries (or the web process env exposes) the CLIENT_ID/SECRET the CLI already uses -- i.e. the web
app's credential resolution reaches `~/swing-data/user-config.toml [integrations.schwab]` the same
way the CLI does. If the operator's creds ARE in user-config but the web `cfg` doesn't surface them
to `resolve_credentials_env_or_prompt`'s cfg tier, that wiring gap is the fix (config plumbing, NOT
a checker change, NOT a new `schwabdev.Client.*` site). Confirmed by §3.3 #2.

**Class B fix (if the diagnostic shows the write failed):** the install-anchored STARTING write
(below) does a `read_liveness_sidecar` readback and logs at WARNING (not the silent `debug` swallow)
if the readback is None, surfacing the path/permission cause. The fix is then to correct the path /
permissions (e.g. `_user_home()` resolution under the web process); still NO schema, NO new client site.

**Hardening (independent of the exact cause; low-cost, additive):**
- **Anchor the STARTING write at install.** Although the current seed already writes STARTING before
  `original()`, make the install path write an initial STARTING tick **immediately after constructing
  `CheckerLiveness`, before the seed `update_tokens()` network round-trip** (reuse
  `record_tick("seed")` or a direct `write_liveness_sidecar`), then **readback-verify it once** and log
  WARNING on failure (Class B detection). Rationale: a slow/hanging seed network call must never delay
  the STARTING sidecar; the badge should flip to STARTING the instant the checker is wired, and a
  write failure must not stay invisible. This is OQ-1's recommended "former."
- **Do NOT regress the A-7 badge contract** (L7): a missing sidecar still maps to UNKNOWN with the
  "client unavailable" reason; this fix just makes the sidecar appear when the client constructs.
- **NO new `schwabdev.Client.*` site (L3):** construction stays via the existing
  `construct_authenticated_client` in `auth.py`; the fix touches credential plumbing + the install
  ordering only.

**Out of scope / escalation (brief §7):** if §3.3 reveals the cause is a `schwabdev.Client()`
construction failure that needs a NEW client path, or that the only fix needs a persisted health
table, STOP + escalate (L2/L3). Do NOT design a large rework.

### §3.5 The UNSEEDED real-token gate (CRITICAL deliverable; the SB5.5 miss, corrected)

**Operator gate (BINDING, S4):** the operator starts `swing web` with their HEALTHY production tokens
+ `marketdata_ladder_enabled=True`, **with NO hand-seeded sidecar** (delete any existing
`~/swing-data/schwab-checker-liveness.production.json` first). Assert, in a real browser:
1. within a few seconds of startup, the sidecar file APPEARS at the path logged in §3.3, and
2. the topbar badge shows **STARTING** -> (within ~30-60s, after the first daemon tick) **ALIVE**,
   NOT `Schwab?` UNKNOWN.

**Automated production-path test (#15, NOT a hand-seeded sidecar):** monkeypatch
`_construct_web_schwab_client` to return a FAKE client whose `tokens.update_tokens` is a real callable
and whose `tokens.access_token` is a non-empty string (so the construction gate passes), then drive
the REAL `_install_web_marketdata_caches` / `create_app` path with a monkeypatched
`checker_liveness_sidecar_path` pointing at a `tmp_path`, and assert a STARTING sidecar FILE was
written by the seed wiring (read it back via `read_liveness_sidecar`; assert
`evaluate_liveness_state(...) == STARTING`). This exercises the install+wrap+seed derivation path
WITHOUT writing the sidecar JSON by hand. A second test simulates a daemon-origin tick (call the
wrapped `update_tokens` from a non-startup thread) and asserts the sidecar advances to ALIVE.

**Construction-path test (Codex R1 Major #2 -- covers the credential-plumbing fix, NOT just
install+wrap+seed):** add a separate production-gated test of `_construct_web_schwab_client` itself
with `_is_ladder_active` True (`environment='production'` + `marketdata_ladder_enabled=True`) and a
monkeypatched `construct_authenticated_client` (so no real network/`schwabdev.Client`), parameterized
over the credential sources: (i) creds in env vars -> returns a client; (ii) creds in the cfg tier
(the post-fix path -- the web `cfg` surfaces `~/swing-data/user-config.toml [integrations.schwab]`) ->
returns a client; (iii) creds absent at all tiers -> returns None + logs the redacted "credentials
incomplete" reason; (iv) partial env-tier -> `SchwabConfigMissingError` caught -> None + redacted log.
This asserts the fix actually makes construction succeed under the operator's credential layout and
that each None-path logs its distinct redacted reason (§3.3). Monkeypatch BOTH `USERPROFILE` AND
`HOME` if the test touches user-config resolution (the `write_user_overrides` gotcha family).

---

## §4 F-2 -- market-weather trend-template / compute-vs-display (the deep item)

### §4.1 The orchestrator-verified mechanics

Two LIVE market-weather sites derive the trend STATE the same way:
- pipeline `_step_charts` (`runner.py:2890-2931`): `weather_state = current_stage(_ws_conn,
  benchmark_ticker, run_asof_date)`, fed to `render_market_weather_svg(bars=..., trend_template_state=...)`.
- web refresh (`routes/dashboard.py:128-146`): `weather_state = current_stage(conn, benchmark,
  last_completed_session(...))`, same render call.

`current_stage` (`patterns/foundation.py:745-790`) is a **read-only wrapper over PERSISTED
evaluation**: it SELECTs the most recent `candidates` row for `(ticker, action_session_date <= asof)`,
counts its `candidate_criteria` rows with `layer='trend_template' AND result='pass'`, and returns
`stage_2` iff the count == `_TREND_TEMPLATE_REQUIRED_PASS_COUNT` (8), else `undefined`. **If there is
no candidate row, it returns `undefined` (`:775-776`).**

The benchmark fetch + chart window:
- `MIN_CALENDAR_DAYS_FOR_MA200 = 300` (`web/ohlcv_cache.py:43`) calendar days ~= ~207 trading bars.
  Used by the chart fetch at `runner.py:2701/2772` and `dashboard.py:96`. This feeds the CHART
  (`render_market_weather_svg`, `ma_windows=(50,200)`), NOT the state.
- `trend_template.evaluate` (`evaluation/criteria/trend_template.py`) returns all-NA when
  `len(closes) < 200` (`:24`), AND TT3 ("200 rising") is NA unless
  `len(sma200.dropna()) >= rising_ma_period_days + 1` (`:60`), i.e. `len(closes) >= 200 +
  rising_ma_period_days`. With `rising_ma_period_days = 21` (`swing.config.toml:46`), the template
  needs **>= 221 bars** for all 8 checks to compute.

### §4.2 The decisive finding (deeper than the brief)

In `_step_evaluate` (`runner.py:1030+`), the evaluated ticker set is the **finviz CSV tickers +
open-trade tickers** (`:1102`, `:1043-1066`). The benchmark (`cfg.rs.benchmark_ticker = "SPY"`) is
fetched ONLY for RS (`:1091`, `lookback_days=365`) and is **never added to the evaluated set.** In the
observed/default path, therefore, SPY has no `candidates` row and `current_stage(conn, 'SPY', ...)`
returns `undefined` (`:775-776`) -- independent of bar count.

**Correction (Codex R1 Major #3):** this is NOT structurally undefined for ALL possible inputs. SPY is
NOT in the ETF blocklist (`swing.config.toml`: `etf_exclusion.manual_block = ["UCO"]`), so IF SPY ever
appeared in the finviz CSV (and was not held), it WOULD be evaluated and persisted with trend criteria.
The claim is the narrower, accurate one: **SPY is not added to the evaluated set; in the operator's
observed/default path it is only fetched for RS, so `current_stage('SPY')` is `undefined` there.** The
§4.4 diagnostic pins this empirically against the operator's DB.

Note the finviz tickers that ARE evaluated use `lookback_days=400` (`:1104`) ~= ~275 bars -- already
ample for the 221-bar TT3 requirement. So the `<200`/`MIN_CALENDAR_DAYS_FOR_MA200=300` bar-count
concern lives only on the CHART-fetch path (the 200-MA line), NOT on the evaluation path. **The
"trend: undefined" symptom is therefore a state-derivation (structural) bug, not a fetch-window bug.**
The SB3 T-3.4 comment ("derive the REAL trend state via current_stage") confirms `current_stage` was
wired in at SB3 -- and for a non-candidate benchmark it is structurally `undefined`.

This finding is fully consistent with the operator's LOCKED ruling: "fetch ~250+ bars **for the
classification**, decouple compute-window from display-window, the 200-MA's value is the regime
STATE." That ruling describes computing the classification from fetched bars -- which is exactly the
fix below.

### §4.3 The fix -- compute the regime state LIVE from fetched bars (decoupled compute/display)

Replace the `current_stage(conn, benchmark, ...)` persisted-read at BOTH live market-weather sites
(`runner.py:2890-2931` + `dashboard.py:128-146`) with a **live trend classification computed from
the fetched benchmark bars**:

- **Compute window (>= 250 bars).** Fetch enough benchmark history for the structural Trend-Template
  checks INCLUDING TT3: `>= 200 + rising_ma_period_days + margin`. With `rising_ma_period_days = 21`,
  that is `>= 221`; add margin -> **~250-260 trading bars ~= ~370-390 calendar days.** Introduce a
  dedicated compute-window constant (e.g. `MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE ~= 390`) rather than
  overloading `MIN_CALENDAR_DAYS_FOR_MA200` (whose `=300` value is correct for the 200-MA chart line).
- **Extract a SHARED structural classifier -- TWO-TIER, per Codex R1 Major #4 + R2 Major #1
  (reuse, not re-implement, WITHOUT changing the existing 8-criterion path).** `trend_template.evaluate()`
  computes TT1-TT8 as one unit and TT8 depends on RS/batch context (not available at the render site),
  so the live site MUST NOT call `evaluate()` and MUST NOT hand-duplicate the TT1-TT5 comparisons. An
  aggregate `stage_2|undefined` helper is too LOSSY for `evaluate()` to reuse (it must preserve each
  criterion's `Result` row -- name/value/message/pass-fail-NA). So extract a **lower-level per-check
  helper** in `swing/evaluation/criteria/trend_template.py`:
  - `structural_checks(closes, *, rising_period) -> tuple[StructuralCheck, ...]` -- computes the TT1-TT5
    structural checks from `closes` using the existing `sma` from `criteria/_base.py`, each carrying
    its status (pass/fail/NA) + the formatted value/message strings the current `evaluate()` emits.
  - **Refactor `evaluate()` to build its TT1-TT5 `Result` rows by converting these check objects**
    (so the existing per-criterion output -- names, values, messages, NA behavior -- is byte-identical;
    a regression test asserts this). TT6-TT8 stay in `evaluate()` unchanged (they need batch/RS context).
  - A thin `structural_stage(closes, *, rising_period) -> "stage_2" | "undefined"` wrapper maps the SAME
    `structural_checks(...)` output to the regime label (all TT1-TT5 pass -> `stage_2`, else `undefined`).
  Both the pipeline `_step_charts` site and the web refresh site call `structural_stage`. ONE source of
  truth for the TT1-TT5 math; ZERO behavior change to the 8-criterion pipeline path.
  **OQ-3a:** the regime check set (structural TT1-TT5 vs full TT1-TT8). Recommend TT1-TT5: TT6/TT7 (52w
  high/low) and TT8 (RS rank vs a universe) are stock-selection criteria, not meaningful for the index
  benchmark vs itself.
- **Display window -- explicit slicing contract (Codex R1 Minor #5).** `OhlcvCache.get_or_fetch(
  window_days=...)` already returns a calendar-sliced window (NOT a raw full archive), so "return FULL
  archive; consumers slice" applies at the CALL site, not inside the helper: the live sites fetch with
  `window_days = MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE` (~390) -> the returned frame IS the compute
  window; pass that full frame to the structural classifier, and pass a **separately sliced recent
  display frame** (e.g. `bars.tail(N_display)` with `N_display ~= the prior display size, ~90-120
  bars`) to `render_market_weather_svg`. Specify `N_display` at writing-plans (recommend keep the prior
  effective display window so the chart's legibility is unchanged). Do NOT chase a visible 200-MA line
  (operator ruling). **OQ-4:** keep `ma_windows=(50,200)` on the (now shorter) display frame -- a short
  200 tail is harmless -- vs drop the 200 line. Recommend keep `(50,200)`; removing it is a separate
  cosmetic call.
- **Fail-soft preserved:** both sites keep their `try/except -> "undefined"` fallback so a fetch /
  compute error never crashes the refresh or aborts the charts step (L5/L6).

### §4.4 The diagnostic + the alternative (escalation guard)

The plan MUST confirm (against the operator's DB or a representative pipeline run) that SPY has NO
passing `candidate_criteria` -- pinning §4.2 empirically. **If** the operator instead prefers to make
SPY a first-class evaluated candidate (un-exclude + evaluate + persist trend criteria), that is a
larger, write-touching pipeline change (NOT read-mostly) and an **escalation point** -- the live-
compute fix above is the read-mostly, localized choice that honors L5 and the operator's ruling, and
is robust regardless of whether SPY is ever a candidate.

### §4.5 Regression (production-path, #15)

A test computes the regime state from a real >=250-bar benchmark fetch (or a >=250-bar synthetic
uptrend fixture exercising the real classify path) and asserts the state is DEFINED (e.g. `stage_2`),
NOT `undefined`; and a `<221`-bar fixture asserts the documented fallback. The test exercises the
real fetch/compute wiring, not a stubbed `current_stage`.

---

## §5 F-3 -- segmented rolling-line polylines (short)

`_format_polyline_points` (`view_models/metrics/process_grade_trend.py:262-301`) skips `None` points
and joins ALL defined points into ONE `points` string, so the single `<polyline>` (template
`metrics/process_grade_trend.html.j2:54-62`) bridges `None` gaps with straight diagonals (now visible
since the close-out A-6 dark-mode CSS made the lines render).

**Fix:** emit **one polyline per contiguous non-`None` run** so gaps render as gaps. SVG `<polyline>`
cannot contain a break, so multiple `<polyline>` elements are required (OQ-5; `<path>` with M/L breaks
is the alternative -- recommend multiple `<polyline>`s to preserve the existing CSS class hooks
`process-grade-rolling-line metric-{name}` per segment).

- **VM shape:** change `RollingSeriesDisplay.svg_polyline_points: str` -> a tuple of segment
  point-strings (e.g. `svg_polyline_segments: tuple[str, ...]`), each a `"x1,y1 x2,y2 ..."` run.
  Build by walking `line_points` and starting a new segment whenever a `None` is encountered; reuse
  `_polyline_x`/`_polyline_y` unchanged (L4). A single isolated defined point yields a 1-point segment
  -- decide whether to drop 1-point segments (invisible as a polyline) or keep them (OQ-5a; recommend
  drop -- a lone point draws nothing and only adds an empty element).
- **`is_drawable` segment semantics (Codex R1 Minor #6).** `is_drawable` currently keys off
  `bool(svg_polyline_points)`. After the segment refactor (and after dropping 1-point segments), define
  it as `(drawability == "<rolling line drawable>") and bool(svg_polyline_segments)` -- i.e. drawable
  iff at least one >=2-point segment survives -- so the template's `{% if series.is_drawable %}` guard
  never wraps an empty segment list (no empty/invisible `<polyline>` elements emitted).
- **Template:** `{% for seg in series.svg_polyline_segments %}<polyline points="{{ seg }}" .../>{% endfor %}`
  inside the existing `{% if series.is_drawable %}`.
- **Test:** a render-string test with a `None` in the middle asserts >=2 `<polyline>` elements
  (multiple segments), and a fully-contiguous series asserts exactly 1.
- **No regression** to the A-6 dark-mode visibility CSS (the class names per segment are preserved).

---

## §6 F-4 -- thumbnail axes-spine borders (short)

`render_watchlist_thumbnail_svg` (`web/charts.py:514-552`) clears ticks
(`set_xticks([])`/`set_yticks([])`) but leaves the matplotlib default axes spines (a black box around
each sub-panel), visible on the hyp-rec dashboard thumbnails (and, since this is the SHARED renderer,
on the watchlist thumbnails too).

**Fix:** hide the spines on BOTH sub-axes:
`for spine in ax_price.spines.values(): spine.set_visible(False)` and the same for `ax_vol`.
- **Test:** a render test asserts the produced SVG has no visible spine paths (or asserts the spines
  are set invisible) for the thumbnail; assert the watchlist thumbnail surface is unchanged in shape.
- **Gate:** the operator re-checks BOTH the hyp-rec thumbnails AND the watchlist thumbnails in the
  browser (shared renderer).

---

## §7 Module touch list

- **F-1:** `swing/web/app.py` (`_install_web_marketdata_caches`: install-anchored STARTING write +
  one-shot diagnostic log; credential-plumbing fix per §3.4 -- likely in `_construct_web_schwab_client`
  or the cfg the web app builds); possibly `swing/integrations/schwab/checker_resilience.py` (only if
  the install-anchored write needs a tiny helper -- prefer reusing `record_tick`/`write_liveness_sidecar`).
  NO change to `auth.py` construction (L3). `tests/...` production-path test (§3.5).
- **F-2:** `swing/web/ohlcv_cache.py` (new compute-window constant
  `MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE`); `swing/evaluation/criteria/trend_template.py` (extract the
  per-check `structural_checks(closes, *, rising_period)` helper + a thin `structural_stage(...)`
  wrapper for TT1-TT5; refactor `evaluate()` to build its TT1-TT5 `Result` rows from `structural_checks`
  -- ONE source of truth, ZERO behavior change to the 8-criterion path; Major #4 + R2 #1);
  `swing/pipeline/runner.py` (`_step_charts` market-weather site) + `swing/web/routes/dashboard.py`
  (refresh site): replace `current_stage` with `structural_stage`, fetch the compute window + slice the
  display frame. `tests/...` regression (incl. a test that `evaluate()` produces byte-identical TT1-TT5
  Result rows after the refactor).
- **F-3:** `swing/web/view_models/metrics/process_grade_trend.py` (`_format_polyline_points` ->
  segments + the `RollingSeriesDisplay` field) + `swing/web/templates/metrics/process_grade_trend.html.j2`
  (segment loop). `tests/...` render test.
- **F-4:** `swing/web/charts.py` (`render_watchlist_thumbnail_svg`). `tests/...` render test.

---

## §8 Schema impact

**NO change. v23 held.** `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`) unchanged. F-1's
liveness stays the existing ephemeral sidecar file (NOT a persisted row/table). F-2 is SELECT/compute
+ render only. F-3/F-4 are render-geometry only. If any item appears to need a persisted row/column
-> STOP + escalate (L2; no v24).

---

## §9 L2-LOCK analysis (F-1)

F-1 touches credential plumbing + the checker install ordering + the badge contract preservation.
**ZERO new `schwabdev.Client.*` call sites:** the `git grep -n "schwabdev.Client." -- swing/` count at
the new HEAD must equal the baseline `bf7e071` count. schwabdev `Client()` construction stays
exclusively in `swing/integrations/schwab/auth.py:construct_authenticated_client` (unchanged). The
`"Schwabdev"` `setLogRecordFactory` redaction is preserved (no logging-config change). The L2 source-
grep test stays green.

---

## §10 Decomposition (slices)

Recommend ONE executing-plans bundle, **4 slices**, F-1 first (deepest, has the diagnosis step):
- **Slice 1 (F-1):** diagnosis log + install-anchored STARTING write + credential-plumbing fix +
  production-path test. (OQ-6: split F-1 into its own bundle -- recommend NO; keep one bundle.)
- **Slice 2 (F-2):** compute-window constant + live structural classifier + replace `current_stage`
  at both LIVE sites + regression.
- **Slice 3 (F-3):** segmented polylines (VM + template + test).
- **Slice 4 (F-4):** hide thumbnail spines (renderer + test).

Codex chain count at writing-plans / executing-plans: **single** (OQ-7).

---

## §11 Test + gate strategy

- **S1** fast suite (`pytest -m "not slow"`) + `ruff check swing/` green on the merged HEAD (re-run on
  MERGED main; `feedback_no_false_green_claim`).
- **S2** schema v23 unchanged + DB backup gate (no migration).
- **S3 (F-1)** `tests/integration/test_l2_lock_source_grep.py` green (zero new `schwabdev.Client.` sites).
- **S4 (F-1, BINDING, UNSEEDED real-token)** operator starts `swing web` with healthy production tokens
  + ladder enabled + NO hand-seeded sidecar -> a sidecar FILE appears + the badge shows STARTING ->
  ALIVE (§3.5). This is the SB5.5 gate's exact miss, corrected.
- **S5 (F-2)** the market-weather trend is DEFINED (not `undefined`) in a real browser refresh +
  pipeline-rendered chart.
- **S6 (F-3/F-4 browser)** the process-grade-trend rolling lines render gaps-as-gaps (no diagonal
  bridges); the hyp-rec AND watchlist thumbnails have no spine borders.
- **S7** commit trailers `git log -1 --format='%(trailers)'` == `[]`; ZERO `Co-Authored-By`.

After teardown, kill any detached `swing web` server (`feedback_taskstop_does_not_kill_detached_server`):
find the PID via `Get-NetTCPConnection -LocalPort`, `Stop-Process -Force`, verify the port is free.

---

## §12 V1 simplifications + V2

- **F-1 V1:** the badge has two states (ALIVE/STARTING/DEGRADED/UNKNOWN); we make the sidecar appear +
  surface the construction-None cause. **V2:** the schwabdev v3 upgrade (Phase 15 `#9`) deletes the
  checker + this module + the P14.N7 guard entirely (F-1's diagnosis INFORMS that upgrade).
- **F-2 V1:** two-value regime label (`stage_2`/`undefined`) computed from structural TT1-TT5. **V2:**
  full Weinstein 4-stage labeling (Stage 1/3/4 differentiation) per `current_stage`'s own V2 note.
- **F-3 V1:** multiple `<polyline>` elements per series. **V2:** `<path>` with M/L breaks if a single
  element per series is ever needed for animation/styling.
- **F-4 V1:** hide spines on the thumbnail. (No V2.)

---

## §13 Operator decision items (OQs; Codex surfaces; operator triages at writing-plans)

1. **OQ-1 (F-1 seed):** force an initial STARTING sidecar at install (recommend -- the "former") vs
   force a token refresh at startup (heavier). The current seed already writes STARTING before
   `original()`; the recommended hardening anchors it even earlier (before the network call).
2. **OQ-2 (F-1 daemon):** RESOLVED in §3.1 -- the daemon reaches the wrapper via attribute lookup and
   heartbeats within ~30s once the client constructs. (Confirm at the S4 gate.)
3. **OQ-3 (F-2 window split):** compute-window ~250-260 trading bars (~390 calendar days) via a new
   constant; display window unchanged. **OQ-3a:** structural TT1-TT5 (recommend) vs full TT1-TT8 for
   the regime classification.
4. **OQ-4 (F-2 200-MA line):** keep `ma_windows=(50,200)` (recommend) vs drop the 200 line for
   legibility (operator leaned omit-as-goal, not omit-the-line).
5. **OQ-5 (F-3 shape):** multiple `<polyline>` elements (recommend) vs `<path>` M/L. **OQ-5a:** drop
   1-point segments (recommend) vs keep.
6. **OQ-6 (decomposition):** one bundle / 4 slices (recommend) vs split F-1.
7. **OQ-7 (Codex chain count downstream):** single (recommend).
8. **OQ-8 (F-1 root cause):** confirm via the §3.3 diagnostic whether the cause is Class A (which
   construction-None sub-path) or Class B (silent sidecar-write failure) before locking the fix shape
   (credential-plumbing for A; path/permission for B).
9. **OQ-9 (F-2 structural finding):** confirm SPY has no passing `candidate_criteria` in the operator's
   DB (§4.4); if the operator prefers making SPY an evaluated candidate instead, escalate (write-touching).

---

## §14 Cumulative discipline applied

- "Return FULL archive; consumers slice" -- applied at the CALL site (F-2 fetches the wider compute
  window via `get_or_fetch(window_days=...)`, which itself returns a sliced calendar window, then slices
  a narrower display frame; the classifier consumes the full fetched frame). Codex R1 Minor #5.
- `feedback_seeded_gate_masks_default_state` (F-1's UNSEEDED real-token gate; the lesson F-1 proves
  AGAIN).
- #15 production-path tests (F-1 + F-2 exercise the real derivation path, NOT stubs/hand-seeds).
- HTMX gotchas reviewed (no new HTMX endpoint; F-3 is a same-fragment render change).
- Matplotlib mathtext (F-4 adds no text; spines only).
- `feedback_no_false_green_claim` / `feedback_taskstop_does_not_kill_detached_server` (S1/S7 teardown).
- `feedback_commit_message_trailer_parse_hazard` (final `-m` paragraph plain prose; verify
  `%(trailers)` `[]`).
- ASCII-only user-facing strings (Windows cp1252).

---

## §15 Close-out position note

This FOLLOW-ON bundle is the FIRST item of the Phase 14 close-out tail: **follow-on bundle (this) ->
B-7 (operator failure-mode classification, final touch) -> Phase 14 close-out review (Sec 9.1 Q6) ->
"Phase 14 CLOSED" at v23.** F-1's diagnosis feeds the Phase 15 schwabdev v3 upgrade (`#9`), which will
obviate P14.N7's checker guard. NO scope creep into B-7 / the close-out review / Phase 15.

---

*End of design spec. Four gate-found corrections: F-1 (P14.N7 web checker -- the seed is NOT the gate;
the absent sidecar is Class A construction-None (likely credential plumbing) OR Class B silent
sidecar-write failure, pinned by a one-shot diagnostic; anchor + readback-verify the STARTING write +
design an UNSEEDED real-token gate), F-2 (market-weather "undefined" -- the cause is `current_stage`
reading absent persisted criteria for a benchmark not in the evaluated set; compute the regime state
live via a SHARED TT1-TT5 helper from a >=250-bar fetch, decoupling compute from display), F-3
(segmented polylines), F-4 (hide thumbnail spines). NO schema (v23 held); L2-LOCK green; reuse not
re-implement; read-mostly.*
