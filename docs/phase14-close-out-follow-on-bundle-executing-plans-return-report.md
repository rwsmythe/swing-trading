# Phase 14 Close-Out FOLLOW-ON Bundle — Executing-Plans Return Report

**Audience:** Orchestrator (QA + merge). **Phase:** 14 close-out tail, FOLLOW-ON bundle, EXECUTING-PLANS.
**Worktree:** `.worktrees/phase14-close-out-follow-on-bundle-executing-plans/` (branch
`phase14-close-out-follow-on-bundle-executing-plans`, from main HEAD `f509a9d`). **LEFT INTACT for QA + the operator S1-S7 gate.**

---

## 1. Final HEAD + commit log (per-slice attribution)

Final HEAD: `bec3843`. Baseline: `f509a9d`. NO rebase; 14 serial commits.

```
bec3843 style(web): F-2 drop redundant quotes on slice_recent_calendar_days annotations (ruff UP037)
08ad404 fix(web): F-1 R1 tie the checker sidecar readback to this install's installed_ts so a stale sidecar cannot mask a failed write
3b70613 fix(web): F-4 hide axes spines on the shared thumbnail renderer
a5ac759 feat(web): F-3 render one polyline per segment; migrate VM + route tests
f7f4472 feat(web): F-3 segment rolling-line polylines at None gaps (one per contiguous run)
129c10a test(web): F-2 migrate dashboard refresh get_or_fetch window assertion to the compute window
4ff39df test(web): F-2 production-path market-weather live-state regression
87c5657 fix(web): F-2 compute market-weather trend live via structural_stage on refresh
b3f8670 fix(pipeline): F-2 compute market-weather trend live via structural_stage
2f35730 feat(web): F-2 add trend-template compute-window constant + display-slice helper
e8b6f81 refactor(evaluation): F-2 extract structural_checks/structural_stage; evaluate() byte-identical
1779987 test(web): F-1 create_app startup tolerates the overridden web cfg
eed3449 fix(web): F-1 apply user-config overrides at the web entry so Schwab creds reach the checker
41c8cf0 fix(web): F-1 anchor + readback-verify the checker STARTING sidecar with startup diagnostic
```

(F-1: commits 41c8cf0, eed3449, 1779987 + R1-fix 08ad404. F-2: e8b6f81, 2f35730, b3f8670, 87c5657, 4ff39df, 129c10a + ruff bec3843. F-3: f7f4472, a5ac759. F-4: 3b70613.)

All commits trailer-clean (`git log -1 --format='%(trailers)'` == `[]` verified after each; full-range audit clean — ZERO `Co-Authored-By`).

---

## 2. The single Codex chain (run to CONVERGENCE)

Transport: copowers v2.0.3 WSL fallback (`command -v codex` -> `/home/rwsmythe/.local/node22/bin/codex`,
verified before the chain; MCP codex tools DEAD in the VS Code extension, not attempted).
Each round's PROMPT + the FULL RESPONSE (incl. the literal final `### Verdict` line) are PERSISTED on
disk in `.copowers-findings.md` (gitignored). The diff reviewed is `.codex-diff.txt` (regenerated per round).

- **R1** (HEAD `3b70613`): `0 CRITICAL, 1 MAJOR, 1 MINOR`. Both ACCEPTED (genuine):
  - MAJOR (swing/web/app.py): the install readback `read_liveness_sidecar(...) is not None` could be
    falsely satisfied by a STALE prior-run sidecar, masking Class B (silent write-fail) exactly where the
    fix must expose it. FIXED: tie the readback to THIS install's `installed_ts`.
  - MINOR (test): the install-path test was not discriminating for the readback fix. FIXED: added a
    stale-sidecar + forced-write-failure test that fails pre-fix and passes post-fix.
