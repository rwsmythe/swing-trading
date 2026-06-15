# Data-collection health monitor — RD→CHARC commissioning brief

**Author:** Research Director (RD). **Routes to:** CHARC (architecture pass per charter §1 — it is a **NEW STANDING PROCESS**, a §3 tripwire; if placed nightly in the pipeline it is also a new pipeline step = orchestrator lane, like the Arc-5 drumbeat integration).
**Date:** 2026-06-13. **Priority:** HIGH (operator-stated). **Candidate placement:** Phase 18 (CHARC/operator decide).
**Companion:** `docs/temporal-log-nan-writer-fix-commissioning-brief.md` (the defect that motivated this). Build order independent; the monitor should ALSO catch the NaN class going forward regardless of the writer fix.

## §0 Read first
- The 2026-06-13 RD data-collection audit (charter §7 once logged) — the probe set below is exactly that audit, mechanized.
- `scripts/weekly_glance.py` — the existing operator-facing 5-min checklist. The monitor is its **integrity superset**, not a replacement.
- `docs/research-director-watch-standard.md` §3.1 (the monthly-read checklist this partly mechanizes).
- Charter behavioral directive #11: "prefer executable probes over prose checklists" — operationalizing the weekly glance found two defects on its first run; the same logic applies here.

## §1 Strategic context / motivation
Today's defect (the temporal-log NaN) entered the log on **2026-06-10** and was not surfaced until a **manual deep audit on 2026-06-13** — it rode invisibly for 2+ days, and would have ridden longer: **RD spins up roughly weekly** (operator cadence), and the operator-facing surfaces showed all-clear. `weekly_glance.py` watches the **funnel/trigger/intent** layer; it does **not** watch the **data-integrity** layer (non-finite OHLC, the excluded-reason breakdown, orphans, look-ahead, observation-date gaps, null pivots, error-bucket spikes). That blind spot is exactly where this defect lived. A mechanized integrity monitor closes it and turns "RD happens to audit" into "the next defect of this class is flagged automatically."

