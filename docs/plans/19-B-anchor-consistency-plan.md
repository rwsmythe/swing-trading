# Implementation Plan — 19-B: launch-context anchor consistency + lease-or-silent + broken-context guard

**Arc:** 19-B (Phase 19 — Launch-Context Robustness & Measurement Parity).
**Brief (binding spec):** [`docs/drumbeat-anchor-consistency-19b-commissioning-brief.md`](../drumbeat-anchor-consistency-19b-commissioning-brief.md) (SUPERSEDES `19185b04`; carries forward that brief's §1.5 HOME-vector analysis + §2.2 both-signals guard).
**Base:** `main` @ `24f316f8` (includes 19-A CALIBRATION-C, merged `fadc193d`). Schema **v31** (no change).
**§3 verdict:** SUB-TRIPWIRE (edits existing `monitoring/`/`pipeline/`/`config`/`web`/`scripts`; no schema, no new module, no dependency, no standing process, no `swing/trades`|`swing/data` carve-out). Guard + push semantics are RD's measurement/alarm lane → **RD plan-stage review (§8) + RD merge-blocking QA.**
**Deliverable of THIS dispatch:** the plan only. Executing is a separate dispatch AFTER the RD plan-stage review gate.

---

## §0. Re-grounded anchor sites (verified on disk at base `24f316f8`, 2026-07-03)

Every brief-cited anchor was grepped against live code. **All match** the brief §0 (the brief's cited line numbers are current):

| Role | Site | ACTUAL location @ `24f316f8` | What it does today |
|---|---|---|---|
| READ (shadow out) | `swing/pipeline/runner.py:1207` | `output_root = cfg.paths.exports_dir / "research"` in `_step_shadow_expectancy` | **config-derived** (correct root; the poison is the write/push not matching it) |
| READ (health compute) | `swing/pipeline/runner.py:1360-1361` | `compute_research_health(conn, cfg=cfg, exports_root=cfg.paths.exports_dir / "research")` | **config-derived** exports_root (explicit; de-coupled from the `__file__` default) |
| READ (compute default) | `swing/monitoring/research_health.py:1782-1789` (sig), `:1802-1805` (default) | `exports_root=None` → `RESEARCH_HEALTH_ARTIFACT_PATH.parent.parent` | `__file__`-anchored FALLBACK (not used by the runner, which passes explicit) |
| WRITE (artifact constant) | `swing/monitoring/stoplights.py:27-30` | `RESEARCH_HEALTH_ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "exports"/"research"/"health"/"latest.json"` | **`__file__`-anchored** → the editable-installed MAIN repo (LOCK-#4 shared reader/writer contract) |
| WRITE (accessor) | `swing/monitoring/stoplights.py:43-49` | `research_health_artifact_path()` returns the constant | the SINGLE seam both reader + writer resolve through |
| WRITE (atomic writer) | `swing/monitoring/research_health.py:236-264` | `write_research_health_artifact(status, out_path=None)` → `out_path=None` resolves via `research_health_artifact_path()` | single-source atomic write (C-NH4) |
| PUSH (comms root) | `swing/monitoring/research_health.py:285-291` | `_default_comms_root()` = `Path(__file__).resolve().parents[2] / "comms"` | **`__file__`-anchored** → MAIN's `comms/` |
| PUSH (helper) | `swing/monitoring/research_health.py:351-390` | `push_research_health_red_to_rd(status, *, run_id, prior_overall, comms_root=None)` | edge-triggered RED → role_mail post to rd |
| PUSH (fired) | `swing/pipeline/runner.py:1368-1369` | `_rh.push_research_health_red_to_rd(status, run_id=run_id, prior_overall=prior_overall)` (no `comms_root`) | uses `_default_comms_root()` → REAL comms |
| STEP call | `swing/pipeline/runner.py:1061` | `_step_research_health(cfg=cfg, run_id=lease.run_id)` | `lease.run_id` = genuine `pipeline_runs.run_id` int |
| WEB reader (stoplight) | `swing/monitoring/stoplights.py:137-145,148-227,229-244` | `_read_research_envelope()` / `read_validated_research_envelope()` / `_research_stoplight()` all call `research_health_artifact_path()` **with no cfg** | the 18-F reader — currently `__file__`-anchored |
| WEB reader (VM) | `swing/web/view_models/health.py:101` | `build_research_health_vm(conn, cfg)` → `read_validated_research_envelope()` (no cfg) | drill-down VM — same reader |
| WEB reader (wiring) | `swing/web/app.py:88-120`; `swing/web/routes/health.py:41-46` | both `apply_overrides(cfg)` then pass cfg down; the stoplight chain drops cfg at `_research_stoplight()` | cfg is available at both entry points but not threaded to the accessor |
| CONFIG resolution | `swing/config.py:633-635` | `project_root = config_path.parent.resolve()`; `_resolve_path` anchors `data/`,`exports/`,`reference/` to it (`:609,617-630`) | `exports_dir="exports"` (shipped, `swing.config.toml:16`) → `project_root/exports`; `db_path` HOME-anchored (`:614`) |

**The confirmed mechanism (restated):** READ is already config-derived (`cfg.paths.exports_dir`), but WRITE + PUSH are `__file__`-anchored → the editable-installed MAIN `swing` package → MAIN's `exports/` + `comms/` regardless of the launch context. A worktree/mis-cwd run reads its OWN (empty) exports → concludes drumbeat-RED → then writes that RED into MAIN's `latest.json` and pushes to MAIN's RD inbox. **Fix: make WRITE + PUSH config-derived to MATCH the already-config-derived READ.** The residual HOME-vector (an empty-DB read from a wrong-`HOME` launch; `db_path` is HOME-anchored, NOT config-anchored) is covered by the guard, not the anchor fix.

**No brief anchor diverged from live code — no STOP-and-flag discrepancy.**

---

## §1. Design overview

Three cooperating changes plus a structural test defense:

1. **Anchor consistency (root fix).** A single config-derived resolver produces the artifact path from `cfg`; a single config-derived resolver produces the comms root from `cfg`. The WRITE (runner + script + web-reader) and PUSH (runner) both resolve from `cfg`, matching the already-config-derived READ. LOCK-#4 preserved: the 18-F web reader AND the 18-D writer both resolve through the SAME cfg-aware accessor.
2. **Lease-or-silent (push gate).** `push_research_health_red_to_rd` posts ONLY when `run_id is not None` (a genuine leased `pipeline_runs.run_id`). Any unleased context (`run_id is None` — tests, standalone probe, ad-hoc worktree calls) logs a WARNING and posts nothing. This structurally kills the `run id: unknown` leak class.
3. **Broken-context guard.** Before writing/pushing, `_step_research_health` (and the standalone script, single-sourced) declines to write when the read looks broken-context-empty on EITHER signal: (i) shadow succeeded this run but its manifest is invisible to the health scan root; (ii) the DB read is detection-empty while a prior valid artifact witnesses that the system previously HAD detections. Broken ⇒ write nothing (leave prior `latest.json`), skip the push, log WARNING. Composes with C-NH5.
4. **Structural suite isolation (test defense; lands FIRST).** An autouse fixture forces the comms root to a per-test tmp dir for the WHOLE suite, so no test can reach the real `comms/` tree even if a future test regresses.

### 1.1 The LOCK-#4 anchor seam (explicit design)

Today, ONE accessor — `stoplights.research_health_artifact_path()` — is the single source both the 18-F reader and the 18-D writer resolve through, but it is `__file__`-anchored (no cfg). The fix keeps ONE accessor but makes it **cfg-aware**:

```python
# swing/monitoring/stoplights.py
def research_health_artifact_path(cfg=None) -> Path:
    """Shared research-health artifact path. When `cfg` is supplied, resolve
    from the config-derived exports dir (launch-context-consistent — reader and
    writer stay co-anchored per launch context, LOCK #4). When `cfg is None`,
    fall back to the __file__-anchored RESEARCH_HEALTH_ARTIFACT_PATH constant
    (the pure-accessor / test-monkeypatch contract)."""
    if cfg is not None:
        return cfg.paths.exports_dir / "research" / "health" / "latest.json"
    return RESEARCH_HEALTH_ARTIFACT_PATH
```

- **Where `project_root` comes from:** the artifact is derived directly from `cfg.paths.exports_dir` (already the config-derived, `_resolve_path`-anchored value). The comms root is derived from an EXPLICIT `cfg.project_root` (a new trailing defaulted field on `Config`, set by `load()`) via the `config_project_root(cfg)` accessor (§1.1.1) — NOT the fragile `exports_dir.parent` inference (Codex R1/R5 MAJOR).
- **The `__file__` constant is NOT deleted.** `RESEARCH_HEALTH_ARTIFACT_PATH` + `RESEARCH_HEALTH_ARTIFACT_PATH.parent.parent` (the `compute_research_health(exports_root=None)` default) remain as the cfg-less fallback. The `_research_stoplight`/VM readers pass cfg (below), so production is config-derived; the fallback only serves cfg-less callers (tests, and the standalone script which passes an explicit `out_path` anyway).
- **Both sides pass cfg:**
  - WRITER (runner): `write_research_health_artifact(status, out_path=research_health_artifact_path(cfg))`; `_read_prior_overall(research_health_artifact_path(cfg))`.
  - WRITER (script): already passes an explicit cfg-derived `out_path` (from `Config.from_defaults()` / `--out`) — unchanged in spirit.
  - READER (web stoplight): thread cfg down the chain `health_stoplights(conn, cfg)` → `_research_stoplight(cfg)` → `read_validated_research_envelope(cfg)` → `_read_research_envelope(cfg)` → `research_health_artifact_path(cfg)`.
  - READER (web VM): `build_research_health_vm(conn, cfg)` → `read_validated_research_envelope(cfg)`.
  - All reader-side params default to `cfg=None` (backward-compat: existing cfg-less test calls resolve to the `__file__` fallback and still pass).

**Why this preserves LOCK-#4:** the reader (context processor + VM both already hold the same `apply_overrides(cfg)`) and the writer (runner holds the same run cfg) now BOTH resolve the artifact through `research_health_artifact_path(cfg)` from the SAME per-launch cfg. In production both cfgs resolve to MAIN/exports; in a worktree both resolve to the worktree/exports; they never split (one config- + one `__file__`-anchored). The single-accessor single-source property is retained — cfg is just its input.

#### 1.1.1 The config-derived comms root (robust `project_root` on `Config`)

**Codex R1 MAJOR (adopted):** deriving the project root from `exports_dir.parent` is only safe for the shipped layout; a relocated/absolute `exports_dir` would re-split the anchor. So the project root is threaded EXPLICITLY from config loading (it is already computed there and discarded):

```python
# swing/config.py — Config dataclass gains a config-derived project_root
@dataclass(frozen=True)
class Config:
    paths: Paths
    ...
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    # NEW: the config-derived project root (= config_path.parent.resolve() at
    # load()). Defaulted so direct Config(...) constructions (tests) stay valid;
    # load()/from_defaults() always populate it.
    project_root: Path | None = None
```

`load()` already computes `project_root = config_path.parent.resolve()` (`config.py:635`) — pass it into the `Config(...)` return (and `from_defaults()` passes its computed root). Then a single accessor:

```python
# swing/config.py
def config_project_root(cfg) -> Path:
    """The config-derived project root — the ONE canonical source the comms
    root derives from. REQUIRES cfg.project_root (set by load()/from_defaults());
    RAISES if it is unset, so production can NEVER silently re-derive comms from
    a divergent exports_dir.parent (Codex R5 MAJOR — no silent-divergence
    fallback). Every production cfg comes from load() and carries it; a test
    double that reaches this must set project_root explicitly."""
    root = getattr(cfg, "project_root", None)
    if root is None:
        raise ValueError(
            "Config.project_root is unset; load()/from_defaults() must set it")
    return root
```

**No silent `exports_dir.parent` fallback (Codex R5 MAJOR — adopted).** The earlier draft fell back to `exports_dir.parent` for a cfg lacking `project_root`; that could re-anchor comms to the wrong root for a relocated/absolute `exports_dir`. Removed: `config_project_root` now RAISES on a missing `project_root`. Production is unaffected (every `load()`/`from_defaults()` cfg carries it); the best-effort push wrappers swallow the (never-in-production) raise → no push (safe). The `_Cfg`/`_Paths` test doubles set `project_root` explicitly (Task 4 / Task 6 test updates). The config seam is now the single canonical contract with NO divergent path.

```python
# swing/monitoring/research_health.py
def _comms_root_for(cfg) -> Path:
    from swing.config import config_project_root
    return config_project_root(cfg) / "comms"
```

- The runner passes `comms_root=_comms_root_for(cfg)` to the push helper. `_default_comms_root()` stays as the `__file__` fallback for the `comms_root=None` path (tests, cfg-less callers).
- **Why robust now:** `cfg.project_root` is the exact `config_path.parent.resolve()` (the real project root), independent of whatever `exports_dir` resolves to. A worktree run's cfg carries the worktree root; a MAIN run's cfg carries MAIN — comms tracks the true launch context. There is NO `exports_dir.parent` fallback -- `config_project_root` RAISES on a missing `project_root` (Codex R5 adopted; the removed-fallback design above); direct-construction test doubles set `project_root` explicitly (Task 4 / Task 6 test updates). (CHARC 2026-07-03 doc-scrub: this sentence previously mis-stated a surviving fallback.)
- **Construction back-compat:** `project_root: Path | None = None` is a trailing DEFAULTED field on the frozen dataclass → every existing positional/keyword `Config(...)` construction that omits it stays valid (the executing implementer greps `Config(` across `swing/` + `tests/` to confirm no positional construction is broken by a new trailing field; a trailing default field is safe for keyword and short-positional calls).
- **`apply_overrides` staleness (Codex R3 MAJOR — verified NOT a vector):** `apply_overrides` returns a NEW cfg via `dataclasses.replace(cfg, ...)`, which PRESERVES `project_root` (an unlisted field is copied). Verified on disk (`swing/config_overrides.py`): overrides mutate ONLY `schwab`/`integrations`/`reconciliation`/`logging` — **NEVER `paths`/`exports_dir`** (paths are not user-overridable). So the overridden cfg keeps BOTH the original `project_root` AND the original `exports_dir` → the comms root and the artifact path cannot split under overrides. **Forward guard (noted for the executing phase + any future override work):** IF a future override ever mutates a `paths` field, `project_root` must be re-derived in that same override (a test asserting `config_project_root(apply_overrides(cfg))` tracks any overridden `exports_dir` locks it). For 19-B this is a verified non-vector, not an open risk.

### 1.2 Lease-or-silent (the push gate)

**Two-part gate: `run_id is not None` in the helper (defense) + a DB lease-existence verification at the runner (the genuine-lease proof — Codex R3 CRITICAL adopted).**

The brief requires "a genuine `pipeline_runs` `run_id`" — so `run_id is not None` alone is insufficient (a forged/stale int would slip it). The runner VERIFIES the run_id exists in `pipeline_runs` (while the ro conn is open) and only pushes when verified:

```python
# swing/monitoring/research_health.py — a machine lease-existence check
def pipeline_run_exists(conn, run_id) -> bool:
    """True iff run_id is a real pipeline_runs row (a genuine leased run). The
    lease-or-silent PROOF: a forged/stale/nonexistent run_id is not in the DB
    -> no push. Degrade-gracefully: a missing pipeline_runs table -> False."""
    if run_id is None:
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM pipeline_runs WHERE run_id = ? LIMIT 1", (run_id,)
        ).fetchone()
        return row is not None
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return False
        raise

# swing/monitoring/research_health.py — the push helper is DEFAULT-DENY on an
# explicit lease proof (Codex R3/R4): it will not post unless the caller passes
# lease_verified=True (the caller having proven the run is a real pipeline_runs
# row) AND run_id is not None.
def push_research_health_red_to_rd(
    status, *, run_id, prior_overall, lease_verified=False, comms_root=None,
) -> bool:
    if not lease_verified or run_id is None:
        log.warning(
            "research-health RD push skipped: unverified/unleased context "
            "(lease_verified=%s, run_id=%s)", lease_verified, run_id)
        return False
    ...  # edge check, compose, post via _effective_comms_root(comms_root)
```

- **The lease proof lives in the HELPER's own gate (Codex R3 CRITICAL + R4 MAJOR — adopted).** `push_research_health_red_to_rd` is DEFAULT-DENY: `lease_verified` defaults to `False`, so ANY caller (current, direct, or future) that does not explicitly prove the lease posts NOTHING. The runner is the only caller that opts in — it computes `lease_verified=_rh.pipeline_run_exists(conn, run_id)` (a real `pipeline_runs` row) WHILE the ro conn is open and passes it. A forged/stale/nonexistent int is not a `pipeline_runs` row → `pipeline_run_exists` False → the runner passes `lease_verified=False` → no push. A hypothetical future caller that forgets to verify → `lease_verified` defaults False → no push. The gate is self-contained in the helper (Codex's "same seam that decides whether a push can happen").
- This closes the requirement: only a run that is BOTH a real `pipeline_runs` row AND explicitly lease-proven pushes — the brief's literal "genuine `pipeline_runs` run_id."
- Every production push is `runner.py:1061` → `run_id=lease.run_id` (a real, just-inserted `pipeline_runs` row) → `pipeline_run_exists` True → `lease_verified=True`. The standalone script never pushes; tests pass fake ints / omit `lease_verified` → no push (belt with the comms seam-guard).
- The 3 leaked pushes were `run id: unknown` = `run_id is None` — blocked; and the `lease_verified` default-deny blocks a fake-int leak even before the DB check.

**The single comms-root seam (Codex R2 CRITICAL — adopted).** `push_research_health_red_to_rd` resolves its comms root through ONE helper that EVERY call path consults — so a single test override closes ALL paths (default None AND explicit `comms_root=`):

```python
# swing/monitoring/research_health.py
def _effective_comms_root(comms_root) -> Path:
    """The ONE comms-root seam every push path consults. Explicit wins; else
    _default_comms_root(). Tests patch THIS to guard the real comms/ tree
    universally (both the default path and an explicit comms_root=)."""
    return comms_root if comms_root is not None else _default_comms_root()
```

The helper body uses `root = _effective_comms_root(comms_root)` (replacing the inline `comms_root if ... else _default_comms_root()`). Production is unchanged (explicit cfg root or default); the test fixture (§1.4) patches `_effective_comms_root` with a guard that redirects any real-repo-comms resolution to tmp.
- **Defense-in-depth note for RD:** the gate is `run_id is not None`, NOT a `pipeline_runs` existence query (the push helper has no live conn at push time — the runner closes the ro conn before the push, `runner.py:1362-1363`). A test that passed a *fake* int would slip this gate — but the structural autouse fixture (§1.4) forces the comms root to tmp for the whole suite, so a fake-int test still cannot reach real comms. Production code never passes a fake int. RD may request the stronger existence check (§8); if so it would require re-opening/keeping the conn — an explicit trade noted, not silently taken.

### 1.3 The broken-context guard (RD-reviewed distinguisher — MACHINE-READABLE)

**Codex R1/R2 MAJOR (adopted):** the guard keys on NO English strings. Both signals use machine-readable inputs: a direct DB `COUNT` for the current read, and a machine-readable `detection_count` stamped into the artifact envelope at WRITE time for the witness. The measurement computation (`compute_research_health`) is NOT touched — a `COUNT` for a write-decision is not a measurement write, and the envelope field is stamped by the writer path (not the locked compute).

A pure predicate in `research_health.py`, called by BOTH the runner step and the standalone script before the write/push:

```python
def should_suppress_broken_context_write(
    *, current_detection_count, exports_root, shadow_manifest_path, prior_env,
) -> tuple[bool, str | None]:
    """Return (suppress, reason). Suppress the write when the read looks
    broken-context-empty on EITHER signal. A pure function of machine-readable
    inputs (an int count + a dir-scan + the prior envelope dict); the caller
    queries db_detection_count(conn) while the conn is open and passes it as
    current_detection_count."""
    # Signal (i): shadow SUCCEEDED this run (wrote a manifest) but the health
    # scan root shows NO engine artifacts -> read/write anchors diverged or the
    # just-written manifest is invisible (a genuine FS/mis-root divergence).
    # Gated on shadow SUCCESS (manifest_path not None) so a genuine shadow
    # FAILURE / first-ever-run still writes its honest drumbeat-RED (we do NOT
    # hide a real never-ran / engine-down state).
    if shadow_manifest_path is not None and _newest_artifact_dir(exports_root) is None:
        return True, "shadow wrote a manifest but the health scan root is empty (anchor divergence)"
    # Signal (ii): the CURRENT DB read is detection-empty (a machine COUNT) AND
    # a prior valid artifact witnesses the system PREVIOUSLY HAD detections
    # (its machine-readable detection_count > 0) -> the DB lost its data (the
    # wrong-HOME empty-read vector; db_path is HOME-anchored).
    if current_detection_count == 0 and _prior_env_had_detections(prior_env):
        return True, "DB read is detection-empty but the prior artifact recorded detections>0 (wrong-HOME empty read?)"
    return False, None
```

Helpers:

```python
def db_detection_count(conn) -> int:
    """Machine-readable current-empty signal: COUNT of the detection log. Zero
    detections is the canonical empty-DB signal (a forward observation cannot
    exist without a parent detection, so zero detections => zero observations).
    Degrade-gracefully: a missing table (schema not yet applied) -> returns a
    large sentinel (treated as 'not empty' -> never suppress on a pre-schema DB)."""
    try:
        (n,) = conn.execute("SELECT COUNT(*) FROM pattern_detection_events").fetchone()
        return int(n)
    except sqlite3.OperationalError as exc:
        if _schema_unavailable(exc):
            return -1  # unknown -> caller's `== 0` is False -> never suppress
        raise

def _prior_env_had_detections(prior_env) -> bool:
    """The machine-readable 'the live system had data' witness. True iff the
    prior valid research_measurement envelope carries a machine-readable
    detection_count > 0. A missing/None/non-int detection_count (an OLD
    pre-19-B artifact, or a non-conformant envelope) -> False -> CONSERVATIVE
    no-suppress (never false-suppress a genuinely-fresh system; the anchor fix
    is the primary protection). The prior artifact lives under the config-
    anchored exports (decoupled from the HOME-anchored DB), so on a wrong-HOME
    empty-DB read with a correct cwd the good prior artifact witnesses the loss."""
    if not isinstance(prior_env, dict) or prior_env.get("monitor") != RESEARCH_MONITOR_ID:
        return False
    dc = prior_env.get("detection_count")
    return isinstance(dc, int) and not isinstance(dc, bool) and dc > 0
```

**Signal (ii) implements the brief's EXACT wording (Codex R4 MAJOR — scope-cited):** the brief §2.3 signal (ii) is verbatim "an empty-DB read (**zero detections/observations**)." `current_detection_count == 0` IS that predicate: a `pattern_forward_observations` row cannot exist without a parent `pattern_detection_events` row (FK), so `COUNT(detections) == 0 ⟺ the temporal log is empty ⟺ zero detections/observations`. The guard is NOT trying to detect "any wrong-but-populated db" (a wrong-HOME db that happens to hold OTHER real detections is NOT an "empty read" — it is out of signal-(ii) scope by the brief, and is separately governed by anchor-consistency + the lease-verification, which fires from the run's own db). So keying on the detection-log emptiness is the brief's literal signal, not a narrower proxy. (The executing implementer MAY add a redundant `COUNT(observations)==0` belt; it is implied by the FK.)

**The `detection_count` envelope field (write-side, single-source-preserving; tolerance PROVEN, not assumed — Codex R4 MAJOR):** the artifact writer gains an OPTIONAL `extra: dict | None` param that merges into the top-level envelope dict AFTER `status.to_dict()`; the runner/script pass `extra={"detection_count": <the count they queried>}`. This keeps ONE writer (`write_research_health_artifact` — the single-source LOCK preserved; extended, not forked). **The artifact is a GITIGNORED RUNTIME FILE, not a schema-versioned contract** — it has no migration concept; its ONLY contract is the reader, and the reader's tolerance of the extra key is PROVEN by a required Task-5 round-trip test (write an envelope WITH `detection_count` → `read_validated_research_envelope` returns it valid AND the drill-down VM builds), NOT merely asserted by inspection. **All consumers enumerated + verified tolerant:** the 18-F reader (`read_validated_research_envelope` gates only on `monitor`/`overall`/`generated_ts`/`checks`), `_read_prior_overall`/`_read_prior_env` (our own), and the drill-down VM (via the reader) — none enforce a closed top-level shape. So the NEXT run reads the field as the machine-readable witness; an artifact written before 19-B lacks the field → witness False → conservative no-suppress (safe). If a FUTURE consumer ever wanted a closed schema, the Task-5 test is the tripwire that would fail first.

**The real-empty-vs-broken-context distinguisher (the RD crux — §8), all machine-readable:**

| Scenario | current DB `COUNT(detections)` | prior artifact `detection_count` | suppress? | correct? |
|---|---|---|---|---|
| Fresh system, never had detections (genuine empty) | 0 | absent / 0 / no prior | NO (witness False) | ✅ writes the honest green "n/a" (RD's blessed genuine-empty behavior) |
| Mature system, sudden empty-DB read (wrong HOME) | 0 | > 0 | YES | ✅ preserves the good prior `latest.json` |
| Shadow succeeded but its manifest invisible to health (anchor divergence) | any | any | YES (signal i) | ✅ declines a mis-rooted write |
| Genuine shadow FAILURE / first-ever run, no manifest | (n/a) | absent | NO (signal i gated on shadow success) | ✅ writes the honest drumbeat-RED (real engine problem surfaced, not hidden) |
| Normal healthy run | > 0 | > 0 | NO | ✅ writes fresh |
| Old pre-19-B prior artifact (no `detection_count`) + empty DB | 0 | missing field | NO (conservative) | ✅ never false-suppress; the anchor fix protects; the NEXT run's artifact carries the field |

**No English-string coupling (Codex R1/R2 MAJOR — designed out):** the current signal is a machine `COUNT`; the witness is the machine `detection_count` field. Neither reads a summary/detail string. The measurement computation is untouched (a COUNT for a write-decision is not a measurement write; the envelope field is stamped by the writer path, not the locked compute). This resolves the brittleness Codex flagged twice.

**Suppression is NOT over-broad (Codex R3 MAJOR — the context-divergence proof is the append-only invariant):** the worry is that `current==0 AND prior>0` fires on a "genuine empty-but-correct" run. But `pattern_detection_events` is an **APPEND-ONLY research log** — verified on disk: there is NO `DELETE FROM pattern_detection_events` anywhere in `swing/`. So a CORRECT db that once had `detection_count>0` can NEVER legitimately read 0 on a later run — a `>0 → 0` transition on the same correct db is IMPOSSIBLE by construction. The only ways to read 0 after a prior `>0` are: (a) a DIFFERENT db (the wrong-HOME vector — exactly the target), or (b) a deliberate full research-log reset (a rare operator maintenance op, for which "leave the prior artifact + let the 7-day staleness gate grey it" is the correct, self-healing outcome — NOT a false-suppress that hides live data). So the append-only invariant IS the direct context-divergence signal Codex asked for; no additional launch-context proof is needed. (The executing implementer confirms no production delete path exists before relying on this — the grep is the proof.)

**Guard scope note:** the standalone script runs against the correct HOME DB (`~/swing-data/swing.db`) and writes its own tree — its broken-context risk is low, but it calls the SAME single-sourced predicate (`shadow_manifest_path=None` → signal (i) never fires there; signal (ii) still applies as belt). Consistency + single-source over a script-specific carve-out.

### 1.4 Structural suite isolation (test defense — MUST land FIRST)

**Ordering is load-bearing:** a pre-fix full-suite run itself leaks a real push to RD's production T1 channel (the `test_step_writes_no_status_column` leak, §3). So the executing implementer front-loads this fixture as **Task 1** — BEFORE any full-suite run — so the very first suite run is already contained.

An autouse, function-scoped fixture in `tests/conftest.py` (alongside the existing `_redirect_home_away_from_real_swing_data` home-redirect autouse) that guards the SINGLE comms-root seam `_effective_comms_root` (§1.2) — universally, for BOTH the default path and an explicit `comms_root=`:

```python
@pytest.fixture(autouse=True)
def _guard_research_health_comms(tmp_path_factory, monkeypatch):
    """Universal prevention: no test can resolve a research-health push to the
    REAL repo comms/ tree. Wrap the ONE seam _effective_comms_root so that any
    resolution landing under <repo>/comms is REDIRECTED to a per-test tmp dir;
    a resolution already under tmp (a test's own comms_root=, or the cfg-derived
    tmp root) passes through unchanged. Covers the default path AND an explicit
    comms_root= — the single-seam property (Codex R2 CRITICAL)."""
    import swing.monitoring.research_health as _rh
    repo_comms = (Path(_rh.__file__).resolve().parents[2] / "comms").resolve()
    safe_tmp = tmp_path_factory.mktemp("comms_isolation")
    real_resolver = _rh._effective_comms_root
    def _guarded(comms_root):
        root = real_resolver(comms_root)
        try:
            resolved = Path(root).resolve()
        except Exception:
            return root
        if resolved == repo_comms or repo_comms in resolved.parents:
            return safe_tmp  # redirect ANY real-repo-comms resolution to tmp
        return root          # tmp roots (test tmp, cfg-derived tmp) pass through
    monkeypatch.setattr(_rh, "_effective_comms_root", _guarded)
    yield
```

- monkeypatch is undone per-test. Because EVERY push path resolves through `_effective_comms_root` (§1.2), this ONE patch closes ALL of them — the default `comms_root=None` path AND any test that explicitly passes a real `comms_root=<repo>/comms`. A test passing its own tmp `comms_root=` (e.g. `test_step_edge_posts_to_rd_end_to_end`) is a tmp root → passes through unchanged → no existing test breaks. This is Codex's "single overridable root seam that all call paths consult," and it PREVENTS the write before it happens (not just detects it after).
- The runner tests that legitimately verify cfg-derived comms routing (§Task 6) use tmp `exports_dir` → `_comms_root_for(cfg)` is a tmp root → passes the guard through → the assertion on the tmp comms holds.

**Second belt — a session-scoped zero-real-comms tripwire (universal DETECTION + suite-fail):**

```python
@pytest.fixture(scope="session", autouse=True)
def _fail_suite_on_real_comms_write():
    """Universal backstop: snapshot the FULL REAL repo comms/ file set at
    session start and assert it is UNCHANGED at session end — catches ANY
    ADD or REMOVE under the real comms tree (not just inbox/*.md), including a
    test that explicitly passes a real comms_root or a future push path that
    forgets the seam. Detection + suite-fail; prevention is the function
    fixture above."""
    from pathlib import Path
    repo_comms = Path(__file__).resolve().parent.parent / "comms"  # tests/ -> repo root
    def _snapshot() -> set:
        return {p for p in repo_comms.rglob("*") if p.is_file()} if repo_comms.exists() else set()
    before = _snapshot()
    yield
    after = _snapshot()
    added, removed = after - before, before - after
    assert not added and not removed, (
        f"tests mutated the REAL comms tree; added={sorted(added)} removed={sorted(removed)}")
```

- The session tripwire computes the real repo comms path DIRECTLY (from `tests/conftest.py`'s `__file__`), independent of any function-scoped patch, and snapshots the WHOLE `comms/` file set recursively → it fails on ANY added OR removed file (Codex R3 MAJOR — the deletions gap closed).
- **Overwrite-in-place is not a reachable push vector:** the push writes via `role_mail.post_message`, which stages a tmp then `os.replace`s into a NEW timestamped `<recipient>/inbox/<ts>-<n>.md` filename — it NEVER overwrites an existing message or deletes one. So a create/remove set-diff is complete for the actual mechanism; content-hashing every file is unnecessary machinery (noted so the executing phase does not over-build).
- Together: the function fixture is universal PREVENTION (the single-seam guard redirects any real-repo resolution to tmp before the write); the session fixture is a belt DETECTION over the whole tree (fails the suite if anything ever slips through — a future push path that forgets the seam still creates a NEW file → caught). Prevention + detection = the true universal backstop.

---

## §2. The identified leaking test (pin)

**`tests/pipeline/test_step_research_health.py::test_step_writes_no_status_column`** — the SUCCESS-path branch (line ~232-235).

Why it leaks (traced on disk):
1. `_seed_green_db(db)` seeds one detection + one terminal observation → coverage green, finiteness green.
2. `_patch_artifact(tmp_path, monkeypatch)` monkeypatches `stoplights.research_health_artifact_path` to `tmp_path/health/latest.json` (absent) → `_read_prior_overall()` returns None (prior absent).
3. The success-path call `runner._step_research_health(cfg=_Cfg(db, tmp_path / "exports"))` passes **no `run_id`** → defaults to `None`, AND seeds **no engine manifest** under `cfg.paths.exports_dir/research` (`tmp_path/exports/research` does not exist).
4. Inside compute, `_check_drumbeat_liveness` finds no artifact dir → **RED "drumbeat never ran (no engine artifacts on disk)"** → `overall="red"`.
5. `_step_research_health` then calls `push_research_health_red_to_rd(status, run_id=None, prior_overall=None)` with **no `comms_root`** → `_default_comms_root()` → the **REAL `comms/rd/inbox/`**; edge = red AND prior(None) != red → **fires → posts with `run id: unknown`.**

This exactly matches RD's evidence: one leak per suite run, `run id: unknown`, drumbeat-RED, and the production `latest.json` stayed GREEN (the artifact is patched to tmp — only the PUSH default leaks, not the artifact write). Every other test in the two candidate files either passes `comms_root=`, monkeypatches `_default_comms_root`/the push, or computes green — none leak. (The full-pipeline path passes a real `run_id`, so it is not the `run id: unknown` source.)

**Three-layer fix (all specified below):** (a) lease-or-silent gate (`run_id=None` → no push) — kills THIS leak in production code; (b) the structural autouse comms fixture — belt for any future test; (c) the test itself becomes hermetic by the autouse fixture (and stays valid: its assertion is `status_calls == []`, unaffected by the push gate). The executing implementer verifies the test still passes and that no real comms file is produced.

---

## §3. Task breakdown (TDD; minimal red→green→commit per task)

Ordering is deliberate: the structural isolation fixture lands FIRST (before any full-suite run); the anchor seam + gate + guard follow; the reader-threading + script single-sourcing close the loop.

### Task 1 — Structural suite-isolation autouse fixtures + the `_effective_comms_root` seam (LANDS FIRST)
- **Files:** `swing/monitoring/research_health.py` (add the `_effective_comms_root(comms_root)` seam from §1.2 and route the existing `push_research_health_red_to_rd` body through it — a pure refactor, no behavior change yet); `tests/conftest.py` (add BOTH autouse fixtures from §1.4: the function-scoped `_guard_research_health_comms` seam-guard AND the session-scoped `_fail_suite_on_real_comms_write` tripwire).
- **Test (red→green):** `tests/monitoring/test_research_health_comms_isolation.py`:
  - `test_effective_comms_root_guarded_redirects_real_repo_comms` — under the autouse fixture, `_effective_comms_root(<repo>/comms)` AND `_effective_comms_root(None)` (the default → repo comms) both return a tmp path OUTSIDE the repo comms tree; `_effective_comms_root(<a tmp path>)` passes the tmp path through. Pre-fix (no seam-guard): returns the real repo comms → fails.
  - `test_push_with_explicit_real_comms_lands_in_tmp` — `push_research_health_red_to_rd(red, run_id=1, prior_overall="green", comms_root=<repo>/comms)` writes NOTHING under the real repo comms (the seam guard redirected to tmp). This is the exact bypass Codex R2 CRITICAL raised.
- **Discriminator check:** compute the pre-fix value (real `<repo>/comms`) vs post-fix (tmp) to prove the assertion distinguishes.
- **Commit:** `test(monitoring): 19-B Task 1 — single comms-root seam + autouse guard + session zero-comms tripwire`.

### Task 2 — Lease-or-silent push gate (default-deny `lease_verified`) + `pipeline_run_exists`
- **Files:** `swing/monitoring/research_health.py` (add `lease_verified: bool = False` to `push_research_health_red_to_rd` with the default-deny gate per §1.2; add `pipeline_run_exists(conn, run_id)`).
- **Tests (red→green):**
  - `test_unverified_lease_does_not_post` — a RED status, prior green, `run_id=104`, `lease_verified=False` (default), explicit tmp `comms_root` → `posted is False`, inbox empty, WARNING logged. Pre-fix (no gate): edge fires → posts → `posted is True` (FAILS). Post-fix: default-deny returns False.
  - `test_run_id_none_does_not_post` — `run_id=None, lease_verified=True` → `posted is False` (the run_id-None belt).
  - `test_verified_lease_posts` — `run_id=104, lease_verified=True, prior_overall="green"` → posts one file (the gate is not over-tight).
  - `test_pipeline_run_exists` — seed a `pipeline_runs` row id=5 → `pipeline_run_exists(conn, 5) is True`; `pipeline_run_exists(conn, 999) is False`; missing table → False; `run_id=None` → False.
- **Existing-test update (18-H.7 helper tests):** every `test_research_health_rd_push.py` test that expects a POST (`test_red_with_prior_not_red_...`, `test_first_ever_red_absent_prior_posts`, the content tests) now passes `lease_verified=True` (they already pass real int run_ids). The non-posting tests (`test_red_with_prior_red_...`, `test_yellow_...`, `test_green_...`) are unaffected (they don't post regardless). Compute each under the default-deny gate to confirm intent preserved.
- **Commit:** `feat(monitoring): 19-B Task 2 — default-deny lease-verified RD push gate + pipeline_run_exists`.

### Task 3 — cfg-aware artifact-path accessor (the LOCK-#4 seam)
- **Files:** `swing/monitoring/stoplights.py` (`research_health_artifact_path(cfg=None)` per §1.1).
- **Tests (red→green):**
  - `test_artifact_path_cfg_derives_from_exports_dir` — a fake cfg with `paths.exports_dir=/tmp/x/exports` → accessor returns `/tmp/x/exports/research/health/latest.json`. Pre-fix (no param): `TypeError`/ignores cfg → returns the `__file__` constant → FAILS.
  - `test_artifact_path_cfg_none_returns_file_constant` — `research_health_artifact_path()` == `RESEARCH_HEALTH_ARTIFACT_PATH` (fallback preserved).
- **Commit:** `feat(monitoring): 19-B Task 3 — cfg-aware research_health_artifact_path accessor (LOCK #4 seam)`.

### Task 4 — Config-derived comms root (explicit `project_root`)
- **Files:** `swing/config.py` (add the defaulted `project_root: Path | None` field on `Config`; populate it in `load()` from the already-computed `config_path.parent.resolve()` and in `from_defaults()`; add the `config_project_root(cfg)` accessor per §1.1.1); `swing/monitoring/research_health.py` (add `_comms_root_for(cfg)` calling `config_project_root`).
- **Tests (red→green):**
  - `test_load_sets_project_root` — `load(<tmp>/swing.config.toml)` → `cfg.project_root == <tmp>` (the config-file parent, resolved).
  - `test_config_project_root_prefers_explicit` — a cfg with `project_root=/p` and `exports_dir=/other/exports` → `config_project_root(cfg) == /p` (NOT `/other`).
  - `test_config_project_root_raises_without_project_root` — a cfg with `project_root=None` → `config_project_root(cfg)` raises `ValueError` (no silent `exports_dir.parent` divergence — Codex R5 MAJOR).
  - `test_comms_root_for_derives_from_project_root` — cfg `project_root=/p` → `_comms_root_for(cfg) == /p/comms`.
  - `test_default_comms_root_unchanged_fallback` — `_default_comms_root()` still `<repo>/comms` (the cfg-less fallback intact).
- **Discriminator note:** `test_config_project_root_prefers_explicit` uses a cfg whose `exports_dir.parent` ≠ `project_root` so it PROVES the accessor prefers the explicit field (the exact robustness Codex R1 MAJOR required).
- **Commit:** `feat(config): 19-B Task 4 — explicit config project_root + config-derived comms root`.

### Task 5 — Broken-context guard predicate + machine-readable signals (single-sourced)
- **Files:** `swing/monitoring/research_health.py` (`should_suppress_broken_context_write` + `db_detection_count(conn)` + `_prior_env_had_detections` per §1.3; a best-effort `_read_prior_env(out_path)` raw-parse helper mirroring `_read_prior_overall`, never raises; the `extra:` param on `write_research_health_artifact` per §1.3).
- **Tests (red→green), pure-predicate + count-helper unit tests:**
  - signal (i): `shadow_manifest_path=<a path>` + `exports_root` empty → `(True, ...)`; `shadow_manifest_path=None` + empty exports → `(False, None)` (genuine failure not hidden); `shadow_manifest_path=<path>` + exports with an artifact → `(False, None)`.
  - signal (ii): `current_detection_count=0` + prior env `{detection_count: 5}` → `(True, ...)`; `current_detection_count=0` + prior env `{detection_count: 0}` → `(False, None)` (genuine fresh); `current_detection_count=0` + prior env `{}` (old, no field) → `(False, None)` (conservative); `current_detection_count=0` + prior env None → `(False, None)`; `current_detection_count=3` + any prior → `(False, None)`.
  - `db_detection_count`: seeded DB with N detections → N; empty DB → 0; missing table → -1 (never suppresses).
  - `_prior_env_had_detections`: `{monitor: "research_measurement", detection_count: 5}` → True; wrong monitor id → False; `detection_count: True` (bool) → False (bool-is-int guard); missing → False.
  - `write_research_health_artifact(status, out_path, extra={"detection_count": 7})` → the written JSON top-level carries `"detection_count": 7` AND still validates through `read_validated_research_envelope` (extra key ignored by the reader).
  - `_read_prior_env`: absent → None; unparseable → None; valid → dict (never raises, incl. deeply-nested RecursionError → None, mirroring `_read_prior_overall`'s broad guard).
- **Discriminator note:** the count helper is exercised against a REAL seeded DB (real `insert_detection_event` rows), and the writer round-trip against the real reader — machine-readable end to end, no hand-built envelope shortcut for the load-bearing paths.
- **Commit:** `feat(monitoring): 19-B Task 5 — broken-context guard + machine-readable detection_count signals`.

### Task 6 — Wire anchor consistency + gate + guard into `_step_research_health` + `_step_shadow_expectancy`
- **Files:** `swing/pipeline/runner.py`.
  - `_step_shadow_expectancy` returns the written manifest `Path` on success, `None` otherwise (it already computes `manifest_path`; add the return; all existing failure/early-return branches `return None`). The run wiring (`runner.py:1036-1051`) captures `shadow_manifest = _step_shadow_expectancy(...)` (defaulting None on the except path).
  - `_step_research_health(*, cfg, run_id=None, shadow_manifest_path=None)`:
    1. `artifact_path = research_health_artifact_path(cfg)`; `prior_overall = _rh._read_prior_overall(artifact_path)`; `prior_env = _rh._read_prior_env(artifact_path)`.
    2. open ro conn; `status = compute_research_health(conn, cfg=cfg, exports_root=cfg.paths.exports_dir/"research")`; `det_count = _rh.db_detection_count(conn)`; `lease_ok = _rh.pipeline_run_exists(conn, run_id)` (ALL while the conn is open); close conn (finally).
    3. `suppress, reason = _rh.should_suppress_broken_context_write(current_detection_count=det_count, exports_root=cfg.paths.exports_dir/"research", shadow_manifest_path=shadow_manifest_path, prior_env=prior_env)`.
    4. if `suppress`: `log.warning("research-health write suppressed (broken context): %s", reason)`; ALSO emit a `warnings_json` run-warning (`step="research_health"` + the suppress `reason`) per gotcha #27 -- **RD 8.1(b) RULING, REQUIRED**: a recurring broken-context launch MUST surface in the run ledger + GUI warning surface, not only pipeline.log (wire via the runner's established run-warnings accumulation -- the executing implementer greps how `_step_*` append to the run `warnings_json`; add a discriminating test asserting the run-warning is present on BOTH suppress vectors [empty-DB + invisible-manifest]); **return** (no push, no write — composes with C-NH5).
    5. else: push (defensive try/except) with `run_id=run_id, prior_overall=prior_overall, lease_verified=lease_ok, comms_root=_rh._comms_root_for(cfg)` — the helper's default-deny gate posts only when `lease_ok`; then ALWAYS `write_research_health_artifact(status, out_path=artifact_path, extra={"detection_count": det_count})` (stamps the machine-readable witness for the NEXT run).
  - **New tests:** `test_step_skips_push_when_run_id_not_in_pipeline_runs` — a RED edge + `run_id=999` (NOT a `pipeline_runs` row) → no push (`comms` inbox empty), but the artifact STILL writes. Pre-fix (run_id-not-None only): the push fires. Post-fix: the DB verification blocks it. `test_step_pushes_when_run_id_is_real_pipeline_run` — seed a real `pipeline_runs` row with that run_id → the push fires (verifies the gate is not over-tight).
  - Call-site update `runner.py:1061`: `_step_research_health(cfg=cfg, run_id=lease.run_id, shadow_manifest_path=shadow_manifest)`.
- **Tests (red→green):**
  - `test_step_writes_to_cfg_derived_artifact_path` — cfg `exports_dir=tmp/exports` + a seeded fresh manifest there → the artifact lands at `tmp/exports/research/health/latest.json` (config-derived), NOT the `__file__` path. Pre-fix: writes via the `__file__` accessor. (This is the anchor-consistency discriminator; see §4.)
  - `test_step_pushes_to_cfg_derived_comms_root` — a RED edge + `run_id=104` + cfg `exports_dir=tmp/exports` → the push lands under `tmp/comms/rd/inbox/`, NOT the real comms. (Combined with the autouse fixture, assert the file is under the cfg-derived tmp comms.)
  - `test_step_suppresses_on_broken_context_empty_db` — seed a prior artifact (cfg-derived path) recording detections, an empty DB (zero detections), `shadow_manifest_path=None` → the step writes NOTHING and the prior artifact is byte-identical; no push.
  - `test_step_suppresses_on_shadow_manifest_invisible` — `shadow_manifest_path=<a path>` + `cfg.paths.exports_dir/research` empty → no write, prior preserved.
  - `test_step_writes_on_genuine_empty` — empty DB, prior absent (or prior "n/a") → writes the honest green "n/a" (not suppressed).
- **Update the existing pin tests that the wiring changes:**
  - `test_step_research_health.py::test_runner_invokes_step_via_step_guard_between_shadow_and_complete` (line 262-264): the asserted source substring `'_step_research_health(cfg=cfg, run_id=lease.run_id)'` changes to include `shadow_manifest_path=` — update the assertion to the new call string; keep the `shadow_i < research_i < complete_i` ordering assertion.
  - The `_patch_artifact`-based tests (`test_step_runs_and_writes_latest_json`, `test_step_reads_manifest_from_cfg_exports_dir_not_default_root`, `test_step_uses_readonly_conn`, `test_failing_compute_does_not_write_and_leaves_prior_artifact`, `test_step_writes_no_status_column`, and the 18-H.7 wiring tests): after Task 6 the runner resolves the artifact via `research_health_artifact_path(cfg)`, so a `_Cfg(db, exports_dir)` fake now determines the artifact path (`exports_dir/research/health/latest.json`). Re-point these fakes/assertions to the cfg-derived path (set `exports_dir=tmp/exports` and assert/seed the artifact under `tmp/exports/research/health/latest.json`); the `stoplights.research_health_artifact_path` monkeypatch is no longer the resolution seam for the runner path. Preserve each test's INTENT (readonly conn, C-NH5 no-write-on-failure, no-status-column, ordering, push-raises-still-writes). **Compute each re-pointed assertion under both the old and new resolution to confirm it still distinguishes.**
  - **Lease-verification ripple (Task 2 → the runner push tests):** the runner now passes `lease_verified=pipeline_run_exists(conn, run_id)`, so the 18-H.7 end-to-end push tests (`test_step_edge_posts_to_rd_end_to_end`) MUST seed a `pipeline_runs` row with the test's `run_id` (else `pipeline_run_exists` False → no push → the test's "one file posted" assertion fails). Add the `pipeline_runs` seed. The `test_step_runtime_ordering_read_prior_then_push_then_write` push-spy signature gains `lease_verified` (and seeds the row so `lease_ok` is True). The `_Cfg`/`_Paths` fakes may add a `project_root` attr (or rely on the `exports_dir.parent` fallback) so `_comms_root_for` resolves a tmp comms.
- **Commit:** `feat(pipeline): 19-B Task 6 — anchor-consistent write/push + broken-context guard in _step_research_health`.

### Task 7 — Thread cfg through the 18-F web reader (LOCK-#4 reader side)
- **Files:** `swing/monitoring/stoplights.py` (`_read_research_envelope(cfg=None)`, `read_validated_research_envelope(cfg=None)`, `_research_stoplight(cfg=None)`, `health_stoplights(conn, cfg)` passes cfg into `_research_stoplight`); `swing/web/view_models/health.py` (`build_research_health_vm` passes cfg into `read_validated_research_envelope(cfg)`). All reader params default `cfg=None` → `__file__` fallback (existing cfg-less tests unaffected).
- **Tests (red→green):**
  - `test_web_reader_reads_cfg_derived_artifact` — write a valid envelope at a cfg-derived tmp exports path; `read_validated_research_envelope(cfg)` returns it; a DIFFERENT `__file__`-path artifact is NOT read. Pre-fix: reader ignores cfg → reads the `__file__` path → returns None/other → FAILS.
  - `test_web_reader_cfg_none_unchanged` — `read_validated_research_envelope()` (no cfg) still resolves the `__file__` path (backward-compat).
  - A stoplight-level test: `health_stoplights(conn, cfg)` lights from the cfg-derived artifact (reader/writer co-anchored) — assert the research stoplight color matches an envelope written at the cfg-derived path.
- **Commit:** `feat(web): 19-B Task 7 — thread cfg through the research stoplight reader (LOCK #4 co-anchor)`.

### Task 8 — Single-source the guard into the standalone script
- **Files:** `scripts/research_health.py`.
  - While the conn is open (before close), `det_count = research_health.db_detection_count(conn)`. After `compute_research_health`, call `research_health.should_suppress_broken_context_write(current_detection_count=det_count, exports_root=exports_root, shadow_manifest_path=None, prior_env=research_health._read_prior_env(out_path))`. On suppress → print a WARNING to stderr, do NOT write, and return 0 (the probe declined to overwrite; not an operational error). On write → pass `extra={"detection_count": det_count}` to `write_research_health_artifact` (same machine-readable stamp as the runner, single-source). The script already never pushes (no push call) — requirement #2 satisfied without change on the push side.
- **Tests (red→green):** a subprocess/`main([...])` test: a prior artifact with `detection_count>0` + an empty DB → the script does NOT overwrite (prior byte-identical) + a stderr warning. And the genuine-fresh case (prior absent / `detection_count` 0) → still writes (and its written artifact carries `detection_count`).
- **Commit:** `feat(scripts): 19-B Task 8 — single-source the broken-context guard into the research-health probe`.

*(Task numbering is logical; the executing implementer may merge closely-coupled tasks (e.g. 3+4, 5) into single red→green commits where the TDD cycle stays clean. The FIRST commit MUST be the isolation fixture, Task 1.)*

---

## §4. Discriminating tests (with pre/post reasoning) — the brief §4.2 gates

1. **Worktree-context run reads+writes+pushes ONLY its own root (MAIN untouched).**
   - Test: a fake cfg with `exports_dir=<worktreeA>/exports`; run `_step_research_health` (RED edge, `run_id=7`); assert the artifact wrote to `<worktreeA>/exports/research/health/latest.json` and the push landed under `<worktreeA>/comms/rd/inbox/`; assert NOTHING was written under a distinct `<main>/exports` or `<main>/comms` sentinel dir.
   - Pre-fix: WRITE resolves via `research_health_artifact_path()` (`__file__` → MAIN) and PUSH via `_default_comms_root()` (`__file__` → MAIN) → both land in MAIN (poison) while the read used the worktree exports. Post-fix: both cfg-derived → worktree only. **Distinguishes** (pre lands in MAIN sentinel; post does not).

2. **An unleased context NEVER posts.**
   - Test: `push_research_health_red_to_rd(red, run_id=None, prior_overall="green", comms_root=<tmp>)` → `posted is False`, inbox empty, WARNING logged.
   - Pre-fix: edge fires → one file, `posted is True`. Post-fix: gate returns False. **Distinguishes.**

3. **Broken-context-empty ⇒ no write + prior `latest.json` preserved.**
   - Test (empty-DB vector): prior artifact (cfg path) with `detection_count>0` + empty DB (`COUNT`=0) + `shadow_manifest_path=None` → step writes nothing, prior byte-identical, no push. Pre-fix (no guard): compute produces green "n/a" (or a degraded status) and OVERWRITES the prior → prior bytes change. Post-fix: suppressed → prior identical. **Distinguishes.**
   - Test (invisible-manifest vector): `shadow_manifest_path=<path>` + empty `exports_root` → suppressed. Pre-fix: writes a drumbeat-RED. **Distinguishes.**

4. **Genuine-empty ⇒ per RD's blessed semantics.**
   - Test: empty DB, prior absent (or prior `detection_count` 0, or an old artifact with no `detection_count`) → the step WRITES the honest green "no mature detections yet (n/a)" envelope (not suppressed), and the written artifact carries `detection_count: 0`. Pre/post: post-fix must NOT over-suppress a genuinely fresh system (the machine-readable witness ensures this). The test fails a naive "suppress on any empty DB" implementation. **Distinguishes** the guard from an over-eager suppressor.

5. **Suite-run zero-real-comms check (brief §2.4).**
   - Test: an integration-style assertion that after the isolation fixture is active, no test can reach `<repo>/comms`. Implement as: (a) the Task 1 fixture test, plus (b) an operator/CI check `git status --porcelain comms/` clean after a full `pytest -m "not slow"` run (specified as an executing-phase acceptance step, §7 — NOT run in this plan-only dispatch). Pre-fix: `test_step_writes_no_status_column` drops one real `comms/rd/inbox/*.md`. Post-fix: zero new files under `comms/*/inbox/`.

**Regression-arithmetic discipline:** every test above has its assertion computed under BOTH the pre-fix and post-fix resolution/gate so it provably distinguishes (per the `feedback_regression_test_arithmetic` memory). Fixtures for the "prior had detections" witness are derived from real `compute_research_health` emitter output, not hand-built dicts (the synthetic-vs-emitter-shape gotcha).

---

## §5. Locks honored (brief §3)

- **Measurement COMPUTATION unchanged:** `compute_research_health` and all 7 check functions are NOT edited (the guard is a downstream write-DECISION consuming its output; the new helpers only READ `status`/`prior_env`). No check threshold, sentinel, or calibration moves.
- **19-A CALIBRATION-C region UNTOUCHED:** 19-A's clause-2b logic lives in `_check_coverage_gaps` (`research_health.py` ~1250-1400, the skip-warning join region). This plan reads the coverage_gaps *result* (the `not per_det` empty-sentinel arm at `:1196-1199`, a DIFFERENT region 19-A did not touch) but edits NONE of the coverage logic. No rebase conflict expected; the executing implementer greps to confirm the `if not per_det:` sentinel string is unchanged before relying on it.
- **`write_research_health_artifact` single-source preserved (extended, not forked):** still the ONE atomic writer; the guard does not add a second write path — it decides WHETHER to call the single writer. The writer gains an OPTIONAL `extra: dict | None` param that merges a top-level `detection_count` into the envelope AFTER `status.to_dict()` — an additive extension of the single writer (both the runner and the script pass it), NOT a second writer. The writer stays pure (no guard logic inside it — LOCK 2 re-validation avoided). The 18-F reader ignores the extra key (verified against `read_validated_research_envelope`'s gates).
- **C-NH5 (write-nothing-on-failure) preserved + extended:** a compute exception still propagates before any write (unchanged); the guard adds "write-nothing-on-suspicious-SUCCESS" composed on top (an explicit early return, no write, no push).
- **Bare `step_guard` (O1) preserved:** the step call stays wrapped by the bare B-shape `step_guard(lease, "research_health", logger=log)` with NO status_key; the guard's early return is a normal return (swallowed as success), not a status write.
- **Read-only `mode=ro` conn preserved:** the ro-URI conn is unchanged; the guard needs no DB access (pure predicate over `status`/`prior_env`/`exports_root` dir-scan).
- **18-H.7 edge-trigger preserved for LEASED runs:** prior-overall read → (guard) → push → write ordering is retained; the lease-or-silent gate only adds a `run_id is None` short-circuit inside the push helper (a genuine leased run with `run_id` int is unaffected).
- **NO schema (v31):** zero migrations, zero table/column changes.

---

## §6. SUB-TRIPWIRE self-certification + enumerated production-file set (brief §3)

**Enumerated production files touched (exact set):**
1. `swing/config.py` — add the defaulted `project_root: Path | None` field on `Config` (populated by `load()`/`from_defaults()`); add the `config_project_root(cfg)` accessor (the robust project-root source; Codex R1 MAJOR).
2. `swing/monitoring/research_health.py` — the `_effective_comms_root` seam + lease-or-silent `run_id is None` gate + `pipeline_run_exists` (DB lease verification); `_comms_root_for` (via `config_project_root`); the guard predicate + helpers (`should_suppress_broken_context_write`, `db_detection_count`, `_prior_env_had_detections`, `_read_prior_env`); the additive `extra:` param on `write_research_health_artifact`.
3. `swing/monitoring/stoplights.py` — `research_health_artifact_path(cfg=None)`; thread `cfg` through `_read_research_envelope`/`read_validated_research_envelope`/`_research_stoplight`/`health_stoplights`.
4. `swing/pipeline/runner.py` — `_step_shadow_expectancy` returns the manifest path; `_step_research_health` anchor-consistent write/push + guard wiring + `shadow_manifest_path` param; call-site update.
5. `swing/web/view_models/health.py` — pass `cfg` into `read_validated_research_envelope`.
6. `scripts/research_health.py` — call the single-sourced guard before the write.

**Test files touched:** `tests/conftest.py` (autouse fixture); `tests/monitoring/test_research_health_rd_push.py`, `tests/monitoring/test_research_health_comms_isolation.py` (new), `tests/monitoring/test_research_health_guard.py` (new, guard predicate), `tests/pipeline/test_step_research_health.py` (re-point + new), `tests/pipeline/test_step_shadow_expectancy.py` (if the return-value change needs a companion assertion — none currently assert it), plus web-reader tests under `tests/monitoring/` or `tests/web/`.

**Self-certification (SUB-TRIPWIRE):**
- **NO schema change** — v31 unchanged, zero migrations. ✅
- **NO new module** — all logic lands in existing `swing/config.py`, `swing/monitoring/research_health.py`, `stoplights.py`, `swing/pipeline/runner.py`, `swing/web/view_models/health.py`, `scripts/research_health.py`. (No new `swing/*` package/module; new test files are not modules-under-tripwire.) ✅
- **NO new dependency** — stdlib + existing imports only. ✅
- **NO new standing process** — no scheduled task, daemon, or nightly step added (19-C owns the scheduled task; this arc only makes the EXISTING step launch-context-safe). ✅
- **NO `swing/trades`|`swing/data` carve-out** — no edits under `swing/trades/` or `swing/data/`. ✅
- **Config change scope** — a `config accessor` (`config_project_root`) + a defaulted trailing `project_root: Path | None` field on `Config` (the brief anticipates "a config accessor"). This is a `swing/config.py` edit (NO schema, NO new module, NO dependency); the frozen-dataclass field is trailing+defaulted so no `Config(...)` construction breaks. NOT a measurement-computation change. ✅

Verdict: **SUB-TRIPWIRE confirmed** — consistent with the brief §3 verdict. No tripwire crossed; RD plan-stage review (guard/lease/anchor semantics) is the gating review, per brief. (The `swing/config.py` field-add is a config-loader edit, not a schema/measurement change — within SUB-TRIPWIRE.)

---

## §7. Executing-phase gates (carried into the executing dispatch — NOT run in this plan-only dispatch)

1. **Full fast suite to green BEFORE the Codex review** (recipe §2), with the autouse isolation fixture in place from Task 1. **This plan-only dispatch does NOT run the suite** — a pre-fix suite run leaks a real push to RD's production channel; the executing implementer runs it only AFTER Task 1 lands.
2. **review-strong to convergence + codex-auto-review** (production code — recipe §3, REPO-ACCESS form because correctness depends on the surrounding reference graph: the editable-install `__file__` vs cfg divergence, the web reader chain, the runner conn lifecycle).
3. **Merged-head no-false-green** re-run; **ruff `ruff check swing/` clean**.
4. **Zero-real-comms acceptance:** `git status --porcelain comms/` clean + no new `comms/*/inbox/*.md` after a full `pytest -m "not slow"`.
5. **Operator witness (brief §4.4):** a normal MAIN-repo pipeline run → correct `latest.json`, no push spam; a deliberate worktree launch → NO main poison, NO RD post (the #5 repro turns green).
6. **RD merge-blocking QA** at the return; the ORCHESTRATOR posts the return report to `charc,rd` after QA (the implementer never posts to directors).

---

## §8. RD plan-stage review — the three semantics surfaced (his T1 channel)

RD reviews this plan BEFORE executing. The three load-bearing decisions, surfaced explicitly (not buried):

> **RD RULINGS (2026-07-03, plan-stage review PASS):** 8.1(a) one-run witness window ACCEPTED (anchor fix + lease-verification are primary; the merge operator-witness MAIN run doubles as the witness-seed and must run PROMPTLY at merge). 8.1(b) suppress posture: leave-prior + WARNING + skip-push is correct AND a `warnings_json` run-warning on suppress is REQUIRED (gotcha #27; folded into Task 6 step 4 above). 8.1(c) `detection_count` envelope stamp ACCEPTED (it is a GUARD WITNESS, not a health metric; a future detection-count-as-health consumer routes through the monitor check framework). 8.2(a) default-deny boolean seam ACCEPTED for V1 (do NOT build the conn-internal-verification hardening now). 8.2(b) EXISTENCE -- do NOT tighten to `state='running'` (over-tightening risks a FUTURE silent no-push failure mode on the alarm channel). 8.3 anchor split CONFIRMED (artifact on `cfg.paths.exports_dir`, comms on `cfg.project_root`). **CHARC:** SUB-TRIPWIRE CONFIRMED -- the `Config.project_root` field-add is a config-loader edit below the architecture-pass bar.

### 8.1 The guard's real-empty-vs-broken-context distinguisher (machine-readable)
- **Empty-DB signal (ii):** current read is detection-empty (a direct DB `COUNT(pattern_detection_events) == 0`) AND the prior valid artifact carries a machine-readable `detection_count > 0` (`_prior_env_had_detections`). The prior artifact is the "the live system had data" witness — it lives under the config-anchored exports, decoupled from the HOME-anchored DB, so on the exact wrong-HOME vector (correct cwd, wrong HOME → empty DB) the good prior artifact is present to witness the loss. A genuinely fresh system (no prior, or prior `detection_count` 0, or an old artifact lacking the field) is NOT suppressed → keeps writing the honest green "n/a" (the §1.3 truth table). **No English-string coupling** (Codex R1/R2 MAJOR designed out — the machine `COUNT` + the machine `detection_count` field replace the coverage-summary proxy).
- **Invisible-manifest signal (i):** gated on shadow SUCCESS (`shadow_manifest_path is not None`) so a genuine shadow failure / first-ever run still writes its honest drumbeat-RED — we do NOT hide a real engine-down state.
- **KNOWN BOUNDED LIMITATION — the one-run witness-seed window (Codex R5 MAJOR — acknowledged, claim corrected):** the empty-DB witness reads `detection_count` from the PRIOR artifact, so it cannot witness until ONE post-19-B run has stamped the field. Concretely: a wrong-HOME empty read that is the VERY FIRST research-health run after 19-B deploys (prior artifact predates the field) is NOT suppressed by signal (ii) — it is protected ONLY by the primary anchor-consistency fix + the lease verification, not by the empty-DB guard. After ONE correct-context run stamps `detection_count`, the witness is live. This is a real, BOUNDED (one-run) gap, called out so the "broken-context guard" claim does not overstate coverage. It is acceptable for V1 because: (a) the window is a single run; (b) anchor-consistency is the PRIMARY protection (the guard is belt-and-suspenders for the residual HOME vector); (c) the only backward-compatible alternative — deriving the witness from the pre-19-B coverage-summary STRING — reintroduces exactly the English-string coupling Codex R1/R2 required removing; and (d) "treat a fresh pre-19-B prior as a credible witness" would FALSE-suppress a genuinely-fresh system whose pre-19-B prior was a green "n/a". **RD decides** whether the one-run window is acceptable or warrants a different witness (e.g. a persisted sidecar count outside the envelope).
- **RD decision points:** (a) is the one-run witness-seed limitation above acceptable? (b) On suppress, is "leave prior + WARNING + skip push" the right posture, or should a suppressed broken-context ALSO emit a distinct diagnostic (e.g. a `run_warnings` entry / a different log level)? (c) is stamping `detection_count` into the envelope (a top-level, reader-ignored, test-proven-tolerant key) acceptable, given the measurement COMPUTATION is untouched?

### 8.2 The lease-or-silent boundary (default-deny helper + DB lease verification)
- Gate (Codex R3/R4 adopted): the helper is DEFAULT-DENY — `lease_verified: bool = False`; it posts NOTHING unless a caller explicitly asserts `lease_verified=True` AND `run_id is not None`. The ONLY opt-in caller is the runner, which computes `lease_verified=pipeline_run_exists(conn, run_id)` (a real `pipeline_runs` row) while the ro conn is open. A forged/stale/nonexistent int → not a `pipeline_runs` row → `lease_verified=False` → no push. A future caller that forgets → default-deny → no push. This meets the brief's literal "genuine `pipeline_runs` run_id."
- **Row is provably active + owned at push time (rebuts Codex R6 "not still active/owned"):** the push fires from `runner.py:1061`, INSIDE the `with step_guard(lease, "research_health", ...)` block, while the runner HOLDS the acquired live `lease` and passes `run_id=lease.run_id`. So the `pipeline_runs` row is, by construction, the CURRENT execution's own still-running lease — not a stale or cross-run id. `pipeline_run_exists` is a belt (it rejects a fake int that isn't a row at all); the genuineness is guaranteed upstream by the runner owning the lease.
- **Adjudication of the "unforgeable proof object" ask (Codex R5/R6 MAJOR — over-reach for V1, cited):** Codex escalated to "pass a live lease token / proof object so the helper cannot be invoked in a posting-eligible state without verifying the DB lease." This is over-engineering for THIS threat model: the app is a **single-operator internal tool with exactly ONE production caller** (the runner, which owns the live lease) and NO adversarial/untrusted callers. The reachable accidental vectors are all closed (run_id None; unverified/forgetful caller → default-deny; forged int → DB check False). A caller that DELIBERATELY passes `lease_verified=True` WITH a fake `run_id` is deliberate internal misuse, outside the threat model — a boolean-vs-proof-object distinction buys nothing against a caller already willing to lie. The default-deny boolean + DB verification is the appropriate V1 seam; the conn-internal-verification hardening is a documented deferred option (below) if RD wants it.
- **RD decision points:** (a) accept the default-deny boolean seam for V1, or (deferred hardening) move the DB verification INSIDE the helper by threading the live ro conn (heavier: every 18-H.7 helper test would provide a conn + seed `pipeline_runs`)? (b) existence (any `pipeline_runs` row) vs a stricter `state='running'` predicate — the push fires from inside the still-running lease so the row is always present + running at push time; RD confirms whether the distinction matters for the T1 channel.

### 8.3 The anchor-contract (LOCK-#4) semantics
- After the change, BOTH the 18-F web reader and the 18-D writer resolve the artifact through the ONE cfg-aware accessor `research_health_artifact_path(cfg)` from the SAME per-launch cfg — never one config- and one `__file__`-anchored. In production both cfgs → MAIN/exports; in a worktree both → worktree/exports; they cannot split.
- The comms root is config-derived via `config_project_root(cfg)` = the EXPLICIT `cfg.project_root` (= `config_path.parent.resolve()`, stored on `Config` at `load()`) — NOT the fragile `exports_dir.parent` inference (Codex R1 MAJOR adopted; §1.1.1). Robust to a relocated/absolute `exports_dir`.
- **RD/CHARC note:** the plan now stores `project_root` explicitly on `Config` (the robust option Codex + the plan both flagged). CHARC confirms the `swing/config.py` field-add stays SUB-TRIPWIRE (config-loader edit; no schema/measurement change). The only residual choice is whether the ARTIFACT path should also key off `cfg.project_root` rather than `cfg.paths.exports_dir` — the plan keeps the artifact on `exports_dir` (so a customized exports location still holds its own artifact) and the comms root on `project_root` (comms is a fixed project-root sibling); RD/CHARC confirm this split is correct.

---

## §9. Risks / open items
- **KNOWN BOUNDED LIMITATION — one-run witness-seed window** (§8.1) — the `detection_count` witness needs ONE post-19-B run to stamp the field; a wrong-HOME empty read that is the FIRST run after deploy is covered only by the anchor fix + lease verification, not the empty-DB guard. Bounded to one run; RD decides acceptability. No English-string coupling remains (Codex R1/R2 designed out).
- **Lease seam is a default-deny boolean, not a proof object** (§8.2) — adjudicated: over-engineering for a single-operator, single-caller tool with no adversarial callers; the reachable vectors are closed. RD may defer the conn-internal-verification hardening.
- **`config_project_root` raises on a missing `project_root`** (§1.1.1) — no silent `exports_dir.parent` divergence; production always sets it via `load()`; the best-effort push wrappers swallow the never-in-production raise. Test doubles must set `project_root`.
- **`_step_shadow_expectancy` return-shape change** — from `None` to `Path | None`. No existing test asserts the return (they check `run_warnings`); the ONE source-substring pin (`test_runner_invokes_step_via_step_guard_between_shadow_and_complete`) is updated in Task 6.
- **Re-pointed runner tests** (§Task 6) — the anchor-consistency change moves the artifact-resolution seam from the monkeypatched `stoplights.research_health_artifact_path` to `cfg.paths.exports_dir`; several existing tests re-point their fake cfg / assertions. Each re-pointed assertion is computed under both resolutions to confirm it still distinguishes.
- **`Config.project_root` field-add** (§1.1.1, adopted from Codex R1 MAJOR) — a trailing defaulted frozen-dataclass field. The executing implementer greps `Config(` across `swing/`+`tests/` to confirm no positional construction is broken; the `config_project_root` fallback keeps direct-construction test cfgs (that omit it) working.
- **The fake `_Cfg`/`_Paths` test doubles** (`tests/pipeline/test_step_research_health.py`) — `config_project_root` now RAISES on a missing `project_root` (no silent fallback, Codex R5), so the doubles MUST set `project_root` (a tmp root) explicitly → `_comms_root_for` resolves a tmp comms in those tests (belt with the comms seam-guard). The executing implementer adds `project_root` to the fake `_Cfg`.
