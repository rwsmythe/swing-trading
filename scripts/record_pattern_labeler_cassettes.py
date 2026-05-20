"""Standalone recording script for pattern_labeler cassettes.

Per spec §A.10 + plan §G.1 T-A.1.4 + post-Phase-12 forward-binding lesson #3:
standalone recording script is the recording mechanism (NOT
``@pytest.mark.vcr(record_mode='new_episodes')``). The script wires the
shared sanitization filters from ``tests/integrations/_cassette_sanitization``
+ outputs cassettes under ``tests/integrations/cassettes/pattern_labeler/``.

V1 LIMITATION (per L1 LOCK + Phase 13 T2.SB1 architecture):

The Claude Code ``Agent`` tool that the ``pattern-labeler`` subagent
dispatches through is a HARNESS tool — it is NOT callable from a standalone
Python script. Therefore this V1 recording script is a SCAFFOLD: it sets up
the VCR cassette infrastructure + sanitization filters + sentinel-leak
audit, then prints operator-actionable guidance about how to record
cassettes from within an operator-paired Claude Code session at T-A.1.7
(the operator-paired exemplar bootstrap pause).

When invoked, this script:

  1. Validates the cassette directory exists + is writable.
  2. Imports the sanitization filter dict from
     ``tests/integrations/_cassette_sanitization``.
  3. Emits operator guidance for the T-A.1.7 paired session.

Operator workflow (per OQ-6 + plan §G.1 T-A.1.7):

    python scripts/record_pattern_labeler_cassettes.py --check

    # ... operator runs `swing patterns label-exemplars` within Claude
    # Code session; the Agent tool invocation is recorded via VCR
    # automatically if VCR is mounted (V2 hardening candidate). For V1,
    # cassettes are populated manually by the operator from the paired
    # session's HTTP traffic. ...

    python scripts/record_pattern_labeler_cassettes.py --audit-sentinels

V2 hardening (banked): when the Claude Code harness exposes a Python-
callable Agent dispatch (or equivalent), wrap that dispatch in
``vcr.use_cassette(...)`` here to make recording fully scripted.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CASSETTE_DIR = _REPO_ROOT / "tests" / "integrations" / "cassettes" / "pattern_labeler"

# Sentinel patterns checked post-cassette-write — any match aborts + deletes
# the offending cassette (operator-actionable error).
_SENTINEL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("anthropic-api-key", re.compile(r"sk-ant-api03-[A-Za-z0-9_-]{40,}")),
    ("authorization-header", re.compile(r"Bearer\s+[A-Za-z0-9_.-]{20,}")),
    ("hex-token-shape", re.compile(r"\b[a-fA-F0-9]{32,}\b")),
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
    """Scan every cassette in the dir for unsanitized sentinel patterns.

    Returns 0 if all clean; 1 (and deletes offending files) if any leak.
    """
    rc = 0
    for cassette in sorted(_CASSETTE_DIR.glob("*.yaml")):
        text = cassette.read_text(encoding="utf-8", errors="replace")
        for label, pattern in _SENTINEL_PATTERNS:
            if pattern.search(text):
                # NEVER print the matched substring (token-shape; could leak).
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
        "Pattern-labeler cassette recording is a paired-session operation "
        "per Phase 13 T2.SB1 OQ-6 + plan §G.1 T-A.1.7."
    )
    print("")
    print("V1 workflow:")
    print(
        "  1. From within an operator-paired Claude Code session, "
        "run `swing patterns label-exemplars` per spec §5.9 step 1."
    )
    print(
        "  2. The Agent tool dispatch HTTP traffic is captured per the "
        "session's VCR config (V2 hardening — wire VCR through the harness)."
    )
    print(
        "  3. After labeling, run `python scripts/"
        "record_pattern_labeler_cassettes.py --audit-sentinels` to verify "
        "no PII / auth tokens leaked into the committed cassettes."
    )
    print("")
    print(
        "Sanitization filters live at "
        "`tests/integrations/_cassette_sanitization.py` (V1) — "
        "`pattern_labeler_vcr_config()` returns the filter dict."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Standalone recording-related operations for "
        "pattern_labeler cassettes (V1 scaffold; recording is operator-paired)."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Verify cassette directory exists + is writable.",
    )
    parser.add_argument(
        "--audit-sentinels", action="store_true",
        help="Scan committed cassettes for unsanitized sentinel patterns; "
        "delete + fail on any leak.",
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
