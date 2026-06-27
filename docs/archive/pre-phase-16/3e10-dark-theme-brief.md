# 3e.10 — Dark theme dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Add a dark theme to the swing-trading web UI with a localStorage-persisted nav-bar toggle. CSS-variable-driven theme system; light is the default; operator opts in to dark via a nav-bar button. Charts stay light (V1; out of scope to regenerate per theme).

**Expected duration:** ~2-4 hr implementation + ~30-45 min dispatch overhead (worktree + TDD + adversarial review). Total ~2.5-4.75 hr.

**Skill posture:**
- Invoke `superpowers:subagent-driven-development` directly (NOT via the `copowers:executing-plans` wrapper).
- DO NOT invoke `superpowers:writing-plans` or `copowers:brainstorming` — design is locked in §0.3 below.
- Adversarial review via `copowers:adversarial-critic` after task families land. Iterate to NO_NEW_CRITICAL_MAJOR. Expected 1-2 Codex rounds (small surface; CSS refactor + minimal JS; main risks are FOUC, localStorage XSS via untrusted theme value, and accessibility).

---

## §0 Read first

### §0.1 Backlog entry
- `docs/phase3e-todo.md` §3e.10 (Dark theme — design locked in §0.3 below per orchestrator + operator in-thread design lock 2026-05-10)

### §0.2 Code surface

**Existing surfaces (read-only context):**

- `swing/web/static/app.css` — 117 lines / 31 color references. Single stylesheet for the entire app. Refactor target.
- `swing/web/templates/base.html.j2` — base layout with the `<nav class="topbar">` element at lines 23-31; 6 existing links (Dashboard / Watchlist / Journal / Reviews / Pipeline / Config). Toggle button gets added at the right end.
- `swing/web/templates/partials/` — many partials inheriting CSS classes from app.css; their rendering is theme-driven indirectly via the shared CSS variables.
- All page templates (`dashboard.html.j2`, `watchlist.html.j2`, `journal.html.j2`, `reviews_pending.html.j2`, `pipeline.html.j2`, `config.html.j2`, `cadence_complete.html.j2`, `review.html.j2`, `error.html.j2`, `page_error.html.j2`, `trades/*.html.j2`) — render via shared CSS; no per-template theme overrides expected.

**New surfaces this dispatch creates:**

