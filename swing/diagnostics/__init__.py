"""Diagnostic tooling: read-only audit + analysis CLIs.

Per Phase 13 T4.SB sec B.1 + sec B.7: each subcommand under ``swing diagnose``
emits a deterministic markdown report (+ CSV sidecar where applicable) to
``exports/diagnostics/`` and writes ZERO domain rows.
"""
