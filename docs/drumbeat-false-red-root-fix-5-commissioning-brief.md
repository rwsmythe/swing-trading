# Drumbeat False-RED Root Fix (#5) — Commissioning Brief

> **SUPERSEDED 2026-07-03 by [`drumbeat-anchor-consistency-19b-commissioning-brief.md`](drumbeat-anchor-consistency-19b-commissioning-brief.md) (Arc 19-B).** The §2.1 absolutize-`config_path` root fix is WITHDRAWN (wrong root — it would anchor a worktree run to MAIN's artifacts, masking worktree isolation). §1.5 (HOME-vector) + §2.2 (both-signals guard) carry forward and remain load-bearing — the 19-B brief incorporates them by reference. Do NOT dispatch from this brief.

**Owner/author:** CHARC. **Date:** 2026-06-27. **Status:** COMMISSIONED.
**Context:** **#5** — the recurring `drumbeat_liveness` false-RED + the poisoned production `research_health/latest.json` (the 18-F stoplight + 18-H.7 push source). RD-flagged (thread `drumbeat-liveness-false-red`); CHARC-diagnosed on disk 2026-06-27.
**§3 verdict:** **SUB-TRIPWIRE** (edits existing `web/`/`config`/`runner` modules; no schema / new module / dependency / standing-process / `swing/trades`|`swing/data` carve-out). The DEFENSIVE GUARD is a research-health **monitor semantics** change → **RD reviews the guard semantics (merge-relevant, RD's measurement lane).** CHARC commissions; the operator §5.10-witnesses. GO.

---

## 0. The CONFIRMED mechanism (CHARC, verified on disk 2026-06-27)

A pipeline run launched from a cwd ≠ the repo root mis-roots the **project-internal** config paths, and that alone produces the drumbeat false-RED + the poisoned `latest.json`:

1. CLI `--config` defaults to the **relative** `"swing.config.toml"` (`swing/cli.py:206`); the web stores `cfg_path` as-is (`swing/web/app.py:618`).
2. `/pipeline/run` spawns the subprocess with `--config str(cfg_path)` and **NO `cwd=`** (`swing/web/routes/pipeline.py:133,141-146`) → the child inherits the **web server's cwd**.
3. `config.load()`: `project_root = config_path.parent.resolve()` (`swing/config.py:635`) → a *relative* path resolves against **cwd**. cwd ≠ repo root → wrong `project_root`.
4. `_resolve_path` anchors only `data/`, `exports/`, `reference/` to `project_root` (`swing/config.py:609,629`). So **`exports_dir` MIS-ROOTS** to an empty dir; **`db_path` (`swing-data/…`) stays HOME-anchored — CORRECT.**
5. `_step_shadow_expectancy` writes the engine manifest to the mis-rooted `exports_dir/research`; `_step_research_health` reads that same empty dir (`swing/pipeline/runner.py:1207,1361`) → drumbeat "no engine artifacts" **FALSE-RED** → it writes that false-RED into the **repo-anchored** `latest.json` → **POISONS the production artifact.**

## 1. The CORRECTION to RD's diagnostic (verified on disk — fold into RD's re-examination)

RD's thread says the broken context "mis-roots the ENTIRE cfg — BOTH `db_path` AND `exports_dir`." **The DB half is wrong:** `db_path = "swing-data/swing.db"` is HOME-anchored (it doesn't match `data/`/`exports/`/`reference/`), and the research-health conn (`runner.py:1351` `cfg.paths.db_path.as_uri()`) reads the correct DB regardless of cwd. Consequences:
- The **exports** mis-rooting FULLY explains the **drumbeat #5 false-RED + the poisoned `latest.json`** (confirmed; this fix targets it).
- RD's **DB-side symptoms** — "empty `pattern_detection_events`", "run id: unknown", "no run-row in live `pipeline_runs`" — are **NOT explained** by this mechanism (the DB conn is correct; `_step_research_health` is called `run_id=lease.run_id`, a real int). **Routed to RD to re-examine against the raw run evidence** — it may identify (a) the SPECIFIC recurring broken launch path (the intermittency + the db-symptoms suggest the recurring offender may be a NON-web path — the nightly/scheduled launch or the standalone `scripts/research_health.py`), and (b) a possible separate sub-bug to fold into this fix.

## 1.5 RD re-examination (2026-06-27) — the HOME-vector + the both-signals guard (LOAD-BEARING for writing-plans)

RD owned the db-correction + grounded the db-symptoms (read-only on disk): `_check_coverage_gaps` reads `pattern_detection_events` via the CONN (`research_health.py:1138-1148`, no WHERE) → "no mature detections" = the conn read an EMPTY db; the RED push fires ONLY from the leased `_step_research_health` (`runner.py:1368`, `run_id=lease.run_id`). **The residual vector is HOME, not cwd:** `db_path` is home-anchored → cwd-INDEPENDENT but HOME-DEPENDENT. A run launched with a DIFFERENT `HOME`/`USERPROFILE` (a scheduled task, a service account, an elevated/other-user shell) resolves `home/swing-data/swing.db` to a DIFFERENT (empty/fresh) db → explains ALL the db-symptoms at once: empty per_det → coverage "no mature detections"; the lease acquired in the empty db degrades → "run id: unknown"; the run-row lands in the wrong-HOME db → missing from the live `pipeline_runs`. A scheduled/service launch typically ALSO carries a wrong cwd → the exports/drumbeat half. So **the OFFENDER is NOT the web-spawn** (the web runs in the operator's session = correct HOME; it would show ONLY the cwd/exports half, and only if its cwd were wrong). The scattered RED times (08:12/16:34/06:18/17:00/03:38 — not a fixed cron) argue an interactive-but-wrong-environment launch; **the operator identifies which launch path he used on those runs — the fastest pin.**

**THE LOAD-BEARING CONSEQUENCE (writing-plans):** the §2.1 ROOT fix (absolutize `config_path`) fixes the cwd/exports/drumbeat half but does NOT fix the HOME-driven empty-db/coverage half — `db_path` is HOME-anchored, NOT `config_path`-anchored. **So the §2.2 GUARD is the ONLY protection for the db-half.** The guard MUST detect a broken-context EMPTY-DB read (zero detections/observations where the live system has data), NOT just the empty-EXPORTS read — **scope the guard to BOTH empty-context signals.** (Once the operator pins the offending launch path, a launcher fix — force the correct HOME/cwd — may be added; that is the only thing that PREVENTS the wrong-HOME db write, since the code can't override the process HOME.)

## 2. Scope — the root + guard fix

### 2.1 ROOT FIX — make `project_root` launch-context-INDEPENDENT
The mis-rooting is a *relative* config_path resolving `project_root` against the wrong cwd. Make the config path ABSOLUTE before any launch-context-sensitive resolution:
- **Web-spawn (confirmed vulnerable):** absolutize `cfg_path` at the web layer (`app.state.cfg_path = cfg_path.resolve()` at startup, when the cwd is the repo root) so the subprocess gets an **absolute `--config`** → `project_root` correct regardless of the subprocess's cwd. (And/or pass `cwd=<config-file-parent>` to `Popen` as a belt — the implementer picks; an absolute `--config` is the cleaner primary.)
- **Cover the OTHER launch paths:** verify whether the nightly/scheduled launch + the standalone `scripts/research_health.py` are also launch-context-sensitive (per §1 — the recurring broken runs may be a NON-web path). Ensure `project_root` is launch-context-independent across **ALL** pipeline entry points (a robust resolution at the CLI entry / `config.load()`, OR each launcher passing an absolute config / a correct cwd). **Ground the actual recurring broken path against RD's re-examination at writing-plans.**
- **Discriminating test:** a pipeline launched from a NON-repo cwd with the relative config resolves `exports_dir` (+ the project-internal paths) to the REPO root, NOT the cwd.

### 2.2 DEFENSIVE GUARD — write-nothing-on-suspicious-empty (RD-semantics-reviewed)
`_step_research_health` (+ the standalone `scripts/research_health.py`, single-sourced) MUST NOT overwrite a good `latest.json` with a suspicious all-empty/degraded status. **RD's exact concern: the guard must reliably DISTINGUISH a genuinely-empty state from a broken-context empty READ.** Direction: treat a broken-context read as **write NOTHING** (leave the prior `latest.json`) + log a WARNING, on EITHER suspicious-empty signal (per §1.5 — the guard covers BOTH because the root fix does not cover the HOME/db half): **(i)** the engine-manifest dir (`exports_root`) is empty/absent where the just-run `_step_shadow_expectancy` should have written one (the cwd/exports vector), AND **(ii)** the DB read is empty (zero detections / observations) where the live system has data (the HOME/db vector). Composes with the existing C-NH5 write-nothing-on-failure. **RD reviews the SEMANTICS (real-empty vs broken-context) — merge-relevant.** Even after the root fix lands, the guard is belt-and-suspenders so a future mis-root can never re-poison the production artifact.

## 3. §3 / locks

- SUB-tripwire (web/config/runner edits). The **root fix is config-path-resolution** (web/pipeline layer) — **measurement-NEUTRAL** (it makes the EXISTING-correct resolution robust against a wrong cwd; it changes no measurement value). The **defensive guard** is a **monitor-write-decision** change → RD reviews the semantics.
- The measurement COMPUTATION (`compute_research_health`) is UNCHANGED. Preserve: the single-sourced `write_research_health_artifact`; the C-NH5 write-nothing-on-failure; the bare `step_guard` (O1 ruling); the read-only `mode=ro` conn.

## 4. Gates

- Root fix: the §2.1 discriminating non-repo-cwd test. Guard: a test (broken-context-empty → NO write + prior `latest.json` preserved; genuine-empty → the correct behavior per RD's semantics).
- **RD reviews the defensive-guard SEMANTICS** (the real-empty-vs-broken-context distinguisher) — merge-relevant; RD also feeds back its db-symptom re-examination (the actual broken path / any sub-bug) at writing-plans.
- **Operator §5.10 witness:** a normal-launch pipeline run → `latest.json` correct, no false-RED (+ if reproducible, a broken-context launch → the root fix yields a correct resolution, and/or the guard writes nothing rather than poisoning).
- review-strong + codex-auto-review; merged-head no-false-green.

## 5. Dispatch recommendation

- **Implementer cell:** `implementer-opus-high`. Rationale: config-path resolution across launch paths + a monitor write-guard with a real-vs-broken-context distinguisher — careful, but not measurement-computation-core (not `-max`); richer than mechanical (above `-sonnet`).
- **Orchestrator:** Opus xhigh. Worktree-isolated.

## 6. Return report

**The ORCHESTRATOR posts the return report to `charc` + `rd` (the guard-semantics review) + `operator` fyi AFTER its QA.** CHARC code-QAs the root fix (launch-context-independence) + the guard on disk; **RD reviews the guard SEMANTICS (merge-relevant)** + confirms its db-symptom re-examination is reconciled; the operator's §5.10 witness is binding before merge.