- `app.css` modifications: add `:root` CSS variable definitions for ALL colors currently hardcoded; replace all hardcoded color values with `var(--*)` references; add `body.dark` block with dark-theme variable overrides.
- `base.html.j2` modifications: add toggle button at right end of `<nav class="topbar">`; add small inline `<script>` block (or `<script src="/static/theme.js">` if implementer prefers external) for localStorage R/W + class toggling. Script must run BEFORE body render to prevent FOUC.
- New static asset (optional, implementer's call): `swing/web/static/theme.js` if external script preferred over inline.

### §0.3 LOCKED DESIGN DECISIONS (DO NOT re-litigate)

Locked by orchestrator + operator in-thread design lock 2026-05-10:

1. **Persistence: localStorage only.** Key name: `swing-trading-theme` (string). Value: `"light"` or `"dark"`. No backend coupling. No cookies. No Phase 5 user-config integration. Operator-locked vs server-side + vs hybrid.

2. **Toggle placement: nav bar, right end.** Add a `<button>` element AFTER the `Config` link inside `<nav class="topbar">`. Button is small + visually subtle.

3. **Toggle UI:** single button with theme-aware emoji + accessible label:
   - When current theme = `light`: button shows `🌙` (moon — "switch to dark"); aria-label `"Switch to dark theme"`
   - When current theme = `dark`: button shows `☀️` (sun — "switch to light"); aria-label `"Switch to light theme"`
   - Button has `id="theme-toggle"` for JS hookup
   - On click: read current theme, flip, write to localStorage, update DOM (toggle `dark` class on `<body>`), update button text + aria-label

4. **Default theme: light.** Operator opts in to dark. Do NOT use `prefers-color-scheme: dark` media query for the default. Operator-locked.

5. **CSS variable naming convention:** semantic tokens, not appearance tokens.
   - `--bg` (page background)
   - `--bg-elevated` (cards / table rows / modals)
   - `--bg-muted` (disabled / placeholder backgrounds)
   - `--fg` (primary text)
   - `--fg-muted` (secondary text / `.muted` class)
   - `--border` (table borders / dividers)
   - `--accent` (primary action color; links; submit buttons)
   - `--accent-hover` (hover state for accent)
   - `--badge-bullish-bg`, `--badge-bullish-fg` (weather Bullish + state-managing)
   - `--badge-caution-bg`, `--badge-caution-fg` (weather Caution + state-pending)
   - `--badge-bearish-bg`, `--badge-bearish-fg` (weather Bearish + state-stop_hit)
   - `--state-entered-bg`, `--state-entered-fg` (Phase 7 trade state badges; one pair per state)
   - `--state-managing-bg`, `--state-managing-fg`
   - `--state-partial_exited-bg`, `--state-partial_exited-fg`
   - `--state-closed-bg`, `--state-closed-fg`
   - `--state-reviewed-bg`, `--state-reviewed-fg`
   - `--badge-update-today-bg`, `--badge-update-today-fg` (3e.5 badge; ✓ logged variant)
   - `--badge-update-needed-bg`, `--badge-update-needed-fg` (3e.5 badge; ⚠ pending variant)
   - `--field-error-bg`, `--field-error-fg` (form validation errors)
   - `--banner-degraded-bg`, `--banner-degraded-fg` (degraded-state banner)
   - `--stale-fg` (stale-price `(stale)` indicator)
   
   If any color in current `app.css` doesn't fit the above tokens, implementer adds a new semantic token (e.g., `--example-aside-bg` for the entry-form example asides). DO NOT introduce raw hex values in `body.dark` overrides; they must reference the same variable names defined under `:root`.

6. **CSS variable scope:** define under `:root { ... }` for light-theme defaults; override under `body.dark { ... }`. Reasoning: `:root` is the conventional cascade root for CSS variables; `body.dark` lets the toggle just flip a class on body without re-querying.

7. **JS implementation contract:**
   - Script must run inside `<head>` BEFORE `<body>` render to prevent FOUC. Pattern: `<script>(function(){ try { var t = localStorage.getItem('swing-trading-theme'); if (t === 'dark') { document.documentElement.classList.add('pre-dark'); } } catch(e){} })();</script>` placed inside `<head>` before any rendered content. Body class application happens on DOMContentLoaded (or inline at end of body).
   - **Wait — simpler pattern recommended:** inline `<script>` in `<head>` reads localStorage and writes `<body class="dark">` directly via document.write OR sets a class on `<html>` element + CSS reads `html.dark body { ... }`. The implementer chooses the lowest-FOUC pattern; document the tradeoff in code comments.
   - localStorage value MUST be validated against `["light", "dark"]` allowlist before applying — never trust localStorage raw. Reject + fall back to light if value is anything else.
   - `try/catch` around `localStorage` access (private-browsing modes block it).
   - Toggle button click handler uses `addEventListener` (NOT `onclick=` inline attribute — for CSP compatibility + maintainability).
   - Script element should NOT contain user-controlled content; it's a literal-string script.

8. **Audit surface (binding for verification):** the implementer MUST visually verify (via TestClient `app.css` content assertions OR by listing affected files) that the following surfaces render correctly in BOTH themes. Operator-witnessed gate exercises a subset; full programmatic coverage isn't realistic for theme verification.
   - Dashboard (status_strip; account card; open-positions table; hyp-recs panel; watchlist; cadence cards; pipeline-status banner)
   - Watchlist page (full + Top 5)
   - Journal page (stats + recent trades)
   - Reviews-pending page
   - Pipeline page (run history)
   - Config page (form + current values)
   - Cadence completion form (`/reviews/{id}/complete` — including the new 3e.16 trade activity section)
   - Trade-detail page (`/trades/{id}` — Phase 7 + Phase 8 daily-management timeline)
   - Trade entry form (with the 3e.7 example asides + `<details>`/`<summary>` collapsibles)
   - Hyp-recs expanded row (with the 3e.4 current-price line)
   - Error pages (`error.html.j2`, `page_error.html.j2`)
   - All state badges (Phase 7 — entered / managing / partial_exited / closed / reviewed)
   - Update-today badges (3e.5/3e.15 — ✓ logged / ⚠ pending)
   - Weather badges (Bullish / Caution / Bearish / STALE)
   - Stale-price `(stale)` indicator
   - Form validation error highlighting (`.field-error` class)
   - Degraded-state banner (`.banner-degraded` class)

9. **Charts: light only (V1).** Matplotlib chart PNGs baked at pipeline time stay light-themed. They will appear as light-on-dark when dark theme is active. Acceptable V1; V1.5 dispatch can add per-theme regeneration if operator surfaces complaints. Do NOT modify `swing/rendering/charts.py` or pipeline chart-generation in this dispatch.

10. **No schema changes; no Python changes; no template changes beyond base.html.j2.** Per CLAUDE.md "Phase isolation" convention. Pure CSS + minimal JS + nav-bar template extension.

11. **Toggle button styling:** matches existing nav link style (same font, padding, hover behavior); button is unobtrusive — operator should not visually scan past it as "this is something important to click" but it should be findable.

12. **Accessibility:**
    - aria-label per §0.3 #3.
    - Keyboard-accessible (button is `<button>` — focusable + Enter-key-activates by default).
    - `prefers-reduced-motion` not applicable here (no animation).
    - Sufficient color contrast in both themes — implementer SHOULD spot-check WCAG AA contrast for primary text/bg pair, but full AA audit is out of scope (V2 if operator surfaces).

---

## §1 Strategic context

Operator-surfaced 2026-05-08 — long evening prep windows benefit from dark theme for eye strain. CSS-variable refactor is small (117-line stylesheet); the audit surface is wide but mostly mechanical (each CSS class that uses a color gets its color converted to a variable reference). Adversarial-review value-add concentrates on the JS toggle (FOUC + localStorage validation + CSP safety).

**Schema state (binding):** Production DB at schema_version 16 post-3e.16 ship at HEAD `40eb6f2`. No schema work in scope.

**What's NOT in scope:**
- Per-theme chart regeneration (V1.5 if operator requests)
- prefers-color-scheme default (operator-locked)
- Cross-device theme sync via server-side persistence (operator-locked)
- 3-state toggle (light / dark / system) — V1 is binary
- WCAG AA audit (V2)
- Dark-theme-specific images/icons (V2; same emoji + glyph set works in both)

---

## §2 Worktree + binding conventions

### §2.1 Worktree
- **Branch:** `3e10-dark-theme`
- **Worktree directory:** `.worktrees/3e10-dark-theme/` at repo root.
- **BASELINE_SHA:** `40eb6f2` (HEAD of `main` post-3e.16 housekeeping).

### §2.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task families land + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §2.3 Commits
- Conventional prefix:
  - `style(web): Task A.X — <description>` for CSS-only commits
  - `feat(templates): Task B.X — <description>` for template additions (toggle button + script)
  - `feat(static): Task B.X — <description>` for new static asset (theme.js if external)
  - `test(web): Task X.Y — <description>` for test commits
  - `fix(area): Codex RN Major #X (internal) — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **TDD:** failing test first where pytest can pin contracts (toggle button presence; script content; CSS variable presence). Visual rendering + interactive behavior = operator-witnessed gate.

### §2.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer owns:** task-family commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§5) — visual inspection across audit surfaces.
- **Orchestrator owns:** integration merge to main + post-merge housekeeping.

### §2.5 Verify command
PowerShell from inside worktree:
```powershell
$env:PYTHONPATH = "."; python -m swing.cli web
```

---

## §3 Per-task implementation breakdown

### §3.1 Task family A — CSS variable refactor + dark overrides

**Acceptance criteria:**

- (A.AC.1) All hardcoded color values in `swing/web/static/app.css` (currently 31 color references per pre-dispatch grep) replaced with `var(--token-name)` references.
- (A.AC.2) `:root { ... }` block defines all CSS variables with light-theme default values, using semantic naming per §0.3 #5.
- (A.AC.3) `body.dark { ... }` (or equivalent — `html.dark` if implementer chose that pattern per §0.3 #7) overrides the variables for dark theme.
- (A.AC.4) Dark-theme contrast: primary text `--fg` against `--bg` MUST achieve at least visually-apparent contrast (operator's eyes are the gate; rough WCAG AA ~7:1 contrast ratio for normal text is the spirit). Suggested baseline:
  - `--bg`: light=`#ffffff`, dark=`#1a1a1a` (or similar near-black)
  - `--fg`: light=`#212529` (or current value), dark=`#e9ecef` (or similar near-white)
  - Other tokens: implementer picks dark-theme values that maintain visual hierarchy + sufficient contrast.
- (A.AC.5) NO behavior change in light theme — light-theme rendering MUST be visually identical to pre-refactor (CSS-variable refactor is a no-op for the default state).

**Suggested test names:**

- `test_app_css_defines_root_variables_block` — assert `:root` block is present + defines key tokens (`--bg`, `--fg`, `--accent`, etc.) by reading `swing/web/static/app.css` directly.
- `test_app_css_defines_dark_overrides_block` — assert `body.dark` (or `html.dark`) block is present + redefines the key tokens.
- `test_app_css_no_hardcoded_color_keywords` — assert that color values OUTSIDE the `:root` and `body.dark` blocks are var() references (regex scan; allow exceptions for non-color properties like `text-shadow` if any).

**Suggested commit shape:**

- A.1: variable refactor + RED tests + GREEN — commit (`style(web): Task A.1 — refactor app.css colors to CSS variables`)
- A.2: dark-theme override block — commit (`style(web): Task A.2 — add body.dark override block to app.css`)

**Watch items:**

- Some color-like values aren't theme-relevant (e.g., `transparent`, `inherit`, opacity-only values like `rgba(0,0,0,0.1)` for borders). Don't refactor these unless the alpha overlay produces unwanted contrast in dark theme — case-by-case judgment.
- `border-left: 3px solid #dee2e6;` in `.entry-example-aside` (3e.7 ship) — convert to `var(--border)`.
- The badge classes (state badges; weather badges; update-today badges) likely have BOTH bg and fg color rules per state — each gets a paired variable.

### §3.2 Task family B — Nav-bar toggle button + JS

**Acceptance criteria:**

- (B.AC.1) New `<button id="theme-toggle">` element in `swing/web/templates/base.html.j2` after the Config link inside `<nav class="topbar">`.
- (B.AC.2) Initial button content: emoji per current theme (server-render-side this defaults to `🌙` since light is default; JS updates to `☀️` if dark is loaded from localStorage).
- (B.AC.3) Inline `<script>` in `<head>` reads localStorage `swing-trading-theme`, validates against `["light","dark"]` allowlist, applies `dark` class to `<body>` (or `<html>`) BEFORE body render to prevent FOUC.
- (B.AC.4) Click handler on toggle button: flips current theme, writes new value to localStorage (try/catch), updates body class, updates button content + aria-label.
- (B.AC.5) localStorage access wrapped in try/catch (private-browsing fallback).
- (B.AC.6) NO inline `onclick=` attribute — handler attached via `addEventListener`.
- (B.AC.7) localStorage value validated before application (allowlist or default to light on bad values).

**Suggested test names:**

- `test_base_html_renders_theme_toggle_button` — TestClient GET `/`; assert response body contains `id="theme-toggle"`.
- `test_base_html_inline_script_reads_localstorage_and_validates` — assert response body contains the localStorage R/W code AND the `["light","dark"]` (or equivalent) allowlist check.
- `test_base_html_no_inline_onclick_on_toggle_button` — assert toggle button has NO `onclick=` attribute.
- `test_base_html_theme_script_in_head_before_body` — assert the FOUC-prevention script appears in `<head>` BEFORE `<body>` (string-position assertion).

**Suggested commit shape:**

- B.1: nav-bar button + RED tests + GREEN template — commit (`feat(templates): Task B.1 — add theme toggle button to nav bar`)
- B.2: inline script + RED tests + GREEN — commit (`feat(templates): Task B.2 — inline script for FOUC-free localStorage theme application`)

**Watch items:**

- FOUC: a brief flash of light theme before dark applies will surface in operator-witnessed gate. The `<head>` inline script pattern prevents this if it sets the body class BEFORE body render. Test for script-in-head position.
- CSP compatibility: project doesn't appear to use a strict CSP currently (no `Content-Security-Policy` headers in default response per a quick grep), so inline scripts are fine. If a strict CSP gets added later (Phase 9+), this script needs nonce hookup; bank as forward-compat watch item.
- `localStorage.getItem` returns `null` for missing key — null-check after the allowlist validation.

### §3.3 Task family C — Audit + adversarial-review prep

**Acceptance criteria:**

- (C.AC.1) Implementer enumerates affected surfaces per §0.3 #8 in the return report. NOT a code task per se — discovery + verification preparation for the operator-witnessed gate.
- (C.AC.2) Implementer documents in return report any surfaces where dark-theme rendering may have visual issues that operator should specifically check (e.g., colored advisory rows; hover states; focus indicators).

No commit needed for Task C (discovery + documentation in return report).

---

## §4 Adversarial review (Codex)

### §4.1 Setup (IMPLEMENTER runs this — convention per orchestrator-context "Executing-plans dispatch convention" 2026-05-02)

After ALL task-family commits land + tests are GREEN at branch HEAD, the implementer performs:

1. `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
2. Invoke `copowers:adversarial-critic` with:
   - `PHASE`: `3e10-dark-theme`
   - `SPEC_PATH`: `docs/3e10-dark-theme-brief.md`
   - `PLAN_PATH`: `docs/3e10-dark-theme-brief.md`
   - `BASELINE_SHA`: `40eb6f2`
3. Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **1-2 rounds** (small surface; most risk areas are pre-empted in §0.3).

### §4.2 Pre-empt list

Adversarial-review value concentrates on Task B (the JS + localStorage interaction). Pre-empt:

- **localStorage XSS / value tampering.** The script reads localStorage and applies a class. If the value is not validated, an attacker who can write to localStorage (via separate XSS) could write `"dark; alert(1)"` or similar. Validate against `["light","dark"]` allowlist BEFORE applying. (Even though `classList.add()` itself is XSS-safe, the validation is good defense-in-depth.)
- **FOUC.** Body renders light momentarily before script applies dark. Mitigated by `<head>`-inline script + html-element class (CSS reads `html.dark body`).
- **Non-CSP-clean inline script.** Document the absence of CSP currently + the future-CSP migration path (script extraction + nonce).
- **Accessibility.** aria-label updates on toggle. Button is keyboard-accessible by default.
- **prefers-reduced-motion.** Not applicable (no animation).
- **CSS cascade gotchas.** Specificity of `body.dark .badge-bullish-bg` vs base `.badge-bullish-bg` — variables defined on `:root` and `body.dark` are picked up via CSS custom-property cascade automatically; no specificity conflicts expected.
- **Refactor regression risk.** Light-theme rendering MUST be byte-equivalent (the var-substitution should be invisible). Spot-check via screenshot diff on a representative page.

---

## §5 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR:

- **Surface 1 — Toggle button renders.** Operator opens dashboard; verifies `🌙` button at right end of nav bar. Hover shows tooltip / aria-label "Switch to dark theme."
- **Surface 2 — Toggle works.** Click the button. Verify (a) immediate visual switch to dark theme; (b) button changes to `☀️`; (c) localStorage now contains `swing-trading-theme: "dark"` (operator can verify via DevTools).
- **Surface 3 — Persistence across refresh.** Reload the page. Verify (a) dark theme is still applied; (b) NO FOUC (no flash of light theme).
- **Surface 4 — Audit surfaces under dark theme.** Operator visits each page: dashboard / watchlist / journal / reviews-pending / pipeline / config / cadence completion form / trade detail / trade entry form / hyp-recs expanded row. Reports any visual issue (illegible text; missing badges; broken layouts).
- **Surface 5 — Toggle back to light.** Click toggle again. Verify (a) light theme returns; (b) button changes to `🌙`; (c) localStorage updated to `"light"`.
- **Surface 6 — Persistence across browser restart (optional).** Close browser; reopen at app URL. Verify last-chosen theme is restored.
- **Surface 7 — pytest + ruff.** `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows 18 (no new violations).

**Expected test count delta:** +5-8 (Task A: 3 CSS-content tests; Task B: 4-5 template-content + script-position tests).
**Expected ruff baseline:** 18 (no change).

---

## §6 Return report shape

After operator-gate PASS, draft a return report with:

1. Final HEAD on branch
2. Commit count breakdown (task-impl / Codex-fix / operator-gate-fix)
3. Codex round chain
4. Test count delta
5. Ruff baseline delta
6. Operator-gate surface results
7. Per-task-family deviations
8. Codex Major findings ACCEPTED with rationale
9. Watch items surfaced but not acted on (esp. any audit-surface visual issues operator flagged)
10. Worktree teardown status

Special return-report ask for this dispatch: include the §0.3 #8 audit-surface enumeration with implementer's discovery notes (which surfaces may need operator extra-attention; which were verified CSS-clean by structural inspection).

---

## §7 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading 3e10-dark-theme dispatch.

WORKING DIRECTORY: c:\Users\rwsmy\swing-trading\.worktrees\3e10-dark-theme
BRANCH: 3e10-dark-theme
BASELINE_SHA: 40eb6f2

Step 1 — Read the dispatch brief end-to-end:
  docs/3e10-dark-theme-brief.md

It locks 12 design decisions (§0.3) that you do NOT re-litigate. Three task families:
  - Task A: CSS variable refactor in app.css + body.dark override block
  - Task B: nav-bar toggle button + FOUC-free localStorage script
  - Task C: audit + return-report documentation (no commits)

Step 2 — Read CLAUDE.md + docs/orchestrator-context.md (binding conventions).

Step 3 — Verify worktree state:
  git rev-parse HEAD                  # expect 40eb6f2
  git status                          # expect clean
  python -m pytest -m "not slow" -q   # expect baseline GREEN (2166 passed)

Step 4 — Execute the brief via superpowers:subagent-driven-development. TDD discipline per task family.

Step 5 — After ALL task families land + GREEN, run the adversarial review YOURSELF (per §4.1):
  - Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active
  - Invoke copowers:adversarial-critic with PHASE=3e10-dark-theme,
    SPEC_PATH=docs/3e10-dark-theme-brief.md,
    PLAN_PATH=docs/3e10-dark-theme-brief.md,
    BASELINE_SHA=40eb6f2
  - Iterate rounds + land Codex-fix commits until NO_NEW_CRITICAL_MAJOR.

Step 6 — Draft return report per §6 + signal orchestrator. Include the §0.3 #8 audit-surface notes. Orchestrator triages; operator drives §5 visual gate; orchestrator handles integration merge.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers
  - Modify swing/rendering/charts.py or pipeline (charts stay light per §0.3 #9)
```

---

## §8 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-10 (post-3e.16-ship).
- **Brief commit:** TBD (committed as final orchestrator action before dispatch).
- **Brief HEAD context:** `40eb6f2` on main.
- **Worktree path (binding):** `.worktrees/3e10-dark-theme/`.
- **Baseline test count:** 2166 fast (1 skipped).
- **Baseline ruff count:** 18 (E501 only).
- **Expected post-dispatch test count:** ~2171-2174 (+5-8).
- **Expected post-dispatch ruff count:** 18 (no change).
