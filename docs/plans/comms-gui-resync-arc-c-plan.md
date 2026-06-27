# G6 Arc C — Comms-GUI Re-Sync (swing -> scaffold) — Implementation Plan

**Status:** PLAN (writing-plans dispatch; no code/tests written here — this document specifies them).
**Brief:** `docs/comms-gui-resync-arc-c-commissioning-brief.md` (swing; CHARC-owned, SUB-TRIPWIRE).
**Source-of-truth:** swing `scripts/comms_ui.py` (read cross-repo; transcribe MECHANISM only).
**EXECUTES IN:** `C:\Users\rwsmy\harness-template` (the generic scaffold) — NOT swing. This plan
is a swing artifact (`docs/plans/`); every code/test change it specifies lands in the
harness-template repo.
**Accept gate:** the scaffold's stdlib `unittest` suite — `python -m unittest discover -s tests`
(from the harness-template repo root; README:106) — plus the operator BROWSER witness on the
SCAFFOLD GUI (binding).

---

## 0. Cross-repo framing (read first)

This is a CROSS-REPO arc. The implementer:
- READS swing `scripts/comms_ui.py` + `scripts/comms_stop_hook.py` + `scripts/comms_unread_hook.py`
  + `.claude/settings.json` as the source-of-truth (the proven mechanism).
- WRITES to the harness-template repo ONLY (scaffold `scripts/comms_ui.py`, a new
  `.claude/hooks/stop.py`, `.claude/settings.json`, and several scaffold tests).
- Touches NOTHING in swing (no swing-repo edit; this plan is the only swing artifact).
- The work executes in a harness-template worktree (`.worktrees/<name>` off `master`); see §7.

The scaffold is a CLEAN-ROOM generic harness. The binding constraint everywhere below is the
**contamination guard** (§5): port the reusable MECHANISM, never swing branding / colors / labels
/ copy / project-terms. The scaffold carries the B-9 genericity gates with executable teeth — a
swing-term leak into a CORE file FAILS the build. The plan calls out the exact tokens to strip per
ported surface.

---

## 1. Premise — re-grounded on disk 2026-06-27 (CONFIRMED)

Verified by reading both files in full and the scaffold's tests.

**Scaffold ALREADY HAS the orchestrator stack** (so Arc C does NOT port it):
- `BUS_ROLES = ("charc", "orchestrator")` — scaffold `comms_ui.py:73`.
- `LAUNCH_ROLES = ("both", "charc", "orchestrator")` — `:78`.
- `_orchestrator_inbox_messages` (flat aggregate) — `:170`; `_orchestrator_read_messages` `:189`;
  `_bus_messages` dispatch `:202`.
