# G6 Arc C — Codex adversarial review transcript + adjudication

> Orchestrator-persisted copy of the executing implementer's `.copowers-findings.md`
> (the worktree `C:\Users\rwsmy\harness-template\.worktrees\g6-arc-c` was swept after merge;
> this is the verbatim convergence record read at QA). HEAD merged to harness-template
> `master` @ `c1a1522`.

Repo: harness-template (worktree `.worktrees/g6-arc-c`, base `master`).
Review tier: `review-strong` (profile present in $CODEX_HOME) + a complementary
`codex exec` second eye at `model_reasoning_effort=high`. Diff fed via stdin with
the `.claude/hooks/user_prompt_submit.py` reference graph appended (the import
contract stop.py reuses) so the review is not diff-blind.

## Round 1 — review-strong

- **CRITICAL** `.claude/hooks/stop.py::_stop_hook_active` / `_parse_stop_payload`:
  a payload that is valid JSON but lacks `stop_hook_active` is treated as `False`,
  so `handle_stop()` blocks when unread mail exists. If Claude Code ever omits or
  renames that field, every continuation payload will also lack it, and a stuck
  unread inbox can create an unbounded continue loop. For loop safety, absence of
  the guard flag should default to allow-stop (`True`).
- **MINOR** `tests/test_comms_ui.py`: the new UI tests are mostly substring checks.

Verdict: BLOCKING_CRITICAL_FOUND.

Adjudication:
- **CRITICAL — ACCEPTED + FIXED.** Changing the `_stop_hook_active` default from
  False to True is strictly safer and has ZERO impact on the documented Claude Code
  contract (the field is ALWAYS present and `false` on a genuine first stop). A
  DELIBERATE DEVIATION from the converged plan's letter, in the plan's own
  loop-safety spirit; flagged in the return report. Added `test_key_absent_allows_stop`.
- **MINOR — ADJUDICATED OUT (browser-witness-bound).** Browser-only HTMX/JS surface;
  the operator BROWSER witness is the binding gate (visual-gate-both-render-and-browser).

## Round 2 — review-strong

- **MAJOR** `.claude/hooks/stop.py`: any falsey `stop_hook_active` (`null`/`0`/`""`/`[]`)
  blocks. Only exact JSON `false` should block.
- **MINOR** substring UI tests (repeat).
- **MINOR** `data-key` keyed by `m.filename` page-global.

Verdict: BLOCKED_ON_MAJOR_LOOP_SAFETY_DEFECT.

Adjudication:
- **MAJOR — ACCEPTED + FIXED.** `payload.get("stop_hook_active", True) is not False`
  — block-once only on an EXACT boolean `False`; identity not truthiness. Added
  `test_non_boolean_falsey_values_allow_stop` over (None, 0, "", []).
- **MINOR (UI substring) — OUT (browser-witness-bound).**
- **MINOR (data-key filename) — OUT (out-of-scope per plan 5.2; pre-existing; the
  flat data-key attributes pre-date Arc C; role_mail filenames are unique across
  disjoint mailboxes -> cross-pane collision practically impossible + benign).**

## Round 3 — review-strong (CONVERGED)

- MINOR substring UI tests (repeat); MINOR empty-stdin/read-failure not locked by a test.

Verdict: NO_NEW_CRITICAL_MAJOR.

Adjudication: CONVERGED (zero new critical/major). MINOR (UI) OUT (repeat). MINOR
(empty stdin) PARTIALLY ADDRESSED — added
`test_empty_and_unreadable_stdin_default_to_allow_stop`; the full main() stdin-read
path is covered by the test_hooks_wiring subprocess exit-0 gates (HOOKS now includes stop.py).

## codex-auto-review (complementary second eye, model_reasoning_effort=high)

Run AFTER review-strong converged (R3), over the same final diff bundle + reference
graph. DISJOINT finding (the 18-H.4 complementary-eye pattern):

- **MAJOR** `.claude/hooks/stop.py`: `_parse_stop_payload` masks UTF-8 decode failures
  with `errors="replace"`, so a garbled payload (`b'...\xff'`) can become valid JSON with
  `stop_hook_active: False` and block. Use strict `raw.decode("utf-8-sig")` and let
  `UnicodeDecodeError` hit the allow-stop path.
- **MINOR** the "unreadable stdin" test does not cover invalid UTF-8.

Verdict: NEW_MAJOR_FOUND.

Adjudication:
- **MAJOR — ACCEPTED + FIXED.** Removed `errors="replace"`; strict `raw.decode("utf-8-sig")`
  -> `UnicodeDecodeError` falls to the allow-stop sentinel `{"stop_hook_active": True}`.
  Genuinely complementary (review-strong's diff-only convergence missed it).
- **MINOR — FIXED.** Added `test_invalid_utf8_payload_allows_stop`.

codex-auto-review re-run (post-fix) — CONVERGED:
- MINOR data-key filename (repeat) -> OUT. MINOR settings comment "three commands" after
  the 4th hook -> **FIXED** ("four commands"). MINOR theme tests string-presence -> OUT
  (browser-witness-bound). NO_NEW_CRITICAL_MAJOR.

## Round 4 — review-strong (post auto-review fixes)

- **MAJOR** `.claude/hooks/stop.py`: the import-failure path is OUTSIDE the broad `try` —
  a broken/closed `stderr` on the degraded-import path can exit nonzero, violating the
  always-exit-0 contract. Put the `_IMPORT_OK` branch inside the outer `try`.
- **MINOR** substring UI tests (repeat).

Adjudication:
- **MAJOR — ACCEPTED + FIXED.** Moved the entire main() body (incl. the degraded-import
  warning) inside the outer `try/except: return 0`. Added
  `test_import_failure_path_exits_zero_even_if_stderr_raises`.
- **MINOR — OUT (repeat).**

## Round 5 — review-strong (CONVERGED, clean)

Findings: none. The Stop hook is fail-open on empty/garbled/invalid-UTF-8/missing/
non-boolean `stop_hook_active`; blocks only on exact boolean `false` + gated role + unread
mail; the continuation (`true`) allows stop; broad handling keeps exit 0; the sibling import
contract matches `user_prompt_submit.py`; `unread_notice("charc", root, None)` is correct for
the singular inbox. Theme + details-preserve JS structurally correct.

Verdict: NO_NEW_CRITICAL_MAJOR.

## codex-auto-review final re-run (final tree) — CONVERGED

NO_NEW_CRITICAL_MAJOR. Two MINORs adjudicated out: UI substring tests (browser-witness-bound);
`test_stop_hook.py::_load_stop()` mutates sys.path/sys.modules without cleanup — follows the
EXISTING scaffold convention (`_load_comms_ui` does the identical insert), non-breaking, suite green.

## CONVERGENCE SUMMARY

BOTH eyes converge on the FINAL tree (HEAD c1a1522):
- review-strong: NO_NEW_CRITICAL_MAJOR (R5, clean).
- codex-auto-review: NO_NEW_CRITICAL_MAJOR (final re-run).
Resolved across the chain: 1 CRITICAL (R1 absent-key->block) + 3 MAJOR (R2
non-boolean-falsey->block; auto-review errors=replace salvage; R4 import-failure
stderr exit-nonzero). All fixes are Stop-hook fail-open / always-exit-0 hardening.
