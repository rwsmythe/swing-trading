"""Harness-vs-production parity check (Hypothesis 5).

Compares production's persisted per-criterion evaluation results against
harness ``evaluate_one`` output for identical inputs. Pre-registration
study doc: ``research/studies/harness-vs-production-parity.md``.

Phase isolation: this package consumes ``swing/`` modules read-only. No
production-code mutation. Tests live under ``tests/research/parity/``.
"""
