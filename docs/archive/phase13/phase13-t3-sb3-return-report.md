# Phase 13 T3.SB3 — Review auto-fill (priors + MFE/MAE from OhlcvCache) return report

**Status:** READY FOR OPERATOR-PAIRED S2-S4 GATES + ORCHESTRATOR-DRIVEN MERGE.
**Branch:** `phase13-t3-sb3-review-auto-fill` — 8 commits off main HEAD `6d7cc3c` (T2.SB5 SHIPPED + housekeeping).
**Commit chain:** `1dd3b47` → `a2ce145` → `26df94e` → `452cadd` → `72fd96d` → `d3af86b` → `cab65d8` → `3173fce`.
**Baseline:** 5463 fast tests passed, 2 skipped, 0 failures (was 5412 + 3 skipped on main HEAD `6d7cc3c`; net +51 fast tests + 1 cross-bundle pin un-skip). ruff 0 E501. schema v20 UNCHANGED.

---

## §1 Scope shipped

Phase 13 T3.SB3 — Theme 3 review auto-fill (priors + MFE/MAE from OhlcvCache); 5 tasks per plan §G.8 + 3 fix-bundle commits closing pre-Codex + Codex R1 + Codex R2 findings.

| Task | Title | Tests landed | Acceptance per plan §G.8 |
|---|---|---|---|
| T-B.3.1 | Priors helpers per spec §E.4 | 17 (priors) | `ReviewPriors` frozen dataclass + `get_priors_for_ticker(conn, ticker, n=5)`; numeric grade encoding A=4..F=0; graceful at n=0; lessons ordered most-recent-first |
| T-B.3.2 | MFE/MAE from OhlcvCache per OQ-8 | 9 (auto-fill helper) | Phase 8 source-ladder + OhlcvCache fallback; `mfe_pct = max(highs)/entry - 1`; `mae_pct = min(lows)/entry - 1`; per-row failure isolation |
| T-B.3.3 | `review_form_page` + ReviewVM extension | 10 (route + VM) | Priors populated as defaults; MFE/MAE auto-populated; hidden audit envelope; session_date aligned; banner counters; backwards-compat default |
| T-B.3.4 | `cadence_complete_post` persist + 3 period helpers | 10 (helpers + persistence) | §E.5 LOCK signatures; `... or None` for nullable JSON column; audit envelope persisted; round-trip + backwards-compat |
| T-B.3.5 | T3.SB3 closer | 1 (fast E2E) + cross-bundle pin un-skip | Full E2E GET → POST; cross-bundle pin un-skip per plan §H.3 row 1 |

**Cross-bundle pin closure**: `test_ohlcv_cache_get_or_fetch_invariant` (still skipped on main HEAD `6d7cc3c` despite plan §H.3 row 1 schedule at T2.SB2 + T2.SB3 + T3.SB3); un-skipped at T-B.3.5 closer with a behavioral surface (ladder-bars-fetcher injection asserting DatetimeIndex + capitalized OHLCV columns; offline; no yfinance / Schwab network call).

---

## §2 LOCKs honored

