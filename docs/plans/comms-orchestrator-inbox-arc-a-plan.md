# G6 Arc A — Orchestrator Per-Generation Inbox + Session Registry — Implementation Plan

**Arc:** Phase-18-close G6, Arc A of A→B+C (operator-sequenced 2026-06-25).
**Owner brief:** [`docs/comms-orchestrator-inbox-arc-a-commissioning-brief.md`](../comms-orchestrator-inbox-arc-a-commissioning-brief.md) (CHARC-owned, COMMISSIONED, commission commit `42c7386f`).
**Re-grounding:** [`docs/comms-orchestrator-inbox-reconciliation-notes.md`](../comms-orchestrator-inbox-reconciliation-notes.md) §"RE-GROUNDED 2026-06-25".
**Proven design SHAPE (sibling, adapt — NOT verbatim):** `C:\Users\rwsmy\coa-chess\docs\comms-orchestrator-inbox-reference.md` + coa-chess live `.claude/hooks/{session_start,user_prompt_submit}.py` + `scripts/role_mail.py`.
**Plan status:** WRITING-PLANS deliverable (plan-only). Executing implementer recommendation: `implementer-opus-high`. Review tier for executing: `review-strong` + codex-auto-review (production-adjacent harness code, repo-access).

---

## 0. Scope, self-cert, and the binding boundary

**IN (Arc A only):**
1. A single-sourced **registry module** `scripts/comms_session_registry.py` (stdlib-only): registry read/write/prune (`write_entry` / `read_entry` / `read_entries` / `touch_last_seen` / `prune_stale` / `live_entries` / `newest_live`) + the FULL registry-owned path API (`is_valid_session_id` / `entry_path` / `per_generation_inbox` / `per_generation_read` / `ensure_per_generation_inbox`) + `STALE_SECONDS = 45*60`, **clock-injected** (no baked `datetime.now()` in the pure resolvers). The registry is the SINGLE owner of the per-gen path shape `comms/orchestrator/<sid>/{inbox,read}` — role_mail delegates to it.
2. A lifecycle **hook** `scripts/comms_session_hook.py` (stdlib-only), two modes via `argv[1]`: `session-start` (register + idempotent per-gen inbox + opportunistic stale-prune) and `heartbeat` (refresh `last_seen`, **gate-free** — runs regardless of role). ALWAYS exits 0.
3. `.claude/settings.json` wiring: a new `SessionStart` entry + a new `UserPromptSubmit` heartbeat entry (both calling `comms_session_hook.py` with the mode arg), in the existing absolute-path `python "C:/.../scripts/..."` command form. The existing `UserPromptSubmit`→`comms_unread_hook.py` and `Stop`→`comms_stop_hook.py` entries stay UNCHANGED.
4. `scripts/role_mail.py` orchestrator addressing: widen `VALID_TO` with `orchestrator`; add `_split_target` (`:<sid>` parse, orchestrator-only suffix); the orchestrator branch in the inbox resolver; bare `--to orchestrator` → `newest_live` at send (CLEAR ERROR if no live gen); `--to orchestrator:<sid>` → direct, registry-INDEPENDENT delivery; `read|list|peek --role orchestrator --session <sid>`. role_mail consumes `newest_live` + `is_valid_session_id` from the registry module — NO re-implementation.
5. `session_id` path-safety validation at every write + consume site, with the `filename == embedded-id` anti-mis-route rule single-sourced in the registry module.

**OUT (do NOT build — Arc A only; STOP-and-flag if a fix would cross this):**
- Launcher generalization (`start_directors.ps1` → role-parameterized, the new-tab spawn lock), GUI `/orchestrator-bootstrap` button, the orchestrator bus aggregation → **Arc B**.
- The GUI re-sync swing→coa-chess/scaffold (B-11 dark-theme, B-13 expanded-`<details>`) → **Arc C**.
- ANY change to `comms_stop_hook.py` (the B-14 continue-once close-hook STAYS untouched).
- ANY change to `scripts/comms_ui.py` (the GUI — Arc B/C). It already imports `role_mail.post_message`/`ack_message`/`MailError`/`_ascii`; this plan preserves those signatures so the GUI keeps working with zero edits (verified §1.6).
- Any coa-chess edit. Any `swing/` package touch. Any schema/migration. Any new dependency.

**Self-cert:** NO schema; NO `swing/` package touch (comms files + `scripts/` + `.claude/settings.json` only); NO new dependency (stdlib-only); measurement-NEUTRAL; the comms taxonomy + the L1 lock UNCHANGED. The `orchestrator-state.md` rollover pointer is **DEFERRED** (optional in Arc A — see §6).

---

## 1. Verified-against-live-code grounding (the coa-chess-claim audit)

Every "coa-chess does X" claim from the reference, checked against swing's actual code on disk (`scripts/role_mail.py`, `scripts/comms_unread_hook.py`, `scripts/comms_stop_hook.py`, `scripts/comms_ui.py`, `.claude/settings.json`, `comms/`). Deltas drive the adaptation.

