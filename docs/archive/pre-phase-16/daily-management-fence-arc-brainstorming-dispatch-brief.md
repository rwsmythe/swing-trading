# Brainstorming Dispatch Brief — Daily-Management Network-Under-Fence (#16) Archive-API Split

**Arc:** Phase 15 / B-family operational hardening — the daily-management network-under-fence fix (`#16`).
**Cycle stage:** `copowers:brainstorming` (produce a LOCKED design spec, Codex-converged) — this is the FIRST of the full copowers cycle (brainstorm → writing-plans → executing-plans). The archive-API split has real blast radius, so the full cycle is mandated (operator, 2026-06-07).
**Branch-from:** main HEAD at the moment you create your worktree (currently `e71d437b`; re-verify with `git log --oneline -3`).
**Schema:** NONE expected — v24 holds. Zero migrations, zero CHECK changes, zero column adds. If your design somehow implies schema, STOP and flag it as a pivotal OQ.
**Deliverable:** a locked design spec at `docs/superpowers/specs/2026-06-07-daily-management-fence-archive-api-split-design.md` + Codex convergence (zero new crit/major) + `.copowers-findings.md` (prompts AND responses).

---

## 1. Mandate (one line)

Formalize + Codex-harden the **already-banked** robust design for the last remaining `runner.py` fence-hygiene locus: `_step_daily_management` does **yfinance network I/O while holding the per-trade SQLite write lock**. The fix is an **archive-API read-only-vs-fetch split** — warm the archive OUTSIDE the fence, read read-only INSIDE — so the held write transaction never does network I/O.

This is the **same bug class** as the Schwab market-data deadlock just fixed (`4f0b4010`, fetch-vs-write reorder), but **NOT a deadlock**: `_step_daily_management` writes no Schwab audit row during its sequential step, so there is no competing `audit_conn` writer. It is a **latent lock-hold** (🟡 hygiene) — a warm-miss / transient-empty / gap-fill can hold the write lock across a network round-trip and block a concurrent web writer. Lower severity than the deadlock; still a real fence-hygiene violation worth closing.

---

## 2. STEP 0 — re-ground BEFORE you design (line numbers JUST drifted)

The fetch-vs-write arc (`4f0b4010`) changed `runner.py` AFTER the precedent spec was written, so every line number in the precedent has moved. Re-verify on YOUR worktree HEAD before locking anything:

1. **The locus.** `_step_daily_management` is at [runner.py:3774](../swing/pipeline/runner.py). The per-trade fence is at **runner.py:3810** (`with lease.fenced_write() as conn:`), wrapping `compute_daily_approximate_snapshot(conn, …)` @3811 + `upsert_snapshot` @3835 + `state_transition` @3839. The `list_open_trades` pre-read fence @3806 is separate (a read; harmless).
2. **The fetch.** `compute_daily_approximate_snapshot` is at [daily_management.py:465](../swing/trades/daily_management.py) (carries a `# noqa: PLR0913  -- spec-locked signature` marker). Its `read_or_fetch_archive(...)` call is at **daily_management.py:510**, returning a full archive DataFrame ≤ `asof_session`, which the function then slices + computes MFE/MAE/SMA from.
3. **The network paths.** `read_or_fetch_archive` is at [ohlcv_archive.py:204](../swing/data/ohlcv_archive.py). yfinance I/O fires at **@257** (`needs_full_refresh` — archive missing/empty OR meta stale ≥7d) and **@275** (gap-fill, `latest_stored < today`). Read this function end-to-end (204–283) — its freshness/gap logic is WHY pre-warming alone cannot guarantee no in-fence fetch.
4. **The read-only precedent.** `resolve_ohlcv_window` (ohlcv_archive.py, the Shape-A read path consumed by the Schwab ladder T-C.3) reads parquet + filters to `[start, end]` with **NO yfinance fallback**. `_bar_for_date` (runner.py, observe locus) already uses it as a read-only path. Read both — your read-only sibling API should mirror this, NOT reinvent it. Verify whether `resolve_ohlcv_window`'s shape (Shape-A per-provider files) is directly consumable by `compute_daily_approximate_snapshot`'s needs (it expects the legacy `{TICKER}.parquet` Shape, capitalized OHLCV) or whether a thin read-only reader over the SAME archive `read_or_fetch_archive` writes is the cleaner sibling. **This is a real design fork — resolve it in the spec.**
5. **Confirm #16 is the ONLY remaining locus.** The precedent spec §2 audited all 18 `fenced_write` blocks; the two deadlock loci (#8 detect Pass-2, #9 observe) were fixed by `4f0b4010`. Spot-check that the post-arc tree still shows only `_step_daily_management` as a network-under-fence locus (re-run the §2-style reasoning over `runner.py` `fenced_write` blocks; you do not need the full 18-row table, but confirm no NEW locus crept in).