| LOCK | Status |
|---|---|
| L1 — Spec §6.3 + §E.3 + §E.4 + §E.5 + §E.6 + §E.7 BINDING verbatim | ✓ Pre-Codex review scope-expansion #2 cross-checked byte-for-byte; CLEAN. |
| L2 — ZERO new Schwab API calls | ✓ Pre-Codex grep'd `schwab` references in T3.SB3 files: zero matches. |
| L3 — `daily_management_records` source FIRST in MFE/MAE source-ladder | ✓ `compute_mfe_mae_from_ohlcv_cache` Phase 8 branch wins; OhlcvCache only fires when Phase 8 absent. |
| L4 — ZERO schema changes (v20 LOCKED) | ✓ No migrations added; schema_version unchanged at v20. |
| L5 — `... or None` for `auto_populated_field_keys_json` nullable column | ✓ `complete_review_atomic` write-path + `cadence_complete_post` route both apply. Discriminating test landed. |
| L6 — Branch base = main HEAD `6d7cc3c` | ✓ Worktree created from `6d7cc3c`. |
| L7 — Frozen dataclasses + `__post_init__` runtime validation | ✓ `ReviewPriors.__post_init__` validates `process_grade_baseline ∈ [0.0, 4.0] | None` + tuple-not-list on candidate fields. |
| L8 — Cross-bundle pin un-skip at T-B.3.5 closer | ✓ `test_ohlcv_cache_get_or_fetch_invariant` un-skipped + behavioral surface materialized. |
| L9 — yfinance V2-FALLBACK only (OhlcvCache routes internally) | ✓ T3.SB3 is OhlcvCache consumer-side only. |
| L10 — Server-stamping at handler entry for audit envelope | ✓ Computed at VM build site; Codex R1 MAJOR #2 closed the tampering surface on the cadence POST path by switching to server-recompute at POST. |
| L11 — n=5 default for `get_priors_for_ticker` per §E.4 LOCK | ✓ Verified via `inspect.signature` discriminating test. |
| L12 — HTMX 3-surface discipline | ✓ HX-Request header propagated on embedded forms; `HX-Redirect: /` for cadence + `HX-Redirect: /reviews/pending` for per-trade success path (both target routes registered). |

---

## §3 Codex MCP adversarial-critic chain

**R1**: 2 MAJORs + 1 ACCEPT-WITH-RATIONALE.
- **MAJOR #1** — `_row_to_review_log` did not map v20 `auto_populated_field_keys_json` column on read; persisted value invisible to `get()` / `list_recent()` / `list_pending()`. FIX at `cab65d8`: map `row[23]`; 2 discriminating round-trip tests added.
- **MAJOR #2** — `cadence_complete_post` trusted operator-submitted hidden form input as audit envelope (tampering surface). FIX at `cab65d8`: drop the Form parameter + recompute the envelope at POST time using the same period helpers `build_cadence_complete_vm` uses on GET; hidden input removed from template; discriminating test asserts a fabricated tampered envelope is ignored (persisted column is NULL matching the server-side recompute).
- ACCEPT-WITH-RATIONALE — per-trade review form's hidden `auto_populated_field_keys_json` input is dead scaffolding (v20 schema lacks per-trade column; `review_post` does not consume the field). Forward-binding scaffolding for a future v21 trades-level audit dispatch.

**R2**: 1 MINOR + ACCEPT-WITH-RATIONALE on R1 fixes (both held). MINOR closed at `3173fce`: removed defensive `if len(row) > 23 else None` fallback in `_row_to_review_log` so schema-drift fails fast rather than silently degrading. Verdict: `NO_NEW_CRITICAL_MAJOR`. **Codex chain converged at R2** (2 rounds; faster than T2.SB4's R5 + on par with T2.SB5's R2).

---

## §4 Pre-Codex orchestrator-side review (22nd cumulative C.C lesson #6 BINDING validation)

Dispatched to a focused reviewer subagent BEFORE invoking Codex MCP, per brief §4.4 + cumulative discipline. Both scope expansions applied:

- **Expansion #1 (T3.SB2 hotfix `cf3c489` discipline)**: grep `swing/` for hardcoded duplicates of T3.SB3 constants. **CLEAN**: `REVIEW_PRIORS_DEFAULT_N=5` is the canonical site; `STAGE_GRADE_NUMERIC` is reused via import (NOT duplicated); no frozenset of allowed `auto_populated_field_keys` (operator-typed exclusion is implicit by omission).
- **Expansion #2 (T2.SB4 R1 M1 lesson)**: cross-check spec §6.3 + §E.3 + §E.4 + §E.5 + §E.6 + §E.7 BINDING text byte-for-byte vs brief sketches. **CLEAN**: n=5 default ✓; source-ladder Phase 8 FIRST + OhlcvCache FALLBACK ✓; grade encoding A=4..F=0 ✓; period helper signatures byte-for-byte ✓; ZERO Schwab gate ✓; ZERO schema changes ✓; `... or None` ✓; server-stamping at handler entry ✓; `Literal[...]` runtime validation ✓; per-row failure isolation ✓.

