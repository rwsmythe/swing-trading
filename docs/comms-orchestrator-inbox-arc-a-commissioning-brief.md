# Comms Orchestrator-Inbox — Arc A Commissioning Brief (G6 core)

**Owner/author:** CHARC (Tool Development Director). **Date:** 2026-06-25. **Status:** COMMISSIONED.
**Phase context:** Phase-18-close **G6** (comms-system sync swing↔coa-chess), arc **A of A→B+C** (operator-sequenced 2026-06-25).
**§3 verdict:** CROSSES the tripwire (**new standing process** — a `SessionStart` hook + per-generation registry + a `UserPromptSubmit` heartbeat). CHARC-owned harness architecture; measurement-NEUTRAL → **RD fyi, NOT merge-blocking**. GO.
**Grounding / design source:**
- Prep + re-grounding: [`docs/comms-orchestrator-inbox-reconciliation-notes.md`](comms-orchestrator-inbox-reconciliation-notes.md) (read §"RE-GROUNDED 2026-06-25" first).
- Proven design SHAPE (sibling project, adapt — do NOT copy verbatim): `C:\Users\rwsmy\coa-chess\docs\comms-orchestrator-inbox-reference.md` + coa-chess's live `scripts/` hooks + `role_mail`.
- Harness model: [`docs/harness-architecture.md`](harness-architecture.md) §3 (comms taxonomy), §5 (tripwires), §6 (state-pointer convention).

---

## 0. Why (the friction this closes)

Swing's `role_mail` has `VALID_TO = (charc, rd, operator)` (verified on disk 2026-06-25, `role_mail.py:43`): **`--to orchestrator` is REJECTED.** Every director→orchestrator message must be hand-carried by the operator. The orchestrator is the one role that ROTATES on context (a generation hits its limit, hands off, a fresh one starts), so it can't have a singular fixed inbox — a message must reach *a specific running generation*, resolved at send time. coa-chess solved this (per-generation inbox + session registry) and it removed the same friction there. G6-A ports that mechanism to swing's roster.

## 1. Scope — Arc A ONLY

**IN:**
1. **Per-generation orchestrator inbox:** `comms/orchestrator/<session_id>/{inbox,read}` — one subtree per generation.
2. **Session registry:** `comms/sessions/<session_id>.json` — ONE FILE PER SESSION (no shared-map write contention); fields `{session_id, role, transcript_path, last_seen}`.
3. **`SessionStart` hook:** register the session (idempotent per-gen inbox creation) + prune-stale registry files; single-source the registry reader/writer so `role_mail` and the hooks share ONE implementation (no writer/reader drift).
4. **`UserPromptSubmit` heartbeat:** refresh the live session's `last_seen` every prompt.
5. **`role_mail` orchestrator addressing:** `--to orchestrator` (bare) = newest-live resolved at send; `--to orchestrator:<session_id>` = explicit generation; `read --role orchestrator --session <sid>`. This REMOVES the `--to orchestrator`-rejected restriction.
6. **`session_id` safety validation** at every write+consume site (it is path input — a dir name AND a filename).

**OUT (explicitly deferred — do NOT build in Arc A):**
- The launcher generalization (`start_directors.ps1` → role-parameterized) + the GUI `/orchestrator-bootstrap` copy button + the orchestrator bus aggregation → **Arc B**.
- The swing→scaffold GUI re-sync (port swing's B-11 dark-theme + B-13 expanded-`<details>` fixes into harness-template) → **Arc C**.
- **The close-hook unify requires NO swing change.** Decision (operator 2026-06-25): swing's `comms_stop_hook.py` **continue-once** design WINS; coa-chess migrates to it later (coa-chess's own CHARC/orch, not this arc). Leave `comms_stop_hook.py` untouched.
- Any edit inside coa-chess. (swing↔coa-chess parity is achieved by coa-chess pulling from the scaffold in Arc C — never by this arc reaching across repos.)

## 2. Design source caveat (§5.11 — sibling-project citation)

The coa-chess reference describes coa-chess's **as-built** (its post-implementation state). The symbols it names — `_orchestrator_inbox_messages`, `_newest_live_session_id`, `_split_target`, the 3 `.claude/hooks/` — **do NOT exist in swing today**; this arc CREATES the swing equivalents. Treat the reference as a *design shape to adapt*, not a spec to transcribe. Adapt to swing's roster: the **orchestrator is the SOLE rotating/per-gen role**; swing's 2nd director is `rd` (coa-chess's is `opsdir`); `charc`/`rd`/`operator` stay SINGULAR (unchanged). Verify every "coa-chess does X" claim against swing's actual code at writing-plans.

