# Comms-GUI Re-Sync (swing→scaffold) — Arc C Commissioning Brief (G6 last item)

**Owner/author:** CHARC (Tool Development Director). **Date:** 2026-06-27. **Status:** COMMISSIONED.
**Phase context:** Phase-18-close **G6**, **Arc C** (the LAST G6 item). Arc A `94e8c7cb` + Arc B `1f8b8545` + B.1 `df262a4d` merged (swing's orchestrator comms system).
**Target repo:** **`C:\Users\rwsmy\harness-template`** (the generic scaffold) — NOT swing. **Cross-repo dispatch: swing orchestrator → harness-template** (operator-decided 2026-06-22; G4 ran B-9/B-12/B-16 this way).
**Source-of-truth:** swing's CURRENT comms GUI `C:\Users\rwsmy\swing-trading\scripts\comms_ui.py` (read cross-repo; transcribe the MECHANISM only).
**§3 verdict:** **SUB-TRIPWIRE** (scaffold comms-GUI templates/static/JS + one `.claude` Stop-hook; no schema / new module / dependency / novel standing-process / `swing/` carve-out — it ports PROVEN swing mechanisms into the scaffold). **CHARC-owned** (the scaffold IS CHARC's harness-architecture domain). RD n/a. GO.

---

## 0. Why

The scaffold's Stage-1.5 comms GUI is a STALE pre-fix snapshot of swing's (backlog B-11/B-13). It lacks the dark-theme toggle and the expand-preserve-across-the-5s-poll fix that swing's matured comms GUI carries — so a project germinating from the scaffold (e.g. coa-chess) inherits an old comms UI. Arc C re-syncs the GENERIC GUI-polish deltas from swing's current comms GUI into the scaffold, in one diff-driven pass.

## 1. PREMISE — grounded on disk 2026-06-27 (do NOT trust the reconciliation notes / backlog claims unverified)

Verified by structural-marker diff of `harness-template/scripts/comms_ui.py` (666 lines) vs swing's `scripts/comms_ui.py` (830 lines):
- **The scaffold ALREADY HAS the orchestrator stack** — `BUS_ROLES=("charc","orchestrator")` (:73), `LAUNCH_ROLES=("both","charc","orchestrator")` (:78), `_orchestrator_inbox_messages` (:170), `/orchestrator-bootstrap` (:608), the `/directors/launch` enum-gate (:584). So **Arc C does NOT port the orchestrator inbox/launch/bus** — the scaffold has its own (it predates swing's G6; swing was the laggard until Arc A+B).
- **The scaffold LACKS exactly the GUI-polish fixes (the Arc-C delta):** NO `theme-toggle`/`toggleTheme` (B-11 dark-theme missing); NO "Preserve expanded" JS (B-13 — the scaffold carries the `data-key` attribute but not the preserve-across-5s-poll-swap logic).
- **An orchestrator-bus MODEL divergence exists but is OUT OF SCOPE:** the scaffold's `_orchestrator_inbox_messages` returns a flat `list[Message]` and treats orchestrator as a `BUS_ROLES` member; swing's Arc-B design returns a per-gen-grouped `list[dict]` (disk-enumerated, grouped by sid). This is a comms-bus DESIGN difference, NOT a GUI-polish fix — **Arc C does NOT touch it** (see §2 OUT). Flagged as a candidate future scaffold item (whether the scaffold's flat orchestrator-bus correctly handles per-gen rotation is a separate question).

## 2. Scope — Arc C (the comms-GUI re-sync)

**Approach (backlog B-13, supersedes patching B-11/B-13 one-by-one):** the implementer **DIFFS the scaffold's comms GUI (templates + static/JS + CSS in `comms_ui.py`) against swing's CURRENT comms GUI**, identifies the GENERIC GUI-polish deltas, and ports the MECHANISM (markup + JS + CSS variables), genericized — catching B-11 + B-13 + any OTHER post-snapshot GUI-polish fix the diff surfaces (the "unknown unknowns" the stale snapshot misses).

**IN:**
1. **B-11 — dark-theme toggle:** the no-flash head script (`localStorage` `*-theme`), the toggle button + its `_applyThemeIcon`/`toggleTheme` JS, the themed CSS custom properties on `:root`/`[data-theme="dark"]`. Swing reference: `comms_ui.py:334-387` + the CSS; swing fix commits `991430c8` (17-D.2) + `5df335d4` (icon-parity).
2. **B-13 — expand-preserve:** the `data-key`-keyed live-set JS that preserves open `<details>` across the 5s poll's `innerHTML` swap. Swing reference: `comms_ui.py:389+` ("Preserve expanded <details>…"); the implementer git-blames that block for the swing fix commit to cite.
3. **Any other GENERIC GUI-polish delta** the diff surfaces (cite each swing commit).
4. **B-14 — the Stop/close-hook** (queued for G6; a continuous-ops bridge): add a genericized `Stop` hook to the scaffold's `.claude` hook set running the same role_mail unread check (block-on-unread + `stop_hook_active` loop-guard + safe-default-allow-stop), mirroring swing's LIVE `scripts/comms_stop_hook.py` + the `.claude/settings.json` `Stop` entry (`e8686e0e`). MECHANISM only, genericized. (Distinct surface from the GUI; commit separately. If the scaffold already has an equivalent Stop-hook, this is a no-op — verify on disk first.)

**OUT (STOP-and-flag if a fix would cross):**
- The orchestrator-bus MODEL difference (flat vs per-gen-grouped — §1; a separate future scaffold item, NOT GUI-polish).
- **Swing STYLING / BRANDING / CONTENT / CONFIG** — the §5.1 scaffold-contamination guard. Transcribe the reusable MECHANISM (theme-toggle infrastructure, expand-preserve logic), NOT swing's specific colors/labels/copy/project terms. A theme toggle is generic UI infra; "SwingTrading"/role-specific copy is not.
- Any `swing/` or swing-repo touch (Arc C is harness-template-ONLY).
- Any schema / new dependency / new module.

## 3. The contamination guard (§5.1) — load-bearing, with executable teeth

The scaffold carries the **B-9 genericity gates** (`test_core_files_are_not_instance`, `test_whole_tracked_tree_is_clean`, the CORE-contamination tests) — they FAIL if a swing project-term / instance content leaks into a CORE file. The re-sync MUST keep them green: port the GENERIC mechanism, never swing branding/content. The implementer runs the scaffold's full test suite (incl. the genericity gates) — a contamination leak trips them. This is the recurring "do NOT contaminate the generic scaffold with swing config" catch, here enforced by the scaffold's own tests.

## 4. Tests / gates

- The scaffold's existing comms_ui tests stay green; ADD (mirroring swing's, genericized): a dark-theme test (the toggle control renders + the persisted-preference head script present) + an expand-preserve test (the `data-key` live-set JS present in the rendered page). The genericity gates (B-9) stay green (contamination check).
- **Operator BROWSER witness is BINDING** (theme toggle + expand-across-refresh are browser-only HTMX/JS surfaces — memory `feedback_visual_gate_both_render_and_browser`): drive the SCAFFOLD's comms GUI in a real browser — toggle dark/light (persists across reload, no flash), expand a message and confirm it STAYS open across the 5s auto-refresh. Witness on the scaffold, not swing.
- **Merged-head no-false-green** full scaffold suite re-run is the binding green (in the harness-template repo).
- review-strong (gpt-5.5/high) + codex-auto-review (the scaffold is production-adjacent harness code).
- Worktree-isolated in the harness-template repo. Tear down any spawned scaffold comms_ui server at the gate (TaskStop-doesn't-kill).

## 5. Dispatch recommendation

- **Implementer cell:** `implementer-opus-high`. Rationale: the approach is settled (diff + port the generic mechanism), but it needs genericization judgment + the contamination guard + cross-repo work + browser-only surfaces. Not measurement-chain → not `-max`.
- **Orchestrator:** Opus xhigh. **Cross-repo: the swing orchestrator dispatches the implementer INTO `harness-template`** (worktree-isolated there); the implementer reads swing's comms_ui as the source-of-truth (cross-repo read) and edits + tests the scaffold.

## 6. Return report

**The ORCHESTRATOR posts the return report to `charc` (+ `operator` fyi) AFTER its own QA** (now via the orchestrator→charc inbox flow). CHARC code-QAs on disk in the harness-template repo: the generic mechanism ported (no swing branding/content — genericity gates green), B-11/B-13 present, B-14 hook (if added) mirrors swing's loop-safe pattern. The operator's BROWSER witness on the scaffold GUI is the binding gate before merge.
