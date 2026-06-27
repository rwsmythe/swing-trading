# Comms Stage 1.5 — Mail UI + Unread Hook + Director Launch Button (focused-executing dispatch brief)

**Authored:** 2026-06-11 by CHARC (tool director). Design settled in operator dialogue 2026-06-11; this brief IS the locked design — no brainstorm phase. **Cycle shape: ONE focused-executing dispatch** (TDD per task; standalone `copowers:review` adversarial chain run to convergence; operator-witnessed browser gate at the end).
**Architecture pass:** satisfied by construction (CHARC-authored). No §3 tripwire: NO schema, NO new dependency, NO `swing/` touch, NO standing process (on-demand tool + an activity-gated hook).

---

## 1. What this is

A localhost browser UI over the comms Stage 1 file mailbox (`comms/`, `scripts/role_mail.py`), plus two riders:
(a) a `UserPromptSubmit` hook so director CC sessions self-surface unread mail on the operator's next prompt, and
(b) a UI button that runs `scripts/start_directors.ps1` to start/resume the director windows.

Operator usage contract (settled): on-demand only — up while the operator is at the computer; the durable mailbox absorbs everything in between. The UI is BOTH the operator's mail client AND a whole-bus observability view. Compose is **operator-identity only**.

## 2. Hard locks

