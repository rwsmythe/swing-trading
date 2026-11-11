# D101 rider -- a per-run detection-count check in `research_health` (CHARC, 2026-11-11)

**Commissioned by the operator 2026-11-11** ("all 4 items are a go", item 2, ahead of the queue; the orchestrator's R2). **Owner:** CHARC (register row D101). **Dispatcher:** the orchestrator. **Cell:** `implementer-opus-high` (settled design; one check in a seven-check monitor with an established calibration pattern). **Worktree:** `.worktrees/d101`, branch `d101` from `main`. Independent of the SG arc; may run in parallel (different files). No plan stage: executing directly on this brief.

## 1. The defect

`swing/monitoring/research_health.py` carries a CUMULATIVE `detection_count` (7,985 at the 10-29 read) and no per-run count, so a nightly whose `pattern_detect` step raised and wrote ZERO `pattern_detection_events` over a non-empty pool reads GREEN (runs 201 and 202, 2026-10-28/29; the cap episode, `20261029T020502Z`). D100 (the step's raise path leaves no `warnings_json` entry) is the other half and is NOT this rider.

## 2. The check (one task, TDD)

- A new read-only check in the existing style (the seven checks' envelope, severity vocabulary and `latest.json` contract are UNCHANGED): **AMBER when the latest COMPLETE pipeline run whose evaluation has a non-empty `aplus`-or-`watch` candidate pool has zero `pattern_detection_events` for that run.** GREEN otherwise; the empty-pool night is GREEN with its reason in the envelope (gotcha #27: an empty pool is reported, never silent).
- Join by the run's own ids (`pipeline_runs.evaluation_run_id` -> `candidates.evaluation_run_id`; detections by their run/evaluation key as the table defines it, READ at the schema, not assumed). Two-read pattern for "latest complete" (the most recent COMPLETED row, never `ORDER BY started_ts DESC` alone).
- **Baseline run 203** (the first post-fix night, 110 detections on 22 watch names); the check carries no count threshold, only zero-vs-non-zero.
- Discriminators RED first, seeded from the LIVE shape (run 201's: pool 20 watch, 0 detections; run 203's: 22 watch, 110): (1) run 201 shape -> AMBER with the run id and pool size in the envelope; (2) run 203 shape -> GREEN; (3) empty pool -> GREEN with the reason; (4) a RUNNING newer run does not mask a completed older one's reading; (5) the stoplight provider surfaces the AMBER on the topbar through the existing aggregator (no new base-VM field; the context-processor path).
- `scripts/research_health.py` and the nightly step need NO change if the check joins the existing list; if a signature moves, say so in the return report.

## 3. Locks

Monitor-only: `swing/monitoring/research_health.py` and its tests; the stoplight provider only if the check needs a new mapping. No schema, no `swing/data`, no `swing/trades`, no `swing/pipeline`, no dependency. Read-only connections (`mode=ro`).

## 4. Gate

Reviewer A to convergence (`strong`); Reviewer B at the orchestrator's seat; merged-head fast suite green and READ; `ruff check swing/`. Operator witness after the merge: `python scripts/research_health.py` on the live DB prints the check GREEN with run 209's reading; one SQL `mode=ro` read of the latest complete run's detection count beside it.
