# Phase 22 — harness riders: the D54 stale-name sweep + the probe's Gotchas-cap reconciliation (§4.2)

**Author:** CHARC, 2026-09-14. **Commissioned:** operator, 2026-09-14 ("proceed" on the queue).
**Executor:** the orchestrator dispatches ONE cell; tests + `scripts/` + one charter table row only; NO production `swing/` code.
**Expected size:** four commits. Mechanical with two sharp edges (§1.3's shadowing proof; §2's ATTENTION flip on the live repo).

**Tripwire self-check (harness §5):** none crossed. No Reviewer B required (charter §2.9 binds B to arcs touching production code); Reviewer A runs at the `fast` tier to convergence. **Cell recommendation:** `implementer-sonnet-high` — settled design, multi-file mechanical edits that still need care.

---

## §0 READ FIRST (pointers)

1. `docs/tool-director-context.md` §4 row **D54** (the three members, with the orchestrator's counts) and §4.2 (the probe standard whose table this brief amends).
2. CLAUDE.md §Gotchas, last bullet ("A version-mirror test's NAME is a claim…") — the ruled canonical form `_is_head` and the two-changes-never-one-commit rule.
3. `docs/orchestrator-context.md` §"Size-check trigger at housekeeping-commit time" — the table row for CLAUDE.md §"Gotchas" (`>~55K chars total, OR any single gotcha >~700 chars`) and for line 3 (`>2,000 chars`). These are the OPERATIVE numbers; the probe's are the stale ones.
4. `scripts/harness_probe.py` (the CLAUDE.md block; the `report()` helper; the exit contract) and `tests/scripts/test_harness_probe_*.py` (the existing test shape — mirror it).
5. `docs/harness-architecture.md` §5.1 SUPERSESSION-BY-REPLACEMENT: a stale "name preserved for continuity" comment is DELETED, not annotated.

## §0.1 SKILL POSTURE

No `brainstorming`/`writing-plans`. TDD for §2 (red first). No mailbox posts; the return report is your final chat message to the orchestrator.

---

## §1 D54 — three stale names, three commits (never with a version bump; none touches `EXPECTED_SCHEMA_VERSION`)

Verified on disk by CHARC 2026-09-14 (method: `grep -n`, `sed -n` on `main @ 032dd277`):

**1.1** `tests/data/test_migration_0017.py` — `test_account_equity_snapshots_table_exists_with_8_columns` asserts `len(cols) == 10` beneath a comment saying the name is "preserved for git-history continuity". Rename to `test_account_equity_snapshots_table_has_the_head_column_set`; DELETE the continuity comment and the trailing `# Phase 11: 8 -> 9 … Phase 16: 9 -> 10` annotation (the `_AES_EXPECTED_COLS` set assertion already carries the contract; keep the `== 10` count assert only if the set assert does not subsume it — it does; drop it and say so). One commit.

**1.2** `tests/data/test_migration_0019_atomic_apply.py:78` — `test_migration_0019_applies_against_v18_baseline` builds NO v18 baseline: it calls `ensure_schema` on an empty path, asserts `post == 38`, then checks sub-bundle-C objects exist. The name is a false SETUP claim. Rename to `test_head_schema_carries_sub_bundle_c_objects`; rewrite the docstring to what the test does; the `== 38` assertion is HEAD-tracking — replace the literal with `EXPECTED_SCHEMA_VERSION` (imported) so this test never joins the `_is_NN` class again. One commit.

**1.3** `tests/pipeline/conftest_temporal.py:25` — fixture `tmp_db_v22` walks to HEAD; its docstring cites a "stale-name-but-current-target per cumulative discipline" convention that no live rule doc contains. Rename to `tmp_db_at_head` at the definition and EVERY reference. Count with method, reported in the return: CHARC's `grep -rn tmp_db_v22 tests/ | wc -l` = **117 lines across 9 files** (the D54 row's "103 references across 9 files" was a different count of the same family — report yours and say which lines are definition/docstring vs use). DELETE the convention sentence by replacement. **Its own commit, and the shadowing proof is mandatory:** a fixture is requested BY NAME, so a missed reference does not fail — it resolves to nothing or to a same-named fixture elsewhere. Before and after: `python -m pytest --collect-only -q tests/pipeline tests/integration | tail -1` (collected count identical) AND `grep -rn "tmp_db_v22" tests/ swing/ scripts/ research/` = 0 after. Also grep `tests/` for any OTHER fixture already named `tmp_db_at_head` before choosing the name (a collision would silently shadow).

