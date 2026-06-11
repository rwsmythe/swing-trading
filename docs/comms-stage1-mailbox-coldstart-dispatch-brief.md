# Dispatch Brief — Comms Stage 1: Durable Role Mailbox + Director Cold-Start Launcher

**Audience:** Fresh Claude Code implementer instance with no prior conversation context.
**Commissioned by:** Tool Development Director (CHARC), operator-approved 2026-06-11 (charter `docs/tool-director-context.md` §2.6).
**Mission:** Build the Stage-1 inter-role communication layer: a durable file mailbox with an enforced message taxonomy, a stdlib CLI (`role_mail.py`), a PowerShell cold-start launcher that spins up the two director roles in CC CLI windows outside VS Code, a probe extension, and the orchestrator return-report posting convention. This removes the operator's manual relay of *information* between roles while preserving every operator *decision* point.
**Expected duration:** One session (~10–15 commits).

---

## 0. Read first

1. `docs/tool-director-context.md` — §2.5/§2.6 (harness custody + this commission), §4.2 (the probe this brief extends). The custodian-of-form boundary governs Task 6's limits.
2. `docs/orchestrator-context.md` §"Brief drafting" + §"Triage of return reports" — the section Task 6 amends.
3. `CLAUDE.md` §Conventions + §"Windows / tooling / test-discipline" — BINDING. Especially: the cp1252 stdout gotcha (ASCII-only output in all new scripts) and the `USERPROFILE`+`HOME` monkeypatch rule for any test touching home paths.
4. `scripts/harness_probe.py` and `scripts/weekly_glance.py` — the house style for read-only operational scripts (stdlib, ASCII, argparse, exit codes).

**Skill posture:** Execute directly from this brief (the design is operator-approved; do NOT run copowers:brainstorming/writing-plans). Use TDD for all Python (`superpowers:test-driven-development`). After all task commits land, run standalone adversarial review (`copowers:review`) on the combined diff to convergence (`NO_NEW_CRITICAL_MAJOR`; no round cap), fixing findings in new commits. Persist EVERY Codex round's full RESPONSE (not just prompts) to a gitignored file at repo root (e.g. `.codex-review-comms-stage1.md`).

---

## 1. Strategic context (compressed)

The project runs four human/AI roles: the operator (decides everything), two directors — CHARC (tool/harness) and the Research Director (research strategy) — and orchestrators (delivery managers in VS Code, who dispatch implementers like you). Today the operator hand-relays ALL traffic between roles. Decision (2026-06-11): automate the *information* flow (status, queries, orchestrator return reports) through a durable mailbox; keep all *authority* flow (decisions, commissions, dispatch prompts) operator-mediated. Directors will additionally run as long-lived CC CLI windows outside VS Code, cold-started by a script after reboots and reset the same way after context exhaustion.

Two constraints are load-bearing and non-negotiable:

- **L1 — Information vs authority.** Role→role messages are limited to types `fyi|status|query|return_report`. The type `decision_request` is valid ONLY when addressed to `operator`. `role_mail.py` ENFORCES this (hard error, nonzero exit). This is the governance protection; do not soften it.
- **L2 — No production code.** Nothing under `swing/` may change. This arc is scripts + docs + tests + one `.gitignore` line only.

---

## 2. Design locks (decided — do not re-open)

### 2.1 Mailbox layout — `comms/` at repo root, gitignored

```
comms/
  charc/inbox/      charc/read/
  rd/inbox/         rd/read/
  operator/inbox/   operator/read/
  .sessions.json    # launcher-maintained role -> {session_name, session_id} map
```

- Gitignored (one new `.gitignore` line). Message traffic is operational coordination; the durable record of decisions remains charters/briefs as today. NO deletion anywhere — `read` (ack) MOVES inbox→read; nothing is ever removed by tooling.
- Valid `--from`: `charc|rd|operator|orchestrator`. Valid `--to`: `charc|rd|operator` (comma-separated list accepted). No orchestrator inbox in V1 — director→orchestrator dispatch stays operator-hand-carried by design.

