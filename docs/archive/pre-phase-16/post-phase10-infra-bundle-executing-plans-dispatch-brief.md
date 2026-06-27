# Post-Phase-10 infra bundle — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute a bundled infrastructure improvement dispatch (cleanup-script `-DeregisterFirst` extension + test-runtime xdist/fixture-scope analysis) on an isolated worktree branch via `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` + adversarial Codex MCP review). **Read-side / infrastructure-only — ZERO production-code changes.** Both items are pre-banked at `docs/phase3e-todo.md` 2026-05-13 entries; both have explicit "DEFERRED as separate orchestrator dispatch AFTER Phase 10 completes" markers; Phase 10 closed at `d560218` so both are unblocked.

**Expected duration:** ~3-5 hr executing-plans wall-clock + ~1-2 hr Codex convergence. 6 tasks total. Estimated 1-3 Codex rounds (this is the simplest dispatch since Phase 6 — minimal external interface; no new production schema; no new operator-facing routes). Lower Codex value-add than any Phase 10 sub-bundle.

---

## §0 Inputs

### §0.1 Backlog entries
- **Item 1 source:** `docs/phase3e-todo.md` 2026-05-13 "Post-Phase-10 standalone dispatches" Item 1 — Extend `cleanup-locked-scratch-dirs.ps1` with `-DeregisterFirst` switch.
- **Item 2 source:** `docs/phase3e-todo.md` 2026-05-13 "Post-Phase-10 standalone dispatches" Item 2 — Test-runtime xdist + fixture-scope analysis.
- **Re-confirmed:** T-E.4 closer section near end of phase3e-todo (line 1788+) lists both as "Post-Phase-10 standalone dispatches (UNBLOCKED by Phase 10 close)".

### §0.2 Project state at dispatch time
- **HEAD on `main`:** `d560218` (Phase 10 CLOSER housekeeping).
- **Test count (main HEAD):** **~3257 fast passing + 1 skipped on main HEAD `d560218`** (3254 worktree-side baseline at Sub-bundle E ship; +3 main-HEAD adjustment per Sub-bundle E gate notes). 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions. **Cross-bundle T-A.7 pin UN-SKIPPED** at E T-E.3 SAME COMMIT (`fb6e48a`).
- **Test runtime baseline:** ~6:00 wall-clock at 3254 tests (~110ms/test average). Per phase3e-todo entry: "slow for unit-style; going to 3300+ tests pushes past 6 min".
- **Ruff baseline:** **18 (E501 only).** Unchanged across entire Phase 9 + 10 arcs.
- **Schema version:** **v17.** LOCKED. **This dispatch introduces ZERO schema changes** (infrastructure-only).
- **Active risk_policy:** `policy_id=5` (unchanged through Phase 10).
- **7 worktree husks pending cleanup-script** at handoff: 4 still-registered Phase 9 (B/C/D/E) + 3 orphans (Phase 10 C/D/E). Item 1 of this bundle clears all 7.
- **No active production-write state changes** since Phase 10 close. Production trades: 8 total (5 open DHC/YOU/VSAT/CVGI/LAR + 3 closed VIR/CC/SGML); account_equity_snapshots #1 + #2 + #3 (post-Sub-bundle-E S6 gate); 30 reconciliation_discrepancies all resolved as `acknowledged_immaterial`.

### §0.3 Scope summary

