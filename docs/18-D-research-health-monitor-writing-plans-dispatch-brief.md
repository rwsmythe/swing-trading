# 18-D research-health monitor — WRITING-PLANS dispatch brief

**Audience:** a fresh Claude Code instance with NO prior conversation context, dispatched as the 18-D **writing-plans** implementer for the Swing Trading project (`c:\Users\rwsmy\swing-trading`).
**Phase:** copowers **writing-plans** ONLY (produce the implementation plan; do NOT write production code). Brainstorming is skipped — the design is locked by the commissioning brief, which is your binding spec.
**Expected duration:** one focused session (plan doc + adversarial Codex to convergence).

---

## §0 Read first (with rationale)

Read these before drafting anything. Ground every claim against the live code — do NOT trust this brief's paraphrases over what is on disk.

1. **`docs/data-collection-health-monitor-commissioning-brief.md` — THE BINDING SPEC.** RD→CHARC commissioning brief, CHARC-architecture-passed (§6.5). §1–§2 = the problem + probe set; §4 = the LOCKS; §6.2 = the architecture + the 7-check set; §6.3 = the cadence (script-first); §6.5 = the two binding writing-plans reinforcements. Your plan implements §6.2/§6.3/§6.5 for the **SCRIPT-FIRST** scope (see §2 below).
2. **`swing/monitoring/stoplights.py` — the LIVE 18-F contract you write FOR.** Import (never redeclare — single-source LOCK C1) the three constants `RESEARCH_HEALTH_ARTIFACT_PATH`, `RESEARCH_MONITOR_ID` (`"research_measurement"`), `RESEARCH_ARTIFACT_MAX_AGE_DAYS` (`7`). Read `read_validated_research_envelope` end-to-end: it defines the **5 false-green gates** your envelope must satisfy *by construction* (identity, valid `overall`, `overall==worst_of(checks)`, `generated_ts` present+parseable+not-future, age ≤ 7d) AND the **full per-check render schema** `_worst_check_severity` enforces (each check is a dict with non-empty str `key`, `status∈{green,yellow,red}`, non-empty str `summary`, `detail` None-or-str).
3. **`swing/monitoring/tool_health.py` + `scripts/tool_health.py` — the PRECEDENT to mirror.** `compute_tool_health(conn, *, cfg=None, prices_cache_dir=None, now=None) -> ToolHealthStatus` is the sibling shape. `ToolHealthCheck` / `ToolHealthStatus` show the frozenset `__post_init__` enum validation (rejecting grey), the `overall==worst_of(checks)` invariant, and `to_dict()` emitting the §3 envelope `{monitor, generated_ts, overall, checks:[...]}`. `scripts/tool_health.py` shows the read-only mode=ro connection + ASCII render + `--json`. Your `compute_research_health` / `ResearchHealthStatus` / `scripts/research_health.py` mirror these.
4. **`scripts/weekly_glance.py` — the integrity-superset precedent.** ASCII discipline, `total_unattributed` read, the trading-calendar / freshness idioms, the `mode=ro` connection pattern. The monitor is its integrity *superset*, not a replacement.
5. **The data anchors each check probes — ground each against the live schema + real emitter output** (memory `feedback_adversarial_review_verify_data_shapes`; Expansion #4 SQL-column verification):
   - check #1 `temporal_log_finiteness`: `pattern_forward_observations.ohlc_today_json` — see `swing/data/repos/pattern_forward_observations.py`, `swing/data/models.py`, `swing/data/migrations/0022_phase14_temporal_log.sql`. Reuse the shared finiteness predicate `swing/data/ohlcv_finiteness.py` (18-A) rather than re-implementing NaN/None detection.
   - check #2 `excluded_reason_breakdown`: read the engine's **`manifest.json`** — `research/harness/shadow_expectancy/{run.py,io.py}` + `research/method-records/shadow-expectancy-engine.md`. **Do NOT recompute attribution** (LOCK §4.2 — the synthetic-vs-production drift the program has been burned by). Verify the actual manifest keys on disk; do not assume.
   - checks #3/#5 trading-calendar + freshness: `swing/evaluation/dates.py` (`sessions_behind`, `last_completed_session`, `action_session_for_run`) — the same helpers 18-E uses.
   - check #5 `drumbeat_liveness`: newest-artifact age + `total_unattributed > 0` (the same `total_unattributed` signal `weekly_glance.py` + the engine emit).
   - check #7 `fetch_transport_health`: `yfinance_calls` (18-C) — `swing/data/repos/yfinance_calls.py`. **Transport indicator ONLY** (§6.2 #7 boundary): `status='success'` is transport success, NOT data usability; a stale `in_flight` row is unknown-not-hung; treat row counts as a sample/indicator, never a census; never alarm on a low count. #1 stays the usability authority.

If a read contradicts this brief or the spec, the **live code wins** — flag the discrepancy in your return report.

## §0 Skill posture

- **Invoke `copowers:writing-plans`** — it wraps `superpowers:writing-plans` + an adversarial Codex review run **to convergence** (zero new crit/major; the 5-round cap is suspended for this project — memory `feedback_codex_round_limit_suspended`). Codex transport is the WSL CLI fallback (memory `feedback_wsl_native_codex_invocation`); the MCP codex tools are dead in this extension.
- **Codex review tier: `review-fast`** (writing-plans/docs tier per `docs/implementer-dispatch-recipe.md` §3 — gpt-5.4-mini/low). If the `review-fast` profile is absent, omit `-p` and report it.
- **Persist each Codex round's RESPONSE** (verdicts/findings, including the final `NO_NEW_CRITICAL_MAJOR` line) to a gitignored on-disk file (e.g. `.copowers-findings.md`) so convergence is independently auditable at QA (memory `feedback_implementer_persist_codex_responses`).
- Do **NOT** invoke `superpowers:brainstorming` (spec is locked). Do **NOT** write production implementation code — this is the planning phase; the plan's TDD tasks are executed in a later dispatch.

---

## §1 Strategic context (compressed)

18-D is the last research-lane Phase-18 arc: a **read-only research data-collection-health monitor**. 18-F already shipped a GUI "Research monitor" stoplight that reads `exports/research/health/latest.json` and shows **grey until 18-D writes a conformant fresh envelope there**. Building 18-D's script-first half **lights that stoplight** and gives the RD a mechanized integrity check at spin-up (the defect that motivated this rode invisibly for 2+ days because RD only spins up ~weekly and the operator-facing surfaces showed all-clear). The monitor watches the **data-integrity layer** `weekly_glance.py` does not: non-finite OHLC, excluded-reason breakdown, coverage gaps, structural integrity, drumbeat liveness, candidate completeness, fetch-transport health.

## §2 Scope

**IN SCOPE — the SCRIPT-FIRST half ONLY** (CHARC: sub-tripwire, cleared to dispatch — §6.5):
- A pure **`compute_research_health(conn, ...) -> ResearchHealthStatus`** in `swing/monitoring/` (sibling of `compute_tool_health`), emitting the §3 envelope (`monitor="research_measurement"`, `overall=worst_of(checks)`, fresh `generated_ts`) with the **7 checks** of §6.2.
- **`ResearchHealthStatus` / `ResearchHealthCheck`** mirroring 18-E's `__post_init__` frozenset enum validation (`{green,yellow,red}`; **REJECT grey** — render-only, never monitor-emitted) — §6.5(a). This makes the emitter structurally incapable of a non-conformant envelope.
- **`scripts/research_health.py`** (mirror `scripts/tool_health.py`): opens its own `mode=ro` connection, prints the ASCII report (RD spin-up review), AND **writes the conformant envelope to `latest.json` on every run** — §6.3 (so the stoplight lights during the script-first phase).
- The `latest.json` write is **ATOMIC** — tmp + `os.replace` in the SAME directory (the `os.replace`-same-filesystem gotcha) — §6.5(b). Create the `exports/research/health/` parent dir if absent.

**OUT OF SCOPE (do NOT plan these):**
- The **nightly pipeline-step half** — DEFERRED to a fast-follow dispatch; it is a new standing process that gets its OWN CHARC sec-3 pass + the 17-B `step_guard` B-shape. Not now.
- **Amending `docs/research-director-watch-standard.md`** — RD's deliberate post-build action, not the implementer's.
- Any **DB write** — read-only `mode=ro`; the ONLY writes are `latest.json` + the ASCII report (an artifact write, same posture as the shadow-expectancy artifacts).
- **Forking the engine funnel/attribution** — read the manifest; never recompute.

## §3 Binding conventions + LOCKS (carry into the plan)

- **Read-only (LOCK §4.1):** open the DB `mode=ro`; never write the measurement DB.
- **Single source of truth (LOCK §4.2):** read the engine `manifest.json`; do NOT fork funnel/attribution logic.
- **ASCII output only (LOCK §4.3):** Windows cp1252 `UnicodeEncodeError` gotcha; assert via `text.encode("ascii")` in a test (Expansion #16). `weekly_glance.py` + `tool_health.py` already honor this.
- **No new dependency (LOCK §4.4):** stdlib `sqlite3`/`json`/`pathlib`/`os` + reuse of existing `swing.*` imports only. No pandas in the monitor module (mirror 18-E's lazy-import-the-readers discipline).
- **Import the 3 contract constants from `swing/monitoring/stoplights.py`** — never redeclare (single-source).
- **Transport-vs-usability boundary (§6.2 #7):** check #7 is a transport indicator; check #1 is the usability authority; the plan must keep them complementary and never let #7 substitute for #1.
- **The 5 false-green gates** the envelope must satisfy — guaranteed by construction via the `__post_init__` enum validation + `overall=worst_of(checks)` + a fresh non-future `generated_ts`.
- **Commits:** conventional (`feat(monitoring):`, `test(monitoring):`); **NO `Co-Authored-By`; NO `--no-verify`; NO amend.** TDD: failing test → minimal impl → pass → commit (the plan specifies these slices; execution is a later dispatch).
- **Frozen-clock convention (R2 rider):** any NEW test exercising date/session logic (`datetime.now`, `action_session_for_run`, `sessions_behind`, `generated_ts` staleness) MUST pin the clock via an injected `now`/frozen-clock fixture, not the live wall clock. `compute_tool_health`'s `now=` seam + `scripts/tool_health.py:_resolve_now` are the precedent.

## §4 What the plan must deliver

A writing-plans plan doc at `docs/superpowers/plans/2026-06-15-phase18-arc-d-research-health-monitor-plan.md` (or your dated equivalent), with:
- Per-task TDD slices (red test → minimal impl → commit) for: the two dataclasses + envelope; each of the 7 checks (each its own slice, with the discriminating test grounded in REAL schema/manifest shape — a test that fails the wrong implementation, per memory `feedback_regression_test_arithmetic`); the `compute_research_health` aggregator; the `scripts/research_health.py` script (ASCII + atomic `latest.json` write); the ASCII-encode assertion; an envelope-conformance test asserting the output passes 18-F's `read_validated_research_envelope` (round-trip: write `latest.json` → read it back through the real 18-F reader → assert it validates green/yellow/red, not grey).
- An explicit per-check **data-grounding note**: the exact table/column/manifest-key each check reads, verified against the live schema/emitter (cite the file:line you confirmed it at).
- A V1-simplification ledger (any stub/placeholder + its V2 dependency) per the banking discipline.
- The degradation contract per check (missing table → yellow "schema unavailable"; missing config input → green/"n/a"; missing operational data → red) mirroring 18-E's posture — state it explicitly per check.

## §5 Adversarial review (target + watch items)

Run `copowers:writing-plans`'s Codex chain (`review-fast`) to convergence. Watch items to pass to the review:
- Does every check's SQL/column/manifest-key match the LIVE schema/emitter (not a paraphrase)? (Expansion #4 + #2.)
- Does the envelope satisfy ALL 5 false-green gates by construction — including the consistency gate `overall==worst_of(checks)` and a non-future `generated_ts`?
- Is the transport-vs-usability boundary (#7 vs #1) preserved — #7 never alarms on a low/sampled row count, never substitutes for #1?
- Is every discriminating test arithmetically distinguishing (fails the wrong impl), per `feedback_regression_test_arithmetic`?
- Is the `latest.json` write atomic + same-filesystem, and does the round-trip test prove the 18-F reader validates the output?
- Is the manifest read defended against an absent/shape-drifted manifest (the engine may not have emitted one yet)?

## §6 Done criteria

- The plan doc is committed; the Codex chain reached convergence (`NO_NEW_CRITICAL_MAJOR`), with each round's response persisted to the gitignored findings file.
- Every check has a grounded data-shape note + a discriminating-test specification.
- Scope fences honored (script-first only; nightly + watch-standard amendment explicitly deferred/out).
- No production implementation code written (planning phase).

## §7 Return report (your final chat message — nothing else)

Produce a structured return report as your FINAL message (do NOT post to any mailbox — the orchestrator posts after QA; memory `feedback_implementer_never_posts_to_directors`):
1. **Plan doc path** + commit SHA(s).
2. **Per-check grounding table:** check key → table/column/manifest-key → file:line confirmed.
3. **Codex convergence:** rounds, final verdict line, path to the persisted findings file.
4. **Locks honored:** read-only / single-source / ASCII / no-dep / import-constants / transport-vs-usability — one line each.
5. **Open questions / discrepancies** found vs the spec or this brief (live-code-wins flags).
6. **V1-simplification ledger** (stub → V2 dependency).
7. **Anything you recommend the executing-plans dispatch watch for.**

## §8 If you get stuck

- Spec ambiguity you cannot resolve from the commissioning brief + live code → state the question + your recommended resolution in the return report; do NOT guess silently.
- WSL Codex unreachable / usage-capped → flag NOT-CONVERGED explicitly (never fabricate a convergence line); the orchestrator resumes the review.
- A data anchor (manifest key, column) not found on disk → STOP and report; do not invent a shape.
