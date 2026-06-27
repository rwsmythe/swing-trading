# B-7 Operator Failure-Mode Classification -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the B-7 brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for **B-7 operator failure-mode classification** -- extend the CR.1 post-trade review surface so the operator can annotate **WHY a trade failed** (e.g. "stopped out on volatility", "thesis invalidated", "execution issue") for outcome-attribution analysis. This is the SECOND commissioned **Phase 15** arc (the schwabdev v3 + Fernet arc SHIPPED+CLOSED 2026-06-03 at `#20`). Its central design question is a **schema decision** (a new nullable `trades` column -> the FIRST v24, vs reuse) -- which is why it warrants a full copowers cycle.

**Brief:** `docs/b7-operator-failure-mode-brainstorming-dispatch-brief.md` (this file).

**Context:** Phase 14 CLOSED; the Phase-15 schwabdev-v3 arc CLOSED (`77d2747e`); main HEAD at this dispatch: see §8 (branch from it). ~7053 fast tests green on main. B-7 was the Phase-14 "FINAL TOUCH" deferred to Phase 15 (`phase3e-todo` `#5`/`#20`).

**Cumulative discipline:** the CLAUDE.md **Gotchas** block is BINDING (esp. the **Web/HTMX/forms** block for the review form + the **SQLite/migrations/schema** block for the v24 question); ~700+ cumulative ZERO Co-Authored-By; **Schema currently v23** -- B-7 likely bumps to **v24** (the FIRST schema migration since the schwabdev arc; re-exercises the backup-gate machinery -- confirm at brainstorm).

**Expected duration:** ~2-4 hours brainstorming + a Codex chain to convergence. Spec line target **~300-500 lines** (smaller than the schwabdev arc -- one focused feature).

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 WSL fallback (MCP `codex`/`codex-reply` PERMANENTLY DEAD in the VS Code extension -- do NOT attempt them).** VERIFIED-WORKING form (USE EXACTLY):
  ```
  wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'
  ```
  The PATH prefix is REQUIRED -- a bare `command -v codex` resolves to the DEAD Windows shim `/mnt/c/Users/rwsmy/AppData/Roaming/npm/codex` (`node: not found`); the `-ilc` login shell ALONE does NOT pick up node22. PROVE liveness with `codex --version` -> `codex-cli 0.135.0` (NOT `command -v codex`). Pre-generate the diff ON WINDOWS; tell Codex NOT to run git. PERSIST each round's PROMPT AND RESPONSE (incl. the literal `### Verdict`) to `.copowers-findings.md`. Memory `feedback_wsl_native_codex_invocation` (+ the 2026-06-03 prefix-required correction) + `feedback_implementer_persist_codex_responses`.
- Output: design spec at `docs/superpowers/specs/2026-06-03-b7-operator-failure-mode-design.md`.

---

