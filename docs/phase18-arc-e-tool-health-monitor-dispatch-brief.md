# Phase 18 Arc 18-E — operational tool-health monitor (commissioning brief + architecture pass)

**Authored:** 2026-06-14 by CHARC. **Roadmap:** `docs/phase18-todo.md` §18-E. **Tripwire: REAL — new standing process + a new `swing/` module.** A genuine §3 crossing, so this brief carries the architecture pass. **Cycle:** writing-plans → executing (NO brainstorm — the design is settled by mirroring `weekly_glance.py`/`harness_probe.py` + this pass). **Dispatch:** via a library cell (sub-agent model proven); orchestrator selects the cell per the rubric (writing-plans ~opus-xhigh, executing ~opus-high/sonnet-high — backend, no measurement-chain) + announces.

**Sequencing:** 18-E is the FIRST of the 18-E→18-F pair. It ships first; 18-F (the GUI stoplights) consumes 18-E's `compute_tool_health(conn)` function + the JSON envelope this brief locks. The 18-F brief is authored AFTER 18-E ships (against the concrete shipped contract).

## 1. Mandate
Operational early-warning is piecemeal: a dying 7-day Schwab token, a heartbeat-stalled pipeline run, a stale archive — each visible only if the operator happens to look at the right surface. The same "rode invisibly" failure that motivated 18-A/18-D applies operationally. Add an **aggregating, read-only roll-up of EXISTING signals** — the data-collection-ENABLING subset — so the health of the collection apparatus is one glance (CLI now; the 18-F stoplight next). It is the operational sibling of the RD's 18-D research monitor and of `harness_probe.py` (hygiene) — three single-purpose probes over distinct domains, aggregate-not-duplicate.

