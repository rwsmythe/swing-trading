# Phase 12 Sub-bundle B — executing-plans dispatch brief (Schwab web-UI-friendliness mini-bundle)

**Audience:** Fresh Claude Code instance dispatched as the Phase 12 Sub-bundle B executing-plans implementer. No prior conversation context.

**Mission:** Execute Phase 12 Sub-bundle B via `copowers:executing-plans`. Sub-bundle B is the **bundled web-UI-friendliness mini-bundle** — credentials-in-file (extend `~/swing-data/user-config.toml` cascade for `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET`) + web OAuth setup form (`GET/POST /schwab/setup`). Two operator UX gaps from Phase 12 Sub-bundle A close discussion: (a) env-vars-only credential entry forces per-shell setup, and (b) weekly OAuth re-auth currently forces operator to drop to a separate PowerShell session for paste-back. Both target the same operator pain: "make Schwab setup work without dropping to PowerShell." Lands on a worktree branch; orchestrator owns integration merge to main post-operator-witnessed-gate.

**Why no brainstorm + no writing-plans:** Per operator scope decision 2026-05-15 (mirrors Phase 12 Sub-bundle A precedent), the design is well-defined in two top phase3e-todo entries dated 2026-05-15. This brief plays plan-role for the bundle.

**Expected duration:** ~1-2 days including ~2-3 Codex rounds. 6-7 tasks (T-B.1..T-B.7; T-B.7 is the optional `/schwab/status` web counterpart). +18-28 fast tests projected.

**The Sub-bundle A integration-test gap that THIS brief is engineered against:** Sub-bundle A's T-A.3 implementer added +5 helper-return-contract tests for `_construct_pipeline_schwab_client` — all green — but the runner.py callsites for `_step_schwab_snapshot` + `_step_schwab_orders` still hardcoded `client=None`. Operator-paired S5 gate caught it; orchestrator-inline fix at `e2c0384` added a runner-level source-pattern regression test. Sub-bundle B's web POST handler is the same structural pattern (route handler wires credentials cascade → invokes `setup_paste_flow` → handles response). The brief's §3 acceptance criteria for T-B.4 INCLUDE explicit route-level integration tests (TestClient against `POST /schwab/setup` with mocked credentials cascade — assert `setup_paste_flow` called with correct credential args) — not just helper-return-contract tests for the cascade extension.

---

## §0 Inputs

### §0.1 No plan; per-task scope LOCKED in this brief §3 (per operator scope decision)

This brief plays the role of BOTH spec + plan + dispatch brief for the mini-bundle. Per-task scope, acceptance criteria, and discriminating-test patterns are spec'd verbatim in §3 below.

### §0.2 Phase 11 + Phase 12 Sub-bundle A SHIPPED context (BINDING)

- **Phase 11 CLOSED 2026-05-14** at `e51e6eb` (Schwab API integration arc). Arc aggregate: 4 sub-bundles A+B+C+D / ~85 commits / ~17 Codex rounds / +447 fast tests / ZERO Critical / 5 ACCEPT-WITH-RATIONALE / 12 NEW CLAUDE.md gotchas / schema v17→v18.
- **Phase 12 Sub-bundle A SHIPPED 2026-05-15** at `123d27a`. 12 commits / 3 Codex rounds + 1 orchestrator-inline gate-fix `e2c0384` / +35 fast tests / ZERO ACCEPT-WITH-RATIONALE / 2 banked V2 candidates (oauth.tokens_db_rename enum value V2.1 §VII.F amendment + logout UTC unification). Schema v18 unchanged (consumer-side only).
- **Phase 12 Sub-bundle A return report:** `docs/phase12-bundle-A-return-report.md` (on main). Read §6 (ZERO ACCEPT-WITH-RATIONALE) + §10 (5 forward-binding lessons including `os.replace` overwrite-by-design + pipeline boundary except-clause broadening + cleanup-script regex tightening + two-phase audit ordering + env-var sentinel-leak discrimination). LOCKED dispositions §9 binding: T-A.2 audit endpoint reused `oauth.code_exchange` (NOT new enum value); T-A.2 timestamp UTC vs logout naïve preserved.
- **Sub-bundle A return reports (Phase 11):** `docs/schwab-bundle-{A,B,C,D}-return-report.md`. Already inherited via Sub-bundle A; no fresh re-read required for B scope (B is wrapper logic + web form + cfg cascade; no new schwabdev call surfaces).
- **CLAUDE.md status line** (latest at `4ed1892`) — Phase 12 Sub-bundle A SHIPPED narrative + 12 Schwab gotchas. **AUTHORITATIVE current-state summary.**
- **`reference/schwabdev/{setup-guide,examples,client,api-calls,streaming,orders,troubleshooting}.md`** — distilled refs already comprehensively pre-checked across the Phase 11 arc; consult only if T-B.4 web form surfaces a question.

### §0.3 BINDING distilled references

NO new schwabdev call surfaces in this bundle. All credential UX changes are pre-flight wrapper logic + cfg cascade. The web `POST /schwab/setup` handler REUSES `setup_paste_flow` (the same service-layer function the CLI uses since Sub-bundle A T-A.4); single-Client-instance discipline is preserved.

- **`swing/integrations/schwab/auth.py:resolve_credentials_env_or_prompt`** at L96 — current shape: env-vars-or-prompt (`raw_id`, `raw_secret` read via `os.environ.get(...)`; partial-env raises `SchwabConfigMissingError`; full-absent + `allow_prompt=True` falls through to `click.prompt(...)`). T-B.1 EXTENDS to env-vars-OR-cfg-OR-prompt cascade.
- **`swing/integrations/schwab/auth.py:setup_paste_flow`** at L713 — invoked by both CLI (existing) and the new web POST handler (T-B.4). Receives `client_id` + `client_secret` as positional args (resolved by caller). T-A.2 self-healing already applies regardless of caller (CLI vs web).
- **`swing/config.py:SchwabIntegrationConfig`** at L227 — 6 fields currently (`environment`, `account_hash`, `lookback_days`, `timeout_seconds`, `marketdata_ladder_enabled`, `callback_url`). T-B.2 EXTENDS with `client_id: str = ""` + `client_secret: str = ""` (per Finviz precedent at L221: `token: str = ""`, NOT `None`).
- **`swing/config.py:load()`** at L394 — drops sensitive Schwab fields from tracked TOML defensively at L435-438 (`environment`/`account_hash`/`lookback_days`/`callback_url`). T-B.2 ADDS `client_id` + `client_secret` to the dropped-from-tracked-TOML set (sensitive-only-in-user-config; mirror Finviz `token` + `screen_query` drop at L426-427).
- **`swing/config_validation.py:FIELD_REGISTRY`** — already supports `masked=True` (per existing `account_hash` precedent). T-B.2 adds two `masked=True` entries for the new fields.
- **`swing/web/routes/config.py:_save_redirect_response`** at L46 — canonical HTMX-aware-redirect helper (204+HX-Redirect for HTMX; 303 for non-HTMX). T-B.4 web POST follows the same pattern verbatim.
- **`swing/web/app.py`** — FastAPI app factory; router includes happen in `swing/web/routes/__init__.py` (or similar; verify at brief drafting / implementation time).
- **`swing/cli_schwab.py:_resolve_credentials_for_cli`** at L113 — wraps `resolve_credentials_env_or_prompt` with click.ClickException translation. T-B.1 cascade extension flows through this wrapper unchanged; 5 CLI callsites at `:185, :277, :346, :994, :1320` benefit automatically.
- **CLAUDE.md gotcha "Finviz Elite API token storage"** — precedent for the cascade pattern (`token` in user-config.toml under `[integrations.finviz]`; tracked TOML drops the field defensively; FIELD_REGISTRY entry with `masked=True`).

### §0.4 Phase 11 + Phase 12 Sub-bundle A cumulative forward-binding lessons (BINDING for Phase 12 Sub-bundle B)

All 22 cumulative forward-binding lessons (Phase 11: 5 A + 7 B + 5 C + 0 D; Phase 12 Sub-bundle A: 5) remain BINDING. Especially relevant for Sub-bundle B:

