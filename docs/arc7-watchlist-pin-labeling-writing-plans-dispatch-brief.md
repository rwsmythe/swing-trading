# Writing-Plans Dispatch Brief — Phase 16 / Arc 7: Watchlist Pin + Hypothesis-Labeling Effectiveness

**Arc:** Phase 16 / **Arc 7**. SECOND of the full copowers cycle; the brainstorm spec is LOCKED + merged (QA'd against the AMENDED commission — all research-director riders verified present).
**Source of truth (LOCKED, merged):** [`docs/superpowers/specs/2026-06-10-watchlist-pin-labeling-design.md`](superpowers/specs/2026-06-10-watchlist-pin-labeling-design.md) — **READ IT END-TO-END.** The plan implements it; do NOT re-litigate. The AMENDED commission ([`docs/phase16-watchlist-pin-and-labeling-effectiveness-commissioning-brief.md`](phase16-watchlist-pin-and-labeling-effectiveness-commissioning-brief.md), amendment block at top) is the governance context; the spec already absorbed it.
**Branch-from:** main HEAD at worktree creation (currently `8a7a3c90`; re-verify — the operator commits in parallel and **the P0 entry-intent arc is EXECUTING in a live worktree** — it has NOT merged as of this brief).
**Schema:** **YES — additive `watchlist` columns** (`pinned`, `pin_note`, `pinned_at`). **The migration number is a STEP-0 LIVE CHECK:** if P0 has landed `0027` on main by your branch time → take `0028`; if not → the plan documents BOTH the number-resolution rule and the #11 version-pin sweep for whatever lands (the 0025/0026 sweeps are the playbook). Strict-equality backup gate per the per-phase shape; `BEGIN;...COMMIT;` + version bump in-file (#9, the ratified 0025 convention).
**Deliverable:** an executing-ready plan at `docs/superpowers/plans/2026-06-10-watchlist-pin-labeling-plan.md` + Codex convergence (`NO_NEW_CRITICAL_MAJOR`) + `.copowers-findings.md` (prompts AND responses). Commit ONLY the plan doc.

---

## 1. Mandate (one line)

Turn the LOCKED spec into an ordered, TDD-structured, executing-ready plan: the additive migration + ON-CONFLICT-preserved pin columns + `set_watchlist_pin` (rowcount==1 authoritative), the pure `pinned_tickers`/`suppressed_removes` service veto, the `_step_evaluate`/`_step_watchlist` universe injection + audit lines, the prefill `include_baseline=True` flip (opt-in #1), the shared `cohort_hint_for` helper + three render sites (opt-in #2, function-local import in dashboard.py per Codex R3), the expanded-row HTMX pin UI, the §13 addendum to the 0026 spec, and the §10 test contracts — incl. the inventory guard test (exactly 3 literal opt-in sites) and the soft-warn/force round-trip.

---

## 2. STEP 0 — re-ground (live checks; the spec grounded on `0ff853e9`)

1. **P0 landing check (LIVE):** `git log --oneline -10` + `ls swing/data/migrations/*.sql | tail -2`. If P0's `entry_intent` (likely `0027`) has merged: take `0028`, ground the entry-form/`routes/trades.py` anchors against the POST-P0 files, and note the reconciliation points. If not: take `0027`, and the plan carries an explicit note that the executing phase re-checks at ITS branch time (P0 may land mid-cycle — whichever lands second reconciles; this arc's touches on the shared files are minimal: no new entry-form field, no new trades route).
2. Re-confirm the spec's anchors at your HEAD: `compute_watchlist_changes` @service.py:57 (+ the not-qualifies branch ~123-150), `_step_watchlist` @runner.py:~1565, the `_step_evaluate` held-ticker union seam, `upsert_watchlist_entry` + the watchlist repo, `hypothesis_prefill.py:28`, the watchlist templates/VMs/routes, `label_match.py`'s 3-rule contract, the 0026 spec file (the §13 addendum target).
3. yfinance/Arc-6 interaction (free synergy — verify the spec's §3 claim): pinned tickers unioned into the evaluate universe join the Arc-6 warm cohort automatically (no extra fetch plumbing).

---

## 3. Plan-shape guidance (you own the decomposition; map every task to the spec §10 contracts)

A natural ordering: (1) migration + models + repo (ON-CONFLICT exclusion + `set_watchlist_pin` + the pin-survival regression + the #11 sweep) — ONE task per #11 read/write atomicity; (2) the pure service veto (`pinned_tickers` keyword-only frozenset default-empty; `suppressed_removes` trace-fidelity lane; the threshold diversion to `streak_increments`); (3) the runner injection (`_step_evaluate` union + `_step_watchlist` plumbing + the pin-injection & suppressed-remove audit lines; the F6 delisted-pinned edge test — error rows must NOT blank `last_*`/`missing_criteria`, the R1-CRITICAL fix); (4) the prefill flip + the R5 soft-warn/force round-trip regressions + the `label_match` contract test; (5) `cohort_hint_for` + the three render sites (function-local import in dashboard.py) + the dashboard containment regression (call-site kwargs asserted) + the inventory guard test; (6) the HTMX pin UI (expanded-row form: `hx-headers HX-Request`, no `<tr>`-root fragments, `hx-target="this"` discipline, 204+HX-Redirect or fragment-swap per the established patterns; TestClient assertions on the rendered attributes); (7) the §13 addendum edit to the 0026 spec doc (a docs task — the Arc-1 §5.3 amendment is the precedent for editing a merged spec with a dated block); (8) full suite + ruff.

**The operator-witnessed BROWSER gate is part of the plan's deliverable definition** (binding for HTMX): script the walkthrough — pin a row → run a nightly that would remove it → witness survival + the badge + the suppressed-remove audit → unpin → witness next-nightly age-off; plus the entry form rendering the server-stamped `Broad-watch baseline (watch); failed: …` for a watch ticker. Form-render + TestClient persistence suffice for the label half; no real trade required.

**Discriminating tests** ([[feedback_regression_test_arithmetic]]): the pin-survival upsert test must FAIL under a naive ON-CONFLICT that includes the pin columns; the veto test must FAIL under remove-suppression that also freezes streaks (compute the streak under both); the inventory guard counts literal `include_baseline=True` occurrences (3) and FAILS on a 4th.

---

## 4. Locks / invariants (spec §11/§13 — propagate verbatim)

R6 in full: registry rows; the matcher two-phase gate + dashboard call-site `include_baseline=False` defaults (regression-tested); `tier.py` + deviation allowlist; the shadow engine + temporal log + measurement chain (the universe-composition note DOCUMENTS the screen∪pinned∪held change — the chain itself is untouched); the 16 historical labels; `mistake_tags`/`process_grade`. Pin columns are operator-owned (nightly upserts preserve). Labels mirror shadow attribution — pins NEVER drive labels. `swing/trades/` untouched. The #27 lanes are warnings/log lines, NOT phantom `watchlist_archive` rows. Schema: the additive migration only (v26 → v27 or v27 → v28 per the STEP-0 check).

---

## 5. copowers process (binding)

- **Run `copowers:writing-plans`** → adversarial Codex loop **to convergence** (`NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED).
- **Codex transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows; tell Codex not to run git.
- Persist BOTH prompts AND responses to gitignored `.copowers-findings.md`. Commit ONLY the plan doc; conventional; no `Co-Authored-By`; no `--no-verify`; final `-m` paragraph plain prose; trailers `[]`.
- **Return a report:** the plan path; the STEP-0 P0/migration-number resolution; the task decomposition + how the browser gate is scripted; the Codex verdict (rounds + final line); flagged items for executing. Then STOP — executing is a separate commission after orchestrator QA.