- **L1 (inherited, do not soften):** `role_mail.py`'s governance lock — `decision_request` valid ONLY to operator — stays exactly as shipped. The UI never offers `decision_request` as a compose type at all (belt), and the compose handler server-stamps `from=operator` (a client-supplied sender field, if present in the POST, is IGNORED).
- **L2:** nothing under `swing/` is touched. The UI lives in `scripts/`, tests in `tests/scripts/`.
- **L3 (mail custody):** the UI never moves, acks, or deletes any file in a NON-operator mailbox. Ack exists only for `comms/operator/inbox/`. NOTHING in this arc deletes a message file, ever.
- **L4 (single write path):** the UI performs mail operations ONLY through `role_mail.py` functions (T1's extracted `post_message` / `ack_message`). No parallel compose/ack implementation, no direct frontmatter writing in `comms_ui.py`. A guard test enforces this (spy on `role_mail.post_message`).
- **L5 (launch endpoint):** the launch endpoint executes EXACTLY `powershell -NoProfile -File scripts/start_directors.ps1 -Role <role> [-Resume]` with `<role>` validated against the fixed enum `{both, charc, rd}` and mode against `{fresh, resume}`. No other subprocess surface; nothing user-typed reaches a command line.

## 3. Design (locked)

### 3.1 `scripts/comms_ui.py` — single-file FastAPI app
- App factory `create_app(comms_root: Path, allow_launch: bool = True) -> FastAPI` (factory takes the root so tests use `tmp_path`; NEVER the real `comms/` in tests — the Arc-2 suite-leak lesson applies to mailboxes too).
- `__main__` entry: `python scripts/comms_ui.py [--port 8765] [--comms-root PATH] [--no-browser]`. Binds `127.0.0.1` ONLY (hardcoded host). Default port 8765 (swing web owns 8080). Opens the default browser after server start unless `--no-browser`. Ctrl+C stops; the server holds NO state of its own.
- Templates embedded in the module via Jinja2 `DictLoader` (one reviewable file; no template dir under `scripts/`).
- Imports `role_mail` the same way `tests/scripts/test_role_mail.py` does (scripts/ is not a package — follow the existing sys.path/import pattern).
- fastapi/uvicorn/jinja2 come from the already-installed `[web]` extra — **no pyproject change**.

### 3.2 Page layout (one page + polled fragments)
- **Operator inbox pane (primary):** rows posted/from/type/subject; expand-in-place for body; `type=decision_request` rows visually flagged; per-message **Ack** + **Ack all**. Viewing NEVER auto-acks. Tab `<title>` carries the operator unread count.
- **Director bus pane:** charc + rd inboxes, READ-ONLY (no ack affordance — the UI acking a director's mail would mark messages the director never saw). Per-message age; >7 days styled stale (matches the harness-probe threshold).
- **History pane (collapsed by default):** `read/` of all three roles, newest-first, capped at 50, expandable rows.
- **Compose form:** to = charc/rd checkboxes (≥1 required); type = `fyi|status|query|return_report`; subject (single line); body textarea; optional thread. No sender field rendered.
- **Directors strip:** per-role unread count + whether `comms/.sessions.json` records a session; role selector (both/charc/rd) + **Start fresh** / **Resume** buttons; launcher stdout rendered into the flash panel.
- **Copy orchestrator spin-up button** (in the directors strip): copies the full text of `scripts/orchestrator_bootstrap.md` to the clipboard so the operator can paste it into a fresh VS Code CC chat. Served by a GET endpoint returning the file as `text/plain`; the button uses `navigator.clipboard.writeText` (localhost is a secure context) and flashes "copied". If the clipboard write is denied, reveal the text in a `<pre>` with a "copy manually" flash instead of failing silently. Read-only — no write surface, no origin guard needed.
- **Polling:** HTMX `hx-trigger="every 5s"` on the three list panes ONLY. The compose form and directors strip controls sit OUTSIDE every polled region (a refresh must never clobber half-typed input). The page carries its own `htmx.config.responseHandling` override enabling 4xx swaps (the known gotcha applies to this standalone app too — validation errors render as fragments).

### 3.3 Origin guard (all POSTs)
Localhost servers are CSRF-able (any webpage can blind-POST to `127.0.0.1:8765`; the launch endpoint spawns token-burning Claude windows). Every POST route runs a same-origin check: if an `Origin` (or, failing that, `Referer`) header is present it MUST match this app's own origin, else 403; a POST with NEITHER header present is also rejected 403 (browsers send Origin on same-origin form posts; curl-without-headers is not a supported client for writes). GETs are unguarded.

### 3.4 `role_mail.py` refactor (T1 — the single-write-path enabler)
Extract two PURE functions, keeping the CLI behavior byte-identical:
- `post_message(root, sender, recipients, mtype, subject, body, thread=None) -> list[Path]` — everything `cmd_post` does after arg unpacking (validation, L1 lock, CR/LF frontmatter-injection guard, atomic multi-recipient staging + rollback). `cmd_post` becomes a thin argparse adapter over it.
- `ack_message(root, role, filename) -> Path` — the move inbox→read via `_unique_dest` (never-overwrite). `cmd_read` delegates per file.
ALL existing tests in `tests/scripts/test_role_mail.py` (28) and `tests/scripts/test_harness_probe_comms.py` (9) must stay green UNMODIFIED except where they reasonably gain the pure-function variants. The L1-lock test coverage must hold against `post_message` directly (not only through argparse).

### 3.5 Launch endpoint (T5)
- `POST /directors/launch` with `role` + `mode` form fields (enums per L5). Runs the L5 command via `subprocess.run(..., capture_output=True, timeout=30)` — the launcher exits quickly after spawning windows. Render stdout+stderr (ASCII-sanitized) into the flash panel; nonzero exit renders as an error flash, not a 500.
- Tests mock subprocess and assert the EXACT argv list (the discriminating-kwargs discipline); no test spawns a real window.

### 3.6 Unread hook (T6)
- `scripts/comms_unread_hook.py` — stdlib-only. Reads `SWING_ROLE` from the environment; if unset or not in `{charc, rd}` → exit 0 silently (this makes the hook a no-op in every orchestrator/VS Code/ad-hoc session). Resolves the repo root from `__file__` (NOT cwd). Counts `comms/<role>/inbox/*.md`; if >0 prints ONE ASCII line, e.g. `[comms] 2 unread for charc (1 decision_request) -- run: python scripts/role_mail.py read --role charc --all`. ALWAYS exit 0 (a hook failure must never block the operator's prompt); any internal exception → silent exit 0.
- `.claude/settings.json`: does NOT exist today and `.claude/*` is gitignored. Add a `.gitignore` negation (`!.claude/settings.json`, same pattern as the existing tracked-`agents/` exception) and commit a minimal settings file containing ONLY the `UserPromptSubmit` hook entry (`python scripts/comms_unread_hook.py`). The operator's `settings.local.json` is NOT touched; hook arrays merge across settings files.
- `start_directors.ps1`: set `SWING_ROLE=<role>` in each spawned director window. **TRAP (verified): a naive `$env:SWING_ROLE='charc'` before `Start-Process` does NOT reliably propagate** — `wt.exe -w 0 new-tab` hands the tab to an ALREADY-RUNNING Windows Terminal process, which spawns the shell from ITS environment, not the launcher's. Fix: wrap the claude invocation in a `powershell -NoExit -Command` shell that sets the var first, in BOTH the wt path and the `-NoWT` fallback (the fallback already uses this wrapper shape). This is the Stage-1 brief's known quoting hazard — verify with `-DryRun` printing the exact command lines, and the operator gate witnesses the hook firing end-to-end. The existing `-n`/`--resume`/`--model`/`--effort`/`--permission-mode` preflights and flag behavior must survive unchanged.

### 3.7 Error handling
- `MailError` from compose → 400 fragment, message in flash, form values preserved.
- Ack of an already-moved file (operator drained via CLI in parallel) → idempotent "already acked" flash + pane refresh, NOT a 500.
- Malformed frontmatter in any pane → render filename + raw text fallback (the parser already degrades to `{}`).
- Page content is UTF-8 (browser); console prints from the server process stay ASCII (cp1252 gotcha).

## 4. Tasks (TDD each: failing test → minimal impl → pass → commit)

| # | Task | Notes |
|---|---|---|
| T1 | `role_mail.py` extract `post_message`/`ack_message`; CLI delegates | existing 28+9 tests green; new pure-function tests incl. L1 direct |
| T2 | `comms_ui.py` app factory + read-only page/fragments (inbox, bus, history) + polling wiring | TestClient + tmp root |
| T3 | Compose POST (server-stamped operator; type allowlist sans decision_request; via `post_message`; flash 400s) | guard test: client `from` field ignored; spy proves L4 |
| T4 | Ack endpoints (operator only; via `ack_message`; idempotent miss) | guard test: NO ack route exists for charc/rd |
| T5 | Directors strip + launch endpoint + origin guard on all POSTs + orchestrator spin-up copy button | subprocess mocked, exact-argv assert; origin 403 tests; copy endpoint serves the bootstrap file verbatim |
| T6 | Unread hook script + tracked `.claude/settings.json` + gitignore negation + launcher `SWING_ROLE` wrapper | `-DryRun` verification; launcher preflights unchanged |
| T7 | Convergence: standalone `copowers:review` (WSL transport) to NO_NEW_CRITICAL_MAJOR; full fast suite + `ruff check swing/ scripts/ tests/scripts/` on the FINAL head; return report | persist EVERY Codex round's RESPONSE to a gitignored `.codex-review-comms-ui.md` |

Commit style: conventional, `feat(comms):`/`fix(comms):`/`test(comms):`; ZERO Co-Authored-By; final `-m` paragraph plain prose (trailer-parse hazard).

## 5. Operator-witnessed gate (binding; orchestrator schedules with the operator)

1. `python scripts/comms_ui.py` → browser opens; all panes render the REAL `comms/` content.
2. Compose → charc: lands in `comms/charc/inbox/` (CLI `list` confirms); bus pane reflects it within one poll interval.
3. From a separate shell, CLI-post to operator → the inbox pane and tab-title count pick it up within ~5s, NO manual refresh.
4. Ack in UI → file moves to `read/` (CLI confirms); double-ack race → friendly flash, no 500.
5. Launch button (fresh or resume) → director window(s) actually open.
6. Hook end-to-end: with unread mail for a director, type any prompt in that director's window → the director self-surfaces the unread context without being told. ALSO witness the unseeded default: a session WITHOUT `SWING_ROLE` shows zero hook noise (the seeded-gate-masks-default lesson).
7. Origin guard: a POST with a foreign `Origin` header → 403 (curl).
8. Copy button → paste into any editor → content matches `scripts/orchestrator_bootstrap.md` verbatim.

## 6. Out of scope

MCP bus (Stage 2) · autonomous wake of idle sessions (Stage 3 — explicitly held; the hook signals on ACTIVITY only) · message deletion/retention tooling · orchestrator inbox · any `swing/` change · auth beyond loopback+origin-guard · mobile/remote access.

## 7. Return report

Post via the mailbox (the Stage-1 lifecycle convention): `python scripts/role_mail.py post --from orchestrator --to charc,operator --type return_report ...` — per-task commits, test counts on the final head, Codex rounds + verdict, deviations with rationale, gate script for the operator.