## 3. HAVE vs NEED (verified on disk 2026-06-25)

**HAVE:**
- `scripts/role_mail.py` — singular inboxes; `VALID_FROM=(charc,rd,operator,orchestrator,pipeline)`, `VALID_TO=(charc,rd,operator)`; resolution via `_list_inbox(root, role)` / `ack_message` / `_validate_recipients` / `_comms_root`; atomic delivery already uses same-dir `_write_temp` + `os.replace` (the Windows cross-volume gotcha is already respected — KEEP that pattern).
- `scripts/comms_unread_hook.py` — `UserPromptSubmit` hook; reads `SWING_ROLE`; `__file__`-anchored comms root (NOT cwd — KEEP); no-op unless role∈`{charc,rd}`; ALWAYS exits 0.
- `scripts/comms_stop_hook.py` — B-14 close-hook, LIVE (untouched by this arc).
- `comms/{charc,rd,operator}/{inbox,read}` + `comms/.sessions.json` (a display-name map only — NOT the new registry).

**NEED (this arc):** `comms/orchestrator/<sid>/` + `comms/sessions/` registry + the `SessionStart` hook + the heartbeat + `role_mail` `:<sid>`/newest-live addressing + `session_id` validation + the single-sourced registry module.

## 4. Design specifics (the load-bearing shape — adapt at writing-plans)

- **Addressing semantics (binding):**
  - `--to orchestrator` (bare) → resolve `newest_live` at SEND time. **If no live generation exists → CLEAR ERROR, never a silent drop.**
  - `--to orchestrator:<session_id>` → write directly to that gen's inbox, **registry-INDEPENDENT** (a known generation stays reachable even if its heartbeat is stale/pruned — "registry-pruned ≠ gone").
  - `read --role orchestrator --session <sid>` for the read/ack side.
