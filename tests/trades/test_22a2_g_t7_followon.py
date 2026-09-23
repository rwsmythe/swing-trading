"""22-A2 Task 7 follow-on -- CHARC's G-T7 rulings Q1 and Q2.

Q1: the preview REFUSES supplied tier-2 evidence when the caller holds a
transaction -- a git subprocess under a caller-held SAVEPOINT is a network
call inside a transaction (S12.1 #9), and "today's only caller holds none" is
a promise about callers, not a property of the code (gotcha #31).  The guard
fires BEFORE the preflight, so no git process starts; the no-evidence preview
is unchanged.

Q2: ``FROZEN_VALUE_EVIDENCE_VERSION`` is BOUND to a digest of the source of
every function the seventh-column blob is a function of, through the pattern
``DERIVATION_RULE_HISTORY`` already runs for ``_derive``: an append-only
``(version, digest)`` history whose CURRENT pair is asserted here.  An edit to
any member without a version bump fails this file.

G-T7F + G-T7F-AMEND (CHARC): the digest hashes BEHAVIOUR -- each member's
``ast.dump`` with its docstring removed (functions and classes) or its AST
value (constants), so a docstring or comment edit moves nothing -- and it is
bound to ``FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION``, not to the GRAMMAR
version the 0039 trigger pins by literal.  ``read_artifact_facts`` is the
seventh root.
"""
from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest

from swing.trades import cohort_provenance_correction as cpc
from swing.trades import frozen_value_evidence as fve
from tests._tier2_world_22a2 import (
    T25_CANDIDATE_ID,
    T25_REC_ID,
    T25_TRADE_ID,
    build_last_word_world,
    build_pre_barrier_world,
    t25_cfg,
)
from tests.trades.test_22a2_correction_service import _evidence

REPO_ROOT = Path(__file__).resolve().parents[2]
REASON = "22-A2 G-T7 follow-on"
IN_TX_REFUSAL = ("tier-2 evidence needs a preflight outside any transaction; "
                 "call the preview on a connection that holds none")

# The members CHARC's Q2 ruling NAMES.  The digest is computed over their
# static reference closure; these are asserted present BY NAME so a refactor
# that stops reaching one fails here rather than silently leaving the pin.
RULED_MEMBERS = (
    "swing.trades.cohort_provenance_correction:_to_utc_naive",
    "swing.trades.frozen_value_evidence:build_interval",
    "swing.trades.frozen_value_evidence:render_price",
    "swing.trades.frozen_value_evidence:find_token",
    "swing.trades.frozen_value_evidence:evaluate_conjunction",
    "swing.trades.frozen_value_evidence:_build_frozen_value_blob",
    # G-T7F item 2: the seventh root, and the parser its closure brings.
    "swing.trades.frozen_value_evidence:read_artifact_facts",
    "swing.trades.frozen_value_evidence:_parse_reflog_instant",
)
FIRST_DERIVATION_VERSION = "2026-09-23.2"
# CHARC G-T9 item 2 moved ``read_artifact_facts`` (the per-invocation ref
# resolution): the second pair.
CURRENT_DERIVATION_VERSION = "2026-09-23.3"
GRAMMAR_VERSION = "2026-09-23.1"


# --------------------------------------------------------------------------- Q1

def _preview(conn, cfg, **kw) -> cpc.CohortProvenanceCorrectionPreview:
    return cpc.preview_cohort_provenance_correction(
        conn, trade_id=T25_TRADE_ID, cited_candidate_id=T25_CANDIDATE_ID,
        cited_recommendation_id=T25_REC_ID, reason=REASON, cfg=cfg, **kw)


def test_the_preview_refuses_tier2_evidence_under_a_caller_held_transaction(
    tmp_path: Path, monkeypatch,
) -> None:
    """PRE: the preview runs the git preflight inside the caller's transaction
    and returns a tier-2 preview.  POST: the typed refusal, ZERO git calls, and
    the caller's transaction untouched."""
    repo, evidence = _evidence(tmp_path)
    conn, _ids = build_pre_barrier_world(tmp_path, "t25")
    cfg = t25_cfg(tmp_path / "t25")
    calls: list[tuple] = []
    real = fve._run_git

    def _counted_git(repo_dir, *args):
        calls.append(args)
        return real(repo_dir, *args)

    monkeypatch.setattr(fve, "_run_git", _counted_git)
    try:
        conn.execute("BEGIN")
        assert conn.in_transaction
        with pytest.raises(cpc.CohortProvenanceCorrectionError) as exc:
            _preview(conn, cfg, frozen_value_evidence=evidence, evidence_repo=repo)
        assert calls == [], "git ran under a caller-held transaction"
        assert isinstance(exc.value, cpc.CallerHeldTransactionError)
        assert IN_TX_REFUSAL in str(exc.value)
        assert str(exc.value).endswith("Nothing was written.")
        assert conn.in_transaction, "the guard must not end the caller's transaction"
    finally:
        conn.rollback()
        conn.close()


