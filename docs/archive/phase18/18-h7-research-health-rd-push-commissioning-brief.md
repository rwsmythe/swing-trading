# Commissioning Brief — 18-H.7: nightly research-health RED → role_mail push to RD

**Commissioned by:** CHARC (Tool Development Director)
**Date:** 2026-06-22
**Arc:** 18-H.7 (Phase-18 G3) — the nightly `research_health` ATTENTION → `role_mail` push to RD that 18-D deferred. A SWING arc (pipeline + comms); NOT cross-repo.
**Status:** COMMISSIONED — **CHARC §3 architecture pass = GO** (the tripwire dispositions are §3 below). Awaiting operator dispatch.
**§3 tripwire: CROSSED** — a **new standing process** (an automated nightly pipeline→comms emit) + a **comms-taxonomy change** (a new `VALID_FROM` sender). CHARC owns the §3 pass (this brief). NOT crossed: new schema, new module/package (additive to existing), new external dependency, `swing/trades`|`swing/data` carve-out.
**Routing:** changes NO measurement VALUE (a notify on the EXISTING RED computation) → **RD = fyi, NOT merge-blocking** (RD pre-specced the demand + will fyi-review the shipped emit: confirm RED-not-yellow + carries the per-check detail). No operator §5.10 live-witness required (a notify; forcing a real RED is impractical — the tests are the witness).

---

## §0 — RD demand-spec (captured 2026-06-22, thread `18h7-nightly-rd-push`; do NOT re-derive)

- **(a) TRIGGER = overall RED only** (`status.overall == "red"`), NOT yellow — the yellows are self-healing/benign-by-design (the calibrations exist to suppress that cry-wolf); a RED is the genuinely-actionable integrity break. The message names the specific RED check(s) so RD triages severity itself.
- **(b) CONTENT = the per-check DETAIL string** (the regression-vs-accepted discriminator RD most needs) + the fired check key(s) + each red check's summary AND detail + the run id + a pointer to `exports/research/health/latest.json` + the GUI research stoplight. (RD maps each check to its T1/T2 taxonomy itself — do NOT encode RD's taxonomy in the emit.)
- **(c) FREQUENCY = EDGE-TRIGGER** (green/yellow→red) as the primary. RD's weekly-re-nag-while-red is OPTIONAL: *"IF a stateful weekly re-nag is non-trivial engineering, pure edge-trigger is ACCEPTABLE — the passive backstops [the 18-F GUI stoplight stays red + the operator weekly glance + RD's monthly read] catch a missed edge-push; if you cut it, note 'no re-nag'."* **CHARC call: ship PURE EDGE-TRIGGER in V1, DEFER the weekly re-nag** (it needs a persistent last-push timestamp = extra state; the edge-trigger reads the prior `latest.json` with NO new state; the passive backstops cover a miss). The brief NOTES "no re-nag" to RD — the passive surfaces are the persistent-red backstop.

## §1 — Verified grounding (CHARC, on disk — do NOT re-derive)

- **Hook point:** `swing/pipeline/runner.py:_step_research_health` (`:1323`, run at `:1060` under `step_guard`, best-effort, read-only `mode=ro` conn) calls `compute_research_health(conn, cfg, exports_root)` → a `ResearchHealthStatus`, then `write_research_health_artifact(status)`. The push slots in **after `compute_research_health` returns and BEFORE (or around) the artifact write** — so the edge-trigger can read the PRIOR `latest.json` before it is overwritten.
- **The status shape** (`swing/monitoring/research_health.py`): `ResearchHealthStatus.overall` (∈ {green,yellow,red} = `worst_of(checks)`), `.checks` = `list[ResearchHealthCheck]` each with `.key` / `.status` / `.summary` / `.detail` (str|None). RED-only trigger = `status.overall == "red"`; the red checks = `[c for c in status.checks if c.status == "red"]`; the content = each red check's `key`/`summary`/`detail`.
- **`role_mail`** (`scripts/role_mail.py`): `VALID_FROM = ("charc","rd","operator","orchestrator")` (the pipeline is NOT a sender — the taxonomy gap), `VALID_TO` includes `rd`, `VALID_TYPES` includes `status`. **`post_message(...)` (`:224`) already EXISTS and is importable** (it takes a `comms_root`; tests pass a tmp dir). So "importable-post" is largely satisfied — the wrinkle is the `scripts/`→`swing/` import reachability.

## §2 — Design contract

**Where:** add the push to `_step_research_health` (the existing best-effort step), AFTER `compute_research_health` returns. Compose + post BEFORE or alongside `write_research_health_artifact` so the edge-trigger reads the prior overall.

**Edge-trigger (no new state):** read the PRIOR `latest.json`'s `overall` (via the existing artifact path; absent/unparseable prior → treat as non-red). Push IFF `current.overall == "red"` AND `prior.overall != "red"` (green/yellow→red, and the first-ever-RED case absent→red). Then write the new `latest.json`. NO new state file; NO weekly re-nag (V1).

**The message:** `--from pipeline --to rd --type status`, subject names the RED + the fired check keys; body = overall=red + each red check's `key` + `summary` + `detail` + the run id + the `exports/research/health/latest.json` path + the GUI research-stoplight pointer. ASCII-only (the cp1252 gotcha).