**Pre-Codex findings closed inline** (commit `d3af86b`):
- MAJOR #1 — `build_review_vm` emitted `json.dumps([])` (truthy "[]") on empty audit envelope; cadence path emitted `None`. Asymmetry would let downstream `... or None` accidentally persist the placeholder string. Fix: emit `None` on empty per cadence-path discipline.
- MINOR #3 — `compute_mfe_mae_from_ohlcv_cache` used `date.today()` for window sizing instead of `last_completed_session(datetime.now())`. Fix: switch for codebase-wide session-anchor consistency.

22nd cumulative C.C lesson #6 BANKED CLEAN with BOTH SCOPE EXPANSIONS applied.

---

## §5 ACCEPT-WITH-RATIONALE banked items (forward-binding for V2 / T2.SB6 / T4.SB)

1. **Per-trade review form's hidden `auto_populated_field_keys_json` input is forward-binding scaffolding.** v20 schema has the audit column on `review_log` (period reviews) only; no `trades.auto_populated_field_keys_json` column. The per-trade hidden input is rendered + server-stamped + visible in the response body (satisfying T-B.3.3 acceptance (c)) but the per-trade POST handler does NOT consume it (no tampering surface exists today since the value is ignored). Forward-binding: a future v21 migration could add a `trades`-level audit column; the per-trade hidden input becomes the canonical persistence anchor at that time. (Banked per Codex R1 + R2 ACCEPT-WITH-RATIONALE.)

2. **`mfe_pct != 0.0` audit-keys gate conflates "no data" with "exactly-zero excursion".** A trade where high/low both equal entry_price would produce `mfe_pct = mae_pct = 0.0` from real data (rare but possible). The current `auto_keys.append("mfe_pct")` predicate gates on truthiness. Bounded impact: helper's `(0.0, 0.0)` no-data fall-through semantic makes the corner case unverifiable from the boolean alone; V2 candidate is to return an explicit `MfeMaeResult` dataclass with `source: Literal['phase8', 'ohlcv', 'none']` tag for richer auditability.

3. **GET/POST recompute drift for cadence audit envelope is acceptable as new ground truth.** Codex R2 surfaced that the cadence POST-side recompute pathway means `vm.auto_populated_field_keys_json` shown at GET time may diverge from what's persisted at POST time if new completed reviews / reviewed trades land between render + submit. The recompute on POST is more authoritative; spec §6.3 doesn't lock the GET-side display value as the authoritative envelope. Forward-binding: if the operator-visible GET-side audit becomes the truth surface, T2.SB6 should switch to a signed nonce or token persistence pattern.

---

## §6 Forward-binding lessons surfaced

1. **Read-path mapping must keep pace with the write path on widened columns.** Codex R1 MAJOR #1 caught `_row_to_review_log` dropping the v20 `auto_populated_field_keys_json` column despite the write path persisting it successfully. Pattern: when widening a dataclass with a new field, audit ALL `_row_to_X` mapper functions in the same module + extend their column-position comments. Discriminating tests: round-trip persist via the write path + read back via the public reader; assert equality (NULL + non-NULL). **Pre-empt in any future schema widening dispatch:** writing-plans §5 watch item — when widening a dataclass field, grep for `_row_to_<table>` in the same module + extend it in the SAME task.

