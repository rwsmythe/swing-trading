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

## Comms GUI reconciliation (from coa-chess `scripts/comms_ui.py`, 675 lines, reviewed 2026-06-21)

A single-file FastAPI+HTMX localhost mail UI — OPTIONAL (`[web]` extra; the core comms NEVER import it → import-isolation preserves the zero-hard-deps core). 127.0.0.1 only; HTMX VENDORED locally (no CDN — this origin holds POST authority). Locks to KEEP: **L1** (compose never offers `decision_request`; server-stamps `from=operator`), **L3** (acks ONLY `operator/inbox`; read-only on every director/orchestrator file; never deletes), **L4** (all writes via `role_mail`), **L5** (launch runs exactly ONE enum-validated fixed argv — nothing user-typed reaches the command line).

**DIRECTION (operator-confirmed 2026-06-21): swing's GUI is the NEWER source-of-truth; the reconciliation is MOSTLY swing→coa-chess.** coa-chess's `comms_ui.py` is the OLDER stale-snapshot (the B-13 refresh-closes-the-expanded-window bug + no B-11 dark-theme toggle). So: RE-SYNC swing's current GUI → coa-chess/the scaffold (the bulk of the work); the ONE coa-chess→swing item is the orchestrator-bootstrap MECHANISM — **EXTRACT just that** (the launch enum + `launch_role.ps1` + `/orchestrator-bootstrap` + the bus aggregation) **and GRAFT it onto swing's newer GUI base — do NOT adopt coa-chess's older GUI wholesale.**

**The two directions in detail:**
- **coa-chess → swing (EXTRACT only the orchestrator bootstrap onto swing's newer base):**
  - `LAUNCH_ROLES = ("both","charc","orchestrator","opsdir")` + `LAUNCH_MODES=("fresh","resume")` — the launch strip STARTS an orchestrator, not just directors, via a role-parameterized `launch_role.ps1` (swing generalizes `start_directors.ps1` → role-parameterized; an orchestrator launch sets `SWING_ROLE=orchestrator` → `session_start` registration). KEEP the L5 enum-validation.
  - A `/orchestrator-bootstrap` endpoint + a copy-to-clipboard button serving the orchestrator bring-up text (from the bootstrap doc's orchestrator section). **This RESOLVES the topology decision I flagged:** coa-chess supports BOTH launch-as-CC-session AND copy-bootstrap-text-for-a-manually-started session — so swing can offer both (a launch button for CC-session orchestrators + a copy-bootstrap button for the VS-Code-relay pattern; operator picks per case).
  - Bus aggregation: `BUS_ROLES=("charc","orchestrator","opsdir")`; the per-generation orchestrator inboxes are AGGREGATED read-only (`_orchestrator_inbox_messages` walks `comms/orchestrator/<sid>/inbox` across all gens). Swing's GUI gains the orchestrator bus view.
- **swing → coa-chess/scaffold (the GUI bug fixes, B-11/B-13):** coa-chess's `comms_ui.py` has NO dark-theme toggle (grep-confirmed) and uses naive `hx-trigger="every 5s"` + `hx-swap="innerHTML"` pane refresh (the B-13 expanded-`<details>`-collapse vector). Swing's CURRENT comms GUI carries the dark-theme toggle (B-11) + the auto-refresh-preserves-expanded fix (B-13) → port those TO the scaffold/coa-chess (the B-13 RE-SYNC).

**Swing GUI delta:** swing HAS a Stage-1.5 comms GUI (with the dark theme + the refresh fix) but it predates the orchestrator inbox → NO orchestrator launch/bootstrap/bus. The arc ADDS the orchestrator launch enum + the `launch_role.ps1` generalization + the `/orchestrator-bootstrap` copy + the orchestrator bus aggregation, KEEPING swing's GUI fixes, the L1/L3/L4/L5 locks, and the optional-`[web]`-extra import-isolation.

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

---

## RE-GROUNDED 2026-06-25 (CHARC, at G6 commence — Explore comparative survey of BOTH repos' CURRENT comms state)

The 2026-06-21 delta above HOLDS. Current-state specifics + corrections (verify each at the brief):
- **swing `role_mail` (current):** `VALID_FROM = (charc, rd, operator, orchestrator, pipeline)` — `orchestrator` + `pipeline` are now SENDERS (pipeline from 18-H.7), but `VALID_TO = (charc, rd, operator)` → **`--to orchestrator` is STILL REJECTED** (the restriction the arc removes); NO `:<sid>`/newest-live addressing yet.
- **swing hook LOCATION (correction):** swing's comms hooks live in **`scripts/`** (`comms_unread_hook.py` + `comms_stop_hook.py` [B-14, LIVE — it fires every turn]) wired via `.claude/settings.json` — NOT `.claude/hooks/`. (The Explore's ".claude/hooks absent" = location, not absence.) coa-chess's are in `.claude/hooks/` (the `session_start`/`session_end`/`user_prompt_submit` registry-owning trio; `session_start` single-sources the registry reader). **G6 decides swing's `session_start` hook location** (scripts/ to match swing, or .claude/hooks/ to match coa-chess).
- **swing `comms/` (current):** singular `comms/{charc,rd,operator}/{inbox,read}` + `.sessions.json` (display-name map only). NO `comms/sessions/` registry, NO `comms/orchestrator/<sid>/`.
- **coa-chess HAS the full per-gen stack (confirmed current):** `comms/sessions/<sid>.json` registry + `comms/orchestrator/<sid>/{inbox,read}` + the 3 `.claude/hooks/` + role_mail `:<sid>`/newest-live + the GUI bus (`_orchestrator_inbox_messages`, `/panes/bus`, BUS_ROLES incl. orchestrator) + launcher orchestrator role (sets HARNESS_ROLE). (coa-chess's 2nd director is `opsdir`; swing's is `rd`, already present.)
- **GUI re-sync direction CONFIRMED:** swing's `comms_ui.py` HAS the dark-theme toggle (B-11) + the expanded-`<details>`-preserved-on-5s-refresh fix (B-13); coa-chess's LACKS the dark-theme toggle. → swing→coa-chess for the GUI fixes; coa-chess→swing for ONLY the orchestrator-bootstrap/bus mechanism, grafted onto swing's newer base.
- **LAUNCHER SPAWN PREFERENCE (operator 2026-06-25, LOCK):** swing's launcher opens a **NEW TAB** in the existing PowerShell window; coa-chess SPAWNS A NEW WINDOW. **The operator PREFERS swing's new-tab method** → when generalizing `start_directors.ps1` → role-parameterized, KEEP swing's new-tab spawn; do NOT adopt coa-chess's new-window spawn.
- **§3:** the new `session_start` standing-process hook + new comms files = a CHARC §3 tripwire pass (new standing process); a SIGNIFICANT comms-architecture change; CHARC-owned. **Likely DECOMPOSE:** (A) the core inbox/registry/role_mail-addressing/`session_start`-hook arc; (B) the launcher (new-tab, role-parameterized) + GUI orchestrator-bootstrap/bus arc; (C) the GUI re-sync swing→coa-chess/scaffold. **Two decisions to present to the operator:** the close-hook unify (swing continue-once vs coa-chess fire-on-new) + the topology (orchestrator-as-bootstrapped-CC-session vs keep the VS-Code relay + add only registration).

**NEXT (fresh CHARC):** synthesize the G6 scope from this re-grounding → the §3 pass → bring the scoped proposal (the A/B/C decomposition + the 2 decisions + the new-tab lock) to the operator BEFORE commissioning.