- `/orchestrator-bootstrap` route `:608`; `/launch` enum-gate `:578`.
- Provenance: harness-template `5f3440c` ("Task I.1-I.2 -- optional comms_ui ... charc+orchestrator
  bus ... role-launch + bring-up surface").

**Scaffold LACKS exactly the GUI-polish fixes (the Arc-C delta):**
- **B-11 dark-theme — ABSENT.** No `theme-toggle` button, no `toggleTheme`/`_applyThemeIcon` JS, no
  no-flash head script, no `[data-theme="dark"]`; the scaffold CSS (`comms_ui.py:288-310`) uses raw
  hex literals, not CSS custom properties. (`grep` for `toggleTheme`/`theme-toggle`/`data-theme` in
  the scaffold returns nothing.)
- **B-13 expand-preserve — ABSENT.** The scaffold renders the `data-key="{{ m.filename }}"`
  *attribute* (e.g. inbox `:359`, bus `:384`) but NOT the preserve-across-the-5s-poll JS (no
  `htmx:afterSwap` re-open, no `openKeys` live set).

**Scaffold has NO Stop hook (B-14 is real work, not a no-op).** `.claude/settings.json` registers
exactly `SessionStart` / `UserPromptSubmit` / `SessionEnd` (no `Stop`). `.claude/hooks/` holds
`session_start.py`, `user_prompt_submit.py`, `session_end.py` — no `stop.py`.

**Orchestrator-bus MODEL divergence exists but is OUT OF SCOPE (§5.2).** Scaffold
`_orchestrator_inbox_messages` returns a flat `list[Message]`; swing's returns a per-gen-grouped
`list[dict]`. This is a comms-bus DESIGN difference, not GUI polish. Arc C does NOT touch it. The
expand-preserve JS keys on `data-key` and the scaffold's flat `data-key` attributes already exist,
so the port works on the scaffold's bus unchanged.

**Git state:** harness-template on branch `master`, clean working tree, HEAD `db644b4`.

---

## 2. The diff — enumerated GENERIC GUI-polish deltas (swing CURRENT -> scaffold)

A surgical diff of the scaffold's GUI (the `_PAGE`/pane templates + the CSS-in-`comms_ui.py`)
against swing's CURRENT `comms_ui.py` surfaces exactly these GENERIC deltas. Everything NOT listed
here is identical-or-deliberately-genericized in the scaffold and is left untouched.

| # | Delta | Swing source | Scaffold today | Swing fix commit(s) |
|---|-------|-------------|----------------|---------------------|
| D1 | No-flash theme head script (localStorage `comms-theme`) | swing `:332-343` | absent | `7b7dc169c` |
| D2 | `_applyThemeIcon` + `toggleTheme` + DOMContentLoaded icon sync | swing `:344-376` | absent | `7b7dc169c` base; `5df335d4` moon/sun icon parity |
| D3 | Expand-preserve live-set head script (`openKeys` + `htmx:afterSwap`) | swing `:388-413` | absent | `30c47081e` (intro) + `60d80467b` (core logic) + `ad44dbc6f` (bind to `document` not `body`) |
| D4 | Themed CSS custom properties: `:root` light vars + `:root[data-theme="dark"]` override (replaces raw hex) | swing `:437-516` | raw hex `:288-310` | `7b7dc169c` base; `991430c8` (`color-scheme` native-control theming) |
| D5 | `.theme-toggle` CSS + `h1 { display:flex; align-items:baseline; gap:0.8rem }` (toggle layout) | swing `:485,487-488` | absent | `7b7dc169c` |
| D6 | `details.msg .age` CSS rule (the bus stale-age span is currently unstyled in the scaffold) | swing `:504` | missing (span rendered, no rule) | `7b7dc169c` |
| D7 | Toggle `<button id="theme-toggle">` in `<h1>` | swing `:519-522` | `<h1>comms</h1>` `:313` | `7b7dc169c` base; `5df335d4` icon |

D4/D5/D6 ship together as ONE replacement of the scaffold's `<style>` block (swing's themed block
covers all of the scaffold's existing selectors PLUS the new theme vars / `.theme-toggle` / `h1` /
`.age`). D1+D2+D7 are the dark-theme toggle (B-11). D3 is expand-preserve (B-13).

**NOT a GUI-polish delta — do NOT port (verified during the diff):**
- swing's per-gen-grouped orchestrator bus (`_orchestrator_inbox_messages` grouped list, bus
  template `generation {{ g.sid }}`, `data-key="orch:{{ g.sid }}:{{ m.filename }}"`) — the OUT
  bus-MODEL difference (§5.2).