### 2.2 Message format — one file per message

Filename: `<UTC yyyymmddTHHMMSSZ>-<from>-<slug>.md` (slug from subject, `[a-z0-9-]`, ≤40 chars; on collision append `-2`, `-3`, …). Content:

```
---
from: charc
to: rd
type: status
subject: <one line>
posted: <UTC ISO8601>
thread: <optional slug>
---
<body, plain text/markdown>
```

Types: `fyi | status | query | return_report | decision_request` (L1 rule applies). Writer uses `encoding="utf-8"`; all CONSOLE output from the tools is ASCII-only (cp1252 gotcha).

### 2.3 `scripts/role_mail.py` — stdlib-only CLI

Subcommands (argparse):

- `post --from X --to Y[,Z] --type T --subject S (--body "..." | --body-file F | stdin)` — one file PER recipient inbox. Enforces L1 + valid role names.
- `list --role X [--unread-only]` — table: filename, from, type, subject, posted. Default lists inbox + count of read/.
- `read --role X [--all | --id <filename>]` — prints message(s) then moves them inbox→read.
- `peek --role X` — prints unread WITHOUT acking (for the operator glancing at another role's queue).
- Global `--comms-root PATH` (default `<repo>/comms`) — REQUIRED for testability; tests never touch the real `comms/`.

Exit codes: 0 ok; 1 validation/enforcement error (with a clear ASCII message). Auto-creates the directory tree on first use. No delete subcommand.

### 2.4 Cold-start launcher — `scripts/start_directors.ps1`

Windows PowerShell 5.1-compatible (no `&&`, no ternary — see CLAUDE.md). Parameters: `-Role charc|rd|both` (default `both`), `-Resume` (switch; default is fresh), `-NoWT` (skip Windows Terminal, use plain windows).

- **Preflight (mandatory):** run `claude --version` and `claude --help`; VERIFY the `-n` (session name) and `--resume` flags exist in the help text before using them; if absent, print an actionable ASCII error and exit 1 — do not launch with guessed flags. **Empirically verify** whether `claude "<prompt>"` auto-submits or only pre-fills the input (documentation is ambiguous; known-version-dependent). Document the observed behavior in the script header comment and the return report.
- **Fresh start (default):** per role, generate session name `director-<role>-<yyyymmdd-HHmm>`, record it to `comms/.sessions.json`, then open a Windows Terminal tab (`wt.exe -w 0 new-tab --title "<ROLE>" -d <repo>`) running `claude -n "<session-name>" "<bootstrap prompt>"`. Fallback when `wt.exe` is missing or `-NoWT`: `Start-Process powershell -ArgumentList '-NoExit', ...`. Launch roles SERIALLY (the session-mapping capture is not concurrency-safe; note this in a comment).
- **Resume:** read the role's `session_name` from `.sessions.json`; `claude --resume "<session-name>" "<re-entry prompt>"`. If the map is missing/empty for the role, print guidance to use fresh mode. Do NOT use `--continue` (it grabs the most-recently-touched session — wrong whenever two roles share this project dir) and do NOT use `--session-id` (unreliable in interactive mode; known upstream bug #44607).
- **Context reset = fresh mode** for that role: new dated name, map updated, old session left untouched on disk. Say so in the script's help text.
- Bootstrap prompts live in tracked files `scripts/director_bootstrap_charc.md` and `scripts/director_bootstrap_rd.md` (the launcher reads them; here-string quoting hazards avoided). Content (draft, polish allowed): identify the role; read the role's charter docs in full (`tool-director-context.md` for CHARC; `research-director-context.md` + `research-director-watch-standard.md` for RD); run `python scripts/role_mail.py read --role <role> --all`; for CHARC additionally run `python scripts/harness_probe.py`; then report current state and AWAIT the operator — take no actions beyond the bootstrap reads. The re-entry (resume) prompt is a short inline string: re-read charter section-of-record + drain the inbox + report.

### 2.5 Probe extension — `scripts/harness_probe.py`

Add a comms section: per-role unread count (INFO); ATTENTION when any unread message is older than 7 days; the operator inbox count is ALWAYS surfaced as its own line when nonzero. Skip silently-with-INFO when `comms/` doesn't exist. Update the §4.2 threshold table in `docs/tool-director-context.md` with one row (dated note, per the standard's amendment rule).

