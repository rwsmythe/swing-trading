# Phase 22 rider — cell_depth prints each transcript's BUILD and RESOLVED MODEL ID (dispatch brief)

**From:** the orchestrator. **Commissioned:** CHARC FYI 2026-09-22 (`comms/orchestrator/read/20260922T222308Z-charc-opus-5-5-float-accepted-model-id-build-r.md`; decision-of-record charter §2.11), which folded the model-id half into the build-version rider this seat already owed from D57. Operator "dispatch the rider", 2026-09-22.
**Cell:** `implementer-sonnet-high` — settled design, one stdlib script, one test file, no production code.
**Worktree:** `.worktrees/cell-depth-model` off `main` at or above the commit that lands this brief. **Rules read from main by absolute path:** `C:/Users/rwsmy/swing-trading/docs/implementer-dispatch-recipe.md` — name the `main` SHA you read it at in your return report.
**Review:** **NO Codex round — declared, with reason:** a read-only, stdlib-only operator instrument under `scripts/` that nothing in `swing/` imports; its correctness is checked by the orchestrator at QA against live transcripts whose build and model are already measured (§4). The fast suite on the final head is still binding.

## §0 READ FIRST

- `scripts/cell_depth.py` (213 lines) and `tests/scripts/test_cell_depth.py` (173 lines) — the whole of what changes.
- **Record shape, MEASURED 2026-09-22 by the orchestrator over 4 main-session and 3 cell transcripts on this box** (re-measure it yourself before building on it):
  - `version` is a **TOP-LEVEL** key on transcript records (e.g. `{"type": "assistant", "version": "2.1.280", "message": {...}}`), present on essentially every record.
  - The model is **`message.model`** on assistant records (e.g. `"claude-opus-5-5"`, `"claude-sonnet-5"`, `"claude-fable-5-1"`). There is NO top-level `model` key.
  - A **`"<synthetic>"`** `message.model` value occurs (1 record in session `daef757e`, a harness-injected message). It is not a model that did work, so **it is excluded.**
  - Every measured file carried exactly ONE distinct `version` and ONE distinct real model. Nothing guarantees that. A mixed file is a real state (e.g. a mid-session `/model` switch), and the instrument must SHOW it rather than choose one value.

## §1 THE CHANGE, exactly

**C1 — `read_cell` collects the builds and models.** `CellDepth` gains two fields, `build: str` and `model: str`:
- `build` = the distinct top-level `version` string values in **first-seen order**, joined with `+`, and `-` when there are none.
- `model` = the distinct `message.model` string values, **excluding `<synthetic>`**, in first-seen order, joined with `+`, and `-` when there are none.
- A record whose `version`/`model` is missing or not a string contributes nothing. Keep the existing tolerance: a partial trailing line and non-dict records are skipped exactly as today. Collect from EVERY parsed record, not only the ones that carry `usage`. The build is on user and tool records too, and the depth logic's `usage` gate must not become the model gate by accident.

**C2 — every output row prints both.** `format_rows` adds `build` and `model` columns between `flag` and the transcript name, in both modes (cells and `--sessions`), with header labels `build` and `model`. Widths: pad to 9 and 16 respectively. Never truncate a value: a mixed `a+b` value that overflows its column shifts the rest of the row, and that is correct, because a clipped model id reads as a DIFFERENT model. ASCII only (cp1252 stdout).

**C3 — the module docstring** gains one short paragraph: what `build` and `model` are, where each is read from (top-level `version`; `message.model`, `<synthetic>` excluded), and why this is dispatcher-read (a cell cannot see which model it is; the `opus` alias floats with the build, charter §2.11). No other docstring changes.

## §2 TESTS (TDD — red first, for its own reason)

Extend the `_record` helper with optional `version=None, model=None` kwargs, placed at the record's real locations (top-level `version`; `message.model`). Existing callers stay unchanged.

1. **Single build and model are read from their real locations.** A cell with records carrying `version="2.1.280"`, `model="claude-opus-5-5"` gives `build == "2.1.280"` and `model == "claude-opus-5-5"`. Plant at least one record with NO `usage` that carries a DIFFERENT, earlier `version`, as the first record. **The discriminator:** an implementation that reads only `usage`-bearing records gets the wrong `build`.
2. **`<synthetic>` is excluded.** Records with `model="<synthetic>"` and `model="claude-sonnet-5"` give `model == "claude-sonnet-5"`. A file whose ONLY model is `<synthetic>` gives `-`.
3. **Mixed values are shown in first-seen order, not collapsed.** Versions `2.1.272, 2.1.272, 2.1.280` give `"2.1.272+2.1.280"`. Models `claude-opus-5, claude-opus-5-5, claude-opus-5` give `"claude-opus-5+claude-opus-5-5"`. Assert the exact strings: last-wins, first-wins and sorted implementations must all FAIL (the sorted order here is the same as first-seen for versions, so add a model pair whose sorted order differs from its first-seen order, e.g. `claude-sonnet-5` then `claude-opus-5-5`).
4. **Absent fields degrade to `-`.** The existing shape (`_record` with no version/model) gives `build == model == "-"` with no exception. All existing tests stay green unmodified, apart from any header-string assertion the new columns legitimately change (report any such change).
5. **CLI rows carry both, in both modes.** Through `main([...])` with `capsys`, one cell with `2.1.280`/`claude-sonnet-5`, and in `--sessions` mode one main session with `2.1.272`/`claude-fable-5-1`. Each value appears on its own row's line, the header contains `build` and `model`, and the output encodes as ASCII (`out.encode("ascii")`).

## §3 SCOPE — exactly this, refuse the rest

`scripts/cell_depth.py` + `tests/scripts/test_cell_depth.py`. **NOTHING under `swing/`.** No change to the depth sum, the cap, the exit codes, `--live`/`--all`/`--sessions` semantics, the slug logic or the sort order. No new flag. No docs outside the script's own docstring: the recipe line that USES this output is the orchestrator's, landed at merge. **Not yours:** the positive control (counting `text` vs `thinking` records at the first Opus 5.5 cell). The orchestrator runs that at the first Opus cell accept; do not build a counter for it. Suite: the fast suite with `-n 4` (D52: `-n auto` is memory-killed on this box, and another cell may be running its suite concurrently), BEFORE handoff and on the final head.

## §4 WHAT THE ORCHESTRATOR WILL CHECK AT QA (so you know the bar)

Running the branch's script against the REAL `~/.claude/projects` must reproduce these values, measured before dispatch:

| transcript | build | model |
|---|---|---|
| session `daef757e…` (the prior orchestrator) | `2.1.272` | `claude-opus-5` (its one `<synthetic>` record excluded) |
| session `4a938de4…` (this orchestrator) | `2.1.280` | `claude-opus-5-5` |
| cell `agent-a3529ef854b2f9562` (D56's executing cell) | `2.1.272` | `claude-sonnet-5` |

You may run the same check yourself (`python scripts/cell_depth.py --sessions --all` and `--all` from the worktree); it is read-only.

## §5 RETURN (per recipe §4; your final chat message, never a mailbox)

Commits (SHA + one line each) · the red run for test 1 and test 3 (the failing assertion text) · the fast-suite tail READ OFF THE FINAL HEAD with its SHA · the `main` SHA you read the recipe at · the output of `python scripts/cell_depth.py --sessions --live 2` and `--live 2` from the worktree (the new columns, live) · the trailer audit (`git log <base>..HEAD --format='%H%n%(trailers)'`, all empty) · deviations, if any.