- **R2** (HEAD `08ad404`): **CONVERGED (NO_NEW_CRITICAL_MAJOR)**. Codex independently re-verified from disk:
  schema v23, no `0024_` migration, `schwabdev.Client.` count == 3 (comment/docstring only), zero
  `svg_polyline_points` refs, both live market-weather sites use `structural_stage`.

**Convergence:** single chain, 2 rounds, CONVERGED at R2 (literal `### Verdict: CONVERGED
(NO_NEW_CRITICAL_MAJOR)` persisted in `.copowers-findings.md` along with the R1 prompt+response and the full
R1/R2 prompts in `.codex-r1-prompt.txt` / `.codex-r2-prompt.txt`). Codex Majors ACCEPTED: 1 (R1; ZERO
rejected). ZERO findings needed a schema change or a new `schwabdev.Client.*` site (no escalation).

---

## 3. Per-slice completion

- **F-1 (P14.N7 web checker liveness):** `web_cmd` now applies `apply_overrides(ctx.obj["config"])` (the
  Class-A credential-plumbing fix — Schwab CLIENT_ID/SECRET reach the cfg tier). `_construct_web_schwab_client`
  logs the previously-silent `(None,None)` creds-absent path. `_install_web_marketdata_caches` reads
  `ladder_active`, anchors a STARTING sidecar via `record_tick("seed")`, **readback-verifies it against this
  install's `installed_ts`** (R1 MAJOR fix: a stale sidecar cannot mask a failed write), WARNINGs on failure,
  and emits a one-shot INFO install summary (`ladder_active` / `client_constructed` / `starting_write_readback`).
  ZERO new schwabdev client-construction sites (construction stays in `auth.py`). Tests: install/seed path
  (fake-client monkeypatch on the REAL `_install_web_marketdata_caches`, NOT a hand-seeded sidecar) +
  daemon->ALIVE + stale-sidecar-discriminating + 4 construction-path scenarios + override-propagation +
  create_app startup divergence-hook tolerance.