2. **"Server-stamped" hidden form inputs are STILL tampering surfaces unless the POST handler RECOMPUTES rather than ACCEPTS.** Codex R1 MAJOR #2 caught `cadence_complete_post` trusting the operator-submitted hidden field value verbatim. The "stamping" only happened at GET render time; POST blindly accepted whatever the operator (or a tampered curl invocation) submitted. Fix pattern: the POST handler MUST re-derive the audit envelope from canonical state at POST time, NOT consume the GET-side hidden input. Honors Phase 8 R2-R5 server-stamping family + L10 LOCK semantically — "server-stamped" means the SERVER computes the value, not that the value RENDERED at GET time is signed/trusted. **Pre-empt in any future hidden-audit-field design:** writing-plans §5 watch item — enumerate per-field disposition as (a) operator-supplied OR (b) recomputed-at-POST-from-canonical-state; ban (c) "trusted-from-GET-render" patterns.

3. **Audit envelope empty-state representation must be uniform across emit + persist paths.** Pre-Codex MAJOR #1 caught `build_review_vm` emitting `json.dumps([])` while `build_cadence_complete_vm` emitted `None`. The string "[]" is truthy under `... or None`, so any downstream POST persistence path would accidentally persist the placeholder string. Pattern: emit `None` (not "[]") on empty across all VM builders + writer paths; the `... or None` gotcha-defense only works if the upstream emit cooperates. **Pre-empt in any future audit-envelope design:** discriminating tests asserting empty → `None` (not "[]" / not "") at BOTH the VM emit + the persist write paths.

4. **Pre-Codex orchestrator-side review with BOTH scope expansions applied is now load-bearing.** 22nd cumulative C.C lesson #6 validation BANKED CLEAN; surfaced 1 MAJOR + 2 MINORs that would otherwise have cost a Codex round. The grep-for-duplicates expansion (T3.SB2 hotfix `cf3c489` discipline) + the spec-source-of-truth byte-for-byte expansion (T2.SB4 R1 M1 lesson) BOTH continue to pay dividends. **23rd validation expected at T2.SB6 dispatch.**

---

## §7 Files changed

```
swing/data/repos/review_log.py                                   |  23 +-
swing/trades/review.py                                           | 264 +++++++++++++
swing/trades/review_auto_fill.py                                 | 242 ++++++++++++
swing/web/routes/trades.py                                       |  58 ++-
swing/web/templates/partials/cadence_complete_form.html.j2       |  37 +-
swing/web/templates/partials/review_form.html.j2                 |  63 ++-
swing/web/view_models/trades.py                                  | 140 ++++++-
tests/integration/test_phase13_t3_sb3_review_auto_fill_e2e.py    | 203 ++++++++++
tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py      |  57 ++-
tests/trades/test_review_auto_fill.py                            | 393 +++++++++++++++++++
tests/trades/test_review_period_helpers.py                       | 416 ++++++++++++++++++++
tests/trades/test_review_priors.py                               | 298 ++++++++++++++
tests/web/test_cadence_complete_route.py                         |  51 +++
tests/web/test_review_form_auto_fill.py                          | 430 +++++++++++++++++++++
15 files changed, 2652 insertions(+), 268 deletions(-)
```

NEW production surfaces: `swing/trades/review_auto_fill.py`. NEW test files: `tests/trades/test_review_priors.py` + `tests/trades/test_review_auto_fill.py` + `tests/trades/test_review_period_helpers.py` + `tests/web/test_review_form_auto_fill.py` + `tests/integration/test_phase13_t3_sb3_review_auto_fill_e2e.py`.

---

## §8 S1 done criteria — CONFIRMED

