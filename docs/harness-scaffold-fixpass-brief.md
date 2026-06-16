# Harness-scaffold pre-accept fix-pass + state-pointer convention — CHARC dispatch brief

**Author:** CHARC. **Date:** 2026-06-16. **Target repo:** `C:/Users/rwsmy/harness-template`, branch `scaffold-build` (continue from HEAD `dbac3b2`). **CROSS-REPO:** all work lands in harness-template; this brief is tracked in swing.

**Context.** The generic harness scaffold build RETURNED + orchestrator-QA'd. The binding **review-strong** chain CONVERGED (1 CRITICAL session_id traversal + 4 MAJOR all fixed; CHARC-verified the CRITICAL closed on disk). The separate **codex-auto-review** (repo-access, matched-HIGH) surfaced **0C / 4M / 2m**; CHARC has adjudicated each (grounded on disk at `dbac3b2`). This brief bundles the APPROVED fixes + the operator-directed director **state-pointer convention** into ONE pre-accept fix-pass, then re-gates to accept. Rationale for fixing before accept: this is the TEMPLATE every future harness inherits, and the headline defect (MAJOR-2) sits in the registry — the scaffold's flagship per-generation-addressing feature. One fix in the template vs one fix per clone.

---

## A. IN this pass

| # | Item | Disposition | Site |
|---|---|---|---|
| A1 | **MAJOR-2** non-atomic registry write | **FIX (required)** | `session_start.py:133`, `:186` |
| A2 | **MAJOR-4** vestigial substrate-exception constant | **FIX (CHARC ruling §C2)** | `genericity_lists.py:111` |
| A3 | **MAJOR-3** `started_ts` raw-string sort — *robustness half only* | **FIX (low-pri companion)** | `session_start.py:259` |
| A4 | **MINOR-2** hook sibling-import before the exit-0 guard | **VERIFY + harden if confirmed** | `user_prompt_submit.py`, `session_end.py` |
| A5 | **State-pointer convention** | **ADD (operator-directed bundle)** | see §C5 |

## B. CITED as best-effort / V2 — NOT in this pass (record in `.copowers-findings.md` + note against spec §7)

- **B1 — MAJOR-1** multi-recipient crash-atomicity. Verified: delivery is a careful two-phase stage-temps → commit-`os.replace`-with-rollback; all-or-nothing for staging/IO errors. Only a hard process-crash mid-commit leaves partial, and true N-file atomicity is a fundamental FS limitation; spec §7 scopes comms best-effort; single-operator recoverable.
- **B2 — MINOR-1** ack check-then-rename race. Low impact, single-operator.

---

## C. Per-item detail

### C1 — MAJOR-2 (atomic registry write) — REQUIRED
`write_entry` (`:133`) and `touch_last_seen` (`:186`) do truncate-in-place `path.write_text`. A concurrent `newest_live`/`read_entries` reading mid-write hits torn JSON → that entry is silently skipped → bare `--to orchestrator` transiently resolves to an older generation or `None`. The heartbeat rewrites every UserPromptSubmit, so the window recurs. **Fix:** route both writes through the SAME atomic pattern role_mail already uses for delivery — `_write_temp(final, content)` then `os.replace` (role_mail.py:404/415). Confirm `_write_temp` stages the temp in the destination dir (`comms/sessions/`) so `os.replace` is same-filesystem-atomic (our `os.replace` gotcha — same-FS only); if it doesn't, stage there explicitly. **Test:** a distinguishing test that the registry write is atomic (no torn intermediate observable at the target path; reader never returns a partial entry), and that a write failure leaves the prior entry intact.

