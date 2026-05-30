"""Phase 14 Sub-bundle 3 (T-3.1) L5 zero-orphan grep gate.

After the atomic rename of the chart-detail surface/function/constant/field/
template-var/CSS-class to the 'ticker_detail' family, NO runtime path under
``swing/`` may still reference the old tokens -- EXCEPT the frozen 0020
migration (historical record) and the 0023 rename migration (legitimately
references the old token in its CASE rewrite). Test files are NOT scanned
(SCAN covers only ``swing/**``), so negative-assertion tokens there are fine.
"""
import fnmatch
import pathlib

FORBIDDEN = (
    "hyprec_detail",
    "render_hyprec_detail_svg",
    "hyprec-detail-chart",
    "_HYPREC_DETAIL_SIZE_PX",
    "hyp-rec detail",
)
ALLOW_GLOBS = (
    "swing/data/migrations/0020_*.sql",
    "swing/data/migrations/0023_*.sql",
)
SCAN = [
    "swing/**/*.py",
    "swing/**/*.sql",
    "swing/web/templates/**/*.j2",
    "swing/web/templates/**/*.html",
    "swing/web/static/**/*.css",
    "swing/web/static/**/*.js",
]


def test_no_orphaned_hyprec_detail_tokens():
    root = pathlib.Path(__file__).resolve().parents[2]
    offenders = []
    for pattern in SCAN:
        for path in root.glob(pattern):
            rel = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, g) for g in ALLOW_GLOBS):
                continue
            text = path.read_text(encoding="utf-8")
            for tok in FORBIDDEN:
                if tok in text:
                    offenders.append(f"{rel}: {tok}")
    assert offenders == [], offenders