---

## 3. The head start — the precedent already banked this design

**Read [`docs/superpowers/specs/2026-06-06-fetch-vs-write-ordering-design.md`](superpowers/specs/2026-06-06-fetch-vs-write-ordering-design.md) §8 + OQ-D (§3) in full.** It banked THIS exact locus with a documented robust design:

> split the archive API into a fetch-capable warm path (called OUTSIDE the fence per open-trade ticker) and a pure **read-only** path (a parquet read with NO yfinance fallback — e.g. via `resolve_ohlcv_window`, as `_bar_for_date` already does); change `compute_daily_approximate_snapshot` (a spec-locked signature) to consume pre-warmed bars / the read-only path so the in-fence phase **skips + #27-logs** rather than re-fetches.

Your job is NOT to re-derive this from scratch — it is to **formalize it into an executing-ready, Codex-converged locked spec**: pin the exact API signatures, resolve the spec-locked-signature threading, enumerate the blast radius with proof of non-breakage, resolve the OQs with the operator, and write the discriminating TDD strategy. The precedent's §4.1/§4.2 per-locus reorder design (snapshot-before-fence, consume-inside, skip+#27 on miss) is your structural template; the precedent's OQ-A ("per-locus, just-before-its-own-write" pre-fetch — no bulk up-front pass) is the governing pattern.

---

## 4. The design to formalize (the shape, not the final word — brainstorm it)

The universal rule (from the precedent): **fetch happens with NO held `fenced_write`; the fence wraps only fast SQLite reads + the persist.** Apply it to `_step_daily_management`:

- **Warm OUTSIDE the fence, per open-trade ticker.** Before opening the per-trade write fence, call the fetch-capable `read_or_fetch_archive` (or an equivalent warm) for that trade's ticker so its parquet archive is fresh on disk. Per OQ-A, warm just-before-its-own-write (no bulk pass).
- **Read read-only INSIDE the fence.** `compute_daily_approximate_snapshot` (inside the fence) must use a **pure read-only** archive read (no yfinance fallback). On a read-only miss — including the case where the outside warm FAILED (transient-empty, network hiccup) — it must **skip + emit a #27 `warnings_json` entry**, never re-fetch under the lock. This is the part "warm-before-fence alone" cannot guarantee; the read-only API is what makes the guarantee structural.
- **The spec-locked-signature decision (CORE).** `compute_daily_approximate_snapshot` has a spec-locked signature (`ohlcv_archive_dir` + `archive_history_days` drive the fetch today). Decide HOW to thread the read-only mode without violating the §6.6 name locks: pass pre-warmed bars in as a new param? add a `read_only: bool` / `fetch: bool` param? have it call the read-only sibling unconditionally and rely on the outside warm? Each has trade-offs for the function's other callers (grep `compute_daily_approximate_snapshot` — is the pipeline runner the ONLY caller? CLI? web? tests?). Pin the chosen signature change and justify it against the existing spec lock (the lock may need an operator-sanctioned amendment — flag it).

---

## 5. Blast radius — the split must NOT break the existing fetch API

