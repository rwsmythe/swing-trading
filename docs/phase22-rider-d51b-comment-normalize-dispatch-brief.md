# Phase 22 rider D51b -- line-start-only comment normalization in the schema-manifest hash -- dispatch brief

**Audience:** a fresh implementer cell (`implementer-sonnet-high`) with no prior context. **From:** the orchestrator. **Authority:** CHARC's disposition of the D51 live-probe finding (register row D59, `eca56da3`), transcribed in section 1. **Codex:** NONE, declared with reason by CHARC: a normalization function + two pins + fixture regeneration, covered by the suite. **Worktree:** `.worktrees/d51b-comment-norm`, branch `d51b-comment-norm`, off `main`. **Sequencing:** this rider lands BEFORE 22-A2 merges. 22-A2's Task 3 also regenerates the fixture, and the orchestrator re-runs `--write` on the merged head at that merge.

## 1. The ruling (the spec)

**Author: CHARC. Courier: the orchestrator.** Transcribed BYTE-FOR-BYTE (script-extracted, span verified present) from `comms/orchestrator/read/20260923T005201Z-charc-d51-probe-finding-ruled-comment-normaliz.md` (posted 2026-09-23T00:52:01Z).

> **D51 LIVE-PROBE FINDING -- DISPOSITION: (b), NORMALIZE COMMENTS OUT BEFORE HASHING, in the LINE-START-ONLY form: before the existing whitespace collapse, drop every line whose first non-blank characters are `--`. Never a general `--`-to-end-of-line strip: that form reaches INSIDE string literals (six DDL lines in the migrations carry `--` inside a quoted RAISE message) and would silently drop the rest of those lines from the hash on both sides -- a sensitivity loss the line-start form does not have, because no DDL string literal in this repo begins a line with `--`. The fixture is regenerated once (every hash moves; the object set does not), the header comment names the normalization, and two tests pin it: a comment-only DDL difference (the live 0008 shape, planted as a raw `CREATE TABLE` with and without a full-line comment) compares CLEAN, and a one-token semantic difference in the same object still reads CHANGED. (a) is REFUSED: a hand-maintained allowlist keyed on a live hash is the D21/D28 roster class and would need a new entry every time history is touched. (c) is REFUSED on the orchestrator's own ground: a standing known-red on a probe is how a real red is waved through. (d) was correctly never offered. DECLARED LIMIT, with its reason: the probe is now blind to comment-only edits of an applied migration -- harmless by definition, since SQLite stores comments verbatim and executes none of them; the class the probe exists for is the SEMANTIC in-place edit, which it still catches. D51 CLOSES on this disposition landing and the live probe reading CLEAN at v38.**

**The live evidence the ruling rests on.** On 2026-09-22 the operator ran `python scripts/schema_manifest.py --db "$USERPROFILE/swing-data/swing.db"`, which printed `schema_version 38` and `changed: table hypothesis_registry` and exited 1. Live `hypothesis_registry` lacks three full-line `--` comments that migration 0008 gained in place at `9fa6bd5a` after it was applied (live DDL 647 chars; fresh 841).

## 2. Tasks (TDD; one red-green per change)

1. **Test first**, in `tests/data/test_schema_manifest_head.py`: (i) a raw `CREATE TABLE` pair differing ONLY by a full-line `--` comment (the live 0008 shape) compares CLEAN; (ii) the same object with a one-token semantic difference reads CHANGED; (iii) a DDL line whose string literal CONTAINS `--` mid-line keeps that text in the hash (so the line-start-only form is pinned against a general strip). See all three fail or pass as appropriate against the current code, then implement.
2. **`scripts/schema_manifest.py`**: before the existing whitespace collapse, drop every line whose first non-blank characters are `--`. Never strip `--` to end of line elsewhere.
3. **Regenerate** `tests/data/schema_manifest_head.tsv` with `python scripts/schema_manifest.py --write`. Every hash moves; the OBJECT SET must not. Verify with a diff of column 1..2 (kind + name) before vs after: identical. The header comment names the normalization.
4. **Full fast suite**: `python -m pytest -m "not slow" -q -n 4`, green. Then `ruff check scripts/ tests/data/`, with no new violations.

## 3. Binding

- Conventional commits, no trailers (check `git log -1 --format='%(trailers)'` is empty), no `--no-verify`, no amend, no push, no merge.
- NEVER any `git stash` command.
- NEVER open the live DB through `swing` code. The live probe is the OPERATOR's step after merge, not yours.
- Do not run `scripts/role_mail.py`.

## 4. Return report (final chat message)

Commits with subjects, the trailer audit, the three tests and what each discriminates (pre-fix vs post-fix result), the object-set-unchanged proof, suite + ruff verbatim, and anything open.
