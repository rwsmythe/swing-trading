# Phase 9 Sub-bundle A — executing-plans return report

**Branch:** `phase9-bundle-A-risk-policy-foundation`
**Final HEAD:** `e3e9e17`
**Worktree:** `.worktrees/phase9-bundle-A-risk-policy-foundation/`
**Baseline:** `700337d` (BASELINE_SHA per dispatch brief §1.1; pre-Bundle-A main HEAD)
**Worktree branching point:** `51ee033` (current main HEAD at worktree-creation; this is the dispatch-brief commit landed on main).
**Spec:** `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`
**Plan:** `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` §A + §B + §D
**Dispatch brief:** `docs/phase9-bundle-A-executing-plans-dispatch-brief.md`

---

## §1 Commit chain

| Sequence | Commit | Title |
|---|---|---|
| 1 | `bf34685` | feat(data): Task A.0 — naive-UTC millisecond-precision datetime helpers |
| 2 | `5400974` | feat(data): Task A.1 — migration 0017 atomic Phase 9 schema landing (v16 → v17) |
| 3 | `b2bd16c` | test(data): Task A.2 — migration 0017 runner discipline regression tests |
| 4 | `5d23a90` | feat(data): Task A.3 — RiskPolicy dataclass + risk_policy repo with `__post_init__` validator |
| 5 | `b737c41` | feat(trades): Task A.4 — risk_policy service (supersession + cfg-cascade + TOML divergence helper) |
| 6 | `9d75f47` | feat(web,cli): Task A.5 — Phase 5 config cascade + post-schema-validation TOML divergence hooks |
| 7 | `088c837` | feat(cli): Task A.6 — swing config policy CLI group (show / set / import-from-toml / history) |
| 8 | `937042d` | feat(trades,data): Task A.7 — Phase 7 entry + Phase 6 review-complete stamps for risk_policy_id |
| 9 | `6b2a51a` | fix(phase9-bundle-A): Codex R1 Major #1 + #3 + #4 + Minor #2 — seed ratification + web banner + CLI cascade + ON DELETE SET NULL |
| 10 | `6352a9a` | fix(phase9-bundle-A): Codex R2 Major #1 + #2 + #3 + Minor #1 — reset cascade + effective-cfg ratification + non-blocking-removal + log spam |
| 11 | `25f158d` | fix(phase9-bundle-A): Codex R3 Major #1 + #2 + #3 — extended import-from-toml + raw-cfg web reset + no-op cascade skip |
| 12 | `e3e9e17` | fix(phase9-bundle-A): Codex R4 Major #1 + Minor #1 — web /config save no-op skip + import-from-toml docstring |

**Total: 12 commits = 8 task-impl (T-A.0..T-A.7) + 4 Codex-fix.** Zero `--no-verify`, zero `--amend`, zero Claude co-author footers.

---

## §2 Codex adversarial-review chain

5-round convergent shape; matches the dispatch-brief §2.1 expected 3-5 round budget.

| Round | New Critical | New Major | New Minor | Verdict | Disposition |
|---|---|---|---|---|---|
| **R1** | 0 | 4 | 2 | ISSUES_FOUND | M#1 ACCEPT-WITH-RATIONALE-then-FIX (cfg-derived seed via post-migration ratification helper); M#2 ACCEPT-WITH-RATIONALE (T-A.5 cfg-cascade keeps user-config in sync; round-trip test added); M#3 RESOLVED (visible web divergence banner); M#4 RESOLVED (legacy `swing config set` now cascades). m#1 ACCEPT (V2 — `--value null` for nullable fields). m#2 RESOLVED (ON DELETE SET NULL on stamp FKs per spec §3.6). |
| **R2** | 0 | 3 | 1 | ISSUES_FOUND | M#1 RESOLVED (config reset cascades to risk_policy on CLI + web); M#2 RESOLVED (ratification uses `apply_overrides` over raw cfg); M#3 RESOLVED (ratification failure raises `ClickException` — non-zero exit). m#1 RESOLVED (per-render `silent=True` kwarg suppresses log spam). |
| **R3** | 0 | 3 | 0 | ISSUES_FOUND | M#1 RESOLVED (`_TOML_MIRROR_MAP` extended to all 4 spec §3.1.3 SEED MAP fields; ratification-not-retryable kept single-fire as ACCEPT-WITH-RATIONALE — repair path is per-field `import-from-toml`); M#2 RESOLVED (web reset reloads raw cfg via `app.state.cfg_path`); M#3 RESOLVED (no-op cascade skip on CLI set / CLI reset / web reset). |
| **R4** | 0 | 1 | 1 | ISSUES_FOUND | M#1 RESOLVED (web `config_save` cascade now does the same no-op skip — 4th cascade emitter brought into parity); m#1 RESOLVED (stale `import-from-toml` docstring updated). |
| **R5** | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** | Convergence reached. |