## 2. The architecture pass — design (settled)
**Form (mirrors `weekly_glance.py`):** a read-only probe. BUT, because 18-F's tool-health stoplight computes at render (the cash-badge precedent — see §18-F), the aggregating LOGIC must be importable by the web, not buried in a `scripts/` file. So:
- **A new `swing/monitoring/` package** (operational monitoring — distinct from `diagnostics/` one-offs and `metrics/` dashboard surfaces; it will also house 18-F's stoplight aggregation, making `swing/monitoring/` the home for the whole health/stoplight concern). New module `swing/monitoring/tool_health.py` with **`compute_tool_health(conn) -> ToolHealthStatus`** (the envelope, §3) — pure, read-only, takes a connection, returns the status. This is the function 18-F calls at render.
- **A thin CLI/script surface** for the operator: ASCII `ATTENTION (N)` / `all clear` output (mirror `weekly_glance.py`) PLUS a `--json` flag emitting the §3 envelope. Whether the surface is a `swing` CLI subcommand (`swing tool-health`) or a `scripts/tool_health.py` probe is the writing-plans' call (lean: a `scripts/` probe mirroring `weekly_glance.py`/`harness_probe.py`, importing `swing.monitoring.tool_health` — keeps the operator-probe family consistent + avoids growing `cli.py`, the largest module).

**NO nightly pipeline step** (unlike 18-D): the compute is cheap + all-DB-backed, so the stoplight runs it live at render. No `step_guard`, no drumbeat coupling. (If a future need for a persisted nightly snapshot appears, that's a separate arc.)

**Reuse, don't reimplement (the premise-check discipline):** every signal already exists. The monitor AGGREGATES; it adds NO new instrumentation and NO new schema. Cite + reuse the existing logic; the writing-plans pins exact file:line.

## 3. The shared monitor-status JSON envelope (CHARC-OWNED CONTRACT — locked here)
This is the interface 18-F consumes and that **18-D MUST conform to** when RD builds it (RD's 18-D brief leaves the JSON shape an open question — §3.3 — so the envelope is undefined anywhere; defining the stoplight-consumption contract is harness architecture = CHARC's). **Coordination:** when RD commissions 18-D, its written status artifact emits THIS envelope. Flag to RD via the operator.

```json
{
  "monitor": "tool_health",          // identifier; "research" for 18-D
  "generated_ts": "2026-06-14T20:31:00",   // ISO 8601 naive (project convention)
  "overall": "green",                 // "green" | "yellow" | "red" — worst-of checks
  "checks": [
    {
      "key": "schwab_token_ttl",      // stable check id
      "status": "yellow",             // "green" | "yellow" | "red"
      "summary": "Schwab token expires in 2 days",   // one-line ASCII
      "detail": "refresh by 2026-06-16; swing schwab setup"  // optional, for the drill-down
    }
  ]
}
```
- `overall` = worst of `checks` (red > yellow > green). The stoplight color = `overall`.
- **`grey` is NOT a monitor-emitted value.** It is purely an 18-F RENDER state for a MISSING artifact (research stoplight before 18-D ships). A monitor always emits green/yellow/red.
- ASCII-only in every string (the cp1252 gotcha). `summary`/`detail` are operator-facing.
- The `ToolHealthStatus` dataclass mirrors this 1:1 (`overall`, `checks: list[ToolHealthCheck]`); `--json` serializes it; `compute_tool_health` returns it.

## 4. Scope — the check set (the data-collection-ENABLING subset)
Exactly three signal families (per the todo scope — broader operational coverage, perf/recon/cash, is Phase 19+; those don't block data COLLECTION). Each maps to one or more `checks` entries:

1. **Pipeline-run health** — reuse the documented two-read pattern (the `ORDER BY started_ts DESC` gotcha): the most-recent COMPLETED run's `finished_ts` (data-freshness) AND the most-recent STARTED run's state (what's happening now). Checks: (a) newest successful `complete` run older than ~1 session → yellow, ~2+ → red (collection not refreshing); (b) a currently-running run whose heartbeat is stale (wedged) → red; (c) recent `failed`/non-complete runs by count → yellow. Locate the `pipeline_runs` read helpers + the heartbeat-staleness convention at writing-plans (NOT `swing/data/repos/pipeline_runs.py` — that path doesn't exist; find the actual reader).
2. **Schwab token TTL** — REUSE the existing days-remaining + severity logic (`swing/web/view_models/schwab.py` / `swing/cli_schwab.py` / `swing/integrations/schwab/auth.py`; `swing schwab status` already surfaces days-remaining with severity escalation, and the 7-day TTL gotcha). Map its severity tiers → green/yellow/red. Do NOT re-derive TTL math. (If no Schwab client is configured, the check is green/"n/a" — absence of Schwab is not a tool-health failure.)
3. **Data freshness** — (a) OHLCV archive: newest archived bar / meta vs the last completed session (reuse the archive meta + the session-anchor helper — the `action_session`/`last_completed_session` directionality gotcha; use the WRITER's anchor); (b) weather: `swing.data.repos.weather.get_latest(conn).run_ts` vs the last session (the weather-keyed-by-`data_asof_date` gotcha). Stale by >1 session → yellow, >2 → red.

**Thresholds:** calibrate against the EXISTING precedents (the schwab severity tiers; the session-anchor helpers) — the writing-plans pins exact cutoffs as module constants (the `weekly_glance.py` `T1_MAX_AGE_DAYS` pattern). Both-ways regression arithmetic where a threshold flips a color.

## 5. LOCKS
1. **Read-only.** Open the DB `mode=ro` (`file:{db}?mode=ro`, `uri=True`) — `weekly_glance.py` is the precedent. NEVER writes the DB. `compute_tool_health(conn)` accepts a caller's connection (the web passes its own); the CLI opens its own `mode=ro`.
2. **Aggregate, don't instrument — NO new schema, NO new signal source.** Every datum is read from an existing table/artifact. If a signal isn't already collected, it is OUT of 18-E (not a new instrument).
3. **Reuse, don't fork.** Reuse the schwab-severity + session-anchor + pipeline-two-read logic; do NOT reimplement them (the synthetic-vs-production drift family). Cite the source; the writing-plans grounds the exact anchors.
4. **stdlib only, NO new dependency** (`sqlite3` + `json` + `dataclasses` + `pathlib` + `datetime`, as `weekly_glance.py`). **ASCII output only** (the cp1252 `UnicodeEncodeError` gotcha — every `summary`/`detail`/print).
5. **The envelope (§3) is the locked contract.** `compute_tool_health` returns it; `--json` serializes it; 18-F + 18-D consume it. A `ToolHealthStatus`/`ToolHealthCheck` dataclass pair with `__post_init__` frozenset validation of `overall`/`status ∈ {green,yellow,red}` (the `Literal`-not-runtime-enforced gotcha).
6. **No measurement-chain touch.** 18-E only READS; it imports no measurement-write path and changes nothing the pipeline/evaluation computes. (Not measurement-core — so RD is FYI, not merge-blocking; see §7.)

## 6. Tripwire / placement
New standing process (a probe the operator + 18-F rely on) + a new `swing/monitoring/` package → CHARC architecture pass, carried by this brief (by construction). No new schema, no new dependency, no new pipeline step, no `swing/trades` or `swing/data` carve-out (the module is a new read-only `swing/monitoring/` package; it imports repos read-only). Default phase-isolation posture intact.

## 7. Gate
**Two-eye + operator** (18-E is operational/CHARC-lane, NOT measurement-core — no RD merge-block): **orchestrator QA-against-disk** + **CHARC** (the envelope contract honored; read-only/mode=ro; reuse-not-reimplement; ASCII; no-new-schema/instrument; the `swing/monitoring/` placement) + **operator** (the CLI output is operator-facing — a quick witness of the ASCII report against the live DB is the operator gate). **RD = FYI** (the envelope §3 is the contract 18-D conforms to — RD reviews the shape, advisory, not blocking). No browser gate (18-E is backend; the browser gate lands at 18-F). No-false-green merged-head fast-suite re-run + ruff before close.

## 8. Return report
The ORCHESTRATOR posts to `charc, operator` (+ `rd` FYI) after its QA (the implementer reports up to the orchestrator; never a director inbox — `feedback_implementer_never_posts_to_directors`). Itemize: the `swing/monitoring/` module + the CLI/script surface; the three check families + their reused sources (file:line) + thresholds; the §3 envelope conformance (the dataclass + `--json` + frozenset validation); the read-only/mode=ro + stdlib + ASCII locks honored on disk; the `compute_tool_health(conn)` signature (18-F's consumption point); Codex rounds + verdict; the sub-agent dispatch notes.

---

## 9. Writing-plans ratification (CHARC architecture seat, 2026-06-14)
Plan reviewed on disk (branch `phase18-arc-e-plan`, `docs/superpowers/plans/2026-06-14-phase18-arc-e-tool-health-monitor-plan.md`, `7004a63f`; 6-round Codex-converged — the MAJOR cascade was a legitimate tz-correctness chain, not churn; orchestrator QA PASS). **One touch-set extension RATIFIED; plan CLEARED from the CHARC seat. Executing = GO on operator authorization.**

**RATIFIED — `sessions_behind(reference, candidate) -> int` added to `swing/evaluation/dates.py`** (beyond the brief's `swing/monitoring/` + `scripts/` set). ACCEPT: the CORRECT architectural home — Codex R2-MAJOR forced pandas OUT of the monitor's own code, and NYSE session arithmetic belongs in the canonical session module that already owns `_NYSE`; this keeps the monitor stdlib + no-pandas (honoring LOCK #3 reuse + #4 no-new-dep) and is a POSITIVE divergence (cleaner than the brief presumed). **Sub-tripwire** — a pure additive function in an EXISTING module; `swing/evaluation/` is NOT under the phase-isolation read-only lock (that's `swing/trades` + `swing/data` only); no schema, no new dependency (reuses `dates.py`'s existing `exchange_calendars`/pandas), no standing process, no measurement-chain touch. Verified additive on the plan (no existing `dates.py` function changed). The orchestrator correctly routed it up (a scope extension, even sub-tripwire — the swimlane working).

**Refinements concurred (all correct):** OHLCV freshness = newest `*.parquet` mtime = WRITE-recency (a V1 simplification honoring aggregate-don't-instrument; a bar-currency V2 needs instrumentation out of scope) · weather freshness keyed on `asof_date` not `run_ts` (the gotcha) · the LOCK-#4 reconciliation (the monitor's OWN code is stdlib + no-pandas; reusing existing-dep helpers via lazy import is reuse-not-fork — my "stdlib only" intended "no NEW dependency", correctly read) · the optional-degrade signature `compute_tool_health(conn, *, cfg=None, prices_cache_dir=None, now=None)` preserves the locked bare-call `compute_tool_health(conn)`.

**Executing-gate conditions (CHARC verifies on the SHIPPED DIFF; two-eye + operator, no browser gate):**
- **C-E1** — `sessions_behind` purely additive in `dates.py` (no existing function changed), reuses `_NYSE` (no forked calendar), correct session/tz handling (the Codex tz-chain).
- **C-E2** — the monitor imports NO pandas at module top; lazy-imports `dates.py`/`cli_schwab` inside the check functions; `mode=ro`; no DB write anywhere.
- **C-E3** — the §3 envelope honored 1:1 (frozenset-validated `ToolHealthStatus`/`ToolHealthCheck`; `monitor="tool_health"`; `overall`=worst-of; `grey` rejected at construction; the bare-call `compute_tool_health(conn)` preserved).
- **C-E4** — ASCII (the subprocess-through-PowerShell encoding test present); the freshness `summary`/`detail` honestly state WRITE-recency (so the operator + the 18-F drill-down aren't misled into reading bar-currency); mtime tz-correct (the host-local trap).
- **C-E5** — no new schema, no new dependency, no measurement-chain touch, no `swing/trades`/`swing/data` carve-out. RD = FYI (the envelope is already conformed 1:1). Operator CLI witness of the ASCII report against the live DB.