- [x] All 5 T-B.3.X tasks committed (`1dd3b47` → `72fd96d`) plus 3 fix-bundle commits (`d3af86b`, `cab65d8`, `3173fce`).
- [x] `python -m pytest -m "not slow" -q -n auto` PASS: **5463 passed, 2 skipped, 0 failures** (baseline 5412 + 3 skipped; net +51 fast tests + 1 cross-bundle un-skip).
- [x] No slow E2E test added (T-B.3.5 uses fast-only E2E per plan).
- [x] `ruff check swing/` clean (0 E501).
- [x] Schema version unchanged at v20 (no migrations; `review_log.auto_populated_field_keys_json` column landed at T-A.1.1).
- [x] Pre-Codex orchestrator-side review dispatched + verdict captured (22nd cumulative C.C lesson #6 BANKED CLEAN with BOTH SCOPE EXPANSIONS applied).
- [x] All commits on branch have empty `Co-Authored-By` trailer (verified via `git log --pretty='%(trailers:key=Co-Authored-By)' phase13-t3-sb3-review-auto-fill --not main | grep -c .` returning 0).
- [x] Codex MCP adversarial-critic chain converged to `NO_NEW_CRITICAL_MAJOR` at R2 (2 rounds).

---

## §9 S2-S4 operator-paired gates (per brief §5.2)

Ready for operator. Reproduction recipe:

```bash
cd c:/Users/rwsmy/swing-trading
git fetch origin phase13-t3-sb3-review-auto-fill
git checkout phase13-t3-sb3-review-auto-fill
pip install -e ".[dev,web]"
python -m swing.cli web   # FastAPI + HTMX on 127.0.0.1:8080
```

- **S2 (browser)**: open `/trades/{trade_id}/review` for a closed-but-not-reviewed trade. Confirm: priors fieldset surfaces if prior same-ticker reviewed trades exist (mistake-tag candidates surfaced + process_grade_baseline displayed + lesson-learned candidates listed in `<details>`); MFE/MAE fieldset surfaces with non-zero values when OhlcvCache returns post-entry bars; hidden `auto_populated_field_keys_json` field present + non-empty audit envelope visible in DevTools.
- **S3 (round-trip)**: open `/reviews/{review_id}/complete` for a pending period review. Confirm: period helpers' starter text auto-populated into `primary_lesson` textarea (if prior completed reviews exist in the period); mistake-tag aggregate fieldset + cohort-health-deltas fieldset surface when reviewed trades exist. Submit the form; confirm DB write via `sqlite3 ~/swing-data/swing.db "SELECT auto_populated_field_keys_json FROM review_log WHERE review_id = N"`.
- **S4 (period review)**: as S3.

---

## §10 Pre-Codex review verdict (BINDING per brief §4.4)

**22nd cumulative C.C lesson #6 validation BANKED CLEAN with BOTH SCOPE EXPANSIONS applied.**

- Expansion #1 grep for hardcoded duplicates: ZERO matches.
- Expansion #2 spec source-of-truth cross-check: CLEAN on all 10 items (n=5 default; source-ladder ordering; numeric grade encoding A=4..F=0; period helper signatures; ZERO Schwab gate; ZERO schema changes; `... or None`; server-stamping; `Literal[...]` runtime validation; per-row failure isolation).
- 1 MAJOR + 2 MINORs surfaced inline + closed at commit `d3af86b` BEFORE Codex MCP invocation (kept Codex MCP rounds tight — converged at R2 vs T2.SB4's R5).

---

## §11 Streaks preserved

- **ZERO `Co-Authored-By` footer trailer drift** — ~320 cumulative commits at handoff time through T3.SB3 (8 new commits at handoff).
- **C.C lesson #6 cumulative validation** — 22nd validation BANKED CLEAN with BOTH SCOPE EXPANSIONS BINDING. 23rd expected at T2.SB6 dispatch.

---

*Phase 13 T3.SB3 — Theme 3 review auto-fill (priors + MFE/MAE from OhlcvCache) — 5 tasks shipped per plan §G.8; +51 fast tests; 1 cross-bundle pin un-skip; 3 Codex/pre-Codex fix bundles; ZERO Schwab API calls; v20 schema UNCHANGED. Codex chain converged at R2 NO_NEW_CRITICAL_MAJOR. 22nd cumulative C.C lesson #6 BANKED CLEAN. Ready for operator-paired S2-S4 gates + orchestrator-driven merge.*
