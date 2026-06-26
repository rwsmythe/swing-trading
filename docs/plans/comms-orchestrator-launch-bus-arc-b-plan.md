# G6 Arc B — Orchestrator launch role + GUI bus — Implementation Plan

**Brief:** `docs/comms-orchestrator-inbox-arc-b-commissioning-brief.md` (CHARC-owned, COMMISSIONED, SUB-TRIPWIRE GO).
**Base:** `main` @ `ab5431d8` (the brief-commission commit; current HEAD at writing-plans).
**Worktree:** `.worktrees/g6b-orchestrator-launch-bus`.
**Type:** NORMAL swing arc — `scripts/start_directors.ps1` + `scripts/comms_ui.py` only. NO `swing/` package touch, NO schema, NO new dependency, NO comms-core change (read-only of the Arc-A registry/inboxes).

This is a PLAN. The executing implementer runs the ordered TDD tasks (red -> green -> commit), the full fast suite, the WSL-Codex review-strong + codex-auto-review (production-adjacent harness, repo-access), then the operator's binding §5.10 browser witness.

---

## 0. Premise grounding (verified on disk 2026-06-25 at HEAD `ab5431d8`)

The reconciliation notes (`docs/comms-orchestrator-inbox-reconciliation-notes.md`) are STALE; the brief §1 corrections were re-verified against the LIVE files. What swing ALREADY HAS (do NOT rebuild):

- **`scripts/start_directors.ps1`** is already role-parameterized — `[ValidateSet('charc','rd','both')]` (:75), `$BootstrapFiles` map (:90-93), `$RoleTitles` map (:94) — and already spawns via `wt -w 0 new-tab` (:223; the **new-tab spawn LOCK is satisfied — do NOT touch it**). It sets `$env:SWING_ROLE='<role>'` **inside the spawned shell** via `Build-LaunchCommand` (:191-201) and `Start-RoleWindow` (:216-231), with the `-EncodedCommand` plain-window fallback (the three-tab `;`-misparse fix is in `Get-EncodedCommand`, :204-214). Launch flags `--model opus --effort max --permission-mode auto` (`$LaunchArgs`, :102). `Start-Fresh`/`Start-Resume` (:239-279) are role-GENERIC — they index `$BootstrapFiles[$role]`, `$RoleTitles[$role]`, `$map[$role]`. `-DryRun` (:79, :251, :276, :291) prints the computed session name + the exact claude command line + the inner shell command and exits without launching or writing the map. The `comms/.sessions.json` read-modify-write is serial (:296-302).
- **`scripts/comms_ui.py`** already has: `BUS_ROLES=("charc","rd")` (:61); `LAUNCH_ROLES=("both","charc","rd")` (:66); `/directors/launch` POST with the **L5 fixed-argv** path (`argv = ["powershell","-NoProfile","-File", f"scripts/{LAUNCHER}", "-Role", role]`, :753-754) gated by `if role not in LAUNCH_ROLES: return 400` (:746); `/orchestrator-bootstrap` (GET, serves `orchestrator_bootstrap.md` verbatim, :769-773; `BOOTSTRAP_FILE`, :69); the **"Copy orchestrator spin-up"** button (:603-604) + its `copyOrchestratorBootstrap()` fetch (:342-359); `/panes/bus` (:787-789) reading `_bus_ctx()` (:660-663); `_recorded_sessions` reading `.sessions.json` (:175-190); `_inbox_messages` (:163-166). **`_orchestrator_inbox_messages` does NOT exist yet** (grep: 0 hits).
- **`scripts/orchestrator_bootstrap.md`** EXISTS (the served copy-text).
- **Arc-A seam (read-only for Arc B):** `scripts/comms_session_registry.py` — `per_generation_inbox(root, sid)` -> `comms/orchestrator/<sid>/inbox` (:90-94), `read_entries` (:177), `is_valid_session_id` (:56-66), `REGISTRABLE_ROLES=("charc","rd","orchestrator")` (:38). It is stdlib-only (no fastapi/web imports). A launched session with `SWING_ROLE=orchestrator` auto-registers via Arc-A's SessionStart hook because `orchestrator` is in `REGISTRABLE_ROLES`.
- **`scripts/role_mail.py`** — Arc A ALSO landed orchestrator addressing: `VALID_TO=("charc","rd","operator","orchestrator")` (:45), the `:<sid>` form, and a lazy `_load_registry()` cached importer (:85-101). So the reconciliation-notes claim "`--to orchestrator` STILL REJECTED" is ALSO stale. (Arc B does NOT touch role_mail; this is grounding only.)

**Conclusion:** swing LACKS exactly three things, which are the Arc B delta — (1) the `orchestrator` ROLE in the launcher enum + maps, (2) `orchestrator` in `LAUNCH_ROLES`, (3) the per-gen orchestrator bus aggregation.

---

## 1. The delta (corrected, narrow §2)

### 1.1 Launcher — add the `orchestrator` role to `start_directors.ps1`

Three additions, all DATA (map/enum entries), zero control-flow change (so PowerShell-5.1-safe by construction):

