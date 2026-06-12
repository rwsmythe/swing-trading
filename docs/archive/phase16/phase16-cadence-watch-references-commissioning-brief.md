# Phase 16 — Cadence-Review Watch-Standard References — Arc Commissioning Brief (SMALL)

**Audience:** The Phase 16 orchestrator instance.
**Mission:** Commission a deliberately SMALL arc (take the next free arc number): the weekly/monthly review cadence
pages in the web UI should reference the corresponding research-director watch-standard activities, so the
operator's existing review ritual carries the watch ritual with it. **Static text only** — the operator's words:
"These can be simple static text items included in those web pages."
**Prepared:** 2026-06-10 by the research-director/evaluator instance (operator-commissioned).

---

## 0. Ground truth (verified 2026-06-10)

- The cadence-review surface: `swing/web/templates/cadence_complete.html.j2` (route `cadence_complete_form`,
  `swing/web/routes/trades.py:2939`), which renders `vm.review.review_type` (`weekly` / `monthly`) — the natural
  hook for per-type static text. `reviews_pending.html.j2` is the sibling list surface.
- The referenced standard: [`docs/research-director-watch-standard.md`](research-director-watch-standard.md) —
  §2.1 the weekly glance procedure (`python scripts/weekly_glance.py`), §3 the monthly evaluator read, §1 the
  quarterly strategic evaluation (every 3rd monthly read; first early 2026-09).

## 1. Requirements (binding)

- **R1 — weekly:** when completing a WEEKLY review, the page displays a static reference: run
  `python scripts/weekly_glance.py` from the repo root (watch standard §2.1; ~5s, read-only) and escalate any
  `ATTENTION` lines to the research director rather than waiting for the monthly read.
- **R2 — monthly:** when completing a MONTHLY review, the page displays: the monthly research-director read is due
  (watch standard §3 — the binding evaluator cadence, first trading week of the month), and every 3rd monthly read
  is the QUARTERLY strategic evaluation (§1).
- **R3 — static only.** Jinja conditionals on `review_type` are fine; no schema; no new VM fields unless strictly
  unavoidable; ASCII-only text; link/cite the standard doc path so the text stays a pointer, not a fork of the
  standard's content (the standard remains the single source of truth — if the cadence ever changes, only the
  standard changes).
- **R4 — tests:** TestClient assertions that the weekly page shows the glance text and NOT the monthly text, and
  vice versa. A light operator browser witness (these are full-page renders, not HTMX fragments — the heavy HTMX
  gate discipline does not apply; one look at each page type suffices).
- **R5 — placement latitude:** if `reviews_pending` (or another cadence surface) is the more natural/additional
  home, your call — the requirement is that the operator SEES the right reference when conducting each review type.

## 2. Constraints + done criteria

- No schema; templates (+ route/VM only if strictly needed) + tests. Zero contact with the measurement chain,
  metrics surfaces, or anything in the standing lock sets.
- Your normal cycle, collapsed as you judge (this is plausibly a single focused-executing dispatch — the design
  space is one decision: exact text + placement).
- Fast suite green on the merged head; ruff clean; zero co-author trailers; `docs/phase16-todo.md` updated.
- Report back; the research director QAs the rendered text against the standard's §-references at the next read.
