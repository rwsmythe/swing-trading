# CHARC architecture pass — RD's two Phase-18 candidate briefs (2026-06-13)

**Author:** CHARC (tool director), per charter §2.4 tripwire gate. **Requested by:** RD (both briefs cross tripwires). **Decision/sequencing:** operator-carried — this is the engineering-soundness verdict + binding conditions, not a commission.
**Subjects:** Brief 1 `docs/temporal-log-nan-writer-fix-commissioning-brief.md` (defect) · Brief 2 `docs/data-collection-health-monitor-commissioning-brief.md` (new standing process).
**Grounding:** all load-bearing claims verified on disk 2026-06-13 (per §5.7 — verify divergence/absence claims before acting). Verdict: **both PASS, with conditions.**

---

## Brief 1 — temporal-log NaN-writer fix: PASS (conditions C1-C3)

**Verified on disk:** `build_ohlc_today_json` (temporal_metadata.py) guards completed-session + key-presence + provider, NO finiteness check (confirmed — no `isfinite`/`isnan` in the body). `_trim_trailing_ragged` exists ONLY in `swing/data/ohlcv_archive.py` (3 sites), never mirrored to the temporal writer — the two-path divergence is real. `validate_bars` (research/harness/shadow_expectancy/validate.py) uses `math.isfinite(v) and v >= 0` → the engine honestly rejects non-finite bars to `invalid_ohlc` BEFORE the sim. **The RD's diagnosis is accurate: this is the Arc-8 fix's missing mirror on a second write path; the consequence is attrition (30% of attributed signals excluded), NOT corruption (no R poisoned).**

**Tripwire:** correctly flagged — `swing/pipeline` writer (+`swing/data`/migration only if the §4.2 backfill is chosen). Routing is right.