1. `[ValidateSet('charc','rd','both')]` (:75) -> `[ValidateSet('charc','rd','orchestrator','both')]`.
2. `$BootstrapFiles` (:90) gains `'orchestrator' = Join-Path $ScriptDir 'orchestrator_bootstrap.md'` (the EXISTING file).
3. `$RoleTitles` (:94) gains `'orchestrator' = 'ORCHESTRATOR'` (ASCII; the wt tab title).

Everything else applies UNCHANGED. `Start-Fresh`/`Start-Resume` index the three maps by `$role`; for `$role='orchestrator'` they read the new entries and the existing `wt new-tab` + `$env:SWING_ROLE`-inside-shell path runs verbatim. The launched orchestrator sets `SWING_ROLE=orchestrator` -> Arc-A's SessionStart hook auto-registers the generation (because `orchestrator` is in `REGISTRABLE_ROLES`).

**DECISION — `.sessions.json` participation: the orchestrator PARTICIPATES in the map exactly like the directors (fresh writes/overwrites the `orchestrator` entry; resume reads `$map['orchestrator'].session_name`).** Justification:
- It is the path of LEAST divergence and least code. `Start-Fresh`/`Start-Resume` are role-generic; adding the three map/enum entries makes the orchestrator "just another role" with ZERO new launch-function code — directly satisfying the brief's "the existing fresh/resume ... all apply UNCHANGED." A fresh-ONLY orchestrator would require a NEW special-case branch in `Start-Resume`/`main` (more surface, contradicts "unchanged").
- `.sessions.json` participation is purely a display-name convenience for the `/resume` picker + the terminal title; it creates NO contradiction with the rotating model. The orchestrator's REAL liveness/addressing record is the Arc-A `comms/sessions/<sid>.json` registry (written by the SessionStart hook, INDEPENDENT of `.sessions.json`) — exactly as the brief states ("the Arc-A `comms/sessions/` registry, NOT `.sessions.json`, is its liveness record either way"). Directors also rotate (CONTEXT RESET = FRESH MODE overwrites the entry); the orchestrator follows the identical pattern.
- Resume of an orchestrator with no recorded entry already degrades gracefully: `Start-Resume` prints "no recorded session ... use fresh mode" and returns (exit 0), surfaced as a GUI flash.

**Deliberate V1 NON-fix (cosmetic, flagged):** `New-SessionName($role)` (:186-189) returns `"director-$role-$stamp"` — so an orchestrator fresh session is DISPLAY-named `director-orchestrator-<stamp>`. This is cosmetic only (the name is a `/resume` picker filter + the prompt-box label; the wt TAB title comes from `$RoleTitles['orchestrator']='ORCHESTRATOR'`, which is correct). Resume round-trips fine (it reads the recorded name string verbatim). Leaving `New-SessionName` UNCHANGED honors "applies unchanged," keeps the directors' existing naming scheme intact (a rename would alter `director-charc-*`/`director-rd-*` too), and adds zero launch-function code. The `director-` prefix wart is noted for a possible later cosmetic polish (operator's call; out of Arc B's enumerated delta). The executing implementer MUST NOT change `New-SessionName` under this arc.

### 1.2 GUI launch enum — add `orchestrator` to `LAUNCH_ROLES`

`LAUNCH_ROLES=("both","charc","rd")` (:66) -> `("both","charc","rd","orchestrator")`.

**VERIFIED: the `/directors/launch` route needs NO other change.** The route (:737-767) enum-validates `if role not in LAUNCH_ROLES: return 400` (:746) BEFORE building `argv = ["powershell","-NoProfile","-File", f"scripts/{LAUNCHER}", "-Role", role]` (:753-754). With `orchestrator` in the enum, `role="orchestrator"` passes the gate and argv becomes `... -Role orchestrator`. L5 holds: the role is enum-validated before it reaches argv; nothing user-typed flows to the command line. The launch-strip dropdown (`_DIRECTORS_STRIP`, :594, `{% for r in launch_roles %}`) renders `launch_roles = list(LAUNCH_ROLES)` (:652), so the `orchestrator` option appears automatically — NO template change.

**DECISION — the directors-strip "unread / session recorded" LIST stays `charc`/`rd` (= `BUS_ROLES`).** `_directors_ctx` (:645-654) drives that list with `_inbox_messages` (singular inbox) + `_recorded_sessions` (keyed on `BUS_ROLES`). The orchestrator is PER-GEN, so its presence belongs in the BUS (per-gen, §1.3), NOT the singular-inbox directors list. Only the launch DROPDOWN gains `orchestrator` (via `launch_roles`). This keeps the per-gen vs singular concerns cleanly separated and requires no change to `_recorded_sessions`/`_directors_ctx`.

### 1.3 Orchestrator bus aggregation — read-only `_orchestrator_inbox_messages`

A NEW read-only helper that walks `comms/orchestrator/<sid>/inbox` across ALL generations (per-gen, since the orchestrator rotates), grouped by generation, surfaced as a DEDICATED section inside the EXISTING `/panes/bus` pane — NOT a naive `BUS_ROLES` append (the orchestrator is per-gen; `BUS_ROLES`/`_recorded_sessions`/`_inbox_messages` all assume a SINGULAR `comms/<role>/inbox`).

