"""22-A2 Task 2 -- roster closure (A2-08) and the 22-A six-case byte pin (A2-09).

A2-08 walks the WHOLE ``tests/`` tree statically (never a run trace) for
module-level test functions carrying an ``a2_NN`` token and asserts, in BOTH
directions, that the set equals the registry: every registry id is implemented
by EXACTLY ONE test function in the module the registry names, and no test
function carries an id the registry does not know (a phantom).

A2-09 is brief section 4.5 mechanised (encoding E-14): "the 22-A six-case gate
stays GREEN byte-unchanged".  22-A2 adds an escape and moves nothing 22-A
ruled, so the test FUNCTIONS implementing 22-A cases 1-6 (AMN / OII / VSTS /
RHI / breach / boundary -- ids 1, 2, 3, 4, 5a, 5b, 6, plus the ``-pre`` twins
1-pre, 5b-pre, 6-pre) are pinned by sha256 of ``inspect.getsource``, captured
at base ``c212238a`` (byte-identical at ``05702929``: only docs changed
between).  Editing any of them is a visible red, never a quiet re-baseline.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import re
from pathlib import Path

import pytest

from tests.trades.case_registry_22a import PLAN_CASES, slug
from tests.trades.case_registry_22a2 import CASES_22A2, token

REPO_ROOT = Path(__file__).resolve().parents[2]

_TOKEN = re.compile(r"(?<![a-z0-9])a2_(\d{2,3}[a-z]?)(?![0-9])")


def _roster_tokens_in_tests() -> dict[str, list[tuple[str, str]]]:
    """token -> [(posix module path, function name)] over every test module."""
    found: dict[str, list[tuple[str, str]]] = {}
    for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "a2_" not in text:
            continue
        tree = ast.parse(text, filename=str(path))
        rel = path.relative_to(REPO_ROOT).as_posix()
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            for m in _TOKEN.finditer(node.name):
                found.setdefault(f"a2_{m.group(1)}", []).append((rel, node.name))
    return found


def test_a2_08_every_roster_id_has_exactly_one_implementing_test() -> None:
    found = _roster_tokens_in_tests()
    known = {token(rid): rid for rid in CASES_22A2}

    phantoms = sorted(t for t in found if t not in known)
    assert not phantoms, (
        f"test functions carry roster tokens the registry does not know: "
        f"{[(t, found[t]) for t in phantoms]}"
    )

    missing: list[str] = []
    wrong: list[str] = []
    for rid, module in sorted(CASES_22A2.items()):
        hits = found.get(token(rid), [])
        if len(hits) != 1:
            missing.append(f"{rid}: {len(hits)} implementing tests {hits}")
            continue
        if hits[0][0] != module:
            wrong.append(f"{rid}: in {hits[0][0]}, registry says {module}")
    assert not missing, missing
    assert not wrong, wrong


# -------------------------------------------------------------------------
# A2-09 -- the six-case byte pin (E-14).
# -------------------------------------------------------------------------
_W9 = "tests/trades/test_22a_task9_entry_wiring.py"
_W4 = "tests/trades/test_22a_task4_authorization_ladder.py"

SIX_CASE_PINS: dict[tuple[str, str], str] = {
    (_W9, "test_a_latched_fill_labels_from_the_fire_case_1"):
        "5948e3b13b265a66ed3eaac4e2616b3d96ff6bd581440102bcf652a427894c61",
    (_W9, "test_bucket_drift_is_not_death_case_1"):
        "9fb2d47c128c845a325a6d8e9f69a61d53614b8613521f1d8ab623987dd8652a",
    (_W9, "test_a_pre_barrier_fire_records_honest_unset_case_1_pre"):
        "235401b9d1c4e55ecef4d66c79b533f45a010415973492ee985fc4120e94a4d5",
    (_W9, "test_a_fill_with_no_latch_rows_falls_through_case_2"):
        "705215c8f95976b60cde990854a73ded0fbda24184f6e376caadb696fd3e9a2b",
    (_W9, "test_an_unfilled_mandate_is_untouched_by_the_arc_case_3"):
        "8ab5c60b1fd048dafb92036eae1a92235fcc59d7702c86d83cdb8f19012ff5f5",
    (_W4, "test_a_place_intent_without_a_validity_row_falls_through_case_4"):
        "4cd85aacdbd6ebaa38c3cb972444b7aca04a9191d80824a567ae5a757baec83b",
    (_W9, "test_a_breach_on_a_prior_session_refuses_case_5a"):
        "1151e8526629a489f2fca721ed25bf3761420a6c5de56b22aec3adccf833bdcf",
    (_W9, "test_the_discarded_label_is_logged_not_persisted_case_5a"):
        "4ef0dd3854fbfa7f1463095f4611c475b4ab979fcfc4c6eb2aa6adaee992c0bd",
    (_W9, "test_a_breach_on_the_fill_session_admits_case_5b"):
        "ac868f4497c5ed32cd627ec1f473f154286a91e5a5006257b1a90c37f180a7f9",
    (_W9, "test_the_pre_barrier_twin_of_the_tie_refuses_case_5b_pre"):
        "bc933d5b6769340e1b7d18233b63a2be29d18dcd746afc1389c91589ff16b59f",
    (_W9, "test_a_close_exactly_at_the_invalidation_admits_case_6"):
        "60683f03351c60ecdab5f21e7415e81797c8a7c3142930a14e581ec93977d2b5",
    (_W9, "test_the_display_precision_variant_varies_BOTH_operands_case_6"):
        "d323bbae4489c0cecf7f54bdceae47be3d2419caecede3044210b2b9c2e362a1",
    (_W9, "test_the_pre_barrier_twin_of_the_boundary_refuses_case_6_pre"):
        "e19a894ea3cceadd77e338916a9d54f88db7baac9f8a85e5ad9d3ae19324be49",
}

_SIX_CASE_IDS = ("1", "2", "3", "4", "5a", "5b", "6", "1-pre", "5b-pre", "6-pre")


def _source_sha(module_path: str, fn_name: str) -> str:
    mod = importlib.import_module(".".join(Path(module_path).with_suffix("").parts))
    src = inspect.getsource(getattr(mod, fn_name))
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def test_a2_09_six_case_functions_are_byte_unchanged() -> None:
    # Closure first: the pin set is EVERY implementing function of the ids,
    # found by the same name convention the 22-A closure check uses -- so a new
    # case-1..6 test added later cannot sit outside the pin unseen.
    for cid in _SIX_CASE_IDS:
        assert cid in PLAN_CASES, cid
    implementing: set[tuple[str, str]] = set()
    for path in sorted((REPO_ROOT / "tests").glob("**/test_22a_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            for cid in _SIX_CASE_IDS:
                if node.name.endswith(f"_case_{slug(cid)}"):
                    implementing.add(
                        (path.relative_to(REPO_ROOT).as_posix(), node.name))
    assert implementing == set(SIX_CASE_PINS), (
        sorted(implementing ^ set(SIX_CASE_PINS)))

    drifted = [
        key for key, pinned in SIX_CASE_PINS.items()
        if _source_sha(*key) != pinned
    ]
    assert not drifted, (
        f"22-A six-case test functions changed (brief 4.5 requires them "
        f"byte-unchanged): {drifted}"
    )


@pytest.mark.parametrize("rid", sorted(CASES_22A2))
def test_registry_tokens_are_well_formed(rid: str) -> None:
    assert re.fullmatch(r"A2-\d{2,3}[a-z]?", rid), rid
    assert _TOKEN.fullmatch(token(rid)), rid