1. **schwabdev silent-failure-mode discipline** (Phase 11 A lesson #1) — `Client.__init__` + `update_tokens()` print + return silently on auth failure. Web POST handler MUST inherit `setup_paste_flow`'s existing silent-failure detection at `auth.py:868-891` (verifies `client.tokens.access_token` populated; raises `SchwabAuthError` if not).
2. **Pre-call factory-replacement defense** (Phase 11 A lesson #3) — `ensure_schwab_log_redaction_factory_installed()` before every schwabdev call. T-B.1 cascade extension MUST register cfg-sourced credentials in the Layer-0 redactor registry BEFORE any schwabdev call fires (mirror existing env-var path at `auth.py:161-162`).
3. **Single-Client-instance discipline** (Phase 11 B forward-binding lesson #3) — `construct_authenticated_client` + `setup_paste_flow` + `force_refresh` are the ONLY `schwabdev.Client(...)` instantiation sites. T-B.4 web POST handler does NOT instantiate `Client` directly; route handler calls `setup_paste_flow` per the established pattern.
4. **Surface-aware advisory audit** (Phase 11 B lesson #2) — `surface='pipeline'` silent-skip; `surface='cli'` advisory audit row. T-B.4 web POST uses `surface='cli'` (same value `setup_paste_flow` already records at `auth.py:806` — no separate `surface='web'` value introduced V1; banked V2 candidate if operator wants distinguishable web vs CLI audit rows).
5. **`Schwabdev` capital-S logger prefix** (Phase 11 A lesson #5) — preserved via `setup_paste_flow`'s existing factory install; web path inherits.
6. **`swing schwab setup` requires clean tokens DB state** (Phase 11 C gotcha) — CLOSED by Phase 12 Sub-bundle A T-A.2 self-healing. Web POST inherits the self-healing because it reuses `setup_paste_flow` (which calls `_rename_stale_tokens_db` at `auth.py:792`).
7. **Operator-paired-gate-caught implementation gap → orchestrator-inline gate-fix precedent (now 2 instances)** (Phase 12 Sub-bundle A lesson). The Sub-bundle A T-A.3 implementer wired the env-var helper into the market-data ladder hook but missed the parallel callsite wiring in `_step_schwab_snapshot` + `_step_schwab_orders`. Helper-return-contract tests don't catch runner-level integration gaps. **T-B.4 acceptance criteria below INCLUDE explicit route-level TestClient integration test** that asserts `setup_paste_flow` is invoked with correct credential args from the cascade — pre-empts the analogous defect class.
8. **`os.replace` is overwrite-by-design** (Phase 12 Sub-bundle A lesson). No `os.replace` use in B scope; lesson noted for completeness.
9. **Pipeline boundary except-clause broadening** (Phase 12 Sub-bundle A lesson). T-B.4 web POST handler's except-clause around `setup_paste_flow` MUST be broad — the route should NEVER crash on Schwab failures; it must render a user-visible error template + return non-2xx status code. Pattern complement to the pipeline boundary lesson.
10. **Form-render hidden anchors driving POST-time validation MUST round-trip through soft-warn confirm `form_values` dict** (Phase 9 Sub-bundle D R3 gotcha) — N/A for B's web form (no soft-warn confirm path V1; web POST either succeeds + redirects to status, or fails + renders error template; no validation cascade).
11. **HTMX form-driven failure surfaces (Phase 5 R1 M1+M2 + Phase 6 I3 gotcha family)** — T-B.4's `POST /schwab/setup` MUST follow the canonical pattern: (a) `hx-headers='{"HX-Request": "true"}'` on the form element for OriginGuard strict-mode propagation; (b) success-path `204 No Content` + `HX-Redirect: /schwab/status` (or fallback URL if T-B.7 deferred); (c) HX-Redirect target route MUST exist (TestClient route-table assertion in T-B.4 tests).
12. **`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM** (CLAUDE.md gotcha). T-B.4 adds `SchwabSetupVM` (new VM extends base layout); ensure standard base-layout fields are present per existing precedent (do NOT introduce a new top-level `vm.foo` requiring updates across all VMs).
13. **All four cascade emitters MUST do the no-op-skip check** (Phase 9 Sub-bundle A gotcha for risk_policy) — N/A for B's cascade (credentials are not policy-versioned; no audit-row supersession; partial-cascade-tier transitions are operator-visible via `swing config show` masking but don't create supersession events).
14. **`tomli_w.dump` strips comments** (Phase 9 Sub-bundle A gotcha) — when `swing config set integrations.schwab.client_id ...` fires the cfg-cascade write path, operator comments in `user-config.toml` are stripped. Acceptable V1 behavior (mirrors Finviz precedent + Phase 9 Sub-bundle A LOCK); T-B.3 commit message + cycle-checklist note must mention this.
15. **USERPROFILE+HOME monkeypatch discipline** (CLAUDE.md gotcha) — T-B.1 + T-B.3 tests exercise `write_user_overrides` write path; MUST monkeypatch BOTH `USERPROFILE` AND `HOME` env vars at fixture setup.

### §0.5 Codex chain pre-emption table (Phase 12 Sub-bundle B specific)

| Pattern family | Phase 11 / 12-A surface | Sub-bundle B applicability + pre-emption |
|---|---|---|
| **Cascade tier-precedence edge cases** (Phase 12 Sub-bundle A T-A.1 family extended) | env-vars-or-prompt | T-B.1 cascade is env-vars → cfg → prompt. Codex will probe: cfg field present but env vars also set (env wins); cfg has CLIENT_ID without CLIENT_SECRET (partial-cfg behavior — see AC2 below); cfg fields empty strings vs absent fields (treat as ABSENT-FOR-RESOLUTION per Sub-bundle A precedent); whitespace-only cfg fields (treat as ABSENT-FOR-RESOLUTION); env-var partial AND cfg full (full-cfg wins? or partial-env raises? — see AC2 LOCK). Pre-empt by writing ALL 6+ edge-case tests FIRST. |
| **Partial-cfg-tier behavior** (Sub-bundle A's partial-env raises analog) | T-A.1 partial-env raises `SchwabConfigMissingError` | T-B.1 partial-cfg: phase3e-todo entry §"Cascade design" says "Both-or-neither at each tier (partial → next tier) — UNLIKE T-A.1 partial-rejects-with-error". **LOCK: partial cfg-tier (CLIENT_ID set without CLIENT_SECRET, or either empty/whitespace) falls through to NEXT TIER (env vars if not yet checked — but env vars are checked first in the cascade; or to prompt if env vars absent).** Rationale per phase3e-todo entry: "file-tier may have CLIENT_ID set without CLIENT_SECRET (rare but valid as the operator may want to fall through to env vars or prompt for the secret)." This DIFFERS from env-tier partial behavior; Codex will probe — pre-empt with explicit test covering "cfg has CLIENT_ID only + env vars absent + allow_prompt=True → prompt fires for BOTH (operator-typed CLIENT_ID overrides partial-cfg)" |
| **Sentinel-leak audit extension** (Phase 12 Sub-bundle A T-A.10 family) | env-var values registered for redaction | T-B.6: cfg-cascade-sourced credentials must register in Layer-0 known-secret registry BEFORE any schwabdev call fires. Tests: (a) set credentials in user-config.toml + invoke any Schwab CLI command + grep caplog for sentinel substrings; assert absent. (b) Mirror Sub-bundle A's short-sentinel test (16-char hyphenated; bypasses Layer-1 heuristic) to discriminate registry registration from heuristic catch. |
| **HTMX failure surfaces (Phase 5 R1 M1+M2 + Phase 6 I3)** | `/config` POST | T-B.4 web POST: (a) form template uses `hx-headers='{"HX-Request": "true"}'`; (b) success-path 204 + HX-Redirect; (c) HX-Redirect target route exists (route-table assertion); (d) error-path renders user-visible template (NOT raw 500). |
| **Route-level integration test (Sub-bundle A T-A.3 gap pre-emption)** | helper-return-contract tests passed; runner-level wiring missed | T-B.4 acceptance MANDATES a route-level TestClient integration test: mock `setup_paste_flow` to return a known summary dict; POST `/schwab/setup` with form data (callback_url field populated); assert `setup_paste_flow` invoked with credentials from cascade; assert response is 204 + HX-Redirect to `/schwab/status` (or fallback). |
| **`copowers-watchdog` review trigger** | new dispatch briefs in `docs/` | This brief lands in `docs/`; orchestrator pre-cleared via the scope-decision question at dispatch time; implementer can proceed without separate review. |
| **schwabdev silent-failure on web path** (Sub-bundle A lesson #1 web extension) | CLI inherits silent-failure detection via setup_paste_flow | T-B.4: web POST inherits silent-failure detection because it REUSES `setup_paste_flow`. Discriminating test: monkeypatch `setup_paste_flow` to raise `SchwabAuthError`; POST `/schwab/setup`; assert response is 4xx with user-visible error template (NOT raw 500). |
| **Two-phase audit-row ordering (Sub-bundle A T-A.2 R2 fix)** | audit OPEN before O_EXCL claim | N/A for B scope (no new audit rows from web POST beyond those `setup_paste_flow` already emits via the CLI path; web POST surface stays `surface='cli'` per LOCK above). |

### §0.6 Inter-bundle dependencies (verify before commit)

- **`resolve_credentials_env_or_prompt(cfg, environment, *, allow_prompt: bool = True, prompter: Callable | None = None)`** at `swing/integrations/schwab/auth.py:96` — T-B.1 EXTENDS the implementation to consult cfg fields BEFORE the partial-env-or-prompt path. Signature MAY remain unchanged (no new kwargs needed — cfg is already a positional arg). Inter-bundle invariant: ALL existing callers (5 CLI surfaces + 1 pipeline surface via `_construct_pipeline_schwab_client`) continue to work without modification. Cascade order LOCKED: env vars (highest) → cfg fields (middle) → prompt (lowest).
- **`SchwabIntegrationConfig`** at `swing/config.py:227` — T-B.2 extends with 2 new fields. Existing 6 fields untouched. `__post_init__` validators: NEW fields require validation (non-empty-string type check OR explicit empty-string acceptance per Finviz precedent — see AC1 LOCK below).
- **`swing/config.py:load()`** at L394 — T-B.2 adds 2 lines to L429-438 region: `raw_schwab.pop("client_id", None)` + `raw_schwab.pop("client_secret", None)` (defensive drop from tracked TOML). Existing 4-field defensive drop pattern at L435-438 is the template.
- **`FIELD_REGISTRY`** at `swing/config_validation.py` — T-B.2 adds 2 entries with `masked=True`. Existing `integrations.schwab.account_hash` is the template.
- **`swing/web/routes/__init__.py`** — T-B.4 registers new router from `swing/web/routes/schwab.py`. Verify at implementation time.
- **`~/swing-data/user-config.toml`** under `[integrations.schwab]` — T-B.3 writes `client_id` + `client_secret` here via `write_user_overrides`. T-A.2 self-healing applies identically to web path (inherited via `setup_paste_flow` reuse).
- **No schema changes; `EXPECTED_SCHEMA_VERSION` stays at 18.**

### §0.7 Project state at dispatch time

- **HEAD on `main`:** `4ed1892` (post-Phase-12-Sub-bundle-A handoff doc).
- **Test count baseline:** **3791 fast passing on main** (post-Phase-12-Sub-bundle-A). 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures (NOT regressions). 1 SKIPPED (only `test_flag_classifier_integration.py`; no cross-bundle pins remain post-Phase-11).
- **Test runtime:** ~68s wall-clock at `-n auto` default.
- **Ruff baseline:** 18 (E501 only).
- **Schema version:** v18 (Phase 11 Sub-bundle A T-A.7 landed; subsequent bundles consumer-side; this bundle also consumer-side).
- **Production tokens DB:** `~/swing-data/schwab-tokens.production.db` clock started 2026-05-15T03:59:25+00:00; expires ~2026-05-22. **Operator may need to re-auth before B's gate session if scheduled close to 2026-05-22.** Sub-bundle A T-A.2 self-healing means recovery is one CLI/web invocation now.
- **Sandbox tokens DB:** `~/swing-data/schwab-tokens.sandbox.db` clock started 2026-05-14T20:30:55+00:00; expires ~2026-05-21.
- **Production discrepancy state:** 30 `acknowledged_immaterial` + 8 `journal_corrected` + 3 unresolved material (39 DHC + 40 VSAT + 41 CVGI from pipeline #63's reconciliation_run #10). **LEFT UNRESOLVED BY DESIGN** — they're correct signal pending Phase 12 Sub-bundle C auto-correct service. **Do NOT resolve them as `acknowledged_immaterial` or via direct DB edit during this dispatch's gate** (architectural anti-pattern per orchestrator-context.md "Lessons captured" 2026-05-15 entry).

### §0.8 Out of scope

- **Sub-bundle C** — auto-correct journal-from-Schwab service (architectural pivot; substantial brainstorm + writing-plans + multi-bundle executing-plans cycle). Queued behind B.
- **Option B (HTTPS callback handler eliminates paste-back entirely)** — V2 candidate per phase3e-todo entry. Substantial complexity (local self-signed HTTPS cert; browser security warning; Schwab Developer Portal app callback URL reconfiguration). Sub-bundle B ships Option A (paste-back form only).
- **Per-environment-namespaced env vars / cfg fields** (e.g., separate `SCHWAB_CLIENT_ID_SANDBOX` / `[integrations.schwab.sandbox].client_id`) — V2 candidate; V1 keeps flat field names that apply across production + sandbox (operator runs separate apps in Schwab Developer Portal, but cfg V1 doesn't surface the distinction).
- **Audit-row `surface='web'` distinct from `surface='cli'`** — V2 candidate (low operational value V1; the audit row's `endpoint` already disambiguates; banked if operator wants distinguishable web vs CLI audit rows).
- **Token encryption-at-rest** — V2 candidate (Q2 from Phase 11 brainstorm; schwabdev's optional `encryption=<key>` constructor parameter wraps the DB in Fernet AES-128).
- **Schema changes** — `EXPECTED_SCHEMA_VERSION` stays at 18.
- **New schwabdev call surfaces** — none in this scope.
- **Empty-finviz-inbox auto-fetch bug** (banked as 2026-05-15 phase3e-todo entry; ~1-line fix) — banked separately; do NOT fold into B unless operator commissions explicitly.

### §0.9 Sub-bundle B scope-summary

6-7 tasks; **+18-28 fast tests projected** (range +15..+35). **Per-task summary** (full per-task content in §3 below):

| Task | Scope | Tests | Files touched |
|---|---|---:|---|
| **T-B.1** | `resolve_credentials_env_or_prompt` cascade extension (env vars → cfg fields → prompt). Partial-cfg-tier falls through to NEXT tier (NOT raises). Sentinel registration mirrors Sub-bundle A. | +5 | `swing/integrations/schwab/auth.py:resolve_credentials_env_or_prompt` (extend) |
| **T-B.2** | `SchwabIntegrationConfig` + `FIELD_REGISTRY` extension (`client_id: str = ""` + `client_secret: str = ""`; `masked=True`). `swing/config.py:load()` defensive drop from tracked TOML extended to 6 fields. | +4 | `swing/config.py` + `swing/config_validation.py` |
| **T-B.3** | `swing config set integrations.schwab.client_id <value>` + `client_secret <value>` paths via existing `swing config set` cascade emitter (no-code wires inherited from FIELD_REGISTRY masking); add CLI smoke tests. | +2 | (no `swing/cli_config.py` changes needed if existing infrastructure handles it; verify at impl time) + tests |
| **T-B.4** | Web `GET /schwab/setup` route renders form template + `POST /schwab/setup` invokes `setup_paste_flow` with cascade-resolved credentials; `SchwabSetupVM` view-model; HTMX patterns (HX-Request propagation + HX-Redirect success path; route-table assertion). **Route-level integration test mandated (defends against T-A.3 implementer gap).** | +7 | `swing/web/routes/schwab.py` (NEW) + `swing/web/templates/schwab_setup.html.j2` (NEW) + `swing/web/view_models/schwab.py` (NEW) + `swing/web/routes/__init__.py` (register) |
| **T-B.5** | Cycle-checklist + CLAUDE.md updates: cfg cascade documented; web setup URL documented; T-A.2 self-healing applies to web inherited from `setup_paste_flow` reuse. | 0 | `docs/cycle-checklist.md` + `CLAUDE.md` |
| **T-B.6** | Sentinel-leak audit extension for cfg-cascade-sourced credentials. Mirror Sub-bundle A's `test_env_var_values_registered_for_redaction` + `test_env_var_values_redacted_when_short_and_layer1_skips` patterns. | +2 | `tests/integrations/test_schwab_token_redaction_audit.py` (extend) |
| **T-B.7 (optional)** | `GET /schwab/status` web counterpart — minimal status view rendering the same info as `swing schwab status` CLI. Implement IF impl complexity is low; defer to follow-up dispatch otherwise. | +3 | `swing/web/routes/schwab.py` (extend) + `swing/web/view_models/schwab.py` (extend) + template |

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `phase12-bundle-B-schwab-web-ui-friendliness`
- **Worktree directory:** `.worktrees/phase12-bundle-B-schwab-web-ui-friendliness/`
- **BASELINE_SHA:** `4ed1892` (current main HEAD).
- **Branch naming intent:** `phase12-bundle-B-*` matches the existing cleanup-script regex post Sub-bundle A T-A.4 fix (`(phase\d+[-_]|schwab(?:-\w+)?-bundle-)`) — operator's `-DeregisterFirst` pass should clean cleanly.

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task commits land + Codex chain converges + before final return-report commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes (`feat(schwab): ...`, `fix(schwab): ...`, `test(schwab): ...`, `docs(schwab): ...`, `feat(web): ...`).
- One commit per task; Codex-fix commits as `fix(phase12-bundle-B): Codex RN <severity> #N — <description>`.
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`** (per CLAUDE.md staging convention; `git add <specific files>` instead of `git add -A`).
- **DEFER the FINAL return-report commit until Codex chain converges to NO_NEW_CRITICAL_MAJOR.**

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:executing-plans invocation → task-by-task TDD → Codex iteration → return-report commit.
- **Orchestrator owns:** plan-triage at dispatch time + integration merge to main + Phase 12 Sub-bundle C (or follow-up arc) commissioning post-B-ship.
- **Operator owns:** operator-witnessed gate driving (per §4 below).

### §1.5 Verify command

```powershell
# After all tasks land + Codex chain converges:
git log --oneline HEAD~8..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; assert EXPECTED_SCHEMA_VERSION == 18"
# Verify cfg-cascade path (if no env vars + no cfg fields → prompt):
Remove-Item env:SCHWAB_CLIENT_ID, env:SCHWAB_CLIENT_SECRET -ErrorAction SilentlyContinue
# (operator runs `swing config set integrations.schwab.client_id <value>` separately + verifies)
python -m swing.cli config show | Select-String "integrations.schwab.client_"  # should show masked values
```

---

## §2 No operator-paired Task 0.b session required

This bundle introduces NO new schwabdev call surfaces. The web POST handler wraps the existing CLI flow (`setup_paste_flow`). Cassette tests stay synthetic-fixture-driven — inherited from Phase 11. No new cassettes recorded.

---

## §3 Per-task scope (BINDING; this brief plays plan-role)

### T-B.1 `resolve_credentials_env_or_prompt` cascade extension (env vars → cfg → prompt)

**Problem:** Sub-bundle A T-A.1 shipped env-vars-or-prompt. Operator UX gap (per phase3e-todo 2026-05-15 entry): env vars require per-shell setup (PowerShell profile is per-shell-application; not all shells/contexts pick up cleanly). File-based storage in `~/swing-data/user-config.toml` mirrors Finviz precedent + persists across shells.

**Acceptance criteria:**

1. **Tier-1 env-var resolution (highest priority; unchanged from Sub-bundle A):** if `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET` BOTH set + non-empty → use them; SKIP cfg + prompt. Partial-env STILL raises `SchwabConfigMissingError` (Sub-bundle A LOCK preserved). Empty-string env vars STILL treated as ABSENT-FOR-RESOLUTION (partial rule applies).
2. **Tier-2 cfg resolution (middle priority; NEW):** if env vars absent → consult `cfg.integrations.schwab.client_id` + `cfg.integrations.schwab.client_secret`. If BOTH non-empty + non-whitespace → use them; SKIP prompt; register secrets in Layer-0 redactor BEFORE returning. **Partial cfg-tier FALLS THROUGH to NEXT tier (NOT raises; differs from env-tier partial behavior per phase3e-todo LOCK).** Rationale: file-tier may have CLIENT_ID set without CLIENT_SECRET (rare but valid as the operator may want to fall through to env vars or prompt for the secret).
3. **Tier-3 prompt fallback (lowest priority; unchanged from Sub-bundle A):** if neither env vars nor cfg → existing `click.prompt(...)` behavior (V1; no regression).
4. **Env vars override cfg unambiguously:** if env vars set (both) AND cfg fields also set → env vars win; cfg fields ignored for THIS invocation (NOT modified on disk).
5. **Sentinel-leak guarantee:** cfg-sourced credentials NEVER appear in audit `error_message` excerpts, log lines, or any diagnostic output. Layer-0 redactor's known-secret registry registration fires BEFORE any schwabdev call invocation (mirrors Sub-bundle A env-var path at `auth.py:161-162`).
6. **`allow_prompt=False` discipline (pipeline path):** when caller passes `allow_prompt=False` (per Sub-bundle A T-A.3 pipeline path; T-A.3 caller passes `allow_prompt=False`):
   - If env vars set → return them.
   - If env vars absent but cfg fields set → return cfg values (NEW V1 behavior; pipeline now picks up cfg-stored credentials too).
   - If env vars + cfg both absent → return `(None, None)` (preserves pipeline silent-skip contract).
   - If partial cfg (only one field set) AND env vars absent AND `allow_prompt=False` → return `(None, None)` (partial-cfg-tier falls through; with prompt disabled, lowest tier returns None pair).
7. **Status surface inheritance:** `swing schwab status` (read-only path; should NOT prompt per Sub-bundle D forward-binding lesson #5) is unaffected — still reads filesystem only.

**Discriminating-test patterns (per acceptance items):**

- Test (1): set both env vars + cfg fields BOTH set + invoke `resolve_credentials_env_or_prompt(cfg, env, allow_prompt=True)` + mock `click.prompt` to raise; assert returned tuple = env-var values (env wins; cfg-fields ignored).
- Test (2): env vars absent + cfg fields BOTH set + invoke + mock `click.prompt` to raise; assert returned tuple = cfg values + assert `register_schwab_secrets` called with cfg values.
- Test (3): env vars absent + cfg has CLIENT_ID only (partial) + `allow_prompt=True` + mock `click.prompt` to return ("p_id", "p_secret"); assert prompt fired for BOTH (operator-typed values returned; partial cfg ignored).
- Test (4): env vars absent + cfg fields BOTH set + invoke with `allow_prompt=False`; assert returned tuple = cfg values (pipeline picks up cfg).
- Test (5): env vars absent + cfg empty-string fields + `allow_prompt=True` + mock prompt to return values; assert prompt fired (empty-string == ABSENT-FOR-RESOLUTION; falls through).
- Test (6): env vars set with PARTIAL pair (CLIENT_ID only) + cfg fields BOTH set; assert raises `SchwabConfigMissingError` (env-tier-partial-raises rule preserved; cfg fallback does NOT apply when env-tier is partial). LOCK rationale: env-tier partial signals operator typo / shell-session error; falling through to cfg would hide the misconfiguration.
- Test (7): sentinel-leak — set cfg fields to a known short Layer-1-bypassing sentinel (16 chars with hyphens; mirror Sub-bundle A precedent) + invoke + emit a fake log record via `schwabdev.Client` mock that interpolates the sentinel; assert sentinel absent from caplog.

**Files touched:** `swing/integrations/schwab/auth.py:resolve_credentials_env_or_prompt` (extend). `tests/integrations/test_schwab_credential_cascade.py` (NEW; OR extend `test_schwab_credential_env_vars.py`).

**Tests added:** +5 (7 test ideas above; collapse 2 partials into one).

**Commit message stem:** `feat(schwab): user-config.toml cfg-tier joins SCHWAB credential cascade (env > cfg > prompt)`.

### T-B.2 `SchwabIntegrationConfig` + FIELD_REGISTRY extension

**Problem:** No fields exist in the cfg dataclass to receive cfg-cascade-sourced credentials.

**Acceptance criteria:**

1. **`SchwabIntegrationConfig` extension** (at `swing/config.py:227`): add `client_id: str = ""` + `client_secret: str = ""` (default empty string per Finviz `token` precedent at L221). **Empty string is the LEGITIMATE V1 default; do NOT use `None`** — empty-string semantics match Finviz cascade pattern + simpler validation. `__post_init__` validation: must be `str` type; no length constraint (operator's actual Schwab Developer Portal credentials vary).
2. **Defensive drop from tracked TOML** (at `swing/config.py:load()` L429-438): add 2 lines `raw_schwab.pop("client_id", None)` + `raw_schwab.pop("client_secret", None)` to the existing 4-field defensive drop pattern. Tracked `swing.config.toml` MUST NOT carry these fields (sensitive-only-in-user-config; mirror Finviz `token` + `screen_query` drop at L426-427).
3. **`FIELD_REGISTRY` extension** (at `swing/config_validation.py`): add 2 entries:
   - `integrations.schwab.client_id` — type `str`, `masked=True`, default `""`.
   - `integrations.schwab.client_secret` — type `str`, `masked=True`, default `""`.
   - Mirror existing `integrations.schwab.account_hash` entry pattern (already `masked=True`).
4. **`swing config show` rendering:** auto-inherits from FIELD_REGISTRY's `masked=True` (first-3 + `***` + last-2 per `swing/config_validation.py:mask_sensitive_value`; existing precedent). NO additional rendering code required; verify via inline test.
5. **`swing config show` NOT exposing raw values:** discriminating test — set cfg fields to a sentinel; invoke `swing config show`; grep output; assert sentinel absent + mask pattern present.
6. **Backwards-compat:** Sub-bundle A operators relying on env vars continue to work unchanged (env vars are highest-priority tier). Discriminating test: set env vars + leave cfg fields empty; invoke `swing schwab status`; assert success without modification.

**Discriminating-test patterns:**

- Test (1): construct `SchwabIntegrationConfig(client_id="abc", client_secret="def")` + verify no `__post_init__` raise.
- Test (2): construct with `client_id=None` (wrong type); verify `__post_init__` raises TypeError (per Finviz precedent which requires `str`).
- Test (3): write `client_id="leak-test-id-12345"` to tracked `swing.config.toml` (test fixture); invoke `load(test_path)`; assert `cfg.integrations.schwab.client_id == ""` (drop-from-tracked enforced).
- Test (4): write to user-config.toml + load; assert cfg fields populated.
- Test (5): `swing config show` rendering with cfg fields set; grep output; assert mask pattern (`abc***45` shape) present.

**Files touched:** `swing/config.py` (extend dataclass + load). `swing/config_validation.py` (extend FIELD_REGISTRY). `tests/config/test_schwab_credentials_in_file.py` (NEW; OR extend existing).

**Tests added:** +4.

**Commit message stem:** `feat(config): SchwabIntegrationConfig.client_id + client_secret fields + FIELD_REGISTRY masked entries`.

### T-B.3 `swing config set integrations.schwab.client_id|client_secret` cascade emitter

**Problem:** Operators need a CLI path to write the credentials to `~/swing-data/user-config.toml` without hand-editing.

**Acceptance criteria:**

1. **Existing `swing config set <path> <value>` infrastructure inherits the new FIELD_REGISTRY entries automatically.** Verify at impl time: `swing/cli_config.py` consumes FIELD_REGISTRY at L<verify>; new entries with `masked=True` may need handling identical to `account_hash` precedent.
2. **CLI smoke test:** `swing config set integrations.schwab.client_id "test_id_value"` writes the value to `~/swing-data/user-config.toml` under `[integrations.schwab]`; subsequent `swing config show` renders the masked value; subsequent `swing schwab status` (with env vars absent) uses the cfg value.
3. **`swing config reset integrations.schwab.client_id` path** (if supported by existing infrastructure): clears the value from user-config.toml; subsequent `swing schwab status` falls through to prompt (or fails if non-TTY).
4. **`tomli_w.dump` comment-stripping** (CLAUDE.md gotcha): `write_user_overrides` strips operator comments. T-B.3 commit message MUST mention this expected behavior; cycle-checklist (T-B.5) note operator can hand-edit user-config.toml directly if comment preservation matters.
5. **USERPROFILE+HOME monkeypatch** (CLAUDE.md gotcha): T-B.3 tests MUST monkeypatch both env vars to tmp_path at fixture setup.

**Discriminating-test patterns:**

- Test (1): invoke `swing config set integrations.schwab.client_id "test_id"` via click.CliRunner; read user-config.toml; assert key+value present.
- Test (2): set value via `swing config set` then invoke `swing config show`; assert mask pattern in output (NOT raw value).

**Files touched:** Possibly NO code changes (if existing `swing config set` infrastructure auto-handles new FIELD_REGISTRY entries via `masked=True`). If code changes ARE needed (e.g., `swing/cli_config.py` has a hand-coded allowlist), extend. `tests/cli/test_config_set_schwab_credentials.py` (NEW; OR extend existing).

**Tests added:** +2.

**Commit message stem:** `feat(cli): swing config set integrations.schwab.client_id + client_secret writes to user-config.toml`.

### T-B.4 Web `GET/POST /schwab/setup` route + template + view-model

**Problem:** Operator's normal mode is the web interface (`swing web` on 127.0.0.1:8080). Weekly OAuth re-auth forces operator to drop to a separate PowerShell session. No web-side equivalent exists.

**Acceptance criteria:**

1. **`GET /schwab/setup` route** at `swing/web/routes/schwab.py` (NEW) renders `schwab_setup.html.j2` template with `SchwabSetupVM` view-model. Form has:
   - Step 1: clickable authorize-URL link (target="_blank"; URL constructed from `cfg.integrations.schwab.callback_url` + Schwab OAuth endpoint).
   - Step 2: text input named `callback_url` for operator-pasted callback URL.
   - Step 3: submit button (HTMX form with `hx-post="/schwab/setup"`, `hx-target` per existing pattern, `hx-headers='{"HX-Request": "true"}'` — per Phase 5 R1 M1 gotcha).
2. **`POST /schwab/setup` handler:**
   - Resolves credentials via `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` (web context = no prompt available). If returns `(None, None)` → render error template pointing operator at `/config` or `swing config set` (HTTP 400 + user-visible error). The cascade extension from T-B.1 means web POST picks up cfg-stored credentials transparently.
   - Invokes `setup_paste_flow(cfg, environment, client_id, client_secret, conn, account_picker=<callable>)` — service-layer function REUSED VERBATIM from Sub-bundle A T-A.4 (NO re-implementation). T-A.2 self-healing applies identically (inherited via setup_paste_flow).
   - `account_picker`: web V1 LOCK = auto-pick singleton; raise `SchwabConfigMissingError` if multi-account (operator must use CLI for multi-account V1). Banked V2 candidate: web multi-account picker (separate HTMX form).
   - **NOTE: `setup_paste_flow` blocks on `schwabdev.Client(...)` construction which prints consent URL + blocks on stdin paste-back.** In the web POST path, the operator has ALREADY pasted the callback URL into the form; `schwabdev.Client` won't be able to consume it via stdin. **Operator-facing reality check:** the web form's "paste callback URL" workflow needs to either (a) feed the callback URL programmatically into schwabdev's flow OR (b) compute the auth `code` from the callback URL operator-side and inject it into the tokens DB write path. Per Phase 11 Sub-bundle A T-A.0.b live-library discovery, schwabdev's paste-back is embedded in `Client.__init__` (NOT a separate `auth.manual_flow()` callable). **OPERATOR-PAIRED INVESTIGATION TASK at start of T-B.4:** before implementing the POST handler, inspect `schwabdev` source for a programmatic-callback-URL ingestion path; if none exists, lock the V1 web-form architecture: form collects callback URL → POST handler extracts `code` query-param from the URL → handler POSTs directly to `https://api.schwabapi.com/v1/oauth/token` with `grant_type=authorization_code` + writes tokens file manually (mirrors revoke flow at `auth.py:1331` which POSTs to `/v1/oauth/revoke` manually). **If the manual-token-exchange path is the V1 architecture, a NEW service-layer helper `setup_paste_flow_with_callback_url(cfg, env, client_id, client_secret, callback_url, conn)` is required** — REFACTOR existing `setup_paste_flow` to share the audit-row + tokens-write + account_linked logic; web POST calls the new helper; CLI continues to use `setup_paste_flow` (stdin-paste-back via schwabdev.Client). **REPORT the architecture decision in return report §5 as a deviation; orchestrator banks the LOCK.**
3. **Success-path response (HTMX):** 204 No Content + `HX-Redirect: /schwab/status` (per Phase 5 R1 M2 gotcha). If T-B.7 deferred, HX-Redirect target = `/config` or `/` (verify route exists; route-table assertion in tests). Non-HTMX clients: 303 to `/schwab/status` (or fallback).
4. **Error-path response:** render user-visible error template at HTTP 4xx; NOT raw 500. Errors to surface:
   - Credentials cascade returned `(None, None)` → 400 + "Set credentials via /config or `swing config set integrations.schwab.client_id`".
   - `setup_paste_flow` raises `SchwabAuthError` → 502 + error template with redacted error message (use `_redacted_excerpt` helper).
   - `setup_paste_flow` raises `SchwabPipelineActiveError` → 409 + error template + "Wait for pipeline run to finish".
   - `setup_paste_flow` raises `SchwabConfigMissingError` (multi-account on web V1) → 400 + error template + "Use `swing schwab setup` CLI for multi-account setup".
   - Any other Exception → 500 + generic error template + log warning.
5. **`SchwabSetupVM` view-model**: standard base-layout fields (`vm.foo` discipline per CLAUDE.md gotcha — verify which fields are expected by existing base.html.j2 pattern); plus setup-specific: `authorize_url: str`, `error_message: str | None`, `existing_tokens_db_warning: bool`. Note: existing-tokens-DB-warning is informational only; the actual rename happens inside `setup_paste_flow` (T-A.2 inherited).
6. **Route registration:** in `swing/web/routes/__init__.py` (or `swing/web/app.py` if routers register there); follow existing pattern (e.g., how `/account` or `/config` routes register).
7. **`hx-headers='{"HX-Request": "true"}'` propagation** (Phase 5 R1 M1 gotcha): form element has this attribute. Discriminating test: render form template; assert `hx-headers` attribute present.
8. **HX-Redirect target route exists** (Phase 6 I3 gotcha): TestClient route-table assertion — `assert any(r.path == "/schwab/status" for r in app.routes)` (if T-B.7 lands) OR `"/config"` (fallback). Decide at impl time.
9. **Route-level integration test (Sub-bundle A T-A.3 gap pre-emption — BINDING):**
   - Test: mock `setup_paste_flow` to return a known summary dict; mock credentials cascade to return `("test_id", "test_secret")`; POST `/schwab/setup` with form data; assert `setup_paste_flow` was called with `client_id="test_id"`, `client_secret="test_secret"`; assert response is 204 + HX-Redirect target verified.
   - This test discriminates the "route handler correctly threads credentials from cascade into `setup_paste_flow` invocation" wiring — analogous to Sub-bundle A's gate-caught `client=None` callsite gap.

**Discriminating-test patterns:**

- Test (1): `GET /schwab/setup` renders template with authorize URL constructed correctly from cfg + Schwab OAuth endpoint.
- Test (2): `GET /schwab/setup` renders `hx-headers='{"HX-Request": "true"}'` attribute on form (regression for Phase 5 R1 M1).
- Test (3): `POST /schwab/setup` with empty form + no credentials in cascade → 400 + error template.
- Test (4): `POST /schwab/setup` with credentials cascade present + form callback URL → mock `setup_paste_flow` returns success → 204 + HX-Redirect (target exists per route-table assertion).
- Test (5): `POST /schwab/setup` with `setup_paste_flow` raising `SchwabAuthError` → response is 4xx (NOT 500) + error template.
- Test (6): route-level integration test — assert `setup_paste_flow` invoked with correct credential args from cascade (T-A.3 gap pre-emption).
- Test (7): HX-Redirect target route exists (`/schwab/status` if T-B.7 lands; `/config` otherwise).

**Files touched:** `swing/web/routes/schwab.py` (NEW). `swing/web/templates/schwab_setup.html.j2` (NEW). `swing/web/view_models/schwab.py` (NEW). `swing/web/routes/__init__.py` OR `swing/web/app.py` (register new router). `tests/web/test_schwab_setup_route.py` (NEW). If T-B.4 investigation determines manual-token-exchange architecture needed: `swing/integrations/schwab/auth.py:setup_paste_flow_with_callback_url` (NEW service function; refactor existing setup_paste_flow to share audit/tokens-write/account-linked logic).

**Tests added:** +7.

**Commit message stem:** `feat(web): GET/POST /schwab/setup route + template + SchwabSetupVM (web OAuth paste-back form)`.

### T-B.5 Cycle-checklist + CLAUDE.md updates

**Acceptance criteria:**

1. **`docs/cycle-checklist.md` update:** add web URL `http://127.0.0.1:8080/schwab/setup` as primary weekly re-auth path; CLI command remains as fallback. Document cfg-cascade tiers (env > cfg > prompt) for credential resolution. Reference T-A.2 self-healing (operator no longer needs `logout → setup` recovery sequence).
2. **`CLAUDE.md` gotcha addition** — "Schwab OAuth web setup flow" documents Option A's HTMX requirements (embedded form HX-Request propagation; HX-Redirect success path; T-A.2 self-healing applies identically; route table includes `/schwab/setup` GET + POST).
3. **`CLAUDE.md` gotcha addition** — "Schwab CLIENT_ID + CLIENT_SECRET storage" mirrors existing "Finviz Elite API token storage" entry. Tracked `swing.config.toml` MUST NOT contain the values (sensitive); only `~/swing-data/user-config.toml`. `.gitignore` patterns for `user-config.toml*` should already cover (verify).
4. **`CLAUDE.md` status line refresh** — append Phase 12 Sub-bundle B SHIPPED entry (orchestrator does this at integration-merge time; implementer drafts the SHIPPED-entry text in return report §11 for orchestrator paste-in).

**Files touched:** `docs/cycle-checklist.md` + `CLAUDE.md`.

**Tests added:** 0 (doc-only).

**Commit message stem:** `docs(cycle-checklist+CLAUDE): Phase 12 Sub-bundle B web OAuth + cfg-cascade documentation`.

### T-B.6 Sentinel-leak audit extension for cfg-cascade-sourced credentials

**Problem:** Sub-bundle A's `test_schwab_token_redaction_audit.py` covers env-var-sourced credentials only. Cfg-cascade-sourced credentials add a new pathway; must verify Layer-0 registry registration fires BEFORE schwabdev log emission.

**Acceptance criteria:**

1. **Extend `tests/integrations/test_schwab_token_redaction_audit.py`** with 2 new tests (mirroring Sub-bundle A's `test_env_var_values_registered_for_redaction` + `test_env_var_values_redacted_when_short_and_layer1_skips`):
   - Test (a) — long ALL-CAPS sentinel registered for redaction via cfg-cascade path; passes via both Layer-1 heuristic + registry.
   - Test (b) — 16-char hyphenated sentinel (BYPASSES Layer-1); only registry registration scrubs.
2. **Discriminating-test pattern:** plant credentials in user-config.toml via test fixture (USERPROFILE+HOME monkeypatched); invoke any Schwab CLI path that resolves credentials via the cascade (e.g., `swing schwab status`); emit a sentinel log record via `schwabdev` mock that interpolates the credentials; assert sentinel absent from caplog + audit `error_message` columns.

**Files touched:** `tests/integrations/test_schwab_token_redaction_audit.py` (extend).

**Tests added:** +2.

**Commit message stem:** `test(schwab): sentinel-leak audit covers cfg-cascade-sourced credentials`.

### T-B.7 (OPTIONAL) `GET /schwab/status` web counterpart

**Problem:** Operator's normal mode is the web interface. `swing schwab status` is CLI-only V1. Modest UX win to surface the same info on the web.

**Acceptance criteria (IF impl complexity is low; defer otherwise):**

1. **`GET /schwab/status` route** at `swing/web/routes/schwab.py` (extend) renders `schwab_status.html.j2` template with `SchwabStatusVM` view-model.
2. **View-model populated from same data sources as CLI:** per-environment LIVE/DEGRADED/PROVISIONAL/NOT_CONFIGURED state + refresh-token TTL + recent calls summary + recent errors count.
3. **Read-only route** (no POSTs; no credential prompts inherited via Sub-bundle D forward-binding lesson #5).
4. **HX-Redirect target from T-B.4 success path:** if T-B.7 lands, HX-Redirect = `/schwab/status`; if deferred, fallback to `/config`.

**Discriminating-test patterns:**

- Test (1): `GET /schwab/status` renders template with expected fields.
- Test (2): per-environment state rendering matches CLI behavior (mock data sources).
- Test (3): NO credential prompts fire (regression for Sub-bundle D lesson #5).

**Files touched:** `swing/web/routes/schwab.py` (extend) + `swing/web/view_models/schwab.py` (extend) + template (NEW).

**Tests added:** +3.

**Commit message stem:** `feat(web): GET /schwab/status web counterpart to swing schwab status CLI`.

**Defer disposition:** if T-B.4 impl complexity overflows or Codex chain takes >3 rounds, DEFER T-B.7 to a follow-up dispatch. Document the defer in return report §5; the HX-Redirect target for T-B.4 success path becomes `/config` instead.

---

## §4 Operator-witnessed verification gate (Sub-bundle B integration)

| # | Surface | Type | Acceptance |
|---|---|---|---|
| **S1** | pytest fast-suite | Inline | `python -m pytest -m "not slow" -q` GREEN at ~3809-3819 fast tests (worktree-side; +18-28 net); 3 pre-existing `test_phase8_pipeline_walkthrough.py` failures unchanged; 1 skipped (flag-classifier only). |
| **S2** | `swing config set` cfg-cascade write path | **Operator-driven (CLI)** | `swing config set integrations.schwab.client_id <test_id>` + `client_secret <test_secret>` succeed; `swing config show` renders masked values; user-config.toml contains the fields under `[integrations.schwab]`. NOTE: use TEST values, NOT operator's actual Schwab Developer Portal credentials; clean up post-gate via `swing config reset` or hand-edit. |
| **S3** | CLI cascade resolution | **Operator-driven (CLI)** | Set cfg values (S2) + unset env vars; invoke `swing schwab status --environment production`; assert NO prompt fired; status renders LIVE (using operator's actual credentials — requires S5 first if test values used in S2 don't authenticate). |
| **S4** | Web GET /schwab/setup | **Operator-driven (browser via Chrome MCP if available; manual otherwise)** | Start `swing web --port 8081` in worktree; navigate to `http://127.0.0.1:8081/schwab/setup`; assert form renders with authorize-URL link + paste-back input + submit button; click authorize link opens new tab to Schwab; copy callback URL from Schwab redirect; paste into form; submit. **NOTE: destructive — consumes a re-auth cycle.** |
| **S5** | Web POST /schwab/setup completion | **Operator-driven (continues S4)** | POST succeeds (HX-Redirect to /schwab/status or /config); tokens DB renamed (T-A.2 self-healing inherited via setup_paste_flow); fresh tokens DB written; fresh 7-day clock starts; `swing schwab status` shows LIVE. Production-write classifier soft-block awareness: orchestrator pre-authorizes via gate-path. |
| **S6** | Sub-bundle B cleanup-script regex regression | **Operator-driven (PowerShell elevated; OPTIONAL)** | Plant a fake `phase12-bundle-B-test` worktree; invoke `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`; verify script picks up the phase12-pattern worktree (regression for Sub-bundle A T-A.4 fix). OPTIONAL — orchestrator may skip if Sub-bundle A T-A.4 gate already validated this regex; verify via the actual worktree husk cleanup post-merge instead. |
| **S7** | ruff baseline | Inline | `ruff check swing/ --statistics` reports 18 E501 unchanged. |
| **S8** | Sentinel-leak audit | Inline | T-B.6 tests cover cfg-cascade-sourced credentials; assert sentinel absent from caplog + audit `error_message` columns. |
| **S9** | `swing config show` masking | Inline | T-B.2 + T-B.3 tests assert masked rendering pattern (`abc***45` shape) for client_id + client_secret entries. |

**Gate session ≤ 6 surfaces budget:** S1+S7+S8+S9 inline (4). S2+S3+S4+S5 operator-driven (4 — at upper limit). S6 optional. Operator may bundle S2+S3 (same cfg-set then status invocation).

**Production state post-gate:** S5 destructively re-auths operator's production tokens DB (fresh 7-day clock starts at gate time; mirrors Sub-bundle A S4 gate). S2-S3 use TEST credential values; cleanup post-gate via `swing config reset` to restore env-var-only or prompt-only path.

**Production-write classifier soft-block awareness:** S5 writes audit + tokens DB from web POST; operator pre-authorizes via gate-path. AskUserQuestion responses are NOT visible to the classifier — if soft-blocked, surface to operator for plain-chat "yes" confirmation per orchestrator-context.md "Lessons captured" 2026-05-12 entry on AskUserQuestion-vs-chat-text classifier visibility.

---

## §5 Skill posture + adversarial review

- **Invoke `copowers:executing-plans`** via the Skill tool. The copowers wrapper handles Codex review automatically.
- Skill inputs:
  - `PLAN_PATH=docs/phase12-bundle-B-schwab-web-ui-friendliness-executing-plans-dispatch-brief.md` (this brief plays plan-role).
  - `SUB_BUNDLE=B` (Tasks T-B.1..T-B.6; T-B.7 optional).
  - `BASELINE_SHA=4ed1892`.
- **Expected Codex chain:** 2-3 rounds (small, focused mini-bundle; matches Sub-bundle A precedent).

### §5.1 Codex value-add concentration (Sub-bundle B specific)

Adversarial review for this bundle typically catches:

- **T-B.1 cascade tier-precedence edge cases** — Codex will probe: env-tier partial + cfg-tier full (env-tier still raises per LOCK); env-tier empty-string vs absent; whitespace-only cfg fields; cfg fields containing the same value as env vars (no-op vs collision). Pre-empt by writing all 6+ edge-case tests FIRST.
- **T-B.1 sentinel-leak via cfg-cascade path** — Codex will probe registry registration ordering: cfg fields registered BEFORE first schwabdev call. Test exercise: monkeypatch schwabdev to emit log on construction; assert sentinel absent from caplog.
- **T-B.2 backwards-compat** — operators using env-vars-only must continue to work; cfg fields default to empty string (NOT raise on absent).
- **T-B.2 defensive-drop from tracked TOML** — Codex will probe: write sensitive values to tracked TOML; assert dropped from loaded cfg. Mirror Finviz test precedent.
- **T-B.4 HTMX patterns** — Codex will probe HX-Request propagation; HX-Redirect-vs-303-swap; HX-Redirect target route existence. Three known Phase 5+ gotchas — pre-empt all three with explicit tests.
- **T-B.4 route-level integration test (Sub-bundle A T-A.3 gap pre-emption)** — Codex may flag if helper-return-contract tests are present but route-level integration test absent. The brief mandates the route-level test; verify it's present.
- **T-B.4 web-form architecture decision** — if manual-token-exchange path is required (operator-paired investigation determines), Codex will probe: refactor of `setup_paste_flow` to share logic with new `setup_paste_flow_with_callback_url`; both functions audit-row + token-write + account-linked semantics IDENTICAL; new function does the `code` extraction + manual POST. Verify via discriminating test that the CLI path (existing `setup_paste_flow`) still works unchanged.
- **T-B.4 error-path coverage** — every error scenario in AC4 must have a discriminating test (Credentials cascade None; SchwabAuthError; SchwabPipelineActiveError; SchwabConfigMissingError; generic Exception).
- **T-B.6 short-sentinel discrimination** — 16-char hyphenated sentinel must BYPASS Layer-1 heuristic to discriminate registry registration; mirror Sub-bundle A precedent.

---

## §6 Watch items for Sub-bundle B implementer

1. **DO NOT add new schwabdev call surfaces** — this bundle is wrapper + config + script changes + web routes only. NO direct `schwabdev.Client(...)` instantiation; route through `setup_paste_flow` (or its refactored sibling if T-B.4 investigation determines manual-token-exchange is the V1 path).
2. **DO NOT introduce new schema** — `EXPECTED_SCHEMA_VERSION` stays at 18.
3. **Preserve existing test fixtures** — T-B.1 cascade extension must not regress any Sub-bundle A env-var-or-prompt test; partial-env-tier still raises.
4. **USERPROFILE+HOME monkeypatch discipline** per CLAUDE.md gotcha — T-B.1 + T-B.3 + T-B.6 tests touch `~/swing-data/` paths; MUST monkeypatch both env vars to tmp_path at fixture setup.
5. **Single-Client-instance discipline** — T-B.4 does NOT introduce new `schwabdev.Client(...)` instantiation sites; route through `setup_paste_flow` (existing service-layer function).
6. **`Schwabdev` capital-S logger prefix** preserved via existing factory install in setup_paste_flow.
7. **HTMX failure surfaces (Phase 5+)** — T-B.4 MUST address all three known gotchas: HX-Request propagation; HX-Redirect-vs-303-swap; HX-Redirect target route existence.
8. **`tomli_w.dump` comment-stripping** (Phase 9 Sub-bundle A gotcha) — T-B.3 commit message + T-B.5 cycle-checklist note must mention this expected behavior.
9. **Phase 12 scope LOCK** — Sub-bundle C scope (auto-correct service) explicitly OUT-OF-SCOPE per §0.8; do NOT scope-creep.
10. **3 unresolved material discrepancies (39/40/41) in production** — LEFT UNRESOLVED BY DESIGN per architectural pivot lock. Do NOT resolve via direct DB edit OR `acknowledged_immaterial` resolution during this dispatch's gate.
11. **`copowers-watchdog`** may flag this brief as needing review — orchestrator pre-cleared this brief via the scope-decision question at dispatch time; implementer can proceed without separate review.
12. **OPERATOR-PAIRED INVESTIGATION at start of T-B.4** — investigate schwabdev source for programmatic-callback-URL ingestion path BEFORE implementing POST handler. If manual-token-exchange is the V1 architecture, refactor `setup_paste_flow` to share logic with new `setup_paste_flow_with_callback_url`; report architecture decision in return report §5 as a deviation.
13. **Route-level integration test for T-B.4** is BINDING (pre-empts Sub-bundle A T-A.3 implementer gap class).

---

## §7 Return report shape

After all task commits land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase12-bundle-B-return-report.md` (mirroring `docs/phase12-bundle-A-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain.
3. Test count delta + ruff baseline delta + schema version delta (unchanged at v18).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate).
5. Per-task deviations from this brief (if any) with rationale. **EXPLICITLY DOCUMENT T-B.4 web-form architecture decision (paste-back-via-schwabdev-stdin vs manual-token-exchange).** **EXPLICITLY DOCUMENT T-B.7 disposition (landed vs deferred).**
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (any V2 candidates surfaced; Sub-bundle C dispatch-readiness).
8. Worktree teardown status (expected ACL-locked husk per Phase precedent; cleanup-script regex matches `phase12-*` so `-DeregisterFirst` should pick it up cleanly).
9. Per-task disposition LOCKS (T-B.4 web architecture; T-B.7 landed-or-deferred).
10. Forward-binding lessons for Phase 12 Sub-bundle C (if commissioned).
11. CLAUDE.md status-line refresh draft text for orchestrator paste-in at integration-merge time.
12. Composition-surface verification via `^def` grep for new helpers (`setup_paste_flow_with_callback_url` if introduced; cascade extension verification).
13. Sentinel-leak audit verification (cfg-sourced credentials absent from audit + caplog).
14. T-B.4 route-table assertion verification (HX-Redirect target exists).

---

## §8 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** 1-2 days including 2-3 Codex rounds.

---

## §9 Watch items for orchestrator (post-Sub-bundle-B-ship)

1. **Operator-witnessed gate driving** — orchestrator drives S2-S5 via operator-paired CLI/browser session. S5 destructively re-auths operator's production tokens DB. S4-S5 use Chrome MCP if available; manual browser walkthrough otherwise.
2. **Phase 12 Sub-bundle C (auto-correct journal-from-Schwab service)** commissioning UNBLOCKED post-B-ship. Substantial brainstorm + writing-plans + multi-bundle executing-plans cycle expected. Per phase3e-todo "ARCHITECTURAL: reconciliation must auto-correct journal-from-Schwab" entry: 4-6 Codex rounds brainstorm; 4-6 Codex rounds writing-plans; 3-4 sub-sub-bundles execution. Operator-paced.
3. **Operator daily-use further unblock — DELIVERED on Sub-bundle B ship:**
   - Credentials persist across shells (cfg-cascade path)
   - Web OAuth setup eliminates PowerShell drop-out for weekly re-auth (Option A; Option B HTTPS callback-handler banked V2)
4. **Token clock awareness** — S5 gate will reset operator's production tokens DB clock to fresh 7-day from gate-time. Sandbox tokens DB clock (~2026-05-21) unaffected.
5. **3 unresolved material discrepancies (39/40/41)** — STILL LEFT UNRESOLVED by design pending Sub-bundle C; B does NOT close this. Phase 10 dashboard banner continues to show "3 unresolved" — that's accurate state.
6. **Phase 11 + 12-A forward-binding lessons (22 cumulative) remain authoritative** for any future Schwab work.
7. **V2 candidates surfaced from Sub-bundle B** (banked at return report §7):
   - Option B HTTPS callback-handler (eliminates paste-back entirely).
   - Per-environment-namespaced env vars / cfg fields.
   - Web multi-account picker.
   - Audit-row `surface='web'` distinct value.
   - Token encryption-at-rest (Q2 from Phase 11 brainstorm).

---

## §10 Dispatch order

B is the next Sub-bundle in Phase 12 (after A SHIPPED). Sub-bundle C queued after B per operator-locked sequencing 2026-05-15. No intra-B sub-task ordering required beyond standard TDD task-by-task discipline; T-B.7 is optional + defer-able per §3 disposition.

**Recommended task sequencing within Sub-bundle B:**

1. T-B.2 first (foundational — cfg dataclass + FIELD_REGISTRY + load-defense; downstream tasks depend on this).
2. T-B.1 second (cascade extension consumes T-B.2's cfg fields).
3. T-B.3 third (CLI `swing config set` verifies T-B.2 infrastructure via end-to-end smoke test).
4. T-B.4 fourth (largest scope; consumes T-B.1 cascade for credential resolution; operator-paired investigation at start).
5. T-B.6 fifth (sentinel-leak audit covers T-B.1 + T-B.3 + T-B.4 paths).
6. T-B.5 sixth (docs).
7. T-B.7 optional (after T-B.4; T-B.4's HX-Redirect target depends on T-B.7 disposition).

---

*End of Phase 12 Sub-bundle B executing-plans dispatch brief. Web-UI-friendliness mini-bundle: credentials-in-file + web OAuth setup form. Bundle plays plan-role. Pre-empts Sub-bundle A T-A.3 implementer integration-test gap via mandated T-B.4 route-level integration test. ZERO new schwabdev call surfaces; ZERO new schema. Phase 11 + 12-A 22 forward-binding lessons inherited BINDING.*
