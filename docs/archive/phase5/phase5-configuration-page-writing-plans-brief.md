# Phase 5 — Configuration Page for Operator-Tunable Settings — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Author an implementation plan for a new `/config` web page (plus parallel CLI) that lets the operator view and edit a small set of tunable settings (`chase_factor`, `web.chart_top_n_watch`, `risk_floor`) without hand-editing TOML. Persists overrides to a separate user-config file outside the repo. Brainstorm is EXPLICITLY SKIPPED — operator and orchestrator locked all design decisions in-thread on 2026-05-01 (see §2).

**Expected duration:** ~45-90 min plan-authoring + 3-5 Codex rounds via `copowers:writing-plans` wrapper = ~2-4 hours total.

**Dispatch type:** `copowers:writing-plans` (NOT executing-plans; this dispatch produces a plan, NOT shipped code).

---

## §0 Read first

Read these in order before drafting:

1. **`CLAUDE.md`** at repo root — project conventions, gotchas, invariants. Note especially: HTMX `<tr>`-leading `makeFragment` pathology (config form is fieldset-based, but the soft-warn confirm fragment must NOT lead with a `<tr>`); HTMX OOB-swap partial drift; `os.replace` cross-device-link gotcha (the user-config write MUST use `tempfile.NamedTemporaryFile(dir=<config-dir>)` to keep tempfile on the same filesystem as the destination); base-layout 5-VM rule (only when `base.html.j2` actually dereferences the new field — confirm before requiring the mitigation); Starlette `TemplateResponse(request, "name", {...}, status_code=...)` signature; TestClient lifespan rule (`with TestClient(app) as client:` for any test touching `app.state.*`).

