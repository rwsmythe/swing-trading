# Phase 5 — Configuration Page for Operator-Tunable Settings — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute `docs/superpowers/plans/2026-05-01-configuration-page-plan.md` end-to-end. The plan is committed at HEAD `e8c6396` after 5 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR` in writing-plans dispatch; design decisions are locked; task partitioning is fixed. This dispatch ships shipped code: ~75 new tests, baseline 1381 → ~1450, ~11 task groups across persistence layer + override-precedence + validation + web routes + template + CLI + nav.

**Expected duration:** ~6-10 hours (full day) — plan complexity is moderate; per-task TDD discipline + 2-5 Codex review rounds + operator-witnessed verification gate add overhead.

**Dispatch type:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` + adversarial Codex review).

---

## §0 Read first

Read these in order before executing:

1. **`docs/superpowers/plans/2026-05-01-configuration-page-plan.md`** — THE PLAN. Source of truth for task partitioning, per-task acceptance criteria, test specifications, file paths. ~2816 lines; budget 30-45 minutes for thorough read. Do NOT skim — Codex review surfaced 4 rounds of refinement; the per-task TDD specifications encode that refinement and must be followed exactly.

2. **`docs/phase5-configuration-page-writing-plans-brief.md`** — the brief that drove the plan. Locked decisions (§2), out-of-scope items (§3), binding conventions (§4), adversarial-review watch items (§6). The plan IMPLEMENTS this brief; if you find a divergence, the plan is the implementation contract — but surface the divergence in your return report.

3. **`CLAUDE.md`** at repo root — gotchas to pre-empt:
   - `os.replace` cross-device-link (atomic write tempfile MUST be in dest dir).
   - HTMX `<tr>`-leading `makeFragment` pathology (config form is fieldset-based; soft-warn confirm fragment must NOT lead with `<tr>`).
   - HTMX OOB-swap partial drift (use `{% include %}` to share partials).
   - `base.html.j2` 5-VM rule (the plan determined the case is STATIC NAV LINK; no propagation needed for the link, but `ConfigPageVM` MUST include the existing banner-guard fields per the new "VM-inheritance audit dimension" lesson — see plan Task 4.0).
   - Starlette `TemplateResponse(request, "name", {...}, status_code=...)` signature.
   - TestClient lifespan: `with TestClient(app) as client:` for any route test.

4. **`docs/orchestrator-context.md`** — focus on:
   - §"Currently in-flight work" (HEAD context).
   - §"Binding conventions" — 4-tier commit-message convention; subject-only ERE grep observable verification (`git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'`); ruff baseline 91; no-amend; no Claude footer.
   - §"Anti-patterns to avoid".
   - §"Lessons captured" — the most-recent two are this dispatch's predecessors:
     - Brief-speculation discipline (verify assertions empirically before relying on them; the plan already corrected the brief's stale field-path claims — read plan §A and §C for the canonical paths).
     - New-VM existing-field inheritance (`ConfigPageVM` must include all base-layout-dereferenced fields with safe defaults).

5. **`swing/config.py`** — verify import-time caching at the 2 sites the plan identified (`swing/cli.py:30` → `ctx.obj["config"]`; `swing/web/app.py:156` → `app.state.cfg`). The plan introduces `swing/config_overrides.py:apply_overrides(base_cfg) -> Config` returning a NEW Config via `dataclasses.replace`. Wired into all 27 cfg-reader sites + `swing/pipeline/__init__.py:run_pipeline(...)` wrapper.

6. **`swing.config.toml`** — full read. `risk_equity_floor = 7500.0` is at line 22; `chase_factor` and `chart_top_n_watch` field paths are confirmed in plan §A.

7. **`swing/web/templates/partials/soft_warn_confirm.html.j2`** — canonical pattern; the plan adapts this for config-form redirect-back semantics in Task 5.x.

8. **`swing/web/routes/journal.py`** + **`swing/web/view_models/journal.py`** + **`swing/web/templates/journal.html.j2`** — structural anchor for the new `/config` page (smallest dashboard-style page).

9. **`tests/cli/`** — survey existing Click test runner patterns; CLI parity tasks mirror.

10. **`pyproject.toml`** — Task 1.0 adds `tomli_w >= 1.0` as a hard dependency. Verify the `[project] dependencies` block before editing.

If any file path above doesn't resolve, verify via `Glob`/`Grep` before executing the plan task.

---

## §0 Skill posture

- **INVOKE** `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review (2-5 rounds typical).
- **DO NOT INVOKE** `superpowers:brainstorming` / `copowers:brainstorming` — design is locked in the plan + brief.
- **DO NOT INVOKE** `copowers:writing-plans` — plan is locked at HEAD `e8c6396`. If you find a plan task is impossible to implement as written, STOP and surface in the return report; do NOT silently re-plan.
- **DO** invoke adversarial Codex review per `copowers:executing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`. Encourage internal-Codex pre-emption (commit message qualifier `(internal)` per 4-tier convention) before invoking the orchestrator-Codex round.

---

## §1 Strategic context (compressed)

The Phase 5 configuration page surfaces 3 operator-tunable settings (`cfg.web.chase_factor`, `cfg.pipeline.chart_top_n_watch`, `cfg.account.risk_equity_floor`) on a new `/config` web page + parallel CLI subcommands (`swing config show|set|reset`). Operator overrides persist to a separate user-config TOML file at `%USERPROFILE%/swing-data/user-config.toml` (parallel to `swing.db`; outside Drive per the SQLite-DB-location invariant). Override-precedence: Python default → tracked `swing.config.toml` → user-config.toml → page/CLI write.

V1 ships infrastructure ready for additional fields (V2 candidates — `risk_pct`, `pipeline_lease_wait_seconds`, `current_balance`, advisory thresholds, etc. — bolt on as small per-field follow-ups). Phase 6 (post-trade review surface) is queued NEXT after Phase 5 ships.

The plan introduces `swing/config_overrides.py` (per-request override application via `dataclasses.replace`); `tomli_w` as hard dependency for TOML writes; per-request read refactor across 27 cfg-reader sites + `run_pipeline` wrapper. Documented residual risk: long-lived caches built at app startup (PriceCache, OhlcvCache) hold the original immutable cfg — fine because none of the V1 fields feed those caches.

---

## §2 Locked decisions (DO NOT re-litigate)

All design decisions locked in `docs/phase5-configuration-page-writing-plans-brief.md` §2 + plan §2. The plan implements them as written; do NOT re-design. If you find a locked decision is impossible to implement as written (per plan), STOP and surface in the return report; do NOT silently deviate.

Notable decisions to keep in mind during execution (NOT exhaustive — read brief §2 for full list):

- **Per-request read** (NOT import-time cache) — plan Task 1b is REQUIRED per writing-plans return report.
- **Atomic write via tempfile-in-dest-dir** — `tempfile.NamedTemporaryFile(dir=<config-dir>, delete=False)` + `os.replace`. NEVER `shutil.move`. NEVER tempfile in `$TMP`.
- **Auto-backup malformed user-config before overwrite** (per Codex R3 + R4 fixes) — backup filename uses `%Y%m%dT%H%M%S%f` microseconds + collision counter; module-level `_dt` for testability. Plan specifies the exact pattern.
- **Web/CLI parity divergence on "lock at default"** (R2 ACCEPTED-with-rationale) — CLI's `--force` semantics provide locking path; web V1 has no lock-checkbox UI. V2 may add per-row Lock control.
- **Atomic-write claim narrowed to "best-effort REPLACE"** (R1 ACCEPTED) — full crash-durability is journal/version pattern; YAGNI for V1.
- **`ConfigPageVM` includes existing banner-guard fields** (`session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded`) with safe defaults — plan Task 4.0 specifies. Static nav link does NOT propagate to other base-layout VMs (CLAUDE.md 5-VM rule does NOT apply for the link itself).

---

## §3 Scope

### In scope (this dispatch)

Execute the plan task list at `docs/superpowers/plans/2026-05-01-configuration-page-plan.md`. ~11 task groups; ~75 new tests; baseline 1381 → ~1450.

### Out of scope (explicitly NOT this dispatch)

- **Re-litigating any locked decision** in brief §2 / plan §2.
- **Adding fields beyond the V1 three** (`cfg.web.chase_factor`, `cfg.pipeline.chart_top_n_watch`, `cfg.account.risk_equity_floor`).
- **Phase 6 territory** — `trades` schema, journal review surface, post-trade review fields, `Review_Log` entity.
- **Authentication / audit log / multi-user support** — single-operator tool.
- **Live-reload signals to running pipeline subprocess** — pipeline reads cfg at startup; in-flight pipeline keeps old values per Q4=A.
- **TOML schema versioning** — flat key-value; no `schema_version` field.
- **V2 web "Lock as override" control** — explicitly deferred to V2 per R2 ACCEPTED-with-rationale.
- **Worktree isolation** — single-subagent dispatch baseline (14-phase ZERO-rogue track record). Escalate ONLY if a novel collision mode emerges; document in return report.

---

## §4 Binding conventions

- **Branch:** `main`. All work commits directly.
- **Commits:** conventional 4-tier convention per orchestrator-context "Binding conventions":
  - Task implementation: `feat(<area>): Task X.Y — <subject>` (e.g., `feat(config): Task 1.0 — tomli_w dependency add`).
  - Codex review-fix: `fix(<area>): Codex R<N> <severity> <id> — <subject>`.
  - Internal-Codex (within-task): append `(internal)` qualifier to the round label (e.g., `fix(config): Codex R1 (internal) Major 2 — atomic-write tempfile dir`).
  - Format-only cleanup (ruff, comment-only): no task ID prefix needed.
- **Subject-only ERE grep observable verification** before EVERY task implementation commit:
  ```
  git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'
  ```
  Empty output for THIS phase's task ID → safe to proceed. Cross-phase noise is expected (per the 2026-04-30 ERE grep cross-phase-collision lesson) — distinguish fresh-vs-stale by date/SHA. STOP and surface in return report only if a duplicate appears within minutes of a prior commit (genuine within-phase collision).
- **TDD:** write failing test → run → see fail → minimal implementation → run → see pass → commit, per task. Plan task text already specifies the failing test FIRST in each task body.
- **Ruff baseline 91 warnings** (as of HEAD `e8c6396`). New code MUST NOT increase the baseline. `ruff check swing/` after each task to verify.
- **No-amend.** Every commit is a NEW commit. If a Codex round triggers a fix, that fix is its own commit (not an amend of the task commit).
- **No `--no-verify`, no `--no-gpg-sign`, no Claude co-author footer.**
- **TestClient lifespan:** any test exercising route behavior MUST use `with TestClient(app) as client:` (enters app lifespan).
- **Atomic write idiom:** `tempfile.NamedTemporaryFile(mode="w", dir=<dest_dir>, delete=False, encoding="utf-8")` + write + `os.replace(tmp.name, dest)`. NEVER `shutil.move`. NEVER tempfile in `$TMP` for cross-volume destinations.

---

## §5 Per-task acceptance criteria

Per-task acceptance criteria are specified in the plan itself. Plan task body is the source of truth; this brief does NOT duplicate per-task specs. Honor the plan exactly.

If you find a task acceptance criterion ambiguous OR contradictory with the locked decisions in brief §2: STOP, surface in the return report under "Plan ambiguities surfaced," and do NOT silently re-interpret.

---

## §6 Adversarial review

**Target:** `NO_NEW_CRITICAL_MAJOR` after up to 5 Codex rounds.

**Watch items** (from plan §F + writing-plans brief §6 — pre-empt these; Codex will probe them):

1. **Toml-shadowing audit completeness.** Every read site of every surfaced field consults the new precedence chain via `apply_overrides`. Plan §C enumerates the 27 cfg-reader sites; verify each one was modified.
2. **Atomic write under cross-device-link** (CLAUDE.md gotcha). Tempfile in dest dir, NOT `$TMP`.
3. **Per-request read regression.** Long-lived cache references to `cfg.<field>` at app startup do NOT pick up user-config writes. Plan documents residual risk (PriceCache, OhlcvCache); accepted because no V1 field feeds those.
4. **Source-introspection accuracy at boundaries.** If user-config explicitly sets a field to its default value, source reports `override` (operator chose to lock it), NOT `default`. Plan specifies this contract.
5. **Soft-warn confirm round-trip ToCToU.** Operator submits `chase_factor=0.05` (soft-warn) → confirm fragment renders → operator confirms → `force=true` resubmit MUST persist `0.05` from form_values hidden input, NOT re-fetch current user-config (which is still pre-submit value). Per multi-path-ingestion lesson 2026-04-29.
6. **Reset semantics** — DELETES the field from user-config; subsequent read falls through. Does NOT write the default value.
7. **CLI + web validation parity** — both surfaces consume the SAME validation registry. Verify single shared module.
8. **Hard-refuse error fragment shape** — no `<tr>`-leading content per CLAUDE.md HTMX gotcha.
9. **Auto-backup behavior** — malformed user-config triggers backup-before-overwrite; backup filename uses microsecond resolution + collision counter (per R3 + R4 fixes).
10. **TOML serialization edge cases** — float-repr (`0.020` vs `0.02`); int vs float disambiguation; section-table presence. Plan uses `tomli_w` for write (verify dependency add).
11. **Cancel-link full-page navigation** — `GET /config` after a soft-warn confirm renders cleanly without nested-layout corruption. Plan Task 7.0 Step 4 covers.

---

## §7 Done criteria

- All plan task list executed; all per-task acceptance criteria met.
- `python -m pytest -m "not slow" -q` exits clean. Test count ~1381 → ~1450 (within the plan's projection).
- `ruff check swing/` reports baseline-or-better (≤91 warnings).
- All 4-tier commit-message convention checks pass; subject-only ERE grep returns empty (within-phase) before each task implementation commit.
- Codex adversarial review reaches `NO_NEW_CRITICAL_MAJOR`.
- **OPERATOR-WITNESSED VERIFICATION GATE (BINDING):** the plan dispatch return report from writing-plans recommended this; orchestrator confirms as binding. Implementer MUST run `swing web` locally + walk the 7-step browser flow per plan Task 7.0 Step 4 + report findings before requesting merge approval. Two specific failure modes are real-browser-only:
  - HTMX `<tr>`-leading `makeFragment` pathology — TestClient assertions verify response body, NOT parser-mangled OOB swaps.
  - Cancel-link full-page navigation — verify nested-layout integrity after soft-warn confirm.
- Browser verification findings reported in return report under "Operator-witnessed verification" section. Any defect surfaced → fix in a new commit before declaring done.

---

## §8 Return report format

Produce as final message:

```
## Return Report — Phase 5 Configuration Page Executing-Plans Dispatch

### Code landed
- Final HEAD: <hash>
- Commits: <N>
- Test count: <pre> → <post> (delta: +<N>)
- Ruff: <baseline> warnings (<= 91 baseline preserved)

### Codex review
- Rounds: <N>
- Final verdict: NO_NEW_CRITICAL_MAJOR
- Per-round summary: <C>/<M>/<m>/<advisory> with disposition (FIXED / ACCEPTED-with-rationale)
- Notable accepts: <list>

### Operator-witnessed verification
- Browser flow executed: <yes/no>
- Findings: <list any defects + commit hashes that resolved them; if none, "all 7 steps pass">
- Specific real-browser checks:
  - Soft-warn confirm fragment renders without OOB-swap mangling: <pass/fail>
  - Cancel-link full-page navigation preserves layout: <pass/fail>
  - Auto-backup of malformed user-config: <verified/not exercised>

### Plan deviations (if any)
- <list any plan-task ambiguities surfaced + how resolved; if none, "none">

### Out-of-scope discoveries (if any)
- <list any latent bugs or follow-up items surfaced during execution; do NOT fix in this dispatch — capture for orchestrator triage>

### Operator handoff
- Next move: orchestrator post-execution housekeeping (orchestrator-context status update, phase3e-todo SHIPPED marker, lessons capture if any)
- Phase 6 (post-trade review surface) is queued next per orchestrator-context.
```

---

## §9 If you get stuck

- **If a plan task is impossible to implement as written** (e.g., cfg refactor scope blows up beyond plan's 27 site enumeration): STOP. Surface in the return report under "Plan ambiguities surfaced." Do NOT silently re-design or re-scope.
- **If `swing/config.py` import-time caching is more entrenched than the plan's 27-site count suggests** (e.g., consumer modules cache `cfg.<field>` at module load that the plan missed): surface as Codex watch-item #3 explicitly; if scope exceeds 1 dispatch, BAIL and request operator escalation. Operator preference is "limited accessor at the 3 V1 fields with documented residual risk" — extending residual-risk acceptance is reasonable.
- **If `tomli_w` introduces a transitive-dependency conflict on the operator's machine** (Python 3.14 / Windows / pre-existing constraint): document in return report; do NOT silently swap to hand-serialization without operator approval.
- **If Codex flags a CLAUDE.md gotcha not pre-empted by the plan**: it's a real finding; FIX or ACCEPT-with-rationale per standard cycle.
- **If you find an additional latent bug** unrelated to Phase 5 scope: capture in return report under "Out-of-scope discoveries"; do NOT fix in this dispatch.
- **If the operator-witnessed verification surfaces a defect**: fix in a new commit (not an amend); update the verification report; do NOT declare done until the operator confirms the fix.

---

**End of brief.**