def test_the_same_open_transaction_with_no_evidence_still_previews(
    tmp_path: Path,
) -> None:
    """The twin: the guard is scoped to SUPPLIED evidence.  Same caller-held
    transaction, no evidence -> the preview runs (a last-word world, which
    previews without a latch; trade 25's world would refuse at rung 9)."""
    conn = build_last_word_world(tmp_path)
    try:
        conn.execute("BEGIN")
        out = cpc.preview_cohort_provenance_correction(
            conn, trade_id=T25_TRADE_ID, cited_candidate_id=T25_CANDIDATE_ID,
            cited_recommendation_id=T25_REC_ID, reason=REASON, cfg=None)
        assert out.admission_tier == "last_word"
        assert conn.in_transaction
    finally:
        conn.rollback()
        conn.close()


# --------------------------------------------------------------------------- Q2

def test_the_derivation_version_is_bound_to_the_current_ast_digest() -> None:
    """The CURRENT pair, on the DERIVATION constant (G-T7F item 3 (B)).  An edit
    to any member's behaviour without a derivation bump (and an appended
    history entry) fails here -- with NO migration: SQL never binds the
    derivation version's value."""
    assert fve.frozen_value_evidence_digest() == fve.FROZEN_VALUE_EVIDENCE_HISTORY[-1][1], (
        "a member of the seventh-column blob's dependency closure changed BEHAVIOUR. "
        "APPEND a new (version, digest) entry to FROZEN_VALUE_EVIDENCE_HISTORY and move "
        "FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION with it in the SAME commit.")
    assert (fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION
            == fve.FROZEN_VALUE_EVIDENCE_HISTORY[-1][0])
    versions = [v for v, _d in fve.FROZEN_VALUE_EVIDENCE_HISTORY]
    assert len(versions) == len(set(versions))
    assert fve.FROZEN_VALUE_EVIDENCE_HISTORY[0][0] == FIRST_DERIVATION_VERSION


def test_the_grammar_version_is_split_from_the_derivation_version() -> None:
    """(A) the GRAMMAR version stays what 0039 pins by literal and is NOT the
    history's constant; (B) the derivation version is a DIFFERENT string, so a
    builder that wrote one constant into the other's key is visible."""
    assert fve.FROZEN_VALUE_EVIDENCE_VERSION == GRAMMAR_VERSION
    assert fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION == CURRENT_DERIVATION_VERSION
    assert [v for v, _d in fve.FROZEN_VALUE_EVIDENCE_HISTORY] == [
        FIRST_DERIVATION_VERSION, CURRENT_DERIVATION_VERSION]
    assert fve.FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION != fve.FROZEN_VALUE_EVIDENCE_VERSION
    assert GRAMMAR_VERSION not in [v for v, _d in fve.FROZEN_VALUE_EVIDENCE_HISTORY]


def test_the_digest_reaches_every_member_the_ruling_names() -> None:
    specs = {spec for _kind, spec, _body in fve.frozen_value_evidence_digest_parts()}
    for spec in RULED_MEMBERS:
        assert spec in specs, spec
    # The DERIVATION version is what the digest PINS; it is not an input to it.
    assert ("swing.trades.frozen_value_evidence:FROZEN_VALUE_EVIDENCE_DERIVATION_VERSION"
            not in specs)
    # The GRAMMAR version is a value the builder emits, so it is a member.
    assert "swing.trades.frozen_value_evidence:FROZEN_VALUE_EVIDENCE_VERSION" in specs


def _member_parts() -> dict[str, tuple[str, str]]:
    return {spec: (kind, body) for kind, spec, body in fve.frozen_value_evidence_digest_parts()}


def test_every_function_and_class_member_is_digested_from_its_ast_not_its_text() -> None:
    """PRE (source text): each body carries its docstring and its comments.
    POST: the body is the member's ``ast.dump`` with the docstring removed."""
    import importlib

    for spec, (kind, body) in _member_parts().items():
        if kind == "constant":
            continue
        mod_name, attr = spec.split(":")
        obj = getattr(importlib.import_module(mod_name), attr)
        node = ast.parse(inspect.getsource(obj)).body[0]
        assert body.startswith(f"{type(node).__name__}("), (spec, body[:40])
        doc = ast.get_docstring(node, clean=False)
        if doc:
            assert repr(doc) not in body, spec


