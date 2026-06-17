# Implementation plan — out-of-framework holding carve-out (path B)

**Phase / arc:** Phase 18 rider — the SPCX out-of-framework holding carve-out (path B, ignore-entirely).
**Author:** dispatched implementer (writing-plans), 2026-06-17.
**Sources (read in full before executing):**
- RD commissioning brief — `docs/out-of-framework-holding-carveout-commissioning-brief.md` (problem, scope, the measurement LOCKS L1-L4, verification §6, out-of-scope §7).
- CHARC architecture pass = **THE SPEC** — `docs/out-of-framework-holding-carveout-charc-architecture-pass.md` (verdict GO; binding conditions C1-C5; the design is SETTLED there — this plan implements exactly it, does NOT re-open it).
- The dispatch recipe — `docs/implementer-dispatch-recipe.md` (TDD + commit conventions; the WSL-Codex review; the return report).

**Review tier for the EXECUTING dispatch: `review-strong` (binding).** This arc ships PRODUCTION code into `swing/trades/` (the authorized carve-out) + `swing/config` + `swing/integrations/schwab`. The executing review MUST be `review-strong` with repo-access (the recipe's PRODUCTION-CODE repo-access note — the carve-out's correctness depends on the surrounding orphan-pass + caller reference graph). `codex-auto-review` (repo-access, matched-high effort) runs alongside as the complementary second eye. This writing-plans review is `review-fast` (not the binding gate).

---

## 1. Overview + the settled design

The operator bought 2 SPCX IPO shares **outside the swing framework** (a long-term buy-and-hold investment, ~$412), tracked in Schwab where it belongs — NOT swing capital. Phase-18 arc 18-H.6 turned that untracked broker holding into a first-class `untracked_broker_position` reconciliation discrepancy, and the Schwab-driven orphan pass emits a **fresh orphan every run** while the position is untracked (acknowledging one does not stop the next — the classify pivot leaves it `unresolved`). Path B carves declared out-of-framework holdings out of the swing system **at the reconciliation boundary**: SPCX (and any future declared holding) is never journaled as a trade, so it cannot contaminate measurement (L1, by construction), and it stops cry-wolf re-emitting the orphan every night.

### The SETTLED design (CHARC architecture pass — do NOT re-litigate)

