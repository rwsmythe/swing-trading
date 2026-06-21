# Comms Orchestrator-Inbox — Swing Reconciliation Notes (Phase-18-close prep)

**Purpose:** prep for the operator-directed Phase-18-close comms-system sync (swing↔coa-chess) — specifically ADDING the per-generation orchestrator inbox + session registry to swing (it has proved convenient in coa-chess and removes the standing "CHARC has no orchestrator inbox → route via operator" friction).
**Source reviewed:** the coa-chess CHARC reference at `C:\Users\rwsmy\coa-chess\docs\comms-orchestrator-inbox-reference.md` (2026-06-21) — describes coa-chess's as-built; adapt to swing's roster, do NOT copy verbatim.
**Status:** PREP ONLY. The arc is scheduled AFTER Phase-18 close + cleanup. Not commissioned yet; this grounds the eventual brief + §3 pass.

---

## The design to port (the roster-agnostic SHAPE)

Two inbox shapes, driven by one asymmetry — directors are stable named targets; the orchestrator ROTATES on context (a generation hits its limit, hands off, a fresh one starts), so a message must reach *a specific running generation*, resolved at SEND time:
- **SINGULAR-inbox roles:** `comms/<role>/{inbox,read}` (one fixed box).
- **PER-GENERATION-inbox role (orchestrator):** `comms/orchestrator/<session_id>/{inbox,read}` — one subtree per generation.
- **Registry:** `comms/sessions/<session_id>.json` — **ONE FILE PER SESSION** (no shared-map write contention); `{session_id, role, transcript_path, last_seen}`; `last_seen` heartbeat refreshed every UserPromptSubmit; `STALE_SECONDS = 45*60`; `newest_live` = newest non-stale; prune-stale on session start.
- **Addressing:** `--to orchestrator` (bare) = newest-live, resolved at send (CLEAR ERROR if no live gen, never a silent drop); `--to orchestrator:<session_id>` = explicit gen — writes directly, registry-INDEPENDENT (a known gen is always reachable even if its heartbeat is stale/pruned). Reading: `read --role orchestrator --session <sid>`.
- **Atomic delivery:** same-dir `mkstemp` + `os.replace` (the Windows cross-volume `os.replace` gotcha swing already knows); collision-suffix on name clash.

---

## Swing roster mapping (the ADAPT step)

- **SINGULAR:** `charc`, `rd` (swing's 2nd director is the Research Director — coa-chess's is `opsdir`), `operator`.
- **PER-GENERATION:** `orchestrator` ONLY (it rolls over on context — confirmed by the swing orchestrator generational handoffs this session). Implementers are ephemeral sub-agents (no inbox). So the orchestrator is the sole rotating role.

## Swing deltas — HAVE vs NEED

- **HAVE:** `scripts/role_mail.py` (singular inboxes charc/rd/operator; `--to orchestrator` currently REJECTED — the "no orchestrator inbox" restriction); `scripts/comms_unread_hook.py` (UserPromptSubmit notice — but NO heartbeat/registry refresh); `scripts/comms_stop_hook.py` (B-14 close-hook, enabled 2026-06-21).
- **NEED:** the per-generation orchestrator inbox + the `comms/sessions/` registry + a `session_start.py` hook (register/refresh `last_seen` + idempotent per-gen inbox creation + prune-stale + **single-source the registry reader** that role_mail imports); role_mail orchestrator addressing (`_split_target` for `:<sid>`, `_newest_live_session_id`, the orchestrator branch in `_inbox_for_target`); the `session_id` safety validation; the rollover state-pointer convention (swing already writes `orchestrator-handoff-*` docs — align to the `orchestrator-state.md` newest-live pattern). The arc REMOVES the `--to orchestrator`-rejected restriction.
- **Launcher + comms-GUI orchestrator BOOTSTRAP option (operator 2026-06-21):** coa-chess's Stage-1.5 comms GUI offers a bootstrap START option for ORCHESTRATORS in addition to the director roles. Swing's cold-start launcher (`scripts/start_directors.ps1`) + the Stage-1.5 comms GUI get the same — a "start orchestrator" bootstrap that launches a CC session with `SWING_ROLE=orchestrator` and triggers `session_start` registration (a NEW per-generation `session_id` + its per-gen inbox). This pairs tightly with the per-gen inbox: **the bootstrap is what registers a generation.** **Topology decision for the arc:** swing's orchestrators currently run in VS Code under manual operator relay (the control-point model); decide whether swing adopts orchestrator-as-bootstrapped-CC-session (the coa-chess pattern) OR keeps the VS Code relay and adds only the registration. (Ground the coa-chess comms-GUI bootstrap implementation at the arc — operator to point to it, as with this inbox reference.)

---

## The ONE real divergence to reconcile — the close-hook

- **swing B-14 (just enabled):** continue-ONCE-per-turn — the `Stop` hook blocks on any unread unless `stop_hook_active` (the loop guard), safe-default-allow-stop on any stdin failure, drain-each-cycle terminates it. STATELESS, loop-safe by construction.
- **coa-chess references a "fire-on-NEW-only" design** (its `docs/template-feedback-close-hook-inbox-check.md`) — only continues on a genuinely-NEW message (tracks a last-seen marker).
- **CHARC read:** the two are close in EFFECT — continue-once + drain ≈ fire-on-new (draining clears unread), but mine is simpler/stateless and fire-on-new is more precise (no re-fire on a read-but-unacked message). Both loop-safe. **Lean: keep swing's continue-once** (simpler, stdlib, now proven live on swing as the operator-designated test-case) unless fire-on-new's precision earns its state. DECIDE at the arc; unify the two projects on one design.

## Lessons-learned guards to KEEP (the non-obvious parts coa-chess paid for)

1. `newest_live == None` is NOT "window closed" — the gen may be idle>45min (pruned) yet resumable; reach it via explicit `:<sid>`. Registry-pruned != gone.
2. Per-gen inboxes exist BECAUSE the orchestrator rotates (don't give a rotating worker a singular box).
3. One-file-per-session registry > a shared map (no contention; partial-file degrades to one-entry-missing, not a corrupt global).
4. Single-source the registry reader (role_mail imports `newest_live`/`read_entry` from the hook — no writer/reader drift).
5. `session_id` is path input (a dir name AND a filename) — validate it as a safe single segment at EVERY write+consume site, and require filename==embedded-id (anti-traversal/mis-route).
6. Explicit-sid + the rollover state-pointer are the resilience pair.

## Disciplines for the arc

- **STDLIB-ONLY in the comms core** (coa-chess enforces via `tests/test_dependency_posture.py`; swing's role_mail + hooks are already stdlib — keep it).
- Harness/comms change — measurement-NEUTRAL (no measurement chain) but a SIGNIFICANT comms-architecture change. At commissioning: a CHARC §3 pass (a new `session_start` standing-process hook + new comms files; assess tripwires) + a brief; keep the lessons-learned guards as explicit acceptance criteria.
- This is CHARC-owned harness architecture; the coa-chess reference is instance-CHARC→swing-CHARC peer input, not a spec to copy.
