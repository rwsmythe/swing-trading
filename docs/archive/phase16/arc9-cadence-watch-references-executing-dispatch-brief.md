# Focused-Executing Dispatch Brief — Phase 16 / Arc 9: Cadence-Review Watch-Standard References

**Arc:** Phase 16 / **Arc 9** — the deliberately SMALL research-director-commissioned arc: static watch-standard references on the weekly/monthly review cadence pages. **The commission is authoritative:** [`docs/phase16-cadence-watch-references-commissioning-brief.md`](phase16-cadence-watch-references-commissioning-brief.md) — R1-R5 binding; read it end-to-end (it's one page).
**Cycle stage:** **FOCUSED executing-with-Codex** (single cycle; commission-sanctioned — the design space is exact text + placement).
**Branch-from:** main HEAD at worktree creation (currently `2dee9a7f`; re-verify — **the Arc-4 executing cycle is IN FLIGHT in parallel**; its loci are `swing/trades/` + reconciliation/dashboard surfaces — your loci are the cadence templates (+ a VM/route touch only if unavoidable); overlap ≈ zero, standard rebase discipline at merge).
**Schema:** **NONE.** Templates + tests (+ route/VM only if strictly needed per R3).
**Deliverable:** the references shipped TDD + Codex-converged + `.copowers-findings.md` (prompts AND responses).

---

## 1. Mandate (one line)

When completing a WEEKLY review the page shows the watch-standard §2.1 reference (run `python scripts/weekly_glance.py` from the repo root; ~5s, read-only; escalate any `ATTENTION` lines to the research director); when completing a MONTHLY review it shows the §3 monthly-evaluator-read reference + the every-3rd-read quarterly note (§1) — static ASCII text, Jinja-conditional on `review_type`, **pointer-not-fork** (cite `docs/research-director-watch-standard.md`; never duplicate the standard's content).

---

## 2. Grounded anchors (orchestrator-verified at acceptance; re-verify at YOUR HEAD)

- `swing/web/templates/cadence_complete.html.j2` renders `vm.review.review_type` (L2/L4) — the natural hook (R5 grants placement latitude; `reviews_pending.html.j2` is an optional additional home if it better guarantees the operator SEES the reference per review type).
- The route: `cadence_complete_form` @routes/trades.py:~2939 (the line may shift — re-anchor).
- The referenced standard exists: `docs/research-director-watch-standard.md` (§2.1 weekly glance / §3 monthly read / §1 quarterly); `scripts/weekly_glance.py` exists.

---

## 3. Requirements (the commission's R1-R5 — essentials)

- **R1 weekly / R2 monthly:** the per-type texts above. **R3:** static only; Jinja conditionals fine; NO schema; no new VM fields unless strictly unavoidable; ASCII-only; pointer-not-fork (if the cadence ever changes, only the standard changes). **R4:** TestClient assertions — the weekly page shows the glance text and NOT the monthly text, and vice versa (per-type text isolation). **R5:** placement is yours — the requirement is the operator SEES the right reference when conducting each review type.
- These are full-page renders, NOT HTMX fragments — the heavy HTMX gate discipline does NOT apply; the operator browser witness is LIGHT (one look at each page type, scheduled with the orchestrator post-merge — it folds into the phase's combined gate pass).

---

## 4. Execution + copowers process (binding)

- **TDD, green-per-commit** (likely 1-2 commits); conventional; NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; trailers `[]`. Zero contact with the measurement chain, metrics surfaces, or any standing lock set. Full fast suite + ruff ON YOUR FINAL HEAD (actual count; baseline ≈7869 + whatever Arc 4 lands if it merges first — re-read the actual number).
- **Codex to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED) — small diff, likely fast; probe the per-type isolation tests + the pointer-not-fork discipline (no duplicated standard content) + ASCII.
- **Transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows; tell Codex not to run git; capture output to FILES. Persist BOTH prompts AND responses to gitignored `.copowers-findings.md`.

---

## 5. Return report (then STOP — do NOT merge)

The commit SHAs + messages; the placement decision (cadence_complete only vs + reviews_pending); the suite result (actual count) + ruff; the Codex verdict (rounds + final line); the operator-witness note (one look per page type; the research director QAs the rendered text against the standard's §-references at the next read).
