# schwabdev v2.5.1 -> v3.0.5 Upgrade -- Brainstorming Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the schwabdev-v3-upgrade brainstorming implementer. No prior conversation context.

**Mission:** Produce a brainstorming design spec for migrating the project off **schwabdev 2.5.1** to **3.0.5** (latest). This is an **operator-inserted prerequisite arc** sequenced FIRST in the Phase 14 close-out tail (before SB5.5), chosen deliberately for v3's better data-handling + the optional Fernet token encryption. **A deep scoping investigation already exists -- BUILD ON IT, do not re-investigate from scratch:** `docs/schwabdev-v3-upgrade-investigation-findings.md` (committed `9d4f6a4`; orchestrator-verified). Your job is to turn that findings doc into a migration DESIGN SPEC: the migration strategy, the token-storage rewrite, the breaking-change fixes, the test strategy, the operator re-setup UX, the L2-LOCK re-anchor, and the design OQs.

**Brief:** `docs/schwabdev-v3-upgrade-brainstorming-dispatch-brief.md` (this file).

**Context:** Phase 14 SB1-SB5 SHIPPED; main HEAD at this dispatch: see the dispatch metadata §9 (branch from it). This upgrade obviates the planned **P14.N7** (v3 removed the daemon `checker` thread by construction -- sync per-request refresh) -> SB5.5 will re-scope to A-3-centric after this lands. NOT a new-Schwab-feature arc; a dependency migration on the L2-LOCKED Schwab surface.

