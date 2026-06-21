# Commissioning Brief — `harness_probe` research-output size check (D18, CHARC-lane FORM half)

**Commissioned by:** CHARC (Tool Development Director)
**Date:** 2026-06-21
**Arc:** register **D18**, the CHARC-lane FORM half only. The ~1.5 GB research-content *disposition* (delete/retain) is routed SEPARATELY to RD (the content decision; operator-concurred 2026-06-21).
**Status:** COMMISSIONED — no §3 tripwire (self-certified). Awaiting dispatch.
**Tripwires crossed:** **NONE.** Amends CHARC's own `scripts/harness_probe.py` (read-only, stdlib-only ASCII probe) + its test. No new schema/module/dependency/standing-process/carve-out. **CHARC-lane FORM** — no RD gate, no operator §5.10 witness (no measurement or user-visible change).

---

## §1 — What + why

Add a size check to `scripts/harness_probe.py` that reports the total size of `exports/research/` and `research/harness/` and fires ATTENTION above a calibrated ceiling. D18 surfaced ~1.5 GB of research output/cache with **no proactive visibility** — the operator caught it only by a manual `du`. The probe (the §4.2 harness-hygiene standard's instrument) governs FORM weight/size and should surface this regression itself.

**Grounding (CHARC, verified on disk 2026-06-21 — do NOT re-derive):**
- `exports/research/` = **1.1 GB**, dominated by `pattern-cohort-detection-*` (7 dirs, ~1.1 GB, all stale 2026-05-25/26 from a closed arc; bulk = gitignored 275 MB `results.csv` files). `shadow-expectancy-*` = **246K / 14 dirs**, **ALREADY keep-90 pruned** by `swing/pipeline/runner.py:_prune_shadow_expectancy_artifacts` (nightly) — NOT the problem (the register's original premise was wrong; corrected in §4 D18).
- `research/harness/` = **466 MB**, dominated by `earnings_proximity/diagnostic-out` (463 MB).

---

## §2 — Design contract

- Compute the total byte size of `exports/research/` and of `research/harness/` via **stdlib `os.walk`/`os.scandir` summing `st_size`** — NO `du` subprocess (cross-platform / Windows-safe). Report each ALWAYS as a human-readable INFO line (MB/GB).
- **Fire ATTENTION** when either exceeds its v1 ceiling. **v1 calibration (amend with a dated note per §4.2):** `exports/research/` **> 500 MB**; `research/harness/` **> 200 MB**. Both fire at CURRENT levels — **intended**: the probe keeps flagging the live bloat until RD's disposition lands, then goes quiet. (CHARC re-calibrates to RD's retained level after the disposition.)
- **ASCII output only** (the probe contract; the cp1252 gotcha). Keep it FAST: a bounded walk over **those two dirs only** — never the whole repo / `reference/` / `.git` / `.worktrees`.
- **Never raise:** guard a missing dir (treat as 0 / skip). The probe must stay defensive.
- Follow the probe's existing check-emission pattern (the `[OK]`/`[INFO]`/ATTENTION lines + the exit-1-on-attention contract).

---

## §3 — Test obligations

- Grep `tests/` for the existing `harness_probe` test module and mirror its style (monkeypatch the probe root to a `tmp_path`). Seed `exports/research/` + `research/harness/` **over and under** the ceiling; assert the INFO line renders and the ATTENTION fires / does-not-fire accordingly. If no probe test module exists, add a focused one.
- Assert **no raise** when either dir is absent.
- Assert **ASCII-only** output (no non-ASCII glyphs in the new lines).
- Before-review: the probe's test module green; `python scripts/harness_probe.py` runs and produces valid output (it WILL now exit 1 — that is correct, it is flagging the live D18 bloat).

---

## §4 — Gates

- **Codex review-fast** to convergence (this is CHARC tooling in `scripts/`, stdlib-only, NOT production `swing/` measurement code — review-fast is the right tier).
- **CHARC QA on disk** (check lands at the two dirs, thresholds as specced, ASCII, never-raises, tests green; `harness_probe.py` stays read-only/stdlib-only).
- **No RD gate; no operator §5.10 witness** (FORM tooling; no measurement/user-visible change).
- Before-review: probe test module green + `ruff check` clean on the touched files.

---

## §5 — Out of scope

- **The ~1.5 GB disposition** (delete/retain the pattern-cohort + earnings_proximity artifacts) — routed to **RD** separately (the content decision).
- **A standing keep-N prune for `pattern-cohort-detection-*`** — DEFERRED (low value: manual/occasional output, a month stale, not growing). Revisit only if RD wants auto-prune going forward.
- **A total-repo-size check** — deliberately omitted (`reference/` book corpus + `.git` + `.worktrees` are intentional/transient noise); the two targeted research dirs are the clean signal.
- **The §4.2 standard table row** for this new check — **CHARC adds it** (the charter/standard is CHARC content; the implementer does NOT edit it).

---

## §6 — Return report

The **ORCHESTRATOR** posts the return report to `charc` **AFTER its own QA gate**. The implementer reports to its orchestrator in chat; it NEVER posts to a director inbox (memory `feedback_implementer_never_posts_to_directors`; CHARC §5.6).

---

## §7 — Dispatch model + effort recommendation

Small, settled, CHARC tooling — a lean executing pass with the brief as spec (no separate writing-plans needed unless the orchestrator prefers one).
- **executing → `implementer-sonnet-high`** — mechanical-but-careful: a stdlib size walk + threshold calibration + a probe test; the design is fully settled here. Codex **review-fast**. Select + announce per `docs/implementer-dispatch-recipe.md`.
