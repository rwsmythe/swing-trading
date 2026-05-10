"""Briefing exporter — writes HTML (+ optional MD) + chart files; enforces size cap."""
from __future__ import annotations

import base64
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from swing.rendering.briefing_md import render_briefing_md
from swing.rendering.html_renderer import render_briefing_html
from swing.rendering.view_models import BriefingViewModel


@dataclass(frozen=True)
class ExportResult:
    html_path: Path
    md_path: Path | None
    chart_paths: tuple[Path, ...]
    html_size_kb: float
    # charts_delinked = True means the size-cap branch ran (initial HTML was > cap).
    # It does NOT guarantee that inline charts were converted to file links — that
    # depends on whether any inline PNGs were present and valid. Callers wanting
    # "were fallback files produced?" should check `len(chart_paths) > 0`.
    charts_delinked: bool
    oversized: bool = False  # True if final briefing.html exceeds size_cap_kb even after delink


# PNG files start with this 8-byte signature.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _data_url_to_png_bytes(data_url: str) -> bytes | None:
    """Decode `data:image/png;base64,XXXX` → raw PNG bytes.
    Returns None on malformed input OR if decoded bytes don't start with the
    PNG signature (integrity check so we never write a non-PNG as a .png)."""
    if not data_url or not data_url.startswith("data:"):
        return None
    marker = ";base64,"
    idx = data_url.find(marker)
    if idx < 0:
        return None
    try:
        # validate=True rejects non-base64 chars (stricter than default permissive mode)
        raw = base64.b64decode(data_url[idx + len(marker):], validate=True)
    except (ValueError, base64.binascii.Error):
        return None
    if not raw.startswith(_PNG_SIGNATURE):
        return None
    return raw


def _delink_charts(
    vm: BriefingViewModel, *, href_tickers: set[str]
) -> BriefingViewModel:
    """Swap inline chart_b64 → chart_href for tickers whose chart file was actually
    written to out_dir/charts/. Tickers without a written chart have both cleared
    (neither inline nor broken link — spec §6.4 integrity)."""
    def _for(ticker: str, b64: str | None, href: str | None) -> tuple[str | None, str | None]:
        if ticker in href_tickers:
            return None, f"charts/{ticker}.png"
        # No actual chart file — drop both rather than emit broken link
        return None, href if ticker in href_tickers else None

    new_decisions = []
    for d in vm.todays_decisions:
        if d.chart_b64 and d.ticker in href_tickers:
            new_decisions.append(replace(d, chart_b64=None, chart_href=f"charts/{d.ticker}.png"))
        elif d.chart_b64:
            # inline was present but no file exists — drop both (no broken link)
            new_decisions.append(replace(d, chart_b64=None, chart_href=None))
        else:
            new_decisions.append(d)
    new_expansions = []
    for x in vm.expansions:
        if x.chart_b64 and x.ticker in href_tickers:
            new_expansions.append(replace(x, chart_b64=None, chart_href=f"charts/{x.ticker}.png"))
        elif x.chart_b64:
            new_expansions.append(replace(x, chart_b64=None, chart_href=None))
        else:
            new_expansions.append(x)
    return replace(vm, todays_decisions=new_decisions, expansions=new_expansions)


def export_briefing(
    *, vm: BriefingViewModel, out_dir: Path,
    chart_files: Mapping[str, Path],
    size_cap_kb: int = 500,
    retain_markdown_sibling: bool = True,
) -> ExportResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    chart_dest_dir = out_dir / "charts"
    chart_dest_dir.mkdir(exist_ok=True)

    # Step 1: copy any provided chart PNG source files into out_dir/charts/.
    written: list[Path] = []
    ticker_has_chart_file: set[str] = set()
    for ticker, src in chart_files.items():
        if src.exists():
            dst = chart_dest_dir / f"{ticker}.png"
            shutil.copy2(src, dst)
            written.append(dst)
            ticker_has_chart_file.add(ticker)

    # Step 2: render HTML. If over cap, delink inline charts — BUT before delinking,
    # extract any inline chart_b64 to a real PNG file in charts/ so the href resolves.
    # Without this, callers that pass inline b64 WITHOUT a corresponding chart_files
    # entry would leave a broken <a href> in the delinked briefing.
    html = render_briefing_html(vm)
    delinked = False
    if len(html.encode("utf-8")) / 1024 > size_cap_kb:
        # Decode inline b64 for tickers that don't already have a chart file on disk.
        for item in list(vm.todays_decisions) + list(vm.expansions):
            if item.ticker in ticker_has_chart_file:
                continue
            if not item.chart_b64:
                continue
            raw = _data_url_to_png_bytes(item.chart_b64)
            if raw is None:
                continue  # malformed or not a valid PNG — delink will drop both b64 and href
            dst = chart_dest_dir / f"{item.ticker}.png"
            dst.write_bytes(raw)
            written.append(dst)
            ticker_has_chart_file.add(item.ticker)
        html = render_briefing_html(_delink_charts(vm, href_tickers=ticker_has_chart_file))
        delinked = True

    html_path = out_dir / "briefing.html"
    html_path.write_text(html, encoding="utf-8")

    md_path: Path | None = None
    if retain_markdown_sibling:
        md_path = out_dir / "briefing.md"
        md_path.write_text(render_briefing_md(vm), encoding="utf-8")

    # Spec §6.4: size governance is advisory, not blocking. If the final file
    # STILL exceeds the cap after delinking charts (because non-chart content is
    # oversized — e.g. a pathologically long rationale), the briefing is written
    # anyway with `oversized=True` so the caller can surface a warning.
    final_size_kb = html_path.stat().st_size / 1024
    oversized = final_size_kb > size_cap_kb
    return ExportResult(
        html_path=html_path, md_path=md_path,
        chart_paths=tuple(written),
        html_size_kb=final_size_kb,
        charts_delinked=delinked,
        oversized=oversized,
    )