**1.4** The CLAUDE.md gotcha's "~16 such" figure is the orchestrator's; do not edit CLAUDE.md here.

## §2 §4.2 reconciliation — ONE threshold set, MEASURED by the probe every run

**The defect (banked 2026-09-08):** two cap sets exist. `scripts/harness_probe.py` says CLAUDE.md total 100,000 / line-3 9,000 and does not look at the Gotchas section at all; `orchestrator-context.md`'s trigger table says Gotchas ~55,000 / any bullet ~700 / line-3 2,000. On 09-08 the probe printed OK while the operative trigger was OVER on line 3 and 363 chars from the Gotchas breach. A cap the instrument does not measure is a cap nobody sees.

**The ruling (CHARC, hygiene lane): the orchestrator-context numbers are the operative set; the probe adopts them and the charter table is amended to match.** Specifically:

- `CLAUDE_MD_LINE3_CHARS_MAX = 2_000` (was 9,000).
- NEW `CLAUDE_MD_GOTCHAS_CHARS_MAX = 55_000`: the Gotchas section = from the line `## Gotchas` to the next top-level `## ` header or EOF; report chars; ATTENTION over the cap.
- NEW `CLAUDE_MD_GOTCHA_BULLET_CHARS_MAX = 700`: a "bullet" = a line inside that section starting with `- ` (top-level only; `###` subheaders and blockquotes are not bullets). Report `bullets: N, over 700: M`; ATTENTION when M > 0, and list the FIVE largest as INFO lines (`<chars> <first 60 chars of the bullet>`), so the compression owner sees the budget without a second tool.
- `CLAUDE_MD_TOTAL_CHARS_MAX` stays 100,000 (no competing number exists).
- Amend the charter's §4.2 table (`docs/tool-director-context.md`) — CHARC-owned content, text supplied here VERBATIM, replace the two CLAUDE.md rows and add one:
  - `| CLAUDE.md line-3 chars | always reported | > 2,000 | RECONCILED 2026-09-14 to the orchestrator-context trigger (was 9,000; the probe read OK on 09-08 while the operative trigger was OVER) |`
  - `| CLAUDE.md §Gotchas section chars | always reported | > 55,000 | added 2026-09-14 — the orchestrator-context cap, now MEASURED; 363 chars from breach on 09-08 and invisible to the probe |`
  - `| CLAUDE.md §Gotchas bullets over 700 chars | count + the five largest | any | added 2026-09-14 — the per-bullet trigger+fix cap; the compression list rides the next gotcha commit |`

**Expected consequence, stated so nobody "fixes" it:** on the live repo the probe will now print ATTENTION for line 3 (4,083) and for the bullets (24 over 700 as of 09-09) and exit 1. That is the instrument telling the truth about a compression that is already owed (the orchestrator's, at the next gotcha commit). Do NOT raise the caps to make it green. Check `grep -rn harness_probe tests/ scripts/` for anything asserting exit 0 against the LIVE repo (as opposed to a synthetic root) and report what you find; a live-repo exit-0 assertion is the D9 class (a test coupled to ambient state) and is retired, not satisfied.

**Tests (red first, `tests/scripts/test_harness_probe_claude_md.py`, synthetic root under `tmp_path`):** (a) a CLAUDE.md whose Gotchas section is under all caps → the three lines read OK; (b) one bullet of 701 chars → the bullet line reads ATTENTION and names it in the top-five; a 700-char bullet → OK (the boundary twin); (c) a section of 55,001 chars → ATTENTION; (d) line 3 of 2,001 chars → ATTENTION, 2,000 → OK; (e) no `## Gotchas` header → INFO "section not found", never a crash. Assert on the printed lines the way the existing probe tests do.

## §3 LOCKS

- Tests + `scripts/harness_probe.py` + the one charter table row ONLY. No `swing/` edit of any kind.
- Never rename in the same commit as anything else; four commits, each pathspec-scoped.
- Full fast suite on the final head (`-n 4` if `-n auto` is memory-killed in your seat — D52); ruff clean.

## §4 RETURN (the ORCHESTRATOR posts to `charc` after QA)

Head SHA; the four commit SHAs; the 1.3 before/after collection counts and the zero-grep; the 1.2 `EXPECTED_SCHEMA_VERSION` substitution; the live-repo probe output after §2 (expected: two ATTENTIONs, exit 1) quoted; the finding on any live-repo exit-0 assertion; the A-loop verdict line; the suite line with SHA.