### 2.6 Orchestrator convention — `docs/orchestrator-context.md` amendment

Add a short dated subsection under §"Triage of return reports": after relaying a return report to the operator in chat (UNCHANGED — the operator's control point stays), the orchestrator ALSO posts the same return report via `role_mail.py post --from orchestrator --to charc,rd --type return_report ...`. Dispatch-direction traffic (briefs, implementer prompts, approvals) remains operator-hand-carried — state this explicitly in the amendment. Do NOT touch `docs/research-director-context.md` (peer-owned content; the RD records their own side).

---

## 3. Tasks

- **T1** — `.gitignore` entry (`comms/`) + `tests/scripts/__init__.py` scaffolding if needed. Commit.
- **T2** — `role_mail.py` via TDD: tests in `tests/scripts/test_role_mail.py` using `tmp_path` + `--comms-root` (NEVER the real `comms/`; tests touching home dirs must monkeypatch BOTH `USERPROFILE` and `HOME` per CLAUDE.md). Required coverage: post/list/read/peek round-trip; multi-recipient post; L1 enforcement (`decision_request` to `rd` → exit 1 + no file written); invalid role/type rejection; filename collision suffix; unread→read move; ASCII-only console output (assert `out.encode("cp1252")` does not raise).
- **T3** — the two bootstrap prompt files.
- **T4** — `start_directors.ps1` per §2.4. No automated test (PowerShell + interactive); acceptance is the operator gate (§5) plus the preflight self-checks.
- **T5** — probe extension per §2.5 + the one-row §4.2 table update.
- **T6** — orchestrator-context amendment per §2.6.
- **T7** — full fast suite green (`python -m pytest -q -n auto`) + `ruff check swing/ scripts/ tests/` clean + adversarial review to convergence (responses persisted) + fixes committed.

Conventional commits, task-scoped; NO `Co-Authored-By` footer, no `--no-verify`. Final commit message paragraph must be plain prose (trailer-parse hazard); verify `git log -1 --format='%(trailers)'` is empty.

## 4. Out of scope

MCP message-bus server (Stage 2) · autonomous wake/headless daemon (Stage 3) · SessionStart hooks · any edit to `docs/research-director-context.md` or the watch standard · anything under `swing/` · message deletion/retention tooling (phase-boundary item) · orchestrator inbox.

## 5. Done criteria + operator gate

Done = T1–T7 complete, suite green on the FINAL head (read the actual run output before claiming — never carry an earlier count forward), ruff clean, Codex converged with responses on disk. Then the **operator-witnessed gate** (binding, after your return): cold-start both directors via the launcher on a fresh terminal; post a test message each direction (charc→rd, rd→charc, one `decision_request`→operator); each director drains its inbox in-session; close a window and `-Resume` it by name; run the probe and see the comms section. You do NOT run this gate — the operator does; your return report must include the exact commands for it.

## 6. Return report

Structured markdown as your final message: per-task commit SHAs; test count delta; the observed `claude` flag behaviors from the T4 preflight (version, `-n`/`--resume` availability, prompt auto-submit vs pre-fill); Codex round count + verdict + evidence file path; deviations from this brief with rationale; the operator-gate command list. ALSO post the same report via `role_mail.py post --from orchestrator --to charc,rd --type return_report` — the first live use of the system you built.

## 7. If stuck

Flag-verification failures (missing `-n`/`--resume`) → stop T4, implement everything else, document in the return report with the `claude --help` output. Anything threatening L1/L2 → stop and report rather than improvise. Windows Terminal absent → the `-NoWT` fallback is the supported path, not a blocker.
