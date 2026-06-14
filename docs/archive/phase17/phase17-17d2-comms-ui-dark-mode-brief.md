# Phase 17 — 17-D.2: Dark mode for the comms mail UI (enhancement)

**Audience:** A fresh Claude Code instance, no prior context. A self-contained presentation enhancement to ONE file (`scripts/comms_ui.py`). No new dependency, no new route, no schema, no swing/ change.

**Mission:** Add a dark-mode theme + a client-persisted toggle to the comms mail UI (the on-demand localhost FastAPI/HTMX view at 127.0.0.1:8765). Light stays the default; the operator can switch to dark and the choice persists across reloads.

**Expected duration:** ~45–60 min including the visual gate.

---

## §0 Read first
- [`scripts/comms_ui.py`](../scripts/comms_ui.py) — the whole single-file app. The presentation lives entirely in the embedded `_PAGE` template: the `<style>` block (≈L315-341, all hardcoded light colors) and the three inline `<head>` `<script>` blocks (the pattern you'll mirror for the theme script). The `<body>` opens with `<h1>comms</h1>` (≈L344) — the toggle goes in that header area. Panes refresh via HTMX `hx-get ... every 5s` `hx-swap="innerHTML"` (L346/353/360).
- [`tests/scripts/test_comms_ui.py`](../tests/scripts/test_comms_ui.py) — the canonical test file to extend (uses `create_app(comms_root=tmp_path, ...)` + a TestClient).
- The module docstring's **hard locks L1–L5** (L8-14) and the OriginGuard — your change must not touch any of that logic (it's pure presentation).

**Skill posture:** TDD for the structural assertions; a light standalone `copowers:review` to convergence (persist responses to a gitignored `.copowers-findings.md`). No brainstorm/writing-plans — scope is locked below.

---

## §1 Scope LOCK
- **`scripts/comms_ui.py` ONLY.** L2 hard lock: nothing under `swing/` is touched. No new file, no new dependency (no CSS framework, no JS lib — the existing inline-style + inline-script pattern is the model), **no new route** (the toggle is pure client-side; the server holds NO state — preserve that invariant; do NOT add a theme endpoint or cookie).
- Do NOT alter compose/ack/ack-all/launch/bootstrap logic, the OriginGuard, role_mail wiring, or any of L1–L5. Pure look-and-feel.
- ASCII-only in any server-console `print` (the cp1252 gotcha); page content is UTF-8 (unchanged).

## §2 Design (locked)
1. **CSS custom properties.** Refactor the `<style>` block so every color is a `var(--name)` defined on `:root` (light defaults), with a `:root[data-theme="dark"] { ... }` override block supplying the dark palette. Cover: page bg/fg, `h2`, `details.msg` border/bg, `.posted`/`.type`/`.from`/`.subject` text, the decision-request red accent (`#c0392b`/`#fdecea`), the stale orange (`#e67e22`), `pre.body` code bg, `.flash.ok`/`.flash.err`, `.strip`/`.empty` borders. Pick a readable dark palette (e.g. bg `#1e1e1e`, fg `#e0e0e0`, borders `#444`, code bg `#2a2a2a`); the decision-request + stale accents must stay legible on dark (tune the backgrounds, keep the hue).
   - **Why CSS variables on `:root`:** the 5s HTMX `innerHTML` swaps replace pane CONTENTS, which reuse the same classes (`.msg`, `.flash`, etc.); variables cascade from `:root`, so swapped-in fragments inherit the active theme automatically with zero per-fragment work. Verify this holds (the theme must survive a poll swap).
2. **Toggle control** in the header (near `<h1>comms</h1>`): a `<button type="button" onclick="toggleTheme()">` (label e.g. "Dark"/"Light" or a fixed "Toggle theme"). Pure client-side; no form, no POST (so OriginGuard is irrelevant to it).
3. **Persistence + no-flash apply.** Add an inline `<head>` `<script>` (mirroring the existing ones) that, AS EARLY AS POSSIBLE, reads `localStorage.getItem("comms-theme")` and sets `document.documentElement.dataset.theme` accordingly (so the page paints dark immediately, no flash-of-light). `toggleTheme()` flips `data-theme` on `<html>` and writes the new value to `localStorage`. Default (no stored value) = light.

## §3 Tests (TDD)
Extend `tests/scripts/test_comms_ui.py` with structural assertions on the rendered page (TestClient `GET /`): the page contains the theme-toggle button, the inline theme script (the `localStorage` "comms-theme" read + the `data-theme` set), and a `[data-theme="dark"]` CSS rule block. (JS toggle behavior is browser-only — these assert the wiring is present; the real confidence is the visual gate.) Keep every existing comms_ui test green (you only ADD markup; the panes/compose/ack/launch tests must not regress).

## §4 Binding conventions
- Conventional commit `feat(comms-ui): 17-D.2 — dark-mode theme + client-persisted toggle`; NO `Co-Authored-By`, NO `--no-verify`, NO amend; `git log -1 --format='%(trailers)'` empty.
- Fast suite `python -m pytest -m "not slow" -q` green on the merged head; ruff clean. (comms_ui lives in `scripts/`; confirm it's in the ruff/pytest scope the project already applies to scripts — match how `test_comms_ui.py` is currently run.)

## §5 Done criteria + GATE
- The theme + toggle + persistence land in `scripts/comms_ui.py`; structural tests added; all existing comms_ui tests green; ruff clean; trailers `[]`.
- `copowers:review` converged (responses persisted).
- **Operator-witnessed visual gate (BINDING):** the operator runs `python scripts/comms_ui.py`, toggles dark↔light, and confirms: (a) the whole page themes (inbox, bus, history, compose, directors strip); (b) the choice PERSISTS across a full reload (no flash-of-light on reload); (c) the theme SURVIVES a 5s pane poll (open the page, toggle dark, wait for a poll swap — panes stay dark); (d) decision-request red + stale orange remain legible on the dark background. This is the real confidence source.

## §6 Return report (final chat message ONLY)
Report: the commit SHA; the diff summary (style refactor to vars + the dark block + toggle button + theme script); the tests added; confirmation no L1–L5 logic / no route / no dependency was added and swing/ was untouched; the `copowers:review` verdict + persisted-findings path; the exact operator steps for the visual gate. Do NOT post to the mailbox or any director.
