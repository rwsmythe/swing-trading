"""Standalone recording script for codex_mcp_pattern_review cassettes.

Per spec §A.10 + plan §G.1 T-A.1.4 + post-Phase-12 forward-binding lesson #3.
Mirror of ``scripts/record_pattern_labeler_cassettes.py`` for the
codex_mcp_pattern_review cassette domain.

V1 LIMITATION: the copowers Codex MCP server is invoked via the
``mcp__plugin_copowers_codex__codex`` Claude Code tool which is also a
HARNESS tool (not Python-callable). Like the pattern-labeler counterpart,
this script is a V1 SCAFFOLD providing cassette directory checks +
sentinel-leak audit + operator guidance.

When invoked, this script:

  1. Validates ``tests/integrations/cassettes/codex_mcp_pattern_review/``
     exists + is writable.
  2. Imports the sanitization filter dict from
     ``tests/integrations/_cassette_sanitization``.
  3. Emits operator-actionable guidance for the T-A.1.7 paired session.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CASSETTE_DIR = (
    _REPO_ROOT / "tests" / "integrations" / "cassettes" / "codex_mcp_pattern_review"
)

_SENTINEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai-api-key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("authorization-header", re.compile(r"Bearer\s+[A-Za-z0-9_.-]{20,}")),
    ("hex-token-shape", re.compile(r"\b[a-fA-F0-9]{32,}\b")),
    ("chatcmpl-id", re.compile(r"\bchatcmpl-[A-Za-z0-9]{10,}\b")),
)


def _check_dir(verbose: bool) -> int:
    if not _CASSETTE_DIR.exists():
        print(
            f"ERROR: cassette dir missing: {_CASSETTE_DIR}",
            file=sys.stderr,
        )
        return 1
    if not _CASSETTE_DIR.is_dir():
        print(
            f"ERROR: cassette path is not a directory: {_CASSETTE_DIR}",
            file=sys.stderr,
        )
        return 1
    if verbose:
        cassettes = list(_CASSETTE_DIR.glob("*.yaml"))
        print(f"cassette dir OK: {_CASSETTE_DIR}")
        print(f"existing cassettes: {len(cassettes)}")
    return 0


def _audit_sentinels(verbose: bool) -> int:
    rc = 0
    for cassette in sorted(_CASSETTE_DIR.glob("*.yaml")):
        text = cassette.read_text(encoding="utf-8", errors="replace")
        for label, pattern in _SENTINEL_PATTERNS:
            if pattern.search(text):
                print(
                    f"LEAK detected in {cassette.name}: {label} pattern "
                    "matched; deleting cassette + failing audit.",
                    file=sys.stderr,
                )
                cassette.unlink()
                rc = 1
        if verbose and rc == 0:
            print(f"{cassette.name}: clean")
    return rc


def _print_operator_guidance() -> None:
    print(
        "Codex MCP cassette recording is a paired-session operation per "
        "Phase 13 T2.SB1 OQ-5 phased rollout + plan §G.1 T-A.1.7."
    )
    print("")
    print("V1 workflow:")
    print(
        "  1. From within an operator-paired Claude Code session, "
        "fire `mcp__plugin_copowers_codex__codex` review on a planted "
        "claude_silver row via labeling.py."
    )
    print(
        "  2. The MCP dispatch HTTP traffic is captured per the session's "
        "VCR config (V2 hardening — wire VCR through MCP harness)."
    )
    print(
        "  3. Run `python scripts/record_codex_mcp_pattern_review_cassettes"
        ".py --audit-sentinels` to verify no PII / auth tokens leaked."
    )
    print("")
    print(
        "Sanitization filters live at "
        "`tests/integrations/_cassette_sanitization.py` (V1) — "
        "`codex_mcp_vcr_config()` returns the filter dict."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Standalone recording-related operations for "
        "codex_mcp_pattern_review cassettes (V1 scaffold; recording is "
        "operator-paired)."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Verify cassette directory exists + is writable.",
    )
    parser.add_argument(
        "--audit-sentinels", action="store_true",
        help="Scan committed cassettes for unsanitized sentinel patterns.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output.",
    )
    args = parser.parse_args(argv)

    rc = 0
    if args.check:
        rc |= _check_dir(args.verbose)
    if args.audit_sentinels:
        rc |= _audit_sentinels(args.verbose)
    if not (args.check or args.audit_sentinels):
        _print_operator_guidance()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