- **Registry:** one JSON file per session; `last_seen` is a heartbeat; `STALE_SECONDS = 45*60`; `newest_live` = newest non-stale; prune stale files on `SessionStart`. (Carry a CLOCK note: swing's live-clock test brittleness, debt D9 — make the staleness comparison injectable/freezable for tests, don't bake `datetime.now()` into the pure resolver.)
- **`SessionStart` hook location — CHARC engineering call: put it in `scripts/` (wired via `.claude/settings.json` `SessionStart`), matching swing's existing `comms_unread_hook.py`/`comms_stop_hook.py` pattern — do NOT introduce a `.claude/hooks/` dir (that is coa-chess's convention, not swing's).** One new `scripts/` hook file + one new `settings.json` `SessionStart` entry.
- **Single-source the registry (lessons-learned guard #4):** the registry read/write/prune + `newest_live`/`read_entry` live in ONE new stdlib module (e.g. `scripts/comms_session_registry.py`); the `SessionStart` hook, the `UserPromptSubmit` heartbeat, and `role_mail` all IMPORT it. No duplicated registry logic.
- **Heartbeat seam (non-obvious — name it so it isn't missed):** the heartbeat refresh must run for the live session **regardless of role** (the orchestrator needs it most), so it must NOT sit behind `comms_unread_hook.py`'s `role∈{charc,rd}` no-op gate. Either (a) refresh in the registry module called at the TOP of the unread hook before that gate, or (b) a separate `UserPromptSubmit` hook command. Implementer's call at writing-plans; the constraint is: **an orchestrator session's `last_seen` DOES refresh.**
- **Rollover state-pointer:** swing already writes `orchestrator-handoff-*` docs; align to the harness `<role>-state.md` newest-live pattern (harness-architecture §6) where it reduces hunt — but a full `orchestrator-state.md` adoption is OPTIONAL in Arc A (the registry's explicit-`:sid` + newest-live is the primary resilience). Flag, don't force.
- **Registration scope:** register any session whose `SWING_ROLE` is set (orchestrator + the directors), so the future GUI bus (Arc B) and newest-live both work; `newest_live` resolution is orchestrator-specific.

## 5. Lessons-learned guards = ACCEPTANCE CRITERIA (the non-obvious parts coa-chess paid for)

Each is a binding acceptance criterion with a discriminating test:
1. **`newest_live == None` is NOT "window closed"** — a gen idle >45 min is pruned yet resumable via explicit `:<sid>`. Test: prune a gen, assert `:<sid>` still delivers.
2. **A rotating worker gets a per-gen box, never a singular one** — the orchestrator inbox is `comms/orchestrator/<sid>/`, not `comms/orchestrator/`.
3. **One-file-per-session registry > a shared map** — no write contention; a partial/corrupt file degrades to one-entry-missing, not a corrupt global. Test: a malformed registry file does not break resolution of the others.
4. **Single-sourced registry reader** — `role_mail` imports `newest_live`/`read_entry` from the registry module; assert no second copy of the resolver exists (grep-clean).
5. **`session_id` is path input** — validate it as a safe single path segment at EVERY write+consume site, and require `filename == embedded-id` (anti-traversal / anti-mis-route). Test: `../`, absolute, and empty `session_id`s are rejected loudly.
6. **Explicit-`:sid` + the rollover pointer are the resilience pair** — both addressing forms work; the explicit form is registry-independent.

## 6. §3 / locks to PRESERVE

- **The comms taxonomy (harness-architecture §3) is UNCHANGED.** `decision_request` stays operator-recipient-only (`L1`, `role_mail.py:263`, sender-agnostic — verified). Adding orchestrator as a `--to` RECIPIENT does **not** touch the type gate: an orchestrator can RECEIVE `fyi|status|query|return_report` (same as any role→role), and `decision_request` to an orchestrator stays REFUSED by the existing recipient gate. **Confirm at writing-plans that widening `VALID_TO` with `orchestrator` does not let `decision_request` reach a non-operator** (the 18-H.7 sender-widening lesson, inverted to the recipient side — verify the type×recipient matrix, not just that the happy path works).
- **STDLIB-ONLY comms core** — the new registry module + hook import nothing outside stdlib. Add/keep a dependency-posture test asserting it (coa-chess enforces via `tests/test_dependency_posture.py`).
- **`__file__`-anchored comms root** everywhere (cwd-independent) — preserve the existing pattern; do NOT resolve comms paths from cwd.
- **Atomic delivery** via same-dir `mkstemp`/`_write_temp` + `os.replace` + collision-suffix — reuse swing's existing helper, do not hand-roll a cross-volume-unsafe variant.

## 7. Test / gate posture

- **Behavioral tests (over a tmp comms tree):** newest-live resolution; explicit-`:sid` delivers to a pruned gen; no-live-gen → CLEAR ERROR; stale-prune at `SessionStart`; `session_id` path-validation/anti-traversal; the type×recipient matrix (orchestrator can't receive `decision_request`); a malformed registry file doesn't break others; the heartbeat refreshes an orchestrator session's `last_seen`.
- **Merged-head no-false-green suite** is the binding green (memory `feedback_no_false_green_claim`) — re-run on the merged head, READ the result.
- **Operator §5.10 live-witness is BINDING for the addressing UX** (CHARC-guided): from a director session, `--to orchestrator` reaches the running generation; an explicit `:<sid>` reaches a specific (incl. idle/pruned) gen; the unread/registry surfaces show the orchestrator's box. The seeded-gate-masks-default discipline: also witness the empty/no-live-gen path (the CLEAR ERROR, not a silent drop).
- Codex review-strong (gpt-5.5/high) to convergence; codex-auto-review complementary second eye (production-adjacent harness code, repo-access review).

## 8. Dispatch recommendation

- **Implementer cell:** `implementer-opus-high`. Rationale: the DESIGN is settled (this brief + the coa-chess reference remove the ambiguity), but it is multi-file, path-safety-sensitive, and cross-cutting (a new module + two hooks + `role_mail` surgery + a settings.json wire) with real footguns (the heartbeat gate seam, `session_id` traversal, the type×recipient matrix, Windows atomic-replace). Not measurement-chain (no `swing/` carve-out, no schema) → NOT `-max`; richer than mechanical → above `-sonnet`. Opus/high fits.
- **Orchestrator:** Opus xhigh (default).
- Worktree-isolated executing (comms files + `scripts/` + `.claude/settings.json`; no `swing/` package touch).

## 9. Return report

**The ORCHESTRATOR posts the return report to `charc` (+ `operator` fyi) AFTER its own QA** — the implementer reports to its orchestrator in chat, never to a director inbox (memory `feedback_implementer_never_posts_to_directors`; charter §5.6). CHARC then code-QAs the §3 conditions + the lessons-learned guards on disk; RD gets an fyi (comms-user, not measurement); the operator's §5.10 live-witness is the binding gate before merge.
