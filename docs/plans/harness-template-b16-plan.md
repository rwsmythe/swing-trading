# Implementation Plan — Harness-Template B-16 (role identity lost on session RESUME)

**Target repo:** `C:\Users\rwsmy\harness-template` (the SCAFFOLD), branch `master`, base HEAD **`f0da3aa`** (the post-B-9+B-12 `master` head, verified on disk).
**This doc lives in:** `swing-trading/docs/plans/` (the swing CONTROL repo). It references coa-chess (the `coa`/`chess`/`course-of-action` terms are `FORBIDDEN_TERMS` in the scaffold's own genericity guard — `tests/genericity_lists.py:64-67`), so it MUST NOT live in the application-agnostic harness-template. This follows the established B-9/B-12 pattern (`swing-trading/docs/plans/harness-template-b9-b12-plan.md`). The WORK targets harness-template; the plan just lives in swing.
**Source brief:** `swing-trading/docs/harness-template-b16-commissioning-brief.md` (committed `84d06644`). Design is framed in brief §1; this plan SETTLES the exact mechanism and makes it executable + the distinguishing-test arithmetic airtight.
**Source recommendation (NOT a reference impl — design fresh):** coa-chess `docs/template-feedback-comms-hierarchy.md` §"role identity is lost on session RESUME". There is NO coa-chess reference implementation for B-16 (unlike B-9).
**Accept gate (NOT pytest):** `python -m unittest discover -s tests` from the harness-template root. Baseline verified **202 tests, OK** at `f0da3aa` on disk.

---

## 0. Executive summary + the settled mechanism

**The gap (verified on disk).** A session's role lives ONLY in the launch-time `HARNESS_ROLE` env var (`ROLE_ENV`, `session_start.py:73`), set by `launch_role.ps1`. Verified: `.claude/hooks/user_prompt_submit.py:153` — `role = env.get(ROLE_ENV, "")`. A RESUMED session that bypasses the launcher (`claude --resume <id>` by hand, or a crash-recovery resume) has `HARNESS_ROLE` UNSET → `role = ""` → silently: (a) the unread-notice never fires (`role` not in `COMMS_ROLES`, `user_prompt_submit.py:189`) — the director/operator stops being told about incoming mail; (b) for an orchestrator, the registry heartbeat + per-generation-inbox ensure are role-gated (`role == REGISTERED_ROLE`, `user_prompt_submit.py:157`) → a resumed orchestrator stops registering. coa-chess hit this: a resumed CHARC (never registered) silently missed an orchestrator message.

**Grounded asymmetry (why the registry alone is insufficient).** The registry (`comms/sessions/<session_id>.json`) records `role`, BUT registration is **orchestrator-only** (`REGISTERED_ROLE = "orchestrator"`; the deliberate "register only orchestrators" design — `session_start.py:68-69`). So a resumed ORCHESTRATOR's role is recoverable from the registry by `session_id`; a resumed CHARC's is NOT (CHARC is never registered). The fallback store MUST cover ALL roles, CHARC included.

**The settled fix (two complementary parts):**

**(a) A session-keyed, hook-written role-recovery store — SEPARATE from the orchestrator-only registry.** At the FIRST prompt of a session when `HARNESS_ROLE` IS set (the original launch), the hook writes a tiny `session_id -> role` record. On a resume (`HARNESS_ROLE` absent), the hook reads that record as the role fallback. The role resolution becomes `role = env.get(ROLE_ENV) or <session-keyed recovery>`. Because the recovery needs `session_id`, `handle_user_prompt_submit` is restructured to fetch `session_id` up front (for ALL roles) before the role gate.

**(b) Document the manual deliberate-resume command** `$env:HARNESS_ROLE='<role>'; claude --resume <id>` in `docs/charc-bootstrap.md` (a resume note) AND the `launch_role.ps1` `.NOTES` block. The fallback (a) is the safety net for a FORGOTTEN / crash resume; (b) is the simple DELIBERATE path.

### 0.1 The settled store mechanism (the load-bearing design choice)

CHARC's lean (brief §1) is adopted: **a thin hook-written `session_id -> role` store, one tiny file per session_id, written when `HARNESS_ROLE` is set, read as the fallback when it is absent.** Settled specifics:

- **Path:** `comms/roles/<session_id>` — a top-level sibling of `comms/sessions/`, `comms/orchestrator/`, `comms/charc/`. Each file contains exactly the role string (e.g. `charc`) plus a trailing newline. (Decision rationale + safety below.)
- **Format:** plain text — the bare role string + `"\n"` (NOT JSON). One file per session_id; the filename IS the session_id (the same identity invariant as the registry). A bare-string file is the minimum: no parsing, no malformed-JSON failure surface, trivially `read_text().strip()`.
- **Helpers (added to `session_start.py`, the shared registry-logic host — clearly labelled as a SEPARATE concern):** `write_session_role(root, session_id, role)` and `read_session_role(root, session_id) -> str | None`. Both reuse `is_valid_session_id` before any path build and `_atomic_write_text` for the write (same atomic same-dir-temp + `os.replace` pattern the registry uses). `read_session_role` returns `None` on a missing/unreadable file or an invalid recovered role string (never raises).
- **Write point + write contract (SETTLED — Codex R2):** in `handle_user_prompt_submit`, AFTER `session_id` is resolved and validated, the hook writes the record on EVERY prompt where `HARNESS_ROLE` IS set AND `session_id` is present/valid (an idempotent overwrite, best-effort, wrapped so a write failure never blocks the prompt). The brief's "FIRST prompt" framing is DESCRIPTIVE of when the record first becomes available (the launch carries the env role), NOT an exclusivity constraint — re-writing the same `session_id -> role` each prompt is a cheap idempotent overwrite and is strictly simpler than a write-once guard (no read-before-write, no first-prompt detection). **The env-set value WINS and REFRESHES the record** (the launch role is authoritative): a relaunch/override that sets `HARNESS_ROLE` updates the stored role to the live launch role, so a later resume recovers the CURRENT role, never a stale one. (This is exactly what `test_env_role_wins_over_a_stale_store_record` pins through the hook path — the env role both wins the resolution AND refreshes the record.) A resume (no `HARNESS_ROLE`) does NOT write — it only reads — so a resume cannot clobber the launch record with an empty/absent role.
- **Read point:** in `handle_user_prompt_submit`, when `env.get(ROLE_ENV)` is empty/absent (a resume), `role` falls back to `read_session_role(root, session_id)` (when `session_id` is present/valid).

**Why session-keyed covers CHARC (and a single `.harness-role` does NOT).** A single repo-level `.harness-role` file is ambiguous when CHARC + an orchestrator (or two orchestrators) run concurrently in ONE clone — a shared file cannot say which session is which role. The store is keyed by Claude Code's `session_id` (the same key the registry uses), so EVERY role — including CHARC, which the registry never records — has its OWN recoverable record. Two roles in one clone resolve to their OWN roles (the no-concurrency-ambiguity requirement → session-keyed, proven by the Task-4 test).

**Why the launcher cannot pre-write it.** The launcher (`launch_role.ps1`) knows the session NAME (`charc-20260622-1430`), not Claude Code's runtime `session_id` (which the substrate mints and delivers in the hook payload). Only the HOOK has BOTH `session_id` (from `payload`) AND `role` (from `HARNESS_ROLE` at original launch) — so the hook owns the write. (This is exactly why the registry, too, is hook-written: `session_start.py:22-25`.)

**Why it stays SEPARATE from the orchestrator-only registry (the binding §2 constraint).**
- A DISTINCT path tree (`comms/roles/`, not `comms/sessions/`). The registry's readers iterate `comms/sessions/*.json` ONLY (`read_entries`/`prune_stale`/`live_entries`/`newest_live` — `session_start.py:189,259`), so the role store is invisible to every registry consumer. (Verified: `Path(sessions).glob("*.json")` does not pick up files outside `sessions/`, and the role store is a different directory entirely.)
- DISTINCT helpers (`write_session_role`/`read_session_role`) — they do NOT call `write_entry`/`touch_last_seen`/`ensure_per_generation_inbox` and never write a `comms/sessions/<id>.json` file. The registry block (`user_prompt_submit.py:155-185`) is run UNCHANGED, still role-gated on `REGISTERED_ROLE`. Role-recovery does NOT register CHARC for liveness — CHARC gets a recovery record only, never a `sessions/<id>.json` entry, never a per-generation inbox.
- DISTINCT lifecycle: the role store is written for ALL roles (recovery is role-agnostic); the registry is written for orchestrators only (liveness). They never read or write each other's files.

**Safety / collision verification (on disk, at `f0da3aa`):**
- `comms/roles/` is gitignored by the existing `comms/*` + `!comms/.gitkeep` rule (`.gitignore`) — runtime coordination state, never tracked, auto-creates at first use.
- The directory name `roles` cannot be confused with a role inbox: `_inbox_for_role` builds `root / role / "inbox"` ONLY for `role in SINGULAR_INBOX_ROLES` (`charc`/`operator`) or the registered orchestrator (`user_prompt_submit.py:114-119`). `roles` is never a value of `role`, so `comms/roles/` is never read as `comms/<role>/inbox`.
- No existing `comms/roles` / `.harness-role` usage anywhere in the tree (grep-verified).

**V1 simplification (flagged):** the role store is NOT pruned (unlike the registry's staleness prune). Records are tiny (one short line each), gitignored, and read only by their own `session_id` on a resume — a stale record is harmless (its session never resumes, or resumes and correctly recovers). A V2 opportunistic prune (mirroring `prune_stale`, or tidied in `session_end.py`) is OUT OF SCOPE for B-16. No correctness depends on cleanup.

### 0.2 Genericity / contamination self-cert (stated up front; re-asserted per task)

The CORE files this arc touches (`.claude/hooks/user_prompt_submit.py`, `.claude/hooks/session_start.py`, `docs/charc-bootstrap.md`, `scripts/launch_role.ps1`) are CORE-scanned by the genericity guard (`tests/test_genericity_guard.py`). Every added string uses ONLY the `<role>` / `<id>` placeholders (NEVER a concrete role like `charc`/`rd` in the documented COMMAND, never a project term). `rd` is a `FORBIDDEN_ROLE_TERM` (`genericity_lists.py:90-92`); `chess`/`coa`/`swing`/etc. are `FORBIDDEN_TERMS`. No project term enters any CORE file. Re-run `test_genericity_guard` after EVERY CORE-doc/launcher edit. No new dependency (stdlib-only hooks). The orchestrator-only registry is UNCHANGED.

---

## 1. Sequencing + split judgment

**Already sequenced:** B-16 is dispatched only after B-9+B-12 merged to `master` (brief §0; verified — base is `f0da3aa`, B-12's single-sourced role handling is present at `user_prompt_submit.py:58-85`). This plan BUILDS ON B-12's single-sourced `SINGULAR_INBOX_ROLES` / `COMMS_ROLES` / `REGISTERED_ROLE` / `_registered_role` / `_REGISTRY_IMPORT_OK` (it does not re-derive them).

**Recommendation: BATCH (single executing pass), fixed internal task order.** Total surface: 2 hook files + 2 docs/launcher + ~5 new test methods (one new test file). The keystone risk is the `handle_user_prompt_submit` restructure (move `session_id` resolution before the role gate WITHOUT altering the registry semantics); that risk is contained by Task 2's tests (the existing registry tests must stay green) + Task 4's distinguishing tests, not by splitting. Task boundaries are split-clean (Tasks 1-4 = the fallback code+tests; Task 5 = the part-(b) docs) if the executing pass judges otherwise — flag to the orchestrator.

---

## 2. The ordered TDD tasks

Each task is red→green→commit. Run `python -m unittest discover -s tests` (or the named module for speed) to SEE red, then green. Ground every line anchor against live code at edit time (line numbers below are from `f0da3aa` and may drift). Test files in harness-template are NOT ruff-gated (the scaffold ships no `swing/`); match each test file's existing stdlib-`unittest` style (`from __future__ import annotations`, `unittest.TestCase`, `tempfile.mkdtemp()` roots, `redirect_stdout`/`redirect_stderr` for hook output).

> **The PRE-FIX BASELINE for every Task-3/Task-4 distinguishing test (Codex R3 — load-bearing for airtight arithmetic).** The task order is Task 1 (helpers) → Task 2 (the hook restructure) → Task 3/Task 4 (the hook-path tests). So when a Task-3/Task-4 test runs, **Task 1's helpers (`read_session_role`/`write_session_role`) ALREADY EXIST.** The pre-fix state these tests distinguish is therefore **"Task 1 landed, the hook restructure (Task 2) ABSENT"** — NOT "nothing exists." In that baseline the un-restructured `handle_user_prompt_submit` resolves `role = env.get(ROLE_ENV, "")` with NO recovery fallback and NO role-store write, so a resume resolves `role=""` (silent, no heartbeat) and a launch writes no record — i.e. the pre-fix RED is the PRODUCTION HOOK-PATH behavior (no notice / no heartbeat / no record), NOT an `AttributeError` from a missing symbol. **To make this airtight in practice, the executing implementer SHOULD see each Task-3/Task-4 test RED against the Task-1-landed-but-hook-un-restructured tree** (commit Task 1 first; write Task 3/4 tests; SEE them red on the un-restructured hook; then do Task 2). The bare `ss.read_session_role(...)`/`ss.write_session_role(...)` calls inside these tests are SEEDING/ASSERTION over EXISTING helpers in that baseline — never the source of the RED. (If the implementer instead writes a Task-4 test before Task 1, the RED would be a symbol-`AttributeError` — a worthless distinguisher; the fixed order prevents that.)

### Task 1 — the role-store helpers (`write_session_role` / `read_session_role`)

**File:** `.claude/hooks/session_start.py`. Add a NEW clearly-labelled section AFTER `ensure_per_generation_inbox` (live ~line 110) and BEFORE `_atomic_write_text` is used — actually place it AFTER `_atomic_write_text` (live ~line 138, so the helper is defined) and the registry read/write block, under a banner comment so it reads as a SEPARATE concern:

```python
# --- role-recovery store (SEPARATE from the orchestrator-only registry) -----
# A thin session_id -> role record so a RESUMED session (which bypasses the
# launcher, so HARNESS_ROLE is unset) can still recover its role. Written by the
# UserPromptSubmit hook at the FIRST prompt of a session when HARNESS_ROLE IS set
# (the original launch carries the role), read as the fallback when it is absent
# (a resume). DISTINCT from the registry (comms/sessions/<id>.json): the registry
# is liveness, orchestrator-only; this is role-recovery for EVERY role (CHARC
# included, which the registry never records). One tiny file per session_id under
# comms/roles/, the filename IS the session_id (the same path-safety contract as
# the registry -- every path build goes through is_valid_session_id). Plain text:
# the bare role string. Best-effort + degrade-gracefully: a missing/unreadable
# record, or an invalid recovered role string, returns None (never raises) so the
# hook keeps its never-block-a-prompt guarantee.

def _roles_dir(root: Path) -> Path:
    return root / "roles"


def _role_path(root: Path, session_id: str) -> Path:
    if not is_valid_session_id(session_id):
        raise ValueError(f"unsafe session_id {session_id!r}")
    return _roles_dir(root) / session_id


def write_session_role(root: Path, session_id: str, role: str) -> Path | None:
    """Record session_id -> role for resume-time recovery (best-effort).

    Returns the path written, or None if the inputs are unfit (no/invalid
    session_id, empty role). Never raises on a normal bad-input path; an OS write
    failure propagates to the caller's best-effort guard (the hook swallows it).
    """
    if not session_id or not is_valid_session_id(session_id) or not role:
        return None
    path = _role_path(root, session_id)
    _atomic_write_text(path, role + "\n")
    return path


def read_session_role(root: Path, session_id: str) -> str | None:
    """The recorded role for session_id, or None (missing/unreadable/invalid).

    Degrade-gracefully: a missing file, an OS error, an empty file, or a recorded
    string that is not a recognized comms role returns None -- so a resume with no
    (or a garbage) record falls through to the existing degraded behavior.
    """
    if not session_id or not is_valid_session_id(session_id):
        return None
    path = _role_path(root, session_id)
    if not path.is_file():
        return None
    try:
        recorded = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return recorded or None
```

> **Validity of the RECOVERED role (load-bearing).** `read_session_role` returns the recorded string as-is (after `strip()` + empty→None). The hook treats an UNRECOGNIZED role exactly as an absent role (it is not in `COMMS_ROLES`, so the notice is silent + the registry block is not entered) — so a garbage record degrades safely WITHOUT `read_session_role` needing to know the role set (which would couple this helper to `COMMS_ROLES`). The brief's "an invalid recovered role string is treated as absent" requirement is satisfied at the HOOK by the existing `role in COMMS_ROLES` / `role == REGISTERED_ROLE` gates — the recovered role flows through the SAME gates an env-set role does. (The executing implementer MAY additionally validate the recovered string against `COMMS_ROLES` inside the hook before using it; that is an equivalent, slightly stricter realization — flag the choice. The plan's baseline is: recover the string, let the existing gates judge it.)

**TDD:** the helpers are pure (root-taking), testable over a tmp tree exactly like the registry helpers. Create `tests/test_role_recovery.py` and add a `RoleStoreHelperTest`:

```python
"""B-16 -- the session_id -> role recovery store (write/read helpers + the
resume role-resolution fallback in the UserPromptSubmit hook). Stdlib unittest."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path

from _loader import load_session_start, load_user_prompt_submit

ss = load_session_start()
ups = load_user_prompt_submit()

T0 = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)


class RoleStoreHelperTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())

    def test_write_then_read_round_trips(self) -> None:
        p = ss.write_session_role(self.root, "sid-1", "charc")
        self.assertIsNotNone(p)
        self.assertEqual(ss.read_session_role(self.root, "sid-1"), "charc")
        # The store lives under comms/roles/, NOT comms/sessions/ (separate).
        self.assertTrue((self.root / "roles" / "sid-1").is_file())
        self.assertFalse((self.root / "sessions" / "sid-1.json").exists())

    def test_missing_record_reads_none(self) -> None:
        self.assertIsNone(ss.read_session_role(self.root, "absent"))

    def test_unsafe_session_id_never_builds_a_path(self) -> None:
        self.assertIsNone(ss.write_session_role(self.root, "../evil", "charc"))
        self.assertIsNone(ss.read_session_role(self.root, "../evil"))
        self.assertFalse((self.root.parent / "evil").exists())

    def test_empty_role_is_not_written(self) -> None:
        self.assertIsNone(ss.write_session_role(self.root, "sid-1", ""))
        self.assertIsNone(ss.read_session_role(self.root, "sid-1"))

    def test_garbage_record_strips_and_reads_back(self) -> None:
        # An empty/whitespace file reads as None; a non-role string reads back as
        # the string (the HOOK's COMMS_ROLES gate treats it as absent).
        (self.root / "roles").mkdir(parents=True)
        (self.root / "roles" / "sid-blank").write_text("  \n", encoding="utf-8")
        self.assertIsNone(ss.read_session_role(self.root, "sid-blank"))
        (self.root / "roles" / "sid-junk").write_text("nonsense\n",
                                                       encoding="utf-8")
        self.assertEqual(ss.read_session_role(self.root, "sid-junk"), "nonsense")
```

**Arithmetic (FAIL-pre / PASS-post):** PRE-task the symbols `write_session_role` / `read_session_role` do not exist on `session_start` → the test fails at the call (`AttributeError`) → RED. POST-task the helpers exist and behave as asserted → GREEN. `test_unsafe_session_id_never_builds_a_path` distinguishes a helper that forgot the `is_valid_session_id` guard (it would build a `comms/roles/../evil` path) from one that has it.

**Commit:** `feat(comms): B-16 — the session_id->role recovery store helpers`

**Contamination self-cert:** adds two stdlib helpers + a separate path under `comms/`; no project term; no dependency; the registry helpers are untouched.

---

### Task 2 — restructure `handle_user_prompt_submit`: resolve `session_id` up front (registry semantics UNCHANGED)

**File:** `.claude/hooks/user_prompt_submit.py`, `handle_user_prompt_submit` (live lines 146-192).

**The restructure (precise — Codex R1 Major 2 fix: minimize the moved behavior).** Today the function fetches `session_id` ONLY inside the `role == REGISTERED_ROLE` block (line 157). The fallback needs `session_id` for ALL roles (a resumed CHARC must read its record). The DESIGN CONSTRAINT (from Codex R1): hoisting `session_id` up front MUST NOT change the orchestrator-only registry's observable behavior, AND it must NOT silently introduce NEW observable behavior (a new stderr warning) for non-orchestrator roles. So the restructure splits cleanly into **a silent resolve-and-validate prelude** + **the orchestrator block keeping ALL its warnings exactly where they were**:

1. **Prelude (silent, all roles):** fetch `session_id = payload.get("session_id")`, fall back to `_degraded_session_id(env)` (tracking the `degraded` flag), and if the resolved id is present-but-UNSAFE, set `session_id = None` — but **emit NO warning here** (the unsafe-id and degraded WARNINGS stay in the orchestrator block, see step 3). The prelude is a pure, side-effect-free resolution so that BOTH consumers (the recovery read + the registry) get a SAFE id and the prior orchestrator-only warning surface is byte-preserved.
2. Resolve `role = env.get(ROLE_ENV, "")`; if empty, fall back to `read_session_role(root, session_id)` (when `session_id` is present/valid).
3. **The orchestrator registry block — UNCHANGED, including ALL its warnings.** It re-derives whether the id was unsafe/degraded for ITS OWN warning emission so the exact prior stderr output is preserved for the orchestrator path and ONLY the orchestrator path. (Realized below by keeping the warnings inside the `role == REGISTERED_ROLE` branch, keyed off the prelude's `degraded` flag + a recomputation of the unsafe case.)
4. Write the recovery record (best-effort) when `HARNESS_ROLE` IS set and `session_id` is present/valid.
5. Run the EXISTING unread-notice block UNCHANGED (`role in COMMS_ROLES`).

**Restructured function (the target shape):**

```python
def handle_user_prompt_submit(payload: dict, env: dict, root: Path,
                              now: datetime) -> None:
    """The UserPromptSubmit action (separated from main() for testability).

    Resolves the session_id UP FRONT (for ALL roles, so the role-recovery
    fallback can key on it), resolves the role (HARNESS_ROLE, or the session-keyed
    recovery store on a resume), records the role for a future resume, then runs
    the role-gated registry heartbeat (orchestrator only) + the unread notice
    (any comms role). ALWAYS best-effort; never blocks a prompt.
    """
    # 0. Resolve + validate the session_id ONCE, for ALL roles, SILENTLY (the
    #    recovery fallback below keys on it; the registry block reuses it). The
    #    unsafe-id / degraded-id WARNINGS are NOT emitted here -- they stay inside
    #    the orchestrator block (step 3) so the prior orchestrator-only stderr
    #    surface is byte-preserved and a CHARC/operator prompt gains NO new
    #    warning (Codex R1 Major 2: no new observable behavior for non-orch roles).
    raw_session_id = payload.get("session_id")
    session_id = raw_session_id
    degraded = False
    if not session_id:
        session_id = _degraded_session_id(env)
        degraded = bool(session_id)
    unsafe = bool(session_id) and not is_valid_session_id(session_id)
    if unsafe:
        session_id = None  # never let an unsafe id reach a path build (any role)

    # 1. Resolve the role: the launch-time env var, OR the session-keyed recovery
    #    store on a resume (HARNESS_ROLE absent). An unrecognized recovered string
    #    flows through the same COMMS_ROLES / REGISTERED_ROLE gates below, so a
    #    garbage record is treated as absent (never a crash).
    role = env.get(ROLE_ENV, "")
    if not role and session_id and _REGISTRY_IMPORT_OK:
        recovered = read_session_role(root, session_id)
        if recovered:
            role = recovered

    # 2. Record role -> session for a FUTURE resume (best-effort), only at the
    #    ORIGINAL launch (HARNESS_ROLE set) with a usable session_id. A write
    #    failure must never block a prompt.
    if env.get(ROLE_ENV) and session_id and _REGISTRY_IMPORT_OK:
        try:
            write_session_role(root, session_id, env[ROLE_ENV])
        except OSError:
            pass

    # 3. Heartbeat + register + per-generation inbox (orchestrator only) -- the
    #    EXISTING block, byte-preserving its warnings (now keyed off the prelude's
    #    `unsafe`/`degraded`/`raw_session_id` so the orchestrator-only stderr is
    #    EXACTLY what it was pre-B-16). No warning is emitted for any other role.
    if role == REGISTERED_ROLE:
        if unsafe:
            print(
                "[registry] WARNING UserPromptSubmit: refusing unsafe "
                f"session_id {raw_session_id!r}; not registering.",
                file=sys.stderr)
        if session_id:
            if degraded:
                print(
                    "[registry] WARNING UserPromptSubmit: hook payload had no "
                    f"session_id; DEGRADED to the fallback id {session_id!r} "
                    "(single-orchestrator assumption).", file=sys.stderr)
            touch_last_seen(root, session_id, now, role=role,
                            transcript_path=payload.get("transcript_path", ""))
            ensure_per_generation_inbox(root, session_id)
        else:
            print(
                "[registry] WARNING UserPromptSubmit: no session_id in the hook "
                "payload and no fallback id; this orchestrator generation is "
                "not registered (single-orchestrator assumption applies until "
                "session_id is available).", file=sys.stderr)

    # 4. Unread notice (any comms role; orchestrator uses its per-generation
    #    inbox -- so it needs the session_id resolved above).
    if role in COMMS_ROLES:
        notice = unread_notice(role, root, session_id)
        if notice:
            print(notice)
```

> **Why this byte-preserves the orchestrator path (the keystone, vs the rejected over-broad hoist).** The prelude resolves+validates SILENTLY; ALL three orchestrator warnings (unsafe-id refusal, degraded-id, no-id) stay INSIDE `if role == REGISTERED_ROLE`, keyed off the prelude's `unsafe`/`degraded`/`raw_session_id`/`session_id`. So for `HARNESS_ROLE=orchestrator`: the exact prior stderr is reproduced AND the registry side-effects (`touch_last_seen`, `ensure_per_generation_inbox`) are unchanged — the ONLY addition is the role-store write (step 2). For a NON-orchestrator role (charc/operator/unknown): NO warning is emitted (the prelude is silent; the orchestrator block is not entered) — so a CHARC/operator prompt with an unsafe/degraded id gains ZERO new observable behavior vs pre-B-16 (it previously never entered the orchestrator block either). This is the Codex R1 Major 2 fix: the moved logic is the SILENT resolution only; every observable warning is byte-identical AND scoped exactly as before.
>
> **Note on the unsafe-id refusal message text:** the existing `test_refuses_unsafe_session_id_no_path_escape` seeds `HARNESS_ROLE=orchestrator` + a `"../../evil"` id and asserts `"unsafe session_id"` in stderr + no escaped path. POST-restructure that orchestrator path STILL prints the refusal (step 3, `if unsafe`) with the SAME text and STILL writes nothing — GREEN. (The message now interpolates `raw_session_id` — the pre-validation id — which is the SAME value the prior code printed via its `session_id!r` before nulling it; verify the `{...!r}` repr matches.)

> **The explicit registry-unchanged regression obligation (Codex R1 Major 2 — proven, not asserted).** Beyond "the existing tests stay green," the executing implementer MUST ADD a `RegistryUnchangedTest` to `tests/test_role_recovery.py` (or extend `test_user_prompt_submit_hook.py`) that pins the orchestrator-path stderr + side-effects across EACH preexisting edge case, AND a paired assertion that the SAME edge case under a NON-orchestrator role emits NO warning (the new-behavior characterization). This is the regression net Codex flagged as missing — it proves the hoist did not move observable behavior:
>
> ```python
> class RegistryUnchangedTest(unittest.TestCase):
>     """Codex R1 Major 2: the session_id hoist must NOT change the
>     orchestrator-only registry's observable behavior, NOR emit a new warning
>     for a non-orchestrator role. Pins both sides for each edge case."""
>
>     def setUp(self) -> None:
>         self.root = Path(tempfile.mkdtemp())
>
>     def _run(self, payload, env):
>         err = io.StringIO()
>         with redirect_stderr(err):
>             ups.handle_user_prompt_submit(payload, env, self.root, T0)
>         return err.getvalue()
>
>     def test_orch_unsafe_id_still_refuses_and_writes_nothing(self) -> None:
>         err = self._run({"session_id": "../../evil"},
>                         {"HARNESS_ROLE": "orchestrator"})
>         self.assertIn("unsafe session_id", err)
>         self.assertFalse((self.root / "sessions").exists()
>                          and list((self.root / "sessions").glob("*.json")))
>         self.assertFalse((self.root.parent / "evil").exists())
>
>     def test_nonorch_unsafe_id_emits_no_warning(self) -> None:
>         # The hoist must NOT surface the orchestrator-registry warning to a
>         # charc/operator/unknown prompt (no new observable behavior).
>         err = self._run({"session_id": "../../evil"}, {"HARNESS_ROLE": "charc"})
>         self.assertEqual(err, "")
>         err2 = self._run({"session_id": "../../evil"}, {})  # resume, no role
>         self.assertEqual(err2, "")
>
>     def test_orch_no_session_id_still_warns_not_registered(self) -> None:
>         err = self._run({}, {"HARNESS_ROLE": "orchestrator"})
>         self.assertIn("not registered", err)
>
>     def test_orch_degraded_fallback_id_still_warns_and_registers(self) -> None:
>         err = self._run({}, {"HARNESS_ROLE": "orchestrator",
>                               "CLAUDE_CODE_SESSION_ID": "fallback-sid"})
>         self.assertIn("DEGRADED", err)
>         self.assertTrue((self.root / "sessions" / "fallback-sid.json").is_file())
>
>     def test_nonorch_degraded_fallback_id_emits_no_warning(self) -> None:
>         err = self._run({}, {"HARNESS_ROLE": "charc",
>                               "CLAUDE_CODE_SESSION_ID": "fallback-sid"})
>         self.assertEqual(err, "")
> ```
>
> **Arithmetic — what distinguishes vs what characterizes (Codex R2 precision).** Two CATEGORIES here, and the plan is explicit about which is which:
> - **REGRESSION-PINS (pass pre- and post-restructure by design; they RED a BROKEN restructure):** `test_orch_unsafe_id_still_refuses...`, `test_orch_no_session_id_still_warns...`, `test_orch_degraded_fallback_id_still_warns...` assert the SAME orchestrator stderr + side-effects across the restructure — they RED only a hoist that dropped/garbled an orchestrator warning or broke registration (the "subtle break in the degraded/unsafe/session-id path" Codex named). They are the registry-UNCHANGED net, NOT fix-distinguishers — and that is the POINT: the restructure's whole obligation is to NOT change this behavior.
> - **CHARACTERIZATIONS (pass on the pre-fix hook too):** `test_nonorch_unsafe_id_emits_no_warning` + `test_nonorch_degraded_fallback_id_emits_no_warning`. PRE-B-16 a non-orchestrator role never resolved `session_id`, so it never warned; POST-B-16 (this SILENT-prelude design) it STILL never warns → GREEN both sides. They are NOT distinguishers of the fix; they LOCK the silent-prelude design AGAINST the rejected over-broad noisy hoist (which would have printed the unsafe-id warning up front for ALL roles → these would RED that alternative). They are a guard against a future regression toward the noisy variant, not a red-pre/green-post witness.
>
> **Where Task 2's actual red→green signal comes from (Codex R2 — explicit):** the RESTRUCTURE itself has no in-isolation red-pre/green-post test (a pure refactor that adds the recovery fallback). Its red→green is driven by **Task 4's resume-recovery tests** (which FAIL pre-fix because the un-restructured hook resolves `role=""` on a resume → no notice/heartbeat, and PASS post-fix once the fallback resolves the role through the hook). That is by design and consistent with the plan's TDD note (Task 2 + Task 4 pair as one red→green cycle). The `RegistryUnchangedTest` regression-pins are the SAFETY net proving the refactor changed nothing observable on the orchestrator path; the distinguishing red signal is Task 4. The plan does NOT claim the `test_nonorch_*` characterizations are distinguishers.

> **Imports.** Add `read_session_role` and `write_session_role` to the guarded `from session_start import (...)` block (live lines 42-52), alongside the existing registry imports. They are covered by the SAME `_REGISTRY_IMPORT_OK` guard, so the steps that call them are gated on `_REGISTRY_IMPORT_OK` (steps 1+2 above) — if the sibling import failed, `main()` already degrades to a logged no-op (`user_prompt_submit.py:196-204`), so the calls are never reached anyway; the `_REGISTRY_IMPORT_OK` checks in steps 1+2 are belt-and-suspenders for a direct `handle_user_prompt_submit` call in a test after a simulated failed import (mirroring the existing `_inbox_for_role` `_REGISTRY_IMPORT_OK` guard, line 116).

**TDD (registry-unchanged is the red→green here):** there is no NEW failing test for Task 2 in isolation — its correctness is "the existing registry tests stay green AND the new fallback tests (Task 4) pass." The TDD discipline: write Task 4's fallback tests, SEE them fail against the un-restructured hook (RED), do this restructure, SEE Task 4's tests pass AND the existing `test_user_prompt_submit_hook.py` stay green (GREEN). To keep one red→green per logical change, the executing implementer may sequence Task 2 + Task 4 as a single red→green pair (write the fallback tests first, restructure, all green) — flag if folded.

**Arithmetic (registry-unchanged):** the six existing orchestrator/charc/degraded/unsafe/unknown tests assert the SAME outputs pre- and post-restructure (the registry side-effects are preserved verbatim + only the role-store write is added, which those tests do not assert on). A restructure that accidentally dropped the heartbeat / the per-generation inbox / a warning would RED one of them — they are the distinguishing net for "registry semantics unchanged."

**Commit:** `refactor(comms): B-16 — resolve session_id up front + role-recovery fallback in the prompt hook`

**Contamination self-cert:** no project term; no dependency; the registry block is byte-preserved (only the role-store write added); `<role>`-agnostic.

---

### Task 3 — the recovery WRITE precondition test (the launch records the role)

**File:** `tests/test_role_recovery.py`. Add `RecoveryWritePathTest`. This is the precondition the Task-4 recovery tests depend on: at the ORIGINAL launch (`HARNESS_ROLE` SET) the hook writes the store so a LATER resume can read it.

```python
class RecoveryWritePathTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())

    def test_charc_launch_records_role_for_resume(self) -> None:
        # HARNESS_ROLE set (the original launch) + a session_id -> the role store
        # is written, so a later HARNESS_ROLE-absent resume can recover it.
        ups.handle_user_prompt_submit(
            {"session_id": "sid-c", "transcript_path": "/t"},
            {"HARNESS_ROLE": "charc"}, self.root, T0)
        self.assertEqual(ss.read_session_role(self.root, "sid-c"), "charc")
        # CHARC is NOT registered for liveness (role-recovery is separate).
        self.assertFalse((self.root / "sessions" / "sid-c.json").exists())

    def test_orchestrator_launch_records_role_and_still_registers(self) -> None:
        # The orchestrator path is byte-preserved: it BOTH records the role AND
        # registers (registry unchanged) + gets its per-generation inbox.
        ups.handle_user_prompt_submit(
            {"session_id": "sid-o", "transcript_path": "/t"},
            {"HARNESS_ROLE": "orchestrator"}, self.root, T0)
        self.assertEqual(ss.read_session_role(self.root, "sid-o"),
                         "orchestrator")
        self.assertTrue((self.root / "sessions" / "sid-o.json").is_file())
        self.assertTrue(
            (self.root / "orchestrator" / "sid-o" / "inbox").is_dir())

    def test_no_session_id_does_not_write_a_record(self) -> None:
        # No session_id (and no fallback env id) -> nothing to key on -> no record.
        ups.handle_user_prompt_submit(
            {"transcript_path": "/t"}, {"HARNESS_ROLE": "charc"}, self.root, T0)
        self.assertFalse((self.root / "roles").exists()
                         and list((self.root / "roles").iterdir()))
```

**Arithmetic (FAIL-pre / PASS-post — against the Task-1-landed baseline, Codex R3).** The baseline is "Task 1 helpers present, hook un-restructured" (see the §2 baseline note). In that state `read_session_role` EXISTS and returns `None` because the un-restructured `handle_user_prompt_submit` NEVER WRITES a record (the role-store write is Task 2's addition) — so `assertEqual(ss.read_session_role(self.root, "sid-c"), "charc")` compares `None != "charc"` → FAILS → RED. The RED is the PRODUCTION-PATH absence of the write, NOT a missing symbol (the helper is present and correctly returns `None` for an absent record). POST-Task-2 the hook writes the record at launch → `read_session_role` returns `"charc"` → GREEN. `test_orchestrator_launch_records_role_and_still_registers` doubles as a registry-unchanged witness (it asserts the `sessions/<id>.json` + per-generation inbox STILL appear — they would vanish if the restructure broke the registry block). `test_no_session_id_does_not_write_a_record` distinguishes a write that forgot the `session_id` precondition (it would create a `comms/roles/`-junk path or crash). To SEE the RED honestly, write this test after committing Task 1 and run it on the un-restructured hook.

**Commit:** `test(comms): B-16 — the launch-time role-recording write path`

**Contamination self-cert:** test-only; no CORE change; no project term.

---

### Task 4 — the binding distinguishing tests: resume recovers the role (CHARC + orchestrator), safe degrade, no concurrency ambiguity

**File:** `tests/test_role_recovery.py`. Add `ResumeRecoveryTest`. These are brief §4's binding artifacts. Each FAILS pre-fix (no fallback → `role=""`) and PASSES post-fix.

```python
class ResumeRecoveryTest(unittest.TestCase):
    """B-16 binding artifact: a HARNESS_ROLE-absent resume recovers its role from
    the session-keyed store, so the unread notice fires + (orchestrator) the
    registry heartbeats. Each FAILS pre-fix (role='' -> silent) / PASSES post."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())

    def _seed_inbox(self, *parts: str) -> None:
        inbox = self.root.joinpath(*parts)
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / "20240601T120000Z-x.md").write_text(
            "---\ntype: fyi\n---\nbody", encoding="utf-8")

    def test_resumed_charc_recovers_role_and_notice_fires(self) -> None:
        # A resumed CHARC: HARNESS_ROLE ABSENT, but a recovery record exists.
        ss.write_session_role(self.root, "sid-c", "charc")
        self._seed_inbox("charc", "inbox")
        buf = io.StringIO()
        with redirect_stdout(buf):
            ups.handle_user_prompt_submit(
                {"session_id": "sid-c", "transcript_path": "/t"},
                {},  # NO HARNESS_ROLE -- the resume case
                self.root, T0)
        self.assertIn("[comms] 1 unread for charc", buf.getvalue())

    def test_resumed_charc_recovery_uses_the_store_not_the_registry(self) -> None:
        # CHARC is NEVER registered (registry is orchestrator-only), so the
        # registry alone cannot serve CHARC. Assert the FALLBACK (the store), not
        # the registry, covers it: no sessions/<id>.json exists, yet the notice
        # fires purely from the role record.
        ss.write_session_role(self.root, "sid-c", "charc")
        self._seed_inbox("charc", "inbox")
        self.assertFalse((self.root / "sessions" / "sid-c.json").exists())
        buf = io.StringIO()
        with redirect_stdout(buf):
            ups.handle_user_prompt_submit(
                {"session_id": "sid-c"}, {}, self.root, T0)
        self.assertIn("[comms] 1 unread for charc", buf.getvalue())
        # Still not registered after the resume (recovery != registration).
        self.assertFalse((self.root / "sessions" / "sid-c.json").exists())

    def test_resumed_orchestrator_recovers_role_and_heartbeats(self) -> None:
        # A resumed orchestrator: HARNESS_ROLE ABSENT, a recovery record exists.
        # The role resolves -> the registry heartbeats (the entry + inbox appear)
        # + the notice fires for its per-generation inbox.
        ss.write_session_role(self.root, "sid-o", "orchestrator")
        self._seed_inbox("orchestrator", "sid-o", "inbox")
        buf = io.StringIO()
        with redirect_stdout(buf):
            ups.handle_user_prompt_submit(
                {"session_id": "sid-o", "transcript_path": "/t"},
                {}, self.root, T0)
        self.assertTrue((self.root / "sessions" / "sid-o.json").is_file())
        self.assertIn("[comms] 1 unread for orchestrator", buf.getvalue())

    def test_safe_degrade_no_store_no_env_role_is_silent_no_crash(self) -> None:
        # No HARNESS_ROLE + no recovery record -> the existing degraded behavior:
        # role stays '' -> no notice, no registry entry, no crash. (The hook
        # returns None; main() would exit 0.)
        self._seed_inbox("charc", "inbox")  # a message exists but role is unknown
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = ups.handle_user_prompt_submit(
                {"session_id": "sid-x"}, {}, self.root, T0)
        self.assertIsNone(result)
        self.assertEqual(buf.getvalue(), "")  # no notice (role unresolved)
        self.assertFalse((self.root / "sessions" / "sid-x.json").exists())

    def test_no_concurrency_ambiguity_two_roles_one_clone(self) -> None:
        # Two roles in ONE clone (two session_ids). SEED each session's record
        # (a precondition, not the distinguisher), then DRIVE THE PRODUCTION HOOK
        # for EACH session_id and assert each resume resolves to ITS OWN role --
        # the session-keyed store disambiguates concurrent roles where a single
        # shared file could not. The distinguisher is the HOOK-PATH notice, not a
        # bare helper read (Codex R1 Major 1 fix).
        ss.write_session_role(self.root, "sid-c", "charc")          # seed
        ss.write_session_role(self.root, "sid-o", "orchestrator")   # seed
        self._seed_inbox("charc", "inbox")
        self._seed_inbox("orchestrator", "sid-o", "inbox")
        # Resume sid-c (no env role) through the hook -> charc notice ONLY.
        buf_c = io.StringIO()
        with redirect_stdout(buf_c):
            ups.handle_user_prompt_submit({"session_id": "sid-c"}, {},
                                          self.root, T0)
        self.assertIn("for charc", buf_c.getvalue())
        self.assertNotIn("for orchestrator", buf_c.getvalue())
        # Resume sid-o (no env role) through the hook -> orchestrator notice ONLY.
        buf_o = io.StringIO()
        with redirect_stdout(buf_o):
            ups.handle_user_prompt_submit({"session_id": "sid-o"}, {},
                                          self.root, T0)
        self.assertIn("for orchestrator", buf_o.getvalue())
        self.assertNotIn("for charc", buf_o.getvalue())

    def test_env_role_wins_over_a_stale_store_record(self) -> None:
        # A relaunched session whose stored record is STALE (a different role
        # under the same id). The LAUNCH env var must win (role = env OR
        # recovery), proven THROUGH THE HOOK PATH: the env=charc launch fires the
        # CHARC notice (NOT the orchestrator notice the stale record would imply)
        # -> the distinguisher is the hook-path role resolution, not a bare helper
        # call (Codex R1 Major 1 fix). A (wrong) recovery-OR-env precedence would
        # resolve role=orchestrator and fire the orchestrator notice -> RED.
        ss.write_session_role(self.root, "sid-c", "orchestrator")  # stale seed
        self._seed_inbox("charc", "inbox")
        self._seed_inbox("orchestrator", "sid-c", "inbox")  # would fire if wrong
        buf = io.StringIO()
        with redirect_stdout(buf):
            ups.handle_user_prompt_submit(
                {"session_id": "sid-c"}, {"HARNESS_ROLE": "charc"},
                self.root, T0)
        self.assertIn("for charc", buf.getvalue())
        self.assertNotIn("for orchestrator", buf.getvalue())  # stale did NOT win
        # The live launch also REFRESHES the record to the current role (a
        # hook-path side-effect: a later resume recovers charc, not the stale
        # orchestrator).
        self.assertEqual(ss.read_session_role(self.root, "sid-c"), "charc")
```

**Arithmetic (FAIL-pre / PASS-post), per test:**
- `test_resumed_charc_recovers_role_and_notice_fires` — PRE-fix `handle_user_prompt_submit` resolves `role = env.get(ROLE_ENV, "")` = `""` (env has no HARNESS_ROLE), there is no recovery fallback → `role` not in `COMMS_ROLES` → no notice → `buf` empty → `assertIn("[comms] 1 unread for charc", ...)` FAILS → RED. POST-fix `role` falls back to `read_session_role(...)` = `"charc"` → in `COMMS_ROLES` → notice fires → GREEN.
- `test_resumed_charc_recovery_uses_the_store_not_the_registry` — same FAIL-pre/PASS-post, PLUS it asserts the registry file is ABSENT on both sides, proving the fallback (not the registry) is what serves CHARC. PRE-fix: no notice → RED. POST: notice from the store, no registry entry → GREEN.
- `test_resumed_orchestrator_recovers_role_and_heartbeats` — PRE-fix `role=""` → the `role == REGISTERED_ROLE` gate is false → no `touch_last_seen` → no `sessions/sid-o.json` → `assertTrue(...is_file())` FAILS → RED. POST `role` recovers to `"orchestrator"` → the registry block runs → entry written + notice fires → GREEN. (Proves the recovery feeds the registry heartbeat, not just the notice.)
- `test_safe_degrade_no_store_no_env_role_is_silent_no_crash` — PRE AND POST: with no record + no env role, `role=""` → silent, no entry, returns None. This passes on BOTH paths by design (it asserts the UNCHANGED degraded behavior is preserved) — it is the safety witness, not a fix-distinguisher. It would RED only a regression that made the no-role path crash or spuriously fire/register.
- `test_no_concurrency_ambiguity_two_roles_one_clone` — the `write_session_role` calls are SEEDING (preconditions); the DISTINGUISHER is the two HOOK-PATH resumes. PRE-fix: a resume (no env role) resolves `role=""` (no fallback in the un-restructured hook) → no notice for EITHER session → `assertIn("for charc", buf_c)` FAILS → RED. POST-fix: each session_id resolves its OWN recovered role through the hook → `sid-c` fires the charc notice only, `sid-o` fires the orchestrator notice only → GREEN. Distinguishes a (rejected) single-shared-file design (which could not disambiguate two concurrent roles — both resumes would resolve the same last-written role and one of the `assertNotIn` would RED). Driven through `handle_user_prompt_submit`, so it cannot false-pass on the helper symbol alone.
- `test_env_role_wins_over_a_stale_store_record` — against the Task-1-landed baseline (`read_session_role` EXISTS), the DISTINGUISHING red signal is the HOOK-PATH RECORD-REFRESH side-effect, not the notice and not a missing symbol. PRE-fix (hook un-restructured): `role=env=charc` (the env path works pre-fix) → the charc notice fires + the orchestrator one does not (the notice assertions PASS pre-fix), BUT the un-restructured hook writes NO record, so the stale `orchestrator` record is never refreshed → `assertEqual(ss.read_session_role(self.root, "sid-c"), "charc")` compares `"orchestrator" != "charc"` → FAILS → RED (a real production-path difference: the launch did not refresh the stale record; `read_session_role` is present and correctly returns the stale value). POST-fix: the env role wins (`role = env OR recovery`, NOT `recovery OR env`) → charc notice only → AND the launch REFRESHES the record to `charc` → GREEN. The test ALSO guards precedence: a (wrong) `recovery OR env` impl would resolve `role=orchestrator` and fire the orchestrator notice (the seeded `comms/orchestrator/sid-c/inbox`) → `assertNotIn("for orchestrator", ...)` RED — so the hook-path notice is a SECONDARY distinguisher of the precedence direction. Both reds are production-path (refresh side-effect + precedence), neither is a symbol-`AttributeError`.

**Commit:** `test(comms): B-16 — resume role-recovery distinguishing tests (charc + orchestrator + degrade + concurrency)`

**Contamination self-cert:** test-only; uses generic `sid-c`/`sid-o`; the role values `charc`/`orchestrator` are the scaffold's two SHIPPED roles (allowed in tests — `test_user_prompt_submit_hook.py` uses them freely; tests are not genericity-scanned, and `charc`/`orchestrator` are not forbidden terms regardless).

---

### Task 5 — part (b): document the manual deliberate-resume command (bootstrap doc + launcher `.NOTES`)

**Goal:** add the manual deliberate-resume command `$env:HARNESS_ROLE='<role>'; claude --resume <id>` (the simple deliberate path; the fallback (a) is the forgotten/crash safety net) to TWO CORE files, using ONLY the `<role>` / `<id>` placeholders.

**File 1 — `docs/charc-bootstrap.md`.** Add a short "Resuming a session" note. The natural location is a new subsection after the 5-step checklist (after live line 111, before "## The orchestrator bring-up prompt") OR within step 5's vicinity. Proposed prose (placeholder-only, no concrete role):

```markdown
### Resuming a session (the role-on-resume note)

A session's role is set at launch via `HARNESS_ROLE` (the launcher does this).
A RESUMED session started by hand (`claude --resume <id>`) bypasses the launcher,
so `HARNESS_ROLE` is unset. The UserPromptSubmit hook RECOVERS the role from a
session-keyed record it wrote at the original launch, so the unread notice +
(for an orchestrator) the registry heartbeat keep working on a resume
automatically. To re-set the role EXPLICITLY (the deliberate path -- or if the
recovery record is unavailable), launch the resume with the env var set:

    $env:HARNESS_ROLE='<role>'; claude --resume <id>

(`<role>` is the session's role; `<id>` is the resume target. The automatic
recovery is the safety net for a forgotten/crash resume; this is the simple
deliberate path.)
```

**File 2 — `scripts/launch_role.ps1`, the `.NOTES` block** (live lines 41-52). Append a resume-command note INSIDE the comment-based-help `.NOTES` block (it is help text, not executed code), placeholder-only:

```
    RESUME: a session started by hand (claude --resume <id>) bypasses this
    launcher, so HARNESS_ROLE is unset; the UserPromptSubmit hook recovers the
    role from a session-keyed record written at the original launch. To re-set
    it explicitly (the deliberate path):
        $env:HARNESS_ROLE='<role>'; claude --resume <id>
```

> **Contamination check on both edits (load-bearing).** Both files are CORE-scanned. The added strings use ONLY `<role>` / `<id>` placeholders + `HARNESS_ROLE` (an allowed substrate var) + `claude --resume` (the substrate CLI). NO concrete role (`charc`/`rd`), NO project term (`swing`/`chess`/`coa`). `rd` is a forbidden role term and `chess`/`coa` are forbidden terms — verify none appears. Run `python -m unittest tests.test_genericity_guard tests.test_doc_acceptance tests.test_launch_role_content` after the edits and SEE green.

> **`.ps1` syntax-check (brief §3 caveat — binding).** `test_launch_role_content.py` GREPS `launch_role.ps1` but does NOT execute it, so a syntax error in the `.NOTES` edit would not be caught by the unittest suite. The executing implementer MUST run a PowerShell AST syntax-check after editing the launcher:
>
> ```powershell
> $errs = $null
> [System.Management.Automation.Language.Parser]::ParseFile(
>     "C:\Users\rwsmy\harness-template\scripts\launch_role.ps1",
>     [ref]$null, [ref]$errs) | Out-Null
> if ($errs) { $errs | ForEach-Object { Write-Host $_.Message }; exit 1 }
> else { Write-Host "launch_role.ps1: no parse errors"; exit 0 }
> ```
>
> Run it and confirm "no parse errors" BEFORE committing. (The `.NOTES` text is inside the `<# ... #>` comment-help block, so a content-only edit is low-risk — but the AST parse is the binding verification the brief mandates, since the grep test cannot see a syntax break.) Because the edit is help-comment-only, the existing `test_launch_role_content.py` assertions (HARNESS_ROLE present, the role set, the seam-4 markers, the spawn path, the preflight, hooks-own-the-registry) all stay green — re-confirm.

**TDD:** add two content assertions binding the convention.
- In `tests/test_launch_role_content.py`, `LaunchRoleContentTest` → `test_notes_document_resume_command`:
  ```python
  def test_notes_document_resume_command(self) -> None:
      # B-16 part (b): the .NOTES block documents the manual deliberate-resume
      # command (placeholder-only; no concrete role/project term).
      self.assertIn("--resume <id>", self.text)
      self.assertIn("$env:HARNESS_ROLE='<role>'", self.text)
  ```
- In `tests/test_doc_acceptance.py`, the bootstrap acceptance test class (grep the live file for the `BootstrapAcceptanceTest` / the class that reads `docs/charc-bootstrap.md`) → `test_documents_resume_role_command`:
  ```python
  def test_documents_resume_role_command(self) -> None:
      # B-16 part (b): the bootstrap doc carries the role-on-resume note +
      # the explicit re-set command (placeholder-only).
      self.assertIn("$env:HARNESS_ROLE='<role>'", self.text)
      self.assertIn("--resume <id>", self.text)
  ```

> **Grounding (verify at edit time):** confirm `tests/test_doc_acceptance.py` HAS a class reading `docs/charc-bootstrap.md` (the B-9/B-12 plan referenced a `BootstrapAcceptanceTest`). If the class name differs, attach the assertion to whichever class loads `self.text = _read("docs/charc-bootstrap.md")`. If no such class exists, add a minimal one mirroring the file's `_read` helper. FLAG if the helper/class shape differs from the assumption.

**Arithmetic (FAIL-pre / PASS-post):** PRE-task neither file contains `$env:HARNESS_ROLE='<role>'` + `--resume <id>` → the two assertions FAIL → RED. POST-task both carry the command verbatim → GREEN. The existing genericity + launcher-content + doc-acceptance tests stay GREEN (the added strings are placeholder-only) — distinguishing an edit that wrongly introduced a concrete role/term (which would RED `test_genericity_guard`).

**Commit:** `docs(comms): B-16 part (b) — document the manual resume-role command in the bootstrap doc + launcher .NOTES`

**Contamination self-cert:** placeholder-only (`<role>`/`<id>`); no concrete role; no project term; `launch_role.ps1` AST-parse-clean; the CORE docs stay generic.

---

## 3. Pre-review full-suite gate + the no-false-green run

After all task-commits land and BEFORE the Codex review (per recipe §2): run the FULL accept gate from the harness-template root:

```
python -m unittest discover -s tests
```

It must report **OK** at a count of **202 + the new tests** (Task 1: 5 helper-test methods; Task 2: 5 `RegistryUnchangedTest` methods; Task 3: 3 write-path methods; Task 4: 6 resume-recovery methods; Task 5: 2 content methods — ~21 new; exact count READ OFF THE FINAL HEAD, never carried forward). Binding facts: zero failures/errors; the existing `test_user_prompt_submit_hook.py` registry tests stay GREEN (the registry-unchanged net) AND the new `RegistryUnchangedTest` passes (the orchestrator-path-byte-preserved + non-orch-no-new-warning characterization); the genericity guard is green over the whole tracked tree (no CORE term added by any task — re-verify after every CORE-doc/launcher edit).

**No-false-green discipline:** the resume-recovery TEST IS the reality check (brief §5 WITNESS — a scaffold-internal change; the operator MAY optionally witness a real manual `claude --resume` without re-setting `HARNESS_ROLE` confirming the notice still fires, a strong-but-optional witness). Do not claim convergence without reading the actual `unittest` tail on the final state.

---

## 4. Codex review (executing phase: review-strong to convergence)

This is the WRITING-PLANS plan (reviewed at **review-fast** over the plan doc); the EXECUTING implementer runs **review-strong** to `NO_NEW_CRITICAL_MAJOR` over the harness-template DIFF, per recipe §3 and brief §5:
- Generate the diff on Windows from the harness-template worktree dir: `git diff f0da3aa..HEAD > .codex-diff.txt`. Tell Codex NOT to run git (`--skip-git-repo-check`); pipe the plan/diff via stdin; write output to a gitignored file (`.codex-*` — covered by harness-template `.gitignore`).
- Because the fix's correctness depends on UN-CHANGED surrounding code (the registry block, `_inbox_for_role`/`unread_notice`, `is_valid_session_id`/`_atomic_write_text`, `COMMS_ROLES`/`REGISTERED_ROLE`), give Codex repo read-access OR bundle the reference-graph files (`user_prompt_submit.py`, `session_start.py`, `role_mail.py`, `tests/test_user_prompt_submit_hook.py`) per recipe §3 "REPO ACCESS for PRODUCTION-CODE review" (the 18-H.4 lesson — the registry-semantics-unchanged claim is exactly the kind of un-changed-surrounding-code correctness a diff-only review is blind to).
- codex-auto-review alongside if the WSL path supports it on this repo (brief §5).
- Persist every round's verbatim response + per-finding adjudication to a gitignored `.copowers-findings.md`.

---

## 5. Acceptance criteria (the executing implementer's done-definition)

- All 5 tasks committed (Task 2 + Task 4 may be one red→green pair — flag if folded) with conventional commits, ZERO `Co-Authored-By`, no `--no-verify`, no amend, final `-m` paragraph plain prose. Trailer-clean: `git log f0da3aa..HEAD --format='%H%n%(trailers)'` all empty.
- `python -m unittest discover -s tests` → OK on the final state (202 + new).
- The brief-§4 distinguishing tests all FAIL-pre / PASS-post (proven by the arithmetic in each task):
  1. **resume recovers role + notice fires + (orchestrator) heartbeat** — Task 4 `test_resumed_charc_recovers_role_and_notice_fires` + `test_resumed_orchestrator_recovers_role_and_heartbeats`.
  2. **CHARC recovery specifically (the fallback, not the registry)** — Task 4 `test_resumed_charc_recovery_uses_the_store_not_the_registry`.
  3. **the WRITE path (launch records the role)** — Task 3 `test_charc_launch_records_role_for_resume`.
  4. **safe degrade** — Task 4 `test_safe_degrade_no_store_no_env_role_is_silent_no_crash` (+ `main()` exits 0 via the existing `test_internal_exception_exits_zero`).
  5. **no concurrency ambiguity** — Task 4 `test_no_concurrency_ambiguity_two_roles_one_clone`.
- The registry-unchanged net stays green: `test_user_prompt_submit_hook.py` all pass AND the new `RegistryUnchangedTest` passes — the orchestrator-path stderr + side-effects are byte-preserved for each preexisting edge case (unsafe-id / no-id / degraded-id), and a NON-orchestrator role emits NO new warning (the silent-prelude design, Codex R1 Major 2).
- The `.ps1` AST syntax-check reports no parse errors (Task 5).
- Codex review-strong converged (`NO_NEW_CRITICAL_MAJOR`); findings persisted.
- CHARC QA-on-disk: the fallback is session-keyed + covers CHARC + preserves the orchestrator-only registry (no `sessions/<id>.json` for CHARC; the registry block byte-preserved) + degrades safely + never blocks a prompt; NO project term / `rd` in any CORE file; no dependency added (stdlib-only hooks).

---

## 6. Self-cert (brief §3 / §5)

- **No new dependency:** the store helpers are pure stdlib (`pathlib`, the existing `_atomic_write_text`/`json`-free plain text). The hooks stay stdlib-only.
- **The orchestrator-only registry is UNCHANGED:** role-recovery is a SEPARATE store (`comms/roles/`, distinct helpers, distinct lifecycle); the `role == REGISTERED_ROLE` registry block is byte-preserved; CHARC is never registered for liveness (recovery != registration — proven by `test_resumed_charc_recovery_uses_the_store_not_the_registry`).
- **The hook never blocks a prompt:** the role-store read/write are best-effort (read returns None on any failure; write is wrapped in the never-block guard); `main()` still swallows all exceptions and exits 0; no path raises a `NameError` (the new calls are `_REGISTRY_IMPORT_OK`-gated, mirroring `_inbox_for_role`).
- **No project term / no `rd` in any CORE file:** the store PATH (`comms/roles/`), the helper code, and the documented COMMAND all use `<role>`/`<id>` placeholders or generic identifiers; verified by the genericity guard staying green over the whole tracked tree after every CORE edit.

---

## 7. Flagged for the orchestrator (verify-at-execution / ambiguities)

- **Recovered-role strictness (Task 1 note):** the plan's baseline recovers the role STRING and lets the existing `COMMS_ROLES`/`REGISTERED_ROLE` gates judge it (a garbage record → treated as absent). The executing implementer MAY additionally validate the recovered string against `COMMS_ROLES` inside the hook (slightly stricter, but couples the helper/hook to the role set). Either is acceptable; FLAG the choice in the return report.
- **Task 2 / Task 4 fold:** Task 2 (the restructure) has no isolated failing test — its red→green pairs with Task 4's fallback tests. The executing implementer may land them as one red→green cycle (write Task 4's tests → see red → restructure → green) — flag if folded; do NOT skip the registry-unchanged re-run.
- **`test_doc_acceptance.py` bootstrap class name (Task 5):** verify the live class that reads `docs/charc-bootstrap.md` before attaching the resume-command assertion; if the shape differs, attach to the loading class or add a minimal one — FLAG the deviation.
- **Store cleanup (V1 simplification):** the role store is NOT pruned in V1 (tiny, gitignored, harmless-if-stale). A V2 opportunistic prune (mirroring `prune_stale` or `session_end.py`) is out of scope — flag if the executing pass believes cleanup is needed.
- **Test count:** READ OFF THE FINAL HEAD; the ~16 estimate is guidance, not a target.
- **Split:** BATCHED is recommended (§1). Task boundaries are split-clean (Tasks 1-4 = fallback code+tests; Task 5 = part-(b) docs) if the executing pass judges otherwise — flag to the orchestrator, do not silently descope.
