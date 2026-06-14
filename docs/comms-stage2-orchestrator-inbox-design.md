# Comms Stage 2 — Orchestrator Inbox + Session Registry (settled design, DEFERRED)

**Status:** SETTLED 2026-06-14 (operator + CHARC design dialogue) — **NOT built.** This is a deferred Stage-2 build-spec. Build only when the operator green-lights an orchestrator inbox, gated on the Stage-2 evidence bar (friction must demonstrably warrant it). CHARC-owned harness architecture (corrections route through CHARC).
**Companions:** `docs/comms-stage2-push-research.md` (the push-comms landscape) · `docs/harness-architecture.md` §3 (the comms taxonomy + staging + the transport-vs-tracker convention) · `tool-director-context.md` §2.5 (staging decision-of-record + friction ledger).
**Why captured now:** the design lived only in a working conversation; per the transport-vs-tracker / durable-landing principle, settled design gets a durable home rather than being re-derived later.

---

## 1. Problem this solves
Two friction instances at the orchestrator boundary (the Stage-2 evidence):
- **#1 (2026-06-12):** directors cannot bus-reply to the orchestrator — it has no inbox; all orchestrator-bound traffic is operator-hand-carried.
- **#2 (2026-06-13):** addressed separately by the transport-vs-tracker convention (must-persist content gets a durable tracker, not a mailbox message). NOT primarily inbox evidence.

An orchestrator inbox closes #1. The complication: **multiple orchestrator generations can run concurrently**, so "the orchestrator" is not a single addressable target — hence the session registry below.

## 2. Session registry (the addressing substrate)

**One file per session** — `comms/sessions/<session_id>.json` — mirroring the mailbox's one-file-per-message pattern (no shared-file read-modify-write concurrency, which is the `.sessions.json` hazard). Each file: `{ session_id, role, transcript_path, started_ts, last_seen }`.

