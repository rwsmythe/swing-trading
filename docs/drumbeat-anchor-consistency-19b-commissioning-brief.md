# Commissioning Brief — 19-B: launch-context anchor consistency + lease-or-silent + guard (#5 root fix, RE-SCOPED)

**From:** CHARC. **To:** the Phase-19 orchestrator. **Arc:** 19-B ([`phase19-scope-charc.md`](phase19-scope-charc.md)). **Committed:** 2026-07-03.
**SUPERSEDES** [`drumbeat-false-red-root-fix-5-commissioning-brief.md`](drumbeat-false-red-root-fix-5-commissioning-brief.md) (`19185b04`, 2026-06-27) — its §2.1 "absolutize `config_path`" root fix is WITHDRAWN (it would anchor a worktree run to MAIN's artifacts, masking worktree isolation — worktree CODE writing MAIN artifacts is the poison, not the cure). Its §1.5 (RD HOME-vector) and §2.2 (both-signals guard) are CARRIED FORWARD below and remain load-bearing.
**§3 verdict:** SUB-TRIPWIRE (edits existing `monitoring/`/`pipeline/`/`config`/`web` modules; no schema / new module / dependency / standing process / carve-out). Guard + push semantics = RD's measurement/alarm lane → **RD plan-stage review + RD merge-blocking QA.**

## §0 References

- Old brief §0/§1/§1.5 (the confirmed cwd mis-rooting chain + RD's HOME-vector analysis) — read in full; the mechanism sections remain valid.
- **Anchor sites (CHARC-verified on disk 2026-07-03):** READ — the runner passes cfg-derived exports (`runner.py:1207,1361`; cwd-mis-rootable), and `compute_research_health(exports_root=None)` defaults from the artifact path (`research_health.py:1802-1805`); WRITE — `RESEARCH_HEALTH_ARTIFACT_PATH` is **`__file__`-anchored** (`swing/monitoring/stoplights.py:27-30` → the editable-installed MAIN repo; the LOCK-#4 shared reader/writer contract); PUSH — `_default_comms_root()` is **`__file__`-anchored** (`research_health.py:285-291` → MAIN's `comms/`), `push_research_health_red_to_rd` (`:351`), fired from `runner.py:1368`.
- **NEW EVIDENCE (RD, 2026-07-03, thread `drumbeat-liveness-false-red` — verified against production):** the 19-A/R4 SUITE runs fired **3 real 18-H.7 pushes** (drumbeat RED, `run id: unknown`) into RD's production inbox at 09:26:59 / 09:34:07 / 09:45:27Z — exactly the 3 fast-suite windows; NO `pipeline_runs` row after 118; production `latest.json` was GREEN throughout. One leaked push per suite run ⇒ likely ONE leaking test. Candidates: `tests/monitoring/test_research_health_rd_push.py` (drives the production helper; most sites pass a tmp `comms_root` — find the one that doesn't) / `tests/pipeline/test_step_research_health.py` (runner-wiring; monkeypatches). This is a TEST-ISOLATION LEAK spamming the T1 drumbeat-death alarm channel (alarm fatigue = the cry-wolf failure the channel exists to avoid).
- #5 history: `charc-state.md` board #2 + RD thread; the pinned offender = manual worktree launches (empty gitignored worktree exports).

## §1 The problem, restated (the anchor triangle)

A run's three artifact anchors DISAGREE: it **reads** exports config/cwd-rooted (→ a worktree's empty tree), but **writes** `latest.json` and **pushes** to comms `__file__`-rooted (→ MAIN production). A worktree/wrong-cwd launch therefore reads its own empty exports, concludes drumbeat-RED, and poisons MAIN's production artifact + spams RD's inbox. The suite evidence extends the class: even TESTS can reach the real push transport. Main-repo ops are clean (no false-RED since the worktree offender was pinned).

## §2 Fix requirements (design detail at writing-plans; requirements binding)

1. **ANCHOR CONSISTENCY (the root fix):** read, write, and push resolve from ONE root per launch context — the config-derived `project_root` — so a worktree run is FULLY self-contained (reads+writes+pushes its own tree) and a main run its own. **Constraint:** preserve the LOCK-#4 shared reader/writer contract — the 18-F stoplight reader and the 18-D writer must derive the path from the SAME source after the change (both config-derived, not one config- and one `__file__`-anchored), or reader/writer can diverge in a worktree with a custom config. Design this seam explicitly in the plan.
2. **LEASE-OR-SILENT (the push gate — RD's rule):** only a REAL leased run (a genuine `pipeline_runs` `run_id`) may post to comms; any unleased context (tests, standalone probes, worktree ad-hoc runs) logs a WARNING and posts NOTHING. This structurally kills the suite-spam class regardless of test hygiene. (The 3 leaked pushes were `run id: unknown` — exactly what this gate blocks.) The standalone `scripts/research_health.py` probe stays legitimate for its OWN tree's artifact write; it simply never pushes.
3. **GUARD (carried forward from the old brief §2.2, semantics unchanged):** write-nothing-on-suspicious-empty covering BOTH broken-context signals — (i) empty/absent engine-manifest dir where `_step_shadow_expectancy` just wrote one (the cwd/exports vector); (ii) an empty-DB read (zero detections/observations) where a live system has data (the HOME/db vector, old brief §1.5 — the root fix does NOT cover it; `db_path` is HOME-anchored). Broken-context ⇒ leave the prior `latest.json`, log WARNING. RD reviews the real-empty-vs-broken-context distinguisher.
4. **TEST-ISOLATION LEAK — pin + fix:** identify the test that fired the 3 real pushes (RD's timestamps = the reproduction ledger; one per suite run). Fix it AND add a structural defense so no test can ever hit the real `comms/` tree (e.g. an autouse fixture forcing the comms root to tmp for the whole suite — design call at writing-plans). Verify by running the fast suite and confirming ZERO new files under the real `comms/*/inbox/`.
5. **Residual sub-symptom pinning:** confirm lease-or-silent + anchor-consistency explain `run id: unknown`; exercise the divergent-config worktree case (the empty-db coverage symptom) against the guard.

## §3 Locks

Measurement COMPUTATION (`compute_research_health`) unchanged. Preserve: the single-sourced `write_research_health_artifact`; C-NH5 write-nothing-on-failure (the guard composes with it); the bare `step_guard` (O1); the read-only `mode=ro` conn; the 18-H.7 edge-trigger semantics (prior-overall read → write → push) for LEASED runs. NO schema (v31). The 19-A CALIBRATION-C logic (just merged, `fadc193d`) is untouched — same file, different region; rebase carefully.

## §4 Gates

1. **RD plan-stage review** (guard distinguisher + lease-or-silent + anchor-contract semantics — his T1 channel; post the plan pointer to rd after your plan QA).
2. Discriminating tests: a worktree-context run reads+writes+pushes ONLY its own root (MAIN untouched); an unleased context never posts; broken-context-empty ⇒ no write, prior `latest.json` preserved; genuine-empty ⇒ per RD's blessed semantics; the suite-run zero-real-comms check (§2.4).
3. review-strong to convergence + codex-auto-review; merged-head no-false-green; ruff.
4. **Operator witness:** a normal main-repo pipeline run → correct `latest.json`, no push spam; a deliberate worktree launch → NO main poison, NO RD post (the #5 repro turned green).
5. **RD merge-blocking QA** at the return; the ORCHESTRATOR posts the return report to `charc,rd` AFTER its QA (implementer never posts to directors).

## §5 Sizing + dispatch recommendation

Small-medium, design-forward (the anchor seam + the lease gate + the guard distinguisher). CHARC recommendation: **writing-plans on `implementer-opus-xhigh`** (real cross-module design: the LOCK-#4 seam, the lease-or-silent boundary), **executing on `implementer-opus-high`**. Orchestrator owns the final cell selections + announces before spawn.
