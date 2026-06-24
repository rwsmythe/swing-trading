# Codex review findings — 18-H.7 research-health RED -> RD push PLAN

Tier: review-fast (profile `review-fast`, model gpt-5.4-mini, reasoning effort low — per the
operator-authored profile). Plan-only writing-plans dispatch. Run to NO_NEW_CRITICAL_MAJOR with an
EMPTY findings list (a non-empty findings list + a trailing NO_NEW_CRITICAL_MAJOR line is NOT
convergence — the findings must be addressed and the review re-run clean).

---

## Round 1

### Codex response (verbatim, `.codex-review-r1.txt` tail)

```
Findings:
1. Major: the plan is internally inconsistent about the `comms_root` seam for the end-to-end test.
   In Task 2, `push_research_health_red_to_rd` is specified to default `comms_root` inline with
   `Path(__file__).resolve().parents[2] / "comms"`, but Task 4 then requires monkeypatching
   `_default_comms_root()` to redirect the helper to a tmp dir. If the helper does not introduce that
   seam up front, the end-to-end test is awkward or impossible to write cleanly, and the plan becomes
   self-contradictory. This needs to be resolved before implementation.

2. Major: the runner wiring test is specified as a source-string assertion on
   `_step_research_health(cfg=cfg, run_id=lease.run_id)` and relative source ordering. That does not
   actually verify runtime ordering, and it is brittle against harmless formatting or refactor
   changes. The plan says it wants to prove read-prior-before-write behavior, but this test only
   checks text, not execution order. A behavioral test around a spy on `_read_prior_overall` and
   `write_research_health_artifact` would be materially stronger and less likely to produce false
   negatives.

NO_NEW_CRITICAL_MAJOR
```

### Adjudication

- **R1 Major 1 (comms_root seam inconsistency) — ACCEPTED, FIXED.** Real plan self-contradiction.
  Task 2 inlined the default `Path(__file__).resolve().parents[2] / "comms"` while Task 4 assumed a
  `_default_comms_root()` monkeypatch seam. Resolution: introduce `_default_comms_root()` as a module
  function in Task 2 up front; the helper resolves `comms_root = comms_root or _default_comms_root()`.
  Task 4 then simply monkeypatches that existing seam. §2.1 and Task 2 updated; Task 4's "add it
  retroactively" paragraph removed.

- **R1 Major 2 (source-string ordering test is not a runtime-ordering proof) — ACCEPTED, FIXED.**
  Valid. The plan already had a behavioral spy test (`test_step_reads_prior_overall_before_
  overwriting`) that proves prior is read before the write OVERWRITES it (the spy sees prior=green
  while the db computes red). I strengthened it to ALSO spy `write_research_health_artifact` and
  assert the prior-read / push / write call ORDER at runtime (a recorded call-sequence list), making
  it the PRIMARY ordering proof. The source-string test is demoted to a thin smoke check that the
  call site threads `run_id=lease.run_id` and stays under `step_guard` between shadow and complete
  (a wiring placement check, NOT the ordering proof) — explicitly labeled as such so it is not
  relied on for runtime ordering.

Both findings addressed by plan edits. Re-running review-fast over the revised plan to confirm a
CLEAN (empty-findings) NO_NEW_CRITICAL_MAJOR.

---

## Round 2

### Codex response (verbatim, `.codex-review-r2.txt` codex section)

```
codex
NO_NEW_CRITICAL_MAJOR
tokens used
20,560
NO_NEW_CRITICAL_MAJOR
```

### Adjudication

CONVERGED. Round 2 returned a CLEAN `NO_NEW_CRITICAL_MAJOR` with NO findings list — both R1 majors
resolved by the plan edits (the `_default_comms_root()` seam introduced in Task 2; the behavioral
runtime-ordering test made the primary ordering proof and the source-string test demoted to a
labeled wiring smoke check). No new critical/major surfaced. Review-fast tier complete for this
plan-only writing-plans dispatch. (The executing dispatch will run review-STRONG to convergence +
codex-auto-review on the shipped production code per recipe §3.)


---

# EXECUTING REVIEW (review-strong, repo-access, production code)

## Round 1 — codex review-strong (-p review-strong resolved; cwd=worktree, -s read-only)

### Codex response (verbatim findings)
MAJOR, swing/monitoring/research_health.py:308 (_read_prior_overall): documented as
never-raising on corrupt prior artifacts, but only catches OSError and ValueError. A
malformed deeply-nested latest.json can make json.loads raise RecursionError, which
escapes before _step_research_health computes or writes the new artifact -> violates
the "read-prior must not skip writer" contract. Fix: wrap the whole prior read in
except Exception: return None (or catch RecursionError/other parse failures as corrupt).

