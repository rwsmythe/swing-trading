# Implementation Plan — 18-H.7: nightly research-health RED -> role_mail push to RD

**Arc:** 18-H.7 (Phase-18 G3). A SWING arc (pipeline + comms); NOT cross-repo.
**Brief:** `docs/18-h7-research-health-rd-push-commissioning-brief.md` (committed `ccc3279e`). CHARC §3 pass = GO.
**Plan dispatch:** writing-plans (this doc). Executing recommendation: `implementer-opus-high`, Codex review-strong to convergence.
**Base:** worktree `18h7-research-health-rd-push` branched from `main` (`9cbd41c6`).

---

## 0. Goal in one paragraph

When the nightly pipeline's read-only `research_health` step computes `overall == "red"` AND the
PRIOR `latest.json` was NOT red (i.e. a green/yellow->red transition, or the first-ever-RED
absent->red case), post a single `role_mail` `status` message `--from pipeline --to rd` naming the
fired RED check key(s) and carrying each red check's `summary` + `detail` (the regression-vs-accepted
discriminator RD most needs) + the run-id + the `latest.json` pointer + the GUI research-stoplight
pointer. NO new state file (the edge is computed by reading the prior artifact before it is
overwritten); NO weekly re-nag (V1 = pure edge-trigger). The push is best-effort: any failure is
swallowed + logged, NEVER fails the pipeline, and `_step_research_health` still writes `latest.json`.

---

## 1. Verified grounding (on disk, this worktree)

All anchors RE-GROUNDED against live code in the worktree (line numbers will drift — the executing
implementer re-greps).

- **Hook point:** `swing/pipeline/runner.py:_step_research_health` (def `~:1323`, invoked at `~:1060`
  under a BARE B-shape `step_guard(lease, "research_health", logger=log)`). The current body:
  - lazy-imports `compute_research_health` + `write_research_health_artifact` from
    `swing.monitoring.research_health`;
  - opens a `mode=ro` URI conn (`cfg.paths.db_path.as_uri() + "?mode=ro"`);
  - `status = compute_research_health(conn, cfg=cfg, exports_root=cfg.paths.exports_dir / "research")`;
  - `conn.close()`;
  - `write_research_health_artifact(status)` (the C-NH4 default = the contract `latest.json`).
- **The status shape** (`swing/monitoring/research_health.py`):
  - `ResearchHealthStatus.overall` in `{green,yellow,red}` (== `worst_of(checks)`, enforced in
    `__post_init__`); `.checks` is a TUPLE of `ResearchHealthCheck` (coerced in `__post_init__`);
    `.generated_ts` aware-UTC.
  - `ResearchHealthCheck.key` / `.status` / `.summary` (non-empty str) / `.detail` (str|None).
  - Red checks = `[c for c in status.checks if c.status == "red"]`.
- **The artifact path accessor:** `swing/monitoring/stoplights.research_health_artifact_path()`
  (`stoplights.py:43`) returns `RESEARCH_HEALTH_ARTIFACT_PATH` (`= <repo>/exports/research/health/
  latest.json`, `stoplights.py:27`). `write_research_health_artifact(status, out_path=None)` resolves
  `out_path` via THIS accessor when `out_path is None` (`research_health.py:247-249`). The existing
  runner-step + script + monitor tests monkeypatch `stoplights.research_health_artifact_path` to a
  tmp file — so reading the prior artifact MUST go through the SAME accessor (not the bare constant)
  to stay test-monkeypatch-honoring.
- **`role_mail`** (`scripts/role_mail.py`):
  - `VALID_FROM = ("charc", "rd", "operator", "orchestrator")` (`:41`) — pipeline NOT yet a sender.
  - `VALID_TO = ("charc", "rd", "operator")` (`:43`); `VALID_TYPES = (..., "status", ...)` (`:44`).
  - `post_message(root, sender, recipients, mtype, subject, body, thread=None)` (`:224`) — validates
    sender in `VALID_FROM` -> type in `VALID_TYPES` -> CR/LF guard -> recipients in `VALID_TO` -> L1
    lock (`decision_request` => operator-only) -> atomic all-or-nothing delivery. Raises `MailError`.
  - **L1 lock (`:262-268`):** `decision_request` may address ONLY operator. The `pipeline` sender is
    governed by the SAME lock (it is sender-agnostic): a `decision_request` from any sender to `rd`
    rejects. Our emit only ever sends `status` -> never trips L1.
- **`VALID_FROM` single-source check (grep, whole repo):** the ONLY code declaration is
  `scripts/role_mail.py:41`; the other `:244/:247/:474` lines are USES (`if sender not in VALID_FROM`,
  help text). `scripts/comms_ui.py` imports `role_mail` and references `role_mail.VALID_*`; its
  compose dropdown hardcodes the RECIPIENT roles `("charc","rd","operator")` (`comms_ui.py:668`) =
  `VALID_TO`-shaped, and the compose UI is operator-identity-only (server-stamps the sender,
  `comms_ui.py:696`) — so there is **NO second copy of the SENDER list anywhere in code**. Adding
  `"pipeline"` to `VALID_FROM` at `:41` is the single edit; no mirror to update (B-12 satisfied).
  (Doc files mentioning `VALID_FROM` are prose, not mirrors.)