`read_or_fetch_archive` has ~9 production consumers (verify with a fresh grep — list each in the spec):
`runner.py` weather hook (@426) + the OHLCV ladder hook · `web/app.py` (@321) · `pipeline/ohlcv.py` `fetch_daily_bars` (@44) · `web/trade_charts.py` (@57) · `prices.py` (@56) · `web/ohlcv_cache.py` (@284) · `web/view_models/patterns/review_form.py` (@482) · `web/routes/patterns.py` (@106) · `daily_management.py` (@510 — THE locus).

**Constraint:** the existing fetch-capable `read_or_fetch_archive` signature + behavior stays byte-identical for all of these. The split **adds** a read-only sibling (and the outside-warm call site); it does not mutate the shared fetch API. Prove non-breakage: every non-locus consumer is untouched.

---

## 6. Locks / invariants to propagate (carry into writing-plans)

- **Schema NONE** (v24). DB-outside-Drive (`%USERPROFILE%/swing-data/swing.db`).
- **Lease-fencing contract:** every write stays inside `fenced_write` + the in-tx lease check; ONLY the fetch moves out. `LeaseRevokedError` MUST still re-raise (runner.py:3844 — Codex R2 M5).
- **#27 silent-skip-audit:** every new skip / read-only-miss / warm-failure path emits a `warnings_json` entry (step=`daily_management`, ticker, reason). The existing `archive returned None` → log+continue (runner.py:3828) becomes a #27-audited skip.
- **F6 empty-result-transient:** the outside warm MUST NOT blank the archive on a transient yfinance empty — `read_or_fetch_archive` already preserves the stale archive (ohlcv_archive.py:263); do not regress that. The read-only path reads whatever is on disk.
- **Session-anchor correctness:** the read still slices on `asof_session = last_completed_session(run_now)` (a BACKWARD-looking anchor — strict-`>`/`<=` semantics per the session-anchor gotcha family); the partial-bar strip is `read_or_fetch_archive`'s concern, preserved. Do not move the anchor.
- **OhlcvBar bad-bar handling (accepted-and-documented 2026-06-07):** unaffected — the yfinance fallback in the warm path already delivers correct bars; the read-only path reads the SAME archive. Do not entangle this arc with bad-bar work.
- **Data-integrity arc barriers** (completed-day write-barrier, `topbar_session_date`) + the lock-contention arc keepers (busy_timeout=30000, serialized `audit_conn`, G2′ telemetry) remain intact.
- **Idempotency:** `upsert_snapshot` SELECT-then-UPDATE-or-INSERT (same-session re-run preserves `management_record_id`); the state-machine `entered → managing` transition stays in-fence after the snapshot lands.

---

## 7. Open questions to resolve WITH the operator (brainstorming surfaces these)

These are the brainstorm's pivotal decisions — present them to the operator, don't silently pick:

- **OQ-1 — read-only sibling shape.** Reuse `resolve_ohlcv_window` (Shape-A) directly, or add a thin read-only reader over the SAME legacy `{TICKER}.parquet` archive that `read_or_fetch_archive` writes? (Shape/column-capitalization compatibility with `compute_daily_approximate_snapshot`'s slicing is the deciding factor — verify it.)
- **OQ-2 — spec-locked-signature threading.** Pass pre-warmed bars in vs a `read_only`/`fetch` flag vs unconditional read-only + outside-warm. Does the chosen change need an operator-sanctioned amendment to the §6.6 signature lock?
- **OQ-3 — warm-failure-then-read-only-miss behavior.** Confirm skip+#27 (NOT the current `None`-return silent continue, NOT a re-fetch). Is a skipped trade's missing snapshot acceptable for that run (≤1-run staleness, like the observe locus)? (Likely yes — but operator-confirm, since daily-mgmt snapshots drive the operator's open-position surface.)
- **OQ-4 — warm scope.** Per-open-trade-ticker just-before-its-fence (OQ-A precedent) vs one warm pass over all open-trade tickers before the per-trade loop. Open-trade count is small (~handful), so either is cheap — pick the one that mirrors the precedent and is simplest to reason about under the fence rule.

---

## 8. Test strategy seed (discriminating — fail-pre-fix / pass-post-fix)

Per `feedback_regression_test_arithmetic`, construct each test to FAIL on pre-fix and PASS on post-fix:

1. **Gold-standard lock-hold reproduction (the binding regression).** Drive the real `_step_daily_management` against a real file-backed SQLite DB with an open trade whose archive is stale/missing (forces the warm). Spy the archive fetch so it attempts a `BEGIN IMMEDIATE` on a SECOND connection (short busy_timeout). Pre-fix: the fetch fires INSIDE the held fence → second-conn `BEGIN IMMEDIATE` times out (lock-held) → assert fails. Post-fix: the fetch ran OUTSIDE the fence → succeeds → assert passes. **Anti-false-pass:** seed conditions that actually fire the warm + assert the fetch was called ≥1 time, so "no lock-hold" can't pass vacuously.
2. **Ordering assertion.** Spy exposes whether the lease is mid-transaction at fetch time; assert every fetch observed `in_fenced_write is False`; assert the in-fence read-only path does ZERO network calls.
3. **Snapshot-field parity (behavior-preserving).** For a warm archive, assert the persisted snapshot field dict (current_price, MFE/MAE, SMA, cap-util, heat, maturity_stage, state transition) is IDENTICAL pre- and post-reorder for the same inputs.
4. **Read-only-miss skip + #27 audit.** Inject a trade whose outside warm fails (transient-empty) AND whose read-only archive is absent; assert the trade is skipped, a #27 `warnings_json` entry is emitted, NO in-fence fetch occurs, and the step continues to the next trade (LeaseRevokedError still re-raises).
5. **Non-breakage of the shared fetch API.** Assert the existing `read_or_fetch_archive` signature/behavior is unchanged (one consumer's existing test still green; no consumer signature touched).
6. **Full fast suite green** (~7223 baseline — re-confirm your branch's actual count) + `ruff check swing/`.

---

## 9. copowers process (binding)

- **Run `copowers:brainstorming`** — it wraps `superpowers:brainstorming` (explore intent + design WITH the operator) then runs the adversarial Codex review loop **to convergence** (zero new crit/major; the 5-round cap is SUSPENDED for this project — run until `NO_NEW_CRITICAL_MAJOR`). Do not stop early while majors surface; do not pad after convergence.
- **Codex transport:** the MCP `codex` tools are DEAD in this VS Code extension. Use the **WSL Codex CLI fallback**: `wsl.exe bash -ilc 'export PATH="$HOME/.local/node22/bin:$PATH"; codex …'` (the PATH prefix is REQUIRED; liveness probe = `codex --version` → `codex-cli 0.135.0`). The worktree `.git` is unreachable from WSL — pre-generate the diff on Windows + tell Codex not to run git. (Memory `feedback_wsl_native_codex_invocation`.)
- **Persist BOTH prompts AND responses** of every Codex round (including the final `NO_NEW_CRITICAL_MAJOR` line) to a gitignored `.copowers-findings.md` so the orchestrator can independently confirm convergence at QA. (Memory `feedback_implementer_persist_codex_responses`.)
- **No `Co-Authored-By` footer; no `--no-verify`; conventional commits; final `-m` paragraph plain prose** (no `Word:`-leading lines → trailer-parse hazard). This phase commits only the spec doc (+ the gitignored findings file is NOT committed).
- **Return a report** to the orchestrator: the spec path, the resolved OQs, the Codex convergence verdict (with the round count + the final line), and any locks/invariants flagged for writing-plans. Then STOP — do not proceed to writing-plans (that is a separate commission after the orchestrator QAs this spec).

---

## 10. What this arc is NOT

- NOT the Schwab market-data deadlock (already fixed `4f0b4010`). NOT Issue #3 (`_count_open_at_run` — a separate bullet). NOT Gate 4 (the quote cassette). NOT the OhlcvBar bad-bar issue (accepted-and-documented; its own queued arc). NO schema change. Do not touch `_step_charts`, detect Pass-2, or observe (already correctly ordered by the precedent arc).
