"""Briefing exporter — writes HTML (+ optional MD) + chart files; enforces size cap."""
from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from swing.rendering.briefing_md import render_briefing_md
from swing.rendering.html_renderer import render_briefing_html
from swing.rendering.view_models import BriefingViewModel, TodaysDecisionVM, TickerExpansionVM


@dataclass(frozen=True)
class ExportResult:
    html_path: Path
    md_path: Path | None
    chart_paths: list[Path]
    html_size_kb: float
    charts_delinked: bool


def _delink_charts(vm: BriefingViewModel) -> BriefingViewModel:
    new_decisions = [
        replace(d, chart_b64=None,
                chart_href=f"charts/{d.ticker}.png" if d.chart_b64 else d.chart_href)
        for d in vm.todays_decisions
    ]
    new_expansions = [
        replace(x, chart_b64=None,
                chart_href=f"charts/{x.ticker}.png" if x.chart_b64 else x.chart_href)
        for x in vm.expansions
    ]
    return replace(vm, todays_decisions=new_decisions, expansions=new_expansions)


def export_briefing(
    *, vm: BriefingViewModel, out_dir: Path,
    chart_files: Mapping[str, Path],
    size_cap_kb: int = 500,
    retain_markdown_sibling: bool = True,
) -> ExportResult:
    out_dir.mkdir(parents=True, exist_ok=True)

    html = render_briefing_html(vm)
    delinked = False
    if len(html.encode("utf-8")) / 1024 > size_cap_kb:
        html = render_briefing_html(_delink_charts(vm))
        delinked = True

    html_path = out_dir / "briefing.html"
    html_path.write_text(html, encoding="utf-8")

    md_path: Path | None = None
    if retain_markdown_sibling:
        md_path = out_dir / "briefing.md"
        md_path.write_text(render_briefing_md(vm), encoding="utf-8")

    chart_dest_dir = out_dir / "charts"
    chart_dest_dir.mkdir(exist_ok=True)
    written: list[Path] = []
    for ticker, src in chart_files.items():
        if src.exists():
            dst = chart_dest_dir / f"{ticker}.png"
            shutil.copy2(src, dst)
            written.append(dst)

    return ExportResult(
        html_path=html_path, md_path=md_path,
        chart_paths=written,
        html_size_kb=html_path.stat().st_size / 1024,
        charts_delinked=delinked,
    )