- **F-2 (market-weather trend live-compute):** `trend_template.py` adds `StructuralCheck` + `structural_checks`
  (TT1-TT5) + `structural_stage`; `evaluate()` refactored to build TT1-TT5 from `structural_checks` —
  **byte-identical** (4-fixture full-tuple repr golden captured from the PRE-refactor `evaluate()`; the entire
  `tests/evaluation/` suite green). `ohlcv_cache.py` adds `MIN_CALENDAR_DAYS_FOR_TREND_TEMPLATE=390` +
  `slice_recent_calendar_days` (anchored on the frame's own last bar — cache-lag-safe, NOT now()). The pipeline
  `_step_charts` market_weather site + the web refresh handler now fetch the wide compute window, compute
  `structural_stage` LIVE, and slice the display frame to MA200. `structural_stage` is imported at module-top in
  both so the call-site tests spy it. Migrated existing tests: `test_weather_trend_state.py`,
  `test_market_weather_fetch_window.py`, `test_step_charts_fetch_window.py`,
  `test_step_charts_ohlcv_cache_wiring.py`, `test_dashboard_chart_integration.py`. New live-state regression
  with REAL-compute call-site tests for BOTH sites (web refresh 204 + spy `render_market_weather_svg`; pipeline
  spy `runner.structural_stage`).
- **F-3 (segmented polylines):** `_format_polyline_points` -> `_format_polyline_segments`
  (`tuple[str, ...]`, one per contiguous non-None run, drop 1-point); `RollingSeriesDisplay.svg_polyline_points`
  -> `svg_polyline_segments`; template loops over segments (per-segment CSS class hooks preserved). The 4
  existing VM test sites migrated + the route test strengthened; ZERO `svg_polyline_points` refs remain.
- **F-4 (thumbnail spines):** `render_watchlist_thumbnail_svg` hides spines on both sub-axes; no
  watchlist/thumbnail regression (143 thumbnail/watchlist tests green).

---

## 4. Test surface

Baseline (branch creation, f509a9d): **7005 passed, 3 skipped**.
Final branch full fast suite on the post-R1-fix + ruff HEAD `bec3843` (`pytest -m "not slow"`):
**7038 passed, 3 skipped, 0 failed** (clean — net +33 tests). An earlier branch run surfaced the known
`test_ohlcv_reader_re_export_identity` xdist re-export-identity flake (in tests/research, unrelated to
F-1–F-4; PASSES serially `-n0`; the brief explicitly anticipated it); it did NOT trip on the final run.
`ruff check swing/` clean on the COMMITTED tree (verified via stash — the UP037 fix is committed at `bec3843`,
not left in the working tree). **Per `feedback_no_false_green_claim`, the orchestrator MUST re-run the suite on
the MERGED head and READ it before claiming green on main.**

---

## 5. LOCK + OQ verification (verbatim)

- **L1** scope = F-1 + F-2 + F-3 + F-4 ONLY (no B-7, no close-out review, no Phase 15). HELD.
- **L2** NO swing schema change: `EXPECTED_SCHEMA_VERSION = 23` unchanged; no `0024_*.sql`. HELD (v23).
- **L3 (L2-LOCK)** F-1 ZERO new `schwabdev.Client.` call sites: `git grep "schwabdev.Client\." -- swing/` ==
  **3** (auth.py:1666, client.py:13, trader.py:364 — all comments/docstrings). `test_l2_lock_source_grep.py`
  green. `"Schwabdev"` `setLogRecordFactory` redaction untouched. HELD.
- **L4** REUSE not re-implement: F-1 reuses `CheckerLiveness`/`record_tick`/`read_liveness_sidecar`/
  `install_resilient_checker` (checker_resilience.py UNCHANGED); F-2's two-tier helper is the SAME SMA logic
  (byte-identical evaluate); F-3 reuses `_polyline_x`/`_polyline_y`; F-4 reuses the existing renderer. HELD.
- **L5** read-mostly: ZERO swing-domain DB writes (the sidecar is an ephemeral file; the chart paths are
  render-direct; structural_stage/the live-compute are SELECT/compute-only). HELD.
- **L6/#15** production-path tests: F-1 exercises the REAL `_install_web_marketdata_caches` seed path with a
  fake-client monkeypatch (NOT a hand-seeded sidecar); F-2 has mandatory route + pipeline call-site tests. HELD.
- **L7** ASCII-only user-facing strings; the close-out A-7 badge contract preserved (badge renders UNKNOWN with
  no sidecar; F-1 makes the sidecar appear so it shows STARTING/ALIVE). HELD.
- **OQ recap:** OQ-1 diagnostic-then-fix (both Class A + B shipped) · OQ-2 daemon heartbeats (test) · OQ-3a
  two-tier helper + byte-identical evaluate · OQ-4 ma_windows kept (render call unchanged) · OQ-5 multiple
  `<polyline>` + drop-1-point · OQ-6 one bundle/4 slices · OQ-7 single chain · OQ-8 Class A/B pinned by the
  §3.3 diagnostic (operator confirms at S4) · OQ-9 (SPY no persisted criteria) — the live-compute fix is
  correct regardless; structurally confirmed by the design (benchmark not in the evaluated set).

---

## 6. The §3.3 diagnostic outcome

The §3.3 startup INFO diagnostic SHIPPED (`P14.N7 checker install summary: ladder_active=... client_constructed=...
sidecar_path=... starting_write_readback=...`). The plan's orchestrator-verified LEADING hypothesis is **Class A,
sub-path #3** (`web_cmd` never called `apply_overrides` -> the web cfg lacked the user-config Schwab
CLIENT_ID/SECRET -> `_construct_web_schwab_client` returned None -> no checker -> no sidecar -> badge UNKNOWN).
The Class-A fix (`apply_overrides` at `web_cmd`) + the Class-B hardening (install-anchored readback-verify, now
install-identity-guarded) BOTH shipped, so whichever class the operator's S4 gate pins, the fix is in place.
**The actual class fired is confirmed at the operator's UNSEEDED real-token S4 gate** (the diagnostic logs ONE
startup line; do NOT hand-seed a sidecar — `feedback_seeded_gate_masks_default_state`).