**C1 — SHARED finiteness predicate, not a third copy (binding).** The root failure IS duplication-by-divergence; the fix must NOT add a third copy of the finiteness logic. Extract a pure `is_finite_ohlc_bar(...)` (or lift `_trim_trailing_ragged`'s finiteness core) into ONE shared helper both write paths consume. **Import-direction constraint:** the shared predicate lives in `swing/data/` (where `ohlcv_archive` already is); `temporal_metadata.py` (pipeline) imports FROM data — the allowed direction. `swing/data/` must NEVER import from `swing/pipeline/` (the §4.1-verified-healthy layer rule). A predicate placed in pipeline that data must import would invert the layering — reject that shape.

**C2 — SPLIT the writer fix from the backfill; ship the writer first (binding sequencing).** Two separable pieces with very different risk:
- (a) **Writer fix** — add the finiteness guard (skip-with-warning, mirroring Arc-8's "never persist bad data; leave the hole; the engine tolerates a hole, not a NaN" — I concur with the RD lean over reject-and-raise). NO schema, NO data mutation, NO operator data-gate beyond the normal cycle. This stops the bleeding. Ship it alone first.
- (b) **The 103 existing rows** — a one-time governed backfill from the Arc-8-protected archive is the ONLY part that mutates the "immutable" log → it needs a migration AND an operator data-gate AND the §5 look-ahead re-verification (`observation_date ≥ data_asof_date` post-repair). Keep it a DISTINCT sub-arc decided on its own merits. Do NOT bundle it into the writer fix. (Cost it as the RD asked, but the writer fix must not wait on the backfill decision.)
  - **The "operator data-gate" is TWO touchpoints, both AFTER costing (operator clarification 2026-06-13):** (i) **GO/NO-GO** — a `decision_request` posed DURING planning, as the gating deliverable of the backfill sub-arc's brainstorm/spec once it has costed recoverability (which of the 19 tickers' bars the archive actually holds for those sessions), the look-ahead proof, and the migration shape. NOT a pre-phase decision — deciding before the cost exists is deciding blind. (ii) **Execution gate** — the standard operator-witnessed live-migration + backup gate at merge, identical to v27/v28/v29; fires only if (i) is GO. What the operator decides PRE-Phase-18 is narrower: whether this backfill sub-arc is in scope as a candidate at all (phase-scoping, not the data-gate). The writer fix (a) reaches NEITHER touchpoint — no migration, normal cycle.

**C3 — observability (Brief 1 open-Q3) is DEDUPED to Brief 2, NOT built here (binding).** The excluded-reason breakdown surfacing belongs in the monitor (Brief 2), built once. The writer fix's skip→`warnings_json`→pipeline.log already partially closes the going-forward observability for the NaN event; the historical/aggregate surface is the monitor's job. Folding it into the writer arc duplicates Brief 2. (This is the 17-C lesson applied pre-commission: catch the redundancy before two arcs build the same thing.)

**Urgency framing for sequencing:** HIGH-value, not an emergency — the engine is robust (no wrong R), the cost is measurement throughput in a starved instrument. A Phase-18 slot, not a mid-Phase-17 interrupt (17 is nearly closed regardless).

---

## Brief 2 — data-collection health monitor: PASS (conditions C4-C5)

**Verified on disk:** `weekly_glance.py` is stdlib-only, `mode=ro` (line 111) — a clean precedent for a one-file read-only probe. `manifest.json` IS engine-emitted (`output.py:write_manifest_json`, called at `run.py:248`) — so the read-don't-recompute lock (§4.2) is satisfiable. The RD's locks (read-only, no funnel fork, ASCII, no new dep) are all sound and match the weekly_glance precedent.

**Tripwire:** correctly flagged — NEW STANDING PROCESS. Note the cadence answer changes the tripwire COUNT: spin-up-only = a script (RD lane, like weekly_glance, minimal surface); nightly = ALSO a new pipeline step (orchestrator lane, like Arc-5).

**C4 — build the read-only SCRIPT first; DEFER the nightly pipeline-step half to a fast-follow (recommended, operator decides).** The script (spin-up read) is the 80% — it closes the "RD spin-up sees the integrity layer" gap, is low-risk, and clones the weekly_glance shape. The nightly half buys latency (catch-the-night vs catch-at-next-spin-up) — real but a smaller increment, and a standing pipeline step should only be added once the probe definitions + thresholds are STABLE (you don't tune thresholds inside a nightly step). Stage it: script now, nightly-flag fast-follow once the probe set is validated against the audit baselines. **If the nightly half is built, it MUST use the 17-B `step_guard` (B-shape best-effort, `warnings_json`)** — it slots into the new abstraction cleanly; do not hand-roll a 12th wrapper.

**C5 — the role_mail-on-ATTENTION idea (open-Q3) is endorsed, but only with the nightly half.** A nightly monitor posting a `role_mail` fyi to `rd` on ATTENTION is the comms system doing exactly its job (surfacing a defect to the next RD spin-up automatically). It rides the nightly step, so it defers with C4's fast-follow. The script-half persists its flags as a plain ASCII report read at spin-up (no mail needed for the synchronous read).

---

## Cross-brief + Phase-18 shape (for operator sequencing)

- **Independent builds, one dedup:** the two briefs are independently buildable (RD confirmed). The single overlap — excluded-reason observability — is assigned to Brief 2 (C3). No redundant work.
- **Recommended order:** Brief 1 writer-fix (C2a, no migration) → Brief 2 script (C4) → [governed: Brief 1 backfill C2b, operator data-gate] → [fast-follow: Brief 2 nightly half C4/C5]. The first two are the high-value low-risk core; the two bracketed items are governed/staged decisions.
- **Phase-18 theme:** "data-collection integrity" is coherent and pairs naturally with Phase 17's consolidation. Supply-side items I'd fold in when the operator scopes Phase 18: D5 (suite runtime watch), the D14 polluter if 17-D.4 doesn't fully close it, and the deferred D10/D11 corpus-retention follow-ons. I'll draft the full Phase-18 scope when the operator opens it.

**No commission here.** RD QAs the returns; operator sequences and authorizes. My conditions C1-C5 bind whatever gets commissioned.
