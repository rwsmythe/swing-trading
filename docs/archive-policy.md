# Archive policy -- the external D: drive

Operator direction 2026-10-29: anything not needed for active development is
PRUNED if no longer needed, or ARCHIVED on the external drive D: in an
appropriate folder. This includes archived DBs. CHARC executed the first pass
the same day; this note is the standing rule and the record.

## The rule

- Archive root: `D:\swing-trading-archive\` (index at its `README.md`). The
  layout mirrors the source tree: `swing-data\...` for the live data dir,
  `repo\...` for gitignored repo artifacts.
- Archive = MOVE (robocopy /MOV or /MOVE; exit codes under 8 are success);
  never copy-and-keep. Leave a short pointer file at the source.
- Prune = delete only what is regenerable or must not be archived: pytest
  temp trees (`.tmp-*`), dead credential files (`schwab-tokens.*.deleted-*`).
- Tracked files are never moved: git is their archive (`docs/archive`,
  `legacy`, `reference/archive`).
- Never archive anything running code reads: `swing.db`, `prices-cache`,
  `prices_cache`, `charts` (static mount + `chart_renders` rows),
  `data/finviz-inbox` (cited by `pipeline_runs.finviz_csv_path`), the two
  newest weekly backups, transcripts cited by OPEN register rows.
- The D: drive is exFAT with a large cluster size: `du` over-reports small
  files. Measure by file count, not `du`, for mail and transcripts.

## First pass, 2026-10-29

| Source | Action | Size |
|---|---|---|
| `~/swing-data/backups` (all but `swing-202643/44.db`) | moved | 36.6 GB, 139 files |
| `~/swing-data/review-transcripts` folders dated before 2026-10 | moved | 25 folders |
| `~/swing-data/research-cache` | moved | 100 MB |
| `~/swing-data/logs/*.gz`, `scratch/`, `diagnose-*.txt` | moved | 21 MB |
| `comms/<role>/read` stamped before 20260830 | moved | 1,377 files |
| `exports/archive/*.zip`, repo-root `.codex-*` | moved | 39 MB |
| `schwab-tokens.production.db.deleted-*` (29) | deleted | 230 KB |
| `.tmp-phase5/6/7` | deleted | 372 MB |

`~/swing-data` went from 43 GB to 5.5 GB.

## Re-archive triggers (the things that regrow)

- Weekly backups: `runner.py` keeps 12 (`_BACKUP_RETENTION_WEEKS`), ~1.9 GB
  each at today's DB size. Move all but the newest two to D: every few weeks,
  or lower the constant (a code change, its own rider).
- Pre-migration gate images: every schema-bumping merge writes one to
  `backups/pre-images`. Move it to D: after the migration's witness closes.
- `exports/archive/*.zip`: `archive_old_exports` writes one per month past
  `retention_days`. Move at phase close.
- `swing schwab logout` leaves a `*.deleted-<stamp>` token file each run.
  Delete them; never archive them.
- `review-transcripts/<arc>`: move when the arc's register row closes.
- `comms/<role>/read`: move mail older than ~60 days at phase close.