- **Registry = a config list, NOT a table (Ruling 1 / C5).** A declared `out_of_framework_tickers` list under a `[reconciliation]` section in **`user-config.toml`** (operator-specific declaration — the same posture as `account_hash` / the finviz token). **NO schema, NO table, NO migration.** Default = empty list. The path-B carve-out only needs the ticker SET to skip the orphan emit; qty/MV come from the broker pull, not the registry.
- **Carve-out (C1/C2).** In `swing/trades/schwab_reconciliation.py` (the Schwab-driven orphan pass at the grounded anchor `:1304-1367`): do NOT emit `untracked_broker_position` for a ticker on the declared set; SURFACE the exclusion as a `#27`-style line in the recon output (the `cash_warnings` channel) — never a silent skip. An UNDECLARED untracked broker position STILL banners.
- **Existing-row resolve (Ruling 3 / C3).** Resolve the existing declared-ticker (SPCX) `unresolved`/`pending_ambiguity_resolution` orphan rows to `acknowledged_immaterial` at landing — SCOPED to declared tickers ONLY, with an audited `resolution_reason` (the out-of-framework declaration). A scoped landing operation that wraps the existing, battle-tested `swing/trades/reconciliation.py:resolve_discrepancy` service (which already owns its tx, auto-clears `ambiguity_kind`, and decrements the run's unresolved counter).
- **§2.4 coherence refinement = DEFERRED (Ruling 2 / C4).** Minimal B (items 1-3) ONLY. This plan does NOT include the swing-NLV redefinition. Minimal B already satisfies L2 (broker is non-flat while held → the both-flat `equity_delta` gate stays suppressed; no false delta).
- **No new module / no standing process (C5).** Registry = a config field. Carve-out = `schwab_reconciliation.py`. Optional thin CLI = `cli_config.py`. The read-only `swing/trades` default returns after the arc.

### Grounded code facts (re-verified against live code on the worktree base — anchors WILL drift; re-ground before editing)

| Fact | Location (grounded) |
|---|---|
| Orphan pass builds `journal_open_tickers = {t.ticker for t in open_trades}` then loops `schwab_positions`, `_emit(... "untracked_broker_position" ...)` for each ticker not in the set | `swing/trades/schwab_reconciliation.py` orphan pass (`journal_open_tickers` assignment; the `for p in schwab_positions:` loop; the `_emit(...)` call ~`:1304-1367`) |
| The classify/dispatch pivot SKIPS `untracked_broker_position` → it stays `unresolved` (re-emits every run) | `schwab_reconciliation.py` `_pivot_classify_and_dispatch_for_run` (`if disc.discrepancy_type == "untracked_broker_position": continue` ~`:590`) |
| The `equity_delta` coherence check fires ONLY when `journal_flat AND broker_flat` | `schwab_reconciliation.py` step 8 (`journal_flat`/`broker_flat`/`if (journal_flat and broker_flat ...)` ~`:1714-1722`) |
| `cash_warnings: list[dict]` is the #27 channel; surfaced via `summary_json["cash_warnings"]` → `_step_schwab_orders` `warnings` → runner `warnings_json` | init ~`:1183`; summary build ~`:1777-1789`; caller surface `integrations/schwab/pipeline_steps.py` ~`:620-628` |
| `run_schwab_reconciliation` signature (kwargs-only; needs a new `out_of_framework_tickers` param) | `schwab_reconciliation.py:run_schwab_reconciliation` ~`:1086-1100` |
| Production caller `_step_schwab_orders` has `cfg` in scope (`schwab_cfg = cfg.integrations.schwab`); invokes `run_schwab_reconciliation` | `integrations/schwab/pipeline_steps.py:_step_schwab_orders` (`:401`; cfg read `:447`; recon call `:579-592`) |
| `config.py:load()` reads tracked `swing.config.toml`; optional sections use `raw.get("<name>", {})` then `XConfig(**...)` (the `review`/`archive` precedent) | `swing/config.py:load` (`:572-659`; `review=ReviewConfig(**raw.get("review", {}))` `:653`) |
| `config_overrides.py:apply_overrides()` layers operator-specific `user-config.toml` values onto base cfg via `dataclasses.replace`; applied at every entry incl. the pipeline (`cli.py:pipeline_run_cmd` `:3291`) | `swing/config_overrides.py:apply_overrides` (`:56-203`); `swing/cli.py:3286-3296` |
| `compute_stats` sweeps the `trades` table (`closed = [t for t in trades_list if t.state in ("closed","reviewed")]`) — a ticker with no `trades` row cannot enter it | `swing/journal/stats.py:compute_stats` (`:172-204`; the `closed` predicate `:179`) |
| `entry_intent` enum = `standard` / `hypothesis_test_by_design` / NULL — no out-of-framework value; `compute_stats` does not filter on it | `swing/data/migrations/0027_entry_intent.sql` CHECK (`:12-13`) |
| `resolve_discrepancy` service — owns `BEGIN IMMEDIATE`, auto `clear_ambiguity_kind` when existing `ambiguity_kind` is non-NULL, decrements run unresolved counter, allows `acknowledged_immaterial` + optional reason, TOCTOU-safe `require_current_resolution`, stamps `resolved_by`/`resolved_at` | `swing/trades/reconciliation.py:resolve_discrepancy` (`:568-697`) |
| migration-0031 cross-column CHECK ties `ambiguity_kind IS NOT NULL` ⟺ `resolution IN (pending_ambiguity_resolution, operator_resolved_ambiguity)`; `acknowledged_immaterial` is a valid resolution value | `swing/data/migrations/0031_untracked_broker_position.sql` (`:55-83`) |
| `update_discrepancy_resolution` (repo) — UPDATE-only (no INSERT OR REPLACE), `clear_ambiguity_kind` flag | `swing/data/repos/reconciliation.py:update_discrepancy_resolution` (`:371-421`) |

---

## 2. Per-task breakdown (TDD-first)

Logical task order: **(i)** config plumbing → **(ii)** the orphan-pass carve-out + the #27 exclusion line → **(iii)** the scoped audited existing-row resolve → **(iv)** OPTIONAL CLI. Each task: one or more red→green→commit cycles. Re-ground every file:line anchor against live code before editing.

> **Test-distinguishing discipline (recipe §2 / memory `feedback_regression_test_arithmetic`):** every test below states the assertion AND the pre-fix vs post-fix value so it provably distinguishes. A test that passes under BOTH paths is worthless.

---

### Task 1 — config plumbing: `[reconciliation] out_of_framework_tickers`

**Purpose.** Add the declared-holdings registry as a config list. Tracked-toml default = empty; the operator's actual declaration lives in `user-config.toml` (operator-specific, like `account_hash`). The registry is the SET of tickers the carve-out (Task 2) and the resolve (Task 3) read.

**Files.**
- `swing/config.py` — add a `Reconciliation` frozen dataclass with `out_of_framework_tickers: tuple[str, ...] = ()`; add it to `Config` (`reconciliation: Reconciliation = field(default_factory=Reconciliation)`); read it in `load()` via the optional-section pattern (`reconciliation=Reconciliation(out_of_framework_tickers=tuple(raw.get("reconciliation", {}).get("out_of_framework_tickers", [])))`). Normalize to uppercased, de-duplicated, sorted `tuple[str, ...]` so the set semantics + audit ordering are deterministic (do the normalization in `__post_init__` or at the load callsite — pick one and test it). Reject a non-list / non-string-element value with a clear `ValueError`/`TypeError` (degrade-or-raise per the existing `__post_init__` discipline — match the `PipelineConfig.__post_init__` style; raising on a malformed TRACKED section is consistent with `load()`'s required-section behavior, but a malformed USER-config value is layered in Task 1b — see below).
- `swing/config_overrides.py` — add an `apply_overrides` block: read `user-config.toml` `reconciliation.out_of_framework_tickers`; when present, `replace(base_cfg, reconciliation=replace(base_cfg.reconciliation, out_of_framework_tickers=<normalized tuple>))`. **Defensive coercion:** a malformed user-config value (not a list, or non-string elements) must NOT crash `apply_overrides` (it runs at every route entry — the existing `logging` block's degrade-never-crash posture is the precedent); coerce string elements, drop non-strings, log a diagnostic, and fall through to the base value rather than raising. This is the genuinely-unconstrained input the recipe's adjudication note says to STILL guard (it is NOT schema-prevented — TOML is free-form).

**TDD — failing tests first.**
1. `test_config_reconciliation_section_defaults_empty` — `load()` of a `swing.config.toml` with NO `[reconciliation]` section → `cfg.reconciliation.out_of_framework_tickers == ()`.
   - Pre-fix: `AttributeError: 'Config' object has no attribute 'reconciliation'`. Post-fix: `()`. **Distinguishes.**
2. `test_config_reconciliation_normalizes_tickers` — a tracked toml carrying `[reconciliation]\nout_of_framework_tickers = ["spcx", "AAPL", "spcx"]` → `("AAPL", "SPCX")` (uppercased, deduped, sorted).
   - Pre-fix: attribute error. Post-fix: the normalized tuple. **Distinguishes** (and pins the normalization contract).
3. `test_apply_overrides_reads_out_of_framework_from_user_config` — monkeypatch BOTH `USERPROFILE` AND `HOME` (CLAUDE.md gotcha: `write_user_overrides` leaks to the real `~/swing-data` otherwise), write a `user-config.toml` `[reconciliation] out_of_framework_tickers = ["spcx"]`, `apply_overrides(base_cfg)` → `cfg.reconciliation.out_of_framework_tickers == ("SPCX",)`.
   - Pre-fix: `()` (the override block does not exist). Post-fix: `("SPCX",)`. **Distinguishes.**
4. `test_apply_overrides_malformed_out_of_framework_does_not_crash` — user-config `out_of_framework_tickers = "SPCX"` (a bare string, not a list) → `apply_overrides` returns a Config (no raise), `out_of_framework_tickers` falls through to base `()` (the plan picks **fall-through-to-base-with-diagnostic** for a non-list, since a bare string is ambiguous — coercing a bare string to `("SPCX",)` is rejected as too-clever; an operator who typed a string without brackets made an error worth a diagnostic, not a silent coercion).
   - **REQUIRED distinguishing form (Codex R1 MINOR #2 — NOT optional):** a "no-raise + falls-through-to-`()`" assertion ALONE is NON-distinguishing (it passes identically whether the override block exists or is absent — both yield `()`). The test MUST additionally PROVE the degrade path actually ran, via EITHER (a) `caplog` asserting the override block logged the malformed-value diagnostic (the preferred form — it directly asserts the block executed and degraded), OR (b) a SECOND, well-formed user-config override key read by `apply_overrides` IN THE SAME CALL whose effect is asserted (proving the block ran). Pre-fix (block absent): no diagnostic logged / the second key not honored → the added assertion FAILS. Post-fix: diagnostic present / second key honored → passes. **This is what makes it distinguish.** Build the test with form (a) by default.

**Acceptance.** `cfg.reconciliation.out_of_framework_tickers` is a normalized `tuple[str, ...]`; empty by default; reads from user-config via `apply_overrides`; malformed user-config degrades (never crashes); the TRACKED `swing.config.toml` MUST NOT carry a declaration (it stays empty — the operator's set lives only in `user-config.toml`). `ruff check swing/` clean.

> **Design note (settled, not re-opened) — `user-config.toml` is the SOLE authoritative source (Codex R1 MINOR #1).** Per CHARC Ruling 1, the operator's SPCX declaration is operator-specific data and lives ONLY in `user-config.toml` (the same posture as `account_hash` / the finviz token). **The tracked `swing.config.toml` MUST stay empty of any `[reconciliation] out_of_framework_tickers` declaration** — this is a contract, not just a default. Reading the section in `load()` (tracked) exists ONLY to give the dataclass field a home (default `()`) so `apply_overrides` can `replace()` it; the OPERATIVE declaration arrives EXCLUSIVELY via the user-config override block. (This mirrors `account.risk_equity_floor`: a tracked default that the user-config override supersedes — and like the finviz `token`, the executing implementer SHOULD NOT add a tracked-toml row.) If the executing implementer prefers, the load-side read MAY be omitted entirely (field defaults to `()` via `default_factory`, override layered in `apply_overrides` only) — that is an equally-valid realization of the same contract and arguably cleaner; the executing dispatch picks one and tests it.

---

### Task 2 — orphan-pass carve-out + the #27 exclusion line

**Purpose.** In the Schwab-driven orphan pass, skip emitting `untracked_broker_position` for a ticker on the declared set, AND surface the exclusion as a `#27`-style `cash_warnings` line (never silent). Thread the declared set from the production caller through to the reconciliation function.

**Files.**
- `swing/trades/schwab_reconciliation.py`:
  - `run_schwab_reconciliation` — add a new kwarg `out_of_framework_tickers: tuple[str, ...] = ()` (default empty preserves every existing caller + test verbatim). Normalize to an uppercased `frozenset[str]` once at the top of the function (so the per-position membership test is O(1) and case-insensitive against the Schwab symbol).
  - The orphan pass loop (~`:1304-1367`): after resolving `sym` (the broker symbol) and BEFORE the `_emit(...)`, add `if sym.upper() in out_of_framework_set:` → append a `cash_warnings` entry `{"step": "schwab_orders", "reason": "out_of_framework_excluded", "detail": f"{sym}: {broker_qty:+.2f} sh @ {mv_text} excluded (operator-declared out-of-framework)"}` and `continue` (skip the emit). Place the carve-out AFTER the existing non-finite-qty guard + the zero-net `abs(broker_qty) <= price_tolerance` skip (so a declared ticker that is zero-net is simply skipped as before; the carve-out only matters for held declared positions) and AFTER `broker_mv`/`mv_text` are computed (so the exclusion line carries qty + MV — the L3 auditable detail the brief's example shows: "out-of-framework holdings excluded: SPCX 2sh @ $412"). Increment a new summary counter `out_of_framework_excluded_count` (init in `counters` alongside the others; surface it in `summary`).
  - The `summary` dict (~`:1777-1789`): add `"out_of_framework_excluded_count": counters.get("out_of_framework_excluded_count", 0)`. (`cash_warnings` is already in the summary, so the exclusion lines surface automatically.)
- `swing/integrations/schwab/pipeline_steps.py:_step_schwab_orders` — at the `run_schwab_reconciliation(...)` call (~`:579-592`), pass `out_of_framework_tickers=cfg.reconciliation.out_of_framework_tickers`. (`cfg` is in scope; the production cfg has overrides applied at the pipeline entry — Task 1's grounding confirms this.)

**TDD — failing tests first (build fixtures from the REAL emitter shape — a Schwab position dict `{"instrument": {"symbol": ...}, "longQuantity": ..., "marketValue": ...}` per the grounded orphan-pass reads).**
1. `test_declared_ticker_emits_no_untracked_orphan` — run `run_schwab_reconciliation` with a Schwab position for `SPCX` (held, non-zero qty), `open_trades` empty (no journal trade), `out_of_framework_tickers=("SPCX",)`. Assert ZERO `untracked_broker_position` rows for `SPCX` after the run.
   - Pre-fix (param absent / not threaded): one `untracked_broker_position` row emitted for SPCX. Post-fix: zero. **Distinguishes.**
2. `test_undeclared_untracked_position_still_banners` (**the L3 / C2 discriminator**) — same setup but a position for `FOO` (NOT declared) alongside `SPCX` (declared). Assert: ZERO `untracked_broker_position` for SPCX, EXACTLY ONE `untracked_broker_position` for FOO, `resolution='unresolved'`.
   - Pre-fix: two orphans (FOO + SPCX). Post-fix: one (FOO only). **Distinguishes** — proves the carve-out is scoped to the declared set, NOT a blanket "ignore unknowns."
3. `test_carveout_surfaces_in_summary_warnings` (**C2 / #27 visibility**) — declared SPCX held → `run.summary_json` parsed → `cash_warnings` contains an entry with `reason == "out_of_framework_excluded"` and a `detail` mentioning `SPCX` + the qty + the MV; AND `summary["out_of_framework_excluded_count"] == 1`.
   - Pre-fix: no such warning entry (KeyError / empty). Post-fix: present. **Distinguishes** — proves the skip is NOT silent.
4. `test_default_empty_out_of_framework_preserves_orphan` (regression guard) — run with `out_of_framework_tickers=()` (the default) and an untracked SPCX position → SPCX STILL emits an `untracked_broker_position` orphan (the 18-H.6 behavior is byte-identical when nothing is declared).
   - Pre-fix == Post-fix for the orphan-present assertion, BUT this guards that the carve-out does not accidentally fire on the empty set. State explicitly it is a no-regression guard, not a distinguishing test (its value is catching an over-eager empty-set carve-out).
5. `test_step_schwab_orders_threads_declared_set` — a `_step_schwab_orders` test (production-path wiring, the byte-tests-insufficient lesson) with a cfg whose `reconciliation.out_of_framework_tickers=("SPCX",)` and a stubbed client returning an SPCX position → no SPCX orphan. Exercises the REAL caller→recon wiring, not just `run_schwab_reconciliation` in isolation.
   - Pre-fix: SPCX orphan (param not threaded at the caller). Post-fix: no SPCX orphan. **Distinguishes** the caller-wiring specifically.

**Acceptance.** A declared held ticker produces ZERO orphans across runs; an undeclared untracked position STILL banners `unresolved`; the carve-out surfaces in `cash_warnings` + the new summary counter; the empty-set default is byte-identical to pre-arc behavior; the wiring is exercised end-to-end through `_step_schwab_orders`. `ruff check swing/` clean.

---

### Task 3 — scoped, audited, idempotent existing-row resolve (C3)

**Purpose.** Clear the existing declared-ticker SPCX `unresolved`/`pending_ambiguity_resolution` orphan rows to `acknowledged_immaterial` with an audited `resolution_reason` — SCOPED to declared tickers ONLY, idempotent, atomic. The carve-out (Task 2) prevents FUTURE orphans; this clears the banner for the rows ALREADY in the DB.

**Mechanism (settled implementer call, within CHARC's latitude).** A new scoped landing function `resolve_out_of_framework_orphans(conn, *, out_of_framework_tickers, resolution_reason_prefix=...) -> int` in `swing/trades/schwab_reconciliation.py` (the authorized carve-out module). It:
1. Returns 0 immediately if `out_of_framework_tickers` is empty (no-op).
2. Queries `reconciliation_discrepancies` for rows WHERE `discrepancy_type = 'untracked_broker_position'` AND `UPPER(ticker) IN (<declared set>)` AND `resolution IN ('unresolved', 'pending_ambiguity_resolution')` (the only two states the orphan can be in — the classify pivot leaves it `unresolved`; a legacy ID-68-style row may be `pending_ambiguity_resolution`). Build the `IN (?, ?, ...)` clause via the `",".join("?"*len(values))` discipline; short-circuit empty (CLAUDE.md gotcha — `IN ()` is invalid SQL).
3. For EACH matched row, call the existing `swing/trades/reconciliation.py:resolve_discrepancy(conn, discrepancy_id=..., resolution="acknowledged_immaterial", resolution_reason=f"{prefix}: <ticker> declared out-of-framework", require_current_resolution=<the row's current resolution>)`. `resolve_discrepancy` owns its OWN `BEGIN IMMEDIATE` per call (so the landing function MUST NOT hold an open tx — it does NOT; it reads the candidate rows in an implicit read tx, then calls `resolve_discrepancy` per row, each its own atomic write). `resolve_discrepancy` auto-handles `clear_ambiguity_kind` for the `pending_ambiguity_resolution` row (the live-ID-68 path) and decrements the run's unresolved counter. The `require_current_resolution` argument closes the read→resolve TOCTOU (a concurrent resolver that committed first → that row is skipped via `DiscrepancyResolutionStateError`, caught + logged + counted-as-skipped, not fatal).
4. Returns the count resolved.

**Idempotency (C3).** Because the query filters on `resolution IN ('unresolved','pending_ambiguity_resolution')`, a SECOND call finds zero rows (the first call moved them to `acknowledged_immaterial`) → returns 0, no-op. The TOCTOU guard + the filter make re-running safe.

**Scope (C3 / L3).** The `UPPER(ticker) IN (<declared set>)` filter is the scoping — ONLY declared tickers are resolved. An undeclared orphan is never touched by this function.

**Invocation surface.** A CLI command `swing schwab resolve-out-of-framework` (or fold it into the optional Task 4 CLI) that calls the landing function with `cfg.reconciliation.out_of_framework_tickers`. **Do NOT** call the resolve from inside `run_schwab_reconciliation` (it would nest `resolve_discrepancy`'s `BEGIN IMMEDIATE` inside the run's outer transaction → the `in_transaction` reject / caller-held-tx error; the recipe's repo-vs-service-asymmetry gotcha). The operator-driven CLI invocation (a one-shot clear after declaring SPCX) is the clean surface, mirroring the operator live gate. (If the executing implementer finds a clean post-COMMIT call site, that is acceptable — but the default is the CLI surface, NOT inside the run tx.)

**TDD — failing tests first (plant the pre-existing orphan rows via RAW `conn.execute` INSERT — the cross-arc write-barrier lesson: the production emitter is the carve-out being tested; the EXISTING rows must be planted directly, mirroring the 18-B.1 raw-insert technique).**
1. `test_resolve_clears_declared_unresolved_orphan` — plant an `unresolved` `untracked_broker_position` row for `SPCX` (raw insert); call `resolve_out_of_framework_orphans(conn, out_of_framework_tickers=("SPCX",))`; assert the row's `resolution == 'acknowledged_immaterial'`, `resolution_reason` mentions out-of-framework + SPCX, `resolved_by` + `resolved_at` set; return value == 1.
   - Pre-fix: function does not exist (ImportError / AttributeError). Post-fix: row cleared. **Distinguishes.**
2. `test_resolve_clears_pending_ambiguity_orphan_and_clears_ambiguity_kind` (**the live-ID-68 path**) — plant a `pending_ambiguity_resolution` orphan with a non-NULL `ambiguity_kind` (raw insert, satisfying the 0031 cross-column CHECK on insert); resolve → `resolution == 'acknowledged_immaterial'` AND `ambiguity_kind IS NULL` (the cross-column CHECK would reject the transition otherwise).
   - Pre-fix: function absent. Post-fix: cleared + ambiguity_kind NULL. **Distinguishes** + proves the CHECK-safe transition.
3. `test_resolve_does_not_touch_undeclared_orphan` (**scope / L3**) — plant an `unresolved` orphan for `FOO` (NOT declared) + one for `SPCX` (declared); resolve with `("SPCX",)` → SPCX cleared, FOO STILL `unresolved`; return value == 1.
   - Pre-fix: function absent. Post-fix: SPCX-only cleared. **Distinguishes** the scoping.
4. `test_resolve_is_idempotent` (**C3**) — plant + resolve SPCX once (returns 1); call AGAIN → returns 0, no further state change, no spurious second resolve.
   - Pre-fix: function absent. Post-fix: second call no-op. **Distinguishes** idempotency.
5. `test_resolve_empty_declared_set_noop` — `resolve_out_of_framework_orphans(conn, out_of_framework_tickers=())` → returns 0, touches nothing (even if unrelated orphans exist).
   - Distinguishes the empty-set short-circuit (and proves it does not accidentally resolve undeclared rows).

**Acceptance.** Declared-ticker existing orphans (both `unresolved` and `pending_ambiguity_resolution`) clear to `acknowledged_immaterial` with an audited reason; undeclared orphans untouched; idempotent; empty-set no-op; the run's `unresolved_discrepancies_count` decrements via `resolve_discrepancy`'s existing decrement. `ruff check swing/` clean.

---

### Task 4 — OPTIONAL: thin CLI to add/remove/list declared tickers (clearly-marked optional polish)

> **OPTIONAL (C5 / CHARC: "a thin CLI to add/remove is optional polish, not required").** Include ONLY if executing-phase budget allows after Tasks 1-3 are green. The operator can edit `user-config.toml` `[reconciliation] out_of_framework_tickers` by hand absent this. If cut, note it in the executing return report as a deferred V1 simplification. The Task-3 resolve invocation surface (a `swing schwab resolve-out-of-framework` command) is NOT optional if Task 3's chosen surface is the CLI — keep the resolve command even if the add/remove polish is cut.

**Purpose.** `swing config out-of-framework add/remove/list <ticker>` — read/modify the `user-config.toml` `[reconciliation] out_of_framework_tickers` list.

**Files.** `swing/cli_config.py` — a new `out-of-framework` sub-group under `config_group`, using `load_user_overrides` / `write_user_overrides` / `_write_override_nested` (the existing helpers). `add` uppercases + dedupes into the list; `remove` drops; `list` prints the effective set (via `apply_overrides`). ASCII-only output (Windows cp1252 gotcha).

**TDD — failing tests first (monkeypatch BOTH `USERPROFILE` AND `HOME`).**
1. `test_cli_add_out_of_framework_ticker` — `add spcx` → user-config `[reconciliation] out_of_framework_tickers == ["SPCX"]`; re-add `SPCX` → still `["SPCX"]` (dedupe).
2. `test_cli_remove_out_of_framework_ticker` — seed `["SPCX","FOO"]`, `remove SPCX` → `["FOO"]`.
3. `test_cli_list_out_of_framework` — seeded set printed; ASCII-only.

**Acceptance.** Add/remove/list manage the user-config list; dedupe + uppercase; ASCII output. `ruff check swing/` clean.

---

## 3. The §6 discriminating tests, mapped to tasks

| §6 mandate | Test(s) | Task |
|---|---|---|
| (a) declared ticker held → ZERO `untracked_broker_position` across runs | `test_declared_ticker_emits_no_untracked_orphan`; `test_step_schwab_orders_threads_declared_set` | 2 |
| (b) UNDECLARED untracked position STILL banners (the L3 discriminator — NOT a blanket) | `test_undeclared_untracked_position_still_banners`; `test_resolve_does_not_touch_undeclared_orphan` | 2, 3 |
| (c) carve-out surfaced in the recon summary/warnings (not silent) | `test_carveout_surfaces_in_summary_warnings` | 2 |
| (d) §2.4 coherence refinement | **DEFERRED (C4) → NOT tested.** Noted here so the executing implementer does NOT add a §2.4 test. Minimal B keeps the both-flat `equity_delta` gate suppressed while holding (broker non-flat) — no false delta; the existing gate is unchanged, so no new test is needed for it. | — |
| (e) declared holdings never appear in `compute_stats` / cohort / hypothesis surfaces (the L1 structural assertion) | `test_declared_holding_never_in_trades_or_stats` (below) | L1 (Task 2 structural property) |

**L1 structural assertion test (`test_declared_holding_never_in_trades_or_stats`).** Run `run_schwab_reconciliation` with a declared held SPCX position + empty journal → assert (1) ZERO rows in `trades` for SPCX (the carve-out never journals — by construction), and (2) `compute_stats(trades=list_open_trades(conn)+closed, ...)` (or simply over the empty trades table) returns `n_trades == 0` and contains no SPCX. This is a BY-CONSTRUCTION assertion: path B never creates a `trades`/`fills` row, so SPCX is structurally absent from every strategy surface. Pre-fix vs post-fix: this test passes BEFORE and AFTER (no trades row either way) — it is a **structural-property LOCK**, not a distinguishing test; its value is guarding that NO future task accidentally journals a declared holding. State this explicitly in the test docstring (per the recipe's distinguishing-test discipline — it is intentionally a lock, not a behavior-distinguisher).

---

## 4. C1-C5 + L1-L4 traceability table (RD is MERGE-BLOCKING on L1-L4 at executing return)

| Condition / Lock | Source | Implemented by (task) | Verified by (test / gate) |
|---|---|---|---|
| **C1 / L1** — declared holdings NEVER create a `trades`/`fills` row (by construction) | CHARC C1; RD L1 | Task 2 (carve-out skips the orphan emit; never journals — there is NO code path in this arc that writes a `trades`/`fills` row for a declared ticker) | `test_declared_holding_never_in_trades_or_stats` (structural LOCK); `compute_stats` grounding (sweeps `trades` table only); operator live gate |
| **C2 / L3** — UNDECLARED untracked position STILL banners; carve-out surfaced (#27); never blanket | CHARC C2; RD L3 | Task 2 (declared-set membership test + `cash_warnings` exclusion line + summary counter) | `test_undeclared_untracked_position_still_banners`; `test_carveout_surfaces_in_summary_warnings`; `test_default_empty_out_of_framework_preserves_orphan`; operator live gate (a genuinely-new undeclared position still fires) |
| **C3** — existing declared-ticker orphans resolved scoped + audited + idempotent | CHARC C3 (Ruling 3) | Task 3 (`resolve_out_of_framework_orphans` — scoped `IN` filter, audited `resolution_reason`, idempotent via the resolution filter, atomic via `resolve_discrepancy`) | `test_resolve_clears_declared_unresolved_orphan`; `test_resolve_clears_pending_ambiguity_orphan_and_clears_ambiguity_kind`; `test_resolve_does_not_touch_undeclared_orphan`; `test_resolve_is_idempotent`; operator live gate (banner clears) |
| **C4 / L2** — §2.4 DEFERRED; minimal B only; no false `equity_delta` | CHARC C4 (Ruling 2); RD L2 | NO §2.4 code (the plan explicitly excludes the swing-NLV redefinition); minimal B leaves the both-flat gate untouched | The equity_delta gate (`schwab_reconciliation.py:1714-1722`) is NOT edited — confirmed by the executing diff carrying no change to step 8; no §2.4 test (mandate (d) deferred) |
| **C5** — config-registry; NO new schema; NO new module/standing-process | CHARC C5 (Ruling 1) | Task 1 (config list in `swing/config.py` + `config_overrides.py` — no migration); carve-out in the existing `schwab_reconciliation.py`; optional CLI in the existing `cli_config.py` | NO file under `swing/data/migrations/` added (the executing diff carries zero migrations); `schema_version` unchanged; no new package/daemon |
| **L4** — measurement chain untouched | RD L4 | NO edits to temporal log / candidates / shadow / detectors / `validate_bars` / finiteness predicates / research-health monitor | The executing diff touches ONLY `swing/config.py`, `swing/config_overrides.py`, `swing/trades/schwab_reconciliation.py`, `swing/integrations/schwab/pipeline_steps.py`, optionally `swing/cli_config.py` — confirmed by file-scope review |

---

## 5. Verification gates

**Automated (before review — fix-to-green first per recipe §2):**
- The discriminating tests above (Tasks 1-3, optionally 4) + the L1 structural lock.
- The FULL fast suite green BEFORE the Codex review: `python -m pytest -m "not slow" -q` (run from the worktree; cwd-based discovery tests the worktree code). Cross-cutting / global-invariant tests (config-section manifests, any `Config`-shape consistency tests) are exercised only by a full run — run it before review so the review converges on a green diff.
- `ruff check swing/` clean.

**Operator live gate (BINDING — mirrors the 18-H.6 live-witness discipline):** on the live DB, after declaring SPCX out-of-framework (`user-config.toml` or the optional CLI):
1. `swing schwab resolve-out-of-framework` (Task 3) → the existing SPCX orphan rows clear to `acknowledged_immaterial`; the banner count drops; the recon banner no longer shows SPCX.
2. A real reconciliation run (`_step_schwab_orders`, production env) → emits NO new SPCX orphan; the `cash_warnings` / summary shows the `out_of_framework_excluded` exclusion line for SPCX.
3. A genuinely-new UNDECLARED untracked broker position WOULD still fire an orphan (the L3 discriminator — verified by confirming an undeclared symbol still banners, or by reasoning from the scoped-set test if no second position is live).

**Executing-phase review (BINDING):** `review-strong` with repo-access (the carve-out's correctness depends on the surrounding orphan-pass + caller reference graph — the recipe's PRODUCTION-CODE repo-access note), run to `NO_NEW_CRITICAL_MAJOR`; `codex-auto-review` (repo-access, matched-high effort) alongside as the complementary second eye. The executing dispatch touches `swing/trades` (the authorized C5 carve-out); the read-only `swing/trades` default returns after the arc.

**RD merge-blocking sign-off** at the executing return, verified against the shipped diff for L1-L4 (the traceability table §4 is the QA checklist).

---

## 6. Explicitly OUT of scope (echoes brief §7)

- **Path A** (track-but-exclude / total-account mirror) — not chosen.
- **Any change to strategy-stat computation surfaces** (`compute_stats`, `swing/metrics/cohort.py`, hypothesis-progress, process-grade) — B needs NONE; L1 holds by construction (no trades row).
- **Any measurement-chain / shadow-engine / monitor change** (temporal log, candidates, shadow expectancy, detectors, `validate_bars`, finiteness predicates, research-health) — L4.
- **§2.4 swing-NLV coherence refinement** — DEFERRED (C4 / Ruling 2); a registered fast-follow if the operator wants the swing-flat coherence check restored while holding declared positions. NOT in this plan; the both-flat `equity_delta` gate is NOT edited.
- **A general cross-run suppression belt for UNDECLARED `untracked_broker_position` orphans** — out of scope; only the declared-registry carve-out. If CHARC wants one for undeclared orphans, it is a separate arc.
- **A schema table for the registry** — AVOIDED (Ruling 1: config list, no migration).

---

## 7. Recommended EXECUTING dispatch

- **Cell:** `implementer-opus-high` (or the orchestrator's standard production-code cell). Rationale: a `swing/trades` carve-out + config plumbing + a reconciliation-resolve interaction with a cross-column CHECK — moderate blast radius, several discriminating tests with subtle pre/post arithmetic, and the cross-arc raw-insert seeding discipline. Worth a strong implementer.
- **Review tier:** `review-strong` (binding) + `codex-auto-review` (complementary), both repo-access. NEVER tier down — this is production code at the reconciliation boundary.
- **Base:** `main` at dispatch time (the orchestrator rebases this plan branch before merge).