**The §3 design decisions (CHARC-owned):**
1. **Sender taxonomy:** add **`"pipeline"`** to `role_mail.VALID_FROM` — an automated-emitter sender (distinct from the human/agent roles), posting a `status` to `rd`. This is transport-automation (a notify), NOT authority — taxonomy-consistent ("automate the transport, never the authority"). Single-source any hook/test mirror of `VALID_FROM` if one exists (per the B-12 single-source discipline).
2. **Importable-post:** reuse `post_message` (it exists) via a **path-resilient import** of `role_mail` (the same pattern the comms hooks use), wrapped in a THIN swing-side notify helper (e.g. in `swing/monitoring/`) that owns the edge-detection + message composition + the post call. Keeps the import wrinkle in one place; the runner step just calls the helper. **Test-safe:** the helper resolves a `comms_root` (default repo `comms/`; tests pass a tmp dir) so tests exercise the push WITHOUT posting to the live comms.
3. **Best-effort / never-fail-the-run:** the push lives under the existing `step_guard` best-effort contract — a push failure is swallowed+logged, NEVER fails the pipeline (mirror the step's existing posture). The push is read-only w.r.t. the measurement DB.

## §3 — CHARC §3 architecture pass (GO)

| Tripwire | Crossed? | Disposition |
|---|---|---|
| New standing process | **YES → AUTHORIZED** | An automated nightly pipeline→comms `status` emit. Comms-staging judgment: this is a NARROW transport-automation (a single RED notify, edge-triggered), consistent with the comms taxonomy — it does NOT require the full Stage-2 push bus; it is one automated `status` emit reusing the Stage-1 mailbox. |
| Comms-taxonomy change | **YES → AUTHORIZED** | Add `"pipeline"` to `VALID_FROM` (an automated-emitter sender). `status`→`rd` only; no `decision_request`, no authority. |
| New schema / module / dependency | **NO** | Additive to existing `runner.py` + `research_health.py` + a thin `swing/monitoring/` helper + the `role_mail` `VALID_FROM` line; stdlib. |
| `swing/trades`\|`swing/data` carve-out | **NO** | `swing/pipeline` + `swing/monitoring` + `scripts/role_mail.py`; read-only w.r.t. the measurement DB. |

Measurement VALUE untouched (a notify on the existing RED) → RD-fyi, not merge-blocking.

## §4 — Test obligations (TDD)

- **Trigger discrimination (binding):** overall=red + prior!=red → posts exactly one `status` to `rd`; overall=yellow → NO post; overall=green → NO post; overall=red + prior=red (no edge) → NO post (the edge-trigger). Each via the production push helper over a tmp `comms_root`.
- **Content:** the posted message carries the red check `key`(s) + `summary` + **`detail`** + the run id + the `latest.json` pointer (assert the detail string is present — RD's regression-vs-accepted discriminator).
- **First-ever-RED:** absent prior `latest.json` + current red → posts (absent→red is an edge).
- **Sender taxonomy:** `post_message(--from pipeline ...)` is accepted (pipeline ∈ VALID_FROM); a `--to` other than the allowed set still rejects; `decision_request` from pipeline still rejects (the L1 lock unchanged).
- **Never-fail-the-run:** a push exception is swallowed+logged; `_step_research_health` still completes + still writes `latest.json` (best-effort preserved).
- **Test-safe:** the push targets the tmp `comms_root`, never the live `comms/`.
- Regression-test-arithmetic: each discriminating test FAILS pre-fix, PASSES post — reason both paths.

## §5 — Gates

- **Codex review-strong** (gpt-5.5/high, repo-access) to convergence + codex-auto-review.
- **CHARC §3 QA on disk** — the sender-taxonomy add is single-sourced + transport-only; the edge-trigger reads-prior-then-writes with no new state; the push is best-effort/never-fails-the-run + test-safe; the message carries the per-check detail; no measurement-value change.
- **RD fyi-review of the shipped emit** (RED-not-yellow + carries detail) — NOT merge-blocking (RD pre-specced).
- **Before-review full fast-suite + `ruff check swing/`** clean.
- No operator §5.10 live-witness required (a notify; the trigger-discrimination tests are the witness).

## §6 — Out of scope

- The **weekly re-nag** — DEFERRED (V1 = pure edge-trigger; note "no re-nag" to RD; the passive backstops are the persistent-red surface). A V2 nicety if the operator wants it (needs a last-push timestamp).
- Pushing on YELLOW — explicitly excluded (RD: cry-wolf).
- Pushing to anyone but RD; any `decision_request` (authority stays operator-routed).
- The `comms/roles/` store, the scaffold — unrelated (those are harness-template).

## §7 — Return report

The **ORCHESTRATOR** posts the return report to `charc` (+`rd` as fyi) **AFTER its QA gate**. The implementer reports to its orchestrator in chat; never to a director inbox.

## §8 — Dispatch model + effort recommendation

- **writing-plans → `implementer-opus-xhigh`** — the edge-trigger/read-prior design, the trigger-discrimination distinguishing-test arithmetic, the sender-taxonomy + import-reachability decisions.
- **executing → `implementer-opus-high`** — additive pipeline+comms wiring (best-effort, read-only w.r.t. the DB; not a measurement-value mutation), so `-high`. Codex review-strong to convergence. Select + announce per `docs/implementer-dispatch-recipe.md`.