| Task | Track | Files | Acceptance | Test count est. |
|---|---|---|---|---:|
| **T-1** recon — pytest profile + worker-safety audit | Test-runtime | `docs/post-phase10-infra-recon.md` (NEW; not committed in this task — captured inline for return report) | Run `python -m pytest -m "not slow" -q --durations=30` against main HEAD; capture top-30 slowest tests; audit for shared-state tests that could break under xdist (port binding, global singletons, shared file paths) | 0 |
| **T-2** Cleanup-script `-DeregisterFirst` extension | Cleanup-script | `cleanup-locked-scratch-dirs.ps1` (modify) + new test fixture under `tests/scripts/` (or document in PR description if test infrastructure for PowerShell is too heavy) | Add `-DeregisterFirst` boolean parameter (default `$false` — script behavior unchanged when omitted; opt-in required); when ON, pre-scan calls `git worktree remove --force <path>` for paths matching `^\.worktrees/phase\d+-.*` OR `^\.claude/worktrees/phase\d+-.*` (script-comment-documented project-precedent + skill-default paths); after deregister loop, existing orphan-discovery picks up the resulting orphans; safety filter rejects any non-matching path; abort if elevation check fails OR if any deregister call returns non-zero exit | 0-3 (PowerShell test infrastructure is heavy — most testing will be in dry-run mode + manual verification) |
| **T-3** pytest-xdist baseline integration | Test-runtime | `pyproject.toml` (add `pytest-xdist` to dev deps; configure default `-n auto`) + `tests/conftest.py` (if needed for worker-safe fixtures) + any test fixes for xdist-unsafe tests identified in T-1 | Add `pytest-xdist>=3.5.0` to `[project.optional-dependencies] dev`; configure `[tool.pytest.ini_options].addopts` to include `-n auto` (or document opt-in via `-n auto` on the CLI); run baseline parallel suite + verify (a) all 3254 fast tests pass under parallelization; (b) wall-clock measurably reduces (target: ~3-5x; ~6 min → ~1.5-2 min); (c) any xdist-unsafe tests identified in T-1 are marked `@pytest.mark.xdist_group(name="...")` OR `@pytest.mark.serial` (pytest-xdist 3.x supports `xdist_group` natively) | varies (test fixes for xdist-unsafe tests; expect 0-10 new marker additions) |
| **T-4** (conditional) Session-scoped schema fixtures | Test-runtime | `tests/conftest.py` + `swing/data/db.py` (if refactor needed) | ONLY if T-1 profile data shows `ensure_schema` is a meaningful hotspot (target: top-10 in `--durations`). Cache fresh-DB template at session scope + `shutil.copy()` per test (saves ~10-50ms per test × thousands of tests = several minutes). Discriminating test: assert template DB is created once per session; per-test DB is unique tmp_path | varies (likely 0 new tests; ~3-6 fixture refactors) |
| **T-5** (conditional) TestClient lifespan audit | Test-runtime | sweep across `tests/web/` | ONLY if T-1 profile data shows TestClient lifespan startup is a hotspot. `with TestClient(app) as client:` enters lifespan (starts `price_fetch_executor`); plain `TestClient(app)` does not. Many tests use `with` even when they don't need the executor. Mechanical sweep | 0 (no new tests; just `with` → no-with conversions on suitable tests) |
| **T-6** Final integration sweep + ruff | Both | `tests/integration/test_post_phase10_infra_bundle.py` (NEW; optional) + ruff sweep | Verify (a) cleanup-script extension is invokable in dry-run mode from a test or operator-witnessed manual run; (b) pytest-xdist baseline is operational; (c) ruff baseline preserved at 18 E501; (d) `verify_phase10.py` still exits 0 (no Phase 10 regression) | 0-5 (mostly integration smoke) |

**Projected test count delta: -5..+15 fast tests** (test additions for cleanup-script if PS test infrastructure justified + integration sweep; possibly negative if duplicate-fixture audits remove redundant tests).
**Projected test-runtime delta: ~6:00 → ~1.5-2:00 wall-clock** (~3-5x reduction at zero coverage cost).

### §0.4 Worktree husk cleanup (T-2 secondary verification)

Operator-witnessed run of the extended cleanup-script (elevated PowerShell required per existing script preflight) against the 7 husks pending:

1. `.worktrees/phase9-bundle-B-reconciliation-depth/`
2. `.worktrees/phase9-bundle-C-hypothesis-and-equity/`
3. `.worktrees/phase9-bundle-D-sector-tamper-hardening/`
4. `.worktrees/phase9-bundle-E-polish-and-phase10-handoff/`
5. `.worktrees/phase10-bundle-C-tier-and-deviation/` (orphan)
6. `.worktrees/phase10-bundle-D-capital-maturity-funnel/` (orphan)
7. `.worktrees/phase10-bundle-E-process-grade-trend-and-polish/` (orphan)

This verification happens at operator-witnessed gate post-merge (NOT in the implementer dispatch — requires elevated PowerShell + operator authorization). Dispatch brief gate §2 enumerates as S3.

### §0.5 26-lesson forward-binding catalog (inheritance only — no new lessons expected)

This dispatch is small enough that no new forward-binding lessons are expected. The 26 cumulative lessons from Phase 9 + 10 (per Sub-bundle E return report §9 + dispatch brief §0.6) carry forward but most are N/A for infrastructure-only work:

| # | Lesson | Applicability here |
|---|---|---|
| 1 | `__post_init__` validators | N/A (no new dataclasses) |
| 2-4, 7-15 | Transaction discipline / form discipline / HTMX failure surfaces / session-anchor / etc. | N/A (no new write paths; no new forms; no new routes) |
| 5 | `^def` grep for composition surfaces | YES — T-1 recon should grep `tests/conftest.py` for fixture surfaces + `swing/data/db.py:ensure_schema` callsites |
| 6 | Empirical-verification of brief assertions | YES — T-1 profile pass IS the verification |
| 17 | Statistical helper formula explicit pin | N/A |
| 18, 19, 20, 22, 25 | Cohort/cadence/units/filters/bounded-range | N/A (no metrics in this dispatch) |
| 21 | Relative-href toggles | N/A (no new toggles) |
| 23 | Plan-prescribed verbatim text → FIELD + rendering target | N/A (no new templates) |
| 24 | started_ts.date() session anchor | N/A (no new queries) |
| 26 | SQL ORDER BY tiebreaker | N/A (no new SQL) |

### §0.6 BINDING semantics — Cleanup-script `-DeregisterFirst` behavior

Per phase3e-todo entry + script architecture at `cleanup-locked-scratch-dirs.ps1` (lines 215-234 currently skip still-registered worktrees by-design):

**BINDING design:**

```powershell
# Add new param to script signature:
param(
  [string]$ProjectRoot = $PSScriptRoot,
  [switch]$DryRun,
  [string]$GrantUser = "$env:USERDOMAIN\$env:USERNAME",
  [switch]$NoConfirm,
  [switch]$SkipWorktrees,
  [switch]$DeregisterFirst   # NEW
)
```

**Implementation:**