def _parsed(source: str) -> ast.AST:
    return ast.parse(source).body[0]


def _redigest(spec: str, source: str) -> str:
    """The live parts with ONE member re-digested from a COPY of its source --
    never an edit to a module on disk."""
    parts = fve.frozen_value_evidence_digest_parts()
    out = [(k, s, fve._member_body(_parsed(source)) if s == spec else b)
           for k, s, b in parts]
    return fve.digest_of_parts(out)


def test_a_docstring_or_comment_edit_to_a_member_leaves_the_digest_unchanged() -> None:
    """D59's lesson on the one instrument that would otherwise force a version
    bump over prose.  A fixture COPY of ``build_interval`` (a function) and of
    ``ArtifactFacts`` (a class) with the docstring rewritten and a comment
    added re-digests to the LIVE digest."""
    live = fve.frozen_value_evidence_digest()
    for obj in (fve.build_interval, fve.ArtifactFacts):
        spec = f"{obj.__module__}:{obj.__qualname__}"
        source = inspect.getsource(obj)
        assert fve._member_body(_parsed(source)) == _member_parts()[spec][1]
        doc = ast.get_docstring(_parsed(source), clean=False)
        assert doc and doc in source
        edited = source.replace(doc, "A REWRITTEN docstring -- prose only.", 1)
        lines = edited.split("\n")
        edited = "\n".join([lines[0], "    # a comment never reaches the AST", *lines[1:]])
        assert edited != source
        assert _redigest(spec, edited) == live, spec


def test_a_one_token_body_edit_moves_the_digest() -> None:
    """The counterpart: ONE token of behaviour in a COPY moves the digest, so the
    current-pair test goes red until the derivation version moves."""
    live = fve.frozen_value_evidence_digest()
    spec = "swing.trades.frozen_value_evidence:_parse_reflog_instant"
    source = inspect.getsource(fve._parse_reflog_instant)
    assert source.count('"@{"') == 1
    assert _redigest(spec, source) == live
    assert _redigest(spec, source.replace('"@{"', '"@["', 1)) != live
    spec = "swing.trades.frozen_value_evidence:build_interval"
    source = inspect.getsource(fve.build_interval)
    assert " < " in source
    assert _redigest(spec, source.replace(" < ", " <= ", 1)) != live


def test_a_constant_member_is_digested_from_its_ast_value() -> None:
    kind, body = _member_parts()["swing.trades.frozen_value_evidence:COMPARE_DP"]
    assert kind == "constant"
    assert body == ast.dump(ast.Constant(value=2))


def test_the_walk_still_fails_loud_on_a_name_it_cannot_place(monkeypatch) -> None:
    monkeypatch.setattr(fve, "FROZEN_VALUE_EVIDENCE_DIGEST_ROOTS",
                        (*fve.FROZEN_VALUE_EVIDENCE_DIGEST_ROOTS,
                         "swing.trades.frozen_value_evidence:no_such_member"))
    with pytest.raises(LookupError, match="no_such_member"):
        fve.frozen_value_evidence_digest_parts()


def test_a_one_character_edit_to_any_member_moves_the_digest() -> None:
    """Computed over a modified SOURCE STRING, never by editing the module on
    disk.  The unmodified parts reproduce the live digest (so the mutation is
    applied to what is actually hashed), and a one-character change to ANY
    member's body -- each of the ruled six included -- moves it."""
    parts = fve.frozen_value_evidence_digest_parts()
    live = fve.frozen_value_evidence_digest()
    assert fve.digest_of_parts(parts) == live
    for i, (kind, spec, body) in enumerate(parts):
        assert body, f"{spec} contributes an empty body"
        flipped = body[:-1] + ("y" if body[-1] == "x" else "x")
        mutated = [*parts[:i], (kind, spec, flipped), *parts[i + 1:]]
        assert fve.digest_of_parts(mutated) != live, spec


def test_the_digest_is_a_function_of_the_value_not_of_the_run() -> None:
    """Two processes, two hash seeds, one digest.  ``repr`` of a set follows
    PYTHONHASHSEED; the derivation pin learned this on its first run."""
    code = ("from swing.trades.frozen_value_evidence import "
            "frozen_value_evidence_digest as d; print(d())")
    outs = set()
    for seed in ("0", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(REPO_ROOT)}
        proc = subprocess.run([sys.executable, "-c", code], cwd=str(REPO_ROOT),
                              capture_output=True, env=env, check=True)
        outs.add(proc.stdout.decode("ascii").strip())
    assert outs == {fve.frozen_value_evidence_digest()}