| Reference claim (coa-chess as-built) | Swing live reality | Adaptation |
|---|---|---|
| Roster: `charc`, `opsdir`, `operator` singular; `orchestrator` per-gen | swing: `charc`, `rd`, `operator` singular (`VALID_TO` = `("charc","rd","operator")`, `role_mail.py:43`); `orchestrator` REJECTED as recipient today | swing's 2nd director is `rd` (not `opsdir`); add `orchestrator` to `VALID_TO` |
| `VALID_FROM` carries orchestrator | swing already: `VALID_FROM = ("charc","rd","operator","orchestrator","pipeline")` (`:41`) — orchestrator + pipeline are SENDERS | no change to `VALID_FROM` |
| Hooks live in `.claude/hooks/` (`session_start.py`, `user_prompt_submit.py`, `session_end.py`) | swing hooks live in **`scripts/`** (`comms_unread_hook.py`, `comms_stop_hook.py`), wired via `.claude/settings.json`; NO `.claude/hooks/` dir | put the new hook in **`scripts/`** (CHARC §4 call); wire via `settings.json` |
| Registry single-sourced INSIDE `session_start.py` (the hook double-duties as the library) | n/a (no registry yet) | swing single-sources into a SEPARATE library `scripts/comms_session_registry.py` (cleaner: the hook + role_mail both import the library; no hook-as-library coupling) |
| Env var `HARNESS_ROLE` | swing uses **`SWING_ROLE`** (`comms_unread_hook.py:82`, `comms_stop_hook.py:77`) | registry/hook read `SWING_ROLE` |
| Registers `orchestrator` ONLY (`REGISTERED_ROLE`) | brief §4: register orchestrator + directors (future bus); `newest_live` orchestrator-specific | `REGISTRABLE_ROLES = ("charc","rd","orchestrator")`; only `orchestrator` gets a per-gen inbox + `newest_live` eligibility |
| `_unique_path` uses `secrets.token_hex(4)` (cross-process race belt) | swing `_unique_path` (`:165`) uses stamp+sender+slug + numeric-suffix existence loop, NO random token | KEEP swing's helper (brief lock §6 "reuse swing's existing helper, do not hand-roll"). The same-second cross-process clobber race is a PRE-EXISTING property of swing's role_mail, NOT introduced here, applies identically to the new per-gen inbox — OUT OF SCOPE (flag, do not change) |
| Atomic delivery: same-dir `mkstemp` + `os.replace` | swing already: `_write_temp` (`:91`) same-dir `mkstemp` + `os.replace` (`:321`) — the Windows cross-volume gotcha respected | reuse `_write_temp`/`os.replace`; the registry library uses a FAITHFUL LOCAL COPY of the same pattern (not a cross-import) to break a role_mail↔registry import cycle (§2.1) |
| L1: `decision_request` operator-only, in `post_message` | swing: L1 at `role_mail.py:283` (`if mtype == "decision_request" and any(r != "operator" ...)`), sender-agnostic; PLUS the `_AUTOMATED_EMITTER_TYPES` pipeline-status-only gate (`:267`, 18-H.7) | UNCHANGED. The L1 check fires on the PARSED role of each recipient BEFORE inbox resolution, so adding orchestrator as a recipient does not weaken it (§5 matrix) |
| comms_ui compose offers role recipients | swing `comms_ui.py` compose offers ONLY `charc`,`rd` (`:558-559`); acks ONLY `operator` (`:720,:731`); imports `post_message`/`ack_message`/`MailError`/`_ascii` | preserve those signatures (default `session_id=None`); GUI needs ZERO edits |

**Net:** the SHAPE ports cleanly. The material adaptations are (1) `rd` not `opsdir`, (2) hook in `scripts/` not `.claude/hooks/`, (3) registry in a SEPARATE library not the hook, (4) `SWING_ROLE` not `HARNESS_ROLE`, (5) register directors too (orchestrator-only for per-gen + newest_live), (6) keep swing's token-free `_unique_path`.

---

## 2. The design (the load-bearing shape)

### 2.1 `scripts/comms_session_registry.py` — the single-sourced registry library

Pure, stdlib-only, clock-injected. The ONE owner of the registry read/write/prune + resolution + the `session_id` safety rule. Imported by the hook and by role_mail; imports NOTHING from role_mail (one-way dependency — no cycle).

**Constants:**
- `STALE_SECONDS = 45 * 60` — single named tunable.
- `REGISTRABLE_ROLES = ("charc", "rd", "orchestrator")` — sessions whose `SWING_ROLE` is registered (brief §4).
- `NEWEST_LIVE_ROLE = "orchestrator"` — only orchestrator entries are `newest_live`-eligible (resolution is orchestrator-specific).
- `ROLE_ENV = "SWING_ROLE"`.
- `_SESSION_ID_RE = re.compile(r"[A-Za-z0-9._-]+")`.

