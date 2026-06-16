# Phase 18 — web-polish run (18-H.2 + 18-H.3 + R1) — dispatch brief

**Authored:** 2026-06-16 by CHARC. **Phase:** copowers executing (FIX-DIRECT — three small, settled web/config fixes; no separate writing-plans, like 18-H.4). **Cohesive batch:** all web-surface (+ one pyproject line), all review-strong, each individually small + low-risk, one reviewable diff. **Tripwire: NONE** → dispatches without a CHARC architecture gate (CHARC verifies at QA, does not block).

## Item 1 — 18-H.2: unify the 404 error surface
**Now:** a validation-400 (`RequestValidationError` → `_handle_validation_error` → `page_error.html.j2`, which extends base) renders the base layout + the 18-F stoplights; but a plain `StarletteHTTPException` 404 (`_handle_http_exc`, `swing/web/app.py:~500`) falls to the minimal Starlette default — no base, no stoplights.
**Fix:** route the 404 path through `page_error.html.j2` too — build the `PageErrorVM` (the same VM the 400 path uses) + return `TemplateResponse(request, "page_error.html.j2", {...}, status_code=404)`. The stoplights come for FREE via the 18-F `_health_stoplights_context_processor` (base-wide injection — `page_error.html.j2` extends base), so NO per-VM stoplight field is needed (the per-VM-field gotcha was already sidestepped by the context processor — verify on disk).
**Binding test:** a request to an unknown route returns **404** AND renders the base layout + the topbar stoplights (assert the base markers + a `.stoplight-` class in the body), NOT the minimal Starlette default. Compute under both paths (pre-fix = minimal default, no base; post-fix = base + stoplights) to prove it distinguishes.
**Gotchas:** Starlette 1.0 signature `TemplateResponse(request, "name", {...}, status_code=...)`; preserve `status_code=404` (don't drop to 200); confirm `PageErrorVM` exists + its required fields (build it the same way `_handle_validation_error` does). Keep the existing bare-unhandled-500 degraded path untouched.

## Item 2 — 18-H.3: stoplight DOT (not the word) in the health drill-down
**Now:** `/health/tool` + `/health/research` drill-downs list each check's status as the WORD (green/yellow/red).
**Fix:** render the colored `.stoplight-<color>` DOT instead (reuse the EXISTING topbar `.stoplight-*` classes — no new CSS framework), **keeping the status WORD as the `title`/`aria-label`** (a11y + test-greppable). Small edits to `health_tool.html.j2` + `health_research.html.j2` + a CSS tweak (`static/app.css`) + their tests.
**Binding test:** the rendered drill-down row carries the `.stoplight-<color>` class for each check AND the status word survives as the `title`/`aria-label` (assert both — the dot class + the word-in-title; so a11y + the existing test-grep on the word still pass).
**Gotchas:** reuse the topbar `.stoplight-*` classes (don't invent new ones); the word MUST remain in `title`/`aria-label` (don't drop it — tests + screen-readers depend on it).

## Item 3 — R1: declare `requests` in pyproject
**Why:** `requests` is USED in the codebase but only present TRANSITIVELY (not in `pyproject.toml`'s declared deps). Declare it explicitly (don't rely on a transitive pin). **This is NOT a new dependency** (requests is already installed/used) → it does NOT cross the new-dependency tripwire; it's a declaration-correctness fix.
**Fix:** add `requests` (with a sensible floor, matching the version already resolved) to `[project.dependencies]` in `pyproject.toml`.
**Binding check:** `requests` appears in the declared `[project.dependencies]`; the suite still green (no resolution change — it was already installed).

## Cell + review
- **Cell: `implementer-opus-high`** (settled design; careful multi-file web work — the 404 handler + the VM + the templates).
- **Review: `review-strong`** (production web code) **WITH REPO ACCESS** (the 18-H.4 methodology — read the surrounding error-handling + base/VM/context-processor code, not diff-only) to `NO_NEW_CRITICAL_MAJOR`; persist findings. **`codex-auto-review` = GATING-complementary** (orchestrator-run, repo-access, `-c model_reasoning_effort=high`) — a B `[P1]`/major resolved-or-cited before merge. before-AND-after full fast suite.

## Gate
Fast suite green (before + after) + `ruff check swing/` clean + `review-strong` convergence + `codex-auto-review` clear → orchestrator QA-against-disk → **the operator's BINDING browser gate** (web/template visual work — TestClient can't see the render): the operator browses an unknown route (the 404 now shows base + stoplights) + the `/health/tool` + `/health/research` drill-downs (the dots render, the word survives as a tooltip) → merge. CHARC verifies the diff at QA (no block — no tripwire). The IMPLEMENTER reports its result to the ORCHESTRATOR in chat (it has no role identity; it must NOT run role_mail / post to any mailbox); the ORCHESTRATOR posts its QA'd return_report to charc as normal.