- swing's "Directors" strip naming / `directors-flash` / `/directors/launch` / `LAUNCHER =
  start_directors.ps1` / compose `rd` checkbox — the scaffold already genericized these to "Roles"
  / `launch-flash` / `/launch` / `launch_role.ps1` / `orchestrator` checkbox. The
  `copyOrchestratorBootstrap` JS already targets `launch-flash` in the scaffold (`:270`) and is left
  untouched. The htmx `responseHandling` override is byte-identical in both — untouched.

---

## 3. Task breakdown

Three logical units, each its own commit (TDD: failing test -> see fail -> minimal impl -> see
pass -> commit). Commits land in the harness-template worktree with BARE git from the worktree cwd.

> **Convention note:** the scaffold's comms_ui tests are gated `@unittest.skipUnless(_HAS_WEB, ...)`
> (FastAPI TestClient). The executing implementer MUST install the `[web]` extra
> (`pip install -e ".[web]"`) in the harness-template venv so the new GUI tests RUN, not skip — a
> skipped gate is a silent hole. Confirm `_HAS_WEB` is True before claiming green.

### Task A — B-11 dark-theme toggle (the GUI delta: D1, D2, D4, D5, D6, D7)

**File:** harness-template `scripts/comms_ui.py` (the `_PAGE` template constant only).

**Change (port the MECHANISM, genericized):**
1. Add the **no-flash theme head script** (D1) into `_PAGE`'s `<head>`, BEFORE the htmx `<script
   src>` (so it runs before first paint): the `localStorage.getItem("comms-theme") === "dark"` ->
   `document.documentElement.dataset.theme = "dark"` IIFE, wrapped in try/catch (localStorage may
   be unavailable -> stay on the light default).
2. Add `_applyThemeIcon(isDark)` + `toggleTheme()` + the `DOMContentLoaded` icon-sync (D2): flip
   `data-theme` on `<html>`, persist/remove the `comms-theme` key, swap the moon/sun glyph + the
   `aria-label`.
3. Replace the scaffold's raw-hex `<style>` block with swing's **themed custom-property** block (D4
   + D5 + D6): `:root { color-scheme: light; --bg/--fg/--posted-fg/... }` light defaults +
   `:root[data-theme="dark"] { color-scheme: dark; ... }` override; the existing selectors
   (`body`, `details.msg`, `.flash`, `.empty`, `.strip`, etc.) re-pointed at `var(--...)`; PLUS the
   new `.theme-toggle`, `h1 { display:flex; align-items:baseline; gap:0.8rem }`, and
   `details.msg .age { color: var(--stale-fg); font-size:0.8rem }` rules.
4. Add the toggle **button** in `<h1>` (D7): `<button type="button" id="theme-toggle"
   class="theme-toggle" onclick="toggleTheme()" aria-label="Switch to dark theme">` with the moon
   glyph as initial content.

**Genericization (CONTAMINATION GUARD — load-bearing, §5):**
- KEEP the localStorage key `comms-theme` — it is already GENERIC (no swing project-term). Do NOT
  invent a swing-specific key. (Confirm-only decision flagged in §6.)
- STRIP swing-specific provenance comments from the ported JS: swing's `:344-348` references "the
  swing web theme control's iconography (base.html.j2)" and "17-D.2 follow-up ... icon parity with
  swing web" — these carry the forbidden term **swing** (the B-9 guard FAILS on `\bswing\b` in a
  CORE file) and swing-internal provenance. Replace with a generic comment (e.g. "a moon glyph when
  light is active, a sun when dark is; aria-label flipped to match. Swap on toggle AND on load").
- STRIP the swing lock reference: swing's head-script comment `:336` says "the stateless-server
  invariant + L2". The scaffold has NO L2 lock (its locks are L1/L3/L4/L5 — there is no `swing/`
  dir to protect). Drop "+ L2" -> keep "the stateless-server invariant".
- The CSS block itself carries NO swing term (verified) — port as-is. The icon glyphs (moon/sun
  emoji) are HTML page content (UTF-8), not stdout — the ASCII-stdout gotcha does NOT apply; keep
  them.
- aria-label copy ("Switch to dark theme" / "Switch to light theme") is generic UI copy — keep.

**Tests (add to `tests/test_comms_ui.py`, class `CommsUiTest`, stdlib unittest):**
- `test_theme_toggle_control_renders`: GET `/`; assert the response text contains
  `id="theme-toggle"` AND `onclick="toggleTheme()"`.
  - PRE-FIX: the scaffold `<h1>comms</h1>` has no button -> assertion FAILS.
  - POST-FIX: button present -> PASSES.
- `test_persisted_theme_preference_head_script_present`: GET `/`; assert the text contains
  `localStorage.getItem("comms-theme")` AND `function toggleTheme()` AND
  `:root[data-theme="dark"]`.
  - PRE-FIX: none of these strings exist in the scaffold page -> FAILS.
  - POST-FIX: all present -> PASSES.
  - Distinguisher confirmed: `grep -c 'comms-theme\|toggleTheme\|data-theme' scaffold/comms_ui.py`
    == 0 today.

### Task B — B-13 expand-preserve (the GUI delta: D3)

**File:** harness-template `scripts/comms_ui.py` (the `_PAGE` template constant only).

**Change:** add the **expand-preserve live-set head script** (swing `:388-413`) into `_PAGE`'s
`<head>`: an IIFE holding `var openKeys = new Set();`, a capture-phase `toggle` listener on
`document` (the `toggle` event does NOT bubble) that adds/removes `d.dataset.key` for
`details.msg[data-key]` rows, and an `htmx:afterSwap` listener on `document` that re-opens every
`details.msg[data-key]` whose key is in `openKeys`. Bind to `document` (NOT `document.body`, which
is null in `<head>`).

**Genericization:** the swing block carries NO swing project-term (verified — comments reference
only `data-key`, "the message filename", "the 5s poll swap", htmx). Port the mechanism verbatim
(genericized = unchanged here; nothing swing-specific to strip). It operates on the scaffold's
EXISTING flat `data-key` attributes — no template/markup change needed, and the OUT-of-scope bus
MODEL is untouched.

**Tests (add to `tests/test_comms_ui.py`, class `CommsUiTest`):**
- `test_expand_preserve_live_set_js_present`: GET `/`; assert the text contains `htmx:afterSwap`
  AND `details.msg[data-key]` AND `openKeys`.
  - PRE-FIX: the scaffold page has no preserve script (the `data-key` *attribute* exists but the
    re-open JS does not) -> FAILS.
  - POST-FIX: present -> PASSES.
  - Distinguisher confirmed: `grep -c 'htmx:afterSwap\|openKeys' scaffold/comms_ui.py` == 0 today;
    asserting the JS (not merely the `data-key` attribute) is what makes the test distinguish.

### Task C — B-14 Stop hook (continuous-ops bridge; DISTINCT surface, separate commit)

**New file:** harness-template `.claude/hooks/stop.py` (stdlib-only CORE hook).

**Design (port swing's `scripts/comms_stop_hook.py` MECHANISM, ADAPTED to the scaffold's hook
architecture):**
- The scaffold's unread-notice machinery lives in `.claude/hooks/user_prompt_submit.py`
  (`unread_notice(role, root, session_id)`, `COMMS_ROLES`, `ROLE_ENV`, `_comms_root_from_file`),
  NOT in a swing-style `comms_unread_hook.py`. The Stop hook REUSES it via a sibling import (the
  same first-party sibling-import pattern the scaffold's hooks already use), so there is NO new
  shared module and no logic duplication. `user_prompt_submit` is already in
  `tests/test_dependency_posture.py::_FIRST_PARTY`, so the AST stdlib-only belt accepts the import.
- **Role gating (recommended V1 — mirrors swing's director-only posture):** a module-level
  `STOP_HOOK_ROLES = ("charc",)`. Read the role from the scaffold's `ROLE_ENV` (value
  `"HARNESS_ROLE"`, imported — NOT swing's `SWING_ROLE`). If the role is not in `STOP_HOOK_ROLES`,
  SILENT no-op exit 0 (does nothing in any orchestrator / plain / ad-hoc session). `charc` is a
  SINGULAR_INBOX_ROLE, so `unread_notice("charc", root, None)` resolves `comms/charc/inbox` and
  ignores `session_id` — EXACTLY mirroring swing's shared-inbox director gating, with NO
  per-generation session_id complexity. (Whether to ALSO fire for `orchestrator` — which would need
  session_id resolved from the Stop payload for its per-generation inbox — is an open CHARC decision;
  see §6. Default: defer; `("charc",)` only.)
- **Loop-safety (load-bearing, verbatim-genericized from swing):** read the Stop-hook JSON payload
  from stdin as RAW BYTES, decode `utf-8-sig` (strip a BOM), parse `stop_hook_active`. Block
  (continue) ONLY when there is unread AND `stop_hook_active` is false — so a turn gets AT MOST ONE
  continuation; a stuck inbox can NEVER loop. On ANY stdin read/decode/parse failure, default the
  flag TRUE (allow stop — the safe direction).
- **On block:** print `{"decision":"block","reason":<notice>}` (the Stop-hook block protocol) with
  a generic reason string (the drain instruction; NO swing terms, NO "B-14" provenance, NO commit
  SHAs). ASCII output (the Windows cp1252 stdout gotcha).
- **Always exit 0** on any error (a hook failure must NEVER trap the agent in a non-stoppable
  state).

**Wiring:** add a `Stop` event to harness-template `.claude/settings.json` mirroring the scaffold's
EXISTING portable convention (NOT swing's machine-absolute path): `"command": "python
\"$CLAUDE_PROJECT_DIR/.claude/hooks/stop.py\""`. The existing `_comment` already documents the
`python`->`python3` substitution — no change needed there.

**Genericization (CONTAMINATION GUARD):** `.claude/hooks/stop.py` is a CORE file (scanned by the
genericity guard; NOT instance surface). It MUST carry zero swing terms:
- env var `SWING_ROLE` -> the scaffold's `ROLE_ENV` (`HARNESS_ROLE`) — required for CORRECTNESS
  (the scaffold sets `HARNESS_ROLE`, not `SWING_ROLE`) AND cleanliness.
- swing docstring/comment terms ("swing", "DIRECTOR_ROLES", commit SHAs, "B-14") -> generic prose.
- import from the scaffold's `user_prompt_submit` (first-party), NOT swing's `comms_unread_hook`.

**Existing-test updates this NEW file forces (each with its pre/post distinguisher):**
1. `_corefiles.py::CORE_RELPATHS`: add `".claude/hooks/stop.py"`.
   - Effect: the AST belt (`test_dependency_posture.py::test_ast_belt_core_imports_are_stdlib_only`)
     now scans stop.py and enforces stdlib-only + first-party imports — the intent-correct
     enforcement. `test_no_core_file_is_instance_surface` iterates `CORE_RELPATHS` and asserts none
     classifies as instance surface; `.claude/hooks/stop.py` is NOT instance surface
     (`is_instance_surface` exempts only `.claude/agents/implementer-*.md` cells + docs patterns +
     APPLICATION/briefs) -> stays GREEN.
   - PRE/POST: not a count assertion; this addition makes the AST belt cover stop.py (without it the
     new hook would be silently un-scanned for the stdlib-only posture).
   - NOTE: `test_dependency_posture.py::_SUBPROCESS_PROBE` has a SEPARATE hardcoded `core_rel` list
     (`:114-119`) that does NOT auto-derive from `CORE_RELPATHS`. The AST belt is sufficient
     stdlib-only enforcement; adding stop.py to the subprocess probe is OPTIONAL (the probe imports
     + exercises a representative subset; stop.py's `main()` reads stdin so it is not trivially
     exercisable there). Recommend: AST belt only (add to `CORE_RELPATHS`); leave the probe list
     unchanged. Flag the non-auto-derived probe list in the return report.
2. `tests/test_manifest_accounting.py`:
   - add `".claude/hooks/stop.py"` to `SHIPPED_MANIFEST` (it is a shipped CORE hook, not a
     support/tests file).
   - update `test_manifest_count_is_nineteen` -> `_is_twenty` (assert `len(SHIPPED_MANIFEST) == 20`)
     and its message ("18 base + charc-state.md + stop.py" = 20).
   - PRE-FIX distinguisher: adding stop.py to the tree WITHOUT adding it to `SHIPPED_MANIFEST` makes
     `test_every_tracked_file_is_manifest_or_support` FAIL (stop.py is unaccounted — not manifest,
     not support, not tests/, not instance surface). Adding it to `SHIPPED_MANIFEST` then makes the
     count test FAIL at `19 != 20`. Both resolve only by the manifest add + the count bump -> the
     edits distinguish.
3. `tests/test_hooks_wiring.py::SettingsJsonTest`:
   - `test_three_hook_events_registered`: the event set becomes `{"SessionStart", "UserPromptSubmit",
     "SessionEnd", "Stop"}`. Update the asserted set (and rename the test, e.g.
     `test_four_hook_events_registered`).
   - `test_each_event_points_at_its_hook_script`: add `"Stop": "stop.py"` to the mapping.
   - PRE-FIX distinguisher: adding the `Stop` entry to `settings.json` makes
     `test_three_hook_events_registered` FAIL (set now has 4 members, asserted 3); the mapping test
     has no `Stop` key so it would not catch the wiring -> both edits are load-bearing.
   - RECOMMENDED: extend `HOOKS = (...)` to include `"stop.py"` so the portability tests
     (`test_each_hook_reads_harness_role_and_exits_zero_on_malformed`,
     `test_each_hook_exits_zero_with_no_role`) cover the Stop hook's exit-0 discipline. The Stop hook
     passes both: `{}` + no role -> no-op exit 0; malformed stdin + `HARNESS_ROLE=orchestrator` ->
     orchestrator is not in `STOP_HOOK_ROLES` -> exit 0 (and even for `charc`, a garbled payload
     defaults `stop_hook_active` TRUE -> allow stop -> exit 0). Do NOT add stop.py to
     `test_sibling_import_failure_still_exits_zero`'s list unless the Stop hook's sibling import is
     guarded the same way `user_prompt_submit` guards its `from session_start import ...` (it
     should be — mirror that guard so a broken `user_prompt_submit` degrades the Stop hook to a
     logged exit-0 no-op rather than a nonzero crash that traps the agent). If the guard is added,
     include stop.py there too.

**Tests (new file `tests/test_stop_hook.py`, stdlib unittest, NO `[web]` needed — mirrors swing's
stop-hook decision matrix):**
- `test_non_comms_role_is_silent_noop`: run `stop.py` with `HARNESS_ROLE` unset (or
  `=orchestrator`, given the `("charc",)` default) + any stdin -> returncode 0, empty stdout.
  - PRE-FIX: stop.py does not exist -> the subprocess invocation errors. POST-FIX: exit 0, no
    block.
- `test_charc_unread_first_stop_blocks`: seed a `comms/<tmp>/charc/inbox/*.md` over a tmp comms
  root (raw write or via the scaffold's `role_mail.post_message`), set `HARNESS_ROLE=charc`, feed
  stdin `{"stop_hook_active": false}` -> stdout parses as JSON with `decision == "block"` and a
  non-empty `reason`; returncode 0.
  - PRE-FIX: no stop.py -> fails. POST-FIX: blocks once.
  - NOTE: the hook resolves the comms root from `user_prompt_submit._comms_root_from_file()` (file-
    relative). To test over a tmp tree without polluting the real `comms/`, follow swing's testable
    seam: the behavior fns take the root explicitly OR the test monkeypatches the root resolver.
    Specify a small testable seam in stop.py (a `_block_reason(role, root, session_id)` /
    `handle_stop(payload, env, root)` split, like user_prompt_submit's `handle_user_prompt_submit`)
    so the unread-block path is unit-testable over `tmp_path` AND the subprocess wiring tests
    (test_hooks_wiring) still exercise the real entry point. (This split must itself stay stdlib-only
    + carry no swing term.)
- `test_charc_stop_hook_active_true_allows_stop`: same seed, stdin `{"stop_hook_active": true}` ->
  returncode 0, NO block emitted (the single-continuation loop guard).
  - PRE-FIX path under BOTH branches: compute the assertion under a NAIVE impl that ignores
    `stop_hook_active` — it would block again -> the test FAILS that impl; the loop-guarded impl
    PASSES. Distinguisher confirmed (the test would not pass a no-loop-guard implementation).
- `test_malformed_stdin_allows_stop`: `HARNESS_ROLE=charc`, stdin `"not json"` -> returncode 0, no
  block (safe-default-allow-stop).
- `test_empty_inbox_allows_stop`: `HARNESS_ROLE=charc`, empty comms tree, stdin
  `{"stop_hook_active": false}` -> returncode 0, no block.

All new test files under `tests/` are scanned by the genericity guard (they are NOT in
`SELF_EXCLUDE_RELPATHS`), so `test_stop_hook.py` MUST carry no forbidden term (no "swing", no
finance tickers).

---

## 4. Full-suite gate (before the Codex review and at end-of-run)

Per the recipe, run the WHOLE scaffold suite to GREEN before the review and again at the end:
```
python -m unittest discover -s tests        # from the harness-template repo root
```
(with the `[web]` extra installed so the comms_ui tests RUN, not skip.) The binding green is the
merged-head no-false-green re-run of the FULL scaffold suite in the harness-template repo. The B-9
genericity gates (`test_whole_tracked_tree_is_clean`, `test_core_files_are_not_instance`, the
instance-surface predicate tests, `test_vocab_bans_are_core_only`) are the contamination check —
they MUST stay green (a swing-term leak into a CORE file trips them).

---

## 5. Contamination guard (§5.1 of the brief) — per ported surface

The scaffold's B-9 guard FAILS on `\bterm\b` (case-insensitive) for the FORBIDDEN_TERMS set —
which includes **swing**, **trading**, **trade(s)**, **finviz**, **schwab**, **sqlite**, **pytest**,
**ruff**, **chess**, **coa**, **finance**, **ticker**, **yfinance** — and the FORBIDDEN_TICKERS
**SPY/QQQ/NDX/SPX/RUT** (case-sensitive uppercase), in any CORE file. Every file Arc C touches
(`scripts/comms_ui.py`, `.claude/hooks/stop.py`, `.claude/settings.json`, the test files) is CORE
(none is instance surface). Per-surface calls:

- **Dark-theme JS (Task A):** STRIP "swing web" + "base.html.j2" + "17-D.2" provenance comments
  (carry `swing`); drop the "+ L2" lock reference (no L2 in the scaffold). KEEP the generic
  localStorage key `comms-theme`, the generic aria-labels, the moon/sun glyphs.
- **Themed CSS (Task A):** the swing CSS block carries no forbidden term — port as-is.
- **Expand-preserve JS (Task B):** no forbidden term in the swing block — port as-is.
- **Stop hook (Task C):** `SWING_ROLE` -> `ROLE_ENV`/`HARNESS_ROLE`; strip "swing"/"DIRECTOR_ROLES"
  /commit-SHA/"B-14" provenance from docstring + comments + the reason string; import the scaffold's
  `user_prompt_submit`, not swing's `comms_unread_hook`.
- **Test files:** assert on GENERIC rendered markup (`theme-toggle`, `toggleTheme`, `comms-theme`,
  `data-theme`, `htmx:afterSwap`, `openKeys`, `decision`/`block`) — none is a forbidden term. Do
  not paste swing copy into a test.

### 5.2 OUT-of-scope — STOP-and-flag if a fix would cross (do NOT work around)

- **The orchestrator-bus MODEL difference** (scaffold flat `list[Message]` vs swing per-gen-grouped
  `list[dict]`; §1). A future scaffold item, NOT GUI polish. Arc C does not touch
  `_orchestrator_inbox_messages` / the bus template's grouping / its `data-key` scheme.
- **Swing STYLING / BRANDING / CONTENT / CONFIG / copy / project-terms** — the contamination guard.
  Transcribe the reusable mechanism only.
- **Any `swing/` or swing-repo touch** — Arc C is harness-template-ONLY (this plan is the only swing
  artifact).
- **Any schema / new dependency / new module** — none is introduced. (`.claude/hooks/stop.py` is a
  new FILE, not a new shared module — it reuses `user_prompt_submit`; it adds NO third-party dep.)

If any required fix would cross one of these, STOP and flag it in the return report rather than
working around it.

---

## 6. Open questions / design decisions for CHARC (plan-stage review)

1. **`STOP_HOOK_ROLES` membership (the main genericization call).** Recommended V1: `("charc",)` —
   mirrors swing's director-only gating, uses the shared `charc/inbox`, needs no session_id.
   Question: should the Stop hook ALSO fire for `orchestrator`? The scaffold's orchestrator is a
   first-class agent session (unlike swing's operator-driven orchestrator). Including it would
   deliver continuous-ops to the orchestrator generation BUT requires resolving `session_id` from
   the Stop payload for the per-generation inbox (`unread_notice` needs it for non-singular roles).
   Default: DEFER orchestrator inclusion to a follow-up; ship `("charc",)`.
2. **localStorage key name.** Recommended: keep swing's `comms-theme` verbatim — it is already
   generic (no swing project-term) and the brief's "do NOT hardcode a swing-specific string" is
   satisfied. Confirm-only.
3. **Stop-hook reason copy.** A generic drain-instruction reason string (no "B-14", no commit SHA,
   no "swing"). Confirm the phrasing is acceptable as generic harness copy.
4. **Test placement.** GUI theme/expand tests -> existing `tests/test_comms_ui.py::CommsUiTest`
   (already `@skipUnless(_HAS_WEB)`); Stop-hook decision-matrix tests -> a new
   `tests/test_stop_hook.py` (stdlib, no `[web]`). Confirm this split.
5. **`HOOKS` portability coverage.** Recommended: add `stop.py` to `test_hooks_wiring.py::HOOKS` so
   the exit-0 portability discipline covers it; mirror `user_prompt_submit`'s guarded sibling-import
   so the Stop hook degrades to exit-0 on a broken import. Confirm.

---

## 7. Executing-phase cross-repo mechanics (for the executing implementer)

- **Worktree (in harness-template, NOT swing):** `git worktree add -b <name>
  C:\Users\rwsmy\harness-template\.worktrees\<name> master` (base is harness-template `master`).
  Work from the worktree cwd; commit with BARE git from that cwd (NOT `git -C` — the harness
  allowlist covers the bare `git add`/`git commit` form only).
- **Editable install:** `pip install -e ".[web]"` in the harness-template venv so the
  `@skipUnless(_HAS_WEB)` comms_ui tests RUN (confirm `_HAS_WEB` True — a skipped gate is a hole).
- **Accept gate (exact command, from the worktree root):** `python -m unittest discover -s tests`.
  This is the binding green; re-run on the merged head (no-false-green) in the harness-template repo.
- **Commits:** TDD, one per task (A, B, C) + the existing-test-update commits folded into Task C's
  commit (they are the same logical change). Conventional messages; ZERO `Co-Authored-By`; no
  `--no-verify`; no amend; final `-m` paragraph plain prose. Task C is a DISTINCT surface from the
  GUI -> its own commit.
- **Codex review (review-strong + codex-auto-review — production-adjacent harness code):** the
  worktree `.git` is a FILE that WSL git cannot resolve -> pre-generate the diff on the WINDOWS
  side (`git diff -U8 master..HEAD > .codex-diff.txt`, run in the harness-template worktree) and
  feed it via stdin with `--skip-git-repo-check` (see the recipe §3). Because `codex-auto-review`'s
  `--commit/--base` form cannot run against the worktree's unresolvable `.git`, SUBSTITUTE `codex
  exec` at `-c model_reasoning_effort=high` over the diff bundle (the recipe's effort=none
  disqualifier corrected). For the production-code repo-access pass, include the surrounding
  reference graph in the stdin bundle (the scaffold `comms_ui.py` head + the
  `user_prompt_submit.py` unread-notice machinery the Stop hook imports) so the review is not
  diff-blind to the import contract. Run to `NO_NEW_CRITICAL_MAJOR`; persist every round to
  `.copowers-findings.md`.
- **Server teardown:** if a scaffold `comms_ui` server is spawned for the browser witness, tear it
  down at the gate (TaskStop does NOT kill a detached uvicorn — find the PID on the bound port,
  Stop-Process -Force, verify the port is free).
- **Binding gate:** the operator BROWSER witness on the SCAFFOLD GUI (not swing) — toggle dark/light
  (persists across reload, NO flash), expand a message and confirm it STAYS open across the 5s
  auto-refresh. Byte/render tests are necessary but NOT sufficient for these browser-only HTMX/JS
  surfaces (memory `feedback_visual_gate_both_render_and_browser`).

---

## 8. Summary of files touched (all in harness-template; ZERO swing touch)

| File | Change | Task |
|------|--------|------|
| `scripts/comms_ui.py` | `_PAGE`: + no-flash theme script, + `toggleTheme`/`_applyThemeIcon`, + expand-preserve script, + toggle button in `<h1>`, themed CSS custom-property block (replaces raw hex; + `.theme-toggle`/`h1`/`.age`) | A, B |
| `.claude/hooks/stop.py` | NEW stdlib-only Stop hook (genericized port of swing's `comms_stop_hook.py`; reuses scaffold `user_prompt_submit`) | C |
| `.claude/settings.json` | + `Stop` event (portable `$CLAUDE_PROJECT_DIR` path) | C |
| `tests/_corefiles.py` | + `.claude/hooks/stop.py` to `CORE_RELPATHS` | C |
| `tests/test_manifest_accounting.py` | + stop.py to `SHIPPED_MANIFEST`; count 19 -> 20 | C |
| `tests/test_hooks_wiring.py` | + `Stop` event + mapping; (rec.) + stop.py to `HOOKS` | C |
| `tests/test_comms_ui.py` | + 2 GUI tests (theme toggle render + persisted-pref head script; expand-preserve JS) | A, B |
| `tests/test_stop_hook.py` | NEW: Stop-hook decision-matrix tests | C |
