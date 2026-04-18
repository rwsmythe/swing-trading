"""Render BriefingViewModel → self-contained HTML string."""
from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment, FileSystemLoader, select_autoescape

from swing.rendering.view_models import BriefingViewModel

_TEMPLATES_DIR = files("swing.rendering").joinpath("templates")
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "html.j2"]),
    trim_blocks=True, lstrip_blocks=True,
)


def render_briefing_html(vm: BriefingViewModel) -> str:
    template = _env.get_template("briefing.html.j2")
    return template.render(vm=vm)