**Convergent tapering:** R1 (4M+2m) → R2 (3M+1m) → R3 (3M+0m) → R4 (1M+1m) → R5 (0M+0m). Mirrors Phase 8 daily-management executing-plans precedent (5 rounds).

**ZERO Critical findings across all 5 rounds.** All 14 raised Major findings either RESOLVED in-tree or ACCEPT-WITH-RATIONALE with discriminating regression tests added.

### §2.1 ACCEPT-WITH-RATIONALE positions banked for orchestrator triage

1. **R1 M#1 partial accept (then mostly resolved by ratification helper):** The migration's hard-coded SQL seed values cannot Python-eval `cfg` at `executescript` time. The post-migration `ratify_seed_from_cfg_on_v17_landing` helper invoked by `swing/cli.py:db_migrate` after the v16→v17 transition replaces the hard-coded defaults with cfg-derived values for all 4 spec §3.1.3 SEED MAP fields. RESOLVED via this helper.
2. **R1 M#2 ACCEPT-WITH-RATIONALE:** `apply_overrides()` re-applies user-config.toml's `risk_equity_floor` on every read, theoretically undoing the startup divergence correction. In the canonical V1 flow (T-A.5 cfg-cascade in Phase 5 form + new T-A.5/Major-#4 cfg-cascade in legacy `swing config set` CLI), user-config.toml stays in lockstep with risk_policy — both written together. Hand-edit user-config.toml divergence is a degenerate path now visibly surfaced by the new web banner + CLI stderr advisory (R1 M#3) and is V2 hardening (extend divergence helper to also check user-config.toml directly). Discriminating round-trip test `test_t_a_5_cfg_cascade_keeps_user_config_in_sync_with_policy` proves cfg-cascade keeps both sides consistent + no banner renders post-cascade.
3. **R3 M#1 ACCEPT-WITH-RATIONALE on the "single-fire ratification" half:** Ratification gate stays at `pre_version <= 16 AND post_version >= 17` (single-fire). Re-firing on subsequent `db-migrate` calls would clobber operator's intentional `swing config policy set` edits made BETWEEN the failed migration and the repair. Repair is now per-field via `swing config policy import-from-toml --field <name>` covering all 4 ratifiable fields (R3 M#1 fix's other half).
4. **R1 m#1 ACCEPT-banked-for-V2:** `_coerce_policy_value` lacks NULL spelling — operator currently has no CLI path to clear `drawdown_pause_threshold_R` etc. via `swing config policy set --value null`. V2 hardening: support `--value none`/`null` for nullable fields.

---

## §3 Test count delta + ruff baseline delta

**Test count:**
- Pre-Bundle-A baseline (per dispatch brief §0.3): 2328 fast tests passing (1 skipped; 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures NOT regressions).
- Post-Bundle-A: **2462 fast tests passing** (1 skipped; same 3 pre-existing failures excluded).
- **Delta: +134 fast tests** (above the dispatch brief §0.4 +40-+80 projection — Codex-driven defensive tests pushed the count higher; matches Bundle-2/3 precedent of biased-low-projection vs Codex-driven-overshoot).

Per-task breakdown:
- T-A.0 datetime_helpers: +11
- T-A.1 migration_0017: +31
- T-A.2 migration_0017_runner_discipline: +5
- T-A.3 risk_policy_repo + RiskPolicy validator: +27
- T-A.4 risk_policy_service: +14
- T-A.5 hooks (CLI + web lifespan + Phase 5 cascade): +11
- T-A.6 config_policy CLI: +8
- T-A.7 entry + review stamps: +9
- Codex R1+R2+R3+R4 fixes (12 new test files): +18

Pre-existing test fixture update: `tests/trades/test_entry.py:_seed_v14` bumped `target_version=16` → `17` so `record_entry`'s new T-A.7 stamp UPDATE finds the risk_policy table. All 48 pre-existing entry tests pass.