**Unique id = the documented hook-provided `session_id`** (delivered in every hook's JSON input alongside `transcript_path`). **NOT** the `CLAUDE_CODE_SESSION_ID` env var — that is observed-but-UNDOCUMENTED and may change across versions; use it only as a last-resort fallback (a model can read it via a bash call).

**Liveness = a hook-written `last_seen` heartbeat**, refreshed by the `UserPromptSubmit` hook each turn. (Chosen over transcript-mtime: hook-owned, no transcript-path correlation needed.) Staleness = `last_seen` age past a threshold (e.g. 30–60 min; tune at build).

**Lifecycle hooks:**
| Hook | Action | Notes |
|---|---|---|
| `SessionStart` | **create** the entry (reads `session_id`, `transcript_path` from hook JSON; `role` from the launch-time env var) | fires + completes BEFORE the first prompt (documented); gets a `source` field (`startup`/`resume`/`clear`/`compact`) — on `resume`, refresh the existing entry (same `session_id`) rather than duplicate |
| `UserPromptSubmit` | **silent refresh + recreate-if-missing** (update `last_seen`; rebuild the file if a prune removed it) | this is the SELF-HEAL; silent (no stdout) → **zero model tokens** |
| opportunistic prune | **delete** entries stale by `last_seen` age | runs at each `SessionStart` (new session prunes on entry) + at any registry read (reader-as-cleaner, the stale-lockfile pattern). NO daemon. |
| `SessionEnd` | **best-effort tidy delete** | `SessionEnd` is the termination hook (NOT `Stop`, which fires per-turn). Best-effort only — NOT reliable on window-close / Ctrl-C / crash; make it idempotent. The opportunistic prune + liveness is what makes correctness independent of whether it fired. |

**Self-healing:** a live-but-idle session pruned during a quiet period (e.g. overnight) re-registers on its next prompt (the `UserPromptSubmit` recreate-if-missing). Residual: a session left truly idle (zero interaction) stays pruned until it's next interacted with — benign, because a dormant session isn't processing anyway; anything addressed to it waits durably in its inbox and is drained when it wakes (and re-registers in the same turn).

## 3. Role must reach the HOOK at launch (the load-bearing requirement)
The generic hooks can't know a session's role. A **model-written prompt-token does NOT self-heal** (when the hook recreates a pruned file it can't re-add a role it doesn't know) — rejected. Instead the role arrives as a **launch-time `ROLE` env var** the hook reads, so the hook owns the FULL entry and recreate-if-missing restores everything. This also enables **role-gated registration** (only orchestrators register) instead of register-everyone-and-filter.

## 4. Launch-model change (the operating-pattern shift)
Per-session env isolation is **impossible in the Claude Code extension panel** (shared extension-host process — two panel sessions can't hold different `ROLE`). It works only in the **CLI / integrated terminal** (own process, isolated env, full hooks, unique `session_id`).

⇒ **Orchestrators move from the extension chat panel to a CC-in-integrated-terminal tab**, launched via a VS Code **`tasks.json` task with an `env` block** (`{ "ROLE": "orchestrator" }`). Still "in VS Code," still under manual operator relay — a terminal tab instead of the sidebar. (`CLAUDE_ENV_FILE` is the documented native env-persistence mechanism as a secondary tool.)

**Convergence benefit:** every role becomes a ROLE-tagged CLI session — directors via `start_directors.ps1` (wt.exe windows, `SWING_ROLE`), orchestrators via the `tasks.json` task (VS Code integrated terminal, `ROLE`). The registry + hooks then work uniformly across all roles; no orchestrator special-casing.

## 5. Cost
Hooks run as **shell, not model invocations** — a SILENT refresh hook (stat + recreate + touch `last_seen`, no stdout) costs **zero model tokens** and sub-ms latency. Only hook STDOUT becomes injected context (that's how the unread-hook's `[comms] N unread` line is the lone token cost in the chain — unchanged). Therefore: keep registry maintenance in silent hooks; **never** do it in the prompt/model (a per-turn model check costs tokens every turn AND is unreliable).

## 6. The inbox itself
- **Addressing:** the registry enables per-generation addressing (`orchestrator-<session_id>`) IF needed; a **single shared `comms/orchestrator/inbox`** drained by the current generation is simpler and likely sufficient (concurrent generations are rare handoff windows). Decide at build.
- **Taxonomy LOCK (non-negotiable):** an orchestrator inbox is **info-only** (`fyi | status | query`) — it must NEVER become a back-channel for briefs / implementer prompts / approvals that bypass the operator-hand-carried dispatch authority. The `role_mail.py` L1 lock extends to enforce this for the orchestrator recipient.

## 7. Build gate
New standing comms surface ⇒ a §3 tripwire ⇒ CHARC architecture pass + a dispatch when commissioned. Build only on operator green-light against the Stage-2 evidence bar. Until then this is reference only.

## 8. Grounding — Claude Code facts (from claude-code-guide consults 2026-06-14; documented vs observed flagged)
- **Documented:** every hook receives `session_id` + `transcript_path` in its JSON input. `SessionStart` fires + completes before the first prompt; carries a `source` field; fires on resume (same `session_id`). `Stop` fires per-turn (end of each response); `SessionEnd` is the termination hook (best-effort; no blocking; not guaranteed on abrupt exit/crash). Hooks fire identically in the VS Code integrated terminal vs standalone CLI. `tasks.json` `env` blocks scope env to the spawned terminal/session; `CLAUDE_ENV_FILE` is the native per-session env-injection mechanism (a `SessionStart` hook appends `export ROLE=...`). `claude --model/--effort/--permission-mode` exist; no `--env` flag.
- **Observed-but-UNDOCUMENTED (do not build on):** `CLAUDE_CODE_SESSION_ID` env var (a UUID matching the transcript filename); `CLAUDE_CODE_CHILD_SESSION=1` (a "I'm a nested subprocess" boolean, not an id).
- **Not available:** any documented way to enumerate live sessions externally — hence the self-maintained registry IS the enumeration.