---

## 7. Gate readiness (S1-S7)

- **S1** fast suite + ruff green (7036 passed; the lone failure is the known xdist re-export flake, green serially).
- **S2** schema v23 / no migration / no new domain writes. CONFIRMED.
- **S3** L2 source-grep green; `schwabdev.Client.` count == 3. CONFIRMED.
- **S4 (F-1, BINDING, UNSEEDED real-token):** operator deletes any
  `~/swing-data/schwab-checker-liveness.production.json`, runs `swing web` with HEALTHY production tokens +
  `marketdata_ladder_enabled=True`; reads the §3.3 startup INFO line; asserts in a real browser the sidecar FILE
  appears + the badge shows STARTING -> ALIVE (not UNKNOWN). **Orchestrator-run the BRANCH server**
  (`python -m swing.cli web --port 8081`); kill by PID per `feedback_taskstop_does_not_kill_detached_server`.
- **S5 (F-2, browser):** market-weather trend DEFINED (not "undefined") on a real-browser refresh + pipeline chart.
- **S6 (F-3/F-4, browser):** process-grade-trend lines render gaps-as-gaps; hyp-rec + watchlist thumbnails have
  NO spine borders.
- **S7** trailers `[]`; ZERO `Co-Authored-By`. CONFIRMED.

After merge: re-run the suite on the MERGED head + READ it (`feedback_no_false_green_claim`); reinstall `swing`
(`pip install -e . --no-deps`).

---

## 8. Cumulative gotcha application

#15 production-path (F-1 real install/seed path, F-2 call-site tests); `feedback_seeded_gate_masks_default_state`
(F-1 fake-client monkeypatch, NOT hand-seeded; S4 UNSEEDED); USERPROFILE+HOME monkeypatch (F-1 cred-resolution
tests); TestClient lifespan (refresh-route tests use `with TestClient(app)`); cp1252/ASCII (all new log lines
ASCII); the worktree-cwd corollary (every git/test command prefixed `cd <worktree> &&`; branch re-verified before
each commit); trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` `[]` verified); yfinance
"return the FULL archive; consumers slice" (F-2 compute fetch returns the wide frame; the display slice narrows
it). The L2-grep false-match (my own comment literally containing `schwabdev.Client.*`) was caught + reworded so
the count stayed 3.

---

## 9. Teardown status + handback

Worktree LEFT INTACT for orchestrator QA + the operator S1-S7 gate. Temp artifacts (`.codex-diff.txt`,
`.codex-r1-prompt.txt`, `.codex-r2-prompt.txt`) are untracked scratch; `.copowers-findings.md` is gitignored and
holds the full Codex transcript (prompts + responses incl. the literal `### Verdict` lines). NO `swing web` server
left running by the implementer.

**Handback:** ready for orchestrator QA -> merge (orchestrator performs the merge across all phases) -> the
operator S1-S7 gate (S4 UNSEEDED real-token is BINDING). Suggested CLAUDE.md status-line refresh draft:
"follow-on bundle EXECUTING-PLANS SHIPPED end-to-end at `<merge-sha>` (14 commits across F-1/F-2/F-3/F-4 + 1
ruff style; 7038 fast tests on branch HEAD `bec3843`; genuine single WSL Codex chain CONVERGED [R1 1 maj + 1
min accepted/fixed -> R2 NO_NEW_CRITICAL_MAJOR]; NO schema v23 held; L2 green [F-1 zero new
`schwabdev.Client.` sites, grep=3]; read-mostly; byte-identical `evaluate()` golden; A-7 badge preserved;
operator-witnessed UNSEEDED real-token S4 gate BINDING -> confirms Class A vs B via the §3.3 startup
diagnostic)".