## §0 Read first (in this order)
1. **THIS BRIEF end-to-end.**
2. **The CR.1 surface (re-grep each at writing-plans per discipline #2; these are the orchestrator-verified anchors):**
   - Review service: `swing/trades/review.py` -- `complete_trade_review()` (`:550-618`; the atomic per-trade review completion; the new failure-mode param threads through here), `MISTAKE_TAGS` (`:37-62`; the 34-tag/6-category vocab -- B-7 is ORTHOGONAL to this), `DISQUALIFYING_VIOLATIONS` (`:95-99`), `compute_process_grade()` (`:102-138`; NO change -- failure-mode is outcome-attribution, not grading).
   - Web route: `swing/web/routes/trades.py:2591-2608` (GET review) + `:2669-2799` (POST review -- the validation ladder + the `complete_trade_review` call).
   - Form: `swing/web/templates/partials/review_form.html.j2` (the fieldsets) + `swing/web/templates/review.html.j2`.
   - VM: `swing/web/view_models/trades.py:1224-1370` (`build_review_vm`) + the `ReviewVM` dataclass (`:1139-1222`).
   - The `Trade` dataclass + its review fields: `swing/data/models.py:214-223` (reviewed_at, mistake_tags, entry/management/exit/process_grade, disqualifying_process_violation, realized_R_if_plan_followed, mistake_cost_confidence, lesson_learned).
   - The review columns migration: `swing/data/migrations/0013_phase6_post_trade_review.sql` (the Phase-6 carve-out precedent).
3. **Schema mechanics:** `swing/data/db.py:51` (`EXPECTED_SCHEMA_VERSION = 23`); the latest migration `swing/data/migrations/0023_phase14_sb3_chart_surface_rename.sql` (the new-0024 template shape: `BEGIN; ...; UPDATE schema_version SET version = 24; COMMIT;`); the STRICT backup-gate (grep `_phase14_sb3_backup_gate` -- copy its `current_version == 23 AND target_version >= 24` clause shape for a new `_b7_backup_gate` / `_phase15_backup_gate`).
4. **CLAUDE.md -- the Web/HTMX/forms gotchas** (hx-headers HX-Request; 204 + HX-Redirect success; `... or None` for nullable CHECK columns; server-stamp audit envelope; the soft-warn confirm flow; the shared-`base.html.j2` VM-field-default gotcha) **+ the SQLite/migrations gotchas** (#9 executescript BEGIN/COMMIT; #11 Schema-CHECK + Python-constant + dataclass-validator in ONE task; the STRICT `pre_version == target-1` backup-gate) **+ the Windows ASCII gotcha #16/#32**. AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines".
5. **Memory:** the WSL Codex transport + persist-responses + round-limit-suspended + trailer-hazard + visual-gate (operator-witnessed browser for the review form) entries.

---

## §1 Pre-locked decisions + LOCKs (BINDING)
- **L1** Scope = **the failure-mode CAPTURE surface ONLY** -- the field (storage), the review-form UI to set it, the persistence through `complete_trade_review`, and its display on the review/journal read-back. Do NOT build the downstream metrics/analysis surface (the failure-mode distribution tile) in V1 -- that is a follow-on (OQ-5). Do NOT touch grading or the mistake-tags vocabulary.
- **L2** **Failure-mode is ORTHOGONAL to process-grade AND to mistake-tags** -- it answers "why did the trade fail" (thesis/market/execution), NOT "how well did the operator execute" (grades) NOR "what process mistakes were made" (mistake_tags). A trade can be an A-grade "good loss" (`failure_mode = thesis_invalidated`, zero mistakes) or a D-grade "bad loss" (`failure_mode = execution_issue`, several mistake_tags). The spec MUST preserve this separation -- do NOT fold failure-mode into the mistake-tags vocab or the grade computation.
- **L3 (PHASE-ISOLATION CARVE-OUT -- must be EXPLICIT in the spec)** B-7 TOUCHES the normally-read-only `swing/trades/review.py` + `swing/data/` (a new nullable `trades` column + a new migration + the `Trade` dataclass field + the `complete_trade_review` signature). The spec MUST explicitly scope this carve-out (exactly as Phase 6 scoped the original review carve-out). Default posture elsewhere stays read-only.
- **L4 (the SCHEMA question -- the design's center; operator-binding OQ-1)** there is NO reusable trade-level failure field today (`fills.reason` is per-leg free-text; `mistake_tags` is orthogonal). The RECOMMENDED design is a **new nullable `failure_mode` column on `trades`** (CHECK-constrained enum) -> a **v24 migration** -- the FIRST schema bump since v23. If v24: copy the STRICT backup-gate shape (`current_version == 23 AND target_version >= 24`), the BEGIN/COMMIT discipline, the `UPDATE schema_version SET version = 24`, AND **gotcha #11** -- the CHECK enum + the Python frozenset constant + the `Trade.__post_init__` validator land in ONE task. The brainstorm must formally weigh the alternatives (a new `failure_mode` mistake-tags CATEGORY = no schema change but violates L2 orthogonality; a free-text column = no enum/CHECK; a new side-table = overkill) and justify the choice.
- **L5** **Nullable + outcome-scoped** -- a winning trade has no failure mode. Decide (OQ-2): is `failure_mode` nullable + only solicited for losing/scratch trades, or always-solicited with an explicit `not_a_loss`/`n/a` sentinel? Either way the column is nullable (gotcha: `... or None`, NOT `... or ""`, for the CHECK-constrained enum).
- **L6** **Preserve every review-form gotcha** -- hx-headers HX-Request; 204 + HX-Redirect; 400 + re-render on validation failure; the server-stamped `auto_populated_field_keys_json` audit envelope; the at-least-one-mistake-tag validation pattern (mirror for failure-mode if required); the `... or None` nullable-CHECK persistence; the operator-witnessed BROWSER gate (the review form is HTMX -- TestClient cannot catch the browser-only failure surfaces; memory `feedback_visual_gate_both_render_and_browser`).

---

## §2 Spec scope to design
### §2.1 The failure-mode vocabulary (the core)
Design a small, CHECK-constrained enum of failure reasons (the operator's examples: "stopped out on volatility", "thesis invalidated", "execution issue"). Ground it in the project's frameworks (the Disciplined-Swing-Trader + Minervini source frameworks per memory `project_references`; the Qullamaggie KB MCP if useful) -- a failure-mode taxonomy distinct from the mistake-tags. Recommend a tight V1 set (~5-9 values) with clear, mutually-distinguishable semantics (market/thesis/execution/risk-event axes). Single-select (the PRIMARY failure reason) vs multi-select (OQ-3).

### §2.2 The schema design (L4)
The new nullable `failure_mode` column on `trades`; the v24 migration shape; the `Trade` dataclass field + `__post_init__` frozenset validation; the Python constant (the canonical `FAILURE_MODES` frozenset) -- ALL in one task (#11). The read-path `_row_to_trade` mapper widened in the same task.

### §2.3 The review-form UX
Where on `review_form.html.j2` the failure-mode control sits (a `<select>` near the grades, or its own fieldset); the GET render (ReviewVM default) + the POST param + the validation; required-vs-optional (L5/OQ-2); the soft-warn/confirm interaction if any. The display-only read-back on the review page + the journal trade detail.

### §2.4 The orthogonality contract (L2)
Spell out, in the spec, that failure-mode does NOT feed `compute_process_grade`, is NOT a mistake-tag, and is independently queryable -- with a test asserting a grade-A trade can carry a non-null failure_mode and vice-versa.

### §2.5 Test + gate strategy
The migration round-trip + v23->v24 backup-gate test (run-migrate-twice no-op); the CHECK + frozenset + dataclass-validator consistency tests (#11); the review-form POST persistence test (nullable -> NULL, valid enum -> stored, invalid -> 400); the orthogonality test; the operator-witnessed BROWSER gate on the review form (set a failure-mode on a real closed trade, submit, see it persist + display). Enumerate the gate.

---

## §3 Open questions (Codex surfaces; operator triage at writing-plans)
1. **OQ-1 schema** -- new nullable `failure_mode` column -> v24 (recommend) vs reuse/free-text/side-table. Operator-binding (the first v24).
2. **OQ-2 scope of solicitation** -- losing/scratch-only (nullable, unsolicited on winners) vs always-solicited with an `n/a` sentinel. Operator UX.
3. **OQ-3 cardinality** -- single primary failure-mode (recommend) vs multi-select.
4. **OQ-4 the vocabulary** -- the exact enum value set + labels (operator-binding; it is the operator's own attribution language).
5. **OQ-5 read/analysis surface** -- V1 capture-only (recommend) vs also a failure-mode distribution metrics tile (defer to a follow-on).
6. **OQ-6 backfill** -- do existing reviewed trades get a one-time failure-mode backfill prompt, or is the field only solicited going forward (recommend forward-only; existing rows stay NULL)?
7. **OQ-7 required-or-optional at submit** -- if losing-trade, is failure-mode REQUIRED (like the at-least-one-mistake-tag rule) or optional?

---

## §4 OUT OF SCOPE (do not design into V1)
- The downstream failure-mode metrics/distribution surface (OQ-5; a follow-on).
- Any change to the grade computation, the mistake-tags vocab, or the disqualifying-violations set (L2).
- The deferred ExitRationale-vs-ExitReason enum split / the fill-level `reason` rework (a separate Tranche-B-ops item).
- Any Schwab/L2-lock surface (B-7 is review-only -- the L2 LOCK is untouched).
- A multi-version schema jump (v24 only; STRICT backup-gate).

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **Schema atomic-consistency (#11)** -- the CHECK enum + the `FAILURE_MODES` frozenset + the `Trade.__post_init__` validator + the `_row_to_trade` read mapper are all designed to land in ONE task; the v24 backup-gate uses STRICT `== 23`.
2. **Orthogonality (L2)** -- failure-mode is provably separate from grade + mistake_tags (a test proves it).
3. **Nullable-CHECK persistence** -- `... or None` (not `... or ""`) for the enum column; empty-submit -> NULL test.
4. **Review-form gotchas (L6)** -- hx-headers; 204+HX-Redirect; 400+re-render; the audit envelope round-trips; the browser gate is declared binding (HTMX surfaces TestClient cannot catch).
5. **Carve-out explicitness (L3)** -- the spec names the read-only carve-out for `swing/trades/` + `swing/data/`.
6. **The vocabulary is tight + mutually-distinguishable** + grounded, not arbitrary.
7. ASCII (#16/#32); Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose).

---

## §6 Deliverable shape
**Design spec at `docs/superpowers/specs/2026-06-03-b7-operator-failure-mode-design.md`** (mirror the prior brainstorm spec format): §1 Architecture overview · §2 Pre-locked decisions + L1-L6 · §3 The failure-mode vocabulary · §4 Schema design (the v24 column + #11 consistency) · §5 The review-form UX · §6 The orthogonality contract · §7 Test strategy + the operator browser gate · §8 Schema impact (v23 -> v24) · §9 Sub-bundle/slice recommendation · §10 V1 simplifications + V2 candidates (the analysis surface) · §11 Operator decision items (the OQs) · §12 Cumulative discipline compliance · §13 Position note (Phase-15 second arc; capture-only; analysis surface follows).

**Target ~300-500 lines.** Commit stem: `docs(b7-spec): brainstorm <draft|R1|...> -- ...` (final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- If a cited file:line no longer matches the live tree, TRUST the tree + re-grep (this brief cites the dispatch HEAD; line numbers shift).
- If the schema seems to need MORE than one nullable column (e.g. a free-text "failure notes" alongside the enum), that is a legitimate design call -- weigh it as part of OQ-1, do not silently expand.
- If failure-mode appears to want to feed the grade or the mistake-tags, STOP -- that violates L2; keep it orthogonal.
- HOLD THE LINE: capture-only V1; orthogonal to grades/mistakes; nullable-CHECK + #11 atomic consistency; the operator-witnessed browser gate is binding.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL prefix form (verify `codex --version`).
- This is BRAINSTORMING ONLY -- produce the design spec + OQs; do NOT write code, do NOT enter writing-plans.

---

## §8 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `b7-operator-failure-mode-brainstorming`. Dir `.worktrees/b7-operator-failure-mode-brainstorming/`. **Branch from main HEAD = the commit that ADDS this brief** (on top of `77d2747e`; the orchestrator states the exact SHA in the inline prompt -- the worktree MUST contain this brief). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). Prefix git/test commands with `cd <worktree> &&` and re-check `git branch --show-current` before each commit.
- **Codex chain count:** SINGLE chain at end, run to convergence via the WSL prefix form (verify `codex --version` first; transcript -> `.copowers-findings.md`).

---

## §9 Return report shape
Mirror the prior brainstorm return reports: final HEAD + commit breakdown; the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict`); spec line count + per-section; L1-L6 verbatim verification; the OQs resolved/deferred (flag OQ-1 schema/v24, OQ-2 solicitation scope, OQ-4 the vocabulary, OQ-7 required-or-optional for the operator); the schema verdict (v23 -> v24 -- the FIRST migration since the schwabdev arc; confirm the backup-gate shape); Codex Majors accepted (ZERO preferred); V1 simplifications + V2 candidates (the analysis surface); the orthogonality contract; the carve-out scoping (L3); cumulative gotcha application (the form + migration checklists); ZERO Co-Authored-By confirmation; worktree teardown status; writing-plans dispatch-readiness.

---

*End of brief. B-7 operator failure-mode classification brainstorming dispatch (the SECOND Phase-15 arc) -- design the post-trade failure-mode CAPTURE surface: a tight CHECK-constrained `failure_mode` enum on `trades` (a new nullable column -> the FIRST v24 migration; recommend), the review-form UI to set it, persistence through `complete_trade_review`, and the read-back display -- KEPT ORTHOGONAL to process-grade and to the mistake-tags vocab (a "good loss" vs "bad loss" distinction). Capture-only V1; the failure-mode analysis surface is a follow-on. The binding gate is an operator-witnessed browser submit on a real closed trade. OUTPUT: a design spec the writing-plans phase can derive a plan from.*
