# Brainstorming Dispatch Brief — Phase 16 / Arc 7: Watchlist Pin + Hypothesis-Labeling Effectiveness

**Arc:** Phase 16 / **Arc 7** — research-director-commissioned (operator-approved 2026-06-10): make hypothesis labeling EFFECTIVE end-to-end in the web-first workflow via (1) a **watchlist pin** and (2) the **matcher-driven auto-label prefill amendment**.
**Authoritative commission:** [`docs/phase16-watchlist-pin-and-labeling-effectiveness-commissioning-brief.md`](phase16-watchlist-pin-and-labeling-effectiveness-commissioning-brief.md) — **READ IT END-TO-END FIRST.** Requirements **R1-R6 are BINDING** (operator-elicited; this brief carries the essentials but the commission is the authority). Its §2 design questions are YOUR brainstorm's deliverable.
**Cycle stage:** `copowers:brainstorming` (produce a LOCKED design spec, Codex-converged). FULL copowers cycle — schema touch + HTMX surfaces + a governance addendum warrant it.
**Branch-from:** main HEAD at worktree creation (currently `4942f246`; re-verify — the operator commits in parallel, and the P0 tuition-vs-error arc is at writing-plans in the research-director lane).
**Schema:** **YES — additive columns on `watchlist`** (R1: `pinned` 0/1 + `pin_note` TEXT + `pinned_at` if cheap). **Migration number taken at BRANCH TIME of the executing phase** (latest today is `0026`; P0 will likely take `0027` → expect this arc at `0028`; whatever number lands re-runs the #11 version-pin sweep — the Arc-1 executing arc has the playbook). Backup-gate: follow the strict-equality per-phase shape.
**Deliverable:** a locked design spec at `docs/superpowers/specs/2026-06-10-watchlist-pin-labeling-design.md` + the **0026-spec ADDENDUM draft language** (R3 governance — part of the spec deliverable, a dated section, not a rewrite) + Codex convergence + `.copowers-findings.md` (prompts AND responses). Commit ONLY the spec doc(s).

---

## 1. Mandate (one line)

Design: a per-ticker watchlist pin (blocks removal ONLY — streaks/requalification keep counting; HTMX set/clear from the row; visibly badged; stale-row treatment for pinned-but-absent tickers) + the one-call-site `include_baseline=True` prefill amendment (web/CLI entry prefill yields narrow-first else `Broad-watch baseline (watch); failed: …`) + the R4 per-row cohort hint + the R5 soft-warn round-trip — with the 0026 addendum, under the R6 lock set.

---

## 2. Grounded current state (orchestrator re-verified on `4942f246`, 2026-06-10 — the commission's anchors with fresh line numbers)

- `watchlist` table (migration 0003): ticker PK, `status`, `qualification_count`, `not_qualified_streak`, `last_data_asof_date`, frozen `entry_target`/`initial_stop_target`, `missing_criteria`, `notes`. **No pin columns.**
- Lifecycle: `_step_watchlist` @[runner.py:1565](../swing/pipeline/runner.py) (shifted +62 by Arc 6 — re-verify at your HEAD) applies `compute_watchlist_changes` @[service.py:57](../swing/watchlist/service.py). **The absent-from-candidates skip is the `if candidate is None: continue` at ~service.py:70** — an absent ticker gets NO streak movement and NO removal path today; read the FULL removal semantics before designing the pin veto.
- The entry form's `hypothesis_label` is server-stamped: resolved at form-render via `lookup_active_recommendation_label` (called @[view_models/trades.py:542](../swing/web/view_models/trades.py); DEFINED @[hypothesis_prefill.py:28](../swing/recommendations/hypothesis_prefill.py) — the matcher call inside it is where `include_baseline=True` lands, that ONE site only); rendered display-only span + HIDDEN input in [partials/trade_entry_form.html.j2](../swing/web/templates/partials/trade_entry_form.html.j2) (~147-148); round-tripped through the soft-warn confirm `form_values` @[routes/trades.py:1462-1518](../swing/web/routes/trades.py); the POST field @:490 with `canonicalize_hypothesis_label` persistence.
- The matcher's two-phase fallback gate @[hypothesis.py:349-351](../swing/recommendations/hypothesis.py) — narrow-first precedence is STRUCTURAL; the prefill inherits it free.
- Governance context: [`docs/superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md`](superpowers/specs/2026-06-09-broad-watch-baseline-hypothesis-design.md) §3.2 + §5.1 (the containment this arc partially amends per the R3 grant). Prior art (context only): `docs/watchlist-sort-by-tags-brief.md`.
- **Coordination:** P0 (entry_intent + entry/review-form changes) is at writing-plans — NOT yet landed. Both arcs touch `trade_entry_form.html.j2` + `routes/trades.py`; land in either order; expect a small merge reconciliation at whichever lands second.

---

## 3. The binding requirements (R1-R6 — the commission §1 is authoritative; essentials)

- **R1:** pin flag + note (+ `pinned_at` if cheap), set/clear from the watchlist row via HTMX. Additive `watchlist` migration; `swing/data` carve-out scoped to schema + repo column plumbing.
- **R2:** pin blocks REMOVAL ONLY — streaks + requalification continue exactly as today; unpin → accumulated state takes effect next nightly (no mid-session retroactive removal). Pinned rows visibly badged (note displayed/abbreviated). Stale-display treatment for pinned-but-absent tickers (do NOT show stale numbers as fresh).
- **R3:** `include_baseline=True` at the `lookup_active_recommendation_label` matcher call ONLY. Tags/pins do NOT drive labels (labels mirror shadow attribution). **The 0026 addendum is REQUIRED** (dated section): dashboard surfaces stay contained (default False + a regression test asserting no broad-watch rows reach the hyp-recs panel); the single-ticker prefill re-classified as an attribution surface; the frozen registry row untouched.
- **R4:** per-row cohort hint on the watchlist page (narrow name | "broad-watch" | none). Minimal V1 affordance — your brainstorm picks the data path (matcher per row at render vs precomputed at the nightly step).
- **R5:** the soft-warn confirm round-trips the new prefill VALUE; `force=true` resubmit does not drop it (hidden-anchor family). Regression: a broad-watch entry through soft-warn persists `Broad-watch baseline …`.
- **R6 locks:** registry rows; matcher two-phase gate + dashboard call-site defaults; `swing/metrics/tier.py` + deviation allowlist; shadow engine + temporal log + measurement chain; the 16 historical trade labels; `mistake_tags`/`process_grade` — ALL untouched. The persisted label must match `Broad-watch baseline` under `label_match.py`'s 3-rule contract (test it).

---

## 4. Design questions (commission §2 — your brainstorm resolves these WITH the operator)

1. **Pin UI mechanics:** row button vs detail view; the HTMX swap shape — the `<tr>`-fragment `makeFragment` gotcha + `hx-target` inheritance + embedded-form `hx-headers HX-Request` all apply; 4xx swap override preserved.
2. **The pin-veto seam:** inside `compute_watchlist_changes` (keep the service PURE — it currently takes rows in/out) vs the write phase in `_step_watchlist`. The delta object may grow a `suppressed_removes` lane for audit.
3. **The #27 audit:** does `watchlist_archive` record a "pin prevented removal" trace, or a `warnings_json` line? (Silent-skip-without-audit leans toward a trace.)
4. **The R4 hint's data path:** matcher-per-row at render (candidates already loaded for the page?) vs precomputed at the nightly step (a column? — that would grow the migration). Keep it small.
5. **Stale-pinned-row display:** `last_data_asof_date` + a stale indicator? What exactly renders when the ticker left the screen entirely?
6. **Migration number + the #11 sweep interaction with P0** (number at executing-branch time; the sweep playbook is the Arc-1/0025 + bwb/0026 precedent).

---

## 5. Things to nail (each needs a test where applicable)

- **HTMX browser-only surfaces:** TestClient cannot catch the `<tr>`-fragment wrap, `hx-target` inheritance, or the OriginGuard 403 on embedded forms — design the templates to the gotcha rules AND plan for the **operator-witnessed browser gate** (BINDING): pin → survives a removing nightly → unpin → ages off; the entry form renders the server-stamped broad-watch label (form-render + a TestClient persist test suffice — no real trade required).
- **The R5 round-trip** through BOTH the soft-warn confirm AND `force=true` (the hidden-anchor 4-tier family; `form_values` exclusion-list interaction @routes/trades.py:1487).
- **The hyp-recs containment regression:** no broad-watch rows in the panel; dashboard call sites still default-False (assert the call-site kwargs, not just behavior).
- **Pin-veto semantics:** a pinned ticker with a removal-grade streak stays; its streak KEEPS counting; unpin → removed at the NEXT nightly (not retroactively). The absent-from-candidates pinned ticker neither moves streak nor gets removed (today's `continue` behavior) — whatever stale display you design, the service semantics stay exact.
- **Migration discipline:** additive columns; explicit `BEGIN;...COMMIT;` + version bump (#9, the 0025/0026 convention); strict-equality backup gate; migrate-twice no-op; the #11 version-pin sweep; `_row_to_*`/dataclass/repo plumbing in the SAME task as the schema (read+write together).
- **Server-stamp discipline:** the pin POST handler re-computes/validates server-side (no trusted hidden state beyond the established hidden-anchor pattern); `... or None` for the nullable `pin_note` (CHECK-constraint family).

---

## 6. copowers process (binding)

- Run `copowers:brainstorming` (explore §4 WITH the operator → adversarial Codex loop **to convergence**, `NO_NEW_CRITICAL_MAJOR`; 5-round cap SUSPENDED).
- **Codex transport (WSL CLI; MCP dead):** `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (PATH prefix REQUIRED; liveness `codex --version` → `codex-cli 0.135.0`). Pre-generate the diff on Windows; tell Codex not to run git.
- Persist BOTH prompts AND responses to gitignored `.copowers-findings.md`. Commit ONLY the spec doc(s); conventional; no `Co-Authored-By`; no `--no-verify`; final `-m` paragraph plain prose; trailers `[]`.
- **Return a report:** the spec path; the resolved §4 design questions; the 0026-addendum draft language (the research director QAs it post-merge); the Codex verdict (rounds + final line); flagged items for writing-plans. Then STOP — writing-plans is a separate commission after orchestrator QA.

---

## 7. What this arc is NOT

NOT a tag store / sort-by-tags feature (the prior-art brief is context, not scope). NOT a post-hoc label editor. NOT a metrics surface (R4 is an affordance). NOT a registry/matcher-gate/tier/measurement-chain change (R6). NOT the P0 entry_intent work (separate in-flight arc; expect to reconcile at merge). Labels are NEVER driven by pins/tags — they mirror shadow attribution (operator decision).
