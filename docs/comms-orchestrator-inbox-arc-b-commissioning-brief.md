# Comms Orchestrator Launch + Bus — Arc B Commissioning Brief (G6)

**Owner/author:** CHARC (Tool Development Director). **Date:** 2026-06-26. **Status:** COMMISSIONED.
**Phase context:** Phase-18-close **G6** (comms-system sync swing↔coa-chess), arc **B of A→B+C** (operator-sequenced 2026-06-25). **Arc A MERGED** @ code `94e8c7cb` (main `f44b0881`) — the per-gen inbox + registry + addressing.
**§3 verdict:** **SUB-TRIPWIRE** (no new schema / module / dependency / standing-process / `swing/` carve-out — extends the EXISTING `scripts/` launcher + `comms_ui.py` GUI). This brief routes through CHARC because Arc B is CHARC-owned harness architecture (I commission it), NOT because a tripwire is crossed. RD fyi (comms-user, not measurement). GO.
**Grounding / design source:**
- Arc A shipped shape (the seam): `scripts/comms_session_registry.py` + `scripts/comms_session_hook.py` + `scripts/role_mail.py` (orchestrator addressing) on main.
- Live swing surfaces Arc B edits: `scripts/start_directors.ps1` + `scripts/comms_ui.py` (verified on disk 2026-06-26 — see §1).
- Reconciliation notes: `docs/comms-orchestrator-inbox-reconciliation-notes.md` — **READ §1 of THIS brief first; the notes are STALE on what swing already has.**

---

## 0. Why

