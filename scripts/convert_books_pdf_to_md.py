"""One-shot PDF -> markdown converter for reference/Books/*.pdf.

Outputs to reference/Books/<slug>/<slug>.md + reference/Books/<slug>/figures/.
Skips files where the target markdown already exists (idempotent re-runs).
Skips the Minervini "Think & Trade Like a Champion" duplicate that was
previously converted to reference/minervini/.
"""

from __future__ import annotations

import pathlib
import re
import sys
import time

import pymupdf4llm

BOOKS_DIR = pathlib.Path("reference/Books")
# Already converted to reference/minervini/ — skip the duplicate copy here.
SKIP_FILENAMES = {
    "Mark Minervini - Think & Trade Like a Champion-Access Publishing Group (2017).pdf",
}


def slugify(name: str) -> str:
    """Lower-case, hyphenate, strip noise — produce a stable filesystem-safe slug."""
    stem = pathlib.Path(name).stem
    # Drop noisy parenthetical suffixes like "( PDFDrive )" / "(2013)" / "_New" etc.
    stem = re.sub(r"\(\s*pdfdrive\s*\)", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"_new\b", "", stem, flags=re.IGNORECASE)
    # Collapse non-alphanumeric to hyphen, lowercase, strip leading/trailing hyphens.
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    # Collapse double-hyphens.
    slug = re.sub(r"-+", "-", slug)
    return slug


def convert_one(pdf_path: pathlib.Path) -> None:
    slug = slugify(pdf_path.name)
    out_dir = BOOKS_DIR / slug
    out_md = out_dir / f"{slug}.md"
    fig_dir = out_dir / "figures"
    if out_md.exists():
        print(f"[skip] {pdf_path.name} -> {out_md} already exists")
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"[start] {pdf_path.name} -> {out_md}")
    try:
        md = pymupdf4llm.to_markdown(
            str(pdf_path),
            write_images=True,
            image_path=str(fig_dir),
            image_format="png",
            dpi=150,
            page_chunks=False,
        )
        out_md.write_text(md, encoding="utf-8")
        dt = time.time() - t0
        n_figs = len(list(fig_dir.glob("*.png")))
        print(
            f"[done]  {pdf_path.name} -> {len(md):,} chars, {n_figs} figures, "
            f"{dt:.1f}s"
        )
    except Exception as e:
        dt = time.time() - t0
        print(f"[FAIL]  {pdf_path.name} after {dt:.1f}s: {type(e).__name__}: {e}")


def main() -> int:
    if not BOOKS_DIR.is_dir():
        print(f"error: {BOOKS_DIR} not found", file=sys.stderr)
        return 1
    pdfs = sorted(BOOKS_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"no PDFs in {BOOKS_DIR}")
        return 0
    print(f"converting {len(pdfs)} PDFs from {BOOKS_DIR}")
    t_total = time.time()
    for pdf in pdfs:
        if pdf.name in SKIP_FILENAMES:
            print(f"[skip] {pdf.name} (handled separately in reference/minervini/)")
            continue
        convert_one(pdf)
    print(f"\nall done in {(time.time() - t_total) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