1. When `$DeregisterFirst` is `$true`:
   - BEFORE the existing orphan-discovery loop, scan `git worktree list` output.
   - Filter to paths matching `^.+\.worktrees[\\/]+phase\d+.*` OR `^.+\.claude[\\/]+worktrees[\\/]+phase\d+.*` (project-precedent + skill-default paths).
   - For each matched path: run `git -C $ProjectRoot worktree remove --force $path` (which deregisters; on-disk delete may fail silently due to ACL lock — that's the expected pattern that creates the orphan for the existing pass to pick up).
   - Log each deregister attempt + outcome to console.
   - After deregister loop completes, the existing orphan-discovery pass scans `.worktrees/` + `.claude/worktrees/` + finds the new orphans + adds them to `$candidates`.

2. When `$DeregisterFirst` is `$false` (default; preserves shipped behavior):
   - SKIP the deregister loop entirely.
   - Existing orphan-discovery runs unchanged.

3. **Safety filter (BINDING):** the deregister scan path-pattern is the safety boundary. Only `phase<digits>-*` branch directories deregister; any other path is left alone. This protects in-flight worktrees (e.g., `post-phase10-infra-bundle` itself — this dispatch's branch name does NOT start with `phase\d+` so it's safe even if `-DeregisterFirst` is run while this dispatch is active in a worktree).

4. **Elevation check (already existing) preserved:** script aborts if not running elevated.

5. **DryRun (already existing) compatibility:** when both `-DryRun` AND `-DeregisterFirst` are passed, the deregister loop reports what WOULD be deregistered without actually calling `git worktree remove --force`.

**Discriminating test pattern (BINDING per phase3e-todo §3.1 lessons #6 + #15):**

- Create a sandbox repo with 2 worktree husks matching `phase\d+-*` + 1 matching `polish-bundle-2026-05-09` (non-matching).
- Run script with `-DeregisterFirst` + `-DryRun` → assert dry-run reports the 2 matching paths + does NOT report the non-matching path + does NOT actually call `git worktree remove`.
- Run script with `-DeregisterFirst` (no dry-run) against sandbox → assert the 2 matching are deregistered + the non-matching remains.

Test infrastructure for PowerShell is heavy; if the implementer judges the test cost too high, document the manual-verification steps inline in the return report + skip test-creation. Operator-witnessed gate S2 covers the manual verification.

### §0.7 BINDING semantics — pytest-xdist worker-safety review (T-1 recon → T-3 implementation)

Per phase3e-todo entry + the "moderately-sized" risks called out:

**T-1 recon BINDING:**

Identify any tests that bind to fixed ports, fixed file paths, or shared global state that would break under parallel execution. Likely candidates:

- **Pipeline lease tests:** `pipeline_runs` table single-lease semantics. Tests that exercise lease acquisition may race if 2 workers try at once. Audit `tests/pipeline/test_*lease*.py`.
- **Web tests with fixed-port app:** `swing web` defaults to 127.0.0.1:8080 but TestClient uses ASGI in-process; should be safe under xdist. Verify.
- **Tests writing to operator's actual swing.db:** any test that doesn't use `tmp_path` for its DB is xdist-unsafe. Audit via grep.
- **Tests writing to user-config.toml:** per existing CLAUDE.md gotcha "Tests that exercise `write_user_overrides` MUST monkeypatch BOTH `USERPROFILE` AND `HOME`" — these are already isolated by monkeypatch (USERPROFILE+HOME point at tmp_path); xdist-safe by construction.
- **Tests reading exchange_calendars:** the calendar object may have a process-wide cache; multiple workers loading it concurrently should be fine (read-only) but worth verifying.

**T-1 deliverable:** inline recon note (no commit) in return report capturing:
- Top-30 slowest tests by `--durations=30`.
- Any identified xdist-unsafe tests + the marker recommendation per test.
- Decision: which conditional tasks (T-4 + T-5) to execute based on profile data.

**T-3 implementation BINDING:**

```toml
# pyproject.toml [project.optional-dependencies] dev
"pytest-xdist>=3.5.0",
```

```toml
# pyproject.toml [tool.pytest.ini_options]
addopts = "-n auto"  # or "-n logical" / "-n N" if "auto" causes contention
```

**Discriminating tests (BINDING):**

- `test_pytest_xdist_is_installed`: import `xdist`; assert version ≥ 3.5.0.
- For each xdist-unsafe test identified in T-1: confirm the test passes BOTH serial AND xdist-parallel (the marker is the fix; without the marker the test must be xdist-safe by construction).

**Wall-clock measurement (BINDING per phase3e-todo entry):**

Run `python -m pytest -m "not slow" -q` THREE times serially (warm cache after first run) and capture median wall-clock. Run THREE times with xdist `-n auto` and capture median. Assert xdist median is at least 2x faster than serial. Document the actual ratio in return report §3.

### §0.8 BINDING semantics — Session-scoped schema fixtures (T-4 conditional)

**ONLY execute T-4 if T-1 profile data shows `ensure_schema` is meaningful.** Likely candidates per the existing test architecture:

- `tests/conftest.py:fresh_db` (or similar) — current implementation likely calls `ensure_schema(conn)` per test.
- `ensure_schema` walks 17 migrations on every call (~10-50ms per call × thousands of tests).

**T-4 implementation pattern (if executed):**

```python
@pytest.fixture(scope="session")
def db_template_path(tmp_path_factory):
    """Session-scoped template DB with schema applied once."""
    template = tmp_path_factory.mktemp("db_templates") / "template.db"
    with sqlite3.connect(template) as conn:
        ensure_schema(conn)
    return template

@pytest.fixture
def fresh_db(tmp_path, db_template_path):
    """Per-test fresh DB cloned from session template."""
    target = tmp_path / "swing.db"
    shutil.copy(db_template_path, target)
    return target
```

**Discriminating test (BINDING):**

- `test_session_template_db_created_once`: assert template DB exists + per-test DB is a copy (different path; same schema_version).
- `test_per_test_db_isolation`: assert writes to one test's DB do NOT bleed to another test's DB.

### §0.9 BINDING semantics — TestClient lifespan audit (T-5 conditional)

**ONLY execute T-5 if T-1 profile data shows TestClient startup is meaningful.**

**Pattern to find via grep:**

```python
# tests/web/test_*.py — current (entering lifespan):
with TestClient(app) as client:
    resp = client.get("/some-readonly-route")
    assert resp.status_code == 200
```

**Pattern to convert (when executor not needed):**

```python
client = TestClient(app)
resp = client.get("/some-readonly-route")
assert resp.status_code == 200
```

**Safety rule (BINDING per CLAUDE.md gotcha):** ANY test touching `app.state.price_fetch_executor` MUST use `with TestClient(app) as client:` (enters lifespan). Mechanical sweep MUST verify each `with`-removed test does NOT touch `app.state.*` or trigger background tasks.

**Discriminating test:** none specific. The sweep is mechanical + the existing test suite is the regression check.

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `post-phase10-infra-bundle`
- **Worktree directory:** `.worktrees/post-phase10-infra-bundle/`
- **BASELINE_SHA:** `d560218` (current main HEAD; Phase 10 closer housekeeping).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time.

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all tasks land + Codex chain converges + before final return-report: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefixes: `feat(scripts):` / `feat(tests):` / `chore(deps):` / `test(scripts):` / `chore(tests):` / `docs(post-phase10-infra):`.
- One commit per task; Codex-fix commits as `fix(post-phase10-infra): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → Codex iteration → return-report commit.
- **Orchestrator owns:** integration merge to main + post-merge operator-witnessed gate S2 (manual cleanup-script run against the 7 husks).

### §1.5 Verify command
```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~10..HEAD
python -m pytest -m "not slow" -q                # SERIAL baseline (compare to xdist below)
python -m pytest -m "not slow" -q -n auto        # PARALLEL with xdist
ruff check swing/ --statistics
python verify_phase10.py
.\cleanup-locked-scratch-dirs.ps1 -DryRun -DeregisterFirst   # dry-run smoke (no elevation needed for dry-run)
```

---

## §2 Operator-witnessed verification gate

3 surfaces; mostly inline since this is infrastructure-only:

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite (serial + parallel) + ruff + verify_phase10 | Inline | `python -m pytest -m "not slow" -q` GREEN at ~3252..~3272 fast tests serial; `python -m pytest -m "not slow" -q -n auto` GREEN at same count parallel; xdist median wall-clock measurably faster (target ≥2x; ideal 3-5x); `ruff check swing/` baseline 18 (E501); `python verify_phase10.py` exits 0. |
| **S2** | Cleanup-script `-DeregisterFirst` operator-witnessed run | **Operator-driven (elevated PowerShell)** | Operator runs the extended script in elevated PowerShell against the 7 husks pending. Acceptance: script enumerates the 7 paths (4 still-registered + 3 orphans); deregisters the 4 still-registered (`git worktree remove --force` succeeds at deregistration even if on-disk delete fails due to ACL lock); existing orphan-discovery picks up all 7 resulting orphans; takeown+icacls+Remove-Item clears all 7 on-disk dirs. Post-run: `git worktree list` shows ONLY the main repo + (if active) the bundle's own worktree. **REQUIRES ELEVATED POWERSHELL** — orchestrator surfaces to operator for plain-chat authorization OR operator runs after merge. |
| **S3** | Worktree teardown — this bundle's own worktree | Implementer/orchestrator | Post-merge: `git worktree remove --force .worktrees/post-phase10-infra-bundle` (may produce 8th orphan if ACL-locked; cleared by the same `-DeregisterFirst` extension when operator runs it). |

**Gate session well under ≤6-surface budget.** No browser gate needed (no UI changes).

**Chrome MCP NOT REQUIRED** for this dispatch — no operator-visible UI surfaces shipped.

---

## §3 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** (wraps `superpowers:subagent-driven-development` + Codex review).
- Skill inputs:
  - `PLAN_PATH=docs/post-phase10-infra-bundle-executing-plans-dispatch-brief.md` (this brief serves as the lightweight plan since no formal writing-plans is required)
  - `SUB_BUNDLE=infra` (single bundle; no sub-letter)
  - `BASELINE_SHA=d560218`
- **Expected Codex chain:** 1-3 rounds. This dispatch has minimal external interface; lower Codex value-add than any Phase 10 sub-bundle. Likely converges in 1 round.
- Iterate per-round fixes as `fix(post-phase10-infra): Codex RN <severity> #N — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §3.1 Codex value-add concentration

Adversarial review for this bundle typically catches:

- **`-DeregisterFirst` safety filter regex over-permissive** — Codex will check the regex matches ONLY `phase\d+-*` patterns; rejects everything else (defense against accidental deregister of in-flight branches).
- **`-DeregisterFirst` script aborts on first failed deregister** — Codex will check: if `git worktree remove --force` returns non-zero (which it likely does when ACL-locked on Windows), the script should treat that as informational (deregister IS what we want; on-disk failure is the expected pattern) NOT abort the loop.
- **DryRun + DeregisterFirst combination handling** — Codex will check both switches together produce reports without side effects.
- **pytest-xdist version pin** — Codex will check `>=3.5.0` (or whatever current stable) per xdist 3.x semantics (xdist_group support; SCM-level worker isolation).
- **`-n auto` cores vs logical** — Codex may flag that `auto` uses physical cores; if the machine has hyperthreading + the test suite is I/O bound (SQLite), `logical` may be faster. Document choice.
- **xdist-unsafe test markers missing** — Codex will check that any test identified in T-1 as xdist-unsafe carries `@pytest.mark.xdist_group(name="...")` OR `@pytest.mark.serial` (per pytest-xdist 3.x semantics).
- **T-4 session-fixture path uniqueness** — Codex will check `tmp_path_factory.mktemp(...)` produces unique paths per session per worker.
- **T-5 lifespan-not-needed conversions don't break tests touching app.state** — Codex will check the mechanical sweep does NOT remove `with` from tests that access `app.state.*` or trigger lifespan dependencies.

### §3.2 Per-task Codex-check pre-emption

| Task | Common Codex finding | Pre-emption |
|---|---|---|
| T-1 | None expected (pure recon) | Document inline in return report; capture profile data + worker-safety audit findings |
| T-2 | `-DeregisterFirst` regex too permissive | Strict `^.+\.worktrees[\\/]+phase\d+.*` + parallel `^.+\.claude[\\/]+worktrees[\\/]+phase\d+.*` patterns; explicit safety-rejection list documented |
| T-2 | Script aborts on expected ACL-lock | Treat non-zero exit from `git worktree remove --force` as informational; continue loop |
| T-2 | Test infrastructure too heavy for PowerShell | If implementer judges PowerShell test cost prohibitive, document inline in return report + skip test creation; operator-witnessed gate S2 covers verification |
| T-3 | `-n auto` not configured | `pyproject.toml [tool.pytest.ini_options].addopts = "-n auto"` (or document opt-in via CLI if pyproject default is undesired) |
| T-3 | xdist 3.x deprecated marker used | Use `xdist_group(name="...")` not the deprecated `xdist.dist_group` |
| T-3 | Wall-clock measurement not captured | 3 serial + 3 xdist runs; median compared; ratio in return report |
| T-4 | Session-fixture template not properly isolated per worker | Per-worker template via `tmp_path_factory` (which IS worker-isolated in xdist) |
| T-5 | Tests accessing `app.state.*` lose `with` | Mechanical sweep verifies each removed `with` does NOT touch `app.state.*` |
| T-6 | verify_phase10 regression | Run `python verify_phase10.py` exit 0 before committing T-6 |

---

## §4 Return report shape

After all tasks land + Codex chain converges + before final return-report commit, draft a return report at `docs/post-phase10-infra-bundle-return-report.md`:

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain.
3. Test count delta + ruff baseline delta + **test-runtime delta (serial vs parallel; ratio achieved)**.
4. Operator-witnessed verification surfaces (S1 inline OK; S2 cleanup-script run pending operator authorization; S3 worktree teardown pending merge).
5. T-1 recon findings — top-30 slowest tests + xdist-unsafe test list + conditional-task disposition (whether T-4 + T-5 executed).
6. Per-task deviations from the brief (if any) with rationale.
7. Codex Major findings ACCEPTED with rationale (if any).
8. Watch items for orchestrator (operator-witnessed gate S2; any test-runtime regressions caught by xdist; cleanup-script edge cases).
9. Worktree teardown status.
10. Composition-surface verification via `^def` grep (NEW helpers in `tests/conftest.py` if T-4 executed).
11. Any in-tree brief amendments (likely none).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over to implement the post-Phase-10 infrastructure bundle (cleanup-script -DeregisterFirst extension + test-runtime xdist/fixture-scope analysis) for swing-trading. Read-side / infrastructure-only; ZERO production-code changes.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\post-phase10-infra-bundle
BRANCH: post-phase10-infra-bundle
BASELINE_SHA: d560218  (per dispatch brief §1.1; HEAD of main BEFORE this brief commit)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\post-phase10-infra-bundle -b post-phase10-infra-bundle $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end:
  docs/post-phase10-infra-bundle-executing-plans-dispatch-brief.md

Step 2 — Read the source phase3e-todo entries:
  docs/phase3e-todo.md  (search for "2026-05-13 Post-Phase-10 standalone dispatches" + "Item 1" + "Item 2"; +  "2026-05-13 Phase 10 closer" section at line 1788+ for "Post-Phase-10 standalone dispatches (UNBLOCKED by Phase 10 close)" item list)

Step 3 — Read binding conventions:
  - CLAUDE.md (gotchas + project conventions; "Tests that exercise write_user_overrides MUST monkeypatch USERPROFILE + HOME" gotcha applies to any xdist worker-safety verification)
  - docs/orchestrator-context.md (orchestrator-role framing; Codex-driven discipline)
  - cleanup-locked-scratch-dirs.ps1 (existing script; understand the orphan-only discovery branch at lines 215-234 + the safety filter at line 271-277)

Step 4 — Verify worktree state:
  git rev-parse HEAD                       # expect current main HEAD (typically the dispatch brief commit)
  git status                               # expect clean
  python -m pytest -m "not slow" -q        # expect baseline GREEN (~3254 passed worktree-side; 1 skipped; 3 pre-existing fails NOT regressions). ~6:00 wall-clock — this IS the baseline to beat.
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"  # expect 17
  ruff check swing/ --statistics            # expect 18 E501
  python verify_phase10.py                  # expect exit 0
  git worktree list                         # expect 5 entries: main + 4 Phase 9 husks (B/C/D/E still registered)

Step 5 — Pre-implementation recon (T-1):
  python -m pytest -m "not slow" -q --durations=30 2>&1 | tail -50  # capture top-30 slowest
  grep -rn "TestClient(app)" tests/web/ | head -20  # T-5 audit candidates
  grep -rn "ensure_schema(conn)" tests/ | head -20  # T-4 audit candidates
  grep -rn "127.0.0.1\|0.0.0.0" tests/ | head -10  # xdist port-binding candidates
  grep -rn "fixed_port\|bind_port" tests/ | head  # xdist port-binding candidates

Step 6 — Invoke copowers:executing-plans:
  - PLAN_PATH: docs/post-phase10-infra-bundle-executing-plans-dispatch-brief.md
  - SUB_BUNDLE: infra
  - BASELINE_SHA: d560218

Step 7 — Execute tasks task-by-task per brief §0.3:
  - T-1 recon (no commit; document inline in PR description / return-report)
  - T-2 cleanup-script -DeregisterFirst extension (commit: feat(scripts): -DeregisterFirst switch for cleanup-locked-scratch-dirs.ps1 (T-2))
  - T-3 pytest-xdist baseline integration (commit: chore(deps): add pytest-xdist + configure -n auto baseline (T-3))
  - T-4 (CONDITIONAL on T-1 profile) session-scoped schema fixtures (commit: chore(tests): session-scoped DB schema fixtures (T-4) — IF EXECUTED)
  - T-5 (CONDITIONAL on T-1 profile) TestClient lifespan audit (commit: chore(tests): TestClient lifespan-not-needed conversions (T-5) — IF EXECUTED)
  - T-6 final sweep + ruff (commit: chore(post-phase10-infra): integration sweep + ruff (T-6))

Step 8 — Iterate Codex rounds until NO_NEW_CRITICAL_MAJOR. Expected 1-3 rounds.

Step 9 — Draft return report at docs/post-phase10-infra-bundle-return-report.md per dispatch brief §4. Commit it.

Step 10 — Remove-Item .copowers-subagent-active + signal orchestrator. Orchestrator drives operator-witnessed gate S2 (elevated PowerShell run of -DeregisterFirst extension against the 7 husks) + integration merge to main.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer
  - Skip the marker-file removal
  - Modify any production code in swing/ — this is INFRASTRUCTURE-ONLY (tests + scripts + deps)
  - Add ANY new schema (§A.0 LOCK from Phase 10 V1; EXPECTED_SCHEMA_VERSION stays at 17 unless §8.4 Corporate_Actions dispatch revises later)
  - Extend the -DeregisterFirst safety filter beyond `phase\d+-*` pattern (defense against accidental deregister of in-flight or operator-curated branches)
  - Use --DeregisterFirst as the DEFAULT — preserve shipped behavior with explicit opt-in switch
  - Skip the wall-clock measurement comparison (3 serial + 3 parallel; median ratio; documented in return report §3)
  - Mark a test as @pytest.mark.serial without justification — prefer xdist_group(name="...") which allows parallelism within the group
  - Run the cleanup-script with -DeregisterFirst against the worktree's OWN branch (the safety filter MUST reject `post-phase10-infra-bundle` since it does NOT match `phase\d+-*`)
  - Execute T-4 or T-5 unconditionally — both are CONDITIONAL on T-1 profile data; if `ensure_schema` is not a top-10 hotspot, skip T-4; if TestClient startup is not a hotspot, skip T-5
  - Schedule the next dispatch — operator will commission Schwab API integration after this bundle ships
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-13 (post-Phase-10-close).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `d560218` on main (Phase 10 closer housekeeping).
- **Worktree path (binding):** `.worktrees/post-phase10-infra-bundle/`.
- **Baseline test count:** ~3257 main / ~3254 worktree-side.
- **Baseline ruff count:** 18 (E501 only).
- **Baseline test runtime:** ~6:00 wall-clock at 3254 tests (~110ms/test).
- **Plan status:** dispatch brief serves as lightweight plan; no formal writing-plans dispatch.
- **Spec status:** N/A (infrastructure-only; no spec impact).
- **Expected dispatch wall-clock:** ~3-5 hr implementer + ~1-2 hr Codex.
- **Expected test count delta:** -5..+15 fast tests.
- **Expected test-runtime delta:** ~6:00 → ~1.5-2:00 (3-5x reduction at zero coverage cost).
- **Expected ruff delta:** 0 (baseline preserved).
- **Next:** post-merge handoff to NEW ORCHESTRATOR INSTANCE for Schwab API integration dispatch (operator-decided sequencing).

---

## §7 Watch items for orchestrator (post-bundle-ship)

1. **Operator-witnessed gate S2** — elevated PowerShell run of `-DeregisterFirst` extension against the 7 husks. Requires operator authorization (elevated PowerShell + production-write-equivalent for filesystem operations). Orchestrator surfaces to operator for plain-chat authorization.

2. **Worktree husk cleanup confirmation** — after S2 runs, verify `git worktree list` shows ONLY main + this bundle's worktree (which will become the 8th orphan post-merge, then cleared on the next `-DeregisterFirst` run).

3. **Test-runtime ratio achieved** — return report §3 enumerates serial vs parallel median. If ratio < 2x, investigate (likely SQLite contention OR xdist worker startup overhead at this test count — both addressable in follow-up dispatch).

4. **Conditional tasks (T-4 + T-5) executed?** — implementer's decision based on T-1 profile data. Both are zero-coverage-loss optimizations; orchestrator should review whether their non-execution is justified by profile data showing they wouldn't help.

5. **Handoff to new orchestrator instance for Schwab API** — operator commissions post-merge. The Schwab API dispatch is significantly larger scope (multi-day; brainstorm + writing-plans + executing-plans cycle); fresh orchestrator instance benefits from clean context window.

6. **Phase 10 plan + electives amendment LOCKED** — this dispatch does NOT modify Phase 10 plan or electives amendment. Any plan-text divergences in cleanup-script or test-runtime work are LOCAL to this dispatch's return report.

---

## §8 Dispatch order — UNCHANGED

Phase 10 ✓ → **post-phase10-infra-bundle (this dispatch)** → Schwab API integration (NEW ORCHESTRATOR INSTANCE; operator-decided).

Post-bundle-ship sequence:
1. Orchestrator drives operator-witnessed gate S2 + integration merge to main.
2. Orchestrator drafts post-merge housekeeping commit (CLAUDE.md status line + phase3e-todo entry).
3. Operator commissions NEW orchestrator instance with Schwab API integration handoff brief.

---

*End of dispatch brief. Post-Phase-10 infrastructure bundle. 2 backlog items consolidated (cleanup-script + test-runtime). 6 tasks (2 always + 2 conditional + 1 recon + 1 sweep). 3 gate surfaces (1 inline + 1 operator-witnessed elevated PowerShell + 1 worktree teardown). Zero production-code changes; zero new schema; zero new operator-facing routes. Pre-handoff hygiene for the larger Schwab API dispatch that follows.*
