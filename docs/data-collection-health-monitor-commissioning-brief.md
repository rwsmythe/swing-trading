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