### C2 — MAJOR-4 (genericity-guard substrate scoping) — CHARC RULING (the durable ratification)
**RATIFIED: the BROAD model the implementer built is correct.** Substrate vocabulary is forbidden in exactly ONE place — the mechanism-agnostic `docs/review-gate-seam.md` (`SUBSTRATE_FORBIDDEN_RELPATHS`) — and permitted everywhere else. Reasoning (the permanent guard-contract record, for future instances + the germinated harness's own CHARC):
1. The scaffold is **substrate-coupled by design** — spec §1 "same substrate"; §10 puts platform-neutral comms explicitly OUT of scope. Windows/WSL/Codex/git/PowerShell appear legitimately across the launcher, README, dispatch-recipe, config, and test machinery.
2. The one load-bearing constraint is the **review/gate seam staying mechanism-agnostic** (decided-choice Q2=b) so a downstream harness with a different reviewer can fill it. The guard enforces exactly that single denied scope.
3. It is **NOT an app/domain-contamination hole** — the FORBIDDEN vocab (swing/trading/finance/tickers/chess/COA) is whole-tree-checked and untouched by this ruling.
4. The tight §8(c) "two named exception files" allowlist reading would cry-wolf on every legitimate substrate mention → the guard gets disabled — the exact anti-pattern `genericity_lists.py` already rejects for the ticker class (its lines 24-28). §8(b) "substrate does NOT fail the build" dominates; §8(c)'s wording was imprecise.

**Disposition:** DELETE `SUBSTRATE_EXCEPTION_RELPATHS` (`genericity_lists.py:111-114`) — it is referenced NOWHERE (confirmed: the guard enforces only `SUBSTRATE_FORBIDDEN_RELPATHS`). Collapse its comment block into a one-line note on `SUBSTRATE_FORBIDDEN_RELPATHS` ("substrate is permitted everywhere except here; there is no exception-allowlist because substrate is not forbidden by default"). No guard-logic change (the constant is already dead); this removes the misleading fossil of the rejected tight model. Guard stays green.

### C3 — MAJOR-3 (robustness companion) — LOW-PRIORITY, same file
The **security hijack is OUT OF SCOPE** (the registry is trusted-local-writer-only; all `started_ts` are uniform `isoformat()` so string-sort == chronological; a crafted value needs `comms/` write access = threat model already lost). The cheap **robustness** half: in `newest_live`, datetime-parse `started_ts` and skip/deprioritize a malformed value, mirroring how `_age_seconds` already handles `last_seen` (`:202`) — closes the internal asymmetry (the registry parses `last_seen` but string-sorts `started_ts`). Include since we are already in the file for C1; **drop to V2 if it adds non-trivial complexity** (it must not balloon the pass).

### C4 — MINOR-2 (hook import-before-exit-0 guard) — VERIFY, then harden if confirmed
**The swing precedent makes this worth the cheap check:** the 2026-06-12 swing incident was exactly this class — a hook failing at the launch/import layer, *before* its in-script exit-0 guard, returned nonzero and **blocked an operator prompt**. **Verify:** do `user_prompt_submit.py` / `session_end.py` do `from session_start import …` (or sibling imports) at module top, outside the `main()` try/except? If a sibling-import failure can escape the exit-0 guard, **harden** it (guard the import path so an import error still exits 0 — a hook must NEVER block a prompt/session). If on inspection the imports cannot fail a launch (e.g. already wrapped, or import is intrinsically safe), record that and take no change. One flag, not a rabbit hole.

### C5 — State-pointer convention (operator-directed bundle)
Bake the director current-state-pointer convention into the scaffold NOW — before any session log accretes — so a germinated harness never develops the duplicate-buried-snapshot problem (the swing cold-start defect this convention fixes). The scaffold charter (`charc-charter.md`) currently has NO session log, which makes this a clean ADD (no retrofit):
1. **ADD `docs/charc-state.md`** — the single current-state pointer for the scaffold's one director (CHARC), shipped as a TEMPLATE/placeholder (a clean scaffold has no live state): the convention header (overwrite-each-session; the charter's session log, once it exists, is append-only history; bootstrap reads this first) + a "on a bare clone there is no prior state — proceed to the charter" note + a skeleton (phase/state, live workstreams, pending items, behavioral pointers). NO app/domain vocab.
2. **REWORK `docs/charc-bootstrap.md` step 1** — read `docs/charc-state.md` FIRST (on a bare clone it is the placeholder pointing onward), THEN read `charc-charter.md` in full. Preserve the staged-guarantee framing.
3. **DOCUMENT the convention in `charc-charter.md`** — a short subsection (fold under §5 Custodian-of-FORM or §7 The-bootstrap, implementer's call): current state lives ONLY in `charc-state.md` (overwritten each session); a session log, when it emerges, is append-only history and carries NO "current/read-me-first" block; the bootstrap reads the state file first. Mark it CHARC-authored harness-architecture.
4. **§8 peer-director-add checklist** — add one line: a new peer director ships its own `<role>-state.md` pointer + its bootstrap reads it first.
5. **Manifest + guard:** update the §2.1 manifest accounting (shipped files 18 → 19 for `charc-state.md`); genericity guard stays GREEN over the whole tree; add/extend the manifest test for the new file.

---

## D. Re-gate + accept path
1. **review-strong** (gpt-5.5/high, repo-access — the binding gate) to convergence (zero new critical/major).
2. **codex-auto-review** (repo-access, matched-HIGH — the now-adopted gating-complementary second eye; this IS a production-code arc) — resolve-or-cite each new finding.
3. **CHARC build-vs-plan/spec verify** (every fix on disk; the C5 convention present + the bootstrap reads-state-first; genericity guard green over the whole tree; §2.1 manifest accounting at 19; the CRITICAL session_id validation still intact).
4. **Operator bootstrap-dry-run witness** on a bare clone (the §5.5 staged guarantee — now including: charc-state.md read first, the placeholder makes sense on a bare clone).
5. **Accept** (merge scaffold-build → master in harness-template; operator cadence on push).

## E. Locks / fences
- **Cross-repo:** work in `harness-template` `scaffold-build` ONLY; read swing for reference; do NOT git-init, do NOT touch swing.
- **No app/domain contamination:** the genericity guard is the binding gate — green over the whole tracked tree (incl. the new `charc-state.md`).
- **Do NOT regress the R1 CRITICAL fix:** `is_valid_session_id` must still gate every path-build + reject invalid registry entries in `read_entries`/`newest_live`.
- **Trailers:** conventional commits, **ZERO `Co-Authored-By`**, no `--no-verify`.
- **Return:** the implementer reports to the ORCHESTRATOR in chat; the ORCHESTRATOR posts the return to CHARC AFTER its QA (never the implementer to a director inbox).

---

## F. AR follow-up — post-QA codex-auto-review ruling (CHARC, 2026-06-16; build verified PASS at `7a237b0`)

The fix-pass orchestrator-QA passed; CHARC build-vs-plan/spec verify PASSED on disk (A1–A5 + 166 green + R1 traversal boundary intact + manifest 19 + `SUBSTRATE_EXCEPTION_RELPATHS` deleted). The gating codex-auto-review surfaced 2 new MAJORs (trusted-local-writer class); CHARC ruling (operator-concurred):

- **AR-MAJOR-1 (read_entries doesn't enforce embedded `session_id == path.stem`) → FOLD.** A crafted/corrupt `comms/sessions/<a>.json` with embedded id `<b>` (both valid) lets `newest_live` mis-route bare `--to orchestrator` to `comms/orchestrator/<b>/inbox`. NOT a traversal (R1 boundary holds), but a real mis-route of the flagship per-generation addressing. **This is a one-clause extension of `read_entries`' EXISTING embedded-id validation** (it already calls `is_valid_session_id` on the embedded id) that enforces the registry's defining identity invariant — "one file per session, filename IS the session_id" (`session_start.py:16`). Same category as A3 (a read-side robustness completion of existing posture), NOT the #39 defensive-hardening treadmill. **Change:** in `read_entries`, extend the skip-condition with `and data.get("session_id") == path.stem` (scope = `read_entries` only — the LIST/resolution path that feeds `newest_live`; `read_entry` stays as-is). **Test:** a planted `<a>.json` with embedded `<b>` is SKIPPED (pre-fix returned; post-fix skipped — distinguishing); a matching `<a>.json`/`<a>` is returned (unaffected). Update the `read_entries` comment to name the filename==session_id invariant.
- **AR-MAJOR-2 (read_entry/touch preserve a malformed embedded id) → CITE V2.** Safe as-is: both build the path from the validated ARG (`_entry_path(arg sid)`), never the embedded field, so no mis-route; and the AR-MAJOR-1 fold makes `read_entries` skip such a file anyway. Recorded in `.copowers-findings.md`.
- **Carried V2 (unchanged):** B1 multi-recipient crash-atomicity, B2 ack check-then-rename race.

**Consistency note (the discrimination rule):** across both fix-pass passes CHARC FOLDS the cheap robustness-completions of an existing posture (A3 `started_ts`, AR-MAJOR-1 `sid==stem`) and CITES the fundamental FS limits + safe-degrades (multi-recipient atomicity, ack race, AR-MAJOR-2). **Cell:** `implementer-sonnet-high` (1 line + 1 test; orchestrator may keep the fix-pass's opus-high cell for continuity). **Re-gate:** review-strong (repo-access, binding) re-converge + codex-auto-review → orchestrator QA → CHARC re-verify (the `== path.stem` clause + the distinguishing test + still 167-ish green + guard green) → operator bootstrap-dry-run → accept.
