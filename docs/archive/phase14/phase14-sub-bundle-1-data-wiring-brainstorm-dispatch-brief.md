# Phase 14 Sub-bundle 1 — Data-wiring — Brainstorm Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 14 Sub-bundle 1 brainstorm implementer. No prior conversation context.

**Mission:** Produce a design spec that closes three data-wiring defects surfaced post-Phase-13 T4.SB SHIPPED (operator-witnessed gate 2026-05-23) and operator Turn H feedback 2026-05-27 PM #2:

1. **V2.G3** — VSAT row in `/dashboard` open-positions table lost Sector + Industry values (data-wiring / regression).
2. **V2.G4** — `/dashboard` "Refresh weather chart" button consistently returns "no OHLCV bars available for benchmark 'SPY'; run the pipeline first" even immediately post-pipeline-run (chart refresh broken end-to-end).
3. **P14.N3** — `/daily-management` Capital % column appends "PROVISIONAL" with no UI affordance explaining what the flag means or what would clear it (UI / state-machine surfacing).

The three items cohere around persistence + JOIN + cfg-resolution debugging at the dashboard + daily-management surface. They are pure UX / wiring fixes — no analytical methodology, no schema-heavy migration anticipated (V1; brainstorm will verify per §2.X investigation paths). Phase 14 Sec 9.1 commissioning LOCKs (`docs/phase14-commissioning-brief.md` Sec 9.1) apply.

**Brief:** `docs/phase14-sub-bundle-1-data-wiring-brainstorm-dispatch-brief.md` (this file).

**Commissioning context:** Phase 14 commissioned at main commit `bf7e071`; Sec 9.1 LOCKs committed at `7a558e4`. Phase 14 = 5 sub-bundles SERIAL per Sec 9.1 Q1+Q2 LOCKs (data-wiring → temporal log V1+ → chart-surface uniformity → review+journal UX → metrics overview); this dispatch is sub-bundle #1.