**Cumulative discipline at dispatch:** 37+ CLAUDE.md gotchas BINDING (the entire **Schwab / schwabdev block** is the migration checklist) + the process disciplines in `docs/orchestrator-context.md`; **~700+ cumulative ZERO Co-Authored-By**; **NO swing-DB schema change expected** (schwabdev's tokens DB is its OWN SQLite, separate from `swing.db`; `EXPECTED_SCHEMA_VERSION` stays 23 -- confirm at brainstorm); **the L2 LOCK is re-anchored by this arc** (the first baseline move -- requires explicit operator sign-off; see L2 below).

**Expected duration:** ~3-5 hours brainstorming + a Codex chain run to convergence. Spec line target **~500-800 lines**.

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- **Codex chain count: SINGLE chain** at end. **Run to CONVERGENCE** (zero new criticals AND zero new majors; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- copowers v2.0.3 + WSL Codex CLI fallback (reads the repo FROM DISK):** the MCP `codex`/`codex-reply` tools are PERMANENTLY DEAD in the VS Code extension. **Do NOT attempt them.** The `adversarial-critic` skill auto-routes to the WSL fallback and (v2.0.3) writes the **full prompt+response transcript** per round to `.copowers-findings.md` (`## Round N` / `### Prompt sent to Codex` / `### Codex response` incl. `### Verdict`). If driving directly: `wsl bash -ilc` (INTERACTIVE login) OR prefix `export PATH="$HOME/.local/node22/bin:$PATH"`, and **VERIFY `command -v codex` -> `/home/<wsluser>/.local/node22/bin/codex`** (NOT a `/mnt/c/.../npm/codex` shim -> dies `node: not found`) BEFORE the chain. Pre-generate the diff on Windows; tell Codex NOT to run git. Memory `feedback_wsl_native_codex_invocation` + `feedback_copowers_codex_mcp_windows_launcher` + `feedback_implementer_persist_codex_responses`.
- Output: design spec at `docs/superpowers/specs/<YYYY-MM-DD>-schwabdev-v3-upgrade-design.md`.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/schwabdev-v3-upgrade-investigation-findings.md`** (committed `9d4f6a4`) -- THE PRIMARY INPUT. The breaking-change-vs-our-usage matrix, the checker verdict, the L2 analysis, and the effort estimate are already done + orchestrator-verified. Treat its findings as the substrate; your spec DESIGNS the migration on top of it. **Re-verify any file:line it cites that you depend on (per discipline #2).**

3. **CLAUDE.md -- the entire "Schwab / schwabdev" gotcha block** = the migration regression checklist. Every gotcha there is a coupling point that MUST still hold post-upgrade. Especially: the `"Schwabdev"` (capital-S) logger-name redaction `setLogRecordFactory`; `update_tokens()` does-not-raise-on-failure (verify post-call state); the `price_history` minute-default footgun; the typed-`SchwabApiError` audit-row close discipline; the sandbox short-circuit (`environment=='production'`-gated domain rows); the Schwab CLI subcommand pipeline-running refusal; the source-artifact reference shape. AND `docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines" (esp. #2 signature/anchor re-grep, #15 production-path tests, #11 atomic-consistency if any constant/enum changes).

4. **Production surfaces to read (the migration touch-set; the findings doc has file:line -- re-grep at writing-plans):** the schwabdev import + `Client(...)` construction sites (`swing/integrations/schwab/auth.py` -- multiple `tokens_file=` sites incl. `_write_schwabdev_tokens_file:1335`, `:762`, `:901`, `:1684`; the `account_linked()` calls at `trader.py:270` + `auth.py:653`); the tokens-file JSON parsing in `swing/cli_schwab.py` (`_read_tokens_metadata:469-490` `json.load`, the `status` command `:606-725`); the schwabdev signature-pin tests (`tests/.../test_*signature*`/`test_account_linked_no_kwargs_required`); the L2-lock test `tests/integration/test_l2_lock_source_grep.py` (baseline `bf7e071`, pattern `schwabdev.Client.`); the redaction factory + its sentinel-leak audit test; `pyproject.toml:20` (the pin).

5. **`docs/superpowers/specs/2026-05-13-schwab-api-design.md`** + `2026-05-13-schwab-api-integration-plan.md` -- the original Schwab integration design (REFERENCE for the auth/token architecture + the audit + redaction layers the migration must preserve).

6. **Memory:** `feedback_copowers_codex_mcp_windows_launcher` + `feedback_wsl_native_codex_invocation` (v2.0.3 transport + `command -v codex` verify), `feedback_implementer_persist_codex_responses`, `feedback_codex_round_limit_suspended`, `feedback_commit_message_trailer_parse_hazard`, `feedback_visual_gate_both_render_and_browser` (here the binding gate is an operator LIVE-OAuth re-setup smoke, not a browser).

---

## §1 Pre-locked decisions + LOCKs (BINDING)

- **L1** Scope = **the schwabdev 2.5.1 -> 3.0.5 migration ONLY** -- re-pin; fix every breaking change the findings doc enumerates (tokens-storage rewrite; `account_linked`->`linked_accounts`; `Client.__init__` signature; public->private token methods); update the signature-pin tests; the L2 re-anchor; the operator re-setup UX; (optionally) Fernet encryption. Do NOT wire A-3, do NOT design SB5.5, do NOT add new Schwab endpoints/features, do NOT touch unrelated surfaces.
- **L2 (RE-ANCHORED BY THIS ARC -- the first baseline move; requires EXPLICIT operator sign-off)** the L2 LOCK = ZERO new Schwab API *endpoints* beyond the existing set. This migration changes HOW we call the existing endpoints (renames, kwarg/storage changes), not WHICH -- so the lock's SPIRIT is preserved. BUT the source-grep test (`schwabdev.Client.` multiset vs `bf7e071`) will trip because the migration edits comments/docstrings/type-annotations containing that literal. **The spec MUST design the re-anchor: bump `L2_LOCK_BASELINE_SHA` to the post-migration HEAD, with an audited rationale + an explicit operator sign-off step, and a re-assertion that ZERO genuinely-new Schwab endpoints were added (a manual endpoint-set diff, not just the grep).** This is the ONLY sanctioned baseline move; do not treat it casually.
- **L3** **NO swing-DB schema change** (v23 held). schwabdev's tokens DB is its own SQLite (separate file under `~/swing-data/`), NOT our `swing.db` migrations. Confirm `EXPECTED_SCHEMA_VERSION` stays 23 + no `00NN` migration. (The `.gitignore` already covers `schwab-tokens.*.db`.)
- **L4** **Preserve EVERY Schwab gotcha post-upgrade:** the `"Schwabdev"`-logger redaction (verify the logger name is still capital-S in 3.0.5); `update_tokens()` post-call-state verification; the typed-error audit-row close; the sandbox `environment=='production'` domain-row gate; the `price_history` daily-bar discipline; the source-artifact `schwab_api:call/{id}` shape. Each gets a re-validation in the spec's test plan.
- **L5** **EXACT-3.0.5-surface verification REQUIRED** -- the investigation read GitHub `main` (version string `3.0.4`). The spec MUST be grounded in the actual `3.0.5` surface: stand up a throwaway venv (`pip install schwabdev==3.0.5`) and read the installed source to CONFIRM the constructor signature, the `tokens_db=`/`encryption=` kwargs, the `linked_accounts` rename, the logger name, and the absence of the daemon checker. Cite the installed-3.0.5 file:line, not GitHub main.
- **L6** **P14.N7 is OBVIATED by this upgrade** (v3's sync per-request refresh removes the daemon checker). The spec NOTES that SB5.5's P14.N7 half drops post-migration; if any thin "last-successful-refresh" liveness surface is still wanted, that is an SB5.5 re-scope decision, NOT this arc.
- **L7** **The binding gate is an operator LIVE-OAuth re-setup smoke** -- because the tokens-storage rewrite + the one-time re-setup can only be truly validated against a real Schwab OAuth round-trip (`swing schwab logout` -> `setup` on v3 -> `status` -> a `fetch`). Mock tests are necessary but INSUFFICIENT for the auth/token path (gotcha #15 spirit).

---

## §2 Spec scope to design

### §2.1 Migration strategy
- The re-pin (`pyproject.toml:20`): exact (`==3.0.5`) vs floored range (OQ-3). The install/uninstall sequence; the dev-dependency implications.
- The tokens-storage rewrite: every `tokens_file=` site -> `tokens_db=`; the `_read_tokens_metadata` JSON-parse in `cli_schwab.py` -> read schwabdev's v3 tokens SQLite (what shape does v3 expose? confirm at L5); `_write_schwabdev_tokens_file` -> the v3 equivalent (or remove if v3 owns the DB lifecycle).
- The `account_linked()` -> `linked_accounts()` rename at both call sites + the stub seam + the signature-pin test.
- The `Client.__init__` signature change at all construction sites.
- The public->private token-method changes (`update_tokens` retained; verify).

### §2.2 The operator re-setup UX (OQ-2)
- v3 cannot read the old 2.x JSON token DBs, so existing operators must re-auth once. Design: force a clean re-`setup` (recommend -- simplest/safest) vs attempt an auto-migration from the old JSON to the v3 SQLite (fragile). Define the operator-facing message + the `swing schwab status` behavior when it detects an old-format/absent token DB.

### §2.3 Fernet token encryption (OQ-1)
- v3 offers optional `encryption=<key>` (Fernet) for the tokens DB -- this retires the "plaintext OAuth at rest (V1)" CLAUDE.md gotcha. Design: include in THIS arc (recommend -- it is the main pull-forward incentive) vs defer. If included: key storage/derivation (where does the Fernet key live? `user-config.toml`? derived?), the key-loss recovery path, and the `.gitignore`/ACL implications.

### §2.4 The L2 re-anchor (L2 above)
- The mechanics: new `L2_LOCK_BASELINE_SHA`; the audited rationale block in the test; the manual endpoint-set diff proving zero new endpoints; the operator sign-off gate.

### §2.5 Test + gate strategy
- Update the signature-pin tests to v3; re-run the redaction sentinel-leak audit; the production-path token-storage tests (real construction, not stubs); the operator LIVE-OAuth re-setup smoke (L7). Enumerate the gate.

---

## §3 Open questions (Codex surfaces; operator triage at writing-plans)
1. **OQ-1 Fernet encryption** -- include in this arc (recommend) vs defer.
2. **OQ-2 tokens-DB migration UX** -- force re-setup (recommend) vs auto-migrate the old JSON.
3. **OQ-3 pin** -- `==3.0.5` vs `>=3.0.5,<4.0.0` (recommend a floored range).
4. **OQ-4 L2 re-anchor** -- the exact rationale + sign-off mechanics (operator-binding).
5. **OQ-5 P14.N7 remnant** -- does any thin checker-liveness surface survive into SB5.5, or does v3's sync refresh drop it entirely? (Feeds the SB5.5 re-scope.)
6. **OQ-6 deploy ordering** -- does the operator re-setup happen at merge time (before `swing web`/pipeline run on v3)? Define the cutover.
7. **OQ-7 Codex chain count** at writing-plans/executing-plans (recommend single).

---

## §4 OUT OF SCOPE (do not design into V1)
- A-3 web market-data wiring + SB5.5 (the NEXT arc, re-scoped after this lands)
- The Phase 14 close-out polish batch (incl. A-6) + B-7 + the close-out review
- Any NEW Schwab endpoint / feature / market-data source (the lock's spirit holds even through the re-anchor)
- A swing-DB schema change / migration (L3; the tokens DB is schwabdev-internal)
- A schwabdev 4.x jump; Phase 15+

---

## §5 Adversarial review (Codex) -- SINGLE chain; run to convergence; watch items
1. **Findings-doc grounding + exact-3.0.5 verification (L5)** -- the spec is grounded in the INSTALLED 3.0.5 surface (throwaway venv), not GitHub main; every breaking-change claim re-confirmed at 3.0.5.
2. **Token-storage rewrite completeness** -- every `tokens_file=` site + the JSON-parse + the writer are migrated; no orphaned 2.x token path.
3. **L2 re-anchor rigor (L2)** -- the spec proves ZERO new ENDPOINTS via a manual endpoint diff (not just the grep), designs the audited re-anchor + the operator sign-off; does NOT silently move the baseline.
4. **Every Schwab gotcha re-validated (L4)** -- redaction logger name; `update_tokens` post-state; sandbox gate; price_history daily discipline; audit-row close; source-artifact shape.
5. **Fernet design soundness (if included)** -- key storage/loss/recovery; no key leakage; ACL/.gitignore.
6. **Operator re-setup UX + cutover ordering** (OQ-2/OQ-6) -- the old-token-DB-detected path is graceful, not a crash.
7. **L3 no swing schema** -- assert v23 held; tokens DB is schwabdev-internal.
8. **The gate is the live-OAuth smoke (L7)** -- mock tests declared insufficient for the auth/token path.
9. **L2 grep continues to function post-re-anchor; ASCII (#16/#32); Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose).

---

## §6 Deliverable shape

**Design spec at `docs/superpowers/specs/<YYYY-MM-DD>-schwabdev-v3-upgrade-design.md`** (mirror the prior brainstorm spec format):
§1 Architecture overview (the migration + what v3 changes) · §2 Pre-locked decisions + L1-L7 · §3 Module touch list (grounded in the findings doc + the 3.0.5 install) · §4 Migration strategy (re-pin + the breaking-change fixes) · §5 Token-storage rewrite + the operator re-setup UX · §6 Fernet encryption design (OQ-1) · §7 The L2 re-anchor design (rationale + sign-off + endpoint diff) · §8 Schema impact (NO swing change) · §9 Sub-bundle decomposition recommendation (slices) · §10 Test strategy + the operator LIVE-OAuth re-setup gate · §11 Schema impact (NO change) · §12 V1 simplifications + V2 candidates · §13 Operator decision items (OQs) · §14 Cumulative discipline compliance (the Schwab gotcha checklist + L2 re-anchor) · §15 Position note (prerequisite arc; obviates P14.N7; SB5.5 re-scope follows).

**Target ~500-800 lines.** Commit stem: `docs(schwabdev-v3-spec): brainstorm <draft|R1|...> -- ...` (final `-m` paragraph plain prose; verify `%(trailers)` is `[]`).

---

## §7 If you get stuck
- If the INSTALLED 3.0.5 surface contradicts the findings doc (e.g., a different constructor signature, the checker NOT actually removed, a different tokens-DB shape), TRUST the install + ESCALATE the discrepancy -- the findings doc read GitHub main (3.0.4), so 3.0.5 is authoritative.
- If the L2 re-anchor seems to hide a genuinely-NEW endpoint, STOP + escalate -- the spirit (no new endpoints) is the real lock; the re-anchor is ONLY for the rename/docstring churn.
- If the migration appears to need a swing-DB schema change, ESCALATE -- the tokens DB is schwabdev-internal (L3).
- HOLD THE LINE: exact-3.0.5 grounding; preserve every Schwab gotcha; the operator re-setup is a one-time cutover; the binding gate is a live-OAuth smoke.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose.
- DO NOT attempt the Codex MCP tools (dead); use the WSL fallback (verify `command -v codex`; v2.0.3 writes the transcript to `.copowers-findings.md`).
- DO NOT widen to A-3/SB5.5 / the close-out batch / Phase 15+.

---

## §8 Return report shape
Mirror the prior brainstorm return reports (15 items): final HEAD + commit breakdown; Codex round chain + convergent shape (**cite `.copowers-findings.md` rounds incl. the final `### Verdict`**); spec line count + per-section; pre-locked decisions verbatim verification (L1-L7); OQs resolved + deferred (esp. Fernet OQ-1 + the L2 re-anchor OQ-4 + the P14.N7-remnant OQ-5 -- flagged for operator); the exact-3.0.5-surface confirmation (what matched/diverged from the findings doc); Codex Major findings accepted (ZERO preferred); V1 simplifications + V2 candidates; forward-binding lessons for writing-plans; sub-bundle decomposition recommendation; schema impact verdict (NO swing change); the L2 re-anchor design summary + the operator-sign-off ask; cumulative gotcha application (the Schwab checklist); worktree teardown status; ZERO Co-Authored-By confirmation; CLAUDE.md status-line refresh draft; writing-plans dispatch-readiness + the SB5.5 re-scope note.

---

## §9 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `schwabdev-v3-upgrade-brainstorming`. Dir `.worktrees/schwabdev-v3-upgrade-brainstorming/`. **Branch from main HEAD = the commit that adds this brief** (the orchestrator will state it in the inline prompt).
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`). For the exact-3.0.5 check use a SEPARATE throwaway venv (do NOT alter the project's installed 2.5.1 environment).
- **Codex chain count:** SINGLE chain at end, run to convergence via the WSL fallback (copowers v2.0.3; verify `command -v codex` first; transcript -> `.copowers-findings.md`).
- **Expected duration:** ~3-5 hours brainstorming + a Codex chain run to convergence.

---

*End of brief. schwabdev v2.5.1 -> 3.0.5 upgrade brainstorming dispatch (operator-inserted prerequisite arc, first in the Phase 14 close-out tail) -- turn the committed investigation findings (`9d4f6a4`) into a migration design spec: re-pin; the tokens-storage rewrite (JSON file -> v3 SQLite, `tokens_file=`->`tokens_db=`) + the operator one-time re-setup UX; `account_linked`->`linked_accounts`; the `Client.__init__` signature; optional Fernet encryption (retires the plaintext-tokens gotcha); and the FIRST-EVER L2-LOCK baseline re-anchor (audited + operator-signed; spirit = zero new endpoints preserved). Ground it in the INSTALLED 3.0.5 surface (throwaway venv), not GitHub main. NO swing schema change (v23 held). v3 obviates P14.N7 (the daemon checker is gone) -> SB5.5 re-scopes to A-3-centric after this lands. The binding gate is an operator LIVE-OAuth re-setup smoke. OUTPUT: a design spec the writing-plans phase can derive a plan from.*