2. **`docs/orchestrator-context.md`** — §"Currently in-flight work" (HEAD `98b9a37` clean; 1381 fast tests; 14-phase ZERO-rogue track record); §"Binding conventions" (4-tier commit-message convention; subject-only ERE grep `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'`; ruff baseline 91; no-amend; no Claude footer); §"Anti-patterns to avoid"; §"Lessons captured" — read entire section. The most directly applicable lessons:
   - **Toml-shadowing audit (`aeb2084`, 2026-04-28).** Any tunable surfaced via the page MUST honor an explicit override-precedence ordering. For this dispatch the order is: **Python default → tracked `swing.config.toml` → user-config.toml → page-write (which writes back into user-config.toml).** This is BINDING; all field-read paths must consult the user-config file.
   - **Multi-path data ingestion needs full-path audit** (sector capture R2 M1, 2026-04-29). Every read site of every surfaced field must consult the new precedence chain. Plan must enumerate read sites via `grep -rn "<field-name>" swing/`.
   - **Spec/plan silence on form-driven success-path response shape is a recurrent failure class** (hyp-recs trade-prep R1 M1, 2026-04-29). Specify success-path response behavior explicitly (303 redirect to `/config` vs HTMX fragment swap).
   - **Snapshot-at-entry-surface ToCToU pattern** (chart-pattern flag-v1 spec §3.6, Phase 5 lesson). For the soft-warn confirm round-trip: the operator's first submit produces the soft-warn fragment containing the SAME values they typed; `force=true` resubmit persists THOSE values (not re-fetched current file state).
   - **External-API empty-result transient handling** (2026-04-30). Not directly applicable — this dispatch is local-file-backed — but the same principle applies inversely: a zero-byte / malformed user-config.toml must be treated as "no overrides" (return empty dict + log warning), NOT as "delete all overrides".
   - **HTMX `<tr>`-leading `makeFragment` pathology** (2026-04-29; CLAUDE.md). Config form root is `<form><div>` not `<table>`; soft-warn confirm fragment must mirror the existing `partials/soft_warn_confirm.html.j2` shape (banner + form + form_values loop). If the confirm fragment uses any table elements, do NOT lead with `<tr>`.
   - **`base.html.j2` shared-VM rule** — verify whether the base layout dereferences any new field added by `ConfigPageVM`. If yes, every base-layout VM (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`) must gain it. If no, scope is `ConfigPageVM` only.

3. **`docs/phase3e-todo.md`** §"2026-04-28 configuration page for operator-tunable settings (QUEUED; future dispatch)" (~lines 759-778) — original scope sketch. The locked decisions in §2 below SUPERSEDE everything in that entry; it's history-only context.

4. **`swing/config.py` (or wherever `cfg` is defined)** — survey BEFORE drafting:
   - `grep -rn "from swing.config" swing/ | head -40` to enumerate consumers.
   - Read the loader. Determine if config is cached at import-time (module-level `cfg = load_config()`) or re-read per access. **If cached, the plan must convert to per-request read** (or per-access via a callable accessor) so user-config edits take effect on the next request without restart.
   - Confirm exact field paths: `chase_factor` (likely top-level `cfg.chase_factor` or under a section); `chart_top_n_watch` (per `docs/phase3e-todo.md:768` it's at `swing.config.toml` line 93 — likely `cfg.web.chart_top_n_watch`).

5. **`swing.config.toml`** at repo root — full read. Enumerate the existing field structure to ensure the user-config file mirrors the same schema namespace.

6. **`grep -rn "7500" swing/ tests/`** — locate every reference to the `risk_floor` magic number. Per `docs/phase3e-todo.md:770`, it is currently a code constant (NOT in `swing.config.toml`). Promoting it to a config field is part of Task 0a (Phase 2 carve-out — see §3).

7. **`grep -rn "chase_factor" swing/`** — confirm where the chase_factor field is defined and consumed (shipped by hyp-recs trade-prep expansion ~2026-04-28).

8. **`swing/web/routes/`** + **`swing/web/view_models/`** + **`swing/web/templates/`** — survey shape of an existing simple page (e.g., `journal.py` route + `journal.py` view_model + `journal.html.j2` template) as the structural template for the new `/config` page.

9. **`swing/web/templates/partials/soft_warn_confirm.html.j2`** — the canonical soft-warn round-trip pattern. Adapt for config-form re-submit semantics.

10. **`swing/cli.py`** — survey existing subcommand patterns (`swing trade entry`, `swing journal review`, `swing hypothesis update`) for the CLI parity tasks. Confirm Click idioms in use (Click groups; `--option` vs argument; `click.Choice` for enum values).

11. **`docs/phase4.5-hypothesis-label-web-form-writing-plans-brief.md`** — most-recent precedent brief for a small frontend-integration dispatch with soft-warn round-trip semantics. Mirror its structure.

If any file path above doesn't resolve, verify via `Glob`/`Grep` before drafting plan tasks against it.

---

## §0 Skill posture

- **INVOKE** `copowers:writing-plans` — wraps `superpowers:writing-plans` with adversarial Codex review (3-5 rounds typical).
- **DO NOT INVOKE** `superpowers:brainstorming` or `copowers:brainstorming` — design decisions are pre-locked (see §2). Re-litigation is out of scope. If you find a locked decision is impossible to implement as written, STOP and surface it in the return report; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:writing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`.
- **Plan output target path:** `docs/superpowers/plans/2026-05-01-configuration-page-plan.md`. Commit the plan as part of the standard cycle.

---

## §1 Strategic context

**Operator-tunable settings are accumulating.** As of 2026-05-01, three non-trivial settings live as Python defaults possibly shadowed by `swing.config.toml`:

- `chase_factor` (default `0.01` = 1% above pivot for buy-limit calculation; shipped by hyp-recs trade-prep expansion ~2026-04-28).
- `web.chart_top_n_watch` (default `10` post-chart-scope-policy-v2; was `5`).
- `risk_floor` (default `$7500`; per `project_capital_risk_floor.md` memory; **currently a code constant, NOT in `swing.config.toml`** — Task 0a promotes it).

Operator currently edits `swing.config.toml` by hand to override any of these. Friction is real but bounded; the larger forward concern is that as the field set grows (future: `risk_pct`, `pipeline_lease_wait_seconds`, etc.), tracked-toml edits become noisy in `git status` and a tracked-vs-runtime divergence becomes easier to introduce by accident.

**This dispatch ships infrastructure + 3 fields.** The infrastructure is the load-bearing piece: a separate user-config file outside the repo (`%USERPROFILE%/swing-data/user-config.toml`, parallel to `swing.db`) holding operator overrides; an explicit override-precedence chain (Python default → tracked toml → user-config → page-write); a per-request read so saves take effect on the next request without restart; per-field validation (hard-refuse + soft-warn); a dedicated `/config` page with override-source visibility + reset-to-default; CLI parity (`swing config show|set|reset`). Three fields ship in V1; bolting on additional fields later requires only adding rows to the field registry, NOT re-architecting persistence or UI.

**Sequencing context.** This dispatch ships AFTER Phase 4.5 + 4.5-followup + TOS-import bug fix all SHIPPED (HEAD `98b9a37`). It is the longest-queued operational item per `docs/phase3e-todo.md`. Phase 6 (post-trade review surface — Mistake_Tags + Process Grade) is queued NEXT after Phase 5; this dispatch must NOT touch any Phase 6 territory (`trades` schema, journal review surface, `Review_Log` entity).

---

## §2 Locked decisions (DO NOT re-litigate)

Operator-locked 2026-05-01. The plan implements these as written; no re-design.

1. **Persistence model: separate user-config file at `%USERPROFILE%/swing-data/user-config.toml`** (parallel to `swing.db` per the SQLite-DB-location invariant — outside Drive). NOT write-back to tracked `swing.config.toml`; NOT a DB-backed `config` table. Rationale: preserves `swing.config.toml` as project-defaults source-of-truth (clean `git status`); separates operator overrides from project defaults; cheaper than DB-backed for a 3-field V1.
2. **Override-precedence (BINDING):** Python default → tracked `swing.config.toml` → user-config.toml → page-write (which writes into user-config.toml). User-config STRICTLY overrides tracked-toml for any field present; absent fields fall through to tracked-toml then default. Per-field, NOT all-or-nothing.
3. **Per-request read (NOT import-time cache).** If `swing/config.py` currently caches at import-time, refactor to per-request read (Task 1b — see §3) so user-config edits take effect on the next request without restart. Acceptable pattern: a thin `get_config()` accessor that re-reads on each call (cheap; toml is tiny + filesystem-cached by OS).
4. **V1 field set (3 fields ONLY):**
   - `chase_factor` — float; default `0.01`; consumer: hyp-recs trade-prep expansion view-model.
   - `web.chart_top_n_watch` — int; default `10`; consumer: chart-scope policy v2 resolver.
   - `risk_floor` — float; default `7500.0`; consumer: position-sizing math (currently a code constant; Task 0a promotes it).
5. **Validation (hard refuse + soft-warn; per Q5=C):**
   | Field | Hard refuse | Soft-warn (allow proceed) |
   |---|---|---|
   | `chase_factor` | outside `[0, 0.10]` | above `0.02` |
   | `chart_top_n_watch` | outside `[1, 50]` | above `25` |
   | `risk_floor` | below `0` | outside `[1000, 25000]` |
   Hard refuses render an error fragment (no write). Soft-warns produce a confirm fragment with the proposed value preserved as a hidden input + a "Confirm" button that submits with `force=true`; the resubmit writes.
6. **Dedicated `/config` page** (NOT a dashboard panel; NOT inline edit). New route + new template + `ConfigPageVM`. Add nav link to `base.html.j2` next to existing nav targets.
7. **Atomic-on-save:** the form submits all fields together. Validation runs on the full set; first hard-refuse short-circuits the write. Per-field reset is independent of the save form (each reset is its own POST).
8. **Override-source visibility (per Q6=yes):** Each field row renders Current value + Default value + Source badge. Source ∈ {`default`, `tracked toml`, `user override`}. Cosmetic but high-clarity.
9. **Reset-to-default per field (per Q7=yes):** A per-field "Reset" button posts to a separate endpoint that DELETES the field from user-config.toml. Subsequent reads fall through to the next layer in the precedence chain. Reset does NOT need confirmation; it's reversible by re-saving.
10. **CLI parity (per D=yes):** Three subcommands under a `swing config` group:
    - `swing config show` — pretty-print all V1 fields + current value + default + source.
    - `swing config set <field> <value>` — validates (hard-refuse exits non-zero with stderr; soft-warn prompts y/n unless `--force` passed).
    - `swing config reset <field>` — removes the field from user-config.toml.
    Same persistence layer as the web page. Both surfaces drive the SAME backing file.
11. **Atomic write semantics:** All writes to user-config.toml use `tempfile.NamedTemporaryFile(dir=<config-dir>, delete=False)` + write + `os.replace(tmp, dest)` per the CLAUDE.md cross-device-link gotcha. Tempfile MUST be in the same directory as the destination file.
12. **File schema:** Mirror `swing.config.toml` structure (top-level keys + section tables). Example user-config.toml after operator sets all three fields:
    ```toml
    chase_factor = 0.02
    risk_floor = 10000.0

    [web]
    chart_top_n_watch = 15
    ```
    Missing fields → fall through. Missing file → empty overrides dict. Malformed file → log warning + empty overrides dict (do NOT raise; do NOT delete the file).
13. **No nav-link auth / access control.** Single-operator tool; existing OriginGuard middleware is sufficient.

---

## §3 Scope

### In scope (this dispatch)

- **Task 0a (Phase 2 carve-out — `swing/trades/` or wherever `risk_floor` constant lives):** Promote `risk_floor` from code constant to config field. Survey via `grep -rn "7500" swing/ tests/` to enumerate references; replace each with `cfg.risk.floor` (or whatever path the plan settles on). Add to `swing.config.toml` and to the loader as a recognized field. Existing tests must remain green; default value MUST byte-equal the previous constant. **Discriminating test: an integration test that exercises position-sizing math with `risk_floor` overridden via user-config and asserts the override takes effect.**
- **Task 1: User-config persistence layer.** New module (recommended location: `swing/config_user.py`; alternative: `swing/data/user_config.py` if persistence layer parity preferred). Public API: `load_user_overrides() -> dict`, `write_user_overrides(overrides: dict) -> None`, `delete_user_override(field_path: str) -> None`, `get_user_config_path() -> Path`. File path: `%USERPROFILE%/swing-data/user-config.toml`. Atomic write per locked decision §2.11. Missing file → empty dict. Malformed file → log warning + empty dict.
- **Task 1b: Convert `swing/config.py` to per-request read** (only if currently import-time cached; verify in §0 Read 4). If already per-request, mark as no-op + skip.
- **Task 2: Override-precedence integration.** Wire user-config consultation into the config loader so `cfg.chase_factor`, `cfg.web.chart_top_n_watch`, `cfg.risk.floor` (or final names) consult the user-config layer between tracked-toml and page-writes. Add an introspection accessor: `get_field_source(field_path: str) -> Literal["default", "tracked", "override"]` for the VM to render the source badge.
- **Task 3: Validation module.** New `swing/web/config_validation.py` (or `swing/config_validation.py` if shared with CLI). `ValidationResult` dataclass: `hard_errors: list[ValidationError]`, `soft_warnings: list[ValidationWarning]`. Per-field rules table sourced from a single registry so web + CLI consume the same validation. Discriminating boundary tests per §2.5 table.
- **Task 4: Web view-model + routes.** New `swing/web/view_models/config.py` with `ConfigPageVM`. New route file `swing/web/routes/config.py` with: `GET /config` → render page; `POST /config` → atomic-save with validation (hard-refuse → error fragment; soft-warn → confirm fragment with form_values pattern; happy-path → 303 redirect to `/config` with success banner); `POST /config/reset/<field_path>` → delete field from user-config + 303 redirect to `/config`. Mount in `swing/web/app.py`.
- **Task 5: Template.** New `swing/web/templates/config.html.j2` extending `base.html.j2`. Per-field row layout: field name + description + current value (editable input) + default value (read-only span) + source badge + reset button (separate form per field). Save button at form bottom (single atomic save). New `swing/web/templates/partials/config_soft_warn_confirm.html.j2` mirroring the existing `soft_warn_confirm.html.j2` pattern adapted for config-page redirect-back semantics. Add `/config` nav link to `base.html.j2`.
- **Task 6: CLI parity.** New `swing/cli_config.py` (or extend `swing/cli.py` with a `config` Click group). Three subcommands per locked decision §2.10. Same validation registry from Task 3. Round-trip via Click test runner.
- **Task 7: Base-layout VM check.** Verify whether `base.html.j2` references any new field. If the new nav link uses a flag like `vm.is_config_page`, that flag MUST be added to all base-layout VMs (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`, `ConfigPageVM`). If no new field is referenced (just a static nav link), no propagation needed. Plan must explicitly call out which case applies.

### Out of scope (explicitly NOT this dispatch)

- **Additional fields beyond the V1 three.** No `risk_pct`, `pipeline_lease_wait_seconds`, `current_balance`, or any other settings. Adding fields later is a small per-field follow-up; the infrastructure ships ready for it.
- **Authentication, audit log, multi-user support.** Single-operator tool; out of scope.
- **Live-reload signals to a running pipeline subprocess.** Pipeline reads config at startup; in-flight pipeline keeps old values. Acceptable per Q4=A.
- **Schema versioning on user-config.toml.** Flat key-value; no schema_version field. Future migration if needed handled by a one-off script then.
- **Phase 6 territory.** Do NOT touch `trades` schema, journal review surface, post-trade review fields, or `Review_Log` entity.
- **Journal-review aggregation by config-snapshot.** Future-dispatch concern.
- **Config page for advisory thresholds (10MA / 20MA / etc.).** Tier-3 #6 advisory state-machine work; out of scope.
- **`cfg.web.*` settings beyond `chart_top_n_watch`.** Out of V1 scope.
- **Validation-rule editing via the page itself.** Validation registry is code-defined, not config-defined.
- **Toml schema versioning, audit-trail, last-modified-by/at.** DB-backed concerns; this dispatch is file-backed.

---

## §4 Binding conventions

- **Branch:** `main`. All work commits directly.
- **Commits:** conventional 4-tier convention per orchestrator-context "Binding conventions":
  - Task implementation: `feat(<area>): Task X.Y — <subject>` (e.g., `feat(config): Task 1 — user-config persistence layer`).
  - Codex review-fix: `fix(<area>): Codex R<N> <severity> <id> — <subject>` (e.g., `fix(config): Codex R1 Major 2 — atomic-write tempfile dir`).
  - Internal-Codex (within-task): append `(internal)` qualifier.
  - Format-only cleanup (ruff, comment-only): no task ID prefix needed.
- **Subject-only ERE grep observable verification** before every task implementation commit:
  ```
  git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y' --since="<dispatch start date>"
  ```
  Empty output → safe to proceed. Any output → STOP and surface the duplicate in the return report.
- **TDD:** write failing test → run → see fail → minimal implementation → run → see pass → commit, per task. Plan must specify the failing test FIRST in each task body.
- **Ruff baseline 91 warnings** (as of HEAD `98b9a37`). New code MUST NOT increase the baseline. `ruff check swing/` after each task to verify.
- **No-amend.** Every commit is a NEW commit. If a Codex round triggers a fix, that fix is its own commit (not an amend of the task commit).
- **No `--no-verify`, no `--no-gpg-sign`, no Claude co-author footer.**
- **TestClient lifespan:** any test exercising route behavior MUST use `with TestClient(app) as client:` (enters app lifespan).
- **Atomic write idiom:** `tempfile.NamedTemporaryFile(mode="w", dir=<dest_dir>, delete=False, encoding="utf-8")` + write + `os.replace(tmp.name, dest)`. NEVER `shutil.move`. NEVER tempfile in `$TMP` for cross-volume destinations.

---

## §5 Per-task acceptance criteria sketch

The plan author drafts the actual task partitioning + commit-by-commit roadmap. The acceptance criteria below are the contract surface the plan must hit.

- **Task 0a (risk_floor promotion).** Discriminating test: position-sizing math with `risk_floor` overridden via user-config takes effect (NOT the constant value). Existing tests green. Default value byte-equals previous constant.
- **Task 1 (persistence).** Round-trip: write `{"chase_factor": 0.02}` → load → assert dict-equal. Atomic write: simulate write-failure mid-write → assert dest file unchanged. Missing file: load returns `{}`. Malformed file: load returns `{}` + emits warning log.
- **Task 1b (per-request read, if needed).** Discriminating test: write user-config override → IMMEDIATELY (within same Python process, no restart) read `cfg.<field>` → assert override-applied value.
- **Task 2 (precedence).** For each of the 3 fields, 3 tests covering: default-only (no toml override, no user-config) → returns Python default; tracked-toml-only (toml override, no user-config) → returns toml value; user-override (user-config present) → returns user-config value. Source-introspection returns correct `default | tracked | override` for each scenario.
- **Task 3 (validation).** Per field: hard-refuse boundary test (one inside, one outside); soft-warn boundary test (one below threshold, one above). Total ~12 boundary tests.
- **Task 4 (web).** GET renders all 3 fields with correct current/default/source. POST happy-path: writes user-config + 303 redirects. POST hard-refuse: returns error fragment, NO write. POST soft-warn: returns confirm fragment with proposed values preserved as hidden inputs. POST confirm-soft-warn (`force=true`): writes user-config (NOT re-validated against soft-warn). POST reset: deletes field from user-config + 303 redirects.
- **Task 5 (template).** Template renders all 3 fields. Source badge renders correct text per source. Reset button is a separate `<form>` (not a child of the main save form). Soft-warn confirm fragment auto-iterates `form_values` (NOT hand-duplicated) per the OOB-swap-drift lesson.
- **Task 6 (CLI).** `swing config show` lists all 3 fields with correct current/default/source. `swing config set chase_factor 0.02` writes successfully. `swing config set chase_factor 0.5` exits non-zero with stderr error message (hard-refuse). `swing config set chase_factor 0.05` prompts y/n (soft-warn); `--force` skips prompt. `swing config reset chase_factor` removes field from user-config.
- **Task 7 (base-layout VM check).** Plan must explicitly state which case applies (new field needed in all 5 base-layout VMs vs static nav link only). If new field needed, every base-layout VM gains it with a safe default.

---

## §6 Adversarial review section (target + watch items)

**Target:** `NO_NEW_CRITICAL_MAJOR` after up to 5 Codex rounds.

**Watch items** (the plan and implementation should pre-empt these; Codex will probe them):

1. **Toml-shadowing audit completeness.** Every read site of every surfaced field consults the new precedence chain. Surface a survey table in the plan: `field path | consumer file:line | reads-via-cfg-loader-yes/no`. Any "no" must be fixed in the plan.
2. **Atomic write under cross-device-link** (CLAUDE.md gotcha). Tempfile in dest dir, NOT `$TMP`. Plan must specify `dir=<config-dir>` explicitly in the tempfile call.
3. **Per-request read regression.** If Task 1b refactors a cached config to per-request, every existing consumer that holds a cached reference to `cfg.<field>` (e.g., a long-lived view-model instance) breaks silently. Plan must enumerate consumer-cache sites + decide either (a) adopt accessor-style reads everywhere, or (b) explicitly accept the lifetime mismatch with rationale.
4. **Source-introspection accuracy at boundaries.** If user-config explicitly sets a field to its default value, source should report `override` (operator chose to lock it), NOT `default`. Plan must specify this contract.
5. **Soft-warn confirm round-trip ToCToU.** Operator submits `chase_factor=0.05` (soft-warn) → confirm fragment renders → operator confirms → `force=true` resubmit. The resubmit MUST persist `0.05` from the form_values hidden input, NOT re-fetch the current user-config value (which is still the pre-submit value). Per the multi-path-ingestion lesson 2026-04-29.
6. **Reset semantics for soft-warn-locked fields.** If user-config has `chase_factor=0.03` (soft-warn-overridden via `--force` or `force=true`), reset should DELETE the field cleanly. Subsequent read falls through. Plan must specify reset deletes the field, NOT writes default value.
7. **CLI + web validation parity.** Both surfaces consume the SAME validation registry. Plan must specify a single shared module, NOT duplicated rule tables.
8. **Hard-refuse error fragment shape.** No `<tr>`-leading content per CLAUDE.md HTMX gotcha. Confirm fragment is a `<div>` or `<section>`-rooted partial.
9. **Risk_floor promotion (Task 0a) consumer audit.** `grep -rn "7500" swing/ tests/` must be exhaustive. Any test that asserts a specific dollar value derived from `risk_floor` must be updated to read from `cfg` rather than hard-code the constant.
10. **CLAUDE.md `base.html.j2` 5-VM rule scope.** Plan must explicitly verify the rule applies (new VM field referenced by base layout) BEFORE blanket-requiring it across all base VMs. If the nav link is a static `<a>` with no VM dereference, the rule does NOT apply.
11. **TOML serialization edge cases.** Floats with trailing zeros (`0.020` vs `0.02`); int vs float disambiguation (`10` vs `10.0` for chart_top_n_watch); section-table presence (`[web]` only emitted when needed). Plan must specify the TOML library used (`tomllib` is read-only stdlib in Python 3.11+; writes need `tomli_w` or hand-serialization). Confirm dependency choice in §0 Read.
12. **Validation registry source-of-truth duplication risk.** Field metadata (default value, validation ranges, description) lives in the registry. Tracked-toml `swing.config.toml` ALSO has the default. Plan must specify which is authoritative + how they stay in sync (likely: registry is the SoT; tracked-toml is the seed/example; loader uses registry default if tracked-toml is absent).

---

## §7 Done criteria

- All §3 in-scope tasks implemented.
- All §5 acceptance criteria met (test counts ~25-35 new tests; baseline 1381 → ~1410+).
- `python -m pytest -m "not slow" -q` exits clean.
- `ruff check swing/` reports baseline-or-better (≤91 warnings).
- All 4-tier commit-message convention checks pass; subject-only ERE grep returns empty before each task implementation commit.
- Codex adversarial review reaches `NO_NEW_CRITICAL_MAJOR`.
- Plan committed to `docs/superpowers/plans/2026-05-01-configuration-page-plan.md`.
- Plan return report explicitly states: (a) which case Task 7 (base-VM check) is in (new field vs static link); (b) whether Task 1b is needed (per-request read refactor) or no-op; (c) the resolved field-path naming for `risk_floor` after consumer audit; (d) the TOML write library chosen.

---

## §8 Return report format

Produce as final message:

```
## Return Report — Phase 5 Configuration Page Writing-Plans Dispatch

### Plan landed
- File: docs/superpowers/plans/2026-05-01-configuration-page-plan.md
- Commit: <hash>

### Codex review
- Rounds: <N>
- Final verdict: NO_NEW_CRITICAL_MAJOR
- Per-round summary: <C>/<M>/<m>/<advisory> with disposition (FIXED / ACCEPTED-with-rationale)

### Resolved-during-planning items
- Task 7 case: <new VM field needed | static link only>
- Task 1b status: <required | no-op (already per-request)>
- Risk_floor consumer audit: <N references found at <file:line, file:line, ...>>; promoted-name decision: cfg.<resolved-path>
- TOML write library: <tomli_w | hand-serialization | other>
- User-config file path: <%USERPROFILE%/swing-data/user-config.toml | other if operator-overridden>

### Open questions surfaced (if any)
- <list any items where the locked decisions in §2 proved insufficient or contradictory; otherwise "none">

### Out-of-scope items deferred
- Per-field expansion follow-ups (V2): <list>
- Codex-surfaced advisories not actionable in V1: <list>

### Operator handoff
- Next dispatch: copowers:executing-plans against the plan
- Brief at: docs/phase5-configuration-page-executing-plans-brief.md (orchestrator drafts post-plan-review)
- Operator-witnessed verification gate: <yes/no — recommendation based on plan complexity>
```

---

## §9 If you get stuck

- **If a locked decision contradicts the existing code** (e.g., precedence-chain not implementable as written): STOP. Surface in the return report with a "Locked decisions blocked by code state" section. Do NOT silently re-design.
- **If `swing.config.py` import-time caching is more entrenched than expected** (e.g., dozens of consumer modules cache `cfg.<field>` at module load): surface as Codex watch-item #3 explicitly; propose either (a) full accessor refactor across consumers (likely scope blow-up — bail with operator escalation) or (b) limited accessor at the 3 V1 fields with documented residual risk. Operator preference is (b) if the scope of (a) exceeds 1 dispatch.
- **If TOML library choice surfaces a stdlib gap** (Python 3.14 has `tomllib` for read; `tomli_w` is third-party for write; hand-serialization is plausible for 3 flat fields + 1 section): plan-author chooses; document in return report.
- **If risk_floor consumer audit surfaces references in research-branch code (`research/`)**: do NOT touch research-branch unless explicitly authorized. Surface in return report; operator decides per-bifurcated-architecture discipline.
- **If you find an additional latent bug** unrelated to Phase 5 scope: capture in return report under "Out-of-scope discoveries"; do NOT fix in this dispatch.
- **If Codex flags a CLAUDE.md gotcha not pre-empted by the plan**: it's a real finding; FIX or ACCEPT-with-rationale per standard cycle.

---

**End of brief.**