## §2 Demand — what the monitor must do
A **read-only** integrity monitor whose flags the RD reviews (flags feed RD review; it does not auto-act — same posture as `weekly_glance.py`'s tripwire mapping). The probe set (the integrity layer, from today's audit):
1. **Temporal-log non-finite OHLC scan** — count + tickers + dates of any NaN/None in `pattern_forward_observations.ohlc_today_json`. (THE check that would have caught today's defect on 06-10.)
2. **Excluded-reason breakdown** (from the newest `manifest.json` the engine already emits — do NOT recompute attribution): `invalid_ohlc` / `insufficient_forward_depth` / `missing_observations`, each as a count and as a % of `unique_signals`; flag on threshold or week-over-week spike.
3. **Forward-obs coverage gaps** — mature detections (detection_date older than the newest session) whose observation-date sequence has holes vs the trading calendar.
4. **Structural integrity** — orphan observations (no parent detection); look-ahead violations (first obs precedes detection_date).
5. **Pipeline-run health** — recent non-`complete` runs; stuck/heartbeat-stale runs; a spike in `warnings_json` entries by step.
6. **Candidate/eval completeness** — null pivots; error-bucket spike.
7. **Drumbeat liveness + funnel honesty** — newest-artifact age; `total_unattributed > 0` (overlaps weekly_glance / watch-standard T1/T2).

**Output:** a structured, ASCII report — `ALL CLEAR` or `ATTENTION` lines with severity, each mapped to the watch-standard tripwire it serves (or a new integrity flag id) — designed to be read at RD spin-up.

## §3 Open design questions (for the brainstorm/spec + CHARC)
1. **Form:** standalone `scripts/rd_health_monitor.py` vs a `--deep` flag on `weekly_glance.py`. **RD lean: separate script** — `weekly_glance.py` stays the operator's 5-min checklist; the monitor is the deeper RD-facing integrity superset.
2. **Cadence / placement (the highest-value question):**
   - **Spin-up read** (RD bootstrap step) — catches at the next RD spin-up (≈weekly).
   - **Nightly best-effort** appended to the drumbeat, writing a rolling flag artifact — catches a defect **the night it happens** (within a session, not a week). This is the higher-value half and is why today's 2-day latency happened.
   - **RD lean: BOTH** — nightly writes the flag; spin-up reads the accumulated flags. The nightly half is a pipeline step (orchestrator lane; coordinate like Arc-5).
3. **Where flags persist** — a rolling JSON/log the bootstrap reads, an artifact under `exports/research/`, or a `role_mail` note to `rd` on ATTENTION. (A mail-on-ATTENTION would surface a defect to the next RD spin-up automatically.)
4. **Thresholds** — derive ATTENTION cutoffs from this audit's baselines (e.g. `invalid_ohlc` > a small floor, any non-finite OHLC at all, any orphan/look-ahead = immediate).
5. **Watch-standard integration** — this mechanizes the §3.1 integrity checks + adds the data-quality layer; the standard's §3.1 should then reference it. **Amending the watch standard is RD's deliberate action, post-build** (not the implementer's).

## §4 LOCKS
1. **Read-only.** Opens the DB `mode=ro`; never writes the measurement DB. (The nightly flag artifact, if any, writes only its own log/JSON.)
2. **Single source of truth — do NOT fork the engine's funnel/attribution logic.** Read the `manifest.json` the engine already emits; recomputing attribution risks the exact synthetic-vs-production drift the program has been burned by.
3. **ASCII output only** (Windows cp1252 `UnicodeEncodeError` gotcha — `weekly_glance.py` already honors this).
4. **No new dependency** (stdlib `sqlite3` + `json` + `pathlib`, as `weekly_glance.py`).

## §5 Routing
New standing process → CHARC architecture pass + Phase 18 sequencing. The script itself is a one-file read-only probe (precedent: `weekly_glance.py`, which RD built directly), so the BUILD can be a focused dispatch; if the nightly-pipeline half is included, that step is the orchestrator lane (coordinate). RD reviews the return and then amends the watch standard to reference it.

---

## §6 COMMISSIONING ADDENDUM — 2026-06-15 (18-D sequenced; post-18-C/18-F reconciliation)

**Status:** the operator has sequenced 18-D NEXT (the last research-lane Phase-18 arc). This addendum brings the 2026-06-13 brief current for the three developments that post-date it and resolves §3's open questions per CHARC's pass. **The §1–§2 problem statement + §4 LOCKS stand unchanged.** CHARC already architecture-passed this brief at **C4** (build the read-only SCRIPT first; DEFER the nightly pipeline-step half to a fast-follow; if nightly is built it MUST use the 17-B `step_guard`, B-shape best-effort, `warnings_json`) and **C5** (`role_mail`-on-ATTENTION endorsed but only with the nightly half). This routes back to CHARC for the **sec-3 (envelope) architecture-pass CONFIRMATION** + the one §6.3 refinement below.

### §6.1 Three developments since 2026-06-13 (all SHIPPED on main)
- **18-C shipped** → `yfinance_calls` audit table EXISTS (fetch-layer transport observability). Adds a check (§6.2 #7).
- **18-E shipped** → `swing/monitoring/compute_tool_health(conn, *, cfg, prices_cache_dir, now) -> ToolHealthStatus` + `scripts/tool_health.py` are the **precedent to mirror** (same package, same section-3 envelope, same read-only/ASCII/no-pandas discipline).
- **18-F shipped** → the research-artifact contract is **LIVE on main** in `swing/monitoring/stoplights.py`: `RESEARCH_HEALTH_ARTIFACT_PATH = exports/research/health/latest.json`, `RESEARCH_MONITOR_ID = "research_measurement"`, `RESEARCH_ARTIFACT_MAX_AGE_DAYS = 7`. 18-D **IMPORTS** all three (C1 single-source; never redeclare) and writes the conformant envelope there.

### §6.2 Architecture + the check set
- A pure `compute_research_health(conn, ...) -> ResearchHealthStatus` in `swing/monitoring/` (sibling of `compute_tool_health`), emitting the **section-3 envelope** `{monitor, generated_ts, overall, checks:[{key,status,summary,detail}]}` with `monitor="research_measurement"`, `overall=worst_of(checks)`, a fresh `generated_ts`.
- `scripts/research_health.py` (mirror `scripts/tool_health.py`): prints the ASCII report (RD spin-up review) AND writes the envelope to `latest.json` (§6.3).
- Checks (the §2 probe set as section-3 checks; each → one `{key,status,summary,detail}`):
  1. `temporal_log_finiteness` — non-finite OHLC scan of `pattern_forward_observations` (red on any). **The 18-A defect detector; the data-USABILITY authority.**
  2. `excluded_reason_breakdown` — `invalid_ohlc`/`insufficient_forward_depth`/`missing_observations` from the engine **manifest** (read, do NOT recompute — §4.2); flag on spike.
  3. `coverage_gaps` — mature-detection observation-date holes vs the trading calendar.
  4. `structural_integrity` — orphan observations + look-ahead violations.
  5. `drumbeat_liveness` — newest-artifact age + `total_unattributed > 0`.
  6. `candidate_completeness` — null pivots + error-bucket spike.
  7. **NEW (post-18-C) `fetch_transport_health`** — `yfinance_calls` error/empty RATE as a **TRANSPORT indicator ONLY** (the 18-C boundary, LOAD-BEARING): consume `status` best-effort (a stale `in_flight` row = incomplete/unknown, NOT a hung call; drops under contention → treat as a sample/indicator, NEVER a census — do not alarm on a low row count). **`status='success'` is TRANSPORT success, NOT data usability** — the all-NaN-Close ragged bar records `success`; so this check NEVER substitutes for #1. `temporal_log_finiteness` stays the usability authority; the two are complementary.

### §6.3 Cadence — C4 staged, RECONCILED with the 18-F staleness gate (the ONE item for CHARC's sec-3 confirmation)
- **Script-first (C4):** `scripts/research_health.py` computes + prints ASCII **AND writes the section-3 envelope to `latest.json` on each run.**
- **REFINEMENT of C5 flagged for CHARC's confirmation:** C5 framed the script-half as persisting "a plain ASCII report" (no artifact). But 18-F's research stoplight (now LIVE) reads `latest.json` and **greys if it is absent or stale**. So the script-first half MUST ALSO write `latest.json` (trivial — the same computed envelope) or the stoplight never lights during the script-first phase. Net: script-first writes BOTH (ASCII for RD + JSON for the stoplight) → the stoplight is green-after-spin-up and greys toward the 7-day edge (an honest "research-health last assessed N days ago"). This refines C5's "ASCII-only script half"; it does not change C4's "defer the nightly STEP."
- **Nightly fast-follow (C4/C5):** a pipeline step via the 17-B `step_guard` (B-shape best-effort, `warnings_json`) running the SAME `compute_research_health` + writing `latest.json` nightly + `role_mail`-fyi-to-`rd` on ATTENTION (C5). This keeps `latest.json` < 1 day fresh (staleness gate stays green) AND doubles as the GUI drumbeat-liveness signal (>7d with no nightly → stoplight greys = the T1 condition surfaced at the GUI).
- **The 5 false-green gates the envelope MUST satisfy** (18-F's reader, `read_validated_research_envelope`): (1) `monitor=="research_measurement"`; (2) `overall∈{green,yellow,red}` valid; (3) `overall==worst_of(checks)`; (4) `generated_ts` present + parseable + NOT future-dated; (5) `≤ 7` days. `compute_research_health` satisfies (3) + (4) by construction.

### §6.4 RD merge-blocking gate (measurement-core) + routing
- **RD is MERGE-BLOCKING on 18-D** (CHARC confirmed: measurement-core). My gate at the executing return, verified on the shipped diff: (a) truly **read-only** — `mode=ro`; never writes the measurement DB (the ONLY writes are `latest.json` + the ASCII report); (b) **no funnel fork** — reads the engine manifest, never recomputes attribution; (c) the **transport-vs-usability boundary** respected (#7 is a transport indicator; #1 is the usability authority); (d) if the nightly half is in scope, it uses `step_guard` B-shape best-effort and **never perturbs the pipeline / measurement steps** (the Arc-5 drumbeat posture). The codex-auto-review A/B re-test rides this executing review (CHARC-lane experiment; does NOT touch my measurement-integrity gate).
- **Route:** CHARC sec-3 confirmation (envelope conformance + the §6.3 C5 refinement) → operator dispatches writing-plans → executing → RD QA + merge-blocking sign-off. **RD post-build action:** amend `docs/research-director-watch-standard.md` §3.1 to reference the monitor (deliberate, RD-only).
