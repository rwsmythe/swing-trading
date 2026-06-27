# Tranche B-ops session 3 — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Execute the rationale-taxonomy cluster from the Tranche B-ops session-1 design spec (T4 entry enum, T5 stop-adjust enum, T6 exit rationale drop, T7 stop-form preservation), plus housekeeping. Then run adversarial review on the combined diff.
**Expected duration:** 6–10 hours of implementer work. Early-return valve provided on T7 if the session is getting unwieldy.
**Prepared:** 2026-04-24 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, gotchas, TDD discipline, Phase isolation rule. Phase isolation carve-out for this session is implicit: T4 and T5 touch `swing/trades/entry.py` and `swing/trades/stop_adjust.py` respectively for enum additions, plus `swing/data/repos/trades.py` remains read-only (the rationale enum's `.value` stays `str` at the service boundary per spec §6).
2. `docs/superpowers/specs/2026-04-23-tranche-b-ops-session-1-design.md` — authoritative design. §3 covers T4/T5/T6 (rationale taxonomies), §5 covers T7 (stop-form preservation), §6 summarizes schema/template/VM/CLI impacts, §7 contains the implementation task list with acceptance criteria for each.
3. `docs/tranche-b-ops-session-2-brief.md` — precedent for brief style; also documents the adversarial-review pattern (Session 2 ran 5 rounds successfully).
4. Recent commits `971ad36..HEAD` — context on what Session 2 shipped and adjusted. In particular, note the criteria-panel as-of semantic change in `build_watchlist_expanded` (Session 2 C4 / Round 3 Major 1) — your Session 3 work does not interact with it but the `trade_events.rationale` column semantics are relevant for T6.

**Skill posture.**
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans`. The design work is done — the spec is your contract.
- Invoke `superpowers:test-driven-development` per CLAUDE.md for each task's red-green cycle.
- Invoke `superpowers:verification-before-completion` before declaring done.
- **After all code commits land**, invoke `copowers:adversarial-critic` (or the equivalent adversarial-review loop — match the Session 2 pattern where the implementer ran `git diff <base>..HEAD -- swing/ tests/` through Codex MCP and iterated rounds until NO_NEW_CRITICAL_MAJOR). Adversarial review is **standing convention now** per user decision; it is not optional on this or future code-shipping sessions.

---

## 1. Session scope — up to five code commits + one housekeeping commit

### Required commits

| # | Commit | Source |
|---|--------|--------|
| C0 | Housekeeping: track this brief + update phase3e-todo.md with Tranche B-ops deferred items | §2 |
| C1 | T4 — entry rationale enum | Spec §3 (+ §7 T4) |
| C2 | T5 — stop-adjust rationale enum | Spec §3 (+ §7 T5) |
| C3 | T6 — drop separate exit rationale field | Spec §3 (+ §7 T6) |
| C4 | T7 — stop-form field preservation + Force checkbox | Spec §5 (+ §7 T7) |
| C5 | (if needed) adversarial-review fixes | §3 adversarial review |

### Early-return valve on T7

T7 depends on T5 (both touch `trade_stop_form.html.j2`) and is the largest single task in the cluster. **If after completing C0–C3 you judge the session has gone long enough, land C1+C2+C3 plus adversarial review on those three, and leave T7 for a thin follow-up session.** This is explicitly authorized. Flag the decision in the return report so the orchestrator can schedule the follow-up.

Signals that the valve should be used: wall-clock session duration exceeds 6 hours, or T4+T5+T6 adversarial review surfaces substantive findings that absorb more than 30 minutes of fix time.

### Explicitly out of scope

- Any migration on `trade_events.rationale` (kept TEXT per spec §6 non-migration statement; historical free-text rows coexist with new enum values).
- Backfilling historical rationale rows.
- Exit-form field preservation (spec §5 "Out of scope" — same latent gap, no live bug, deferred to §8).
- `TradeExitFormVM` preservation pattern even as a parallel refactor.
- An `ExitRationale` enum distinct from `ExitReason` (spec §3 "Known limitation" — deferred to §8).
- Generalized override-UX workstream beyond the single Force checkbox (spec §5 scope clarification).
- Any adjacent refactor, abstraction, or shared-base-class between `TradeEntryFormVM` and `TradeStopFormVM` — spec §5 "Rationale" explicitly rejects this at N=2.

If during implementation you find a tempting adjacent improvement, flag it in the return report rather than doing it.

---

## 2. Housekeeping commit (C0) — first commit of the session

### Task 2a — Track the session-3 brief

`docs/tranche-b-ops-session-3-brief.md` (this file) is untracked. Add it.

### Task 2b — Append Tranche B-ops deferred items to phase3e-todo.md

Phase3e-todo.md is the project's operational backlog (per CLAUDE.md). Items surfaced during Tranche B-ops sessions 1 and 2 belong here so they persist beyond the conversation. Append a new section at the end of the file (before any final separator if one exists; otherwise at the end):

```markdown
---

## Tranche B-ops deferred items (2026-04-24)

Items surfaced during Tranche B-ops sessions 1 (design) and 2 (execution) that were deliberately deferred. See the session-1 design spec §8 (`docs/superpowers/specs/2026-04-23-tranche-b-ops-session-1-design.md`) for full context on items marked (§8).

### From design (§8):

- **Pipeline-linkage bundle** — add `evaluation_run_id` FK on `pipeline_runs` + new `pipeline_chart_targets` table keyed on `(run_id, ticker)`. Would eliminate both chart-scope drift modes documented in spec §4 AND subsume the `insufficient-data` → `fetcher-failed` / `too-few-bars` split. Estimated ~1 pipeline-layer session. Phase 2 carve-out required.
- **Exit-form field preservation** — `TradeExitFormVM` has the same latent preservation gap as the stop form. No live bug; the spec scopes preservation specifically to the stop form. Low-effort follow-up.
- **ExitRationale enum distinct from ExitReason** — revisit when journal analysis produces evidence that `reason=partial|manual` rows corrupt downstream queries.
- **Total-book risk cap config** — `cfg.risk.max_total_risk_pct` + warn-coloring on the Open-risk tile. Deferred until evidence about the right default.
- **Book-equity-based Open-risk percent** — requires live prices in risk math. Current denominator is realized equity.
- **Chart-reason split: `insufficient-data` → `fetcher-failed` vs `too-few-bars`** — needs pipeline-layer per-ticker chart-status persistence. Subsumed by the pipeline-linkage bundle above.

### From Session 2 adversarial review:

- **Session-gating propagation for read-only surfaces** — `DashboardVM.stale_banner` currently does not propagate to watchlist/expand and other non-dashboard surfaces. Chart-scope resolver accepts the weekend/holiday drift for this reason. A future brainstorming session would design strict cross-UI session-gating. Spec-level decision required.
- **Transport/decode img failure fallback** — Session 2 C3 intentionally dropped `<img onerror>` per spec §4 rationale (transient static-mount errors "should page someone"). If real operational experience argues for a narrow client-side fallback distinct from the server-side intentional-absence states, reconsider. Low priority; monitor.

---
```

No other changes to phase3e-todo.md.

### C0 commit message

```
docs: track session-3 brief and capture tranche-b-ops deferred items in backlog

- Track docs/tranche-b-ops-session-3-brief.md (dispatch for this session).
- Append "Tranche B-ops deferred items (2026-04-24)" section to
  docs/phase3e-todo.md covering items from session-1 design §8 and
  session-2 adversarial-review follow-ups (session-gating propagation,
  img transport-failure fallback).
```

Ship C0 first, before any code commits.

---

## 3. Adversarial review — standing convention, baked in

After all code commits (C1–C4, or C1–C3 if you invoke the T7 early-return valve), run adversarial review on the combined code+test diff:

```bash
git diff <base-SHA>..HEAD -- swing/ tests/
```

where `<base-SHA>` is the commit immediately before C1 (i.e., C0's SHA).

Invoke `copowers:adversarial-critic` or follow the Session 2 pattern:

1. Run Codex MCP with the diff and request adversarial review (MIN=2, MAX=5 rounds — plugin defaults).
2. Iterate until `NO_NEW_CRITICAL_MAJOR` verdict.
3. **Fix findings in a new commit (C5), not by amending C1–C4.** CLAUDE.md's no-amending rule is binding. Accepted-with-rationale findings are fine — document the rationale in the return report rather than fixing.
4. Add regression tests for every fix, following the Session 2 pattern (at both VM and template layer where the finding crosses both).

### Watch items for adversarial review on this session

Based on the session's surface area, Codex is likely to probe:

- **Enum taxonomy completeness** — whether the 6+1 options cover the operator vocabulary. Accepted-with-rationale is appropriate per spec §3 "Rationale — taxonomy sizing." Do not expand the enum mid-session.
- **Provenance documentation** — whether the Provenance columns in the spec are reflected in code comments / docstrings naming which enum values came from repo-literal sources vs. operator-vocabulary expansions.
- **`other` validation layer placement** — route vs. VM builder. Follow `TradeEntryFormVM`'s existing validation pattern (orchestrator-resolved from spec §9: route-layer validation is the established pattern in this codebase).
- **Force checkbox auto-tick** — spec §5 is explicit: "Force is not auto-ticked by the re-render." Expect Codex to probe whether the preservation pattern accidentally ticks it.
- **Exit-rationale semantic thinness** — spec §3 "Known limitation" documents this as accepted cost. Do not re-open.
- **Migration concerns** — spec §6 non-migration statement is explicit. Do not re-open.

---

## 4. Task notes — orchestrator additions to the spec

The spec is authoritative. These are sequencing + judgment-call notes.

### C1 — T4 entry rationale enum (spec §7 T4)

- Define `EntryRationale` in `swing/trades/entry.py` (alongside existing `EntryRequest`). Values per spec §3: `aplus-setup`, `near-trigger-breakout`, `vcp-breakout`, `pivot-breakout`, `post-earnings-continuation`, `relative-strength`, `other`.
- Add a Provenance docstring on the enum class naming which values came from repo-literal sources (e.g., bucket names, Minervini trend-template criteria) vs. operator-vocabulary expansions. This closes the spec §3 provenance concern and reduces Codex review friction.
- `EntryRequest.rationale` stays `str` at the dataclass boundary (spec §6 service-layer impacts). Route handler and CLI do enum validation before constructing the request.
- `other` validation lives in the route handler per spec §3 "Decision — `other` ergonomics" and the orchestrator-resolved judgment call above. Return a 4xx with preserved field values on validation failure.
- Tests per spec §7 T4 acceptance criteria: non-enum value → 4xx/CLI error; `other` without `--notes` → error; valid enum value persists to `trade_events.rationale`; template renders the `<select>` with all seven options; `other` selection reveals the `notes` required-field visual (the HTML/JS toggle — verify it works in a TestClient HTML snapshot).

### C2 — T5 stop-adjust rationale enum (spec §7 T5)

- Mirror structure of T4. Define `StopAdjustRationale` in `swing/trades/stop_adjust.py`. Values per spec §3: `breakeven`, `trail-10ma`, `trail-20ma`, `weather-tighten`, `manual-trail`, `news`, `other`.
- Provenance docstring same pattern as T4.
- `StopAdjustRequest.rationale` stays `str` at the dataclass boundary.
- **T5 does NOT add the Force checkbox to the template** — that is T7's scope. T5 ships the rationale `<select>` only; T7 layers the Force checkbox and preservation fields on top.
- Tests per spec §7 T5 acceptance.

### C3 — T6 drop separate exit rationale (spec §7 T6)

- Per spec §3 "Decision — exit rationale: reuse `ExitReason`":
  - Drop the separate `rationale` input from `trade_exit_form.html.j2`.
  - Drop the `--rationale` option from `trade exit` CLI.
  - In the exit route handler and CLI command, write `req.reason.value` into `trade_events.rationale` automatically.
  - Keep `notes` for free-form context.
- Service-layer: `record_exit` signature does NOT change (it still accepts `rationale`); the route/CLI synthesizes `rationale=req.reason.value` before calling the service.
- This is a **deliberate accepted-cost decision** per spec §3 "Known limitation." Values like `partial` and `manual` will appear as rationale rows. Do NOT redesign the exit rationale schema in this task.
- Tests: form no longer has a rationale input; CLI `--rationale` is removed (flag `UsageError` if passed? Check click defaults); `trade_events.rationale` column receives `req.reason.value` on exit events.

### C4 — T7 stop-form field preservation + Force checkbox (spec §7 T7)

- Only begin T4 and T5 are committed (C1, C2). T7 depends on T5's rationale `<select>`.
- Preservation fields on `TradeStopFormVM` per spec §5: `new_stop_input`, `rationale`, `notes`, `force` with defaults `None | "" | "" | False`.
- Route error path: catch `StopRegressionError`, build VM populating preservation fields from submitted form, re-render with error banner. The pattern mirrors `TradeEntryFormVM` exactly — read that code as the template.
- Force checkbox: `<input type="checkbox" name="force">`. Default unchecked. On re-render, do NOT auto-tick. The operator must explicitly tick it to submit a regression-intentional stop.
- Tests per spec §7 T7 acceptance. Include:
  - Preservation of typed values across error re-render (all four fields).
  - Force checkbox default = unchecked.
  - Force checkbox not auto-ticked on error re-render.
  - Force ticked → `StopAdjustRequest(force=True)` → no `StopRegressionError` → success path.

---

## 5. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits (`feat(trades):`, `fix(web):`, `docs:`, etc. per CLAUDE.md). No Claude co-author footer. No `--no-verify`. No amending.
- **TDD:** red-green-refactor per task, per CLAUDE.md.
- **Tests:** fast suite green after every commit. Baseline going in: 546 passing (post-Session-2).
- **Ruff:** no new violations beyond the 81-error baseline.
- **Phase isolation:** implicit carve-out for this session on `swing/trades/entry.py` (T4 — add enum), `swing/trades/stop_adjust.py` (T5 — add enum). No `swing/data/` changes. No migrations.

---

## 6. Commit sequencing

1. **C0** — Housekeeping (docs only).
2. **C1** — T4 entry rationale (adds enum + validation + UI).
3. **C2** — T5 stop-adjust rationale (mirrors T4 pattern).
4. **C3** — T6 exit rationale drop (removal + automatic rationale synthesis).
5. **C4** — T7 stop-form preservation + Force checkbox (depends on C2).
6. **Adversarial review** — run on combined diff `<C0-SHA>..HEAD -- swing/ tests/`.
7. **C5** (if needed) — review fixes.

Run `python -m pytest -m "not slow" -q` and `ruff check swing/` after each code commit.

---

## 7. Done criteria

- C0 shipped (housekeeping).
- C1 + C2 + C3 shipped (rationale taxonomy cluster).
- Either: C4 shipped (T7 preservation complete), OR: T7 early-return valve invoked and flagged in return report.
- Adversarial review completed with `NO_NEW_CRITICAL_MAJOR` verdict.
- C5 shipped if review found fix-worthy findings.
- Fast suite green; no new ruff violations.
- Return report produced per §8.

---

## 8. Return report format

```
## Tranche B-ops session 3 return report

### Commits landed
- <SHA> docs: track session-3 brief and capture tranche-b-ops deferred items in backlog
- <SHA> feat(trades): constrain entry rationale to closed taxonomy (T4)
- <SHA> feat(trades): constrain stop-adjust rationale to closed taxonomy (T5)
- <SHA> feat(trades): drop separate exit rationale; synthesize from reason (T6)
- <SHA> feat(web): stop-form field preservation + Force checkbox (T7)  [or: "T7 deferred, see valve flag"]
- <SHA> fix(web): address tranche-b-ops session-3 adversarial review findings  [if C5 was needed]

### T7 early-return valve
<"Not invoked — T7 shipped as C4." OR "Invoked after C3. Rationale: <brief>. T7 deferred to thin follow-up session.">

### Tests
- Before: 546 passing, 0 failing (fast suite).
- After: <N> passing, 0 failing. New tests: <M>.
  - C1 (T4): <N> new tests
  - C2 (T5): <N> new tests
  - C3 (T6): <N> new tests
  - C4 (T7): <N> new tests  [if shipped]
  - C5 (review fixes): <N> new tests  [if shipped]

### Ruff
- No new violations (baseline 81 unchanged).

### Adversarial review — summary
- Rounds: <N>
- Base SHA: <C0's SHA>
- Thread ID: <from Codex MCP>
- Findings: <N> critical / <N> major / <N> minor
- FIXED: <short summary per fix>
- ACCEPTED-with-rationale: <short summary per acceptance; rationale preserved from spec or project constraints>
- Verdict: NO_NEW_CRITICAL_MAJOR at Round <N>

### Deviations from brief / spec
<Anything different from the brief or spec, and why. Empty if none.>

### Items flagged but not done (scope discipline)
<Any adjacent cleanup or enhancement noticed but deliberately not touched.>

### Open questions for orchestrator
<Anything the brief or spec under-specified; judgment calls made. Empty if none.>
```

---

## 9. If you get stuck

- If the Provenance-documentation approach doesn't fit cleanly as an enum docstring, try a module-level comment block adjacent to the enum. Do not create a separate provenance file — that's registry maximalism.
- If Codex review surfaces a spec-level design concern (e.g., "reconsider ExitRationale enum"), ACCEPTED-with-rationale is the correct response. The implementer does not re-open design decisions mid-execution-session; that's what the follow-up section in phase3e-todo.md is for.
- If a test you write passes against BOTH the pre-change and post-change code, rewrite the test — it's vacuous (see `memory/feedback_regression_test_arithmetic.md`).
- If the T7 preservation pattern would be cleaner via a shared base class between `TradeEntryFormVM` and `TradeStopFormVM`, do NOT create one. Spec §5 rejects this at N=2 explicitly. Mirror the pattern via copy — the fields differ enough that a shared base would impose more than it saves.
- If an acceptance criterion in spec §7 seems internally inconsistent with the §3/§5 decisions, the §3/§5 decisions win. §7 is implementation guidance; §3/§5 are the authoritative design.
- If the session is getting long and you're partway through T7, use the early-return valve per §1. Ship C1+C2+C3+C5(review), flag T7 deferred, and let the orchestrator schedule the thin follow-up.
