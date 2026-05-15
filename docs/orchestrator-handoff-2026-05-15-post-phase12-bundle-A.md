# Orchestrator handoff — 2026-05-15 (post-Phase-12-Sub-bundle-A-merge; Phase 11 CLOSED + Phase 12 30% shipped)

You are taking over as orchestrator for the Swing Trading project at the **post-Phase-12-Sub-bundle-A-merge** breakpoint. The Schwab API integration arc (Phase 11) is fully CLOSED; Phase 12 has shipped its first sub-bundle (Tier 1 operational-pain unblock for daily Schwab CLI use). Phase 12 Sub-bundle B (bundled web-UI-friendliness mini-bundle) is UNBLOCKED + queued as the next operator-paced dispatch; Sub-bundle C (auto-correct journal-from-Schwab service — the architectural pivot) is queued after.

The prior orchestrator is handing off NOW because:
1. **Clean breakpoint** — Phase 12 Sub-bundle A fully shipped + integrated + housekeeping landed; gate passed live against operator's production Schwab credentials with one orchestrator-inline gate-fix.
2. **Architectural pivot just banked** — substantial Phase 12 Sub-bundle C scope (auto-correct journal-from-Schwab service) became clear during the gate's discrepancy investigation; benefits from a fresh-context orchestrator owning the dispatch from brainstorm onward.
3. **Sub-bundle B scope is well-defined for fast follow-up** — bundled "credentials-in-file + web OAuth setup form" mini-bundle; implementer-dispatch-ready when operator commissions.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). You will NOT see SessionStart claude-mem injection blocks. Do NOT attempt `mcp__plugin_claude-mem_mcp-search__*`. Auto-memory dir (`~/.claude/projects/c--Users-rwsmy-swing-trading/memory/MEMORY.md` + linked files) IS still loaded.

**Chrome MCP is AVAILABLE** for browser-driven gates. Use port 8081 for any worktree-side `swing web` to avoid colliding with operator's main-HEAD `swing web` on 8080.

**Fast suite runs `-n auto` by default** at ~68s wall-clock post-Phase-12-Sub-bundle-A (3791 tests on main HEAD).

**Operator dispatches implementers themselves** (per durable preference `feedback_orchestrator_vs_implementer_execution.md`). Orchestrator drafts the brief + provides inline dispatch prompt as fenced code block; operator dispatches when ready.

**Always provide an inline dispatch prompt** with every brief (per durable preference `feedback_always_provide_inline_dispatch_prompt.md`).

