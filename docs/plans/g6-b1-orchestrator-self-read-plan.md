# G6 B.1 — Orchestrator newest-live self-read (implementation plan)

**Status:** PLAN (writing-plans). No production code in this document — it
specifies the change, the tasks, and every test with its pre-fix/post-fix
distinguisher.
**Brief:** `docs/comms-orchestrator-self-read-b1-commissioning-brief.md` (CHARC,
2026-06-26). Closes G6 Finding 2 (the Arc-B §5.10 resume-drain gap).
**Scope (files):** `scripts/role_mail.py` + `scripts/start_directors.ps1` +
`tests/scripts/test_role_mail.py` + `tests/scripts/test_start_directors_orchestrator.py`.
**§3 verdict:** SUB-TRIPWIRE — a `role_mail` read-behavior change + a one-line
launcher string. NO schema / module / dependency / standing-process / `swing/`
carve-out. Stdlib-only read path.
**Base:** `main` (`75287909` at worktree creation). Re-grounded vs live source
2026-06-26 (the brief grounded at `d4c4f119`; only docs commits since — the
cited `role_mail.py` line anchors hold).

---

## 1. Problem (re-stated from the brief, grounded on disk)

A **resumed** orchestrator's `$ResumePrompt`
(`scripts/start_directors.ps1:113`) emits:

```
python scripts/role_mail.py read --role orchestrator --all
```

with **no `--session`**. Arc A deliberately requires `--session <sid>` for any
orchestrator read/ack:

- `role_mail.py:294-297` `_role_inbox_dir` — orchestrator + falsy sid →
  `MailError("reading an orchestrator inbox requires --session <session_id>")`.
- `role_mail.py:309-312` `_role_read_dir` — orchestrator + falsy sid →
  `MailError("an orchestrator ack requires --session <session_id>")`.

An orchestrator does not trivially know its own Claude `session_id` (the
registry key), so it cannot self-drain → the last link of the
director→orchestrator loop is broken.

**The send side already solved the symmetric problem.** A bare
`--to orchestrator` (no sid) resolves to the **newest-live** generation via the
registry, at `_inbox_for_target:272-285`:

```python
if role == "orchestrator":
    eff = sid
    if eff is None:
        entry = _registry().newest_live(root, now if now is not None else _now())
        if not entry:
            raise NoLiveOrchestratorError(...)        # clear, never a silent drop
        eff = entry.get("session_id")
    if not _registry().is_valid_session_id(eff):       # re-validate belt (:283)
        raise MailError("refusing unsafe session_id " + repr(eff))
    return _registry().per_generation_inbox(root, eff)
```

The fix mirrors this on the **read** side, with the added read-only hazard that
a read is TWO operations (list the inbox + ack each message) that MUST agree on
the same generation.

---

## 2. Design

### 2.1 The single-resolution helper (the load-bearing decision)

The read path currently threads the **raw** `sid = getattr(args, "session", None)`
into BOTH the inbox listing (`_list_inbox` → `_role_inbox_dir`) AND the ack
(`ack_message(..., session_id=sid)` → `_role_read_dir`). See `cmd_read`
(`:622-645`), `cmd_list` (`:590-611`), `cmd_peek` (`:648-663`).

If newest-live resolution were placed **inside** `_role_inbox_dir` and
`_role_read_dir` (so each resolves on `sid is None`), there would be **two**
resolution sites that could disagree, and the ack would re-resolve independently
of the read → it could archive the WRONG generation's mail (the exact hazard the
brief names). It would also add a second `newest_live` consumer in a path the
brief wants single-sourced.

**Decision: resolve the effective sid EXACTLY ONCE, at the `cmd_*` layer, in a
single new helper, and thread the resolved value through both the read and the
ack.** This is the structural answer to the read+ack asymmetry (the send side
resolves once because it has one call site per recipient; the read side has two,
so resolution must be hoisted above both).

New helper (added to `role_mail.py`, near `_role_inbox_dir`):

