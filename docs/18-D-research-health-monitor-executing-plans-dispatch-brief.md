# 18-D research-health monitor — EXECUTING-PLANS dispatch brief

**Audience:** a dispatched implementer (sub-agent via a `.claude/agents/implementer-*` cell) with NO prior conversation context.
**Phase:** copowers **executing-plans** — implement the merged plan task-by-task via TDD, then hand-run Codex (`review-strong`) to convergence. This arc is **measurement-core (RD merge-blocking)**; the locks below are binding.
**Expected duration:** one focused session (8 plan tasks, each a red→green→commit cycle; then the review loop).

---

## §0 Read first (in this order)
1. **`docs/implementer-dispatch-recipe.md`** — THE protocol (worktree, TDD, the WSL-Codex loop, the before-AND-after full-suite discipline, the return-to-orchestrator rule). Binding.
2. **`CLAUDE.md`** (repo root) — the project gotchas + conventions (you do NOT inherit them otherwise). Note especially the SQLite/`os.replace`-same-filesystem, the cp1252 ASCII-stdout crash, and the repo-reader-default-arg-vs-config gotchas.
3. **`docs/superpowers/plans/2026-06-15-phase18-arc-d-research-health-monitor-plan.md`** — **THE binding implementation spec.** Execute its 8 tasks EXACTLY (each carries its files, the failing tests with pre/post-fix arithmetic, the implementation sketch, and the acceptance + commit message). Do not redesign; if a task's anchor diverges from live code, STOP-and-ask (recipe §5).
4. **`docs/data-collection-health-monitor-commissioning-brief.md`** — the binding SPEC/LOCKS (§1-2 problem, §4 LOCKS, the §6 addendum, §6.5 CHARC reinforcements). CHARC sec-3 envelope pass CONFIRMED + C5 (script writes `latest.json`) APPROVED.
5. **Re-ground these against live code before editing** (line numbers drift): `swing/monitoring/stoplights.py` (the 3 contract constants + `read_validated_research_envelope`'s 5 gates you write FOR), `swing/monitoring/tool_health.py` + `scripts/tool_health.py` (the precedent), and each per-check data anchor the plan cites (`pattern_forward_observations.ohlc_today_json`, the shadow-expectancy `manifest.json`, `swing/evaluation/dates.py`, `swing/data/repos/candidates.py`, `yfinance_calls`).

## §0 Skill posture
- Execute the plan task-by-task via **TDD** (recipe §2): failing test → SEE it fail → minimal impl → SEE it pass → commit with the plan's task id.
- After all task-commits land, **run the FULL fast suite to GREEN BEFORE the Codex review** (recipe §2, the 18-F lesson) — fix any cross-cutting/global-invariant break first so the review converges on a green diff.
- Hand-run the **WSL-Codex adversarial review at the `review-strong` tier** (recipe §3) to convergence (`NO_NEW_CRITICAL_MAJOR`; the 5-round cap is suspended — run until zero-new). Persist EVERY round's verbatim response + your adjudication to a gitignored `.copowers-findings.md`.
- **Do NOT run `codex exec review` / the codex-auto-review A/B** — that is the ORCHESTRATOR's job (the built-in reviewer runs git, which cannot resolve the worktree `.git` under WSL). You run ONLY the hand-rolled `review-strong` loop.
- Return your report to the ORCHESTRATOR as your final chat message (recipe §4). Do NOT post to any role mailbox; do NOT run `role_mail.py`.

## §1 Scope
**IN — the SCRIPT-FIRST half ONLY:**
- `swing/monitoring/research_health.py` — `compute_research_health(conn, *, cfg=None, exports_root=None, manifest_dir=None, now=None) -> ResearchHealthStatus` + the 7 per-check helpers + the envelope dataclasses (`ResearchHealthCheck`, `ResearchHealthStatus`), per the plan Tasks 1-7.
- `scripts/research_health.py` — the operator probe (mirror `scripts/tool_health.py`): `mode=ro` connection, ASCII / `--json`, AND the ATOMIC `latest.json` write that lights 18-F's grey research stoplight, per plan Task 8.
- Tests under `tests/monitoring/` + `tests/scripts/`.

**OUT (do NOT implement):**
- The **nightly pipeline-step half** (deferred fast-follow; its own CHARC sec-3 pass + the 17-B `step_guard`).
- **Amending `docs/research-director-watch-standard.md`** (RD's deliberate post-build action).
- Any **DB write**; **forking the engine funnel/attribution**.
- **Diff fence:** touch ONLY `swing/monitoring/` + `scripts/` + `tests/`. **NO** `swing/data`, `swing/trades`, `swing/pipeline`; **NO** `swing/evaluation/dates.py` edit (the coverage logic is self-contained in the monitor module; `_NYSE`/`last_completed_session` are lazy-IMPORTED read-only, never edited); **NO** schema/migration; **NO** new dependency; **NO** `pyproject.toml` / `swing.config.toml`.

## §2 Binding constraints (RD merge-blocking, measurement-core — carry into every task)
1. **READ-ONLY (LOCK §4.1).** `compute_research_health` only READS the caller's connection; the script opens its OWN `mode=ro` URI connection. The ONLY writes are `latest.json` + the ASCII report (artifact writes — never the measurement DB). The plan's `test_compute_research_health_is_read_only` (drives the aggregator on a `mode=ro` connection) is the binding proof — it MUST pass.
2. **NO FUNNEL FORK (LOCK §4.2).** Checks #2/#5 READ the engine `manifest.json` via the 3-state `_read_newest_manifest` (absent / corrupt / shape-drift); never recompute attribution. Sum `funnel.per_hypothesis.*.excluded` + read `funnel.detection_level.unique_signals` / `funnel.unattributed` — nothing more.
3. **TRANSPORT-vs-USABILITY boundary (#7 vs #1) — RD-CONFIRMED.** `_check_fetch_transport_health` consumes `yfinance_calls.status` as a TRANSPORT indicator ONLY: exclude `in_flight`; `success` is transport-not-usability; it NEVER substitutes for #1. **`#7` is DETAIL-ONLY on a low sample — do NOT derive a COLOR from the row count on a sub-floor sample** (RD-confirmed: the brief §6.2 #7 LOCK is binding; a sparse-sample rate would false-alarm; the sample-gated-color is a DEFERRED V2). The observed count/tallies appear in the `detail`; the color stays green below the sample floor. `_check_temporal_log_finiteness` (#1) is the usability authority (RED on any non-finite). The plan's `test_transport_does_not_substitute_for_finiteness` is the load-bearing separation proof.
4. **ENVELOPE + the 5 false-green gates BY CONSTRUCTION.** `monitor="research_measurement"`, `overall=worst_of(checks)`, a fresh **aware-UTC** `generated_ts`. **IMPORT** the 3 constants (`RESEARCH_HEALTH_ARTIFACT_PATH`, `RESEARCH_MONITOR_ID`, `RESEARCH_ARTIFACT_MAX_AGE_DAYS`) from `swing/monitoring/stoplights.py` (LOCK C1 — never redeclare). The envelope must satisfy all 5 gates of `read_validated_research_envelope` (identity, valid overall, `overall==worst_of`, fresh non-future `generated_ts`, per-check render schema incl. non-empty `checks`). The plan's round-trip test (write `latest.json` → read back through the LIVE 18-F reader → assert validates, not grey) is the binding proof.
5. **CHARC reinforcements (binding).** (a) `ResearchHealthStatus`/`ResearchHealthCheck` MIRROR 18-E's `__post_init__` frozenset enum validation — REJECT `grey` (render-only, never monitor-emitted). (b) Write `latest.json` **ATOMICALLY** — tmp + `os.replace` in the SAME directory (the `os.replace`-same-filesystem gotcha).
6. **aware-UTC `generated_ts` is a DELIBERATE, tested divergence from 18-E's naive-local stamp** (the 18-F host-tz staleness gate). Do NOT "consistency-fix" it back to naive-local.

## §3 Verification (before you hand back)
- **BOTH full-suite runs** (recipe §2 + §4): `python -m pytest -m "not slow" -q` to GREEN BEFORE the Codex loop, AND again on the final post-convergence HEAD. Report the tail count read off the FINAL head (never carry a mid-work count forward).
- `python -m pytest tests/monitoring tests/scripts/test_research_health_script.py -q` — green.
- `ruff check swing/` — clean (no new violations in `swing/`).
- The plan's read-only proof + the 18-F round-trip proof + the no-measurement-chain-touch diff check (§Verification of the plan) — all satisfied.
- **The operator gate is a POST-RETURN orchestrator/operator step** (you cannot witness it from the worktree): the operator runs `scripts/research_health.py` against the LIVE `~/swing-data/swing.db` (where #1 MUST fire RED on the ~103 non-finite obs — the motivating-defect proof) + confirms the 18-F research stoplight flips grey→its true color in the browser. **In your return report, document the EXACT commands** (`PYTHONPATH=. python scripts/research_health.py` and `... --json`) so the operator gate is turnkey.

## §4 Dispatch metadata
- **Worktree:** `<repo>/.worktrees/phase18-arc-d-exec`, base = the `BASELINE_SHA` the orchestrator gives you in the spawn prompt (current `main` HEAD, which contains this brief + the plan). `git worktree add -b phase18-arc-d-exec .worktrees/phase18-arc-d-exec <BASELINE_SHA>`.
- **Codex tier:** `review-strong` (executing / production code — NEVER tier down). If the profile is absent, omit `-p` and report it.
- Leave the worktree intact; do NOT merge or push (the orchestrator rebases onto main + `merge --ff-only`).

## §5 Return report (to the ORCHESTRATOR — your final chat message; recipe §4)
- Per-task commits (SHA + task id) in shipped order; trailer-clean audit (`git log <base>..HEAD --format='%H%n%(trailers)'` → all empty).
- Final-head test count (the `pytest -m "not slow" -q` tail) + the `tests/monitoring`+`tests/scripts` result.
- Codex `review-strong` rounds + final verdict + the `.copowers-findings.md` path. (You did NOT run codex-auto-review — that is the orchestrator's A/B.)
- Each §2 constraint stated as honored-on-disk (file:line): read-only, no-funnel-fork, transport #7 detail-only, envelope+5-gates, the 2 CHARC reinforcements, the diff fence.
- The turnkey operator-gate commands (§3).
- Deviations / V1 simplifications (with V2 dependency) / anything flagged-not-fixed.

## §6 If you get stuck
- A plan anchor (column / manifest key / signature) doesn't match live code → STOP-and-ask (recipe §5); do not work around it.
- A fix would need a schema/migration/new dependency the brief didn't authorize → STOP (tripwire; route up).
- WSL Codex unreachable / usage-capped → flag NOT-CONVERGED explicitly (never fabricate a convergence line); the orchestrator resumes the review.
- A forbidden commit trailer slipped in → STOP-and-flag (do NOT amend / `--no-verify`); the orchestrator resolves it at merge.