MINOR, swing/monitoring/research_health.py:324 (_compose_red_push): claims ASCII-only,
but interpolates check keys/summaries/details verbatim. ResearchHealthCheck only requires
str; DB-backed fields (tickers) are not ASCII-constrained -> a future/noncanonical value
can produce non-ASCII mail content (not write-boundary-prevented). Fix: apply a local
ASCII sanitizer (backslashreplace) to interpolated subject/body fields.

NEW_CRITICAL_MAJOR=1

### Adjudication
- MAJOR (RecursionError in _read_prior_overall): VALID + ACCEPTED. _read_prior_overall
  runs BEFORE the conn/compute in _step_research_health; if it raises, the whole step
  body (incl. write_research_health_artifact) is skipped via step_guard -> latest.json
  would not refresh on a night the prior is corrupt-nested. RecursionError is a
  RuntimeError subclass, not caught by (OSError, ValueError). Broaden to except Exception
  -> return None. FIXED.
- MINOR (ASCII sanitize the composed message): ACCEPTED. The brief mandates ASCII-only
  message strings; .detail can carry a ticker and tickers are not ASCII-constrained at
  the schema. Apply backslashreplace to the composed subject+body so a non-ASCII detail
  can never produce non-ASCII mail content. FIXED (cheap, aligns with the brief).

## Round 2 — codex review-strong (post-R1-fix re-review)

### Codex response (verbatim verdict)
No new critical or major findings. Verified the R1 fixes are present:
_read_prior_overall now guards the full read/parse/accessor path and degrades to
None; _compose_red_push returns ASCII-sanitized subject/body. The pipeline still
reads prior before compute/write, pushes best-effort, then calls the writer;
role_mail keeps VALID_TO and the sender-agnostic L1 decision_request lock intact.
Static review only.

NO_NEW_CRITICAL_MAJOR

### Adjudication
Converged on review-strong. Proceeding to codex-auto-review (complementary
second-eye, repo-access, matched-high effort).

## codex-auto-review (complementary second-eye; effort=high, repo-access)

NOTE on substitution: the native `codex exec review --commit/--base` cannot
resolve the worktree `.git` (a file pointing at an unreachable Windows path), so
this ran as `codex exec @ -c model_reasoning_effort=high -s read-only` over the
same diff+repo, per recipe ss3.

### Codex response (verbatim)
MAJOR: scripts/role_mail.py:41 / :262 -- Adding `pipeline` to VALID_FROM grants it
every VALID_TYPES value. The L1 gate only rejects decision_request when a recipient
is not operator, so post_message(root, "pipeline", ["operator"], "decision_request",
...) now SUCCEEDS. The RED push only needs status to rd; this widens an automated
emitter into an authority-bearing sender. Fix: add a sender/type guard in
post_message -- allow only `status` for `pipeline` (or reject pipeline+
decision_request). Add a regression test for pipeline->operator decision_request
rejecting, not just pipeline->rd.

Count: 1

### Adjudication
ACCEPTED + FIXED. This is the complementary blind spot the 18-H.4 A/B predicted:
review-strong checked the L1 lock as sender-AGNOSTIC (which it is) and the push code
path (status->rd only), but the auto-review caught that the TAXONOMY change opens a
NEW capability -- a `pipeline` sender could in principle post decision_request to
operator. The brief ss3 disposition #1 is explicit: pipeline is "transport-automation,
NOT authority", posting "a status to rd". So the intent-preserving fix is to constrain
the pipeline sender to `status` ONLY at the transport layer (a TIGHTENING within the
already-authorized VALID_FROM change -- "automate the transport, never the authority";
it does NOT cross a new tripwire). Added a guard in post_message + a regression test
(pipeline->operator decision_request rejects; pipeline non-status to rd rejects;
pipeline status to rd still passes).

## Round 3 — codex review-strong (post auto-review-fix re-review of the WHOLE diff)

### Codex response (verbatim verdict)
Findings: none. Re-reviewed the whole supplied diff and surrounding paths. The new
_AUTOMATED_EMITTER_TYPES guard is in the single delivery path before any writes,
blocks pipeline from all non-status types incl. decision_request to operator, and
does not widen VALID_TO. The pipeline helper hardcodes from=pipeline, to=rd,
type=status; the runner catches push failures before always calling the artifact
writer after successful compute. (Also confirmed the subject is built from local
`key` constants, not DB values -- no frontmatter-injection concern; DB detail/summary
are body content + ASCII-sanitized.)

NO_NEW_CRITICAL_MAJOR

### CONVERGENCE
review-strong converged (R2 + R3 both NO_NEW_CRITICAL_MAJOR; R1's MAJOR+MINOR fixed).
codex-auto-review's single complementary MAJOR (automated-emitter authority widening)
fixed + re-verified clean in R3. Both gates clean on the final head.