```python
def _effective_read_session(root, role, sid, now=None):
    """The session_id a read/list/peek op should use (resolve newest-live ONCE).

    - Singular role (charc/rd/operator): returns sid unchanged (the singular
      path ignores it) -> ZERO behavior change.
    - orchestrator WITH an explicit sid: returns it unchanged (a specific,
      possibly non-newest / pruned gen) -> ZERO behavior change (back-compat).
    - orchestrator with NO sid (the self-read): resolve the newest-live
      generation via the registry (single-source, mirroring the SEND side at
      _inbox_for_target). No live gen -> a CLEAR read-side error
      (NoLiveOrchestratorReadError), NOT the old "requires --session". The
      resolved sid is re-validated via is_valid_session_id BEFORE it is returned
      into any path (the same belt the send side uses).
    """
    if role != "orchestrator" or sid is not None:
        return sid
    entry = _registry().newest_live(root, now if now is not None else _now())
    if not entry:
        raise NoLiveOrchestratorReadError(
            "no live orchestrator generation to read. Address a specific "
            "generation with '--session <session_id>', or bring an orchestrator "
            "generation up first.")
    eff = entry.get("session_id")
    if not _registry().is_valid_session_id(eff):
        raise MailError("refusing unsafe session_id " + repr(eff))
    return eff
```

`cmd_read`, `cmd_list`, `cmd_peek` change ONLY their session line:

```python
# was: sid = getattr(args, "session", None)
sid = _effective_read_session(root, args.role, getattr(args, "session", None))
```

After this line, `sid` is a concrete validated string for the orchestrator
self-read (or unchanged for singular / explicit-sid). It is threaded EXACTLY as
today: `cmd_read` passes it to `_list_inbox(root, role, sid)` and to
`ack_message(root, role, name, session_id=sid)` — so the read and the ack use
the SAME resolved generation. Read+ack consistency is guaranteed by
construction (one resolution, two consumers of the same value).

The role-validity guard (`if args.role not in VALID_TO: raise MailError`) at the
top of each `cmd_*` runs **before** the resolution line, so an invalid `--role`
still errors with its existing message (no regression).

### 2.2 Why `_role_inbox_dir` / `_role_read_dir` / `ack_message` stay UNCHANGED

These keep their explicit-sid-or-error contract as a **low-level backstop**:

- For the orchestrator self-read, the `cmd_*` layer has already resolved a
  concrete sid, so these helpers never receive `None` on that path — the
  "requires --session" / "an orchestrator ack requires --session" raises become
  unreachable from the CLI no-session path.
- They remain a defense-in-depth guard for any DIRECT programmatic call
  (`ack_message(root, "orchestrator", name)` with no session). The comms GUI
  (`scripts/comms_ui.py`) only ever acks `"operator"` (singular) — it walks the
  orchestrator per-gen inboxes read-only via `_orchestrator_inbox_messages` and
  never acks orchestrator — so this backstop is preserved without touching the
  UI.
