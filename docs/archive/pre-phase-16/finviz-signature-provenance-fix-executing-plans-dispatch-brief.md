# Finviz Signature-Provenance Fix -- Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the finviz-signature-provenance-fix executing-plans implementer. No prior conversation context.

**Mission:** A small, fully-specified production fix (no brainstorm/writing-plans needed -- the design is decided). The Finviz screen "signature changed since prior run; operator may have edited the saved screen" warning is **miscalibrated**: `compute_signature_hash` hashes `{column_set, first_row}`, but `first_row` (the #1 ticker in the screen RESULT) is volatile -- it changes as the market moves -- so the warning fires on routine top-result drift and wrongly implies an operator edit. **Fix (operator-decided "option 1"): hash ONLY `column_set` (drop `first_row`)** so the warning fires ONLY on a real screen-DEFINITION change (the column set), not on result drift. Execute via `copowers:executing-plans` (TDD: failing test -> see fail -> minimal fix -> see pass -> commit), single Codex chain to convergence.

**Brief:** `docs/finviz-signature-provenance-fix-executing-plans-dispatch-brief.md` (this file).

**Context:** Phase 15 (4 arcs closed: schwabdev-v3 / B-7 / PGT-redesign / pool-widening `#23`). This is a small standalone operational fix surfaced at the pool-widening live gate (2026-06-04). main HEAD at this dispatch: see §6 (branch from it). ~7128 fast tests green; schema v24. **NO schema change, NO migration, NO lock change** (this is internal drift-detection; the Schwab L2 LOCK is untouched -- this is the FINVIZ integration, not Schwab).

**Cumulative discipline:** ASCII (#16/#32) on any new/changed strings; ~700+ ZERO `Co-Authored-By`; `feedback_verify_regression_test_arithmetic` (each test value computed under BOTH the old and new hash basis, asserting they DIFFER in the discriminating direction). Schema v24 UNCHANGED.

**Skill posture:**
- Invoke `copowers:executing-plans` against this brief.
- **SINGLE Codex chain** at end, run to CONVERGENCE (`NO_NEW_CRITICAL_MAJOR`; the ~5-round cap is suspended -- memory `feedback_codex_round_limit_suspended`).
- **Codex transport -- WSL fallback (MCP DEAD).** USE EXACTLY: `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec ...'` (PATH prefix REQUIRED; prove liveness with `codex --version` -> `codex-cli 0.135.0`). Pass the prompt via STDIN (`cat prompt.txt | codex exec -s read-only --skip-git-repo-check -`). Pre-generate the diff on Windows; tell Codex NOT to run git. PERSIST each round's PROMPT AND RESPONSE (incl. `### Verdict`) to `.copowers-findings.md`. Memory `feedback_wsl_native_codex_invocation` + `feedback_implementer_persist_codex_responses`.

---

## §0 Read first
1. **THIS BRIEF.**
2. **`swing/integrations/finviz_api.py:231-276`** -- `compute_signature_hash`. The payload (currently `{"column_set": header_cleaned, "first_row": first_row}` at `:272-275`) + the `first_row` extraction loop (`:261-271`). The docstring (`:232-243`) claims "first-row-Ticker/Sector/Industry change -> different hash" -- that claim is being REMOVED.
3. **The consumer (confirm the hash is drift-detection-ONLY):** `swing/pipeline/runner.py:3986-3992` + `:4047-4053` (`get_latest_signature_hash` -> the "signature changed ... operator may have edited the saved screen" `log.warning`); `swing/data/repos/finviz_api_calls.py:59` (`get_latest_signature_hash`). **GREP the repo for `signature_hash` to confirm NO other consumer depends on the `first_row` component** (it is stored in `finviz_api_calls.signature_hash` + read only by the drift warning).
4. **The tests** -- grep `tests/` for `compute_signature_hash` / `signature_hash` / `first_row` to find every test asserting the OLD behavior (esp. any "first-row change -> different hash" assertion). These re-baseline.
5. **CLAUDE.md** Finviz gotchas + the ASCII discipline. Memory: the WSL Codex transport + persist-responses + round-limit-suspended + trailer-hazard + regression-test-arithmetic.

---

## §1 The fix (BINDING -- decided; do NOT re-design)
- **`compute_signature_hash`:** drop `first_row` from the hashed payload -> `payload = json.dumps({"column_set": header_cleaned}, sort_keys=True).encode("utf-8")`. REMOVE the now-dead `first_row` extraction loop (`:261-271`). Preserve everything else verbatim: the `utf-8-sig` BOM handling, the leading-blank-row skip, the empty-`<empty>` sentinel (`:258-259`), `sorted(...)` on the headers, the `sha256().hexdigest()` return.
- **Docstring:** update to state the signature now reflects ONLY the canonicalized COLUMN SET (the screen-definition fingerprint); a column-set change -> different hash; the screen RESULT (rows / top ticker) does NOT affect it. Remove the `first_row` language.
- **The warning is now ACCURATE -- keep it** (`runner.py:3989/4050` "operator may have edited the saved screen"): it now fires ONLY on a real column-set/definition change. (Optionally tighten the wording to name the column set; not required.)
- **NO other change.** Do NOT touch the Schwab path, the ladder, or the data-integrity concerns (that is a SEPARATE arc). Do NOT change `normalize_to_canonical_csv` (it is a different function; only `compute_signature_hash` changes).

## §1.1 Transitional note (state in the return report; not a defect)
The stored `signature_hash` basis changes (old rows include `first_row`, new rows don't), so the **first post-fix pipeline run will emit ONE "signature changed" warning** as the hash basis shifts, then stabilize. This is expected + benign (a one-time transition). Note it for the operator.

## §2 Tests (TDD)
- **The fix regression (the point):** same `column_set` + DIFFERENT `first_row` (different top-ticker rows) -> **SAME** signature. (Pre-fix: different. Post-fix: same. The discriminating axis is the first_row insensitivity -- compute the asserted hash under both bases per `feedback_verify_regression_test_arithmetic`.)
- **Preserved:** different `column_set` (add/remove/rename a header) -> **DIFFERENT** signature.
- **Preserved edges:** the `<empty>` sentinel (no rows); BOM-prefixed body -> same hash as the un-BOM'd equivalent; leading-blank-row tolerance.
- **Re-baseline:** update every existing test that asserted the OLD `first_row`-sensitivity (now: first_row change -> same hash). Do NOT weaken a column-set assertion. Trust the final pytest count (gotcha #1).

## §3 Adversarial review (Codex) -- SINGLE chain; watch items
1. The payload hashes ONLY `column_set`; `first_row` extraction is fully removed (no dead code); the BOM / blank-row / empty-sentinel handling is byte-preserved.
2. The fix regression (same columns + different top ticker -> same hash) + the preserved column-set sensitivity are both tested + non-tautological.
3. No other consumer depended on the `first_row` component (grep result stated); the drift warning is now accurate.
4. NO schema/migration/lock change; the Schwab L2 LOCK is untouched (FINVIZ integration only). ASCII (#16/#32); Co-Authored-By suppression + trailer-parse hazard (final `-m` paragraph plain prose; `%(trailers)` `[]`).

## §4 If you get stuck
- If a cited line no longer matches the tree, TRUST the tree + re-grep (main is `<this brief's commit>`+).
- If `first_row` looks consumed somewhere beyond the audit-row store + the drift warning, STOP + report (the fix assumes drift-detection-only).
- If the fix seems to need a Schwab/ladder/data change, STOP -- out of scope (separate arc).
- HOLD THE LINE: hash only `column_set`; preserve the BOM/blank/empty handling; the warning stays (now accurate); NO schema/lock.
- DO NOT add `Co-Authored-By`; DO NOT `--no-verify`; final `-m` paragraph plain prose. DO NOT attempt the Codex MCP tools (dead) -- use the WSL prefix + stdin form. Run `python -m pytest -m "not slow" -q` green before the Codex chain; the known xdist co-residency flakes pass in isolation (`-n0`) -- not regressions.

## §5 Deliverable + return report
The merged-ready fix on the branch (suite-green + Codex-converged). Return report: final HEAD + commit breakdown; the fast-suite result (cite it; the new/re-baselined test delta); the Codex round chain + convergent verdict (cite `.copowers-findings.md` incl. the final `### Verdict`); the §1.1 transitional note; the grep confirmation that `first_row` had no other consumer; the schema verdict (NONE -- v24; `git diff --stat` shows zero migration/schema change; Schwab untouched); ZERO Co-Authored-By confirmation; worktree status (left intact for orchestrator QA + merge); merge-readiness.

---

## §6 Dispatch metadata
- **Subagent type:** `general-purpose`. **Foreground.** **Model:** harness default.
- **Worktree:** YES -- branch `finviz-signature-provenance-fix`. Dir `.worktrees/finviz-signature-provenance-fix/`. **Branch from main HEAD = the commit that ADDS this brief** (the orchestrator states the exact SHA in the inline prompt). Use the `superpowers:using-git-worktrees` skill.
- **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`); prefix git/test with `cd <worktree> &&`; re-check `git branch --show-current` before each commit. NO isolated venv; NO live-DB touch.
- **Codex chain count:** SINGLE chain at end, to convergence via the WSL prefix + stdin form.

---

*End of brief. Finviz signature-provenance fix (a small standalone Phase-15 operational fix) -- make `compute_signature_hash` hash ONLY the canonicalized `column_set` (drop the volatile `first_row` = the #1 result ticker) so the "screen signature changed; operator may have edited the saved screen" warning fires ONLY on a real screen-DEFINITION change, not on normal top-result drift. Preserve the BOM/blank/empty handling; re-baseline the first_row-sensitivity tests; one transitional warning on the first post-fix run. NO schema/lock; Schwab untouched. OUTPUT: the merged-ready fix, suite-green + Codex-converged.*