**Expected duration:** ~60-120 min brainstorm + 2-4 Codex rounds. Scope is bounded (three line items; small fix surface). Spec line target: **~400-600 lines**.

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- `copowers:brainstorming` wraps `superpowers:brainstorming` with adversarial Codex MCP review after the spec is written.
- Codex chain count: **SINGLE chain** per Sec 9.1 Q7 LOCK (orchestrator discretion per sub-bundle; data-wiring is pure UX/wiring with no substantive analytical artifact — single chain at end is appropriate per gotcha #36 explicit caveat).
- Output is a spec doc at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-1-data-wiring-design.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/phase14-commissioning-brief.md`** — Phase 14 mission scope + Sec 9.1 LOCKs (operator-paired 7 decisions; LOCKED 2026-05-27 PM #4). Especially:
   - Sec 1 mission summary (Phase 14 is UX + wiring + methodological-infrastructure; NOT a ruleset deployment phase)
   - Sec 2.2 Data-wiring sub-bundle architectural notes
   - Sec 4 Cumulative discipline BINDING (37 gotchas; `Co-Authored-By` streak ~581+; Schema v21 LOCKED)
   - Sec 6 Cross-cutting watch items
   - Sec 9.1 LOCKs (binding for this dispatch)

3. **`docs/phase3e-todo.md`** PM #2 Phase 14 preliminary scope roll-up — 5-field detail blocks for the three items in scope:
   - **V2.G3** at the "Post-T4.SB-SHIPPED operator gate feedback" section
   - **V2.G4** at the same section
   - **P14.N3** at the "NEW Phase 14 operator items" section

4. **`CLAUDE.md`** — especially:
   - Current state paragraph at line 3 (commissioning context)
   - "Invariants" + "Conventions" sections
   - Gotchas BINDING for this dispatch (cited per-item at §2):
     - **PriceCache `_last_close` only sees tickers in today's `candidates` table** — likely directly applicable to V2.G3 (Sector/Industry data may suffer the same ticker-rotation fate)
     - **Session-anchor read/write mismatch (forward-looking `action_session_for_run` vs backward-looking `last_completed_session`)** — possibly applicable to V2.G4 if SPY-bar persistence is session-anchored differently than the refresh handler reads
     - **OHLCV fetch scope = open-trade tickers ONLY** — V2.G4 invariant context
     - **Empty-pool early-return + audit emission discipline** (gotcha #27) — pipeline-step early-return discipline; V2.G4 may inherit
     - **Schema-CHECK + Python-constant + dataclass-validator paired discipline** (gotcha #11) — applies IF P14.N3 investigation reveals a CHECK enum widening is needed
     - **OHLCV archive bar-content TEMPORAL mutation** (gotcha #26) — V2.G4 V2-style read-vs-write semantics may surface this
     - **Form-render anchor lifecycle audit** (gotcha #15 / Expansion #9) — applies if any P14.N3 fix introduces an operator-visible state transition
     - **Server-stamping for hidden audit fields** (Phase 8 R2.M2+R3.M2+R4.M2 family) — applies to any new form input on the daily-management surface

5. **`docs/orchestrator-context.md`** "Currently in-flight work" + "Lessons captured" — ~135+ cumulative forward-binding lessons inherited.

6. **Production code surfaces relevant to each item** (consult during brainstorm):
   - V2.G3: `swing/web/view_models/dashboard.py` open-positions row builder; `swing/web/templates/partials/open_positions_row.html.j2`; `swing/pipeline/runner.py:_step_evaluate` for Sector/Industry persistence path; `swing/data/repos/trades.py` or `swing/data/models.py` for trades schema (verify Sector/Industry are NOT columns on trades AS OF v21); `swing/data/repos/candidates.py` for candidate-side persistence
   - V2.G4: `swing/web/routes/dashboard.py` for `/dashboard/weather-chart/refresh` handler; `swing/web/chart_jit.py:get_or_render_surface(surface='market_weather')`; `swing/web/charts.py:render_market_weather_svg`; `swing/data/ohlcv_archive.py:read_or_fetch_archive` for SPY-bar read path; `swing/pipeline/runner.py:_step_weather` for SPY-bar write path
   - P14.N3: `Grep "PROVISIONAL"` across `swing/` to locate the flag + flip-condition; likely candidates `swing/web/view_models/daily_management.py` + `swing/trades/daily_management.py` + `swing/data/repos/daily_management.py`; backing table `daily_management_records` per Phase 8 ship + Phase 9 `risk_policy` ratification ladder

7. **Memory entries** at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\`:
   - `feedback_orchestrator_qa_implementer_product` (orchestrator-side; informational)
   - `feedback_commit_brief_before_inline_prompt` (commit brief BEFORE inline prompt; applies if you spawn sub-implementer work)
   - `project_applied_research_arc_2026-05-27` (substantive context on why Phase 14 prioritizes UX + wiring + temporal log over ruleset deployment)

8. **Phase 13 T4.SB return report** at `docs/phase13-t4-sb-return-report.md` — V1 simplifications + V2 candidates banked at end-of-Phase-13; some may overlap V2.G3/V2.G4/P14.N3 root causes (cross-check at brainstorm).

---

## §1 Pre-locked operator decisions (Sec 9.1 LOCKs + sub-bundle-specific; DO NOT re-litigate)

### §1.1 Decision 1 — Sub-bundle scope: ONLY V2.G3 + V2.G4 + P14.N3 (Sec 9.1 Q1 LOCK)

Sub-bundle 1 ships ONLY the three data-wiring items above. Do NOT widen scope to:
- Chart-surface uniformity (V2.G1 + V2.G2 + P14.N1 + P14.N2 + P14.N4) — Sub-bundle 3 scope
- Temporal log infrastructure — Sub-bundle 2 scope
- Review + journal UX (CR.1 + P14.N6) — Sub-bundle 4 scope
- Metrics overview (P14.N5) — Sub-bundle 5 scope
- Any ruleset deployment work — Phase 14 OUT-OF-SCOPE per commissioning brief Sec 1 + arc closure
- Any Phase 15+ scope (substrate-size augmentation; Finviz filter widening; etc.)

**Brainstorm SHALL:**
- Verify each of the three items is self-contained at its current scope (NO cross-sub-bundle dependency creep).
- If V2.G4 investigation reveals overlap with V2.G1 root cause (per phase3e-todo V2.G4 cross-reference note: "Possibly tied to V2.G1 — if `market_weather` and `hyprec_detail` share the same broken cache-hydration path"), SURFACE the overlap as an Open Question (§3) for orchestrator review; do NOT silently expand scope to fix V2.G1.

### §1.2 Decision 2 — Codex chain count: SINGLE chain at end (Sec 9.1 Q7 LOCK)

Data-wiring is a pure UX/wiring sub-bundle. No analytical artifact (no smoke artifact; no methodology emission; no findings doc beyond the standard return report). Single Codex MCP chain at the end of the brainstorm phase per gotcha #36 explicit caveat: "production-feature dispatches without a substantive emitted artifact may continue to use single-chain placement at orchestrator discretion."

**Brainstorm SHALL:**
- Invoke Codex MCP review ONCE after the spec draft is complete + before final commit.
- Target convergence within 2-4 rounds (scope is bounded).

### §1.3 Decision 3 — Serial execution per Sec 9.1 Q2 LOCK

Sub-bundle 1 ships FIRST. Sub-bundle 2 (temporal log V1+) depends on Sub-bundle 1 merge. Do NOT propose parallel execution with Sub-bundle 2.

### §1.4 Decision 4 — Operator-witnessed gate at sub-bundle merge per Sec 9.1 Q6 LOCK

Sub-bundle 1 ships with per-sub-bundle operator-witnessed gate (browser verification of all three fixes). Final Phase 14 cross-sub-bundle integration review at Phase 14 close-out.

**Brainstorm SHALL design** an operator-witnessed gate surface enumeration covering:
- V2.G3 — VSAT row in open-positions table shows non-NULL Sector + Industry post-fix
- V2.G4 — Refresh weather chart button produces a fresh SPY weather chart render (NOT the "no OHLCV bars" error)
- P14.N3 — Daily management Capital % "PROVISIONAL" suffix either explained (tooltip / inline description) OR removed when condition no longer applies

### §1.5 Decision 5 — Schema migration posture

V1 expectation: **NO schema migration**. Sub-bundle 1 stays Schema v21 LOCKED.

**Brainstorm SHALL verify** the no-migration posture per item:
- V2.G3: prefer view-layer fix (denormalize-at-read OR cache-last-known per-ticker) over schema-write-time denormalization (which would require `trades.sector` + `trades.industry` columns + v22 migration); IF the investigation surfaces that view-layer fix is non-viable, ESCALATE (do NOT silently propose schema migration; route through orchestrator).
- V2.G4: cache-hydration / read-path fix; no schema impact expected.
- P14.N3: UI affordance + investigation (Grep flip-condition); IF the investigation reveals "PROVISIONAL" is an undocumented CHECK enum value (vs a runtime-computed suffix), schema CHECK widening to descriptive enum values may be warranted — BUT this widening is V2 candidate per phase3e-todo P14.N3 proposed-resolution wording; V1 ships the UI affordance only.

**If any item's investigation reveals schema migration is unavoidable**, SURFACE the migration scope as an Open Question (§3) for orchestrator review. The temporal log Sub-bundle 2 owns the v22 migration slot; Sub-bundle 1 introducing a v22 migration would collide with Sub-bundle 2.

### §1.6 Decision 6 — Backwards-compatibility for legacy data

V2.G3's phase3e-todo entry explicitly notes: "DHA (DHC?) never had them as that position was opened prior to them being included." Operator already acknowledges legacy NULL Sector/Industry values are acceptable for pre-feature trades.

**Brainstorm SHALL design** the V2.G3 fix to:
- Restore Sector/Industry for tickers that HAVE them in the upstream data source (candidates / finviz CSV / etc.) but lost them due to the JOIN failure mode
- NOT attempt to backfill legacy NULL values
- Document the legacy-NULL acknowledgment explicitly in the spec

---

## §2 Architectural surface for the brainstorm to design

Given §1's locks, the brainstorm spec MUST design + Codex-review the following:

### §2.1 V2.G3 — VSAT lost Sector + Industry investigation + fix

**Investigation path** (brainstorm spec walks through):

1. **Trace persistence path**: where do Sector + Industry land in the database?
   - `candidates.sector` + `candidates.industry` (likely; written per-evaluation-run from finviz CSV; rotates out when ticker leaves finviz screen)
   - `trades.sector` + `trades.industry` (verify NOT present in v21 schema; would be V2 candidate)
   - Some other persistence surface?
2. **Trace read path**: how does the open-positions row builder consume Sector + Industry?
   - View model JOINs `trades` with `candidates` on ticker + latest evaluation_run_id?
   - View model reads from a separate cached projection?
3. **Identify the failure mode**: which JOIN / read step produces NULL for VSAT?
   - Hypothesis A (most likely; per phase3e-todo cross-reference to "PriceCache `_last_close`" gotcha): VSAT rotated OUT of today's finviz CSV → no fresh candidates row → JOIN returns NULL for Sector/Industry → open-positions row renders NULL.
   - Hypothesis B: the new finviz CSV ingest path (Phase 11 finviz API integration) may have failed to persist Sector/Industry for some columns/rows
   - Hypothesis C: a JOIN condition lost the row mid-pipeline (e.g., `_step_evaluate` excluded VSAT under an unrelated filter)

**Fix candidates** (brainstorm spec enumerates + recommends):

- **Fix A (view-layer; recommended for V1)**: open-positions VM builder, if `candidates JOIN` returns NULL for Sector/Industry on an open-position ticker, consult `candidates_history` (or equivalent fallback table) for the most recent non-NULL Sector/Industry value for that ticker. Mirrors PriceCache `_last_close` ticker-rotation fallback pattern. NO schema migration.
- **Fix B (schema denormalization at entry-form time)**: `trades.sector` + `trades.industry` columns added; entry-form POST snapshots current Sector/Industry from candidates at trade-entry time. Schema v22 migration. **Brainstorm SHALL flag this as V2 candidate if Fix A is viable**; if Fix A is non-viable, ESCALATE to orchestrator.
- **Fix C (union open-trade tickers into Sector/Industry persistence)**: `_step_evaluate` writes Sector/Industry for open-trade tickers even if they aren't in today's finviz CSV (mirror precedent: open-trade tickers are unioned into `_step_evaluate` for `bucket='excluded'` candidate rows so their close stays fresh). NO schema migration.
- **Fix D (per-ticker last-known cache)**: separate `sector_industry_cache` table keyed on ticker; written at every observation; consumed by the VM builder fallback path. Schema v22 migration. **V2 candidate.**

**Brainstorm SHALL recommend** Fix A or Fix C (V1; no schema migration); Fix B + Fix D bank as V2 candidates.

**Discriminating tests** (brainstorm spec enumerates):
- Plant trade row for ticker X with NULL Sector/Industry; plant historical candidates row for X with non-NULL Sector/Industry; assert VM renders non-NULL via fallback.
- Plant trade row for ticker Y with NULL Sector/Industry AND no historical candidates row; assert VM renders NULL gracefully (mirrors legacy DHA/DHC acknowledgment).
- Round-trip test that ticker X's Sector/Industry survives a pipeline run where X is NOT in today's finviz CSV (post-fix the value remains visible).

### §2.2 V2.G4 — "Refresh weather chart" SPY OHLCV bars unavailable investigation + fix

**Investigation path** (brainstorm spec walks through):

1. **Trace SPY-bar write path**: where does the pipeline persist SPY OHLCV bars?
   - `swing/pipeline/runner.py:_step_weather` — confirm SPY bars are written to `OhlcvArchive` or `OhlcvCache` or another surface
   - `swing/data/ohlcv_archive.py:write_window` — verify SPY persistence semantic
   - Verify `cfg.rs.benchmark_ticker` resolution at write time (cfg vs literal "SPY")
2. **Trace SPY-bar read path**: where does the refresh handler read SPY bars from?
   - `swing/web/routes/dashboard.py:/dashboard/weather-chart/refresh` handler
   - `swing/web/chart_jit.py:get_or_render_surface(surface='market_weather')` invocation chain
   - `swing/web/charts.py:render_market_weather_svg(bars=...)` — what `bars` value does it receive?
   - `cfg.rs.benchmark_ticker` resolution at read time (cfg vs literal "SPY"; verify request-time vs handler-init-time)
3. **Identify the divergence**: which read step returns empty / fails for SPY?
   - Hypothesis A: `chart_jit.get_or_render_surface` does NOT invoke an OHLCV-cache hydration step; the handler passes an empty / unhydrated `bars` DataFrame; `render_market_weather_svg` raises the "no OHLCV bars available" error.
   - Hypothesis B: cfg.rs.benchmark_ticker is read at handler-init time (frozen at app boot) vs request-time; if cfg was reloaded mid-session, value drift.
   - Hypothesis C: SPY bars persisted by `_step_weather` write to a DIFFERENT cache path than what the refresh handler reads; the two paths diverged at some point in Phase 13.
   - Hypothesis D: V2.G1 family — chart_jit cache-hydration is broken for ALL surfaces consuming `market_weather`-style data; V2.G4 + V2.G1 share root cause.

**Fix candidates** (brainstorm spec enumerates + recommends):

- **Fix A (hook chart_jit cache-miss into OhlcvArchive read)**: when `chart_jit.get_or_render_surface(surface='market_weather')` fires, the cache-miss path explicitly invokes `read_or_fetch_archive(ticker=cfg.rs.benchmark_ticker, ...)` BEFORE invoking the renderer. Closes the hydration gap.
- **Fix B (ensure refresh handler invokes hydration explicitly)**: the `/dashboard/weather-chart/refresh` handler invokes `OhlcvCache.refresh_archive(ticker='SPY')` (or equivalent) BEFORE invoking `chart_jit.get_or_render_surface`. Belt-and-suspenders.
- **Fix C (audit cfg.rs.benchmark_ticker resolution)**: enforce request-time cfg resolution at handler entry; document cfg-freshness invariant.

**If Hypothesis D confirms** (V2.G4 + V2.G1 share root cause), SURFACE the overlap as an Open Question (§3); the orchestrator may direct V2.G4 to bank with V2.G1 in Sub-bundle 3 instead of fixing in Sub-bundle 1.

**Discriminating tests** (brainstorm spec enumerates):
- Plant SPY bars in `OhlcvCache` directly; invoke handler; assert render succeeds.
- Plant empty SPY bars (or simulate cache miss); invoke handler; assert hydration fires + render succeeds.
- Assert handler reads SPY ticker from `cfg.rs.benchmark_ticker` at request-time (not handler-init-time).
- Mock yfinance to simulate SPY fetch failure; assert handler returns operator-friendly error (not the current "no OHLCV bars" error).

### §2.3 P14.N3 — Daily management Capital % "PROVISIONAL" suffix investigation + fix

**Investigation path** (brainstorm spec walks through):

1. **Locate the flag**: `Grep "PROVISIONAL"` across `swing/` and `tests/`.
2. **Identify the flip-condition**: what causes the suffix to appear? What causes it to disappear?
3. **Identify the state machine**: is "PROVISIONAL" a runtime-computed suffix (template-rendered conditionally) OR a persisted state value (e.g., `daily_management_records.capital_percent_status='provisional'`)?
4. **Map to Phase 8 + Phase 9 semantics**:
   - Phase 8 introduced `daily_management_records` table with state machine semantics (see Phase 8 R2.M2+R3.M2+R4.M2 server-stamping family gotchas)
   - Phase 9 introduced `risk_policy` ratification (single-fire at v16→v17; see gotcha "Phase 9 risk_policy ratification is single-fire")
   - Likely the "PROVISIONAL" suffix is a pre-reconciliation OR pre-equity-snapshot-finalization placeholder
5. **Confirm the clear-condition**: does the flag clear automatically when reconciliation completes? OR only on manual operator action? OR never (bug)?

**Fix candidates** (brainstorm spec enumerates + recommends):

- **Fix A (UI affordance; recommended for V1)**: extend the `/daily-management` template + VM to surface a tooltip OR inline explanation describing why "PROVISIONAL" appears + what would clear it. NO schema migration; NO state-machine refactor. Matches CLAUDE.md gotcha #11 template-rendering-surface audit discipline.
- **Fix B (CHECK enum widening to descriptive values)**: if "PROVISIONAL" is a persisted CHECK enum value, widen the CHECK to include descriptive variants (e.g., `'provisional_pre_reconciliation'`, `'provisional_pre_equity_snapshot'`, `'finalized'`). **V2 candidate per phase3e-todo P14.N3 proposed-resolution wording**; do NOT include in V1 unless investigation reveals the V1 UI affordance is non-viable without schema change.
- **Fix C (auto-clear on reconciliation completion)**: if the flag is supposed to clear when reconciliation completes but currently doesn't (bug), wire the clear-condition into the reconciliation flow service. May require small touch on `swing/trades/reconciliation_auto_correct.py` OR `swing/trades/daily_management.py`. **Brainstorm assesses** at investigation time.

**Brainstorm SHALL recommend Fix A** unless investigation reveals the flag is bugged (in which case Fix C is correct + Fix A becomes complement).

**Discriminating tests** (brainstorm spec enumerates):
- Plant `daily_management_records` row in each known state; assert UI renders the correct affordance (tooltip text OR description OR no flag if condition no longer applies).
- Plant pre-reconciliation row; trigger reconciliation; assert flag clears post-fix (Fix C path).
- Template-rendering test asserting the tooltip text is present (Fix A path).

---

## §3 Open questions (Codex chain SHOULD surface answers)

Brainstorm Codex chain enumerates + designs (operator decision pending at brainstorm-output time):

1. **V2.G3 Fix A vs Fix C** — view-layer fallback (per-VM lookup of last-known) vs union-into-`_step_evaluate` (write-time fix). Trade-off: view-layer adds query overhead per render; write-time adds work to pipeline + may write stale data if Sector/Industry changes (rare). Brainstorm recommends + rationalizes.

2. **V2.G4 + V2.G1 root cause overlap** — does V2.G4 SPY-bar refresh fail for the SAME reason hyp-rec / watchlist expanded charts don't render candlesticks? If yes, ESCALATE to orchestrator for cross-sub-bundle scoping decision.

3. **V2.G4 cfg.rs.benchmark_ticker resolution timing** — handler-init vs request-time. Verify current behavior + recommend if change is warranted.

4. **P14.N3 state-machine semantic** — is "PROVISIONAL" runtime-computed OR persisted? Investigation result drives Fix A vs Fix B vs Fix C choice.

5. **Test fixture strategy** — pure TestClient + monkeypatched OhlcvArchive / candidates queries OR cassette-based? Brainstorm recommends per item.

6. **Operator-witnessed gate surface count** — likely 3-5 surfaces (S1 fast/ruff; S2 V2.G3 VSAT row Sector/Industry visible; S3 V2.G4 Refresh weather chart produces fresh SVG; S4 P14.N3 tooltip/explanation present; optional S5 cross-fix regression check).

7. **Schema migration escalation rule** — if ANY item's investigation reveals schema migration is unavoidable, brainstorm SHALL escalate to orchestrator (per §1.5 LOCK). Do NOT silently propose schema migration.

8. **Sub-bundle dispatch decomposition** — likely ONE writing-plans / executing-plans dispatch (three small fixes; coheres around same VM + template + service-layer surfaces). Brainstorm verifies + locks.

9. **`_thumb_bytes` partial precedent** — V2.G3 fix may want to mirror the watchlist `_thumb_bytes` partial's fallback semantic (gracefully render NULL when no data is available); verify the precedent shape + propose the parallel for Sector/Industry.

10. **HTMX failure surface assessment** — Sub-bundle 1 is unlikely to add NEW HTMX surfaces (V2.G4 refresh handler ALREADY EXISTS; the fix is a wiring fix not a UX surface change). Brainstorm verifies the no-new-HTMX-surface assumption + flags if any item DOES introduce a new HTMX endpoint (which would invoke the HTMX trinity discipline: Phase 5 R1 M1 + M2 + Phase 6 I3 LOCKs).

---

## §4 OUT OF SCOPE (do not design)

- **V2.G1** (hyp-rec + watchlist expanded charts not rendering candlesticks) — Sub-bundle 3 scope (chart-surface uniformity). Even if V2.G4 root-cause investigation surfaces overlap with V2.G1, the fix is owned by Sub-bundle 3.
- **V2.G2** (watchlist chart title "hyp-rec detail" leakage) — Sub-bundle 3 scope (v23 schema rename per Sec 9.1 Q4 LOCK).
- **P14.N1** (small thumbnail charts on open-positions + hyp-rec tables) — Sub-bundle 3 scope.
- **P14.N2** (all charts must be candlesticks; 10+20 MA overlays) — Sub-bundle 3 scope.
- **P14.N4** (BULZ green/yellow shaded region undescribed) — Sub-bundle 3 scope.
- **CR.1** (closeout review exit data + chart snapshot) — Sub-bundle 4 scope.
- **P14.N6** (journal page redesign) — Sub-bundle 4 scope.
- **P14.N5** (metrics overview dashboard) — Sub-bundle 5 scope.
- **Temporal log infrastructure** (Sec 2.5 of commissioning brief) — Sub-bundle 2 scope.
- **Any ruleset deployment work** — Phase 14 OUT-OF-SCOPE per commissioning brief Sec 1 + arc closure.
- **Phase 15+ scope** (substrate-size augmentation; Finviz filter widening; cohort-stability LOCK; D2 baseline canonical_survival_rate L4 remediation) — explicit Phase 15+ candidates per commissioning brief Sec 8.
- **Schema migrations beyond v21** — Sub-bundle 1 stays v21 LOCKED per §1.5; v22 belongs to Sub-bundle 2 (temporal log); v23 belongs to Sub-bundle 3 (V2.G2 rename).
- **Behavioral changes to non-touched surfaces** — Sub-bundle 1 is consumer-side of Phase 11 finviz CSV ingest + Phase 8 daily_management + Phase 9 risk_policy + Phase 13 chart_jit. ESPECIALLY: do NOT modify `_step_evaluate` candidate persistence path unless V2.G3 Fix C is the recommended fix AND orchestrator concurs.
- **Operator failure-mode classification surface** — explicitly V2 candidate per Sec 9.1 Q3 LOCK (temporal log V1+ does NOT include); Phase 15+ scope.
- **CLAUDE.md / orchestrator-context archive-splits** — not Sub-bundle 1 scope.
- **Phase 8 walkthrough failing-test triage OR ruff E501 cleanup** — not Sub-bundle 1 scope.

---

## §5 Adversarial review (Codex)

Invoked automatically by `copowers:brainstorming` after the spec draft + before final commit.

**Expected chain shape:** 2-4 substantive Codex rounds (scope is bounded; three discrete fixes; single chain at end per §1.2 LOCK).

**Adversarial review watch items (Sub-bundle 1-specific):**

1. **PriceCache `_last_close` ticker-rotation discipline** (CLAUDE.md gotcha) — V2.G3 fix MUST mirror the precedent semantics (open-trade tickers must not lose data when they rotate out of finviz screen).
2. **Session-anchor read/write mismatch family** (CLAUDE.md gotcha) — V2.G4 SPY-bar read predicate MUST match the write predicate (likely `data_asof_date`-keyed; verify the read predicate doesn't drift to `action_session_for_run`).
3. **OHLCV fetch scope = open-trade tickers ONLY** (CLAUDE.md gotcha) — V2.G3 + V2.G4 fixes MUST NOT widen yfinance fetch scope; the discipline is preserved.
4. **Empty-pool early-return + audit emission** (gotcha #27) — V2.G4 refresh handler may have an early-return path; verify it emits `warnings_json` (or equivalent operator-visible signal) on the empty-bars path.
5. **Schema-CHECK + Python-constant + dataclass-validator paired discipline** (gotcha #11) — applies IF P14.N3 investigation reveals a CHECK enum widening (escalation per §1.5).
6. **OHLCV archive bar-content TEMPORAL mutation** (gotcha #26) — V2.G4 SPY-bar read MUST NOT silently re-fetch + mutate archive content; honor write-through-cache F6 discipline.
7. **Form-render anchor lifecycle audit** (gotcha #15 / Expansion #9) — applies IF any P14.N3 fix introduces an operator-visible state transition (likely not for V1 Fix A).
8. **Server-stamping for hidden audit fields** (Phase 8 family) — applies IF any P14.N3 fix adds a form-driven state transition.
9. **`Co-Authored-By` footer suppression** (project invariant) — explicit citation in dispatch prompts; ~581+ cumulative ZERO drift streak.
10. **ASCII-only template + CLI output** (gotcha #32) — declare scope in return report.
11. **Test fixture shape vs production emitter shape** (Phase 12 C.D family; gotcha "Synthetic-fixture-vs-production-emitter shape drift") — V2.G3 test fixtures MUST match the production candidates row shape exactly; V2.G4 fixtures MUST match the OhlcvArchive write shape exactly.
12. **Read-path mapping must keep pace with write-path** (gotcha "Read-path mapping must keep pace with write-path on widened columns") — applies IF any item's fix widens a dataclass; brainstorm verifies all `_row_to_<table>` mappers consume new fields.
13. **L2 LOCK preservation** (commissioning brief Sec 6) — ZERO new Schwab API calls; parametric source-grep test included in spec test scope.

---

## §6 Deliverable shape

**Spec document at `docs/superpowers/specs/<YYYY-MM-DD>-phase14-sub-bundle-1-data-wiring-design.md`** (mirror existing brainstorm spec format):

- §0 Glossary
- §1 Architecture overview (three items; cohesion around dashboard + daily-management surfaces)
- §2 Pre-locked operator decisions (the 6 from §1 above; verbatim binding clauses)
- §3 Module touch list (per-item; with `(NEW)` / `(MODIFIED)` annotations)
- §4 V2.G3 investigation + fix design (per §2.1 walkthrough)
- §5 V2.G4 investigation + fix design (per §2.2 walkthrough)
- §6 P14.N3 investigation + fix design (per §2.3 walkthrough)
- §7 Error handling + edge cases (per item)
- §8 Cross-item coherence (e.g., shared VM extensions; shared template patterns)
- §9 Discriminating-example walkthroughs (5-10 cases per item covering pass + fail + edge paths)
- §10 Sub-bundle decomposition (likely single writing-plans / executing-plans dispatch; brainstorm verifies)
- §11 Test fixture strategy (per item; TestClient discipline)
- §12 Schema impact analysis (verify v21 LOCKED; ESCALATE if any item surfaces unavoidable migration)
- §13 V1 simplifications + V2 candidates banked (e.g., V2.G3 Fix B + D; P14.N3 Fix B)
- §14 Operator decision items pending (Open Questions from §3 that Codex didn't resolve)
- §15 Cumulative discipline compliance summary (gotchas applied per item)

**Target line count: ~400-600 lines** (smaller than typical Phase 13 specs because scope is bounded to three small fixes).

**Commit message stem:** `docs(phase14-sub-bundle-1-spec): brainstorm -- <N> Codex rounds -> NO_NEW_CRITICAL_MAJOR convergent (R1 ... -> R<N> ...)`.

---

## §7 If you get stuck

- If V2.G3 investigation surfaces a schema migration is unavoidable, **STOP + escalate** to orchestrator. Do not silently propose schema work.
- If V2.G4 root cause overlaps with V2.G1, SURFACE as Open Question (§3 #2) for orchestrator cross-sub-bundle scoping decision; do NOT widen Sub-bundle 1 scope to fix V2.G1.
- If P14.N3 investigation reveals a Phase 8 / Phase 9 state-machine bug (not just a UI affordance gap), SURFACE as Open Question for orchestrator scoping; do not silently expand to a state-machine refactor.
- If Codex pushes back on the V1 single-Codex-chain choice per §1.2, HOLD THE LINE — Sec 9.1 Q7 LOCK + gotcha #36 caveat permit single chain for pure UX/wiring sub-bundles.
- If Codex pushes back on the no-schema-migration posture per §1.5, HOLD THE LINE — operator-locked at commissioning.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in spec + return report.
- DO NOT propose temporal log work within Sub-bundle 1 scope (§4 lock; Sub-bundle 2 scope).
- DO NOT propose chart-surface uniformity work within Sub-bundle 1 scope (§4 lock; Sub-bundle 3 scope).
- DO NOT add `Co-Authored-By` footer to ANY commit message (project invariant; ~581+ cumulative ZERO drift streak; CLAUDE.md governs).
- DO NOT skip hooks (`--no-verify`) or bypass signing on commits (CLAUDE.md "Conventions" + project discipline).

---

## §8 Return report shape

After Codex chain converges + before final commit, draft a return report at `docs/phase14-sub-bundle-1-data-wiring-brainstorm-return-report.md`:

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Spec line count.
4. Pre-locked operator decisions verbatim verification (Sec 9.1 LOCKs + §1 sub-bundle locks).
5. §3 Open Questions: which Codex resolved + which deferred to operator review.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Cumulative V2 candidates banked (per item).
8. Forward-binding lessons for writing-plans dispatch.
9. CLAUDE.md status-line refresh draft text.
10. Sub-bundle decomposition recommendation (single dispatch vs split).
11. Schema impact verdict (v21 unchanged; explicit confirmation).
12. Cumulative gotcha set application summary (which gotchas fired; which were preempted).
13. Worktree teardown status.
14. ZERO Co-Authored-By footer drift confirmation (verify via `%(trailers)` inspection per Phase 12.5 #3 + V2-mechanic precedent).

---

## §9 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — branch `phase14-sub-bundle-1-data-wiring-brainstorm` (matches cleanup-script regex). Worktree directory `.worktrees/phase14-sub-bundle-1-data-wiring-brainstorm/`.
- **Model:** defer to harness default.
- **Expected duration:** ~60-120 min brainstorm + ~30-60 min Codex chain. Total ~2 hours operator-paced.
- **Codex MCP chain count:** SINGLE chain at end (per §1.2 + Sec 9.1 Q7 LOCK).

---

*End of brief. Phase 14 Sub-bundle 1 brainstorm dispatch — 3 data-wiring items (V2.G3 + V2.G4 + P14.N3); Sec 9.1 LOCKs honored; ~400-600 line spec target; 2-4 Codex round expectation. OUTPUT: design spec for the data-wiring fixes that writing-plans phase can decompose into a single executing-plans dispatch.*