- Keeping resolution OUT of these helpers is what makes the resolution
  single-sited (guard #4): newest-live is consumed in exactly one new place on
  the read side (`_effective_read_session`), delegating to the registry —
  mirroring the one send-side consumer.

This is a deliberate design choice surfaced for CHARC review (see §7): the brief
calls these "the two 'requires --session' sites you are REVERSING"; the reversal
is implemented at the `cmd_*` layer (route around them with a single resolver)
rather than inside the two helpers (which would re-introduce the two-site /
cross-gen-ack hazard). Net behavior for the CLI is exactly the reversal the
brief specifies; the low-level contract stays as a backstop.

### 2.3 The read-side clear error

Add a new exception class, the twin of `NoLiveOrchestratorError`:

```python
class NoLiveOrchestratorReadError(MailError):
    """No live orchestrator generation to read a bare `--role orchestrator`.

    A CLEAR read-side error (never the old "requires --session"): the caller
    addresses a specific generation with `--session <session_id>` or brings one
    up.
    """
```

It is a `MailError` subclass, so `main()`'s existing
`except MailError` handler maps it to **rc 1** with ASCII-sanitized stderr — no
change to `main()`. It is a **sibling** of `NoLiveOrchestratorError` (both
`MailError`), with a read-appropriate message (no "Nothing was written", which
is meaningless for a read; says `--session` not `--to orchestrator:<sid>`).

### 2.4 The `--session` help text (the §2 documentation requirement)

`build_parser` currently emits (`:700-701`):

```python
session_help = ("orchestrator generation session_id "
                "(required for --role orchestrator)")
```

`(required for --role orchestrator)` is now **false** for read/list/peek. Update
to a role-neutral, newest-live-aware string, e.g.:

```python
session_help = ("orchestrator generation session_id; omit to target the "
                "newest-live generation (pass it for a specific/non-newest gen)")
```

The same `session_help` is shared by the `list`, `read`, and `peek`
subparsers, so one edit covers all three. (The `post` subcommand documents
orchestrator addressing separately via `--to` help — unchanged.)

### 2.5 The launcher wording (Task b)

`scripts/start_directors.ps1:113`:

```powershell
$ResumePrompt = 'Resuming your director session: re-read your charter section-of-record, run python scripts/role_mail.py read --role {0} --all to drain your inbox, then report current state and await the operator.'
```

Make the prompt **genuinely role-neutral** (the brief §1(b) binding requirement;
"Resuming your session" is its EXAMPLE, not the whole wart). Two director-framed
phrases must go, or the prompt is still wrong for a resumed orchestrator (Codex
R2 MAJOR — half-neutralizing leaves a director-only phrase that a first-clause-
only test would not catch):

1. `Resuming your director session` → `Resuming your session`.
2. `re-read your charter section-of-record` → `re-read your role's
   section-of-record` (directors have a charter section-of-record; the
   orchestrator has `docs/orchestrator-context.md` — "your role's
   section-of-record" is accurate AND role-neutral for both).

Resulting line:

```powershell
$ResumePrompt = 'Resuming your session: re-read your role''s section-of-record, run python scripts/role_mail.py read --role {0} --all to drain your inbox, then report current state and await the operator.'
```

The `read --role {0} --all` drain command is UNCHANGED — it now WORKS for
orchestrator via §2.1 (the `{0}` is `[string]::Format($ResumePrompt, $role)` at
`:289`). **PS-5.1 single-quote escaping:** an apostrophe inside a PowerShell
single-quoted string is doubled (`role''s`), so "role's" is written `role''s`.
*(If CHARC prefers to avoid the apostrophe entirely, use "your role section-of-
record" — no doubled-quote needed; surfaced in §7.)* No `&&`, ternary, or
null-coalescing; ASCII-only.

### 2.6 Locks / invariants (confirmed against the read path)

- **Comms taxonomy + L1 UNCHANGED.** The read path (`cmd_read`/`cmd_list`/
  `cmd_peek`, `_list_inbox`/`_list_read`, `ack_message`) touches no
  sender/recipient/type validation; the L1 governance gate lives entirely in
  the WRITE path (`post_message:450-455`). No read-path code added here goes
  near it. (Confirmed on disk: the only `decision_request`/L1 logic is in
  `post_message`.)
- **Single-source (guard #4).** Newest-live resolution is added in ONE new
  read-side site, calling `_registry().newest_live` — no re-implementation. The
  existing `test_role_mail_has_no_private_resolver_copy` (`def newest_live` not
  in role_mail; `STALE_SECONDS =` not in role_mail) stays green (the fix adds
  neither).
- **STDLIB-ONLY.** No new import — `_registry()` / `_now()` already exist; the
  new helper + exception use only what is in the module.
- **`__file__`-anchored comms root.** Unchanged (`_REPO_ROOT`, `_comms_root`).
- **ASCII discipline.** The new error message + help text are ASCII; the
  launcher edit is ASCII.

---

## 3. Task breakdown (TDD: each task is red → green → its own commits during
execution; the converged PLAN is committed once)

> Execution note (per recipe §2): the executing implementer writes the failing
> test first, sees it fail the RIGHT way, makes the minimal change, sees it
> pass, commits per logical change. This plan enumerates the order and the
> distinguisher for each test. The plan itself is committed ONCE at convergence.

### Task 1 — read-side newest-live resolution (the core)

1. Add `NoLiveOrchestratorReadError(MailError)` (§2.3).
2. Add `_effective_read_session(root, role, sid, now=None)` (§2.1).
3. Rewire `cmd_read`, `cmd_list`, `cmd_peek` to resolve the session once via the
   helper (§2.1) and thread the resolved value unchanged into the existing
   `_list_inbox` / `_list_read` / `ack_message` calls.
4. Update `session_help` (§2.4).

Tests (Task 1) — added to `tests/scripts/test_role_mail.py`, in the existing
"G6 Arc A" section; they reuse the existing `_seed_live_orch`, `_per_gen_inbox`,
`_per_gen_read`, `_FIXED` helpers:

- **T1a `test_orchestrator_read_no_session_resolves_newest_live_and_acks_that_gen`**
  Seed ONE live gen `g1` (`_seed_live_orch(comms, "g1", monkeypatch)`); post
  `orchestrator:g1` a message; `role_mail.main(["read","--role","orchestrator",
  "--all","--comms-root",...])` (NO `--session`).
  - **Assert:** rc 0; body printed; `_per_gen_inbox(comms,"g1")` is empty AND
    `_per_gen_read(comms,"g1")` has the 1 message (**read+ack consistency**: the
    `.md` moved `g1/inbox` → `g1/read`).
  - **Distinguishes:** pre-fix `read` with no session raises
    `MailError("reading an orchestrator inbox requires --session")` → rc 1,
    inbox NOT drained (file still in `g1/inbox`); post-fix rc 0 + drained-and-
    acked-in-`g1/read`.

- **T1b `test_orchestrator_read_no_session_no_live_gen_clear_error`**
  *(THE FLIP of the existing `test_orchestrator_read_without_session_errors`,
  line 773 — see Task 3.)* Empty registry (no live gen);
  `read --role orchestrator --all` (no session).
  - **Assert:** rc 1; stderr contains the new clear-error marker (case-insensitive
    `"no live orchestrator"`); stderr does **NOT** contain `"requires --session"`;
    no `.md` anywhere.
  - **Distinguishes:** pre-fix stderr is "reading an orchestrator inbox requires
    --session" → `"no live orchestrator" in err.lower()` FAILS and
    `"requires --session" not in err` FAILS; post-fix both PASS.

- **T1c `test_orchestrator_read_explicit_session_targets_specific_non_newest_gen`**
  **REGRESSION GUARD (passes on BOTH paths by design — NOT a fails-pre/passes-post
  distinguisher; per Codex R1 MINOR).** Its job is to prove the fix does NOT
  BREAK explicit-session back-compat, not to prove the B.1 change. Seed TWO live
  gens: `g1` (older `started_ts`) and `g2` (newer `started_ts`, the newest-live),
  each given a message; then `read --role orchestrator --session g1 --all`.
  - **Assert:** rc 0; `g1` drained (`g1/inbox` empty, `g1/read` has 1); `g2`
    UNTOUCHED (`g2/inbox` still 1) — explicit `--session` is honored over
    newest-live.
  - **Guards against:** a fix that wrongly let newest-live OVERRIDE an explicit
    sid (`g2` would be drained, `g1` left). Pre-fix this path already worked via
    `_role_inbox_dir`; the guard ensures the fix keeps it working AND proves a
    NON-newest gen is reachable explicitly. (Explicit-session is unchanged by
    the fix, so this passes pre- and post-fix — that is the point of a guard.)
  - *Seeding note:* `_seed_live_orch` writes `started_ts` from `_FIXED`. To make
    `g2` strictly newer, the test seeds each gen then rewrites its
    `started_ts`/`last_seen` in the registry JSON directly (the same pattern
    `_seed_live_orch` already uses for `last_seen`) — `g1` an earlier
    `started_ts`, `g2` a later one, both within the staleness window of `_FIXED`.

- **T1d `test_orchestrator_list_no_session_resolves_newest_live_no_ack`**
  Seed `g1` live + one message; `role_mail.main(["list","--role",
  "orchestrator","--comms-root",...])` (no session).
  - **Assert:** rc 0; output reports `1 unread`; `_per_gen_inbox(comms,"g1")`
    STILL has the message (observational — no ack).
  - **Distinguishes:** pre-fix `list` with no session → rc 1 "requires
    --session", no listing; post-fix rc 0 + the count, inbox unchanged.

- **T1e `test_orchestrator_peek_no_session_resolves_newest_live_no_ack`**
  Seed `g1` live + one message; `peek --role orchestrator` (no session).
  - **Assert:** rc 0; body printed; `_per_gen_inbox(comms,"g1")` still 1 (peek
    never acks).
  - **Distinguishes:** pre-fix rc 1 "requires --session"; post-fix rc 0 + no ack.

- **T1f `test_orchestrator_read_no_session_multi_gen_drains_newest_only`**
  *(the §2 documented EDGE.)* Seed TWO live gens `g1` (older) + `g2` (newer),
  each with a message; `read --role orchestrator --all` (no session).
  - **Assert:** rc 0; `g2` (newest) drained (`g2/read` has 1, `g2/inbox` empty);
    `g1` UNTOUCHED (`g1/inbox` still 1). Pins the newest-live default + read+ack
    consistency on the resolved (newest) gen.
  - **Distinguishes:** a fix that read `g2` but acked a different gen, or read
    the wrong gen, fails this; same `started_ts` rewrite seeding as T1c.

- **T1g `test_session_help_is_newest_live_aware_not_required`**
  Build the parser (`role_mail.build_parser()`), locate the `--session` action
  on the `read` subparser, read its `help`.
  - **Assert:** help does NOT contain `"required"`; help contains
    `"newest-live"`.
  - **Distinguishes:** pre-fix help is "(required for --role orchestrator)" →
    `"required" not in help` FAILS; post-fix PASSES.
  - *Mechanism:* inspect via the parser's subparser actions (the
    `read`/`list`/`peek` subparsers each carry the shared `session_help`); a
    single subparser check suffices since the string is shared. (If subparser
    introspection is awkward, fall back to a source-text assertion on the
    `session_help = (...)` literal — kept ASCII, ≤100-char lines.)

### Task 2 — single-source / delegation backstop

No production change beyond Task 1 (this task is the structural pin).

Tests (Task 2) — `tests/scripts/test_role_mail.py`:

Three pins, each proving a DIFFERENT facet of single-source (Codex R2 MINOR
noted T2a alone does not prove the single-helper seam — so T2c is added to pin
exactly that, and T2a's claim is scoped to what it actually proves):

- **T2a `test_role_mail_read_delegates_resolution_to_registry`** — pins
  *registry-delegation* (NOT the single-helper seam; T2c does that). The
  read-path twin of the existing send-path
  `test_role_mail_delegates_resolution_to_registry` (`:782`). Monkeypatch
  `role_mail._registry` to a stub whose `newest_live` returns
  `{"session_id":"STUB"}`, `is_valid_session_id` returns True, and
  `per_generation_inbox` / `per_generation_read` return sentinel dirs under
  `comms`. Pre-place a `.md` in the sentinel inbox (raw write). Run
  `read --role orchestrator --all` (no session).
  - **Assert:** the message is read from AND acked into the STUB's sentinel
    dirs (proves the read path consumed the registry's `newest_live` +
    per-generation paths — it does NOT hand-roll resolution off the filesystem).
  - **Distinguishes:** a read path that hand-rolled resolution (ignoring the
    registry) would not route through the stub → the sentinel inbox untouched.

- **T2c `test_read_commands_route_through_effective_read_session`** — pins the
  *single resolve-once seam* (the structural decision in §2.1). Monkeypatch
  `role_mail._effective_read_session` with a spy that records its calls and
  returns the raw `sid` unchanged (so behavior is preserved). Invoke `cmd_read`,
  `cmd_list`, `cmd_peek` (each via `role_mail.main([...])` for a singular role so
  no live gen is needed).
  - **Assert:** the spy was called exactly once per command, with
    `(root, role, sid)` (the resolve-once-per-op contract).
  - **Distinguishes:** an implementation that inlined registry calls in each
    command (no single helper) would never call the spy → fails. This is the
    test that actually pins "resolve EXACTLY ONCE via one helper" (the read+ack
    consistency guarantee in §2.1 depends on it).

- **T2b (existing GUARD, must stay green) `test_role_mail_has_no_private_resolver_copy`
  (`:807`)** — re-run unchanged. Confirms `def newest_live` / `STALE_SECONDS =`
  remain ABSENT from role_mail after the fix (no second resolver added). The
  brief's "grep-clean: no second `newest_live` in role_mail" guard.

### Task 3 — FLIP the Arc-A "requires --session" test

The single test codifying the now-reversed contract is
`test_orchestrator_read_without_session_errors`
(`tests/scripts/test_role_mail.py:773-778`):

```python
def test_orchestrator_read_without_session_errors(comms, capsys):
    rc = role_mail.main(["read", "--role", "orchestrator", "--all",
                         "--comms-root", str(comms)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "session" in err.lower()
```

`"session" in err.lower()` is a WEAK assertion that would coincidentally still
pass against the new error (it mentions "session_id"). **FLIP it** so it pins the
NEW behavior and would FAIL the OLD one — this is exactly T1b. Implementation:
**rename/repurpose** this test to **T1b**
(`test_orchestrator_read_no_session_no_live_gen_clear_error`) asserting:
- rc 1;
- `"requires --session" not in err` (the OLD message is gone — FAILS pre-fix);
- `"no live orchestrator" in err.lower()` (the NEW clear error — FAILS pre-fix);
- no `.md` written.

> Verified by grep across `tests/` and `scripts/`: this is the ONLY test
> asserting the old read-side "requires --session" contract. The two helper-level
> messages (`role_mail.py:297` and `:312`) have no other direct test; they remain
> as backstops (§2.2) and are not exercised by the CLI no-session path post-fix.
> No other Arc-A test (the send-side `test_bare_orchestrator_*`, the explicit
> `test_orchestrator_read_list_peek_session_round_trip`, `test_ack_message_*`)
> asserts the reversed rule, so no other flip is needed.

### Task 4 — launcher wording

Edit `scripts/start_directors.ps1:113` per §2.5 — neutralize BOTH director-framed
phrases (`director session` AND `charter section-of-record`).

Tests (Task 4) — `tests/scripts/test_start_directors_orchestrator.py`
(static-content, always-runs, no PowerShell/claude needed):

- **T4a `test_resume_prompt_is_role_neutral`**
  Read `start_directors.ps1` text; locate the `$ResumePrompt =` line.
  - **Assert (FULL role-neutrality, not just the first clause — Codex R2 MAJOR):**
    the line does NOT contain `"director"` AND does NOT contain `"charter"` (both
    director-framed terms gone); it DOES contain `"Resuming your session"` AND
    `"section-of-record"` (the role-neutral replacement); it STILL contains
    `"read --role {0} --all"` (the drain command preserved with the `{0}`
    substitution).
  - **Distinguishes:** pre-fix the line is "Resuming your director session:
    re-read your charter section-of-record" → `"director" not in line` and
    `"charter" not in line` BOTH FAIL; post-fix BOTH PASS. The whole-line
    `"director"`/`"charter"` checks (not just `"director session"`) are what
    make this catch a HALF-neutralized edit. The `{0}`-drain assertion guards
    against an over-eager edit that drops the self-drain command.

> The existing `test_dryrun_orchestrator_sets_role_and_prints_command` and the
> Task-4 effort/session-name tests in this file are unaffected (the resume
> prompt is not exercised by the `-DryRun` fresh-start path they cover); re-run
> to confirm green.

---

## 4. Test ledger — summary

Two classes (per Codex R1 MINOR): **DISTINGUISHERS** fail pre-fix and pass
post-fix (they prove the B.1 change); **GUARDS** pass on BOTH paths by design
(they prove the fix does not BREAK existing behavior / re-implement a resolver).

**Distinguishers (fail pre-fix → pass post-fix):**

| # | Test | File | Pre-fix | Post-fix |
|---|------|------|---------|----------|
| T1a | read no-session → reads + acks newest gen | test_role_mail | rc 1 "requires --session", not drained | rc 0, `g1/inbox`→`g1/read` |
| T1b | read no-session, no live gen → clear error (FLIP of :773) | test_role_mail | err "requires --session" | rc 1, "no live orchestrator", NOT "requires --session" |
| T1d | list no-session → newest-live, no ack | test_role_mail | rc 1 "requires --session" | rc 0, count shown, inbox unchanged |
| T1e | peek no-session → newest-live, no ack | test_role_mail | rc 1 "requires --session" | rc 0, printed, inbox unchanged |
| T1f | read no-session, multi-gen → newest only | test_role_mail | rc 1 | rc 0, g2 drained, g1 untouched |
| T1g | `--session` help is newest-live-aware | test_role_mail | help says "required" | help says "newest-live", not "required" |
| T2a | read path delegates to registry (not a private resolver) | test_role_mail | sentinel untouched (no delegation) | read+ack via stub sentinel dirs |
| T2c | cmd_read/list/peek route through the single `_effective_read_session` seam | test_role_mail | spy never called (no single seam) | spy called once per cmd |
| T4a | resume prompt FULLY role-neutral (no "director", no "charter") | test_start_directors_orchestrator | "director"/"charter" present | "Resuming your session" + "section-of-record", drain preserved |

**Guards (pass on BOTH paths — regression / single-source pins):**

| # | Test | File | What it guards |
|---|------|------|----------------|
| T1c | explicit `--session g1` targets non-newest gen | test_role_mail | newest-live does NOT override an explicit `--session`; a non-newest gen stays reachable |
| T2b | no private resolver copy (existing) | test_role_mail | `def newest_live` / `STALE_SECONDS =` stay ABSENT from role_mail (no second resolver) |

All existing role_mail tests (send-side Arc-A, singular round-trips, L1,
atomicity, ASCII, ack back-compat `test_ack_message_three_arg_still_works`) stay
green — the change is additive on the orchestrator no-session read path and
inert for every other path.

---

## 5. Execution order & commits (during the execute phase, NOT this plan)

1. `feat(scripts): B.1 Task 1 — orchestrator newest-live self-read (read/list/peek no-session)` — helper + exception + cmd rewire + help text + T1a..T1g.
2. `test(scripts): B.1 Task 2 — read-path single-source pins (registry delegation + single-seam)` — T2a + T2c (T2b already present).
3. `refactor(scripts): B.1 Task 3 — flip the Arc-A requires-session read test to newest-live/clear-error` — repurpose `:773` into T1b. *(If T1b is authored directly in step 1, this becomes the rename/removal of the old test — keep it a distinct commit so the contract reversal is legible in history.)*
4. `feat(scripts): B.1 Task 4 — role-neutral resume prompt` — launcher edit + T4a.

(Commit grouping is the executing implementer's call within recipe §2; the
plan's contract is the task/test set, not the exact commit count.)

Then per recipe §2: run the FULL fast suite to green BEFORE the Codex review;
per §3 run review-strong + codex-auto-review to convergence; per §4 return to
the orchestrator.

---

## 6. Locks honored (to re-confirm on disk at execute + QA)

- **Comms taxonomy + L1 UNCHANGED** — read-path only; L1 lives in `post_message`
  (write path); no read-path code added here touches it (§2.6).
- **Single-source (guard #4)** — one new read-side `newest_live` consumer
  (`_effective_read_session`) delegating to the registry; no re-implementation;
  `test_role_mail_has_no_private_resolver_copy` stays green.
- **STDLIB-ONLY** — no new import; `_registry()`/`_now()` reused.
- **`__file__`-anchored comms root** — unchanged.
- **ASCII** — new error/help/launcher strings ASCII-only.
- **Explicit `--session` back-compat** — unchanged (T1c, T1f, the existing
  explicit-session round-trip test).
- **GUI unaffected** — `comms_ui.py` acks only `"operator"` and reads
  orchestrator inboxes read-only on disk; not touched.

---

## 7. Open questions / design decisions surfaced for CHARC (plan-stage review)

1. **Resolution location (§2.2).** The reversal is implemented at the `cmd_*`
   layer via the single `_effective_read_session` resolver, leaving
   `_role_inbox_dir` / `_role_read_dir` / `ack_message` as low-level
   explicit-sid-or-error backstops (UNCHANGED). This is what guarantees read+ack
   consistency (resolve once, two consumers) and keeps resolution single-sited.
   The brief calls those two helpers "the sites you are REVERSING" — confirm
   CHARC is content that the reversal is routed AROUND them (cmd layer) rather
   than placed inside them (which would re-introduce the two-site /
   cross-gen-ack hazard). *Recommend: keep as designed.*

2. **Read-side error name/shape (§2.3).** Proposing a NEW sibling class
   `NoLiveOrchestratorReadError(MailError)` (not reusing the send-side
   `NoLiveOrchestratorError`, whose "Nothing was written" message is wrong for a
   read), message: *"no live orchestrator generation to read. Address a specific
   generation with '--session <session_id>', or bring an orchestrator generation
   up first."* Confirm the name + message wording (it is operator-facing on the
   §5.10 witness).

3. **The Arc-A test being flipped (Task 3).** Exactly ONE:
   `test_orchestrator_read_without_session_errors`
   (`tests/scripts/test_role_mail.py:773`) → repurposed to T1b
   (no-live-gen clear error). Confirm CHARC concurs that is the full flip set
   (grep-verified: no other test asserts the old read-side contract; the two
   helper-level messages have no other direct test and remain as backstops).

4. **Launcher full role-neutralization (§2.5) — DECIDED in-plan after Codex R2.**
   The brief §1(b)'s binding requirement is "role-neutral"; "Resuming your
   session" is its example, not the whole wart. The same `$ResumePrompt` also
   said "re-read your **charter** section-of-record" (director-framed; the
   orchestrator reads `docs/orchestrator-context.md`, not a charter). A
   half-neutralized prompt is still wrong for a resumed orchestrator (Codex R2
   flagged it MAJOR — and a first-clause-only test would pass while the prompt
   stayed non-neutral). The plan therefore neutralizes BOTH phrases:
   `Resuming your session` + `re-read your role's section-of-record`, and T4a
   asserts neither "director" nor "charter" survives. **CHARC confirm:** (a) the
   replacement wording "your role's section-of-record" (accurate for directors'
   charter sections AND the orchestrator-context); and (b) the PS-5.1 apostrophe
   escaping `role''s` — or prefer the apostrophe-free "your role
   section-of-record" (no doubled quote). *Recommend: "your role's
   section-of-record" with `role''s`.*

5. **`orchestrator_bootstrap.md:39` follow-up (out of scope, FYI).** The
   bootstrap currently reads "Self-drain via role_mail is the next increment;
   until then the comms GUI bus." Post-B.1 the self-drain works; that note
   becomes stale. Not in this brief's file scope — surfaced for a possible CHARC
   doc follow-up, not changed here.