**Operator-paired gate driving — one command at a time** (operator's stated preference 2026-05-15). When driving the operator-witnessed gate, send ONE command per orchestrator turn, wait for output, verify, send the next. Don't batch 5 commands at once.

## Step 1 — Read these in order

1. **This brief end-to-end** — captures post-Phase-12-Sub-bundle-A-merge state + Sub-bundle B + C dispatch readiness + the gate-caught defect + the architectural-pivot bank.

2. **`CLAUDE.md` status line** — single-paragraph; updated through Phase 12 Sub-bundle A SHIPPED at `bbfcbc8`. **Authoritative current-state summary.** Includes both V2 candidates banked for Phase 12 (architectural pivot + credentials-in-file).

3. **`docs/phase3e-todo.md`** top entries 2026-05-15 — read in TOP-DOWN order:
   - **Web-UI OAuth paste-back form** (Phase 12 Sub-bundle B refinement; bundle with credentials-in-file)
   - **Schwab CLIENT_ID + CLIENT_SECRET in user-config.toml** (the credentials-in-file bank)
   - **ARCHITECTURAL: reconciliation must auto-correct journal-from-Schwab** (Phase 12 Sub-bundle C headline)
   - **`cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` regex** (closed by 12A T-A.4 — historical at this point)
   - **Pipeline run on empty finviz inbox** (open follow-up bug; ~1-line fix candidate)
   - **Pipeline run on missing finviz inbox folder** (closed by 2026-05-15 #3 fix at `6ea94f7` — historical)
   - **Phase 12 Sub-bundle A SHIPPED entry**
   - **Phase 11 CLOSED entry** (Sub-bundle D)

4. **`docs/orchestrator-context.md`** — durable orchestrator-role conventions. Section "Lessons captured" updated 2026-05-15 with two NEW high-value lessons:
   - Operator-paired-gate-caught implementation gap → orchestrator-inline gate-fix precedent (now 2 instances: `34be84e` + `e2c0384`)
   - Operator architectural pushback supersedes orchestrator scope assumptions; reframe before bandaging
   "Currently in-flight work" section is heavily stale (says "as of 2026-05-11"); a 2026-05-15 pointer block at the top redirects to CLAUDE.md status line + phase3e-todo. Treat the older narrative entries as historical only.

5. **`docs/phase12-bundle-A-schwab-operational-pain-executing-plans-dispatch-brief.md`** (`892e3e3`) — most recent dispatch brief; format precedent for Phase 12 Sub-bundle B brief drafting.

6. **`docs/phase12-bundle-A-return-report.md`** (on main post-merge) — implementer return report; §6 watch items + per-task LOCKED dispositions (T-A.2 audit-row disposition; T-A.4 regex disposition).

7. **`docs/orchestrator-handoff-2026-05-14-post-bundle-B.md`** (the prior orchestrator handoff) — historical; format precedent for THIS handoff.

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10                    # expect b13fcc5 at HEAD (or later if operator landed follow-on commits)
git status                               # expect clean (some untracked operator artifact dirs OK)
git worktree list                        # expect main + 1 husk (.worktrees/phase12-bundle-A-schwab-operational-pain) — operator may have already cleaned via cleanup-locked-scratch-dirs.ps1 -DeregisterFirst
python -m pytest -m "not slow" -q | tail -5     # expect ~3791 fast pass + 3 pre-existing test_phase8_pipeline_walkthrough failures + 1 skipped (flag-classifier only; xdist scheduling may show 3 or 4 failed depending on the flaky setup CLI test)
ruff check swing/ --statistics | tail -3        # expect 18 E501
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 18
```

Expected state on main HEAD (`b13fcc5` or later):
- Phase 11 (Schwab API) CLOSED at `e51e6eb`. Arc aggregate: 4 sub-bundles A+B+C+D / ~85 commits / ~17 Codex rounds / +447 fast tests / ZERO Critical / 5 ACCEPT-WITH-RATIONALE / 12 NEW CLAUDE.md gotchas / schema v17→v18.
- Phase 12 Sub-bundle A SHIPPED at `123d27a`. 12 commits / 3 Codex rounds + 1 orchestrator-inline gate-fix `e2c0384` / +35 fast tests / ZERO ACCEPT-WITH-RATIONALE / 2 banked V2 candidates. Schema v18 unchanged (consumer-side only).
- Schema v18.

## Step 3 — Phase 12 state at handoff

### Commit chain since prior orchestrator handoff (2026-05-14)

```
b13fcc5 docs(phase3e-todo): bank web-UI OAuth paste-back form (Phase 12 Sub-bundle B refinement; bundle with credentials-in-file)
bbfcbc8 docs(CLAUDE): refresh status line with Phase 12 Sub-bundle A SHIPPED + 2 banked V2 candidates
db55e39 docs(phase3e-todo): Phase 12 Sub-bundle A SHIPPED entry + bank Schwab credentials-in-file V2 path
123d27a Merge phase12-bundle-A-schwab-operational-pain into main: Phase 12 Sub-bundle A SHIPPED
75b876c docs(phase3e-todo): refine reconciliation pivot to three-tier resolution model (operator clarification 2026-05-15)
28a7d01 docs(phase3e-todo): bank ARCHITECTURAL pivot — reconciliation must auto-correct journal-from-Schwab (Phase 12 Sub-bundle C headline)
e2c0384 fix(phase12-bundle-A): orchestrator-inline gate-fix — wire schwab_client into Sub-bundle B pipeline-step callsites (T-A.3 acceptance #4 closer)
55e77b9 docs(phase3e-todo): bank empty-finviz-inbox auto-fetch bug
... (12 implementer commits 74d3fea..2cbb8c4 for Phase 12 Sub-bundle A T-A.1..T-A.4)
892e3e3 docs(phase12): Phase 12 Sub-bundle A executing-plans dispatch brief
... (4-commit batch 6acdbba..4834c42 for Phase 11 close housekeeping + finviz-inbox-mkdir fix + cleanup-script regex bank)
```

### Phase 12 sub-bundle status

| Sub-bundle | Status | Branch / Merge SHA | Tasks | Tests delta | Codex rounds | Notes |
|---|---|---|---|---:|---:|---|
| **A** operational-pain | ✅ SHIPPED 2026-05-15 | `123d27a` | 4 (T-A.1..T-A.4) | +35 net | 3 + 1 inline | Env vars + setup self-healing + pipeline env-var wiring + cleanup-script regex; daily-CLI-use unblock |
| **B** web-UI-friendliness | 🟡 UNBLOCKED — your first dispatch | TBD | ~5-7 (TBD at brief drafting) | +12-18 projected | 2-3 estimated | Bundled credentials-in-file + web OAuth setup form per phase3e-todo top entries; Option A (paste-back form) for V1; Option B (HTTPS callback handler) banked V2 |
| **C** auto-correct service | ⏸ BLOCKED on B (recommended sequencing) | TBD | TBD (substantial brainstorm needed) | TBD; substantial | 4-6 estimated brainstorm + 4-6 writing-plans + multi-bundle execution | Architectural pivot — three-tier resolution model; closes the discrepancy stream as a category |

Recommended dispatch sequencing (operator-confirmed 2026-05-15): A → B → C. Sub-bundle B is small + immediate UX win; Sub-bundle C is substantial + benefits from B's surfaces being in place first.

### Production state at handoff

- **Schema:** v18 (unchanged since Phase 11 Sub-bundle A T-A.7).
- **Tests:** ~3791 fast passing on main.
- **Production tokens DB:** `~/swing-data/schwab-tokens.production.db` exists; refresh-token clock started 2026-05-15T03:59:25 UTC during 12A S4 self-healing test; **expires ~2026-05-22**. Operator must re-auth before then OR Sub-bundle B/C gate sessions need rescheduling.
- **Production discrepancy state:** 30 `acknowledged_immaterial` + 8 `journal_corrected` + **3 unresolved material (39/40/41)** from pipeline #63's reconciliation_run #10. **These are LEFT UNRESOLVED by design** — they're correct signal of fiction-vs-truth divergences in operator-typed-from-memory fills (`reconciliation_status='unreconciled'` + `tos_match_id=NULL` on all three; yesterday's operator resolutions only marked-as-resolved without correcting underlying fills). Phase 10 dashboard banner shows "3 unresolved" — that's accurate state. Will be auto-corrected categorically when Phase 12 Sub-bundle C ships.
- **Production schwab_api_calls:** 38 rows (mix of refresh + snapshot + orders + transactions + sandbox + setup-self-healing audit + pipeline-side calls 35-38).
- **Production reconciliation_runs:** 10 (7 TOS-CSV + 3 schwab_api).
- **Worktree husks:** likely 1 pending (`.worktrees/phase12-bundle-A-schwab-operational-pain/`); operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` recognizes this name (`phase12-*` matches existing regex post T-A.4 fix); should clean cleanly.

### Phase 12 Sub-bundle A forward-binding lessons (for any future Schwab work)

Per `docs/phase12-bundle-A-return-report.md` + the orchestrator-context.md "Lessons captured" updates from this dispatch:

1. **Operator-paired-gate-caught implementation gap → orchestrator-inline gate-fix precedent** (now 2 instances: B `34be84e` camelCase kwarg defect + 12A `e2c0384` snapshot/orders callsite wiring defect). When defect is small + structural + has clear discriminating signal, inline-fix on the worktree branch with a regression test is appropriate; integration merge folds it in via `--no-ff`. Saves a full implementer cycle vs re-dispatch.
2. **Operator architectural pushback supersedes orchestrator scope assumptions** — when operator pushes back on framing, REFRAME forward, don't defend the tactical patch. (Source: 2026-05-15 reconciliation pivot conversation.)
3. **Implementer test-coverage gap surface:** helper-return-contract tests don't catch runner-level integration gaps. T-A.3 implementer's +5 helper tests (return-value contract for `_construct_pipeline_schwab_client`) all passed; orchestrator-inline gate-fix added a runner-level source-pattern regression test that explicitly rejects the pre-fix `client=None, surface="pipeline"` shape. **Brief-drafting note for future similar dispatches:** when extending a helper that's consumed at multiple callsites, briefs should include integration tests at the callsite level OR explicit source-level regression tests pinning the consumer wiring.
4. **`acknowledged_immaterial` is the wrong label when broker data is authoritative.** Bury this resolution-enum value as Phase 12 Sub-bundle C lands the auto-correct service; for V1, leave it in place as a back-compat path for legitimate "Schwab data itself is wrong" override cases. (Architectural insight from 2026-05-15 reconciliation pivot.)

### Cross-bundle pin status

**ZERO cross-bundle pins remaining.** Phase 11 Sub-bundle C closed both T-C.5 + T-C.7 pins; Phase 12 Sub-bundle A introduced no new cross-bundle pins.

### V2 candidates banked from Phase 12 Sub-bundle A (operator-action follow-ups, not orchestrator-blocking)

Per phase3e-todo Phase 12 Sub-bundle A SHIPPED entry + the implementer return report:

1. **`oauth.tokens_db_rename` dedicated endpoint enum value** for T-A.2 audit row (currently uses `oauth.code_exchange` with descriptive `error_message`; would require schema v18→v19 to add new enum value). Cosmetic; banked.
2. **Unify `logout` `revoke_and_delete` timestamp to UTC.** Cosmetic; banked.

### Operator-action items pending post-handoff (NOT orchestrator-blocking)

1. **Worktree husk cleanup** — `.worktrees/phase12-bundle-A-schwab-operational-pain/` likely ACL-locked. Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` (elevated PowerShell) at convenience. **NEW since 12A T-A.4 fix:** the `-DeregisterFirst` regex now matches both `phase\d+-*` AND `schwab(?:-\w+)?-bundle-` patterns; should clean cleanly without manual `git worktree remove --force` workaround.
2. **3 unresolved material discrepancies (39/40/41)** — leave alone; correct signal pending Sub-bundle C auto-correct service.
3. **7-day refresh-token clock expires ~2026-05-22** — operator may need to re-run `swing schwab setup` paste-back if Sub-bundle B/C gate sessions land later. Sub-bundle A's T-A.2 self-healing means the recovery is one CLI invocation (no `logout → setup` workaround needed).
4. **Empty-finviz-inbox auto-fetch bug** banked as 2026-05-15 phase3e-todo entry; ~1-line fix; could fold into Sub-bundle B or be a standalone polish dispatch.

## Step 4 — Phase 12 Sub-bundle B dispatch brief drafting (your first major deliverable)

Sub-bundle B is the **bundled web-UI-friendliness mini-bundle**: credentials-in-file (`user-config.toml` cascade) + web OAuth setup form (`GET/POST /schwab/setup`). Per the two top phase3e-todo entries dated 2026-05-15. Operator-locked sequencing: Sub-bundle B before Sub-bundle C.

### What the Sub-bundle B dispatch brief MUST include

Mirror `docs/phase12-bundle-A-schwab-operational-pain-executing-plans-dispatch-brief.md` structure (365 lines; 10 sections; brief plays plan-role since brainstorm + writing-plans skipped per operator scope decision precedent). Must consume:

1. **§0 reads:** the two top phase3e-todo entries (web-UI OAuth + credentials-in-file) as binding §0 design source — they spec the cascade design + the form architecture + acceptance criteria + cross-references.
2. **§0.4 BINDING forward-binding lessons:** all Phase 11 (5+7+5+0) + Phase 12 Sub-bundle A (4 NEW) cumulative. Especially the operator-paired-gate-caught-defect precedent (orchestrator pre-empts by writing runner-level integration test for the credential cascade BEFORE the implementer ships).
3. **§0.5 Codex pre-emption table** — extend Phase 12 Sub-bundle A's patterns with NEW Sub-bundle B-specific patterns (HTMX form-driven failure surfaces per Phase 5 R1 M1+M2 + Phase 6 I3; cycle-cascade no-op skip checks; sentinel-leak audit extension to cover cfg-cascade-sourced credentials).
4. **§0.6 inter-bundle dependencies** — Sub-bundle A's `resolve_credentials_env_or_prompt` helper EXTENDS to add user-config.toml tier (don't re-implement; mirror Phase 11 single-Client-instance discipline pattern). Sub-bundle A's `setup_paste_flow` service-layer function REUSED VERBATIM by web POST handler.
5. **§2 NO operator-paired Task 0.b session required** (no new schwabdev call surfaces; web form just wraps existing CLI flow).
6. **§3 per-task scope** — likely 5-7 tasks: T-B.1 cascade extension; T-B.2 SchwabConfig + FIELD_REGISTRY extension; T-B.3 `swing config set` cascade emitter; T-B.4 web `GET/POST /schwab/setup` route + template + view-model; T-B.5 cycle-checklist + CLAUDE.md updates; T-B.6 sentinel-leak audit extension; T-B.7 (optional) `GET /schwab/status` web counterpart.
7. **§4 operator-witnessed verification gate** — bundle credentials-in-file + web OAuth surfaces; ~5-7 surfaces total. S-credentials-in-file: operator sets credentials via `swing config set integrations.schwab.client_id <value>` + `client_secret <value>` + verifies `swing config show` shows masked values. S-web-OAuth-setup: operator visits `http://127.0.0.1:8080/schwab/setup` + clicks authorize link + completes OAuth in new tab + pastes callback URL into form + submits + verifies fresh tokens DB written. NOTE: S-web-OAuth-setup is destructive (consumes a re-auth cycle).

### Sub-bundle B task summary (anticipated; finalize at brief-drafting time)

5-7 tasks; ~+12-18 fast tests projected:

| Task (anticipated) | Scope | Tests | Files touched |
|---|---|---:|---|
| T-B.1 | `resolve_credentials_env_or_prompt` cascade extension (env vars > user-config.toml > prompt) | +4 | `swing/integrations/schwab/auth.py` (extend) |
| T-B.2 | `SchwabConfig` + `FIELD_REGISTRY` extension (`client_id` + `client_secret` fields with `masked=True`) | +3 | `swing/config.py` |
| T-B.3 | `swing config set integrations.schwab.client_id` + `client_secret` cascade emitter wires | +2 | `swing/cli.py` (extend config-set group) |
| T-B.4 | Web `GET/POST /schwab/setup` route + template + `SchwabSetupVM` (HTMX-friendly per Phase 5+ failure-surface gotchas) | +6 | `swing/web/routes/schwab.py` (NEW) + template + view-model |
| T-B.5 | Cycle-checklist + CLAUDE.md updates | 0 | `docs/cycle-checklist.md` + `CLAUDE.md` |
| T-B.6 | Sentinel-leak audit extension for cfg-cascade-sourced credentials | +2 | `tests/integrations/test_schwab_token_redaction_audit.py` (extend) |
| T-B.7 (optional) | `GET /schwab/status` web counterpart | +3 | `swing/web/routes/schwab.py` (extend) |

### Where the Sub-bundle B dispatch brief MUST defend against the 12A T-A.3 implementer gap

The 12A gate caught the implementer's helper-return-contract tests passing while the runner-level callsite wiring was wrong. Sub-bundle B's web POST handler is a similar pattern — `setup_paste_flow` is reused (correct) BUT the route handler must wire credentials from the cascade THEN invoke `setup_paste_flow` THEN handle response. Brief MUST include integration test at the route level (TestClient against `POST /schwab/setup` with mocked credentials cascade; assert `setup_paste_flow` called with correct args) — not just helper-return-contract tests for the cascade extension.

## Step 5 — Phase 12 Sub-bundle C dispatch (FUTURE; after B ships)

The architectural pivot. **NOT for your first dispatch.** When operator commissions, Sub-bundle C will need:
1. **Brainstorm** (4-6 Codex rounds expected) — formalize the three-tier resolution model + ambiguity classifier + audit-history schema design.
2. **Writing-plans** (4-6 Codex rounds expected) — multi-sub-bundle decomposition; substantial; expect 1500-2500 line plan.
3. **Multi-bundle executing-plans** — likely 3-4 sub-sub-bundles within Sub-bundle C.

Per phase3e-todo "ARCHITECTURAL: reconciliation must auto-correct journal-from-Schwab" entry, the architectural changes required:
- New ambiguity classifier (`auto_correctable` / `ambiguous` with structured `ambiguity_kind` enum / `unsupported`).
- New service-layer auto-correction module (transactional, validator-respecting, audit-aware).
- New audit-history table OR `event_log` extension for pre/post journal value preservation.
- Tier-2 ambiguity-resolution UI/CLI (operator-facing surface with type-specific resolution choices).
- Reconciliation flow pivot from "emit + wait" to "classify + dispatch + apply".
- `fills.reconciliation_status` enum change.
- NO magnitude-based threshold (determinism is the axis, not delta size).
- Backfill path for existing unresolved discrepancies (39/40/41 + future).
- Fill auto-population at trade-entry time (closes the entire discrepancy stream as a category; could be its own sub-sub-bundle).

## Step 6 — Operator preferences (durable; carry over)

- **Implementer-dispatch is the default** per `feedback_orchestrator_vs_implementer_execution.md`.
- **Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."
- **Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly** (binding convention).
- **Implementer runs adversarial-critic via `copowers:executing-plans` wrapper.**
- **Multi-choice format for design questions** (AskUserQuestion preferred).
- **Spec is canonical over brief on cosmetic typos.**
- **Production-write classifier soft-block** — Sub-bundle B's web OAuth POST writes to `schwab_api_calls` audit + tokens DB; may trigger soft-block at gate time. Operator pre-authorizes via gate-path AskUserQuestion or plain-chat "yes" if classifier blocks.
- **Always provide an inline dispatch prompt** (per `feedback_always_provide_inline_dispatch_prompt.md`).
- **Operator-paired gate driving — one command at a time.** When driving a gate, send ONE command per turn, wait for output, verify, send the next. Don't batch.
- **Stop the web server when done** — worktree-side `swing web` MUST use `--port 8081` if operator's main session uses 8080.

## Step 7 — When Sub-bundle B dispatch brief gets drafted

Threading reminders:

1. **HTMX form-driven failure surfaces** — Sub-bundle B introduces NEW HTMX surfaces (`POST /schwab/setup`). Per Phase 5 R1 M1+M2 + Phase 6 I3 CLAUDE.md gotchas: embedded form `hx-headers='{"HX-Request": "true"}'` propagation; success-path `204 No Content` + `HX-Redirect: /schwab/status` (NOT 303 swap); HX-Redirect target route MUST exist (TestClient assertion).
2. **`SchwabSetupVM` extends base layout** — must add any NEW fields to ALL base-layout VMs per CLAUDE.md gotcha "base.html.j2 is shared".
3. **T-A.2 self-healing applies identically** — web POST handler invokes `setup_paste_flow` which already does the auto-rename. Don't re-implement.
4. **Sentinel-leak audit extension** — cfg-cascade-sourced credentials (new in B) must register in Layer 0 known-secret registry BEFORE any schwabdev call fires.
5. **Operator-paired gate is destructive** (re-auth consumed). Operator should be ready to paste-back when S-web-OAuth-setup runs.

## Step 8 — When Sub-bundle C dispatch happens (FUTURE)

Threading reminders for the Sub-bundle C brainstorm brief (when operator commissions):

1. **Schwab data IS truth** — design from this premise; do NOT re-litigate.
2. **Three-tier resolution model** (auto-correct > ambiguity-surfaced > operator-override) per phase3e-todo entry.
3. **Magnitude is the wrong axis** — determinism is the axis; no threshold gates.
4. **`acknowledged_immaterial` enum value** stays as back-compat for legitimate "Schwab is wrong" override cases; new discrepancies use the new enum values (`auto_corrected_from_schwab` / `pending_ambiguity_resolution` / `operator_resolved_ambiguity` / `operator_overridden`).
5. **Backfill path for existing unresolved 39/40/41** — when Sub-bundle C ships, run classifier across them; tier-1 cases auto-apply; tier-2 cases queue for operator decision.
6. **Fill auto-population at trade-entry time** is a separate sub-sub-bundle worth scoping at brainstorm — closes discrepancy stream as a category, not one-at-a-time.

## Step 9 — Quick reference summary

| Artifact | Path / commit |
|---|---|
| Phase 12 Sub-bundle A executing-plans brief | `docs/phase12-bundle-A-schwab-operational-pain-executing-plans-dispatch-brief.md` (`892e3e3`) |
| Phase 12 Sub-bundle A return report | `docs/phase12-bundle-A-return-report.md` (on main post-merge) |
| Phase 12 Sub-bundle A integration merge | `123d27a` |
| Phase 12 Sub-bundle A orchestrator-inline gate-fix | `e2c0384` |
| Phase 12 Sub-bundle A SHIPPED entry | phase3e-todo top SHIPPED-band entry @ `db55e39` |
| Phase 11 Sub-bundle D / arc closure entry | phase3e-todo (closed at `e51e6eb`; SHIPPED entry below 12A) |
| ARCHITECTURAL pivot bank (Sub-bundle C headline) | phase3e-todo top entry @ `28a7d01` + `75b876c` |
| Credentials-in-file bank (Sub-bundle B headline #1) | phase3e-todo top entry @ `db55e39` |
| Web OAuth paste-back form bank (Sub-bundle B headline #2) | phase3e-todo top entry @ `b13fcc5` |
| Sub-bundle B executing-plans brief | TBD (your first deliverable) |
| Sub-bundle C brainstorm brief | TBD (deferred) |
| Cross-phase backlog | `docs/phase3e-todo.md` (active; archive at `docs/phase3e-todo-archive.md`) |
| Orchestrator-role context | `docs/orchestrator-context.md` (updated 2026-05-15 with new lessons) |

## Step 10 — Closing note from prior orchestrator

This handoff caps a productive session that drove Phase 12 Sub-bundle A from operator-dispatch through gate to merge, plus a substantial architectural conversation that reframed the reconciliation system's intent.

**Key story arcs of this session:**

1. **T-A.3 implementer gap caught at gate** — implementer wired env-var helper into market-data ladder but missed the parallel wiring into Sub-bundle B's snapshot/orders callsites. Pipeline #62 ran with ZERO new schwab_api_calls despite env vars set. Orchestrator-inline gate-fix at `e2c0384` (mirror of B's `34be84e` precedent). Pipeline #63 then fired Schwab steps end-to-end as designed.

2. **Operator architectural pushback on the reconciliation triage loop** — orchestrator surfaced 3 fresh discrepancies + recommended operator-action paths (direct DB edit, "immaterial" framing, etc.). Operator pushed back: Schwab IS truth; system should auto-correct, not surface for operator-triage. Orchestrator reframed: three-tier resolution model banked as Phase 12 Sub-bundle C headline. (See orchestrator-context.md "Lessons captured" 2026-05-15 entry on architectural pushback.)

3. **Operator UX clarification on env vars** — operator initially worried about weekly env-var reset (conflated with weekly OAuth re-auth). Clarified: app credentials are STABLE from Schwab Developer Portal; only the OAuth refresh_token rotates weekly. Banked credentials-in-file V2 path mirroring Finviz precedent.

4. **Web OAuth paste-back gap surfaced** — operator's normal mode is web interface; current `swing schwab setup` is CLI-only. Banked Option A (web paste-back form) for V1; Option B (HTTPS callback handler) for V2.

Phase 12 Sub-bundle B is well-defined as a bundled mini-bundle (~1-2 days of implementer work + orchestrator-inline regression-test discipline to pre-empt the runner-integration gap that bit T-A.3). Sub-bundle C is the substantial architectural pivot; benefits from a fresh-context orchestrator owning the brainstorm onward.

**Operator preference reaffirmed via this session:** when orchestrator's recommendation feels tactical-but-incomplete + operator pushes back framing-wise, listen for the architectural model + reframe forward; don't defend the tactical patch. Banked as orchestrator-context.md lesson.

Good luck.

---

*End of handoff brief. Post-Phase-12-Sub-bundle-A-merge orchestrator transition. Phase 11 CLOSED. Phase 12 Sub-bundle A SHIPPED. Phase 12 Sub-bundle B (bundled web-UI-friendliness) UNBLOCKED — your first dispatch. Sub-bundle C (auto-correct service) queued behind B. Operator-paced.*