- **Path-resilient `role_mail` import precedent:** `scripts/comms_ui.py:44-48` and
  `tests/scripts/test_role_mail.py:16-19` both load `role_mail` via
  `importlib.util.spec_from_file_location("role_mail", <scripts>/role_mail.py)` +
  `module_from_spec` + `loader.exec_module` (scripts/ is NOT on `swing`'s import path). Our helper
  lives in `swing/monitoring/research_health.py`, so the repo root is
  `Path(__file__).resolve().parents[2]` (matches `stoplights.py:28`'s `parents[2]`); the
  `role_mail.py` path is `<repo>/scripts/role_mail.py`; the default `comms_root` is `<repo>/comms`.

---

## 2. Design contract (settled in the brief; this section makes it executable)

### 2.1 The thin notify helper — a function in `swing/monitoring/research_health.py`

Per brief §3 disposition #2 ("additive to existing ... a thin `swing/monitoring/` helper") and the
recipe's "no new module unless clearly cleaner": add the helper as a FUNCTION in the EXISTING
`swing/monitoring/research_health.py` (it already owns `ResearchHealthStatus`, the artifact-path
accessor wiring, and `write_research_health_artifact`). No new module/file.

Two small functions + module-level constants:

```python
# swing/monitoring/research_health.py  (additive; near write_research_health_artifact)

# The GUI research-stoplight pointer surfaced in the push body (ASCII; the live
# web nav path to the research drill-down). A module constant so the message text
# has a single source.
_RESEARCH_STOPLIGHT_URL = "/health/research"          # see Task 0 grounding note
_LATEST_JSON_POINTER = "exports/research/health/latest.json"


def _default_comms_root() -> Path:
    """The repo comms/ root (the role_mail mailbox). Introduced as a MODULE
    FUNCTION (not an inline expression) so tests can monkeypatch it to a tmp dir
    — the seam the runner-wiring end-to-end test (Task 4) drives the REAL helper
    through without touching the live comms/ tree. <repo> = parents[2] (matches
    stoplights.py:28's parents[2]; this module is swing/monitoring/...)."""
    return Path(__file__).resolve().parents[2] / "comms"


def _read_prior_overall(out_path: Path | None = None) -> str | None:
    """Read the PRIOR latest.json's `overall` BEFORE it is overwritten.

    `out_path=None` resolves via stoplights.research_health_artifact_path() (the
    SAME accessor write_research_health_artifact uses, so a test monkeypatch is
    honored). Returns the prior `overall` string, or None when the artifact is
    ABSENT or UNPARSEABLE or carries no/invalid `overall` -> treated as non-red by
    the caller (absent/corrupt -> not red -> an absent->red is a valid first-ever
    edge). NEVER raises (best-effort; a read failure must not break the step)."""
    if out_path is None:
        from swing.monitoring.stoplights import research_health_artifact_path
        out_path = research_health_artifact_path()
    try:
        env = json.loads(Path(out_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(env, dict):
        return None
    overall = env.get("overall")
    return overall if isinstance(overall, str) else None


def push_research_health_red_to_rd(
    status: ResearchHealthStatus,
    *,
    run_id: int | None,
    prior_overall: str | None,
    comms_root: Path | None = None,
) -> bool:
    """Edge-triggered RED notify to RD. Returns True iff a message was posted.

    Edge = current.overall == "red" AND prior_overall != "red" (covers
    green/yellow->red AND absent/corrupt(None)->red). On a non-edge -> return
    False, post nothing. On the edge -> compose + post ONE `status` message
    `--from pipeline --to rd` and return True.

    `comms_root=None` -> `_default_comms_root()` (the repo `comms/`); tests pass a
    tmp dir, OR monkeypatch `_default_comms_root` (the runner-wiring end-to-end
    test), so they never touch the live comms.

    BEST-EFFORT: any exception (import failure, MailError, IO) is swallowed +
    logged; returns False. The caller is ALSO under step_guard, but this function
    owns its own try/except so a push failure never reaches the writer call that
    follows it (write-latest.json must still happen)."""
```

Body of `push_research_health_red_to_rd`:
1. `if status.overall != "red" or prior_overall == "red": return False` (the edge gate — the ONLY
   place the edge is decided; pure, testable).
2. `try:` everything below; `except Exception as exc: log.warning("research-health RD push failed:
   %s", exc); return False` (best-effort; NEVER re-raise).
3. Resolve `comms_root = comms_root or _default_comms_root()` (the monkeypatchable seam).
4. Path-resilient import of `role_mail` via `importlib.util.spec_from_file_location` from
   `Path(__file__).resolve().parents[2] / "scripts" / "role_mail.py"` (the comms-hook precedent).
   (Import lazily INSIDE the function, inside the try, so a missing/edited scripts tree degrades
   to a logged no-post rather than an import-time crash of the module.)
5. Compose subject + body (§2.2) from `status` + `run_id`.
6. `role_mail.post_message(comms_root, "pipeline", ["rd"], "status", subject, body)`.
7. `log.info(...)` the post; `return True`.

**Why the function owns its own try/except even though the step is under `step_guard`:** the writer
(`write_research_health_artifact`) runs AFTER the push in `_step_research_health`. If a push exception
propagated to `step_guard`, the guard would swallow it but the writer line would be SKIPPED ->
`latest.json` would not refresh on a night the push happened to fail. Owning the try/except locally
guarantees the write-latest.json side-effect is independent of push success (brief: "the step still
completes + still writes latest.json").

### 2.2 The message

- `sender = "pipeline"`, `recipients = ["rd"]`, `mtype = "status"`.
- **Subject** (single line, no CR/LF — `post_message` rejects newlines in subject): name RED + the
  fired check key(s). e.g. `"research-health RED: temporal_log_finiteness, structural_integrity"`.
  Build from `red_keys = [c.key for c in status.checks if c.status == "red"]`. ASCII-only. If the
  joined subject would be very long, the body carries the full per-check detail regardless — keep the
  subject a compact key list (no truncation logic needed in V1; keys are short identifiers).
- **Body** (multi-line; ASCII-only — the cp1252 gotcha; no em-dash, no section glyph, no arrows):
  ```
  overall=red

  RED checks:
  - <key>: <summary>
    detail: <detail or "(none)">
  ... (one block per red check, in status.checks order)

  run id: <run_id or "unknown">
  artifact: exports/research/health/latest.json
  GUI: /health/research
  ```
  - The `detail` line is LOAD-BEARING (RD's regression-vs-accepted discriminator) — always emit it,
    substituting `(none)` when `c.detail is None` so the line is always present and the content test
    can assert the real detail substring when present.
  - Use only ASCII punctuation. No Unicode.

### 2.3 Wiring into `_step_research_health`

Re-order the existing body so the prior `overall` is read BEFORE the write overwrites it:

```python
def _step_research_health(*, cfg, run_id=None) -> None:
    from swing.monitoring.research_health import (
        compute_research_health,
        push_research_health_red_to_rd,
        write_research_health_artifact,
        _read_prior_overall,
    )
    # 1. read PRIOR overall BEFORE compute/write (the edge baseline; never raises)
    prior_overall = _read_prior_overall()
    ro_uri = cfg.paths.db_path.as_uri() + "?mode=ro"
    conn = sqlite3.connect(ro_uri, uri=True, timeout=2.0)
    try:
        status = compute_research_health(
            conn, cfg=cfg, exports_root=cfg.paths.exports_dir / "research")
    finally:
        conn.close()
    # 2. push IFF the RED edge fired (best-effort; never raises; never blocks the write)
    push_research_health_red_to_rd(
        status, run_id=run_id, prior_overall=prior_overall)
    # 3. write the NEW latest.json (single-source atomic writer) — always runs
    write_research_health_artifact(status)
```

**Ordering rationale (the no-new-state edge):** `_read_prior_overall()` reads the artifact that the
PREVIOUS night's run wrote. We capture `prior_overall` FIRST, compute the current `status`, fire the
push against `(current, prior)`, THEN overwrite `latest.json`. The edge is derived purely from the
two artifact reads — no persistent last-push timestamp / no new state file. Absent/unparseable prior
-> `None` -> `prior_overall == "red"` is False -> an absent->red counts as an edge (first-ever-RED).

**`run_id` source:** the brief wants the run id in the body. `_step_research_health` is called at
`runner.py:~1061` from inside `run_pipeline`, where `lease.run_id` is in scope. Thread it through:
change the call site to `_step_research_health(cfg=cfg, run_id=lease.run_id)` and add the
`run_id: int | None = None` keyword param to `_step_research_health` (default None keeps the existing
direct-call tests — which call `_step_research_health(cfg=_Cfg(...))` — passing unchanged; they will
emit `run id: unknown` in any push, which is fine since those tests seed GREEN dbs and never push).

### 2.4 Sender taxonomy — the authorized §3 change

Single edit: `scripts/role_mail.py:41`
```python
VALID_FROM = ("charc", "rd", "operator", "orchestrator", "pipeline")
```
- `"pipeline"` is an AUTOMATED-EMITTER sender (the nightly pipeline), distinct from the human/agent
  roles. It posts `status` to `rd` only. It is transport-automation, NOT authority.
- **L1 lock UNCHANGED:** the `decision_request`-operator-only gate (`role_mail.py:262-268`) is
  sender-agnostic; adding `pipeline` to `VALID_FROM` does NOT loosen it. A `decision_request` from
  `pipeline` to `rd` still rejects (test in Task 2). A `--to` outside `VALID_TO` still rejects (the
  `_validate_recipients` gate, unchanged).
- `pipeline` is NOT added to `VALID_TO` (it has no inbox; it only emits) and NOT to the compose-UI
  dropdown (operator-identity-only). No other edit.

---

## 3. Self-certification (against the brief / recipe locks)

- **No new schema / migration:** none. Read-only w.r.t. the measurement DB (the existing `mode=ro`
  conn is unchanged; the new reads are a JSON artifact + the comms filesystem).
- **No new module:** the helper is a FUNCTION added to the existing `swing/monitoring/
  research_health.py` (brief §3 disposition #2; recipe "additive-to-existing").
- **No new dependency:** stdlib only (`json`, `importlib.util`, `pathlib`). `role_mail` is loaded by
  path (already in-repo).
- **No `swing/trades` | `swing/data` carve-out:** touches `swing/pipeline/runner.py`,
  `swing/monitoring/research_health.py`, `scripts/role_mail.py` only.
- **No measurement-VALUE change:** a NOTIFY on the EXISTING RED computation; `compute_research_health`
  is unchanged; `write_research_health_artifact(status)` still writes the same envelope.
- **Sender taxonomy add is the ONLY taxonomy change** and is the explicit §3-AUTHORIZED one;
  single-sourced; L1 unchanged.
- **Best-effort:** the push never fails the run; `latest.json` still written.
- **ASCII-only** user-facing strings (subject/body) — the cp1252 gotcha.

---

## 4. Ordered TDD tasks

Each task: write the failing test FIRST, SEE it fail (correct reason), minimal implementation, SEE
it pass, commit (conventional, task-id, ZERO Co-Authored-By, plain-prose final paragraph). The
distinguishing-test arithmetic (FAIL pre / PASS post) is stated per test.

**Test files:**
- `tests/scripts/test_role_mail.py` — the sender-taxonomy task (mirror the existing
  `importlib.spec_from_file_location` load + the `comms = tmp_path/"comms"` fixture + the `_post`
  helper at lines 16-33).
- `tests/monitoring/test_research_health_rd_push.py` — NEW file for the helper trigger/content/
  best-effort/test-safe tests (mirror `test_research_health_aggregate.py` imports; construct
  `ResearchHealthStatus` directly).
- `tests/pipeline/test_step_research_health.py` — EXTEND for the runner-wiring + read-prior ordering
  + run_id threading (mirror the existing `_Cfg`/`_Paths`/`_patch_artifact`/`_seed_green_db` idioms).

A note on constructing a RED `ResearchHealthStatus` in tests: build it directly —
`ResearchHealthStatus(overall="red", checks=[ResearchHealthCheck(key="temporal_log_finiteness",
status="red", summary="3 post-baseline non-finite OHLC observation(s)", detail="ZZZ@2026-06-20")])`.
`__post_init__` enforces `overall == worst_of(checks)` (satisfied: one red check -> worst is red) and
a fresh-aware-UTC default `generated_ts` (satisfied by the default factory). No DB seeding needed for
the helper-level tests; the helper consumes the `status` object.

---

### Task 1 — sender taxonomy: add `"pipeline"` to `VALID_FROM`

**Files:** `scripts/role_mail.py` (impl), `tests/scripts/test_role_mail.py` (test).

**Tests (in `tests/scripts/test_role_mail.py`, using the existing `comms` fixture + `_post` helper):**

- `test_pipeline_is_a_valid_sender`: `_post(comms, **{"from": "pipeline", "to": "rd", "type":
  "status", "subject": "research-health RED", "body": "overall=red"})` returns `0`, and exactly one
  file lands in `comms/rd/inbox/` containing `from: pipeline`.
  - **FAIL pre-fix:** `pipeline` not in `VALID_FROM` -> `post_message` raises `MailError("invalid
    --from 'pipeline' ...")` -> `cmd_post` -> `main` returns `1` (not `0`); inbox empty. Assert `rc ==
    0` FAILS.
  - **PASS post-fix:** `pipeline` in `VALID_FROM` -> validation passes -> `rc == 0`, one inbox file
    with `from: pipeline`.
- `test_pipeline_decision_request_to_rd_still_rejects` (L1 lock unchanged): `_post(comms, **{"from":
  "pipeline", "to": "rd", "type": "decision_request", "subject": "x", "body": "y"})` returns `1`
  (`MailError` from the L1 gate); inbox empty.
  - **FAIL pre-fix:** pre-fix `pipeline` is rejected at the SENDER gate (before L1), so it also
    returns `1` — but for the WRONG reason. To make this test DISTINGUISH the L1 behavior (not the
    sender gate), assert on the ERROR TEXT: capture stderr (the existing tests use `capsys`) and
    assert the message contains `"L1"` / `"decision_request"`, NOT `"invalid --from"`. Pre-fix the
    error is `invalid --from 'pipeline'` (sender-gate) -> the `"L1"` assertion FAILS. Post-fix the
    sender passes and the L1 gate fires -> the error contains `L1` -> PASSES. (This proves the L1
    lock still bites a `pipeline` decision_request rather than the change accidentally bypassing it.)
- `test_pipeline_to_invalid_recipient_rejects` (VALID_TO unchanged): `_post(comms, **{"from":
  "pipeline", "to": "santa", "type": "status", "subject": "x", "body": "y"})` returns `1`; assert
  stderr contains `"invalid recipient"`. Post-fix the sender passes but `_validate_recipients`
  rejects `santa`. (Pre-fix it would fail at the sender gate; the recipient-text assertion
  distinguishes post-fix behavior. This guards that widening VALID_FROM did not widen VALID_TO.)

**Impl:** add `"pipeline"` to the `VALID_FROM` tuple at `scripts/role_mail.py:41`. (One-line.)

**Commit:** `feat(comms): Task 1 -- add 'pipeline' automated-emitter sender to role_mail VALID_FROM`

---

### Task 2 — the edge-gate + helper: `_read_prior_overall` + `push_research_health_red_to_rd` (no post yet on non-edge)

**Files:** `swing/monitoring/research_health.py` (impl), `tests/monitoring/test_research_health_rd_push.py` (test).

This task lands the helper functions and the EDGE-DISCRIMINATION + the actual post, all driven
through the production helper over a tmp `comms_root`. (Combining the edge + post in one task keeps
the helper coherent; each behavior is its own test.)

**Test scaffolding (top of the new test file):**
```python
import importlib.util
from pathlib import Path
from swing.monitoring.research_health import (
    ResearchHealthCheck, ResearchHealthStatus,
    push_research_health_red_to_rd, _read_prior_overall,
)
# load role_mail the not-a-package way (to inspect inbox frontmatter)
_RM = Path(__file__).resolve().parents[2] / "scripts" / "role_mail.py"
_spec = importlib.util.spec_from_file_location("role_mail", _RM)
role_mail = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(role_mail)

def _red_status(detail="ZZZ@2026-06-20"):
    return ResearchHealthStatus(overall="red", checks=[ResearchHealthCheck(
        key="temporal_log_finiteness", status="red",
        summary="3 post-baseline non-finite OHLC observation(s)", detail=detail)])

def _yellow_status():
    return ResearchHealthStatus(overall="yellow", checks=[ResearchHealthCheck(
        key="drumbeat_liveness", status="yellow", summary="5 day(s) old", detail="age->yellow")])

def _green_status():
    return ResearchHealthStatus(overall="green", checks=[ResearchHealthCheck(
        key="temporal_log_finiteness", status="green", summary="0 non-finite", detail=None)])

def _rd_inbox(comms_root):
    d = Path(comms_root) / "rd" / "inbox"
    return sorted(d.glob("*.md")) if d.is_dir() else []
```

**Trigger-discrimination tests (each over a tmp `comms_root = tmp_path / "comms"`):**

- `test_red_with_prior_not_red_posts_one_status_to_rd`:
  `posted = push_research_health_red_to_rd(_red_status(), run_id=104, prior_overall="green",
  comms_root=tmp_path/"comms")`. Assert `posted is True`; `len(_rd_inbox(...)) == 1`; the file's
  frontmatter has `from: pipeline`, `to: rd`, `type: status`.
  - **FAIL pre-impl:** `push_research_health_red_to_rd` does not exist -> `ImportError` at collection.
    (After the function exists but before the post body, a stub returning False would FAIL `posted is
    True` + the inbox-count assertion.)
  - **PASS post-impl:** the edge fires (red + prior green) -> one `status` posted from `pipeline` to
    `rd`.
- `test_red_with_prior_red_does_not_post` (no edge): `posted = push_...(_red_status(),
  run_id=1, prior_overall="red", comms_root=...)`. Assert `posted is False`; `_rd_inbox(...) == []`.
  - **FAIL pre-impl (naive "post on any red"):** an impl that posts whenever `overall == "red"`
    (ignoring `prior_overall`) would POST -> `posted is False` FAILS + inbox non-empty FAILS.
  - **PASS post-impl:** the edge gate `prior_overall == "red"` short-circuits -> no post.
- `test_yellow_does_not_post`: `push_...(_yellow_status(), run_id=1, prior_overall="green",
  comms_root=...)` -> `posted is False`, inbox empty.
  - **FAIL pre-impl (red-OR-yellow trigger):** an impl triggering on `overall != "green"` would post
    on yellow -> FAILS.
  - **PASS post-impl:** `overall != "red"` -> no post.
- `test_green_does_not_post`: `push_...(_green_status(), run_id=1, prior_overall="yellow",
  comms_root=...)` -> `posted is False`, inbox empty.
  - **FAIL pre-impl (trigger on any non-green-prior):** would FAIL.
  - **PASS post-impl:** `overall != "red"` -> no post.
- `test_first_ever_red_absent_prior_posts`: `push_...(_red_status(), run_id=7, prior_overall=None,
  comms_root=...)` -> `posted is True`, one inbox file.
  - **FAIL pre-impl (impl treating `prior_overall is None` as "red"/"skip"):** an impl that guarded
    `if prior_overall != "red"` but mistakenly initialized prior to `"red"` on absent, OR that
    required a non-None prior to count an edge, would NOT post -> `posted is True` FAILS.
  - **PASS post-impl:** `None != "red"` is True -> edge fires -> posts (absent->red is the
    first-ever-RED edge).

**Content test:**

- `test_posted_message_carries_keys_summary_detail_runid_pointer`:
  `push_...(_red_status(detail="ZZZ@2026-06-20 non-finite Close"), run_id=104,
  prior_overall="green", comms_root=tmp/"comms")`; read the single inbox file's text; assert it
  contains: the red key `"temporal_log_finiteness"`; the summary substring `"3 post-baseline
  non-finite"`; the **detail substring `"ZZZ@2026-06-20 non-finite Close"`** (the load-bearing
  discriminator); `"104"` (the run id); `"exports/research/health/latest.json"`; `"/health/research"`
  (the GUI pointer).
  - **FAIL pre-impl (body omits detail):** a body that emits only key+summary (no `detail:` line)
    would FAIL the detail-substring assertion. (This is the brief's binding content discriminator.)
  - **PASS post-impl:** the body template (§2.2) emits the detail line + all pointers.
- `test_detail_none_renders_placeholder_not_crash`: build a red status whose red check has
  `detail=None`; push with prior green; assert `posted is True` and the body contains `"(none)"` (no
  `None`/`NoneType` crash, no missing line).
  - **FAIL pre-impl (naive f-string of None / a body that skips the line):** asserting the explicit
    `"(none)"` placeholder distinguishes a deliberate substitution from a `None`-stringified or
    omitted line.
  - **PASS post-impl:** the template substitutes `(none)` when `c.detail is None`.

**Prior-read tests (`_read_prior_overall`):**

- `test_read_prior_overall_absent_returns_none`: point the accessor (monkeypatch
  `stoplights.research_health_artifact_path` to a tmp path that does NOT exist) -> `_read_prior_overall()
  is None`.
- `test_read_prior_overall_unparseable_returns_none`: write `"{ not json"` at the accessor path ->
  `None`.
- `test_read_prior_overall_reads_overall`: write `{"monitor":"research_measurement","overall":"red",
  "checks":[...]}` -> `_read_prior_overall() == "red"`. Also a `{"overall": 123}` (non-str) -> `None`;
  a non-dict top-level `[1,2]` -> `None`.
  - **FAIL pre-impl:** function absent -> ImportError. A naive impl `json.load(...)["overall"]` would
    crash on absent/unparseable/non-dict -> the absent/unparseable tests (asserting `None`, not a
    raise) FAIL.
  - **PASS post-impl:** the try/except + isinstance guards return `None` on every degraded shape.

**Test-safe assertion (explicit):**

- `test_push_targets_tmp_comms_root_not_live`: after `push_...(..., comms_root=tmp/"comms")`, assert
  the tmp `comms/rd/inbox` has the file AND assert the live repo `comms/` was NOT written — i.e.
  `_read_prior_overall` and `push` never reference the live tree when `comms_root` is passed. (Assert
  the message landed under `tmp_path`, and that the call did NOT require the live `comms/` to exist.)
  The default-`comms_root` resolution (`parents[2]/"comms"`) is exercised only by the runner-wiring
  test under a monkeypatched artifact path, never posting to live comms in the suite.

**Impl (Task 2):** add `_RESEARCH_STOPLIGHT_URL`/`_LATEST_JSON_POINTER` constants,
`_default_comms_root()`, `_read_prior_overall`, and `push_research_health_red_to_rd` to
`swing/monitoring/research_health.py` exactly as §2.1/§2.2. The edge gate is the first two lines; the
default-comms-root resolution is `comms_root = comms_root or _default_comms_root()` (the
monkeypatchable seam Task 4's end-to-end test uses); the post body the template; the path-resilient
`role_mail` import inside the try.

**Commit:** `feat(monitoring): Task 2 -- edge-triggered research-health RED push helper (_read_prior_overall + push_research_health_red_to_rd)`

---

### Task 3 — best-effort: a push exception is swallowed + logged; the step still writes latest.json

**Files:** `swing/monitoring/research_health.py` (already has the try/except from Task 2 — this task
adds the PROVING tests + the runner-step still-writes test), `tests/monitoring/
test_research_health_rd_push.py` (helper-level), `tests/pipeline/test_step_research_health.py` (step-level).

**Helper-level test:**

- `test_push_swallows_post_failure_and_logs` (in the monitoring test file): monkeypatch the helper's
  `role_mail` load to raise (e.g. monkeypatch `importlib.util.spec_from_file_location` used inside the
  helper, OR — simpler and more robust — point `comms_root` at a path that cannot be written, e.g. a
  FILE where a directory is expected, forcing `post_message` to raise inside the try). Assert
  `push_...(_red_status(), run_id=1, prior_overall="green", comms_root=<bad>)` returns `False` (NOT a
  raise) and logs a warning (use `caplog`). 
  - **FAIL pre-impl (no try/except):** the underlying `MailError`/`OSError` would PROPAGATE ->
    `pytest.raises`-less call raises -> test errors. 
  - **PASS post-impl:** the helper's `except Exception` swallows -> returns `False` + a `log.warning`.

  Implementation detail for a deterministic failure: create `bad = tmp_path / "comms"; bad.write_text(
  "x")` (a regular FILE at the comms-root path). `post_message` -> `_ensure_tree(root)` does
  `(root / role / "inbox").mkdir(parents=True)` which raises `NotADirectoryError`/`FileExistsError`
  on a file-typed `root` -> the helper's try/except swallows it. (Confirm the exact exception in the
  red phase; the `except Exception` catches any of them.)

**Step-level test (in `tests/pipeline/test_step_research_health.py`):**

- `test_step_still_writes_latest_json_when_push_raises`: seed a db that produces overall=red (use the
  raw-insert post-baseline NaN-Close recipe from `test_research_health_aggregate.py:_POST_BASELINE_DATE`
  — copy the helper into this test file or import the date constant), `_patch_artifact` to a tmp path,
  monkeypatch `swing.monitoring.research_health.push_research_health_red_to_rd` to raise
  `RuntimeError("push boom")`. Run `_step_research_health(cfg=_Cfg(db, exports_dir), run_id=104)`.
  Assert the tmp `latest.json` EXISTS and is the NEW red envelope (not a prior file) — i.e. the write
  ran despite the push raising.
  - **FAIL pre-fix (push called AFTER the write, or push not wrapped so it escapes before the
    write):** if `push_research_health_red_to_rd` is invoked and allowed to raise BEFORE
    `write_research_health_artifact`, and the step does NOT guard it, the write line is skipped -> the
    tmp `latest.json` is absent (or stale) -> FAILS. 
  - **PASS post-fix:** the helper owns its try/except (returns False on its own internal failure), AND
    even a monkeypatched-to-raise push at the step level cannot skip the write because the write call
    is positioned to ALWAYS run — but since this test monkeypatches the helper to RAISE (bypassing its
    internal swallow), the step ITSELF must tolerate it. **Design resolution:** the step's call to
    `push_research_health_red_to_rd` is itself the best-effort boundary — but the production helper
    never raises (it swallows internally). To make the STEP robust against a hypothetical helper bug
    AND keep the write unconditional, the step wraps the push call defensively too:
    ```python
    try:
        push_research_health_red_to_rd(status, run_id=run_id, prior_overall=prior_overall)
    except Exception as exc:               # belt: the helper already swallows, this is defense-in-depth
        log.warning("research-health RD push raised unexpectedly: %s", exc)
    write_research_health_artifact(status)  # ALWAYS runs
    ```
    With this, the monkeypatched-raise push is caught at the step -> the write still runs -> the test
    passes. (This double-guard mirrors the brief's "the step still completes + still writes
    latest.json" being independent of the push.)

  NOTE for the executing implementer: the existing `test_failing_compute_does_not_write_and_leaves_
  prior_artifact` test asserts a FAILING COMPUTE writes nothing — that contract is UNCHANGED (the push
  is AFTER a successful compute; a compute failure still short-circuits before push + write). Verify
  that existing test still passes after the re-order.

**Commit:** `feat(monitoring): Task 3 -- push best-effort (helper swallows; step double-guards so latest.json always writes)`

---

### Task 4 — runner wiring: read-prior ordering + run_id threading + edge end-to-end

**Files:** `swing/pipeline/runner.py` (impl), `tests/pipeline/test_step_research_health.py` (test).

**Tests:**

- `test_step_runtime_ordering_read_prior_then_push_then_write` (the PRIMARY behavioral ordering
  proof — a true runtime-order assertion, NOT a source-string check, per Codex R1 Major 2): seed a db
  that produces overall=red; `_patch_artifact` to a tmp path; pre-write a PRIOR `latest.json` with a
  VALID GREEN envelope (`{"monitor":"research_measurement","overall":"green","checks":[{"key":"k",
  "status":"green","summary":"s","detail":null}],"generated_ts": <fresh aware-UTC ISO string>}`).
  Install a shared `calls: list[tuple]` recorder and monkeypatch THREE module functions on
  `swing.monitoring.research_health` to append a marker AND delegate to the real impl where needed:
  - `_read_prior_overall`: wrap the REAL function — append `("read_prior", <returned value>)` to
    `calls`, return the real value (so the captured `prior_overall` is the genuine green read).
  - `push_research_health_red_to_rd`: a spy appending `("push", kwargs["prior_overall"],
    kwargs["run_id"])` to `calls` (no real post — this test asserts ORDER + the args, not delivery).
  - `write_research_health_artifact`: a spy appending `("write",)` to `calls` (do NOT actually write
    — or delegate to the real writer; either is fine since we assert order, not file content here).
  Run `_step_research_health(cfg=_Cfg(db, exports_dir), run_id=104)`. Assert:
  - `calls == [("read_prior", "green"), ("push", "green", 104), ("write",)]` — i.e. the prior is read
    FIRST (and is GREEN, the previous night's value, NOT the just-computed red), the push is called
    NEXT with that prior + the threaded `run_id=104`, and the write runs LAST.
  - **FAIL pre-fix (read-after-write / write-first / no run_id thread):** if the step wrote
    `latest.json` before reading prior, the recorded order would be `[("write",), ("read_prior",
    "red"), ...]` (write first, and prior would read RED — the just-written value) -> the exact
    `calls` list assertion FAILS on BOTH the order and the `"green"` value. If `run_id` is not
    threaded, the `("push", "green", 104)` tuple shows `None` not `104` -> FAILS.
  - **PASS post-fix:** the §2.3 order (read prior -> compute -> push -> write) + the threaded
    `run_id=lease.run_id` reproduce the exact `calls` list.
- `test_step_edge_posts_to_rd_end_to_end` (drives the REAL helper, no push monkeypatch): `_patch_artifact`
  tmp; pre-write a prior GREEN envelope; seed a RED db; monkeypatch the Task-2 seam
  `swing.monitoring.research_health._default_comms_root` to return `tmp_path / "comms"` (so the REAL
  `push_research_health_red_to_rd` posts to the tmp tree, never the live `comms/`). Run
  `_step_research_health(cfg=_Cfg(db, exports_dir), run_id=104)`. Assert exactly one file in the tmp
  `comms/rd/inbox` whose frontmatter is `from: pipeline`, `to: rd`, `type: status`, and whose body
  carries the red key + `104`.
  - **FAIL pre-fix:** before the wiring, the step never calls the push -> no inbox file -> FAILS.
  - **PASS post-fix:** the RED edge fires through the real helper -> one inbox `status` from
    `pipeline`.
- `test_step_no_edge_when_prior_already_red`: pre-write a prior RED envelope; seed a RED db;
  monkeypatched `_default_comms_root` -> tmp; run the step; assert the tmp `comms/rd/inbox` is EMPTY
  (no edge: red->red).
  - **FAIL pre-fix (post-on-any-red):** would post -> inbox non-empty -> FAILS.
  - **PASS post-fix:** prior red -> no edge -> no post (but the write still refreshes latest.json,
    asserted separately by the existing write test).
- `test_runner_call_site_threads_run_id_and_step_placement` (a THIN WIRING SMOKE CHECK — NOT the
  ordering proof; the runtime ordering is proven by `test_step_runtime_ordering_...` above). Mirrors
  the existing `test_runner_invokes_step_via_step_guard...` source check: read `runner.__file__`
  source; assert `_step_research_health(cfg=cfg, run_id=lease.run_id)` appears (run_id threaded), is
  still inside `step_guard(lease, "research_health", logger=log)`, and still placed between
  `_step_shadow_expectancy(cfg=cfg` and `lease.step("complete")`.
  - **Why source-string here is OK (and was a Codex R1 Major when used FOR ordering):** this asserts
    only the call-site WIRING (run_id threaded + step placement under the guard, between shadow and
    complete) — facts that ARE textual (which function is called where, with what arg). It does NOT
    assert intra-function execution order; that is the behavioral test's job. Keeping a source check
    for placement matches the existing runner-step convention; it is brittle only to a literal rename
    of the call, which is acceptable for a wiring assertion.
  - **FAIL pre-fix:** the existing call site is `_step_research_health(cfg=cfg)` (no run_id) -> the
    `run_id=lease.run_id` substring assertion FAILS.
  - **PASS post-fix:** the call site passes `run_id=lease.run_id`.

**Impl:**
- Edit `_step_research_health` to the §2.3 shape: add `run_id: int | None = None` param; read
  `prior_overall = _read_prior_overall()` BEFORE the conn; after compute, the step-level
  `try: push_research_health_red_to_rd(status, run_id=run_id, prior_overall=prior_overall) except
  Exception: log.warning(...)`; then `write_research_health_artifact(status)`.
- Edit the call site `runner.py:~1061` from `_step_research_health(cfg=cfg)` to
  `_step_research_health(cfg=cfg, run_id=lease.run_id)`.
- (No new helper here — `_default_comms_root()` was introduced in Task 2; the runner-wiring
  end-to-end test monkeypatches that existing seam.)

**Commit:** `feat(pipeline): Task 4 -- wire the RED edge push into _step_research_health (read-prior-before-write + run_id thread)`

---

### Task 5 — existing-test regression sweep + fast-suite-to-green BEFORE Codex

Not a code task — the recipe-mandated full fast-suite run BEFORE the Codex review (§2 of the recipe).
After Tasks 1-4 commit:
- Run `python -m pytest -m "not slow" -q` from the worktree; fix any failure to green. Pay special
  attention to:
  - `tests/pipeline/test_step_research_health.py::test_failing_compute_does_not_write_and_leaves_
    prior_artifact` (the re-order must not break write-nothing-on-compute-failure).
  - `tests/pipeline/test_step_research_health.py::test_step_runs_and_writes_latest_json` and the other
    existing direct-call tests (they call `_step_research_health(cfg=...)` with NO `run_id` -> default
    None -> they seed GREEN dbs so no push fires -> they must still pass; the new `run_id` param
    default-None preserves them).
  - `tests/scripts/test_role_mail.py` existing tests (the VALID_FROM widen must not break the
    existing sender-rejection test `test_invalid_from_role_rejected` — assert it uses a sender NOT in
    the new tuple; if it used a now-valid sender it would break, but it uses an arbitrary invalid one).
  - `tests/web/test_routes/test_health_stoplights.py` (the artifact contract is unchanged; should be
    untouched).
- `ruff check swing/` clean (the helper + the runner edit are in `swing/`; `scripts/role_mail.py` is
  outside the ruff gate but keep it clean anyway).

No commit (verification only) unless a fix is needed (then `fix(...): ...`).

---

## 5. Task 0 grounding note — GUI research-stoplight pointer (GROUNDED)

The GUI research-stoplight drill-down route is `GET /health/research`, REGISTERED at
`swing/web/routes/health.py:37` (`@router.get("/health/research", ...)` -> `health_research_page`,
the 18-D-checks drill-down). So `_RESEARCH_STOPLIGHT_URL = "/health/research"` is grounded and
correct. This is a display pointer in the message body only — a wrong string would be cosmetic, not a
correctness defect, but it is confirmed against the live route. (If the executing implementer finds
the route has moved by merge time, re-confirm and update the one constant.)

---

## 6. Distinguishing-test arithmetic — summary table

| Test | Pre-impl behavior (FAILS) | Post-impl behavior (PASSES) |
|---|---|---|
| pipeline valid sender | sender-gate `MailError` -> rc 1, empty inbox | rc 0, one `from: pipeline` file |
| pipeline decision_request rejects (L1) | error text `invalid --from` (sender gate) | error text contains `L1` (L1 gate bites) |
| pipeline -> invalid recipient rejects | sender-gate failure | recipient-gate `invalid recipient` |
| red + prior!=red -> posts | helper absent / stub False -> no post | True + one `status` to rd |
| red + prior==red -> no post | naive post-on-red -> posts | edge gate -> no post |
| yellow -> no post | red-or-yellow trigger -> posts | overall!=red -> no post |
| green -> no post | non-green-prior trigger -> posts | overall!=red -> no post |
| absent prior + red -> posts | None-treated-as-skip -> no post | None!=red -> edge -> posts |
| content carries key+summary+DETAIL+runid+pointers | body omits detail -> substring FAILS | full body template -> all substrings present |
| detail=None -> `(none)` placeholder | naive None render / omitted line | explicit `(none)` substitution |
| `_read_prior_overall` absent/unparseable -> None | naive json.load crashes | try/except + isinstance -> None |
| push swallows post failure | exception propagates -> test errors | `except Exception` -> False + warning |
| step still writes latest.json when push raises | push-before-write unguarded -> write skipped -> no artifact | step double-guard -> write always runs |
| runtime order read-prior/push/write + run_id (BEHAVIORAL) | write-first / read-after-write -> `calls` shows write first + prior `red`; no run_id -> `None` | `calls == [("read_prior","green"),("push","green",104),("write",)]` |
| step edge posts end-to-end (REAL helper, tmp comms via `_default_comms_root` monkeypatch) | step never calls push -> empty inbox | real helper posts one `status` to rd |
| step no-edge when prior red | post-on-any-red -> inbox non-empty | red->red -> empty inbox |
| call-site WIRING (run_id thread + step placement; NOT ordering) | `_step_research_health(cfg=cfg)` (no run_id) | `_step_research_health(cfg=cfg, run_id=lease.run_id)` |

---

## 7. Out of scope (V1) — note to RD

- **Weekly re-nag while red: DEFERRED.** V1 is pure edge-trigger (NO re-nag). A persistent-red is
  covered by the passive backstops: the 18-F GUI research stoplight stays red, the operator's weekly
  glance, and RD's monthly read. **note "no re-nag" to RD.** (A V2 nicety would need a last-push
  timestamp = new state.)
- **Pushing on YELLOW: excluded** (RD: cry-wolf; the yellows are self-healing/benign-by-design).
- **Pushing to anyone but RD; any `decision_request`** (authority stays operator-routed; L1 unchanged).
- The `comms/roles/` store / scaffold — unrelated harness template.

---

## 8. Executing-implementer checklist

1. Worktree reuse (this worktree, branch `18h7-research-health-rd-push`).
2. Task 0 grounding (confirm `_RESEARCH_STOPLIGHT_URL`).
3. Tasks 1-4 TDD red->green->commit (one commit per task; conventional; ZERO Co-Authored-By;
   plain-prose final paragraph; no `--no-verify`; no amend).
4. Task 5: full fast suite to green + `ruff check swing/` BEFORE the Codex review.
5. Codex **review-strong** to `NO_NEW_CRITICAL_MAJOR` + `codex-auto-review` (production-code arc;
   repo-access binding review per recipe §3). Persist every round to `.copowers-findings.md`.
6. Return report to the orchestrator (chat only; never `role_mail`). Trailer-clean verify:
   `git log main..HEAD --format='%H%n%(trailers)'`.