**`session_id` safety (the single rule — guard #5, lesson §5.11):**
```
def is_valid_session_id(session_id) -> bool:
    # str, non-empty, not "." / "..", no "/" or "\\",
    # session_id == Path(session_id).name, and fullmatch _SESSION_ID_RE
```
This is THE rule, mirrored by every path-building + consuming site via import (the registry module, the hook, and role_mail all call `is_valid_session_id`). No second copy.

**Path helpers (each validates `session_id` before building a path):**
- `comms_root_from_file() -> Path` — `Path(__file__).resolve().parent.parent / "comms"` (the file lives in `scripts/`; repo root is one parent up; `__file__`-anchored, NOT cwd).
- `sessions_dir(root)` → `root / "sessions"`.
- `entry_path(root, sid)` → `sessions_dir(root) / f"{sid}.json"`; raises `ValueError` on an unsafe sid.
- `per_generation_inbox(root, sid)` → `root / "orchestrator" / sid / "inbox"`; raises on unsafe sid.
- `per_generation_read(root, sid)` → `root / "orchestrator" / sid / "read"`; raises on unsafe sid. (The registry is the SINGLE owner of the per-gen path shape; role_mail's read/ack/list/peek delegate to these — see §2.5, Codex R2 MAJOR.)
- `ensure_per_generation_inbox(root, sid)` → idempotently `mkdir(parents=True, exist_ok=True)` of `per_generation_inbox` and `per_generation_read`; returns the inbox dir.

**Atomic JSON write (a faithful local lift of role_mail's `_write_temp`+`os.replace` pattern — NOT a cross-import, to keep the registry zero-dep + break the role_mail↔registry cycle):**
- `_atomic_write_text(path, content)` — `path.parent.mkdir(parents=True, exist_ok=True)` (so `comms/sessions/` and any per-gen dir bootstrap on first write — fresh-tree safe; Codex R4 MAJOR) → `mkstemp(dir=path.parent)` → write utf-8 `newline="\n"` → `os.replace(tmp, path)`; cleanup the temp on any staging/replace failure. The parent-mkdir + same-dir temp mirror role_mail's `_write_temp` (`:97-98`) exactly; same-dir temp = same-filesystem `os.replace` (the Windows cross-volume gotcha respected). This is the SPIRIT of brief lock §6 ("do not hand-roll a cross-volume-unsafe variant") — same proven pattern, kept local to avoid the import cycle. **Flagged for review adjudication.**

**Registry read/write/prune (each takes an injectable `now: datetime` — the clock seam; NO `datetime.now()` inside any pure function):**
- `write_entry(root, sid, role, transcript_path, now, started_ts=None)` → writes `{session_id, role, transcript_path, started_ts, last_seen}` (started_ts preserved across refreshes if passed, else `now.isoformat()`); the FULL-entry write makes recreate-if-missing self-healing.
- `read_entry(root, sid) -> dict | None` — malformed/missing → None, never raises.
- `read_entries(root) -> list[dict]` — all well-formed entries; **a malformed file is SKIPPED** (degrade-gracefully); enforces the identity invariant: include an entry ONLY if `is_valid_session_id(data["session_id"])` AND `data["session_id"] == path.stem` (the **filename == embedded-id** anti-mis-route rule — guard #5). One bad file never corrupts the read (guard #3).
- `touch_last_seen(root, sid, now, *, role=None, transcript_path=None)` — refresh `last_seen` only (preserve started_ts + role); recreate-if-missing rebuilds the full entry from the supplied role (raises if role is None on a missing entry — the caller must pass role for self-heal).
- `_age_seconds(entry, now)` — parse `last_seen` (naive→UTC); unparseable → None.
- `prune_stale(root, now, stale_seconds=STALE_SECONDS) -> list[str]` — delete entries whose age > threshold OR whose `last_seen` is unparseable (cannot prove liveness); best-effort (an unremovable file is skipped); returns pruned ids.
- `live_entries(root, now, stale_seconds=STALE_SECONDS)` — non-stale entries with `role == NEWEST_LIVE_ROLE` (does NOT mutate).
- `newest_live(root, now, stale_seconds=STALE_SECONDS) -> dict | None` — the max-`started_ts` live orchestrator entry, or None. Sort key = `(started_ts_valid_flag, parsed_started_ts, session_id)`: a malformed `started_ts` is DEPRIORITIZED (`flag=0`, `parsed=datetime.min`) so a garbage string can't hijack "newest", AND the trailing `session_id` is a DETERMINISTIC final tiebreaker — so the all-malformed-`started_ts` case (and any exact `started_ts` tie) resolves to a single, stable entry (the lexically-greatest `session_id`), never a `max()`-order-dependent flake. This lexical-greatest-`session_id` tiebreak is a DELIBERATE tie policy pinned by the test oracle — do NOT change it without updating the `newest_live` tie test. **[Codex R1 + R5 MINOR]**

**Why one-file-per-session (guard #3):** `comms/sessions/<sid>.json` — each hook writes ONLY its own file, so concurrent generations never contend on a shared map; a partial/corrupt file degrades to "that one entry missing," not a corrupt global.

### 2.2 `scripts/comms_session_hook.py` — the lifecycle hook (two modes)

Stdlib-only; imports the registry library. `main(argv)` dispatches on `argv[1]`:
- `session-start` → `handle_session_start(payload, env, root, now)`
- `heartbeat` → `handle_heartbeat(payload, env, root, now)`
- unknown / missing mode → logged stderr warning, exit 0 (never block).

It reads the hook JSON payload from **stdin** defensively (`_read_payload()` → `{}` on any read/decode/parse failure, incl. pytest's no-stdin `DontReadFromInput`). It reads `SWING_ROLE` + `session_id` + `transcript_path`. ALWAYS exits 0 (a hook must NEVER block a session/prompt — `main()` swallows all exceptions to exit 0; the registry-import is guarded at module load too, mirroring coa-chess's `user_prompt_submit.py` resilience).

`session_id` source: PRIMARY = `payload["session_id"]`; degraded fallback = an env var — candidate `CLAUDE_SESSION_ID` (coa-chess used `CLAUDE_CODE_SESSION_ID`); **the executing implementer MUST verify the exact var name against the live SessionStart/UserPromptSubmit hook payload + env before relying on it** (Codex R5 MINOR — do not wire the fallback blind) — used with a logged stderr WARNING (never silently mis-key). If no session_id and no fallback → logged warning, no registration (the generation is unaddressable-by-sid until the substrate provides one), exit 0.

**`handle_session_start`:**
1. `prune_stale(root, now)` ALWAYS (reader-as-cleaner / new-session-on-entry — regardless of role).
2. If `SWING_ROLE not in REGISTRABLE_ROLES` → return (registration is role-gated).
3. Resolve + validate `session_id` (`is_valid_session_id`; unsafe → logged warning, return).
4. `write_entry(...)` (preserve started_ts on resume via `read_entry`).
5. If role == `orchestrator`: `ensure_per_generation_inbox(root, sid)`.

**`handle_heartbeat` (the SEAM — gate-free, see §2.4):**
1. If `SWING_ROLE not in REGISTRABLE_ROLES` → return (no role to register).
2. Resolve + validate `session_id`.
3. `touch_last_seen(root, sid, now, role=SWING_ROLE, transcript_path=...)` (recreate-if-missing self-heal).
4. If role == `orchestrator`: `ensure_per_generation_inbox(root, sid)` (so a pruned-then-resumed gen regains its box).

**No unread-notice in this hook.** The director unread notice stays in the UNTOUCHED `comms_unread_hook.py`. The orchestrator's own auto-unread-notice is DEFERRED (pairs with the Arc-B topology decision; the orchestrator's box is witnessed in Arc A via `role_mail peek/list --role orchestrator --session <sid>`). See §2.4 rationale.

### 2.3 `.claude/settings.json` — wiring

Add (preserving the existing entries verbatim):
- A new top-level `"SessionStart"` array with one command: `python "C:/Users/rwsmy/swing-trading/scripts/comms_session_hook.py" session-start`.
- A new object in the existing `"UserPromptSubmit"` array (alongside `comms_unread_hook.py`): `python "C:/Users/rwsmy/swing-trading/scripts/comms_session_hook.py" heartbeat`.

Match the existing absolute-path quoted command form (`.claude/settings.json:8`). The `Stop`→`comms_stop_hook.py` entry is UNTOUCHED.

### 2.4 The heartbeat SEAM — DECISION: option (b), a separate UserPromptSubmit hook command

The brief offers (a) refresh at the TOP of `comms_unread_hook.py` before its `{charc,rd}` gate, or (b) a separate `UserPromptSubmit` hook command. **Chosen: (b)** — a `heartbeat` mode of the new `comms_session_hook.py`, wired as a SECOND `UserPromptSubmit` entry. Justification:
1. **Gate-free by construction.** There is NO `{charc,rd}` gate in the new hook, so an orchestrator session's `last_seen` refreshes with no seam to thread — the binding constraint ("orchestrator's `last_seen` DOES refresh") is satisfied structurally, not by ordering code before a gate.
2. **Minimal blast radius on live B-14 machinery.** `comms_unread_hook.py` is imported by the freshly-enabled (`2026-06-21`), load-bearing `comms_stop_hook.py` (`from comms_unread_hook import DIRECTOR_ROLES, comms_root_default, unread_notice`). Leaving `comms_unread_hook.py` UNTOUCHED keeps those three symbols + the `{charc,rd}` continue-once contract pristine — zero regression risk to the close-hook.
3. **Separation of concerns.** Unread-notice (operator-prompt surfacing) vs registry-heartbeat (liveness) are independent; a heartbeat failure can never perturb the notice and vice versa. Each is independently testable.
4. **Correct Arc-A topology boundary.** The orchestrator is NOT in `DIRECTOR_ROLES`, so the UNTOUCHED `comms_stop_hook.py` does NOT continue-on-unread for an orchestrator — exactly right for Arc A (orchestrator-as-continuous-ops is part of the DEFERRED topology decision; the stop-hook is explicitly out of scope).

Rejected alternative (a): modifying `comms_unread_hook.py` would (i) perturb a B-14-coupled file, and (ii) only earn the orchestrator auto-unread-notice — which is itself deferred — so it buys nothing Arc A needs while adding regression surface. Cost of (b): two `UserPromptSubmit` hook processes per prompt (both fast, both exit 0) — acceptable.

**Env-identity scope (Codex R4 MINOR).** The heartbeat refreshes an orchestrator session's `last_seen` WHEN `SWING_ROLE=orchestrator` is present in that session's environment (exactly as directors carry `SWING_ROLE=charc`/`rd` today). HOW a live orchestrator session comes to CARRY `SWING_ROLE=orchestrator` (a launcher role-parameterization / GUI bootstrap that sets the env var) is the **Arc-B** launcher/bootstrap concern — DEFERRED, paired with the topology decision (orchestrator-as-bootstrapped-CC-session vs the VS-Code relay). Arc A's heartbeat is correct + tested with a synthetic `env={"SWING_ROLE": "orchestrator"}`; the §8 operator live-witness confirms the real session env actually carries it.

### 2.5 `scripts/role_mail.py` — the addressing surgery

**Role tuples (`:41`/`:43`):**
- `VALID_FROM` — UNCHANGED.
- `VALID_TO = ("charc", "rd", "operator", "orchestrator")` — adds orchestrator.
- NEW `SINGULAR_INBOX_ROLES = ("charc", "rd", "operator")` — the fixed-inbox roles.

**`_ensure_tree(root)` (`:122`) — retarget body** to iterate `SINGULAR_INBOX_ROLES` (was `VALID_TO`). Identical output today (`SINGULAR_INBOX_ROLES` == old `VALID_TO`), but it must NOT auto-create a singular `comms/orchestrator/inbox` once orchestrator joins `VALID_TO` (guard #2). The NAME stays `_ensure_tree` (referenced by `tests/scripts/test_role_mail.py:483,498` and `tests/scripts/test_comms_ui.py:399`).

**Lazy registry loader (single-source):**
```
def _registry():
    # import comms_session_registry (scripts/ on sys.path when run as a hook/CLI),
    # else importlib.util.spec_from_file_location from _REPO_ROOT/"scripts"/...
    # cache the module; raise MailError("registry module unavailable: ...") on failure.
```
Robust to BOTH the script-run path (scripts/ on sys.path) AND the test loader (`spec_from_file_location("role_mail", ...)`, scripts/ NOT on sys.path). role_mail CALLS `_registry().is_valid_session_id(...)` and `_registry().newest_live(...)` — it NEVER re-implements them (guard #4).

**`NoLiveOrchestratorError(MailError)`** — the typed CLEAR ERROR for bare `--to orchestrator` with no live generation.

**`_split_target(token) -> (role, sid_or_None)`:**
- No `:` → `(token, None)` if `token in VALID_TO` else `MailError("invalid recipient ...")`.
- With `:` → `role, sid = token.partition(":")`; only `orchestrator` may carry a suffix (else `MailError` naming the singular roles); empty sid → `MailError`; else `_registry().is_valid_session_id(sid)` must hold (else `MailError("refusing unsafe session_id ...")`), return `("orchestrator", sid)`.

**`_inbox_for_target(root, role, sid, now=None) -> Path`:**
- `role in SINGULAR_INBOX_ROLES` → `root/role/"inbox"` (role_mail owns the SINGULAR path shape only).
- `role == "orchestrator"`: if `sid is None` → `sid = newest_live_sid` (`_registry().newest_live(root, now or _now())["session_id"]`); on None → `raise NoLiveOrchestratorError(<clear message: address orchestrator:<sid> or bring a gen up>)`; re-validate the resolved sid (`is_valid_session_id`, belt — never trust a resolved value into a path). Return **`_registry().per_generation_inbox(root, sid)`** — DELEGATE the per-gen path shape to the registry (the single owner; Codex R2 MAJOR — do NOT rebuild `root/"orchestrator"/sid/"inbox"` inline).

**Per-gen inbox-dir bootstrap on the SEND path — single ownership (Codex R1 CRITICAL+MAJOR).** Resolving the target only computes the Path; it does NOT require the dir to exist. The directory `comms/orchestrator/<sid>/inbox` is CREATED by the EXISTING `_write_temp` (`role_mail.py:97`), which runs `final.parent.mkdir(parents=True, exist_ok=True)` before `mkstemp` — the SAME mechanism that bootstraps any singular inbox on first post today. So an explicit `--to orchestrator:<sid>` to a NEVER-registered or PRUNED generation delivers durably (registry-INDEPENDENT) with no extra mkdir step: `_unique_path` computes the name (no dir needed) → `_write_temp` mkdirs the per-gen inbox + stages the temp → `os.replace` commits. **Single owner of inbox-dir bootstrap:** `_write_temp`'s `mkdir(parents=True)` on the SEND path; `ensure_per_generation_inbox` on the REGISTER path (the hook). Both are idempotent and create the identical `comms/orchestrator/<sid>/inbox`. (The READ side — `_role_inbox_dir` + `_list_inbox` — already returns `[]` when the dir is absent, so reading a not-yet-written gen is an empty inbox, never an error.) This is load-bearing: do NOT remove the `_write_temp` mkdir nor assume the dir pre-exists.

**`post_message(...)` restructure** (preserve the validation ORDER + the all-or-nothing atomic delivery + rollback exactly as today):
1. sender ∈ `VALID_FROM` (else MailError).
2. mtype ∈ `VALID_TYPES` (else MailError).
3. `_AUTOMATED_EMITTER_TYPES` allowlist (`:267`, 18-H.7) — UNCHANGED.
4. CR/LF frontmatter-injection guard on subject/thread — UNCHANGED.
5. Parse recipients to `(role, sid)` pairs via `_split_target` (de-dupe pairs preserving order).
6. **L1 lock (`:283`) — UNCHANGED, fires on the PARSED role BEFORE any inbox resolution:** `if mtype == "decision_request" and any(role != "operator" for role, _ in pairs)` → MailError. (So `decision_request` to `orchestrator`/`orchestrator:<sid>` is refused here, regardless of liveness — §5 matrix.)
7. `_ensure_tree(root)` (singular roles).
8. Resolve each pair to its concrete inbox via `_inbox_for_target` (so a `NoLiveOrchestratorError` fires BEFORE any temp is staged → all-or-nothing); de-dupe by the RESOLVED inbox Path (so bare `orchestrator` + `orchestrator:<newest_sid>` collapse to one delivery); compute the effective sid for the frontmatter `to:` label (`orchestrator:<sid>` via a `_recipient_label`).
9. Stage same-dir temps via `_write_temp` → `os.replace` each → commit/rollback EXACTLY as the current code (`:296-347`).

**`_recipient_label(role, sid)`** → `f"orchestrator:{sid}"` for an orchestrator recipient with a resolved sid, else `role` (so the `to:` frontmatter records the concrete generation).

**`ack_message(root, role, filename, session_id=None)`** — add `session_id` (default None, back-compat for the GUI + cmd_read singular calls). orchestrator branch: require `session_id` (else MailError), validate it, source the inbox via `_registry().per_generation_inbox(root, sid)` and the dest via `_registry().per_generation_read(root, sid)`. **Preserve the existing `read_dir.mkdir(parents=True, exist_ok=True)` lazy bootstrap (`role_mail.py:370`)** so the per-gen `read/` dir is created at ack time even for a session that NEVER ran `session-start` (Codex R3 MAJOR — the send path bootstraps `inbox/` via `_write_temp`, the ack path bootstraps `read/`; together the explicit-`:<sid>` round-trip works with no `session-start`). Keep the bare-basename traversal guard (`:363`). Singular roles unchanged.

**`_role_inbox_dir(root, role, sid)` / `_role_read_dir(root, role, sid)`** — new helpers for list/read/peek/ack: singular → `root/role/{inbox,read}` (role_mail-owned); orchestrator → require + validate sid → **`_registry().per_generation_inbox(root, sid)` / `_registry().per_generation_read(root, sid)`** (DELEGATE to the registry's single-owner path helpers; Codex R2 MAJOR — no second copy of the per-gen path shape anywhere in role_mail).

**`cmd_list` / `cmd_read` / `cmd_peek`** — accept `--session`; for `role == "orchestrator"` with no `--session` → MailError ("reading an orchestrator inbox requires --session <session_id>"); otherwise ALL THREE resolve the inbox via the SAME `_role_inbox_dir(root, role, args.session)` (so `peek`/`list` enforce the identical session-id validation path as `read` — they are observational [no ack] but the resolution + safety check is identical; Codex R4 MINOR). **`cmd_read` MUST additionally thread the session through to the ack:** `ack_message(root, args.role, path.name, session_id=args.session)` (Codex R2 MAJOR — a literal 3-arg `ack_message(root, args.role, path.name)` would fail for EVERY orchestrator read even with `--session` present). Their `args.role in VALID_TO` check now admits orchestrator.

**Registry-import blast radius (Codex R2 MINOR — bounded).** `_registry()` is invoked ONLY on an orchestrator-path operation that genuinely needs the registry: bare `--to orchestrator` newest-live resolution, `:<sid>` session-id validation, and orchestrator `read`/`list`/`peek`/`ack` session-id validation + path delegation. A missing/broken registry module → a HARD `MailError` (fail-LOUD) on those paths ONLY. SINGULAR-role operations (charc/rd/operator post/list/read/peek/ack) NEVER call `_registry()` — so a broken/absent registry module can never break director or operator mail (the comms core stays available for the roles that don't need liveness).

**Parser** — add `--session` (default None) to `read`, `list`, `peek`; update the `--to` help to mention `orchestrator:<session_id>` (bare = newest-live). The `--from`/`--to`/`--type` help strings already join the tuples.

**Replace `test_orchestrator_cannot_receive`** (`test_role_mail.py:181`) — it asserts the OLD contract (`--to orchestrator` rejected). Arc A inverts it. Replace with the §5 matrix + §7 tests (it would otherwise pass post-change for the WRONG reason: bare `--to orchestrator` with no registry still rc==1, but as `NoLiveOrchestratorError`, not "no inbox"). The replacement asserts the NEW contract explicitly (bare → clear no-live-gen error; `:<sid>` → delivery; fyi → delivered, decision_request → L1-refused).

---

## 3. The clock-injection approach (debt D9 — freezable staleness)

The live-clock-test-brittleness debt (D9) is pre-empted: **no pure function calls `datetime.now()`**. Every registry function that compares time takes an injectable `now: datetime` parameter (`write_entry`, `read_entry` n/a, `touch_last_seen`, `prune_stale`, `live_entries`, `newest_live`, `_age_seconds`). `datetime.now(UTC)` is called ONLY in the hook `main()` entry points (and passed down). role_mail's `_inbox_for_target`/`_newest_live` resolution takes `now=None` defaulting to the existing `role_mail._now()` seam (`:77`, already monkeypatched by tests, e.g. `test_filename_collision_suffix`). Tests freeze `now` to a fixed `datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)` and assert exact staleness boundaries (e.g. `last_seen = now - timedelta(seconds=STALE_SECONDS + 1)` is stale; `- (STALE_SECONDS - 1)` is live) — no sleeps, no wall-clock flake.

---

## 4. The `session_id` path-safety sites (guard #5 — enumerated, one rule mirrored via import)

The single rule `comms_session_registry.is_valid_session_id` is enforced at EVERY site where `session_id` becomes a dir name OR a filename OR is consumed from a registry file:

| Site | File | Enforcement |
|---|---|---|
| `entry_path` (write the JSON) | registry | raises `ValueError` on unsafe sid |
| `per_generation_inbox` / `ensure_per_generation_inbox` | registry | raises on unsafe sid |
| `read_entries` identity invariant | registry | skip unless `is_valid_session_id(embedded)` AND `embedded == path.stem` (filename==embedded-id) |
| `handle_session_start` / `handle_heartbeat` | hook | validate the payload/env sid before any path build; unsafe → logged warning, no registration |
| `_split_target` (`--to orchestrator:<sid>`) | role_mail | `_registry().is_valid_session_id(sid)` → MailError on unsafe (fail-LOUD, never silently accept) |
| `_inbox_for_target` (newest-live resolved sid) | role_mail | re-validate the resolved sid (belt — never trust a resolved value into a path) |
| `_role_inbox_dir` / `_role_read_dir` / `ack_message` (`--session <sid>`) | role_mail | validate before building the read/ack path |

Discriminating cases (`../evil`, `/abs`, `""`, `a/b`, `..`, `.`, and a `*`-containing token) are rejected LOUDLY at write (ValueError) AND consume (MailError); a crafted `:<sid>` never writes a file outside `comms/orchestrator/<sid>/` (assert no `.md` lands outside the per-gen tree).

---

## 5. The type×recipient matrix (the 18-H.7 lesson, inverted to the recipient side)

Widening `VALID_TO` with `orchestrator` must NOT let a `decision_request` reach a non-operator. The L1 lock is recipient-based + sender-agnostic and fires on the PARSED role BEFORE inbox resolution. **Verified on disk:** L1 is `role_mail.py:283` (`if mtype == "decision_request" and any(r != "operator" ...)`); the automated-emitter gate is `:267`. Adding orchestrator to `VALID_TO` does NOT touch either gate. The full matrix (each a test):

| sender | recipient | type | expected | reason |
|---|---|---|---|---|
| charc | `orchestrator:<sid>` | `fyi`/`status`/`query`/`return_report` | DELIVERED to the per-gen inbox | role→role traffic allowed |
| charc | `orchestrator:<sid>` | `decision_request` | **REFUSED (L1)** | `decision_request` operator-only (orchestrator ≠ operator) |
| charc | `orchestrator` (bare, live gen) | `decision_request` | **REFUSED (L1)** | L1 fires on parsed role before newest-live resolution |
| charc | `operator` | `decision_request` | DELIVERED | unchanged — operator is the sole `decision_request` recipient |
| pipeline | `orchestrator:<sid>` | `status` | DELIVERED | automated-emitter allowlist permits `status` |
| pipeline | `orchestrator:<sid>` | `decision_request` | **REFUSED (automated-emitter gate, before L1)** | unchanged 18-H.7 guarantee |

The decision_request-to-orchestrator test asserts the error text contains **"L1"** (NOT "invalid recipient") — proving the lock HELD post-widening, mirroring the existing `test_l1_lock_unchanged_for_human_sender` / `test_pipeline_decision_request_to_rd_still_rejects` discrimination pattern.

---

## 6. Locks to preserve + the deferred state-pointer

- **Comms taxonomy + L1 UNCHANGED** — §5 matrix; L1 (`:283`) + automated-emitter gate (`:267`) untouched.
- **STDLIB-ONLY comms core** — the registry module + the hook import nothing outside stdlib. A dependency-posture test (Task 1) asserts it (AST-scan or `ast.walk` over imports; mirrors coa-chess `tests/test_dependency_posture.py`).
- **`__file__`-anchored comms root everywhere** — `comms_root_from_file()` (registry), `comms_root_default()` (existing unread hook, untouched); NEVER cwd.
- **Atomic delivery** — mail via the EXISTING `_write_temp`+`os.replace`+collision-suffix (`:91`/`:165`/`:321`); the registry's JSON write uses a same-dir-temp+`os.replace` LOCAL copy of that pattern (§2.1, flagged).
- **`comms_stop_hook.py` UNTOUCHED** — its three imported symbols (`DIRECTOR_ROLES`, `comms_root_default`, `unread_notice`) keep their exact signatures (default `session_id=None` is NOT added to `unread_notice` — that function is not modified at all under option (b)).
- **`comms_ui.py` UNTOUCHED** — `post_message`/`ack_message`/`MailError`/`_ascii` signatures preserved (back-compat default `session_id=None` on `ack_message`); the compose form (charc/rd only) + operator-only ack keep working.

**The rollover `orchestrator-state.md` pointer is DEFERRED (FLAG, not forced).** Brief §4/§5.6: it is OPTIONAL in Arc A — the explicit-`:sid` + newest-live pair IS the primary resilience. Swing already writes `orchestrator-handoff-*` docs; aligning them to a single `orchestrator-state.md` newest-live pointer is a documentation/process convention, not load-bearing for the addressing mechanism. Defer to a follow-up (or Arc B alongside the bus). Not built here.

---

## 7. Ordered TDD tasks (red → green → commit)

Each task: write the failing test, SEE it fail (for the right reason), minimal implementation, SEE it pass, commit (conventional message carrying the task id). Test files mirror `tests/scripts/`. All behavioral tests run over a `tmp_path` comms tree (never the real `comms/`). Match the existing test style in `tests/scripts/test_role_mail.py` (`importlib.util.spec_from_file_location` module load; `comms` fixture = `tmp_path / "comms"`; frozen `now` via `monkeypatch.setattr(mod, "_now", ...)` or an explicit `now=` arg).

### Task 1 — the registry library (`scripts/comms_session_registry.py`) + tests
New file `tests/scripts/test_comms_session_registry.py`. TDD sub-cycles:
1. `is_valid_session_id` — accepts `g1`, `2026-06-25T12.00.00`, `abc_DEF-1`; rejects `""`, `.`, `..`, `../evil`, `/abs`, `a/b`, `a\\b`, `a*b`, a non-str. **[guard #5]**
2. `entry_path`/`per_generation_inbox`/`ensure_per_generation_inbox` — build under `sessions/` and `orchestrator/<sid>/{inbox,read}`; raise `ValueError` on an unsafe sid; `ensure_*` is idempotent (twice → no error). **[guard #2, #5]**
3. `write_entry`/`read_entry` round-trip over frozen `now` AND over a FRESH tree (no pre-made `comms/sessions/` — assert the first `write_entry` bootstraps it, Codex R4 MAJOR); `read_entry` → None on missing + on malformed (write garbage bytes, assert None, no raise). **[guard #3]**
4. `read_entries` — two valid + one malformed file → returns exactly the two valid; an entry whose embedded `session_id != path.stem` is SKIPPED (filename==embedded-id). **[guard #3, #5]**
5. `touch_last_seen` — refresh moves `last_seen` to the new `now`, preserves `started_ts` + `role`; recreate-if-missing rebuilds from the supplied role; raises if role is None on a missing entry.
6. `prune_stale` — seed a stale entry (`last_seen = now - (STALE_SECONDS + 1)s`) + a live entry (`now - (STALE_SECONDS - 1)s`); prune deletes ONLY the stale file, returns its id; a malformed-`last_seen` entry is pruned (can't prove liveness). **[§7 stale-prune; clock frozen]**
7. `newest_live` — None when none live; with two live orchestrator entries returns the max-`started_ts` one; a `role=charc` entry is NEVER newest_live (orchestrator-specific); a malformed `started_ts` is deprioritized (a good entry wins over a garbage one). **[guard #1 substrate]**
8. **Dependency posture** — `ast`-scan the registry module's imports; assert every top-level import is stdlib (no third-party). **[lock: stdlib-only]**
9. **Atomic-write same-dir guard (Codex R1/R5 MINOR)** — assert the SAFETY PROPERTY, not the temp-name detail: (a) the file lands at `target`; (b) after a SUCCESSFUL write the ONLY artifact in the whole tmp tree is `target` (no stray leftover ANYWHERE — proves no cross-volume `gettempdir()` staging and a clean temp), checked by globbing the tree; (c) the staging dir is `target.parent` (observe via a wrapped/`monkeypatch`ed `mkstemp` asserting its `dir=` kwarg equals `target.parent`, NOT keyed on a `.tmp` suffix); (d) overwriting an existing target fully replaces the prior content (never torn). Fails if the impl regresses to a cross-volume-unsafe `gettempdir()` staging. **[lock: cross-volume-safe atomic write]**

Discriminating arithmetic: prune uses `STALE_SECONDS = 2700`; an entry at `now-2701s` is stale (pruned), at `now-2699s` is live (kept). A non-degrading reader (json.loads without try/except) would RAISE on the malformed file in sub-cycles 3/4 → red; the skip-on-malformed impl → green. **Commit:** `feat(comms): Task 1 -- single-sourced session registry library (stdlib, clock-injected)`.

### Task 2 — the lifecycle hook (`scripts/comms_session_hook.py`) + tests
New file `tests/scripts/test_comms_session_hook.py`. Exercise `handle_session_start` / `handle_heartbeat` directly over a tmp tree with a synthetic `payload` dict + `env` dict + frozen `now` (the pure-handler seam, like coa-chess). Sub-cycles:
1. `session-start`, role=orchestrator, payload sid=`g1` → registry entry written (role=orchestrator) + `comms/orchestrator/g1/{inbox,read}` created. **[guard #2]**
2. `session-start` ALWAYS prunes (seed a stale entry; assert it is gone after a session-start of a DIFFERENT new session, even role=charc). **[§7 stale-prune at SessionStart]**
3. `session-start`, role=charc, sid=`d1` → registry entry written (role=charc) BUT NO per-gen inbox created (directors are singular). **[brief §4 registration scope]**
4. **heartbeat refreshes an orchestrator's `last_seen` (the SEAM)** — `write_entry(...,now=t0)`; `handle_heartbeat(payload={"session_id":"g1"}, env={"SWING_ROLE":"orchestrator"}, root, now=t1>t0)` → entry `last_seen == t1.isoformat()`. Discriminating: the heartbeat has NO `{charc,rd}` gate, so an orchestrator (NOT a director) DOES refresh; a reintroduced gate would leave `last_seen == t0` → this test fails. (The synthetic `env` stands in for the live `SWING_ROLE=orchestrator` that the Arc-B launcher/bootstrap will provide — Codex R4 MINOR; the §8 witness confirms the real env.) **[brief §4 SEAM; §7]**
5. heartbeat recreate-if-missing — prune the entry, then `handle_heartbeat` rebuilds it in full (role from env, sid from payload). **[guard #1: registry-pruned != gone, the resume path]**
6. degraded/unsafe sid — payload sid `../evil` → logged stderr warning, NO registration, NO path escape (assert `comms/sessions/` has no `evil` file, no traversal). **[guard #5]**
7. resilience — `main(["session-start"])` and `main(["heartbeat"])` with NO stdin / a broken payload / an internal raise ALWAYS return 0 and never raise (a hook must never block). A subprocess no-op test (no `SWING_ROLE`) exits 0 with no registration (the seeded-gate-masks-default discipline — witness the quiet path).

**Commit:** `feat(comms): Task 2 -- session lifecycle hook (session-start register+prune, gate-free heartbeat)`.

### Task 3 — settings.json wiring + a wiring test
Edit `.claude/settings.json`: add the `SessionStart` entry + the second `UserPromptSubmit` (heartbeat) entry; preserve the existing `UserPromptSubmit`→unread + `Stop`→stop entries verbatim. Add `tests/scripts/test_comms_session_settings_wiring.py`: parse `.claude/settings.json`, assert (a) a `SessionStart` command references `comms_session_hook.py` with the `session-start` arg, (b) a `UserPromptSubmit` command references it with `heartbeat`, (c) the existing `comms_unread_hook.py` UserPromptSubmit + `comms_stop_hook.py` Stop entries are STILL present unchanged, (d) commands use the absolute quoted-path `python "C:/.../scripts/..."` form. **Commit:** `feat(comms): Task 3 -- wire SessionStart + UserPromptSubmit heartbeat in settings.json`.

### Task 4 — role_mail orchestrator addressing + tests
Edit `scripts/role_mail.py` per §2.5. Extend `tests/scripts/test_role_mail.py` (and REPLACE `test_orchestrator_cannot_receive`). Sub-cycles (each FAIL-pre / PASS-post reasoned):

- **4a. bare `--to orchestrator`, live gen → per-gen delivery.** Seed a live registry entry (write a `comms/sessions/g1.json` with `role=orchestrator`, `last_seen=now`, frozen `now`); `post_message(root, charc, ["orchestrator"], "fyi", ...)` → a file lands in `comms/orchestrator/g1/inbox/`; the `to:` frontmatter is `orchestrator:g1`; `comms/orchestrator/inbox` does NOT exist. FAIL-pre: orchestrator not in VALID_TO → MailError, no file. **[guard #2]**
- **4b. bare `--to orchestrator`, NO live gen → CLEAR ERROR.** Empty/all-stale registry; `post_message(... ["orchestrator"] ...)` raises `NoLiveOrchestratorError`; rc==1 via CLI; the message names "no live orchestrator" + the recovery hint; NO file written (not a silent drop: assert rc==1 AND `rglob("*.md") == []`). FAIL-pre: rejected as "invalid recipient" (wrong reason); a silent-drop impl would rc==0 — distinguished. **[§7 no-live-gen clear error]**
- **4c. `--to orchestrator:<sid>` reaches a PRUNED *and* a NEVER-registered gen, and the full send→read→ack round-trip works WITHOUT `session-start` (registry-INDEPENDENT; lazy bootstrap).** Over an EMPTY registry (no `comms/sessions/` entries, NO pre-existing `comms/orchestrator/` dir — so the test cannot pass on incidental prior state): (i) `post_message(root, charc, ["orchestrator:g2"], "fyi", ...)` with `g2` NEVER registered delivers a file to `comms/orchestrator/g2/inbox/` (send-path `_write_temp` mkdir bootstraps `inbox/`, §2.5); (ii) `read --role orchestrator --session g2 --all` prints AND moves the file into `comms/orchestrator/g2/read/` (ack-path mkdir bootstraps `read/` lazily — proving full round-trippability with no `session-start`, Codex R3 MAJOR); (iii) register-then-prune `g3`, then `["orchestrator:g3"]` still delivers (pruned ≠ gone). All succeed even though `newest_live` is None. FAIL-pre: orchestrator rejected entirely (no file). **[guard #1, #6; Codex R1 CRITICAL+MAJOR, R3 MAJOR]**
- **4d. session_id path-safety in `:<sid>`.** `orchestrator:../evil`, `orchestrator:/abs`, `orchestrator:` (empty), `orchestrator:a/b` → MailError; NO `.md` outside the per-gen tree. Also `charc:foo` (suffix on a singular role) → MailError. **[guard #5]**
- **4e. type×recipient matrix** (§5 table) — fyi/status/query/return_report to `orchestrator:g1` delivered; `decision_request` to `orchestrator:g1` AND to bare `orchestrator` (live gen) → MailError with "L1" in the text (NOT "invalid recipient"); `decision_request` to operator still delivered; pipeline `decision_request` to `orchestrator:g1` → "automated emitter" rejection. **[§5; lock: L1]**
- **4f. read/list/peek/ack with `--session` (the full round-trip).** post to `orchestrator:g1`; `peek --role orchestrator --session g1` shows it without acking (inbox count unchanged); `read --role orchestrator --session g1 --all` prints AND moves the file from `comms/orchestrator/g1/inbox/` → `comms/orchestrator/g1/read/` (proving `cmd_read` threaded `--session` into `ack_message`, Codex R2 MAJOR — a 3-arg ack would have errored); `read --role orchestrator` (no `--session`) → MailError; `list --role orchestrator --session g1` counts it.
- **4g. single-sourced reader — BEHAVIORAL delegation (primary) + a narrow structural backstop.** (i) **Behavioral (the binding single-source proof, Codex R1/R2 MINOR — robust to renamed/re-exported logic):** load role_mail, force its `_registry()` to return a STUB module whose `newest_live` returns a sentinel `{"session_id": "STUB"}` and whose `per_generation_inbox` returns a sentinel path; assert a bare `--to orchestrator` resolves through the stub (e.g. resolves to the stub's `per_generation_inbox`/`STUB`), proving role_mail DELEGATES rather than computing liveness or the per-gen path itself. A private copy ignores the stub and fails. (ii) **Structural backstop — a NON-BLOCKING SANITY CHECK only, NOT the binding discriminator (Codex R2/R4 MINOR; brief guard #4 mandates a grep-clean check, kept minimal):** assert `scripts/role_mail.py` contains NO `def newest_live` and NO `STALE_SECONDS =` assignment; assert `scripts/comms_session_registry.py` DOES define `newest_live` + `STALE_SECONDS`. The behavioral test (i) is the real single-source proof; the grep is a cheap structural smoke-check that may need a one-line update on a harmless refactor. **[guard #4]**
- **4h. backward-compat regression** — the EXISTING singular post/list/read/peek/multi-recipient/L1/atomic-rollback/ASCII tests still pass unchanged; `_ensure_tree` still creates charc/rd/operator (and does NOT create `comms/orchestrator/inbox`); `ack_message(root, "operator", fname)` (3-arg) still works.

**Commit(s):** `feat(comms): Task 4 -- role_mail orchestrator per-gen addressing (newest-live + explicit-:sid)`. (Split into 4-write / 4-read commits if the diff is large; keep each red→green.)

### Task 5 — full fast suite to green + cross-cutting checks
Run `python -m pytest -m "not slow" -q` from the worktree (the WHOLE fast suite, per recipe §2) and fix any failure (esp. `test_comms_ui.py` + `test_comms_unread_hook.py` + `test_harness_probe_comms.py` — assert they stay green: comms_ui + the unread/stop hooks are untouched). Confirm `ruff check swing/` is clean (no `swing/` files touched, so it should be a no-op — verify). **No commit unless a fix is needed** (then `fix(comms): ...` per the surfaced break).

---

## 8. Operator §5.10 live-witness checklist (BINDING for the addressing UX — CHARC-guided, post-merge)

(For the orchestrator after QA; recorded here so the executing implementer wires the surfaces the witness needs.)
1. From a director session, `role_mail post --from charc --to orchestrator ...` reaches the running generation's per-gen inbox.
2. `--to orchestrator:<sid>` reaches a SPECIFIC generation, including an idle/pruned one (registry-independent).
3. `peek/list/read --role orchestrator --session <sid>` shows + drains the orchestrator's box.
4. **The empty/no-live-gen path (seeded-gate-masks-default):** bare `--to orchestrator` with NO live generation emits the CLEAR ERROR (not a silent drop).
5. Stale-prune fires at SessionStart; an orchestrator session's `last_seen` refreshes each prompt (registry file mtime/`last_seen` advances).

---

## 9. Flags / deviations / open items (for the orchestrator + CHARC)

- **`orchestrator-state.md` rollover pointer — DEFERRED** (§6; brief-sanctioned optional).
- **`_unique_path` same-second cross-process clobber race — PRE-EXISTING, OUT OF SCOPE** (§1; swing's token-free helper kept per brief lock §6).
- **The registry's `_atomic_write_text` is a LOCAL copy of role_mail's `_write_temp`+`os.replace` pattern, not a cross-import** (§2.1) — to break a role_mail↔registry import cycle and keep the registry zero-dep. Same proven same-dir+`os.replace` pattern (cross-volume gotcha respected); Task 1 sub-cycle 9 adds the same-dir-staging regression test guarding it. Flagged for the executing review's adjudication.
- **role_mail consumes `newest_live` + `is_valid_session_id` from the registry; it does NOT call `read_entry`** (the brief §A lists `read_entry` in the imported surface — it is consumed by the HOOKS, not role_mail). The single-source guarantee (no re-implementation anywhere) is what guard #4 binds; minor literal deviation from the brief's list, flagged.
- **`test_orchestrator_cannot_receive` is REPLACED** (its old assertion is inverted by this arc); the replacement asserts the new contract (§7 Task 4).
- **The orchestrator auto-unread-notice in its OWN session is DEFERRED** (option (b) rationale, §2.4) — pairs with the Arc-B topology decision; the box is witnessed via `role_mail peek/list` in Arc A.

If any executing step would cross the Arc-A boundary (Arc B/C, a `comms_stop_hook.py` change, a `swing/` touch, a schema/migration, a new dependency): STOP and flag — do not work around.