The "both affordances" decision (operator 2026-06-25): swing offers BOTH a launch-an-orchestrator-as-a-CC-session button AND a copy-the-bootstrap-text button; the operator picks per case. The launch button is what makes a GUI-launched orchestrator **auto-register** (it sets `SWING_ROLE=orchestrator`, so Arc A's `SessionStart` hook registers the generation → bare `--to orchestrator` resolves to it). Plus an orchestrator **bus** so the operator can see the per-generation orchestrator inboxes in the GUI.

## 1. PREMISE CORRECTION — the reconciliation notes are STALE (verified on disk 2026-06-26)

The notes say swing has "NO orchestrator launch/bootstrap/bus." **FALSE on the live code.** What swing ALREADY HAS:
- **`start_directors.ps1` is already role-parameterized** (`[ValidateSet('charc','rd','both')]`) and **already spawns via `wt -w 0 new-tab`** (the **new-tab LOCK is already satisfied** — preserve it, do NOT touch the spawn mechanism), with a `-NoExit -EncodedCommand` plain-window fallback. It sets `$env:SWING_ROLE='<role>'` **inside the spawned shell** via `Build-LaunchCommand` (`start_directors.ps1:191-201`) — the load-bearing wt-new-tab env-propagation pattern (a launcher-set env would NOT propagate through wt's already-running process). The launch flags are `--model opus --effort max --permission-mode auto`, preflight-verified.
- **`comms_ui.py` already has:** `/directors/launch` (POST, **L5 fixed-argv** `powershell -NoProfile -File scripts/start_directors.ps1 -Role <role>` [+`-Resume`], enum-validated against `LAUNCH_ROLES=("both","charc","rd")`); **`/orchestrator-bootstrap`** (GET, serves `orchestrator_bootstrap.md` verbatim) + the **"Copy orchestrator spin-up"** button (`comms_ui.py:339-357,604,769`) — **the copy-text affordance ALREADY EXISTS**; `/panes/bus` with `BUS_ROLES=("charc","rd")`; `_recorded_sessions` reading the launcher's `.sessions.json` map.
- **`scripts/orchestrator_bootstrap.md` EXISTS** (the served copy-text).

So the REAL Arc B delta is small — see §2. (This correction is the §5.11 sibling-doc-vs-live hazard: the notes were grounded against an Explore + the coa-chess reference, which conflated coa-chess's state with swing's. Ground every "swing has/lacks X" claim against the live file at writing-plans.)

## 2. Scope — Arc B

**IN (the corrected, narrower delta):**
1. **Launcher — add the `orchestrator` role** to `start_directors.ps1`: extend `-Role` `[ValidateSet]` with `orchestrator`; add `orchestrator` to `$BootstrapFiles` (point at the existing `scripts/orchestrator_bootstrap.md`) + `$RoleTitles`. The existing fresh/resume + `wt new-tab` + the `$env:SWING_ROLE` set-inside-the-shell path all apply unchanged — a launched orchestrator sets `SWING_ROLE=orchestrator` → Arc A's `SessionStart` hook auto-registers the generation. (Decide at writing-plans whether the orchestrator participates in the `.sessions.json` display-name/resume map like directors, or is fresh-only since it rotates — the Arc A `comms/sessions/` registry, NOT `.sessions.json`, is its liveness record either way.)
2. **GUI launch enum — add `orchestrator` to `LAUNCH_ROLES`** so the launch strip offers it; the existing generic `/directors/launch` route passes `-Role orchestrator` to the launcher (verify the route needs no other change — it builds argv from the enum-validated role).
3. **Orchestrator bus aggregation** — a read-only `_orchestrator_inbox_messages(root)` that walks `comms/orchestrator/<sid>/inbox` across ALL generations (per-gen, since the orchestrator rotates) + surface it in the GUI bus (extend `BUS_ROLES` or add a dedicated orchestrator-bus pane). Read-only, defensive-never-raises (a malformed/absent per-gen dir degrades to empty, never a 500).

**OUT (do NOT build — STOP-and-flag if a fix would cross this):**
- The GUI re-sync swing→harness-template scaffold (B-11 dark-theme + B-13 expanded-`<details>` fix) → **Arc C**.
- Any `comms/` core change (the registry / hook / `role_mail` are Arc-A-DONE; Arc B only READS the registry + per-gen inboxes for the bus). Any `swing/` touch, schema, or new dependency.
- Any coa-chess edit. Any change to the new-tab spawn mechanism (already correct).
- The `orchestrator-state.md` rollover pointer (Arc-A-deferred; not Arc B unless the implementer finds the launch genuinely needs it — then FLAG, don't silently add).

## 3. The Arc A seam + the two affordances

- **Affordance (a) — LAUNCH button (NEW in Arc B):** launches an orchestrator as a standalone CC-session tab with `SWING_ROLE=orchestrator` → Arc A's `SessionStart` hook auto-registers the generation → bare `--to orchestrator` resolves to it. This is the auto-registering path (a topology shift: the orchestrator runs as a CC tab, like the directors).
- **Affordance (b) — COPY-bootstrap-text (ALREADY EXISTS):** for an orchestrator the operator starts manually (e.g. the VS-Code relay). That session does NOT carry `SWING_ROLE=orchestrator` unless the operator sets it, so it does NOT auto-register — reach it via explicit `--to orchestrator:<sid>` or by setting the env. This is the unchanged control-point path.
- Both present = the operator's "both affordances" decision. Arc B ADDS (a); (b) already works.

## 4. Locks to PRESERVE (verified on disk)

- **L5 — launch runs exactly ONE enum-validated fixed argv; nothing user-typed reaches the command line.** Adding `orchestrator` to `LAUNCH_ROLES` + the launcher `[ValidateSet]` keeps this intact (the role is enum-validated BEFORE argv is built, `comms_ui.py:744-754`). Do NOT introduce any user-typed value into the launch path.
- **L1** (compose never offers `decision_request`; server-stamps `from=operator`), **L3** (ack ONLY `operator/inbox`; read-only on every other role's files — the orchestrator bus is READ-ONLY), **L4** (all writes via `role_mail`). The bus aggregation only READS per-gen inboxes; it never acks or writes.
- **The `$env:SWING_ROLE` set-inside-the-spawned-shell pattern** (`start_directors.ps1:191-201`) — load-bearing for wt new-tab; the orchestrator launch MUST use the same path (it does, by reusing `Build-LaunchCommand`/`Start-RoleWindow`). Do NOT set the role in the launcher's own env and expect propagation.
- **Optional-`[web]` import isolation** — the comms core never imports `comms_ui.py`; keep it. The bus aggregation lives in `comms_ui.py`, not the core.
- **PowerShell 5.1 compatibility** (no `&&`/ternary/null-coalescing) + ASCII-only console output + serial role launch (the `.sessions.json` read-modify-write is not concurrency-safe) — all per the launcher's existing constraints.

## 5. Test / gate posture

- **`comms_ui` tests** (over a tmp comms tree): the launch strip offers `orchestrator` + `/directors/launch` accepts the enum-validated `orchestrator` role (mock the subprocess — do NOT actually spawn); the orchestrator bus aggregates synthetic `comms/orchestrator/<sid>/inbox` messages across multiple gens, read-only, and degrades to empty on a malformed/absent per-gen dir (never 500). The L1/L3/L5 locks stay asserted.
- **Launcher `-DryRun` test** for `-Role orchestrator` (compute the session name + the exact `claude` command line + that `$env:SWING_ROLE='orchestrator'` is in the inner command, WITHOUT launching).
- **Operator §5.10 + BROWSER witness is BINDING for the GUI** (the HTMX/browser-only failure surfaces — memory `feedback_visual_gate_both_render_and_browser` + the HTMX gotchas): in a real browser, launch an orchestrator from the GUI strip → a new tab opens, `SWING_ROLE=orchestrator` set, and (Arc A) a `comms/sessions/<sid>.json` registers → the orchestrator appears in the bus; the existing "Copy orchestrator spin-up" button still copies the bootstrap text; a message posted to the launched gen shows in the bus. Witness the empty/no-gen bus state too (seeded-gate-masks-default).
- **Merged-head no-false-green** full-suite re-run is the binding green (memory `feedback_no_false_green_claim`).
- review-strong (gpt-5.5/high) to convergence + codex-auto-review (production-adjacent harness; repo-access).
- Worktree-isolated executing (`scripts/` + `comms_ui.py`; no `swing/` touch). **TaskStop does not kill a detached `comms_ui`/launched session** (memory `feedback_taskstop_does_not_kill_detached_server`) — tear down any spawned process at the gate.

## 6. Dispatch recommendation

- **Implementer cell:** `implementer-opus-high`. Rationale: settled design, narrow delta, but it spans PowerShell (the launcher `[ValidateSet]` + maps) + a browser-rendered GUI (the launch enum + the bus aggregation) with real browser-only failure surfaces (HTMX) and the L5/L1/L3 locks to preserve. Not measurement-chain (no `swing/`/schema) → not `-max`; richer than mechanical → above `-sonnet`.
- **Orchestrator:** Opus xhigh (default).

## 7. Return report

**The ORCHESTRATOR posts the return report to `charc` (+ `operator` fyi) AFTER its own QA** — the implementer reports to its orchestrator in chat, never to a director inbox (memory `feedback_implementer_never_posts_to_directors`; charter §5.6). CHARC code-QAs the locks + the Arc-A seam on disk; RD fyi; the operator's §5.10 **browser** witness is the binding gate before merge.