Mechanical version-bump regression: 7 pre-existing tests asserted `EXPECTED_SCHEMA_VERSION == 16` or `migration X advances to 16`; all updated to `17` with comments noting `ensure_schema` walks to HEAD post-0017.

**Ruff baseline:** 18 (E501 only) — **UNCHANGED** from pre-Bundle-A baseline. Per-line `# noqa: N803/N815` comments added on spec-driven mixed-case columns (`drawdown_*_R`, `scratch_epsilon_R`, `trail_MA_*`) in `swing/data/models.py` + `swing/data/repos/risk_policy.py` mirroring the Phase 8 daily_management_records pattern.

---

## §4 Operator-witnessed verification surfaces (per dispatch brief §3)

**Status: PENDING orchestrator-driven verification.** The following 5 surfaces enumerated in the dispatch brief §3 require operator-witnessed verification before integration merge.

| # | Surface | Description |
|---|---|---|
| **S1** | Pre-migration baseline | Operator runs `swing db-migrate --check` from worktree; verifies `current_version=16, pending=0` (or expected post-T-A.1 state). Verifies `python -m pytest -m "not slow" -q` GREEN. |
| **S2** | Post-migration policy show | Operator runs `swing db-migrate` then `swing config policy show`; verifies seed `policy_id=1` prints with all 34 fields from `swing.config.toml` cascaded (Codex R1 M#1 fix: ratification firing on v17 first-time landing supersedes the hard-coded seed with operator's actual cfg values for the 4 mirrored fields). |
| **S3** | Policy supersession | Operator runs `swing config policy set --field max_account_risk_per_trade_pct --value 0.75 --notes "operator test"`; verifies new `policy_id=2` created; `policy_id=1` has `is_active=0` + `superseded_by_policy_id=2`. Discriminating CLI output renders the supersession audit. |
| **S4** | Phase 7 entry stamp | Operator navigates to `/trades/entry`, creates a new test trade; verifies the new `trades` row has `risk_policy_id_at_lock=2` (the currently active policy after S3). |
| **S5** | Phase 6 review-complete stamp | Operator navigates to a review-eligible trade's `/reviews/{id}/complete`, completes the review; verifies the `review_log` row has `risk_policy_id_at_review_completion=2`. |
| **S6** | pytest + ruff | From worktree: `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows ≤18. Verified by implementer; operator reverifies on integration. |

**Additional V2-banked operator-witnessed surface (added by Codex R1 M#3 fix):**

| # | Surface | Description |
|---|---|---|
| **S2.bis** | Web divergence banner | Operator hand-edits `swing.config.toml` to change `risk_equity_floor` to a value differing from active policy; navigates to `/config`; verifies yellow-banner warning renders with both diverging values + operator-actionable `swing config policy import-from-toml --field capital_floor_constant_dollars` command. |

---

## §5 Per-task deviations from the plan

| Deviation | Source | Disposition |
|---|---|---|
| Plan T-A.1 test scaffold uses `init_db(db_path)`; existing repo public surface is `ensure_schema(db_path)` | Plan-vs-shipped-API mismatch | Used `ensure_schema` throughout T-A.1 tests. No `init_db` helper introduced. |
| Plan T-A.1 legacy-trade INSERT test uses outdated columns (`action`, `planned_risk_budget_dollars`) | Plan was drafted against an older trades schema; Phase 7 migration 0014 dropped those columns | Test rewritten using actual current trades schema columns (`ticker`, `entry_date`, `entry_price`, `initial_shares`, `initial_stop`, `current_stop`, `state`, `sector`, `industry`, `trade_origin`, `pre_trade_locked_at`, `current_size`). |
| Plan T-A.4 `_VALID_FIELDS` whitelist did not enumerate metadata exclusions explicitly | Plan focused on the 28 editable fields | Service rejects PK/metadata smuggling (policy_id, effective_from, effective_to, is_active, superseded_by_policy_id, created_at) via the same whitelist exclusion. Discriminating test `test_supersede_rejects_pk_or_metadata_field` pins this boundary. |
| Plan §B file-map listed `seed_initial_policy(conn, cfg)` as called from migration runner OR migration SQL | Migration SQL cannot Python-eval cfg | `seed_initial_policy` ships as a fall-back service helper (test-fixture support) only; the migration's hard-coded INSERT seeds at v17 + `ratify_seed_from_cfg_on_v17_landing` (NEW helper added per Codex R1 M#1) supersedes from cfg post-migration. |
| Plan §B file-map for T-A.5 listed CLI hook as "every CLI handler that needs a divergence-corrected cfg" | Touching every handler is heavy | Centralized in `@main.callback` at `swing/cli.py:main` with explicit skip-list (`db-migrate`, `db-backup`). One invocation site, applies before every subcommand except the skip-listed ones. |
| Plan T-A.6 CLI did not enumerate `import-from-toml` field count | V1 spec §3.1.3 mentioned only 1 field had a Phase-5-surfaced cfg counterpart | Initially limited to 1 field; Codex R3 M#1 expanded to all 4 spec §3.1.3 SEED MAP fields to support post-ratification-failure repair workflow. |
| Plan T-A.7 plan-template used `record_entry(conn, req)` without required kwargs | Plan-vs-shipped-API mismatch | Tests use `record_entry(conn, req, soft_warn=10, hard_cap=20, force=True)` per the actual signature. |
| Migration 0017 ALTER ADD COLUMN initially missing `ON DELETE SET NULL` | Spec §3.6 explicitly requires it; plan §B file-map didn't enumerate the FK action | Added `ON DELETE SET NULL` to both stamps via Codex R1 m#2 fix. |
| Codex R1 M#1 introduced a NEW helper `ratify_seed_from_cfg_on_v17_landing` not in plan §B | Required by spec §3.1.3 SEED MAP semantics + atomic-migration constraint | Added; documented inline + tested. The plan's §B file-map should be amended in V2 to include it. |
| Codex R1 M#3 introduced a NEW VM field `risk_policy_divergence` on `ConfigPageVM` | Required by spec §3.1.3 R3 Minor #2 binding "yellow-banner warning until resolved" | Added; passes the base-layout VM rule (the field has a safe `None` default; only ConfigPageVM is affected). |

---

## §6 Codex Major findings ACCEPTED with rationale

Per dispatch brief §4 target: **zero accept-with-rationale.** Bundle A landed **TWO** ACCEPT-WITH-RATIONALE positions on Major findings (above target):

1. **R1 M#2** (apply_overrides re-applies user-config.toml override) — V1 trusts the canonical T-A.5 cfg-cascade flow to keep user-config.toml in sync with risk_policy; hand-edit user-config.toml divergence is V2 hardening (extend divergence helper to also check user-config.toml directly, not just post-overlay cfg). Discriminating round-trip test added proving cfg-cascade keeps both sides consistent.

2. **R3 M#1** (ratification not retryable on subsequent db-migrate runs) — single-fire gate kept; re-firing would clobber operator's intentional CLI policy edits made between failed migration and repair. Per-field repair via `swing config policy import-from-toml` now covers all 4 ratifiable fields (the OTHER half of R3 M#1's fix), giving operator a complete documented recovery workflow.

Both ACCEPT-WITH-RATIONALE positions are operator-recoverable + spec-aligned (V1-scoped per spec §3.1.3); orchestrator triage may elect to bank as V2 hardening items.

---

## §7 Watch items surfaced but not acted on

(For Sub-bundles B/C/D/E to absorb OR for orchestrator-context capture.)

1. **TOML comment-stripping via `write_user_overrides` (tomli_w parse-then-emit).** The Phase 5 cfg-cascade write path (`swing/web/routes/config.py:config_save` → `write_user_overrides`) strips operator comments from `user-config.toml` because tomli_w doesn't preserve them. This is a structural limitation that existed pre-Bundle-A; Bundle A inherits via the cfg-cascade. V2 hardening item: switch `write_user_overrides` to a comment-preserving TOML writer (tomlkit) OR document the constraint in the operator manual.
2. **Test pollution risk: `swing/config_user.py:_user_home()` reads `USERPROFILE`/`HOME` env vars unmonkeypatched.** Tests that exercise `write_user_overrides` (any T-A.5 cascade test, T-A.6 CLI tests, T-A.5 lifespan tests) MUST `monkeypatch.setenv("USERPROFILE", str(home))` and `monkeypatch.setenv("HOME", str(home))` before invoking — otherwise writes leak to the operator's REAL `~/swing-data/user-config.toml`. Codified in the 5 fixed test files (test_cli_config_set_cascade.py / test_cli_config_reset_cascade.py / test_config_policy_cli.py / test_cli_toml_divergence_post_schema_hook.py / test_web_lifespan_toml_divergence_hook.py / test_config_page_divergence_banner.py / test_cli_config_policy_import_from_toml_extended.py / test_cli_config_reset_no_op_skip.py). Mid-Codex-R1 the operator's real user-config.toml accumulated test pollution; restoration was performed manually. **Bank as orchestrator-context lesson**: any future test fixture that exercises the user-config.toml write path MUST monkeypatch USERPROFILE+HOME.
3. **`_TOML_MIRROR_MAP` divergence: `_RISK_POLICY_CASCADE_MAP` (web routes + CLI config_set) only covers 1 field; `_TOML_MIRROR_MAP` (CLI policy import-from-toml) covers all 4.** The asymmetry is intentional per spec §3.1.3 (only ONE Phase-5-surfaced field is mirrored in V1) but a future-maintenance hazard. V2 should consolidate the maps OR add a comment warning future maintainers that the asymmetry is by-design.
4. **Migration `executescript` cannot Python-eval cfg.** The seed values are hard-coded in SQL; the post-migration ratification step is the canonical cfg-derived seed mechanism. V2 may consider migrating to a Python-driven migration runner (alembic-style) that supports parameterized seeds.
5. **No `--value null` for nullable risk_policy fields via `swing config policy set`.** `_coerce_policy_value` only parses int/float/string; operator currently cannot clear `drawdown_pause_threshold_R` etc. V2 add NULL spelling support.
6. **Spec §3.2 + §3.3 column counts ("17" + "18") are brainstorm miscounts; actual counts (verified at T-A.1) are 19 + 19.** Plan §A.0.1 covered the risk_policy 28-vs-34 reconciliation; the same spec-text-vs-column-list pattern applies to reconciliation_runs and reconciliation_discrepancies. No code impact (the column LIST is the binding artifact + tests assert the LIST), but the spec text should be amended in V2.
7. **DeprecationWarning on `datetime.utcnow()` in `swing/data/datetime_helpers.py`.** Python 3.12+ deprecated `utcnow()`. Spec/plan literally use the API; tests rely on the specific `utcnow()` monkeypatch surface. V2 should migrate to `datetime.now(UTC).replace(tzinfo=None)` with a corresponding test-fixture update.

---

## §8 Worktree teardown status

Pending integration merge by orchestrator. Branch + worktree retained at `e3e9e17`. ACL-locked husk expected after orchestrator's merge + cleanup script (per Phase 8 / Bundle-2/3 precedent).

---

## §9 Composition-surface verification

**NOT applicable for Sub-bundle A** — no advisory composition surfaces touched. Advisory rules (Phase 3e.8 Bundles 1+2+3) are independent of risk_policy. The risk_policy stamps on `trades` and `review_log` are pure FK additions; existing advisory composition surfaces (web ×4 + pipeline briefing + CLI) are read-only against the new columns and require no thread-through changes in Bundle A.

---

## §10 Bundle B/C/D/E hand-off notes

For the orchestrator dispatching Sub-bundle B next:

1. **Migration 0017 is locked + frozen.** Sub-bundles B/C/D/E **DO NOT modify it.** All 5 new tables + 2 ALTER ADDs + all indexes + all seed rows are in place at branch HEAD.
2. **Production DB upgrade path:** operator runs `swing db-migrate` after merging Bundle A. The new `_phase9_backup_gate` fires only on `current_version == 16 AND target_version >= 17` (filename `swing-pre-phase9-migration-<ISO>.db`). Post-migration, `ratify_seed_from_cfg_on_v17_landing` supersedes the hard-coded seed with the operator's actual cfg values for the 4 spec §3.1.3 SEED MAP fields. Failure of ratification raises ClickException + exits non-zero with operator-actionable repair instructions.
3. **Bundle B (reconciliation depth) consumes `reconciliation_runs` + `reconciliation_discrepancies` tables already created by 0017.** Bundle B implements the repos + service + CLI + tos_import.py refactor.
4. **Bundle C (hypothesis_status_history + account_equity_snapshots) consumes the tables already created by 0017** including the per-hypothesis seed rows (one row per existing hypothesis_registry row, normalized to day-start anchor per spec §3.4.1 R3 Major #2).
5. **Bundle D (sector/industry tamper hardening) consumes risk_policy + reconciliation_runs + reconciliation_discrepancies** for the audit-row emission on rejection path (`source='system_audit'` per spec §3.2 + plan §A.4).
6. **Bundle E (E2E + polish) integration-tests the full arc.**
7. **`swing/trades/risk_policy.py:supersede_active_policy` + `read_active_policy` + `seed_initial_policy` + `ratify_seed_from_cfg_on_v17_landing` + `check_and_reconcile_toml_divergence` are the canonical service-layer entry points.** Sub-bundles B/C/D/E should use these (or the repo CRUD in `swing/data/repos/risk_policy.py`) rather than direct SQL.
8. **Single-write-path for hypothesis status (plan §A.1):** Sub-bundle C deletes `swing/data/repos/hypothesis.py:update_hypothesis_status` and introduces `swing/trades/hypothesis.py:update_hypothesis_status_with_audit`. The repo function is currently called from EXACTLY ONE site per plan §A.1.1 grep recon (`swing/cli.py:hypothesis_update_cmd`); Bundle C rewires that handler.
9. **Phase 7 + Phase 8 transactional discipline FORWARD-BOUND:** Bundle B's reconciliation service + Bundle C's hypothesis_status_history service MUST follow the same "reject caller-held tx + own BEGIN IMMEDIATE / COMMIT / ROLLBACK + reject-don't-auto-detect" contract codified in `swing/trades/risk_policy.py:supersede_active_policy` + `seed_initial_policy`. Discriminating regression tests must verify caller-held-tx rejection.
10. **Cross-bundle Codex review depth:** Bundle A's 5-round Codex chain (4M+2m → 3M+1m → 3M+0m → 1M+1m → 0M+0m) is a useful baseline. The schema-foundation scope of Bundle A explored a wider attack surface than the consumer-side Bundles B-E will; subsequent bundles should converge faster (3-4 rounds expected).

---

## §11 Operator-side action items

1. **Verify `c:\Users\rwsmy\swing-data\user-config.toml` is intact** post-mid-Codex-R1 manual restoration. Implementer-side restoration was attempted then operator-restored; current state per implementer's last read shows integrations-only (`[integrations.finviz]` token + screen_query preserved). Operator's prior comments may have been lost in implementer's restoration attempt — **operator already addressed this and restored from a known-good source**.
2. **Add to orchestrator-context "Lessons captured":**
   - Test pollution: `swing/config_user.py:_user_home()` reads USERPROFILE/HOME unmonkeypatched. Any future test fixture exercising the user-config.toml write path MUST monkeypatch both env vars.
   - `write_user_overrides` (tomli_w) strips operator comments. V2 candidate: switch to tomlkit OR document the constraint.
3. **Add to CLAUDE.md gotchas (forward-binding for Bundle B/C/D/E):**
   - Phase 9 ratification helper `ratify_seed_from_cfg_on_v17_landing` is the single-fire (v16→v17 transition only) cfg-derived seed mechanism. Subsequent db-migrate runs intentionally do NOT re-fire to avoid clobbering operator's CLI policy edits. Repair path: per-field `swing config policy import-from-toml`.
   - All four cascade emitters (CLI `config set`, CLI `config reset`, web `POST /config`, web `POST /config/reset/{field}`) MUST do the no-op-skip check (compare would-be value to active policy value) before invoking `supersede_active_policy`. Pattern is per-emitter; future emitters MUST mirror it.
4. **Operator-witnessed verification gate** (§4 surfaces S1-S6 + S2.bis) — orchestrator drives.

---

## §12 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-11.
- **Brief commit:** `51ee033` on main.
- **Implementer-spawn:** Subagent dispatched 2026-05-12.
- **Total wall-clock:** ~6 hr implementation + ~1.5 hr Codex convergence (5 rounds). Below the dispatch-brief §0 expected duration of "12-16 hr implementation + 2-4 hr Codex convergence".
- **Marker file:** removed before R1 invocation per dispatch brief §2.1 step 1.
- **Codex thread:** `019e1ae9-421b-7610-af4e-8702108b0228` (preserved through R5).
- **Final HEAD:** `e3e9e17` on `phase9-bundle-A-risk-policy-foundation`.
- **Sub-bundle B dispatch dependency:** A's migration must merge to main + production DB at v17 (operator runs `swing db-migrate`) before B can dispatch. Orchestrator commissions B after operator-witnessed gate PASS + integration merge.

---

*End of return report. Standing by for orchestrator integration merge + Sub-bundle B dispatch.*