**Why a dedicated section in `_BUS_PANE` (not a new pane/route):** it reuses the existing `#bus-pane` 5s poll wiring (:455-458), the expand-preserve `data-key` JS, and the bus-is-read-only posture — adding zero new poll wiring and zero new route. Lowest-risk surface.

Signature + behavior:

```python
def _orchestrator_inbox_messages(root: Path, now: datetime) -> list[dict]:
    """Per-generation orchestrator inboxes, grouped by session, newest-active
    first. READ-ONLY; never acks/writes. Defensive: any malformed/absent
    structure degrades to [] (or skips the bad entry) -- NEVER raises.

    Returns: [{"sid": <session_id>, "messages": [Message, ...]}, ...]
    """
```

Implementation shape (the executing implementer follows this; line-anchor the helpers at exec time):
- Resolve the registry lazily via a comms_ui-local `_load_registry()` (mirror role_mail's `_load_registry`, :85-101 — `importlib.util.spec_from_file_location("comms_session_registry", _SCRIPTS_DIR / "comms_session_registry.py")`, cached) that RETURNS the module or `None` on any import failure (so a broken/absent registry degrades the bus to empty, never a 500 at app construction). This single-sources the path shape (`per_generation_inbox`) + the safety rule (`is_valid_session_id`) — lessons-learned guard #4 (no reader/path-shape drift).
- `base = root / "orchestrator"`. If `not base.is_dir()`: return `[]`.
- For each child of `sorted(base.iterdir())`: skip if not a dir (a stray file is not a generation); skip if `not registry.is_valid_session_id(child.name)` (guards BEFORE calling `per_generation_inbox`, which RAISES `ValueError` on an unsafe id). **This enumerates from the DIRECTORY, registry-INDEPENDENT — and that is DELIBERATE, brief-mandated (NOT a registry-as-source-of-truth enumeration; Codex R3 MAJOR #2 was REJECTED here):** brief §2 item 3 says "walks `comms/orchestrator/<sid>/inbox` across ALL generations," and reconciliation-notes lessons-learned guard #1 ("Registry-pruned != gone") establishes that a generation pruned from `comms/sessions/` (idle >45 min) is still RESUMABLE and its queued mail MUST stay visible — the entire reason per-gen inboxes are durable across rotation. Enumerating from `read_entries` would HIDE messages queued for a pruned-but-resumable generation (a regression against the brief). So a pruned-but-on-disk generation is STILL shown. **Live-code evidence (verified on disk — the premise is NOT an assumption):** `comms_session_registry.prune_stale` unlinks ONLY `comms/sessions/<id>.json`, NEVER the `comms/orchestrator/<sid>/` inbox tree — so a pruned gen's inbox + its queued mail PERSIST on disk and are invisible to `read_entries`; mail can still be DELIVERED there via role_mail's registry-INDEPENDENT `:<sid>` form, so it MUST stay visible in the bus. And the SessionStart hook calls `ensure_per_generation_inbox` (`comms_session_hook.py:111`, re-ensured on resume :133) which CREATES `comms/orchestrator/<sid>/{inbox,read}` at register time — so a registered-but-EMPTY generation HAS an inbox dir on disk and the disk walk DOES show it (rendered "(empty)"); the disk walk misses nothing the registry would have. (Codex R3/R4 repeatedly proposed registry-source-of-truth enumeration; REJECTED with this evidence — the reviewer lacks the brief + this live-code context.)
- `inbox = registry.per_generation_inbox(root, sid)`; `paths = sorted(inbox.glob("*.md")) if inbox.is_dir() else []`; `msgs = [_message_from_path(p, "orchestrator", now) for p in paths]` (reuse the existing `_message_from_path`, :132-160 — the same Message dataclass + malformed-frontmatter fallback; `role="orchestrator"` so a malformed message's `to` falls back sensibly; the per-gen sid is carried on the GROUP, not the Message).
- **Defensive guards must catch BOTH `OSError` AND `ValueError` (Codex R2 MAJOR — adopted):** wrap the per-child body in `try/except (OSError, ValueError): continue` and the whole walk in `try/except (OSError, ValueError): return []`. `is_valid_session_id(child.name)` is the PRIMARY pre-guard, but the `(OSError, ValueError)` except is defense-in-depth: if the validator and `per_generation_inbox` ever disagree, the loaded registry's contract drifts, or any path-validation step raises, the bad entry is SKIPPED (or the walk degrades to `[]`) — NEVER a 500. This honors the brief's defensive-never-raises lock without relying solely on the pre-guard. (If `_load_registry()` returned `None`, `_orchestrator_inbox_messages` returns `[]` immediately — the bus simply shows the empty state.)
- Order generations **most-recently-MESSAGED first** (Codex R3 MAJOR #1 — the semantic is named precisely): sort key `(max(m.filename for m in g["messages"], default=""), g["sid"])`, `reverse=True` — the gen with the newest UTC-stamped message floats to the top; empty-inbox gens (key `("", sid)`) sort last; deterministic sid tiebreaker (no `sort`-order flake). This is the correct semantic for a MAIL bus (the operator wants the generation with the freshest mail at the top) and is the ONLY recency signal uniformly available across ALL disk-enumerated gens, INCLUDING pruned ones with no registry entry — so it is NOT coupled to the registry's `started_ts` (which would be unavailable for pruned-but-resumable gens). Test 3b pins this with lexically-CONFLICTING fixtures so a naive ascending-sid `sorted(iterdir())` sorter FAILS. **Filename-stamp invariant (Codex R5 MINOR — noted):** the `max(m.filename)` recency key relies on the canonical role_mail filename stamp `<yyyymmddTHHMMSSZ>-<from>-<slug>.md` — the SAME convention the existing `_history_ctx` already sorts by (`msgs.sort(key=lambda m: m.filename, reverse=True)`, comms_ui.py:671), so this is consistent with the live codebase; a malformed/renamed filename degrades to its lexical position (non-fatal — read-only display, never a crash).

`_bus_ctx()` (:660-663) gains `"orchestrator_generations": _orchestrator_inbox_messages(comms_root, now)`. The `/panes/bus` route (:787-789) already renders `_bus_ctx()` — no route change.

`_BUS_PANE` template (:510-530) gains a dedicated section AFTER the director loop:

```jinja
<h2>Orchestrator bus (read-only)</h2>
{% if not orchestrator_generations %}<p class="empty">(no orchestrator generations)</p>{% endif %}
{% for g in orchestrator_generations %}
<h3 style="font-size:0.95rem;margin:0.5rem 0 0.2rem">generation {{ g.sid }}
  -- {{ g.messages|length }} unread</h3>
{% if not g.messages %}<p class="empty">(empty)</p>{% endif %}
{% for m in g.messages %}
<details class="msg
  {%- if m.is_decision_request %} decision-request{% endif %}
  {%- if m.stale %} stale{% endif %}" data-key="orch:{{ g.sid }}:{{ m.filename }}">
  <summary>
    <span class="posted">{{ m.posted }}</span>
    <span class="from">{{ m.frm }}</span>
    <span class="type">{{ m.mtype }}</span>
    <span class="subject">{{ m.subject }}</span>
    {% if m.stale %}<span class="age">{{ m.age_days }}d stale</span>{% endif %}
  </summary>
  <pre class="body">{{ m.body }}</pre>
</details>
{% endfor %}
{% endfor %}
```

Notes:
- **NO ack form / NO `hx-post`** in the orchestrator rows (L3: the bus is read-only — mirror the director-bus rows, which carry no `/ack`). The existing `test_bus_pane_has_no_ack_affordance` (asserts `/ack` not in the bus body) MUST stay green; the orchestrator section introduces no `/ack`.
- **data-key is COMPOSITE** `orch:{{ g.sid }}:{{ m.filename }}` — guarantees uniqueness across generations (two gens could share a filename) and never collides with the director-bus/inbox bare-filename keys. The expand-preserve JS (`details.msg[data-key]`) treats the key as an opaque string, so a composite key works unchanged.
- The orchestrator rows reuse the existing `.msg`/`.stale`/`.decision-request`/`.age` classes -> they inherit the dark-theme CSS variables automatically (no new CSS).

---

## 2. Ordered TDD tasks (red -> green -> commit)

Each task: write the failing test, SEE it fail (the right way), minimal implementation, SEE it pass, commit. Test files: `tests/scripts/test_comms_ui.py` (extend) for the GUI; a new `tests/scripts/test_start_directors_orchestrator.py` for the launcher subprocess test (keeps the PowerShell-subprocess test isolated). Match the existing test style (`_load`, the `comms`/`client` fixtures, `_SAME_ORIGIN`, `_mock_run`, `_launcher_argv`).

### Task 1 — Launcher: add the `orchestrator` role (3 map/enum edits)

**Test 1a (static-content, always runs, distinguishes).** Add `tests/scripts/test_start_directors_orchestrator.py`. Read `scripts/start_directors.ps1` as text; assert all three additions:
- the `[ValidateSet(...)]` line contains `'orchestrator'`;
- `$BootstrapFiles` block contains `'orchestrator'` AND `orchestrator_bootstrap.md`;
- `$RoleTitles` block contains `'orchestrator'`.

Arithmetic: PRE — none of the three appear (the launcher knows only charc/rd/both) -> FAIL. POST -> PASS. (Static-content assertion, deterministic, no claude/powershell needed; the always-runs distinguisher for the launcher delta.)

**Implementation 1a:** the three edits in §1.1.

**Test 1b (behavioral `-DryRun`, skip-guarded).** Also in `test_start_directors_orchestrator.py`. Guard: `if shutil.which("powershell") is None or shutil.which("claude") is None: pytest.skip(...)` (the launcher's `Invoke-Preflight` requires the `claude` CLI on PATH BEFORE the DryRun short-circuit; the merged-head no-false-green re-run executes on the operator's box where both are present, so this provides REAL coverage there and skips cleanly in a claude-less CI). Run:

```python
import subprocess
script = Path(__file__).resolve().parents[2] / "scripts" / "start_directors.ps1"
r = subprocess.run(["powershell", "-NoProfile", "-File", str(script),
                    "-Role", "orchestrator", "-DryRun"],
                   capture_output=True, text=True, timeout=60)
assert r.returncode == 0
out = r.stdout + r.stderr
assert "$env:SWING_ROLE='orchestrator'" in out          # the inner-shell role set
assert "claude --model opus --effort max --permission-mode auto" in out
assert "orchestrator_bootstrap.md" in out               # the bootstrap in the prompt
assert "DRY RUN" in out                                 # no window launched, no map write
```

Arithmetic: PRE — `-Role orchestrator` fails `[ValidateSet]` (charc/rd/both only) -> PowerShell parameter-binding error, nonzero exit, the `$env:SWING_ROLE='orchestrator'` inner command never printed -> FAIL. POST — the role is valid, DryRun computes + prints the inner command -> PASS. (Distinguishes; reuses the existing `-DryRun` print-and-exit path; never launches a window or writes the map.)

**On the skip-guard + the distinguisher-burden split (Codex R2 MINOR — clarified).** The DISTINGUISHING burden for the launcher delta is carried by the ALWAYS-RUNS static-content Test 1a (no `claude`/`powershell` dependency) — so the launcher change is covered deterministically even in a `claude`-less CI. Test 1b is a supplementary BEHAVIORAL net that runs on the OPERATOR'S box, which is exactly where the merged-head no-false-green re-run executes (both `powershell` and `claude` are present there), so the skip is intentional and provides real coverage where it runs. Mocking the `claude` preflight INSIDE a spawned PowerShell subprocess is not practical, so the `shutil.which` skip-guard is the honest path (not a weakened distinguisher — 1a already distinguishes). The `assert "DRY RUN" in out` IS grounded: the launcher prints `Write-Info "DRY RUN -- no windows launched, session map not written."` (`start_directors.ps1:291`). The executing implementer MAY drop the `"DRY RUN"` assert if it proves environment-fragile, but MUST keep the load-bearing asserts (`$env:SWING_ROLE='orchestrator'`, the exact claude command, the bootstrap path).

**Commit 1:** `feat(scripts): Task 1 -- add orchestrator role to start_directors.ps1 (ValidateSet + BootstrapFiles + RoleTitles)`.

### Task 2 — GUI: `orchestrator` in `LAUNCH_ROLES` (launch strip offers it + route accepts it)

**Test 2a (launch strip offers orchestrator, distinguishes).** In `test_comms_ui.py`:
```python
def test_launch_strip_offers_orchestrator(client):
    page = client.get("/").text
    assert '<option value="orchestrator">' in page
```
Arithmetic: PRE — `LAUNCH_ROLES=("both","charc","rd")` renders only `value="both"/"charc"/"rd"`; the page's other `orchestrator` mentions are the copy button text + `/orchestrator-bootstrap` (NEITHER is `<option value="orchestrator">`) -> FAIL. POST — the new enum renders the option -> PASS. (Asserts the SPECIFIC option markup, NOT a bare `orchestrator` substring that already passes pre.)

**Test 2b (route accepts the enum-validated orchestrator role; exact argv; subprocess MOCKED).** Mirror `test_launch_fresh_runs_exact_argv` / `_launcher_argv` with `role="orchestrator"`:
```python
def test_launch_orchestrator_fresh_runs_exact_argv(client, monkeypatch):
    calls = _mock_run(monkeypatch)
    r = client.post("/directors/launch",
                    data={"role": "orchestrator", "mode": "fresh"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 200
    assert len(calls) == 1
    assert calls[0][0] == _launcher_argv("orchestrator", resume=False)
    assert calls[0][1].get("cwd") == str(comms_ui._SCRIPTS_DIR.parent)

def test_launch_orchestrator_resume_appends_resume_flag(client, monkeypatch):
    calls = _mock_run(monkeypatch)
    client.post("/directors/launch",
                data={"role": "orchestrator", "mode": "resume"},
                headers=_SAME_ORIGIN)
    assert calls[0][0] == _launcher_argv("orchestrator", resume=True)
```
Arithmetic: PRE — `role="orchestrator"` hits `if role not in LAUNCH_ROLES: return 400` -> status 400, `calls == []` -> both assertions FAIL. POST — passes the gate, argv = `[..., "-Role", "orchestrator"]` (+ `-Resume`) -> PASS. (MOCK-not-spawn: `_mock_run` replaces `comms_ui.subprocess.run`; asserts the argv that WOULD run, never spawns a window.)

**Implementation 2:** add `orchestrator` to `LAUNCH_ROLES` (:66). (No route/template change — verified §1.2.)

**Test 2c (L5 lock regression net — passes pre AND post; not a distinguisher).** Assert a non-enum / user-typed role is still rejected at the enum before argv:
```python
def test_launch_rejects_arbitrary_user_typed_role(client, monkeypatch):
    calls = _mock_run(monkeypatch)
    r = client.post("/directors/launch",
                    data={"role": "orchestrator; rm -rf /", "mode": "fresh"},
                    headers=_SAME_ORIGIN)
    assert r.status_code == 400
    assert calls == []   # subprocess NEVER reached
```
(The existing `test_launch_rejects_invalid_role` [role="operator"] already covers the enum gate; this adds the injection-shaped-string net. Both pass pre and post — they are L5 REGRESSION assertions that would catch a future change widening the gate to accept user-typed values.)

**Commit 2:** `feat(scripts): Task 2 -- offer orchestrator in the comms-UI launch strip (LAUNCH_ROLES)`.

### Task 3 — GUI: the per-generation orchestrator bus aggregation

Test seeding uses RAW file writes into `comms/orchestrator/<sid>/inbox/` (the same raw-write pattern as `test_bus_pane_styles_stale_over_7_days`), NOT `role_mail` — synthetic per-gen inbox content, independent of whether role_mail's orchestrator `:<sid>` send path is exercised. A small local helper:
```python
def _seed_orch_msg(comms, sid, fname, frm="orchestrator", to=None, mtype="status",
                   subject="s", body="b"):
    inbox = comms / "orchestrator" / sid / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    to = to or f"orchestrator:{sid}"
    (inbox / fname).write_text(
        f"---\nfrom: {frm}\nto: {to}\ntype: {mtype}\nsubject: {subject}\n"
        f"posted: 2026-06-20T00:00:00Z\n---\n\n{body}\n", encoding="utf-8")
```
Filenames follow the role_mail stamp shape `<yyyymmddTHHMMSSZ>-<from>-<slug>.md`. All fixture sids used below (`gen-aaa`, `gen-bbb`, `gen-ccc`, `gen-ok`, `gen-x`) conform to `is_valid_session_id` (`_SESSION_ID_RE = [A-Za-z0-9._-]+`, `comms_session_registry.py:53`), so they are ACCEPTED by the bus pre-guard; the deliberately-invalid `"bad name"` dir in Test 3d (a space) is correctly REJECTED by that regex (Codex R4 MINOR — grounded).

**Test 3a (aggregates across MULTIPLE gens, distinguishes).**
```python
def test_orchestrator_bus_aggregates_across_generations(client, comms):
    _seed_orch_msg(comms, "gen-aaa", "20260619T010000Z-charc-a.md", subject="hello-aaa")
    _seed_orch_msg(comms, "gen-bbb", "20260620T010000Z-rd-b.md", subject="hello-bbb")
    _seed_orch_msg(comms, "gen-bbb", "20260620T020000Z-operator-c.md", subject="hello-bbb2")
    body = client.get("/panes/bus").text
    assert "Orchestrator bus" in body
    assert "hello-aaa" in body
    assert "hello-bbb" in body
    assert "hello-bbb2" in body
    assert "gen-aaa" in body and "gen-bbb" in body   # grouped by generation
```
Arithmetic: PRE — `_orchestrator_inbox_messages` does not exist + `_BUS_PANE` has no orchestrator section -> the seeded messages never render -> FAIL (subjects + header absent). POST -> PASS.

**Test 3b (most-recently-messaged generation first — THREE generations so recency is NON-MONOTONIC in sid; distinguishes recency from BOTH name-sort directions; Codex R4 MAJOR — adopted).** Two generations can never distinguish a recency sort from BOTH an ascending- AND a descending-sid sorter (with 2 items the recency order necessarily equals one of them). Use THREE gens whose recency order is non-monotonic in sid — middle-sid gen carries the newest message:
```python
def test_orchestrator_bus_most_recently_messaged_generation_first(client, comms):
    _seed_orch_msg(comms, "gen-aaa", "20260301T010000Z-charc-a.md", subject="mid-gen")
    _seed_orch_msg(comms, "gen-bbb", "20260620T010000Z-rd-b.md", subject="new-gen")
    _seed_orch_msg(comms, "gen-ccc", "20260101T010000Z-charc-c.md", subject="old-gen")
    body = client.get("/panes/bus").text
    # recency (newest msg first) = [bbb (Jun), aaa (Mar), ccc (Jan)] -- which
    # equals NEITHER ascending-sid [aaa,bbb,ccc] NOR descending-sid [ccc,bbb,aaa].
    assert body.index("gen-bbb") < body.index("gen-aaa") < body.index("gen-ccc")
```
Arithmetic: PRE — no orchestrator section -> `body.index(...)` raises ValueError (substring absent) -> FAIL. POST — recency sort yields [bbb,aaa,ccc] -> PASS. Ascending-sid bug -> [aaa,bbb,ccc] -> `index(bbb) < index(aaa)` FALSE -> FAIL. Descending-sid bug -> [ccc,bbb,aaa] -> `index(aaa) < index(ccc)` FALSE -> FAIL. (Distinguishes the intended message-recency ordering from BOTH directory-name sort directions.) The fixture sids conform to `is_valid_session_id` (`[A-Za-z0-9._-]+`, `comms_session_registry.py:53`) so they are accepted, not skipped.

**Test 3c (degrades to EMPTY on absent `comms/orchestrator/`, distinguishes the rendered empty-state + never-500).**
```python
def test_orchestrator_bus_empty_state_when_absent(client, comms):
    # no comms/orchestrator/ at all
    r = client.get("/panes/bus")
    assert r.status_code == 200
    assert "(no orchestrator generations)" in r.text
```
Arithmetic: PRE — no orchestrator section -> the empty-state marker is absent (and a bare "200 with no orchestrator section" would PASS pre, which is why the assertion targets the rendered MARKER) -> FAIL. POST — the section renders its empty state, status 200 -> PASS. (Proves both the dedicated section exists AND the never-500 absent path.)

**Test 3d (defensive — malformed structures SKIP, valid content still renders, never 500).**
```python
def test_orchestrator_bus_degrades_on_malformed(client, comms):
    base = comms / "orchestrator"
    base.mkdir(parents=True, exist_ok=True)
    (base / "stray-file.md").write_text("not a generation dir\n", encoding="utf-8")  # a FILE child
    (base / "bad name").mkdir()              # invalid session_id (space) -> skipped
    _seed_orch_msg(comms, "gen-ok", "20260620T010000Z-charc-a.md", subject="good-msg")
    # also a malformed MESSAGE (no frontmatter) in the good gen
    (base / "gen-ok" / "inbox" / "20260620T020000Z-rd-broken.md").write_text(
        "no frontmatter at all\n", encoding="utf-8")
    r = client.get("/panes/bus")
    assert r.status_code == 200          # never a 500
    assert "good-msg" in r.text          # the valid gen still renders
    assert "broken" in r.text            # malformed message -> filename fallback
```
Arithmetic: PRE — no orchestrator section -> `good-msg` never renders -> FAIL. POST — the stray file + bad-named dir are skipped (`child.is_dir()` / `is_valid_session_id`), the valid gen renders, the malformed message uses the filename fallback, status 200 -> PASS. (Proves the defensive-never-raises skip + graceful degrade.)

**Test 3e (L3 read-only lock — the orchestrator bus has NO ack/write affordance; passes post, regression net).**
```python
def test_orchestrator_bus_has_no_ack_affordance(client, comms):
    _seed_orch_msg(comms, "gen-x", "20260620T010000Z-charc-a.md", subject="x")
    body = client.get("/panes/bus").text
    assert "/ack" not in body            # L3: never acks any orchestrator gen
    assert "hx-post" not in body         # no write control in the bus pane

def test_viewing_orchestrator_bus_never_mutates(client, comms):
    _seed_orch_msg(comms, "gen-x", "20260620T010000Z-charc-a.md", subject="x")
    before = sorted((comms / "orchestrator").rglob("*.md"))
    client.get("/panes/bus"); client.get("/panes/bus")
    after = sorted((comms / "orchestrator").rglob("*.md"))
    assert before == after               # read-only: no move/delete/create
```
(The existing `test_bus_pane_has_no_ack_affordance` already guards the director bus; 3e extends the guarantee to the orchestrator section. L3/L1/L4: the bus only READS per-gen inboxes; it never acks or writes.)

**Implementation 3:** `_load_registry()` (comms_ui-local, returns module-or-None) + `_orchestrator_inbox_messages` (§1.3) + the `_bus_ctx()` key + the `_BUS_PANE` section.

**Commit 3:** `feat(scripts): Task 3 -- read-only per-generation orchestrator bus in the comms UI`.

---

## 3. Full fast suite + Codex review

After Tasks 1-3 commit and BEFORE the Codex loop (recipe §2 fix-to-green-first):
- From the worktree cwd: `python -m pytest -m "not slow" -q`. Fix any cross-cutting failure to green (the bus-no-ack existing test, the directors-strip/launch existing tests, the `_load`-import path). Record the tail count off the final head.
- Then run the WSL-Codex review per recipe §3 — **review-strong** (this is production-adjacent harness code: the launch surface + the bus) + **codex-auto-review** (repo-access, matched-high effort). Iterate to `NO_NEW_CRITICAL_MAJOR`; persist every round verbatim + adjudication to gitignored `.copowers-findings.md`. (This writing-plans dispatch's OWN review is review-FAST over the plan; the above review-strong is the EXECUTING implementer's gate.)

---

## 4. Locks — designed-to + on-disk verification points

- **L5 (launch = ONE enum-validated fixed argv; nothing user-typed reaches the cmdline).** `comms_ui.py:746` `if role not in LAUNCH_ROLES: return 400` runs BEFORE argv (`:753-754`); adding `orchestrator` to `LAUNCH_ROLES` + the launcher `[ValidateSet]` keeps it intact. No user-typed value is introduced into the launch path. Asserted by Tests 2b (exact argv) + 2c (arbitrary role rejected).
- **L1 (compose never offers `decision_request`; server-stamps `from=operator`).** UNTOUCHED — no compose change. The existing `test_compose_*` stay green.
- **L3 (ack ONLY `operator/inbox`; read-only on every other role's files).** The orchestrator bus aggregation only READS per-gen inboxes; it never acks/writes/deletes. Asserted by Tests 3e (no ack/write affordance + files unmutated by GET).
- **L4 (all mail writes via `role_mail`).** UNTOUCHED — Arc B adds no write path.
- **`$env:SWING_ROLE`-set-inside-the-spawned-shell pattern (`start_directors.ps1:191-201`).** The orchestrator launch reuses `Build-LaunchCommand`/`Start-RoleWindow` by being just another role (the three map/enum edits add no new launch code). NOT set in the launcher's own env. Asserted by Test 1b (`$env:SWING_ROLE='orchestrator'` printed in the inner command).
- **New-tab spawn mechanism (`wt -w 0 new-tab`, :223).** UNTOUCHED (the LOCK is already satisfied).
- **Optional-`[web]` import isolation.** The bus lives in `comms_ui.py`, never the comms core. Importing `comms_session_registry` into `comms_ui` is the ALLOWED direction (the forbidden direction is core->comms_ui); `comms_session_registry` is stdlib-only (contextlib/json/os/re/tempfile/datetime/pathlib — NO fastapi/web), so it introduces no `[web]` dependency into anything the core loads. The lazy `_load_registry()` returns None on import failure, so app construction never depends on it.
- **PowerShell 5.1 compatibility (no `&&`/ternary/null-coalescing).** The launcher edits are pure DATA (map/enum entries) — no new control flow. Safe by construction.
- **ASCII-only console output.** `$RoleTitles['orchestrator']='ORCHESTRATOR'` is ASCII; no non-ASCII added anywhere.
- **Serial role launch (the `.sessions.json` RMW is not concurrency-safe).** UNTOUCHED — the orchestrator launches through the same serial `foreach ($r in $roles)` path.

---

## 5. Operator §5.10 BROWSER witness (BINDING for the GUI; the executing orchestrator schedules it)

HTMX has browser-only failure surfaces TestClient cannot detect (memory `feedback_visual_gate_both_render_and_browser` + the CLAUDE.md HTMX gotchas). The operator drives a REAL browser:
1. Open the comms UI; the launch strip dropdown now offers `orchestrator`.
2. Select `orchestrator` + "Start fresh" -> a NEW Windows-Terminal tab opens with `SWING_ROLE=orchestrator` set (the tab runs claude on the orchestrator bootstrap). Confirm the inner shell set the role (the SessionStart hook fires).
3. Arc A registers `comms/sessions/<sid>.json` for the new generation -> the generation appears in the "Orchestrator bus (read-only)" section of the bus pane (post a test message to the launched gen and confirm it shows; confirm the 5s poll preserves an expanded `<details>`).
4. The existing "Copy orchestrator spin-up" button STILL copies the bootstrap text (affordance (b) unchanged).
5. **Witness the EMPTY/no-gen bus state too** (seeded-gate-masks-default, memory `feedback_seeded_gate_masks_default_state`): with no orchestrator generations on disk, the bus shows "(no orchestrator generations)" and never errors.
6. **Teardown:** TaskStop does NOT kill a detached `comms_ui`/launched session (memory `feedback_taskstop_does_not_kill_detached_server`) — find the PID (`Get-NetTCPConnection -LocalPort <port>`), `Stop-Process -Force`, and verify the port is free + no straggler launched orchestrator tab before claiming teardown.

The **merged-head no-false-green** full-suite re-run on `main` is the binding green (memory `feedback_no_false_green_claim`); the operator's browser witness is binding before merge.

---

## 6. Self-certification

- NO schema. NO `swing/` package touch (`scripts/start_directors.ps1` + `scripts/comms_ui.py` + `tests/scripts/` only). NO new dependency. NO comms-core change (read-only of the Arc-A registry/per-gen inboxes; role_mail/hooks/registry UNTOUCHED).
- The new-tab spawn + the `$env:SWING_ROLE`-inside-shell pattern UNCHANGED.
- L5 / L1 / L3 / L4 preserved; optional-`[web]` isolation preserved; PowerShell-5.1 + ASCII-only + serial-launch constraints preserved.

## 7. Out of scope (STOP-and-flag if a fix would cross)

- The GUI re-sync swing->harness-template scaffold (B-11 dark-theme / B-13 expanded-`<details>`) -> Arc C.
- ANY `comms/` core change (registry/hook/role_mail are Arc-A-DONE; Arc B only READS).
- Any `swing/` touch, schema, or dependency. Any coa-chess edit. Any change to the new-tab spawn mechanism.
- `New-SessionName`'s `director-` prefix (cosmetic; the deliberate V1 non-fix in §1.1 — do NOT change it under this arc).
- **`orchestrator-state.md` rollover pointer (Arc-A-deferred): NOT needed for Arc B.** The launch auto-registers via the SessionStart hook -> `comms/sessions/<sid>.json`; the bus reads per-gen inboxes from disk. Neither the launch nor the bus needs the rollover pointer. (Flagged confirmed-not-needed; if the executing implementer finds the launch genuinely needs it, STOP and flag — do NOT silently add.)
